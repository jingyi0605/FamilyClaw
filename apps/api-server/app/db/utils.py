from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_uuid() -> str:
    return str(uuid4())


def dump_json(value: Any | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def load_json(value: str | None) -> Any | None:
    if value is None:
        return None
    return json.loads(value)
