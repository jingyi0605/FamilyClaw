from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def encrypt_plugin_config_secrets(secret_payload: dict[str, Any]) -> str | None:
    if not secret_payload:
        return None
    raw = json.dumps(secret_payload, ensure_ascii=False).encode("utf-8")
    return _build_fernet().encrypt(raw).decode("utf-8")


def decrypt_plugin_config_secrets(secret_payload_encrypted: str | None) -> dict[str, Any]:
    if not secret_payload_encrypted:
        return {}
    try:
        decrypted = _build_fernet().decrypt(secret_payload_encrypted.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("插件 secret 配置解密失败") from exc

    payload = json.loads(decrypted.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("插件 secret 配置解密后不是对象")
    return payload


def _build_fernet() -> Fernet:
    seed = settings.plugin_config_secret_seed.encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)
