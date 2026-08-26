#!/usr/bin/env python3
"""Contract checks: durable deferred-scope events and the run-level scope
ceiling threaded into `packet()`.

See `slice_wave_contract_base.py` for the module-wide rationale, and
`test_slice_wave_contract.py` for the sibling module covering guarded
task-result reads, quality-gate-block answer injection, and the
record-only `over_scope` critique field (with
`test_slice_wave_contract_crash.py` covering `internal-error`). Split
purely to keep each
module's whole-file `class_lines` under the quality gate's 300-line
threshold; no test here depends on anything in the sibling.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_slice_wave_contract_scope.py'
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from slice_wave_contract_base import (
    ADVISORY_FILE_ANYWAY, ADVISORY_NOT_A_FILTER, BLOCKING_HELPER, CHARTS,
    CHARTS_EVENT, CLEAN_MEMBER_VERDICT, COMMAND_MD, CONCERN_MARKER,
    COUNCIL_VERDICT_EVENT, CTX_TRAVELS_LINE, DEFER_FILTER, DEFER_ME,
    DERIVE_INPUTS_DRIVER, DERIVE_INPUTS_FN, DEFERRAL_DRIVER,
    DEFERRAL_EMIT, DEFERRAL_HELPER, DEFERRAL_MARKER, DEFERRAL_MARKER_FALSE,
    DEFERRAL_PAYLOAD, DEFERRED_ARRAY, DEFERRED_TYPE, FLAGGING_MEMBER_VERDICT,
    FOLD_ME, GATE_PROMPT, HELPER_END, MARKED, NO_HINT, OPEN_SET, PACKET_END,
    PACKET_START, RECORD_DEFERRALS_CALL, RECORD_DEFERRALS_FN,
    RECORD_DEFERRALS_GUARDED, RECORD_DEFERRALS_ON_ENDORSE, REVIEW_PROMPT,
    SCOPE_CEILING_DRIVER, SCOPE_CEILING_HELPER, SCOPE_CEILING_READ,
    SCOPE_HELPER, SLICE, SPLIT_RETURN, STAGE_CRITIQUE_END,
    STAGE_CRITIQUE_START, STATE_DEFERRED, STATE_DEFERRED_INIT,
    THREE_DEFERRALS, UNMARKED, WorkflowSourceTestCase,
)


class TestDeferredScopeIsARecordNotAFilter(WorkflowSourceTestCase):
    """Requirement 5 asks for ONE durable human-facing record per deferred
    concern. The record is prose data: it reaches the reviewer as quoted
    context and it must be provably incapable of removing a finding, because
    the blocking set is the one thing this run may not touch."""

    def test_one_deferred_event_is_emitted_per_defer_hinted_concern(self):
        helper = self.between(DEFERRAL_HELPER, HELPER_END)
        self.assertIn(DEFER_FILTER, helper)
        self.assertIn(DEFERRED_TYPE, helper)
        self.assertIn(DEFERRAL_EMIT, self.src)

    def test_the_payload_leads_with_a_summary_key(self):
        # SUMMARY_TEXT_KEYS in run_state.py reads `summary` first, so the
        # decisions-log line is prose instead of a JSON blob.
        self.assertIn(DEFERRAL_PAYLOAD, self.between(DEFERRAL_HELPER, HELPER_END))

    def test_the_scope_marker_is_a_bare_boolean_true_and_omitted_otherwise(self):
        helper = self.between(DEFERRAL_HELPER, HELPER_END)
        self.assertIn(DEFERRAL_MARKER, helper)
        self.assertNotIn(DEFERRAL_MARKER_FALSE, helper)

    def test_each_concern_remembers_its_own_members_scope_judgement(self):
        self.assertIn(CONCERN_MARKER, self.src)

    def test_the_council_verdict_deferred_array_is_not_repurposed(self):
        # run_metrics.concerns_deferred is a live consumer of this array.
        self.assertIn(DEFERRED_ARRAY, self.line_containing(COUNCIL_VERDICT_EVENT))

    def test_the_prompt_only_deferred_list_is_initialised_with_the_state(self):
        # An uninitialised state field is a TypeError in reviewPrompt for
        # every tier-1 slice, which never runs Stage C at all.
        self.assertIn(STATE_DEFERRED_INIT, self.line_containing("tasksCompleted: 0"))

    def test_deferred_scope_reaches_the_reviewer_as_quoted_advisory_data(self):
        review = self.between(REVIEW_PROMPT, GATE_PROMPT)
        self.assertIn(STATE_DEFERRED, review)
        self.assertIn(ADVISORY_NOT_A_FILTER, review)
        self.assertIn(ADVISORY_FILE_ANYWAY, review)

    def test_nothing_filters_the_blocking_set_on_a_deferral(self):
        # NEVER DELETE A FINDING: blocking()'s output is untouched.
        blocking = self.between(BLOCKING_HELPER, HELPER_END)
        self.assertNotIn("defer", blocking)
        self.assertNotIn("over_scope", blocking)
        self.assertIn(OPEN_SET, self.src)


class TestDeferralsAreRecordedOnlyWhenThePlanProceeds(WorkflowSourceTestCase):
    """Regression: `deferralEvents(...).forEach` used to run unconditionally
    before every Stage-C early return, so a SPLIT (plan discarded, each
    grafted child re-critiques and emits its own events for the same
    concerns) and an unresolved council objection (plan never executed,
    re-appended on every resume - persist_slice/append_event de-duplicate
    nothing) both recorded a durable event for a plan that never ran.
    `recordDeferrals` must fire only on the two paths where `plan` actually
    reaches Stage T: the ENDORSE/ENDORSE_WITH_CONCERNS path, and an OBJECT
    path that `resolveCouncilObjection` actually resolved (answered or
    replanned), never on SPLIT or on an unresolved objection's escalation."""

    def stage_critique_body(self):
        return self.between(STAGE_CRITIQUE_START, STAGE_CRITIQUE_END)

    def test_the_split_return_precedes_any_deferral_recording(self):
        body = self.stage_critique_body()
        split_at = body.find(SPLIT_RETURN)
        self.assertNotEqual(
            split_at, -1, "missing anchor %r" % (SPLIT_RETURN,))
        first_record_at = body.find(RECORD_DEFERRALS_CALL)
        self.assertNotEqual(
            first_record_at, -1, "missing anchor %r" % (RECORD_DEFERRALS_CALL,))
        note = ("a defer-hinted concern must not be recorded before the "
                "SPLIT branch already returned")
        self.assertLess(split_at, first_record_at, note)

    def test_the_split_branch_itself_never_calls_recordDeferrals(self):
        split_line = self.line_containing(SPLIT_RETURN)
        self.assertNotIn("recordDeferrals", split_line)

    def test_the_endorsed_path_records_before_returning_the_plan(self):
        self.assertIn(RECORD_DEFERRALS_ON_ENDORSE, self.src)

    def test_the_objection_path_records_only_when_it_actually_resolved(self):
        # An unresolved objection's `stop` means the plan never executed;
        # recording here would file a deferral for a plan that only ever
        # escalates and resumes.
        self.assertIn(RECORD_DEFERRALS_GUARDED, self.src)

    def test_recordDeferrals_is_the_single_place_that_pushes_deferred_events(self):
        self.assertEqual(self.src.count(DEFERRAL_EMIT), 1)
        helper = self.between(RECORD_DEFERRALS_FN, HELPER_END)
        self.assertIn(DEFERRAL_EMIT, helper)


class TestDeferralEventsBehavesAndNotJustExists(WorkflowSourceTestCase):
    """The source assertions above prove the lines are present. This one
    extracts deferralEvents() and runs it under real node, because the two
    failures that matter are behavioural: emitting an event for a concern the
    council wanted FOLDED (work silently dropped), and emitting the scope
    marker on a concern nobody flagged (a false scope claim in the log)."""

    def deferral_events(self, cases):
        """deferralEvents() applied to each [slice, concerns] pair by node."""
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available on this machine")
        source = self.between(DEFERRAL_HELPER, HELPER_END) + "\n}"
        fd, path = tempfile.mkstemp(suffix=".mjs")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(DEFERRAL_DRIVER % (source, json.dumps(cases)))
            proc = subprocess.run(
                [node, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = proc.stdout.decode()
            self.assertEqual(proc.returncode, 0, "node failed:\n%s" % (out,))
            return json.loads(out)
        finally:
            os.unlink(path)

    def summaries(self, concerns):
        """Every summary deferralEvents() builds for one panel's concerns."""
        got = self.deferral_events([[SLICE, concerns]])[0]
        return [e["payload"]["summary"] for e in got]

    def test_only_defer_hinted_concerns_become_events(self):
        # A fold concern is work to do now; an unhinted one is neither.
        got = self.summaries([FOLD_ME, DEFER_ME, NO_HINT])
        self.assertEqual(got, ["defer me"])

    def test_a_deferred_concern_becomes_one_event_scoped_to_the_slice(self):
        got = self.deferral_events([[SLICE, [CHARTS]]])[0]
        self.assertEqual(got, [CHARTS_EVENT])

    def test_the_marker_is_present_only_on_the_flagging_members_concern(self):
        got = self.deferral_events([[SLICE, [MARKED, UNMARKED]]])[0]
        self.assertIs(got[0]["payload"]["over_scope"], True)
        self.assertNotIn("over_scope", got[1]["payload"])

    def test_a_council_with_no_deferrals_emits_nothing_at_all(self):
        got = self.deferral_events([[SLICE, [FOLD_ME]], [SLICE, []]])
        self.assertEqual(got, [[], []])

    def test_every_deferred_concern_gets_its_own_event_in_order(self):
        got = self.summaries(THREE_DEFERRALS)
        self.assertEqual(got, ["first", "second", "third"])


class TestDeriveCouncilInputsBroadcastsScopeAtTheProductionSite(WorkflowSourceTestCase):
    """Coverage gap this class closes: every other over_scope-marker test
    above (`test_the_marker_is_present_only_on_the_flagging_members_concern`
    included) drives `deferralEvents()` with fixture concerns that already
    carry `over_scope: True/False` set by hand - none of them ever run the
    real propagation at `deriveCouncilInputs`, the one production site that
    actually stamps a concern with its raising member's flag. This class
    extracts and runs `deriveCouncilInputs` itself (plus `scopeRecord`, which
    it calls) under real node, and pins the ACTUAL behaviour: a member with
    `over_scope.flag: true` marks BOTH of its own concerns, including one
    that has nothing to do with scope - this is member-level attribution
    broadcast onto every concern that member raised, not a per-concern
    judgement (see the docstring on `deriveCouncilInputs` in the workflow,
    the `deferred` payload bullet in run-state-v2.md, and the `_summarize`
    docstring in run_state.py for the same caveat spelled out for readers)."""

    def derive_concerns(self, verdict_lists):
        """deriveCouncilInputs(verdicts).concerns for each verdicts list, via
        real node running the extracted scopeRecord + deriveCouncilInputs
        source exactly as the workflow defines them."""
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available on this machine")
        scope_source = self.between(SCOPE_HELPER, HELPER_END) + "\n}"
        derive_source = self.between(DERIVE_INPUTS_FN, HELPER_END) + "\n}"
        source = scope_source + "\n" + derive_source
        fd, path = tempfile.mkstemp(suffix=".mjs")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(DERIVE_INPUTS_DRIVER % (source, json.dumps(verdict_lists)))
            proc = subprocess.run(
                [node, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = proc.stdout.decode()
            self.assertEqual(proc.returncode, 0, "node failed:\n%s" % (out,))
            return json.loads(out)
        finally:
            os.unlink(path)

    def test_a_flagging_members_unrelated_concern_is_marked_over_scope_too(self):
        got = self.derive_concerns(
            [[FLAGGING_MEMBER_VERDICT, CLEAN_MEMBER_VERDICT]])[0]
        self.assertEqual(len(got), 3)
        # Both concerns raised by the flagging member - the on-topic one AND
        # the unrelated "needs a doc comment" one - are broadcast True.
        self.assertIs(got[0]["over_scope"], True)
        self.assertIs(got[1]["over_scope"], True)
        self.assertEqual(got[1]["text"], "the retry helper needs a doc comment")
        # The clean member's own concern is untouched by the other member's
        # flag: attribution does not leak across verdicts.
        self.assertIs(got[2]["over_scope"], False)


class TestTheRunScopeCeilingReachesEveryAgent(WorkflowSourceTestCase):
    """A ceiling in dag.json that reaches neither call site validates green,
    passes every test, and reaches no agent."""

    def test_the_packet_carries_the_ceiling(self):
        packet = self.between(PACKET_START, PACKET_END)
        self.assertIn(SCOPE_CEILING_READ, packet)
        self.assertIn("do NOT build these", packet)

    def test_the_read_goes_through_the_type_safe_helper_not_a_bare_field_access(self):
        # Regression: `(CTX.scope_ceiling || []).length` was null-safe but not
        # type-safe - truthy for a non-empty STRING too, and the very next
        # read (`.map(...)`) is undefined on a string, throwing a TypeError
        # that the catch-all now classifies as 'internal-error' - before crash
        # classification such errors were mislabeled as a budget escalation.
        # packet() must never touch `CTX.scope_ceiling` directly; only the
        # helper may.
        packet = self.between(PACKET_START, PACKET_END)
        self.assertNotIn("CTX.scope_ceiling", packet)
        self.assertIn(SCOPE_CEILING_READ, packet)
        helper = self.between(SCOPE_CEILING_HELPER, HELPER_END)
        self.assertIn("Array.isArray(raw)", helper)
        self.assertIn("typeof raw === 'string'", helper)

    def test_the_controller_builds_the_ctx_field(self):
        command = COMMAND_MD.read_text(encoding="utf-8")
        self.assertIn("scope_ceiling", command)
        # run-level, one home: never duplicated into the per-slice objects.
        self.assertIn(CTX_TRAVELS_LINE, command)


class TestScopeCeilingListBehavesAndNotJustExists(WorkflowSourceTestCase):
    """The source assertions above prove the type-check lines are present.
    This one extracts scopeCeilingList() and runs it under real node with a
    non-array, non-string value - the wrong-type input the source-only
    pinned test never exercised, and the exact shape that broke the
    null-safe-but-not-type-safe original read."""

    def ceiling_for(self, cases):
        """scopeCeilingList() applied to each raw `ctx.scope_ceiling` value
        by real node, wrapped as `{scope_ceiling: <case>}` the way CTX is
        actually shaped."""
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available on this machine")
        source = self.between(SCOPE_CEILING_HELPER, HELPER_END) + "\n}"
        contexts = [{"scope_ceiling": c} for c in cases]
        fd, path = tempfile.mkstemp(suffix=".mjs")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(SCOPE_CEILING_DRIVER % (source, json.dumps(contexts)))
            proc = subprocess.run(
                [node, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = proc.stdout.decode()
            self.assertEqual(proc.returncode, 0, "node failed:\n%s" % (out,))
            return json.loads(out)
        finally:
            os.unlink(path)

    def test_an_absent_or_empty_ceiling_reads_as_an_empty_list(self):
        self.assertEqual(self.ceiling_for([None, []]), [[], []])

    def test_a_real_list_passes_through_unchanged(self):
        ceiling = [["dashboard charts", "v1 migration"]]
        self.assertEqual(self.ceiling_for(ceiling), ceiling)

    def test_a_lone_string_is_coerced_to_a_one_element_list(self):
        # The realistic malformed input: an LLM controller populating ctx
        # from prose writes one ceiling item as a bare string instead of
        # wrapping it in a list. Coerced, not dropped and not thrown on.
        self.assertEqual(self.ceiling_for(["dashboard charts"]), [["dashboard charts"]])

    def test_an_empty_string_reads_as_absent_not_as_one_blank_entry(self):
        self.assertEqual(self.ceiling_for([""]), [[]])

    def test_a_non_array_non_string_value_reads_as_absent_not_a_crash(self):
        # The wrong-type inputs a source-only test cannot exercise: node
        # actually running `.map` on any of these would throw if the guard
        # were missing, exactly reproducing the defect this helper fixes.
        self.assertEqual(self.ceiling_for([5, True, {"nope": True}]), [[], [], []])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
