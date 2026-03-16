> 说明：本文件里出现的 SQLite 描述属于历史方案或阶段性验收记录。项目已于 2026-03-16 统一切换到 PostgreSQL，当前实现与测试基线都以 PostgreSQL 为准。

# 璁捐鏂囨。 - 瀹跺涵闂瓟鎻愰啋涓庡満鏅紪鎺?

鐘舵€侊細Draft

## 1. 姒傝堪

### 1.1 Spec 瀹氫綅

`Spec 002.1` 鏄?`Spec 002` 鐨勪笂灞傛湇鍔″瓙 Spec銆?

濡傛灉璇?`Spec 002` 瑙ｅ喅鐨勬槸鈥滅郴缁熺煡閬撹繖涓褰撳墠鍙戠敓浜嗕粈涔堚€濓紝閭ｄ箞鏈?Spec 瑙ｅ喅鐨勬槸鈥滅郴缁熸嬁杩欎簺淇℃伅鍘诲仛浠€涔堚€濄€?

褰撳墠闃舵鍙仛涓夌被鏈€鍊煎緱鍋氥€佹渶鑳芥紨绀恒€佷篃鏈€鑳界户缁線涓婃壙鎺ョ殑鑳藉姏锛?

1. **瀹跺涵闂瓟 v1**锛氬彧璇绘煡璇€佸彲瑙ｉ噴銆佸彲瑁佸壀
2. **鎻愰啋涓庡箍鎾?v1**锛氬彲閰嶇疆銆佸彲璋冨害銆佸彲纭銆佸彲鍗囩骇
3. **妯℃澘鍖栧満鏅紪鎺?v1**锛氭湁闄愭ā鏉裤€佹湁闄愭潯浠躲€佹湁闄愬姩浣溿€佸己瀹堝崼
4. **AI 渚涘簲鍟嗘娊璞″眰 v1**锛氱粺涓€妯″瀷渚涘簲鍟嗛厤缃€佽兘鍔涜矾鐢便€侀殣绉佽鍓笌闄嶇骇绛栫暐

### 1.2 鑼冨洿杈圭晫

鏈璁″彧瑙ｅ喅棣栨湡鍙棴鐜兘鍔涳細

- 鍥寸粫瀹跺涵鐘舵€併€佽澶囩姸鎬併€佹彁閱掔姸鎬佸拰鍩虹璁板繂鎽樿鐨勯棶绛?
- 鍥寸粫闂瓟銆佹彁閱掓枃妗堢敓鎴愩€佸満鏅В閲婄殑 AI 渚涘簲鍟嗘娊璞″眰
- 鍥寸粫瀹氭椂涓庝笂涓嬫枃瑙﹀彂鐨勬彁閱?
- 鍥寸粫涓夌被妯℃澘鍦烘櫙鐨勭紪鎺掍笌鎵ц
- 鍥寸粫鍚庡彴娌荤悊鐨勬湇鍔′腑蹇冮〉闈?

鏄庣‘涓嶅仛锛?

- 浠绘剰鑷劧璇█鍒颁换鎰忓姩浣滅殑鍏ㄨ嚜鍔ㄦ櫤鑳戒綋
- 閫氱敤鍙鍖栬鍒欏紩鎿?
- 澶ц妯″紓姝ュ伐浣滄祦骞冲彴
- 鍏ㄩ噺璁板繂涓績鎴栫浉鍐岄棶绛斿紩鎿?

### 1.3 鍒嗛樁娈典氦浠樼瓥鐣?

涓轰簡鎺у埗澶嶆潅搴︼紝鎸変笅闈㈤『搴忔帹杩涳細

1. **鍏堝仛 AI 妯″瀷缃戝叧銆佺粨鏋勫寲浜嬪疄瑙嗗浘涓庢潈闄愯鍓?*
2. **鍐嶅仛闂瓟 API v1 涓庢彁閱掍换鍔＄鐞?*
3. **鐒跺悗鍋氭彁閱掕皟搴︺€侀€佽揪銆佺‘璁ゃ€佸崌绾?*
4. **鏈€鍚庡仛妯℃澘鍦烘櫙銆佸啿绐佹不鐞嗗拰绠＄悊鍙伴泦鎴?*

杩欐剰鍛崇潃锛?

- AI 渚涘簲鍟嗗厛鍋氱粺涓€鎶借薄灞?
- 闂瓟鍏堝彧璇?
- 鎻愰啋鍏堣鍒欏寲
- 鍦烘櫙鍏堟ā鏉垮寲

涓嶈鍙嶈繃鏉ャ€傚弽杩囨潵灏辨槸杩囧害璁捐銆?

---

## 2. 鏋舵瀯璁捐

### 2.1 妯″潡鎷嗗垎

鏈?Spec 寤鸿鍦ㄧ幇鏈?`api-server` 鍩虹涓婃柊澧炴垨鎵╁睍浠ヤ笅妯″潡锛?

1. `family_qa`
   - 闂瓟璇锋眰鍏ュ彛
   - 缁撴瀯鍖栦簨瀹炶鍥炬嫾瑁?
   - 鏉冮檺瑁佸壀涓庡洖绛旂敓鎴?
2. `ai_gateway`
   - 渚涘簲鍟嗛€傞厤鍣ㄦ娊璞?
   - 鑳藉姏璺敱銆佷富澶囧垏鎹笌瓒呮椂閲嶈瘯
   - 璇锋眰鑴辨晱銆佺粨鏋滃綊涓€鍖栦笌璋冪敤瀹¤
3. `ai_provider_admin`
   - AI 渚涘簲鍟嗘。妗堢鐞?
   - 鑳藉姏璺敱閰嶇疆
   - 瀵嗛挜寮曠敤涓庨儴缃查厤缃槧灏?
4. `reminder`
   - 鎻愰啋浠诲姟 CRUD
   - 鎻愰啋鎬昏鏌ヨ
   - 鎻愰啋杩愯鐘舵€佹満
5. `reminder_scheduler`
   - 瀹氭椂鎵弿
   - 鏉′欢璇勪及
   - 杩愯鍒涘缓涓庡箓绛夋帶鍒?
6. `delivery`
   - 閫佽揪娓犻亾鎶借薄
   - 鎴块棿/鎴愬憳/璁惧璺敱
   - 鍗囩骇绛栫暐鎵ц
7. `scene_engine`
   - 妯℃澘鍦烘櫙娉ㄥ唽
   - 瑙﹀彂璇勪及
   - 瀹堝崼銆佸啿绐併€佸喎鍗村垽鏂?
8. `scene_execution`
   - 鍦烘櫙姝ラ鎵ц
   - 鎵ц鏃ュ織涓庡洖鎵ц仛鍚?
9. `service_center_admin`
   - 鏈嶅姟涓績绠＄悊鍙伴〉闈?
   - `context-center` 鎽樿鑱斿姩

### 2.2 杩愯鏃朵緷璧?

- `SQLite`锛氭彁閱掍换鍔°€佽繍琛岃褰曘€佸満鏅ā鏉裤€佹墽琛屾棩蹇楃瓑鎸佷箙鍖?
- `Redis`锛氱煭鏃跺幓閲嶉敭銆佽皟搴︽父鏍囥€佺儹鐐归棶绛斿缓璁紦瀛樸€佽繍琛屼腑鐨勫満鏅攣
- 澶栭儴鎴栨湰鍦?`AI Providers`锛歄penAI 鍏煎浜戞ā鍨嬨€佽嚜寤虹綉鍏炽€佹湰鍦版ā鍨嬫湇鍔＄瓑缁熶竴鎺ュ叆鐩爣
- 閮ㄧ讲渚?`Secret Store / ENV`锛氫繚瀛樹緵搴斿晢瀵嗛挜涓庢晱鎰熸帴鍏ヤ俊鎭?
- `Spec 002 context API`锛氭垚鍛樼姸鎬併€佹埧闂村崰鐢ㄣ€佽澶囨憳瑕佷笌褰撳墠瀹跺涵涓婁笅鏂?
- `Spec 001 household/member/device/permission`锛氬搴富鏁版嵁銆佹潈闄愪笌鍋忓ソ
- `Home Assistant`锛氳澶囧姩浣滄墽琛屼笌璁惧鐘舵€佹煡璇?
- `Admin Web`锛氭湇鍔′腑蹇冮〉闈€侀棶绛旇瘯杩愯銆佹彁閱掍笌鍦烘櫙绠＄悊

### 2.3 鏍稿績鏁版嵁娴?

#### 搂2.3.1 闂瓟鏌ヨ娴?

`Admin Web / Voice UI` 鈫?`family_qa` 鈫?缁勮 `QaFactView` 鈫?鏉冮檺瑁佸壀 鈫?`ai_gateway`锛堟垨妯℃澘鍥炵瓟锛夆啋 鍥炵瓟鐢熸垚 鈫?瀹¤鏃ュ織

瑕佺偣锛?

- 鍥炵瓟鍏堝熀浜庣粨鏋勫寲浜嬪疄锛屼笉瑕佸厛渚濊禆澶фā鍨嬭嚜鐢卞彂鎸?
- 涓氬姟妯″潡涓嶅緱鐩存帴缁戝畾鏌愬渚涘簲鍟?SDK锛屽繀椤荤粡杩囨ā鍨嬬綉鍏?
- 鍥炵瓟涓繀椤昏兘鍖哄垎鈥滀簨瀹炩€濆拰鈥滄帹鏂€?
- 棣栨湡鍙仛鍙锛屼笉甯﹁澶囨墽琛?

#### 搂2.3.2 鎻愰啋璋冨害娴?

`ReminderTask` 鈫?`reminder_scheduler` 瀹氭椂鎵弿 鈫?瑙﹀彂鏉′欢璇勪及 鈫?鍒涘缓 `ReminderRun` 鈫?鍐欏叆寰呴€佽揪闃熷垪

瑕佺偣锛?

- 浠モ€滀换鍔♀€濆拰鈥滆繍琛屸€濆垎绂伙紝閬垮厤鍚庣画鐘舵€佹墦鏋?
- 鍚屼竴璋冨害妲戒綅鍙兘鍒涘缓涓€涓湁鏁堣繍琛?
- 鏀寔瀹氭椂涓庢潯浠惰Е鍙戜袱绫诲叆鍙?

#### 搂2.3.3 鎻愰啋閫佽揪涓庣‘璁ゆ祦

`ReminderRun` 鈫?`delivery` 閫夋嫨鎴愬憳/鎴块棿/娓犻亾 鈫?鍒涘缓 `DeliveryAttempt` 鈫?绛夊緟 `AckEvent` 鈫?瓒呮椂鍚庡崌绾?

瑕佺偣锛?

- 閫佽揪涓庣‘璁ゅ垎寮€寤烘ā
- 鏈‘璁や笉鏄け璐ワ紝鍙槸鏈畬鎴?
- 鍗囩骇渚濊禆纭鐘舵€侊紝涓嶄緷璧栫寽娴?

#### 搂2.3.4 鍦烘櫙瑙﹀彂璇勪及娴?

澶栭儴浜嬩欢 / 瀹氭椂鍣?/ 鎵嬪姩瑙﹀彂 鈫?`scene_engine` 閫夋嫨妯℃澘 鈫?璇勪及鏉′欢涓庡畧鍗?鈫?鍐茬獊/鍐峰嵈鍒ゆ柇 鈫?鐢熸垚 `SceneExecution`

瑕佺偣锛?

- 棣栨湡鍙敮鎸佹ā鏉挎敞鍐岋紝涓嶆敮鎸佷换鎰忓浘寮忕紪鎺?
- 鏉′欢鍜屽畧鍗厛缁撴瀯鍖栵紝鍐嶆墽琛?
- 鍚屼竴瑙﹀彂婧愮殑鍘婚噸閿繀椤荤ǔ瀹?

#### 搂2.3.5 鍦烘櫙鎵ц涓庡璁℃祦

`SceneExecution` 鈫?閫愭鎵ц鎻愰啋/骞挎挱/涓婁笅鏂囨洿鏂?璁惧鍔ㄤ綔 鈫?鑱氬悎姝ラ缁撴灉 鈫?鍐欏璁′笌浜嬩欢璁板綍 鈫?鍥炲啓鏈嶅姟涓績鎬昏

瑕佺偣锛?

- 姝ラ绾х粨鏋滃繀椤昏惤搴?
- 澶辫触鍏佽閮ㄥ垎鎴愬姛锛屼絾蹇呴』璁叉竻妤氬摢閲屽け璐?
- 楂橀闄╁姩浣滀笉鍏佽琚ā鏉垮伔鍋风粫杩囩‘璁?

#### 搂2.3.6 AI 鑳藉姏璺敱涓庨檷绾ф祦

涓氬姟妯″潡锛堥棶绛?鎻愰啋/鍦烘櫙瑙ｉ噴锛?鈫?`ai_gateway` 鈫?璇诲彇 `AiCapabilityRoute` 鈫?閫夋嫨涓讳緵搴斿晢 鈫?璇锋眰鑴辨晱涓庢ā鏉挎嫾瑁?鈫?璋冪敤閫傞厤鍣?鈫?缁撴灉褰掍竴鍖?鈫?澶辫触鏃跺洖閫€鍒板渚涘簲鍟嗘垨妯℃澘鍥炵瓟

瑕佺偣锛?

- 璺敱浠モ€滆兘鍔涒€濅负鍗曚綅锛岃€屼笉鏄互鈥滈〉闈⑩€濇垨鈥滄ā鍧椻€濈‖缂栫爜
- 棣栨湡鑷冲皯瑕佹敮鎸?`qa_generation`銆乣reminder_copywriting`銆乣scene_explanation` 涓夌被鑳藉姏
- 鏈潵淇濈暀 `embedding`銆乣rerank`銆乣stt`銆乣tts`銆乣vision` 鑳藉姏浣嶏紝浣嗗綋鍓嶄笉瑕佹眰鍏ㄩ儴瀹炵幇
- 闄嶇骇蹇呴』鏄庣‘锛屼笉鍏佽 provider 鎸備簡浠ュ悗涓氬姟妯″潡鑷繁鍚勫啓涓€濂楀湡鍔炴硶

---

## 3. 缁勪欢涓庢帴鍙?

### 3.0 AI 妯″瀷渚涘簲鍟嗘娊璞′笌鑳藉姏璺敱

#### 3.0.1 璁捐鐩爣

杩欏眰涓嶆槸涓轰簡鐐妧锛岃€屾槸涓轰簡閬垮厤浠ュ悗绯荤粺閲屽埌澶勬暎钀斤細

- `if provider == openai`
- `if provider == local`
- `if provider == xxx`

杩欑浠ｇ爜涓€澶氾紝鏁翠釜绯荤粺浼氳繀閫熺儌鎺夈€?

妯″瀷缃戝叧灞傚繀椤绘妸浠ヤ笅浜嬫儏缁熶竴鏀朵綇锛?

1. 渚涘簲鍟嗚兘鍔涙敞鍐?
2. 涓诲璺敱
3. 瓒呮椂銆侀噸璇曘€佺啍鏂?
4. 璇锋眰鑴辨晱涓庨殣绉侀樆鏂?
5. 鍝嶅簲褰掍竴鍖?
6. 璋冪敤瀹¤涓庢垚鏈粺璁?

#### 3.0.2 鑳藉姏鍒嗗眰

妯″瀷鑳藉姏鎸夆€滅敤閫斺€濇媶鍒嗭紝涓嶆寜渚涘簲鍟嗘媶鍒嗭細

- `qa_generation`锛氬搴棶绛旇嚜鐒惰瑷€鐢熸垚
- `qa_structured_answer`锛氫弗鏍?JSON / 缁撴瀯鍖栧洖绛?
- `reminder_copywriting`锛氭彁閱掓枃妗堟鼎鑹蹭笌宸紓鍖栬〃杈?
- `scene_explanation`锛氬満鏅墽琛岃В閲婁笌棰勮璇存槑
- `embedding`锛氬悜閲忓寲
- `rerank`锛氭绱㈤噸鎺?
- `stt`锛氳闊宠浆鏂囨湰
- `tts`锛氭枃鏈浆璇煶
- `vision`锛氬浘鍍忕悊瑙?

褰撳墠 Spec 棣栨湡寮轰緷璧栧墠涓夐」锛屽悗浜旈」浣滀负缁熶竴鎶借薄棰勭暀鑳藉姏浣嶃€?

#### 3.0.3 渚涘簲鍟嗛€傞厤鍣ㄦ帴鍙?

寤鸿鍐呴儴鎶借薄锛?

- `ChatGenerationProvider`
- `StructuredOutputProvider`
- `EmbeddingProvider`
- `RerankProvider`
- `SpeechToTextProvider`
- `TextToSpeechProvider`
- `VisionProvider`

缁熶竴杈撳嚭缁撴瀯搴旇嚦灏戝寘鍚細

- `provider_code`
- `model_name`
- `capability`
- `trace_id`
- `latency_ms`
- `usage`
- `finish_reason`
- `raw_response_ref`
- `normalized_output`

#### 3.0.4 閰嶇疆鏉ユ簮

閰嶇疆鍒嗕袱灞傦細

1. **闈欐€侀儴缃查厤缃?*
   - 閫氳繃 `app/core/config.py` 鍜?`.env` 鎻愪緵榛樿缃戝叧琛屼负
   - 渚嬪榛樿瓒呮椂銆侀粯璁ゆ湰鍦颁紭鍏堛€佹槸鍚﹀厑璁歌繙绔緵搴斿晢銆侀粯璁ゅ瘑閽ュ紩鐢ㄥ墠缂€
2. **鍔ㄦ€佷笟鍔￠厤缃?*
   - 閫氳繃鏁版嵁搴撲腑鐨?`AiProviderProfile` 涓?`AiCapabilityRoute` 瀛樺偍鍙垏鎹㈡。妗?
   - 鐢ㄤ簬涓嶅悓瀹跺涵銆佷笉鍚岀幆澧冦€佷笉鍚岃兘鍔涚殑璺敱鍒囨崲

璇存槑锛?

- 瀵嗛挜涓嶅啓鍏ヤ笟鍔¤〃
- 涓氬姟琛ㄥ彧瀛?`secret_ref`
- 鐪熸瀵嗛挜鐢辩幆澧冨彉閲忔垨瀵嗛挜绠＄悊鍣ㄦ彁渚?

#### 3.0.5 绠＄悊鎺ュ彛

寤鸿鏂板锛?

- `GET /api/v1/ai/providers`
- `POST /api/v1/ai/providers`
- `PATCH /api/v1/ai/providers/{provider_profile_id}`
- `GET /api/v1/ai/routes`
- `PUT /api/v1/ai/routes/{capability}`

杩欎簺鎺ュ彛褰撳墠涓昏闈㈠悜绠＄悊鍛樺拰杩愮淮锛屼笉寮哄埗鍦ㄩ鏈熷墠绔氨浜や粯瀹屾暣閰嶇疆椤碉紝浣嗗悗绔绾﹀繀椤诲厛瑙勫垝娓呮銆?

#### 3.0.6 闄嶇骇绛栫暐

姣忎釜鑳藉姏鑷冲皯鏀寔 4 绉嶇瓥鐣ワ細

1. `template_only`锛氬畬鍏ㄤ笉璧版ā鍨嬶紝鍙敤妯℃澘鍥炵瓟
2. `primary_then_fallback`锛氬厛涓讳緵搴斿晢锛屽け璐ュ啀鍒囧渚涘簲鍟?
3. `local_only`锛氫粎鍏佽鏈湴妯″瀷
4. `local_preferred_then_cloud`锛氫紭鍏堟湰鍦帮紝澶辫触鍐嶅垏浜戠

棣栨湡闂瓟榛樿寤鸿锛?

- 浜嬪疄瑙嗗浘绋冲畾鏃讹細`template_only` 鎴?`local_preferred_then_cloud`
- 鏁忔劅瀹跺涵锛氫紭鍏?`local_only`
- 绠＄悊鍙拌皟璇曪細鍏佽 `primary_then_fallback`

### 3.1 瀹跺涵闂瓟鏌ヨ鎺ュ彛

寤鸿鏂板锛?

- `POST /api/v1/family-qa/query`

#### 杈撳叆

```json
{
  "household_id": "uuid",
  "requester_member_id": "uuid 鎴?null",
  "question": "鐖风埛浠婂ぉ鍚冭嵂浜嗗悧锛?,
  "channel": "admin_web",
  "context": {
    "room_id": "uuid 鎴?null",
    "active_member_id": "uuid 鎴?null"
  }
}
```

#### 杈撳嚭

```json
{
  "answer_type": "reminder_status",
  "answer": "浠婂ぉ鏅氶キ鍚庣殑鏈嶈嵂鎻愰啋宸茬粡瑙﹀彂锛屼絾杩樻病鏈夌‘璁ゅ畬鎴愩€?,
  "confidence": 0.91,
  "facts": [
    {
      "type": "reminder_run",
      "label": "鏅氶キ鍚庢湇鑽彁閱?,
      "source": "reminder_runs",
      "occurred_at": "2026-03-09T18:30:00Z",
      "visibility": "family",
      "inferred": false
    }
  ],
  "degraded": false,
  "suggestions": [
    "鏌ョ湅鎻愰啋璇︽儏",
    "鎵嬪姩鍐嶆鎻愰啋"
  ]
}
```

#### 棣栨湡鏀寔闂绫诲瀷

- 鎴愬憳鍦ㄥ/鎴块棿鐘舵€?
- 璁惧寮€鍏充笌鍩虹鍋ュ悍鐘舵€?
- 浠婃棩瀹夋帓/璇剧▼/鍏变韩鎻愰啋
- 鎻愰啋鏄惁宸茶Е鍙?宸茬‘璁?宸插畬鎴?
- 妯℃澘鍦烘櫙鏄惁鍚敤銆佹渶杩戞槸鍚︽墽琛?

#### 鏍￠獙绾︽潫

- `household_id` 蹇呭～
- `question` 涓嶅彲涓虹┖
- `requester_member_id` 鑻ュ瓨鍦ㄥ繀椤诲睘浜庡綋鍓嶅搴?
- 闂瓟鍙锛屼笉鎺ュ彈鍔ㄤ綔鍙傛暟

#### 閿欒杩斿洖

- `400`锛氶棶棰樹负绌恒€佸瓧娈电己澶?
- `403`锛氭棤鏉冩煡鐪嬬洰鏍囦俊鎭?
- `404`锛氬搴垨鎴愬憳涓嶅瓨鍦?
- `422`锛氶棶棰樹笉鍦ㄦ敮鎸佽寖鍥村唴涓旀棤娉曞畨鍏ㄩ檷绾?

### 3.2 鐑棬闂涓庡缓璁帴鍙?

寤鸿鏂板锛?

- `GET /api/v1/family-qa/suggestions?household_id=<id>`

鐢ㄩ€旓細

- 缁欑鐞嗗彴鍜岃闊冲叆鍙ｆ彁渚涘揩鎹烽棶鍙?
- 缂撳瓨瀹跺涵绾ч珮棰戦棶娉?
- 鎶婂彲鍥炵瓟鐨勮寖鍥寸洿鎺ユ毚闇插嚭鏉ワ紝鍑忓皯绌鸿浆

### 3.3 鎻愰啋浠诲姟绠＄悊鎺ュ彛

寤鸿鏂板锛?

- `GET /api/v1/reminders?household_id=<id>`
- `POST /api/v1/reminders`
- `PATCH /api/v1/reminders/{reminder_id}`
- `DELETE /api/v1/reminders/{reminder_id}`

#### 鏍稿績杈撳叆瀛楁

- `household_id`
- `owner_member_id`
- `target_member_ids`
- `reminder_type`锛歚personal|family|medication|course|announcement`
- `schedule_kind`锛歚once|recurring|contextual`
- `schedule_rule`
- `priority`锛歚low|normal|high|urgent`
- `preferred_room_ids`
- `delivery_channels`
- `ack_required`
- `escalation_policy`
- `enabled`

#### 璁捐瑕佺偣

- `schedule_rule` 鍏堟斁 JSON锛屼笉鍋氫竴鍫嗗瓙琛?
- `contextual` 绫诲瀷鎻愰啋鍙互缁戝畾绠€鍗曟潯浠讹紝渚嬪鈥滄垚鍛樺埌瀹跺悗 10 鍒嗛挓鍐呪€?
- 鍒犻櫎浠诲姟涓嶅垹闄ゅ巻鍙茶繍琛岋紝鍙妸閰嶇疆鐘舵€佸叧闂?

### 3.4 鎻愰啋鎬昏銆佹墜鍔ㄨЕ鍙戜笌纭鎺ュ彛

寤鸿鏂板锛?

- `GET /api/v1/reminders/overview?household_id=<id>`
- `POST /api/v1/reminders/{reminder_id}/trigger`
- `POST /api/v1/reminder-runs/{run_id}/ack`

#### `ack` 杈撳叆

```json
{
  "member_id": "uuid",
  "action": "done",
  "channel": "speaker",
  "note": "宸叉湇鑽?
}
```

#### `ack` 璇箟

- `heard`锛氬凡鍚埌锛屼絾鏈畬鎴?
- `done`锛氬凡瀹屾垚
- `dismissed`锛氬拷鐣?
- `delegated`锛氳浆浜ょ粰鍏朵粬鎴愬憳

### 3.5 鍦烘櫙妯℃澘涓庢墜鍔ㄨЕ鍙戞帴鍙?

寤鸿鏂板锛?

- `GET /api/v1/scenes/templates?household_id=<id>`
- `PUT /api/v1/scenes/templates/{template_code}`
- `POST /api/v1/scenes/templates/{template_code}/preview`
- `POST /api/v1/scenes/templates/{template_code}/trigger`

#### 棣栨湡妯℃澘

- `smart_homecoming`
- `child_bedtime`
- `elder_care`

#### `preview` 杈撳嚭閲嶇偣

- 褰撳墠鍛戒腑鐨勮Е鍙戞潯浠?
- 鏈€氳繃鐨勫畧鍗潯浠?
- 璁″垝鎵ц姝ラ
- 闇€瑕佺‘璁ょ殑楂橀闄╁姩浣?

#### `trigger` 璁捐瑕佺偣

- 鎵嬪姩瑙﹀彂鍏佽绠＄悊鍛橀獙璇佸満鏅摼璺?
- 鎵嬪姩瑙﹀彂涔熷繀椤诲啓鍏ュ満鏅墽琛屾棩蹇?
- 鎵嬪姩瑙﹀彂涓嶈兘缁曡繃楂橀闄╁畧鍗?

### 3.6 鍦烘櫙鎵ц鏌ヨ鎺ュ彛

寤鸿鏂板锛?

- `GET /api/v1/scenes/executions?household_id=<id>`
- `GET /api/v1/scenes/executions/{execution_id}`

鐢ㄩ€旓細

- 灞曠ず鏈€杩戞墽琛岃褰?
- 鏌ョ湅姝ラ鎴愬姛/澶辫触璇︽儏
- 杩借釜鍐茬獊璺宠繃銆佸喎鍗存嫤鎴€佸畧鍗懡涓師鍥?

### 3.7 绠＄悊鍙伴〉闈㈣璁?

寤鸿鏂板鏈嶅姟涓績椤甸潰锛?

- 璺敱锛歚/service-center`

椤甸潰鍒嗗洓灞傦細

1. **鏈嶅姟鎬昏 Hero**
   - 褰撳墠瀹跺涵鏈嶅姟鍋ュ悍搴?
   - 浠婃棩鎻愰啋鏁伴噺
   - 鏈€杩戝満鏅墽琛?
   - 闂瓟鍙敤鐘舵€?
2. **闂瓟宸ヤ綔鍙?*
   - 鐑棬闂
   - 杈撳叆妗?
   - 鍥炵瓟缁撴灉
   - 璇佹嵁浜嬪疄鍒楄〃
3. **鎻愰啋涓庡箍鎾潰鏉?*
   - 鎻愰啋鍒楄〃
   - 浠婃棩杩愯鐘舵€?
   - 鎵嬪姩瑙﹀彂
   - 纭/閲嶈瘯/鏆傚仠
4. **鍦烘櫙缂栨帓闈㈡澘**
   - 妯℃澘鍚仠
   - 妯℃澘鍙傛暟瑕嗙洊
   - 棰勮/鎵嬪姩瑙﹀彂
   - 鏈€杩戞墽琛屾棩蹇?

鍚屾椂鍦?`/context-center` 灞曠ず鎽樿鍗★細

- 浠婃棩寰呯‘璁ゆ彁閱?
- 鏈€杩戜竴娆″満鏅墽琛?
- 甯歌闂瓟鍏ュ彛

涓嶈鎶婃墍鏈夌鐞嗘搷浣滈兘濉炶繘 `/context-center`銆傞偅椤甸潰宸茬粡澶熼噸浜嗐€?

---

## 4. 鏁版嵁妯″瀷

### 4.0 AI 渚涘簲鍟嗛厤缃ā鍨?

#### 4.0.1 `AiProviderProfile`

寤鸿琛細`ai_provider_profiles`

瀛楁锛?

- `id`
- `provider_code`
- `display_name`
- `transport_type`锛歚openai_compatible|native_sdk|local_gateway`
- `base_url`
- `api_version`
- `secret_ref`
- `enabled`
- `supported_capabilities_json`
- `privacy_level`锛歚local_only|private_cloud|public_cloud`
- `latency_budget_ms`
- `cost_policy_json`
- `extra_config_json`
- `updated_at`

璇存槑锛?

- `supported_capabilities_json` 鎻忚堪杩欎釜妗ｆ鏀寔鍝簺鑳藉姏
- `secret_ref` 鎸囧悜鐜鍙橀噺鎴栧瘑閽ョ鐞嗗櫒閿悕
- 涓嶄繚瀛樻槑鏂囧瘑閽?

#### 4.0.2 `AiCapabilityRoute`

寤鸿琛細`ai_capability_routes`

瀛楁锛?

- `id`
- `capability`
- `household_id` 鎴?`null`
- `primary_provider_profile_id`
- `fallback_provider_profile_ids_json`
- `routing_mode`
- `timeout_ms`
- `max_retry_count`
- `allow_remote`
- `prompt_policy_json`
- `response_policy_json`
- `enabled`
- `updated_at`

璇存槑锛?

- 鍏佽鍏ㄥ眬榛樿璺敱锛屼篃鍏佽瀹跺涵绾ц鐩?
- `routing_mode` 瀵瑰簲 `template_only / primary_then_fallback / local_only / local_preferred_then_cloud`
- `allow_remote=false` 鏃朵笉鑳芥妸璇锋眰閫佸嚭鏈湴杈圭晫

#### 4.0.3 `AiModelCallLog`

寤鸿琛細`ai_model_call_logs`

瀛楁锛?

- `id`
- `capability`
- `provider_code`
- `model_name`
- `household_id`
- `requester_member_id`
- `trace_id`
- `input_policy`
- `masked_fields_json`
- `latency_ms`
- `usage_json`
- `status`
- `fallback_used`
- `error_code`
- `created_at`

璇存槑锛?

- 涓嶅己琛屼繚瀛樺畬鏁村師濮?prompt 涓庡畬鏁村師濮嬪搷搴?
- 棣栨湡鍙繚鐣欏繀瑕佸璁″厓鏁版嵁銆佽劚鏁忎俊鎭拰寮曠敤
- 濡傞渶淇濆瓨鍘熸枃锛屽繀椤荤粡杩囬澶栭殣绉佸紑鍏虫帶鍒?

### 4.1 `QaFactView`

鐢ㄩ€旓細闂瓟鏃朵复鏃舵嫾瑁呯殑瀹跺涵浜嬪疄瑙嗗浘锛屼笉涓€瀹氳惤搴撱€?

寤鸿瀛楁锛?

- `household_id`
- `generated_at`
- `requester_member_id`
- `active_member`
- `member_states`
- `room_occupancy`
- `device_summary`
- `device_states`
- `reminder_summary`
- `scene_summary`
- `memory_summary`
- `permission_scope`

璇存槑锛?

- 杩欐槸鍥炵瓟鐨勪簨瀹炲簳搴?
- 鍏堟嫾瑁呭啀瑁佸壀锛屼笉瑕佸厛瑁佷竴鍗婂啀鎷硷紝瀹规槗涓俊鎭?

### 4.2 `QaQueryLog`

寤鸿琛細`qa_query_logs`

瀛楁锛?

- `id`
- `household_id`
- `requester_member_id`
- `question`
- `answer_type`
- `answer_summary`
- `confidence`
- `degraded`
- `facts_json`
- `created_at`

璇存槑锛?

- 璁板綍闂瓟璇锋眰涓庣粨鏋滄憳瑕?
- 涓嶅己琛屽瓨鏁存闀垮洖绛斿叏鏂囷紝棣栨湡鍙瓨鎽樿涓庤瘉鎹紩鐢?

### 4.3 `ReminderTask`

寤鸿琛細`reminder_tasks`

瀛楁锛?

- `id`
- `household_id`
- `owner_member_id`
- `title`
- `description`
- `reminder_type`
- `target_member_ids_json`
- `preferred_room_ids_json`
- `schedule_kind`
- `schedule_rule_json`
- `priority`
- `delivery_channels_json`
- `ack_required`
- `escalation_policy_json`
- `enabled`
- `version`
- `updated_by`
- `updated_at`

### 4.4 `ReminderRun`

寤鸿琛細`reminder_runs`

瀛楁锛?

- `id`
- `task_id`
- `household_id`
- `schedule_slot_key`
- `trigger_reason`
- `planned_at`
- `started_at`
- `finished_at`
- `status`锛歚pending|delivering|acked|expired|cancelled|failed`
- `context_snapshot_json`
- `result_summary_json`

璇存槑锛?

- `schedule_slot_key` 鐢ㄤ簬淇濊瘉鍚屼竴妲戒綅骞傜瓑
- `context_snapshot_json` 鐢ㄤ簬浜嬪悗瑙ｉ噴涓轰粈涔堝綋鏃惰繖涔堣Е杈?

### 4.5 `ReminderDeliveryAttempt`

寤鸿琛細`reminder_delivery_attempts`

瀛楁锛?

- `id`
- `run_id`
- `target_member_id`
- `target_room_id`
- `channel`
- `attempt_index`
- `planned_at`
- `sent_at`
- `status`锛歚queued|sent|heard|failed|skipped`
- `provider_result_json`
- `failure_reason`

### 4.6 `ReminderAckEvent`

寤鸿琛細`reminder_ack_events`

瀛楁锛?

- `id`
- `run_id`
- `member_id`
- `action`锛歚heard|done|dismissed|delegated`
- `note`
- `created_at`

### 4.7 `SceneTemplate`

寤鸿琛細`scene_templates`

瀛楁锛?

- `id`
- `household_id`
- `template_code`
- `name`
- `description`
- `enabled`
- `priority`
- `cooldown_seconds`
- `trigger_json`
- `conditions_json`
- `guards_json`
- `actions_json`
- `rollout_policy_json`
- `version`
- `updated_by`
- `updated_at`

璇存槑锛?

- 鍏堢敤鍗曡〃 + JSON锛岄伩鍏嶉鏈熸媶鎴愪竴鍫嗚鍒欏瓙琛?
- 妯℃澘浠ｇ爜鍥哄畾锛屽厑璁告湁闄愬弬鏁拌鐩?

### 4.8 `SceneExecution`

寤鸿琛細`scene_executions`

瀛楁锛?

- `id`
- `template_id`
- `household_id`
- `trigger_key`
- `trigger_source`
- `started_at`
- `finished_at`
- `status`锛歚planned|running|success|partial|skipped|blocked|failed`
- `guard_result_json`
- `conflict_result_json`
- `context_snapshot_json`
- `summary_json`

### 4.9 `SceneExecutionStep`

寤鸿琛細`scene_execution_steps`

瀛楁锛?

- `id`
- `execution_id`
- `step_index`
- `step_type`锛歚reminder|broadcast|device_action|context_update`
- `target_ref`
- `request_json`
- `result_json`
- `status`锛歚planned|success|skipped|failed|blocked`
- `started_at`
- `finished_at`

---

## 5. 姝ｇ‘鎬у睘鎬т笌涓氬姟涓嶅彉閲?

### 5.0 AI 妯″瀷缃戝叧涓嶅彉閲?

1. 涓氬姟妯″潡涓嶅緱鐩存帴渚濊禆鍏蜂綋妯″瀷渚涘簲鍟?SDK锛屾墍鏈夋ā鍨嬭皟鐢ㄩ兘蹇呴』缁忚繃妯″瀷缃戝叧銆?
2. 妯″瀷璺敱蹇呴』鎸夆€滆兘鍔涒€濋厤缃紝鑰屼笉鏄暎钀藉湪涓氬姟浠ｇ爜鏉′欢鍒嗘敮閲屻€?
3. 鏄庢枃瀵嗛挜涓嶅緱杩涘叆涓氬姟鏁版嵁搴擄紱鏁版嵁搴撳彧鑳戒繚瀛樺瘑閽ュ紩鐢ㄣ€?
4. 褰撹兘鍔涜矾鐢卞０鏄?`allow_remote=false` 鎴?`local_only` 鏃讹紝浠讳綍璇锋眰閮戒笉寰楃粫杩囪绛栫暐鍙戝線浜戠銆?
5. 鍚屼竴娆′笟鍔¤姹傝嫢鍙戠敓渚涘簲鍟嗗洖閫€锛屾渶缁堝搷搴斿繀椤昏兘鏍囪瘑涓讳緵搴斿晢澶辫触涓庡洖閫€璺緞銆?

### 5.1 闂瓟涓嶅彉閲?

1. 闂瓟鏄彧璇昏矾寰勶紝涓嶅緱鍋峰伔瑙﹀彂璁惧鍔ㄤ綔銆?
2. 浠讳綍鍥炵瓟閮藉繀椤诲彲鍏宠仈鍒扮粨鏋勫寲浜嬪疄鎴栨樉寮忔帹鏂€?
3. 鏉冮檺瑁佸壀鍙戠敓鍦ㄥ搷搴斿墠锛屼笉鑳藉厛杩斿洖鍐嶅睆钄姐€?
4. 淇℃伅涓嶈冻鏃跺繀椤婚檷绾ф垚鈥滀笉纭畾鈥濓紝涓嶈兘骞绘兂銆?

### 5.2 鎻愰啋璋冨害涓嶅彉閲?

1. 鍚屼竴涓?`ReminderTask + schedule_slot_key` 鏈€澶氬彧鏈変竴涓湁鏁?`ReminderRun`銆?
2. 绂佺敤浠诲姟涓嶅緱鍒涘缓鏂拌繍琛岋紝浣嗗巻鍙茶繍琛屽彲缁х画鏌ヨ銆?
3. 宸茶繃鏈熻繍琛屼笉寰楅噸鏂拌繘鍏ラ€佽揪鐘舵€併€?
4. 璋冨害鍣ㄩ噸鍚悗鍙兘琛ヨЕ鍙戞湭瀹屾垚妲戒綅锛屼笉鑳介噸澶嶈桨鐐搞€?

### 5.3 鎻愰啋纭涓嶅彉閲?

1. 涓€涓?`done` 纭蹇呴』缁撴潫鍚庣画鍗囩骇銆?
2. `dismissed` 涓嶇瓑浜?`done`锛屽繀椤讳繚鐣欒涔夊樊寮傘€?
3. `delegated` 蹇呴』淇濈暀鍘?run锛屼笉閲嶆柊浼€犳柊浠诲姟銆?
4. 纭浜嬩欢蹇呴』鏈夋槑纭垚鍛樻潵婧愭垨绠＄悊鍛樻潵婧愩€?

### 5.4 鍦烘櫙瀹夊叏涓嶅彉閲?

1. 楂橀闄╄澶囧姩浣滀笉鑳借妯℃澘缁曡繃纭銆?
2. 鏁忔劅鎴块棿鍜屽効绔ヤ繚鎶ら檺鍒朵紭鍏堜簬鏅€氬満鏅究鍒╂€с€?
3. 绉佸瘑鎻愰啋涓嶅緱鍦ㄥ叕鍏卞箍鎾腑娉勯湶鍏蜂綋鍐呭銆?
4. 鍦烘櫙鎵ц缁撴灉蹇呴』鍙В閲娾€滀负浠€涔堟墽琛?涓轰粈涔堟病鎵ц鈥濄€?

### 5.5 鍦烘櫙鍐茬獊涓庡喎鍗翠笉鍙橀噺

1. 鍚屼竴 `template_code + trigger_key` 鍦ㄥ喎鍗寸獥鍙ｅ唴涓嶈兘閲嶅鎵ц銆?
2. 鍚屼竴璁惧鍚屼竴鏃跺埢鑻ヨ澶氫釜鍦烘櫙绔炰簤锛屾寜浼樺厛绾т笌瀹堝崼鍐崇瓥鍞竴鎵ц璺緞銆?
3. 鎵嬪姩瑙﹀彂鍙鐩栨櫘閫氳嚜鍔ㄥ満鏅紝浣嗕笉鑳借鐩栭珮椋庨櫓瀹堝崼銆?
4. `partial` 鐘舵€佸繀椤诲寘鍚€愭缁撴灉锛屼笉鑳藉彧缁欎竴涓┖娲炲け璐ョ爜銆?

---

## 6. 閿欒澶勭悊涓庨檷绾?

### 6.0 AI 渚涘簲鍟嗛敊璇鐞?

- `400`锛氳兘鍔涜矾鐢遍厤缃潪娉曘€佷緵搴斿晢鑳藉姏涓嶅尮閰?
- `403`锛氳姹傛暟鎹闅愮绛栫暐闃绘柇锛岀姝㈠彂閫佸埌鐩爣渚涘簲鍟?
- `409`锛氬綋鍓嶈兘鍔涜矾鐢辫绂佺敤鎴栧啿绐?
- `422`锛氱粨鏋勫寲杈撳嚭鏍￠獙澶辫触涓旀棤瀹夊叏闄嶇骇缁撴灉
- `429`锛氫緵搴斿晢闄愭祦
- `502`锛氫緵搴斿晢璋冪敤澶辫触鎴栬繑鍥為潪娉曟暟鎹?
- `504`锛氫緵搴斿晢瓒呮椂

闄嶇骇绛栫暐锛?

- 涓讳緵搴斿晢瓒呮椂 鈫?鍒囧渚涘簲鍟嗘垨妯℃澘鍥炵瓟
- 缁撴瀯鍖栬緭鍑轰笉鍚堟硶 鈫?鍥為€€鍒版ā鏉垮洖绛旀垨鏇翠弗鏍肩殑缁撴瀯鍖栨ā鍨?
- 杩滅鍙楅檺 鈫?闃绘柇骞惰繑鍥炩€滃綋鍓嶇瓥鐣ョ姝娇鐢ㄥ閮ㄦā鍨嬧€?
- 鎴愭湰鎴栭厤棰濊秴闄?鈫?鍒囨湰鍦版ā鏉挎ā寮忓苟鎵撴爣涓洪檷绾?

### 6.1 闂瓟閿欒澶勭悊

- `400`锛氶棶棰樹负绌恒€佷笂涓嬫枃瀛楁闈炴硶
- `403`锛氭棤鏉冮檺璇诲彇鐩爣浜嬪疄
- `422`锛氬綋鍓嶉棶棰樹笉鍦ㄩ鏈熸敮鎸佽寖鍥达紝涓旀棤娉曞畨鍏ㄩ檷绾?
- `503`锛氫簨瀹炶鍥惧叧閿緷璧栦笉鍙敤涓旀棤闄嶇骇鏁版嵁

闄嶇骇绛栫暐锛?

- 璁板繂鎽樿涓嶅彲鐢?鈫?浠呯敤涓婁笅鏂囦笌鎻愰啋浜嬪疄鍥炵瓟
- 璁惧鐘舵€佺己澶?鈫?杩斿洖鈥滃綋鍓嶆棤娉曠‘璁よ澶囩姸鎬佲€?
- 鎻愰啋鏈嶅姟涓嶅彲鐢?鈫?鍙洖绛旈潤鎬佷换鍔￠厤缃紝涓嶅洖绛旀渶鏂版墽琛岀姸鎬?

### 6.2 鎻愰啋閿欒澶勭悊

- `400`锛氳皟搴﹁鍒欐垨鍗囩骇绛栫暐鏍煎紡闈炴硶
- `404`锛氭垚鍛?鎴块棿/浠诲姟涓嶅瓨鍦?
- `409`锛氬悓涓€妲戒綅宸插瓨鍦ㄨ繍琛?
- `422`锛氭彁閱掔洰鏍囦笌瀹跺涵杈圭晫鍐茬獊

闄嶇骇绛栫暐锛?

- 鏌愰€佽揪娓犻亾澶辫触 鈫?鍒囧埌娆′紭娓犻亾鎴栧崌绾х瓥鐣?
- 鎴块棿璺敱澶辫触 鈫?鍥為€€鎴愬憳绾ч粯璁ゆ笭閬?
- 澶栭儴鎾姤涓嶅彲鐢?鈫?璁板綍澶辫触骞朵繚鐣欏緟纭鐘舵€?

### 6.3 鍦烘櫙閿欒澶勭悊

- `400`锛氭ā鏉垮弬鏁伴潪娉曟垨涓嶆敮鎸佽嚜鐢辨墿灞?
- `403`锛氭墜鍔ㄨЕ鍙戣秺鏉?
- `409`锛氬懡涓喎鍗存垨鍐茬獊閿?
- `422`锛氳Е鍙戜笉婊¤冻妯℃澘鏉′欢
- `502`锛氫笅娓歌澶囧姩浣滄墽琛屽け璐?

闄嶇骇绛栫暐锛?

- 璁惧鍔ㄤ綔澶辫触 鈫?鍦烘櫙鍙繘鍏?`partial`
- 骞挎挱澶辫触 鈫?瑙嗕紭鍏堢骇鏀逛负閫氱煡/鏃ュ織鎻愮ず
- 楂橀闄╁姩浣滄湭纭 鈫?鍦烘櫙杩涘叆 `blocked`

### 6.4 鍥炴粴涓庢仮澶嶇瓥鐣?

- 鎻愰啋浠诲姟鏇存柊閲囩敤鐗堟湰鍙凤紝澶辫触鍥炴粴鍒颁笂涓€涓彲鐢ㄧ増鏈?
- 鍦烘櫙妯℃澘鏇存柊澶辫触涓嶅緱褰卞搷褰撳墠宸插惎鐢ㄧ増鏈?
- 璋冨害鍣ㄦ仮澶嶆椂鎸?`schedule_slot_key` 琛ュ伩锛屼笉鎸夆€滅幇鍦ㄦ椂闂村叏閲忚ˉ璺戔€?
- 鎵嬪姩瑙﹀彂澶辫触蹇呴』淇濈暀瀹屾暣澶辫触璁板綍锛屼究浜庡鐩?

---

## 7. 娴嬭瘯绛栫暐

### 7.1 鍗曞厓娴嬭瘯

瑕嗙洊锛?

- AI 鑳藉姏璺敱閫夋嫨涓庡洖閫€
- 璇锋眰鑴辨晱涓庨殣绉侀樆鏂?
- 闂瓟闂鍒嗙被涓庝簨瀹炶鍓?
- 鎻愰啋妲戒綅璁＄畻涓庡箓绛夐敭鐢熸垚
- 鍗囩骇绛栫暐鐘舵€佹祦杞?
- 鍦烘櫙瀹堝崼銆佸喎鍗村拰鍐茬獊鍒ゆ柇

### 7.2 闆嗘垚娴嬭瘯

瑕嗙洊锛?

- `ai gateway` 鈫?provider route 鈫?fallback 鈫?normalized output
- `family-qa/query` 鈫?浜嬪疄缁勮 鈫?鏉冮檺瑁佸壀 鈫?鍥炵瓟杈撳嚭
- `reminder task` 鈫?`reminder run` 鈫?`delivery attempt` 鈫?`ack`
- `scene template` 鈫?`preview` 鈫?`trigger` 鈫?`device-actions`

### 7.3 鍦烘櫙鍥炴斁娴嬭瘯

鑷冲皯鍥炴斁涓夋潯浠ｈ〃閾捐矾锛?

1. 鏅鸿兘鍥炲
2. 鍎跨鐫″墠
3. 鑰佷汉鍏虫€€鎻愰啋

瑕佹眰楠岃瘉锛?

- 瑙﹀彂鏉′欢鏄惁鍑嗙‘
- 瀹堝崼鏄惁鐢熸晥
- 鎵ц鏃ュ織鏄惁瀹屾暣
- 闂瓟鏄惁鑳借拷闂埌缁撴灉

### 7.4 绠＄悊鍙拌仈璋?

鑱旇皟椤甸潰锛?

- `/service-center`
- `/context-center`

鑱旇皟閲嶇偣锛?

- 闂瓟缁撴灉涓庝簨瀹炲紩鐢ㄤ竴鑷?
- 鎻愰啋纭鍚庣姸鎬佸嵆鏃跺埛鏂?
- 鍦烘櫙棰勮涓庣湡瀹炴墽琛岀粨鏋滀竴鑷存€?
- 鎵ц澶辫触鍚庣殑閿欒璇存槑涓庡璁″彲杩借釜

---

## 8. 椋庨櫓涓庡欢鏈熼」

### 8.1 褰撳墠鏄庣‘椋庨櫓

1. `Spec 003` 瀹屾暣璁板繂涓績灏氭湭钀藉湴锛岄棶绛旈鏈熶富瑕佷緷璧栦笂涓嬫枃涓庣粨鏋勫寲鎽樿锛屼笉搴旀壙璇哄叏閲忚蹇嗛棶绛斻€?
2. 鎻愰啋閫佽揪娓犻亾棣栨湡鍙兘鍙湁绠＄悊鍙般€佹棩蹇椾笌闊崇鎾姤鐨勯鏋讹紝鐪熷疄娓犻亾澶氭牱鎬ч渶瑕佸悗缁墿灞曘€?
3. 鍦烘櫙妯℃澘渚濊禆 `Spec 002` 鐨勮澶囧姩浣滃彲鐢ㄦ€т笌涓婁笅鏂囧噯纭€э紝涓婃父鎶栧姩浼氱洿鎺ュ奖鍝嶄綋楠屻€?
4. 澶氫緵搴斿晢妯″瀷杩斿洖椋庢牸銆佺粨鏋勫寲绋冲畾鎬т笌鏃跺欢宸紓寰堝ぇ锛屽鏋滄病鏈夌粺涓€缃戝叧鍜屽己绾︽潫杈撳嚭锛屼笟鍔″眰浼氳繀閫熻姹℃煋銆?
5. 鏈湴妯″瀷涓庝簯妯″瀷鐨勮兘鍔涘樊璺濄€佹垚鏈樊璺濆拰闅愮杈圭晫宸紓鏄庢樉锛屽繀椤荤敱璺敱绛栫暐鏄惧紡澶勭悊锛屼笉鑳介潬浜哄伐绾﹀畾銆?

### 8.2 褰撳墠鏄庣‘寤舵湡

- 閫氱敤鑷敱缂栨帓寮曟搸
- 澶嶆潅澶氳疆闂瓟浠ｇ悊
- 鑷劧璇█鐩存帴鐢熸垚鏂板満鏅?
- 楂樼骇鍋ュ悍寤鸿涓庡尰鐤楃骇瑙ｉ噴
- 璺ㄧ粓绔己涓€鑷存彁閱掑悓姝?
- 瀹屾暣 AI 渚涘簲鍟嗛厤缃墠绔不鐞嗗彴

缁撹寰堢畝鍗曪細鍏堟妸鍙В閲娿€佸彲楠岃瘉銆佸彲瀹¤鐨勫搴湇鍔￠棴鐜仛鍑烘潵锛屽啀璋堟洿鑱槑鐨勪笢瑗裤€?

