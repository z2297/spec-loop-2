# Review package: 39f7a2829017a87ce351ae17505c8d64cf89c1d3..97fd3c3  (context: -U5)

## Commits
97fd3c3 docs: the cap override discard signal, and the ask the skill now describes
ea21c9f escalation-gate skill: the lost-slice sentence names the three-way ask, pinned to the wave's own text
2d9d183 an unusable agent cap override is announced instead of discarded in silence
15999ea the non-injection pin now reads the prompts of a whole slice run, matching its claim
ed8aae3 harness: a schema-valid mock that carries one slice from plan through verify
a3ee0b1 refactor(harness): the harness owns the mock sandboxes, the test module owns the assertions
597f405 fix(quality-gate): trim slice_wave_behaviour.test.mjs comments to clear class_lines
39a69c5 changelog: agent cap override channel and the three-way lost-slice ask
063e118 document the single-dispatch agent cap override in the controller contract
abdba0c lost-slice record: a three-way ask matching its three options
fd63b5c record an applied agent cap raise as an auditable event (also confirmed by execution: a budget-exhausted answer already reaches no agent prompt)
2380e95 budget-exhausted: a human-authorised agent cap raise the guard actually enforces

## Files changed
 CHANGELOG.md                                       |  40 ++++
 plugins/spec-loop/commands/spec-loop.md            |  25 ++-
 plugins/spec-loop/references/run-state-v2.md       |  20 +-
 .../scripts/slice_wave_behaviour.test.mjs          | 201 +++++++++++++++------
 plugins/spec-loop/scripts/slice_wave_harness.mjs   |  85 ++++++++-
 .../spec-loop/scripts/test_slice_wave_contract.py  |  22 ++-
 .../scripts/test_slice_wave_contract_crash.py      |   8 +-
 plugins/spec-loop/skills/escalation-gate/SKILL.md  |   2 +-
 plugins/spec-loop/workflows/slice-wave.workflow.js |  89 ++++++++-
 9 files changed, 421 insertions(+), 71 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
10,
43
],
[
45,
50
]
],
"plugins/spec-loop/commands/spec-loop.md": [
[
96,
97
],
[
140,
159
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
120,
123
],
[
146,
146
],
[
161,
173
]
],
"plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs": [
[
2,
5
],
[
10,
12
],
[
26,
26
],
[
30,
31
],
[
91,
91
],
[
96,
101
],
[
111,
111
],
[
114,
117
],
[
128,
131
],
[
149,
149
],
[
172,
173
],
[
208,
209
],
[
230,
345
]
],
"plugins/spec-loop/scripts/slice_wave_harness.mjs": [
[
116,
116
],
[
119,
119
],
[
126,
130
],
[
140,
140
],
[
143,
215
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract.py": [
[
3,
4
],
[
27,
27
],
[
310,
327
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_crash.py": [
[
236,
238
],
[
242,
244
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
89,
89
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
17,
19
],
[
39,
44
],
[
466,
467
],
[
472,
503
],
[
990,
1028
],
[
1031,
1032
],
[
1053,
1053
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index e8cab4a..eb1dce6 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -5,11 +5,51 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 
+### Added
+- **A `budget-exhausted` answer that actually raises the cap.** The wave args gain one optional
+  top-level field, `agent_cap_overrides: {"<slice-id>": <integer>}`. `agentCap` in
+  `slice-wave.workflow.js` reads it and the per-slice structural guard enforces the number it
+  returns, so a human who authorises a raise now has a lever instead of prose. The channel is
+  deliberately narrow: it can only RAISE (a value at or below the review tier's own cap in
+  `CAPS` is discarded), it is keyed per slice, it lives in the args object of the single
+  re-dispatch the controller hands it to, and it moves no default. An applied raise emits an
+  `agent-cap-override` event carrying `{tier, default_cap, effective_cap}`, so the exception is
+  auditable in `events.jsonl` rather than inferable from a larger `agents_used`. The record
+  itself now offers three controller-named options and its recommended option names the args
+  field to write. `budget-exhausted` remains NOT a judgment trigger — its answer is injected
+  into no agent prompt, pinned by source text and by execution across
+  all eight prompts one slice builds running plan, critique, task, review, gate, fix, re-review
+  and verify — and the per-stage
+  token floor is untouched, having no args-level lever at all: its resource is the wave budget
+  the host supplies. The controller still translates the human's free-text answer into the
+  integer it writes; nothing in the loop parses that text. An override the channel cannot use
+  is no longer discarded in silence: a value at or below the tier default, a non-integer value,
+  or a key naming no slice of the wave emits a `decision` event naming the discarded value, so
+  a mistyped lever is visible at the dispatch that carried it rather than only at the next cap
+  record. Documented in `commands/spec-loop.md`
+  step 7 and `references/run-state-v2.md`.
+
+### Changed
+- **The lost-slice escalation asks the three-way question its options already offered.** The
+  record widened to `Retry this slice` / `Skip this slice` / `Stop the run` but still asked
+  "Re-run the wave to retry this slice?", so a human answering "no" had chosen none of the
+  three and the stored free text bound to no option. It now asks "Retry this slice, skip it and
+  continue the run, or stop the run to investigate the silent failure?", matching the crash
+  record's shape with its own tail — the lost-slice record has no exception text to diagnose.
+  Pinned by execution in `slice_wave_behaviour.test.mjs` and by source text in
+  `test_slice_wave_contract_crash.py`.
+
 ### Fixed
+- **The escalation-gate skill describes the lost-slice ask the wave actually emits.**
+  `skills/escalation-gate/SKILL.md` still said the lost-slice record "asks only whether to re-run
+  the wave" after that record widened to the three-way retry/skip/stop question. The sentence now
+  names the three-way ask and its own tail, and `test_slice_wave_contract.py` holds the doc
+  against the wave's real question text, so the next change to the ask breaks the doc pin instead
+  of drifting past it.
 - **`escalations.md` renders one section per distinct escalation question.** An
   `escalation-opened` event whose raw `id`, `context` and `question` match a section already on
   the page now rewrites that section in place (`run_state.place_escalation_section`) instead of
   appending a second copy; a record differing in any of those three raw fields is a different
   question and keeps its own section. Matching compares the fingerprint `escalation_identity`
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index d7ddbf8..7ec8520 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -91,11 +91,12 @@ deadlock is itself an escalation):
    ("python3 <plugin_root>/scripts/quality_gate.py --config <global> --overlay <repo
    overlay>" — the same two paths, so agents measure against the merged bar), models,
    thorough, polish}, slices: [{id, goal, files, subsystems, risk_tier, depth, worktree,
    branch, base_sha, kg_snippet}] (per-slice only —
    the scope ceiling is run-level and travels in ctx, never duplicated here),
-   answers: {}}` — then invoke
+   answers: {}, agent_cap_overrides: {} (optional; see step 7 — omit it on a normal
+   dispatch)}` — then invoke
    the Workflow named `spec-loop:slice-wave` (fallback: `scriptPath:
    "${CLAUDE_PLUGIN_ROOT}/workflows/slice-wave.workflow.js"`). Pass `args` as a real
    JSON object in the tool call, never a JSON-encoded string — a stringified object
    reaches the script as one string and the wave dies instantly on `args.slices`. Record the wave:
    `dag.py record-wave --index N --slice-ids <ids> --workflow-run-id <wf_id>`; append a
@@ -134,12 +135,30 @@ deadlock is itself an escalation):
    dispatch's round number solely from the keys already present in `answers`, so every
    re-dispatch this run makes — same session or after a `--resume` — must hand the wave an
    `answers` map carrying EVERY answered escalation of the run, all rounds included, not
    just the newest: dropping an earlier round's key reissues the id that round already
    answered. Retaining the older keys surfaces no stale text to a slice, since the wave
-   still reads only the newest answered round. Then
-   **re-dispatch the wave with ONLY its non-terminal slices** — filter `slices` to the ones
+   still reads only the newest answered round.
+
+   A `budget-exhausted` record is a resource request, not a judgment: the wave injects
+   its answer into no prompt, so writing the answer back changes nothing on its own. The
+   AGENT-CAP variant of that record ("agent cap reached (N)") has a lever — after the
+   human authorises a raise, hand the very next dispatch `agent_cap_overrides:
+   {"<slice-id>": <integer>}` alongside the usual `answers` map. `agentCap` in the wave
+   reads it, the structural guard enforces the raised number, and an `agent-cap-override`
+   event records the authorisation. An override the wave cannot use — at or below the tier
+   default, non-integer, or keyed to a slice this wave never dispatched — raises nothing and
+   says so: it emits a `decision` event naming the discarded value, so a mistyped key surfaces
+   at the dispatch that carried it. Two rules bind you. The override is single-dispatch:
+   it belongs to the one re-dispatch the human authorised, so drop it from every later
+   dispatch of the run rather than carrying it forward like `answers`. And it only ever
+   raises — a value at or below the tier default is discarded by the wave, so it is no
+   route to a tighter bound either. The TOKEN-FLOOR variant ("token budget exhausted")
+   has no such lever: its resource is the wave budget the host supplies, and no args
+   field in this contract changes the stage floor.
+
+   Then **re-dispatch the wave with ONLY its non-terminal slices** — filter `slices` to the ones
    whose sidecars are not DONE/SPLIT (merged work never re-enters a wave; its worktree is
    already gone) — same `ctx`, `answers` filled in, and `resumeFromRunId: <wf_id>` so the
    escalated slices' completed stages replay from the journal where the cache holds. Never
    rely on replay to make a terminal slice free: a cache miss re-runs it live against a
    deleted worktree and the result must be discarded (observed cost: 140 minutes). If a
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 05b7e2b..2a7fcf1 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -115,11 +115,14 @@ prose about the slice.
   "answer": null, "answered_at": null
 }
 ```
 
 `budget-exhausted` is raised only by the loop's two structural guards (agent cap, stage
-token floor); `internal-error` covers the two machine-failure shapes the loop actually
+token floor). It stays a resource request rather than a judgment — no prompt ever receives
+its answer — and only the agent-cap half is answerable mechanically: the controller supplies
+`agent_cap_overrides` on the one re-dispatch the human authorised, and the stage token floor
+has no such field. `internal-error` covers the two machine-failure shapes the loop actually
 produces — an unhandled exception that aborted a slice, and a slice that returned no result
 at all — either of which may itself have a host- or agent-layer cause (e.g. a rejected agent
 call on a hard token or rate limit) that the record does not pretend to rule out. It is not
 a catch-all for every other failure: a failure the loop can name keeps the trigger that
 names it, so a spent replan stays `council-objection` and a blocked task — including a task
@@ -138,11 +141,11 @@ stamps `ts` — workflow scripts have no clock).
 
 Event types (extensible; consumers ignore unknown types): `run-created`,
 `baseline`, `council-verdict`, `decision`, `deferred`, `escalation-opened`,
 `escalation-answered`, `wave-dispatched`, `wave-collected`, `slice-merged`,
 `integration-check`, `split-ingested`, `quality-gate`, `review-summary`,
-`agent-dispatch`, `phase5-gate`, `publish-choice`.
+`agent-dispatch`, `phase5-gate`, `publish-choice`, `agent-cap-override`.
 
 Pinned payload facts (consumers rely on these; everything else is
 best-effort):
 
 - **`ts` is a collection stamp, not a duration source.** The controller
@@ -153,10 +156,23 @@ best-effort):
   future harness exposes per-dispatch identity — all optional and null-honest.
   (Verified 2026-07-30: workflow journal keys are opaque digests, so
   per-dispatch timing/tokens are NOT extractable today.) `engine_active_s`
   derives ONLY from `dispatched_at`/`returned_at` pairs; when absent it is
   `null`, never a `ts`-based guess.
+- **`agent-cap-override`** payload: `{tier, default_cap, effective_cap}` — emitted by
+  the wave at slice start, once per dispatch, only after a human-authorised raise has
+  actually taken effect. `default_cap` is the review tier's own cap and `effective_cap`
+  is the raised number the guard enforces; the pair makes the exception auditable rather
+  than inferable from a larger `agents_used`. The raise arrives as the wave arg
+  `agent_cap_overrides` (`{"<slice-id>": <integer>}`), belongs to the single dispatch the
+  controller hands it to, and can only raise: a value at or below the tier default is
+  discarded. `tier` is the review tier at slice start, which a later tier promotion can
+  move. A supplied override that does NOT take effect emits no `agent-cap-override` event: a
+  value at or below the tier default, or a non-integer value, is announced once at slice
+  start as a `decision` event whose summary opens `agent cap override`, and override keys
+  matching no slice of the dispatched wave are announced the same way on the wave's first
+  slice. The discard is therefore visible without waiting on a second cap record.
 - **`wave-collected`** payload carries the per-wave aggregates the workflow
   completion notification reports: `{index, agent_count, subagent_tokens,
   duration_ms}` — the honest wave-level token/duration channel while
   per-dispatch stamps are unavailable. Optional, null-honest.
 - **`council-verdict`** payload carries `safety: bool` — whether the verdict
diff --git a/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
index 2f07e57..8633e34 100644
--- a/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
@@ -1,26 +1,17 @@
 // slice_wave_behaviour.test.mjs — the first EXECUTING test of the wave workflow.
-//
-// HONEST LIMIT, stated plainly: this suite verifies the workflow's
-// DETERMINISTIC CONTROL FLOW ONLY. It drives the file against a mock
-// agent/parallel/log/budget sandbox described by HOST_CONTRACT in
-// slice_wave_harness.mjs. That contract is an ASSUMPTION written down by hand;
-// the repo specifies no host-sandbox contract anywhere. The real Workflow-host
-// seam is therefore NOT exercised here and stays unverified. A green run on
-// this file does not promote any claim to "behaviourally verified against the
-// host" — it says the behaviour asserted below holds against the mock
-// sandbox, and nothing wider.
-//
-// Node BUILT-INS ONLY (node:test + node:assert/strict), matching
-// dashboard_assets/index.test.mjs and the repo's zero-dependency posture.
+// HONEST LIMIT: verifies only the workflow's DETERMINISTIC CONTROL FLOW, against
+// the mock HOST_CONTRACT sandbox in slice_wave_harness.mjs (an ASSUMPTION the repo
+// does not itself specify) — the real Workflow-host seam stays unverified. Node
+// BUILT-INS ONLY (node:test + node:assert/strict), matching the repo's posture.
 
 import test from "node:test";
 import assert from "node:assert/strict";
 import {
-  HOST_CONTRACT, countExportConst, countWrapperName, WRAPPER_NAME,
-  rawSource, wrappedSource, makeWave, runWave, sliceFixture, waveArgs,
-} from "./slice_wave_harness.mjs";
+  HOST_CONTRACT, countExportConst, countWrapperName, WRAPPER_NAME, rawSource,
+  wrappedSource, makeWave, runWave, sliceFixture, waveArgs,
+  capturePrompts, capAgent, fullPipeline, PIPELINE_LABELS } from "./slice_wave_harness.mjs";
 
 test("the export-const rewrite matches exactly once", () => {
   assert.equal(countExportConst(rawSource()), 1);
   assert.equal(countExportConst(wrappedSource()), 0);
 });
@@ -30,21 +21,16 @@ test("the wrapped source instantiates as an AsyncFunction", () => {
   assert.equal(typeof wave, "function");
   assert.equal(wave.constructor.name, "AsyncFunction");
 });
 
 test("the assumed host contract is a named artifact marked unverified", () => {
-  assert.deepEqual(
-    Object.keys(HOST_CONTRACT).sort(),
-    ["agent", "budget", "log", "parallel", "verified"],
-  );
+  assert.deepEqual(Object.keys(HOST_CONTRACT).sort(), ["agent", "budget", "log", "parallel", "verified"]);
   assert.equal(HOST_CONTRACT.verified, false);
 });
 
-// The wrapped source only DECLARES the wrapper; makeWave appends a call to it
-// BY NAME. A rename inside slice_wave_contract_base.WRAP_HEAD would otherwise
-// make every behavioural test below assert against undefined. These two tests
-// make that failure land here, in the loader group, with a readable cause.
+// The wrapped source only DECLARES the wrapper; makeWave appends a call to it BY
+// NAME, so a rename in slice_wave_contract_base.WRAP_HEAD lands here, readably.
 test("the wrapper name appears exactly once in the wrapped source", () => {
   assert.equal(WRAPPER_NAME, "__wrap");
   assert.equal(countWrapperName(wrappedSource()), 1);
   assert.equal(countWrapperName(rawSource()), 0);
 });
@@ -100,49 +86,51 @@ test("the guaranteed context ordering leads with the two variable diagnostics",
 
 test("a crash before any dispatch yields the no-stage title", async () => {
   const budget = { total: 1, remaining: () => { throw new Error("NOBUDGET"); } };
   const out = await runWave(ONE_SLICE(), { budget });
   assert.equal(only(out).title, "slice crashed before any agent was dispatched");
-  assert.ok(only(out).context.includes(
-    "none (the crash happened before any agent was dispatched)"));
+  assert.ok(only(out).context.includes("none (the crash happened before any agent was dispatched)"));
 });
 
 const LOST = { parallel: async () => [null] };
 
+// Three-way, matching the crash record's shape: the record offers three controller-named options,
+// so a yes/no ask would leave a human answering "no" bound to none of them. The tail differs from
+// the crash record's on purpose — this record carries no exception text to diagnose.
+const LOST_QUESTION =
+  "Retry this slice, skip it and continue the run, or stop the run to investigate the silent failure?";
+
 test("a lost slice escalates with the same trigger and its own title", async () => {
   const out = await runWave(ONE_SLICE(), LOST);
   assert.equal(out.results[0].status, "ESCALATED");
   assert.equal(out.results[0].tasks_completed, 0);
   assert.equal(out.results[0].agents_used, 0);
   assert.deepEqual(out.results[0].quality, { status: "SKIPPED", detail: "slice never ran" });
   assert.equal(only(out).id, "s1:" + CRASH_TRIGGER);
   assert.equal(only(out).trigger, CRASH_TRIGGER);
   assert.equal(only(out).title, "slice lost");
-  assert.ok(only(out).question.startsWith("Re-run the wave to retry this slice"));
+  assert.equal(only(out).question, LOST_QUESTION);
 });
 
-// The lost-slice record used to rely on esc()'s empty-array substitution, which
-// yields ONE option labelled "Proceed with the recommended default" whose detail
-// repeats the whole context. The human ruled that widening this record to the same
-// three controller-named labels as the crash record is the fix. The record's own
-// question stays binary on purpose, so this test pins the OPTION SET by execution
-// and claims nothing about the ask.
+// The lost-slice record used to rely on esc()'s empty-array substitution, which yields ONE option
+// labelled "Proceed with the recommended default" whose detail repeats the whole context. The human
+// ruled that widening this record to the same three controller-named labels as the crash record is
+// the fix. This test pins the OPTION SET by execution; the ask itself is pinned separately, above.
 test("the lost-slice record carries the same three controller-named options", async () => {
   const rec = only(await runWave(ONE_SLICE(), LOST));
   assert.deepEqual(rec.options.map((o) => o.label), RECORD_OPTIONS);
   assert.equal(rec.options[0].recommended, true);
   assert.equal(rec.options[1].recommended, undefined);
   assert.equal(rec.options[2].recommended, undefined);
   rec.options.forEach((o) => assert.notEqual(o.detail, rec.context));
   rec.options.forEach((o) => assert.ok(o.detail.includes("CONTROLLER")));
 });
 
-// The two internal-error records now share the trigger, the id shape and the three
-// option labels. What still separates them is the evidence and the ask: the crash
-// record carries exception text plus a stage attribution and asks which of the three
-// to take; the lost-slice record carries neither and asks the binary re-run question.
-// A future edit that collapses them into one indistinguishable record fails here.
+// The two internal-error records now share the trigger, the id shape and the three option labels. They
+// differ in evidence and in ask: the crash record carries exception text plus a stage attribution and
+// asks which of the three to take; the lost-slice record carries neither and asks the same three-way
+// question with its own tail. An edit collapsing them into one indistinguishable record fails here.
 test("the crash and lost-slice records stay distinguishable after the widening", async () => {
   const crash = only(await runWave(ONE_SLICE(), THROWS));
   const lost = only(await runWave(ONE_SLICE(), LOST));
   assert.equal(crash.trigger, lost.trigger);
   assert.deepEqual(crash.options.map((o) => o.label), RECORD_OPTIONS);
@@ -156,12 +144,11 @@ test("the crash and lost-slice records stay distinguishable after the widening",
   assert.ok(!lost.context.includes("Last stage/role dispatched"));
 });
 
 const FOUR_IDS = ["s1", "s2", "s3", "s4"];
 const FOUR = () => waveArgs(FOUR_IDS.map(sliceFixture));
-// The prompt carries the slice id (planPrompt embeds it), so an agent that
-// throws the prompt's own id back gives each slice a distinguishable failure.
+// The prompt carries the slice id, so an agent throwing it back distinguishes each slice's failure.
 const THROW_LABELLED = {
   agent: async (prompt, opts) => { throw new Error("crash-of-" + opts.label); },
 };
 
 test("every slice in a width-4 wave gets its own result, positionally", async () => {
@@ -180,13 +167,12 @@ test("each escalation id and context is attributed to its own slice", async () =
   assert.deepEqual(recs.map((r) => r.context.startsWith("Error: crash-of-")), [true, true, true, true]);
   FOUR_IDS.forEach((id, i) => assert.ok(recs[i].context.includes("crash-of-" + id + ":plan")));
 });
 
 // ── escalation id rounds (esc/escId) and answer matching (latestAnswer) ──────
-// The round is derived from args.answers, the only channel that survives a
-// re-dispatch, so these tests drive it by handing the wave the answers map a
-// resuming controller would hand it and reading the id the wave actually emits.
+// The round comes from args.answers, so these tests hand the wave an answers map a
+// resuming controller would supply and read the id the wave actually emits.
 
 const CRASH_KEY = "s1:" + CRASH_TRIGGER;
 const withAnswers = (answers) => waveArgs([sliceFixture("s1")], answers);
 
 test("an unanswered slice keeps the bare id, with no round component", async () => {
@@ -217,21 +203,12 @@ test("the same answers map reproduces the same id across dispatches", async () =
 test("an answer to one trigger does not advance another trigger's round", async () => {
   const out = await runWave(withAnswers({ "s1:ambiguity": "do this" }), THROWS);
   assert.equal(only(out).id, CRASH_KEY);
 });
 
-// Answer MATCHING, observed where it is observable: the planner prompt. A
-// round-suffixed id whose answer no longer reaches the prompt is the dead end
-// this slice exists to avoid, so it is pinned by execution, not by inspection.
-const capturePrompts = () => {
-  const seen = [];
-  return {
-    seen,
-    agent: async (prompt) => { seen.push(prompt); throw new Error("BOOM"); },
-  };
-};
-
+// Answer MATCHING, observed where it is observable: the planner prompt. A round-suffixed
+// id whose answer no longer reaches the prompt is pinned here by execution, not inspection.
 test("an answer keyed without a round still reaches the prompt", async () => {
   const cap = capturePrompts();
   await runWave(withAnswers({ "s1:ambiguity": "ANSWER-ONE" }), { agent: cap.agent });
   assert.ok(cap.seen[0].includes("ANSWER-ONE"));
   assert.ok(cap.seen[0].includes('HUMAN ANSWER to your earlier "ambiguity" escalation'));
@@ -248,5 +225,121 @@ test("the newest answered round wins with several rounds answered", async () =>
   const answers = { "s1:ambiguity": "ANSWER-ONE", "s1:ambiguity:2": "ANSWER-TWO" };
   await runWave(withAnswers(answers), { agent: cap.agent });
   assert.ok(cap.seen[0].includes("ANSWER-TWO"));
   assert.ok(!cap.seen[0].includes("ANSWER-ONE"));
 });
+
+// ── the per-slice agent cap and its human-authorised raise (guard/agentCap) ──
+// Driven by EXECUTION, not by inspection: the twelve-task fixture in the harness makes the wave
+// spend one dispatch per task, so the tier-1 default of ten is reached inside stageTasks and a
+// raised cap is reached later, in stageReviewGate. The caps themselves are the workflow's own CAPS
+// values; nothing here restates the rule, it reads the record the guard actually produced.
+
+const capWave = (overrides) => waveArgs([sliceFixture("s1")], {}, overrides);
+
+test("the tier default agent cap stops the slice with a budget-exhausted record", async () => {
+  const out = await runWave(capWave(undefined), capAgent());
+  assert.equal(out.results[0].status, "ESCALATED");
+  assert.equal(only(out).trigger, "budget-exhausted");
+  assert.equal(only(out).id, "s1:budget-exhausted");
+  assert.equal(only(out).title, "agent cap reached (10)");
+  assert.ok(only(out).context.includes("tier 1 default 10, effective cap 10"));
+  assert.equal(out.results[0].agents_used, 10);
+});
+
+test("an authorised override raises the cap the guard enforces", async () => {
+  const out = await runWave(capWave({ agent_cap_overrides: { s1: 14 } }), capAgent());
+  assert.equal(only(out).trigger, "budget-exhausted");
+  assert.equal(only(out).title, "agent cap reached (14)");
+  assert.ok(only(out).context.includes("tier 1 default 10, effective cap 14"));
+  assert.equal(out.results[0].agents_used, 14);
+  assert.equal(out.results[0].tasks_completed, 12);
+});
+
+test("an override at or below the tier default is ignored", async () => {
+  const out = await runWave(capWave({ agent_cap_overrides: { s1: 5 } }), capAgent());
+  assert.equal(only(out).title, "agent cap reached (10)");
+  assert.equal(out.results[0].agents_used, 10);
+});
+
+test("a non-numeric override is ignored rather than trusted", async () => {
+  const out = await runWave(capWave({ agent_cap_overrides: { s1: "lots" } }), capAgent());
+  assert.equal(only(out).title, "agent cap reached (10)");
+});
+
+test("an override keyed to another slice does not raise this slice's cap", async () => {
+  const out = await runWave(capWave({ agent_cap_overrides: { s2: 30 } }), capAgent());
+  assert.equal(only(out).title, "agent cap reached (10)");
+  assert.equal(out.results[0].agents_used, 10);
+});
+
+test("the cap record's options name the controller action that applies a raise", async () => {
+  const rec = only(await runWave(capWave(undefined), capAgent()));
+  assert.deepEqual(rec.options.map((o) => o.label), [
+    "Raise the agent cap and resume", "Accept the slice as-is", "Drop the slice",
+  ]);
+  assert.equal(rec.options[0].recommended, true);
+  assert.ok(rec.options[0].detail.includes("agent_cap_overrides"));
+  rec.options.forEach((o) => assert.ok(o.detail.includes("CONTROLLER")));
+  assert.equal(rec.question, "Raise the cap and resume, accept the slice as-is, or drop it?");
+});
+
+const capEvents = (out) => out.results[0].events.filter((e) => e.type === "agent-cap-override");
+
+// A supplied override the channel cannot use leaves the tier default in force. Announcing it at
+// slice start is the point: silence hides the discard until the slice hits the cap a second time.
+// It stays out of the agent-cap-override event, whose payload means a raise that took effect.
+const discards = (out) => out.results[0].events.filter(
+  (e) => e.type === "decision" && String(e.payload.summary).startsWith("agent cap override"));
+
+test("an applied raise is recorded as one auditable event, announcing no discard", async () => {
+  const out = await runWave(capWave({ agent_cap_overrides: { s1: 14 } }), capAgent());
+  assert.equal(capEvents(out).length, 1);
+  assert.equal(capEvents(out)[0].scope, "s1");
+  assert.deepEqual(capEvents(out)[0].payload, { tier: 1, default_cap: 10, effective_cap: 14 });
+  assert.equal(discards(out).length, 0);
+});
+
+test("no override means no override event and no discard either", async () => {
+  const out = await runWave(capWave(undefined), capAgent());
+  assert.equal(capEvents(out).length, 0);
+  assert.equal(discards(out).length, 0);
+});
+
+test("an override below the tier default records no raise and is announced once", async () => {
+  const out = await runWave(capWave({ agent_cap_overrides: { s1: 5 } }), capAgent());
+  assert.equal(capEvents(out).length, 0);
+  assert.equal(discards(out).length, 1);
+});
+
+test("a fractional override leaves the tier default in force and is announced once", async () => {
+  const out = await runWave(capWave({ agent_cap_overrides: { s1: 10.5 } }), capAgent());
+  assert.equal(only(out).title, "agent cap reached (10)");
+  assert.equal(out.results[0].agents_used, 10);
+  assert.equal(discards(out).length, 1);
+  assert.equal(discards(out)[0].scope, "s1");
+  assert.ok(discards(out)[0].payload.summary.includes("10.5"));
+  assert.equal(capEvents(out).length, 0);
+});
+
+test("an override keyed to no slice of the wave is announced too", async () => {
+  const out = await runWave(capWave({ agent_cap_overrides: { s2: 30 } }), capAgent());
+  assert.equal(discards(out).length, 1);
+  assert.ok(discards(out)[0].payload.summary.includes("s2"));
+});
+
+// budget-exhausted requests a resource, so its answer is deliberately injected into no agent
+// prompt. The source-text twin of this lives in test_slice_wave_contract.py; this one drives a
+// real answer through a slice that runs plan through verify and reads all eight prompts that run
+// built. The label set is asserted too, so the pin cannot narrow in silence, and the ambiguity
+// answer alongside it proves injection was live at the same time.
+test("a budget-exhausted answer reaches no prompt of a whole slice run", async () => {
+  const cap = fullPipeline();
+  const answers = { "s1:budget-exhausted": "RAISE-IT-TO-40", "s1:ambiguity": "ANSWER-CTL" };
+  const out = await runWave(waveArgs([sliceFixture("s1", 2)], answers), { agent: cap.agent });
+  const prompts = cap.seen.map((s) => s.prompt);
+  assert.equal(out.results[0].status, "DONE");
+  assert.deepEqual(cap.seen.map((s) => s.label).sort(), [...PIPELINE_LABELS].sort());
+  assert.ok(prompts.some((p) => p.includes("ANSWER-CTL")));
+  prompts.forEach((p) => assert.ok(!p.includes("RAISE-IT-TO-40")));
+  prompts.forEach((p) => assert.ok(!p.includes("budget-exhausted")));
+});
diff --git a/plugins/spec-loop/scripts/slice_wave_harness.mjs b/plugins/spec-loop/scripts/slice_wave_harness.mjs
index 3d58272..65f22bb 100644
--- a/plugins/spec-loop/scripts/slice_wave_harness.mjs
+++ b/plugins/spec-loop/scripts/slice_wave_harness.mjs
@@ -111,28 +111,105 @@ const defaultSandbox = () => ({
 export async function runWave(waveArgsObj, sandbox) {
   const s = { ...defaultSandbox(), ...sandbox };
   return makeWave()(waveArgsObj, s.agent, s.parallel, s.log, s.budget, s.phase, s.pipeline);
 }
 
-export function sliceFixture(id) {
+export function sliceFixture(id, riskTier) {
   return {
     id, goal: "goal of " + id, files: ["a.py"], subsystems: ["x"],
-    deps: [], risk_tier: 1, depth: 0, parent: null,
+    deps: [], risk_tier: riskTier || 1, depth: 0, parent: null,
     branch: "spec-loop/t/" + id, base_sha: "0000000", worktree: "/tmp/wt/" + id,
   };
 }
 
 // `answers` is the controller's resume channel, keyed by escalation id. It is a
 // parameter so a test can drive the round the workflow computes from it, rather
-// than asserting the id scheme against a copy of the rule.
-export function waveArgs(slices, answers) {
+// than asserting the id scheme against a copy of the rule. `extra` carries any
+// additional TOP-LEVEL wave arg a test needs to drive, such as the per-slice
+// agent cap override map, so the harness never hand-builds a second args shape
+// that could drift from this one.
+export function waveArgs(slices, answers, extra) {
   return {
     run_id: "20260827-harness", wave_index: 0, slices, answers: answers || {},
     ctx: {
       run_dir: "/tmp/run", plugin_root: "/tmp/plugin", base_ref: "main",
       test_command: "true", conventions_path: "/tmp/run/conventions.md",
       shared_constraints: ["none"], tier3_surfaces: [],
       quality_gate_cmd: "true", models: { reviewer: "inherit" },
       thorough: false, polish: false,
     },
+    ...(extra || {}),
   };
 }
+
+// ── Mock sandboxes and mock agent returns ────────────────────────────────
+// Fixture DATA lives here, beside defaultSandbox, so the test module carries
+// assertions and their rationale instead. Nothing below restates a workflow
+// rule: every value is a schema-shaped agent return the wave reads.
+
+export const capturePrompts = () => {
+  const seen = [];
+  return { seen, agent: async (prompt) => { seen.push(prompt); throw new Error("BOOM"); } };
+};
+
+const TASK_IDS = ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "t10", "t11", "t12"];
+const PLAN_TWELVE = {
+  status: "PLANNED", plan_path: "/tmp/plan.md",
+  tasks: TASK_IDS.map((id) => ({ id, title: "task " + id, lane: "standard", files: ["a.py"] })),
+};
+const TASK_DONE = {
+  status: "DONE", touched_files: [], concerns: [], deviations: [],
+  commits: { base: "0000000", head: "c0ffee0" },
+};
+
+// Twelve standard tasks: one dispatch per task, so a tier-1 slice reaches its
+// tier default inside stageTasks and a raised cap later, in stageReviewGate.
+export const capAgent = () => ({
+  agent: async (prompt, opts) => (String(opts.label).indexOf(":task:") > 0 ? TASK_DONE : PLAN_TWELVE),
+});
+
+// A one-task plan whose review returns a single P0 finding. Driving a tier-2
+// slice with it runs plan, critique, task, review, gate, fix, re-review and
+// verify - the eight dispatches PIPELINE_LABELS names - and ends the slice DONE.
+const ONE_TASK_PLAN = {
+  status: "PLANNED", plan_path: "/tmp/plan.md",
+  tasks: [{ id: "t1", title: "task t1", lane: "standard", files: ["a.py"] }],
+};
+const P0_FINDING = {
+  id: "f1", severity: "P0", category: "correctness", file: "a.py", line: 1,
+  claim: "a claim", evidence: { quote: "q" }, remedy: "change it",
+  confidence: "high", outside_diff: false,
+};
+const VERIFY_PASS = {
+  suite: { command: "true", passed: true, summary: "ok" },
+  quality: { summary_pass: true, violations: [], detail: "clean" },
+  head_sha: "c0ffee0", tree_sha: "tree000",
+};
+const PIPELINE = {
+  "plan": ONE_TASK_PLAN,
+  "critic:full-council": { verdict: "ENDORSE", safety: { flag: false, reason: null }, concerns: [] },
+  "task:t1": TASK_DONE,
+  "review:full": { verdict: "APPROVE_WITH_FINDINGS", findings: [P0_FINDING], aspects_examined: {}, summary: "one finding" },
+  "gate": VERIFY_PASS,
+  "fix:1": { status: "DONE", touched_files: ["a.py"], addressed: ["r0-f1"], refuted: [], commits: { base: "0000000", head: "f1x0000" } },
+  "re-review:1": { verdicts: [{ finding_id: "r0-f1", verdict: "ADDRESSED" }], new_breakage: [] },
+  "verify:1": VERIFY_PASS,
+};
+
+export const PIPELINE_LABELS = Object.keys(PIPELINE).map((role) => "s1:" + role);
+
+// Records the label and the prompt of every dispatch and answers each one with
+// the return above. An unmapped role throws under its own name: a new stage
+// must be mapped here rather than degrading a run into a fail-closed path in
+// silence, which would quietly narrow whatever a test built on this asserts.
+export const fullPipeline = () => {
+  const seen = [];
+  const agent = async (prompt, opts) => {
+    const label = String(opts.label);
+    const role = label.slice(label.indexOf(":") + 1);
+    const mapped = PIPELINE[role];
+    if (mapped === undefined) throw new Error("slice_wave_harness: no mock return mapped to role " + role);
+    seen.push({ label, prompt });
+    return mapped;
+  };
+  return { seen, agent };
+};
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract.py b/plugins/spec-loop/scripts/test_slice_wave_contract.py
index 17d9539..27aed54 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract.py
@@ -1,8 +1,9 @@
 #!/usr/bin/env python3
 """Contract checks: guarded task-result reads, quality-gate-block answer
-injection, and the record-only `over_scope` critique field.
+injection, the record-only `over_scope` critique field, and the
+escalation-gate skill's account of the lost-slice ask.
 
 See `slice_wave_contract_base.py` for the module-wide rationale (why this
 is source-text assertion, why snippets are named constants, and the two
 known-and-deliberately-unguarded instances this module does NOT claim to
 cover). Two siblings carry the rest of the same contract:
@@ -21,10 +22,11 @@ import os
 import re
 import shutil
 import subprocess
 import tempfile
 import unittest
+from pathlib import Path
 
 from slice_wave_contract_base import (
     ANSWER_CONTEXT_END, ANSWER_CONTEXT_START, ANSWERABLE_TRIGGERS, CLEAN,
     COMMAND_MD, COUNCIL_VERDICT_EVENT, CRITIQUE_REQUIRED, CRITIQUE_ROLLUP,
     FAIL_CLOSED_DEFAULT, FINDING_CATEGORIES, FLAGGED, GATE_ANSWER,
@@ -303,7 +305,25 @@ class TestTheAnswersMapStaysCumulativeAcrossAResume(WorkflowSourceTestCase):
         # describe: the derivation they exist to protect is the real one.
         source = wrapped_source()
         self.assertIn("return answerKeysFor(sliceId, trigger).length + 1", source)
 
 
+SKILL_MD = (Path(__file__).resolve().parents[1]
+            / "skills" / "escalation-gate" / "SKILL.md")
+LOST_ASK_TAIL = "or stop the run to investigate the silent failure"
+LOST_ASK_STALE = "asks only whether to re-run the wave"
+
+
+class TestTheSkillDescribesTheLostSliceAsk(WorkflowSourceTestCase):
+    """The skill doc is a live plugin surface, and this sentence already
+    carried a prior run's accuracy complaint. The wave widened the ask to
+    three ways; nothing held the doc to it, so the drift was silent."""
+
+    def test_the_skill_names_the_ask_the_wave_actually_emits(self):
+        prose = re.sub(r"\s+", " ", SKILL_MD.read_text(encoding="utf-8"))
+        self.assertIn(LOST_ASK_TAIL, self.src)
+        self.assertIn(LOST_ASK_TAIL, prose)
+        self.assertNotIn(LOST_ASK_STALE, prose)
+
+
 if __name__ == "__main__":  # pragma: no cover
     unittest.main()
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
index 11aa888..cb8dd55 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
@@ -231,15 +231,19 @@ class TestCrashesAreClassifiedAsInternalError(WorkflowSourceTestCase):
 
     def test_a_lost_slice_is_an_internal_error_too(self):
         # parallel() resolved the thunk to null: the slice died with no result
         # at all, outside runSlice's try/catch. Same one classification, per
         # the run's human-decided single-value constraint; the honest 'slice
-        # lost' title and its own question are kept.
+        # lost' title and its own question are kept. The record's ask is
+        # three-way, matching the three controller-named options it already
+        # carries, so a human answer binds to one of them.
         wave_entry = self.between(
             "const results = await parallel(", "log(`wave ")
         self.assertIn(SLICE_LOST_RECORD, wave_entry)
-        self.assertIn("Re-run the wave to retry this slice?", wave_entry)
+        self.assertIn(
+            "Retry this slice, skip it and continue the run, or stop the run "
+            "to investigate the silent failure?", wave_entry)
         self.assertNotIn("'budget-exhausted'", wave_entry)
 
     def test_the_lost_slice_record_denies_no_cause_it_cannot_prove(self):
         # Same rule as the crash record, third instance of the pattern: a
         # thunk that resolved to null says nothing about WHY, so asserting
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index 5dc505d..410f703 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -84,11 +84,11 @@ so only a human or the controller resolves it. Both records now offer the same t
 controller-named options, retry the slice, skip it, or stop the run, each detail naming the
 CONTROLLER as what applies it — matched to the `options` argument the wave-entry fallback
 passes to `esc`, alongside the one `runSliceError` already passed. What still separates the two
 is the evidence and the ask: the exception record carries the exception text and the last
 stage/role dispatched and asks which of the three to take, while the lost-slice record carries
-neither and asks only whether to re-run the wave),
+neither and asks the same three-way question with its own tail, ending "or stop the run to investigate the silent failure"),
 and the council's **over-scope flag** (`critique.over_scope.flag`). The flag is a record: it is
 carried into the `council-verdict` payload and the slice sidecar with its reason, and it raises no
 escalation, changes no verdict, suppresses no split, and blocks nothing. There are exactly five
 JUDGMENT triggers; an over-scope flag is not a sixth.
 
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index c385107..bca6bc5 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -12,11 +12,13 @@ export const meta = {
 // deterministic code here. Everything an agent needs arrives as an absolute
 // file path; every LLM→LLM handoff is a schema-forced structured return.
 //
 // Hard rules this file owns (single home):
 //   - loop bounds: replan ≤1, task retry ≤1, fix rounds ≤2, debug-fix ≤1
-//   - per-slice agent caps by review tier: 10 / 18 / 32
+//   - per-slice agent caps by review tier: 10 / 18 / 32, raisable in one
+//     dispatch through args.agent_cap_overrides (agentCap); the raise never
+//     lowers a cap and never changes a default
 //   - fail-closed synthesis: an unusable agent return is never an approval
 //   - answers injection: args.answers["<sliceId>:<trigger>"], or
 //     ["<sliceId>:<trigger>:<round>"] from the second round on, resumes an
 //     escalated stage (escId writes the id, latestAnswer reads it back);
 //     unchanged stages replay from the journal cache
@@ -32,10 +34,16 @@ const CTX = A.ctx // {run_dir, plugin_root, base_ref, test_command, conventions_
 
 const CAPS = { 1: 10, 2: 18, 3: 32 }
 const MAX_FIX_ROUNDS = 2
 const BUDGET_STAGE_FLOOR = 60_000 // skip-and-escalate below this remaining budget
 
+// Per-slice agent-cap raises authorised by the human, keyed by slice id. This map
+// arrives in the wave args of ONE dispatch and expires with it: the controller
+// writes it after a human answers a budget-exhausted cap record, and no default in
+// CAPS moves. See agentCap below.
+const CAP_OVERRIDES = A.agent_cap_overrides || {}
+
 // ── Schemas ──────────────────────────────────────────────────────────────────
 
 const ESCALATION = {
   type: 'object', additionalProperties: false,
   properties: {
@@ -453,16 +461,48 @@ Polish the diff ${state.commits.base}..HEAD in the worktree: behavior-preserving
 }
 
 // ── Guarded dispatch ─────────────────────────────────────────────────────────
 
 function guard(slice, state) {
-  if (state.agentsUsed >= CAPS[state.review_tier])
-    throw { escRecord: esc(slice, 'budget-exhausted', { title: `agent cap reached (${CAPS[state.review_tier]})`, context: `Slice used ${state.agentsUsed} agents (tier ${state.review_tier} cap).`, question: 'Raise the cap and resume, accept the slice as-is, or drop it?', options: [] }) }
+  const cap = agentCap(slice, state)
+  if (state.agentsUsed >= cap) throw { escRecord: agentCapEscalation(slice, state, cap) }
   if (budget.total && budget.remaining() < BUDGET_STAGE_FLOOR)
     throw { escRecord: esc(slice, 'budget-exhausted', { title: 'token budget exhausted', context: `Wave budget remaining ${Math.round(budget.remaining() / 1000)}k is below the ${BUDGET_STAGE_FLOOR / 1000}k stage floor.`, question: 'Raise the budget and resume, accept committed work as-is, or drop the slice?', options: [] }) }
 }
 
+// The effective cap of ONE dispatch of one slice. The override channel can only
+// RAISE: a supplied value at or below the tier default is discarded, so the args
+// map is unable to tighten a bound the loop owns, and a missing, non-numeric or
+// fractional value leaves the tier default in force. Declared here, between guard()
+// and dispatch(), so both budget-exhausted records stay inside the source span the
+// guard-wording contract test reads. (PURE over CAP_OVERRIDES)
+function agentCap(slice, state) {
+  const base = CAPS[state.review_tier]
+  const raised = Number(CAP_OVERRIDES[slice.id])
+  if (Number.isInteger(raised) && raised > base) return raised
+  return base
+}
+
+// The agent-cap record. Its options name the CONTROLLER as what applies each one,
+// because the loop applies none of them: budget-exhausted requests a resource, so
+// the answer text is never injected into an agent prompt. The recommended option
+// names the exact args field the controller writes, which is the whole path from a
+// human saying yes to a cap that actually moves.
+function agentCapEscalation(slice, state, cap) {
+  const base = CAPS[state.review_tier]
+  return esc(slice, 'budget-exhausted', {
+    title: `agent cap reached (${cap})`,
+    context: `Slice used ${state.agentsUsed} agents (tier ${state.review_tier} default ${base}, effective cap ${cap}).`,
+    question: 'Raise the cap and resume, accept the slice as-is, or drop it?',
+    options: [
+      { label: 'Raise the agent cap and resume', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: put the authorised integer under args.agent_cap_overrides, keyed by this slice id, then re-dispatch the wave. The raise lives in that one args object and moves no default in CAPS.', recommended: true },
+      { label: 'Accept the slice as-is', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and take no further work from it. The loop enforces no acceptance by itself.' },
+      { label: 'Drop the slice', detail: 'The CONTROLLER must act on this at the next dispatch: exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.' },
+    ],
+  })
+}
+
 async function dispatch(slice, state, role, prompt, opts) {
   guard(slice, state)
   // Last dispatch STARTED, not a per-throw stage: never cleared, and
   // concurrent fan-outs overwrite each other. After guard() so a cap or
   // token-floor rejection cannot advance it to a role that never ran.
@@ -945,12 +985,53 @@ function runSliceError(slice, state, e) {
     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.' },
   ]
   return escalated(slice, state, esc(slice, 'internal-error', { title, context, question, options }))
 }
 
+// An authorised cap raise is a single-dispatch exception to a bound the loop owns,
+// so it belongs in the machine channel rather than being inferable only from a
+// larger agents_used. Emitted once per slice dispatch, at slice start, and only
+// once the raise has actually taken effect. The payload names the tier as it stands
+// at slice start; maybePromoteTier can raise the tier later, and agentCap recomputes
+// the effective cap at every dispatch, so the event is a record of the authorisation
+// rather than a prediction of the final bound. A supplied override that took no
+// effect is announced by recordDiscardedOverride instead.
+
+// A supplied override the channel cannot use leaves the tier default in force.
+// Announcing that once, at slice start, is the point: silence hides the discard
+// until the slice reaches the cap a second time. It stays OUT of the
+// agent-cap-override event, whose payload means a raise that took effect.
+function recordDiscardedOverride(slice, state, base) {
+  const supplied = JSON.stringify(CAP_OVERRIDES[slice.id])
+  state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `agent cap override ${supplied} discarded: the channel takes an integer above the tier ${state.review_tier} default ${base}`, rationale: 'the override raises only, on an integer value; the tier default stays in force', reversibility: 'n/a' } })
+}
+
+// A key naming no slice of this wave raises nothing and belongs to no slice's
+// own record, so it is announced once, on the wave's first slice, rather than
+// dying silent.
+function recordUnmatchedOverrides(slice, state) {
+  const ids = A.slices.map(s => s.id)
+  const unmatched = Object.keys(CAP_OVERRIDES).filter(k => !ids.includes(k))
+  if (!unmatched.length || slice.id !== ids[0]) return
+  state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `agent cap override keys naming no slice of this wave, raising nothing: ${unmatched.join(', ')}`, rationale: 'the override map is keyed by slice id; a key matching none of the dispatched slices reaches no guard', reversibility: 'n/a' } })
+}
+
+function recordCapOverride(slice, state) {
+  const base = CAPS[state.review_tier]
+  const cap = agentCap(slice, state)
+  const supplied = Object.prototype.hasOwnProperty.call(CAP_OVERRIDES, slice.id)
+  if (cap === base) {
+    if (supplied) recordDiscardedOverride(slice, state, base)
+    return
+  }
+  state.events.push({ scope: slice.id, type: 'agent-cap-override', payload: { tier: state.review_tier, default_cap: base, effective_cap: cap } })
+}
+
 async function runSlice(slice) {
   const state = initSliceState(slice)
+  recordCapOverride(slice, state)
+  recordUnmatchedOverrides(slice, state)
   try {
     return await runStages(slice, state)
   } catch (e) {
     return runSliceError(slice, state, e)
   }
@@ -967,11 +1048,11 @@ const out = results.map((r, i) => r || {
   tasks_completed: 0, review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
   tests: null, quality: { status: 'SKIPPED', detail: 'slice never ran' },
   escalations: [esc(A.slices[i], 'internal-error', {
     title: 'slice lost',
     context: 'The slice function returned no result (terminal failure) — it died outside runSlice\'s try/catch. Neither structural guard raised its escalation record — each raises budget-exhausted with an escRecord runSlice would have returned — and that is all a null result proves, not that no guard check ran. A host- or agent-layer resource failure dies the same silent way, so the cause is unknown here.',
-    question: 'Re-run the wave to retry this slice?',
+    question: 'Retry this slice, skip it and continue the run, or stop the run to investigate the silent failure?',
     options: [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice. No result came back, so this record carries no exception text to diagnose and no record of committed work — inspect the slice branch before the retry, which starts from its base.', recommended: true },
      { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
      { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so a silent host- or agent-layer failure can be investigated before more agents are spent. Nothing in the loop stops the run by itself.' }],
   })],
   agents_used: 0, wave: A.wave_index, events: [],
