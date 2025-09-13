from typing import Dict, List
from langchain.schema import Document
from langchain_mistralai import ChatMistralAI
from ..config.settings import settings

class ResearchAgent:
    def __init__(self):
        """
        Initialiser l'agent de recherche avec Mistral ChatMistralAI.
        """

        print("Initialisation de ResearchAgent avec Mistral ChatMistralAI...")
        self.model = ChatMistralAI(
            model=settings.MODEL_ID,
            api_key=settings.MISTRALAI_API_KEY,
            temperature=0.3,
            max_tokens=300,
        )
        print("ModelInference initialisé avec succès.")

    def sanitize_response(self, response_text: str) -> str:
        """
        Nettoyer la réponse du LLM en supprimant les espaces inutiles.
        """
        return response_text.strip()

    def generate_prompt(self, question: str, context: str) -> str:
        """
        Générer un prompt structuré pour le LLM afin de générer une réponse précise et factuelle.
        """
        prompt = f"""
        Vous êtes un assistant IA conçu pour fournir des réponses précises et factuelles basées sur le contexte donné.

        **Instructions:**
        - Répondez à la question suivante en utilisant uniquement le contexte fourni.
        - Soyez clair, concis et factuel.
        - Retournez autant d'informations que vous pouvez obtenir du contexte.

        **Question:** {question}
        **Contexte:**
        {context}

        **Fournissez votre réponse ci-dessous:**
        """
        return prompt

    def generate(self, question: str, documents: List[Document]) -> Dict:
        """
        Générer une réponse initiale en utilisant les documents fournis.
        """
        print(f"ResearchAgent.generate appelé avec question='{question}' et {len(documents)} documents.")

        # Combiner le contenu des documents principaux en une seule chaîne
        context = "\n\n".join([doc.page_content for doc in documents])
        print(f"Longueur du contexte combiné: {len(context)} caractères.")

        # Créer un prompt pour le LLM
        prompt = self.generate_prompt(question, context)
        print("Prompt créé pour le LLM.")

        # Appeler le LLM pour générer la réponse
        try:
            print("Envoi du prompt au modèle...")
            response = self.model.invoke(prompt)
            print("Réponse du LLM reçue.")
        except Exception as e:
            print(f"Erreur lors de l'inférence du modèle: {e}")
            raise RuntimeError("Échec de la génération de réponse en raison d'une erreur de modèle.") from e

        # Extraire et traiter la réponse du LLM
        try:
            llm_response = response.content.strip()
            print(f"Réponse brute du LLM:\n{llm_response}")
        except (IndexError, KeyError) as e:
            print(f"Structure de réponse inattendue: {e}")
            llm_response = "Je ne peux pas répondre à cette question basée sur les documents fournis."

        # Nettoyer la réponse
        draft_answer = self.sanitize_response(llm_response) if llm_response else "Je ne peux pas répondre à cette question basée sur les documents fournis."

        print(f"Réponse générée: {draft_answer}")

        return {
            "draft_answer": draft_answer,
            "context_used": context
        }
