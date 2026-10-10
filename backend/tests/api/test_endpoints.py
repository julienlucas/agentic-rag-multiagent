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
