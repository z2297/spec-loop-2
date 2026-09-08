# Review package: 080b265f86c921ba4d264011532ff5459880dc50..65ff49a  (context: -U5)

## Commits
65ff49a test(spec-loop): assert the uncommitted-markers sentence appears exactly once
8cc5fd5 docs(spec-loop): state the escalation-answered write-back and de-fuse the wave-raised exclusion

## Files changed
 plugins/spec-loop/commands/spec-loop.md            | 16 ++++++++++------
 .../scripts/test_doctrine_loop_boundary.py         | 22 ++++++++++++++++++++--
 2 files changed, 30 insertions(+), 8 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/commands/spec-loop.md": [
[
255,
261
],
[
263,
265
]
],
"plugins/spec-loop/scripts/test_doctrine_loop_boundary.py": [
[
162,
165
],
[
171,
173
],
[
190,
198
],
[
235,
238
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index 13375aa..d00e416 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -250,12 +250,16 @@ ambiguity, a config first-run choice, the publish prompt, any question you raise
 rather than a wave — append the record FIRST, then ask:
 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run_state.py" append-event --run-dir <dir> --ts <now>
 --scope run --type escalation-opened --payload <EscalationRecord JSON>`. The order is the
 point: `open-escalations` reads events.jsonl, so a question asked before its record exists is
 invisible to a resume and to anything else reading run state, and the `escalation-answered`
-event you write back pairs by an `id` that was never opened. This excludes records a wave
-raised are already appended by `persist-slice` — never re-append those.
+event you write back pairs by an `id` that was never opened. Closing the record is the second
+half of the same rule: the moment the human answers, append the matching
+`escalation-answered` event keyed by the same `id` verbatim, before you act on the answer.
+`open-escalations` holds an opened id with no answer event open forever, so an unclosed
+record is re-gathered by Phase 2 step 7, re-asked at the next wave boundary, and surfaced
+by the dashboard until it is closed. The rule does not apply to wave-raised escalations:
+records a wave raised are already appended by `persist-slice`, so never re-append those.
 
-Every autonomous decision = one `decision` event with
-rationale and reversibility. When a workflow result surprises you (empty, malformed,
-contradicting its own events), read the workflow journal before re-dispatching — never
-re-run work you merely failed to look at.
+Every autonomous decision = one `decision` event with rationale and reversibility. When a
+workflow result surprises you (empty, malformed, contradicting its own events), read the
+workflow journal before re-dispatching — never re-run work you merely failed to look at.
diff --git a/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py b/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
index fa68fda..bda416f 100644
--- a/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
+++ b/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
@@ -157,16 +157,22 @@ class TestPhase2ClosesTheWaveLoopInTheSameTurn(unittest.TestCase):
 OPEN_FIRST = "append the record FIRST, then ask"
 OPEN_CLI = "--type escalation-opened"
 OPEN_SCOPE = "any question you raise yourself rather than a wave"
 OPEN_WHY = "a question asked before its record exists is invisible to a resume"
 OPEN_NO_DOUBLE = "records a wave raised are already appended by `persist-slice`"
+ANSWER_BACK = "append the matching `escalation-answered` event keyed by the same `id`"
+ANSWER_WHY = "an opened id with no answer event open forever"
+ANSWER_RE_ASK = "re-gathered by Phase 2 step 7"
+OPEN_NO_DOUBLE_TAIL = "so never re-append those"
 
 
 class TestControllerQuestionsAreRecordedBeforeTheyAreAsked(unittest.TestCase):
     """`open-escalations` reads events.jsonl, so an unrecorded question is a
     question no resume and no run-state reader can see, and an answer written
-    back pairs by an id that was never opened."""
+    back pairs by an id that was never opened. An opened record never answered
+    back is re-asked at every later wave boundary, so the write-back is pinned
+    with the ordering."""
 
     def setUp(self):
         self.text = prose(COMMAND_MD)
 
     def test_the_record_is_appended_before_the_question_is_asked(self):
@@ -179,10 +185,19 @@ class TestControllerQuestionsAreRecordedBeforeTheyAreAsked(unittest.TestCase):
     def test_the_rule_says_why_the_order_matters(self):
         self.assertIn(OPEN_WHY, self.text)
 
     def test_wave_raised_records_are_not_re_appended(self):
         self.assertIn(OPEN_NO_DOUBLE, self.text)
+        self.assertIn(OPEN_NO_DOUBLE_TAIL, self.text)
+
+    def test_the_answer_write_back_is_the_second_half_of_the_rule(self):
+        self.assertIn(ANSWER_BACK, self.text)
+        self.assertLess(self.text.index(OPEN_FIRST), self.text.index(ANSWER_BACK))
+
+    def test_the_rule_says_why_an_unclosed_record_is_re_asked(self):
+        self.assertIn(ANSWER_WHY, self.text)
+        self.assertIn(ANSWER_RE_ASK, self.text)
 
     def test_the_rule_lives_in_the_escalation_discipline_section(self):
         head = self.text.index("## Escalation discipline")
         self.assertLess(head, self.text.index(OPEN_FIRST))
 
@@ -215,11 +230,14 @@ class TestTheMarkerLifecyclesAreWrittenDown(unittest.TestCase):
     def test_phase_1_writes_the_controller_session_marker(self):
         self.assertIn(SESSION_WRITE, self.text)
         self.assertIn(SESSION_PURPOSE, self.text)
 
     def test_the_markers_are_stated_once_to_be_uncommitted(self):
-        self.assertIn(SESSION_NEVER_COMMITTED, self.text)
+        """The name says once, so count it: the drift this pin guards against is a
+        SECOND copy of the claim appearing in another phase and the two falling out
+        of step, which a mere `assertIn` would never see."""
+        self.assertEqual(self.text.count(SESSION_NEVER_COMMITTED), 1)
 
     def test_resume_rewrites_the_session_marker(self):
         self.assertIn(SESSION_RESUME, self.text)
         self.assertLess(
             self.text.index("## Resume"),
