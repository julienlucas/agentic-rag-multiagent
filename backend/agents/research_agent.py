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

    RULES = """**RÈGLES STRICTES:**
1. Répondez UNIQUEMENT avec des informations EXPLICITEMENT présentes dans le contexte
2. Ne faites AUCUNE supposition ni extrapolation au-delà du contexte. UNE SEULE exception :
   si la question demande une métrique qui se CALCULE à partir de chiffres présents dans le
   contexte (ratio, marge, variation, total), faites le calcul — posez la formule, citez
   chaque chiffre d'entrée avec son passage [n], donnez le résultat. Ne dites jamais qu'un
   ratio « n'est pas fourni » quand ses composantes le sont.
3. Si l'information n'est PAS dans le contexte, répondez: "Cette information n'est pas disponible dans le document."
   Réservez cette réponse au cas où le document ne dit RIEN du sujet. Une indication
   qualitative suffit à répondre : « deleverage of store payroll » veut dire que les salaires
   ont pesé plus lourd en % des ventes, donc qu'ils ont augmenté en % des ventes. Répondez alors
   Oui / Non en citant cette phrase, et dites qu'aucun chiffre isolé n'est publié.
4. Citez les chiffres et faits EXACTEMENT comme ils apparaissent, signe et unité compris
   (une valeur entre parenthèses dans un tableau financier est négative)
5. N'ajoutez JAMAIS de connaissances externes
6. Chaque passage du contexte est numéroté. Après CHAQUE affirmation, indiquez entre
   crochets le ou les numéros des passages qui la soutiennent : [1] ou [2][5].
   N'utilisez JAMAIS un numéro qui n'apparaît pas dans le contexte, et n'affirmez
   rien qui ne puisse être rattaché à un passage.
7. Ratios financiers : si la question donne la formule, appliquez-la exactement et donnez un
   seul résultat. Sinon, plusieurs conventions usuelles coexistent : donnez le résultat avec
   chacune, sur une ligne chacune, en nommant la convention :
   - quick ratio = (trésorerie et équivalents + placements à court terme + créances clients
     nettes) / passifs courants ; et (actifs courants − stocks) / passifs courants ;
   - rotation des stocks = coût des ventes / stock moyen (début et fin d'exercice) ; et coût
     des ventes / stock de fin d'exercice ;
   - ROA = résultat net / total actif moyen ; et résultat net / total actif de fin d'exercice ;
   - couverture des intérêts = résultat opérationnel / charges d'intérêts ;
   - une marge = l'indicateur / le chiffre d'affaires.
   Écrivez chaque formule, puis son résultat, arrondi comme la question le demande. La
   conclusion (Oui / Non, amélioration / dégradation) vaut pour toutes les conventions ; si
   elles divergent, dites-le.
8. Format : court et précis dès la première phrase.
   - Question fermée (« Is… ? », « Does… ? », « Has… ? », « Did… ? », « Est-ce que… ? ») : la
     réponse commence TOUJOURS par « Oui » ou « Non », jamais par une explication.
   - La PREMIÈRE phrase contient la réponse précise elle-même : le nom, le chiffre, l'élément,
     avec sa citation [n] — pas une phrase générale (« Oui, plusieurs événements ont… » ne
     suffit pas : écrivez « Oui : le gain sur la création de la coentreprise Consumer
     Healthcare (8,1 Md$) [3] »). Répondez au niveau demandé (le total avant le détail).
   - Toute conclusion s'appuie sur AU MOINS UN CHIFFRE PRÉCIS du document, cité [n] : montant,
     ratio, pourcentage, nombre, avec son unité et son exercice. Une explication sans chiffre
     ne suffit pas.
   - Ensuite, au plus 3 à 5 lignes : les éléments qui justifient la réponse (chiffres d'entrée
     d'un calcul, formule), en puces courtes. Pas de titres, pas de sections, pas de résumé final.
   - N'ajoutez pas d'éléments que la question ne demande pas.
   - Commencez directement par la réponse : pas de phrase sur votre démarche ou vos recherches
     (« J'ai maintenant toutes les données… »).
9. Questions d'analyse (« la liquidité est-elle saine ? », « la marge s'améliore-t-elle ? »,
   « l'entreprise est-elle capitalistique ? », « quel segment a le plus progressé ? ») : ne
   vous contentez pas d'une appréciation. Calculez vous-même l'indicateur qui tranche (quick
   ratio, marge, variation en %, capex / chiffre d'affaires, total actif / chiffre
   d'affaires…), sur chaque exercice comparé, puis concluez par Oui / Non ou par l'élément
   demandé. Posez le calcul : formule, chiffres d'entrée cités [n], résultat.
10. Exactitude des chiffres : recopiez les chiffres du document tels quels (sans les arrondir
   avant un calcul), vérifiez l'exercice et l'unité (millions ou milliards), et refaites chaque
   opération avant d'écrire le résultat.
11. Exercices fiscaux : un exercice se désigne souvent par l'année où il se TERMINE (« FY2023 »
   = l'exercice clos en janvier 2023, que l'entreprise peut appeler « fiscal 2022 »). Si
   l'exercice demandé n'existe pas sous ce nom dans le document, prenez celui qui se termine
   dans l'année demandée et dites-le, au lieu de répondre que l'information n'est pas
   disponible."""

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
- `open_document(doc)` : le plan du document (PART, ITEM, états financiers, notes) avec les pages.
`navigate` et `open_document` indiquent où lire, ils ne ramènent pas de passage : enchaînez avec
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

    def generate_prompt(self, question: str, context: str, note: Optional[str] = None) -> str:
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

{self.RULES}

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
        # à un extrait précis (règle 6 du prompt), et le frontend afficher la source
        # derrière chaque marqueur [n].
        context, citations = self.build_numbered_context(documents)
        logger.debug(f"Longueur du contexte combiné: {len(context)} caractères, {len(citations)} passages numérotés.")

        # Créer un prompt pour le LLM
        prompt = self.generate_prompt(question, context, note=note)
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
        Génère la réponse en disposant des outils search / grep / read_page / open_document /
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
            + self.RULES + "\n\n" + self.TOOLS_GUIDE.format(budget=budget, hint=hint)
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
