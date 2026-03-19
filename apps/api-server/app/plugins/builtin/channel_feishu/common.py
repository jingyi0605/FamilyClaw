from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


FEISHU_OPEN_BASE_URL = "https://open.feishu.cn"
LARK_OPEN_BASE_URL = "https://open.larksuite.com"


def load_account_config(raw_config: Any) -> dict[str, Any]:
    """把账号配置统一解析成 dict，避免各个入口各写一套散装判断。"""
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str) and raw_config.strip():
        try:
            parsed = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            raise ValueError("feishu account config is not valid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    return {}


def first_text(mapping: Any, *keys: str) -> str | None:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def first_int(mapping: Any, *keys: str, default: int) -> int:
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return int(value.strip())
            except ValueError:
                continue
    return default


def resolve_open_base_url(config: dict[str, Any]) -> str:
    """兼容 manifest 里的 base_url 和旧逻辑里的 domain。"""
    domain = first_text(config, "base_url", "baseUrl", "domain")
    if not domain or domain == "feishu":
        return FEISHU_OPEN_BASE_URL
    if domain == "lark":
        return LARK_OPEN_BASE_URL
    if domain.startswith("https://"):
        normalized = domain.rstrip("/")
        if normalized.endswith("/open-apis"):
            normalized = normalized.removesuffix("/open-apis")
        return normalized
    raise ValueError("feishu domain is invalid")


def load_callback_body(raw_request: Any, *, encrypt_key: str | None) -> dict[str, Any]:
    if not isinstance(raw_request, dict):
        raise ValueError("feishu webhook request is missing")
    body_text = raw_request.get("body_text")
    if not isinstance(body_text, str) or not body_text.strip():
        raise ValueError("feishu webhook body is missing")
    return decode_callback_payload(body_text, encrypt_key=encrypt_key)


def decode_callback_payload(raw_payload: Any, *, encrypt_key: str | None) -> dict[str, Any]:
    """统一处理 webhook 和长连接收到的 JSON 负载。"""
    if isinstance(raw_payload, dict):
        payload = raw_payload
    elif isinstance(raw_payload, bytes):
        payload = _load_json_object(raw_payload.decode("utf-8"))
    elif isinstance(raw_payload, str) and raw_payload.strip():
        payload = _load_json_object(raw_payload)
    else:
        raise ValueError("feishu callback payload is missing")

    encrypted = first_text(payload, "encrypt")
    if encrypted is None:
        return payload
    if not encrypt_key:
        raise ValueError("feishu encrypt callback requires encrypt_key")
    return decrypt_encrypted_payload(encrypted, encrypt_key)


def _load_json_object(raw_json: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError("feishu callback payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("feishu callback payload must be a JSON object")
    return payload


def decrypt_encrypted_payload(encrypted_text: str, encrypt_key: str) -> dict[str, Any]:
    encrypted_bytes = _decode_base64(encrypted_text)
    candidate_keys = _build_candidate_keys(encrypt_key)
    for key_bytes in candidate_keys:
        try:
            plaintext = _decrypt_with_key(encrypted_bytes, key_bytes)
            payload = _parse_decrypted_payload(plaintext)
        except ValueError:
            continue
        if payload is not None:
            return payload
    raise ValueError("feishu encrypt payload cannot be decrypted with current encrypt_key")


def _build_candidate_keys(encrypt_key: str) -> list[bytes]:
    normalized = encrypt_key.strip()
    candidates: list[bytes] = []
    raw_bytes = normalized.encode("utf-8")
    if len(raw_bytes) in {16, 24, 32}:
        candidates.append(raw_bytes)
    candidates.append(hashlib.sha256(raw_bytes).digest())
    try:
        decoded = _decode_base64(normalized)
    except ValueError:
        decoded = None
    if decoded is not None and len(decoded) in {16, 24, 32}:
        candidates.append(decoded)

    unique_candidates: list[bytes] = []
    seen: set[bytes] = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        unique_candidates.append(item)
    return unique_candidates


def _decrypt_with_key(ciphertext: bytes, key_bytes: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(key_bytes[:16]))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as exc:
        raise ValueError("feishu decrypt padding is invalid") from exc


def _parse_decrypted_payload(plaintext: bytes) -> dict[str, Any] | None:
    try:
        decoded = plaintext.decode("utf-8")
    except UnicodeDecodeError:
        decoded = plaintext.decode("utf-8", errors="ignore")
    candidates = [decoded]
    start = decoded.find("{")
    end = decoded.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidates.append(decoded[start : end + 1])

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _decode_base64(value: str) -> bytes:
    normalized = value.strip()
    padded = normalized + "=" * (-len(normalized) % 4)
    try:
        return base64.b64decode(padded)
    except Exception as exc:
        raise ValueError("feishu encrypted payload is not valid base64") from exc
