# Garde-fous de régression sur FinanceBench, à lancer à la main avant de merger un changement
# de prompt, de chunking, de retrieval ou de modèle. Pas en CI : ils appellent les vraies API.
#
#   retrieval  : rejoue le retrieval des 26 questions et compare, question par question, le
#                rang de la page de preuve à une baseline versionnée. Pas de modèle de réponse
#                ni de juge : embeddings, routeur, multi-query et rerank — quelques centimes.
#   sentinels  : ~10 questions que le système réussit aujourd'hui, jugées de bout en bout
#                (verdict ET trajectoire : la page de preuve a-t-elle été vue ?). ~0,10 €.
#
# Usage:
#   uv run python backend/evals/financebench/regression.py retrieval
#   uv run python backend/evals/financebench/regression.py sentinels
#   uv run python backend/evals/financebench/regression.py retrieval --update-baseline
#
# Rien n'est écrit en local à part la baseline versionnée (la référence du garde-fou) :
# le détail des écarts s'affiche dans le terminal.
#
# Code de sortie : 0 si le garde-fou passe, 1 en cas de régression, 2 si le run est invalide
# (un service externe a lâché en silence, ex. quota Cohere : le résultat ne mesure pas le code).

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

HERE = Path(__file__).resolve().parent
GATE_DIR = HERE / "regression"
BASELINE_PATH = GATE_DIR / "retrieval_baseline.json"
SENTINELS_PATH = GATE_DIR / "sentinels.json"

TOP_K = 10  # = RESEARCH_TOP_K : ce que le modèle de réponse voit sans outils
K_VALUES = [5, 10, 20]


def _log(msg: str):
    print(f"[regression] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Comparaisons (pures, testées dans backend/tests/evals/test_regression_gate.py)
# ---------------------------------------------------------------------------

def _in_top(rank: Optional[int], k: int) -> bool:
    return rank is not None and rank <= k


def compare_retrieval(
    baseline: Dict[str, Dict],
    current: Dict[str, Dict],
    k: int = TOP_K,
    max_lost: int = 0,
    max_mean_drop: float = 0.05,
) -> Dict:
    """
    Compare deux runs de retrieval, question par question.

    Une moyenne ne suffit pas : sur 26 questions, perdre la preuve de 2 questions et la
    gagner sur 2 autres laisse page_hit@10 inchangé. Ce qui compte, c'est la liste des
    questions dont la preuve sort du top-k (le modèle ne la voit plus sans outils).
    """
    lost, gained, moved = [], [], []
    for qid, base in baseline.items():
        cur = current.get(qid)
        if cur is None:
            continue
        b_rank, c_rank = base.get("gold_rank"), cur.get("gold_rank")
        if _in_top(b_rank, k) and not _in_top(c_rank, k):
            lost.append({"id": qid, "before": b_rank, "after": c_rank})
        elif _in_top(c_rank, k) and not _in_top(b_rank, k):
            gained.append({"id": qid, "before": b_rank, "after": c_rank})
        elif b_rank != c_rank:
            moved.append({"id": qid, "before": b_rank, "after": c_rank})

    common = [q for q in baseline if q in current]
    missing = [q for q in baseline if q not in current]

    def _mean(rows, key):
        vals = [rows[q].get(key) for q in common if rows[q].get(key) is not None]
        return round(mean(vals), 4) if vals else None

    metrics = {}
    for key in (f"page_hit@{k}", f"page_recall@{k}", f"mrr@{k}"):
        b, c = _mean(baseline, key), _mean(current, key)
        metrics[key] = {"baseline": b, "current": c,
                        "delta": None if b is None or c is None else round(c - b, 4)}

    hit_delta = metrics[f"page_hit@{k}"]["delta"] or 0.0
    reasons = []
    if len(lost) > max_lost:
        reasons.append(f"{len(lost)} question(s) perdent la page de preuve du top-{k} (tolérance {max_lost})")
    if hit_delta < -max_mean_drop:
        reasons.append(f"page_hit@{k} baisse de {-hit_delta * 100:.1f} pts (tolérance {max_mean_drop * 100:.0f})")
    if missing:
        reasons.append(f"{len(missing)} question(s) de la baseline absentes du run")
    return {"ok": not reasons, "reasons": reasons, "lost": lost, "gained": gained,
            "moved": moved, "missing": missing, "metrics": metrics}


def check_sentinel(row: Dict, expect: Dict) -> List[str]:
    """Raisons d'échec d'une question sentinelle (liste vide = elle passe)."""
    if row.get("failed"):
        return [f"échec technique: {row.get('error', '')[:120]}"]
    failures = []
    want = expect.get("verdict", "CORRECT")
    if row.get("verdict") != want:
        failures.append(f"verdict {row.get('verdict')} au lieu de {want}")
    if expect.get("evidence_seen") and not row.get("evidence_seen"):
        failures.append("la page de preuve n'a jamais été montrée au modèle")
    if row.get("tool_calls", 0) < expect.get("min_tool_calls", 0):
        failures.append(f"{row.get('tool_calls', 0)} appel(s) d'outils, {expect['min_tool_calls']} attendu(s) au moins")
    return failures


def per_question(rows: List[Dict], k_values: List[int] = K_VALUES) -> Dict[str, Dict]:
    """Réduit des lignes de résultats aux champs que compare la baseline."""
    keys = ["gold_rank"] + [f"{m}@{k}" for k in k_values for m in ("page_hit", "page_recall", "mrr")]
    out = {}
    for r in rows:
        if r.get("id") and r["id"] not in out:
            out[r["id"]] = {key: r.get(key) for key in keys}
    return out


# ---------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------

class DegradationWatch:
    """
    Enveloppe le retriever et repère les runs où un service a lâché sans lever d'erreur.

    RerankRetriever renvoie les candidats non reclassés quand Cohere échoue (quota, clé,
    panne) : le pipeline continue, mais le retrieval mesuré n'est plus celui du code. Sans
    ce contrôle, un quota épuisé s'affiche comme une régression du code.
    """

    def __init__(self, retriever):
        self._retriever = retriever
        self.unreranked: List[str] = []

    def invoke(self, query: str):
        from backend.config.settings import settings

        docs = self._retriever.invoke(query)
        if settings.RERANK_ENABLED and docs and not any("rerank_score" in (d.metadata or {}) for d in docs):
            self.unreranked.append(query[:80])
        return docs

    def __getattr__(self, name):
        return getattr(self._retriever, name)

    def problems(self, total: int) -> List[str]:
        if not self.unreranked:
            return []
        return [f"rerank Cohere indisponible sur {len(self.unreranked)}/{total} requêtes initiales "
                "(quota, clé ou panne : voir les WARNING « Erreur Cohere Rerank »)"]


def _invalid(problems: List[str]) -> int:
    for p in problems:
        _log(f"RUN INVALIDE — {p}")
    _log("Le résultat ne mesure pas le code : rien n'est comparé ni écrit. Corrigez l'infra et relancez.")
    return 2


def _load_index(dataset: List[Dict]):
    from backend.evals.experiment_utils import eval_index

    docs = sorted({ex["doc_name"] for ex in dataset})
    retriever, page_store = eval_index(docs)  # collections d'éval de Qdrant, écrites par prepare.py
    return DegradationWatch(retriever), page_store, docs


def run_retrieval(dataset: List[Dict], workers: int, page_tolerance: int) -> List[Dict]:
    from concurrent.futures import ThreadPoolExecutor
    import contextvars

    from backend.evals.experiment import compute_retrieval_metrics
    from backend.evals.experiment_utils import call_with_backoff

    retriever, _, docs = _load_index(dataset)
    _log(f"Retrieval sur {len(dataset)} questions ({', '.join(docs)})")

    def one(ex):
        found = call_with_backoff(lambda: retriever.invoke(ex["question"]), f"retrieval {ex['id']}", log=_log)
        return {"id": ex["id"], **compute_retrieval_metrics(found, ex, K_VALUES, page_tolerance)}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        rows = list(pool.map(lambda ex: contextvars.copy_context().run(one, ex), dataset))
    return rows, retriever.problems(len(dataset))


def run_sentinels(dataset: List[Dict], sentinels: List[Dict], workers: int, page_tolerance: int):
    from concurrent.futures import ThreadPoolExecutor
    import contextvars

    from backend.agents.workflow import AgentWorkflow
    from backend.evals.experiment import evaluate_example
    from backend.evals.experiment_utils import FinanceBenchJudge

    by_id = {ex["id"]: ex for ex in dataset}
    unknown = [s["id"] for s in sentinels if s["id"] not in by_id]
    if unknown:
        raise SystemExit(f"Sentinelles absentes du dataset: {', '.join(unknown)}")
    examples = [by_id[s["id"]] for s in sentinels]

    # Même index que l'éval complète (les 4 documents), pas seulement ceux des sentinelles :
    # le routage et les distracteurs doivent être les mêmes.
    retriever, page_store, _ = _load_index(dataset)
    workflow, judge = AgentWorkflow(), FinanceBenchJudge()
    _log(f"{len(examples)} sentinelles, mode agentic + juge")

    def one(ex):
        return evaluate_example(ex, retriever, ["agentic"], workflow, None, judge,
                                K_VALUES, page_tolerance, page_store)[0]

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        rows = list(pool.map(lambda ex: contextvars.copy_context().run(one, ex), examples))
    return rows, retriever.problems(len(examples))


def _fmt_rank(rank):
    return "absente" if rank is None else f"rang {rank}"


def cmd_retrieval(args, dataset) -> int:
    rows, problems = run_retrieval(dataset, args.workers, args.page_tolerance)
    if problems:
        return _invalid(problems)
    source = "run live"
    current = per_question(rows)

    if args.update_baseline:
        GATE_DIR.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(json.dumps({
            "created": date.today().isoformat(),
            "source": source,
            "note": "" if source == "run live" else "Reprise de résultats existants : à régénérer par un run live.",
            "dataset": args.dataset,
            "top_k": TOP_K,
            "questions": current,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        hit = mean(1.0 if _in_top(q["gold_rank"], TOP_K) else 0.0 for q in current.values())
        _log(f"Baseline écrite: {BASELINE_PATH} ({len(current)} questions, page_hit@{TOP_K} = {hit:.1%})")
        return 0

    if not BASELINE_PATH.exists():
        raise SystemExit(f"Pas de baseline ({BASELINE_PATH}). Lancez d'abord avec --update-baseline.")
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    report = compare_retrieval(baseline["questions"], current, TOP_K, args.max_lost, args.max_mean_drop)

    print()
    for key, m in report["metrics"].items():
        delta = "—" if m["delta"] is None else f"{m['delta'] * 100:+.1f} pts"
        print(f"  {key:<16} {m['baseline']!s:>8} -> {m['current']!s:<8} {delta}")
    for label, items in (("PERDUES", report["lost"]), ("gagnées", report["gained"])):
        for it in items:
            print(f"  {label:<8} {it['id']}: {_fmt_rank(it['before'])} -> {_fmt_rank(it['after'])}")
    print()
    if report["ok"]:
        _log(f"OK — retrieval sans régression par rapport à la baseline du {baseline.get('created')}.")
        if report["gained"]:
            _log("Des questions ont été gagnées : pensez à --update-baseline une fois le changement mergé.")
        return 0
    for r in report["reasons"]:
        _log(f"RÉGRESSION — {r}")
    return 1


def cmd_sentinels(args, dataset) -> int:
    sentinels = json.loads(SENTINELS_PATH.read_text(encoding="utf-8"))["sentinels"]
    t0 = time.time()
    rows, problems = run_sentinels(dataset, sentinels, args.workers, args.page_tolerance)
    if problems:
        return _invalid(problems)
    expect = {s["id"]: s for s in sentinels}
    failures = {r["id"]: check_sentinel(r, expect[r["id"]]) for r in rows}
    failures = {k: v for k, v in failures.items() if v}

    print()
    for r in rows:
        mark = "ÉCHEC" if r["id"] in failures else "ok"
        print(f"  {mark:<5} {r['id']} ({r.get('doc_name')}) — {expect[r['id']].get('why', '')}")
        for reason in failures.get(r["id"], []):
            print(f"        -> {reason}")
    print()
    _log(f"{len(rows) - len(failures)}/{len(rows)} sentinelles passent ({time.time() - t0:.0f}s).")
    if len(failures) > args.max_failures:
        _log(f"RÉGRESSION — {len(failures)} échec(s), tolérance {args.max_failures}.")
        return 1
    if failures:
        _log(f"Toléré ({len(failures)} ≤ {args.max_failures}) : relancez la question en échec pour "
             "distinguer une régression du non-déterminisme résiduel du modèle.")
    return 0


def main():
    from backend.evals.financebench.langsmith_sync import DEFAULT_DATASET

    parser = argparse.ArgumentParser(description="Garde-fous de régression FinanceBench")
    parser.add_argument("gate", choices=["retrieval", "sentinels"])
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="dataset LangSmith")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--page-tolerance", type=int, default=1)
    parser.add_argument("--update-baseline", action="store_true",
                        help="retrieval : remplace la baseline par ce run au lieu de comparer")
    parser.add_argument("--max-lost", type=int, default=0,
                        help="retrieval : questions tolérées dont la preuve sort du top-10")
    parser.add_argument("--max-mean-drop", type=float, default=0.05,
                        help="retrieval : baisse tolérée de page_hit@10 (0.05 = 5 points)")
    parser.add_argument("--max-failures", type=int, default=1,
                        help="sentinels : échecs tolérés (le modèle n'est pas strictement déterministe)")
    args = parser.parse_args()

    from backend.evals.financebench.langsmith_sync import get_client, load_rows
    dataset = load_rows(get_client(), args.dataset)  # questions lues dans LangSmith
    code = cmd_retrieval(args, dataset) if args.gate == "retrieval" else cmd_sentinels(args, dataset)
    sys.exit(code)


if __name__ == "__main__":
    main()
