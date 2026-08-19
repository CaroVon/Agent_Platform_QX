"""memory graph: entities/relations/insights tables

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


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "memory_entities"):
        op.create_table(
            "memory_entities",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("scope", sa.String(length=20), nullable=False, server_default="project"),
            sa.Column("project_id", sa.UUID(), nullable=True),
            sa.Column("type", sa.String(length=50), nullable=False, server_default="other"),
            sa.Column("name", sa.String(length=500), nullable=False),
            sa.Column("aliases", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("embedding", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.6"),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_memory_entities_scope", "memory_entities", ["scope"])
        op.create_index("ix_memory_entities_project_id", "memory_entities", ["project_id"])
        op.create_index("ix_memory_entities_name", "memory_entities", ["name"])
        op.create_index("ix_memory_entities_last_seen_at", "memory_entities", ["last_seen_at"])

    if not _has_table(bind, "memory_relations"):
        op.create_table(
            "memory_relations",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("source_entity_id", sa.UUID(), nullable=False),
            sa.Column("target_entity_id", sa.UUID(), nullable=False),
            sa.Column("relation_type", sa.String(length=100), nullable=False),
            sa.Column("evidence", sa.Text(), nullable=True),
            sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_memory_relations_source_entity_id", "memory_relations", ["source_entity_id"])
        op.create_index("ix_memory_relations_target_entity_id", "memory_relations", ["target_entity_id"])

    if not _has_table(bind, "memory_insights"):
        op.create_table(
            "memory_insights",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("scope", sa.String(length=20), nullable=False, server_default="project"),
            sa.Column("project_id", sa.UUID(), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("entity_ids", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=50), nullable=False, server_default="task_summary"),
            sa.Column("source_url", sa.String(length=2048), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_memory_insights_scope", "memory_insights", ["scope"])
        op.create_index("ix_memory_insights_project_id", "memory_insights", ["project_id"])


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("memory_insights", "memory_relations", "memory_entities"):
        if _has_table(bind, table):
            op.drop_table(table)
