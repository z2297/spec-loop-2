"""Tests for review_package.py — real git fixtures in tempdirs, stdlib only."""

import json
import os
import re
import subprocess
import tempfile
import unittest

import review_package


def git(repo, *argv):
    subprocess.run(
        ["git", "-C", repo, *argv], check=True, capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", self.repo]))
        git(self.repo, "init", "-b", "main")
        self._write("a.py", "def f():\n    return 1\n")
        git(self.repo, "add", "a.py")
        git(self.repo, "commit", "-m", "base")
        self.base = self._sha()
        self._write("a.py", "def f():\n    return 2\n\n\ndef g():\n    return 3\n")
        self._write("b.py", "X = 1\n")
        git(self.repo, "add", "a.py", "b.py")
        git(self.repo, "commit", "-m", "change")
        self.head = self._sha()

    def _write(self, name, content):
        with open(os.path.join(self.repo, name), "w") as fh:
            fh.write(content)

    def _sha(self):
        out = subprocess.run(["git", "-C", self.repo, "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def _run(self, **kw):
        out = os.path.join(self.repo, "pkg.md")
        rc = review_package.main(["--repo-dir", self.repo, "--base", self.base,
                                  "--head", self.head, "--out", out])
        self.assertEqual(rc, 0)
        with open(out) as fh:
            return fh.read()

    def test_package_sections(self):
        text = self._run()
        for section in ("## Commits", "## Files changed", "## Hunk index", "## Diff"):
            self.assertIn(section, text)
        self.assertIn("change", text)          # commit subject
        self.assertIn("def g():", text)        # diff content
        self.assertIn("-U5", text)             # default context noted

    def test_hunk_index_covers_changed_lines(self):
        text = self._run()
        block = re.search(r"```hunk-index\n(.*?)\n```", text, re.S).group(1)
        index = json.loads(block)
        self.assertIn("a.py", index)
        self.assertIn("b.py", index)
        # a.py line 2 changed and lines 3-5 added: some range must cover line 2
        self.assertTrue(any(lo <= 2 <= hi for lo, hi in index["a.py"]))
        # b.py is a new 1-line file
        self.assertTrue(any(lo <= 1 <= hi for lo, hi in index["b.py"]))

    def test_deleted_file_absent_from_index(self):
        git(self.repo, "rm", "b.py")
        git(self.repo, "commit", "-m", "delete b")
        self.head = self._sha()
        text = self._run()
        block = re.search(r"```hunk-index\n(.*?)\n```", text, re.S).group(1)
        self.assertNotIn("b.py", json.loads(block))

    def test_oversize_falls_back(self):
        big = "\n".join(f"LINE_{i} = {i}" for i in range(30000)) + "\n"
        self._write("big.py", big)
        git(self.repo, "add", "big.py")
        git(self.repo, "commit", "-m", "big")
        self.head = self._sha()
        text = self._run()
        self.assertLessEqual(len(text.encode()), review_package.MAX_BYTES)
        self.assertIn("## Hunk index", text)   # index survives every fallback

    def test_bad_ref_exits_2(self):
        rc = review_package.main(["--repo-dir", self.repo, "--base", "nope",
                                  "--head", self.head,
                                  "--out", os.path.join(self.repo, "x.md")])
        self.assertEqual(rc, 2)

    def test_atomic_and_named_out(self):
        out = os.path.join(self.repo, "packages", "s1-round1.md")
        rc = review_package.main(["--repo-dir", self.repo, "--base", self.base,
                                  "--head", self.head, "--out", out])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(out))
        self.assertFalse(os.path.exists(out + ".tmp"))


if __name__ == "__main__":
    unittest.main()
