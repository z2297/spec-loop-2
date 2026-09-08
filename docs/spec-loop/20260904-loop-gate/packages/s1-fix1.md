# Review package: d0333b8..159dca7  (context: -U5)

## Commits
159dca7 fix(spec-loop): reformat continuation lines in test_doctrine_loop_boundary.py

## Files changed
 .../spec-loop/scripts/test_doctrine_loop_boundary.py   | 18 ++++++++++++------
 1 file changed, 12 insertions(+), 6 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/test_doctrine_loop_boundary.py": [
[
51,
54
],
[
149,
152
],
[
224,
227
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py b/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
index fd740c7..fa68fda 100644
--- a/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
+++ b/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
@@ -46,12 +46,14 @@ def not_trigger_bullet_count():
     Read off the file rather than remembered, so the count word in the
     section's own opening sentence cannot drift away from the list it
     counts. The section ends at the next `## ` heading.
     """
     lines = SKILL_MD.read_text(encoding="utf-8").splitlines()
-    start = next(i for i, line in enumerate(lines)
-                 if line.strip() == NOT_TRIGGERS_HEADING)
+    start = next(
+        i for i, line in enumerate(lines)
+        if line.strip() == NOT_TRIGGERS_HEADING
+    )
     count = 0
     for line in lines[start + 1:]:
         if line.startswith("## "):
             break
         if line.startswith("- **"):
@@ -142,12 +144,14 @@ class TestPhase2ClosesTheWaveLoopInTheSameTurn(unittest.TestCase):
 
     def test_the_invariants_line_names_the_boundary_as_a_dispatch_point(self):
         self.assertIn(INVARIANT_BOUNDARY, self.text)
         head = self.text.index("Invariants (non-negotiable)")
         self.assertLess(head, self.text.index(INVARIANT_BOUNDARY))
-        self.assertLess(self.text.index(INVARIANT_BOUNDARY),
-                        self.text.index("## Phase 0 — Intake"))
+        self.assertLess(
+            self.text.index(INVARIANT_BOUNDARY),
+            self.text.index("## Phase 0 — Intake"),
+        )
 
 
 # ---- the command: record the escalation BEFORE asking ----
 
 OPEN_FIRST = "append the record FIRST, then ask"
@@ -215,12 +219,14 @@ class TestTheMarkerLifecyclesAreWrittenDown(unittest.TestCase):
     def test_the_markers_are_stated_once_to_be_uncommitted(self):
         self.assertIn(SESSION_NEVER_COMMITTED, self.text)
 
     def test_resume_rewrites_the_session_marker(self):
         self.assertIn(SESSION_RESUME, self.text)
-        self.assertLess(self.text.index("## Resume"),
-                        self.text.index(SESSION_RESUME))
+        self.assertLess(
+            self.text.index("## Resume"),
+            self.text.index(SESSION_RESUME),
+        )
 
     def test_the_paused_lifecycle_names_who_writes_and_who_clears(self):
         for pin in (PAUSED_WHO, PAUSED_CLEAR, PAUSED_NEVER_SELF):
             self.assertIn(pin, self.text)
