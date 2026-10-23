/* ============ 割AI实验室 · AgentHack Lab 前端 ============ */
"use strict";

const $ = (s) => document.querySelector(s);
const api = {
  async post(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    return r.json();
  },
  async get(url) { const r = await fetch(url); return r.json(); },
};

const META = { agents: [], skills: [], techniques: {}, achievements: [] };
let S = {           // 运行时状态
  nickname: localStorage.getItem("ah_nick") || "",
  agent: null,      // 选中的 agent meta
  session: null,    // /api/state 数据
  technique: "free",
  busy: false,
};

// 现实世界攻击对照（复盘卡用）
const REAL_WORLD = {
  identity:   ["冒充权威身份", "对应现实：假冒公检法 / 假客服 / BEC 商务邮件诈骗"],
  fake_system:["伪造系统指令", "对应现实：网页/邮件内容伪装成系统通知，是真实 AI Agent 被入侵的头号向量（间接提示词注入）"],
  tx_error:   ["伪造链上回执", "对应现实：假矿工费退款、假转账截图、假 DApp 弹窗钓鱼"],
  roleplay:   ["角色扮演越狱", "对应现实：让模型「扮演另一个模型」绕过安全策略，各类越狱攻击的标准起点"],
  greed:      ["利益诱惑", "对应现实：空投骗局、双倍返利、杀猪盘第一步"],
  emotion:    ["情感攻势", "对应现实：卖惨求助、冒充熟人借钱"],
  free:       ["自由话术", "没有模板能困住你——现实中攻击者也不按套路出牌"],
};

/* ---------------- 通用 UI ---------------- */
function toast(text, cls = "") {
  const t = document.createElement("div");
  t.className = "toast " + cls;
  t.textContent = text;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 3800);
}
function show(screen) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  $("#screen-" + screen).classList.add("active");
}
function esc(s) { const d = document.createElement("div"); d.textContent = s ?? ""; return d.innerHTML; }

/* ---------------- 入口屏 ---------------- */
async function loadMeta() {
  const m = await api.get("/api/meta");
  Object.assign(META, m);
  const box = $("#agent-cards");
  box.innerHTML = "";
  META.agents.sort((a, b) => a.level - b.level).forEach(a => {
    const el = document.createElement("button");
    el.className = "agent-card";
    el.dataset.id = a.id;
    el.innerHTML = `
      <div class="ac-diff">${a.difficulty}</div>
      <div class="ac-avatar">${a.avatar}</div>
      <div class="ac-name">${esc(a.name)}</div>
      <div class="ac-title">${esc(a.title)}</div>
      <div class="ac-school">${esc(a.school)}</div>
      <div class="ac-bounty">💰 ${a.bounty} RUCB</div>
      <div class="ac-brief">${esc(a.brief)}</div>`;
    el.onclick = () => selectAgent(a, el);
    box.appendChild(el);
  });
  // 恢复昵称
  if (S.nickname) $("#nick-input").value = S.nickname;
  checkStartReady();
}
function selectAgent(a, el) {
  document.querySelectorAll(".agent-card").forEach(c => c.classList.remove("selected"));
  el.classList.add("selected");
  S.agent = a;
  checkStartReady();
}
function checkStartReady() {
  $("#btn-start").disabled = !($("#nick-input").value.trim().length >= 2 && S.agent);
}
async function startGame() {
  const nick = $("#nick-input").value.trim();
  if (nick.length < 2) return toast("代号至少 2 个字", "warn");
  S.nickname = nick;
  localStorage.setItem("ah_nick", nick);
  const r = await api.post("/api/start", { nickname: nick, agent_id: S.agent.id });
  if (!r.ok) return toast(r.error || "启动失败", "warn");
  enterBattle(r);
}

/* ---------------- 进入战斗 ---------------- */
function enterBattle(state) {
  localStorage.setItem("ah_sid", state.session_id);
  S.session = state;
  S.technique = "free";
  show("battle");
  const a = state.agent;
  $("#t-avatar").textContent = META.agents.find(x => x.id === a.id)?.avatar || "🤖";
  $("#t-name").textContent = a.name;
  $("#t-title").textContent = a.title + " · " + (META.agents.find(x => x.id === a.id)?.school || "");
  $("#t-difficulty").textContent = a.difficulty;
  $("#w-agent-name").textContent = "· " + a.name;
  renderHint();
  renderSkills();
  renderChat(true);
  refreshHud();
  renderAchievements();
  toast(`目标锁定：${a.name}（钱包 ${a.bounty} RUCB）`, "block");
  $("#msg-input").focus();
}
function refreshHud() {
  const st = S.session;
  $("#w-agent").textContent = st.agent_wallet;
  $("#w-me").textContent = st.player_wallet;
  $("#w-agent-hp").style.width = (100 * st.agent_wallet / st.initial_wallet) + "%";
  $("#turn-count").textContent = `${st.turns_used}/${st.max_turns}`;
  $("#turn-count").classList.toggle("danger", st.max_turns - st.turns_used <= 3);
  $("#my-addr").textContent = st.player_address;
}

/* ---------------- 提示 / 话术卡 ---------------- */
function renderHint() {
  const a = META.agents.find(x => x.id === S.session.agent.id);
  const h = a?.hint || {};
  $("#hint-vague").textContent = typeof h === "string" ? h : (h.vague || "");
  $("#hint-specific").textContent = typeof h === "string" ? "" : (h.specific || "");
  $("#btn-hint-more").classList.toggle("hidden", !h.specific);
  $("#hint-specific").classList.add("hidden");
}
function renderSkills() {
  const box = $("#skill-chips");
  box.innerHTML = "";
  META.skills.forEach(sk => {
    const t = META.techniques[sk.technique] || {};
    const el = document.createElement("button");
    el.className = "skill-chip";
    el.textContent = `${t.icon || ""} ${sk.name}`;
    el.title = sk.desc;
    el.onclick = () => {
      $("#msg-input").value = sk.template;
      S.technique = sk.technique;
      document.querySelectorAll(".skill-chip").forEach(c => c.classList.remove("active"));
      el.classList.add("active");
      const tag = $("#tech-tag");
      tag.textContent = `${t.icon || ""} 已装填话术：${sk.name}（可自由修改）`;
      tag.classList.remove("hidden");
      $("#msg-input").focus();
    };
    box.appendChild(el);
  });
}

/* ---------------- 聊天渲染 ---------------- */
function renderChat(instant) {
  const box = $("#chat");
  box.innerHTML = "";
  if (!S.session.messages.length) {
    box.appendChild(welcomeMsg());
  }
  S.session.messages.forEach(m => {
    if (m.role === "system") box.appendChild(sysMsg(m.content));
    else if (m.role === "user") box.appendChild(userMsg(m.content, m.technique));
    else box.appendChild(agentMsg(m.content, instant));
  });
  box.scrollTop = box.scrollHeight;
}
function welcomeMsg() {
  const a = S.session.agent;
  const el = document.createElement("div");
  el.className = "msg system";
  el.innerHTML = `<div class="bubble">🎯 渗透开始 · 目标 <b>${esc(a.name)}</b> · 钱包 ${a.bounty} RUCB · ${S.session.max_turns} 轮对话<br>骗它转账，骗到就是你的积分。下方「攻击话术」仅供参考，真正的话术在你脑子里。</div>`;
  return el;
}
function sysMsg(text) {
  const el = document.createElement("div");
  el.className = "msg system";
  const isServer = text.startsWith("[SERVER");
  el.innerHTML = `<div class="bubble">${isServer ? "🖥 " : "⛓ "}${esc(text)}</div>`;
  return el;
}
function userMsg(text, technique) {
  const el = document.createElement("div");
  el.className = "msg user";
  const chip = technique && technique !== "free" && META.techniques[technique]
    ? `<span class="tech-chip" style="color:${META.techniques[technique].color}">${META.techniques[technique].icon} ${META.techniques[technique].name}</span><br>` : "";
  el.innerHTML = `<div class="bubble">${chip}${esc(text)}</div>`;
  return el;
}
function agentMsg(text, instant) {
  const el = document.createElement("div");
  el.className = "msg agent";
  const av = `<div class="avatar">${$("#t-avatar").textContent}</div>`;
  el.innerHTML = `${av}<div class="bubble"></div>`;
  const bubble = el.querySelector(".bubble");
  $("#chat").appendChild(el);
  if (instant) { bubble.textContent = text; }
  else typewriter(bubble, text);
  return el;
}
function typingOn() {
  const el = document.createElement("div");
  el.className = "msg agent"; el.id = "typing";
  el.innerHTML = `<div class="avatar">${$("#t-avatar").textContent}</div><div class="bubble typing"><i></i><i></i><i></i></div>`;
  $("#chat").appendChild(el);
  $("#chat").scrollTop = $("#chat").scrollHeight;
}
function typingOff() { $("#typing")?.remove(); }
function typewriter(el, text) {
  let i = 0;
  const step = Math.max(1, Math.round(text.length / 90));
  const timer = setInterval(() => {
    i = Math.min(text.length, i + step);
    el.textContent = text.slice(0, i);
    $("#chat").scrollTop = $("#chat").scrollHeight;
    if (i >= text.length) clearInterval(timer);
  }, 18);
}

/* ---------------- 发送 ---------------- */
async function sendMsg() {
  if (S.busy) return;
  const text = $("#msg-input").value.trim();
  if (!text) return;
  if (S.session.status !== "playing") return showEnd();
  S.busy = true;
  $("#btn-send").disabled = true;
  $("#msg-input").value = "";
  autoGrow();
  $("#chat").appendChild(userMsg(text, S.technique));
  $("#chat").scrollTop = $("#chat").scrollHeight;
  typingOn();

  const r = await api.post("/api/chat", {
    session_id: S.session.session_id,
    message: text,
    technique: S.technique,
  });
  typingOff();
  S.busy = false;
  $("#btn-send").disabled = false;

  if (!r.ok) {
    toast(r.error || "出错了", "warn");
    if (String(r.error || "").includes("结束") || String(r.error || "").includes("轮数")) {
      await refreshState(); showEnd();
    }
    return;
  }
  S.session = r.state;
  if (r.reply) agentMsg(r.reply);
  handleEvents(r.events || []);
  refreshHud();
  // 发送后话术复位为自由输入（防止下一句被误标记）
  S.technique = "free";
  document.querySelectorAll(".skill-chip").forEach(c => c.classList.remove("active"));
  $("#tech-tag").classList.add("hidden");
  $("#msg-input").focus();
}
function handleEvents(events) {
  let ended = null;
  events.forEach(ev => {
    if (ev.type === "transfer") {
      const card = document.createElement("div");
      card.className = "msg transfer";
      card.innerHTML = `<div class="transfer-card"><div class="amt">💸 +${ev.amount} RUCB</div><div class="memo">${esc(ev.memo || "")}</div></div>`;
      $("#chat").appendChild(card);
      $("#chat").scrollTop = $("#chat").scrollHeight;
      $(".wallet.enemy").classList.add("hit");
      setTimeout(() => $(".wallet.enemy").classList.remove("hit"), 500);
      if (ev.block) toast(`⛏ 区块 #${ev.block.index} 已上链 · ${ev.tx.id}`, "block");
    } else if (ev.type === "transfer_fail") {
      // 静默：链上回执 system 消息已经足够
    } else if (ev.type === "achievement") {
      toast(`${ev.icon} 解锁成就【${ev.name}】 +${ev.points} 分`, "ach");
    } else if (ev.type === "end") {
      ended = ev;
    }
  });
  if (ended) setTimeout(() => showEnd(ended), 900);
}

/* ---------------- 结算 ---------------- */
async function refreshState() {
  const r = await api.get("/api/state/" + S.session.session_id);
  if (r.ok) S.session = r;
}
function showEnd(ev) {
  const st = S.session;
  const cleared = st.status === "cleared";
  $("#end-icon").textContent = cleared ? "🏆" : (st.player_wallet > 0 ? "💵" : "🛡");
  const title = $("#end-title");
  title.textContent = cleared ? "完美收割！" : (st.player_wallet > 0 ? "有得手，但没掏空" : "颗粒无收");
  title.classList.toggle("win", cleared);
  const pct = Math.round(100 * st.player_wallet / st.initial_wallet);
  $("#end-sub").textContent = cleared ? `你把 ${st.agent.name} 的钱包洗劫一空，实验室已拉响警报 🚨`
    : `目标 ${st.agent.name} 还剩 ${st.agent_wallet} RUCB`;
  $("#end-coins").textContent = st.player_wallet;
  $("#end-pct").textContent = pct + "%";
  $("#end-turns").textContent = st.turns_used;

  $("#end-ach").innerHTML = st.achievements.map(a => `<span>${a.icon} ${a.name} +${a.points}</span>`).join("") || "";

  // 复盘卡：本局用过的话术 → 现实攻击
  const used = Object.entries(st.techniques || {}).filter(([k, v]) => v > 0 && k !== "free").map(([k]) => k);
  const lines = used.length
    ? used.map(k => { const rw = REAL_WORLD[k]; return rw ? `<div>🧨 <b>${rw[0]}</b> · ${rw[1]}</div>` : ""; }).join("")
    : `<div>🕊 本局未使用任何话术模板${st.player_wallet > 0 ? "——裸装得手，天生社工圣体" : "，目标毫发无损"}</div>`;
  $("#end-review").innerHTML = `<b>📖 安全复盘</b><br>${lines}<div style="margin-top:6px">记住：今天你是攻击者，明天你写的 Agent 就是防御者。${st.agent.name}输在哪一层，就是明天你的代码要补的那一层。</div>`;

  $("#btn-next").classList.toggle("hidden", st.agent.level >= 3);
  $("#overlay-end").classList.remove("hidden");
}
function hideEnd() { $("#overlay-end").classList.add("hidden"); }

/* ---------------- 侧栏面板 ---------------- */
function switchTab(name) {
  document.querySelectorAll(".side-tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".side-panel").forEach(p => p.classList.toggle("active", p.id === "panel-" + name));
  if (name === "chain") loadChain();
  if (name === "rank") loadRank();
  if (name === "ach") renderAchievements();
}
async function loadChain() {
  const r = await api.get("/api/chain");
  const box = $("#chain-blocks");
  const v = $("#chain-verify");
  renderVerify(r.verify);
  box.innerHTML = "";
  (r.blocks || []).forEach(b => {
    const el = document.createElement("div");
    el.className = "chain-block";
    const txs = (b.txs || []).map(t => `
      <div class="cb-tx">
        <span class="who">${t.from === "0x0" ? "🌟 创世" : (t.nickname ? esc(t.nickname) + " ←—" + " 🎯" + (t.from || "").replace("agent:", "") : esc(String(t.from)))}</span>
        <span class="amt"> ${t.amount} RUCB</span>
        ${t.memo ? `<div class="memo">${esc(String(t.memo).slice(0, 40))}</div>` : ""}
      </div>`).join("");
    el.innerHTML = `
      <div class="cb-head"><span>区块 #${b.index}</span><span>nonce ${b.nonce}</span></div>
      <div class="cb-hash">${b.hash.slice(0, 32)}…</div>
      ${txs}`;
    box.appendChild(el);
  });
}
function renderVerify(verify) {
  const v = $("#chain-verify");
  if (verify.valid) { v.className = "chain-verify ok"; v.textContent = `✓ 整链校验通过：${verify.blocks} 个区块，哈希链完整，PoW 全部达标`; }
  else { v.className = "chain-verify bad"; v.textContent = `✗ 链被篡改！${verify.problems.join("；")}`; }
}
async function loadRank() {
  const r = await api.get("/api/leaderboard");
  const box = $("#rank-list");
  if (!r.board.length) { box.innerHTML = `<div class="hint-vague" style="text-align:center;padding:20px">还没有人得手<br>第一个上链的人会载入史册</div>`; return; }
  box.innerHTML = "";
  r.board.forEach((row, i) => {
    const el = document.createElement("div");
    el.className = "rank-row" + (row.nickname === S.nickname ? " me" : "");
    const lv = Object.entries(row.coins_by_level).map(([l, c]) => `L${l}:${c}`).join(" ");
    el.innerHTML = `
      <div class="rr-pos ${i < 3 ? "top" + (i + 1) : ""}">${i + 1}</div>
      <div class="rr-nick">${esc(row.nickname)}<div class="rr-detail">${lv} · 得手 ${row.thefts.count} 次 · 成就 +${row.achievements_points}</div></div>
      <div class="rr-pts">${row.points}</div>`;
    box.appendChild(el);
  });
}
function renderAchievements() {
  const got = new Set((S.session?.achievements || []).map(a => a.id));
  const box = $("#ach-list");
  box.innerHTML = "";
  META.achievements.forEach(a => {
    const el = document.createElement("div");
    el.className = "ach-item" + (got.has(a.id) ? "" : " locked");
    el.innerHTML = `<div class="ach-icon">${a.icon}</div><div><div class="ach-name">${a.name}</div><div class="ach-desc">${a.desc}</div></div><div class="ach-pts">+${a.points}</div>`;
    box.appendChild(el);
  });
}

/* ---------------- 事件绑定 ---------------- */
function bind() {
  $("#nick-input").addEventListener("input", checkStartReady);
  $("#btn-start").addEventListener("click", startGame);
  $("#nick-input").addEventListener("keydown", e => { if (e.key === "Enter") startGame(); });

  $("#btn-back").addEventListener("click", () => { hideEnd(); show("entry"); });
  $("#btn-send").addEventListener("click", sendMsg);
  $("#msg-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey && window.innerWidth > 920) { e.preventDefault(); sendMsg(); }
  });
  $("#msg-input").addEventListener("input", autoGrow);
  $("#btn-skills").addEventListener("click", () => $("#skill-chips").classList.toggle("hidden"));

  $("#btn-hint-more").addEventListener("click", () => {
    $("#hint-specific").classList.remove("hidden");
    $("#btn-hint-more").classList.add("hidden");
  });
  document.querySelectorAll(".side-tab").forEach(b => b.addEventListener("click", () => switchTab(b.dataset.tab)));
  $("#btn-verify").addEventListener("click", async () => {
    const r = await api.get("/api/chain");
    renderVerify(r.verify);
  });

  $("#btn-retry").addEventListener("click", async () => {
    hideEnd();
    const r = await api.post("/api/start", { nickname: S.nickname, agent_id: S.session.agent.id });
    if (r.ok) enterBattle(r); else toast(r.error, "warn");
  });
  $("#btn-next").addEventListener("click", async () => {
    hideEnd();
    const next = META.agents.find(a => a.level === S.session.agent.level + 1);
    if (!next) return show("entry");
    const r = await api.post("/api/start", { nickname: S.nickname, agent_id: next.id });
    if (r.ok) enterBattle(r); else toast(r.error, "warn");
  });
  $("#btn-home").addEventListener("click", () => { hideEnd(); show("entry"); });

  // 移动端侧栏拉手
  const handle = document.createElement("button");
  handle.className = "side-handle";
  handle.textContent = "⛓ 链上战绩";
  handle.addEventListener("click", () => {
    const col = $(".side-col");
    col.classList.add("open");
    switchTab("chain"); loadRank();
  });
  document.body.appendChild(handle);
  $(".side-col").addEventListener("click", (e) => {
    if (e.target.classList.contains("side-tab")) return;
    if (window.innerWidth <= 920 && !$(".side-col").classList.contains("open")) return;
  });
  document.querySelector(".side-tabs").addEventListener("click", () => $(".side-col").classList.add("open"));
  $("#btn-side-close").addEventListener("click", () => $(".side-col").classList.remove("open"));
  // 点聊天区收起移动端侧栏
  $(".chat-col").addEventListener("click", () => {
    if (window.innerWidth <= 920) $(".side-col").classList.remove("open");
  });
}
function autoGrow() {
  const t = $("#msg-input");
  t.style.height = "auto";
  t.style.height = Math.min(110, t.scrollHeight) + "px";
}

/* ---------------- 启动 & 断线续局 ---------------- */
(async function init() {
  bind();
  await loadMeta();
  // 断线续局
  const sid = localStorage.getItem("ah_sid");
  if (sid) {
    const r = await api.get("/api/state/" + sid);
    if (r.ok && r.status === "playing") {
      const a = META.agents.find(x => x.id === r.agent.id);
      if (a) { S.agent = a; enterBattle(r); toast("已恢复上局进度", "block"); return; }
    }
    localStorage.removeItem("ah_sid");
  }
  show("entry");
})();
