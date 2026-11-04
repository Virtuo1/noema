"""Persist concise summaries for explicitly saved notes.

Revision ID: 0002_saved_note_summary
Revises: 0001_initial_schema
Create Date: 2026-11-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_saved_note_summary"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    evidence_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("evidence")
    }
    summary_columns = {
        "summary": sa.Text(),
        "summary_provider": sa.String(),
        "summary_model": sa.String(),
        "summary_prompt_version": sa.String(),
        "summary_generated_at": sa.String(),
    }
    for name, column_type in summary_columns.items():
        if name not in evidence_columns:
            op.add_column("evidence", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    evidence_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("evidence")
    }
    for name in (
        "summary_generated_at",
        "summary_prompt_version",
        "summary_model",
        "summary_provider",
        "summary",
    ):
        if name in evidence_columns:
            op.drop_column("evidence", name)
