#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无头浏览器抓取模块
使用 Playwright 以无头模式 + session 登录访问公考雷达岗位页面。

策略（按顺序执行）：
  1. 优先访问 WAP 子域名（wap.gongkaoleida.com）获取岗位正文
  2. 若 WAP 缺少截止日期，尝试访问 PC 版（www.gongkaoleida.com）补全
  3. 支持 SPA 懒加载等待、动态内容超时控制

改动记录：
  - 增加 wait_for_timeout(2000) 等待 SPA 内容加载
  - 增加多选择器逐级 fallback
  - 新增 _try_fetch_deadline() 从 PC 端补全截止日期
  - 统一使用 logger 模块替代 print
"""
import asyncio
import os
import json
import re
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, BrowserContext

from scripts.logger import get_logger

log = get_logger("scraper")

# ── 配置 ──────────────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

CHROME_PATH   = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
SESSION_FILE  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "session.json")
TEXT_MAX_LEN  = 14000   # 单次最大字符截断（上调以覆盖更长的 PC 页面）
WAIT_AFTER_LOAD = 2500  # networkidle 后额外等待 ms（让 SPA 完成渲染）
PAGE_TIMEOUT  = 35000   # 单页超时 ms

# WAP 内容选择器（优先级从高到低）
WAP_SELECTORS = [
    ".article-content",
    ".job-detail",
    ".detail-content",
    ".content-wrap",
    ".article-detail",
    ".recruit-detail",
    ".main-content",
    "article",
    "main",
]

# PC 页面截止日期正则（匹配"报名截止：2026-05-01"之类的文本）
_DEADLINE_RE = re.compile(
    r"(?:报名截止|截止日期|报名时间[至~-]|截止时间)[：:\s]*"
    r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})",
    re.IGNORECASE,
)


def _to_wap_url(url: str) -> str:
    """
    将公考雷达岗位链接转换为 WAP 版本。
    www.gongkaoleida.com/user/article/xxxx
    → wap.gongkaoleida.com/user/article/xxxx（或保留 wap 链接不变）
    """
    parsed = urlparse(url)
    if "wap." in parsed.netloc:
        return url  # 已经是 WAP
    netloc = parsed.netloc.replace("www.", "wap.", 1)
    if not netloc.startswith("wap."):
        netloc = "wap." + parsed.netloc
    return urlunparse(parsed._replace(netloc=netloc))


def _to_pc_url(url: str) -> str:
    """将 WAP 链接转换为 PC 版本"""
    parsed = urlparse(url)
    netloc = parsed.netloc.replace("wap.", "www.", 1)
    return urlunparse(parsed._replace(netloc=netloc))


async def _add_domain_cookies(context: BrowserContext, session_file: str):
    """将 session.json 的 cookie 扩展到 .gongkaoleida.com 根域，解决子域名共享问题"""
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


async def _extract_text(page: Page) -> tuple[str, str]:
    """
    从页面提取核心文本，返回 (text, matched_selector)。
    优先用 WAP_SELECTORS，fallback 到全页 body。
    """
    for selector in WAP_SELECTORS:
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                if len(text.strip()) > 100:
                    return text, selector
        except Exception:
            continue

    text = await page.inner_text("body")
    return text, "body"


async def _clean_text(raw: str) -> str:
    """清理文本：去除多余空行、首尾空白"""
    lines = [line.strip() for line in raw.split("\n")]
    return "\n".join(line for line in lines if line)


async def _try_fetch_deadline(context: BrowserContext, pc_url: str) -> str:
    """
    尝试从 PC 版页面补全截止日期。
    返回格式化日期字符串（YYYY-MM-DD），或空字符串。
    """
    try:
        pc_page = await context.new_page()
        log.debug(f"尝试抓取 PC 端截止日期: {pc_url}")
        await pc_page.goto(pc_url, wait_until="networkidle", timeout=PAGE_TIMEOUT)
        await pc_page.wait_for_timeout(WAIT_AFTER_LOAD)

        text = await pc_page.inner_text("body")
        await pc_page.close()

        match = _DEADLINE_RE.search(text)
        if match:
            raw = match.group(1)
            # 统一转为 YYYY-MM-DD
            normalized = re.sub(r"[/年月]", "-", raw).rstrip("-")
            parts = normalized.split("-")
            if len(parts) == 3:
                y, m, d = parts
                return f"{y}-{int(m):02d}-{int(d):02d}"
    except Exception as e:
        log.debug(f"PC 端截止日期抓取失败（非致命）: {e}")
    return ""


async def scrape_page(url: str, fetch_deadline: bool = True) -> dict:
    """
    抓取指定 URL 的页面内容。

    Args:
        url:            目标链接（支持 www / wap 两种域名）
        fetch_deadline: 是否尝试从 PC 端补全截止日期

    Returns:
        {
            "text":     页面纯文本（已清理）,
            "title":    页面标题,
            "url":      实际 URL,
            "deadline": 截止日期字符串（YYYY-MM-DD，若未找到则为空字符串）,
        }
    """
    if not os.path.exists(SESSION_FILE):
        raise FileNotFoundError("session.json 不存在，请先运行 refresh_session.py 登录")

    wap_url = _to_wap_url(url)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=CHROME_PATH,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        try:
            context = await browser.new_context(
                storage_state=SESSION_FILE,
                viewport={"width": 414, "height": 896},   # 手机视口，适配 WAP
                user_agent=(
                    "Mozilla/5.0 (Linux; Android 12; Pixel 6) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Mobile Safari/537.36"
                ),
            )
            await _add_domain_cookies(context, SESSION_FILE)

            # ── 抓取 WAP 页面 ──────────────────────────────────
            page = await context.new_page()
            log.step(f"访问 WAP: {wap_url}")
            await page.goto(wap_url, wait_until="networkidle", timeout=PAGE_TIMEOUT)

            # 等待 SPA 动态渲染完成
            await page.wait_for_timeout(WAIT_AFTER_LOAD)

            # 登录状态检测
            content_html = await page.content()
            page_title = await page.title()
            if "登录" in page_title or "请登录" in content_html or "login" in page_title.lower():
                raise PermissionError("session 已失效，请运行 refresh_session.py 重新登录")

            raw_text, selector = await _extract_text(page)
            clean = await _clean_text(raw_text)
            log.ok(f"WAP 内容抓取成功（选择器: {selector}），长度: {len(clean)} 字符")

            actual_url = page.url
            await page.close()

            # ── 尝试从 PC 端补全截止日期 ──────────────────────
            deadline = ""
            if fetch_deadline and "暂无" not in clean and "报名截止" not in clean:
                pc_url = _to_pc_url(wap_url)
                deadline = await _try_fetch_deadline(context, pc_url)
                if deadline:
                    log.ok(f"从 PC 端获取到截止日期: {deadline}")
                else:
                    log.debug("PC 端未找到截止日期")

            return {
                "text":     clean[:TEXT_MAX_LEN],
                "title":    page_title,
                "url":      actual_url,
                "deadline": deadline,
            }

        finally:
            await browser.close()


def scrape(url: str, fetch_deadline: bool = True) -> dict:
    """同步包装，供外部直接调用"""
    return asyncio.run(scrape_page(url, fetch_deadline=fetch_deadline))


# ── 命令行直接运行 ────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python scripts/scraper.py <URL> [--no-deadline]")
        sys.exit(1)

    target = sys.argv[1]
    fetch_dl = "--no-deadline" not in sys.argv

    result = scrape(target, fetch_deadline=fetch_dl)
    print(f"\n标题: {result['title']}")
    print(f"URL:  {result['url']}")
    print(f"截止: {result['deadline'] or '（未找到）'}")
    print(f"\n内容预览（前600字）:\n{result['text'][:600]}")
