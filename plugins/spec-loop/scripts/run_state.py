#!/usr/bin/env python3
"""Sidecars, events, and prose rendering for a spec-loop run (stdlib only).

Every durable per-slice fact a wave produces enters run state through this
script (shapes pinned in references/run-state-v2.md):

    slice-<id>-status.json   the tool-validated SliceResult sidecar
    events.jsonl             the append-only machine channel (run_metrics reads it)
    decisions-log.md         human render of decision/deferred/gate events
    escalations.md           human render of EscalationRecords, answers written back
    slice-<id>-report.md     short human summary of one sidecar

Design decisions:
- **Validation is the gate, and it fails closed.** `persist-slice` validates the
  SliceResult against the sidecar contract BEFORE writing anything; an invalid
  object is refused with `{"ok": false, "errors": [...]}` and exit 1, and the
  caller treats that slice as ESCALATED. A slice that cannot describe its own
  outcome is not a slice we may record as DONE. Validation reports every problem
  at once so one round-trip is enough, and `validate-sidecar` exposes the same
  check standalone.
- **The controller owns the clock.** Every timestamp is passed in with `--ts`;
  nothing here calls `datetime.now()`. Workflow scripts have no clock, so the
  stamped `ts` is the controller's, consistently.
- **One writer, one path.** All prose is rendered from the structured objects as
  a side effect of appending the event, so a fact can never reach events.jsonl
  without reaching the human surface (or vice versa). Nothing parses the prose
  back — `escalations.md` carries an HTML-comment id anchor purely so an answer
  can be written back to the right entry deterministically.
- **The sidecar is the single home of per-slice facts.** `persist-slice` emits
  only events that have their own type in the contract (`council-verdict`,
  `review-summary`, `quality-gate`, `escalation-*`); it never re-emits the
  slice's own outcome — status, commits, tiers, counts, timings — as an event.
  Readers that want those read the sidecar, so there is nothing to drift.
  A sidecar carrying none of those facts (a bare FAILED result) therefore
  appends no events at all, and that is correct.
- **Pure renderers.** `validate_sidecar`, `render_report`, `render_escalation`,
  `answer_escalation`, and `decision_line` are pure functions over objects and
  markdown text, so the whole contract is testable without a filesystem.
- **Null-honest.** Missing values are omitted from prose and preserved as `null`
  in payloads; nothing is invented to fill a gap.
- **Atomic where it matters.** Sidecars and reports are rewritten via a temp
  file plus `os.replace`; events.jsonl and decisions-log.md are append-only
  single-writer files, so an O_APPEND write is the atomic operation there.

Exit codes: 0 = ok; 1 = contract failure (invalid sidecar); 2 = usage /
unreadable input (bad JSON, bad `--ts`, non-object payload).

Usage:
    run_state.py persist-slice    --run-dir <dir> --json <file|-> --wave N --ts <ISO>
    run_state.py append-event     --run-dir <dir> --ts <ISO> --scope <s>
                                  --type <t> [--payload <json|->]
    run_state.py open-escalations  --run-dir <dir>
    run_state.py validate-sidecar  --run-dir <dir> --file <file|->
"""

import argparse
import json
import os
import re
import sys
import tempfile

SCHEMA_VERSION = 2
SLICE_RESULT_STATUSES = ("DONE", "SPLIT", "ESCALATED", "FAILED")
QUALITY_STATUSES = ("PASS", "FAIL", "SKIPPED")
VERDICTS = ("ENDORSE", "ENDORSE_WITH_CONCERNS", "OBJECT", "SKIPPED")
ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
                       "council-objection", "quality-gate-block", "budget-exhausted")
ESCALATION_STATUSES = ("OPEN", "ANSWERED")
RISK_TIERS = (1, 2, 3)
# Matches dag.py: references/split-ingestion.md calls a one-child split a
# malformed proposal, so a SPLIT sidecar proposing one is refused here too.
MIN_SPLIT_CHILDREN = 2

EVENTS_FILE = "events.jsonl"
DECISIONS_LOG = "decisions-log.md"
ESCALATIONS_MD = "escalations.md"

# Event types whose payload is also rendered for humans.
ESCALATION_EVENTS = ("escalation-opened", "escalation-answered")
DECISION_EVENTS = ("decision", "deferred", "council-verdict", "quality-gate",
                   "integration-check", "phase5-gate")

DECISIONS_HEADER = ("# Decisions log\n\n"
                    "Rendered from the run's events; append-only, and nothing "
                    "parses it back.\n\n")
ESCALATIONS_HEADER = ("# Escalations\n\n"
                      "Rendered from EscalationRecords; answers are written back "
                      "into the matching entry.\n\n")

ID_ANCHOR = "<!-- escalation-id: %s -->"
SUMMARY_LIMIT = 200
# Payload keys, in priority order, that may carry a human-readable one-liner.
# Module-level for the same reason as the messages below: a wrapped literal
# inside _first_text's loop reads as nesting to the quality gate.
SUMMARY_TEXT_KEYS = ("summary", "decision", "title", "question", "detail",
                     "answer", "result", "status", "note")
# critique.over_scope validation messages. Module-level so _over_scope_errors
# stays flat: the quality gate derives nesting/cognitive scores from indentation,
# and wrapped message literals inside the checks push it past both thresholds.
OVER_SCOPE_NOT_OBJECT = ("critique.over_scope must be a JSON object when "
                         "present (found %r)")
OVER_SCOPE_BAD_FLAG = "critique.over_scope.flag must be true or false (found %r)"
OVER_SCOPE_BAD_REASON = ("critique.over_scope.reason must be a string or null "
                         "when present (found %r)")
# Deliberately permissive ISO-8601: date, optional time, optional fraction, and
# an optional Z / ±HH:MM offset. The controller supplies UTC stamps.
ISO_TS = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?)?$")


class RunStateError(Exception):
    """Input could not be read or used at all — exit 2."""


class SidecarInvalid(Exception):
    """The SliceResult violates the sidecar contract — exit 1."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


# --------------------------------------------------------------------------
# small io helpers
# --------------------------------------------------------------------------

def _atomic_write(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".run-state-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except OSError as exc:
        raise RunStateError("cannot write %s: %s" % (path, exc))


def _append_text(path, text, header=""):
    """Append to a prose/jsonl file, creating it (with its header) if needed."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        fresh = not os.path.exists(path)
        with open(path, "a", encoding="utf-8") as fh:
            if fresh and header:
                fh.write(header)
            fh.write(text)
    except OSError as exc:
        raise RunStateError("cannot append to %s: %s" % (path, exc))


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def read_json(path):
    """Read a JSON object from a path, or from stdin when path is '-'."""
    try:
        if path == "-":
            return json.loads(sys.stdin.read())
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise RunStateError("cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise RunStateError("%s is not valid JSON: %s" % (path, exc))


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _nonempty_str(value):
    return isinstance(value, str) and bool(value.strip())


def _one_line(text, limit=SUMMARY_LIMIT):
    collapsed = " ".join(str(text).split())
    return collapsed if len(collapsed) <= limit else collapsed[:limit - 1] + "…"


# --------------------------------------------------------------------------
# validation — pure
# --------------------------------------------------------------------------

def validate_escalation(record, label):
    """Return every contract violation in one EscalationRecord."""
    if not isinstance(record, dict):
        return ["%s must be a JSON object" % label]
    errors = []
    if not _nonempty_str(record.get("id")):
        errors.append("%s: id must be a non-empty string "
                      "(\"<slice-id>:<trigger>[:<round>]\")" % label)
    if record.get("trigger") not in ESCALATION_TRIGGERS:
        errors.append("%s: trigger must be one of %s (found %r)"
                      % (label, "/".join(ESCALATION_TRIGGERS), record.get("trigger")))
    if not _nonempty_str(record.get("title")):
        errors.append("%s: title must be a non-empty string" % label)
    if not _nonempty_str(record.get("question")):
        errors.append("%s: question must be a non-empty string" % label)
    if "status" in record and record.get("status") not in ESCALATION_STATUSES:
        errors.append("%s: status must be OPEN or ANSWERED (found %r)"
                      % (label, record.get("status")))
    options = record.get("options")
    if not isinstance(options, list) or not options:
        errors.append("%s: options must be a non-empty list" % label)
    else:
        for position, option in enumerate(options):
            if not isinstance(option, dict):
                errors.append("%s: option %d must be a JSON object" % (label, position + 1))
            elif not _nonempty_str(option.get("label")):
                errors.append("%s: option %d has no label" % (label, position + 1))
    return errors


def _validate_children(children, label="split.children"):
    errors = []
    if not isinstance(children, list) or len(children) < MIN_SPLIT_CHILDREN:
        return ["%s must list at least %d children — a one-child split is the "
                "same slice, not a decomposition" % (label, MIN_SPLIT_CHILDREN)]
    for position, child in enumerate(children):
        number = position + 1
        if not isinstance(child, dict):
            errors.append("%s[%d] must be a JSON object" % (label, number))
            continue
        if not _nonempty_str(child.get("goal")):
            errors.append("%s[%d] has no goal" % (label, number))
        refs = child.get("internal_deps")
        if refs is None:
            continue
        if not isinstance(refs, list):
            errors.append("%s[%d]: internal_deps must be a list" % (label, number))
            continue
        for ref in refs:
            if not _is_int(ref) or ref < 1 or ref > len(children) or ref == number:
                errors.append("%s[%d]: internal_deps entry %r is not another "
                              "child's 1-based index" % (label, number, ref))
    return errors


def _returned_event_errors(events):
    """Validate the workflow's `events[]` entries: {scope?, type, payload?}.

    Fail-closed like the rest of the sidecar: an entry with no usable `type`
    would be appended to events.jsonl as an unreadable line, so it is refused
    here rather than written and ignored downstream.
    """
    if not isinstance(events, list):
        return []
    errors = []
    for position, entry in enumerate(events):
        label = "events[%d]" % (position + 1)
        if not isinstance(entry, dict):
            errors.append("%s must be a JSON object" % label)
            continue
        if not _nonempty_str(entry.get("type")):
            errors.append("%s: type must be a non-empty event type" % label)
        if entry.get("payload") is not None and not isinstance(entry["payload"], dict):
            errors.append("%s: payload must be a JSON object when present" % label)
        if entry.get("scope") is not None and not _nonempty_str(entry.get("scope")):
            errors.append("%s: scope must be a non-empty string when present" % label)
    return errors


def validate_sidecar(body):
    """Return every contract violation in a SliceResult sidecar.

    Fail-closed by construction: an unknown or missing `status` is itself an
    error, so a sidecar can never slip past the per-status requirements by
    naming a status this contract does not know. The checks are split into
    focused, PURE helpers by concern (top-level fields, shape/type checks,
    critique/quality, and per-status requirements) so no single function's
    branching grows unbounded as the contract grows.
    """
    if not isinstance(body, dict):
        return ["sidecar must contain a JSON object"]

    top_errors, status = _top_level_sidecar_errors(body)
    errors = list(top_errors)
    errors.extend(_shape_errors(body))
    errors.extend(_critique_and_quality_errors(body))
    split = body.get("split")
    if isinstance(split, dict):
        errors.extend(_validate_children(split.get("children")))
    for position, record in enumerate(body.get("escalations") or []):
        errors.extend(validate_escalation(record, "escalations[%d]" % (position + 1)))
    errors.extend(_status_requirement_errors(status, body, split))
    return errors


def _top_level_sidecar_errors(body):
    """schema_version/id/status checks (PURE). Returns (errors, normalized_status)."""
    errors = []
    if body.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be %d (found %r)" % (SCHEMA_VERSION, body.get("schema_version")))
    if not _nonempty_str(body.get("id")):
        errors.append("id must be a non-empty slice id")
    status = body.get("status")
    if status not in SLICE_RESULT_STATUSES:
        errors.append("status must be one of %s (found %r)" % ("/".join(SLICE_RESULT_STATUSES), status))
        status = None
    return errors, status


_SHAPE_TYPE_FIELDS = (
    ("commits", dict, "JSON object"), ("critique", dict, "JSON object"),
    ("review", dict, "JSON object"), ("tests", dict, "JSON object"),
    ("quality", dict, "JSON object"), ("split", dict, "JSON object"),
    ("escalations", list, "list"), ("events", list, "list"),
)


def _shape_errors(body):
    """Type/shape checks for the optional top-level fields (PURE)."""
    errors = _shape_type_errors(body)
    errors.extend(_shape_numeric_errors(body))
    return errors


def _shape_type_errors(body):
    """Type checks on the optional dict/list fields, the event list's own
    content, and the `branch` string field (PURE)."""
    errors = []
    for key, kind, noun in _SHAPE_TYPE_FIELDS:
        if key in body and body[key] is not None and not isinstance(body[key], kind):
            errors.append("%s must be a %s when present" % (key, noun))
    errors.extend(_returned_event_errors(body.get("events")))
    if "branch" in body and body["branch"] is not None and not _nonempty_str(body["branch"]):
        errors.append("branch must be a non-empty string when present")
    return errors


def _shape_numeric_errors(body):
    """The integer fields and the tier-enum fields (PURE)."""
    errors = []
    for key in ("wave", "tasks_completed", "agents_used"):
        message = _int_field_error(body, key)
        if message:
            errors.append(message)
    for key in ("risk_tier", "review_tier"):
        message = _tier_field_error(body, key)
        if message:
            errors.append(message)
    return errors


def _int_field_error(body, key):
    """The error for one integer field, or None when it is valid (PURE)."""
    if body.get(key) is not None and not _is_int(body[key]):
        return "%s must be an integer when present (found %r)" % (key, body[key])
    return None


def _tier_field_error(body, key):
    """The error for one risk/review tier field, or None when valid (PURE)."""
    if body.get(key) is not None and body[key] not in RISK_TIERS:
        return "%s must be 1, 2 or 3 when present (found %r)" % (key, body[key])
    return None


def _critique_and_quality_errors(body):
    """critique.verdict/critique.over_scope and quality.status checks (PURE)."""
    errors = _critique_errors(body.get("critique"))
    quality = body.get("quality")
    if isinstance(quality, dict) and quality.get("status") not in QUALITY_STATUSES:
        errors.append("quality.status must be one of %s (found %r)" % ("/".join(QUALITY_STATUSES), quality.get("status")))
    return errors


def _critique_errors(critique):
    """critique.verdict and critique.over_scope checks (PURE)."""
    if not isinstance(critique, dict):
        return []
    errors = []
    if critique.get("verdict") not in VERDICTS:
        errors.append("critique.verdict must be one of %s (found %r)" % ("/".join(VERDICTS), critique.get("verdict")))
    errors.extend(_over_scope_errors(critique.get("over_scope")))
    return errors


def _status_requirement_errors(status, body, split):
    """Per-status required-field checks (PURE)."""
    if status == "DONE":
        return _done_requirement_errors(body)
    if status == "SPLIT":
        if not isinstance(split, dict):
            return ["SPLIT requires split.children (the proposed children)"]
        return []
    if status == "ESCALATED":
        if not body.get("escalations"):
            return ["ESCALATED requires a non-empty escalations list"]
        return []
    return []


def _done_requirement_errors(body):
    """The DONE-status field requirements (PURE)."""
    errors = []
    commits = body.get("commits")
    if not isinstance(commits, dict):
        errors.append("DONE requires commits with a head sha")
    elif not _nonempty_str(commits.get("head")):
        errors.append("DONE requires commits.head (a DONE slice committed something)")
    tests = body.get("tests")
    if not isinstance(tests, dict):
        errors.append("DONE requires tests (command, result, scope)")
    elif not _nonempty_str(tests.get("result")):
        errors.append("DONE requires tests.result")
    if not isinstance(body.get("quality"), dict):
        errors.append("DONE requires quality (status, detail)")
    return errors


def _over_scope_errors(block):
    """Messages for a `critique.over_scope` record (PURE).

    Absent — and an explicit `null` — mean "no scope judgement was recorded",
    which is a different claim from `flag: false` and is therefore valid. When
    the block IS present it must carry both halves of the record: a real
    boolean `flag`, and a `reason` that is a string or null. Every problem is
    reported; nothing short-circuits.
    """
    if block is None:
        return []
    if not isinstance(block, dict):
        return [OVER_SCOPE_NOT_OBJECT % (block,)]
    errors = []
    flag = block.get("flag")
    reason = block.get("reason")
    if not isinstance(flag, bool):
        errors.append(OVER_SCOPE_BAD_FLAG % (flag,))
    if reason is not None and not isinstance(reason, str):
        errors.append(OVER_SCOPE_BAD_REASON % (reason,))
    return errors


# --------------------------------------------------------------------------
# renderers — pure
# --------------------------------------------------------------------------

def _ordered_options(record):
    """Recommended options first, otherwise in the order given."""
    options = [o for o in (record.get("options") or []) if isinstance(o, dict)]
    return ([o for o in options if o.get("recommended")]
            + [o for o in options if not o.get("recommended")])


def render_escalation(scope, record):
    """Render one EscalationRecord as its escalations.md entry (PURE)."""
    status = record.get("status") or "OPEN"
    lines = ["## [%s] %s   (status: %s)"
             % (scope, _one_line(record.get("title") or "(untitled)"), status),
             ID_ANCHOR % (record.get("id") or "?"),
             "- Trigger: %s" % (record.get("trigger") or "(not recorded)"),
             "- Opened: %s" % (record.get("opened") or "(not recorded)"),
             "- Context: %s" % _one_line(record.get("context") or "(not recorded)", 400),
             "- The decision: %s" % _one_line(record.get("question") or "(not recorded)",
                                              400),
             "- Options:"]
    for position, option in enumerate(_ordered_options(record)):
        marker = "(RECOMMENDED DEFAULT) " if option.get("recommended") else ""
        detail = _one_line(option.get("detail") or "", 300)
        lines.append("  %d. %s — %s%s" % (position + 1, option.get("label"),
                                          marker, detail))
    lines.append("- If unanswered: %s"
                 % _one_line(record.get("if_unanswered") or "(not recorded)", 300))
    answer = record.get("answer")
    lines.append("- Answer:%s" % (" " + _one_line(answer, 400) if answer else ""))
    lines.append("- Answered-at:%s"
                 % (" " + record["answered_at"] if record.get("answered_at") else ""))
    return "\n".join(lines) + "\n\n"


def answer_escalation(body, escalation_id, answer, answered_at):
    """Write an answer into the matching escalations.md entry (PURE).

    Returns (updated markdown, matched?). The entry is located by its id
    anchor, so re-titled or reordered entries still resolve.
    """
    anchor = ID_ANCHOR % escalation_id
    lines = body.splitlines(True)
    try:
        at = next(i for i, line in enumerate(lines) if line.strip() == anchor)
    except StopIteration:
        return body, False

    for index in range(at, -1, -1):
        if lines[index].startswith("## "):
            lines[index] = lines[index].replace("(status: OPEN)", "(status: ANSWERED)")
            break
    for index in range(at + 1, len(lines)):
        if lines[index].startswith("## "):
            break
        if lines[index].startswith("- Answer:"):
            lines[index] = "- Answer: %s\n" % _one_line(answer or "", 400)
        elif lines[index].startswith("- Answered-at:"):
            lines[index] = "- Answered-at: %s\n" % answered_at
    return "".join(lines), True


def _summarize(event):
    """One-line human summary of an event payload (PURE)."""
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        return _one_line(payload)
    event_type = event.get("type")
    if event_type == "council-verdict":
        return _verdict_summary(payload)
    if event_type in ("quality-gate", "integration-check", "phase5-gate"):
        outcome = payload.get("status") or payload.get("result") or "(no result)"
        detail = payload.get("detail") or payload.get("summary")
        return "%s%s" % (outcome, " — %s" % _one_line(detail) if detail else "")
    if event_type == "deferred" and payload.get("over_scope") is True:
        return "SCOPE %s" % _first_text(payload)
    return _first_text(payload)


def _verdict_summary(payload):
    """The council-verdict line (PURE).

    `safety` is pinned in the contract and is the objection that halts the loop
    alone, so it is named whenever it is set. The `over_scope` record is
    rendered whenever the payload carries one — including `flag: false` — so a
    council that looked and found nothing is distinguishable from a council
    that never looked. It is a record, never a verdict: it changes no branch.
    """
    prefix = "SAFETY " if payload.get("safety") else ""
    line = "%s%s" % (prefix, payload.get("verdict") or "(no verdict)")
    if payload.get("concerns"):
        line += " (%s concerns)" % (payload["concerns"],)
    note = _scope_note(payload.get("over_scope"))
    if note:
        line += " [%s]" % (note,)
    return line


def _scope_note(block):
    """Human phrase for an over-scope record, or None when none was recorded (PURE).

    Four distinct outcomes, none collapsed into another: absent/null -> None
    (nothing is rendered at all), `flag: false` -> "scope: clean",
    `flag: true` -> the flag plus its reason when one was given, and anything
    malformed -> "scope: unreadable" rather than a silent pass.
    """
    if block is None:
        return None
    if not isinstance(block, dict) or not isinstance(block.get("flag"), bool):
        return "scope: unreadable"
    reason = block.get("reason")
    if reason is not None and not isinstance(reason, str):
        return "scope: unreadable"
    if not block["flag"]:
        return "scope: clean"
    if isinstance(reason, str) and reason.strip():
        return "SCOPE-FLAGGED: %s" % _one_line(reason)
    return "SCOPE-FLAGGED"


def _first_text(payload):
    """The first human-readable field of an arbitrary payload (PURE)."""
    for key in SUMMARY_TEXT_KEYS:
        if payload.get(key):
            return _one_line(payload[key])
    return _one_line(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def decision_line(event):
    """The decisions-log.md line for an event (PURE)."""
    return "[%s] %s: %s — AT: %s" % (event.get("scope"),
                                     str(event.get("type")).upper(),
                                     _summarize(event), event.get("ts"))


def _orphan_answer_entry(event):
    """An answer whose escalation entry is missing must still be visible."""
    payload = event.get("payload") or {}
    escalation_id = payload.get("id") or "?"
    return ("## [%s] Answer without a matching escalation entry   "
            "(status: ANSWERED)\n%s\n"
            "- Opened: (not recorded — no escalation-opened entry was rendered)\n"
            "- Answer: %s\n- Answered-at: %s\n\n"
            % (event.get("scope"), ID_ANCHOR % escalation_id,
               _one_line(payload.get("answer") or "", 400),
               payload.get("answered_at") or event.get("ts")))


def render_report(body):
    """Render the short human summary of one sidecar (PURE, null-honest).

    The sections below are split into focused, PURE helpers by concern (the
    top summary bullets, then the optional residual/split/escalations
    sections) so no single function's branching grows unbounded as the
    report grows new sections.
    """
    slice_id = body.get("id") or "?"
    review = body.get("review") if isinstance(body.get("review"), dict) else {}
    lines = ["# Slice %s — %s" % (slice_id, body.get("status") or "UNKNOWN"), ""]
    lines += _report_summary_lines(body, review)
    lines += _report_residual_lines(review)
    lines += _report_split_lines(body)
    lines += _report_escalation_lines(body)
    footer = "_Rendered from slice-%s-status.json; that sidecar is authoritative._" % slice_id
    lines += ["", footer, ""]
    return "\n".join(lines)


def _report_summary_lines(body, review):
    """The top `- **Label:** value` bullets of a slice report (PURE).

    Each non-trivial field's value is computed by its own small PURE helper
    (returning None when the field contributes no bullet) so this function
    stays a flat dispatch table rather than growing nested per-field logic."""
    lines = []

    def add(label, value):
        if value not in (None, "", []):
            lines.append("- **%s:** %s" % (label, value))

    add("Wave", body.get("wave"))
    add("Branch", body.get("branch"))
    add("Commits", _report_commits_value(body))
    add("Risk tier", _report_risk_tier_value(body))
    add("Tasks completed", body.get("tasks_completed"))
    add("Tests", _report_tests_value(body))
    add("Quality gate", _report_quality_value(body))
    add("Iron Council", _report_council_value(body))
    if review:
        add("Review", _review_summary(review))
    add("Agents used", body.get("agents_used"))
    add("Window", _report_window_value(body))
    return lines


def _report_commits_value(body):
    """The `Commits` bullet's value, or None (PURE)."""
    commits = body.get("commits") if isinstance(body.get("commits"), dict) else {}
    if not (commits.get("base") or commits.get("head")):
        return None
    return "%s → %s" % (commits.get("base") or "(unknown base)", commits.get("head") or "nothing committed")


def _report_risk_tier_value(body):
    """The `Risk tier` bullet's value, or None (PURE)."""
    if not body.get("risk_tier"):
        return None
    review_tier = body.get("review_tier")
    suffix = ""
    if review_tier and review_tier != body["risk_tier"]:
        suffix = " (review tier %s)" % review_tier
    return "%s%s" % (body["risk_tier"], suffix)


def _report_tests_value(body):
    """The `Tests` bullet's value, or None (PURE)."""
    tests = body.get("tests") if isinstance(body.get("tests"), dict) else {}
    if not (tests.get("command") or tests.get("result")):
        return None
    detail = "`%s` — %s" % (tests.get("command") or "(command not recorded)", tests.get("result") or "(result not recorded)")
    if tests.get("scope"):
        detail += " (scope: %s)" % tests["scope"]
    return detail


def _report_quality_value(body):
    """The `Quality gate` bullet's value, or None (PURE)."""
    quality = body.get("quality") if isinstance(body.get("quality"), dict) else {}
    if not quality.get("status"):
        return None
    suffix = " — %s" % _one_line(quality.get("detail")) if quality.get("detail") else ""
    return "%s%s" % (quality["status"], suffix)


def _report_council_value(body):
    """The `Iron Council` bullet's value, or None (PURE)."""
    critique = body.get("critique") if isinstance(body.get("critique"), dict) else {}
    if not critique.get("verdict"):
        return None
    return _council_summary(critique)


def _report_window_value(body):
    """The `Window` bullet's value, or None (PURE)."""
    if not (body.get("started_at") or body.get("finished_at")):
        return None
    return "%s → %s" % (body.get("started_at") or "(unknown)", body.get("finished_at") or "(unknown)")


_REVIEW_SUMMARY_FIELDS = (
    ("confirmed", "confirmed"), ("refuted", "refuted"),
    ("evidence_failed", "evidence-failed"), ("fix_rounds", "fix round"),
)


def _review_summary(review):
    """The `Review` bullet's value: counts of confirmed/refuted/etc (PURE)."""
    parts = []
    for key, label in _REVIEW_SUMMARY_FIELDS:
        value = review.get(key)
        if value is None:
            continue
        plural = "s" if key == "fix_rounds" and value != 1 else ""
        parts.append("%s %s%s" % (value, label, plural))
    return ", ".join(parts)


def _report_residual_lines(review):
    """The `## Residual findings` section, or nothing when there is none (PURE)."""
    residual = [r for r in (review.get("residual") or []) if r]
    if not residual:
        return []
    return ["", "## Residual findings", ""] + \
        ["- %s" % _one_line(item, 300) for item in residual]


def _report_split_lines(body):
    """The `## Proposed split` section, or nothing when there is none (PURE)."""
    split = body.get("split") if isinstance(body.get("split"), dict) else {}
    children = [c for c in (split.get("children") or []) if isinstance(c, dict)]
    if not children:
        return []
    lines = ["", "## Proposed split into %d children" % len(children), ""]
    for position, child in enumerate(children):
        lines.append(_report_split_child_line(position, child))
    return lines


def _report_split_child_line(position, child):
    """One numbered child line of the `## Proposed split` section (PURE)."""
    refs = [str(r) for r in (child.get("internal_deps") or [])]
    suffix = " (after child %s)" % ", ".join(refs) if refs else ""
    goal = _one_line(child.get("goal") or "(no goal)", 300)
    return "%d. %s%s" % (position + 1, goal, suffix)


def _report_escalation_lines(body):
    """The `## Escalations` section, or nothing when there are none (PURE)."""
    escalations = [e for e in (body.get("escalations") or []) if isinstance(e, dict)]
    if not escalations:
        return []
    lines = ["", "## Escalations", ""]
    for record in escalations:
        lines.append(_report_escalation_line(record))
    return lines


def _report_escalation_line(record):
    """One bullet of the `## Escalations` section (PURE)."""
    status = record.get("status") or "OPEN"
    escalation_id = record.get("id") or "?"
    title = _one_line(record.get("title") or "(untitled)")
    return "- **%s** `%s` — %s" % (status, escalation_id, title)


def _council_summary(critique):
    """The `Iron Council` value of a slice report, from a critique block (PURE).

    Shares `_scope_note` with the decisions log, so the two human surfaces can
    never disagree about whether a scope judgement was recorded.
    """
    line = "%s" % (critique["verdict"],)
    if critique.get("concerns"):
        line += " (%s concerns)" % (critique["concerns"],)
    note = _scope_note(critique.get("over_scope"))
    if note:
        line += " — %s" % (note,)
    return line


# --------------------------------------------------------------------------
# events
# --------------------------------------------------------------------------

def events_path(run_dir):
    return os.path.join(run_dir, EVENTS_FILE)


def read_events(run_dir):
    """Every parseable event, in file order. A half-written line is skipped."""
    events = []
    for line in _read_text(events_path(run_dir)).splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue  # tolerate a torn tail; never crash a reader
        if isinstance(event, dict):
            events.append(event)
    return events


def append_event(run_dir, ts, scope, event_type, payload):
    """Append one event and render it onto the human surface it belongs to."""
    event = {"ts": ts, "scope": scope, "type": event_type,
             "payload": payload if payload is not None else {}}
    _append_text(events_path(run_dir),
                 json.dumps(event, ensure_ascii=False, sort_keys=False) + "\n")

    if event_type == "escalation-opened":
        _append_text(os.path.join(run_dir, ESCALATIONS_MD),
                     render_escalation(scope, event["payload"]), ESCALATIONS_HEADER)
    elif event_type == "escalation-answered":
        path = os.path.join(run_dir, ESCALATIONS_MD)
        body = _read_text(path)
        updated, matched = answer_escalation(
            body, event["payload"].get("id"), event["payload"].get("answer"),
            event["payload"].get("answered_at") or ts)
        if matched:
            _atomic_write(path, updated)
        else:
            _append_text(path, _orphan_answer_entry(event), ESCALATIONS_HEADER)
    elif event_type in DECISION_EVENTS:
        _append_text(os.path.join(run_dir, DECISIONS_LOG),
                     decision_line(event) + "\n", DECISIONS_HEADER)
    return event


def open_escalations(run_dir):
    """Every escalation opened and not yet answered, in the order opened."""
    state = {}
    for event in read_events(run_dir):
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        escalation_id = payload.get("id")
        if not _nonempty_str(escalation_id):
            continue
        if event.get("type") == "escalation-opened":
            state[escalation_id] = {
                "record": payload,
                "answered": payload.get("status") == "ANSWERED",
            }
        elif event.get("type") == "escalation-answered" and escalation_id in state:
            state[escalation_id]["answered"] = True

    records = []
    for entry in state.values():
        if entry["answered"]:
            continue
        record = dict(entry["record"])
        record["status"] = "OPEN"
        records.append(record)
    return records


# --------------------------------------------------------------------------
# persist-slice
# --------------------------------------------------------------------------

def _returned_events(body, slice_id):
    """The workflow's own `events[]`, normalized to (scope, type, payload).

    Payloads are passed through byte-for-byte (the pinned contract), `scope`
    defaults to the slice, and any `ts` the entry carries is discarded — the
    controller owns the clock, and per-agent timing lives inside the payload
    (`dispatched_at`/`returned_at`), never in the collection stamp.
    """
    normalized = []
    for entry in body.get("events") or []:
        payload = entry.get("payload")
        normalized.append((entry.get("scope") or slice_id, entry.get("type"),
                           payload if isinstance(payload, dict) else {}))
    return normalized


def _derived_gate_events(body):
    """Gate/verdict/review events reconstructed from the sidecar's own blocks.

    The FALLBACK channel only: it carries just the summary numbers the sidecar
    happens to keep, which is all a lean result (the inline fallback worker)
    offers. Never appended alongside a returned `events[]` — the rich array
    already covers these, and emitting both would double-count every gate.
    """
    events = []
    critique = body.get("critique")
    if isinstance(critique, dict) and critique.get("verdict") \
            and critique["verdict"] != "SKIPPED":
        events.append(("council-verdict", critique))
    if body.get("review"):
        events.append(("review-summary", body["review"]))
    if body.get("quality"):
        events.append(("quality-gate", body["quality"]))
    return events


def _escalation_events(body, ts, already_opened):
    """escalation-opened/answered for the sidecar's embedded EscalationRecords.

    Always derived, whichever channel supplied the rest: a workflow reports
    escalations in `escalations[]`, not as events, so skipping these when a rich
    `events[]` is present would leave escalations.md and `open-escalations`
    empty — the human would never see the question. Records already carried as
    `escalation-opened` in the returned array are skipped here by id.
    """
    events = []
    for record in body.get("escalations") or []:
        if record.get("id") in already_opened:
            continue
        events.append(("escalation-opened", record))
        if record.get("status") == "ANSWERED" and record.get("answer"):
            events.append(("escalation-answered", {
                "id": record.get("id"),
                "answer": record.get("answer"),
                "answered_at": record.get("answered_at") or ts,
            }))
    return events


def _slice_events(body, ts, slice_id):
    """Every (scope, type, payload) one persisted SliceResult contributes.

    The workflow's returned `events[]` wins when present: it carries the rich
    payloads — `agent-dispatch` entries, the council `safety` flag, review
    `findings`/`reviewers` counts — that CANNOT be reconstructed from the
    sidecar's summary blocks, and run_metrics' dials read null without them.
    The sidecar-derived gate events are the fallback for a lean result, never an
    addition. Escalations are derived either way (see `_escalation_events`).

    The slice's own outcome (status, commits, tiers, counts, timings) is never
    emitted as an event on either path: the sidecar is its single home.
    """
    returned = _returned_events(body, slice_id)
    events = returned or [(slice_id, event_type, payload)
                          for event_type, payload in _derived_gate_events(body)]
    already_opened = {payload.get("id") for scope, event_type, payload in returned
                      if event_type == "escalation-opened"}
    events += [(slice_id, event_type, payload)
               for event_type, payload in _escalation_events(body, ts, already_opened)]
    return events


def persist_slice(run_dir, body, wave, ts):
    """Validate and persist one SliceResult: sidecar + events + prose.

    Raises SidecarInvalid (writing nothing) when the object violates the
    contract — the caller treats such a slice as ESCALATED.
    """
    errors = validate_sidecar(body)
    if errors:
        raise SidecarInvalid(errors)

    body = dict(body)
    if wave is not None:
        body["wave"] = wave  # the controller knows which wave collected this
    slice_id = body["id"]

    sidecar_path = os.path.join(run_dir, "slice-%s-status.json" % slice_id)
    _atomic_write(sidecar_path, json.dumps(body, ensure_ascii=False, indent=2) + "\n")

    emitted = []
    for scope, event_type, payload in _slice_events(body, ts, slice_id):
        append_event(run_dir, ts, scope, event_type, payload)
        emitted.append(event_type)

    report_path = os.path.join(run_dir, "slice-%s-report.md" % slice_id)
    _atomic_write(report_path, render_report(body))

    return {"ok": True, "id": slice_id, "status": body.get("status"),
            "wave": body.get("wave"), "sidecar": sidecar_path,
            "report": report_path, "events": emitted}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _require_ts(ts):
    if not ISO_TS.match(ts or ""):
        raise RunStateError("--ts %r is not an ISO-8601 timestamp "
                            "(e.g. 2026-07-30T12:00:00Z)" % (ts,))
    return ts


def _payload_arg(raw):
    if raw is None:
        return {}
    try:
        payload = json.loads(sys.stdin.read()) if raw == "-" else json.loads(raw)
    except ValueError as exc:
        raise RunStateError("--payload is not valid JSON: %s" % exc)
    if not isinstance(payload, dict):
        raise RunStateError("--payload must be a JSON object")
    return payload


def _require_run_dir(run_dir):
    """The run dir is created once, in Phase 1, with dag.json — every later
    invocation must land in that same directory. A --run-dir that does not
    exist or lacks dag.json means the caller's cwd drifted (e.g. a test
    command's `cd server && ...` persisting across Bash calls); writing there
    would scatter run-state fragments the dashboard can never find, so refuse
    loudly instead."""
    if not os.path.isfile(os.path.join(run_dir, "dag.json")):
        raise RunStateError(
            "--run-dir %r is not an existing run directory (no dag.json found). "
            "Refusing to create a fragment — check the current working directory "
            "or pass the run dir as an absolute path." % run_dir)


def _run(args):
    """Return (payload, exit_code) for parsed arguments."""
    _require_run_dir(args.run_dir)
    if args.command == "persist-slice":
        _require_ts(args.ts)
        body = read_json(args.json)
        return persist_slice(args.run_dir, body, args.wave, args.ts), 0

    if args.command == "append-event":
        _require_ts(args.ts)
        payload = _payload_arg(args.payload)
        return append_event(args.run_dir, args.ts, args.scope, args.type, payload), 0

    if args.command == "open-escalations":
        return open_escalations(args.run_dir), 0

    errors = validate_sidecar(read_json(args.file))
    return {"ok": not errors, "errors": errors}, (1 if errors else 0)


def build_parser():
    ap = argparse.ArgumentParser(
        description="Persist spec-loop run state: sidecars, events, prose.")
    subs = ap.add_subparsers(dest="command", required=True)

    def with_run_dir(parser):
        parser.add_argument("--run-dir", required=True,
                            help="docs/spec-loop/<run-id> directory")
        return parser

    persist = with_run_dir(subs.add_parser(
        "persist-slice", help="validate and persist a SliceResult sidecar"))
    persist.add_argument("--json", required=True,
                         help="SliceResult JSON file; - for stdin")
    persist.add_argument("--wave", type=int, required=True,
                         help="wave index that collected this slice")
    persist.add_argument("--ts", required=True, help="ISO-8601 UTC timestamp")

    event = with_run_dir(subs.add_parser("append-event", help="append one event"))
    event.add_argument("--ts", required=True, help="ISO-8601 UTC timestamp")
    event.add_argument("--scope", required=True,
                       help="slice id | intake | wave<N> | phase5 | run")
    event.add_argument("--type", required=True, help="event type")
    event.add_argument("--payload", help="event payload JSON; - for stdin")

    with_run_dir(subs.add_parser("open-escalations",
                                 help="list unanswered escalations as JSON"))

    check = with_run_dir(subs.add_parser(
        "validate-sidecar", help="validate a sidecar without persisting it"))
    check.add_argument("--file", required=True, help="sidecar JSON file; - for stdin")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        payload, code = _run(args)
    except SidecarInvalid as exc:
        print(json.dumps({"ok": False, "errors": exc.errors},
                         ensure_ascii=False, indent=2))
        return 1
    except RunStateError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
