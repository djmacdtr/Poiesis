"""认证路由：登录、登出、当前用户信息。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from poiesis.api import deps
from poiesis.api.services import auth_service
from poiesis.db.database import Database

router = APIRouter(prefix="/api/auth", tags=["认证"])

# Cookie 名称
_COOKIE_NAME = "poiesis_token"


class LoginRequest(BaseModel):
    """登录请求体。"""

    username: str
    password: str


class UserInfo(BaseModel):
    """当前登录用户信息（不含密码）。"""

    id: int
    username: str
    role: str


@router.post("/login")
def login(
    body: LoginRequest,
    response: Response,
    db: Database = Depends(deps.get_db),
) -> UserInfo:
    """用户登录：验证凭据，写入 HttpOnly Cookie 并返回用户信息。"""
    user = auth_service.authenticate_user(db, body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = auth_service.create_access_token(
        user_id=user["id"],
        username=user["username"],
        role=user["role"],
    )
    # HttpOnly Cookie，防止 JS 读取，SameSite=Lax 兼容性较好
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 3600,  # 7 天
        path="/",
    )
    return UserInfo(id=user["id"], username=user["username"], role=user["role"])


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    """退出登录：清除 Cookie。"""
    response.delete_cookie(key=_COOKIE_NAME, path="/")
    return {"message": "已退出登录"}


@router.get("/me", response_model=UserInfo)
def get_me(
    current_user: dict[str, Any] = Depends(deps.get_current_user),
) -> UserInfo:
    """获取当前登录用户信息。"""
    return UserInfo(
        id=int(current_user["sub"]),
        username=current_user["username"],
        role=current_user["role"],
    )
