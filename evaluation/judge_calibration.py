"""Calibration des juges en ligne contre les votes des utilisateurs (👍/👎).

Un verdict de juge ne vaut que s'il concorde avec un humain. Les votes et les verdicts des
juges en ligne (evaluation/online_evaluators.py) sont des feedbacks sur le même run racine
« question » : ce script les met en face et mesure leur accord. Lecture seule, aucun appel
de modèle.

    uv run python evaluation/judge_calibration.py              # 30 derniers jours
    uv run python evaluation/judge_calibration.py --days 90

Lecture : un 👎 ne dit pas pourquoi la réponse déplaît (fausse, hors sujet, incomplète…),
c'est un signal approché. Un juge qui valide la plupart des réponses notées 👎 (TNR bas)
est trop indulgent : c'est son prompt qu'il faut retravailler. Kappa de Cohen ≥ 0,6 :
juge utilisable pour piloter ; en dessous, à retravailler.
"""
import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config.settings import settings  # noqa: E402  (charge aussi le .env)
from backend.feedback import FEEDBACK_KEY, TRACE_PROJECT  # noqa: E402

# Juges en ligne notant le run racine « question » (clés de feedback des règles)
JUDGE_KEYS = ("faithfulness", "answer_relevance")
MIN_KAPPA = 0.6


def agreement(pairs: List[Tuple[bool, bool]]) -> Dict[str, Optional[float]]:
    """Accord entre verdicts (humain, juge) : taux d'accord, TPR, TNR, kappa de Cohen."""
    n = len(pairs)
    if not n:
        return {"n": 0, "agreement": None, "tpr": None, "tnr": None, "kappa": None}
    both_pass = sum(1 for h, j in pairs if h and j)
    both_fail = sum(1 for h, j in pairs if not h and not j)
    human_pass = sum(1 for h, _ in pairs if h)
    judge_pass = sum(1 for _, j in pairs if j)
    observed = (both_pass + both_fail) / n
    expected = (human_pass * judge_pass + (n - human_pass) * (n - judge_pass)) / (n * n)
    return {
        "n": n,
        "agreement": observed,
        # Le juge valide-t-il ce que l'humain approuve… et rejette-t-il ce qu'il rejette ?
        "tpr": both_pass / human_pass if human_pass else None,
        "tnr": both_fail / (n - human_pass) if n - human_pass else None,
        "kappa": None if expected == 1 else (observed - expected) / (1 - expected),
    }


def pairs_by_judge(feedback: List) -> Dict[str, List[Tuple[bool, bool]]]:
    """Feedbacks LangSmith → {juge: [(vote humain, verdict du juge)]}, run par run."""
    by_run: Dict[str, Dict[str, float]] = defaultdict(dict)
    for fb in feedback:
        if fb.score is not None:
            by_run[str(fb.run_id)][fb.key] = fb.score
    pairs: Dict[str, List[Tuple[bool, bool]]] = defaultdict(list)
    for scores in by_run.values():
        if FEEDBACK_KEY not in scores:
            continue
        for key in JUDGE_KEYS:
            if key in scores:
                pairs[key].append((scores[FEEDBACK_KEY] >= 0.5, scores[key] >= 0.5))
    return pairs


def report(days: int) -> int:
    if not settings.LANGSMITH_API_KEY:
        print("✗ LANGSMITH_API_KEY absente.", file=sys.stderr)
        return 1
    from langsmith import Client
    client = Client(api_key=settings.LANGSMITH_API_KEY)
    voted = list(client.list_runs(
        project_name=TRACE_PROJECT, is_root=True,
        start_time=datetime.now(timezone.utc) - timedelta(days=days),
        filter=f'eq(feedback_key, "{FEEDBACK_KEY}")',
    ))
    if not voted:
        print(f"Aucune réponse votée sur {days} jour(s).")
        return 0
    feedback = list(client.list_feedback(run_ids=[r.id for r in voted],
                                         feedback_key=[FEEDBACK_KEY, *JUDGE_KEYS]))
    pairs = pairs_by_judge(feedback)

    def fmt(value):
        return "  -  " if value is None else f"{value:.2f}"

    print(f"{len(voted)} réponse(s) votée(s) sur {days} jour(s)\n")
    print(f"{'juge':<18} {'n':>3}  accord   TPR    TNR   kappa  verdict")
    for key in JUDGE_KEYS:
        stats = agreement(pairs.get(key, []))
        usable = stats["kappa"] is not None and stats["kappa"] >= MIN_KAPPA
        verdict = "utilisable" if usable else ("à retravailler" if stats["n"] else "-")
        print(f"{key:<18} {stats['n']:>3}  {fmt(stats['agreement']):>6} {fmt(stats['tpr']):>6} "
              f"{fmt(stats['tnr']):>6} {fmt(stats['kappa']):>6}  {verdict}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Accord juges en ligne / votes des utilisateurs")
    parser.add_argument("--days", type=int, default=30)
    return report(parser.parse_args().days)


if __name__ == "__main__":
    sys.exit(main())
