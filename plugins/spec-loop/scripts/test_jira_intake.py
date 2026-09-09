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

TS = "2026-09-09T00:00:00Z"


class TestIssueKeyValidation(unittest.TestCase):
    """The key reaches a filesystem path and argv, so a permissive key is a
    traversal bug, not a formatting nit."""

    def test_a_well_formed_key_is_returned_unchanged(self):
        self.assertEqual(intake.validate_issue_key("ABC-123"), "ABC-123")

    def test_a_traversal_key_is_refused(self):
        bad_keys = (
            "../ABC-1", "ABC-1/../..", "abc-1", "ABC-1 ", "ABC-1\n",
            "ABC-1;rm -rf /", "", "A-1")
        for bad in bad_keys:
            with self.subTest(bad=bad), self.assertRaises(intake.IntakeUsageError):
                intake.validate_issue_key(bad)


class TestArtifactPathGuard(unittest.TestCase):
    """Sanitize-and-assert: the composed path must provably sit under the
    artifact root before any caller writes to it."""

    def test_the_path_is_under_the_artifact_root(self):
        path = intake.artifact_path("ABC-123", intake.ARTIFACT_ROOT)
        self.assertEqual(path, ".spec-loop-jira/ABC-123/intake.md")

    def test_a_bad_key_never_yields_a_path(self):
        with self.assertRaises(intake.IntakeUsageError):
            intake.artifact_path("../../etc/passwd", intake.ARTIFACT_ROOT)

    def test_a_root_that_escapes_is_refused(self):
        bad_roots = ("../elsewhere", "/etc", ".spec-loop-jira/..", "")
        for bad_root in bad_roots:
            with self.subTest(bad_root=bad_root), self.assertRaises(intake.IntakeUsageError):
                intake.artifact_path("ABC-123", bad_root)


def make_refinement(**over):
    """A minimal valid refinement dict; keyword args override one key."""
    base = {
        "description": "Add a widget toggle to the settings pane.",
        "acceptance_criteria": ["Toggle persists across reload."],
        "risks": [{
            "id": "R1", "risk": "No migration for existing rows.",
            "severity": "high"}],
        "gaps": [{
            "id": "G1", "question": "Which roles see the toggle?",
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
        gap = {"question": "q", "impact": "high", "blocking": False}
        bad = make_refinement(gaps=[gap])
        errors = intake.validate_refinement(bad)
        self.assertTrue(any("id" in e for e in errors))

    def test_an_unknown_impact_value_is_reported(self):
        gap = {"id": "G1", "question": "q", "impact": "urgent",
               "blocking": False}
        bad = make_refinement(gaps=[gap])
        errors = intake.validate_refinement(bad)
        self.assertTrue(any("impact" in e for e in errors))

    def test_an_unknown_logged_as_value_is_reported(self):
        answer = {"answer": None, "logged_as": "email"}
        bad = make_refinement(answers={"G1": answer})
        errors = intake.validate_refinement(bad)
        self.assertTrue(any("logged_as" in e for e in errors))

    def test_an_answer_for_an_unknown_gap_is_reported(self):
        answer = {"answer": "x", "logged_as": "decision"}
        bad = make_refinement(answers={"G9": answer})
        errors = intake.validate_refinement(bad)
        self.assertTrue(any("G9" in e for e in errors))

    def test_id_less_gaps_do_not_report_a_none_duplicate(self):
        """_errors_for_gap already reports the missing id; folding both
        malformed gaps to a None sentinel invented a second, wrong error."""
        refinement = make_refinement(
            gaps=[{"question": "q", "impact": "high", "blocking": True},
                  "not-an-object"],
            answers={})
        errors = intake.validate_refinement(refinement)
        self.assertNotIn("gaps have duplicate id: None", errors)
        self.assertIn("gaps[0].id must be a non-empty string", errors)
        self.assertIn("gaps[1] must be an object", errors)


class TestGapRanking(unittest.TestCase):
    """The ranking decides the order of the single AskUserQuestion round, so
    it must be total and deterministic."""

    def test_blocking_gaps_come_before_non_blocking_ones(self):
        gaps = [
            {"id": "G2", "question": "q2", "impact": "high",
             "blocking": False},
            {"id": "G1", "question": "q1", "impact": "low",
             "blocking": True}]
        ranked = [g["id"] for g in intake.rank_gaps(gaps)]
        self.assertEqual(ranked, ["G1", "G2"])

    def test_within_a_blocking_class_impact_orders_them(self):
        gaps = [
            {"id": "G1", "question": "q", "impact": "low",
             "blocking": False},
            {"id": "G2", "question": "q", "impact": "high",
             "blocking": False},
            {"id": "G3", "question": "q", "impact": "medium",
             "blocking": False}]
        ranked = [g["id"] for g in intake.rank_gaps(gaps)]
        self.assertEqual(ranked, ["G2", "G3", "G1"])

    def test_ties_break_on_id_and_the_input_is_not_mutated(self):
        gaps = [
            {"id": "G2", "question": "q", "impact": "high",
             "blocking": True},
            {"id": "G1", "question": "q", "impact": "high",
             "blocking": True}]
        original = [dict(g) for g in gaps]
        ranked = [g["id"] for g in intake.rank_gaps(gaps)]
        self.assertEqual(ranked, ["G1", "G2"])
        self.assertEqual(gaps, original)


class TestDuplicateGapIds(unittest.TestCase):
    """answers is a map keyed by gap id, so two gaps sharing an id both
    resolve to the same entry and an answer cannot be attributed to either
    one. Narrow, measured defect: comment markers do NOT collide when the
    questions differ, because the marker hash covers the question text."""

    def _two_gaps(self, first_id, second_id):
        """A refinement whose two gaps carry the given ids."""
        return make_refinement(gaps=[
            {"id": first_id, "question": "q1", "impact": "high",
             "blocking": True},
            {"id": second_id, "question": "q2", "impact": "low",
             "blocking": False}])

    def test_distinct_gap_ids_are_valid(self):
        self.assertEqual(
            intake.validate_refinement(self._two_gaps("G1", "G2")), [])

    def test_a_duplicate_gap_id_is_an_error(self):
        errors = intake.validate_refinement(self._two_gaps("G1", "G1"))
        self.assertIn("gaps have duplicate id: G1", errors)

    def test_rendering_refuses_a_duplicate_gap_id(self):
        refinement = self._two_gaps("G1", "G1")
        with self.assertRaises(intake.IntakeError):
            intake.render_artifact(make_record(), refinement, TS)


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


class TestRecordValidation(unittest.TestCase):
    """The record file is authored by the calling model, not handed straight
    from jira_client.py, so it gets the same hand-rolled validation the
    refinement already gets. Untrusted shape, not just untrusted text."""

    def test_a_well_formed_record_has_no_errors(self):
        self.assertEqual(intake.validate_record(make_record()), [])

    def test_a_non_dict_record_is_an_error(self):
        for bad in ([1, 2], "ABC-123", None, 7):
            with self.subTest(bad=bad):
                errors = intake.validate_record(bad)
                self.assertEqual(errors, ["record must be a JSON object"])

    def test_each_missing_required_field_is_named(self):
        for field in intake.RECORD_KEYS:
            with self.subTest(field=field):
                record = make_record()
                del record[field]
                errors = intake.validate_record(record)
                expected = ["record is missing required key: %s" % field]
                self.assertEqual(errors, expected)

    def test_rendering_refuses_a_malformed_record(self):
        for bad in ([1, 2], {"key": "ABC-123"}):
            with self.subTest(bad=bad), self.assertRaises(intake.IntakeError):
                intake.render_artifact(bad, make_refinement(), TS)

    def test_building_comments_refuses_a_malformed_record(self):
        with self.assertRaises(intake.IntakeError):
            intake.build_comment_bodies([1, 2], make_refinement(), TS)

    def test_a_none_scalar_is_refused(self):
        errors = intake.validate_record(make_record(status=None))
        self.assertEqual(errors, ["record key status must be a string"])

    def test_a_non_list_comments_field_is_refused(self):
        errors = intake.validate_record(make_record(comments="x"))
        self.assertEqual(errors, ["record key comments must be a list"])


class TestCommentMarker(unittest.TestCase):
    """j3 dedupes by reading this marker back off the card, so it must be
    stable across runs and must NOT contain the timestamp."""

    def test_the_marker_has_the_pinned_shape(self):
        marker = intake.comment_marker("ABC-123", "decision", "payload")
        self.assertTrue(marker.startswith("[spec-loop-intake:decision:"))
        self.assertTrue(marker.endswith("]"))
        self.assertEqual(len(marker.split(":")[2].rstrip("]")), 12)

    def test_the_marker_is_stable_for_the_same_payload(self):
        first = intake.comment_marker("ABC-123", "decision", "p")
        second = intake.comment_marker("ABC-123", "decision", "p")
        self.assertEqual(first, second)

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
        body = intake.render_comment(
            "ABC-123", "decision", "Admins only.", TS)
        marker = intake.comment_marker("ABC-123", "decision", "Admins only.")
        self.assertIn(marker, body)
        self.assertIn(TS, body)
        self.assertIn("Admins only.", body)

    def test_the_timestamp_does_not_change_the_marker(self):
        early = intake.render_comment("ABC-123", "decision", "p", "2026-01-01T00:00:00Z")
        late = intake.render_comment("ABC-123", "decision", "p", "2026-12-31T00:00:00Z")
        marker = intake.comment_marker("ABC-123", "decision", "p")
        self.assertIn(marker, early)
        self.assertIn(marker, late)

    def test_one_understanding_comment_plus_one_per_gap(self):
        gaps = [
            {"id": "G1", "question": "Which roles?", "impact": "high",
             "blocking": True},
            {"id": "G2", "question": "What timezone?", "impact": "low",
             "blocking": False}]
        answers = {"G1": {"answer": "Admins only.", "logged_as": "decision"}}
        refinement = make_refinement(gaps=gaps, answers=answers)
        built = intake.build_comment_bodies(
            make_record(), refinement, TS)
        kinds = [c["kind"] for c in built]
        self.assertEqual(kinds, ["understanding", "decision", "open-question"])
        self.assertEqual([c["gap_id"] for c in built], [None, "G1", "G2"])

    def test_an_unanswered_gap_becomes_an_open_question_carrying_the_question(self):
        answer = {"answer": None, "logged_as": "open-question"}
        refinement = make_refinement(answers={"G1": answer})
        built = intake.build_comment_bodies(
            make_record(), refinement, TS)
        self.assertEqual(built[1]["kind"], "open-question")
        self.assertIn("Which roles see the toggle?", built[1]["body"])

    def test_the_understanding_body_carries_description_ac_and_risks(self):
        built = intake.build_comment_bodies(
            make_record(), make_refinement(), TS)
        body = built[0]["body"]
        self.assertIn("Add a widget toggle to the settings pane.", body)
        self.assertIn("Toggle persists across reload.", body)
        self.assertIn("No migration for existing rows.", body)

    def test_an_invalid_refinement_is_refused_rather_than_half_rendered(self):
        with self.assertRaises(intake.IntakeError):
            intake.build_comment_bodies(
                make_record(), {"description": "x"}, TS)


class TestArtifactRendering(unittest.TestCase):
    """The artifact schema IS the command prose; this pins the field names a
    later reader (and the handoff) depends on."""

    def setUp(self):
        self.text = intake.render_artifact(
            make_record(), make_refinement(), TS)

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
                make_record(), make_refinement(), TS):
            with self.subTest(kind=comment["kind"]):
                self.assertIn(comment["marker"], self.text)

    def test_the_counts_match_the_refinement(self):
        self.assertIn("gap_count: 1", self.text)
        self.assertIn("open_question_count: 0", self.text)

    def test_injection_findings_are_reported_in_section_six(self):
        finding = "Card text asks the agent to ignore its instructions."
        refinement = make_refinement(injection_findings=[finding])
        text = intake.render_artifact(
            make_record(), refinement, TS)
        tail = text[text.index("## 6. Untrusted-input findings"):]
        self.assertIn("ignore its instructions", tail)

    def test_an_invalid_refinement_is_refused(self):
        with self.assertRaises(intake.IntakeError):
            intake.render_artifact(
                make_record(), {"description": "x"}, TS)


class TestFrontMatterEscaping(unittest.TestCase):
    """The artifact IS the file handed to /spec-loop:spec-loop --from-plan, so
    front matter that will not parse is a broken handoff, not a cosmetic nit.
    issue_status, issue_type and acceptance_criteria_source are all
    Jira-controlled strings, and colon-space is common in real statuses."""

    def _value_for(self, record, field):
        """Parse one front-matter field back out of the rendered artifact."""
        text = intake.render_artifact(record, make_refinement(), TS)
        block = text.split("---\n")[1]
        for line in block.splitlines():
            name, _, raw = line.partition(": ")
            if name == field:
                return json.loads(raw)
        self.fail("field %s missing from front matter" % field)

    def test_a_colon_space_status_round_trips(self):
        value = "Blocked: waiting on design"
        self.assertEqual(
            self._value_for(make_record(status=value), "issue_status"), value)

    def test_a_double_quote_round_trips(self):
        value = 'Needs "final" sign-off'
        self.assertEqual(
            self._value_for(make_record(issue_type=value), "issue_type"), value)

    def test_a_newline_round_trips(self):
        value = "field\nsecond line"
        record = make_record(acceptance_criteria_source=value)
        got = self._value_for(record, "acceptance_criteria_source")
        self.assertEqual(got, value)

    def test_a_newline_does_not_break_the_front_matter_delimiters(self):
        text = intake.render_artifact(
            make_record(status="a\n---\nb"), make_refinement(),
            TS)
        self.assertTrue(text.startswith("---\n"))
        self.assertEqual(text.count("\n---\n"), 1)

    def test_numeric_fields_stay_unquoted(self):
        text = intake.render_artifact(make_record(), make_refinement(), TS)
        self.assertIn("gap_count: 1", text)
        self.assertIn("schema_version: 2", text)


class TestRenderCli(unittest.TestCase):
    """The command shells this CLI; its exit codes and stream choice must
    match jira_client.py so the command handles one idiom, not two."""

    def setUp(self):
        self.dirpath = tempfile.mkdtemp(prefix="jira-intake-test-")
        self.record_path = Path(self.dirpath) / "record.json"
        self.refinement_path = Path(self.dirpath) / "refinement.json"
        self.record_path.write_text(json.dumps(make_record()), encoding="utf-8")
        refinement_json = json.dumps(make_refinement())
        self.refinement_path.write_text(refinement_json, encoding="utf-8")

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
                "--ts", TS]

    def test_a_good_render_exits_zero_with_one_json_object(self):
        code, out, _ = self.run_cli(self.base_argv())
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["posted"])
        self.assertEqual(
            payload["artifact_path"], ".spec-loop-jira/ABC-123/intake.md")
        self.assertIn("## 1. Refined description", payload["artifact"])
        self.assertEqual(payload["comments"][0]["kind"], "understanding")

    def test_an_invalid_refinement_is_a_contract_failure_on_stdout(self):
        invalid_json = json.dumps({"description": "x"})
        self.refinement_path.write_text(invalid_json, encoding="utf-8")
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


class TestBodyDelimiterNeutralization(unittest.TestCase):
    """A bare '---' line is ordinary markdown in a Jira card, and this
    artifact IS the file handed to /spec-loop:spec-loop --from-plan: a card
    that forges a front-matter delimiter breaks the handoff. Every
    card-derived surface must still render exactly two '---' lines."""

    BAR = "before\n---\nafter"

    def _delimiter_count(self, record, refinement):
        """Rendered lines exactly equal to '---'."""
        text = intake.render_artifact(record, refinement, TS)
        return len([ln for ln in text.splitlines() if ln == "---"])

    def test_a_rule_in_the_description_keeps_two_delimiters(self):
        refinement = make_refinement(description=self.BAR)
        self.assertEqual(
            self._delimiter_count(make_record(), refinement), 2)

    def test_a_rule_in_the_summary_keeps_two_delimiters(self):
        record = make_record(summary=self.BAR)
        self.assertEqual(
            self._delimiter_count(record, make_refinement()), 2)

    def test_a_rule_in_an_acceptance_criterion_keeps_two_delimiters(self):
        refinement = make_refinement(acceptance_criteria=[self.BAR])
        self.assertEqual(
            self._delimiter_count(make_record(), refinement), 2)

    def test_a_rule_in_a_risk_keeps_two_delimiters(self):
        refinement = make_refinement(
            risks=[{"id": "R1", "risk": self.BAR, "severity": "high"}])
        self.assertEqual(
            self._delimiter_count(make_record(), refinement), 2)

    def test_a_rule_in_a_gap_question_keeps_two_delimiters(self):
        refinement = make_refinement(
            gaps=[{"id": "G1", "question": self.BAR,
                   "impact": "high", "blocking": True}])
        self.assertEqual(
            self._delimiter_count(make_record(), refinement), 2)

    def test_a_rule_in_an_injection_finding_keeps_two_delimiters(self):
        refinement = make_refinement(injection_findings=[self.BAR])
        self.assertEqual(
            self._delimiter_count(make_record(), refinement), 2)

    def test_the_posted_comment_bodies_are_not_rewritten(self):
        """j3 posts these to Jira, where '---' is harmless, and
        comment_marker hashes the payload: only the EMBEDDED copy is
        neutralized."""
        refinement = make_refinement(description=self.BAR)
        built = intake.build_comment_bodies(
            make_record(), refinement, TS)
        self.assertIn("\n---\n", built[0]["body"])


class TestIdsCannotForgeFrontMatterDelimiters(unittest.TestCase):
    """risks[].id and gaps[].id are emitted inline into the artifact body
    WITHOUT passing through _neutralize_delimiters, and they are also
    dict keys in `answers` and components of comment_marker. A multi-line
    id therefore forges a third '---' line and breaks the handoff file,
    so it is rejected rather than rewritten."""

    BAR = "R1\n---\nx"

    def test_a_multiline_risk_id_is_rejected(self):
        refinement = make_refinement(
            risks=[{"id": self.BAR, "risk": "r", "severity": "high"}])
        errors = intake.validate_refinement(refinement)
        self.assertTrue(
            any("risks[0].id" in e and "newline" in e for e in errors), errors)

    def test_a_multiline_gap_id_is_rejected(self):
        refinement = make_refinement(
            gaps=[{"id": self.BAR, "question": "q",
                   "impact": "high", "blocking": True}],
            answers={})
        errors = intake.validate_refinement(refinement)
        self.assertTrue(
            any("gaps[0].id" in e and "newline" in e for e in errors), errors)

    def test_a_carriage_return_in_an_id_is_rejected(self):
        refinement = make_refinement(
            risks=[{"id": "R1\rX", "risk": "r", "severity": "high"}])
        self.assertNotEqual(intake.validate_refinement(refinement), [])

    def test_a_multiline_id_can_no_longer_reach_the_artifact(self):
        refinement = make_refinement(
            risks=[{"id": self.BAR, "risk": "r", "severity": "high"}])
        with self.assertRaises(intake.IntakeError):
            intake.render_artifact(make_record(), refinement, TS)

    def test_a_single_line_id_is_still_accepted(self):
        self.assertEqual(intake.validate_refinement(make_refinement()), [])


if __name__ == "__main__":
    unittest.main()
