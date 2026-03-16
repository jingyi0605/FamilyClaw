# 001.5 验证记录

## 已完成验证

### 1. 后端 provider registry 定向测试

命令：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ai_config_center.AiConfigCenterTests.test_provider_adapter_registry_exposes_core_adapters
```

执行目录：

```text
apps/api-server
```

结果：通过。

## 当前阻塞

### 1. 前端全量类型检查阻塞

命令：

```powershell
npm.cmd run typecheck:user-app
```

结果：失败。

当前可见错误：

- `apps/user-app/src/pages/family/LegacyFamilyPage.tsx` 存在大量 i18n key 类型错误和 `pickLocaleText` 未定义错误。
- `apps/user-app/src/pages/home/page.rn.tsx` 依赖的 `page.shared` 导出不匹配。

说明：

- 这些报错不在这次 AI 供应商管理改造的核心文件里，但它们会挡住当前工作区的全量类型检查。

### 2. 页面联调阻塞

- 访问 `http://10.255.0.85:10086/pages/settings/ai/index` 会跳转到登录页。
- 当前已知测试账号无法登录，所以没法完成页面真机联调。

### 3. 完整后端测试阻塞

命令：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ai_config_center
```

结果：未完全通过。

阻塞点：

- `test_butler_bootstrap_flow_reuses_existing_agent_creation_model`

原因：

- 这个测试会走真实 OpenAI 调用。
- 当前环境里的 API key 无效，导致 bootstrap 流程状态没有进入预期值。

## 建议验收步骤

### 页面人工验收

1. 登录 `user-app` 后打开 `/pages/settings/ai/index`。
2. 进入 AI 供应商管理页，确认主页面只展示列表、汇总和摘要，没有大段平铺配置。
3. 点击新增按钮，确认第一步先出现供应商插件选择区。
4. 选择不同供应商，确认表单字段会跟着切换，并显示支持类型和 `llm_workflow`。
5. 创建一个新模型，返回列表后确认摘要里能看到插件、模型名、支持类型、路由能力和关键字段。
6. 选中已有模型点编辑，确认能回显旧配置，且不会要求重建旧数据。

### 后端补充验收

1. 提供有效 OpenAI key 后重新执行完整测试：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ai_config_center
```

2. 如果不希望测试依赖真实外部调用，就把该测试改成 mock，再重新验收。

### 前端补充验收

1. 先修复当前工作区的全量 TypeScript 报错。
2. 再重新执行：

```powershell
npm.cmd run typecheck:user-app
```
