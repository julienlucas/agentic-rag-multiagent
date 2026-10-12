"""L'API HTTP, avec le client de test Django : OCR, index et pipeline sont remplacés par des faux."""
import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from backend import endpoints  # noqa: E402
from conftest import FakeProcessor, load_example, post_json  # noqa: E402


def test_question_before_any_document_is_a_400(api):
    r = post_json(api, "/api/process-question", {"question": "q", "session_id": "s"})
    assert r.status_code == 400
    assert "Aucun document" in r.json()["error"]


def test_upload_then_question_goes_through_the_pipeline(api, monkeypatch):
    seen = {}

    def full_pipeline(question, retriever, page_store=None):
        seen.update(question=question, retriever=retriever, pages=page_store.page_count("rapport"))
        return {"draft_answer": "réponse [1]", "verification_report": "rapport", "citations": [{"n": 1}]}

    monkeypatch.setattr(endpoints._workflow, "full_pipeline", full_pipeline)
    up = load_example(api, "rapport.pdf", b"%PDF-1.4", "s")
    assert up.status_code == 200 and up.json()["chunks_count"] == 1

    r = post_json(api, "/api/process-question", {"question": "  quel CA ?  ", "session_id": "s"})
    assert r.status_code == 200
    assert r.json() == {"draft_answer": "réponse [1]", "verification_report": "rapport", "citations": [{"n": 1}],
                        "feedback_token": None}  # votes désactivés sans LANGSMITH_API_KEY
    assert seen == {"question": "quel CA ?", "retriever": ("retriever", "demo-s", 1), "pages": 2}


def test_sessions_are_isolated(api, monkeypatch):
    monkeypatch.setattr(endpoints._workflow, "full_pipeline", lambda **k: {"draft_answer": "", "verification_report": ""})
    load_example(api, "a.pdf", b"a", "alice")
    r = post_json(api, "/api/process-question", {"question": "q", "session_id": "bob"})
    assert r.status_code == 400


def test_public_upload_is_gone(api):
    """Déposer ses propres fichiers demande un compte (espace connecté, backend/saas)."""
    assert api.post("/api/upload-file", {"session_id": "s"}).status_code == 404


def test_a_demo_session_never_reaches_an_account_space(api, store):
    """Le tenant de la démo est préfixé : un session_id « ws-… » ne désigne pas l'espace d'un compte."""
    store.for_tenant("ws-abc").add_document("h" * 64, "secret.pdf", [], [])
    assert api.get("/api/documents", {"session_id": "ws-abc"}).json()["documents"] == []


def test_load_file_reads_from_the_examples_dir(api, store):
    r = post_json(api, "/api/load-file", {"file_name": "rapport.pdf", "session_id": "s"})
    assert r.status_code == 200
    assert r.json()["filename"] == "rapport.pdf"
    assert [os.path.basename(src) for src in store.for_tenant("demo-s").sources()] == ["rapport.pdf"]


@pytest.mark.parametrize("name", ["../secret.md", "/etc/hosts", "", "sub/../../secret.md"])
def test_load_file_refuses_paths_outside_the_examples_dir(api, store, name):
    r = post_json(api, "/api/load-file", {"file_name": name, "session_id": "s"})
    assert r.status_code == 400
    assert store.for_tenant("demo-s").documents() == []


def test_documents_accumulate_in_the_space_and_are_not_reprocessed(api, store):
    load_example(api, "a.pdf", b"a", "s")
    load_example(api, "b.pdf", b"b", "s")
    again = load_example(api, "a.pdf", b"a", "s")
    assert again.status_code == 200 and again.json()["message"] == "Document déjà indexé"
    assert FakeProcessor.calls == 2  # pas d'OCR pour un fichier déjà indexé
    listed = api.get("/api/documents", {"session_id": "s"}).json()["documents"]
    assert sorted(d["name"] for d in listed) == ["a.pdf", "b.pdf"]


def test_delete_document_and_space(api):
    load_example(api, "a.pdf", b"a", "s")
    load_example(api, "b.pdf", b"b", "s")
    first = api.get("/api/documents", {"session_id": "s"}).json()["documents"][0]
    assert post_json(api, "/api/delete-document", {"session_id": "other", "file_hash": first["file_hash"]}).status_code == 404
    assert post_json(api, "/api/delete-document", {"session_id": "s", "file_hash": first["file_hash"]}).status_code == 200
    assert len(api.get("/api/documents", {"session_id": "s"}).json()["documents"]) == 1
    assert post_json(api, "/api/delete-space", {"session_id": "s"}).status_code == 200
    assert api.get("/api/documents", {"session_id": "s"}).json()["documents"] == []


def test_invalid_session_id_is_a_400(api):
    r = post_json(api, "/api/process-question", {"question": "q", "session_id": "../x y"})
    assert r.status_code == 400
    r = load_example(api, "a.pdf", b"a", "a b")
    assert r.status_code == 400


def test_pipeline_failure_is_a_json_500(api, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("Mistral indisponible")

    monkeypatch.setattr(endpoints._workflow, "full_pipeline", boom)
    load_example(api, "a.pdf", b"a", "s")
    r = post_json(api, "/api/process-question", {"question": "q", "session_id": "s"})
    assert r.status_code == 500 and "indisponible" in r.json()["error"]


def test_get_on_api_routes_is_rejected(api):
    assert api.get("/api/process-question").status_code == 405


# ── Originaux et ouverture d'une citation ─────────────────────────────────────

def test_a_document_already_indexed_elsewhere_is_copied_without_ocr(api, store):
    load_example(api, "rapport.pdf", b"%PDF meme", "alice")
    calls = FakeProcessor.calls
    r = load_example(api, "rapport.pdf", b"%PDF meme", "bob")
    assert r.status_code == 200 and FakeProcessor.calls == calls
    assert [os.path.basename(src) for src in store.for_tenant("demo-bob").sources()] == ["rapport.pdf"]
    assert list(store.for_tenant("demo-bob").pages().values()) == [["page 1", "page 2"]]


def test_page_text_is_the_fallback_when_the_original_is_missing(api, store):
    load_example(api, "rapport.pdf", b"%PDF-1.4", "alice")
    digest = store.for_tenant("demo-alice").documents()[0]["file_hash"]
    r = api.get("/api/documents/page", {"session_id": "alice", "file_hash": digest, "page": 2})
    assert r.status_code == 200 and r.json()["text"] == "page 2"
    assert api.get("/api/documents/page", {"session_id": "bob", "file_hash": digest, "page": 2}).status_code == 404
    assert api.get("/api/documents/page", {"session_id": "alice", "file_hash": digest, "page": "x"}).status_code == 400


def test_citations_of_an_example_point_to_the_static_pdf(api, monkeypatch):
    monkeypatch.setattr(endpoints._workflow, "full_pipeline", lambda **k: {
        "draft_answer": "CA [1]", "verification_report": "",
        "citations": [{"n": 1, "source": "rapport", "page": 3}],  # page lue par read_page : nom seul
    })
    post_json(api, "/api/load-file", {"file_name": "rapport.pdf", "session_id": "s"})
    c = post_json(api, "/api/process-question", {"question": "q", "session_id": "s"}).json()["citations"][0]
    assert c["pdf_url"] == "/static/rapport.pdf" and len(c["file_hash"]) == 64
