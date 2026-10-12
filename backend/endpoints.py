import json
import hashlib
import os
import uuid
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .document_processor import storage
from .document_processor.file_handler import DocumentProcessor
from .retriever.builder import RetrieverBuilder
from .retriever.page_store import PageStore
from .vectorstore import QuotaExceeded, get_store
from .agents.workflow import AgentWorkflow
from .evals.feedback import votes, votes_dataset
from .config.settings import settings
from .utils.logging import logger
from langsmith import trace

# Configuration LangSmith pour le tracking, seulement si une clé est fournie : sans clé,
# os.environ[...] = None faisait planter l'import du module (la clé est optionnelle).
if settings.LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = votes.TRACE_PROJECT

# Démo publique (sans compte) : les exemples AMD / Boeing, dans un espace par session_id envoyé
# par le client, préfixé « demo- ». Ce n'est pas une isolation réelle (quiconque connaît un
# session_id lit cet espace), d'où : pas de dépôt de fichier ici, seulement les exemples. Le
# préfixe garantit qu'un session_id ne désigne jamais l'espace d'un compte (« ws-… », saas/).
# L'espace connecté (backend/saas/views.py) tire son tenant de la session authentifiée.

# Pages OCR par (tenant, documents indexés) : évite de relire toutes les pages dans Qdrant
# à chaque question. La clé change dès qu'un document est ajouté ou supprimé.
_PAGE_CACHE_MAX = 32
_page_cache = {}


class BadTenant(ValueError):
    pass


def _tenant(session_id):
    try:
        return get_store().for_tenant(f"demo-{session_id}")
    except ValueError as e:
        raise BadTenant(str(e)) from e


def _page_store(tenant, documents):
    key = (tenant.tenant_id, tuple(sorted(d["file_hash"] for d in documents)))
    if key not in _page_cache:
        if len(_page_cache) >= _PAGE_CACHE_MAX:
            _page_cache.pop(next(iter(_page_cache)))
        pages = tenant.pages()
        _page_cache[key] = PageStore(pages) if pages else None
    return _page_cache[key]

# Workflow instancié une seule fois (les modèles LangGraph + LLM clients
# sont réutilisés entre requêtes).
_workflow = AgentWorkflow()

def file_hash(file) -> str:
    """SHA-256 du contenu : identifie un document dans l'espace du tenant."""
    if hasattr(file, 'file_obj'):
        file.file_obj.seek(0)
        content = file.file_obj.read()
        file.file_obj.seek(0)
    else:
        with open(file.name, "rb") as f:
            content = f.read()
    return hashlib.sha256(content).hexdigest()


def _is_example(f) -> bool:
    return not hasattr(f, 'file_obj')


def document_url(f, digest: str):
    """
    Lien vers l'original d'un PDF, gardé dans les métadonnées de ses chunks (`pdf_url`).
    Un exemple est servi par le frontend (static/, copié par vercel.json) ; un fichier déposé
    est rangé dans le stockage des originaux et servi par l'API (document_file).
    """
    if not f.name.lower().endswith(".pdf"):
        return None
    if _is_example(f):
        return f"/static/{os.path.basename(f.name)}"
    return storage.api_url(digest)


def _store_original(f, digest: str):
    """Garde l'original d'un fichier déposé ; un échec ne bloque pas l'indexation (repli : texte OCR)."""
    if _is_example(f):
        return
    try:
        f.file_obj.seek(0)
        storage.save(digest, os.path.splitext(f.name)[1], f.file_obj.read())
        f.file_obj.seek(0)
    except OSError as e:
        logger.error(f"Original de {f.name} non sauvegardé ({e}) : la citation s'ouvrira sur le texte OCR")


def _release_original(file_hash: str):
    """Efface l'original quand plus aucun espace (ni aucun compte) n'indexe ce document."""
    from .saas.ingestion import release_original
    release_original(file_hash)


def process_files(file_objects, session_id, success_message="Fichiers traités avec succès"):
    """
    Indexe les fichiers dans l'espace Qdrant du tenant ; un fichier déjà indexé est ignoré.
    Un fichier déjà indexé à l'identique dans un autre espace (un exemple, surtout) y est recopié
    avec ses vecteurs, sans OCR ni embeddings : charger AMD ou Boeing devient immédiat.
    """
    tenant = _tenant(session_id)
    hashes = {id(f): file_hash(f) for f in file_objects}
    new_files = [f for f in file_objects if not tenant.has_document(hashes[id(f)])]

    indexed = 0
    store = get_store()
    pending = []
    for f in new_files:
        digest = hashes[id(f)]
        _store_original(f, digest)
        donors = [t for t in store.tenants_with_document(digest) if t != tenant.tenant_id]
        if donors:
            indexed += tenant.copy_document_from(store.for_tenant(donors[0]), digest)
        else:
            pending.append(f)

    if pending:
        processor = DocumentProcessor()
        chunks = processor.process(pending)
        logger.info(f"Chunks générés: {len(chunks)}")
        by_source = {}
        for chunk in chunks:
            by_source.setdefault(chunk.metadata.get("source"), []).append(chunk)
        for f in pending:
            file_chunks = by_source.get(f.name, [])
            if not file_chunks:
                return JsonResponse({"error": f"Aucun texte extrait de {os.path.basename(f.name)}."}, status=422)
            # Identifiant et lien de l'original sur chaque chunk : une citation rouvre le document.
            url = document_url(f, hashes[id(f)])
            for chunk in file_chunks:
                chunk.metadata["file_hash"] = hashes[id(f)]
                if url:
                    chunk.metadata["pdf_url"] = url
            indexed += tenant.add_document(hashes[id(f)], f.name, file_chunks, processor.pages.get(f.name, []))

    documents = tenant.documents()
    logger.info(f"Tenant {tenant.tenant_id}: {len(documents)} document(s), {indexed} chunks ajoutés "
                f"({len(new_files) - len(pending)} recopié(s) d'un autre espace)")
    return JsonResponse({
        "message": success_message if new_files else "Document déjà indexé",
        "chunks_count": sum(d["chunk_count"] for d in documents if d["file_hash"] in hashes.values()),
    })

@csrf_exempt
@require_http_methods(["GET"])
def index(request):
    return render(request, 'frontend/dist/index.html')

@csrf_exempt
@require_http_methods(["POST"])
def load_file(request):
    """Charger un fichier depuis le disque dur"""

    data = json.loads(request.body)
    file_name = data.get('file_name', '').strip()
    session_id = data.get('session_id', 'default')

    # Le nom vient du client : sans ce contrôle, « ../README.md » (ou tout .md/.txt/.pdf du
    # serveur) était OCRisé et devenait interrogeable par n'importe quel visiteur.
    examples_dir = os.path.realpath(settings.EXAMPLES_DIR)
    file_path = os.path.realpath(os.path.join(examples_dir, file_name))
    if not file_name or file_path == examples_dir or os.path.commonpath([examples_dir, file_path]) != examples_dir:
        return JsonResponse({"error": f"Fichier d'exemple inconnu: {file_name}"}, status=400)

    try:
        # Créer un objet fichier pour le processeur
        class FileObject:
            def __init__(self, path):
                self.name = path

        file_obj = FileObject(file_path)

        response = process_files([file_obj], session_id, "Fichier chargé avec succès")
        response_data = json.loads(response.content)
        response_data["filename"] = file_name
        return JsonResponse(response_data, status=response.status_code)

    except (BadTenant, QuotaExceeded) as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        logger.error(f"Erreur lors du chargement du fichier: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def process_question(request):
    """Traiter une question avec les documents chargés"""

    data = json.loads(request.body)
    question = data.get('question', '').strip()
    session_id = data.get('session_id', 'default')

    try:
        tenant = _tenant(session_id)
        documents = tenant.documents()
        if not documents:
            return JsonResponse({"error": "Aucun document chargé. Veuillez d'abord charger un document."}, status=400)

        # Run racine à l'identifiant connu : les appels LangChain du pipeline s'y rattachent,
        # et le vote de l'utilisateur vise ce run (votes.py). Les métadonnées permettent de
        # rejouer la question plus tard sur les mêmes documents (backend/evals/feedback/replay.py).
        run_id = uuid.uuid4()
        with trace(
            "question", "chain", run_id=run_id, inputs={"question": question},
            metadata={
                "tenant_id": tenant.tenant_id,
                "documents": [d["file_hash"] for d in documents],
                "document_names": [os.path.basename(d["source"]) for d in documents],
            },
        ) as run:
            result = _workflow.full_pipeline(
                question=question,
                retriever=RetrieverBuilder().build_hybrid_retriever(tenant),
                page_store=_page_store(tenant, documents),
            )
            run.end(outputs=result)

        return JsonResponse({
            "draft_answer": result["draft_answer"],
            "verification_report": result["verification_report"],
            "citations": locate_citations(result.get("citations", []), documents),
            "feedback_token": votes.issue_token(run_id, tenant.tenant_id) if votes.enabled() else None,
        })

    except BadTenant as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la question: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


def locate_citations(citations, documents):
    """
    Complète chaque citation avec l'identifiant (`file_hash`) et le lien (`pdf_url`) de son
    document, pour que le frontend l'ouvre à la page citée. Les chunks indexés depuis le
    stockage des originaux les portent déjà ; les pages lues par read_page et les documents
    indexés avant n'ont que leur nom, retrouvé ici parmi les documents de l'espace.
    """
    by_name = {os.path.splitext(os.path.basename(d["source"]))[0]: d for d in documents}
    for c in citations:
        doc = by_name.get(c.get("source"))
        if doc is None:
            continue
        c.setdefault("file_hash", None)
        c["file_hash"] = c["file_hash"] or doc["file_hash"]
        if not c.get("pdf_url") and doc["source"].lower().endswith(".pdf"):
            examples_dir = os.path.realpath(settings.EXAMPLES_DIR)
            if os.path.dirname(os.path.realpath(doc["source"])) == examples_dir:
                c["pdf_url"] = f"/static/{os.path.basename(doc['source'])}"
            elif storage.find(doc["file_hash"]) is not None:
                c["pdf_url"] = storage.api_url(doc["file_hash"])
    return citations


@csrf_exempt
@require_http_methods(["GET"])
def document_file(request, file_hash):
    """L'original d'un document déposé, s'il appartient à l'espace du tenant."""
    try:
        tenant = _tenant(request.GET.get('session_id', 'default'))
    except BadTenant as e:
        return JsonResponse({"error": str(e)}, status=400)
    path = storage.find(file_hash) if tenant.has_document(file_hash) else None
    if path is None:
        return JsonResponse({"error": "Original indisponible pour ce document."}, status=404)
    content_type = "application/pdf" if path.suffix == ".pdf" else "application/octet-stream"
    return FileResponse(open(path, "rb"), content_type=content_type, as_attachment=False)


@csrf_exempt
@require_http_methods(["GET"])
def document_page(request):
    """Texte OCR d'une page (numérotée à partir de 1) : le repli quand l'original n'est pas disponible."""
    try:
        tenant = _tenant(request.GET.get('session_id', 'default'))
        file_hash = request.GET.get('file_hash', '')
        page = int(request.GET.get('page', ''))
    except BadTenant as e:
        return JsonResponse({"error": str(e)}, status=400)
    except ValueError:
        return JsonResponse({"error": "page doit être un entier."}, status=400)
    text = tenant.page_text(file_hash, page - 1) if page >= 1 else None
    if text is None:
        return JsonResponse({"error": "Page introuvable dans cet espace."}, status=404)
    return JsonResponse({"file_hash": file_hash, "page": page, "text": text})


@csrf_exempt
@require_http_methods(["GET"])
def list_documents(request):
    """Documents de l'espace du tenant."""
    try:
        tenant = _tenant(request.GET.get('session_id', 'default'))
        return JsonResponse({"documents": [
            {"file_hash": d["file_hash"], "name": os.path.basename(d["source"]),
             "chunk_count": d["chunk_count"], "page_count": d["page_count"]}
            for d in tenant.documents()
        ]})
    except BadTenant as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def delete_document(request):
    """Supprime un document (par son hash) de l'espace du tenant."""
    data = json.loads(request.body)
    try:
        tenant = _tenant(data.get('session_id', 'default'))
        target = data.get('file_hash', '')
        if not tenant.has_document(target):
            return JsonResponse({"error": "Document inconnu dans cet espace."}, status=404)
        tenant.delete_document(target)
        _release_original(target)
        return JsonResponse({"message": "Document supprimé"})
    except BadTenant as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def delete_space(request):
    """Vide l'espace du tenant."""
    data = json.loads(request.body)
    try:
        tenant = _tenant(data.get('session_id', 'default'))
        hashes = [d["file_hash"] for d in tenant.documents()]
        tenant.delete_all()
        for digest in hashes:
            _release_original(digest)
        return JsonResponse({"message": "Espace vidé"})
    except BadTenant as e:
        return JsonResponse({"error": str(e)}, status=400)



@csrf_exempt
@require_http_methods(["POST"])
def submit_feedback(request):
    """Vote 👍 (score 1) / 👎 (score 0) sur une réponse, avec un commentaire facultatif."""
    data = json.loads(request.body)
    score = data.get("score")
    comment = (data.get("comment") or "").strip()
    if not votes.enabled():
        return JsonResponse({"error": "Les votes ne sont pas activés sur ce serveur."}, status=503)
    if score not in (0, 1) or isinstance(score, bool):
        return JsonResponse({"error": "score doit valoir 0 ou 1."}, status=400)
    if len(comment) > votes.COMMENT_MAX_CHARS:
        return JsonResponse({"error": f"Commentaire limité à {votes.COMMENT_MAX_CHARS} caractères."}, status=400)
    try:
        tenant = _tenant(data.get("session_id", "default"))
        run_id = votes.read_token(data.get("feedback_token") or "", tenant.tenant_id)
    except (BadTenant, votes.InvalidFeedback) as e:
        return JsonResponse({"error": str(e)}, status=400)
    try:
        votes.send(run_id, score, comment)
    except Exception as e:
        logger.error(f"Envoi du vote à LangSmith impossible: {e}")
        return JsonResponse({"error": "Vote non enregistré, réessayez plus tard."}, status=502)
    votes_dataset.collect_in_background(run_id, score, comment)
    return JsonResponse({"message": "Merci pour votre retour"})
