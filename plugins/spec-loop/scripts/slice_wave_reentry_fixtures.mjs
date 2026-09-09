// slice_wave_reentry_fixtures.mjs — mock agent returns for the measurement and
// re-entry paths driven by slice_wave_reentry.test.mjs. A separate module
// because slice_wave_harness.mjs sits at the quality gate's 300-non-blank-line
// class_lines ceiling. Nothing here restates a workflow rule: every value is a
// schema-shaped agent return the wave reads.
// ── Re-entry / measurement fixtures ──────────────────────────────────────
// Schema-legal returns for the paths a re-dispatched slice takes: a red suite,
// a fixer that could not fix, a re-reviewer that closes nothing, and a gate
// re-measure. Each carries a head sha distinct from every other fixture so a
// test can tell WHICH measurement the sidecar recorded.
export const VERIFY_SUITE_RED = {
  suite: { command: "true", passed: false, summary: "1 failed" },
  quality: { summary_pass: true, violations: [], detail: "clean" },
  head_sha: "red0000", tree_sha: "treered",
};
export const GATE_REMEASURE = {
  suite: { command: "skipped", passed: true, summary: "gate-only dispatch" },
  quality: { summary_pass: true, violations: [], detail: "clean after fix" },
  head_sha: "f1x0000", tree_sha: "treef1x",
};
export const FIX_BLOCKED = { status: "BLOCKED", touched_files: [], addressed: [], refuted: [], blocker: "cannot" };
export const FIX_ROUND_TWO = {
  status: "DONE", touched_files: ["a.py"], addressed: ["r0-f1"], refuted: [],
  commits: { base: "f1x0000", head: "f2x0000" },
};
export const RR_NOT_ADDRESSED = { verdicts: [{ finding_id: "r0-f1", verdict: "NOT_ADDRESSED" }], new_breakage: [] };
export const RR_ADDRESSED = { verdicts: [{ finding_id: "r0-f1", verdict: "ADDRESSED" }], new_breakage: [] };
export const DEBUG_FIX_DONE = {
  status: "DONE", touched_files: ["a.py"], addressed: [], refuted: [],
  commits: { base: "0000000", head: "d3b0000" },
};

// ── slice.entry fixtures ──────────────────────────────────────────────────
import { sliceFixture } from "./slice_wave_harness.mjs";

// A slice the controller re-dispatches with an entry, built over the same
// fixture every other test uses so the two shapes cannot drift.
export const reentrySlice = (id, tier, entry) => ({ ...sliceFixture(id, tier), entry });

export const ENTRY_HEAD = "c0bdca3";
export const ORDER_TEXT = "defuse card-derived front-matter delimiters on every body surface";
export const RR_ORDER_ADDRESSED = { verdicts: [{ finding_id: "order-0", verdict: "ADDRESSED" }], new_breakage: [] };
export const PLAN_EMPTY = { status: "PLANNED", plan_path: "/tmp/plan.md", tasks: [] };
export const TASK_BLOCKED = { status: "BLOCKED", touched_files: [], concerns: [], deviations: [], blocker: "which store?" };
export const TASK_RETRY_DONE = {
  status: "DONE", touched_files: [], concerns: [], deviations: [],
  commits: { base: "0000000", head: "c0ffee0" },
};

// ── Accepted-violation fixtures (run 20260908, slice j1) ─────────────────
// The four violations j1 escalated on three times: three whole-file
// class_lines breaches (no function) and one stdlib-forced parameter_count.
// Shapes follow quality_gate.py's summary.failures entries.
const cl = (file, value) => ({ metric: "class_lines", value, threshold: 300, file, pass: false });
export const J1_VIOLATIONS = [
  cl("plugins/spec-loop/scripts/jira_client.py", 536),
  cl("plugins/spec-loop/scripts/test_jira_client.py", 700),
  cl("scripts/measure_coverage.py", 537),
  { metric: "parameter_count", value: 6, threshold: 5, file: "plugins/spec-loop/scripts/jira_client.py", function: "redirect_request", pass: false },
];
export const NESTING_VIOLATION = { metric: "nesting_depth", value: 4, threshold: 3, file: "plugins/spec-loop/scripts/jira_client.py", function: "_http_get", pass: false };
export const J1_ACCEPTED = J1_VIOLATIONS.map((v) => ({ metric: v.metric, file: v.file, function: v.function || null }));
export const verifyFailing = (violations) => ({
  suite: { command: "true", passed: true, summary: "ok" },
  quality: { summary_pass: false, violations, detail: violations.length + " failures" },
  head_sha: "f79156b", tree_sha: "treej1",
});
export const VERIFY_FAIL_J1 = verifyFailing(J1_VIOLATIONS);
export const VERIFY_NULL_GATE = { ...verifyFailing(J1_VIOLATIONS), quality: { summary_pass: null, violations: [], detail: "gate crashed" } };
