# Review package: 299f0dbd1f700f8f3b3991ea7d601df797dd3749..af31142  (context: -U5)

## Commits
af31142 test(metrics): drive internal-error through the real legacy escalation parser

## Files changed
 plugins/spec-loop/scripts/test_run_metrics.py | 51 +++++++++++++++++++++++----
 1 file changed, 44 insertions(+), 7 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/test_run_metrics.py": [
[
275,
288
],
[
481,
490
],
[
1358,
1377
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/test_run_metrics.py b/plugins/spec-loop/scripts/test_run_metrics.py
index 7f26692..f397e73 100644
--- a/plugins/spec-loop/scripts/test_run_metrics.py
+++ b/plugins/spec-loop/scripts/test_run_metrics.py
@@ -270,10 +270,24 @@ LEGACY_ESCALATIONS = """\
 - Trigger: council-objection
 - If unanswered: pause this slice (s7); continue all independent slices.
 - Answer: **Option 1 — apply the council's proven remedy, then execute.**
 """
 
+# A v1 escalations.md whose Trigger lines carry the crash trigger, in the same
+# prose shape as LEGACY_ESCALATIONS. Kept separate from that fixture because
+# LegacyComputeTests pins exact per-trigger counts derived from it.
+LEGACY_ESCALATIONS_CRASH = """\
+# Escalations — legacy
+
+## [s4] Slice worker crashed mid-dispatch   (status: ANSWERED)
+- Trigger: internal-error (the dispatch raised and was caught by the wave harness)
+- Answer: **Proceed with the recommended default.**
+
+## [s5] Retry exhausted against a resource limit   (status: OPEN)
+- Trigger: budget-exhausted + internal-error (a resource signal, then a caught throw)
+"""
+
 
 # ---------------------------------------------------------------------------
 # helpers
 # ---------------------------------------------------------------------------
 
@@ -462,17 +476,20 @@ class EscalationPairingTests(unittest.TestCase):
             id="a:internal-error", trigger="internal-error")
         result = self.records_for(json.dumps(opened))
         triggers = [r["trigger"] for r in result["records"]]
         self.assertEqual(triggers, ["internal-error"])
 
-    def test_internal_error_is_substring_safe_against_every_other_trigger(self):
-        # _legacy_match_triggers() in run_metrics.py matches by containment
-        # (no line number: it moved once already when internal-error landed).
-        others = [t for t in rm.ESCALATION_TRIGGERS if t != "internal-error"]
-        for other in others:
-            self.assertNotIn(other, "internal-error")
-            self.assertNotIn("internal-error", other)
+    def test_the_trigger_names_are_pairwise_non_substrings(self):
+        # A name-level property only: no canonical trigger contains another,
+        # which is what makes _legacy_match_triggers' containment matching
+        # unambiguous. The matcher itself is exercised in
+        # LegacyProseParserTests against real v1 prose; this method reads the
+        # constant and never reaches the parser.
+        for probe in rm.ESCALATION_TRIGGERS:
+            rest = [t for t in rm.ESCALATION_TRIGGERS if t != probe]
+            for other in rest:
+                self.assertNotIn(other, probe)
 
     def test_union_counts_a_duplicated_record_once(self):
         metrics = compute_for(v2_files(), run_id="20260730-v2")
         self.assertEqual(metrics["safety"]["escalations"]["total"], 2)
         self.assertEqual(metrics["safety"]["escalations"]["basis"],
@@ -1336,10 +1353,30 @@ class LegacyProseParserTests(unittest.TestCase):
         open_escs = rm.legacy_parse_escalations(
             "## [s1] Pick a port   (status: OPEN)\n"
             "- Trigger: material-assumption\n- Answer:\n")
         self.assertEqual(open_escs[0]["status"], "OPEN")
 
+    def test_a_crash_trigger_line_matches_internal_error_through_the_real_parser(self):
+        # Drives rm.legacy_parse_escalations -> _legacy_body_fields ->
+        # _legacy_match_triggers on real v1 prose, so a change to the matcher's
+        # containment semantics turns this red. ESCALATION_TRIGGERS is imported,
+        # never re-listed here.
+        escs = rm.legacy_parse_escalations(LEGACY_ESCALATIONS_CRASH)
+        crash = escs[0]
+        self.assertEqual(crash["triggers"], ["internal-error"])
+        self.assertEqual(crash["trigger"], "internal-error")
+        spurious = set(rm.ESCALATION_TRIGGERS) - {"internal-error"}
+        self.assertEqual(set(crash["triggers"]) & spurious, set())
+
+    def test_a_crash_trigger_line_alongside_budget_exhausted_collects_both(self):
+        # _legacy_match_triggers collects every containment match, in
+        # ESCALATION_TRIGGERS declaration order.
+        escs = rm.legacy_parse_escalations(LEGACY_ESCALATIONS_CRASH)
+        both_in_declaration_order = ["budget-exhausted", "internal-error"]
+        self.assertEqual(escs[1]["triggers"], both_in_declaration_order)
+        self.assertEqual(escs[1]["status"], "OPEN")
+
 
 class LegacyComputeTests(unittest.TestCase):
     @classmethod
     def setUpClass(cls):
         with tempfile.TemporaryDirectory() as tmp:
