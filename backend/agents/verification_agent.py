from typing import Dict, List
from langchain.schema import Document
from langchain_mistralai import ChatMistralAI
from ..config.settings import settings

class VerificationAgent:
    def __init__(self):
        """
        Initialiser l'agent de vérification avec Mistral ChatMistralAI.
        """
        # Initialiser Mistral ChatMistralAI
        print("Initialisation de VerificationAgent avec Mistral ChatMistralAI...")
        self.model = ChatMistralAI(
            model=settings.MODEL_ID,
            api_key=settings.MISTRALAI_API_KEY,
            temperature=0,
            max_tokens=200,
        )
        print("ModelInference initialisé avec succès.")

    def sanitize_response(self, response_text: str) -> str:
        """
        Nettoyer la réponse du LLM en supprimant les espaces inutiles.
        """
        return response_text.strip()

    def generate_prompt(self, answer: str, context: str) -> str:
        """
        Générer un prompt structuré pour le LLM afin de vérifier la réponse par rapport au contexte.
        """
        prompt = f"""
        Vous êtes un assistant IA conçu pour vérifier l'exactitude et la pertinence des réponses basées sur le contexte fourni.

        **Instructions:**
        - Vérifiez la réponse suivante par rapport au contexte fourni.
        - Vérifiez pour:
        1. Support factuel direct/indirect (OUI/NON)
        2. Affirmations non supportées (listez-en si présentes)
        3. Contradictions (listez-en si présentes)
        4. Pertinence par rapport à la question (OUI/NON)
        - Fournissez des détails ou explications supplémentaires si pertinent.
        - Répondez dans le format exact spécifié ci-dessous sans ajouter d'informations non liées.

        **Format:**
        Supported: OUI/NON
        Unsupported Claims: [élément1, élément2, ...]
        Contradictions: [élément1, élément2, ...]
        Relevant: OUI/NON
        Additional Details: [Toute information ou explication supplémentaire]

        **Answer:** {answer}
        **Context:**
        {context}

        **Répondez UNIQUEMENT avec le format ci-dessus.**
        """
        return prompt

    def parse_verification_response(self, response_text: str) -> Dict:
        """
        Parser la réponse de vérification du LLM en un dictionnaire structuré.
        """
        try:
            lines = response_text.split('\n')
            verification = {}
            for line in lines:
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key, value = parts
                        key = key.strip().capitalize()
                        value = value.strip()
                    else:
                        continue
                    if key in {"Supported", "Unsupported claims", "Contradictions", "Relevant", "Additional details"}:
                        if key in {"Unsupported claims", "Contradictions"}:
                            # Convert string list to actual list
                            if value.startswith('[') and value.endswith(']'):
                                items = value[1:-1].split(',')
                                # Remove any surrounding quotes and whitespace
                                items = [item.strip().strip('"').strip("'") for item in items if item.strip()]
                                verification[key] = items
                            else:
                                verification[key] = []
                        elif key == "Additional details":
                            verification[key] = value
                        else:
                            verification[key] = value.upper()
            # Ensure all keys are present
            for key in ["Supported", "Unsupported Claims", "Contradictions", "Relevant", "Additional Details"]:
                if key not in verification:
                    if key in {"Unsupported Claims", "Contradictions"}:
                        verification[key] = []
                    elif key == "Additional Details":
                        verification[key] = ""
                    else:
                        verification[key] = "NON"

            return verification
        except Exception as e:
            print(f"Erreur lors du parsing de la réponse de vérification: {e}")
            return None

    def format_verification_report(self, verification: Dict) -> str:
        """
        Formater le dictionnaire de rapport de vérification en un paragraphe lisible.
        """
        supported = verification.get("Supported", "NON")
        unsupported_claims = verification.get("Unsupported Claims", [])
        contradictions = verification.get("Contradictions", [])
        relevant = verification.get("Relevant", "NON")
        additional_details = verification.get("Additional Details", "")

        report = f"**Supporté:** {supported}\n"
        if unsupported_claims:
            report += f"**Affirmations non supportées:** {', '.join(unsupported_claims)}\n"
        else:
            report += f"**Affirmations non supportées:** Aucune\n"

        if contradictions:
            report += f"**Contradictions:** {', '.join(contradictions)}\n"
        else:
            report += f"**Contradictions:** Aucune\n"

        report += f"**Pertinent:** {relevant}\n"

        if additional_details:
            report += f"**Détails supplémentaires:** {additional_details}\n"
        else:
            report += f"**Détails supplémentaires:** Aucun\n"

        return report

    def check(self, answer: str, documents: List[Document]) -> Dict:
        """
        Vérifier la réponse par rapport aux documents fournis.
        """
        print(f"VerificationAgent.check appelé avec answer='{answer}' et {len(documents)} documents.")

        # Combiner tous les contenus de documents en une seule chaîne sans troncature
        context = "\n\n".join([doc.page_content for doc in documents])
        print(f"Longueur du contexte combiné: {len(context)} caractères.")

        # Créer un prompt pour le LLM afin de vérifier la réponse
        prompt = self.generate_prompt(answer, context)
        print("Prompt créé pour le LLM.")

        # Appeler le LLM pour générer le rapport de vérification
        try:
            print("Envoi du prompt au modèle...")
            response = self.model.invoke(prompt)
            print("Réponse du LLM reçue.")
        except Exception as e:
            print(f"Erreur lors de l'inférence du modèle: {e}")
            raise RuntimeError("Échec de la vérification de la réponse en raison d'une erreur du modèle.") from e

        # Extraire et traiter la réponse du LLM
        try:
            llm_response = response.content.strip()
            print(f"Réponse brute du LLM:\n{llm_response}")
        except (IndexError, KeyError) as e:
            print(f"Structure de réponse inattendue: {e}")
            verification_report = {
                "Supported": "NON",
                "Unsupported Claims": [],
                "Contradictions": [],
                "Relevant": "NON",
                "Additional Details": "Structure de réponse invalide du modèle."
            }
            verification_report_formatted = self.format_verification_report(verification_report)
            print(f"Rapport de vérification:\n{verification_report_formatted}")
            print(f"Contexte utilisé: {context}")
            return {
                "verification_report": verification_report_formatted,
                "context_used": context
            }

        # Nettoyer la réponse
        sanitized_response = self.sanitize_response(llm_response) if llm_response else ""
        if not sanitized_response:
            print("Le LLM a retourné une réponse vide.")
            verification_report = {
                "Supported": "NON",
                "Unsupported Claims": [],
                "Contradictions": [],
                "Relevant": "NON",
                "Additional Details": "Réponse vide du modèle."
            }
        else:
            # Parser la réponse dans le format attendu
            verification_report = self.parse_verification_response(sanitized_response)
            if verification_report is None:
                print("Le LLM n'a pas répondu avec le format attendu. Utilisation du rapport de vérification par défaut.")
                verification_report = {
                    "Supported": "NON",
                    "Unsupported Claims": [],
                    "Contradictions": [],
                    "Relevant": "NON",
                    "Additional Details": "Échec du parsing de la réponse du modèle."
                }

        # Formater le rapport de vérification en paragraphe
        verification_report_formatted = self.format_verification_report(verification_report)
        print(f"Rapport de vérification:\n{verification_report_formatted}")
        print(f"Contexte utilisé: {context}")

        return {
            "verification_report": verification_report_formatted,
            "context_used": context
        }
