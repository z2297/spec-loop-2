#!/usr/bin/env python3
"""Tests for run_state.py — sidecars, events, prose rendering (stdlib unittest).

Validation, summarisation, and every renderer are pure functions over fixture
objects and fixture markdown, so most of this suite needs no filesystem at all.
The persistence paths (atomic sidecar write, events.jsonl appends,
decisions-log/escalations rendering, answer write-back) run against throwaway
run directories built with tempfile. No clock: every timestamp is injected, as
in production.

Usage:
    python3 -m unittest test_run_state
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_state as rs  # noqa: E402

TS = "2026-07-30T12:00:00Z"
LATER = "2026-07-30T13:00:00Z"


def escalation(**over):
    record = {
        "id": "s1:review-block",
        "trigger": "review-block",
        "title": "Reviewer blocks the retry policy",
        "context": "The reviewer says retries must be bounded; the plan says otherwise.",
        "question": "Bound the retries, or keep the plan as written?",
        "options": [
            {"label": "keep plan", "detail": "ship as planned"},
            {"label": "bound retries", "detail": "cap at 3", "recommended": True},
        ],
        "if_unanswered": "pause this slice; continue all independent slices",
        "status": "OPEN",
        "opened": TS,
        "answer": None,
        "answered_at": None,
    }
    record.update(over)
    return record


def sidecar(status="DONE", **over):
    body = {
        "schema_version": 2,
        "id": "s1",
        "status": status,
        "branch": "spec-loop/20260730-demo/s1",
        "commits": {"base": "a" * 7, "head": "b" * 7},
        "risk_tier": 2,
        "review_tier": 3,
        "critique": {"verdict": "ENDORSE_WITH_CONCERNS", "concerns": 2},
        "tasks_completed": 4,
        "review": {"confirmed": 1, "refuted": 2, "evidence_failed": 0,
                   "fix_rounds": 1, "residual": ["P2: naming could be clearer"]},
        "tests": {"command": "pytest -q", "result": "42 passed", "scope": "full",
                  "tree_sha": "c" * 40},
        "quality": {"status": "PASS", "detail": "no threshold exceeded"},
        "agents_used": 12,
        "wave": 1,
        "started_at": TS,
        "finished_at": LATER,
    }
    if status == "SPLIT":
        body["split"] = {"children": [
            {"goal": "extract the parser", "files": ["p.py"], "subsystems": [],
             "internal_deps": []},
            {"goal": "wire it up", "files": [], "subsystems": [], "internal_deps": [1]},
        ]}
        body["commits"] = {"base": "a" * 7, "head": None}
    if status == "ESCALATED":
        body["escalations"] = [escalation()]
    body.update(over)
    return body


# --------------------------------------------------------------------------
# validate_sidecar — pure, fail-closed
# --------------------------------------------------------------------------

class TestValidateSidecar(unittest.TestCase):
    def assertValid(self, obj):
        self.assertEqual(rs.validate_sidecar(obj), [])

    def assertMentions(self, obj, needle):
        errors = rs.validate_sidecar(obj)
        self.assertTrue(errors, "expected errors")
        self.assertTrue(any(needle in e for e in errors),
                        "no error mentioned %r; got %r" % (needle, errors))

    def test_done_sidecar_is_valid(self):
        self.assertValid(sidecar())

    def test_split_sidecar_is_valid(self):
        self.assertValid(sidecar("SPLIT"))

    def test_escalated_sidecar_is_valid(self):
        self.assertValid(sidecar("ESCALATED"))

    def test_failed_sidecar_needs_no_extras(self):
        self.assertValid({"schema_version": 2, "id": "s1", "status": "FAILED"})

    def test_not_an_object(self):
        self.assertMentions(["nope"], "object")

    def test_wrong_schema_version(self):
        self.assertMentions(sidecar(schema_version=1), "schema_version")

    def test_missing_id(self):
        body = sidecar()
        del body["id"]
        self.assertMentions(body, "id")

    def test_unknown_status_is_invalid(self):
        self.assertMentions(sidecar(status="MOSTLY_DONE"), "status")

    def test_missing_status_is_invalid(self):
        body = sidecar()
        del body["status"]
        self.assertMentions(body, "status")

    def test_lowercase_status_is_invalid(self):
        self.assertMentions(sidecar(status="done"), "status")

    def test_done_requires_commits(self):
        body = sidecar()
        del body["commits"]
        self.assertMentions(body, "commits")

    def test_done_requires_a_head_commit(self):
        self.assertMentions(sidecar(commits={"base": "a" * 7, "head": None}), "head")

    def test_done_requires_tests(self):
        body = sidecar()
        del body["tests"]
        self.assertMentions(body, "tests")

    def test_done_requires_a_test_result(self):
        self.assertMentions(sidecar(tests={"command": "pytest"}), "tests.result")

    def test_done_requires_quality(self):
        body = sidecar()
        del body["quality"]
        self.assertMentions(body, "quality")

    def test_quality_status_enum(self):
        self.assertMentions(sidecar(quality={"status": "probably fine"}), "quality.status")

    def test_split_requires_children(self):
        body = sidecar("SPLIT")
        body["split"] = {"children": []}
        self.assertMentions(body, "children")

    def test_split_with_one_child_is_invalid(self):
        # references/split-ingestion.md: fewer than two children is malformed.
        body = sidecar("SPLIT")
        body["split"]["children"] = [{"goal": "the whole thing"}]
        self.assertMentions(body, "at least 2 children")

    def test_split_requires_the_split_object(self):
        body = sidecar("SPLIT")
        del body["split"]
        self.assertMentions(body, "split")

    def test_split_child_needs_a_goal(self):
        body = sidecar("SPLIT")
        body["split"]["children"] = [{"files": []}, {"goal": "second"}]
        self.assertMentions(body, "goal")

    def test_split_internal_deps_must_be_in_range(self):
        body = sidecar("SPLIT")
        body["split"]["children"] = [{"goal": "a", "internal_deps": [4]}, {"goal": "b"}]
        self.assertMentions(body, "internal_deps")

    def test_escalated_requires_escalations(self):
        body = sidecar("ESCALATED")
        body["escalations"] = []
        self.assertMentions(body, "escalations")

    def test_escalation_needs_an_id(self):
        body = sidecar("ESCALATED", escalations=[escalation(id="")])
        self.assertMentions(body, "id")

    def test_escalation_trigger_enum(self):
        body = sidecar("ESCALATED", escalations=[escalation(trigger="vibes")])
        self.assertMentions(body, "trigger")

    def test_escalation_needs_options(self):
        body = sidecar("ESCALATED", escalations=[escalation(options=[])])
        self.assertMentions(body, "options")

    def test_escalation_option_needs_a_label(self):
        body = sidecar("ESCALATED", escalations=[escalation(options=[{"detail": "x"}])])
        self.assertMentions(body, "label")

    def test_escalation_needs_a_question(self):
        body = sidecar("ESCALATED", escalations=[escalation(question="")])
        self.assertMentions(body, "question")

    def test_escalation_status_enum(self):
        body = sidecar("ESCALATED", escalations=[escalation(status="MAYBE")])
        self.assertMentions(body, "status")

    def test_critique_verdict_enum(self):
        self.assertMentions(sidecar(critique={"verdict": "LGTM"}), "verdict")

    def test_wave_must_be_an_integer(self):
        self.assertMentions(sidecar(wave="one"), "wave")

    def test_risk_tier_enum(self):
        self.assertMentions(sidecar(risk_tier=9), "risk_tier")

    def test_every_problem_is_reported_at_once(self):
        self.assertGreaterEqual(len(rs.validate_sidecar(
            {"schema_version": 1, "status": "DONE"})), 3)

    def test_commits_must_be_an_object(self):
        self.assertMentions(sidecar(commits="abc123"), "commits")

    def test_escalations_must_be_a_list(self):
        self.assertMentions(sidecar(escalations={"id": "x"}), "escalations")

    def test_branch_must_be_a_non_empty_string(self):
        self.assertMentions(sidecar(branch="  "), "branch")

    def test_escalation_entry_must_be_an_object(self):
        self.assertMentions(sidecar("ESCALATED", escalations=["nope"]), "object")

    def test_escalation_needs_a_title(self):
        self.assertMentions(sidecar("ESCALATED", escalations=[escalation(title="")]),
                            "title")

    def test_escalation_option_must_be_an_object(self):
        self.assertMentions(sidecar("ESCALATED", escalations=[escalation(options=["a"])]),
                            "option 1")

    def test_split_child_must_be_an_object(self):
        body = sidecar("SPLIT")
        body["split"]["children"] = ["extract the parser", {"goal": "b"}]
        self.assertMentions(body, "children[1]")

    def test_split_internal_deps_must_be_a_list(self):
        body = sidecar("SPLIT")
        body["split"]["children"] = [{"goal": "a", "internal_deps": 2}, {"goal": "b"}]
        self.assertMentions(body, "internal_deps")

    def test_a_sidecar_without_an_over_scope_block_is_valid(self):
        # over_scope is optional: absence means "no scope judgement recorded",
        # which is not the same claim as flag=False.
        body = sidecar()
        self.assertNotIn("over_scope", body["critique"])
        self.assertValid(body)

    def test_an_over_scope_record_with_a_flag_and_a_reason_is_valid(self):
        self.assertValid(sidecar(critique={
            "verdict": "ENDORSE_WITH_CONCERNS", "concerns": 2,
            "over_scope": {"flag": True, "reason": "adds a tier heuristic"}}))

    def test_an_over_scope_record_may_carry_a_null_reason(self):
        self.assertValid(sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0,
            "over_scope": {"flag": False, "reason": None}}))

    def test_a_null_over_scope_reads_as_absent_and_is_valid(self):
        self.assertValid(sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0, "over_scope": None}))

    def test_over_scope_must_be_an_object(self):
        self.assertMentions(sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0, "over_scope": True}),
            "critique.over_scope must be a JSON object")

    def test_over_scope_flag_must_be_a_boolean(self):
        self.assertMentions(sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0,
            "over_scope": {"flag": "yes", "reason": None}}),
            "critique.over_scope.flag")

    def test_over_scope_without_a_flag_is_refused(self):
        self.assertMentions(sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0, "over_scope": {"reason": "x"}}),
            "critique.over_scope.flag")

    def test_over_scope_reason_must_be_a_string_or_null(self):
        self.assertMentions(sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0,
            "over_scope": {"flag": True, "reason": 7}}),
            "critique.over_scope.reason")

    def test_a_bad_flag_and_a_bad_reason_are_reported_together(self):
        # Validation never short-circuits: one round-trip must show everything.
        errors = rs.validate_sidecar(sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0,
            "over_scope": {"flag": None, "reason": []}}))
        scoped = [e for e in errors if e.startswith("critique.over_scope.")]
        self.assertEqual(len(scoped), 2)


# --------------------------------------------------------------------------
# renderers — pure
# --------------------------------------------------------------------------

class TestRenderEscalation(unittest.TestCase):
    def test_shape(self):
        body = rs.render_escalation("s1", escalation())
        self.assertIn("## [s1] Reviewer blocks the retry policy   (status: OPEN)",
                      body)
        self.assertIn("- Trigger: review-block", body)
        self.assertIn("- Opened: %s" % TS, body)
        self.assertIn("- Context: The reviewer says", body)
        self.assertIn("- The decision: Bound the retries", body)
        self.assertIn("- Options:", body)
        self.assertIn("- If unanswered: pause this slice", body)
        self.assertIn("- Answer:\n", body)
        self.assertIn("- Answered-at:", body)

    def test_recommended_option_comes_first_and_is_labelled(self):
        lines = rs.render_escalation("s1", escalation()).splitlines()
        options = [line for line in lines if line.strip().startswith(("1.", "2."))]
        self.assertEqual(options[0].strip(),
                         "1. bound retries — (RECOMMENDED DEFAULT) cap at 3")
        self.assertEqual(options[1].strip(), "2. keep plan — ship as planned")

    def test_option_order_is_stable_without_a_recommendation(self):
        record = escalation(options=[{"label": "a", "detail": "one"},
                                     {"label": "b", "detail": "two"}])
        lines = rs.render_escalation("s1", record).splitlines()
        options = [line.strip() for line in lines if line.strip().startswith(("1.", "2."))]
        self.assertEqual(options, ["1. a — one", "2. b — two"])

    def test_id_anchor_is_embedded_for_answer_write_back(self):
        self.assertIn("s1:review-block", rs.render_escalation("s1", escalation()))

    def test_answered_record_renders_its_answer(self):
        record = escalation(status="ANSWERED", answer="bound them",
                            answered_at=LATER)
        body = rs.render_escalation("s1", record)
        self.assertIn("(status: ANSWERED)", body)
        self.assertIn("- Answer: bound them", body)
        self.assertIn("- Answered-at: %s" % LATER, body)


class TestAnswerWriteBack(unittest.TestCase):
    def setUp(self):
        self.body = (rs.ESCALATIONS_HEADER
                     + rs.render_escalation("s1", escalation())
                     + rs.render_escalation("s2", escalation(id="s2:ambiguity",
                                                             title="Which format?")))

    def test_fills_in_the_matching_entry(self):
        updated, matched = rs.answer_escalation(self.body, "s2:ambiguity",
                                                "use CSV", LATER)
        self.assertTrue(matched)
        self.assertIn("- Answer: use CSV", updated)
        self.assertIn("- Answered-at: %s" % LATER, updated)

    def test_flips_only_the_matching_heading_to_answered(self):
        updated, _ = rs.answer_escalation(self.body, "s2:ambiguity", "use CSV", LATER)
        headings = [line for line in updated.splitlines() if line.startswith("## ")]
        self.assertIn("(status: OPEN)", headings[0])
        self.assertIn("(status: ANSWERED)", headings[1])

    def test_leaves_the_other_entry_untouched(self):
        updated, _ = rs.answer_escalation(self.body, "s2:ambiguity", "use CSV", LATER)
        self.assertEqual(updated.count("- Answer: use CSV"), 1)
        self.assertEqual(updated.count("- Answer:\n"), 1)

    def test_reports_no_match(self):
        updated, matched = rs.answer_escalation(self.body, "s9:ghost", "x", LATER)
        self.assertFalse(matched)
        self.assertEqual(updated, self.body)

    def test_multiline_answer_is_collapsed(self):
        updated, _ = rs.answer_escalation(self.body, "s1:review-block",
                                          "do this\nthen that", LATER)
        self.assertIn("- Answer: do this then that", updated)


class TestDecisionLine(unittest.TestCase):
    def line(self, event_type, payload, scope="s1"):
        return rs.decision_line({"ts": TS, "scope": scope, "type": event_type,
                                 "payload": payload})

    def test_shape(self):
        self.assertEqual(
            self.line("decision", {"summary": "use the existing CSV writer"}),
            "[s1] DECISION: use the existing CSV writer — AT: %s" % TS)

    def test_council_verdict_summary(self):
        self.assertIn("ENDORSE_WITH_CONCERNS (2 concerns)",
                      self.line("council-verdict",
                                {"verdict": "ENDORSE_WITH_CONCERNS", "concerns": 2}))

    def test_quality_gate_summary(self):
        self.assertIn("FAIL — complexity 14 > 10",
                      self.line("quality-gate",
                                {"status": "FAIL", "detail": "complexity 14 > 10"}))

    def test_integration_check_summary(self):
        self.assertIn("conflict in app.py",
                      self.line("integration-check",
                                {"result": "FAIL", "detail": "conflict in app.py"},
                                scope="phase5"))

    def test_deferred_falls_back_to_the_title(self):
        self.assertIn("rate limiting", self.line("deferred", {"title": "rate limiting"}))

    def test_newlines_are_collapsed(self):
        self.assertNotIn("\n", self.line("decision", {"summary": "a\nb"}))

    def test_long_summary_is_truncated(self):
        line = self.line("decision", {"summary": "x" * 500})
        self.assertLess(len(line), 300)

    def test_unsummarisable_payload_falls_back_to_json(self):
        self.assertIn("{", self.line("decision", {"weird": [1, 2]}))

    def test_empty_payload_is_tolerated(self):
        self.assertIn("[s1] DECISION:", self.line("decision", {}))

    def test_non_object_payload_is_tolerated(self):
        self.assertIn("just text", self.line("decision", "just text"))

    def test_a_flagged_scope_record_is_named_in_the_council_line(self):
        record = {"flag": True, "reason": "adds a tier heuristic"}
        payload = {"verdict": "ENDORSE", "concerns": 1, "over_scope": record}
        line = self.line("council-verdict", payload)
        self.assertIn("SCOPE-FLAGGED: adds a tier heuristic", line)

    def test_a_flagged_scope_record_without_a_reason_still_says_flagged(self):
        record = {"flag": True, "reason": None}
        payload = {"verdict": "ENDORSE", "over_scope": record}
        self.assertIn("SCOPE-FLAGGED", self.line("council-verdict", payload))

    def test_a_clean_scope_record_is_rendered_not_swallowed(self):
        # Unconditional rendering: "the council looked and found nothing" must
        # be visible, otherwise it is indistinguishable from "nobody looked".
        record = {"flag": False, "reason": None}
        payload = {"verdict": "ENDORSE", "over_scope": record}
        self.assertIn("scope: clean", self.line("council-verdict", payload))

    def test_an_absent_scope_record_renders_no_scope_phrase_at_all(self):
        line = self.line("council-verdict", {"verdict": "ENDORSE", "concerns": 0})
        self.assertNotIn("scope", line.lower())

    def test_a_malformed_scope_record_is_reported_as_unreadable(self):
        payload = {"verdict": "ENDORSE", "over_scope": {"flag": "yes"}}
        line = self.line("council-verdict", payload)
        self.assertIn("scope: unreadable", line)

    def test_a_non_object_scope_record_is_reported_as_unreadable(self):
        payload = {"verdict": "ENDORSE", "over_scope": True}
        line = self.line("council-verdict", payload)
        self.assertIn("scope: unreadable", line)

    def test_a_flagged_record_with_a_malformed_reason_is_unreadable_not_silent(self):
        # A valid boolean flag with a non-string, non-null reason must not
        # fall through to the bare "SCOPE-FLAGGED" line dropping the reason
        # silently — _scope_note's own docstring promises "scope: unreadable"
        # for anything malformed, so the reason and the flag are read together.
        payload = {"verdict": "ENDORSE", "over_scope": {"flag": True, "reason": 7}}
        line = self.line("council-verdict", payload)
        self.assertIn("scope: unreadable", line)
        self.assertNotIn("SCOPE-FLAGGED", line)

    def test_the_safety_prefix_and_the_scope_note_coexist(self):
        record = {"flag": True, "reason": "dashboards"}
        payload = {"verdict": "OBJECT", "concerns": 2, "safety": True}
        payload["over_scope"] = record
        line = self.line("council-verdict", payload)
        self.assertIn("SAFETY OBJECT (2 concerns)", line)
        self.assertIn("SCOPE-FLAGGED: dashboards", line)

    def test_a_scope_marked_deferral_is_marked_in_the_decisions_log(self):
        payload = {"title": "dashboard charts", "over_scope": True}
        line = self.line("deferred", payload)
        self.assertIn("DEFERRED: SCOPE dashboard charts", line)

    def test_an_ordinary_deferral_is_unmarked(self):
        line = self.line("deferred", {"title": "dashboard charts"})
        self.assertIn("DEFERRED: dashboard charts", line)
        self.assertNotIn("SCOPE", line)

    def test_a_deferral_marked_false_is_not_a_scope_deferral(self):
        # over_scope: false is an explicit "not a scope deferral"; only the
        # boolean true earns the marker.
        payload = {"title": "dashboard charts", "over_scope": False}
        line = self.line("deferred", payload)
        self.assertIn("DEFERRED: dashboard charts", line)
        self.assertNotIn("SCOPE", line)

    def test_a_non_string_verdict_is_still_rendered_not_crashed_on(self):
        # decision_line renders arbitrary events.jsonl payloads, so the
        # extracted _verdict_summary must stay as type-tolerant as the
        # %-formatted expression it replaced.
        line = self.line("council-verdict", {"verdict": 7, "concerns": "many"})
        self.assertIn("COUNCIL-VERDICT: 7 (many concerns)", line)

    def test_the_scope_marker_is_only_read_on_deferred_events(self):
        # over_scope on some other event type is not a rendering instruction.
        payload = {"summary": "use the CSV writer", "over_scope": True}
        line = self.line("decision", payload)
        self.assertIn("DECISION: use the CSV writer", line)
        self.assertNotIn("SCOPE", line)


class TestRenderReport(unittest.TestCase):
    def test_done_report(self):
        body = rs.render_report(sidecar())
        self.assertIn("# Slice s1 — DONE", body)
        self.assertIn("spec-loop/20260730-demo/s1", body)
        self.assertIn("Wave:** 1", body)
        self.assertIn("pytest -q", body)
        self.assertIn("42 passed", body)
        self.assertIn("PASS", body)
        self.assertIn("ENDORSE_WITH_CONCERNS", body)
        self.assertIn("1 confirmed", body)
        self.assertIn("P2: naming could be clearer", body)
        self.assertIn("Agents used:** 12", body)

    def test_fix_rounds_are_pluralised(self):
        self.assertIn("1 fix round\n", rs.render_report(sidecar()))
        body = sidecar()
        body["review"] = dict(body["review"], fix_rounds=2)
        self.assertIn("2 fix rounds", rs.render_report(body))

    def test_review_counters_that_were_not_recorded_are_left_out(self):
        body = rs.render_report(sidecar(review={"confirmed": 3}))
        self.assertIn("3 confirmed", body)
        self.assertNotIn("refuted", body)

    def test_report_mentions_both_tiers_when_promoted(self):
        self.assertIn("review tier 3", rs.render_report(sidecar()))

    def test_report_omits_review_tier_when_equal(self):
        self.assertNotIn("review tier", rs.render_report(sidecar(review_tier=2)))

    def test_split_report_lists_children(self):
        body = rs.render_report(sidecar("SPLIT"))
        self.assertIn("# Slice s1 — SPLIT", body)
        self.assertIn("extract the parser", body)
        self.assertIn("wire it up", body)
        self.assertIn("nothing committed", body)

    def test_escalated_report_lists_escalations(self):
        body = rs.render_report(sidecar("ESCALATED"))
        self.assertIn("Reviewer blocks the retry policy", body)
        self.assertIn("s1:review-block", body)
        self.assertIn("OPEN", body)

    def test_sparse_failed_report_does_not_invent_values(self):
        body = rs.render_report({"schema_version": 2, "id": "s7", "status": "FAILED"})
        self.assertIn("# Slice s7 — FAILED", body)
        for absent in ("None", "null", "Tests:", "Quality gate:"):
            self.assertNotIn(absent, body)

    def test_report_points_at_the_authoritative_sidecar(self):
        self.assertIn("slice-s1-status.json", rs.render_report(sidecar()))

    def test_the_report_names_a_flagged_scope_beside_the_council_verdict(self):
        text = rs.render_report(sidecar(critique={
            "verdict": "ENDORSE_WITH_CONCERNS", "concerns": 2,
            "over_scope": {"flag": True, "reason": "adds a tier heuristic"}}))
        self.assertIn("Iron Council", text)
        self.assertIn("SCOPE-FLAGGED: adds a tier heuristic", text)

    def test_the_report_names_a_clean_scope_verdict_too(self):
        text = rs.render_report(sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0,
            "over_scope": {"flag": False, "reason": None}}))
        self.assertIn("scope: clean", text)

    def test_the_report_says_nothing_about_scope_when_none_was_recorded(self):
        # The Tests line has always printed the unrelated "(scope: full)"
        # test-scope field, so the unrecorded-scope contract is asserted
        # against the Iron Council line itself, not the whole document.
        text = rs.render_report(sidecar())
        self.assertEqual(
            [ln for ln in text.splitlines() if "Iron Council" in ln],
            ["- **Iron Council:** ENDORSE_WITH_CONCERNS (2 concerns)"])
        self.assertNotIn("SCOPE", text)

    def test_a_non_string_council_verdict_is_still_rendered_in_the_report(self):
        text = rs.render_report(sidecar(critique={"verdict": 7, "concerns": 1}))
        self.assertIn("**Iron Council:** 7 (1 concerns)", text)

    def test_a_malformed_scope_record_is_named_unreadable_in_the_report(self):
        text = rs.render_report(sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0, "over_scope": {"reason": "x"}}))
        self.assertIn("scope: unreadable", text)


# --------------------------------------------------------------------------
# filesystem: events, persist-slice, open escalations
# --------------------------------------------------------------------------

class RunStateTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.run_dir = os.path.join(self.root, "docs", "spec-loop", "20260730-demo")
        os.makedirs(self.run_dir)
        # Phase 1 creates dag.json before any event is appended; the CLI
        # refuses a run dir without it (see TestRunDirGuard).
        with open(os.path.join(self.run_dir, "dag.json"), "w", encoding="utf-8") as fh:
            json.dump({"schema_version": 2}, fh)

    def read(self, name):
        path = os.path.join(self.run_dir, name)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    def events(self):
        return rs.read_events(self.run_dir)

    def cli(self, *argv, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        patches = [mock.patch("sys.stdout", out), mock.patch("sys.stderr", err)]
        if stdin is not None:
            patches.append(mock.patch("sys.stdin", io.StringIO(stdin)))
        for patch in patches:
            patch.start()
        try:
            code = rs.main(list(argv) + ["--run-dir", self.run_dir])
        finally:
            for patch in reversed(patches):
                patch.stop()
        payload = json.loads(out.getvalue()) if out.getvalue().strip() else None
        return code, payload, err.getvalue()


class TestRunDirGuard(RunStateTestCase):
    def _main(self, run_dir):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            code = rs.main(["append-event", "--run-dir", run_dir, "--ts", TS,
                            "--scope", "run", "--type", "baseline",
                            "--payload", "{}"])
        return code, err.getvalue()

    def test_cli_refuses_nonexistent_run_dir(self):
        # Regression (run 20260807-upsell-lines-invoice-status): a test
        # command's `cd server && ...` left the session cwd in server/, and
        # append-event silently created server/docs/spec-loop/<run-id>/ with
        # an events.jsonl fragment the dashboard could never find.
        stray = os.path.join(self.root, "server", "docs", "spec-loop",
                             "20260730-demo")
        code, err = self._main(stray)
        self.assertEqual(code, 2)
        self.assertIn("dag.json", err)
        self.assertFalse(os.path.exists(stray))

    def test_cli_refuses_run_dir_without_dag_json(self):
        os.unlink(os.path.join(self.run_dir, "dag.json"))
        code, err = self._main(self.run_dir)
        self.assertEqual(code, 2)
        self.assertIn("dag.json", err)

    def test_cli_accepts_real_run_dir(self):
        code, err = self._main(self.run_dir)
        self.assertEqual(code, 0, err)
        self.assertIsNotNone(self.read("events.jsonl"))


class TestAppendEvent(RunStateTestCase):
    def test_creates_events_jsonl(self):
        rs.append_event(self.run_dir, TS, "run", "run-created", {"run_id": "x"})
        lines = self.read("events.jsonl").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), {
            "ts": TS, "scope": "run", "type": "run-created",
            "payload": {"run_id": "x"}})

    def test_appends_in_order(self):
        rs.append_event(self.run_dir, TS, "run", "run-created", {})
        rs.append_event(self.run_dir, LATER, "wave1", "wave-dispatched", {"index": 1})
        self.assertEqual([e["type"] for e in self.events()],
                         ["run-created", "wave-dispatched"])

    def test_unrendered_event_writes_no_prose(self):
        rs.append_event(self.run_dir, TS, "wave1", "wave-dispatched", {"index": 1})
        self.assertIsNone(self.read("decisions-log.md"))
        self.assertIsNone(self.read("escalations.md"))

    def test_decision_event_renders_a_log_line(self):
        rs.append_event(self.run_dir, TS, "s1", "decision",
                        {"summary": "reuse the CSV writer"})
        body = self.read("decisions-log.md")
        self.assertIn("# Decisions log", body)
        self.assertIn("[s1] DECISION: reuse the CSV writer — AT: %s" % TS, body)

    def test_decision_log_is_append_only(self):
        rs.append_event(self.run_dir, TS, "s1", "decision", {"summary": "one"})
        rs.append_event(self.run_dir, LATER, "s2", "deferred", {"summary": "two"})
        body = self.read("decisions-log.md")
        self.assertIn("one", body)
        self.assertIn("two", body)
        self.assertEqual(body.count("# Decisions log"), 1)

    def test_every_gate_event_type_is_logged(self):
        for index, event_type in enumerate(
                ("decision", "deferred", "council-verdict", "quality-gate",
                 "integration-check", "phase5-gate")):
            rs.append_event(self.run_dir, TS, "s%d" % index, event_type,
                            {"summary": "s", "verdict": "ENDORSE", "status": "PASS",
                             "result": "PASS"})
        body = self.read("decisions-log.md")
        for event_type in ("DECISION", "DEFERRED", "COUNCIL-VERDICT",
                           "QUALITY-GATE", "INTEGRATION-CHECK", "PHASE5-GATE"):
            self.assertIn(event_type, body)

    def test_escalation_opened_writes_a_full_entry(self):
        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
        body = self.read("escalations.md")
        self.assertIn("# Escalations", body)
        self.assertIn("(status: OPEN)", body)
        self.assertIn("- The decision: Bound the retries", body)
        self.assertIsNone(self.read("decisions-log.md"))

    def test_escalation_answered_fills_in_the_entry(self):
        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
        rs.append_event(self.run_dir, LATER, "s1", "escalation-answered",
                        {"id": "s1:review-block", "answer": "bound them"})
        body = self.read("escalations.md")
        self.assertIn("- Answer: bound them", body)
        self.assertIn("- Answered-at: %s" % LATER, body)
        self.assertIn("(status: ANSWERED)", body)

    def test_escalation_answered_honours_an_explicit_answered_at(self):
        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
        rs.append_event(self.run_dir, LATER, "s1", "escalation-answered",
                        {"id": "s1:review-block", "answer": "x",
                         "answered_at": "2026-08-01T00:00:00Z"})
        self.assertIn("- Answered-at: 2026-08-01T00:00:00Z", self.read("escalations.md"))

    def test_orphan_answer_is_still_surfaced(self):
        rs.append_event(self.run_dir, LATER, "s1", "escalation-answered",
                        {"id": "s1:ghost", "answer": "whatever"})
        body = self.read("escalations.md")
        self.assertIn("s1:ghost", body)
        self.assertIn("whatever", body)

    def test_events_survive_a_prose_render(self):
        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
        self.assertEqual([e["type"] for e in self.events()], ["escalation-opened"])

    def test_malformed_lines_are_skipped_by_the_reader(self):
        rs.append_event(self.run_dir, TS, "s1", "decision", {"summary": "ok"})
        with open(os.path.join(self.run_dir, "events.jsonl"), "a", encoding="utf-8") as fh:
            fh.write("{half written\n")
        rs.append_event(self.run_dir, LATER, "s1", "decision", {"summary": "also ok"})
        self.assertEqual(len(self.events()), 2)

    def test_reader_tolerates_a_missing_file(self):
        self.assertEqual(rs.read_events(self.run_dir), [])

    def test_reader_skips_blank_lines(self):
        rs.append_event(self.run_dir, TS, "s1", "decision", {"summary": "ok"})
        with open(os.path.join(self.run_dir, "events.jsonl"), "a", encoding="utf-8") as fh:
            fh.write("\n\n")
        self.assertEqual(len(self.events()), 1)

    def test_unwritable_run_dir_is_a_run_state_error(self):
        blocked = os.path.join(self.root, "not-a-dir")
        with open(blocked, "w", encoding="utf-8") as fh:
            fh.write("x")
        with self.assertRaises(rs.RunStateError):
            rs.append_event(blocked, TS, "run", "run-created", {})

    def test_sidecar_write_failure_is_a_run_state_error(self):
        with mock.patch.object(rs.os, "replace", side_effect=OSError("read-only")):
            with self.assertRaises(rs.RunStateError):
                rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)


class TestPersistSlice(RunStateTestCase):
    def test_writes_the_sidecar_atomically(self):
        report = rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
        self.assertTrue(report["ok"])
        stored = json.loads(self.read("slice-s1-status.json"))
        self.assertEqual(stored["id"], "s1")
        self.assertEqual(stored["status"], "DONE")
        self.assertNotIn(True, [name.startswith(".") for name
                                in os.listdir(self.run_dir)])

    def test_the_cli_wave_wins_over_the_payload(self):
        rs.persist_slice(self.run_dir, sidecar(wave=1), wave=3, ts=TS)
        self.assertEqual(json.loads(self.read("slice-s1-status.json"))["wave"], 3)

    def test_renders_the_human_report(self):
        rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
        body = self.read("slice-s1-report.md")
        self.assertIn("# Slice s1 — DONE", body)

    def test_report_is_rewritten_on_a_second_persist(self):
        rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
        rs.persist_slice(self.run_dir, sidecar(status="FAILED"), wave=1, ts=LATER)
        body = self.read("slice-s1-report.md")
        self.assertIn("FAILED", body)
        self.assertEqual(body.count("# Slice s1"), 1)

    def test_emits_council_review_and_quality_events(self):
        report = rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
        types = [e["type"] for e in self.events()]
        self.assertEqual(types, ["council-verdict", "review-summary",
                                 "quality-gate"])
        self.assertEqual(report["events"], types)

    def test_the_slice_outcome_is_not_re_emitted_as_an_event(self):
        # The sidecar is the single home of per-slice facts: status, commits,
        # tiers, counts, and timings must not appear on a second channel.
        rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
        for event in self.events():
            for owned_by_the_sidecar in ("commits", "branch", "started_at",
                                         "finished_at", "tasks_completed",
                                         "agents_used", "risk_tier"):
                self.assertNotIn(owned_by_the_sidecar, event["payload"])

    def test_a_bare_sidecar_emits_no_events_at_all(self):
        report = rs.persist_slice(
            self.run_dir, {"schema_version": 2, "id": "s7", "status": "FAILED"},
            wave=1, ts=TS)
        self.assertEqual(report["events"], [])
        self.assertEqual(self.events(), [])
        self.assertIn("# Slice s7 — FAILED", self.read("slice-s7-report.md"))

    def test_every_event_carries_the_controller_timestamp_and_slice_scope(self):
        rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
        for event in self.events():
            self.assertEqual(event["ts"], TS)
            self.assertEqual(event["scope"], "s1")

    def test_the_sidecar_keeps_null_honest_values(self):
        rs.persist_slice(self.run_dir, sidecar(agents_used=None), wave=2, ts=TS)
        stored = json.loads(self.read("slice-s1-status.json"))
        self.assertEqual(stored["status"], "DONE")
        self.assertEqual(stored["wave"], 2)
        self.assertIsNone(stored["agents_used"])

    def test_gate_events_reach_the_decisions_log(self):
        rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
        body = self.read("decisions-log.md")
        self.assertIn("QUALITY-GATE", body)
        self.assertIn("COUNCIL-VERDICT", body)

    def test_skipped_critique_emits_no_council_event(self):
        rs.persist_slice(self.run_dir,
                         sidecar(critique={"verdict": "SKIPPED", "concerns": 0}),
                         wave=1, ts=TS)
        self.assertNotIn("council-verdict", [e["type"] for e in self.events()])

    def test_escalations_produce_events_and_the_human_surface(self):
        rs.persist_slice(self.run_dir, sidecar("ESCALATED"), wave=1, ts=TS)
        types = [e["type"] for e in self.events()]
        self.assertIn("escalation-opened", types)
        self.assertIn("(status: OPEN)", self.read("escalations.md"))

    def test_already_answered_escalation_emits_both_events(self):
        body = sidecar("ESCALATED", escalations=[
            escalation(status="ANSWERED", answer="bound them", answered_at=LATER)])
        rs.persist_slice(self.run_dir, body, wave=1, ts=LATER)
        types = [e["type"] for e in self.events()]
        self.assertIn("escalation-opened", types)
        self.assertIn("escalation-answered", types)
        self.assertIn("- Answer: bound them", self.read("escalations.md"))

    def test_split_sidecar_persists_without_grafting(self):
        # Grafting children is dag.py's job; persist only records the proposal.
        report = rs.persist_slice(self.run_dir, sidecar("SPLIT"), wave=1, ts=TS)
        self.assertTrue(report["ok"])
        self.assertIn("extract the parser", self.read("slice-s1-report.md"))
        children = json.loads(self.read("slice-s1-status.json"))["split"]["children"]
        self.assertEqual(len(children), 2)
        self.assertNotIn("split-ingested", [e["type"] for e in self.events()])

    def test_invalid_sidecar_is_refused_and_writes_nothing(self):
        with self.assertRaises(rs.SidecarInvalid) as ctx:
            rs.persist_slice(self.run_dir, sidecar(status="DONE", commits={}),
                             wave=1, ts=TS)
        self.assertTrue(ctx.exception.errors)
        self.assertEqual(os.listdir(self.run_dir), ["dag.json"])  # fixture only

    def test_unknown_status_is_refused(self):
        with self.assertRaises(rs.SidecarInvalid):
            rs.persist_slice(self.run_dir, sidecar(status="PROBABLY_FINE"),
                             wave=1, ts=TS)

    # A malformed critique.over_scope record STAYS FAIL-CLOSED: the binding
    # ruling on this run is that the defect was the missing tests, never the
    # strictness. Each variant below must both raise SidecarInvalid AND leave
    # the run dir untouched — the fixture's dag.json is the only file present,
    # exactly as test_invalid_sidecar_is_refused_and_writes_nothing pins above.

    def test_a_non_object_over_scope_record_is_refused_and_writes_nothing(self):
        body = sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0, "over_scope": True})
        with self.assertRaises(rs.SidecarInvalid) as ctx:
            rs.persist_slice(self.run_dir, body, wave=1, ts=TS)
        self.assertErrorMentions(
            ctx.exception.errors, "critique.over_scope must be a JSON object")
        self.assertEqual(os.listdir(self.run_dir), ["dag.json"])

    def test_a_non_boolean_flag_is_refused_and_writes_nothing(self):
        body = sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0,
            "over_scope": {"flag": "yes", "reason": None}})
        with self.assertRaises(rs.SidecarInvalid) as ctx:
            rs.persist_slice(self.run_dir, body, wave=1, ts=TS)
        self.assertErrorMentions(ctx.exception.errors, "critique.over_scope.flag")
        self.assertEqual(os.listdir(self.run_dir), ["dag.json"])

    def test_a_non_string_non_null_reason_is_refused_and_writes_nothing(self):
        body = sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0,
            "over_scope": {"flag": True, "reason": 7}})
        with self.assertRaises(rs.SidecarInvalid) as ctx:
            rs.persist_slice(self.run_dir, body, wave=1, ts=TS)
        self.assertErrorMentions(ctx.exception.errors, "critique.over_scope.reason")
        self.assertEqual(os.listdir(self.run_dir), ["dag.json"])

    def assertErrorMentions(self, errors, needle):
        self.assertTrue(
            any(needle in message for message in errors),
            "expected %r among %r" % (needle, errors))


class TestOpenEscalations(RunStateTestCase):
    def open_one(self, escalation_id, ts=TS, **over):
        rs.append_event(self.run_dir, ts, escalation_id.split(":")[0],
                        "escalation-opened", escalation(id=escalation_id, **over))

    def answer(self, escalation_id, ts=LATER):
        rs.append_event(self.run_dir, ts, escalation_id.split(":")[0],
                        "escalation-answered",
                        {"id": escalation_id, "answer": "done"})

    def test_no_events_no_escalations(self):
        self.assertEqual(rs.open_escalations(self.run_dir), [])

    def test_lists_open_records(self):
        self.open_one("s1:review-block")
        self.open_one("s2:ambiguity")
        self.assertEqual([r["id"] for r in rs.open_escalations(self.run_dir)],
                         ["s1:review-block", "s2:ambiguity"])

    def test_answered_records_drop_out(self):
        self.open_one("s1:review-block")
        self.open_one("s2:ambiguity")
        self.answer("s1:review-block")
        self.assertEqual([r["id"] for r in rs.open_escalations(self.run_dir)],
                         ["s2:ambiguity"])

    def test_records_carry_their_full_shape(self):
        self.open_one("s1:review-block")
        record = rs.open_escalations(self.run_dir)[0]
        self.assertEqual(record["trigger"], "review-block")
        self.assertEqual(record["status"], "OPEN")
        self.assertTrue(record["options"])

    def test_reopening_the_same_id_keeps_one_record(self):
        self.open_one("s1:review-block")
        self.open_one("s1:review-block", ts=LATER, title="Reworded")
        records = rs.open_escalations(self.run_dir)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "Reworded")

    def test_reopened_after_an_answer_counts_as_open(self):
        self.open_one("s1:review-block")
        self.answer("s1:review-block")
        self.open_one("s1:review-block", ts="2026-07-31T00:00:00Z")
        self.assertEqual([r["id"] for r in rs.open_escalations(self.run_dir)],
                         ["s1:review-block"])

    def test_record_already_marked_answered_is_not_open(self):
        rs.append_event(self.run_dir, TS, "s1", "escalation-opened",
                        escalation(status="ANSWERED", answer="x", answered_at=TS))
        self.assertEqual(rs.open_escalations(self.run_dir), [])

    def test_non_object_payloads_are_ignored(self):
        with open(os.path.join(self.run_dir, "events.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": TS, "scope": "s1",
                                 "type": "escalation-opened",
                                 "payload": ["not a record"]}) + "\n")
        self.assertEqual(rs.open_escalations(self.run_dir), [])

    def test_payloads_without_an_id_are_ignored(self):
        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", {"title": "no id"})
        self.assertEqual(rs.open_escalations(self.run_dir), [])


# --------------------------------------------------------------------------
# the workflow's returned events[] — the rich channel
# --------------------------------------------------------------------------

def returned_events():
    """The shape slice-wave.workflow.js actually returns: {scope, type, payload}."""
    return [
        {"scope": "s1", "type": "agent-dispatch",
         "payload": {"role": "planner", "model": "claude-opus-5", "effort": "high",
                     "agent_type": "slice-planner"}},
        {"scope": "s1", "type": "agent-dispatch",
         "payload": {"role": "implementer", "model": "claude-sonnet-5",
                     "effort": "medium", "agent_type": "sdd-implementer"}},
        {"scope": "s1", "type": "council-verdict",
         "payload": {"verdict": "ENDORSE_WITH_CONCERNS", "panel": ["architect"],
                     "safety": False, "concerns_folded": 2, "deferred": []}},
        {"scope": "s1", "type": "review-summary",
         "payload": {"findings": 7, "confirmed": 1, "refuted": 2, "fix_rounds": 1,
                     "reviewers": 3}},
        {"scope": "s1", "type": "quality-gate",
         "payload": {"status": "PASS", "violations": 0}},
        {"scope": "s1", "type": "decision",
         "payload": {"summary": "review tier promoted to 3: diff touches tier3 surface",
                     "rationale": "deterministic surface-glob match",
                     "reversibility": "n/a"}},
    ]


class TestReturnedEvents(RunStateTestCase):
    """The workflow's events[] is the rich channel; the sidecar blocks are the
    lean fallback. Losing the rich payloads nulls out run_metrics' dials."""

    def test_returned_events_are_appended_verbatim(self):
        rich = returned_events()
        rs.persist_slice(self.run_dir, sidecar(events=rich), wave=1, ts=TS)
        stored = self.events()
        self.assertEqual([e["type"] for e in stored], [e["type"] for e in rich])
        for original, appended in zip(rich, stored):
            self.assertEqual(appended["payload"], original["payload"])

    def test_rich_payload_keys_survive(self):
        # These are exactly the keys the sidecar summary blocks cannot carry.
        rs.persist_slice(self.run_dir, sidecar(events=returned_events()),
                         wave=1, ts=TS)
        by_type = {}
        for event in self.events():
            by_type.setdefault(event["type"], []).append(event["payload"])
        self.assertEqual(len(by_type["agent-dispatch"]), 2)
        self.assertEqual(by_type["agent-dispatch"][0]["agent_type"], "slice-planner")
        self.assertIs(by_type["council-verdict"][0]["safety"], False)
        self.assertEqual(by_type["review-summary"][0]["findings"], 7)
        self.assertEqual(by_type["review-summary"][0]["reviewers"], 3)

    def test_every_returned_event_is_stamped_with_the_controller_clock(self):
        rs.persist_slice(self.run_dir, sidecar(events=returned_events()),
                         wave=1, ts=TS)
        self.assertEqual({e["ts"] for e in self.events()}, {TS})

    def test_an_entrys_own_ts_is_replaced_by_the_controller_stamp(self):
        rs.persist_slice(self.run_dir, sidecar(events=[
            {"scope": "s1", "type": "quality-gate", "ts": "1999-01-01T00:00:00Z",
             "payload": {"status": "PASS"}}]), wave=1, ts=TS)
        self.assertEqual(self.events()[0]["ts"], TS)

    def test_scope_is_preserved_and_defaults_to_the_slice(self):
        rs.persist_slice(self.run_dir, sidecar(events=[
            {"scope": "wave1", "type": "decision", "payload": {"summary": "a"}},
            {"type": "decision", "payload": {"summary": "b"}}]), wave=1, ts=TS)
        self.assertEqual([e["scope"] for e in self.events()], ["wave1", "s1"])

    def test_no_double_emission_of_gate_events(self):
        # The sidecar also carries critique/review/quality blocks; with a rich
        # array present each event type must appear exactly once.
        rs.persist_slice(self.run_dir, sidecar(events=returned_events()),
                         wave=1, ts=TS)
        types = [e["type"] for e in self.events()]
        for once in ("council-verdict", "review-summary", "quality-gate"):
            self.assertEqual(types.count(once), 1, once)

    def test_the_rich_verdict_wins_over_the_sidecar_summary(self):
        rs.persist_slice(self.run_dir, sidecar(events=returned_events()),
                         wave=1, ts=TS)
        verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
        self.assertIn("panel", verdict["payload"])  # rich shape, not {verdict, concerns}

    def test_derivation_still_fires_when_events_are_absent(self):
        rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
        self.assertEqual([e["type"] for e in self.events()],
                         ["council-verdict", "review-summary", "quality-gate"])

    def test_derivation_still_fires_on_an_empty_events_array(self):
        rs.persist_slice(self.run_dir, sidecar(events=[]), wave=1, ts=TS)
        self.assertEqual([e["type"] for e in self.events()],
                         ["council-verdict", "review-summary", "quality-gate"])

    def test_escalations_are_emitted_alongside_a_rich_array(self):
        # The workflow reports escalations in escalations[], never as events, so
        # skipping derivation wholesale would leave the human surface empty.
        rs.persist_slice(self.run_dir,
                         sidecar("ESCALATED", events=returned_events()),
                         wave=1, ts=TS)
        types = [e["type"] for e in self.events()]
        self.assertEqual(types.count("escalation-opened"), 1)
        self.assertIn("(status: OPEN)", self.read("escalations.md"))
        self.assertEqual([r["id"] for r in rs.open_escalations(self.run_dir)],
                         ["s1:review-block"])

    def test_an_escalation_already_in_the_rich_array_is_not_duplicated(self):
        record = escalation()
        rich = [{"scope": "s1", "type": "escalation-opened", "payload": record}]
        rs.persist_slice(self.run_dir,
                         sidecar("ESCALATED", escalations=[record], events=rich),
                         wave=1, ts=TS)
        types = [e["type"] for e in self.events()]
        self.assertEqual(types.count("escalation-opened"), 1)
        self.assertEqual(self.read("escalations.md").count("s1:review-block"), 1)

    def test_rich_decision_events_reach_the_decisions_log(self):
        rs.persist_slice(self.run_dir, sidecar(events=returned_events()),
                         wave=1, ts=TS)
        body = self.read("decisions-log.md")
        self.assertIn("DECISION: review tier promoted to 3", body)
        self.assertIn("QUALITY-GATE: PASS", body)

    def test_agent_dispatch_events_render_no_prose(self):
        rs.persist_slice(self.run_dir, sidecar(events=[
            {"scope": "s1", "type": "agent-dispatch", "payload": {"role": "planner"}}]),
            wave=1, ts=TS)
        self.assertEqual(len(self.events()), 1)
        self.assertIsNone(self.read("decisions-log.md"))

    def test_the_report_returns_the_types_that_were_appended(self):
        report = rs.persist_slice(self.run_dir, sidecar(events=returned_events()),
                                  wave=1, ts=TS)
        self.assertEqual(report["events"], [e["type"] for e in self.events()])

    def test_events_must_be_a_list(self):
        self.assertIn("events must be a list when present",
                      rs.validate_sidecar(sidecar(events={"type": "decision"})))

    def test_an_entry_without_a_type_is_refused(self):
        with self.assertRaises(rs.SidecarInvalid) as ctx:
            rs.persist_slice(self.run_dir,
                             sidecar(events=[{"scope": "s1", "payload": {}}]),
                             wave=1, ts=TS)
        self.assertIn("events[1]: type", " ".join(ctx.exception.errors))
        self.assertEqual(os.listdir(self.run_dir), ["dag.json"])  # fixture only

    def test_a_non_object_entry_is_refused(self):
        self.assertIn("events[1] must be a JSON object",
                      rs.validate_sidecar(sidecar(events=["decision"])))

    def test_a_non_object_payload_is_refused(self):
        self.assertIn("events[1]: payload must be a JSON object when present",
                      rs.validate_sidecar(sidecar(events=[
                          {"type": "decision", "payload": "just text"}])))

    def test_a_blank_scope_is_refused(self):
        self.assertIn("events[1]: scope must be a non-empty string when present",
                      rs.validate_sidecar(sidecar(events=[
                          {"type": "decision", "scope": "  ", "payload": {}}])))

    def test_a_missing_payload_becomes_an_empty_object(self):
        rs.persist_slice(self.run_dir, sidecar(events=[{"type": "baseline"}]),
                         wave=1, ts=TS)
        self.assertEqual(self.events()[0]["payload"], {})


# --------------------------------------------------------------------------
# pinned payload facts (run-state-v2.md §Pinned payload facts)
# --------------------------------------------------------------------------

class TestPinnedPayloadFacts(RunStateTestCase):
    """These are contract, not implementation detail: consumers rely on them."""

    def test_escalation_opened_carries_the_full_record_including_its_id(self):
        record = escalation()
        rs.persist_slice(self.run_dir, sidecar("ESCALATED", escalations=[record]),
                         wave=1, ts=TS)
        opened = [e for e in self.events() if e["type"] == "escalation-opened"][0]
        self.assertEqual(opened["payload"], record)
        self.assertEqual(opened["payload"]["id"], "s1:review-block")

    def test_answers_pair_by_id_not_by_scope(self):
        # One slice can open several escalations; answering one must not close
        # its siblings.
        first, second = escalation(), escalation(id="s1:ambiguity",
                                                 trigger="ambiguity")
        rs.persist_slice(self.run_dir,
                         sidecar("ESCALATED", escalations=[first, second]),
                         wave=1, ts=TS)
        rs.append_event(self.run_dir, LATER, "s1", "escalation-answered",
                        {"id": "s1:ambiguity", "answer": "ISO-8601"})
        self.assertEqual([r["id"] for r in rs.open_escalations(self.run_dir)],
                         ["s1:review-block"])

    def test_an_answer_from_another_scope_still_pairs_by_id(self):
        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
        rs.append_event(self.run_dir, LATER, "run", "escalation-answered",
                        {"id": "s1:review-block", "answer": "bound them"})
        self.assertEqual(rs.open_escalations(self.run_dir), [])

    def test_council_verdict_passes_safety_through(self):
        rs.persist_slice(self.run_dir, sidecar(critique={
            "verdict": "OBJECT", "concerns": 3, "safety": True}), wave=1, ts=TS)
        verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
        self.assertIs(verdict["payload"]["safety"], True)

    def test_safety_false_is_preserved_not_dropped(self):
        rs.persist_slice(self.run_dir, sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0, "safety": False}), wave=1, ts=TS)
        verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
        self.assertIs(verdict["payload"]["safety"], False)

    def test_safety_is_named_in_the_decisions_log(self):
        rs.append_event(self.run_dir, TS, "s1", "council-verdict",
                        {"verdict": "OBJECT", "concerns": 1, "safety": True})
        self.assertIn("SAFETY OBJECT", self.read("decisions-log.md"))

    def test_council_verdict_carries_the_whole_over_scope_record_not_just_a_bool(self):
        # safety drops its reason and records it nowhere; over_scope must not
        # repeat that — flag AND reason are both durable.
        record = {"flag": True, "reason": "adds a tier-assignment heuristic"}
        rs.persist_slice(self.run_dir, sidecar(critique={
            "verdict": "OBJECT", "concerns": 3, "over_scope": record}),
            wave=1, ts=TS)
        verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
        self.assertEqual(verdict["payload"]["over_scope"], record)

    def test_a_clean_over_scope_record_survives_persistence(self):
        rs.persist_slice(self.run_dir, sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0,
            "over_scope": {"flag": False, "reason": None}}), wave=1, ts=TS)
        verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
        self.assertIs(verdict["payload"]["over_scope"]["flag"], False)
        self.assertIn("scope: clean", self.read("decisions-log.md"))

    def test_a_returned_council_verdict_event_keeps_over_scope_byte_for_byte(self):
        payload = {"verdict": "ENDORSE_WITH_CONCERNS", "panel": ["plan-critic"],
                   "safety": False, "concerns_folded": 1, "deferred": ["P2: later"],
                   "over_scope": {"flag": True, "reason": "dashboard UI work"}}
        rs.persist_slice(self.run_dir, sidecar(events=[
            {"scope": "s1", "type": "council-verdict", "payload": payload}]),
            wave=1, ts=TS)
        stored = [e for e in self.events() if e["type"] == "council-verdict"][0]
        self.assertEqual(stored["payload"], payload)

    def test_the_wave_emitted_council_verdict_shape_validates_and_renders(self):
        # The payload slice-wave.workflow.js builds after run 20260825: the
        # scope record sits beside `deferred[]`, never replacing it. The JS is
        # not executed by any lane of this suite, so this is the seam where its
        # emitted shape is actually asserted against the real renderer.
        payload = {"verdict": "ENDORSE_WITH_CONCERNS",
                   "panel": ["full-council", "risk"], "safety": False,
                   "concerns_folded": 2, "deferred": ["dashboard charts"],
                   "over_scope": {"flag": True, "reason": "dashboard UI work"}}
        rs.persist_slice(self.run_dir, sidecar(events=[
            {"scope": "s1", "type": "council-verdict", "payload": payload}]),
            wave=1, ts=TS)
        stored = [e for e in self.events() if e["type"] == "council-verdict"][0]
        log = self.read("decisions-log.md")
        self.assertEqual(stored["payload"], payload)
        self.assertIn("SCOPE-FLAGGED: dashboard UI work", log)

    def test_the_wave_emitted_sidecar_critique_shape_is_accepted(self):
        # state.critique omits over_scope entirely when no member recorded one,
        # and carries {flag, reason} verbatim when one did.
        rs.persist_slice(self.run_dir, sidecar(critique={
            "verdict": "ENDORSE_WITH_CONCERNS", "concerns": 2,
            "over_scope": {"flag": False, "reason": None}}), wave=1, ts=TS)
        self.assertIn("scope: clean", self.read("slice-s1-report.md"))

    def test_a_deferred_event_marks_deferred_scope_with_over_scope_true(self):
        payload = {"title": "dashboard charts", "over_scope": True}
        rs.append_event(self.run_dir, TS, "s1", "deferred", payload)
        stored = self.events()[0]["payload"]
        decisions_log = self.read("decisions-log.md")
        self.assertEqual(stored, payload)
        self.assertIn("DEFERRED: SCOPE dashboard charts", decisions_log)

    def test_over_scope_never_changes_the_recorded_verdict(self):
        # Record-only: the flag is not a vote and not a finding.
        rs.persist_slice(self.run_dir, sidecar(critique={
            "verdict": "ENDORSE", "concerns": 0,
            "over_scope": {"flag": True, "reason": "out of the run ceiling"}}),
            wave=1, ts=TS)
        verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
        self.assertEqual(verdict["payload"]["verdict"], "ENDORSE")

    def test_agent_dispatch_payload_is_passed_through_verbatim(self):
        payload = {"role": "implementer", "model": "claude-opus-5", "effort": "high",
                   "agent_type": "sdd-implementer",
                   "dispatched_at": TS, "returned_at": LATER,
                   "tokens_in": 1200, "tokens_out": 340}
        rs.append_event(self.run_dir, TS, "s1", "agent-dispatch", payload)
        stored = self.events()[0]
        self.assertEqual(stored["payload"], payload)
        self.assertIsNone(self.read("decisions-log.md"))

    def test_agent_dispatch_absent_timings_stay_absent(self):
        rs.append_event(self.run_dir, TS, "s1", "agent-dispatch",
                        {"role": "reviewer", "model": None})
        self.assertEqual(self.events()[0]["payload"], {"role": "reviewer",
                                                      "model": None})

    def test_no_emitted_payload_derives_a_duration(self):
        # ts is a batch collection stamp: nothing here may turn it into elapsed
        # time. The sidecar's own started_at/finished_at pass through untouched.
        rs.persist_slice(self.run_dir, sidecar("ESCALATED",
                                               escalations=[escalation()]),
                         wave=1, ts=TS)
        for event in self.events():
            for key in event["payload"]:
                self.assertNotIn("duration", key)
                self.assertNotIn("elapsed", key)
        stored = json.loads(self.read("slice-s1-status.json"))
        self.assertEqual(stored["started_at"], TS)
        self.assertEqual(stored["finished_at"], LATER)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

class TestCli(RunStateTestCase):
    def sidecar_file(self, body):
        path = os.path.join(self.root, "slice-s1-status.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(body, fh)
        return path

    def test_persist_slice_from_a_file(self):
        code, payload, _ = self.cli("persist-slice", "--json",
                                    self.sidecar_file(sidecar()),
                                    "--wave", "1", "--ts", TS)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["id"], "s1")
        self.assertTrue(os.path.exists(
            os.path.join(self.run_dir, "slice-s1-status.json")))

    def test_persist_slice_from_stdin(self):
        code, payload, _ = self.cli("persist-slice", "--json", "-", "--wave", "2",
                                    "--ts", TS, stdin=json.dumps(sidecar()))
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])

    def test_persist_slice_invalid_is_exit_one_with_errors(self):
        body = sidecar()
        del body["tests"]
        code, payload, _ = self.cli("persist-slice", "--json",
                                    self.sidecar_file(body), "--wave", "1", "--ts", TS)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["errors"])
        self.assertFalse(os.path.exists(
            os.path.join(self.run_dir, "slice-s1-status.json")))

    def test_persist_slice_unreadable_json_is_exit_two(self):
        code, payload, err = self.cli("persist-slice", "--json",
                                      os.path.join(self.root, "nope.json"),
                                      "--wave", "1", "--ts", TS)
        self.assertEqual(code, 2)
        self.assertIsNone(payload)
        self.assertIn("error:", err)

    def test_bad_timestamp_is_exit_two(self):
        code, _, err = self.cli("persist-slice", "--json",
                                self.sidecar_file(sidecar()),
                                "--wave", "1", "--ts", "yesterday")
        self.assertEqual(code, 2)
        self.assertIn("ts", err)

    def test_append_event_cli(self):
        code, payload, _ = self.cli("append-event", "--ts", TS, "--scope", "s1",
                                    "--type", "decision", "--payload",
                                    '{"summary": "reuse the writer"}')
        self.assertEqual(code, 0)
        self.assertEqual(payload["type"], "decision")
        self.assertIn("reuse the writer", self.read("decisions-log.md"))

    def test_append_event_payload_from_stdin(self):
        code, _, _ = self.cli("append-event", "--ts", TS, "--scope", "phase5",
                              "--type", "phase5-gate", "--payload", "-",
                              stdin='{"result": "PASS"}')
        self.assertEqual(code, 0)
        self.assertIn("PHASE5-GATE", self.read("decisions-log.md"))

    def test_append_event_defaults_to_an_empty_payload(self):
        code, payload, _ = self.cli("append-event", "--ts", TS, "--scope", "run",
                                    "--type", "run-created")
        self.assertEqual(code, 0)
        self.assertEqual(payload["payload"], {})

    def test_append_event_rejects_a_non_object_payload(self):
        code, _, err = self.cli("append-event", "--ts", TS, "--scope", "run",
                                "--type", "decision", "--payload", '["a"]')
        self.assertEqual(code, 2)
        self.assertIn("object", err)

    def test_append_event_malformed_payload_is_exit_two(self):
        code, _, err = self.cli("append-event", "--ts", TS, "--scope", "run",
                                "--type", "decision", "--payload", "{nope")
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)

    def test_unreadable_sidecar_json_is_exit_two(self):
        path = os.path.join(self.root, "torn.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"schema_version": 2, "id')
        code, _, err = self.cli("validate-sidecar", "--file", path)
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)

    def test_append_event_requires_a_type(self):
        with self.assertRaises(SystemExit):
            self.cli("append-event", "--ts", TS, "--scope", "run")

    def test_open_escalations_cli(self):
        self.cli("append-event", "--ts", TS, "--scope", "s1", "--type",
                 "escalation-opened", "--payload", json.dumps(escalation()))
        code, payload, _ = self.cli("open-escalations")
        self.assertEqual(code, 0)
        self.assertEqual([r["id"] for r in payload], ["s1:review-block"])

    def test_open_escalations_empty_is_exit_zero(self):
        code, payload, _ = self.cli("open-escalations")
        self.assertEqual(code, 0)
        self.assertEqual(payload, [])

    def test_validate_sidecar_cli_ok(self):
        code, payload, _ = self.cli("validate-sidecar", "--file",
                                    self.sidecar_file(sidecar()))
        self.assertEqual(code, 0)
        self.assertEqual(payload, {"ok": True, "errors": []})

    def test_validate_sidecar_cli_failure(self):
        code, payload, _ = self.cli("validate-sidecar", "--file",
                                    self.sidecar_file(sidecar(status="NOPE")))
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])

    def test_validate_sidecar_reads_stdin(self):
        code, payload, _ = self.cli("validate-sidecar", "--file", "-",
                                    stdin=json.dumps(sidecar()))
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])

    def test_unknown_subcommand(self):
        with self.assertRaises(SystemExit):
            self.cli("teleport")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
