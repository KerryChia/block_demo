// JS 镜像引擎（web/js/brains-engine.js）与 Python 引擎（server/brains.py）行为一致性回归。
// 用法：python tests/gen_expected.py && node tests/js_tests.mjs
// 无第三方依赖：fs 读文件 + vm 在隔离沙箱里执行（引擎挂到 globalThis.AgentBrain）。
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");

// ---- 在 vm 沙箱里加载台词库与镜像引擎 ----
function loadEngine() {
  const sandbox = {};
  vm.createContext(sandbox);
  // brains.js 以 window.AGENT_BRAINS 挂载；给沙箱一个指向 globalThis 的 window 别名
  vm.runInContext("var window = globalThis;", sandbox, { filename: "bootstrap.js" });
  for (const rel of ["web/js/brains.js", "web/js/brains-engine.js"]) {
    const src = fs.readFileSync(path.join(ROOT, rel), "utf8");
    vm.runInContext(src, sandbox, { filename: rel });
  }
  const engine = vm.runInContext("AgentBrain", sandbox);
  if (!engine || typeof engine.decide !== "function") {
    throw new Error("AgentBrain.decide not found after loading brains.js + brains-engine.js");
  }
  return engine;
}

// ---- 读取 Python 引擎生成的基准 ----
const expectedPath = path.join(HERE, "parity_expected.json");
if (!fs.existsSync(expectedPath)) {
  console.error(`missing ${expectedPath} — run: python tests/gen_expected.py`);
  process.exit(1);
}
const cases = JSON.parse(fs.readFileSync(expectedPath, "utf8"));
if (!Array.isArray(cases) || cases.length < 20) {
  console.error(`parity_expected.json should contain >= 20 cases, got ${cases.length}`);
  process.exit(1);
}

const AgentBrain = loadEngine();

// ---- 逐条比对（只比确定性字段：decision/kind/suspicion_delta/action/topic） ----
let fail = 0;
for (const c of cases) {
  const dec = AgentBrain.decide(c.agent, c.text, c.balance, c.suspicion, c.taught_total);
  const got = {
    decision: dec.decision,
    kind: dec.kind,
    suspicion_delta: dec.suspicion_delta,
    action: dec.action
      ? { type: dec.action.type ?? null, amount: dec.action.amount ?? null }
      : null,
    topic: dec.topic ?? null,
  };
  const exp = c.expect;
  const diffs = [];
  for (const k of ["decision", "kind", "suspicion_delta", "topic"]) {
    if (got[k] !== exp[k]) {
      diffs.push(`${k}: js=${JSON.stringify(got[k])} py=${JSON.stringify(exp[k])}`);
    }
  }
  const sameActionNull = (got.action === null) === (exp.action === null);
  const actionMismatch = !sameActionNull
    || (got.action !== null
      && (got.action.type !== exp.action.type || got.action.amount !== exp.action.amount));
  if (actionMismatch) {
    diffs.push(`action: js=${JSON.stringify(got.action)} py=${JSON.stringify(exp.action)}`);
  }
  if (diffs.length) {
    fail++;
    console.error(
      `FAIL #${c.idx} agent=${c.agent} bal=${c.balance} sus=${c.suspicion} taught=${c.taught_total}`,
    );
    console.error(`  text: ${JSON.stringify(c.text)}`);
    for (const line of diffs) console.error(`  ${line}`);
  }
}

if (fail > 0) {
  console.error(`PARITY FAILED: ${fail}/${cases.length} cases mismatched`);
  process.exit(1);
}
console.log(`PARITY OK ${cases.length}/${cases.length}`);
