"""studio_products: add keywords column (key word groups as part of the asset)

Revision ID: 0008
Revises: 0007
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
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
