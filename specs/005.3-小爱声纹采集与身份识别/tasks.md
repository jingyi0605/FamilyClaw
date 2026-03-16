> 说明：本文件里出现的 SQLite 描述属于历史方案或阶段性验收记录。项目已于 2026-03-16 统一切换到 PostgreSQL，当前实现与测试基线都以 PostgreSQL 为准。

# 浠诲姟娓呭崟 - 灏忕埍澹扮汗閲囬泦涓庤韩浠借瘑鍒紙浜鸿瘽鐗堬級

鐘舵€侊細Draft

## 杩欎唤鏂囨。鏄共浠€涔堢殑

杩欎唤浠诲姟娓呭崟涓嶆槸鎰挎湜鍗曪紝鏄悗闈㈢湡姝ｈ寮€宸ユ椂鐨勬柦宸ュ浘銆傛墦寮€浠绘剰涓€涓换鍔★紝搴旇绔嬪埢鐭ラ亾锛?

- 杩欎竴姝ュ埌搴曞仛浠€涔?
- 鍋氬畬浠ュ悗鑳界湅鍒颁粈涔堢粨鏋?
- 瀹冧緷璧栦粈涔?
- 涓昏鏀瑰摢浜涙枃浠?
- 杩欎竴姝ユ槑纭笉鍋氫粈涔?
- 鎬庝箞楠岃瘉瀹冪湡鍋氬畬浜?

## 鐘舵€佽鏄?

- `TODO`锛氳繕娌″紑濮?
- `IN_PROGRESS`锛氭鍦ㄥ仛
- `BLOCKED`锛氳澶栭儴闂鍗′綇
- `IN_REVIEW`锛氬凡缁忔湁缁撴灉锛岀瓑澶嶆牳
- `DONE`锛氬凡缁忓畬鎴愬苟鍥炲啓鐘舵€?
- `CANCELLED`锛氬彇娑堬紝涓嶅仛浜嗭紝浣嗚鍐欏師鍥?

瑙勫垯锛?

- 鍙湁 `鐘舵€侊細DONE` 鐨勪换鍔℃墠鑳藉嬀鎴?`[x]`
- 姣忓畬鎴愪竴涓换鍔★紝閮借绔嬪埢鍥炲啓杩欓噷
- 濡傛灉浠诲姟杈圭晫鍙樹簡锛屽厛鏀逛换鍔℃弿杩帮紝鍐嶇户缁仛

---

## 闃舵 0锛氬厛鎶婃祴璇曞仛瀹岋紝鍒€ョ潃鍐欎唬鐮?

- [x] 0.1 楠岃瘉 open-xiaoai 鍒?gateway 鐨勯煶棰戦摼璺埌搴曠粰浜嗕粈涔?
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細纭 Rust client 鍙戠殑鏄笉鏄彲鎭㈠鐨勫師濮嬮煶棰戞祦锛屽埆鎶娾€滄湁鏂囨湰鍥炶皟鈥濊褰撴垚鈥滄湁澹扮汗婧愭枃浠垛€濄€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鑳芥槑纭鍑洪摼璺噷鎷垮埌鐨勬槸 `record` 闊抽鍒嗙墖锛屽苟涓旇兘鎭㈠鎴?`.wav / .pcm`銆?
  - 鍏堜緷璧栦粈涔堬細鏃?
  - 寮€濮嬪墠鍏堢湅锛?
    - `open-xiaoai/packages/client-rust/README.md`
    - `open-xiaoai/packages/client-rust/src/bin/client.rs`
    - `open-xiaoai/packages/client-rust/src/services/audio/record.rs`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
  - 涓昏鏀瑰摢閲岋細鏃犱唬鐮佹敼鍔紝鍙ˉ Spec 鏂囨。
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鏀规寮忎笟鍔′唬鐮?
  - 鎬庝箞绠楀畬鎴愶細
    1. 宸茬‘璁?Rust client 鍙戦€?`record` 闊抽娴佸垎鐗囥€?
    2. 宸茬‘璁?gateway 鑳界炕璇戞垚 `audio.append`銆?
    3. 宸茬‘璁ゅ垎鐗囧彲浠ユ仮澶嶆垚鏍囧噯婧愭枃浠躲€?
  - 鎬庝箞楠岃瘉锛?
    - 闊抽鎭㈠娴嬭瘯
    - 鐜版湁 gateway 缈昏瘧娴嬭瘯
  - 瀵瑰簲闇€姹傦細`requirements.md` 闂搁棬 A銆侀渶姹?2
  - 瀵瑰簲璁捐锛歚design.md` 1.4銆?.2

- [x] 0.2 璺戦€氫竴涓彲钀藉湴鐨勫杞０绾瑰缓妗ｆ渶灏忛棴鐜?
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鍏堝埆鎼炲 provider锛屽厛鎵句竴涓湰鍦板彲璺戠殑鍩虹嚎鏂规锛岄獙璇佲€滃杞牱鏈?-> embedding 鑱氬悎 -> 鎼滅储/楠岃瘉鈥濇槸涓嶆槸閫氱殑銆?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鑳芥槑纭煡閬撶涓€鐗堜笉鏄瀻閫夋柟妗堬紝鑰屾槸閫変簡涓€涓凡缁忚窇閫氶棴鐜殑鏂规銆?
  - 鍏堜緷璧栦粈涔堬細0.1
  - 寮€濮嬪墠鍏堢湅锛?
    - `docs/20260315-灏忕埍澹扮汗娴嬭瘯缁撹涓庡紑鍙戦椄闂?md`
  - 涓昏鏀瑰摢閲岋細鏃犱唬鐮佹敼鍔紝鍙ˉ Spec 鏂囨。
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鎺ュ叆姝ｅ紡涓氬姟閾捐矾
  - 鎬庝箞绠楀畬鎴愶細
    1. 宸查€夊畾涓€鏉￠鐗堝０绾瑰熀绾挎柟妗堛€?
    2. 宸查獙璇佸杞牱鏈彲浠ヨ仛鍚堟垚涓€涓彲鎼滅储妗ｆ銆?
  - 鎬庝箞楠岃瘉锛?
    - 鏈湴 ONNX 澹扮汗闂幆娴嬭瘯
  - 瀵瑰簲闇€姹傦細`requirements.md` 闂搁棬 B銆侀渶姹?3
  - 瀵瑰簲璁捐锛歚design.md` 3.1銆?.2

- [x] 0.2.1 鐢ㄥ叕寮€鏍锋湰瀹屾垚 `CAM++` 涓?`ResNet34` 瀵规瘮锛屽苟閿佸畾棣栫増妯″瀷
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鍒啀鍑劅瑙夐€夋ā鍨嬶紝鐩存帴鎷垮叕寮€鏍锋湰鎶婁袱绉嶅€欓€夋ā鍨嬫斁鍒板悓涓€濂楄鍒欓噷瀵规瘮锛岄攣瀹氶鐗堟柟妗堛€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細Spec 閲屼笉鍐嶅啓鈥滄ā鍨嬪緟瀹氣€濓紝鑰屾槸鏄庣‘绗竴鐗堢敤 `ResNet34`銆?
  - 鍏堜緷璧栦粈涔堬細0.2
  - 寮€濮嬪墠鍏堢湅锛?
    - `docs/20260315-灏忕埍澹扮汗娴嬭瘯缁撹涓庡紑鍙戦椄闂?md`
  - 涓昏鏀瑰摢閲岋細鏃犱唬鐮佹敼鍔紝鍙ˉ Spec 鏂囨。
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鍋氱嚎涓?A/B锛屼笉鍋氬妯″瀷鍏卞瓨
  - 鎬庝箞绠楀畬鎴愶細
    1. 宸茬敤鍏紑鏍锋湰瀹屾垚 `CAM++` 涓?`ResNet34` 瀵规瘮銆?
    2. 宸茬‘璁ゅ綋鍓嶇涓€鐗堟寮忛€夌敤 `ResNet34`銆?
  - 鎬庝箞楠岃瘉锛?
    - 鍏紑鏍锋湰鍩哄噯娴嬭瘯
  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?3
  - 瀵瑰簲璁捐锛歚design.md` 1.4銆?.1

- [x] 0.3 娴嬫竻妤?`100ms` 鐨勮竟鐣岋紝涓嶈鍐嶉潬鐚?
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細缁欎笉鍚屾煡璇㈢獥鍙ｈ窇鐪熷疄鏃跺欢锛屾槑纭?`100ms` 鍒板簳鍦ㄥ摢涓尯闂磋繕鑳芥垚绔嬨€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鍚庨潰鍐欓渶姹傛椂涓嶄細鍐嶇┖鍙ｆ壙璇衡€滈粯璁?100ms鈥濄€?
  - 鍏堜緷璧栦粈涔堬細0.2
  - 寮€濮嬪墠鍏堢湅锛?
    - `docs/20260315-灏忕埍澹扮汗娴嬭瘯缁撹涓庡紑鍙戦椄闂?md`
  - 涓昏鏀瑰摢閲岋細鏃犱唬鐮佹敼鍔紝鍙ˉ Spec 鏂囨。
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鍋氭€ц兘浼樺寲瀹炵幇
  - 鎬庝箞绠楀畬鎴愶細
    1. 宸茬粰鍑?`1s / 2s / 3s / 4s` 鏌ヨ绐楀彛鐨勫疄娴嬫椂寤躲€?
    2. 宸插啓娓呮绗竴鐗堝厑璁哥殑绐楀彛鍜岃秴鍑哄悗鐨勫鐞嗘柟寮忋€?
  - 鎬庝箞楠岃瘉锛?
    - 鏈湴鍩哄噯娴嬭瘯
  - 瀵瑰簲闇€姹傦細`requirements.md` 闂搁棬 C銆侀潪鍔熻兘闇€姹?1
  - 瀵瑰簲璁捐锛歚design.md` 3.3銆?.1

- [x] 0.4 鎶婃祴璇曠粨璁哄洖鍐欏埌 Spec锛屽舰鎴愬紑鍙戦椄闂?
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鎶婂凡缁忔祴鍑烘潵鐨勭粨璁烘寮忓啓杩?README銆乺equirements銆乨esign 鍜?docs锛岄槻姝㈠悗闈㈠張鍥炲埌鍙ｅご绾﹀畾銆?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細浠讳綍浜烘嬁鍒?`005.3` 閮界煡閬撯€滃厛娴嬩簡浠€涔堛€佺粨璁烘槸浠€涔堛€佹帴涓嬫潵鎵嶅厑璁稿仛浠€涔堚€濄€?
  - 鍏堜緷璧栦粈涔堬細0.1銆?.2銆?.3
  - 寮€濮嬪墠鍏堢湅锛?
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `docs/README.md`
  - 涓昏鏀瑰摢閲岋細
    - 褰撳墠 Spec 鍏ㄩ儴鏂囨。
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鍏ュ簱涓氬姟瀹炵幇
  - 鎬庝箞绠楀畬鎴愶細
    1. 宸叉柊澧炴祴璇曠粨璁烘枃妗ｃ€?
    2. 宸叉妸鈥滄祴璇曞厛琛屸€濆啓杩涢渶姹傘€佽璁″拰浠诲姟銆?
  - 鎬庝箞楠岃瘉锛?
    - 浜哄伐璧版煡
  - 瀵瑰簲闇€姹傦細`requirements.md` 闂搁棬 A銆侀椄闂?B銆侀椄闂?C
  - 瀵瑰簲璁捐锛歚design.md` 1.4銆?.2銆?.1

---

## 闃舵 1锛氬厛鎶婃暟鎹粨鏋勫拰闊抽浜х墿閾捐矾绔嬩綇

- [x] 1.1 瀹氫箟澹扮汗寤烘。銆佹牱鏈拰妗ｆ鐨勬暟鎹ā鍨?  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鎶婂缓妗ｄ换鍔°€佹垚鍛樺０绾规。妗堛€佸綍闊虫牱鏈笁绫诲璞″缓鎴愭寮?model 鍜?schema锛屽埆鍐嶉潬闆舵暎瀛楁纭噾銆?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鏁版嵁搴撻噷鏈夋竻妤氱殑琛ㄧ粨鏋勶紝鍚庣画寤烘。銆佽瘑鍒€佹竻鐞嗛兘鐭ラ亾璇ユ寕鍦ㄥ摢銆?
  - 鍏堜緷璧栦粈涔堬細0.4
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?1銆侀渶姹?4銆侀渶姹?7
    - `design.md` 4.3銆?.1銆?.2
    - `apps/api-server/migrations/20260311-鏁版嵁搴撹縼绉昏鑼?md`
    - `apps/api-server/app/modules/member/models.py`
  - 涓昏鏀瑰摢閲岋細
    - `apps/api-server/app/modules/voiceprint/`
    - `apps/api-server/migrations/versions/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鎺ュ叆 provider锛屼笉鍏堝仛椤甸潰锛屼笉鍏堝仛璇嗗埆绠楁硶
  - 鎬庝箞绠楀畬鎴愶細
    1. `voiceprint_enrollments / member_voiceprint_profiles / member_voiceprint_samples` 涓夌被瀵硅薄鏈夋寮忔ā鍨嬨€?
    2. 瀵瑰簲 Alembic migration 宸茬粡鍐欏嚭鏉ャ€?
  - 鎬庝箞楠岃瘉锛?    - `alembic upgrade head`
    - 鏂版棫搴撹縼绉绘鏌?  - 鏈疆钀藉疄锛?    - 宸叉柊澧?`voiceprint_enrollments / member_voiceprint_profiles / member_voiceprint_samples` 鐨?model銆乻chema 鍜屾煡璇㈡湇鍔°€?    - 宸茶ˉ榻?Alembic migration `20260315_0036_create_voiceprint_foundation.py`锛屽苟鐢ㄤ复鏃?sqlite 搴撹窇閫?`upgrade head`銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?1銆侀渶姹?4銆侀渶姹?7
  - 瀵瑰簲璁捐锛歚design.md` 4.3銆?.1銆?.2

- [x] 1.2 璁?voice-runtime 鍦?commit 鏃惰惤鍑哄彲瑙ｆ瀽闊抽鏂囦欢
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鎶婄幇鍦ㄥ彧鍦ㄥ唴瀛橀噷鏀掗煶棰戝潡鐨?`voice-runtime` 琛ユ垚姝ｅ紡闊抽浜х墿閾捐矾锛宑ommit 鏃惰兘钀藉嚭 `.wav`锛屽繀瑕佹椂淇濈暀 `.pcm`銆?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細姣忔閲囨牱鎴栧璇?commit 鍚庯紝绯荤粺閮借兘鎷垮埌鏄庣‘鐨勯煶棰戞枃浠跺拰鍏冩暟鎹紝鑰屼笉鏄彧鍓╀竴鍫嗕复鏃跺瓧鑺傘€?
  - 鍏堜緷璧栦粈涔堬細1.1
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?2銆侀渶姹?5銆侀渶姹?7
    - `design.md` 4.2銆?.5.3銆?.3
    - `apps/voice-runtime/voice_runtime/service.py`
    - `apps/voice-runtime/voice_runtime/app.py`
  - 涓昏鏀瑰摢閲岋細
    - `apps/voice-runtime/voice_runtime/service.py`
    - `apps/voice-runtime/voice_runtime/schemas.py`
    - `apps/voice-runtime/voice_runtime/app.py`
    - `apps/voice-runtime/tests/test_app.py`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鍦?runtime 閲屽仛鎴愬憳璇嗗埆锛屼篃涓嶆妸 provider 璋冪敤濉炶繘 runtime
  - 鎬庝箞绠楀畬鎴愶細
    1. commit 杩斿洖閲岃兘鎷垮埌闊抽浜х墿鍏冩暟鎹€?
    2. 钀藉湴鏂囦欢鍙互琚爣鍑嗛煶棰戝簱璇诲嚭鏉ャ€?
  - 鎬庝箞楠岃瘉锛?    - `python -m unittest tests.test_app`
    - 涓存椂鏍锋湰鏂囦欢璇诲彇娴嬭瘯
  - 鏈疆钀藉疄锛?    - `voice-runtime` 宸插湪 `commit` 鏃惰惤 `.wav`锛屽苟杩斿洖 `audio_artifact_id / audio_file_path / sample_rate / channels / sample_width / duration_ms / audio_sha256`銆?    - `api-server` 鐨?runtime client 鍜?pipeline 宸叉帴浣忛煶棰戜骇鐗╁厓鏁版嵁锛岀己澶变骇鐗╂椂鎸夐檷绾ц矾寰勭户缁紝涓嶆墦鏂幇鏈夎闊充富閾俱€?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?2銆侀渶姹?5銆侀渶姹?7
  - 瀵瑰簲璁捐锛歚design.md` 4.2銆?.5.3銆?.3

- [x] 1.3 鎵╁睍 gateway 浼氳瘽鎵撴爣锛屾敮鎸佲€滄櫘閫氬璇濃€濆拰鈥滃缓妗ｉ噰鏍封€濅袱绉嶇敤閫?  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細璁?gateway 鐭ラ亾褰撳墠缁堢鏄惁瀛樺湪寰呭鐞嗗缓妗ｄ换鍔★紝骞舵妸浼氳瘽鐢ㄩ€旀墦鍒颁笂琛屼簨浠堕噷銆?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鍚屼竴鏉″皬鐖卞綍闊抽摼璺紝绯荤粺鑳藉尯鍒嗏€滆繖娆℃槸鏅€氳亰澶┾€濊繕鏄€滆繖娆℃槸缁欐煇涓垚鍛橀噰鏍封€濄€?
  - 鍏堜緷璧栦粈涔堬細1.1銆?.2
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?1銆侀渶姹?2
    - `design.md` 2.4.1銆?.1銆?.5.2
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/bridge.py`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
    - `apps/api-server/app/api/v1/endpoints/devices.py`
  - 涓昏鏀瑰摢閲岋細
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/bridge.py`
    - `apps/open-xiaoai-gateway/open_xiaoai_gateway/translator.py`
    - `apps/api-server/app/api/v1/endpoints/devices.py`
    - `apps/open-xiaoai-gateway/tests/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鍦?gateway 閲屽仛澹扮汗璇嗗埆锛屼笉鍋氭渶缁堟垚鍛樺垽瀹?
  - 鎬庝箞绠楀畬鎴愶細
    1. gateway 鑳芥嬁鍒板緟寤烘。浠诲姟鎽樿銆?
    2. `session.start / audio.commit` 鑳藉尯鍒嗗缓妗ｅ拰鏅€氬璇濄€?
  - 鎬庝箞楠岃瘉锛?    - gateway 鍗曞厓娴嬭瘯
    - 浜嬩欢娴佹柇瑷€娴嬭瘯
  - 鏈疆钀藉疄锛?    - 璁惧 binding 宸茶兘杩斿洖 `pending_voiceprint_enrollment` 鎽樿銆?    - gateway 宸叉敮鎸?`conversation / voiceprint_enrollment` 涓ょ被浼氳瘽鐢ㄩ€旓紝骞跺湪 `session.start / audio.commit` 涓婂甫鍑?`session_purpose` 鍜?`enrollment_id`銆?    - 宸茶ˉ涓婄儹鍒锋柊閫昏緫锛屽湪绾跨粓绔嬁鍒版柊鐨勫緟寤烘。浠诲姟鍚庝細鏇存柊浼氳瘽鎵撴爣锛屼笉闇€瑕侀噸杩炪€?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?1銆侀渶姹?2
  - 瀵瑰簲璁捐锛歚design.md` 2.4.1銆?.1銆?.5.2

### 闃舵妫€鏌?

- [x] 1.4 闃舵妫€鏌ワ細闊抽鏍锋湰鏄笉鏄凡缁忔湁姝ｅ紡钀界偣
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細纭寤烘。閾捐矾鏈€搴曞眰宸茬粡绔欑ǔ锛屽悗闈笉浼氫竴杈规帴 provider 涓€杈硅繕鍦ㄧ寽闊抽鏍锋湰浠庡摢鏉ャ€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鏁版嵁搴撳璞°€侀煶棰戞枃浠跺拰 gateway 浼氳瘽鐢ㄩ€斾笁浠朵簨鑳戒覆璧锋潵銆?
  - 鍏堜緷璧栦粈涔堬細1.1銆?.2銆?.3
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 涓昏鏀瑰摢閲岋細鏈樁娈靛叏閮ㄧ浉鍏虫枃浠?
  - 杩欎竴鍏堜笉鍋氫粈涔堬細涓嶆墿鏂伴渶姹傦紝涓嶆彁鍓嶅仛 UI
  - 鎬庝箞绠楀畬鎴愶細
    1. 鏍锋湰鏂囦欢璺緞鍜屽厓鏁版嵁鑳借姝ｅ紡璁板綍銆?
    2. gateway 宸茶兘姝ｇ‘鏍囪瘑寤烘。浼氳瘽銆?
  - 鎬庝箞楠岃瘉锛?    - 浜哄伐璧版煡
    - 鏍锋湰閾捐矾鍥炴斁娴嬭瘯
  - 鏈疆闃舵缁撹锛?    - 鏁版嵁搴撳熀纭€瀵硅薄銆侀煶棰戞枃浠朵骇鐗╁拰 gateway 浼氳瘽鐢ㄩ€斾笁浠朵簨宸茬粡涓蹭笂浜嗐€?    - 鐜伴樁娈靛凡缁忔弧瓒斥€滃厛鎶婂簳灞傞摼璺珯绋斥€濈殑闂搁棬锛屽彲浠ヨ繘鍏ラ樁娈?2 鍋氭寮忓缓妗?API 鍜屼富娴佺▼涓茶仈銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?1銆侀渶姹?2銆侀渶姹?7
  - 瀵瑰簲璁捐锛歚design.md` 2.4.1銆?.1銆?.2銆?.2

---

## 闃舵 2锛氭妸鎴愬憳澹扮汗寤烘。涓婚摼琛ュ畬鏁?

- [x] 2.1 鏂板 voiceprint 妯″潡鍜屽缓妗ｇ鐞?API
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鎶婂缓妗ｄ换鍔″垱寤恒€佹煡璇€佸彇娑堛€佹煡鐪嬫。妗堣繖浜涙寮忓叆鍙ｈˉ鍑烘潵锛屽埆璁╁悗闈㈣仈璋冭繕闈犺剼鏈‖鎹呮暟鎹簱銆?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細绠＄悊鍛樺彲浠ラ€氳繃姝ｅ紡 API 绠＄悊鎴愬憳寤烘。浠诲姟鍜屽０绾规。妗堛€?
  - 鍏堜緷璧栦粈涔堬細1.4
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?1銆侀渶姹?4銆侀渶姹?7
    - `design.md` 4.3銆?.5.1銆?.5.4
    - `apps/api-server/app/api/v1/endpoints/members.py`
  - 涓昏鏀瑰摢閲岋細
    - `apps/api-server/app/modules/voiceprint/`
    - `apps/api-server/app/api/v1/endpoints/voiceprints.py`
    - `apps/api-server/tests/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉琛ュぇ鑰屽叏鍓嶇椤甸潰
  - 鎬庝箞绠楀畬鎴愶細
    1. 鏈夋寮?API 鍒涘缓鍜屾煡璇㈠缓妗ｄ换鍔°€?
    2. 鏈夋寮?API 鏌ョ湅鍜屽垹闄ゆ垚鍛樺０绾规。妗堛€?
  - 鎬庝箞楠岃瘉锛?    - API 鍗曞厓娴嬭瘯
    - 闆嗘垚娴嬭瘯
  - 鏈疆钀藉疄锛?    - 宸叉柊澧?`POST /api/v1/voiceprints/enrollments`銆乣GET /api/v1/voiceprints/enrollments`銆乣GET /api/v1/voiceprints/enrollments/{enrollment_id}`銆乣POST /api/v1/voiceprints/enrollments/{enrollment_id}/cancel`銆?    - 宸叉柊澧?`GET /api/v1/voiceprints/members/{member_id}` 鍜?`DELETE /api/v1/voiceprints/members/{member_id}`锛屾敮鎸佹煡鐪嬪綋鍓嶆。妗堛€佹牱鏈拰寰呭鐞嗗缓妗ｄ换鍔★紝骞舵敮鎸佸仠鐢ㄦ垚鍛樼幇鏈夊０绾规。妗堛€?    - 宸茶ˉ涓?`voiceprint` API 娴嬭瘯锛岃鐩栭粯璁?3 杞缓妗ｃ€佺粓绔啿绐併€佷换鍔″彇娑堝拰鎴愬憳妗ｆ鍒犻櫎銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?1銆侀渶姹?4銆侀渶姹?7
  - 瀵瑰簲璁捐锛歚design.md` 4.3銆?.5.1銆?.5.4

- [x] 2.2 鎺ュ叆棣栫増澹扮汗閫傞厤灞傦紝鏀寔寤烘。鍜屾洿鏂版。妗?  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鍏堟妸宸茬粡娴嬮€氳繃鐨勬湰鍦板熀绾挎柟妗堟帴杩涙潵锛屾妸鏍锋湰鏂囦欢閫佸幓鍋?embedding锛屽啀淇濆瓨妗ｆ銆?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細绯荤粺涓嶅彧鏄繚瀛樺綍闊筹紝杩樿兘鐪熸鐢熸垚鈥滆繖涓垚鍛樼殑澹扮汗妗ｆ鈥濄€?
  - 鍏堜緷璧栦粈涔堬細2.1
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?3銆侀渶姹?4銆侀渶姹?6
    - `design.md` 3.1銆?.2銆?.2
    - `apps/api-server/app/modules/voice/identity_service.py`
  - 涓昏鏀瑰摢閲岋細
    - `apps/api-server/app/modules/voiceprint/provider.py`
    - `apps/api-server/app/modules/voiceprint/service.py`
    - `apps/api-server/tests/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鎶婂瀹?provider SDK 閫昏緫鏁ｅ埌 gateway 鍜?voice pipeline 閲?
  - 鎬庝箞绠楀畬鎴愶細
    1. 閫傞厤灞傛敮鎸佸缓妗ｃ€佹洿鏂板拰璇嗗埆涓夌被璋冪敤銆?
    2. provider 澶辫触鏃惰兘鏄庣‘鍥炲啓浠诲姟鍜岄敊璇姸鎬併€?
  - 鎬庝箞楠岃瘉锛?    - provider mock 娴嬭瘯
    - 瓒呮椂鍜屽け璐ュ垎鏀祴璇?  - 鏈疆钀藉疄锛?    - 宸叉柊澧?`apps/api-server/app/modules/voiceprint/provider.py`锛岄鐗堝浐瀹氭寜 `sherpa-onnx + weSpeaker/ResNet34` 瀹炵幇鏈湴 ONNX 閫傞厤灞傦紝骞舵妸妯″瀷璺緞銆乹uery window(`1s~2s`) 鍜岄槇鍊煎仛鎴愰厤缃€?    - 宸插湪 `apps/api-server/app/modules/voiceprint/service.py` 钀藉湴澶氳疆鏍锋湰 embedding 鑱氬悎銆乭ousehold 鑼冨洿鍐?search/verify銆佸巻鍙叉牱鏈閲忔洿鏂?profile锛屼互鍙?provider 澶辫触鏃剁殑鏄惧紡鐘舵€佸洖鍐欍€?    - 宸茶ˉ `apps/api-server/tests/test_voiceprint_service.py`锛岃鐩?3 杞缓妗ｈ仛鍚堛€乸rovider 涓嶅彲鐢ㄥけ璐ャ€佹牱鏈枃鏈牎楠屾嫆缁濄€乭ousehold search/verify銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?3銆侀渶姹?4銆侀渶姹?6
  - 瀵瑰簲璁捐锛歚design.md` 3.1銆?.2銆?.2

- [x] 2.3 鎶婂缓妗ｄ换鍔°€佹牱鏈拰妗ｆ鐘舵€佺湡姝ｄ覆璧锋潵
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鎶娾€滃垱寤轰换鍔?-> 閲囧埌鏍锋湰 -> 鏍￠獙鏍锋湰 -> 璋?provider -> 鏇存柊妗ｆ -> 鍥炲啓鐘舵€佲€濅覆鎴愪竴鏉″畬鏁翠富閾俱€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細寤烘。杩欎欢浜嬩笉鍐嶆槸鍗婅矾鏂紑鐨勫涓楠わ紝鑰屾槸涓€鏉″畬鏁村伐浣滄祦銆?
  - 鍏堜緷璧栦粈涔堬細2.2
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?1銆侀渶姹?2銆侀渶姹?4
    - `design.md` 2.4.1銆?.2銆?.2
  - 涓昏鏀瑰摢閲岋細
    - `apps/api-server/app/modules/voiceprint/service.py`
    - `apps/api-server/app/modules/voice/pipeline.py`
    - `apps/api-server/tests/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鍋氭壒閲忓鍏ュ巻鍙查煶棰?
  - 鎬庝箞绠楀畬鎴愶細
    1. 寤烘。浠诲姟鐘舵€佽兘浠?`pending` 璧板埌 `completed/failed`銆?
    2. 鏍锋湰鍜屾。妗堢増鏈兘浜掔浉鍏宠仈銆?
  - 鎬庝箞楠岃瘉锛?    - 寤烘。娴佺▼闆嗘垚娴嬭瘯
    - 澶辫触閲嶈瘯娴嬭瘯
  - 鏈疆钀藉疄锛?    - 宸插湪 `apps/api-server/app/modules/voice/pipeline.py` 澧炲姞 `voiceprint_enrollment` 涓撶敤 commit 鍒嗘敮锛屾櫘閫?`conversation` 璺敱淇濇寔鍘熺姸锛屼笉鐮村潖 Spec 005 / 005.2 鐜版湁涓婚摼銆?    - 宸叉妸 runtime 鍥炴潵鐨?`.wav` 浜х墿鍏冩暟鎹€佽浆鍐欐枃鏈€佹牱鏈牎楠屻€佹牱鏈叆搴撱€乸rofile 鏇存柊鍜?enrollment 鐘舵€佸洖鍐欎覆鎴愪竴鏉℃寮忓悗绔摼璺€?    - 宸茶ˉ `apps/api-server/tests/test_voiceprint_enrollment_pipeline.py`锛岀敤 mocked runtime/provider 璺戦€氫笁杞缓妗ｄ細璇濓紝璇佹槑 enrollment 浼氫粠 `pending` 璧板埌 `completed`锛屽苟鐢熸垚 `member_voiceprint_profiles / member_voiceprint_samples`銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?1銆侀渶姹?2銆侀渶姹?4
  - 瀵瑰簲璁捐锛歚design.md` 2.4.1銆?.2銆?.2

### 闃舵妫€鏌?

- [x] 2.4 闃舵妫€鏌ワ細鎴愬憳澹扮汗鏄笉鏄凡缁忚兘姝ｅ紡寤哄嚭鏉?  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細纭绯荤粺宸茬粡涓嶆槸鈥滀細褰曢煶鈥濓紝鑰屾槸鐪熺殑鈥滀細寤烘。鈥濄€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鎸囧畾鎴愬憳鑳戒骇鍑哄彲杩借釜鐨勫０绾规。妗堬紝澶辫触涔熸湁鏄庣‘鐘舵€併€?
  - 鍏堜緷璧栦粈涔堬細2.1銆?.2銆?.3
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 涓昏鏀瑰摢閲岋細鏈樁娈靛叏閮ㄧ浉鍏虫枃浠?
  - 杩欎竴鍏堜笉鍋氫粈涔堬細涓嶆彁鍓嶅仛瀵硅瘽鍓嶈瘑鍒紭鍖?
  - 鎬庝箞绠楀畬鎴愶細
    1. 鑷冲皯涓€鏉″缓妗ｉ摼璺彲琚嚜鍔ㄥ寲娴嬭瘯璇佹槑鎴愮珛銆?
    2. 鏍锋湰銆佹。妗堛€佷换鍔＄姸鎬佸彲浠ヤ簰鐩歌拷韪€?
  - 鎬庝箞楠岃瘉锛?    - 绔埌绔缓妗ｆ祴璇?    - 浜哄伐璧版煡鐘舵€佽褰?  - 鏈疆闃舵缁撹锛?    - `voiceprint_enrollment` 浼氳瘽宸茬粡鑳戒粠 runtime 闊抽浜х墿涓€璺蛋鍒版牱鏈叆搴撱€乪mbedding 鑱氬悎銆乸rofile 瀹屾垚鍜?enrollment 鐘舵€佸洖鍐欍€?    - 闃舵 2 鐨勮嚜鍔ㄥ寲璇佹槑宸茬粡琛ラ綈锛歚voiceprints_api / voiceprint_service / voiceprint_enrollment_pipeline / voice_pipeline / voice_runtime_client / voice_device_discovery_api` 鐩稿叧娴嬭瘯鍏ㄩ儴閫氳繃锛屽缓妗ｄ富閾炬垚绔嬨€?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?1銆侀渶姹?2銆侀渶姹?4銆侀渶姹?7
  - 瀵瑰簲璁捐锛歚design.md` 2.4.1銆?.3銆?.2

---

## 闃舵 3锛氭妸瀵硅瘽鍓嶈韩浠藉垽瀹氭帴杩涙寮忚闊充富閾?

- [x] 3.1 鍦?voice pipeline 閲屾帴鍏モ€滃厛澹扮汗锛屽悗涓婁笅鏂囧厹搴曗€濈殑韬唤瑙ｆ瀽椤哄簭
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鎶婂璇濆墠韬唤鍒ゅ畾椤哄簭鏀规垚鈥滃厛璇曞０绾硅瘑鍒紝澶辫触鍐嶉€€鍥炵幇鏈変笂涓嬫枃鎺ㄦ柇鈥濓紝骞剁粺涓€浜у嚭涓€浠借韩浠界粨鏋溿€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細绯荤粺涓嶅啀鍙槸闈犳埧闂村拰娲昏穬鎴愬憳鐚滀汉锛岃€屾槸鐪熸鍏堣窇涓€娆″０绾广€?
  - 鍏堜緷璧栦粈涔堬細2.4
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?5銆侀渶姹?6
    - `design.md` 2.4.2銆?.4銆?.3
    - `apps/api-server/app/modules/voice/identity_service.py`
    - `apps/api-server/app/modules/voice/router.py`
    - `apps/api-server/app/modules/voice/pipeline.py`
  - 涓昏鏀瑰摢閲岋細
    - `apps/api-server/app/modules/voice/identity_service.py`
    - `apps/api-server/app/modules/voice/router.py`
    - `apps/api-server/app/modules/voice/pipeline.py`
    - `apps/api-server/tests/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鎼炲璇磋瘽浜鸿瘑鍒?
  - 鎬庝箞绠楀畬鎴愶細
    1. 鏅€氬璇濅細鍏堝皾璇曞０绾硅瘑鍒€?
    2. 鏈€缁堣韩浠界粨鏋滀粛閫氳繃缁熶竴 `VoiceIdentityResolution` 鏆撮湶銆?
  - 鎬庝箞楠岃瘉锛?    - voice pipeline 闆嗘垚娴嬭瘯
    - 浣庣疆淇″害鍥為€€娴嬭瘯
  - 鏈疆钀藉疄锛?    - 宸插湪 `apps/api-server/app/modules/voiceprint/service.py` 琛ラ綈 household 鑼冨洿鍐呯殑鏅€氬璇濆０绾硅瘑鍒妯″瀷锛屾寜鈥滃厛 search锛屽悗 verify鈥濊緭鍑?`matched / conflict / low_confidence / unavailable / no_profile`銆?    - 宸插湪 `apps/api-server/app/modules/voice/identity_service.py` 鍜?`apps/api-server/app/modules/voice/router.py` 鎶婃櫘閫?`conversation` 浼氳瘽鏀规垚浼樺厛璇诲彇鏈 `.wav` 浜х墿鍋氬０绾硅瘑鍒紝鍛戒腑鏃剁洿鎺ョ敤澹扮汗鎴愬憳锛屽け璐ユ椂鍐嶉€€鍥炵幇鏈変笂涓嬫枃鎺ㄦ柇銆?    - 宸茶ˉ `tests.test_voice_identity` 鍜?`tests.test_voice_pipeline`锛岃瘉鏄庢櫘閫氬璇濅細鍏堝皾璇曞０绾硅瘑鍒紝涓旀渶缁堜粛閫氳繃缁熶竴 `VoiceIdentityResolution` 鏆撮湶韬唤缁撴灉銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?5銆侀渶姹?6
  - 瀵瑰簲璁捐锛歚design.md` 2.4.2銆?.4銆?.3

- [x] 3.2 纭繚 LLM 鎱㈣矾寰勪娇鐢ㄥ０绾硅瘑鍒嚭鐨勬垚鍛樿韩浠?  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鎶婅瘑鍒嚭鐨勬垚鍛樼湡姝ｄ紶杩?`conversation` 鎱㈣矾寰勶紝鍒仠鐣欏湪鏃ュ織閲岃嚜鍡ㄣ€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鍚屼竴涓皬鐖遍煶鍝嶏紝涓嶅悓鎴愬憳璇磋瘽鏃讹紝LLM 瀵硅瘽涓婁笅鏂囦細鎸夋垚鍛樿韩浠借蛋銆?
  - 鍏堜緷璧栦粈涔堬細3.1
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?5
    - `design.md` 2.4.2銆?.4
    - `apps/api-server/app/modules/voice/conversation_bridge.py`
  - 涓昏鏀瑰摢閲岋細
    - `apps/api-server/app/modules/voice/conversation_bridge.py`
    - `apps/api-server/tests/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉琛ュ叏閮?persona 绮剧粏鍖栭厤缃?
  - 鎬庝箞绠楀畬鎴愶細
    1. `conversation` 鎱㈣矾寰勮兘鎷垮埌澹扮汗璇嗗埆鍑虹殑鎴愬憳 id銆?
    2. 娌¤瘑鍒嚭鏉ユ椂浠嶈兘鎸夌幇鏈夐€昏緫鍥為€€銆?
  - 鎬庝箞楠岃瘉锛?    - conversation bridge 闆嗘垚娴嬭瘯
    - 璇锋眰韬唤鏂█娴嬭瘯
  - 鏈疆钀藉疄锛?    - 宸茬‘璁?`apps/api-server/app/modules/voice/conversation_bridge.py` 鍦ㄥ垱寤轰細璇濇椂鐩存帴鎶?`identity.primary_member_id` 鍐欒繘 `ConversationSession.requester_member_id`锛屾櫘閫氬璇濇棤闇€鍙﹀紑鏃佽矾銆?    - 宸茶ˉ `tests.test_voice_conversation_bridge` 鍜?`tests.test_voice_pipeline`锛屾柇瑷€鎱㈣矾寰勫垱寤轰細璇濇椂鎷垮埌鐨?`requester_member_id` 灏辨槸澹扮汗璇嗗埆鍑虹殑鎴愬憳 id锛涘０绾规病璇嗗埆鍑烘潵鏃朵粛鎸夌幇鏈夐€昏緫鍥為€€銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?5銆侀渶姹?6
  - 瀵瑰簲璁捐锛歚design.md` 2.4.2銆?.4銆?.2

- [x] 3.3 鍥炲綊蹇矾寰勩€佹潈闄愬拰鐜版湁鐢ㄦ埛绌洪棿
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細纭鍔犱簡澹扮汗璇嗗埆涔嬪悗锛岃澶囨帶鍒跺揩璺緞銆佸尶鍚嶅洖閫€鍜岄粯璁ゅ璇濅富閾鹃兘娌¤鎼炲潖銆?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鏂拌兘鍔涙槸澧炲己椤癸紝涓嶆槸鏂扮偢寮广€?
  - 鍏堜緷璧栦粈涔堬細3.2
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?6
    - `design.md` 2.4.3銆?.2銆?.2
    - `apps/api-server/app/modules/voice/fast_action_service.py`
  - 涓昏鏀瑰摢閲岋細
    - `apps/api-server/tests/`
    - 瑙嗘儏鍐佃ˉ `apps/open-xiaoai-gateway/tests/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鍋氶珮椋庨櫓鎿嶄綔鐨勯澶栫敓鐗╄瘑鍒‘璁?
  - 鎬庝箞绠楀畬鎴愶細
    1. provider 涓嶅彲鐢ㄦ椂鏅€氬璇濊繕鑳界户缁€?
    2. 蹇矾寰勫拰鎱㈣矾寰勮鍙栫殑鏄悓涓€浠借韩浠界粨鏋溿€?
  - 鎬庝箞楠岃瘉锛?    - 闄嶇骇鍥炲綊娴嬭瘯
    - 蹇矾寰勫洖褰掓祴璇?  - 鏈疆钀藉疄锛?    - 宸茶ˉ provider 涓嶅彲鐢ㄣ€佷綆缃俊搴﹀啿绐佸拰涓婁笅鏂囧厹搴曟祴璇曪紝纭澹扮汗澶辫触鏃朵笉浼氳繑鍥炴柊鐨?`agent.error`锛屾櫘閫氬璇濅粛鑳界户缁蛋鐜版湁蹇矾寰勬垨鎱㈣矾寰勩€?    - 宸茶ˉ `tests.test_voiceprint_service`銆乣tests.test_voice_identity`銆乣tests.test_voice_pipeline`锛岃瘉鏄庡揩璺緞鍜屾參璺緞璇诲彇鐨勬槸鍚屼竴浠?`VoiceIdentityResolution`锛屼笉浼氬嚭鐜颁竴杈规寜澹扮汗銆佷竴杈规寜涓婁笅鏂囧悇璺戝悇鐨勩€?    - 宸蹭繚鐣?Spec 005 / 005.2 鐜版湁琛屼负锛歡ateway 鏅€氫細璇濅粛鎵?`conversation` 鏍囪锛寁oice-runtime 浠嶅彧鍋氶煶棰戣惤鐩樺拰鍏冩暟鎹繑鍥烇紝涓嶅仛韬唤鍐崇瓥銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?6
  - 瀵瑰簲璁捐锛歚design.md` 2.4.3銆?.2銆?.2銆?.3

### 闃舵妫€鏌?

- [x] 3.4 闃舵妫€鏌ワ細澹扮汗璇嗗埆鏄笉鏄凡缁忕珯鍒?LLM 鍓嶉潰浜?  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細纭绯荤粺宸茬粡鐪熺殑鍋氬埌鈥滃厛璇嗗埆韬唤锛屽啀杩?LLM鈥濓紝涓嶆槸鍙妸瀛楁濉炶繘鏁版嵁搴撹鏍峰瓙銆?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鎱㈣矾寰勫璇濆墠宸茬粡鏈夋寮忚韩浠界粨鏋滐紝涓斿洖閫€绛栫暐娓呮銆?
  - 鍏堜緷璧栦粈涔堬細3.1銆?.2銆?.3
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 涓昏鏀瑰摢閲岋細鏈樁娈靛叏閮ㄧ浉鍏虫枃浠?
  - 杩欎竴鍏堜笉鍋氫粈涔堬細涓嶈拷鍔犳柊涓氬姟鑳藉姏
  - 鎬庝箞绠楀畬鎴愶細
    1. 瀵硅瘽鍓嶈韩浠借В鏋愰『搴忓凡缁忔敼瀵广€?
    2. 璇嗗埆澶辫触鏃朵笉浼氭墦鏂富閾俱€?
  - 鎬庝箞楠岃瘉锛?    - 绔埌绔璇濆洖褰掓祴璇?    - 浜哄伐璧版煡
  - 鏈疆闃舵缁撹锛?    - 鑷姩鍖栨祴璇曞凡缁忚瘉鏄庢櫘閫氬璇?commit 鍚庝細鍏堝仛 household 鑼冨洿澹扮汗璇嗗埆锛屽啀鎶婄粺涓€韬唤缁撴灉浜ょ粰蹇矾寰?鎱㈣矾寰勶紱鎱㈣矾寰勫垱寤轰細璇濆墠灏卞凡缁忔嬁鍒版寮?`member_id`銆?    - 璇嗗埆澶辫触銆乸rovider 涓嶅彲鐢ㄣ€佷綆缃俊搴﹀拰鍐茬獊璺緞閮借兘绋冲畾闄嶇骇锛屼笉浼氭墦鏂幇鏈夎闊充富閾俱€?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?5銆侀渶姹?6
  - 瀵瑰簲璁捐锛歚design.md` 2.4.2銆?.4.3銆?.4

---

## 闃舵 4锛氳ˉ娴嬭瘯銆佽仈璋冨拰浜ゆ帴鏂囨。

- [x] 4.1 琛ラ綈 gateway銆乿oice-runtime銆乤pi-server 涓夋娴嬭瘯
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鎶婃渶瀹规槗鍥炲綊鐨勪笁娈甸摼璺兘琛ヤ笂娴嬭瘯锛屼笉鐒朵互鍚庤皝涓€鏀硅闊抽摼璺紝澹扮汗鑳藉姏灏变細琚『鎵嬫悶姝汇€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細寤烘。銆侀煶棰戣惤鍦般€佸璇濆墠璇嗗埆鍜岄檷绾у洖閫€閮芥湁鑷姩鍖栦繚鎶ゃ€?
  - 鍏堜緷璧栦粈涔堬細3.4
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 鍏ㄩ儴闇€姹?
    - `design.md` 8.2銆?.3銆?.4
  - 涓昏鏀瑰摢閲岋細
    - `apps/open-xiaoai-gateway/tests/`
    - `apps/voice-runtime/tests/`
    - `apps/api-server/tests/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細鍏堜笉鍋氬疄鏈洪暱鏃堕棿 soak test 鑷姩鍖?
  - 鎬庝箞绠楀畬鎴愶細
    1. 涓夋娴嬭瘯閮借鐩栨垚鍔熴€佸け璐ュ拰闄嶇骇璺緞銆?
    2. 鍏抽敭涓婚摼鏈夊洖褰掍繚鎶ゃ€?
  - 鎬庝箞楠岃瘉锛?    - 鍒嗛」鐩祴璇曡窇閫?  - 鏈疆钀藉疄锛?    - `apps/api-server/tests/` 宸茶ˉ鏅€氬璇濆０绾逛紭鍏堛€佹參璺緞鎴愬憳閫忎紶銆乸rovider 闄嶇骇銆乭ousehold 鍐茬獊鍜屽揩璺緞鍚屾簮韬唤缁撴灉娴嬭瘯銆?    - `apps/open-xiaoai-gateway/tests/test_translator.py` 宸茶ˉ鏅€氬璇濋粯璁や繚鎸?`conversation` 浼氳瘽鐢ㄩ€旂殑鍥炲綊娴嬭瘯锛岄槻姝㈡櫘閫氫細璇濊鎵撴垚寤烘。浼氳瘽銆?    - `apps/voice-runtime/tests/test_app.py` 宸茶ˉ `voiceprint_enrollment` 浜х墿鐩綍鍥炲綊娴嬭瘯锛岀‘璁?runtime 浠嶅彧璐熻矗钀界洏鍜屽厓鏁版嵁锛屼笉鎶婅韩浠藉喅绛栧杩涘幓銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 鍏ㄩ儴闇€姹?  - 瀵瑰簲璁捐锛歚design.md` 8.2銆?.3銆?.4

- [x] 4.2 鍐欒仈璋冨拰楠屾敹鏂囨。
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細鎶婂缓妗ｆ€庝箞璺戙€佹牱鏈€庝箞鐪嬨€佽瘑鍒け璐ユ€庝箞鏌ャ€侀殣绉佹暟鎹€庝箞娓呯悊鍐欐垚鏂囨。锛屽埆璁╁悗闈㈢殑浜虹户缁潬鐚溿€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鍚庣画鎺ユ墜鐨勪汉鐭ラ亾鎬庝箞楠屽缓妗ｃ€佹€庝箞楠岃瘑鍒€佹€庝箞瀹氫綅闂銆?
  - 鍏堜緷璧栦粈涔堬細4.1
  - 寮€濮嬪墠鍏堢湅锛?
    - `requirements.md` 闇€姹?2銆侀渶姹?6銆侀渶姹?7
    - `design.md` 6銆?銆?
    - `specs/005.2-灏忕埍鍘熺敓浼樺厛涓庡墠缂€鎺ョ/docs/`
  - 涓昏鏀瑰摢閲岋細
    - `specs/005.3-灏忕埍澹扮汗閲囬泦涓庤韩浠借瘑鍒?docs/`
  - 杩欎竴鍏堜笉鍋氫粈涔堬細涓嶅啓瀹ｄ紶绋匡紝鍙啓鑳藉共娲荤殑鏂囨。
  - 鎬庝箞绠楀畬鎴愶細
    1. 鑱旇皟姝ラ鍐欐竻妤氥€?
    2. 鏍锋湰鏂囦欢銆佹。妗堢姸鎬佸拰璇嗗埆缁撴灉鐨勬帓鏌ユ柟寮忓啓娓呮銆?
    3. 闅愮娓呯悊瑙勫垯鍐欐竻妤氥€?
  - 鎬庝箞楠岃瘉锛?    - 浜哄伐璧版煡
  - 鏈疆钀藉疄锛?    - 宸叉柊澧?`docs/20260315-鏅€氬璇濆０绾硅瘑鍒仈璋冧笌楠屾敹鎵嬪唽.md`锛屾妸寤烘。鑱旇皟銆佹櫘閫氬璇濊瘑鍒獙鏀躲€侀檷绾у洖閫€銆佹帓鏌ュ叆鍙ｅ拰闅愮娓呯悊瑙勫垯鍐欐垚鍙墽琛屾楠ゃ€?    - 宸叉洿鏂?`docs/README.md`锛屾妸鏅€氬璇濆０绾硅瘑鍒仈璋冩枃妗ｅ姞杩涚洰褰曞叆鍙ｏ紝閬垮厤鍚庣画鎺ユ墜鐨勪汉缁х画闈犵寽銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 闇€姹?2銆侀渶姹?6銆侀渶姹?7
  - 瀵瑰簲璁捐锛歚design.md` 6銆?銆?

- [x] 4.3 鏈€缁堟鏌ョ偣
  - 鐘舵€侊細DONE
  - 杩欎竴姝ュ埌搴曞仛浠€涔堬細纭杩欎唤 Spec 鐪熺殑鎶婅竟鐣屻€佹暟鎹€侀摼璺€佸洖閫€鍜岄獙璇佹柟寮忓啓瀹屾暣浜嗭紝鑰屼笉鏄張鐣欎笅涓€鍫嗗彛澶寸害瀹氥€?
  - 鍋氬畬浣犺兘鐪嬪埌浠€涔堬細鏂扮殑 Codex 涓婁笅鏂囨垨鏂板悓浜嬫嬁鍒拌繖浠?Spec锛岃兘鐩存帴鎺ョ潃骞诧紝涓嶉渶瑕侀噸鏂扮寽鏋舵瀯銆?
  - 鍏堜緷璧栦粈涔堬細4.2
  - 寮€濮嬪墠鍏堢湅锛?
    - `README.md`
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 涓昏鏀瑰摢閲岋細褰撳墠 Spec 鍏ㄩ儴鏂囦欢
  - 杩欎竴鍏堜笉鍋氫粈涔堬細涓嶅啀鎵╅渶姹?
  - 鎬庝箞绠楀畬鎴愶細
    1. 闇€姹傘€佽璁°€佷换鍔¤兘涓€涓€杩借釜銆?
    2. 鏁版嵁缁撴瀯銆佽亴璐ｈ竟鐣屽拰楠岃瘉鏂瑰紡閮芥竻妤氥€?
    3. 鍚庣画鎺ユ墜鐨勪汉鐭ラ亾鍏堝仛浠€涔堛€佹敼鍝噷銆佹€庝箞楠屻€?
  - 鎬庝箞楠岃瘉锛?    - 鎸?Spec 楠屾敹娓呭崟閫愰」鏍稿
  - 鏈疆鏈€缁堢粨璁猴細
    - `README.md / requirements.md / design.md / tasks.md / docs/` 宸叉寜褰撳墠瀹炵幇鍜屾祴璇曠粨鏋滈噸鏂版牳瀵癸紝闃舵 3 鍜岄樁娈?4 鐨勮竟鐣屻€侀摼璺€侀檷绾у拰楠岃瘉鍙ｅ緞娌℃湁浜掔浉鎵撴灦銆?    - 鍚庣画鎺ユ墜鐨勪汉鐜板湪鍙互鐩存帴浠庢枃妗ｅ拰娴嬭瘯杩涘叆锛氬厛鐪?`docs/` 鐭ラ亾鎬庝箞楠岋紝鍐嶇湅 `tests/` 鐭ラ亾涓婚摼淇濇姢鍦ㄥ摢閲岋紝鏈€鍚庢敼 `voiceprint / voice` 鐩稿叧妯″潡銆?  - 瀵瑰簲闇€姹傦細`requirements.md` 鍏ㄩ儴闇€姹?  - 瀵瑰簲璁捐锛歚design.md` 鍏ㄦ枃

