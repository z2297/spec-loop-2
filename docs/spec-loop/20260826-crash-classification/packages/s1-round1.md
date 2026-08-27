# Review package: 8d0e2c13ba95e4f0aae04941428ea9ecaae3944b..9e8ffe9  (context: -U5)

## Commits
9e8ffe9 test(dashboard): pin that a record-carried internal-error survives _enum_or_none
50fdc32 style(tests): reindent the internal-error bucketing test to clear nesting_depth
d3d0948 style(tests): reindent the crash id-parse test to the 4-space hanging indent
a4d11cd fix(wave): claim only the last dispatched stage, not a stage in flight
99c45aa docs: internal-error in the run-state contract, escalation gate, and inline twin
d23275e Sweep every comment and docstring asserting the old catch-all behaviour
4818011 fix(wave): a lost slice reports internal-error, not budget-exhausted
fd6c0da fix(wave): classify unhandled slice exceptions as internal-error with stage attribution
860f3f9 feat(wave): record the dispatched stage/role on slice state
30a05bb feat(escalations): add internal-error to the trigger enum and all three tuples

## Files changed
 plugins/spec-loop/agents/slice-worker-fallback.md  |  15 ++-
 plugins/spec-loop/references/run-state-v2.md       |   6 +-
 plugins/spec-loop/scripts/dashboard_server.py      |   2 +-
 plugins/spec-loop/scripts/run_metrics.py           |   1 +
 plugins/spec-loop/scripts/run_state.py             |   3 +-
 .../spec-loop/scripts/slice_wave_contract_base.py  |  19 +++-
 plugins/spec-loop/scripts/test_dashboard_server.py |  27 ++++-
 plugins/spec-loop/scripts/test_run_metrics.py      |  17 +++
 plugins/spec-loop/scripts/test_run_state.py        |  11 ++
 .../spec-loop/scripts/test_slice_wave_contract.py  | 123 ++++++++++++++++++---
 plugins/spec-loop/skills/escalation-gate/SKILL.md  |  17 +--
 plugins/spec-loop/workflows/slice-wave.workflow.js |  43 +++++--
 scripts/coverage_omit.txt                          |   4 +-
 13 files changed, 242 insertions(+), 46 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/agents/slice-worker-fallback.md": [
[
145,
153
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
101,
101
],
[
113,
116
]
],
"plugins/spec-loop/scripts/dashboard_server.py": [
[
151,
151
]
],
"plugins/spec-loop/scripts/run_metrics.py": [
[
126,
126
]
],
"plugins/spec-loop/scripts/run_state.py": [
[
68,
69
]
],
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
7,
9
],
[
113,
126
]
],
"plugins/spec-loop/scripts/test_dashboard_server.py": [
[
1247,
1257
],
[
1260,
1260
],
[
1279,
1292
]
],
"plugins/spec-loop/scripts/test_run_metrics.py": [
[
457,
473
]
],
"plugins/spec-loop/scripts/test_run_state.py": [
[
199,
209
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract.py": [
[
3,
4
],
[
27,
30
],
[
32,
34
],
[
36,
39
],
[
65,
68
],
[
153,
155
],
[
262,
350
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
72,
72
],
[
74,
82
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
40,
40
],
[
432,
435
],
[
456,
456
],
[
640,
646
],
[
858,
867
],
[
870,
877
],
[
899,
899
]
],
"scripts/coverage_omit.txt": [
[
38,
39
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/agents/slice-worker-fallback.md b/plugins/spec-loop/agents/slice-worker-fallback.md
index cbfd8c5..a7ee19b 100644
--- a/plugins/spec-loop/agents/slice-worker-fallback.md
+++ b/plugins/spec-loop/agents/slice-worker-fallback.md
@@ -140,16 +140,19 @@ trusts the sidecar over anything you say, and an invalid one makes this slice un
 regardless of how the work went.
 
 ## Escalations
 
 Every escalation is an EscalationRecord in `escalations[]`: stable id `<slice-id>:<trigger>`,
-one of the six triggers (`ambiguity`, `material-assumption`, `review-block`,
-`council-objection`, `quality-gate-block`, `budget-exhausted`), the context, the precise
-question, options with one marked `recommended`, and `if_unanswered`. Proceed-and-log stays the
-default — surface only genuine ambiguity or a material assumption touching behavior, public
-contracts, persisted data, security, or an external integration. A slice with any open
-escalation returns `ESCALATED`.
+one of the seven triggers (`ambiguity`, `material-assumption`, `review-block`,
+`council-objection`, `quality-gate-block`, `budget-exhausted`, `internal-error`), the context,
+the precise question, options with one marked `recommended`, and `if_unanswered`.
+Proceed-and-log stays the default — surface only genuine ambiguity or a material assumption
+touching behavior, public contracts, persisted data, security, or an external integration. A
+slice with any open escalation returns `ESCALATED`. `budget-exhausted` is only for a cap or a
+bound (see Loop bounds); an unhandled exception or a stage that died with no result is
+`internal-error`, and its context must name the last stage/role dispatched before the failure —
+you cannot know which stage threw, so do not claim one — plus the real error text.
 
 ## Return
 
 Statuses: `DONE` · `SPLIT` · `ESCALATED` · `FAILED`. Return a summary of **≤15 lines** —
 status, branch, `base..head`, critique verdict, tasks completed, review outcome (confirmed /
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index cbbd777..61944c9 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -96,11 +96,11 @@ prose about the slice.
 ## `EscalationRecord` (embedded in sidecars; rendered into `escalations.md`)
 
 ```jsonc
 {
   "id": "s1:review-block",     // "<slice-id>:<trigger>[:<round>]" — stable across resumes
-  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | budget-exhausted",
+  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | budget-exhausted | internal-error",
   "title": "<short title>",
   "context": "<what the loop was doing and why it cannot decide>",
   "question": "<the precise question>",
   "options": [{ "label": "...", "detail": "...", "recommended": true }],
   "if_unanswered": "pause this slice; continue all independent slices",
@@ -108,10 +108,14 @@ prose about the slice.
   "opened": "<ISO-8601 UTC>",
   "answer": null, "answered_at": null
 }
 ```
 
+`budget-exhausted` is a structural resource limit (agent cap, stage token floor);
+`internal-error` is a machine failure — an unhandled exception in the loop or an agent
+contract, or a slice that returned no result. Neither is a judgment trigger.
+
 ## `events.jsonl` — the machine channel
 
 Append-only, one JSON object per line, written only by the controller
 (`run_state.py` appends; workflow returns carry the payloads; the controller
 stamps `ts` — workflow scripts have no clock).
diff --git a/plugins/spec-loop/scripts/dashboard_server.py b/plugins/spec-loop/scripts/dashboard_server.py
index a2ee2d4..ec8e994 100644
--- a/plugins/spec-loop/scripts/dashboard_server.py
+++ b/plugins/spec-loop/scripts/dashboard_server.py
@@ -146,11 +146,11 @@ PROJECTED = "projected"
 
 # The EscalationRecord triggers (run-state-v2.md). Used both to validate a
 # record's own ``trigger`` field and to read the trigger an escalation id encodes.
 ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
                        "council-objection", "quality-gate-block",
-                       "budget-exhausted")
+                       "budget-exhausted", "internal-error")
 
 # Labels meaning "the sidecar recorded a terminal outcome that the controller has
 # not yet written back into dag.json, and which WILL clear on its own" — a DONE
 # slice awaiting its serial merge, a SPLIT awaiting child ingestion. Neither is
 # runnable, but both are treated as landed by the wave projection so dependents
diff --git a/plugins/spec-loop/scripts/run_metrics.py b/plugins/spec-loop/scripts/run_metrics.py
index 5202194..737db91 100644
--- a/plugins/spec-loop/scripts/run_metrics.py
+++ b/plugins/spec-loop/scripts/run_metrics.py
@@ -121,10 +121,11 @@ ESCALATION_TRIGGERS = (
     "material-assumption",
     "review-block",
     "council-objection",
     "quality-gate-block",
     "budget-exhausted",
+    "internal-error",
 )
 REVERSIBILITY_BUCKETS = ("trivial", "moderate", "high", "n/a")
 GATE_RESULTS = ("PASS", "FAIL", "SKIPPED")
 # The sidecar's review block — the numerically-precise review channel.
 REVIEW_COUNTER_KEYS = ("confirmed", "refuted", "evidence_failed", "fix_rounds")
diff --git a/plugins/spec-loop/scripts/run_state.py b/plugins/spec-loop/scripts/run_state.py
index 1689f79..e44150e 100644
--- a/plugins/spec-loop/scripts/run_state.py
+++ b/plugins/spec-loop/scripts/run_state.py
@@ -63,11 +63,12 @@ import tempfile
 SCHEMA_VERSION = 2
 SLICE_RESULT_STATUSES = ("DONE", "SPLIT", "ESCALATED", "FAILED")
 QUALITY_STATUSES = ("PASS", "FAIL", "SKIPPED")
 VERDICTS = ("ENDORSE", "ENDORSE_WITH_CONCERNS", "OBJECT", "SKIPPED")
 ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
-                       "council-objection", "quality-gate-block", "budget-exhausted")
+                       "council-objection", "quality-gate-block", "budget-exhausted",
+                       "internal-error")
 ESCALATION_STATUSES = ("OPEN", "ANSWERED")
 RISK_TIERS = (1, 2, 3)
 # Matches dag.py: references/split-ingestion.md calls a one-child split a
 # malformed proposal, so a SPLIT sidecar proposing one is refused here too.
 MIN_SPLIT_CHILDREN = 2
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index cafdfb2..01e612c 100644
--- a/plugins/spec-loop/scripts/slice_wave_contract_base.py
+++ b/plugins/spec-loop/scripts/slice_wave_contract_base.py
@@ -2,12 +2,13 @@
 
 The wave workflow is JavaScript and is not run by any lane of this repo's
 suite: it is resolved at runtime from the installed plugin cache. Its
 correctness has therefore rested entirely on review, and this run paid for
 that twice - an unguarded optional-field read aborted a whole wave and was
-mislabelled as a budget escalation. The two ``test_slice_wave_contract*.py``
-modules that import this one are the cheapest honest coverage available:
+mislabelled as a budget escalation (both the read and the mislabelling are now
+pinned here). The two ``test_slice_wave_contract*.py`` modules that import this
+one are the cheapest honest coverage available:
 they parse the file with node (a real parse, not a substring) and pin the
 handful of source facts whose loss is a known, observed outage - the
 null-guards on TASK_RESULT.commits and its sibling optional arrays, the
 type-safe read of CTX.scope_ceiling, the answer-injection sites, and the
 record-only isolation of the over-scope flag from the four control-flow
@@ -107,10 +108,24 @@ CONCERN_MARKER = "over_scope: !!(v.over_scope && v.over_scope.flag === true)"
 DEFERRED_ARRAY = (
     "deferred: concerns.filter(c => c.disposition_hint === 'defer')"
     ".map(c => c.text)")
 STATE_DEFERRED_INIT = "deferred: []"
 STATE_DEFERRED = "state.deferred"
+STATE_STAGE_INIT = "stage: null"
+STAGE_ASSIGNMENT = "state.stage = role"
+DISPATCH_GUARD_CALL = "guard(slice, state)"
+CRASH_STAGE_CONTEXT = "Last stage/role dispatched before the failure: ${stage}"
+CRASH_STAGE_PRECISION = "the most recent dispatch, not a per-throw stage"
+CRASH_STAGE_OVERCLAIM = "in flight"
+CRASH_TRIGGER = "esc(slice, 'internal-error',"
+CRASH_STAGE_FALLBACK = "const stage = state.stage || 'before any agent was dispatched'"
+CRASH_CLASSIFIED_PASSTHROUGH = "if (e && e.escRecord) return escalated(slice, state, e.escRecord)"
+CRASH_OPTION_RETRY = "label: 'Retry this slice'"
+CRASH_OPTION_SKIP = "label: 'Skip this slice'"
+CRASH_OPTION_STOP = "label: 'Stop the run'"
+GUARD_BUDGET_TRIGGER = "esc(slice, 'budget-exhausted',"
+SLICE_LOST_RECORD = "esc(A.slices[i], 'internal-error', 'slice lost',"
 STAGE_CRITIQUE_START = "async function stageCritique(slice, state, plan) {"
 STAGE_CRITIQUE_END = "// Stage T helpers"
 SPLIT_RETURN = "if (splitRec) return { stop: doneResult(slice, state, 'SPLIT'"
 RECORD_DEFERRALS_FN = "function recordDeferrals(slice, state, concerns) {"
 RECORD_DEFERRALS_CALL = "recordDeferrals(slice, state, concerns)"
diff --git a/plugins/spec-loop/scripts/test_dashboard_server.py b/plugins/spec-loop/scripts/test_dashboard_server.py
index 3452ed0..6c68e39 100644
--- a/plugins/spec-loop/scripts/test_dashboard_server.py
+++ b/plugins/spec-loop/scripts/test_dashboard_server.py
@@ -1242,13 +1242,24 @@ class EscalationSourceTests(unittest.TestCase):
         # empty rather than invented. The trigger, though, is encoded in the id
         # itself by contract, so that much is real.
         self.assertEqual(e["title"], "")
         self.assertEqual(e["trigger"], "budget-exhausted")
 
+    def test_internal_error_parses_out_of_an_escalation_id(self):
+        # The id's second segment is the trigger by contract, so a crash id
+        # must resolve — _trigger_from_id gates on ESCALATION_TRIGGERS.
+        def build(run_dir):
+            write_dag_v2(run_dir, [slice_obj("s1")])
+            write_events(run_dir, [
+                ("s1", "escalation-opened", {"id": "s1:internal-error"}),
+            ])
+        run = self.scan(build)
+        self.assertEqual(run["escalations"][0]["trigger"], "internal-error")
+
     def test_a_malformed_id_yields_no_made_up_trigger(self):
         # The id's second segment is only accepted when it is one of the
-        # contract's six triggers, so a hand-edited id cannot surface garbage.
+        # contract's known triggers, so a hand-edited id cannot surface garbage.
         def build(run_dir):
             write_dag_v2(run_dir, [slice_obj("s1")])
             write_events(run_dir, [
                 ("s1", "escalation-opened", {"id": "s1:not-a-real-trigger"}),
                 ("s2", "escalation-opened", {"id": "noseparator"}),
@@ -1263,10 +1274,24 @@ class EscalationSourceTests(unittest.TestCase):
                           escalations=[escalation_record("s1:review-block",
                                                          trigger="made-up")])
         run = self.scan(build)
         self.assertEqual(run["escalations"][0]["trigger"], "review-block")
 
+    def test_a_record_trigger_of_internal_error_is_kept_as_itself(self):
+        # The record path, not the id path: _enum_or_none nulls any trigger
+        # outside ESCALATION_TRIGGERS, so a crash record must be listed there
+        # or every crash escalation renders with no trigger at all. The id is
+        # deliberately trigger-less here to isolate _enum_or_none from the
+        # _trigger_from_id fallback.
+        def build(run_dir):
+            write_dag_v2(run_dir, [slice_obj("s1")])
+            write_sidecar(run_dir, "s1", status="ESCALATED", escalations=[
+                escalation_record("s1", trigger="internal-error"),
+            ])
+        run = self.scan(build)
+        self.assertEqual(run["escalations"][0]["trigger"], "internal-error")
+
     def test_nested_and_named_payload_id_forms_are_both_accepted(self):
         # v2 pins the EscalationRecord but not how an event wraps it.
         def build(run_dir):
             write_dag_v2(run_dir, [slice_obj("s1")])
             write_events(run_dir, [
diff --git a/plugins/spec-loop/scripts/test_run_metrics.py b/plugins/spec-loop/scripts/test_run_metrics.py
index 72c9657..736afbc 100644
--- a/plugins/spec-loop/scripts/test_run_metrics.py
+++ b/plugins/spec-loop/scripts/test_run_metrics.py
@@ -452,10 +452,27 @@ class EscalationPairingTests(unittest.TestCase):
             json.dumps(ev("2026-07-30T10:00:00Z", "b", "escalation-opened",
                           id="b:x")))
         self.assertEqual([r["trigger"] for r in result["records"]],
                          ["other", None])
 
+    def test_internal_error_buckets_as_itself_not_other(self):
+        # _normalize_trigger degrades unknowns to "other"; a crash must keep
+        # its own by_trigger key so mislabelled resource limits stay visible.
+        opened = ev(
+            "2026-07-30T10:00:00Z", "a", "escalation-opened",
+            id="a:internal-error", trigger="internal-error")
+        result = self.records_for(json.dumps(opened))
+        triggers = [r["trigger"] for r in result["records"]]
+        self.assertEqual(triggers, ["internal-error"])
+
+    def test_internal_error_is_substring_safe_against_every_other_trigger(self):
+        # run_metrics.py:1692 (_legacy_match_triggers) matches by containment.
+        others = [t for t in rm.ESCALATION_TRIGGERS if t != "internal-error"]
+        for other in others:
+            self.assertNotIn(other, "internal-error")
+            self.assertNotIn("internal-error", other)
+
     def test_union_counts_a_duplicated_record_once(self):
         metrics = compute_for(v2_files(), run_id="20260730-v2")
         self.assertEqual(metrics["safety"]["escalations"]["total"], 2)
         self.assertEqual(metrics["safety"]["escalations"]["basis"],
                          rm.BASIS_BOTH)
diff --git a/plugins/spec-loop/scripts/test_run_state.py b/plugins/spec-loop/scripts/test_run_state.py
index 2f8c3a8..a6aaff6 100644
--- a/plugins/spec-loop/scripts/test_run_state.py
+++ b/plugins/spec-loop/scripts/test_run_state.py
@@ -194,10 +194,21 @@ class TestValidateSidecar(unittest.TestCase):
 
     def test_escalation_trigger_enum(self):
         body = sidecar("ESCALATED", escalations=[escalation(trigger="vibes")])
         self.assertMentions(body, "trigger")
 
+    def test_escalation_trigger_accepts_internal_error(self):
+        # A machine failure is a first-class trigger: run_state.py:204 is
+        # fail-closed, so an unlisted value would falsely fail the sidecar.
+        body = sidecar("ESCALATED", escalations=[
+            escalation(id="s1:internal-error", trigger="internal-error")])
+        self.assertValid(body)
+
+    def test_escalation_trigger_still_rejects_a_bogus_value(self):
+        body = sidecar("ESCALATED", escalations=[escalation(trigger="kaboom")])
+        self.assertMentions(body, "trigger")
+
     def test_escalation_needs_options(self):
         body = sidecar("ESCALATED", escalations=[escalation(options=[])])
         self.assertMentions(body, "options")
 
     def test_escalation_option_needs_a_label(self):
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract.py b/plugins/spec-loop/scripts/test_slice_wave_contract.py
index 488397e..be494cd 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract.py
@@ -1,8 +1,9 @@
 #!/usr/bin/env python3
 """Contract checks: guarded task-result reads, quality-gate-block answer
-injection, and the record-only `over_scope` critique field.
+injection, the record-only `over_scope` critique field, and the `internal-error`
+classification of machine failures.
 
 See `slice_wave_contract_base.py` for the module-wide rationale (why this
 is source-text assertion, why snippets are named constants, and the two
 known-and-deliberately-unguarded instances this module does NOT claim to
 cover). `test_slice_wave_contract_scope.py` is this module's sibling,
@@ -21,19 +22,23 @@ import subprocess
 import tempfile
 import unittest
 
 from slice_wave_contract_base import (
     ANSWER_CONTEXT_END, ANSWER_CONTEXT_START, ANSWERABLE_TRIGGERS, CLEAN,
-    COUNCIL_VERDICT_EVENT, CRITIQUE_REQUIRED, CRITIQUE_ROLLUP,
+    COUNCIL_VERDICT_EVENT, CRASH_CLASSIFIED_PASSTHROUGH, CRASH_OPTION_RETRY,
+    CRASH_OPTION_SKIP, CRASH_OPTION_STOP, CRASH_STAGE_CONTEXT,
+    CRASH_STAGE_FALLBACK, CRASH_STAGE_OVERCLAIM, CRASH_STAGE_PRECISION,
+    CRASH_TRIGGER, CRITIQUE_REQUIRED, CRITIQUE_ROLLUP, DISPATCH_GUARD_CALL,
     FAIL_CLOSED_DEFAULT, FINDING_CATEGORIES, FLAGGED, GATE_ANSWER,
-    GATE_ANSWER_CONTEXT, GUARDED_BASE, GUARDED_CONCERNS, GUARDED_DEVIATIONS,
-    GUARDED_HEAD, GUARDED_LOCAL, GUARDED_TOUCHED, HELPER_END,
-    NO_COMMITS_ESCALATION, OBJECTION_SELECTION, OVER_SCOPE_DEFAULT,
+    GATE_ANSWER_CONTEXT, GUARD_BUDGET_TRIGGER, GUARDED_BASE, GUARDED_CONCERNS,
+    GUARDED_DEVIATIONS, GUARDED_HEAD, GUARDED_LOCAL, GUARDED_TOUCHED,
+    HELPER_END, NO_COMMITS_ESCALATION, OBJECTION_SELECTION, OVER_SCOPE_DEFAULT,
     OVER_SCOPE_SCHEMA, REPLAN_VETO, SCOPE_DRIVER, SCOPE_HELPER, SCOPE_LOCAL,
-    SCOPE_REASON_KEPT, SCOPE_SPREAD, SIDECAR_SCOPE_ATTACH,
-    SPLIT_SUPPRESSION, TASK_LOOP_END, TASK_LOOP_START, TASK_RESULT_REQUIRED,
-    WorkflowSourceTestCase, wrapped_source,
+    SCOPE_REASON_KEPT, SCOPE_SPREAD, SIDECAR_SCOPE_ATTACH, SLICE_LOST_RECORD,
+    SPLIT_SUPPRESSION, STAGE_ASSIGNMENT, STATE_STAGE_INIT, TASK_LOOP_END,
+    TASK_LOOP_START, TASK_RESULT_REQUIRED, WorkflowSourceTestCase,
+    wrapped_source,
 )
 
 
 class TestTheFileStillParses(unittest.TestCase):
     def test_node_parses_the_wrapped_workflow_source(self):
@@ -55,14 +60,14 @@ class TestTheFileStillParses(unittest.TestCase):
 
 
 class TestOptionalTaskResultReadsAreGuarded(WorkflowSourceTestCase):
     """Regression, run 20260825-scope-ceiling wave 2: TASK_RESULT does not
     require `commits`, so a task that legitimately committed nothing returned
-    DONE with the key absent. `state.commits.head = r.commits.head` threw a
-    TypeError, the catch-all re-labelled it 'wave interrupted' /
-    budget-exhausted, and a wave whose five tasks had all committed was
-    reported as a resource failure."""
+    DONE with the key absent. An unguarded `state.commits.head = r.commits.head`
+    threw a TypeError, which is now correctly classified as 'internal-error' by
+    the crash handler. Before crash classification, such errors were mislabeled
+    as budget-exhausted, causing misdirected diagnosis."""
 
     def task_loop(self):
         """The Stage-T task-result-handling region (runTask() and its small
         helpers, through stageTasks()'s loop), where every task-result read
         happens."""
@@ -143,12 +148,13 @@ class TestOverScopeIsRecordOnly(WorkflowSourceTestCase):
         required = self.line_containing(CRITIQUE_REQUIRED)
         self.assertNotIn("over_scope", required)
 
     def test_the_fail_closed_default_supplies_the_field(self):
         # Extended BEFORE any read exists: an unguarded read of a missing
-        # optional field throws, is swallowed by the catch-all, and is
-        # mislabelled as a budget escalation - the defect that killed wave 2.
+        # optional field throws, is swallowed by the catch-all, and is now
+        # correctly classified as 'internal-error' - before crash classification,
+        # such errors were mislabeled as budget escalation, which killed wave 2.
         default = self.line_containing(FAIL_CLOSED_DEFAULT)
         self.assertIn(OVER_SCOPE_DEFAULT, default)
 
     def test_the_read_goes_through_the_pure_helper_not_a_bare_field_access(self):
         helper = self.between(SCOPE_HELPER, HELPER_END)
@@ -251,7 +257,96 @@ class TestScopeRecordBehavesAndNotJustExists(WorkflowSourceTestCase):
         # would reach run_state.py as an absent key instead of an explicit null.
         got = self.scope_record([[{"over_scope": {"flag": True}}]])
         self.assertEqual(got, [{"flag": True, "reason": None}])
 
 
+class TestTheCrashRecordNamesTheLastDispatchedStage(WorkflowSourceTestCase):
+    """A crash record carrying only an exception string sent run
+    20260825-scope-ceiling's controller looking for a budget problem. The
+    cheapest honest signal is the LAST DISPATCHED role - state.stage is
+    never cleared and dispatch() may fan out via parallel(), so it is not
+    a per-throw stage and the record must not claim to be one."""
+
+    def test_slice_state_initialises_a_stage_field(self):
+        init = self.between("function initSliceState(slice) {", "function doneResult(")
+        self.assertIn(STATE_STAGE_INIT, init)
+
+    def test_dispatch_records_the_role_only_after_the_guards_pass(self):
+        # A cap or token-floor rejection must not advance state.stage to a
+        # role that never dispatched, so the assignment follows guard().
+        fn = self.between(
+            "async function dispatch(slice, state, role, prompt, opts) {",
+            "// ── The slice pipeline")
+        self.assertIn(STAGE_ASSIGNMENT, fn)
+        self.assertLess(fn.index(DISPATCH_GUARD_CALL), fn.index(STAGE_ASSIGNMENT))
+
+
+class TestCrashesAreClassifiedAsInternalError(WorkflowSourceTestCase):
+    """Regression, run 20260825-scope-ceiling: the catch-all relabelled every
+    unclassified JS exception as `budget-exhausted` 'wave interrupted', so a
+    TypeError read as a resource limit and the controller spent ~85 and ~76
+    minutes diagnosing in the wrong direction (the HUMAN answered both in
+    ~1 min - the cost was misdirected diagnosis, not human waiting). The
+    catch-all now says machine failure, names the last dispatched stage, and offers
+    controller actions instead of 'raise budget/caps'."""
+
+    def crash_fallback(self):
+        return self.between(
+            "function runSliceError(slice, state, e) {",
+            "async function runSlice(slice) {")
+
+    def test_the_catch_all_emits_internal_error_not_budget_exhausted(self):
+        fallback = self.crash_fallback()
+        self.assertIn(CRASH_TRIGGER, fallback)
+        self.assertNotIn(GUARD_BUDGET_TRIGGER, fallback)
+
+    def test_a_classified_throw_still_passes_through_unchanged(self):
+        # The two structural guards throw {escRecord} with their own
+        # budget-exhausted record; reclassifying those would be a regression.
+        self.assertIn(CRASH_CLASSIFIED_PASSTHROUGH, self.crash_fallback())
+
+    def test_the_crash_record_names_the_last_dispatched_stage_without_overclaiming(self):
+        fallback = self.crash_fallback()
+        self.assertIn(CRASH_STAGE_FALLBACK, fallback)
+        self.assertIn(CRASH_STAGE_CONTEXT, fallback)
+        self.assertIn(CRASH_STAGE_PRECISION, fallback)
+        self.assertNotIn(CRASH_STAGE_OVERCLAIM, fallback)
+
+    def test_the_crash_record_carries_the_real_exception_text(self):
+        self.assertIn("String((e && e.message) || e)", self.crash_fallback())
+
+    def test_the_options_are_controller_actions_not_resource_requests(self):
+        fallback = self.crash_fallback()
+        self.assertIn(CRASH_OPTION_RETRY, fallback)
+        self.assertIn(CRASH_OPTION_SKIP, fallback)
+        self.assertIn(CRASH_OPTION_STOP, fallback)
+        self.assertNotIn("Raise budget/caps", fallback)
+
+    def test_the_structural_guards_keep_their_budget_exhausted_wording(self):
+        guard = self.between(
+            "function guard(slice, state) {", "async function dispatch(")
+        self.assertIn("agent cap reached", guard)
+        self.assertIn("token budget exhausted", guard)
+        self.assertEqual(guard.count(GUARD_BUDGET_TRIGGER), 2)
+
+    def test_internal_error_is_not_injected_into_any_prompt(self):
+        # Mirror of test_budget_exhausted_is_still_not_injected_anywhere: a
+        # crash answer is a controller action (retry / skip / stop), so there
+        # is nothing for an agent prompt to apply. It is deliberately NOT in
+        # ANSWERABLE_TRIGGERS.
+        self.assertNotIn("answerFor(slice, 'internal-error')", self.src)
+        self.assertNotIn("internal-error", str(ANSWERABLE_TRIGGERS))
+
+    def test_a_lost_slice_is_an_internal_error_too(self):
+        # parallel() resolved the thunk to null: the slice died with no result
+        # at all, outside runSlice's try/catch. Same one classification, per
+        # the run's human-decided single-value constraint; the honest 'slice
+        # lost' title and its own question are kept.
+        wave_entry = self.between(
+            "const results = await parallel(", "log(`wave ")
+        self.assertIn(SLICE_LOST_RECORD, wave_entry)
+        self.assertIn("Re-run the wave to retry this slice?", wave_entry)
+        self.assertNotIn("'budget-exhausted'", wave_entry)
+
+
 if __name__ == "__main__":  # pragma: no cover
     unittest.main()
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index bcc2293..4c4e408 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -67,18 +67,21 @@ Do not act. Return an `EscalationRecord` and let the controller batch it:
    to avoid this.
 
 When uncertain whether something is "material": if a reasonable reviewer could reject the slice
 over it, it is material → surface it.
 
-The enum lives in `slice-wave.workflow.js` (`ESCALATION.trigger`). Two things that are
+The enum lives in `slice-wave.workflow.js` (`ESCALATION.trigger`). Three things that are
 deliberately NOT judgment triggers, and must never be turned into one: `budget-exhausted` (the
-workflow's guard emits it when a structural cap is hit — agent cap, stage token floor, lost
-slice; it asks for a resource, not a decision) and the council's **over-scope flag**
-(`critique.over_scope.flag`). The flag is a record: it is carried into the `council-verdict`
-payload and the slice sidecar with its reason, and it raises no escalation, changes no verdict,
-suppresses no split, and blocks nothing. There are exactly five triggers; an over-scope flag is
-not a sixth.
+workflow's guard emits it when a structural cap is hit — agent cap, stage token floor; it asks for a
+resource, not a decision), `internal-error` (an unhandled exception aborted a slice, or a slice
+returned no result at all; the record names the last stage/role dispatched before the failure — the
+loop records the most recent dispatch, not a per-throw stage — plus the real exception — it reports
+a machine failure and asks the controller to retry, skip, or stop, so it is never answerable by
+re-dispatching an agent prompt), and the council's **over-scope flag** (`critique.over_scope.flag`).
+The flag is a record: it is carried into the `council-verdict` payload and the slice sidecar with
+its reason, and it raises no escalation, changes no verdict, suppresses no split, and blocks
+nothing. There are exactly five JUDGMENT triggers; an over-scope flag is not a sixth.
 
 ### Precedent check (before returning any SURFACE escalation)
 
 Prior runs' human answers are settled decisions — check them before asking a question the human
 may have already answered. Search prior runs (excluding this one): answered escalation records
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index 73c9c99..a6ded0a 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -35,11 +35,11 @@ const BUDGET_STAGE_FLOOR = 60_000 // skip-and-escalate below this remaining budg
 // ── Schemas ──────────────────────────────────────────────────────────────────
 
 const ESCALATION = {
   type: 'object', additionalProperties: false,
   properties: {
-    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'budget-exhausted'] },
+    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'budget-exhausted', 'internal-error'] },
     title: { type: 'string' }, context: { type: 'string' }, question: { type: 'string' },
     options: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { label: { type: 'string' }, detail: { type: 'string' }, recommended: { type: 'boolean' } }, required: ['label', 'detail'] } },
   },
   required: ['trigger', 'title', 'context', 'question', 'options'],
 }
@@ -427,10 +427,14 @@ function guard(slice, state) {
     throw { escRecord: esc(slice, 'budget-exhausted', 'token budget exhausted', `Wave budget remaining ${Math.round(budget.remaining() / 1000)}k is below the ${BUDGET_STAGE_FLOOR / 1000}k stage floor.`, 'Raise the budget and resume, accept committed work as-is, or drop the slice?', []) }
 }
 
 async function dispatch(slice, state, role, prompt, opts) {
   guard(slice, state)
+  // Last dispatch STARTED, not a per-throw stage: never cleared, and
+  // concurrent fan-outs overwrite each other. After guard() so a cap or
+  // token-floor rejection cannot advance it to a role that never ran.
+  state.stage = role
   state.agentsUsed++
   const r = await agent(prompt, { ...opts, label: `${slice.id}:${role}`, phase: `wave ${A.wave_index}` })
   state.events.push({ scope: slice.id, type: 'agent-dispatch', payload: { role, model: opts.model || 'inherit', effort: opts.effort || null, agent_type: opts.agentType || null } })
   return r // null on user-skip/terminal error — callers fail closed
 }
@@ -447,11 +451,11 @@ async function dispatch(slice, state, role, prompt, opts) {
 
 const TASK_LANE = { transcribe: { model: 'haiku', effort: 'low' }, standard: { model: 'sonnet', effort: 'medium' }, judgment: { model: 'inherit', effort: 'high' } }
 
 function initSliceState(slice) {
   return {
-    agentsUsed: 0, events: [], escalations: [],
+    agentsUsed: 0, stage: null, events: [], escalations: [],
     review_tier: Math.max(slice.risk_tier, CTX.thorough ? Math.min(slice.risk_tier + 1, 3) : slice.risk_tier),
     critique: { verdict: 'SKIPPED', concerns: 0 },
     commits: { base: slice.base_sha, head: null },
     tasksCompleted: 0, implConcerns: [], deferred: [],
     review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
@@ -631,17 +635,17 @@ async function runTask(slice, state, plan, task) {
   if (taskNeedsRetry(r))
     return { stop: escalated(slice, state, esc(slice, 'ambiguity', `task ${task.id} blocked`, taskBlockReason(r), `Task "${task.title}" cannot proceed. How should it resolve?`, [])) }
   state.tasksCompleted++
   // TASK_RESULT requires only status/touched_files/concerns/deviations, so a
   // task that legitimately changed nothing returns DONE with `commits`
-  // absent. Reading it unguarded threw a TypeError that the catch-all below
-  // re-labelled as a budget-exhausted 'wave interrupted' — run
-  // 20260825-scope-ceiling lost a wave to it after all five tasks had
-  // already committed. Guarded the way the fix and debug-fix sites already
-  // guard the identical access; `head` keeps its previous value, so a slice
-  // where NO task committed still leaves it null and falls into the 'plan
-  // produced no commits' escalation below.
+  // absent. Reading it unguarded threw a TypeError that would now be
+  // classified as an 'internal-error' by the catch-all; run 20260825-scope-
+  // ceiling lost a wave to this defect before crash classification was added.
+  // Guarded the way the fix and debug-fix sites already guard the identical
+  // access; `head` keeps its previous value, so a slice where NO task
+  // committed still leaves it null and falls into the 'plan produced no commits'
+  // escalation below.
   mergeTaskCommits(state, r)
   state.implConcerns.push(...(r.concerns || []), ...(r.deviations || []).map(d => `deviation: ${d}`))
   return { touched: r.touched_files || [] }
 }
 
@@ -849,13 +853,30 @@ async function runStages(slice, state) {
 
   await maybePolish(slice, state)
   return stageVerify(slice, state, plan)
 }
 
+// An unclassified throw is a MACHINE failure, not a resource limit and not a
+// judgment call: the two structural guards above throw {escRecord} with their
+// own budget-exhausted record, so anything reaching the fallback is a bug in
+// the loop or in an agent contract. It is reported as such, naming the LAST
+// DISPATCHED stage and the real exception, because run 20260825-scope-ceiling
+// showed the cost of a mislabelled crash is misdirected DIAGNOSIS. state.stage
+// is the most recent dispatch, not a per-throw stage (it is never cleared, and
+// concurrent fan-outs overwrite it), so the record says "after", not "in", and
+// says so explicitly. Retry of the crashed stage is deliberately a
+// human/controller decision, not automatic.
 function runSliceError(slice, state, e) {
   if (e && e.escRecord) return escalated(slice, state, e.escRecord)
-  return escalated(slice, state, esc(slice, 'budget-exhausted', 'wave interrupted', String((e && e.message) || e), 'The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?', []))
+  const stage = state.stage || 'before any agent was dispatched'
+  return escalated(slice, state, esc(slice, 'internal-error',
+    `slice crashed after ${stage}`,
+    `An unhandled exception aborted the slice. Last stage/role dispatched before the failure: ${stage}. The loop records the most recent dispatch, not a per-throw stage, so the failure may have happened after that role finished, or in a sibling of a concurrent fan-out — treat it as a starting point, not a culprit. Error: ${String((e && e.message) || e)}. This is a loop or agent-contract bug, NOT a cap or budget limit — ${state.tasksCompleted} task(s) had already completed and any committed work is on the branch.`,
+    'Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?',
+    [{ label: 'Retry this slice', detail: 'Re-dispatch the wave for this slice; committed work on its branch is kept.', recommended: true },
+     { label: 'Skip this slice', detail: 'Leave it ESCALATED and continue with the independent slices.' },
+     { label: 'Stop the run', detail: 'Halt so the exception can be diagnosed before more agents are spent.' }]))
 }
 
 async function runSlice(slice) {
   const state = initSliceState(slice)
   try {
@@ -873,10 +894,10 @@ const out = results.map((r, i) => r || {
   schema_version: 2, id: A.slices[i].id, status: 'ESCALATED', branch: A.slices[i].branch,
   commits: { base: A.slices[i].base_sha, head: null }, risk_tier: A.slices[i].risk_tier,
   review_tier: A.slices[i].risk_tier, critique: { verdict: 'SKIPPED', concerns: 0 },
   tasks_completed: 0, review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
   tests: null, quality: { status: 'SKIPPED', detail: 'slice never ran' },
-  escalations: [esc(A.slices[i], 'budget-exhausted', 'slice lost', 'The slice function returned no result (terminal failure).', 'Re-run the wave to retry this slice?', [])],
+  escalations: [esc(A.slices[i], 'internal-error', 'slice lost', 'The slice function returned no result (terminal failure) — the slice process died with no result at all, outside runSlice\'s try/catch. Not a resource limit.', 'Re-run the wave to retry this slice?', [])],
   agents_used: 0, wave: A.wave_index, events: [],
 })
 log(`wave ${A.wave_index} collected: ${out.map(r => `${r.id}=${r.status}`).join(' ')}`)
 return { run_id: A.run_id, wave_index: A.wave_index, results: out }
diff --git a/scripts/coverage_omit.txt b/scripts/coverage_omit.txt
index 0c4e51a..78268c7 100644
--- a/scripts/coverage_omit.txt
+++ b/scripts/coverage_omit.txt
@@ -33,10 +33,10 @@ scripts/dashboard_server.py:1645-1646    # __main__ entry shim (if __name__/sys.
 scripts/knowledge_graph.py:1211-1212     # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/pr_resolver.py:488-489           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/quality_gate.py:1118-1119        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/release.py:194-195               # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/review_package.py:131-132        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/run_metrics.py:2174-2175         # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/run_state.py:1103-1104           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/run_metrics.py:2175-2176         # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/run_state.py:1104-1105           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/spec_loop_guard.py:250-251       # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/validate_marketplace.py:417-418  # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/worktrees.py:385-386             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
