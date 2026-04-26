#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公考岗位收藏主入口
串联 session 验证 -> 抓取 -> LLM 解析 -> Excel 存储

用法:
  python scripts/collect.py "https://www.gongkaoleida.com/user/article/xxxx"
  python scripts/collect.py "链接1" "链接2" ...  # 批量收藏
"""
import sys
import os

# 设置 stdout 编码为 utf-8（解决 Windows GBK 问题）
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 将项目根目录加入路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from scripts.scraper import scrape
from scripts.parser import parse_job_info
from scripts.storage import save_job, get_stats


def collect_one(url: str) -> dict:
    """
    收藏单个岗位链接
    返回结果字典
    """
    print("\n" + "="*50)
    print("开始收藏: " + url)
    print("="*50)

    # Step 1: 抓取页面（scraper 内部已含 session 失效检测，无需单独验证）
    try:
        page_data = scrape(url)
        print("[OK] 页面抓取成功，内容长度: {} 字符".format(len(page_data['text'])))
    except FileNotFoundError as e:
        return {"success": False, "message": str(e), "url": url}
    except PermissionError as e:
        return {"success": False, "message": str(e), "url": url}
    except Exception as e:
        return {"success": False, "message": "抓取失败: {}".format(e), "url": url}

    # Step 2: LLM 解析
    try:
        job_info = parse_job_info(page_data)
        print("[OK] LLM 解析成功: {}".format(job_info.get('岗位名称', '未知岗位')))
    except Exception as e:
        return {"success": False, "message": "LLM 解析失败: {}".format(e), "url": url}

    # Step 3: 保存到 Excel
    try:
        save_result = save_job(job_info)
    except Exception as e:
        return {"success": False, "message": "保存失败: {}".format(e), "url": url}

    return {
        "success": save_result["success"],
        "message": save_result["message"],
        "url": url,
        "job_info": job_info,
    }


def print_job_summary(result: dict):
    """打印岗位摘要"""
    if not result["success"]:
        print("\n[FAIL] " + result['message'])
        return

    job = result.get("job_info", {})
    print("\n" + "="*50)
    print("[OK] " + result['message'])
    print("="*50)
    print("岗位名称: " + job.get('岗位名称', '-'))
    print("招聘单位: " + job.get('招聘单位', '-'))
    print("所在地区: " + job.get('所在地区', '-'))
    print("招录人数: " + job.get('招录人数', '-') + " 人")
    print("学历要求: " + job.get('学历要求', '-'))
    print("专业要求: " + job.get('专业要求', '-'))
    print("报名截止: " + job.get('报名截止日期', '-'))
    print("投递方式: " + job.get('投递方式', '-'))
    print("考试类型: " + job.get('考试类型', '-'))
    if job.get("其他要求"):
        print("其他要求: " + job.get('其他要求'))
    if job.get("备注"):
        print("备注: " + job.get('备注'))
    print("="*50)

    # 统计
    stats = get_stats()
    print("当前共收藏 {} 个岗位 | 文件: {}".format(stats['total'], stats['file']))


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/collect.py <URL> [URL2 ...]")
        print("示例: python scripts/collect.py \"https://www.gongkaoleida.com/user/article/2790853\"")
        sys.exit(1)

    urls = sys.argv[1:]

    # session 验证已合并到 scrape() 中，无需单独检查
    # 批量收藏所有链接
    results = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        result = collect_one(url)
        print_job_summary(result)
        results.append(result)

    # 批量收藏时的汇总
    if len(urls) > 1:
        success_count = sum(1 for r in results if r["success"])
        print("\n批量收藏完成: 成功 {}/{} 个".format(success_count, len(urls)))


if __name__ == "__main__":
    main()
