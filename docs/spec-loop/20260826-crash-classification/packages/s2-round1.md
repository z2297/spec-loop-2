# Review package: f9f2bd8a8c57be1ba2e6db19dd873b7f8094a575..70f35c1  (context: -U5)

## Commits
70f35c1 docs: correct stale budget-exhausted catch-all claim in test_slice_wave_contract_scope.py
53bc482 docs(changelog): internal-error trigger, narrowed budget-exhausted, downgrade data-loss warning

## Files changed
 CHANGELOG.md                                       | 57 ++++++++++++++++++++++
 .../scripts/test_slice_wave_contract_scope.py      |  6 ++-
 2 files changed, 61 insertions(+), 2 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
10,
66
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_scope.py": [
[
254,
257
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index f193dcc..08e11bf 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -5,10 +5,67 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 
+### Added
+- **`internal-error` escalation trigger** — a seventh `EscalationRecord.trigger` value for machine
+  failure, one string covering both shapes of it: an unhandled exception that aborted a slice
+  (`workflows/slice-wave.workflow.js` — the catch-all at :885) and a slice that returned no result
+  at all (:912). The enum lives at :40. The record leads with the real exception text and names the
+  last stage/role dispatched before the failure — the most recent dispatch, **not** a per-throw
+  stage: the whole stage sequence sits under one `try`, so the loop cannot know which stage threw,
+  and the record says "after", not "in", and says why. It also refuses to guess the cause: an
+  exception reaching the catch-all fired neither structural guard, so it may be a loop or
+  agent-contract bug and it may equally be a host- or agent-layer resource failure that never
+  reaches those guards (a rejected agent call on a hard token or rate limit, say) — the exception
+  text is the evidence, not the label. It is not a judgment trigger and it is not answerable by
+  re-dispatching an agent: its three options (retry the slice, skip it, stop the run) are
+  controller actions, and each option's detail names the controller as what applies it. Added to
+  `ESCALATION_TRIGGERS` in `run_state.py`, `run_metrics.py` and `dashboard_server.py`, to the
+  record shape in `references/run-state-v2.md`, and to the enumerations in
+  `skills/escalation-gate/SKILL.md` and `agents/slice-worker-fallback.md` — the last of these
+  being the behavioral spec for the inline-mode twin, which must classify identically.
+
+### Changed
+- **`budget-exhausted` narrowed to a resource signal** — the string stays and its position in the
+  enum is unchanged; only its meaning narrows. It is now raised solely by the loop's two structural
+  guards, the per-slice agent cap and the per-stage token floor (`slice-wave.workflow.js:425` and
+  `:427`), both of which keep their existing wording. It no longer covers an unhandled exception or
+  a lost slice: through 2.2.0 the catch-all relabelled every uncaught error as a `budget-exhausted`
+  "wave interrupted" escalation — a resource request for a failure that no resource would have
+  prevented — and the lost-slice record carried the same trigger. Both are now `internal-error`.
+  There are still exactly five *judgment* triggers; neither `budget-exhausted` nor `internal-error`
+  is one, and `internal-error` is deliberately outside the answerable set, which stays at five.
+- **`schema_version` stays `2`** — adding an enum value is an additive change to the sidecar
+  contract, so the version is deliberately not bumped (human-decided). `SCHEMA_VERSION` in
+  `run_state.py` and `run_metrics.py` is unchanged, and existing run directories carrying
+  `budget-exhausted` records still validate and still bucket as `budget-exhausted` rather than
+  degrading to `other`.
+
+#### Compatibility: a plugin downgrade to 2.2.0 DISCARDS an affected run dir
+
+This is worse than a mis-labelled trigger, and it is not symmetric with a normal additive change.
+`run_state.py`'s `persist_slice` validates the whole `SliceResult` **before** it writes anything and
+raises `SidecarInvalid` on an unrecognised `trigger`; only after validation passes does it write the
+sidecar, append the slice's events, and render `slice-<id>-report.md`. Under 2.2.0, whose
+`ESCALATION_TRIGGERS` has no `internal-error`, a slice that escalated with that trigger therefore
+produces **no sidecar, no events and no report at all** — not a wrongly-labelled record. The slice
+reports `ESCALATED` with nothing on disk saying why, and the diagnostic information the escalation
+existed to deliver is gone.
+
+Consequences, stated plainly: a run directory written by this version is **not readable by 2.2.0**,
+and the repository and the installed plugin must be updated together. Re-running the affected slice
+under 2.2.0 will not recover the record, because the record was never written.
+
+Verifiability ceiling: nothing this entry describes in `workflows/slice-wave.workflow.js` has been
+executed. The loop resolves its workflow from the installed plugin cache, so the merged file takes
+effect only after a plugin reinstall. Those claims rest on a real `node` parse of the source plus
+source-text contract assertions (`test_slice_wave_contract_crash.py`), which prove a construct is
+present and cannot prove it behaves. The Python-side tuple, validation, metrics and dashboard
+changes are covered by executed tests.
+
 ## [2.2.0] - 2026-08-26
 ### Added
 - **Run-level scope ceiling** — an optional `scope_ceiling` list in `dag.json` (validated
   only when present; a run without one stays fully valid and mutable), threaded through
   `ctx` and prefixed to **every** agent prompt by the wave's shared packet as a binding
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_scope.py b/plugins/spec-loop/scripts/test_slice_wave_contract_scope.py
index 34f29a2..01bb619 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_scope.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_scope.py
@@ -249,12 +249,14 @@ class TestTheRunScopeCeilingReachesEveryAgent(WorkflowSourceTestCase):
 
     def test_the_read_goes_through_the_type_safe_helper_not_a_bare_field_access(self):
         # Regression: `(CTX.scope_ceiling || []).length` was null-safe but not
         # type-safe - truthy for a non-empty STRING too, and the very next
         # read (`.map(...)`) is undefined on a string, throwing a TypeError
-        # that the catch-all mislabels as a budget escalation. packet() must
-        # never touch `CTX.scope_ceiling` directly; only the helper may.
+        # that the catch-all now classifies as 'internal-error' - before crash
+        # classification such errors were mislabeled as a budget escalation.
+        # packet() must never touch `CTX.scope_ceiling` directly; only the
+        # helper may.
         packet = self.between(PACKET_START, PACKET_END)
         self.assertNotIn("CTX.scope_ceiling", packet)
         self.assertIn(SCOPE_CEILING_READ, packet)
         helper = self.between(SCOPE_CEILING_HELPER, HELPER_END)
         self.assertIn("Array.isArray(raw)", helper)
