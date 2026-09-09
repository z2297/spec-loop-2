#!/usr/bin/env python3
"""Doctrine pins for accepted quality-gate violations and the escalation round
bound — the prose the controller model actually reads.

Run 20260908-jira-intake's slice j1 raised quality-gate-block three times on
four violations the controller had already accepted, then was closed by a
hand-written DONE sidecar. The mechanism now exists (the wave's
accepted_violations channel, redispatch.py accept-violations, open-escalations'
repeat_of, the non-terminating reframing); these tests pin that every home the
controller reads names it, so the mechanism is not left to be rediscovered.
Pattern follows test_doctrine_refactor_scope.py: exact sentences, collapsed
whitespace, counted on disk rather than remembered.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_doctrine_accepted_violations.py'
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = PLUGIN_ROOT / "skills" / "escalation-gate" / "SKILL.md"
COMMAND_MD = PLUGIN_ROOT / "commands" / "spec-loop.md"
RUN_STATE_MD = PLUGIN_ROOT / "references" / "run-state-v2.md"
WORKFLOW_JS = PLUGIN_ROOT / "workflows" / "slice-wave.workflow.js"


def collapsed(path):
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


class TestTheEscalationGateNamesTheMechanism(unittest.TestCase):
    def setUp(self):
        self.text = collapsed(SKILL_MD)

    def test_trigger_five_records_an_acceptance_instead_of_a_threshold_change(self):
        self.assertIn("recorded as an accepted violation", self.text)
        self.assertIn("never as a threshold change and never as prose alone", self.text)
        self.assertNotIn("Thresholds are never weakened to avoid this.", self.text)

    def test_the_precedent_check_has_a_same_run_bullet(self):
        self.assertIn("**Same-run precedent:**", self.text)
        self.assertIn("redispatch.py accept-violations", self.text)
        self.assertIn("`repeat_of`", self.text)

    def test_the_two_new_violations_are_listed(self):
        self.assertIn("Accepting a quality-gate residual in prose alone", self.text)
        self.assertIn("Hand-writing a DONE sidecar", self.text)


class TestTheControllerHasTheLever(unittest.TestCase):
    def setUp(self):
        self.text = collapsed(COMMAND_MD)

    def test_step_seven_names_the_accept_command_and_the_map(self):
        self.assertIn("accept-violations", self.text)
        self.assertIn("accepted_violations", self.text)
        self.assertIn("never hand-write a DONE sidecar", self.text)

    def test_step_seven_names_the_non_terminating_title(self):
        self.assertIn("`non-terminating:`", self.text)


class TestTheContractAndTheWaveAgree(unittest.TestCase):
    def test_the_contract_documents_every_new_field(self):
        text = collapsed(RUN_STATE_MD)
        for needle in ("accepted_violations", '"accepted"', '"violations"', "repeat_of", "MAX_ESC_ROUNDS = 2"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_wave_bound_matches_the_contract(self):
        self.assertIn("const MAX_ESC_ROUNDS = 2", WORKFLOW_JS.read_text(encoding="utf-8"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
