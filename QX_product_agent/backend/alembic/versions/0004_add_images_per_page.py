"""add images_per_page to projects and page_number to project_images

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column(
        'images_per_page', sa.Integer(),
        server_default='2', nullable=False
    ))
    op.add_column('project_images', sa.Column(
        'page_number', sa.Integer(),
        nullable=True
    ))
    op.create_index(
        'ix_project_images_page_number',
        'project_images', ['page_number']
    )


def downgrade() -> None:
    op.drop_index('ix_project_images_page_number', table_name='project_images')
    op.drop_column('project_images', 'page_number')
    op.drop_column('projects', 'images_per_page')
