---
title: 计划任务与 OpenAPI
docId: zh-plugin-schedule
version: v0.1
status: active
order: 475
outline: deep
---

# 计划任务与 OpenAPI

这页只回答 3 件事：

1. 现在有哪些正式计划任务接口
2. 去哪里看自动生成的 OpenAPI 文档
3. 作为插件开发者，哪些字段能配，哪些事情不能乱做

## 先把边界说死

- 现在开发者真正能配置的目标，只有插件，也就是 `target_type=plugin_job`
- `target_ref_id` 不是任意字符串，它就是插件 `id`
- 插件必须在 `manifest.triggers` 里声明 `schedule`，否则计划任务接口会拒绝
- 插件不会因为写了 `schedule` 就自己注册 cron；真正的调度、归属、权限和幂等都归计划任务系统管
- 计划任务现在已经区分两种归属：
  - `household`：家庭公共任务
  - `member`：成员私有任务

## OpenAPI 到哪看

如果后端服务已经启动，默认可以直接看这几个入口：

- `GET /openapi.json`：完整 OpenAPI JSON
- `GET /docs`：Swagger UI
- `GET /redoc`：ReDoc

这三者的区别很简单：

- `openapi.json` 适合给工具读，或者导入 Postman、Insomnia
- `/docs` 适合联调时直接点接口试
- `/redoc` 更适合浏览字段说明

## 当前正式接口

代码入口：`apps/api-server/app/api/v1/endpoints/scheduled_tasks.py`

### 创建计划任务

- 方法：`POST /api/v1/scheduled-tasks`
- 作用：创建一条任务定义
- 认证：要求已登录且绑定家庭成员

最小示例：

```json
{
  "household_id": "household-demo",
  "owner_scope": "household",
  "code": "daily-health-sync",
  "name": "每天健康同步",
  "trigger_type": "schedule",
  "schedule_type": "daily",
  "schedule_expr": "09:00",
  "target_type": "plugin_job",
  "target_ref_id": "health-basic-reader"
}
```

关键字段说明：

- `owner_scope`
  - `household`：家庭公共任务，只允许管理员建
  - `member`：成员私有任务，普通成员只能给自己建
- `trigger_type`
  - `schedule`：固定时间触发
  - `heartbeat`：心跳巡检触发
- `schedule_type`
  - 当前支持：`daily`、`interval`、`cron`
- `target_type`
  - 当前稳定可用：`plugin_job`
- `target_ref_id`
  - 当前就是插件 `id`

### 查任务定义列表

- 方法：`GET /api/v1/scheduled-tasks`
- 作用：按家庭、归属、状态过滤任务定义

常用查询参数：

- `household_id`
- `owner_scope`
- `owner_member_id`
- `enabled`
- `trigger_type`
- `target_type`
- `status`

### 查任务详情

- 方法：`GET /api/v1/scheduled-tasks/{task_id}`
- 作用：查单条任务定义

### 更新任务定义

- 方法：`PATCH /api/v1/scheduled-tasks/{task_id}`
- 作用：改名称、说明、归属、时间配置、目标插件、启用状态等

注意：

- 改目标插件时，后端会重新校验插件是否存在、是否启用、是否支持 `schedule`

### 启用 / 停用任务

- 方法：`POST /api/v1/scheduled-tasks/{task_id}/enable`
- 方法：`POST /api/v1/scheduled-tasks/{task_id}/disable`
- 作用：切换任务启停状态

### 查运行记录

- 方法：`GET /api/v1/scheduled-task-runs`
- 作用：查某个家庭下的运行历史

常用查询参数：

- `household_id`
- `task_definition_id`
- `owner_scope`
- `owner_member_id`
- `status`
- `created_from`
- `created_to`
- `limit`

## 一条完整主链怎么查

你要查“计划任务 -> plugin_job -> 可查询”这条链，按这个顺序最清楚：

1. 先用 `GET /api/v1/scheduled-tasks` 找到任务定义
2. 再用 `GET /api/v1/scheduled-task-runs?task_definition_id=...` 找运行记录
3. 看返回里的 `target_run_id`
4. 再去查 `GET /api/v1/plugin-jobs/{job_id}`

关键追踪字段：

- `scheduled_task_run.target_run_id`：对应 `plugin_job.id`
- `plugin_job.source_task_definition_id`：来源任务定义 id
- `plugin_job.source_task_run_id`：来源任务运行 id

## 插件开发者现在还能配什么

现阶段，插件和计划任务相关的正式可配置内容，只有这些：

### `manifest.triggers`

- 要接计划任务，必须包含 `schedule`
- 没有这项，就别指望能被计划任务系统引用

### `manifest.schedule_templates`

- 这是推荐模板，不是自动建任务
- 适合告诉前端或后续配置入口：“这个插件通常怎么配”

### 插件挂载启用状态

- 插件在家庭挂载层被禁用后，新建任务会被拒绝
- 已经排队但还没分发的运行，也会在分发时失败收口

## 现在还没开放给插件作者的东西

这些现在别写、别赌、别假设：

- 插件自己注册 cron 或 heartbeat
- 插件自己维护调度状态
- 插件模板自动落库成正式计划任务
- 计划任务直接绕过 `plugin_job` 去同步跑插件
- 插件市场里一键配置计划任务全流程

## 联调建议

最省事的调法：

1. 先开 `/docs` 看字段模型
2. 用 `POST /api/v1/scheduled-tasks` 建一条目标插件任务
3. 用 `GET /api/v1/scheduled-task-runs` 看它有没有生成运行记录
4. 再用 `GET /api/v1/plugin-jobs/{job_id}` 看是否真的进了插件后台任务链

如果你在第 2 步就失败，优先检查：

- 插件 id 是否写对
- 插件是否启用
- 插件 `triggers` 是否包含 `schedule`
- 归属是不是越权了
