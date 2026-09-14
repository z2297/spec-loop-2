#!/usr/bin/env python3
"""Unit tests for the pure ADO-intake logic (standard library only).

Usage:
    python3 -m unittest test_ado_intake
"""

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ado_intake as intake  # noqa: E402

TS = "2026-09-14T00:00:00Z"


class TestTheRendererIsPure(unittest.TestCase):
    """No network, no clock, no filesystem, no subprocess -- the property
    that makes this module testable at all."""

    FORBIDDEN = ("import urllib", "import os", "import subprocess",
                 "import datetime", "import time", "import socket",
                 "open(", "write_text(")

    def source(self):
        return Path(intake.__file__).read_text(encoding="utf-8")

    def test_no_side_effecting_import_or_call_appears(self):
        src = self.source()
        for bad in self.FORBIDDEN:
            with self.subTest(bad=bad):
                self.assertNotIn(bad, src)

    def test_no_jira_or_pr_resolver_coupling(self):
        src = self.source()
        for bad in ("jira_intake", "jira_client", "pr_resolver"):
            with self.subTest(bad=bad):
                self.assertNotIn("import " + bad, src)


class TestWorkItemIdValidation(unittest.TestCase):
    """The id reaches a filesystem path and a hash, so a permissive id is a
    traversal bug, not a formatting nit."""

    def test_a_well_formed_id_is_returned_unchanged(self):
        self.assertEqual(intake.validate_work_item_id("1234"), "1234")

    def test_a_traversal_or_typed_id_is_refused(self):
        bad = ("../1", "1/../..", "1 ", "1\n", "", "0" * 11, "12a",
               "-1", 1234, None)
        for value in bad:
            with self.subTest(value=value), \
                    self.assertRaises(intake.IntakeUsageError):
                intake.validate_work_item_id(value)


class TestProjectNameIsRefusedNotRewritten(unittest.TestCase):
    """A project name lands in YAML front matter and in a slug. A control
    character or line break is refused outright (jira_intake's
    _errors_for_id_newline idiom), because a raw newline inside a quoted
    scalar can forge the closing front-matter delimiter."""

    def test_a_permissive_real_world_name_is_accepted(self):
        for good in ("My Team – Platform", "Contoso.Web", "プロ"):
            with self.subTest(good=good):
                self.assertEqual(intake.validate_project_name(good), good)

    def test_a_control_character_or_break_is_refused(self):
        for bad in ("a\nb", "a\rb", "a\tb", "a\x00b", "", "   ", 7, None):
            with self.subTest(bad=bad), \
                    self.assertRaises(intake.IntakeUsageError):
                intake.validate_project_name(bad)

    def test_an_org_with_a_path_segment_is_refused(self):
        for bad in ("../org", "org/x", "", "org name", None):
            with self.subTest(bad=bad), \
                    self.assertRaises(intake.IntakeUsageError):
                intake.validate_org(bad)
