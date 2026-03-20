# 任务清单 - 插件配置协议与动态表单

状态：DONE

## 更新记录

- 2026-03-19
  - 新增“动态选项源、字段联动、普通字段清空”这一轮增量任务。
  - 已完成宿主协议、解析接口、前端联动、天气插件接入和回归测试补充。

## 任务状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `DONE`：已经完成并回写

## 已完成的基础阶段

- [x] 1. 协议定型
  - 状态：DONE
  - 结果：插件配置已有正式 `config_schema`、`ui_schema`、多作用域和 secret 语义。

- [x] 2. 后端配置持久化与基础 API
  - 状态：DONE
  - 结果：宿主已有统一配置实例表、读写接口和校验链路。

- [x] 3. 前端动态表单 renderer
  - 状态：DONE
  - 结果：设置页已能按协议动态渲染基础字段。

- [x] 4. 首批插件接入
  - 状态：DONE
  - 结果：已有插件配置接入通路，不再完全依赖专用页面。

## 本轮增量任务：联动能力补齐

- [x] 5.1 扩展 manifest 动态选项源协议
  - 状态：DONE
  - 这一步做什么：新增 `option_source`、`depends_on`、`clear_on_dependency_change`。
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
  - 验证结果：
    - manifest 校验可识别动态源和依赖引用

- [x] 5.2 扩展普通字段清空语义
  - 状态：DONE
  - 这一步做什么：新增 `clear_fields`，解决“前端删了但数据库还留着”的问题。
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/schemas.py`
    - `apps/api-server/app/modules/plugin/config_service.py`
    - `apps/api-server/app/modules/integration/schemas.py`
    - `apps/api-server/app/modules/integration/service.py`
  - 验证结果：
    - 新增自动化测试覆盖普通字段清空

- [x] 5.3 增加配置草稿解析接口
  - 状态：DONE
  - 这一步做什么：新增 `POST /ai-config/{household_id}/plugins/{plugin_id}/config/resolve`。
  - 主要改哪里：
    - `apps/api-server/app/modules/plugin/config_service.py`
    - `apps/api-server/app/api/v1/endpoints/ai_config.py`
    - `apps/api-server/app/modules/plugin/__init__.py`
  - 验证结果：
    - `GET config` 和 `POST resolve` 统一走动态解析链

- [x] 5.4 改造前端设置页联动逻辑
  - 状态：DONE
  - 这一步做什么：字段变化后重拉 schema，自动清理失效子级值，并在提交时带上 `clear_fields`。
  - 主要改哪里：
    - `apps/user-app/src/pages/settings/settingsTypes.ts`
    - `apps/user-app/src/pages/settings/settingsApi.ts`
    - `apps/user-app/src/pages/settings/integrations/index.tsx`
  - 验证结果：
    - 省、市、区都以 select 渲染
    - 父级切换后下游选项会联动刷新

- [x] 5.5 天气插件迁到新协议
  - 状态：DONE
  - 这一步做什么：去掉巨型静态省市区枚举，改成动态 provider 和地区目录级联。
  - 主要改哪里：
- `apps/api-server/plugins-dev/official_weather/manifest.json`
- `apps/api-server/plugins-dev/official_weather/locales/zh-CN.json`
- `apps/api-server/plugins-dev/official_weather/locales/en-US.json`
- `apps/api-server/plugins-dev/official_weather/service.py`
  - 验证结果：
    - 支持从宿主读取可用地区 provider
    - 支持按 provider 拉省、市、区县
    - 保留旧 `provider_selector` / `region_code` 兼容读取

- [x] 5.6 同步规范和测试
  - 状态：DONE
  - 这一步做什么：更新 Spec、开发文档、技术规范，并补测试。
  - 主要改哪里：
    - `specs/004.2.3-插件配置协议与动态表单/*`
    - `docs/开发者文档/插件开发/zh-CN/03-manifest字段规范.md`
    - `docs/开发者文档/插件开发/zh-CN/11-插件配置接入说明.md`
    - `docs/开发设计规范/20260318-插件能力与接口规范-v1.md`
    - `apps/api-server/tests/test_plugin_config_dynamic_api.py`
    - `apps/api-server/tests/test_weather_plugin_config.py`
  - 验证结果：
    - 后端新增测试通过

## 本轮结论

这一轮不是“给天气插件补个小修”，而是把插件系统补到了真正能承接联动表单的程度。

现在宿主已经正式支持：

- 动态地区 provider 列表
- 按父字段重算子级地区目录
- 草稿级 resolve
- 普通字段和 secret 字段的正式清空
- 天气插件通过通用能力接入，而不是继续靠特判
