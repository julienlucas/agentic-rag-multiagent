"""
La métrique de l'index vectoriel doit rester explicite.

Le défaut de Chroma est "l2". Il n'est correct que tant que les embeddings sont normés
(mistral-embed l'est). Un modèle non normé rendrait ce défaut faux sans erreur ni log :
ces tests échouent si quelqu'un retire le réglage explicite.
"""
from unittest.mock import patch

from backend.config.settings import settings


def test_vector_space_is_explicit_and_valid():
    assert settings.VECTOR_SPACE in {"cosine", "l2", "ip"}
    assert settings.VECTOR_SPACE == "cosine"


def test_in_memory_store_declares_the_space():
    """Le store de production (par session, en mémoire) doit poser hnsw:space."""
    from backend.retriever import builder as B

    captured = {}

    class FakeStore:
        def as_retriever(self, **kw):
            return object()

    def fake_from_documents(documents, embedding, **kwargs):
        captured.update(kwargs)
        return FakeStore()

    with patch.object(B, "Chroma") as chroma:
        chroma.from_documents.side_effect = fake_from_documents
        try:
            B.RetrieverBuilder.build_hybrid_retriever(
                _StubBuilder(), _one_doc(), persist_directory=None
            )
        except Exception:
            # La chaîne complète (BM25, reranker...) n'est pas l'objet du test :
            # seul compte ce qui a été passé à Chroma avant l'échec éventuel.
            pass

    assert captured.get("collection_metadata") == {"hnsw:space": settings.VECTOR_SPACE}


class _StubBuilder:
    embeddings = object()
    llm = object()
    llm_text = object()


def _one_doc():
    from langchain_core.documents import Document

    return [Document(page_content="revenue 2022", metadata={"source": "A.pdf"})]
