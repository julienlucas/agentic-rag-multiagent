# Prépare l'évaluation FinanceBench, de zéro jusqu'à un index prêt :
#   1. télécharge les questions open source et les PDF (GitHub de Patronus AI) ;
#   2. écrit le dataset dans LangSmith (« FinanceBench »), seule source des questions ;
#   3. produit le texte des documents page par page, selon --source :
#        markdown (défaut) : le markdown OCR de `shhdwi/financebench-markdown`, recalé sur les pages
#                            du PDF (markdown_corpus.py) ; ses pages manquantes sont comblées selon --fill ;
#        ocr               : Mistral OCR de tout le PDF ;
#      puis découpage parent / enfant ;
#   4. indexe chunks, embeddings et pages dans les collections d'évaluation de Qdrant
#      (eval_chunks / eval_pages), séparées des documents des utilisateurs.
# Idempotent : relancé, il ne refait ni l'OCR (cache local) ni les embeddings déjà indexés.
#
# Usage:
#   uv run python backend/evals/financebench/prepare.py                 # 4 rapports, 26 questions
#   uv run python backend/evals/financebench/prepare.py --clean         # puis supprime PDF et cache locaux
#   uv run python backend/evals/financebench/prepare.py --docs extended # 18 rapports, 70 questions
#   uv run python backend/evals/financebench/prepare.py --docs pilot    # 20 rapports, 74 questions
#   uv run python backend/evals/financebench/prepare.py --docs all      # 84 rapports, 150 questions
#   ... --skip-embeddings  # tout sauf les embeddings (aucun appel Bedrock) : contrôle du corpus

import argparse
import base64
import hashlib
import json
import pickle
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mistralai import Mistral

from backend.config.settings import settings
from backend.document_processor.chunkers import ParentChildChunkingStrategy
from backend.evals.experiment_utils import call_with_backoff
from backend.evals.financebench.langsmith_sync import DEFAULT_DATASET, sort_rows
from backend.evals.financebench import markdown_corpus

HERE = Path(__file__).resolve().parent
PDF_DIR = HERE / "pdfs"
CACHE_DIR = HERE / "cache"

GITHUB_RAW = "https://raw.githubusercontent.com/patronus-ai/financebench/main"
QUESTIONS_URL = f"{GITHUB_RAW}/data/financebench_open_source.jsonl"

# Les 3 documents portant 7 questions chacun (21 questions), plus PepsiCo : 5 questions
# dont 2 `metrics-generated` à réponse numérique exacte (EBITDA, marge) = 26 questions.
DEFAULT_DOCS = [
    "AMD_2022_10K",
    "AMERICANEXPRESS_2022_10K",
    "BOEING_2022_10K",
    "PEPSICO_2022_10K",
]

# Jeu étendu : tous les documents portant au moins 3 questions (18 documents, 70 questions).
# À 26 questions, l'IC95 de l'accuracy fait ~35 points de large : un écart de 5 points entre
# deux versions n'y est pas mesurable. À 70, la largeur tombe vers ~20 points.
EXTENDED_MIN_QUESTIONS = 3

# Essai avant le corpus complet : les 20 documents qui portent le plus de questions (74 questions,
# dont les 4 du protocole publié).
PILOT_SIZE = 20

# Préréglages de --docs, et le suffixe de leur dataset LangSmith.
PRESETS = {"extended": "extended", "pilot": "pilot 20", "all": "84 docs"}

# Source du texte des documents (voir l'en-tête). Chacune a son propre espace Qdrant et son cache.
SOURCES = ("markdown", "ocr")
DEFAULT_SOURCE = "markdown"


def _question_counts(questions: List[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for q in questions:
        counts[q["doc_name"]] = counts.get(q["doc_name"], 0) + 1
    return counts


def extended_docs(questions: List[Dict], min_questions: int = EXTENDED_MIN_QUESTIONS) -> List[str]:
    """Documents du jeu étendu, triés : ceux qui portent au moins `min_questions` questions."""
    return sorted(d for d, n in _question_counts(questions).items() if n >= min_questions)


def preset_docs(questions: List[Dict], preset: str) -> List[str]:
    """Documents d'un préréglage de --docs, triés."""
    counts = _question_counts(questions)
    if preset == "extended":
        return extended_docs(questions)
    if preset == "pilot":  # à égalité de questions, ordre alphabétique : sélection stable
        return sorted(sorted(counts, key=lambda d: (-counts[d], d))[:PILOT_SIZE])
    if preset == "all":
        return sorted(counts)
    raise ValueError(f"Préréglage inconnu : {preset}")


def dataset_name_for(docs: List[str], preset: str = "") -> str:
    """
    Le dataset LangSmith « FinanceBench » porte les 26 questions du protocole publié. Tout
    autre jeu de documents va dans un dataset à part : avant, `--docs AMD_2022_10K` le
    réécrivait avec 7 questions, et le run suivant n'était plus comparable aux chiffres du README.
    """
    if sorted(docs) == sorted(DEFAULT_DOCS):
        return DEFAULT_DATASET
    return f"{DEFAULT_DATASET} ({PRESETS.get(preset, 'custom')})"


def pdf_url(doc_name: str) -> str:
    """Le PDF annoté par Patronus AI (copie GitHub) : celui dont les pages font foi."""
    return f"{GITHUB_RAW}/pdfs/{doc_name}.pdf"


# Longueur cible des snippets gold découpés depuis evidence_text.
# Les evidence FinanceBench vont de 180 à 2400 caractères : un parent chunk (1200 car.)
# ne peut pas contenir 60% des tokens d'une evidence de 2400 car., donc _doc_relevance_flags
# ne matcherait jamais. On découpe en snippets de la taille d'un chunk enfant.
GOLD_SNIPPET_CHARS = 250


def _log(msg: str):
    print(f"[prepare] {msg}", flush=True)


def eval_tenant_for(docs: List[str], source: str = DEFAULT_SOURCE) -> str:
    """
    Espace Qdrant dédié à un jeu de documents précis, dans une source précise.

    Indispensable : si on réutilisait un espace unique, un run lancé avec --docs sur un
    sous-ensemble chercherait aussi dans tous les documents indexés précédemment ; et un
    document indexé depuis deux sources y serait en double.
    """
    key = hashlib.sha256(f"{source}:{','.join(sorted(docs))}".encode()).hexdigest()[:12]
    return f"financebench-{key}"


def _pages_cache(doc_name: str, source: str) -> Path:
    """Texte page par page d'un document. L'OCR Mistral garde son nom historique."""
    return CACHE_DIR / (f"{doc_name}.ocr.json" if source == "ocr" else f"{doc_name}.{source}.json")


def _chunks_cache(doc_name: str, source: str) -> Path:
    return CACHE_DIR / f"{doc_name}.{source}.chunks.pkl"


def load_cached_chunks(docs: List[str], source: str = DEFAULT_SOURCE) -> List:
    """Recharge les chunks mis en cache par la phase prepare."""
    chunks = []
    missing = []
    for doc_name in docs:
        cache_path = _chunks_cache(doc_name, source)
        if not cache_path.exists():
            missing.append(doc_name)
            continue
        with open(cache_path, "rb") as f:
            chunks.extend(pickle.load(f)["chunks"])
    if missing:
        raise SystemExit(
            f"Chunks absents du cache pour: {', '.join(missing)}.\n"
            f"Lancez d'abord: uv run python backend/evals/financebench/prepare.py "
            f"--source {source} --docs {','.join(docs)}"
        )
    return chunks


def load_cached_pages(docs: List[str], source: str = DEFAULT_SOURCE) -> Dict[str, List[str]]:
    """
    Recharge le markdown page par page mis en cache par la phase prepare.
    Alimente le PageStore (outils grep / read_page de l'agent de recherche).
    """
    pages_by_doc: Dict[str, List[str]] = {}
    for doc_name in docs:
        cached = _load_ocr_cache(_pages_cache(doc_name, source))
        if not cached:
            raise SystemExit(
                f"Pages absentes du cache pour {doc_name}.\n"
                f"Lancez d'abord: uv run python backend/evals/financebench/prepare.py "
                f"--source {source} --docs {doc_name}"
            )
        pages_by_doc[doc_name] = [cached.get(i, "") for i in range(max(cached) + 1)]
    return pages_by_doc


def download(url: str, dest: Path, force: bool = False) -> Path:
    """Télécharge un fichier si absent."""
    if dest.exists() and not force and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    _log(f"Téléchargement {url} -> {dest.name}")
    with urllib.request.urlopen(url, timeout=180) as resp:
        data = resp.read()
    dest.write_bytes(data)
    _log(f"  {len(data) / 1e6:.1f} Mo")
    return dest


def load_questions(force: bool = False) -> List[Dict]:
    """Charge les 150 questions open-source de FinanceBench."""
    path = download(QUESTIONS_URL, CACHE_DIR / "financebench_open_source.jsonl", force)
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _pdf_page_count(pdf_path: Path) -> Optional[int]:
    """Nombre de pages lu localement, pour découper l'OCR en lots."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(pdf_path)).pages)
    except Exception as e:
        _log(f"  comptage de pages impossible ({type(e).__name__}), OCR en un seul appel")
        return None


def _document_url(client: Mistral, pdf_path: Path) -> str:
    """Upload le PDF une fois et renvoie une URL signée (repli sur data URL base64)."""
    file_bytes = pdf_path.read_bytes()
    try:
        uploaded = call_with_backoff(
            lambda: client.files.upload(
                file={"file_name": pdf_path.name, "content": file_bytes},
                purpose="ocr",
            ),
            "l'upload du PDF", attempts=7, base_delay=15.0, log=_log,
        )
        signed = client.files.get_signed_url(file_id=uploaded.id, expiry=1)
        return signed.url
    except Exception as e:
        _log(f"  upload indisponible ({type(e).__name__}: {e}), repli sur base64")
        return f"data:application/pdf;base64,{base64.b64encode(file_bytes).decode('utf-8')}"


def _load_ocr_cache(cache_path: Path) -> Dict[int, str]:
    """Relit le cache OCR, éventuellement partiel. Tolère l'ancien format (liste)."""
    if not cache_path.exists():
        return {}
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    if isinstance(data, list):  # ancien format
        return {i: page for i, page in enumerate(data)}
    return {int(k): v for k, v in (data.get("pages") or {}).items()}


def _save_ocr_cache(cache_path: Path, pages: Dict[int, str], n_pages: Optional[int], **extra):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"n_pages": n_pages, "pages": {str(k): v for k, v in sorted(pages.items())}, **extra}
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def ocr_document(
    client: Mistral,
    pdf_path: Path,
    doc_name: str,
    force: bool = False,
    batch_size: int = 50,
    delay: float = 2.0,
    only: Optional[List[int]] = None,
) -> List[str]:
    """
    OCR un PDF via Mistral OCR en conservant le découpage par page.

    Contrairement à DocumentProcessor._process_file qui joint toutes les pages en un seul
    markdown, on garde une entrée par page pour pouvoir attacher le numéro de page en
    metadata (les evidence FinanceBench sont annotées par page, zero-indexed).

    L'OCR est découpé en lots et le cache est écrit après chaque lot : un rate limit ou une
    interruption ne fait pas perdre le travail déjà payé — relancer reprend où ça s'est arrêté.

    `only` : les seules pages à OCRiser (index du PDF), pour combler les trous d'une autre
    source ; les pages non demandées et absentes du cache restent vides dans le résultat.
    """
    cache_path = CACHE_DIR / f"{doc_name}.ocr.json"
    cached: Dict[int, str] = {} if force else _load_ocr_cache(cache_path)
    n_pages = _pdf_page_count(pdf_path)

    todo: Optional[List[int]] = None
    if only is not None:
        if n_pages is None:
            raise SystemExit(f"{doc_name}: nombre de pages illisible, OCR de pages choisies impossible")
        todo = [i for i in sorted(set(only)) if i not in cached]
        if not todo:
            return [cached.get(i, "") for i in range(n_pages)]
        _log(f"{doc_name}: OCR de {len(todo)} page(s) : {todo}")
    elif cached and (n_pages is None or len(cached) >= n_pages):
        _log(f"{doc_name}: {len(cached)} pages depuis le cache OCR")
        return [cached.get(i, "") for i in range(max(cached) + 1)]
    elif cached:
        _log(f"{doc_name}: reprise de l'OCR ({len(cached)}/{n_pages} pages déjà en cache)")
    else:
        _log(f"{doc_name}: OCR ({pdf_path.stat().st_size / 1e6:.1f} Mo, {n_pages or '?'} pages)...")

    start = time.time()
    url = _document_url(client, pdf_path)

    def ocr_call(page_indices: Optional[List[int]]):
        kwargs = {
            "model": settings.MODEL_OCR_ID,
            "document": {"type": "document_url", "document_url": url},
            "include_image_base64": False,  # inutile ici, et très lourd en réponse
        }
        if page_indices is not None:
            kwargs["pages"] = page_indices
        return client.ocr.process(**kwargs)

    if n_pages is None:
        # Pas de découpage possible : un seul appel, avec retry.
        response = call_with_backoff(lambda: ocr_call(None), f"l'OCR de {doc_name}",
                                     attempts=7, base_delay=15.0, log=_log)
        for page in response.pages:
            cached[int(page.index)] = page.markdown or ""
        n_pages = len(cached)
    else:
        if todo is None:
            todo = [i for i in range(n_pages) if i not in cached]
        batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
        for batch_no, batch in enumerate(batches, start=1):
            response = call_with_backoff(
                lambda b=batch: ocr_call(b),
                f"l'OCR de {doc_name} (pages {batch[0]}-{batch[-1]})",
                attempts=7, base_delay=15.0, log=_log,
            )
            for page in response.pages:
                # On se fie à page.index : l'API renvoie l'index absolu dans le document.
                cached[int(page.index)] = page.markdown or ""
            _save_ocr_cache(cache_path, cached, n_pages)
            _log(f"  {doc_name}: lot {batch_no}/{len(batches)} — {len(cached)}/{n_pages} pages")
            if batch_no < len(batches) and delay:
                time.sleep(delay)

    _save_ocr_cache(cache_path, cached, n_pages)
    pages = [cached.get(i, "") for i in range(n_pages)]
    total_chars = sum(len(p) for p in pages)
    _log(
        f"{doc_name}: {len(todo) if only is not None else len(pages)} pages OCR en "
        f"{time.time() - start:.0f}s ({total_chars / 1000:.0f}k caractères en cache)"
    )
    return pages


def markdown_document(
    doc_name: str,
    pdf_path: Path,
    fill: str,
    ocr_client: Optional[Mistral] = None,
    force: bool = False,
    **ocr_kwargs,
) -> List[str]:
    """
    Texte page par page d'un document depuis `shhdwi/financebench-markdown`, recalé sur les pages
    du PDF (voir markdown_corpus.py). Environ 6 % des pages du corpus manquent à ce markdown ;
    `fill` dit comment les combler :
      - « ocr »      : Mistral OCR de ces seules pages (4 $ les 1 000 pages) ; les pages scannées,
                       sans texte extractible, sont aussi OCRisées pour servir de référence d'alignement ;
      - « pdf-text » : texte brut du PDF (gratuit, tableaux aplatis) ;
      - « none »     : pages laissées vides.
    """
    cache_path = _pages_cache(doc_name, "markdown")
    # Le cache n'est repris que s'il a été écrit avec le même remplissage des pages manquantes.
    same_fill = cache_path.exists() and json.loads(cache_path.read_text(encoding="utf-8")).get("fill") == fill
    cached = _load_ocr_cache(cache_path) if same_fill and not force else {}
    if cached:
        _log(f"{doc_name}: {len(cached)} pages depuis le cache markdown")
        return [cached.get(i, "") for i in range(max(cached) + 1)]

    md_path = download(markdown_corpus.MARKDOWN_URL.format(doc_name=doc_name),
                       CACHE_DIR / "markdown" / f"{doc_name}.md", force)
    reference = markdown_corpus.pdf_page_texts(pdf_path)
    scanned = [p for p, text in enumerate(reference) if not markdown_corpus.has_text(text)]
    if scanned and fill == "ocr":
        ocr = ocr_document(ocr_client, pdf_path, doc_name, force, only=scanned, **ocr_kwargs)
        for p in scanned:
            reference[p] = ocr[p]

    pages = markdown_corpus.markdown_pages(md_path.read_text(encoding="utf-8"), reference)
    gaps = markdown_corpus.page_gaps(pages, reference)
    if gaps and fill == "ocr":
        filler = ocr_document(ocr_client, pdf_path, doc_name, force, only=gaps, **ocr_kwargs)
    elif gaps and fill == "pdf-text":
        filler = reference
    else:
        filler = None
    for p in gaps if filler else []:
        pages[p] = filler[p]

    _save_ocr_cache(cache_path, dict(enumerate(pages)), len(pages), fill=fill, gaps=gaps, scanned=scanned)
    _log(f"{doc_name}: {len(pages)} pages, dont {len(gaps)} absentes du markdown "
         f"({'comblées : ' + fill if filler else 'laissées vides'}), {len(scanned)} scannées")
    return pages


def chunk_document(pages: List[str], doc_name: str, source: str = DEFAULT_SOURCE,
                   force: bool = False) -> List:
    """
    Chunke un document page par page en attachant source, page et lien du PDF en metadata.

    On utilise explicitement ParentChildChunkingStrategy (recursive) plutôt que la factory
    get_chunking_strategy() : la stratégie sémantique embed les paragraphes par batchs de 16
    en série, ce qui prendrait plusieurs minutes par 10-K de 250 pages.
    """
    cache_path = _chunks_cache(doc_name, source)
    # Empreinte des pages : des pages changées (autre remplissage des trous) invalident le cache.
    pages_hash = hashlib.sha256("\f".join(pages).encode()).hexdigest()
    if cache_path.exists() and not force:
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        if cached.get("pages_hash") == pages_hash:
            _log(f"{doc_name}: {len(cached['chunks'])} chunks depuis le cache")
            return cached["chunks"]

    chunker = ParentChildChunkingStrategy()
    all_chunks = []
    for page_idx, page_text in enumerate(pages):
        if not page_text.strip():
            continue
        metadata = {"source": doc_name, "doc_name": doc_name, "page": page_idx,
                    "pdf_url": pdf_url(doc_name)}
        all_chunks.extend(chunker.split(page_text, metadata))

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump({"pages_hash": pages_hash, "chunks": all_chunks}, f)
    _log(f"{doc_name}: {len(all_chunks)} chunks (children) générés")
    return all_chunks


def _split_evidence(text: str, target: int = GOLD_SNIPPET_CHARS) -> List[str]:
    """
    Découpe une evidence longue en snippets ~250 caractères, en respectant les fins de phrase
    et les sauts de ligne (les evidence de 10-K sont souvent des tableaux multi-lignes).
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= target:
        return [text]

    # Découpe en unités atomiques : lignes puis phrases.
    units: List[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if len(line) <= target:
            units.append(line)
        else:
            units.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip())

    snippets: List[str] = []
    current = ""
    for unit in units:
        candidate = f"{current} {unit}".strip()
        if current and len(candidate) > target:
            snippets.append(current)
            current = unit
        else:
            current = candidate
    if current:
        snippets.append(current)

    # Les snippets trop courts (< 40 car.) matchent trop facilement n'importe quel chunk.
    return [s for s in snippets if len(s) >= 40] or [text[:target]]


def _keywords_from_answer(answer: str) -> List[str]:
    """
    Extrait des mots-clés de la réponse gold pour context_hit_rate : nombres/montants
    et groupes nominaux capitalisés (noms de segments, de postes comptables...).
    """
    answer = answer or ""
    keywords = []
    # Montants et pourcentages : $1,577.00 / 16% / 1.57
    keywords.extend(re.findall(r"\$?\d[\d,]*\.?\d*\s*%?", answer)[:6])
    # Groupes nominaux capitalisés (Data Center, Customer deposits...)
    keywords.extend(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", answer)[:4])

    seen, out = set(), []
    for k in keywords:
        # Retire la ponctuation de bord ("737," -> "737", "2023." -> "2023")
        k = k.strip().strip(".,;:")
        # Une année seule n'est pas discriminante dans un 10-K, elle apparaît partout.
        if re.fullmatch(r"(19|20)\d{2}", k):
            continue
        if len(k) >= 2 and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out


def build_dataset(questions: List[Dict], docs: List[str]) -> List[Dict]:
    """Convertit les questions FinanceBench au format dataset du projet."""
    selected = [q for q in questions if q["doc_name"] in set(docs)]
    rows = []
    for q in selected:
        gold_passages, gold_pages = [], []
        for ev in q.get("evidence", []):
            gold_passages.extend(_split_evidence(ev.get("evidence_text", "")))
            page = ev.get("evidence_page_num")
            ev_doc = ev.get("evidence_doc_name") or q["doc_name"]
            if page is not None and str(page).strip() != "":
                gold_pages.append([ev_doc, int(page)])

        rows.append({
            "id": q["financebench_id"],
            "doc_name": q["doc_name"],
            "company": q.get("company"),
            "question": q["question"].strip(),
            "expected_answer": (q.get("answer") or "").strip(),
            "justification": (q.get("justification") or "").strip(),
            "answer_keywords": _keywords_from_answer(q.get("answer", "")),
            "gold_passages": gold_passages,
            "gold_pages": gold_pages,
            "question_type": q.get("question_type"),
            "question_reasoning": q.get("question_reasoning"),
        })

    return sort_rows(rows)  # groupé par type de question, pour la ventilation du résumé


def already_indexed(docs: List[str], source: str = DEFAULT_SOURCE) -> List[str]:
    """Documents du jeu déjà présents dans l'espace Qdrant d'évaluation."""
    from backend.vectorstore import get_eval_store
    sources = set(get_eval_store().for_tenant(eval_tenant_for(docs, source)).sources())
    return [d for d in docs if d in sources]


def markdown_gaps(doc_name: str) -> List[int]:
    """Pages du PDF absentes du markdown, telles qu'enregistrées dans son cache par markdown_document."""
    path = _pages_cache(doc_name, "markdown")
    return json.loads(path.read_text(encoding="utf-8")).get("gaps", []) if path.exists() else []


def unanswerable(questions: List[Dict], gaps_by_doc: Dict[str, List[int]]) -> Dict[str, str]:
    """Questions dont une preuve est sur une page manquante : {financebench_id: raison}."""
    out = {}
    for q in questions:
        for ev in q.get("evidence", []):
            doc = ev.get("evidence_doc_name") or q["doc_name"]
            page = ev.get("evidence_page_num")
            if page is not None and str(page).strip() != "" and int(page) in set(gaps_by_doc.get(doc, [])):
                out[q["financebench_id"]] = f"{doc} p.{int(page)} absente du markdown"
    return out


def check_evidence(questions: List[Dict], pages_by_doc: Dict[str, List[str]], tolerance: int = 1) -> List[Dict]:
    """
    Contrôle gratuit, avant tout embedding : chaque preuve annotée doit se retrouver dans le texte
    indexé, à sa page (± `tolerance`). Une preuve introuvable rend sa question insoluble pour le
    RAG, quel qu'il soit. Renvoie les preuves introuvables.

    Le seuil (la moitié des trigrammes de la preuve) laisse passer les preuves recopiées depuis un
    tableau, dont la mise en forme diffère de celle du document.
    """
    missing, checked = [], 0
    for q in questions:
        for ev in q.get("evidence", []):
            doc = ev.get("evidence_doc_name") or q["doc_name"]
            page = ev.get("evidence_page_num")
            pages = pages_by_doc.get(doc)
            if pages is None or page is None or str(page).strip() == "":
                continue
            page = int(page)
            window = pages[max(0, page - tolerance):page + tolerance + 1]
            covs = [markdown_corpus.evidence_coverage(ev.get("evidence_text", ""), p) for p in window]
            if not covs or covs[0] is None:
                continue
            checked += 1
            if max(covs) < 0.5:
                missing.append({"id": q["financebench_id"], "doc_name": doc, "page": page,
                                "coverage": round(max(covs), 2)})
    _log(f"Contrôle des preuves : {checked - len(missing)}/{checked} retrouvées à leur page (±{tolerance})")
    for m in missing:
        _log(f"  introuvable : {m['id']} {m['doc_name']} p.{m['page']} (couverture {m['coverage']:.0%})")
    return missing


def build_vector_store(chunks: List, docs: List[str], todo: List[str], source: str = DEFAULT_SOURCE,
                       force: bool = False):
    """
    Indexe les chunks dans l'espace Qdrant du jeu de documents, pour ne pas ré-embedder
    à chaque run (idempotent : un document déjà indexé à l'identique est sauté).
    """
    from backend.evals.experiment_utils import index_chunks

    tenant_id = eval_tenant_for(docs, source)
    _log(f"Indexation Qdrant (collections d'évaluation) de {len(chunks)} chunks dans l'espace {tenant_id}...")
    start = time.time()
    tenant = index_chunks(tenant_id, chunks, load_cached_pages(todo, source), force=force)
    _log(f"Espace {tenant_id}: {tenant.chunk_count()} chunks, prêt en {time.time() - start:.0f}s")


def main():
    parser = argparse.ArgumentParser(description="Prépare l'évaluation FinanceBench")
    parser.add_argument("--docs", default=",".join(DEFAULT_DOCS),
                        help="Documents à ingérer, séparés par des virgules, ou un préréglage : 'extended' "
                             f"(documents à {EXTENDED_MIN_QUESTIONS}+ questions : 18 documents, 70 questions), "
                             f"'pilot' ({PILOT_SIZE} documents, 74 questions), 'all' (84 documents, 150 questions)")
    parser.add_argument("--source", default=DEFAULT_SOURCE, choices=SOURCES,
                        help="Texte des documents : markdown shhdwi recalé sur le PDF (défaut), ou Mistral OCR")
    parser.add_argument("--fill", default="none", choices=("ocr", "pdf-text", "none"),
                        help="Source markdown : comment combler ses pages manquantes (voir markdown_document). "
                             "Avec « none » (défaut), les questions dont une preuve est sur une page manquante "
                             "sont retirées du dataset")
    parser.add_argument("--force", action="store_true", help="Ignore les caches et tout reconstruit")
    parser.add_argument("--skip-embeddings", action="store_true",
                        help="S'arrête avant les embeddings, sans indexer dans Qdrant (les expériences exigent l'index)")
    parser.add_argument("--clean", action="store_true",
                        help="Supprime les PDF et le cache local une fois l'index écrit dans Qdrant")
    parser.add_argument("--ocr-batch", type=int, default=50,
                        help="Pages par appel OCR. Baisser (ex. 20) si rate limits répétés")
    parser.add_argument("--ocr-delay", type=float, default=2.0,
                        help="Pause en secondes entre deux lots OCR")
    args = parser.parse_args()
    uses_ocr = args.source == "ocr" or args.fill == "ocr"

    # Vérifié AVANT tout appel payant : l'OCR ne doit pas tourner pour rien.
    missing = [name for name, ok in (
        ("LANGSMITH_API_KEY (dataset)", settings.LANGSMITH_API_KEY),
        ("MISTRALAI_API_KEY (OCR)", settings.MISTRALAI_API_KEY or not uses_ocr),
        ("QDRANT_URL (index persistant)", settings.QDRANT_URL or args.skip_embeddings),
    ) if not ok]
    if missing:
        raise SystemExit("Variables manquantes dans le .env : " + ", ".join(missing))

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    questions = load_questions(args.force)
    _log(f"{len(questions)} questions FinanceBench chargées")

    preset = args.docs.strip() if args.docs.strip() in PRESETS else ""
    docs = preset_docs(questions, preset) if preset else [d.strip() for d in args.docs.split(",") if d.strip()]
    _log(f"Source: {args.source}{' (pages manquantes : ' + args.fill + ')' if args.source == 'markdown' else ''}")
    _log(f"Documents ({len(docs)}): {', '.join(docs)}")
    questions = [q for q in questions if q["doc_name"] in set(docs)]
    if not questions:
        raise SystemExit(f"Aucune question trouvée pour: {docs}")
    dataset_name = dataset_name_for(docs, preset)

    # Documents déjà dans l'index Qdrant : ni téléchargement, ni OCR, ni embeddings (même sans cache).
    indexed = set() if (args.force or args.skip_embeddings) else set(already_indexed(docs, args.source))
    if indexed:
        _log(f"Déjà indexés dans Qdrant, sautés : {', '.join(sorted(indexed))}")
    todo = [d for d in docs if d not in indexed]

    # Pages de chaque document. En source markdown, il les faut toutes (même indexées, depuis le
    # cache ou gratuitement) : les pages manquantes décident des questions gardées dans le dataset.
    client = Mistral(api_key=settings.MISTRALAI_API_KEY) if uses_ocr else None
    ocr_kwargs = {"batch_size": args.ocr_batch, "delay": args.ocr_delay}
    pages_by_doc, gaps_by_doc = {}, {}
    for doc_name in (docs if args.source == "markdown" else todo):
        pdf_path = download(pdf_url(doc_name), PDF_DIR / f"{doc_name}.pdf", args.force)
        if args.source == "markdown":
            pages_by_doc[doc_name] = markdown_document(doc_name, pdf_path, args.fill, client, args.force, **ocr_kwargs)
            gaps_by_doc[doc_name] = markdown_gaps(doc_name) if args.fill == "none" else []
        else:
            pages_by_doc[doc_name] = ocr_document(client, pdf_path, doc_name, args.force, **ocr_kwargs)

    # Une question dont une preuve est sur une page absente du texte indexé est insoluble pour tout
    # RAG : on la retire du dataset plutôt que de la compter fausse. Jamais dans le protocole publié
    # (26 questions), qui doit rester comparable à ses runs antérieurs.
    dropped = unanswerable(questions, gaps_by_doc)
    if dropped and dataset_name == DEFAULT_DATASET:
        _log(f"⚠️ {len(dropped)} question(s) du protocole publié ont une preuve sur une page manquante ; "
             "gardées pour rester comparables (voir --fill)")
        dropped = {}
    for qid, reason in dropped.items():
        _log(f"  question retirée : {qid} ({reason})")
    kept = [q for q in questions if q["financebench_id"] not in dropped]
    _log(f"Questions : {len(kept)} gardées sur {len(questions)}")

    from backend.evals.financebench.langsmith_sync import get_client, upsert_dataset
    upsert_dataset(get_client(), dataset_name, build_dataset(kept, docs),  # le dataset n'existe que dans LangSmith
                   prune=dataset_name != DEFAULT_DATASET, corpus=docs)
    check_evidence(kept, pages_by_doc)

    if not todo:
        _log("Tout est déjà indexé : rien à faire.")
        return

    all_chunks = []
    for doc_name in todo:
        all_chunks.extend(chunk_document(pages_by_doc[doc_name], doc_name, args.source, args.force))
    _log(f"Total: {len(all_chunks)} chunks sur {len(todo)} documents")

    if not args.skip_embeddings:
        build_vector_store(all_chunks, docs, todo, args.source, args.force)
        if args.clean:
            # L'index (pages comprises) est dans Qdrant : les copies locales ne servent plus.
            shutil.rmtree(PDF_DIR, ignore_errors=True)
            shutil.rmtree(CACHE_DIR, ignore_errors=True)
            _log("PDF et cache locaux supprimés (l'index est dans Qdrant).")
    else:
        _log("Embeddings sautés (--skip-embeddings) : rien n'est écrit dans Qdrant.")
        return

    source_flag = "" if args.source == DEFAULT_SOURCE else f" --source {args.source}"
    _log("Préparation terminée. Lancer maintenant:")
    if dataset_name == DEFAULT_DATASET:
        _log(f"  uv run python backend/evals/experiment.py --mode both{source_flag}")
    else:
        _log(f'  uv run python backend/evals/experiment.py --mode both --dataset "{dataset_name}"{source_flag}')


if __name__ == "__main__":
    main()
