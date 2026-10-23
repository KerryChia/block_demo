# -*- coding: utf-8 -*-
"""构建同步脚本：
1. game/brains.json → web/js/brains.js（本地模式台词库）+ docs/js/brains.js
2. web/（唯一前端源码）→ docs/（GitHub Pages 目录，保留 .nojekyll）

用法：python sync_docs.py（改完 web/ 或 brains.json 后跑一次再提交）
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))

def build_brains():
    src = os.path.join(ROOT, "game", "brains.json")
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    payload = "window.AGENT_BRAINS = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    for dst in (os.path.join(ROOT, "web", "js", "brains.js"), os.path.join(ROOT, "docs", "js", "brains.js")):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="") as f:
            f.write(payload)
    agents = list(data["agents"].keys())
    topics = {k: len(v.get("smalltalk", [])) for k, v in data["agents"].items()}
    print(f"[brains] {len(agents)} agents -> brains.js: {topics}")

def sync_web_to_docs():
    src_dir = os.path.join(ROOT, "web")
    dst_dir = os.path.join(ROOT, "docs")
    copied = []
    for rel in ("index.html", os.path.join("css", "style.css"), os.path.join("js", "app.js"),
                os.path.join("js", "brains.js"), os.path.join("js", "brains-engine.js")):
        src = os.path.join(src_dir, rel)
        dst = os.path.join(dst_dir, rel)
        if not os.path.exists(src):
            print(f"[sync] 缺少源文件，跳过: {rel}")
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        copied.append(rel)
    nojekyll = os.path.join(dst_dir, ".nojekyll")
    if not os.path.exists(nojekyll):
        open(nojekyll, "w").close()
    print(f"[sync] web/ -> docs/: {', '.join(copied)}")

if __name__ == "__main__":
    build_brains()
    sync_web_to_docs()
    print("[done] 提交前记得 git add docs/")
