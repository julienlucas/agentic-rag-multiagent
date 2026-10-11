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


def test_index_corpus_comes_from_dataset_metadata_and_falls_back_to_questions():
    """Un document sans question reste dans l'index : l'espace Qdrant se calcule sur le corpus enregistré."""
    from types import SimpleNamespace
    from backend.evals.financebench.langsmith_sync import load_corpus

    def client(metadata):
        return SimpleNamespace(read_dataset=lambda dataset_name: SimpleNamespace(metadata=metadata))

    rows = [ROW, {**ROW, "doc_name": "BOEING_2022_10K"}]
    assert load_corpus(client({"corpus": ["Z_8K", "AMD_2022_10K"]}), "x", rows) == ["AMD_2022_10K", "Z_8K"]
    assert load_corpus(client({}), "x", rows) == ["AMD_2022_10K", "BOEING_2022_10K"]
