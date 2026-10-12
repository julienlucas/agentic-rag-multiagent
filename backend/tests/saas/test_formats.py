"""Formats acceptés : contrôle du contenu, estimation des pages, extraction sans OCR."""
import io

import pytest

from backend.document_processor import formats


def _pdf(pages):
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=100, height=100)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def _xlsx(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Ventes"
    for r in rows:
        ws.append(r)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_check_accepts_matching_content_and_refuses_the_rest():
    assert formats.check("a.pdf", _pdf(1)) == "pdf"
    assert formats.check("notes.MD", b"# Titre") == "text"
    assert formats.check("photo.png", b"\x89PNG\r\n\x1a\n...") == "image"
    with pytest.raises(formats.UnsupportedFormat, match="ne correspond pas"):
        formats.check("a.pdf", b"MZ binaire")
    with pytest.raises(formats.UnsupportedFormat, match="non pris en charge"):
        formats.check("a.exe", b"MZ")
    with pytest.raises(formats.UnsupportedFormat):
        formats.check("notes.txt", b"\x00\x01\x02 binaire")


def test_text_is_paged_between_paragraphs():
    text = "\n\n".join(f"Paragraphe {i} " + "mot " * 200 for i in range(10))
    pages = formats.text_pages(text)
    assert len(pages) > 1 and all(len(p) <= formats.TEXT_PAGE_CHARS for p in pages)
    assert all(p.startswith("Paragraphe") for p in pages)  # aucune coupure en plein paragraphe
    assert formats.text_pages("   ") == []


def test_a_giant_paragraph_is_still_cut():
    pages = formats.text_pages("mot " * 5000)
    assert len(pages) >= 6 and all(len(p) <= formats.TEXT_PAGE_CHARS for p in pages)


def test_sheets_become_markdown_tables_of_50_rows():
    rows = [["Produit", "CA"]] + [[f"P{i}", i] for i in range(120)]
    pages = formats.sheet_pages("ventes.xlsx", _xlsx(rows))
    assert len(pages) == 3
    assert pages[0].startswith("## Feuille Ventes (lignes 2 à 51)")
    assert "| Produit | CA |" in pages[1] and "| P119 | 119 |" in pages[2]


def test_csv_with_semicolons():
    pages = formats.sheet_pages("t.csv", "nom;montant\nA;1\nB;2\n".encode())
    assert "| nom | montant |" in pages[0] and "| B | 2 |" in pages[0]


def test_html_is_converted_to_markdown_without_scripts():
    pages = formats.extract_pages("page.html", b"<h1>Rapport</h1><script>alert(1)</script><p>CA : 12</p>",
                                  ocr=None)
    assert pages[0].startswith("# Rapport") and "alert" not in pages[0] and "CA : 12" in pages[0]


def test_page_estimates():
    assert formats.estimate_pages("a.pdf", _pdf(7)) == 7
    assert formats.estimate_pages("a.png", b"\x89PNG") == 1
    assert formats.estimate_pages("a.txt", b"court") == 1


def test_ocr_receives_the_right_mime_type():
    seen = []

    def ocr(content, mime):
        seen.append(mime)
        return ["page"]

    formats.extract_pages("a.pdf", b"%PDF", ocr)
    formats.extract_pages("a.jpg", b"\xff\xd8", ocr)
    formats.extract_pages("a.docx", b"PK", ocr)  # sans LibreOffice : le DOCX part tel quel
    formats.extract_pages("a.docx", b"PK", ocr, pdf=b"%PDF")  # converti : c'est le PDF qui part
    assert seen == ["application/pdf", "image/jpeg",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/pdf"]
    with pytest.raises(formats.UnsupportedFormat, match="LibreOffice"):
        formats.extract_pages("a.odt", b"PK", ocr)
