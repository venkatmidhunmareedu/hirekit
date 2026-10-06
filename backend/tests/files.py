"""Byte strings that look like resumes to the upload sniffer; none is a parseable document."""

import io
import zipfile

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_TYPE = "application/pdf"


def pdf_bytes(tag: str = "a") -> bytes:
    """A file that starts like a PDF; `tag` makes the bytes (and the hash) differ."""
    return f"%PDF-1.7\n{tag}\n%%EOF".encode()


def zip_bytes(*names: str) -> bytes:
    """A zip holding one tiny entry per name."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name in names:
            archive.writestr(name, "<x/>")
    return out.getvalue()


def docx_bytes(tag: str = "a") -> bytes:
    """A zip with the part every DOCX has."""
    return zip_bytes("[Content_Types].xml", "word/document.xml", f"tag/{tag}")
