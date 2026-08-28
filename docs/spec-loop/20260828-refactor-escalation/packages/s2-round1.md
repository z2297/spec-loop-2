# Review package: d67cff6e255fc363e93cea410e0d7bc2cff1aae6..4d1a03d  (context: -U5)

## Commits
4d1a03d feat(spec-loop): make refactor-scope answerable from the plan prompt
f522cda feat(spec-loop): add refactor-scope to the escalation trigger enum

## Files changed
 plugins/spec-loop/agents/slice-worker-fallback.md           |  8 ++++++--
 plugins/spec-loop/references/run-state-v2.md                |  9 ++++++++-
 plugins/spec-loop/scripts/dashboard_server.py               |  2 +-
 plugins/spec-loop/scripts/run_metrics.py                    |  1 +
 plugins/spec-loop/scripts/run_state.py                      |  4 ++--
 plugins/spec-loop/scripts/slice_wave_contract_base.py       | 10 +++++-----
 plugins/spec-loop/scripts/test_run_state.py                 | 11 +++++++++++
 plugins/spec-loop/scripts/test_slice_wave_contract_crash.py |  4 +++-
 plugins/spec-loop/workflows/slice-wave.workflow.js          | 10 ++++++++--
 9 files changed, 45 insertions(+), 14 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/agents/slice-worker-fallback.md": [
[
155,
155
],
[
157,
158
],
[
174,
176
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
107,
107
],
[
131,
137
]
],
"plugins/spec-loop/scripts/dashboard_server.py": [
[
150,
150
]
],
"plugins/spec-loop/scripts/run_metrics.py": [
[
125,
125
]
],
"plugins/spec-loop/scripts/run_state.py": [
[
74,
75
]
],
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
101,
101
],
[
114,
116
],
[
118,
118
]
],
"plugins/spec-loop/scripts/test_run_state.py": [
[
221,
231
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_crash.py": [
[
279,
281
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
50,
50
],
[
351,
356
],
[
364,
364
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/agents/slice-worker-fallback.md b/plugins/spec-loop/agents/slice-worker-fallback.md
index 706fd00..e07b88e 100644
--- a/plugins/spec-loop/agents/slice-worker-fallback.md
+++ b/plugins/spec-loop/agents/slice-worker-fallback.md
@@ -150,13 +150,14 @@ trusts the sidecar over anything you say, and an invalid one makes this slice un
 regardless of how the work went.
 
 ## Escalations
 
 Every escalation is an EscalationRecord in `escalations[]`: stable id `<slice-id>:<trigger>`,
-plus `:<round>` from the second round of that trigger in that slice onward, one of the seven
+plus `:<round>` from the second round of that trigger in that slice onward, one of the eight
 triggers (`ambiguity`, `material-assumption`, `review-block`,
-`council-objection`, `quality-gate-block`, `budget-exhausted`, `internal-error`), the context,
+`council-objection`, `quality-gate-block`, `refactor-scope`, `budget-exhausted`,
+`internal-error`), the context,
 the precise question, options with one marked `recommended`, and `if_unanswered`.
 Proceed-and-log stays the default — surface only genuine ambiguity or a material assumption
 touching behavior, public contracts, persisted data, security, or an external integration. A
 slice with any open escalation returns `ESCALATED`. `budget-exhausted` is only for the tier
 agent cap or the per-stage token floor (see Loop bounds), never for a spent loop bound.
@@ -168,10 +169,13 @@ identically; `ambiguity` is answerable and `internal-error` deliberately is not,
 mislabelling one costs the human the ability to answer it. An `internal-error` context
 carries the real error text and names the stage/role you were actually running when it
 aborted: you drive every stage serially, so unlike the workflow you DO know which one it was
 — say it. Hedge only for a failure inside step 4's concurrent review ∥ quality-gate message,
 where either dispatch may be the one that died; there, name both and say which is unclear.
+`refactor-scope` is raised only by the workflow itself at plan time, when the plan's own
+declared refactor-to-feature ratio crosses the configured threshold; you never mint one, and
+you never use it for a refactor you merely think is large.
 
 ## Return
 
 Statuses: `DONE` · `SPLIT` · `ESCALATED` · `FAILED`. Return a summary of **≤15 lines** —
 status, branch, `base..head`, critique verdict, tasks completed, review outcome (confirmed /
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 7cbad95..ae84e20 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -102,11 +102,11 @@ prose about the slice.
                                 // Stable across resumes: the round counts the answers
                                 // already recorded for the slice+trigger, so the same
                                 // answers map reproduces the same id. Answers are keyed
                                 // by this id verbatim; latestAnswer reads the newest
                                 // answered round back into the resumed prompts.
-  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | budget-exhausted | internal-error",
+  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | refactor-scope | budget-exhausted | internal-error",
   "title": "<short title>",
   "context": "<what the loop was doing and why it cannot decide>",
   "question": "<the precise question>",
   "options": [{ "label": "...", "detail": "...", "recommended": true }],
   "if_unanswered": "pause this slice; continue all independent slices",
@@ -126,10 +126,17 @@ at all — either of which may itself have a host- or agent-layer cause (e.g. a
 call on a hard token or rate limit) that the record does not pretend to rule out. It is not
 a catch-all for every other failure: a failure the loop can name keeps the trigger that
 names it, so a spent replan stays `council-objection` and a blocked task — including a task
 dispatch that returned no result — stays `ambiguity`. Neither is a judgment trigger.
 
+`refactor-scope` is the one trigger the workflow raises on its own arithmetic rather than on
+an agent's judgment: at plan time, when the plan's declared refactor-to-feature ratio exceeds
+the configured threshold. It IS a judgment trigger — its answer is injected back into the
+plan prompt — because the only useful answer is a human trade-off between shipping the
+refactor with the feature and splitting it out. An absent or unmeasured ratio never raises
+it: not-measured proceeds and is recorded as null.
+
 ## `events.jsonl` — the machine channel
 
 Append-only, one JSON object per line, written only by the controller
 (`run_state.py` appends; workflow returns carry the payloads; the controller
 stamps `ts` — workflow scripts have no clock).
diff --git a/plugins/spec-loop/scripts/dashboard_server.py b/plugins/spec-loop/scripts/dashboard_server.py
index ec8e994..5f54cd7 100644
--- a/plugins/spec-loop/scripts/dashboard_server.py
+++ b/plugins/spec-loop/scripts/dashboard_server.py
@@ -145,11 +145,11 @@ RECORDED_WAVE_STATUSES = ("dispatched", "collected")
 PROJECTED = "projected"
 
 # The EscalationRecord triggers (run-state-v2.md). Used both to validate a
 # record's own ``trigger`` field and to read the trigger an escalation id encodes.
 ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
-                       "council-objection", "quality-gate-block",
+                       "council-objection", "quality-gate-block", "refactor-scope",
                        "budget-exhausted", "internal-error")
 
 # Labels meaning "the sidecar recorded a terminal outcome that the controller has
 # not yet written back into dag.json, and which WILL clear on its own" — a DONE
 # slice awaiting its serial merge, a SPLIT awaiting child ingestion. Neither is
diff --git a/plugins/spec-loop/scripts/run_metrics.py b/plugins/spec-loop/scripts/run_metrics.py
index b4d17e3..4dc8d04 100644
--- a/plugins/spec-loop/scripts/run_metrics.py
+++ b/plugins/spec-loop/scripts/run_metrics.py
@@ -120,10 +120,11 @@ ESCALATION_TRIGGERS = (
     "ambiguity",
     "material-assumption",
     "review-block",
     "council-objection",
     "quality-gate-block",
+    "refactor-scope",
     "budget-exhausted",
     "internal-error",
 )
 REVERSIBILITY_BUCKETS = ("trivial", "moderate", "high", "n/a")
 GATE_RESULTS = ("PASS", "FAIL", "SKIPPED")
diff --git a/plugins/spec-loop/scripts/run_state.py b/plugins/spec-loop/scripts/run_state.py
index 5db0311..6352ec4 100644
--- a/plugins/spec-loop/scripts/run_state.py
+++ b/plugins/spec-loop/scripts/run_state.py
@@ -69,12 +69,12 @@ import tempfile
 SCHEMA_VERSION = 2
 SLICE_RESULT_STATUSES = ("DONE", "SPLIT", "ESCALATED", "FAILED")
 QUALITY_STATUSES = ("PASS", "FAIL", "SKIPPED")
 VERDICTS = ("ENDORSE", "ENDORSE_WITH_CONCERNS", "OBJECT", "SKIPPED")
 ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
-                       "council-objection", "quality-gate-block", "budget-exhausted",
-                       "internal-error")
+                       "council-objection", "quality-gate-block", "refactor-scope",
+                       "budget-exhausted", "internal-error")
 ESCALATION_STATUSES = ("OPEN", "ANSWERED")
 RISK_TIERS = (1, 2, 3)
 # Matches dag.py: references/split-ingestion.md calls a one-child split a
 # malformed proposal, so a SPLIT sidecar proposing one is refused here too.
 MIN_SPLIT_CHILDREN = 2
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index 5895b59..6dff36e 100644
--- a/plugins/spec-loop/scripts/slice_wave_contract_base.py
+++ b/plugins/spec-loop/scripts/slice_wave_contract_base.py
@@ -96,11 +96,11 @@ GATE_ANSWER = "answerFor(slice, 'quality-gate-block')"
 GATE_ANSWER_CONTEXT = "answerContext(slice, 'quality-gate-block')"
 ANSWER_CONTEXT_START = "const answerContext = (slice, trigger) => {"
 ANSWER_CONTEXT_END = "\n}\n"
 ANSWERABLE_TRIGGERS = (
     "ambiguity", "material-assumption", "review-block",
-    "council-objection", "quality-gate-block")
+    "council-objection", "quality-gate-block", "refactor-scope")
 CRITIQUE_REQUIRED = "required: ['verdict', 'safety', 'concerns']"
 FAIL_CLOSED_DEFAULT = "unreadable critic verdict (fail closed)"
 OVER_SCOPE_DEFAULT = "over_scope: null"
 OVER_SCOPE_SCHEMA = "over_scope: { type: 'object'"
 CRITIQUE_ROLLUP = "state.critique = { verdict:"
@@ -109,15 +109,15 @@ OBJECTION_SELECTION = "ob: (safety || objections[0])"
 REPLAN_VETO = "if (safety || !ob.fixable_by_replan || state.replanned)"
 FINDING_CATEGORIES = "category: { enum: ["
 # The trigger enum has six homes: this line, the ESCALATION_TRIGGERS tuple in
 # run_state.py, run_metrics.py and dashboard_server.py, and two PROSE
 # enumerations - the fallback agent's escalation section and the run-state
-# contract reference - located by the two locator constants below. Earlier
-# this comment said five and then listed four; the guard that names it now
-# asserts over all six.
+# contract reference - located by the two locator constants below. Earlier this
+# comment said five and then listed four; the guard that names it now asserts
+# over all six homes, and the enum they carry is now eight values wide.
 TRIGGER_ENUM_LINE = "trigger: { enum: ["
-TRIGGER_PROSE_LEAD = "one of the seven triggers ("
+TRIGGER_PROSE_LEAD = "one of the eight triggers ("
 TRIGGER_UNION_PREFIX = '"trigger": "'
 FALLBACK_MD = Path(__file__).resolve().parents[1] / "agents" / "slice-worker-fallback.md"
 RUN_STATE_MD = Path(__file__).resolve().parents[1] / "references" / "run-state-v2.md"
 COUNCIL_VERDICT_EVENT = "type: 'council-verdict'"
 SCOPE_HELPER = "function scopeRecord("
diff --git a/plugins/spec-loop/scripts/test_run_state.py b/plugins/spec-loop/scripts/test_run_state.py
index de179ec..8d5855d 100644
--- a/plugins/spec-loop/scripts/test_run_state.py
+++ b/plugins/spec-loop/scripts/test_run_state.py
@@ -216,10 +216,21 @@ class TestValidateSidecar(unittest.TestCase):
         # unlisted value would falsely fail the sidecar.
         body = sidecar("ESCALATED", escalations=[
             escalation(id="s1:internal-error", trigger="internal-error")])
         self.assertValid(body)
 
+    def test_escalation_trigger_accepts_refactor_scope(self):
+        # The plan-time refactor-scope checkpoint writes a real
+        # EscalationRecord, and validate_escalation runs BEFORE
+        # persist_slice writes anything: a value missing from
+        # ESCALATION_TRIGGERS would cost the slice its sidecar, its
+        # events and its report rather than mislabelling one field.
+        # This drives the membership check, it does not re-list the tuple.
+        body = sidecar("ESCALATED", escalations=[
+            escalation(id="s1:refactor-scope", trigger="refactor-scope")])
+        self.assertValid(body)
+
     def test_escalation_trigger_still_rejects_a_bogus_value(self):
         body = sidecar("ESCALATED", escalations=[escalation(trigger="kaboom")])
         self.assertMentions(body, "trigger")
 
     def test_escalation_needs_options(self):
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
index cb8dd55..d71a3d5 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
@@ -274,11 +274,13 @@ class TestTheTriggerEnumAgreesAcrossAllSixHomes(WorkflowSourceTestCase):
     anything and raises on an unrecognised trigger, so a value missing from one
     tuple costs an affected slice its sidecar, its events and its report - not
     a mislabelled field. A one-home edit would otherwise stay fully green. The
     two prose homes are pinned here too: a doc that lists a stale set of
     triggers is what a worker agent reads before it builds a record, so a
-    drifted enumeration produces exactly that rejected write."""
+    drifted enumeration produces exactly that rejected write. The enum is
+    eight values wide as of the refactor-scope trigger; the six homes and the
+    order-sensitivity of this comparison are unchanged."""
 
     def triggers(self):
         return run_state.ESCALATION_TRIGGERS
 
     def test_the_three_python_tuples_are_identical(self):
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index bca6bc5..6672097 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -45,11 +45,11 @@ const CAP_OVERRIDES = A.agent_cap_overrides || {}
 // ── Schemas ──────────────────────────────────────────────────────────────────
 
 const ESCALATION = {
   type: 'object', additionalProperties: false,
   properties: {
-    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'budget-exhausted', 'internal-error'] },
+    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'refactor-scope', 'budget-exhausted', 'internal-error'] },
     title: { type: 'string' }, context: { type: 'string' }, question: { type: 'string' },
     options: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { label: { type: 'string' }, detail: { type: 'string' }, recommended: { type: 'boolean' } }, required: ['label', 'detail'] } },
   },
   required: ['trigger', 'title', 'context', 'question', 'options'],
 }
@@ -346,18 +346,24 @@ const answerFor = (slice, trigger) => {
 const answerContext = (slice, trigger) => {
   const a = latestAnswer(slice.id, trigger)
   return a ? `\nHUMAN ANSWER on the earlier "${trigger}" escalation, for context only — it does NOT change what you report: the suite result and quality.summary_pass/violations stay verbatim from the real output: ${a}` : ''
 }
 
+// refactor-scope is raised by the plan stage, so its answer is read back HERE and nowhere
+// else: a trigger whose answer never re-enters the prompt of the stage that raised it is
+// structurally unanswerable by re-dispatch and the human's answer is silently discarded
+// (the quality-gate-block outage this file already carries). The planner is an actor, not a
+// transcriber, so this is answerFor (an instruction) rather than answerContext. replanPrompt
+// interpolates planPrompt(slice), so it inherits the read-back and must not repeat the call.
 function planPrompt(slice) {
   return `${packet(slice)}
 
 Plan slice ${slice.id} of run ${A.run_id}: ${slice.goal}
 Named files: ${slice.files.join(', ') || '(none named)'} · Subsystems: ${slice.subsystems.join(', ') || '—'}
 Risk tier: ${slice.risk_tier} · Split depth: ${slice.depth} (split allowed only below depth 2)
 Write the plan to exactly: ${CTX.run_dir}/plans/${slice.id}.md
-Test/build command for verification steps: ${CTX.test_command}${answerFor(slice, 'ambiguity')}${answerFor(slice, 'material-assumption')}`
+Test/build command for verification steps: ${CTX.test_command}${answerFor(slice, 'ambiguity')}${answerFor(slice, 'material-assumption')}${answerFor(slice, 'refactor-scope')}`
 }
 
 function criticPrompt(slice, plan, role) {
   return `${packet(slice)}
