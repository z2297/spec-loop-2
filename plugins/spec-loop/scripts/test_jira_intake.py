#!/usr/bin/env python3
"""Unit tests for the pure Jira-intake logic (standard library only).

Usage:
    python3 -m unittest test_jira_intake
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
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
        "answers": {"G1": {"answer": "Admins only.", "logged_as": "decision"}},
    }
    base.update(over)
    return base


class TestRefinementValidation(unittest.TestCase):
    """Hand-rolled validation returning error strings, per the repo rule."""

    def test_a_valid_refinement_has_no_errors(self):
        self.assertEqual(intake.validate_refinement(make_refinement()), [])

    def test_a_missing_key_is_reported_by_name(self):
        bad = make_refinement()
        del bad["gaps"]
        self.assertIn("gaps", " ".join(intake.validate_refinement(bad)))

    def test_a_wrongly_typed_description_is_reported(self):
        errors = intake.validate_refinement(make_refinement(description=42))
        self.assertTrue(any("description" in e for e in errors))

    def test_a_gap_missing_its_id_is_reported(self):
        bad = make_refinement(gaps=[{"question": "q", "impact": "high",
                                     "blocking": False}])
        self.assertTrue(any("id" in e for e in intake.validate_refinement(bad)))

    def test_an_unknown_impact_value_is_reported(self):
        bad = make_refinement(gaps=[{"id": "G1", "question": "q",
                                     "impact": "urgent", "blocking": False}])
        self.assertTrue(any("impact" in e for e in intake.validate_refinement(bad)))

    def test_an_unknown_logged_as_value_is_reported(self):
        bad = make_refinement(answers={"G1": {"answer": None,
                                              "logged_as": "email"}})
        self.assertTrue(any("logged_as" in e for e in intake.validate_refinement(bad)))

    def test_an_answer_for_an_unknown_gap_is_reported(self):
        bad = make_refinement(answers={"G9": {"answer": "x",
                                              "logged_as": "decision"}})
        self.assertTrue(any("G9" in e for e in intake.validate_refinement(bad)))


class TestGapRanking(unittest.TestCase):
    """The ranking decides the order of the single AskUserQuestion round, so
    it must be total and deterministic."""

    def test_blocking_gaps_come_before_non_blocking_ones(self):
        gaps = [{"id": "G2", "question": "q2", "impact": "high",
                 "blocking": False},
                {"id": "G1", "question": "q1", "impact": "low",
                 "blocking": True}]
        self.assertEqual([g["id"] for g in intake.rank_gaps(gaps)],
                         ["G1", "G2"])

    def test_within_a_blocking_class_impact_orders_them(self):
        gaps = [{"id": "G1", "question": "q", "impact": "low",
                 "blocking": False},
                {"id": "G2", "question": "q", "impact": "high",
                 "blocking": False},
                {"id": "G3", "question": "q", "impact": "medium",
                 "blocking": False}]
        self.assertEqual([g["id"] for g in intake.rank_gaps(gaps)],
                         ["G2", "G3", "G1"])

    def test_ties_break_on_id_and_the_input_is_not_mutated(self):
        gaps = [{"id": "G2", "question": "q", "impact": "high",
                 "blocking": True},
                {"id": "G1", "question": "q", "impact": "high",
                 "blocking": True}]
        original = [dict(g) for g in gaps]
        self.assertEqual([g["id"] for g in intake.rank_gaps(gaps)],
                         ["G1", "G2"])
        self.assertEqual(gaps, original)


def make_record(**over):
    """A minimal jira_client.py resolve record; keyword args override."""
    base = {"key": "ABC-123",
            "web_url": "https://example.atlassian.net/browse/ABC-123",
            "summary": "Widget toggle",
            "description": "Users want a toggle.",
            "acceptance_criteria": "Toggle persists.",
            "acceptance_criteria_source": "field",
            "status": "To Do",
            "issue_type": "Story",
            "comments": []}
    base.update(over)
    return base


class TestCommentMarker(unittest.TestCase):
    """j3 dedupes by reading this marker back off the card, so it must be
    stable across runs and must NOT contain the timestamp."""

    def test_the_marker_has_the_pinned_shape(self):
        marker = intake.comment_marker("ABC-123", "decision", "payload")
        self.assertTrue(marker.startswith("[spec-loop-intake:decision:"))
        self.assertTrue(marker.endswith("]"))
        self.assertEqual(len(marker.split(":")[2].rstrip("]")), 12)

    def test_the_marker_is_stable_for_the_same_payload(self):
        self.assertEqual(intake.comment_marker("ABC-123", "decision", "p"),
                         intake.comment_marker("ABC-123", "decision", "p"))

    def test_the_marker_changes_with_key_kind_or_payload(self):
        base = intake.comment_marker("ABC-123", "decision", "p")
        self.assertNotEqual(base, intake.comment_marker("ABC-124", "decision", "p"))
        self.assertNotEqual(base, intake.comment_marker("ABC-123", "open-question", "p"))
        self.assertNotEqual(base, intake.comment_marker("ABC-123", "decision", "q"))

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(intake.IntakeUsageError):
            intake.comment_marker("ABC-123", "transition", "p")


class TestRenderedComments(unittest.TestCase):
    """This slice RENDERS bodies and posts nothing; the bodies are the
    artifact j3 will later post unchanged."""

    def test_a_body_carries_its_marker_and_the_caller_supplied_timestamp(self):
        body = intake.render_comment("ABC-123", "decision", "Admins only.",
                                     "2026-09-09T00:00:00Z")
        self.assertIn(intake.comment_marker("ABC-123", "decision", "Admins only."),
                      body)
        self.assertIn("2026-09-09T00:00:00Z", body)
        self.assertIn("Admins only.", body)

    def test_the_timestamp_does_not_change_the_marker(self):
        early = intake.render_comment("ABC-123", "decision", "p", "2026-01-01T00:00:00Z")
        late = intake.render_comment("ABC-123", "decision", "p", "2026-12-31T00:00:00Z")
        marker = intake.comment_marker("ABC-123", "decision", "p")
        self.assertIn(marker, early)
        self.assertIn(marker, late)

    def test_one_understanding_comment_plus_one_per_gap(self):
        refinement = make_refinement(
            gaps=[{"id": "G1", "question": "Which roles?", "impact": "high",
                   "blocking": True},
                  {"id": "G2", "question": "What timezone?", "impact": "low",
                   "blocking": False}],
            answers={"G1": {"answer": "Admins only.", "logged_as": "decision"}})
        built = intake.build_comment_bodies(make_record(), refinement,
                                            "2026-09-09T00:00:00Z")
        self.assertEqual([c["kind"] for c in built],
                         ["understanding", "decision", "open-question"])
        self.assertEqual([c["gap_id"] for c in built], [None, "G1", "G2"])

    def test_an_unanswered_gap_becomes_an_open_question_carrying_the_question(self):
        refinement = make_refinement(answers={"G1": {"answer": None,
                                                     "logged_as": "open-question"}})
        built = intake.build_comment_bodies(make_record(), refinement,
                                            "2026-09-09T00:00:00Z")
        self.assertEqual(built[1]["kind"], "open-question")
        self.assertIn("Which roles see the toggle?", built[1]["body"])

    def test_the_understanding_body_carries_description_ac_and_risks(self):
        built = intake.build_comment_bodies(make_record(), make_refinement(),
                                            "2026-09-09T00:00:00Z")
        body = built[0]["body"]
        self.assertIn("Add a widget toggle to the settings pane.", body)
        self.assertIn("Toggle persists across reload.", body)
        self.assertIn("No migration for existing rows.", body)

    def test_an_invalid_refinement_is_refused_rather_than_half_rendered(self):
        with self.assertRaises(intake.IntakeError):
            intake.build_comment_bodies(make_record(), {"description": "x"},
                                        "2026-09-09T00:00:00Z")


class TestArtifactRendering(unittest.TestCase):
    """The artifact schema IS the command prose; this pins the field names a
    later reader (and the handoff) depends on."""

    def setUp(self):
        self.text = intake.render_artifact(make_record(), make_refinement(),
                                           "2026-09-09T00:00:00Z")

    def test_every_front_matter_field_is_present(self):
        for field in intake.ARTIFACT_FIELDS:
            with self.subTest(field=field):
                self.assertIn("%s:" % field, self.text)

    def test_the_front_matter_is_delimited(self):
        self.assertTrue(self.text.startswith("---\n"))
        self.assertEqual(self.text.count("\n---\n"), 1)

    def test_every_numbered_section_is_present_in_order(self):
        positions = [self.text.index(s) for s in intake.ARTIFACT_SECTIONS]
        self.assertEqual(positions, sorted(positions))

    def test_the_rendered_comment_bodies_are_embedded(self):
        for comment in intake.build_comment_bodies(
                make_record(), make_refinement(), "2026-09-09T00:00:00Z"):
            with self.subTest(kind=comment["kind"]):
                self.assertIn(comment["marker"], self.text)

    def test_the_counts_match_the_refinement(self):
        self.assertIn("gap_count: 1", self.text)
        self.assertIn("open_question_count: 0", self.text)

    def test_injection_findings_are_reported_in_section_six(self):
        text = intake.render_artifact(
            make_record(),
            make_refinement(injection_findings=["Card text asks the agent to "
                                                "ignore its instructions."]),
            "2026-09-09T00:00:00Z")
        tail = text[text.index("## 6. Untrusted-input findings"):]
        self.assertIn("ignore its instructions", tail)

    def test_an_invalid_refinement_is_refused(self):
        with self.assertRaises(intake.IntakeError):
            intake.render_artifact(make_record(), {"description": "x"},
                                   "2026-09-09T00:00:00Z")


class TestRenderCli(unittest.TestCase):
    """The command shells this CLI; its exit codes and stream choice must
    match jira_client.py so the command handles one idiom, not two."""

    def setUp(self):
        self.dirpath = tempfile.mkdtemp(prefix="jira-intake-test-")
        self.record_path = Path(self.dirpath) / "record.json"
        self.refinement_path = Path(self.dirpath) / "refinement.json"
        self.record_path.write_text(json.dumps(make_record()), encoding="utf-8")
        self.refinement_path.write_text(json.dumps(make_refinement()),
                                        encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.dirpath, ignore_errors=True)

    def run_cli(self, argv):
        """Run main() capturing stdout/stderr; returns (code, out, err)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = intake.main(argv)
        return code, out.getvalue(), err.getvalue()

    def base_argv(self):
        """The happy-path argv for `render`."""
        return ["render", "--record", str(self.record_path),
                "--refinement", str(self.refinement_path),
                "--ts", "2026-09-09T00:00:00Z"]

    def test_a_good_render_exits_zero_with_one_json_object(self):
        code, out, _ = self.run_cli(self.base_argv())
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["posted"])
        self.assertEqual(payload["artifact_path"],
                         ".spec-loop-jira/ABC-123/intake.md")
        self.assertIn("## 1. Refined description", payload["artifact"])
        self.assertEqual(payload["comments"][0]["kind"], "understanding")

    def test_an_invalid_refinement_is_a_contract_failure_on_stdout(self):
        self.refinement_path.write_text(json.dumps({"description": "x"}),
                                        encoding="utf-8")
        code, out, err = self.run_cli(self.base_argv())
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out)["ok"])
        self.assertEqual(err, "")

    def test_a_bad_issue_key_is_a_usage_failure_on_stderr(self):
        bad = make_record(key="../etc")
        self.record_path.write_text(json.dumps(bad), encoding="utf-8")
        code, out, err = self.run_cli(self.base_argv())
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("error: "))

    def test_an_unreadable_input_file_is_a_usage_failure(self):
        argv = self.base_argv()
        argv[2] = str(Path(self.dirpath) / "absent.json")
        code, _, err = self.run_cli(argv)
        self.assertEqual(code, 2)
        self.assertIn("error: ", err)

    def test_malformed_json_input_is_a_usage_failure(self):
        self.record_path.write_text("{not json", encoding="utf-8")
        code, _, err = self.run_cli(self.base_argv())
        self.assertEqual(code, 2)
        self.assertIn("error: ", err)


if __name__ == "__main__":
    unittest.main()
