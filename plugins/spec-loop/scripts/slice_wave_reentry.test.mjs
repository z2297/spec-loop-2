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
