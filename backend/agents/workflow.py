from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict
from .research_agent import ResearchAgent
from .verification_agent import VerificationAgent
from .relevance_checker import RelevanceChecker
from langchain_core.documents import Document
from langchain_classic.retrievers.ensemble import EnsembleRetriever
import logging

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    question: str
    documents: List[Document]
    draft_answer: str
    verification_report: str
    is_relevant: bool
    retriever: EnsembleRetriever

class AgentWorkflow:
    def __init__(self):
        self.researcher = ResearchAgent()
        self.verifier = VerificationAgent()
        self.relevance_checker = RelevanceChecker()
        self.compiled_workflow = self.build_workflow()  # Compile once during initialization

    def build_workflow(self):
        """Créer et compiler le workflow multi-agents."""
        workflow = StateGraph(AgentState)

        # Ajouter les nœuds
        workflow.add_node("check_relevance", self._check_relevance_step)
        workflow.add_node("research", self._research_step)
        workflow.add_node("verify", self._verification_step)

        # Définir les arêtes
        workflow.set_entry_point("check_relevance")
        workflow.add_conditional_edges(
            "check_relevance",
            self._decide_after_relevance_check,
            {
                "relevant": "research",
                "irrelevant": END
            }
        )
        workflow.add_edge("research", "verify")
        workflow.add_edge("verify", END)  # Plus de boucle re_research
        return workflow.compile()

    def _check_relevance_step(self, state: AgentState) -> Dict:
        classification = self.relevance_checker.check(
            question=state["question"],
            documents=state["documents"],
            k=20
        )

        if classification == "CAN_ANSWER":
            # Nous avons assez d'informations pour continuer
            return {"is_relevant": True}

        elif classification == "PARTIAL":
            # Il y a une couverture partielle, mais nous pouvons quand même continuer
            return {
                "is_relevant": True
            }

        else:  # classification == "NO_MATCH"
            return {
                "is_relevant": False,
                "draft_answer": "Cette question n'est pas liée (ou il n'y a pas de données) pour votre requête. Veuillez poser une autre question pertinente aux document(s) téléchargé(s)."
            }


    def _decide_after_relevance_check(self, state: AgentState) -> str:
        decision = "relevant" if state["is_relevant"] else "irrelevant"
        print(f"[DEBUG] _decide_after_relevance_check -> {decision}")
        return decision

    def full_pipeline(self, question: str, retriever: EnsembleRetriever):
        try:
            print(f"[DEBUG] Démarrage du pipeline complet avec question='{question}'")
            documents = retriever.invoke(question)
            logger.info(f"Récupéré {len(documents)} documents pertinents (depuis .invoke)")

            initial_state = AgentState(
                question=question,
                documents=documents,
                draft_answer="",
                verification_report="",
                is_relevant=False,
                retriever=retriever
            )

            final_state = self.compiled_workflow.invoke(initial_state)

            return {
                "draft_answer": final_state["draft_answer"],
                "verification_report": final_state["verification_report"]
            }
        except Exception as e:
            logger.error(f"L'exécution du workflow a échoué: {e}")
            raise

    def _research_step(self, state: AgentState) -> Dict:
        print(f"[DEBUG] Entrée dans _research_step avec question='{state['question']}'")
        # Limiter à top 5 docs pour éviter dilution du contexte
        top_docs = state["documents"][:5]
        print(f"[DEBUG] Utilisation de {len(top_docs)} docs (sur {len(state['documents'])} récupérés)")
        result = self.researcher.generate(state["question"], top_docs)
        print("[DEBUG] Le chercheur a retourné une réponse provisoire.")
        return {"draft_answer": result["draft_answer"]}

    def _verification_step(self, state: AgentState) -> Dict:
        print("[DEBUG] Entrée dans _verification_step. Vérification de la réponse provisoire...")
        # Utiliser top 7 docs pour vérification (plus large que génération)
        top_docs = state["documents"][:7]
        result = self.verifier.check(state["draft_answer"], top_docs)
        print("[DEBUG] L'agent de vérification a retourné un rapport de vérification.")
        return {"verification_report": result["verification_report"]}

    def _decide_next_step(self, state: AgentState) -> str:
        verification_report = state["verification_report"]
        print(f"[DEBUG] _decide_next_step avec verification_report='{verification_report}'")
        # Supprimé la boucle re_research qui causait des hallucinations
        # Si la vérification échoue, on garde la réponse telle quelle
        # plutôt que de forcer le modèle à "inventer" une réponse
        logger.info("[DEBUG] Vérification terminée, fin du workflow.")
        return "end"
