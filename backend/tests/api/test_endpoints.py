"""L'API HTTP, avec le client de test Django : OCR, index et pipeline sont remplacés par des faux."""
import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

from backend import endpoints  # noqa: E402
from conftest import FakeProcessor, post_json  # noqa: E402


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
    up = api.post("/api/upload-file", {"file": SimpleUploadedFile("rapport.pdf", b"%PDF-1.4"), "session_id": "s"})
    assert up.status_code == 200 and up.json()["chunks_count"] == 1

    r = post_json(api, "/api/process-question", {"question": "  quel CA ?  ", "session_id": "s"})
    assert r.status_code == 200
    assert r.json() == {"draft_answer": "réponse [1]", "verification_report": "rapport", "citations": [{"n": 1}],
                        "feedback_token": None}  # votes désactivés sans LANGSMITH_API_KEY
    assert seen == {"question": "quel CA ?", "retriever": ("retriever", "s", 1), "pages": 2}


def test_sessions_are_isolated(api, monkeypatch):
    monkeypatch.setattr(endpoints._workflow, "full_pipeline", lambda **k: {"draft_answer": "", "verification_report": ""})
    api.post("/api/upload-file", {"file": SimpleUploadedFile("a.pdf", b"a"), "session_id": "alice"})
    r = post_json(api, "/api/process-question", {"question": "q", "session_id": "bob"})
    assert r.status_code == 400


def test_upload_rejects_unsupported_types_and_missing_file(api):
    r = api.post("/api/upload-file", {"file": SimpleUploadedFile("x.exe", b"MZ"), "session_id": "s"})
    assert r.status_code == 400 and "non supporté" in r.json()["error"]
    assert api.post("/api/upload-file", {"session_id": "s"}).status_code == 400


def test_load_file_reads_from_the_examples_dir(api, store):
    r = post_json(api, "/api/load-file", {"file_name": "rapport.pdf", "session_id": "s"})
    assert r.status_code == 200
    assert r.json()["filename"] == "rapport.pdf"
    assert [os.path.basename(src) for src in store.for_tenant("s").sources()] == ["rapport.pdf"]


@pytest.mark.parametrize("name", ["../secret.md", "/etc/hosts", "", "sub/../../secret.md"])
def test_load_file_refuses_paths_outside_the_examples_dir(api, store, name):
    r = post_json(api, "/api/load-file", {"file_name": name, "session_id": "s"})
    assert r.status_code == 400
    assert store.for_tenant("s").documents() == []


def test_documents_accumulate_in_the_space_and_are_not_reprocessed(api, store):
    api.post("/api/upload-file", {"file": SimpleUploadedFile("a.pdf", b"a"), "session_id": "s"})
    api.post("/api/upload-file", {"file": SimpleUploadedFile("b.pdf", b"b"), "session_id": "s"})
    again = api.post("/api/upload-file", {"file": SimpleUploadedFile("a.pdf", b"a"), "session_id": "s"})
    assert again.status_code == 200 and again.json()["message"] == "Document déjà indexé"
    assert FakeProcessor.calls == 2  # pas d'OCR pour un fichier déjà indexé
    listed = api.get("/api/documents", {"session_id": "s"}).json()["documents"]
    assert sorted(d["name"] for d in listed) == ["a.pdf", "b.pdf"]


def test_delete_document_and_space(api):
    api.post("/api/upload-file", {"file": SimpleUploadedFile("a.pdf", b"a"), "session_id": "s"})
    api.post("/api/upload-file", {"file": SimpleUploadedFile("b.pdf", b"b"), "session_id": "s"})
    first = api.get("/api/documents", {"session_id": "s"}).json()["documents"][0]
    assert post_json(api, "/api/delete-document", {"session_id": "other", "file_hash": first["file_hash"]}).status_code == 404
    assert post_json(api, "/api/delete-document", {"session_id": "s", "file_hash": first["file_hash"]}).status_code == 200
    assert len(api.get("/api/documents", {"session_id": "s"}).json()["documents"]) == 1
    assert post_json(api, "/api/delete-space", {"session_id": "s"}).status_code == 200
    assert api.get("/api/documents", {"session_id": "s"}).json()["documents"] == []


def test_invalid_session_id_is_a_400(api):
    r = post_json(api, "/api/process-question", {"question": "q", "session_id": "../x y"})
    assert r.status_code == 400
    r = api.post("/api/upload-file", {"file": SimpleUploadedFile("a.pdf", b"a"), "session_id": "a b"})
    assert r.status_code == 400


def test_pipeline_failure_is_a_json_500(api, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("Mistral indisponible")

    monkeypatch.setattr(endpoints._workflow, "full_pipeline", boom)
    api.post("/api/upload-file", {"file": SimpleUploadedFile("a.pdf", b"a"), "session_id": "s"})
    r = post_json(api, "/api/process-question", {"question": "q", "session_id": "s"})
    assert r.status_code == 500 and "indisponible" in r.json()["error"]


def test_get_on_api_routes_is_rejected(api):
    assert api.get("/api/process-question").status_code == 405


# ── Originaux et ouverture d'une citation ─────────────────────────────────────

def _chunk_metadata(store, tenant_id):
    flt = store.for_tenant(tenant_id)._filter()
    records, _ = store._client.scroll(store.chunks, scroll_filter=flt, limit=10, with_payload=True)
    return [r.payload["metadata"] for r in records]


def test_upload_keeps_the_original_and_links_it_from_the_chunks(api, store):
    pdf = b"%PDF-1.4 rapport annuel"
    api.post("/api/upload-file", {"file": SimpleUploadedFile("rapport.pdf", pdf), "session_id": "alice"})
    digest = store.for_tenant("alice").documents()[0]["file_hash"]

    meta = _chunk_metadata(store, "alice")[0]
    assert meta["file_hash"] == digest and meta["pdf_url"] == f"/api/documents/{digest}/file"

    r = api.get(f"/api/documents/{digest}/file", {"session_id": "alice"})
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert b"".join(r.streaming_content) == pdf
    # Un autre espace ne lit pas l'original, même en connaissant son hash.
    assert api.get(f"/api/documents/{digest}/file", {"session_id": "bob"}).status_code == 404


def test_a_document_already_indexed_elsewhere_is_copied_without_ocr(api, store):
    api.post("/api/upload-file", {"file": SimpleUploadedFile("rapport.pdf", b"%PDF meme"), "session_id": "alice"})
    calls = FakeProcessor.calls
    r = api.post("/api/upload-file", {"file": SimpleUploadedFile("rapport.pdf", b"%PDF meme"), "session_id": "bob"})
    assert r.status_code == 200 and FakeProcessor.calls == calls
    assert store.for_tenant("bob").sources() == ["rapport.pdf"]
    assert store.for_tenant("bob").pages() == {"rapport.pdf": ["page 1", "page 2"]}


def test_page_text_is_the_fallback_when_the_original_is_missing(api, store):
    api.post("/api/upload-file", {"file": SimpleUploadedFile("rapport.pdf", b"%PDF-1.4"), "session_id": "alice"})
    digest = store.for_tenant("alice").documents()[0]["file_hash"]
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


def test_deleting_the_last_copy_removes_the_original(api, store):
    from backend.document_processor import storage
    api.post("/api/upload-file", {"file": SimpleUploadedFile("a.pdf", b"%PDF a"), "session_id": "alice"})
    api.post("/api/upload-file", {"file": SimpleUploadedFile("a.pdf", b"%PDF a"), "session_id": "bob"})
    digest = store.for_tenant("alice").documents()[0]["file_hash"]

    post_json(api, "/api/delete-document", {"session_id": "alice", "file_hash": digest})
    assert storage.find(digest) is not None  # bob l'indexe encore
    post_json(api, "/api/delete-space", {"session_id": "bob"})
    assert storage.find(digest) is None
