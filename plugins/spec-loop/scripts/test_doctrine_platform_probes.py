#!/usr/bin/env python3
"""Doctrine checks for `references/platform-probes.md`'s register.

That file's whole job is separating what was empirically established from
what was not. The failure mode it must survive is a quiet promotion: an
UNRESOLVED probe re-worded as a settled fact, or a CONFIRMED fact losing
the evidence sentence that earns the label, with the suite still green.
The vocabulary is therefore pinned here.

A second failure mode is already realised history: the file once said the
guard relies on the payload's `cwd` as its only root signal, which
`spec_loop_guard.py:297` contradicts. The corrected precedence sentence is
pinned so it cannot silently revert.

Its own module rather than a class in test_doctrine_loop_boundary.py:
that module's docstring scopes it to commands/spec-loop.md and the
escalation-gate skill, and this file is neither.

Honest limits: these are substring assertions over collapsed prose. They
prove a sentence is present or absent. They prove nothing about the
platform's behaviour, and they are not a test of spec_loop_guard.py --
that code is tested in test_spec_loop_guard.py and
test_spec_loop_guard_stop.py.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_doctrine_platform_probes.py'
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PROBES_MD = PLUGIN_ROOT / "references" / "platform-probes.md"


def prose(path):
    """One file's text with every whitespace run collapsed to a space. (PURE)"""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


class TestUnresolvedProbesStayUnresolved(unittest.TestCase):
    """The AskUserQuestion probe produced no observation at all. Its bullet
    must keep saying so, in those words: an absence of opportunity reads as
    a negative result to anyone who skims, and a negative result is one
    edit away from being re-written as a settled fact."""

    def setUp(self):
        self.text = prose(PROBES_MD)

    def test_the_askuserquestion_bullet_is_present_and_unresolved(self):
        self.assertIn(
            "Whether `AskUserQuestion` emits `PreToolUse` at all is "
            "UNRESOLVED", self.text)

    def test_the_absence_of_opportunity_framing_survives(self):
        self.assertIn(
            "absence of opportunity, not a negative result", self.text)
        self.assertIn(
            "Nothing here licenses the claim that the event does or does "
            "not fire", self.text)

    def test_the_interactive_followups_stay_listed_as_unsettled(self):
        self.assertIn(
            "Four questions need an INTERACTIVE session to settle", self.text)
        self.assertIn("Does Ctrl+C route through `Stop`?", self.text)
        self.assertIn(
            "Does `Stop` fire at the end of a `Task` subagent's turn?",
            self.text)
        # Three of the four carry an explicit "Untested." marker; the
        # AskUserQuestion entry is covered by its own bullet above.
        self.assertEqual(self.text.count("Untested"), 3)


class TestConfirmedFactsKeepTheirEvidence(unittest.TestCase):
    """Only two hook facts were established. Each keeps its CONFIRMED label
    AND the sentence that earns it, so a label cannot outlive its
    evidence."""

    def setUp(self):
        self.text = prose(PROBES_MD)

    def test_the_stop_block_fact_is_confirmed_with_its_evidence(self):
        self.assertIn(
            "A sync `Stop` hook honours a top-level "
            "`{\"decision\":\"block\",\"reason\":…}` (CONFIRMED).", self.text)
        self.assertIn("Evidence, not inference", self.text)

    def test_the_per_turn_flag_fact_is_confirmed_with_its_evidence(self):
        self.assertIn("(CONFIRMED).** Both fires were logged in one turn",
                      self.text)
        self.assertIn(
            "pushes ONCE PER STALL rather than fencing", self.text)

    def test_exactly_two_hook_facts_are_labelled_confirmed(self):
        self.assertEqual(self.text.count("(CONFIRMED)"), 2)


class TestTheGuardRootSignalClaimStaysTrue(unittest.TestCase):
    """The shipped false claim: that the payload's `cwd` is what the guard
    relies on. `spec_loop_guard.py:297` prefers CLAUDE_PROJECT_DIR. The
    corrected sentence carries its own citation."""

    def setUp(self):
        self.text = prose(PROBES_MD)

    def test_the_false_only_root_signal_claim_is_gone(self):
        self.assertNotIn("is the only root signal", self.text)

    def test_the_true_precedence_is_stated_and_cited(self):
        self.assertIn("carries **no** `project_dir` key", self.text)
        self.assertIn("`spec_loop_guard.py:297`", self.text)
        self.assertIn(
            "the environment variable wins and the payload's `cwd` is only "
            "the first fallback", self.text)


if __name__ == "__main__":
    unittest.main()
