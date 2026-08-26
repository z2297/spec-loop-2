# Review package: 5ead1bcddf01683229b6a9a939754af96fd1165e..c0fc037  (context: -U5)

## Commits
c0fc037 docs(run-state-v2): document the optional dag.json scope_ceiling
f2c1f87 feat(dag): optional absent-tolerant scope_ceiling in dag.json

## Files changed
 plugins/spec-loop/references/run-state-v2.md |  9 +++++
 plugins/spec-loop/scripts/dag.py             | 19 ++++++++-
 plugins/spec-loop/scripts/test_dag.py        | 59 ++++++++++++++++++++++++++++
 scripts/coverage_omit.txt                    |  2 +-
 4 files changed, 87 insertions(+), 2 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/references/run-state-v2.md": [
[
27,
27
],
[
56,
63
]
],
"plugins/spec-loop/scripts/dag.py": [
[
161,
169
],
[
181,
189
]
],
"plugins/spec-loop/scripts/test_dag.py": [
[
114,
148
],
[
882,
905
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
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index be9bdba..d1d6cde 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -22,10 +22,11 @@ objects and are never machine-load-bearing; metrics are null-honest.
   "base_branch": "<branch it was cut from>",
   "merge_mode": "single-branch | per-slice-pr",
   "mode": "workflow | inline",              // inline = slice-worker-fallback path
   "created_at": "<ISO-8601 UTC>",
   "shared_constraints": ["<run-wide must-not-regress constraints; [] if none>"],
+  "scope_ceiling": ["<things this run must not build; OPTIONAL, may be absent>"],
   "slices": [{
     "id": "s1",
     "goal": "<one shippable change>",
     "files": ["..."], "subsystems": ["..."],
     "deps": ["<slice ids>"],
@@ -50,10 +51,18 @@ schedules, never blocks). `dag.py next-wave` is the one implementation;
 nothing else re-derives it. The `waves[]` array records what was actually
 dispatched (the durable pointer from run state to workflow journals), not a
 prediction. Split children use ids `<parent>.1`, `<parent>.2`, …, with
 `depth = parent.depth + 1`.
 
+`scope_ceiling` is **optional**: `dag.py validate_dag` checks it only when
+the key is present (a list of non-empty strings), and a `dag.json` without
+it is fully valid and fully mutable. That is deliberate asymmetry — the
+neighbouring run-level keys (`run_id`, `base_ref`, `merge_mode`,
+`shared_constraints`, …) are not validated at all, and making any run-level
+key required would make every pre-existing run un-resumable, because
+`_load_for_mutation` refuses to mutate a contract-invalid dag.
+
 ## `slice-<id>-status.json` — per-slice sidecar
 
 Persisted by the controller (via `run_state.py persist-slice`) from the
 tool-validated SliceResult a wave workflow returns. Authoritative over any
 prose about the slice.
diff --git a/plugins/spec-loop/scripts/dag.py b/plugins/spec-loop/scripts/dag.py
index 430747c..3567f4e 100644
--- a/plugins/spec-loop/scripts/dag.py
+++ b/plugins/spec-loop/scripts/dag.py
@@ -156,11 +156,19 @@ def deps_of(item):
 # --------------------------------------------------------------------------
 # validate
 # --------------------------------------------------------------------------
 
 def validate_dag(dag):
-    """Return every contract violation in `dag` as a list of messages."""
+    """Return every contract violation in `dag` as a list of messages.
+
+    Run-level keys are deliberately asymmetric: `scope_ceiling` is checked only
+    when present, while its neighbours (`run_id`, `base_ref`, `merge_mode`,
+    `shared_constraints`, ...) stay unvalidated. Absence must never be an error:
+    `_load_for_mutation` refuses to mutate a contract-invalid dag, so making any
+    run-level key required would make every pre-existing run un-resumable and
+    hard-fail mark/record-wave/ingest-split mid-run.
+    """
     if not isinstance(dag, dict):
         return ["dag.json must contain a JSON object"]
 
     errors = []
     if dag.get("schema_version") != SCHEMA_VERSION:
@@ -168,10 +176,19 @@ def validate_dag(dag):
                       % (SCHEMA_VERSION, dag.get("schema_version")))
     if not isinstance(dag.get("slices"), list):
         errors.append("slices must be a list")
     if "waves" in dag and not isinstance(dag.get("waves"), list):
         errors.append("waves must be a list")
+    if "scope_ceiling" in dag:
+        ceiling = dag.get("scope_ceiling")
+        if not isinstance(ceiling, list):
+            errors.append("scope_ceiling must be a list of strings")
+        else:
+            for position, entry in enumerate(ceiling):
+                if not isinstance(entry, str) or not entry.strip():
+                    errors.append("scope_ceiling entry %d must be a non-empty string "
+                                  "(found %r)" % (position, entry))
 
     seen = set()
     for position, item in enumerate(slices_of(dag)):
         sid = item.get("id")
         if not isinstance(sid, str) or not sid:
diff --git a/plugins/spec-loop/scripts/test_dag.py b/plugins/spec-loop/scripts/test_dag.py
index 3d496ef..ffbc2aa 100644
--- a/plugins/spec-loop/scripts/test_dag.py
+++ b/plugins/spec-loop/scripts/test_dag.py
@@ -109,10 +109,45 @@ class TestValidate(unittest.TestCase):
         self.assertErrorMentions(dagmod.validate_dag(d), "schema_version")
 
     def test_slices_must_be_a_list(self):
         self.assertErrorMentions(dagmod.validate_dag(make_dag(slices={})), "slices")
 
+    def test_scope_ceiling_is_absent_from_a_well_formed_dag_and_that_is_valid(self):
+        d = make_dag()
+        self.assertNotIn("scope_ceiling", d)
+        self.assertEqual(dagmod.validate_dag(d), [])
+
+    def test_scope_ceiling_of_non_empty_strings_is_valid(self):
+        d = make_dag(scope_ceiling=["do not touch the tier table",
+                                    "no dashboard UI work"])
+        self.assertEqual(dagmod.validate_dag(d), [])
+
+    def test_scope_ceiling_may_be_an_empty_list(self):
+        self.assertEqual(dagmod.validate_dag(make_dag(scope_ceiling=[])), [])
+
+    def test_scope_ceiling_must_be_a_list(self):
+        self.assertErrorMentions(
+            dagmod.validate_dag(make_dag(scope_ceiling="no dashboard work")),
+            "scope_ceiling must be a list")
+
+    def test_scope_ceiling_rejects_a_non_string_entry(self):
+        errors = dagmod.validate_dag(make_dag(scope_ceiling=["ok", 7]))
+        self.assertErrorMentions(errors, "scope_ceiling entry 1")
+
+    def test_scope_ceiling_rejects_a_blank_entry(self):
+        errors = dagmod.validate_dag(make_dag(scope_ceiling=["   "]))
+        self.assertErrorMentions(errors, "scope_ceiling entry 0")
+
+    def test_scope_ceiling_reports_every_bad_entry_without_short_circuiting(self):
+        errors = dagmod.validate_dag(make_dag(scope_ceiling=[None, "ok", ""]))
+        self.assertEqual(
+            len([e for e in errors if e.startswith("scope_ceiling entry")]), 2)
+
+    def test_a_null_scope_ceiling_is_reported_as_a_bad_list_not_ignored(self):
+        self.assertErrorMentions(dagmod.validate_dag(make_dag(scope_ceiling=None)),
+                                 "scope_ceiling must be a list")
+
     def test_duplicate_slice_ids(self):
         d = make_dag(slices=[sl("s1"), sl("s1")])
         self.assertErrorMentions(dagmod.validate_dag(d), "duplicate slice id")
 
     def test_missing_slice_id(self):
@@ -842,10 +877,34 @@ class TestCli(DagCliTestCase):
         code, payload, _ = self.cli("mark", "--slice", "s1", "--status", "complete")
         self.assertEqual(code, 1)
         self.assertIn("schema_version", " ".join(payload["errors"]))
         self.assertEqual(self.raw(), before)
 
+    def test_a_dag_without_scope_ceiling_validates_and_still_marks(self):
+        # scope_ceiling is optional: a pre-existing run with no ceiling must stay
+        # contract-valid, so _load_for_mutation still lets `mark` through
+        # (run 20260825-scope-ceiling).
+        body = make_dag()
+        self.assertNotIn("scope_ceiling", body)
+        self.write(body)
+        code, payload, _ = self.cli("validate")
+        self.assertEqual(code, 0)
+        self.assertTrue(payload["ok"])
+        code, _, _ = self.cli("mark", "--slice", "s1", "--status", "complete")
+        self.assertEqual(code, 0)
+        self.assertEqual(self.read()["slices"][0]["status"], "complete")
+        self.assertNotIn("scope_ceiling", self.read())
+
+    def test_a_dag_with_a_malformed_scope_ceiling_refuses_to_mark(self):
+        self.write(make_dag(scope_ceiling="not a list"))
+        before = self.raw()
+        code, payload, _ = self.cli("mark", "--slice", "s1", "--status", "complete")
+        self.assertEqual(code, 1)
+        self.assertFalse(payload["ok"])
+        self.assertTrue(any("scope_ceiling" in e for e in payload["errors"]))
+        self.assertEqual(self.raw(), before)
+
     def test_unknown_subcommand_is_usage_error(self):
         with self.assertRaises(SystemExit):
             self.cli("frobnicate")
 
 
diff --git a/scripts/coverage_omit.txt b/scripts/coverage_omit.txt
index a483583..16f181a 100644
--- a/scripts/coverage_omit.txt
+++ b/scripts/coverage_omit.txt
@@ -20,11 +20,11 @@
 # Line numbers verified against source on 2026-07-30 (spec-loop 2 script
 # inventory); re-verify whenever these files change length. Plugin scripts live
 # in plugins/spec-loop/scripts/ but keys stay scripts/<name>.py because
 # measure_coverage.normalize_key canonicalizes either scripts/ dir.
 
-scripts/dag.py:676-677                   # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/dag.py:693-694                   # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/dashboard_launcher.py:558-559    # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/dashboard_server.py:1645-1646    # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/knowledge_graph.py:1211-1212     # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/pr_resolver.py:488-489           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/quality_gate.py:1104-1105        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
