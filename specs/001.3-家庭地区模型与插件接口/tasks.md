# 任务清单 - 家庭地区模型与插件接口（人话版）

状态：Draft

## 这份文档是干什么的

这份任务清单是给后续实现的人直接开工用的。

你打开任何一个任务，都应该马上知道：

- 这一步到底在建什么
- 做完以后页面、接口、数据会出现什么结果
- 需要先看哪些文档和现有文件
- 这一步故意不做什么，避免越做越散

## 状态说明

- `TODO`：还没开始
- `IN_PROGRESS`：正在做
- `BLOCKED`：被外部问题卡住
- `IN_REVIEW`：已经有结果，等复核
- `DONE`：已经完成，并且已经回写状态
- `CANCELLED`：取消，不做了，但要写原因

## 阶段 1：先把地区数据底座立住

- [ ] 1.1 建地区目录表和家庭地区绑定表
  - 状态：TODO
  - 这一步到底做什么：新增 `region_nodes` 和 `household_regions` 两张表，把家庭正式地区绑定和中国大陆目录的存储位置先建出来。
  - 做完你能看到什么：数据库里正式有地方存“标准地区节点”和“家庭当前绑定到哪个区县”。
  - 先依赖什么：无
  - 开始前先看：
    - `requirements.md` 需求 1、需求 2、需求 3
    - `design.md` §3.2「数据结构」
    - `design.md` §4.1「数据关系」
    - `apps/api-server/migrations/20260311-数据库迁移规范.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/region/`
    - `apps/api-server/app/modules/household/models.py`
    - `apps/api-server/migrations/versions/`
  - 这一步先不做什么：先不碰前端，不接天气插件，不导入海外地区。
  - 怎么算完成：
    1. `region_nodes` 和 `household_regions` 的 model 与 migration 都已落地
    2. 唯一约束、父子查询索引、一对一家庭绑定约束已经补齐
  - 怎么验证：
    - 运行 `alembic upgrade head`
    - 检查表字段、索引、约束与 `design.md` 一致
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` §3.2、§4.1、§6.1

- [ ] 1.2 做中国大陆目录导入和基础查询 service
  - 状态：TODO
  - 这一步到底做什么：导入中国大陆省 / 市 / 区县目录，并做按父节点查子节点、按编码解析路径、按关键字搜索的基础 service。
  - 做完你能看到什么：后端已经能稳定回答“这个省下面有哪些市”“这个区县属于哪条路径”。
  - 先依赖什么：1.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 4
    - `design.md` §2.3.1、§3.2.1、§3.3.1、§3.3.2
  - 主要改哪里：
    - `apps/api-server/app/modules/region/`
    - `apps/api-server/tests/`
    - `specs/001.3-家庭地区模型与插件接口/docs/`
  - 这一步先不做什么：先不做地图搜索，不做经纬度计算，不做国外目录。
  - 怎么算完成：
    1. 中国大陆目录可以按省 / 市 / 区县层级被查询
    2. 非法编码、断裂路径、重复编码都会被拒绝
  - 怎么验证：
    - 目录导入测试
    - service 单元测试
    - API 集成测试
  - 对应需求：`requirements.md` 需求 2、需求 4
  - 对应设计：`design.md` §2.3.1、§3.2.1、§3.3.1、§3.3.2、§5.3

- [ ] 1.3 阶段检查：地区底座是不是站稳了
  - 状态：TODO
  - 这一步到底做什么：检查目录表、绑定表、基础查询逻辑是不是已经可靠，不要后面一边接接口一边返工底层。
  - 做完你能看到什么：可以放心进入家庭接口改造，而不是后面再改表结构。
  - 先依赖什么：1.1、1.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关全部文件
  - 这一步先不做什么：不扩新国家，不顺手做业务插件。
  - 怎么算完成：
    1. 目录节点模型和家庭绑定模型职责清楚
    2. 查询路径、层级校验、唯一绑定规则都能被测试覆盖
  - 怎么验证：
    - 人工走查
    - 跑地区模块测试
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 4
  - 对应设计：`design.md` §2.1、§3.2、§4.1、§6.1、§6.2

## 阶段 2：把家庭接口和前端入口接上

- [ ] 2.1 扩展家庭 schema、service 和 API 返回结构
  - 状态：TODO
  - 这一步到底做什么：给家庭创建、编辑、详情接口加 `region_selection` 输入和 `region` 输出，并把兼容 `city` 的投影逻辑收口到后端。
  - 做完你能看到什么：后端正式支持区县级家庭地区绑定，同时旧客户端还能继续看到 `city`。
  - 先依赖什么：1.3
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3、需求 4
    - `design.md` §2.3.1、§2.3.2、§3.3.3、§3.3.4
    - `apps/api-server/app/modules/household/schemas.py`
    - `apps/api-server/app/modules/household/service.py`
    - `apps/api-server/app/api/v1/endpoints/households.py`
  - 主要改哪里：
    - `apps/api-server/app/modules/household/schemas.py`
    - `apps/api-server/app/modules/household/service.py`
    - `apps/api-server/app/api/v1/endpoints/households.py`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不改天气功能，不做历史家庭自动猜区县。
  - 怎么算完成：
    1. 家庭接口支持提交和返回结构化地区对象
    2. 已绑定地区的 `city` 值来自快照投影
    3. 旧家庭未绑定地区时仍然可以被读取和编辑
  - 怎么验证：
    - household API 集成测试
    - 旧数据兼容回归测试
  - 对应需求：`requirements.md` 需求 1、需求 3、需求 4
  - 对应设计：`design.md` §2.3.1、§2.3.2、§3.3.3、§3.3.4、§6.3

- [ ] 2.2 接前端地区选择器和家庭资料页面
  - 状态：TODO
  - 这一步到底做什么：把 `apps/user-web` 里的初始化向导、家庭资料展示和编辑入口改成区县级地区选择，而不是只填一个城市输入框。
  - 做完你能看到什么：用户能在页面里按省 / 市 / 区县选地区，家庭详情也能看到正式地区结构。
  - 先依赖什么：2.1
  - 开始前先看：
    - `requirements.md` 需求 1、需求 3
    - `design.md` §2.3.1、§2.3.2、§3.3.1、§3.3.4
    - `apps/user-web/src/pages/SetupWizardPage.tsx`
    - `apps/user-web/src/pages/FamilyPage.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
  - 主要改哪里：
    - `apps/user-web/src/pages/SetupWizardPage.tsx`
    - `apps/user-web/src/pages/FamilyPage.tsx`
    - `apps/user-web/src/lib/api.ts`
    - `apps/user-web/src/lib/types.ts`
    - `apps/user-web/src/state/household.tsx`
  - 这一步先不做什么：先不做地图模式，不做地区搜索弹窗的高级交互。
  - 怎么算完成：
    1. 向导和设置入口都能完成区县选择并提交
    2. 家庭详情能展示省 / 市 / 区县
    3. 旧家庭如果还没配置正式地区，页面有明确补录提示
  - 怎么验证：
    - 前端手工联调
    - 关键页面回归测试
  - 对应需求：`requirements.md` 需求 1、需求 3
  - 对应设计：`design.md` §2.3.1、§2.3.2、§3.3.1、§3.3.4

- [ ] 2.3 阶段检查：家庭主链路是不是已经跑通
  - 状态：TODO
  - 这一步到底做什么：检查从地区选择、家庭保存到家庭详情返回这条主链路是不是已经真正打通。
  - 做完你能看到什么：家庭地区不再只是设计稿，而是用户真的能配、系统真的能存、接口真的能回。
  - 先依赖什么：2.1、2.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
  - 主要改哪里：本阶段相关全部文件
  - 这一步先不做什么：不扩新业务，不追加海外地区。
  - 怎么算完成：
    1. 新家庭能绑定到中国大陆区县
    2. 旧家庭兼容读取正常
    3. 前后端字段语义一致，没有一边叫城市一边实际传区县编码的混乱
  - 怎么验证：
    - 端到端手工回放
    - API / 页面联调走查
  - 对应需求：`requirements.md` 需求 1、需求 2、需求 3
  - 对应设计：`design.md` §2.3.1、§2.3.2、§4.2、§6.1、§6.3

## 阶段 3：把插件接口和扩展点补齐

- [ ] 3.1 做地区上下文 service 和插件桥接接口
  - 状态：TODO
  - 这一步到底做什么：实现 `region.resolve_household_context` 这类统一入口，让天气、地区问答等插件能按 `household_id` 拿到标准地区上下文。
  - 做完你能看到什么：插件不再自己读 `households.city` 瞎猜，而是走统一地区服务。
  - 先依赖什么：2.3
  - 开始前先看：
    - `requirements.md` 需求 4、需求 5
    - `design.md` §2.3.3、§3.1、§3.3.5、§3.3.6
    - `apps/api-server/app/modules/plugin/`
  - 主要改哪里：
    - `apps/api-server/app/modules/region/`
    - `apps/api-server/app/modules/plugin/`
    - `apps/api-server/tests/`
  - 这一步先不做什么：先不做具体天气插件，也不做地区问答提示词细化。
  - 怎么算完成：
    1. 插件可以通过统一接口读取家庭地区上下文
    2. 未配置地区和提供方异常都有明确错误或降级结果
    3. 插件层不再依赖 `city` 文本做主判断
  - 怎么验证：
    - 插件桥接集成测试
    - service 单元测试
  - 对应需求：`requirements.md` 需求 4、需求 5
  - 对应设计：`design.md` §2.3.3、§3.1、§3.3.5、§3.3.6、§6.4

- [ ] 3.2 定义地区提供方注册机制和内置中国大陆提供方
  - 状态：TODO
  - 这一步到底做什么：把地区提供方接口、注册表和内置中国大陆实现定下来，为以后海外地区插件接入留正式入口。
  - 做完你能看到什么：第一版虽然只有中国大陆，但新增其他国家和地区时已经知道该往哪接，不用再重构家庭模型。
  - 先依赖什么：3.1
  - 开始前先看：
    - `requirements.md` 需求 2、需求 5
    - `design.md` §2.3.4、§3.1、§3.3.6、§8.2
    - `specs/004.2-插件系统与外部能力接入/design.md`
    - `specs/004.3-插件开发规范与注册表/requirements.md`
  - 主要改哪里：
    - `apps/api-server/app/modules/region/`
    - `apps/api-server/app/modules/plugin/`
    - `specs/004.3-插件开发规范与注册表/`（如需补充联动说明）
    - `specs/001.3-家庭地区模型与插件接口/docs/`
  - 这一步先不做什么：先不真的导入海外目录，也不开放第三方远程执行。
  - 怎么算完成：
    1. 地区提供方最小接口和注册方式已经明确
    2. 中国大陆提供方作为第一版内置实现可以跑通
    3. 海外地区接入不需要修改家庭绑定模型
  - 怎么验证：
    - 提供方契约测试
    - 文档走查
  - 对应需求：`requirements.md` 需求 2、需求 5
  - 对应设计：`design.md` §2.3.4、§3.1、§3.3.6、§6.4、§8.2

- [ ] 3.3 最终检查点
  - 状态：TODO
  - 这一步到底做什么：确认这个 Spec 真正把“家庭地区模型 + 中国大陆区县 + 插件地区接口 + 扩展点”四件事讲清楚了。
  - 做完你能看到什么：后续实现者可以按文档直接开工，不会再问“家庭地区到底存哪里、插件到底读什么”。
  - 先依赖什么：3.1、3.2
  - 开始前先看：
    - `requirements.md`
    - `design.md`
    - `tasks.md`
    - `docs/`
  - 主要改哪里：当前 Spec 全部文件
  - 这一步先不做什么：不再追加天气业务本身和海外地区真实数据。
  - 怎么算完成：
    1. 需求、设计、任务三份文档能互相对上
    2. 兼容策略、插件接口、扩展点都写清楚了
    3. 后续开发顺序清楚，没有先后颠倒
  - 怎么验证：
    - 人工按 Spec 逐项走查
  - 对应需求：`requirements.md` 全部需求
  - 对应设计：`design.md` 全文
