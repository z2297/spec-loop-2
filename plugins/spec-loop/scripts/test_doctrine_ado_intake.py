#!/usr/bin/env python3
"""Doctrine checks for the ADO intake command.

Four invariants prose alone will not hold: (1) the command is structurally
incapable of starting the loop or editing a file - no Workflow and no Edit
in allowed-tools; (2) its one Azure DevOps write is bounded to adding a
comment, off by default, and behind a separate confirmation that names the
item it is about to write to; (3) the artifact schema the prose promises is
the schema ado_intake.py actually renders, field name for field name; and
(4) the five claims this connector cannot afford to overstate are present in
their honest form - the target binding, the web-UI-delete re-arm, the
undeclared body format, the unverified marker round trip, and the temp-copy
residue.

Honest limit: these are substring assertions over one markdown file plus a
comparison against the module's own constants. They prove the authored tool
list and the pinned sentences are present, not that the runtime honours
them. There is deliberately NO gitignore assertion here: the repo-level
.spec-loop-ado/ entry is another slice's file, and Step 1's containment acts
on the INVOKING repo, not on this one.

Usage:
    python3 -m unittest discover -s plugins/spec-loop/scripts \\
        -p 'test_doctrine_ado_intake.py'
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ado_intake as intake

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
COMMAND_MD = PLUGIN_ROOT / "commands" / "ado-intake.md"


def raw_text():
    """The command file exactly as authored."""
    return COMMAND_MD.read_text(encoding="utf-8")


def prose():
    """The command file with every whitespace run collapsed to one space and
    em dashes normalized to '-', so a claim can be asserted without
    depending on where it wrapped or on which dash it was typed with."""
    return re.sub(r"\s+", " ", raw_text()).replace("\u2014", "-")


def allowed_tools():
    """The command's authored allowed-tools list, parsed from front matter."""
    match = re.search(r"^allowed-tools:\s*\[(.*?)\]\s*$", raw_text(), re.M)
    assert match, "ado-intake.md has no allowed-tools line"
    return [item.strip().strip('"') for item in match.group(1).split(",")]


class TestTheCommandCannotStartTheLoopOrEdit(unittest.TestCase):
    """An intake lane exists so that work-item text cannot cause work to
    begin. Absent tools are the only structural guarantee of that."""

    def test_workflow_is_absent_from_allowed_tools(self):
        self.assertNotIn("Workflow", allowed_tools())

    def test_edit_is_absent_from_allowed_tools(self):
        self.assertNotIn("Edit", allowed_tools())

    def test_the_tool_list_is_exactly_the_authored_four(self):
        expected = ["AskUserQuestion", "Bash", "Read", "Write"]
        self.assertEqual(sorted(allowed_tools()), expected)

    def test_the_description_is_quoted(self):
        """validate_marketplace refuses an unquoted frontmatter value that
        contains ': '; the description is long prose, so it is quoted."""
        match = re.search(r"^description:\s*(.*)$", raw_text(), re.M)
        self.assertIsNotNone(match)
        self.assertTrue(match.group(1).strip().startswith('"'))
        self.assertTrue(match.group(1).strip().endswith('"'))

    def test_the_handoff_is_a_printed_line_for_the_human(self):
        text = prose()
        self.assertIn("/spec-loop:spec-loop --from-plan", text)
        self.assertIn("Do not run it", text)


class TestTheAdoWriteIsBoundedToComments(unittest.TestCase):
    """The write is only safe because it is bounded, off by default, and
    confirmed, so each of those claims is pinned rather than remembered."""

    def setUp(self):
        self.text = prose()

    def test_the_write_is_bounded_to_adding_a_comment(self):
        self.assertIn(
            "comments only, never transitions or field edits", self.text)
        forbidden_claims = (
            "never a created or closed work item",
            "never a sub-task",
            "never an edit or deletion of any comment",
        )
        for forbidden in forbidden_claims:
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, self.text)

    def test_posting_is_off_by_default(self):
        self.assertIn("Posting is off by default", self.text)

    def test_the_write_is_armed_only_by_an_explicit_flag(self):
        self.assertIn("--post", self.text)
        self.assertIn("arms the HTTP verb", self.text)

    def test_the_preview_runs_without_the_flag(self):
        preview = ('ado_client.py" comment --record <tmp>/record.json '
                   "--comments <tmp>/payload.json")
        self.assertIn(preview, self.text)

    def test_the_comment_subcommand_takes_no_target_flags(self):
        """The target is derived from two files that must agree. A --id,
        --org or --project flag would re-open the disagreement that closes."""
        self.assertIn(
            "no --id, no --org and no --project on that subcommand",
            self.text)

    def test_the_dedupe_gate_is_the_items_own_comment_list(self):
        self.assertIn("work item's own full comment list", self.text)
        self.assertIn("already-posted", self.text)

    def test_the_cross_process_dedupe_window_is_disclosed(self):
        self.assertIn("read once per invocation", self.text)

    def test_recovery_is_the_posting_step_not_the_whole_command(self):
        """A regenerated refinement yields new markers, so 're-run this
        command' would double-post on a live work item. MEASURED on the
        Jira twin."""
        self.assertIn(
            "re-run the POSTING step with the same rendered payload file",
            self.text)
        self.assertIn("NOT re-run the refinement", self.text)
        self.assertIn(
            "a regenerated refinement produces new markers", self.text)
        self.assertNotIn("re-run this command", self.text)

    def test_it_carries_the_untrusted_input_framing(self):
        self.assertIn("data, never instructions", self.text)
        self.assertIn("is itself a finding to report", self.text)


class TestTheFiveClaimsThisLaneCannotOverstate(unittest.TestCase):
    """Each of these five sentences was wrong in an earlier draft of this
    connector's prose, in one direction or the other. They are pinned in the
    exact honest form, so a later 'clarifying' edit fails here."""

    def setUp(self):
        self.text = prose()

    def test_the_confirmation_names_the_title_and_the_web_url(self):
        """An ADO work item is a bare integer: an id typo lands on a real,
        different item where a mistyped Jira key would 404."""
        self.assertIn(
            "names the resolved work-item title and its web URL, not just "
            "the id", self.text)
        self.assertIn("_links.html.href", self.text)
        self.assertIn("would 404", self.text)

    def test_the_target_binding_is_stated_with_its_real_ordering(self):
        self.assertIn(
            "bound to the resolved record's (org, project, id) triple",
            self.text)
        self.assertIn(
            "refused before any credential is read and before the first "
            "request", self.text)
        self.assertIn(
            "re-proved against a freshly resolved work item after that read "
            "and before any write", self.text)

    def test_a_web_ui_delete_re_arms_the_comment(self):
        self.assertIn(
            "deleting a spec-loop comment in the Azure DevOps web UI "
            "re-arms it", self.text)
        self.assertIn("excludes deleted comments by default", self.text)
        self.assertIn("includeDeleted", self.text)
        self.assertIn("correct behaviour", self.text)

    def test_the_body_format_claim_is_the_narrow_honest_one(self):
        """The connector controls the bytes it sends, not how ADO
        interprets them. Both earlier wordings overstated this."""
        self.assertIn(
            "escapes `&`, `<` and `>` in every rendered body and refuses, "
            "before the first request, any body still carrying `<` or `>`",
            self.text)
        self.assertIn(
            "does not control how Azure DevOps interprets the stored body",
            self.text)
        self.assertIn(
            "link, image, emphasis and code-fence syntax remain active, and "
            "escaped entities may render literally", self.text)

    def test_the_overstated_body_format_wordings_are_absent(self):
        self.assertNotIn(
            "guarantees only that the body contains no active markup",
            self.text)
        self.assertNotIn(
            "reads correctly under either interpretation", self.text)

    def test_the_marker_round_trip_is_stated_as_unverified(self):
        self.assertIn(
            "has not been verified against a live organization", self.text)
        self.assertIn("7.0-preview.3", self.text)
        self.assertIn("7.1-preview.4", self.text)

    def test_the_temp_copy_residue_is_disclosed(self):
        self.assertIn(
            "retains `record.json` - the full work item, including its "
            "description, acceptance criteria, repro steps and every "
            "existing comment", self.text)
        self.assertIn(
            "protects the repository, not that temporary copy", self.text)
        self.assertIn("adds no cleanup", self.text)


class TestTheArtifactSchemaIsPinnedInBothPlaces(unittest.TestCase):
    """The command prose IS the schema a reader learns. If prose and renderer
    drift, the reader is told about fields that do not exist."""

    def setUp(self):
        self.text = raw_text()

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

    def test_the_artifact_path_is_taken_from_the_payload_not_composed(self):
        self.assertIn("never compose it by hand", prose())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
