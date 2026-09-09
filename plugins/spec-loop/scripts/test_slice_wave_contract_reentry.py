#!/usr/bin/env python3
"""Contract checks for the measurement path the wave takes on its way OUT of a
slice: the quality block is written by one recorder from the LAST measurement,
every fix-loop escalation re-measures first, verification is recorded before
it is judged, and the package tags name files that exist.

Run 20260908-jira-intake paid for each of these: six sidecar quality blocks
were pre-fix snapshots the controller re-measured by hand, and every fix
prompt named `packages/<slice>-round2.md`, a file nothing writes. The
executing lane (slice_wave_reentry.test.mjs) proves the behaviour against the
mock sandbox; this module pins the SOURCE facts a behavioural test cannot:
that no escalation path out of the fix loop bypasses the re-measure, that the
round-tag arithmetic lives in exactly one place, and that the sidecar's
quality enum was not widened to express accepted debt.

A sixth `test_slice_wave_contract*.py` module because its siblings sit near
the quality gate's 300-non-blank-line class_lines ceiling. Every pinned
snippet is a module-level constant, not a literal in a test body, because
quality_gate.py's metrics are line-based.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_slice_wave_contract_reentry.py'
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from slice_wave_contract_base import WorkflowSourceTestCase  # noqa: E402

RUN_STATE_PY = Path(__file__).resolve().parent / "run_state.py"

ROUND_TAG = "round${state.review.fix_rounds + 1}"
STAGE_R_START = "async function stageReviewGate(slice, state, plan) {"
STAGE_R_END = "// Re-measure the gate at the CURRENT head"
ANCHOR_HELPER = "function anchorPackages(slice, state) {"
ANCHOR_CALL = "anchorPackages(slice, state).join(' and ')"
BATCH_PROMPT_START = "function verifierBatchPrompt("
FIX_PROMPT_START = "function fixPrompt("
FIX_PROMPT_END = "// FIX_RESULT.commits is optional"
FIX_LOOP_START = "async function runFixRound(slice, state, ctx) {"
FIX_LOOP_END = "// Stage S"
RAW_ESCALATION = "escalated(slice, state, esc("
FIX_LOOP_EXIT = "fixLoopEscalation(slice, state, {"
FIX_ROUNDS_INCREMENT = "state.review.fix_rounds += 1"
FIX_ROUNDS_ASSIGN = "fix_rounds = round + 1"
STAGE_Z_START = "async function stageVerify(slice, state, plan) {"
STAGE_Z_END = "// The seven-stage sequence"
RECORD_VERIFICATION = "recordVerification(slice, state, v,"
VERIFY_JUDGE = "if (verifyPassed(v))"
OLD_DONE_HELPER = "function markVerifiedDone("
QUALITY_WRITE = "state.quality = "
STAMP_START = "function stampQuality(slice, state, v, role) {"
STAMP_END = "// Tests + quality + head from one verifier return"
REMEASURE_START = "async function remeasureGate(slice, state) {"
REMEASURE_END = "// Every fix-loop escalation leaves through here"
STAMP_ROLE_FIELD = "measured_at: role"
GATE_EVENT_STAGE = "stage: role }"
QUALITY_ENUM = 'QUALITY_STATUSES = ("PASS", "FAIL", "SKIPPED")'
LOST_SLICE_QUALITY = "quality: { status: 'SKIPPED', detail: 'slice never ran' }"
REVIEW_BLOCK_ANSWER = "answerFor(slice, 'review-block')"
AMBIGUITY_ANSWER = "answerFor(slice, 'ambiguity')"
TASK_PROMPT_START = "function taskPrompt("
TASK_PROMPT_END = "function packageCmd("
RETRY_MARKER = "RETRY:"
DEBUG_FIX_START = "function debugFixPrompt("
DEBUG_FIX_END = "function simplifyPrompt("
ENTRY_STAGES_LINE = "const ENTRY_STAGES = ['plan', 'review', 'fix', 'verify']"
ENTRY_ERROR_TITLE = "title: 'unusable slice.entry'"
REENTRY_EVENT = "type: 're-entry'"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
COMMAND_MD = PLUGIN_ROOT / "commands" / "spec-loop.md"
SKILL_MD = PLUGIN_ROOT / "skills" / "escalation-gate" / "SKILL.md"
RUN_STATE_MD = PLUGIN_ROOT / "references" / "run-state-v2.md"
OLD_JOURNAL_CLAIM = "completed stages replay from the workflow journal"


class TestTheRoundTagLivesInOnePlace(WorkflowSourceTestCase):
    def test_the_round_tag_is_computed_exactly_once_inside_stage_r(self):
        line = self.line_containing(ROUND_TAG)
        self.assertIn(line, self.between(STAGE_R_START, STAGE_R_END))

    def test_the_fix_and_batch_verifier_prompts_read_the_anchor_helper(self):
        self.assertIn(ANCHOR_HELPER, self.src)
        self.assertIn(ANCHOR_CALL, self.between(BATCH_PROMPT_START, FIX_PROMPT_START))
        self.assertIn(ANCHOR_CALL, self.between(FIX_PROMPT_START, FIX_PROMPT_END))

    def test_the_fix_round_counter_is_cumulative(self):
        self.assertIn(FIX_ROUNDS_INCREMENT, self.src)
        self.assertNotIn(FIX_ROUNDS_ASSIGN, self.src)


class TestEveryFixLoopExitReMeasures(WorkflowSourceTestCase):
    def test_no_fix_loop_escalation_bypasses_the_re_measure(self):
        span = self.between(FIX_LOOP_START, FIX_LOOP_END)
        self.assertEqual(span.count(RAW_ESCALATION), 0)
        self.assertEqual(span.count(FIX_LOOP_EXIT), 2)


class TestVerificationIsRecordedBeforeItIsJudged(WorkflowSourceTestCase):
    def test_the_recorder_runs_before_the_verdict(self):
        span = self.between(STAGE_Z_START, STAGE_Z_END)
        self.assertLess(span.index(RECORD_VERIFICATION), span.index(VERIFY_JUDGE))

    def test_the_done_only_writer_is_gone(self):
        self.assertNotIn(OLD_DONE_HELPER, self.src)


class TestOneRecorderWritesTheQualityBlock(WorkflowSourceTestCase):
    def test_every_quality_write_sits_in_the_recorder_or_the_re_measure(self):
        allowed = self.between(STAMP_START, STAMP_END) + self.between(REMEASURE_START, REMEASURE_END)
        for line in [l for l in self.src.splitlines() if QUALITY_WRITE in l]:
            with self.subTest(line=line.strip()[:60]):
                self.assertIn(line, allowed)

    def test_the_recorder_stamps_the_role_on_block_and_event(self):
        span = self.between(STAMP_START, STAMP_END)
        self.assertIn(STAMP_ROLE_FIELD, span)
        self.assertIn(GATE_EVENT_STAGE, span)


class TestTheQualityEnumIsNotWidened(WorkflowSourceTestCase):
    def test_run_state_keeps_the_three_statuses(self):
        self.assertIn(QUALITY_ENUM, RUN_STATE_PY.read_text(encoding="utf-8"))

    def test_the_lost_slice_fallback_block_is_untouched(self):
        self.assertIn(LOST_SLICE_QUALITY, self.src)


class TestAnswersReachTheAgentThatActs(WorkflowSourceTestCase):
    """Run 20260908: a review-block answer carrying fix orders reached the
    REVIEWER, a task-blocked ambiguity answer reached the PLANNER, and the
    fixer and the task retry — the two actors — read nothing."""

    def test_the_fix_prompt_carries_the_review_block_answer(self):
        self.assertIn(REVIEW_BLOCK_ANSWER, self.between(FIX_PROMPT_START, FIX_PROMPT_END))

    def test_the_debug_fix_prompt_carries_the_review_block_answer(self):
        self.assertIn(REVIEW_BLOCK_ANSWER, self.between(DEBUG_FIX_START, DEBUG_FIX_END))

    def test_the_task_retry_carries_the_ambiguity_answer_and_the_first_attempt_does_not(self):
        span = self.between(TASK_PROMPT_START, TASK_PROMPT_END)
        self.assertIn(AMBIGUITY_ANSWER, span)
        self.assertLess(span.index(RETRY_MARKER), span.index(AMBIGUITY_ANSWER))


class TestReentryIsDeclaredInEveryHome(WorkflowSourceTestCase):
    def test_the_workflow_names_the_four_stages_and_fails_loud(self):
        self.assertIn(ENTRY_STAGES_LINE, self.src)
        self.assertIn(ENTRY_ERROR_TITLE, self.src)
        self.assertIn(REENTRY_EVENT, self.src)

    def test_the_controller_and_the_contract_name_the_entry(self):
        self.assertIn("slice.entry", COMMAND_MD.read_text(encoding="utf-8"))
        self.assertIn("redispatch.py", COMMAND_MD.read_text(encoding="utf-8"))
        self.assertIn("`re-entry`", RUN_STATE_MD.read_text(encoding="utf-8"))

    def test_the_journal_replay_promise_is_gone_from_the_doctrine(self):
        self.assertNotIn(OLD_JOURNAL_CLAIM, SKILL_MD.read_text(encoding="utf-8"))
        self.assertIn("slice.entry", SKILL_MD.read_text(encoding="utf-8"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
