---
name: gongkao-collector
version: 1.0.0
description: >
  公考岗位收藏工具。接收公考雷达（gongkaoleida.com）网站的岗位链接，
  自动使用无头浏览器抓取岗位详情，用 MiniMax LLM 解析结构化信息，
  并追加保存到本地 Excel 表格中，方便选岗和投递管理。
  触发词：收藏岗位、保存岗位、抓取公考、公考雷达链接、帮我收藏、岗位信息、公考收藏
author: user
---

# 公考岗位收藏 Skill

## 功能说明

本 Skill 帮助用户收藏公考雷达平台上的招聘岗位信息，核心流程：

1. 验证登录 session 是否有效
2. 无头浏览器带 session 访问岗位链接
3. 调用 MiniMax LLM 解析岗位结构化字段
4. 追加写入本地 Excel 表格（去重）
5. 返回岗位摘要给用户

## 使用方式

当用户说出类似以下内容时触发本 Skill：
- "帮我收藏这个岗位：https://www.gongkaoleida.com/..."
- "收藏一下这个公考链接"
- "保存这个岗位信息"
- "抓取这个公考页面"

## 执行步骤

### 环境准备（首次使用）

1. 安装依赖：
```bash
cd e:\cache\studio\gongkao
pip install -r requirements.txt
playwright install chromium
```

2. 配置 API Key（已内置于 .env 文件）

3. 若 session 失效，运行刷新脚本（需要图形界面，非无头）：
```bash
python refresh_session.py
```

### 收藏岗位

```bash
python scripts/collect.py "https://www.gongkaoleida.com/user/article/xxxx"
```

## 输出

- 控制台打印岗位摘要
- 数据追加写入 `jobs.xlsx`

## 文件说明

| 文件 | 说明 |
|------|------|
| `scripts/collect.py` | 主入口脚本 |
| `scripts/scraper.py` | 无头浏览器抓取 |
| `scripts/parser.py` | MiniMax LLM 解析 |
| `scripts/storage.py` | Excel 读写管理 |
| `session.json` | 登录凭证（需定期刷新） |
| `jobs.xlsx` | 收藏数据表（自动创建） |
| `.env` | API Key 配置 |
