from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


FRAME_TYPE_CONTROL = 0
FRAME_TYPE_DATA = 1

MESSAGE_TYPE_EVENT = "event"
MESSAGE_TYPE_PING = "ping"
MESSAGE_TYPE_PONG = "pong"

HEADER_TYPE = "type"
HEADER_MESSAGE_ID = "message_id"
HEADER_SUM = "sum"
HEADER_SEQ = "seq"
HEADER_BIZ_RT = "biz_rt"


@dataclass(slots=True)
class FeishuWsHeader:
    key: str
    value: str


@dataclass(slots=True)
class FeishuWsFrame:
    seq_id: int
    log_id: int
    service_id: int
    method: int
    headers: list[FeishuWsHeader] = field(default_factory=list)
    payload_encoding: str | None = None
    payload_type: str | None = None
    payload: bytes = b""
    log_id_new: str | None = None


@dataclass(slots=True)
class FeishuWsClientConfig:
    reconnect_count: int = -1
    reconnect_interval: int = 120
    reconnect_nonce: int = 30
    ping_interval: int = 120


def get_header_value(headers: list[FeishuWsHeader], key: str) -> str | None:
    for header in headers:
        if header.key == key:
            return header.value
    return None


def build_ping_frame(service_id: int) -> FeishuWsFrame:
    return FeishuWsFrame(
        seq_id=0,
        log_id=0,
        service_id=service_id,
        method=FRAME_TYPE_CONTROL,
        headers=[FeishuWsHeader(key=HEADER_TYPE, value=MESSAGE_TYPE_PING)],
    )


def build_ack_frame(
    request_frame: FeishuWsFrame,
    *,
    code: int,
    biz_rt_ms: int | None = None,
) -> FeishuWsFrame:
    response_headers = [FeishuWsHeader(key=item.key, value=item.value) for item in request_frame.headers]
    if biz_rt_ms is not None:
        response_headers.append(FeishuWsHeader(key=HEADER_BIZ_RT, value=str(max(biz_rt_ms, 0))))

    payload_json = json.dumps({"code": int(code)}, ensure_ascii=False, separators=(",", ":"))
    return FeishuWsFrame(
        seq_id=request_frame.seq_id,
        log_id=request_frame.log_id,
        service_id=request_frame.service_id,
        method=request_frame.method,
        headers=response_headers,
        payload_encoding=request_frame.payload_encoding,
        payload_type=request_frame.payload_type,
        payload=payload_json.encode("utf-8"),
        log_id_new=request_frame.log_id_new,
    )


def parse_client_config(payload: bytes) -> FeishuWsClientConfig | None:
    if not payload:
        return None
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return FeishuWsClientConfig(
        reconnect_count=_coerce_int(data.get("ReconnectCount"), -1),
        reconnect_interval=max(_coerce_int(data.get("ReconnectInterval"), 120), 1),
        reconnect_nonce=max(_coerce_int(data.get("ReconnectNonce"), 30), 0),
        ping_interval=max(_coerce_int(data.get("PingInterval"), 120), 1),
    )


def decode_frame(data: bytes) -> FeishuWsFrame:
    offset = 0
    frame = FeishuWsFrame(seq_id=0, log_id=0, service_id=0, method=0)
    while offset < len(data):
        tag, offset = _decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if field_number == 1 and wire_type == 0:
            frame.seq_id, offset = _decode_varint(data, offset)
            continue
        if field_number == 2 and wire_type == 0:
            frame.log_id, offset = _decode_varint(data, offset)
            continue
        if field_number == 3 and wire_type == 0:
            frame.service_id, offset = _decode_varint(data, offset)
            continue
        if field_number == 4 and wire_type == 0:
            frame.method, offset = _decode_varint(data, offset)
            continue
        if field_number == 5 and wire_type == 2:
            raw_header, offset = _decode_length_delimited(data, offset)
            frame.headers.append(_decode_header(raw_header))
            continue
        if field_number == 6 and wire_type == 2:
            raw_value, offset = _decode_length_delimited(data, offset)
            frame.payload_encoding = raw_value.decode("utf-8")
            continue
        if field_number == 7 and wire_type == 2:
            raw_value, offset = _decode_length_delimited(data, offset)
            frame.payload_type = raw_value.decode("utf-8")
            continue
        if field_number == 8 and wire_type == 2:
            frame.payload, offset = _decode_length_delimited(data, offset)
            continue
        if field_number == 9 and wire_type == 2:
            raw_value, offset = _decode_length_delimited(data, offset)
            frame.log_id_new = raw_value.decode("utf-8")
            continue

        offset = _skip_field(data, offset, wire_type)
    return frame


def encode_frame(frame: FeishuWsFrame) -> bytes:
    parts: list[bytes] = []
    parts.append(_encode_key(1, 0) + _encode_varint(frame.seq_id))
    parts.append(_encode_key(2, 0) + _encode_varint(frame.log_id))
    parts.append(_encode_key(3, 0) + _encode_varint(frame.service_id))
    parts.append(_encode_key(4, 0) + _encode_varint(frame.method))

    for header in frame.headers:
        encoded_header = _encode_header(header)
        parts.append(_encode_key(5, 2) + _encode_varint(len(encoded_header)) + encoded_header)
    if frame.payload_encoding:
        encoded = frame.payload_encoding.encode("utf-8")
        parts.append(_encode_key(6, 2) + _encode_varint(len(encoded)) + encoded)
    if frame.payload_type:
        encoded = frame.payload_type.encode("utf-8")
        parts.append(_encode_key(7, 2) + _encode_varint(len(encoded)) + encoded)
    if frame.payload:
        parts.append(_encode_key(8, 2) + _encode_varint(len(frame.payload)) + frame.payload)
    if frame.log_id_new:
        encoded = frame.log_id_new.encode("utf-8")
        parts.append(_encode_key(9, 2) + _encode_varint(len(encoded)) + encoded)
    return b"".join(parts)


def _decode_header(data: bytes) -> FeishuWsHeader:
    offset = 0
    key = ""
    value = ""
    while offset < len(data):
        tag, offset = _decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07
        if field_number == 1 and wire_type == 2:
            raw_value, offset = _decode_length_delimited(data, offset)
            key = raw_value.decode("utf-8")
            continue
        if field_number == 2 and wire_type == 2:
            raw_value, offset = _decode_length_delimited(data, offset)
            value = raw_value.decode("utf-8")
            continue
        offset = _skip_field(data, offset, wire_type)
    return FeishuWsHeader(key=key, value=value)


def _encode_header(header: FeishuWsHeader) -> bytes:
    key_bytes = header.key.encode("utf-8")
    value_bytes = header.value.encode("utf-8")
    return b"".join(
        [
            _encode_key(1, 2),
            _encode_varint(len(key_bytes)),
            key_bytes,
            _encode_key(2, 2),
            _encode_varint(len(value_bytes)),
            value_bytes,
        ]
    )


def _encode_key(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("protobuf varint cannot encode negative values in current feishu runtime")
    chunks = bytearray()
    while value > 0x7F:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    chunks.append(value & 0x7F)
    return bytes(chunks)


def _decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise ValueError("protobuf varint is truncated")
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            return result, offset
        shift += 7
        if shift > 63:
            raise ValueError("protobuf varint is too large")


def _decode_length_delimited(data: bytes, offset: int) -> tuple[bytes, int]:
    size, offset = _decode_varint(data, offset)
    end = offset + size
    if end > len(data):
        raise ValueError("protobuf field is truncated")
    return data[offset:end], end


def _skip_field(data: bytes, offset: int, wire_type: int) -> int:
    if wire_type == 0:
        _, offset = _decode_varint(data, offset)
        return offset
    if wire_type == 1:
        end = offset + 8
        if end > len(data):
            raise ValueError("protobuf fixed64 field is truncated")
        return end
    if wire_type == 2:
        _, end = _decode_length_delimited(data, offset)
        return end
    if wire_type == 5:
        end = offset + 4
        if end > len(data):
            raise ValueError("protobuf fixed32 field is truncated")
        return end
    raise ValueError(f"protobuf wire type is not supported: {wire_type}")


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default
