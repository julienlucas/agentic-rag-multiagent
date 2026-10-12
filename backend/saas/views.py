"""
API de l'espace connecté (/api/app/…) et routes publiques du produit. Contrat : docs/api-produit.md.

Le tenant Qdrant vient TOUJOURS de la session (Workspace.tenant_id), jamais du client.
"""
import hashlib
import json
import os
import uuid
from functools import wraps

from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from langsmith import trace

from .. import endpoints
from ..config import constants
from ..document_processor import formats, storage
from ..evals.feedback import votes, votes_dataset
from ..utils.logging import logger
from ..vectorstore import get_store
from . import billing, credits, ingestion, pricing
from .accounts import delete_account, workspace_of
from .models import Conversation, Document, Message

QUESTION_MAX_CHARS = 2000


def _error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def api_login_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _error("Connectez-vous pour continuer.", 401)
        return view(request, workspace_of(request.user), *args, **kwargs)
    return wrapper


def _json(request) -> dict:
    try:
        data = json.loads(request.body or b"{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


# ── Public ─────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def pricing_view(request):
    return JsonResponse(pricing.public())


@ensure_csrf_cookie
@require_http_methods(["GET"])
def me(request):
    if not request.user.is_authenticated:
        return _error("Non connecté.", 401)
    ws = workspace_of(request.user)
    active = ws.documents.exclude(status="error")
    return JsonResponse({
        "user": {"email": request.user.email},
        "workspace": {
            "id": str(ws.id), "plan": ws.plan, "balance": credits.balance(ws),
            "documents_count": active.count(), "pages_count": sum(active.values_list("pages", flat=True)),
            "max_documents": ws.limits["documents"], "max_pages": ws.limits["pages"],
        },
    })


# ── Documents ──────────────────────────────────────────────────────────────────

def _document_json(doc: Document) -> dict:
    return {
        "id": str(doc.id), "name": doc.name, "kind": doc.extension.lstrip("."), "size": doc.size,
        "pages": doc.pages, "status": doc.status, "error": doc.error or None, "credits": doc.credits,
        "created_at": doc.created_at.isoformat(),
        "file_url": f"/api/app/documents/{doc.id}/file" if doc.has_pdf else None,
    }


def _unique_name(name: str, taken: set) -> str:
    base = os.path.basename(name.replace("\\", "/")).strip() or "document"
    stem, ext = os.path.splitext(base)
    stem = stem[:180]
    candidate, n = f"{stem}{ext}", 2
    while candidate in taken:
        candidate, n = f"{stem} ({n}){ext}", n + 1
    return candidate


@require_http_methods(["GET", "POST"])
@api_login_required
def documents(request, ws):
    if request.method == "GET":
        return JsonResponse({"documents": [_document_json(d) for d in ws.documents.all()]})

    files = request.FILES.getlist("files") or request.FILES.getlist("file")
    if not files:
        return _error("Aucun fichier reçu (champ « files »).", 400)

    # 1. Lecture et contrôle de chaque fichier, avant toute écriture.
    incoming = {}
    for f in files:
        if f.size > constants.MAX_FILE_SIZE:
            return _error(f"{f.name} dépasse {constants.MAX_FILE_SIZE // 1024 // 1024} Mo.", 400)
        content = f.read()
        try:
            kind = formats.check(f.name, content)
            pages = formats.estimate_pages(f.name, content)
        except formats.UnsupportedFormat as e:
            return _error(str(e), 400)
        except Exception as e:
            logger.warning(f"Fichier illisible {f.name}: {e}")
            return _error(f"{f.name} est illisible ou endommagé.", 400)
        if pages > formats.MAX_PAGES:
            return _error(f"{f.name} compte {pages} pages ; la limite est de {formats.MAX_PAGES} par fichier.", 400)
        digest = hashlib.sha256(content).hexdigest()
        incoming.setdefault(digest, {"name": f.name, "kind": kind, "pages": pages, "content": content})

    # Déjà dans l'espace : renvoyé tel quel (pas de double facturation), sauf un échec, qu'on relance.
    known = {d.file_hash: d for d in ws.documents.filter(file_hash__in=incoming)}
    failed = [d for d in known.values() if d.status == "error"]
    for d in failed:
        d.delete()
        known.pop(d.file_hash)
    new = {h: v for h, v in incoming.items() if h not in known}

    # 2. Quotas de l'offre.
    limits = ws.limits
    active = ws.documents.exclude(status="error")
    if active.count() + len(new) > limits["documents"]:
        return _error(f"Votre offre permet {limits['documents']} documents. Supprimez-en ou passez à l'offre "
                      f"à la carte.", 403)
    used_pages = sum(active.values_list("pages", flat=True))
    new_pages = sum(v["pages"] for v in new.values())
    if used_pages + new_pages > limits["pages"]:
        return _error(f"Votre offre permet {limits['pages']} pages indexées ({used_pages} utilisées, "
                      f"{new_pages} demandées).", 403)

    # 3. Originaux sur le volume (idempotent par hash), puis documents et réservation, atomiquement.
    for digest, v in new.items():
        storage.save(digest, formats.suffix(v["name"]), v["content"])
        if v["kind"] == "pdf":
            storage.save(digest, ".pdf", v["content"])  # déjà un PDF : c'est aussi la copie du visualiseur
    cost_per_page = 0 if limits["indexing_free"] else pricing.PAGE_CREDITS
    created = []
    try:
        with transaction.atomic():
            needed = sum(v["pages"] for v in new.values()) * cost_per_page
            if needed:
                current = credits.balance(ws)
                if needed > current:
                    raise credits.InsufficientCredits(needed, current)
            taken = set(ws.documents.values_list("name", flat=True))
            for digest, v in new.items():
                name = _unique_name(v["name"], taken)
                taken.add(name)
                doc = Document.objects.create(
                    workspace=ws, name=name, kind=v["kind"], extension=formats.suffix(name), size=len(v["content"]),
                    file_hash=digest, pages=v["pages"], credits=v["pages"] * cost_per_page,
                )
                if doc.credits:
                    credits.charge(ws, doc.credits, "indexing", f"Indexation : {name}", document=doc)
                created.append(doc)
    except credits.InsufficientCredits as e:
        for digest in new:
            ingestion.release_original(digest)
        return _error(f"Crédits insuffisants : l'indexation coûte {e.needed} crédits, il vous en reste "
                      f"{e.balance}.", 402)

    ingestion.notify()
    if created:
        logger.info(f"[{ws.tenant_id}] {len(created)} document(s) en file, {sum(d.pages for d in created)} pages")
    docs = created + list(known.values())
    return JsonResponse({"documents": [_document_json(d) for d in docs], "balance": credits.balance(ws)})


def _document_of(ws, document_id):
    try:
        return ws.documents.get(pk=uuid.UUID(str(document_id)))
    except (ValueError, Document.DoesNotExist):
        return None


@require_http_methods(["DELETE"])
@api_login_required
def document_detail(request, ws, document_id):
    doc = _document_of(ws, document_id)
    if doc is None:
        return _error("Document inconnu.", 404)
    get_store().for_tenant(ws.tenant_id).delete_document(doc.file_hash)
    digest = doc.file_hash
    doc.delete()
    ingestion.release_original(digest)
    return JsonResponse({"ok": True})


@require_http_methods(["GET"])
@api_login_required
def document_file(request, ws, document_id):
    doc = _document_of(ws, document_id)
    path = storage.find_pdf(doc.file_hash) if doc and doc.has_pdf else None
    if path is None:
        return _error("Aperçu indisponible pour ce document.", 404)
    response = FileResponse(open(path, "rb"), content_type="application/pdf", as_attachment=False)
    response["Content-Disposition"] = "inline"
    response["Cache-Control"] = "private, max-age=3600"
    return response


@require_http_methods(["GET"])
@api_login_required
def document_page(request, ws):
    doc = _document_of(ws, request.GET.get("document"))
    try:
        page = int(request.GET.get("page", ""))
    except ValueError:
        return _error("page doit être un entier.", 400)
    text = get_store().for_tenant(ws.tenant_id).page_text(doc.file_hash, page - 1) if doc and page >= 1 else None
    if text is None:
        return _error("Page introuvable.", 404)
    return JsonResponse({"page": page, "text": text})


# ── Chat ───────────────────────────────────────────────────────────────────────

def _locate_citations(citations, ws):
    """Rattache chaque citation au document de l'espace, pour l'ouvrir à la page citée."""
    docs = list(ws.documents.filter(status="ready"))
    by_hash = {d.file_hash: d for d in docs}
    by_stem = {os.path.splitext(d.name)[0]: d for d in docs}
    by_stem.update({d.name: d for d in docs})
    for c in citations:
        doc = by_hash.get(c.get("file_hash") or "") or by_stem.get(c.get("source") or "")
        c["pdf_url"] = None
        if doc is None:
            continue
        c["file_hash"] = doc.file_hash
        c["document_id"] = str(doc.id)
        if doc.has_pdf:
            c["pdf_url"] = f"/api/app/documents/{doc.id}/file"
    return citations


def _message_json(m: Message, ws) -> dict:
    return {
        "id": str(m.id), "question": m.question, "answer": m.answer,
        "verification_report": m.verification_report, "citations": m.citations, "credits": m.credits,
        "created_at": m.created_at.isoformat(),
        "feedback_token": votes.issue_token(m.run_id, ws.tenant_id) if (m.run_id and votes.enabled()) else None,
    }


@require_http_methods(["POST"])
@api_login_required
def ask(request, ws):
    data = _json(request)
    question = (data.get("question") or "").strip()
    if not question:
        return _error("La question est vide.", 400)
    if len(question) > QUESTION_MAX_CHARS:
        return _error(f"Question limitée à {QUESTION_MAX_CHARS} caractères.", 400)

    tenant = get_store().for_tenant(ws.tenant_id)
    indexed = tenant.documents()
    if not indexed:
        return _error("Aucun document prêt. Déposez d'abord un document dans « Documents ».", 400)

    conversation = None
    if data.get("conversation_id"):
        try:
            conversation = ws.conversations.get(pk=uuid.UUID(str(data["conversation_id"])))
        except (ValueError, Conversation.DoesNotExist):
            return _error("Conversation inconnue.", 404)

    run_id = uuid.uuid4()
    try:
        credits.charge(ws, pricing.QUESTION_CREDITS, "question", question[:120], reference=str(run_id))
    except credits.InsufficientCredits as e:
        return _error(f"Crédits insuffisants : une question coûte {e.needed} crédits, il vous en reste "
                      f"{e.balance}.", 402)

    try:
        with trace(
            "question", "chain", run_id=run_id, inputs={"question": question},
            metadata={
                "tenant_id": ws.tenant_id,
                "documents": [d["file_hash"] for d in indexed],
                "document_names": [os.path.basename(d["source"]) for d in indexed],
            },
        ) as run:
            result = endpoints._workflow.full_pipeline(
                question=question,
                retriever=endpoints.RetrieverBuilder().build_hybrid_retriever(tenant),
                page_store=endpoints._page_store(tenant, indexed),
            )
            run.end(outputs=result)
    except Exception as e:
        logger.error(f"[{ws.tenant_id}] Question en échec : {e}")
        credits.refund(ws, pricing.QUESTION_CREDITS, "Question en échec", reference=str(run_id))
        return _error("La réponse n'a pas pu être produite. Vos crédits ont été rendus ; réessayez.", 500)

    if conversation is None:
        conversation = Conversation.objects.create(workspace=ws, title=question[:120])
    message = Message.objects.create(
        conversation=conversation, question=question, answer=result.get("draft_answer", ""),
        verification_report=result.get("verification_report", ""),
        citations=_locate_citations(result.get("citations", []), ws),
        credits=pricing.QUESTION_CREDITS, run_id=run_id,
    )
    conversation.save(update_fields=["updated_at"])
    return JsonResponse({"conversation_id": str(conversation.id), "message": _message_json(message, ws),
                         "balance": credits.balance(ws)})


@require_http_methods(["GET"])
@api_login_required
def conversations(request, ws):
    return JsonResponse({"conversations": [
        {"id": str(c.id), "title": c.title, "updated_at": c.updated_at.isoformat()}
        for c in ws.conversations.all()[:100]
    ]})


@require_http_methods(["GET", "DELETE"])
@api_login_required
def conversation_detail(request, ws, conversation_id):
    try:
        conversation = ws.conversations.get(pk=uuid.UUID(str(conversation_id)))
    except (ValueError, Conversation.DoesNotExist):
        return _error("Conversation inconnue.", 404)
    if request.method == "DELETE":
        conversation.delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"id": str(conversation.id), "title": conversation.title,
                         "messages": [_message_json(m, ws) for m in conversation.messages.all()]})


@require_http_methods(["POST"])
@api_login_required
def feedback(request, ws):
    data = _json(request)
    score = data.get("score")
    comment = (data.get("comment") or "").strip()
    if not votes.enabled():
        return _error("Les votes ne sont pas activés sur ce serveur.", 503)
    if score not in (0, 1) or isinstance(score, bool):
        return _error("score doit valoir 0 ou 1.", 400)
    if len(comment) > votes.COMMENT_MAX_CHARS:
        return _error(f"Commentaire limité à {votes.COMMENT_MAX_CHARS} caractères.", 400)
    try:
        run_id = votes.read_token(data.get("feedback_token") or "", ws.tenant_id)
    except votes.InvalidFeedback as e:
        return _error(str(e), 400)
    try:
        votes.send(run_id, score, comment)
    except Exception as e:
        logger.error(f"Envoi du vote à LangSmith impossible: {e}")
        return _error("Vote non enregistré, réessayez plus tard.", 502)
    votes_dataset.collect_in_background(run_id, score, comment)
    return JsonResponse({"message": "Merci pour votre retour"})


# ── Crédits et paiement ────────────────────────────────────────────────────────

@require_http_methods(["GET"])
@api_login_required
def credits_view(request, ws):
    entries = ws.credit_entries.all()[:100]
    return JsonResponse({"balance": credits.balance(ws), "billing_enabled": billing.enabled(), "entries": [
        {"id": e.id, "delta": e.delta, "reason": e.reason, "label": e.label or e.get_reason_display(),
         "created_at": e.created_at.isoformat()}
        for e in entries
    ]})


def _frontend_url(request) -> str:
    from ..config.settings import settings
    if settings.FRONTEND_URL:
        return settings.FRONTEND_URL.rstrip("/")
    origin = request.headers.get("Origin")
    return origin.rstrip("/") if origin else f"{request.scheme}://{request.get_host()}"


@require_http_methods(["POST"])
@api_login_required
def checkout(request, ws):
    pack = _json(request).get("pack", "")
    try:
        url = billing.create_checkout(ws, request.user.email, pack, _frontend_url(request))
    except billing.BillingDisabled as e:
        return _error(str(e), 503)
    except ValueError as e:
        return _error(str(e), 400)
    except Exception as e:
        logger.error(f"Stripe Checkout : {e}")
        return _error("Le paiement n'a pas pu démarrer, réessayez.", 502)
    return JsonResponse({"url": url})


@csrf_exempt  # appelé par Stripe, authentifié par la signature
@require_http_methods(["POST"])
def stripe_webhook(request):
    try:
        billing.handle_webhook(request.body, request.headers.get("Stripe-Signature", ""))
    except billing.BillingDisabled as e:
        return _error(str(e), 503)
    except ValueError as e:
        return _error(str(e), 400)
    return JsonResponse({"ok": True})


# ── Compte ─────────────────────────────────────────────────────────────────────

@require_http_methods(["DELETE"])
@api_login_required
def account(request, ws):
    from django.contrib.auth import logout
    user = request.user
    logout(request)
    delete_account(user)
    return JsonResponse({"ok": True})
