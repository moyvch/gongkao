#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax LLM 解析模块
将页面文本发送给 MiniMax，提取结构化岗位信息
"""
import os
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from scripts.logger import get_logger

log = get_logger("parser")

# 加载 .env 配置
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"
MODEL = "MiniMax-Text-01"

SYSTEM_PROMPT = """你是一个公务员/国企/事业单位招聘信息提取助手。
请从给定的招聘页面文本中，精确提取结构化信息。

【重要规则】
1. 严格只返回 JSON，不要任何解释性文字
2. 如果某个字段在页面中找不到对应内容，填 "暂无"（数字类填 0）
3. 内容要精简，不要复述大段职位描述原文
4. 特别注意"联系电话"字段，电话号码也是投递方式的一种"""

EXTRACT_PROMPT = """从以下招聘页面文本中提取字段，严格按此 JSON 格式返回（只返回 JSON）：

```json
{{
  "岗位名称": "岗位名称（从「职位名称」或「岗位名称」字段提取）",
  "招聘单位": "单位全称（从「招聘单位」「工作单位」「招考单位」字段提取）",
  "所在地区": "省/市/区（从「报考地区」「所在地区」字段提取）",
  "招录人数": "数字，无则填 0（从「招录人数」「人数」字段提取，注意「若干」填 0）",
  "学历要求": "从「学历要求」字段提取，如：本科及以上",
  "专业要求": "从「专业要求」字段提取，无则填「不限」",
  "报名截止日期": "从「报名截止」「截止日期」「报名时间」字段提取，格式化为 YYYY-MM-DD，无法判断则填「暂无」",
  "投递方式": "从以下所有位置提取联系方式，格式示例：\n  - 电话：「电话：010-12345678」或「电话：010-12345678,020-88888888」\n  - 邮箱：「邮箱：hr@example.com」\n  - 网上报名：「网上报名：https://xxx.com/apply」（必须包含完整网址！）\n  - 现场报名：「现场报名：XX市XX区XX路XX号」\n  多个联系方式用逗号分隔。完全没有时填「暂无」",
  "考试类型": "从「考试类型」字段提取，常见值：国考/省考/事业编/选调生/国企/银行/军队文职/三支一扶",
  "其他要求": "从「报考条件」「其他条件」「年龄要求」「工作经历」字段提取，填写3-5个最关键的附加条件（如：年龄35岁以下、2年以上经验、党员优先），无则填「暂无」，不要超过50字",
  "备注": "只填【亮点/特别提醒】，如：限2024届应届生、有编制、仅面试、加分政策等\n  不要复述职位介绍原文！不要填职位描述！最多3条，无亮点则填「暂无」",
  "原始链接": "{url}"
}}
```

页面文本如下：
---
{page_text}
---

只返回 JSON，不要任何其他内容。"""


def parse_job_info(page_data: dict) -> dict:
    """
    调用 MiniMax API 解析岗位信息
    page_data: scraper 返回的 {"text": ..., "title": ..., "url": ...}
    返回: 结构化岗位字典
    """
    if not MINIMAX_API_KEY:
        raise ValueError("MINIMAX_API_KEY 未配置，请检查 .env 文件")

    page_text = page_data.get("text", "")
    if not page_text:
        raise ValueError("页面内容为空，无法解析")

    prompt = EXTRACT_PROMPT.format(page_text=page_text, url=page_data.get("url", ""))

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,  # 低温度，保证输出稳定
        "max_tokens": 1024,
    }

    log.step("调用 MiniMax LLM 解析岗位信息...")

    # 配置请求 session，自动重试 3 次（网络波动时更加健壮）
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist={500, 502, 503, 504})
    session.mount("https://", HTTPAdapter(max_retries=retry))

    try:
        response = session.post(
            MINIMAX_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"MiniMax API 请求失败: {e}")

    result = response.json()

    # 提取 LLM 返回的文本
    try:
        llm_text = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"MiniMax API 返回格式异常: {result}")

    # 解析 JSON（处理 LLM 可能包裹在 ```json ``` 中的情况）
    job_info = _extract_json(llm_text)

    # 补充链接字段
    job_info["原始链接"] = page_data.get("url", "")

    return job_info


def _extract_json(text: str) -> dict:
    """从 LLM 返回文本中提取 JSON"""
    text = text.strip()

    # 去掉 ```json ... ``` 包裹
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        text = text[start:end].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试找到第一个 { 到最后一个 }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # 解析失败，返回默认结构
        log.warn(f"警告：JSON 解析失败，LLM 原始输出：\n{text[:500]}")
        return {
            "岗位名称": "解析失败",
            "招聘单位": "",
            "所在地区": "",
            "招录人数": "",
            "学历要求": "",
            "专业要求": "",
            "报名截止日期": "",
            "投递方式": "",
            "考试类型": "",
            "其他要求": "",
            "备注": f"LLM 解析失败，原始内容: {text[:200]}",
            "原始链接": "",
        }


if __name__ == "__main__":
    # 测试用
    test_data = {
        "text": "岗位名称：综合管理岗 招聘单位：XX市人力资源和社会保障局 招录人数：2人 学历要求：本科及以上 报名截止：2026-05-15 投递方式：网上报名",
        "title": "测试岗位",
        "url": "https://www.gongkaoleida.com/test",
    }
    result = parse_job_info(test_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
