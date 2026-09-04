#!/usr/bin/env python3
"""Doctrine checks for the Phase-2 loop-boundary prose.

The loop's failure this slice exists to fix is prose-shaped: a controller
that reaches a wave boundary with slices still runnable and ends its turn
to report. Nothing in the shipped prose said the boundary is a dispatch
point, and the escalation-gate's "Not triggers" list did not name it.
Those sentences are now load-bearing, so they are pinned here.

Honest limits: these are substring assertions over collapsed prose plus
one count of bullets on disk. They prove a sentence is present and that
its superseded form is gone. They prove nothing about whether a
controller obeys it, and they are NOT a behavioural test of the Stop
gate - that gate lives in spec_loop_guard.py and is tested there.

A separate module rather than a class in test_doctrine_refactor_scope.py
or test_doctrine_run_docs.py: those are owned by other slices' doctrine,
and slice_wave_contract_base.py is at its 300-line class ceiling.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_doctrine_loop_boundary.py'
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
COMMAND_MD = PLUGIN_ROOT / "commands" / "spec-loop.md"
SKILL_MD = PLUGIN_ROOT / "skills" / "escalation-gate" / "SKILL.md"

NUMBER_WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}

NOT_TRIGGERS_HEADING = "### Not triggers (autonomous by design)"


def prose(path):
    """One file's text with every whitespace run collapsed to a space. (PURE)"""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def not_trigger_bullet_count():
    """Count the `- **` bullets under SKILL.md's "Not triggers" heading.

    Read off the file rather than remembered, so the count word in the
    section's own opening sentence cannot drift away from the list it
    counts. The section ends at the next `## ` heading.
    """
    lines = SKILL_MD.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.strip() == NOT_TRIGGERS_HEADING)
    count = 0
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if line.startswith("- **"):
            count += 1
    return count


# ---- the skill: a runnable wave boundary is not a stopping point ----

SKILL_BOUNDARY_BULLET = "**A wave boundary with slices still runnable.**"
SKILL_DISPATCH_POINT = "a dispatch point, not a decision"
SKILL_RUNNABLE_ONLY = "This entry covers the RUNNABLE case ONLY"
SKILL_DEADLOCK_KEPT = "is the opposite: it is a genuine escalation"
SKILL_PINNED_TAIL = "exactly the six triggers above"
SKILL_OTHER_LIST = "Three things that are deliberately NOT judgment triggers"
SKILL_STALE_COUNT = "Three things that look like stopping points"


class TestTheSkillNamesTheRunnableWaveBoundary(unittest.TestCase):
    """The list of things that look like stopping points but are handled by
    the loop grows a fourth entry. It must be readable ONLY as the runnable
    case: a reported deadlock is a real escalation, and a reader who
    generalised this entry would swallow it."""

    def setUp(self):
        self.text = prose(SKILL_MD)

    def test_the_fourth_not_trigger_is_the_runnable_wave_boundary(self):
        self.assertIn(SKILL_BOUNDARY_BULLET, self.text)
        self.assertIn(SKILL_DISPATCH_POINT, self.text)

    def test_the_entry_is_scoped_to_runnable_and_spares_deadlock(self):
        self.assertIn(SKILL_RUNNABLE_ONLY, self.text)
        self.assertIn(SKILL_DEADLOCK_KEPT, self.text)

    def test_the_count_word_matches_the_bullets_on_disk(self):
        count = not_trigger_bullet_count()
        self.assertEqual(count, 4)
        word = NUMBER_WORDS[count]
        self.assertIn(
            "%s things that look like stopping points" % word, self.text)

    def test_the_superseded_three_count_is_gone(self):
        self.assertNotIn(SKILL_STALE_COUNT, self.text)

    def test_the_pinned_tail_clause_and_the_other_list_are_untouched(self):
        self.assertIn(SKILL_PINNED_TAIL, self.text)
        self.assertIn(SKILL_OTHER_LIST, self.text)
