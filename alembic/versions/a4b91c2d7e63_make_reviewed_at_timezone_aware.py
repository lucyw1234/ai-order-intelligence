"""Make reviewed_at timezone-aware."""

from typing import Optional, Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a4b91c2d7e63"
down_revision: Optional[str] = "9c4e7a1d6b30"
branch_labels: Optional[Sequence[str]] = None
depends_on: Optional[Sequence[str]] = None


def upgrade() -> None:
    op.alter_column(
        "fuel_orders",
        "reviewed_at",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="reviewed_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "fuel_orders",
        "reviewed_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        existing_nullable=True,
        postgresql_using="reviewed_at AT TIME ZONE 'UTC'",
    )
