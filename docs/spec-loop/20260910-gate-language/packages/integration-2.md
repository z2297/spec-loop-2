# Review package: fa01826d50b011e0666b2d5ce36ea5dc1a684837..HEAD  (context: -U5)

## Commits
2c22dd3 Merge spec-loop remediation slice r1: preserve tab indentation through the literal mask, and resolve the enclosure bound once
7aba97e refactor(gate): resolve the phantom enclosure bound once and drop the state bag
75aa33b test(gate): pin the downward direction of the tab indent model
9e20e1c fix(gate): preserve tab indentation through the python literal mask
892a2aa Merge spec-loop slice s3: expand tabs in the python nesting and cognitive indent model
a580350 docs(changelog): make the s3 direction claim bidirectional in the bolded sentence
6d9a213 fix(changelog): correct s3's one-directional nesting-depth claim
fb7a3f1 test(quality-gate): pin tab-indented method header base_indent site
24f9529 docs(changelog): fix a dangling residual reference in the s1 entry Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
aa28c6a fix(quality-gate): expand tabs in the python nesting and cognitive indent model
26adcad Merge spec-loop slice s2: count C# foreach as a branch, and correct s1's overstated suppression guarantee
5ba3c6b fix(quality-gate): reformat dict comprehension to clear nesting_depth threshold
e933d5e docs(gate): correct the phantom-suppression safety claim and name its parameter_count residual
acf8dcf feat(gate): count C# foreach as a cyclomatic branch
b574405 Merge spec-loop slice s1: language-scoped control-keyword guard with coverage-conditional suppression, and a record for every unmeasured changed file
c52d9f2 fix(gate): strict enclosure and param-aware suppression close two under-count paths; skip reasons and measure() refactored
2f2b7c7 fix(gate): record every unmeasured changed file, not just unsupported extensions
29aa74b fix(gate): scope the C-family control-keyword guard by extension, suppressing only enclosed phantoms

## Files changed
 CHANGELOG.md                                   | 161 ++++++
 plugins/spec-loop/scripts/quality_gate.py      | 390 +++++++++++---
 plugins/spec-loop/scripts/test_quality_gate.py | 678 ++++++++++++++++++++++++-
 3 files changed, 1147 insertions(+), 82 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
9,
169
]
],
"plugins/spec-loop/scripts/quality_gate.py": [
[
136,
143
],
[
587,
595
],
[
601,
601
],
[
903,
915
],
[
942,
963
],
[
967,
969
],
[
971,
972
],
[
975,
975
],
[
978,
981
],
[
985,
991
],
[
994,
1027
],
[
1030,
1051
],
[
1053,
1075
],
[
1102,
1102
],
[
1134,
1134
],
[
1154,
1157
],
[
1160,
1160
],
[
1185,
1188
],
[
1192,
1192
],
[
1220,
1221
],
[
1366,
1492
],
[
1498,
1503
],
[
1512,
1512
],
[
1514,
1515
],
[
1518,
1518
],
[
1525,
1526
],
[
1530,
1536
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
636,
796
],
[
1304,
1341
],
[
2152,
2608
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index ff64bc6..5735c74 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -4,10 +4,171 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
+### Fixed
+- **A tab-indented python file was measured as if it had no nesting at all, and now
+  measures the same as the identical space-indented file.** Parity now survives the
+  literal mask too: the python mask's own continuation-row fill started at `lstrip(" ")` and
+  overwrote a tab-indented row's leading tabs, so a tab body holding a multi-line string
+  whose closing row carries branch operators measured cognitive 10 against the space body's
+  13 -- an under-count, now fixed in `_token_mask_spans` and pinned by
+  `TestTabIndentedPython`. `_nesting_depth_python` and the
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
+  specifically. **This changes existing `.py` results in both directions, most often
+  upward**: a tab-indented python function that passes the gate today can fail after this
+  change. That is the safe direction under the never-under-count rule and is the intended
+  effect, but it is an observable behaviour change, not merely internal. It also moves
+  results DOWN where a tab-indented `def` header is combined with space-indented body lines:
+  `_function_metrics`'s `base_indent` now expands the header's tab while the body lines'
+  indent (already space-only) is unchanged, so the gap between them can shrink (measured on
+  one such method: nesting_depth 10 -> 9, cognitive 21 -> 18), retiring an existing violation
+  on that mixed-indent shape — the new values are closer to truth in both directions, a
+  reduction in over-count rather than a new under-count.
+  Known, documented residuals: `_extract_functions_python` still measures indent with a bare
+  `lstrip()` and is deliberately left alone — it compares a header against its own body with
+  one consistent measure, so it already spans a tab-indented file correctly, and expanding
+  there was measured to SHRINK a mixed tab-and-space function's span (a four-line method
+  dropping to one), which would be a new under-count. The 4-column tab step is HARDCODED,
+  deliberately: the indent step stays at 4 and is not parameterised, since no 2-space
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
+- **The quality gate's C-family control-keyword guard is now scoped to the language that
+  reserves the word, and suppresses a phantom record only when the real enclosing method was
+  itself measured.** `plugins/spec-loop/scripts/quality_gate.py` keys the new
+  `_CONTROL_WORDS_BY_EXT` map by file extension — `foreach`/`using`/`lock`/`fixed` for `.cs`,
+  `synchronized` for `.java` — while the nine words in `_CONTROL_WORDS` stay global; the
+  extension is threaded from `analyze_builtin` through `_extract_functions_for` and
+  `_extract_functions_cbrace` into `_looks_like_call_or_control`, whose unused `line`
+  parameter it replaces and whose docstring no longer claims a function-call detection the
+  body never implemented. Suppression is conditional on coverage by design: the new PURE
+  `_encloses_line` helper drops a `foreach` record only when an already-extracted function's
+  1-based inclusive span contains it. **The retained phantom is DELIBERATE, not a residual
+  defect** — on a C# method whose opening brace sits on its own line, `_CBRACE_DEF_RE` never
+  sees the method, so the `foreach` record is the only measurement of that body (measured:
+  cyclomatic 5, cognitive 8); suppressing it unconditionally would take the file to
+  `class_lines` alone and turn a real reading into a silent pass. An over-count is the one
+  direction this heuristic is permitted to move. That safety argument is PER-METRIC, not
+  blanket: an enclosed phantom's cyclomatic, cognitive, method_lines and nesting_depth are
+  all dominated by the enclosing record whose body contains it, but its `parameter_count` is
+  read from its own header and is NOT — see the `_phantom_is_redundant` entry below.
+  Known, documented residuals: a pure-Allman C# file (every brace on its own line, the
+  Visual Studio default) still extracts nothing at all, because `_CBRACE_DEF_RE` requires
+  the `{` on the signature line — deferred to its own run. (A related residual — `foreach`
+  absent from `_BRANCH_WORDS` — is fixed below in this same Unreleased section.)
+- **A changed file the quality gate could not measure can no longer vanish from the report.**
+  `measure()` in `plugins/spec-loop/scripts/quality_gate.py` ended its skip chain in
+  `elif _lang_for(path) is None`, so a file with a supported extension that yielded zero
+  callables produced neither a function measurement nor a `skipped` entry — measured on a
+  pure-Allman `.cs` file and a `def`-less `.py` file, `skipped` named neither. The chain now
+  ends in an unconditional `else` carrying the new PURE `_skip_reason(path)`, which keeps the
+  existing `"unsupported file type for analysis"` text and adds `"no callable found by the
+  builtin heuristic"` for the supported case, so the two are distinguishable in the report.
+  `plugins/spec-loop/scripts/test_quality_gate.py` gains `TestMeasureSkipRecord`, the suite's
+  first `qg.measure()`-level test. Known, documented residuals: a `skipped` entry still feeds
+  no threshold and no exit code, and `summary.vacuous` is still read by nothing in the
+  per-slice pipeline — only `references/phase-5-integration.md:14` tells any reader to check
+  it. Both are deferred, not fixed here.
+- **The control-keyword suppression could itself under-count, on two separate paths, and both
+  are closed.** `plugins/spec-loop/scripts/quality_gate.py`'s `_encloses_line` (now
+  `_strictly_enclosing_record`) tested only `fn["start"] <= line_no <= fn["end"]`; because `.cs`
+  and `.java` are excluded from `_JS_MASK_EXTS`, `_match_brace_end` counts a `}` inside a
+  string or char literal on the enclosing method's own header line — e.g.
+  `raw.Split('}')` — as a real close, ending the enclosing record's span exactly AT the
+  phantom's header line. That equality used to count as enclosure, suppressing the phantom
+  even though the enclosing record measures almost none of its body; the bound is now
+  exclusive (`line_no < fn["end"]`), and `TestExtensionScopedControlWords` gains
+  `test_a_literal_brace_on_the_control_header_line_keeps_its_phantom` pinning the retained
+  `foreach` record. Separately, suppression assumed an enclosed phantom's own metrics were
+  always dominated by the enclosing record, which is false for `parameter_count`: a C#
+  `using (a, b, c, d, e)` can declare more comma-separated items than the enclosing method's
+  own signature. The new PURE `_phantom_is_redundant` compares the phantom's own header
+  against the enclosing record's header, and the guard keeps the phantom whenever its own
+  count is higher;
+  `test_an_enclosed_multi_declaration_using_keeps_its_own_finding` pins a 5-parameter `using`
+  surviving inside a 1-parameter `Import` method (5 > `DEFAULT_THRESHOLDS["parameter_count"]`
+  == 4). Both are the same failure family the run's NEVER-UNDER-COUNT constraint names.
+  Known, documented residuals: the parameter_count guarantee is an ARGUMENT the code does
+  not assert. `_phantom_is_redundant` reports a phantom redundant when its own count is less
+  than or equal to the enclosing header's, and only a redundant phantom is dropped; a phantom
+  whose count is strictly higher is kept. That is safe only
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
+- **A skip record could itself misreport why a file went unmeasured.** `measure()`'s new
+  unconditional `else` arm (see above) reached `_skip_reason(path)` whenever a file yielded
+  zero IN-RANGE findings — which also fires for an import-only edit, a docstring tweak, or any
+  changed hunk that simply falls outside every callable in an otherwise fully-measurable file.
+  Such a file got the same `"no callable found by the builtin heuristic"` text as a file with
+  no callables at all, a false claim on the common path. `_skip_reason` now takes the file's
+  `source` too and calls the new PURE `_has_any_callable` (a changed-range-free extraction) to
+  tell the two apart, returning `"no changed callable found by the builtin heuristic"` when
+  callables exist outside the diff. `measure()` is also refactored into `_read_changed_source`,
+  `_backend_records_for`, `_measurements_for_file`, `_heuristic_measurement`,
+  `_class_measurement`, `_python_only`, `_detect_backend_records` and `_used_backend_names`,
+  which brings its own cyclomatic/cognitive/method_lines/nesting_depth back under threshold
+  (measured before: 14/36/66/5 against 10/15/50/3; after: 5/11/40/3) without changing its
+  return contract; `_extract_functions_cbrace` is similarly split out into `_cbrace_name_at`,
+  bringing its nesting_depth from 5 to 3. `TestMeasureSkipRecord` gains
+  `test_an_import_only_edit_does_not_falsely_claim_no_callable_exists`. Known, documented
+  residuals: `_extract_functions_python`, `_match_brace_end` and `_match_changed` carry
+  pre-existing cognitive_complexity/nesting_depth violations this slice did not introduce and
+  does not fix here, and `class_lines` on both `quality_gate.py` and `test_quality_gate.py`
+  remains accepted debt per standing ruling.
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
index a60f537..2edc89e 100644
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
@@ -575,21 +582,25 @@ def _mask_line_range(row, start_col, end_col):
 
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
@@ -887,10 +898,23 @@ def _branch_count(text):
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
@@ -913,45 +937,144 @@ def _extract_functions_python(lines):
         funcs.append({"name": m.group(1), "start": i + 1, "end": last_body + 1,
                       "header_idx": i})
     return funcs
 
 
-def _extract_functions_cbrace(lines):
+def _cbrace_name_at(lines, ext, funcs, i):
+    """The function name detected at 0-based line `i` (else None), tried as a
+    brace signature first and an arrow form second. `funcs` is the record list
+    collected so far; this is where the control-keyword guard's enclosure
+    question is resolved, by _strictly_enclosing_record then
+    _phantom_is_redundant, so the guard itself takes a plain boolean.
+    Extracted out of _extract_functions_cbrace purely to keep that loop's own
+    nesting shallow; carries no state across calls. (PURE)"""
+    line = lines[i]
+    m = _CBRACE_DEF_RE.search(line)
+    if m:
+        enclosing = _strictly_enclosing_record(funcs, i + 1)
+        redundant = _phantom_is_redundant(enclosing, line, lines)
+        if not _looks_like_call_or_control(ext, m, redundant):
+            return m.group(1)
+    am = _CBRACE_ARROW_RE.search(line)
+    if am:
+        return am.group(1)
+    return None
+
+
+def _extract_functions_cbrace(lines, ext=""):
     """Split brace-language source into functions by matching the brace that
     opens each detected signature. Returns [{name, start, end, header_idx}] with
     1-based inclusive spans. Best-effort: a signature whose opening brace can't
-    be balanced is skipped."""
+    be balanced is skipped. `ext` is the file's extension, used only to scope
+    the per-language reserved words in _looks_like_call_or_control; it defaults
+    to "" so a caller with no path gets the global words alone."""
     funcs = []
-    text_by_line = lines
-    for i, line in enumerate(lines):
-        name = None
-        m = _CBRACE_DEF_RE.search(line)
-        if m and not _looks_like_call_or_control(line, m):
-            name = m.group(1)
-        else:
-            am = _CBRACE_ARROW_RE.search(line)
-            if am:
-                name = am.group(1)
+    for i in range(len(lines)):
+        name = _cbrace_name_at(lines, ext, funcs, i)
         if not name:
             continue
-        end = _match_brace_end(text_by_line, i)
+        end = _match_brace_end(lines, i)
         if end is None:
             continue
-        funcs.append({"name": name, "start": i + 1, "end": end + 1,
-                      "header_idx": i})
+        funcs.append({
+            "name": name, "start": i + 1, "end": end + 1,
+            "header_idx": i,
+        })
     return funcs
 
 
+# The 9 words below are reserved in EVERY brace language this analyzer reads,
+# so they stay global. `foreach`/`using`/`lock`/`fixed` (C#) and
+# `synchronized` (Java) are reserved only in their own language -- a .js class
+# may legitimately define a method named `lock`, and measured on a fixture
+# with methods named lock/fixed/using, adding those words globally drops all
+# three real functions from the report. They are therefore keyed by EXTENSION,
+# not by the "cbrace" family, which .ts and .cs share.
 _CONTROL_WORDS = {"if", "for", "while", "switch", "catch", "else", "do",
                   "return", "case"}
+_CONTROL_WORDS_BY_EXT = {
+    ".cs": frozenset({"foreach", "using", "lock", "fixed"}),
+    ".java": frozenset({"synchronized"}),
+}
+
+
+def _control_words_for(ext):
+    """The extra reserved words for one file extension (a frozenset, possibly
+    empty). `ext` is a leading-dot extension; None, "" and any unknown
+    extension yield the empty set. (PURE)"""
+    return _CONTROL_WORDS_BY_EXT.get((ext or "").lower(), frozenset())
+
+
+def _strictly_enclosing_record(funcs, line_no):
+    """The already-collected function record that STRICTLY contains
+    `line_no`, or None. `funcs` is a list of
+    {name, start, end, header_idx} records whose start/end are 1-BASED
+    INCLUSIVE; `line_no` is 1-based. Records arrive in header order, so the
+    first match is the OUTERMOST enclosing one -- the selection the bare
+    next() this helper replaces already made, preserved deliberately:
+    whichever record encloses the phantom is always emitted alongside it.
+
+    The upper bound is exclusive on purpose: a record's span can only reach
+    exactly the phantom's header line when a non-JS-masked brace language
+    (.cs/.java are excluded from _JS_MASK_EXTS) counts a `}` inside a string
+    or char literal ON that header line and balances the enclosing scan to
+    depth 0 there. In that case the enclosing record does not actually
+    dominate the phantom's body, so equality must not count as enclosure --
+    otherwise the phantom (and the real violation it measures) is suppressed
+    while the record kept in its place covers almost none of it. (PURE)"""
+    for fn in funcs:
+        if fn["start"] <= line_no < fn["end"]:
+            return fn
+    return None
 
 
-def _looks_like_call_or_control(line, match):
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
+    enclosing_params = _count_params(lines[enclosing["header_idx"]])
+    return phantom_params <= enclosing_params
+
+
+def _looks_like_call_or_control(ext, match, phantom_is_redundant):
     """True if the C-family signature match is really a control keyword
-    (`if (...) {`) or a function CALL, not a definition. Cheap guard to cut the
-    most common false positives in the heuristic path."""
-    return match.group(1) in _CONTROL_WORDS
+    (`if (...) {`) rather than a definition, so the caller should not record it
+    as a function. `ext` is the file's extension, `match` the _CBRACE_DEF_RE
+    match, and `phantom_is_redundant` the caller's already-resolved answer to
+    "does a real record enclose this phantom and already carry every metric it
+    would measure" (see _strictly_enclosing_record and _phantom_is_redundant).
+    Resolving it once at the call site keeps the enclosure bound written in
+    exactly one place.
+
+    A globally reserved word is always rejected. A per-extension word is
+    rejected ONLY when `phantom_is_redundant` -- i.e. when the real enclosing
+    method was itself extracted and the phantom is redundant on every metric
+    it would have measured. When nothing encloses it the phantom is the sole
+    measurement of that method body -- measured on a C# method whose brace
+    sits on its own line, dropping it takes the file from a reported
+    cyclomatic 5 / cognitive 8 to no function measurement at all -- so it is
+    deliberately kept. That is an over-count, the one direction this
+    heuristic is allowed to move. (PURE)"""
+    word = match.group(1)
+    if word in _CONTROL_WORDS:
+        return True
+    if word not in _control_words_for(ext):
+        return False
+    return phantom_is_redundant
 
 
 def _match_brace_end(lines, header_idx):
     """Return the 0-based index of the line holding the closing brace that
     balances the first `{` at/after header_idx, or None. PURE over `lines`."""
@@ -974,11 +1097,11 @@ def _nesting_depth_python(body_lines, base_indent):
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
 
 
@@ -1006,11 +1129,11 @@ def _cognitive_approx(body_text_or_lines, lang, base_indent):
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
@@ -1026,15 +1149,17 @@ def _cognitive_approx(body_text_or_lines, lang, base_indent):
 
 def _nonblank(lines):
     return sum(1 for line in lines if line.strip())
 
 
-def _extract_functions_for(lines, lang):
-    """The extracted callables of one file, by language family. (PURE)"""
+def _extract_functions_for(lines, lang, ext=""):
+    """The extracted callables of one file, by language family. `ext` scopes
+    the brace extractor's per-language reserved words; the python branch
+    ignores it. (PURE)"""
     if lang == "python":
         return _extract_functions_python(lines)
-    return _extract_functions_cbrace(lines)
+    return _extract_functions_cbrace(lines, ext)
 
 
 def _nesting_depth_for(body_lines, lang, base_indent):
     """Nesting depth of one RAW function body, by language family. Always
     measured on raw text: the mask is for branch scanning only. (PURE)"""
@@ -1055,16 +1180,18 @@ def _scan_lines_for(source, scan_lang, lines):
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
-    base_indent = len(header_line) - len(header_line.lstrip(" "))
+    base_indent = _py_indent_width(header_line)
     return {
         "cyclomatic_complexity": _branch_count("\n".join(scan_body)),
         "method_lines": _nonblank(body_lines),
         "parameter_count": _count_params(header_line),
         "cognitive_complexity": _cognitive_approx(
@@ -1088,11 +1215,12 @@ def analyze_builtin(path, source, changed_ranges):
     lang = _lang_for(path)
     if lang is None:
         return [], None
     lines = source.splitlines()
     scan_lines = _scan_lines_for(source, _scan_lang_for(path), lines)
-    funcs = _extract_functions_for(lines, lang)
+    funcs = _extract_functions_for(
+        lines, lang, os.path.splitext(path)[1].lower())
 
     findings = []
     for fn in funcs:
         if not _intersects_changed(fn["start"], fn["end"], changed_ranges):
             continue
@@ -1233,81 +1361,181 @@ def _match_changed(records, changed_ranges):
     return [r for r in records
             if _intersects_changed(r["line_start"], r["line_end"],
                                     changed_ranges)]
 
 
+def _has_any_callable(path, source):
+    """True if the builtin extractor finds at least one callable anywhere in
+    `path`'s full source, ignoring changed ranges entirely. Used only to tell
+    apart, for the skip reason, a file whose callables all sit outside the
+    diff from a file the extractor cannot see any callable in at all. (PURE)"""
+    lang = _lang_for(path)
+    if lang is None:
+        return False
+    lines = source.splitlines()
+    return bool(_extract_functions_for(
+        lines, lang, os.path.splitext(path)[1].lower()))
+
+
+def _skip_reason(path, source):
+    """Why one changed file produced no function measurement. Three cases:
+    unsupported extension (_lang_for(path) is None); a supported file whose
+    callables exist somewhere but none intersect the changed ranges (its
+    diff touched only imports, constants, a docstring, etc.); and a supported
+    file the extractor could not see any callable in at all.
+
+    The second case used to be misreported as the third: `measure()` reached
+    this helper whenever a file yielded zero IN-RANGE findings, with no way to
+    tell "no callables at all" apart from "callables exist, just not in the
+    diff" -- so an import-only edit to a file full of real functions falsely
+    claimed the builtin heuristic found no callable in it. `source` lets this
+    helper re-run the (changed-range-free) extraction to distinguish the two.
+    (PURE)"""
+    if _lang_for(path) is None:
+        return "unsupported file type for analysis"
+    if _has_any_callable(path, source):
+        return "no changed callable found by the builtin heuristic"
+    return "no callable found by the builtin heuristic"
+
+
+def _read_changed_source(path, repo_dir):
+    """The text of one changed file, or None if it cannot be read (missing,
+    a directory, undecodable in a way `errors="replace"` doesn't paper over,
+    permissions, ...). Isolated so measure()'s own loop stays a single
+    if/continue rather than a try/except."""
+    full_path = os.path.join(repo_dir, path)
+    try:
+        with open(full_path, encoding="utf-8", errors="replace") as fh:
+            return fh.read()
+    except (OSError, IsADirectoryError):
+        return None
+
+
+def _backend_records_for(path, changed_ranges, lizard_by_file, radon_by_file):
+    """The in-range backend records for one changed file (lizard preferred,
+    radon as fallback), plus its forward-slash-normalised path. Looks up both
+    the normalised and raw spellings since a backend may report either."""
+    norm = path.replace("\\", "/")
+    recs = _match_changed(
+        lizard_by_file.get(norm, []) or lizard_by_file.get(path, []),
+        changed_ranges)
+    if not recs:
+        recs = _match_changed(
+            radon_by_file.get(norm, []) or radon_by_file.get(path, []),
+            changed_ranges)
+    return recs, norm
+
+
+def _heuristic_measurement(path, hf):
+    """One heuristic-only function measurement record for the report, built
+    from a single analyze_builtin() finding `hf`. (PURE)"""
+    return {
+        "file": path, "function": hf["function"],
+        "metrics": hf["metrics"], "source": "builtin-heuristic",
+    }
+
+
+def _class_measurement(path, heur_class):
+    """The class_lines measurement record for `path`, or None if
+    analyze_builtin found no class_finding for it. (PURE)"""
+    if heur_class is None:
+        return None
+    return {
+        "file": path, "class_lines": heur_class["class_lines"],
+        "source": "builtin-heuristic",
+    }
+
+
+def _measurements_for_file(
+        path, source, changed_ranges, lizard_by_file, radon_by_file):
+    """Function measurements, the class measurement (or None) and the skip
+    reason (or None) for one already-read changed file. Exactly one of "some
+    func_measurements" or "a skip reason" holds; never both, never neither."""
+    heur_funcs, heur_class = analyze_builtin(path, source, changed_ranges)
+    backend_recs, norm = _backend_records_for(
+        path, changed_ranges, lizard_by_file, radon_by_file)
+
+    if backend_recs:
+        funcs = _merge_backend_and_heuristic(backend_recs, heur_funcs, norm)
+        skip = None
+    elif heur_funcs:
+        funcs = [_heuristic_measurement(path, hf) for hf in heur_funcs]
+        skip = None
+    else:
+        funcs = []
+        skip = _skip_reason(path, source)
+
+    return funcs, _class_measurement(path, heur_class), skip
+
+
+def _python_only(files):
+    """The .py-suffixed subset of `files`, order preserved. (PURE)"""
+    return [f for f in files if f.endswith(".py")]
+
+
+def _detect_backend_records(files, py_files, repo_dir, backends):
+    """Run the configured backends over the changed files, honouring the
+    historical preference order: lizard first when enabled, radon only as a
+    fallback when lizard produced nothing. Returns (lizard_recs, radon_recs),
+    either possibly empty."""
+    lizard_recs = run_lizard(files, repo_dir) if "lizard" in backends else []
+    radon_wanted = "radon" in backends and not lizard_recs
+    radon_recs = run_radon(py_files, repo_dir) if radon_wanted else []
+    return lizard_recs, radon_recs
+
+
+def _used_backend_names(lizard_recs, radon_recs):
+    """Which backend(s) actually produced records, in preference order.
+    (PURE)"""
+    by_name = (("lizard", lizard_recs), ("radon", radon_recs))
+    return [name for name, recs in by_name if recs]
+
+
 def measure(changed, repo_dir, backends):
     """Measure every changed file, preferring detected backends and falling back
     to the builtin heuristic per file. Returns (function_measurements,
     class_measurements, skipped, used_backends) where each function measurement
     is {file, function, metrics: {...}, source} and skipped is a list of
-    {"metric"|"file", "reason"} entries.
+    {"metric"|"file", "reason"} entries. EVERY changed file that yields no
+    function measurement gets a `skipped` entry -- an unreadable file, an
+    unsupported extension, a supported file whose callables all sit outside
+    the diff, or a supported file the heuristic could not see any callable in
+    at all (see _skip_reason) -- so a file can never leave the report with an
+    incorrect or silently missing explanation.
 
     A backend supplies cyclomatic_complexity / method_lines / parameter_count
     (lizard) or cyclomatic_complexity only (radon); every remaining metric for
     that function -- always cognitive_complexity, plus nesting_depth and any
     metric the backend omitted -- is filled from the builtin heuristic and
     tagged accordingly, so no metric is silently dropped and cognitive is never
     attributed to a tool."""
     files = sorted(changed)
-    py_files = [f for f in files if f.endswith(".py")]
+    py_files = _python_only(files)
 
-    lizard_recs = run_lizard(files, repo_dir) if "lizard" in backends else []
-    radon_recs = (run_radon(py_files, repo_dir)
-                  if "radon" in backends and not lizard_recs else [])
+    lizard_recs, radon_recs = _detect_backend_records(
+        files, py_files, repo_dir, backends)
     lizard_by_file = _backend_records_by_file(lizard_recs)
     radon_by_file = _backend_records_by_file(radon_recs)
-
-    used_backends = []
-    if lizard_recs:
-        used_backends.append("lizard")
-    if radon_recs:
-        used_backends.append("radon")
+    used_backends = _used_backend_names(lizard_recs, radon_recs)
 
     func_measurements = []
     class_measurements = []
     skipped = []
 
     for path in files:
-        try:
-            with open(os.path.join(repo_dir, path), encoding="utf-8",
-                      errors="replace") as fh:
-                source = fh.read()
-        except (OSError, IsADirectoryError):
+        source = _read_changed_source(path, repo_dir)
+        if source is None:
             skipped.append({"file": path, "reason": "file not readable"})
             continue
 
-        heur_funcs, heur_class = analyze_builtin(path, source, changed[path])
-        heur_by_name = {(f["function"], f["line_start"]): f for f in heur_funcs}
-
-        norm = path.replace("\\", "/")
-        backend_recs = _match_changed(
-            lizard_by_file.get(norm, []) or lizard_by_file.get(path, []),
-            changed[path])
-        if not backend_recs:
-            backend_recs = _match_changed(
-                radon_by_file.get(norm, []) or radon_by_file.get(path, []),
-                changed[path])
-
-        if backend_recs:
-            func_measurements.extend(
-                _merge_backend_and_heuristic(backend_recs, heur_funcs, norm))
-        elif heur_funcs:
-            for hf in heur_funcs:
-                func_measurements.append({
-                    "file": path, "function": hf["function"],
-                    "metrics": hf["metrics"], "source": "builtin-heuristic",
-                })
-        elif _lang_for(path) is None:
-            skipped.append({"file": path,
-                            "reason": "unsupported file type for analysis"})
-
-        if heur_class is not None:
-            class_measurements.append({
-                "file": path, "class_lines": heur_class["class_lines"],
-                "source": "builtin-heuristic",
-            })
+        funcs, class_measurement, skip = _measurements_for_file(
+            path, source, changed[path], lizard_by_file, radon_by_file)
+        func_measurements.extend(funcs)
+        if class_measurement is not None:
+            class_measurements.append(class_measurement)
+        if skip is not None:
+            skipped.append({"file": path, "reason": skip})
 
     return func_measurements, class_measurements, skipped, used_backends
 
 
 def _nearest_heuristic(heur_funcs, name, line_start):
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index 1b72581..572bbc3 100644
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
@@ -611,10 +631,171 @@ class TestNesting(unittest.TestCase):
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
+
 class TestCrapScore(unittest.TestCase):
     def test_full_coverage_equals_complexity(self):
         # CRAP with 100% coverage collapses to the complexity itself
         self.assertAlmostEqual(qg.crap_score(10, 1.0), 10)
 
@@ -1118,10 +1299,48 @@ class TestAnalyzeBuiltinPython(unittest.TestCase):
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
@@ -1928,7 +2147,464 @@ class TestDifferentialAgainstRawScan(unittest.TestCase):
             if brace and got["metrics"] != was["metrics"]:
                 moved.append(where)
         self.assertGreater(len(moved), 10)
 
 
+
+# --------------------------------------------------------------------------
+# D1: the C-family control-keyword guard was language-blind. `foreach`,
+# `using`, `lock`, `fixed` (C#) and `synchronized` (Java) matched
+# _CBRACE_DEF_RE and were measured as functions. These fixtures live at
+# module level because the gate measures function bodies and a fixture inside
+# a test method would be counted as that method's own branching.
+# --------------------------------------------------------------------------
+
+CS_KR_SOURCE = (
+    "public class Importer\n"
+    "{\n"
+    "    public void Import(List<Row> rows, bool strict) {\n"
+    "        foreach (var row in rows) {\n"
+    "            if (row.Valid) { Accept(row); }\n"
+    "        }\n"
+    "        using (var log = Open()) {\n"
+    "            log.Write(\"done\");\n"
+    "        }\n"
+    "        lock (_gate) { _count++; }\n"
+    "    }\n"
+    "}\n"
+)
+
+CS_MIXED_SOURCE = (
+    "public class Importer\n"
+    "{\n"
+    "    public void Import(List<Row> rows, bool strict)\n"
+    "    {\n"
+    "        foreach (var row in rows) {\n"
+    "            if (row.Valid && strict) { Accept(row); }\n"
+    "            else if (row.Retry) { Queue(row); }\n"
+    "            while (row.Next != null) { row = row.Next; }\n"
+    "        }\n"
+    "    }\n"
+    "}\n"
+)
+
+CS_LITERAL_BRACE_HEADER_SOURCE = (
+    "public class Importer\n"
+    "{\n"
+    "    public void Import(string raw) {\n"
+    "        foreach (var part in raw.Split('}')) {\n"
+    "            if (part.Length > 0) { Accept(part); }\n"
+    "        }\n"
+    "    }\n"
+    "}\n"
+)
+
+CS_MULTI_DECL_USING_SOURCE = (
+    "public class Importer\n"
+    "{\n"
+    "    public void Import(List<Row> rows) {\n"
+    "        using (var a = Foo(), b = Bar(), c = Baz(), d = Qux(), e = Zap()) {\n"
+    "            a.Write(b);\n"
+    "        }\n"
+    "    }\n"
+    "}\n"
+)
+
+# r1-F1 follow-up (s2): the same shape with the DOMINANCE reversed. The
+# `using` header declares 5 comma items, the enclosing Go declares 6, so
+# _phantom_is_redundant DOES report the phantom redundant, so it is dropped.
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
+JAVA_SYNCHRONIZED_SOURCE = (
+    "public class Cache\n"
+    "{\n"
+    "    public void put(String k, Object v) {\n"
+    "        synchronized (this) {\n"
+    "            if (k != null) { map.put(k, v); }\n"
+    "        }\n"
+    "    }\n"
+    "}\n"
+)
+
+JS_RESERVED_NAME_METHODS = (
+    "class Store {\n"
+    "    lock(a, b) {\n"
+    "        if (a) { return b; }\n"
+    "        return 0;\n"
+    "    }\n"
+    "    fixed(a) {\n"
+    "        return a;\n"
+    "    }\n"
+    "    using(a, b) {\n"
+    "        if (a && b) { return 1; }\n"
+    "        return 2;\n"
+    "    }\n"
+    "}\n"
+)
+
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
+FULL = [(1, 400)]
+
+
+class TestExtensionScopedControlWords(unittest.TestCase):
+    """The per-extension reserved words suppress a phantom record ONLY when an
+    already-extracted function encloses the match line. Otherwise the phantom
+    is the sole measurement of that method body and is deliberately kept: an
+    over-count is the permitted direction, a silent pass is not."""
+
+    def names(self, path, source):
+        findings, _ = qg.analyze_builtin(path, source, FULL)
+        return [f["function"] for f in findings]
+
+    def by_name(self, path, source):
+        findings, _ = qg.analyze_builtin(path, source, FULL)
+        return {f["function"]: f for f in findings}
+
+    def test_the_function_record_contract_is_one_based_inclusive(self):
+        # The enclosure helper reads these spans, so the convention is pinned
+        # directly rather than inferred: start/end are 1-based inclusive and
+        # header_idx is 0-based, always start - 1.
+        funcs = qg._extract_functions_cbrace(CS_KR_SOURCE.splitlines(), ".cs")
+        self.assertEqual(len(funcs), 1)
+        record = funcs[0]
+        self.assertEqual(sorted(record), ["end", "header_idx", "name", "start"])
+        self.assertEqual(record["name"], "Import")
+        self.assertEqual((record["start"], record["end"]), (3, 11))
+        self.assertEqual(record["header_idx"], record["start"] - 1)
+
+    def test_the_enclosure_helper_reads_one_based_inclusive_spans_strictly(self):
+        # r0-F1: the upper bound is EXCLUSIVE now -- a record whose own end
+        # equals the phantom's header line does not strictly enclose it. That
+        # equality is exactly what a stray brace-in-a-literal on the header
+        # line produces (see test_a_literal_brace_on_the_header_line_...
+        # below), so treating it as enclosure silently drops a real
+        # violation.
+        # r1-F4: the helper now returns the enclosing record or None; the
+        # bound is unchanged.
+        funcs = [{"name": "Import", "start": 3, "end": 11, "header_idx": 2}]
+        self.assertIsNone(qg._strictly_enclosing_record(funcs, 2))
+        self.assertIsNotNone(qg._strictly_enclosing_record(funcs, 3))
+        self.assertIsNotNone(qg._strictly_enclosing_record(funcs, 10))
+        self.assertIsNone(qg._strictly_enclosing_record(funcs, 11))
+        self.assertIsNone(qg._strictly_enclosing_record(funcs, 12))
+        self.assertIsNone(qg._strictly_enclosing_record([], 3))
+
+    def test_the_reserved_words_are_scoped_to_their_own_extensions(self):
+        self.assertEqual(
+            qg._control_words_for(".cs"),
+            frozenset({"foreach", "using", "lock", "fixed"}))
+        self.assertEqual(
+            qg._control_words_for(".java"), frozenset({"synchronized"}))
+        self.assertEqual(qg._control_words_for(".js"), frozenset())
+        self.assertEqual(qg._control_words_for(""), frozenset())
+        self.assertEqual(qg._control_words_for(None), frozenset())
+        # The 9 globally reserved words are unchanged and stay global.
+        self.assertEqual(
+            qg._CONTROL_WORDS,
+            {"if", "for", "while", "switch", "catch", "else", "do",
+             "return", "case"})
+
+    def test_a_kandr_csharp_method_drops_its_enclosed_phantoms(self):
+        # Measured before: 4 records -- Import (3-11, cc 2, cog 3) plus
+        # foreach (4-6, cc 2), using (7-9, cc 1) and lock (10-10, cc 1), all
+        # three inside Import's span. After: Import alone, metrics unchanged.
+        # s2: adding `foreach` to _BRANCH_WORDS raises Import's own count --
+        # cyclomatic 2 -> 3, cognitive 3 -> 5 (the foreach is at brace depth 1,
+        # so _cognitive_approx weights it x2). The extraction list is unchanged.
+        self.assertEqual(
+            qg._extract_functions_cbrace(CS_KR_SOURCE.splitlines(), ".cs"),
+            [{"name": "Import", "start": 3, "end": 11, "header_idx": 2}])
+        found = self.by_name("Importer.cs", CS_KR_SOURCE)
+        self.assertEqual(sorted(found), ["Import"])
+        self.assertEqual(found["Import"]["metrics"], {
+            "cyclomatic_complexity": 3,
+            "method_lines": 9,
+            "parameter_count": 2,
+            "cognitive_complexity": 5,
+            "nesting_depth": 2,
+        })
+
+    def test_a_java_synchronized_block_drops_inside_its_method(self):
+        # Measured before: put (3-7, cc 2, cog 3, nest 2) AND the phantom
+        # synchronized (4-6, cc 2, cog 2, nest 1). After: put alone.
+        self.assertEqual(
+            qg._extract_functions_cbrace(
+                JAVA_SYNCHRONIZED_SOURCE.splitlines(), ".java"),
+            [{"name": "put", "start": 3, "end": 7, "header_idx": 2}])
+        found = self.by_name("Cache.java", JAVA_SYNCHRONIZED_SOURCE)
+        self.assertEqual(sorted(found), ["put"])
+        self.assertEqual(found["put"]["metrics"]["cognitive_complexity"], 3)
+        self.assertEqual(found["put"]["metrics"]["nesting_depth"], 2)
+
+    def test_an_unenclosed_csharp_phantom_is_deliberately_retained(self):
+        # The mixed-brace shape: the method's `{` is on its own line so
+        # _CBRACE_DEF_RE misses the method, and the `foreach` record (5-9,
+        # cc 5, cog 8, ml 5, nest 1) is the ONLY measurement of that body.
+        # Measured: unconditional suppression collapses this file to
+        # class_lines alone. Nothing extracted encloses line 5, so the
+        # record is KEPT, before and after, with every metric identical.
+        # s2: the retained record's own body now counts its `foreach` too --
+        # cyclomatic 5 -> 6, cognitive 8 -> 9. Retention itself is unchanged.
+        self.assertEqual(
+            qg._extract_functions_cbrace(CS_MIXED_SOURCE.splitlines(), ".cs"),
+            [{"name": "foreach", "start": 5, "end": 9, "header_idx": 4}])
+        found = self.by_name("Importer.cs", CS_MIXED_SOURCE)
+        self.assertEqual(sorted(found), ["foreach"])
+        self.assertEqual(found["foreach"]["metrics"], {
+            "cyclomatic_complexity": 6,
+            "method_lines": 5,
+            "parameter_count": 1,
+            "cognitive_complexity": 9,
+            "nesting_depth": 1,
+        })
+
+    def test_javascript_methods_named_lock_fixed_and_using_survive(self):
+        # The safety regression the extension scoping exists to prevent: add
+        # these words GLOBALLY and this file measures zero functions. Measured
+        # both before and after -- lock (2-5, cc 2, cog 2, ml 4, params 2,
+        # nest 1), fixed (6-8, cc 1, cog 0, ml 3, params 1, nest 0),
+        # using (9-12, cc 3, cog 4, ml 4, params 2, nest 1).
+        found = self.by_name("store.js", JS_RESERVED_NAME_METHODS)
+        self.assertEqual(sorted(found), ["fixed", "lock", "using"])
+        self.assertEqual(found["lock"]["metrics"], {
+            "cyclomatic_complexity": 2, "method_lines": 4,
+            "parameter_count": 2, "cognitive_complexity": 2,
+            "nesting_depth": 1,
+        })
+        self.assertEqual(found["fixed"]["metrics"], {
+            "cyclomatic_complexity": 1, "method_lines": 3,
+            "parameter_count": 1, "cognitive_complexity": 0,
+            "nesting_depth": 0,
+        })
+        self.assertEqual(found["using"]["metrics"], {
+            "cyclomatic_complexity": 3, "method_lines": 4,
+            "parameter_count": 2, "cognitive_complexity": 4,
+            "nesting_depth": 1,
+        })
+
+    def test_a_typescript_file_is_not_given_the_csharp_words(self):
+        # .ts and .cs both route to "cbrace"; the scoping key is the
+        # EXTENSION, not the family, so a .ts `using` method survives.
+        found = self.by_name("store.ts", JS_RESERVED_NAME_METHODS)
+        self.assertEqual(sorted(found), ["fixed", "lock", "using"])
+
+    def test_the_global_control_words_still_apply_to_every_extension(self):
+        # Regression guard on the 9 pre-existing words: `if (a) {` must not
+        # become a function in a .cs file either.
+        self.assertNotIn("if", self.names("Importer.cs", CS_KR_SOURCE))
+        self.assertNotIn("if", self.names("store.js", JS_RESERVED_NAME_METHODS))
+
+    def test_a_literal_brace_on_the_control_header_line_keeps_its_phantom(self):
+        # r0-F1: .cs is excluded from _JS_MASK_EXTS, so _match_brace_end reads
+        # raw text and the char literal '}' inside `raw.Split('}')` balances
+        # Import's own scan to depth 0 exactly on the foreach header line,
+        # i.e. Import's measured end EQUALS foreach's header line_no. Under
+        # the old inclusive `_encloses_line` that equality counted as
+        # enclosure and foreach vanished entirely (measured: only "Import"
+        # remained). Under the new strict `_strictly_enclosing_record` equality
+        # no longer enclose, so foreach is retained.
+        funcs = qg._extract_functions_cbrace(
+            CS_LITERAL_BRACE_HEADER_SOURCE.splitlines(), ".cs")
+        names = [fn["name"] for fn in funcs]
+        self.assertIn("foreach", names)
+        found = self.by_name("Importer.cs", CS_LITERAL_BRACE_HEADER_SOURCE)
+        self.assertIn("foreach", found)
+
+    def test_an_enclosed_multi_declaration_using_keeps_its_own_finding(self):
+        # r1-F1: `using (a, b, c, d, e)`'s own header declares 5 comma
+        # items -- more than the enclosing Import(rows) method's 1 parameter
+        # -- so suppressing it as "redundant" would drop a real
+        # parameter_count violation (5 > DEFAULT_THRESHOLDS["parameter_count"]
+        # == 4) that the enclosing record's own header never carries. Measured
+        # before this guard: the phantom was unconditionally suppressed once
+        # enclosed, at parameter_count 5.
+        funcs = qg._extract_functions_cbrace(
+            CS_MULTI_DECL_USING_SOURCE.splitlines(), ".cs")
+        names = [fn["name"] for fn in funcs]
+        self.assertIn("using", names)
+        found = self.by_name("Importer.cs", CS_MULTI_DECL_USING_SOURCE)
+        self.assertIn("using", found)
+        self.assertEqual(found["using"]["metrics"]["parameter_count"], 5)
+        self.assertGreater(
+            found["using"]["metrics"]["parameter_count"],
+            qg.DEFAULT_THRESHOLDS["parameter_count"])
+
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
+            counts = {
+                f["function"]: f["metrics"]["parameter_count"]
+                for f in findings
+            }
+            self.assertEqual(counts, {"Go": 6})
+            self.assertGreater(
+                counts["Go"], qg.DEFAULT_THRESHOLDS["parameter_count"])
+
+
+# --------------------------------------------------------------------------
+# D3: measure()'s skip chain ended in `elif _lang_for(path) is None`, so a
+# SUPPORTED file that yielded zero callables produced neither a function
+# measurement nor a skip record -- it vanished from the report entirely.
+# Measured on a pure-Allman I.cs plus a def-less conf.py: skipped held one
+# entry (notes.md) and neither of the other two files appeared anywhere in it.
+# --------------------------------------------------------------------------
+
+CS_PURE_ALLMAN_SOURCE = (
+    "public class I\n"
+    "{\n"
+    "    public void Import(int a)\n"
+    "    {\n"
+    "        return;\n"
+    "    }\n"
+    "}\n"
+)
+
+
+class TestMeasureSkipRecord(unittest.TestCase):
+    """measure() must leave a record for every changed file it could not
+    measure, distinguishing an unsupported extension from a supported one that
+    yielded no callables. Writes real files, so this is not a pure test."""
+
+    def setUp(self):
+        self._tmp = tempfile.mkdtemp(prefix="quality_gate_skip_")
+        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
+        Path(self._tmp, "I.cs").write_text(
+            CS_PURE_ALLMAN_SOURCE, encoding="utf-8")
+        Path(self._tmp, "conf.py").write_text("x = 1\n", encoding="utf-8")
+        Path(self._tmp, "notes.md").write_text("# notes\n", encoding="utf-8")
+
+    def measure_all(self):
+        changed = {"I.cs": [(1, 7)], "conf.py": [(1, 1)],
+                   "notes.md": [(1, 1)]}
+        funcs, classes, skipped, backends = qg.measure(
+            changed, self._tmp, [])
+        return funcs, classes, skipped, backends
+
+    def test_the_three_skip_reasons_are_distinguishable(self):
+        self.assertEqual(
+            qg._skip_reason("notes.md", "# notes\n"),
+            "unsupported file type for analysis")
+        self.assertEqual(
+            qg._skip_reason("I.cs", CS_PURE_ALLMAN_SOURCE),
+            "no callable found by the builtin heuristic")
+        self.assertEqual(
+            qg._skip_reason("conf.py", "x = 1\n"),
+            "no callable found by the builtin heuristic")
+        self.assertEqual(
+            qg._skip_reason("m.py", "def a(x):\n    return x\n"),
+            "no changed callable found by the builtin heuristic")
+
+    def test_a_supported_file_with_no_callables_leaves_a_skip_record(self):
+        # Measured before: skipped == [{"file": "notes.md", ...}] only -- the
+        # pure-Allman I.cs (which extracts zero functions because
+        # _CBRACE_DEF_RE needs the `{` on the signature line) and the def-less
+        # conf.py appeared in NO record. After: all three are present.
+        funcs, _, skipped, _ = self.measure_all()
+        self.assertEqual(funcs, [])
+        self.assertEqual(
+            {s["file"]: s["reason"] for s in skipped},
+            {"notes.md": "unsupported file type for analysis",
+             "I.cs": "no callable found by the builtin heuristic",
+             "conf.py": "no callable found by the builtin heuristic"})
+
+    def test_the_unsupported_reason_string_is_unchanged(self):
+        # The pre-existing reason text is an output surface; only the new arm
+        # is new, so pin the old string exactly.
+        _, _, skipped, _ = self.measure_all()
+        reasons = [s["reason"] for s in skipped if s["file"] == "notes.md"]
+        self.assertEqual(reasons, ["unsupported file type for analysis"])
+
+    def test_a_measured_file_gets_no_skip_record(self):
+        # The else-arm must not fire for a file that WAS measured.
+        Path(self._tmp, "m.py").write_text(
+            "def a(x):\n    if x:\n        return 1\n    return 0\n",
+            encoding="utf-8")
+        funcs, _, skipped, _ = qg.measure({"m.py": [(1, 4)]}, self._tmp, [])
+        self.assertEqual([f["function"] for f in funcs], ["a"])
+        self.assertEqual(skipped, [])
+
+    def test_class_lines_is_still_emitted_for_a_skipped_supported_file(self):
+        # The skip record is additive: class_lines is not language-routed and
+        # must still be measured for I.cs and conf.py.
+        _, classes, _, _ = self.measure_all()
+        self.assertEqual(
+            {c["file"]: c["class_lines"] for c in classes},
+            {"I.cs": 7, "conf.py": 1})
+
+    def test_an_import_only_edit_does_not_falsely_claim_no_callable_exists(self):
+        # r0-F2: before this fix, measure() reached _skip_reason whenever a
+        # file yielded zero IN-RANGE findings, so an import-only edit to a
+        # file that DOES define real callables -- they just aren't in the
+        # diff -- reported the same "no callable found by the builtin
+        # heuristic" text as a genuinely callable-less file. Measured before:
+        # skipped == [{"file": "m.py",
+        # "reason": "no callable found by the builtin heuristic"}], a false
+        # claim since `def a(x)` is right there, just outside line (1, 1).
+        Path(self._tmp, "m.py").write_text(
+            "import os\ndef a(x):\n    return os.path.join(x)\n",
+            encoding="utf-8")
+        funcs, _, skipped, _ = qg.measure({"m.py": [(1, 1)]}, self._tmp, [])
+        self.assertEqual(funcs, [])
+        self.assertEqual(
+            {s["file"]: s["reason"] for s in skipped},
+            {"m.py": "no changed callable found by the builtin heuristic"})
+
+
 if __name__ == "__main__":
     unittest.main()
