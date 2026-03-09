# Spec 001 - 设计方案

## 概述

本 Spec 采用**模块化单体**设计，先在一个 `api-server` 内完成以下模块：

1. `household`
2. `member`
3. `relationship`
4. `permission`
5. `room`
6. `device`
7. `ha_integration`
8. `audit`

同时保留后续拆分空间。

数据库实现约束：

- 首期持久化统一采用 `SQLite`
- 所有主键以 `TEXT` 形式存储 UUID
- 时间字段以 `TEXT` 形式存储 `ISO8601 UTC`
- JSON 结构字段以 `TEXT` 形式存储 JSON 字符串

---

## 一、模块设计

## 1. `household`

职责：

- 创建家庭
- 查询家庭详情
- 更新家庭基础设置

数据表：

- `households`

核心接口：

- `POST /api/v1/households`
- `GET /api/v1/households/{id}`

## 2. `member`

职责：

- 成员增删改查
- 成员状态维护
- 管理员录入家庭成员

数据表：

- `members`
- `member_preferences`

核心接口：

- `POST /api/v1/members`
- `GET /api/v1/members`
- `PATCH /api/v1/members/{id}`

## 3. `relationship`

职责：

- 家庭成员关系管理

数据表：

- `member_relationships`

核心接口：

- `POST /api/v1/member-relationships`
- `GET /api/v1/member-relationships`

## 4. `permission`

职责：

- 成员权限读写
- 资源访问决策基础

数据表：

- `member_permissions`

核心接口：

- `PUT /api/v1/member-permissions/{member_id}`
- `GET /api/v1/member-permissions/{member_id}`

## 5. `room`

职责：

- 房间管理

数据表：

- `rooms`

核心接口：

- `POST /api/v1/rooms`
- `GET /api/v1/rooms`

## 6. `device`

职责：

- 本地设备主数据管理
- 房间与设备绑定

数据表：

- `devices`
- `device_bindings`

核心接口：

- `GET /api/v1/devices`
- `PATCH /api/v1/devices/{id}`

## 7. `ha_integration`

职责：

- 从 HA 拉取实体
- 归一化设备信息
- 写入本地设备表

依赖：

- `Home Assistant REST API`

核心接口：

- `POST /api/v1/devices/sync/ha`

## 8. `audit`

职责：

- 记录关键动作日志

数据表：

- `audit_logs`

触发点：

- 家庭创建
- 成员编辑
- 房间编辑
- 设备同步

---

## 二、目录建议

```text
apps/api-server/
├── app/
│   ├── api/
│   │   └── v1/
│   ├── core/
│   ├── db/
│   ├── modules/
│   │   ├── household/
│   │   ├── member/
│   │   ├── relationship/
│   │   ├── permission/
│   │   ├── room/
│   │   ├── device/
│   │   ├── ha_integration/
│   │   └── audit/
│   └── main.py
└── migrations/
```

---

## 三、数据模型

本 Spec 首批采用以下表：

1. `households`
2. `members`
3. `member_relationships`
4. `member_preferences`
5. `member_permissions`
6. `rooms`
7. `devices`
8. `device_bindings`
9. `audit_logs`

其中：

- `members.household_id` 关联 `households.id`
- `rooms.household_id` 关联 `households.id`
- `devices.room_id` 关联 `rooms.id`
- `device_bindings.device_id` 关联 `devices.id`

---

## 四、权限设计

首期先做最小规则：

### 管理员

- 可管理家庭、成员、房间、设备、权限

### 成人

- 默认可读公共资源和自身资源

### 儿童

- 只能访问自己的非敏感资源

### 老人

- 默认可访问自身相关提醒与公共信息

### 访客

- 只可访问极少量公共信息

首期权限判断建议：

1. 先基于角色做默认权限
2. 再读取 `member_permissions` 增量覆盖

---

## 五、HA 设备同步设计

## 输入

- 管理员手动触发同步

## 同步流程

1. 请求 HA 实体列表
2. 过滤首期支持类型：
   - 灯
   - 空调
   - 窗帘
   - 音箱
   - 摄像头
   - 门锁
   - 传感器
3. 归一化字段
4. 若本地不存在则新建 `devices`
5. 写入 `device_bindings`
6. 写入审计日志

## 失败处理

- 单个实体失败不阻断整批
- 记录失败原因
- 返回同步成功数/失败数

---

## 六、审计设计

审计日志记录字段：

- actor
- action
- target_type
- target_id
- result
- details
- created_at

首期必须接入审计的接口：

- 创建家庭
- 编辑成员
- 配置关系
- 配置权限
- 新增房间
- HA 设备同步

---

## 七、接口设计原则

1. 所有接口走 `/api/v1`
2. 所有写接口必须校验管理员身份
3. 列表接口默认分页
4. 错误返回统一格式
5. 写操作成功后尽量返回最新对象

---

## 八、为什么先做这一层

因为它解决的是整个项目后续最难统一、最容易返工的部分：

- 顶层家庭模型
- 成员主数据
- 设备主数据
- 权限边界
- 房间设备映射

一旦这一层清晰，后续提醒、问答、记忆、广播、场景编排都能建立在稳定结构上。
