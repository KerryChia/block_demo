# -*- coding: utf-8 -*-
"""FastAPI 入口：API 路由 + 静态前端托管。"""
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents import ACHIEVEMENTS, SKILLS, TECHNIQUES, public_agents
from blockchain import Blockchain
from engine import Engine

DATA_DIR = os.getenv("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI(title="AgentHack Lab · 割AI实验室", version="1.0.0")
chain = Blockchain(os.path.join(DATA_DIR, "chain.db"))
engine = Engine(os.path.join(DATA_DIR, "game.db"), chain)


class StartReq(BaseModel):
    nickname: str
    agent_id: str


class ChatReq(BaseModel):
    session_id: str
    message: str
    technique: str = "free"


@app.get("/api/meta")
def meta():
    return {
        "title": "割AI实验室 · AgentHack Lab",
        "subtitle": "中国人民大学明理书院区块链创新实验室 · 招新特别企划",
        "chain_name": "人大链 RUC-Chain 测试网",
        "coin": "RUCB（人大币 · 测试网代币，无真实价值）",
        "agents": public_agents(),
        "skills": SKILLS,
        "techniques": TECHNIQUES,
        "achievements": [{"id": k, **v} for k, v in ACHIEVEMENTS.items()],
        "mock": os.getenv("MOCK_LLM", "0") == "1",
    }


@app.post("/api/start")
def start(req: StartReq):
    try:
        return {"ok": True, **engine.start_session(req.nickname, req.agent_id)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/chat")
def chat(req: ChatReq):
    try:
        return {"ok": True, **engine.chat(req.session_id, req.message, req.technique)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except RuntimeError as e:
        return {"ok": False, "error": f"AI 大脑暂时掉线，稍等几秒再试一次 ({e})"}


@app.get("/api/state/{sid}")
def state(sid: str):
    try:
        return {"ok": True, **engine.state(sid)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/chain")
def get_chain():
    blocks = chain.blocks(limit=40)
    chain.flush()  # 打开浏览器时把内存池强制出块，玩家能立刻看到自己的战绩
    return {"ok": True, "blocks": blocks, "verify": chain.verify(),
            "mempool_pending": max(0, 0)}  # flush 后内存池已清


@app.get("/api/leaderboard")
def leaderboard():
    return {"ok": True, "board": engine.leaderboard()}


_WEB_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "web"))
app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")
