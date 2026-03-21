# 004.9 需求文档：插件来源模型降级与安装方式收口

## 背景

这次收口解决的是一个非常实际的问题：旧模型把 `builtin`、`official`、`third_party`、`trusted_level`、市场源、开发目录和安装目录混成一团，结果开发源码和运行时安装产物互相踩。

这次要把模型压回最小可用状态：

- 插件来源只保留 `builtin` 和 `third_party`
- 安装方式只保留 `local` 和 `marketplace`
- `plugins-dev` 成为仓库内第三方插件开发源码目录，并参与加载
- 同 `plugin_id` 的开发版和已安装版不再互相隐藏，而是并存可见、互斥启用

## 核心定义

- **内置插件（builtin）**：跟宿主一起交付，源码在 `apps/api-server/app/plugins/builtin/`
- **第三方插件（third_party）**：不跟宿主镜像强绑定，通过本地安装、市场安装或开发源码目录参与运行
- **本地安装（local）**：运行时产物落到 `apps/api-server/data/plugins/third_party/local/`
- **市场安装（marketplace）**：运行时产物落到 `apps/api-server/data/plugins/third_party/marketplace/`
- **开发源码目录（plugins-dev）**：仓库内第三方插件开发源码目录 `apps/api-server/plugins-dev/`；会参与插件发现，但不属于安装目录

## 需求 1：插件来源模型必须只保留 builtin 和 third_party

**用户故事：**
作为平台维护者，我希望插件来源模型只表达真正影响系统行为的区别，而不是继续让 `official` 污染数据库、目录和运行逻辑。

### 验收标准

1. 系统正式读写插件来源时，只允许 `builtin` 或 `third_party`
2. 旧 `official` 只允许在兼容迁移层被映射到 `third_party`
3. 正式文档和规范不再把 `official` 当成当前来源类型

## 需求 2：第三方插件必须显式区分 local 和 marketplace

**用户故事：**
作为开发者和运维人员，我希望一眼看出第三方插件是怎么装进来的，这样目录、升级、卸载和排障都能说清楚。

### 验收标准

1. `third_party` 插件必须显式带 `install_method`
2. `install_method=local` 和 `install_method=marketplace` 分别对应各自运行时目录
3. 启动同步、清理和安装逻辑按安装方式工作，而不是再按 `official`、`manual` 或 `trusted_level` 之类旧词工作

## 需求 3：plugins-dev 必须成为可加载的开发源码目录

**用户故事：**
作为插件开发者，我希望直接在仓库里改第三方插件源码，并且开发版可以和已安装版同时留在系统里，方便我来回切换验证。

### 验收标准

1. `apps/api-server/plugins-dev/` 会参与插件发现和家庭插件注册表构建
2. 当 `plugins-dev` 和已安装 third_party 的 `plugin_id` 相同时，插件管理页必须同时显示“开发版”和“已安装版”
3. 同一个 `plugin_id` 在同一时刻只允许启用一个变体
4. 默认仍优先开发版，方便联调
5. 想测试正式安装版时，可以直接切换启用，不需要手动移动 `plugins-dev` 目录
6. 当前实际生效的是开发版时，前端必须明确显示“开发插件生效中”
7. 前端必须能区分开发版和已安装版，不能只靠来源字段糊过去
8. `plugins-dev` 不能覆盖 `builtin`

## 需求 4：plugins-dev 不能被误当成安装目录

**用户故事：**
作为平台维护者，我希望开发源码目录和运行时安装目录彻底拆开，避免安装、卸载和清理误伤开发源码。

### 验收标准

1. `plugins-dev` 不写入 `plugin_mounts`
2. `plugins-dev` 不参与 `marketplace` / `local` 安装落盘
3. 卸载或清理安装态插件时，不删除 `plugins-dev` 下的源码
4. 启动同步只恢复安装态目录，不给 `plugins-dev` 创建挂载记录

## 需求 5：旧 official / trusted_level 语义必须退回历史兼容层

**用户故事：**
作为维护者，我希望旧数据还能迁移，但迁移完成后不再继续污染新模型。

### 验收标准

1. 数据库中的旧 `official` 和 `trusted_level` 能迁移到新模型
2. 历史目录 `official/marketplace` 能迁移或兼容到 `third_party/marketplace`
3. 迁移完成后，系统不再新增 `official`、`trusted_level` 或旧目录分支

## 需求 6：文档和规范必须统一新口径

**用户故事：**
作为后续接手的人，我希望从代码、spec、开发规范和官方文档里看到的是同一套说法，而不是一边写并存可见，一边又写成开发版会把安装版挤没。

### 验收标准

1. 官方开发文档明确写清 `plugins-dev` 会被加载
2. 官方开发文档明确写清第三方同名冲突时是“开发版 / 已安装版并存可见、互斥启用、默认开发版”
3. 官方开发文档明确写清测试安装版时不需要手动移动 `plugins-dev`
4. 插件规范明确写出前端需要区分开发版和已安装版，并显式显示“开发插件生效中”
5. 历史 spec 如果仍提到 `data/plugins/official` 或 `third_party/manual`，必须明确标成历史说明
