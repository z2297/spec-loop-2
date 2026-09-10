# Review package: 892a2aab98f10174fc296a8c8cd56a92a71a304c..7aba97e  (context: -U5)

## Commits
7aba97e refactor(gate): resolve the phantom enclosure bound once and drop the state bag
75aa33b test(gate): pin the downward direction of the tab indent model
9e20e1c fix(gate): preserve tab indentation through the python literal mask

## Files changed
 CHANGELOG.md                                   |  36 +++++--
 plugins/spec-loop/scripts/quality_gate.py      | 117 ++++++++++++----------
 plugins/spec-loop/scripts/test_quality_gate.py | 133 +++++++++++++++++++++++--
 3 files changed, 216 insertions(+), 70 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
11,
16
],
[
47,
57
],
[
76,
76
],
[
96,
96
],
[
107,
109
],
[
114,
116
]
],
"plugins/spec-loop/scripts/quality_gate.py": [
[
587,
595
],
[
601,
601
],
[
945,
949
],
[
952,
956
],
[
1007,
1014
],
[
1024,
1046
],
[
1048,
1048
],
[
1051,
1051
],
[
1055,
1059
],
[
1062,
1064
],
[
1075,
1075
],
[
1185,
1188
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
673,
716
],
[
763,
795
],
[
1304,
1341
],
[
2214,
2214
],
[
2313,
2314
],
[
2316,
2321
],
[
2435,
2435
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 0016e0e..5735c74 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -6,11 +6,16 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 ### Fixed
 - **A tab-indented python file was measured as if it had no nesting at all, and now
-  measures the same as the identical space-indented file.** `_nesting_depth_python` and the
+  measures the same as the identical space-indented file.** Parity now survives the
+  literal mask too: the python mask's own continuation-row fill started at `lstrip(" ")` and
+  overwrote a tab-indented row's leading tabs, so a tab body holding a multi-line string
+  whose closing row carries branch operators measured cognitive 10 against the space body's
+  13 -- an under-count, now fixed in `_token_mask_spans` and pinned by
+  `TestTabIndentedPython`. `_nesting_depth_python` and the
   python arm of `_cognitive_approx` in `plugins/spec-loop/scripts/quality_gate.py` stripped
   leading SPACES only (`lstrip(" ")`) before dividing by the model's 4-column step, so every
   line of a tab-indented file read as indent 0 and the whole file collapsed to
   `nesting_depth` 0 at any real depth. Measured on one six-level-deep body: space-indented it
   reports cognitive 20 / nesting_depth 6 and FAILS the nesting threshold of 3; the
@@ -37,14 +42,21 @@ All notable changes to the spec-loop plugin are documented here. The format is
   `lstrip()` and is deliberately left alone — it compares a header against its own body with
   one consistent measure, so it already spans a tab-indented file correctly, and expanding
   there was measured to SHRINK a mixed tab-and-space function's span (a four-line method
   dropping to one), which would be a new under-count. The 4-column tab step is HARDCODED,
   deliberately: the indent step stays at 4 and is not parameterised, since no 2-space
-  language is routed to this model. A file mixing tabs and spaces inconsistently is measured
-  by column width alone, which can disagree with python's own tokenizer (tabs at 8); no such
-  file exists in this repo and none is handled specially. The mask-span helper's own
-  `lstrip(" ")` is left as-is on purpose: it picks a raw column index, not a width.
+  language is routed to this model. Parity is against the 4-column space form specifically,
+  because the `// 4` step is hardcoded: MEASURED on a six-level body indented at TWO spaces
+  per level, the space form reports cognitive 11 / nesting_depth 3 and its tab-converted twin
+  reports cognitive 20 / nesting_depth 6. That is an over-count on the tab side, the
+  permitted direction, but it is not parity. A row whose own leading whitespace mixes tabs
+  and spaces is likewise measured by column width at a 4-column tab, which can disagree with
+  python's own tokenizer at 8. The python mask helper `_token_mask_spans` measures a
+  continuation row's leading whitespace with the same bare `lstrip()` `_py_indent_width`
+  uses, so a masked row keeps its tab indent; it previously used `lstrip(" ")` and
+  under-counted a tab-indented body holding a multi-line string (see the parity note
+  above).
 - **The quality gate's C-family control-keyword guard is now scoped to the language that
   reserves the word, and suppresses a phantom record only when the real enclosing method was
   itself measured.** `plugins/spec-loop/scripts/quality_gate.py` keys the new
   `_CONTROL_WORDS_BY_EXT` map by file extension — `foreach`/`using`/`lock`/`fixed` for `.cs`,
   `synchronized` for `.java` — while the nine words in `_CONTROL_WORDS` stay global; the
@@ -59,11 +71,11 @@ All notable changes to the spec-loop plugin are documented here. The format is
   cyclomatic 5, cognitive 8); suppressing it unconditionally would take the file to
   `class_lines` alone and turn a real reading into a silent pass. An over-count is the one
   direction this heuristic is permitted to move. That safety argument is PER-METRIC, not
   blanket: an enclosed phantom's cyclomatic, cognitive, method_lines and nesting_depth are
   all dominated by the enclosing record whose body contains it, but its `parameter_count` is
-  read from its own header and is NOT — see the `_phantom_has_more_params` entry below.
+  read from its own header and is NOT — see the `_phantom_is_redundant` entry below.
   Known, documented residuals: a pure-Allman C# file (every brace on its own line, the
   Visual Studio default) still extracts nothing at all, because `_CBRACE_DEF_RE` requires
   the `{` on the signature line — deferred to its own run. (A related residual — `foreach`
   absent from `_BRANCH_WORDS` — is fixed below in this same Unreleased section.)
 - **A changed file the quality gate could not measure can no longer vanish from the report.**
@@ -79,29 +91,31 @@ All notable changes to the spec-loop plugin are documented here. The format is
   no threshold and no exit code, and `summary.vacuous` is still read by nothing in the
   per-slice pipeline — only `references/phase-5-integration.md:14` tells any reader to check
   it. Both are deferred, not fixed here.
 - **The control-keyword suppression could itself under-count, on two separate paths, and both
   are closed.** `plugins/spec-loop/scripts/quality_gate.py`'s `_encloses_line` (now
-  `_strictly_encloses_line`) tested only `fn["start"] <= line_no <= fn["end"]`; because `.cs`
+  `_strictly_enclosing_record`) tested only `fn["start"] <= line_no <= fn["end"]`; because `.cs`
   and `.java` are excluded from `_JS_MASK_EXTS`, `_match_brace_end` counts a `}` inside a
   string or char literal on the enclosing method's own header line — e.g.
   `raw.Split('}')` — as a real close, ending the enclosing record's span exactly AT the
   phantom's header line. That equality used to count as enclosure, suppressing the phantom
   even though the enclosing record measures almost none of its body; the bound is now
   exclusive (`line_no < fn["end"]`), and `TestExtensionScopedControlWords` gains
   `test_a_literal_brace_on_the_control_header_line_keeps_its_phantom` pinning the retained
   `foreach` record. Separately, suppression assumed an enclosed phantom's own metrics were
   always dominated by the enclosing record, which is false for `parameter_count`: a C#
   `using (a, b, c, d, e)` can declare more comma-separated items than the enclosing method's
-  own signature. The new PURE `_phantom_has_more_params` compares the phantom's own header
-  against the enclosing record's header and keeps the phantom whenever its count is higher;
+  own signature. The new PURE `_phantom_is_redundant` compares the phantom's own header
+  against the enclosing record's header, and the guard keeps the phantom whenever its own
+  count is higher;
   `test_an_enclosed_multi_declaration_using_keeps_its_own_finding` pins a 5-parameter `using`
   surviving inside a 1-parameter `Import` method (5 > `DEFAULT_THRESHOLDS["parameter_count"]`
   == 4). Both are the same failure family the run's NEVER-UNDER-COUNT constraint names.
   Known, documented residuals: the parameter_count guarantee is an ARGUMENT the code does
-  not assert. `_phantom_has_more_params` keeps a phantom only when its own count is strictly
-  higher, so a phantom whose count is equal or lower is still dropped; that is safe only
+  not assert. `_phantom_is_redundant` reports a phantom redundant when its own count is less
+  than or equal to the enclosing header's, and only a redundant phantom is dropped; a phantom
+  whose count is strictly higher is kept. That is safe only
   because the enclosing record's own count is then at least as high AND is always emitted
   alongside — the enclosing span strictly contains the phantom's, so any changed range that
   reaches the phantom reaches the enclosing record too. Measured both halves on `.cs`:
   `using (Stream p = A(), q = B(), r = C(), s = D(), t = E())` inside `Go(int a)` reports
   `Go` 1 AND `using` 5 (the phantom survives, 5 > the threshold of 4); the same `using`
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index 8c24703..2edc89e 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -582,21 +582,25 @@ def _mask_line_range(row, start_col, end_col):
 
 def _token_mask_spans(tok, rows):
     """The (row_index, start_col, end_col) spans one masked token covers, one per
     physical line it reaches. Row indexes are 0-based into `rows`. On the
     opening physical line, masking starts at the token's own start column. On
-    every later physical line, masking starts after that row's own leading
-    spaces rather than at column 0, so the sentinel fill never erases the
-    leading whitespace a downstream nesting-level reader derives from that
-    row: leading whitespace carries no branch words or operator punctuation,
-    so leaving it unmasked is measurement-neutral. (PURE)"""
+    every later physical line, masking starts after that row's whole
+    leading-whitespace run -- spaces AND tabs, the same bare lstrip()
+    _py_indent_width uses -- so the sentinel fill never erases the indent a
+    downstream nesting-level reader derives from that row. It measured that
+    run with lstrip(" ") until the tab fix made _py_indent_width expand
+    tabs: a tab-indented continuation row then had its tabs overwritten and
+    read as indent 0, UNDER-counting _cognitive_approx. Leading whitespace
+    carries no branch words or operator punctuation, so leaving all of it
+    unmasked is measurement-neutral for the scan itself. (PURE)"""
     (first_row, first_col), (last_row, last_col) = tok.start, tok.end
     spans = []
     for row in range(first_row, last_row + 1):
         line = rows[row - 1]
         start = first_col if row == first_row else (
-            len(line) - len(line.lstrip(" ")))
+            len(line) - len(line.lstrip()))
         end = len(line)
         if row == last_row:
             end = last_col
         spans.append((row - 1, start, end))
     return spans
@@ -936,18 +940,22 @@ def _extract_functions_python(lines):
 
 
 def _cbrace_name_at(lines, ext, funcs, i):
     """The function name detected at 0-based line `i` (else None), tried as a
     brace signature first and an arrow form second. `funcs` is the record list
-    collected so far, needed by the control-keyword guard. Extracted out of
-    _extract_functions_cbrace purely to keep that loop's own nesting shallow;
-    carries no state across calls. (PURE)"""
+    collected so far; this is where the control-keyword guard's enclosure
+    question is resolved, by _strictly_enclosing_record then
+    _phantom_is_redundant, so the guard itself takes a plain boolean.
+    Extracted out of _extract_functions_cbrace purely to keep that loop's own
+    nesting shallow; carries no state across calls. (PURE)"""
     line = lines[i]
     m = _CBRACE_DEF_RE.search(line)
-    state = {"funcs": funcs, "lines": lines}
-    if m and not _looks_like_call_or_control(ext, m, i + 1, state):
-        return m.group(1)
+    if m:
+        enclosing = _strictly_enclosing_record(funcs, i + 1)
+        redundant = _phantom_is_redundant(enclosing, line, lines)
+        if not _looks_like_call_or_control(ext, m, redundant):
+            return m.group(1)
     am = _CBRACE_ARROW_RE.search(line)
     if am:
         return am.group(1)
     return None
 
@@ -994,74 +1002,79 @@ def _control_words_for(ext):
     empty). `ext` is a leading-dot extension; None, "" and any unknown
     extension yield the empty set. (PURE)"""
     return _CONTROL_WORDS_BY_EXT.get((ext or "").lower(), frozenset())
 
 
-def _strictly_encloses_line(funcs, line_no):
-    """True if any already-collected function record STRICTLY contains
-    `line_no`, i.e. `line_no` is not the record's own last line. `funcs` is a
-    list of {name, start, end, header_idx} records whose start/end are
-    1-BASED INCLUSIVE; `line_no` is 1-based.
+def _strictly_enclosing_record(funcs, line_no):
+    """The already-collected function record that STRICTLY contains
+    `line_no`, or None. `funcs` is a list of
+    {name, start, end, header_idx} records whose start/end are 1-BASED
+    INCLUSIVE; `line_no` is 1-based. Records arrive in header order, so the
+    first match is the OUTERMOST enclosing one -- the selection the bare
+    next() this helper replaces already made, preserved deliberately:
+    whichever record encloses the phantom is always emitted alongside it.
 
     The upper bound is exclusive on purpose: a record's span can only reach
     exactly the phantom's header line when a non-JS-masked brace language
     (.cs/.java are excluded from _JS_MASK_EXTS) counts a `}` inside a string
     or char literal ON that header line and balances the enclosing scan to
     depth 0 there. In that case the enclosing record does not actually
     dominate the phantom's body, so equality must not count as enclosure --
     otherwise the phantom (and the real violation it measures) is suppressed
     while the record kept in its place covers almost none of it. (PURE)"""
-    return any(fn["start"] <= line_no < fn["end"] for fn in funcs)
-
-
-def _phantom_has_more_params(funcs, line_no, lines):
-    """True if a control-keyword phantom's own header declares more
-    comma-separated items than the real function record enclosing it -- e.g. a
-    C# `using (a, b, c, d, e)` inside a method whose own signature takes one
-    argument. When true the phantom must be kept despite being a control
-    keyword: collapsing it into the enclosing record would silently drop a
-    parameter_count violation the enclosing record's own header does not
-    carry, the exact under-count this heuristic must never introduce. Assumes
-    an enclosing record exists (only called once one has been confirmed).
-    (PURE)"""
-    enclosing = next(
-        fn for fn in funcs if fn["start"] <= line_no < fn["end"])
-    phantom_params = _count_params(lines[line_no - 1])
+    for fn in funcs:
+        if fn["start"] <= line_no < fn["end"]:
+            return fn
+    return None
+
+
+def _phantom_is_redundant(enclosing, phantom_header, lines):
+    """True when a control-keyword phantom adds no parameter_count reading
+    its enclosing record does not already carry. `enclosing` is the record
+    from _strictly_enclosing_record (None when nothing encloses the
+    phantom, in which case the phantom is the sole measurement of that body
+    and is never redundant). `phantom_header` is the phantom's own raw
+    source line; `lines` is the file's raw source lines, used only to read
+    the enclosing record's header.
+
+    A phantom declaring MORE comma-separated items than the enclosing
+    method -- e.g. a C# `using (a, b, c, d, e)` inside a one-argument
+    method -- is kept, because collapsing it would silently drop a
+    parameter_count violation the enclosing header does not carry: the
+    exact under-count this heuristic must never introduce. (PURE)"""
+    if enclosing is None:
+        return False
+    phantom_params = _count_params(phantom_header)
     enclosing_params = _count_params(lines[enclosing["header_idx"]])
-    return phantom_params > enclosing_params
+    return phantom_params <= enclosing_params
 
 
-def _looks_like_call_or_control(ext, match, line_no, state):
+def _looks_like_call_or_control(ext, match, phantom_is_redundant):
     """True if the C-family signature match is really a control keyword
     (`if (...) {`) rather than a definition, so the caller should not record it
     as a function. `ext` is the file's extension, `match` the _CBRACE_DEF_RE
-    match and `line_no` the match's 1-based line. `state` bundles the two
-    pieces of scan-so-far context the redundancy check below needs together --
-    {"funcs": the records collected so far, "lines": the file's raw source
-    lines} -- kept as one parameter rather than two positional ones.
+    match, and `phantom_is_redundant` the caller's already-resolved answer to
+    "does a real record enclose this phantom and already carry every metric it
+    would measure" (see _strictly_enclosing_record and _phantom_is_redundant).
+    Resolving it once at the call site keeps the enclosure bound written in
+    exactly one place.
 
     A globally reserved word is always rejected. A per-extension word is
-    rejected ONLY when an already-collected record strictly encloses
-    `line_no` (see _strictly_encloses_line) AND the phantom's own header does
-    not declare more parameters than that enclosing record's header (see
-    _phantom_has_more_params) -- i.e. when the real enclosing method was
-    itself extracted and the phantom is redundant on every metric it would
-    have measured. When nothing encloses it the phantom is the sole
+    rejected ONLY when `phantom_is_redundant` -- i.e. when the real enclosing
+    method was itself extracted and the phantom is redundant on every metric
+    it would have measured. When nothing encloses it the phantom is the sole
     measurement of that method body -- measured on a C# method whose brace
     sits on its own line, dropping it takes the file from a reported
     cyclomatic 5 / cognitive 8 to no function measurement at all -- so it is
     deliberately kept. That is an over-count, the one direction this
     heuristic is allowed to move. (PURE)"""
     word = match.group(1)
     if word in _CONTROL_WORDS:
         return True
     if word not in _control_words_for(ext):
         return False
-    funcs = state["funcs"]
-    if not _strictly_encloses_line(funcs, line_no):
-        return False
-    return not _phantom_has_more_params(funcs, line_no, state["lines"])
+    return phantom_is_redundant
 
 
 def _match_brace_end(lines, header_idx):
     """Return the 0-based index of the line holding the closing brace that
     balances the first `{` at/after header_idx, or None. PURE over `lines`."""
@@ -1167,12 +1180,14 @@ def _scan_lines_for(source, scan_lang, lines):
     return scan_lines
 
 
 def _function_metrics(lines, scan_lines, fn, lang):
     """Measured metric values for one extracted function. `lines` is raw source;
-    `scan_lines` is its masked counterpart, read by the two branch scans alone,
-    so span, indentation and length metrics all stay on raw text. (PURE)"""
+    `scan_lines` is its masked counterpart. Span and length metrics stay on raw
+    text, as does `base_indent`; `_cognitive_approx` reads BOTH branch hits and
+    per-line indent off the masked body, which is why _token_mask_spans must
+    preserve each row's whole leading-whitespace run. (PURE)"""
     body_lines = lines[fn["header_idx"]:fn["end"]]
     scan_body = scan_lines[fn["header_idx"]:fn["end"]]
     header_line = lines[fn["header_idx"]]
     base_indent = _py_indent_width(header_line)
     return {
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index 6ef0d14..572bbc3 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -668,10 +668,54 @@ DEEP_PY_METHOD_SPACES = (
 )
 DEEP_PY_METHOD_TABS = "\n".join(
     line.replace("    ", "\t")
     for line in DEEP_PY_METHOD_SPACES.split("\n"))
 
+# A tab-indented body that CONTAINS a triple-quoted string whose CLOSING
+# row carries branch operators, and the byte-identical space-indented
+# body. No existing TestTabIndentedPython fixture holds a string literal,
+# which is why the mask defect below went uncaught; and the operators
+# after the closing quotes are what make it visible in a metric rather
+# than only in the mask's column arithmetic. MEASURED before this fix:
+# the tab form reported cognitive 10 against the space form's 13 -- the
+# python mask overwrote the tab row's leading tabs with the sentinel, so
+# _cognitive_approx read that continuation row at indent 0. After this
+# fix both report 13 and the full metrics dicts are equal.
+STRINGY_PY_SPACES = (
+    "def stringy(a, b, c):\n"
+    "    if a:\n"
+    "        for i in b:\n"
+    "            note = \"\"\"a long\n"
+    "            note\"\"\" if c and b else \"\"\n"
+    "            if c and note:\n"
+    "                return i\n"
+    "    return 0\n"
+)
+STRINGY_PY_TABS = "\n".join(
+    line.replace("    ", "\t") for line in STRINGY_PY_SPACES.split("\n"))
+
+# The DOWN direction, which no other fixture here pins: a class whose
+# `def` header is TAB-indented while its body lines are SPACE-indented.
+# base_indent now expands the header's tab to 4 columns while the body's
+# space widths are unchanged, so the gap between them SHRINKS. MEASURED
+# pre-s3 (26adcad) cognitive 25 / nesting_depth 7; head cognitive
+# 20 / nesting_depth 6. That is a reduction in over-count, not a new
+# under-count -- head cognitive 20 is still above the cognitive
+# threshold of 15, so this shape does NOT change its verdict; it changes
+# its number, and this fixture exists so that direction is never silent.
+MIXED_INDENT_PY = (
+    "class C:\n"
+    "\tdef mixed(self, a, b, c):\n"
+    "        if a:\n"
+    "            for i in b:\n"
+    "                if c:\n"
+    "                    while a:\n"
+    "                        if b and c:\n"
+    "                            return i\n"
+    "        return 0\n"
+)
+
 
 class TestTabIndentedPython(unittest.TestCase):
     """The indent model must read a tab as one nesting step. Before this
     fix _nesting_depth_python and the python arm of _cognitive_approx
     stripped only spaces, so a tab-indented file collapsed to depth 0 and
@@ -714,10 +758,43 @@ class TestTabIndentedPython(unittest.TestCase):
         self.assertEqual(qg._py_indent_width("        if a:"), 8)
         self.assertEqual(qg._py_indent_width("\t    if a:"), 8)
         self.assertEqual(qg._py_indent_width("if a:"), 0)
         self.assertEqual(qg._py_indent_width(""), 0)
 
+    def test_a_tab_indented_string_literal_keeps_its_indent_through_the_mask(
+            self):
+        # F1: _token_mask_spans started each continuation row's sentinel fill
+        # at lstrip(" "), which is 0 on a tab-indented row, so the fill erased
+        # the leading TABS that _py_indent_width now reads. MEASURED before
+        # the fix: cognitive 10 for the tab body against 13 for the identical
+        # space body -- an under-count, the one direction this heuristic is
+        # never allowed to move.
+        self.assertEqual(
+            self.metrics(STRINGY_PY_TABS),
+            self.metrics(STRINGY_PY_SPACES))
+
+    def test_the_mask_leaves_a_tab_continuation_rows_indent_alone(self):
+        # The mechanism behind the test above, pinned directly: every masked
+        # row must report the same _py_indent_width as its raw counterpart.
+        # MEASURED before the fix: row index 4 read 12 raw and 0 masked.
+        masked = qg._mask_python_literals(STRINGY_PY_TABS)
+        self.assertIsNotNone(masked)
+        for raw, got in zip(STRINGY_PY_TABS.split("\n"), masked.split("\n")):
+            self.assertEqual(
+                qg._py_indent_width(got), qg._py_indent_width(raw))
+
+    def test_a_mixed_indent_method_pins_the_downward_direction(self):
+        # F3: the CHANGELOG documents that this change can move results DOWN
+        # and nothing pinned it. Tab-indented `def` header, space-indented
+        # body: MEASURED pre-s3 (26adcad) cognitive 25 / nesting_depth
+        # 7, head cognitive 20 / nesting_depth 6. Both head values
+        # are pinned exactly so a future indent change cannot move this shape
+        # again without a test saying so.
+        got = self.metrics(MIXED_INDENT_PY)
+        self.assertEqual(got["cognitive_complexity"], 20)
+        self.assertEqual(got["nesting_depth"], 6)
+
 
 class TestCrapScore(unittest.TestCase):
     def test_full_coverage_equals_complexity(self):
         # CRAP with 100% coverage collapses to the complexity itself
         self.assertAlmostEqual(qg.crap_score(10, 1.0), 10)
@@ -1222,10 +1299,48 @@ class TestAnalyzeBuiltinPython(unittest.TestCase):
         findings, cls = qg.analyze_builtin("data.txt", "whatever\n", [(1, 1)])
         self.assertEqual(findings, [])
         self.assertIsNone(cls)
 
 
+# A two-record list where the OUTER record is listed first, exactly as
+# _extract_functions_cbrace appends them (headers in source order). F4:
+# the bound `fn['start'] <= line_no < fn['end']` used to be written twice
+# -- once as a predicate and once re-derived inside a bare next() -- so a
+# drift between them would raise StopIteration inside analyze_builtin,
+# which has no try/except around it in measure()'s file loop and would
+# abort the gate for EVERY file rather than one. MEASURED: behaviour is
+# unchanged; next() selected the OUTERMOST enclosing record and so does
+# the helper. The 1-based-inclusive boundary cases live with
+# TestExtensionScopedControlWords, which owns them already.
+ENCLOSING_FUNCS = [
+    {"name": "outer", "start": 1, "end": 20, "header_idx": 0},
+    {"name": "inner", "start": 5, "end": 12, "header_idx": 4},
+]
+
+
+class TestEnclosingRecord(unittest.TestCase):
+    def test_it_selects_the_outermost_enclosing_record(self):
+        got = qg._strictly_enclosing_record(ENCLOSING_FUNCS, 7)
+        self.assertEqual(got["name"], "outer")
+
+    def test_a_phantom_with_more_params_is_not_redundant(self):
+        lines = ["void outer(int a) {"] + [""] * 19
+        self.assertFalse(
+            qg._phantom_is_redundant(
+                ENCLOSING_FUNCS[0], "using (a, b, c, d, e) {", lines))
+
+    def test_a_phantom_with_no_more_params_is_redundant(self):
+        lines = ["void outer(int a, int b) {"] + [""] * 19
+        self.assertTrue(
+            qg._phantom_is_redundant(
+                ENCLOSING_FUNCS[0], "using (x) {", lines))
+
+    def test_no_enclosing_record_means_not_redundant(self):
+        self.assertFalse(
+            qg._phantom_is_redundant(None, "using (x) {", []))
+
+
 class TestAnalyzeBuiltinCbrace(unittest.TestCase):
     SOURCE = (
         "function outer(a, b) {\n"
         "    if (a) {\n"
         "        return b && a || c;\n"
@@ -2094,11 +2209,11 @@ CS_MULTI_DECL_USING_SOURCE = (
     "}\n"
 )
 
 # r1-F1 follow-up (s2): the same shape with the DOMINANCE reversed. The
 # `using` header declares 5 comma items, the enclosing Go declares 6, so
-# _phantom_has_more_params does NOT keep the phantom and it is dropped.
+# _phantom_is_redundant DOES report the phantom redundant, so it is dropped.
 # Measured: {'Go': 6} for a full [(1, 400)] range and for a narrow
 # [(4, 6)] range covering only the using block -- the dropped count is
 # never the file's highest, and the enclosing record is always emitted
 # alongside because its span strictly contains the phantom's.
 CS_DOMINATED_USING_SOURCE = (
@@ -2193,17 +2308,19 @@ class TestExtensionScopedControlWords(unittest.TestCase):
         # equals the phantom's header line does not strictly enclose it. That
         # equality is exactly what a stray brace-in-a-literal on the header
         # line produces (see test_a_literal_brace_on_the_header_line_...
         # below), so treating it as enclosure silently drops a real
         # violation.
+        # r1-F4: the helper now returns the enclosing record or None; the
+        # bound is unchanged.
         funcs = [{"name": "Import", "start": 3, "end": 11, "header_idx": 2}]
-        self.assertFalse(qg._strictly_encloses_line(funcs, 2))
-        self.assertTrue(qg._strictly_encloses_line(funcs, 3))
-        self.assertTrue(qg._strictly_encloses_line(funcs, 10))
-        self.assertFalse(qg._strictly_encloses_line(funcs, 11))
-        self.assertFalse(qg._strictly_encloses_line(funcs, 12))
-        self.assertFalse(qg._strictly_encloses_line([], 3))
+        self.assertIsNone(qg._strictly_enclosing_record(funcs, 2))
+        self.assertIsNotNone(qg._strictly_enclosing_record(funcs, 3))
+        self.assertIsNotNone(qg._strictly_enclosing_record(funcs, 10))
+        self.assertIsNone(qg._strictly_enclosing_record(funcs, 11))
+        self.assertIsNone(qg._strictly_enclosing_record(funcs, 12))
+        self.assertIsNone(qg._strictly_enclosing_record([], 3))
 
     def test_the_reserved_words_are_scoped_to_their_own_extensions(self):
         self.assertEqual(
             qg._control_words_for(".cs"),
             frozenset({"foreach", "using", "lock", "fixed"}))
@@ -2313,11 +2430,11 @@ class TestExtensionScopedControlWords(unittest.TestCase):
         # raw text and the char literal '}' inside `raw.Split('}')` balances
         # Import's own scan to depth 0 exactly on the foreach header line,
         # i.e. Import's measured end EQUALS foreach's header line_no. Under
         # the old inclusive `_encloses_line` that equality counted as
         # enclosure and foreach vanished entirely (measured: only "Import"
-        # remained). Under the new strict `_strictly_encloses_line` equality
+        # remained). Under the new strict `_strictly_enclosing_record` equality
         # no longer enclose, so foreach is retained.
         funcs = qg._extract_functions_cbrace(
             CS_LITERAL_BRACE_HEADER_SOURCE.splitlines(), ".cs")
         names = [fn["name"] for fn in funcs]
         self.assertIn("foreach", names)
