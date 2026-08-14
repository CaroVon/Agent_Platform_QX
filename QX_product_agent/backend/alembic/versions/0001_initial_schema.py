"""Alembic 迁移脚本 v0001 —— 初始表结构"""
# type: ignore

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建初始表结构"""
    # users 表
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("monthly_project_limit", sa.Integer(), server_default="10", nullable=False),
        sa.Column("projects_used_this_month", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_pages_generated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # projects 表
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("topic", sa.String(500), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PREPARING_DATA", "WAITING_OUTLINE_APPROVAL",
                "DRAFTING", "COMPLETED", "FAILED",
                name="project_status",
            ),
            server_default="PREPARING_DATA",
            nullable=False,
        ),
        sa.Column("outline_content", sa.Text(), nullable=True, comment="暂存大纲 Markdown（等待用户确认）"),
        sa.Column("pdf_path", sa.String(1000), nullable=True),
        sa.Column("md_path", sa.String(1000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_id"), "projects", ["id"], unique=False)
    op.create_index(op.f("ix_projects_owner_id"), "projects", ["owner_id"], unique=False)

    # tasks 表
    op.create_table(
        "tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column(
            "task_type",
            sa.Enum(
                "SEARCH", "BUILD_KNOWLEDGE_BASE", "GENERATE_OUTLINE",
                "WRITE_SECTION", "GENERATE_IMAGE", "BUILD_REPORT", "GENERATE_PDF",
                name="task_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "PROCESSING", "COMPLETED", "FAILED", "RETRYING", "CANCELLED",
                name="task_status",
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("sequence_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("section_title", sa.String(500), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_retries", sa.Integer(), server_default="3", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_id"), "tasks", ["id"], unique=False)
    op.create_index(op.f("ix_tasks_project_id"), "tasks", ["project_id"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)

    # documents 表
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("section_title", sa.String(500), nullable=False),
        sa.Column("section_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("source_urls", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_id"), "documents", ["id"], unique=False)
    op.create_index(op.f("ix_documents_project_id"), "documents", ["project_id"], unique=False)

    # document_blocks 表（面向 Tiptap 块级编辑器的细粒度存储）
    op.create_table(
        "document_blocks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("section_title", sa.String(500), nullable=False, comment="归属的章节标题"),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False, comment="全局排序序号"),
        sa.Column("content", sa.Text(), nullable=False, comment="块内容（Markdown 格式）"),
        sa.Column("citations", sa.Text(), nullable=True, comment="引用映射（JSON 格式）"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_blocks_id"), "document_blocks", ["id"], unique=False)
    op.create_index(op.f("ix_document_blocks_project_id"), "document_blocks", ["project_id"], unique=False)

    # ─── 插入默认管理员用户（UUID 全零的演示用户） ──────────
    op.execute(
        """
        INSERT INTO users (id, email, username, hashed_password, is_active, is_superuser)
        VALUES (
            '00000000-0000-0000-0000-000000000001',
            'admin@research-agent.local',
            'admin',
            '$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qn7qLqF7qF7qLqF7qLqF7qLqF7q',
            true,
            true
        )
        ON CONFLICT (id) DO NOTHING;
        """
    )


def downgrade() -> None:
    """回滚所有表"""
    op.drop_table("document_blocks")
    op.drop_table("documents")
    op.drop_table("tasks")
    op.drop_table("projects")
    op.drop_table("users")

    # 删除自定义枚举类型
    op.execute("DROP TYPE IF EXISTS project_status")
    op.execute("DROP TYPE IF EXISTS task_type")
    op.execute("DROP TYPE IF EXISTS task_status")
