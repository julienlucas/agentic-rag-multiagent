"""
Parent-Child Retriever.
Récupère les children matchés et retourne les parents pour plus de contexte.
"""
from typing import List, Dict, Set
from langchain_core.documents import Document
from ..config.settings import settings
from ..utils.logging import logger


class ParentChildRetriever:
    """
    Wrapper de retriever qui récupère les children mais retourne les parents.
    Permet une recherche précise sur les petits chunks tout en retournant
    le contexte complet via les parents.
    """

    def __init__(self, base_retriever, return_parents: bool = True):
        """
        Args:
            base_retriever: Le retriever de base (hybrid, vector, etc.)
            return_parents: Si True, retourne les parents; sinon retourne les children
        """
        self.retriever = base_retriever
        self.return_parents = return_parents and settings.PARENT_CHILD_ENABLED

    def invoke(self, query: str) -> List[Document]:
        """
        Exécute la recherche et retourne les parents des children matchés.

        Args:
            query: La question/requête

        Returns:
            Liste de documents (parents si PARENT_CHILD_ENABLED, sinon children)
        """
        # Récupérer les children depuis le retriever de base
        children = self.retriever.invoke(query)

        if not self.return_parents:
            return children

        # Extraire les parents uniques
        parents_map: Dict[str, Document] = {}
        children_without_parent: List[Document] = []

        for child in children:
            parent_id = child.metadata.get("parent_id")
            parent_content = child.metadata.get("parent_content")

            if parent_id and parent_content:
                if parent_id not in parents_map:
                    # Créer un document parent
                    parent_metadata = {
                        k: v for k, v in child.metadata.items()
                        if k not in ("parent_id", "parent_content", "is_child")
                    }
                    parent_metadata["parent_id"] = parent_id
                    parent_metadata["matched_children_count"] = 1

                    parents_map[parent_id] = Document(
                        page_content=parent_content,
                        metadata=parent_metadata
                    )
                else:
                    # Incrémenter le compteur de children matchés
                    parents_map[parent_id].metadata["matched_children_count"] += 1
            else:
                # Pas de parent, garder le child
                children_without_parent.append(child)

        # Trier les parents par nombre de children matchés (plus de matches = plus pertinent)
        sorted_parents = sorted(
            parents_map.values(),
            key=lambda d: d.metadata.get("matched_children_count", 0),
            reverse=True
        )

        # Combiner parents et children orphelins
        results = sorted_parents + children_without_parent

        logger.debug(
            f"ParentChildRetriever: {len(children)} children -> "
            f"{len(sorted_parents)} parents + {len(children_without_parent)} orphelins"
        )

        return results

    def get_relevant_documents(self, query: str) -> List[Document]:
        """Alias pour compatibilité LangChain."""
        return self.invoke(query)
