from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict
from .research_agent import ResearchAgent
from .relevance_checker import RelevanceChecker
from .corrective_retrieval import CorrectiveRetrieval
from ..config.settings import settings
from ..utils.resilience import is_rate_limit
from langchain_core.documents import Document
from langchain_classic.retrievers.ensemble import EnsembleRetriever
import logging

logger = logging.getLogger(__name__)

class AgentState(TypedDict, total=False):
    question: str
    documents: List[Document]
    draft_answer: str
    verification_report: str
    is_relevant: bool
    retriever: EnsembleRetriever
    relevance: str            # CAN_ANSWER | PARTIAL | NO_MATCH
    corrective_rounds: int    # nb de recherches correctives déjà tentées
    corrective_queries: List[str]  # requêtes réécrites (traçabilité)

class AgentWorkflow:
    def __init__(self):
        self.researcher = ResearchAgent()
        self.relevance_checker = RelevanceChecker()
        self.corrective = CorrectiveRetrieval()
        self.compiled_workflow = self.build_workflow()  # Compile once during initialization

    def build_workflow(self):
        """Créer et compiler le workflow multi-agents."""
        workflow = StateGraph(AgentState)

        workflow.add_node("check_relevance", self._check_relevance_step)
        workflow.add_node("corrective_retrieval", self._corrective_retrieval_step)
        workflow.add_node("research", self._research_step)

        workflow.set_entry_point("check_relevance")
        workflow.add_conditional_edges(
            "check_relevance",
            self._decide_after_relevance_check,
            {
                "relevant": "research",
                "correct": "corrective_retrieval",
                "irrelevant": END
            }
        )
        # Après la recherche corrective, on revérifie la pertinence des nouveaux passages.
        workflow.add_edge("corrective_retrieval", "check_relevance")
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
            return {"is_relevant": True, "relevance": classification}

        elif classification == "PARTIAL":
            # Il y a une couverture partielle, mais nous pouvons quand même continuer
            return {"is_relevant": True, "relevance": classification}

        else:  # classification == "NO_MATCH"
            return {
                "is_relevant": False,
                "relevance": classification,
                "draft_answer": "Cette question n'est pas liée (ou il n'y a pas de données) pour votre requête. Veuillez poser une autre question pertinente aux document(s) téléchargé(s)."
            }


    def _decide_after_relevance_check(self, state: AgentState) -> str:
        relevance = state.get("relevance", "")
        rounds = state.get("corrective_rounds", 0)

        # Déclencheur de la recherche corrective :
        # - NO_MATCH du checker (rare : son prompt le biaise vers PARTIAL), OU
        # - score max du reranker faible = signal continu que le retrieval a raté.
        #   (CAN_ANSWER du checker fait foi : il a vu les passages, on ne corrige pas.)
        weak_retrieval = False
        threshold = settings.CORRECTIVE_RERANK_THRESHOLD
        if threshold > 0 and relevance != "CAN_ANSWER":
            scores = [
                d.metadata.get("rerank_score")
                for d in (state.get("documents") or [])[:5]
                if getattr(d, "metadata", None) and d.metadata.get("rerank_score") is not None
            ]
            weak_retrieval = bool(scores) and max(scores) < threshold
            if weak_retrieval:
                logger.info(f"Retrieval faible (rerank max={max(scores):.3f} < {threshold}), correction")
        if (
            (relevance == "NO_MATCH" or weak_retrieval)
            and settings.CORRECTIVE_RETRIEVAL_ENABLED
            and rounds < settings.CORRECTIVE_MAX_ROUNDS
            and state.get("retriever") is not None
        ):
            decision = "correct"
        elif state["is_relevant"]:
            decision = "relevant"
        else:
            decision = "irrelevant"
        print(f"[DEBUG] _decide_after_relevance_check ({relevance}, round {rounds}) -> {decision}")
        return decision

    def _corrective_retrieval_step(self, state: AgentState) -> Dict:
        """Réécrit la question dans le lexique du document, recherche, fusionne."""
        retriever = state["retriever"]
        scope = None
        if hasattr(retriever, "route"):
            try:
                scope = retriever.route(state["question"])
            except Exception:
                scope = None
        result = self.corrective.expand(
            state["question"], retriever, state["documents"], scope=scope
        )
        return {
            "documents": result["documents"],
            "corrective_queries": result["queries"],
            "corrective_rounds": state.get("corrective_rounds", 0) + 1,
        }

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
                retriever=retriever,
                relevance="",
                corrective_rounds=0,
                corrective_queries=[],
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
        # Limiter le contexte aux meilleurs documents (dilution vs couverture)
        top_docs = state["documents"][:settings.RESEARCH_TOP_K]
        print(f"[DEBUG] Utilisation de {len(top_docs)} docs (sur {len(state['documents'])} récupérés)")
        try:
            result = self.researcher.generate(state["question"], top_docs)
            print("[DEBUG] Le chercheur a retourné une réponse provisoire.")
            return {"draft_answer": result["draft_answer"]}
        except Exception as e:
            # Un rate limit doit remonter : l'appelant (éval, retry externe) sait le
            # rejouer. L'avaler en message figé perdait la question définitivement.
            if is_rate_limit(e):
                raise
            logger.error(f"ResearchAgent a échoué: {e}")
            return {
                "draft_answer": (
                    "Une erreur est survenue lors de la génération de la réponse. "
                    "Merci de réessayer."
                )
            }
