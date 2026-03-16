> 说明：本文件里出现的 SQLite 描述属于历史方案或阶段性验收记录。项目已于 2026-03-16 统一切换到 PostgreSQL，当前实现与测试基线都以 PostgreSQL 为准。

# 璁捐鏂囨。 - 璁惧鎺у埗涓庡灞呮帴鍏ユ彃浠跺寲鏀归€?

鐘舵€侊細Draft

## 1. 姒傝堪

### 1.1 鐩爣

- 鎶婅澶囨帶鍒朵富閾句粠鈥滄牳蹇冪洿鎺ヨ皟鐢?HA鈥濇敼鎴愨€滄牳蹇冪粺涓€鍗忚 + 鎻掍欢鐪熷疄鎵ц鈥?
- 鎶婅澶囨帴鍏ヤ富閾句粠鈥滄牳蹇冪洿鎺ュ悓姝?HA鈥濇敼鎴愨€滄彃浠舵彁渚涘钩鍙版暟鎹?+ 鏍稿績缁熶竴钀藉簱鈥?
- 璁?Home Assistant 鍐呯疆鎻掍欢鐪熸鎺ョ涓婚摼锛岃€屼笉鏄户缁綋鍗犱綅澹?
- 淇濅綇鐜版湁鏉冮檺銆侀珮椋庨櫓纭銆佸璁°€佸満鏅拰璇煶鍏ュ彛锛屼笉璁╄繖浜涢€氱敤瑙勭煩鏁ｈ惤鍒版彃浠堕噷
- 涓哄悗缁骞冲彴骞跺瓨鍋氬噯澶囷紝浣嗕笉鍦ㄨ繖娆℃柟妗堥噷杩囧害璁捐甯傚満銆佸畨瑁呭櫒鍜屾柊骞冲彴瀹炵幇

### 1.2 瑕嗙洊闇€姹?

- `requirements.md` 闇€姹?1
- `requirements.md` 闇€姹?2
- `requirements.md` 闇€姹?3
- `requirements.md` 闇€姹?4
- `requirements.md` 闇€姹?5
- `requirements.md` 闇€姹?6
- `requirements.md` 闇€姹?7

### 1.3 鎶€鏈害鏉?

- 鍚庣锛欶astAPI + SQLAlchemy + Alembic
- 鎻掍欢绯荤粺锛氫紭鍏堝鐢ㄧ幇鏈?`plugin` 妯″潡銆乵anifest銆乪ntrypoint銆佹墽琛屽櫒鍜屼换鍔′綋绯?
- 鏁版嵁瀛樺偍锛氬綋鍓嶅熀绾夸粛鏄?SQLite + Alembic锛屼笉鍋囪宸茬粡鏈変笓闂ㄦ秷鎭€荤嚎
- 鎺ュ彛鍏煎锛氱幇鏈?`device-actions`銆乣devices/sync/ha`銆乣devices/rooms/sync/ha` 绛夊叆鍙ｈ灏介噺淇濇寔澶栭儴璇箟绋冲畾
- 杩佺Щ鍘熷垯锛氬厛璁?HA 璧扮湡鎻掍欢锛屽啀鍒犳牳蹇冮噷鐨?HA 璁惧瀹炵幇灞?
- 璁捐鍘熷垯锛氭牳蹇冧繚鐣欑粺涓€鍗忚鍜岄€氱敤瑙勫垯锛涘钩鍙板疄鐜板繀椤绘斁鎻掍欢锛屼笉鍦ㄦ牳蹇冪户缁啓 `if vendor == xxx`

### 1.4 鏂规缁撹

#### 1.4.1 鏈湴鍒板簳淇濈暀浠€涔?

鏈湴鏍稿績淇濈暀杩欎簺鍐呭锛?

- 缁熶竴鍔ㄤ綔瀹氫箟鍜屽弬鏁?schema
- 璁惧鎺у埗璇锋眰妯″瀷銆佹墽琛岀粨鏋滄ā鍨嬪拰閿欒鐮?
- 鏉冮檺鎺у埗銆侀珮椋庨櫓纭銆佸満鏅紪鎺掋€佸璁℃棩蹇椼€佸箓绛夈€佽秴鏃躲€侀敊璇綊涓€
- 璁惧缁戝畾妯″瀷鍜屾彃浠堕€夋嫨瑙勫垯
- 缁熶竴鎵ц鍣ㄦ帴鍙ｅ拰缁熶竴鍚屾缂栨帓鍣?

#### 1.4.2 鏈湴鏄庣‘涓嶄繚鐣欎粈涔?

鏈湴鏍稿績涓嶅啀淇濈暀杩欎簺鍐呭锛?

- `turn_on -> light.turn_on` 杩欑骞冲彴鍔ㄤ綔鏄犲皠
- `set_temperature -> climate.set_temperature` 杩欑骞冲彴 service 缁勮
- HA registry 鎷夊彇缁嗚妭銆佸钩鍙?SDK 缁嗚妭銆佸巶鍟嗛敊璇粏鑺?
- 閽堝骞冲彴璁惧绫诲瀷鐨勬暎瑁呭疄鐜板垎鏀?

#### 1.4.3 鎻掍欢蹇呴』鎵挎媴浠€涔?

鎻掍欢蹇呴』鎵挎媴涓ょ被鐪熷疄宸ヤ綔锛?

1. **鎺у埗鎵ц**锛氭妸缁熶竴鍔ㄤ綔缈昏瘧鎴愬钩鍙?API 鎴?service call
2. **骞冲彴鎺ュ叆**锛氭妸骞冲彴璁惧銆佸疄浣撱€佹埧闂淬€佽兘鍔涙暣鐞嗘垚缁熶竴鍊欓€夊拰鍚屾缁撴灉

## 2. 鏋舵瀯

### 2.1 绯荤粺缁撴瀯

```mermaid
flowchart LR
    Caller[椤甸潰 / 璇煶 / 瀵硅瘽 / 鍦烘櫙] --> ControlAPI[device_action / devices sync API]
    ControlAPI --> CorePolicy[缁熶竴鍗忚 + 鏉冮檺 + 椋庨櫓鎺у埗 + 瀹¤]
    CorePolicy --> Executor[璁惧鎺у埗鎵ц鍣?/ 鎺ュ叆鍚屾缂栨帓鍣╙
    Executor --> PluginRuntime[plugin runtime]
    PluginRuntime --> HAPlugin[HA 鍐呯疆鎻掍欢]
    PluginRuntime --> FuturePlugin[绫冲 / 娑傞甫绛夋湭鏉ユ彃浠禲
    HAPlugin --> HA[Home Assistant]
    FuturePlugin --> Vendor[鍏朵粬骞冲彴]
    Executor --> Repo[devices / rooms / bindings / audit]
```

涓€鍙ヨ瘽姒傛嫭锛?

> 璋冪敤鏂瑰彧璇粹€滄垜瑕佸仛浠€涔堚€濓紝鏍稿績璐熻矗鈥滆繖浠朵簨鑳戒笉鑳藉仛銆佹€庝箞璁拌处銆佹€庝箞鏀跺彛鈥濓紝鎻掍欢璐熻矗鈥滃埌搴曟€庝箞鍜屽钩鍙拌璇濃€濄€?

### 2.2 妯″潡鑱岃矗

| 妯″潡 | 鑱岃矗 | 杈撳叆 | 杈撳嚭 |
| --- | --- | --- | --- |
| `device_control_protocol` | 瀹氫箟缁熶竴鍔ㄤ綔銆佸弬鏁?schema銆侀闄╃瓑绾с€佹爣鍑嗙粨鏋?| 鍔ㄤ綔鍚嶃€佽澶囩被鍨嬨€佸弬鏁?| 鏍￠獙瑙勫垯銆佸姩浣滃畾涔?|
| `device_control_service` | 缁熶竴鎺у埗涓婚摼锛屽鐞嗘潈闄愩€佸箓绛夈€佸璁°€佹彃浠惰皟搴?| 鎺у埗璇锋眰 | 缁熶竴鎵ц缁撴灉 |
| `device_integration_service` | 缁熶竴鍚屾涓婚摼锛屽鐞嗗€欓€夋煡璇€佸悓姝ユ憳瑕併€佽惤搴?| 鍚屾璇锋眰 | 鍚屾鎽樿銆佺粦瀹氫俊鎭?|
| `device_plugin_router` | 鏍规嵁璁惧缁戝畾鎴栧钩鍙扮被鍨嬮€夋彃浠?| 璁惧銆佺粦瀹氥€佽姹備笂涓嬫枃 | `plugin_id`銆佹墽琛屼笂涓嬫枃 |
| `plugin runtime` | 鎵ц鎻掍欢 entrypoint锛屽鐞嗚繍琛屾椂鍜岃秴鏃?| `PluginExecutionRequest` | 鎻掍欢鍘熷缁撴灉 |
| `homeassistant-device-action` | 鎶婄粺涓€鍔ㄤ綔缈绘垚 HA service call | 鏍囧噯鎺у埗 payload | 骞冲彴鎵ц缁撴灉 |
| `homeassistant-device-sync` | 浠?HA 鎷夎澶囥€佸疄浣撱€佹埧闂村苟杩斿洖鏍囧噯鍚屾 payload | 鍚屾璇锋眰 | 鍊欓€夊垪琛ㄣ€佸悓姝ョ粨鏋?|
| `scene / voice / conversation` | 缁х画鍋氫笂灞傜紪鎺掞紝涓嶇骞冲彴瀹炵幇 | 鏍囧噯鍔ㄤ綔鎴栧満鏅剰鍥?| 鎺у埗璇锋眰 |

### 2.3 鍏抽敭娴佺▼

#### 2.3.1 缁熶竴璁惧鎺у埗娴佺▼

1. 椤甸潰銆佽闊炽€佸満鏅垨瀵硅瘽鍙戣捣缁熶竴鎺у埗璇锋眰銆?
2. `device_control_service` 璇诲彇璁惧銆佸搴€佺粦瀹氫俊鎭€?
3. 鏍稿績鍏堝仛璁惧褰掑睘銆佽澶囧彲鎺ф€с€佸姩浣滄敮鎸併€佸弬鏁版牎楠屽拰楂橀闄╃‘璁ゃ€?
4. `device_plugin_router` 鏍规嵁璁惧缁戝畾瀹氫綅璐熻矗鐨?`plugin_id`銆?
5. 鏍稿績缁勮鏍囧噯鎻掍欢 payload锛屽苟浜ょ粰鎻掍欢 runtime 鎵ц銆?
6. 鎻掍欢鎶婄粺涓€鍔ㄤ綔缈昏瘧鎴愬钩鍙拌皟鐢紝杩斿洖鏍囧噯鎵ц缁撴灉銆?
7. 鏍稿績缁熶竴鍐欏璁°€佹墽琛岀粨鏋滃拰閿欒鏀跺彛锛屽繀瑕佹椂鍥炲啓璁惧蹇収銆?

#### 2.3.2 璁惧鍊欓€夋煡璇㈡祦绋?

1. 椤甸潰璇锋眰鏌愪釜骞冲彴鐨勮澶囧€欓€夊垪琛ㄣ€?
2. `device_integration_service` 閫夋嫨瀵瑰簲鎺ュ叆鎻掍欢銆?
3. 鎻掍欢鎷夊钩鍙拌澶囥€佹埧闂淬€佸疄浣撳拰鑳藉姏锛岃繑鍥炴爣鍑嗗€欓€夐」銆?
4. 鏍稿績琛ヤ笂鏈湴鏄惁宸茬粦瀹氥€佹槸鍚﹀凡鍚屾绛変俊鎭悗杩斿洖鍓嶇銆?

#### 2.3.3 璁惧鍚屾娴佺▼

1. 椤甸潰鍙戣捣鎸夊钩鍙板悓姝ヨ澶囨垨鎴块棿銆?
2. `device_integration_service` 閫氳繃鎻掍欢鎷夊彇骞冲彴瀹屾暣鏁版嵁銆?
3. 鎻掍欢鍙礋璐ｇ粰鍑烘爣鍑嗗悓姝ラ」锛屼笉鐩存帴鍐欐湰鍦版暟鎹簱銆?
4. 鏍稿績缁熶竴鍒涘缓鎴栨洿鏂?`Device`銆乣Room`銆乣DeviceBinding` 鍜屽悓姝ユ憳瑕併€?
5. 鏍稿績璁板綍鍚屾缁撴灉銆佸け璐ュ師鍥犲拰瀹¤鏃ュ織銆?

#### 2.3.4 鍦烘櫙涓庤闊冲鐢ㄦ祦绋?

1. `scene`銆乣voice fast action`銆乣conversation fast action` 缁х画鐢熸垚缁熶竴鍔ㄤ綔璇锋眰銆?
2. 缁熶竴鍔ㄤ綔璇锋眰鍏ㄩ儴璧?`device_control_service`銆?
3. 鏍稿績灞備笉鍏冲績杩欐璇锋眰鏉ヨ嚜鍝潯涓婂眰涓氬姟閾撅紝鍙叧蹇冩槸鍚﹀厑璁告墽琛屽拰鎬庝箞璋冩彃浠躲€?

## 3. 缁勪欢鍜屾帴鍙?

### 3.1 鏍稿績缁勪欢

瑕嗙洊闇€姹傦細1銆?銆?銆?銆?銆?銆?

- `DeviceControlProtocolRegistry`
  - 绠＄悊缁熶竴鍔ㄤ綔瀹氫箟
  - 鎻愪緵鏍囧噯鍙傛暟鏍￠獙鍏ュ彛
- `DeviceControlService`
  - 缁熶竴鎺у埗鎵ц鍏ュ彛
  - 澶勭悊鏉冮檺銆侀珮椋庨櫓纭銆佸箓绛夈€佸璁°€佽秴鏃跺拰閿欒褰掍竴
- `DeviceIntegrationService`
  - 缁熶竴璁惧鍊欓€夈€佽澶囧悓姝ャ€佹埧闂村悓姝ュ叆鍙?
  - 缁熶竴鎶婃彃浠剁粨鏋滆惤鎴愮郴缁熶富鏁版嵁
- `DevicePluginRouter`
  - 鏍规嵁缁戝畾淇℃伅鍜岃姹傜被鍨嬮€夋嫨鎻掍欢
- `DevicePluginPayloadFactory`
  - 缁勮缁欐彃浠剁殑鏍囧噯 payload
- `HomeAssistantActionPlugin`
  - 鐪熷疄瀹炵幇 HA 鎺у埗
- `HomeAssistantSyncPlugin`
  - 鐪熷疄瀹炵幇 HA 鍊欓€夋煡璇㈠拰鍚屾鏁版嵁鎶撳彇

### 3.2 鏁版嵁缁撴瀯

瑕嗙洊闇€姹傦細1銆?銆?銆?銆?銆?

#### 3.2.1 `DeviceActionDefinition`

| 瀛楁 | 绫诲瀷 | 蹇呭～ | 璇存槑 | 绾︽潫 |
| --- | --- | --- | --- | --- |
| `action` | string | 鏄?| 缁熶竴鍔ㄤ綔鍚?| 绋冲畾 id锛屼緥濡?`turn_on` |
| `supported_device_types` | string[] | 鏄?| 鍝簺鏈湴璁惧绫诲瀷鍙敤 | 闈炵┖ |
| `risk_level` | string | 鏄?| `low/medium/high` | 鏈夐檺闆嗗悎 |
| `params_schema` | object | 鏄?| 鏍囧噯鍙傛暟 schema | JSON Schema 椋庢牸鎴栫瓑浠风粨鏋?|
| `required_permissions` | string[] | 鏄?| 鎵€闇€鏉冮檺 | 鍙┖浣嗗瓧娈靛繀椤诲瓨鍦?|
| `idempotent_scope` | string | 鏄?| 骞傜瓑鍒ゆ柇鑼冨洿 | `request/device/action` 绛夊浐瀹氶泦鍚?|

璇存槑锛?

- 杩欏紶瀹氫箟琛ㄥ彲浠ュ厛钀藉湪浠ｇ爜娉ㄥ唽琛ㄩ噷锛屼笉瑕佹眰杩欐鍏堝仛鏁版嵁搴撹〃銆?
- 鍔ㄤ綔鍚嶆槸绯荤粺鍗忚锛屼笉鍏佽鎻掍欢鑷繁鍙戞槑涓€涓彧鍦ㄥ钩鍙伴噷鑳芥噦鐨勫悕瀛楃粰璋冪敤鏂圭敤銆?

#### 3.2.2 `DeviceControlRequest`

| 瀛楁 | 绫诲瀷 | 蹇呭～ | 璇存槑 | 绾︽潫 |
| --- | --- | --- | --- | --- |
| `household_id` | string | 鏄?| 瀹跺涵 id | 闈炵┖ |
| `device_id` | string | 鏄?| 鏈湴璁惧 id | 闈炵┖ |
| `action` | string | 鏄?| 缁熶竴鍔ㄤ綔鍚?| 蹇呴』瀛樺湪浜庡姩浣滄敞鍐岃〃 |
| `params` | object | 鏄?| 鏍囧噯鍙傛暟 | 榛樿涓虹┖瀵硅薄 |
| `reason` | string | 鏄?| 璋冪敤鍘熷洜 | 闈炵┖锛屾渶澶ч暱搴﹀彈鎺?|
| `confirm_high_risk` | bool | 鏄?| 鏄惁宸茬‘璁ら珮椋庨櫓鍔ㄤ綔 | 榛樿 `false` |
| `idempotency_key` | string | 鍚?| 骞傜瓑閿?| 寤鸿鐢变笂灞備紶鍏ユ垨鏍稿績鐢熸垚 |
| `requested_by` | object | 鍚?| 鎿嶄綔浜轰笂涓嬫枃 | 鐢ㄤ簬瀹¤ |

#### 3.2.3 `DeviceControlPluginPayload`

| 瀛楁 | 绫诲瀷 | 蹇呭～ | 璇存槑 | 绾︽潫 |
| --- | --- | --- | --- | --- |
| `schema_version` | string | 鏄?| payload 鐗堟湰 | 鍒濈増 `device-control.v1` |
| `request_id` | string | 鏄?| 涓€娆℃帶鍒惰姹?id | 鍏ㄩ摼璺敮涓€ |
| `household_id` | string | 鏄?| 瀹跺涵 id | 闈炵┖ |
| `plugin_id` | string | 鏄?| 鐩爣鎻掍欢 | 闈炵┖ |
| `binding` | object | 鏄?| 璁惧缁戝畾淇℃伅 | 鑷冲皯鍖呭惈澶栭儴瀵硅薄 id |
| `device_snapshot` | object | 鏄?| 鏈湴璁惧蹇収 | 鑷冲皯鍖呭惈 `device_type`銆乣name` |
| `action` | string | 鏄?| 缁熶竴鍔ㄤ綔鍚?| 闈炵┖ |
| `params` | object | 鏄?| 鏍囧噯鍙傛暟 | 宸查€氳繃鏍稿績鏍￠獙 |
| `timeout_seconds` | number | 鏄?| 骞冲彴鎵ц瓒呮椂 | 姝ｆ暟 |

#### 3.2.4 `DeviceControlPluginResult`

| 瀛楁 | 绫诲瀷 | 蹇呭～ | 璇存槑 | 绾︽潫 |
| --- | --- | --- | --- | --- |
| `success` | bool | 鏄?| 鏄惁鎴愬姛 | 闈炵┖ |
| `platform` | string | 鏄?| 骞冲彴鏍囪瘑 | 濡?`home_assistant` |
| `plugin_id` | string | 鏄?| 鎵ц鎻掍欢 | 闈炵┖ |
| `external_request` | object | 鍚?| 鍙戠粰骞冲彴鐨勬憳瑕?| 涓嶈兘娉勬紡鏁忔劅淇℃伅 |
| `external_response` | object | 鍚?| 骞冲彴杩斿洖鎽樿 | 鍙鍓?|
| `normalized_state_patch` | object | 鍚?| 鍙€夌姸鎬佸洖鍐欏缓璁?| 鍙厑璁告爣鍑嗗瓧娈?|
| `error_code` | string | 鍚?| 骞冲彴閿欒褰掍竴缁撴灉 | 澶辫触鏃跺繀濉?|
| `error_message` | string | 鍚?| 閿欒璇存槑 | 澶辫触鏃跺繀濉?|

#### 3.2.5 `DeviceSyncPluginPayload`

| 瀛楁 | 绫诲瀷 | 蹇呭～ | 璇存槑 | 绾︽潫 |
| --- | --- | --- | --- | --- |
| `schema_version` | string | 鏄?| payload 鐗堟湰 | 鍒濈増 `device-sync.v1` |
| `household_id` | string | 鏄?| 瀹跺涵 id | 闈炵┖ |
| `sync_scope` | string | 鏄?| `devices/rooms` | 鏈夐檺闆嗗悎 |
| `selected_external_ids` | string[] | 鍚?| 鎸囧畾鍚屾瀵硅薄 | 鍙┖ |
| `options` | object | 鏄?| 鍚屾閫夐」 | 宸叉爣鍑嗗寲 |

#### 3.2.6 `DeviceSyncPluginResult`

| 瀛楁 | 绫诲瀷 | 蹇呭～ | 璇存槑 | 绾︽潫 |
| --- | --- | --- | --- | --- |
| `platform` | string | 鏄?| 骞冲彴鏍囪瘑 | 闈炵┖ |
| `plugin_id` | string | 鏄?| 鏉ユ簮鎻掍欢 | 闈炵┖ |
| `device_candidates` | object[] | 鍚?| 鍊欓€夎澶囧垪琛?| 鏍囧噯缁撴瀯 |
| `room_candidates` | object[] | 鍚?| 鍊欓€夋埧闂村垪琛?| 鏍囧噯缁撴瀯 |
| `devices` | object[] | 鍚?| 鏍囧噯鍚屾璁惧椤?| 鏍囧噯缁撴瀯 |
| `rooms` | object[] | 鍚?| 鏍囧噯鍚屾鎴块棿椤?| 鏍囧噯缁撴瀯 |
| `failures` | object[] | 鍚?| 澶辫触椤?| 鑷冲皯鍖呭惈澶栭儴寮曠敤鍜屽師鍥?|

#### 3.2.7 `DeviceBinding` 鎵╁睍

鐜版湁 `DeviceBinding` 闇€瑕佽ˉ瓒虫垨姝ｅ紡浣跨敤杩欎簺璇箟锛?

| 瀛楁 | 褰撳墠鎯呭喌 | 鏈瑕佹眰 |
| --- | --- | --- |
| `platform` | 宸插瓨鍦?| 淇濈暀锛岀敤浜庣矖绮掑害骞冲彴鏍囪瘑 |
| `external_entity_id` | 宸插瓨鍦?| 淇濈暀锛屼綔涓轰富澶栭儴瀵硅薄涔嬩竴 |
| `external_device_id` | 宸插瓨鍦?| 淇濈暀锛屼綔涓哄钩鍙拌澶囩骇 id |
| `capabilities` | 宸插瓨鍦?| 缁х画淇濆瓨鑳藉姏蹇収锛屼絾涓嶅啀鎵胯浇涓嶇ǔ瀹氫复鏃跺瓧娈?|
| `plugin_id` | 缂哄け | 鏂板锛屾槑纭摢涓彃浠惰礋璐ｆ墽琛屽拰鍚屾 |
| `binding_version` | 缂哄け | 鏂板鎴栫瓑浠峰瓧娈碉紝渚夸簬鍚庣画鍏煎鍗囩骇 |

### 3.3 鎺ュ彛濂戠害

瑕嗙洊闇€姹傦細1銆?銆?銆?銆?銆?銆?

#### 3.3.1 缁熶竴璁惧鎺у埗鏈嶅姟鍏ュ彛

- 绫诲瀷锛欶unction / Service
- 璺緞鎴栨爣璇嗭細`device_control_service.execute`
- 杈撳叆锛歚DeviceControlRequest`
- 杈撳嚭锛氱粺涓€鎺у埗鍝嶅簲锛屽寘鍚澶囥€佸姩浣溿€佹墽琛屾彃浠躲€佸钩鍙般€佺粨鏋溿€佹椂闂存埑
- 鏍￠獙锛?
  - 璁惧蹇呴』灞炰簬褰撳墠瀹跺涵
  - 璁惧蹇呴』鍙帶
  - 鍔ㄤ綔蹇呴』瀛樺湪浜庣粺涓€鍔ㄤ綔鍗忚
  - 鍙傛暟蹇呴』閫氳繃鏍囧噯 schema 鏍￠獙
  - 楂橀闄╁姩浣滃繀椤诲厛瀹屾垚纭
- 閿欒锛?
  - `device_not_controllable`
  - `action_not_supported`
  - `plugin_not_available`
  - `high_risk_confirmation_required`
  - `plugin_execution_failed`
  - `plugin_execution_timeout`

#### 3.3.2 缁熶竴璁惧鍊欓€夋煡璇㈠叆鍙?

- 绫诲瀷锛欶unction / Service
- 璺緞鎴栨爣璇嗭細`device_integration_service.list_candidates`
- 杈撳叆锛歚household_id`銆乣plugin_id`銆乣scope`
- 杈撳嚭锛氭爣鍑嗗€欓€夊垪琛?
- 鏍￠獙锛?
  - 鎻掍欢蹇呴』宸叉敞鍐屼笖宸插湪褰撳墠瀹跺涵鍚敤
  - 鎻掍欢蹇呴』澹版槑 `connector` 鑳藉姏
- 閿欒锛?
  - `plugin_not_available`
  - `plugin_type_not_supported`
  - `plugin_execution_failed`

#### 3.3.3 缁熶竴璁惧鍚屾鍏ュ彛

- 绫诲瀷锛欶unction / Service
- 璺緞鎴栨爣璇嗭細`device_integration_service.sync`
- 杈撳叆锛歚DeviceSyncPluginPayload`
- 杈撳嚭锛氱粺涓€鍚屾鎽樿
- 鏍￠獙锛?
  - 鍙厑璁告寚瀹氬钩鍙版彃浠惰繘鍏ュ搴斿悓姝ユ祦绋?
  - 鎻掍欢缁撴灉蹇呴』绗﹀悎鏍囧噯鍚屾缁撴瀯
- 閿欒锛?
  - `plugin_not_available`
  - `plugin_result_invalid`
  - `device_binding_conflict`
  - `room_sync_conflict`

#### 3.3.4 澶栭儴 API 鍏煎绛栫暐

- `POST /api/v1/device-actions/execute`
  - 淇濈暀鐜版湁鍏ュ彛
  - 搴曞眰浠?`device_action.service -> ha_integration.service` 鏀规垚 `device_action.service -> device_control_service -> plugin runtime`
- `POST /api/v1/devices/sync/ha`
  - 绗竴闃舵淇濈暀鏃ц矾寰勶紝鍐呴儴鏀逛负璋冪敤 HA 鎺ュ叆鎻掍欢
  - 绗簩闃舵鍙鍔犳洿閫氱敤鐨?`/devices/integrations/{plugin_id}/sync`
- `GET /api/v1/devices/ha-candidates/{household_id}`
  - 绗竴闃舵淇濈暀鏃ц矾寰勶紝鍐呴儴鏀逛负璋?HA 鎺ュ叆鎻掍欢
- `POST /api/v1/devices/rooms/sync/ha`
  - 绗竴闃舵淇濈暀鏃ц矾寰勶紝鍐呴儴鏀逛负璋?HA 鎺ュ叆鎻掍欢

璇存槑锛?

- 鍏堜繚鍏煎锛屽啀鏀跺彛閫氱敤璺緞锛岃繖鏄负浜嗕笉鎶婄幇鏈夊墠绔拰璇煶閾句竴璧风牳浜嗐€?

### 3.4 鎻掍欢鍗忚

#### 3.4.1 鍔ㄤ綔鎻掍欢 entrypoint 绾﹀畾

- 鍏ュ彛绫诲瀷锛歚action`
- 鍑芥暟绛惧悕锛氭帴鍙楁爣鍑嗘帶鍒?payload锛岃繑鍥炴爣鍑嗘帶鍒剁粨鏋?
- 鎻掍欢鑱岃矗锛?
  - 璇诲彇缁戝畾淇℃伅
  - 鍋氬钩鍙板姩浣滄槧灏?
  - 璋冨钩鍙?API
  - 鎶婂钩鍙伴敊璇炕璇戞垚鏍囧噯閿欒
- 鎻掍欢鏄庣‘涓嶈礋璐ｏ細
  - 鏉冮檺鍒ゆ柇
  - 楂橀闄╃‘璁?
  - 瀹¤鏃ュ織
  - 鍦烘櫙缂栨帓

#### 3.4.2 鎺ュ叆鎻掍欢 entrypoint 绾﹀畾

- 鍏ュ彛绫诲瀷锛歚connector`
- 鍑芥暟绛惧悕锛氭帴鍙楁爣鍑嗗悓姝?payload锛岃繑鍥炴爣鍑嗗悓姝ョ粨鏋?
- 鎻掍欢鑱岃矗锛?
  - 鎷夊钩鍙板€欓€夐」鍜屽畬鏁村悓姝ユ暟鎹?
  - 鏁寸悊骞冲彴璁惧銆佸疄浣撱€佹埧闂淬€佽兘鍔?
  - 杩斿洖鏍囧噯缁撴瀯
- 鎻掍欢鏄庣‘涓嶈礋璐ｏ細
  - 鏈湴鏁版嵁搴撳啓鍏?
  - 鏈湴璁惧 id 鍒嗛厤
  - 瀹¤鏃ュ織

#### 3.4.3 HA 鎻掍欢鎷嗗垎绛栫暐

- `homeassistant-device-action`
  - 璐熻矗鏅€氭帶鍒跺姩浣滐紝渚嬪鐏€佺┖璋冦€佺獥甯樸€侀煶绠?
- `homeassistant-door-lock-action`
  - 鍙互淇濈暀涓洪珮椋庨櫓鍔ㄤ綔涓撶敤鎻掍欢锛屼篃鍙互鍚堝苟杩涙櫘閫?HA 鍔ㄤ綔鎻掍欢
  - 杩欐寤鸿淇濈暀鐙珛鎻掍欢 id锛岄闄╄竟鐣屾洿娓呮
- `homeassistant-device-sync`
  - 璐熻矗鍊欓€夋煡璇€佽澶囧悓姝ャ€佹埧闂村悓姝ャ€佽兘鍔涘揩鐓ф暣鐞?

## 4. 鏁版嵁涓庣姸鎬佹ā鍨?

### 4.1 鏁版嵁鍏崇郴

杩欐瑕佹妸鏁版嵁鍏崇郴鏀规竻妤氾紝涓嶅啀闈犲瓧娈电寽娴嬪钩鍙帮細

- `Device`
  - 琛ㄧず绯荤粺閲岀殑璁惧涓绘暟鎹?
- `DeviceBinding`
  - 琛ㄧず杩欎釜璁惧鐢卞摢涓彃浠躲€佸摢涓钩鍙板璞¤礋璐?
- `PluginRegistryItem / PluginMount / PluginStateOverride`
  - 琛ㄧず鎻掍欢鏄惁瀛樺湪銆佸綋鍓嶅搴槸鍚﹀惎鐢?
- `AuditLog`
  - 璁板綍涓€娆℃帶鍒舵垨鍚屾鍒板簳鏄皝鍙戣捣銆佽蛋浜嗗摢涓彃浠躲€佹垚娌℃垚鍔?

鍏抽敭鍏崇郴锛?

1. 涓€涓?`Device` 鑷冲皯搴旀湁涓€涓寮?`DeviceBinding` 鎵嶈兘鍋氬钩鍙版帶鍒躲€?
2. 涓€涓?`DeviceBinding` 蹇呴』鏄庣‘灞炰簬鏌愪釜 `plugin_id`銆?
3. 涓€娆℃帶鍒惰姹傚繀椤诲厛鎵惧埌 `DeviceBinding.plugin_id`锛屽啀鍐冲畾鎵ц鎻掍欢銆?
4. 涓€娆″悓姝ヨ姹傚厛鎸囧畾骞冲彴鎻掍欢锛屽啀鐢辨牳蹇冨喅瀹氬浣曡惤鏈湴璁惧鍜屾埧闂淬€?

### 4.2 鐘舵€佹祦杞?

#### 4.2.1 鎺у埗鎵ц鐘舵€?

| 鐘舵€?| 鍚箟 | 杩涘叆鏉′欢 | 閫€鍑烘潯浠?|
| --- | --- | --- | --- |
| `received` | 璇锋眰宸茶繘鍏ョ粺涓€鎺у埗涓婚摼 | API 鎴栦笂灞傛湇鍔℃彁浜よ姹?| 瀹屾垚鏍￠獙 |
| `validated` | 宸查€氳繃鏍稿績鏍￠獙 | 鏉冮檺銆佸弬鏁般€侀闄╂牎楠岄€氳繃 | 杩涘叆鎻掍欢鎵ц |
| `running` | 鎻掍欢鎵ц涓?| 宸蹭氦缁欐彃浠?runtime | 鎴愬姛銆佸け璐ユ垨瓒呮椂 |
| `succeeded` | 骞冲彴宸叉墽琛屾垚鍔?| 鎻掍欢杩斿洖鎴愬姛缁撴灉 | 娴佺▼缁撴潫 |
| `failed` | 骞冲彴鎵ц澶辫触鎴栫粨鏋滈潪娉?| 鎻掍欢澶辫触銆佽秴鏃躲€佺粨鏋滀笉鍚堟硶 | 娴佺▼缁撴潫 |
| `blocked` | 鏍稿績绛栫暐闃绘柇 | 鏉冮檺銆侀珮椋庨櫓纭銆佹彃浠跺仠鐢ㄧ瓑闃绘柇 | 娴佺▼缁撴潫 |

#### 4.2.2 璁惧鍚屾鐘舵€?

| 鐘舵€?| 鍚箟 | 杩涘叆鏉′欢 | 閫€鍑烘潯浠?|
| --- | --- | --- | --- |
| `collecting` | 姝ｅ湪鎷夊钩鍙版暟鎹?| 宸叉墽琛屾帴鍏ユ彃浠?| 缁撴灉杩斿洖 |
| `applying` | 姝ｅ湪钀芥湰鍦版ā鍨?| 鎻掍欢缁撴灉鍚堟硶 | 鍏ㄩ儴澶勭悊瀹屾垚 |
| `partial_success` | 鏈夋垚鍔熶篃鏈夊け璐?| 閮ㄥ垎鍚屾椤瑰け璐?| 娴佺▼缁撴潫 |
| `succeeded` | 鍏ㄩ儴鎴愬姛 | 鏃犲け璐ラ」 | 娴佺▼缁撴潫 |
| `failed` | 鎻掍欢鎴栨牳蹇冩暣浣撳け璐?| 鏃犳硶缁х画澶勭悊 | 娴佺▼缁撴潫 |

## 5. 閿欒澶勭悊

### 5.1 閿欒绫诲瀷

- `plugin_not_available`锛氭彃浠朵笉瀛樺湪銆佹湭鍚敤鎴栨湭澹版槑瀵瑰簲鑳藉姏
- `device_binding_missing`锛氳澶囨病鏈夋寮忕粦瀹氫俊鎭?
- `device_binding_conflict`锛氱粦瀹氫俊鎭啿绐佹垨鎸囧悜閿欒鎻掍欢
- `action_not_supported`锛氱粺涓€鍔ㄤ綔涓嶆敮鎸佸綋鍓嶈澶囩被鍨?
- `high_risk_confirmation_required`锛氶珮椋庨櫓鍔ㄤ綔鏈‘璁?
- `plugin_execution_timeout`锛氭彃浠舵垨骞冲彴鎵ц瓒呮椂
- `plugin_execution_failed`锛氭彃浠惰繑鍥炲け璐?
- `plugin_result_invalid`锛氭彃浠惰繑鍥炵粨鏋勪笉鍚堟硶
- `platform_request_failed`锛氬钩鍙版帴鍙ｈ皟鐢ㄥけ璐?
- `sync_apply_failed`锛氭彃浠惰繑鍥炲悎娉曪紝浣嗘湰鍦拌惤搴撳け璐?

### 5.2 閿欒鍝嶅簲鏍煎紡

```json
{
  "detail": "璁惧鎺у埗鎵ц澶辫触锛欻A 鎻掍欢杩斿洖瓒呮椂",
  "error_code": "plugin_execution_timeout",
  "field": "plugin_id",
  "timestamp": "2026-03-15T12:00:00Z"
}
```

### 5.3 澶勭悊绛栫暐

1. 杈撳叆楠岃瘉閿欒锛氭牳蹇冪洿鎺ユ嫆缁濓紝涓嶈繘鍏ユ彃浠舵墽琛屻€?
2. 涓氬姟瑙勫垯閿欒锛氭牳蹇冪洿鎺ラ樆鏂紝骞跺啓鍏ュ璁℃棩蹇椼€?
3. 鎻掍欢鎵ц閿欒锛氭牳蹇冪粺涓€鏀跺彛閿欒鐮侊紝骞惰褰?`plugin_id`銆佸钩鍙板拰澶栭儴璇锋眰鎽樿銆?
4. 骞冲彴閮ㄥ垎澶辫触锛氬悓姝ユ祦绋嬪厑璁搁儴鍒嗘垚鍔燂紝鎺у埗娴佺▼榛樿鏁存澶辫触銆?
5. 閲嶈瘯銆侀檷绾ф垨琛ュ伩锛?
   - 鎺у埗璇锋眰榛樿涓嶈嚜鍔ㄩ噸璇曪紝閬垮厤鐪熷疄璁惧閲嶅鎵ц銆?
   - 鍚屾璇锋眰鍙互鍦ㄤ汉宸ョ‘璁ゅ悗閲嶈瘯銆?
   - 鎻掍欢瓒呮椂蹇呴』鏄庣‘鏍囪锛屼笉鑳藉亣瑁呮垚鍔熴€?

## 6. 姝ｇ‘鎬у睘鎬?

### 6.1 灞炴€?1锛氳皟鐢ㄦ柟涓嶉渶瑕佺煡閬撳钩鍙扮粏鑺?

*瀵逛簬浠讳綍* 璁惧鎺у埗璇锋眰锛岀郴缁熼兘搴旇婊¤冻锛氫笂灞傝皟鐢ㄦ柟鍙兘鐪嬪埌缁熶竴鍔ㄤ綔鍜岀粺涓€缁撴灉锛屼笉鑳戒緷璧栨煇涓钩鍙扮殑 service 鍚嶇О鎴?payload 缁嗚妭銆?

**楠岃瘉闇€姹傦細** `requirements.md` 闇€姹?1銆侀渶姹?7

### 6.2 灞炴€?2锛氬钩鍙板疄鐜颁笉鐣欏湪鏍稿績涓婚摼

*瀵逛簬浠讳綍* 骞冲彴璁惧鎺у埗鎴栧钩鍙板悓姝ユ祦绋嬶紝绯荤粺閮藉簲璇ユ弧瓒筹細鐪熷疄骞冲彴璋冪敤鍙戠敓鍦ㄦ彃浠堕噷锛岃€屼笉鏄牳蹇冩湇鍔＄洿鎺ヨ皟鐢ㄥ钩鍙?SDK 鎴?HTTP API銆?

**楠岃瘉闇€姹傦細** `requirements.md` 闇€姹?2銆侀渶姹?3銆侀渶姹?6

### 6.3 灞炴€?3锛氶珮椋庨櫓鍔ㄤ綔蹇呴』鍏堣繃鏍稿績瑙勫垯

*瀵逛簬浠讳綍* 楂橀闄╁姩浣滆姹傦紝绯荤粺閮藉簲璇ユ弧瓒筹細濡傛灉娌℃湁瀹屾垚鏍稿績纭鍜屾潈闄愬垽鏂紝灏辩粷涓嶈兘杩涘叆鎻掍欢鎵ц銆?

**楠岃瘉闇€姹傦細** `requirements.md` 闇€姹?4

### 6.4 灞炴€?4锛氳澶囧埌鎻掍欢鐨勮矾鐢卞繀椤荤ǔ瀹?

*瀵逛簬浠讳綍* 鍙帶璁惧锛岀郴缁熼兘搴旇婊¤冻锛氬彧瑕佺粦瀹氫俊鎭畬鏁达紝绯荤粺鎬昏兘绋冲畾瀹氫綅璐熻矗瀹冪殑鎻掍欢锛涚粦瀹氱己澶辨椂蹇呴』鏄庣‘澶辫触锛屼笉鑳戒复鏃剁寽骞冲彴銆?

**楠岃瘉闇€姹傦細** `requirements.md` 闇€姹?5

### 6.5 灞炴€?5锛欻A 鍐呯疆鎻掍欢蹇呴』鎵胯浇鐪熷疄涓氬姟

*瀵逛簬浠讳綍* HA 璁惧鎺у埗鎴?HA 璁惧鍚屾璇锋眰锛岀郴缁熼兘搴旇婊¤冻锛氭寮忛摼璺娇鐢ㄧ湡瀹?HA 鎻掍欢鎵ц锛屼笉鍏佽鍐嶈蛋 demo stub 鎴栨牳蹇冪洿杩炴棫閫昏緫銆?

**楠岃瘉闇€姹傦細** `requirements.md` 闇€姹?6

## 7. 娴嬭瘯绛栫暐

### 7.1 鍗曞厓娴嬭瘯

- 缁熶竴鍔ㄤ綔瀹氫箟鍜屽弬鏁版牎楠屾祴璇?
- 楂橀闄╃‘璁ゃ€佹潈闄愭牎楠屻€佸箓绛夐€昏緫娴嬭瘯
- `DevicePluginRouter` 璁惧缁戝畾閫夋彃浠舵祴璇?
- 鎻掍欢 payload 缁勮鍜岀粨鏋滆В鏋愭祴璇?
- HA 鎻掍欢鍔ㄤ綔鏄犲皠銆佸弬鏁版槧灏勩€侀敊璇炕璇戞祴璇?

### 7.2 闆嗘垚娴嬭瘯

- `POST /device-actions/execute` 璧扮粺涓€鎺у埗涓婚摼骞惰皟鐢ㄦ彃浠?
- `voice fast action`銆乣conversation fast action`銆乣scene` 澶嶇敤缁熶竴鎺у埗涓婚摼
- HA 璁惧鍊欓€夋煡璇€佽澶囧悓姝ャ€佹埧闂村悓姝ラ€氳繃鎻掍欢瀹屾垚
- 鎻掍欢鍋滅敤銆佺粦瀹氱己澶便€佽秴鏃躲€佺粨鏋滈潪娉曠瓑寮傚父璺緞娴嬭瘯

### 7.3 绔埌绔祴璇?

- 鐢ㄦ埛绔厤缃?HA 鍚庢煡鐪嬪€欓€夎澶囥€佸悓姝ヨ澶囥€佸悓姝ユ埧闂?
- 鐢ㄦ埛绔垨绠＄悊绔Е鍙戠伅銆佺┖璋冦€侀棬閿佺瓑鍏稿瀷鍔ㄤ綔
- 璇煶蹇矾寰勮Е鍙戣澶囨帶鍒跺苟姝ｇ‘钀藉璁?
- 鍦烘櫙鎵ц瑙﹀彂澶氫釜璁惧鍔ㄤ綔骞舵纭鐢ㄦ彃浠舵墽琛岄摼

### 7.4 楠岃瘉鏄犲皠

| 闇€姹?| 璁捐绔犺妭 | 楠岃瘉鏂瑰紡 |
| --- | --- | --- |
| `requirements.md` 闇€姹?1 | `design.md` 搂2.3.1銆伮?.2.1銆伮?.3.1銆伮?.1 | 鍗曞厓娴嬭瘯 + 鎺у埗鎺ュ彛闆嗘垚娴嬭瘯 |
| `requirements.md` 闇€姹?2 | `design.md` 搂2.3.1銆伮?.4.1銆伮?.1銆伮?.2 | HA 鍔ㄤ綔鎻掍欢娴嬭瘯 + 涓婚摼闆嗘垚娴嬭瘯 |
| `requirements.md` 闇€姹?3 | `design.md` 搂2.3.2銆伮?.3.3銆伮?.4.2銆伮?.2 | 鍊欓€夋煡璇?鍚屾闆嗘垚娴嬭瘯 |
| `requirements.md` 闇€姹?4 | `design.md` 搂2.3.1銆伮?.3銆伮?.3 | 鏉冮檺銆侀珮椋庨櫓銆佸箓绛夋祴璇?|
| `requirements.md` 闇€姹?5 | `design.md` 搂3.2.7銆伮?.1銆伮?.4 | 缁戝畾璺敱娴嬭瘯 |
| `requirements.md` 闇€姹?6 | `design.md` 搂3.4.3銆伮?.5 | 鍐呯疆鎻掍欢鐪熷疄鎵ц閾炬祴璇?|
| `requirements.md` 闇€姹?7 | `design.md` 搂2.3.4銆伮?.3.4 | 璇煶/鍦烘櫙/鏃?API 鍥炲綊娴嬭瘯 |

## 8. 椋庨櫓涓庡緟纭椤?

### 8.1 椋庨櫓

- 鐜版湁 `ha_integration` 閫昏緫姣旇緝鍘氾紝杩佺Щ鏃跺鏄撳嚭鐜版柊鏃у弻杞ㄥ叡瀛樺お涔呯殑闂銆?
- 鐜版湁鎻掍欢 `action` / `connector` 鎺ュ彛鍋忛€氱敤锛岃惤璁惧鍗忚鏃跺鏋?payload 璁捐澶澗锛屽悗闈㈣繕浼氬洖鍒扳€滃ぇ瀹跺悇鐜╁悇鐨勨€濄€?
- `DeviceBinding` 澧炲瓧娈典細褰卞搷鍘嗗彶鏁版嵁锛岄渶瑕佽縼绉昏剼鏈拰鍥炲～绛栫暐銆?
- 璁惧鎺у埗榛樿涓嶈嚜鍔ㄩ噸璇曟槸瀵圭殑锛屼絾涓氬姟渚у彲鑳戒細璇互涓衡€滆秴鏃跺氨璇ヨ嚜鍔ㄥ啀鍙戜竴娆♀€濓紝闇€瑕佹槑纭害鏉熴€?

### 8.2 寰呯‘璁ら」

- `homeassistant-door-lock-action` 鏄户缁嫭绔嬩繚鐣欙紝杩樻槸鍚堝苟杩?`homeassistant-device-action`銆傛湰璁捐榛樿淇濈暀鐙珛鎻掍欢銆?
- 閫氱敤 API 鏄惁鍦ㄧ涓€闃舵灏辨柊澧?`/devices/integrations/{plugin_id}/sync`锛岃繕鏄厛鍙仛鍐呴儴鏀跺彛銆佸澶栦繚鐣?HA 璺緞銆傚綋鍓嶅缓璁厛淇濆吋瀹广€?
- 骞傜瓑閿槸鍚﹁姹傛墍鏈変笂灞傝皟鐢ㄦ柟閮芥樉寮忎紶鍏ワ紝杩樻槸鍏堢敱鏍稿績鍦ㄧ己鐪佹椂鑷姩鐢熸垚銆傚綋鍓嶅缓璁€滄敮鎸佹樉寮忎紶鍏ワ紝缂虹渷鑷姩鐢熸垚鈥濄€?

