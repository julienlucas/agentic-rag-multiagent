import json
import hashlib
import os
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from typing import List
from .document_processor.file_handler import DocumentProcessor
from .retriever.builder import RetrieverBuilder
from .agents.workflow import AgentWorkflow
from .config import constants
from .config.settings import settings
from .utils.logging import logger

# Configuration LangSmith pour le tracking (si besoin)
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGCHAIN_PROJECT"] = "agentic_rag_multi_agent"

# Stockage des sessions (en production, utiliser Redis ou base de données)
sessions = {}

def get_file_hashes(uploaded_files: List) -> frozenset:
    """Générer des hashes SHA-256 pour les fichiers téléchargés"""

    hashes = set()
    for file in uploaded_files:
        if hasattr(file, 'file_obj'):
            # Fichier uploadé - lire depuis file_obj
            file.file_obj.seek(0)  # Remettre au début
            content = file.file_obj.read()
            hashes.add(hashlib.sha256(content).hexdigest())
        else:
            # Fichier local - lire depuis le chemin
            with open(file.name, "rb") as f:
                hashes.add(hashlib.sha256(f.read()).hexdigest())
    return frozenset(hashes)

def process_files(file_objects, session_id, success_message="Fichiers traités avec succès"):
    """Fonction commune pour traiter les fichiers et mettre à jour la session"""

    # Initialiser la session si nécessaire
    if session_id not in sessions:
        sessions[session_id] = {
            "file_hashes": frozenset(),
            "retriever": None
        }

    # Traiter les documents
    processor = DocumentProcessor()
    retriever_builder = RetrieverBuilder()

    chunks = processor.process(file_objects)
    logger.info(f"Chunks générés: {len(chunks)}")

    retriever = retriever_builder.build_hybrid_retriever(chunks)
    logger.info(f"Retriever créé: {retriever is not None}")

    # Mettre à jour la session
    current_hashes = get_file_hashes(file_objects)
    sessions[session_id].update({
        "file_hashes": current_hashes,
        "retriever": retriever
    })

    logger.info(f"Session {session_id} mise à jour. Retriever: {sessions[session_id]['retriever'] is not None}")

    return JsonResponse({
        "message": success_message,
        "chunks_count": len(chunks)
    })

@csrf_exempt
@require_http_methods(["GET"])
def index(request):
    return render(request, 'frontend/dist/index.html')

@csrf_exempt
@require_http_methods(["POST"])
def upload_file(request):
    """Télécharger et traiter un fichier"""

    file = request.FILES.get('file')
    session_id = request.POST.get('session_id', 'default')

    try:
        # Valider le fichier
        if not file.name.lower().endswith(tuple(constants.ALLOWED_TYPES)):
            return JsonResponse({"error": f"Type de fichier non supporté: {file.name}"}, status=400)

        # Créer l'objet fichier pour le processeur
        class FileObject:
            def __init__(self, file_obj):
                self.name = file_obj.name
                self.file_obj = file_obj

        file_object = FileObject(file)
        return process_files([file_object], session_id, "Fichier traité avec succès")

    except Exception as e:
        logger.error(f"Erreur lors du traitement du fichier: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def load_file(request):
    """Charger un fichier depuis le disque dur"""

    data = json.loads(request.body)
    file_name = data.get('file_name', '').strip()
    session_id = data.get('session_id', 'default')

    try:
        # Chemin vers le fichier sur le disque dur
        file_path = os.path.join(settings.EXAMPLES_DIR, file_name)

        # Créer un objet fichier pour le processeur
        class FileObject:
            def __init__(self, path):
                self.name = path

        file_obj = FileObject(file_path)

        response = process_files([file_obj], session_id, "Fichier chargé avec succès")
        response_data = json.loads(response.content)
        response_data["filename"] = file_name
        return JsonResponse(response_data)

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
        # Vérifier que la session existe et a un retriever
        if session_id not in sessions:
            return JsonResponse({"error": "Aucun document chargé. Veuillez d'abord charger un document."}, status=400)

        if sessions[session_id]["retriever"] is None:
            return JsonResponse({"error": "Aucun retriever disponible. Veuillez recharger le document."}, status=400)

        workflow = AgentWorkflow()
        result = workflow.full_pipeline(
            question=question,
            retriever=sessions[session_id]["retriever"]
        )

        return JsonResponse({
            "draft_answer": result["draft_answer"],
            "verification_report": result["verification_report"]
        })

    except Exception as e:
        logger.error(f"Erreur lors du traitement de la question: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

