# 20260315-ImmichConnector输入输出草案

这份文档是 `design.md` 里 `ImmichConnector` 契约的便于联调版本。

正式边界只有一句话：

- 插件只负责动作
- `photo` 模块负责定义

## 1. 输入草案

```json
{
  "provider_account_id": "photo-provider-001",
  "sync_mode": "incremental",
  "scope": {
    "scope_type": "album",
    "scope_ref": "album_123"
  },
  "cursor": "2026-03-15T08:00:00Z",
  "page_size": 200,
  "include_people": true,
  "include_albums": true,
  "force": false,
  "request_id": "photo-sync-req-001"
}
```

## 2. 输出草案

```json
{
  "records": [
    {
      "record_type": "photo_asset",
      "provider_type": "immich",
      "provider_asset_id": "asset_001",
      "captured_at": "2026-03-15T06:30:00Z",
      "mime_type": "image/jpeg",
      "width": 4032,
      "height": 3024,
      "checksum": "sha256:xxxx",
      "album_refs": ["album_123"],
      "people": [
        {
          "provider_group_ref": "person_001",
          "provider_face_ref": "face_001",
          "confidence": 0.98,
          "bbox": {"left": 0.1, "top": 0.2, "width": 0.3, "height": 0.4}
        }
      ],
      "metadata": {
        "location_text": "Shanghai",
        "timezone": "Asia/Shanghai"
      }
    }
  ],
  "sync_summary": {
    "fetched": 120,
    "created": 30,
    "updated": 80,
    "skipped": 8,
    "failed": 2
  },
  "next_cursor": "2026-03-15T09:00:00Z",
  "warnings": [],
  "errors": []
}
```

## 3. 明确不返回什么

下面这些字段不允许由插件直接返回为最终业务结论：

- `member_id`
- `memory_card_id`
- `story_id`
- `timeline_id`
- `final_privacy_level`

原因很简单：这些都是本地 `photo` 模块的定义，不是插件动作层的输出。
