// slice_wave_behaviour.test.mjs — the first EXECUTING test of the wave workflow.
// HONEST LIMIT: verifies only the workflow's DETERMINISTIC CONTROL FLOW, against
// the mock HOST_CONTRACT sandbox in slice_wave_harness.mjs (an ASSUMPTION the repo
// does not itself specify) — the real Workflow-host seam stays unverified. Node
// BUILT-INS ONLY (node:test + node:assert/strict), matching the repo's posture.

import test from "node:test";
import assert from "node:assert/strict";
import {
  HOST_CONTRACT, countExportConst, countWrapperName, WRAPPER_NAME, rawSource,
  wrappedSource, makeWave, runWave, sliceFixture, waveArgs,
  capturePrompts, capAgent, fullPipeline, PIPELINE_LABELS } from "./slice_wave_harness.mjs";

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
  assert.deepEqual(Object.keys(HOST_CONTRACT).sort(), ["agent", "budget", "log", "parallel", "verified"]);
  assert.equal(HOST_CONTRACT.verified, false);
});

// The wrapped source only DECLARES the wrapper; makeWave appends a call to it BY
// NAME, so a rename in slice_wave_contract_base.WRAP_HEAD lands here, readably.
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
  assert.ok(only(out).context.includes("none (the crash happened before any agent was dispatched)"));
});

const LOST = { parallel: async () => [null] };

// Three-way, matching the crash record's shape: the record offers three controller-named options,
// so a yes/no ask would leave a human answering "no" bound to none of them. The tail differs from
// the crash record's on purpose — this record carries no exception text to diagnose.
const LOST_QUESTION =
  "Retry this slice, skip it and continue the run, or stop the run to investigate the silent failure?";

test("a lost slice escalates with the same trigger and its own title", async () => {
  const out = await runWave(ONE_SLICE(), LOST);
  assert.equal(out.results[0].status, "ESCALATED");
  assert.equal(out.results[0].tasks_completed, 0);
  assert.equal(out.results[0].agents_used, 0);
  assert.deepEqual(out.results[0].quality, { status: "SKIPPED", detail: "slice never ran" });
  assert.equal(only(out).id, "s1:" + CRASH_TRIGGER);
  assert.equal(only(out).trigger, CRASH_TRIGGER);
  assert.equal(only(out).title, "slice lost");
  assert.equal(only(out).question, LOST_QUESTION);
});

// The lost-slice record used to rely on esc()'s empty-array substitution, which yields ONE option
// labelled "Proceed with the recommended default" whose detail repeats the whole context. The human
// ruled that widening this record to the same three controller-named labels as the crash record is
// the fix. This test pins the OPTION SET by execution; the ask itself is pinned separately, above.
test("the lost-slice record carries the same three controller-named options", async () => {
  const rec = only(await runWave(ONE_SLICE(), LOST));
  assert.deepEqual(rec.options.map((o) => o.label), RECORD_OPTIONS);
  assert.equal(rec.options[0].recommended, true);
  assert.equal(rec.options[1].recommended, undefined);
  assert.equal(rec.options[2].recommended, undefined);
  rec.options.forEach((o) => assert.notEqual(o.detail, rec.context));
  rec.options.forEach((o) => assert.ok(o.detail.includes("CONTROLLER")));
});

// The two internal-error records now share the trigger, the id shape and the three option labels. They
// differ in evidence and in ask: the crash record carries exception text plus a stage attribution and
// asks which of the three to take; the lost-slice record carries neither and asks the same three-way
// question with its own tail. An edit collapsing them into one indistinguishable record fails here.
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
// The prompt carries the slice id, so an agent throwing it back distinguishes each slice's failure.
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

// ── escalation id rounds (esc/escId) and answer matching (latestAnswer) ──────
// The round comes from args.answers, so these tests hand the wave an answers map a
// resuming controller would supply and read the id the wave actually emits.

const CRASH_KEY = "s1:" + CRASH_TRIGGER;
const withAnswers = (answers) => waveArgs([sliceFixture("s1")], answers);

test("an unanswered slice keeps the bare id, with no round component", async () => {
  const out = await runWave(withAnswers({}), THROWS);
  assert.equal(only(out).id, CRASH_KEY);
});

test("a second dispatch after an answer to round one raises round two", async () => {
  const out = await runWave(withAnswers({ [CRASH_KEY]: "retry it" }), THROWS);
  assert.equal(only(out).id, CRASH_KEY + ":2");
  assert.equal(only(out).trigger, CRASH_TRIGGER);
});

test("a third round follows the bare and the round-two answers", async () => {
  const answers = { [CRASH_KEY]: "retry it", [CRASH_KEY + ":2"]: "retry again" };
  const out = await runWave(withAnswers(answers), THROWS);
  assert.equal(only(out).id, CRASH_KEY + ":3");
});

test("the same answers map reproduces the same id across dispatches", async () => {
  const answers = { [CRASH_KEY]: "retry it" };
  const first = await runWave(withAnswers(answers), THROWS);
  const second = await runWave(withAnswers(answers), THROWS);
  assert.equal(only(first).id, only(second).id);
  assert.equal(only(second).id, CRASH_KEY + ":2");
});

test("an answer to one trigger does not advance another trigger's round", async () => {
  const out = await runWave(withAnswers({ "s1:ambiguity": "do this" }), THROWS);
  assert.equal(only(out).id, CRASH_KEY);
});

// Answer MATCHING, observed where it is observable: the planner prompt. A round-suffixed
// id whose answer no longer reaches the prompt is pinned here by execution, not inspection.
test("an answer keyed without a round still reaches the prompt", async () => {
  const cap = capturePrompts();
  await runWave(withAnswers({ "s1:ambiguity": "ANSWER-ONE" }), { agent: cap.agent });
  assert.ok(cap.seen[0].includes("ANSWER-ONE"));
  assert.ok(cap.seen[0].includes('HUMAN ANSWER to your earlier "ambiguity" escalation'));
});

test("an answer keyed with a round reaches the prompt too", async () => {
  const cap = capturePrompts();
  await runWave(withAnswers({ "s1:ambiguity:2": "ANSWER-TWO" }), { agent: cap.agent });
  assert.ok(cap.seen[0].includes("ANSWER-TWO"));
});

test("the newest answered round wins with several rounds answered", async () => {
  const cap = capturePrompts();
  const answers = { "s1:ambiguity": "ANSWER-ONE", "s1:ambiguity:2": "ANSWER-TWO" };
  await runWave(withAnswers(answers), { agent: cap.agent });
  assert.ok(cap.seen[0].includes("ANSWER-TWO"));
  assert.ok(!cap.seen[0].includes("ANSWER-ONE"));
});

// ── the per-slice agent cap and its human-authorised raise (guard/agentCap) ──
// Driven by EXECUTION, not by inspection: the twelve-task fixture in the harness makes the wave
// spend one dispatch per task, so the tier-1 default of ten is reached inside stageTasks and a
// raised cap is reached later, in stageReviewGate. The caps themselves are the workflow's own CAPS
// values; nothing here restates the rule, it reads the record the guard actually produced.

const capWave = (overrides) => waveArgs([sliceFixture("s1")], {}, overrides);

test("the tier default agent cap stops the slice with a budget-exhausted record", async () => {
  const out = await runWave(capWave(undefined), capAgent());
  assert.equal(out.results[0].status, "ESCALATED");
  assert.equal(only(out).trigger, "budget-exhausted");
  assert.equal(only(out).id, "s1:budget-exhausted");
  assert.equal(only(out).title, "agent cap reached (10)");
  assert.ok(only(out).context.includes("tier 1 default 10, effective cap 10"));
  assert.equal(out.results[0].agents_used, 10);
});

test("an authorised override raises the cap the guard enforces", async () => {
  const out = await runWave(capWave({ agent_cap_overrides: { s1: 14 } }), capAgent());
  assert.equal(only(out).trigger, "budget-exhausted");
  assert.equal(only(out).title, "agent cap reached (14)");
  assert.ok(only(out).context.includes("tier 1 default 10, effective cap 14"));
  assert.equal(out.results[0].agents_used, 14);
  assert.equal(out.results[0].tasks_completed, 12);
});

test("an override at or below the tier default is ignored", async () => {
  const out = await runWave(capWave({ agent_cap_overrides: { s1: 5 } }), capAgent());
  assert.equal(only(out).title, "agent cap reached (10)");
  assert.equal(out.results[0].agents_used, 10);
});

test("a non-numeric override is ignored rather than trusted", async () => {
  const out = await runWave(capWave({ agent_cap_overrides: { s1: "lots" } }), capAgent());
  assert.equal(only(out).title, "agent cap reached (10)");
});

test("an override keyed to another slice does not raise this slice's cap", async () => {
  const out = await runWave(capWave({ agent_cap_overrides: { s2: 30 } }), capAgent());
  assert.equal(only(out).title, "agent cap reached (10)");
  assert.equal(out.results[0].agents_used, 10);
});

test("the cap record's options name the controller action that applies a raise", async () => {
  const rec = only(await runWave(capWave(undefined), capAgent()));
  assert.deepEqual(rec.options.map((o) => o.label), [
    "Raise the agent cap and resume", "Accept the slice as-is", "Drop the slice",
  ]);
  assert.equal(rec.options[0].recommended, true);
  assert.ok(rec.options[0].detail.includes("agent_cap_overrides"));
  rec.options.forEach((o) => assert.ok(o.detail.includes("CONTROLLER")));
  assert.equal(rec.question, "Raise the cap and resume, accept the slice as-is, or drop it?");
});

const capEvents = (out) => out.results[0].events.filter((e) => e.type === "agent-cap-override");

// A supplied override the channel cannot use leaves the tier default in force. Announcing it at
// slice start is the point: silence hides the discard until the slice hits the cap a second time.
// It stays out of the agent-cap-override event, whose payload means a raise that took effect.
const discards = (out) => out.results[0].events.filter(
  (e) => e.type === "decision" && String(e.payload.summary).startsWith("agent cap override"));

test("an applied raise is recorded as one auditable event, announcing no discard", async () => {
  const out = await runWave(capWave({ agent_cap_overrides: { s1: 14 } }), capAgent());
  assert.equal(capEvents(out).length, 1);
  assert.equal(capEvents(out)[0].scope, "s1");
  assert.deepEqual(capEvents(out)[0].payload, { tier: 1, default_cap: 10, effective_cap: 14 });
  assert.equal(discards(out).length, 0);
});

test("no override means no override event and no discard either", async () => {
  const out = await runWave(capWave(undefined), capAgent());
  assert.equal(capEvents(out).length, 0);
  assert.equal(discards(out).length, 0);
});

test("an override below the tier default records no raise and is announced once", async () => {
  const out = await runWave(capWave({ agent_cap_overrides: { s1: 5 } }), capAgent());
  assert.equal(capEvents(out).length, 0);
  assert.equal(discards(out).length, 1);
});

test("a fractional override leaves the tier default in force and is announced once", async () => {
  const out = await runWave(capWave({ agent_cap_overrides: { s1: 10.5 } }), capAgent());
  assert.equal(only(out).title, "agent cap reached (10)");
  assert.equal(out.results[0].agents_used, 10);
  assert.equal(discards(out).length, 1);
  assert.equal(discards(out)[0].scope, "s1");
  assert.ok(discards(out)[0].payload.summary.includes("10.5"));
  assert.equal(capEvents(out).length, 0);
});

test("an override keyed to no slice of the wave is announced too", async () => {
  const out = await runWave(capWave({ agent_cap_overrides: { s2: 30 } }), capAgent());
  assert.equal(discards(out).length, 1);
  assert.ok(discards(out)[0].payload.summary.includes("s2"));
});

// budget-exhausted requests a resource, so its answer is deliberately injected into no agent
// prompt. The source-text twin of this lives in test_slice_wave_contract.py; this one drives a
// real answer through a slice that runs plan through verify and reads all eight prompts that run
// built. The label set is asserted too, so the pin cannot narrow in silence, and the ambiguity
// answer alongside it proves injection was live at the same time.
test("a budget-exhausted answer reaches no prompt of a whole slice run", async () => {
  const cap = fullPipeline();
  const answers = { "s1:budget-exhausted": "RAISE-IT-TO-40", "s1:ambiguity": "ANSWER-CTL" };
  const out = await runWave(waveArgs([sliceFixture("s1", 2)], answers), { agent: cap.agent });
  const prompts = cap.seen.map((s) => s.prompt);
  assert.equal(out.results[0].status, "DONE");
  assert.deepEqual(cap.seen.map((s) => s.label).sort(), [...PIPELINE_LABELS].sort());
  assert.ok(prompts.some((p) => p.includes("ANSWER-CTL")));
  prompts.forEach((p) => assert.ok(!p.includes("RAISE-IT-TO-40")));
  prompts.forEach((p) => assert.ok(!p.includes("budget-exhausted")));
});
