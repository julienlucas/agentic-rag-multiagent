"""
Recherche corrective (agentique).

Quand le vérificateur de pertinence juge que les passages récupérés ne répondent pas à la
question, on ne refuse pas tout de suite : on réécrit la question dans le vocabulaire
qu'emploie réellement le document, on relance la recherche, et on fusionne.

C'est ce qui traite les échecs de type « la question ne parle pas la langue du document » :
« legal battles » alors que le 10-K dit *litigation* / *lawsuits* ; « gross margin » pour une
banque qui ne publie que *pretax income* ; « effective tax rate » qu'il faut aller chercher
sous *provision for income taxes*.
"""
import hashlib
from typing import Dict, List, Optional

from langchain_core.documents import Document
from langchain_mistralai import ChatMistralAI

from ..config.settings import settings
from ..utils.logging import logger


REWRITE_PROMPT = """Tu es un analyste financier qui connaît parfaitement la structure des rapports annuels (10-K, 10-Q, rapports d'activité).

La recherche documentaire n'a PAS trouvé de passage répondant à la question ci-dessous. Génère {count} requêtes de recherche alternatives, en anglais, qui emploient le VOCABULAIRE EXACT qu'on trouve dans un tel rapport :
- les intitulés de lignes comptables (ex. "provision for income taxes", "income before income taxes", "total revenues", "cost of sales", "customer deposits")
- les titres de sections (ex. "Legal Proceedings", "Segment Information", "Liquidity and Capital Resources", "Risk Factors")
- les synonymes du jargon financier (ex. "legal battles" -> "litigation", "lawsuits" ; "gross margin" -> "cost of revenues", "gross profit" ; "geographies" -> "geographic regions", "segment")
- si la question porte sur une métrique qui doit être CALCULÉE (marge, ratio, variation), cible les lignes de base nécessaires au calcul.

Chaque requête doit inclure le nom de l'entreprise ou de l'entité mentionnée dans la question, si elle en mentionne une.

Question : {question}

Réponds UNIQUEMENT avec les {count} requêtes, une par ligne, sans numérotation ni explication."""


class CorrectiveRetrieval:
    """Réécrit la question dans le lexique du document et relance la recherche."""

    def __init__(self, llm=None):
        self.llm = llm
        self.query_count = settings.CORRECTIVE_QUERY_COUNT

    def _get_llm(self):
        if self.llm is None:
            self.llm = ChatMistralAI(
                model=settings.MODEL_SMALL_ID,
                api_key=settings.MISTRALAI_API_KEY,
                temperature=0,
                max_tokens=300,
                timeout=settings.LLM_TIMEOUT,
                max_retries=settings.LLM_MAX_RETRIES,
            )
        return self.llm

    def rewrite(self, question: str) -> List[str]:
        """Génère des requêtes alternatives dans le vocabulaire des rapports financiers."""
        prompt = REWRITE_PROMPT.format(count=self.query_count, question=question)
        try:
            content = self._get_llm().invoke(prompt).content.strip()
        except Exception as e:
            logger.warning(f"CorrectiveRetrieval: réécriture impossible ({e})")
            return []
        queries = []
        for line in content.splitlines():
            line = line.strip().lstrip("-•*0123456789.) ").strip().strip('"')
            if line and line.lower() != question.lower():
                queries.append(line)
        return queries[: self.query_count]

    @staticmethod
    def _merge(doc_lists: List[List[Document]], top_n: int) -> List[Document]:
        """
        Fusion RRF (Reciprocal Rank Fusion) de plusieurs listes ordonnées, dédupliquée
        par contenu. Un passage trouvé par plusieurs requêtes remonte.
        """
        K = 60
        scores: Dict[str, float] = {}
        docs: Dict[str, Document] = {}
        for lst in doc_lists:
            for rank, doc in enumerate(lst, start=1):
                key = hashlib.md5(doc.page_content.encode()).hexdigest()
                scores[key] = scores.get(key, 0.0) + 1.0 / (K + rank)
                docs.setdefault(key, doc)
        ordered = sorted(scores, key=scores.get, reverse=True)
        return [docs[k] for k in ordered[:top_n]]

    def expand(
        self,
        question: str,
        retriever,
        current_docs: List[Document],
        scope: Optional[List[str]] = None,
        top_n: int = 30,
    ) -> Dict:
        """
        Relance la recherche avec les requêtes réécrites et fusionne avec les documents
        déjà récupérés. Retourne {"documents": [...], "queries": [...]}.

        Si le retriever supporte un périmètre (routage par document), on le conserve :
        une requête réécrite peut ne plus contenir le nom de l'entreprise.
        """
        queries = self.rewrite(question)
        if not queries:
            return {"documents": current_docs, "queries": []}

        def search(q: str) -> List[Document]:
            try:
                if scope is not None and hasattr(retriever, "invoke_with_scope"):
                    return retriever.invoke_with_scope(q, scope)
                return retriever.invoke(q)
            except Exception as e:
                logger.warning(f"CorrectiveRetrieval: échec de la requête '{q[:60]}': {e}")
                return []

        new_lists = [search(q) for q in queries]

        # Fusion CONSERVATRICE : le haut du classement initial est intouchable.
        # La correction ne peut qu'ajouter après lui — jamais éjecter une preuve
        # que le retrieval initial avait déjà bien classée.
        protect = max(0, settings.CORRECTIVE_PROTECT_TOP)
        head = current_docs[:protect]
        head_keys = {hashlib.md5(d.page_content.encode()).hexdigest() for d in head}
        tail = [
            d for d in self._merge([current_docs[protect:]] + new_lists, top_n)
            if hashlib.md5(d.page_content.encode()).hexdigest() not in head_keys
        ]
        merged = head + tail[: max(0, top_n - len(head))]
        logger.info(
            f"CorrectiveRetrieval: {len(queries)} requêtes réécrites -> "
            f"{sum(len(l) for l in new_lists)} docs -> top-{protect} initial protégé "
            f"+ {len(merged) - len(head)} fusionnés"
        )
        return {"documents": merged, "queries": queries}
