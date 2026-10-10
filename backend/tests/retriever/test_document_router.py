from backend.retriever.document_router import (
    RETRIEVAL_SCOPE,
    DocumentRouter,
    DocumentRouterRetriever,
    _identity_tokens,
    retrieval_scope,
)
from conftest import FakeLLM, FakeRetriever, make_doc

SOURCES = ["AMD_2022_10K.pdf", "AMERICANEXPRESS_2022_10K.pdf", "Boeing 2022 10K.pdf"]


def test_identity_tokens_ignore_generic_words():
    assert _identity_tokens("AMERICANEXPRESS_2022_10K.pdf") == {"americanexpress"}
    assert _identity_tokens("Boeing 2022 10K.pdf") == {"boeing"}
    assert _identity_tokens("annual report final.pdf") == set()


def test_match_by_name_targets_named_company_only():
    router = DocumentRouter(SOURCES)
    assert router.route("What was American Express's net revenue in 2022?") == ["AMERICANEXPRESS_2022_10K.pdf"]
    assert router.route("Compare AMD and Boeing free cash flow") == ["AMD_2022_10K.pdf", "Boeing 2022 10K.pdf"]


def test_route_without_llm_and_without_name_searches_everywhere():
    assert DocumentRouter(SOURCES, llm=None).route("What is the total revenue?") is None


def test_route_single_source_is_disabled():
    assert DocumentRouter(["only.pdf"]).route("only question") is None


def test_llm_routing_all_and_named_label():
    assert DocumentRouter(SOURCES, llm=FakeLLM(contents=["ALL"])).route("total revenue?") is None
    chosen = DocumentRouter(SOURCES, llm=FakeLLM(contents=["- AMD_2022_10K"])).route("chip maker margin?")
    assert chosen == ["AMD_2022_10K.pdf"]


def test_llm_failure_falls_back_to_all_documents():
    router = DocumentRouter(SOURCES, llm=FakeLLM(error=RuntimeError("down")))
    assert router.route("total revenue?") is None


def test_retrieval_scope_is_reset_after_block():
    assert RETRIEVAL_SCOPE.get() is None
    with retrieval_scope(["a.pdf"]):
        assert RETRIEVAL_SCOPE.get() == ["a.pdf"]
    assert RETRIEVAL_SCOPE.get() is None


def test_router_retriever_sets_scope_during_delegation():
    seen = []

    class Recording(FakeRetriever):
        def invoke(self, query):
            seen.append(RETRIEVAL_SCOPE.get())
            return [make_doc("hit")]

    wrapped = DocumentRouterRetriever(Recording(), DocumentRouter(SOURCES))
    wrapped.invoke("Boeing backlog?")
    wrapped.invoke("generic question")
    assert seen == [["Boeing 2022 10K.pdf"], None]
    assert RETRIEVAL_SCOPE.get() is None
