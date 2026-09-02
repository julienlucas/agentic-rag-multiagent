import math

from evaluation.run_eval import aggregate, _f1_score, _mrr_at_k, _ndcg_at_k, _recall_at_k


def test_recall_at_k():
    assert _recall_at_k([0, 1, 0, 1], 2) == 0.5
    assert _recall_at_k([1, 1, 0], 3) == 1.0
    assert _recall_at_k([0, 0, 0], 3) == 0.0
    assert _recall_at_k([], 3) is None


def test_mrr_at_k():
    assert _mrr_at_k([1, 0, 0], 3) == 1.0
    assert _mrr_at_k([0, 1, 0], 3) == 0.5
    assert _mrr_at_k([0, 0, 1], 2) == 0.0  # hors fenêtre k


def test_ndcg_at_k():
    assert _ndcg_at_k([1, 0, 0], 3) == 1.0
    assert math.isclose(_ndcg_at_k([0, 1, 0], 3), 1 / math.log2(3), rel_tol=1e-9)
    assert _ndcg_at_k([0, 0, 0], 3) == 0.0


def test_token_f1():
    assert _f1_score("Revenue was 10", "revenue was 10") == 1.0
    assert _f1_score("alpha beta", "gamma delta") == 0.0
    assert math.isclose(_f1_score("the revenue was 10", "revenue 10"), 2 / 3, rel_tol=1e-9)


# --- Agrégation du harness interne ------------------------------------------------


def _row(mode="agentic", **kw):
    base = {
        "mode": mode, "answer_f1": 1.0, "context_hit": True,
        "supported": None, "relevant": True,
        "generation_sec": 1.0, "retrieval_sec": 0.1,
    }
    base.update(kw)
    return base


def test_failed_rows_leave_the_denominator_but_stay_counted():
    """Un run amputé de questions ne doit pas se lire comme un run complet."""
    out = aggregate([_row(), _row(), _row(failed=True, rate_limited=True)], [10])
    assert out["count"] == 2
    assert out["failed"] == 1
    assert out["attempted"] == 3
    assert out["rate_limited"] == 1


def test_all_failed_does_not_crash_and_reports_nothing():
    out = aggregate([_row(failed=True), _row(failed=True)], [10])
    assert out["count"] == 0
    assert "mean_f1" not in out


def test_verdicts_produce_counts_and_confidence_interval():
    """Le taux seul est trompeur sur un petit échantillon : comptage et IC95 obligatoires."""
    rows = [_row(verdict="CORRECT", judge_faithfulness=5.0) for _ in range(3)]
    rows.append(_row(verdict="INCORRECT", judge_faithfulness=2.0))
    fb = aggregate(rows, [10])["financebench"]
    assert fb["counts"] == {"correct": 3, "refusal": 0, "hallucination": 1}
    assert fb["accuracy"] == 0.75
    lo, hi = fb["accuracy_ci95"]
    assert lo < 0.75 < hi
    # 4 questions : l'intervalle doit être franchement large, pas décoratif.
    assert hi - lo > 0.5


def test_dead_verification_signal_reports_null_not_zero():
    """bool(None is False) valait False : le résumé annonçait « 0 % d'hallucinations »
    alors que le VerificationAgent qui produisait ce signal a été retiré."""
    out = aggregate([_row(hallucinated=None), _row(hallucinated=None)], [10])
    assert out["hallucination_rate"] is None
    assert out["supported_rate"] is None
