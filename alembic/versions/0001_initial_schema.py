"""Initial Noema relational schema and FTS5 virtual table.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-11-04 14:55:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

import noema.persistence.models  # noqa: F401
from noema.persistence.db import Base

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(text("PRAGMA foreign_keys = ON;"))
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "sqlite":
        bind.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS search_documents_fts USING fts5(
                    document_id UNINDEXED,
                    owner_user_id UNINDEXED,
                    kind UNINDEXED,
                    text,
                    tokenize = 'unicode61'
                );
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(text("DROP TABLE IF EXISTS search_documents_fts;"))
    Base.metadata.drop_all(bind=bind)
