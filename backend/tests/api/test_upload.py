"""POST /v1/roles/{id}/resumes against fake repositories (HK-58)."""

import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.types import Message, Scope

from app.api.resumes.form import read_form
from app.core.errors import TooManyFilesError, ValidationFailedError
from app.db.models import Role
from app.domain.candidates.service import clean_file_name
from tests.api.fakes import FakeRoles, FakeSessions, FakeUploads, FakeUsers
from tests.files import DOCX_TYPE, PDF_TYPE, docx_bytes, pdf_bytes, zip_bytes

type Part = tuple[str, tuple[str, bytes, str]]


@pytest.fixture
async def recruiter(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (
        await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    ).unsafe_headers


@pytest.fixture
def role(roles: FakeRoles) -> Role:
    return roles.seed(status="approved", version=3)


def part(name: str, data: bytes, content_type: str = "application/octet-stream") -> Part:
    return ("files", (name, data, content_type))


async def upload(
    client: AsyncClient, role_id: uuid.UUID, headers: dict[str, str], parts: list[Part]
) -> Response:
    return await client.post(f"/v1/roles/{role_id}/resumes", files=parts, headers=headers)


def error_of(response: Response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


async def test_accepts_pdf_and_docx_with_one_result_per_file(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    parts = [part("a.pdf", pdf_bytes("1")), part("b.docx", docx_bytes("2"))]

    response = await upload(client, role.id, recruiter, parts)

    assert response.status_code == 207
    assert response.headers["cache-control"] == "no-store"
    results = response.json()["results"]
    assert [(r["file_name"], r["status"], r["candidate_no"]) for r in results] == [
        ("a.pdf", "accepted", 1),
        ("b.docx", "accepted", 2),
    ]
    assert [f[1] for f in uploads.files] == [PDF_TYPE, DOCX_TYPE]
    assert [j[2] for j in uploads.jobs] == [3, 3]


@pytest.mark.parametrize(
    "data",
    [b"just some text", b"MZ\x90\x00 an exe", pdf_bytes()[1:], zip_bytes("xl/workbook.xml")],
)
async def test_rejects_other_types_naming_pdf_and_docx(
    client: AsyncClient,
    uploads: FakeUploads,
    role: Role,
    recruiter: dict[str, str],
    data: bytes,
) -> None:
    response = await upload(client, role.id, recruiter, [part("cv.pdf", data, PDF_TYPE)])

    result = response.json()["results"][0]
    assert response.status_code == 207
    assert result["status"] == "rejected"
    assert result["candidate_id"] is None
    assert "PDF" in result["reason"]
    assert "DOCX" in result["reason"]
    assert uploads.candidates == []


async def test_empty_file_is_rejected_on_its_own_and_the_others_are_kept(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    parts = [part("empty.pdf", b""), part("ok.pdf", pdf_bytes())]

    results = (await upload(client, role.id, recruiter, parts)).json()["results"]

    assert [r["status"] for r in results] == ["rejected", "accepted"]
    assert "empty" in results[0]["reason"].lower()


async def test_the_type_comes_from_the_bytes_not_the_name_or_content_type(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    parts = [part("resume.txt", pdf_bytes(), "text/plain"), part("x.pdf", b"text", PDF_TYPE)]

    results = (await upload(client, role.id, recruiter, parts)).json()["results"]

    assert [r["status"] for r in results] == ["accepted", "rejected"]
    assert uploads.files[0][1] == PDF_TYPE


async def test_a_file_over_the_size_limit_is_rejected_and_one_at_the_limit_is_kept(
    client: AsyncClient,
    app: FastAPI,
    uploads: FakeUploads,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    limit = app.state.settings.max_upload_bytes
    at_limit = pdf_bytes() + b"x" * (limit - len(pdf_bytes()))
    parts = [part("big.pdf", at_limit + b"x"), part("fits.pdf", at_limit)]

    results = (await upload(client, role.id, recruiter, parts)).json()["results"]

    assert [r["status"] for r in results] == ["rejected", "accepted"]
    assert "too large" in results[0]["reason"].lower()
    assert len(uploads.files[0][2]) == limit


async def test_a_duplicate_is_accepted_and_flagged(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    parts = [part("a.pdf", pdf_bytes("same")), part("copy.pdf", pdf_bytes("same"))]

    results = (await upload(client, role.id, recruiter, parts)).json()["results"]

    assert [(r["status"], r["duplicate_of_candidate_no"]) for r in results] == [
        ("accepted", None),
        ("accepted", 1),
    ]
    assert len(uploads.jobs) == 2


async def test_100_files_are_accepted_and_101_are_refused_as_a_whole(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    hundred = [part(f"{n}.pdf", pdf_bytes(str(n))) for n in range(100)]

    ok = await upload(client, role.id, recruiter, hundred)
    stored = len(uploads.candidates)
    over = await upload(client, role.id, recruiter, [*hundred, part("101.pdf", pdf_bytes("x"))])

    assert ok.status_code == 207
    assert len(ok.json()["results"]) == 100
    assert error_of(over) == (422, "too_many_files")
    assert len(uploads.candidates) == stored == 100


async def test_a_102nd_file_is_refused_the_same_way(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    parts = [part(f"{n}.pdf", pdf_bytes(str(n))) for n in range(102)]

    response = await upload(client, role.id, recruiter, parts)

    assert error_of(response) == (422, "too_many_files")
    assert uploads.candidates == []


async def test_no_files_part_is_a_validation_error(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    response = await client.post(
        f"/v1/roles/{role.id}/resumes", data={"other": "x"}, headers=recruiter
    )

    assert error_of(response) == (422, "validation_error")


async def test_a_files_field_that_is_not_a_file_is_a_validation_error(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    response = await client.post(
        f"/v1/roles/{role.id}/resumes",
        data={"files": "plain text"},
        files=[("other", ("o.txt", b"x", "text/plain"))],
        headers=recruiter,
    )

    assert error_of(response) == (422, "validation_error")


async def test_a_draft_role_refuses_the_whole_upload_and_writes_nothing(
    client: AsyncClient, uploads: FakeUploads, roles: FakeRoles, recruiter: dict[str, str]
) -> None:
    draft = roles.seed(status="draft")

    response = await upload(client, draft.id, recruiter, [part("a.pdf", pdf_bytes())])

    assert error_of(response) == (409, "role_not_approved")
    assert (uploads.candidates, uploads.files, uploads.jobs) == ([], [], [])


async def test_a_role_that_turns_draft_between_files_gives_per_file_results(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    uploads.draft_after = 1
    parts = [part(f"{n}.pdf", pdf_bytes(str(n))) for n in range(3)]

    response = await upload(client, role.id, recruiter, parts)

    assert response.status_code == 207
    assert [r["status"] for r in response.json()["results"]] == [
        "accepted",
        "role_not_approved",
        "role_not_approved",
    ]
    assert len(uploads.candidates) == 1


async def test_unknown_role_is_404(
    client: AsyncClient, uploads: FakeUploads, recruiter: dict[str, str]
) -> None:
    response = await upload(client, uuid.uuid4(), recruiter, [part("a.pdf", pdf_bytes())])

    assert error_of(response) == (404, "not_found")


async def test_at_the_budget_cap_in_live_mode_the_upload_is_refused(
    client: AsyncClient,
    app: FastAPI,
    uploads: FakeUploads,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"model_mode": "live"})
    uploads.spent = Decimal("7.99")

    response = await upload(client, role.id, recruiter, [part("a.pdf", pdf_bytes())])

    assert error_of(response) == (409, "budget_reached")
    assert response.json()["error"]["message"] == (
        "The model budget of $8.00 has been reached. No new model calls can be made."
    )
    assert uploads.candidates == []


async def test_in_replay_mode_the_budget_never_blocks(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    uploads.spent = Decimal(8)

    response = await upload(client, role.id, recruiter, [part("a.pdf", pdf_bytes())])

    assert response.status_code == 207


async def test_the_file_name_loses_its_path_and_control_characters(
    client: AsyncClient, uploads: FakeUploads, role: Role, recruiter: dict[str, str]
) -> None:
    parts = [
        part("C:\\Users\\jo\\cv.pdf", pdf_bytes("1")),
        part("../../etc/joe.pdf", pdf_bytes("2")),
        part("a/", pdf_bytes("3")),
        part("n" * 300 + ".pdf", pdf_bytes("4")),
    ]

    results = (await upload(client, role.id, recruiter, parts)).json()["results"]

    names = [r["file_name"] for r in results]
    assert names[:3] == ["cv.pdf", "joe.pdf", "resume"]
    assert len(names[3]) == 255
    assert [c["file_name"] for c in uploads.candidates] == names


async def test_an_interviewer_is_refused(
    client: AsyncClient,
    uploads: FakeUploads,
    role: Role,
    users: FakeUsers,
    sessions: FakeSessions,
) -> None:
    headers = (
        await sessions.sign_in(users.add(email="i@example.com", role="interviewer"))
    ).unsafe_headers

    response = await upload(client, role.id, headers, [part("a.pdf", pdf_bytes())])

    assert error_of(response) == (403, "forbidden")


# The body is never read when the caller is refused or the declared size is over the cap -----------


class Spy:
    """An ASGI receive that counts calls, for a request whose body must not be read."""

    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = list(chunks)
        self.calls = 0

    async def __call__(self) -> Message:
        self.calls += 1
        if self.chunks:
            chunk = self.chunks.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(self.chunks)}
        return {"type": "http.request", "body": b"", "more_body": False}


def scope_for(method: str, path: str, headers: dict[str, str]) -> Scope:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("test", 1),
        "server": ("test", 80),
        "state": {},
    }


async def raw_post(
    app: FastAPI, path: str, headers: dict[str, str], chunks: list[bytes]
) -> tuple[int, Spy]:
    spy = Spy(chunks)
    status = 0

    async def send(message: Message) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = int(message["status"])

    await app(scope_for("POST", path, headers), spy, send)
    return status, spy


BOUNDARY = {"content-type": "multipart/form-data; boundary=x"}


async def test_an_anonymous_upload_is_refused_before_the_body_is_read(
    app: FastAPI, uploads: FakeUploads, sessions: FakeSessions, role: Role
) -> None:
    status, spy = await raw_post(app, f"/v1/roles/{role.id}/resumes", BOUNDARY, [b"--x--"])

    assert (status, spy.calls) == (401, 0)


async def test_an_upload_without_the_csrf_token_is_refused_before_the_body_is_read(
    app: FastAPI,
    uploads: FakeUploads,
    users: FakeUsers,
    sessions: FakeSessions,
    role: Role,
) -> None:
    signed = await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))

    status, spy = await raw_post(
        app, f"/v1/roles/{role.id}/resumes", {**BOUNDARY, **signed.cookie}, [b"--x--"]
    )

    assert (status, spy.calls) == (403, 0)


async def test_a_declared_length_over_the_cap_is_413_before_the_body_is_read(
    app: FastAPI,
    uploads: FakeUploads,
    users: FakeUsers,
    sessions: FakeSessions,
    role: Role,
) -> None:
    signed = await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    over = app.state.settings.max_request_bytes + 1
    headers = {**BOUNDARY, **signed.unsafe_headers, "content-length": str(over)}

    status, spy = await raw_post(app, f"/v1/roles/{role.id}/resumes", headers, [b"--x--"])

    assert (status, spy.calls) == (413, 0)


async def test_a_chunked_body_over_the_cap_is_413(
    app: FastAPI,
    uploads: FakeUploads,
    users: FakeUsers,
    sessions: FakeSessions,
    role: Role,
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"max_request_bytes": 1000})
    signed = await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    headers = {**BOUNDARY, **signed.unsafe_headers}  # no content-length: a chunked client

    head = b'--x\r\nContent-Disposition: form-data; name="files"; filename="a.pdf"\r\n\r\n'

    status, _ = await raw_post(
        app, f"/v1/roles/{role.id}/resumes", headers, [head + b"x" * 600, b"x" * 600]
    )

    assert status == 413


async def test_a_json_route_over_the_cap_is_413_too(
    app: FastAPI, users: FakeUsers, sessions: FakeSessions, roles: FakeRoles
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"max_request_bytes": 1000})
    signed = await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    headers = {"content-type": "application/json", **signed.unsafe_headers}

    status, _ = await raw_post(app, "/v1/roles", headers, [b'{"title": "' + b"x" * 2000])

    assert status == 413


# The one place that matches a Starlette message ---------------------------------------------------


def multipart_request(files: int) -> Request:
    part_head = 'Content-Disposition: form-data; name="files"; filename="{n}.pdf"'
    body = (
        b"".join(f"--b\r\n{part_head.format(n=n)}\r\n\r\nx\r\n".encode() for n in range(files))
        + b"--b--\r\n"
    )
    scope: Scope = {
        "type": "http",
        "app": True,  # Starlette raises its 400 only inside an application
        "method": "POST",
        "headers": [(b"content-type", b"multipart/form-data; boundary=b")],
    }
    return Request(scope, Spy([body]))


async def test_read_form_maps_starlettes_too_many_files_message() -> None:
    """Fails if Starlette rewords its 400, which would turn a 102nd file into a plain 422."""
    with pytest.raises(TooManyFilesError):
        await read_form(multipart_request(102))


async def test_read_form_returns_the_files_up_to_the_limit() -> None:
    form = await read_form(multipart_request(101))

    files = form.getlist("files")
    await form.close()
    assert len(files) == 101
    assert all(isinstance(f, UploadFile) for f in files)


async def test_read_form_maps_a_broken_multipart_body_to_a_validation_error() -> None:
    scope: Scope = {
        "type": "http",
        "app": True,  # Starlette raises its 400 only inside an application
        "method": "POST",
        "headers": [(b"content-type", b"multipart/form-data; boundary=b")],
    }

    with pytest.raises(ValidationFailedError):
        await read_form(Request(scope, Spy([b"--b\r\nContent-Disposition: nope\r\n\r\nx"])))


def test_clean_file_name_drops_control_characters_and_nul() -> None:
    assert clean_file_name("jo\x00e\x1b\x7f.pdf") == "joe.pdf"
