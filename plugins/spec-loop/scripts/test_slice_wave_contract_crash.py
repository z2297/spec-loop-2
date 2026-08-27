#!/usr/bin/env python3
"""Contract checks: the `internal-error` classification of machine failures -
what the crash record names, what it refuses to claim, and whose job its
options are.

See `slice_wave_contract_base.py` for the module-wide rationale, and
`test_slice_wave_contract.py` for the sibling module covering guarded
task-result reads, quality-gate-block answer injection, and the
record-only `over_scope` critique field. Split purely to keep each
module's whole-file `class_lines` under the quality gate's 300-line
threshold; no test here depends on anything in the sibling.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_slice_wave_contract_crash.py'
"""

import re
import unittest

import dashboard_server
import run_metrics
import run_state
from slice_wave_contract_base import (
    ANSWERABLE_TRIGGERS, CRASH_BUDGET_DENIAL_OVERCLAIM, CRASH_CAUSE_OVERCLAIM,
    CRASH_CLASSIFICATION_SENTENCE, CRASH_CLASSIFIED_PASSTHROUGH,
    CRASH_ERROR_EXPR, CRASH_ERROR_FIRST,
    CRASH_GUARD_ORIGIN_OVERCLAIM, CRASH_HOST_LAYER_CAVEAT,
    CRASH_OPTION_CONTROLLER_ACTS,
    CRASH_OPTION_RETRY, CRASH_OPTION_SKIP, CRASH_OPTION_STOP,
    CRASH_STAGE_CAVEAT, CRASH_STAGE_CONTEXT, CRASH_STAGE_FALLBACK,
    CRASH_STAGE_OVERCLAIM,
    CRASH_STAGE_PRECISION, CRASH_TITLE_BRANCH, CRASH_TITLE_UNGRAMMATICAL,
    CRASH_TRIGGER, DISPATCH_GUARD_CALL, GUARD_BUDGET_TRIGGER,
    GUARD_FIRED_OVERCLAIM, SLICE_LOST_CAUSE_DENIAL,
    SLICE_LOST_CAUSE_UNKNOWN, SLICE_LOST_GUARD_PROVABLE,
    SLICE_LOST_RECORD, STAGE_ASSIGNMENT,
    STATE_STAGE_INIT, TRIGGER_ENUM_LINE,
    WorkflowSourceTestCase,
)

# A real crash message from run 20260825-scope-ceiling, and the LONGEST stage
# text the fallback can interpolate (the no-dispatch phrase, longer than any
# role name), so the render check below measures the worst realistic case.
SAMPLE_MESSAGE = "Cannot read properties of undefined (reading 'head')"
LONGEST_STAGE = "none (the crash happened before any agent was dispatched)"
# The template's LAST sentence. It is evicted by the renderer's truncation at
# this worst-case length, which is what makes the ordering assertion below a
# real constraint rather than a tautology.
CONTEXT_TAIL = "task(s) had already completed"


class TestTheCrashRecordNamesTheLastDispatchedStage(WorkflowSourceTestCase):
    """A crash record carrying only an exception string sent run
    20260825-scope-ceiling's controller looking for a budget problem. The
    cheapest honest signal is the LAST DISPATCHED role - state.stage is
    never cleared and dispatch() may fan out via parallel(), so it is not
    a per-throw stage and the record must not claim to be one."""

    def test_slice_state_initialises_a_stage_field(self):
        init = self.between("function initSliceState(slice) {", "function doneResult(")
        self.assertIn(STATE_STAGE_INIT, init)

    def test_dispatch_records_the_role_only_after_the_guards_pass(self):
        # A cap or token-floor rejection must not advance state.stage to a
        # role that never dispatched, so the assignment follows guard().
        fn = self.between(
            "async function dispatch(slice, state, role, prompt, opts) {",
            "// ── The slice pipeline")
        self.assertIn(STAGE_ASSIGNMENT, fn)
        self.assertLess(fn.index(DISPATCH_GUARD_CALL), fn.index(STAGE_ASSIGNMENT))


class TestCrashesAreClassifiedAsInternalError(WorkflowSourceTestCase):
    """Regression, run 20260825-scope-ceiling: the catch-all relabelled every
    unclassified JS exception as `budget-exhausted` 'wave interrupted', so a
    TypeError read as a resource limit and the controller spent ~85 and ~76
    minutes diagnosing in the wrong direction (the HUMAN answered both in
    ~1 min - the cost was misdirected diagnosis, not human waiting). The
    catch-all now says machine failure, names the last dispatched stage, and offers
    controller actions instead of 'raise budget/caps'."""

    def crash_fallback(self):
        return self.between(
            "function runSliceError(slice, state, e) {",
            "async function runSlice(slice) {")

    def test_the_catch_all_emits_internal_error_not_budget_exhausted(self):
        fallback = self.crash_fallback()
        self.assertIn(CRASH_TRIGGER, fallback)
        self.assertNotIn(GUARD_BUDGET_TRIGGER, fallback)

    def test_a_classified_throw_still_passes_through_unchanged(self):
        # The two structural guards throw {escRecord} with their own
        # budget-exhausted record; reclassifying those would be a regression.
        self.assertIn(CRASH_CLASSIFIED_PASSTHROUGH, self.crash_fallback())

    def test_the_crash_record_names_the_last_dispatched_stage_without_overclaiming(self):
        fallback = self.crash_fallback()
        self.assertIn(CRASH_STAGE_FALLBACK, fallback)
        self.assertIn(CRASH_STAGE_CONTEXT, fallback)
        self.assertIn(CRASH_STAGE_PRECISION, fallback)
        self.assertNotIn(CRASH_STAGE_OVERCLAIM, fallback)

    def test_the_crash_record_carries_the_real_exception_text(self):
        self.assertIn("String((e && e.message) || e)", self.crash_fallback())

    def test_the_crash_record_claims_only_what_the_code_can_prove(self):
        # The fallback catches EVERY throw without an escRecord, which includes
        # host- and agent-layer resource failures that never reach guard(): a
        # rejected agent(...) promise on a hard token or rate limit, or a throw
        # from budget.remaining() itself. Asserting "bug, NOT a budget limit"
        # would be the same unprovable assertion as the "budget" label this
        # trigger replaced, just pointing the other way.
        fallback = self.crash_fallback()
        self.assertNotIn(CRASH_CAUSE_OVERCLAIM, fallback)
        self.assertNotIn(CRASH_BUDGET_DENIAL_OVERCLAIM, fallback)
        self.assertIn(CRASH_CLASSIFICATION_SENTENCE, fallback)
        self.assertIn(CRASH_HOST_LAYER_CAVEAT, fallback)

    def test_the_record_claims_only_that_neither_guard_raised_a_record(self):
        # A fourth instance of the same pattern, one level subtler:
        # `budget.remaining()` is called INSIDE the token-floor guard, so a
        # throw from there ORIGINATES in a guard and still arrives with no
        # escRecord. All the escRecord check proves is that neither guard
        # RAISED its record - never that the crash came from outside them.
        fallback = self.crash_fallback()
        self.assertIn(CRASH_CLASSIFICATION_SENTENCE, fallback)
        self.assertNotIn(CRASH_GUARD_ORIGIN_OVERCLAIM, fallback)

    def test_the_title_is_grammatical_when_no_agent_was_dispatched(self):
        # This title is an escalations.md heading and the dashboard label for
        # the crash shape with the LEAST operator context; interpolating the
        # no-dispatch fallback phrase after "after" rendered as "slice crashed
        # after before any agent was dispatched".
        fallback = self.crash_fallback()
        self.assertIn(CRASH_TITLE_BRANCH, fallback)
        self.assertNotIn(CRASH_TITLE_UNGRAMMATICAL, fallback)

    def test_every_option_says_the_controller_must_act_on_it(self):
        # internal-error is not in ANSWERABLE_TRIGGERS and the controller's
        # step 7 re-dispatches every non-DONE slice, so nothing in the loop
        # enforces skip or stop. Each detail says whose job it is.
        fallback = self.crash_fallback()
        self.assertEqual(fallback.count(CRASH_OPTION_CONTROLLER_ACTS), 3)
        self.assertEqual(fallback.count("recommended: true"), 1)
        self.assertLess(
            fallback.index(CRASH_OPTION_RETRY), fallback.index("recommended: true"))

    def test_the_options_are_controller_actions_not_resource_requests(self):
        fallback = self.crash_fallback()
        self.assertIn(CRASH_OPTION_RETRY, fallback)
        self.assertIn(CRASH_OPTION_SKIP, fallback)
        self.assertIn(CRASH_OPTION_STOP, fallback)
        self.assertNotIn("Raise budget/caps", fallback)

    def test_the_structural_guards_keep_their_budget_exhausted_wording(self):
        guard = self.between(
            "function guard(slice, state) {", "async function dispatch(")
        self.assertIn("agent cap reached", guard)
        self.assertIn("token budget exhausted", guard)
        self.assertEqual(guard.count(GUARD_BUDGET_TRIGGER), 2)

    def test_internal_error_is_not_injected_into_any_prompt(self):
        # Mirror of test_budget_exhausted_is_still_not_injected_anywhere: a
        # crash answer is a controller action (retry / skip / stop), so there
        # is nothing for an agent prompt to apply. It is deliberately NOT in
        # ANSWERABLE_TRIGGERS.
        self.assertNotIn("answerFor(slice, 'internal-error')", self.src)
        self.assertNotIn("internal-error", str(ANSWERABLE_TRIGGERS))

    def test_the_real_exception_text_leads_the_context_not_the_boilerplate(self):
        fallback = self.crash_fallback()
        error_at = fallback.index(CRASH_ERROR_FIRST)
        stage_at = fallback.index(CRASH_STAGE_CONTEXT)
        prose_at = fallback.index(CRASH_CLASSIFICATION_SENTENCE)
        self.assertLess(error_at, stage_at)
        self.assertLess(stage_at, prose_at)

    def crash_context(self):
        """The shipped context template literal, backticks stripped."""
        fallback = self.crash_fallback()
        start = fallback.index(CRASH_ERROR_FIRST)
        return fallback[start + 1:fallback.index("`,", start)]

    def rendered_crash_context(self, message, stage_text):
        """The `- Context:` line escalations.md actually receives, produced by
        the REAL run_state.render_escalation(). Re-implementing its collapse
        and truncate here protected nothing: the copy sliced unconditionally
        and appended no ellipsis, so it disagreed with _one_line() on two of
        its three behaviours and could not have caught a change to either."""
        filled = self.crash_context().replace(CRASH_ERROR_EXPR, message)
        filled = filled.replace("${stageText}", stage_text)
        filled = filled.replace("${state.tasksCompleted}", "2")
        record = {"id": "s1:internal-error", "trigger": "internal-error",
                  "title": "slice crashed", "context": filled,
                  "question": "Retry, skip, or stop."}
        section = run_state.render_escalation("s1", record)
        lines = section.splitlines()
        return next(line for line in lines if line.startswith("- Context: "))

    def test_the_stage_attribution_survives_the_real_context_render(self):
        # run_state.render_escalation() collapses the context and truncates it
        # through _one_line(), so anything past that budget never reaches
        # escalations.md - which is also the corpus a later run's
        # escalation-gate precedent check reads. The stage attribution is this
        # record's headline diagnostic and the title asserts it, so it and its
        # caveat must sit inside the budget, ahead of the fixed prose. The
        # budget is not named here: the assertion runs the real renderer, so
        # the test cannot drift from whatever limit render_escalation applies.
        rendered = self.rendered_crash_context(SAMPLE_MESSAGE, LONGEST_STAGE)
        attribution = CRASH_STAGE_CONTEXT.replace("${stageText}", LONGEST_STAGE)
        self.assertIn(SAMPLE_MESSAGE, rendered)
        self.assertIn(attribution, rendered)
        self.assertIn(CRASH_STAGE_CAVEAT, rendered)
        self.assertNotIn(CONTEXT_TAIL, rendered)

    def test_a_lost_slice_is_an_internal_error_too(self):
        # parallel() resolved the thunk to null: the slice died with no result
        # at all, outside runSlice's try/catch. Same one classification, per
        # the run's human-decided single-value constraint; the honest 'slice
        # lost' title and its own question are kept.
        wave_entry = self.between(
            "const results = await parallel(", "log(`wave ")
        self.assertIn(SLICE_LOST_RECORD, wave_entry)
        self.assertIn("Re-run the wave to retry this slice?", wave_entry)
        self.assertNotIn("'budget-exhausted'", wave_entry)

    def test_the_lost_slice_record_denies_no_cause_it_cannot_prove(self):
        # Same rule as the crash record, third instance of the pattern: a
        # thunk that resolved to null says nothing about WHY, so asserting
        # "Not a resource limit" is as unprovable as the "budget" label this
        # trigger replaced. A host- or agent-layer rejection dies this way too.
        wave_entry = self.between(
            "const results = await parallel(", "log(`wave ")
        self.assertNotIn(SLICE_LOST_CAUSE_DENIAL, wave_entry)
        self.assertIn(CRASH_HOST_LAYER_CAVEAT, wave_entry)

    def test_the_lost_slice_record_claims_only_that_no_guard_record_came_back(self):
        # Fifth instance, and the sibling of the crash record's: a guard that
        # "fired" asserts its CHECK never ran, which a null result cannot show.
        # A throw from inside `budget.remaining()` ORIGINATES in the token-floor
        # guard and still arrives with no escRecord, so both records may claim
        # only that no guard RAISED one. Forbidden across the whole source so
        # neither record can reintroduce it.
        wave_entry = self.between(
            "const results = await parallel(", "log(`wave ")
        self.assertIn(SLICE_LOST_GUARD_PROVABLE, wave_entry)
        self.assertIn(SLICE_LOST_CAUSE_UNKNOWN, wave_entry)
        self.assertNotIn(GUARD_FIRED_OVERCLAIM, self.src)


class TestTheTriggerEnumAgreesAcrossAllFiveHomes(WorkflowSourceTestCase):
    """The enum has five homes and no test held them against each other.
    `run_state.persist_slice` validates the whole SliceResult BEFORE it writes
    anything and raises on an unrecognised trigger, so a value missing from one
    tuple costs an affected slice its sidecar, its events and its report - not
    a mislabelled field. A one-home edit would otherwise stay fully green."""

    def triggers(self):
        return run_state.ESCALATION_TRIGGERS

    def test_the_three_python_tuples_are_identical(self):
        self.assertEqual(run_metrics.ESCALATION_TRIGGERS, self.triggers())
        self.assertEqual(dashboard_server.ESCALATION_TRIGGERS, self.triggers())

    def test_the_workflow_enum_carries_exactly_those_values_in_order(self):
        enum_line = self.line_containing(TRIGGER_ENUM_LINE)
        self.assertEqual(tuple(re.findall(r"'([^']+)'", enum_line)),
            self.triggers())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
