"""Create the initial fuel_orders table."""

from typing import Optional, Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "9c4e7a1d6b30"
down_revision: Optional[str] = None
branch_labels: Optional[Sequence[str]] = None
depends_on: Optional[Sequence[str]] = None


def upgrade() -> None:
    op.create_table(
        "fuel_orders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("stated_total", sa.Float(), nullable=False),
        sa.Column("calculated_total", sa.Float(), nullable=True),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("review_status", sa.String(), nullable=False),
        sa.Column("reviewer", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("fuel_orders")
