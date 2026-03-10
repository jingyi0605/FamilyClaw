# 家庭版 OpenClaw 首批接口文档 v0.1

## 1. 文档范围

本文档覆盖 `家庭底座与成员中心` 当前已交付的首批接口，范围包括：

- 健康检查
- 家庭管理
- 成员管理
- 成员关系管理
- 成员偏好与权限
- 房间与设备管理
- Home Assistant 设备同步
- 审计日志查询

当前服务基础前缀为：

- 根地址：`http://127.0.0.1:8000`
- API 前缀：`/api/v1`

---

## 2. 通用约定

### 2.1 Header

当前实现建议所有请求都携带以下 Header：

```http
Content-Type: application/json
X-Actor-Role: admin
X-Actor-Id: local-dev
```

说明：

- `X-Actor-Role=admin`：写接口必须携带，否则会返回 `403 admin role required`
- `X-Actor-Id`：当前可选，便于审计记录追踪

### 2.2 分页参数

支持列表查询的接口统一使用：

- `page`：页码，从 `1` 开始，默认 `1`
- `page_size`：每页数量，默认 `20`，最大 `100`

统一返回结构：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

### 2.3 错误码

当前阶段常见错误：

- `400`：参数校验失败或业务约束不满足
- `403`：未使用管理员身份调用写接口
- `404`：目标资源不存在
- `409`：数据库唯一约束等完整性冲突
- `502`：调用 Home Assistant 失败

---

## 3. 健康检查

### `GET /api/v1/healthz`

用途：

- 检查 API 服务与 SQLite 连接状态

响应示例：

```json
{
  "status": "ok",
  "service": "api-server",
  "database": "ok"
}
```

### `GET /`

用途：

- 返回服务名称、版本与状态

响应示例：

```json
{
  "name": "FamilyClaw API Server",
  "version": "0.1.0",
  "status": "ok"
}
```

---

## 4. 家庭管理

### `POST /api/v1/households`

用途：

- 创建家庭

请求体：

```json
{
  "name": "Jackson 家庭",
  "timezone": "Asia/Shanghai",
  "locale": "zh-CN"
}
```

响应字段：

- `id`
- `name`
- `timezone`
- `locale`
- `status`
- `created_at`
- `updated_at`

### `GET /api/v1/households`

用途：

- 查询家庭列表

查询参数：

- `status`：可选，按状态筛选
- `page`
- `page_size`

### `GET /api/v1/households/{household_id}`

用途：

- 查询单个家庭详情

---

## 5. 成员管理

### `POST /api/v1/members`

用途：

- 创建成员

请求体：

```json
{
  "household_id": "household-id",
  "name": "Coco",
  "nickname": "可可",
  "role": "child",
  "age_group": "child",
  "birthday": "2018-05-01",
  "phone": "13800000000",
  "guardian_member_id": "guardian-member-id"
}
```

字段约束：

- `role`：`admin | adult | child | elder | guest`
- `age_group`：`toddler | child | teen | adult | elder`
- `status` 由系统初始化为 `active`

### `GET /api/v1/members`

用途：

- 查询家庭成员列表

查询参数：

- `household_id`：必填
- `status`：可选，`active | inactive`
- `page`
- `page_size`

### `PATCH /api/v1/members/{member_id}`

用途：

- 编辑成员资料
- 支持停用成员

可更新字段：

- `name`
- `nickname`
- `role`
- `age_group`
- `birthday`
- `phone`
- `status`
- `guardian_member_id`

停用示例：

```json
{
  "status": "inactive"
}
```

---

## 6. 成员关系管理

### `POST /api/v1/member-relationships`

用途：

- 创建家庭内部成员关系

请求体：

```json
{
  "household_id": "household-id",
  "source_member_id": "member-a",
  "target_member_id": "member-b",
  "relation_type": "guardian",
  "visibility_scope": "family",
  "delegation_scope": "device"
}
```

枚举值：

- `relation_type`：`spouse | parent | child | guardian | caregiver`
- `visibility_scope`：`public | family | private`
- `delegation_scope`：`none | reminder | health | device`

约束说明：

- `source_member_id` 与 `target_member_id` 不能相同
- 双方必须属于同一个家庭
- `source_member_id + target_member_id + relation_type` 组合唯一

### `GET /api/v1/member-relationships`

用途：

- 查询家庭关系列表

查询参数：

- `household_id`：必填
- `source_member_id`：可选
- `target_member_id`：可选
- `relation_type`：可选
- `page`
- `page_size`

---

## 7. 成员偏好与权限

### `PUT /api/v1/member-preferences/{member_id}`

用途：

- 新增或更新成员偏好

请求体示例：

```json
{
  "preferred_name": "爸爸",
  "light_preference": {
    "brightness": 70,
    "tone": "warm"
  },
  "climate_preference": {
    "temperature": 25,
    "mode": "cool"
  },
  "content_preference": {
    "topics": ["科技", "亲子"]
  },
  "reminder_channel_preference": {
    "channels": ["app", "speaker"]
  },
  "sleep_schedule": {
    "weekday_sleep": "23:00",
    "weekday_wake": "07:00"
  }
}
```

### `GET /api/v1/member-preferences/{member_id}`

用途：

- 查询成员偏好

说明：

- 当成员存在但偏好尚未创建时，返回字段为空的默认偏好对象，不再返回 `404`

### `PUT /api/v1/member-permissions/{member_id}`

用途：

- 整批覆盖成员权限规则

请求体示例：

```json
{
  "rules": [
    {
      "resource_type": "device",
      "resource_scope": "family",
      "action": "manage",
      "effect": "allow"
    },
    {
      "resource_type": "photo",
      "resource_scope": "family",
      "action": "read",
      "effect": "deny"
    }
  ]
}
```

枚举值：

- `resource_type`：`memory | health | device | photo | scenario`
- `resource_scope`：`self | children | family | public`
- `action`：`read | write | execute | manage`
- `effect`：`allow | deny`

### `GET /api/v1/member-permissions/{member_id}`

用途：

- 查询成员权限规则列表

响应示例：

```json
{
  "member_id": "member-id",
  "household_id": "household-id",
  "items": [
    {
      "id": "permission-id",
      "household_id": "household-id",
      "member_id": "member-id",
      "resource_type": "device",
      "resource_scope": "family",
      "action": "manage",
      "effect": "allow",
      "created_at": "2026-03-09T10:00:00+00:00"
    }
  ]
}
```

---

## 8. 房间与设备

### `POST /api/v1/rooms`

用途：

- 创建房间

请求体：

```json
{
  "household_id": "household-id",
  "name": "主卧",
  "room_type": "bedroom",
  "privacy_level": "private"
}
```

枚举值：

- `room_type`：`living_room | bedroom | study | entrance`
- `privacy_level`：`public | private | sensitive`

### `GET /api/v1/rooms`

用途：

- 查询房间列表

查询参数：

- `household_id`：必填
- `page`
- `page_size`

### `GET /api/v1/devices`

用途：

- 查询设备列表

查询参数：

- `household_id`：必填
- `room_id`：可选
- `device_type`：可选
- `status`：可选
- `page`
- `page_size`

### `PATCH /api/v1/devices/{device_id}`

用途：

- 更新设备名称、状态、可控性、所属房间

请求体示例：

```json
{
  "room_id": "room-id"
}
```

---

## 9. Home Assistant 同步

### `POST /api/v1/devices/sync/ha`

用途：

- 手动触发 Home Assistant 设备同步

请求体：

```json
{
  "household_id": "household-id"
}
```

响应字段：

- `household_id`
- `created_devices`
- `updated_devices`
- `created_bindings`
- `skipped_entities`
- `failed_entities`
- `devices`
- `failures`

失败示例：

- 当 HA 地址不可达或 token 无效时，返回 `502`

---

## 10. 审计日志

### `GET /api/v1/audit-logs`

用途：

- 查询家庭维度的审计日志

查询参数：

- `household_id`：必填
- `action`：可选
- `page`
- `page_size`

当前已接入审计的关键动作包括：

- `household.create`
- `member.create`
- `member.update`
- `member_relationship.create`
- `member_preference.upsert`
- `member_permission.replace`
- `room.create`
- `device.update`
- `device.sync.home_assistant`
- `seed.mock_data`

---

## 11. curl 示例

### 11.1 创建家庭

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/households" \
  -H "Content-Type: application/json" \
  -H "X-Actor-Role: admin" \
  -d '{
    "name": "Jackson 家庭",
    "timezone": "Asia/Shanghai",
    "locale": "zh-CN"
  }'
```

### 11.2 查询成员

```bash
curl "http://127.0.0.1:8000/api/v1/members?household_id=YOUR_HOUSEHOLD_ID" \
  -H "X-Actor-Role: admin"
```

### 11.3 同步 HA 设备

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/devices/sync/ha" \
  -H "Content-Type: application/json" \
  -H "X-Actor-Role: admin" \
  -d '{
    "household_id": "YOUR_HOUSEHOLD_ID"
  }'
```

### 11.4 查询审计日志

```bash
curl "http://127.0.0.1:8000/api/v1/audit-logs?household_id=YOUR_HOUSEHOLD_ID" \
  -H "X-Actor-Role: admin"
```
