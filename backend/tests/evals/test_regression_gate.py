"""La logique de décision des garde-fous de régression (backend/evals/financebench/regression.py).

Les runs eux-mêmes appellent les API ; ce qui est testé ici, c'est ce qui décide « régression
ou pas » — un garde-fou qui laisse passer une régression est pire que pas de garde-fou."""
import json
from pathlib import Path

from backend.config.settings import settings
from backend.evals.financebench.regression import (
    BASELINE_PATH,
    SENTINELS_PATH,
    DegradationWatch,
    check_sentinel,
    compare_retrieval,
    per_question,
)
from conftest import FakeRetriever, make_doc


def _q(rank, hit=None):
    hit = (1.0 if rank is not None and rank <= 10 else 0.0) if hit is None else hit
    return {"gold_rank": rank, "page_hit@10": hit, "page_recall@10": hit, "mrr@10": 1 / rank if rank else 0.0}


def test_identical_runs_pass():
    base = {"a": _q(1), "b": _q(15), "c": _q(None)}
    assert compare_retrieval(base, dict(base))["ok"]


def test_losing_one_question_fails_even_if_the_mean_is_unchanged():
    """Une perte compensée par un gain laisse page_hit@10 identique : la moyenne ne voit rien."""
    base = {"a": _q(3), "b": _q(15)}
    cur = {"a": _q(12), "b": _q(4)}
    report = compare_retrieval(base, cur)
    assert report["metrics"]["page_hit@10"]["delta"] == 0
    assert not report["ok"]
    assert report["lost"] == [{"id": "a", "before": 3, "after": 12}]
    assert report["gained"] == [{"id": "b", "before": 15, "after": 4}]


def test_tolerances_are_respected():
    base = {f"q{i}": _q(1) for i in range(20)}
    cur = dict(base, q0=_q(None))
    assert not compare_retrieval(base, cur)["ok"]
    assert compare_retrieval(base, cur, max_lost=1)["ok"]  # 1 perte sur 20 = -5 pts : à la limite
    cur2 = dict(cur, q1=_q(None))
    assert not compare_retrieval(base, cur2, max_lost=2)["ok"]  # -10 pts > 5 pts tolérés


def test_moves_inside_the_top_k_are_reported_not_failed():
    report = compare_retrieval({"a": _q(2)}, {"a": _q(8)})
    assert report["ok"] and report["moved"] == [{"id": "a", "before": 2, "after": 8}]


def test_missing_questions_fail_the_gate():
    report = compare_retrieval({"a": _q(1), "b": _q(2)}, {"a": _q(1)})
    assert not report["ok"] and report["missing"] == ["b"]


def test_per_question_keeps_one_row_per_id():
    rows = [{"id": "a", "mode": "baseline", "gold_rank": 3}, {"id": "a", "mode": "agentic", "gold_rank": 3}]
    assert list(per_question(rows)) == ["a"]


def test_sentinel_checks_verdict_evidence_and_tools():
    expect = {"verdict": "CORRECT", "evidence_seen": True, "min_tool_calls": 1}
    good = {"verdict": "CORRECT", "evidence_seen": True, "tool_calls": 2}
    assert check_sentinel(good, expect) == []
    assert len(check_sentinel({"verdict": "INCORRECT", "evidence_seen": False, "tool_calls": 0}, expect)) == 3
    assert check_sentinel({"failed": True, "error": "timeout"}, expect)[0].startswith("échec technique")


def test_sentinels_exist_in_the_dataset_and_are_explained():
    # Les questions du protocole : celles de la baseline versionnée (le dataset vit dans LangSmith).
    ids = set(json.loads(Path(BASELINE_PATH).read_text(encoding="utf-8"))["questions"])
    sentinels = json.loads(Path(SENTINELS_PATH).read_text(encoding="utf-8"))["sentinels"]
    assert len(sentinels) >= 8
    for s in sentinels:
        assert s["id"] in ids
        assert s.get("why")


def test_degradation_watch_flags_silent_rerank_fallback(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_ENABLED", True)
    reranked = make_doc("a")
    reranked.metadata["rerank_score"] = 0.9
    ok = DegradationWatch(FakeRetriever(default=[reranked]))
    ok.invoke("q")
    assert ok.problems(1) == []

    degraded = DegradationWatch(FakeRetriever(default=[make_doc("a")]))
    degraded.invoke("q")
    assert "rerank" in degraded.problems(1)[0]
    assert degraded.calls == ["q"]  # les autres attributs passent au retriever enveloppé


def test_other_document_sets_never_overwrite_the_published_dataset():
    from backend.evals.financebench.prepare import DEFAULT_DOCS, dataset_name_for, extended_docs

    assert dataset_name_for(list(reversed(DEFAULT_DOCS))) == "agentic-search · FinanceBench"
    assert dataset_name_for(["AMD_2022_10K"]) == "agentic-search · FinanceBench (custom)"
    questions = [{"doc_name": d} for d in ["A"] * 3 + ["B"] * 2 + ["C"] * 4]
    assert extended_docs(questions) == ["A", "C"]
    assert dataset_name_for(["A", "C"], "extended") == "agentic-search · FinanceBench (extended)"


def test_prepare_skips_documents_already_in_the_eval_index(monkeypatch):
    """Relancer prepare.py sans cache local ne doit pas repayer l'OCR d'un document déjà indexé."""
    import backend.vectorstore as vectorstore
    from backend.evals.financebench.prepare import already_indexed, eval_tenant_for
    from conftest import make_store

    store = make_store()
    monkeypatch.setattr(vectorstore, "get_eval_store", lambda: store)
    docs = ["AMD_2022_10K", "BOEING_2022_10K"]
    tenant = store.for_tenant(eval_tenant_for(docs))
    tenant.add_document("h", "AMD_2022_10K", [make_doc("bilan", source="AMD_2022_10K")], ["p1"])

    assert already_indexed(docs) == ["AMD_2022_10K"]


def test_a_document_indexed_for_another_document_set_is_copied_not_re_embedded(monkeypatch):
    """Les 84 rapports reprennent les vecteurs des 20 de l'essai : aucun appel d'embedding pour eux."""
    import backend.vectorstore as vectorstore
    from backend.evals.experiment_utils import index_chunks
    from conftest import make_store

    store = make_store()
    monkeypatch.setattr(vectorstore, "get_eval_store", lambda: store)
    chunks = [make_doc("Total net revenue 23,601", source="AMD_2022_10K"),
              make_doc("Gaming revenue 6,805", source="AMD_2022_10K")]
    index_chunks("financebench-pilot", chunks, {"AMD_2022_10K": ["p0", "p1"]})

    calls = []
    cls = type(store.embeddings)
    real = cls.embed_documents
    monkeypatch.setattr(cls, "embed_documents", lambda self, texts: calls.append(texts) or real(self, texts))
    full = index_chunks("financebench-full", chunks, {"AMD_2022_10K": ["p0", "p1"]})

    assert calls == []
    assert full.chunk_count() == 2 and full.sources() == ["AMD_2022_10K"]
    assert full.pages() == {"AMD_2022_10K": ["p0", "p1"]}
    assert {d.page_content for d in full.hybrid_search("Gaming revenue", 5, 5)} == {c.page_content for c in chunks}
    assert store.for_tenant("financebench-pilot").chunk_count() == 2  # l'original est intact
