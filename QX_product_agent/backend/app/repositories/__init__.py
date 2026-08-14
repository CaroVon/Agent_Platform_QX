"""
Repository Layer —— Celery Worker 专用的同步数据库访问层。

解决的问题：
1. 消除所有 raw SQL (text("SELECT ...")) 调用——使用 ORM 查询保证类型安全
2. 消除所有 asyncio.run() 调用——使用同步 SQLAlchemy 引擎，无需事件循环
3. 提供统一的错误处理和日志记录，所有 DB 操作集中在一处

使用方式（在 Celery 任务中）：
    from app.repositories import ProjectRepo
    repo = ProjectRepo()
    project = repo.get_project("uuid-here")
    repo.update_task_status("uuid-here", TaskType.WRITE_SECTION, TaskStatus.COMPLETED)
"""

from app.repositories.project_repo import ProjectRepo

__all__ = ["ProjectRepo"]
