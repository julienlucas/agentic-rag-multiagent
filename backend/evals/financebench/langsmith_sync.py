"""
FinanceBench sur LangSmith : le dataset et les résultats n'existent que là.

- Le dataset (question, réponse de référence, document, type, pages et passages de preuve,
  mots-clés) est un dataset LangSmith, seule source des questions : prepare.py l'écrit
  (upsert_dataset), les expériences le lisent (load_rows). Clé : l'identifiant FinanceBench.
- Chaque run devient une expérience par mode (baseline / agentic) rattachée à ce dataset :
  une ligne par question, avec la réponse générée et ses scores en feedback (verdict du juge,
  F1, faithfulness, recall@10...). Les expériences successives se comparent côte à côte
  dans l'onglet « Experiments » du dataset.

Appelé à la fin de backend/evals/experiment.py : c'est le seul endroit où les résultats sont
conservés (aucune sortie locale).
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config.settings import settings  # noqa: E402  (charge aussi le .env)

# Datasets préfixés par le projet LangSmith : le workspace est partagé avec d'autres projets.
DATASET_PREFIX = "agentic-rag · "
DEFAULT_DATASET = DATASET_PREFIX + "FinanceBench"  # le protocole publié : 26 questions sur 4 rapports
DESCRIPTION = "FinanceBench (Patronus AI) : questions sur des rapports 10-K, réponses et preuves de référence."

# Champs d'une question rangés en métadonnées de l'exemple (en plus de financebench_id).
_METADATA = ("company", "doc_name", "question_type", "question_reasoning",
             "gold_pages", "gold_passages", "answer_keywords")
_LISTS = ("gold_pages", "gold_passages", "answer_keywords")
_TYPE_ORDER = {"metrics-generated": 0, "domain-relevant": 1, "novel-generated": 2}


# Scores numériques d'une ligne de résultats, envoyés comme feedback LangSmith.
NUMERIC_FEEDBACK = [
    "answer_f1", "judge_faithfulness", "answer_relevancy", "tool_calls",
    "recall@5", "recall@10", "mrr@10", "ndcg@10", "page_hit@5", "page_hit@10", "page_recall@10",
]


def get_client():
    if not os.getenv("LANGSMITH_API_KEY"):
        print("⚠️  LANGSMITH_API_KEY non défini : rien n'est envoyé à LangSmith")
        return None
    from langsmith import Client
    return Client()


def sort_rows(rows: List[Dict]) -> List[Dict]:
    """Ordre stable des questions (type, document, id) : --max-items prend toujours les mêmes."""
    return sorted(rows, key=lambda r: (_TYPE_ORDER.get(r.get("question_type"), 9), r["doc_name"], r["id"]))


def example_from_row(row: Dict) -> Dict:
    """Question du projet → exemple LangSmith (inputs / outputs / metadata)."""
    return {
        "inputs": {"question": row["question"], "doc_name": row["doc_name"]},
        "outputs": {"answer": row.get("expected_answer", ""), "justification": row.get("justification", "")},
        "metadata": {"financebench_id": row["id"], **{k: row.get(k) for k in _METADATA}},
    }


def row_from_example(inputs: Dict, outputs: Optional[Dict], metadata: Optional[Dict]) -> Dict:
    """Exemple LangSmith → question au format attendu par les expériences."""
    md, outputs = metadata or {}, outputs or {}
    row = {
        "id": md["financebench_id"], "question": inputs["question"], "doc_name": inputs["doc_name"],
        "expected_answer": outputs.get("answer", ""), "justification": outputs.get("justification", ""),
    }
    for key in _METADATA:
        if key != "doc_name":
            row[key] = md.get(key) if md.get(key) is not None else ([] if key in _LISTS else None)
    return row


def upsert_dataset(client, name: str, rows: List[Dict], prune: bool = False,
                   corpus: Optional[List[str]] = None):
    """
    Crée le dataset si besoin, ajoute les questions absentes, met à jour celles qui ont changé.
    `prune` : retire aussi les questions du dataset absentes de `rows` (questions écartées).
    `corpus` : les documents indexés pour ce dataset, gardés dans ses métadonnées (voir load_corpus).
    """
    dataset = (client.read_dataset(dataset_name=name) if client.has_dataset(dataset_name=name)
               else client.create_dataset(name, description=DESCRIPTION))
    if corpus is not None and (dataset.metadata or {}).get("corpus") != sorted(corpus):
        # Le SDK n'a pas d'update_dataset : route PATCH de l'API.
        client.request_with_retries("PATCH", f"/datasets/{dataset.id}",
                                    json={"metadata": {**(dataset.metadata or {}), "corpus": sorted(corpus)}})
    known = {(ex.metadata or {}).get("financebench_id"): ex for ex in client.list_examples(dataset_id=dataset.id)}
    new, updated = [], 0
    for row in rows:
        ex = example_from_row(row)
        old = known.get(row["id"])
        if old is None:
            new.append(ex)
        elif (old.inputs, old.outputs, old.metadata) != (ex["inputs"], ex["outputs"], ex["metadata"]):
            client.update_example(old.id, inputs=ex["inputs"], outputs=ex["outputs"], metadata=ex["metadata"])
            updated += 1
    if new:
        client.create_examples(dataset_id=dataset.id, inputs=[e["inputs"] for e in new],
                               outputs=[e["outputs"] for e in new], metadata=[e["metadata"] for e in new])
    wanted = {row["id"] for row in rows}
    stale = [ex.id for fid, ex in known.items() if fid not in wanted] if prune else []
    if stale:
        client.delete_examples(stale)
    print(f"✓ Dataset LangSmith « {name} » : {len(new)} question(s) ajoutée(s), {updated} mise(s) à jour"
          + (f", {len(stale)} retirée(s)" if stale else ""))
    return dataset


def load_corpus(client, name: str, rows: List[Dict]) -> List[str]:
    """
    Documents de l'index d'un dataset. Ce sont ceux enregistrés par prepare.py ; à défaut, ceux de
    ses questions. Ils peuvent différer : un document dont toutes les questions ont été retirées
    reste indexé, comme distracteur, et l'espace Qdrant est calculé sur la liste complète.
    """
    corpus = (client.read_dataset(dataset_name=name).metadata or {}).get("corpus")
    return sorted(corpus) if corpus else sorted({row["doc_name"] for row in rows})


def load_rows(client, name: str = DEFAULT_DATASET) -> List[Dict]:
    """Les questions d'un dataset LangSmith, dans l'ordre stable."""
    if not client.has_dataset(dataset_name=name):
        raise SystemExit(f"Dataset LangSmith « {name} » absent : lancer d'abord backend/evals/financebench/prepare.py")
    return sort_rows([row_from_example(ex.inputs, ex.outputs, ex.metadata)
                      for ex in client.list_examples(dataset_name=name)])


def _feedback(row: Dict) -> List[tuple]:
    out = []
    verdict = row.get("verdict")
    if verdict and verdict != "ERROR":
        out.append(("correct", 1.0 if verdict == "CORRECT" else 0.0, f"{verdict} — {row.get('judge_reason', '')}"))
    for key in NUMERIC_FEEDBACK:
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out.append((key, float(value), None))
    if isinstance(row.get("evidence_seen"), bool):
        out.append(("evidence_seen", 1.0 if row["evidence_seen"] else 0.0, None))
    return out


def log_experiments(client, dataset_name: str, summary: Dict, results: List[Dict],
                    name: Optional[str] = None) -> List[str]:
    """Une expérience LangSmith par mode, une ligne par question et par répétition (les
    répétitions d'une question se rattachent au même exemple). Retourne les noms des expériences."""
    dataset = client.read_dataset(dataset_name=dataset_name)
    example_ids = {(ex.metadata or {}).get("financebench_id"): ex.id
                   for ex in client.list_examples(dataset_id=dataset.id)}
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    name = name or settings.REASONING_MODEL_ID
    experiments = []

    for mode in sorted({r["mode"] for r in results}):
        rows = [r for r in results if r["mode"] == mode and r.get("id") in example_ids]
        fb = (summary.get(mode) or {}).get("financebench") or {}
        project = client.create_project(
            f"{name} · {mode} · {stamp}",
            reference_dataset_id=dataset.id,
            metadata={
                "mode": mode,
                "reasoning_model": name,
                "small_model": settings.MODEL_SMALL_ID,
                "embeddings": settings.EMBEDDING_MODEL_ID,
                "reranker": settings.RERANK_MODEL,
                "index": summary.get("index"),
                "source": summary.get("source"),
                "documents": summary.get("documents"),
                "accuracy": fb.get("accuracy"),
                "reps": summary.get("reps", 1),
                "pass_all_rate": ((summary.get(mode) or {}).get("repetitions") or {}).get("pass_all_rate"),
                "verdict_stability": ((summary.get(mode) or {}).get("repetitions") or {}).get("verdict_stability"),
                "cost_usd": (summary.get("cost") or {}).get("total_usd"),
            },
        )
        run_ids = []
        end = datetime.now(timezone.utc)
        for row in rows:
            run_id = uuid.uuid4()
            duration = float(row.get("retrieval_sec") or 0) + float(row.get("generation_sec") or 0)
            client.create_run(
                id=run_id,
                name="financebench",
                run_type="chain",
                inputs={"question": row["question"], "doc_name": row["doc_name"]},
                outputs={"answer": row.get("answer", "")},
                reference_example_id=example_ids[row["id"]],
                project_name=project.name,
                start_time=end - timedelta(seconds=duration),
                end_time=end,
                extra={"metadata": {
                    "mode": mode, "rep": row.get("rep", 0), "verdict": row.get("verdict"), "error": row.get("error"),
                    "question_type": row.get("question_type"),
                    "pages_read": row.get("pages_read"), "tool_queries": row.get("corrective_queries"),
                    "gold_rank": row.get("gold_rank"),
                }},
            )
            run_ids.append((run_id, row))
        client.flush()  # les runs doivent exister avant leurs feedbacks
        for run_id, row in run_ids:
            for key, score, comment in _feedback(row):
                # session_id : sans lui, LangSmith n'attachait pas tous les verdicts à l'expérience.
                client.create_feedback(run_id, key=key, score=score, comment=comment,
                                       trace_id=run_id, session_id=project.id)
        # Les feedbacks partent en arrière-plan : sans flush, le script se terminait avant leur
        # envoi (run du 11 oct. 2026 : 48 verdicts sur 65 dans LangSmith).
        client.flush()
        client.update_project(project.id, end_time=datetime.now(timezone.utc))
        experiments.append(project.name)
        acc = fb.get("accuracy")
        print(f"✓ Expérience LangSmith « {project.name} » : {len(rows)} questions"
              + (f", exactitude {acc:.1%}" if isinstance(acc, (int, float)) else ""))
    return experiments


def push_eval(dataset_name: str, summary: Dict, results: List[Dict], name: Optional[str] = None) -> List[str]:
    """Point d'entrée du runner : n'échoue jamais (un incident LangSmith ne doit pas faire perdre un run)."""
    client = get_client()
    if client is None:
        return []
    try:
        return log_experiments(client, dataset_name, summary, results, name)
    except Exception as e:
        print(f"⚠️  Envoi LangSmith impossible : {type(e).__name__}: {e}")
        return []
