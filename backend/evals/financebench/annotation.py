# Calibrer le juge FinanceBench sur une annotation humaine.
#
# Le choix du juge pèse lourd : sur les mêmes 65 réponses, Pixtral Large donne 83 %, gpt-oss-120b
# et Qwen3 235B 70 %. Un juge se choisit donc sur son accord avec un humain, pas sur son score.
#
#   queue      : fait juger les réponses d'une expérience par les juges candidats, puis crée une
#                file d'annotation LangSmith, à l'aveugle (aucun verdict affiché), en mettant en
#                tête les réponses où les juges divergent ;
#   agreement  : après annotation (clé « human_correct »), accord de chaque juge avec l'humain ;
#   examples   : exporte les annotations dans judge_examples.json, que le juge reçoit comme
#                exemples. Chaque question est jugée sans son propre exemple : l'accord mesuré
#                ensuite ne recopie pas l'annotation.
#
# Les extraits de contexte ne sont pas conservés dans LangSmith : les juges ne voient que la
# question, la référence et la réponse. Seul le verdict est comparé, pas la faithfulness.
#
# Usage:
#   uv run python backend/evals/financebench/annotation.py queue --experiment "<nom>" --size 30
#   uv run python backend/evals/financebench/annotation.py agreement --project "<projet d'annotation>"
#   uv run python backend/evals/financebench/annotation.py examples --project "<projet d'annotation>"

import argparse
import random
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config.settings import settings  # noqa: E402
from backend.evals.experiment_utils import FinanceBenchJudge, call_with_backoff  # noqa: E402
from backend.evals.financebench.langsmith_sync import get_client, load_rows  # noqa: E402

HUMAN_KEY = "human_correct"

# Juges candidats : (nom court, identifiant Bedrock, région). Tous hors famille Claude.
CANDIDATES = [
    ("qwen3-235b", "qwen.qwen3-235b-a22b-2507-v1:0", "eu-central-1"),
    ("gpt-oss-120b", "openai.gpt-oss-120b-1:0", "eu-central-1"),
    ("pixtral-large", "eu.mistral.pixtral-large-2502-v1:0", None),
]

NO_CONTEXT = "(extraits non conservés : juger le verdict seulement)"

RUBRIC = """Pour chaque réponse, décidez si elle répond correctement à la question, au vu de la
réponse de référence de FinanceBench et du document (lien vers la page de preuve).
- 1 = correcte : même information que la référence, ou équivalente (autres mots, autre
  granularité, arrondi), sans la contredire ;
- 0 = incorrecte : autre chiffre, autre élément, conclusion inverse, ou refus alors que
  l'information existe.
Si la référence vous semble fausse, notez la réponse sur le fond et dites-le en commentaire."""


def _log(msg: str):
    print(f"[annotation] {msg}", flush=True)


def _judges() -> Dict[str, FinanceBenchJudge]:
    from backend.llm.bedrock import chat_model
    return {name: FinanceBenchJudge(llm=chat_model(model, max_tokens=2000, region=region), model=model)
            for name, model, region in CANDIDATES}


def _verdicts(judges: Dict[str, FinanceBenchJudge], items: List[Dict]) -> Dict[str, Dict[str, bool]]:
    """{financebench_id: {juge: correct ?}} — deux appels à la fois, reprises sur throttling."""
    def judge_one(args):
        name, judge, item = args
        v = call_with_backoff(
            lambda: judge.evaluate(question=item["question"], expected_answer=item["expected_answer"],
                                   justification=item.get("justification", ""),
                                   generated_answer=item["answer"], context=NO_CONTEXT),
            f"juge {name}", attempts=8, base_delay=10.0, log=lambda m: None,
        )
        return item["id"], name, v.verdict == "CORRECT"

    out: Dict[str, Dict[str, bool]] = {}
    tasks = [(name, judge, item) for name, judge in judges.items() for item in items]
    with ThreadPoolExecutor(2) as pool:
        for fid, name, ok in pool.map(judge_one, tasks):
            out.setdefault(fid, {})[name] = ok
    return out


def _experiment_answers(client, experiment: str, dataset: str) -> List[Dict]:
    """Réponses d'une expérience, jointes à leur question de référence dans le dataset."""
    rows = {r["id"]: r for r in load_rows(client, dataset)}
    items = []
    for run in client.list_runs(project_name=experiment, is_root=True):
        ex = client.read_example(run.reference_example_id)
        fid = (ex.metadata or {}).get("financebench_id")
        if fid in rows:
            items.append({**rows[fid], "answer": (run.outputs or {}).get("answer", "")})
    return items


def add_to_queue(client, queue_id, run_ids, attempts: int = 12, delay: float = 5.0):
    """
    Ajoute les runs à la file. LangSmith ingère les runs en différé : ajoutés aussitôt créés,
    ils donnaient un 404. On attend qu'ils soient lisibles, avec des reprises.
    """
    import time
    for attempt in range(attempts):
        try:
            for run_id in run_ids:
                client.read_run(run_id)
            client.add_runs_to_annotation_queue(queue_id, run_ids=run_ids)
            return
        except Exception as e:
            if attempt == attempts - 1:
                raise
            _log(f"runs pas encore disponibles ({type(e).__name__}), nouvel essai dans {delay:.0f}s")
            time.sleep(delay)


def queue(experiment: str, dataset: str, size: int, seed: int = 0, only_divergent: bool = False):
    client = get_client()
    items = _experiment_answers(client, experiment, dataset)
    _log(f"{len(items)} réponses dans « {experiment} » ; jugement par {len(CANDIDATES)} juges…")
    verdicts = _verdicts(_judges(), items)

    split = [i for i in items if len(set(verdicts[i["id"]].values())) > 1]
    agreed = [i for i in items if i not in split]
    random.Random(seed).shuffle(agreed)  # complète l'échantillon : réponses jugées justes et fausses
    chosen = split if only_divergent else (split + agreed)[:size]
    _log(f"{len(split)} réponses où les juges divergent ; {len(chosen)} retenues pour l'annotation")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    project = client.create_project(
        f"FinanceBench · annotation · {stamp}",
        metadata={"experiment": experiment, "dataset": dataset, "kind": "annotation"},
    )
    now = datetime.now(timezone.utc)
    run_ids = []
    for item in chosen:
        run_id = uuid.uuid4()
        pages = ", ".join(f"{d} p. {p + 1}" for d, p in item.get("gold_pages", []))
        client.create_run(
            id=run_id, name="financebench · à annoter", run_type="chain", project_name=project.name,
            inputs={"question": item["question"], "reference_answer": item["expected_answer"],
                    "justification": item.get("justification", ""), "document": item["doc_name"],
                    "evidence_pages": pages},
            outputs={"answer": item["answer"]},
            start_time=now, end_time=now,
            extra={"metadata": {"financebench_id": item["id"], "experiment": experiment}},
        )
        run_ids.append(run_id)
    client.flush()

    # Le critère doit exister comme feedback config, sinon il n'apparaît pas dans la file.
    from langsmith.schemas import AnnotationQueueRubricItem, FeedbackConfig
    if not any(f.feedback_key == HUMAN_KEY for f in client.list_feedback_configs()):
        client.create_feedback_config(HUMAN_KEY, feedback_config=FeedbackConfig(
            type="categorical", categories=[{"value": 1, "label": "correcte"}, {"value": 0, "label": "incorrecte"}]))
    rubric = [AnnotationQueueRubricItem(
        feedback_key=HUMAN_KEY, description="La réponse est-elle correcte (protocole FinanceBench) ?",
        value_descriptions={"1": "correcte", "0": "incorrecte"}, is_required=True)]
    q = client.create_annotation_queue(name=f"FinanceBench · juge · {stamp}", description=RUBRIC,
                                       rubric_instructions=RUBRIC, rubric_items=rubric)
    add_to_queue(client, q.id, run_ids)
    _log(f"File d'annotation « {q.name} » : {len(run_ids)} réponses (les divergentes d'abord)")
    _log(f"Projet d'annotation : « {project.name} »")
    _log(f'Ensuite : annotation.py agreement --project "{project.name}"')


def agreement(project: str):
    client = get_client()
    runs = list(client.list_runs(project_name=project, is_root=True))
    human = {}
    for f in client.list_feedback(run_ids=[r.id for r in runs], feedback_key=[HUMAN_KEY]):
        human[f.run_id] = (f.score == 1, f.comment or "")
    items = []
    for r in runs:
        if r.id not in human:
            continue
        inp = r.inputs or {}
        items.append({"id": (r.extra or {}).get("metadata", {}).get("financebench_id") or str(r.id),
                      "question": inp.get("question", ""), "expected_answer": inp.get("reference_answer", ""),
                      "justification": inp.get("justification", ""),
                      "answer": (r.outputs or {}).get("answer", ""), "human": human[r.id]})
    if not items:
        raise SystemExit(f"Aucune annotation « {HUMAN_KEY} » dans « {project} ».")
    _log(f"{len(items)} réponses annotées ; jugement par {len(CANDIDATES)} juges…")
    verdicts = _verdicts(_judges(), items)

    _log(f"Accord avec l'humain (juge actuel : {settings.EVAL_JUDGE_MODEL_ID})")
    for name, _, _ in CANDIDATES:
        agree = sum(verdicts[i["id"]][name] == i["human"][0] for i in items)
        lenient = sum(verdicts[i["id"]][name] and not i["human"][0] for i in items)
        strict = sum(not verdicts[i["id"]][name] and i["human"][0] for i in items)
        _log(f"  {name:14s} {agree}/{len(items)} = {agree / len(items):.0%}  "
             f"(trop indulgent : {lenient}, trop sévère : {strict})")
    _log("Désaccords (humain ≠ juge actuel) :")
    current = next(n for n, m, _ in CANDIDATES if m == settings.EVAL_JUDGE_MODEL_ID)
    for i in items:
        if verdicts[i["id"]][current] != i["human"][0]:
            _log(f"  {i['id']} humain={'correct' if i['human'][0] else 'incorrect'} — {i['human'][1][:120]}")


def export_examples(project: str, max_answer_chars: int = 700):
    """
    Écrit les réponses annotées dans JUDGE_EXAMPLES_PATH : le juge les reçoit comme exemples
    (few-shot). Toutes, correctes et incorrectes, pour qu'il apprenne le seuil et pas seulement
    l'indulgence. Le juge écarte l'exemple de la question qu'il note (voir FinanceBenchJudge).
    """
    import json
    from backend.evals.experiment_utils import JUDGE_EXAMPLES_PATH
    client = get_client()
    runs = list(client.list_runs(project_name=project, is_root=True))
    human = {f.run_id: f for f in client.list_feedback(run_ids=[r.id for r in runs], feedback_key=[HUMAN_KEY])}
    examples = []
    for r in runs:
        f = human.get(r.id)
        if f is None:
            continue
        inp, answer = r.inputs or {}, (r.outputs or {}).get("answer", "")
        examples.append({
            "id": (r.extra or {}).get("metadata", {}).get("financebench_id") or str(r.id),
            "question": inp.get("question", ""),
            "reference": inp.get("reference_answer", ""),
            "answer": answer if len(answer) <= max_answer_chars else answer[:max_answer_chars] + " […]",
            "verdict": "CORRECT" if f.score == 1 else "INCORRECT",
            "comment": f.comment or "",
        })
    if not examples:
        raise SystemExit(f"Aucune annotation « {HUMAN_KEY} » dans « {project} ».")
    examples.sort(key=lambda e: e["id"])
    JUDGE_EXAMPLES_PATH.write_text(json.dumps(examples, ensure_ascii=False, indent=1) + "\n")
    n_ok = sum(e["verdict"] == "CORRECT" for e in examples)
    _log(f"{len(examples)} exemples ({n_ok} corrects, {len(examples) - n_ok} incorrects) → {JUDGE_EXAMPLES_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Calibrer le juge FinanceBench sur annotation humaine")
    sub = parser.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("queue", help="Crée la file d'annotation LangSmith")
    q.add_argument("--experiment", required=True, help="Expérience LangSmith (mode agentic) à annoter")
    q.add_argument("--dataset", default="agentic-rag · FinanceBench (pilot 20)")
    q.add_argument("--size", type=int, default=30)
    q.add_argument("--only-divergent", action="store_true",
                   help="Seulement les réponses où les juges ne sont pas d'accord (annotation courte)")
    a = sub.add_parser("agreement", help="Accord de chaque juge avec l'annotation humaine")
    a.add_argument("--project", required=True, help="Projet d'annotation créé par « queue »")
    e = sub.add_parser("examples", help="Exporte les annotations comme exemples du juge (few-shot)")
    e.add_argument("--project", required=True, help="Projet d'annotation créé par « queue »")
    args = parser.parse_args()
    if args.cmd == "queue":
        queue(args.experiment, args.dataset, args.size, only_divergent=args.only_divergent)
    elif args.cmd == "examples":
        export_examples(args.project)
    else:
        agreement(args.project)


if __name__ == "__main__":
    main()
