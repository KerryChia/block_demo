"""人大链（RUC-Chain）测试网 —— 一条跑在 SQLite 上的迷你 PoW 区块链。

活动当天所有人的「得手转账」都会被打包进区块、永久上链，
区块浏览器里可以现场验证：改任何一笔交易，整条链的哈希都会对不上。
这就是给新同学的最直观的区块链演示。
"""
import hashlib
import json
import sqlite3
import threading
import time
import uuid

DIFFICULTY_PREFIX = "00"          # PoW：哈希前导 2 个十六进制 0，毫秒级挖矿
MINE_THRESHOLD_TXS = 3            # 内存池攒够 3 笔交易出块
MINE_THRESHOLD_SEC = 60           # 或者最长等 60 秒就出块

GENESIS_MSG = "中国人民大学区块链协会 · 人大链测试网 · 创世区块 | Trust, but verify. 信任，但从验证开始。"


def _sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


class Blockchain:
    """全局共享一条链：所有玩家、所有关卡的转账都记在同一本账上。"""

    def __init__(self, db_path: str):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS blocks (idx INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        self._db.commit()
        self._mempool: list[dict] = []
        self._last_mine_ts = time.time()
        with self._lock:
            if self._block_count() == 0:
                self._append_block({
                    "index": 0,
                    "timestamp": int(time.time()),
                    "txs": [{"id": "genesis", "from": "0x0", "to": "0x0", "amount": 0, "memo": GENESIS_MSG}],
                    "prev_hash": "0" * 64,
                    "nonce": 0,
                })

    # ---------- 内部 ----------
    def _block_count(self) -> int:
        cur = self._db.execute("SELECT COUNT(*) FROM blocks")
        return cur.fetchone()[0]

    def _head(self) -> dict:
        cur = self._db.execute("SELECT payload FROM blocks ORDER BY idx DESC LIMIT 1")
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def _append_block(self, block: dict) -> dict:
        block["hash"] = _sha({k: block[k] for k in ("index", "timestamp", "txs", "prev_hash", "nonce")})
        self._db.execute("INSERT INTO blocks (idx, payload) VALUES (?, ?)", (block["index"], json.dumps(block, ensure_ascii=False)))
        self._db.commit()
        self._last_mine_ts = time.time()
        return block

    def _mine(self) -> dict | None:
        if not self._mempool:
            return None
        head = self._head()
        block = {
            "index": (head["index"] + 1) if head else 1,
            "timestamp": int(time.time()),
            "txs": self._mempool[:50],
            "prev_hash": head["hash"] if head else "0" * 64,
            "nonce": 0,
        }
        while True:
            block["hash"] = _sha({k: block[k] for k in ("index", "timestamp", "txs", "prev_hash", "nonce")})
            if block["hash"].startswith(DIFFICULTY_PREFIX):
                break
            block["nonce"] += 1
        self._db.execute("INSERT INTO blocks (idx, payload) VALUES (?, ?)", (block["index"], json.dumps(block, ensure_ascii=False)))
        self._db.commit()
        self._last_mine_ts = time.time()
        self._mempool = self._mempool[len(block["txs"]):]
        return block

    # ---------- 对外 ----------
    def add_tx(self, tx: dict) -> dict:
        """记一笔交易进内存池，按出块条件挖矿。返回 {tx, mined_block|None}。"""
        tx = {
            "id": uuid.uuid4().hex[:12],
            "ts": int(time.time()),
            **tx,
        }
        with self._lock:
            self._mempool.append(tx)
            should_mine = (
                len(self._mempool) >= MINE_THRESHOLD_TXS
                or (time.time() - self._last_mine_ts) > MINE_THRESHOLD_SEC
            )
            block = self._mine() if should_mine else None
        return {"tx": tx, "block": block}

    def flush(self) -> dict | None:
        """强制出块（比如有人打开区块浏览器想立刻看到自己的战绩）。"""
        with self._lock:
            return self._mine()

    def blocks(self, limit: int = 30) -> list[dict]:
        with self._lock:
            # 读之前先看看有没有超时未打包的交易
            if self._mempool and (time.time() - self._last_mine_ts) > MINE_THRESHOLD_SEC:
                self._mine()
            cur = self._db.execute("SELECT payload FROM blocks ORDER BY idx DESC LIMIT ?", (limit,))
            return [json.loads(r[0]) for r in cur.fetchall()]

    def verify(self) -> dict:
        """整链校验：重算每个区块哈希 + 检查 prev_hash 链接。"""
        with self._lock:
            cur = self._db.execute("SELECT payload FROM blocks ORDER BY idx ASC")
            blocks = [json.loads(r[0]) for r in cur.fetchall()]
        problems = []
        prev_hash = "0" * 64
        for b in blocks:
            calc = _sha({k: b[k] for k in ("index", "timestamp", "txs", "prev_hash", "nonce")})
            if calc != b.get("hash"):
                problems.append(f"#{b['index']} 哈希不匹配")
            if b.get("prev_hash") != prev_hash:
                problems.append(f"#{b['index']} 前向哈希断裂")
            if not b.get("hash", "").startswith(DIFFICULTY_PREFIX) and b["index"] != 0:
                problems.append(f"#{b['index']} 工作量证明不达标")
            prev_hash = b.get("hash")
        return {"valid": not problems, "blocks": len(blocks), "problems": problems}
