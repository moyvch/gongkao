#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无头浏览器抓取模块
使用 Playwright 以无头模式 + session 登录访问公考雷达岗位页面
"""
import asyncio
import os
import json
from urllib.parse import urlparse
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# 加载 .env 配置
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

CHROME_PATH = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "session.json")
TEXT_MAX_LENGTH = 12000  # 提升截断上限（原 8000）


async def scrape_page(url: str) -> dict:
    """
    抓取指定 URL 的页面内容
    返回: {"text": 页面纯文本, "title": 页面标题, "url": 实际URL}
    """
    if not os.path.exists(SESSION_FILE):
        raise FileNotFoundError("session.json 不存在，请先运行 refresh_session.py 登录")

    async with async_playwright() as p:
        # 无头模式，后台静默运行
        browser = await p.chromium.launch(
            headless=True,
            executable_path=CHROME_PATH,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )

        try:
            # 带 session 登录状态创建上下文
            context = await browser.new_context(
                storage_state=SESSION_FILE,
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )

            # 补充 wap 子域名的 cookie（解决手机分享链接 cookie 不共享的问题）
            # 从 session.json 中读取已有 cookies，添加 .gongkaoleida.com 域名级别的 cookie
            try:
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    session_data = json.load(f)
                cookies = session_data.get("cookies", [])
                for cookie in cookies:
                    # 如果 cookie 没有指定 domain 或 domain 为 www，扩展到 .gongkaoleida.com
                    cur_domain = cookie.get("domain", "")
                    if not cur_domain or cur_domain == "www.gongkaoleida.com":
                        cookie["domain"] = ".gongkaoleida.com"
                        cookie["name"] = cookie.get("name", "")
                        try:
                            await context.add_cookies([cookie])
                        except Exception:
                            pass  # 忽略添加失败的 cookie
            except Exception:
                pass  # 静默跳过，不影响主流程

            page = await context.new_page()

            print("正在访问: " + url)
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # 检查是否需要登录（session 失效判断，同时适用于 www 和 wap 子域名）
            content = await page.content()
            page_title = await page.title()
            if "登录" in page_title or "请登录" in content or "login" in page_title.lower():
                raise PermissionError("session 已失效，请运行 refresh_session.py 重新登录")

            # 获取页面标题
            title = page_title

            # 尝试提取核心内容区域（公考雷达岗位详情）
            # 优先提取详情容器，fallback 到全页文本
            page_text = ""

            # 尝试多个可能的选择器
            selectors = [
                ".article-content",
                ".job-detail",
                ".detail-content",
                ".content-wrap",
                ".article-detail",
                ".recruit-detail",
                "article",
                "main",
                ".main-content",
            ]

            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        page_text = await element.inner_text()
                        if len(page_text.strip()) > 100:
                            print("使用选择器 '{}' 提取内容，长度: {}".format(selector, len(page_text)))
                            break
                except Exception:
                    continue

            # 如果所有选择器都没有找到，使用全页文本
            if not page_text or len(page_text.strip()) < 100:
                page_text = await page.inner_text("body")
                print("使用全页文本，长度: {}".format(len(page_text)))

            # 清理文本：去掉多余空行
            lines = [line.strip() for line in page_text.split("\n")]
            page_text = "\n".join(line for line in lines if line)

            return {
                "text": page_text[:TEXT_MAX_LENGTH],
                "title": title,
                "url": page.url,
            }

        finally:
            await browser.close()


def scrape(url: str) -> dict:
    """同步包装，供外部直接调用"""
    return asyncio.run(scrape_page(url))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python scraper.py <URL>")
        sys.exit(1)

    result = scrape(sys.argv[1])
    print("\n标题: " + result['title'])
    print("URL: " + result['url'])
    print("\n内容预览（前500字）:\n" + result['text'][:500])
