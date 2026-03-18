# 插件开发文档（中文）

## 这套文档现在怎么读

这套手册现在只服务两件事：

1. 插件系统 V1 的正式开发规则
2. AI 供应商插件化已经落地后的统一开发口径

先记住四句话：

- 宿主只保留平台规则和统一入口，不再继续吸收供应商特例
- 领域能力走正式插件类型，状态型能力走 `integration`
- 记忆能力只通过独占槽位接入：`memory_engine`、`memory_provider`、`context_engine`
- AI 供应商一律按 `004.8.1` 的当前实现边界来写，不再按“迁移中”理解

## 阅读顺序

### 固定规则，先看这些

- `00-文档使用与维护原则.md`
- `01-插件开发总览.md`
- `03-manifest字段规范.md`
- `12-V1插件类型与接口总表.md`

### 接口和调用方式，再看这些

- `05-插件对接方式说明.md`
- `11-插件配置接入说明.md`
- `10-计划任务接口与OpenAPI说明.md`

### 实操和验证，按需看

- `02-插件开发环境与本地调试.md`
- `06-从零开发一个可运行插件.md`
- `07-插件测试与项目内运行验证.md`

## 当前正式插件类型

- `integration`
- `action`
- `agent-skill`
- `channel`
- `region-provider`
- `ai-provider`
- `locale-pack`
- `theme-pack`

## 当前正式独占槽位

- `memory_engine`
- `memory_provider`
- `context_engine`

## AI 供应商插件当前边界

AI 供应商相关规则统一按下面顺序看：

1. `specs/004.8.1-AI供应商彻底插件化迁移/`
2. `docs/开发设计规范/20260318-插件能力与接口规范-v1.md`
3. 这套开发者手册

当前正式口径是：

- 宿主保留统一 AI 网关、路由、权限、审计、密钥、插件状态校验和降级
- `ai-provider` 插件负责供应商声明、字段 schema、driver entrypoint、协议适配、流式输出、厂商特例

注意两点：

- 这是当前实现边界，不是目标态
- 旧 spec 和历史报告可以保留，但只能当历史背景，不能当现行规则

## 高频事实来源

- `apps/api-server/app/modules/plugin/schemas.py`
- `apps/api-server/app/modules/plugin/service.py`
- `apps/api-server/app/modules/ai_gateway/provider_driver.py`
- `apps/api-server/app/modules/ai_gateway/provider_config_service.py`
- `apps/api-server/app/plugins/builtin/ai_provider_*/manifest.json`
- `specs/004.8.1-AI供应商彻底插件化迁移/`
