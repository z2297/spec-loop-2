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


TRIPLE_FIELDS = ("org", "project", "id")
_SLUG_DISALLOWED_RE = re.compile(r"[^a-z0-9._-]+")
_SLUG_DASH_RUN_RE = re.compile(r"-{2,}")
_SLUG_DOT_RUN_RE = re.compile(r"[.]{2,}")


def _dict_triple_values(triple):
    """The raw org, project and id of a record-shaped dict, or raise. (PURE)"""
    if any(field not in triple for field in TRIPLE_FIELDS):
        raise IntakeUsageError(
            "error: the target must carry org, project and id; got keys "
            "%s" % (sorted(triple),))
    return [triple[field] for field in TRIPLE_FIELDS]


def validate_triple(triple):
    """Return the validated (org, project, id) tuple, else raise. (PURE)

    Accepts the tuple form or a record-shaped dict, so a caller can pass the
    resolved record straight through without re-spelling the keys. The triple
    is ONE parameter everywhere it is consumed: it is the single unit that
    binds a rendered preview to the work item it was rendered for."""
    if isinstance(triple, dict):
        values = _dict_triple_values(triple)
    elif isinstance(triple, (list, tuple)) and len(triple) == 3:
        values = list(triple)
    else:
        raise IntakeUsageError(
            "error: expected an (org, project, id) triple; got %r"
            % (triple,))
    return (validate_org(values[0]),
            validate_project_name(values[1]),
            validate_work_item_id(values[2]))


def _collapse_slug_runs(slug):
    """Collapse '-' and '.' runs, then strip both from the ends. (PURE)

    Collapsing '.' runs is what makes '..' STRUCTURALLY unrepresentable in a
    slug rather than something checked for afterwards, and stripping is what
    keeps a slug from naming a dotfile. project_slug applies this twice --
    once before the length cap and once after -- because the cap itself can
    expose a fresh trailing separator."""
    collapsed = _SLUG_DASH_RUN_RE.sub("-", _SLUG_DOT_RUN_RE.sub(".", slug))
    return collapsed.strip("-.")


def project_slug(project):
    """A path-safe slug for one ADO project name. Lossy and TOTAL. (PURE)

    Whitelist-by-construction, not an allow-list check: casefold, replace
    every character outside [a-z0-9._-] with '-', collapse runs, strip
    leading/trailing '-' and '.', cap the length, and refuse an empty
    result. '..', '/', '\\' and NUL are therefore unrepresentable rather
    than checked for. This slug is for the FILESYSTEM ONLY -- a request URL
    must use the original name, percent-encoded by the caller, because the
    slug 404s on every project whose name contains a space."""
    name = validate_project_name(project)
    slug = _collapse_slug_runs(_SLUG_DISALLOWED_RE.sub("-", name.casefold()))
    slug = _collapse_slug_runs(slug[:PROJECT_MAX_SLUG])
    if not slug or ".." in slug:
        raise IntakeUsageError(
            "error: the project name %r has no path-safe slug; rename the "
            "project or run the intake from a project whose name contains "
            "at least one letter or digit" % (project,))
    return slug


def _target_discriminator(org, project):
    """8 hex of sha256 over the ORIGINAL org and project names. (PURE)

    The slug is lossy, so two different projects can slug identically, and
    work item 42 exists in every project of every org. The discriminator is
    taken from the unslugged names so neither collision is possible."""
    joined = "\n".join([org, project]).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()[:8]


def target_dir(triple):
    """'<slug>-<hash8>/<id>' for one validated triple. (PURE)"""
    org, project, work_item_id = validate_triple(triple)
    slug = project_slug(project)
    discriminator = _target_discriminator(org, project)
    return "%s-%s/%s" % (slug, discriminator, work_item_id)


def _validated_artifact_root(artifact_root):
    """The normalized artifact root, or raise. (PURE)

    The root is the caller's, not the work item's, but it is still the outer
    half of a composed path, so it is checked before anything is composed
    against it."""
    root = str(artifact_root or "").strip().rstrip("/")
    segments = root.split("/")
    if not root or root.startswith("/") or "\\" in root or ".." in segments:
        raise IntakeUsageError(
            "error: artifact root %r must be a relative path with no '..' "
            "segment, and no backslash" % (artifact_root,))
    return root


def artifact_path(triple, artifact_root):
    """Compose the intake artifact path and ASSERT it sits under the root.

    Sanitize-and-assert: every segment is made safe first, then the composed
    path is re-checked against the normalized root, so no later change to
    the composition can escape unnoticed. The triple is one parameter both
    to keep the signature narrow and because org, project and id are only
    ever meaningful together."""
    relative = target_dir(triple)
    root = _validated_artifact_root(artifact_root)
    path = "%s/%s/intake.md" % (root, relative)
    if not path.startswith(root + "/") or ".." in path.split("/"):
        raise IntakeUsageError(
            "error: refusing to write outside the artifact root %r"
            % (root,))
    return path


def main(argv=None):
    """Placeholder until the render subcommand lands (slice a3, task 8)."""
    raise NotImplementedError


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
