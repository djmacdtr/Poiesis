"""Poiesis 加密工具模块。

使用 Fernet 对称加密保护敏感配置（如 API Key）。
加密密钥从环境变量 POIESIS_SECRET_KEY 读取；
若未设置，则自动生成并打印提示（仅用于开发/测试）。
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    """获取 Fernet 实例。

    优先使用环境变量 POIESIS_SECRET_KEY；若未设置，则使用确定性的默认密钥，
    并输出警告（生产环境请务必配置该变量）。
    """
    raw_key = os.environ.get("POIESIS_SECRET_KEY")
    if raw_key:
        # 支持两种格式：已编码的 Fernet key 或原始字节串
        try:
            key = raw_key.encode() if isinstance(raw_key, str) else raw_key
            return Fernet(key)
        except Exception:  # noqa: BLE001
            # 若不是合法 Fernet key，对其做 base64 填充处理
            padded = base64.urlsafe_b64encode(raw_key.encode()[:32].ljust(32, b"\x00"))
            return Fernet(padded)

    # 未配置密钥时使用固定默认密钥（仅开发/测试用途），并打印警告
    import warnings
    warnings.warn(
        "POIESIS_SECRET_KEY 未设置，使用内置默认密钥。生产环境请务必配置该环境变量！",
        stacklevel=3,
    )
    default_key = base64.urlsafe_b64encode(b"poiesis-default-secret-key-00000")
    return Fernet(default_key)


def encrypt(plaintext: str) -> str:
    """加密明文字符串，返回 base64 编码的密文。

    Args:
        plaintext: 待加密的字符串（如 API Key）。

    Returns:
        加密后的密文（UTF-8 字符串）。
    """
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """解密密文，返回原始明文字符串。

    Args:
        ciphertext: 加密后的密文字符串。

    Returns:
        解密后的明文。

    Raises:
        cryptography.fernet.InvalidToken: 若密文无效或密钥不匹配。
    """
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()
