from langchain_core.embeddings import Embeddings
from langchain_mistralai import MistralAIEmbeddings
from ..config.settings import settings
from ..utils.logging import logger


def get_embeddings() -> Embeddings:
    """
    Factory function pour obtenir le provider d'embeddings Mistral.

    Returns:
        Embeddings: Instance MistralAIEmbeddings
    """
    logger.info("Utilisation des embeddings Mistral")
    return MistralAIEmbeddings(
        model=settings.EMBEDDING_MODEL_ID,
        api_key=settings.MISTRALAI_API_KEY,
    )
