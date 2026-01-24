import os
import re
from langchain_community.vectorstores import Chroma
from langchain_mistralai import ChatMistralAI
from sentence_transformers import CrossEncoder
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
    Reranker avec support de plusieurs stratégies :
    - cross: CrossEncoder (BGE-reranker-v2-m3 ou ms-marco-MiniLM)
    - llm: LLM scoring (lent mais flexible)
    - embedding: Cosine similarity (rapide mais moins précis)
    """

    # Cache du modèle CrossEncoder pour éviter de le recharger à chaque requête
    _cross_encoder_cache = {}

    def __init__(self, retriever, embeddings, llm):
        self.retriever = retriever
        self.embeddings = embeddings
        self.llm = llm
        self._init_cross_encoder()

    def _init_cross_encoder(self):
        """Initialise le CrossEncoder avec fallback si le modèle n'est pas disponible."""
        model_name = settings.RERANK_CE_MODEL
        device = getattr(settings, "RERANK_DEVICE", "cpu")

        # Utiliser le cache
        cache_key = f"{model_name}_{device}"
        if cache_key in self._cross_encoder_cache:
            self.cross = self._cross_encoder_cache[cache_key]
            return

        try:
            self.cross = CrossEncoder(model_name, device=device)
            self._cross_encoder_cache[cache_key] = self.cross
            logger.info(f"CrossEncoder chargé: {model_name} sur {device}")
        except Exception as e:
            # Fallback vers ms-marco-MiniLM-L-6 si échec
            fallback_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
            logger.warning(f"Erreur chargement {model_name}: {e}")
            logger.info(f"Fallback vers {fallback_model}")
            try:
                self.cross = CrossEncoder(fallback_model, device="cpu")
                self._cross_encoder_cache[f"{fallback_model}_cpu"] = self.cross
            except Exception as e2:
                logger.error(f"Erreur chargement fallback: {e2}")
                self.cross = None

    def _cosine(self, a, b):
        """Calcule la similarité cosinus entre deux vecteurs."""
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
        """Score de pertinence via LLM."""
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
        """Reranke les documents récupérés."""
        docs = self.retriever.invoke(query)
        if not docs or not settings.RERANK_ENABLED:
            return docs

        top_k = min(settings.RERANK_TOP_K, len(docs))

        if settings.RERANK_STRATEGY == "llm":
            scores = [self._llm_score(query, d.page_content) for d in docs[:top_k]]

        elif settings.RERANK_STRATEGY == "cross" and self.cross is not None:
            pairs = [(query, d.page_content) for d in docs[:top_k]]
            scores = self.cross.predict(pairs)
            if not isinstance(scores, list):
                scores = list(scores)

        else:
            # Fallback vers embedding similarity
            query_emb = self.embeddings.embed_query(query)
            doc_embs = self.embeddings.embed_documents([d.page_content for d in docs[:top_k]])
            scores = [self._cosine(query_emb, emb) for emb in doc_embs]

        # Scorer et trier
        scored = list(zip(docs[:top_k], scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        # Log des scores pour debug
        if scored:
            top_score = scored[0][1]
            avg_score = sum(s for _, s in scored) / len(scored)
            logger.debug(f"Rerank: top_score={top_score:.3f}, avg={avg_score:.3f}")

        reranked = [d for d, _ in scored] + docs[top_k:]

        # Ajouter le score de reranking dans les metadata
        for doc, score in scored:
            doc.metadata["rerank_score"] = float(score)

        return reranked

    def get_relevant_documents(self, query: str):
        """Alias pour compatibilité LangChain."""
        return self.invoke(query)