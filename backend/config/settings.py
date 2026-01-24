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
    BGE_M3_MODEL_ID: str = "BAAI/bge-m3"

    # Paramètres de récupération - OPTIMISÉS
    VECTOR_SEARCH_K: int = 25  # Augmenté: plus de candidats = meilleur recall
    BM25_K: int = 25  # Augmenté
    HYBRID_RETRIEVER_WEIGHTS: tuple = (0.6, 0.4)  # Favorise BM25 (matching exact)
    RERANK_ENABLED: bool = True
    RERANK_TOP_K: int = 20  # Rerank plus de docs
    RERANK_STRATEGY: str = "cross"
    RERANK_CE_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    RERANK_DEVICE: str = "cpu"

    # Multi-Query - AUGMENTÉ
    MULTI_QUERY_ENABLED: bool = True
    MULTI_QUERY_COUNT: int = 3  # 3 reformulations = meilleur recall

    # HyDE - DÉSACTIVÉ
    HYDE_ENABLED: bool = False

    # Query Decomposition - DÉSACTIVÉ
    QUERY_DECOMPOSITION_ENABLED: bool = False

    # Contextual Compression - DÉSACTIVÉ
    CONTEXTUAL_COMPRESSION_ENABLED: bool = False
    CONTEXTUAL_COMPRESSION_TOP_K: int = 5

    # Paramètres de chunking - OPTIMISÉS
    CHUNKING_STRATEGY: str = "semantic"
    PARENT_CHILD_ENABLED: bool = True
    PARENT_CHUNK_SIZE: int = 1500  # Réduit pour plus de granularité
    CHILD_CHUNK_SIZE: int = 350  # Légèrement réduit
    CHILD_OVERLAP: int = 100  # Plus d'overlap = moins de perte d'info
    CHUNK_SIZE: int = 600  # Réduit
    CHUNK_OVERLAP: int = 200  # Plus d'overlap
    SEMANTIC_THRESHOLD: float = 0.45  # Plus de découpes sémantiques

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