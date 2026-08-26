# Review package: c0fc037..cdb336b  (context: -U5)

## Commits
cdb336b fix(dag): extract validate_dag into focused helpers to clear quality-gate metrics

## Files changed
 plugins/spec-loop/scripts/dag.py      | 189 ++++++++++++++++++++++------------
 plugins/spec-loop/scripts/test_dag.py |   8 +-
 scripts/coverage_omit.txt             |   4 +-
 3 files changed, 131 insertions(+), 70 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/dag.py": [
[
169,
173
],
[
178,
188
],
[
191,
193
],
[
198,
214
],
[
216,
218
],
[
229,
230
],
[
231,
231
],
[
233,
258
],
[
263,
265
],
[
266,
266
],
[
268,
295
],
[
298,
324
]
],
"plugins/spec-loop/scripts/test_dag.py": [
[
120,
121
],
[
146,
147
]
],
"scripts/coverage_omit.txt": [
[
25,
25
],
[
34,
34
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/dag.py b/plugins/spec-loop/scripts/dag.py
index 3567f4e..db4d0d2 100644
--- a/plugins/spec-loop/scripts/dag.py
+++ b/plugins/spec-loop/scripts/dag.py
@@ -164,105 +164,166 @@ def validate_dag(dag):
     when present, while its neighbours (`run_id`, `base_ref`, `merge_mode`,
     `shared_constraints`, ...) stay unvalidated. Absence must never be an error:
     `_load_for_mutation` refuses to mutate a contract-invalid dag, so making any
     run-level key required would make every pre-existing run un-resumable and
     hard-fail mark/record-wave/ingest-split mid-run.
+
+    Delegates each independent section of the contract (top-level keys, per-
+    slice fields, cross-slice relations, cycles, waves) to its own helper so no
+    single function accumulates every branch — each section's errors are still
+    concatenated into one flat list, in the same order as before.
     """
     if not isinstance(dag, dict):
         return ["dag.json must contain a JSON object"]
 
+    errors = list(_top_level_errors(dag))
+    errors.extend(_slice_field_errors(dag))
+    index = slice_index(dag)
+    errors.extend(_slice_relation_errors(dag, index))
+    errors.extend(_cycle_errors(dag, index))
+    errors.extend(_wave_errors(dag, index))
+    return errors
+
+
+def _top_level_errors(dag):
+    """Run-level key checks: schema_version, slices, waves, scope_ceiling."""
     errors = []
     if dag.get("schema_version") != SCHEMA_VERSION:
-        errors.append("schema_version must be %d (found %r)"
-                      % (SCHEMA_VERSION, dag.get("schema_version")))
+        errors.append(
+            "schema_version must be %d (found %r)"
+            % (SCHEMA_VERSION, dag.get("schema_version")))
     if not isinstance(dag.get("slices"), list):
         errors.append("slices must be a list")
     if "waves" in dag and not isinstance(dag.get("waves"), list):
         errors.append("waves must be a list")
-    if "scope_ceiling" in dag:
-        ceiling = dag.get("scope_ceiling")
-        if not isinstance(ceiling, list):
-            errors.append("scope_ceiling must be a list of strings")
-        else:
-            for position, entry in enumerate(ceiling):
-                if not isinstance(entry, str) or not entry.strip():
-                    errors.append("scope_ceiling entry %d must be a non-empty string "
-                                  "(found %r)" % (position, entry))
+    errors.extend(_scope_ceiling_errors(dag))
+    return errors
+
+
+def _scope_ceiling_errors(dag):
+    if "scope_ceiling" not in dag:
+        return []
+    ceiling = dag.get("scope_ceiling")
+    if not isinstance(ceiling, list):
+        return ["scope_ceiling must be a list of strings"]
+    return [
+        "scope_ceiling entry %d must be a non-empty string (found %r)"
+        % (position, entry)
+        for position, entry in enumerate(ceiling)
+        if not isinstance(entry, str) or not entry.strip()
+    ]
+
 
+def _slice_field_errors(dag):
+    """Per-slice field checks (id, status, risk_tier, depth, deps)."""
+    errors = []
     seen = set()
     for position, item in enumerate(slices_of(dag)):
         sid = item.get("id")
         if not isinstance(sid, str) or not sid:
             errors.append("slice at position %d has no usable id" % position)
             continue
         if sid in seen:
             errors.append("duplicate slice id %r" % sid)
             continue
         seen.add(sid)
+        errors.extend(_single_slice_field_errors(sid, item))
+    return errors
 
-        if item.get("status") not in SLICE_STATUSES:
-            errors.append("slice %s: status must be one of %s (found %r)"
-                          % (sid, "/".join(SLICE_STATUSES), item.get("status")))
-        if item.get("risk_tier") not in RISK_TIERS:
-            errors.append("slice %s: risk_tier must be 1, 2 or 3 (found %r)"
-                          % (sid, item.get("risk_tier")))
-        depth = item.get("depth")
-        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
-            errors.append("slice %s: depth must be a non-negative integer (found %r)"
-                          % (sid, depth))
-        elif depth > MAX_DEPTH:
-            errors.append("slice %s: depth %d exceeds the cap of %d"
-                          % (sid, depth, MAX_DEPTH))
-        if not isinstance(item.get("deps", []), list):
-            errors.append("slice %s: deps must be a list" % sid)
 
-    index = slice_index(dag)
+def _single_slice_field_errors(sid, item):
+    errors = []
+    if item.get("status") not in SLICE_STATUSES:
+        errors.append("slice %s: status must be one of %s (found %r)"
+                      % (sid, "/".join(SLICE_STATUSES), item.get("status")))
+    if item.get("risk_tier") not in RISK_TIERS:
+        errors.append("slice %s: risk_tier must be 1, 2 or 3 (found %r)"
+                      % (sid, item.get("risk_tier")))
+    errors.extend(_depth_errors(sid, item.get("depth")))
+    if not isinstance(item.get("deps", []), list):
+        errors.append("slice %s: deps must be a list" % sid)
+    return errors
+
+
+def _depth_errors(sid, depth):
+    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
+        return ["slice %s: depth must be a non-negative integer (found %r)"
+               % (sid, depth)]
+    if depth > MAX_DEPTH:
+        return ["slice %s: depth %d exceeds the cap of %d" % (sid, depth, MAX_DEPTH)]
+    return []
+
+
+def _slice_relation_errors(dag, index):
+    """Cross-slice checks: deps resolve, and parent/split/depth agreement."""
+    errors = []
     for item in slices_of(dag):
         sid = item.get("id")
         if not isinstance(sid, str) or not sid:
             continue
-        for dep in deps_of(item):
-            if dep not in index:
-                errors.append("slice %s: dep %r references an unknown slice" % (sid, dep))
-        parent_id = item.get("parent")
-        if parent_id is None:
-            continue
-        parent = index.get(parent_id)
-        if parent is None:
-            errors.append("slice %s: unknown parent %r" % (sid, parent_id))
-            continue
-        if parent.get("status") != "split":
-            errors.append("slice %s: parent %s must have status \"split\" (found %r)"
-                          % (sid, parent_id, parent.get("status")))
-        if isinstance(item.get("depth"), int) and isinstance(parent.get("depth"), int):
-            if item["depth"] != parent["depth"] + 1:
-                errors.append("slice %s: depth %r must be parent %s depth + 1 (%d)"
-                              % (sid, item["depth"], parent_id, parent["depth"] + 1))
+        errors.extend(_dep_reference_errors(sid, item, index))
+        errors.extend(_parent_relation_errors(sid, item, index))
+    return errors
+
+
+def _dep_reference_errors(sid, item, index):
+    return ["slice %s: dep %r references an unknown slice" % (sid, dep)
+            for dep in deps_of(item) if dep not in index]
+
+
+def _parent_relation_errors(sid, item, index):
+    parent_id = item.get("parent")
+    if parent_id is None:
+        return []
+    parent = index.get(parent_id)
+    if parent is None:
+        return ["slice %s: unknown parent %r" % (sid, parent_id)]
+
+    errors = []
+    if parent.get("status") != "split":
+        errors.append("slice %s: parent %s must have status \"split\" (found %r)"
+                      % (sid, parent_id, parent.get("status")))
+    child_depth, parent_depth = item.get("depth"), parent.get("depth")
+    if (isinstance(child_depth, int) and isinstance(parent_depth, int)
+            and child_depth != parent_depth + 1):
+        errors.append("slice %s: depth %r must be parent %s depth + 1 (%d)"
+                      % (sid, child_depth, parent_id, parent_depth + 1))
+    return errors
 
-    errors.extend(_cycle_errors(dag, index))
 
+def _wave_errors(dag, index):
+    """Wave checks: 1-based unique index, status enum, slice_ids resolve."""
+    errors = []
     wave_indexes = set()
     for position, item in enumerate(waves_of(dag)):
-        wave_index = item.get("index")
-        label = wave_index if isinstance(wave_index, int) else "at position %d" % position
-        if not isinstance(wave_index, int) or isinstance(wave_index, bool) or wave_index < 1:
-            errors.append("wave %s: index must be a 1-based integer" % label)
-        elif wave_index in wave_indexes:
-            errors.append("duplicate wave index %d" % wave_index)
-        else:
-            wave_indexes.add(wave_index)
-        if item.get("status") not in WAVE_STATUSES:
-            errors.append("wave %s: status must be one of %s (found %r)"
-                          % (label, "/".join(WAVE_STATUSES), item.get("status")))
-        ids = item.get("slice_ids")
-        if not isinstance(ids, list):
-            errors.append("wave %s: slice_ids must be a list" % label)
-            continue
-        for sid in ids:
-            if sid not in index:
-                errors.append("wave %s: slice_ids entry %r references an unknown slice"
-                              % (label, sid))
+        errors.extend(_single_wave_errors(position, item, index, wave_indexes))
+    return errors
+
+
+def _single_wave_errors(position, item, index, wave_indexes):
+    wave_index = item.get("index")
+    label = wave_index if isinstance(wave_index, int) else "at position %d" % position
+
+    errors = []
+    if not isinstance(wave_index, int) or isinstance(wave_index, bool) or wave_index < 1:
+        errors.append("wave %s: index must be a 1-based integer" % label)
+    elif wave_index in wave_indexes:
+        errors.append("duplicate wave index %d" % wave_index)
+    else:
+        wave_indexes.add(wave_index)
+    if item.get("status") not in WAVE_STATUSES:
+        errors.append("wave %s: status must be one of %s (found %r)"
+                      % (label, "/".join(WAVE_STATUSES), item.get("status")))
+
+    ids = item.get("slice_ids")
+    if not isinstance(ids, list):
+        errors.append("wave %s: slice_ids must be a list" % label)
+        return errors
+    errors.extend(
+        "wave %s: slice_ids entry %r references an unknown slice" % (label, sid)
+        for sid in ids if sid not in index
+    )
     return errors
 
 
 def _cycle_errors(dag, index):
     """One message per slice that participates in a dependency cycle."""
diff --git a/plugins/spec-loop/scripts/test_dag.py b/plugins/spec-loop/scripts/test_dag.py
index ffbc2aa..616c398 100644
--- a/plugins/spec-loop/scripts/test_dag.py
+++ b/plugins/spec-loop/scripts/test_dag.py
@@ -115,12 +115,12 @@ class TestValidate(unittest.TestCase):
         d = make_dag()
         self.assertNotIn("scope_ceiling", d)
         self.assertEqual(dagmod.validate_dag(d), [])
 
     def test_scope_ceiling_of_non_empty_strings_is_valid(self):
-        d = make_dag(scope_ceiling=["do not touch the tier table",
-                                    "no dashboard UI work"])
+        entries = ["do not touch the tier table", "no dashboard UI work"]
+        d = make_dag(scope_ceiling=entries)
         self.assertEqual(dagmod.validate_dag(d), [])
 
     def test_scope_ceiling_may_be_an_empty_list(self):
         self.assertEqual(dagmod.validate_dag(make_dag(scope_ceiling=[])), [])
 
@@ -141,12 +141,12 @@ class TestValidate(unittest.TestCase):
         errors = dagmod.validate_dag(make_dag(scope_ceiling=[None, "ok", ""]))
         self.assertEqual(
             len([e for e in errors if e.startswith("scope_ceiling entry")]), 2)
 
     def test_a_null_scope_ceiling_is_reported_as_a_bad_list_not_ignored(self):
-        self.assertErrorMentions(dagmod.validate_dag(make_dag(scope_ceiling=None)),
-                                 "scope_ceiling must be a list")
+        errors = dagmod.validate_dag(make_dag(scope_ceiling=None))
+        self.assertErrorMentions(errors, "scope_ceiling must be a list")
 
     def test_duplicate_slice_ids(self):
         d = make_dag(slices=[sl("s1"), sl("s1")])
         self.assertErrorMentions(dagmod.validate_dag(d), "duplicate slice id")
 
diff --git a/scripts/coverage_omit.txt b/scripts/coverage_omit.txt
index 16f181a..a514cdf 100644
--- a/scripts/coverage_omit.txt
+++ b/scripts/coverage_omit.txt
@@ -20,18 +20,18 @@
 # Line numbers verified against source on 2026-07-30 (spec-loop 2 script
 # inventory); re-verify whenever these files change length. Plugin scripts live
 # in plugins/spec-loop/scripts/ but keys stay scripts/<name>.py because
 # measure_coverage.normalize_key canonicalizes either scripts/ dir.
 
-scripts/dag.py:693-694                   # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/dag.py:754-755                   # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/dashboard_launcher.py:558-559    # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/dashboard_server.py:1645-1646    # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/knowledge_graph.py:1211-1212     # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/pr_resolver.py:488-489           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/quality_gate.py:1104-1105        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/release.py:194-195               # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/review_package.py:131-132        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/run_metrics.py:1825-1826         # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/run_state.py:822-823             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/run_state.py:837-838             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/spec_loop_guard.py:240-241       # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/validate_marketplace.py:417-418  # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/worktrees.py:385-386             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
