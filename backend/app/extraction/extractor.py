"""The concrete `Extractor`: PDF, DOCX and plain text to body text only (ADR-0009).

Metadata never enters the pipeline: PDF document info (an Author field is a name) is never
read, and for DOCX only `word/document.xml` is opened, so core properties, headers, footers,
comments and the other parts are never touched. The format is chosen by magic bytes, not by the
declared name. No OCR: a file with no text layer fails with a plain reason. Every error message
is a constant; none carries file content or a library message (tenet 7).
"""

import io
import time
import zipfile
from collections.abc import Callable
from xml.etree.ElementTree import Element, ParseError

from defusedxml import ElementTree as SafeElementTree  # type: ignore[import-untyped]  # no stubs
from pypdf import PdfReader

from app.anonymizer.pipeline import MAX_INPUT_CHARS
from app.worker.errors import ExtractionError

# Upload limit is 10 MiB elsewhere; refuse more before any parser sees it.
MAX_BYTES_IN = 10 * 1024 * 1024
# A resume is a few pages; more is not one, and silently dropping pages would hide evidence.
MAX_PAGES = 20
# The lease is 180 s; extraction must end well inside it (worker LLD section 8).
DEADLINE_SECONDS = 60.0
# 500k characters of text is about 5 MB of WordprocessingML; 10 MiB leaves room for markup.
MAX_DOCX_XML_BYTES = 10 * 1024 * 1024
# Never return more than the anonymizer accepts.
MAX_TEXT_CHARS = MAX_INPUT_CHARS

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"
DOCX_BODY = "word/document.xml"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

NO_TEXT = "No text could be read from this file (a scanned image has no text layer)."
CORRUPT = "The file is corrupt or not a readable document."
ENCRYPTED = "The PDF is encrypted or password protected."
TOO_LARGE = "The file is too large to read."
TOO_MANY_PAGES = "The PDF has too many pages to be a resume."
TOO_MUCH_TEXT = "The file holds more text than can be processed."
TOO_SLOW = "Reading the file took too long."
UNSUPPORTED = "The file type is not supported."
NOT_UTF8 = "The text file is not valid UTF-8."


class ResumeExtractor:
    """Implements `app.worker.ports.Extractor`; sync, the Worker runs it in a thread."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        deadline_seconds: float = DEADLINE_SECONDS,
    ) -> None:
        self._clock = clock
        self._deadline_seconds = deadline_seconds

    def extract(self, data: bytes, media_type: str) -> str:
        if len(data) > MAX_BYTES_IN:
            raise ExtractionError(TOO_LARGE)
        if data.startswith(PDF_MAGIC):
            text = self._pdf(data)
        elif data.startswith(ZIP_MAGIC):
            text = _docx(data)
        elif media_type.split(";")[0].strip().lower().startswith("text/"):
            text = _plain(data)
        else:
            raise ExtractionError(UNSUPPORTED)
        if len(text) > MAX_TEXT_CHARS:
            raise ExtractionError(TOO_MUCH_TEXT)
        if not text.strip():
            raise ExtractionError(NO_TEXT)
        return text

    def _pdf(self, data: bytes) -> str:
        started = self._clock()
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ExtractionError(ENCRYPTED)
            pages = reader.pages
            if len(pages) > MAX_PAGES:
                raise ExtractionError(TOO_MANY_PAGES)
            parts: list[str] = []
            total = 0
            for page in pages:
                if self._clock() - started > self._deadline_seconds:
                    raise ExtractionError(TOO_SLOW)
                part = page.extract_text()
                total += len(part)
                if total > MAX_TEXT_CHARS:
                    raise ExtractionError(TOO_MUCH_TEXT)
                parts.append(part)
        except ExtractionError:
            raise
        except Exception as error:  # pypdf raises many unrelated types on hostile input
            raise ExtractionError(CORRUPT) from error
        return "\n".join(parts)


def _plain(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ExtractionError(NOT_UTF8) from error
    if "\x00" in text:
        raise ExtractionError(UNSUPPORTED)
    return text


def _docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            try:
                member = archive.open(DOCX_BODY)
            except KeyError as error:
                raise ExtractionError(UNSUPPORTED) from error
            with member:
                # Read one byte past the cap: a lying header cannot make us expand a bomb.
                xml = member.read(MAX_DOCX_XML_BYTES + 1)
        if len(xml) > MAX_DOCX_XML_BYTES:
            raise ExtractionError(TOO_LARGE)
        root = SafeElementTree.fromstring(xml, forbid_dtd=True)
    except ExtractionError:
        raise
    # defusedxml's exceptions (entities, DTD, external refs) subclass ValueError.
    except (zipfile.BadZipFile, ParseError, ValueError, OSError) as error:
        raise ExtractionError(CORRUPT) from error
    # Paragraphs in document order: body, table cells and text boxes; w:t only, so deleted
    # text (w:delText) and field instructions are left out.
    return "\n".join(_paragraph(p) for p in root.iter(f"{_W}p"))


def _paragraph(paragraph: Element) -> str:
    out: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{_W}t":
            out.append(node.text or "")
        elif node.tag == f"{_W}tab":
            out.append("\t")
        elif node.tag in (f"{_W}br", f"{_W}cr"):
            out.append("\n")
    return "".join(out)
