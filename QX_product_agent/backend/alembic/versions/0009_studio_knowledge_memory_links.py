"""link knowledge and memory records to studio_products

Revision ID: 0009
Revises: 0008
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    for table in ("knowledge_assets", "memory_entities", "memory_insights"):
        if "studio_product_id" not in _columns(bind, table):
            op.add_column(
                table,
                sa.Column(
                    "studio_product_id",
                    sa.UUID(),
                    nullable=True,
                ),
            )
            op.create_index(
                f"ix_{table}_studio_product_id",
                table,
                ["studio_product_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("memory_insights", "memory_entities", "knowledge_assets"):
        if "studio_product_id" in _columns(bind, table):
            op.drop_index(f"ix_{table}_studio_product_id", table_name=table)
            op.drop_column(table, "studio_product_id")
