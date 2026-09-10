# Review package: b574405e4b90c33a56ba02658a63ee37c6a5d8e4..e933d5edbba3218676ad0b1126c4bfaab5462f75  (context: -U5)

## Commits
e933d5e docs(gate): correct the phantom-suppression safety claim and name its parameter_count residual
acf8dcf feat(gate): count C# foreach as a cyclomatic branch

## Files changed
 CHANGELOG.md                                   |  50 ++++++++++--
 plugins/spec-loop/scripts/quality_gate.py      |   9 ++-
 plugins/spec-loop/scripts/test_quality_gate.py | 107 +++++++++++++++++++++++--
 3 files changed, 155 insertions(+), 11 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
25,
33
],
[
65,
79
],
[
100,
120
]
],
"plugins/spec-loop/scripts/quality_gate.py": [
[
136,
143
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
13,
17
],
[
601,
616
],
[
2013,
2030
],
[
2058,
2077
],
[
2141,
2143
],
[
2150,
2150
],
[
2153,
2153
],
[
2176,
2177
],
[
2184,
2184
],
[
2187,
2187
],
[
2262,
2295
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index de2e051..09d4f61 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -20,15 +20,19 @@ All notable changes to the spec-loop plugin are documented here. The format is
   1-based inclusive span contains it. **The retained phantom is DELIBERATE, not a residual
   defect** — on a C# method whose opening brace sits on its own line, `_CBRACE_DEF_RE` never
   sees the method, so the `foreach` record is the only measurement of that body (measured:
   cyclomatic 5, cognitive 8); suppressing it unconditionally would take the file to
   `class_lines` alone and turn a real reading into a silent pass. An over-count is the one
-  direction this heuristic is permitted to move. Known, documented residuals: a pure-Allman
-  C# file (every brace on its own line, the Visual Studio default) still extracts nothing at
-  all, because `_CBRACE_DEF_RE` requires the `{` on the signature line — deferred to its own
-  run; and `foreach` is still absent from `_BRANCH_WORDS`, so a C# `foreach` adds no
-  cyclomatic branch.
+  direction this heuristic is permitted to move. That safety argument is PER-METRIC, not
+  blanket: an enclosed phantom's cyclomatic, cognitive, method_lines and nesting_depth are
+  all dominated by the enclosing record whose body contains it, but its `parameter_count` is
+  read from its own header and is NOT — see the `_phantom_has_more_params` entry below.
+  Known, documented residuals: a pure-Allman C# file (every brace on its own line, the
+  Visual Studio default) still extracts nothing at all, because `_CBRACE_DEF_RE` requires
+  the `{` on the signature line — deferred to its own run. (The second residual named here
+  — `foreach` absent from `_BRANCH_WORDS` — is fixed below in this same Unreleased
+  section.)
 - **A changed file the quality gate could not measure can no longer vanish from the report.**
   `measure()` in `plugins/spec-loop/scripts/quality_gate.py` ended its skip chain in
   `elif _lang_for(path) is None`, so a file with a supported extension that yielded zero
   callables produced neither a function measurement nor a `skipped` entry — measured on a
   pure-Allman `.cs` file and a `def`-less `.py` file, `skipped` named neither. The chain now
@@ -56,10 +60,25 @@ All notable changes to the spec-loop plugin are documented here. The format is
   own signature. The new PURE `_phantom_has_more_params` compares the phantom's own header
   against the enclosing record's header and keeps the phantom whenever its count is higher;
   `test_an_enclosed_multi_declaration_using_keeps_its_own_finding` pins a 5-parameter `using`
   surviving inside a 1-parameter `Import` method (5 > `DEFAULT_THRESHOLDS["parameter_count"]`
   == 4). Both are the same failure family the run's NEVER-UNDER-COUNT constraint names.
+  Known, documented residuals: the parameter_count guarantee is an ARGUMENT the code does
+  not assert. `_phantom_has_more_params` keeps a phantom only when its own count is strictly
+  higher, so a phantom whose count is equal or lower is still dropped; that is safe only
+  because the enclosing record's own count is then at least as high AND is always emitted
+  alongside — the enclosing span strictly contains the phantom's, so any changed range that
+  reaches the phantom reaches the enclosing record too. Measured both halves on `.cs`:
+  `using (Stream p = A(), q = B(), r = C(), s = D(), t = E())` inside `Go(int a)` reports
+  `Go` 1 AND `using` 5 (the phantom survives, 5 > the threshold of 4); the same `using`
+  inside `Go(int a,int b,int c,int d,int e,int f)` reports `Go` 6 alone, for a full range and
+  for a narrow range covering only the `using` block. `test_quality_gate.py`'s
+  `test_a_dominated_using_is_dropped_only_behind_a_higher_count` pins that second half. A
+  related measured non-result, recorded so no reader re-derives it: the nested-call form
+  `foreach (var x in Zip(a, b, c))` does NOT reach this path at all — `_count_params` splits
+  commas only at paren depth 0, so it measures 1. The multi-declarator `using` is the only
+  shape that reaches it.
 - **A skip record could itself misreport why a file went unmeasured.** `measure()`'s new
   unconditional `else` arm (see above) reached `_skip_reason(path)` whenever a file yielded
   zero IN-RANGE findings — which also fires for an import-only edit, a docstring tweak, or any
   changed hunk that simply falls outside every callable in an otherwise fully-measurable file.
   Such a file got the same `"no callable found by the builtin heuristic"` text as a file with
@@ -76,10 +95,31 @@ All notable changes to the spec-loop plugin are documented here. The format is
   `test_an_import_only_edit_does_not_falsely_claim_no_callable_exists`. Known, documented
   residuals: `_extract_functions_python`, `_match_brace_end` and `_match_changed` carry
   pre-existing cognitive_complexity/nesting_depth violations this slice did not introduce and
   does not fix here, and `class_lines` on both `quality_gate.py` and `test_quality_gate.py`
   remains accepted debt per standing ruling.
+- **A C# `foreach` now contributes a cyclomatic branch.** `_BRANCH_WORDS` in
+  `plugins/spec-loop/scripts/quality_gate.py:142` gains `foreach`, so both `_branch_count`
+  and `_cognitive_approx` see C#'s loop keyword. Measured on a K&R `.cs` method containing
+  one `foreach`, one `if` with `&&` and one `switch`/`case`: cyclomatic_complexity 4 → 5 and
+  cognitive_complexity 8 → 10, the foreach having contributed nothing before. The word set
+  stays GLOBAL rather than per-language, because a `foreach` in a language that does not
+  reserve it can only over-count, the one direction this heuristic is permitted to move.
+  The match stays case-sensitive and word-boundary-anchored, so JS/Java/Kotlin
+  `arr.forEach(...)` — a method call, not a loop — is not counted, and `for` inside
+  `foreach` fails its own trailing boundary so the keyword adds exactly one branch, not two.
+  `plugins/spec-loop/scripts/test_quality_gate.py` gains
+  `test_csharp_foreach_counts_exactly_one_branch`,
+  `test_camel_case_for_each_is_not_a_branch_word` and the end-to-end
+  `test_a_csharp_foreach_adds_a_branch_to_its_enclosing_method` over the new
+  `CS_FOREACH_CONTROL_SOURCE` fixture, whose enclosing method is genuinely extracted (the
+  phantom is suppressed there by the enclosure guard above, which is why this change is
+  sequenced after it); two pre-existing pinned metric dicts move with it, `Import` 2/3 → 3/5
+  and the deliberately retained `foreach` phantom 5/8 → 6/9. Known, documented residuals:
+  a `foreach` written in a language that does not reserve the word is counted as a branch by
+  design (an over-count); a pure-Allman C# file still extracts no method at all, so its
+  `foreach` is attributed to nothing — deferred to its own run.
 
 ## [2.5.0] - 2026-09-09
 ### Added
 - **`/spec-loop:jira-intake`: read a Jira card, refine it, confirm, and write decisions back.**
   `scripts/jira_client.py` is a stdlib-only, read-first Jira Cloud REST v3 client that resolves
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index d4c33b6..9fcfa74 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -131,11 +131,18 @@ _EXT_LANG = {
 # therefore also stay on raw text.
 _JS_MASK_EXTS = frozenset({".js", ".mjs", ".cjs", ".ts"})
 
 # Branch keywords whose occurrence adds one to cyclomatic complexity. Matched as
 # whole words (or operators) so an identifier like `ifield` is not counted.
-_BRANCH_WORDS = ("if", "elif", "case", "catch", "for", "while", "when")
+# The set is deliberately GLOBAL, not per-language: `foreach` is C#'s loop
+# keyword and its worst case elsewhere is an over-count, the one direction
+# this heuristic is permitted to move. Matching stays case-sensitive and
+# \b-anchored so JS/Java `arr.forEach(...)` -- a method call, not a loop --
+# is never counted; `for` inside `foreach` fails its own trailing \b, so the
+# keyword contributes exactly one branch, not two.
+_BRANCH_WORDS = ("if", "elif", "case", "catch", "for", "while", "when",
+                 "foreach")
 _BRANCH_WORD_RE = re.compile(r"\b(?:%s)\b" % "|".join(_BRANCH_WORDS))
 # Boolean operators and the ternary each add a branch. `else if` is NOT listed
 # here: its `if` is already counted by _BRANCH_WORD_RE, so matching it again
 # would double-count the same branch. The `?(?!\?)` avoids matching `??`.
 _BRANCH_OPS_RE = re.compile(r"&&|\|\||\?(?!\?)")
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index 8821b99..717925d 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -8,11 +8,15 @@ that hides string-literal and comment content from the two branch scans for
 python and the JS/TypeScript family alike (including its extension routing, the
 brace languages left deliberately unmasked, the measured regex-versus-quote
 residuals, and every fall-back-to-raw path), a differential harness comparing
 masked against raw measurement over every heuristic-readable file in the plugin
 tree, the builtin heuristic function extraction for python and brace languages,
-backend CSV/JSON
+the per-extension reserved-word scoping and its coverage-conditional phantom
+suppression (`TestExtensionScopedControlWords`), `measure()`'s skip record for
+every changed file it could not measure (`TestMeasureSkipRecord` — the
+suite's FIRST `qg.measure()`-level test; every other class exercises the
+primitives or `analyze_builtin`), backend CSV/JSON
 parsing and backend+heuristic merging with per-metric sourcing (cognitive is
 NEVER attributed to a tool), coverage parsing (cobertura + lcov) and CRAP
 assembly, custom-gate evaluation (metric-form evaluated here, command-form
 deferred to the skill), threshold pass/fail + report shape, and main()'s exit
 codes. Backends are exercised by mocking shutil.which / subprocess.run so the
@@ -592,10 +596,26 @@ class TestBranchCount(unittest.TestCase):
 
     def test_word_boundary_avoids_identifiers(self):
         # 'ifield' / 'forum' must not be counted as if/for
         self.assertEqual(qg._branch_count("ifield = forum + whilehouse\n"), 1)
 
+    def test_csharp_foreach_counts_exactly_one_branch(self):
+        # D2: `foreach` was not a branch word. Measured before: 1 (base only).
+        # After: 2. The tuple's earlier "for" alternative fails its trailing
+        # \b inside `foreach`, so the engine backtracks to the `foreach`
+        # alternative and the keyword is counted ONCE, not twice.
+        self.assertEqual(
+            qg._branch_count("foreach (var r in rows) { }\n"), 2)
+
+    def test_camel_case_for_each_is_not_a_branch_word(self):
+        # The match must stay case-sensitive and \b-anchored: JS/Java/Kotlin
+        # `arr.forEach(...)` is a method call, not a loop keyword, and the
+        # differential harness floors are pinned at EQUALITY against files
+        # that contain it.
+        self.assertEqual(qg._branch_count("arr.forEach(x => x);\n"), 1)
+        self.assertEqual(qg._BRANCH_WORD_RE.findall("arr.forEach(x)"), [])
+
 
 class TestNesting(unittest.TestCase):
     def test_python_nesting_by_indent(self):
         lines = [
             "    if a:",           # base_indent 4, level 0
@@ -1988,10 +2008,28 @@ CS_MULTI_DECL_USING_SOURCE = (
     "        }\n"
     "    }\n"
     "}\n"
 )
 
+# r1-F1 follow-up (s2): the same shape with the DOMINANCE reversed. The
+# `using` header declares 5 comma items, the enclosing Go declares 6, so
+# _phantom_has_more_params does NOT keep the phantom and it is dropped.
+# Measured: {'Go': 6} for a full [(1, 400)] range and for a narrow
+# [(4, 6)] range covering only the using block -- the dropped count is
+# never the file's highest, and the enclosing record is always emitted
+# alongside because its span strictly contains the phantom's.
+CS_DOMINATED_USING_SOURCE = (
+    "public class C\n"
+    "{\n"
+    "    public void Go(int a,int b,int c,int d,int e,int f) {\n"
+    "        using (Stream p = A(), q = B(), r = C(), s = D(), t = E()) {\n"
+    "            p.Write(q);\n"
+    "        }\n"
+    "    }\n"
+    "}\n"
+)
+
 JAVA_SYNCHRONIZED_SOURCE = (
     "public class Cache\n"
     "{\n"
     "    public void put(String k, Object v) {\n"
     "        synchronized (this) {\n"
@@ -2015,10 +2053,30 @@ JS_RESERVED_NAME_METHODS = (
     "        return 2;\n"
     "    }\n"
     "}\n"
 )
 
+# D2: `foreach` was absent from _BRANCH_WORDS, so a C# foreach loop added no
+# cyclomatic branch. Measured on this fixture BEFORE the fix: Go scored
+# cyclomatic_complexity 4 (1 base + if + && + case) and cognitive 8, with
+# the foreach contributing nothing. AFTER: 5 and 10. K&R braces, so the
+# real enclosing method IS extracted and the branch is attributed to Go
+# rather than to a phantom (s1's enclosure suppression drops the phantom
+# here, which is why this slice was ordered after s1).
+CS_FOREACH_CONTROL_SOURCE = (
+    "public class C\n"
+    "{\n"
+    "    public void Go(List<Row> rows) {\n"
+    "        foreach (var r in rows) {\n"
+    "            if (r.A && r.B) { X(r); }\n"
+    "        }\n"
+    "        switch (rows.Count) { case 1: Y(); break; }\n"
+    "    }\n"
+    "}\n"
+)
+
+
 FULL = [(1, 400)]
 
 
 class TestExtensionScopedControlWords(unittest.TestCase):
     """The per-extension reserved words suppress a phantom record ONLY when an
@@ -2078,20 +2136,23 @@ class TestExtensionScopedControlWords(unittest.TestCase):
 
     def test_a_kandr_csharp_method_drops_its_enclosed_phantoms(self):
         # Measured before: 4 records -- Import (3-11, cc 2, cog 3) plus
         # foreach (4-6, cc 2), using (7-9, cc 1) and lock (10-10, cc 1), all
         # three inside Import's span. After: Import alone, metrics unchanged.
+        # s2: adding `foreach` to _BRANCH_WORDS raises Import's own count --
+        # cyclomatic 2 -> 3, cognitive 3 -> 5 (the foreach is at brace depth 1,
+        # so _cognitive_approx weights it x2). The extraction list is unchanged.
         self.assertEqual(
             qg._extract_functions_cbrace(CS_KR_SOURCE.splitlines(), ".cs"),
             [{"name": "Import", "start": 3, "end": 11, "header_idx": 2}])
         found = self.by_name("Importer.cs", CS_KR_SOURCE)
         self.assertEqual(sorted(found), ["Import"])
         self.assertEqual(found["Import"]["metrics"], {
-            "cyclomatic_complexity": 2,
+            "cyclomatic_complexity": 3,
             "method_lines": 9,
             "parameter_count": 2,
-            "cognitive_complexity": 3,
+            "cognitive_complexity": 5,
             "nesting_depth": 2,
         })
 
     def test_a_java_synchronized_block_drops_inside_its_method(self):
         # Measured before: put (3-7, cc 2, cog 3, nest 2) AND the phantom
@@ -2110,20 +2171,22 @@ class TestExtensionScopedControlWords(unittest.TestCase):
         # _CBRACE_DEF_RE misses the method, and the `foreach` record (5-9,
         # cc 5, cog 8, ml 5, nest 1) is the ONLY measurement of that body.
         # Measured: unconditional suppression collapses this file to
         # class_lines alone. Nothing extracted encloses line 5, so the
         # record is KEPT, before and after, with every metric identical.
+        # s2: the retained record's own body now counts its `foreach` too --
+        # cyclomatic 5 -> 6, cognitive 8 -> 9. Retention itself is unchanged.
         self.assertEqual(
             qg._extract_functions_cbrace(CS_MIXED_SOURCE.splitlines(), ".cs"),
             [{"name": "foreach", "start": 5, "end": 9, "header_idx": 4}])
         found = self.by_name("Importer.cs", CS_MIXED_SOURCE)
         self.assertEqual(sorted(found), ["foreach"])
         self.assertEqual(found["foreach"]["metrics"], {
-            "cyclomatic_complexity": 5,
+            "cyclomatic_complexity": 6,
             "method_lines": 5,
             "parameter_count": 1,
-            "cognitive_complexity": 8,
+            "cognitive_complexity": 9,
             "nesting_depth": 1,
         })
 
     def test_javascript_methods_named_lock_fixed_and_using_survive(self):
         # The safety regression the extension scoping exists to prevent: add
@@ -2194,10 +2257,44 @@ class TestExtensionScopedControlWords(unittest.TestCase):
         self.assertEqual(found["using"]["metrics"]["parameter_count"], 5)
         self.assertGreater(
             found["using"]["metrics"]["parameter_count"],
             qg.DEFAULT_THRESHOLDS["parameter_count"])
 
+    def test_a_csharp_foreach_adds_a_branch_to_its_enclosing_method(self):
+        # D2, end to end through analyze_builtin so a mis-wired routing fails
+        # here rather than passing on a hand-composed _branch_count call.
+        # Measured before: Go cyclomatic 4, cognitive 8. After: 5 and 10 --
+        # the foreach sits at brace depth 1, so _cognitive_approx weights it
+        # x2. Every other metric is unchanged.
+        found = self.by_name("C.cs", CS_FOREACH_CONTROL_SOURCE)
+        self.assertEqual(sorted(found), ["Go"])
+        self.assertEqual(found["Go"]["metrics"], {
+            "cyclomatic_complexity": 5,
+            "method_lines": 6,
+            "parameter_count": 1,
+            "cognitive_complexity": 10,
+            "nesting_depth": 2,
+        })
+
+    def test_a_dominated_using_is_dropped_only_behind_a_higher_count(self):
+        # The narrow guarantee the CHANGELOG now states, pinned rather than
+        # argued: suppression's per-metric safety for parameter_count rests on
+        # BOTH halves. When the phantom's own count is higher it survives
+        # (test_an_enclosed_multi_declaration_using_keeps_its_own_finding);
+        # when it is lower it is dropped, and the enclosing record that
+        # replaces it carries a HIGHER count and is emitted for any changed
+        # range that could have reached the phantom -- its span strictly
+        # contains the phantom's.
+        for ranges in ([(1, 400)], [(4, 6)]):
+            findings, _ = qg.analyze_builtin(
+                "C.cs", CS_DOMINATED_USING_SOURCE, ranges)
+            counts = {f["function"]: f["metrics"]["parameter_count"]
+                      for f in findings}
+            self.assertEqual(counts, {"Go": 6})
+            self.assertGreater(
+                counts["Go"], qg.DEFAULT_THRESHOLDS["parameter_count"])
+
 
 # --------------------------------------------------------------------------
 # D3: measure()'s skip chain ended in `elif _lang_for(path) is None`, so a
 # SUPPORTED file that yielded zero callables produced neither a function
 # measurement nor a skip record -- it vanished from the report entirely.
