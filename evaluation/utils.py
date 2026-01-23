import json
import os
import sys
from pathlib import Path
from typing import Dict, List

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
    try:
        client = Client()
        run = client.create_run(
            name=name,
            run_type="evaluation",
            inputs=inputs,
            outputs=summary,
            project_name="agentic_rag_multi_agent_evals",
        )
        print(f"✓ Résultats envoyés à LangSmith (projet: agentic_rag_multi_agent_eval)")
        return run
    except Exception as e:
        print(f"⚠️  Erreur LangSmith: {e}")
        return None
