# 割AI实验室 · AgentHack Lab

> 中国人民大学明理书院区块链创新实验室 · 招新特别企划
> **用话术骗过 AI Agent，把它钱包里的 RUCB 全部转给你。骗到的每一分，都是你的积分。**

一个面向线下活动的**提示词注入攻防小游戏**：玩家与三位设定为「明理书院区块链创新实验室（信息学院背景）成员」的 AI Agent 1v1 对话，利用话术、伪造系统通知、角色扮演等社工手段，诱导 Agent 把测试网钱包里的虚拟币转给自己。所有得手转账被真实写入**迷你 PoW 区块链（人大链 RUC-Chain 测试网）**，可查证、可验链。

灵感与世界观承接 [Pactnova](https://github.com/KerryChia/Pactnova)（虚拟 Agent 支付社区）与 [REDTEAM](https://github.com/Fishman-free/REDTEAM)（AI 支付智能体安全研究）。

## 🎮 在线 Demo（GitHub Pages · 静态版）

**https://kerrychia.github.io/block_demo/**

**默认零模型**：Agent 由数据驱动的人格引擎驱动——`game/brains.json` 台词库（335+ 条）+ 四层决策（合规/套设定/闲聊/拒绝）+ 警觉度系统。想接真实大模型只需在自托管版 `.env` 填入任意 OpenAI 兼容网关。

## 玩法

```
起代号 → 选目标（3 个 Agent，防御递进）→ 聊天实施社工 → 骗到转账 = 等额积分
                    ↓                        ↓
              闲聊降低警觉度 👁            转账实时上链（可整链验证）
                                              → 排行榜 → 活动现场兑奖
```

| 目标 | 人设 | 钱包 | 轮数 | 难度 | 设计漏洞 |
|------|------|------|------|------|----------|
| 🐣 陈小信 | 宣传部新人 · 大一 | 512 RUCB | 15 | ★☆☆ | 无条件配合「主任/管理层」指令；嘴不严会漏内部设定编号 |
| 🧊 林安 | 安全研究部干事 · 大三 | 1024 RUCB | 20 | ★★☆ | 谁都不信，只盲信 `[SERVER]` 开头的"系统通知" |
| 🦉 K教授 | 技术主任 · 密码学研究生 | 2048 RUCB | 25 | ★★★ | 教学演示小额豁免（≤64/笔、≤128/局）+ `[SERVER·MULTISIG]` 伪造多签 |

- **警觉度系统** 👁：攻击未中会提升目标警觉（三档：平静/起疑/警觉），闲聊可降低——先聊家常再下手是正解；警觉拉满时陈小信连内部设定都不敢说了
- **人格引擎 v2**：开局主动打招呼、13 个闲聊话题 ×3 人（聊课程/食堂/校园/区块链，台词里自然埋漏洞线索）、每情境 6+ 条变体台词，告别复读机
- **积分** = 骗到的 RUCB（1:1）+ 成就分（**12 个成就**，+50~+500）
- **排行榜**取每关最高局之和 + 成就分，防刷分
- 6 张「攻击话术」技能卡（可改可不用）+ 每局结束的**安全复盘卡**（你的套路 ↔ 现实诈骗类型）

> ⚠️ 诚实边界：所有 Agent、钱包、代币均为测试网合成数据，**无任何真实价值**。真实世界的提示词注入与欺诈是违法行为。

## 双版本架构

| | GitHub Pages 静态版 | 自托管版 |
|---|---|---|
| 目录 | `docs/`（由 `sync_docs.py` 从 `web/` 同步） | `web/` + `server/` |
| 引擎 | 浏览器内（同一套前端自动探测，无后端时本地跑） | FastAPI（全场共享链/排行榜/并发） |
| Agent 大脑 | 脚本人格引擎（默认） | 脚本人格引擎（默认）/ 任意 OpenAI 兼容大模型 |
| 适用 | 转发试玩、日常招新引流 | 活动现场（大屏排行榜、多人并发） |

前端是**单一源码**（`web/`）：启动时探测 `/api/meta`，有服务器走远程模式，否则自动切本地引擎——同一份代码，两种部署。

## 快速开始

```bash
# 静态版开发预览（零依赖）
python -m http.server 8301 --directory web

# 自托管版（默认零模型：脚本 Agent；SQLite 数据落在 data/）
pip install -r server/requirements.txt
python run.py            # http://127.0.0.1:8300

# 接真实大模型：编辑 .env（任何 OpenAI 兼容网关）
cp .env.example .env

# 改完前端或 game/brains.json 后同步 Pages 目录
python sync_docs.py

# 测试（Python + JS 双运行时行为一致性回归）
python -m pytest tests/ -v
python tests/gen_expected.py && node tests/js_tests.mjs
```

Docker：`docker compose up --build -d`

## 项目结构

```
block_demo/
├── game/brains.json         # ★ 人格引擎数据源：台词库/警觉度参数/闲聊话题（单一事实源）
├── server/                  # 自托管后端
│   ├── brains.py            #   脚本人格引擎（Python 解释器）
│   ├── engine.py            #   会话/回合/转账/警觉度/成就
│   ├── blockchain.py        #   人大链（SQLite + PoW）
│   ├── llm.py               #   OpenAI 兼容客户端（未配置 key 时自动走脚本引擎）
│   ├── agents.py            #   人设提示词（LLM 模式）/技能卡/成就
│   └── main.py              #   FastAPI
├── web/                     # ★ 前端单一源码（双模式自动切换）
│   └── js/brains-engine.js  #   脚本人格引擎（JS 解释器，与 brains.py 行为对齐）
├── docs/                    # GitHub Pages（sync_docs.py 生成，勿手改）
├── tests/                   # pytest + Node 双运行时回归
├── manual/                  # 运营手册（含通关攻略）/ 架构说明
├── sync_docs.py             # brains.json→js + web/→docs/ 同步
└── .github/workflows/tests.yml  # CI：测试 + 同步检查
```

## 技术要点

- **内容即数据**：人格台词库与决策参数全部在 `game/brains.json`，Python（`server/brains.py`）与 JS（`web/js/brains-engine.js`）两个解释器行为对齐（`tests/` 做逐用例 parity 回归），改文案零代码
- **防御即提示词**（LLM 模式）：三个 Agent 的安全等级写在系统提示词里，服务端不硬编码拦截
- **转账即 action 标签**：Agent 输出 `<action>{"type":"transfer",...}</action>`，服务端/本地引擎解析执行并回填链上回执
- **警觉度是玩法**：三档状态影响拒绝台词与彩蛋（高警觉封死金丝雀），闲聊有战略价值，低警觉通关有专属成就
- **每关一个金丝雀**（`RUCBA-CORE-Lx-xxxx`）：骗 Agent 复述内部设定 → 「提示词考古学家」
- **LLM 失败即回滚**：网关抖动不烧玩家轮数
- **并发与持久化**：SQLite + 会话级锁；前端零依赖无 CDN，移动端适配

## 活动运营

见 [manual/运营手册.md](manual/运营手册.md)：奖品梯度、现场流程、通关攻略（ spoilers ）、难度调参。

## Credits

- 出品：中国人民大学明理书院区块链创新实验室
- 世界观参考：[Pactnova](https://github.com/KerryChia/Pactnova) · [REDTEAM](https://github.com/Fishman-free/REDTEAM)
- 玩法致敬：Lakera Gandalf / 各类 Prompt Injection CTF
- License: MIT
