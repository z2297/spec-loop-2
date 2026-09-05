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

A third: the per-turn reset of stop_hook_active was written as Untested
while the run's evidence file was missing probe B2. It is CONFIRMED by that
probe's two-turn log, and the promotion is pinned in both directions here so
neither the fact nor what it rules out can be dropped.

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

# Expected substrings live at module scope, not inside the test bodies:
# quality_gate.py derives python nesting depth from leading whitespace, so a
# visually-aligned call continuation reads as depth 4. Hoisting keeps every
# assertion body at depth 1 with the assertion set unchanged.
PER_TURN_CONFIRMED = (
    "resets to `false` again at the start of every NEW user turn "
    "(CONFIRMED).**"
)
PER_TURN_EVIDENCE = (
    "established by the THIRD fire of a two-turn session (probe B2)"
)
PER_TURN_NOT_A_FENCE = (
    "pushes ONCE PER STALL rather than blocking indefinitely"
)
PER_TURN_NOT_ONE_SHOT = (
    "Not a one-shot per session: the gate re-arms on every user turn"
)
RETRACTED_UNTESTED_FRAMING = (
    "whether the gate re-arms per turn or is one-shot for the whole session"
)
RETRACTED_FOLLOWUP_QUESTION = (
    "Does `stop_hook_active` reset to `false` at the start of a new user "
    "turn?"
)


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
            "Three questions need an INTERACTIVE session to settle",
            self.text)
        self.assertIn("Does Ctrl+C route through `Stop`?", self.text)
        self.assertIn(
            "Does `Stop` fire at the end of a `Task` subagent's turn?",
            self.text)
        # Two of the three carry an explicit "Untested." marker; the
        # AskUserQuestion entry is covered by its own bullet above.
        self.assertEqual(self.text.count("Untested"), 2)


class TestConfirmedFactsKeepTheirEvidence(unittest.TestCase):
    """Only two hook facts were established, and each keeps its CONFIRMED
    label AND the sentence that earns it, so a label cannot outlive its
    evidence. The per-turn reset was promoted from Untested once probe B2
    was recorded; the framing that called it untested must not survive
    alongside the promotion."""

    def setUp(self):
        self.text = prose(PROBES_MD)

    def test_the_stop_block_fact_is_confirmed_with_its_evidence(self):
        self.assertIn(
            "A sync `Stop` hook honours a top-level "
            "`{\"decision\":\"block\",\"reason\":…}` (CONFIRMED).", self.text)
        self.assertIn("Evidence, not inference", self.text)

    def test_the_per_turn_flag_fact_is_confirmed_with_its_evidence(self):
        self.assertIn(PER_TURN_CONFIRMED, self.text)
        self.assertIn(PER_TURN_EVIDENCE, self.text)
        self.assertIn(PER_TURN_NOT_A_FENCE, self.text)
        self.assertIn(PER_TURN_NOT_ONE_SHOT, self.text)

    def test_the_retracted_untested_framing_is_gone(self):
        self.assertNotIn(RETRACTED_UNTESTED_FRAMING, self.text)
        self.assertNotIn(RETRACTED_FOLLOWUP_QUESTION, self.text)

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
