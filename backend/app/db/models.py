"""SQLAlchemy models. Every module with models must be imported by alembic/env.py.

The schema is written in SQL (alembic/versions/0001_initial_schema.sql, from
docs/design/schema.sql). A model is added here only for a table the code reads or
writes, with its work item (the gateway adds `Budget` and `CallLog`, the Api adds `User` and
`UserSession`). Migrations for this schema are written by hand; autogenerate would propose
dropping every unmapped table.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Budget(Base):
    """The single running total of model spend (one row, id 1)."""

    __tablename__ = "budget"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    spent_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class CallLog(Base):
    """One row per gateway call, live or replayed."""

    __tablename__ = "call_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    # No ForeignKey: `roles` has no model yet; the database enforces the reference.
    role_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("reserved", "settled", "replayed", "released", name="call_status", create_type=False),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String, nullable=False)
    request_key: Mapped[str] = mapped_column(String, nullable=False)
    schema_retry: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class User(Base):
    """A seeded recruiter or interviewer who can sign in."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("recruiter", "interviewer", name="user_role", create_type=False), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserSession(Base):
    """A server-side session behind the cookie; keyed by the SHA-256 of the cookie value."""

    __tablename__ = "sessions"

    token_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    csrf_token: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Role(Base):
    """A job being hired for; `criteria_version` is bumped by every criteria write."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    title: Mapped[str] = mapped_column(String, nullable=False)
    job_description: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("draft", "approved", name="role_status", create_type=False),
        nullable=False,
        server_default="draft",
    )
    criteria_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Criterion(Base):
    """One scoring criterion of a role; retired rows stay so scores keep their target."""

    __tablename__ = "criteria"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(
        Enum("must_have", "nice_to_have", name="criterion_kind", create_type=False),
        nullable=False,
    )
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RubricLevel(Base):
    """The descriptor for one score level 0 to 4 of a criterion."""

    __tablename__ = "rubric_levels"

    criterion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("criteria.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    descriptor: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
