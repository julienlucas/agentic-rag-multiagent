"""
Sentence Window Retriever.
Transforme les chunks de phrases en chunks avec contexte de fenêtre.
"""
from typing import List
from langchain_core.documents import Document
from ..config.settings import settings
from ..utils.logging import logger


class SentenceWindowRetriever:
    """
    Retriever qui étend les chunks de phrases avec leur contexte de fenêtre.

    Workflow:
    1. Récupère les documents (phrases) du retriever de base
    2. Remplace le contenu de chaque doc par son window_context si disponible
    3. Déduplique les fenêtres qui se chevauchent
    """

    def __init__(self, base_retriever):
        """
        Args:
            base_retriever: Le retriever de base qui retourne des phrases
        """
        self.retriever = base_retriever
        self.enabled = settings.CHUNKING_STRATEGY.lower() == "sentence_window"

    def _expand_to_window(self, doc: Document) -> Document:
        """
        Étend un chunk de phrase à son contexte de fenêtre.

        Args:
            doc: Document contenant une phrase avec window_context en metadata

        Returns:
            Document avec le contenu étendu
        """
        window_context = doc.metadata.get("window_context")

        if window_context:
            # Utiliser le contexte de fenêtre au lieu de la phrase seule
            return Document(
                page_content=window_context,
                metadata={
                    **doc.metadata,
                    "original_sentence": doc.page_content,
                    "expanded": True,
                }
            )
        return doc

    def _deduplicate_windows(self, docs: List[Document]) -> List[Document]:
        """
        Déduplique les fenêtres qui se chevauchent.

        Args:
            docs: Liste de documents avec fenêtres potentiellement chevauchantes

        Returns:
            Liste de documents dédupliqués
        """
        seen_content = set()
        unique_docs = []

        for doc in docs:
            # Hash basé sur le début du contenu pour détecter les chevauchements
            content_start = doc.page_content[:200]
            if content_start not in seen_content:
                seen_content.add(content_start)
                unique_docs.append(doc)

        return unique_docs

    def invoke(self, query: str) -> List[Document]:
        """
        Exécute la recherche et étend les résultats avec le contexte de fenêtre.

        Args:
            query: La question

        Returns:
            Liste de documents avec contexte étendu
        """
        docs = self.retriever.invoke(query)

        if not self.enabled or not docs:
            return docs

        # Étendre chaque document à son contexte de fenêtre
        expanded_docs = [self._expand_to_window(doc) for doc in docs]

        # Dédupliquer les fenêtres chevauchantes
        unique_docs = self._deduplicate_windows(expanded_docs)

        expanded_count = sum(1 for d in unique_docs if d.metadata.get("expanded"))
        logger.info(
            f"SentenceWindowRetriever: {len(docs)} docs -> "
            f"{len(unique_docs)} uniques ({expanded_count} étendus)"
        )

        return unique_docs

    def get_relevant_documents(self, query: str) -> List[Document]:
        """Alias pour compatibilité LangChain."""
        return self.invoke(query)
