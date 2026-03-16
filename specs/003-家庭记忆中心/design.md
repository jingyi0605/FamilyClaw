> 说明：本文件里出现的 SQLite 描述属于历史方案或阶段性验收记录。项目已于 2026-03-16 统一切换到 PostgreSQL，当前实现与测试基线都以 PostgreSQL 为准。

# 璁捐鏂囨。 - 瀹跺涵璁板繂涓績

鐘舵€侊細Draft

## 1. 姒傝堪

### 1.1 鐩爣

- 鎶婂搴暱鏈熻蹇嗕粠姒傚康鍙樻垚鐪熷疄鍙惤搴撱€佸彲妫€绱€佸彲娌荤悊鐨勮兘鍔?
- 鍦ㄤ笉鐮村潖鐜版湁涓婁笅鏂囦腑蹇冦€侀棶绛斻€佹彁閱掗摼璺殑鍓嶆彁涓嬶紝琛ラ綈闀挎湡璁板繂灞?
- 鐢ㄦ渶绠€鍗曚絾鍙紨杩涚殑鏂瑰紡瀹炵幇闀挎湡璁板繂锛屼笉鍦ㄧ涓€鐗堝紩鍏ヤ笉蹇呰澶嶆潅搴?

### 1.2 瑕嗙洊闇€姹?

- `requirements.md` 闇€姹?1锛氱粺涓€璁板繂鍐欏洖鍏ュ彛
- `requirements.md` 闇€姹?2锛氱粨鏋勫寲闀挎湡璁板繂鍗?
- `requirements.md` 闇€姹?3锛氶暱鏈熻蹇嗘帴鍏?Context Engine
- `requirements.md` 闇€姹?4锛氶暱鏈熻蹇嗘绱笌闂瓟鎺ュ叆
- `requirements.md` 闇€姹?5锛氳蹇嗙籂閿欍€佸け鏁堝拰鍒犻櫎娌荤悊
- `requirements.md` 闇€姹?6锛氱鐞嗗彴涓庣敤鎴风璁板繂涓績鎺ュ叆

### 1.3 褰撳墠鐜扮姸鍒ゆ柇

褰撳墠浠ｇ爜宸茬粡鏈夊嚑鍧楄兘鐩存帴澶嶇敤鐨勫湴鍩猴細

- `apps/api-server/app/modules/context/service.py`锛氬彲鐢熸垚瀹跺涵瀹炴椂涓婁笅鏂囨€昏
- `apps/api-server/app/modules/context/cache_service.py`锛氬凡鏈夎交閲忎笂涓嬫枃缂撳瓨
- `apps/api-server/app/modules/family_qa/fact_view_service.py`锛氬彲鎶婁笂涓嬫枃銆佹彁閱掋€佸満鏅嫾鎴愰棶绛斾簨瀹炶鍥?
- `apps/api-server/app/modules/family_qa/schemas.py`锛氬凡棰勭暀 `QaMemorySummary`
- `apps/user-web/src/pages/MemoriesPage.tsx`锛氬凡鏈夎蹇嗛〉闈㈠澹筹紝浣嗕粛鏄?mock

褰撳墠缂哄彛涔熷緢娓呮锛?

- 杩樻病鏈夌湡姝ｇ殑 `memory_cards`銆乣memory_card_members`銆乣event_records` 瀹炵幇
- 闂瓟鏈嶅姟杩樻病鏈夊疄闄呰蛋闀挎湡璁板繂妫€绱?
- 涓婁笅鏂囩紦瀛樿繕鏄€滃綋鍓嶇姸鎬佺紦瀛樷€濓紝涓嶆槸闀挎湡璁板繂涓婁笅鏂囧紩鎿?
- 鎻愰啋銆佸満鏅€佸湪瀹剁姸鎬併€侀棶绛旂粨鏋滆繕娌＄粺涓€鍐欏洖

### 1.4 鎶€鏈害鏉熶笌璁捐鍘熷垯

- 鍚庣锛歚Python + FastAPI + SQLAlchemy`
- 鍓嶇锛歚React`
- 鏁版嵁瀛樺偍锛氬綋鍓嶄互 `SQLite` 涓轰富锛屽悗缁彲婕旇繘
- 缂撳瓨锛氬綋鍓嶅凡鏈夋湰鍦板唴瀛樼紦瀛樿兘鍔涳紝鍚庣画鍙崲 `Redis`
- 璁よ瘉鎺堟潈锛氭部鐢ㄧ幇鏈?admin / member actor 浣撶郴

璁捐鍘熷垯锛?

1. **鍏堜繚鐣欏師濮嬩簨浠讹紝鍐嶇敓鎴愭憳瑕?*銆傝繖鐐瑰€熼壌 `lossless-claw` 鐨勬€濊矾锛屽師濮嬩笂涓嬫枃涓嶈兘鍏堝ぉ涓㈠け銆?
2. **鍏堝仛缁撴瀯鍖栨绱紝鍐嶈皥璇箟妫€绱?*銆傜涓€鐗堝厛鎶婃暟鎹粨鏋勫仛瀵癸紝涓嶅厛鍫嗗悜閲忓簱銆?
3. **涓婁笅鏂囨寜鐩爣瑁佸壀锛屼笉鍋氬叏閲忔嫾鎺?*銆傝繖鐐瑰€熼壌 OpenClaw 鐨勯暱鏈熻蹇嗕笌 Context Engine 鎬濊矾銆?
4. **缁濅笉鐮村潖鐜版湁鎺ュ彛**銆傚綋鍓?`context`銆乣family_qa`銆乣reminder`銆乣scene` 鍏堜繚鐣欑幇鏈夎涓猴紝閫愭鎺ュ叆闀挎湡璁板繂銆?

## 2. 鏋舵瀯

### 2.1 绯荤粺缁撴瀯

瀹跺涵璁板繂涓績閲囩敤鈥滀袱灞傛暟鎹?+ 涓€涓嫾瑁呭紩鎿庘€濈殑缁撴瀯锛?

1. **浜嬩欢娴佹按灞?*
   - 淇濆瓨鍘熷浜嬪疄鏉ユ簮
   - append-only
   - 鏀寔閲嶆斁銆佸箓绛夈€佽拷璐?

2. **闀挎湡璁板繂灞?*
   - 淇濆瓨鍙洿鎺ユ湇鍔￠棶绛斻€佹彁閱掋€侀櫔浼寸殑缁撴瀯鍖栬蹇?
   - 鏀寔鏇存銆佸け鏁堛€佸垹闄ゃ€佹潈闄愯繃婊?

3. **Context Engine**
   - 鎸夎姹傜被鍨嬨€佹垚鍛樿韩浠姐€佹潈闄愯寖鍥淬€乼oken 棰勭畻鎷艰涓婁笅鏂?
   - 鍚堝苟瀹炴椂涓婁笅鏂囥€侀暱鏈熻蹇嗐€佹渶杩戜簨浠躲€佸緟澶勭悊浜嬮」

### 2.2 妯″潡鑱岃矗

| 妯″潡 | 鑱岃矗 | 杈撳叆 | 杈撳嚭 |
| --- | --- | --- | --- |
| `memory_event_ingestor` | 鎺ユ敹鍚勬ā鍧楀啓鍥炰簨浠?| presence / reminder / scene / qa / manual | `event_records` |
| `memory_extractor` | 浠庝簨浠舵彁鐐艰蹇嗗崱 | `event_records` | `memory_cards`銆乣memory_card_members` |
| `memory_revision_service` | 澶勭悊绾犻敊銆佸け鏁堛€佸垹闄?| 浜哄伐鎿嶄綔銆佺郴缁熷悎骞?| `memory_card_revisions`銆佹湁鏁堣蹇嗙姸鎬?|
| `memory_query_service` | 鎼滅储鍜岀瓫閫夐暱鏈熻蹇?| 鏌ヨ鏉′欢銆佹潈闄愯寖鍥?| 璁板繂鍊欓€夐泦 |
| `context_engine` | 鎷艰鏈嶅姟涓婁笅鏂?| 瀹炴椂涓婁笅鏂囥€侀暱鏈熻蹇嗐€佹渶杩戜簨浠躲€佹潈闄?| `MemoryContextBundle` |
| `memory_api` | 鎻愪緵鍓嶇涓庡唴閮ㄦ帴鍙?| HTTP 璇锋眰 | 鍒楄〃銆佽鎯呫€佹煡璇€佷慨璁㈢粨鏋?|

### 2.3 鍏抽敭娴佺▼

#### 2.3.1 璁板繂鍐欏洖娴佺▼

1. `presence`銆乣reminder`銆乣scene`銆乣family_qa`銆佸墠绔汉宸ュ綍鍏ヨ皟鐢ㄧ粺涓€鍐欏洖鍏ュ彛銆?
2. 绯荤粺鍏堝啓 `event_records`锛屼繚璇佸師濮嬩簨浠惰惤搴撱€?
3. `memory_extractor` 鍒ゆ柇鏄惁鍊煎緱鐢熸垚鎴栨洿鏂拌蹇嗗崱銆?
4. 濡傚懡涓幓閲嶉敭锛屽垯鏇存柊宸叉湁璁板繂鍗¤€屼笉鏄柊澧為噸澶嶅崱銆?
5. 璁板繂鍗″彉鏇村悗鍒锋柊鐑憳瑕佸拰涓婁笅鏂囩紦瀛樸€?

#### 2.3.2 闀挎湡璁板繂妫€绱㈡祦绋?

1. 闂瓟鎴栧墠绔姹傚厛鎷垮埌 actor 鍜?household銆?
2. 绯荤粺鐢熸垚鏉冮檺鑼冨洿锛氬彲瑙佹垚鍛樸€佸彲瑙佹埧闂淬€佸彲瑙佸彲瑙佹€х骇鍒€?
3. 鍏堝仛缁撴瀯鍖栫瓫閫夛細鎴愬憳銆佺被鍨嬨€佹椂闂淬€佺姸鎬併€佸彲瑙佹€с€?
4. 鍐嶅仛鍏抽敭璇嶆绱㈠拰杞婚噺鎺掑簭銆?
5. 杈撳嚭鍊欓€夎蹇嗭紝骞剁敓鎴愬彲瑙ｉ噴浜嬪疄寮曠敤銆?

#### 2.3.3 Context Engine 鎷艰娴佺▼

1. 鏍规嵁鑳藉姏绫诲瀷閫夋嫨涓婁笅鏂囨ā鏉匡紝濡?`family_qa`銆乣assistant_chat`銆乣reminder_broadcast`銆?
2. 鎷夊彇瀹炴椂涓婁笅鏂囷細娲昏穬鎴愬憳銆佸湪瀹剁姸鎬併€佹埧闂村崰鐢ㄣ€佽澶囨瑙堛€?
3. 鎷夊彇闀挎湡璁板繂锛氫簨瀹炪€佸亸濂姐€佸叧绯汇€佽繎鏈熼噸瑕佷簨浠躲€?
4. 鍚堝苟寰呭鐞嗕簨椤癸細鎻愰啋銆佽繍琛屼腑鍦烘櫙銆佹湭纭浜嬩欢銆?
5. 鍦ㄩ绠楀唴瑁佸壀杈撳嚭锛屽舰鎴愮粨鏋勫寲 `MemoryContextBundle`銆?

#### 2.3.4 绾犻敊涓庡垹闄ゆ祦绋?

1. 鍓嶇鍙戣捣鏇存銆佸け鏁堟垨鍒犻櫎璇锋眰銆?
2. 绯荤粺鍏堝仛鏉冮檺鏍￠獙銆?
3. 鐢熸垚 `memory_card_revisions` 璁板綍銆?
4. 鏇存柊褰撳墠鏈夋晥璁板繂鐘舵€併€?
5. 鍒锋柊鐑憳瑕併€佹悳绱㈢粨鏋滃拰涓婁笅鏂囩紦瀛樸€?

#### 2.3.5 鍘嗗彶鍥炲～娴佺▼

1. 浠庣幇鏈?`presence_events`銆佹彁閱掓祦姘淬€佸満鏅墽琛岃褰曚腑璇诲彇鍘嗗彶璁板綍銆?
2. 杞崲鎴愮粺涓€ `event_records`銆?
3. 鎸夊箓绛夐敭閫愭壒鍐欏叆銆?
4. 鎵ц鎻愮偧娴佺▼鐢熸垚棣栨壒闀挎湡璁板繂鍗°€?

## 3. 缁勪欢鍜屾帴鍙?

### 3.1 鏍稿績缁勪欢

瑕嗙洊闇€姹傦細1銆?銆?銆?銆?銆?

- `app/modules/memory/models.py`
- `app/modules/memory/schemas.py`
- `app/modules/memory/repository.py`
- `app/modules/memory/service.py`
- `app/modules/memory/context_engine.py`
- `app/api/v1/endpoints/memories.py`

### 3.2 鏁版嵁妯″瀷

#### 3.2.1 `event_records`

鐢ㄩ€旓細

- 淇濆瓨鎵€鏈夊彲娌夋穩涓洪暱鏈熻蹇嗙殑鍘熷杈撳叆
- 浣滀负鍥炴斁銆侀噸璇曞拰杩借矗鐨勫敮涓€浜嬪疄鏉ユ簮

瀛楁寤鸿锛?

| 瀛楁 | 绫诲瀷 | 璇存槑 |
| --- | --- | --- |
| `id` | `text pk` | 浜嬩欢 ID |
| `household_id` | `text fk` | 鎵€灞炲搴?|
| `event_type` | `varchar(50)` | `presence_changed` / `reminder_done` / `scene_executed` / `qa_confirmed` / `memory_manual_created` |
| `source_type` | `varchar(30)` | `presence` / `reminder` / `scene` / `qa` / `admin` / `member` |
| `source_ref` | `text nullable` | 鏉ユ簮瀵硅薄 ID |
| `subject_member_id` | `text nullable fk` | 涓昏鍏宠仈鎴愬憳 |
| `room_id` | `text nullable fk` | 鍏宠仈鎴块棿 |
| `payload_json` | `text` | 鍘熷浜嬩欢鍐呭 |
| `dedupe_key` | `text nullable` | 骞傜瓑閿?|
| `processing_status` | `varchar(20)` | `pending` / `processed` / `failed` / `ignored` |
| `generate_memory_card` | `integer` | 鏄惁灏濊瘯鐢熸垚璁板繂 |
| `failure_reason` | `text nullable` | 澶辫触鍘熷洜 |
| `occurred_at` | `text` | 浜嬩欢鍙戠敓鏃堕棿 |
| `created_at` | `text` | 鍐欏叆鏃堕棿 |
| `processed_at` | `text nullable` | 澶勭悊瀹屾垚鏃堕棿 |

鍏抽敭瑙勫垯锛?

- `event_records` append-only锛屼笉鍋氱墿鐞嗚鐩栨洿鏂?
- `dedupe_key` 鍛戒腑鏃跺彧鏇存柊澶勭悊鐘舵€侊紝涓嶆柊澧為噸澶嶈蹇?
- 鎵€鏈夊閮ㄦ潵婧愬厛钀戒簨浠讹紝鍐嶅仛鍚庣画鎻愮偧

#### 3.2.2 `memory_cards`

鐢ㄩ€旓細

- 淇濆瓨鍙洿鎺ユ湇鍔′簬闂瓟銆佹彁閱掑拰闄即鐨勭粨鏋勫寲闀挎湡璁板繂

瀛楁寤鸿锛?

| 瀛楁 | 绫诲瀷 | 璇存槑 |
| --- | --- | --- |
| `id` | `text pk` | 璁板繂 ID |
| `household_id` | `text fk` | 鎵€灞炲搴?|
| `memory_type` | `varchar(30)` | `fact` / `event` / `preference` / `relation` / `growth` |
| `title` | `varchar(200)` | 鏍囬 |
| `summary` | `text` | 浜虹被鍙鎽樿 |
| `normalized_text` | `text` | 鐢ㄤ簬妫€绱㈢殑褰掍竴鍖栨枃鏈?|
| `content_json` | `text` | 缁撴瀯鍖栨鏂?|
| `status` | `varchar(20)` | `active` / `pending_review` / `invalidated` / `deleted` |
| `visibility` | `varchar(30)` | `public` / `family` / `private` / `sensitive` |
| `importance` | `integer` | 1~5 |
| `confidence` | `real` | 0~1 |
| `subject_member_id` | `text nullable fk` | 涓讳綋鎴愬憳 |
| `source_event_id` | `text nullable fk` | 鏉ユ簮浜嬩欢 |
| `dedupe_key` | `text nullable` | 鍘婚噸閿?|
| `effective_at` | `text nullable` | 鐢熸晥鏃堕棿 |
| `last_observed_at` | `text nullable` | 鏈€杩戜竴娆¤瑙傚療鍒?|
| `created_by` | `varchar(30)` | `system` / `admin` / `member` |
| `created_at` | `text` | 鍒涘缓鏃堕棿 |
| `updated_at` | `text` | 鏇存柊鏃堕棿 |
| `invalidated_at` | `text nullable` | 澶辨晥鏃堕棿 |

鍏抽敭瑙勫垯锛?

- 鍚屼竴闀挎湡浜嬪疄浼樺厛鏇存柊鏃у崱锛岃€屼笉鏄敓鎴愬寮犲唴瀹圭瓑浠风殑鍗?
- `status != active` 鐨勫崱榛樿涓嶅弬涓庝笂涓嬫枃鎷艰
- `visibility` 蹇呴』鍙備笌鏌ヨ鍜屼笂涓嬫枃杩囨护

#### 3.2.3 `memory_card_members`

鐢ㄩ€旓細

- 鏄惧紡缁存姢璁板繂鍗″拰鎴愬憳鐨勫叧绯?

瀛楁寤鸿锛?

| 瀛楁 | 绫诲瀷 | 璇存槑 |
| --- | --- | --- |
| `memory_id` | `text fk` | 璁板繂 ID |
| `member_id` | `text fk` | 鎴愬憳 ID |
| `relation_role` | `varchar(30)` | `subject` / `participant` / `mentioned` / `owner` |

绾︽潫锛?

- `primary key(memory_id, member_id, relation_role)`

#### 3.2.4 `memory_card_revisions`

鐢ㄩ€旓細

- 淇濆瓨鏇存銆佸悎骞躲€佸け鏁堛€佸垹闄ゅ巻鍙?

瀛楁寤鸿锛?

| 瀛楁 | 绫诲瀷 | 璇存槑 |
| --- | --- | --- |
| `id` | `text pk` | 淇 ID |
| `memory_id` | `text fk` | 璁板繂 ID |
| `revision_no` | `integer` | 鐗堟湰鍙?|
| `action` | `varchar(30)` | `create` / `correct` / `merge` / `invalidate` / `delete` |
| `before_json` | `text nullable` | 鍙樻洿鍓嶅揩鐓?|
| `after_json` | `text nullable` | 鍙樻洿鍚庡揩鐓?|
| `reason` | `text nullable` | 鍘熷洜 |
| `actor_type` | `varchar(30)` | `system` / `admin` / `member` |
| `actor_id` | `text nullable` | 鎿嶄綔鑰?|
| `created_at` | `text` | 鍒涘缓鏃堕棿 |

### 3.3 妫€绱笌鎺掑簭绛栫暐

#### 3.3.1 绗竴鐗堟绱㈢瓥鐣?

绗竴鐗堜笉鍋氳姳鍝ㄤ笢瑗匡紝鎸変笅闈㈤『搴忔潵锛?

1. 鏉冮檺杩囨护
2. 缁撴瀯鍖栫瓫閫?
3. 鍏抽敭璇嶅尮閰?
4. 绠€鍗曟帓搴?

鎺掑簭寤鸿鍒嗘暟锛?

- 鎴愬憳鐩存帴鍛戒腑锛歚+40`
- `memory_type` 涓庨棶棰樻剰鍥句竴鑷达細`+20`
- 鏈€杩?30 澶╀簨浠讹細`+15`
- `importance >= 4`锛歚+10`
- `confidence >= 0.8`锛歚+10`
- 鏁忔劅璁板繂锛氭棤鏉冮檺鐩存帴杩囨护

#### 3.3.2 鐑憳瑕佺瓥鐣?

鐑憳瑕佷笉鏄柊鐨勪簨瀹炴簮锛屽彧鏄紦瀛樺眰銆?

寤鸿缂撳瓨涓ょ被缁撴灉锛?

- 鎸夊搴淮搴︼細杩戞湡閲嶈浜嬩欢銆佸叏灞€鍋忓ソ鍙樺寲銆佹彁閱掓湭瀹屾垚浜嬮」
- 鎸夋垚鍛樼淮搴︼細楂橀鍋忓ソ銆佽繎鏈熶簨浠躲€佸叧绯绘憳瑕?

缂撳瓨鏉ユ簮锛?

- `memory_cards`
- `event_records`
- `context/service.py` 褰撳墠瀹炴椂涓婁笅鏂?

缂撳瓨澶辨晥鏉′欢锛?

- 璁板繂鍗℃柊澧炪€佹洿鏂般€佸け鏁堛€佸垹闄?
- 鎻愰啋鐘舵€佸彉鍖?
- 鎴愬憳鍦ㄥ鐘舵€佸彂鐢熸樉钁楀彉鍖?

### 3.4 Context Engine 璁捐

#### 3.4.1 鐩爣

Context Engine 涓嶆槸鈥滃啀鍋氫竴涓紦瀛樷€濓紝鑰屾槸璐熻矗鎶婂綋鍓嶈姹傜湡姝ｉ渶瑕佺殑涓婁笅鏂囨嫾鍑烘潵銆?

#### 3.4.2 杈撳叆鍒囩墖

杈撳叆鑷冲皯鍖呭惈浠ヤ笅鍒囩墖锛?

- `request_profile`
  - `household_id`
  - `requester_member_id`
  - `capability`
  - `channel`
- `live_context_slice`
  - 娲昏穬鎴愬憳
  - 鎴愬憳鐘舵€?
  - 鎴块棿鍗犵敤
  - 璁惧鎽樿
- `memory_slice`
  - 浜嬪疄璁板繂
  - 鍋忓ソ璁板繂
  - 鍏崇郴璁板繂
  - 鏈€杩戜簨浠惰蹇?
- `task_slice`
  - 寰呭鐞嗘彁閱?
  - 杩愯涓満鏅?
- `guardrail_slice`
  - 鏉冮檺鑼冨洿
  - 鑴辨晱瑙勫垯
  - 闄嶇骇鏍囪

#### 3.4.3 杈撳嚭缁撴瀯

寤鸿瀹氫箟 `MemoryContextBundle`锛?

| 瀛楁 | 璇存槑 |
| --- | --- |
| `household_id` | 瀹跺涵 ID |
| `requester_member_id` | 璇锋眰鑰呮垚鍛?|
| `capability` | 褰撳墠鑳藉姏 |
| `live_context_summary` | 瀹炴椂涓婁笅鏂囨憳瑕?|
| `memory_facts` | 缁撴瀯鍖栭暱鏈熻蹇嗗垪琛?|
| `recent_events` | 鏈€杩戜簨浠跺垪琛?|
| `pending_items` | 寰呭鐞嗘彁閱掑拰鍦烘櫙鎽樿 |
| `masked_sections` | 琚潈闄愭垨闄嶇骇瑁佹帀鐨勯儴鍒?|
| `degraded` | 鏄惁闄嶇骇 |
| `generated_at` | 鐢熸垚鏃堕棿 |

#### 3.4.4 瑁佸壀瑙勫垯

- `family_qa`锛氫紭鍏堟垚鍛樹簨瀹炪€佸亸濂姐€佸叧绯汇€佽繎鏈熶簨浠?
- `assistant_chat`锛氫紭鍏堝綋鍓嶈亰澶╁璞＄浉鍏崇殑闀挎湡璁板繂鍜屾渶杩戜簰鍔?
- `reminder_broadcast`锛氫紭鍏堟彁閱掑璞°€佹埧闂翠笂涓嬫枃銆侀潤榛樿鍒?
- `scene_explanation`锛氫紭鍏堣Е鍙戜簨浠躲€佸彈褰卞搷鎴愬憳銆佸啿绐佸亸濂?

### 3.5 API 璁捐

#### 3.5.1 `GET /api/v1/memories`

鐢ㄩ€旓細

- 鏌ヨ璁板繂鍒楄〃

杈撳叆锛?

- `household_id`
- `memory_type`
- `member_id`
- `status`
- `visibility`
- `query`
- `limit`
- `cursor`

杈撳嚭锛?

- 璁板繂鍒楄〃
- 鎬绘暟鎴栧垎椤垫父鏍?
- 闄嶇骇鏍囪

閿欒澶勭悊锛?

- 鏃犳潈闄愶細`403`
- 瀹跺涵涓嶅瓨鍦細`404`
- 鏌ヨ鍙傛暟闈炴硶锛歚422`

#### 3.5.2 `GET /api/v1/memories/{memory_id}`

鐢ㄩ€旓細

- 鏌ョ湅璁板繂璇︽儏鍜屼慨璁㈠巻鍙叉憳瑕?

#### 3.5.3 `POST /api/v1/memories/events`

鐢ㄩ€旓細

- 鍐欏叆缁熶竴浜嬩欢娴佹按

璋冪敤鏂癸細

- 鍐呴儴妯″潡浼樺厛浣跨敤锛屼笉鐩存帴鏆撮湶缁欐櫘閫氱敤鎴风

#### 3.5.4 `POST /api/v1/memories/cards/manual`

鐢ㄩ€旓細

- 绠＄悊鍛樻垨鎺堟潈鎴愬憳鎵嬪姩鍒涘缓璁板繂

#### 3.5.5 `POST /api/v1/memories/{memory_id}/corrections`

鐢ㄩ€旓細

- 璁板繂绾犻敊銆佸け鏁堛€佸垹闄?

杈撳叆锛?

- `action`
- `reason`
- `patch`

#### 3.5.6 `POST /api/v1/memories/query`

鐢ㄩ€旓細

- 渚涢棶绛斿拰鍔╂墜璋冪敤鐨勭粨鏋勫寲妫€绱㈠叆鍙?

### 3.6 涓庣幇鏈夋ā鍧楃殑闆嗘垚鐐?

#### 3.6.1 `presence`

- `apps/api-server/app/modules/presence/service.py`
- 鎴愬憳鍦ㄥ鐘舵€佸彉鍖栨椂鍐?`presence_changed` 浜嬩欢
- 閲嶈鐘舵€佸垏鎹㈠彲鐢熸垚浜嬩欢璁板繂鎴栦簨瀹炴洿鏂?

#### 3.6.2 `reminder`

- `apps/api-server/app/modules/reminder/service.py`
- 鎻愰啋鍒涘缓銆佺‘璁ゃ€佸崌绾ф椂鍐欎簨浠?
- 鐢ㄤ簬鐢熸垚闀挎湡鎻愰啋鍋忓ソ銆佷緷浠庢€у拰鍏抽敭瀹屾垚璁板綍

#### 3.6.3 `scene`

- `apps/api-server/app/modules/scene/service.py`
- 鍦烘櫙鎵ц鎴愬姛/澶辫触鍐欎簨浠?
- 閲嶈鑱斿姩缁撴灉鍙矇娣€涓轰簨浠惰蹇?

#### 3.6.4 `family_qa`

- `apps/api-server/app/modules/family_qa/fact_view_service.py`
- `apps/api-server/app/modules/family_qa/service.py`
- 鐢?`memory_query_service` 鏇挎崲鐜板湪鐨勨€滆蹇嗘殏鏈帴鍏モ€濆崰浣?
- 闂瓟缁撴灉鏈韩涔熷彲閫夋嫨鎬у洖鍐欒蹇嗕簨浠?

#### 3.6.5 `context`

- `apps/api-server/app/modules/context/service.py`
- 缁х画璐熻矗瀹炴椂涓婁笅鏂?
- 鐢辨柊鐨?`context_engine` 鍦ㄥ叾涔嬩笂鎷奸暱鏈熻蹇嗗垏鐗?

## 4. 姝ｇ‘鎬х害鏉?

### 4.1 涓嶅彉閲?

1. 姣忔潯鏈夋晥璁板繂鍗￠兘蹇呴』鑳借拷鍒拌嚦灏戜竴涓潵婧愪簨浠舵垨浜哄伐鍒涘缓璁板綍銆?
2. 鏃犳潈闄?actor 姘歌繙涓嶈兘閫氳繃鍒楄〃銆佽鎯呮垨涓婁笅鏂囨嫾瑁呮嬁鍒版晱鎰熻蹇嗘鏂囥€?
3. 澶辨晥鎴栧垹闄ゅ悗鐨勮蹇嗗崱涓嶈兘缁х画杩涘叆 `family_qa` 鎴?Context Engine 缁撴灉銆?
4. 浜嬩欢鍐欏洖澶辫触涓嶅簲鐮村潖鍘熸湁鎻愰啋銆侀棶绛斻€佸満鏅富娴佺▼銆?

### 4.2 骞傜瓑瑙勫垯

1. 鍚屼竴鏉ユ簮閲嶅鍐欏叆蹇呴』鐢?`dedupe_key` 鏀舵暃銆?
2. 鍥炲～鑴氭湰閲嶅鎵ц涓嶅緱鍒堕€犻噸澶嶉暱鏈熻蹇嗐€?
3. 绾犻敊鎿嶄綔蹇呴』鍩轰簬 revision 搴忓彿锛岄伩鍏嶈鐩栧苟鍙戜慨鏀广€?

## 5. 閿欒澶勭悊

### 5.1 鍐欏洖澶辫触

- 淇濈暀 `event_records`
- 鏍囪 `processing_status=failed`
- 璁板綍 `failure_reason`
- 鏀寔鍚庡彴閲嶈瘯鎴栦汉宸ュ洖鏀?

### 5.2 妫€绱㈠け璐ユ垨缂撳瓨涓嶅彲鐢?

- 閫€鍥炴暟鎹簱鐩存帴鏌ヨ
- 鍦ㄥ搷搴斾腑鏍囪 `degraded=true`
- 涓嶅奖鍝嶇幇鏈変笂涓嬫枃涓庨棶绛斾富閾捐矾

### 5.3 鏉冮檺澶辫触

- 杩斿洖 `403`
- 瀹¤鏃ュ織璁板綍 actor銆佺洰鏍囪蹇嗗拰鎿嶄綔绫诲瀷

### 5.4 鏁版嵁鍐茬獊

- 鍘婚噸閿啿绐佹椂浼樺厛鏇存柊鏃у崱
- revision 鍐茬獊鏃舵嫆缁濆啓鍏ュ苟瑕佹眰閲嶆柊鑾峰彇鏈€鏂扮増鏈?

## 6. 杩佺Щ涓庡吋瀹圭瓥鐣?

### 6.1 杩佺Щ椤哄簭

1. 鏂板琛ㄥ拰妯″潡锛屼笉鍔ㄧ幇鏈夋帴鍙ｈ涓?
2. 鍏堟帴鍐欏洖锛屼笉绔嬪埢鍒囨帀鏃ч棶绛旈€昏緫
3. 鍐嶆帴 `family_qa` 鐨勯暱鏈熻蹇嗘绱?
4. 鏈€鍚庢浛鎹㈠墠绔?mock 鍜岃蹇嗕腑蹇冮〉闈?

### 6.2 鍚戝悗鍏煎

- `context/overview` 淇濇寔鍘熸帴鍙ｄ笉鍙?
- `family_qa` 鍦ㄨ蹇嗘湭鍛戒腑鎴栨ā鍧楀叧闂椂缁х画浣跨敤鍘熸湁 fact view 鑳藉姏
- 鐢ㄦ埛绔拰绠＄悊鍙板湪鎺ュ彛鏈帴瀹屽墠淇濈暀闄嶇骇鎻愮ず

### 6.3 鍔熻兘寮€鍏?

寤鸿澧炲姞锛?

- `memory_center_enabled`
- `memory_writeback_enabled`
- `memory_context_engine_enabled`
- `memory_backfill_enabled`

## 7. 娴嬭瘯绛栫暐

### 7.1 鍗曞厓娴嬭瘯

- 浜嬩欢鍘婚噸
- 璁板繂鎻愮偧
- 鏉冮檺杩囨护
- revision 鍐茬獊

### 7.2 鏈嶅姟娴嬭瘯

- `POST /memories/events`
- `GET /memories`
- `POST /memories/query`
- `POST /memories/{id}/corrections`

### 7.3 闆嗘垚娴嬭瘯

- `presence -> event_records -> memory_cards`
- `reminder -> event_records -> memory_cards`
- `family_qa + memory_query_service`
- `context_engine + permission_scope`

### 7.4 鍓嶇楠屾敹

- 绠＄悊鍙拌蹇嗕腑蹇冩煡璇€佺瓫閫夈€佺籂閿欍€佸垹闄?
- 鐢ㄦ埛绔蹇嗛〉浠?mock 鍒囧埌鐪熷疄鏁版嵁
- 鏉冮檺閬僵鍜岄檷绾ф彁绀哄彲瑙?

## 8. 椋庨櫓涓庡洖婊?

### 8.1 涓昏椋庨櫓

- 璁板繂閲嶅鐖嗙偢
- 鏉冮檺娉勯湶
- LLM 鍙備笌鎻愮偧鏃跺紩鍏ュ够瑙?
- 鐑憳瑕佷笌鐪熷疄鏁版嵁涓嶄竴鑷?

### 8.2 鎺у埗鍔炴硶

- 绗竴鐗堜紭鍏堣鍒欐彁鐐硷紝AI 鍙仛琛ュ厖鎽樿锛屼笉鍋氬敮涓€浜嬪疄鏉ユ簮
- 缁熶竴骞傜瓑閿拰 revision 鏈哄埗
- Context Engine 鍏堟潈闄愯繃婊わ紝鍐嶅仛鎷艰
- 鐑憳瑕侀殢鍐欐搷浣滄樉寮忓け鏁?

### 8.3 鍥炴粴绛栫暐

- 鍏抽棴 `memory_context_engine_enabled`锛岄棶绛斿洖閫€鍒扮幇鏈?fact view
- 鍏抽棴 `memory_writeback_enabled`锛屼富娴佺▼缁х画杩愯浣嗘殏鍋滈暱鏈熻蹇嗘柊澧?
- 淇濈暀宸插啓浜嬩欢涓庤蹇嗘暟鎹紝渚夸簬鍚庣画閲嶆柊鍚敤

