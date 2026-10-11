"""Fin de la boucle d'outils : le modèle doit conclure, pas écrire un appel d'outil en texte."""
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from backend.agents.search_agent import FINAL_INSTRUCTION, run_tool_loop, strip_pseudo_calls
from conftest import FakeToolLLM


@tool
def read_page(doc: str, page: int) -> str:
    """Lit une page."""
    return f"page {page} de {doc}"


PSEUDO = '[Called read_page with parameters: {"doc": "PEPSICO_2022_10K", "page": 76, "end_page": 78}]'


def test_exhausted_budget_asks_explicitly_for_the_final_answer():
    llm = FakeToolLLM([[("read_page", {"doc": "PEP", "page": 76})], "Réponse : aucun litige matériel [3]."])
    out = run_tool_loop(llm, [read_page], [HumanMessage(content="q")], max_tool_calls=1)
    assert out["tool_calls"] == 1
    assert llm.invocations[-1][-1].content == FINAL_INSTRUCTION
    assert out["final"].content == "Réponse : aucun litige matériel [3]."


def test_a_tool_call_written_as_text_is_retried_once():
    llm = FakeToolLLM([[("read_page", {"doc": "PEP", "page": 76})], PSEUDO, "Réponse finale [2]."])
    out = run_tool_loop(llm, [read_page], [HumanMessage(content="q")], max_tool_calls=1)
    assert out["final"].content == "Réponse finale [2]."
    assert len(llm.invocations) == 3


def test_pseudo_calls_are_stripped_from_the_answer():
    assert strip_pseudo_calls(f"{PSEUDO}\nLe CA est de 86 Md$ [1].") == "Le CA est de 86 Md$ [1]."
    assert strip_pseudo_calls(PSEUDO) == ""


def test_process_preamble_is_removed_from_the_answer():
    from backend.agents.research_agent import ResearchAgent
    agent = ResearchAgent.__new__(ResearchAgent)
    raw = "I now have all the data needed. Let me calculate.\n\n---\n\n**JnJ sold its inventory 2.7×** [3]"
    assert agent.sanitize_response(raw) == "**JnJ sold its inventory 2.7×** [3]"
    assert agent.sanitize_response("Oui : un client = 16 % du CA [2].") == "Oui : un client = 16 % du CA [2]."
