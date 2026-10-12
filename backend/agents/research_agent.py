import re
from typing import Dict, List, Optional
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from ..config.settings import settings
from .reasoning_llm import reasoning_llm
import logging

logger = logging.getLogger(__name__)

class ResearchAgent:
    def __init__(self):
        """
        Initialiser l'agent de recherche avec le modèle de raisonnement (Claude Sonnet 4.6 sur Bedrock).
        """

        logger.info(f"Initialisation de ResearchAgent avec {settings.REASONING_MODEL_ID}...")
        self.model = reasoning_llm()
        # Même instance : la réponse avec outils suit plusieurs tours et pose parfois un calcul,
        # le plafond de REASONING_MAX_TOKENS couvre les deux cas.
        self.model_tools = self.model
        logger.info("ModelInference initialisé avec succès.")

    # Phrases sur la démarche que le modèle écrit parfois en tête malgré la consigne
    # (« I now have all the data needed. Let me calculate. », « J'ai maintenant toutes les… »).
    _PREAMBLE = re.compile(
        r"^\s*(?:(?:i now have|i have all|i've now|now i have|let me|j'ai maintenant|j'ai toutes|"
        r"j'ai désormais|je peux maintenant|je vais (?:maintenant )?calculer|voici le calcul)[^\n]*\n+|"
        r"-{3,}\s*\n+)+",
        re.IGNORECASE,
    )

    def sanitize_response(self, response_text: str) -> str:
        """
        Nettoyer la réponse du LLM : espaces inutiles, et phrases de démarche en tête de réponse.
        """
        cleaned = self._PREAMBLE.sub("", response_text.strip(), count=1).strip()
        return cleaned or response_text.strip()

    # Principes valables pour tout document. Les conventions propres aux rapports financiers
    # sont dans FINANCE_RULES, ajoutées seulement quand le contexte en contient un.
    RULES = """**RÈGLES STRICTES:**
1. Source : uniquement les passages numérotés du contexte, jamais de connaissance externe.
   Après chaque affirmation, citez le ou les passages qui la soutiennent : [1] ou [2][5]. Pas de
   numéro absent du contexte, pas d'affirmation qui ne se rattache à aucun passage.
2. La réponse d'abord : la première phrase EST la réponse précise (le nom, le chiffre, la liste,
   avec [n]), au niveau que la question demande : le périmètre qu'elle nomme, le total avant le
   détail, pas une somme de sous-parties. Dans un tableau, prenez la ligne de total qui porte
   exactement le périmètre de la question plutôt que d'additionner des lignes vous-même. Une
   question fermée (« Is… ? », « Does… ? », « Has… ? », « Est-ce que… ? ») commence par « Oui »
   ou « Non ». Ensuite, 3 à 5 puces courtes qui justifient
   (chiffres d'entrée, formule). Pas de titres, pas de résumé final, rien que la question ne
   demande pas, pas de phrase sur votre démarche.
3. Tranchez : une seule réponse. Ni entre-deux (« modérément », « en partie »), ni plusieurs
   options côte à côte. Une réserve vient après la conclusion, jamais à sa place. Toute
   conclusion s'appuie sur au moins un chiffre précis du document, cité [n].
4. Calculez ce qui se calcule : une métrique dont les composantes sont dans le contexte (ratio,
   marge, variation, total) se calcule, elle n'est jamais « non fournie ». Si la question donne
   la formule, appliquez-la exactement. Posez la formule et les chiffres d'entrée [n], refaites
   l'opération, arrondissez et présentez comme demandé (deux décimales sans « % » demandé = un
   ratio décimal comme −0,02). Une question d'analyse (« la liquidité est-elle saine ? ») se
   tranche avec l'indicateur qui la mesure, calculé sur chaque période comparée.
5. Chiffres exacts : recopiez-les tels quels, signe et unité compris (entre parenthèses dans un
   tableau = négatif), sans arrondir avant un calcul. Vérifiez la période et l'unité (millions,
   milliards).
6. Lisez ce que le document dit lui-même du sujet : la section, la note ou le tableau qui lui
   est consacré l'emporte sur une mention en passant ou une formule générique. Une indication
   qualitative suffit à répondre (« deleverage of store payroll » = les salaires ont pesé plus
   lourd en % des ventes) : citez-la, et dites qu'aucun chiffre isolé n'est publié.
7. Pertinence d'une métrique : si la question demande de dire quand une métrique n'est pas
   pertinente, ne le dites que si elle ne s'applique pas à cette activité, et alors sans
   calculer de substitut. Si elle s'applique, concluez avec elle.
8. Si le document ne dit RIEN du sujet, et seulement dans ce cas, répondez :
   « Cette information n'est pas disponible dans le document. »"""

    FINANCE_RULES = """**RAPPORTS FINANCIERS (10-K, 10-Q, résultats trimestriels):**
- Conventions par défaut, sauf formule donnée par la question (un seul résultat) : ROA = résultat net / total actif de fin
  d'exercice ; couverture des intérêts = résultat opérationnel / charges d'intérêts ; marge =
  indicateur / chiffre d'affaires.
- Deux ratios ont deux conventions courantes : la principale en tête, l'autre entre
  parenthèses dans la même phrase, puis UNE conclusion.
  - quick ratio = (actifs courants − stocks) / passifs courants ; entre parenthèses,
    (trésorerie + placements à court terme + créances clients) / passifs courants ;
  - rotation des stocks = coût des ventes / stock moyen ; entre parenthèses, sur le stock de fin.
  « Rotation des stocks FY2022 : 2,7× (2,5× sur le stock de fin) [n] ».
- Liquidité (« la liquidité est-elle saine ? » d'après le quick ratio ou le current ratio) : sous
  1, la réponse est « Non », même de peu (0,96) ; « Oui » à partir de 1. La nuance (accès au
  crédit, notation) vient après, sans changer la réponse.
- Intensité capitalistique (« capital-intensive ? ») : Oui ou Non, jamais « modérément ». Capex
  / chiffre d'affaires sous ~10 % et immobilisations nettes sous ~30 % du total actif : Non.
- « Net income » sans précision = le résultat attribuable aux actionnaires de l'entreprise
  (« attributable to <entreprise> »), pas le résultat consolidé avec les minoritaires.
- Couverture des intérêts avec un numérateur négatif : la réponse est 0. La première phrase
  dit « Couverture des intérêts : 0 (EBIT négatif) » ; le ratio négatif calculé peut suivre,
  jamais en tête.
- Banques, cartes de paiement, assureurs : ni stocks ni marge opérationnelle classique ; leur
  performance se lit à la marge d'intérêts et au résultat avant impôt.
- Exercices : « FY2023 » = l'exercice qui se TERMINE en 2023, que l'entreprise peut appeler
  « fiscal 2022 ». Prenez celui qui se termine dans l'année demandée, et dites-le.
- Litiges matériels : la réponse est dans « Item 3. Legal Proceedings » (10-Q : « Part II,
  Item 1 »), à lire en premier. « … will not have a material adverse effect » = Non. La liste
  générique des Risk Factors ne désigne aucun litige matériel.
- Listes d'acquisitions, de cessions, de segments (« les trois principales acquisitions… ») :
  prenez celles que présente la note consacrée (« Acquisitions », « Segment information ») pour
  la période du document. Jamais des opérations anciennes citées en passant, comme l'historique
  d'une filiale acquise des années plus tôt."""

    # Un rapport financier se reconnaît à son nom (FinanceBench : 3M_2022_10K) ou à ses états.
    _FINANCIAL_NAME = re.compile(r"10-?K|10-?Q|8-?K|EARNINGS|annual[ _-]?report", re.IGNORECASE)
    _FINANCIAL_TEXT = re.compile(
        r"consolidated (?:balance sheets?|statements? of (?:income|operations|cash flows))|form 10-[kq]",
        re.IGNORECASE)

    @classmethod
    def is_financial(cls, documents: List[Document]) -> bool:
        """Le contexte contient-il un rapport financier ? (règles FINANCE_RULES)"""
        for doc in documents:
            meta = getattr(doc, "metadata", None) or {}
            name = str(meta.get("doc_name") or meta.get("source") or "")
            if cls._FINANCIAL_NAME.search(name) or cls._FINANCIAL_TEXT.search(doc.page_content or ""):
                return True
        return False

    def rules_for(self, documents: List[Document]) -> str:
        return self.RULES + ("\n\n" + self.FINANCE_RULES if self.is_financial(documents) else "")

    TOOLS_GUIDE = """**OUTILS:**
Le contexte ci-dessous est ce que la recherche initiale a trouvé : des extraits, pas des pages.
Vous disposez de cinq outils pour aller voir le document lui-même :
- `search(query, doc)` : recherche sémantique + lexicale, en langage naturel, dans le vocabulaire
  des rapports annuels ("provision for income taxes", "Legal Proceedings", "segment information").
- `grep(pattern, doc)` : occurrences littérales page par page, exhaustif — 0 résultat sur un
  document permet d'affirmer que le terme n'y figure pas.
- `read_page(doc, page, end_page)` : la page entière (tableau compris) ; `end_page` pour un
  tableau qui continue sur la page suivante.
- `navigate(doc, section)` : la page où commence une section, cherchée dans les titres seulement
  ("consolidated balance sheet", "income taxes") — le chemin le plus court vers un état financier.
- `open_doc(doc)` : le plan du document (PART, ITEM, états financiers, notes) avec les pages.
`navigate` et `open_doc` indiquent où lire, ils ne ramènent pas de passage : enchaînez avec
`read_page`.
Chaque passage ramené par un outil reçoit un numéro [n] affiché dans le résultat : citez-le comme
les autres.

Quand les utiliser — dans le doute, vérifiez : un appel d'outil coûte moins qu'une réponse fausse.
- Un chiffre précis, un calcul (ratio, marge, variation), une comparaison entre deux exercices :
  lisez la page du tableau d'où viennent les chiffres (`read_page`), signe et unité compris,
  plutôt que de vous fier à un extrait coupé.
- Un extrait qui semble tronqué (tableau sans en-tête, ligne sans total, note sans suite) :
  lisez la page, et la suivante si le tableau continue.
- OBLIGATOIRE : avant d'écrire qu'une information « n'est pas disponible », qu'une métrique
  « n'est pas fournie » ou qu'un ratio « ne peut pas être calculé », faites au moins un `grep`
  sur le document (le terme, puis ses synonymes comptables) et lisez la page trouvée. Une
  réponse négative ne vaut que si elle s'appuie sur un grep sans résultat.
- Répondez sans outil seulement quand le contexte contient clairement et entièrement la réponse.{hint}
{budget} appels d'outils au maximum ; après quoi vous devez répondre avec ce que vous avez."""

    RELEVANCE_HINTS = {
        "PARTIAL": "\nUn vérificateur indépendant a jugé le contexte initial PARTIEL : il mentionne le sujet "
                   "sans donner tous les détails. Cherchez ce qui manque avant de répondre.",
        "NO_MATCH": "\nUn vérificateur indépendant n'a trouvé AUCUN passage pertinent dans le contexte "
                    "initial : cherchez avec les outils avant de conclure.",
    }

    def generate_prompt(self, question: str, context: str, note: Optional[str] = None,
                        rules: Optional[str] = None) -> str:
        """
        Générer un prompt structuré pour le LLM afin de générer une réponse précise et factuelle.
        `note` : conclusion d'un agent de recherche préalable (ce qu'il a trouvé et où) — à
        vérifier contre les passages, jamais à citer comme source.
        """
        note_block = ""
        if note:
            note_block = f"""

**Note de l'agent de recherche (indique où regarder ; vérifiez chaque chiffre dans les passages, ne citez jamais la note elle-même):**
{note}"""
        prompt = f"""Vous êtes un assistant IA factuel et rigoureux.

{rules or self.RULES}

**Question:** {question}{note_block}

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
        est connue, un extrait court, et de quoi rouvrir le document au passage (`file_hash`,
        `pdf_url`, texte entier ; complétés par endpoints.locate_citations s'ils manquent).
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
                # Pour rouvrir le document à la page citée et y surligner le passage entier.
                "file_hash": meta.get("file_hash"),
                "pdf_url": meta.get("pdf_url"),
                "text": doc.page_content,
            })
        return "\n\n".join(parts), citations

    def generate(self, question: str, documents: List[Document], note: Optional[str] = None) -> Dict:
        """
        Générer une réponse initiale en utilisant les documents fournis.
        """
        logger.debug(f"ResearchAgent.generate appelé avec question='{question}' et {len(documents)} documents.")

        # Numéroter les passages : le modèle doit pouvoir rattacher chaque affirmation
        # à un extrait précis (règle 1 du prompt), et le frontend afficher la source
        # derrière chaque marqueur [n].
        context, citations = self.build_numbered_context(documents)
        logger.debug(f"Longueur du contexte combiné: {len(context)} caractères, {len(citations)} passages numérotés.")

        # Créer un prompt pour le LLM
        prompt = self.generate_prompt(question, context, note=note, rules=self.rules_for(documents))
        logger.debug("Prompt créé pour le LLM.")

        # Appeler le LLM pour générer la réponse
        try:
            logger.debug("Envoi du prompt au modèle...")
            response = self.model.invoke(prompt)
            logger.debug("Réponse du LLM reçue.")
        except Exception as e:
            logger.error(f"Erreur lors de l'inférence du modèle: {e}")
            raise RuntimeError("Échec de la génération de réponse en raison d'une erreur de modèle.") from e

        # Extraire et traiter la réponse du LLM (blocs de réflexion ignorés)
        from .search_agent import message_text
        try:
            llm_response = message_text(response).strip()
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

    def generate_with_tools(
        self,
        question: str,
        documents: List[Document],
        retriever,
        page_store=None,
        scope=None,
        max_tool_calls: Optional[int] = None,
        relevance: Optional[str] = None,
    ) -> Dict:
        """
        Génère la réponse en disposant des outils search / grep / read_page / open_doc /
        navigate — le modèle qui
        cherche est celui qui répond, dans la même conversation.

        `relevance` : verdict du vérificateur de pertinence (CAN_ANSWER / PARTIAL / NO_MATCH).
        Il ne bloque plus rien — il devient un indice dans le prompt, qui pousse à chercher.

        Les passages initiaux gardent leurs numéros ; chaque passage ramené par un outil est
        ajouté à la suite avec un nouveau numéro, affiché dans le résultat de l'outil, pour
        que la réponse puisse le citer. `documents` retourné = tout ce que le modèle a vu.
        """
        import hashlib
        from ..tools.tools import build_tools
        from .search_agent import message_text, run_tool_loop, strip_pseudo_calls

        budget = settings.GENERATOR_MAX_TOOL_CALLS if max_tool_calls is None else max_tool_calls
        seen_docs: List[Document] = list(documents)
        index = {hashlib.md5(d.page_content.encode()).hexdigest(): i + 1 for i, d in enumerate(seen_docs)}

        def on_documents(docs: List[Document]) -> List[int]:
            numbers = []
            for d in docs:
                key = hashlib.md5(d.page_content.encode()).hexdigest()
                if key not in index:
                    seen_docs.append(d)
                    index[key] = len(seen_docs)
                numbers.append(index[key])
            return numbers

        trace: Dict = {}
        tools = build_tools(retriever, page_store, scope, trace, on_documents=on_documents)

        context, _ = self.build_numbered_context(documents)
        hint = self.RELEVANCE_HINTS.get(relevance or "", "")
        system = (
            "Vous êtes un assistant IA factuel et rigoureux.\n\n"
            + self.rules_for(documents) + "\n\n" + self.TOOLS_GUIDE.format(budget=budget, hint=hint)
        )
        user = (
            f"**Question:** {question}\n\n"
            f"**Contexte (passages numérotés):**\n{context}\n\n"
            "**Réponse (basée UNIQUEMENT sur les passages, initiaux ou ramenés par les outils, "
            "avec citations [n]):**"
        )
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        try:
            loop = run_tool_loop(self.model_tools, tools, messages, budget, final_llm=self.model_tools)
        except Exception as e:
            logger.error(f"Erreur lors de l'inférence du modèle (outils): {e}")
            raise RuntimeError("Échec de la génération de réponse en raison d'une erreur de modèle.") from e

        answer = strip_pseudo_calls(message_text(loop["final"]))
        draft_answer = self.sanitize_response(answer) if answer else \
            "Je ne peux pas répondre à cette question basée sur les documents fournis."
        full_context, citations = self.build_numbered_context(seen_docs)
        logger.info(
            f"ResearchAgent (outils): {loop['tool_calls']} appel(s), "
            f"{len(seen_docs) - len(documents)} passage(s) ajouté(s) au contexte"
        )
        return {
            "draft_answer": draft_answer,
            "context_used": full_context,
            "citations": citations,
            "documents": seen_docs,
            "tool_calls": loop["tool_calls"],
            "queries": list(trace.get("calls", [])),
        }
