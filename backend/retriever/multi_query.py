"""
Multi-Query Retrieval.
Génère plusieurs reformulations de la question pour améliorer le recall.
"""
from typing import List, Set
from langchain_core.documents import Document
from langchain_mistralai import ChatMistralAI
from ..config.settings import settings
from ..utils.logging import logger


MULTI_QUERY_PROMPT = """Tu es un assistant spécialisé dans la reformulation de questions pour la recherche documentaire.

Génère {count} reformulations différentes de la question suivante pour améliorer la recherche.
Chaque reformulation doit :
- Garder le même sens que la question originale
- Utiliser des synonymes ou structures différentes
- Être concise et claire

Question originale: {question}

Réponds UNIQUEMENT avec les {count} reformulations, une par ligne, sans numérotation ni explication."""


class MultiQueryRetriever:
    """
    Retriever qui génère plusieurs reformulations de la question,
    exécute chaque query, et fusionne les résultats.
    """

    def __init__(self, base_retriever, llm=None):
        """
        Args:
            base_retriever: Le retriever de base
            llm: LLM pour générer les reformulations (optionnel)
        """
        self.retriever = base_retriever
        self.llm = llm
        self.enabled = settings.MULTI_QUERY_ENABLED
        self.query_count = settings.MULTI_QUERY_COUNT

    def _get_llm(self):
        """Initialise le LLM si nécessaire."""
        if self.llm is None:
            self.llm = ChatMistralAI(
                model=settings.MODEL_ID,
                api_key=settings.MISTRALAI_API_KEY,
                temperature=0.7,  # Un peu de variabilité pour les reformulations
                max_tokens=500,
            )
        return self.llm

    def _generate_queries(self, question: str) -> List[str]:
        """
        Génère des reformulations de la question.

        Args:
            question: La question originale

        Returns:
            Liste de questions (originale + reformulations)
        """
        if not self.enabled or self.query_count <= 1:
            return [question]

        try:
            llm = self._get_llm()
            prompt = MULTI_QUERY_PROMPT.format(
                count=self.query_count,
                question=question
            )
            response = llm.invoke(prompt)
            content = response.content.strip()

            # Parser les reformulations
            reformulations = [
                line.strip()
                for line in content.split("\n")
                if line.strip() and not line.strip().startswith(("-", "*", "#"))
            ]

            # Ajouter la question originale en premier
            queries = [question] + reformulations[:self.query_count]

            logger.debug(f"MultiQuery: {len(queries)} queries générées")
            return queries

        except Exception as e:
            logger.warning(f"MultiQuery: erreur génération, utilisation query originale: {e}")
            return [question]

    def _deduplicate_docs(self, all_docs: List[Document]) -> List[Document]:
        """
        Déduplique les documents par contenu.

        Args:
            all_docs: Liste de tous les documents récupérés

        Returns:
            Liste de documents uniques
        """
        seen_content: Set[str] = set()
        unique_docs: List[Document] = []

        for doc in all_docs:
            # Utiliser un hash du contenu pour la déduplication
            content_hash = hash(doc.page_content[:500])  # Premiers 500 chars
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_docs.append(doc)

        return unique_docs

    def invoke(self, query: str) -> List[Document]:
        """
        Exécute la recherche multi-query.

        Args:
            query: La question originale

        Returns:
            Liste de documents dédupliqués
        """
        if not self.enabled:
            return self.retriever.invoke(query)

        # Générer les reformulations
        queries = self._generate_queries(query)

        # Exécuter les queries en parallèle
        all_docs: List[Document] = []

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch_docs(q: str) -> List[Document]:
            try:
                return self.retriever.invoke(q)
            except Exception as e:
                logger.warning(f"MultiQuery: erreur pour query '{q[:50]}...': {e}")
                return []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(fetch_docs, q): q for q in queries}
            for future in as_completed(futures):
                all_docs.extend(future.result())

        # Dédupliquer
        unique_docs = self._deduplicate_docs(all_docs)

        logger.info(
            f"MultiQuery: {len(queries)} queries -> "
            f"{len(all_docs)} docs -> {len(unique_docs)} uniques"
        )

        return unique_docs

    def get_relevant_documents(self, query: str) -> List[Document]:
        """Alias pour compatibilité LangChain."""
        return self.invoke(query)
