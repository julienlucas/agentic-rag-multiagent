import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from .constants import MAX_FILE_SIZE, MAX_TOTAL_SIZE, ALLOWED_TYPES

load_dotenv()

class Settings(BaseSettings):
    # Paramètres requis
    MISTRALAI_API_KEY: str = os.getenv("MISTRALAI_API_KEY")
    MODEL_ID: str = "mistral-large-latest"
    MODEL_OCR_ID: str = "mistral-ocr-latest"
    EMBEDDING_MODEL_ID: str = "mistral-embed"

    # Tracking LangSmith (si besoin)
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY")

    # Paramètres optionnels avec valeurs par défaut
    MAX_FILE_SIZE: int = MAX_FILE_SIZE
    MAX_TOTAL_SIZE: int = MAX_TOTAL_SIZE
    ALLOWED_TYPES: list = ALLOWED_TYPES

    # Paramètres de base de données
    CHROMA_DB_PATH: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "documents"

    # Paramètres d'embeddings
    EMBEDDING_PROVIDER: str = "mistral"  # "mistral" ou "bge-m3"
    BGE_M3_MODEL_ID: str = "BAAI/bge-m3"  # Utilisé si EMBEDDING_PROVIDER = "bge-m3"

    # Paramètres de récupération
    VECTOR_SEARCH_K: int = 15
    BM25_K: int = 15
    HYBRID_RETRIEVER_WEIGHTS: tuple = (0.5, 0.5)
    RERANK_ENABLED: bool = True
    RERANK_TOP_K: int = 15  # Limite les docs à reranker
    RERANK_STRATEGY: str = "cross"  # "cross", "llm" ou "embedding"
    RERANK_CE_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Léger, compatible Mac

    # Multi-Query
    MULTI_QUERY_ENABLED: bool = True
    MULTI_QUERY_COUNT: int = 2  # 2 reformulations = bon compromis latence/recall

    # Paramètres de chunking
    CHUNKING_STRATEGY: str = "semantic"  # "recursive" ou "semantic"
    PARENT_CHILD_ENABLED: bool = True
    PARENT_CHUNK_SIZE: int = 2000
    CHILD_CHUNK_SIZE: int = 400
    CHUNK_SIZE: int = 700
    CHUNK_OVERLAP: int = 300

    # Evaluation
    EVAL_LLM_JUDGE_ENABLED: bool = True

    # Paramètres de journalisation
    LOG_LEVEL: str = "INFO"

    # Nouveaux paramètres de cache avec annotations de type
    CACHE_DIR: str = "document_cache"
    CACHE_EXPIRE_DAYS: int = 7

    # Répertoire des exemples
    EXAMPLES_DIR: str = "./static"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()