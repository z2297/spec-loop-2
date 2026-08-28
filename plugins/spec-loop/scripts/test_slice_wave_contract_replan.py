#!/usr/bin/env python3
"""Contract checks for the post-OBJECT replan re-check and the last three
unguarded optional agent-return reads.

Two facts this pins that a behavioural test cannot: that the re-check sits on
the ONLY path out of a replan (a future edit adding a second `return { plan:
revised }` would restore the leak while every behavioural test still passed),
and that each guard reaches its comparison through an explicit null/type test
rather than by coercion.

A fifth `test_slice_wave_contract*.py` module rather than a class in an
existing one: `slice_wave_contract_base.py` is at 299 non-blank lines and its
four current importers are at 240-292, against a whole-file `class_lines`
threshold of 300. Every pinned snippet below is a module-level constant, not a
literal in a test body, because quality_gate.py's metrics are line-based and a
`&&` inside a string literal scores as real branching.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_slice_wave_contract_replan.py'
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from slice_wave_contract_base import WorkflowSourceTestCase  # noqa: E402

FIX_COMMITS = ("const fixCommits = (fix) => "
               "(fix && typeof fix.commits === 'object' && fix.commits) ? fix.commits : {}")
USABLE_SPLIT = ("const usableSplit = (s) => !!s && typeof s === 'object' "
                "&& Array.isArray(s.children) && s.children.length > 0")
IS_REVISED = ("const isRevisedPlan = (r) => !!r && typeof r === 'object' "
              "&& r.status === 'PLANNED'")
OBJECTION_SOURCE = ("const objectionSource = (v, fallback) => "
                    "(v && v.objection && typeof v.objection.reason === 'string') ? v : fallback")
PLAN_ESCALATION = "function planEscalation(slice, plan) {"
GUARDED_ESC_LOCAL = ("const e = (plan.escalation && typeof plan.escalation === 'object') "
                     "? plan.escalation : {}")
GUARDED_TRIGGER = ("const trigger = (typeof e.trigger === 'string' && e.trigger) "
                   "? e.trigger : 'ambiguity'")
SPLIT_BRANCH = "if (plan.status === 'SPLIT') return { stop: splitResult(slice, state, plan) }"
ESC_BRANCH = ("if (plan.status === 'ESCALATE') return "
              "{ stop: escalated(slice, state, planEscalation(slice, plan)) }")
RECRITIQUE_FN = "async function recritiqueRevisedPlan(slice, state, plan) {"
RECRITIQUE_ROLE = "'critic:replan'"
RECRITIQUE_AGENT = "agentType: 'spec-loop:plan-critic', schema: CRITIQUE"
FAIL_CLOSED_RECHECK = "return v || failClosedCritique()"
ACCEPT_FN = "async function acceptRevisedPlan(slice, state, ctx) {"
ACCEPT_END = "\n}\n"
REPLAN_HANDOFF = "return acceptRevisedPlan(slice, state, { revised, ob, safety })"
RECHECK_EVENT = "type: 'replan-recheck'"
SAFETY_GUARD = "const flagged = !!(rc.safety && rc.safety.flag === true)"
ACCEPTED_GUARD = "const accepted = rc.verdict !== 'OBJECT' && !flagged"
LEAKY_ACCEPT = "revised.status === 'PLANNED'"
RADIUS_GATE_CALL = "refactorRadiusGate("


# ---- the three optional-read guards ----
class TestTheLastOptionalReadsAreGuarded(WorkflowSourceTestCase):
    """Each of the three reads that PLAN_RESULT/FIX_RESULT never promised now
    runs through a type guard, and the raw read is gone from the file."""

    def test_the_fix_result_commits_read_goes_through_a_type_guard(self):
        self.assertIn(FIX_COMMITS, self.src)

    def test_no_bare_fix_commits_base_read_survives_anywhere(self):
        self.assertNotIn("fix.commits.base", self.src)

    def test_the_split_branch_routes_through_the_usable_split_predicate(self):
        self.assertIn(USABLE_SPLIT, self.src)
        self.assertIn(SPLIT_BRANCH, self.src)

    def test_the_escalate_branch_never_reads_the_trigger_off_a_bare_plan(self):
        self.assertIn(ESC_BRANCH, self.src)
        self.assertNotIn("plan.escalation.trigger", self.src)

    def test_the_planner_escalation_builder_guards_the_object_then_the_field(self):
        body = self.between(PLAN_ESCALATION, "\n}\n")
        self.assertIn(GUARDED_ESC_LOCAL, body)
        self.assertIn(GUARDED_TRIGGER, body)
        self.assertLess(body.index(GUARDED_ESC_LOCAL), body.index(GUARDED_TRIGGER))


# ---- the re-check on the replan path ----
class TestARevisedPlanIsRecheckedAndNotAcceptedOnStatus(WorkflowSourceTestCase):
    """The leak this closes: a well-formed revision used to be accepted on
    `status === 'PLANNED'` alone, so one silent retry absorbed the objection."""

    def test_the_replan_dispatch_hands_off_to_the_acceptance_helper(self):
        self.assertIn(REPLAN_HANDOFF, self.src)

    def test_no_status_only_acceptance_of_a_revision_survives(self):
        self.assertNotIn(LEAKY_ACCEPT, self.src)

    def test_the_recheck_dispatches_one_plan_critic_seat_on_the_revision(self):
        body = self.between(RECRITIQUE_FN, "\n}\n")
        self.assertIn(RECRITIQUE_ROLE, body)
        self.assertIn(RECRITIQUE_AGENT, body)

    def test_an_unreadable_recheck_falls_back_to_the_fail_closed_verdict(self):
        self.assertIn(FAIL_CLOSED_RECHECK, self.between(RECRITIQUE_FN, "\n}\n"))

    def test_the_acceptance_helper_has_exactly_one_proceed_return(self):
        body = self.between(ACCEPT_FN, ACCEPT_END)
        self.assertEqual(body.count("return { plan: revised }"), 1)

    def test_the_only_proceed_return_is_reached_after_the_recheck(self):
        body = self.between(ACCEPT_FN, ACCEPT_END)
        self.assertLess(body.index("recritiqueRevisedPlan("), body.index("return { plan: revised }"))

    def test_the_recheck_records_one_event_naming_the_verdict_it_reached(self):
        self.assertIn(RECHECK_EVENT, self.between(ACCEPT_FN, ACCEPT_END))


# ---- no verdict by coercion ----
class TestNoAcceptanceIsReachedByCoercion(WorkflowSourceTestCase):
    """Every acceptance predicate compares an explicitly typed value: a plan is
    a plan only on the literal status string, and a safety flag counts only on
    a literal `true`."""

    def test_a_revision_is_a_plan_only_on_an_explicit_object_and_status_test(self):
        self.assertIn(IS_REVISED, self.src)

    def test_the_recheck_safety_flag_is_compared_to_a_literal_true(self):
        self.assertIn(SAFETY_GUARD, self.src)

    def test_acceptance_names_both_halves_and_neither_is_truthiness(self):
        self.assertIn(ACCEPTED_GUARD, self.src)

    def test_the_objection_carried_to_the_human_guards_the_optional_block(self):
        self.assertIn(OBJECTION_SOURCE, self.src)


# ---- the honest limit ----
class TestTheRadiusGateIsNotReRunOnARevision(WorkflowSourceTestCase):
    """A deliberate, logged gap this run does NOT close: the plan-time refactor
    radius is evaluated once, in stagePlan, and a revision is not re-measured.
    Pinned so that closing it later is a visible decision, not a drift."""

    def test_the_radius_gate_is_called_from_exactly_one_place(self):
        self.assertEqual(self.src.count(RADIUS_GATE_CALL), 2)  # definition + one call

    def test_the_acceptance_helper_does_not_call_the_radius_gate(self):
        self.assertNotIn(RADIUS_GATE_CALL, self.between(ACCEPT_FN, ACCEPT_END))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
