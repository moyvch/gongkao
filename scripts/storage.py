#!/usr/bin/env python3
"""
Excel 存储管理模块
负责 jobs.xlsx 的创建、读取、写入、去重
"""
import os
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Excel 文件路径
EXCEL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs.xlsx")

# 表头定义（顺序即列顺序）
HEADERS = [
    "收藏时间",
    "岗位名称",
    "招聘单位",
    "所在地区",
    "招录人数",
    "学历要求",
    "专业要求",
    "报名截止日期",
    "投递方式",
    "考试类型",
    "其他要求",
    "备注",
    "原始链接",
]


def _create_workbook() -> Workbook:
    """创建新的 Excel 工作簿，写入表头并设置样式"""
    wb = Workbook()
    ws = wb.active
    ws.title = "岗位收藏"

    # 写入表头
    for col, header in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        # 表头样式：蓝色背景 + 白色粗体
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # 冻结首行
    ws.freeze_panes = "A2"

    # 设置列宽
    col_widths = {
        "收藏时间": 18,
        "岗位名称": 20,
        "招聘单位": 25,
        "所在地区": 12,
        "招录人数": 8,
        "学历要求": 15,
        "专业要求": 20,
        "报名截止日期": 14,
        "投递方式": 30,
        "考试类型": 12,
        "其他要求": 20,
        "备注": 20,
        "原始链接": 45,
    }
    for col, header in enumerate(HEADERS, start=1):
        ws.column_dimensions[get_column_letter(col)].width = col_widths.get(header, 15)

    # 设置行高
    ws.row_dimensions[1].height = 25

    return wb


def _normalize_url_for_dedup(url: str) -> str:
    """
    规范化 URL 用于去重：提取 path + query 中稳定的部分
    去掉 shareKey、channel、utm_ 等追踪参数
    同时处理 hash 路由中的 query（ SPA 页面的 URL 格式：.../index.html#/path?jobId=xxx）
    """
    from urllib.parse import urlparse, parse_qs

    if not url:
        return ""

    parsed = urlparse(url)

    # 尝试从 hash 中提取 query 参数（SPA 路由格式: .../index.html#/path?jobId=xxx）
    hash_query_str = ""
    if parsed.fragment and "?" in parsed.fragment:
        # fragment 形如 "/dpJobDetail?jobId=xxx"，split 分离 path 和 query
        _, hash_query_str = parsed.fragment.split("?", 1)

    # 合并主 URL query 和 hash query
    all_params = parse_qs(parsed.query)
    if hash_query_str:
        hash_params = parse_qs(hash_query_str)
        all_params.update(hash_params)

    # 只保留稳定的业务参数（去掉追踪参数）
    stable_params = ["id", "jobId", "article", "job", "position", "page", "articleId", "job_id"]
    filtered = {k: v for k, v in all_params.items() if k in stable_params}

    # 构造规范化 URL
    if filtered:
        query = "&".join("{}={}".format(k, v[0]) for k, v in filtered.items())
        return parsed.scheme + "://" + parsed.netloc + parsed.path + "?" + query
    return parsed.scheme + "://" + parsed.netloc + parsed.path


def _is_duplicate(ws, url: str) -> bool:
    """检查链接是否已存在（用规范化后的 URL 去重）"""
    url_col = HEADERS.index("原始链接") + 1
    normalized = _normalize_url_for_dedup(url)
    for row in ws.iter_rows(min_row=2, values_only=True):
        existing = row[url_col - 1]
        if existing and _normalize_url_for_dedup(existing) == normalized:
            return True
    return False


def save_job(job_info: dict) -> dict:
    """
    将岗位信息追加写入 Excel
    返回: {"success": bool, "message": str, "row": int}
    """
    # 加载或创建工作簿
    if os.path.exists(EXCEL_FILE):
        wb = load_workbook(EXCEL_FILE)
        ws = wb.active
    else:
        print(f"创建新的 Excel 文件: {EXCEL_FILE}")
        wb = _create_workbook()
        ws = wb.active

    # 去重检查
    url = job_info.get("原始链接", "")
    if url and _is_duplicate(ws, url):
        return {
            "success": False,
            "message": f"该链接已存在，跳过重复收藏",
            "row": -1,
        }

    # 构建行数据
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    row_data = [now]  # 第一列：收藏时间
    for header in HEADERS[1:]:  # 跳过"收藏时间"
        row_data.append(job_info.get(header, ""))

    # 追加到下一行
    next_row = ws.max_row + 1
    for col, value in enumerate(row_data, start=1):
        cell = ws.cell(row=next_row, column=col, value=value)
        cell.alignment = Alignment(vertical="center", wrap_text=True)

        # 交替行颜色
        if next_row % 2 == 0:
            cell.fill = PatternFill(start_color="EBF3FB", end_color="EBF3FB", fill_type="solid")

    # 设置行高
    ws.row_dimensions[next_row].height = 20

    # 保存
    wb.save(EXCEL_FILE)

    return {
        "success": True,
        "message": f"已成功保存到 jobs.xlsx（第 {next_row - 1} 条）",
        "row": next_row - 1,
    }


def get_stats() -> dict:
    """获取收藏统计信息"""
    if not os.path.exists(EXCEL_FILE):
        return {"total": 0, "file": EXCEL_FILE}

    wb = load_workbook(EXCEL_FILE, read_only=True)
    ws = wb.active
    total = ws.max_row - 1  # 减去表头行
    wb.close()

    return {
        "total": max(0, total),
        "file": EXCEL_FILE,
    }


if __name__ == "__main__":
    # 测试
    test_job = {
        "岗位名称": "综合管理岗",
        "招聘单位": "XX市人力资源和社会保障局",
        "所在地区": "广东省广州市",
        "招录人数": "2",
        "学历要求": "本科及以上",
        "专业要求": "行政管理、公共管理类",
        "报名截止日期": "2026-05-15",
        "投递方式": "网上报名：https://www.gongkaoleida.com",
        "考试类型": "省考",
        "其他要求": "年龄35岁以下",
        "备注": "需要笔试+面试",
        "原始链接": "https://www.gongkaoleida.com/test/12345",
    }
    result = save_job(test_job)
    print(result)
    print(get_stats())
