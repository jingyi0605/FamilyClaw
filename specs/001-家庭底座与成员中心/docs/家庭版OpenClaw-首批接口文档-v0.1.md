> 说明：本文件里出现的 SQLite 描述属于历史方案或阶段性验收记录。项目已于 2026-03-16 统一切换到 PostgreSQL，当前实现与测试基线都以 PostgreSQL 为准。

# 瀹跺涵鐗?OpenClaw 棣栨壒鎺ュ彛鏂囨。 v0.1

## 1. 鏂囨。鑼冨洿

鏈枃妗ｈ鐩?`瀹跺涵搴曞骇涓庢垚鍛樹腑蹇僠 褰撳墠宸蹭氦浠樼殑棣栨壒鎺ュ彛锛岃寖鍥村寘鎷細

- 鍋ュ悍妫€鏌?
- 瀹跺涵绠＄悊
- 鎴愬憳绠＄悊
- 鎴愬憳鍏崇郴绠＄悊
- 鎴愬憳鍋忓ソ涓庢潈闄?
- 鎴块棿涓庤澶囩鐞?
- Home Assistant 璁惧鍚屾
- 瀹¤鏃ュ織鏌ヨ

褰撳墠鏈嶅姟鍩虹鍓嶇紑涓猴細

- 鏍瑰湴鍧€锛歚http://127.0.0.1:8000`
- API 鍓嶇紑锛歚/api/v1`

---

## 2. 閫氱敤绾﹀畾

### 2.1 Header

褰撳墠瀹炵幇寤鸿鎵€鏈夎姹傞兘鎼哄甫浠ヤ笅 Header锛?

```http
Content-Type: application/json
X-Actor-Role: admin
X-Actor-Id: local-dev
```

璇存槑锛?

- `X-Actor-Role=admin`锛氬啓鎺ュ彛蹇呴』鎼哄甫锛屽惁鍒欎細杩斿洖 `403 admin role required`
- `X-Actor-Id`锛氬綋鍓嶅彲閫夛紝渚夸簬瀹¤璁板綍杩借釜

### 2.2 鍒嗛〉鍙傛暟

鏀寔鍒楄〃鏌ヨ鐨勬帴鍙ｇ粺涓€浣跨敤锛?

- `page`锛氶〉鐮侊紝浠?`1` 寮€濮嬶紝榛樿 `1`
- `page_size`锛氭瘡椤垫暟閲忥紝榛樿 `20`锛屾渶澶?`100`

缁熶竴杩斿洖缁撴瀯锛?

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

### 2.3 閿欒鐮?

褰撳墠闃舵甯歌閿欒锛?

- `400`锛氬弬鏁版牎楠屽け璐ユ垨涓氬姟绾︽潫涓嶆弧瓒?
- `403`锛氭湭浣跨敤绠＄悊鍛樿韩浠借皟鐢ㄥ啓鎺ュ彛
- `404`锛氱洰鏍囪祫婧愪笉瀛樺湪
- `409`锛氭暟鎹簱鍞竴绾︽潫绛夊畬鏁存€у啿绐?
- `502`锛氳皟鐢?Home Assistant 澶辫触

---

## 3. 鍋ュ悍妫€鏌?

### `GET /api/v1/healthz`

鐢ㄩ€旓細

- 妫€鏌?API 鏈嶅姟涓?SQLite 杩炴帴鐘舵€?

鍝嶅簲绀轰緥锛?

```json
{
  "status": "ok",
  "service": "api-server",
  "database": "ok"
}
```

### `GET /`

鐢ㄩ€旓細

- 杩斿洖鏈嶅姟鍚嶇О銆佺増鏈笌鐘舵€?

鍝嶅簲绀轰緥锛?

```json
{
  "name": "FamilyClaw API Server",
  "version": "0.1.0",
  "status": "ok"
}
```

---

## 4. 瀹跺涵绠＄悊

### `POST /api/v1/households`

鐢ㄩ€旓細

- 鍒涘缓瀹跺涵

璇锋眰浣擄細

```json
{
  "name": "Jackson 瀹跺涵",
  "timezone": "Asia/Shanghai",
  "locale": "zh-CN"
}
```

鍝嶅簲瀛楁锛?

- `id`
- `name`
- `timezone`
- `locale`
- `status`
- `created_at`
- `updated_at`

### `GET /api/v1/households`

鐢ㄩ€旓細

- 鏌ヨ瀹跺涵鍒楄〃

鏌ヨ鍙傛暟锛?

- `status`锛氬彲閫夛紝鎸夌姸鎬佺瓫閫?
- `page`
- `page_size`

### `GET /api/v1/households/{household_id}`

鐢ㄩ€旓細

- 鏌ヨ鍗曚釜瀹跺涵璇︽儏

---

## 5. 鎴愬憳绠＄悊

### `POST /api/v1/members`

鐢ㄩ€旓細

- 鍒涘缓鎴愬憳

璇锋眰浣擄細

```json
{
  "household_id": "household-id",
  "name": "Coco",
  "nickname": "鍙彲",
  "role": "child",
  "age_group": "child",
  "birthday": "2018-05-01",
  "phone": "13800000000",
  "guardian_member_id": "guardian-member-id"
}
```

瀛楁绾︽潫锛?

- `role`锛歚admin | adult | child | elder | guest`
- `age_group`锛歚toddler | child | teen | adult | elder`
- `status` 鐢辩郴缁熷垵濮嬪寲涓?`active`

### `GET /api/v1/members`

鐢ㄩ€旓細

- 鏌ヨ瀹跺涵鎴愬憳鍒楄〃

鏌ヨ鍙傛暟锛?

- `household_id`锛氬繀濉?
- `status`锛氬彲閫夛紝`active | inactive`
- `page`
- `page_size`

### `PATCH /api/v1/members/{member_id}`

鐢ㄩ€旓細

- 缂栬緫鎴愬憳璧勬枡
- 鏀寔鍋滅敤鎴愬憳

鍙洿鏂板瓧娈碉細

- `name`
- `nickname`
- `role`
- `age_group`
- `birthday`
- `phone`
- `status`
- `guardian_member_id`

鍋滅敤绀轰緥锛?

```json
{
  "status": "inactive"
}
```

---

## 6. 鎴愬憳鍏崇郴绠＄悊

### `POST /api/v1/member-relationships`

鐢ㄩ€旓細

- 鍒涘缓瀹跺涵鍐呴儴鎴愬憳鍏崇郴

璇锋眰浣擄細

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

鏋氫妇鍊硷細

- `relation_type`锛歚spouse | parent | child | guardian | caregiver`
- `visibility_scope`锛歚public | family | private`
- `delegation_scope`锛歚none | reminder | health | device`

绾︽潫璇存槑锛?

- `source_member_id` 涓?`target_member_id` 涓嶈兘鐩稿悓
- 鍙屾柟蹇呴』灞炰簬鍚屼竴涓搴?
- `source_member_id + target_member_id + relation_type` 缁勫悎鍞竴

### `GET /api/v1/member-relationships`

鐢ㄩ€旓細

- 鏌ヨ瀹跺涵鍏崇郴鍒楄〃

鏌ヨ鍙傛暟锛?

- `household_id`锛氬繀濉?
- `source_member_id`锛氬彲閫?
- `target_member_id`锛氬彲閫?
- `relation_type`锛氬彲閫?
- `page`
- `page_size`

---

## 7. 鎴愬憳鍋忓ソ涓庢潈闄?

### `PUT /api/v1/member-preferences/{member_id}`

鐢ㄩ€旓細

- 鏂板鎴栨洿鏂版垚鍛樺亸濂?

璇锋眰浣撶ず渚嬶細

```json
{
  "preferred_name": "鐖哥埜",
  "light_preference": {
    "brightness": 70,
    "tone": "warm"
  },
  "climate_preference": {
    "temperature": 25,
    "mode": "cool"
  },
  "content_preference": {
    "topics": ["绉戞妧", "浜插瓙"]
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

鐢ㄩ€旓細

- 鏌ヨ鎴愬憳鍋忓ソ

璇存槑锛?

- 褰撴垚鍛樺瓨鍦ㄤ絾鍋忓ソ灏氭湭鍒涘缓鏃讹紝杩斿洖瀛楁涓虹┖鐨勯粯璁ゅ亸濂藉璞★紝涓嶅啀杩斿洖 `404`

### `PUT /api/v1/member-permissions/{member_id}`

鐢ㄩ€旓細

- 鏁存壒瑕嗙洊鎴愬憳鏉冮檺瑙勫垯

璇锋眰浣撶ず渚嬶細

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

鏋氫妇鍊硷細

- `resource_type`锛歚memory | health | device | photo | scenario`
- `resource_scope`锛歚self | children | family | public`
- `action`锛歚read | write | execute | manage`
- `effect`锛歚allow | deny`

### `GET /api/v1/member-permissions/{member_id}`

鐢ㄩ€旓細

- 鏌ヨ鎴愬憳鏉冮檺瑙勫垯鍒楄〃

鍝嶅簲绀轰緥锛?

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

## 8. 鎴块棿涓庤澶?

### `POST /api/v1/rooms`

鐢ㄩ€旓細

- 鍒涘缓鎴块棿

璇锋眰浣擄細

```json
{
  "household_id": "household-id",
  "name": "涓诲崸",
  "room_type": "bedroom",
  "privacy_level": "private"
}
```

鏋氫妇鍊硷細

- `room_type`锛歚living_room | bedroom | study | entrance`
- `privacy_level`锛歚public | private | sensitive`

### `GET /api/v1/rooms`

鐢ㄩ€旓細

- 鏌ヨ鎴块棿鍒楄〃

鏌ヨ鍙傛暟锛?

- `household_id`锛氬繀濉?
- `page`
- `page_size`

### `GET /api/v1/devices`

鐢ㄩ€旓細

- 鏌ヨ璁惧鍒楄〃

鏌ヨ鍙傛暟锛?

- `household_id`锛氬繀濉?
- `room_id`锛氬彲閫?
- `device_type`锛氬彲閫?
- `status`锛氬彲閫?
- `page`
- `page_size`

### `PATCH /api/v1/devices/{device_id}`

鐢ㄩ€旓細

- 鏇存柊璁惧鍚嶇О銆佺姸鎬併€佸彲鎺ф€с€佹墍灞炴埧闂?

璇锋眰浣撶ず渚嬶細

```json
{
  "room_id": "room-id"
}
```

---

## 9. Home Assistant 鍚屾

### `POST /api/v1/devices/sync/ha`

鐢ㄩ€旓細

- 鎵嬪姩瑙﹀彂 Home Assistant 璁惧鍚屾

璇锋眰浣擄細

```json
{
  "household_id": "household-id"
}
```

鍝嶅簲瀛楁锛?

- `household_id`
- `created_devices`
- `updated_devices`
- `created_bindings`
- `skipped_entities`
- `failed_entities`
- `devices`
- `failures`

澶辫触绀轰緥锛?

- 褰?HA 鍦板潃涓嶅彲杈炬垨 token 鏃犳晥鏃讹紝杩斿洖 `502`

---

## 10. 瀹¤鏃ュ織

### `GET /api/v1/audit-logs`

鐢ㄩ€旓細

- 鏌ヨ瀹跺涵缁村害鐨勫璁℃棩蹇?

鏌ヨ鍙傛暟锛?

- `household_id`锛氬繀濉?
- `action`锛氬彲閫?
- `page`
- `page_size`

褰撳墠宸叉帴鍏ュ璁＄殑鍏抽敭鍔ㄤ綔鍖呮嫭锛?

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

## 11. curl 绀轰緥

### 11.1 鍒涘缓瀹跺涵

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/households" \
  -H "Content-Type: application/json" \
  -H "X-Actor-Role: admin" \
  -d '{
    "name": "Jackson 瀹跺涵",
    "timezone": "Asia/Shanghai",
    "locale": "zh-CN"
  }'
```

### 11.2 鏌ヨ鎴愬憳

```bash
curl "http://127.0.0.1:8000/api/v1/members?household_id=YOUR_HOUSEHOLD_ID" \
  -H "X-Actor-Role: admin"
```

### 11.3 鍚屾 HA 璁惧

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/devices/sync/ha" \
  -H "Content-Type: application/json" \
  -H "X-Actor-Role: admin" \
  -d '{
    "household_id": "YOUR_HOUSEHOLD_ID"
  }'
```

### 11.4 鏌ヨ瀹¤鏃ュ織

```bash
curl "http://127.0.0.1:8000/api/v1/audit-logs?household_id=YOUR_HOUSEHOLD_ID" \
  -H "X-Actor-Role: admin"
```

