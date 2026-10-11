"""Pages OCR livrées avec un exemple : son chargement ne repaie pas Mistral OCR."""
import json
from types import SimpleNamespace

from backend.document_processor.file_handler import DocumentProcessor


def test_example_reads_its_bundled_pages_in_order(tmp_path):
    pdf = tmp_path / "AMD_2022_10K.pdf"
    pdf.write_bytes(b"%PDF")
    (tmp_path / "AMD_2022_10K.ocr.json").write_text(json.dumps({"n_pages": 3, "pages": {"2": "c", "0": "a", "1": "b"}}))
    assert DocumentProcessor._bundled_ocr(SimpleNamespace(name=str(pdf))) == ["a", "b", "c"]


def test_uploaded_file_and_example_without_sidecar_go_through_ocr(tmp_path):
    pdf = tmp_path / "rapport.pdf"
    pdf.write_bytes(b"%PDF")
    assert DocumentProcessor._bundled_ocr(SimpleNamespace(name=str(pdf))) == []
    assert DocumentProcessor._bundled_ocr(SimpleNamespace(name="rapport.pdf", file_obj=object())) == []
