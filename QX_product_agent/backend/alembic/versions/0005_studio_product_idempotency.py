"""add idempotency fields to studio products

Revision ID: 0005
Revises: 0004
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("studio_products"):
        # The table is currently also created by application startup.  A later
        # create_all will include these nullable columns when no table exists.
        return

    columns = {column["name"] for column in inspector.get_columns("studio_products")}
    if "idempotency_key" not in columns:
        op.add_column(
            "studio_products",
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        )
    if "idea_hash" not in columns:
        op.add_column(
            "studio_products",
            sa.Column("idea_hash", sa.String(length=64), nullable=True),
        )

    indexes = {index["name"] for index in inspector.get_indexes("studio_products")}
    if "ix_studio_products_idempotency_key" not in indexes:
        op.create_index(
            "ix_studio_products_idempotency_key",
            "studio_products",
            ["idempotency_key"],
            unique=True,
        )
    if "ix_studio_products_idea_hash" not in indexes:
        op.create_index(
            "ix_studio_products_idea_hash",
            "studio_products",
            ["idea_hash"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("studio_products"):
        return
    op.drop_index("ix_studio_products_idea_hash", table_name="studio_products")
    op.drop_index("ix_studio_products_idempotency_key", table_name="studio_products")
    op.drop_column("studio_products", "idea_hash")
    op.drop_column("studio_products", "idempotency_key")
