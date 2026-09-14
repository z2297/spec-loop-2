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


def make_refinement(**over):
    """A minimal valid refinement dict; keyword args override one key."""
    base = {
        "description": "Add a widget toggle to the settings pane.",
        "acceptance_criteria": ["Toggle persists across reload."],
        "risks": [{"id": "R1", "risk": "No migration for existing rows.",
                   "severity": "high"}],
        "gaps": [{"id": "G1", "question": "Which roles see the toggle?",
                  "impact": "high", "blocking": True}],
        "injection_findings": [],
        "answers": {"G1": {"answer": "Admins only.",
                           "logged_as": "decision"}},
    }
    base.update(over)
    return base


class TestRefinementValidation(unittest.TestCase):
    def test_a_minimal_refinement_is_valid(self):
        self.assertEqual(intake.validate_refinement(make_refinement()), [])

    def test_a_missing_key_is_reported_by_name(self):
        bad = make_refinement()
        del bad["risks"]
        self.assertEqual(intake.validate_refinement(bad),
                         ["missing required key: risks"])

    def test_a_non_object_refinement_is_reported(self):
        self.assertEqual(intake.validate_refinement(["x"]),
                         ["refinement must be a JSON object"])

    def test_a_bad_impact_severity_and_blocking_are_each_reported(self):
        bad = make_refinement(
            gaps=[{"id": "G1", "question": "q", "impact": "urgent",
                   "blocking": "yes"}],
            risks=[{"id": "R1", "risk": "r", "severity": "fatal"}],
            answers={})
        errors = intake.validate_refinement(bad)
        self.assertIn("gaps[0].impact must be one of high|medium|low", errors)
        self.assertIn("gaps[0].blocking must be a boolean", errors)
        self.assertIn("risks[0].severity must be one of high|medium|low",
                      errors)

    def test_a_newline_in_an_id_is_refused(self):
        bad = make_refinement(
            gaps=[{"id": "G\n1", "question": "q", "impact": "low",
                   "blocking": False}], answers={})
        self.assertIn("gaps[0].id must not contain a newline",
                      intake.validate_refinement(bad))

    def test_a_duplicate_gap_id_makes_an_answer_unattributable(self):
        gap = {"id": "G1", "question": "q", "impact": "low",
               "blocking": False}
        bad = make_refinement(gaps=[gap, dict(gap)], answers={})
        self.assertIn("gaps have duplicate id: G1",
                      intake.validate_refinement(bad))

    def test_an_answer_with_no_matching_gap_is_reported(self):
        bad = make_refinement(
            answers={"G9": {"answer": None, "logged_as": "open-question"}})
        self.assertIn("answers has no matching gap for id G9",
                      intake.validate_refinement(bad))

    def test_a_bad_logged_as_is_reported(self):
        bad = make_refinement(answers={"G1": {"answer": "a",
                                              "logged_as": "note"}})
        self.assertIn(
            "answers[G1].logged_as must be one of decision|open-question",
            intake.validate_refinement(bad))


class TestGapRanking(unittest.TestCase):
    def test_blocking_then_impact_then_id(self):
        gaps = [
            {"id": "G3", "impact": "high", "blocking": False},
            {"id": "G1", "impact": "low", "blocking": True},
            {"id": "G2", "impact": "high", "blocking": True},
            {"id": "G0", "impact": "high", "blocking": False},
        ]
        self.assertEqual([g["id"] for g in intake.rank_gaps(gaps)],
                         ["G2", "G1", "G0", "G3"])

    def test_ranking_does_not_mutate_the_input(self):
        gaps = [{"id": "G2", "impact": "low", "blocking": False},
                {"id": "G1", "impact": "high", "blocking": True}]
        intake.rank_gaps(gaps)
        self.assertEqual([g["id"] for g in gaps], ["G2", "G1"])


def make_record(**over):
    """A minimal valid ADO record dict; keyword args override one key."""
    base = {
        "org": "contoso",
        "project": "My Team – Platform",
        "id": "1234",
        "web_url": "https://dev.azure.com/contoso/_workitems/edit/1234",
        "title": "Widget toggle",
        "description": "Users want a toggle.",
        "acceptance_criteria": "Toggle persists.",
        "acceptance_criteria_source": "field",
        "repro_steps": "",
        "state": "Active",
        "work_item_type": "User Story",
        "comments": [],
    }
    base.update(over)
    return base


class TestRecordValidation(unittest.TestCase):
    """The record file is authored by the calling model rather than piped
    straight from ado_client.py, so its shape is a contract to check."""

    def test_a_minimal_record_is_valid(self):
        self.assertEqual(intake.validate_record(make_record()), [])

    def test_an_unknown_extra_key_is_tolerated(self):
        self.assertEqual(
            intake.validate_record(make_record(rendered_text="<b>x</b>")), [])

    def test_a_missing_key_is_reported_by_name(self):
        bad = make_record()
        del bad["repro_steps"]
        self.assertEqual(intake.validate_record(bad),
                         ["record is missing required key: repro_steps"])

    def test_a_none_scalar_is_reported_not_rendered(self):
        self.assertIn("record key title must be a string",
                      intake.validate_record(make_record(title=None)))

    def test_comments_must_be_a_list(self):
        self.assertIn("record key comments must be a list",
                      intake.validate_record(make_record(comments={})))

    def test_an_empty_triple_field_is_a_half_resolve(self):
        for field in ("org", "project", "id"):
            with self.subTest(field=field):
                self.assertIn(
                    "record key %s must not be empty" % field,
                    intake.validate_record(make_record(**{field: ""})))

    def test_a_numeric_id_is_refused(self):
        self.assertIn("record key id must be a string",
                      intake.validate_record(make_record(id=1234)))

    def test_require_valid_record_raises_with_every_error_joined(self):
        with self.assertRaises(intake.IntakeError) as caught:
            intake._require_valid_record(make_record(title=None))
        self.assertIn("refusing to render from an invalid record",
                      str(caught.exception))

    def test_record_triple_is_the_validated_target(self):
        self.assertEqual(intake.record_triple(make_record()),
                         ("contoso", "My Team – Platform", "1234"))


class TestTheBodyCarriesNoActiveMarkup(unittest.TestCase):
    """BLOCKING: the ADO Add-comment body has no declarable format, so the
    ADF-text-node inertness the Jira lane got for free is gone. The body is
    escaped so it is inert under either interpretation. This module claims
    only that -- never that it controls how ADO stores or renders it."""

    def test_the_three_html_active_characters_are_escaped(self):
        escaped = intake.escape_for_comment("a & b < c > d")
        self.assertEqual(escaped, "a &amp; b &lt; c &gt; d")

    def test_escaping_is_ampersand_first_so_it_is_not_double_applied(self):
        self.assertEqual(intake.escape_for_comment("<x>"), "&lt;x&gt;")
        self.assertEqual(intake.escape_for_comment("&lt;"), "&amp;lt;")

    def test_a_script_tag_from_the_work_item_cannot_stay_active(self):
        body = intake.render_comment(
            TRIPLE, "understanding",
            intake.escape_for_comment("<script>alert(1)</script>"), TS)
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)


class TestMarkerIsScopedToTheTriple(unittest.TestCase):
    """A marker over the bare id is identical for work item 1234 in two
    different orgs."""

    def test_the_marker_matches_the_pinned_shape(self):
        marker = intake.comment_marker(TRIPLE, "understanding", "p")
        self.assertRegex(marker, r"^" + intake.MARKER_RE.pattern + r"$")

    def test_the_bare_digest_is_extractable_for_the_two_tier_match(self):
        marker = intake.comment_marker(TRIPLE, "understanding", "p")
        digests = intake.MARKER_DIGEST_RE.findall(marker)
        self.assertEqual(len(digests), 1)
        self.assertIn(digests[0], marker)

    def test_the_marker_contains_no_escapable_character(self):
        marker = intake.comment_marker(TRIPLE, "decision", "p")
        for char in "&<>\"'*_`":
            with self.subTest(char=char):
                self.assertNotIn(char, marker)
        self.assertEqual(intake.escape_for_comment(marker), marker)

    def test_a_different_org_yields_a_different_marker(self):
        a = intake.comment_marker(("orga", "P", "1234"), "decision", "p")
        b = intake.comment_marker(("orgb", "P", "1234"), "decision", "p")
        self.assertNotEqual(a, b)

    def test_a_different_project_yields_a_different_marker(self):
        a = intake.comment_marker(("org", "PA", "1234"), "decision", "p")
        b = intake.comment_marker(("org", "PB", "1234"), "decision", "p")
        self.assertNotEqual(a, b)

    def test_the_timestamp_is_not_hashed(self):
        early = intake.render_comment(
            TRIPLE, "decision", "p", "2026-01-01T00:00:00Z")
        late = intake.render_comment(
            TRIPLE, "decision", "p", "2027-01-01T00:00:00Z")
        self.assertNotEqual(early, late)
        self.assertEqual(
            intake.MARKER_RE.findall(early),
            intake.MARKER_RE.findall(late))

    def test_the_payload_is_hashed(self):
        a = intake.comment_marker(TRIPLE, "decision", "Ship it.")
        b = intake.comment_marker(TRIPLE, "decision", "Ship it")
        self.assertNotEqual(a, b)

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(intake.IntakeUsageError):
            intake.comment_marker(TRIPLE, "gossip", "p")

    def test_a_bad_triple_never_yields_a_marker(self):
        with self.assertRaises(intake.IntakeUsageError):
            intake.comment_marker(("contoso", "P", "../1"), "decision", "p")


class TestCommentBodyIsBlankLineSeparatedBlocks(unittest.TestCase):
    """BLOCKING: ADO cannot be told the body's format. Under markdown a
    single newline is not a line break, so a '\\n'-joined body collapses to
    one run-on paragraph."""

    def test_the_marker_is_alone_on_line_one(self):
        body = intake.render_comment(TRIPLE, "understanding", "p", TS)
        first = body.split("\n")[0]
        self.assertRegex(first, r"^" + intake.MARKER_RE.pattern + r"$")

    def test_every_block_is_separated_by_a_blank_line(self):
        body = intake.render_comment(
            TRIPLE, "understanding", "alpha\n\nbeta", TS)
        blocks = body.split("\n\n")
        self.assertGreaterEqual(len(blocks), 4)
        for block in blocks:
            with self.subTest(block=block):
                self.assertTrue(block.strip())

    def test_the_body_names_the_heading_the_timestamp_and_the_payload(self):
        body = intake.render_comment(TRIPLE, "decision", "the payload", TS)
        self.assertIn(intake.COMMENT_HEADINGS["decision"], body)
        self.assertIn(TS, body)
        self.assertIn("the payload", body)
        self.assertIn("/spec-loop:ado-intake", body)

    def test_a_marker_extracted_from_a_wrapped_body_still_matches(self):
        body = intake.render_comment(TRIPLE, "decision", "p", TS)
        wrapped = "<div>%s</div>" % body.replace("\n", "<br>\n")
        self.assertEqual(
            set(intake.MARKER_RE.findall(wrapped)),
            set(intake.MARKER_RE.findall(body)))


class TestCommentBodiesAreBuiltNotPosted(unittest.TestCase):
    def test_the_understanding_comment_comes_first(self):
        built = intake.build_comment_bodies(
            make_record(), make_refinement(), TS)
        self.assertEqual(built[0]["kind"], "understanding")
        self.assertIsNone(built[0]["gap_id"])

    def test_each_entry_has_exactly_the_pinned_keys(self):
        for entry in intake.build_comment_bodies(
                make_record(), make_refinement(), TS):
            self.assertEqual(set(entry),
                             {"kind", "gap_id", "marker", "body"})
            self.assertTrue(entry["body"].startswith(entry["marker"]))

    def test_an_answered_gap_is_a_decision(self):
        built = intake.build_comment_bodies(
            make_record(), make_refinement(), TS)
        gap_entry = built[1]
        self.assertEqual(gap_entry["kind"], "decision")
        self.assertEqual(gap_entry["gap_id"], "G1")
        self.assertIn("Admins only.", gap_entry["body"])

    def test_an_unanswered_gap_is_an_open_question(self):
        refinement = make_refinement(
            answers={"G1": {"answer": None,
                            "logged_as": "open-question"}})
        built = intake.build_comment_bodies(make_record(), refinement, TS)
        self.assertEqual(built[1]["kind"], "open-question")
        self.assertIn("Open question (G1", built[1]["body"])

    def test_a_decision_logged_as_with_no_answer_degrades_to_open_question(self):
        refinement = make_refinement(
            answers={"G1": {"answer": None, "logged_as": "decision"}})
        built = intake.build_comment_bodies(make_record(), refinement, TS)
        self.assertEqual(built[1]["kind"], "open-question")

    def test_untrusted_work_item_text_reaches_the_body_escaped(self):
        refinement = make_refinement(description="<b>hi</b> & bye")
        built = intake.build_comment_bodies(make_record(), refinement, TS)
        self.assertNotIn("<b>", built[0]["body"])
        self.assertIn("&lt;b&gt;hi&lt;/b&gt; &amp; bye", built[0]["body"])

    def test_an_invalid_refinement_refuses_a_partial_render(self):
        with self.assertRaises(intake.IntakeError):
            intake.build_comment_bodies(
                make_record(), make_refinement(description=""), TS)

    def test_an_invalid_record_refuses_a_partial_render(self):
        with self.assertRaises(intake.IntakeError):
            intake.build_comment_bodies(
                make_record(project=""), make_refinement(), TS)

    def test_every_marker_in_one_batch_is_distinct(self):
        refinement = make_refinement(
            gaps=[{"id": "G1", "question": "same?", "impact": "low",
                   "blocking": False},
                  {"id": "G2", "question": "same?", "impact": "low",
                   "blocking": False}],
            answers={})
        built = intake.build_comment_bodies(make_record(), refinement, TS)
        markers = [e["marker"] for e in built]
        self.assertEqual(len(markers), len(set(markers)))

    def test_a_duplicate_marker_batch_is_refused_before_anything_is_returned(self):
        entry = {"kind": "decision", "gap_id": "G1", "marker": "[m]",
                 "body": "b"}
        self.assertEqual(intake._duplicate_marker_errors([entry]), [])
        self.assertEqual(
            intake._duplicate_marker_errors([entry, dict(entry)]),
            ["two comments share the dedupe marker [m]"])


if __name__ == "__main__":
    unittest.main()
