"""
Stratégies de chunking pour le traitement des documents.
Inclut: Recursive, Semantic, et Parent-Child.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import uuid

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ..config.settings import settings
from ..utils.logging import logger


class ChunkingStrategy(ABC):
    """Interface de base pour les stratégies de chunking."""

    @abstractmethod
    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Découpe le texte en chunks."""
        pass


class RecursiveChunkingStrategy(ChunkingStrategy):
    """
    Stratégie de chunking récursive standard.
    Coupe aux caractères de séparation (\\n\\n, \\n, etc.)
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        separators: List[str] = None
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
        )

    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Découpe le texte avec la méthode récursive."""
        metadata = metadata or {}
        docs = self._splitter.create_documents([text], [metadata])
        logger.debug(f"RecursiveChunking: {len(docs)} chunks créés")
        return docs


class SemanticChunkingStrategy(ChunkingStrategy):
    """
    Stratégie de chunking sémantique.
    Utilise les embeddings pour détecter les frontières sémantiques.
    """

    def __init__(
        self,
        embeddings=None,
        breakpoint_threshold: float = 0.5,
        min_chunk_size: int = 100,
        max_chunk_size: int = None
    ):
        self.embeddings = embeddings
        self.breakpoint_threshold = breakpoint_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size or settings.CHUNK_SIZE

    def _compute_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Calcule la similarité cosinus entre deux embeddings."""
        dot = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = sum(a * a for a in emb1) ** 0.5
        norm2 = sum(b * b for b in emb2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """
        Découpe le texte aux frontières sémantiques.
        Si embeddings non fournis, fallback vers RecursiveChunking.
        """
        metadata = metadata or {}

        # Fallback si pas d'embeddings
        if self.embeddings is None:
            logger.warning("SemanticChunking: pas d'embeddings, fallback vers RecursiveChunking")
            return RecursiveChunkingStrategy().split(text, metadata)

        # Découper en phrases ou paragraphes d'abord
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [s.strip() + "." for s in text.split(". ") if s.strip()]

        if len(paragraphs) <= 1:
            return [Document(page_content=text, metadata=metadata)]

        # Calculer les embeddings des paragraphes
        try:
            embeddings = self.embeddings.embed_documents(paragraphs)
        except Exception as e:
            logger.warning(f"SemanticChunking: erreur embeddings, fallback: {e}")
            return RecursiveChunkingStrategy().split(text, metadata)

        # Trouver les points de rupture sémantique
        chunks = []
        current_chunk = [paragraphs[0]]
        current_size = len(paragraphs[0])

        for i in range(1, len(paragraphs)):
            similarity = self._compute_similarity(embeddings[i - 1], embeddings[i])

            # Si faible similarité ou chunk trop grand -> nouvelle rupture
            if (similarity < self.breakpoint_threshold and current_size >= self.min_chunk_size) or \
               current_size + len(paragraphs[i]) > self.max_chunk_size:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(Document(page_content=chunk_text, metadata=metadata.copy()))
                current_chunk = [paragraphs[i]]
                current_size = len(paragraphs[i])
            else:
                current_chunk.append(paragraphs[i])
                current_size += len(paragraphs[i])

        # Ajouter le dernier chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(Document(page_content=chunk_text, metadata=metadata.copy()))

        logger.debug(f"SemanticChunking: {len(chunks)} chunks créés")
        return chunks


class ParentChildChunkingStrategy(ChunkingStrategy):
    """
    Stratégie Parent-Child.
    Crée des petits chunks (children) pour la recherche précise,
    mais stocke la référence au parent pour retourner plus de contexte.
    """

    def __init__(
        self,
        parent_chunk_size: int = None,
        child_chunk_size: int = None,
        child_overlap: int = 50
    ):
        self.parent_chunk_size = parent_chunk_size or settings.PARENT_CHUNK_SIZE
        self.child_chunk_size = child_chunk_size or settings.CHILD_CHUNK_SIZE
        self.child_overlap = child_overlap

        self._parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.parent_chunk_size,
            chunk_overlap=100,
        )
        self._child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.child_chunk_size,
            chunk_overlap=self.child_overlap,
        )

    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """
        Crée une hiérarchie parent-child.
        Retourne les children avec metadata contenant parent_id et parent_content.
        """
        metadata = metadata or {}
        all_children = []

        # Créer les parents
        parent_docs = self._parent_splitter.create_documents([text], [metadata])

        for parent in parent_docs:
            parent_id = str(uuid.uuid4())
            parent_content = parent.page_content

            # Créer les children pour ce parent
            children = self._child_splitter.create_documents(
                [parent_content],
                [parent.metadata]
            )

            for child in children:
                child.metadata = {
                    **child.metadata,
                    "parent_id": parent_id,
                    "parent_content": parent_content,
                    "is_child": True,
                }
                all_children.append(child)

        logger.debug(f"ParentChildChunking: {len(parent_docs)} parents, {len(all_children)} children")
        return all_children


def get_chunking_strategy(embeddings=None) -> ChunkingStrategy:
    """
    Factory function pour obtenir la stratégie de chunking configurée.

    Args:
        embeddings: Instance d'embeddings (requis pour SemanticChunking)

    Returns:
        ChunkingStrategy: Instance de la stratégie configurée
    """
    strategy = settings.CHUNKING_STRATEGY.lower()

    if strategy == "semantic":
        logger.info("Utilisation du chunking sémantique")
        return SemanticChunkingStrategy(embeddings=embeddings)

    elif strategy == "parent-child" or settings.PARENT_CHILD_ENABLED:
        logger.info("Utilisation du chunking parent-child")
        return ParentChildChunkingStrategy()

    else:
        logger.info("Utilisation du chunking récursif standard")
        return RecursiveChunkingStrategy()
