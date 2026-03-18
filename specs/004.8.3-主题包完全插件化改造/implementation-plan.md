# 主题包完全插件化改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `apps/api-server + apps/user-app` 的主题资源彻底收口到真实 `theme-pack` 插件目录、manifest 和 token 资源文件，内置与远端统一插件模型，H5/RN/登录页都不再读取宿主静态主题表。

**Architecture:** 后端停止生成虚拟主题插件，改为扫描真实 `theme-pack` 目录并输出主题注册表、按需 token 资源接口；前端建立一套共享主题插件运行时，让 H5 只负责把 token 映射成 CSS 变量，RN 只负责把同一份 token 映射成 RN 语义 token。8 套默认主题变成真实插件目录，构建期同步进 `user-app` bundle，运行时仍然只认插件 ID、manifest 和资源版本。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy、Python unittest/pytest、Taro React、TypeScript、Node test、现有 `@familyclaw/user-core` / `@familyclaw/user-ui`

---

## 文件分解

### 后端插件与接口

- Create: `apps/api-server/app/plugins/builtin/theme_chun_he_jing_ming_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_chun_he_jing_ming_pack/themes/chun-he-jing-ming.json`
- Create: `apps/api-server/app/plugins/builtin/theme_yue_lang_xing_xi_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_yue_lang_xing_xi_pack/themes/yue-lang-xing-xi.json`
- Create: `apps/api-server/app/plugins/builtin/theme_ming_cha_qiu_hao_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_ming_cha_qiu_hao_pack/themes/ming-cha-qiu-hao.json`
- Create: `apps/api-server/app/plugins/builtin/theme_wan_zi_qian_hong_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_wan_zi_qian_hong_pack/themes/wan-zi-qian-hong.json`
- Create: `apps/api-server/app/plugins/builtin/theme_feng_chi_dian_che_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_feng_chi_dian_che_pack/themes/feng-chi-dian-che.json`
- Create: `apps/api-server/app/plugins/builtin/theme_xing_he_wan_li_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_xing_he_wan_li_pack/themes/xing-he-wan-li.json`
- Create: `apps/api-server/app/plugins/builtin/theme_qing_shan_lv_shui_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_qing_shan_lv_shui_pack/themes/qing-shan-lv-shui.json`
- Create: `apps/api-server/app/plugins/builtin/theme_jin_xiu_qian_cheng_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_jin_xiu_qian_cheng_pack/themes/jin-xiu-qian-cheng.json`
- Modify: `apps/api-server/app/modules/plugin/schemas.py`
- Modify: `apps/api-server/app/modules/plugin/service.py`
- Modify: `apps/api-server/app/modules/plugin/theme_registry.py`
- Modify: `apps/api-server/app/api/v1/endpoints/ai_config.py`
- Modify: `apps/api-server/app/modules/plugin/startup_sync_service.py`

### 前端共享运行时

- Create: `apps/user-app/scripts/sync-builtin-theme-plugins.mjs`
- Create: `apps/user-app/src/runtime/shared/theme-plugin/builtinThemeBundleIndex.ts`
- Create: `apps/user-app/src/runtime/shared/theme-plugin/themeResourceClient.ts`
- Create: `apps/user-app/src/runtime/shared/theme-plugin/themeRuntime.ts`
- Create: `apps/user-app/src/runtime/shared/theme-plugin/types.ts`
- Modify: `apps/user-app/package.json`
- Modify: `apps/user-app/src/runtime/app-runtime.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/theme/ThemeProvider.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/theme/applyThemeDocument.ts`
- Modify: `apps/user-app/src/runtime/h5-shell/components/ThemeSwitcher.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
- Modify: `apps/user-app/src/runtime/rn-shell/tokens.ts`
- Create: `apps/user-app/src/runtime/rn-shell/theme/RnThemeProvider.tsx`
- Modify: `apps/user-app/src/runtime/rn-shell/index.ts`

### 共享类型与测试

- Modify: `packages/user-core/src/domain/types.ts`
- Modify: `packages/user-core/src/state/theme.ts`
- Modify: `packages/user-core/src/state/index.ts`
- Modify: `packages/user-ui/src/theme/themes.ts`
- Modify: `apps/api-server/tests/test_plugin_manifest.py`
- Create: `apps/api-server/tests/test_plugin_themes_api.py`
- Modify: `apps/api-server/tests/test_plugin_startup_sync.py`
- Create: `apps/user-app/src/runtime/shared/theme-plugin/__tests__/themeRuntime.test.ts`
- Create: `apps/user-app/tsconfig.plugin-theme-tests.json`
- Modify: `docs/开发设计规范/20260318-插件能力与接口规范-v1.md`
- Modify: `specs/004.8.3-主题包完全插件化改造/tasks.md`

## Task 1: 落 8 套内置主题插件目录并生成前端 bundle 索引

**Files:**
- Create: `apps/api-server/app/plugins/builtin/theme_chun_he_jing_ming_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_chun_he_jing_ming_pack/themes/chun-he-jing-ming.json`
- Create: `apps/api-server/app/plugins/builtin/theme_yue_lang_xing_xi_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_yue_lang_xing_xi_pack/themes/yue-lang-xing-xi.json`
- Create: `apps/api-server/app/plugins/builtin/theme_ming_cha_qiu_hao_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_ming_cha_qiu_hao_pack/themes/ming-cha-qiu-hao.json`
- Create: `apps/api-server/app/plugins/builtin/theme_wan_zi_qian_hong_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_wan_zi_qian_hong_pack/themes/wan-zi-qian-hong.json`
- Create: `apps/api-server/app/plugins/builtin/theme_feng_chi_dian_che_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_feng_chi_dian_che_pack/themes/feng-chi-dian-che.json`
- Create: `apps/api-server/app/plugins/builtin/theme_xing_he_wan_li_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_xing_he_wan_li_pack/themes/xing-he-wan-li.json`
- Create: `apps/api-server/app/plugins/builtin/theme_qing_shan_lv_shui_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_qing_shan_lv_shui_pack/themes/qing-shan-lv-shui.json`
- Create: `apps/api-server/app/plugins/builtin/theme_jin_xiu_qian_cheng_pack/manifest.json`
- Create: `apps/api-server/app/plugins/builtin/theme_jin_xiu_qian_cheng_pack/themes/jin-xiu-qian-cheng.json`
- Create: `apps/user-app/scripts/sync-builtin-theme-plugins.mjs`
- Create: `apps/user-app/src/runtime/shared/theme-plugin/builtinThemeBundleIndex.ts`
- Modify: `apps/user-app/package.json`
- Test: `apps/api-server/tests/test_plugin_manifest.py`

- [ ] **Step 1: 先写 manifest 失败用例，要求 `theme-pack` 必须声明资源版本和 schema 版本**

```python
def test_theme_pack_manifest_requires_schema_version() -> None:
    payload = {
        "id": "theme-chun-he-jing-ming",
        "name": "春和景明主题包",
        "version": "1.0.0",
        "api_version": 1,
        "types": ["theme-pack"],
        "permissions": [],
        "entrypoints": {},
        "capabilities": {
            "theme_pack": {
                "theme_id": "chun-he-jing-ming",
                "display_name": "春和景明",
                "tokens_resource": "themes/chun-he-jing-ming.json"
            }
        },
    }
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(payload)
```

- [ ] **Step 2: 运行测试，确认当前 schema 还不满足**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_manifest.py -q`

Expected: FAIL。

- [ ] **Step 3: 把 8 套默认主题全部变成真实 `theme-pack` 目录**

```json
{
  "id": "theme-chun-he-jing-ming",
  "name": "春和景明主题包",
  "version": "1.0.0",
  "api_version": 1,
  "types": ["theme-pack"],
  "permissions": [],
  "entrypoints": {},
  "capabilities": {
    "theme_pack": {
      "theme_id": "chun-he-jing-ming",
      "display_name": "春和景明",
      "tokens_resource": "themes/chun-he-jing-ming.json",
      "resource_version": "1.0.0",
      "theme_schema_version": 1,
      "platform_targets": ["h5", "rn"]
    }
  }
}
```

- [ ] **Step 4: 写构建期同步脚本，把主题插件 token 映射成前端 bundle 索引**

```js
const index = builtinPlugins.map(plugin => ({
  pluginId: plugin.id,
  themeId: plugin.capabilities.theme_pack.theme_id,
  resourceVersion: plugin.capabilities.theme_pack.resource_version,
  bundleModule: `./bundles/${plugin.id}/${plugin.capabilities.theme_pack.theme_id}.json`,
}));
```

- [ ] **Step 5: 让 `user-app` 在 typecheck 前刷新 `builtinThemeBundleIndex.ts`**

Run: `npm --prefix apps/user-app run typecheck`

Expected: PASS。

- [ ] **Step 6: 回跑 manifest 测试**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_manifest.py -q`

Expected: PASS。

- [ ] **Step 7: 提交这一批**

```bash
git add apps/api-server/app/plugins/builtin/theme_chun_he_jing_ming_pack apps/api-server/app/plugins/builtin/theme_yue_lang_xing_xi_pack apps/api-server/app/plugins/builtin/theme_ming_cha_qiu_hao_pack apps/api-server/app/plugins/builtin/theme_wan_zi_qian_hong_pack apps/api-server/app/plugins/builtin/theme_feng_chi_dian_che_pack apps/api-server/app/plugins/builtin/theme_xing_he_wan_li_pack apps/api-server/app/plugins/builtin/theme_qing_shan_lv_shui_pack apps/api-server/app/plugins/builtin/theme_jin_xiu_qian_cheng_pack apps/user-app/scripts/sync-builtin-theme-plugins.mjs apps/user-app/src/runtime/shared/theme-plugin/builtinThemeBundleIndex.ts apps/user-app/package.json apps/api-server/tests/test_plugin_manifest.py apps/api-server/app/modules/plugin/schemas.py
git commit -m "feat：004.8.3-落内置主题插件目录与资源索引；"
```

## Task 2: 停掉虚拟主题注册表，改成真实目录扫描和资源接口

**Files:**
- Modify: `apps/api-server/app/modules/plugin/schemas.py`
- Modify: `apps/api-server/app/modules/plugin/service.py`
- Modify: `apps/api-server/app/modules/plugin/theme_registry.py`
- Modify: `apps/api-server/app/api/v1/endpoints/ai_config.py`
- Create: `apps/api-server/tests/test_plugin_themes_api.py`

- [ ] **Step 1: 先写失败用例，要求 `/themes` 返回注册表，`/plugin-themes/{plugin_id}/{theme_id}` 返回 token**

```python
def test_list_household_themes_returns_registry_snapshot(self) -> None:
    response = client.get(f"/api/v1/ai-config/{household_id}/themes")
    payload = response.json()
    assert payload["items"][0]["resource_version"] == "1.0.0"
    assert "tokens" not in payload["items"][0]

def test_get_theme_resource_returns_token_payload(self) -> None:
    response = client.get(f"/api/v1/ai-config/{household_id}/plugin-themes/theme-chun-he-jing-ming/chun-he-jing-ming")
    payload = response.json()
    assert payload["theme_id"] == "chun-he-jing-ming"
    assert payload["tokens"]["brandPrimary"] == "#d97756"
```

- [ ] **Step 2: 运行测试，确认现状还是虚拟主题插件**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_themes_api.py -q`

Expected: FAIL。

- [ ] **Step 3: 从 `service.py` 移除 `_build_theme_registry_entries()` 和 `theme_registry.py` 的虚拟目录逻辑，改成真实插件清单**

```python
manifest_entries = _discover_registry_manifest_entries(root or BUILTIN_PLUGIN_ROOT)
theme_entries = [entry for entry in manifest_entries if "theme-pack" in entry[1].types]
```

- [ ] **Step 4: 实现主题注册表 DTO 和单主题资源接口**

```python
class PluginThemeRegistryItemRead(BaseModel):
    plugin_id: str
    theme_id: str
    display_name: str
    resource_version: str
    resource_source: Literal["builtin_bundle", "managed_plugin_dir"]
    state: Literal["ready", "disabled", "invalid", "stale"]
```

- [ ] **Step 5: 跑接口测试**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_themes_api.py -q`

Expected: PASS。

- [ ] **Step 6: 提交这一批**

```bash
git add apps/api-server/app/modules/plugin/schemas.py apps/api-server/app/modules/plugin/service.py apps/api-server/app/api/v1/endpoints/ai_config.py apps/api-server/tests/test_plugin_themes_api.py
git commit -m "feat：004.8.3-重写主题注册表与资源接口；"
```

## Task 3: 建共享主题插件运行时，去掉宿主静态主题表

**Files:**
- Create: `apps/user-app/src/runtime/shared/theme-plugin/types.ts`
- Create: `apps/user-app/src/runtime/shared/theme-plugin/themeResourceClient.ts`
- Create: `apps/user-app/src/runtime/shared/theme-plugin/themeRuntime.ts`
- Modify: `apps/user-app/src/runtime/h5-shell/theme/ThemeProvider.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/theme/applyThemeDocument.ts`
- Modify: `packages/user-core/src/domain/types.ts`
- Modify: `packages/user-core/src/state/theme.ts`
- Modify: `packages/user-core/src/state/index.ts`
- Modify: `packages/user-ui/src/theme/themes.ts`
- Create: `apps/user-app/src/runtime/shared/theme-plugin/__tests__/themeRuntime.test.ts`
- Create: `apps/user-app/tsconfig.plugin-theme-tests.json`
- Modify: `apps/user-app/package.json`

- [ ] **Step 1: 先写运行时失败用例，覆盖“首屏只读内置主题插件、已选主题失效进入待重选、H5/RN 共享同一份 token”**

```ts
test('boots with builtin theme plugin before household registry arrives', async () => {
  const runtime = createThemeRuntime({ builtinIndex, fetchRegistry, fetchResource });
  await runtime.bootstrap();
  expect(runtime.getState().activeThemeId).toBe('chun-he-jing-ming');
});

test('marks theme as missing instead of falling back to host theme table', async () => {
  const runtime = createThemeRuntime({ builtinIndex, fetchRegistry, fetchResource });
  runtime.select('theme-third-party', 'aurora');
  runtime.invalidateSelection();
  expect(runtime.getState().status).toBe('missing');
});
```

- [ ] **Step 2: 运行测试，确认当前还没有共享主题运行时**

Run: `npm --prefix apps/user-app run test:plugin-theme-runtime`

Expected: FAIL。

- [ ] **Step 3: 把 `packages/user-ui/src/theme/themes.ts` 从“静态主题资源源”改成“token 归一化与平台映射工具”**

```ts
export function normalizePluginThemeTokens(payload: PluginThemeResource): UserAppThemeTokens {
  return {
    brandPrimary: payload.tokens.brandPrimary,
    bgApp: payload.tokens.bgApp,
  };
}
```

- [ ] **Step 4: 在 `themeRuntime.ts` 里统一内置 bundle / 远端主题接口**

```ts
if (entry.resource_source === 'builtin_bundle') {
  return loadBuiltinThemeBundle(entry.plugin_id, entry.theme_id);
}
return requestPluginThemeResource(householdId, entry.plugin_id, entry.theme_id);
```

- [ ] **Step 5: 让 `ThemeProvider.tsx` 只消费运行时状态，不再从 `userAppThemeList` 推导真实可用主题**

Run: `npm --prefix apps/user-app run test:plugin-theme-runtime`

Expected: PASS。

Run: `npm --prefix apps/user-app run typecheck`

Expected: PASS。

- [ ] **Step 6: 提交这一批**

```bash
git add apps/user-app/src/runtime/shared/theme-plugin apps/user-app/src/runtime/h5-shell/theme/ThemeProvider.tsx apps/user-app/src/runtime/h5-shell/theme/applyThemeDocument.ts packages/user-core/src/domain/types.ts packages/user-core/src/state/theme.ts packages/user-core/src/state/index.ts packages/user-ui/src/theme/themes.ts apps/user-app/package.json apps/user-app/tsconfig.plugin-theme-tests.json
git commit -m "feat：004.8.3-建立统一主题插件运行时；"
```

## Task 4: 接通登录页、H5、RN 的主题插件链路

**Files:**
- Modify: `apps/user-app/src/runtime/app-runtime.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/components/ThemeSwitcher.tsx`
- Modify: `apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx`
- Modify: `apps/user-app/src/runtime/rn-shell/tokens.ts`
- Create: `apps/user-app/src/runtime/rn-shell/theme/RnThemeProvider.tsx`
- Modify: `apps/user-app/src/runtime/rn-shell/index.ts`
- Test: `apps/user-app/src/runtime/shared/theme-plugin/__tests__/themeRuntime.test.ts`

- [ ] **Step 1: 先补登录页主题集成失败用例**

```ts
test('login screen uses builtin plugin theme before actor bootstrap', async () => {
  render(<H5LoginPage />);
  expect(document.documentElement.getAttribute('data-theme')).toBe('chun-he-jing-ming');
});
```

- [ ] **Step 2: 让 `AppRuntimeProvider` 在登录后刷新家庭主题注册表，在退出登录后退回内置主题**

```ts
await themeRuntime.refreshRegistry({ householdId: nextBootstrap.actor.household_id });
await themeRuntime.resetToBuiltin();
```

- [ ] **Step 3: 让 `ThemeSwitcher.tsx` 只显示插件注册表里的主题，不再读宿主静态列表**

- [ ] **Step 4: 把 RN token 改成从运行时主题资源派生，而不是固定取 `chun-he-jing-ming`**

Run: `npm --prefix apps/user-app run test:plugin-theme-runtime`

Expected: PASS。

Run: `npm --prefix apps/user-app run build:h5`

Expected: BUILD SUCCESS。

Run: `npm --prefix apps/user-app run build:ios`

Expected: BUILD SUCCESS。

- [ ] **Step 5: 提交这一批**

```bash
git add apps/user-app/src/runtime/app-runtime.tsx apps/user-app/src/runtime/h5-shell/components/ThemeSwitcher.tsx apps/user-app/src/runtime/h5-shell/components/LoginPage.tsx apps/user-app/src/runtime/rn-shell/tokens.ts apps/user-app/src/runtime/rn-shell/theme/RnThemeProvider.tsx apps/user-app/src/runtime/rn-shell/index.ts
git commit -m "feat：004.8.3-让登录页与双端页面接入主题插件；"
```

## Task 5: 接通安装同步、文档和总验证

**Files:**
- Modify: `apps/api-server/app/modules/plugin/startup_sync_service.py`
- Modify: `apps/api-server/tests/test_plugin_startup_sync.py`
- Modify: `docs/开发设计规范/20260318-插件能力与接口规范-v1.md`
- Modify: `specs/004.8.3-主题包完全插件化改造/tasks.md`

- [ ] **Step 1: 先补远端主题插件安装/升级/卸载后的失败用例**

```python
def test_startup_sync_refreshes_theme_registry_when_marketplace_theme_changes(self) -> None:
    result = sync_persisted_plugins_on_startup(self.db)
    assert result.marketplace_mount_updated >= 1
```

- [ ] **Step 2: 在 startup sync 中把 `theme-pack` 变更纳入主题注册表刷新**

```python
if manifest.types and "theme-pack" in manifest.types:
    changed_household_ids.add(household_id)
```

- [ ] **Step 3: 同步更新文档和 spec 任务状态**

Run: `cd apps/api-server && python -m pytest tests/test_plugin_manifest.py tests/test_plugin_themes_api.py tests/test_plugin_startup_sync.py -q`

Expected: PASS。

Run: `npm --prefix apps/user-app run test:plugin-theme-runtime`

Expected: PASS。

Run: `npm --prefix apps/user-app run typecheck`

Expected: PASS。

Run: `npm --prefix apps/user-app run build:h5`

Expected: BUILD SUCCESS。

- [ ] **Step 4: 做最终 diff 回读，确认没有宿主主题 fallback**

Checklist:
- `ThemeProvider.tsx` 不再用宿主静态主题表当 canonical source
- `packages/user-ui/src/theme/themes.ts` 只剩 token 归一化/映射工具
- RN token 不再硬编码默认主题资源
- `/themes` 返回注册表，token 正文只由 `/plugin-themes/...` 返回

- [ ] **Step 5: 提交收尾批次**

```bash
git add apps/api-server/app/modules/plugin/startup_sync_service.py apps/api-server/tests/test_plugin_startup_sync.py docs/开发设计规范/20260318-插件能力与接口规范-v1.md specs/004.8.3-主题包完全插件化改造/tasks.md
git commit -m "feat：004.8.3-打通主题插件安装同步与文档；"
```

## 总验证

- [ ] `cd apps/api-server && python -m pytest tests/test_plugin_manifest.py tests/test_plugin_themes_api.py tests/test_plugin_startup_sync.py -q`
- [ ] `npm --prefix apps/user-app run test:plugin-theme-runtime`
- [ ] `npm --prefix apps/user-app run typecheck`
- [ ] `npm --prefix apps/user-app run build:h5`
- [ ] `npm --prefix apps/user-app run build:ios`

## Done / Partial / Skipped

- Done: implementation plan 已覆盖真实插件目录、manifest、token 资源文件、后端注册表接口、前端双来源运行时、登录页/首屏、安装同步和文档更新。
- Partial: RN 主题 provider 的最终注入点要在实现时结合真实页面树确认，但计划里已经给出新增文件和替换方向。
- Skipped: 没把签名校验、商业化分发、设计系统额外重做写进本计划，因为 spec 明确不做。
