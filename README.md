# 公考岗位收藏工具

自动化抓取公考雷达岗位信息，用 LLM 解析结构化字段，保存到 Excel。

## 功能特性

- 自动登录保持（session 持久化）
- 无头浏览器抓取（WAP + PC 双策略，SPA 动态等待）
- **PC 端截止日期补全**（WAP 不含截止日期时自动从 PC 版抓取）
- LLM 智能解析（MiniMax API）
- Excel 去重存储 + **投递状态管理**（待投递/已投递/已过期/不合适）
- **投递方式标准化**（电话/邮箱/网上报名/现场报名格式统一）
- 历史数据回归脚本（支持 `--dry-run`）
- **命令行查询工具**（关键词/地区/类型/状态多维筛选）
- 统一日志模块（带时间戳、颜色、语义化级别）

## 目录结构

```
gongkao/
├── .env                     # API Key 和浏览器路径配置（需手动创建，示例见下方）
├── session.json             # 登录凭证（运行 refresh_session.py 后自动生成）
├── jobs.xlsx                # 收藏的岗位数据
├── SKILL.md                 # WorkBuddy Skill 文档
├── README.md                # 本文档
├── refresh_session.py       # 刷新登录 session（非无头，需手动操作）
├── restore_login.py         # 恢复登录状态
├── verify_login.py          # 验证登录状态
├── scripts/
│   ├── collect.py           # 主入口：收藏岗位（支持批量）
│   ├── query.py             # 命令行查询/筛选工具（新增）
│   ├── rescan.py            # 历史数据回归脚本
│   ├── scraper.py           # 无头浏览器抓取（WAP+PC双策略）
│   ├── parser.py            # LLM 解析模块
│   ├── storage.py           # Excel 存储管理
│   └── logger.py            # 统一日志模块（新增）
└── requirements.txt
```

## 快速开始

### 1. 安装依赖

```bash
cd e:\cache\studio\gongkao
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置

创建 `.env` 文件（从以下模板复制）：

```env
MINIMAX_API_KEY=your_api_key_here
CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
```

> **注意**：`.env` 和 `session.json` 不在 Git 版本控制中（已加入 .gitignore），需要本地创建。

### 3. 首次登录

运行刷新脚本（需要图形界面）：

```bash
python refresh_session.py
```

按提示在浏览器中登录公考雷达，session 将自动保存到 `session.json`。

### 4. 收藏岗位

```bash
# 收藏单个岗位
python scripts/collect.py "https://www.gongkaoleida.com/user/article/12345"

# 批量收藏（多个链接）
python scripts/collect.py "链接1" "链接2" "链接3"

# 或在 WorkBuddy 中直接说：
# "帮我收藏这个岗位：https://..."
```

### 5. 查询收藏

```bash
# 列出全部岗位（含统计摘要）
python scripts/query.py

# 关键词搜索
python scripts/query.py -k 计算机

# 按地区筛选
python scripts/query.py -r 广东

# 按考试类型筛选
python scripts/query.py -t 事业编

# 按投递状态筛选
python scripts/query.py -s 待投递

# 组合筛选
python scripts/query.py -r 广东 -t 事业编 -k IT

# 查看某条详情（使用列表中的 # 行号）
python scripts/query.py -d 3

# 修改投递状态
python scripts/query.py --set-status 3 已投递

# 统计摘要
python scripts/query.py --stats
```

### 6. 查看收藏

直接打开 `jobs.xlsx` 文件。

---

## 数据字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| 收藏时间 | 添加到表格的时间 | 2026-04-26 10:31 |
| 岗位名称 | 职位名称 | 综合管理岗 |
| 招聘单位 | 所属机构 | XX市人力资源和社会保障局 |
| 所在地区 | 省份/城市/区 | 广东省广州市天河区 |
| 招录人数 | 招录人数（数字）| 1 |
| 学历要求 | 最低学历要求 | 本科及以上 |
| 专业要求 | 所需专业 | 计算机科学与技术... |
| 报名截止日期 | 截止日期（YYYY-MM-DD）| 2026-05-15 |
| 投递方式 | 电话/邮箱/网上报名/现场报名 | 电话：010-12345678 |
| 考试类型 | 岗位类型 | 国企/银行/事业单位 |
| 其他要求 | 附加条件（年龄/经验等）| 2年以上工作经验 |
| 备注 | 亮点提示 | 有编制、限应届生 |
| **投递状态** | **待投递/已投递/已过期/不合适**（新增）| 待投递 |
| 原始链接 | 公考雷达原始链接 | https://... |

---

## 脚本说明

### collect.py - 收藏岗位

```bash
python scripts/collect.py <岗位链接> [链接2 ...]
```

自动完成：抓取页面 → LLM 解析 → PC 端补全截止日期 → 写入 Excel → 去重检查

### query.py - 查询筛选

```bash
python scripts/query.py [-k 关键词] [-r 地区] [-t 考试类型] [-s 投递状态]
python scripts/query.py --set-status <行号> <状态>
python scripts/query.py --stats
```

### rescan.py - 历史数据回归

当 LLM 提示词优化后，可以用此脚本重新解析历史数据：

```bash
python scripts/rescan.py           # 重新解析需要更新的记录
python scripts/rescan.py --dry-run # 只列出需要更新的记录，不实际修改
```

### refresh_session.py - 刷新登录

当 session 过期时运行（需要图形界面）：

```bash
python refresh_session.py
```

### verify_login.py - 验证登录

```bash
python verify_login.py
```

---

## 数据质量说明

| 字段 | 完整度 | 说明 |
|------|--------|------|
| 岗位名称 | 100% | 全部提取 |
| 招聘单位 | 100% | 全部提取 |
| 所在地区 | 100% | 全部提取 |
| 招录人数 | 100% | "若干"自动转为 0 |
| 学历要求 | 100% | 全部提取 |
| 专业要求 | 100% | 全部提取 |
| 投递方式 | 80% | 标准化为 [类型]：[详情] 格式 |
| 考试类型 | 100% | 全部提取 |
| 其他要求 | 100% | 关键条件精简 |
| 备注 | 60% | 亮点提炼，非职位描述 |
| 报名截止日期 | 60%↑ | WAP 无则从 PC 版补全 |

---

## 常见问题

### Q: session 过期了怎么办？

运行 `python refresh_session.py` 重新登录。

### Q: 抓取内容太短怎么办？

已内置 2.5 秒 SPA 等待，如仍不足请升级 `WAIT_AFTER_LOAD` 值（`scraper.py` 顶部常量）。

### Q: 如何去重？

基于 URL 中的 jobId 去重，忽略分享参数（shareKey、channel 等）。

### Q: 投递状态如何修改？

```bash
python scripts/query.py --set-status <行号> 已投递
```

或直接在 Excel 中修改「投递状态」列（下次写入不影响已有状态）。

---

## 技术栈

- **浏览器自动化**: Playwright (Python)
- **LLM 解析**: MiniMax Text-01 API
- **数据存储**: openpyxl
- **环境配置**: python-dotenv

---

## 优化方向

### ✅ 已完成

- [x] 日志模块（`scripts/logger.py`）替代控制台输出
- [x] 批量收藏（一次传入多个链接）
- [x] 投递状态管理（新增"已投递/待确认/已过期"列）
- [x] 投递方式格式标准化（`[类型]：[详情]`）
- [x] PC 端截止日期补全
- [x] SPA 动态等待（`wait_for_timeout`）
- [x] 命令行查询工具（`query.py`）
- [x] rescan 支持 `--dry-run`

### 🟡 待完成

- [ ] 截止日期临近提醒通知
- [ ] 多平台支持（智联招聘、BOSS 直聘等）
- [ ] 数据导出（CSV/JSON）
- [ ] Web 可视化界面（Gradio/Streamlit）
