# 004.9 需求文档：插件来源模型降级与安装方式收口

## 背景

这次收口只解决一个真问题：旧模型把 `builtin`、`official`、`third_party`、`trusted_level`、市场源、开发目录、安装目录混在一起，结果开发源码和运行时安装目录互相踩。

当前要把模型压回最小可用状态：

- 插件类型只保留 `builtin`、`third_party`
- 安装方式只保留 `local`、`marketplace`
- `plugins-dev` 成为仓库内第三方插件开发源码目录，同时作为开发覆盖源

## 核心定义

- **内置插件（builtin）**：跟宿主一起交付，源码在 `apps/api-server/app/plugins/builtin/`
- **第三方插件（third_party）**：不跟宿主镜像强绑定，通过本地安装、市场安装或开发覆盖源参与运行
- **本地安装（local）**：运行时产物落到 `apps/api-server/data/plugins/third_party/local/`
- **市场安装（marketplace）**：运行时产物落到 `apps/api-server/data/plugins/third_party/marketplace/`
- **开发覆盖源（plugins-dev）**：仓库内第三方插件开发源码目录 `apps/api-server/plugins-dev/`，参与家庭插件注册表合并，但不写入安装态目录和挂载记录

## 需求 1：插件类型必须只保留 builtin 和 third_party

**用户故事：** 作为平台维护者，我希望插件来源模型只表达真正影响系统行为的区别，而不是继续让 `official` 污染数据库、目录和运行逻辑。

### 验收标准

1. 系统正式读写插件类型时，只允许 `builtin` 或 `third_party`
2. 旧 `official` 输入在兼容窗口内只能被映射到 `third_party`，不能再生成新的 `official` 正式逻辑
3. 正式文档和规范不能再把 `official` 当成当前插件类型

## 需求 2：第三方插件必须显式区分 local 和 marketplace

**用户故事：** 作为开发者和运维人员，我希望一眼看出第三方插件是怎么装进来的，这样目录、升级、卸载和排障都能说清楚。

### 验收标准

1. `third_party` 插件必须显式带 `install_method`
2. `install_method=local` 与 `install_method=marketplace` 分别对应各自运行时目录
3. 启动同步、清理和安装逻辑按安装方式工作，而不是按 `official`、`manual`、`trusted_level` 之类的旧词工作

## 需求 3：plugins-dev 必须成为开发覆盖源

**用户故事：** 作为插件开发者，我希望直接在仓库里改第三方插件源码，并且同名时能覆盖已安装第三方插件，这样我不用每改一次都重新安装插件。

### 验收标准

1. `apps/api-server/plugins-dev/` 会参与家庭插件注册表合并
2. 同 `plugin_id` 冲突时，优先级固定为 `builtin > plugins-dev > 已安装 third_party`
3. `plugins-dev` 可以覆盖已安装 third_party 的 manifest、runner 配置和执行入口
4. `plugins-dev` 不能覆盖 `builtin`
5. `plugins-dev` 中的开发插件即使没有安装态挂载，也可以作为开发态第三方插件进入家庭注册表

## 需求 4：plugins-dev 不能被误当成安装目录

**用户故事：** 作为平台维护者，我希望开发源码目录和运行时安装目录彻底拆开，避免安装、卸载和清理把开发源码误伤。

### 验收标准

1. `plugins-dev` 不写入 `plugin_mounts`
2. `plugins-dev` 不参与 marketplace/local 安装落盘
3. 卸载或清理安装态插件时，不删除 `plugins-dev` 下的源码
4. 启动同步只恢复安装态目录，不给 `plugins-dev` 创建挂载记录

## 需求 5：旧 official / trusted_level 语义必须退回历史兼容层

**用户故事：** 作为维护者，我希望旧数据还能迁移，但迁移完成后不再继续污染新模型。

### 验收标准

1. 数据库中的旧 `official` 与 `trusted_level` 能迁移到新模型
2. 历史目录 `official/marketplace` 能迁移或兼容到 `third_party/marketplace`
3. 迁移完成后，系统不再新增 `official`、`trusted_level` 或旧目录分支

## 需求 6：文档和规范必须统一新口径

**用户故事：** 作为后来接手的人，我希望从代码、spec、开发规范和官方文档里看到的是同一套说法，而不是一边写会加载，一边写不会加载。

### 验收标准

1. 官方开发文档明确写出 `plugins-dev` 是开发覆盖源
2. 插件规范明确写出同名优先级和目录职责
3. 历史 spec 如果仍提到 `data/plugins/official` 或 `third_party/manual`，必须显式标注为历史说明，不得继续当作当前实现指引
