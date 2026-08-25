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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
