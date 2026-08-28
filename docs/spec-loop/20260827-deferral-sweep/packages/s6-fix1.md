# Review package: 0c0495c..1461cd9  (context: -U5)

## Commits
1461cd9 fix(quality-gate): stop the brace mask from silently under-counting JSX and backtick-in-regex sources

## Files changed
 plugins/spec-loop/scripts/quality_gate.py      | 63 ++++++++++++++++-------
 plugins/spec-loop/scripts/test_quality_gate.py | 69 +++++++++++++++++++++++++-
 2 files changed, 111 insertions(+), 21 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/quality_gate.py": [
[
101,
115
],
[
117,
117
],
[
474,
476
],
[
478,
480
],
[
594,
594
],
[
620,
632
],
[
674,
679
],
[
684,
685
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
148,
171
],
[
672,
690
],
[
701,
701
],
[
702,
702
],
[
719,
728
],
[
765,
778
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index a7d9217..002c5af 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -96,20 +96,27 @@ _EXT_LANG = {
     ".c": "cbrace", ".h": "cbrace", ".cpp": "cbrace", ".cc": "cbrace",
     ".hpp": "cbrace", ".rs": "cbrace",
 }
 
 # The subset of the brace extensions whose scan mask may be lexed by the hand
-# scanner below. It implements JS/TypeScript quoting rules alone, where a single
-# quote always opens a string. In Rust a single quote usually opens a lifetime,
-# in C++ it also serves as a digit separator, so two of them on one line pair
-# into a phantom string covering the real code between them -- measured, that
-# turns 2 branches into 1 with no signal, the one direction this mask is never
-# allowed to move a count. Rust, C, C++, Go, Java and C# therefore keep their
-# raw text: they stay on today's over-count, which is the safe direction,
-# rather than being lexed by quoting rules that are not theirs.
+# scanner below. It implements plain JS/TypeScript quoting rules alone, where
+# a single quote always opens a string. In Rust a single quote usually opens
+# a lifetime, in C++ it also serves as a digit separator, so two of them on
+# one line pair into a phantom string covering the real code between them --
+# measured, that turns 2 branches into 1 with no signal, the one direction
+# this mask is never allowed to move a count. Rust, C, C++, Go, Java and C#
+# therefore keep their raw text: they stay on today's over-count, which is
+# the safe direction, rather than being lexed by quoting rules that are not
+# theirs. JSX and TSX carry the same residual for a different reason: the
+# scanner has no model of a JSX text node, where an apostrophe is prose, not
+# a string opener, so two contractions on one JSX text line pair into a
+# phantom string over real code between them -- measured on
+# `function Row(p) { return (<p>It's {p.a && p.b} - don't worry</p>); }`,
+# cyclomatic_complexity 1 where the raw branch count is 2. `.jsx` and `.tsx`
+# therefore also stay on raw text.
 _JS_MASK_EXTS = frozenset(
-    {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"})
+    {".js", ".mjs", ".cjs", ".ts"})
 
 # Branch keywords whose occurrence adds one to cyclomatic complexity. Matched as
 # whole words (or operators) so an identifier like `ifield` is not counted.
 _BRANCH_WORDS = ("if", "elif", "case", "catch", "for", "while", "when")
 _BRANCH_WORD_RE = re.compile(r"\b(?:%s)\b" % "|".join(_BRANCH_WORDS))
@@ -462,15 +469,17 @@ def _count_params(sig):
 # indent-derived end of the enclosing function. Masked spans are filled with a
 # non-whitespace sentinel rather than spaces, because _cognitive_approx derives
 # its nesting level from leading whitespace: space-fill would RAISE the measured
 # cognitive complexity of dozens of functions. Every failure path returns the
 # raw text, so the worst case remains today's over-count. Two maskers sit
-# behind this seam: python via stdlib tokenize, the JS/TypeScript family
-# (.js, .jsx, .mjs, .cjs, .ts, .tsx) via the hand scanner below. The remaining
-# brace extensions -- .rs, .c, .h, .cpp, .cc, .hpp, .go, .java, .cs -- are
+# behind this seam: python via stdlib tokenize, the plain JS/TypeScript family
+# (.js, .mjs, .cjs, .ts) via the hand scanner below. The remaining brace
+# extensions -- .rs, .c, .h, .cpp, .cc, .hpp, .go, .java, .cs -- are
 # deliberately NOT masked, because the hand scanner lexes JS quoting rules
-# alone. _scan_lang_for holds that routing.
+# alone. .jsx and .tsx are ALSO deliberately NOT masked, because the scanner
+# has no model of a JSX text node and an apostrophe inside one is prose, not
+# a string opener. _scan_lang_for holds that routing.
 
 _SCAN_SENTINEL = "x"
 
 # The corruption trip-wire, expressed as a denominator: a mask that leaves more
 # than one line in _MASK_LOST_DENOM of the non-blank lines with no content at
@@ -580,11 +589,11 @@ def _mask_python_literals(text):
 # deletes genuine operators and UNDER-counts a function, the dangerous
 # direction. The scanner stops short of one construct on purpose: a regex
 # literal. Telling a regex literal from a division operator needs the
 # parser's expectation of the next token, which a character scanner does not
 # have, so a lone slash outside a comment is stepped over and a regex
-# literal's interior stays visible. Three residuals follow from that. First,
+# literal's interior stays visible. Four residuals follow from that. First,
 # a quote character inside a regex literal opens a phantom string, and that
 # phantom can cover real operator punctuation lying between it and a later
 # quote, which lowers a count silently. Two limits a reader might expect are
 # NOT there, both measured against _mask_cbrace_literals and pinned by
 # TestRegexQuotePhantom. An odd number of quote characters on the line does
@@ -606,14 +615,23 @@ def _mask_python_literals(text):
 # with the next real block comment anywhere later in the source and blank
 # every line between the two.
 # The scanner guards against this one directly: once a bare slash has been
 # stepped over on the current source line, a later star-slash sequence on
 # that same line is refused rather than treated as a comment opener, and the
-# whole scan fails toward raw text instead of silently under-counting. That
-# guard is verified by a dedicated test rather than a repo sweep, because a
-# sweep can only bound occurrences that already exist, not ones a later file
-# introduces. Measured at the time this landed, the sweep of regex-literal
+# whole scan fails toward raw text instead of silently under-counting. Fourth,
+# also unbounded: a backtick inside a regex literal's character contents
+# reads as a template-literal opener, and the template alternative's closing
+# search crosses newlines with no escape needed, so it would otherwise pair
+# with the next real backtick anywhere later in the source and blank every
+# line between the two, exactly as the star-slash shape above does. The
+# scanner guards against this one the same way: once a bare slash has been
+# stepped over on the current source line, a later backtick on that same
+# line is refused rather than treated as a template-literal opener, and the
+# whole scan fails toward raw text instead. Both guards are verified by a
+# dedicated test rather than a repo sweep, because a sweep can only bound
+# occurrences that already exist, not ones a later file introduces. Measured
+# at the time this landed, the sweep of regex-literal
 # uses in this repo surfaced none containing a quote character, every
 # doubled slash the scanner treated as a line comment was a genuine trailing
 # comment after a properly closed regex literal, and the scanner closes every
 # construct it recognises in every brace source here. The sweeping greps
 # behind those statements are recorded in the slice report.
@@ -651,15 +669,22 @@ def _cb_flat_step(text, pos, stop, slash_since_newline):
 
 
 def _cb_step(text, pos, stop, slash_since_newline):
     """One scanner step from `pos`: (next_pos, mask_spans,
     slash_since_newline), else None to fail toward raw text. The
-    lone-slash memory resets at the newline that ends its line. (PURE)"""
+    lone-slash memory resets at the newline that ends its line. A backtick
+    reached after a lone slash on the same line is refused rather than
+    treated as a template-literal opener, mirroring the star-slash guard in
+    `_cb_flat_step`: its closing search would otherwise cross newlines and
+    pair with a real backtick far later in the file, blanking real code in
+    between; refusing sends the whole scan back to raw text instead. (PURE)"""
     ch = text[pos]
     if ch == "\n":
         return pos + 1, [], False
     if ch == "`":
+        if slash_since_newline:
+            return None
         got = _cb_template_step(text, pos, stop)
         if got is None:
             return None
         nxt, spans = got
         return nxt, spans, slash_since_newline
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index af1f146..4cab26d 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -143,10 +143,34 @@ REGEX_QUOTE_PHANTOM_MULTILINE = (
     "a = /'\\\n"
     "p && q'/ ;\n"
     "z = 1;\n"
 )
 
+# A JSX text node where an apostrophe is prose, not a string opener. The hand
+# scanner has no model of JSX text, so the two contractions on the text line
+# pair into a phantom string covering the real code between them, hiding the
+# genuine boolean operator. Measured raw-versus-masked branch counts are
+# pinned below.
+JSX_APOSTROPHE_FUNCTION = (
+    "function Row(p) {\n"
+    "  return (\n"
+    "    <p>It's {p.a && p.b} - don't worry</p>\n"
+    "  );\n"
+    "}\n"
+)
+
+# A backtick inside a regex literal's character contents. The template
+# alternative's closing search crosses newlines with no escape needed, so it
+# would otherwise pair with the next real backtick anywhere later in the
+# source and blank real code -- including a genuine boolean operator --
+# between the two.
+BACKTICK_REGEX_PHANTOM_SOURCE = (
+    "const open = /`/;\n"
+    "function f(a){ return a && a.x ? 1 : 2; }\n"
+    "const close = /`/;\n"
+)
+
 
 def unmasked(text, lang):
     """Identity stand-in for qg._strip_for_scan, so a test can measure the same
     source the way the gate measured it before the mask existed. Named at module
     level because a paren-aligned mock.patch.object continuation inside a test
@@ -643,10 +667,29 @@ class TestCbraceMaskFill(unittest.TestCase):
         self.assertIsNotNone(masked)
         self.assertEqual(masked.count("\n"), source.count("\n"))
         self.assertNotIn("line", masked)
         self.assertIn("const a = b;", masked)
 
+    def test_a_backtick_inside_a_regex_literal_does_not_open_a_phantom_template(self):
+        # A stepped-over slash on a source line, followed later by a
+        # backtick, would otherwise open a template-literal span reaching
+        # all the way to the next real backtick much later in the source,
+        # silently hiding the boolean operator on the line in between. The
+        # scan is required to refuse this opener and fall back to raw text.
+        self.assertIsNone(
+            qg._mask_cbrace_literals(BACKTICK_REGEX_PHANTOM_SOURCE))
+        self.assertEqual(
+            qg._strip_for_scan(BACKTICK_REGEX_PHANTOM_SOURCE, "js"),
+            BACKTICK_REGEX_PHANTOM_SOURCE)
+
+    def test_an_ordinary_template_literal_still_masks(self):
+        source = "const a = `line one\nline two`;\n"
+        masked = qg._mask_cbrace_literals(source)
+        self.assertIsNotNone(masked)
+        self.assertEqual(masked.count("\n"), source.count("\n"))
+        self.assertNotIn("line", masked)
+
 
 class TestScanLangForPath(unittest.TestCase):
     """Which extensions the scan mask is allowed to lex. The hand scanner
     implements JS/TypeScript quoting rules alone, so every other brace
     extension has to stay on raw text -- today's over-count, the safe
@@ -654,13 +697,11 @@ class TestScanLangForPath(unittest.TestCase):
 
     def test_the_js_family_extensions_are_masked(self):
         self.assertEqual(qg._scan_lang_for("a.js"), "js")
         self.assertEqual(qg._scan_lang_for("a.mjs"), "js")
         self.assertEqual(qg._scan_lang_for("a.cjs"), "js")
-        self.assertEqual(qg._scan_lang_for("a.jsx"), "js")
         self.assertEqual(qg._scan_lang_for("a.ts"), "js")
-        self.assertEqual(qg._scan_lang_for("a.TSX"), "js")
 
     def test_a_python_path_keeps_the_python_mask(self):
         self.assertEqual(qg._scan_lang_for("a.py"), "python")
 
     def test_the_other_brace_extensions_are_left_on_raw_text(self):
@@ -673,10 +714,20 @@ class TestScanLangForPath(unittest.TestCase):
         self.assertIsNone(qg._scan_lang_for("a.go"))
         self.assertIsNone(qg._scan_lang_for("a.java"))
         self.assertIsNone(qg._scan_lang_for("a.cs"))
         self.assertEqual(qg._lang_for("a.rs"), "cbrace")
 
+    def test_jsx_and_tsx_are_also_left_on_raw_text(self):
+        # The hand scanner has no model of a JSX text node, where an
+        # apostrophe is prose, not a string opener, so these two extensions
+        # stay on raw text for a different reason than the other brace
+        # languages above -- see test_a_jsx_apostrophe_pair_keeps_both_branches.
+        self.assertIsNone(qg._scan_lang_for("a.jsx"))
+        self.assertIsNone(qg._scan_lang_for("a.TSX"))
+        self.assertEqual(qg._lang_for("a.jsx"), "cbrace")
+        self.assertEqual(qg._lang_for("a.tsx"), "cbrace")
+
     def test_an_unknown_extension_is_left_on_raw_text(self):
         self.assertIsNone(qg._scan_lang_for("a.rb"))
 
     def test_a_rust_lifetime_pair_keeps_both_branches(self):
         # The defect this routing prevents, measured on the real callables:
@@ -709,10 +760,24 @@ class TestScanLangForPath(unittest.TestCase):
             "a.cpp", CPP_DIGIT_SEPARATOR_FUNCTION, [(1, 1)])
         self.assertEqual(len(findings), 1)
         self.assertEqual(
             findings[0]["metrics"]["cyclomatic_complexity"], 2)
 
+    def test_a_jsx_apostrophe_pair_keeps_both_branches(self):
+        # The defect this routing prevents, measured on the real callables:
+        # lexed with JS quoting rules the two contractions on the text line
+        # pair into a phantom string over the boolean operator between them,
+        # dropping 2 branches to 1.
+        findings, _ = qg.analyze_builtin(
+            "Row.jsx", JSX_APOSTROPHE_FUNCTION, [(1, 5)])
+        self.assertEqual(len(findings), 1)
+        self.assertEqual(
+            findings[0]["metrics"]["cyclomatic_complexity"], 2)
+        scanned = qg._strip_for_scan(
+            JSX_APOSTROPHE_FUNCTION, qg._scan_lang_for("Row.tsx"))
+        self.assertEqual(scanned, JSX_APOSTROPHE_FUNCTION)
+
     def test_the_extraction_family_name_is_no_longer_a_mask_language(self):
         # "cbrace" still selects the brace extraction model, so it must NOT
         # double as a mask language: handed to the mask it returns raw text.
         self.assertEqual(
             qg._strip_for_scan(CBRACE_SOURCE_WITH_LITERALS, "cbrace"),
