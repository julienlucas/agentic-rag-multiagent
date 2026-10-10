"""
Les outils de l'agent : recherche façon système de fichiers sur les documents d'une question.

Cinq outils, les cinq de l'Agentic Search de Mistral (search, open, navigate, read, grep),
fermés sur le retriever et le PageStore d'une question :

- search(query, doc)              : le retrieval hybride + rerank du pipeline (c'est sa force à
                                    cette échelle, on ne le remplace pas — on le rend itératif).
- grep(pattern, doc)              : occurrences littérales page par page, exhaustif. Un 0 résultat
                                    sur 260 pages fonde une réponse négative.
- read_page(doc, page, end_page)  : une page entière, ou 2-3 pages consécutives pour un tableau
                                    à cheval — ce qu'un chunk de 1 200 caractères ne montre jamais.
- open_document(doc)              : le plan du document (PART, ITEM, états financiers, notes) et
                                    son nombre de pages ; sans `doc`, la liste des documents.
- navigate(doc, section)          : une section par son titre — la page où commence le bilan
                                    consolidé, là où grep renverrait aussi sommaire et renvois.

Contrairement à Mistral, aucun document n'est « ouvert » entre deux appels : chaque outil
reçoit `doc`, open_document sert à découvrir la structure, pas à changer d'état. Seuls search
et read_page ramènent des passages citables ; les trois autres indiquent où lire.


Utilisés par le modèle de génération (ResearchAgent.generate_with_tools, mode par défaut) et
par l'agent de recherche séparé (agents/search_agent.py, mode correctif). Les passages
initiaux sont intouchables : les outils ne peuvent qu'AJOUTER après eux.
"""
import hashlib
from typing import Callable, Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.tools import tool

from ..retriever.page_store import PageStore, doc_label
from ..utils.logging import logger
from ..utils.resilience import is_rate_limit


def doc_key(doc: Document) -> str:
    return hashlib.md5(doc.page_content.encode()).hexdigest()


def locator(doc: Document) -> str:
    meta = doc.metadata or {}
    name = doc_label(meta.get("doc_name") or meta.get("source") or "document")
    page = meta.get("page")
    return f"{name}, p. {int(page) + 1}" if page is not None else name


def build_tools(
    retriever,
    page_store: Optional[PageStore],
    scope,
    trace: Dict,
    on_documents: Optional[Callable[[List[Document]], List[int]]] = None,
):
    """
    Construit search / grep / read_page / open_document / navigate fermés sur le retriever,
    le PageStore et la trace.

    `trace` reçoit : calls (libellés lisibles), search_results (listes de Documents),
    read_pages (Documents de pages lues).

    `on_documents(docs) -> [numéros]` : si fourni, chaque Document ramené par search ou
    read_page est enregistré dans le contexte numéroté du générateur, et le numéro attribué
    est affiché dans le résultat de l'outil pour que le modèle puisse le citer [n].
    """
    found_docs: List[List[Document]] = trace.setdefault("search_results", [])
    read_pages: List[Document] = trace.setdefault("read_pages", [])
    calls: List[str] = trace.setdefault("calls", [])

    def _scope_for(doc: Optional[str]):
        if doc and page_store is not None:
            label = page_store.resolve(doc)
            if label:
                return [page_store.source_of(label)]
        if doc:
            return [doc]
        return scope

    def _numbers(docs: List[Document]) -> List[Optional[int]]:
        if on_documents is None or not docs:
            return [None] * len(docs)
        return list(on_documents(docs))

    @tool
    def search(query: str, doc: Optional[str] = None) -> str:
        """Recherche sémantique + lexicale dans les documents indexés. `query` : une phrase
        courte en langage naturel, dans le vocabulaire des rapports financiers (pas
        d'opérateur booléen). `doc` : restreindre à un document (optionnel)."""
        calls.append(f'search: "{query}"' + (f" [{doc}]" if doc else ""))
        try:
            target = _scope_for(doc)
            if target is not None and hasattr(retriever, "invoke_with_scope"):
                results = retriever.invoke_with_scope(query, target)
            else:
                results = retriever.invoke(query)
        except Exception as e:
            if is_rate_limit(e):
                raise
            logger.warning(f"search a échoué: {e}")
            return "Erreur de recherche, réessayez avec une autre formulation."
        results = list(results or [])[:8]
        found_docs.append(results)
        if not results:
            return "Aucun résultat."
        numbers = _numbers(results)
        lines = []
        for i, (d, n) in enumerate(zip(results, numbers), start=1):
            tag = f"[{n}]" if n is not None else f"[{i}]"
            excerpt = " ".join(d.page_content.split())[:400]
            lines.append(f"{tag} ({locator(d)}) {excerpt}")
        return "\n".join(lines)

    @tool
    def grep(pattern: str, doc: Optional[str] = None) -> str:
        """Occurrences littérales d'un terme (regex insensible à la casse), page par page.
        Exhaustif : 0 résultat signifie que le terme est absent du document. `doc` :
        restreindre à un document (optionnel, recommandé)."""
        calls.append(f'grep: "{pattern}"' + (f" [{doc}]" if doc else ""))
        if page_store is None:
            return "grep indisponible (pas de pages OCR pour ce corpus)."
        result = page_store.grep(pattern, doc=doc)
        if result.get("error"):
            return f"{result['error']}. Documents : {', '.join(result.get('documents', []))}"
        if not result["hits"]:
            return f"0 occurrence de « {pattern} »."
        lines = [f"{h['doc']} p. {h['page'] + 1}: {h['line']}" for h in result["hits"]]
        more = result["total"] - len(result["hits"])
        if more > 0:
            lines.append(f"… et {more} autres occurrences (affinez le motif ou le document).")
        return "\n".join(lines)

    @tool
    def read_page(doc: str, page: int, end_page: Optional[int] = None) -> str:
        """Lit une page entière d'un document (numéro tel qu'affiché par search et grep, à
        partir de 1). Pour un tableau à cheval sur plusieurs pages, donnez `end_page` :
        les pages `page` à `end_page` sont lues ensemble (3 au plus)."""
        span = f"{page}-{end_page}" if end_page is not None and end_page != page else f"{page}"
        calls.append(f"read_page: {doc} p. {span}")
        if page_store is None:
            return "read_page indisponible (pas de pages OCR pour ce corpus)."
        try:
            start = int(page) - 1
            end = int(end_page) - 1 if end_page is not None else start
        except (TypeError, ValueError):
            return f"page invalide: {page!r}"
        documents = page_store.page_documents(doc, start, end)
        if not documents:
            result = page_store.read_page(doc, start)
            return result.get("error", "page introuvable")
        new = [d for d in documents if all(doc_key(d) != doc_key(p) for p in read_pages)]
        read_pages.extend(new)
        numbers = _numbers(documents)
        parts = []
        for d, n in zip(documents, numbers):
            tag = f"[{n}] " if n is not None else ""
            parts.append(f"=== {tag}{locator(d)} ===\n{d.page_content}")
        return "\n\n".join(parts)

    @tool
    def open_document(doc: Optional[str] = None) -> str:
        """Ouvre un document : nombre de pages et plan (PART, ITEM, états financiers
        consolidés, notes) avec la page de chaque section. Sans `doc`, liste les documents
        disponibles. Utile pour savoir où se trouve une section avant de la lire."""
        calls.append("open_document" + (f": {doc}" if doc else ""))
        if page_store is None:
            return "open_document indisponible (pas de pages OCR pour ce corpus)."
        if not doc:
            return "\n".join(f"- {d} ({page_store.page_count(d)} pages)" for d in page_store.documents())
        result = page_store.outline(doc)
        if result.get("error"):
            return f"{result['error']}. Documents : {', '.join(result.get('documents', []))}"
        lines = [f"{result['doc']} — {result['n_pages']} pages"]
        lines += [f"p. {e['page'] + 1} : {e['title']}" for e in result["entries"]]
        more = result["total"] - len(result["entries"])
        if more > 0:
            lines.append(f"… et {more} autres sections (navigate pour en trouver une).")
        return "\n".join(lines)

    @tool
    def navigate(doc: str, section: str) -> str:
        """Trouve une section par son titre (ex. "consolidated balance sheet", "income
        taxes", "segment information") : les en-têtes dont l'intitulé contient tous les mots,
        avec leur page et le début du texte. Ne cherche que dans les titres, contrairement à
        grep ; enchaînez avec read_page."""
        calls.append(f'navigate: "{section}" [{doc}]')
        if page_store is None:
            return "navigate indisponible (pas de pages OCR pour ce corpus)."
        result = page_store.find_sections(doc, section)
        if result.get("error"):
            documents = result.get("documents")
            return result["error"] + (f". Documents : {', '.join(documents)}" if documents else "")
        if not result["hits"]:
            return f"Aucun titre ne contient « {section} » ; essayez open_document, grep ou search."
        lines = [f"p. {h['page'] + 1} : {h['title']} — {h['excerpt']}" for h in result["hits"]]
        more = result["total"] - len(result["hits"])
        if more > 0:
            lines.append(f"… et {more} autres titres (précisez la section).")
        return "\n".join(lines)

    return [search, grep, read_page, open_document, navigate]
