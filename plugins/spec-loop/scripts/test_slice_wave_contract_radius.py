#!/usr/bin/env python3
"""Contract checks for the plan-time refactor-radius ceiling.

Two layers, both here. The first pins SOURCE TEXT: that every threshold
comparison in the radius block is reached only after an explicit `!== null`
guard, because `undefined >= n` is false and `null >= 0` is true and a
comparison reached by coercion decides halts by accident. The second layer
EXECUTES `refactorRadiusStatus()` under real node through the same
extract-and-drive pattern `TestScopeRecordBehavesAndNotJustExists` uses in
test_slice_wave_contract.py, because a substring assertion proves a guard is
present and nothing at all about what it decides.

A fourth `test_slice_wave_contract*.py` module rather than a class in an
existing one: `slice_wave_contract_base.py` sits at 298 non-blank lines and
the quality gate's `class_lines` threshold is 300 whole-file non-blank lines,
so every constant below is module-local by necessity as well as by the
snippet-as-named-constant rule. The `basis`-field checks live in a fifth
module, test_slice_wave_contract_radius_basis.py, for the same reason: this
file crossed 300 non-blank lines once that class was added here, and the
shared node driver moved to slice_wave_contract_radius_driver.py so both
files can execute refactorRadiusStatus() without one importing a TestCase
out of the other.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_slice_wave_contract_radius.py'
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from slice_wave_contract_base import COMMAND_MD, RUN_STATE_MD, WorkflowSourceTestCase  # noqa: E402
from slice_wave_contract_radius_driver import RADIUS_START, RADIUS_END, radius_status  # noqa: E402

RADIUS_NUM = ("const radiusNum = (v) => "
              "(typeof v === 'number' && Number.isFinite(v)) ? v : null")
RATIO_GUARD = "const over = (v, max) => v !== null && max !== null && v > max"
FLOOR_GUARD = "m.rewritten_lines !== null && limits.min_rewritten_lines !== null"
NOT_CONFIGURED = "state: 'NOT_CONFIGURED'"
NOT_MEASURED = "state: 'NOT_MEASURED'"
NO_USABLE_CEILING = "state: 'NO_USABLE_CEILING'"
WITHIN_PARTIAL = "state: 'WITHIN_PARTIAL'"
EXCEEDED = "state: 'EXCEEDED'"
COERCION_OPERATORS = (">=", "<=")
NAMED_BRANCHES = (NOT_CONFIGURED, NO_USABLE_CEILING, NOT_MEASURED,
                  WITHIN_PARTIAL, EXCEEDED)

# The shipped defaults, and the declared-radius fixtures each state needs.
# Module-level because nesting_depth is measured from raw indentation, so a
# hanging literal inside a test body scores as real block nesting.
LIMITS = {"enabled": True, "max_rewrite_ratio": 0.5,
          "max_touched_existing_files": 8, "min_rewritten_lines": 150}
BIG = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 900}
AT_CEILING = {"rewrite_ratio": 0.5, "touched_existing_files": 8, "rewritten_lines": 900}
TINY = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 20}
ZEROED = {"rewrite_ratio": 0, "touched_existing_files": 0, "rewritten_lines": 0}
NO_CEILINGS = {"enabled": True, "max_rewrite_ratio": None,
               "max_touched_existing_files": None, "min_rewritten_lines": 150}
STRING_CEILINGS = {"enabled": True, "max_rewrite_ratio": "0.5",
                   "max_touched_existing_files": "8", "min_rewritten_lines": 150}
STRINGY = {"rewrite_ratio": "0.9", "touched_existing_files": "12"}
ONE_CEILING = dict(LIMITS, max_rewrite_ratio=None)
PARTIAL = {"rewrite_ratio": 0.9, "touched_existing_files": 2, "rewritten_lines": 40}
FILES_ONLY_DECLARED = {"touched_existing_files": 2, "rewritten_lines": 40}

# Expected verdict fragments, hoisted for the same reason: a hanging
# literal inside a test body is scored as real block nesting by the
# quality gate's indentation heuristic.
THREE_NULLS = {"rewrite_ratio": None,
               "touched_existing_files": None,
               "rewritten_lines": None}
BOTH_CEILINGS = ["rewrite_ratio", "touched_existing_files"]


# ---- the predicate, executed ----

class TestTheRadiusPredicateDecidesAndNotJustExists(WorkflowSourceTestCase):
    """Seven states, none collapsed into another. A substring assertion can
    prove the word NOT_MEASURED appears in the file and nothing about which
    inputs reach it, so this class runs the real helpers under real node and
    reads the verdicts back: absence, disablement, an unusable ceiling, an
    unmeasured plan, a plan at its ceiling, a breach, and a noise-floor one."""

    def test_an_absent_ctx_block_is_not_configured_and_compares_nothing(self):
        # In order: no block at all, a string where an object belongs, and an
        # array. None of the three is a ceiling, and guessing the shipped
        # defaults here would give the repo two sources of truth for a number
        # the operator is invited to tune.
        got = radius_status([[BIG, None], [BIG, "0.5"], [BIG, [0.5]]])
        self.assertEqual([g["state"] for g in got], ["NOT_CONFIGURED"] * 3)
        self.assertEqual([g["thresholds"] for g in got], [None, None, None])
        self.assertEqual([g["exceeded"] for g in got], [[], [], []])

    def test_a_disabled_block_never_fires_however_large_the_numbers(self):
        got = radius_status([[BIG, dict(LIMITS, enabled=False)]])
        self.assertEqual(got[0]["state"], "DISABLED")

    def test_an_absent_plan_block_is_not_measured_with_three_explicit_nulls(self):
        # PLAN_RESULT.required is ['status'] only, so all three reads are
        # optional-field reads: absent, empty and array-shaped all land on the
        # same fail-open state rather than throwing or inventing a zero.
        got = radius_status([[None, LIMITS], [{}, LIMITS], [[1], LIMITS]])
        self.assertEqual([g["state"] for g in got], ["NOT_MEASURED"] * 3)
        self.assertEqual(got[0]["measured"], THREE_NULLS)

    def test_declared_zeros_are_a_measurement_and_never_read_as_absence(self):
        got = radius_status([[ZEROED, LIMITS]])
        self.assertEqual(got[0]["state"], "WITHIN")
        self.assertEqual(got[0]["measured"]["rewrite_ratio"], 0)

    def test_string_numbers_are_not_measurements_and_are_never_coerced(self):
        got = radius_status([[STRINGY, LIMITS]])
        self.assertEqual(got[0]["state"], "NOT_MEASURED")
        self.assertIsNone(got[0]["measured"]["rewrite_ratio"])

    def test_a_plan_exactly_at_both_ceilings_is_within_and_does_not_halt(self):
        got = radius_status([[AT_CEILING, LIMITS]])
        self.assertEqual(got[0]["state"], "WITHIN")

    def test_each_ceiling_is_breached_on_its_own_and_is_named_in_exceeded(self):
        ratio = {"rewrite_ratio": 0.9, "rewritten_lines": 900}
        files = {"touched_existing_files": 12, "rewritten_lines": 900}
        got = radius_status([[ratio, LIMITS], [files, LIMITS]])
        self.assertEqual([g["state"] for g in got], ["EXCEEDED", "EXCEEDED"])
        self.assertEqual(got[0]["exceeded"], ["rewrite_ratio"])
        self.assertEqual(got[1]["exceeded"], ["touched_existing_files"])

    def test_the_noise_floor_suppresses_a_breach_but_keeps_the_numbers(self):
        got = radius_status([[TINY, LIMITS]])
        self.assertEqual(got[0]["state"], "BELOW_FLOOR")
        self.assertEqual(got[0]["exceeded"], BOTH_CEILINGS)
        self.assertEqual(got[0]["measured"]["rewritten_lines"], 20)

    def test_an_unmeasured_line_count_does_not_suppress_a_measured_breach(self):
        # The floor can only silence a fire it can prove is noise. A missing
        # rewritten_lines proves nothing, so the measured ratio breach stands.
        got = radius_status([[{"rewrite_ratio": 0.9}, LIMITS]])
        self.assertEqual(got[0]["state"], "EXCEEDED")

    def test_a_configured_block_with_no_usable_ceiling_is_its_own_state(self):
        # WITHIN used to claim "every declared number is at or under its
        # ceiling", which no comparison supported: a silent no-op that passed.
        got = radius_status([[BIG, NO_CEILINGS], [BIG, STRING_CEILINGS]])
        self.assertEqual([g["state"] for g in got], ["NO_USABLE_CEILING"] * 2)
        self.assertEqual([g["exceeded"] for g in got], [[], []])

    def test_an_unusable_ceiling_is_reported_before_an_unmeasured_plan(self):
        # A mistyped ceiling is an operator-config defect, and blaming the
        # planner for it would leave the real defect invisible.
        got = radius_status([[None, NO_CEILINGS]])
        self.assertEqual(got[0]["state"], "NO_USABLE_CEILING")

    def test_one_usable_ceiling_of_the_two_still_judges_the_plan(self):
        # The second pair also pins that a ceiling of 0 is a real, if severe,
        # ceiling: a falsy usability test would read it as no ceiling at all.
        one = dict(NO_CEILINGS, max_touched_existing_files=8)
        zero = dict(NO_CEILINGS, max_rewrite_ratio=0)
        got = radius_status([[BIG, one], [BIG, zero]])
        self.assertEqual([g["state"] for g in got], ["EXCEEDED"] * 2)
        self.assertEqual(got[0]["exceeded"], ["touched_existing_files"])
        self.assertEqual(got[1]["exceeded"], ["rewrite_ratio"])

    def test_every_verdict_carries_the_thresholds_it_compared_against(self):
        # A threshold that silently declines to fire is a permanent invisible
        # narrowing, so the no-fire and not-measured verdicts carry the
        # ceilings too - a reader never has to re-derive why nothing happened.
        got = radius_status([[BIG, LIMITS], [ZEROED, LIMITS], [None, LIMITS]])
        for g in got:
            self.assertEqual(g["thresholds"]["max_rewrite_ratio"], 0.5)
            self.assertEqual(g["thresholds"]["max_touched_existing_files"], 8)
            self.assertEqual(g["thresholds"]["min_rewritten_lines"], 150)

    def test_a_declared_number_with_no_usable_ceiling_is_never_within_one(self):
        # The mirror of NO_USABLE_CEILING: one mistyped ceiling beside one
        # valid one used to short-circuit on the null side and then report
        # WITHIN about a ratio no comparison had touched.
        got = radius_status([[PARTIAL, ONE_CEILING]])
        self.assertEqual(got[0]["state"], "WITHIN_PARTIAL")
        self.assertEqual(got[0]["compared"], ["touched_existing_files"])
        self.assertEqual(got[0]["skipped"], ["rewrite_ratio"])

    def test_the_partial_verdict_names_the_dimension_it_never_compared(self):
        got = radius_status([[PARTIAL, ONE_CEILING]])
        self.assertIn("rewrite_ratio", got[0]["reason"])
        self.assertIn("no usable ceiling", got[0]["reason"])

    def test_a_partial_verdict_fails_open_and_exceeds_nothing(self):
        got = radius_status([[PARTIAL, ONE_CEILING]])
        self.assertEqual(got[0]["exceeded"], [])
        self.assertNotEqual(got[0]["state"], "EXCEEDED")

    def test_a_fully_compared_plan_keeps_todays_within_verdict_exactly(self):
        got = radius_status([[AT_CEILING, LIMITS], [ZEROED, LIMITS]])
        self.assertEqual([g["state"] for g in got], ["WITHIN"] * 2)
        self.assertEqual(got[0]["compared"], BOTH_CEILINGS)
        self.assertEqual(got[0]["skipped"], [])

    def test_a_breach_beside_an_uncompared_number_still_says_which(self):
        got = radius_status([[BIG, ONE_CEILING]])
        self.assertEqual(got[0]["state"], "EXCEEDED")
        self.assertEqual(got[0]["skipped"], ["rewrite_ratio"])
        self.assertIn("rewrite_ratio", got[0]["reason"])

    def test_a_number_the_plan_never_declared_is_not_reported_as_skipped(self):
        # Silence is not a skipped comparison: only a DECLARED number can be
        # a number that went uncompared.
        got = radius_status([[FILES_ONLY_DECLARED, LIMITS]])
        self.assertEqual(got[0]["state"], "WITHIN")
        self.assertEqual(got[0]["skipped"], [])


# ---- the guards, pinned in source ----

class TestNoRadiusComparisonIsReachedByCoercion(WorkflowSourceTestCase):
    """`undefined >= n` is false and `null >= 0` is true, so an absent
    measurement compared directly against a threshold produces a verdict
    with no explicit branch. The whole block is therefore forbidden the
    `>=`/`<=` operators outright, and both comparison sites are pinned to
    guards that test BOTH sides for null first."""

    def region(self):
        return self.between(RADIUS_START, RADIUS_END)

    def test_the_radius_block_uses_no_coercion_friendly_operator_at_all(self):
        for op in COERCION_OPERATORS:
            self.assertNotIn(op, self.region())

    def test_both_comparisons_guard_both_sides_for_null_first(self):
        self.assertIn(RATIO_GUARD, self.region())
        self.assertIn(FLOOR_GUARD, self.region())

    def test_a_number_is_type_checked_before_it_is_ever_a_measurement(self):
        self.assertIn(RADIUS_NUM, self.region())

    def test_the_five_no_fire_states_exist_as_their_own_named_branches(self):
        for marker in NAMED_BRANCHES:
            self.assertIn(marker, self.region())


# ---- the declared block on PLAN_RESULT, and the planner instruction ----

PLAN_REQUIRED = "required: ['status'],"
RADIUS_SCHEMA = "refactor_radius: { type: 'object', additionalProperties: false"
RADIUS_RATIO_TYPE = "rewrite_ratio: { type: ['number', 'null'] }"
PROMPT_ASK = "Also return refactor_radius: your DECLARED estimate"
PROMPT_NO_ZERO = "omit it rather than guessing a zero"
PROMPT_JUDGE = "the workflow judges them against the run's ceiling"
CTX_FIELD = "refactor_radius{enabled,max_rewrite_ratio"
PLAN_PROMPT_START = "function planPrompt(slice) {"
PLAN_PROMPT_END = "function criticPrompt("


class TestThePlannerDeclaresNumbersAndTheWorkflowJudgesThem(WorkflowSourceTestCase):
    """The planner is an ACTOR that reports numbers; the verdict is JS's.
    The field stays optional because absence must remain a different claim
    from zero all the way from the schema to the event payload."""

    def test_the_schema_carries_an_optional_refactor_radius_block(self):
        self.assertIn(RADIUS_SCHEMA, self.src)
        self.assertIn(RADIUS_RATIO_TYPE, self.src)

    def test_plan_result_still_requires_status_and_nothing_else(self):
        self.assertIn(PLAN_REQUIRED, self.src)
        self.assertNotIn("required: ['status', 'refactor_radius']", self.src)

    def test_the_plan_prompt_asks_for_the_numbers_without_asking_for_a_verdict(self):
        prompt = self.between(PLAN_PROMPT_START, PLAN_PROMPT_END)
        self.assertIn(PROMPT_ASK, prompt)
        self.assertIn(PROMPT_JUDGE, prompt)

    def test_the_plan_prompt_forbids_inventing_a_zero_for_an_unknown(self):
        self.assertIn(PROMPT_NO_ZERO, self.between(PLAN_PROMPT_START, PLAN_PROMPT_END))

    def test_the_ctx_field_list_names_refactor_radius_as_the_one_channel(self):
        self.assertIn(CTX_FIELD, self.line_containing("const CTX = A.ctx"))


# ---- the halt: only a measured breach, only at plan time ----

GATE_CALL = "const radius = refactorRadiusGate(slice, state, plan)"
GATE_STOP = "if (radius) return { stop: escalated(slice, state, radius) }"
GATE_TRIGGER = "return esc(slice, 'refactor-scope', refactorAsk(slice, verdict))"
GATE_SUPPRESSION = "if (verdict.state !== 'EXCEEDED' || answered) return null"
GATE_ALWAYS_EMITS = "state.events.push(radiusEvent(slice, verdict, answered))"
GATE_ANSWERED = "const answered = !!latestAnswer(slice.id, 'refactor-scope')"
GATE_KEY_COUNT = "answerKeysFor(slice.id, 'refactor-scope').length"
STAGE_PLAN_START = "async function stagePlan(slice, state) {"
STAGE_PLAN_END = "// Stage C helpers"
GATE_FN_START = "function refactorRadiusGate(slice, state, plan) {"
GATE_FN_END = "\n}\n"
SUPPRESSED_GUARD = "const suppressed = answered && verdict.state === 'EXCEEDED'"
SUPPRESSED_SPREAD = "...(suppressed ? { suppressed_by_answer: true } : {}),"
EVENT_FN_START = "function radiusEvent(slice, verdict, answered) {"


class TestOnlyAMeasuredBreachHaltsAndOnlyAtPlanTime(WorkflowSourceTestCase):
    """The event push precedes the halt decision in source order, so no
    return path can skip it; and the halt is raised from stagePlan and
    nowhere else, before a single implementation dispatch is spent."""

    def test_the_event_is_pushed_before_any_halt_decision_is_taken(self):
        body = self.between(GATE_FN_START, GATE_FN_END)
        self.assertLess(body.index(GATE_ALWAYS_EMITS), body.index(GATE_SUPPRESSION))

    def test_only_the_exceeded_state_and_only_an_unanswered_slice_halts(self):
        self.assertIn(GATE_SUPPRESSION, self.src)

    def test_the_halt_is_disarmed_by_a_truthy_answer_and_not_by_a_key(self):
        self.assertIn(GATE_ANSWERED, self.between(GATE_FN_START, GATE_FN_END))

    def test_no_answer_key_count_decides_anything_in_the_gate(self):
        self.assertNotIn(GATE_KEY_COUNT, self.src)

    def test_a_suppression_is_only_claimed_for_a_breach_an_answer_waived(self):
        body = self.between(EVENT_FN_START, GATE_FN_END)
        self.assertIn(SUPPRESSED_GUARD, body)
        self.assertIn(SUPPRESSED_SPREAD, body)

    def test_no_suppression_flag_is_set_from_answeredness_alone(self):
        self.assertNotIn("...(answered ? { suppressed_by_answer: true } : {})", self.src)

    def test_the_record_is_minted_with_the_refactor_scope_trigger(self):
        self.assertIn(GATE_TRIGGER, self.src)

    def test_the_gate_is_called_from_the_plan_stage_and_from_nowhere_else(self):
        self.assertIn(GATE_CALL, self.between(STAGE_PLAN_START, STAGE_PLAN_END))
        self.assertIn(GATE_STOP, self.between(STAGE_PLAN_START, STAGE_PLAN_END))
        self.assertEqual(self.src.count("refactorRadiusGate("), 2)


# ---- the controller thread: ctx is the only lawful door ----

CTX_THREAD = "refactor_radius"
ONE_DOOR = "--print-config"
EVENT_IN_LIST = "`refactor-radius`"
PAYLOAD_BULLET = "**`refactor-radius`** payload"
PROXY_LIMIT = "a proxy declared before implementation, not a measured diff"
PARTIAL_STATE_DOC = "`WITHIN_PARTIAL`"
COVERAGE_KEYS_DOC = "compared[], skipped[]"


class TestTheThresholdsReachTheWorkflowOnlyThroughCtx(WorkflowSourceTestCase):
    """The workflow has no fs and no process access by design, so the only
    lawful path for a threshold is --print-config -> the controller command
    -> ctx. If the command stops threading it, every installation silently
    evaluates NOT_CONFIGURED and the ceiling never fires again."""

    def test_the_controller_takes_the_block_from_the_one_config_door(self):
        text = COMMAND_MD.read_text(encoding="utf-8")
        self.assertIn(ONE_DOOR, text)
        self.assertIn(CTX_THREAD, text)

    def test_the_event_type_is_listed_in_its_single_home(self):
        text = RUN_STATE_MD.read_text(encoding="utf-8")
        self.assertIn(EVENT_IN_LIST, text)
        self.assertIn(PAYLOAD_BULLET, text)

    def test_the_contract_states_the_pre_execution_proxy_limit_plainly(self):
        self.assertIn(PROXY_LIMIT, RUN_STATE_MD.read_text(encoding="utf-8"))

    def test_the_partial_coverage_state_is_documented_in_its_single_home(self):
        # A state a reader of the event cannot look up is a state that gets
        # read as a typo for WITHIN.
        text = RUN_STATE_MD.read_text(encoding="utf-8")
        self.assertIn(PARTIAL_STATE_DOC, text)
        self.assertIn(COVERAGE_KEYS_DOC, text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
