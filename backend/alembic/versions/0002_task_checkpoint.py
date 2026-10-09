"""Create the task checkpoint table for worker resume.

Revision ID: 0002_task_checkpoint
Revises: 0001_analysis_core
Create Date: 2026-10-08

0001 created the core tables via Base.metadata.create_all, so a brand-new
database still has them all. This revision only adds the new
ai_task_checkpoint table that did not exist when 0001 was first applied,
so deployed databases pick it up on the next ``alembic upgrade head``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_task_checkpoint"
down_revision: str | None = "0001_analysis_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_task_checkpoint",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("fence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["ai_analysis_task.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "stage", name="uq_checkpoint_task_stage"),
        sa.CheckConstraint(
            "stage IN ('collected', 'decided')", name="ck_checkpoint_stage"
        ),
        sa.CheckConstraint("fence >= 0", name="ck_checkpoint_fence"),
    )
    op.create_index(
        "ix_task_checkpoint_task_id", "ai_task_checkpoint", ["task_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_task_checkpoint_task_id", table_name="ai_task_checkpoint")
    op.drop_table("ai_task_checkpoint")
