# 任务文档 - 家居接入与上下文中心

状态说明：

- `TODO`：尚未开始
- `IN_PROGRESS`：正在进行
- `DONE`：当前阶段已完成
- `BLOCKED`：被外部依赖阻塞

---

## 阶段 1：事件与上下文底座

- [ ] 1.1 创建在家事件与成员快照数据模型
  - 状态：TODO
  - 目标：建立 `presence_events`、`member_presence_state`、`context_configs` 的迁移、模型与基础仓储能力
  - 依赖：无
  - 需求关联：`requirements.md` 需求 2 / 验收 2.1、2.2、2.4；需求 3 / 验收 3.1、3.4；需求 7 / 验收 7.3
  - 设计关联：`design.md` §4.1、§4.2、§4.3、§5.1、§5.5
  - 上下文入口：
    - `requirements.md` 需求 2、需求 3、需求 7
    - `design.md` §4.1「presence_events」
    - `design.md` §4.2「member_presence_state」
    - `design.md` §4.3「context_configs」
  - 涉及产物：
    - `apps/api-server/migrations/`
    - `apps/api-server/app/modules/presence/`
    - `apps/api-server/app/modules/context/`
  - 执行说明：先把表和模型钉死，不要一上来就写一堆事件处理分支。配置结构首期统一放进 JSON，别过度设计。
  - 验收标准：
    1. 可创建并查询上述 3 类数据结构
    2. 家庭边界约束可验证
    3. 配置 JSON 可以被正确读写
  - 验证方式：
    - 迁移执行
    - ORM/仓储测试
    - 手动插入与查询验证

- [ ] 1.2 实现在家事件写入与成员快照聚合服务
  - 状态：TODO
  - 目标：接收原始事件并更新成员在家快照、房间占用和活跃成员缓存
  - 依赖：1.1
  - 需求关联：`requirements.md` 需求 2 / 验收 2.1、2.2、2.3；需求 3 / 验收 3.1、3.2、3.3、3.4；需求 4 / 验收 4.1、4.2、4.3、4.4
  - 设计关联：`design.md` §2.3.2、§2.3.3、§4.1、§4.2、§4.4、§5.2、§5.3、§5.4、§6.2、§6.3
  - 上下文入口：
    - `requirements.md` 需求 2、需求 3、需求 4
    - `design.md` §2.3.2「在家事件流」
    - `design.md` §4.4「Redis 热缓存键设计」
    - `design.md` §5.2「成员快照不变量」
    - `design.md` §5.3「房间占用不变量」
  - 涉及产物：
    - `apps/api-server/app/modules/presence/`
    - `apps/api-server/app/modules/context/`
    - `apps/api-server/app/api/v1/endpoints/`
  - 执行说明：聚合规则先追求稳定和可解释，不要急着做“聪明”的推理。冲突先按时间和置信度排，低置信度就降级。
  - 验收标准：
    1. 写入事件后可更新成员快照
    2. 房间占用和活跃成员缓存可被刷新
    3. 缓存不可用时可以降级
  - 验证方式：
    - 单元测试
    - 集成测试
    - 模拟事件回放验证

### 阶段检查点

- [ ] 1.3 上下文底座检查点
  - 状态：TODO
  - 目标：确认原始事件、当前快照和配置结构已经成型，可进入 API 层实现
  - 依赖：1.1、1.2
  - 需求关联：`requirements.md` 需求 2、需求 3、需求 4
  - 设计关联：`design.md` §2、§4、§5、§6
  - 上下文入口：
    - `requirements.md` 需求 2、需求 3、需求 4
    - `design.md` §2「架构设计」
    - `design.md` §4「数据模型」
    - `design.md` §5「正确性属性与业务不变量」
  - 涉及产物：阶段 1 全部相关文件
  - 执行说明：只检查结构闭环与降级策略，不扩展新范围。
  - 验收标准：
    1. 数据模型与聚合逻辑可追踪
    2. 已知边界条件有明确处理策略
  - 验证方式：
    - 人工走查
    - 关键测试集验证

---

## 阶段 2：上下文查询与设备动作接口

- [ ] 2.1 实现家庭上下文总览与配置接口
  - 状态：TODO
  - 目标：提供 `context overview` 与 `context configs` API，统一对前端输出家庭上下文
  - 依赖：1.3
  - 需求关联：`requirements.md` 需求 5 / 验收 5.1、5.2、5.3、5.4；需求 7 / 验收 7.2、7.4；需求 8 / 验收 8.2、8.4；需求 9 / 验收 9.1、9.2
  - 设计关联：`design.md` §3.3、§3.4、§4.3、§4.4、§5.1、§5.5、§6.3、§6.4
  - 上下文入口：
    - `requirements.md` 需求 5、需求 7、需求 8、需求 9
    - `design.md` §3.3「家庭上下文总览接口」
    - `design.md` §3.4「家庭上下文配置接口」
    - `design.md` §4.3「context_configs」
  - 涉及产物：
    - `apps/api-server/app/api/v1/endpoints/context.py`
    - `apps/api-server/app/modules/context/`
  - 执行说明：别让前端自己拼装全局状态。总览接口就是为了消灭分散查询和 UI 里的特殊情况。
  - 验收标准：
    1. 前端可以一次请求得到家庭上下文总览
    2. 配置接口能做家庭边界校验与持久化
    3. 降级状态可明确返回
  - 验证方式：
    - API 集成测试
    - curl / Postman 验证

- [ ] 2.2 实现基础设备动作执行与审计闭环
  - 状态：TODO
  - 目标：提供统一设备动作入口并打通 `Home Assistant` 执行与审计记录
  - 依赖：1.3
  - 需求关联：`requirements.md` 需求 1 / 验收 1.4；需求 6 / 验收 6.1、6.2、6.3、6.4；需求 8 / 验收 8.1、8.3；需求 9 / 验收 9.3、9.4
  - 设计关联：`design.md` §3.1、§3.5、§5.1、§5.6、§6.1
  - 上下文入口：
    - `requirements.md` 需求 1、需求 6、需求 8、需求 9
    - `design.md` §3.1「复用设备同步接口」
    - `design.md` §3.5「基础设备动作执行接口」
    - `design.md` §5.6「审计不变量」
  - 涉及产物：
    - `apps/api-server/app/modules/ha_integration/`
    - `apps/api-server/app/api/v1/endpoints/device_actions.py`
    - `apps/api-server/app/modules/audit/`
  - 执行说明：控制链路先做清晰的白名单动作和参数转换，别搞一个万能 action executor 把复杂性藏起来。
  - 验收标准：
    1. 可执行首批支持设备动作
    2. 高风险动作有权限边界
    3. 成功和失败都可审计
  - 验证方式：
    - 集成测试
    - 真实 HA 联调

### 阶段检查点

- [ ] 2.3 接口闭环检查点
  - 状态：TODO
  - 目标：确认上下文查询、配置与动作执行接口可支撑前端联调
  - 依赖：2.1、2.2
  - 需求关联：`requirements.md` 需求 1、需求 5、需求 6、需求 8、需求 9
  - 设计关联：`design.md` §3、§5、§6、§7
  - 上下文入口：
    - `requirements.md` 需求 1、需求 5、需求 6、需求 8、需求 9
    - `design.md` §3「组件与接口」
    - `design.md` §6「错误处理」
    - `design.md` §7「测试策略」
  - 涉及产物：阶段 2 全部相关文件
  - 执行说明：验证接口足够让前端吃，不新增花哨功能。
  - 验收标准：
    1. 关键接口可联调
    2. 关键异常路径有处理
  - 验证方式：
    - 联调验证
    - 关键测试集复跑

---

## 阶段 3：管理台原型与联调收口

- [x] 3.1 实现家居上下文仪表盘与配置原型页
  - 状态：DONE
  - 目标：在管理台交付一个可演示的家居上下文页面，展示家庭状态、成员状态、关键仪表盘与美观配置界面
  - 依赖：无
  - 需求关联：`requirements.md` 需求 7 / 验收 7.1、7.2、7.3、7.4
  - 设计关联：`design.md` §1.3、§3.4、§3.6、§4.5、§6.4、§7.3
  - 上下文入口：
    - `requirements.md` 需求 7
    - `design.md` §1.3「当前阶段交付策略」
    - `design.md` §3.6「管理台页面设计」
    - `design.md` §4.5「前端本地草稿结构」
  - 涉及产物：
    - `apps/admin-web/src/pages/ContextCenterPage.tsx`
    - `apps/admin-web/src/lib/contextDraft.ts`
    - `apps/admin-web/src/App.tsx`
    - `apps/admin-web/src/styles.css`
  - 执行说明：当前阶段不等后端接口全部完成，先用真实主数据 + 本地草稿把页面做出来，避免 UI 和接口一起失焦。
  - 验收标准：
    1. 页面可展示家庭状态、成员状态、房间热区、设备健康和近期活动
    2. 页面可配置家庭模式、成员状态和房间策略
    3. 配置可在浏览器刷新后恢复
  - 验证方式：
    - `npm run build`
    - 手工切换家庭与刷新页面验证

- [ ] 3.2 将原型页切换到后端上下文接口并补齐联调文档
  - 状态：TODO
  - 目标：把前端从本地草稿模式切换为后端 `context overview / context configs`，并形成联调说明
  - 依赖：2.3、3.1
  - 需求关联：`requirements.md` 需求 5 / 验收 5.1、5.2；需求 7 / 验收 7.2、7.4；需求 8 / 验收 8.3、8.4
  - 设计关联：`design.md` §3.3、§3.4、§3.6、§6.4、§7.4
  - 上下文入口：
    - `requirements.md` 需求 5、需求 7、需求 8
    - `design.md` §3.3「家庭上下文总览接口」
    - `design.md` §3.4「家庭上下文配置接口」
    - `design.md` §7.4「人工联调」
  - 涉及产物：
    - `apps/admin-web/src/lib/api.ts`
    - `apps/admin-web/src/pages/ContextCenterPage.tsx`
    - `specs/002-家居接入与上下文中心/docs/`
  - 执行说明：只替换数据来源，不推翻现有 UI 结构。页面结构已经定了，别重写。
  - 验收标准：
    1. 前端读取真实上下文总览接口
    2. 配置保存到后端并可重新加载
    3. 联调说明完整可执行
  - 验证方式：
    - 前后端联调
    - 文档走查

### 最终检查点

- [ ] 3.3 最终检查点
  - 状态：TODO
  - 目标：确认家居接入与上下文中心满足可交付条件，可继续支撑后续问答、提醒和场景编排
  - 依赖：3.2
  - 需求关联：`requirements.md` 全部需求
  - 设计关联：`design.md` 全文
  - 上下文入口：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 涉及产物：当前 Spec 全部文件
  - 执行说明：核对需求、设计、任务、原型、接口、联调说明和已知风险，不再追加范围。
  - 验收标准：
    1. 需求到设计到任务可完整追踪
    2. 前端和后端边界清晰
    3. 已知延期项和风险已记录
  - 验证方式：
    - Spec 走查
    - 联调结果复核
