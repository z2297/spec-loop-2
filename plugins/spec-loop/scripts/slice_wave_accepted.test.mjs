// slice_wave_accepted.test.mjs — accepted quality-gate violations and the
// escalation round cap, EXECUTED. Run 20260908's slice j1 escalated
// quality-gate-block three times on the same four violations the controller
// had already accepted, because the wave had no notion of an acceptance and no
// bound on re-raising. HONEST LIMITS: deterministic control flow against the
// mock sandbox in slice_wave_harness.mjs only.

import test from "node:test";
import assert from "node:assert/strict";
import { runWave, waveArgs, sliceFixture, pipelineWith } from "./slice_wave_harness.mjs";
import {
  GATE_REMEASURE, FIX_ROUND_TWO, RR_NOT_ADDRESSED,
  J1_VIOLATIONS, NESTING_VIOLATION, J1_ACCEPTED, VERIFY_FAIL_J1, VERIFY_NULL_GATE, verifyFailing,
} from "./slice_wave_reentry_fixtures.mjs";

const T2 = () => [sliceFixture("s1", 2)];
const accepting = (fps, answers) => waveArgs(T2(), answers, { accepted_violations: { s1: fps } });
const run = async (args, sandbox) => (await runWave(args, sandbox)).results[0];
const failingBoth = (v) => pipelineWith({ "gate": v, "verify:1": v });
// The gate passes at stage R and the violation appears at verification, so the
// escalation under test is the verify stage's own (a failing stage-R gate would
// spend fix rounds on qg-N findings first).
const failingVerify = (v) => pipelineWith({ "verify:1": v });
const decisions = (r) => r.events.filter((e) => e.type === "decision").map((e) => e.payload.summary);
const lastGate = (r) => r.events.filter((e) => e.type === "quality-gate").at(-1).payload;
const promptOf = (sandbox, label) => sandbox.seen.find((d) => d.label === label).prompt;

test("a slice whose only violations are accepted finishes DONE with an honest FAIL quality block", async () => {
  const r = await run(accepting(J1_ACCEPTED), failingBoth(VERIFY_FAIL_J1));
  assert.equal(r.status, "DONE");
  assert.equal(r.quality.status, "FAIL");
  assert.equal(r.quality.accepted.length, 4);
  assert.equal(r.quality.violations, 0);
  assert.equal(lastGate(r).accepted, 4);
  assert.equal(lastGate(r).violations, 0);
});

test("an acceptance matches on metric, file and function, never on the measured value", async () => {
  const grown = J1_VIOLATIONS.map((v) => ({ ...v, value: v.value + 400 }));
  const r = await run(accepting(J1_ACCEPTED), failingBoth(verifyFailing(grown)));
  assert.equal(r.status, "DONE");
});

test("a leading ./ on either side does not defeat the match", async () => {
  const dotted = J1_ACCEPTED.map((fp) => ({ ...fp, file: "./" + fp.file }));
  const r = await run(accepting(dotted), failingBoth(VERIFY_FAIL_J1));
  assert.equal(r.status, "DONE");
});

test("one unaccepted violation still escalates, and the record lists only that one", async () => {
  const r = await run(accepting(J1_ACCEPTED), failingVerify(verifyFailing([...J1_VIOLATIONS, NESTING_VIOLATION])));
  assert.equal(r.status, "ESCALATED");
  const rec = r.escalations[0];
  assert.equal(rec.trigger, "quality-gate-block");
  assert.equal(rec.violations.length, 1);
  assert.equal(rec.violations[0].metric, "nesting_depth");
  assert.equal(rec.violations[0].function, "_http_get");
  assert.match(rec.context, /4 accepted/);
  assert.equal(r.quality.accepted.length, 4);
  assert.equal(r.quality.violations, 1);
});

test("an acceptance keyed to another slice changes nothing here and is announced once", async () => {
  const args = waveArgs(T2(), {}, { accepted_violations: { s2: J1_ACCEPTED } });
  const r = await run(args, failingVerify(VERIFY_FAIL_J1));
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].violations.length, 4);
  assert.equal(decisions(r).filter((s) => /naming no slice/.test(s) && /s2/.test(s)).length, 1);
});

test("a gate that produced no JSON is never acceptable", async () => {
  const r = await run(accepting(J1_ACCEPTED), failingVerify(VERIFY_NULL_GATE));
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].trigger, "quality-gate-block");
});

test("an accepted fingerprint that matches nothing measured is announced as drift", async () => {
  const stale = [...J1_ACCEPTED, { metric: "class_lines", file: "plugins/spec-loop/scripts/renamed.py", function: null }];
  const r = await run(accepting(stale), failingBoth(VERIFY_FAIL_J1));
  assert.equal(r.status, "DONE");
  assert.equal(decisions(r).filter((s) => /matched no measured violation/.test(s) && /renamed\.py/.test(s)).length, 1);
});

test("a wildcard fingerprint is discarded and announced, never applied", async () => {
  const r = await run(accepting([{ metric: "class_lines", file: "*", function: null }]), failingVerify(VERIFY_FAIL_J1));
  assert.equal(r.status, "ESCALATED");
  assert.equal(r.escalations[0].violations.length, 4);
  assert.equal(decisions(r).filter((s) => /discarded/.test(s) && /\*/.test(s)).length, 1);
});

test("accepted violations produce no quality-gate finding for the fixer", async () => {
  const sandbox = failingBoth(VERIFY_FAIL_J1);
  await run(accepting(J1_ACCEPTED), sandbox);
  assert.ok(!promptOf(sandbox, "s1:fix:1").includes("qg-"));
});

// ── Round cap ────────────────────────────────────────────────────────────

const TWO_ROUNDS = { "s1:quality-gate-block": "accept them", "s1:quality-gate-block:2": "still accept" };

test("the third round of one trigger is reframed as non-terminating with controller-named options", async () => {
  const r = await run(waveArgs(T2(), TWO_ROUNDS), failingVerify(VERIFY_FAIL_J1));
  const rec = r.escalations[0];
  assert.equal(rec.id, "s1:quality-gate-block:3");
  assert.match(rec.title, /^non-terminating: same quality-gate-block after 2 answered rounds/);
  assert.ok(rec.options.some((o) => o.detail.includes("accept-violations")));
  assert.ok(rec.options.some((o) => /never hand-write a DONE sidecar/.test(o.detail)));
  assert.equal(rec.violations.length, 4);
});

test("a later-round answer still reaches the fixer after the cap", async () => {
  const sandbox = failingVerify(VERIFY_FAIL_J1);
  await run(waveArgs(T2(), { ...TWO_ROUNDS, "s1:quality-gate-block:3": "ROUND-THREE-GUIDANCE" }), sandbox);
  assert.match(promptOf(sandbox, "s1:fix:1"), /ROUND-THREE-GUIDANCE/);
});

test("the cap on one trigger leaves another trigger's round alone", async () => {
  const sandbox = pipelineWith({ "re-review:1": RR_NOT_ADDRESSED, "fix:2": FIX_ROUND_TWO, "re-review:2": RR_NOT_ADDRESSED, "gate:remeasure": GATE_REMEASURE });
  const r = await run(waveArgs(T2(), TWO_ROUNDS), sandbox);
  assert.equal(r.escalations[0].id, "s1:review-block");
  assert.doesNotMatch(r.escalations[0].title, /^non-terminating/);
});

test("a record whose id already has an answer is returned ANSWERED, not re-opened", async () => {
  const r = await run(waveArgs(T2(), { "s1:quality-gate-block:2": "already ruled" }), failingVerify(VERIFY_FAIL_J1));
  assert.equal(r.escalations[0].id, "s1:quality-gate-block:2");
  assert.equal(r.escalations[0].status, "ANSWERED");
  assert.equal(r.escalations[0].answer, "already ruled");
});
