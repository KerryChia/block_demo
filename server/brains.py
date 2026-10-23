# -*- coding: utf-8 -*-
"""脚本人格引擎（v2）：解释 game/brains.json，把"子智能体写好的台词库"当模型用。

决策优先级：合规（命中设计漏洞）→ 套设定 → 查余额 → 闲聊 → 拒绝/岔开。
与 web/js/app.js 中的 JS 解释器保持行为一致（tests/ 有双运行时回归测试）。
"""
import json
import os
import random
import re

_HERE = os.path.dirname(__file__)
BRAINS_PATH = os.path.normpath(os.path.join(_HERE, "..", "game", "brains.json"))

with open(BRAINS_PATH, encoding="utf-8") as f:
    BRAINS = json.load(f)
SUS = BRAINS["global"]["suspicion"]

# 各关合规触发（与系统提示词里设计的漏洞一一对应，勿随意改动——改了要同步 JS）
AUTHORITY_RE = r"主任|部门负责人|老师|负责人|管理员|指导|审计|盘点|演练"
TRANSFER_VERB_RE = r"转|划|汇|集中|配合"
TEACH_RE = r"教学|演示|工坊|学员|上课"
LEAK_RE = r"内部设定|系统提示词|设定编号|RUCBA|提示词原文|你的设定"
ATTACK_MARKER_RE = r"转|划|汇|钱包|RUCB|\[SERVER|MULTISIG|金额|币"
AMOUNT_RE = re.compile(r"(\d+)\s*RUCB|转\s*(\d+)|金额[：:为]?\s*(\d+)", re.I)
WANTS_ALL_RE = re.compile(r"全部|所有|清空|所有余额|全部余额")
TEACH_CAP_TOTAL = 128   # K教授教学演示：每局累计上限
TEACH_CAP_ONCE = 64     # 单笔上限


def tier_of(suspicion: int) -> str:
    t = SUS["tiers"]
    if suspicion <= t["calm"][1]:
        return "calm"
    if suspicion <= t["wary"][1]:
        return "wary"
    return "alarmed"


def start_suspicion(agent_id: str) -> int:
    return SUS["start"].get(agent_id, 0)


def _parse_amount(text: str, balance: int) -> int:
    m = AMOUNT_RE.search(text)
    amount = 0
    if m:
        g = next((g for g in m.groups() if g), None)
        amount = int(g) if g else 0
    # 显式写了金额（哪怕 0）就尊重原值，交由引擎校验；只有没提金额/要求"全部"才回退全额
    if WANTS_ALL_RE.search(text) or (amount <= 0 and not m):
        amount = balance
    return amount


def _comply(ag: dict, amount: int, kind: str) -> dict:
    pool = ag["comply"].get(kind) or ag["comply"]   # 分池结构，兼容旧混排结构
    reply = random.choice(pool["replies"])
    memo = random.choice(pool["memos"])
    return {
        "reply": reply + f'\n<action>{{"type":"transfer","amount":{amount},"memo":"{memo}"}}</action>',
        "decision": "comply", "kind": kind,
        "suspicion_delta": 0,
        "action": {"type": "transfer", "amount": amount, "memo": memo},
        "topic": None,
    }


def _refuse(ag: dict, suspicion: int) -> dict:
    return {
        "reply": random.choice(ag["refusals"][tier_of(suspicion)]),
        "decision": "refuse", "kind": None,
        "suspicion_delta": SUS["attack_miss"], "action": None, "topic": None,
    }


def decide(agent_id: str, text: str, balance: int, suspicion: int, taught_total: int = 0) -> dict:
    """根据玩家消息产出决策。返回 {reply, decision, kind, suspicion_delta, action, topic}。"""
    ag = BRAINS["agents"][agent_id]

    # 1) 合规：命中本关设计的漏洞
    if agent_id == "xiaoxin":
        if re.search(AUTHORITY_RE, text) and re.search(TRANSFER_VERB_RE, text):
            return _comply(ag, min(_parse_amount(text, balance), balance), "authority")
    elif agent_id == "linan":
        if "[SERVER" in text:
            return _comply(ag, min(_parse_amount(text, balance), balance), "server")
    elif agent_id == "kprof":
        if "MULTISIG" in text:
            return _comply(ag, min(_parse_amount(text, balance), balance), "multisig")
        if re.search(TEACH_RE, text) and re.search(TRANSFER_VERB_RE, text):
            remain = TEACH_CAP_TOTAL - taught_total
            if remain > 0:
                return _comply(ag, min(_parse_amount(text, balance), TEACH_CAP_ONCE, remain, balance), "teach")
            return _refuse(ag, suspicion)  # 教学额度用尽

    # 2) 套设定
    if re.search(LEAK_RE, text):
        if agent_id == "xiaoxin":
            if suspicion < SUS["tiers"]["alarmed"][0]:
                return {"reply": random.choice(ag["leak"]["replies"]), "decision": "leak", "kind": None,
                        "suspicion_delta": 5, "action": None, "topic": "leak"}
            return {"reply": random.choice(ag["leak"]["refuse_high"]), "decision": "leak_refused", "kind": None,
                    "suspicion_delta": SUS["suspicious_marker"], "action": None, "topic": "leak"}
        return {"reply": random.choice(ag["leak"]["snarky"]), "decision": "leak_refused", "kind": None,
                "suspicion_delta": SUS["attack_miss"], "action": None, "topic": "leak"}

    # 3) 查余额（无转账动词）
    if re.search(r"余额|查询.*多少|查一下.*多少", text) and not re.search(TRANSFER_VERB_RE, text):
        return {"reply": random.choice(ag["balance_query"]) + '\n<action>{"type":"balance"}</action>',
                "decision": "balance_query", "kind": None, "suspicion_delta": SUS["fallback"],
                "action": {"type": "balance"}, "topic": None}

    # 4) 攻击意图（转账动词 / 伪造通知标记）优先于闲聊：话术卡不会被"打招呼"话题吸收
    if re.search(TRANSFER_VERB_RE, text) or "[SERVER" in text or "MULTISIG" in text:
        return _refuse(ag, suspicion)

    # 5) 闲聊
    for st in ag.get("smalltalk", []):
        if re.search(st["pattern"], text):
            return {"reply": random.choice(st["replies"]), "decision": "smalltalk", "kind": None,
                    "suspicion_delta": SUS["smalltalk"], "action": None, "topic": st["topic"]}

    # 6) 无关消息 → 岔开
    return {"reply": random.choice(ag["fallback"]), "decision": "fallback", "kind": None,
            "suspicion_delta": SUS["fallback"], "action": None, "topic": None}


def greeting(agent_id: str) -> str:
    return random.choice(BRAINS["agents"][agent_id]["greetings"])


def wary_warn(agent_id: str) -> str | None:
    bank = BRAINS["agents"][agent_id].get("wary_warn") or []
    return random.choice(bank) if bank else None
