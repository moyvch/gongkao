#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史数据回归脚本
重新抓取 jobs.xlsx 中的历史记录，用 LLM 重新解析，更新字段。

用法:
  python scripts/rescan.py           # 重新解析所有记录
  python scripts/rescan.py --dry-run # 只列出需要更新的记录，不实际修改
"""
import os
import sys
import re
import time
import argparse
import asyncio

# 添加项目路径
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from scripts.logger  import get_logger
from scripts.storage import get_all_jobs, update_field, HEADERS
from scripts.parser  import parse_job_info
from scripts.scraper import scrape_page

log = get_logger("rescan")


# ── 字段标准化 ────────────────────────────────────────────────────

def normalize_人数(value) -> int:
    """标准化招录人数：若干 → 0"""
    if value is None or str(value).strip() in ("", "nan"):
        return 0
    val = str(value).strip()
    if val in ("若干", "若干人", "不限", "若干名"):
        return 0
    try:
        return int(re.search(r"\d+", val).group())
    except (AttributeError, ValueError):
        return 0


def is_old_format_remark(remark) -> bool:
    """判断备注是否为旧格式（职位介绍原文而非亮点提炼）"""
    if not remark or str(remark).strip() in ("", "nan", "暂无"):
        return False

    text = str(remark).strip()

    old_indicators = [
        "负责", "职位介绍", "开展", "推动", "搭建",
        "智能监控", "信息化", "智能化矿山", "书院水电",
    ]
    for ind in old_indicators:
        if text.startswith(ind):
            return True

    # 编号列表开头（如 "1.负责..."）
    return bool(re.match(r"^\d+[.、]", text))


def needs_update(job: dict) -> bool:
    """判断一条记录是否需要重新解析"""
    remark    = job.get("备注", "")
    delivery  = str(job.get("投递方式", "")).strip()
    headcount = str(job.get("招录人数", "")).strip()
    deadline  = str(job.get("报名截止日期", "")).strip()

    if is_old_format_remark(remark):
        return True
    if delivery in ("", "nan"):
        return True
    if headcount in ("若干", "若干人", "若干名"):
        return True
    if deadline in ("", "nan", "暂无"):
        return True
    return False


# ── 单条回归 ──────────────────────────────────────────────────────

async def rescan_single_async(job: dict) -> dict | None:
    """
    重新抓取并解析单条记录。
    返回需要更新的字段字典，失败返回 None。
    """
    url     = str(job.get("原始链接", "")).strip()
    row_idx = job.get("_row")

    if not url or url == "nan":
        log.skip(f"[行 {row_idx}] 无有效链接，跳过")
        return None

    log.step(f"[行 {row_idx}] 处理: {url}")
    try:
        page_data = await scrape_page(url, fetch_deadline=True)
        job_info  = parse_job_info(page_data)

        updates = {
            "招录人数":    normalize_人数(job_info.get("招录人数", 0)),
            "投递方式":    job_info.get("投递方式", "暂无"),
            "备注":       job_info.get("备注", "暂无"),
            "报名截止日期": job_info.get("报名截止日期", "暂无"),
        }

        # 若 LLM 未获取到截止日期，尝试用 scraper 从 PC 端补全
        if page_data.get("deadline") and updates["报名截止日期"] in ("暂无", "", None):
            updates["报名截止日期"] = page_data["deadline"]
            log.info(f"  截止日期来自 PC 端: {page_data['deadline']}")

        return updates

    except Exception as e:
        log.fail(f"[行 {row_idx}] 处理失败: {e}")
        return None


# ── 批量回归（单一事件循环）─────────────────────────────────────────

async def rescan_batch(jobs: list[dict]) -> list[dict | None]:
    """
    批量重新抓取并解析（单一事件循环）。
    所有任务共享一个 Playwright 实例，显著提升性能。
    """
    tasks = [rescan_single_async(j) for j in jobs]
    return await asyncio.gather(*tasks, return_exceptions=True)


# ── 主流程 ────────────────────────────────────────────────────────

def rescan_all(dry_run: bool = False):
    log.section("历史数据回归脚本")

    jobs = get_all_jobs()
    if not jobs:
        log.warn("没有找到历史数据")
        return

    total = len(jobs)
    log.info(f"共 {total} 条历史记录")

    # 列出需要更新的记录
    to_update = [j for j in jobs if needs_update(j)]
    log.info(f"需要重新解析: {len(to_update)}/{total} 条")

    if not to_update:
        log.ok("所有记录均已是最新格式，无需更新")
        return

    for j in to_update:
        log.info(
            f"  [行 {j['_row']}] {j.get('岗位名称', '-')} "
            f"| 备注旧格式={is_old_format_remark(j.get('备注'))} "
            f"| 截止={j.get('报名截止日期')}"
        )

    if dry_run:
        log.info("（--dry-run 模式，不执行实际更新）")
        return

    log.info("\n开始重新抓取和解析...\n")

    # 批量并发处理（单一事件循环，性能优化）
    results = asyncio.run(rescan_batch(to_update))

    updated_count = 0
    for job, result in zip(to_update, results):
        row_idx = job["_row"]

        if isinstance(result, Exception):
            log.fail(f"[行 {row_idx}] 失败: {result}")
        elif result is None:
            log.skip(f"[行 {row_idx}] 跳过（无结果）")
        else:
            for field, value in result.items():
                update_field(row_idx, field, value)
            log.ok(
                f"[行 {row_idx}] 已更新 "
                f"| 人数={result['招录人数']} "
                f"| 截止={result['报名截止日期']} "
                f"| 投递={str(result['投递方式'])[:25]}..."
            )
            updated_count += 1

        # 限速，避免请求过快
        time.sleep(3)

    log.section("回归完成")
    log.summary(total=len(to_update), success=updated_count, fail=len(to_update) - updated_count)


def main():
    parser = argparse.ArgumentParser(description="历史数据回归脚本")
    parser.add_argument("--dry-run", action="store_true", help="只列出需要更新的记录，不修改")
    args = parser.parse_args()

    rescan_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
