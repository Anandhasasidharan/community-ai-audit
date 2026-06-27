"""Add organizations, users, api_keys, projects, webhooks, schedules tables.

Revision ID: 002
Revises: 001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), sa.ForeignKey("organizations.id")),
        sa.Column("email", sa.String(), unique=True),
        sa.Column("password_hash", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("key", sa.String(), unique=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id")),
        sa.Column("name", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), sa.ForeignKey("organizations.id")),
        sa.Column("name", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "webhooks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id")),
        sa.Column("url", sa.String()),
        sa.Column("events", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "schedules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id")),
        sa.Column("cron_expr", sa.String()),
        sa.Column("model_id", sa.String()),
        sa.Column("next_run", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("audit_jobs", sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_jobs", "project_id")
    op.drop_table("schedules")
    op.drop_table("webhooks")
    op.drop_table("projects")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("organizations")
