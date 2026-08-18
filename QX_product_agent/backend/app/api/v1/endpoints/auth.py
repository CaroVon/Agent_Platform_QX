"""
============================================================
认证端点 —— /api/v1/auth/*
  POST   /auth/login      用户名 + 密码 → token
  POST   /auth/bootstrap  本地开发免密签发（AUTH_BOOTSTRAP=true 时）
  GET    /auth/me         当前用户信息（需认证）
============================================================
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import create_token, get_current_user
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserInfo(BaseModel):
    username: str
    auth_enabled: bool


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """用户名 + 密码登录，签发访问令牌。"""
    settings = get_settings()
    if not settings.AUTH_ENABLED:
        username = settings.AUTH_ADMIN_USERNAME
    else:
        if body.username != settings.AUTH_ADMIN_USERNAME:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if body.password != settings.AUTH_ADMIN_PASSWORD:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        username = body.username
    return TokenResponse(
        access_token=create_token(username),
        username=username,
    )


@router.post("/bootstrap", response_model=TokenResponse)
async def bootstrap():
    """本地开发便利：免密签发管理员 token。

    仅当 AUTH_BOOTSTRAP=true 时可用；生产环境必须置 false。
    """
    settings = get_settings()
    if not settings.AUTH_BOOTSTRAP:
        raise HTTPException(status_code=404, detail="bootstrap 未启用")
    return TokenResponse(
        access_token=create_token(settings.AUTH_ADMIN_USERNAME),
        username=settings.AUTH_ADMIN_USERNAME,
    )


@router.get("/me", response_model=UserInfo)
async def me(current_user: User = Depends(get_current_user)):
    """返回当前登录用户信息（用于前端 401 检测）。"""
    return UserInfo(
        username=current_user.username,
        auth_enabled=get_settings().AUTH_ENABLED,
    )
