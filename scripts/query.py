#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令行查询/筛选工具
从 jobs.xlsx 中按条件筛选岗位，支持关键词搜索、地区/考试类型/投递状态过滤。

用法:
  python scripts/query.py                         # 列出全部
  python scripts/query.py -k 广州                 # 关键词搜索（所有字段）
  python scripts/query.py -r 广东                 # 按地区筛选
  python scripts/query.py -t 省考                 # 按考试类型筛选
  python scripts/query.py -s 待投递               # 按投递状态筛选
  python scripts/query.py -r 广东 -t 事业编 -k IT # 组合筛选
  python scripts/query.py --set-status 2 已投递   # 修改第2条记录的投递状态
  python scripts/query.py --stats                 # 显示统计摘要
"""
import sys
import os
import argparse
import re

# 将项目根目录加入路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from scripts.logger  import get_logger
from scripts.storage import (
    get_all_jobs, get_stats, update_delivery_status,
    HEADERS, DELIVERY_STATUS_OPTIONS
)

log = get_logger("query")


# ── 辅助函数 ──────────────────────────────────────────────────────

def _match_keyword(job: dict, keyword: str) -> bool:
    """在所有字段中搜索关键词（大小写不敏感）"""
    kw = keyword.lower()
    for field in ["岗位名称", "招聘单位", "所在地区", "专业要求", "其他要求", "备注", "考试类型"]:
        val = str(job.get(field, "")).lower()
        if kw in val:
            return True
    return False


def _match_region(job: dict, region: str) -> bool:
    val = str(job.get("所在地区", "")).lower()
    return region.lower() in val


def _match_type(job: dict, exam_type: str) -> bool:
    val = str(job.get("考试类型", "")).lower()
    return exam_type.lower() in val


def _match_status(job: dict, status: str) -> bool:
    val = str(job.get("投递状态", "")).strip()
    return val == status


def _truncate(text: str, max_len: int = 20) -> str:
    """截断长文本"""
    text = str(text) if text else ""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


# ── 显示函数 ──────────────────────────────────────────────────────

def print_jobs_table(jobs: list[dict]):
    """以简洁表格形式打印岗位列表"""
    if not jobs:
        log.warn("没有找到符合条件的岗位")
        return

    # 列定义：(字段名, 显示宽度, 截断长度)
    columns = [
        ("_row",       4,  4,  "#"),
        ("岗位名称",   18, 18, "岗位名称"),
        ("招聘单位",   22, 22, "招聘单位"),
        ("所在地区",   12, 12, "所在地区"),
        ("招录人数",    6,  6, "人数"),
        ("报名截止日期",12, 12, "截止日期"),
        ("考试类型",   10, 10, "类型"),
        ("投递状态",    8,  8, "状态"),
    ]

    # 表头
    header_row = "  ".join(
        label.ljust(width) if not field.startswith("_") else label.rjust(width)
        for field, width, _, label in columns
    )
    sep = "-" * len(header_row)

    print()
    print(sep)
    print(header_row)
    print(sep)

    for job in jobs:
        row = "  ".join(
            _truncate(job.get(field, ""), trunc).ljust(width)
            if field != "_row"
            else str(job.get(field, "")).rjust(width)
            for field, width, trunc, _ in columns
        )
        print(row)

    print(sep)
    print(f"共 {len(jobs)} 条结果\n")


def print_job_detail(job: dict):
    """打印单条岗位详情"""
    log.section(f"岗位详情 (第 {job.get('_row', '?')} 条)")
    for field in HEADERS:
        if field in ("收藏时间", "原始链接"):
            continue
        val = job.get(field, "")
        if val and str(val) not in ("", "暂无", "0"):
            log.info(f"  {field:<10}: {val}")
    log.info(f"  {'收藏时间':<10}: {job.get('收藏时间', '')}")
    log.info(f"  {'原始链接':<10}: {job.get('原始链接', '')}")


def print_stats(jobs: list[dict]):
    """打印统计摘要"""
    stats = get_stats()
    log.section("数据统计摘要")

    total = stats["total"]
    log.info(f"  总收藏: {total} 个岗位")

    if not jobs:
        return

    # 按考试类型统计
    type_count: dict[str, int] = {}
    for job in jobs:
        t = str(job.get("考试类型", "未知")).strip() or "未知"
        type_count[t] = type_count.get(t, 0) + 1
    log.info("  考试类型分布:")
    for t, cnt in sorted(type_count.items(), key=lambda x: -x[1]):
        log.info(f"    {t}: {cnt} 个")

    # 按投递状态统计
    status_count: dict[str, int] = {}
    for job in jobs:
        s = str(job.get("投递状态", "待投递")).strip() or "待投递"
        status_count[s] = status_count.get(s, 0) + 1
    log.info("  投递状态分布:")
    for s, cnt in sorted(status_count.items(), key=lambda x: -x[1]):
        log.info(f"    {s}: {cnt} 个")

    # 截止日期最近的 3 个
    dated = [j for j in jobs if re.match(r"\d{4}-\d{2}-\d{2}", str(j.get("报名截止日期", "")))]
    dated.sort(key=lambda x: x.get("报名截止日期", ""))
    if dated:
        log.info("  最近截止的岗位:")
        for j in dated[:3]:
            log.info(f"    [{j['报名截止日期']}] {j.get('岗位名称', '-')} — {j.get('招聘单位', '-')}")


# ── CLI 入口 ──────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="公考岗位查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("-k", "--keyword",    help="关键词搜索（所有字段）")
    parser.add_argument("-r", "--region",     help="按地区筛选（如：广东、北京）")
    parser.add_argument("-t", "--type",       help="按考试类型筛选（如：省考、事业编、国企）")
    parser.add_argument("-s", "--status",     help=f"按投递状态筛选（可选: {'/'.join(DELIVERY_STATUS_OPTIONS)}）")
    parser.add_argument("-d", "--detail",     type=int, metavar="ROW",
                        help="查看指定行号的岗位详情（行号见列表 # 列）")
    parser.add_argument("--set-status",       nargs=2, metavar=("ROW", "STATUS"),
                        help=f"修改投递状态，例: --set-status 3 已投递")
    parser.add_argument("--stats",            action="store_true", help="显示统计摘要")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # ── 修改投递状态 ──
    if args.set_status:
        row_str, new_status = args.set_status
        try:
            row_idx = int(row_str)
        except ValueError:
            log.fail(f"行号必须是整数，收到: {row_str}")
            sys.exit(1)

        if new_status not in DELIVERY_STATUS_OPTIONS:
            log.fail(f"无效状态: {new_status}，可选值: {DELIVERY_STATUS_OPTIONS}")
            sys.exit(1)

        # 行号从表格 # 列映射到 Excel 行号（# 从 1 开始，Excel 行 = # + 1）
        excel_row = row_idx + 1
        ok = update_delivery_status(excel_row, new_status)
        if ok:
            log.ok(f"第 {row_idx} 条记录的投递状态已更新为「{new_status}」")
        else:
            log.fail("更新失败")
        return

    # ── 加载数据 ──
    jobs = get_all_jobs()
    if not jobs:
        log.warn("jobs.xlsx 不存在或为空，请先收藏岗位")
        return

    # ── 统计摘要 ──
    if args.stats:
        print_stats(jobs)
        return

    # ── 详情查看 ──
    if args.detail:
        matched = [j for j in jobs if j.get("_row") == args.detail + 1]
        if not matched:
            log.warn(f"未找到行号 {args.detail} 的记录")
        else:
            print_job_detail(matched[0])
        return

    # ── 筛选 ──
    filtered = jobs
    if args.keyword:
        filtered = [j for j in filtered if _match_keyword(j, args.keyword)]
    if args.region:
        filtered = [j for j in filtered if _match_region(j, args.region)]
    if args.type:
        filtered = [j for j in filtered if _match_type(j, args.type)]
    if args.status:
        filtered = [j for j in filtered if _match_status(j, args.status)]

    print_jobs_table(filtered)

    # 无筛选条件时显示简短统计
    if not any((args.keyword, args.region, args.type, args.status)):
        print_stats(filtered)


if __name__ == "__main__":
    main()
