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
  // Two real children, not an empty array: a childless SPLIT is now itself an
  // escalation (usableSplit), which would end this slice before the question
  // under test - whether the radius gate runs on a SPLIT - could be asked.
  const child = { goal: "half", files: ["a.py"], subsystems: ["x"], internal_deps: [] };
  const split = { status: "SPLIT", split: { children: [child, child] } };
  const out = await runWave(radiusArgs(S1(), RADIUS_DEFAULTS), planThenStop(split));
  assert.equal(out.results[0].status, "SPLIT");
  assert.equal(radiusEvents(out.results[0]).length, 0);
});

// ── the halt itself ───────────────────────────────────────────────────────
const OPTION_LABELS = [
  "Narrow the plan to the smallest change that meets the goal",
  "Approve the rewrite as planned",
  "Carve the rewrite out into its own slice",
];
const record = (r) => r.escalations.find((e) => e.trigger === "refactor-scope");

test("a measured breach halts the slice at plan time with the new trigger", async () => {
  const result = await evaluate(BIG, RADIUS_DEFAULTS);
  assert.equal(result.status, "ESCALATED");
  assert.equal(result.tasks_completed, 0);
  assert.equal(record(result).id, "s1:refactor-scope");
  assert.equal(record(result).status, "OPEN");
  assert.equal(radiusEvents(result)[0].payload.state, "EXCEEDED");
});

test("the halt happens before any implementation dispatch is spent", async () => {
  // planThenStop throws on every non-plan dispatch: reaching the critique
  // stage would surface as an internal-error record instead of this one.
  const result = await evaluate(BIG, RADIUS_DEFAULTS);
  assert.equal(result.escalations.length, 1);
  assert.equal(result.agents_used, 1);
});

test("the record offers the three trade-offs, narrowing recommended", async () => {
  const rec = record(await evaluate(BIG, RADIUS_DEFAULTS));
  assert.deepEqual(rec.options.map((o) => o.label), OPTION_LABELS);
  assert.equal(rec.options[0].recommended, true);
  assert.equal(rec.options[1].recommended, undefined);
  assert.equal(rec.options[2].recommended, undefined);
  rec.options.forEach((o) => assert.ok(o.detail.includes("CONTROLLER")));
});

test("the context states the numbers, the ceilings and the proxy limit", async () => {
  const rec = record(await evaluate(BIG, RADIUS_DEFAULTS));
  assert.ok(rec.context.includes("0.9"));
  assert.ok(rec.context.includes("0.5"));
  assert.ok(rec.context.includes("12"));
  assert.ok(rec.context.includes("not a measured diff"));
  assert.ok(rec.title.includes("rewrite_ratio"));
});

test("an answered slice proceeds instead of re-raising the same question", async () => {
  const answers = { "s1:refactor-scope": "approved, go ahead" };
  const result = await evaluate(BIG, RADIUS_DEFAULTS, answers);
  assert.equal(record(result), undefined);
  assert.equal(radiusEvents(result)[0].payload.state, "EXCEEDED");
  assert.equal(radiusEvents(result)[0].payload.suppressed_by_answer, true);
});

test("a no-fire evaluation is never marked as suppressed by an answer", async () => {
  const ev = await only(SMALL, RADIUS_DEFAULTS);
  assert.equal(ev.payload.suppressed_by_answer, undefined);
});

test("the human answer reaches the planner prompt that raised the question", async () => {
  const seen = [];
  const agent = async (prompt) => { seen.push(prompt); throw new Error("STOP"); };
  await runWave(radiusArgs(S1(), RADIUS_DEFAULTS,
    { "s1:refactor-scope": "NARROW-IT-DOWN" }), { agent });
  assert.ok(seen[0].includes("NARROW-IT-DOWN"));
  assert.ok(seen[0].includes('HUMAN ANSWER to your earlier "refactor-scope" escalation'));
});
