# 插件开发者文档

## 文档元数据

- 当前版本：v1.6
- 中文主入口：
  - `docs/开发者文档/插件开发/zh-CN/README.md`
- 英文入口：
  - `docs/开发者文档/插件开发/en/README.md`
- 关联主 spec：
  - `specs/004.8-插件系统V1定稿与全量迁移/`
  - `specs/004.8.1-AI供应商彻底插件化迁移/`

这套文档现在只做一件事：给开发者提供当前正式规则。

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

## AI 供应商当前口径

AI 供应商插件化现在已经完成收口，统一按下面顺序理解：

1. `specs/004.8.1-AI供应商彻底插件化迁移/`
2. `docs/开发设计规范/20260318-插件能力与接口规范-v1.md`
3. 这套开发者手册

当前正式规则只有一句话：

- 宿主保留统一 AI 网关、路由、权限、审计、密钥和 fallback
- `ai-provider` 插件负责供应商声明、字段 schema、driver entrypoint、协议适配、流式输出和厂商特例

注意：

- 这不是目标态，而是当前正式边界
- 旧 spec 和旧报告只保留历史背景，不再定义当前实现

## 阅读顺序

先看固定规则：

- `zh-CN/00-文档使用与维护原则.md`
- `zh-CN/01-插件开发总览.md`
- `zh-CN/03-manifest字段规范.md`
- `zh-CN/12-V1插件类型与接口总表.md`

再看接口与实操：

- `zh-CN/05-插件对接方式说明.md`
- `zh-CN/11-插件配置接入说明.md`
- `zh-CN/07-插件测试与项目内运行验证.md`

英文入口按同名文件同步维护。
