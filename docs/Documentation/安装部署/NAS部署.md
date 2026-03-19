---
title: NAS部署
docId: zh-2.4
version: v0.1
status: draft
order: 240
outline: deep
---

# NAS部署

## 这页要解决什么

- 给 NAS 用户一条统一入口，而不是每种面板各写一套散文

## 当前建议支持的平台

- 群晖
- 威联通
- 飞牛 OS
- 宝塔
- 其他支持 Docker / Compose 的 NAS 面板

## 写法原则

- 先讲共性：镜像、端口、卷挂载、环境变量
- 再按平台补差异步骤
- 不要把平台差异写成产品能力差异

## 建议正文结构

### 共通准备

- 镜像版本
- 数据目录
- 网络和端口

### 群晖

- Container Manager / Docker 套件入口

### 威联通

- Container Station 入口

### 飞牛 OS

- 应用中心或容器入口

### 宝塔

- Docker 管理器入口

## 完成标准

- NAS 用户能在一页内找到自己的平台落点
