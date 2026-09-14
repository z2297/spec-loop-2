#!/usr/bin/env python3
"""The one sanctioned cross-provider doctrine test.

This plugin's connectors share no runtime module on purpose: duplication over
coupling, so loosening one provider cannot loosen another. That stance has a
cost this test pays. The bounded-write claim set is the safety contract of
BOTH intake commands, and it now exists as two independently authored copies
of the same promise. Each command's own doctrine test asserts its own copy,
so the two can drift apart while both suites stay green - and the drift
would be invisible in exactly the place it matters, since an operator reads
one file and generalizes to the other.

So this file asserts ONE property: every intake command makes the same
bounded-write claim set. It is prose parity only. It imports neither
connector, asserts nothing about runtime behaviour, and is deliberately the
ONLY shared artifact between the two lanes.

The Jira lane says "issue" where the ADO lane says "work item", so each
claim is a regex alternation rather than a substring. That is a vocabulary
difference, not a contract difference; anything stronger would require
editing jira-intake.md, whose prose is frozen.

Honest limit: this proves both files CLAIM the same bounds. That the
connectors HONOUR them is asserted in test_ado_client.py and
test_jira_client.py, not here.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_doctrine_intake_parity.py'
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
COMMANDS = PLUGIN_ROOT / "commands"
INTAKE_COMMANDS = ("jira-intake.md", "ado-intake.md")

# Each entry: a human name for the claim, and a regex that must match the
# whitespace-collapsed prose of EVERY intake command. The alternations cover
# the one sanctioned vocabulary difference (issue / work item / card).
BOUNDED_WRITE_CLAIMS = (
    ("comments only, never a transition or a field edit",
     r"comments only, never transitions or field edits"),
    ("never a created or closed item",
     r"never a created or closed (?:issue|work item)"),
    ("never a sub-task", r"never a sub-task"),
    ("never a comment edited or deleted",
     r"never an edit or deletion of any comment"),
    ("posting is off by default", r"Posting is off by default"),
    ("the write is armed only by an explicit flag", r"arms the HTTP verb"),
)


def prose(name):
    """One command file's text, every whitespace run collapsed to a space."""
    raw = (COMMANDS / name).read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", raw)


class TestEveryIntakeCommandExists(unittest.TestCase):
    """If a third intake command is ever added, INTAKE_COMMANDS must grow
    with it - otherwise this parity test silently stops covering the new
    one, which is the failure mode it exists to prevent."""

    def test_the_named_commands_are_on_disk(self):
        for name in INTAKE_COMMANDS:
            with self.subTest(name=name):
                self.assertTrue((COMMANDS / name).is_file())

    def test_no_intake_command_is_missing_from_the_list(self):
        on_disk = sorted(p.name for p in COMMANDS.glob("*-intake.md"))
        self.assertEqual(on_disk, sorted(INTAKE_COMMANDS))


class TestTheBoundedWriteClaimSetIsIdenticalAcrossProviders(
        unittest.TestCase):
    """Both intake lanes reverse this plugin's read-only doctrine, and both
    are safe only because the reversal is bounded to adding a comment. The
    bound is stated in prose, twice, by hand. This is the only thing that
    keeps the two statements the same statement."""

    def test_every_command_makes_every_bounded_write_claim(self):
        for name in INTAKE_COMMANDS:
            text = prose(name)
            for claim, pattern in BOUNDED_WRITE_CLAIMS:
                with self.subTest(command=name, claim=claim):
                    self.assertRegex(text, pattern)

    def test_no_command_offers_re_running_itself_as_recovery(self):
        """Measured on the Jira twin: the marker hashes the regenerated
        refinement, so 're-run this command' means a second near-identical
        comment on a live item. Neither lane may offer it."""
        for name in INTAKE_COMMANDS:
            with self.subTest(command=name):
                self.assertNotIn("re-run this command", prose(name))

    def test_every_command_scopes_recovery_to_the_posting_step(self):
        for name in INTAKE_COMMANDS:
            with self.subTest(command=name):
                self.assertRegex(
                    prose(name),
                    r"re-run the POSTING step with the same rendered "
                    r"(?:comments|payload) file")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
