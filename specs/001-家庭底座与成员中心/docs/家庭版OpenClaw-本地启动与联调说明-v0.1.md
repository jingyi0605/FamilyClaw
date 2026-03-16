> 说明：本文件里出现的 SQLite 描述属于历史方案或阶段性验收记录。项目已于 2026-03-16 统一切换到 PostgreSQL，当前实现与测试基线都以 PostgreSQL 为准。

# 瀹跺涵鐗?OpenClaw 鏈湴鍚姩涓庤仈璋冭鏄?v0.1

## 1. 鐩爣

鏈枃妗ｇ敤浜庡府鍔╂柊鎴愬憳鍦?30 鍒嗛挓鍐呭畬鎴愪互涓嬪姩浣滐細

- 鍚姩鍚庣鏈嶅姟
- 鍒濆鍖?SQLite 鏁版嵁搴撲笌杩佺Щ
- 鍐欏叆婕旂ず鐢ㄦā鎷熸暟鎹?
- 鍚姩绠＄悊鍙?
- 閰嶇疆骞惰仈璋?Home Assistant 璁惧鍚屾

---

## 2. 褰撳墠宸ョ▼缁撴瀯

鏍稿績鐩綍濡備笅锛?

- `apps/api-server`锛欶astAPI 鍚庣
- `apps/admin-web`锛歏ite + React 绠＄悊鍙?
- `apps/start-api-server.sh`锛氬悗绔惎鍔ㄨ剼鏈紝鑷姩澶勭悊 venv銆佷緷璧栥€佽縼绉讳笌鐑噸杞?
- `apps/seed-api-server.sh`锛氭紨绀烘暟鎹瀛愯剼鏈?
- `apps/start-admin-web.sh`锛氬墠绔惎鍔ㄨ剼鏈紝鑷姩妫€鏌ヤ緷璧栧苟鏀寔鐑噸杞?
- `specs/001-瀹跺涵搴曞骇涓庢垚鍛樹腑蹇?docs/瀹跺涵鐗圤penClaw-棣栨壒鎺ュ彛鏂囨。-v0.1.md`锛氶鎵规帴鍙ｆ枃妗?

---

## 3. 鐜瑕佹眰

鏈湴寤鸿鐜锛?

- Python `3.11`
- Node.js `18+`
- npm `9+`

棣栨湡鏁版嵁搴撳浐瀹氫娇鐢細

- SQLite

褰撳墠闃舵鑼冨洿浠呴檺锛?

- 瀹跺涵搴曞骇
- 鎴愬憳涓績
- 鎴块棿涓庤澶?
- 瀹¤鏃ュ織
- Home Assistant 璁惧鍚屾

鏈撼鍏ラ鏈熻仈璋冭寖鍥达細

- 闂瓟
- 闀挎湡璁板繂
- 璇煶
- 澶嶆潅鍦烘櫙缂栨帓

---

## 4. 鍚庣鍚姩

### 4.1 閰嶇疆鐜鍙橀噺

鍦?`apps/api-server` 涓嬪垱寤烘湰鍦?`.env`锛?

```bash
cp apps/api-server/.env.example apps/api-server/.env
```

寤鸿鑷冲皯纭浠ヤ笅鍙橀噺锛?

```env
FAMILYCLAW_DATABASE_URL=postgresql+psycopg://familyclaw:change-me@127.0.0.1:5432/familyclaw
FAMILYCLAW_HOME_ASSISTANT_BASE_URL=http://127.0.0.1:8123
FAMILYCLAW_HOME_ASSISTANT_TOKEN=replace-with-your-token
FAMILYCLAW_HOME_ASSISTANT_TIMEOUT_SECONDS=10
```

璇存槑锛?

- `.env` 宸茶蹇界暐锛屼笉搴旀彁浜ゅ埌浠撳簱
- 濡傞渶鎺ュ叆鐪熷疄 HA锛岃鏇挎崲 `BASE_URL` 涓?`TOKEN`

### 4.2 鍚姩鍛戒护

鍦ㄤ粨搴撴牴鐩綍鎵ц锛?

```bash
./apps/start-api-server.sh
```

鑴氭湰浼氳嚜鍔ㄥ畬鎴愶細

- 妫€娴?`python3.11`
- 鍒涘缓 `apps/api-server/.venv`
- 渚濇嵁 `pyproject.toml` 妫€鏌ュ苟瀹夎渚濊禆
- 鎵ц `alembic upgrade head`
- 浠ョ儹閲嶈浇妯″紡鍚姩 `uvicorn`

榛樿鍦板潃锛?

- `http://0.0.0.0:8000`

甯哥敤瑕嗙洊鍙傛暟锛?

```bash
HOST=0.0.0.0 PORT=8000 ./apps/start-api-server.sh
```

### 4.3 鍩虹楠岃瘉

```bash
curl http://127.0.0.1:8000/api/v1/healthz
curl http://127.0.0.1:8000/
```

棰勬湡锛?

- 涓や釜鎺ュ彛鍧囧彲杩斿洖 `status: ok`

---

## 5. PostgreSQL 与迁移验证

### 5.1 鎵ц杩佺Щ

鑻ュ彧鎯冲崟鐙墽琛岃縼绉伙細

```bash
cd apps/api-server
source .venv/bin/activate
alembic upgrade head
```

### 5.2 检查 PostgreSQL 连接

推荐直接检查 `.env` 中的连接串和 Alembic 版本，而不是再去看本地 SQLite 文件。

### 5.3 验证表已经创建

可以执行：

```bash
cd apps/api-server
alembic current
```

预期至少要确认：

- `households`
- `members`
- `member_relationships`
- `member_preferences`
- `member_permissions`
- `rooms`
- `devices`
- `device_bindings`
- `audit_logs`
- `alembic_version`

---

## 6. 婕旂ず鏁版嵁

### 6.1 鍐欏叆妯℃嫙鏁版嵁

鍦ㄤ粨搴撴牴鐩綍鎵ц锛?

```bash
./apps/seed-api-server.sh
```

鎴栨墜鍔ㄦ墽琛岋細

```bash
cd apps/api-server
source .venv/bin/activate
alembic upgrade head
python -m app.seed
```

### 6.2 妯℃嫙鏁版嵁绾﹀畾

褰撳墠绉嶅瓙鏁版嵁鍧囨樉寮忔爣璁颁负妯℃嫙鏁版嵁锛?

- 鍚嶇О鍓嶇紑锛歚[妯℃嫙鏁版嵁]`
- 璁惧缁戝畾鍓嶇紑锛歚mock.`
- 瀹¤鍔ㄤ綔锛歚seed.mock_data`

閫傜敤鍦烘櫙锛?

- 椤甸潰婕旂ず
- 鍓嶅悗绔仈璋?
- 闈炵敓浜х幆澧冨洖褰掗獙璇?

---

## 7. 绠＄悊鍙板惎鍔?

### 7.1 鍚姩鍛戒护

鍦ㄤ粨搴撴牴鐩綍鎵ц锛?

```bash
./apps/start-admin-web.sh
```

鑴氭湰浼氳嚜鍔ㄥ畬鎴愶細

- 妫€娴?`node` 涓?`npm`
- 瀵?`package.json` 鍙樺寲鍋氫緷璧栨鏌?
- 鑷姩 `npm install`
- 鍚姩 Vite 鐑洿鏂板紑鍙戞湇鍔″櫒

榛樿鍦板潃锛?

- `http://0.0.0.0:5173`

### 7.2 褰撳墠椤甸潰鑼冨洿

褰撳墠绠＄悊鍙板凡鍙闂細

- 瀹跺涵绠＄悊
- 鎴愬憳绠＄悊
- 鎴愬憳鍏崇郴
- 鍋忓ソ涓庢潈闄?
- 鎴块棿涓庤澶?
- 瀹¤鏃ュ織

---

## 8. Home Assistant 鑱旇皟

### 8.1 鍓嶆彁

闇€瑕佸噯澶囷細

- 鍙闂殑 Home Assistant 鍦板潃
- 闀挎湡璁块棶 Token

鍦?`apps/api-server/.env` 涓厤缃細

```env
FAMILYCLAW_HOME_ASSISTANT_BASE_URL=http://your-ha-host:8123
FAMILYCLAW_HOME_ASSISTANT_TOKEN=your-long-lived-access-token
```

### 8.2 鑱旇皟姝ラ

1. 鍚姩鍚庣锛歚./apps/start-api-server.sh`
2. 鍚姩鍓嶇锛歚./apps/start-admin-web.sh`
3. 纭繚宸插瓨鍦ㄥ綋鍓嶅搴?
4. 杩涘叆绠＄悊鍙扳€滄埧闂翠笌璁惧鈥濋〉
5. 鐐瑰嚮鈥滄墜鍔ㄥ悓姝?HA 璁惧鈥?
6. 瑙傚療璁惧鍒楄〃涓庡悓姝ユ憳瑕?
7. 杩涘叆鈥滃璁℃棩蹇椻€濋〉纭鏄惁鐢熸垚鍚屾璁板綍

### 8.3 鎺ュ彛鑱旇皟鏂瑰紡

涔熷彲鐩存帴璋冪敤鎺ュ彛锛?

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/devices/sync/ha" \
  -H "Content-Type: application/json" \
  -H "X-Actor-Role: admin" \
  -d '{
    "household_id": "YOUR_HOUSEHOLD_ID"
  }'
```

### 8.4 甯歌闂

#### HA 鍦板潃涓嶅彲杈?

鐜拌薄锛?

- 杩斿洖 `502`
- 閿欒淇℃伅閫氬父涓鸿繛鎺ヨ秴鏃躲€佽繛鎺ヨ鎷掔粷鎴栬矾鐢变笉鍙揪

鎺掓煡寤鸿锛?

- 纭涓绘満涓?HA 鍦ㄥ悓涓€缃戞
- 妫€鏌ラ槻鐏涓庣鍙?`8123`
- 纭 HA 宸插惎鍔?

#### Token 鏃犳晥

鐜拌薄锛?

- HA 鍚屾澶辫触
- 瀹¤涓褰曞け璐ョ粨鏋?

鎺掓煡寤鸿锛?

- 閲嶆柊鐢熸垚闀挎湡璁块棶 Token
- 妫€鏌?`.env` 涓槸鍚︽湁澶氫綑绌烘牸鎴栨崲琛?

#### 鍚屾鍚庤澶囦负绌?

鎺掓煡寤鸿锛?

- 妫€鏌?HA 涓槸鍚﹀凡鏈夊彲璇嗗埆瀹炰綋
- 褰撳墠褰掍竴鍖栭潰鍚戝父瑙佸搴澶囧疄浣擄紝闈炵洰鏍囧疄浣撳彲鑳借璺宠繃

---

## 9. 鑱旇皟鎺ㄨ崘椤哄簭

寤鸿鎸変互涓嬮『搴忛獙璇侊細

1. 鍋ュ悍妫€鏌ワ細`/api/v1/healthz`
2. 瀹跺涵鍒涘缓涓庢煡璇?
3. 鎴愬憳鍒涘缓銆佺紪杈戙€佸仠鐢?
4. 鎴愬憳鍏崇郴閰嶇疆
5. 鎴愬憳鍋忓ソ涓庢潈闄愰厤缃?
6. 鎴块棿鍒涘缓涓庤澶囧綊灞炶皟鏁?
7. HA 鎵嬪姩鍚屾
8. 瀹¤鏃ュ織鏍稿

---

## 10. 鏈疆鑱旇皟楠屾敹寤鸿

鍙寜浠ヤ笅鏈€灏忛棴鐜繘琛岋細

1. 鍒涘缓涓€涓搴?
2. 鍒涘缓鑷冲皯 2 涓垚鍛?
3. 閰嶇疆 1 鏉℃垚鍛樺叧绯?
4. 涓烘煇鎴愬憳淇濆瓨鍋忓ソ涓庢潈闄?
5. 鍒涘缓 1 涓埧闂?
6. 瑙﹀彂 1 娆?HA 鍚屾
7. 璋冩暣鑷冲皯 1 涓澶囧綊灞?
8. 鍦ㄥ璁℃棩蹇椾腑纭鍏抽敭鍐欐搷浣滃凡璁板綍

瀹屾垚浠ヤ笂姝ラ锛屽彲瑙嗕负褰撳墠 `瀹跺涵搴曞骇涓庢垚鍛樹腑蹇僠 MVP 宸插叿澶囬杞仈璋冨熀纭€銆?

