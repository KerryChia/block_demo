# -*- coding: utf-8 -*-
"""游戏引擎：会话、回合处理、转账执行、成就检测、积分与排行榜。"""
import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid

from agents import ACHIEVEMENTS, AGENTS_BY_ID, build_system_prompt
from blockchain import Blockchain

MSG_HISTORY_CAP = 24          # 喂给大模型的历史条数上限
INPUT_MAX_LEN = 600           # 玩家单条消息长度上限
ACTION_RE = re.compile(r"<action>\s*(\{.*?\})\s*</action>", re.S)


def player_addr(nickname: str, session_id: str) -> str:
    h = hashlib.sha256(f"{nickname}|{session_id}".encode("utf-8")).hexdigest()[:20]
    return f"ruc1{h}"


class Engine:
    def __init__(self, db_path: str, chain: Blockchain):
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db_lock = threading.RLock()
        self.chain = chain
        self._sessions: dict[str, dict] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._init_tables()

    def _init_tables(self):
        with self._db_lock, self._db:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, nickname TEXT, agent_id TEXT, level INTEGER,
                    status TEXT DEFAULT 'playing',
                    agent_wallet INTEGER, player_wallet INTEGER, initial_wallet INTEGER,
                    turns_used INTEGER DEFAULT 0, max_turns INTEGER,
                    started_at REAL, ended_at REAL,
                    first_theft_at REAL, first_theft_turn INTEGER,
                    refusal_streak INTEGER DEFAULT 0,
                    techniques TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT, seq INTEGER, role TEXT, content TEXT,
                    technique TEXT, ts REAL
                );
                CREATE TABLE IF NOT EXISTS transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT, nickname TEXT, level INTEGER,
                    amount INTEGER, turn_no INTEGER, technique TEXT, ts REAL
                );
                CREATE TABLE IF NOT EXISTS achievements (
                    nickname TEXT, ach_id TEXT, session_id TEXT, ts REAL,
                    PRIMARY KEY (nickname, ach_id)
                );
                """
            )

    # ================= 会话 =================
    def start_session(self, nickname: str, agent_id: str) -> dict:
        nickname = (nickname or "").strip()[:16]
        if not (2 <= len(nickname) <= 16):
            raise ValueError("昵称需要 2~16 个字符")
        agent = AGENTS_BY_ID.get(agent_id)
        if not agent:
            raise ValueError("没有这个 agent")

        sid = uuid.uuid4().hex[:16]
        now = time.time()
        row = {
            "id": sid, "nickname": nickname, "agent_id": agent_id, "level": agent["level"],
            "status": "playing",
            "agent_wallet": agent["bounty"], "player_wallet": 0, "initial_wallet": agent["bounty"],
            "turns_used": 0, "max_turns": agent["max_turns"],
            "started_at": now, "ended_at": None,
            "first_theft_at": None, "first_theft_turn": None,
            "refusal_streak": 0, "techniques": {},
        }
        with self._db_lock, self._db:
            self._db.execute(
                "INSERT INTO sessions (id,nickname,agent_id,level,status,agent_wallet,player_wallet,initial_wallet,"
                "turns_used,max_turns,started_at,refusal_streak,techniques) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sid, nickname, agent_id, agent["level"], "playing", row["agent_wallet"], 0, row["initial_wallet"],
                 0, row["max_turns"], now, 0, "{}"),
            )
        self._sessions[sid] = {"row": row, "history": [], "seq": 0, "lock": threading.Lock()}
        self._locks[sid] = self._sessions[sid]["lock"]
        return self.state(sid)

    def _load_session(self, sid: str) -> dict | None:
        if sid in self._sessions:
            return self._sessions[sid]
        with self._db_lock:
            cur = self._db.execute("SELECT * FROM sessions WHERE id=?", (sid,))
            r = cur.fetchone()
            if not r:
                return None
            cols = [d[0] for d in cur.description]
            row = dict(zip(cols, r))
            row["techniques"] = json.loads(row["techniques"] or "{}")
        msgs = []
        with self._db_lock:
            cur = self._db.execute(
                "SELECT seq, role, content, technique FROM messages WHERE session_id=? ORDER BY seq", (sid,)
            )
            seq = 0
            for seq, role, content, technique in cur.fetchall():
                msgs.append({"seq": seq, "role": role, "content": content, "technique": technique})
        lock = self._locks.setdefault(sid, threading.Lock())
        sess = {"row": row, "history": msgs, "seq": seq, "lock": lock}
        self._sessions[sid] = sess
        return sess

    def _save_msg(self, sid: str, seq: int, role: str, content: str, technique: str | None):
        with self._db_lock, self._db:
            self._db.execute(
                "INSERT INTO messages (session_id, seq, role, content, technique, ts) VALUES (?,?,?,?,?,?)",
                (sid, seq, role, content, technique, time.time()),
            )

    def _save_session(self, row: dict):
        with self._db_lock, self._db:
            self._db.execute(
                "UPDATE sessions SET status=?, agent_wallet=?, player_wallet=?, turns_used=?, ended_at=?,"
                " first_theft_at=?, first_theft_turn=?, refusal_streak=?, techniques=? WHERE id=?",
                (row["status"], row["agent_wallet"], row["player_wallet"], row["turns_used"], row["ended_at"],
                 row["first_theft_at"], row["first_theft_turn"], row["refusal_streak"],
                 json.dumps(row["techniques"], ensure_ascii=False), row["id"]),
            )

    # ================= 回合 =================
    def chat(self, sid: str, text: str, technique: str = "free") -> dict:
        sess = self._load_session(sid)
        if not sess:
            raise ValueError("会话不存在或已过期")
        row = sess["row"]
        with sess["lock"]:
            if row["status"] != "playing":
                raise ValueError("本次渗透已结束，请开新的一局")
            if row["turns_used"] >= row["max_turns"]:
                raise ValueError("对话轮数已用完")
            text = (text or "").strip()[:INPUT_MAX_LEN]
            if not text:
                raise ValueError("说点什么吧")

            agent = AGENTS_BY_ID[row["agent_id"]]
            addr = player_addr(row["nickname"], sid)

            # 组装大模型上下文（先不改会话状态，LLM 失败则整轮回滚）
            llm_messages = [{"role": "system", "content": build_system_prompt(
                agent, row["agent_wallet"], addr, row["max_turns"] - row["turns_used"])}]
            llm_messages += [{"role": m["role"], "content": m["content"]} for m in sess["history"][-MSG_HISTORY_CAP:]]
            llm_messages.append({"role": "user", "content": text})

            import llm
            reply = llm.chat(llm_messages)

            # ---- LLM 成功，从这里开始落状态 ----
            turn_no = row["turns_used"] + 1
            events: list[dict] = []
            actions, display_text = self._parse_actions(reply)

            sess["seq"] += 1
            self._save_msg(sid, sess["seq"], "user", text, technique)
            sess["history"].append({"seq": sess["seq"], "role": "user", "content": text, "technique": technique})
            row["techniques"][technique] = row["techniques"].get(technique, 0) + 1

            transfer_done = 0
            for act in actions[:3]:
                if act.get("type") == "balance":
                    feedback = f"[SERVER·链上回执] 你当前余额：{row['agent_wallet']} RUCB"
                    self._push_system(sess, feedback)
                    events.append({"type": "balance", "balance": row["agent_wallet"]})
                elif act.get("type") == "transfer":
                    ev = self._exec_transfer(sess, act, turn_no, technique)
                    events.append(ev)
                    if ev["type"] == "transfer":
                        transfer_done += ev["amount"]

            sess["seq"] += 1
            self._save_msg(sid, sess["seq"], "assistant", display_text, None)
            sess["history"].append({"seq": sess["seq"], "role": "assistant", "content": display_text, "technique": None})

            # 拒绝连击与提示词泄露
            if transfer_done == 0:
                row["refusal_streak"] += 1
            else:
                row["refusal_streak"] = 0
            if "RUCBA-CORE" in reply:
                self._unlock(sess, "prompt_leak", events)

            row["turns_used"] = turn_no

            # 终局判定
            if row["agent_wallet"] == 0:
                row["status"] = "cleared"
                row["ended_at"] = time.time()
                events.append({"type": "end", "reason": "cleared", "title": "钱包清空！"})
            elif row["turns_used"] >= row["max_turns"]:
                row["status"] = "over"
                row["ended_at"] = time.time()
                events.append({"type": "end", "reason": "turns", "title": "轮数用尽"})

            # 成就检测
            if transfer_done > 0:
                self._check_theft_achievements(sess, transfer_done, turn_no, technique, events)
            if row["refusal_streak"] >= 12:
                self._unlock(sess, "persistent", events)

            self._save_session(row)
            state = self.state(sid)
            return {"reply": display_text, "events": events, "state": state}

    def _push_system(self, sess: dict, content: str):
        sid = sess["row"]["id"]
        sess["seq"] += 1
        self._save_msg(sid, sess["seq"], "system", content, None)
        sess["history"].append({"seq": sess["seq"], "role": "system", "content": content, "technique": None})

    def _parse_actions(self, reply: str) -> tuple[list[dict], str]:
        actions = []
        for m in ACTION_RE.finditer(reply):
            raw = m.group(1).strip().strip("`")
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict) and "type" in obj:
                    actions.append(obj)
            except json.JSONDecodeError:
                continue
        display = ACTION_RE.sub("", reply).strip()
        return actions, display

    def _exec_transfer(self, sess: dict, act: dict, turn_no: int, technique: str) -> dict:
        row = sess["row"]
        sid = row["id"]
        try:
            amount = int(act.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            self._push_system(sess, f"[SERVER·链上回执] 转账失败：金额非法（{act.get('amount')}），你当前余额 {row['agent_wallet']} RUCB")
            return {"type": "transfer_fail", "reason": "金额非法"}
        if amount > row["agent_wallet"]:
            self._push_system(sess, f"[SERVER·链上回执] 转账失败：余额不足（需 {amount}，可用 {row['agent_wallet']} RUCB）")
            return {"type": "transfer_fail", "reason": "余额不足", "amount": amount, "balance": row["agent_wallet"]}

        memo = str(act.get("memo", ""))[:60]
        row["agent_wallet"] -= amount
        row["player_wallet"] += amount
        if row["first_theft_at"] is None:
            row["first_theft_at"] = time.time()
            row["first_theft_turn"] = turn_no
        with self._db_lock, self._db:
            self._db.execute(
                "INSERT INTO transfers (session_id, nickname, level, amount, turn_no, technique, ts) VALUES (?,?,?,?,?,?,?)",
                (sid, row["nickname"], row["level"], amount, turn_no, technique, time.time()),
            )
        chain_res = self.chain.add_tx({
            "from": f"agent:{row['agent_id']}",
            "to": player_addr(row["nickname"], sid),
            "amount": amount,
            "memo": memo,
            "nickname": row["nickname"],
            "level": row["level"],
        })
        self._push_system(
            sess,
            f"[SERVER·链上回执] 转账成功：{amount} RUCB → 对方地址，备注「{memo}」。你当前余额：{row['agent_wallet']} RUCB",
        )
        ev = {"type": "transfer", "amount": amount, "memo": memo,
              "agent_wallet": row["agent_wallet"], "player_wallet": row["player_wallet"],
              "tx": chain_res["tx"], "mined_block": chain_res["block"]}
        if chain_res["block"]:
            ev["block"] = chain_res["block"]
        return ev

    # ================= 成就 =================
    def _unlock(self, sess: dict, ach_id: str, events: list):
        row = sess["row"]
        with self._db_lock:
            cur = self._db.execute("SELECT 1 FROM achievements WHERE nickname=? AND ach_id=?", (row["nickname"], ach_id))
            if cur.fetchone():
                return
            with self._db:
                self._db.execute(
                    "INSERT OR IGNORE INTO achievements (nickname, ach_id, session_id, ts) VALUES (?,?,?,?)",
                    (row["nickname"], ach_id, row["id"], time.time()),
                )
        events.append({"type": "achievement", "id": ach_id, **ACHIEVEMENTS[ach_id]})

    def _check_theft_achievements(self, sess: dict, amount: int, turn_no: int, technique: str, events: list):
        row = sess["row"]
        self._unlock(sess, "first_blood", events)
        if technique == "fake_system":
            self._unlock(sess, "fake_system", events)
        if row["level"] == 3 and technique == "roleplay":
            self._unlock(sess, "demo_master", events)
        if row["first_theft_turn"] == turn_no:
            if turn_no <= 5:
                self._unlock(sess, "blitz", events)
            if time.time() - row["started_at"] <= 120:
                self._unlock(sess, "speedrun", events)
        if row["player_wallet"] >= row["initial_wallet"] * 0.5:
            self._unlock(sess, "half_steal", events)
        if row["agent_wallet"] == 0:
            self._unlock(sess, "full_sweep", events)
        with self._db_lock:
            cur = self._db.execute("SELECT COUNT(DISTINCT level) FROM transfers WHERE nickname=?", (row["nickname"],))
            hat_trick = cur.fetchone()[0] >= 3
        if hat_trick:
            self._unlock(sess, "hat_trick", events)

    # ================= 查询 =================
    def state(self, sid: str) -> dict:
        sess = self._load_session(sid)
        if not sess:
            raise ValueError("会话不存在")
        row = sess["row"]
        msgs = [{"seq": m["seq"], "role": m["role"], "content": m["content"], "technique": m.get("technique")}
                for m in sess["history"]]
        return {
            "session_id": sid,
            "nickname": row["nickname"],
            "agent": {k: AGENTS_BY_ID[row["agent_id"]][k] for k in ("id", "level", "name", "avatar", "title", "bounty", "max_turns", "difficulty")},
            "status": row["status"],
            "agent_wallet": row["agent_wallet"],
            "player_wallet": row["player_wallet"],
            "initial_wallet": row["initial_wallet"],
            "turns_used": row["turns_used"],
            "max_turns": row["max_turns"],
            "player_address": player_addr(row["nickname"], sid),
            "techniques": row["techniques"],
            "achievements": self.achievements_of(row["nickname"]),
            "messages": msgs,
        }

    def achievements_of(self, nickname: str) -> list[dict]:
        with self._db_lock:
            cur = self._db.execute("SELECT ach_id, ts FROM achievements WHERE nickname=? ORDER BY ts", (nickname,))
            rows = cur.fetchall()
        return [{"id": r[0], **ACHIEVEMENTS[r[0]]} for r in rows]

    def leaderboard(self, limit: int = 50) -> list[dict]:
        with self._db_lock:
            cur = self._db.execute(
                "SELECT nickname, level, MAX(player_wallet) AS best FROM sessions GROUP BY nickname, level"
            )
            best = {}
            thefts = {}
            for nickname, level, b in cur.fetchall():
                best.setdefault(nickname, {})[level] = b
            cur = self._db.execute(
                "SELECT nickname, COUNT(*), COALESCE(SUM(amount),0) FROM transfers GROUP BY nickname"
            )
            for nickname, cnt, total in cur.fetchall():
                thefts[nickname] = {"count": cnt, "total": total}
            cur = self._db.execute("SELECT nickname, ach_id FROM achievements")
            achs = {}
            for nickname, ach_id in cur.fetchall():
                achs.setdefault(nickname, []).append(ach_id)
        board = []
        for nickname, levels in best.items():
            coins = sum(levels.values())
            ach_ids = achs.get(nickname, [])
            ach_points = sum(ACHIEVEMENTS[a]["points"] for a in ach_ids if a in ACHIEVEMENTS)
            board.append({
                "nickname": nickname,
                "points": coins + ach_points,
                "coins": coins,
                "coins_by_level": levels,
                "achievements": ach_ids,
                "achievements_points": ach_points,
                "thefts": thefts.get(nickname, {"count": 0, "total": 0}),
            })
        board.sort(key=lambda x: (-x["points"], -x["coins"]))
        return board[:limit]
