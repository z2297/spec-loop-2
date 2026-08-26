#!/usr/bin/env python3
"""Contract checks: guarded task-result reads, quality-gate-block answer
injection, and the record-only `over_scope` critique field.

See `slice_wave_contract_base.py` for the module-wide rationale (why this
is source-text assertion, why snippets are named constants, and the two
known-and-deliberately-unguarded instances this module does NOT claim to
cover). `test_slice_wave_contract_scope.py` is this module's sibling,
covering the deferred-event and run-scope-ceiling concerns - split out
purely to keep each module's whole-file `class_lines` under the quality
gate's 300-line threshold; no test here depends on anything in the sibling.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_slice_wave_contract.py'
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from slice_wave_contract_base import (
    ANSWER_CONTEXT_END, ANSWER_CONTEXT_START, ANSWERABLE_TRIGGERS, CLEAN,
    COUNCIL_VERDICT_EVENT, CRASH_CLASSIFIED_PASSTHROUGH, CRASH_OPTION_RETRY,
    CRASH_OPTION_SKIP, CRASH_OPTION_STOP, CRASH_STAGE_FALLBACK, CRASH_TRIGGER,
    CRITIQUE_REQUIRED, CRITIQUE_ROLLUP,
    FAIL_CLOSED_DEFAULT, FINDING_CATEGORIES, FLAGGED, GATE_ANSWER,
    GATE_ANSWER_CONTEXT, GUARD_BUDGET_TRIGGER, GUARDED_BASE, GUARDED_CONCERNS,
    GUARDED_DEVIATIONS,
    GUARDED_HEAD, GUARDED_LOCAL, GUARDED_TOUCHED, HELPER_END,
    NO_COMMITS_ESCALATION, OBJECTION_SELECTION, OVER_SCOPE_DEFAULT,
    OVER_SCOPE_SCHEMA, REPLAN_VETO, SCOPE_DRIVER, SCOPE_HELPER, SCOPE_LOCAL,
    SCOPE_REASON_KEPT, SCOPE_SPREAD, SIDECAR_SCOPE_ATTACH, SLICE_LOST_RECORD,
    SPLIT_SUPPRESSION, STAGE_ASSIGNMENT, STATE_STAGE_INIT, TASK_LOOP_END,
    TASK_LOOP_START, TASK_RESULT_REQUIRED,
    WorkflowSourceTestCase, wrapped_source,
)


class TestTheFileStillParses(unittest.TestCase):
    def test_node_parses_the_wrapped_workflow_source(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available on this machine")
        fd, path = tempfile.mkstemp(suffix=".mjs")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(wrapped_source())
            proc = subprocess.run(
                [node, "--check", path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(
                proc.returncode, 0,
                "node --check failed:\n%s" % (proc.stdout.decode(),))
        finally:
            os.unlink(path)


class TestOptionalTaskResultReadsAreGuarded(WorkflowSourceTestCase):
    """Regression, run 20260825-scope-ceiling wave 2: TASK_RESULT does not
    require `commits`, so a task that legitimately committed nothing returned
    DONE with the key absent. `state.commits.head = r.commits.head` threw a
    TypeError, the catch-all re-labelled it 'wave interrupted' /
    budget-exhausted, and a wave whose five tasks had all committed was
    reported as a resource failure."""

    def task_loop(self):
        """The Stage-T task-result-handling region (runTask() and its small
        helpers, through stageTasks()'s loop), where every task-result read
        happens."""
        return self.between(TASK_LOOP_START, TASK_LOOP_END)

    def test_commits_is_not_required_by_the_task_result_schema(self):
        # The premise of the guard: absent `commits` is a legal DONE return.
        required = self.line_containing(TASK_RESULT_REQUIRED)
        self.assertNotIn("commits", required)

    def test_no_unguarded_commits_head_read_survives_anywhere(self):
        self.assertNotIn("r.commits.head", self.src)
        self.assertNotIn("r.commits.base", self.src)

    def test_the_task_loop_reads_commits_through_a_guarded_local(self):
        loop = self.task_loop()
        self.assertIn(GUARDED_LOCAL, loop)
        self.assertIn(GUARDED_HEAD, loop)
        self.assertIn(GUARDED_BASE, loop)

    def test_the_sibling_optional_arrays_are_read_defensively_too(self):
        loop = self.task_loop()
        self.assertIn(GUARDED_TOUCHED, loop)
        self.assertIn(GUARDED_CONCERNS, loop)
        self.assertIn(GUARDED_DEVIATIONS, loop)

    def test_a_slice_where_no_task_committed_still_reaches_its_escalation(self):
        # The guard must not paper over the real "nothing was built" case:
        # head stays null and the existing handler below the loop fires.
        self.assertIn(TASK_LOOP_END, self.src)
        self.assertIn(NO_COMMITS_ESCALATION, self.src)


class TestQualityGateBlockAnswersHaveAnInjectionPath(WorkflowSourceTestCase):
    """A quality-gate-block escalation had no answerFor() site, so a human
    answer could not be carried by the re-dispatch: this run's controller
    hand-resolved one twice. The fix loop (fixPrompt) can legitimately act on
    such an answer, so it gets the real answerFor() (apply it). The Stage-Z
    reporter (verifyPrompt -> spec-loop:verifier) cannot: it is transcription
    -only ("you never return a PASS/FAIL label"), so an "apply it" answer
    there has no lawful effect except a mis-transcribed false pass. It gets
    answerContext() instead: the human's answer is still carried into the
    resumed dispatch (so it is not silently lost / re-asked), but worded as
    context only, never as an instruction to change what gets reported."""

    def test_every_human_answerable_trigger_has_at_least_one_injection_site(self):
        for trigger in ANSWERABLE_TRIGGERS:
            self.assertIn(
                "answerFor(slice, '%s')" % (trigger,), self.src,
                "%s has no answer injection path" % (trigger,))

    def test_the_fix_prompt_carries_the_gate_answer(self):
        fix = self.between("function fixPrompt(", "function reReviewPrompt(")
        self.assertIn(GATE_ANSWER, fix)

    def test_the_verify_prompt_carries_the_gate_answer_as_context_only(self):
        verify = self.between("function verifyPrompt(", "function debugFixPrompt(")
        self.assertIn(GATE_ANSWER_CONTEXT, verify)
        self.assertNotIn(GATE_ANSWER, verify)

    def test_the_context_only_answer_never_instructs_the_reporter_to_apply_it(self):
        answer_context_fn = self.between(ANSWER_CONTEXT_START, ANSWER_CONTEXT_END)
        self.assertNotIn("apply it", answer_context_fn)

    def test_budget_exhausted_is_still_not_injected_anywhere(self):
        # It asks for a resource, not a decision (escalation-gate SKILL.md):
        # there is nothing for a prompt to apply.
        self.assertNotIn("answerFor(slice, 'budget-exhausted')", self.src)


class TestOverScopeIsRecordOnly(WorkflowSourceTestCase):
    """The flag is a record, not a vote. Requirement 4 of this run is 'flag
    it AND build it': a flag that reached any of the four council branches
    would turn recording into work-dropping."""

    def test_over_scope_is_an_optional_critique_field(self):
        self.assertIn(OVER_SCOPE_SCHEMA, self.src)
        required = self.line_containing(CRITIQUE_REQUIRED)
        self.assertNotIn("over_scope", required)

    def test_the_fail_closed_default_supplies_the_field(self):
        # Extended BEFORE any read exists: an unguarded read of a missing
        # optional field throws, is swallowed by the catch-all, and is
        # mislabelled as a budget escalation - the defect that killed wave 2.
        default = self.line_containing(FAIL_CLOSED_DEFAULT)
        self.assertIn(OVER_SCOPE_DEFAULT, default)

    def test_the_read_goes_through_the_pure_helper_not_a_bare_field_access(self):
        helper = self.between(SCOPE_HELPER, HELPER_END)
        self.assertIn("typeof v.over_scope.flag === 'boolean'", helper)
        self.assertIn(SCOPE_LOCAL, self.src)

    def test_the_verdict_rollup_does_not_read_the_scope_record(self):
        self.assertNotIn("over_scope", self.line_containing(CRITIQUE_ROLLUP))

    def test_the_split_suppression_condition_does_not_read_it(self):
        self.assertNotIn("over_scope", self.line_containing(SPLIT_SUPPRESSION))

    def test_the_objection_selection_does_not_read_it(self):
        self.assertNotIn("over_scope", self.line_containing(OBJECTION_SELECTION))

    def test_the_replan_veto_does_not_read_it(self):
        self.assertNotIn("over_scope", self.line_containing(REPLAN_VETO))

    def test_scope_is_never_a_finding_category(self):
        # blocking() filters on severity alone, so a scope finding would
        # block at Tier 2 and Tier 3.
        categories = self.line_containing(FINDING_CATEGORIES)
        self.assertNotIn("scope", categories)

    def test_the_council_verdict_payload_carries_flag_and_reason(self):
        payload = self.line_containing(COUNCIL_VERDICT_EVENT)
        self.assertIn(SCOPE_SPREAD, payload)
        self.assertIn("deferred:", payload)  # the machine channel survives
        helper = self.between(SCOPE_HELPER, HELPER_END)
        self.assertIn(SCOPE_REASON_KEPT, helper)

    def test_the_sidecar_critique_carries_the_record_after_the_rollup(self):
        # The record is attached on its OWN statement, AFTER the rollup
        # literal, never spread into it: the binding RECORD-ONLY constraint
        # forbids the flag from appearing in the verdict rollup line at all.
        # This checks relative ORDER, not mere presence - a source-level
        # swap of the two statements would silently discard the attached
        # record every time (plain object-literal assignment overwrites),
        # and a presence-only assertion would not catch that swap.
        rollup_at = self.src.find(CRITIQUE_ROLLUP)
        attach_at = self.src.find(SIDECAR_SCOPE_ATTACH)
        self.assertNotEqual(
            rollup_at, -1, "missing anchor %r" % (CRITIQUE_ROLLUP,))
        self.assertNotEqual(
            attach_at, -1, "missing anchor %r" % (SIDECAR_SCOPE_ATTACH,))
        note = ("over_scope must be attached AFTER the verdict rollup "
                "statement, never before or spread into it")
        self.assertLess(rollup_at, attach_at, note)


class TestScopeRecordBehavesAndNotJustExists(WorkflowSourceTestCase):
    """Every other class here asserts source text, which proves a line is
    present and nothing about what it does. This one extracts scopeRecord()
    and runs it under real node, because the whole point of the field is the
    four outcomes run_state.py renders differently: no record at all, a clean
    record, a flagged record with its reason, and a malformed one. Collapsing
    any pair of those is a silent loss no substring assertion would catch."""

    def scope_record(self, panels):
        """scopeRecord() applied to each panel in turn, evaluated by node."""
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available on this machine")
        source = self.between(SCOPE_HELPER, HELPER_END) + "\n}"
        fd, path = tempfile.mkstemp(suffix=".mjs")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(SCOPE_DRIVER % (source, json.dumps(panels)))
            proc = subprocess.run(
                [node, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = proc.stdout.decode()
            self.assertEqual(proc.returncode, 0, "node failed:\n%s" % (out,))
            return json.loads(out)
        finally:
            os.unlink(path)

    def test_a_panel_that_recorded_nothing_readable_yields_no_record(self):
        # In order: no field at all; the fail-closed default's own `null`; a
        # flag that is not a boolean. None of the three is a scope judgement,
        # and inventing `flag: false` for them would be a false claim.
        self.assertEqual(
            self.scope_record([
                [{"verdict": "ENDORSE"}, {"verdict": "OBJECT"}],
                [{"over_scope": None}],
                [{"over_scope": {"flag": "yes"}}],
                [],
            ]),
            [None, None, None, None])

    def test_a_clean_record_is_kept_and_never_collapsed_into_absence(self):
        got = self.scope_record([[CLEAN]])
        self.assertEqual(got, [{"flag": False, "reason": None}])

    def test_a_flagged_record_wins_over_a_clean_one_in_either_order(self):
        both = self.scope_record([[CLEAN, FLAGGED], [FLAGGED, CLEAN]])
        self.assertEqual(both, [FLAGGED["over_scope"], FLAGGED["over_scope"]])

    def test_a_flag_without_a_reason_records_a_null_reason_not_undefined(self):
        # JSON.stringify drops an undefined value, so an unnormalised reason
        # would reach run_state.py as an absent key instead of an explicit null.
        got = self.scope_record([[{"over_scope": {"flag": True}}]])
        self.assertEqual(got, [{"flag": True, "reason": None}])


class TestTheCrashRecordCanNameTheStageInFlight(WorkflowSourceTestCase):
    """A crash record that carries only an exception string sent run
    20260825-scope-ceiling's controller looking for a budget problem. The
    cheapest honest signal for "what was in flight" is the last dispatched
    role, which dispatch() already receives."""

    def test_slice_state_initialises_a_stage_field(self):
        init = self.between("function initSliceState(slice) {", "function doneResult(")
        self.assertIn(STATE_STAGE_INIT, init)

    def test_dispatch_records_the_role_it_is_about_to_run(self):
        fn = self.between(
            "async function dispatch(slice, state, role, prompt, opts) {",
            "// ── The slice pipeline")
        self.assertIn(STAGE_ASSIGNMENT, fn)


class TestCrashesAreClassifiedAsInternalError(WorkflowSourceTestCase):
    """Regression, run 20260825-scope-ceiling: the catch-all relabelled every
    unclassified JS exception as `budget-exhausted` 'wave interrupted', so a
    TypeError read as a resource limit and the controller spent ~85 and ~76
    minutes diagnosing in the wrong direction (the HUMAN answered both in
    ~1 min - the cost was misdirected diagnosis, not human waiting). The
    catch-all now says machine failure, names the stage in flight, and offers
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

    def test_the_crash_record_names_the_stage_in_flight(self):
        fallback = self.crash_fallback()
        self.assertIn(CRASH_STAGE_FALLBACK, fallback)
        self.assertIn("${stage}", fallback)

    def test_the_crash_record_carries_the_real_exception_text(self):
        self.assertIn("String((e && e.message) || e)", self.crash_fallback())

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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
