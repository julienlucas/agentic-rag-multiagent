"""Espace connecté : comptes, documents, ingestion, crédits, chat, isolation, paiement."""
import io
import json
import os
import uuid

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django  # noqa: E402

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client  # noqa: E402

from backend import endpoints  # noqa: E402
from backend.saas import billing, credits, ingestion, pricing  # noqa: E402
from backend.saas.models import CreditEntry, Document, Purchase, Workspace  # noqa: E402
from conftest import FakeBuilder, FakeProcessor, post_json  # noqa: E402


def pdf_bytes(pages: int) -> bytes:
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def app(db, store, monkeypatch, tmp_path):
    from backend.config.settings import settings
    FakeProcessor.calls = 0
    monkeypatch.setattr(ingestion, "DocumentProcessor", FakeProcessor)
    monkeypatch.setattr(endpoints, "RetrieverBuilder", FakeBuilder)
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", str(tmp_path / "originals"))
    monkeypatch.setattr(ingestion, "notify", lambda: None)
    return store


def login(email="alice@example.com", plan="free"):
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.create_user(username=email, email=email, password="motdepasse-solide")
    Workspace.objects.filter(owner=user).update(plan=plan)
    client = Client()
    client.force_login(user)
    return client, Workspace.objects.get(owner=user)


def upload(client, *files):
    return client.post("/api/app/documents", {"files": [SimpleUploadedFile(n, c) for n, c in files]})


def run_queue():
    while (doc := ingestion.claim()) is not None:
        ingestion.ingest(doc)


# ── Comptes ────────────────────────────────────────────────────────────────────

def test_a_new_account_gets_a_workspace_and_welcome_credits(app):
    client, ws = login()
    me = client.get("/api/me").json()
    assert me["user"]["email"] == "alice@example.com"
    assert me["workspace"]["balance"] == pricing.WELCOME_CREDITS
    assert me["workspace"]["plan"] == "free" and me["workspace"]["max_documents"] == 20
    assert ws.tenant_id.startswith("ws-")


def test_app_routes_require_a_session(app):
    anonymous = Client()
    assert anonymous.get("/api/me").status_code == 401
    assert "csrftoken" in anonymous.cookies  # posé même sans session, pour le formulaire de connexion
    for url in ("/api/app/documents", "/api/app/credits", "/api/app/conversations"):
        assert anonymous.get(url).status_code == 401
    assert post_json(anonymous, "/api/app/ask", {"question": "q"}).status_code == 401


def test_pricing_is_public(app):
    p = Client().get("/api/pricing").json()
    assert p["question_credits"] == 20 and p["free"]["documents"] == 20 and ".pdf" in p["formats"]


# ── Documents et ingestion ─────────────────────────────────────────────────────

def test_free_upload_is_queued_then_indexed_without_charge(app):
    client, ws = login()
    r = upload(client, ("notes.txt", "Le chiffre d'affaires 2024 est de 12 M€.".encode()))
    assert r.status_code == 200
    doc = r.json()["documents"][0]
    assert doc["status"] == "queued" and doc["pages"] == 1 and doc["credits"] == 0
    assert r.json()["balance"] == pricing.WELCOME_CREDITS  # indexation offerte en gratuit

    run_queue()
    doc = client.get("/api/app/documents").json()["documents"][0]
    assert doc["status"] == "ready" and doc["pages"] == 2  # FakeProcessor : deux pages
    assert doc["file_url"] is None  # un .txt ne s'ouvre pas en PDF : repli sur le texte de la page
    assert app.for_tenant(ws.tenant_id).sources() == ["notes.txt"]


def test_paid_upload_reserves_pages_then_settles_on_the_real_count(app):
    client, ws = login(plan="paid")
    r = upload(client, ("rapport.pdf", pdf_bytes(3)))
    assert r.json()["documents"][0]["credits"] == 3
    assert r.json()["balance"] == pricing.WELCOME_CREDITS - 3
    run_queue()  # FakeProcessor rend 2 pages : 1 crédit rendu
    doc = Document.objects.get(workspace=ws)
    assert doc.credits == 2 and doc.has_pdf
    assert credits.balance(ws) == pricing.WELCOME_CREDITS - 2


def test_upload_without_enough_credits_creates_nothing(app):
    client, ws = login(plan="paid")
    credits.charge(ws, pricing.WELCOME_CREDITS - 2, "question")
    r = upload(client, ("rapport.pdf", pdf_bytes(3)))
    assert r.status_code == 402 and "3 crédits" in r.json()["error"]
    assert not Document.objects.filter(workspace=ws).exists()


def test_the_same_file_is_never_charged_twice(app):
    client, ws = login(plan="paid")
    upload(client, ("a.pdf", pdf_bytes(2)))
    again = upload(client, ("copie.pdf", pdf_bytes(2)))
    assert again.status_code == 200 and again.json()["documents"][0]["name"] == "a.pdf"
    assert Document.objects.filter(workspace=ws).count() == 1
    assert credits.balance(ws) == pricing.WELCOME_CREDITS - 2


def test_two_files_with_the_same_name_are_kept_apart(app):
    client, ws = login()
    upload(client, ("notes.txt", b"version une"))
    upload(client, ("notes.txt", b"version deux"))
    run_queue()
    names = sorted(Document.objects.filter(workspace=ws).values_list("name", flat=True))
    assert names == ["notes (2).txt", "notes.txt"]
    assert len(app.for_tenant(ws.tenant_id).documents()) == 2


def test_plan_quotas_are_enforced(app, monkeypatch):
    monkeypatch.setitem(pricing.PLANS, "free", {**pricing.PLANS["free"], "documents": 1})
    client, _ = login()
    assert upload(client, ("a.txt", b"un")).status_code == 200
    r = upload(client, ("b.txt", b"deux"))
    assert r.status_code == 403 and "1 documents" in r.json()["error"]


def test_unsupported_or_disguised_files_are_refused(app):
    client, _ = login()
    assert upload(client, ("virus.exe", b"MZ")).status_code == 400
    r = upload(client, ("faux.pdf", b"ceci n'est pas un pdf"))
    assert r.status_code == 400 and "ne correspond pas" in r.json()["error"]


def test_a_failed_ingestion_refunds_its_credits(app, monkeypatch):
    client, ws = login(plan="paid")

    class Broken(FakeProcessor):
        def process(self, files):
            raise RuntimeError("OCR indisponible")

    monkeypatch.setattr(ingestion, "DocumentProcessor", Broken)
    upload(client, ("rapport.pdf", pdf_bytes(4)))
    run_queue()
    doc = Document.objects.get(workspace=ws)
    assert doc.status == "error" and doc.credits == 0 and "OCR indisponible" in doc.error
    assert credits.balance(ws) == pricing.WELCOME_CREDITS
    # Un nouveau dépôt du même fichier relance l'indexation.
    assert upload(client, ("rapport.pdf", pdf_bytes(4))).json()["documents"][0]["status"] == "queued"


def test_a_file_indexed_by_another_account_is_copied_without_ocr(app):
    alice, _ = login("alice@example.com")
    bob, bob_ws = login("bob@example.com")
    upload(alice, ("rapport.pdf", pdf_bytes(2)))
    run_queue()
    upload(bob, ("mon-rapport.pdf", pdf_bytes(2)))
    run_queue()
    assert FakeProcessor.calls == 1
    assert app.for_tenant(bob_ws.tenant_id).sources() == ["mon-rapport.pdf"]
    assert Document.objects.get(workspace=bob_ws).status == "ready"


# ── Isolation ──────────────────────────────────────────────────────────────────

def test_another_account_cannot_read_or_delete_a_document(app):
    alice, _ = login("alice@example.com")
    bob, _ = login("bob@example.com")
    upload(alice, ("rapport.pdf", pdf_bytes(2)))
    run_queue()
    doc_id = alice.get("/api/app/documents").json()["documents"][0]["id"]

    r = alice.get(f"/api/app/documents/{doc_id}/file")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert alice.get("/api/app/documents/page", {"document": doc_id, "page": 2}).json()["text"] == "page 2"

    assert bob.get(f"/api/app/documents/{doc_id}/file").status_code == 404
    assert bob.get("/api/app/documents/page", {"document": doc_id, "page": 2}).status_code == 404
    assert bob.delete(f"/api/app/documents/{doc_id}").status_code == 404
    assert bob.get("/api/app/documents").json()["documents"] == []


def test_deleting_the_last_copy_removes_the_original(app):
    from backend.document_processor import storage
    alice, _ = login("alice@example.com")
    bob, _ = login("bob@example.com")
    for client in (alice, bob):
        upload(client, ("a.pdf", pdf_bytes(1)))
    run_queue()
    digest = Document.objects.first().file_hash
    alice.delete(f"/api/app/documents/{alice.get('/api/app/documents').json()['documents'][0]['id']}")
    assert storage.find(digest) is not None  # bob l'a encore
    bob.delete(f"/api/app/documents/{bob.get('/api/app/documents').json()['documents'][0]['id']}")
    assert storage.find(digest) is None


# ── Chat ───────────────────────────────────────────────────────────────────────

def _answer(**kwargs):
    return {"draft_answer": "12 M€ [1]", "verification_report": "ok",
            "citations": [{"n": 1, "source": "rapport", "page": 0, "excerpt": "12 M€"}]}


def test_a_question_costs_credits_and_is_kept_in_a_conversation(app, monkeypatch):
    monkeypatch.setattr(endpoints._workflow, "full_pipeline", _answer)
    client, ws = login()
    upload(client, ("rapport.pdf", pdf_bytes(1)))
    run_queue()

    r = post_json(client, "/api/app/ask", {"question": "Quel CA ?"})
    assert r.status_code == 200
    body = r.json()
    assert body["balance"] == pricing.WELCOME_CREDITS - pricing.QUESTION_CREDITS
    citation = body["message"]["citations"][0]
    doc = Document.objects.get(workspace=ws)
    assert citation["pdf_url"] == f"/api/app/documents/{doc.id}/file" and citation["file_hash"] == doc.file_hash

    follow = post_json(client, "/api/app/ask", {"question": "Et en 2023 ?", "conversation_id": body["conversation_id"]})
    assert follow.json()["conversation_id"] == body["conversation_id"]
    conv = client.get(f"/api/app/conversations/{body['conversation_id']}").json()
    assert [m["question"] for m in conv["messages"]] == ["Quel CA ?", "Et en 2023 ?"]
    assert client.get("/api/app/conversations").json()["conversations"][0]["title"] == "Quel CA ?"


def test_a_failed_question_is_refunded(app, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("Bedrock indisponible")

    monkeypatch.setattr(endpoints._workflow, "full_pipeline", boom)
    client, ws = login()
    upload(client, ("a.txt", b"texte"))
    run_queue()
    r = post_json(client, "/api/app/ask", {"question": "q"})
    assert r.status_code == 500 and "rendus" in r.json()["error"]
    assert credits.balance(ws) == pricing.WELCOME_CREDITS


def test_no_question_without_credits_or_documents(app, monkeypatch):
    monkeypatch.setattr(endpoints._workflow, "full_pipeline", _answer)
    client, ws = login()
    assert post_json(client, "/api/app/ask", {"question": "q"}).status_code == 400  # aucun document prêt
    upload(client, ("a.txt", b"texte"))
    run_queue()
    credits.charge(ws, pricing.WELCOME_CREDITS - 5, "question")
    r = post_json(client, "/api/app/ask", {"question": "q"})
    assert r.status_code == 402 and "20 crédits" in r.json()["error"]


def test_a_conversation_of_another_account_is_unreachable(app, monkeypatch):
    monkeypatch.setattr(endpoints._workflow, "full_pipeline", _answer)
    alice, _ = login("alice@example.com")
    bob, _ = login("bob@example.com")
    upload(alice, ("a.txt", b"texte"))
    run_queue()
    conv_id = post_json(alice, "/api/app/ask", {"question": "q"}).json()["conversation_id"]
    assert bob.get(f"/api/app/conversations/{conv_id}").status_code == 404
    upload(bob, ("b.txt", b"autre"))
    run_queue()
    assert post_json(bob, "/api/app/ask", {"question": "q", "conversation_id": conv_id}).status_code == 404


# ── Crédits, paiement, compte ──────────────────────────────────────────────────

def test_credit_statement_lists_every_movement(app):
    client, ws = login()
    credits.charge(ws, 20, "question", "Quel CA ?")
    entries = client.get("/api/app/credits").json()["entries"]
    assert [(e["delta"], e["reason"]) for e in entries] == [(-20, "question"), (300, "welcome")]


def test_checkout_is_unavailable_without_stripe(app):
    client, _ = login()
    assert post_json(client, "/api/app/checkout", {"pack": "pack_10"}).status_code == 503


def test_a_paid_checkout_credits_once_and_upgrades_the_plan(app):
    _, ws = login()
    Purchase.objects.create(workspace=ws, pack="pack_25", price_eur=25, credits=2600, stripe_session_id="cs_test_1")
    assert billing.fulfill("cs_test_1") is True
    assert billing.fulfill("cs_test_1") is False  # webhook rejoué
    ws.refresh_from_db()
    assert ws.plan == "paid" and credits.balance(ws) == pricing.WELCOME_CREDITS + 2600


def test_deleting_the_account_erases_everything(app):
    from backend.document_processor import storage
    client, ws = login()
    upload(client, ("a.pdf", pdf_bytes(1)))
    run_queue()
    digest, tenant_id = Document.objects.get(workspace=ws).file_hash, ws.tenant_id
    assert client.delete("/api/app/account").json() == {"ok": True}
    assert not Workspace.objects.filter(pk=ws.pk).exists() and not CreditEntry.objects.exists()
    assert app.for_tenant(tenant_id).documents() == [] and storage.find(digest) is None
    assert client.get("/api/me").status_code == 401


def test_a_vote_from_the_app_is_bound_to_the_workspace(app, monkeypatch):
    from backend.config.settings import settings
    from backend.evals.feedback import votes, votes_dataset
    sent = []
    monkeypatch.setattr(settings, "LANGSMITH_API_KEY", "ls-test")
    monkeypatch.setattr(votes, "send", lambda run_id, score, comment=None: sent.append(score))
    monkeypatch.setattr(votes_dataset, "collect_in_background", lambda *a: None)
    monkeypatch.setattr(endpoints._workflow, "full_pipeline", _answer)
    alice, _ = login("alice@example.com")
    bob, _ = login("bob@example.com")
    upload(alice, ("a.txt", b"texte"))
    run_queue()
    token = post_json(alice, "/api/app/ask", {"question": "q"}).json()["message"]["feedback_token"]
    assert post_json(bob, "/api/app/feedback", {"feedback_token": token, "score": 1}).status_code == 400
    assert post_json(alice, "/api/app/feedback", {"feedback_token": token, "score": 1}).status_code == 200
    assert sent == [1]


def test_a_stale_processing_document_goes_back_to_the_queue(app):
    from datetime import timedelta
    from django.utils import timezone
    client, ws = login()
    upload(client, ("a.txt", b"texte"))
    doc = ingestion.claim()
    Document.objects.filter(pk=doc.pk).update(updated_at=timezone.now() - timedelta(hours=1))
    ingestion._requeue_stale()
    assert Document.objects.get(pk=doc.pk).status == "queued"


def test_unknown_ids_are_404_not_500(app):
    client, _ = login()
    assert client.delete(f"/api/app/documents/{uuid.uuid4()}").status_code == 404
    assert client.delete("/api/app/documents/pas-un-uuid").status_code == 404
    assert client.get("/api/app/conversations/pas-un-uuid").status_code == 404
    assert json.loads(client.get("/api/app/documents/page", {"document": "x", "page": 1}).content)["error"]


# ── Parcours d'authentification réel (allauth headless, client « browser ») ────

def _code_from(mail):
    import re
    return re.search(r"^\s*([A-Z0-9]{4}-?[A-Z0-9]{4})\s*$", mail.body, re.M).group(1)


def test_signup_verify_by_code_then_login(app):
    from django.core import mail
    client = Client(enforce_csrf_checks=True)
    client.get("/api/me")  # pose le cookie csrftoken
    csrf = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
    base = "/_allauth/browser/v1/auth"

    r = client.post(f"{base}/signup", json.dumps({"email": "Carla@Example.com", "password": "un-mot-de-passe-long"}),
                    content_type="application/json", **csrf)
    assert r.status_code == 401
    assert any(f["id"] == "verify_email" and f.get("is_pending") for f in r.json()["data"]["flows"])
    assert client.get("/api/me").status_code == 401  # pas de session avant la vérification

    code = _code_from(mail.outbox[-1])
    r = client.post(f"{base}/email/verify", json.dumps({"key": code}), content_type="application/json", **csrf)
    assert r.status_code == 200
    csrf = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}  # renouvelé à la connexion
    me = client.get("/api/me").json()
    assert me["user"]["email"].lower() == "carla@example.com" and me["workspace"]["balance"] == 300

    assert client.delete(f"{base}/session", **csrf).status_code == 401  # déconnecté
    r = client.post(f"{base}/login", json.dumps({"email": "carla@example.com", "password": "un-mot-de-passe-long"}),
                    content_type="application/json", **{"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value})
    assert r.status_code == 200 and client.get("/api/me").status_code == 200


def test_app_writes_require_the_csrf_token(app):
    client, _ = login()
    strict = Client(enforce_csrf_checks=True)
    strict.cookies = client.cookies
    assert post_json(strict, "/api/app/ask", {"question": "q"}).status_code == 403
