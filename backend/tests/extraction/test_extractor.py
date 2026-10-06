"""Extractor behaviour with tiny files built here by hand (no fixtures on disk, no OCR)."""

import io
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.anonymizer.pipeline import MAX_INPUT_CHARS
from app.extraction import ResumeExtractor
from app.extraction import extractor as module
from app.worker.errors import ExtractionError

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_pdf(pages: list[str], author: str | None = None) -> bytes:
    """A minimal valid PDF, one Helvetica text line per page, with a correct xref table."""
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        stream = f"BT /F1 12 Tf 72 700 Td ({text}) Tj ET".encode()
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    trailer_extra = ""
    if author is not None:
        objs.append(f"<< /Author ({author}) /Title (Doc Title Secret) >>".encode())
        trailer_extra = f" /Info {len(objs)} 0 R"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R{trailer_extra} >>\n".encode()
    out += b"startxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


def make_docx(
    body_xml: str, extra: dict[str, str] | None = None, raw_body: bytes | None = None
) -> bytes:
    buf = io.BytesIO()
    document = (
        raw_body
        if raw_body is not None
        else (
            f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{body_xml}</w:body>'
            "</w:document>"
        ).encode()
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", document)
        for name, content in (extra or {}).items():
            z.writestr(name, content)
    return buf.getvalue()


def para(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def extract(data: bytes, media_type: str = PDF) -> str:
    return ResumeExtractor().extract(data, media_type)


def test_pdf_body_text_is_extracted() -> None:
    assert "Python engineer" in extract(make_pdf(["Python engineer"]))


def test_pdf_metadata_is_never_returned() -> None:
    data = make_pdf(["Body words"], author="Zed Quark")
    assert b"Zed Quark" in data
    text = extract(data)
    assert "Body words" in text
    assert "Zed Quark" not in text
    assert "Secret" not in text


def test_docx_paragraphs_and_table_cells_are_extracted() -> None:
    cells = f"<w:tc>{para('Cell Alpha')}</w:tc><w:tc>{para('Cell Beta')}</w:tc>"
    table = f"<w:tbl><w:tr>{cells}</w:tr></w:tbl>"
    text = extract(make_docx(para("Intro line") + table), DOCX)
    assert "Intro line" in text
    assert "Cell Alpha" in text
    assert "Cell Beta" in text


def test_docx_other_parts_are_never_returned() -> None:
    extra = {
        "docProps/core.xml": "<cp:coreProperties><dc:creator>Zed Quark</dc:creator>"
        "</cp:coreProperties>",
        "word/header1.xml": f'<w:hdr xmlns:w="{W}">{para("HeaderSecret")}</w:hdr>',
        "word/footer1.xml": f'<w:ftr xmlns:w="{W}">{para("FooterSecret")}</w:ftr>',
        "word/comments.xml": f'<w:comments xmlns:w="{W}">{para("CommentSecret")}</w:comments>',
    }
    text = extract(make_docx(para("Body only"), extra), DOCX)
    assert text == "Body only"


def test_wrong_declared_type_is_ignored_when_magic_says_pdf() -> None:
    assert "Magic wins" in extract(make_pdf(["Magic wins"]), DOCX)
    assert "Magic wins" in extract(make_pdf(["Magic wins"]), "text/plain")


def test_plain_text_is_decoded_as_utf8() -> None:
    assert extract("Zoë café".encode(), "text/plain; charset=utf-8") == "Zoë café"


def test_plain_text_that_is_not_utf8_fails() -> None:
    with pytest.raises(ExtractionError, match="not valid UTF-8"):
        extract(b"\xff\xfe\xfa", "text/plain")


def test_unknown_bytes_with_a_non_text_type_fail() -> None:
    with pytest.raises(ExtractionError, match="not supported"):
        extract(b"just words", PDF)


def test_zip_without_a_document_part_fails() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<x/>")
    with pytest.raises(ExtractionError, match="not supported"):
        extract(buf.getvalue(), DOCX)


def test_scanned_pdf_with_no_text_layer_fails() -> None:
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    buf = io.BytesIO()
    writer.write(buf)
    with pytest.raises(ExtractionError, match="No text could be read"):
        extract(buf.getvalue())


def test_whitespace_only_docx_fails() -> None:
    with pytest.raises(ExtractionError, match="No text could be read"):
        extract(make_docx(para("   ")), DOCX)


def test_corrupt_pdf_fails() -> None:
    with pytest.raises(ExtractionError, match="corrupt"):
        extract(b"%PDF-1.4\n1 0 obj << garbage")


def test_corrupt_docx_fails() -> None:
    with pytest.raises(ExtractionError, match="corrupt"):
        extract(b"PK\x03\x04 not really a zip", DOCX)


def test_encrypted_pdf_fails() -> None:
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    writer.encrypt("secret-pass")
    buf = io.BytesIO()
    writer.write(buf)
    with pytest.raises(ExtractionError, match="encrypted"):
        extract(buf.getvalue())


def test_zip_bomb_is_refused_without_expanding_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "MAX_DOCX_XML_BYTES", 1000)
    bomb = make_docx("", raw_body=b"<a>" + b"x" * 50_000 + b"</a>")
    assert len(bomb) < 1000
    reads: list[int] = []
    real = zipfile.ZipExtFile.read

    def spy(self: zipfile.ZipExtFile, n: int | None = -1) -> bytes:
        data = real(self, n)
        reads.append(len(data))
        return data

    monkeypatch.setattr(zipfile.ZipExtFile, "read", spy)
    with pytest.raises(ExtractionError, match="too large"):
        extract(bomb, DOCX)
    assert max(reads) <= 1001


def test_entity_expansion_is_refused() -> None:
    laughs = (
        b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "lol"><!ENTITY b "&a;&a;&a;&a;">]>'
        b"<w:document xmlns:w='" + W.encode() + b"'><w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p>"
        b"</w:body></w:document>"
    )
    with pytest.raises(ExtractionError, match="corrupt"):
        extract(make_docx("", raw_body=laughs), DOCX)


def test_external_entity_is_refused_and_no_file_is_read(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("FILE-SECRET-CONTENT")
    xxe = (
        f'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file://{secret}">]>'
        f"<w:document xmlns:w='{W}'><w:body><w:p><w:r><w:t>&x;</w:t></w:r></w:p></w:body>"
        "</w:document>"
    ).encode()
    with pytest.raises(ExtractionError) as info:
        extract(make_docx("", raw_body=xxe), DOCX)
    assert "FILE-SECRET" not in str(info.value)


def test_pdf_over_the_page_cap_fails() -> None:
    with pytest.raises(ExtractionError, match="too many pages"):
        extract(make_pdf(["p"] * (module.MAX_PAGES + 1)))


def test_pdf_at_the_page_cap_is_read() -> None:
    assert extract(make_pdf(["p"] * module.MAX_PAGES))


def test_deadline_is_checked_between_pages() -> None:
    now = [0.0]

    def clock() -> float:
        now[0] += 10.0
        return now[0]

    slow = ResumeExtractor(clock=clock, deadline_seconds=25.0)
    with pytest.raises(ExtractionError, match="took too long"):
        slow.extract(make_pdf(["one", "two", "three", "four"]), PDF)


def test_oversized_input_fails_before_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "MAX_BYTES_IN", 10)
    with pytest.raises(ExtractionError, match="too large"):
        extract(b"x" * 11, "text/plain")


def test_text_over_the_character_cap_fails() -> None:
    assert module.MAX_TEXT_CHARS <= MAX_INPUT_CHARS
    with pytest.raises(ExtractionError, match="more text"):
        extract(("a" * (MAX_INPUT_CHARS + 1)).encode(), "text/plain")


@pytest.mark.parametrize(
    "build",
    [
        lambda: (b"%PDF-1.4 SECRETWORDS broken", PDF),
        lambda: (b"PK\x03\x04SECRETWORDS", DOCX),
        lambda: (b"\xff SECRETWORDS", "text/plain"),
        lambda: (make_docx(para("SECRETWORDS") + "<w:p>"), DOCX),
    ],
)
def test_error_messages_never_contain_file_text(build: Callable[[], tuple[bytes, str]]) -> None:
    data, media_type = build()
    with pytest.raises(ExtractionError) as info:
        extract(data, media_type)
    assert "SECRETWORDS" not in str(info.value)
