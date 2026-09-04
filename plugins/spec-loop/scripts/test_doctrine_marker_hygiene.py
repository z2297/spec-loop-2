#!/usr/bin/env python3
"""Doctrine checks for spec-loop run-state marker hygiene.

The guard hooks key off on-disk markers under docs/spec-loop/<run-id>/:
.active, .done, .publish-choice, .paused, and .controller-session. A marker
that is COMMITTED arrives on every clone and every fresh worktree, which
turns the guard against the repo - a committed .active denies pushes and
main-branch commits forever, for everyone, in sessions that have no run at
all.

This happened: .active entered the index twice (commits 5de8f42 and
a413b93) and two runs' .done / .publish-choice markers rode in on the
feature merges 7fdd7e2 and e9460f8, while references/run-state-v2.md
already said .active is "never committed". Prose alone did not hold the
line, so this module pins it.

Honest limits: the tracking assertion shells out to `git ls-files` and is
skipped only when there is no .git entry at REPO_ROOT (a source tarball).
When git IS present it fails loudly rather than skipping, so the pin cannot
degrade into a silent no-op. The .gitignore assertions check literal
entries and the absence of a leading slash; they prove the patterns are
present and unanchored, not that git's matcher behaves as intended - that
part is covered by the tracking assertion, which is the property that
actually matters.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_doctrine_marker_hygiene.py'
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GITIGNORE = REPO_ROOT / ".gitignore"
RUN_STATE_MD = (
    Path(__file__).resolve().parents[1] / "references" / "run-state-v2.md"
)
MARKERS = (
    ".active",
    ".controller-session",
    ".done",
    ".paused",
    ".publish-choice",
)


def prose(path):
    """One file's text with every whitespace run collapsed to a space. (PURE)"""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def ignore_lines():
    """The non-blank, non-comment lines of .gitignore, stripped."""
    return [
        line.strip()
        for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def repo_has_git():
    """True when REPO_ROOT has a .git dir OR a .git file (linked worktree)."""
    return (REPO_ROOT / ".git").exists()


def git(*args):
    """Stripped stdout of a git command in REPO_ROOT. Raises on failure."""
    done = subprocess.run(
        ("git", "-C", str(REPO_ROOT)) + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if done.returncode != 0:
        raise RuntimeError(
            "git %s failed with exit %d: %s"
            % (" ".join(args), done.returncode, done.stderr.strip())
        )
    return done.stdout.strip()


class TestMarkersAreNotTracked(unittest.TestCase):
    """No run-state marker may be in the index, and all five are ignored."""

    def test_no_run_state_marker_is_tracked(self):
        if not repo_has_git():
            self.skipTest("no .git at repo root (source tarball)")
        listing = git("ls-files", "--", "docs/spec-loop")
        tracked = [
            path
            for path in listing.splitlines()
            if Path(path).name in MARKERS
        ]
        self.assertEqual(
            tracked,
            [],
            "these run-state markers are committed and will fire the guard "
            "on every checkout; remove them from the index only, leaving "
            "them on disk: %s" % tracked,
        )

    def test_every_marker_name_is_gitignored(self):
        lines = ignore_lines()
        for marker in MARKERS:
            self.assertIn(
                marker,
                lines,
                "%s is not a literal .gitignore entry, so the next run can "
                "commit it again" % marker,
            )

    def test_marker_ignore_patterns_are_unanchored(self):
        for line in ignore_lines():
            for marker in MARKERS:
                if line.endswith(marker):
                    self.assertEqual(
                        line,
                        marker,
                        "%s must be matched at any depth, so its .gitignore "
                        "entry must be the bare name, not %r" % (marker, line),
                    )
