// slice_wave_reentry.test.mjs — measurements, re-measure-before-escalation,
// package anchors and (later) the slice.entry re-entry path, EXECUTED.
// HONEST LIMITS: deterministic control flow against the mock sandbox in
// slice_wave_harness.mjs only; the real Workflow-host seam stays unverified.
// Separate module because slice_wave_behaviour.test.mjs sits at the quality
// gate's 300-non-blank-line class_lines ceiling.

import test from "node:test";
import assert from "node:assert/strict";
import {
  runWave, waveArgs, sliceFixture, pipelineWith, fullPipeline, PIPELINE_LABELS,
} from "./slice_wave_harness.mjs";
import {
  VERIFY_SUITE_RED, GATE_REMEASURE, FIX_BLOCKED, FIX_ROUND_TWO,
  RR_NOT_ADDRESSED, RR_ADDRESSED, DEBUG_FIX_DONE,
  reentrySlice, ENTRY_HEAD, ORDER_TEXT, RR_ORDER_ADDRESSED, PLAN_EMPTY, TASK_BLOCKED, TASK_RETRY_DONE,
} from "./slice_wave_reentry_fixtures.mjs";

const T2 = () => [sliceFixture("s1", 2)];
const run = async (sandbox) => (await runWave(waveArgs(T2()), sandbox)).results[0];
const gateEvents = (r) => r.events.filter((e) => e.type === "quality-gate");
const promptOf = (sandbox, label) => sandbox.seen.find((d) => d.label === label).prompt;

// ── Stale measurements (run 20260908: six pre-fix quality blocks) ─────────

test("a failed verification still records the last suite and gate measurement", async () => {
  const sandbox = pipelineWith({ "verify:1": VERIFY_SUITE_RED, "debug-fix": DEBUG_FIX_DONE, "verify:2": VERIFY_SUITE_RED });
  const r = await run(sandbox);
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].trigger, "review-block");
  assert.ok(r.tests, "tests block is recorded on the failing path");
  assert.equal(r.tests.passed, false);
  assert.equal(r.tests.scope, "full");
  assert.equal(r.quality.measured_at, "verify:2");
  assert.equal(r.quality.head_sha, VERIFY_SUITE_RED.head_sha);
});

test("every quality-gate event names the head, tree and stage it measured", async () => {
  const r = await run(fullPipeline());
  const events = gateEvents(r);
  assert.deepEqual(events.map((e) => e.payload.stage), ["gate", "verify:1"]);
  for (const e of events) {
    assert.equal(typeof e.payload.head_sha, "string");
    assert.equal(typeof e.payload.tree_sha, "string");
  }
});

test("a verified DONE slice records where its quality was measured", async () => {
  const r = await run(fullPipeline());
  assert.equal(r.status, "DONE");
  assert.equal(r.quality.measured_at, "verify:1");
  assert.equal(r.quality.status, "PASS");
});

// ── Re-measure before any fix-loop escalation ────────────────────────────

test("an exhausted fix loop re-measures the gate before escalating", async () => {
  const sandbox = pipelineWith({
    "re-review:1": RR_NOT_ADDRESSED, "fix:2": FIX_ROUND_TWO, "re-review:2": RR_NOT_ADDRESSED,
    "gate:remeasure": GATE_REMEASURE,
  });
  const r = await run(sandbox);
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].trigger, "review-block");
  assert.equal(sandbox.seen.at(-1).label, "s1:gate:remeasure");
  assert.equal(r.quality.measured_at, "gate:remeasure");
  assert.equal(r.quality.head_sha, GATE_REMEASURE.head_sha);
  assert.equal(r.review.open.length, 1);
  assert.equal(r.review.open[0].id, "r0-f1");
  assert.equal(gateEvents(r).at(-1).payload.head_sha, GATE_REMEASURE.head_sha);
});

test("a blocked fixer also triggers the re-measure", async () => {
  const sandbox = pipelineWith({ "fix:1": FIX_BLOCKED, "gate:remeasure": GATE_REMEASURE });
  const r = await run(sandbox);
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].title, "fix agent blocked");
  assert.equal(sandbox.seen.at(-1).label, "s1:gate:remeasure");
  assert.equal(r.quality.measured_at, "gate:remeasure");
});

test("a re-measure that throws keeps the review-block record and says it was skipped", async () => {
  const sandbox = pipelineWith({
    "re-review:1": RR_NOT_ADDRESSED, "fix:2": FIX_ROUND_TWO, "re-review:2": RR_NOT_ADDRESSED,
    "gate:remeasure": new Error("cap"),
  });
  const r = await run(sandbox);
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].trigger, "review-block");
  assert.match(r.quality.detail, /re-measure skipped/);
});

// ── Package anchors (the round${fix_rounds + 1} off-by-one) ──────────────

test("the first fix round anchors on the round-1 package that was actually written", async () => {
  const sandbox = fullPipeline();
  await run(sandbox);
  const fix1 = promptOf(sandbox, "s1:fix:1");
  assert.match(fix1, /-round1\.md/);
  assert.doesNotMatch(fix1, /-round2\.md/);
});

test("the second fix round anchors on the round-1 and fix-1 packages", async () => {
  const sandbox = pipelineWith({ "re-review:1": RR_NOT_ADDRESSED, "fix:2": FIX_ROUND_TWO, "re-review:2": RR_ADDRESSED });
  const r = await run(sandbox);
  assert.equal(r.status, "DONE");
  const fix2 = promptOf(sandbox, "s1:fix:2");
  assert.match(fix2, /-round1\.md/);
  assert.match(fix2, /-fix1\.md/);
  assert.doesNotMatch(fix2, /-round3\.md/);
});

test("the eight-dispatch pipeline labels are unchanged", async () => {
  const sandbox = fullPipeline();
  await run(sandbox);
  assert.deepEqual(sandbox.seen.map((d) => d.label), PIPELINE_LABELS);
});

// ── slice.entry: re-dispatch resumes at a stage, against the real head ────
// Run 20260908: a resumed j2 dispatch re-planned from the slice GOAL, found it
// delivered, escalated "already implemented", and dropped the controller's
// three fix orders (1 agent, 0 tasks). The entry names the stage to resume at.

const labels = (sandbox) => sandbox.seen.map((d) => d.label);
const runEntry = async (entry, sandbox, answers) =>
  (await runWave(waveArgs([reentrySlice("s1", 2, entry)], answers), sandbox)).results[0];

test("a fix-mode entry skips plan, critique and tasks and starts at the gate", async () => {
  const sandbox = pipelineWith({ "re-review:1": RR_ORDER_ADDRESSED });
  const r = await runEntry({ stage: "fix", head: ENTRY_HEAD, orders: [ORDER_TEXT] }, sandbox);
  assert.equal(r.status, "DONE");
  assert.deepEqual(labels(sandbox).slice(0, 2), ["s1:gate", "s1:fix:1"]);
  assert.ok(!labels(sandbox).some((l) => /:plan$|:critic:|:task:/.test(l)));
});

test("fix-mode orders reach the fixer as findings", async () => {
  const sandbox = pipelineWith({ "re-review:1": RR_ORDER_ADDRESSED });
  await runEntry({ stage: "fix", head: ENTRY_HEAD, orders: [ORDER_TEXT] }, sandbox);
  const fix = promptOf(sandbox, "s1:fix:1");
  assert.match(fix, /order-0/);
  assert.ok(fix.includes(ORDER_TEXT));
});

test("seeded fix rounds keep labels, package tags and the sidecar counter cumulative", async () => {
  const sandbox = pipelineWith({ "fix:3": FIX_ROUND_TWO, "re-review:3": RR_ORDER_ADDRESSED });
  const r = await runEntry({ stage: "fix", head: ENTRY_HEAD, fix_rounds: 2, orders: [ORDER_TEXT] }, sandbox);
  assert.equal(r.status, "DONE");
  assert.ok(labels(sandbox).includes("s1:fix:3"));
  assert.match(promptOf(sandbox, "s1:re-review:3"), /-fix3\.md/);
  assert.match(promptOf(sandbox, "s1:fix:3"), /-fix2\.md/);
  assert.equal(r.review.fix_rounds, 3);
});

test("a verify-mode entry goes straight to verification", async () => {
  const sandbox = fullPipeline();
  const r = await runEntry({ stage: "verify", head: ENTRY_HEAD }, sandbox);
  assert.deepEqual(labels(sandbox), ["s1:verify:1"]);
  assert.equal(r.status, "DONE");
  assert.equal(r.quality.measured_at, "verify:1");
  assert.equal(r.tests.passed, true);
});

test("a review-mode entry reviews base..entry.head under the next round tag", async () => {
  const sandbox = pipelineWith({ "fix:3": FIX_ROUND_TWO, "re-review:3": RR_ADDRESSED });
  const r = await runEntry({ stage: "review", head: ENTRY_HEAD, fix_rounds: 2 }, sandbox);
  assert.equal(r.status, "DONE");
  const review = promptOf(sandbox, "s1:review:full");
  assert.ok(review.includes("--head " + ENTRY_HEAD));
  assert.match(review, /-round3\.md/);
  assert.ok(labels(sandbox)[0] === "s1:review:full" || labels(sandbox)[0] === "s1:gate");
});

test("an entry with an unknown stage escalates internal-error before any dispatch", async () => {
  const sandbox = fullPipeline();
  const r = await runEntry({ stage: "polish", head: ENTRY_HEAD }, sandbox);
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].trigger, "internal-error");
  assert.equal(r.escalations[0].title, "unusable slice.entry");
  assert.equal(sandbox.seen.length, 0);
});

test("an entry without a head escalates the same way", async () => {
  const sandbox = fullPipeline();
  const r = await runEntry({ stage: "fix" }, sandbox);
  assert.equal(r.escalations[0].title, "unusable slice.entry");
  assert.equal(sandbox.seen.length, 0);
});

test("a plan-mode entry tells the planner what is delivered and accepts zero tasks", async () => {
  const sandbox = pipelineWith({ "plan": PLAN_EMPTY });
  const r = await runEntry({ stage: "plan", head: ENTRY_HEAD }, sandbox);
  assert.equal(r.status, "DONE");
  const plan = promptOf(sandbox, "s1:plan");
  assert.match(plan, /RE-ENTRY/);
  assert.ok(plan.includes(ENTRY_HEAD));
  assert.ok(!labels(sandbox).some((l) => /:critic:/.test(l)), "critique is skipped on an empty re-entry plan");
  assert.ok(labels(sandbox).includes("s1:review:full"));
});

test("re-entry is recorded once with its stage and head", async () => {
  const r = await runEntry({ stage: "verify", head: ENTRY_HEAD }, fullPipeline());
  const events = r.events.filter((e) => e.type === "re-entry");
  assert.equal(events.length, 1);
  assert.equal(events[0].payload.stage, "verify");
  assert.equal(events[0].payload.head, ENTRY_HEAD);
});

test("the residual after a fix-mode re-entry is the carried one, never a replayed review", async () => {
  const sandbox = pipelineWith({ "re-review:1": RR_ORDER_ADDRESSED });
  const r = await runEntry({ stage: "fix", head: ENTRY_HEAD, orders: [ORDER_TEXT], residual: ["P2: old"] }, sandbox);
  assert.deepEqual(r.review.residual, ["P2: old"]);
});

// ── Answer routing: the answer reaches the agent that acts on it ──────────

test("a review-block answer reaches the fixer", async () => {
  const sandbox = fullPipeline();
  await runWave(waveArgs(T2(), { "s1:review-block": "ORDER-X" }), sandbox);
  assert.match(promptOf(sandbox, "s1:fix:1"), /ORDER-X/);
});

test("a review-block answer reaches the debug-fixer on a red suite", async () => {
  const sb = pipelineWith({ "verify:1": VERIFY_SUITE_RED, "debug-fix": DEBUG_FIX_DONE, "verify:2": VERIFY_SUITE_RED });
  await runWave(waveArgs(T2(), { "s1:review-block": "GUIDE-Y" }), sb);
  assert.match(promptOf(sb, "s1:debug-fix"), /GUIDE-Y/);
});

test("a task-blocked ambiguity answer reaches the retry prompt and not the first attempt", async () => {
  const sandbox = pipelineWith({ "task:t1": TASK_BLOCKED, "task:t1:retry": TASK_RETRY_DONE });
  const r = await (await runWave(waveArgs(T2(), { "s1:ambiguity": "USE-THE-SECOND-STORE" }), sandbox)).results[0];
  assert.equal(r.status, "DONE");
  assert.match(promptOf(sandbox, "s1:task:t1:retry"), /USE-THE-SECOND-STORE/);
  assert.doesNotMatch(promptOf(sandbox, "s1:task:t1"), /USE-THE-SECOND-STORE/);
});
