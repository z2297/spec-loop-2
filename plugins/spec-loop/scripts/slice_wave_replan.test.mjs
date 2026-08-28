// slice_wave_replan.test.mjs — the guards on optional agent-return fields and the
// re-check of a plan revised after a council OBJECT, EXECUTED.
// HONEST LIMITS: this drives deterministic control flow only, against the mock
// sandbox in slice_wave_harness.mjs; the real Workflow-host seam stays unverified.
// It does NOT cover the plan-time refactor-radius gate on a revised plan - that
// re-evaluation is a known, deliberate gap (see the workflow comment on
// acceptRevisedPlan). Third harness module because slice_wave_behaviour.test.mjs
// sits at the quality gate's 300-non-blank-line class_lines ceiling.

import test from "node:test";
import assert from "node:assert/strict";
import {
  runWave, waveArgs, sliceFixture, councilSandbox, pipelineWith,
  SPLIT_OK, SPLIT_EMPTY, ESCALATE_BARE, ESCALATE_FULL,
} from "./slice_wave_harness.mjs";

const T1 = () => [sliceFixture("s1", 1)];
const runPlan = async (planReturn) => {
  const out = await runWave(waveArgs(T1()), councilSandbox({ plan: planReturn }));
  return out.results[0];
};

test("a SPLIT plan carrying children still returns a SPLIT result", async () => {
  const r = await runPlan(SPLIT_OK);
  assert.equal(r.status, "SPLIT");
  assert.equal(r.split.children.length, 2);
});

test("a SPLIT plan with no split object escalates instead of shipping undefined", async () => {
  const r = await runPlan(SPLIT_EMPTY);
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations.length, 1);
  assert.equal(r.escalations[0].trigger, "ambiguity");
  assert.match(r.escalations[0].title, /SPLIT/);
});

test("an ESCALATE plan with a readable record keeps the planner's own trigger", async () => {
  const r = await runPlan(ESCALATE_FULL);
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].trigger, "material-assumption");
  assert.equal(r.escalations[0].title, "which store");
});

test("an ESCALATE plan with no escalation object still produces a usable record", async () => {
  const r = await runPlan(ESCALATE_BARE);
  assert.equal(r.status, "ESCALATED");
  const rec = r.escalations[0];
  assert.equal(rec.trigger, "ambiguity");
  assert.equal(typeof rec.title, "string");
  assert.ok(rec.question.length > 0);
  assert.ok(rec.options.length > 0);
});

test("a re-review prompt never interpolates undefined when the fixer omits commits", async () => {
  const sandbox = pipelineWith({
    "fix:1": { status: "DONE", touched_files: ["a.py"], addressed: ["r0-f1"], refuted: [] },
  });
  await runWave(waveArgs([sliceFixture("s1", 2)]), sandbox);
  const rr = sandbox.seen.find((d) => d.label === "s1:re-review:1");
  assert.ok(rr, "the re-review dispatch must still happen");
  assert.equal(rr.prompt.includes("--base undefined"), false);
  assert.equal(rr.prompt.includes("--head undefined"), false);
  assert.match(rr.prompt, /--base 0000000/);
});
