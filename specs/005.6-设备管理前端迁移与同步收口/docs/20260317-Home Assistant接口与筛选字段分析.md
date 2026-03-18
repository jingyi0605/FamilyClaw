# 20260317-Home Assistant接口与筛选字段分析

## 这份文档是干什么的

这份文档只回答一件事：

这次“部分同步筛选”到底靠什么数据做，不准空口说白话。

如果名称、房间、集成分类这三个筛选项说不清字段来源，那这个需求就不算设计完成。

## 当前项目已经接了哪些 HA 接口

从当前项目代码看，HA 客户端已经在用下面这些接口：

### 1. REST `GET /api/states`

当前用途：

- 读取实体实时状态
- 读取 `friendly_name`
- 读取 `unit_of_measurement`
- 读取可能存在的 `area_name` / `room_name`

项目位置：

- [client.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/client.py)
- [connector.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/connector.py)

官方参考：

- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/)

### 2. WebSocket `/api/websocket`

当前用途：

- 认证后发送 registry 命令
- 读取设备注册表
- 读取实体注册表
- 读取区域注册表

项目位置：

- [client.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/client.py)

官方参考：

- [Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket/)

### 3. `config/device_registry/list`

当前用途：

- 读取 HA 设备列表
- 读取设备名称
- 读取设备 `area_id`
- 读取厂商、型号等元信息

项目位置：

- [client.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/client.py)
- [connector.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/connector.py)

### 4. `config/entity_registry/list`

当前用途：

- 读取实体列表
- 按 `device_id` 把实体归到设备
- 读取 `entity_id`
- 读取实体名称
- 排除被禁用实体

项目位置：

- [client.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/client.py)
- [connector.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/connector.py)

官方参考：

- [Entity registry](https://developers.home-assistant.io/docs/entity_registry_index/)

### 5. `config/area_registry/list`

当前用途：

- 读取 房间（Area）列表
- 把 `area_id` 映射成用户能读懂的房间名

项目位置：

- [client.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/client.py)
- [connector.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/connector.py)

官方参考：

- [Area registry](https://developers.home-assistant.io/docs/area_registry_index/)

### 6. REST `POST /api/services/{domain}/{service}`

当前用途：

- 执行灯、空调、窗帘、音箱、门锁的具体控制动作

项目位置：

- [client.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/client.py)
- [executor.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/executor.py)
- [mapper.py](/C:/Code/FamilyClaw/apps/api-server/app/plugins/builtin/homeassistant_device_action/mapper.py)

官方参考：

- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/)

## 三个筛选项到底从哪里来

## 1. 名称搜索

这个最简单，当前链路已经够了。

### 可用来源

优先级：

1. `device.name_by_user`
2. `device.name`
3. `entity.name`
4. `entity.original_name`
5. `state.attributes.friendly_name`

### 结论

- 可以直接支持
- 前端本地过滤就够，不需要改同步执行逻辑

## 2. 房间筛选

这也已经够了。

### 可用来源

优先级：

1. `entity.area_id -> area_registry.name`
2. `device.area_id -> area_registry.name`
3. `state.attributes.area_name`
4. `state.attributes.room_name`
5. `state.attributes.room`

### 当前项目怎么做

当前 `connector.py` 里已经有 `_resolve_room_name()`，会优先走 `area_id` 和 `area_registry`，拿不到再从 state attributes 里兜底。

### 结论

- 可以直接支持
- 前端只要对 `room_name` 做分组筛选即可

## 3. 集成分类筛选

这里是唯一要说清楚的麻烦点。

用户要的是“HA 集成分类”，不是“设备类型”。

### 真正应该依赖的来源

优先级：

1. entity registry 里的平台字段（platform）
2. device / entity 关联的 config entry 所属集成
3. 如果上面都拿不到，才退化为 `primary_entity_id` 的 domain

### 当前项目现状

当前候选设备返回给前端的稳定字段主要是：

- `external_device_id`
- `primary_entity_id`
- `name`
- `room_name`
- `device_type`
- `entity_count`
- `already_synced`

这意味着：

- 名称和房间没问题
- 真正的“集成分类”当前前端还没有稳定字段可直接用

### 可接受方案

#### 方案 A：最小只读字段补充，推荐

在候选设备响应里补：

- `integration_category`
- `integration_category_source`

注意：

- 这只是补候选展示字段
- 不改 `device_sync` 的执行逻辑
- 不改 `selected_external_ids` 的语义

这不属于改后端同步逻辑，而是补读模型。

#### 方案 B：纯前端降级，保守

如果一点后端 DTO 都不想动，那前端只能：

- 从 `primary_entity_id` 里截出 domain，例如 `light`、`climate`、`cover`
- 把筛选器名字写成“实体域”

这个方案能跑，但不该谎称它是“HA 集成分类”。

### 结论

- 如果产品坚持“集成分类”四个字，建议用方案 A。
- 如果产品接受降级，可以用方案 B，但文案必须改掉。

## 当前项目字段够不够

| 筛选项 | 当前链路是否够用 | 是否需要后端补充 | 说明 |
| --- | --- | --- | --- |
| 名称搜索 | 够 | 否 | 直接用 `name` |
| 房间 | 够 | 否 | 直接用 `room_name` |
| 集成分类 | 不完全够 | 建议补只读字段 | 不然只能退化成实体 domain |

## 为什么这不算改后端同步逻辑

因为真正的同步逻辑是：

1. 后端按 `selected_external_ids` 或空数组决定同步范围
2. 插件去 HA 拉数据
3. 后端落库

这三件事我们都不动。

如果补 `integration_category`，只是把“候选列表展示给前端时多带一个标签”，本质上是读模型补充，不是执行逻辑变更。

## 建议落地结论

1. 名称搜索：纯前端实现。
2. 房间筛选：纯前端实现。
3. 集成分类筛选：
   - 推荐：补候选只读字段。
   - 保守：前端降级为实体域筛选，并改文案。

## 参考链接

- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/)
- [Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket/)
- [Entity registry](https://developers.home-assistant.io/docs/entity_registry_index/)
- [Device registry](https://developers.home-assistant.io/docs/device_registry_index/)
- [Area registry](https://developers.home-assistant.io/docs/area_registry_index/)
