# 语言包完全插件化改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `apps/api-server + apps/user-app` 的语言资源彻底收口到真实 `locale-pack` 插件目录、manifest 和资源文件，内置与远端统一插件模型，登录页和首屏也不再读取宿主硬编码文案。

**Architecture:** 后端负责插件 manifest 校验、家庭可见语言注册表和按需资源接口；前端建立一套共享语言插件运行时，用“内置 bundle 解析器 + 远端资源解析器”屏蔽来源差异。`zh-CN`、`en-US`、`zh-TW` 变成真实插件目录，`user-app` 在构建期把这些内置插件资源打进前端包，但运行时仍然只认插件 ID、manifest 和资源版本。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy、Python unittest/pytest、Taro React、TypeScript、Node test、现有 `@familyclaw/user-core` / `@familyclaw/user-ui`

---

## 文件分解

### 后端插件与接口

- Create: `apps/api-server/app/plugins/builtin/locale_zh_cn_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/locale_zh_cn_pack/locales/zh-CN.json`
- Create: `apps/api-server/app/plugins/builtin/locale_en_us_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/locale_en_us_pack/locales/en-US.json`
- Modify: `apps/api-server/app/plugins/builtin/locale_zh_tw_pack/manifest.json`
- Modify: `apps/api-server/app/plugins/builtin/locale_zh_tw_pack/locales/zh-TW.json`
- Modify: `apps/api-server/app/modules/plugin/schemas.py`
- Modify: `apps/api-server/app/modules/plugin/service.py`
- Modify: `apps/api-server/app/api/v1/endpoints/ai_config.py`
- Modify: `apps/api-server/app/modules/plugin/startup_sync_service.py`

### 前端共享运行时

- Create: `apps/user-app/scripts/sync-builtin-locale-plugins.mjs`
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/builtinLocaleBundleIndex.ts`
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/localeResourceClient.ts`
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/localeRuntime.ts`
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/types.ts`
- Modify: `apps/user-app/package.json`
- Modify: `apps/user-app/src/runtime/app-runtime.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/i18n/I18nProvider.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/components/LanguageSwitcher.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.ts`
- Modify: `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.en-US.ts`
- Modify: `apps/user-app/src/runtime/h5-shell/i18n/pageMessageUtils.ts`
- Create: `apps/user-app/src/runtime/rn-shell/i18n/RnI18nProvider.tsx`
- Modify: `apps/user-app/src/runtime/rn-shell/index.ts`

### 共享类型与测试

- Modify: `packages/user-core/src/domain/types.ts`
- Modify: `packages/user-core/src/state/locale.ts`
- Modify: `packages/user-core/src/state/index.ts`
- Modify: `apps/api-server/tests/test_plugin_manifest.py`
- Modify: `apps/api-server/tests/test_plugin_locales_api.py`
- Create: `apps/api-server/tests/test_plugin_locale_resources_api.py`
- Modify: `apps/api-server/tests/test_plugin_startup_sync.py`
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/__tests__/localeRuntime.test.ts`
- Create: `apps/user-app/tsconfig.plugin-locale-tests.json`
- Modify: `docs/开发设计规范/20260318-插件能力与接口规范-v1.md`
- Modify: `specs/004.8.2-语言包完全插件化改造/tasks.md`

## Task 1: 落内置语言插件目录和构建期资源同步

**Files:**
- Create: `apps/api-server/app/plugins/builtin/locale_zh_cn_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/locale_zh_cn_pack/locales/zh-CN.json`
- Create: `apps/api-server/app/plugins/builtin/locale_en_us_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/locale_en_us_pack/locales/en-US.json`
- Modify: `apps/api-server/app/plugins/builtin/locale_zh_tw_pack/manifest.json`
- Modify: `apps/api-server/app/plugins/builtin/locale_zh_tw_pack/locales/zh-TW.json`
- Create: `apps/user-app/scripts/sync-builtin-locale-plugins.mjs`
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/builtinLocaleBundleIndex.ts`
- Modify: `apps/user-app/package.json`
- Test: `apps/api-server/tests/test_plugin_manifest.py`

- [ ] **Step 1: 先补后端 manifest 校验失败用例**

```python
def test_locale_pack_manifest_requires_resource_version_fields() -> None:
    payload = {
        "id": "locale-zh-cn",
        "name": "简体中文语言包",
        "version": "1.0.0",
        "api_version": 1,
        "types": ["locale-pack"],
        "permissions": [],
        "entrypoints": {},
        "capabilities": {},
        "locales": [
            {
                "id": "zh-CN",
                "label": "Simplified Chinese",
                "native_label": "简体中文",
                "resource": "locales/zh-CN.json",
            }
        ],
    }
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(payload)
```

- [ ] **Step 2: 运行测试，确认当前 contract 还不够**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_manifest.py -q`

Expected: FAIL，报 `locale-pack` 缺少新增资源字段或 schema 不匹配。

- [ ] **Step 3: 创建两个新内置插件目录，并把现有 `zh-TW` 插件补齐到同一结构**

```json
{
  "id": "locale-zh-cn",
  "name": "简体中文语言包",
  "version": "1.0.0",
  "api_version": 1,
  "types": ["locale-pack"],
  "permissions": [],
  "entrypoints": {},
  "capabilities": {
    "locale_pack": {
      "bundle_resource": "locales/zh-CN.json",
      "resource_version": "1.0.0",
      "platform_targets": ["h5", "rn"]
    }
  },
  "locales": [
    {
      "id": "zh-CN",
      "label": "Simplified Chinese",
      "native_label": "简体中文",
      "resource": "locales/zh-CN.json"
    }
  ]
}
```

- [ ] **Step 4: 写构建期同步脚本，把内置插件资源映射成前端 bundle 索引**

```js
// apps/user-app/scripts/sync-builtin-locale-plugins.mjs
const index = builtinPlugins.map(plugin => ({
  pluginId: plugin.id,
  localeId: plugin.locale.id,
  resourceVersion: plugin.capabilities.locale_pack.resource_version,
  bundleModule: `./bundles/${plugin.id}/${plugin.locale.id}.json`,
}));
```

- [ ] **Step 5: 让 `user-app` 在 typecheck 前自动刷新 `builtinLocaleBundleIndex.ts`**

Run: `npm --prefix apps/user-app run typecheck`

Expected: PASS，且 `builtinLocaleBundleIndex.ts` 被重新生成。

- [ ] **Step 6: 回跑 manifest 测试**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_manifest.py -q`

Expected: PASS。

- [ ] **Step 7: 提交这一批**

```bash
git add apps/api-server/app/plugins/builtin/locale_zh_cn_pack apps/api-server/app/plugins/builtin/locale_en_us_pack apps/api-server/app/plugins/builtin/locale_zh_tw_pack apps/user-app/scripts/sync-builtin-locale-plugins.mjs apps/user-app/src/runtime/shared/i18n-plugin/builtinLocaleBundleIndex.ts apps/user-app/package.json apps/api-server/tests/test_plugin_manifest.py apps/api-server/app/modules/plugin/schemas.py
git commit -m "feat：004.8.2-落内置语言插件目录与资源索引；"
```

## Task 2: 改后端语言注册表和按需资源接口

**Files:**
- Modify: `apps/api-server/app/modules/plugin/schemas.py`
- Modify: `apps/api-server/app/modules/plugin/service.py`
- Modify: `apps/api-server/app/api/v1/endpoints/ai_config.py`
- Modify: `apps/api-server/tests/test_plugin_locales_api.py`
- Create: `apps/api-server/tests/test_plugin_locale_resources_api.py`

- [ ] **Step 1: 先写 `/locales` 新 contract 和 `/plugin-locales/{plugin_id}/{locale_id}` 新接口的失败用例**

```python
def test_list_household_locales_returns_registry_without_messages(self) -> None:
    response = client.get(f"/api/v1/ai-config/{household_id}/locales")
    payload = response.json()
    assert "messages" not in payload["items"][0]
    assert payload["items"][0]["resource_version"] == "1.0.0"

def test_get_plugin_locale_resource_returns_messages(self) -> None:
    response = client.get(f"/api/v1/ai-config/{household_id}/plugin-locales/locale-zh-cn/zh-CN")
    payload = response.json()
    assert payload["plugin_id"] == "locale-zh-cn"
    assert payload["locale_id"] == "zh-CN"
    assert payload["messages"]["login.title"] == "登录"
```

- [ ] **Step 2: 运行接口测试，确认当前 `/locales` 还是旧返回**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_locales_api.py tests/test_plugin_locale_resources_api.py -q`

Expected: FAIL，`/locales` 仍然内嵌 `messages`，新资源接口不存在。

- [ ] **Step 3: 给 schema 增加注册表 DTO 和资源正文 DTO**

```python
class PluginLocaleRegistryItemRead(BaseModel):
    plugin_id: str
    locale_id: str
    label: str
    native_label: str
    source_type: PluginSourceType
    resource_version: str
    resource_source: Literal["builtin_bundle", "managed_plugin_dir"]
    state: Literal["ready", "disabled", "invalid", "stale"]

class PluginLocaleResourceRead(BaseModel):
    plugin_id: str
    locale_id: str
    resource_version: str
    messages: dict[str, str]
```

- [ ] **Step 4: 把 `list_registered_plugin_locales_for_household` 改成只返回注册表，新增读取单个语言资源正文的方法**

```python
def get_plugin_locale_resource_for_household(...):
    plugin = get_household_plugin(...)
    manifest_dir = Path(plugin.manifest_path).resolve().parent
    resource_path = (manifest_dir / locale_spec.resource).resolve()
    messages = _load_locale_messages_or_log(...)
    return PluginLocaleResourceRead(...)
```

- [ ] **Step 5: 在 `ai_config.py` 暴露新接口，并保持家庭可见性校验**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_locales_api.py tests/test_plugin_locale_resources_api.py -q`

Expected: PASS。

- [ ] **Step 6: 补一条“插件损坏/资源缺失返回明确错误码”的回归测试**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_locales_api.py tests/test_plugin_locale_resources_api.py -q`

Expected: PASS，错误详情包含 `plugin_locale_resource_unavailable` 或同级错误码。

- [ ] **Step 7: 提交这一批**

```bash
git add apps/api-server/app/modules/plugin/schemas.py apps/api-server/app/modules/plugin/service.py apps/api-server/app/api/v1/endpoints/ai_config.py apps/api-server/tests/test_plugin_locales_api.py apps/api-server/tests/test_plugin_locale_resources_api.py
git commit -m "feat：004.8.2-重写语言注册表与资源接口；"
```

## Task 3: 建共享语言插件运行时，取代宿主硬编码消息源

**Files:**
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/types.ts`
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/localeResourceClient.ts`
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/localeRuntime.ts`
- Modify: `apps/user-app/src/runtime/h5-shell/i18n/I18nProvider.tsx`
- Modify: `packages/user-core/src/domain/types.ts`
- Modify: `packages/user-core/src/state/locale.ts`
- Modify: `packages/user-core/src/state/index.ts`
- Create: `apps/user-app/src/runtime/shared/i18n-plugin/__tests__/localeRuntime.test.ts`
- Create: `apps/user-app/tsconfig.plugin-locale-tests.json`
- Modify: `apps/user-app/package.json`

- [ ] **Step 1: 先给共享运行时写失败用例，覆盖“内置优先加载、远端按需拉取、已选插件失效进入待重选”**

```ts
test('uses builtin bundle before household registry is ready', async () => {
  const runtime = createLocaleRuntime({ builtinIndex, fetchRegistry, fetchResource });
  await runtime.bootstrap();
  expect(runtime.getState().activeLocaleId).toBe('zh-CN');
  expect(runtime.t('login.title')).toBe('登录');
});

test('marks selected locale as missing instead of falling back to host messages', async () => {
  const runtime = createLocaleRuntime({ builtinIndex, fetchRegistry, fetchResource });
  await runtime.select('third-party-zh-hk-pack', 'zh-HK');
  runtime.invalidateSelection();
  expect(runtime.getState().status).toBe('missing');
});
```

- [ ] **Step 2: 运行新测试，确认现在还没有共享运行时**

Run: `npm --prefix apps/user-app run test:plugin-locale-runtime`

Expected: FAIL，提示缺少脚本、缺少运行时文件或断言不成立。

- [ ] **Step 3: 在 `user-core` 扩展前端领域类型，去掉“内置语言定义 = 宿主静态消息”这个假设**

```ts
export type PluginLocaleRegistryItem = {
  plugin_id: string;
  locale_id: string;
  resource_version: string;
  resource_source: 'builtin_bundle' | 'managed_plugin_dir';
  state: 'ready' | 'disabled' | 'invalid' | 'stale';
};
```

- [ ] **Step 4: 实现 `localeRuntime.ts`，把内置 bundle 和远端接口统一成一个状态机**

```ts
if (entry.resource_source === 'builtin_bundle') {
  return loadBuiltinLocaleBundle(entry.plugin_id, entry.locale_id);
}
return requestPluginLocaleResource(householdId, entry.plugin_id, entry.locale_id);
```

- [ ] **Step 5: 把 `I18nProvider.tsx` 改成薄封装，不再保留 `SHELL_MESSAGES` / `BUILTIN_MESSAGES` 作为正式源**

```ts
const runtime = useLocaleRuntime();
const t = (key: string, params?: Record<string, string | number>) => runtime.translate(key, params);
```

- [ ] **Step 6: 运行运行时测试和前端 typecheck**

Run: `npm --prefix apps/user-app run test:plugin-locale-runtime`

Expected: PASS。

Run: `npm --prefix apps/user-app run typecheck`

Expected: PASS。

- [ ] **Step 7: 提交这一批**

```bash
git add apps/user-app/src/runtime/shared/i18n-plugin apps/user-app/src/runtime/h5-shell/i18n/I18nProvider.tsx packages/user-core/src/domain/types.ts packages/user-core/src/state/locale.ts packages/user-core/src/state/index.ts apps/user-app/package.json apps/user-app/tsconfig.plugin-locale-tests.json
git commit -m "feat：004.8.2-建立统一语言插件运行时；"
```

## Task 4: 把登录页、H5、RN 一起切到插件语言链路

**Files:**
- Modify: `apps/user-app/src/runtime/app-runtime.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/components/LanguageSwitcher.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.ts`
- Modify: `apps/user-app/src/runtime/h5-shell/i18n/pageMessages.en-US.ts`
- Modify: `apps/user-app/src/runtime/h5-shell/i18n/pageMessageUtils.ts`
- Create: `apps/user-app/src/runtime/rn-shell/i18n/RnI18nProvider.tsx`
- Modify: `apps/user-app/src/runtime/rn-shell/index.ts`
- Test: `apps/user-app/src/runtime/shared/i18n-plugin/__tests__/localeRuntime.test.ts`

- [ ] **Step 1: 先写一条登录页集成失败用例，确认未登录态只读内置插件**

```ts
test('login screen renders builtin locale strings before household bootstrap', async () => {
  render(<H5LoginPage />);
  expect(screen.getByText('登录')).toBeInTheDocument();
});
```

- [ ] **Step 2: 把 `pageMessages*.ts` 中剩余页面文案转存到内置插件 JSON，并清理旧聚合层**

```ts
export const PAGE_MESSAGE_KEYS = [
  'dashboard.title',
  'settings.language.title',
];
```

- [ ] **Step 3: 让 `AppRuntimeProvider` 在登录后刷新家庭注册表，在退出登录后退回内置注册表**

```ts
await localeRuntime.refreshRegistry({ householdId: nextBootstrap.actor.household_id });
await localeRuntime.resetToBuiltin();
```

- [ ] **Step 4: 给 RN 接上同一套 provider 和 `t()` 能力，不允许再各自维护字符串**

Run: `npm --prefix apps/user-app run test:plugin-locale-runtime`

Expected: PASS。

Run: `npm --prefix apps/user-app run build:h5`

Expected: BUILD SUCCESS。

Run: `npm --prefix apps/user-app run build:ios`

Expected: BUILD SUCCESS。

- [ ] **Step 5: 提交这一批**

```bash
git add apps/user-app/src/runtime/app-runtime.tsx apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx apps/user-app/src/runtime/h5-shell/components/LanguageSwitcher.tsx apps/user-app/src/runtime/h5-shell/i18n/pageMessages.ts apps/user-app/src/runtime/h5-shell/i18n/pageMessages.en-US.ts apps/user-app/src/runtime/h5-shell/i18n/pageMessageUtils.ts apps/user-app/src/runtime/rn-shell/i18n/RnI18nProvider.tsx apps/user-app/src/runtime/rn-shell/index.ts
git commit -m "feat：004.8.2-让登录页与双端页面接入语言插件；"
```

## Task 5: 接通安装同步、文档和总验证

**Files:**
- Modify: `apps/api-server/app/modules/plugin/startup_sync_service.py`
- Modify: `apps/api-server/tests/test_plugin_startup_sync.py`
- Modify: `docs/开发设计规范/20260318-插件能力与接口规范-v1.md`
- Modify: `specs/004.8.2-语言包完全插件化改造/tasks.md`

- [ ] **Step 1: 先补远端语言插件安装/升级/卸载后的失败用例**

```python
def test_startup_sync_refreshes_locale_registry_when_marketplace_plugin_changes(self) -> None:
    result = sync_persisted_plugins_on_startup(self.db)
    assert result.marketplace_mount_updated >= 1
```

- [ ] **Step 2: 让 startup sync 在插件变更后刷新语言资源索引和版本**

```python
if manifest.types and "locale-pack" in manifest.types:
    changed_household_ids.add(household_id)
```

- [ ] **Step 3: 同步更新开发规范文档和 spec 任务状态**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_manifest.py tests/test_plugin_locales_api.py tests/test_plugin_locale_resources_api.py tests/test_plugin_startup_sync.py -q`

Expected: PASS。

Run: `npm --prefix apps/user-app run test:plugin-locale-runtime`

Expected: PASS。

Run: `npm --prefix apps/user-app run typecheck`

Expected: PASS。

Run: `npm --prefix apps/user-app run build:h5`

Expected: BUILD SUCCESS。

- [ ] **Step 4: 做最终 diff 回读，确认没有宿主语言 fallback**

Checklist:
- `I18nProvider.tsx` 不再内嵌正式语言消息表
- `locale.ts` 不再内置 canonical message payload
- 登录页和设置页都只通过运行时 `t()` 取文案
- `/locales` 返回注册表，资源正文只由 `/plugin-locales/...` 返回

- [ ] **Step 5: 提交收尾批次**

```bash
git add apps/api-server/app/modules/plugin/startup_sync_service.py apps/api-server/tests/test_plugin_startup_sync.py docs/开发设计规范/20260318-插件能力与接口规范-v1.md specs/004.8.2-语言包完全插件化改造/tasks.md
git commit -m "feat：004.8.2-打通语言插件安装同步与文档；"
```

## 总验证

- [ ] `cd apps/api-server && python -m pytest tests/test_plugin_manifest.py tests/test_plugin_locales_api.py tests/test_plugin_locale_resources_api.py tests/test_plugin_startup_sync.py -q`
- [ ] `npm --prefix apps/user-app run test:plugin-locale-runtime`
- [ ] `npm --prefix apps/user-app run typecheck`
- [ ] `npm --prefix apps/user-app run build:h5`
- [ ] `npm --prefix apps/user-app run build:ios`

## Done / Partial / Skipped

- Done: implementation plan 已覆盖真实插件目录、manifest、资源文件、后端注册表接口、前端双来源运行时、登录页/首屏、安装同步和文档更新。
- Partial: 计划里把 RN provider 和测试入口补进来了，但具体 RN 页面接入点仍需实现时按实际页面树再补一轮文件清单。
- Skipped: 没把第三方签名校验、插件市场商业化、离线资源平台化写进本计划，因为 spec 明确不做。
