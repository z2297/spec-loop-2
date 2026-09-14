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


IMPACT_ORDER = {"high": 0, "medium": 1, "low": 2}
LOGGED_AS_VALUES = ("decision", "open-question")
REFINEMENT_KEYS = ("description", "acceptance_criteria", "risks", "gaps",
                   "injection_findings", "answers")


_ID_FORBIDDEN = ("\n", "\r")


def _errors_for_id_newline(value, where):
    """Error strings for an id containing a line break. (PURE)

    risks[].id and gaps[].id are emitted inline into the artifact body
    WITHOUT escaping, so a multi-line id can put a third line equal to
    '---' into the file and forge the front-matter delimiter. An id is
    also a dict key in `answers` and a component of `comment_marker`, so
    it is refused rather than rewritten."""
    if not isinstance(value, str):
        return []
    if any(bad in value for bad in _ID_FORBIDDEN):
        return ["%s.id must not contain a newline" % where]
    return []


def _errors_for_gap(gap, index):
    """Error strings for ONE gap entry. (PURE)"""
    where = "gaps[%d]" % index
    if not isinstance(gap, dict):
        return ["%s must be an object" % where]
    errors = []
    for field in ("id", "question"):
        if not isinstance(gap.get(field), str) or not gap.get(field):
            errors.append("%s.%s must be a non-empty string" % (where, field))
    errors += _errors_for_id_newline(gap.get("id"), where)
    if gap.get("impact") not in IMPACT_ORDER:
        errors.append("%s.impact must be one of high|medium|low" % where)
    if not isinstance(gap.get("blocking"), bool):
        errors.append("%s.blocking must be a boolean" % where)
    return errors


def _errors_for_risk(risk, index):
    """Error strings for ONE risk entry. (PURE)"""
    where = "risks[%d]" % index
    if not isinstance(risk, dict):
        return ["%s must be an object" % where]
    errors = []
    for field in ("id", "risk"):
        if not isinstance(risk.get(field), str) or not risk.get(field):
            errors.append("%s.%s must be a non-empty string" % (where, field))
    errors += _errors_for_id_newline(risk.get("id"), where)
    if risk.get("severity") not in IMPACT_ORDER:
        errors.append("%s.severity must be one of high|medium|low" % where)
    return errors


def _errors_for_one_answer(gap_id, entry, gap_ids):
    """Error strings for ONE answers-map entry, keyed by gap id. (PURE)"""
    if gap_id not in gap_ids:
        return ["answers has no matching gap for id %s" % gap_id]
    if not isinstance(entry, dict):
        return ["answers[%s] must be an object" % gap_id]
    errors = []
    if entry.get("logged_as") not in LOGGED_AS_VALUES:
        errors.append(
            "answers[%s].logged_as must be one of decision|open-question"
            % gap_id)
    answer = entry.get("answer")
    if answer is not None and not isinstance(answer, str):
        errors.append("answers[%s].answer must be a string or null" % gap_id)
    return errors


def _errors_for_answers(answers, gap_ids):
    """Error strings for the answers map, keyed by gap id. (PURE)"""
    if not isinstance(answers, dict):
        return ["answers must be an object keyed by gap id"]
    errors = []
    for gap_id, entry in sorted(answers.items()):
        errors += _errors_for_one_answer(gap_id, entry, gap_ids)
    return errors


def _errors_for_str_list(value, name):
    """Error strings for a list-of-non-empty-strings field. (PURE)"""
    if not isinstance(value, list):
        return ["%s must be a list of strings" % name]
    return ["%s[%d] must be a non-empty string" % (name, i)
            for i, item in enumerate(value)
            if not isinstance(item, str) or not item]


def _typed_list(value, name, errors):
    """Return `value` as a list, else [] plus a type error on `errors`. (PURE
    in its return; appends to the caller's error list as a side effect, the
    same shape validate_refinement's own accumulator already uses.)"""
    if isinstance(value, list):
        return value
    errors.append("%s must be a list" % name)
    return []


def _errors_for_entries(entries, error_fn):
    """Flatten one error-list-per-entry field down to a single list. (PURE)"""
    errors = []
    for index, entry in enumerate(entries):
        errors += error_fn(entry, index)
    return errors


def _missing_keys(refinement):
    """Required refinement keys absent from `refinement`, in REFINEMENT_KEYS
    order. (PURE)"""
    return [key for key in REFINEMENT_KEYS if key not in refinement]


def _duplicate_gap_id_errors(gaps):
    """Error strings for gap ids used more than once, in first-seen order.
    (PURE)

    answers is keyed by gap id, so a repeated id makes an answer
    unattributable: both gaps resolve to the same entry. A gap with no
    usable id is already reported by _errors_for_gap, so it is skipped here
    rather than folded to a shared None sentinel."""
    seen = set()
    errors = []
    for gap in gaps:
        gap_id = gap.get("id") if isinstance(gap, dict) else None
        if not isinstance(gap_id, str) or not gap_id:
            continue
        if gap_id in seen:
            errors.append("gaps have duplicate id: %s" % gap_id)
        seen.add(gap_id)
    return errors


def validate_refinement(refinement):
    """Return a list of human-readable error strings; [] means valid. (PURE)"""
    if not isinstance(refinement, dict):
        return ["refinement must be a JSON object"]
    missing_keys = _missing_keys(refinement)
    if missing_keys:
        return ["missing required key: %s" % key for key in missing_keys]
    errors = []
    description = refinement["description"]
    if not isinstance(description, str) or not description:
        errors.append("description must be a non-empty string")
    errors += _errors_for_str_list(
        refinement["acceptance_criteria"], "acceptance_criteria")
    errors += _errors_for_str_list(
        refinement["injection_findings"], "injection_findings")
    gaps = _typed_list(refinement["gaps"], "gaps", errors)
    risks = _typed_list(refinement["risks"], "risks", errors)
    errors += _errors_for_entries(gaps, _errors_for_gap)
    errors += _errors_for_entries(risks, _errors_for_risk)
    errors += _duplicate_gap_id_errors(gaps)
    gap_ids = {g.get("id") for g in gaps if isinstance(g, dict)}
    errors += _errors_for_answers(refinement["answers"], gap_ids)
    return errors


def _gap_sort_key(gap):
    """Total, deterministic ordering key for one gap. (PURE)"""
    return (0 if gap.get("blocking") else 1,
            IMPACT_ORDER.get(gap.get("impact"), len(IMPACT_ORDER)),
            str(gap.get("id")))


def rank_gaps(gaps):
    """Blocking first, then impact, then id. Returns a new list. (PURE)"""
    return sorted(list(gaps), key=_gap_sort_key)


def main(argv=None):
    """Placeholder until the render subcommand lands (slice a3, task 8)."""
    raise NotImplementedError


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
