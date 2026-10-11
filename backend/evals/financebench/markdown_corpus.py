# Corpus FinanceBench en markdown, découpé selon les pages du PDF.
#
# Source : le dataset Hugging Face `shhdwi/financebench-markdown`, un markdown OCR des 84 documents
# qui portent les 150 questions open source, avec ses tableaux en HTML. Il remplace l'OCR Mistral
# (même qualité de texte et de tableaux, sans coût), mais il n'a pas de découpage par page : ses
# balises <page_number> reprennent les numéros imprimés (table des matières comprise), pas les pages
# du PDF. Or les preuves FinanceBench sont annotées par page du PDF (index à partir de 0).
#
# On reconstruit donc la pagination : chaque bloc du markdown (paragraphe, ligne de tableau) est
# rattaché à la page du PDF dont le texte (extrait par pypdf, gratuit) contient ses n-grammes,
# sous contrainte d'ordre (les pages ne reculent jamais d'un bloc au suivant). Les tableaux HTML
# sont rendus en tableaux markdown, le format de l'OCR Mistral ; un tableau à cheval sur deux pages
# est coupé en deux, son en-tête répété sur la seconde.

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

MARKDOWN_URL = "https://huggingface.co/datasets/shhdwi/financebench-markdown/resolve/main/data/{doc_name}.md"

# Taille des n-grammes d'alignement : assez longs pour être propres à une page, assez courts pour
# qu'une ligne de tableau (« Embedded 4552 246 ») en porte au moins un.
NGRAM_SIZES = (4, 3)
# Un n-gramme présent sur plus de pages que ça (en-têtes répétés, « in millions ») ne vote pas.
MAX_PAGES_PER_NGRAM = 3

_TABLE_RE = re.compile(r"<table\b.*?</table>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_PAGE_NUMBER_RE = re.compile(r"<page_number>.*?</page_number>", re.S | re.I)


# ── Tokens ────────────────────────────────────────────────────────────────────

def tokens(text: str) -> List[str]:
    """Mots et nombres en minuscules, séparateurs de milliers retirés : « $23,601 » -> « 23601 »."""
    text = _TAG_RE.sub(" ", html.unescape(text or "")).lower()
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    return re.findall(r"[a-z]+|\d+(?:\.\d+)?", text)


def _ngrams(toks: List[str], n: int) -> List[Tuple[str, ...]]:
    return [tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)]


# ── Lecture du markdown ───────────────────────────────────────────────────────

class _Row:
    """Une ligne de tableau : ses cellules (texte, colspan, rowspan) et si elle est d'en-tête."""

    def __init__(self, header: bool):
        self.header = header
        self.cells: List[Tuple[str, int, int]] = []


class _TableParser(HTMLParser):
    """Lignes d'un tableau HTML. Le texte des balises de mise en forme (<strong>, <sup>…) est gardé."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: List[_Row] = []
        self._in_thead = False
        self._cell: Optional[List[str]] = None
        self._span = (1, 1)

    def handle_starttag(self, tag, attrs):
        if tag == "thead":
            self._in_thead = True
        elif tag == "tr":
            self.rows.append(_Row(self._in_thead))
        elif tag in ("td", "th"):
            if not self.rows:
                self.rows.append(_Row(self._in_thead))
            a = dict(attrs)
            self._span = (_int(a.get("colspan")), _int(a.get("rowspan")))
            self._cell = []
            if tag == "th":
                self.rows[-1].header = True
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag == "thead":
            self._in_thead = False
        elif tag in ("td", "th") and self._cell is not None:
            self.rows[-1].cells.append((_clean_inline("".join(self._cell)), *self._span))
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _int(value) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _clean_inline(text: str) -> str:
    """Texte d'une cellule : balises de l'OCR retirées (texte gardé), espaces normalisés."""
    text = _PAGE_NUMBER_RE.sub(lambda m: _TAG_RE.sub("", m.group(0)), html.unescape(text))
    text = _TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip().replace("|", "\\|")


def _grid(rows: List[_Row]) -> List[List[str]]:
    """Cellules à plat : un colspan laisse des cellules vides à sa droite, un rowspan en dessous."""
    grid: List[List[str]] = []
    pending: Dict[Tuple[int, int], str] = {}  # (ligne, colonne) occupées par un rowspan
    for r, row in enumerate(rows):
        out: List[str] = []
        col = 0
        for text, colspan, rowspan in row.cells:
            while (r, col) in pending:
                out.append(pending.pop((r, col)))
                col += 1
            for k in range(colspan):
                out.append(text if k == 0 else "")
                for below in range(1, rowspan):
                    pending[(r + below, col + k)] = ""
            col += colspan
        while (r, col) in pending:
            out.append(pending.pop((r, col)))
            col += 1
        grid.append(out)
    return grid


def table_to_markdown(rows: List[_Row]) -> str:
    """Tableau markdown, comme l'OCR Mistral : la 1re ligne sert d'en-tête, puis « | --- | »."""
    grid = [g for g in _grid(rows) if any(c for c in g)]
    if not grid:
        return ""
    width = max(len(g) for g in grid)
    lines = ["| " + " | ".join(g + [""] * (width - len(g))) + " |" for g in grid]
    lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
    return "\n".join(lines)


def _clean_text(text: str) -> str:
    """Texte hors tableau : numéros de page imprimés retirés, gras HTML en markdown, autres balises ôtées."""
    text = html.unescape(text)
    text = _PAGE_NUMBER_RE.sub("", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?(?:strong|b)>", "**", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.I)
    text = _TAG_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_blocks(markdown: str) -> List[Dict]:
    """
    Blocs du document, dans l'ordre : {"kind": "text", "text"} pour un paragraphe,
    {"kind": "row", "table": i, "row": _Row} pour chaque ligne d'un tableau.
    """
    blocks: List[Dict] = []
    pos, table_no = 0, 0
    for m in _TABLE_RE.finditer(markdown):
        blocks.extend(_text_blocks(markdown[pos:m.start()]))
        parser = _TableParser()
        parser.feed(m.group(0))
        for row in parser.rows:
            if row.cells:
                blocks.append({"kind": "row", "table": table_no, "row": row})
        table_no += 1
        pos = m.end()
    blocks.extend(_text_blocks(markdown[pos:]))
    return blocks


def _text_blocks(text: str) -> List[Dict]:
    out = []
    for para in re.split(r"\n\s*\n", text):
        para = _clean_text(para)
        if para:
            out.append({"kind": "text", "text": para})
    return out


def _block_text(block: Dict) -> str:
    if block["kind"] == "text":
        return block["text"]
    return " ".join(c[0] for c in block["row"].cells)


# ── Alignement sur les pages du PDF ───────────────────────────────────────────

def pdf_page_texts(pdf_path: Path) -> List[str]:
    """Texte brut de chaque page du PDF (pypdf) : la référence de pagination, index à partir de 0."""
    from pypdf import PdfReader
    pages = []
    for page in PdfReader(str(pdf_path)).pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # page illisible : elle ne votera pour aucun bloc
            pages.append("")
    return pages


def assign_pages(blocks: List[Dict], reference_pages: List[str]) -> List[int]:
    """
    Page (index du PDF) de chaque bloc. Chaque n-gramme d'un bloc présent sur 1 à 3 pages de la
    référence vote pour elles ; une programmation dynamique choisit ensuite la suite de pages qui
    recueille le plus de votes sans jamais reculer. Un bloc sans vote (logo, ligne trop courte)
    prend la page de ses voisins.
    """
    n_pages = len(reference_pages)
    index: Dict[int, Dict[Tuple[str, ...], set]] = {n: {} for n in NGRAM_SIZES}
    for p, text in enumerate(reference_pages):
        toks = tokens(text)
        for n in NGRAM_SIZES:
            for g in _ngrams(toks, n):
                index[n].setdefault(g, set()).add(p)

    votes = np.zeros((len(blocks), n_pages), dtype=np.float32)
    for i, block in enumerate(blocks):
        toks = tokens(_block_text(block))
        n = next((n for n in NGRAM_SIZES if len(toks) >= n), None)
        if n is None:
            continue
        for g in _ngrams(toks, n):
            pages = index[n].get(g)
            if pages and len(pages) <= MAX_PAGES_PER_NGRAM:
                for p in pages:
                    votes[i, p] += 1.0 / len(pages)

    # Viterbi monotone : score[p] = meilleur total des blocs précédents finissant à une page <= p.
    back = np.zeros((len(blocks), n_pages), dtype=np.int32)
    score = np.zeros(n_pages, dtype=np.float32)
    arange = np.arange(n_pages, dtype=np.int32)
    for i in range(len(blocks)):
        best = np.maximum.accumulate(score)
        # À égalité, rester sur la même page plutôt que revenir sur une page antérieure.
        back[i] = np.maximum.accumulate(np.where(score == best, arange, 0))
        score = best + votes[i]

    pages_out = [0] * len(blocks)
    p = int(np.argmax(score))
    for i in range(len(blocks) - 1, -1, -1):
        pages_out[i] = p
        p = int(back[i, p])
    return pages_out


# ── Rendu page par page ───────────────────────────────────────────────────────

def render_pages(blocks: List[Dict], block_pages: List[int], n_pages: int) -> List[str]:
    """
    Markdown de chaque page du PDF. Un tableau coupé par un saut de page répète son en-tête.

    Le markdown source recopie souvent une page juste après elle-même (sur AMD 2022, la moitié des
    paragraphes longs sont en double, et 599 doublons sur 606 tombent sur la page de l'original) :
    un paragraphe ou un tableau déjà présent sur sa page n'y est pas répété.
    """
    parts: List[List[str]] = [[] for _ in range(n_pages)]
    seen: List[set] = [set() for _ in range(n_pages)]

    def add(page: int, text: str):
        if text not in seen[page]:
            seen[page].add(text)
            parts[page].append(text)

    i = 0
    while i < len(blocks):
        block, page = blocks[i], block_pages[i]
        if block["kind"] == "text":
            add(page, block["text"])
            i += 1
            continue
        table = block["table"]
        rows_all, pages_all = [], []
        while i < len(blocks) and blocks[i]["kind"] == "row" and blocks[i]["table"] == table:
            rows_all.append(blocks[i]["row"])
            pages_all.append(block_pages[i])
            i += 1
        header = [r for r in rows_all if r.header]
        start = 0
        for k in range(1, len(rows_all) + 1):
            if k == len(rows_all) or pages_all[k] != pages_all[start]:
                rows = rows_all[start:k]
                if start > 0 and header and not rows[0].header:
                    rows = header + rows
                rendered = table_to_markdown(rows)
                if rendered:
                    add(pages_all[start], rendered)
                start = k
    return ["\n\n".join(p) for p in parts]


def markdown_pages(markdown: str, reference_pages: List[str]) -> List[str]:
    """Le markdown d'un document, découpé selon les pages de son PDF (autant d'entrées que de pages)."""
    blocks = parse_blocks(markdown)
    return render_pages(blocks, assign_pages(blocks, reference_pages), len(reference_pages))


# ── Contrôles ─────────────────────────────────────────────────────────────────

# En dessous de ce nombre de trigrammes distincts, une page n'a pas de texte exploitable
# (page blanche, scan sans couche texte) : elle ne sert ni de référence ni de contrôle.
MIN_PAGE_TRIGRAMS = 15
# Une page dont le markdown couvre moins de 30 % des trigrammes du PDF manque au markdown.
GAP_COVERAGE = 0.3


def _trigrams(text: str) -> set:
    return set(_ngrams(tokens(text), 3))


def has_text(text: str) -> bool:
    return len(_trigrams(text)) >= MIN_PAGE_TRIGRAMS


def page_gaps(pages: List[str], reference_pages: List[str]) -> List[int]:
    """Pages dont le PDF a du texte mais que le markdown ne couvre pas (pages manquantes)."""
    gaps = []
    for p, (page, ref) in enumerate(zip(pages, reference_pages)):
        ref_grams = _trigrams(ref)
        if len(ref_grams) >= MIN_PAGE_TRIGRAMS and len(ref_grams & _trigrams(page)) / len(ref_grams) < GAP_COVERAGE:
            gaps.append(p)
    return gaps


def evidence_coverage(evidence: str, page: str) -> Optional[float]:
    """Part des trigrammes d'une preuve FinanceBench présents dans une page (None : preuve vide)."""
    grams = _trigrams(evidence)
    return len(grams & _trigrams(page)) / len(grams) if grams else None
