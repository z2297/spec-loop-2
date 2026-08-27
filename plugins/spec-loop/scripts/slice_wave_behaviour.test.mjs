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
