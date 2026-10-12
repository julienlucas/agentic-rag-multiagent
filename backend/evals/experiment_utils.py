"""Outils communs aux expériences (FinanceBench, convergence, rejeu des votes) :

- index : indexation des chunks et lecture de l'index d'éval dans Qdrant, retriever ;
- métriques : retrieval (recall/precision/MRR/nDCG@k) et réponse (F1, context_hit) ;
- juge FinanceBench : verdict CORRECT / INCORRECT / REFUSAL contre la référence ;
- answer relevancy (méthode RAGAS) : la réponse vise-t-elle la question ?

Même rôle que evaluating-ai-agents/evals/experiment_utils.py.
"""
import hashlib
import math
import os
import re
import sys
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langsmith import Client  # noqa: E402

from backend.config.settings import settings  # noqa: E402
from backend.retriever.builder import RetrieverBuilder  # noqa: E402
from backend.utils.logging import logger  # noqa: E402
# Résilience aux rate limits : implémentation côté backend (utilisée aussi par le
# workflow et les agents), ré-exportée ici pour les scripts d'évaluation.
from backend.utils.resilience import (  # noqa: E402,F401
    call_with_backoff,
    is_rate_limit,
    retry_after,
    root_cause,
)


# ══ Datasets, index et LangSmith ══════════════════════════════════════════════

# Tout ce que produisent les évaluations va dans le projet de l'application, comme dans
# evaluating-ai-agents : pas de projet à part. Un tag les distingue des vraies questions.
EVAL_TAG = "eval"            # résumés de runs d'évaluation
EVALUATOR_TAG = "evaluator"  # traces des évaluateurs des expériences


def traced_in_project(evaluator):
    """
    Trace un évaluateur d'expérience dans le projet de l'application, tag « evaluator ».

    evaluate() trace ses évaluateurs dans un projet « evaluators » imposé par LangSmith : on
    lance donc evaluate(..., disable_evaluator_tracing=True) et on trace nous-mêmes.
    """
    import functools

    from langsmith import traceable, tracing_context

    from backend.evals.feedback.votes import TRACE_PROJECT

    traced = traceable(name=evaluator.__name__, run_type="chain",
                       project_name=TRACE_PROJECT, tags=[EVALUATOR_TAG])(evaluator)

    @functools.wraps(evaluator)  # garde la signature : evaluate() s'en sert pour passer les arguments
    def wrapper(*args, **kwargs):
        with tracing_context(enabled=True):  # evaluate() coupe le tracing autour des évaluateurs
            return traced(*args, **kwargs)
    return wrapper


def log_to_langsmith(name: str, summary: Dict, inputs: Dict):
    api_key = os.getenv("LANGSMITH_API_KEY")
    if not api_key:
        print("⚠️  LANGSMITH_API_KEY non défini, skip logging")
        return None

    from backend.evals.feedback.votes import TRACE_PROJECT
    project = TRACE_PROJECT
    try:
        client = Client()
        run_id = uuid.uuid4()
        # LangSmith n'accepte que: tool, chain, llm, retriever, embedding, prompt, parser.
        # "evaluation" était refusé avec un 422 et le logging ne fonctionnait donc jamais.
        now = datetime.now(timezone.utc)
        client.create_run(
            id=run_id,
            name=name,
            run_type="chain",
            inputs=inputs,
            outputs=summary,
            project_name=project,
            tags=[EVAL_TAG],
            # Sans end_time, le run resterait affiché « en cours » indéfiniment.
            start_time=now,
            end_time=now,
        )
        # create_run met en file d'attente : sans flush, une erreur serveur passerait
        # inaperçue et le message de succès serait mensonger.
        client.flush()
        print(f"✓ Résumé envoyé à LangSmith (projet {project}, tag « {EVAL_TAG} »)")
        return run_id
    except Exception as e:
        print(f"⚠️  Erreur LangSmith: {e}")
        return None


def index_chunks(tenant_id: str, chunks: List, pages_by_doc: Optional[Dict[str, List[str]]] = None,
                 force: bool = False):
    """
    Indexe des chunks déjà produits dans l'espace Qdrant `tenant_id`, document par document.
    Idempotent : un document dont les chunks n'ont pas changé n'est pas ré-embeddé. S'il est déjà
    indexé, à l'identique, dans l'espace d'un autre jeu de documents (l'essai sur 20 rapports avant
    les 84), ses vecteurs y sont recopiés au lieu d'être recalculés.
    Retourne le TenantStore.
    """
    from backend.vectorstore import get_eval_store

    store = get_eval_store()
    tenant = store.for_tenant(tenant_id)  # collections d'éval, jamais celles des utilisateurs
    by_source: Dict[str, List] = {}
    for chunk in chunks:
        by_source.setdefault(str(chunk.metadata.get("source")), []).append(chunk)
    for source, doc_chunks in by_source.items():
        digest = hashlib.sha256(source.encode())
        for chunk in doc_chunks:
            digest.update(chunk.page_content.encode())
        file_hash = digest.hexdigest()
        if tenant.has_document(file_hash) and not force:
            continue
        donors = [] if force else [t for t in store.tenants_with_document(file_hash) if t != tenant_id]
        if donors:
            tenant.copy_document_from(store.for_tenant(donors[0]), file_hash)
            continue
        pages = (pages_by_doc or {}).get(source, [])
        tenant.add_document(file_hash, source, doc_chunks, pages, enforce_quota=False)
    return tenant


def eval_index(docs: List[str], source: Optional[str] = None):
    """
    (retriever, PageStore) d'un jeu de documents, lus dans les collections d'évaluation de Qdrant.

    Qdrant est la seule source de l'index FinanceBench : prepare.py l'écrit une fois (OCR, chunks,
    embeddings, pages), les expériences ne font que le lire, avec la même chaîne de retrieval que la
    production. Rien n'est recalculé ici.
    """
    from backend.evals.financebench.prepare import DEFAULT_SOURCE, eval_tenant_for
    from backend.retriever.page_store import PageStore
    from backend.vectorstore import get_eval_store

    tenant = get_eval_store().for_tenant(eval_tenant_for(docs, source or DEFAULT_SOURCE))
    if not tenant.chunk_count():
        raise SystemExit(f"Espace Qdrant {tenant.tenant_id} vide ({', '.join(docs)}) : "
                         "lancer d'abord backend/evals/financebench/prepare.py")
    return RetrieverBuilder().build_hybrid_retriever(tenant), PageStore(tenant.pages())


def build_retriever_from_chunks(chunks: List, tenant_id: str,
                                pages_by_doc: Optional[Dict[str, List[str]]] = None):
    """
    Construit le retriever à partir de chunks déjà produits, sans repasser par l'OCR.

    L'évaluation FinanceBench pré-calcule ses chunks (OCR page par page + metadata de page)
    dans une phase séparée, les indexe dans un espace Qdrant dédié au jeu de documents, et
    réutilise ici exactement la même chaîne de retrieval que la production :
    Qdrant (BM25 sparse + dense) -> ParentChild -> MultiQuery -> Rerank Bedrock.
    """
    tenant = index_chunks(tenant_id, chunks, pages_by_doc)
    return RetrieverBuilder().build_hybrid_retriever(tenant)


# ══ Métriques ═════════════════════════════════════════════════════════════════

# Métriques d'évaluation partagées : retrieval (recall@k, precision@k, MRR, nDCG) et réponse (F1,
# context_hit). Extraites de l'ancien harness `backend/evals/run_eval.py` (supprimé avec le
# jeu interne) pour que l'évaluation FinanceBench garde exactement le même calcul.

def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> List[str]:
    return _normalize(text).split()


def _f1_score(pred: str, ref: str) -> float:
    pred_toks = _tokens(pred)
    ref_toks = _tokens(ref)
    if not pred_toks or not ref_toks:
        return 0.0
    common = {}
    for tok in pred_toks:
        common[tok] = common.get(tok, 0) + 1
    overlap = 0
    for tok in ref_toks:
        if common.get(tok, 0) > 0:
            overlap += 1
            common[tok] -= 1
    precision = overlap / max(len(pred_toks), 1)
    recall = overlap / max(len(ref_toks), 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _context_hits(docs, expected_answer: str, keywords: Optional[List[str]]) -> bool:
    context = "\n\n".join(getattr(d, "page_content", "") for d in docs)
    if expected_answer:
        if _normalize(expected_answer) in _normalize(context):
            return True
    if keywords:
        norm_ctx = _normalize(context)
        return any(_normalize(k) in norm_ctx for k in keywords if k)
    return False


def _normalize_list(values: Optional[List[str]]) -> List[str]:
    return [_normalize(v) for v in (values or []) if v]


def _token_overlap_score(gold_text: str, doc_text: str) -> float:
    """Calcule le ratio de tokens du gold présents dans le doc."""
    gold_toks = _tokens(gold_text)
    if not gold_toks:
        return 0.0
    doc_toks_set = set(_tokens(doc_text))
    matched = sum(1 for t in gold_toks if t in doc_toks_set)
    return matched / len(gold_toks)


def _doc_relevance_flags(docs, gold_passages: Optional[List[str]], fuzzy_threshold: float = 0.6) -> List[int]:
    """
    Détermine la pertinence de chaque doc par rapport aux gold passages.
    Utilise un matching hybride : substring exact OU token overlap >= seuil.
    """
    if not gold_passages:
        return []
    gold = _normalize_list(gold_passages)
    flags = []
    for doc in docs:
        content = _normalize(getattr(doc, "page_content", ""))
        # Match exact (substring) — rapide
        if any(g in content for g in gold):
            flags.append(1)
            continue
        # Match fuzzy (token overlap) — rattrape les reformulations et coupures
        if any(_token_overlap_score(g, content) >= fuzzy_threshold for g in gold):
            flags.append(1)
            continue
        flags.append(0)
    return flags


def _recall_at_k(flags: List[int], k: int) -> Optional[float]:
    if not flags:
        return None
    total_relevant = sum(flags)
    if total_relevant == 0:
        return 0.0
    return min(sum(flags[:k]) / total_relevant, 1.0)


def _precision_at_k(flags: List[int], k: int) -> Optional[float]:
    """
    Part des k premiers passages qui sont pertinents (dénominateur k, convention standard :
    renvoyer moins de k passages ne gonfle pas la précision).

    Sur FinanceBench, une question n'a souvent qu'une ou deux preuves : precision@10 est
    plafonnée bien en dessous de 1 par construction. Elle se lit en évolution d'un run à
    l'autre (moins de bruit dans le contexte), pas en valeur absolue.
    """
    if not flags or k <= 0:
        return None
    return sum(flags[:k]) / k


def _mrr_at_k(flags: List[int], k: int) -> Optional[float]:
    if not flags:
        return None
    for idx, rel in enumerate(flags[:k], start=1):
        if rel:
            return 1.0 / idx
    return 0.0


def _ndcg_at_k(flags: List[int], k: int) -> Optional[float]:
    if not flags:
        return None
    dcg = 0.0
    for i, rel in enumerate(flags[:k], start=1):
        if rel:
            dcg += 1.0 / math.log2(i + 1)
    ideal = sorted(flags, reverse=True)
    idcg = 0.0
    for i, rel in enumerate(ideal[:k], start=1):
        if rel:
            idcg += 1.0 / math.log2(i + 1)
    if idcg == 0:
        return 0.0
    return dcg / idcg


# ══ Juge FinanceBench ═════════════════════════════════════════════════════════

# Messages de refus émis par le pipeline (backend/agents/research_agent.py et workflow.py).
# Détectés sans appel LLM, pour économiser du budget de juge.
#
# ⚠️ Ces messages doivent constituer TOUTE la réponse pour valoir refus. Le premier
# marqueur est aussi la phrase que le prompt de génération demande au modèle d'employer
# (research_agent.py) : il apparaît donc légitimement au milieu d'une réponse complète,
# pour dire qu'un point secondaire manque. Une recherche de sous-chaîne classait ces
# réponses REFUSAL sans jamais appeler le juge — sur le run du 2 sept. 2026, les 6
# verdicts REFUSAL étaient tous des réponses de 300 à 1900 caractères, dont plusieurs
# jugées CORRECT par ailleurs. D'où la comparaison sur la réponse entière ci-dessous.
REFUSAL_MARKERS = [
    "cette information n'est pas disponible dans le document",
    "je ne peux pas répondre à cette question basée sur les documents fournis",
    "cette question n'est pas liée",
]

# Messages d'erreur technique : ni une réponse, ni un refus légitime.
# Ceux-là sont émis par le pipeline lui-même, jamais par le modèle : ils commencent
# toujours la réponse, et rien ne les suit qui ressemble à un contenu.
ERROR_MARKERS = [
    "une erreur est survenue lors du traitement de votre question",
    "une erreur est survenue lors de la génération de la réponse",
]

# Marge tolérée autour d'un message figé : le pipeline ajoute parfois une phrase
# d'invite derrière ("Veuillez poser une autre question..."). Au-delà, la réponse
# contient autre chose que le refus, et c'est au juge de trancher.
_CANNED_MAX_EXTRA_CHARS = 160


FINANCEBENCH_JUDGE_PROMPT = """Tu es un évaluateur expert en analyse financière. Tu compares la réponse d'un système RAG à la réponse de référence annotée par des experts sur le benchmark FinanceBench.
{examples}
**Question:** {question}

**Réponse de référence (ground truth):** {expected_answer}

**Justification de la référence:** {justification}

**Réponse générée par le système:** {generated_answer}

**Extraits du document fournis au système:**
{context}

Rends DEUX jugements.

1) VERDICT — procède en deux temps.
Étape 1 : quel est l'élément que la question demande ? (un chiffre, un nom, une liste, ou une conclusion Oui / Non)
Étape 2 : la réponse générée donne-t-elle cet élément, et les chiffres qu'elle cite sont-ils justes ?
- "CORRECT": oui. Tolère les écarts de formulation, d'unité, de mise en forme et d'arrondi ($1,577 = 1577.00 = 1 577 millions ; 8,74 Md$ pour 8,70 : écart ≤ 1 % en relatif). Ne pénalise PAS :
  - une réponse plus précise ou plus détaillée que la référence ;
  - une autre granularité cohérente avec la référence (des pays au lieu des régions qui les regroupent ; « International » quand la référence nomme une de ses sous-régions) ;
  - une autre métrique ou une autre méthode qui mène à la même conclusion ;
  - un détail secondaire inexact qui n'est pas l'objet de la question (le lieu de cotation quand la question demande quels titres sont cotés).
- "INCORRECT": le chiffre demandé est faux (écart au-delà de l'arrondi) ; la réponse donne un autre élément que celui demandé ; sa conclusion est inverse à la référence ; ou, pour une question fermée (Is… ? Does… ? Has… ?), elle ne répond pas clairement Oui ou Non dans le sens de la référence — rester dans l'entre-deux (« modérément ») ou esquiver (« ce ratio est peu pertinent ») quand la référence tranche est INCORRECT, même avec le bon chiffre.
- "REFUSAL": elle déclare ne pas pouvoir répondre ou que l'information n'est pas dans le document.

RÈGLE DE DÉPARTAGE (à appliquer AVANT de choisir REFUSAL) : si la réponse de référence dit elle-même que la métrique n'est pas applicable, pas publiée ou pas utilisée pour cette entreprise (ex. "Performance is not measured through gross margin", "There are none"), alors une réponse générée qui constate que le document ne fournit pas cette métrique, qu'elle n'y figure pas ou qu'il n'y en a pas est CORRECT — ce n'est pas un refus, c'est la bonne réponse. REFUSAL est réservé au cas où la référence contient une vraie information que la réponse générée déclare introuvable.

2) FAITHFULNESS (1-5) — tout ce qu'affirme la réponse est-il appuyé par les extraits fournis ?
- 5: intégralement appuyé | 4: inférences mineures raisonnables | 3: quelques affirmations non appuyées
- 2: plusieurs affirmations inventées | 1: hallucinations majeures
Un refus honnête vaut 5.

Réponds EXACTEMENT dans ce format. Remplis la grille ligne par ligne AVANT de choisir le verdict : le verdict en découle, il ne se décide pas en comparant la réponse à la référence d'un bloc.
ÉLÉMENT DEMANDÉ: [ce que la question demande, en quelques mots]
PRÉSENT DANS LA RÉPONSE: [oui|non] (une autre granularité cohérente ou une réponse plus précise compte comme oui)
CHIFFRES JUSTES: [oui|non|sans objet] (écart d'arrondi ≤ 1 % toléré ; un détail secondaire inexact ne compte pas)
QUESTION FERMÉE TRANCHÉE: [oui|non|sans objet] (Oui / Non clair, dans le sens de la référence)
VERDICT: [CORRECT|INCORRECT|REFUSAL] (CORRECT si toutes les lignes de la grille valent oui ou sans objet)
FAITHFULNESS: [1-5]
RAISON: [1-2 phrases]"""


# Écrit par `annotation.py examples` à partir d'une file d'annotation LangSmith.
JUDGE_EXAMPLES_PATH = ROOT_DIR / "backend" / "evals" / "financebench" / "judge_examples.json"


def load_judge_examples(path: Path = JUDGE_EXAMPLES_PATH) -> List[Dict]:
    """Les exemples annotés du juge FinanceBench ; aucun si le fichier n'existe pas."""
    import json
    if not path.exists():
        return []
    return json.loads(path.read_text())


# --- Contrôle numérique ------------------------------------------------------

# Référence faite d'un seul nombre : « 77.78 », « -0.02 », « $8.70 », « 9068.00 », « 24.26 ».
_NUMERIC_REFERENCE = re.compile(
    r"^\s*[$€]?\s*[-−–]?\(?\s*[$€]?\s*\d[\d,]*(?:\.\d+)?\s*\)?\s*%?\s*"
    r"(?:usd|eur|million|millions|billion|billions)?\s*$", re.IGNORECASE)
# Un nombre dans la réponse : signe, parenthèses comptables, séparateurs de milliers (« , »
# anglais ou espaces français), décimale « . » ou « , ».
_NUMBER = re.compile(r"(?<![\w.])([-−–]\s?|\()?\$?\s?(\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)((?:[.,]\d+)*)")
# Mêmes grandeurs exprimées à une autre échelle : millions / milliards, ratio / pourcentage.
_SCALES = (1, 1e3, 1e-3, 1e6, 1e-6, 100, 0.01)


def _to_float(text: str) -> Optional[float]:
    t = text.replace("$", "").replace("€", "").replace(",", "").replace("(", "-").replace(")", "")
    t = t.replace("−", "-").replace("–", "-").replace(" ", "")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group()) if m else None


def _answer_numbers(text: str) -> List[float]:
    """Les nombres d'un texte, avec les deux lectures d'une virgule ambiguë (8,738 = 8738 ou 8,738)."""
    out = []
    for m in _NUMBER.finditer(text):
        # « (1,577) » : négatif en convention comptable, mais un capex s'y écrit aussi ; « - » : négatif.
        signs = (1, -1) if (m.group(1) or "").startswith("(") else ((-1,) if m.group(1) else (1,))
        whole = re.sub(r"[ \u00a0\u202f]", "", m.group(2))
        tail = m.group(3)
        readings = set()
        if not tail:
            readings.add(whole)
        else:
            parts = re.split(r"([.,])", tail)[1:]  # [sep, digits, sep, digits…]
            seps = parts[0::2]
            groups = parts[1::2]
            if all(len(g) == 3 for g in groups) and len(groups) >= 1:
                readings.add(whole + "".join(groups))  # séparateurs de milliers
            # dernier séparateur = décimale, les précédents = milliers
            readings.add(whole + "".join(groups[:-1]) + "." + groups[-1])
        out.extend(sign * float(r) for r in readings for sign in signs)
    return out


def numeric_match(reference: str, answer: str) -> Optional[str]:
    """
    Si la référence est un nombre seul et que le début de la réponse (ses deux premières lignes,
    où le prompt de l'agent place le résultat) contient la même valeur, à l'arrondi de la référence ou à 1 % près,
    éventuellement à une autre échelle, retourne l'explication ; sinon None.
    """
    if not reference or not _NUMERIC_REFERENCE.match(reference):
        return None
    ref = _to_float(reference)
    if not ref:  # « 0 » répond à une question fermée (« s'il n'y en a pas, dites 0 ») : au juge
        return None
    if re.search(r"\(\s*[$€]?\s*\d", reference):
        ref = -abs(ref)
    decimals = len(reference.split(".")[1].strip().rstrip("%").split()[0]) if "." in reference else 0
    tolerance = max(0.01 * abs(ref), 0.5 * 10 ** -decimals)
    lines = [line for line in (answer or "").splitlines() if line.strip()][:2]
    first = re.sub(r"\[\d+\]", "", " ".join(lines).replace("*", ""))[:300]  # sans citations ni gras
    for value in _answer_numbers(first):
        for scale in _SCALES:
            if abs(value * scale - ref) <= tolerance:
                return f"{value:g} dans la réponse correspond à la référence {reference.strip()} (écart toléré {tolerance:g})"
    return None


@dataclass
class FinanceBenchVerdict:
    """Résultat du juge FinanceBench pour une réponse."""
    verdict: str  # CORRECT | INCORRECT | REFUSAL | ERROR
    faithfulness: float  # 1-5
    reason: str

    @property
    def is_correct(self) -> bool:
        return self.verdict == "CORRECT"

    @property
    def is_refusal(self) -> bool:
        return self.verdict == "REFUSAL"

    @property
    def is_hallucination(self) -> bool:
        """Répond avec assurance mais se trompe — la métrique centrale de FinanceBench."""
        return self.verdict == "INCORRECT"


class FinanceBenchJudge:
    """
    Juge LLM au protocole FinanceBench : un appel, un verdict ternaire + faithfulness.
    """

    VALID_VERDICTS = {"CORRECT", "INCORRECT", "REFUSAL"}

    def __init__(self, llm=None, model: Optional[str] = None, prompt: Optional[str] = None,
                 examples: Optional[List[Dict]] = None):
        self.llm = llm
        self.model = model or settings.EVAL_JUDGE_MODEL_ID
        # Même protocole avec un autre prompt (mêmes champs) : backend/evals/feedback/replay.py.
        self.prompt = prompt or FINANCEBENCH_JUDGE_PROMPT
        # Réponses annotées par un humain, montrées au juge pour calibrer son seuil.
        self.examples = load_judge_examples() if examples is None else examples

    @staticmethod
    def _same_question(a: str, b: str) -> bool:
        return " ".join(a.lower().split()) == " ".join(b.lower().split())

    def examples_block(self, question: str) -> str:
        """
        Les exemples annotés, sauf celui de la question jugée : sinon le juge recopierait le
        verdict humain, et l'accord mesuré par annotation.py ne vaudrait plus rien.
        """
        shown = [e for e in self.examples if not self._same_question(e["question"], question)]
        if not shown:
            return ""
        parts = ["\n**Exemples notés par un annotateur humain** (d'autres questions : ils montrent où "
                 "passe la limite entre CORRECT et INCORRECT) :"]
        for i, e in enumerate(shown, 1):
            comment = f"\nCommentaire de l'annotateur : {e['comment']}" if e.get("comment") else ""
            parts.append(f"\n--- Exemple {i} ---\nQuestion : {e['question']}\nRéférence : {e['reference']}\n"
                         f"Réponse : {e['answer']}\nVerdict humain : {e['verdict']}{comment}")
        parts.append("\n--- Fin des exemples. Juge maintenant la réponse suivante. ---\n")
        return "\n".join(parts)

    def _get_llm(self):
        if self.llm is None:
            from backend.llm.bedrock import chat_model
            # Le juge raisonne avant de répondre, et ce raisonnement compte dans max_tokens :
            # à 250, il épuisait le budget avant d'écrire le verdict.
            self.llm = chat_model(self.model, max_tokens=2000, region=settings.EVAL_JUDGE_REGION)
        return self.llm

    @staticmethod
    def _normalize(answer: str) -> str:
        """Minuscules, sans emphase markdown ni espaces multiples : un refus figé reste
        reconnaissable même quand le modèle le met en gras."""
        low = (answer or "").lower()
        for ch in "*_#`>":
            low = low.replace(ch, " ")
        return " ".join(low.split())

    @classmethod
    def detect_canned_response(cls, answer: str) -> Optional[str]:
        """
        Détecte sans appel LLM les messages figés du pipeline.
        Retourne "REFUSAL", "ERROR", ou None.

        Le message figé doit *être* la réponse, pas y apparaître : une réponse complète
        qui signale au passage qu'un point manque n'est pas un refus (voir REFUSAL_MARKERS).
        """
        low = cls._normalize(answer)
        if not low:
            return "ERROR"
        if any(low.startswith(m) for m in ERROR_MARKERS):
            return "ERROR"
        for marker in REFUSAL_MARKERS:
            if low.startswith(marker) and len(low) <= len(marker) + _CANNED_MAX_EXTRA_CHARS:
                return "REFUSAL"
        return None

    # « **VERDICT:** CORRECT » ou « VERDICT**: CORRECT » : sans cette tolérance, un juge qui
    # met ses champs en gras voyait tous ses CORRECT comptés INCORRECT (valeur par défaut).
    _FIELD = r"{}\**\s*:[\s*\[]*"

    def _parse(self, response: str) -> FinanceBenchVerdict:
        verdict = "INCORRECT"
        m = re.search(self._FIELD.format("VERDICT") + r"(CORRECT|INCORRECT|REFUSAL)", response, re.IGNORECASE)
        if m:
            verdict = m.group(1).upper()

        faithfulness = 3.0
        m = re.search(self._FIELD.format("FAITHFULNESS") + r"(\d(?:\.\d)?)", response, re.IGNORECASE)
        if m:
            try:
                faithfulness = max(1.0, min(5.0, float(m.group(1))))
            except ValueError:
                pass

        reason = "Impossible de parser la réponse du juge"
        m = re.search(self._FIELD.format("RAISON") + r"(.+?)(?:\n\s*\n|$)", response, re.IGNORECASE | re.DOTALL)
        if m:
            reason = " ".join(m.group(1).split())

        return FinanceBenchVerdict(verdict=verdict, faithfulness=faithfulness, reason=reason)

    def evaluate(
        self,
        question: str,
        expected_answer: str,
        generated_answer: str,
        context: str,
        justification: str = "",
        max_context_len: int = 6000,
    ) -> FinanceBenchVerdict:
        """Juge une réponse. Les messages figés du pipeline court-circuitent l'appel LLM."""
        canned = self.detect_canned_response(generated_answer)
        if canned == "ERROR":
            return FinanceBenchVerdict("ERROR", 0.0, "Erreur technique du pipeline (timeout ou LLM indisponible)")
        if canned == "REFUSAL":
            return FinanceBenchVerdict("REFUSAL", 5.0, "Refus explicite du pipeline (message figé)")

        if len(context) > max_context_len:
            context = context[:max_context_len] + "..."

        prompt = self.prompt.format(
            examples=self.examples_block(question),
            question=question,
            expected_answer=expected_answer or "(non fournie)",
            justification=justification or "(non fournie)",
            generated_answer=generated_answer,
            context=context or "(aucun extrait)",
        )
        try:
            response = self._get_llm().invoke(prompt)
            # .text : les seuls blocs de texte. Un modèle de raisonnement renvoie une liste
            # (raisonnement, puis texte) que _parse ne savait pas lire.
            verdict = self._parse(response.text)
        except Exception as e:
            # Un rate limit doit remonter à l'appelant pour être rejoué (backoff) ;
            # l'avaler en verdict ERROR fausserait le dénominateur de l'accuracy.
            if is_rate_limit(e):
                raise
            logger.warning(f"FinanceBenchJudge error: {e}")
            return FinanceBenchVerdict("ERROR", 0.0, f"Erreur du juge: {type(e).__name__}: {e}")
        # Référence purement numérique : le calcul tranche, pas le LLM. Le juge refusait 24,24
        # pour 24,26 (Activision) malgré la tolérance écrite dans son prompt. Seulement dans ce
        # sens : un chiffre exprimé autrement (unité, convention) reste à l'appréciation du juge.
        match = numeric_match(expected_answer, generated_answer)
        if match and verdict.verdict != "CORRECT":
            return FinanceBenchVerdict("CORRECT", verdict.faithfulness, f"Contrôle numérique : {match}")
        return verdict


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Optional[List[float]]:
    """
    Intervalle de Wilson à 95 % sur une proportion.

    Sur 21 questions l'intervalle fait ~35 points de large : sans lui, un écart d'une
    ou deux questions entre deux configurations se lit à tort comme une amélioration.
    """
    if n <= 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def aggregate_financebench_verdicts(verdicts: List[FinanceBenchVerdict]) -> Dict:
    """
    Agrège au protocole FinanceBench.
    Les erreurs techniques sont exclues du dénominateur et comptées à part.

    Chaque taux est publié avec son comptage brut et son IC95 : ce sont les trois
    chiffres nécessaires pour citer un résultat honnêtement sur un si petit échantillon.
    """
    if not verdicts:
        return {}

    scored = [v for v in verdicts if v.verdict != "ERROR"]
    errors = len(verdicts) - len(scored)
    if not scored:
        return {"count": 0, "errors": errors}

    n = len(scored)
    faith = [v.faithfulness for v in scored if v.faithfulness > 0]
    counts = {
        "correct": sum(1 for v in scored if v.is_correct),
        "refusal": sum(1 for v in scored if v.is_refusal),
        "hallucination": sum(1 for v in scored if v.is_hallucination),
    }
    return {
        "count": n,
        "errors": errors,
        "counts": counts,
        "accuracy": round(counts["correct"] / n, 4),
        "refusal_rate": round(counts["refusal"] / n, 4),
        "hallucination_rate": round(counts["hallucination"] / n, 4),
        "accuracy_ci95": wilson_interval(counts["correct"], n),
        "refusal_rate_ci95": wilson_interval(counts["refusal"], n),
        "hallucination_rate_ci95": wilson_interval(counts["hallucination"], n),
        "mean_faithfulness": round(sum(faith) / len(faith), 2) if faith else None,
    }


# ══ Answer relevancy ══════════════════════════════════════════════════════════

# Answer relevancy : la réponse traite-t-elle la question posée ?
#
# Méthode de RAGAS (Es et al., 2023) : un LLM écrit les questions auxquelles la réponse répond,
# puis on mesure la similarité cosinus moyenne entre leurs embeddings et celui de la question
# d'origine. Une réponse hors sujet, ou qui répond à côté (autre exercice, autre métrique),
# produit des questions éloignées ; une réponse évasive ou un refus vaut 0.
#
# Complémentaire du verdict du juge, pas redondant : le juge dit si la réponse est JUSTE par
# rapport à la référence ; la relevancy dit si elle est CENTRÉE sur la question — une réponse
# correcte noyée dans trois paragraphes hors sujet a un bon verdict et une relevancy basse.
# Ne compare jamais à la réponse de référence.

RELEVANCY_PROMPT = """Voici une réponse produite par un assistant d'analyse financière.

Réponse :
{answer}

1. Sur la première ligne, écris EVASIVE: OUI si la réponse ne s'engage pas (refus, « information
   non disponible », réponse vague sans contenu), sinon EVASIVE: NON.
2. Puis écris {n} questions différentes auxquelles cette réponse répond directement, une par
   ligne, dans la langue de la réponse, sans numérotation. Chaque question doit reprendre
   l'entreprise, la période et la métrique dont parle la réponse."""


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _strip_citations(text: str) -> str:
    return re.sub(r"(\[\d+\])+", "", text or "").strip()


def parse_generated(content: str, n: int):
    """(évasive, questions) depuis la sortie du LLM, tolérante aux puces et numéros."""
    evasive = False
    questions = []
    for raw in (content or "").splitlines():
        line = raw.strip().strip("*").strip()
        if not line:
            continue
        m = re.match(r"EVASIVE\s*:\s*\**\s*(OUI|NON|YES|NO)\b", line, re.IGNORECASE)
        if m:
            evasive = m.group(1).upper() in ("OUI", "YES")
            continue
        line = re.sub(r"^(\d+[.)]|[-•])\s*", "", line).strip()
        if len(line) > 8:
            questions.append(line)
    return evasive, questions[:n]


class AnswerRelevancy:
    def __init__(self, llm=None, embeddings=None, n_questions: int = 3):
        self.llm = llm
        self.embeddings = embeddings
        self.n = n_questions

    def _get_llm(self):
        if self.llm is None:
            from backend.llm.bedrock import chat_model
            # Métrique d'éval : sur un Mistral de Bedrock, comme le juge (voir settings).
            self.llm = chat_model(settings.EVAL_RELEVANCY_MODEL_ID, max_tokens=300,
                                  region=settings.EVAL_RELEVANCY_REGION)
        return self.llm

    def _get_embeddings(self):
        if self.embeddings is None:
            from backend.retriever.embeddings import get_embeddings
            self.embeddings = get_embeddings()
        return self.embeddings

    def score(self, question: str, answer: str) -> Optional[float]:
        """Score entre 0 et 1, ou None si la mesure n'a pas pu être faite (erreur technique)."""
        canned = FinanceBenchJudge.detect_canned_response(answer)
        if canned == "ERROR":
            return None
        if canned == "REFUSAL":
            return 0.0
        try:
            content = self._get_llm().invoke(
                RELEVANCY_PROMPT.format(answer=_strip_citations(answer), n=self.n)
            ).content
            evasive, generated = parse_generated(content, self.n)
            if evasive:
                return 0.0
            if not generated:
                return None
            vectors = self._get_embeddings().embed_documents([question] + generated)
        except Exception as e:
            if is_rate_limit(e):
                raise  # rejoué par l'appelant (backoff), pas une mesure manquante
            return None
        sims = [_cosine(vectors[0], v) for v in vectors[1:]]
        return round(max(0.0, sum(sims) / len(sims)), 4)
