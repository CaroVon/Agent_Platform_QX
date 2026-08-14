"""add search_depth and logo_url to projects

Revision ID: 0003
Revises: 24f2c9f525d7
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '24f2c9f525d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column(
        'search_depth', sa.Integer(), server_default='10', nullable=False,
        doc="搜索强度: 5/10/15/20"
    ))
    op.add_column('projects', sa.Column(
        'logo_url', sa.String(500), nullable=True,
        doc="Logo 图片 URL"
    ))


def downgrade() -> None:
    op.drop_column('projects', 'logo_url')
    op.drop_column('projects', 'search_depth')
