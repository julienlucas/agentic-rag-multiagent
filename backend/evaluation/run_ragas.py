# Évalue la qualite RAG via Ragas: faithfulness, answer_relevancy, context_precision/recall.

import argparse
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings

from backend.agents.workflow import AgentWorkflow
from backend.agents.research_agent import ResearchAgent
from backend.config.settings import settings
from backend.evaluation.utils import build_retriever_for_file, load_dataset, log_to_langsmith, resolve_file_path


def _build_llm():
    if not settings.MISTRALAI_API_KEY:
        raise RuntimeError("MISTRALAI_API_KEY manquant")
    return ChatMistralAI(
        model=settings.MODEL_ID,
        api_key=settings.MISTRALAI_API_KEY,
        temperature=0,
        max_tokens=300,
    )


def _build_embeddings():
    if not settings.MISTRALAI_API_KEY:
        raise RuntimeError("MISTRALAI_API_KEY manquant")
    return MistralAIEmbeddings(
        model=settings.EMBEDDING_MODEL_ID,
        api_key=settings.MISTRALAI_API_KEY,
    )

def _run_inference(example: Dict, retriever, mode: str) -> Dict:
    question = example["question"].strip()
    expected_answer = example.get("expected_answer", "").strip()
    if not expected_answer:
        return {}

    docs = retriever.invoke(question)
    contexts = [d.page_content for d in docs]

    if mode == "baseline":
        answer = ResearchAgent().generate(question, docs)["draft_answer"]
    else:
        answer = AgentWorkflow().full_pipeline(question, retriever)["draft_answer"]

    return {
        "question": question,
        "answer": answer,
        "contexts": contexts,
        "ground_truth": expected_answer,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Chemin vers le dataset JSONL")
    parser.add_argument("--mode", default="agentic", choices=["baseline", "agentic"])
    parser.add_argument("--out-dir", default="ragas_outputs")
    parser.add_argument("--max-items", type=int, default=0)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    if args.max_items:
        dataset = dataset[: args.max_items]

    retrievers = {}
    rows = []
    for example in dataset:
        file_path = resolve_file_path(example)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fichier introuvable: {file_path}")
        if file_path not in retrievers:
            retrievers[file_path] = build_retriever_for_file(file_path)
        row = _run_inference(example, retrievers[file_path], args.mode)
        if row:
            rows.append(row)

    if not rows:
        raise RuntimeError("Aucune ligne valide (expected_answer manquant)")

    ds = Dataset.from_list(rows)
    llm = _build_llm()
    embeddings = _build_embeddings()
    start = time.time()
    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        embeddings=embeddings,
    )
    elapsed = round(time.time() - start, 2)

    df = result.to_pandas()
    summary = {
        "count": len(df),
        "elapsed_sec": elapsed,
        "faithfulness": round(mean(df["faithfulness"]), 4),
        "answer_relevancy": round(mean(df["answer_relevancy"]), 4),
        "context_precision": round(mean(df["context_precision"]), 4),
        "context_recall": round(mean(df["context_recall"]), 4),
    }
    summary["percent"] = {k: round(v * 100, 2) for k, v in summary.items() if k not in {"count", "elapsed_sec"}}

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "ragas_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out_dir, "ragas_results.json"), "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    log_to_langsmith(
        name="run_ragas",
        summary=summary,
        inputs={"dataset": args.dataset, "mode": args.mode},
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
