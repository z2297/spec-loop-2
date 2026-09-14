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


def assert_refused(case, call, value):
    """Assert `call(value)` raises IntakeUsageError, naming `value`.

    A module-level helper rather than a `with subTest(), assertRaises()`
    pair inside every loop: the paired form needs a continuation line that
    this repo's quality gate reads as real block nesting."""
    with case.subTest(value=value):
        with case.assertRaises(intake.IntakeUsageError):
            call(value)


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


TRIPLE = ("contoso", "My Team – Platform", "1234")


def path_for_triple(triple):
    """artifact_path for one triple under the default root. (test helper)"""
    return intake.artifact_path(triple, intake.ARTIFACT_ROOT)


def path_under_root(artifact_root):
    """artifact_path for TRIPLE under one root. (test helper)"""
    return intake.artifact_path(TRIPLE, artifact_root)


class TestProjectSlugIsWhitelistByConstruction(unittest.TestCase):
    """A regex permissive enough for real project names is too permissive to
    be a security control, so the name is slugged by a total lossy
    transform instead: '..', '/', '\\' and NUL are structurally
    unrepresentable rather than checked for."""

    def assert_path_safe(self, slug):
        """No separator, no '..', and no leading or trailing dot."""
        self.assertNotIn("/", slug)
        self.assertNotIn("\\", slug)
        self.assertNotIn("..", slug)
        self.assertFalse(slug.startswith("."))
        self.assertFalse(slug.endswith("."))

    def test_the_slug_is_lowercase_and_dash_collapsed(self):
        self.assertEqual(
            intake.project_slug("My Team – Platform"), "my-team-platform")

    def test_traversal_and_separators_cannot_be_represented(self):
        for name in ("a/b", "a\\b", "a..b", "a/../b", ".hidden", "a. "):
            with self.subTest(name=name):
                self.assert_path_safe(intake.project_slug(name))

    def test_the_slug_is_capped_in_length(self):
        self.assertLessEqual(
            len(intake.project_slug("x" * 200)), intake.PROJECT_MAX_SLUG)

    def test_the_cap_never_leaves_a_trailing_separator(self):
        self.assertEqual(intake.project_slug("x" * 47 + " tail"), "x" * 47)

    def test_a_name_that_slugs_away_entirely_is_refused(self):
        for name in ("...", "///", "––", "..", "../..", "./."):
            assert_refused(self, intake.project_slug, name)


class TestArtifactPathGuard(unittest.TestCase):
    """Sanitize-and-assert, plus the ADO-specific collision fix: work item
    42 exists in every project, so the project must be in the path."""

    def test_the_path_is_under_the_artifact_root(self):
        path = intake.artifact_path(TRIPLE, intake.ARTIFACT_ROOT)
        self.assertTrue(path.startswith(".spec-loop-ado/"))
        self.assertTrue(path.endswith("/1234/intake.md"))
        self.assertIn("my-team-platform-", path)

    def test_two_projects_that_slug_alike_do_not_collide(self):
        a = path_for_triple(("contoso", "Team/One", "42"))
        b = path_for_triple(("contoso", "Team One", "42"))
        self.assertNotEqual(a, b)

    def test_the_same_id_in_two_orgs_does_not_collide(self):
        a = path_for_triple(("orga", "Shared", "42"))
        b = path_for_triple(("orgb", "Shared", "42"))
        self.assertNotEqual(a, b)

    def test_the_path_is_deterministic(self):
        self.assertEqual(path_for_triple(TRIPLE), path_for_triple(TRIPLE))

    def test_a_bad_triple_never_yields_a_path(self):
        bad = (
            ("contoso", "Proj", "../../etc/passwd"),
            ("../org", "Proj", "1"),
            ("contoso", "Pro\nj", "1"),
            ("contoso", "Proj"),
            "contoso/Proj/1",
        )
        for triple in bad:
            assert_refused(self, path_for_triple, triple)

    def test_a_root_that_escapes_is_refused(self):
        for root in ("../elsewhere", "/etc", ".spec-loop-ado/..", ""):
            assert_refused(self, path_under_root, root)

    def test_a_dict_triple_is_accepted_and_validated(self):
        got = intake.validate_triple(
            {"org": "contoso", "project": "Proj", "id": "7"})
        self.assertEqual(got, ("contoso", "Proj", "7"))

    def test_a_dict_missing_a_triple_key_is_refused(self):
        assert_refused(self, intake.validate_triple, {"org": "contoso"})

    def test_the_target_dir_carries_the_slug_and_the_id(self):
        discriminated = path_for_triple(TRIPLE).split("/")[1]
        self.assertEqual(intake.target_dir(TRIPLE), discriminated + "/1234")
