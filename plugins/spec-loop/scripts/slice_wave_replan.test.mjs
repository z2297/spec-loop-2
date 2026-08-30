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
  ONE_TASK_PLANNED, SPLIT_OK, SPLIT_EMPTY, ESCALATE_BARE, ESCALATE_FULL,
  OBJECTION_FIXABLE, RECHECK_CLEAN, RECHECK_OBJECT, RECHECK_SAFETY,
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

// ── The post-OBJECT replan re-check ───────────────────────────────────────
// A tier-2 slice runs the critique stage; the council OBJECTs fixably, the
// planner returns a revision, and the question every test below asks is what
// the wave does with that revision.
const T2 = () => [sliceFixture("s1", 2)];
const objectThenReplan = async (revised, recheck) => {
  const sandbox = councilSandbox({
    plan: ONE_TASK_PLANNED,
    "critic:full-council": OBJECTION_FIXABLE,
    replan: revised,
    ...(recheck === undefined ? {} : { "critic:replan": recheck }),
  });
  const out = await runWave(waveArgs(T2()), sandbox);
  return { r: out.results[0], seen: sandbox.seen };
};

test("a revised plan is re-critiqued before the slice proceeds on it", async () => {
  const { seen } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_CLEAN);
  assert.deepEqual(seen.slice(0, 4), ["plan", "critic:full-council", "replan", "critic:replan"]);
});

test("a clean re-critique lets the slice proceed to its tasks", async () => {
  const { seen } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_CLEAN);
  assert.equal(seen[4], "task:t1");
});

test("a re-critique that OBJECTS escalates instead of proceeding", async () => {
  const { r, seen } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_OBJECT);
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].trigger, "council-objection");
  assert.equal(seen.includes("task:t1"), false);
});

test("the escalation carries the reason the REVISION was rejected", async () => {
  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_OBJECT);
  assert.equal(r.escalations[0].context, "the revision still skips the migration test");
});

test("an unreadable re-critique fails closed into the same escalation", async () => {
  const { r } = await objectThenReplan(ONE_TASK_PLANNED, null);
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].trigger, "council-objection");
});

test("a safety flag raised only on the re-check still blocks and is titled SAFETY", async () => {
  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_SAFETY);
  assert.equal(r.status, "ESCALATED");
  assert.match(r.escalations[0].title, /^SAFETY — /);
});

// RECHECK_SAFETY carries no `objection` block (schema-legal: CRITIQUE only
// requires verdict/safety/concerns) and its safety reason deliberately differs
// from OBJECTION_FIXABLE's objection reason, so this catches a silent fallback
// to the stale, pre-replan objection instead of the re-check's own new risk.
test("the escalation describes the re-check's OWN safety reason, not the stale original objection", async () => {
  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_SAFETY);
  assert.match(r.escalations[0].title, /the revision drops the pre-migration backup/);
  assert.equal(r.escalations[0].context, "the revision drops the pre-migration backup");
  assert.equal(r.escalations[0].context.includes("migration test"), false);
});

test("a re-check safety reason is carried in the replan-recheck event payload", async () => {
  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_SAFETY);
  const ev = r.events.find((e) => e.type === "replan-recheck");
  assert.equal(ev.payload.safety_reason, "the revision drops the pre-migration backup");
});

test("a replan that returns no plan escalates without spending a re-critique", async () => {
  const { r, seen } = await objectThenReplan(null, RECHECK_CLEAN);
  assert.equal(r.status, "ESCALATED");
  assert.equal(seen.includes("critic:replan"), false);
});

test("a replan that returns ESCALATE is not accepted as a plan", async () => {
  const { r, seen } = await objectThenReplan(ESCALATE_BARE, RECHECK_CLEAN);
  assert.equal(r.status, "ESCALATED");
  assert.equal(seen.includes("critic:replan"), false);
});

test("every re-check records exactly one replan-recheck event with its verdict", async () => {
  const { r } = await objectThenReplan(ONE_TASK_PLANNED, RECHECK_OBJECT);
  const evs = r.events.filter((e) => e.type === "replan-recheck");
  assert.equal(evs.length, 1);
  assert.equal(evs[0].scope, "s1");
  assert.equal(evs[0].payload.verdict, "OBJECT");
  assert.equal(evs[0].payload.safety, false);
  assert.equal(evs[0].payload.accepted, false);
});
