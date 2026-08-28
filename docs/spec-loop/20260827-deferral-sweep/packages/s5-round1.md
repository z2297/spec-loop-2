# Review package: 8518f56aa84d0128b7271210f2dec489aacd8b68..de55460  (context: -U5)

## Commits
de55460 test_slice_wave_contract_crash: keep rendered_crash_context flat for the quality gate
7edd648 test_slice_wave_contract_crash: render the crash context through the real run_state renderer

## Files changed
 .../spec-loop/scripts/slice_wave_contract_base.py  |  5 ----
 .../scripts/test_slice_wave_contract_crash.py      | 34 ++++++++++++++++------
 2 files changed, 25 insertions(+), 14 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
164,
164
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_crash.py": [
[
26,
26
],
[
46,
49
],
[
186,
190
],
[
194,
204
],
[
207,
209
],
[
215,
215
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index aff3495..3573555 100644
--- a/plugins/spec-loop/scripts/slice_wave_contract_base.py
+++ b/plugins/spec-loop/scripts/slice_wave_contract_base.py
@@ -160,15 +160,10 @@ CRASH_ERROR_EXPR = "${String((e && e.message) || e)}"
 # token-floor guard, so a throw from there starts in a guard and still reaches
 # the fallback with no escRecord. The old phrasing asserted the stronger claim.
 CRASH_CLASSIFICATION_SENTENCE = "neither structural guard raised its escalation record"
 CRASH_GUARD_ORIGIN_OVERCLAIM = "so this crash came from neither"
 CRASH_HOST_LAYER_CAVEAT = "host- or agent-layer resource failure"
-# render_escalation() (run_state.py) collapses the context and hard-truncates it
-# at 400 characters, and escalations.md is the corpus the escalation gate's
-# precedent check reads. Both the exception text and the stage attribution have
-# to fit inside that budget, ahead of the fixed classification prose.
-CRASH_CONTEXT_RENDER_LIMIT = 400
 CRASH_STAGE_CAVEAT = "so a starting point, not a culprit"
 # The mirror-image overclaim this module now forbids: asserting "bug, NOT a
 # budget limit" is as unprovable as the old "budget" assertion it replaced.
 CRASH_CAUSE_OVERCLAIM = "This is a loop or agent-contract bug"
 CRASH_BUDGET_DENIAL_OVERCLAIM = "NOT a cap or budget limit"
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
index cf42db4..72a6dc9 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
@@ -21,11 +21,11 @@ import dashboard_server
 import run_metrics
 import run_state
 from slice_wave_contract_base import (
     ANSWERABLE_TRIGGERS, CRASH_BUDGET_DENIAL_OVERCLAIM, CRASH_CAUSE_OVERCLAIM,
     CRASH_CLASSIFICATION_SENTENCE, CRASH_CLASSIFIED_PASSTHROUGH,
-    CRASH_CONTEXT_RENDER_LIMIT, CRASH_ERROR_EXPR, CRASH_ERROR_FIRST,
+    CRASH_ERROR_EXPR, CRASH_ERROR_FIRST,
     CRASH_GUARD_ORIGIN_OVERCLAIM, CRASH_HOST_LAYER_CAVEAT,
     CRASH_OPTION_CONTROLLER_ACTS,
     CRASH_OPTION_RETRY, CRASH_OPTION_SKIP, CRASH_OPTION_STOP,
     CRASH_STAGE_CAVEAT, CRASH_STAGE_CONTEXT, CRASH_STAGE_FALLBACK,
     CRASH_STAGE_OVERCLAIM,
@@ -41,10 +41,14 @@ from slice_wave_contract_base import (
 # A real crash message from run 20260825-scope-ceiling, and the LONGEST stage
 # text the fallback can interpolate (the no-dispatch phrase, longer than any
 # role name), so the render check below measures the worst realistic case.
 SAMPLE_MESSAGE = "Cannot read properties of undefined (reading 'head')"
 LONGEST_STAGE = "none (the crash happened before any agent was dispatched)"
+# The template's LAST sentence. It is evicted by the renderer's truncation at
+# this worst-case length, which is what makes the ordering assertion below a
+# real constraint rather than a tautology.
+CONTEXT_TAIL = "task(s) had already completed"
 
 
 class TestTheCrashRecordNamesTheLastDispatchedStage(WorkflowSourceTestCase):
     """A crash record carrying only an exception string sent run
     20260825-scope-ceiling's controller looking for a budget problem. The
@@ -177,28 +181,40 @@ class TestCrashesAreClassifiedAsInternalError(WorkflowSourceTestCase):
         fallback = self.crash_fallback()
         start = fallback.index(CRASH_ERROR_FIRST)
         return fallback[start + 1:fallback.index("`,", start)]
 
     def rendered_crash_context(self, message, stage_text):
-        """The context as run_state.render_escalation() would render it."""
+        """The `- Context:` line escalations.md actually receives, produced by
+        the REAL run_state.render_escalation(). Re-implementing its collapse
+        and truncate here protected nothing: the copy sliced unconditionally
+        and appended no ellipsis, so it disagreed with _one_line() on two of
+        its three behaviours and could not have caught a change to either."""
         filled = self.crash_context().replace(CRASH_ERROR_EXPR, message)
         filled = filled.replace("${stageText}", stage_text)
         filled = filled.replace("${state.tasksCompleted}", "2")
-        return " ".join(filled.split())[:CRASH_CONTEXT_RENDER_LIMIT - 1]
-
-    def test_the_stage_attribution_survives_the_400_char_context_render(self):
-        # run_state.render_escalation() renders "- Context: %s" through
-        # _one_line(..., 400), so anything past 400 collapsed characters never
-        # reaches escalations.md - which is also the corpus a later run's
+        record = {"id": "s1:internal-error", "trigger": "internal-error",
+                  "title": "slice crashed", "context": filled,
+                  "question": "Retry, skip, or stop."}
+        section = run_state.render_escalation("s1", record)
+        lines = section.splitlines()
+        return next(line for line in lines if line.startswith("- Context: "))
+
+    def test_the_stage_attribution_survives_the_real_context_render(self):
+        # run_state.render_escalation() collapses the context and truncates it
+        # through _one_line(), so anything past that budget never reaches
+        # escalations.md - which is also the corpus a later run's
         # escalation-gate precedent check reads. The stage attribution is this
         # record's headline diagnostic and the title asserts it, so it and its
-        # caveat must sit inside that budget, ahead of the fixed prose.
+        # caveat must sit inside the budget, ahead of the fixed prose. The
+        # budget is not named here: the assertion runs the real renderer, so
+        # the test cannot drift from whatever limit render_escalation applies.
         rendered = self.rendered_crash_context(SAMPLE_MESSAGE, LONGEST_STAGE)
         attribution = CRASH_STAGE_CONTEXT.replace("${stageText}", LONGEST_STAGE)
         self.assertIn(SAMPLE_MESSAGE, rendered)
         self.assertIn(attribution, rendered)
         self.assertIn(CRASH_STAGE_CAVEAT, rendered)
+        self.assertNotIn(CONTEXT_TAIL, rendered)
 
     def test_a_lost_slice_is_an_internal_error_too(self):
         # parallel() resolved the thunk to null: the slice died with no result
         # at all, outside runSlice's try/catch. Same one classification, per
         # the run's human-decided single-value constraint; the honest 'slice
