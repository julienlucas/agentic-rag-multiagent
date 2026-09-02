"""Le graphe LangGraph avec agents stubbés : aucun appel réseau."""
import pytest

from backend.agents.workflow import AgentWorkflow, build_verification_report
from backend.config.settings import settings
from conftest import FakeRetriever, make_doc


@pytest.fixture
def wf(monkeypatch):
    monkeypatch.setattr(settings, "CORRECTIVE_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(settings, "CORRECTIVE_MAX_ROUNDS", 1)
    monkeypatch.setattr(settings, "CORRECTIVE_RERANK_THRESHOLD", 0.5)
    w = AgentWorkflow()
    w.researcher.generate = lambda q, docs: {"draft_answer": f"answer from {len(docs)} docs", "citations": [{"n": 1}]}
    w.corrective.expand = lambda q, r, docs, scope=None: {"documents": docs + [make_doc("corrected", rerank=0.9)], "queries": ["q'"]}
    return w


def _run(w, relevance_sequence, docs):
    seq = list(relevance_sequence)
    w.relevance_checker.check = lambda question, documents, k=3: seq.pop(0)
    retriever = FakeRetriever(default=docs)
    return w.full_pipeline("question", retriever)


def test_can_answer_goes_straight_to_research(wf):
    out = _run(wf, ["CAN_ANSWER"], [make_doc("a", rerank=0.9)])
    assert out["draft_answer"].startswith("answer from")
    assert "non nécessaire" in out["verification_report"]
    assert out["citations"] == [{"n": 1}]


def test_no_match_triggers_one_corrective_round_then_answers(wf):
    out = _run(wf, ["NO_MATCH", "CAN_ANSWER"], [make_doc("a", rerank=0.2)])
    assert out["draft_answer"].startswith("answer from 2")
    assert "déclenchée (1 tour)" in out["verification_report"]
    assert "q'" in out["verification_report"]


def test_no_match_twice_stops_after_max_rounds_with_refusal(wf):
    out = _run(wf, ["NO_MATCH", "NO_MATCH"], [make_doc("a", rerank=0.2)])
    assert "n'est pas liée" in out["draft_answer"]
    assert "**Pertinent:** Non" in out["verification_report"]


def test_partial_with_weak_rerank_corrects_but_strong_rerank_does_not(wf):
    weak = _run(wf, ["PARTIAL", "PARTIAL"], [make_doc("a", rerank=0.2)])
    assert "déclenchée" in weak["verification_report"]
    strong = _run(wf, ["PARTIAL"], [make_doc("a", rerank=0.8)])
    assert "non nécessaire" in strong["verification_report"]


def test_can_answer_is_trusted_even_with_weak_rerank(wf):
    out = _run(wf, ["CAN_ANSWER"], [make_doc("a", rerank=0.1)])
    assert "non nécessaire" in out["verification_report"]


def test_verification_report_lists_sources_and_pages():
    state = {
        "relevance": "CAN_ANSWER",
        "documents": [make_doc("x", source="AMD_2022_10K.pdf", page=3, rerank=0.75), make_doc("y", source="AMD_2022_10K.pdf", page=7)],
        "corrective_rounds": 0,
    }
    report = build_verification_report(state)
    assert "**Pertinent:** Oui" in report
    assert "0.75 — élevée" in report
    assert "AMD_2022_10K (p. 4, 8)" in report  # pages affichées en 1-indexé
