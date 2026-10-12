"""Les outils de l'agent (backend/tools/tools.py) : search, grep, read_page, open_doc,
navigate, appelés par un LLM factice à travers l'agent de recherche."""
from backend.agents.search_agent import SearchAgent
from backend.retriever.page_store import PageStore
from conftest import PAGES, FakeRetriever, FakeToolLLM, initial_docs, make_doc


def test_search_uses_document_scope_when_the_model_names_a_doc():
    class Scoped(FakeRetriever):
        def __init__(self):
            super().__init__(default=[make_doc("scoped", source="AMD_2022_10K", page=0)])
            self.scopes = []

        def invoke_with_scope(self, query, sources):
            self.scopes.append(sources)
            return self.invoke(query)

    r = Scoped()
    llm = FakeToolLLM([[("search", {"query": "litigation", "doc": "amd"})], "ok"])
    SearchAgent(llm=llm).run("q", r, [], scope=["ALL"], page_store=PageStore({"/x/AMD_2022_10K.pdf": ["p"]}))
    assert r.scopes == [["/x/AMD_2022_10K.pdf"]]  # le libellé est résolu vers la source

def test_tools_degrade_gracefully_without_page_store():
    llm = FakeToolLLM([[("grep", {"pattern": "x"}), ("read_page", {"doc": "AMD_2022_10K", "page": 1})], "ok"])
    out = SearchAgent(llm=llm).run("q", FakeRetriever(), initial_docs(2), page_store=None)
    tool_msgs = [m for m in llm.invocations[-1] if m.type == "tool"]
    assert all("indisponible" in m.content for m in tool_msgs)
    assert len(out["documents"]) == 2

def test_read_page_can_span_pages_and_note_is_returned():
    llm = FakeToolLLM([
        [("read_page", {"doc": "AMD_2022_10K", "page": 2, "end_page": 3})],
        "NOTE : bilan p. 2-3, current liabilities 6 369.",
    ])
    out = SearchAgent(llm=llm).run("q", FakeRetriever(), initial_docs(2), page_store=PageStore(PAGES))
    extras = out["documents"][2:]
    assert [d.metadata["page"] for d in extras] == [1, 2]
    assert out["queries"] == ["read_page: AMD_2022_10K p. 2-3"]
    assert out["note"] == "NOTE : bilan p. 2-3, current liabilities 6 369."
    tool_msg = [m for m in llm.invocations[-1] if m.type == "tool"][0]
    assert "=== AMD_2022_10K, p. 2 ===" in tool_msg.content and "=== AMD_2022_10K, p. 3 ===" in tool_msg.content

def test_open_doc_and_navigate_point_to_pages_without_adding_passages():
    pages = {"AMD_2022_10K": [
        "# PART II\n# ITEM 8. FINANCIAL STATEMENTS",
        "# Consolidated Balance Sheets\nCash 4,835\nCurrent liabilities 6,369",
        "# NOTE 4 – Segment Reporting",
    ]}
    llm = FakeToolLLM([
        [("open_doc", {})],
        [("open_doc", {"doc": "amd"})],
        [("navigate", {"doc": "AMD_2022_10K", "section": "balance sheet"})],
        [("navigate", {"doc": "AMD_2022_10K", "section": "cash flows"})],
        "Bilan p. 2.",
    ])
    out = SearchAgent(llm=llm).run("q", FakeRetriever(), initial_docs(2), page_store=PageStore(pages))
    tool_msgs = [m.content for m in llm.invocations[-1] if m.type == "tool"]
    assert tool_msgs[0] == "- AMD_2022_10K (3 pages)"
    assert tool_msgs[1].splitlines() == [
        "AMD_2022_10K — 3 pages", "p. 1 : PART II", "p. 1 : ITEM 8. FINANCIAL STATEMENTS",
        "p. 2 : Consolidated Balance Sheets", "p. 3 : NOTE 4 – Segment Reporting",
    ]
    assert tool_msgs[2].startswith("p. 2 : Consolidated Balance Sheets — Cash 4,835")
    assert tool_msgs[3].startswith("Aucun titre ne contient « cash flows »")
    assert out["queries"] == [
        "open_doc", "open_doc: amd",
        'navigate: "balance sheet" [AMD_2022_10K]', 'navigate: "cash flows" [AMD_2022_10K]',
    ]
    # navigation seulement : aucun passage ajouté après la tête
    assert len(out["documents"]) == 2

def test_grep_without_doc_stays_in_the_routed_scope():
    store = PageStore({"/x/ULTA_2023.pdf": ["SG&A decreased"], "/x/AMCOR_2023.pdf": ["SG&A decreased"]})
    llm = FakeToolLLM([[("grep", {"pattern": "SG&A"}), ("grep", {"pattern": "SG&A", "doc": "amcor"})], "ok"])
    SearchAgent(llm=llm).run("q", FakeRetriever(), [], scope=["/x/ULTA_2023.pdf"], page_store=store)
    scoped, explicit = [m.content for m in llm.invocations[-1] if m.type == "tool"]
    assert scoped == "ULTA_2023 p. 1: SG&A decreased"
    assert explicit == "AMCOR_2023 p. 1: SG&A decreased"  # un document nommé reste accessible
