<p align="center">
  <img src="apps/user-app/logo/familyclaw-logo.svg" alt="FamilyClaw Logo" width="120" />
</p>

<h1 align="center">FamilyClaw</h1>

<p align="center">
  <strong>一个真正以「家人」为中心的家庭 AI 操作系统</strong><br/>
  <strong>A Family-First Home AI Operating System</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-blue" alt="Version" />
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="Python" />
  <img src="https://img.shields.io/badge/node-20+-green" alt="Node" />
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="License" />
  <img src="https://img.shields.io/badge/platforms-Web%20%7C%20iOS%20%7C%20Android%20%7C%20HarmonyOS-brightgreen" alt="Platforms" />
</p>

<p align="center">
  官网：<a href="https://familyclaw.cc">familyclaw.cc</a> |
  官方文档：<a href="https://docs.familyclaw.cc">docs.familyclaw.cc</a> |
  官方交流群：964063018
</p>

---

[中文](#中文) | [English](#english)

---

# 中文

## 这是什么？

FamilyClaw 不是又一个智能音箱 App，也不是一个冷冰冰的设备控制面板。

它是一个**懂你全家的 AI 管家** —— 认识每个家庭成员，记住你们的偏好和习惯，在日常生活中默默守护你的家。

传统的智能家居平台以「设备」为中心：灯、空调、传感器。FamilyClaw 把视角翻转过来 —— **家人才是主角，设备只是工具**。它认识你、了解你，随着时间推移越来越懂你的家。

## 我们的愿景

> 让每一个家庭都拥有一位有温度、有记忆、有个性的 AI 管家。
> 不需要学习复杂的操作，不需要对着音箱喊固定的口令。
> 只要自然地生活，AI 就能理解你的需求，照顾你的家人。

我们相信，家庭 AI 不应该是科技发烧友的专属玩具，而应该是每一位家庭成员都能舒服使用的贴心助手 —— 无论是忙碌的父母、正在成长的孩子，还是需要关怀的老人。

## 项目功能

### 家庭成员管理

- **多成员识别**：通过声纹（已实现）、人脸（开发中）、蓝牙（计划中）等方式自动识别「现在是谁在说话」
- **成员画像**：每个人都有独立的偏好、权限和互动记录
- **角色与权限**：为父母、孩子、老人、访客设置不同的使用权限
- **亲属关系**：AI 理解家庭成员之间的关系，对话更自然

### AI 管家对话

- **本地大模型深度适配** —— 让 Ollama 等本地模型发挥最大能力，完全离线也能用
- **多角色 AI 助手**：管家、营养师、健身教练、学习辅导...... 你的家庭成员各取所需
- **人格化设计**：每个 AI 角色有自己的性格、说话风格和服务边界
- **实时对话**：基于 WebSocket 的流式响应，和 AI 的对话流畅自然
- **智能提案**：AI 会在对话中主动建议行动（比如「要不要帮你设个提醒？」），你确认后自动执行
- **主动关怀**：通过计划任务和心跳机制，AI管家会提醒你的会议日程，提醒老人吃药，提醒孩子的网课

### 家庭长期记忆

这是 FamilyClaw 最核心的能力之一。

- **六种记忆类型**：事实、事件、偏好、关系、成长、观察 —— 完整刻画家庭生活
- **越用越懂你**：AI 会从日常对话中提取有价值的信息，形成家庭记忆
- **隐私分层**：公开、家庭可见、仅自己可见、敏感信息 —— 你的隐私你做主
- **语义搜索**：通过向量嵌入实现智能检索，问什么都能找到相关记忆

### 智能家居控制

- **Home Assistant 接入**：无缝对接 Home Assistant 生态，几千种设备即接即用
- **小米生态**：专门适配小米智能家居设备（通过HA进行桥接）
- **对话式控制**：不用打开设备面板，直接对 AI 说「把客厅灯调暗一点」
- **设备感知**：AI 实时了解所有设备状态，回答更精准
- **智能场景**：随着AI管家对你的家庭的了解加深，后续会更加主动的根据家庭的状态、人员的状态智能调节智能家居（开发中）

### 场景自动化（开发中）

- **智能回家**：识别到家人回家，自动开灯、播报欢迎消息
- **儿童睡前**：到了睡觉时间自动调低音量、发送温馨提醒
- **老人关怀**：定时问候、用药提醒，让子女安心
- **安全守护**：静默时段保护、儿童内容过滤、隐私区域限制

### 定时任务与提醒

- **对话式创建**：聊天中说一句「明天早上 8 点提醒我吃药」，AI 自动创建提醒
- **灵活调度**：支持单次、重复、自定义周期
- **升级提醒**：重要事项无人响应时自动升级通知方式

### 多平台覆盖

- **网页端**（H5）：打开浏览器就能用
- **iOS / Android**：原生移动体验
- **鸿蒙**（HarmonyOS）：支持华为生态（开发中）
- **即时通讯接入**：钉钉、飞书、企业微信（开发中）、Discord（开发中）、Telegram —— 在你常用的 App 里就能和家庭 AI 对话

### 插件生态

FamilyClaw 拥有一套成熟的插件系统，目前内置 **32+ 个插件**：

| 类型 | 数量 | 示例 |
|------|------|------|
| AI 供应商 | 14 个 | ChatGPT、Claude、Deepseek、通义千问、豆包、Kimi、智谱 GLM、Gemini 等 |
| 通讯渠道 | 6 个 | 钉钉、飞书、企业微信、Discord、Telegram |
| 主题包 | 8 个 | 春和景明、风驰电掣、锦绣前程、星河万里...... |
| 语言包 | 1 个 | 繁体中文 |
| 设备集成 | 2 个 | Home Assistant、小爱音箱 |
| 健康服务 | 1 个 | 基础健康数据 |

支持从插件市场一键安装，也支持 ZIP 手动上传。第三方插件在安全沙箱中运行，不影响主系统稳定性。
支持开发者生态，提供完整的开发文档和规范，开发者可以快速上手进行插件开发，哪怕你是不懂开发的普通人，也可以通过AI来实现快速开发！

## 项目亮点

**本地优先，安全第一**
9-14B模型即可稳定运行大部分功能，家用级设备友好，可以做到数据完全本地化。

**家人优先，设备其次**
不是先买设备再配 App，而是先了解家人再服务生活。

**AI 有记忆，不健忘**
不同于每次对话都是「初次见面」的通用 AI，FamilyClaw 的 AI 真正记住你的家。

**多角色 AI，各司其职**
管家处理日常事务，营养师关注饮食健康，健身教练督促锻炼 —— 一个系统，多位专家。

**声纹识别，开口即知**
不用先解锁手机或报上名字，AI 听到声音就知道是谁。

**本地化语音处理**
语音识别和声纹比对在本地完成，你的语音数据不会上传到云端。

**灵活的 AI 供应商**
支持 14 种 AI 供应商，本地 Ollama 和云端 API 随意切换，可设置自动回退策略。

**全平台覆盖**
一套系统，Web、iOS、Android、鸿蒙全支持。还能在钉钉、飞书、Telegram 里直接使用。

**Docker 一键部署**
一条命令完成安装，自带数据库、反向代理和进程管理，适合家庭服务器和 NAS。

## 开发路线图

### 正在做的事

- **分层长期记忆优化** —— 让 AI 的记忆更智能，重要的事情永远不忘，琐碎的信息自动淡化
- **对话式设备控制升级** —— 更自然的语音/文字设备控制，支持复合指令
- **更多通讯渠道** —— 微信个人号、LINE 等平台的接入
- **成员画像增强** —— 实时感知家庭成员状态，AI 服务更贴心
- **视频流接入** —— 通过接入视频信息，让AI更加了解你的家庭

### 下一步计划

- **记忆知识图谱** —— 家庭记忆不再是零散的卡片，而是构建成可视化的知识网络
- **插件市场正式上线** —— 完善版本管理和自动更新，社区贡献的插件一键安装
- **智能场景推荐** —— AI 根据家庭生活模式，主动推荐自动化场景
- **多家庭协同** —— 父母和子女的家庭之间建立连接，异地关怀更便捷
- **儿童成长追踪** —— 记录学习进度、兴趣变化，帮助家长更好地了解孩子
- **健康管理进阶** —— 对接健康设备，追踪运动数据和健康指标

## 安装指南

### 方式一：Docker 部署（推荐）

这是最简单的安装方式，适合大多数用户。

**准备工作：**
- 一台能运行 Docker 的设备（家用电脑、NAS、树莓派都行）
- 至少 2GB 内存

**安装步骤：**

```bash
# 1. 如果你已经有docker应用程序，一条命令即可运行
docker run -d \
  --name familyclaw \
  -p 8080:8080 \
  -p 4399:4399 \
  -v /srv/familyclaw-data:/data \
  jingyi0605/familyclaw:0.1.0

# 2. 等待服务启动（约 60 秒），然后打开浏览器访问
# http://你的设备IP:8080
```

**初始账号：**
- 管理员：`user` / `user`（初始化后即失效）

### 方式二：本地开发部署

适合想自己折腾的技术用户。

**前置要求：**
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+

```bash
# 1. 克隆项目
git clone https://github.com/your-org/familyclaw.git
cd familyclaw

# 2. 配置数据库
# 创建 PostgreSQL 数据库：familyclaw，用户：familyclaw

# 3. 启动后端
cp apps/api-server/.env.example apps/api-server/.env
# 修改 .env 中的数据库连接信息
cd apps
bash start-api-server.sh
# 脚本会自动创建虚拟环境、安装依赖、运行数据库迁移
# 请在 Git Bash 中执行；Windows 上如果 PATH 里只有 py，脚本会自动回退到 py -3.11

# 4. 启动前端（新开一个终端）
cd ..  # 回到项目根目录
npm install --legacy-peer-deps
npm run dev:user-app:h5

# 5. 打开浏览器访问 http://localhost:10086（或终端提示的地址）
```

### 方式三：连接小爱音箱（可选）

如果你有小米的小爱音箱，可以启动网关让 AI 管家通过小爱音箱说话：

```bash
cd apps
bash start-open-xiaoai-gateway.sh
# 请在 Git Bash 中执行；Windows 上如果 PATH 里只有 py，脚本也会自动识别
```

### 关键配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `FAMILYCLAW_DATABASE_URL` | PostgreSQL 数据库地址 | Docker 首次启动自动生成随机密码，并持久化到 `/data/runtime/secrets/db-password` |
| `FAMILYCLAW_HOME_ASSISTANT_BASE_URL` | Home Assistant 地址 | `http://127.0.0.1:8123` |
| `FAMILYCLAW_HOME_ASSISTANT_TOKEN` | Home Assistant 长期访问令牌 | 需要手动填写 |
| `FAMILYCLAW_AI_DEFAULT_PROVIDER_CODE` | 默认 AI 供应商 | `local-ollama` |
| `FAMILYCLAW_VOICE_RUNTIME_MODE` | 语音模式 | `embedded`（本地处理） |

## 插件开发指南

FamilyClaw 欢迎社区开发者贡献插件！以下是快速入门。

### 插件能做什么？

| 插件类型 | 用途 | 举例 |
|----------|------|------|
| `ai-provider` | 接入新的 AI 大模型 | 接入一个新的国产大模型 |
| `channel` | 接入新的通讯平台 | 微信个人号接入 |
| `integration` | 对接外部设备/服务 | 对接扫地机器人 |
| `action` | 添加可执行的操作 | 自动浇花 |
| `agent-skill` | 给 AI 助手添加新技能 | 教 AI 查天气 |
| `locale-pack` | 添加新语言 | 日语支持 |
| `theme-pack` | 添加新主题 | 自定义配色 |
| `region-provider` | 提供地区数据 | 本地天气/地理信息 |

### 快速开始

**1. 创建插件目录**

```
my-awesome-plugin/
├── manifest.json        # 插件描述文件（必须）
├── __init__.py          # 入口代码（必须）
├── config_specs.json    # 配置表单定义（可选）
└── README.md            # 插件说明
```

**2. 编写 manifest.json**

```json
{
  "id": "my-awesome-plugin",
  "name": "我的插件",
  "version": "1.0.0",
  "api_version": "1",
  "types": ["action"],
  "description": "一个示例插件",
  "entrypoints": {
    "action": "my_module:execute"
  },
  "risk_level": "low"
}
```

**3. 编写插件逻辑**

```python
async def execute(context, params):
    """插件的主要逻辑"""
    # context 包含家庭信息、设备状态等上下文
    # params 包含调用参数
    return {"status": "ok", "message": "执行成功！"}
```

**4. 安装测试**

将插件目录压缩为 ZIP，在「插件管理」页面上传安装。第三方插件以子进程模式运行，安装后即刻生效，无需重启服务。

### 深入学习

完整的插件开发文档在 `docs/开发者文档/插件开发/` 目录下：

| 文档 | 内容 |
|------|------|
| [01 - 插件开发总览](docs/开发者文档/插件开发/zh-CN/01-插件开发总览.md) | 架构设计和边界说明 |
| [03 - manifest 字段规范](docs/开发者文档/插件开发/zh-CN/03-manifest字段规范.md) | manifest.json 完整字段说明 |
| [04 - 目录结构规范](docs/开发者文档/插件开发/zh-CN/04-插件目录结构规范.md) | 推荐的文件组织方式 |
| [06 - 从零开发插件](docs/开发者文档/插件开发/zh-CN/06-从零开发一个可运行插件.md) | 手把手教程 |
| [11 - 配置接入说明](docs/开发者文档/插件开发/zh-CN/11-插件配置接入说明.md) | 动态配置表单开发 |
| [12 - 类型与接口总表](docs/开发者文档/插件开发/zh-CN/12-V1插件类型与接口总表.md) | 所有插件类型的完整接口参考 |

## 项目架构

```
FamilyClaw/
├── apps/
│   ├── api-server/          # Python 后端（FastAPI + SQLAlchemy）
│   │   ├── app/
│   │   │   ├── modules/     # 业务模块（成员、对话、记忆、设备、插件...）
│   │   │   └── plugins/     # 内置插件（32+）
│   │   └── migrations/      # 数据库迁移（Alembic）
│   ├── user-app/            # 跨平台前端（Taro + React + TypeScript）
│   └── open-xiaoai-gateway/ # 设备网关
├── packages/
│   ├── user-core/           # 前端公共库（类型定义、服务层）
│   ├── user-platform/       # 平台适配层
│   └── user-ui/             # UI 组件库
├── docs/                    # 项目文档（VitePress 驱动）
├── specs/                   # 功能规格书（50+ 篇）
├── docker/                  # Docker 部署配置
└── Dockerfile               # 一键构建镜像
```

## 鸣谢

FamilyClaw 的诞生离不开以下优秀的开源项目：

### 核心依赖

- **[FastAPI](https://github.com/tiangolo/fastapi)** — 高性能 Python Web 框架，支撑了整个后端 API
- **[SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy)** — 强大的数据库 ORM
- **[Taro](https://github.com/NervJS/taro)** — 跨平台前端框架，一套代码运行在 Web、iOS、Android、鸿蒙
- **[React](https://github.com/facebook/react)** — 用户界面构建库
- **[Alembic](https://github.com/sqlalchemy/alembic)** — 数据库迁移管理

### 智能能力

- **[Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)** — 本地语音识别与声纹比对引擎
- **[Home Assistant](https://github.com/home-assistant/core)** — 开源智能家居平台
- **[open-xiaoai](https://github.com/idootop/open-xiaoai)** — 让小爱音箱「听见你的声音」，解锁无限可能。

### 参考项目

- **[OpenClaw](https://github.com/openclaw/openclaw)** (MIT License) — 个人 AI 助手项目，FamilyClaw 在通讯渠道插件设计上参考了其优秀的架构理念

### 基础设施

- **[PostgreSQL](https://www.postgresql.org/)** — 可靠的关系型数据库
- **[Nginx](https://nginx.org/)** — 高性能反向代理
- **[VitePress](https://vitepress.dev/)** — 文档站点生成器
- **[Docker](https://www.docker.com/)** — 容器化部署

## 参与贡献

FamilyClaw 是一个充满热情的项目，欢迎各种形式的贡献：

- 提交 Bug 报告或功能建议
- 开发新的插件（AI 供应商、通讯渠道、主题包等）
- 改进文档和翻译
- 分享使用经验

## 联系我们

如果你对 FamilyClaw 感兴趣，或者在使用中遇到问题，欢迎通过 Issue 与我们交流。

---

# English

## What is FamilyClaw?

FamilyClaw is not just another smart home app or a cold device control panel.

It is an **AI butler that truly knows your family** — it recognizes every family member, remembers your preferences and habits, and quietly takes care of your home in everyday life.

Traditional smart home platforms center around **devices**: lights, thermostats, sensors. FamilyClaw flips the perspective — **your family members are the protagonists, devices are just tools**. It knows you, understands you, and grows to know your family better over time.

## Our Vision

> Give every family a warm, thoughtful, personalized AI butler.
> No complicated setups. No rigid voice commands.
> Just live naturally, and the AI understands your needs and cares for your family.

We believe home AI shouldn't be a toy for tech enthusiasts only — it should be a caring assistant that every family member can comfortably use, whether it's busy parents, growing children, or elderly relatives who need extra care.

## Features

### Family Member Management

- **Multi-member identification**: Automatically recognizes "who's talking" via voiceprint, facial recognition, and Bluetooth
- **Individual profiles**: Each member has their own preferences, permissions, and interaction history
- **Role-based access**: Different permission levels for parents, children, elders, and guests
- **Family relationships**: AI understands family dynamics for more natural conversations

### AI Butler Conversations

- **Deep local model adaptation**: Help local models such as Ollama deliver their best performance, with full offline availability
- **Multi-persona AI assistants**: Butler, Nutritionist, Fitness Coach, Study Coach — each family member gets the help they need
- **Personality design**: Every AI persona has its own character, speaking style, and service boundaries
- **Real-time chat**: WebSocket-based streaming responses for smooth, natural conversations
- **Smart proposals**: AI proactively suggests actions during conversations (e.g., "Shall I set a reminder for that?"), executed after your confirmation
- **Proactive care**: Through scheduled tasks and heartbeat-style checks, the AI butler can remind you about meetings, remind elders to take medicine, and remind children about online classes

### Long-Term Family Memory

This is one of FamilyClaw's most powerful capabilities.

- **Six memory types**: Facts, Events, Preferences, Relations, Growth, Observations — a complete portrait of family life
- **Gets smarter over time**: AI extracts valuable information from daily conversations to build family memory
- **Privacy layers**: Public, Family-visible, Private, Sensitive — you control your privacy
- **Semantic search**: Vector embedding-powered smart retrieval finds relevant memories for any query

### Smart Home Control

- **Home Assistant integration**: Seamless connection with the Home Assistant ecosystem — thousands of devices ready to use
- **Xiaomi ecosystem**: Purpose-built support for Xiaomi smart home devices through Home Assistant bridging
- **Conversational control**: Just tell the AI "dim the living room lights" instead of opening a device panel
- **Device awareness**: AI has real-time knowledge of all device states for more accurate responses
- **Smart scenes**: As the AI butler learns more about your household and the status of your family members, it can gradually make smarter, more proactive home adjustments (in development)

### Scene Automation (In Development)

- **Smart Homecoming**: Detects family members arriving home, automatically turns on lights and announces a welcome
- **Child Bedtime**: Automatically lowers volume and sends gentle reminders at bedtime
- **Elder Care**: Scheduled check-ins and medication reminders to give adult children peace of mind
- **Safety Guards**: Quiet hours protection, child content filtering, and privacy zone restrictions

### Scheduled Tasks & Reminders

- **Conversational creation**: Say "remind me to take medicine at 8 AM tomorrow" in a chat, and AI creates the reminder automatically
- **Flexible scheduling**: One-time, recurring, or custom intervals
- **Escalation**: Automatically increases notification urgency for unacknowledged reminders

### Multi-Platform Support

- **Web (H5)**: Open a browser and start using it
- **iOS / Android**: Native mobile experience
- **HarmonyOS**: Huawei ecosystem support (in development)
- **Messaging integrations**: DingTalk, Feishu, WeCom (in development), Discord (in development), Telegram — chat with your family AI right in the apps you already use

### Plugin Ecosystem

FamilyClaw features a mature plugin system with **32+ built-in plugins**:

| Type | Count | Examples |
|------|-------|---------|
| AI Providers | 14 | ChatGPT, Claude, Deepseek, Qwen, Doubao, Kimi, GLM, Gemini, etc. |
| Channels | 6 | DingTalk, Feishu, WeCom, Discord, Telegram |
| Themes | 8 | Spring Breeze, Lightning Speed, Starry Night, and more |
| Locale Packs | 1 | Traditional Chinese |
| Device Integrations | 2 | Home Assistant, Xiaomi Speaker |
| Health Services | 1 | Basic health data |

Plugins can be installed with one click from the marketplace or manually uploaded as ZIP files. Third-party plugins run in a secure sandbox without affecting system stability.
The project also supports a developer ecosystem with complete documentation and conventions, so contributors can get started quickly. Even non-developers can use AI assistance to build plugins faster.

## Highlights

**Local First, Security First**
Most features can run reliably on 9B-14B models, making FamilyClaw friendly to household-grade hardware while keeping data fully local.

**Family First, Devices Second**
Instead of starting with devices and fitting people around them, FamilyClaw starts with understanding your family and serving their lives.

**AI with Memory**
Unlike generic AI assistants that "meet you for the first time" every conversation, FamilyClaw's AI truly remembers your family.

**Multi-Persona AI Team**
A butler handles daily affairs, a nutritionist watches your diet, a fitness coach keeps you active — one system, multiple experts.

**Voiceprint Recognition**
No need to unlock your phone or introduce yourself — the AI knows who you are just by hearing your voice.

**Local Voice Processing**
Voice recognition and voiceprint matching happen locally. Your voice data never leaves your home.

**Flexible AI Providers**
14 AI providers supported. Switch freely between local Ollama and cloud APIs, with automatic fallback strategies.

**True Cross-Platform**
One system covering Web, iOS, Android, and HarmonyOS. Plus chat directly through DingTalk, Feishu, or Telegram.

**One-Command Docker Deployment**
A single command installs everything — database, reverse proxy, and process management included. Perfect for home servers and NAS devices.

## Roadmap

### Currently Working On

- **Hierarchical memory optimization** — Smarter memory management: important things are never forgotten, trivial info fades naturally
- **Conversational device control upgrade** — More natural voice/text device control with compound commands
- **More messaging channels** — WeChat personal account, LINE, and more
- **Enhanced member profiles** — Real-time awareness of family member status for more caring AI service
- **Video stream integration** — Help the AI understand your household better by bringing in video information

### What's Next

- **Memory knowledge graph** — Transform scattered memory cards into a visual knowledge network
- **Plugin marketplace launch** — Version management, auto-updates, and one-click community plugin installation
- **Smart scene recommendations** — AI proactively suggests automation scenes based on your family's living patterns
- **Multi-household collaboration** — Connect parents' and children's households for easier long-distance caring
- **Child growth tracking** — Record learning progress and interest changes to help parents understand their children better
- **Advanced health management** — Connect health devices, track fitness data and health indicators

## Installation Guide

### Option 1: Docker Deployment (Recommended)

The simplest installation method, suitable for most users.

**Prerequisites:**
- A device that can run Docker (home PC, NAS, Raspberry Pi, etc.)
- At least 2GB of RAM

**Steps:**

```bash
# 1. If you already have Docker installed, one command is enough
docker run -d \
  --name familyclaw \
  -p 8080:8080 \
  -p 4399:4399 \
  -v /srv/familyclaw-data:/data \
  jingyi0605/familyclaw:0.1.0

# 2. Wait for startup (~60 seconds), then open your browser
# http://your-device-ip:8080
```

**Default credentials:**
- Admin: `user` / `user` (invalid immediately after initialization)

### Option 2: Local Development Setup

For tech-savvy users who want to tinker.

**Requirements:**
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+

```bash
# 1. Clone the project
git clone https://github.com/your-org/familyclaw.git
cd familyclaw

# 2. Set up the database
# Create a PostgreSQL database: familyclaw, user: familyclaw

# 3. Start the backend
cp apps/api-server/.env.example apps/api-server/.env
# Edit database connection info in .env
cd apps
bash start-api-server.sh
# The script auto-creates a virtual environment, installs dependencies, and runs migrations
# Run this in Git Bash; on Windows the script also falls back to py -3.11 when python is not on PATH

# 4. Start the frontend (in a new terminal)
cd ..  # Back to project root
npm install --legacy-peer-deps
npm run dev:user-app:h5

# 5. Open your browser at http://localhost:10086 (or the address shown in your terminal)
```

### Option 3: Xiaomi Speaker Integration (Optional)

If you have a Xiaomi XiaoAI speaker, start the gateway to let the AI butler speak through it:

```bash
cd apps
bash start-open-xiaoai-gateway.sh
# Run this in Git Bash; on Windows the script also detects py automatically
```

### Key Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `FAMILYCLAW_DATABASE_URL` | PostgreSQL connection string | Docker auto-generates a random password on first start and stores it in `/data/runtime/secrets/db-password` |
| `FAMILYCLAW_HOME_ASSISTANT_BASE_URL` | Home Assistant URL | `http://127.0.0.1:8123` |
| `FAMILYCLAW_HOME_ASSISTANT_TOKEN` | Home Assistant long-lived access token | Must be set manually |
| `FAMILYCLAW_AI_DEFAULT_PROVIDER_CODE` | Default AI provider | `local-ollama` |
| `FAMILYCLAW_VOICE_RUNTIME_MODE` | Voice processing mode | `embedded` (local) |

## Plugin Development Guide

FamilyClaw welcomes community developers to contribute plugins! Here's how to get started.

### What Can Plugins Do?

| Plugin Type | Purpose | Example |
|-------------|---------|---------|
| `ai-provider` | Connect new AI models | Add a new LLM provider |
| `channel` | Connect new messaging platforms | WeChat personal account |
| `integration` | Interface with external devices/services | Robot vacuum integration |
| `action` | Add executable operations | Auto-watering plants |
| `agent-skill` | Add new skills to AI assistants | Teach AI to check weather |
| `locale-pack` | Add new languages | Japanese support |
| `theme-pack` | Add new themes | Custom color schemes |
| `region-provider` | Provide regional data | Local weather/geo info |

### Quick Start

**1. Create the plugin directory**

```
my-awesome-plugin/
├── manifest.json        # Plugin descriptor (required)
├── __init__.py          # Entry code (required)
├── config_specs.json    # Config form definition (optional)
└── README.md            # Plugin documentation
```

**2. Write manifest.json**

```json
{
  "id": "my-awesome-plugin",
  "name": "My Awesome Plugin",
  "version": "1.0.0",
  "api_version": "1",
  "types": ["action"],
  "description": "An example plugin",
  "entrypoints": {
    "action": "my_module:execute"
  },
  "risk_level": "low"
}
```

**3. Write plugin logic**

```python
async def execute(context, params):
    """Main plugin logic"""
    # context includes family info, device state, etc.
    # params includes invocation parameters
    return {"status": "ok", "message": "Success!"}
```

**4. Install and test**

Compress your plugin directory into a ZIP file and upload it via the Plugin Management page. Third-party plugins run in subprocess mode — they take effect immediately without restarting the server.

### Learn More

Complete plugin development docs are available in `docs/开发者文档/插件开发/`:

| Document | Content |
|----------|---------|
| [01 - Plugin Development Overview](docs/开发者文档/插件开发/en/01-plugin-development-overview.md) | Architecture and boundary explanation |
| [03 - Manifest Specification](docs/开发者文档/插件开发/en/03-manifest-spec.md) | Complete manifest.json field reference |
| [04 - Directory Structure](docs/开发者文档/插件开发/en/04-plugin-directory-structure.md) | Recommended file organization |
| [06 - Build a Plugin Walkthrough](docs/开发者文档/插件开发/en/06-build-a-runnable-plugin-walkthrough.md) | Step-by-step tutorial |
| [11 - Configuration Integration](docs/开发者文档/插件开发/en/11-plugin-configuration-integration.md) | Dynamic config form development |
| [12 - Plugin Types & Contracts](docs/开发者文档/插件开发/en/12-v1-plugin-types-and-contracts.md) | Complete interface reference for all plugin types |

## Project Architecture

```
FamilyClaw/
├── apps/
│   ├── api-server/          # Python backend (FastAPI + SQLAlchemy)
│   │   ├── app/
│   │   │   ├── modules/     # Business modules (members, chat, memory, devices, plugins...)
│   │   │   └── plugins/     # Built-in plugins (32+)
│   │   └── migrations/      # Database migrations (Alembic)
│   ├── user-app/            # Cross-platform frontend (Taro + React + TypeScript)
│   └── open-xiaoai-gateway/ # Xiaomi Speaker gateway
├── packages/
│   ├── user-core/           # Shared frontend library (types, services)
│   ├── user-platform/       # Platform adaptation layer
│   └── user-ui/             # UI component library
├── docs/                    # Project documentation (powered by VitePress)
├── specs/                   # Feature specifications (50+)
├── docker/                  # Docker deployment config
└── Dockerfile               # One-command image build
```

## Acknowledgments

FamilyClaw wouldn't exist without these amazing open-source projects:

### Core Dependencies

- **[FastAPI](https://github.com/tiangolo/fastapi)** — High-performance Python web framework powering the entire backend API
- **[SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy)** — Powerful database ORM
- **[Taro](https://github.com/NervJS/taro)** — Cross-platform frontend framework: one codebase for Web, iOS, Android, and HarmonyOS
- **[React](https://github.com/facebook/react)** — User interface library
- **[Alembic](https://github.com/sqlalchemy/alembic)** — Database migration management

### Intelligence

- **[Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)** — Local speech recognition and voiceprint matching engine
- **[Home Assistant](https://github.com/home-assistant/core)** — Open-source smart home platform
- **[open-xiaoai](https://github.com/idootop/open-xiaoai)** — Lets Xiaomi XiaoAI speakers "hear your voice" and unlock far more possibilities

### Inspiration

- **[OpenClaw](https://github.com/openclaw/openclaw)** (MIT License) — Personal AI assistant project. FamilyClaw drew architectural inspiration from its excellent channel plugin design

### Infrastructure

- **[PostgreSQL](https://www.postgresql.org/)** — Reliable relational database
- **[Nginx](https://nginx.org/)** — High-performance reverse proxy
- **[VitePress](https://vitepress.dev/)** — Documentation site generator
- **[Docker](https://www.docker.com/)** — Containerized deployment

## Contributing

FamilyClaw is a passion-driven project, and we welcome contributions of all kinds:

- Submit bug reports or feature suggestions
- Develop new plugins (AI providers, channels, themes, etc.)
- Improve documentation and translations
- Share your experience

## Contact

If you're interested in FamilyClaw or need help, feel free to reach out via Issues.

---

<p align="center">
  <sub>Built with love for every family.</sub><br/>
  <sub>用心，为每一个家。</sub>
</p>
