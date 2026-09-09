#!/usr/bin/env python3
"""Unit tests for the pure Jira-intake logic (standard library only).

Usage:
    python3 -m unittest test_jira_intake
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jira_intake as intake  # noqa: E402


class TestIssueKeyValidation(unittest.TestCase):
    """The key reaches a filesystem path and argv, so a permissive key is a
    traversal bug, not a formatting nit."""

    def test_a_well_formed_key_is_returned_unchanged(self):
        self.assertEqual(intake.validate_issue_key("ABC-123"), "ABC-123")

    def test_a_traversal_key_is_refused(self):
        for bad in ("../ABC-1", "ABC-1/../..", "abc-1", "ABC-1 ", "ABC-1\n",
                    "ABC-1;rm -rf /", "", "A-1"):
            with self.subTest(bad=bad):
                with self.assertRaises(intake.IntakeUsageError):
                    intake.validate_issue_key(bad)


class TestArtifactPathGuard(unittest.TestCase):
    """Sanitize-and-assert: the composed path must provably sit under the
    artifact root before any caller writes to it."""

    def test_the_path_is_under_the_artifact_root(self):
        self.assertEqual(intake.artifact_path("ABC-123", intake.ARTIFACT_ROOT),
                         ".spec-loop-jira/ABC-123/intake.md")

    def test_a_bad_key_never_yields_a_path(self):
        with self.assertRaises(intake.IntakeUsageError):
            intake.artifact_path("../../etc/passwd", intake.ARTIFACT_ROOT)

    def test_a_root_that_escapes_is_refused(self):
        for bad_root in ("../elsewhere", "/etc", ".spec-loop-jira/..", ""):
            with self.subTest(bad_root=bad_root):
                with self.assertRaises(intake.IntakeUsageError):
                    intake.artifact_path("ABC-123", bad_root)
