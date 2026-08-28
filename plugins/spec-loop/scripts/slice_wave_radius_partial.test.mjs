// slice_wave_radius_partial.test.mjs — a PARTIALLY usable radius ceiling, EXECUTED.
// One valid ceiling beside one mistyped one is a usable configuration, so it gets
// past radiusNoCeiling; the declared number on the null side was then reported as
// being under a ceiling nothing had compared it to. HONEST LIMIT: this drives the
// workflow's deterministic control flow against the mock sandbox in
// slice_wave_harness.mjs — the real Workflow-host seam stays unverified, and the
// numbers are planner-DECLARED, so nothing here proves a diff was that size.
// A fourth module rather than more cases in slice_wave_radius.test.mjs, which sits
// at 293 non-blank lines against the quality gate's 300-line class_lines ceiling.

import test from "node:test";
import assert from "node:assert/strict";
import {
  runWave, sliceFixture, radiusArgs, RADIUS_DEFAULTS,
  planWithRadius, planThenStop } from "./slice_wave_harness.mjs";

const S1 = () => [sliceFixture("s1")];
// A ratio ceiling that did not survive refactorLimits: null in one config,
// a mistyped string in the other. Both must behave identically.
const NO_RATIO_CEILING = { ...RADIUS_DEFAULTS, max_rewrite_ratio: null };
const STRING_RATIO_CEILING = { ...RADIUS_DEFAULTS, max_rewrite_ratio: "0.5" };
// The motivating shape: a heavy declared ratio beside a small file count.
const HEAVY_RATIO = { rewrite_ratio: 0.9, touched_existing_files: 2, rewritten_lines: 900, basis: "b" };
const SMALL = { rewrite_ratio: 0.1, touched_existing_files: 2, rewritten_lines: 40, basis: "b" };
const BIG = { rewrite_ratio: 0.9, touched_existing_files: 12, rewritten_lines: 900, basis: "b" };
const FILES_ONLY = { touched_existing_files: 2, rewritten_lines: 40, basis: "b" };

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
const record = (r) => r.escalations.find((e) => e.trigger === "refactor-scope");

test("a declared ratio with no usable ceiling is never reported as within one", async () => {
  const ev = await only(HEAVY_RATIO, NO_RATIO_CEILING);
  assert.equal(ev.payload.state, "WITHIN_PARTIAL");
  assert.equal(ev.payload.state === "WITHIN", false);
});

test("the event names which dimensions were compared and which were skipped", async () => {
  const ev = await only(HEAVY_RATIO, NO_RATIO_CEILING);
  assert.deepEqual(ev.payload.compared, ["touched_existing_files"]);
  assert.deepEqual(ev.payload.skipped, ["rewrite_ratio"]);
});

test("the summary says plainly that the ratio was never compared", async () => {
  const ev = await only(HEAVY_RATIO, NO_RATIO_CEILING);
  assert.ok(ev.payload.summary.startsWith("refactor radius WITHIN_PARTIAL"));
  assert.ok(ev.payload.summary.includes("rewrite_ratio"));
  assert.ok(ev.payload.summary.includes("no usable ceiling"));
});

test("a mistyped string ceiling behaves exactly like an absent one", async () => {
  const ev = await only(HEAVY_RATIO, STRING_RATIO_CEILING);
  assert.equal(ev.payload.state, "WITHIN_PARTIAL");
  assert.deepEqual(ev.payload.skipped, ["rewrite_ratio"]);
});

test("a partial verdict fails open: the slice raises nothing and exceeds nothing", async () => {
  const result = await evaluate(HEAVY_RATIO, NO_RATIO_CEILING);
  assert.equal(record(result), undefined);
  assert.deepEqual(radiusEvents(result)[0].payload.exceeded, []);
});

test("a fully usable config still records WITHIN with nothing skipped", async () => {
  const ev = await only(SMALL, RADIUS_DEFAULTS);
  assert.equal(ev.payload.state, "WITHIN");
  assert.deepEqual(ev.payload.skipped, []);
  assert.deepEqual(ev.payload.compared, ["rewrite_ratio", "touched_existing_files"]);
});

test("a real breach beside an uncompared dimension still halts the slice", async () => {
  const result = await evaluate(BIG, NO_RATIO_CEILING);
  const ev = radiusEvents(result)[0];
  assert.equal(ev.payload.state, "EXCEEDED");
  assert.deepEqual(ev.payload.skipped, ["rewrite_ratio"]);
  assert.equal(record(result).trigger, "refactor-scope");
});

test("the escalation context tells the human what was not compared", async () => {
  const result = await evaluate(BIG, NO_RATIO_CEILING);
  assert.ok(record(result).context.includes("not compared for want of a usable ceiling"));
  assert.ok(record(result).context.includes("rewrite_ratio"));
});

test("a number the plan never declared is not counted as skipped", async () => {
  const ev = await only(FILES_ONLY, NO_RATIO_CEILING);
  assert.equal(ev.payload.state, "WITHIN");
  assert.deepEqual(ev.payload.skipped, []);
});
