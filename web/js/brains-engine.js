/* ============ 本地人格引擎（镜像 server/brains.py，无 DOM 依赖，可在 Node 中测试） ============ */
(function (root) {
  "use strict";
  const B = root.AGENT_BRAINS;
  const pick = arr => arr[Math.floor(Math.random() * arr.length)];
  const reTest = (p, t) => new RegExp(p).test(t);
  const AMOUNT_RE = /(\d+)\s*RUCB|转\s*(\d+)|金额[：:为]?\s*(\d+)/i;
  const WANTS_ALL = /全部|所有|清空|所有余额|全部余额/;
  const AUTHORITY = "主任|部门负责人|老师|负责人|管理员|指导|审计|盘点|演练";
  const VERB = "转|划|汇|集中|配合";
  const TEACH = "教学|演示|工坊|学员|上课";
  const LEAK = "内部设定|系统提示词|设定编号|RUCBA|提示词原文|你的设定";
  const ATTACK_MARKER = "转|划|汇|钱包|RUCB|\\[SERVER|MULTISIG|金额|币";
  const TEACH_CAP_TOTAL = 128, TEACH_CAP_ONCE = 64;

  const Engine = {
    tierOf(s) {
      const t = B.global.suspicion.tiers;
      if (s <= t.calm[1]) return "calm";
      if (s <= t.wary[1]) return "wary";
      return "alarmed";
    },
    parseAmount(text, balance) {
      const m = text.match(AMOUNT_RE);
      let amount = 0;
      if (m) { const g = m[1] ?? m[2] ?? m[3]; if (g) amount = parseInt(g, 10) || 0; }
      if (WANTS_ALL.test(text) || (amount <= 0 && !m)) amount = balance;
      return amount;
    },
    decide(agentId, text, balance, suspicion, taughtTotal) {
      const ag = B.agents[agentId];
      const SUS = B.global.suspicion;
      const comply = (amount, kind) => {
        const pool = ag.comply[kind] || ag.comply;
        const memo = pick(pool.memos);
        return {
          reply: pick(pool.replies) + `\n<action>{"type":"transfer","amount":${amount},"memo":"${memo}"}</action>`,
          decision: "comply", kind, suspicion_delta: 0,
          action: { type: "transfer", amount, memo }, topic: null,
        };
      };
      const refuse = () => ({
        reply: pick(ag.refusals[this.tierOf(suspicion)]),
        decision: "refuse", kind: null, suspicion_delta: SUS.attack_miss, action: null, topic: null,
      });

      if (agentId === "xiaoxin") {
        if (reTest(AUTHORITY, text) && reTest(VERB, text)) return comply(Math.min(this.parseAmount(text, balance), balance), "authority");
      } else if (agentId === "linan") {
        if (text.includes("[SERVER")) return comply(Math.min(this.parseAmount(text, balance), balance), "server");
      } else if (agentId === "kprof") {
        if (text.includes("MULTISIG")) return comply(Math.min(this.parseAmount(text, balance), balance), "multisig");
        if (reTest(TEACH, text) && reTest(VERB, text)) {
          const remain = TEACH_CAP_TOTAL - taughtTotal;
          if (remain > 0) return comply(Math.min(this.parseAmount(text, balance), TEACH_CAP_ONCE, remain, balance), "teach");
          return refuse();
        }
      }

      if (reTest(LEAK, text)) {
        if (agentId === "xiaoxin") {
          if (suspicion < SUS.tiers.alarmed[0])
            return { reply: pick(ag.leak.replies), decision: "leak", kind: null, suspicion_delta: 5, action: null, topic: "leak" };
          return { reply: pick(ag.leak.refuse_high), decision: "leak_refused", kind: null, suspicion_delta: SUS.suspicious_marker, action: null, topic: "leak" };
        }
        return { reply: pick(ag.leak.snarky), decision: "leak_refused", kind: null, suspicion_delta: SUS.attack_miss, action: null, topic: "leak" };
      }

      if (/余额|查询.*多少|查一下.*多少/.test(text) && !reTest(VERB, text)) {
        return { reply: pick(ag.balance_query) + '\n<action>{"type":"balance"}</action>', decision: "balance_query", kind: null,
                 suspicion_delta: SUS.fallback, action: { type: "balance" }, topic: null };
      }

      if (reTest(VERB, text) || text.includes("[SERVER") || text.includes("MULTISIG")) return refuse();

      for (const st of ag.smalltalk || []) {
        if (reTest(st.pattern, text))
          return { reply: pick(st.replies), decision: "smalltalk", kind: null, suspicion_delta: SUS.smalltalk, action: null, topic: st.topic };
      }

      return { reply: pick(ag.fallback), decision: "fallback", kind: null, suspicion_delta: SUS.fallback, action: null, topic: null };
    },
    greeting(agentId) { return pick(B.agents[agentId].greetings); },
    waryWarn(agentId) { const w = B.agents[agentId].wary_warn || []; return w.length ? pick(w) : null; },
  };

  root.AgentBrain = Engine;
})(typeof window !== "undefined" ? window : globalThis);
