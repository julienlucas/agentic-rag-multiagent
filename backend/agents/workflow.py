from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict
from .research_agent import ResearchAgent
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
        self.relevance_checker = RelevanceChecker()
        self.compiled_workflow = self.build_workflow()  # Compile once during initialization

    def build_workflow(self):
        """Créer et compiler le workflow multi-agents."""
        workflow = StateGraph(AgentState)

        workflow.add_node("check_relevance", self._check_relevance_step)
        workflow.add_node("research", self._research_step)

        workflow.set_entry_point("check_relevance")
        workflow.add_conditional_edges(
            "check_relevance",
            self._decide_after_relevance_check,
            {
                "relevant": "research",
                "irrelevant": END
            }
        )
        workflow.add_edge("research", END)
        return workflow.compile()

    def _check_relevance_step(self, state: AgentState) -> Dict:
        classification = self.relevance_checker.check(
            question=state["question"],
            documents=state["documents"],
            k=3
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
                "verification_report": final_state.get("verification_report", "")
            }
        except Exception as e:
            logger.error(f"L'exécution du workflow a échoué: {e}")
            return {
                "draft_answer": (
                    "Une erreur est survenue lors du traitement de votre question "
                    "(timeout ou service LLM indisponible). Merci de réessayer dans un instant."
                ),
                "verification_report": f"Erreur: {type(e).__name__}"
            }

    def _research_step(self, state: AgentState) -> Dict:
        print(f"[DEBUG] Entrée dans _research_step avec question='{state['question']}'")
        # Limiter à top 5 docs pour éviter dilution du contexte
        top_docs = state["documents"][:5]
        print(f"[DEBUG] Utilisation de {len(top_docs)} docs (sur {len(state['documents'])} récupérés)")
        try:
            result = self.researcher.generate(state["question"], top_docs)
            print("[DEBUG] Le chercheur a retourné une réponse provisoire.")
            return {"draft_answer": result["draft_answer"]}
        except Exception as e:
            logger.error(f"ResearchAgent a échoué: {e}")
            return {
                "draft_answer": (
                    "Une erreur est survenue lors de la génération de la réponse. "
                    "Merci de réessayer."
                )
            }
