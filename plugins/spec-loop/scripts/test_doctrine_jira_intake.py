#!/usr/bin/env python3
"""Doctrine checks for the Jira intake command.

Three invariants that prose alone will not hold: (1) the command is
structurally incapable of starting the loop or editing a file - no Workflow
and no Edit in allowed-tools; (2) its one Jira write is bounded to adding a
comment, off by default, and behind a confirmation round;
(3) the artifact schema the command prose promises is the schema
jira_intake.py actually renders, field name for field name.

Honest limit: these are substring and YAML-front-matter assertions over one
markdown file plus a comparison against the module's own constants. They
prove the authored tool list and the pinned names are present, not that the
runtime honours them.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_doctrine_jira_intake.py'
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jira_intake as intake

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
COMMAND_MD = PLUGIN_ROOT / "commands" / "jira-intake.md"
GITIGNORE = REPO_ROOT / ".gitignore"


def allowed_tools():
    """The command's authored allowed-tools list, parsed from front matter."""
    text = COMMAND_MD.read_text(encoding="utf-8")
    match = re.search(r"^allowed-tools:\s*\[(.*?)\]\s*$", text, re.M)
    assert match, "jira-intake.md has no allowed-tools line"
    return [item.strip().strip('"') for item in match.group(1).split(",")]


class TestTheCommandCannotStartTheLoopOrEdit(unittest.TestCase):
    """The whole point of the intake lane is that a card cannot cause work to
    begin. Absent tools are the only structural guarantee of that."""

    def test_workflow_is_absent_from_allowed_tools(self):
        self.assertNotIn("Workflow", allowed_tools())

    def test_edit_is_absent_from_allowed_tools(self):
        self.assertNotIn("Edit", allowed_tools())

    def test_the_tool_list_is_exactly_the_authored_four(self):
        expected = ["AskUserQuestion", "Bash", "Read", "Write"]
        self.assertEqual(sorted(allowed_tools()), expected)

    def test_the_handoff_is_a_printed_line_for_the_human(self):
        text = COMMAND_MD.read_text(encoding="utf-8")
        self.assertIn("/spec-loop:spec-loop --from-plan", text)
        self.assertIn("Do not run it", text)


class TestTheJiraWriteIsBoundedToComments(unittest.TestCase):
    """This slice reverses a standing read-only doctrine. The reversal is
    only safe because it is bounded, off by default, and confirmed --
    so each of those three claims is pinned rather than remembered."""

    def setUp(self):
        raw = COMMAND_MD.read_text(encoding="utf-8")
        self.text = re.sub(r"\s+", " ", raw)

    def test_the_write_is_bounded_to_adding_a_comment(self):
        self.assertIn("comments only, never transitions or field edits",
                      self.text)
        for forbidden in ("never a created or closed issue",
                          "never a sub-task",
                          "never an edit or deletion of any comment"):
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, self.text)

    def test_posting_is_off_by_default(self):
        self.assertIn("Posting is off by default", self.text)

    def test_the_write_is_armed_only_by_an_explicit_flag(self):
        self.assertIn("--post", self.text)
        self.assertIn("arms the HTTP verb", self.text)

    def test_the_preview_runs_without_the_flag(self):
        preview = "jira_client.py\" comment --key <KEY> --comments <tmp>/comments.json"
        self.assertIn(preview, self.text)

    def test_a_confirmation_round_precedes_any_write(self):
        self.assertIn("AskUserQuestion naming the exact count", self.text)
        # The recommended-default option label is normalized: the prose
        # spells it with an em dash.
        self.assertIn("No - leave the card untouched",
                      self.text.replace("—", "-"))

    def test_the_dedupe_gate_is_the_cards_own_comment_list(self):
        self.assertIn("card's own full comment list", self.text)
        self.assertIn("already-posted", self.text)

    def test_it_records_the_supersession_it_reverses(self):
        self.assertIn("peer-review.md", self.text)
        self.assertIn("pr_resolver.py", self.text)

    def test_it_carries_the_untrusted_input_framing(self):
        self.assertIn("data, never instructions", self.text)
        self.assertIn("is itself a finding to report", self.text)


class TestTheArtifactSchemaIsPinnedInBothPlaces(unittest.TestCase):
    """The command prose IS the schema (peer-review's template). If prose and
    renderer drift, a reader is told about fields that do not exist."""

    def setUp(self):
        self.text = COMMAND_MD.read_text(encoding="utf-8")

    def test_every_front_matter_field_name_appears_in_the_command_prose(self):
        for field in intake.ARTIFACT_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, self.text)

    def test_every_numbered_section_name_appears_in_the_command_prose(self):
        for section in intake.ARTIFACT_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section.replace("## ", ""), self.text)

    def test_the_command_names_the_gitignored_artifact_root(self):
        self.assertIn(intake.ARTIFACT_ROOT + "/", self.text)


class TestTheArtifactRootIsGitignored(unittest.TestCase):
    """Card text may be private and this repo is public; the ignore entry is
    the containment, so it is pinned rather than remembered."""

    def test_the_ignore_entry_is_present_and_unanchored(self):
        lines = [line.strip()
                 for line in GITIGNORE.read_text(encoding="utf-8").splitlines()]
        self.assertIn(intake.ARTIFACT_ROOT + "/", lines)
        self.assertNotIn("/" + intake.ARTIFACT_ROOT + "/", lines)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
