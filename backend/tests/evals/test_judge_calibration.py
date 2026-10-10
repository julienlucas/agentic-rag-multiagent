"""Calibration des juges en ligne : accord avec les votes, sans appel réseau."""
from types import SimpleNamespace

from backend.evals.judge_calibration import agreement, pairs_by_judge


def _fb(run, key, score):
    return SimpleNamespace(run_id=run, key=key, score=score)


def test_perfect_agreement():
    stats = agreement([(True, True), (False, False)])
    assert stats["agreement"] == 1.0 and stats["kappa"] == 1.0


def test_judge_that_always_passes_has_zero_kappa_and_zero_tnr():
    stats = agreement([(True, True), (False, True), (True, True), (False, True)])
    assert stats["kappa"] == 0.0
    assert stats["tnr"] == 0.0  # ne rejette aucune des réponses notées 👎


def test_empty_sample():
    assert agreement([])["kappa"] is None


def test_pairs_only_runs_with_a_vote_and_a_verdict():
    feedback = [
        _fb("r1", "user_score", 1), _fb("r1", "faithfulness", 1), _fb("r1", "answer_relevance", 0),
        _fb("r2", "user_score", 0), _fb("r2", "faithfulness", 1),
        _fb("r3", "faithfulness", 0),                     # pas de vote : ignoré
        _fb("r4", "user_score", 1), _fb("r4", "faithfulness", None),  # verdict manquant
    ]
    pairs = pairs_by_judge(feedback)
    assert sorted(pairs["faithfulness"]) == [(False, True), (True, True)]
    assert pairs["answer_relevance"] == [(True, False)]
