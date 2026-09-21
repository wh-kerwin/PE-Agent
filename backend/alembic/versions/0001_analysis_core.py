"""Create analysis core tables.

Revision ID: 0001_analysis_core
Revises:
Create Date: 2026-09-20
"""

from collections.abc import Sequence

from alembic import op
from pe_agent.adapters.persistence.models import Base

revision: str = "0001_analysis_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
