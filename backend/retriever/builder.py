import os
from langchain_community.vectorstores import Chroma
from langchain_mistralai import ChatMistralAI
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
from .document_router import DocumentRouter, DocumentRouterRetriever, ScopedHybridRetriever

hf_token = os.environ.get("HF_TOKEN")
if hf_token:
    os.environ["HUGGINGFACE_HUB_TOKEN"] = hf_token


class RetrieverBuilder:
    def __init__(self):
        """Initialiser le constructeur de récupérateur avec les embeddings."""
        # Utiliser la factory pour les embeddings (BGE-M3 ou Mistral)
        self.embeddings = get_embeddings()
        self.llm = ChatMistralAI(
            model=settings.MODEL_SMALL_ID,
            api_key=settings.MISTRALAI_API_KEY,
            temperature=0,
            max_tokens=10,
            timeout=settings.LLM_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
        )
        # LLM "texte" pour les composants qui doivent produire plusieurs lignes
        # (reformulations multi-query, noms de documents du routeur). Le self.llm
        # ci-dessus est bridé à 10 tokens : passé à MultiQuery, il tronquait les
        # reformulations à quelques mots.
        self.llm_text = ChatMistralAI(
            model=settings.MODEL_SMALL_ID,
            api_key=settings.MISTRALAI_API_KEY,
            temperature=0,
            max_tokens=200,
            timeout=settings.LLM_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    def build_hybrid_retriever(self, docs, persist_directory: str = None):
        """
        Construire un récupérateur hybride utilisant BM25 et la récupération basée sur les vecteurs.

        Args:
            docs: Les documents (chunks) à indexer.
            persist_directory: Si fourni, la collection Chroma est persistée sur disque et
                réutilisée telle quelle si elle contient déjà tous les vecteurs. Utilisé par
                l'évaluation FinanceBench pour ne pas ré-embedder des milliers de chunks à
                chaque run. Par défaut (None), le comportement est inchangé : store en mémoire.
        """
        try:
            # Créer le récupérateur BM25 d'abord
            bm25 = BM25Retriever.from_documents(docs)
            bm25.k = settings.BM25_K
            logger.info("Récupérateur BM25 créé avec succès.")

            try:
                if persist_directory:
                    # Collection persistée : réutilisée si déjà complète, sinon (re)construite.
                    vector_store = Chroma(
                        persist_directory=persist_directory,
                        embedding_function=self.embeddings,
                        collection_name=settings.CHROMA_COLLECTION_NAME,
                        collection_metadata={"hnsw:space": settings.VECTOR_SPACE},
                    )
                    existing = vector_store._collection.count()
                    if 0 < existing < len(docs):
                        # Indexation précédente interrompue : ré-ajouter produirait des doublons.
                        logger.warning(
                            f"Collection persistée incomplète ({existing}/{len(docs)}), reconstruction."
                        )
                        vector_store.delete_collection()
                        vector_store = Chroma(
                            persist_directory=persist_directory,
                            embedding_function=self.embeddings,
                            collection_name=settings.CHROMA_COLLECTION_NAME,
                            collection_metadata={"hnsw:space": settings.VECTOR_SPACE},
                        )
                        existing = 0
                    if existing == 0:
                        logger.info(f"Indexation de {len(docs)} chunks dans la collection persistée...")
                        vector_store.add_documents(docs)
                    else:
                        logger.info(f"Collection persistée réutilisée ({existing} vecteurs).")
                else:
                    # Store en mémoire par session : évite l'accumulation de vecteurs
                    # entre uploads (qui gonflait la collection et polluait les résultats).
                    vector_store = Chroma.from_documents(
                        documents=docs,
                        embedding=self.embeddings,
                        collection_metadata={"hnsw:space": settings.VECTOR_SPACE},
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

                if settings.DOCUMENT_ROUTING_ENABLED:
                    # Même fusion RRF, mais capable de se restreindre au périmètre posé
                    # par DocumentRouterRetriever (BM25 sur le sous-ensemble + filtre Chroma).
                    hybrid_retriever = ScopedHybridRetriever(
                        docs, vector_store, weights,
                        bm25_k=settings.BM25_K, vector_k=settings.VECTOR_SEARCH_K,
                    )
                else:
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
                    retriever = MultiQueryRetriever(retriever, self.llm_text)
                    logger.info("Multi-Query retriever activé.")

                # Query Decomposition (décompose les questions complexes)
                if settings.QUERY_DECOMPOSITION_ENABLED:
                    retriever = QueryDecompositionRetriever(retriever, self.llm)
                    logger.info("Query Decomposition retriever activé.")

                # Reranker (améliore la précision du ranking)
                if settings.RERANK_ENABLED:
                    retriever = RerankRetriever(retriever, self.embeddings, self.llm)
                    logger.info(f"Reranker activé: {settings.RERANK_MODEL}")

                # Contextual Compression (filtre le contenu non pertinent)
                if settings.CONTEXTUAL_COMPRESSION_ENABLED:
                    retriever = ContextualCompressionRetriever(retriever, self.llm)
                    logger.info("Contextual Compression activé.")

                # Routage par document (le plus externe : décide du périmètre avant tout)
                if settings.DOCUMENT_ROUTING_ENABLED:
                    retriever = self._wrap_with_router(retriever, docs)

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
                    retriever = MultiQueryRetriever(retriever, self.llm_text)
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


    def _wrap_with_router(self, retriever, docs):
        """Ajoute le routage par document si plusieurs sources sont indexées."""
        sources = list(dict.fromkeys(
            str(d.metadata.get("source")) for d in docs if d.metadata.get("source")
        ))
        if len(sources) <= 1:
            logger.info("Routage par document: une seule source, désactivé.")
            return retriever
        router = DocumentRouter(sources, llm=self.llm_text)
        logger.info(f"Routage par document activé sur {len(sources)} sources.")
        return DocumentRouterRetriever(retriever, router)


class RerankRetriever:
    """
    Reranker utilisant l'API Cohere Rerank.
    Top-tier performance, excellent multilingue.
    """

    def __init__(self, retriever, embeddings, llm):
        self.retriever = retriever
        self.embeddings = embeddings
        self.llm = llm
        self._client = None
        logger.info(f"Cohere Reranker initialisé: {settings.RERANK_MODEL}")

    @property
    def client(self):
        """Lazy loading du client Cohere."""
        if self._client is None:
            import cohere
            self._client = cohere.Client(api_key=settings.COHERE_API_KEY)
        return self._client

    def invoke(self, query: str):
        """Reranke les documents via l'API Cohere Rerank."""
        return self.rerank(query, self.retriever.invoke(query))

    def rerank(self, query: str, docs, top_n: int = None):
        """
        Reclasse `docs` selon `query`. Exposé séparément de invoke() pour que la recherche
        corrective puisse reclasser un ensemble fusionné contre la question d'ORIGINE :
        classés selon les requêtes réécrites, les passages ajoutés éjectaient des preuves
        que le retrieval initial avait bien trouvées.
        """
        if not docs or not settings.RERANK_ENABLED:
            return docs

        # Cap le nombre de candidats envoyés à Cohere pour limiter la latence.
        # Multi-query peut produire 100-200 docs uniques, ce qui ralentit
        # inutilement le rerank sans gain de qualité notable au-delà de ~40.
        MAX_RERANK_CANDIDATES = 40
        if len(docs) > MAX_RERANK_CANDIDATES:
            docs = docs[:MAX_RERANK_CANDIDATES]
        num_to_rerank = len(docs)

        try:
            # Cohere rerank a une limite de ~10000 docs, largement suffisant
            response = self.client.rerank(
                model=settings.RERANK_MODEL,
                query=query,
                documents=[d.page_content for d in docs],
                top_n=min(top_n or settings.RERANK_TOP_K, num_to_rerank),
            )

            # Reconstruire la liste ordonnée par score de reranking
            reranked_docs = []
            for result in response.results:
                doc = docs[result.index]
                doc.metadata["rerank_score"] = result.relevance_score
                reranked_docs.append(doc)

            # Log des scores pour debug
            if response.results:
                top_score = response.results[0].relevance_score
                avg_score = sum(r.relevance_score for r in response.results) / len(response.results)
                logger.info(
                    f"Cohere Rerank: {num_to_rerank} docs -> top {len(reranked_docs)}, "
                    f"top_score={top_score:.3f}, avg={avg_score:.3f}"
                )

            return reranked_docs

        except Exception as e:
            logger.warning(f"Erreur Cohere Rerank: {e}, retour des docs non rerankés")
            return docs

    def get_relevant_documents(self, query: str):
        """Alias pour compatibilité LangChain."""
        return self.invoke(query)