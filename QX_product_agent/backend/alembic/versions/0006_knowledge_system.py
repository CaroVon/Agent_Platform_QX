"""knowledge system: three-tier KB schema (assets/experiences/image analysis/project profile)

Revision ID: 0006
Revises: 0005
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ─── 1. projects: topic_embedding / domain_tags ─────────────
    if _has_table(bind, "projects"):
        if not _has_column(bind, "projects", "topic_embedding"):
            op.add_column(
                "projects",
                sa.Column("topic_embedding", sa.Text(), nullable=True),
            )
        if not _has_column(bind, "projects", "domain_tags"):
            op.add_column(
                "projects",
                sa.Column("domain_tags", sa.Text(), nullable=True),
            )

    # ─── 2. project_images: 知识库图片分析字段 ──────────────────
    if _has_table(bind, "project_images"):
        for col, coltype in (
            ("source", sa.String(length=20)),
            ("status", sa.String(length=20)),
            ("analysis_text", sa.Text()),
            ("tags", sa.String(length=1000)),
            ("file_path", sa.String(length=1000)),
        ):
            if not _has_column(bind, "project_images", col):
                op.add_column("project_images", sa.Column(col, coltype, nullable=True))
        # source 已有默认值约束由 ORM 层负责；迁移层面仅加列

    # ─── 3. knowledge_assets（全局/领域知识资产登记表） ─────────
    if not _has_table(bind, "knowledge_assets"):
        op.create_table(
            "knowledge_assets",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("scope", sa.String(length=100), nullable=False),
            sa.Column("owner_id", sa.UUID(), nullable=True),
            sa.Column("source", sa.String(length=50), nullable=False, server_default="upload"),
            sa.Column("title", sa.String(length=1000), nullable=False),
            sa.Column("source_url", sa.String(length=2048), nullable=True),
            sa.Column("tags", sa.String(length=1000), nullable=True),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("extra", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_knowledge_assets_scope", "knowledge_assets", ["scope"])
        op.create_index("ix_knowledge_assets_owner_id", "knowledge_assets", ["owner_id"])
        op.create_index("ix_knowledge_assets_stale_at", "knowledge_assets", ["stale_at"])

    # ─── 4. domain_experiences（领域经验包） ────────────────────
    if not _has_table(bind, "domain_experiences"):
        op.create_table(
            "domain_experiences",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("project_id", sa.UUID(), nullable=False),
            sa.Column("domain_tags", sa.String(length=1000), nullable=False, server_default="[]"),
            sa.Column("topic", sa.String(length=500), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("source_url", sa.String(length=2048), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_domain_experiences_project_id", "domain_experiences", ["project_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "domain_experiences"):
        op.drop_table("domain_experiences")
    if _has_table(bind, "knowledge_assets"):
        op.drop_table("knowledge_assets")
    if _has_table(bind, "project_images"):
        for col in ("file_path", "tags", "analysis_text", "status", "source"):
            if _has_column(bind, "project_images", col):
                op.drop_column("project_images", col)
    if _has_table(bind, "projects"):
        for col in ("domain_tags", "topic_embedding"):
            if _has_column(bind, "projects", col):
                op.drop_column("projects", col)
