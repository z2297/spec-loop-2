"""Unit tests for measure_coverage.py's __main__-entry-shim resolver and manifest.

Split out of ``test_measure_coverage.py`` (which keeps the executable-line,
path-key, OMIT-parsing and threshold tests) to keep each test module a
manageable size. Covers ``resolve_main_shim`` and its two extracted helpers
directly, and separately asserts that the shipped ``coverage_omit.txt``
manifest — parsed and resolved through the real code paths, never a fixture
copy — names every target's shim symbolically and resolves to a block of the
size pinned by SHIPPED_SHIM_LINES in this module.

Usage: python3 -m unittest scripts.test_measure_coverage_manifest
       (or) python3 scripts/test_measure_coverage_manifest.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure_coverage as mc  # noqa: E402

# Every shipped target's entry shim is a guard header plus a single-line body, so the
# resolved omission is exactly this many lines. One pin covers all thirteen targets:
# raising it relaxes every target at once, not just the one that grew.
SHIPPED_SHIM_LINES = 2


class ResolveMainShimTests(unittest.TestCase):
    def test_resolves_header_and_sys_exit_body(self):
        src = "a = 1\nif __name__ == \"__main__\":\n    sys.exit(main())\n"
        self.assertEqual(mc.resolve_main_shim(src, "synthetic.py"), {2, 3})

    def test_resolves_a_raise_systemexit_body(self):
        src = "a = 1\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n"
        self.assertEqual(mc.resolve_main_shim(src, "synthetic.py"), {2, 3})

    def test_tolerates_a_pragma_comment_on_the_header(self):
        src = "if __name__ == '__main__':  # pragma: no cover\n    sys.exit(main())\n"
        self.assertEqual(mc.resolve_main_shim(src, "synthetic.py"), {1, 2})

    def test_position_moves_with_the_file(self):
        src = "\n" * 40 + "if __name__ == \"__main__\":\n    sys.exit(main())\n"
        self.assertEqual(mc.resolve_main_shim(src, "synthetic.py"), {41, 42})

    def test_absent_shim_raises(self):
        with self.assertRaises(ValueError):
            mc.resolve_main_shim("a = 1\n", "synthetic.py")

    def test_two_shims_raise(self):
        src = ("if __name__ == \"__main__\":\n    sys.exit(main())\n"
               "if __name__ == \"__main__\":\n    sys.exit(main())\n")
        with self.assertRaises(ValueError):
            mc.resolve_main_shim(src, "synthetic.py")

    def test_oversized_block_raises(self):
        body = "".join("    x = %d\n" % n for n in range(mc.MAX_SHIM_LINES + 2))
        src = "if __name__ == \"__main__\":\n" + body
        with self.assertRaises(ValueError):
            mc.resolve_main_shim(src, "synthetic.py")

    def test_sole_shim_header_reports_the_headers_own_line(self):
        src = "\n" * 12 + "if __name__ == \"__main__\":\n    sys.exit(main())\n"
        self.assertEqual(mc._sole_shim_header(src.splitlines(), "synthetic.py"), 13)

    def test_guarded_block_stops_at_the_next_column_zero_line(self):
        lines = ["if __name__ == \"__main__\":", "    sys.exit(main())", "",
                 "TRAILER = 1"]
        self.assertEqual(mc._guarded_block(lines, 1), {1, 2})

    def test_every_manifest_target_resolves_against_its_real_source(self):
        for relpath in mc.TARGET_FILES:
            source = mc._target_source_path(relpath).read_text()
            resolved = mc.resolve_main_shim(source, relpath)
            self.assertTrue(resolved, relpath)
            self.assertLessEqual(max(resolved), source.count("\n") + 1, relpath)


class ManifestIntegrityTests(unittest.TestCase):
    """The shipped manifest, parsed and resolved by the real code paths."""

    def setUp(self):
        self.omit = mc.parse_omit(mc.OMIT_FILE.read_text())

    def test_every_target_names_its_shim_symbolically(self):
        for relpath in mc.TARGET_FILES:
            self.assertIn(relpath, self.omit)
            self.assertTrue(self.omit[relpath].main_shim, relpath)
            self.assertEqual(self.omit[relpath].lines, set(), relpath)

    def test_no_manifest_key_is_outside_the_target_set(self):
        self.assertEqual(set(self.omit) - set(mc.TARGET_FILES), set())

    def test_each_resolved_omission_is_the_pinned_block_size(self):
        """The resolved block stays at its pinned size, so it cannot absorb code.

        This is the guard that can fail: a statement added beneath a target's
        entry guard grows the resolved block, the count stops matching
        SHIPPED_SHIM_LINES, and the pinned size must be deliberately raised in
        this module to go green again. The companion assertLess is a pin too,
        not a check - it restates that the shipped size sits under the resolver
        cap and moves only on a source edit.
        """
        self.assertLess(SHIPPED_SHIM_LINES, mc.MAX_SHIM_LINES)
        for relpath, spec in self.omit.items():
            source = mc._target_source_path(relpath).read_text()
            resolved = mc.resolve_omit(spec, source, relpath)
            self.assertEqual(len(resolved), SHIPPED_SHIM_LINES, relpath)

    def test_each_resolved_omission_passes_validate_omit(self):
        for relpath, spec in self.omit.items():
            source = mc._target_source_path(relpath).read_text()
            resolved = mc.resolve_omit(spec, source, relpath)
            target = mc.FileLines(
                relpath, mc.executable_lines(source, relpath),
                source.count("\n") + 1,
            )
            mc.validate_omit(target, resolved)


if __name__ == "__main__":
    unittest.main()
