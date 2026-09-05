#!/usr/bin/env python3
"""Doctrine checks for `references/platform-probes.md`'s register.

That file's whole job is separating what was empirically established from
what was not. The failure mode it must survive is a quiet promotion: an
UNRESOLVED probe re-worded as a settled fact, or a CONFIRMED fact losing
the evidence sentence that earns the label, with the suite still green.
The vocabulary is therefore pinned here.

A second failure mode is already realised history: the file once said the
guard relies on the payload's `cwd` as its only root signal, which the
guard's `evaluate()` contradicts. The corrected precedence sentence, and
its citation-by-symbol form, are both pinned so neither can silently
revert.

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
PER_TURN_SCOPED_TO_FIRST_STOP = (
    "so it stands at the first `Stop` attempt of every turn"
)
PER_TURN_WITHIN_TURN_GAP = (
    "within that same turn the fire that ends a block-caused continuation "
    "carries the flag true and is skipped, so a turn that drives several "
    "wave boundaries is only guarded at its first one"
)
RETRACTED_UNTESTED_FRAMING = (
    "whether the gate re-arms per turn or is one-shot for the whole session"
)
RETRACTED_FOLLOWUP_QUESTION = (
    "Does `stop_hook_active` reset to `false` at the start of a new user "
    "turn?"
)
ROOT_PRECEDENCE_BY_SYMBOL = (
    "`spec_loop_guard.py`'s `evaluate()` resolves the project root as "
    "`CLAUDE_PROJECT_DIR` from the environment, then the payload's `cwd`, "
    "then `os.getcwd()`"
)
PRECEDENCE_CONSEQUENCE = (
    "the environment variable wins and the payload's `cwd` is only the "
    "first fallback"
)

# CHANGELOG.md restates this register's open-question list, so the two are
# cross-checked below. Neither count is written here: both are read out of
# the files at run time.
REPO_ROOT = PLUGIN_ROOT.parents[1]
CHANGELOG_MD = REPO_ROOT / "CHANGELOG.md"

WORD_TO_INT = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
CHANGELOG_OPEN_COUNT_RE = re.compile(
    r"the (\w+) questions that remain UNTESTED there")
PROBES_OPEN_COUNT_RE = re.compile(
    r"(\w+) questions need an INTERACTIVE session to settle")
PROBES_NUMBERED_ITEM_RE = re.compile(r"^\d+\. ", re.MULTILINE)
CHANGELOG_TOPICS = (
    "whether `AskUserQuestion` emits `PreToolUse` at all",
    "whether Ctrl+C routes through `Stop`",
    "whether `Stop` fires for `Task` subagents",
)
CHANGELOG_RETRACTED_FRAMING = "is one-shot per session is NOT established"
CHANGELOG_INSTALL_VERSION_LIMIT = (
    "The installed plugin was 2.2.0 while this repository is 2.3.0"
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

    def test_the_per_turn_reset_does_not_overclaim_per_boundary_coverage(
            self):
        # evaluate() returns None whenever stop_hook_active is true, so a
        # turn with several wave boundaries is only guarded at its first
        # Stop attempt -- the register must say so, not claim coverage at
        # every boundary.
        self.assertIn(PER_TURN_SCOPED_TO_FIRST_STOP, self.text)
        self.assertIn(PER_TURN_WITHIN_TURN_GAP, self.text)
        self.assertNotIn(
            "it stands at every wave boundary, not only the first",
            self.text)

    def test_the_retracted_untested_framing_is_gone(self):
        self.assertNotIn(RETRACTED_UNTESTED_FRAMING, self.text)
        self.assertNotIn(RETRACTED_FOLLOWUP_QUESTION, self.text)

    def test_exactly_two_hook_facts_are_labelled_confirmed(self):
        self.assertEqual(self.text.count("(CONFIRMED)"), 2)


class TestTheGuardRootSignalClaimStaysTrue(unittest.TestCase):
    """The shipped false claim: that the payload's cwd is what the guard
    relies on. The guard's evaluate() prefers CLAUDE_PROJECT_DIR. The
    corrected sentence names that symbol, not a line number — a citation
    pinned by its digits rots silently on the next insertion above it,
    which is the failure this module exists to close."""

    def setUp(self):
        self.text = prose(PROBES_MD)

    def test_the_false_only_root_signal_claim_is_gone(self):
        self.assertNotIn("is the only root signal", self.text)

    def test_the_true_precedence_is_stated_and_cited(self):
        self.assertIn("carries **no** `project_dir` key", self.text)
        self.assertIn(ROOT_PRECEDENCE_BY_SYMBOL, self.text)
        self.assertIn(PRECEDENCE_CONSEQUENCE, self.text)

    def test_no_citation_is_pinned_to_a_line_number(self):
        self.assertNotIn("spec_loop_guard.py:", self.text)


class TestChangelogAgreesWithTheProbeRegister(unittest.TestCase):
    """CHANGELOG.md restates this register's open-question list, and a
    restatement with no test is exactly how it went stale: the entry said
    four questions remained UNTESTED for a whole phase after the per-turn
    reset was promoted to CONFIRMED here.

    Scoped to THIS module rather than a new one: the subject under test is
    the probe register's contents, and a user-facing file asserting a
    different count is a claim about that register. A separate module would
    have to re-derive the register's own count anyway.

    Both counts are read out of the two files. Hard-coding three in the
    assertion would make this pin need an edit the next time a question is
    settled -- and an unedited pin is as stale as the prose it guards. The
    register's spelled-out word is additionally cross-checked against its
    numbered list items on disk, so the link is to the list, not to a word.
    """

    def setUp(self):
        self.changelog = prose(CHANGELOG_MD)
        self.probes = prose(PROBES_MD)
        self.probes_raw = PROBES_MD.read_text(encoding="utf-8")

    def _count(self, pattern, text, label):
        match = pattern.search(text)
        self.assertIsNotNone(match, "%s: count sentence not found" % label)
        word = match.group(1).lower()
        self.assertIn(word, WORD_TO_INT, "%s: %r is not a number word"
                      % (label, word))
        return WORD_TO_INT[word]

    def test_the_register_word_matches_its_numbered_list(self):
        stated = self._count(PROBES_OPEN_COUNT_RE, self.probes, "probes")
        items = len(PROBES_NUMBERED_ITEM_RE.findall(self.probes_raw))
        self.assertEqual(stated, items)

    def test_the_changelog_open_question_count_matches_the_register(self):
        changelog = self._count(
            CHANGELOG_OPEN_COUNT_RE, self.changelog, "changelog")
        probes = self._count(PROBES_OPEN_COUNT_RE, self.probes, "probes")
        self.assertEqual(changelog, probes)

    def test_the_changelog_names_each_open_question(self):
        for topic in CHANGELOG_TOPICS:
            self.assertIn(topic, self.changelog)

    def test_the_changelog_retracted_untested_framing_is_gone(self):
        self.assertNotIn(CHANGELOG_RETRACTED_FRAMING, self.changelog)

    def test_the_changelog_keeps_its_install_version_limitation(self):
        self.assertIn(CHANGELOG_INSTALL_VERSION_LIMIT, self.changelog)


if __name__ == "__main__":
    unittest.main()
