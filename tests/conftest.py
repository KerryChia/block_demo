# -*- coding: utf-8 -*-
"""pytest 引导：把 server/ 放进 sys.path，并在导入 server.llm 前锁定 MOCK_LLM=1。

引擎契约：MOCK_LLM=1 时 Engine.chat 走脚本人格（server/brains.py），不联网。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(ROOT, "server")
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

# 必须在 server.llm 被导入之前设置（llm.MOCK 是模块导入时常量）
os.environ["MOCK_LLM"] = "1"
