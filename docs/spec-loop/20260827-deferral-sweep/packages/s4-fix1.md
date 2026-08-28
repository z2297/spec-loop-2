# Review package: 17be9d4..d3c3ddd  (context: -U5)

## Commits
d3c3ddd quality-gate tests: hoist mock stand-ins to module level to avoid hanging-indent nesting
db5703f quality-gate: fix mask column-0 bug, add corruption/scan-token coverage
07ed541 quality-gate: test docstring matches the mask coverage that exists

## Files changed
 plugins/spec-loop/scripts/quality_gate.py      |  18 +++--
 plugins/spec-loop/scripts/test_quality_gate.py | 105 ++++++++++++++++++++++++-
 2 files changed, 114 insertions(+), 9 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/quality_gate.py": [
[
494,
500
],
[
504,
507
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
6,
11
],
[
69,
81
],
[
91,
114
],
[
481,
495
],
[
517,
547
],
[
668,
681
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index cf5764b..05a62d1 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -489,20 +489,24 @@ def _mask_line_range(row, start_col, end_col):
     return row[:start_col] + (_SCAN_SENTINEL * width) + row[stop:]
 
 
 def _token_mask_spans(tok, rows):
     """The (row_index, start_col, end_col) spans one masked token covers, one per
-    physical line it reaches. Row indexes are 0-based into `rows`. A token
-    continuing past its opening line is masked from column 0 to the end of that
-    physical line. (PURE)"""
+    physical line it reaches. Row indexes are 0-based into `rows`. On the
+    opening physical line, masking starts at the token's own start column. On
+    every later physical line, masking starts after that row's own leading
+    spaces rather than at column 0, so the sentinel fill never erases the
+    leading whitespace a downstream nesting-level reader derives from that
+    row: leading whitespace carries no branch words or operator punctuation,
+    so leaving it unmasked is measurement-neutral. (PURE)"""
     (first_row, first_col), (last_row, last_col) = tok.start, tok.end
     spans = []
     for row in range(first_row, last_row + 1):
-        start = 0
-        if row == first_row:
-            start = first_col
-        end = len(rows[row - 1])
+        line = rows[row - 1]
+        start = first_col if row == first_row else (
+            len(line) - len(line.lstrip(" ")))
+        end = len(line)
         if row == last_row:
             end = last_col
         spans.append((row - 1, start, end))
     return spans
 
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index 8d16ba7..b8025df 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -1,12 +1,16 @@
 #!/usr/bin/env python3
 """Tests for the objective code-quality gate (stdlib unittest).
 
 Covers the PURE diff parser on embedded fixture text, config loading (defaults /
 loaded / disabled / malformed), the pure metric primitives (parameter counting,
-branch counting, nesting depth, CRAP, cognitive approximation), the builtin
-heuristic function extraction for python and brace languages, backend CSV/JSON
+branch counting, nesting depth, CRAP, cognitive approximation), the scan mask
+that hides python string-literal and comment content from the two branch
+scans (including its fall-back-to-raw paths), a differential harness
+comparing masked against raw measurement over every heuristic-readable file
+in the plugin tree, the builtin heuristic function extraction for python and
+brace languages, backend CSV/JSON
 parsing and backend+heuristic merging with per-metric sourcing (cognitive is
 NEVER attributed to a tool), coverage parsing (cobertura + lcov) and CRAP
 assembly, custom-gate evaluation (metric-form evaluated here, command-form
 deferred to the skill), threshold pass/fail + report shape, and main()'s exit
 codes. Backends are exercised by mocking shutil.which / subprocess.run so the
@@ -60,19 +64,56 @@ CBRACE_SOURCE_WITH_LITERALS = (
     "    const q = '" + BRANCH_WORDS_IN_LITERALS + "';\n"
     "    return a ? q : null;\n"
     "}\n"
 )
 
+# A multi-line string literal whose closing row also carries a real ternary
+# after the literal ends. The literal's interior rows are indented to keep
+# them inside the enclosing `if` block for extraction purposes.
+MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE = (
+    "def f(a, b):\n"
+    "    " + "if" + " a:\n"
+    "        s = '''\n"
+    "        text\n"
+    "        ''' " + "if" + " b " + "else" + " 'z'\n"
+    "        return s\n"
+    "    return b\n"
+)
+
 
 def unmasked(text, lang):
     """Identity stand-in for qg._strip_for_scan, so a test can measure the same
     source the way the gate measured it before the mask existed. Named at module
     level because a paren-aligned mock.patch.object continuation inside a test
     body is itself read as nesting by the metric under test."""
     return text
 
 
+NON_ENDMARKER_TAIL_TOKEN = tokenize.TokenInfo(
+    tokenize.NEWLINE, "\n", (1, 0), (1, 1), "\n")
+
+
+def empty_token_stream(readline):
+    """Stand-in for tokenize.generate_tokens yielding no tokens at all. Named
+    at module level for the same paren-alignment reason as `unmasked`."""
+    return iter([])
+
+
+def non_endmarker_token_stream(readline):
+    """Stand-in for tokenize.generate_tokens whose last token is not
+    ENDMARKER. Named at module level for the same paren-alignment reason as
+    `unmasked`."""
+    return iter([NON_ENDMARKER_TAIL_TOKEN])
+
+
+def longer_scan(text, lang):
+    """Stand-in for qg._strip_for_scan that returns one extra physical line,
+    so the caller's line count no longer matches its input. Named at module
+    level for the same paren-alignment reason as `unmasked`."""
+    return text + "\nextra"
+
+
 # --------------------------------------------------------------------------
 # parse_diff — pure, embedded fixtures
 # --------------------------------------------------------------------------
 
 class TestParseDiff(unittest.TestCase):
@@ -435,10 +476,25 @@ class TestStripForScan(unittest.TestCase):
         # still measured. Mirrors the JS rule that ${...} content survives.
         source = "def g(a, b, c):\n    return f'{a " + "if" + " b else c}'\n"
         masked = qg._strip_for_scan(source, "python")
         self.assertEqual(qg._branch_count(masked), 2)
 
+    def test_a_real_branch_on_a_literals_closing_row_keeps_its_nesting_level(self):
+        # A multi-line string literal's closing row can carry real code after
+        # the literal ends. The masked line's leading whitespace must match
+        # the raw line's leading whitespace exactly, or the nesting level
+        # _cognitive_approx derives from that row silently drops.
+        masked = qg._strip_for_scan(
+            MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE, "python")
+        raw_rows = MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE.split("\n")
+        masked_rows = masked.split("\n")
+        for raw, got in zip(raw_rows, masked_rows):
+            self.assertEqual(
+                len(raw) - len(raw.lstrip(" ")),
+                len(got) - len(got.lstrip(" ")),
+                msg=raw)
+
 
 class TestMaskFailsTowardRaw(unittest.TestCase):
     def test_a_tokenizer_failure_yields_the_raw_text(self):
         self.assertIsNone(qg._mask_python_literals(UNTERMINATED_SOURCE))
         self.assertEqual(
@@ -456,10 +512,41 @@ class TestMaskFailsTowardRaw(unittest.TestCase):
 
     def test_an_all_blank_file_is_not_treated_as_corruption(self):
         self.assertFalse(qg._mask_lost_too_much(["", "  "], ["", "  "]))
 
 
+class TestScanTokensFallbackPaths(unittest.TestCase):
+    """_scan_tokens's two guards send the whole mask back to raw text, but
+    stdlib tokenize never produces either shape for real source, so each is
+    driven directly through the real callable with a patched tokenizer."""
+
+    def test_an_empty_token_stream_yields_none(self):
+        with mock.patch.object(qg.tokenize, "generate_tokens", empty_token_stream):
+            self.assertIsNone(qg._scan_tokens("x = 1\n"))
+
+    def test_a_non_endmarker_end_state_yields_none(self):
+        with mock.patch.object(qg.tokenize, "generate_tokens", non_endmarker_token_stream):
+            self.assertIsNone(qg._scan_tokens("x = 1\n"))
+
+    def test_the_corruption_guard_inside_mask_python_literals_falls_back(self):
+        # _mask_lost_too_much itself is exercised directly above; this drives
+        # the guard AS WRITTEN inside _mask_python_literals, forcing the
+        # signal it reacts to rather than trying to construct real source
+        # that trips it (masking never empties a line: the sentinel is
+        # always non-whitespace).
+        with mock.patch.object(qg, "_mask_lost_too_much", return_value=True):
+            self.assertIsNone(qg._mask_python_literals("x = 1\n"))
+
+
+class TestScanLinesForFallback(unittest.TestCase):
+    def test_a_line_count_mismatch_falls_back_to_the_raw_lines(self):
+        source = "x = 1\ny = 2\n"
+        lines = source.splitlines()
+        with mock.patch.object(qg, "_strip_for_scan", longer_scan):
+            self.assertEqual(qg._scan_lines_for(source, "python", lines), lines)
+
+
 # --------------------------------------------------------------------------
 # Builtin heuristic extraction
 # --------------------------------------------------------------------------
 
 class TestAnalyzeBuiltinPython(unittest.TestCase):
@@ -576,10 +663,24 @@ class TestAnalyzeBuiltinMasksLiterals(unittest.TestCase):
         probe = next(f for f in findings if f["function"] == "probe")
         self.assertGreater(probe["metrics"]["cyclomatic_complexity"], 1)
         raw = self.measure_unmasked(broken, "m.py")["probe"]
         self.assertEqual(probe["metrics"], raw["metrics"])
 
+    def test_a_real_branch_after_a_multiline_literal_closes_is_not_undercounted(self):
+        # The masked and unmasked cognitive_complexity must agree exactly:
+        # the real `if`/`else` on the literal's closing row must keep the
+        # nesting weight its own row's indentation implies, never dropping to
+        # a shallower level because the mask overwrote that row's leading
+        # whitespace with the sentinel.
+        masked = self.measure(
+            MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE, "m.py")["f"]
+        raw = self.measure_unmasked(
+            MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE, "m.py")["f"]
+        self.assertEqual(
+            masked["metrics"]["cognitive_complexity"],
+            raw["metrics"]["cognitive_complexity"])
+
 
 class TestMatchBraceEnd(unittest.TestCase):
     def test_balances_nested_braces(self):
         lines = ["f() {", "  { }", "}"]
         self.assertEqual(qg._match_brace_end(lines, 0), 2)
