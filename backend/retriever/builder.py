import os
import re
from langchain_community.vectorstores import Chroma
from langchain_mistralai import ChatMistralAI
from mistralai import Mistral
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers.ensemble import EnsembleRetriever
from ..config.settings import settings
from ..utils.logging import logger
from .embeddings import get_embeddings
from .parent_child_retriever import ParentChildRetriever
from .multi_query import MultiQueryRetriever
from .hyde import HyDERetriever
from .query_decomposition import QueryDecompositionRetriever
from .contextual_compression import ContextualCompressionRetriever
from .sentence_window_retriever import SentenceWindowRetriever

hf_token = os.environ.get("HF_TOKEN")
if hf_token:
    os.environ["HUGGINGFACE_HUB_TOKEN"] = hf_token


class RetrieverBuilder:
    def __init__(self):
        """Initialiser le constructeur de récupérateur avec les embeddings."""
        # Utiliser la factory pour les embeddings (BGE-M3 ou Mistral)
        self.embeddings = get_embeddings()
        self.llm = ChatMistralAI(
            model=settings.MODEL_ID,
            api_key=settings.MISTRALAI_API_KEY,
            temperature=0,
            max_tokens=10,
        )

    def build_hybrid_retriever(self, docs):
        """Construire un récupérateur hybride utilisant BM25 et la récupération basée sur les vecteurs."""
        try:
            # Créer le récupérateur BM25 d'abord
            bm25 = BM25Retriever.from_documents(docs)
            bm25.k = settings.BM25_K
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

                # Chaîner les composants optimisés pour le recall :
                # Hybrid → SentenceWindow → ParentChild → HyDE → MultiQuery → QueryDecomp → Rerank → Compression
                retriever = hybrid_retriever

                # Sentence Window (étend les phrases au contexte de fenêtre)
                if settings.CHUNKING_STRATEGY.lower() == "sentence_window":
                    retriever = SentenceWindowRetriever(retriever)
                    logger.info("Sentence Window retriever activé.")

                # Parent-Child (retourne parents des children matchés)
                if settings.PARENT_CHILD_ENABLED:
                    retriever = ParentChildRetriever(retriever)
                    logger.info("Parent-Child retriever activé.")

                # HyDE (génère une réponse hypothétique pour améliorer les embeddings)
                if settings.HYDE_ENABLED:
                    retriever = HyDERetriever(retriever, self.llm)
                    logger.info("HyDE retriever activé.")

                # Multi-Query (génère variations de la question)
                if settings.MULTI_QUERY_ENABLED:
                    retriever = MultiQueryRetriever(retriever, self.llm)
                    logger.info("Multi-Query retriever activé.")

                # Query Decomposition (décompose les questions complexes)
                if settings.QUERY_DECOMPOSITION_ENABLED:
                    retriever = QueryDecompositionRetriever(retriever, self.llm)
                    logger.info("Query Decomposition retriever activé.")

                # Reranker (améliore la précision du ranking)
                if settings.RERANK_ENABLED:
                    retriever = RerankRetriever(retriever, self.embeddings, self.llm)
                    logger.info(f"Reranker activé: {settings.RERANK_CE_MODEL}")

                # Contextual Compression (filtre le contenu non pertinent)
                if settings.CONTEXTUAL_COMPRESSION_ENABLED:
                    retriever = ContextualCompressionRetriever(retriever, self.llm)
                    logger.info("Contextual Compression activé.")

                return retriever

            except Exception as e:
                logger.warning(f"Erreur lors de la création du magasin de vecteurs: {e}")
                logger.info("Utilisation du récupérateur BM25 uniquement.")
                # Même chaînage pour BM25 seul
                retriever = bm25
                if settings.PARENT_CHILD_ENABLED:
                    retriever = ParentChildRetriever(retriever)
                if settings.HYDE_ENABLED:
                    retriever = HyDERetriever(retriever, self.llm)
                if settings.MULTI_QUERY_ENABLED:
                    retriever = MultiQueryRetriever(retriever, self.llm)
                if settings.QUERY_DECOMPOSITION_ENABLED:
                    retriever = QueryDecompositionRetriever(retriever, self.llm)
                if settings.RERANK_ENABLED:
                    retriever = RerankRetriever(retriever, self.embeddings, self.llm)
                if settings.CONTEXTUAL_COMPRESSION_ENABLED:
                    retriever = ContextualCompressionRetriever(retriever, self.llm)
                return retriever

        except Exception as e:
            logger.error(f"Échec de la construction du récupérateur hybride: {e}")
            raise


class RerankRetriever:
    """
    Reranker utilisant l'API Mistral Rerank (mistral-rerank-2408).
    Plus léger que les modèles locaux (pas de torch/transformers).
    """

    def __init__(self, retriever, embeddings, llm):
        self.retriever = retriever
        self.embeddings = embeddings
        self.llm = llm
        self.client = Mistral(api_key=settings.MISTRALAI_API_KEY)
        logger.info(f"Mistral Reranker initialisé: {settings.RERANK_MODEL}")

    def invoke(self, query: str):
        """Reranke les documents via l'API Mistral Rerank."""
        docs = self.retriever.invoke(query)
        if not docs or not settings.RERANK_ENABLED:
            return docs

        top_k = min(settings.RERANK_TOP_K, len(docs))
        docs_to_rerank = docs[:top_k]

        try:
            # Appel à l'API Mistral Rerank
            response = self.client.classifiers.rerank(
                model=settings.RERANK_MODEL,
                query=query,
                documents=[d.page_content for d in docs_to_rerank],
                top_k=top_k,
            )

            # Reconstruire la liste ordonnée par score
            reranked_docs = []
            for result in response.results:
                doc = docs_to_rerank[result.index]
                doc.metadata["rerank_score"] = result.relevance_score
                reranked_docs.append(doc)

            # Log des scores pour debug
            if reranked_docs:
                top_score = response.results[0].relevance_score
                avg_score = sum(r.relevance_score for r in response.results) / len(response.results)
                logger.debug(f"Mistral Rerank: top_score={top_score:.3f}, avg={avg_score:.3f}")

            # Ajouter les docs non rerankés à la fin
            return reranked_docs + docs[top_k:]

        except Exception as e:
            logger.warning(f"Erreur Mistral Rerank: {e}, retour des docs non rerankés")
            return docs

    def get_relevant_documents(self, query: str):
        """Alias pour compatibilité LangChain."""
        return self.invoke(query)