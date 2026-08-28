// slice_wave_harness.mjs — loads slice-wave.workflow.js so it can be EXECUTED.
//
// The workflow file cannot be imported as an ES module: the Workflow host wraps
// the whole script in an implicit async function, so the file legally carries a
// top-level `return` and a top-level `await`. `node --check` refuses it in both
// module modes. The wrapping transform already exists in Python, as
// slice_wave_contract_base.wrapped_source(), and this module SHELLS OUT to it
// rather than re-implementing it, so there is exactly one wrapper in the repo
// and it cannot drift from the one the source-contract tests parse.
//
// The workflow uses no Node or host API of its own (it is pure logic over
// `args` plus the injected sandbox globals), which is what makes an
// AsyncFunction with mock globals a faithful driver of its control flow.

import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const WORKFLOW = join(HERE, "..", "workflows", "slice-wave.workflow.js");
const PY = "import sys; sys.path.insert(0, '.'); import slice_wave_contract_base as b; sys.stdout.write(b.wrapped_source())";

// The name of the function that slice_wave_contract_base.WRAP_HEAD declares.
// wrapped_source() is a PARSE wrapper: its body only DECLARES that function.
// To EXECUTE the workflow the harness appends a call to it, so this module now
// depends on that name. A rename in WRAP_HEAD would make the wave resolve
// undefined in silence, which is what WRAPPER_NAME plus the loader-integrity
// tests in slice_wave_behaviour.test.mjs exist to surface loudly.
export const WRAPPER_NAME = "__wrap";
const INVOKE = "\nreturn " + WRAPPER_NAME + "()\n";

// The ASSUMED host-sandbox contract. Written down as a named object on purpose:
// the repo specifies this nowhere (checked references/ and commands/), so the
// assumption is a diffable artifact instead of a caveat in prose that decays.
// `verified: false` is the honest state of every clause below.
export const HOST_CONTRACT = {
  agent: "agent(prompt, opts) resolves to a schema-valid object, or throws.",
  parallel: "parallel(fns) resolves an array of results, positional per input.",
  log: "log(message) is side-effect-free from the workflow's point of view.",
  budget: "budget.remaining() returns a number; budget.total is a number.",
  verified: false,
};

// The globals the host injects, in the order the AsyncFunction declares them.
const SANDBOX_PARAMS = ["args", "agent", "parallel", "log", "budget", "phase", "pipeline"];

export function rawSource() {
  return readFileSync(WORKFLOW, "utf8");
}

// Occurrences of a line-initial `export const`. The rewrite must match exactly
// once; a second top-level export, or zero, means the file's top-level shape
// changed and the harness would otherwise degrade in silence.
export function countExportConst(src) {
  return (src.match(/^export const\b/gm) || []).length;
}

// Memoized at module scope: one python3 spawn and one read across the
// whole suite, matching slice_wave_contract_base's module-level SOURCE pattern
// named in conventions.md.
let cachedWrapped = null;

export function wrappedSource() {
  cachedWrapped = cachedWrapped || readWrapped();
  return cachedWrapped;
}

function readWrapped() {
  // execFileSync throws on a non-zero exit, so a broken python side is loud.
  // The rethrow names BOTH dependencies by name, because the raw execFileSync
  // error is opaque about which of the two went missing.
  try {
    return execFileSync("python3", ["-c", PY], {
      cwd: HERE, encoding: "utf8", maxBuffer: 32 * 1024 * 1024,
    });
  } catch (err) {
    throw new Error(
      "slice_wave_harness needs python3 on PATH plus an importable "
      + "slice_wave_contract_base.wrapped_source() in "
      + HERE + ". Underlying failure: " + err.message,
    );
  }
}

// wrapped_source() DECLARES the wrapper and stops there. Appending the call is
// what makes this AsyncFunction body resolve the workflow's return value
// instead of undefined. The one existing Python transform is reused as-is; no
// second, divergent wrapper is introduced anywhere.
export function makeWave() {
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  return new AsyncFunction(...SANDBOX_PARAMS, wrappedSource() + INVOKE);
}

// Occurrences of the wrapper name in the wrapped source. Exactly one is the
// only healthy value: zero means WRAP_HEAD was renamed and INVOKE now names a
// function that does not exist.
export function countWrapperName(src) {
  return (src.match(/\b__wrap\b/g) || []).length;
}

const defaultSandbox = () => ({
  agent: async () => ({ status: "PLANNED" }),
  parallel: async (fns) => Promise.all(fns.map((f) => f())),
  log: () => {},
  budget: { total: 0, remaining: () => 1e9 },
  phase: () => {},
  pipeline: () => {},
});

export async function runWave(waveArgsObj, sandbox) {
  const s = { ...defaultSandbox(), ...sandbox };
  return makeWave()(waveArgsObj, s.agent, s.parallel, s.log, s.budget, s.phase, s.pipeline);
}

export function sliceFixture(id, riskTier) {
  return {
    id, goal: "goal of " + id, files: ["a.py"], subsystems: ["x"],
    deps: [], risk_tier: riskTier || 1, depth: 0, parent: null,
    branch: "spec-loop/t/" + id, base_sha: "0000000", worktree: "/tmp/wt/" + id,
  };
}

// `answers` is the controller's resume channel, keyed by escalation id. It is a
// parameter so a test can drive the round the workflow computes from it, rather
// than asserting the id scheme against a copy of the rule. `extra` carries any
// additional TOP-LEVEL wave arg a test needs to drive, such as the per-slice
// agent cap override map, so the harness never hand-builds a second args shape
// that could drift from this one.
export function waveArgs(slices, answers, extra) {
  return {
    run_id: "20260827-harness", wave_index: 0, slices, answers: answers || {},
    ctx: {
      run_dir: "/tmp/run", plugin_root: "/tmp/plugin", base_ref: "main",
      test_command: "true", conventions_path: "/tmp/run/conventions.md",
      shared_constraints: ["none"], tier3_surfaces: [],
      quality_gate_cmd: "true", models: { reviewer: "inherit" },
      thorough: false, polish: false,
    },
    ...(extra || {}),
  };
}

// ── Mock sandboxes and mock agent returns ────────────────────────────────
// Fixture DATA lives here, beside defaultSandbox, so the test module carries
// assertions and their rationale instead. Nothing below restates a workflow
// rule: every value is a schema-shaped agent return the wave reads.

export const capturePrompts = () => {
  const seen = [];
  return { seen, agent: async (prompt) => { seen.push(prompt); throw new Error("BOOM"); } };
};

const TASK_IDS = ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10", "t11", "t12"];
const PLAN_TWELVE = {
  status: "PLANNED", plan_path: "/tmp/plan.md",
  tasks: TASK_IDS.map((id) => ({ id, title: "task " + id, lane: "standard", files: ["a.py"] })),
};
const TASK_DONE = {
  status: "DONE", touched_files: [], concerns: [], deviations: [],
  commits: { base: "0000000", head: "c0ffee0" },
};

// Twelve standard tasks: one dispatch per task, so a tier-1 slice reaches its
// tier default inside stageTasks and a raised cap later, in stageReviewGate.
export const capAgent = () => ({
  agent: async (prompt, opts) => (String(opts.label).indexOf(":task:") > 0 ? TASK_DONE : PLAN_TWELVE),
});

// A one-task plan whose review returns a single P0 finding. Driving a tier-2
// slice with it runs plan, critique, task, review, gate, fix, re-review and
// verify - the eight dispatches PIPELINE_LABELS names - and ends the slice DONE.
const ONE_TASK_PLAN = {
  status: "PLANNED", plan_path: "/tmp/plan.md",
  tasks: [{ id: "t1", title: "task t1", lane: "standard", files: ["a.py"] }],
};
const P0_FINDING = {
  id: "f1", severity: "P0", category: "correctness", file: "a.py", line: 1,
  claim: "a claim", evidence: { quote: "q" }, remedy: "change it",
  confidence: "high", outside_diff: false,
};
const VERIFY_PASS = {
  suite: { command: "true", passed: true, summary: "ok" },
  quality: { summary_pass: true, violations: [], detail: "clean" },
  head_sha: "c0ffee0", tree_sha: "tree000",
};
const PIPELINE = {
  "plan": ONE_TASK_PLAN,
  "critic:full-council": { verdict: "ENDORSE", safety: { flag: false, reason: null }, concerns: [] },
  "task:t1": TASK_DONE,
  "review:full": { verdict: "APPROVE_WITH_FINDINGS", findings: [P0_FINDING], aspects_examined: {}, summary: "one finding" },
  "gate": VERIFY_PASS,
  "fix:1": { status: "DONE", touched_files: ["a.py"], addressed: ["r0-f1"], refuted: [], commits: { base: "0000000", head: "f1x0000" } },
  "re-review:1": { verdicts: [{ finding_id: "r0-f1", verdict: "ADDRESSED" }], new_breakage: [] },
  "verify:1": VERIFY_PASS,
};

export const PIPELINE_LABELS = Object.keys(PIPELINE).map((role) => "s1:" + role);

// Records the label and the prompt of every dispatch and answers each one with
// the return above. An unmapped role throws under its own name: a new stage
// must be mapped here rather than degrading a run into a fail-closed path in
// silence, which would quietly narrow whatever a test built on this asserts.
export const fullPipeline = () => {
  const seen = [];
  const agent = async (prompt, opts) => {
    const label = String(opts.label);
    const role = label.slice(label.indexOf(":") + 1);
    const mapped = PIPELINE[role];
    if (mapped === undefined) throw new Error("slice_wave_harness: no mock return mapped to role " + role);
    seen.push({ label, prompt });
    return mapped;
  };
  return { seen, agent };
};
