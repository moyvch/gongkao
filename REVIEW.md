# 公考收藏工具 — 代码审查报告

> 审查时间：2026-04-28
> 审查范围：`scripts/` 下所有 Python 文件

---

## ✅ 无问题确认（已排除）

以下项目经逐一验证，确认无误，无需修改：

| 项目 | 结论 |
|------|------|
| `query.py` `print_stats(jobs)` 参数 | `jobs` 是显式函数参数，调用处均有实参传递，**无 bug** |
| `collect.py` `result.get('job_info', {})` | 失败分支使用 dict 默认值，安全，**无 bug** |
| 日期正则 `_DEADLINE_RE` | 验证 6 种格式边界（`YYYY-MM-DD` / `YYYY年MM月DD` / `YYYY/MM/DD` 等），`len(parts)==3` 保护，**无 crash 风险** |
| `is_old_format_remark` | 保守策略（宁漏不误），已知灰色地带（"要求：本科…"等）属设计权衡，**可接受** |

---

## 🔴 需修复（2 项）

### Bug 1 — `storage.py`：`wb.save()` 无异常保护 ⛔ 高风险

**影响场景：** Windows 上用 Excel 打开 `jobs.xlsx` 期间，任何收藏/更新操作会直接崩溃，报 `PermissionError`，程序非正常退出，无友好提示。

**位置：**
- `scripts/storage.py` 第 248 行（`save_job`）
- `scripts/storage.py` 第 323 行（`update_field`）

```python
# ❌ 当前代码
wb.save(EXCEL_FILE)  # ← Excel 被占用时直接崩溃
```

**修复方案：**

```python
try:
    wb.save(EXCEL_FILE)
except PermissionError:
    log.fail(f"保存失败：jobs.xlsx 正被其他程序占用，请关闭后再试")
    return False
except Exception as e:
    log.fail(f"保存失败：{e}")
    return False
```

---

### Bug 2 — `scraper.py`：`_add_domain_cookies` 全局静默吞异常 ⛸ 中风险

**影响场景：**
- `session.json` 被误删或 JSON 损坏时，完全无提示，cookie 加载失败，后续抓取拿到登录墙页面才报错（定位困难）
- cookie 添加部分失败（如 `secure` 属性冲突）静默绕过，登录态实际未生效

**位置：** `scripts/scraper.py` 第 82–96 行

```python
# ❌ 当前代码：三层 except 全部 bare pass
async def _add_domain_cookies(context, session_file):
    try:
        with open(session_file) as f:
            session_data = json.load(f)   # ← 文件不存在/JSON损坏 → 静默跳过
        for cookie in session_data.get("cookies", []):
            # ...
            except Exception:            # ← 添加失败 → 静默跳过
                pass
    except Exception:                    # ← 外层也静默
        pass
```

**修复方案：**

```python
async def _add_domain_cookies(context, session_file):
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            session_data = json.load(f)
    except FileNotFoundError:
        log.warn(f"session.json 不存在，请先运行 refresh_session.py 登录")
        return  # 降级，不阻塞主流程
    except json.JSONDecodeError:
        log.fail(f"session.json 格式损坏，请删除后重新登录")
        return

    for cookie in session_data.get("cookies", []):
        cur_domain = cookie.get("domain", "")
        if not cur_domain or cur_domain in ("www.gongkaoleida.com",):
            cookie["domain"] = ".gongkaoleida.com"
            try:
                await context.add_cookies([cookie])
            except Exception as e:
                log.debug(f"Cookie 添加失败（非致命）: {e}")
```

---

## 🟡 建议改（1 项）

### 建议 1 — `rescan.py`：循环内重复创建事件循环 ⚠️ 性能

**位置：** `scripts/rescan.py` 第 162 行

```python
# ❌ 当前：每条记录新建+销毁事件循环
for idx, job in enumerate(to_update):
    result = asyncio.run(rescan_single_async(job))
```

**影响：** 10 条记录 = 10 次 `asyncio.run()`，每次重新初始化 Chromium，额外 1–2 秒/条。

**修复方案：** 改为批量并发，所有任务放入单一事件循环：

```python
async def rescan_batch(jobs: list[dict]) -> list[dict | None]:
    """批量重新抓取解析（单一事件循环）"""
    tasks = [rescan_single_async(j) for j in jobs]
    return await asyncio.gather(*tasks, return_exceptions=True)

# 主流程
if not dry_run:
    results = asyncio.run(rescan_batch(to_update))
    for job, result in zip(to_update, results):
        if isinstance(result, Exception):
            log.fail(f"[行 {job['_row']}] 失败: {result}")
            continue
        if result:
            for field, value in result.items():
                update_field(job["_row"], field, value)
            # ... 日志
```

---

## 💭 清理项（1 项）

### 清理 1 — `requirements.txt`：未使用的 pandas 依赖

**确认方式：** AST 扫描 `scripts/` 下所有 `.py` 文件，`pd` / `pandas` 均未出现。

```diff
 # requirements.txt
- pandas>=2.0.0
```

---

## 📊 统计摘要

| 维度 | 结果 |
|------|------|
| 语法错误 | 0 |
| 🔴 需修复 | 2 |
| 🟡 建议改 | 1 |
| 💭 清理 | 1 |
| ✅ 确认无 bug | 4 项 |

---

## 修复优先级

```
P0 — Bug 1（Excel 保存崩溃）：立即修，影响每一次用户操作
P0 — Bug 2（静默异常）：立即修，降低故障定位成本
P2 — 建议 1（事件循环）：可选，性能优化
P3 — 清理 1（pandas）：可选，减小安装体积
```
