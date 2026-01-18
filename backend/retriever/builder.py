import os
import re
from langchain_community.vectorstores import Chroma
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from sentence_transformers import CrossEncoder
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers.ensemble import EnsembleRetriever
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
                if settings.RERANK_ENABLED:
                    return RerankRetriever(hybrid_retriever, self.embeddings, self.llm)
                return hybrid_retriever
            except Exception as e:
                logger.warning(f"Erreur lors de la création du magasin de vecteurs: {e}")
                logger.info("Utilisation du récupérateur BM25 uniquement.")
                if settings.RERANK_ENABLED:
                    return RerankRetriever(bm25, self.embeddings, self.llm)
                return bm25

        except Exception as e:
            logger.error(f"Échec de la construction du récupérateur hybride: {e}")
            raise


class RerankRetriever:
    def __init__(self, retriever, embeddings, llm):
        self.retriever = retriever
        self.embeddings = embeddings
        self.llm = llm
        self.cross = CrossEncoder(settings.RERANK_CE_MODEL)

    def _cosine(self, a, b):
        dot = 0.0
        na = 0.0
        nb = 0.0
        for x, y in zip(a, b):
            dot += x * y
            na += x * x
            nb += y * y
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / ((na ** 0.5) * (nb ** 0.5))

    def _llm_score(self, query: str, passage: str) -> float:
        prompt = (
            "Note la pertinence du passage pour la question sur 0-100. "
            "Réponds uniquement par un nombre.\n\n"
            f"Question: {query}\n\nPassage:\n{passage}"
        )
        try:
            response = self.llm.invoke(prompt)
            text = (response.content or "").strip()
            return float(re.findall(r"\\d+", text)[0])
        except Exception:
            return 0.0

    def invoke(self, query: str):
        docs = self.retriever.invoke(query)
        if not docs or not settings.RERANK_ENABLED:
            return docs
        top_k = min(settings.RERANK_TOP_K, len(docs))
        if settings.RERANK_STRATEGY == "llm":
            scores = [self._llm_score(query, d.page_content) for d in docs[:top_k]]
        elif settings.RERANK_STRATEGY == "cross":
            pairs = [(query, d.page_content) for d in docs[:top_k]]
            scores = self.cross.predict(pairs)
            if not isinstance(scores, list):
                scores = list(scores)
        else:
            query_emb = self.embeddings.embed_query(query)
            doc_embs = self.embeddings.embed_documents([d.page_content for d in docs[:top_k]])
            scores = [self._cosine(query_emb, emb) for emb in doc_embs]
        scored = list(zip(docs[:top_k], scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        reranked = [d for d, _ in scored] + docs[top_k:]
        return reranked