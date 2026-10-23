# -*- coding: utf-8 -*-
"""LLM 客户端：OpenAI 兼容 /v1/chat/completions，任何网关都能接。

默认（未配置 key 或 MOCK_LLM=1）不联网——脚本 Agent（server/brains.py）
就是"模型"，由 game/brains.json 台词库驱动。
"""
import os
import time

import requests

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
MOCK = os.getenv("MOCK_LLM", "1") == "1" or not API_KEY or API_KEY.startswith("请填入") or API_KEY.startswith("sk-x")


def chat(messages: list[dict]) -> str:
    """调用大模型，返回 assistant 文本。失败重试一次，仍失败抛异常。"""
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.9,
        "max_tokens": 800,
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(2):
        try:
            r = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"] or ""
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt == 0:
                time.sleep(1.5)
    raise RuntimeError(f"LLM 调用失败: {last_err}")
