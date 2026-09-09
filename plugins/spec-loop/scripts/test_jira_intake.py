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


if __name__ == "__main__":
    unittest.main()
