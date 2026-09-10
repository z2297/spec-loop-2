# Review package: fa01826d50b011e0666b2d5ce36ea5dc1a684837..2f2b7c7  (context: -U5)

## Commits
2f2b7c7 fix(gate): record every unmeasured changed file, not just unsupported extensions
29aa74b fix(gate): scope the C-family control-keyword guard by extension, suppressing only enclosed phantoms

## Files changed
 CHANGELOG.md                                   |  34 +++
 plugins/spec-loop/scripts/quality_gate.py      |  92 ++++++--
 plugins/spec-loop/scripts/test_quality_gate.py | 291 +++++++++++++++++++++++++
 3 files changed, 402 insertions(+), 15 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
9,
42
]
],
"plugins/spec-loop/scripts/quality_gate.py": [
[
918,
918
],
[
922,
924
],
[
930,
930
],
[
946,
952
],
[
955,
972
],
[
975,
975
],
[
977,
993
],
[
1072,
1075
],
[
1078,
1078
],
[
1136,
1137
],
[
1282,
1296
],
[
1302,
1306
],
[
1363,
1364
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
1933,
2223
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index ff64bc6..6747ea1 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -4,10 +4,44 @@ All notable changes to the spec-loop plugin are documented here. The format is
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
+  direction this heuristic is permitted to move. Known, documented residuals: a pure-Allman
+  C# file (every brace on its own line, the Visual Studio default) still extracts nothing at
+  all, because `_CBRACE_DEF_RE` requires the `{` on the signature line — deferred to its own
+  run; and `foreach` is still absent from `_BRANCH_WORDS`, so a C# `foreach` adds no
+  cyclomatic branch.
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
 
 ## [2.5.0] - 2026-09-09
 ### Added
 - **`/spec-loop:jira-intake`: read a Jira card, refine it, confirm, and write decisions back.**
   `scripts/jira_client.py` is a stdlib-only, read-first Jira Cloud REST v3 client that resolves
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index a60f537..6b8fbb9 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -913,21 +913,23 @@ def _extract_functions_python(lines):
         funcs.append({"name": m.group(1), "start": i + 1, "end": last_body + 1,
                       "header_idx": i})
     return funcs
 
 
-def _extract_functions_cbrace(lines):
+def _extract_functions_cbrace(lines, ext=""):
     """Split brace-language source into functions by matching the brace that
     opens each detected signature. Returns [{name, start, end, header_idx}] with
     1-based inclusive spans. Best-effort: a signature whose opening brace can't
-    be balanced is skipped."""
+    be balanced is skipped. `ext` is the file's extension, used only to scope
+    the per-language reserved words in _looks_like_call_or_control; it defaults
+    to "" so a caller with no path gets the global words alone."""
     funcs = []
     text_by_line = lines
     for i, line in enumerate(lines):
         name = None
         m = _CBRACE_DEF_RE.search(line)
-        if m and not _looks_like_call_or_control(line, m):
+        if m and not _looks_like_call_or_control(ext, m, funcs, i + 1):
             name = m.group(1)
         else:
             am = _CBRACE_ARROW_RE.search(line)
             if am:
                 name = am.group(1)
@@ -939,19 +941,58 @@ def _extract_functions_cbrace(lines):
         funcs.append({"name": name, "start": i + 1, "end": end + 1,
                       "header_idx": i})
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
+def _encloses_line(funcs, line_no):
+    """True if any already-collected function record contains `line_no`.
+    `funcs` is a list of {name, start, end, header_idx} records whose
+    start/end are 1-BASED INCLUSIVE; `line_no` is 1-based. (PURE)"""
+    return any(fn["start"] <= line_no <= fn["end"] for fn in funcs)
 
 
-def _looks_like_call_or_control(line, match):
+def _looks_like_call_or_control(ext, match, funcs, line_no):
     """True if the C-family signature match is really a control keyword
-    (`if (...) {`) or a function CALL, not a definition. Cheap guard to cut the
-    most common false positives in the heuristic path."""
-    return match.group(1) in _CONTROL_WORDS
+    (`if (...) {`) rather than a definition, so the caller should not record it
+    as a function. `ext` is the file's extension, `match` the _CBRACE_DEF_RE
+    match, `funcs` the records collected so far and `line_no` the match's
+    1-based line.
+
+    A globally reserved word is always rejected. A per-extension word is
+    rejected ONLY when an already-collected record encloses `line_no`, i.e.
+    when the real enclosing method was itself extracted and the phantom is
+    redundant. When nothing encloses it the phantom is the sole measurement of
+    that method body -- measured on a C# method whose brace sits on its own
+    line, dropping it takes the file from a reported cyclomatic 5 / cognitive 8
+    to no function measurement at all -- so it is deliberately kept. That is an
+    over-count, the one direction this heuristic is allowed to move. (PURE)"""
+    word = match.group(1)
+    if word in _CONTROL_WORDS:
+        return True
+    return word in _control_words_for(ext) and _encloses_line(funcs, line_no)
 
 
 def _match_brace_end(lines, header_idx):
     """Return the 0-based index of the line holding the closing brace that
     balances the first `{` at/after header_idx, or None. PURE over `lines`."""
@@ -1026,15 +1067,17 @@ def _cognitive_approx(body_text_or_lines, lang, base_indent):
 
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
@@ -1088,11 +1131,12 @@ def analyze_builtin(path, source, changed_ranges):
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
@@ -1233,16 +1277,35 @@ def _match_changed(records, changed_ranges):
     return [r for r in records
             if _intersects_changed(r["line_start"], r["line_end"],
                                     changed_ranges)]
 
 
+def _skip_reason(path):
+    """Why one changed file produced no function measurement. Returns the
+    unsupported-extension reason when _lang_for(path) is None, otherwise the
+    supported-but-empty reason.
+
+    The second case used to produce NO record at all: the skip chain ended in
+    `elif _lang_for(path) is None`, so a .cs or .rs file whose callables the
+    signature detector could not see -- a pure-Allman C# file, for instance,
+    where every brace sits on its own line -- vanished from the report rather
+    than reporting that it had not been measured. (PURE)"""
+    if _lang_for(path) is None:
+        return "unsupported file type for analysis"
+    return "no callable found by the builtin heuristic"
+
+
 def measure(changed, repo_dir, backends):
     """Measure every changed file, preferring detected backends and falling back
     to the builtin heuristic per file. Returns (function_measurements,
     class_measurements, skipped, used_backends) where each function measurement
     is {file, function, metrics: {...}, source} and skipped is a list of
-    {"metric"|"file", "reason"} entries.
+    {"metric"|"file", "reason"} entries. EVERY changed
+    file that yielded no function measurement gets a `skipped` entry -- an
+    unreadable file, an unsupported extension, or a supported extension whose
+    callables the heuristic could not see (see _skip_reason) -- so a file can
+    never leave the report silently unmeasured.
 
     A backend supplies cyclomatic_complexity / method_lines / parameter_count
     (lizard) or cyclomatic_complexity only (radon); every remaining metric for
     that function -- always cognitive_complexity, plus nesting_depth and any
     metric the backend omitted -- is filled from the builtin heuristic and
@@ -1295,13 +1358,12 @@ def measure(changed, repo_dir, backends):
             for hf in heur_funcs:
                 func_measurements.append({
                     "file": path, "function": hf["function"],
                     "metrics": hf["metrics"], "source": "builtin-heuristic",
                 })
-        elif _lang_for(path) is None:
-            skipped.append({"file": path,
-                            "reason": "unsupported file type for analysis"})
+        else:
+            skipped.append({"file": path, "reason": _skip_reason(path)})
 
         if heur_class is not None:
             class_measurements.append({
                 "file": path, "class_lines": heur_class["class_lines"],
                 "source": "builtin-heuristic",
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index 1b72581..50fede9 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -1928,7 +1928,298 @@ class TestDifferentialAgainstRawScan(unittest.TestCase):
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
+    def test_the_enclosure_helper_reads_one_based_inclusive_spans(self):
+        funcs = [{"name": "Import", "start": 3, "end": 11, "header_idx": 2}]
+        self.assertFalse(qg._encloses_line(funcs, 2))
+        self.assertTrue(qg._encloses_line(funcs, 3))
+        self.assertTrue(qg._encloses_line(funcs, 11))
+        self.assertFalse(qg._encloses_line(funcs, 12))
+        self.assertFalse(qg._encloses_line([], 3))
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
+        self.assertEqual(
+            qg._extract_functions_cbrace(CS_KR_SOURCE.splitlines(), ".cs"),
+            [{"name": "Import", "start": 3, "end": 11, "header_idx": 2}])
+        found = self.by_name("Importer.cs", CS_KR_SOURCE)
+        self.assertEqual(sorted(found), ["Import"])
+        self.assertEqual(found["Import"]["metrics"], {
+            "cyclomatic_complexity": 2,
+            "method_lines": 9,
+            "parameter_count": 2,
+            "cognitive_complexity": 3,
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
+        self.assertEqual(
+            qg._extract_functions_cbrace(CS_MIXED_SOURCE.splitlines(), ".cs"),
+            [{"name": "foreach", "start": 5, "end": 9, "header_idx": 4}])
+        found = self.by_name("Importer.cs", CS_MIXED_SOURCE)
+        self.assertEqual(sorted(found), ["foreach"])
+        self.assertEqual(found["foreach"]["metrics"], {
+            "cyclomatic_complexity": 5,
+            "method_lines": 5,
+            "parameter_count": 1,
+            "cognitive_complexity": 8,
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
+    def test_the_two_skip_reasons_are_distinguishable(self):
+        self.assertEqual(
+            qg._skip_reason("notes.md"),
+            "unsupported file type for analysis")
+        self.assertEqual(
+            qg._skip_reason("I.cs"),
+            "no callable found by the builtin heuristic")
+        self.assertEqual(
+            qg._skip_reason("conf.py"),
+            "no callable found by the builtin heuristic")
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
+
 if __name__ == "__main__":
     unittest.main()
