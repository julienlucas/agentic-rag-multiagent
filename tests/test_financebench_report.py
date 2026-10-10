"""Agrégat et tableau de fin de run FinanceBench : chaque métrique mesurée doit y remonter."""
import io

from evaluation.financebench import run_financebench_eval as R
from conftest import make_doc


def test_retrieval_metrics_include_precision():
    docs = [make_doc("x", source="AMD", page=p) for p in (3, 40, 41, 3)]
    for d in docs:
        d.metadata["doc_name"] = "AMD"
    ex = {"gold_pages": [["AMD", 3]], "gold_passages": []}
    m = R.compute_retrieval_metrics(docs, ex, [2, 4], page_tolerance=0)
    assert m["page_precision@2"] == 0.5 and m["page_precision@4"] == 0.5
    assert m["gold_rank"] == 1


def _row(relevancy, verdict="CORRECT"):
    return {
        "answer_f1": 0.1, "context_hit": True, "generation_sec": 1.0, "retrieval_sec": 0.5,
        "evidence_seen": True, "verdict": verdict, "judge_faithfulness": 5.0,
        "answer_relevancy": relevancy, "precision@5": 0.2, "page_precision@5": 0.4,
    }


def test_aggregate_and_report_show_new_metrics(monkeypatch):
    agg = R.aggregate([_row(0.9), _row(0.7), _row(None, "REFUSAL")], [5])
    assert agg["mean_answer_relevancy"] == 0.8 and agg["answer_relevancy_count"] == 2
    assert agg["retrieval"]["precision@5"] == 0.2 and agg["retrieval"]["page_precision@5"] == 0.4

    out = io.StringIO()
    monkeypatch.setattr(R, "_REAL_STDOUT", out)
    R.print_report({"agentic": agg, "n_questions": 3}, ["agentic"], [5])
    text = out.getvalue()
    assert "Answer relevancy (0-1)" in text and "0.8" in text
    assert "page_precision@5" in text and "precision@5 (texte)" in text
    assert "Faithfulness moyenne /5" in text


def _rep(qid, rep, verdict):
    return {"id": qid, "rep": rep, "verdict": verdict}


def test_repetition_stats_separate_stable_from_lucky_successes():
    rows = [_rep("q1", r, "CORRECT") for r in range(3)]                       # toujours juste
    rows += [_rep("q2", 0, "CORRECT"), _rep("q2", 1, "INCORRECT"), _rep("q2", 2, "CORRECT")]  # tirage
    stats = R.repetition_stats(rows)
    assert stats["reps"] == 3 and stats["questions"] == 2
    assert stats["pass_all_rate"] == 0.5          # seule q1 passe à chaque fois
    assert stats["mean_accuracy"] == round(5 / 6, 4)
    assert stats["verdict_stability"] == round((1 + 2 / 3) / 2, 4)


def test_repetition_stats_ignore_failures_and_judge_errors():
    rows = [_rep("q1", 0, "CORRECT"), _rep("q1", 1, "ERROR"), {"id": "q1", "rep": 2, "failed": True}]
    assert R.repetition_stats(rows)["pass_all_rate"] == 1.0
    assert R.repetition_stats([{"id": "q", "failed": True}]) == {}


def test_each_repetition_regenerates_but_retrieves_once():
    class Retriever:
        calls = 0

        def invoke(self, q):
            Retriever.calls += 1
            return [make_doc("x")]

    class Researcher:
        def generate(self, q, docs):
            return {"draft_answer": "réponse"}

    rows = R.evaluate_example({"id": "q1", "question": "q ?", "expected_answer": "r"}, Retriever(),
                              ["baseline"], None, Researcher(), None, [5], 0, reps=3)
    assert [r["rep"] for r in rows] == [0, 1, 2]
    assert Retriever.calls == 1
