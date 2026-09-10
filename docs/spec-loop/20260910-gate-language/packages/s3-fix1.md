# Review package: 26adcad..fb7a3f1  (context: -U5)

## Commits
fb7a3f1 test(quality-gate): pin tab-indented method header base_indent site
24f9529 docs(changelog): fix a dangling residual reference in the s1 entry Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
aa28c6a fix(quality-gate): expand tabs in the python nesting and cognitive indent model

## Files changed
 CHANGELOG.md                                   | 35 ++++++++++-
 plugins/spec-loop/scripts/quality_gate.py      | 19 +++++-
 plugins/spec-loop/scripts/test_quality_gate.py | 84 ++++++++++++++++++++++++++
 3 files changed, 132 insertions(+), 6 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
10,
39
],
[
61,
62
]
],
"plugins/spec-loop/scripts/quality_gate.py": [
[
899,
911
],
[
1089,
1089
],
[
1121,
1121
],
[
1177,
1177
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
636,
719
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 09d4f61..dd02ecd 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -5,10 +5,40 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 ### Fixed
+- **A tab-indented python file was measured as if it had no nesting at all, and now
+  measures the same as the identical space-indented file.** `_nesting_depth_python` and the
+  python arm of `_cognitive_approx` in `plugins/spec-loop/scripts/quality_gate.py` stripped
+  leading SPACES only (`lstrip(" ")`) before dividing by the model's 4-column step, so every
+  line of a tab-indented file read as indent 0 and the whole file collapsed to
+  `nesting_depth` 0 at any real depth. Measured on one six-level-deep body: space-indented it
+  reports cognitive 20 / nesting_depth 6 and FAILS the nesting threshold of 3; the
+  byte-identical tab-indented body reported cognitive 5 / nesting_depth 0 and PASSED, on the
+  same branch count (cyclomatic 6 either way). The new PURE `_py_indent_width` is now the
+  single place leading whitespace becomes a column count — it expands tabs at 4 columns,
+  matching the `// 4` the nesting and cognitive models divide by, so one tab is exactly one
+  level — and the three space-only sites (`_nesting_depth_python`, the `_cognitive_approx`
+  python arm, and `_function_metrics`' `base_indent`) call it. `test_quality_gate.py` gains
+  `TestTabIndentedPython`, pinning tab/space parity and the helper itself, including a
+  tab-indented method whose own `def` header is indented (not just a top-level function at
+  column 0), which is the shape that exercises `_function_metrics`'s `base_indent` call
+  specifically. **This changes
+  existing `.py` results upward**: a tab-indented python function that passes the gate today
+  can fail after this change. That is the safe direction under the never-under-count rule and
+  is the intended effect, but it is an observable behaviour change, not merely internal.
+  Known, documented residuals: `_extract_functions_python` still measures indent with a bare
+  `lstrip()` and is deliberately left alone — it compares a header against its own body with
+  one consistent measure, so it already spans a tab-indented file correctly, and expanding
+  there was measured to SHRINK a mixed tab-and-space function's span (a four-line method
+  dropping to one), which would be a new under-count. The 4-column tab step is HARDCODED,
+  deliberately: the indent step stays at 4 and is not parameterised, since no 2-space
+  language is routed to this model. A file mixing tabs and spaces inconsistently is measured
+  by column width alone, which can disagree with python's own tokenizer (tabs at 8); no such
+  file exists in this repo and none is handled specially. The mask-span helper's own
+  `lstrip(" ")` is left as-is on purpose: it picks a raw column index, not a width.
 - **The quality gate's C-family control-keyword guard is now scoped to the language that
   reserves the word, and suppresses a phantom record only when the real enclosing method was
   itself measured.** `plugins/spec-loop/scripts/quality_gate.py` keys the new
   `_CONTROL_WORDS_BY_EXT` map by file extension — `foreach`/`using`/`lock`/`fixed` for `.cs`,
   `synchronized` for `.java` — while the nine words in `_CONTROL_WORDS` stay global; the
@@ -26,13 +56,12 @@ All notable changes to the spec-loop plugin are documented here. The format is
   blanket: an enclosed phantom's cyclomatic, cognitive, method_lines and nesting_depth are
   all dominated by the enclosing record whose body contains it, but its `parameter_count` is
   read from its own header and is NOT — see the `_phantom_has_more_params` entry below.
   Known, documented residuals: a pure-Allman C# file (every brace on its own line, the
   Visual Studio default) still extracts nothing at all, because `_CBRACE_DEF_RE` requires
-  the `{` on the signature line — deferred to its own run. (The second residual named here
-  — `foreach` absent from `_BRANCH_WORDS` — is fixed below in this same Unreleased
-  section.)
+  the `{` on the signature line — deferred to its own run. (A related residual — `foreach`
+  absent from `_BRANCH_WORDS` — is fixed below in this same Unreleased section.)
 - **A changed file the quality gate could not measure can no longer vanish from the report.**
   `measure()` in `plugins/spec-loop/scripts/quality_gate.py` ended its skip chain in
   `elif _lang_for(path) is None`, so a file with a supported extension that yielded zero
   callables produced neither a function measurement nor a `skipped` entry — measured on a
   pure-Allman `.cs` file and a `def`-less `.py` file, `skipped` named neither. The chain now
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index 9fcfa74..8c24703 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -894,10 +894,23 @@ def _branch_count(text):
     return (1
             + len(_BRANCH_WORD_RE.findall(text))
             + len(_BRANCH_OPS_RE.findall(text)))
 
 
+def _py_indent_width(line):
+    """Leading-whitespace width of one python source line, in COLUMNS, with
+    tabs expanded. The step is 4 to match the `// 4` the nesting and
+    cognitive models divide by, so one tab reads as exactly one nesting
+    level; expanding at python's own default of 8 would read it as two.
+    The three indent measurements that feed those models go through here:
+    they used to strip spaces alone (`lstrip(" ")`), so a tab-indented file
+    measured indent 0 on every line and collapsed to nesting_depth 0 at any
+    real depth. (PURE)"""
+    lead = line[:len(line) - len(line.lstrip())]
+    return len(lead.expandtabs(4))
+
+
 def _extract_functions_python(lines):
     """Split python source (list of lines, 0-based) into functions by indent.
     Returns [{name, start, end, header_idx}] with 1-based inclusive line spans.
     A function's body runs to the LAST non-blank line more-indented than its
     `def`; trailing blank lines (and the blank gap before the next definition)
@@ -1071,11 +1084,11 @@ def _nesting_depth_python(body_lines, base_indent):
     4-space-equivalent steps beyond the def's own indent. PURE."""
     max_depth = 0
     for line in body_lines:
         if not line.strip():
             continue
-        indent = len(line) - len(line.lstrip(" "))
+        indent = _py_indent_width(line)
         depth = max(0, (indent - base_indent)) // 4
         max_depth = max(max_depth, depth)
     return max_depth
 
 
@@ -1103,11 +1116,11 @@ def _cognitive_approx(body_text_or_lines, lang, base_indent):
     if lang == "python":
         for line in body_text_or_lines:
             stripped = line.strip()
             if not stripped:
                 continue
-            indent = len(line) - len(line.lstrip(" "))
+            indent = _py_indent_width(line)
             level = max(0, (indent - base_indent)) // 4
             hits = (len(_BRANCH_WORD_RE.findall(stripped))
                     + len(_BRANCH_OPS_RE.findall(stripped)))
             score += hits * (1 + level)
     else:
@@ -1159,11 +1172,11 @@ def _function_metrics(lines, scan_lines, fn, lang):
     `scan_lines` is its masked counterpart, read by the two branch scans alone,
     so span, indentation and length metrics all stay on raw text. (PURE)"""
     body_lines = lines[fn["header_idx"]:fn["end"]]
     scan_body = scan_lines[fn["header_idx"]:fn["end"]]
     header_line = lines[fn["header_idx"]]
-    base_indent = len(header_line) - len(header_line.lstrip(" "))
+    base_indent = _py_indent_width(header_line)
     return {
         "cyclomatic_complexity": _branch_count("\n".join(scan_body)),
         "method_lines": _nonblank(body_lines),
         "parameter_count": _count_params(header_line),
         "cognitive_complexity": _cognitive_approx(
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index 5091928..6ef0d14 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -631,10 +631,94 @@ class TestNesting(unittest.TestCase):
     def test_brace_nesting_two_levels(self):
         self.assertEqual(
             qg._nesting_depth_braces("{ if(x){ while(y){ z; } } }"), 2)
 
 
+# A six-level-deep python body, and the byte-identical body with each
+# four-space indent run replaced by a single tab. Measured before the tab
+# fix: the space form reported cognitive 20 / nesting_depth 6, the tab form
+# cognitive 5 / nesting_depth 0 -- every line read as indent 0.
+DEEP_PY_SPACES = (
+    "def deep(a, b, c):\n"
+    "    if a:\n"
+    "        for i in b:\n"
+    "            if c:\n"
+    "                while a:\n"
+    "                    if b and c:\n"
+    "                        return i\n"
+    "    return 0\n"
+)
+DEEP_PY_TABS = "\n".join(
+    line.replace("    ", "\t") for line in DEEP_PY_SPACES.split("\n"))
+
+# The same six-level-deep body, but as a method: the `def` header itself is
+# indented one level inside a class. This pins _function_metrics's own
+# base_indent = _py_indent_width(header_line) line, which DEEP_PY_SPACES /
+# DEEP_PY_TABS above never exercise -- their top-level `def deep` sits at
+# column 0 in both variants, so base_indent is 0 under the old formula too.
+DEEP_PY_METHOD_SPACES = (
+    "class C:\n"
+    "    def deep(self, a, b, c):\n"
+    "        if a:\n"
+    "            for i in b:\n"
+    "                if c:\n"
+    "                    while a:\n"
+    "                        if b and c:\n"
+    "                            return i\n"
+    "        return 0\n"
+)
+DEEP_PY_METHOD_TABS = "\n".join(
+    line.replace("    ", "\t")
+    for line in DEEP_PY_METHOD_SPACES.split("\n"))
+
+
+class TestTabIndentedPython(unittest.TestCase):
+    """The indent model must read a tab as one nesting step. Before this
+    fix _nesting_depth_python and the python arm of _cognitive_approx
+    stripped only spaces, so a tab-indented file collapsed to depth 0 and
+    passed the nesting threshold of 3 at any real depth -- an under-count,
+    the one direction this heuristic is never allowed to move."""
+
+    def metrics(self, source):
+        """Builtin metrics for one whole-file python source string."""
+        findings, _ = qg.analyze_builtin("m.py", source, [(1, 8)])
+        return findings[0]["metrics"]
+
+    def test_a_tab_indented_body_reports_real_nesting_depth(self):
+        got = self.metrics(DEEP_PY_TABS)
+        self.assertEqual(got["nesting_depth"], 6)
+        self.assertGreater(
+            got["nesting_depth"],
+            qg.DEFAULT_THRESHOLDS["nesting_depth"])
+
+    def test_tabs_and_spaces_measure_identically(self):
+        self.assertEqual(
+            self.metrics(DEEP_PY_TABS), self.metrics(DEEP_PY_SPACES))
+
+    def test_a_tab_indented_method_header_reports_real_nesting_depth(self):
+        """Pins _function_metrics's base_indent line: a tab-indented `def`
+        header that is itself indented (a method, not a top-level function)
+        must still measure the real nesting depth of its body."""
+        got = self.metrics(DEEP_PY_METHOD_TABS)
+        self.assertEqual(got["nesting_depth"], 6)
+        self.assertGreater(
+            got["nesting_depth"],
+            qg.DEFAULT_THRESHOLDS["nesting_depth"])
+
+    def test_tabs_and_spaces_measure_identically_for_a_method(self):
+        self.assertEqual(
+            self.metrics(DEEP_PY_METHOD_TABS),
+            self.metrics(DEEP_PY_METHOD_SPACES))
+
+    def test_the_helper_expands_a_tab_to_one_indent_step(self):
+        self.assertEqual(qg._py_indent_width("\tif a:"), 4)
+        self.assertEqual(qg._py_indent_width("        if a:"), 8)
+        self.assertEqual(qg._py_indent_width("\t    if a:"), 8)
+        self.assertEqual(qg._py_indent_width("if a:"), 0)
+        self.assertEqual(qg._py_indent_width(""), 0)
+
+
 class TestCrapScore(unittest.TestCase):
     def test_full_coverage_equals_complexity(self):
         # CRAP with 100% coverage collapses to the complexity itself
         self.assertAlmostEqual(qg.crap_score(10, 1.0), 10)
