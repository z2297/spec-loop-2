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

export function sliceFixture(id) {
  return {
    id, goal: "goal of " + id, files: ["a.py"], subsystems: ["x"],
    deps: [], risk_tier: 1, depth: 0, parent: null,
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
