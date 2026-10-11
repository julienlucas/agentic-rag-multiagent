"""Corpus FinanceBench en markdown : tableaux, recalage sur les pages du PDF, trous et doublons."""
from backend.evals.financebench.markdown_corpus import (
    assign_pages, evidence_coverage, markdown_pages, page_gaps, parse_blocks, render_pages,
)
from backend.evals.financebench.prepare import DEFAULT_DOCS, eval_tenant_for, preset_docs

TABLE = """<table>
  <thead>
    <tr><th></th><th colspan="2">Year Ended</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>Data Center</strong></td><td>$ 6,043</td><td>$ 3,694</td></tr>
    <tr><td rowspan="2">Client</td><td>6,201</td><td>6,887</td></tr>
    <tr><td>1</td><td>2</td></tr>
  </tbody>
</table>"""

# Trois pages de PDF, chacune avec un texte qui lui est propre (assez long pour compter comme une page).
REFERENCE = [
    "Advanced Micro Devices annual report cover page for the fiscal year ended December thirty one "
    "twenty twenty two filed with the Securities and Exchange Commission in Washington",
    "Data Center net revenue increased strongly driven by EPYC server processors sales to cloud "
    "customers and enterprise buyers across North America Europe and Asia during the year",
    "Gaming segment revenue declined on lower semi custom product sales this year partially offset "
    "by higher Radeon graphics processor sales into the channel and to notebook makers",
]


def test_html_table_becomes_a_markdown_table_with_spans_flattened():
    blocks = parse_blocks(TABLE)
    page = render_pages(blocks, [0] * len(blocks), 1)[0]
    assert page.splitlines() == [
        "|  | Year Ended |  |",
        "| --- | --- | --- |",
        "| Data Center | $ 6,043 | $ 3,694 |",
        "| Client | 6,201 | 6,887 |",
        "|  | 1 | 2 |",
    ]


def test_printed_page_numbers_and_entities_are_cleaned_outside_tables():
    blocks = parse_blocks("Revenue rose &amp; margins held.\n\n&lt;page_number&gt;47&lt;/page_number&gt;")
    assert [b["text"] for b in blocks] == ["Revenue rose & margins held."]


def test_blocks_follow_the_pdf_pages_and_never_go_back():
    md = "\n\n".join([
        "Advanced Micro Devices annual report cover page",
        "Data Center net revenue increased strongly driven by EPYC",
        "Logo",  # trop court pour voter : prend la page de ses voisins
        "server processors sales to cloud customers and enterprise buyers",
        "Gaming segment revenue declined on lower semi custom product",
    ])
    blocks = parse_blocks(md)
    assert assign_pages(blocks, REFERENCE) == [0, 1, 1, 1, 2]


def test_a_table_cut_by_a_page_break_repeats_its_header():
    blocks = parse_blocks(TABLE)
    pages = render_pages(blocks, [0, 0, 1, 1], 2)
    assert pages[1].splitlines()[0] == "|  | Year Ended |  |"
    assert "Client" in pages[1] and "Client" not in pages[0]


def test_a_page_copied_twice_in_the_markdown_is_kept_once():
    md = "\n\n".join([REFERENCE[1], REFERENCE[1], TABLE, TABLE])
    page = markdown_pages(md, ["", REFERENCE[1] + " Data Center 6043 3694 Client 6201 6887", ""])[1]
    assert page.count("EPYC") == 1 and page.count("| Data Center |") == 1


def test_pages_missing_from_the_markdown_are_reported():
    pages = markdown_pages(REFERENCE[0], REFERENCE)
    assert page_gaps(pages, REFERENCE) == [1, 2]
    assert evidence_coverage(REFERENCE[2], pages[2]) == 0.0


def test_pilot_preset_keeps_the_most_questioned_documents_and_the_published_protocol():
    questions = [{"doc_name": d} for d in DEFAULT_DOCS for _ in range(5)]
    questions += [{"doc_name": f"DOC_{i:02d}"} for i in range(30)]
    pilot = preset_docs(questions, "pilot")
    assert len(pilot) == 20 and set(DEFAULT_DOCS) <= set(pilot)
    assert preset_docs(questions, "all") == sorted({q["doc_name"] for q in questions})


def test_each_source_has_its_own_qdrant_space():
    assert eval_tenant_for(DEFAULT_DOCS, "markdown") != eval_tenant_for(DEFAULT_DOCS, "ocr")
    assert eval_tenant_for(DEFAULT_DOCS) == eval_tenant_for(list(reversed(DEFAULT_DOCS)), "markdown")


def test_questions_with_evidence_on_a_missing_page_are_dropped():
    from backend.evals.financebench.prepare import unanswerable
    questions = [
        {"financebench_id": "ok", "doc_name": "BOEING_2022_10K", "evidence": [{"evidence_page_num": 7}]},
        {"financebench_id": "gap", "doc_name": "BOEING_2022_10K",
         "evidence": [{"evidence_page_num": 7}, {"evidence_page_num": 54}]},
    ]
    assert list(unanswerable(questions, {"BOEING_2022_10K": [53, 54]})) == ["gap"]


def test_prune_removes_questions_no_longer_in_the_dataset():
    from types import SimpleNamespace
    from backend.evals.financebench.langsmith_sync import example_from_row, upsert_dataset

    row = {"id": "keep", "doc_name": "D", "question": "q", "expected_answer": "a", "gold_pages": [],
           "gold_passages": [], "answer_keywords": []}
    kept = example_from_row(row)
    old = SimpleNamespace(id="ex-old", inputs={}, outputs={}, metadata={"financebench_id": "old"})
    same = SimpleNamespace(id="ex-keep", **kept)
    deleted = []
    client = SimpleNamespace(
        has_dataset=lambda dataset_name: True,
        read_dataset=lambda dataset_name: SimpleNamespace(id="ds"),
        list_examples=lambda dataset_id: [old, same],
        update_example=lambda *a, **k: None,
        create_examples=lambda **k: None,
        delete_examples=deleted.extend,
    )
    upsert_dataset(client, "x", [row], prune=True)
    assert deleted == ["ex-old"]
