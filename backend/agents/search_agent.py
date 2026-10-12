"""
L'agent de recherche séparé, et la boucle d'appels d'outils commune aux deux usages.

Les outils eux-mêmes (search, grep, read_page, open_doc, navigate) sont dans
backend/tools/tools.py. Deux usages :

1. Le modèle de GÉNÉRATION reçoit ces outils directement (ResearchAgent.generate_with_tools) :
   il cherche et répond dans la même conversation, comme dans l'Agentic Search de Mistral.
   C'est le mode par défaut (settings.GENERATOR_TOOLS_ENABLED).

2. `SearchAgent` — un agent séparé collecte la preuve manquante puis la transmet au générateur,
   avec sa note de synthèse. Mode conditionnel, déclenché par le vérificateur de pertinence
   (settings.CORRECTIVE_MODE = "agent"). Conservé pour comparaison.

Dans les deux cas, le contrat avec le reste du pipeline est le même : les RESEARCH_TOP_K
passages initiaux sont intouchables, les outils ne peuvent qu'AJOUTER après eux.
"""
import re
from typing import Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langsmith import traceable

from ..config.settings import settings
from ..retriever.page_store import PageStore, doc_label
from ..tools.tools import build_tools, doc_key, locator
from ..utils.logging import logger
from ..utils.resilience import is_rate_limit
from .corrective_retrieval import CorrectiveRetrieval, _find_reranker
from .reasoning_llm import reasoning_llm


def message_text(message) -> str:
    """
    Texte d'un AIMessage. `content` est une str, ou une liste de blocs ({"type": "text", ...})
    selon la réponse de l'API : le run FinanceBench du 4 sept. 2026 (soir) a perdu 2 questions
    sur un `'list' object has no attribute 'strip'`.
    """
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type", "text") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content or "")


@traceable(name="tool_decision", run_type="chain",
           process_inputs=lambda inputs: {"messages": inputs.get("messages")})
def _tool_decision(bound, messages: List) -> AIMessage:
    """Un tour de la boucle : appeler un outil, ou répondre. Run nommé « tool_decision »,
    noté par le juge en ligne « choix d'outil » (backend/evals/online_evaluators.py)."""
    return bound.invoke(messages)


# Dernier tour, sans outils : le modèle doit conclure. Sans outils déclarés, langchain-aws réécrit
# les appels d'outils de l'historique en texte (« [Called read_page with parameters: …] ») ; sans
# consigne explicite, le modèle imitait ce format en guise de réponse (PepsiCo 2022, run
# FinanceBench du 11 oct. 2026).
FINAL_INSTRUCTION = (
    "Le budget d'appels d'outils est épuisé : n'appelez plus aucun outil et n'écrivez aucun appel "
    "d'outil dans votre texte. Rédigez maintenant votre réponse finale à la question, à partir de "
    "ce que vous avez déjà lu, avec ses citations [n]."
)
_PSEUDO_CALL = re.compile(r"^\s*\[Called \w+ with parameters:.*$", re.MULTILINE)


def strip_pseudo_calls(text: str) -> str:
    """Retire les appels d'outils écrits en texte (« [Called read_page with parameters: …] »)."""
    return _PSEUDO_CALL.sub("", text).strip()


def _conclude(llm, messages: List) -> AIMessage:
    """Tour final sans outils, relancé une fois si le modèle n'écrit qu'un appel d'outil en texte."""
    messages.append(HumanMessage(content=FINAL_INSTRUCTION))
    final = llm.invoke(messages)
    if not strip_pseudo_calls(message_text(final)):
        messages.append(final)
        messages.append(HumanMessage(content=FINAL_INSTRUCTION))
        final = llm.invoke(messages)
    messages.append(final)
    return final


def run_tool_loop(llm, tools, messages: List, max_tool_calls: int, final_llm=None) -> Dict:
    """
    Boucle d'appels d'outils bornée. `messages` est complété en place.
    Retourne {"tool_calls": n, "final": AIMessage}. Quand le budget est épuisé, un dernier
    tour SANS outils (`final_llm`, ou `llm` s'il n'est pas fourni) force une conclusion.
    """
    tool_map = {t.name: t for t in tools}
    bound = llm.bind_tools(tools)
    n_calls = 0
    final: Optional[AIMessage] = None
    for _turn in range(max_tool_calls + 1):
        ai: AIMessage = _tool_decision(bound, list(messages))  # copie : `messages` grandit ensuite
        messages.append(ai)
        tool_calls = list(getattr(ai, "tool_calls", None) or [])
        if not tool_calls:
            final = ai
            break
        for call in tool_calls:
            if n_calls >= max_tool_calls:
                messages.append(ToolMessage(
                    content="Budget d'appels épuisé : conclus avec ce que tu as.",
                    tool_call_id=call["id"],
                ))
                continue
            n_calls += 1
            fn = tool_map.get(call["name"])
            try:
                output = fn.invoke(call["args"]) if fn else f"outil inconnu: {call['name']}"
            except Exception as e:
                if is_rate_limit(e):
                    raise
                logger.warning(f"outil {call['name']} a levé {e}")
                output = f"Erreur outil: {type(e).__name__}"
            messages.append(ToolMessage(content=str(output), tool_call_id=call["id"]))
        if n_calls >= max_tool_calls:
            final = _conclude(final_llm or llm, messages)
            break
    if final is None:
        final = _conclude(final_llm or llm, messages)
    return {"tool_calls": n_calls, "final": final}


SYSTEM_PROMPT = """Tu es un analyste financier. Une première recherche documentaire n'a PAS suffi à répondre à la question ; tu disposes d'outils pour trouver la preuve manquante dans les documents indexés.

Documents disponibles :
{documents}

Ce que le modèle a déjà sous les yeux (passages initiaux, ils resteront dans son contexte) :
{initial}

Méthode :
1. Identifie ce qui manque précisément (un chiffre, une ligne comptable, une section).
2. `search` pour une recherche sémantique en langage naturel dans le vocabulaire des rapports annuels ("provision for income taxes", "Legal Proceedings", "segment information").
3. `grep` pour vérifier qu'un terme existe (ou n'existe pas) dans un document, et savoir sur quelle page.
4. `navigate` pour aller droit à une section dont tu connais le titre (un état financier consolidé, une note) ; `open_doc` pour voir le plan d'un document quand tu ne sais pas où chercher.
5. `read_page` pour lire une page entière quand un résultat pointe vers un tableau ou une note : les tableaux sont coupés dans les extraits, jamais dans la page. Si le tableau continue sur la page suivante, lis les deux (`end_page`).
6. Arrête-toi dès que tu as lu la ou les pages qui portent la preuve — les pages lues seront transmises telles quelles au modèle qui répond. Tu as {budget} appels d'outils au maximum.

Si la question porte sur une métrique qui doit être calculée (ratio, marge, variation), cherche les lignes de base du calcul (ex. quick ratio : cash, short-term investments, receivables, current liabilities — dans le bilan consolidé).

Quand tu as terminé, écris une NOTE courte pour le modèle qui répondra : ce que tu as trouvé, sur quelle(s) page(s), les chiffres exacts avec leur signe, ou ce que tu as constaté absent (et sur quelle base — un grep sans résultat, par exemple)."""


class SearchAgent:
    """Agent séparé : cherche la preuve manquante, la transmet au générateur avec une note."""

    def __init__(self, llm=None):
        self.llm = llm
        self.max_tool_calls = settings.CORRECTIVE_MAX_TOOL_CALLS

    def _get_llm(self):
        if self.llm is None:
            self.llm = reasoning_llm()
        return self.llm

    @staticmethod
    def _describe_initial(docs: List[Document], limit: int) -> str:
        lines = []
        for i, d in enumerate(docs[:limit], start=1):
            lines.append(f"[{i}] ({locator(d)}) {' '.join(d.page_content.split())[:160]}…")
        return "\n".join(lines) or "(aucun)"

    def run(
        self,
        question: str,
        retriever,
        current_docs: List[Document],
        scope: Optional[List[str]] = None,
        page_store: Optional[PageStore] = None,
    ) -> Dict:
        """
        Cherche la preuve manquante avec les outils, puis assemble le contexte :
        tête protégée (inchangée) + pages lues + résultats de recherche reclassés.

        Retourne {"documents", "queries" (trace), "tool_calls", "note"} — la note est la
        conclusion de l'agent, transmise au générateur pour qu'il sache ce qui a été trouvé
        et pourquoi ces pages sont là.
        """
        protect = max(0, settings.CORRECTIVE_PROTECT_TOP)
        extra_budget = max(0, settings.CORRECTIVE_EXTRA_DOCS)
        head = current_docs[:protect]
        head_keys = {doc_key(d) for d in head}

        trace: Dict = {}
        tools = build_tools(retriever, page_store, scope, trace)

        documents = (page_store.documents() if page_store is not None else None) or sorted({
            doc_label((d.metadata or {}).get("doc_name") or (d.metadata or {}).get("source") or "")
            for d in current_docs
        } - {""})
        system = SYSTEM_PROMPT.format(
            documents="\n".join(f"- {d}" for d in documents) or "- (inconnus)",
            initial=self._describe_initial(current_docs, protect),
            budget=self.max_tool_calls,
        )
        messages = [SystemMessage(content=system), HumanMessage(content=f"Question : {question}")]
        loop = run_tool_loop(self._get_llm(), tools, messages, self.max_tool_calls)
        n_calls = loop["tool_calls"]
        note = message_text(loop["final"]).strip() if n_calls else ""

        # --- Assemblage du contexte : la tête ne bouge pas, on ajoute après. ---
        extras: List[Document] = []
        seen = set(head_keys)
        for page in trace.get("read_pages", []):
            if len(extras) >= extra_budget:
                break
            k = doc_key(page)
            if k not in seen:
                extras.append(page)
                seen.add(k)

        remaining = extra_budget - len(extras)
        if remaining > 0 and trace.get("search_results"):
            merged = [
                d for d in CorrectiveRetrieval._merge(trace["search_results"], top_n=30)
                if doc_key(d) not in seen
            ]
            reranker = _find_reranker(retriever)
            if reranker is not None and merged:
                merged = reranker.rerank(question, merged, top_n=remaining)
            for d in merged[:remaining]:
                extras.append(d)
                seen.add(doc_key(d))

        logger.info(
            f"SearchAgent: {n_calls} appel(s) d'outils, {len(trace.get('read_pages', []))} page(s) lue(s), "
            f"{len(extras)} passage(s) ajouté(s) après les {len(head)} initiaux"
        )
        return {
            "documents": head + extras,
            "queries": list(trace.get("calls", [])),
            "tool_calls": n_calls,
            "note": note,
        }
