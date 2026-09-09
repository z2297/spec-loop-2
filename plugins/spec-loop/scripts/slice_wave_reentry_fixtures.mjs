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
