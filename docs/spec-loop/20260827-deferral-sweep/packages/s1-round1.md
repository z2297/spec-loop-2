# Review package: 299f0dbd1f700f8f3b3991ea7d601df797dd3749..6f9b7b0  (context: -U5)

## Commits
6f9b7b0 ci(wave): run the behavioural harness in validate.yml with a fail-closed count floor
09a291e test(wave): pin per-slice escalation-id attribution at wave width 4
9f40fb1 test(wave): pin the lost-slice record's single substituted option, distinct from the crash record
a7ed7fb test(wave): pin the caught-exception internal-error record by execution
e796026 test(wave): load slice-wave.workflow.js through wrapped_source() into an executable AsyncFunction

## Files changed
 .github/workflows/validate.yml                     |  20 +++
 .../scripts/slice_wave_behaviour.test.mjs          | 161 +++++++++++++++++++++
 .../spec-loop/scripts/slice_wave_contract_base.py  |  26 +++-
 plugins/spec-loop/scripts/slice_wave_harness.mjs   | 135 +++++++++++++++++
 4 files changed, 339 insertions(+), 3 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
".github/workflows/validate.yml": [
[
62,
81
]
],
"plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs": [
[
1,
161
]
],
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
3,
9
],
[
35,
44
],
[
274,
279
]
],
"plugins/spec-loop/scripts/slice_wave_harness.mjs": [
[
1,
135
]
]
}
```

## Diff
diff --git a/.github/workflows/validate.yml b/.github/workflows/validate.yml
index 9e755b6..fcec2d9 100644
--- a/.github/workflows/validate.yml
+++ b/.github/workflows/validate.yml
@@ -57,10 +57,30 @@ jobs:
           ran=$(printf '%s\n' "$out" | sed -n 's/^# tests \([0-9][0-9]*\).*/\1/p')
           if [ "${ran:-0}" -lt 12 ]; then
             echo "FAIL: only ${ran:-0} client JS tests ran (expected >= 12)"; exit 1
           fi
 
+      - name: Wave workflow behavioural harness (Node)
+        # The ONLY lane in which slice-wave.workflow.js actually EXECUTES. It is
+        # loaded through slice_wave_contract_base.wrapped_source(), so this step
+        # needs the python3 set up earlier in this job as well as node. Two
+        # gates, both fail closed, mirroring the client JS step: exit status,
+        # and a minimum TAP count so an emptied file cannot pass silently.
+        # Scope: deterministic control flow only. The real Workflow-host seam
+        # is NOT covered here — see the test file's own honest-limit header.
+        run: |
+          out=$(node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs 2>&1)
+          rc=$?
+          echo "$out"
+          if [ "$rc" -ne 0 ]; then
+            echo "FAIL: wave harness exited non-zero (rc=$rc)"; exit "$rc"
+          fi
+          ran=$(printf '%s\n' "$out" | sed -n 's/^# tests \([0-9][0-9]*\).*/\1/p')
+          if [ "${ran:-0}" -lt 14 ]; then
+            echo "FAIL: only ${ran:-0} wave harness tests ran (expected >= 14)"; exit 1
+          fi
+
       - name: Install Claude Code CLI
         run: npm install -g @anthropic-ai/claude-code
 
       - name: Official plugin validation
         run: |
diff --git a/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
new file mode 100644
index 0000000..58bedb8
--- /dev/null
+++ b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
@@ -0,0 +1,161 @@
+// slice_wave_behaviour.test.mjs — the first EXECUTING test of the wave workflow.
+//
+// HONEST LIMIT, stated plainly: this suite verifies the workflow's
+// DETERMINISTIC CONTROL FLOW ONLY. It drives the file against a mock
+// agent/parallel/log/budget sandbox described by HOST_CONTRACT in
+// slice_wave_harness.mjs. That contract is an ASSUMPTION written down by hand;
+// the repo specifies no host-sandbox contract anywhere. The real Workflow-host
+// seam is therefore NOT exercised here and stays unverified. A green run on
+// this file does not promote any claim to "behaviourally verified against the
+// host" — it says the behaviour asserted below holds against the mock
+// sandbox, and nothing wider.
+//
+// Node BUILT-INS ONLY (node:test + node:assert/strict), matching
+// dashboard_assets/index.test.mjs and the repo's zero-dependency posture.
+
+import test from "node:test";
+import assert from "node:assert/strict";
+import {
+  HOST_CONTRACT, countExportConst, countWrapperName, WRAPPER_NAME,
+  rawSource, wrappedSource, makeWave, runWave, sliceFixture, waveArgs,
+} from "./slice_wave_harness.mjs";
+
+test("the export-const rewrite matches exactly once", () => {
+  assert.equal(countExportConst(rawSource()), 1);
+  assert.equal(countExportConst(wrappedSource()), 0);
+});
+
+test("the wrapped source instantiates as an AsyncFunction", () => {
+  const wave = makeWave();
+  assert.equal(typeof wave, "function");
+  assert.equal(wave.constructor.name, "AsyncFunction");
+});
+
+test("the assumed host contract is a named artifact marked unverified", () => {
+  assert.deepEqual(
+    Object.keys(HOST_CONTRACT).sort(),
+    ["agent", "budget", "log", "parallel", "verified"],
+  );
+  assert.equal(HOST_CONTRACT.verified, false);
+});
+
+// The wrapped source only DECLARES the wrapper; makeWave appends a call to it
+// BY NAME. A rename inside slice_wave_contract_base.WRAP_HEAD would otherwise
+// make every behavioural test below assert against undefined. These two tests
+// make that failure land here, in the loader group, with a readable cause.
+test("the wrapper name appears exactly once in the wrapped source", () => {
+  assert.equal(WRAPPER_NAME, "__wrap");
+  assert.equal(countWrapperName(wrappedSource()), 1);
+  assert.equal(countWrapperName(rawSource()), 0);
+});
+
+test("running the loaded wave resolves an object carrying a results array", async () => {
+  const sandbox = { agent: async () => { throw new Error("BOOM"); } };
+  const out = await runWave(waveArgs([sliceFixture("s1")]), sandbox);
+  assert.equal(typeof out, "object");
+  assert.notEqual(out, null);
+  assert.ok(Array.isArray(out.results));
+  assert.equal(out.results.length, 1);
+});
+
+const CRASH_TRIGGER = "internal-error";
+const RECORD_OPTIONS = ["Retry this slice", "Skip this slice", "Stop the run"];
+const ONE_SLICE = () => waveArgs([sliceFixture("s1")]);
+const THROWS = { agent: async () => { throw new Error("BOOM"); } };
+const only = (out) => out.results[0].escalations[0];
+
+test("an agent that throws escalates the slice with the internal-error trigger", async () => {
+  const out = await runWave(ONE_SLICE(), THROWS);
+  assert.equal(out.results.length, 1);
+  assert.equal(out.results[0].status, "ESCALATED");
+  assert.equal(out.results[0].escalations.length, 1);
+  assert.equal(only(out).id, "s1:" + CRASH_TRIGGER);
+  assert.equal(only(out).trigger, CRASH_TRIGGER);
+  assert.equal(only(out).status, "OPEN");
+});
+
+test("the crash record title names the last dispatched stage", async () => {
+  const out = await runWave(ONE_SLICE(), THROWS);
+  assert.equal(only(out).title, "slice crashed after plan");
+});
+
+test("the crash record carries the three controller-named options in order", async () => {
+  const out = await runWave(ONE_SLICE(), THROWS);
+  assert.deepEqual(only(out).options.map((o) => o.label), RECORD_OPTIONS);
+  assert.equal(only(out).options[0].recommended, true);
+  assert.equal(only(out).options[1].recommended, undefined);
+  assert.equal(only(out).options[2].recommended, undefined);
+});
+
+test("the guaranteed context ordering leads with the two variable diagnostics", async () => {
+  const ctx = only(await runWave(ONE_SLICE(), THROWS)).context;
+  assert.ok(ctx.startsWith("Error: BOOM."));
+  const stageAt = ctx.indexOf("Last stage/role dispatched before the failure: plan");
+  const causeAt = ctx.indexOf("Cause unknown");
+  const tasksAt = ctx.indexOf("task(s) had already completed");
+  assert.ok(stageAt > 0);
+  assert.ok(causeAt > stageAt);
+  assert.ok(tasksAt > causeAt);
+});
+
+test("a crash before any dispatch yields the no-stage title", async () => {
+  const budget = { total: 1, remaining: () => { throw new Error("NOBUDGET"); } };
+  const out = await runWave(ONE_SLICE(), { budget });
+  assert.equal(only(out).title, "slice crashed before any agent was dispatched");
+  assert.ok(only(out).context.includes(
+    "none (the crash happened before any agent was dispatched)"));
+});
+
+const GENERIC_OPTION = "Proceed with the recommended default";
+const LOST = { parallel: async () => [null] };
+
+test("a lost slice escalates with the same trigger and its own title", async () => {
+  const out = await runWave(ONE_SLICE(), LOST);
+  assert.equal(out.results[0].status, "ESCALATED");
+  assert.equal(out.results[0].tasks_completed, 0);
+  assert.equal(out.results[0].agents_used, 0);
+  assert.deepEqual(out.results[0].quality, { status: "SKIPPED", detail: "slice never ran" });
+  assert.equal(only(out).id, "s1:" + CRASH_TRIGGER);
+  assert.equal(only(out).trigger, CRASH_TRIGGER);
+  assert.equal(only(out).title, "slice lost");
+  assert.ok(only(out).question.startsWith("Re-run the wave to retry this slice"));
+});
+
+// PINS CURRENT BEHAVIOUR, with an open question standing against it.
+// controller-verified-evidence.md section 2 records that widening the
+// lost-slice record to the same three labels as the crash record "may be the
+// better fix at the same cost" and is a live question standing before the human. A future
+// widening should read as "update this pinned expectation", never as a
+// regression.
+test("the lost-slice record gets ONE substituted generic option", async () => {
+  const rec = only(await runWave(ONE_SLICE(), LOST));
+  assert.equal(rec.options.length, 1);
+  assert.equal(rec.options[0].label, GENERIC_OPTION);
+  assert.equal(rec.options[0].recommended, true);
+  assert.equal(rec.options[0].detail, rec.context);
+});
+
+const FOUR_IDS = ["s1", "s2", "s3", "s4"];
+const FOUR = () => waveArgs(FOUR_IDS.map(sliceFixture));
+// The prompt carries the slice id (planPrompt embeds it), so an agent that
+// throws the prompt's own id back gives each slice a distinguishable failure.
+const THROW_LABELLED = {
+  agent: async (prompt, opts) => { throw new Error("crash-of-" + opts.label); },
+};
+
+test("every slice in a width-4 wave gets its own result, positionally", async () => {
+  const out = await runWave(FOUR(), THROW_LABELLED);
+  assert.equal(out.results.length, 4);
+  assert.deepEqual(out.results.map((r) => r.id), FOUR_IDS);
+  assert.deepEqual(out.results.map((r) => r.status), ["ESCALATED", "ESCALATED", "ESCALATED", "ESCALATED"]);
+  assert.equal(out.wave_index, 0);
+  assert.equal(out.run_id, "20260827-harness");
+});
+
+test("each escalation id and context is attributed to its own slice", async () => {
+  const out = await runWave(FOUR(), THROW_LABELLED);
+  const recs = out.results.map((r) => r.escalations[0]);
+  assert.deepEqual(recs.map((r) => r.id), FOUR_IDS.map((i) => i + ":" + CRASH_TRIGGER));
+  assert.deepEqual(recs.map((r) => r.context.startsWith("Error: crash-of-")), [true, true, true, true]);
+  FOUR_IDS.forEach((id, i) => assert.ok(recs[i].context.includes("crash-of-" + id + ":plan")));
+});
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index dc9a957..73c2fe4 100644
--- a/plugins/spec-loop/scripts/slice_wave_contract_base.py
+++ b/plugins/spec-loop/scripts/slice_wave_contract_base.py
@@ -1,10 +1,14 @@
 """Shared source-contract infrastructure for slice-wave.workflow.js.
 
-The wave workflow is JavaScript and is not run by any lane of this repo's
-suite: it is resolved at runtime from the installed plugin cache. Its
-correctness has therefore rested entirely on review, and this run paid for
+The wave workflow is JavaScript and is resolved at runtime from the installed
+plugin cache. One lane of this repo's suite now executes it: the companion
+module slice_wave_behaviour.test.mjs loads it through wrapped_source() and
+drives its deterministic control flow against a MOCK agent/parallel/log/budget
+sandbox. That lane exercises no real Workflow-host seam, so the host seam stays
+unverified and review remains the only control over it. Before that lane
+existed its correctness rested entirely on review, and this run paid for
 that twice - an unguarded optional-field read aborted a whole wave and was
 mislabelled as a budget escalation (both the read and the mislabelling are now
 pinned here). The three ``test_slice_wave_contract*.py`` modules that import
 this one are the cheapest honest coverage available:
 they parse the file with node (a real parse, not a substring) and pin the
@@ -26,10 +30,20 @@ prefer existed.
 
 These are source-text assertions. They prove a guard is present; they
 cannot prove it behaves. Any change to the workflow that trips one of them
 is either a regression or an intentional contract change that belongs in
 one of the importing modules too.
+Companion lane: slice_wave_behaviour.test.mjs executes the workflow in a mock
+sandbox and pins the runtime record shapes it produces there, including the
+crash record's three option labels and the lost-slice record's one substituted
+label. It carries its own honest-limit header stating that it covers
+deterministic control flow only. The three crash labels therefore live in three
+non-historical places: the workflow itself, the CRASH_OPTION_RETRY /
+CRASH_OPTION_SKIP / CRASH_OPTION_STOP constants below, and RECORD_OPTIONS in
+that module. The substituted lost-slice label lives in two: the workflow's
+esc() default and GENERIC_OPTION in that module. A label change must move every
+one of them.
 
 Every pinned JS snippet is a module-level constant rather than a literal in
 a test body, and continuation lines use a 4-space hanging indent. Both are
 deliberate: quality_gate.py's heuristics are line-based, so a `&&` or an `if`
 inside a string literal scores as real branching (cognitive_complexity) and a
@@ -255,10 +269,16 @@ CHARTS_EVENT = {"scope": "s1", "type": "deferred", "payload": CHARTS_PAYLOAD}
 THREE_DEFERRALS = [{"text": "first", "disposition_hint": "defer"},
                     {"text": "second", "disposition_hint": "defer"},
                     {"text": "third", "disposition_hint": "defer"}]
 
 
+# Two consumers now. The Python side parses this with node via
+# TestTheFileStillParses. The Node side, slice_wave_harness.mjs, appends a call
+# to the wrapper function this body declares and EXECUTES the result, so it
+# depends on the WRAP_HEAD function NAME as well as on the wrapping itself. A
+# rename of that function must move slice_wave_harness.WRAPPER_NAME in the same
+# change; its loader-integrity test is the guard that makes a miss loud.
 def wrapped_source():
     """The workflow source in the async wrapper node can actually parse."""
     body = SOURCE.replace("\nexport const", "\nconst")
     if body.startswith("export const"):
         body = body[len("export "):]
diff --git a/plugins/spec-loop/scripts/slice_wave_harness.mjs b/plugins/spec-loop/scripts/slice_wave_harness.mjs
new file mode 100644
index 0000000..fe7583d
--- /dev/null
+++ b/plugins/spec-loop/scripts/slice_wave_harness.mjs
@@ -0,0 +1,135 @@
+// slice_wave_harness.mjs — loads slice-wave.workflow.js so it can be EXECUTED.
+//
+// The workflow file cannot be imported as an ES module: the Workflow host wraps
+// the whole script in an implicit async function, so the file legally carries a
+// top-level `return` and a top-level `await`. `node --check` refuses it in both
+// module modes. The wrapping transform already exists in Python, as
+// slice_wave_contract_base.wrapped_source(), and this module SHELLS OUT to it
+// rather than re-implementing it, so there is exactly one wrapper in the repo
+// and it cannot drift from the one the source-contract tests parse.
+//
+// The workflow uses no Node or host API of its own (it is pure logic over
+// `args` plus the injected sandbox globals), which is what makes an
+// AsyncFunction with mock globals a faithful driver of its control flow.
+
+import { readFileSync } from "node:fs";
+import { execFileSync } from "node:child_process";
+import { dirname, join } from "node:path";
+import { fileURLToPath } from "node:url";
+
+const HERE = dirname(fileURLToPath(import.meta.url));
+const WORKFLOW = join(HERE, "..", "workflows", "slice-wave.workflow.js");
+const PY = "import sys; sys.path.insert(0, '.'); import slice_wave_contract_base as b; sys.stdout.write(b.wrapped_source())";
+
+// The name of the function that slice_wave_contract_base.WRAP_HEAD declares.
+// wrapped_source() is a PARSE wrapper: its body only DECLARES that function.
+// To EXECUTE the workflow the harness appends a call to it, so this module now
+// depends on that name. A rename in WRAP_HEAD would make the wave resolve
+// undefined in silence, which is what WRAPPER_NAME plus the loader-integrity
+// tests in slice_wave_behaviour.test.mjs exist to surface loudly.
+export const WRAPPER_NAME = "__wrap";
+const INVOKE = "\nreturn " + WRAPPER_NAME + "()\n";
+
+// The ASSUMED host-sandbox contract. Written down as a named object on purpose:
+// the repo specifies this nowhere (checked references/ and commands/), so the
+// assumption is a diffable artifact instead of a caveat in prose that decays.
+// `verified: false` is the honest state of every clause below.
+export const HOST_CONTRACT = {
+  agent: "agent(prompt, opts) resolves to a schema-valid object, or throws.",
+  parallel: "parallel(fns) resolves an array of results, positional per input.",
+  log: "log(message) is side-effect-free from the workflow's point of view.",
+  budget: "budget.remaining() returns a number; budget.total is a number.",
+  verified: false,
+};
+
+// The globals the host injects, in the order the AsyncFunction declares them.
+const SANDBOX_PARAMS = ["args", "agent", "parallel", "log", "budget", "phase", "pipeline"];
+
+export function rawSource() {
+  return readFileSync(WORKFLOW, "utf8");
+}
+
+// Occurrences of a line-initial `export const`. The rewrite must match exactly
+// once; a second top-level export, or zero, means the file's top-level shape
+// changed and the harness would otherwise degrade in silence.
+export function countExportConst(src) {
+  return (src.match(/^export const\b/gm) || []).length;
+}
+
+// Memoized at module scope: one python3 spawn and one read across the
+// whole suite, matching slice_wave_contract_base's module-level SOURCE pattern
+// named in conventions.md.
+let cachedWrapped = null;
+
+export function wrappedSource() {
+  cachedWrapped = cachedWrapped || readWrapped();
+  return cachedWrapped;
+}
+
+function readWrapped() {
+  // execFileSync throws on a non-zero exit, so a broken python side is loud.
+  // The rethrow names BOTH dependencies by name, because the raw execFileSync
+  // error is opaque about which of the two went missing.
+  try {
+    return execFileSync("python3", ["-c", PY], {
+      cwd: HERE, encoding: "utf8", maxBuffer: 32 * 1024 * 1024,
+    });
+  } catch (err) {
+    throw new Error(
+      "slice_wave_harness needs python3 on PATH plus an importable "
+      + "slice_wave_contract_base.wrapped_source() in "
+      + HERE + ". Underlying failure: " + err.message,
+    );
+  }
+}
+
+// wrapped_source() DECLARES the wrapper and stops there. Appending the call is
+// what makes this AsyncFunction body resolve the workflow's return value
+// instead of undefined. The one existing Python transform is reused as-is; no
+// second, divergent wrapper is introduced anywhere.
+export function makeWave() {
+  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
+  return new AsyncFunction(...SANDBOX_PARAMS, wrappedSource() + INVOKE);
+}
+
+// Occurrences of the wrapper name in the wrapped source. Exactly one is the
+// only healthy value: zero means WRAP_HEAD was renamed and INVOKE now names a
+// function that does not exist.
+export function countWrapperName(src) {
+  return (src.match(/\b__wrap\b/g) || []).length;
+}
+
+const defaultSandbox = () => ({
+  agent: async () => ({ status: "PLANNED" }),
+  parallel: async (fns) => Promise.all(fns.map((f) => f())),
+  log: () => {},
+  budget: { total: 0, remaining: () => 1e9 },
+  phase: () => {},
+  pipeline: () => {},
+});
+
+export async function runWave(waveArgsObj, sandbox) {
+  const s = { ...defaultSandbox(), ...sandbox };
+  return makeWave()(waveArgsObj, s.agent, s.parallel, s.log, s.budget, s.phase, s.pipeline);
+}
+
+export function sliceFixture(id) {
+  return {
+    id, goal: "goal of " + id, files: ["a.py"], subsystems: ["x"],
+    deps: [], risk_tier: 1, depth: 0, parent: null,
+    branch: "spec-loop/t/" + id, base_sha: "0000000", worktree: "/tmp/wt/" + id,
+  };
+}
+
+export function waveArgs(slices) {
+  return {
+    run_id: "20260827-harness", wave_index: 0, slices, answers: {},
+    ctx: {
+      run_dir: "/tmp/run", plugin_root: "/tmp/plugin", base_ref: "main",
+      test_command: "true", conventions_path: "/tmp/run/conventions.md",
+      shared_constraints: ["none"], tier3_surfaces: [],
+      quality_gate_cmd: "true", models: { reviewer: "inherit" },
+      thorough: false, polish: false,
+    },
+  };
+}
