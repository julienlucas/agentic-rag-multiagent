from backend.agents.corrective_retrieval import CorrectiveRetrieval
from backend.config.settings import settings
from conftest import FakeLLM, FakeRetriever, make_doc


def test_rrf_merge_boosts_doc_found_by_several_queries():
    a, b, c, d = (make_doc(t) for t in "ABCD")
    merged = CorrectiveRetrieval._merge([[a, b, c], [c, d]], top_n=10)
    # RRF (K=60) : C = 1/63 + 1/61 > A = 1/61 > B = D = 1/62 (égalité -> ordre d'insertion)
    assert [m.page_content for m in merged] == ["C", "A", "B", "D"]


def test_rrf_merge_dedups_by_content_and_respects_top_n():
    a1, a2 = make_doc("same text"), make_doc("same text")
    b = make_doc("other")
    merged = CorrectiveRetrieval._merge([[a1, b], [a2]], top_n=1)
    assert len(merged) == 1
    assert merged[0].page_content == "same text"


def test_rewrite_strips_bullets_numbering_and_original_question():
    llm = FakeLLM(contents=['1. provision for income taxes\n- "litigation"\n• Legal Proceedings\nwhat is the tax rate?'])
    cr = CorrectiveRetrieval(llm=llm)
    queries = cr.rewrite("what is the tax rate?")
    assert queries == ["provision for income taxes", "litigation", "Legal Proceedings"][: settings.CORRECTIVE_QUERY_COUNT]
    assert "{count}" not in llm.prompts[0] and "what is the tax rate?" in llm.prompts[0]


def test_rewrite_returns_empty_on_llm_failure():
    cr = CorrectiveRetrieval(llm=FakeLLM(error=RuntimeError("boom")))
    assert cr.rewrite("q") == []


def test_expand_without_queries_keeps_current_docs():
    cr = CorrectiveRetrieval(llm=FakeLLM(error=RuntimeError("boom")))
    current = [make_doc("x"), make_doc("y")]
    result = cr.expand("q", FakeRetriever(), current)
    assert result == {"documents": current, "queries": []}


def test_expand_protects_initial_top_k_and_dedups():
    protect = settings.CORRECTIVE_PROTECT_TOP
    current = [make_doc(f"initial-{i}") for i in range(protect + 3)]
    new_docs = [make_doc("new-1"), make_doc("initial-0"), make_doc("new-2")]  # initial-0 = doublon
    llm = FakeLLM(contents=["q1\nq2\nq3"])
    retriever = FakeRetriever(default=new_docs)
    cr = CorrectiveRetrieval(llm=llm)

    result = cr.expand("question", retriever, current, top_n=30)

    merged = [d.page_content for d in result["documents"]]
    assert merged[:protect] == [d.page_content for d in current[:protect]]  # tête intouchable
    assert len(merged) == len(set(merged))  # aucun doublon
    assert "new-1" in merged and "new-2" in merged
    assert result["queries"] == ["q1", "q2", "q3"]
    assert retriever.calls == ["q1", "q2", "q3"]


def test_expand_uses_scope_when_retriever_supports_it():
    class ScopedRetriever(FakeRetriever):
        def __init__(self):
            super().__init__(default=[make_doc("scoped")])
            self.scopes = []

        def invoke_with_scope(self, query, sources):
            self.scopes.append(sources)
            return self.invoke(query)

    r = ScopedRetriever()
    cr = CorrectiveRetrieval(llm=FakeLLM(contents=["q1"]))
    cr.expand("question", r, [], scope=["AMD_2022_10K.pdf"])
    assert r.scopes == [["AMD_2022_10K.pdf"]]
