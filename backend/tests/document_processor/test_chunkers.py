from backend.document_processor.chunkers import ParentChildChunkingStrategy

TEXT = " ".join(f"sentence number {i} about revenue and margins." for i in range(120))


def test_parent_child_children_carry_parent_and_metadata():
    strat = ParentChildChunkingStrategy(parent_chunk_size=400, child_chunk_size=120, child_overlap=20)
    children = strat.split(TEXT, metadata={"source": "AMD_2022_10K.pdf", "page": 12})

    assert children, "aucun chunk produit"
    parents = {c.metadata["parent_id"] for c in children}
    assert len(parents) >= 2
    for c in children:
        assert c.metadata["is_child"] is True
        assert c.metadata["source"] == "AMD_2022_10K.pdf" and c.metadata["page"] == 12
        assert c.page_content in c.metadata["parent_content"]
        assert len(c.page_content) <= 120
        assert len(c.metadata["parent_content"]) <= 400


def test_parent_child_covers_whole_text():
    strat = ParentChildChunkingStrategy(parent_chunk_size=400, child_chunk_size=120, child_overlap=20)
    children = strat.split(TEXT)
    joined = " ".join(c.page_content for c in children)
    assert "sentence number 0 " in joined and "sentence number 119" in joined
