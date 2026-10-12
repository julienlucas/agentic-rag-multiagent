"""
Ingestion des documents déposés : OCR (ou lecture directe) → chunks → embeddings → Qdrant.

La file est la table Document elle-même (status = queued). Une boucle de fond, lancée dans le
service web (apps.SaasConfig.ready), la dépile : pas de worker séparé, car un volume Railway ne
s'attache qu'à un seul service et l'ingestion lit les originaux sur ce volume.

- Plusieurs processus web peuvent tourner : un document est réservé par
  SELECT … FOR UPDATE SKIP LOCKED (Postgres), jamais traité deux fois.
- Un redémarrage pendant un traitement laisse le document « processing » : passé
  STALE_AFTER sans nouvelle, il repart en file (au plus MAX_ATTEMPTS fois).
- Les crédits sont réservés au dépôt (views.upload) ; ici on les ajuste aux pages réelles,
  ou on les rend si l'indexation échoue.
"""
import io
import os
import threading
import time
from datetime import timedelta

from django.db import close_old_connections, transaction
from django.utils import timezone

from ..config.settings import settings
from ..document_processor import formats, storage
from ..document_processor.file_handler import DocumentProcessor
from ..utils.logging import logger
from ..vectorstore import get_store
from . import credits, pricing
from .models import Document

STALE_AFTER = timedelta(minutes=30)
MAX_ATTEMPTS = 3
IDLE_WAIT = 5  # secondes entre deux lectures de la file vide

_wake = threading.Event()
_started = False
_start_lock = threading.Lock()


def notify():
    """Réveille les boucles : un document vient d'entrer en file."""
    _wake.set()


def start():
    """Lance les boucles d'ingestion de ce processus (une seule fois)."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
    for i in range(max(1, settings.INGESTION_CONCURRENCY)):
        threading.Thread(target=_loop, name=f"ingestion-{i}", daemon=True).start()
    logger.info(f"Ingestion : {settings.INGESTION_CONCURRENCY} boucle(s) de fond démarrée(s)")


def _loop():
    while True:
        try:
            close_old_connections()
            _requeue_stale()
            doc = claim()
            if doc is None:
                _wake.wait(IDLE_WAIT)
                _wake.clear()
                continue
            ingest(doc)
        except Exception as e:  # la boucle ne meurt jamais
            logger.error(f"Ingestion : erreur de la boucle ({e})")
            time.sleep(IDLE_WAIT)


def _requeue_stale():
    limit = timezone.now() - STALE_AFTER
    stale = Document.objects.filter(status="processing", updated_at__lt=limit)
    stale.filter(attempts__lt=MAX_ATTEMPTS).update(status="queued")
    for doc in stale.filter(attempts__gte=MAX_ATTEMPTS):
        _fail(doc, "Le traitement a été interrompu trop de fois.")


def claim():
    """Réserve le plus ancien document en file, ou None."""
    with transaction.atomic():
        doc = (Document.objects.select_for_update(skip_locked=True)
               .filter(status="queued").order_by("created_at").first())
        if doc is None:
            return None
        doc.status = "processing"
        doc.attempts += 1
        doc.save(update_fields=["status", "attempts", "updated_at"])
    return doc


def _fail(doc: Document, message: str):
    refunded = doc.credits
    doc.status, doc.error, doc.credits = "error", message[:500], 0
    doc.save(update_fields=["status", "error", "credits", "updated_at"])
    credits.refund(doc.workspace, refunded, f"Indexation échouée : {doc.name}", document=doc)
    logger.warning(f"Ingestion [{doc.workspace.tenant_id}] {doc.name} : échec ({message}), {refunded} crédits rendus")


class _File:
    """L'objet attendu par DocumentProcessor : un nom, un flux, et le PDF converti s'il existe."""

    def __init__(self, name, content, pdf=None):
        self.name = name
        self.file_obj = io.BytesIO(content)
        self.pdf = pdf


def ingest(doc: Document):
    """Indexe un document réservé par claim(). Ne lève pas : un échec passe le document en erreur."""
    workspace = doc.workspace
    store = get_store()
    tenant = store.for_tenant(workspace.tenant_id)
    limits = workspace.limits
    try:
        content = storage.read(f"{doc.file_hash}{doc.extension}")
        if content is None:
            raise RuntimeError("Fichier original introuvable sur le stockage.")
        pdf_path = storage.find_pdf(doc.file_hash)
        if doc.kind == "office" and pdf_path is None:
            converted = formats.convert_to_pdf(doc.name, content, settings.SOFFICE_BIN)
            if converted:
                storage.save(doc.file_hash, ".pdf", converted)
                pdf_path = storage.find_pdf(doc.file_hash)
        pdf = pdf_path.read_bytes() if (pdf_path and doc.kind == "office") else None

        donors = [t for t in store.tenants_with_document(doc.file_hash) if t != tenant.tenant_id]
        if donors:
            # Même fichier déjà indexé ailleurs : vecteurs recopiés, ni OCR ni embeddings.
            chunk_count = tenant.copy_document_from(store.for_tenant(donors[0]), doc.file_hash, source=doc.name)
            pages = next((d["page_count"] for d in tenant.documents() if d["file_hash"] == doc.file_hash), doc.pages)
        else:
            processor = DocumentProcessor()
            chunks = processor.process([_File(doc.name, content, pdf)])
            page_texts = processor.pages.get(doc.name, [])
            if not chunks:
                raise RuntimeError("Aucun texte n'a pu être extrait de ce fichier.")
            for chunk in chunks:
                chunk.metadata["file_hash"] = doc.file_hash
            chunk_count = tenant.add_document(
                doc.file_hash, doc.name, chunks, page_texts,
                max_documents=limits["documents"], max_chunks=limits["pages"] * pricing.CHUNKS_PER_PAGE,
            )
            pages = len(page_texts) or doc.pages
    except Exception as e:
        logger.error(f"Ingestion [{workspace.tenant_id}] {doc.name} : {e}")
        tenant.delete_document(doc.file_hash)  # restes d'une indexation partielle
        _fail(doc, str(e) if isinstance(e, (RuntimeError, formats.UnsupportedFormat)) else
              "L'indexation a échoué. Vos crédits ont été rendus ; réessayez plus tard.")
        return

    if not Document.objects.filter(pk=doc.pk).exists():  # supprimé pendant le traitement
        tenant.delete_document(doc.file_hash)
        return
    billed = doc.credits
    if not workspace.limits["indexing_free"]:
        billed = credits.settle(workspace, doc.credits, pages * pricing.PAGE_CREDITS,
                                f"Ajustement aux pages réelles : {doc.name}", document=doc)
    Document.objects.filter(pk=doc.pk).update(
        status="ready", error="", pages=pages, chunks=chunk_count, credits=billed,
        has_pdf=storage.find_pdf(doc.file_hash) is not None, updated_at=timezone.now(),
    )
    logger.info(f"Ingestion [{workspace.tenant_id}] {doc.name} : {pages} pages, {chunk_count} chunks, {billed} crédits")


def release_original(file_hash: str):
    """Efface l'original quand plus aucun document (ni aucun espace Qdrant, démo comprise) ne l'utilise."""
    if Document.objects.filter(file_hash=file_hash).exists():
        return
    if get_store().tenants_with_document(file_hash):
        return
    storage.remove(file_hash)
    logger.info(f"Original {file_hash[:12]}… effacé du stockage")


def is_running_server() -> bool:
    """Vrai pour un serveur web (gunicorn, runserver), faux pour migrate, shell, tests."""
    import sys
    argv = " ".join(sys.argv)
    if "pytest" in argv or os.environ.get("INGESTION_DISABLED") == "1":
        return False
    return "gunicorn" in argv or "uvicorn" in argv or ("runserver" in argv and os.environ.get("RUN_MAIN") == "true")
