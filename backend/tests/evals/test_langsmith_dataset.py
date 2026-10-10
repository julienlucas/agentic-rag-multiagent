"""Dataset FinanceBench dans LangSmith : aller-retour fidèle, sans appel réseau."""
from backend.evals.financebench.langsmith_sync import example_from_row, row_from_example, sort_rows

ROW = {
    "id": "financebench_id_00222", "doc_name": "AMD_2022_10K", "company": "AMD",
    "question": "Quick ratio FY22 ?", "expected_answer": "1.57", "justification": "",
    "answer_keywords": ["1.57"], "gold_passages": ["Cash and cash equivalents $ 4,835"],
    "gold_pages": [["AMD_2022_10K", 55]], "question_type": "domain-relevant",
    "question_reasoning": "Logical reasoning",
}


def test_round_trip_keeps_every_field_the_metrics_need():
    assert row_from_example(**example_from_row(ROW)) == ROW


def test_old_examples_without_evidence_get_empty_lists():
    row = row_from_example({"question": "q", "doc_name": "D"}, {"answer": "a"}, {"financebench_id": "x"})
    assert row["gold_pages"] == [] and row["gold_passages"] == [] and row["answer_keywords"] == []


def test_rows_are_ordered_by_type_then_document():
    rows = [{**ROW, "id": "b", "question_type": "novel-generated"},
            {**ROW, "id": "a", "question_type": "metrics-generated", "doc_name": "Z"},
            {**ROW, "id": "c", "question_type": "metrics-generated", "doc_name": "A"}]
    assert [r["id"] for r in sort_rows(rows)] == ["c", "a", "b"]
