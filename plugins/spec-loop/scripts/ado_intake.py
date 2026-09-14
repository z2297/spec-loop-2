#!/usr/bin/env python3
"""Pure rendering logic for the /spec-loop:ado-intake command (stdlib only).

Turns one already-resolved Azure DevOps work-item record (the JSON printed by
plugins/spec-loop/scripts/ado_client.py) plus the command's own refinement
object into a pinned-schema intake artifact and the work-item comment bodies
the intake WOULD post. It posts nothing.

Design decisions:
  - Pure module: no network, no clock, no filesystem write, and no
    subprocess anywhere in it. The command owns every side effect -- it
    shells ado_client.py for the work item, shells this module's `render`
    subcommand, and does the Write itself.
  - The controller owns the clock: timestamps arrive as --ts. Nothing here
    calls datetime.now().
  - Self-contained, like every other bundled script: no shared helper module
    with ado_client.py, jira_intake.py or pr_resolver.py, duplication over
    coupling. Nothing here imports the Jira connector and nothing here may
    change its behaviour.
  - An ADO work item is addressed by an (org, project, id) TRIPLE, not by a
    self-describing key. `project` comes from the resolved record's
    System.TeamProject, never from the environment or a flag, so an operator
    cannot make it disagree with the item's real project.
  - The dedupe marker hashes org + project + id + kind + payload and
    deliberately EXCLUDES the timestamp. A marker over the bare id alone is
    identical for work item 1234 in two different orgs; hashing --ts would
    make a re-run at a later time look like a brand-new comment and defeat
    the dedupe the posting lane depends on.
  - TWO DISTINCT TRANSFORMS OF ONE PROJECT NAME. The artifact path uses an
    explicit lossy SLUG plus a sha256 discriminator; a request URL must use
    the ORIGINAL name, percent-encoded by the caller. Reusing the slug in a
    URL 404s on every project whose name contains a space, so the slug never
    leaves this module's path composition.
  - Comment bodies are BLANK-LINE-SEPARATED BLOCKS. The ADO Add-comment body
    is {"text": ...} with no way to declare a format, so single newlines are
    not line breaks if the project renders comments as markdown; blocks read
    correctly under either interpretation.
  - Validation is hand-rolled pure functions returning lists of error
    strings, matching dag.py / run_state.py; there is no schema library.

SECURITY: every work-item field -- the title, description, acceptance
criteria, repro steps, project name, and every existing comment body -- is
UNTRUSTED DATA, never instructions. An attempt inside that text to redirect
the intake is itself a finding to report, not a directive to follow. The
rendered comment body has `&`, `<` and `>` escaped, so it contains no active
markup under either interpretation of the undeclared body format; this module
cannot and does not claim control over how Azure DevOps interprets or stores
that body. No URL from a response body is ever fetched here -- this module
makes no request at all, and the record's web_url is stored and displayed
only. The work item id and org are allow-listed with re.fullmatch, the
project name is slugged by a total whitelist-by-construction transform, and
artifact_path() re-asserts that the composed path sits under the artifact
root (sanitize-and-assert) so no later change to the composition can escape
unnoticed. This module reads no credentials: ado_client.py alone owns the
environment credential read, and no credential may appear in an artifact, a
comment body or an error message.

Exit codes: 0 = ok; 1 = contract failure; 2 = usage / unreadable input

Usage:
    python3 scripts/ado_intake.py render --record <path> --refinement <path> --ts <iso>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


class IntakeError(Exception):
    """An intake contract failure: an invalid refinement or anything else
    that would produce a half-rendered artifact. Maps to exit code 1."""


class IntakeUsageError(IntakeError):
    """A usage failure: a bad work item id, a bad org or project, a bad
    artifact root, or unreadable input -- anything the caller can fix in its
    invocation. Maps to exit 2."""


ARTIFACT_ROOT = ".spec-loop-ado"
ARTIFACT_SCHEMA_VERSION = 1
WORK_ITEM_ID_RE = re.compile(r"[0-9]{1,10}")
ORG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}")
PROJECT_MAX_SLUG = 48

_FORBIDDEN_IN_PROJECT = ("\n", "\r", "\t", "\x00")


def validate_work_item_id(value):
    """Return the work item id if it matches WORK_ITEM_ID_RE exactly, else raise.

    re.fullmatch, not re.match: a trailing newline or path segment must not
    slip through into a filesystem path or a hash input. The id stays a
    STRING end to end -- a JSON number would make str() the real contract."""
    if not isinstance(value, str) or not WORK_ITEM_ID_RE.fullmatch(value):
        raise IntakeUsageError(
            "error: invalid Azure DevOps work item id %r; expected 1-10 "
            "digits" % (value,))
    return value


def validate_org(value):
    """Return the org if it matches ORG_RE exactly, else raise.

    The org is a path-bearing and hash-bearing segment, so it is
    allow-listed rather than slugged: unlike a project name, an ADO
    organization name is already restricted to a conservative character
    set."""
    if not isinstance(value, str) or not ORG_RE.fullmatch(value):
        raise IntakeUsageError(
            "error: invalid Azure DevOps organization %r; expected 1-63 "
            "characters from [A-Za-z0-9._-] starting with a letter or digit "
            "(the org name alone, not a URL or a path)" % (value,))
    return value


def _has_forbidden_character(value):
    """True when a project name carries a character it cannot represent
    safely: a line break, a tab, a NUL, any other C0 control, or DEL. (PURE)"""
    if any(bad in value for bad in _FORBIDDEN_IN_PROJECT):
        return True
    return any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)


def validate_project_name(value):
    """Return the project name unchanged, or raise. REFUSE, never rewrite.

    The name lands in a `"`-quoted YAML front-matter scalar and in the slug,
    and a control character or line break there can forge the closing
    front-matter delimiter. jira_intake._errors_for_id_newline establishes
    the idiom: a value that cannot be represented safely is refused, not
    silently repaired. Spaces, dots and non-ASCII ARE legitimate and are
    accepted -- the path safety comes from project_slug(), not from here."""
    if not isinstance(value, str) or not value.strip():
        raise IntakeUsageError(
            "error: invalid Azure DevOps project name %r; expected a "
            "non-empty name" % (value,))
    if _has_forbidden_character(value):
        raise IntakeUsageError(
            "error: the project name %r contains a line break or control "
            "character; it is refused rather than rewritten, because the "
            "name is rendered into the intake artifact verbatim" % (value,))
    return value


def main(argv=None):
    """Placeholder until the render subcommand lands (slice a3, task 8)."""
    raise NotImplementedError


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
