> 说明：本文件里出现的 SQLite 描述属于历史方案或阶段性验收记录。项目已于 2026-03-16 统一切换到 PostgreSQL，当前实现与测试基线都以 PostgreSQL 为准。

# Spec 001 - 璁捐鏂规

## 姒傝堪

鏈?Spec 閲囩敤**妯″潡鍖栧崟浣?*璁捐锛屽厛鍦ㄤ竴涓?`api-server` 鍐呭畬鎴愪互涓嬫ā鍧楋細

1. `household`
2. `member`
3. `relationship`
4. `permission`
5. `room`
6. `device`
7. `ha_integration`
8. `audit`

鍚屾椂淇濈暀鍚庣画鎷嗗垎绌洪棿銆?

鏁版嵁搴撳疄鐜扮害鏉燂細

- 棣栨湡鎸佷箙鍖栫粺涓€閲囩敤 `SQLite`
- 鎵€鏈変富閿互 `TEXT` 褰㈠紡瀛樺偍 UUID
- 鏃堕棿瀛楁浠?`TEXT` 褰㈠紡瀛樺偍 `ISO8601 UTC`
- JSON 缁撴瀯瀛楁浠?`TEXT` 褰㈠紡瀛樺偍 JSON 瀛楃涓?

---

## 涓€銆佹ā鍧楄璁?

## 1. `household`

鑱岃矗锛?

- 鍒涘缓瀹跺涵
- 鏌ヨ瀹跺涵璇︽儏
- 鏇存柊瀹跺涵鍩虹璁剧疆

鏁版嵁琛細

- `households`

鏍稿績鎺ュ彛锛?

- `POST /api/v1/households`
- `GET /api/v1/households/{id}`

## 2. `member`

鑱岃矗锛?

- 鎴愬憳澧炲垹鏀规煡
- 鎴愬憳鐘舵€佺淮鎶?
- 绠＄悊鍛樺綍鍏ュ搴垚鍛?

鏁版嵁琛細

- `members`
- `member_preferences`

鏍稿績鎺ュ彛锛?

- `POST /api/v1/members`
- `GET /api/v1/members`
- `PATCH /api/v1/members/{id}`

## 3. `relationship`

鑱岃矗锛?

- 瀹跺涵鎴愬憳鍏崇郴绠＄悊

鏁版嵁琛細

- `member_relationships`

鏍稿績鎺ュ彛锛?

- `POST /api/v1/member-relationships`
- `GET /api/v1/member-relationships`

## 4. `permission`

鑱岃矗锛?

- 鎴愬憳鏉冮檺璇诲啓
- 璧勬簮璁块棶鍐崇瓥鍩虹

鏁版嵁琛細

- `member_permissions`

鏍稿績鎺ュ彛锛?

- `PUT /api/v1/member-permissions/{member_id}`
- `GET /api/v1/member-permissions/{member_id}`

## 5. `room`

鑱岃矗锛?

- 鎴块棿绠＄悊

鏁版嵁琛細

- `rooms`

鏍稿績鎺ュ彛锛?

- `POST /api/v1/rooms`
- `GET /api/v1/rooms`

## 6. `device`

鑱岃矗锛?

- 鏈湴璁惧涓绘暟鎹鐞?
- 鎴块棿涓庤澶囩粦瀹?

鏁版嵁琛細

- `devices`
- `device_bindings`

鏍稿績鎺ュ彛锛?

- `GET /api/v1/devices`
- `PATCH /api/v1/devices/{id}`

## 7. `ha_integration`

鑱岃矗锛?

- 浠?HA 鎷夊彇瀹炰綋
- 褰掍竴鍖栬澶囦俊鎭?
- 鍐欏叆鏈湴璁惧琛?

渚濊禆锛?

- `Home Assistant REST API`

鏍稿績鎺ュ彛锛?

- `POST /api/v1/devices/sync/ha`

## 8. `audit`

鑱岃矗锛?

- 璁板綍鍏抽敭鍔ㄤ綔鏃ュ織

鏁版嵁琛細

- `audit_logs`

瑙﹀彂鐐癸細

- 瀹跺涵鍒涘缓
- 鎴愬憳缂栬緫
- 鎴块棿缂栬緫
- 璁惧鍚屾

---

## 浜屻€佺洰褰曞缓璁?

```text
apps/api-server/
鈹溾攢鈹€ app/
鈹?  鈹溾攢鈹€ api/
鈹?  鈹?  鈹斺攢鈹€ v1/
鈹?  鈹溾攢鈹€ core/
鈹?  鈹溾攢鈹€ db/
鈹?  鈹溾攢鈹€ modules/
鈹?  鈹?  鈹溾攢鈹€ household/
鈹?  鈹?  鈹溾攢鈹€ member/
鈹?  鈹?  鈹溾攢鈹€ relationship/
鈹?  鈹?  鈹溾攢鈹€ permission/
鈹?  鈹?  鈹溾攢鈹€ room/
鈹?  鈹?  鈹溾攢鈹€ device/
鈹?  鈹?  鈹溾攢鈹€ ha_integration/
鈹?  鈹?  鈹斺攢鈹€ audit/
鈹?  鈹斺攢鈹€ main.py
鈹斺攢鈹€ migrations/
```

---

## 涓夈€佹暟鎹ā鍨?

鏈?Spec 棣栨壒閲囩敤浠ヤ笅琛細

1. `households`
2. `members`
3. `member_relationships`
4. `member_preferences`
5. `member_permissions`
6. `rooms`
7. `devices`
8. `device_bindings`
9. `audit_logs`

鍏朵腑锛?

- `members.household_id` 鍏宠仈 `households.id`
- `rooms.household_id` 鍏宠仈 `households.id`
- `devices.room_id` 鍏宠仈 `rooms.id`
- `device_bindings.device_id` 鍏宠仈 `devices.id`

---

## 鍥涖€佹潈闄愯璁?

棣栨湡鍏堝仛鏈€灏忚鍒欙細

### 绠＄悊鍛?

- 鍙鐞嗗搴€佹垚鍛樸€佹埧闂淬€佽澶囥€佹潈闄?

### 鎴愪汉

- 榛樿鍙鍏叡璧勬簮鍜岃嚜韬祫婧?

### 鍎跨

- 鍙兘璁块棶鑷繁鐨勯潪鏁忔劅璧勬簮

### 鑰佷汉

- 榛樿鍙闂嚜韬浉鍏虫彁閱掍笌鍏叡淇℃伅

### 璁垮

- 鍙彲璁块棶鏋佸皯閲忓叕鍏变俊鎭?

棣栨湡鏉冮檺鍒ゆ柇寤鸿锛?

1. 鍏堝熀浜庤鑹插仛榛樿鏉冮檺
2. 鍐嶈鍙?`member_permissions` 澧為噺瑕嗙洊

---

## 浜斻€丠A 璁惧鍚屾璁捐

## 杈撳叆

- 绠＄悊鍛樻墜鍔ㄨЕ鍙戝悓姝?

## 鍚屾娴佺▼

1. 璇锋眰 HA 瀹炰綋鍒楄〃
2. 杩囨护棣栨湡鏀寔绫诲瀷锛?
   - 鐏?
   - 绌鸿皟
   - 绐楀笜
   - 闊崇
   - 鎽勫儚澶?
   - 闂ㄩ攣
   - 浼犳劅鍣?
3. 褰掍竴鍖栧瓧娈?
4. 鑻ユ湰鍦颁笉瀛樺湪鍒欐柊寤?`devices`
5. 鍐欏叆 `device_bindings`
6. 鍐欏叆瀹¤鏃ュ織

## 澶辫触澶勭悊

- 鍗曚釜瀹炰綋澶辫触涓嶉樆鏂暣鎵?
- 璁板綍澶辫触鍘熷洜
- 杩斿洖鍚屾鎴愬姛鏁?澶辫触鏁?

---

## 鍏€佸璁¤璁?

瀹¤鏃ュ織璁板綍瀛楁锛?

- actor
- action
- target_type
- target_id
- result
- details
- created_at

棣栨湡蹇呴』鎺ュ叆瀹¤鐨勬帴鍙ｏ細

- 鍒涘缓瀹跺涵
- 缂栬緫鎴愬憳
- 閰嶇疆鍏崇郴
- 閰嶇疆鏉冮檺
- 鏂板鎴块棿
- HA 璁惧鍚屾

---

## 涓冦€佹帴鍙ｈ璁″師鍒?

1. 鎵€鏈夋帴鍙ｈ蛋 `/api/v1`
2. 鎵€鏈夊啓鎺ュ彛蹇呴』鏍￠獙绠＄悊鍛樿韩浠?
3. 鍒楄〃鎺ュ彛榛樿鍒嗛〉
4. 閿欒杩斿洖缁熶竴鏍煎紡
5. 鍐欐搷浣滄垚鍔熷悗灏介噺杩斿洖鏈€鏂板璞?

---

## 鍏€佷负浠€涔堝厛鍋氳繖涓€灞?

鍥犱负瀹冭В鍐崇殑鏄暣涓」鐩悗缁渶闅剧粺涓€銆佹渶瀹规槗杩斿伐鐨勯儴鍒嗭細

- 椤跺眰瀹跺涵妯″瀷
- 鎴愬憳涓绘暟鎹?
- 璁惧涓绘暟鎹?
- 鏉冮檺杈圭晫
- 鎴块棿璁惧鏄犲皠

涓€鏃﹁繖涓€灞傛竻鏅帮紝鍚庣画鎻愰啋銆侀棶绛斻€佽蹇嗐€佸箍鎾€佸満鏅紪鎺掗兘鑳藉缓绔嬪湪绋冲畾缁撴瀯涓娿€?

