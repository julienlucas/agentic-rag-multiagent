from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict
from .research_agent import ResearchAgent
from .relevance_checker import RelevanceChecker
from .corrective_retrieval import CorrectiveRetrieval
from .search_agent import SearchAgent
from ..config.settings import settings
from ..retriever.page_store import PageStore
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
    citations: List[Dict]
    is_relevant: bool
    retriever: EnsembleRetriever
    page_store: PageStore     # pages OCR (outils grep / read_page de l'agent de recherche)
    relevance: str            # CAN_ANSWER | PARTIAL | NO_MATCH
    corrective_rounds: int    # nb de recherches correctives déjà tentées
    corrective_queries: List[str]  # requêtes réécrites ou appels d'outils (traçabilité)
    tool_calls: int           # appels d'outils consommés (agent de recherche ou générateur)
    search_note: str          # conclusion de l'agent de recherche, transmise au générateur
    context_size: int         # nb de passages réellement vus par le générateur (mode outils)

def build_verification_report(state: "AgentState") -> str:
    """
    Rapport de vérification construit à partir des signaux réels du pipeline —
    aucun appel LLM supplémentaire (le VerificationAgent a été retiré pour la latence).

    Le frontend convertit **gras** et *italique*.
    """
    import os
    from collections import OrderedDict

    relevance = state.get("relevance") or ""
    rel_labels = {
        "CAN_ANSWER": "les passages récupérés permettent de répondre à la question",
        "PARTIAL": "couverture partielle — la réponse peut être incomplète",
        "NO_MATCH": "aucun passage pertinent trouvé dans les documents",
    }
    lines = []
    lines.append(f"**Pertinent:** {'Non' if relevance == 'NO_MATCH' else 'Oui'}")
    if relevance:
        lines.append(f"**Pertinence des passages:** {relevance} — {rel_labels.get(relevance, '')}")

    docs = (state.get("documents") or [])[:effective_top_k(state)]

    # Confiance retrieval : meilleur score du reranker sur les passages transmis
    scores = [
        d.metadata.get("rerank_score") for d in docs
        if getattr(d, "metadata", None) and d.metadata.get("rerank_score") is not None
    ]
    if scores:
        top = max(scores)
        level = "élevée" if top >= 0.7 else ("moyenne" if top >= 0.4 else "faible")
        lines.append(f"**Confiance retrieval (reranker):** {top:.2f} — {level}")

    # Recherche corrective
    rounds = state.get("corrective_rounds", 0)
    queries = state.get("corrective_queries") or []
    if rounds:
        calls = state.get("tool_calls") or 0
        detail = f"{calls} appel{'s' if calls > 1 else ''} d'outils" if calls else f"{rounds} tour{'s' if rounds > 1 else ''}"
        lines.append(f"**Recherche corrective:** déclenchée ({detail})")
        for q in queries[:5]:
            lines.append(f"  • *{q}*")
    else:
        lines.append("**Recherche corrective:** non nécessaire")

    # Sources réellement transmises au modèle (document + pages si disponibles)
    by_source = OrderedDict()
    for d in docs:
        meta = getattr(d, "metadata", None) or {}
        source = meta.get("doc_name") or meta.get("source")
        if not source:
            continue
        name = os.path.splitext(os.path.basename(str(source)))[0]
        page = meta.get("page")
        by_source.setdefault(name, set())
        if page is not None:
            by_source[name].add(int(page))
    if by_source:
        parts = []
        for name, pages in by_source.items():
            if pages:
                shown = sorted(pages)[:6]
                pages_txt = ", ".join(str(p + 1) for p in shown) + ("…" if len(pages) > 6 else "")
                parts.append(f"{name} (p. {pages_txt})")
            else:
                parts.append(name)
        lines.append(f"**Sources utilisées:** {' · '.join(parts)} — {len(docs)} passages transmis au modèle")

    return "\n".join(lines)



def effective_top_k(state) -> int:
    """
    Nombre de passages transmis au modèle. Après une recherche corrective, on ajoute
    CORRECTIVE_EXTRA_DOCS aux RESEARCH_TOP_K initiaux : les passages corrigés viennent
    en plus des initiaux, jamais à leur place. Quand le générateur a lui-même les outils,
    il pose `context_size` : tout ce qu'il a ramené compte.
    """
    if state.get("context_size"):
        return state["context_size"]
    extra = settings.CORRECTIVE_EXTRA_DOCS if state.get("corrective_rounds") else 0
    return settings.RESEARCH_TOP_K + extra


class AgentWorkflow:
    def __init__(self):
        self.researcher = ResearchAgent()
        self.relevance_checker = RelevanceChecker()
        self.corrective = CorrectiveRetrieval()
        self.search_agent = SearchAgent()
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
        documents = state["documents"]
        k = 3
        if state.get("corrective_rounds"):
            # Après une correction, la tête est inchangée par construction : revérifier
            # les 3 mêmes passages redonnerait le même verdict. On juge la tête ET les
            # passages ajoutés — c'est eux que la correction est censée avoir apportés.
            extras = documents[settings.RESEARCH_TOP_K:effective_top_k(state)]
            documents = documents[:k] + extras
            k = len(documents)
        classification = self.relevance_checker.check(
            question=state["question"],
            documents=documents,
            k=k
        )

        if classification == "CAN_ANSWER":
            # Nous avons assez d'informations pour continuer
            return {"is_relevant": True, "relevance": classification}

        elif classification == "PARTIAL":
            # Il y a une couverture partielle, mais nous pouvons quand même continuer
            return {"is_relevant": True, "relevance": classification}

        else:  # classification == "NO_MATCH"
            refusal_state = dict(state)
            refusal_state["relevance"] = classification
            return {
                "is_relevant": False,
                "relevance": classification,
                "draft_answer": "Cette question n'est pas liée (ou il n'y a pas de données) pour votre requête. Veuillez poser une autre question pertinente aux document(s) téléchargé(s).",
                "verification_report": build_verification_report(refusal_state),
            }


    def _decide_after_relevance_check(self, state: AgentState) -> str:
        relevance = state.get("relevance", "")
        rounds = state.get("corrective_rounds", 0)

        # Déclencheur de la recherche corrective. Le checker ne renvoie que trois valeurs,
        # et NO_MATCH est rare (son prompt le biaise vers PARTIAL) : la correction ne doit
        # donc pas dépendre du seul NO_MATCH.
        #
        # PARTIAL déclenche désormais la correction. Auparavant il fallait *en plus* que le
        # score max du reranker passe sous CORRECTIVE_RERANK_THRESHOLD, et cette condition
        # n'a jamais été remplie : 0 déclenchement sur les 22 questions PARTIAL des deux jeux
        # d'éval. Conséquence, le mode agentic appelait exactement le même generate() que la
        # baseline sur toutes les questions — le verdict du checker était calculé puis jeté.
        # Or c'est un bon détecteur : sur 3 runs FinanceBench, les 8 divergences de verdict
        # entre les deux modes tombaient toutes sur des questions PARTIAL (p ≈ 0,0004).
        #
        # CAN_ANSWER continue de faire foi : le checker a vu les passages, on ne corrige pas.
        # Le garde-fou reste CORRECTIVE_MAX_ROUNDS, et CORRECTIVE_PROTECT_TOP empêche la
        # fusion d'éjecter les meilleurs passages déjà trouvés.
        needs_correction = relevance in ("NO_MATCH", "PARTIAL")

        # Le générateur a lui-même les outils : il cherche s'il le juge utile, sur toutes
        # les questions. Pas de recherche corrective séparée, et un NO_MATCH n'est plus un
        # refus a priori — le modèle peut encore trouver (ou constater l'absence par grep).
        if settings.GENERATOR_TOOLS_ENABLED and state.get("retriever") is not None:
            decision = "relevant" if state.get("documents") else "irrelevant"
            logger.debug(f"_decide_after_relevance_check ({relevance}, outils au générateur) -> {decision}")
            return decision

        # Filet supplémentaire : un retrieval au score anormalement bas, même jugé
        # CAN_ANSWER. Désactivé par défaut (seuil à 0) — activer en connaissance de cause.
        threshold = settings.CORRECTIVE_RERANK_THRESHOLD
        if not needs_correction and threshold > 0:
            scores = [
                d.metadata.get("rerank_score")
                for d in (state.get("documents") or [])[:5]
                if getattr(d, "metadata", None) and d.metadata.get("rerank_score") is not None
            ]
            if scores and max(scores) < threshold:
                logger.info(f"Retrieval faible (rerank max={max(scores):.3f} < {threshold}), correction")
                needs_correction = True

        if (
            needs_correction
            and settings.CORRECTIVE_RETRIEVAL_ENABLED
            and rounds < settings.CORRECTIVE_MAX_ROUNDS
            and state.get("retriever") is not None
        ):
            decision = "correct"
        elif state["is_relevant"]:
            decision = "relevant"
        else:
            decision = "irrelevant"
        logger.debug(f"_decide_after_relevance_check ({relevance}, round {rounds}) -> {decision}")
        return decision

    def _corrective_retrieval_step(self, state: AgentState) -> Dict:
        """
        Complète un retrieval jugé insuffisant. Deux formes (settings.CORRECTIVE_MODE) :
        l'agent à outils (search / grep / read_page, le modèle voit chaque résultat), ou
        la réécriture aveugle de la question. Dans les deux cas les passages initiaux
        restent en tête, la correction ne fait qu'ajouter après eux.
        """
        retriever = state["retriever"]
        scope = None
        if hasattr(retriever, "route"):
            try:
                scope = retriever.route(state["question"])
            except Exception:
                scope = None

        result = None
        if settings.CORRECTIVE_MODE == "agent":
            try:
                result = self.search_agent.run(
                    state["question"], retriever, state["documents"],
                    scope=scope, page_store=state.get("page_store"),
                )
            except Exception as e:
                if is_rate_limit(e):
                    raise
                logger.warning(f"SearchAgent indisponible ({e}), repli sur la réécriture")
        if result is None:
            result = self.corrective.expand(
                state["question"], retriever, state["documents"], scope=scope
            )
        return {
            "documents": result["documents"],
            "corrective_queries": result["queries"],
            "corrective_rounds": state.get("corrective_rounds", 0) + 1,
            "tool_calls": state.get("tool_calls", 0) + result.get("tool_calls", 0),
            "search_note": result.get("note") or state.get("search_note", ""),
        }

    def full_pipeline(self, question: str, retriever: EnsembleRetriever, page_store: PageStore = None):
        try:
            logger.debug(f"Démarrage du pipeline complet avec question='{question}'")
            documents = retriever.invoke(question)
            logger.info(f"Récupéré {len(documents)} documents pertinents (depuis .invoke)")

            initial_state = AgentState(
                question=question,
                documents=documents,
                draft_answer="",
                verification_report="",
                citations=[],
                is_relevant=False,
                retriever=retriever,
                page_store=page_store,
                relevance="",
                corrective_rounds=0,
                corrective_queries=[],
                tool_calls=0,
                search_note="",
                context_size=0,
            )

            final_state = self.compiled_workflow.invoke(initial_state)

            return {
                "draft_answer": final_state["draft_answer"],
                "verification_report": final_state.get("verification_report", ""),
                "citations": final_state.get("citations", []),
            }
        except Exception as e:
            logger.error(f"L'exécution du workflow a échoué: {e}")
            return {
                "draft_answer": (
                    "Une erreur est survenue lors du traitement de votre question "
                    "(timeout ou service LLM indisponible). Merci de réessayer dans un instant."
                ),
                "verification_report": f"Erreur: {type(e).__name__}",
                "citations": [],
            }

    def _research_step(self, state: AgentState) -> Dict:
        logger.debug(f"Entrée dans _research_step avec question='{state['question']}'")
        # Limiter le contexte aux meilleurs documents (dilution vs couverture)
        top_docs = state["documents"][:effective_top_k(state)]
        logger.debug(f"Utilisation de {len(top_docs)} docs (sur {len(state['documents'])} récupérés)")
        try:
            if settings.GENERATOR_TOOLS_ENABLED and state.get("retriever") is not None:
                retriever = state["retriever"]
                scope = None
                if hasattr(retriever, "route"):
                    try:
                        scope = retriever.route(state["question"])
                    except Exception:
                        scope = None
                result = self.researcher.generate_with_tools(
                    state["question"], top_docs, retriever,
                    page_store=state.get("page_store"), scope=scope,
                    relevance=state.get("relevance") or None,
                )
                # Le contexte réel du modèle = initiaux + ce que ses outils ont ramené.
                # `corrective_rounds` reste le signal « a cherché davantage » du rapport
                # et de l'éval (corrective_rate = part des questions où il a appelé un outil).
                used_tools = result.get("tool_calls", 0) > 0
                update = {
                    "documents": result["documents"],
                    "context_size": len(result["documents"]),
                    "tool_calls": state.get("tool_calls", 0) + result.get("tool_calls", 0),
                    "corrective_queries": list(state.get("corrective_queries") or []) + result.get("queries", []),
                    "corrective_rounds": state.get("corrective_rounds", 0) + (1 if used_tools else 0),
                }
                report_state = {**state, **update}
                update.update({
                    "draft_answer": result["draft_answer"],
                    "verification_report": build_verification_report(report_state),
                    "citations": result.get("citations", []),
                })
                return update

            result = self.researcher.generate(
                state["question"], top_docs, note=state.get("search_note") or None
            )
            logger.debug("Le chercheur a retourné une réponse provisoire.")
            return {
                "draft_answer": result["draft_answer"],
                "verification_report": build_verification_report(state),
                "citations": result.get("citations", []),
            }
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
