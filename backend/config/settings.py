import os
from dotenv import load_dotenv
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    # Paramètres requis
    MISTRALAI_API_KEY: str = os.getenv("MISTRALAI_API_KEY")
    MODEL_ID: str = "mistral-large-latest"  # Réservé à la génération finale
    MODEL_SMALL_ID: str = "mistral-small-latest"  # Sous-agents (classif, reformulation)
    MODEL_OCR_ID: str = "mistral-ocr-latest"
    EMBEDDING_MODEL_ID: str = "mistral-embed"

    # Timeouts et retries sur les appels LLM (évite les blocages de 2min)
    LLM_TIMEOUT: int = 30  # secondes par appel
    LLM_MAX_RETRIES: int = 2

    # Tracking LangSmith (si besoin)
    LANGSMITH_API_KEY: Optional[str] = None  # optionnel : le README le dit, le code ne le permettait pas

    # Paramètres optionnels avec valeurs par défaut

    CHROMA_COLLECTION_NAME: str = "documents"

    # Cohere API (pour reranking)
    COHERE_API_KEY: Optional[str] = None

    # Paramètres d'embeddings

    # Paramètres de récupération - CONFIG OPTIMISÉE RECALL
    VECTOR_SEARCH_K: int = 20
    BM25_K: int = 20
    HYBRID_RETRIEVER_WEIGHTS: tuple = (0.5, 0.5)  # Équilibré — BM25 crucial pour termes exacts
    RERANK_ENABLED: bool = True
    RERANK_TOP_K: int = 30  # Top N résultats après reranking de TOUS les candidats
    RERANK_MODEL: str = "rerank-v4.0-pro"  # Cohere Rerank 4 Pro (gratuit en trial)

    # Multi-Query - 1 reformulation (compromis latence/recall pour la prod)
    MULTI_QUERY_ENABLED: bool = True
    MULTI_QUERY_COUNT: int = 1

    # HyDE - DÉSACTIVÉ (nuit au retrieval sur ce corpus)
    HYDE_ENABLED: bool = False

    # Query Decomposition - DÉSACTIVÉ
    QUERY_DECOMPOSITION_ENABLED: bool = False

    # Contextual Compression - DÉSACTIVÉ
    CONTEXTUAL_COMPRESSION_ENABLED: bool = False
    CONTEXTUAL_COMPRESSION_TOP_K: int = 5

    # Routage par document : avant de chercher, cibler le(s) document(s) que la question
    # désigne (nom d'entreprise / de fichier). Réduit la dilution quand plusieurs documents
    # longs sont indexés ensemble. Sans effet avec un seul document.
    DOCUMENT_ROUTING_ENABLED: bool = True

    # Recherche corrective (agentique) : si le vérificateur de pertinence juge les passages
    # insuffisants, réécrire la question dans le vocabulaire du document et relancer la
    # recherche, puis fusionner. Traite les questions dont les mots ne sont pas ceux du texte
    # ("legal battles" vs "litigation", "gross margin" absent d'un bilan bancaire).
    CORRECTIVE_RETRIEVAL_ENABLED: bool = True
    CORRECTIVE_MAX_ROUNDS: int = 1
    CORRECTIVE_QUERY_COUNT: int = 3
    # Les N premiers documents du retrieval initial sont intouchables : la recherche
    # corrective ne peut qu'ajouter après eux. Éval FinanceBench : la fusion RRF naïve
    # éjectait du top-10 des preuves initialement aux rangs 2 et 6.
    CORRECTIVE_PROTECT_TOP: int = 5
    # Déclencheur : score max du reranker Cohere sous ce seuil = le retrieval a
    # probablement raté -> corriger. (NO_MATCH du checker déclenche toujours ;
    # le checker seul ne suffit pas : son prompt le biaise vers PARTIAL et il ne
    # renvoie pratiquement jamais NO_MATCH.) 0 = désactive ce critère.
    # Filet pour un retrieval au score anormalement bas malgré un CAN_ANSWER.
    # À 0 = désactivé : PARTIAL et NO_MATCH suffisent à déclencher la correction, et ce
    # seuil-ci n'avait jamais rien déclenché sur les deux jeux d'éval.
    CORRECTIVE_RERANK_THRESHOLD: float = 0.0

    # Nombre de documents (parents) transmis au LLM pour la génération.
    # Éval FinanceBench : à 5, 3 questions sur 21 avaient leur preuve au rang 6-20.
    RESEARCH_TOP_K: int = 10

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


    # Nouveaux paramètres de cache avec annotations de type
    CACHE_DIR: str = "document_cache"
    CACHE_EXPIRE_DAYS: int = 7

    # Répertoire des exemples
    EXAMPLES_DIR: str = "./static"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()