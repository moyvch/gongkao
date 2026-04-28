#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公考岗位收藏主入口
串联 session 验证 -> 抓取 -> LLM 解析 -> Excel 存储

用法:
  python scripts/collect.py "https://www.gongkaoleida.com/user/article/xxxx"
  python scripts/collect.py "链接1" "链接2" ...   # 批量收藏
"""
import sys
import os

# 解决 Windows GBK 终端乱码
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 将项目根目录加入路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from scripts.logger  import get_logger
from scripts.scraper import scrape
from scripts.parser  import parse_job_info
from scripts.storage import save_job, get_stats

log = get_logger("collect")


def collect_one(url: str) -> dict:
    """
    收藏单个岗位链接。

    Returns:
        {
            "success":  bool,
            "message":  str,
            "url":      str,
            "job_info": dict,  # 仅 success=True 时存在
        }
    """
    log.section(f"收藏岗位")
    log.info(f"链接: {url}")

    # ── Step 1: 抓取 ──────────────────────────────────────────────
    log.step("Step 1/3  抓取页面")
    try:
        page_data = scrape(url)
        log.ok(f"抓取成功，内容长度: {len(page_data['text'])} 字符"
               + (f"，PC 端截止: {page_data['deadline']}" if page_data.get("deadline") else ""))
    except FileNotFoundError as e:
        log.fail(str(e))
        return {"success": False, "message": str(e), "url": url}
    except PermissionError as e:
        log.fail(str(e))
        return {"success": False, "message": str(e), "url": url}
    except Exception as e:
        log.fail(f"抓取失败: {e}")
        return {"success": False, "message": f"抓取失败: {e}", "url": url}

    # ── Step 2: LLM 解析 ─────────────────────────────────────────
    log.step("Step 2/3  LLM 解析")
    try:
        job_info = parse_job_info(page_data)
        log.ok(f"解析成功: {job_info.get('岗位名称', '未知岗位')}")
    except Exception as e:
        log.fail(f"LLM 解析失败: {e}")
        return {"success": False, "message": f"LLM 解析失败: {e}", "url": url}

    # 若 LLM 未提取到截止日期，但 scraper 从 PC 端获取到了，则补充
    if page_data.get("deadline") and job_info.get("报名截止日期") in ("暂无", "", None):
        job_info["报名截止日期"] = page_data["deadline"]
        log.info(f"补充截止日期（来自 PC 端）: {page_data['deadline']}")

    # ── Step 3: 保存 ─────────────────────────────────────────────
    log.step("Step 3/3  保存到 Excel")
    try:
        save_result = save_job(job_info)
    except Exception as e:
        log.fail(f"保存失败: {e}")
        return {"success": False, "message": f"保存失败: {e}", "url": url}

    if save_result["success"]:
        log.ok(save_result["message"])
    else:
        log.skip(save_result["message"])

    return {
        "success":  save_result["success"],
        "message":  save_result["message"],
        "url":      url,
        "job_info": job_info,
    }


def print_job_summary(result: dict):
    """打印单个岗位摘要"""
    if not result["success"]:
        # 跳过重复收藏时不打印 FAIL
        if "已存在" in result.get("message", ""):
            log.skip(result["message"])
        else:
            log.fail(result["message"])
        return

    job = result.get("job_info", {})
    lines = [
        f"岗位名称: {job.get('岗位名称', '-')}",
        f"招聘单位: {job.get('招聘单位', '-')}",
        f"所在地区: {job.get('所在地区', '-')}",
        f"招录人数: {job.get('招录人数', '-')} 人",
        f"学历要求: {job.get('学历要求', '-')}",
        f"专业要求: {job.get('专业要求', '-')}",
        f"报名截止: {job.get('报名截止日期', '-')}",
        f"投递方式: {job.get('投递方式', '-')}",
        f"考试类型: {job.get('考试类型', '-')}",
    ]
    if job.get("其他要求") and job["其他要求"] != "暂无":
        lines.append(f"其他要求: {job['其他要求']}")
    if job.get("备注") and job["备注"] != "暂无":
        lines.append(f"备注:     {job['备注']}")

    for line in lines:
        log.info("  " + line)

    stats = get_stats()
    log.info(f"  ── 当前共收藏 {stats['total']} 个岗位")


def main():
    if len(sys.argv) < 2:
        log.info("用法: python scripts/collect.py <URL> [URL2 ...]")
        log.info('示例: python scripts/collect.py "https://www.gongkaoleida.com/user/article/2790853"')
        sys.exit(1)

    urls = [u.strip() for u in sys.argv[1:] if u.strip()]
    total = len(urls)

    if total == 0:
        log.warn("未检测到有效链接")
        sys.exit(1)

    results = []
    for idx, url in enumerate(urls, start=1):
        if total > 1:
            log.info(f"\n[{idx}/{total}] 开始处理...")
        result = collect_one(url)
        print_job_summary(result)
        results.append(result)

    # 批量汇总
    if total > 1:
        success = sum(1 for r in results if r["success"])
        skipped = sum(1 for r in results if not r["success"] and "已存在" in r.get("message", ""))
        failed  = total - success - skipped
        log.section("批量收藏汇总")
        log.summary(total=total, success=success, fail=failed)
        if skipped:
            log.info(f"  跳过重复: {skipped} 个")


if __name__ == "__main__":
    main()
