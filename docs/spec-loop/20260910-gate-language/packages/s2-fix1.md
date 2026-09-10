# Review package: fa01826..5ba3c6b  (context: -U5)

## Commits
5ba3c6b fix(quality-gate): reformat dict comprehension to clear nesting_depth threshold
e933d5e docs(gate): correct the phantom-suppression safety claim and name its parameter_count residual
acf8dcf feat(gate): count C# foreach as a cyclomatic branch
b574405 Merge spec-loop slice s1: language-scoped control-keyword guard with coverage-conditional suppression, and a record for every unmeasured changed file
c52d9f2 fix(gate): strict enclosure and param-aware suppression close two under-count paths; skip reasons and measure() refactored
2f2b7c7 fix(gate): record every unmeasured changed file, not just unsupported extensions
29aa74b fix(gate): scope the C-family control-keyword guard by extension, suppressing only enclosed phantoms

## Files changed
 CHANGELOG.md                                   | 112 ++++++
 plugins/spec-loop/scripts/quality_gate.py      | 340 ++++++++++++++----
 plugins/spec-loop/scripts/test_quality_gate.py | 477 ++++++++++++++++++++++++-
 3 files changed, 858 insertions(+), 71 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
9,
120
]
],
"plugins/spec-loop/scripts/quality_gate.py": [
[
136,
143
],
[
925,
942
],
[
946,
948
],
[
950,
951
],
[
954,
954
],
[
957,
960
],
[
964,
970
],
[
973,
1017
],
[
1020,
1020
],
[
1022,
1049
],
[
1128,
1131
],
[
1134,
1134
],
[
1192,
1193
],
[
1338,
1464
],
[
1470,
1475
],
[
1484,
1484
],
[
1486,
1487
],
[
1490,
1490
],
[
1497,
1498
],
[
1502,
1508
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
1953,
2407
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index ff64bc6..09d4f61 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -4,10 +4,122 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
+### Fixed
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
+  read from its own header and is NOT — see the `_phantom_has_more_params` entry below.
+  Known, documented residuals: a pure-Allman C# file (every brace on its own line, the
+  Visual Studio default) still extracts nothing at all, because `_CBRACE_DEF_RE` requires
+  the `{` on the signature line — deferred to its own run. (The second residual named here
+  — `foreach` absent from `_BRANCH_WORDS` — is fixed below in this same Unreleased
+  section.)
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
+  `_strictly_encloses_line`) tested only `fn["start"] <= line_no <= fn["end"]`; because `.cs`
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
+  own signature. The new PURE `_phantom_has_more_params` compares the phantom's own header
+  against the enclosing record's header and keeps the phantom whenever its count is higher;
+  `test_an_enclosed_multi_declaration_using_keeps_its_own_finding` pins a 5-parameter `using`
+  surviving inside a 1-parameter `Import` method (5 > `DEFAULT_THRESHOLDS["parameter_count"]`
+  == 4). Both are the same failure family the run's NEVER-UNDER-COUNT constraint names.
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
index a60f537..9fcfa74 100644
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
@@ -913,45 +920,135 @@ def _extract_functions_python(lines):
         funcs.append({"name": m.group(1), "start": i + 1, "end": last_body + 1,
                       "header_idx": i})
     return funcs
 
 
-def _extract_functions_cbrace(lines):
+def _cbrace_name_at(lines, ext, funcs, i):
+    """The function name detected at 0-based line `i` (else None), tried as a
+    brace signature first and an arrow form second. `funcs` is the record list
+    collected so far, needed by the control-keyword guard. Extracted out of
+    _extract_functions_cbrace purely to keep that loop's own nesting shallow;
+    carries no state across calls. (PURE)"""
+    line = lines[i]
+    m = _CBRACE_DEF_RE.search(line)
+    state = {"funcs": funcs, "lines": lines}
+    if m and not _looks_like_call_or_control(ext, m, i + 1, state):
+        return m.group(1)
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
+def _strictly_encloses_line(funcs, line_no):
+    """True if any already-collected function record STRICTLY contains
+    `line_no`, i.e. `line_no` is not the record's own last line. `funcs` is a
+    list of {name, start, end, header_idx} records whose start/end are
+    1-BASED INCLUSIVE; `line_no` is 1-based.
+
+    The upper bound is exclusive on purpose: a record's span can only reach
+    exactly the phantom's header line when a non-JS-masked brace language
+    (.cs/.java are excluded from _JS_MASK_EXTS) counts a `}` inside a string
+    or char literal ON that header line and balances the enclosing scan to
+    depth 0 there. In that case the enclosing record does not actually
+    dominate the phantom's body, so equality must not count as enclosure --
+    otherwise the phantom (and the real violation it measures) is suppressed
+    while the record kept in its place covers almost none of it. (PURE)"""
+    return any(fn["start"] <= line_no < fn["end"] for fn in funcs)
+
+
+def _phantom_has_more_params(funcs, line_no, lines):
+    """True if a control-keyword phantom's own header declares more
+    comma-separated items than the real function record enclosing it -- e.g. a
+    C# `using (a, b, c, d, e)` inside a method whose own signature takes one
+    argument. When true the phantom must be kept despite being a control
+    keyword: collapsing it into the enclosing record would silently drop a
+    parameter_count violation the enclosing record's own header does not
+    carry, the exact under-count this heuristic must never introduce. Assumes
+    an enclosing record exists (only called once one has been confirmed).
+    (PURE)"""
+    enclosing = next(
+        fn for fn in funcs if fn["start"] <= line_no < fn["end"])
+    phantom_params = _count_params(lines[line_no - 1])
+    enclosing_params = _count_params(lines[enclosing["header_idx"]])
+    return phantom_params > enclosing_params
 
 
-def _looks_like_call_or_control(line, match):
+def _looks_like_call_or_control(ext, match, line_no, state):
     """True if the C-family signature match is really a control keyword
-    (`if (...) {`) or a function CALL, not a definition. Cheap guard to cut the
-    most common false positives in the heuristic path."""
-    return match.group(1) in _CONTROL_WORDS
+    (`if (...) {`) rather than a definition, so the caller should not record it
+    as a function. `ext` is the file's extension, `match` the _CBRACE_DEF_RE
+    match and `line_no` the match's 1-based line. `state` bundles the two
+    pieces of scan-so-far context the redundancy check below needs together --
+    {"funcs": the records collected so far, "lines": the file's raw source
+    lines} -- kept as one parameter rather than two positional ones.
+
+    A globally reserved word is always rejected. A per-extension word is
+    rejected ONLY when an already-collected record strictly encloses
+    `line_no` (see _strictly_encloses_line) AND the phantom's own header does
+    not declare more parameters than that enclosing record's header (see
+    _phantom_has_more_params) -- i.e. when the real enclosing method was
+    itself extracted and the phantom is redundant on every metric it would
+    have measured. When nothing encloses it the phantom is the sole
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
+    funcs = state["funcs"]
+    if not _strictly_encloses_line(funcs, line_no):
+        return False
+    return not _phantom_has_more_params(funcs, line_no, state["lines"])
 
 
 def _match_brace_end(lines, header_idx):
     """Return the 0-based index of the line holding the closing brace that
     balances the first `{` at/after header_idx, or None. PURE over `lines`."""
@@ -1026,15 +1123,17 @@ def _cognitive_approx(body_text_or_lines, lang, base_indent):
 
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
@@ -1088,11 +1187,12 @@ def analyze_builtin(path, source, changed_ranges):
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
@@ -1233,81 +1333,181 @@ def _match_changed(records, changed_ranges):
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
index 1b72581..5091928 100644
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
@@ -1928,7 +1948,462 @@ class TestDifferentialAgainstRawScan(unittest.TestCase):
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
+        funcs = [{"name": "Import", "start": 3, "end": 11, "header_idx": 2}]
+        self.assertFalse(qg._strictly_encloses_line(funcs, 2))
+        self.assertTrue(qg._strictly_encloses_line(funcs, 3))
+        self.assertTrue(qg._strictly_encloses_line(funcs, 10))
+        self.assertFalse(qg._strictly_encloses_line(funcs, 11))
+        self.assertFalse(qg._strictly_encloses_line(funcs, 12))
+        self.assertFalse(qg._strictly_encloses_line([], 3))
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
+        # remained). Under the new strict `_strictly_encloses_line` equality
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
