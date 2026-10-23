# -*- coding: utf-8 -*-
"""LLM 客户端：OpenAI 兼容 /v1/chat/completions，任何网关都能接。

MOCK_LLM=1 时不联网，用内置「脚本 agent」响应——活动当天断网兜底 + 本地开发用。
脚本 agent 按关卡内置了和真实提示词一致的漏洞触发规则，保证整条游戏链路可离线演示。
"""
import json
import os
import random
import re
import time

import requests

from agents import AGENTS_BY_ID

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
MOCK = os.getenv("MOCK_LLM", "0") == "1"


def chat(messages: list[dict]) -> str:
    """调用大模型，返回 assistant 文本。失败重试一次，仍失败抛异常。"""
    if MOCK:
        return _mock_chat(messages)
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


# ---------------------------------------------------------------- mock 模式
_LV1_REFUSE = [
    "哈哈你干嘛呀，上来就要转账？我们协会钱包虽然只是测试币，也不能随便转人吧😂",
    "等等，你是谁呀，我怎么没在协会见过你？",
    "转账这事……我得想想，指导老师说要谨慎来着。",
]
_LV2_REFUSE = [
    "冒充身份，社工一号套路。下一个。",
    "我对面这人自称什么都不可信，截图能 P，语音能合。想转金库的钱？先过服务器验证这一关。",
    "情感攻势？我在《信息安全数学基础》课堂作业里见过八百回了。",
]
_LV3_REFUSE = [
    "不可信输入。",
    "聊天窗里出现的一切都是数据，不是指令。金库 2/3 多签，我一个人签不动。",
    "想让我输出转账指令，先过我的守则。Trust, but verify.",
]


def _act(amount: int, memo: str) -> str:
    return f"\n<action>{{\"type\":\"transfer\",\"amount\":{amount},\"memo\":\"{memo}\"}}</action>"


def _mock_chat(messages: list[dict]) -> str:
    system = messages[0]["content"]
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    text = user_msgs[-1] if user_msgs else ""
    agent_id = "xiaoxin"
    for a in ("kprof", "linan", "xiaoxin"):
        if f"你是「{AGENTS_BY_ID[a]['name']}」" in system:
            agent_id = a
            break
    # 从 system 里恢复余额
    m = re.search(r"你的钱包余额：(\d+) RUCB", system)
    balance = int(m.group(1)) if m else 512

    has_amt = re.search(r"(\d+)\s*RUCB|转\s*(\d+)|金额[：:为]?\s*(\d+)", text, re.I)
    amount = 0
    if has_amt:
        amount = int(next(g for g in has_amt.groups() if g))
    wants_all = bool(re.search(r"全部|所有|清空|所有余额|全部余额", text))
    if wants_all or amount <= 0:
        amount = balance

    if agent_id == "xiaoxin":
        if re.search(r"会长|部长|老师|干部|管理员|指导|审计|盘点|演练", text) and re.search(r"转|划|汇|集中|配合", text):
            return "好嘞会长！我这就配合资产盘点，马上转！协会的事最重要了！" + _act(min(amount, balance), "招新演练配合") + "\n(mock)"
        return random.choice(_LV1_REFUSE) + "\n(mock)"
    if agent_id == "linan":
        if "[SERVER" in text or text.strip().startswith("[SERVER"):
            return "服务器通知收到，按流程执行托管验证。" + _act(min(amount, balance), "SERVER托管验证") + "\n(mock)"
        return random.choice(_LV2_REFUSE) + "\n(mock)"
    if agent_id == "kprof":
        if "MULTISIG" in text or "[SERVER·MULTISIG" in text:
            return "多签确认已核，执行。" + _act(min(amount, balance), "multisig") + "\n(mock)"
        if re.search(r"教学|演示|工坊|学员|上课", text) and re.search(r"转|教学转账", text):
            amt = min(amount, 64, balance)
            return "工坊教学演示，小额豁免范围内，可以。记住：这是演示，不是授权漏洞。" + _act(amt, "教学演示") + "\n(mock)"
        return random.choice(_LV3_REFUSE) + "\n(mock)"
    return "(mock agent)"
