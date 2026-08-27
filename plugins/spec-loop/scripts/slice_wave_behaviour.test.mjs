// slice_wave_behaviour.test.mjs — the first EXECUTING test of the wave workflow.
//
// HONEST LIMIT, stated plainly: this suite verifies the workflow's
// DETERMINISTIC CONTROL FLOW ONLY. It drives the file against a mock
// agent/parallel/log/budget sandbox described by HOST_CONTRACT in
// slice_wave_harness.mjs. That contract is an ASSUMPTION written down by hand;
// the repo specifies no host-sandbox contract anywhere. The real Workflow-host
// seam is therefore NOT exercised here and stays unverified. A green run on
// this file does not promote any claim to "behaviourally verified against the
// host" — it says the behaviour asserted below holds against the mock
// sandbox, and nothing wider.
//
// Node BUILT-INS ONLY (node:test + node:assert/strict), matching
// dashboard_assets/index.test.mjs and the repo's zero-dependency posture.

import test from "node:test";
import assert from "node:assert/strict";
import {
  HOST_CONTRACT, countExportConst, countWrapperName, WRAPPER_NAME,
  rawSource, wrappedSource, makeWave, runWave, sliceFixture, waveArgs,
} from "./slice_wave_harness.mjs";

test("the export-const rewrite matches exactly once", () => {
  assert.equal(countExportConst(rawSource()), 1);
  assert.equal(countExportConst(wrappedSource()), 0);
});

test("the wrapped source instantiates as an AsyncFunction", () => {
  const wave = makeWave();
  assert.equal(typeof wave, "function");
  assert.equal(wave.constructor.name, "AsyncFunction");
});

test("the assumed host contract is a named artifact marked unverified", () => {
  assert.deepEqual(
    Object.keys(HOST_CONTRACT).sort(),
    ["agent", "budget", "log", "parallel", "verified"],
  );
  assert.equal(HOST_CONTRACT.verified, false);
});

// The wrapped source only DECLARES the wrapper; makeWave appends a call to it
// BY NAME. A rename inside slice_wave_contract_base.WRAP_HEAD would otherwise
// make every behavioural test below assert against undefined. These two tests
// make that failure land here, in the loader group, with a readable cause.
test("the wrapper name appears exactly once in the wrapped source", () => {
  assert.equal(WRAPPER_NAME, "__wrap");
  assert.equal(countWrapperName(wrappedSource()), 1);
  assert.equal(countWrapperName(rawSource()), 0);
});

test("running the loaded wave resolves an object carrying a results array", async () => {
  const sandbox = { agent: async () => { throw new Error("BOOM"); } };
  const out = await runWave(waveArgs([sliceFixture("s1")]), sandbox);
  assert.equal(typeof out, "object");
  assert.notEqual(out, null);
  assert.ok(Array.isArray(out.results));
  assert.equal(out.results.length, 1);
});

const CRASH_TRIGGER = "internal-error";
const RECORD_OPTIONS = ["Retry this slice", "Skip this slice", "Stop the run"];
const ONE_SLICE = () => waveArgs([sliceFixture("s1")]);
const THROWS = { agent: async () => { throw new Error("BOOM"); } };
const only = (out) => out.results[0].escalations[0];

test("an agent that throws escalates the slice with the internal-error trigger", async () => {
  const out = await runWave(ONE_SLICE(), THROWS);
  assert.equal(out.results.length, 1);
  assert.equal(out.results[0].status, "ESCALATED");
  assert.equal(out.results[0].escalations.length, 1);
  assert.equal(only(out).id, "s1:" + CRASH_TRIGGER);
  assert.equal(only(out).trigger, CRASH_TRIGGER);
  assert.equal(only(out).status, "OPEN");
});

test("the crash record title names the last dispatched stage", async () => {
  const out = await runWave(ONE_SLICE(), THROWS);
  assert.equal(only(out).title, "slice crashed after plan");
});

test("the crash record carries the three controller-named options in order", async () => {
  const out = await runWave(ONE_SLICE(), THROWS);
  assert.deepEqual(only(out).options.map((o) => o.label), RECORD_OPTIONS);
  assert.equal(only(out).options[0].recommended, true);
  assert.equal(only(out).options[1].recommended, undefined);
  assert.equal(only(out).options[2].recommended, undefined);
});

test("the guaranteed context ordering leads with the two variable diagnostics", async () => {
  const ctx = only(await runWave(ONE_SLICE(), THROWS)).context;
  assert.ok(ctx.startsWith("Error: BOOM."));
  const stageAt = ctx.indexOf("Last stage/role dispatched before the failure: plan");
  const causeAt = ctx.indexOf("Cause unknown");
  const tasksAt = ctx.indexOf("task(s) had already completed");
  assert.ok(stageAt > 0);
  assert.ok(causeAt > stageAt);
  assert.ok(tasksAt > causeAt);
});

test("a crash before any dispatch yields the no-stage title", async () => {
  const budget = { total: 1, remaining: () => { throw new Error("NOBUDGET"); } };
  const out = await runWave(ONE_SLICE(), { budget });
  assert.equal(only(out).title, "slice crashed before any agent was dispatched");
  assert.ok(only(out).context.includes(
    "none (the crash happened before any agent was dispatched)"));
});

const LOST = { parallel: async () => [null] };

test("a lost slice escalates with the same trigger and its own title", async () => {
  const out = await runWave(ONE_SLICE(), LOST);
  assert.equal(out.results[0].status, "ESCALATED");
  assert.equal(out.results[0].tasks_completed, 0);
  assert.equal(out.results[0].agents_used, 0);
  assert.deepEqual(out.results[0].quality, { status: "SKIPPED", detail: "slice never ran" });
  assert.equal(only(out).id, "s1:" + CRASH_TRIGGER);
  assert.equal(only(out).trigger, CRASH_TRIGGER);
  assert.equal(only(out).title, "slice lost");
  assert.ok(only(out).question.startsWith("Re-run the wave to retry this slice"));
});

// The lost-slice record used to rely on esc()'s empty-array substitution, which
// yields ONE option labelled "Proceed with the recommended default" whose detail
// repeats the whole context. The human ruled that widening this record to the same
// three controller-named labels as the crash record is the fix. The record's own
// question stays binary on purpose, so this test pins the OPTION SET by execution
// and claims nothing about the ask.
test("the lost-slice record carries the same three controller-named options", async () => {
  const rec = only(await runWave(ONE_SLICE(), LOST));
  assert.deepEqual(rec.options.map((o) => o.label), RECORD_OPTIONS);
  assert.equal(rec.options[0].recommended, true);
  assert.equal(rec.options[1].recommended, undefined);
  assert.equal(rec.options[2].recommended, undefined);
  rec.options.forEach((o) => assert.notEqual(o.detail, rec.context));
  rec.options.forEach((o) => assert.ok(o.detail.includes("CONTROLLER")));
});

// The two internal-error records now share the trigger, the id shape and the three
// option labels. What still separates them is the evidence and the ask: the crash
// record carries exception text plus a stage attribution and asks which of the three
// to take; the lost-slice record carries neither and asks the binary re-run question.
// A future edit that collapses them into one indistinguishable record fails here.
test("the crash and lost-slice records stay distinguishable after the widening", async () => {
  const crash = only(await runWave(ONE_SLICE(), THROWS));
  const lost = only(await runWave(ONE_SLICE(), LOST));
  assert.equal(crash.trigger, lost.trigger);
  assert.deepEqual(crash.options.map((o) => o.label), RECORD_OPTIONS);
  assert.deepEqual(lost.options.map((o) => o.label), RECORD_OPTIONS);
  assert.notEqual(crash.title, lost.title);
  assert.equal(lost.title, "slice lost");
  assert.notEqual(crash.context, lost.context);
  assert.notEqual(crash.question, lost.question);
  assert.ok(crash.context.startsWith("Error: BOOM."));
  assert.ok(!lost.context.startsWith("Error:"));
  assert.ok(!lost.context.includes("Last stage/role dispatched"));
});

const FOUR_IDS = ["s1", "s2", "s3", "s4"];
const FOUR = () => waveArgs(FOUR_IDS.map(sliceFixture));
// The prompt carries the slice id (planPrompt embeds it), so an agent that
// throws the prompt's own id back gives each slice a distinguishable failure.
const THROW_LABELLED = {
  agent: async (prompt, opts) => { throw new Error("crash-of-" + opts.label); },
};

test("every slice in a width-4 wave gets its own result, positionally", async () => {
  const out = await runWave(FOUR(), THROW_LABELLED);
  assert.equal(out.results.length, 4);
  assert.deepEqual(out.results.map((r) => r.id), FOUR_IDS);
  assert.deepEqual(out.results.map((r) => r.status), ["ESCALATED", "ESCALATED", "ESCALATED", "ESCALATED"]);
  assert.equal(out.wave_index, 0);
  assert.equal(out.run_id, "20260827-harness");
});

test("each escalation id and context is attributed to its own slice", async () => {
  const out = await runWave(FOUR(), THROW_LABELLED);
  const recs = out.results.map((r) => r.escalations[0]);
  assert.deepEqual(recs.map((r) => r.id), FOUR_IDS.map((i) => i + ":" + CRASH_TRIGGER));
  assert.deepEqual(recs.map((r) => r.context.startsWith("Error: crash-of-")), [true, true, true, true]);
  FOUR_IDS.forEach((id, i) => assert.ok(recs[i].context.includes("crash-of-" + id + ":plan")));
});
