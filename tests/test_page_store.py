"""Le PageStore : grep / read_page / toc sur des pages OCR, sans appel réseau."""
from backend.retriever.page_store import PageStore, doc_label

PAGES = {
    "/tmp/AMD_2022_10K.pdf": [
        "# Item 1. Business\nAMD designs semiconductors.",
        "## Segment Information\nData Center segment revenue was $6,043 million.\n| Segment | 2022 |\n| Data Center | 6,043 |",
        "Provision for income taxes (122)\nEffective tax rate 21.6%",
    ],
    "BOEING_2022_10K": ["Boeing page one", "Effective tax rate 0.6%"],
}


def test_labels_and_resolution():
    store = PageStore(PAGES)
    assert doc_label("/tmp/AMD_2022_10K.pdf") == "AMD_2022_10K"
    assert store.documents() == ["AMD_2022_10K", "BOEING_2022_10K"]
    assert store.page_count("AMD_2022_10K") == 3
    assert store.source_of("AMD_2022_10K") == "/tmp/AMD_2022_10K.pdf"
    # libellé exact, chemin, sous-chaîne insensible à la casse
    assert store.resolve("AMD_2022_10K") == "AMD_2022_10K"
    assert store.resolve("/tmp/AMD_2022_10K.pdf") == "AMD_2022_10K"
    assert store.resolve("boeing") == "BOEING_2022_10K"
    assert store.resolve("2022_10K") is None  # ambigu


def test_grep_is_exhaustive_and_page_indexed():
    store = PageStore(PAGES)
    out = store.grep("effective tax rate")
    assert out["total"] == 2
    assert {(h["doc"], h["page"]) for h in out["hits"]} == {("AMD_2022_10K", 2), ("BOEING_2022_10K", 1)}
    scoped = store.grep("effective tax rate", doc="AMD_2022_10K")
    assert scoped["total"] == 1 and scoped["hits"][0]["page"] == 2
    # 0 résultat = le terme est absent, c'est une information
    assert store.grep("gross margin", doc="AMD_2022_10K") == {"hits": [], "total": 0}
    # regex invalide -> repli littéral, pas d'exception
    assert store.grep("(122", doc="AMD_2022_10K")["total"] == 1
    assert "error" in store.grep("x", doc="UNKNOWN")


def test_read_page_returns_whole_page_and_checks_bounds():
    store = PageStore(PAGES)
    page = store.read_page("AMD_2022_10K", 1)
    assert "| Data Center | 6,043 |" in page["text"] and page["n_pages"] == 3
    assert "error" in store.read_page("AMD_2022_10K", 3)
    assert "error" in store.read_page("AMD_2022_10K", -1)
    assert "error" in store.read_page("NOPE", 0)
    truncated = store.read_page("AMD_2022_10K", 1, max_chars=20)
    assert truncated["truncated"] and truncated["text"].endswith("[page tronquée]")


def test_page_document_carries_chunk_compatible_metadata():
    store = PageStore(PAGES)
    doc = store.page_document("AMD_2022_10K", 2)
    assert doc.metadata == {
        "source": "/tmp/AMD_2022_10K.pdf", "doc_name": "AMD_2022_10K", "page": 2, "origin": "read_page",
    }
    assert store.page_document("AMD_2022_10K", 99) is None


def test_toc_lists_markdown_headers_with_pages():
    store = PageStore(PAGES)
    toc = store.toc("AMD_2022_10K")
    assert [(e["page"], e["level"], e["title"]) for e in toc["entries"]] == [
        (0, 1, "Item 1. Business"), (1, 2, "Segment Information"),
    ]


def test_read_pages_spans_consecutive_pages_with_a_cap():
    store = PageStore(PAGES)
    out = store.read_pages("AMD_2022_10K", 1, 2)
    assert out["pages"] == [1, 2]
    assert "=== p. 2 ===" in out["text"] and "=== p. 3 ===" in out["text"]
    assert store.read_pages("AMD_2022_10K", 2, 1)["pages"] == [1, 2]  # bornes inversées
    assert store.read_pages("AMD_2022_10K", 0, 10, max_pages=2)["pages"] == [0, 1]  # plafond
    assert "error" in store.read_pages("AMD_2022_10K", 7, 9)
    docs = store.page_documents("AMD_2022_10K", 1, 2)
    assert [d.metadata["page"] for d in docs] == [1, 2] and all(d.metadata["origin"] == "read_page" for d in docs)
