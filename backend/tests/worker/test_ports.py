"""The text loaders are declared as ports; the anonymizer's real loader and the fakes fit them."""

from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.anonymizer import load_anonymized
from app.gateway.text import AnonymizedText, JobDescriptionText
from app.worker.ports import AnonymizedLoader, CriterionSpec, JobDescriptionLoader
from tests.worker.fakes import FakeAnonymizedLoader, FakeJobDescriptionLoader

# mypy proves the real loader satisfies the port: this assignment fails the gate otherwise.
REAL_LOADER: AnonymizedLoader = load_anonymized


async def test_the_anonymized_loader_port_returns_an_anonymized_text() -> None:
    candidate = uuid4()
    loader: AnonymizedLoader = FakeAnonymizedLoader({candidate: "[NAME] built payments."})
    loaded = await loader(AsyncSession(), candidate)
    assert isinstance(loaded, AnonymizedText)
    assert loaded.value == "[NAME] built payments."


async def test_the_job_description_loader_port_adds_the_criterion_for_a_kit() -> None:
    role = uuid4()
    loader: JobDescriptionLoader = FakeJobDescriptionLoader({role: "Build APIs."})
    criterion = CriterionSpec(uuid4(), "Python", "must_have", Decimal(3), 1, ())
    plain = await loader(AsyncSession(), role)
    kit = await loader(AsyncSession(), role, criterion)
    assert isinstance(plain, JobDescriptionText)
    assert plain.value == "Build APIs."
    assert "Python" in kit.value
