> 说明：本文件里出现的 SQLite 描述属于历史方案或阶段性验收记录。项目已于 2026-03-16 统一切换到 PostgreSQL，当前实现与测试基线都以 PostgreSQL 为准。

# 璁捐鏂囨。 - 瀹跺眳鎺ュ叆涓庝笂涓嬫枃涓績

鐘舵€侊細Draft

## 1. 姒傝堪

### 1.1 璁捐鐩爣

鏈?Spec 瑕佽В鍐崇殑涓嶆槸鈥滃啀澶氭帴鍑犱釜璁惧鈥濓紝鑰屾槸鎶婅澶囥€佹垚鍛樸€佹埧闂村拰褰撳墠鐘舵€佷覆鎴愪竴涓兘鐢ㄧ殑涓婁笅鏂囧眰銆?

棣栨湡璁捐鐩爣鏈夊洓涓細

1. 璁╄澶囨帴鍏ヤ粠鈥滈潤鎬佹竻鍗曗€濆崌绾у埌鈥滃彲鎰熺煡銆佸彲鎵ц鈥?
2. 璁╃郴缁熸湁绋冲畾鐨勬垚鍛樺湪瀹跺揩鐓у拰鎴块棿鍗犵敤缁撴灉
3. 璁╁墠绔兘涓€娆℃€ф媺鍒板搴笂涓嬫枃鎬昏
4. 璁╃鐞嗗憳鏈変竴濂楄兘鐪嬨€佽兘璋冦€佽兘绾犲亸鐨勭鐞嗙晫闈?

### 1.2 鑼冨洿杈圭晫

鏈湡浼樺厛瀹屾垚锛?

- `Home Assistant` 璁惧鍚屾澶嶇敤涓庡熀纭€鍔ㄤ綔鎵ц
- 鍦ㄥ浜嬩欢鎺ュ叆涓庢垚鍛樼姸鎬佽仛鍚堥鏋?
- 鎴块棿鍗犵敤鍜屾椿璺冩垚鍛樼儹缂撳瓨
- 瀹跺涵涓婁笅鏂囨€昏鏌ヨ鎺ュ彛
- 绠＄悊鍙板灞呬笂涓嬫枃浠〃鐩樹笌閰嶇疆椤?

鏈湡鏄庣‘涓嶅仛锛?

- 瀹屾暣澶氭ā鎬佽瘑鍒畻娉?
- 瀹屾暣瑙勫垯寮曟搸涓庡鏉傚満鏅紪鎺?
- 澶嶆潅灏忕背鐢熸€佸弻鍚戞ˉ鎺?
- 鏈€缁堢増绉诲姩绔垨瀹跺涵灞忎氦浜?

### 1.3 褰撳墠闃舵浜や粯绛栫暐

褰撳墠闃舵鍏堣惤涓€涓?*鍓嶇鍘熷瀷椤?*锛屽師鍥犲緢绠€鍗曪細

- 鍚庣涓婁笅鏂囪兘鍔涜繕娌″啓瀹岋紝浣嗙鐞嗗憳椤甸潰涓嶈兘涓€鐩寸┖鐫€
- 鍏堟妸瑕佸睍绀轰粈涔堛€佽閰嶇疆浠€涔堝畾涓嬫潵锛屽悗绔帴鍙ｆ墠涓嶄細鐬庨暱
- 閰嶇疆鏁版嵁棣栨湡鍏佽鐢ㄦ祻瑙堝櫒鏈湴鎸佷箙鍖栨壙鎺ワ紝鍚庣画鍐嶆浛鎹㈡垚鍚庣 `context configs` API

杩欎笉鏄伔鎳掞紝杩欐槸鎶婃暟鎹粨鏋勫厛閽夋锛岄伩鍏嶅悗闈㈠墠鍚庣涓€璧蜂贡濂椼€?

---

## 2. 鏋舵瀯璁捐

### 2.1 妯″潡鎷嗗垎

鏈?Spec 鍦ㄧ幇鏈?`api-server` 鍩虹涓婃柊澧炴垨鎵╁睍浠ヤ笅妯″潡锛?

1. `ha_integration`
   - 澶嶇敤璁惧鍚屾鑳藉姏
   - 澧炲姞鍩虹鍔ㄤ綔鎵ц灏佽
2. `presence`
   - 鍐欏叆鍘熷鍦ㄥ浜嬩欢
   - 鎻愪緵浜嬩欢鏍￠獙
3. `context_engine`
   - 鑱氬悎鎴愬憳鍦ㄥ鐘舵€?
   - 璁＄畻娲昏穬鎴愬憳涓庢埧闂村崰鐢?
4. `context_cache`
   - 灏嗗揩鐓у啓鍏?`Redis`
   - 璐熻矗璇诲彇闄嶇骇閫昏緫
5. `context_api`
   - 鎻愪緵涓婁笅鏂囨€昏涓庨厤缃帴鍙?
6. `admin_web_context`
   - 鎻愪緵浠〃鐩樸€佹垚鍛樼姸鎬侀潰鏉裤€佹埧闂寸儹鍖哄拰閰嶇疆鐣岄潰

### 2.2 杩愯鏃朵緷璧?

- `SQLite`锛氭寔涔呭寲鍘熷浜嬩欢銆佹垚鍛樺揩鐓т笌閰嶇疆
- `Redis`锛氬瓨鍌ㄥ綋鍓嶅搴儹缂撳瓨
- `Home Assistant`锛氳澶囩姸鎬併€佸疄浣撳悓姝ヤ笌鍔ㄤ綔鎵ц
- `Admin Web`锛氭煡鐪嬫€昏銆佽皟鏁撮厤缃€佸仛婕旂ず涓庨獙鏀?

### 2.3 鏍稿績鏁版嵁娴?

#### 搂2.3.1 璁惧鍚屾娴?

`Admin Web` / 璋冨害浠诲姟 鈫?`ha_integration` 鈫?`devices` / `device_bindings` 鈫?瀹¤鏃ュ織

#### 搂2.3.2 鍦ㄥ浜嬩欢娴?

澶栭儴閫傞厤鍣?鈫?`presence` 鈫?`presence_events` 鈫?`context_engine` 鈫?`member_presence_state` 鈫?`Redis`

#### 搂2.3.3 涓婁笅鏂囨€昏鏌ヨ娴?

`Admin Web` 鈫?`context_api` 鈫?璇诲彇 `Redis` 鐑紦瀛?鈫?涓嶈冻閮ㄥ垎琛ユ煡 `SQLite` 鍜?`devices` 鈫?鑱氬悎鍝嶅簲

#### 搂2.3.4 璁惧鍔ㄤ綔鎵ц娴?

蹇矾寰勬垨绠＄悊鍙?鈫?`context_api` / `ha_integration` 鈫?鏉冮檺鏍￠獙 鈫?`Home Assistant` 鏈嶅姟璋冪敤 鈫?瀹¤鏃ュ織

---

## 3. 缁勪欢涓庢帴鍙?

### 3.1 澶嶇敤璁惧鍚屾鎺ュ彛

缁х画澶嶇敤锛?

- `POST /api/v1/devices/sync/ha`

璇存槑锛?

- 璇ユ帴鍙ｆ潵鑷?`Spec 001`
- 鏈?Spec 涓嶉噸閫犺疆瀛愶紝鍙姹傚悓姝ョ粨鏋滆兘琚笂涓嬫枃椤垫秷璐?
- 鍓嶇浠〃鐩橀渶灞曠ず鏈€杩戝悓姝ョ粨鏋滀笌璁惧鍋ュ悍姒傚喌

### 3.2 鍦ㄥ浜嬩欢鍐欏叆鎺ュ彛

寤鸿鏂板锛?

- `POST /api/v1/context/presence-events`

#### 杈撳叆

```json
{
  "household_id": "uuid",
  "member_id": "uuid 鎴?null",
  "room_id": "uuid 鎴?null",
  "source_type": "lock|camera|bluetooth|sensor|voice",
  "source_ref": "door_lock.main",
  "confidence": 0.92,
  "payload": {
    "event": "unlock",
    "summary": "camera matched parent"
  },
  "occurred_at": "2026-03-09T07:30:00Z"
}
```

#### 杈撳嚭

```json
{
  "event_id": "uuid",
  "accepted": true,
  "snapshot_updated": true
}
```

#### 鏍￠獙绾︽潫

- `household_id` 蹇呭～
- `source_type` 蹇呴』鍦ㄦ敮鎸佹灇涓惧唴
- `confidence` 鑼冨洿涓?`0 ~ 1`
- `member_id`銆乣room_id` 鑻ュ瓨鍦紝蹇呴』灞炰簬褰撳墠瀹跺涵
- `occurred_at` 涓嶅緱鏄庢樉瓒呭嚭鍏佽鏃堕挓鍋忓樊

#### 閿欒杩斿洖

- `400`锛氬瓧娈电己澶辨垨鏋氫妇闈炴硶
- `404`锛氭垚鍛樻垨鎴块棿涓嶅瓨鍦?
- `409`锛氫簨浠堕噸澶嶆垨鍐茬獊
- `422`锛氱疆淇″害銆佹椂闂存埑绛夎涔夋牎楠屽け璐?

### 3.3 瀹跺涵涓婁笅鏂囨€昏鎺ュ彛

寤鸿鏂板锛?

- `GET /api/v1/context/overview?household_id=<id>`

#### 杈撳嚭缁撴瀯

```json
{
  "household_id": "uuid",
  "home_mode": "home",
  "privacy_mode": "balanced",
  "automation_level": "assisted",
  "home_assistant_status": "healthy",
  "active_member": {
    "member_id": "uuid",
    "name": "Jamie",
    "confidence": 0.91,
    "current_room_id": "uuid"
  },
  "member_states": [],
  "room_occupancy": [],
  "device_summary": {
    "total": 12,
    "active": 9,
    "offline": 2,
    "controllable": 8
  },
  "insights": [],
  "degraded": false,
  "generated_at": "2026-03-09T08:00:00Z"
}
```

#### 璁捐瑕佺偣

- 浠ュ搴负杈圭晫杈撳嚭瀹屾暣鎬昏
- 鎴愬憳銆佹埧闂淬€佽澶囬兘鍏佽涓虹┖鏁扮粍
- `degraded=true` 鐢ㄦ潵琛ㄧず缂撳瓨鎴栧閮ㄧ姸鎬佺己澶憋紝浣嗗搷搴斾粛鍙敤
- 鍓嶇涓嶅繀鑷繁鎷?5 涓帴鍙ｅ幓鐚滃叏灞€鐘舵€?

### 3.4 瀹跺涵涓婁笅鏂囬厤缃帴鍙?

寤鸿鏂板锛?

- `GET /api/v1/context/configs/{household_id}`
- `PUT /api/v1/context/configs/{household_id}`

#### 閰嶇疆鍐呭

- 瀹跺涵妯″紡锛歚home / away / night / sleep / custom`
- 闅愮妯″紡锛歚balanced / strict / care`
- 鑷姩鍖栫瓑绾э細`manual / assisted / automatic`
- 璁垮妯″紡銆佸効绔ヤ繚鎶ゃ€佽€佷汉鍏虫€€銆侀潤闊虫椂娈点€佽闊冲揩璺緞
- 鎴愬憳绾т笂涓嬫枃瑕嗙洊椤?
- 鎴块棿绾х瓥鐣ヨ鐩栭」

#### 褰撳墠闃舵绛栫暐

- 鍚庣鎺ュ彛鏈畬鎴愬墠锛岀鐞嗗彴浣跨敤娴忚鍣ㄦ湰鍦拌崏绋挎壙鎺?
- 鑽夌缁撴瀯蹇呴』涓庡悗绔渶缁堥厤缃粨鏋勫敖閲忎竴鑷?
- 鍚庣画鍒囨崲鍒板悗绔帴鍙ｆ椂锛岄〉闈笉搴旈噸鍐欎竴閬?

### 3.5 鍩虹璁惧鍔ㄤ綔鎵ц鎺ュ彛

寤鸿鏂板锛?

- `POST /api/v1/device-actions/execute`

#### 杈撳叆

```json
{
  "household_id": "uuid",
  "device_id": "uuid",
  "action": "turn_on",
  "params": {
    "brightness": 80
  },
  "reason": "context.fast_path"
}
```

#### 涓氬姟瑙勫垯

- 璁惧蹇呴』灞炰簬褰撳墠瀹跺涵
- 璁惧蹇呴』 `controllable=true`
- 楂橀闄╄澶囧姩浣滈渶瑕佹潈闄愭牎楠?
- 鎴愬姛澶辫触閮藉啓瀹¤鏃ュ織

### 3.6 绠＄悊鍙伴〉闈㈣璁?

璺敱锛?

- `/context-center`

椤甸潰鐢卞洓灞傜粍鎴愶細

1. **瀹跺涵鐘舵€?Hero 鍖?*
   - 褰撳墠瀹跺涵鍚嶇О
   - 瀹跺涵妯″紡 / 闅愮妯″紡 / 鑷姩鍖栫瓑绾?/ HA 鐘舵€?
   - 褰撳墠娲昏穬鎴愬憳
2. **鍏抽敭鎸囨爣浠〃鐩?*
   - 鍦ㄥ鎴愬憳鏁?
   - 宸插崰鐢ㄦ埧闂存暟
   - 鍦ㄧ嚎璁惧鏁?
   - 閲嶇偣鍏虫敞鎴愬憳鏁?
3. **鎴愬憳涓庢埧闂寸姸鎬侀潰鏉?*
   - 鎴愬憳鍗＄墖锛氬湪瀹剁姸鎬併€佹椿鍔ㄧ姸鎬併€佸綋鍓嶄綅缃€佺疆淇″害
   - 鎴块棿鍗＄墖锛氬崰鐢ㄦ儏鍐点€佽澶囨暟閲忋€佹埧闂寸瓥鐣?
4. **閰嶇疆鐣岄潰**
   - 瀹跺涵绾х瓥鐣ラ厤缃?
   - 鎴愬憳鐘舵€佹紨绀洪厤缃?
   - 鎴块棿绛栫暐閰嶇疆

椤甸潰鏁版嵁瑁呴厤绛栫暐锛?

- 鍏堝苟鍙戞媺 `members / rooms / devices / audit_logs`
- 褰撳墠闃舵鐢ㄦ湰鍦拌崏绋胯ˉ榻愬皻鏈湁鍚庣鐨勬暟鎹?
- 鍔犺浇杩囩▼閲囩敤 `Promise.allSettled`锛岄伩鍏嶄竴涓帴鍙ｅけ璐ュ鑷存暣椤靛簾鎺?

---

## 4. 鏁版嵁妯″瀷

### 4.1 `presence_events`

鐢ㄩ€旓細淇濆瓨鍘熷鍦ㄥ浜嬩欢銆?

| 瀛楁 | 绫诲瀷 | 璇存槑 |
|---|---|---|
| id | text pk | 浜嬩欢 ID |
| household_id | text fk | 鎵€灞炲搴?|
| member_id | text nullable fk | 鍛戒腑鐨勬垚鍛?|
| room_id | text nullable fk | 鍏宠仈鎴块棿 |
| source_type | varchar(30) | `lock/camera/bluetooth/sensor/voice` |
| source_ref | varchar(255) | 鏉ユ簮寮曠敤 |
| confidence | real | 缃俊搴?|
| payload | text(JSON) | 鍘熷鎽樿 |
| occurred_at | text | 浜嬩欢鍙戠敓鏃堕棿 |
| created_at | text | 鍏ュ簱鏃堕棿 |

绱㈠紩锛?

- `idx_presence_events_household_occurred_at`
- `idx_presence_events_member_id`
- `idx_presence_events_source_type`

### 4.2 `member_presence_state`

鐢ㄩ€旓細淇濆瓨鎴愬憳褰撳墠鍦ㄥ蹇収銆?

| 瀛楁 | 绫诲瀷 | 璇存槑 |
|---|---|---|
| member_id | text pk fk | 鎴愬憳 ID |
| household_id | text fk | 鎵€灞炲搴?|
| status | varchar(20) | `home/away/unknown` |
| current_room_id | text nullable fk | 褰撳墠鎴块棿 |
| confidence | real | 鑱氬悎鍚庣疆淇″害 |
| source_summary | text(JSON) | 鏉ユ簮鎽樿 |
| updated_at | text | 鏇存柊鏃堕棿 |

璇存槑锛?

- 姣忎釜鎴愬憳鏈€澶氬彧鏈変竴鏉″綋鍓嶅揩鐓?
- 涓嶈褰曞巻鍙诧紝鍘嗗彶鐢?`presence_events` 鎵挎媴

### 4.3 `context_configs`

鐢ㄩ€旓細淇濆瓨瀹跺涵绾т笂涓嬫枃閰嶇疆銆?

| 瀛楁 | 绫诲瀷 | 璇存槑 |
|---|---|---|
| household_id | text pk fk | 鎵€灞炲搴?|
| config_json | text(JSON) | 瀹跺涵銆佹垚鍛樸€佹埧闂撮厤缃崏妗?|
| version | integer | 鐗堟湰鍙?|
| updated_by | text nullable | 鏈€鍚庝慨鏀逛汉 |
| updated_at | text | 鏇存柊鏃堕棿 |

璁捐鐞嗙敱锛?

- 閰嶇疆缁撴瀯浠嶅湪婕旇繘锛岀敤 JSON 姣旀媶 5 寮犲皬琛ㄦ洿绋?
- 棣栨湡鍐欏皯璇诲锛孞SON 鏌ヨ鎬ц兘涓嶆槸闂
- 鍙杈圭晫鏍￠獙鍋氬ソ锛屽鏉傚害杩滀綆浜庤繃鏃╂瑙勫寲

### 4.4 `Redis` 鐑紦瀛橀敭璁捐

- `context:household:{household_id}:overview`
- `context:household:{household_id}:member_presence`
- `context:household:{household_id}:room_occupancy`
- `context:household:{household_id}:active_member`

### 4.5 鍓嶇鏈湴鑽夌缁撴瀯

褰撳墠闃舵 `Admin Web` 浣跨敤娴忚鍣ㄦ湰鍦板瓨鍌紝缁撴瀯涓?`context_configs.config_json` 瀵归綈锛?

```json
{
  "home_mode": "home",
  "privacy_mode": "balanced",
  "automation_level": "assisted",
  "home_assistant_status": "healthy",
  "active_member_id": "uuid 鎴?null",
  "voice_fast_path_enabled": true,
  "guest_mode_enabled": false,
  "child_protection_enabled": true,
  "elder_care_watch_enabled": true,
  "quiet_hours_enabled": true,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "07:00",
  "member_states": [],
  "room_settings": []
}
```

---

## 5. 姝ｇ‘鎬у睘鎬т笌涓氬姟涓嶅彉閲?

### 5.1 瀹跺涵杈圭晫涓嶅彉閲?

- 浠讳綍鎴愬憳銆佹埧闂淬€佽澶囥€侀厤缃兘蹇呴』灞炰簬鍚屼竴涓?`household_id`
- 璺ㄥ搴紩鐢ㄤ竴寰嬫嫆缁?

### 5.2 鎴愬憳蹇収涓嶅彉閲?

- 涓€涓垚鍛樺彧鑳芥湁涓€鏉″綋鍓嶅揩鐓?
- 褰撳墠蹇収鐢辨渶鏂版湁鏁堜簨浠惰仛鍚堝緱鍒?
- 浣庣疆淇″害涓嶈兘浼鎴愰珮纭畾鐘舵€?

### 5.3 鎴块棿鍗犵敤涓嶅彉閲?

- 鎴块棿鍗犵敤鍙敱鈥滃綋鍓嶅湪瀹朵笖瀹氫綅鏄庣‘鈥濈殑鎴愬憳蹇収鎺ㄥ
- 娌℃湁鎴愬憳鏃舵埧闂寸姸鎬佸繀椤绘槸绌烘垨鏈煡锛屼笉鑳藉嚟绌烘湁浜?

### 5.4 娲昏穬鎴愬憳涓嶅彉閲?

- 娲昏穬鎴愬憳蹇呴』鏄綋鍓嶅搴垚鍛?
- 娲昏穬鎴愬憳蹇呴』涓庡綋鍓嶅湪鍦轰笂涓嬫枃涓€鑷达紝鍚﹀垯搴斾负 `null`

### 5.5 閰嶇疆涓€鑷存€т笉鍙橀噺

- 閰嶇疆涓殑 `member_id` 鍜?`room_id` 蹇呴』瀛樺湪浜庡綋鍓嶅搴?
- 鍒犻櫎鎴愬憳鎴栨埧闂村悗锛岄厤缃紩鐢ㄥ繀椤昏娓呯悊鎴栧拷鐣?

### 5.6 瀹¤涓嶅彉閲?

- 璁惧鍔ㄤ綔鎵ц銆侀厤缃繚瀛樸€佸悓姝ヤ换鍔＄瓑鍏抽敭鍔ㄤ綔閮藉繀椤诲彲杩借釜
- 澶辫触涔熻鐣欑棔锛屼笉鑳藉彧璁版垚鍔熶笉璁板け璐?

---

## 6. 閿欒澶勭悊

### 6.1 澶栭儴绯荤粺閿欒

#### `Home Assistant` 涓嶅彲鐢?

澶勭悊绛栫暐锛?

- 璁惧鍚屾鎴栧姩浣滄墽琛岃繑鍥炲け璐?
- 瀹¤鍐?`fail`
- 涓婁笅鏂囨€昏灏?`home_assistant_status` 鏍囦负 `degraded` 鎴?`offline`

### 6.2 浜嬩欢杈撳叆閿欒

#### 闈炴硶鏉ユ簮銆侀潪娉曞搴€侀潪娉曟埧闂?

澶勭悊绛栫暐锛?

- 鎷掔粷鍐欏叆
- 杩斿洖鏄庣‘瀛楁閿欒
- 涓嶅厑璁歌剰浜嬩欢姹℃煋鑱氬悎閾捐矾

### 6.3 缂撳瓨閿欒

#### `Redis` 澶辨晥鎴栦笉鍙揪

澶勭悊绛栫暐锛?

- 浠?`SQLite` 蹇収闄嶇骇鏌ヨ
- 鍝嶅簲涓爣璁?`degraded=true`
- 鍐欐棩蹇楄褰曢檷绾у彂鐢?

### 6.4 鍓嶇閮ㄥ垎鏁版嵁鍔犺浇澶辫触

澶勭悊绛栫暐锛?

- 椤甸潰浣跨敤 `Promise.allSettled`
- 鍙睍绀洪儴鍒嗙户缁睍绀?
- 椤堕儴缁欏嚭鏄庣‘閿欒鎻愮ず
- 涓嶆妸鏁翠釜椤甸潰鍙樻垚鐧芥澘

---

## 7. 娴嬭瘯绛栫暐

### 7.1 鍗曞厓娴嬭瘯

瑕嗙洊锛?

- 鍦ㄥ浜嬩欢鏍￠獙
- 鎴愬憳蹇収鑱氬悎閫昏緫
- 鎴块棿鍗犵敤鎺ㄥ閫昏緫
- 閰嶇疆 JSON 鏍￠獙涓庡綊涓€鍖?

### 7.2 鎺ュ彛闆嗘垚娴嬭瘯

瑕嗙洊锛?

- `POST /context/presence-events`
- `GET /context/overview`
- `PUT /context/configs/{household_id}`
- `POST /device-actions/execute`

楠岃瘉鐐癸細

- 姝ｅ父璺緞
- 闈炴硶瀹跺涵杈圭晫
- 缂撳瓨闄嶇骇璺緞
- 瀹¤鍐欏叆

### 7.3 鍓嶇楠岃瘉

瑕嗙洊锛?

- `apps/admin-web` 鏋勫缓閫氳繃
- 瀹跺眳涓婁笅鏂囬〉鍦ㄦ湁/鏃犲搴満鏅笅鍙敤
- 鏈湴鑽夌鍒锋柊鍚庡彲鎭㈠
- 瀹跺涵鍒囨崲鍚庝华琛ㄧ洏鍜岄厤缃悓姝ュ垏鎹?

### 7.4 浜哄伐鑱旇皟

瑕嗙洊锛?

- 鐪熷疄 `Home Assistant` 鍚屾鎴愬姛
- 妯℃嫙鍦ㄥ浜嬩欢鍐欏叆鍚庯紝涓婁笅鏂囨€昏鑳藉弽鏄犲彉鍖?
- 鍓嶇閰嶇疆涓庡悗绔厤缃粨鏋勫榻?

---

## 8. 椋庨櫓涓庡洖婊氱瓥鐣?

### 8.1 鏈€澶ч闄?

1. 浜嬩欢鍣０澶ぇ锛屽鑷存垚鍛樼姸鎬佹潵鍥炴姈鍔?
2. 閰嶇疆缁撴瀯杩囨棭鎷嗙粏锛屽鑷村墠鍚庣涓€璧峰鏉傚寲
3. 鍓嶇鍏堝仛鍘熷瀷浣嗘暟鎹粨鏋勬病閽夋锛屽悗闈㈤噸鍐欎竴閬?

### 8.2 搴斿绛栫暐

1. 鍘熷浜嬩欢涓庤仛鍚堝揩鐓у垎灞備繚瀛?
2. 閰嶇疆棣栨湡鏀舵暃鍒颁竴寮?JSON 琛?
3. 鍓嶇鍘熷瀷涓ユ牸璐磋繎鍚庣璁″垝缁撴瀯
4. 瀵逛綆缃俊搴︾粨鏋滈粯璁や繚瀹堝鐞?

### 8.3 鍥炴粴绛栫暐

- 鏂版帴鍙ｅ彲鎸夎矾鐢卞拰鍔熻兘寮€鍏崇嫭绔嬪叧闂?
- 绠＄悊鍙伴〉闈㈠彲閫€鍥炲彧璇绘ā寮?
- 缂撳瓨涓嶅彲鐢ㄦ椂閫€鍥炴暟鎹簱蹇収鏌ヨ

