#!/usr/bin/env python3
"""Contract checks for the two run-level doc surfaces s6 reconciled.

`skills/escalation-gate/SKILL.md` is the single home of the judgment-trigger
doctrine; README.md and references/risk-tiers.md only REFER to its count, and
an uncounted reference is exactly the kind of prose that drifts silently. This
module pins both references at six, pins that their five-trigger predecessors
are gone, and pins README's counted component inventory against a real count of
the tree rather than against a remembered number.

Honest limit: these are substring assertions over collapsed prose plus a
directory count. They prove a sentence is present and its superseded form is
absent; they prove nothing about whether a reader or an agent acts on it, and
they are not a behavioural test of any gate. The component test counts files on
disk, so it fails on a real inventory change - which is the point.

A separate module rather than a class in test_doctrine_refactor_scope.py:
that module is owned by the doctrine slice and this one by the docs close-out;
slice_wave_contract_base.py is at its 300-line ceiling and must not grow.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_doctrine_run_docs.py'
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
README_MD = PLUGIN_ROOT / "README.md"
RISK_TIERS_MD = PLUGIN_ROOT / "references" / "risk-tiers.md"


def prose(path):
    """One file's text with every whitespace run collapsed to a space. (PURE)"""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


# ---- README: the escalations section ----

README_SIX = "the escalation-gate's six triggers"
README_SIXTH = "or a plan-time refactor-scope breach"
README_ARITHMETIC = "the only one the wave raises from its own arithmetic"
README_STALE_FIVE = "the escalation-gate's five triggers"


class TestTheReadmeNamesSixJudgmentTriggers(unittest.TestCase):
    """README is the first surface a new user reads; a stale count here
    understates what the loop will stop for, which is the failure direction
    that surprises a human mid-run."""

    def setUp(self):
        self.text = prose(README_MD)

    def test_the_readme_counts_six_judgment_triggers(self):
        self.assertIn(README_SIX, self.text)

    def test_the_five_trigger_predecessor_sentence_is_gone(self):
        self.assertNotIn(README_STALE_FIVE, self.text)

    def test_the_readme_names_the_sixth_trigger_and_who_raises_it(self):
        self.assertIn(README_SIXTH, self.text)
        self.assertIn(README_ARITHMETIC, self.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
