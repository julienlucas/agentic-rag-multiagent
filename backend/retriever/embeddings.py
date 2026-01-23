"""
Factory pour embeddings avec support BGE-M3 et Mistral.
"""
from typing import List
from langchain_core.embeddings import Embeddings
from langchain_mistralai import MistralAIEmbeddings
from ..config.settings import settings
from ..utils.logging import logger


class BGEM3Embeddings(Embeddings):
    """Wrapper LangChain pour BGE-M3 via FlagEmbedding."""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.BGE_M3_MODEL_ID
        self._model = None

    def _load_model(self):
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel
            logger.info(f"Chargement du modèle BGE-M3: {self.model_name}")
            self._model = BGEM3FlagModel(
                self.model_name,
                use_fp16=True,
                device="cpu"  # Changez en "cuda" si GPU disponible
            )
        return self._model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed une liste de documents."""
        model = self._load_model()
        embeddings = model.encode(
            texts,
            batch_size=32,
            max_length=512,
        )["dense_vecs"]
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Embed une requête."""
        model = self._load_model()
        embedding = model.encode(
            [text],
            batch_size=1,
            max_length=512,
        )["dense_vecs"][0]
        return embedding.tolist()


def get_embeddings() -> Embeddings:
    """
    Factory function pour obtenir le bon provider d'embeddings.

    Returns:
        Embeddings: Instance du provider configuré (BGE-M3 ou Mistral)
    """
    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "bge-m3":
        logger.info("Utilisation des embeddings BGE-M3")
        return BGEM3Embeddings(settings.BGE_M3_MODEL_ID)
    elif provider == "mistral":
        logger.info("Utilisation des embeddings Mistral")
        return MistralAIEmbeddings(
            model=settings.EMBEDDING_MODEL_ID,
            api_key=settings.MISTRALAI_API_KEY,
        )
    else:
        logger.warning(f"Provider inconnu '{provider}', fallback vers Mistral")
        return MistralAIEmbeddings(
            model=settings.EMBEDDING_MODEL_ID,
            api_key=settings.MISTRALAI_API_KEY,
        )
