"""studio_products: add keywords column (key word groups as part of the asset)

Revision ID: 0007
Revises: 0006
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # SQLite has no ALTER ... ADD COLUMN IF NOT EXISTS guard for TEXT cols
        pass
    columns = {c["name"] for c in sa.inspect(bind).get_columns("studio_products")}
    if "keywords" not in columns:
        op.add_column(
            "studio_products",
            sa.Column("keywords", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("studio_products")}
    if "keywords" in columns:
        op.drop_column("studio_products", "keywords")
