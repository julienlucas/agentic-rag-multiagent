"""Le graphe LangGraph avec agents stubbés : aucun appel réseau."""
import pytest

from backend.agents.workflow import AgentWorkflow, build_verification_report
from backend.config.settings import settings
from conftest import FakeRetriever, make_doc


@pytest.fixture
def wf(monkeypatch):
    monkeypatch.setattr(settings, "CORRECTIVE_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(settings, "CORRECTIVE_MAX_ROUNDS", 1)
    monkeypatch.setattr(settings, "CORRECTIVE_RERANK_THRESHOLD", 0.0)
    # Ces tests couvrent la recherche corrective séparée ; le mode « outils au générateur »
    # a les siens plus bas.
    monkeypatch.setattr(settings, "GENERATOR_TOOLS_ENABLED", False)
    w = AgentWorkflow()
    w.researcher.generate = lambda q, docs, note=None: {"draft_answer": f"answer from {len(docs)} docs", "citations": [{"n": 1}]}
    corrected = lambda q, r, docs, scope=None, page_store=None: {
        "documents": docs + [make_doc("corrected", rerank=0.9)], "queries": ["q'"], "tool_calls": 2,
    }
    w.search_agent.run = corrected
    w.corrective.expand = lambda q, r, docs, scope=None: corrected(q, r, docs, scope)
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
    assert "déclenchée (2 appels d'outils)" in out["verification_report"]
    assert "q'" in out["verification_report"]


def test_rewrite_mode_falls_back_to_blind_rewriting(wf, monkeypatch):
    monkeypatch.setattr(settings, "CORRECTIVE_MODE", "rewrite")
    wf.search_agent.run = lambda *a, **k: (_ for _ in ()).throw(AssertionError("agent ne doit pas tourner"))
    wf.corrective.expand = lambda q, r, docs, scope=None: {"documents": docs + [make_doc("rw")], "queries": ["rw"]}
    out = _run(wf, ["PARTIAL", "CAN_ANSWER"], [make_doc("a", rerank=0.2)])
    assert out["draft_answer"].startswith("answer from 2")
    assert "déclenchée (1 tour)" in out["verification_report"]


def test_agent_failure_falls_back_to_rewriting(wf):
    wf.search_agent.run = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no function calling"))
    wf.corrective.expand = lambda q, r, docs, scope=None: {"documents": docs + [make_doc("rw")], "queries": ["rw"]}
    out = _run(wf, ["PARTIAL", "CAN_ANSWER"], [make_doc("a", rerank=0.2)])
    assert out["draft_answer"].startswith("answer from 2")
    assert "*rw*" in out["verification_report"]


def test_second_relevance_check_sees_head_and_added_passages(wf, monkeypatch):
    """Après correction, la tête est inchangée par construction : revérifier les 3 mêmes
    passages ne servirait à rien. Le checker doit voir la tête ET ce qui a été ajouté."""
    monkeypatch.setattr(settings, "RESEARCH_TOP_K", 3)
    monkeypatch.setattr(settings, "CORRECTIVE_EXTRA_DOCS", 2)
    seen = []

    def check(question, documents, k=3):
        seen.append([d.page_content for d in documents[:k]])
        return "PARTIAL" if len(seen) == 1 else "CAN_ANSWER"

    wf.relevance_checker.check = check
    wf.search_agent.run = lambda q, r, docs, scope=None, page_store=None: {
        "documents": docs[:3] + [make_doc("page-lue"), make_doc("resultat")], "queries": [], "tool_calls": 2,
    }
    initial = [make_doc(f"d{i}") for i in range(5)]
    wf.full_pipeline("question", FakeRetriever(default=initial))
    assert seen[0] == ["d0", "d1", "d2"]
    assert seen[1] == ["d0", "d1", "d2", "page-lue", "resultat"]


def test_no_match_twice_stops_after_max_rounds_with_refusal(wf):
    out = _run(wf, ["NO_MATCH", "NO_MATCH"], [make_doc("a", rerank=0.2)])
    assert "n'est pas liée" in out["draft_answer"]
    assert "**Pertinent:** Non" in out["verification_report"]


def test_partial_always_corrects_whatever_the_rerank_score(wf):
    """Le verdict PARTIAL du checker suffit. Avant, il fallait en plus un score de reranker
    sous le seuil — jamais atteint sur les 22 questions PARTIAL des deux jeux d'éval : le
    mode agentic appelait donc le même generate() que la baseline, et le verdict du checker
    ne servait à rien."""
    weak = _run(wf, ["PARTIAL", "PARTIAL"], [make_doc("a", rerank=0.2)])
    assert "déclenchée" in weak["verification_report"]
    strong = _run(wf, ["PARTIAL", "CAN_ANSWER"], [make_doc("a", rerank=0.95)])
    assert "déclenchée" in strong["verification_report"]


def test_can_answer_is_trusted_even_with_weak_rerank(wf):
    """Le checker a vu les passages : son CAN_ANSWER fait foi, on ne corrige pas."""
    out = _run(wf, ["CAN_ANSWER"], [make_doc("a", rerank=0.1)])
    assert "non nécessaire" in out["verification_report"]


def test_rerank_threshold_is_an_opt_in_safety_net_on_can_answer(wf, monkeypatch):
    """Seuil à 0 par défaut. Activé, il rattrape un retrieval au score anormalement bas
    que le checker a pourtant jugé suffisant."""
    monkeypatch.setattr(settings, "CORRECTIVE_RERANK_THRESHOLD", 0.5)
    out = _run(wf, ["CAN_ANSWER", "CAN_ANSWER"], [make_doc("a", rerank=0.1)])
    assert "déclenchée" in out["verification_report"]


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


def test_search_note_is_passed_to_the_generator(wf):
    """La conclusion de l'agent de recherche (où il a trouvé quoi) ne doit pas être jetée."""
    seen = {}
    wf.researcher.generate = lambda q, docs, note=None: seen.update(note=note) or {"draft_answer": "ok", "citations": []}
    wf.search_agent.run = lambda q, r, docs, scope=None, page_store=None: {
        "documents": docs + [make_doc("p")], "queries": ["read_page: X p. 3"], "tool_calls": 1,
        "note": "Bilan p. 3 : current liabilities 6 369.",
    }
    _run(wf, ["PARTIAL", "CAN_ANSWER"], [make_doc("a")])
    assert seen["note"] == "Bilan p. 3 : current liabilities 6 369."


@pytest.fixture
def wf_tools(monkeypatch):
    monkeypatch.setattr(settings, "GENERATOR_TOOLS_ENABLED", True)
    w = AgentWorkflow()
    w.corrective.expand = lambda *a, **k: (_ for _ in ()).throw(AssertionError("pas de correction séparée"))
    w.search_agent.run = lambda *a, **k: (_ for _ in ()).throw(AssertionError("pas d'agent séparé"))
    return w


def test_generator_with_tools_runs_on_every_question_and_reports_its_context(wf_tools):
    """Outils au générateur : plus de recherche corrective conditionnelle. Le contexte réel
    (initiaux + ramenés) est celui que le rapport et l'éval doivent voir."""
    calls = []

    def generate_with_tools(q, docs, retriever, page_store=None, scope=None, relevance=None):
        calls.append((len(docs), relevance))
        return {
            "draft_answer": "réponse [11]", "citations": [{"n": 11}],
            "documents": docs + [make_doc("page lue", source="AMD_2022_10K", page=55)],
            "tool_calls": 2, "queries": ['grep: "quick ratio" [AMD_2022_10K]', "read_page: AMD_2022_10K p. 56"],
        }

    wf_tools.researcher.generate_with_tools = generate_with_tools
    wf_tools.relevance_checker.check = lambda question, documents, k=3: "CAN_ANSWER"
    initial = [make_doc(f"d{i}", source="AMD_2022_10K", page=i) for i in range(12)]
    out = wf_tools.full_pipeline("question", FakeRetriever(default=initial))
    assert calls == [(settings.RESEARCH_TOP_K, "CAN_ANSWER")]  # le verdict devient un indice
    assert out["draft_answer"] == "réponse [11]"
    assert "déclenchée (2 appels d'outils)" in out["verification_report"]
    assert "read_page: AMD_2022_10K p. 56" in out["verification_report"]
    assert "11 passages transmis au modèle" in out["verification_report"]


def test_generator_with_tools_answers_even_on_no_match(wf_tools):
    """NO_MATCH n'est plus un refus a priori : le modèle a de quoi chercher."""
    wf_tools.researcher.generate_with_tools = lambda q, docs, r, page_store=None, scope=None, relevance=None: {
        "draft_answer": "trouvé par grep", "citations": [], "documents": docs, "tool_calls": 1, "queries": ["grep: x"],
    }
    wf_tools.relevance_checker.check = lambda question, documents, k=3: "NO_MATCH"
    out = wf_tools.full_pipeline("question", FakeRetriever(default=[make_doc("a")]))
    assert out["draft_answer"] == "trouvé par grep"


def test_generator_with_tools_without_tool_calls_is_not_reported_as_corrective(wf_tools):
    wf_tools.researcher.generate_with_tools = lambda q, docs, r, page_store=None, scope=None, relevance=None: {
        "draft_answer": "direct", "citations": [], "documents": docs, "tool_calls": 0, "queries": [],
    }
    wf_tools.relevance_checker.check = lambda question, documents, k=3: "CAN_ANSWER"
    out = wf_tools.full_pipeline("question", FakeRetriever(default=[make_doc("a")]))
    assert "non nécessaire" in out["verification_report"]
