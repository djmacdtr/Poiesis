"""认证服务：密码哈希、JWT 签发与验证。"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from poiesis.db.database import Database

# JWT 配置
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 24 * 7  # 7 天有效期


def _get_jwt_secret() -> str:
    """从环境变量读取 JWT 签名密钥（复用 POIESIS_SECRET_KEY）。"""
    key = os.environ.get("POIESIS_SECRET_KEY", "")
    if not key:
        # 开发/测试回退：使用固定密钥并打印警告
        import warnings
        warnings.warn(
            "POIESIS_SECRET_KEY 未设置，JWT 使用内置默认密钥。生产环境请务必配置！",
            stacklevel=3,
        )
        return "poiesis-dev-jwt-secret-key-00000"
    return key


def hash_password(plaintext: str) -> str:
    """使用 bcrypt 对密码进行哈希，返回 UTF-8 字符串。"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plaintext.encode(), salt).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    """验证明文密码与已存储的 bcrypt 哈希是否匹配。"""
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except (ValueError, UnicodeDecodeError):
        return False


def create_access_token(user_id: int, username: str, role: str) -> str:
    """签发 JWT access token。

    Args:
        user_id: 用户主键 id。
        username: 用户名。
        role: 角色（admin / user）。

    Returns:
        编码后的 JWT 字符串。
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=_JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """解码并验证 JWT token，返回 payload；无效时返回 None。

    Args:
        token: JWT 字符串。

    Returns:
        解码后的 payload dict，或 None（无效/过期）。
    """
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def authenticate_user(db: Database, username: str, password: str) -> dict[str, Any] | None:
    """验证用户名与密码，返回用户记录；失败返回 None。

    Args:
        db: 数据库实例。
        username: 用户名。
        password: 明文密码。

    Returns:
        用户记录 dict，或 None。
    """
    user = db.get_user_by_username(username)
    if user is None:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def change_password(db: Database, user_id: int, old_password: str, new_password: str) -> bool:
    """修改用户密码。

    Args:
        db: 数据库实例。
        user_id: 用户 id。
        old_password: 当前密码（明文）。
        new_password: 新密码（明文）。

    Returns:
        True 表示修改成功，False 表示旧密码不匹配。
    """
    with db._cursor() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
    if row is None:
        return False
    if not verify_password(old_password, row["password_hash"]):
        return False
    new_hash = hash_password(new_password)
    db.update_user_password(user_id, new_hash)
    return True


def ensure_admin_exists(db: Database) -> None:
    """若数据库中还没有 admin 用户，则从环境变量自动创建一次。

    读取环境变量：
        POIESIS_ADMIN_USER  管理员用户名（默认 admin）
        POIESIS_ADMIN_PASS  管理员密码（默认 admin，生产环境请务必修改）
    """
    if db.count_admins() > 0:
        return

    username = os.environ.get("POIESIS_ADMIN_USER", "admin")
    password = os.environ.get("POIESIS_ADMIN_PASS", "admin")

    if password == "admin":
        import warnings
        warnings.warn(
            "使用默认管理员密码 'admin'，生产环境请设置 POIESIS_ADMIN_PASS 环境变量！",
            stacklevel=2,
        )

    hashed = hash_password(password)
    db.create_user(username=username, password_hash=hashed, role="admin")
