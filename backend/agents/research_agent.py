from typing import Dict, List
from langchain_core.documents import Document
from langchain_mistralai import ChatMistralAI
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)

class ResearchAgent:
    def __init__(self):
        """
        Initialiser l'agent de recherche avec Mistral ChatMistralAI.
        """

        logger.info("Initialisation de ResearchAgent avec Mistral ChatMistralAI...")
        self.model = ChatMistralAI(
            model=settings.MODEL_ID,
            api_key=settings.MISTRALAI_API_KEY,
            temperature=0,  # Déterministe pour éviter les hallucinations
            max_tokens=500,
            timeout=settings.LLM_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
        )
        logger.info("ModelInference initialisé avec succès.")

    def sanitize_response(self, response_text: str) -> str:
        """
        Nettoyer la réponse du LLM en supprimant les espaces inutiles.
        """
        return response_text.strip()

    def generate_prompt(self, question: str, context: str) -> str:
        """
        Générer un prompt structuré pour le LLM afin de générer une réponse précise et factuelle.
        """
        prompt = f"""Vous êtes un assistant IA factuel et rigoureux.

**RÈGLES STRICTES:**
1. Répondez UNIQUEMENT avec des informations EXPLICITEMENT présentes dans le contexte
2. Ne faites AUCUNE supposition, inférence ou extrapolation
3. Si l'information n'est PAS dans le contexte, répondez: "Cette information n'est pas disponible dans le document."
4. Citez les chiffres et faits EXACTEMENT comme ils apparaissent
5. N'ajoutez JAMAIS de connaissances externes
6. Chaque passage du contexte est numéroté. Après CHAQUE affirmation, indiquez entre
   crochets le ou les numéros des passages qui la soutiennent : [1] ou [2][5].
   N'utilisez JAMAIS un numéro qui n'apparaît pas dans le contexte, et n'affirmez
   rien qui ne puisse être rattaché à un passage.

**Question:** {question}

**Contexte (seule source autorisée, passages numérotés):**
{context}

**Réponse (basée UNIQUEMENT sur le contexte ci-dessus, avec citations [n]):**"""
        return prompt

    @staticmethod
    def build_numbered_context(documents: List[Document]) -> tuple:
        """
        Numérote les passages transmis au modèle et renvoie (contexte, citations).

        Le contexte préfixe chaque extrait par [n] et son document d'origine, pour que
        le modèle puisse citer. `citations` est la table de correspondance renvoyée au
        frontend : un dict par passage avec son numéro, son document, sa page si elle
        est connue (seul le pipeline FinanceBench pose `page`), et un extrait court.
        """
        import os

        parts = []
        citations = []
        for i, doc in enumerate(documents, start=1):
            meta = getattr(doc, "metadata", None) or {}
            source = meta.get("doc_name") or meta.get("source") or "document"
            name = os.path.splitext(os.path.basename(str(source)))[0]
            page = meta.get("page")
            locator = f"{name}, p. {int(page) + 1}" if page is not None else name

            parts.append(f"[{i}] ({locator})\n{doc.page_content}")
            citations.append({
                "n": i,
                "source": name,
                "page": int(page) + 1 if page is not None else None,
                "locator": locator,
                "excerpt": " ".join(doc.page_content.split())[:280],
            })
        return "\n\n".join(parts), citations

    def generate(self, question: str, documents: List[Document]) -> Dict:
        """
        Générer une réponse initiale en utilisant les documents fournis.
        """
        logger.debug(f"ResearchAgent.generate appelé avec question='{question}' et {len(documents)} documents.")

        # Numéroter les passages : le modèle doit pouvoir rattacher chaque affirmation
        # à un extrait précis (règle 6 du prompt), et le frontend afficher la source
        # derrière chaque marqueur [n].
        context, citations = self.build_numbered_context(documents)
        logger.debug(f"Longueur du contexte combiné: {len(context)} caractères, {len(citations)} passages numérotés.")

        # Créer un prompt pour le LLM
        prompt = self.generate_prompt(question, context)
        logger.debug("Prompt créé pour le LLM.")

        # Appeler le LLM pour générer la réponse
        try:
            logger.debug("Envoi du prompt au modèle...")
            response = self.model.invoke(prompt)
            logger.debug("Réponse du LLM reçue.")
        except Exception as e:
            logger.error(f"Erreur lors de l'inférence du modèle: {e}")
            raise RuntimeError("Échec de la génération de réponse en raison d'une erreur de modèle.") from e

        # Extraire et traiter la réponse du LLM
        try:
            llm_response = response.content.strip()
            logger.debug(f"Réponse brute du LLM:\n{llm_response}")
        except (IndexError, KeyError) as e:
            logger.error(f"Structure de réponse inattendue: {e}")
            llm_response = "Je ne peux pas répondre à cette question basée sur les documents fournis."

        # Nettoyer la réponse
        draft_answer = self.sanitize_response(llm_response) if llm_response else "Je ne peux pas répondre à cette question basée sur les documents fournis."

        logger.debug(f"Réponse générée: {draft_answer}")

        return {
            "draft_answer": draft_answer,
            "context_used": context,
            "citations": citations,
        }
