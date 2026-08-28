#!/usr/bin/env python3
"""Contract checks for the refactor-radius `basis` field.

Split out of test_slice_wave_contract_radius.py, which crossed the quality
gate's 300-non-blank-line class_lines threshold once this class was added.
The planner declares HOW it counted (`basis`); a human weighing approve /
narrow / carve-out cannot weigh a number whose derivation is invisible. The
field is display-only, so these tests pin that it travels from the verdict
to the event AND that it changes no verdict at all.

Uses the same node driver as test_slice_wave_contract_radius.py, imported
from slice_wave_contract_radius_driver rather than from that module's
TestCase directly - importing a TestCase class into a second module makes
`unittest discover` collect and run its tests twice.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_slice_wave_contract_radius_basis.py'
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from slice_wave_contract_base import WorkflowSourceTestCase  # noqa: E402
from slice_wave_contract_radius_driver import (  # noqa: E402
    RADIUS_START, RADIUS_END, radius_status)

BIG = {"rewrite_ratio": 0.9, "touched_existing_files": 12, "rewritten_lines": 900}
LIMITS = {"enabled": True, "max_rewrite_ratio": 0.5,
          "max_touched_existing_files": 8, "min_rewritten_lines": 150}
RADIUS_BASIS_GUARD = "(typeof radius.basis === 'string' && radius.basis) ? radius.basis : null"
BASIS_IN_BASE = "basis: radiusBasis(radius)"
BASIS_IN_EVENT = "basis: verdict.basis,"
BASIS_TEXT = "counted with git diff --stat against main"
WITH_BASIS = dict(BIG, basis=BASIS_TEXT)
BAD_BASIS = dict(BIG, basis=17)


class TestTheBasisReachesTheHumanAndDecidesNothing(WorkflowSourceTestCase):
    """The planner declares HOW it counted; a human weighing approve /
    narrow / carve-out cannot weigh a number whose derivation is invisible.
    The field is display-only, so these tests pin that it travels AND that
    the verdict is identical with and without it."""

    def test_the_basis_is_carried_on_the_verdict_and_out_to_the_event(self):
        self.assertIn(BASIS_IN_BASE, self.between(RADIUS_START, RADIUS_END))
        self.assertIn(BASIS_IN_EVENT, self.src)

    def test_only_a_non_empty_string_is_accepted_as_a_basis(self):
        self.assertIn(RADIUS_BASIS_GUARD, self.between(RADIUS_START, RADIUS_END))

    def test_the_basis_travels_beside_measured_and_never_inside_it(self):
        got = radius_status([[WITH_BASIS, LIMITS], [BIG, LIMITS], [BAD_BASIS, LIMITS]])
        self.assertEqual(got[0]["basis"], BASIS_TEXT)
        self.assertIsNone(got[1]["basis"])
        self.assertIsNone(got[2]["basis"])
        self.assertNotIn("basis", got[0]["measured"])

    def test_the_basis_changes_no_state_and_no_exceeded_list(self):
        got = radius_status([[WITH_BASIS, LIMITS], [BIG, LIMITS]])
        self.assertEqual(got[0]["state"], got[1]["state"])
        self.assertEqual(got[0]["exceeded"], got[1]["exceeded"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
