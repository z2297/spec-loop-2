// slice_wave_radius.test.mjs — the plan-time refactor-radius ceiling, EXECUTED.
// HONEST LIMIT: this drives the workflow's deterministic control flow against the
// mock sandbox in slice_wave_harness.mjs; the real Workflow-host seam stays
// unverified, and the numbers under test are DECLARED by the planner, so nothing
// here proves a diff was actually that size. Split out of
// slice_wave_behaviour.test.mjs because that module sits at the quality gate's
// 300-non-blank-line class_lines ceiling.

import test from "node:test";
import assert from "node:assert/strict";
import {
  runWave, sliceFixture, radiusArgs, RADIUS_DEFAULTS,
  planWithRadius, planThenStop } from "./slice_wave_harness.mjs";

const S1 = () => [sliceFixture("s1")];
const BIG = { rewrite_ratio: 0.9, touched_existing_files: 12, rewritten_lines: 900, basis: "counted by hand" };
const SMALL = { rewrite_ratio: 0.1, touched_existing_files: 2, rewritten_lines: 40, basis: "counted by hand" };
const AT_CEILING = { rewrite_ratio: 0.5, touched_existing_files: 8, rewritten_lines: 900, basis: "b" };
const TINY = { rewrite_ratio: 0.9, touched_existing_files: 12, rewritten_lines: 20, basis: "b" };
const ZEROED = { rewrite_ratio: 0, touched_existing_files: 0, rewritten_lines: 0, basis: "b" };

// One run of a slice whose plan declares `radius`, under gate config `limits`.
const evaluate = async (radius, limits, answers) => {
  const out = await runWave(radiusArgs(S1(), limits, answers),
                            planThenStop(planWithRadius(radius)));
  return out.results[0];
};
const radiusEvents = (r) => r.events.filter((e) => e.type === "refactor-radius");
const only = async (radius, limits, answers) => {
  const events = radiusEvents(await evaluate(radius, limits, answers));
  assert.equal(events.length, 1);
  return events[0];
};

test("a within-ceiling plan still emits exactly one evaluation event", async () => {
  const ev = await only(SMALL, RADIUS_DEFAULTS);
  assert.equal(ev.scope, "s1");
  assert.equal(ev.payload.state, "WITHIN");
  assert.deepEqual(ev.payload.exceeded, []);
});

test("the no-fire event carries the numbers AND the thresholds compared", async () => {
  const ev = await only(SMALL, RADIUS_DEFAULTS);
  assert.equal(ev.payload.measured.rewrite_ratio, 0.1);
  assert.equal(ev.payload.measured.touched_existing_files, 2);
  assert.equal(ev.payload.measured.rewritten_lines, 40);
  assert.equal(ev.payload.thresholds.max_rewrite_ratio, 0.5);
  assert.equal(ev.payload.thresholds.max_touched_existing_files, 8);
  assert.equal(ev.payload.thresholds.min_rewritten_lines, 150);
});

test("an unmeasured plan records three nulls and never a zero", async () => {
  const ev = await only(undefined, RADIUS_DEFAULTS);
  assert.equal(ev.payload.state, "NOT_MEASURED");
  assert.deepEqual(ev.payload.measured,
    { rewrite_ratio: null, touched_existing_files: null, rewritten_lines: null });
});

test("declared zeros are recorded as zeros and stay a measurement", async () => {
  const ev = await only(ZEROED, RADIUS_DEFAULTS);
  assert.equal(ev.payload.state, "WITHIN");
  assert.equal(ev.payload.measured.rewrite_ratio, 0);
});

test("an unconfigured ctx records the absence with null thresholds", async () => {
  const ev = await only(BIG, undefined);
  assert.equal(ev.payload.state, "NOT_CONFIGURED");
  assert.equal(ev.payload.thresholds, null);
});

test("a disabled block records the evaluation it declined to make", async () => {
  const ev = await only(BIG, { ...RADIUS_DEFAULTS, enabled: false });
  assert.equal(ev.payload.state, "DISABLED");
  assert.equal(ev.payload.measured.rewrite_ratio, 0.9);
});

test("a plan exactly at both ceilings records WITHIN, not a breach", async () => {
  const ev = await only(AT_CEILING, RADIUS_DEFAULTS);
  assert.equal(ev.payload.state, "WITHIN");
});

test("a breach under the noise floor is recorded and does not halt", async () => {
  const result = await evaluate(TINY, RADIUS_DEFAULTS);
  const ev = radiusEvents(result)[0];
  assert.equal(ev.payload.state, "BELOW_FLOOR");
  assert.deepEqual(ev.payload.exceeded, ["rewrite_ratio", "touched_existing_files"]);
  assert.equal(result.escalations.filter((e) => e.trigger === "refactor-scope").length, 0);
});

test("the payload leads with a human-readable summary for the decisions log", async () => {
  const ev = await only(BIG, RADIUS_DEFAULTS);
  assert.equal(Object.keys(ev.payload)[0], "summary");
  assert.ok(ev.payload.summary.startsWith("refactor radius EXCEEDED"));
});

test("a SPLIT plan is discarded before the gate and emits no evaluation", async () => {
  const split = { status: "SPLIT", split: { children: [] } };
  const out = await runWave(radiusArgs(S1(), RADIUS_DEFAULTS), planThenStop(split));
  assert.equal(out.results[0].status, "SPLIT");
  assert.equal(radiusEvents(out.results[0]).length, 0);
});
