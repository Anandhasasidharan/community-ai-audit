"""Initial migration — create audit_jobs table.

Revision ID: 001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), default="pending"),
        sa.Column("model_id", sa.String()),
        sa.Column("provider", sa.String()),
        sa.Column("scanners", sa.Text()),
        sa.Column("results", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("risk_score", sa.Float()),
        sa.Column("severity", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_jobs")
