# Review package: d0e0102..8dc2887  (context: -U5)

## Commits
8dc2887 fix(tests): reduce nesting depth in marker-hygiene unanchored test

## Files changed
 .../scripts/test_doctrine_marker_hygiene.py        | 25 +++++++++++++++-------
 1 file changed, 17 insertions(+), 8 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py": [
[
64,
71
],
[
125,
133
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py b/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py
index 01d3b2e..6d0fbc3 100644
--- a/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py
+++ b/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py
@@ -59,10 +59,18 @@ def ignore_lines():
         for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
         if line.strip() and not line.strip().startswith("#")
     ]
 
 
+def marker_suffix(line):
+    """The marker `line` ends with, or None. (PURE)"""
+    for marker in MARKERS:
+        if line.endswith(marker):
+            return marker
+    return None
+
+
 def repo_has_git():
     """True when REPO_ROOT has a .git dir OR a .git file (linked worktree)."""
     return (REPO_ROOT / ".git").exists()
 
 
@@ -112,18 +120,19 @@ class TestMarkersAreNotTracked(unittest.TestCase):
                 "commit it again" % marker,
             )
 
     def test_marker_ignore_patterns_are_unanchored(self):
         for line in ignore_lines():
-            for marker in MARKERS:
-                if line.endswith(marker):
-                    self.assertEqual(
-                        line,
-                        marker,
-                        "%s must be matched at any depth, so its .gitignore "
-                        "entry must be the bare name, not %r" % (marker, line),
-                    )
+            marker = marker_suffix(line)
+            if marker is None:
+                continue
+            self.assertEqual(
+                line,
+                marker,
+                "%s must be matched at any depth, so its .gitignore "
+                "entry must be the bare name, not %r" % (marker, line),
+            )
 
 
 class TestRunStateDocStatesMarkerHygiene(unittest.TestCase):
     """The Markers section must name every marker and the ignore rule."""
