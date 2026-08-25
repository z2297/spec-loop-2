#!/usr/bin/env python3
"""Executable contract checks on plugins/spec-loop/workflows/slice-wave.workflow.js.

The wave workflow is JavaScript and is not run by any lane of this repo's
suite: it is resolved at runtime from the installed plugin cache. Its
correctness has therefore rested entirely on review, and this run paid for
that twice - an unguarded optional-field read aborted a whole wave and was
mislabelled as a budget escalation. This module is the cheapest honest
coverage available: it parses the file with node (a real parse, not a
substring) and pins the handful of source facts whose loss is a known,
observed outage - the null-guards on optional agent-return fields, the
answer-injection sites, and the record-only isolation of the over-scope
flag from the four control-flow branches.

These are source-text assertions. They prove a guard is present; they
cannot prove it behaves. Any change to the workflow that trips one of them
is either a regression or an intentional contract change that belongs here
too.

Every pinned JS snippet is a module-level constant rather than a literal in
the test body, and continuation lines use a 4-space hanging indent. Both are
deliberate: quality_gate.py's heuristics are line-based, so a `&&` or an `if`
inside a string literal scores as real branching (cognitive_complexity) and a
paren-aligned continuation scores as real nesting (nesting_depth). Naming the
snippets keeps the assertions byte-exact while the metrics stay honest.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_slice_wave_contract.py'
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "slice-wave.workflow.js"
SOURCE = WORKFLOW.read_text(encoding="utf-8")
# The file has a top-level `return` and `export const` (it is executed by the
# Workflow tool inside an async wrapper), so `node --check` refuses it as-is.
# Wrapping it the way the runtime does is what makes a real parse possible.
WRAP_HEAD = "async function __wrap(){\n"
WRAP_TAIL = "\n}\n"

# Anchors and pinned source lines (see the module docstring for why these are
# constants and not literals inside the test bodies).
TASK_RESULT_REQUIRED = "required: ['status', 'touched_files', 'concerns', 'deviations']"
TASK_LOOP_START = "for (const task of plan.tasks || [])"
TASK_LOOP_END = "if (!state.commits.head)"
NO_COMMITS_ESCALATION = "'plan produced no commits'"
GUARDED_LOCAL = "const c = (r.commits && typeof r.commits === 'object') ? r.commits : {}"
GUARDED_HEAD = "if (c.head) state.commits.head = c.head"
GUARDED_BASE = "if (state.commits.base === null && c.base) state.commits.base = c.base"
GUARDED_TOUCHED = "touched.push(...(r.touched_files || []))"
GUARDED_CONCERNS = "...(r.concerns || [])"
GUARDED_DEVIATIONS = "...(r.deviations || []).map("
GATE_ANSWER = "answerFor(slice, 'quality-gate-block')"
ANSWERABLE_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
                       "council-objection", "quality-gate-block")
CRITIQUE_REQUIRED = "required: ['verdict', 'safety', 'concerns']"
FAIL_CLOSED_DEFAULT = "unreadable critic verdict (fail closed)"
OVER_SCOPE_DEFAULT = "over_scope: null"
OVER_SCOPE_SCHEMA = "over_scope: { type: 'object'"
CRITIQUE_ROLLUP = "state.critique = { verdict:"
SPLIT_SUPPRESSION = "if (splitRec && slice.depth < 2"
OBJECTION_SELECTION = "const ob = (safety || objections[0])"
REPLAN_VETO = "if (!safety && ob.fixable_by_replan"
FINDING_CATEGORIES = "category: { enum: ["
COUNCIL_VERDICT_EVENT = "type: 'council-verdict'"
SCOPE_HELPER = "function scopeRecord("
HELPER_END = "\n}\n"
SCOPE_LOCAL = "const scope = scopeRecord(verdicts)"
SCOPE_SPREAD = "...(scope ? { over_scope: scope } : {})"
SCOPE_REASON_KEPT = "reason: v.over_scope.reason"
SIDECAR_SCOPE_ATTACH = "if (scope) state.critique.over_scope = scope"

# Driver for the one behavioural check in this module: the extracted
# scopeRecord() source, applied to each supplied panel by real node. %s is the
# function source, then the JSON panel list.
SCOPE_DRIVER = """%s
const cases = %s
console.log(JSON.stringify(cases.map(c => scopeRecord(c))))
"""
CLEAN = {"over_scope": {"flag": False, "reason": None}}
FLAGGED = {"over_scope": {"flag": True, "reason": "dashboard UI work"}}


def wrapped_source():
    """The workflow source in the async wrapper node can actually parse."""
    body = SOURCE.replace("\nexport const", "\nconst")
    if body.startswith("export const"):
        body = body[len("export "):]
    return WRAP_HEAD + body + WRAP_TAIL


class WorkflowSourceTestCase(unittest.TestCase):
    """Source-text helpers shared by every contract class below."""

    def setUp(self):
        self.src = SOURCE

    def line_containing(self, needle):
        """The one source line holding `needle` (a moved anchor fails loudly)."""
        hits = [l for l in self.src.splitlines() if needle in l]
        self.assertEqual(
            len(hits), 1,
            "expected exactly one line containing %r, found %d" % (needle, len(hits)))
        return hits[0]

    def between(self, start_needle, end_needle):
        """The source between two anchors, both of which must exist."""
        start = self.src.find(start_needle)
        end = self.src.find(end_needle, start + 1)
        self.assertNotEqual(start, -1, "missing anchor %r" % (start_needle,))
        self.assertNotEqual(end, -1, "missing anchor %r" % (end_needle,))
        return self.src[start:end]


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
        """The Stage-T task loop body, where every task-result read happens."""
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
    hand-resolved one twice."""

    def test_every_human_answerable_trigger_has_at_least_one_injection_site(self):
        for trigger in ANSWERABLE_TRIGGERS:
            self.assertIn(
                "answerFor(slice, '%s')" % (trigger,), self.src,
                "%s has no answer injection path" % (trigger,))

    def test_the_fix_prompt_carries_the_gate_answer(self):
        fix = self.between("function fixPrompt(", "function reReviewPrompt(")
        self.assertIn(GATE_ANSWER, fix)

    def test_the_verify_prompt_carries_the_gate_answer(self):
        verify = self.between("function verifyPrompt(", "function debugFixPrompt(")
        self.assertIn(GATE_ANSWER, verify)

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
        # The record is attached on its own statement rather than spread into
        # the rollup literal: the binding RECORD-ONLY constraint forbids the
        # flag from appearing in the verdict rollup line at all, and the two
        # assertions above and here would otherwise contradict each other.
        self.assertIn(SIDECAR_SCOPE_ATTACH, self.src)


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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
