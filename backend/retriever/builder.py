import os
from langchain_community.vectorstores import Chroma
from langchain_mistralai import MistralAIEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from ..config.settings import settings
from ..utils.logging import logger

hf_token = os.environ.get("HF_TOKEN")
if hf_token:
    os.environ["HUGGINGFACE_HUB_TOKEN"] = hf_token

class RetrieverBuilder:
    def __init__(self):
        """Initialiser le constructeur de récupérateur avec les embeddings."""

        embedding = MistralAIEmbeddings(
            model=settings.EMBEDDING_MODEL_ID,
            api_key=settings.MISTRALAI_API_KEY,
        )
        self.embeddings = embedding

    def build_hybrid_retriever(self, docs):
        """Construire un récupérateur hybride utilisant BM25 et la récupération basée sur les vecteurs."""
        try:
            # Créer le récupérateur BM25 d'abord
            bm25 = BM25Retriever.from_documents(docs)
            logger.info("Récupérateur BM25 créé avec succès.")

            try:
                vector_store = Chroma.from_documents(
                    documents=docs,
                    embedding=self.embeddings,
                    persist_directory=settings.CHROMA_DB_PATH
                )
                logger.info("Magasin de vecteurs créé avec succès.")

                # Créer le récupérateur basé sur les vecteurs
                vector_retriever = vector_store.as_retriever(search_kwargs={"k": settings.VECTOR_SEARCH_K})
                logger.info("Récupérateur de vecteurs créé avec succès.")

                # Combiner les récupérateurs en un récupérateur hybride
                weights = settings.HYBRID_RETRIEVER_WEIGHTS
                if len(weights) != 2:
                    logger.warning(f"Poids incorrects: {weights}, utilisation des poids par défaut")
                    weights = [0.4, 0.6]

                hybrid_retriever = EnsembleRetriever(
                    retrievers=[bm25, vector_retriever],
                    weights=weights
                )
                logger.info("Récupérateur hybride créé avec succès.")
                return hybrid_retriever
            except Exception as e:
                logger.warning(f"Erreur lors de la création du magasin de vecteurs: {e}")
                logger.info("Utilisation du récupérateur BM25 uniquement.")
                return bm25

        except Exception as e:
            logger.error(f"Échec de la construction du récupérateur hybride: {e}")
            raise