# -*- coding: utf-8 -*-
"""一键启动：python run.py（自动读取同目录 .env）"""
import os
import sys


def load_env(path: str = ".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "server"))
    load_env()
    import uvicorn
    from main import app  # noqa: E402  (在 sys.path 调整后导入)

    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8300")))
