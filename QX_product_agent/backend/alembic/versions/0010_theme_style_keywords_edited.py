"""studio template selection (theme_id/style_id) + keywords_edited flag

Revision ID: 0010
Revises: 0009
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, "studio_products")
    if "theme_id" not in cols:
        op.add_column("studio_products",
                      sa.Column("theme_id", sa.String(64), nullable=True))
    if "style_id" not in cols:
        op.add_column("studio_products",
                      sa.Column("style_id", sa.String(64), nullable=True))
    if "keywords_edited" not in cols:
        op.add_column("studio_products",
                      sa.Column("keywords_edited", sa.Boolean(), nullable=False,
                                server_default="0"))


def downgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, "studio_products")
    if "keywords_edited" in cols:
        op.drop_column("studio_products", "keywords_edited")
    if "style_id" in cols:
        op.drop_column("studio_products", "style_id")
    if "theme_id" in cols:
        op.drop_column("studio_products", "theme_id")
