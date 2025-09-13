from langchain_mistralai import ChatMistralAI
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)

class RelevanceChecker:
    def __init__(self):
        self.model = ChatMistralAI(
            model=settings.MODEL_ID,
            api_key=settings.MISTRALAI_API_KEY,
            temperature=0,
            max_tokens=10,
        )

    def check(self, question: str, retriever, k=3) -> str:
        """
        1. Récupérer les k premiers chunks de documents depuis le récupérateur global.
        2. Les combiner en une seule chaîne de texte.
        3. Passer ce texte + question au LLM pour classification.

        Retourne: "CAN_ANSWER", "PARTIAL", ou "NO_MATCH".
        """

        logger.debug(f"RelevanceChecker.check appelé avec question='{question}' et k={k}")

        # Récupérer les chunks de documents depuis le récupérateur d'ensemble
        top_docs = retriever.invoke(question)
        if not top_docs:
            logger.debug("Aucun document retourné par retriever.invoke(). Classification comme NO_MATCH.")
            return "NO_MATCH"

        # Combiner les k premiers chunks de texte en une seule chaîne
        document_content = "\n\n".join(doc.page_content for doc in top_docs[:k])

        # Créer un prompt pour le LLM afin de classifier la pertinence
        prompt = f"""
        Vous êtes un vérificateur de pertinence IA entre la question d'un utilisateur et le contenu de document fourni.

        **Instructions:**
        - Classifiez dans quelle mesure le contenu du document répond à la question de l'utilisateur.
        - Répondez avec un seul des labels suivants: CAN_ANSWER, PARTIAL, NO_MATCH.
        - N'incluez aucun texte ou explication supplémentaire.

        **Labels:**
        1) "CAN_ANSWER": Les passages contiennent suffisamment d'informations explicites pour répondre complètement à la question.
        2) "PARTIAL": Les passages mentionnent ou discutent le sujet de la question mais ne fournissent pas tous les détails nécessaires pour une réponse complète.
        3) "NO_MATCH": Les passages ne discutent ni ne mentionnent le sujet de la question du tout.

        **Important:** Si les passages mentionnent ou font référence au sujet ou à la période de la question de quelque manière que ce soit, même si incomplète, répondez avec "PARTIAL" au lieu de "NO_MATCH".

        **Question:** {question}
        **Passages:** {document_content}

        **Répondez UNIQUEMENT avec un des labels suivants: CAN_ANSWER, PARTIAL, NO_MATCH**
        """

        # Appeler le LLM
        try:
            response = self.model.invoke(prompt)
        except Exception as e:
            logger.error(f"Erreur lors de l'inférence du modèle: {e}")
            return "NO_MATCH"

        # Extraire le contenu de la réponse
        try:
            llm_response = response.content.strip()
            logger.debug(f"Réponse du LLM: {llm_response}")
        except (IndexError, KeyError) as e:
            logger.error(f"Structure de réponse inattendue: {e}")
            return "NO_MATCH"

        print(f"Réponse du vérificateur: {llm_response}")

        # Valider la réponse
        valid_labels = {"CAN_ANSWER", "PARTIAL", "NO_MATCH"}
        if llm_response not in valid_labels:
            logger.debug("Le LLM n'a pas répondu avec un label valide. Forçage de 'NO_MATCH'.")
            classification = "NO_MATCH"
        else:
            logger.debug(f"Classification reconnue comme '{llm_response}'.")
            classification = llm_response

        return classification
