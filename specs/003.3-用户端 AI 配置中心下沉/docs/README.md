# 003.3 补充说明

这份文档只写已经落地的东西，不写空话。

## 本轮已完成

### 1. user-web 已经成为正式 AI 配置入口

- `设置 / AI` 不再只是只读展示
- 用户现在可以在 `user-web` 里完成：
  - 供应商新增、编辑、删除
  - household 级 capability route 绑定
  - Agent 新增
  - Agent 基础资料编辑
  - Agent 人格资料编辑
  - Agent 运行时策略编辑
  - Agent 成员认知编辑

### 2. 供应商差异已收敛到适配器注册表

当前已经提供下面这些适配器定义：

- `chatgpt`
- `glm`
- `siliconflow`
- `kimi`
- `minimax`

用户端页面不再把每家供应商字段硬编码在页面里，而是根据适配器定义渲染。

### 3. 003.2 向导后两步已复用正式能力

`/setup` 里的下面两步，已经不再维护第二套临时 AI 表单：

- `provider_setup`
- `first_butler_agent`

当前实现方式是复用正式的：

- `AiProviderConfigPanel`
- `AgentConfigPanel`

这保证了 `003.2` 主链路和 `003.3` 正式入口不是两套分叉垃圾。

## 当前边界

这轮**没有**完成下面这些内容：

- 首个管家真正的对话式创建流程
- 与对话式创建相关的 session/message/confirm 接口
- 更复杂的多供应商高级参数暴露

也就是说，`003.3` 的阶段 1 和阶段 2 已完成，阶段 3 还没做。

## 验证方式

### 前端

在 `apps/user-web` 下执行：

```bash
npm.cmd run build
```

### 后端

在 `apps/api-server` 下执行：

```bash
python -m compileall app
python -m unittest tests.test_ai_config_center -v
```

## 联调时先看哪里

如果后面有人继续接手，先看这些文件：

- `apps/user-web/src/pages/SettingsAiPage.tsx`
- `apps/user-web/src/pages/SetupWizardPage.tsx`
- `apps/user-web/src/components/AiProviderConfigPanel.tsx`
- `apps/user-web/src/components/AgentConfigPanel.tsx`
- `apps/api-server/app/api/v1/endpoints/ai_config.py`
- `apps/api-server/app/modules/ai_gateway/provider_adapter_registry.py`

别一上来就去翻 `admin-web`。那不是正式入口。
