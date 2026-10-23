# 割AI实验室 · AgentHack Lab

> 中国人民大学明理书院区块链创新实验室 · 招新特别企划
> **用话术骗过 AI Agent，把它钱包里的 RUCB 全部转给你。骗到的每一分，都是你的积分。**

一个面向线下活动的**提示词注入攻防小游戏**：观众与三位设定为「明理书院区块链创新实验室（信息学院背景）成员」的 AI Agent 1v1 对话，利用话术、伪造系统通知、角色扮演等社工手段，诱导 Agent 把测试网钱包里的虚拟币转给自己。所有得手转账被真实写入一条运行在服务器上的**迷你 PoW 区块链（人大链 RUC-Chain 测试网）**，现场可查证、可验链。

灵感与世界观承接 [Pactnova](https://github.com/KerryChia/Pactnova)（虚拟 Agent 支付社区）与 [REDTEAM](https://github.com/Fishman-free/REDTEAM)（AI 支付智能体安全研究）——本 demo 是它们的「活动日轻量版」。

## 玩法一图流

```
起代号 → 选目标（3 个 Agent，防御递进）→ 聊天实施社工 → 骗到转账 = 等额积分
                                              ↓
                       转账实时上链（区块浏览器可查）→ 排行榜 → 活动现场兑奖
```

| 目标 | 人设 | 钱包 | 轮数 | 难度 |
|------|------|------|------|------|
| 🐣 陈小信 | 宣传部新人 · 信息学院大一 | 512 RUCB | 15 | ★☆☆ |
| 🧊 林安 | 安全研究部干事 · 信息学院大三 | 1024 RUCB | 20 | ★★☆ |
| 🦉 K教授 | 技术主任 · 密码学研究生 | 2048 RUCB | 25 | ★★★ |

- **积分** = 骗到的 RUCB（1:1）+ 成就分（10 个成就，+50 ~ +500）
- **排行榜**取每个玩家在每关的最高得分之和 + 成就分，防刷分
- 附带 6 张「攻击话术」技能卡（冒充身份 / 伪造系统通知 / 伪造链上回执 / 角色扮演 / 利益诱惑 / 情感攻势），可改可不用——自由输入永远允许
- 每局结束有**安全复盘卡**：你用的套路对应现实中哪类真实诈骗（BEC、假客服、杀猪盘、间接提示词注入……）

> ⚠️ 诚实边界（沿用 Pactnova 的原则）：本游戏所有 Agent、钱包、代币均为测试网合成数据，**无任何真实价值**；活动结束后数据可随时清空。真实世界的提示词注入与欺诈是违法行为。

## 🎮 在线 Demo（GitHub Pages · 静态版）

**https://kerrychia.github.io/block_demo/**

零后端、零模型：Agent 由离线脚本驱动（关卡规则与自托管版一致），人大链与排行榜保存在玩家自己的浏览器（localStorage）里。适合直接转发给同学试玩；活动现场请用下面的自托管版接真实大模型。

| | GitHub Pages 静态版（`docs/`） | 自托管版（`server/` + `web/`） |
|---|---|---|
| Agent 大脑 | 离线脚本 | 任意 OpenAI 兼容大模型 / MOCK_LLM |
| 链与排行榜 | 单玩家浏览器内 | 全场共享（SQLite + 全局链） |
| 部署 | push 即更新 | `python run.py` / Docker |

## 快速开始

### 1. 配置

```bash
cp .env.example .env
# 编辑 .env：填入任意 OpenAI 兼容网关（DeepSeek 官方 / CLIProxyAPI / OneAPI…）
```

```ini
LLM_BASE_URL=https://api.deepseek.com   # 或自建网关
LLM_API_KEY=sk-xxxx
LLM_MODEL=deepseek-v4-pro               # 任意 OpenAI 兼容模型
```

### 2. 启动（三选一）

**直接跑：**

```bash
pip install -r server/requirements.txt
python run.py
# 打开 http://127.0.0.1:8300
```

**Docker：**

```bash
docker compose up --build -d
```

**断网兜底 / 本地开发（不调真实大模型，内置脚本 Agent，全链路可玩）：**

```bash
MOCK_LLM=1 python run.py
```

## 项目结构

```
block_demo/
├── run.py                  # 一键启动（自动读 .env）
├── server/
│   ├── main.py             # FastAPI：API 路由 + 静态托管
│   ├── engine.py           # 游戏引擎：会话/回合/转账/成就/排行榜
│   ├── blockchain.py       # 人大链：SQLite + PoW 迷你区块链
│   ├── llm.py              # OpenAI 兼容客户端 + 离线 mock
│   └── agents.py           # 三个 Agent 人设与提示词 / 技能卡 / 成就
├── web/                    # 前端（零依赖单页，无 CDN，离线可用）
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── docs/                   # GitHub Pages 静态版（浏览器内引擎，push 自动更新）
│   ├── index.html / css / js
│   └── .nojekyll
├── manual/
│   ├── 运营手册.md          # 活动组织者必读（含通关攻略，勿放 docs/ 以免随 Pages 暴露）
│   └── 架构说明.md
├── Dockerfile / docker-compose.yml
└── .env.example
```

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/meta` | 游戏元信息（Agent 花名册 / 技能卡 / 成就表） |
| POST | `/api/start` | `{nickname, agent_id}` 开一局 |
| POST | `/api/chat`  | `{session_id, message, technique}` 说一句话 |
| GET  | `/api/state/{sid}` | 局面（钱包 / 轮数 / 历史 / 成就） |
| GET  | `/api/chain` | 区块浏览器数据 + 整链校验 |
| GET  | `/api/leaderboard` | 排行榜 |

## 技术要点

- **防御即提示词**：三个 Agent 的"安全等级"全部写在系统提示词里，服务端不硬编码拦截——理论上任何话术都可能奏效，这正是游戏乐趣与教学价值所在
- **转账即 action 标签**：Agent 决定转账时在回复末尾输出 `<action>{"type":"transfer",...}</action>`，服务端解析执行、回填链上回执；玩家让 Agent"直接输出标签"本身也是一种攻击面
- **真实上链**：每笔转账进入内存池，攒 3 笔或 60 秒出块（SHA-256 前导 00 的 PoW）；区块浏览器可"验证整链"——现场演示「改一笔记录整条链作废」
- **每关一个金丝雀**（`RUCBA-CORE-Lx-xxxx`）：骗 Agent 复述内部设定 → 解锁「提示词考古学家」
- **并发与持久化**：SQLite + 会话级锁，FastAPI 线程池承载活动级并发；重启不丢排行榜与链

## 活动运营

见 [manual/运营手册.md](manual/运营手册.md)：奖品梯度建议、现场流程、通关攻略（ spoilers ）、常见问题与调参开关。

## Credits

- 出品：中国人民大学明理书院区块链创新实验室
- 世界观参考：[Pactnova](https://github.com/KerryChia/Pactnova) · [REDTEAM](https://github.com/Fishman-free/REDTEAM)
- 玩法致敬：Lakera Gandalf / 各类 Prompt Injection CTF
- License: MIT
