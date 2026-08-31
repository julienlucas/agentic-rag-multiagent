import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langsmith import Client
from backend.config.settings import settings
from backend.document_processor.file_handler import DocumentProcessor
from backend.retriever.builder import RetrieverBuilder


def load_dataset(path: str) -> List[Dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset introuvable: {path}")
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            items.append(json.loads(line))
    return items


def resolve_file_path(example: Dict) -> str:
    if example.get("file_path"):
        return example["file_path"]
    file_name = example.get("file_name", "").strip()
    return os.path.join(settings.EXAMPLES_DIR, file_name)


def build_retriever_for_file(file_path: str):
    class FileObject:
        def __init__(self, path: str):
            self.name = path

    processor = DocumentProcessor()
    retriever_builder = RetrieverBuilder()
    chunks = processor.process([FileObject(file_path)])
    return retriever_builder.build_hybrid_retriever(chunks)


def log_to_langsmith(name: str, summary: Dict, inputs: Dict):
    api_key = os.getenv("LANGSMITH_API_KEY")
    if not api_key:
        print("⚠️  LANGSMITH_API_KEY non défini, skip logging")
        return None

    project = os.getenv("LANGSMITH_PROJECT", "agentic_rag_multi_agent_evals")
    try:
        client = Client()
        run_id = uuid.uuid4()
        # LangSmith n'accepte que: tool, chain, llm, retriever, embedding, prompt, parser.
        # "evaluation" était refusé avec un 422 et le logging ne fonctionnait donc jamais.
        now = datetime.now(timezone.utc)
        client.create_run(
            id=run_id,
            name=name,
            run_type="chain",
            inputs=inputs,
            outputs=summary,
            project_name=project,
            # Sans end_time, le run resterait affiché « en cours » indéfiniment.
            start_time=now,
            end_time=now,
        )
        # create_run met en file d'attente : sans flush, une erreur serveur passerait
        # inaperçue et le message de succès serait mensonger.
        client.flush()
        print(f"✓ Résultats envoyés à LangSmith (projet: {project})")
        return run_id
    except Exception as e:
        print(f"⚠️  Erreur LangSmith: {e}")
        return None


def build_retriever_from_chunks(chunks: List, persist_directory: str = None):
    """
    Construit le retriever à partir de chunks déjà produits, sans repasser par l'OCR.

    build_retriever_for_file() passe par DocumentProcessor, qui ré-OCRise le fichier.
    L'évaluation FinanceBench pré-calcule ses chunks (OCR page par page + metadata de page)
    dans une phase séparée, et réutilise ici exactement la même chaîne de retrieval que
    la production : BM25 + Chroma -> ParentChild -> MultiQuery -> Rerank Cohere.
    """
    return RetrieverBuilder().build_hybrid_retriever(chunks, persist_directory=persist_directory)


# Résilience aux rate limits : implémentation côté backend (utilisée aussi par le
# workflow et les agents), ré-exportée ici pour les scripts d'évaluation.
from backend.utils.resilience import (  # noqa: E402,F401
    call_with_backoff,
    is_rate_limit,
    retry_after,
    root_cause,
)
