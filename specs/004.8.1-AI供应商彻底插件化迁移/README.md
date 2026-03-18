# Spec 004.8.1 - AI 供应商彻底插件化迁移

状态：Implemented

## 这份 Spec 现在负责什么

这份 Spec 已经从“迁移设计稿”收口为“现行主规则”。

从现在开始，凡是涉及下面这些问题，都以 `004.8.1` 为准：

- 宿主和 `ai-provider` 插件的最终边界
- `provider driver contract` 的稳定接口
- 哪些代码必须留在宿主
- 哪些供应商逻辑必须迁到插件
- 旧 spec 和开发者文档该怎么降级成历史背景

## 迁移已经完成到什么程度

这次迁移已经把“AI 供应商事实来源”和“厂商特例执行逻辑”从核心里挪出去了，当前以真实插件为准，不再以核心内置注册表为准。

已经完成的结果：

- `apps/api-server/app/modules/ai_gateway/provider_adapter_registry.py` 已删除
- 宿主通过 `apps/api-server/app/modules/ai_gateway/provider_driver.py` 按插件 entrypoint 加载 provider driver
- `apps/api-server/app/modules/plugin/service.py` 不再虚拟生成 `ai-provider` manifest
- builtin AI 供应商现在是 `apps/api-server/app/plugins/builtin/ai_provider_*/manifest.json`
- SiliconFlow、OpenRouter 这类厂商特例已经迁到各自插件 driver
- `app/modules/ai_gateway` 和 `app/modules/plugin` 不再保留供应商专用分发表

## 当前正式边界

宿主保留：

- 统一 AI Gateway
- 路由和 fallback
- 权限、审计、密钥、插件启停校验
- 统一错误语义和统一调用结果

`ai-provider` 插件负责：

- 供应商声明
- 字段 schema
- provider driver entrypoint
- 协议适配
- 流式输出
- 厂商特例和最小诊断信息

一句话说明：

宿主只负责平台规则和统一入口；供应商怎么接、怎么发请求、有什么厂商特例，都由 `ai-provider` 插件自己负责。

## 现在明确不允许什么

- 不允许再把新供应商写回核心注册表
- 不允许再在 `app/modules/ai_gateway` 里新增厂商特判
- 不允许再生成“虚拟 ai-provider manifest”冒充真实插件
- 不允许开发者文档继续写“AI 供应商还只是元数据插件”

## 和旧 spec 的关系

`004.8.1` 是 AI 供应商插件化的唯一主 spec。

旧 spec 继续保留，但只保留历史角色：

- `001.5`
  - 记录 AI 配置中心第一轮页面插件化背景
- `001.5.1`
  - 记录官方对齐和 Coding Plan 扩展的历史阶段
- `004.5`
  - 记录通用插件系统、启停和版本治理的大边界
- `004.8`
  - 继续作为插件系统 V1 的父级 spec

这些旧 spec 不再定义 AI 供应商的当前实现边界。

## 阅读顺序

1. `requirements.md`
2. `design.md`
3. `tasks.md`
4. `docs/README.md`
5. `docs/开发设计规范/20260318-插件能力与接口规范-v1.md`
