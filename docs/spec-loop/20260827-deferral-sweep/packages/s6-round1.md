# Review package: 8518f56aa84d0128b7271210f2dec489aacd8b68..0c0495c  (context: -U5)

## Commits
0c0495c docs(quality-gate): widen the test module docstring to the brace-language mask
0de7c74 test(quality-gate): keep a counted branch word out of the new phantom-test comment
eb37700 docs(quality-gate): the brace scan mask recognises five constructs, not four
2cc6177 fix(quality-gate): correct the regex-quote residual claims to the measured behaviour
782e71c fix(quality-gate): mask only the JS family, keep other brace languages raw
fe46b34 Fix: block-comment mask can silently cross a regex literal into a real comment
615817d quality-gate: brace-language scan mask verified across the suite
506aad2 quality-gate: measured pins for the brace mask over the real workflow
e9dee8b quality-gate: pin interpolation, comment and mjs mask behaviour
dc8548c quality-gate: brace-language branch scans read the masked source
29ce895 quality-gate: cbrace span scanner for comments, strings and templates

## Files changed
 plugins/spec-loop/scripts/quality_gate.py      | 299 +++++++++++++-
 plugins/spec-loop/scripts/test_quality_gate.py | 528 ++++++++++++++++++++++++-
 2 files changed, 796 insertions(+), 31 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/quality_gate.py": [
[
31,
35
],
[
100,
111
],
[
395,
408
],
[
466,
471
],
[
573,
803
],
[
806,
810
],
[
978,
978
],
[
981,
984
],
[
1014,
1016
],
[
1024,
1024
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
7,
13
],
[
84,
147
],
[
482,
493
],
[
589,
761
],
[
793,
868
],
[
974,
974
],
[
976,
988
],
[
1015,
1081
],
[
1562,
1651
],
[
1714,
1724
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index 05a62d1..a7d9217 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -26,14 +26,15 @@ Pipeline:
   4. Builtin heuristic -- for any changed file no backend covers, a pure-stdlib
      analyzer splits the source into functions by signature regex (python / js /
      ts / java / c# / go styles, language by extension) and estimates each
      metric by branch-keyword counting, signature parsing, and indent/brace
      nesting. Branch counting reads a masked copy of the source in which the
-     content of python string literals and comments has been replaced by a
-     sentinel, so words and punctuation inside them are not measured as
-     branching; a tokenizer failure falls back to the raw text. Every such
-     finding is marked "source": "builtin-heuristic".
+     content of string literals and comments has been replaced by a sentinel
+     -- python via stdlib tokenize, brace languages via a hand scanner that
+     keeps ${} interpolation code visible -- so words and punctuation inside
+     them are not measured as branching; a scanner failure falls back to the
+     raw text. Every such finding is marked "source": "builtin-heuristic".
      cognitive_complexity is ONLY ever produced by this heuristic (a
      nesting-weighted approximation) or skipped -- it is never attributed to a
      real tool.
   5. crap_score -- only when a coverage report is found (--coverage, else a
      probe of the repo root for coverage.xml / lcov.info / cobertura*.xml).
@@ -94,10 +95,22 @@ _EXT_LANG = {
     ".java": "cbrace", ".cs": "cbrace", ".go": "cbrace",
     ".c": "cbrace", ".h": "cbrace", ".cpp": "cbrace", ".cc": "cbrace",
     ".hpp": "cbrace", ".rs": "cbrace",
 }
 
+# The subset of the brace extensions whose scan mask may be lexed by the hand
+# scanner below. It implements JS/TypeScript quoting rules alone, where a single
+# quote always opens a string. In Rust a single quote usually opens a lifetime,
+# in C++ it also serves as a digit separator, so two of them on one line pair
+# into a phantom string covering the real code between them -- measured, that
+# turns 2 branches into 1 with no signal, the one direction this mask is never
+# allowed to move a count. Rust, C, C++, Go, Java and C# therefore keep their
+# raw text: they stay on today's over-count, which is the safe direction,
+# rather than being lexed by quoting rules that are not theirs.
+_JS_MASK_EXTS = frozenset(
+    {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"})
+
 # Branch keywords whose occurrence adds one to cyclomatic complexity. Matched as
 # whole words (or operators) so an identifier like `ifield` is not counted.
 _BRANCH_WORDS = ("if", "elif", "case", "catch", "for", "while", "when")
 _BRANCH_WORD_RE = re.compile(r"\b(?:%s)\b" % "|".join(_BRANCH_WORDS))
 # Boolean operators and the ternary each add a branch. `else if` is NOT listed
@@ -377,10 +390,24 @@ def _parse_radon_json(text):
 
 def _lang_for(path):
     return _EXT_LANG.get(os.path.splitext(path)[1].lower())
 
 
+def _scan_lang_for(path):
+    """The language family whose scan mask may be applied to `path`, else None
+    to leave the file on raw text. Distinct from _lang_for on purpose: that one
+    picks the extraction and nesting model, this one picks the mask, and only
+    the JS/TypeScript subset of the brace extensions has a mask that lexes its
+    quoting correctly. (PURE)"""
+    lang = _lang_for(path)
+    if lang != "cbrace":
+        return lang
+    if os.path.splitext(path)[1].lower() in _JS_MASK_EXTS:
+        return "js"
+    return None
+
+
 def _count_params(sig):
     """Count parameters in a parenthesized signature substring. PURE. Splits the
     top-level parameter list on commas ignoring nested brackets, and drops a
     leading python `self`/`cls`."""
     depth = 0
@@ -434,11 +461,16 @@ def _count_params(sig):
 # a masked docstring continuation line starts at column 0 and would move the
 # indent-derived end of the enclosing function. Masked spans are filled with a
 # non-whitespace sentinel rather than spaces, because _cognitive_approx derives
 # its nesting level from leading whitespace: space-fill would RAISE the measured
 # cognitive complexity of dozens of functions. Every failure path returns the
-# raw text, so the worst case remains today's over-count.
+# raw text, so the worst case remains today's over-count. Two maskers sit
+# behind this seam: python via stdlib tokenize, the JS/TypeScript family
+# (.js, .jsx, .mjs, .cjs, .ts, .tsx) via the hand scanner below. The remaining
+# brace extensions -- .rs, .c, .h, .cpp, .cc, .hpp, .go, .java, .cs -- are
+# deliberately NOT masked, because the hand scanner lexes JS quoting rules
+# alone. _scan_lang_for holds that routing.
 
 _SCAN_SENTINEL = "x"
 
 # The corruption trip-wire, expressed as a denominator: a mask that leaves more
 # than one line in _MASK_LOST_DENOM of the non-blank lines with no content at
@@ -536,18 +568,248 @@ def _mask_python_literals(text):
     if _mask_lost_too_much(rows, masked):
         return None
     return "\n".join(masked)
 
 
+# --------------------------------------------------------------------------
+# Brace-language scan mask
+# --------------------------------------------------------------------------
+# Brace languages get no stdlib tokenizer, so this is a hand character
+# scanner over five constructs: the two comment forms and the three string
+# forms. Template literals are handled separately from the flat forms
+# because a ${...} interpolation holds real code -- blanking a whole template
+# deletes genuine operators and UNDER-counts a function, the dangerous
+# direction. The scanner stops short of one construct on purpose: a regex
+# literal. Telling a regex literal from a division operator needs the
+# parser's expectation of the next token, which a character scanner does not
+# have, so a lone slash outside a comment is stepped over and a regex
+# literal's interior stays visible. Three residuals follow from that. First,
+# a quote character inside a regex literal opens a phantom string, and that
+# phantom can cover real operator punctuation lying between it and a later
+# quote, which lowers a count silently. Two limits a reader might expect are
+# NOT there, both measured against _mask_cbrace_literals and pinned by
+# TestRegexQuotePhantom. An odd number of quote characters on the line does
+# not force the whole-file fallback: a trailing line comment swallows the
+# unpaired quote before end-of-line, so the mask succeeds with a real
+# boolean operator hidden, and that line's branch count drops from 2 to 1.
+# Nor is the phantom held to one line: the quote alternative accepts a
+# backslash followed by any character, the newline included, so a backslash
+# in final position on the opening line carries the phantom onto the next
+# line and hides real operator punctuation there, with the same shape
+# repeatable to extend it further. Second, a doubled slash inside a regex
+# literal reads as a line comment and masks the rest of that line, which
+# lowers a count silently as well. Neither residual is guarded; both are
+# recorded rather than fixed, and hardening the scanner against them is
+# deferred to a slice that can carry its own differential re-measurement.
+# Third, and unbounded: a star-slash sequence inside a regex literal's
+# character contents reads as a block-comment opener, and the block-comment
+# alternative's closing search crosses newlines, so it would otherwise pair
+# with the next real block comment anywhere later in the source and blank
+# every line between the two.
+# The scanner guards against this one directly: once a bare slash has been
+# stepped over on the current source line, a later star-slash sequence on
+# that same line is refused rather than treated as a comment opener, and the
+# whole scan fails toward raw text instead of silently under-counting. That
+# guard is verified by a dedicated test rather than a repo sweep, because a
+# sweep can only bound occurrences that already exist, not ones a later file
+# introduces. Measured at the time this landed, the sweep of regex-literal
+# uses in this repo surfaced none containing a quote character, every
+# doubled slash the scanner treated as a line comment was a genuine trailing
+# comment after a properly closed regex literal, and the scanner closes every
+# construct it recognises in every brace source here. The sweeping greps
+# behind those statements are recorded in the slice report.
+
+_CB_FLAT_RE = re.compile(
+    r"//[^\n]*"
+    r"|/\*[\s\S]*?\*/"
+    r"|'(?:\\[\s\S]|[^'\\\n])*'"
+    r'|"(?:\\[\s\S]|[^"\\\n])*"'
+)
+_CB_OPENERS = "/'\""
+_CB_TPL_RE = re.compile(r"\\[\s\S]|\$\{|`")
+_CB_DEPTH = {"{": 1, "}": -1}
+
+
+def _cb_flat_step(text, pos, stop, slash_since_newline):
+    """One scanner step at a comment or a quote opener: (next_pos, spans,
+    slash_since_newline) once the flat regex closed the construct, else None
+    to fail toward raw text. A lone slash is division or a regex literal, so
+    it is stepped over and remembered for the rest of the line. A star-slash
+    match reached after such a lone slash on the same line is refused rather
+    than treated as a block-comment opener, since its unbounded closing
+    search would otherwise pair with a real block comment far later in the
+    file and blank real code in between; refusing sends the whole scan back
+    to raw text instead. (PURE)"""
+    is_block_open = text.startswith("/*", pos)
+    if slash_since_newline and is_block_open:
+        return None
+    m = _CB_FLAT_RE.match(text, pos, stop)
+    if m is not None:
+        return m.end(), [(m.start(), m.end())], slash_since_newline
+    if text[pos] == "/" and not is_block_open:
+        return pos + 1, [], True
+    return None
+
+
+def _cb_step(text, pos, stop, slash_since_newline):
+    """One scanner step from `pos`: (next_pos, mask_spans,
+    slash_since_newline), else None to fail toward raw text. The
+    lone-slash memory resets at the newline that ends its line. (PURE)"""
+    ch = text[pos]
+    if ch == "\n":
+        return pos + 1, [], False
+    if ch == "`":
+        got = _cb_template_step(text, pos, stop)
+        if got is None:
+            return None
+        nxt, spans = got
+        return nxt, spans, slash_since_newline
+    if ch in _CB_OPENERS:
+        return _cb_flat_step(text, pos, stop, slash_since_newline)
+    return pos + 1, [], slash_since_newline
+
+
+def _cbrace_spans(text, start, stop):
+    """The mask spans over text[start:stop] as half-open (begin, end)
+    character ranges covering comment and string content, else None once a
+    construct never closes, which sends the caller back to raw text.
+    (PURE)"""
+    spans = []
+    pos = start
+    slash_since_newline = False
+    while pos < stop:
+        got = _cb_step(text, pos, stop, slash_since_newline)
+        if got is None:
+            return None
+        pos, found, slash_since_newline = got
+        spans.extend(found)
+    return spans
+
+
+def _cb_depth_delta(text, pos, got):
+    """The brace-depth change one scanner step makes: nonzero only on a plain
+    code character, so braces inside a literal or a comment are ignored.
+    (PURE)"""
+    plain = (got[0] == pos + 1) and not got[1]
+    if not plain:
+        return 0
+    return _CB_DEPTH.get(text[pos], 0)
+
+
+def _cb_interp_end(text, start, stop):
+    """The index just past the brace closing the ${ that opens at `start`,
+    paired with the mask spans found inside it, else None. Nested literals
+    and comments are stepped over with the same scanner, so a brace inside
+    one does not close the interpolation; their spans are returned here so
+    the caller reuses this single walk rather than repeating it. (PURE)"""
+    depth = 1
+    pos = start + 2
+    spans = []
+    slash_since_newline = False
+    while pos < stop:
+        got = _cb_step(text, pos, stop, slash_since_newline)
+        if got is None:
+            return None
+        depth += _cb_depth_delta(text, pos, got)
+        if depth == 0:
+            return pos + 1, spans
+        spans.extend(got[1])
+        pos, _found, slash_since_newline = got
+    return None
+
+
+def _cb_template_hop(text, m, stop, chunk):
+    """The scanner state after one non-closing hit inside a template literal:
+    (next_pos, next_chunk_start, spans). A backslash escape masks straight
+    through. A ${ ends the current masked chunk, scans the interpolation as
+    ordinary code, and restarts the chunk past its closing brace.
+    (None, None, []) once the interpolation never closes. (PURE)"""
+    if m.group(0) != "${":
+        return m.end(), chunk, []
+    got = _cb_interp_end(text, m.start(), stop)
+    if got is None:
+        return None, None, []
+    end, inner = got
+    return end, end, [(chunk, m.start())] + inner
+
+
+def _cb_template_step(text, pos, stop):
+    """The whole template literal opening at the backtick at `pos`:
+    (next_pos, mask_spans). Literal content is masked and every ${...}
+    interpolation is scanned as ordinary code, so real operators inside one
+    stay visible. None once the literal never closes. (PURE)"""
+    spans = []
+    chunk = pos
+    m = _CB_TPL_RE.search(text, pos + 1, stop)
+    while m is not None:
+        if m.group(0) == "`":
+            spans.append((chunk, m.end()))
+            return m.end(), spans
+        nxt, chunk, inner = _cb_template_hop(text, m, stop, chunk)
+        if nxt is None:
+            return None
+        spans.extend(inner)
+        m = _CB_TPL_RE.search(text, nxt, stop)
+    return None
+
+
+# The fill preserves the newline and the two brace characters. Line count and
+# line lengths matter because a masked body must cover exactly the same lines
+# as its raw body, and brace positions matter because _cognitive_approx's
+# brace-language arm derives its nesting level from the brace counts it sees
+# on the masked text: dropping a brace out of a literal could RAISE the
+# weight of every following line, and the mask is only ever allowed to lower
+# a count. Neither character carries a branch word or operator punctuation,
+# so preserving both is measurement-neutral. Same shape as the reason the
+# sentinel is non-whitespace.
+_CB_PRESERVED = "\n{}"
+
+
+def _cb_masked_char(ch):
+    """The mask character of one source character: the newline and the two
+    brace characters survive, everything else becomes the sentinel.
+    (PURE)"""
+    if ch in _CB_PRESERVED:
+        return ch
+    return _SCAN_SENTINEL
+
+
+def _mask_cbrace_literals(text):
+    """`text` with comment and string content replaced by the non-whitespace
+    sentinel, preserving line count, line lengths and brace positions, else
+    None to fall back to the raw text. Code inside a ${} interpolation stays
+    visible. (PURE)"""
+    spans = _cbrace_spans(text, 0, len(text))
+    if spans is None:
+        return None
+    chars = list(text)
+    for begin, end in spans:
+        chars[begin:end] = [_cb_masked_char(ch) for ch in chars[begin:end]]
+    masked = "".join(chars)
+    if _mask_lost_too_much(text.split("\n"), masked.split("\n")):
+        return None
+    return masked
+
+
+def _mask_for_lang(text, lang):
+    """The masked form of `text` in one SCAN language, else None once no mask
+    applies. Keyed by the value _scan_lang_for produces, never by the
+    extraction family. (PURE)"""
+    if lang == "python":
+        return _mask_python_literals(text)
+    if lang == "js":
+        return _mask_cbrace_literals(text)
+    return None
+
+
 def _strip_for_scan(text, lang):
     """`text` with string-literal and comment content masked out, so words and
-    punctuation inside literals stop being measured as real branching. Python is
-    masked via stdlib tokenize; every other language is returned unchanged, so
-    the brace scanner keeps its current behaviour. (PURE)"""
-    if lang != "python":
-        return text
-    masked = _mask_python_literals(text)
+    punctuation inside literals stop being measured as real branching. Python
+    is masked via stdlib tokenize, the JS/TypeScript family via the hand
+    scanner that keeps ${} interpolation code visible. Every other language
+    family, plus every mask failure, returns the raw text. (PURE)"""
+    masked = _mask_for_lang(text, lang)
     if masked is None:
         return text
     return masked
 
 
@@ -711,15 +973,17 @@ def _nesting_depth_for(body_lines, lang, base_indent):
     if lang == "python":
         return _nesting_depth_python(body_lines[1:], base_indent)
     return _nesting_depth_braces("\n".join(body_lines))
 
 
-def _scan_lines_for(source, lang, lines):
+def _scan_lines_for(source, scan_lang, lines):
     """The masked counterpart of `lines`, for the two branch scans only. Falls
     back to `lines` unless the mask preserved the physical line count exactly,
-    so a masked body always covers the same lines as its raw body. (PURE)"""
-    scan_lines = _strip_for_scan(source, lang).splitlines()
+    so a masked body always covers the same lines as its raw body. The
+    language here is the SCAN language from _scan_lang_for, not the extraction
+    family. (PURE)"""
+    scan_lines = _strip_for_scan(source, scan_lang).splitlines()
     if len(scan_lines) != len(lines):
         return lines
     return scan_lines
 
 
@@ -745,20 +1009,21 @@ def analyze_builtin(path, source, changed_ranges):
     """Pure-stdlib heuristic analysis of one changed file. Returns
     (function_findings, class_finding_or_None) where each finding is a dict of
     measured metric values for functions intersecting `changed_ranges`, tagged
     source="builtin-heuristic". `source` is the file text; changed_ranges is the
     file's list of (start, end) changed spans. The two branch scans read a
-    masked copy of the source (see _strip_for_scan); every other metric reads
-    the raw text.
+    masked copy of the source (see _strip_for_scan); the mask is selected by
+    _scan_lang_for, so a brace language outside the JS family keeps its raw
+    text. Every other metric reads the raw text.
 
     An unsupported/binary file (no known language) yields ([], None); the caller
     records a skip for it."""
     lang = _lang_for(path)
     if lang is None:
         return [], None
     lines = source.splitlines()
-    scan_lines = _scan_lines_for(source, lang, lines)
+    scan_lines = _scan_lines_for(source, _scan_lang_for(path), lines)
     funcs = _extract_functions_for(lines, lang)
 
     findings = []
     for fn in funcs:
         if not _intersects_changed(fn["start"], fn["end"], changed_ranges):
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index b8025df..af1f146 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -2,15 +2,17 @@
 """Tests for the objective code-quality gate (stdlib unittest).
 
 Covers the PURE diff parser on embedded fixture text, config loading (defaults /
 loaded / disabled / malformed), the pure metric primitives (parameter counting,
 branch counting, nesting depth, CRAP, cognitive approximation), the scan mask
-that hides python string-literal and comment content from the two branch
-scans (including its fall-back-to-raw paths), a differential harness
-comparing masked against raw measurement over every heuristic-readable file
-in the plugin tree, the builtin heuristic function extraction for python and
-brace languages, backend CSV/JSON
+that hides string-literal and comment content from the two branch scans for
+python and the JS/TypeScript family alike (including its extension routing, the
+brace languages left deliberately unmasked, the measured regex-versus-quote
+residuals, and every fall-back-to-raw path), a differential harness comparing
+masked against raw measurement over every heuristic-readable file in the plugin
+tree, the builtin heuristic function extraction for python and brace languages,
+backend CSV/JSON
 parsing and backend+heuristic merging with per-metric sourcing (cognitive is
 NEVER attributed to a tool), coverage parsing (cobertura + lcov) and CRAP
 assembly, custom-gate evaluation (metric-form evaluated here, command-form
 deferred to the skill), threshold pass/fail + report shape, and main()'s exit
 codes. Backends are exercised by mocking shutil.which / subprocess.run so the
@@ -77,10 +79,74 @@ MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE = (
     "        ''' " + "if" + " b " + "else" + " 'z'\n"
     "        return s\n"
     "    return b\n"
 )
 
+# A template literal whose interpolation carries REAL operators, plus a
+# comment and a single-quoted string that carry fake ones. Module level, for
+# the reason given above the python fixtures.
+CBRACE_TEMPLATE_SOURCE = (
+    "function probe(e) {\n"
+    "    // a comment that isn't code: " + BRANCH_WORDS_IN_LITERALS + "\n"
+    "    const s = `msg ${String((e && e.message) || e)} "
+    + BRANCH_WORDS_IN_LITERALS + "`;\n"
+    "    /* block " + BRANCH_WORDS_IN_LITERALS + " */\n"
+    "    " + "if" + " (s) { return s; }\n"
+    "    return '" + BRANCH_WORDS_IN_LITERALS + "';\n"
+    "}\n"
+)
+
+CBRACE_UNTERMINATED_SOURCE = (
+    "function probe(a) {\n"
+    "    const s = 'never closed " + BRANCH_WORDS_IN_LITERALS + ";\n"
+    "    return a;\n"
+    "}\n"
+)
+
+CBRACE_APOSTROPHE_COMMENTS_SOURCE = (
+    "function probe(a, b) {\n"
+    "    // it doesn't matter\n"
+    "    " + "if" + " (a) { return b; }\n"
+    "    // and it isn't a literal\n"
+    "    " + "for" + " (const x of b) { a += x; }\n"
+    "    return a;\n"
+    "}\n"
+)
+
+# Three shapes that a JS-quoting mask corrupts in a NON-JS brace language. In
+# Rust a single quote opens a lifetime, in C++ it also serves as a digit
+# separator, so two of them on one line pair into a phantom string spanning the
+# real code between them. Measured raw-versus-masked branch counts are pinned
+# below. The third fixture is the C++ shape wrapped in an extractable function,
+# used to drive the routing through analyze_builtin end to end.
+RUST_LIFETIME_LINE = (
+    "fn f(a: &'x A, b: &'y B) -> bool { helper(&'x a) && other(&'y b) }\n")
+CPP_DIGIT_SEPARATOR_LINE = "int x = 1'000 + (a ? b : c) + 2'000;\n"
+CPP_DIGIT_SEPARATOR_FUNCTION = (
+    "int f(int a) { int x = 1'000 + (a ? 2 : 3) + 2'000; return x; }\n")
+
+# The measured counter-example to the claim that an odd number of quote
+# characters on a line forces a whole-file fallback: the first two quotes sit
+# inside single-character regex literals and pair into a phantom string over the
+# real boolean operator, the third is swallowed by the trailing line comment, so
+# the odd count never survives to end-of-line.
+REGEX_QUOTE_PHANTOM_SOURCE = (
+    "x = /'/.test(a) && /'/.test(b); // don't\n"
+    "y = p && q;\n"
+)
+
+# The measured counter-example to the claim that such a phantom stays on its own
+# line. _CB_FLAT_RE's escape alternative accepts a backslash followed by ANY
+# character, the newline included, so a backslash in final position on the
+# opening line carries the phantom forward and hides a real boolean operator on
+# the NEXT line. Chaining that shape extends the phantom arbitrarily.
+REGEX_QUOTE_PHANTOM_MULTILINE = (
+    "a = /'\\\n"
+    "p && q'/ ;\n"
+    "z = 1;\n"
+)
+
 
 def unmasked(text, lang):
     """Identity stand-in for qg._strip_for_scan, so a test can measure the same
     source the way the gate measured it before the mask existed. Named at module
     level because a paren-aligned mock.patch.object continuation inside a test
@@ -411,16 +477,22 @@ class TestCognitiveApprox(unittest.TestCase):
 # --------------------------------------------------------------------------
 # _strip_for_scan — the mask handed to the two branch scans
 # --------------------------------------------------------------------------
 
 class TestStripForScan(unittest.TestCase):
-    def test_a_non_python_language_is_returned_byte_for_byte(self):
-        # This slice masks python only; the brace scanner keeps today's
-        # behaviour until the follow-up slice.
-        self.assertEqual(
-            qg._strip_for_scan(CBRACE_SOURCE_WITH_LITERALS, "cbrace"),
-            CBRACE_SOURCE_WITH_LITERALS)
+    def test_a_brace_language_line_shape_survives_the_mask(self):
+        masked = qg._strip_for_scan(CBRACE_SOURCE_WITH_LITERALS, "js")
+        raw_rows = CBRACE_SOURCE_WITH_LITERALS.split("\n")
+        masked_rows = masked.split("\n")
+        raw_widths = [len(r) for r in raw_rows]
+        masked_widths = [len(r) for r in masked_rows]
+        self.assertEqual(len(masked_rows), len(raw_rows))
+        self.assertEqual(masked_widths, raw_widths)
+
+    def test_an_unknown_language_is_returned_byte_for_byte(self):
+        got = qg._strip_for_scan(CBRACE_SOURCE_WITH_LITERALS, "ruby")
+        self.assertEqual(got, CBRACE_SOURCE_WITH_LITERALS)
 
     def test_line_count_and_line_lengths_survive_the_mask(self):
         masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
         raw_rows = LITERAL_HEAVY_SOURCE.split("\n")
         masked_rows = masked.split("\n")
@@ -512,10 +584,183 @@ class TestMaskFailsTowardRaw(unittest.TestCase):
 
     def test_an_all_blank_file_is_not_treated_as_corruption(self):
         self.assertFalse(qg._mask_lost_too_much(["", "  "], ["", "  "]))
 
 
+class TestCbraceMaskFill(unittest.TestCase):
+    """What the brace-language fill is allowed to change, character by
+    character."""
+
+    def test_braces_and_newlines_survive_inside_a_literal(self):
+        masked = qg._mask_cbrace_literals("x = '{a}'\n")
+        self.assertEqual(masked.count("{"), 1)
+        self.assertEqual(masked.count("}"), 1)
+        self.assertEqual(masked.count("\n"), 1)
+        self.assertEqual(len(masked), len("x = '{a}'\n"))
+
+    def test_literal_content_becomes_the_shared_sentinel(self):
+        masked = qg._mask_cbrace_literals("x = 'ab'\n")
+        self.assertEqual(masked, "x = " + qg._SCAN_SENTINEL * 4 + "\n")
+
+    def test_code_outside_a_literal_is_byte_for_byte(self):
+        masked = qg._mask_cbrace_literals("const a = b;\n")
+        self.assertEqual(masked, "const a = b;\n")
+
+    def test_an_unterminated_construct_yields_none(self):
+        self.assertIsNone(
+            qg._mask_cbrace_literals(CBRACE_UNTERMINATED_SOURCE))
+
+    def test_the_corruption_guard_inside_the_cbrace_mask_falls_back(self):
+        # The guard AS WRITTEN inside _mask_cbrace_literals. Masking never
+        # empties a line (the sentinel is non-whitespace), so the signal is
+        # forced rather than constructed from real source -- the same
+        # technique the python mask's guard test uses.
+        with mock.patch.object(qg, "_mask_lost_too_much", return_value=True):
+            self.assertIsNone(qg._mask_cbrace_literals("x = 1;\n"))
+
+    def test_an_unterminated_brace_source_still_yields_raw_counts(self):
+        masked = qg._strip_for_scan(CBRACE_UNTERMINATED_SOURCE, "js")
+        self.assertEqual(masked, CBRACE_UNTERMINATED_SOURCE)
+
+    def test_a_star_slash_inside_a_regex_literal_does_not_open_a_phantom_comment(self):
+        # A stepped-over slash inside a character class, followed by a `*`,
+        # forms a star-slash sequence that would otherwise open a
+        # block-comment span reaching all the way to the next real block
+        # comment much later in the source, silently dropping the branches
+        # of every line in between. The scan is required to refuse this
+        # opener and fall back to raw text instead.
+        source = (
+            "const re = /[/*]/;\n"
+            "function f(a){ ternary(a, a) ; }\n"
+            "/* real comment */\n"
+            "function g(b){ ternary(b, 1) ; }\n"
+        )
+        self.assertIsNone(qg._mask_cbrace_literals(source))
+        self.assertEqual(qg._strip_for_scan(source, "js"), source)
+
+    def test_an_ordinary_multiline_block_comment_still_masks(self):
+        source = "/* line one\nline two */\nconst a = b;\n"
+        masked = qg._mask_cbrace_literals(source)
+        self.assertIsNotNone(masked)
+        self.assertEqual(masked.count("\n"), source.count("\n"))
+        self.assertNotIn("line", masked)
+        self.assertIn("const a = b;", masked)
+
+
+class TestScanLangForPath(unittest.TestCase):
+    """Which extensions the scan mask is allowed to lex. The hand scanner
+    implements JS/TypeScript quoting rules alone, so every other brace
+    extension has to stay on raw text -- today's over-count, the safe
+    direction."""
+
+    def test_the_js_family_extensions_are_masked(self):
+        self.assertEqual(qg._scan_lang_for("a.js"), "js")
+        self.assertEqual(qg._scan_lang_for("a.mjs"), "js")
+        self.assertEqual(qg._scan_lang_for("a.cjs"), "js")
+        self.assertEqual(qg._scan_lang_for("a.jsx"), "js")
+        self.assertEqual(qg._scan_lang_for("a.ts"), "js")
+        self.assertEqual(qg._scan_lang_for("a.TSX"), "js")
+
+    def test_a_python_path_keeps_the_python_mask(self):
+        self.assertEqual(qg._scan_lang_for("a.py"), "python")
+
+    def test_the_other_brace_extensions_are_left_on_raw_text(self):
+        self.assertIsNone(qg._scan_lang_for("a.rs"))
+        self.assertIsNone(qg._scan_lang_for("a.c"))
+        self.assertIsNone(qg._scan_lang_for("a.h"))
+        self.assertIsNone(qg._scan_lang_for("a.cpp"))
+        self.assertIsNone(qg._scan_lang_for("a.cc"))
+        self.assertIsNone(qg._scan_lang_for("a.hpp"))
+        self.assertIsNone(qg._scan_lang_for("a.go"))
+        self.assertIsNone(qg._scan_lang_for("a.java"))
+        self.assertIsNone(qg._scan_lang_for("a.cs"))
+        self.assertEqual(qg._lang_for("a.rs"), "cbrace")
+
+    def test_an_unknown_extension_is_left_on_raw_text(self):
+        self.assertIsNone(qg._scan_lang_for("a.rb"))
+
+    def test_a_rust_lifetime_pair_keeps_both_branches(self):
+        # The defect this routing prevents, measured on the real callables:
+        # lexed with JS rules the two lifetimes pair into a phantom string
+        # over the boolean operator between them, dropping 2 branches to 1.
+        self.assertEqual(qg._branch_count(RUST_LIFETIME_LINE), 2)
+        self.assertEqual(
+            qg._branch_count(qg._mask_cbrace_literals(RUST_LIFETIME_LINE)), 1)
+        scanned = qg._strip_for_scan(
+            RUST_LIFETIME_LINE, qg._scan_lang_for("lib.rs"))
+        self.assertEqual(scanned, RUST_LIFETIME_LINE)
+        self.assertEqual(qg._branch_count(scanned), 2)
+
+    def test_a_cplusplus_digit_separator_pair_keeps_both_branches(self):
+        self.assertEqual(qg._branch_count(CPP_DIGIT_SEPARATOR_LINE), 2)
+        self.assertEqual(
+            qg._branch_count(
+                qg._mask_cbrace_literals(CPP_DIGIT_SEPARATOR_LINE)), 1)
+        scanned = qg._strip_for_scan(
+            CPP_DIGIT_SEPARATOR_LINE, qg._scan_lang_for("a.cpp"))
+        self.assertEqual(scanned, CPP_DIGIT_SEPARATOR_LINE)
+        self.assertEqual(qg._branch_count(scanned), 2)
+
+    def test_analyze_builtin_keeps_both_branches_in_a_cplusplus_file(self):
+        # The end-to-end pin: this drives the routing through the product
+        # entry point, so a mis-wired analyze_builtin fails here rather than
+        # passing on hand-composed calls. Measured before the routing landed,
+        # this reported 1; the raw line has 2.
+        findings, _ = qg.analyze_builtin(
+            "a.cpp", CPP_DIGIT_SEPARATOR_FUNCTION, [(1, 1)])
+        self.assertEqual(len(findings), 1)
+        self.assertEqual(
+            findings[0]["metrics"]["cyclomatic_complexity"], 2)
+
+    def test_the_extraction_family_name_is_no_longer_a_mask_language(self):
+        # "cbrace" still selects the brace extraction model, so it must NOT
+        # double as a mask language: handed to the mask it returns raw text.
+        self.assertEqual(
+            qg._strip_for_scan(CBRACE_SOURCE_WITH_LITERALS, "cbrace"),
+            CBRACE_SOURCE_WITH_LITERALS)
+
+
+class TestRegexQuotePhantom(unittest.TestCase):
+    """The regex-versus-quote residual as the code actually behaves, measured
+    through the real callable. Two documented safety claims were falsified
+    here: the mask succeeds on an odd quote count, and the phantom it opens
+    can reach past the end of its own line."""
+
+    def test_an_odd_quote_count_does_not_force_the_fallback(self):
+        # Three quote characters on line one, mask still succeeds.
+        self.assertIsNotNone(
+            qg._mask_cbrace_literals(REGEX_QUOTE_PHANTOM_SOURCE))
+
+    def test_the_phantom_hides_one_real_boolean_operator(self):
+        first_raw = REGEX_QUOTE_PHANTOM_SOURCE.split("\n")[0]
+        masked = qg._mask_cbrace_literals(REGEX_QUOTE_PHANTOM_SOURCE)
+        first_masked = masked.split("\n")[0]
+        self.assertEqual(qg._branch_count(first_raw), 2)
+        self.assertEqual(qg._branch_count(first_masked), 1)
+
+    def test_a_plain_phantom_does_not_reach_the_next_line(self):
+        # Narrow by design: this pins ONE spot-checked shape, the one with no
+        # backslash before the newline. It is NOT a general boundary claim --
+        # the multiline test below pins the shape that crosses.
+        masked = qg._mask_cbrace_literals(REGEX_QUOTE_PHANTOM_SOURCE)
+        rows = masked.split("\n")
+        raw_rows = REGEX_QUOTE_PHANTOM_SOURCE.split("\n")
+        self.assertEqual(rows[1], raw_rows[1])
+
+    def test_a_trailing_backslash_carries_the_phantom_past_the_newline(self):
+        # The falsified line-boundedness claim, pinned: the mask succeeds and
+        # the hidden boolean operator sits on the SECOND line.
+        masked = qg._mask_cbrace_literals(REGEX_QUOTE_PHANTOM_MULTILINE)
+        self.assertIsNotNone(masked)
+        self.assertEqual(qg._branch_count(REGEX_QUOTE_PHANTOM_MULTILINE), 2)
+        self.assertEqual(qg._branch_count(masked), 1)
+        rows = masked.split("\n")
+        raw_rows = REGEX_QUOTE_PHANTOM_MULTILINE.split("\n")
+        self.assertNotEqual(rows[1], raw_rows[1])
+        self.assertEqual(rows[2], raw_rows[2])
+
+
 class TestScanTokensFallbackPaths(unittest.TestCase):
     """_scan_tokens's two guards send the whole mask back to raw text, but
     stdlib tokenize never produces either shape for real source, so each is
     driven directly through the real callable with a patched tokenizer."""
 
@@ -543,10 +788,86 @@ class TestScanLinesForFallback(unittest.TestCase):
         lines = source.splitlines()
         with mock.patch.object(qg, "_strip_for_scan", longer_scan):
             self.assertEqual(qg._scan_lines_for(source, "python", lines), lines)
 
 
+class TestCbraceSpanScanner(unittest.TestCase):
+    """The span scanner is what decides which characters the brace-language
+    mask is allowed to blank. Every case is driven through the real
+    callables."""
+
+    def spans(self, text):
+        return qg._cbrace_spans(text, 0, len(text))
+
+    def covered(self, text):
+        """The concatenated text of every span the scanner reported."""
+        return "".join(text[a:b] for a, b in self.spans(text))
+
+    def test_a_line_comment_is_one_span_to_the_newline(self):
+        text = "a = 1 // note\nb = 2\n"
+        self.assertEqual(self.covered(text), "// note")
+
+    def test_a_block_comment_span_crosses_lines(self):
+        text = "a\n/* one\ntwo */\nb\n"
+        self.assertEqual(self.covered(text), "/* one\ntwo */")
+
+    def test_both_quote_flavours_are_spans_including_delimiters(self):
+        text = "x = 'a' + \"b\"\n"
+        self.assertEqual(self.covered(text), "'a'\"b\"")
+
+    def test_an_escaped_quote_does_not_close_a_string(self):
+        text = "x = 'a\\'b' + 1\n"
+        self.assertEqual(self.covered(text), "'a\\'b'")
+
+    def test_an_apostrophe_inside_a_comment_opens_nothing(self):
+        text = "// it doesn't\nif (a) { b() }\n"
+        self.assertEqual(self.covered(text), "// it doesn't")
+
+    def test_template_interpolation_code_is_not_covered(self):
+        text = "x = `m ${a && b} t`\n"
+        covered = self.covered(text)
+        self.assertIn("m ", covered)
+        self.assertNotIn("&&", covered)
+
+    def test_a_string_inside_an_interpolation_is_covered(self):
+        text = "x = `m ${f('q')} t`\n"
+        covered = self.covered(text)
+        self.assertIn("'q'", covered)
+        self.assertNotIn("f(", covered)
+
+    def test_a_brace_inside_an_interpolated_string_does_not_close_it(self):
+        text = "x = `m ${f('}')} t`\n"
+        covered = self.covered(text)
+        self.assertIn("'}'", covered)
+        self.assertNotIn("f(", covered)
+
+    def test_an_escaped_backtick_does_not_close_a_template(self):
+        # Drives the escape hop inside _cb_template_hop: the whole literal,
+        # escaped delimiter included, comes back as one span.
+        text = "x = `m \\` t` + 1\n"
+        self.assertEqual(self.covered(text), "`m \\` t`")
+
+    def test_a_lone_slash_is_stepped_over_as_division(self):
+        text = "x = a / b\n"
+        self.assertEqual(self.spans(text), [])
+
+    def test_an_unterminated_string_fails_toward_raw(self):
+        self.assertIsNone(self.spans("x = 'open\n"))
+
+    def test_an_unterminated_block_comment_fails_toward_raw(self):
+        self.assertIsNone(self.spans("x = 1 /* open\n"))
+
+    def test_an_unterminated_template_fails_toward_raw(self):
+        self.assertIsNone(self.spans("x = `open\n"))
+
+    def test_an_unterminated_interpolation_fails_toward_raw(self):
+        self.assertIsNone(self.spans("x = `m ${a\n"))
+
+    def test_an_unterminated_string_inside_an_interpolation_fails(self):
+        self.assertIsNone(self.spans("x = `m ${f('open} t`\n"))
+
+
 # --------------------------------------------------------------------------
 # Builtin heuristic extraction
 # --------------------------------------------------------------------------
 
 class TestAnalyzeBuiltinPython(unittest.TestCase):
@@ -648,14 +969,25 @@ class TestAnalyzeBuiltinMasksLiterals(unittest.TestCase):
         self.assertEqual((probe["line_start"], probe["line_end"]), (1, 6))
         self.assertEqual(probe["metrics"]["method_lines"], 6)
         self.assertEqual(probe["metrics"]["nesting_depth"], 2)
         self.assertEqual(probe["metrics"]["parameter_count"], 2)
 
-    def test_a_brace_language_keeps_todays_counts(self):
+    def test_a_brace_language_literal_stops_being_counted(self):
         outer = self.measure(CBRACE_SOURCE_WITH_LITERALS, "m.js")["outer"]
-        raw = self.measure_unmasked(CBRACE_SOURCE_WITH_LITERALS, "m.js")
-        self.assertEqual(outer["metrics"], raw["outer"]["metrics"])
+        raw = self.measure_unmasked(
+            CBRACE_SOURCE_WITH_LITERALS, "m.js")["outer"]
+        got = outer["metrics"]
+        was = raw["metrics"]
+        # The fixture's literal carries six fake branches; the one real
+        # branch is the ternary on the return line.
+        self.assertLess(
+            got["cyclomatic_complexity"], was["cyclomatic_complexity"])
+        self.assertEqual(got["cyclomatic_complexity"], 2)
+        self.assertEqual(got["nesting_depth"], was["nesting_depth"])
+        self.assertEqual(got["method_lines"], was["method_lines"])
+        self.assertEqual(outer["line_start"], raw["line_start"])
+        self.assertEqual(outer["line_end"], raw["line_end"])
 
     def test_an_untokenizable_python_file_still_yields_raw_counts(self):
         broken = "def probe(a):\n    return a  # " + BRANCH_WORDS_IN_LITERALS \
                  + "\n    x = '''open\n"
         findings, _ = qg.analyze_builtin(
@@ -678,10 +1010,77 @@ class TestAnalyzeBuiltinMasksLiterals(unittest.TestCase):
         self.assertEqual(
             masked["metrics"]["cognitive_complexity"],
             raw["metrics"]["cognitive_complexity"])
 
 
+class TestCbraceMaskedMetrics(unittest.TestCase):
+    """The three constructs the brace-language mask must get right, measured
+    end to end through analyze_builtin."""
+
+    def measure(self, source, path):
+        findings, _ = qg.analyze_builtin(
+            path, source, [(1, len(source.splitlines()))])
+        return {f["function"]: f for f in findings}
+
+    def measure_unmasked(self, source, path):
+        with mock.patch.object(qg, "_strip_for_scan", unmasked):
+            return self.measure(source, path)
+
+    def test_real_operators_inside_an_interpolation_are_still_counted(self):
+        masked = self.measure(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
+        # The real branches: the two operators inside ${...} and the one
+        # branch keyword. Base path plus three.
+        self.assertEqual(masked["metrics"]["cyclomatic_complexity"], 4)
+
+    def test_the_template_and_comment_text_is_not_counted(self):
+        masked = self.measure(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
+        raw = self.measure_unmasked(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
+        got = masked["metrics"]
+        was = raw["metrics"]
+        self.assertLess(
+            got["cyclomatic_complexity"], was["cyclomatic_complexity"])
+        self.assertLess(
+            got["cognitive_complexity"], was["cognitive_complexity"])
+
+    def test_the_shape_metrics_and_the_span_are_untouched(self):
+        masked = self.measure(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
+        raw = self.measure_unmasked(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
+        got = masked["metrics"]
+        was = raw["metrics"]
+        self.assertEqual(got["nesting_depth"], was["nesting_depth"])
+        self.assertEqual(got["method_lines"], was["method_lines"])
+        self.assertEqual(got["parameter_count"], was["parameter_count"])
+        self.assertEqual(masked["line_start"], raw["line_start"])
+        self.assertEqual(masked["line_end"], raw["line_end"])
+
+    def test_an_apostrophe_in_a_comment_does_not_blank_the_code(self):
+        # A strings-only scanner opens at the first comment's apostrophe a
+        # literal it can never close, since the quote alternatives exclude
+        # the newline, so the whole file loses its mask and reverts to
+        # today's over-count. Both real branches must survive AND the mask
+        # must succeed -- the assertIsNotNone is what makes this test bite
+        # on a strings-only scanner, because the equalities below hold
+        # either way once the mask falls back to raw text.
+        source = CBRACE_APOSTROPHE_COMMENTS_SOURCE
+        self.assertIsNotNone(qg._mask_cbrace_literals(source))
+        masked = self.measure(source, "m.js")["probe"]
+        raw = self.measure_unmasked(source, "m.js")["probe"]
+        got = masked["metrics"]
+        was = raw["metrics"]
+        self.assertEqual(
+            got["cyclomatic_complexity"], was["cyclomatic_complexity"])
+        self.assertEqual(
+            got["cognitive_complexity"], was["cognitive_complexity"])
+
+    def test_the_mjs_extension_takes_the_same_path(self):
+        masked = self.measure(CBRACE_TEMPLATE_SOURCE, "m.mjs")["probe"]
+        raw = self.measure_unmasked(CBRACE_TEMPLATE_SOURCE, "m.mjs")["probe"]
+        self.assertLess(
+            masked["metrics"]["cyclomatic_complexity"],
+            raw["metrics"]["cyclomatic_complexity"])
+
+
 class TestMatchBraceEnd(unittest.TestCase):
     def test_balances_nested_braces(self):
         lines = ["f() {", "  { }", "}"]
         self.assertEqual(qg._match_brace_end(lines, 0), 2)
 
@@ -1158,10 +1557,100 @@ def scanned_sources():
         if path.suffix in SCANNED_SUFFIXES and path.is_file():
             found.append(path)
     return found
 
 
+WORKFLOW_JS = PLUGIN_ROOT / "workflows" / "slice-wave.workflow.js"
+
+
+class TestCbraceMaskOverTheRealWorkflow(unittest.TestCase):
+    """The brace-language mask measured against the file that motivated it:
+    directions plus a floor under each masked value, so a regression that
+    masked MORE than it should also fails."""
+
+    @classmethod
+    def setUpClass(cls):
+        cls.source = WORKFLOW_JS.read_text(encoding="utf-8")
+
+    def analyze(self, source):
+        findings, _ = qg.analyze_builtin(
+            str(WORKFLOW_JS), source, [(1, len(source.splitlines()))])
+        return {f["function"]: f for f in findings}
+
+    def analyze_unmasked(self, source):
+        with mock.patch.object(qg, "_strip_for_scan", unmasked):
+            return self.analyze(source)
+
+    def check_comes_down(self, name, new, old, floor):
+        """One function's masked-versus-raw move: cognitive strictly down but
+        no lower than the value measured as this pin landed, and cyclomatic
+        never up. The floor is the upper bound on how much may be masked."""
+        got = new[name]["metrics"]
+        was = old[name]["metrics"]
+        self.assertLess(
+            got["cognitive_complexity"], was["cognitive_complexity"])
+        self.assertGreaterEqual(got["cognitive_complexity"], floor)
+        self.assertLessEqual(
+            got["cyclomatic_complexity"], was["cyclomatic_complexity"])
+
+    def check_masks_cleanly(self, path):
+        text = path.read_text(encoding="utf-8")
+        self.assertIsNotNone(
+            qg._mask_cbrace_literals(text), msg=str(path))
+
+    def test_the_mask_does_not_blank_the_file(self):
+        # The guard against the failure mode a strings-only scanner produces
+        # here: an apostrophe inside a line comment opens a literal that can
+        # never close, _mask_cbrace_literals returns None, and the whole file
+        # reverts to today's over-count. Function signatures live in code,
+        # never inside a literal, so a working mask must also yield the
+        # identical function list.
+        masked = qg._mask_cbrace_literals(self.source)
+        self.assertIsNotNone(masked)
+        raw_funcs = qg._extract_functions_cbrace(self.source.splitlines())
+        masked_funcs = qg._extract_functions_cbrace(masked.splitlines())
+        self.assertEqual(masked_funcs, raw_funcs)
+        self.assertGreater(len(raw_funcs), 60)
+
+    def test_the_three_motivating_functions_all_come_down(self):
+        new = self.analyze(self.source)
+        old = self.analyze_unmasked(self.source)
+        self.check_comes_down("globToRe", new, old, 17)
+        self.check_comes_down("stageFixLoop", new, old, 13)
+        self.check_comes_down("runSliceError", new, old, 12)
+
+    def test_stage_fix_loop_gains_real_headroom(self):
+        # It measures cognitive EXACTLY at the threshold before the mask and
+        # passes only because the check is value <= threshold, so it is the
+        # live instance this change rescues.
+        limit = qg.DEFAULT_THRESHOLDS["cognitive_complexity"]
+        old = self.analyze_unmasked(self.source)["stageFixLoop"]
+        new = self.analyze(self.source)["stageFixLoop"]
+        self.assertEqual(old["metrics"]["cognitive_complexity"], limit)
+        self.assertLess(new["metrics"]["cognitive_complexity"], limit)
+
+    def test_the_mask_does_not_rescue_glob_to_re(self):
+        # Honest limit, pinned: the miscount inflates globToRe, it does not
+        # create the violation. The function is genuinely over threshold
+        # before and after.
+        limit = qg.DEFAULT_THRESHOLDS["cognitive_complexity"]
+        new = self.analyze(self.source)["globToRe"]
+        self.assertGreater(new["metrics"]["cognitive_complexity"], limit)
+
+    def test_the_mask_succeeds_on_every_brace_source_in_the_tree(self):
+        # Named for what it proves and no more: the mask closes every
+        # construct it recognises in every brace source here, so no file
+        # silently falls back to raw counts. It is NOT a proof about regex
+        # literals -- a regex holding an even number of quotes masks cleanly
+        # and this still passes. The regex residual is backed by the pasted
+        # grep in the slice report instead.
+        brace = [p for p in scanned_sources() if p.suffix != ".py"]
+        self.assertGreater(len(brace), 0)
+        for path in brace:
+            self.check_masks_cleanly(path)
+
+
 class TestDifferentialAgainstRawScan(unittest.TestCase):
     """The mask may only ever LOWER a complexity count, and it may never move a
     function's span, its nesting depth, its length or its parameter count.
     Measured over the plugin tree's own source, masked against raw."""
 
@@ -1220,8 +1709,19 @@ class TestDifferentialAgainstRawScan(unittest.TestCase):
         # the mask actually moves numbers somewhere in the tree.
         moved = [where for where, got, was in self.measure_tree()
                  if got["metrics"] != was["metrics"]]
         self.assertGreater(len(moved), 100)
 
+    def test_a_brace_language_file_is_measurably_lowered(self):
+        # The tree-wide "something moved" test above would pass on a mask
+        # that only ever touched python, so pin the brace-language half
+        # separately.
+        moved = []
+        for where, got, was in self.measure_tree():
+            brace = (".js " in where) or (".mjs " in where)
+            if brace and got["metrics"] != was["metrics"]:
+                moved.append(where)
+        self.assertGreater(len(moved), 10)
+
 
 if __name__ == "__main__":
     unittest.main()
