"""
Intervalle de confiance (Wilson, 95 %) sur une proportion — pour ne plus annoncer
"~71-76 %" sur 21 questions sans dire l'incertitude qui va avec.

Sur 21 questions, l'IC95 fait ~35 points de large : une différence d'une ou deux
questions entre deux configurations n'est pas un résultat.

Usage :
    uv run python evaluation/financebench/confidence.py 15 21
    uv run python evaluation/financebench/confidence.py --summary evaluation/financebench/outputs/financebench_summary.json
"""
import argparse
import json
import math
from pathlib import Path
from typing import Tuple


def wilson(successes: int, n: int, z: float = 1.96) -> Tuple[float, float, float]:
    """Retourne (proportion, borne basse, borne haute)."""
    if n == 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def fmt(label: str, k: int, n: int) -> str:
    p, lo, hi = wilson(k, n)
    return f"{label:<16} {k:>3}/{n:<3} = {p:6.1%}   IC95 % [{lo:5.1%} ; {hi:5.1%}]"


# Les métriques du résumé sont des taux ; le protocole FinanceBench raisonne en
# nombre de questions. On remonte au comptage, seule base d'un intervalle exact.
_RATES = [("correct", "accuracy"), ("hallucination", "hallucination_rate"), ("refusal", "refusal_rate")]


def from_summary(path: Path) -> None:
    summary = json.loads(path.read_text())
    for mode in ("baseline", "agentic"):
        block = (summary.get(mode) or {}).get("financebench") or {}
        n = block.get("count") or 0
        if not n:
            print(f"\n[{mode}] aucun verdict dans le résumé")
            continue
        print(f"\n[{mode}] n = {n} questions jugées")
        for label, key in _RATES:
            rate = block.get(key)
            if rate is not None:
                print("  " + fmt(label, round(rate * n), n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("successes", nargs="?", type=int)
    ap.add_argument("n", nargs="?", type=int)
    ap.add_argument("--summary", type=Path, help="financebench_summary.json : IC par mode")
    args = ap.parse_args()

    if args.summary:
        from_summary(args.summary)
        return

    if args.successes is None or args.n is None:
        ap.error("donner <successes> <n> ou --summary")
    print(fmt("accuracy", args.successes, args.n))


if __name__ == "__main__":
    main()
