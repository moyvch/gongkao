# 公考岗位收藏工具

自动化抓取公考雷达岗位信息，用 LLM 解析结构化字段，保存到 Excel。

## 功能特性

- 自动登录保持（session 持久化）
- 无头浏览器抓取（WAP 子域名 cookie 共享）
- LLM 智能解析（MiniMax API）
- Excel 去重存储
- 历史数据回归脚本

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
│   ├── collect.py           # 主入口：收藏单个岗位
│   ├── rescan.py            # 历史数据回归脚本
│   ├── scraper.py           # 无头浏览器抓取
│   ├── parser.py            # LLM 解析模块
│   └── storage.py           # Excel 存储管理
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
python scripts/collect.py "https://wap.gongkaoleida.com/.../jobId=12345"

# 或在 WorkBuddy 中直接说：
# "帮我收藏这个岗位：https://..."
```

### 5. 查看收藏

直接打开 `jobs.xlsx` 文件。

---

## 数据字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| 收藏时间 | 添加到表格的时间 | 2026-04-26 10:31 |
| 岗位名称 | 职位名称 | 综合管理岗 |
| 招聘单位 | 所属机构 | XX市人力资源和社会保障局 |
| 所在地区 | 省份/城市/区 | 广东省广州市天河区 |
| 招录人数 | 招录人数（数字） | 1 |
| 学历要求 | 最低学历要求 | 本科及以上 |
| 专业要求 | 所需专业 | 计算机科学与技术... |
| 报名截止日期 | 截止日期（YYYY-MM-DD） | 暂无 |
| 投递方式 | 联系方式 | 电话：010-12345678 |
| 考试类型 | 岗位类型 | 国企/银行/事业单位 |
| 其他要求 | 附加条件（年龄/经验等） | 2年以上工作经验 |
| 备注 | 亮点提示 | 有编制、限应届生 |
| 原始链接 | 公考雷达原始链接 | https://... |

---

## 脚本说明

### collect.py - 收藏岗位

```bash
python scripts/collect.py <岗位链接>
```

自动完成：验证登录 → 抓取页面 → LLM解析 → 写入Excel → 去重检查

### rescan.py - 历史数据回归

当 LLM 提示词优化后，可以用此脚本重新解析历史数据：

```bash
python scripts/rescan.py
```

会重新抓取并解析所有历史记录，更新备注、投递方式、招录人数字段。

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
| 招录人数 | 100% | "若干"自动转为0 |
| 学历要求 | 100% | 全部提取 |
| 专业要求 | 100% | 全部提取 |
| 投递方式 | 80% | 有则提取，无则"暂无" |
| 考试类型 | 100% | 全部提取 |
| 其他要求 | 100% | 关键条件精简 |
| 备注 | 60% | 亮点提炼，非职位描述 |

> 注：WAP 页面不提供网上报名链接，报名需用户自行到目标单位官网操作。

---

## 常见问题

### Q: session 过期了怎么办？

运行 `python refresh_session.py` 重新登录。

### Q: 抓取内容太短怎么办？

页面可能还在加载，稍等后重试。如持续如此，检查网络或 session 状态。

### Q: 如何去重？

基于 URL 中的 jobId 去重，忽略分享参数（shareKey、channel 等）。

### Q: "若干"招录人数怎么处理？

自动转为数字 0，保存到 Excel。

---

## 技术栈

- **浏览器自动化**: Playwright (Python)
- **LLM 解析**: MiniMax Text-01 API
- **数据存储**: openpyxl + pandas
- **环境配置**: python-dotenv

---

## 后续优化方向

### 🔴 高优先级

#### 1. 报名截止日期提取
**现状**：5 条记录全是"暂无"，WAP 页面未显示截止日期
**方案**：
- 尝试抓取 PC 版页面获取截止日期
- 或让 LLM 从其他字段推断（如"报名时间：2026-05-01"）

#### 2. 页面内容抓取优化
**现状**：WAP 页面内容偏短（600-900字），SPA 懒加载可能未完全渲染
**方案**：
- 添加 `wait_for_timeout(2000)` 等待动态内容加载
- 尝试多个内容选择器（`.article-content`, `.job-detail` 等）
- 或等待特定元素出现后再提取

#### 3. 投递方式格式标准化
**现状**：当前是"电话："前缀，但可能有邮箱、网上报名等多种格式混在一起
**方案**：
- 统一为结构化格式：`[类型] 详情`，如 `电话:010-12345678`、`邮箱:hr@xx.com`、`报名:https://xx.com`
- 或拆分为"投递类型"+"投递详情"两列

---

### 🟡 中优先级

- [ ] 日志模块（`scripts/logger.py`）替代控制台输出
- [ ] 批量收藏（一次传入多个链接）
- [ ] 投递状态管理（新增"已投递/待确认/已过期"列）
- [ ] 截止日期提醒通知

---

### 🟢 低优先级

- [ ] 多平台支持（智联招聘、BOSS直聘等）
- [ ] 数据导出（CSV/JSON/PDF）
- [ ] Web 可视化界面（Gradio/Streamlit）
