# Review package: 299f0dbd1f700f8f3b3991ea7d601df797dd3749..17be9d4  (context: -U5)

## Commits
17be9d4 quality-gate: differential harness pins masked scans against raw over the tree
d27656c quality-gate: branch scans read the masked source, every other metric reads raw
a3486ef quality-gate: tokenize-based scan mask for python literals and comments

## Files changed
 plugins/spec-loop/scripts/quality_gate.py      | 205 ++++++++++++++++---
 plugins/spec-loop/scripts/test_quality_gate.py | 263 +++++++++++++++++++++++++
 2 files changed, 445 insertions(+), 23 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/quality_gate.py": [
[
30,
34
],
[
56,
56
],
[
63,
63
],
[
424,
549
],
[
697,
739
],
[
745,
747
],
[
755,
756
],
[
761,
761
],
[
765,
765
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
27,
27
],
[
37,
73
],
[
370,
460
],
[
541,
581
],
[
1032,
1124
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index 2b397e8..cf5764b 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -25,11 +25,15 @@ Pipeline:
      function is measured only when its line span intersects a changed range.
   4. Builtin heuristic -- for any changed file no backend covers, a pure-stdlib
      analyzer splits the source into functions by signature regex (python / js /
      ts / java / c# / go styles, language by extension) and estimates each
      metric by branch-keyword counting, signature parsing, and indent/brace
-     nesting. Every such finding is marked "source": "builtin-heuristic".
+     nesting. Branch counting reads a masked copy of the source in which the
+     content of python string literals and comments has been replaced by a
+     sentinel, so words and punctuation inside them are not measured as
+     branching; a tokenizer failure falls back to the raw text. Every such
+     finding is marked "source": "builtin-heuristic".
      cognitive_complexity is ONLY ever produced by this heuristic (a
      nesting-weighted approximation) or skipped -- it is never attributed to a
      real tool.
   5. crap_score -- only when a coverage report is found (--coverage, else a
      probe of the repo root for coverage.xml / lcov.info / cobertura*.xml).
@@ -47,16 +51,18 @@ Usage:
     quality_gate.py --config <path> --base <ref> [--head HEAD]
                     [--repo-dir .] [--coverage <path>]
 """
 
 import argparse
+import io
 import json
 import os
 import re
 import shutil
 import subprocess
 import sys
+import tokenize
 import xml.etree.ElementTree as ET
 
 # The default thresholds mirror the quality-gate skill's table (SKILL.md) and
 # the /spec-loop:quality-gate command's "Recommended" level, so the builtin
 # fallback and any custom config stay consistent with the documented bar.
@@ -413,10 +419,136 @@ def _count_params(sig):
     if names and names[0] in ("self", "cls"):
         names = names[1:]
     return len(names)
 
 
+# --------------------------------------------------------------------------
+# Scan mask -- what the two branch scans are allowed to see
+# --------------------------------------------------------------------------
+# The builtin heuristic used to scan raw source text, so a branch word or a
+# piece of operator punctuation inside a string literal or a comment was
+# measured as real branching. The worst measured example in this repo was a
+# human question ending in a question mark, counted as a ternary and pushing a
+# function to exactly its cognitive threshold. Masking is applied ONLY to the
+# text handed to _branch_count and _cognitive_approx: function extraction,
+# brace depth, method_lines and class_lines all keep reading raw text, because
+# a masked docstring continuation line starts at column 0 and would move the
+# indent-derived end of the enclosing function. Masked spans are filled with a
+# non-whitespace sentinel rather than spaces, because _cognitive_approx derives
+# its nesting level from leading whitespace: space-fill would RAISE the measured
+# cognitive complexity of dozens of functions. Every failure path returns the
+# raw text, so the worst case remains today's over-count.
+
+_SCAN_SENTINEL = "x"
+
+# The corruption trip-wire, expressed as a denominator: a mask that leaves more
+# than one line in _MASK_LOST_DENOM of the non-blank lines with no content at
+# all is discarded in favour of raw text. A correct mask empties nothing (the
+# sentinel is non-blank), so any trip here means the span arithmetic went wrong.
+_MASK_LOST_DENOM = 20
+
+
+def _masked_token_types():
+    """Token types whose text is masked out of a branch scan: string literals,
+    comments, and the literal segments of an f-string. An f-string's embedded
+    expression arrives as ordinary tokens and stays visible, so genuine
+    operators inside one are still measured. (PURE)"""
+    types = {tokenize.STRING, tokenize.COMMENT}
+    types.add(getattr(tokenize, "FSTRING_MIDDLE", None))
+    types.discard(None)
+    return frozenset(types)
+
+
+_MASKED_TOKEN_TYPES = _masked_token_types()
+
+
+def _scan_tokens(text):
+    """Tokenized `text`, or None on any tokenizer failure or a non-default end
+    state. Every None return sends the caller back to the raw text. (PURE)"""
+    try:
+        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
+    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
+        return None
+    if not toks:
+        return None
+    if toks[-1].type != tokenize.ENDMARKER:
+        return None
+    return toks
+
+
+def _masked_tokens(toks):
+    """The subset of `toks` whose text gets masked out of a branch scan.
+    (PURE)"""
+    return [tok for tok in toks if tok.type in _MASKED_TOKEN_TYPES]
+
+
+def _mask_line_range(row, start_col, end_col):
+    """`row` with the half-open column range replaced by sentinel characters, so
+    the line keeps its original length. (PURE)"""
+    stop = min(end_col, len(row))
+    width = max(0, stop - start_col)
+    return row[:start_col] + (_SCAN_SENTINEL * width) + row[stop:]
+
+
+def _token_mask_spans(tok, rows):
+    """The (row_index, start_col, end_col) spans one masked token covers, one per
+    physical line it reaches. Row indexes are 0-based into `rows`. A token
+    continuing past its opening line is masked from column 0 to the end of that
+    physical line. (PURE)"""
+    (first_row, first_col), (last_row, last_col) = tok.start, tok.end
+    spans = []
+    for row in range(first_row, last_row + 1):
+        start = 0
+        if row == first_row:
+            start = first_col
+        end = len(rows[row - 1])
+        if row == last_row:
+            end = last_col
+        spans.append((row - 1, start, end))
+    return spans
+
+
+def _mask_lost_too_much(raw_rows, masked_rows):
+    """True once the mask has emptied more than one line in _MASK_LOST_DENOM of
+    the non-blank lines -- the corruption signal that sends the scan back to raw
+    text. (PURE)"""
+    nonblank = sum(1 for row in raw_rows if row.strip())
+    lost = sum(1 for raw, masked in zip(raw_rows, masked_rows)
+               if raw.strip() and not masked.strip())
+    return bool(nonblank) and (lost * _MASK_LOST_DENOM > nonblank)
+
+
+def _mask_python_literals(text):
+    """`text` with every string-literal, comment and f-string-literal span filled
+    with the non-whitespace sentinel, preserving line count and line lengths, or
+    None to fall back to the raw text. (PURE)"""
+    toks = _scan_tokens(text)
+    if toks is None:
+        return None
+    rows = text.split("\n")
+    masked = list(rows)
+    for tok in _masked_tokens(toks):
+        for row_idx, start, end in _token_mask_spans(tok, rows):
+            masked[row_idx] = _mask_line_range(masked[row_idx], start, end)
+    if _mask_lost_too_much(rows, masked):
+        return None
+    return "\n".join(masked)
+
+
+def _strip_for_scan(text, lang):
+    """`text` with string-literal and comment content masked out, so words and
+    punctuation inside literals stop being measured as real branching. Python is
+    masked via stdlib tokenize; every other language is returned unchanged, so
+    the brace scanner keeps its current behaviour. (PURE)"""
+    if lang != "python":
+        return text
+    masked = _mask_python_literals(text)
+    if masked is None:
+        return text
+    return masked
+
+
 def _branch_count(text):
     """Cyclomatic branch count for a block of code (PURE): 1 base path plus one
     per branch keyword / boolean operator / ternary occurrence."""
     return (1
             + len(_BRANCH_WORD_RE.findall(text))
@@ -560,52 +692,79 @@ def _cognitive_approx(body_text_or_lines, lang, base_indent):
 
 def _nonblank(lines):
     return sum(1 for line in lines if line.strip())
 
 
+def _extract_functions_for(lines, lang):
+    """The extracted callables of one file, by language family. (PURE)"""
+    if lang == "python":
+        return _extract_functions_python(lines)
+    return _extract_functions_cbrace(lines)
+
+
+def _nesting_depth_for(body_lines, lang, base_indent):
+    """Nesting depth of one RAW function body, by language family. Always
+    measured on raw text: the mask is for branch scanning only. (PURE)"""
+    if lang == "python":
+        return _nesting_depth_python(body_lines[1:], base_indent)
+    return _nesting_depth_braces("\n".join(body_lines))
+
+
+def _scan_lines_for(source, lang, lines):
+    """The masked counterpart of `lines`, for the two branch scans only. Falls
+    back to `lines` unless the mask preserved the physical line count exactly,
+    so a masked body always covers the same lines as its raw body. (PURE)"""
+    scan_lines = _strip_for_scan(source, lang).splitlines()
+    if len(scan_lines) != len(lines):
+        return lines
+    return scan_lines
+
+
+def _function_metrics(lines, scan_lines, fn, lang):
+    """Measured metric values for one extracted function. `lines` is raw source;
+    `scan_lines` is its masked counterpart, read by the two branch scans alone,
+    so span, indentation and length metrics all stay on raw text. (PURE)"""
+    body_lines = lines[fn["header_idx"]:fn["end"]]
+    scan_body = scan_lines[fn["header_idx"]:fn["end"]]
+    header_line = lines[fn["header_idx"]]
+    base_indent = len(header_line) - len(header_line.lstrip(" "))
+    return {
+        "cyclomatic_complexity": _branch_count("\n".join(scan_body)),
+        "method_lines": _nonblank(body_lines),
+        "parameter_count": _count_params(header_line),
+        "cognitive_complexity": _cognitive_approx(
+            scan_body, lang, base_indent),
+        "nesting_depth": _nesting_depth_for(body_lines, lang, base_indent),
+    }
+
+
 def analyze_builtin(path, source, changed_ranges):
     """Pure-stdlib heuristic analysis of one changed file. Returns
     (function_findings, class_finding_or_None) where each finding is a dict of
     measured metric values for functions intersecting `changed_ranges`, tagged
     source="builtin-heuristic". `source` is the file text; changed_ranges is the
-    file's list of (start, end) changed spans.
+    file's list of (start, end) changed spans. The two branch scans read a
+    masked copy of the source (see _strip_for_scan); every other metric reads
+    the raw text.
 
     An unsupported/binary file (no known language) yields ([], None); the caller
     records a skip for it."""
     lang = _lang_for(path)
     if lang is None:
         return [], None
     lines = source.splitlines()
-    if lang == "python":
-        funcs = _extract_functions_python(lines)
-    else:
-        funcs = _extract_functions_cbrace(lines)
+    scan_lines = _scan_lines_for(source, lang, lines)
+    funcs = _extract_functions_for(lines, lang)
 
     findings = []
     for fn in funcs:
         if not _intersects_changed(fn["start"], fn["end"], changed_ranges):
             continue
-        body_lines = lines[fn["header_idx"]:fn["end"]]
-        body_text = "\n".join(body_lines)
-        header_line = lines[fn["header_idx"]]
-        base_indent = len(header_line) - len(header_line.lstrip(" "))
-        metrics = {
-            "cyclomatic_complexity": _branch_count(body_text),
-            "method_lines": _nonblank(body_lines),
-            "parameter_count": _count_params(header_line),
-            "cognitive_complexity": _cognitive_approx(body_lines, lang,
-                                                       base_indent),
-        }
-        if lang == "python":
-            metrics["nesting_depth"] = _nesting_depth_python(
-                body_lines[1:], base_indent)
-        else:
-            metrics["nesting_depth"] = _nesting_depth_braces(body_text)
         findings.append({
             "file": path, "function": fn["name"],
             "line_start": fn["start"], "line_end": fn["end"],
-            "metrics": metrics,
+            "metrics": _function_metrics(lines, scan_lines, fn, lang),
         })
 
     class_finding = None
     if any(_spans_overlap(1, len(lines), cs, ce) for cs, ce in changed_ranges):
         class_finding = {"file": path, "class_lines": _nonblank(lines)}
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index eae21ee..8d16ba7 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -22,19 +22,57 @@ import json
 import os
 import shutil
 import subprocess
 import sys
 import tempfile
+import tokenize
 import unittest
 from pathlib import Path
 from unittest import mock
 
 sys.path.insert(0, str(Path(__file__).resolve().parent))
 
 import quality_gate as qg  # noqa: E402
 
 
+# --------------------------------------------------------------------------
+# Fixtures for the scan mask. These deliberately carry branch words and
+# operator punctuation INSIDE literals and comments, so they live at module
+# level: the gate measures function bodies, and a fixture like this one inside
+# a test method would be counted as that method's own branching.
+# --------------------------------------------------------------------------
+
+BRANCH_WORDS_IN_LITERALS = "if for while ? && ||"
+
+LITERAL_HEAVY_SOURCE = (
+    "def probe(a, b):\n"
+    '    """Prose mentioning ' + BRANCH_WORDS_IN_LITERALS + '."""\n'
+    "    label = '" + BRANCH_WORDS_IN_LITERALS + "'  # "
+    + BRANCH_WORDS_IN_LITERALS + "\n"
+    "    " + "if" + " a:\n"
+    "        return label\n"
+    "    return b\n"
+)
+
+UNTERMINATED_SOURCE = "def h():\n    x = '''" + BRANCH_WORDS_IN_LITERALS + "\n"
+
+CBRACE_SOURCE_WITH_LITERALS = (
+    "function outer(a) {\n"
+    "    const q = '" + BRANCH_WORDS_IN_LITERALS + "';\n"
+    "    return a ? q : null;\n"
+    "}\n"
+)
+
+
+def unmasked(text, lang):
+    """Identity stand-in for qg._strip_for_scan, so a test can measure the same
+    source the way the gate measured it before the mask existed. Named at module
+    level because a paren-aligned mock.patch.object continuation inside a test
+    body is itself read as nesting by the metric under test."""
+    return text
+
+
 # --------------------------------------------------------------------------
 # parse_diff — pure, embedded fixtures
 # --------------------------------------------------------------------------
 
 class TestParseDiff(unittest.TestCase):
@@ -327,10 +365,101 @@ class TestCognitiveApprox(unittest.TestCase):
     def test_brace_language_weights_by_depth(self):
         lines = ["if (a) {", "    if (b) {", "    }", "}"]
         self.assertGreater(qg._cognitive_approx(lines, "cbrace", 0), 0)
 
 
+# --------------------------------------------------------------------------
+# _strip_for_scan — the mask handed to the two branch scans
+# --------------------------------------------------------------------------
+
+class TestStripForScan(unittest.TestCase):
+    def test_a_non_python_language_is_returned_byte_for_byte(self):
+        # This slice masks python only; the brace scanner keeps today's
+        # behaviour until the follow-up slice.
+        self.assertEqual(
+            qg._strip_for_scan(CBRACE_SOURCE_WITH_LITERALS, "cbrace"),
+            CBRACE_SOURCE_WITH_LITERALS)
+
+    def test_line_count_and_line_lengths_survive_the_mask(self):
+        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
+        raw_rows = LITERAL_HEAVY_SOURCE.split("\n")
+        masked_rows = masked.split("\n")
+        self.assertEqual(len(masked_rows), len(raw_rows))
+        # Hanging rather than paren-aligned continuations in the methods this
+        # slice adds: the gate derives nesting_depth from leading whitespace on
+        # RAW text, which the scan mask deliberately does not touch, so a
+        # paren-aligned argument reads to it as a deeply nested block.
+        self.assertEqual(
+            [len(row) for row in masked_rows],
+            [len(row) for row in raw_rows])
+
+    def test_code_outside_literals_is_left_alone(self):
+        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
+        rows = masked.split("\n")
+        self.assertEqual(rows[0], "def probe(a, b):")
+        self.assertEqual(rows[3].strip(), "if a:")
+        self.assertEqual(rows[5].strip(), "return b")
+
+    def test_masked_spans_are_filled_with_a_non_whitespace_sentinel(self):
+        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
+        docstring_row = masked.split("\n")[1]
+        self.assertTrue(docstring_row.strip())
+        self.assertEqual(set(docstring_row.strip()), {qg._SCAN_SENTINEL})
+
+    def test_a_comment_is_masked_in_the_same_pass(self):
+        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
+        assignment_row = masked.split("\n")[2]
+        self.assertNotIn("#", assignment_row)
+        self.assertIn("label = ", assignment_row)
+
+    def test_the_masked_body_scans_as_one_real_branch(self):
+        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
+        # base path 1 plus the one real branching statement
+        self.assertEqual(qg._branch_count(masked), 2)
+
+    def test_leading_indentation_of_a_code_line_is_preserved(self):
+        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
+        raw_rows = LITERAL_HEAVY_SOURCE.split("\n")
+        masked_rows = masked.split("\n")
+        for raw, got in zip(raw_rows, masked_rows):
+            self.assertEqual(
+                len(raw) - len(raw.lstrip(" ")),
+                len(got) - len(got.lstrip(" ")),
+                msg=raw)
+
+    @unittest.skipUnless(hasattr(tokenize, "FSTRING_MIDDLE"),
+                         "f-string literal segments are separate tokens only "
+                         "on newer pythons")
+    def test_an_embedded_f_string_expression_still_counts(self):
+        # The literal segments of an f-string are masked; the tokens of its
+        # embedded expression are not, so a real conditional inside one is
+        # still measured. Mirrors the JS rule that ${...} content survives.
+        source = "def g(a, b, c):\n    return f'{a " + "if" + " b else c}'\n"
+        masked = qg._strip_for_scan(source, "python")
+        self.assertEqual(qg._branch_count(masked), 2)
+
+
+class TestMaskFailsTowardRaw(unittest.TestCase):
+    def test_a_tokenizer_failure_yields_the_raw_text(self):
+        self.assertIsNone(qg._mask_python_literals(UNTERMINATED_SOURCE))
+        self.assertEqual(
+            qg._strip_for_scan(UNTERMINATED_SOURCE, "python"),
+            UNTERMINATED_SOURCE)
+
+    def test_emptying_too_many_lines_trips_the_corruption_guard(self):
+        raw_rows = ["a = 1", "b = 2", "c = 3"]
+        self.assertTrue(qg._mask_lost_too_much(raw_rows, ["a = 1", "b = 2", "  "]))
+
+    def test_a_small_share_of_emptied_lines_is_tolerated(self):
+        raw_rows = ["a = 1"] * 40
+        masked_rows = ["a = 1"] * 39 + ["  "]
+        self.assertFalse(qg._mask_lost_too_much(raw_rows, masked_rows))
+
+    def test_an_all_blank_file_is_not_treated_as_corruption(self):
+        self.assertFalse(qg._mask_lost_too_much(["", "  "], ["", "  "]))
+
+
 # --------------------------------------------------------------------------
 # Builtin heuristic extraction
 # --------------------------------------------------------------------------
 
 class TestAnalyzeBuiltinPython(unittest.TestCase):
@@ -407,10 +536,51 @@ class TestAnalyzeBuiltinCbrace(unittest.TestCase):
         src = "const handler = (x, y) => {\n    return x + y;\n}\n"
         findings, _ = qg.analyze_builtin("m.ts", src, [(1, 3)])
         self.assertIn("handler", {f["function"] for f in findings})
 
 
+class TestAnalyzeBuiltinMasksLiterals(unittest.TestCase):
+    """Branch words and operator punctuation inside a literal or a comment are
+    not branching, and masking them must not disturb any other metric."""
+
+    def measure(self, source, lang_path):
+        findings, _ = qg.analyze_builtin(
+            lang_path, source, [(1, len(source.splitlines()))])
+        return {f["function"]: f for f in findings}
+
+    def measure_unmasked(self, source, lang_path):
+        with mock.patch.object(qg, "_strip_for_scan", unmasked):
+            return self.measure(source, lang_path)
+
+    def test_only_the_real_branch_is_counted_in_python(self):
+        probe = self.measure(LITERAL_HEAVY_SOURCE, "m.py")["probe"]
+        self.assertEqual(probe["metrics"]["cyclomatic_complexity"], 2)
+        self.assertEqual(probe["metrics"]["cognitive_complexity"], 2)
+
+    def test_the_span_and_the_shape_metrics_are_untouched(self):
+        probe = self.measure(LITERAL_HEAVY_SOURCE, "m.py")["probe"]
+        self.assertEqual((probe["line_start"], probe["line_end"]), (1, 6))
+        self.assertEqual(probe["metrics"]["method_lines"], 6)
+        self.assertEqual(probe["metrics"]["nesting_depth"], 2)
+        self.assertEqual(probe["metrics"]["parameter_count"], 2)
+
+    def test_a_brace_language_keeps_todays_counts(self):
+        outer = self.measure(CBRACE_SOURCE_WITH_LITERALS, "m.js")["outer"]
+        raw = self.measure_unmasked(CBRACE_SOURCE_WITH_LITERALS, "m.js")
+        self.assertEqual(outer["metrics"], raw["outer"]["metrics"])
+
+    def test_an_untokenizable_python_file_still_yields_raw_counts(self):
+        broken = "def probe(a):\n    return a  # " + BRANCH_WORDS_IN_LITERALS \
+                 + "\n    x = '''open\n"
+        findings, _ = qg.analyze_builtin(
+            "m.py", broken, [(1, len(broken.splitlines()))])
+        probe = next(f for f in findings if f["function"] == "probe")
+        self.assertGreater(probe["metrics"]["cyclomatic_complexity"], 1)
+        raw = self.measure_unmasked(broken, "m.py")["probe"]
+        self.assertEqual(probe["metrics"], raw["metrics"])
+
+
 class TestMatchBraceEnd(unittest.TestCase):
     def test_balances_nested_braces(self):
         lines = ["f() {", "  { }", "}"]
         self.assertEqual(qg._match_brace_end(lines, 0), 2)
 
@@ -857,7 +1027,100 @@ class TestEndToEndRealGit(unittest.TestCase):
         self.assertEqual(rc, 1)
         self.assertFalse(report["summary"]["pass"])
         self.assertTrue(report["summary"]["failures"])
 
 
+# --------------------------------------------------------------------------
+# Differential harness — masked versus raw over the whole plugin tree
+# --------------------------------------------------------------------------
+# The mask is a measurement change to a blocking control, so it is pinned
+# against the measurement it replaces over real source rather than fixtures
+# alone: every .py, .js and .mjs file under the plugin root is measured twice,
+# once through the mask and once through the identity stand-in that reproduces
+# the pre-mask behaviour. Those three suffixes were the only heuristic-readable
+# ones present in the tree at the time of writing; a source file in one of the
+# other extensions _EXT_LANG covers would not be walked by this harness.
+
+PLUGIN_ROOT = Path(__file__).resolve().parents[1]
+SCANNED_SUFFIXES = (".py", ".js", ".mjs")
+
+# The mask is allowed to lower these two. The other three are measured on raw
+# text, so they must come back identical, as must the function's span.
+LOWERABLE_METRICS = ("cyclomatic_complexity", "cognitive_complexity")
+UNCHANGED_METRICS = ("nesting_depth", "method_lines", "parameter_count")
+
+
+def scanned_sources():
+    """Every .py, .js and .mjs file under the plugin root, sorted. Walks the
+    real tree, so it is not PURE."""
+    found = []
+    for path in sorted(PLUGIN_ROOT.rglob("*")):
+        if path.suffix in SCANNED_SUFFIXES and path.is_file():
+            found.append(path)
+    return found
+
+
+class TestDifferentialAgainstRawScan(unittest.TestCase):
+    """The mask may only ever LOWER a complexity count, and it may never move a
+    function's span, its nesting depth, its length or its parameter count.
+    Measured over the plugin tree's own source, masked against raw."""
+
+    def analyze(self, path, source):
+        findings, _ = qg.analyze_builtin(
+            str(path), source, [(1, len(source.splitlines()))])
+        return {(f["function"], f["line_start"]): f for f in findings}
+
+    def analyze_unmasked(self, path, source):
+        with mock.patch.object(qg, "_strip_for_scan", unmasked):
+            return self.analyze(path, source)
+
+    def assertNoRegression(self, got, was, where):
+        for name in LOWERABLE_METRICS:
+            self.assertLessEqual(
+                got["metrics"][name], was["metrics"][name], msg=where)
+        for name in UNCHANGED_METRICS:
+            self.assertEqual(
+                got["metrics"][name], was["metrics"][name], msg=where)
+        self.assertEqual(
+            (got["line_start"], got["line_end"]),
+            (was["line_start"], was["line_end"]), msg=where)
+
+    def measure_tree(self):
+        """Every scanned file measured twice, as (where, masked, unmasked)
+        triples of one function's findings. The two measurements must cover the
+        same set of functions, so that is asserted here."""
+        pairs = []
+        for path in scanned_sources():
+            source = path.read_text(encoding="utf-8")
+            new = self.analyze(path, source)
+            old = self.analyze_unmasked(path, source)
+            self.assertEqual(sorted(new), sorted(old), msg=str(path))
+            for key, got in new.items():
+                pairs.append(("%s %s" % (path, key), got, old[key]))
+        return pairs
+
+    def test_the_plugin_tree_is_actually_being_scanned(self):
+        paths = scanned_sources()
+        self.assertGreaterEqual(len(paths), 26)
+        suffixes = {path.suffix for path in paths}
+        self.assertIn(".py", suffixes)
+        self.assertTrue(".js" in suffixes or ".mjs" in suffixes)
+
+    def test_no_function_gets_more_complex_and_no_span_moves(self):
+        pairs = self.measure_tree()
+        for where, got, was in pairs:
+            self.assertNoRegression(got, was, where)
+        # The tree measured well over a thousand functions at the time this
+        # harness was written; a collapse to a handful would mean the walk
+        # stopped finding files rather than that the mask is safe.
+        self.assertGreater(len(pairs), 1000)
+
+    def test_the_mask_measurably_lowers_something(self):
+        # A harness that would pass on a no-op mask proves nothing, so pin that
+        # the mask actually moves numbers somewhere in the tree.
+        moved = [where for where, got, was in self.measure_tree()
+                 if got["metrics"] != was["metrics"]]
+        self.assertGreater(len(moved), 100)
+
+
 if __name__ == "__main__":
     unittest.main()
