"""
Text extraction from reference documents the teacher uploads for question generation.

    extract_text("lecture.docx", data) -> str

Supported: PDF (typed text, via PyMuPDF), TXT / MD (UTF-8 or Windows-1252) and DOCX
(paragraphs and table cells, via python-docx). Scanned PDFs yield little or no text;
the caller decides what to do with a short result.
"""
import io
from pathlib import Path

SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md", ".docx")


class DocumentError(ValueError):
    """The file could not be read; the message is safe to show to the user."""


class UnsupportedDocument(DocumentError):
    """File type not handled."""


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocument(
            f"Unsupported file type '{ext or '(none)'}'. Use {', '.join(e.upper().lstrip('.') for e in SUPPORTED_EXTENSIONS)}."
        )
    if not data:
        return ""
    if ext in (".txt", ".md"):
        return _text_from_bytes(data)
    if ext == ".docx":
        return _text_from_docx(data)
    return _text_from_pdf(data)


def _text_from_bytes(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace").strip()


def _text_from_docx(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise DocumentError("DOCX support needs the python-docx package (pip install python-docx).") from exc
    try:
        doc = Document(io.BytesIO(data))
    except Exception as exc:
        raise DocumentError(f"Could not open the DOCX file: {exc}") from exc
    chunks = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
            if cells:
                chunks.append(" | ".join(cells))
    return "\n".join(chunks).strip()


def _text_from_pdf(data: bytes) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise DocumentError("PDF support needs the pymupdf package (pip install pymupdf).") from exc
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise DocumentError(f"Could not open the PDF: {exc}") from exc
    chunks = []
    try:
        for page in doc:
            try:
                chunks.append(page.get_text("text"))
            except Exception:
                continue
    finally:
        doc.close()
    return "\n".join(chunks).strip()
