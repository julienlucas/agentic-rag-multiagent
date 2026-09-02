# Évalue retrieval + QA classique: Recall@k/MRR/nDCG, F1, erreurs/regressions.

import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.agents.workflow import AgentWorkflow
from backend.agents.research_agent import ResearchAgent
from evaluation.utils import build_retriever_for_file, load_dataset, log_to_langsmith, resolve_file_path
from evaluation.llm_judge import LLMJudge
from backend.config.settings import settings


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> List[str]:
    return _normalize(text).split()


def _f1_score(pred: str, ref: str) -> float:
    pred_toks = _tokens(pred)
    ref_toks = _tokens(ref)
    if not pred_toks or not ref_toks:
        return 0.0
    common = {}
    for tok in pred_toks:
        common[tok] = common.get(tok, 0) + 1
    overlap = 0
    for tok in ref_toks:
        if common.get(tok, 0) > 0:
            overlap += 1
            common[tok] -= 1
    precision = overlap / max(len(pred_toks), 1)
    recall = overlap / max(len(ref_toks), 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _context_hits(docs, expected_answer: str, keywords: Optional[List[str]]) -> bool:
    context = "\n\n".join(getattr(d, "page_content", "") for d in docs)
    if expected_answer:
        if _normalize(expected_answer) in _normalize(context):
            return True
    if keywords:
        norm_ctx = _normalize(context)
        return any(_normalize(k) in norm_ctx for k in keywords if k)
    return False


def _normalize_list(values: Optional[List[str]]) -> List[str]:
    return [_normalize(v) for v in (values or []) if v]


def _token_overlap_score(gold_text: str, doc_text: str) -> float:
    """Calcule le ratio de tokens du gold présents dans le doc."""
    gold_toks = _tokens(gold_text)
    if not gold_toks:
        return 0.0
    doc_toks_set = set(_tokens(doc_text))
    matched = sum(1 for t in gold_toks if t in doc_toks_set)
    return matched / len(gold_toks)


def _doc_relevance_flags(docs, gold_passages: Optional[List[str]], fuzzy_threshold: float = 0.6) -> List[int]:
    """
    Détermine la pertinence de chaque doc par rapport aux gold passages.
    Utilise un matching hybride : substring exact OU token overlap >= seuil.
    """
    if not gold_passages:
        return []
    gold = _normalize_list(gold_passages)
    flags = []
    for doc in docs:
        content = _normalize(getattr(doc, "page_content", ""))
        # Match exact (substring) — rapide
        if any(g in content for g in gold):
            flags.append(1)
            continue
        # Match fuzzy (token overlap) — rattrape les reformulations et coupures
        if any(_token_overlap_score(g, content) >= fuzzy_threshold for g in gold):
            flags.append(1)
            continue
        flags.append(0)
    return flags


def _recall_at_k(flags: List[int], k: int) -> Optional[float]:
    if not flags:
        return None
    total_relevant = sum(flags)
    if total_relevant == 0:
        return 0.0
    return min(sum(flags[:k]) / total_relevant, 1.0)


def _mrr_at_k(flags: List[int], k: int) -> Optional[float]:
    if not flags:
        return None
    for idx, rel in enumerate(flags[:k], start=1):
        if rel:
            return 1.0 / idx
    return 0.0


def _ndcg_at_k(flags: List[int], k: int) -> Optional[float]:
    if not flags:
        return None
    dcg = 0.0
    for i, rel in enumerate(flags[:k], start=1):
        if rel:
            dcg += 1.0 / math.log2(i + 1)
    ideal = sorted(flags, reverse=True)
    idcg = 0.0
    for i, rel in enumerate(ideal[:k], start=1):
        if rel:
            idcg += 1.0 / math.log2(i + 1)
    if idcg == 0:
        return 0.0
    return dcg / idcg


def _parse_section_header(line: str) -> Optional[str]:
    """Extrait le nom de section depuis une ligne `# Factual (8)` / `# Multi-passage (2)`."""
    line = line.strip()
    if not line.startswith("#"):
        return None
    m = re.match(r"^\s*#\s*(.+?)\s*\(\d+\)\s*$", line)
    if m:
        return m.group(1).strip()
    return None


def _example_labels_for_dataset(path: str) -> List[str]:
    """Une étiquette par ligne JSON, alignée sur load_dataset (ex. « Factual 3 », « Numerical 2 »)."""
    labels: List[str] = []
    current_category = ""
    idx_in_section = 0
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            cat = _parse_section_header(line)
            if cat is not None:
                current_category = cat
                idx_in_section = 0
                continue
            if line.startswith("#"):
                continue
            json.loads(line)
            idx_in_section += 1
            if current_category:
                labels.append(f"{current_category} {idx_in_section}")
            else:
                labels.append(f"Example {idx_in_section}")
    return labels


def _parse_verification_flags(report: str) -> Tuple[Optional[bool], Optional[bool], Optional[bool]]:
    supported = None
    relevant = None
    has_unsupported = None
    for line in (report or "").splitlines():
        line = line.strip().lower()
        if line.startswith("**supporté:**"):
            supported = "oui" in line
        if line.startswith("**pertinent:**"):
            relevant = "oui" in line
        if line.startswith("**affirmations non supportées:**"):
            has_unsupported = "aucune" not in line and "[]" not in line
    return supported, relevant, has_unsupported


def evaluate_example(example: Dict, retriever, mode: str, llm_judge: Optional[LLMJudge] = None) -> Dict:
    question = example["question"].strip()
    expected_answer = example.get("expected_answer", "").strip()
    keywords = example.get("answer_keywords", [])
    gold_passages = example.get("gold_passages", [])

    result = {
        "id": example.get("id"),
        "question": question,
        "expected_answer": expected_answer,
        "mode": mode,
    }

    if mode == "baseline":
        docs = retriever.invoke(question)
        answer = ResearchAgent().generate(question, docs)["draft_answer"]
        supported = None
        relevant = None
    else:
        docs = retriever.invoke(question)
        pipeline_result = AgentWorkflow().full_pipeline(question, retriever)
        answer = pipeline_result["draft_answer"]
        supported, relevant, has_unsupported = _parse_verification_flags(pipeline_result["verification_report"])

    result["answer"] = answer
    result["context_hit"] = _context_hits(docs, expected_answer, keywords)
    result["answer_f1"] = _f1_score(answer, expected_answer) if expected_answer else 0.0
    result["supported"] = supported
    result["relevant"] = relevant
    if mode == "agentic":
        # Ces deux signaux venaient du VerificationAgent, retiré en avril 2026 : le rapport
        # ne contient plus les lignes "**Supporté:**" / "**Affirmations non supportées:**".
        # Sans ce None, bool(None is False) valait False sur chaque question et le rapport
        # annonçait un « 0 % d'hallucinations » que rien n'avait mesuré. La métrique
        # d'hallucination vivante est celle du juge LLM (judge_is_hallucination).
        if supported is None and has_unsupported is None:
            result["hallucinated"] = None
        else:
            result["hallucinated"] = bool((supported is False) or (has_unsupported is True))
    result["gold_passages"] = gold_passages

    # LLM-as-a-Judge évaluation
    if llm_judge and settings.EVAL_LLM_JUDGE_ENABLED and expected_answer:
        context = "\n\n".join(getattr(d, "page_content", "") for d in docs)
        judge_result = llm_judge.evaluate(
            question=question,
            expected_answer=expected_answer,
            generated_answer=answer,
            context=context
        )
        result["judge_correctness"] = judge_result.correctness
        result["judge_faithfulness"] = judge_result.faithfulness
        result["judge_completeness"] = judge_result.completeness
        result["judge_correctness_reason"] = judge_result.correctness_reason
        result["judge_faithfulness_reason"] = judge_result.faithfulness_reason
        result["judge_completeness_reason"] = judge_result.completeness_reason
        result["judge_is_hallucination"] = judge_result.is_hallucination

    return result


def aggregate(results: List[Dict], k_values: List[int]) -> Dict:
    if not results:
        return {}
    f1s = [r["answer_f1"] for r in results]
    hits = [r["context_hit"] for r in results]
    supported = [r["supported"] for r in results if r["supported"] is not None]
    relevant = [r["relevant"] for r in results if r["relevant"] is not None]
    hallucinated = [r["hallucinated"] for r in results if r.get("hallucinated") is not None]
    base = {
        "count": len(results),
        "mean_f1": round(mean(f1s), 4),
        "context_hit_rate": round(sum(hits) / len(hits), 4),
        "supported_rate": round(sum(1 for v in supported if v) / len(supported), 4) if supported else None,
        "relevant_rate": round(sum(1 for v in relevant if v) / len(relevant), 4) if relevant else None,
        "hallucination_rate": round(sum(1 for v in hallucinated if v) / len(hallucinated), 4) if hallucinated else None,
    }
    retrieval = {}
    for k in k_values:
        recall_vals = [r.get(f"recall@{k}") for r in results if r.get(f"recall@{k}") is not None]
        mrr_vals = [r.get(f"mrr@{k}") for r in results if r.get(f"mrr@{k}") is not None]
        ndcg_vals = [r.get(f"ndcg@{k}") for r in results if r.get(f"ndcg@{k}") is not None]
        if recall_vals:
            retrieval[f"recall@{k}"] = round(mean(recall_vals), 4)
        if mrr_vals:
            retrieval[f"mrr@{k}"] = round(mean(mrr_vals), 4)
        if ndcg_vals:
            retrieval[f"ndcg@{k}"] = round(mean(ndcg_vals), 4)
    base["retrieval"] = retrieval

    # LLM Judge metrics
    judge_correctness = [r.get("judge_correctness") for r in results if r.get("judge_correctness") is not None]
    judge_faithfulness = [r.get("judge_faithfulness") for r in results if r.get("judge_faithfulness") is not None]
    judge_completeness = [r.get("judge_completeness") for r in results if r.get("judge_completeness") is not None]
    judge_hallucinations = [r.get("judge_is_hallucination") for r in results if r.get("judge_is_hallucination") is not None]

    if judge_correctness:
        base["llm_judge"] = {
            "mean_correctness": round(mean(judge_correctness), 2),
            "mean_faithfulness": round(mean(judge_faithfulness), 2) if judge_faithfulness else None,
            "mean_completeness": round(mean(judge_completeness), 2) if judge_completeness else None,
            "hallucination_rate": round(sum(1 for v in judge_hallucinations if v) / len(judge_hallucinations), 4) if judge_hallucinations else None,
            "perfect_faithfulness_rate": round(sum(1 for v in judge_faithfulness if v >= 4) / len(judge_faithfulness), 4) if judge_faithfulness else None,
        }

    return base


def _percent(value: Optional[float]):
    if value is None:
        return None
    return round(value * 100, 2)


def _percent_block(block: Dict) -> Dict:
    out = {}
    for key in ["mean_f1", "context_hit_rate", "supported_rate", "relevant_rate", "hallucination_rate"]:
        if key in block:
            out[key] = _percent(block[key])
    if "retrieval" in block:
        out["retrieval"] = {k: _percent(v) for k, v in block["retrieval"].items()}
    if "llm_judge" in block:
        out["llm_judge"] = {
            "mean_correctness": block["llm_judge"].get("mean_correctness"),
            "mean_faithfulness": block["llm_judge"].get("mean_faithfulness"),
            "mean_completeness": block["llm_judge"].get("mean_completeness"),
            "hallucination_rate": _percent(block["llm_judge"].get("hallucination_rate")),
            "perfect_faithfulness_rate": _percent(block["llm_judge"].get("perfect_faithfulness_rate")),
        }
    return out


def write_outputs(out_dir: str, per_example: List[Dict], summary: Dict, regressions: List[Dict], errors: List[Dict]):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "eval_results.json"), "w", encoding="utf-8") as f:
        json.dump(per_example, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "eval_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "eval_regressions.json"), "w", encoding="utf-8") as f:
        json.dump(regressions, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "eval_errors.json"), "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/dataset.jsonl", help="Chemin vers le dataset JSONL")
    parser.add_argument("--mode", default="both", choices=["baseline", "agentic", "both"])
    parser.add_argument("--out-dir", default="eval_outputs")
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--k-values", default="10")
    args = parser.parse_args()

    # Résoudre le chemin relatif depuis la racine du projet
    dataset_path = args.dataset
    if not os.path.isabs(dataset_path):
        # Si le chemin commence par evaluation/, c'est relatif à la racine
        if dataset_path.startswith("evaluation/"):
            dataset_path = os.path.join(ROOT_DIR, dataset_path)
        # Si le chemin commence par backend/evaluation/, corriger vers evaluation/
        elif dataset_path.startswith("backend/evaluation/"):
            dataset_path = os.path.join(ROOT_DIR, dataset_path.replace("backend/evaluation/", "evaluation/"))
        # Sinon, essayer depuis le répertoire evaluation actuel
        elif not os.path.exists(dataset_path):
            eval_dir = Path(__file__).parent
            potential_path = eval_dir / dataset_path
            if potential_path.exists():
                dataset_path = str(potential_path)

    dataset = load_dataset(dataset_path)
    if args.max_items:
        dataset = dataset[: args.max_items]
    example_labels = _example_labels_for_dataset(dataset_path)
    if args.max_items:
        example_labels = example_labels[: args.max_items]
    if len(example_labels) != len(dataset):
        example_labels = [f"Example {i + 1}" for i in range(len(dataset))]
    k_values = [int(v) for v in args.k_values.split(",") if v.strip()]
    if k_values == [10]:
        k_values = [5, 10, 20]

    retrievers = {}
    per_example = []
    start = time.time()

    # Initialiser LLM Judge si activé
    llm_judge = LLMJudge() if settings.EVAL_LLM_JUDGE_ENABLED else None
    if llm_judge:
        print("LLM-as-a-Judge activé pour l'évaluation")

    for ex_idx, example in enumerate(dataset):
        label = example_labels[ex_idx]
        ex_id = example.get("id")
        print(f"[eval] {label}" + (f" — {ex_id}" if ex_id else ""), flush=True)
        file_path = resolve_file_path(example)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fichier introuvable: {file_path}")

        if file_path not in retrievers:
            retrievers[file_path] = build_retriever_for_file(file_path)
        retriever = retrievers[file_path]

        docs = retriever.invoke(example["question"].strip())
        flags = _doc_relevance_flags(docs, example.get("gold_passages", []))
        retrieval_metrics = {}
        for k in k_values:
            retrieval_metrics[f"recall@{k}"] = _recall_at_k(flags, k)
            retrieval_metrics[f"mrr@{k}"] = _mrr_at_k(flags, k)
            retrieval_metrics[f"ndcg@{k}"] = _ndcg_at_k(flags, k)

        modes = ["baseline", "agentic"] if args.mode == "both" else [args.mode]
        for mode in modes:
            if not example.get("expected_answer") and not example.get("answer_keywords"):
                continue
            row = evaluate_example(example, retriever, mode, llm_judge)
            row.update(retrieval_metrics)
            per_example.append(row)

    grouped = {"baseline": [], "agentic": []}
    for row in per_example:
        grouped[row["mode"]].append(row)

    summary = {
        "baseline": aggregate(grouped["baseline"], k_values),
        "agentic": aggregate(grouped["agentic"], k_values),
        "elapsed_sec": round(time.time() - start, 2),
    }

    if summary["baseline"] and summary["agentic"]:
        summary["delta"] = {
            "mean_f1": round(summary["agentic"]["mean_f1"] - summary["baseline"]["mean_f1"], 4),
            "context_hit_rate": round(summary["agentic"]["context_hit_rate"] - summary["baseline"]["context_hit_rate"], 4),
        }

    summary["percent"] = {
        "baseline": _percent_block(summary["baseline"]),
        "agentic": _percent_block(summary["agentic"]),
    }

    regressions = []
    errors = []
    by_id = {}
    for row in per_example:
        if row.get("id") is None:
            continue
        by_id.setdefault(row["id"], {})[row["mode"]] = row

    for ex_id, pair in by_id.items():
        base = pair.get("baseline")
        agent = pair.get("agentic")
        if not base or not agent:
            continue
        if agent["answer_f1"] + 1e-9 < base["answer_f1"]:
            regressions.append({
                "id": ex_id,
                "question": agent["question"],
                "baseline_f1": base["answer_f1"],
                "agentic_f1": agent["answer_f1"],
            })
        if not agent.get("context_hit"):
            errors.append({
                "id": ex_id,
                "question": agent["question"],
                "type": "no_context_hit",
            })
        if agent.get("supported") is False:
            errors.append({
                "id": ex_id,
                "question": agent["question"],
                "type": "not_supported",
            })

    write_outputs(args.out_dir, per_example, summary, regressions, errors)
    log_to_langsmith(
        name="run_eval",
        summary=summary,
        inputs={"dataset": args.dataset, "mode": args.mode},
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
