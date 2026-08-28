# Review package: a53c48cb3767679591511622a6ad64e4d906c521..058b316  (context: -U5)

## Commits
058b316 fix round 3: reconcile the resume drain with the cumulative answers-map invariant

## Files changed
 plugins/spec-loop/commands/spec-loop.md            | 14 +++---
 .../spec-loop/scripts/test_slice_wave_contract.py  | 51 +++++++++++++++++++++-
 2 files changed, 59 insertions(+), 6 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/commands/spec-loop.md": [
[
135,
139
],
[
170,
173
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract.py": [
[
21,
21
],
[
29,
29
],
[
260,
307
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index cdbdb7e..d7ddbf8 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -130,13 +130,15 @@ deadlock is itself an escalation):
    precedent. Everything else: ONE `AskUserQuestion` round for ALL open escalations
    (recommended defaults first). Write answers back (`escalation-answered` events), keying
    each answer by the escalation's `id` verbatim — a round-suffixed id keeps its suffix in
    the `answers` map, and the wave reads the newest answered round. The wave derives a
    dispatch's round number solely from the keys already present in `answers`, so every
-   re-dispatch this run makes must hand the wave an `answers` map that still carries each
-   previously answered round's key alongside the newest one — dropping an earlier round's
-   key reissues the id that round already answered. Then
+   re-dispatch this run makes — same session or after a `--resume` — must hand the wave an
+   `answers` map carrying EVERY answered escalation of the run, all rounds included, not
+   just the newest: dropping an earlier round's key reissues the id that round already
+   answered. Retaining the older keys surfaces no stale text to a slice, since the wave
+   still reads only the newest answered round. Then
    **re-dispatch the wave with ONLY its non-terminal slices** — filter `slices` to the ones
    whose sidecars are not DONE/SPLIT (merged work never re-enters a wave; its worktree is
    already gone) — same `ctx`, `answers` filled in, and `resumeFromRunId: <wf_id>` so the
    escalated slices' completed stages replay from the journal where the cache holds. Never
    rely on replay to make a terminal slice free: a cache miss re-runs it live against a
@@ -163,12 +165,14 @@ Executive Readout, verbatim.
 
 ## Resume
 
 `--resume <run-id>`: read `dag.json` (recover branch, mode, wave history), recreate
 `.active`, checkout the integration branch (clean-tree guard), `worktrees.py prepare
---resume` for the incomplete wave's slices, drain ANSWERED-but-undispatched escalations into
-the `answers` map, and re-enter the wave loop at the first incomplete wave — same-session
+--resume` for the incomplete wave's slices, drain EVERY answered escalation of the run into
+the `answers` map (every round, already-dispatched ones included, per step 7's
+cumulative-map invariant), and re-enter the wave loop at the first incomplete wave —
+same-session
 with `resumeFromRunId`, fresh invocation otherwise. All slices terminal → straight to
 Phase 5 (regenerating `runbook.md` is safe).
 
 ## Escalation discipline
 
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract.py b/plugins/spec-loop/scripts/test_slice_wave_contract.py
index ef66fbd..17d9539 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract.py
@@ -16,18 +16,19 @@ Usage:
     python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_slice_wave_contract.py'
 """
 
 import json
 import os
+import re
 import shutil
 import subprocess
 import tempfile
 import unittest
 
 from slice_wave_contract_base import (
     ANSWER_CONTEXT_END, ANSWER_CONTEXT_START, ANSWERABLE_TRIGGERS, CLEAN,
-    COUNCIL_VERDICT_EVENT, CRITIQUE_REQUIRED, CRITIQUE_ROLLUP,
+    COMMAND_MD, COUNCIL_VERDICT_EVENT, CRITIQUE_REQUIRED, CRITIQUE_ROLLUP,
     FAIL_CLOSED_DEFAULT, FINDING_CATEGORIES, FLAGGED, GATE_ANSWER,
     GATE_ANSWER_CONTEXT, GUARDED_BASE, GUARDED_CONCERNS,
     GUARDED_DEVIATIONS, GUARDED_HEAD, GUARDED_LOCAL, GUARDED_TOUCHED,
     HELPER_END, NO_COMMITS_ESCALATION, OBJECTION_SELECTION,
     OVER_SCOPE_DEFAULT, OVER_SCOPE_SCHEMA, REPLAN_VETO, SCOPE_DRIVER,
@@ -254,7 +255,55 @@ class TestScopeRecordBehavesAndNotJustExists(WorkflowSourceTestCase):
         # would reach run_state.py as an absent key instead of an explicit null.
         got = self.scope_record([[{"over_scope": {"flag": True}}]])
         self.assertEqual(got, [{"flag": True, "reason": None}])
 
 
+# The round component of an escalation id is derived from the keys of the
+# `answers` map alone, so the map handed to a re-dispatch has to stay
+# cumulative over the whole run. Both controller paragraphs that build that
+# map are pinned below, on collapsed whitespace so a rewrap of the prose
+# leaves the pin intact. The helper is module-local rather than shared,
+# because `slice_wave_contract_base` sits at its non-blank-line ceiling.
+def collapsed(text):
+    """Runs of whitespace become a single space."""
+    return re.sub(r"\s+", " ", text)
+
+
+ANSWERS_INVARIANT = (
+    "must hand the wave an `answers` map carrying EVERY answered escalation "
+    "of the run, all rounds included")
+RESUME_DRAIN = (
+    "drain EVERY answered escalation of the run into the `answers` map")
+NARROW_DRAIN = "ANSWERED-but-undispatched"
+
+
+class TestTheAnswersMapStaysCumulativeAcrossAResume(WorkflowSourceTestCase):
+    """`escRound` counts the answered rounds present in `args.answers`, so a
+    truncated map re-issues an id that has already been answered - the
+    collision the round suffix exists to remove. The controller command is
+    the only place that builds the map, and its two build sites (the
+    escalation step and the resume drain) have to agree on that."""
+
+    def command(self):
+        return collapsed(COMMAND_MD.read_text(encoding="utf-8"))
+
+    def test_the_escalation_step_states_the_cumulative_map_invariant(self):
+        self.assertIn(collapsed(ANSWERS_INVARIANT), self.command())
+
+    def test_the_resume_drain_covers_every_answered_escalation(self):
+        self.assertIn(collapsed(RESUME_DRAIN), self.command())
+
+    def test_no_build_site_narrows_the_drain_to_undispatched_answers(self):
+        # The narrow drain kept only answers not yet handed to a slice, which
+        # is precisely the set that leaves the round counter short after a
+        # fresh resume.
+        self.assertNotIn(NARROW_DRAIN, self.command())
+
+    def test_the_round_number_is_still_derived_from_the_answer_keys(self):
+        # The pins above are prose. This one holds them to the code they
+        # describe: the derivation they exist to protect is the real one.
+        source = wrapped_source()
+        self.assertIn("return answerKeysFor(sliceId, trigger).length + 1", source)
+
+
 if __name__ == "__main__":  # pragma: no cover
     unittest.main()
