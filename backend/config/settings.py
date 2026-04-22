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

    # Cohere API (pour reranking)
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY")

    # Paramètres d'embeddings
    EMBEDDING_PROVIDER: str = "mistral"  # Mistral-embed fonctionne mieux sur ce corpus
    BGE_M3_MODEL_ID: str = "BAAI/bge-m3"

    # Paramètres de récupération - CONFIG OPTIMISÉE RECALL
    VECTOR_SEARCH_K: int = 20
    BM25_K: int = 20
    HYBRID_RETRIEVER_WEIGHTS: tuple = (0.5, 0.5)  # Équilibré — BM25 crucial pour termes exacts
    RERANK_ENABLED: bool = True
    RERANK_TOP_K: int = 30  # Top N résultats après reranking de TOUS les candidats
    RERANK_MODEL: str = "rerank-v4.0-pro"  # Cohere Rerank 4 Pro (gratuit en trial)

    # Multi-Query - 2 reformulations (compromis latence/recall pour la prod)
    MULTI_QUERY_ENABLED: bool = True
    MULTI_QUERY_COUNT: int = 2

    # HyDE - DÉSACTIVÉ (nuit au retrieval sur ce corpus)
    HYDE_ENABLED: bool = False

    # Query Decomposition - DÉSACTIVÉ
    QUERY_DECOMPOSITION_ENABLED: bool = False

    # Contextual Compression - DÉSACTIVÉ
    CONTEXTUAL_COMPRESSION_ENABLED: bool = False
    CONTEXTUAL_COMPRESSION_TOP_K: int = 5

    # Paramètres de chunking - CONFIG OPTIMISÉE RECALL
    CHUNKING_STRATEGY: str = "semantic"
    PARENT_CHILD_ENABLED: bool = True
    PARENT_CHUNK_SIZE: int = 1200  # Parents ciblés pour le reranking
    CHILD_CHUNK_SIZE: int = 400  # Children assez gros pour matcher les keywords BM25
    CHILD_OVERLAP: int = 50
    CHUNK_SIZE: int = 500  # Réduit pour éviter la "moyennisation" des embeddings
    CHUNK_OVERLAP: int = 100  # 300 était excessif, 100 suffit
    SEMANTIC_THRESHOLD: float = 0.35  # Splits plus granulaires

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