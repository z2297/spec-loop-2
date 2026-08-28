#!/usr/bin/env python3
"""Contract checks for the doctrine surfaces of the refactor-scope trigger.

The gate itself is JavaScript and already pinned by
test_slice_wave_contract_radius.py. This module pins the three PROSE
surfaces a human or an agent actually reads - the escalation-gate skill,
the slice-planner agent, and the controller command - against the shipped
behaviour, because prose is a live plugin surface and drift in it is
silent. The precedent is TestTheSkillDescribesTheLostSliceAsk in
test_slice_wave_contract.py, which exists because exactly this drift
happened once already.

Honest limit: these are substring assertions over collapsed prose. They
prove a sentence is present and that its superseded form is gone. They
prove nothing about whether an agent obeys it, and they are not a
behavioural test of the gate.

A separate module rather than a class in an existing one:
slice_wave_contract_base.py sits at 299 non-blank lines and
test_slice_wave_contract_radius.py at 301, both at or over the quality
gate's 300-line class_lines threshold.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_doctrine_refactor_scope.py'
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from slice_wave_contract_base import COMMAND_MD  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = PLUGIN_ROOT / "skills" / "escalation-gate" / "SKILL.md"
PLANNER_MD = PLUGIN_ROOT / "agents" / "slice-planner.md"


def prose(path):
    """One file's text with every whitespace run collapsed to a space. (PURE)"""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


# ---- the escalation-gate skill: six triggers, over-scope still not one ----

SIX_HEADING = "### SURFACE to human (only these six triggers)"
SIX_COUNT = "There are exactly six JUDGMENT triggers"
SIX_BAR = "exactly the six triggers above"
TRIGGER_NAME = "**Refactor scope** (`refactor-scope`)"
TRIGGER_ARITHMETIC = "raised by the workflow's own arithmetic"
TRIGGER_MEASURED = "an absent or unmeasured number is never a breach"
OVER_SCOPE_KEPT = "raises no escalation, changes no verdict, suppresses no split"
OVER_SCOPE_NOT_ONE = "an over-scope flag is not one of them"
STALE_FIVE_HEADING = "only these five triggers"
STALE_FIVE_COUNT = "exactly five JUDGMENT triggers"
STALE_FIVE_BAR = "exactly the five triggers above"
STALE_NOT_SIXTH = "an over-scope flag is not a sixth"
STALE_FIVE_FORMS = (
    STALE_FIVE_HEADING,
    STALE_FIVE_COUNT,
    STALE_FIVE_BAR,
    STALE_NOT_SIXTH,
)


class TestTheSkillCountsSixJudgmentTriggers(unittest.TestCase):
    """Three places in this file stated FIVE and one of them explicitly
    denied a sixth. refactor-scope makes six. The over-scope flag must stay
    excluded on its own separate grounds - it is a record, not a count."""

    def setUp(self):
        self.text = prose(SKILL_MD)

    def test_all_three_five_trigger_statements_now_say_six(self):
        for pin in (SIX_HEADING, SIX_COUNT, SIX_BAR):
            self.assertIn(pin, self.text)

    def test_no_superseded_five_trigger_sentence_survives(self):
        for stale in STALE_FIVE_FORMS:
            self.assertNotIn(stale, self.text)

    def test_the_sixth_trigger_is_named_and_described_as_arithmetic(self):
        self.assertIn(TRIGGER_NAME, self.text)
        self.assertIn(TRIGGER_ARITHMETIC, self.text)

    def test_the_sixth_trigger_fires_only_on_a_measured_breach(self):
        self.assertIn(TRIGGER_MEASURED, self.text)

    def test_the_over_scope_flag_is_still_a_record_and_still_not_a_trigger(self):
        self.assertIn(OVER_SCOPE_KEPT, self.text)
        self.assertIn(OVER_SCOPE_NOT_ONE, self.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
