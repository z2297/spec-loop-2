#!/usr/bin/env python3
"""Tests for the objective code-quality gate (stdlib unittest).

Covers the PURE diff parser on embedded fixture text, config loading (defaults /
loaded / disabled / malformed), the pure metric primitives (parameter counting,
branch counting, nesting depth, CRAP, cognitive approximation), the scan mask
that hides string-literal and comment content from the two branch scans for
python and the JS/TypeScript family alike (including its extension routing, the
brace languages left deliberately unmasked, the measured regex-versus-quote
residuals, and every fall-back-to-raw path), a differential harness comparing
masked against raw measurement over every heuristic-readable file in the plugin
tree, the builtin heuristic function extraction for python and brace languages,
backend CSV/JSON
parsing and backend+heuristic merging with per-metric sourcing (cognitive is
NEVER attributed to a tool), coverage parsing (cobertura + lcov) and CRAP
assembly, custom-gate evaluation (metric-form evaluated here, command-form
deferred to the skill), threshold pass/fail + report shape, and main()'s exit
codes. Backends are exercised by mocking shutil.which / subprocess.run so the
suite passes whether or not lizard/radon are installed. Standard library only;
no live network. Real git is used only in a tiny throwaway repo for the
end-to-end path.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_quality_gate.py'
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tokenize
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quality_gate as qg  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures for the scan mask. These deliberately carry branch words and
# operator punctuation INSIDE literals and comments, so they live at module
# level: the gate measures function bodies, and a fixture like this one inside
# a test method would be counted as that method's own branching.
# --------------------------------------------------------------------------

BRANCH_WORDS_IN_LITERALS = "if for while ? && ||"

LITERAL_HEAVY_SOURCE = (
    "def probe(a, b):\n"
    '    """Prose mentioning ' + BRANCH_WORDS_IN_LITERALS + '."""\n'
    "    label = '" + BRANCH_WORDS_IN_LITERALS + "'  # "
    + BRANCH_WORDS_IN_LITERALS + "\n"
    "    " + "if" + " a:\n"
    "        return label\n"
    "    return b\n"
)

UNTERMINATED_SOURCE = "def h():\n    x = '''" + BRANCH_WORDS_IN_LITERALS + "\n"

CBRACE_SOURCE_WITH_LITERALS = (
    "function outer(a) {\n"
    "    const q = '" + BRANCH_WORDS_IN_LITERALS + "';\n"
    "    return a ? q : null;\n"
    "}\n"
)

# A multi-line string literal whose closing row also carries a real ternary
# after the literal ends. The literal's interior rows are indented to keep
# them inside the enclosing `if` block for extraction purposes.
MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE = (
    "def f(a, b):\n"
    "    " + "if" + " a:\n"
    "        s = '''\n"
    "        text\n"
    "        ''' " + "if" + " b " + "else" + " 'z'\n"
    "        return s\n"
    "    return b\n"
)

# A template literal whose interpolation carries REAL operators, plus a
# comment and a single-quoted string that carry fake ones. Module level, for
# the reason given above the python fixtures.
CBRACE_TEMPLATE_SOURCE = (
    "function probe(e) {\n"
    "    // a comment that isn't code: " + BRANCH_WORDS_IN_LITERALS + "\n"
    "    const s = `msg ${String((e && e.message) || e)} "
    + BRANCH_WORDS_IN_LITERALS + "`;\n"
    "    /* block " + BRANCH_WORDS_IN_LITERALS + " */\n"
    "    " + "if" + " (s) { return s; }\n"
    "    return '" + BRANCH_WORDS_IN_LITERALS + "';\n"
    "}\n"
)

CBRACE_UNTERMINATED_SOURCE = (
    "function probe(a) {\n"
    "    const s = 'never closed " + BRANCH_WORDS_IN_LITERALS + ";\n"
    "    return a;\n"
    "}\n"
)

CBRACE_APOSTROPHE_COMMENTS_SOURCE = (
    "function probe(a, b) {\n"
    "    // it doesn't matter\n"
    "    " + "if" + " (a) { return b; }\n"
    "    // and it isn't a literal\n"
    "    " + "for" + " (const x of b) { a += x; }\n"
    "    return a;\n"
    "}\n"
)

# Three shapes that a JS-quoting mask corrupts in a NON-JS brace language. In
# Rust a single quote opens a lifetime, in C++ it also serves as a digit
# separator, so two of them on one line pair into a phantom string spanning the
# real code between them. Measured raw-versus-masked branch counts are pinned
# below. The third fixture is the C++ shape wrapped in an extractable function,
# used to drive the routing through analyze_builtin end to end.
RUST_LIFETIME_LINE = (
    "fn f(a: &'x A, b: &'y B) -> bool { helper(&'x a) && other(&'y b) }\n")
CPP_DIGIT_SEPARATOR_LINE = "int x = 1'000 + (a ? b : c) + 2'000;\n"
CPP_DIGIT_SEPARATOR_FUNCTION = (
    "int f(int a) { int x = 1'000 + (a ? 2 : 3) + 2'000; return x; }\n")

# The measured counter-example to the claim that an odd number of quote
# characters on a line forces a whole-file fallback: the first two quotes sit
# inside single-character regex literals and pair into a phantom string over the
# real boolean operator, the third is swallowed by the trailing line comment, so
# the odd count never survives to end-of-line.
REGEX_QUOTE_PHANTOM_SOURCE = (
    "x = /'/.test(a) && /'/.test(b); // don't\n"
    "y = p && q;\n"
)

# The measured counter-example to the claim that such a phantom stays on its own
# line. _CB_FLAT_RE's escape alternative accepts a backslash followed by ANY
# character, the newline included, so a backslash in final position on the
# opening line carries the phantom forward and hides a real boolean operator on
# the NEXT line. Chaining that shape extends the phantom arbitrarily.
REGEX_QUOTE_PHANTOM_MULTILINE = (
    "a = /'\\\n"
    "p && q'/ ;\n"
    "z = 1;\n"
)

# A JSX text node where an apostrophe is prose, not a string opener. The hand
# scanner has no model of JSX text, so the two contractions on the text line
# pair into a phantom string covering the real code between them, hiding the
# genuine boolean operator. Measured raw-versus-masked branch counts are
# pinned below.
JSX_APOSTROPHE_FUNCTION = (
    "function Row(p) {\n"
    "  return (\n"
    "    <p>It's {p.a && p.b} - don't worry</p>\n"
    "  );\n"
    "}\n"
)

# A backtick inside a regex literal's character contents. The template
# alternative's closing search crosses newlines with no escape needed, so it
# would otherwise pair with the next real backtick anywhere later in the
# source and blank real code -- including a genuine boolean operator --
# between the two.
BACKTICK_REGEX_PHANTOM_SOURCE = (
    "const open = /`/;\n"
    "function f(a){ return a && a.x ? 1 : 2; }\n"
    "const close = /`/;\n"
)


def unmasked(text, lang):
    """Identity stand-in for qg._strip_for_scan, so a test can measure the same
    source the way the gate measured it before the mask existed. Named at module
    level because a paren-aligned mock.patch.object continuation inside a test
    body is itself read as nesting by the metric under test."""
    return text


NON_ENDMARKER_TAIL_TOKEN = tokenize.TokenInfo(
    tokenize.NEWLINE, "\n", (1, 0), (1, 1), "\n")


def empty_token_stream(readline):
    """Stand-in for tokenize.generate_tokens yielding no tokens at all. Named
    at module level for the same paren-alignment reason as `unmasked`."""
    return iter([])


def non_endmarker_token_stream(readline):
    """Stand-in for tokenize.generate_tokens whose last token is not
    ENDMARKER. Named at module level for the same paren-alignment reason as
    `unmasked`."""
    return iter([NON_ENDMARKER_TAIL_TOKEN])


def longer_scan(text, lang):
    """Stand-in for qg._strip_for_scan that returns one extra physical line,
    so the caller's line count no longer matches its input. Named at module
    level for the same paren-alignment reason as `unmasked`."""
    return text + "\nextra"


# refactor_radius config fixtures. A multi-line dict literal passed inline to
# a helper call forces a deep hanging indent when the continuation aligns with
# the opening brace, and the gate's nesting-depth heuristic reads that
# indentation as block nesting -- so these live at module level for the same
# reason as the fixtures above.
OVERLAY_SIBLINGS_BASE_RADIUS = {
    "refactor_radius": {
        "enabled": True,
        "max_rewrite_ratio": 0.4,
        "max_touched_existing_files": 6,
        "min_rewritten_lines": 120,
    },
}

OVERLAY_SIBLINGS_EXPECTED_RADIUS = {
    "enabled": True,
    "max_rewrite_ratio": 0.3,
    "max_touched_existing_files": 6,
    "min_rewritten_lines": 120,
}


# --------------------------------------------------------------------------
# parse_diff — pure, embedded fixtures
# --------------------------------------------------------------------------

class TestParseDiff(unittest.TestCase):
    def test_single_file_added_range(self):
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "index 111..222 100644\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,0 +2,3 @@\n"
            "+a\n+b\n+c\n"
        )
        self.assertEqual(qg.parse_diff(diff), {"foo.py": [(2, 4)]})

    def test_hunk_without_count_is_single_line(self):
        # `+5` with no ,count means exactly one added line at 5.
        diff = (
            "--- a/x.js\n"
            "+++ b/x.js\n"
            "@@ -5 +5 @@\n"
            "-old\n+new\n"
        )
        self.assertEqual(qg.parse_diff(diff), {"x.js": [(5, 5)]})

    def test_multiple_hunks_and_files(self):
        diff = (
            "--- a/a.py\n+++ b/a.py\n"
            "@@ -1,0 +1,2 @@\n+x\n+y\n"
            "@@ -10,0 +20,1 @@\n+z\n"
            "--- a/b.py\n+++ b/b.py\n"
            "@@ -1,0 +3,1 @@\n+q\n"
        )
        self.assertEqual(
            qg.parse_diff(diff),
            {"a.py": [(1, 2), (20, 20)], "b.py": [(3, 3)]})

    def test_deleted_file_is_skipped(self):
        # A file whose new path is /dev/null contributes no range.
        diff = (
            "--- a/gone.py\n"
            "+++ /dev/null\n"
            "@@ -1,3 +0,0 @@\n-a\n-b\n-c\n"
        )
        self.assertEqual(qg.parse_diff(diff), {})

    def test_pure_deletion_hunk_contributes_no_range(self):
        # `+0,0` (zero new lines) is a deletion within an otherwise-live file.
        diff = (
            "--- a/f.py\n+++ b/f.py\n"
            "@@ -5,2 +4,0 @@\n-a\n-b\n"
        )
        self.assertEqual(qg.parse_diff(diff), {})

    def test_b_prefix_stripped(self):
        diff = "--- a/dir/x.py\n+++ b/dir/x.py\n@@ -1 +1 @@\n-a\n+b\n"
        self.assertEqual(qg.parse_diff(diff), {"dir/x.py": [(1, 1)]})

    def test_empty_diff(self):
        self.assertEqual(qg.parse_diff(""), {})


class TestSpanHelpers(unittest.TestCase):
    def test_overlap_true_and_false(self):
        self.assertTrue(qg._spans_overlap(1, 5, 5, 9))
        self.assertTrue(qg._spans_overlap(3, 4, 1, 10))
        self.assertFalse(qg._spans_overlap(1, 5, 6, 9))

    def test_intersects_changed(self):
        self.assertTrue(qg._intersects_changed(10, 20, [(1, 2), (15, 16)]))
        self.assertFalse(qg._intersects_changed(10, 20, [(1, 2), (30, 40)]))


# --------------------------------------------------------------------------
# Config loading
# --------------------------------------------------------------------------

class TestLoadConfig(unittest.TestCase):
    def test_missing_path_uses_defaults(self):
        cfg, src = qg.load_config("/nonexistent/quality-gate.json")
        self.assertEqual(src, "defaults")
        self.assertEqual(cfg["thresholds"], qg.DEFAULT_THRESHOLDS)
        self.assertTrue(cfg["enabled"])

    def test_none_path_uses_defaults(self):
        cfg, src = qg.load_config(None)
        self.assertEqual(src, "defaults")

    def test_loaded_merges_partial_thresholds_over_defaults(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"enabled": True,
                       "thresholds": {"cyclomatic_complexity": 5},
                       "custom_gates": [{"name": "g", "metric": "x",
                                         "threshold": 1}]}, fh)
            path = fh.name
        self.addCleanup(os.unlink, path)
        cfg, src = qg.load_config(path)
        self.assertEqual(src, "loaded")
        self.assertEqual(cfg["thresholds"]["cyclomatic_complexity"], 5)
        # untouched keys keep their default value
        self.assertEqual(cfg["thresholds"]["method_lines"],
                         qg.DEFAULT_THRESHOLDS["method_lines"])
        self.assertEqual(len(cfg["custom_gates"]), 1)

    def test_disabled_flag_preserved(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"enabled": False}, fh)
            path = fh.name
        self.addCleanup(os.unlink, path)
        cfg, _ = qg.load_config(path)
        self.assertFalse(cfg["enabled"])

    def test_malformed_json_is_hard_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{not json")
            path = fh.name
        self.addCleanup(os.unlink, path)
        with self.assertRaises(qg.GateError):
            qg.load_config(path)

    def test_non_object_json_is_hard_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump([1, 2, 3], fh)
            path = fh.name
        self.addCleanup(os.unlink, path)
        with self.assertRaises(qg.GateError):
            qg.load_config(path)

    def test_defaults_carry_the_full_default_on_refactor_radius_block(self):
        cfg, src = qg.load_config(None)
        self.assertEqual(src, "defaults")
        self.assertEqual(cfg["refactor_radius"], qg.DEFAULT_REFACTOR_RADIUS)
        self.assertTrue(cfg["refactor_radius"]["enabled"])

    def test_a_partial_refactor_radius_block_keeps_its_unmentioned_sibling_keys(self):
        path = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.25}})
        cfg, _ = qg.load_config(path)
        radius = cfg["refactor_radius"]
        default = qg.DEFAULT_REFACTOR_RADIUS
        self.assertEqual(radius["max_rewrite_ratio"], 0.25)
        self.assertEqual(
            radius["max_touched_existing_files"],
            default["max_touched_existing_files"])
        self.assertEqual(
            radius["min_rewritten_lines"], default["min_rewritten_lines"])
        self.assertTrue(radius["enabled"])

    def test_a_refactor_radius_block_can_be_switched_off_by_the_operator(self):
        path = self._tmp_json({"refactor_radius": {"enabled": False}})
        cfg, _ = qg.load_config(path)
        radius = cfg["refactor_radius"]
        self.assertFalse(radius["enabled"])
        self.assertEqual(
            radius["max_rewrite_ratio"],
            qg.DEFAULT_REFACTOR_RADIUS["max_rewrite_ratio"])

    def test_a_non_object_refactor_radius_in_the_config_is_a_hard_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"refactor_radius": [0.5]}, fh)
            path = fh.name
        self.addCleanup(os.unlink, path)
        with self.assertRaises(qg.GateError) as ctx:
            qg.load_config(path)
        self.assertIn("refactor_radius", str(ctx.exception))

    def _tmp_json(self, obj):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(obj, fh)
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_overlay_merges_over_global(self):
        base = self._tmp_json({
            "thresholds": {"cyclomatic_complexity": 12, "method_lines": 60},
            "custom_gates": [{"name": "g1", "metric": "x", "threshold": 1}],
            "tier3_surfaces": ["**/auth/**"],
            "models": {"reviewer": "sonnet"},
        })
        overlay = self._tmp_json({
            "thresholds": {"cyclomatic_complexity": 8},
            "custom_gates": [{"name": "g2", "metric": "y", "threshold": 2}],
            "tier3_surfaces": ["**/migrations/**"],
            "models": {"reviewer": "inherit"},
        })
        cfg, src = qg.load_config(base, overlay)
        self.assertEqual(src, "loaded+overlay")
        self.assertEqual(cfg["thresholds"]["cyclomatic_complexity"], 8)   # overlay wins
        self.assertEqual(cfg["thresholds"]["method_lines"], 60)           # base survives
        self.assertEqual([g["name"] for g in cfg["custom_gates"]], ["g1", "g2"])
        self.assertEqual(cfg["tier3_surfaces"], ["**/auth/**", "**/migrations/**"])
        self.assertEqual(cfg["models"], {"reviewer": "inherit"})          # non-list keys override

    def test_overlay_over_missing_global_uses_defaults(self):
        overlay = self._tmp_json({"thresholds": {"nesting_depth": 2}})
        cfg, src = qg.load_config(None, overlay)
        self.assertEqual(src, "defaults+overlay")
        self.assertEqual(cfg["thresholds"]["nesting_depth"], 2)
        self.assertEqual(cfg["thresholds"]["cyclomatic_complexity"],
                         qg.DEFAULT_THRESHOLDS["cyclomatic_complexity"])

    def test_missing_overlay_path_is_ignored(self):
        base = self._tmp_json({"thresholds": {"method_lines": 40}})
        cfg, src = qg.load_config(base, "/nonexistent/.spec-loop/quality-gate.json")
        self.assertEqual(src, "loaded")
        self.assertEqual(cfg["thresholds"]["method_lines"], 40)

    def test_malformed_overlay_is_hard_error(self):
        base = self._tmp_json({})
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{not json")
        self.addCleanup(os.unlink, fh.name)
        with self.assertRaises(qg.GateError):
            qg.load_config(base, fh.name)

    def test_an_overlay_tuning_one_radius_number_does_not_drop_its_siblings(self):
        base = self._tmp_json(OVERLAY_SIBLINGS_BASE_RADIUS)
        overlay = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.3}})
        cfg, src = qg.load_config(base, overlay)
        self.assertEqual(src, "loaded+overlay")
        self.assertEqual(cfg["refactor_radius"], OVERLAY_SIBLINGS_EXPECTED_RADIUS)

    def test_an_overlay_radius_key_over_a_global_without_the_block_keeps_defaults(self):
        base = self._tmp_json({"thresholds": {"method_lines": 40}})
        overlay = self._tmp_json({"refactor_radius": {"max_touched_existing_files": 4}})
        cfg, _ = qg.load_config(base, overlay)
        radius = cfg["refactor_radius"]
        default = qg.DEFAULT_REFACTOR_RADIUS
        self.assertEqual(radius["max_touched_existing_files"], 4)
        self.assertEqual(radius["max_rewrite_ratio"], default["max_rewrite_ratio"])
        self.assertEqual(radius["min_rewritten_lines"], default["min_rewritten_lines"])

    def test_a_non_object_refactor_radius_in_the_overlay_is_a_hard_error(self):
        base = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.4}})
        overlay = self._tmp_json({"refactor_radius": 0.9})
        with self.assertRaises(qg.GateError) as ctx:
            qg.load_config(base, overlay)
        self.assertIn("refactor_radius", str(ctx.exception))

    def test_a_non_object_refactor_radius_in_the_base_is_a_hard_error_under_an_overlay(self):
        base = self._tmp_json({"refactor_radius": ["nope"]})
        overlay = self._tmp_json({"thresholds": {"method_lines": 40}})
        with self.assertRaises(qg.GateError):
            qg.load_config(base, overlay)

    def test_print_config_surfaces_the_merged_refactor_radius_block(self):
        base = self._tmp_json({"refactor_radius": {"max_touched_existing_files": 6}})
        overlay = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.3}})
        proc = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "quality_gate.py"),
             "--config", base, "--overlay", overlay, "--print-config"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["source"], "loaded+overlay")
        self.assertEqual(out["config"]["refactor_radius"], {
            "enabled": True,
            "max_rewrite_ratio": 0.3,
            "max_touched_existing_files": 6,
            "min_rewritten_lines": qg.DEFAULT_REFACTOR_RADIUS["min_rewritten_lines"],
        })

    def test_print_config_cli(self):
        base = self._tmp_json({"tier3_surfaces": ["**/auth/**"]})
        proc = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "quality_gate.py"),
             "--config", base, "--print-config"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["source"], "loaded")
        self.assertEqual(out["config"]["tier3_surfaces"], ["**/auth/**"])

    def test_base_required_without_print_config(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "quality_gate.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)


# --------------------------------------------------------------------------
# Command-doc single-home pin. commands/quality-gate.md is the ONE operator-
# facing home of the config schema; when it and the defaults disagree, one of
# them is wrong, and this catches the drift in the same suite that owns the
# defaults.
# --------------------------------------------------------------------------

COMMAND_DOC = (Path(__file__).resolve().parents[1] / "commands" / "quality-gate.md")


class TestCommandDocDocumentsRefactorRadius(unittest.TestCase):
    def setUp(self):
        self.doc = COMMAND_DOC.read_text(encoding="utf-8")

    def test_every_refactor_radius_key_is_named_in_the_command_doc(self):
        for key in qg.DEFAULT_REFACTOR_RADIUS:
            with self.subTest(key=key):
                self.assertIn(key, self.doc)

    def test_the_step_one_key_list_names_the_block(self):
        step_one = self.doc.split("2. **Choose a quality level**")[0]
        self.assertIn("refactor_radius", step_one)

    def test_the_written_schema_carries_the_shipped_default_numbers(self):
        schema = self.doc.split("```json")[1].split("```")[0]
        self.assertIn('"refactor_radius"', schema)
        for key, value in qg.DEFAULT_REFACTOR_RADIUS.items():
            with self.subTest(key=key):
                literal = {True: "true", False: "false"}.get(value, str(value))
                self.assertIn(f'"{key}": {literal}', schema)

    def test_the_doc_states_the_block_is_a_declared_proxy_not_a_measured_diff(self):
        self.assertIn("proxy", self.doc.lower())


# --------------------------------------------------------------------------
# Pure metric primitives
# --------------------------------------------------------------------------

class TestCountParams(unittest.TestCase):
    def test_zero_params(self):
        self.assertEqual(qg._count_params("def f():"), 0)

    def test_simple_params(self):
        self.assertEqual(qg._count_params("def f(a, b, c):"), 3)

    def test_drops_leading_self(self):
        self.assertEqual(qg._count_params("def m(self, a, b):"), 2)

    def test_drops_leading_cls(self):
        self.assertEqual(qg._count_params("def m(cls, a):"), 1)

    def test_nested_generics_not_split(self):
        # a comma inside Dict[str, int] must not inflate the count
        self.assertEqual(
            qg._count_params("def f(a: Dict[str, int], b: List[int]):"), 2)

    def test_no_parens_returns_zero(self):
        self.assertEqual(qg._count_params("x = 1"), 0)


class TestBranchCount(unittest.TestCase):
    def test_base_path_only(self):
        self.assertEqual(qg._branch_count("x = 1\nreturn x\n"), 1)

    def test_counts_keywords_and_operators(self):
        code = "if a and b:\n    for i in x:\n        while y or z:\n            pass"
        # base 1 + if + for + while + and(&&-equivalent via 'and'? no) ...
        # 'and'/'or' are words not counted by ops regex; && || ? are. Here:
        # if, for, while -> 3 branch words; no &&/||/? -> total 1+3 = 4
        self.assertEqual(qg._branch_count(code), 4)

    def test_counts_boolean_operators_and_ternary(self):
        code = "return a && b || (c ? d : e)"
        # base 1 + && + || + ? -> 4
        self.assertEqual(qg._branch_count(code), 4)

    def test_else_if_counts_once(self):
        code = "if a {} else if b {}"
        # base 1 + two `if` words (leading + the one inside `else if`); the
        # `else if` is NOT separately counted as an op -> 3, not 4.
        self.assertEqual(qg._branch_count(code), 3)

    def test_word_boundary_avoids_identifiers(self):
        # 'ifield' / 'forum' must not be counted as if/for
        self.assertEqual(qg._branch_count("ifield = forum + whilehouse\n"), 1)


class TestNesting(unittest.TestCase):
    def test_python_nesting_by_indent(self):
        lines = [
            "    if a:",           # base_indent 4, level 0
            "        if b:",       # level 1
            "            x = 1",   # level 2
        ]
        self.assertEqual(qg._nesting_depth_python(lines, 4), 2)

    def test_brace_nesting(self):
        # outer function brace is depth 1 (discounted); one nested block -> 1
        self.assertEqual(qg._nesting_depth_braces("{ if (x) { y; } }"), 1)

    def test_brace_nesting_two_levels(self):
        self.assertEqual(
            qg._nesting_depth_braces("{ if(x){ while(y){ z; } } }"), 2)


class TestCrapScore(unittest.TestCase):
    def test_full_coverage_equals_complexity(self):
        # CRAP with 100% coverage collapses to the complexity itself
        self.assertAlmostEqual(qg.crap_score(10, 1.0), 10)

    def test_zero_coverage(self):
        # comp^2 * 1 + comp
        self.assertAlmostEqual(qg.crap_score(5, 0.0), 30)

    def test_partial_coverage(self):
        # 4^2 * (0.5)^3 + 4 = 16*0.125 + 4 = 6
        self.assertAlmostEqual(qg.crap_score(4, 0.5), 6)


class TestCognitiveApprox(unittest.TestCase):
    def test_nested_branches_weighted_more(self):
        flat = ["    if a:", "    if b:"]
        nested = ["    if a:", "        if b:"]
        flat_score = qg._cognitive_approx(flat, "python", 4)
        nested_score = qg._cognitive_approx(nested, "python", 4)
        self.assertGreater(nested_score, flat_score)

    def test_brace_language_weights_by_depth(self):
        lines = ["if (a) {", "    if (b) {", "    }", "}"]
        self.assertGreater(qg._cognitive_approx(lines, "cbrace", 0), 0)


# --------------------------------------------------------------------------
# _strip_for_scan — the mask handed to the two branch scans
# --------------------------------------------------------------------------

class TestStripForScan(unittest.TestCase):
    def test_a_brace_language_line_shape_survives_the_mask(self):
        masked = qg._strip_for_scan(CBRACE_SOURCE_WITH_LITERALS, "js")
        raw_rows = CBRACE_SOURCE_WITH_LITERALS.split("\n")
        masked_rows = masked.split("\n")
        raw_widths = [len(r) for r in raw_rows]
        masked_widths = [len(r) for r in masked_rows]
        self.assertEqual(len(masked_rows), len(raw_rows))
        self.assertEqual(masked_widths, raw_widths)

    def test_an_unknown_language_is_returned_byte_for_byte(self):
        got = qg._strip_for_scan(CBRACE_SOURCE_WITH_LITERALS, "ruby")
        self.assertEqual(got, CBRACE_SOURCE_WITH_LITERALS)

    def test_line_count_and_line_lengths_survive_the_mask(self):
        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
        raw_rows = LITERAL_HEAVY_SOURCE.split("\n")
        masked_rows = masked.split("\n")
        self.assertEqual(len(masked_rows), len(raw_rows))
        # Hanging rather than paren-aligned continuations in the methods this
        # slice adds: the gate derives nesting_depth from leading whitespace on
        # RAW text, which the scan mask deliberately does not touch, so a
        # paren-aligned argument reads to it as a deeply nested block.
        self.assertEqual(
            [len(row) for row in masked_rows],
            [len(row) for row in raw_rows])

    def test_code_outside_literals_is_left_alone(self):
        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
        rows = masked.split("\n")
        self.assertEqual(rows[0], "def probe(a, b):")
        self.assertEqual(rows[3].strip(), "if a:")
        self.assertEqual(rows[5].strip(), "return b")

    def test_masked_spans_are_filled_with_a_non_whitespace_sentinel(self):
        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
        docstring_row = masked.split("\n")[1]
        self.assertTrue(docstring_row.strip())
        self.assertEqual(set(docstring_row.strip()), {qg._SCAN_SENTINEL})

    def test_a_comment_is_masked_in_the_same_pass(self):
        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
        assignment_row = masked.split("\n")[2]
        self.assertNotIn("#", assignment_row)
        self.assertIn("label = ", assignment_row)

    def test_the_masked_body_scans_as_one_real_branch(self):
        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
        # base path 1 plus the one real branching statement
        self.assertEqual(qg._branch_count(masked), 2)

    def test_leading_indentation_of_a_code_line_is_preserved(self):
        masked = qg._strip_for_scan(LITERAL_HEAVY_SOURCE, "python")
        raw_rows = LITERAL_HEAVY_SOURCE.split("\n")
        masked_rows = masked.split("\n")
        for raw, got in zip(raw_rows, masked_rows):
            self.assertEqual(
                len(raw) - len(raw.lstrip(" ")),
                len(got) - len(got.lstrip(" ")),
                msg=raw)

    @unittest.skipUnless(hasattr(tokenize, "FSTRING_MIDDLE"),
                         "f-string literal segments are separate tokens only "
                         "on newer pythons")
    def test_an_embedded_f_string_expression_still_counts(self):
        # The literal segments of an f-string are masked; the tokens of its
        # embedded expression are not, so a real conditional inside one is
        # still measured. Mirrors the JS rule that ${...} content survives.
        source = "def g(a, b, c):\n    return f'{a " + "if" + " b else c}'\n"
        masked = qg._strip_for_scan(source, "python")
        self.assertEqual(qg._branch_count(masked), 2)

    def test_a_real_branch_on_a_literals_closing_row_keeps_its_nesting_level(self):
        # A multi-line string literal's closing row can carry real code after
        # the literal ends. The masked line's leading whitespace must match
        # the raw line's leading whitespace exactly, or the nesting level
        # _cognitive_approx derives from that row silently drops.
        masked = qg._strip_for_scan(
            MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE, "python")
        raw_rows = MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE.split("\n")
        masked_rows = masked.split("\n")
        for raw, got in zip(raw_rows, masked_rows):
            self.assertEqual(
                len(raw) - len(raw.lstrip(" ")),
                len(got) - len(got.lstrip(" ")),
                msg=raw)


class TestMaskFailsTowardRaw(unittest.TestCase):
    def test_a_tokenizer_failure_yields_the_raw_text(self):
        self.assertIsNone(qg._mask_python_literals(UNTERMINATED_SOURCE))
        self.assertEqual(
            qg._strip_for_scan(UNTERMINATED_SOURCE, "python"),
            UNTERMINATED_SOURCE)

    def test_emptying_too_many_lines_trips_the_corruption_guard(self):
        raw_rows = ["a = 1", "b = 2", "c = 3"]
        self.assertTrue(qg._mask_lost_too_much(raw_rows, ["a = 1", "b = 2", "  "]))

    def test_a_small_share_of_emptied_lines_is_tolerated(self):
        raw_rows = ["a = 1"] * 40
        masked_rows = ["a = 1"] * 39 + ["  "]
        self.assertFalse(qg._mask_lost_too_much(raw_rows, masked_rows))

    def test_an_all_blank_file_is_not_treated_as_corruption(self):
        self.assertFalse(qg._mask_lost_too_much(["", "  "], ["", "  "]))


class TestCbraceMaskFill(unittest.TestCase):
    """What the brace-language fill is allowed to change, character by
    character."""

    def test_braces_and_newlines_survive_inside_a_literal(self):
        masked = qg._mask_cbrace_literals("x = '{a}'\n")
        self.assertEqual(masked.count("{"), 1)
        self.assertEqual(masked.count("}"), 1)
        self.assertEqual(masked.count("\n"), 1)
        self.assertEqual(len(masked), len("x = '{a}'\n"))

    def test_literal_content_becomes_the_shared_sentinel(self):
        masked = qg._mask_cbrace_literals("x = 'ab'\n")
        self.assertEqual(masked, "x = " + qg._SCAN_SENTINEL * 4 + "\n")

    def test_code_outside_a_literal_is_byte_for_byte(self):
        masked = qg._mask_cbrace_literals("const a = b;\n")
        self.assertEqual(masked, "const a = b;\n")

    def test_an_unterminated_construct_yields_none(self):
        self.assertIsNone(
            qg._mask_cbrace_literals(CBRACE_UNTERMINATED_SOURCE))

    def test_the_corruption_guard_inside_the_cbrace_mask_falls_back(self):
        # The guard AS WRITTEN inside _mask_cbrace_literals. Masking never
        # empties a line (the sentinel is non-whitespace), so the signal is
        # forced rather than constructed from real source -- the same
        # technique the python mask's guard test uses.
        with mock.patch.object(qg, "_mask_lost_too_much", return_value=True):
            self.assertIsNone(qg._mask_cbrace_literals("x = 1;\n"))

    def test_an_unterminated_brace_source_still_yields_raw_counts(self):
        masked = qg._strip_for_scan(CBRACE_UNTERMINATED_SOURCE, "js")
        self.assertEqual(masked, CBRACE_UNTERMINATED_SOURCE)

    def test_a_star_slash_inside_a_regex_literal_does_not_open_a_phantom_comment(self):
        # A stepped-over slash inside a character class, followed by a `*`,
        # forms a star-slash sequence that would otherwise open a
        # block-comment span reaching all the way to the next real block
        # comment much later in the source, silently dropping the branches
        # of every line in between. The scan is required to refuse this
        # opener and fall back to raw text instead.
        source = (
            "const re = /[/*]/;\n"
            "function f(a){ ternary(a, a) ; }\n"
            "/* real comment */\n"
            "function g(b){ ternary(b, 1) ; }\n"
        )
        self.assertIsNone(qg._mask_cbrace_literals(source))
        self.assertEqual(qg._strip_for_scan(source, "js"), source)

    def test_an_ordinary_multiline_block_comment_still_masks(self):
        source = "/* line one\nline two */\nconst a = b;\n"
        masked = qg._mask_cbrace_literals(source)
        self.assertIsNotNone(masked)
        self.assertEqual(masked.count("\n"), source.count("\n"))
        self.assertNotIn("line", masked)
        self.assertIn("const a = b;", masked)

    def test_a_backtick_inside_a_regex_literal_does_not_open_a_phantom_template(self):
        # A stepped-over slash on a source line, followed later by a
        # backtick, would otherwise open a template-literal span reaching
        # all the way to the next real backtick much later in the source,
        # silently hiding the boolean operator on the line in between. The
        # scan is required to refuse this opener and fall back to raw text.
        self.assertIsNone(
            qg._mask_cbrace_literals(BACKTICK_REGEX_PHANTOM_SOURCE))
        self.assertEqual(
            qg._strip_for_scan(BACKTICK_REGEX_PHANTOM_SOURCE, "js"),
            BACKTICK_REGEX_PHANTOM_SOURCE)

    def test_an_ordinary_template_literal_still_masks(self):
        source = "const a = `line one\nline two`;\n"
        masked = qg._mask_cbrace_literals(source)
        self.assertIsNotNone(masked)
        self.assertEqual(masked.count("\n"), source.count("\n"))
        self.assertNotIn("line", masked)


class TestScanLangForPath(unittest.TestCase):
    """Which extensions the scan mask is allowed to lex. The hand scanner
    implements JS/TypeScript quoting rules alone, so every other brace
    extension has to stay on raw text -- today's over-count, the safe
    direction."""

    def test_the_js_family_extensions_are_masked(self):
        self.assertEqual(qg._scan_lang_for("a.js"), "js")
        self.assertEqual(qg._scan_lang_for("a.mjs"), "js")
        self.assertEqual(qg._scan_lang_for("a.cjs"), "js")
        self.assertEqual(qg._scan_lang_for("a.ts"), "js")

    def test_a_python_path_keeps_the_python_mask(self):
        self.assertEqual(qg._scan_lang_for("a.py"), "python")

    def test_the_other_brace_extensions_are_left_on_raw_text(self):
        self.assertIsNone(qg._scan_lang_for("a.rs"))
        self.assertIsNone(qg._scan_lang_for("a.c"))
        self.assertIsNone(qg._scan_lang_for("a.h"))
        self.assertIsNone(qg._scan_lang_for("a.cpp"))
        self.assertIsNone(qg._scan_lang_for("a.cc"))
        self.assertIsNone(qg._scan_lang_for("a.hpp"))
        self.assertIsNone(qg._scan_lang_for("a.go"))
        self.assertIsNone(qg._scan_lang_for("a.java"))
        self.assertIsNone(qg._scan_lang_for("a.cs"))
        self.assertEqual(qg._lang_for("a.rs"), "cbrace")

    def test_jsx_and_tsx_are_also_left_on_raw_text(self):
        # The hand scanner has no model of a JSX text node, where an
        # apostrophe is prose, not a string opener, so these two extensions
        # stay on raw text for a different reason than the other brace
        # languages above -- see test_a_jsx_apostrophe_pair_keeps_both_branches.
        self.assertIsNone(qg._scan_lang_for("a.jsx"))
        self.assertIsNone(qg._scan_lang_for("a.TSX"))
        self.assertEqual(qg._lang_for("a.jsx"), "cbrace")
        self.assertEqual(qg._lang_for("a.tsx"), "cbrace")

    def test_an_unknown_extension_is_left_on_raw_text(self):
        self.assertIsNone(qg._scan_lang_for("a.rb"))

    def test_a_rust_lifetime_pair_keeps_both_branches(self):
        # The defect this routing prevents, measured on the real callables:
        # lexed with JS rules the two lifetimes pair into a phantom string
        # over the boolean operator between them, dropping 2 branches to 1.
        self.assertEqual(qg._branch_count(RUST_LIFETIME_LINE), 2)
        self.assertEqual(
            qg._branch_count(qg._mask_cbrace_literals(RUST_LIFETIME_LINE)), 1)
        scanned = qg._strip_for_scan(
            RUST_LIFETIME_LINE, qg._scan_lang_for("lib.rs"))
        self.assertEqual(scanned, RUST_LIFETIME_LINE)
        self.assertEqual(qg._branch_count(scanned), 2)

    def test_a_cplusplus_digit_separator_pair_keeps_both_branches(self):
        self.assertEqual(qg._branch_count(CPP_DIGIT_SEPARATOR_LINE), 2)
        self.assertEqual(
            qg._branch_count(
                qg._mask_cbrace_literals(CPP_DIGIT_SEPARATOR_LINE)), 1)
        scanned = qg._strip_for_scan(
            CPP_DIGIT_SEPARATOR_LINE, qg._scan_lang_for("a.cpp"))
        self.assertEqual(scanned, CPP_DIGIT_SEPARATOR_LINE)
        self.assertEqual(qg._branch_count(scanned), 2)

    def test_analyze_builtin_keeps_both_branches_in_a_cplusplus_file(self):
        # The end-to-end pin: this drives the routing through the product
        # entry point, so a mis-wired analyze_builtin fails here rather than
        # passing on hand-composed calls. Measured before the routing landed,
        # this reported 1; the raw line has 2.
        findings, _ = qg.analyze_builtin(
            "a.cpp", CPP_DIGIT_SEPARATOR_FUNCTION, [(1, 1)])
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0]["metrics"]["cyclomatic_complexity"], 2)

    def test_a_jsx_apostrophe_pair_keeps_both_branches(self):
        # The defect this routing prevents, measured on the real callables:
        # lexed with JS quoting rules the two contractions on the text line
        # pair into a phantom string over the boolean operator between them,
        # dropping 2 branches to 1.
        findings, _ = qg.analyze_builtin(
            "Row.jsx", JSX_APOSTROPHE_FUNCTION, [(1, 5)])
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0]["metrics"]["cyclomatic_complexity"], 2)
        scanned = qg._strip_for_scan(
            JSX_APOSTROPHE_FUNCTION, qg._scan_lang_for("Row.tsx"))
        self.assertEqual(scanned, JSX_APOSTROPHE_FUNCTION)

    def test_the_extraction_family_name_is_no_longer_a_mask_language(self):
        # "cbrace" still selects the brace extraction model, so it must NOT
        # double as a mask language: handed to the mask it returns raw text.
        self.assertEqual(
            qg._strip_for_scan(CBRACE_SOURCE_WITH_LITERALS, "cbrace"),
            CBRACE_SOURCE_WITH_LITERALS)


class TestRegexQuotePhantom(unittest.TestCase):
    """The regex-versus-quote residual as the code actually behaves, measured
    through the real callable. Two documented safety claims were falsified
    here: the mask succeeds on an odd quote count, and the phantom it opens
    can reach past the end of its own line."""

    def test_an_odd_quote_count_does_not_force_the_fallback(self):
        # Three quote characters on line one, mask still succeeds.
        self.assertIsNotNone(
            qg._mask_cbrace_literals(REGEX_QUOTE_PHANTOM_SOURCE))

    def test_the_phantom_hides_one_real_boolean_operator(self):
        first_raw = REGEX_QUOTE_PHANTOM_SOURCE.split("\n")[0]
        masked = qg._mask_cbrace_literals(REGEX_QUOTE_PHANTOM_SOURCE)
        first_masked = masked.split("\n")[0]
        self.assertEqual(qg._branch_count(first_raw), 2)
        self.assertEqual(qg._branch_count(first_masked), 1)

    def test_a_plain_phantom_does_not_reach_the_next_line(self):
        # Narrow by design: this pins ONE spot-checked shape, the one with no
        # backslash before the newline. It is NOT a general boundary claim --
        # the multiline test below pins the shape that crosses.
        masked = qg._mask_cbrace_literals(REGEX_QUOTE_PHANTOM_SOURCE)
        rows = masked.split("\n")
        raw_rows = REGEX_QUOTE_PHANTOM_SOURCE.split("\n")
        self.assertEqual(rows[1], raw_rows[1])

    def test_a_trailing_backslash_carries_the_phantom_past_the_newline(self):
        # The falsified line-boundedness claim, pinned: the mask succeeds and
        # the hidden boolean operator sits on the SECOND line.
        masked = qg._mask_cbrace_literals(REGEX_QUOTE_PHANTOM_MULTILINE)
        self.assertIsNotNone(masked)
        self.assertEqual(qg._branch_count(REGEX_QUOTE_PHANTOM_MULTILINE), 2)
        self.assertEqual(qg._branch_count(masked), 1)
        rows = masked.split("\n")
        raw_rows = REGEX_QUOTE_PHANTOM_MULTILINE.split("\n")
        self.assertNotEqual(rows[1], raw_rows[1])
        self.assertEqual(rows[2], raw_rows[2])


class TestScanTokensFallbackPaths(unittest.TestCase):
    """_scan_tokens's two guards send the whole mask back to raw text, but
    stdlib tokenize never produces either shape for real source, so each is
    driven directly through the real callable with a patched tokenizer."""

    def test_an_empty_token_stream_yields_none(self):
        with mock.patch.object(qg.tokenize, "generate_tokens", empty_token_stream):
            self.assertIsNone(qg._scan_tokens("x = 1\n"))

    def test_a_non_endmarker_end_state_yields_none(self):
        with mock.patch.object(qg.tokenize, "generate_tokens", non_endmarker_token_stream):
            self.assertIsNone(qg._scan_tokens("x = 1\n"))

    def test_the_corruption_guard_inside_mask_python_literals_falls_back(self):
        # _mask_lost_too_much itself is exercised directly above; this drives
        # the guard AS WRITTEN inside _mask_python_literals, forcing the
        # signal it reacts to rather than trying to construct real source
        # that trips it (masking never empties a line: the sentinel is
        # always non-whitespace).
        with mock.patch.object(qg, "_mask_lost_too_much", return_value=True):
            self.assertIsNone(qg._mask_python_literals("x = 1\n"))


class TestScanLinesForFallback(unittest.TestCase):
    def test_a_line_count_mismatch_falls_back_to_the_raw_lines(self):
        source = "x = 1\ny = 2\n"
        lines = source.splitlines()
        with mock.patch.object(qg, "_strip_for_scan", longer_scan):
            self.assertEqual(qg._scan_lines_for(source, "python", lines), lines)


class TestCbraceSpanScanner(unittest.TestCase):
    """The span scanner is what decides which characters the brace-language
    mask is allowed to blank. Every case is driven through the real
    callables."""

    def spans(self, text):
        return qg._cbrace_spans(text, 0, len(text))

    def covered(self, text):
        """The concatenated text of every span the scanner reported."""
        return "".join(text[a:b] for a, b in self.spans(text))

    def test_a_line_comment_is_one_span_to_the_newline(self):
        text = "a = 1 // note\nb = 2\n"
        self.assertEqual(self.covered(text), "// note")

    def test_a_block_comment_span_crosses_lines(self):
        text = "a\n/* one\ntwo */\nb\n"
        self.assertEqual(self.covered(text), "/* one\ntwo */")

    def test_both_quote_flavours_are_spans_including_delimiters(self):
        text = "x = 'a' + \"b\"\n"
        self.assertEqual(self.covered(text), "'a'\"b\"")

    def test_an_escaped_quote_does_not_close_a_string(self):
        text = "x = 'a\\'b' + 1\n"
        self.assertEqual(self.covered(text), "'a\\'b'")

    def test_an_apostrophe_inside_a_comment_opens_nothing(self):
        text = "// it doesn't\nif (a) { b() }\n"
        self.assertEqual(self.covered(text), "// it doesn't")

    def test_template_interpolation_code_is_not_covered(self):
        text = "x = `m ${a && b} t`\n"
        covered = self.covered(text)
        self.assertIn("m ", covered)
        self.assertNotIn("&&", covered)

    def test_a_string_inside_an_interpolation_is_covered(self):
        text = "x = `m ${f('q')} t`\n"
        covered = self.covered(text)
        self.assertIn("'q'", covered)
        self.assertNotIn("f(", covered)

    def test_a_brace_inside_an_interpolated_string_does_not_close_it(self):
        text = "x = `m ${f('}')} t`\n"
        covered = self.covered(text)
        self.assertIn("'}'", covered)
        self.assertNotIn("f(", covered)

    def test_an_escaped_backtick_does_not_close_a_template(self):
        # Drives the escape hop inside _cb_template_hop: the whole literal,
        # escaped delimiter included, comes back as one span.
        text = "x = `m \\` t` + 1\n"
        self.assertEqual(self.covered(text), "`m \\` t`")

    def test_a_lone_slash_is_stepped_over_as_division(self):
        text = "x = a / b\n"
        self.assertEqual(self.spans(text), [])

    def test_an_unterminated_string_fails_toward_raw(self):
        self.assertIsNone(self.spans("x = 'open\n"))

    def test_an_unterminated_block_comment_fails_toward_raw(self):
        self.assertIsNone(self.spans("x = 1 /* open\n"))

    def test_an_unterminated_template_fails_toward_raw(self):
        self.assertIsNone(self.spans("x = `open\n"))

    def test_an_unterminated_interpolation_fails_toward_raw(self):
        self.assertIsNone(self.spans("x = `m ${a\n"))

    def test_an_unterminated_string_inside_an_interpolation_fails(self):
        self.assertIsNone(self.spans("x = `m ${f('open} t`\n"))


# --------------------------------------------------------------------------
# Builtin heuristic extraction
# --------------------------------------------------------------------------

class TestAnalyzeBuiltinPython(unittest.TestCase):
    SOURCE = (
        "class Foo:\n"
        "    def small(self, a):\n"
        "        return a\n"
        "\n"
        "    def big(self, a, b, c, d, e):\n"
        "        if a:\n"
        "            for i in b:\n"
        "                if c:\n"
        "                    while d:\n"
        "                        return e\n"
        "        return 0\n"
    )

    def test_extracts_functions_intersecting_changed_ranges(self):
        # change only touches the `big` function (lines 5-11)
        findings, cls = qg.analyze_builtin("m.py", self.SOURCE, [(5, 11)])
        names = {f["function"] for f in findings}
        self.assertIn("big", names)
        self.assertNotIn("small", names)  # outside the changed range

    def test_metrics_reasonable(self):
        findings, cls = qg.analyze_builtin("m.py", self.SOURCE, [(1, 11)])
        big = next(f for f in findings if f["function"] == "big")
        m = big["metrics"]
        self.assertEqual(m["parameter_count"], 5)      # a,b,c,d,e (self dropped)
        self.assertGreaterEqual(m["cyclomatic_complexity"], 4)  # if/for/if/while
        self.assertGreaterEqual(m["nesting_depth"], 3)
        self.assertIn("cognitive_complexity", m)
        self.assertGreater(m["method_lines"], 0)

    def test_class_finding_counts_nonblank_lines(self):
        _, cls = qg.analyze_builtin("m.py", self.SOURCE, [(1, 11)])
        self.assertIsNotNone(cls)
        self.assertEqual(cls["class_lines"], qg._nonblank(self.SOURCE.splitlines()))

    def test_unsupported_extension_yields_nothing(self):
        findings, cls = qg.analyze_builtin("data.txt", "whatever\n", [(1, 1)])
        self.assertEqual(findings, [])
        self.assertIsNone(cls)


class TestAnalyzeBuiltinCbrace(unittest.TestCase):
    SOURCE = (
        "function outer(a, b) {\n"
        "    if (a) {\n"
        "        return b && a || c;\n"
        "    }\n"
        "    return 0;\n"
        "}\n"
    )

    def test_extracts_brace_function(self):
        findings, _ = qg.analyze_builtin("m.js", self.SOURCE, [(1, 6)])
        names = {f["function"] for f in findings}
        self.assertIn("outer", names)

    def test_control_keyword_not_treated_as_function(self):
        # `if (a) {` must not register as a function named `if`
        findings, _ = qg.analyze_builtin("m.js", self.SOURCE, [(1, 6)])
        self.assertNotIn("if", {f["function"] for f in findings})

    def test_params_and_complexity(self):
        findings, _ = qg.analyze_builtin("m.js", self.SOURCE, [(1, 6)])
        outer = next(f for f in findings if f["function"] == "outer")
        self.assertEqual(outer["metrics"]["parameter_count"], 2)
        # base + if + && + || -> >= 4
        self.assertGreaterEqual(outer["metrics"]["cyclomatic_complexity"], 4)

    def test_arrow_function_detected(self):
        src = "const handler = (x, y) => {\n    return x + y;\n}\n"
        findings, _ = qg.analyze_builtin("m.ts", src, [(1, 3)])
        self.assertIn("handler", {f["function"] for f in findings})


class TestAnalyzeBuiltinMasksLiterals(unittest.TestCase):
    """Branch words and operator punctuation inside a literal or a comment are
    not branching, and masking them must not disturb any other metric."""

    def measure(self, source, lang_path):
        findings, _ = qg.analyze_builtin(
            lang_path, source, [(1, len(source.splitlines()))])
        return {f["function"]: f for f in findings}

    def measure_unmasked(self, source, lang_path):
        with mock.patch.object(qg, "_strip_for_scan", unmasked):
            return self.measure(source, lang_path)

    def test_only_the_real_branch_is_counted_in_python(self):
        probe = self.measure(LITERAL_HEAVY_SOURCE, "m.py")["probe"]
        self.assertEqual(probe["metrics"]["cyclomatic_complexity"], 2)
        self.assertEqual(probe["metrics"]["cognitive_complexity"], 2)

    def test_the_span_and_the_shape_metrics_are_untouched(self):
        probe = self.measure(LITERAL_HEAVY_SOURCE, "m.py")["probe"]
        self.assertEqual((probe["line_start"], probe["line_end"]), (1, 6))
        self.assertEqual(probe["metrics"]["method_lines"], 6)
        self.assertEqual(probe["metrics"]["nesting_depth"], 2)
        self.assertEqual(probe["metrics"]["parameter_count"], 2)

    def test_a_brace_language_literal_stops_being_counted(self):
        outer = self.measure(CBRACE_SOURCE_WITH_LITERALS, "m.js")["outer"]
        raw = self.measure_unmasked(
            CBRACE_SOURCE_WITH_LITERALS, "m.js")["outer"]
        got = outer["metrics"]
        was = raw["metrics"]
        # The fixture's literal carries six fake branches; the one real
        # branch is the ternary on the return line.
        self.assertLess(
            got["cyclomatic_complexity"], was["cyclomatic_complexity"])
        self.assertEqual(got["cyclomatic_complexity"], 2)
        self.assertEqual(got["nesting_depth"], was["nesting_depth"])
        self.assertEqual(got["method_lines"], was["method_lines"])
        self.assertEqual(outer["line_start"], raw["line_start"])
        self.assertEqual(outer["line_end"], raw["line_end"])

    def test_an_untokenizable_python_file_still_yields_raw_counts(self):
        broken = "def probe(a):\n    return a  # " + BRANCH_WORDS_IN_LITERALS \
                 + "\n    x = '''open\n"
        findings, _ = qg.analyze_builtin(
            "m.py", broken, [(1, len(broken.splitlines()))])
        probe = next(f for f in findings if f["function"] == "probe")
        self.assertGreater(probe["metrics"]["cyclomatic_complexity"], 1)
        raw = self.measure_unmasked(broken, "m.py")["probe"]
        self.assertEqual(probe["metrics"], raw["metrics"])

    def test_a_real_branch_after_a_multiline_literal_closes_is_not_undercounted(self):
        # The masked and unmasked cognitive_complexity must agree exactly:
        # the real `if`/`else` on the literal's closing row must keep the
        # nesting weight its own row's indentation implies, never dropping to
        # a shallower level because the mask overwrote that row's leading
        # whitespace with the sentinel.
        masked = self.measure(
            MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE, "m.py")["f"]
        raw = self.measure_unmasked(
            MULTILINE_LITERAL_WITH_TRAILING_TERNARY_SOURCE, "m.py")["f"]
        self.assertEqual(
            masked["metrics"]["cognitive_complexity"],
            raw["metrics"]["cognitive_complexity"])


class TestCbraceMaskedMetrics(unittest.TestCase):
    """The three constructs the brace-language mask must get right, measured
    end to end through analyze_builtin."""

    def measure(self, source, path):
        findings, _ = qg.analyze_builtin(
            path, source, [(1, len(source.splitlines()))])
        return {f["function"]: f for f in findings}

    def measure_unmasked(self, source, path):
        with mock.patch.object(qg, "_strip_for_scan", unmasked):
            return self.measure(source, path)

    def test_real_operators_inside_an_interpolation_are_still_counted(self):
        masked = self.measure(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
        # The real branches: the two operators inside ${...} and the one
        # branch keyword. Base path plus three.
        self.assertEqual(masked["metrics"]["cyclomatic_complexity"], 4)

    def test_the_template_and_comment_text_is_not_counted(self):
        masked = self.measure(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
        raw = self.measure_unmasked(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
        got = masked["metrics"]
        was = raw["metrics"]
        self.assertLess(
            got["cyclomatic_complexity"], was["cyclomatic_complexity"])
        self.assertLess(
            got["cognitive_complexity"], was["cognitive_complexity"])

    def test_the_shape_metrics_and_the_span_are_untouched(self):
        masked = self.measure(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
        raw = self.measure_unmasked(CBRACE_TEMPLATE_SOURCE, "m.js")["probe"]
        got = masked["metrics"]
        was = raw["metrics"]
        self.assertEqual(got["nesting_depth"], was["nesting_depth"])
        self.assertEqual(got["method_lines"], was["method_lines"])
        self.assertEqual(got["parameter_count"], was["parameter_count"])
        self.assertEqual(masked["line_start"], raw["line_start"])
        self.assertEqual(masked["line_end"], raw["line_end"])

    def test_an_apostrophe_in_a_comment_does_not_blank_the_code(self):
        # A strings-only scanner opens at the first comment's apostrophe a
        # literal it can never close, since the quote alternatives exclude
        # the newline, so the whole file loses its mask and reverts to
        # today's over-count. Both real branches must survive AND the mask
        # must succeed -- the assertIsNotNone is what makes this test bite
        # on a strings-only scanner, because the equalities below hold
        # either way once the mask falls back to raw text.
        source = CBRACE_APOSTROPHE_COMMENTS_SOURCE
        self.assertIsNotNone(qg._mask_cbrace_literals(source))
        masked = self.measure(source, "m.js")["probe"]
        raw = self.measure_unmasked(source, "m.js")["probe"]
        got = masked["metrics"]
        was = raw["metrics"]
        self.assertEqual(
            got["cyclomatic_complexity"], was["cyclomatic_complexity"])
        self.assertEqual(
            got["cognitive_complexity"], was["cognitive_complexity"])

    def test_the_mjs_extension_takes_the_same_path(self):
        masked = self.measure(CBRACE_TEMPLATE_SOURCE, "m.mjs")["probe"]
        raw = self.measure_unmasked(CBRACE_TEMPLATE_SOURCE, "m.mjs")["probe"]
        self.assertLess(
            masked["metrics"]["cyclomatic_complexity"],
            raw["metrics"]["cyclomatic_complexity"])


class TestMatchBraceEnd(unittest.TestCase):
    def test_balances_nested_braces(self):
        lines = ["f() {", "  { }", "}"]
        self.assertEqual(qg._match_brace_end(lines, 0), 2)

    def test_unbalanced_returns_none(self):
        lines = ["f() {", "  x"]
        self.assertIsNone(qg._match_brace_end(lines, 0))


# --------------------------------------------------------------------------
# Backend parsing + merge
# --------------------------------------------------------------------------

class TestLizardCsvParse(unittest.TestCase):
    def test_parses_rows(self):
        # nloc,ccn,token,param,length,location,file,func,long,start,end
        csv_text = (
            '12,7,80,3,20,"foo@5-24@m.py",m.py,foo,"foo(a,b,c)",5,24\n'
            'bad,row\n'
        )
        recs = qg._parse_lizard_csv(csv_text)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["file"], "m.py")
        self.assertEqual(r["function"], "foo")
        self.assertEqual(r["cyclomatic_complexity"], 7)
        self.assertEqual(r["method_lines"], 12)
        self.assertEqual(r["parameter_count"], 3)
        self.assertEqual((r["line_start"], r["line_end"]), (5, 24))


class TestRadonJsonParse(unittest.TestCase):
    def test_parses_function_and_method_blocks(self):
        data = json.dumps({
            "m.py": [
                {"type": "f", "name": "foo", "lineno": 3, "endline": 20,
                 "complexity": 9},
                {"type": "m", "name": "bar", "lineno": 25, "endline": 30,
                 "complexity": 4},
                {"type": "c", "name": "Klass", "lineno": 1, "complexity": 2},
            ]
        })
        recs = qg._parse_radon_json(data)
        names = {r["function"] for r in recs}
        self.assertEqual(names, {"foo", "bar"})   # class block excluded
        foo = next(r for r in recs if r["function"] == "foo")
        self.assertEqual(foo["cyclomatic_complexity"], 9)

    def test_malformed_json_yields_empty(self):
        self.assertEqual(qg._parse_radon_json("not json"), [])


class TestBackendUnavailableReturnsEmpty(unittest.TestCase):
    def test_run_lizard_empty_files(self):
        self.assertEqual(qg.run_lizard([], "."), [])

    def test_run_lizard_missing_binary(self):
        with mock.patch("quality_gate.subprocess.run",
                        side_effect=FileNotFoundError("lizard")):
            self.assertEqual(qg.run_lizard(["m.py"], "."), [])

    def test_run_radon_nonzero_exit_returns_empty(self):
        with mock.patch("quality_gate.subprocess.run") as m:
            m.return_value = mock.Mock(returncode=2, stdout="", stderr="boom")
            self.assertEqual(qg.run_radon(["m.py"], "."), [])


class TestMergeBackendAndHeuristic(unittest.TestCase):
    def test_backend_owns_measured_cognitive_from_heuristic(self):
        backend = [{"file": "m.py", "function": "foo",
                    "line_start": 5, "line_end": 20,
                    "cyclomatic_complexity": 7, "method_lines": 12,
                    "parameter_count": 3}]
        heur = [{"function": "foo", "line_start": 5, "line_end": 20,
                 "metrics": {"cyclomatic_complexity": 6, "method_lines": 11,
                             "parameter_count": 3, "cognitive_complexity": 8,
                             "nesting_depth": 2}}]
        merged = qg._merge_backend_and_heuristic(backend, heur, "m.py")
        self.assertEqual(len(merged), 1)
        m = merged[0]
        # backend value wins for the metric it measured
        self.assertEqual(m["metrics"]["cyclomatic_complexity"], 7)
        self.assertEqual(m["metric_sources"]["cyclomatic_complexity"], "lizard")
        # cognitive ALWAYS comes from the heuristic, never the tool
        self.assertEqual(m["metrics"]["cognitive_complexity"], 8)
        self.assertEqual(m["metric_sources"]["cognitive_complexity"],
                         "builtin-heuristic")
        # nesting also from heuristic (lizard doesn't measure it)
        self.assertEqual(m["metric_sources"]["nesting_depth"],
                         "builtin-heuristic")

    def test_radon_backend_name_when_no_method_lines(self):
        backend = [{"file": "m.py", "function": "foo",
                    "line_start": 5, "line_end": 20,
                    "cyclomatic_complexity": 9}]
        merged = qg._merge_backend_and_heuristic(backend, [], "m.py")
        self.assertEqual(merged[0]["source"], "radon")
        self.assertEqual(merged[0]["metric_sources"]["cyclomatic_complexity"],
                         "radon")

    def test_no_matching_heuristic_still_reports_backend_metrics(self):
        backend = [{"file": "m.py", "function": "orphan",
                    "line_start": 1, "line_end": 3,
                    "cyclomatic_complexity": 4, "method_lines": 2,
                    "parameter_count": 1}]
        merged = qg._merge_backend_and_heuristic(backend, [], "m.py")
        self.assertNotIn("cognitive_complexity", merged[0]["metrics"])


# --------------------------------------------------------------------------
# Coverage parsing + CRAP assembly
# --------------------------------------------------------------------------

class TestCoverageParsing(unittest.TestCase):
    def test_cobertura(self):
        xml = (
            '<coverage><packages><package><classes>'
            '<class filename="src/m.py"><lines>'
            '<line number="1" hits="1"/>'
            '<line number="2" hits="0"/>'
            '<line number="3" hits="1"/>'
            '</lines></class>'
            '</classes></package></packages></coverage>'
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "coverage.xml")
            Path(path).write_text(xml)
            cov = qg.parse_coverage(path, d)
        self.assertIn("src/m.py", cov)
        self.assertAlmostEqual(cov["src/m.py"], 2 / 3)

    def test_lcov(self):
        lcov = (
            "SF:src/m.py\n"
            "DA:1,1\nDA:2,0\nDA:3,4\n"
            "end_of_record\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "lcov.info")
            Path(path).write_text(lcov)
            cov = qg.parse_coverage(path, d)
        self.assertAlmostEqual(cov["src/m.py"], 2 / 3)

    def test_malformed_xml_yields_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "coverage.xml")
            Path(path).write_text("<not-closed>")
            self.assertEqual(qg.parse_coverage(path, d), {})

    def test_none_path_yields_empty(self):
        self.assertEqual(qg.parse_coverage(None, "."), {})


class TestFindCoverage(unittest.TestCase):
    def test_explicit_path_when_exists(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "cov.xml")
            Path(p).write_text("x")
            self.assertEqual(qg.find_coverage(p, d), p)

    def test_explicit_missing_returns_none(self):
        self.assertIsNone(qg.find_coverage("/nope/cov.xml", "."))

    def test_probes_repo_root(self):
        with tempfile.TemporaryDirectory() as d:
            Path(os.path.join(d, "coverage.xml")).write_text("x")
            self.assertEqual(qg.find_coverage(None, d),
                             os.path.join(d, "coverage.xml"))

    def test_no_report_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(qg.find_coverage(None, d))


class TestCrapAssembly(unittest.TestCase):
    def test_crap_finding_emitted_with_coverage(self):
        func_m = [{"file": "m.py", "function": "foo",
                   "metrics": {"cyclomatic_complexity": 5},
                   "source": "builtin-heuristic"}]
        findings, skipped = [], []
        qg._append_crap_findings(func_m, 30, {"m.py": 0.0}, findings, skipped)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["metric"], "crap_score")
        self.assertAlmostEqual(findings[0]["value"], 30)  # comp^2 + comp at 0 cov

    def test_missing_file_coverage_noted_once(self):
        func_m = [
            {"file": "m.py", "function": "a",
             "metrics": {"cyclomatic_complexity": 3}, "source": "x"},
            {"file": "m.py", "function": "b",
             "metrics": {"cyclomatic_complexity": 4}, "source": "x"},
        ]
        findings, skipped = [], []
        qg._append_crap_findings(func_m, 30, {"other.py": 1.0}, findings,
                                 skipped)
        self.assertEqual(findings, [])
        crap_skips = [s for s in skipped if s.get("metric") == "crap_score"]
        self.assertEqual(len(crap_skips), 1)  # noted once for the file

    def test_coverage_for_matches_by_basename(self):
        cov = {"deep/nested/m.py": 0.5}
        self.assertEqual(qg._coverage_for("other/m.py", cov), 0.5)


# --------------------------------------------------------------------------
# Threshold evaluation + custom gates
# --------------------------------------------------------------------------

class TestEvaluate(unittest.TestCase):
    def _func(self, **metrics):
        return {"file": "m.py", "function": "foo", "metrics": metrics,
                "source": "builtin-heuristic"}

    def test_pass_and_fail_findings(self):
        fm = [self._func(cyclomatic_complexity=5, method_lines=200)]
        findings, _ = qg.evaluate(fm, [], qg.DEFAULT_THRESHOLDS, {}, False)
        by_metric = {f["metric"]: f for f in findings}
        self.assertTrue(by_metric["cyclomatic_complexity"]["pass"])   # 5 <= 10
        self.assertFalse(by_metric["method_lines"]["pass"])           # 200 > 50

    def test_crap_skipped_when_no_coverage(self):
        fm = [self._func(cyclomatic_complexity=5)]
        _, skipped = qg.evaluate(fm, [], qg.DEFAULT_THRESHOLDS, {}, False)
        self.assertTrue(any(s.get("metric") == "crap_score"
                            and s["reason"] == "no coverage report"
                            for s in skipped))

    def test_class_lines_evaluated(self):
        cm = [{"file": "m.py", "class_lines": 400,
               "source": "builtin-heuristic"}]
        findings, _ = qg.evaluate([], cm, qg.DEFAULT_THRESHOLDS, {}, False)
        cl = next(f for f in findings if f["metric"] == "class_lines")
        self.assertFalse(cl["pass"])   # 400 > 300
        self.assertIsNone(cl["function"])

    def test_missing_cognitive_metric_noted_once(self):
        # a backend-only function that never got a cognitive value
        fm = [{"file": "m.py", "function": "a",
               "metrics": {"cyclomatic_complexity": 3}, "source": "lizard"},
              {"file": "m.py", "function": "b",
               "metrics": {"cyclomatic_complexity": 4}, "source": "lizard"}]
        _, skipped = qg.evaluate(fm, [], qg.DEFAULT_THRESHOLDS, {}, False)
        cog = [s for s in skipped if s.get("metric") == "cognitive_complexity"]
        self.assertEqual(len(cog), 1)


class TestCustomGates(unittest.TestCase):
    def _func(self, **metrics):
        return {"file": "m.py", "function": "foo", "metrics": metrics,
                "source": "builtin-heuristic"}

    def test_metric_form_evaluated_here(self):
        fm = [self._func(cyclomatic_complexity=12)]
        gates = [{"name": "tight-cc", "metric": "cyclomatic_complexity",
                  "threshold": 8}]
        findings, skipped = qg.evaluate_custom_gates(gates, fm, [])
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0]["pass"])   # 12 > 8
        self.assertEqual(findings[0]["gate"], "tight-cc")

    def test_command_form_deferred_to_skill(self):
        gates = [{"name": "no-todos", "command": "! grep -r TODO",
                  "pass_when": "exit 0"}]
        findings, skipped = qg.evaluate_custom_gates(gates, [], [])
        self.assertEqual(findings, [])
        self.assertEqual(len(skipped), 1)
        self.assertIn("command-form", skipped[0]["reason"])
        self.assertEqual(skipped[0]["gate"], "no-todos")

    def test_metric_not_measured_is_skipped(self):
        gates = [{"name": "g", "metric": "halstead", "threshold": 1}]
        findings, skipped = qg.evaluate_custom_gates(gates, [], [])
        self.assertEqual(findings, [])
        self.assertIn("not measured", skipped[0]["reason"])

    def test_malformed_gate_skipped(self):
        gates = [{"name": "g"}]  # neither command nor metric+threshold
        findings, skipped = qg.evaluate_custom_gates(gates, [], [])
        self.assertEqual(findings, [])
        self.assertIn("malformed", skipped[0]["reason"])


# --------------------------------------------------------------------------
# Report shape
# --------------------------------------------------------------------------

class TestBuildReport(unittest.TestCase):
    def test_pass_when_all_findings_pass(self):
        findings = [qg._finding("m.py", "f", "cyclomatic_complexity", 3, 10,
                                "builtin-heuristic")]
        report = qg.build_report("BASE", "HEAD", "defaults",
                                 ["builtin-heuristic"], findings, [])
        self.assertTrue(report["summary"]["pass"])
        self.assertEqual(report["summary"]["failures"], [])
        self.assertEqual(report["version"], 1)
        self.assertEqual(report["base"], "BASE")

    def test_fail_lists_failures(self):
        findings = [
            qg._finding("m.py", "f", "method_lines", 90, 50, "lizard"),
            qg._finding("m.py", "f", "cyclomatic_complexity", 3, 10, "lizard"),
        ]
        report = qg.build_report("B", "H", "loaded", ["lizard"], findings, [])
        self.assertFalse(report["summary"]["pass"])
        self.assertEqual(len(report["summary"]["failures"]), 1)
        self.assertEqual(report["summary"]["failures"][0]["metric"],
                         "method_lines")

    def test_vacuous_pass_is_flagged(self):
        # Regression (run 20260807, Phase 5): a pass with ZERO checks over a
        # 60-file range was indistinguishable from a measured pass; the
        # controller had to catch it by hand. A zero-check pass over a
        # non-empty diff now carries summary.vacuous so no caller can mistake
        # it for evidence.
        report = qg.build_report("B", "H", "loaded", [], [], [],
                                 changed_files=60)
        self.assertTrue(report["summary"]["pass"])
        self.assertEqual(report["summary"]["checks"], 0)
        self.assertTrue(report["summary"]["vacuous"])

    def test_measured_pass_is_not_vacuous(self):
        findings = [qg._finding("m.py", "f", "cyclomatic_complexity", 3, 10,
                                "builtin-heuristic")]
        report = qg.build_report("B", "H", "loaded", ["builtin-heuristic"],
                                 findings, [], changed_files=1)
        self.assertEqual(report["summary"]["checks"], 1)
        self.assertFalse(report["summary"]["vacuous"])

    def test_empty_diff_pass_is_not_vacuous(self):
        report = qg.build_report("B", "H", "loaded", [], [], [],
                                 changed_files=0)
        self.assertFalse(report["summary"]["vacuous"])


# --------------------------------------------------------------------------
# main() / run_gate — exit codes, disabled gate (git mocked or real)
# --------------------------------------------------------------------------

class TestMainDisabledGate(unittest.TestCase):
    def test_disabled_gate_short_circuits_exit_zero(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"enabled": False}, fh)
            path = fh.name
        self.addCleanup(os.unlink, path)
        with mock.patch("sys.stdout") as out:
            rc = qg.main(["--config", path, "--base", "HEAD~1"])
        self.assertEqual(rc, 0)
        printed = "".join(c.args[0] for c in out.write.call_args_list if c.args)
        self.assertIn("gate disabled", printed)

    def test_git_failure_exits_two(self):
        with mock.patch("quality_gate.git_changed_ranges",
                        side_effect=qg.GateError("bad ref")), \
             mock.patch("sys.stderr"):
            rc = qg.main(["--base", "nope"])
        self.assertEqual(rc, 2)


class TestRunGateExitCodes(unittest.TestCase):
    """Drive run_gate with git + backends mocked so a failing metric yields the
    report (main maps it to exit 1) and a clean one yields pass."""

    def _args(self, **over):
        ns = mock.Mock()
        ns.config = None
        ns.base = "BASE"
        ns.head = "HEAD"
        ns.repo_dir = "."
        ns.coverage = None
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    def test_failing_metric_makes_main_return_one(self):
        # One changed file whose sole function is far over method_lines.
        long_body = "def big():\n" + "\n".join(
            f"    x{i} = {i}" for i in range(60))
        with tempfile.TemporaryDirectory() as d:
            Path(os.path.join(d, "big.py")).write_text(long_body + "\n")
            with mock.patch("quality_gate.git_changed_ranges",
                            return_value={"big.py": [(1, 61)]}), \
                 mock.patch("quality_gate._lizard_available",
                            return_value=False), \
                 mock.patch("quality_gate._radon_available",
                            return_value=False), \
                 mock.patch("sys.stdout"):
                rc = qg.main(["--base", "BASE", "--repo-dir", d])
        self.assertEqual(rc, 1)

    def test_clean_change_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            Path(os.path.join(d, "ok.py")).write_text(
                "def tiny(a):\n    return a\n")
            with mock.patch("quality_gate.git_changed_ranges",
                            return_value={"ok.py": [(1, 2)]}), \
                 mock.patch("quality_gate._lizard_available",
                            return_value=False), \
                 mock.patch("quality_gate._radon_available",
                            return_value=False), \
                 mock.patch("sys.stdout"):
                rc = qg.main(["--base", "BASE", "--repo-dir", d])
        self.assertEqual(rc, 0)


class TestEndToEndRealGit(unittest.TestCase):
    """Exercises the full git -> parse_diff -> builtin measure -> report path
    against a REAL throwaway repo (no git mock), so the diff-parsing and
    changed-range intersection are validated end-to-end."""

    def _git(self, *args):
        subprocess.run(["git", *args], cwd=self._tmp, check=True,
                       capture_output=True, text=True)

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="quality_gate_realgit_")
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "Test")
        Path(self._tmp, "m.py").write_text("def a():\n    return 1\n")
        self._git("add", "m.py")
        self._git("commit", "-q", "-m", "base")
        # Add an over-complex function in the second commit.
        Path(self._tmp, "m.py").write_text(
            "def a():\n    return 1\n\n"
            "def b(p, q, r, s, t):\n"
            "    if p:\n"
            "        if q:\n"
            "            if r:\n"
            "                if s:\n"
            "                    return t\n"
            "    return 0\n"
        )
        self._git("commit", "-q", "-am", "add b")

    def test_reports_changed_function_over_thresholds(self):
        with mock.patch("sys.stdout") as out:
            rc = qg.main(["--base", "HEAD~1", "--repo-dir", self._tmp])
        printed = "".join(c.args[0] for c in out.write.call_args_list if c.args)
        report = json.loads(printed)
        funcs = {f["function"] for f in report["findings"]}
        self.assertIn("b", funcs)          # the changed function is measured
        self.assertNotIn("a", funcs)       # the unchanged function is not
        # parameter_count 5 > 4 and nesting_depth 4 > 3 -> failures -> exit 1
        self.assertEqual(rc, 1)
        self.assertFalse(report["summary"]["pass"])
        self.assertTrue(report["summary"]["failures"])


# --------------------------------------------------------------------------
# Differential harness — masked versus raw over the whole plugin tree
# --------------------------------------------------------------------------
# The mask is a measurement change to a blocking control, so it is pinned
# against the measurement it replaces over real source rather than fixtures
# alone: every .py, .js and .mjs file under the plugin root is measured twice,
# once through the mask and once through the identity stand-in that reproduces
# the pre-mask behaviour. Those three suffixes were the only heuristic-readable
# ones present in the tree at the time of writing; a source file in one of the
# other extensions _EXT_LANG covers would not be walked by this harness.

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCANNED_SUFFIXES = (".py", ".js", ".mjs")

# The mask is allowed to lower these two. The other three are measured on raw
# text, so they must come back identical, as must the function's span.
LOWERABLE_METRICS = ("cyclomatic_complexity", "cognitive_complexity")
UNCHANGED_METRICS = ("nesting_depth", "method_lines", "parameter_count")


def scanned_sources():
    """Every .py, .js and .mjs file under the plugin root, sorted. Walks the
    real tree, so it is not PURE."""
    found = []
    for path in sorted(PLUGIN_ROOT.rglob("*")):
        if path.suffix in SCANNED_SUFFIXES and path.is_file():
            found.append(path)
    return found


WORKFLOW_JS = PLUGIN_ROOT / "workflows" / "slice-wave.workflow.js"


class TestCbraceMaskOverTheRealWorkflow(unittest.TestCase):
    """The brace-language mask measured against the file that motivated it:
    directions plus a floor under each masked value, so a regression that
    masked MORE than it should also fails."""

    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW_JS.read_text(encoding="utf-8")

    def analyze(self, source):
        findings, _ = qg.analyze_builtin(
            str(WORKFLOW_JS), source, [(1, len(source.splitlines()))])
        return {f["function"]: f for f in findings}

    def analyze_unmasked(self, source):
        with mock.patch.object(qg, "_strip_for_scan", unmasked):
            return self.analyze(source)

    def check_comes_down(self, name, new, old, floor):
        """One function's masked-versus-raw move: cognitive strictly down but
        no lower than the value measured as this pin landed, and cyclomatic
        never up. The floor is the upper bound on how much may be masked."""
        got = new[name]["metrics"]
        was = old[name]["metrics"]
        self.assertLess(
            got["cognitive_complexity"], was["cognitive_complexity"])
        self.assertGreaterEqual(got["cognitive_complexity"], floor)
        self.assertLessEqual(
            got["cyclomatic_complexity"], was["cyclomatic_complexity"])

    def check_masks_cleanly(self, path):
        text = path.read_text(encoding="utf-8")
        self.assertIsNotNone(
            qg._mask_cbrace_literals(text), msg=str(path))

    def test_the_mask_does_not_blank_the_file(self):
        # The guard against the failure mode a strings-only scanner produces
        # here: an apostrophe inside a line comment opens a literal that can
        # never close, _mask_cbrace_literals returns None, and the whole file
        # reverts to today's over-count. Function signatures live in code,
        # never inside a literal, so a working mask must also yield the
        # identical function list.
        masked = qg._mask_cbrace_literals(self.source)
        self.assertIsNotNone(masked)
        raw_funcs = qg._extract_functions_cbrace(self.source.splitlines())
        masked_funcs = qg._extract_functions_cbrace(masked.splitlines())
        self.assertEqual(masked_funcs, raw_funcs)
        self.assertGreater(len(raw_funcs), 60)

    def test_the_three_motivating_functions_all_come_down(self):
        new = self.analyze(self.source)
        old = self.analyze_unmasked(self.source)
        self.check_comes_down("globToRe", new, old, 17)
        self.check_comes_down("stageFixLoop", new, old, 13)
        self.check_comes_down("runSliceError", new, old, 12)

    def test_stage_fix_loop_gains_real_headroom(self):
        # It measures cognitive EXACTLY at the threshold before the mask and
        # passes only because the check is value <= threshold, so it is the
        # live instance this change rescues.
        limit = qg.DEFAULT_THRESHOLDS["cognitive_complexity"]
        old = self.analyze_unmasked(self.source)["stageFixLoop"]
        new = self.analyze(self.source)["stageFixLoop"]
        self.assertEqual(old["metrics"]["cognitive_complexity"], limit)
        self.assertLess(new["metrics"]["cognitive_complexity"], limit)

    def test_the_mask_does_not_rescue_glob_to_re(self):
        # Honest limit, pinned: the miscount inflates globToRe, it does not
        # create the violation. The function is genuinely over threshold
        # before and after.
        limit = qg.DEFAULT_THRESHOLDS["cognitive_complexity"]
        new = self.analyze(self.source)["globToRe"]
        self.assertGreater(new["metrics"]["cognitive_complexity"], limit)

    def test_the_mask_succeeds_on_every_brace_source_in_the_tree(self):
        # Named for what it proves and no more: the mask closes every
        # construct it recognises in every brace source here, so no file
        # silently falls back to raw counts. It is NOT a proof about regex
        # literals -- a regex holding an even number of quotes masks cleanly
        # and this still passes. The regex residual is backed by the pasted
        # grep in the slice report instead.
        brace = [p for p in scanned_sources() if p.suffix != ".py"]
        self.assertGreater(len(brace), 0)
        for path in brace:
            self.check_masks_cleanly(path)


class TestDifferentialAgainstRawScan(unittest.TestCase):
    """The mask may only ever LOWER a complexity count, and it may never move a
    function's span, its nesting depth, its length or its parameter count.
    Measured over the plugin tree's own source, masked against raw."""

    def analyze(self, path, source):
        findings, _ = qg.analyze_builtin(
            str(path), source, [(1, len(source.splitlines()))])
        return {(f["function"], f["line_start"]): f for f in findings}

    def analyze_unmasked(self, path, source):
        with mock.patch.object(qg, "_strip_for_scan", unmasked):
            return self.analyze(path, source)

    def assertNoRegression(self, got, was, where):
        for name in LOWERABLE_METRICS:
            self.assertLessEqual(
                got["metrics"][name], was["metrics"][name], msg=where)
        for name in UNCHANGED_METRICS:
            self.assertEqual(
                got["metrics"][name], was["metrics"][name], msg=where)
        self.assertEqual(
            (got["line_start"], got["line_end"]),
            (was["line_start"], was["line_end"]), msg=where)

    def measure_tree(self):
        """Every scanned file measured twice, as (where, masked, unmasked)
        triples of one function's findings. The two measurements must cover the
        same set of functions, so that is asserted here."""
        pairs = []
        for path in scanned_sources():
            source = path.read_text(encoding="utf-8")
            new = self.analyze(path, source)
            old = self.analyze_unmasked(path, source)
            self.assertEqual(sorted(new), sorted(old), msg=str(path))
            for key, got in new.items():
                pairs.append(("%s %s" % (path, key), got, old[key]))
        return pairs

    def test_the_plugin_tree_is_actually_being_scanned(self):
        paths = scanned_sources()
        self.assertGreaterEqual(len(paths), 26)
        suffixes = {path.suffix for path in paths}
        self.assertIn(".py", suffixes)
        self.assertTrue(".js" in suffixes or ".mjs" in suffixes)

    def test_no_function_gets_more_complex_and_no_span_moves(self):
        pairs = self.measure_tree()
        for where, got, was in pairs:
            self.assertNoRegression(got, was, where)
        # The tree measured well over a thousand functions at the time this
        # harness was written; a collapse to a handful would mean the walk
        # stopped finding files rather than that the mask is safe.
        self.assertGreater(len(pairs), 1000)

    def test_the_mask_measurably_lowers_something(self):
        # A harness that would pass on a no-op mask proves nothing, so pin that
        # the mask actually moves numbers somewhere in the tree.
        moved = [where for where, got, was in self.measure_tree()
                 if got["metrics"] != was["metrics"]]
        self.assertGreater(len(moved), 100)

    def test_a_brace_language_file_is_measurably_lowered(self):
        # The tree-wide "something moved" test above would pass on a mask
        # that only ever touched python, so pin the brace-language half
        # separately.
        moved = []
        for where, got, was in self.measure_tree():
            brace = (".js " in where) or (".mjs " in where)
            if brace and got["metrics"] != was["metrics"]:
                moved.append(where)
        self.assertGreater(len(moved), 10)


if __name__ == "__main__":
    unittest.main()
