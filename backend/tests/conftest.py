"""
Environnement minimal pour importer le backend sans clés réelles ni appel réseau.
Doit être importé avant backend.config.settings (pytest charge conftest en premier).
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("MISTRALAI_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("COHERE_API_KEY", "test-key")
os.environ.setdefault("QDRANT_URL", "")  # tests : jamais le cluster réel
os.environ.setdefault("LANGSMITH_API_KEY", "")
os.environ.setdefault("FEEDBACK_AUTO_COLLECT", "false")  # pas de thread vers LangSmith en test

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import json  # noqa: E402

import pytest  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402


def make_doc(text: str, source: str = "DOC.pdf", page: int | None = None, rerank: float | None = None) -> Document:
    meta = {"source": source, "doc_name": source}
    if page is not None:
        meta["page"] = page
    if rerank is not None:
        meta["rerank_score"] = rerank
    return Document(page_content=text, metadata=meta)


class FakeLLM:
    """Remplace ChatMistralAI : renvoie des contenus prédéfinis, ou lève une exception."""

    def __init__(self, contents=None, error: Exception | None = None):
        self.contents = list(contents or [])
        self.error = error
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        content = self.contents.pop(0) if self.contents else ""

        class _Resp:
            pass

        r = _Resp()
        r.content = content
        return r


class FakeRetriever:
    """Retriever déterministe : une liste de docs par requête (ou par défaut)."""

    def __init__(self, by_query=None, default=None):
        self.by_query = by_query or {}
        self.default = default or []
        self.calls = []

    def invoke(self, query: str):
        self.calls.append(query)
        return list(self.by_query.get(query, self.default))


class FakeSparse:
    """Remplace fastembed BM25 : fréquences de termes, hashés de façon stable (sans réseau)."""

    @staticmethod
    def _vec(text: str, query: bool = False):
        import re
        import zlib
        from qdrant_client import models

        counts = {}
        for tok in re.findall(r"\w+", text.lower()):
            idx = zlib.crc32(tok.encode())
            counts[idx] = 1.0 if query else counts.get(idx, 0.0) + 1.0
        return models.SparseVector(indices=list(counts), values=list(counts.values()))

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text, query=True)


def make_store():
    """QdrantStore en mémoire, embeddings et BM25 factices."""
    from langchain_core.embeddings import DeterministicFakeEmbedding
    from qdrant_client import QdrantClient

    from backend.config.settings import settings
    from backend.vectorstore import QdrantStore

    return QdrantStore(
        client=QdrantClient(":memory:"),
        embeddings=DeterministicFakeEmbedding(size=settings.EMBEDDING_DIMENSIONS),
        sparse=FakeSparse(),
    )


class FakeCohere:
    """Score = recouvrement lexical avec la requête, pour un ordre déterministe."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def rerank(self, model, query, documents, top_n):
        import re

        self.calls.append(len(documents))
        if self.fail:
            raise RuntimeError("cohere 503")
        q = set(re.findall(r"\w+", query.lower()))

        def score(text):
            return len(q & set(re.findall(r"\w+", text.lower()))) / (len(q) or 1)

        ranked = sorted(range(len(documents)), key=lambda i: score(documents[i]), reverse=True)[:top_n]

        class _Res:
            def __init__(self, i):
                self.index, self.relevance_score = i, score(documents[i])

        class _Resp:
            results = [_Res(i) for i in ranked]
            meta = None

        return _Resp()


# ── API HTTP (tests de backend/endpoints.py et des votes) ─────────────────────
# Django n'est démarré que par les tests qui demandent ces fixtures.

def _django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
    import django
    django.setup()
    from backend import endpoints
    return endpoints


class FakeProcessor:
    """Remplace l'OCR : chaque fichier donne un chunk et deux pages."""
    calls = 0

    def __init__(self):
        self.pages = {}

    def process(self, files):
        FakeProcessor.calls += 1
        self.pages = {f.name: ["page 1", "page 2"] for f in files}
        return [make_doc(f"chunk de {f.name}", source=f.name) for f in files]


class FakeBuilder:
    def build_hybrid_retriever(self, tenant):
        return ("retriever", tenant.tenant_id, len(tenant.sources()))


@pytest.fixture
def store(monkeypatch):
    endpoints = _django()
    s = make_store()
    monkeypatch.setattr(endpoints, "get_store", lambda: s)
    monkeypatch.setattr(endpoints, "_page_cache", {})
    return s


@pytest.fixture
def api(monkeypatch, tmp_path, store):
    endpoints = _django()
    from django.test import Client
    from backend.config.settings import settings

    FakeProcessor.calls = 0
    monkeypatch.setattr(endpoints, "DocumentProcessor", FakeProcessor)
    monkeypatch.setattr(endpoints, "RetrieverBuilder", FakeBuilder)
    monkeypatch.setattr(settings, "EXAMPLES_DIR", str(tmp_path))
    (tmp_path / "rapport.pdf").write_bytes(b"%PDF-1.4 exemple")
    (tmp_path.parent / "secret.md").write_text("hors du dossier d'exemples")
    return Client()


def post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


# ── Agent à outils : LLM factice qui émet des appels d'outils ──────────────────

class FakeToolLLM:
    """Renvoie une séquence d'AIMessage (avec ou sans tool_calls) ; bind_tools est un no-op."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.invocations = []

    def bind_tools(self, tools):
        self.tool_names = [t.name for t in tools]
        return self

    def invoke(self, messages):
        self.invocations.append(list(messages))
        if not self.turns:
            return AIMessage(content="terminé")
        turn = self.turns.pop(0)
        if isinstance(turn, str):
            return AIMessage(content=turn)
        return AIMessage(content="", tool_calls=[
            {"name": name, "args": args, "id": f"call{i:05d}"} for i, (name, args) in enumerate(turn)
        ])


PAGES = {"AMD_2022_10K": ["Item 1", "Balance sheet\nCash 4,835\nCurrent liabilities 6,369", "Item 3"]}


def initial_docs(n=None):
    """Les passages initiaux protégés d'une question (RESEARCH_TOP_K)."""
    from backend.config.settings import settings
    n = settings.CORRECTIVE_PROTECT_TOP if n is None else n
    return [make_doc(f"initial-{i}", source="AMD_2022_10K", page=i) for i in range(n)]
