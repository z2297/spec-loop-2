# Review package: cdb336b..2dde3dc  (context: -U5)

## Commits
2dde3dc fix(dag): flatten the validate_dag helpers to clear nesting/cognitive gates

## Files changed
 plugins/spec-loop/scripts/dag.py      | 104 ++++++++++++++++++++++------------
 plugins/spec-loop/scripts/test_dag.py |  10 ++++
 scripts/coverage_omit.txt             |   2 +-
 3 files changed, 79 insertions(+), 37 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/dag.py": [
[
234,
236
],
[
238,
238
],
[
242,
254
],
[
264,
269
],
[
294,
296
],
[
300,
316
],
[
327,
327
],
[
330,
333
],
[
335,
337
],
[
339,
353
],
[
355,
357
]
],
"plugins/spec-loop/scripts/test_dag.py": [
[
207,
216
]
],
"scripts/coverage_omit.txt": [
[
25,
25
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/dag.py b/plugins/spec-loop/scripts/dag.py
index db4d0d2..cd8beb3 100644
--- a/plugins/spec-loop/scripts/dag.py
+++ b/plugins/spec-loop/scripts/dag.py
@@ -229,32 +229,46 @@ def _slice_field_errors(dag):
         errors.extend(_single_slice_field_errors(sid, item))
     return errors
 
 
 def _single_slice_field_errors(sid, item):
-    errors = []
-    if item.get("status") not in SLICE_STATUSES:
-        errors.append("slice %s: status must be one of %s (found %r)"
-                      % (sid, "/".join(SLICE_STATUSES), item.get("status")))
-    if item.get("risk_tier") not in RISK_TIERS:
-        errors.append("slice %s: risk_tier must be 1, 2 or 3 (found %r)"
-                      % (sid, item.get("risk_tier")))
+    """Every field message for one slice that has a usable, unique id."""
+    errors = list(_slice_status_errors(sid, item.get("status")))
+    errors.extend(_risk_tier_errors(sid, item.get("risk_tier")))
     errors.extend(_depth_errors(sid, item.get("depth")))
-    if not isinstance(item.get("deps", []), list):
-        errors.append("slice %s: deps must be a list" % sid)
+    errors.extend(_deps_shape_errors(sid, item.get("deps", [])))
     return errors
 
 
+def _slice_status_errors(sid, status):
+    if status in SLICE_STATUSES:
+        return []
+    return ["slice %s: status must be one of %s (found %r)"
+            % (sid, "/".join(SLICE_STATUSES), status)]
+
+
+def _risk_tier_errors(sid, risk_tier):
+    if risk_tier in RISK_TIERS:
+        return []
+    return ["slice %s: risk_tier must be 1, 2 or 3 (found %r)" % (sid, risk_tier)]
+
+
 def _depth_errors(sid, depth):
     if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
         return ["slice %s: depth must be a non-negative integer (found %r)"
                % (sid, depth)]
     if depth > MAX_DEPTH:
         return ["slice %s: depth %d exceeds the cap of %d" % (sid, depth, MAX_DEPTH)]
     return []
 
 
+def _deps_shape_errors(sid, deps):
+    if isinstance(deps, list):
+        return []
+    return ["slice %s: deps must be a list" % sid]
+
+
 def _slice_relation_errors(dag, index):
     """Cross-slice checks: deps resolve, and parent/split/depth agreement."""
     errors = []
     for item in slices_of(dag):
         sid = item.get("id")
@@ -275,56 +289,74 @@ def _parent_relation_errors(sid, item, index):
     if parent_id is None:
         return []
     parent = index.get(parent_id)
     if parent is None:
         return ["slice %s: unknown parent %r" % (sid, parent_id)]
-
-    errors = []
-    if parent.get("status") != "split":
-        errors.append("slice %s: parent %s must have status \"split\" (found %r)"
-                      % (sid, parent_id, parent.get("status")))
-    child_depth, parent_depth = item.get("depth"), parent.get("depth")
-    if (isinstance(child_depth, int) and isinstance(parent_depth, int)
-            and child_depth != parent_depth + 1):
-        errors.append("slice %s: depth %r must be parent %s depth + 1 (%d)"
-                      % (sid, child_depth, parent_id, parent_depth + 1))
+    errors = list(_parent_status_errors(sid, parent_id, parent.get("status")))
+    errors.extend(_child_depth_errors(
+        sid, parent_id, item.get("depth"), parent.get("depth")))
     return errors
 
 
+def _parent_status_errors(sid, parent_id, parent_status):
+    if parent_status == "split":
+        return []
+    return ["slice %s: parent %s must have status \"split\" (found %r)"
+            % (sid, parent_id, parent_status)]
+
+
+def _child_depth_errors(sid, parent_id, child_depth, parent_depth):
+    """A child sits exactly one level below its parent (unknown depths pass)."""
+    if not isinstance(child_depth, int) or not isinstance(parent_depth, int):
+        return []
+    if child_depth == parent_depth + 1:
+        return []
+    return ["slice %s: depth %r must be parent %s depth + 1 (%d)"
+            % (sid, child_depth, parent_id, parent_depth + 1)]
+
+
 def _wave_errors(dag, index):
     """Wave checks: 1-based unique index, status enum, slice_ids resolve."""
     errors = []
     wave_indexes = set()
     for position, item in enumerate(waves_of(dag)):
         errors.extend(_single_wave_errors(position, item, index, wave_indexes))
     return errors
 
 
 def _single_wave_errors(position, item, index, wave_indexes):
+    """Every field message for one wave, in index/status/slice_ids order."""
     wave_index = item.get("index")
     label = wave_index if isinstance(wave_index, int) else "at position %d" % position
+    errors = list(_wave_index_errors(wave_index, label, wave_indexes))
+    errors.extend(_wave_status_errors(label, item.get("status")))
+    errors.extend(_wave_slice_id_errors(label, item.get("slice_ids"), index))
+    return errors
 
-    errors = []
+
+def _wave_index_errors(wave_index, label, wave_indexes):
+    """1-based and unique; records a usable index in `wave_indexes` (IMPURE)."""
     if not isinstance(wave_index, int) or isinstance(wave_index, bool) or wave_index < 1:
-        errors.append("wave %s: index must be a 1-based integer" % label)
-    elif wave_index in wave_indexes:
-        errors.append("duplicate wave index %d" % wave_index)
-    else:
-        wave_indexes.add(wave_index)
-    if item.get("status") not in WAVE_STATUSES:
-        errors.append("wave %s: status must be one of %s (found %r)"
-                      % (label, "/".join(WAVE_STATUSES), item.get("status")))
+        return ["wave %s: index must be a 1-based integer" % label]
+    if wave_index in wave_indexes:
+        return ["duplicate wave index %d" % wave_index]
+    wave_indexes.add(wave_index)
+    return []
 
-    ids = item.get("slice_ids")
+
+def _wave_status_errors(label, status):
+    if status in WAVE_STATUSES:
+        return []
+    return ["wave %s: status must be one of %s (found %r)"
+            % (label, "/".join(WAVE_STATUSES), status)]
+
+
+def _wave_slice_id_errors(label, ids, index):
     if not isinstance(ids, list):
-        errors.append("wave %s: slice_ids must be a list" % label)
-        return errors
-    errors.extend(
-        "wave %s: slice_ids entry %r references an unknown slice" % (label, sid)
-        for sid in ids if sid not in index
-    )
-    return errors
+        return ["wave %s: slice_ids must be a list" % label]
+    return ["wave %s: slice_ids entry %r references an unknown slice" % (label, sid)
+            for sid in ids if sid not in index]
 
 
 def _cycle_errors(dag, index):
     """One message per slice that participates in a dependency cycle."""
     state = {}  # sid -> 0 unvisited / 1 on stack / 2 done
diff --git a/plugins/spec-loop/scripts/test_dag.py b/plugins/spec-loop/scripts/test_dag.py
index 616c398..265612d 100644
--- a/plugins/spec-loop/scripts/test_dag.py
+++ b/plugins/spec-loop/scripts/test_dag.py
@@ -202,10 +202,20 @@ class TestValidate(unittest.TestCase):
         d = make_dag(slices=[
             sl("s1", status="split"), sl("s1.1", depth=2, parent="s1"),
         ])
         self.assertErrorMentions(dagmod.validate_dag(d), "depth")
 
+    def test_child_with_an_unusable_depth_is_not_compared_to_its_parent(self):
+        """A non-integer depth is reported once, as a type error only: the
+        parent-depth+1 comparison is skipped rather than guessing an offset."""
+        d = make_dag(slices=[
+            sl("s1", status="split"), sl("s1.1", depth="one", parent="s1"),
+        ])
+        errors = [e for e in dagmod.validate_dag(d) if "depth" in e]
+        self.assertEqual(len(errors), 1, errors)
+        self.assertIn("non-negative integer", errors[0])
+
     def test_unknown_slice_status(self):
         d = make_dag(slices=[sl("s1", status="FAILED")])
         self.assertErrorMentions(dagmod.validate_dag(d), "status")
 
     def test_bad_risk_tier(self):
diff --git a/scripts/coverage_omit.txt b/scripts/coverage_omit.txt
index a514cdf..f4d8262 100644
--- a/scripts/coverage_omit.txt
+++ b/scripts/coverage_omit.txt
@@ -20,11 +20,11 @@
 # Line numbers verified against source on 2026-07-30 (spec-loop 2 script
 # inventory); re-verify whenever these files change length. Plugin scripts live
 # in plugins/spec-loop/scripts/ but keys stay scripts/<name>.py because
 # measure_coverage.normalize_key canonicalizes either scripts/ dir.
 
-scripts/dag.py:754-755                   # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/dag.py:786-787                   # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/dashboard_launcher.py:558-559    # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/dashboard_server.py:1645-1646    # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/knowledge_graph.py:1211-1212     # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/pr_resolver.py:488-489           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/quality_gate.py:1104-1105        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
