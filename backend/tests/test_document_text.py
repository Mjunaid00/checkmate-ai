"""
Text extraction from reference documents (PDF, TXT, DOCX) used by the quiz generator.
"""
import io
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_txt_utf8():
    from services.document_text import extract_text
    assert extract_text("notes.txt", "Photosynthesis converts light to energy.\n".encode("utf-8")) == \
        "Photosynthesis converts light to energy."


def test_txt_with_bom_and_latin1_fallback():
    from services.document_text import extract_text
    assert extract_text("a.txt", "﻿Hello".encode("utf-8")) == "Hello"
    assert extract_text("b.txt", "caf\xe9".encode("cp1252")) == "caf\xe9"


def test_markdown_is_treated_as_text():
    from services.document_text import extract_text
    assert "# Title" in extract_text("lecture.MD", b"# Title\nbody")


def test_docx_paragraphs_and_table_cells():
    from docx import Document
    from services.document_text import extract_text
    d = Document()
    d.add_paragraph("Newton's second law relates force and acceleration.")
    t = d.add_table(rows=1, cols=2)
    t.cell(0, 0).text = "Chlorophyll"
    t.cell(0, 1).text = "absorbs light"
    buf = io.BytesIO()
    d.save(buf)
    text = extract_text("Lecture 3.docx", buf.getvalue())
    assert "Newton's second law" in text
    assert "Chlorophyll" in text and "absorbs light" in text


def test_pdf_text():
    import fitz
    from services.document_text import extract_text
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Mitochondria are the powerhouse of the cell.")
    data = doc.tobytes()
    doc.close()
    assert "powerhouse" in extract_text("bio.pdf", data)


def test_unsupported_extension_raises():
    from services.document_text import extract_text, UnsupportedDocument
    with pytest.raises(UnsupportedDocument):
        extract_text("old.doc", b"xx")
    with pytest.raises(UnsupportedDocument):
        extract_text("image.png", b"xx")


def test_corrupt_docx_raises_document_error_not_crash():
    from services.document_text import extract_text, DocumentError
    with pytest.raises(DocumentError):
        extract_text("broken.docx", b"this is not a zip")


def test_supported_extensions_listed():
    from services.document_text import SUPPORTED_EXTENSIONS
    assert {".pdf", ".txt", ".docx", ".md"} <= set(SUPPORTED_EXTENSIONS)
