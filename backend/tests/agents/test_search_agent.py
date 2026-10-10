"""L'agent de recherche à outils, avec un LLM factice qui émet des appels d'outils."""
from langchain_core.messages import AIMessage

from backend.agents.search_agent import SearchAgent
from backend.config.settings import settings
from backend.retriever.page_store import PageStore
from conftest import PAGES, FakeRetriever, FakeToolLLM, initial_docs, make_doc


def test_read_pages_come_first_then_reranked_search_results_after_protected_head():
    llm = FakeToolLLM([
        [("grep", {"pattern": "current liabilities", "doc": "AMD_2022_10K"})],
        [("read_page", {"doc": "AMD_2022_10K", "page": 2})],
        [("search", {"query": "AMD cash and short-term investments 2022"})],
        "J'ai trouvé le bilan p. 2.",
    ])
    retriever = FakeRetriever(default=[make_doc("search-hit", source="AMD_2022_10K", page=1),
                                       make_doc("initial-0", source="AMD_2022_10K", page=0)])
    agent = SearchAgent(llm=llm)
    head = initial_docs()
    out = agent.run("quick ratio d'AMD ?", retriever, head + [make_doc("tail")],
                    page_store=PageStore(PAGES))

    assert llm.tool_names == ["search", "grep", "read_page", "open_document", "navigate"]
    assert out["tool_calls"] == 3
    docs = out["documents"]
    # tête intouchable, dans le même ordre
    assert [d.page_content for d in docs[:len(head)]] == [d.page_content for d in head]
    extras = docs[len(head):]
    assert extras[0].metadata["origin"] == "read_page" and extras[0].metadata["page"] == 1
    assert "Current liabilities 6,369" in extras[0].page_content
    # le résultat de search vient après la page lue ; le doublon de la tête est écarté
    assert [d.page_content for d in extras[1:]] == ["search-hit"]
    assert len(extras) <= settings.CORRECTIVE_EXTRA_DOCS
    # trace lisible pour le rapport de vérification
    assert out["queries"] == [
        'grep: "current liabilities" [AMD_2022_10K]',
        "read_page: AMD_2022_10K p. 2",
        'search: "AMD cash and short-term investments 2022"',
    ]
    # les résultats d'outils sont bien renvoyés au modèle (ToolMessage après chaque appel)
    tool_msgs = [m for m in llm.invocations[-1] if m.type == "tool"]
    assert len(tool_msgs) == 3
    assert "p. 2: Current liabilities 6,369" in tool_msgs[0].content
    assert tool_msgs[1].content.startswith("=== AMD_2022_10K, p. 2 ===")
    assert "[1] (AMD_2022_10K, p. 2) search-hit" in tool_msgs[2].content


def test_budget_caps_tool_calls_and_still_returns_head():
    calls = [[("grep", {"pattern": f"t{i}", "doc": "AMD_2022_10K"})] for i in range(10)]
    llm = FakeToolLLM(calls)
    agent = SearchAgent(llm=llm)
    agent.max_tool_calls = 2
    out = agent.run("q", FakeRetriever(), initial_docs(3), page_store=PageStore(PAGES))
    assert out["tool_calls"] == 2
    assert [d.page_content for d in out["documents"]] == ["initial-0", "initial-1", "initial-2"]


def test_no_tool_calls_keeps_context_unchanged():
    llm = FakeToolLLM(["Rien à chercher."])
    out = SearchAgent(llm=llm).run("q", FakeRetriever(), initial_docs(4), page_store=PageStore(PAGES))
    assert out == {"documents": initial_docs(4), "queries": [], "tool_calls": 0} or (
        [d.page_content for d in out["documents"]] == [d.page_content for d in initial_docs(4)]
        and out["queries"] == [] and out["tool_calls"] == 0
    )


def test_generator_with_tools_numbers_fetched_passages_and_answers_in_place():
    """Le modèle qui cherche est celui qui répond : les passages ramenés par ses outils
    reçoivent un numéro qu'il voit dans le résultat, et la réponse finale les cite."""
    from backend.agents.research_agent import ResearchAgent

    llm = FakeToolLLM([
        [("search", {"query": "AMD balance sheet", "doc": "AMD_2022_10K"})],
        [("read_page", {"doc": "AMD_2022_10K", "page": 2})],
        "Quick ratio = 4,835 / 6,369 [3][4]",
    ])
    agent = ResearchAgent.__new__(ResearchAgent)  # sans clients Mistral
    agent.model = llm
    agent.model_tools = llm
    retriever = FakeRetriever(default=[make_doc("search-hit", source="AMD_2022_10K", page=1),
                                       make_doc("initial-0", source="AMD_2022_10K", page=0)])
    initial = [make_doc("initial-0", source="AMD_2022_10K", page=0), make_doc("initial-1", source="AMD_2022_10K", page=1)]
    out = agent.generate_with_tools("quick ratio ?", initial, retriever, page_store=PageStore(PAGES),
                                    max_tool_calls=3, relevance="PARTIAL")

    assert out["draft_answer"] == "Quick ratio = 4,835 / 6,369 [3][4]"
    assert out["tool_calls"] == 2
    # initiaux [1][2] conservés, search-hit -> [3] (initial-0 déjà [1]), page lue -> [4]
    assert [c["n"] for c in out["citations"]] == [1, 2, 3, 4]
    assert [d.page_content for d in out["documents"]][:3] == ["initial-0", "initial-1", "search-hit"]
    assert out["documents"][3].metadata["origin"] == "read_page"
    tool_msgs = [m for m in llm.invocations[-1] if m.type == "tool"]
    assert "[3] (AMD_2022_10K, p. 2) search-hit" in tool_msgs[0].content
    assert "[1] (AMD_2022_10K, p. 1) initial-0" in tool_msgs[0].content  # doublon : garde son numéro
    assert tool_msgs[1].content.startswith("=== [4] AMD_2022_10K, p. 2 ===")
    # le prompt système porte les règles et le guide des outils, avec le budget
    system = llm.invocations[0][0]
    assert "RÈGLES STRICTES" in system.content and "3 appels d'outils au maximum" in system.content
    assert "jugé le contexte initial PARTIEL" in system.content  # le verdict du vérificateur, en indice


def test_generator_with_tools_forces_an_answer_when_budget_is_exhausted():
    from backend.agents.research_agent import ResearchAgent

    # Deux appels dans le même tour, budget d'un seul : le second est refusé, puis le
    # modèle est rappelé sans outils pour conclure.
    llm = FakeToolLLM([
        [("grep", {"pattern": "a", "doc": "AMD_2022_10K"}), ("grep", {"pattern": "b", "doc": "AMD_2022_10K"})],
        "réponse forcée",
    ])
    agent = ResearchAgent.__new__(ResearchAgent)
    agent.model = llm
    agent.model_tools = llm
    out = agent.generate_with_tools("q", [make_doc("x")], FakeRetriever(), page_store=PageStore(PAGES), max_tool_calls=1)
    assert out["tool_calls"] == 1
    assert out["draft_answer"] == "réponse forcée"
    # le second appel a été refusé avec un message de budget, puis conclusion forcée
    budget_msgs = [m for m in llm.invocations[-1] if m.type == "tool" and "Budget" in m.content]
    assert budget_msgs


def test_block_list_content_is_flattened_to_text():
    """Mistral renvoie parfois `content` en liste de blocs : 2 questions perdues sur un run."""
    from backend.agents.search_agent import message_text

    assert message_text(AIMessage(content="plain")) == "plain"
    assert message_text(AIMessage(content=[{"type": "text", "text": "a "}, {"type": "text", "text": "b"}])) == "a b"
    assert message_text(AIMessage(content=[])) == ""
