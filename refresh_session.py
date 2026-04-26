#!/usr/bin/env python3
"""
公考雷达登录脚本
功能：打开Chrome浏览器，扫码登录后自动更新session并上传到GitHub
"""
import asyncio
import os
import json
import subprocess
from datetime import datetime
from playwright.async_api import async_playwright


def git_commit_and_push():
    """提交session更新到GitHub"""
    try:
        # 添加session.json的更改
        subprocess.run(['git', 'add', 'session.json'], check=True, capture_output=True)

        # 检查是否有更改需要提交
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, check=True
        )

        if not result.stdout.strip():
            print("没有需要提交的更改")
            return False

        # 提交更改
        commit_msg = f"Update session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True, capture_output=True)

        # 推送到GitHub
        subprocess.run(['git', 'push', 'origin', 'main'], check=True, capture_output=True)

        print("✓ 已成功推送到GitHub")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Git操作失败: {e}")
        print(e.stderr.decode() if e.stderr else "")
        return False


async def main():
    session_file = os.path.join(os.path.dirname(__file__), 'session.json')
    backup_file = os.path.join(
        os.path.dirname(__file__),
        f'session_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )

    async with async_playwright() as p:
        # 读取已有的session作为参考（如果有）
        existing_session = None
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as f:
                existing_session = json.load(f)
            # 备份旧session
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(existing_session, f, ensure_ascii=False, indent=2)
            print(f"已备份旧session到: {backup_file}")

        # 启动Chrome浏览器（使用系统默认用户配置）
        # Windows 路径
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        browser = await p.chromium.launch(
            headless=False,
            executable_path=chrome_path,
            args=[
                '--no-first-run',
                '--no-default-browser-check',
            ]
        )

        # 使用已保存的session恢复登录状态
        if existing_session:
            context = await browser.new_context(storage_state=session_file)
        else:
            context = await browser.new_context()

        page = await context.new_page()

        # 访问目标页面
        target_url = "https://www.gongkaoleida.com/area/2129-2130-0-2,3-0"
        print(f"正在打开: {target_url}")
        await page.goto(target_url)
        await page.wait_for_load_state('networkidle')

        print("页面已加载，等待用户登录...")
        print("请点击右上角的「登录」按钮，使用微信扫码登录")
        print("登录成功后，程序会自动保存新的session")

        # 等待登录成功（检测用户信息出现）
        # 登录成功后，页面会显示用户名
        try:
            # 等待登录按钮消失或用户信息出现
            # 这里我们等待用户点击登录后，页面出现用户信息
            await page.wait_for_selector(
                'text=Four Leaf Clover',
                timeout=120000  # 120秒超时，给足够时间扫码
            )
            print("\n检测到登录成功！正在保存新的session...")

            # 保存新的session
            storage_state = await context.storage_state(path=session_file)
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(storage_state, f, ensure_ascii=False, indent=2)

            print(f"新session已保存到: {session_file}")

            # 验证登录
            print("\n验证登录状态...")
            await page.reload()
            await page.wait_for_load_state('networkidle')
            content = await page.content()

            if "Four Leaf Clover" in content:
                print("✓ 登录验证成功！")

                # 自动提交并推送到GitHub
                print("\n正在推送到GitHub...")
                git_commit_and_push()
            else:
                print("✗ 警告：登录验证可能失败，请手动检查")

        except Exception as e:
            print(f"\n等待登录超时或出错: {e}")
            print("如果已经登录成功，请手动关闭浏览器，session可能已经保存")

        print("\n浏览器将保持打开状态以便确认。")
        print("确认登录成功后，请关闭浏览器窗口。")

        # 保持浏览器打开
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
