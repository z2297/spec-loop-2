#!/usr/bin/env python3
"""Run-metrics harness for spec-loop v2 runs.

Derives safety, quality, performance, and token metrics from a run's durable
artifacts under ``docs/spec-loop/<run-id>/`` so the plugin's own development can
be steered by data: did a change regress the escalation rate, the review
verification quality, the quality-gate first-pass rate, the wall clock, the
tokens burned per slice?

  compute <run-dir>       print one versioned metrics JSON document for a run;
                          ``--write`` additionally persists it atomically as
                          ``<run-dir>/metrics.json`` (the ONLY mutating action).
  trend <repo-root>       recompute metrics across every run under
                          ``docs/spec-loop/`` and print a cross-run comparison
                          (``--md`` for a human table, JSON otherwise). Handles
                          v1 and v2 run dirs sitting side by side.

Design rules (mirror dashboard_server's layering):
* Pure core: every parser takes text/dicts, never paths; ``compute_metrics``
  assembles the document. The thin shell is the only layer that touches the
  filesystem.
* Fail-soft, null-honest: a metric that cannot be derived is ``null`` — never a
  fabricated 0. A section with no channel degrades to nulls with a ``basis`` of
  ``null``; it never crashes and never invents. "Zero escalations happened" and
  "we cannot see whether escalations happened" are different documents.
* Every section carries a ``basis`` provenance marker: ``"events-jsonl"``,
  ``"sidecar-v2"``, ``"events-jsonl+sidecar-v2"``, ``"runbook-table"``,
  ``"legacy-v1-prose"``, or ``null``.
* Stdlib only. Exit codes: 0 ok, 2 usage error.

CHANNELS (v2). ``events.jsonl`` is the primary channel and the per-slice
sidecars (``slice-<id>-status.json``) are authoritative for anything about a
slice; ``dag.json`` is the sole authority on run structure. See
``references/run-state-v2.md``. v1's prose channels are NOT read here: the
pinned line grammar of ``decisions-log.md``, ``slice-*-agents.jsonl``, and
Claude Code transcript scraping are all gone. ``runbook.md``'s requirement
traceability table is still parsed (a table, not a line grammar) and is marked
``basis: "runbook-table"`` so its softness is visible.

TIMESTAMPS — an event's ``ts`` is a BATCH COLLECTION STAMP. The controller
appends events when a wave is collected, not when the thing happened, so
deriving any duration from ``ts`` is forbidden by the contract. Every interval
here comes from an explicit pair of stamps carried in the data —
``agent-dispatch``'s ``dispatched_at``/``returned_at``, the EscalationRecord's
``opened``/``answered_at``, the sidecar's ``started_at``/``finished_at`` — and
is ``null`` when its pair is absent. ``ts`` is used for exactly one thing: the
coarse end bound of the run window, where it is not a duration but a real
moment the run had demonstrably already reached.

EVENT PAYLOAD KEYS. Keys marked (pinned) are fixed by run-state-v2.md; the rest
are what this harness reads by convention. Every one is optional — absent means
the dial it feeds is ``null``, never 0. If a producer names a field
differently, the dial goes null rather than wrong, and
``sources.events_skipped`` / ``sources.event_types`` make the drift visible.

  escalation-opened    the full EscalationRecord (pinned), of which this reads
                       id (pinned), trigger, title, status, opened, answered_at
  escalation-answered  id (pinned), answered_at
  decision             reversibility, rationale
  council-verdict      safety (pinned bool), verdict, member,
                       concerns | (concerns_folded + deferred[]) — concerns is
                       a complete count; the workflow instead reports the
                       disposition split, whose SUM is the same quantity (a
                       deferred concern was still raised). The sidecar's
                       critique.concerns is the fallback only when no verdict
                       event carried a count — never summed with them: one is
                       per-verdict, the other a per-slice rollup
  quality-gate         status | result, refactor_passes
  review-summary       findings, refuted_by_fixer, confirmed, refuted,
                       evidence_failed
  integration-check    status | result
  phase5-gate          status | result
  slice-merged         sha | merge_commit
  wave-collected       index, agent_count, subagent_tokens, duration_ms
                       (pinned, all optional)
  agent-dispatch       agent_type (pinned; bare `agent` read as a legacy
                       alias), model, effort, role, dispatched_at, returned_at,
                       tokens_in, tokens_out   (pinned, all optional)

TOKEN ATTRIBUTION, TODAY vs LATER. Workflow journal keys are opaque digests, so
the controller cannot match a journal entry to the dispatch that produced it:
in the current harness ``agent-dispatch`` carries no stamps and no tokens, and
every per-dispatch dial here is null on real runs. The live channel is the
workflow completion notification, which yields exact PER-WAVE aggregates
(``wave-collected``). Those are reported under ``tokens.wave_totals`` with
basis ``wave-collected-events``, and the per-model/per-role/per-agent
breakdowns stay null because a wave total genuinely is not attributable to a
role — splitting it would be invention. The per-dispatch paths are kept intact
and tested for the harness that can populate them later; when both channels are
present the section reports both side by side rather than reconciling them.

LEGACY. v1 run dirs (no ``schema_version`` in ``dag.json``, no
``events.jsonl``) are still summarizable by ``trend`` through the clearly-walled
``legacy_*`` prose parsers at the bottom of the pure core. They are reachable
ONLY from ``trend`` — never from ``compute``, never as a fallback for a v2
section — so prose can never masquerade as a v2 measurement.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2
MAX_FILE_BYTES = 4_000_000       # cap any single artifact read into memory

SLICE_STATUSES = ("DONE", "SPLIT", "ESCALATED", "FAILED")
COUNCIL_VERDICTS = ("ENDORSE", "ENDORSE_WITH_CONCERNS", "OBJECT", "SKIPPED")
ESCALATION_TRIGGERS = (
    "ambiguity",
    "material-assumption",
    "review-block",
    "council-objection",
    "quality-gate-block",
    "budget-exhausted",
)
REVERSIBILITY_BUCKETS = ("trivial", "moderate", "high", "n/a")
GATE_RESULTS = ("PASS", "FAIL", "SKIPPED")
# The sidecar's review block — the numerically-precise review channel.
REVIEW_COUNTER_KEYS = ("confirmed", "refuted", "evidence_failed", "fix_rounds")

BASIS_EVENTS = "events-jsonl"
BASIS_WAVE_EVENTS = "wave-collected-events"
BASIS_SIDECAR = "sidecar-v2"
BASIS_BOTH = "events-jsonl+sidecar-v2"
BASIS_RUNBOOK = "runbook-table"
BASIS_LEGACY = "legacy-v1-prose"

# A dispatch counts as a reviewer dispatch when its role or agent name says so.
# Heuristic by necessity: the contract does not enumerate role vocabulary.
# Diff-reviewer dispatches only: the wave workflow's pinned role vocabulary is
# review:<lane> for pr-reviewer passes (re-review:, verify-findings, critic:,
# and verify: are the fix-loop adjudicator, batched verifier, plan critique,
# and suite runner — none of them "find" findings, so counting them dilutes
# findings_per_reviewer_dispatch). agent_type is the second signal for
# dispatches that carry no role.
REVIEWER_HINT = re.compile(r"(?:^|\s)review(?::|$|\s)|pr-reviewer", re.IGNORECASE)
# The agents that actually PRODUCE review findings, and so form the denominator
# of findings-per-dispatch. Exact match on the pinned agent_type, because the
# role strings the workflow emits are free-form (`correctness`, `re-review:2`,
# `task:s1`) and no regex over them stays correct as lanes are renamed.
# finding-verifier and plan-critic are deliberately absent: they adjudicate and
# challenge, they do not report findings, so counting them would inflate the
# denominator and understate findings per reviewer.
REVIEWER_AGENT_TYPES = ("spec-loop:pr-reviewer", "spec-loop:re-reviewer")


# ==========================================================================
# generic pure helpers
# ==========================================================================

def _read_text_capped(path, cap=MAX_FILE_BYTES):
    """Read up to ``cap`` bytes of text, or return '' if absent/unreadable."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(cap)
    except (OSError, ValueError):
        return ""


def _read_text_flagged(path):
    """``(text, truncated)`` for a file read under the size cap.

    ``events.jsonl`` is append-only and unbounded, so unlike v1's prose logs it
    can genuinely outgrow the cap. A silent truncation would drop tail events
    and understate every count that derives from them — so the truncation is
    reported (``sources.events_truncated``) rather than swallowed."""
    text = _read_text_capped(path, MAX_FILE_BYTES + 1)
    if len(text) > MAX_FILE_BYTES:
        return text[:MAX_FILE_BYTES], True
    return text, False


def _load_json(path):
    """Parse a JSON file, or return None if absent/unreadable/malformed."""
    text = _read_text_capped(path)
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def parse_iso(value):
    """Parse an ISO-8601 string to an aware UTC datetime, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _iso_or_none(value):
    """The input string when it parses as ISO-8601, else None."""
    return value if parse_iso(value) else None


def _is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _ratio(part, whole):
    """part/whole rounded to 4 places, or None when whole is falsy/None."""
    if part is None or not whole:
        return None
    return round(part / whole, 4)


def _median(values):
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _max_overlap(intervals):
    """Max number of concurrently-open ``(start, end)`` intervals."""
    points = []
    for start, end in intervals:
        points.append((start, 1))
        points.append((end, -1))
    points.sort(key=lambda p: (p[0], p[1]))
    best = current = 0
    for _, delta in points:
        current += delta
        best = max(best, current)
    return best


def _interval_union_seconds(intervals):
    """Total seconds covered by the union of ``(start, end)`` datetime
    intervals (overlaps counted once), or None when nothing is timed."""
    spans = sorted((s, e) for s, e in intervals if s and e and e > s)
    if not spans:
        return None
    total = 0.0
    cur_start, cur_end = spans[0]
    for start, end in spans[1:]:
        if start > cur_end:
            total += (cur_end - cur_start).total_seconds()
            cur_start, cur_end = start, end
        elif end > cur_end:
            cur_end = end
    total += (cur_end - cur_start).total_seconds()
    return round(total, 1)


def _tally(keys):
    """Count occurrences of each non-None key, preserving no order guarantee
    beyond sorted output. Returns {} when nothing counted."""
    counts = {}
    for key in keys:
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _basis(from_events, from_sidecars):
    """The provenance marker for a section fed by either/both v2 channels."""
    if from_events and from_sidecars:
        return BASIS_BOTH
    if from_events:
        return BASIS_EVENTS
    if from_sidecars:
        return BASIS_SIDECAR
    return None


# ==========================================================================
# pure core — events.jsonl (primary channel)
# ==========================================================================

def parse_events(text):
    """Parse events.jsonl into ``{events, skipped, types}``.

    One JSON object per line: ``{ts, scope, type, payload}``. Lenient by
    design — the file is append-only and may be read mid-write: blank lines are
    ignored, unparseable or shapeless lines are counted in ``skipped`` (never
    crash, never guess), unknown ``type`` values are kept so a consumer that
    predates a new event type still reports it in ``types``."""
    rows, skipped = [], 0
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if not isinstance(obj, dict) or not isinstance(obj.get("type"), str) \
                or not obj["type"].strip():
            skipped += 1
            continue
        payload = obj.get("payload")
        rows.append({
            "ts": _iso_or_none(obj.get("ts")),
            "scope": obj["scope"] if isinstance(obj.get("scope"), str) else None,
            "type": obj["type"].strip(),
            "payload": payload if isinstance(payload, dict) else {},
        })
    return {"events": rows, "skipped": skipped,
            "types": _tally(row["type"] for row in rows)}


def _of_type(events, *types):
    return [e for e in events if e["type"] in types]


def _pstr(event, key):
    """A non-empty string payload field, else None."""
    value = event["payload"].get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _pcount(event, key):
    """A non-negative integer payload field, else None."""
    value = event["payload"].get(key)
    return value if _is_count(value) else None


def _dispatch_key(event, field):
    """The grouping key for one dispatch dimension.

    ``agent`` resolves the pinned payload key ``agent_type``, accepting bare
    ``agent`` as a legacy alias — either spelling yields the real agent name,
    so this can never silently produce "(unknown)" for a well-formed event."""
    if field == "agent":
        return _pstr(event, "agent_type") or _pstr(event, "agent")
    return _pstr(event, field)


def _plist_len(event, key):
    """The length of a list-valued payload field, else None (absent stays
    absent — an unreported list is not an empty one)."""
    value = event["payload"].get(key)
    return len(value) if isinstance(value, list) else None


def _pstamp(event, key):
    """An ISO-8601 payload timestamp, else None.

    All timing in this module flows through here rather than through the
    event's ``ts``, which is a batch collection stamp (see module docstring)."""
    return _iso_or_none(event["payload"].get(key))


def _presult(event):
    """The PASS/FAIL/SKIPPED verdict of a gate-ish event, or None.

    Producers write it as ``status`` (the sidecar's spelling) or ``result``;
    anything outside the vocabulary is None rather than coerced."""
    for key in ("status", "result"):
        value = _pstr(event, key)
        if value and value.upper() in GATE_RESULTS:
            return value.upper()
    return None


def _pfindings(event):
    """``findings`` as a count, accepting either an int or a list of findings."""
    value = event["payload"].get("findings")
    if _is_count(value):
        return value
    if isinstance(value, list):
        return len(value)
    return None


def _sum_optional(values):
    """Sum the non-None values, or None when every value is None — the
    null-honest fold used for every "…when present" event counter."""
    present = [v for v in values if v is not None]
    return sum(present) if present else None


# --- escalations ----------------------------------------------------------

def escalations_from_events(events):
    """``{records, unkeyed}`` — escalation records paired from the event channel.

    ``escalation-opened`` carries the full EscalationRecord, so the record's own
    ``opened``/``answered_at`` fields are the clock. The event ``ts`` is a batch
    collection stamp and is never read here.

    Paired on ``payload.id`` alone — never on ``scope``, which would merge two
    escalations raised by the same slice into one (the pinned id format
    ``<slice-id>:<trigger>[:<round>]`` exists precisely because that happens).
    The contract pins the id, so an event without one is contract-violating
    data: it still becomes a record (a producer bug must not erase an
    escalation that really happened) but under a key that can never pair, and
    it is counted in ``unkeyed`` so the drift is loud rather than silently
    merging or inflating escalations."""
    order, records, unkeyed = [], {}, 0
    for index, event in enumerate(_of_type(events, "escalation-opened",
                                           "escalation-answered")):
        ident = _pstr(event, "id")
        if ident is None:
            unkeyed += 1
            ident = "(unkeyed:%d)" % index
        if ident not in records:
            order.append(ident)
            records[ident] = {
                "id": ident, "scope": event["scope"], "trigger": None,
                "title": None, "status": "OPEN",
                "opened": None, "answered_at": None,
            }
        _fold_escalation_event(records[ident], event)
    return {"records": [records[key] for key in order], "unkeyed": unkeyed}


def _fold_escalation_event(record, event):
    """Fold one escalation event into its record, first non-null winning."""
    for field, value in (("trigger", _normalize_trigger(_pstr(event, "trigger"))),
                         ("title", _pstr(event, "title")),
                         ("opened", _pstamp(event, "opened")),
                         ("answered_at", _pstamp(event, "answered_at"))):
        record[field] = record[field] or value
    if event["type"] == "escalation-answered" or record["answered_at"] \
            or (_pstr(event, "status") or "").upper() == "ANSWERED":
        record["status"] = "ANSWERED"


def _normalize_trigger(value):
    """A canonical trigger, ``"other"`` for an unrecognized non-empty one,
    or None when absent."""
    if not value:
        return None
    lowered = value.strip().lower()
    return lowered if lowered in ESCALATION_TRIGGERS else "other"


def merge_escalation_records(from_events, from_sidecars):
    """Union the two escalation channels by id, events winning on conflict.

    Sidecars are authoritative about a slice, but a run that escalated at
    intake has no sidecar at all, and an interrupted run may have events with
    no persisted sidecar yet — so neither channel alone is complete."""
    merged, order = {}, []
    for record in list(from_sidecars) + list(from_events):
        key = record["id"]
        if key not in merged:
            order.append(key)
            merged[key] = dict(record)
            continue
        existing = merged[key]
        answered = "ANSWERED" in (existing["status"], record["status"])
        existing.update({k: v for k, v in record.items() if v is not None})
        # An answer recorded in either channel happened; a channel that only
        # saw the open must not walk the escalation back to OPEN.
        if answered:
            existing["status"] = "ANSWERED"
    return [merged[key] for key in order]


# ==========================================================================
# pure core — dag.json / sidecars / runbook.md
# ==========================================================================

def parse_dag(obj):
    """Normalize dag.json, or return None when it is not a usable DAG.

    Tolerant of a half-written file: a missing ``slices`` list makes the whole
    DAG unusable (report the run momentarily unreadable), but individual
    malformed slice entries are skipped."""
    if not isinstance(obj, dict) or not isinstance(obj.get("slices"), list):
        return None
    slices = [s for s in obj["slices"] if isinstance(s, dict)]
    depths = [s["depth"] for s in slices if _is_count(s.get("depth"))]
    return {
        "schema_version": obj.get("schema_version")
            if _is_count(obj.get("schema_version")) else None,
        "base_ref": obj.get("base_ref"),
        "merge_mode": obj.get("merge_mode"),
        "mode": obj.get("mode"),
        "created_at": _iso_or_none(obj.get("created_at")),
        "slice_ids": [s.get("id") for s in slices if isinstance(s.get("id"), str)],
        "slice_count": len(slices),
        "split_parents": sum(1 for s in slices if s.get("status") == "split"),
        "max_depth": max(depths) if depths else None,
        "remediation_count": sum(1 for s in slices if s.get("remediation") is True),
        "status_counts": _tally(s.get("status") or "unknown" for s in slices),
        "risk_tiers": _tally(s.get("risk_tier") for s in slices
                             if _is_count(s.get("risk_tier"))),
        "waves": _parse_waves(obj.get("waves")),
    }


def _parse_waves(waves):
    """Normalize the ``waves[]`` array — the durable record of what was
    actually dispatched. Returns None when absent (an inline-mode or
    not-yet-dispatched run), [] never being confused with "no waves ran"."""
    if not isinstance(waves, list):
        return None
    out = []
    for wave in waves:
        if not isinstance(wave, dict):
            continue
        slice_ids = [s for s in wave.get("slice_ids") or [] if isinstance(s, str)]
        out.append({
            "index": wave["index"] if _is_count(wave.get("index")) else None,
            "slice_ids": slice_ids,
            "slices": len(slice_ids),
            "status": wave.get("status") if isinstance(wave.get("status"), str)
                      else None,
            "workflow_run_id": wave.get("workflow_run_id")
                if isinstance(wave.get("workflow_run_id"), str) else None,
        })
    return out or None


def parse_sidecar(obj):
    """Normalize a ``slice-<id>-status.json`` v2 sidecar, or None when unusable.

    Every block below the identity fields is optional: a sidecar persisted for
    an ESCALATED slice has no ``review``, an inline run has no ``wave``. Absent
    stays absent."""
    if not isinstance(obj, dict):
        return None
    status = obj.get("status")
    wave = obj.get("wave")
    return {
        "id": obj.get("id") if isinstance(obj.get("id"), str) else None,
        "status": status if status in SLICE_STATUSES else None,
        "risk_tier": obj.get("risk_tier") if _is_count(obj.get("risk_tier")) else None,
        "review_tier": obj.get("review_tier") if _is_count(obj.get("review_tier")) else None,
        "critique": _parse_critique(obj.get("critique")),
        "review": _parse_review_block(obj.get("review")),
        "quality_status": _parse_gate_status(obj.get("quality")),
        "tests_result": _nested_str(obj.get("tests"), "result"),
        "tasks_completed": obj.get("tasks_completed")
            if _is_count(obj.get("tasks_completed")) else None,
        "agents_used": obj.get("agents_used")
            if _is_count(obj.get("agents_used")) else None,
        "wave": wave if _is_count(wave) else None,
        "started_at": _iso_or_none(obj.get("started_at")),
        "finished_at": _iso_or_none(obj.get("finished_at")),
        "escalations": _parse_embedded_escalations(obj.get("escalations")),
    }


def _nested_str(block, key):
    if not isinstance(block, dict):
        return None
    value = block.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _parse_critique(block):
    """The council critique summary a slice carries, or None."""
    if not isinstance(block, dict):
        return None
    verdict = block.get("verdict")
    concerns = block.get("concerns")
    if verdict not in COUNCIL_VERDICTS and not _is_count(concerns):
        return None
    return {
        "verdict": verdict if verdict in COUNCIL_VERDICTS else None,
        "concerns": concerns if _is_count(concerns) else None,
    }


def _parse_review_block(block):
    """The sidecar review counters — the precise review channel.

    Returns ``{confirmed, refuted, evidence_failed, fix_rounds, residual}``
    with each counter present only when it is a real non-negative int, or None
    when the block carries nothing usable."""
    if not isinstance(block, dict):
        return None
    counters = {k: block[k] for k in REVIEW_COUNTER_KEYS if _is_count(block.get(k))}
    residual = block.get("residual")
    if isinstance(residual, list):
        counters["residual"] = len(residual)
    return counters or None


def _parse_gate_status(block):
    """The quality block's PASS/FAIL/SKIPPED status, or None."""
    value = _nested_str(block, "status")
    return value.upper() if value and value.upper() in GATE_RESULTS else None


def _parse_embedded_escalations(records):
    """Normalize the EscalationRecords a sidecar embeds into the same shape
    ``escalations_from_events`` produces, so the two channels can be unioned."""
    if not isinstance(records, list):
        return []
    out = []
    for record in records:
        if not isinstance(record, dict):
            continue
        ident = record.get("id")
        if not isinstance(ident, str) or not ident.strip():
            continue
        status = record.get("status")
        answered_at = _iso_or_none(record.get("answered_at"))
        out.append({
            "id": ident.strip(),
            "scope": ident.split(":")[0] or None,
            "trigger": _normalize_trigger(record.get("trigger")
                                          if isinstance(record.get("trigger"), str)
                                          else None),
            "title": record.get("title") if isinstance(record.get("title"), str)
                     else None,
            "status": status if status in ("OPEN", "ANSWERED")
                      else ("ANSWERED" if answered_at else "OPEN"),
            "opened": _iso_or_none(record.get("opened")),
            "answered_at": answered_at,
        })
    return out


def parse_runbook_traceability(text):
    """Count delivered/partial/deferred rows in the runbook's Requirement
    Traceability table, or None when the section/table is absent. Prose-derived
    and marked as such (``basis: "runbook-table"``)."""
    in_section = False
    counts = {"delivered": 0, "partial": 0, "deferred": 0}
    seen_row = False
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            in_section = "requirement traceability" in stripped.lower()
            continue
        if not in_section or not stripped.startswith("|"):
            continue
        status = _traceability_row_status(stripped)
        if status:
            counts[status] += 1
            seen_row = True
    return counts if seen_row else None


def _traceability_row_status(row):
    """The status keyword of one table row, or None for header/divider rows."""
    cells = [c.strip().lower() for c in row.strip("|").split("|")]
    if len(cells) < 2:
        return None
    for status in ("delivered", "partial", "deferred"):
        if status in cells[1]:
            return status
    return None


# ==========================================================================
# pure core — run schema detection
# ==========================================================================

def detect_run_schema(dag_obj, has_events):
    """The run-state generation of a run dir: 2 for v2, 1 for v1.

    ``dag.json``'s ``schema_version`` is the declaration; v1 dags have no such
    key. A dir with an ``events.jsonl`` but an unreadable/absent dag (an
    interrupted v2 run) is still v2 — only the absence of both signals reads
    as v1."""
    declared = (dag_obj or {}).get("schema_version") \
        if isinstance(dag_obj, dict) else None
    if _is_count(declared) and declared >= 2:
        return 2
    if has_events:
        return 2
    return 1


# ==========================================================================
# pure core — metric computation (v2)
# ==========================================================================

def compute_metrics(artifacts):
    """Assemble the versioned metrics document from loaded v2 artifacts.

    ``artifacts``: {run_id, dag, events_text, runbook_text, sidecars} (see
    ``load_run_artifacts``). Pure — no clock, no filesystem; the shell stamps
    ``generated_at``. Never reads v1 prose: a v1 run dir analyzed here yields
    an honestly-null document, and ``trend`` is what routes it to the legacy
    parsers instead."""
    parsed_events = parse_events(artifacts.get("events_text") or "")
    events = parsed_events["events"]
    sidecars = [s for s in (parse_sidecar(x) for x in artifacts.get("sidecars") or [])
                if s]
    event_escalations = escalations_from_events(events)
    sidecar_escalations = [rec for sc in sidecars for rec in sc["escalations"]]
    parsed = {
        "events": events,
        "event_types": parsed_events["types"],
        "events_skipped": parsed_events["skipped"],
        "events_truncated": bool(artifacts.get("events_truncated")),
        "has_events": bool(events),
        "dag": parse_dag(artifacts.get("dag")),
        "sidecars": sidecars,
        "runbook": parse_runbook_traceability(artifacts.get("runbook_text") or ""),
        "escalations": merge_escalation_records(event_escalations["records"],
                                               sidecar_escalations),
        "escalation_unkeyed": event_escalations["unkeyed"],
        "escalation_basis": _basis(bool(event_escalations["records"]),
                                   bool(sidecar_escalations)),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": artifacts.get("run_id"),
        "run_schema_detected": detect_run_schema(artifacts.get("dag"),
                                                 parsed["has_events"]),
        "generated_at": None,
        "sources": _sources(parsed),
        "safety": _safety_metrics(parsed),
        "quality": _quality_metrics(parsed),
        "performance": _performance_metrics(parsed),
        "tokens": _token_metrics(parsed),
    }


def _sources(parsed):
    dag = parsed["dag"]
    return {
        "dag": dag is not None,
        "dag_schema_version": (dag or {}).get("schema_version"),
        "events": len(parsed["events"]),
        "events_skipped": parsed["events_skipped"],
        "events_truncated": parsed["events_truncated"],
        "event_types": parsed["event_types"],
        "sidecars": len(parsed["sidecars"]),
        "runbook": parsed["runbook"] is not None,
    }


# --- safety ---------------------------------------------------------------

def _safety_metrics(parsed):
    """Escalation pressure, autonomy, and council verdicts — how often the
    loop had to interrupt the human, and how often it was told to stop."""
    observed = parsed["has_events"] or bool(parsed["sidecars"])
    escalations = parsed["escalations"]
    decisions = _of_type(parsed["events"], "decision")
    deferrals = _of_type(parsed["events"], "deferred")
    decisions_total = len(decisions) if parsed["has_events"] else None
    return {
        "basis": _basis(parsed["has_events"], bool(parsed["sidecars"])),
        "escalations": _escalation_stats(escalations, observed,
                                        parsed["escalation_basis"],
                                        parsed["escalation_unkeyed"]),
        "decisions_total": decisions_total,
        "deferrals_total": len(deferrals) if parsed["has_events"] else None,
        "autonomy_ratio": _autonomy_ratio(decisions_total, escalations, observed),
        "escalation_answer_latency_s": _answer_latency(escalations),
        "council": _council_stats(parsed),
        "reversibility_mix": _reversibility_mix(decisions),
        "precedent_reuse": _precedent_stats(decisions),
    }


def _escalation_stats(escalations, observed, basis, unkeyed):
    """``unkeyed_events`` is the count of escalation events that arrived
    without the pinned ``payload.id``; non-zero means ``total`` may be
    inflated by events that could not be paired."""
    if not observed:
        return {"basis": None, "total": None, "open": None, "answered": None,
                "by_trigger": None, "per_scope": None, "unkeyed_events": None}
    return {
        "basis": basis,
        "total": len(escalations),
        "open": sum(1 for e in escalations if e["status"] == "OPEN"),
        "answered": sum(1 for e in escalations if e["status"] == "ANSWERED"),
        "by_trigger": _tally(e["trigger"] for e in escalations),
        "per_scope": _tally(e["scope"] for e in escalations),
        "unkeyed_events": unkeyed,
    }


def _autonomy_ratio(decisions_total, escalations, observed):
    """Share of judgement calls the loop resolved itself rather than handing
    to the human. None when neither channel was observed — a run with no
    events file has not demonstrated 100% autonomy."""
    if not observed or decisions_total is None:
        return None
    return _ratio(decisions_total, decisions_total + len(escalations))


def _council_stats(parsed):
    """Verdict mix from council-verdict events, with the sidecar critique
    verdicts as a parallel per-slice view.

    ``safety_objections`` stays null unless at least one verdict payload
    carries a ``safety`` flag: "no payload said safety" is not evidence that no
    SAFETY objection was raised. ``over_scope_flags`` and
    ``over_scope_deferrals`` are a record of what the council observed and
    feed no threshold, gate or blocking decision."""
    verdict_events = _of_type(parsed["events"], "council-verdict")
    critiques = [sc["critique"] for sc in parsed["sidecars"] if sc["critique"]]
    sidecar_verdicts = [c["verdict"] for c in critiques if c["verdict"]]
    if not verdict_events and not critiques:
        return {"basis": None, "verdicts": None, "object_rate": None,
                "safety_objections": None, "concerns_total": None,
                "concerns_deferred": None, "by_member": None,
                "slice_verdicts": None, "over_scope_flags": None,
                "over_scope_deferrals": None}
    verdicts = [_pstr(e, "verdict") for e in verdict_events]
    verdicts = [v.upper() for v in verdicts if v and v.upper() in COUNCIL_VERDICTS]
    safety_flagged = [e for e in verdict_events
                      if isinstance(e["payload"].get("safety"), bool)]
    return {
        "basis": _basis(bool(verdict_events), bool(critiques)),
        "verdicts": _tally(verdicts) if verdict_events else None,
        "object_rate": _ratio(verdicts.count("OBJECT"), len(verdicts)),
        "safety_objections": sum(1 for e in safety_flagged
                                 if e["payload"]["safety"]) if safety_flagged
                             else None,
        "concerns_total": _concerns_total(verdict_events, critiques),
        "concerns_deferred": _sum_optional(_plist_len(e, "deferred")
                                           for e in verdict_events),
        "by_member": _tally(_pstr(e, "member") for e in verdict_events) or None,
        "slice_verdicts": _tally(sidecar_verdicts) or None,
        "over_scope_flags": _flag_count(verdict_events, "over_scope"),
        "over_scope_deferrals": _marked_count(
            _of_type(parsed["events"], "deferred"), "over_scope"),
    }


def _flag_count(events, key):
    """How many payloads carried `{key: {flag: true}}`, or None (PURE).

    Null-honest in the same way as ``safety_objections``: "no payload recorded
    a scope judgement" is not evidence that nothing was over scope, and a
    malformed record counts as no record rather than as a clean one."""
    observed = [e for e in events if _has_bool_flag(e, key)]
    if not observed:
        return None
    return sum(1 for e in observed if e["payload"][key]["flag"])


def _has_bool_flag(event, key):
    """True if `event`'s payload carries `{key: {flag: <bool>}}` (PURE)."""
    block = event["payload"].get(key)
    return isinstance(block, dict) and isinstance(block.get("flag"), bool)


def _marked_count(events, key):
    """How many payloads set the boolean marker `key` true, or None (PURE)."""
    observed = [e for e in events if isinstance(e["payload"].get(key), bool)]
    if not observed:
        return None
    return sum(1 for e in observed if e["payload"][key])


def _concerns_total(verdict_events, critiques):
    """Concerns raised across the council.

    Events win over sidecars: there is one ``council-verdict`` event per
    verdict, so summing them counts every member's concerns, whereas the
    sidecar's ``critique.concerns`` is one already-rolled-up number per slice —
    mixing the two would double-count. The sidecar is the fallback for a run
    where no verdict event carried a count at all.

    Within an event, ``concerns`` and ``concerns_folded`` name the same
    quantity (the contract's sidecar spelling and the workflow's spelling
    respectively), so either is accepted."""
    from_events = _sum_optional(_verdict_concerns(e) for e in verdict_events)
    if from_events is not None:
        return from_events
    return _sum_optional(c["concerns"] for c in critiques)


def _verdict_concerns(event):
    """One verdict's total concerns RAISED.

    ``concerns`` is a complete count on its own (the sidecar critique's
    spelling) and wins outright when present. The workflow instead reports the
    disposition split — ``concerns_folded`` plus a ``deferred`` list — and the
    total is their SUM: a deferred concern was still raised, it was just not
    acted on now. Reading ``concerns_folded`` alone would quietly under-report
    every council that deferred anything, which is precisely the run where the
    concern count matters most."""
    total = _pcount(event, "concerns")
    if total is not None:
        return total
    folded = _pcount(event, "concerns_folded")
    deferred = _plist_len(event, "deferred")
    if folded is None and deferred is None:
        return None
    return (folded or 0) + (deferred or 0)


def _reversibility_mix(decisions):
    """Reversibility buckets from decision payloads, or None when no decision
    declared one (v1 read this out of prose; v2 wants it structured)."""
    values = []
    for event in decisions:
        value = _pstr(event, "reversibility")
        if value:
            lowered = value.lower()
            values.append(lowered if lowered in REVERSIBILITY_BUCKETS else "other")
    return _tally(values) or None


def _precedent_stats(decisions):
    """How often a decision cited precedent instead of fresh reasoning."""
    if not decisions:
        return {"count": None, "rate": None}
    rationales = [(_pstr(e, "rationale") or "").lower() for e in decisions]
    if not any(rationales):
        return {"count": None, "rate": None}
    count = sum(1 for text in rationales if "precedent" in text)
    return {"count": count, "rate": _ratio(count, len(decisions))}


def _answer_latency(escalations):
    """How long the human took to answer — the dial that says whether the
    escalation budget is actually cheap."""
    latencies = []
    for esc in escalations:
        opened, answered = parse_iso(esc["opened"]), parse_iso(esc["answered_at"])
        if opened and answered and answered >= opened:
            latencies.append((answered - opened).total_seconds())
    if not latencies:
        return None
    return {
        "count": len(latencies),
        "median_s": round(_median(latencies), 1),
        "max_s": round(max(latencies), 1),
    }


# --- quality --------------------------------------------------------------

def _quality_metrics(parsed):
    return {
        "basis": _basis(parsed["has_events"], bool(parsed["sidecars"])),
        "quality_gate": _quality_gate_stats(parsed),
        "review": _review_stats(parsed),
        "merges": _merge_stats(parsed["events"], parsed["has_events"]),
        "splits": _split_stats(parsed["dag"]),
        "integration": _integration_stats(parsed),
        "requirement_coverage": _coverage_stats(parsed["runbook"]),
        "slice_outcomes": _slice_outcomes(parsed),
        "tests": _test_stats(parsed["sidecars"]),
    }


def _quality_gate_stats(parsed):
    """First-pass rate over quality-gate events, plus the sidecars' final
    per-slice statuses.

    First-pass is per scope, not per event: a slice whose FIRST gate event is
    PASS passed first time, however many measurements followed."""
    events = _of_type(parsed["events"], "quality-gate")
    finals = _tally(sc["quality_status"] for sc in parsed["sidecars"]
                    if sc["quality_status"])
    if not events and not finals:
        return {"basis": None, "measurements": None, "scopes": None,
                "first_pass": None, "first_pass_rate": None,
                "refactor_passes_total": None, "failures": None,
                "final_status_counts": None}
    first_by_scope = {}
    for event in events:
        scope = event["scope"] or "(unscoped)"
        if scope not in first_by_scope:
            first_by_scope[scope] = _presult(event)
    decided = {s: r for s, r in first_by_scope.items() if r is not None}
    first_pass = sum(1 for result in decided.values() if result == "PASS")
    return {
        "basis": _basis(bool(events), bool(finals)),
        "measurements": len(events),
        "scopes": len(first_by_scope) or None,
        "first_pass": first_pass if decided else None,
        "first_pass_rate": _ratio(first_pass, len(decided)),
        "refactor_passes_total": _sum_optional(_pcount(e, "refactor_passes")
                                               for e in events),
        "failures": sum(1 for e in events if _presult(e) == "FAIL") if events
                    else None,
        "final_status_counts": finals or None,
    }


def _review_stats(parsed):
    """Review verification quality: how much of what reviewers reported
    survived adversarial verification, and how much fixer effort it cost.

    The sidecar ``review`` block is the precise channel; ``review-summary``
    event payloads add the per-dispatch findings volume and the
    fixer-refutation dial the sidecar does not carry."""
    sidecars = [sc["review"] for sc in parsed["sidecars"] if sc["review"]]
    summaries = _of_type(parsed["events"], "review-summary")
    if not sidecars and not summaries:
        return {"basis": None, "counters": None, "verified_findings": None,
                "refuted_rate": None, "evidence_failed_drop_rate": None,
                "fix_rounds_total": None, "residual_total": None,
                "findings_total": None, "reviewer_dispatches": None,
                "findings_per_reviewer_dispatch": None,
                "refuted_by_fixer": None, "refuted_by_fixer_rate": None,
                "block_escalations": None}
    counters = _sum_review_counters(sidecars, summaries)
    confirmed = counters.get("confirmed")
    refuted = counters.get("refuted")
    evidence_failed = counters.get("evidence_failed")
    verified = _sum_optional([confirmed, refuted])
    adjudicated = _sum_optional([confirmed, refuted, evidence_failed])
    findings_total = _sum_optional(_pfindings(e) for e in summaries)
    reviewer_dispatches = _reviewer_dispatch_count(parsed["events"])
    refuted_by_fixer = _sum_optional(_pcount(e, "refuted_by_fixer")
                                     for e in summaries)
    return {
        "basis": _basis(bool(summaries), bool(sidecars)),
        "counters": counters or None,
        "verified_findings": verified,
        "refuted_rate": _ratio(refuted, verified),
        "evidence_failed_drop_rate": _ratio(evidence_failed, adjudicated),
        "fix_rounds_total": counters.get("fix_rounds"),
        "residual_total": counters.get("residual"),
        "findings_total": findings_total,
        "reviewer_dispatches": reviewer_dispatches,
        "findings_per_reviewer_dispatch": _rate_1dp(findings_total,
                                                    reviewer_dispatches),
        "refuted_by_fixer": refuted_by_fixer,
        "refuted_by_fixer_rate": _ratio(refuted_by_fixer, findings_total),
        "block_escalations": sum(1 for e in parsed["escalations"]
                                 if e["trigger"] == "review-block"),
    }


def _sum_review_counters(sidecar_reviews, summaries):
    """Sum the review counters, preferring the sidecars (authoritative per
    slice) and falling back to review-summary payloads per key."""
    keys = REVIEW_COUNTER_KEYS + ("residual",)
    totals = {}
    for key in keys:
        value = _sum_optional(block.get(key) for block in sidecar_reviews)
        if value is None and key in REVIEW_COUNTER_KEYS:
            value = _sum_optional(_pcount(e, key) for e in summaries)
        if value is not None:
            totals[key] = value
    return totals


def _reviewer_dispatch_count(events):
    """Finding-producing dispatches, or None when nothing was dispatched.

    Primary test is exact ``agent_type`` membership of REVIEWER_AGENT_TYPES.
    REVIEWER_HINT over the role is kept only as a fallback for dispatches that
    name no agent type at all (the inline slice-worker-fallback path), where a
    name hint is the only signal there is."""
    dispatches = _of_type(events, "agent-dispatch")
    if not dispatches:
        return None
    return sum(1 for e in dispatches if _is_reviewer_dispatch(e))


def _is_reviewer_dispatch(event):
    """True when a dispatch belongs to a finding-producing reviewer.

    Union of two signals, deliberately never an either/or: a lane variant
    (``pr-reviewer-integration``) is caught by the family prefix, and
    ``re-reviewer`` — whose role reads ``re-review:2``, where REVIEWER_HINT's
    word-boundary rule does not fire — is caught only by that prefix. The role
    hint then catches a future reviewer this list has not learned yet."""
    agent = (_dispatch_key(event, "agent") or "").lower()
    if any(agent.startswith(family) for family in REVIEWER_AGENT_TYPES):
        return True
    return bool(REVIEWER_HINT.search("%s %s" % (_pstr(event, "role") or "",
                                                agent)))


def _rate_1dp(part, whole):
    return round(part / whole, 1) if part is not None and whole else None


def _merge_stats(events, has_events):
    """Slice merges recorded on the integration branch."""
    merged = _of_type(events, "slice-merged")
    if not has_events:
        return {"basis": None, "count": None, "commits": None}
    shas = sorted({sha for e in merged
                   for sha in (_pstr(e, "sha"), _pstr(e, "merge_commit")) if sha})
    return {"basis": BASIS_EVENTS, "count": len(merged), "commits": shas or None}


def _split_stats(dag):
    """Decomposition quality: how often intake mis-sized a slice."""
    if dag is None:
        return None
    return {
        "basis": "dag-json",
        "total_slices": dag["slice_count"],
        "split_parents": dag["split_parents"],
        "split_rate": _ratio(dag["split_parents"], dag["slice_count"]),
        "max_depth": dag["max_depth"],
        "remediation_slices": dag["remediation_count"],
        "risk_tiers": dag["risk_tiers"] or None,
    }


def _integration_stats(parsed):
    """Per-wave integration checks plus the terminal Phase-5 gate."""
    checks = _of_type(parsed["events"], "integration-check")
    gates = _of_type(parsed["events"], "phase5-gate")
    dag = parsed["dag"]
    if not parsed["has_events"]:
        return {"basis": None, "checks": None, "check_failures": None,
                "gate": None, "remediation_slices":
                    dag["remediation_count"] if dag else None}
    results = [_presult(e) for e in checks]
    return {
        "basis": BASIS_EVENTS,
        "checks": [{"scope": e["scope"], "result": _presult(e)} for e in checks],
        "check_failures": sum(1 for r in results if r == "FAIL"),
        "gate": _presult(gates[-1]) if gates else None,
        "remediation_slices": dag["remediation_count"] if dag else None,
    }


def _coverage_stats(runbook):
    """Requirement traceability from the runbook table — prose-derived, so it
    carries its own softer basis rather than borrowing the section's."""
    if runbook is None:
        return None
    total = sum(runbook.values())
    return {"basis": BASIS_RUNBOOK, **runbook,
            "rate": _ratio(runbook["delivered"], total)}


def _slice_outcomes(parsed):
    """Terminal slice statuses — sidecars when present, else the DAG's view."""
    statuses = [sc["status"] for sc in parsed["sidecars"] if sc["status"]]
    if statuses:
        return {"basis": BASIS_SIDECAR, "counts": _tally(statuses)}
    if parsed["dag"] is not None:
        return {"basis": "dag-json", "counts": parsed["dag"]["status_counts"]}
    return {"basis": None, "counts": None}


def _test_stats(sidecars):
    """Whether each slice's own verification actually ran."""
    results = _tally(sc["tests_result"] for sc in sidecars if sc["tests_result"])
    if not results:
        return None
    return {"basis": BASIS_SIDECAR, "results": results}


# --- performance ----------------------------------------------------------

def _performance_metrics(parsed):
    """Wall clock, per-slice and per-wave shape, agent dispatch profile, and
    the engine-active / human-wait split that says where the time actually
    went."""
    window = _run_window(parsed)
    dispatch_intervals = list(_dispatch_intervals(parsed["events"]))
    return {
        "basis": window["basis"],
        "run_wall_clock_s": window["wall_clock_s"],
        "started_at": window["started_at"],
        "finished_at": window["finished_at"],
        "slices": _slice_durations(parsed["sidecars"]),
        "waves": _wave_stats(parsed),
        "agents": _agent_stats(parsed["events"]),
        "engine_active_s": _interval_union_seconds(dispatch_intervals),
        "human_wait_s": _interval_union_seconds(
            (parse_iso(esc["opened"]), parse_iso(esc["answered_at"]))
            for esc in parsed["escalations"]),
    }


def _run_window(parsed):
    """The run's ``[start, end]``.

    Canonically ``dag.created_at`` → last event ts. This is the one place a
    collection stamp is legitimate: it is not a duration between two ``ts``
    values but a bound, and the run had demonstrably reached its last append.
    When the DAG has no ``created_at`` (or no DAG at all) the earliest observed
    stamp stands in, and the basis records that the start is inferred rather
    than declared."""
    dag_created = parse_iso((parsed["dag"] or {}).get("created_at"))
    event_stamps = sorted(dt for dt in
                          (parse_iso(e["ts"]) for e in parsed["events"]) if dt)
    other = []
    for sc in parsed["sidecars"]:
        other += [parse_iso(sc["started_at"]), parse_iso(sc["finished_at"])]
    for esc in parsed["escalations"]:
        other += [parse_iso(esc["opened"]), parse_iso(esc["answered_at"])]
    observed = sorted(dt for dt in event_stamps + other if dt)
    if not observed and dag_created is None:
        return {"basis": None, "wall_clock_s": None,
                "started_at": None, "finished_at": None}
    start = dag_created or (observed[0] if observed else None)
    end = observed[-1] if observed else dag_created
    basis = BASIS_EVENTS if event_stamps else _basis(False,
                                                     bool(parsed["sidecars"]))
    if dag_created is not None:
        basis = "dag-json+%s" % basis if basis else "dag-json"
    wall = (end - start).total_seconds() if start and end and end > start else None
    return {"basis": basis, "wall_clock_s": wall,
            "started_at": start.isoformat() if start else None,
            "finished_at": end.isoformat() if end else None}


def _dispatch_intervals(events):
    """``(start, end)`` per timed agent-dispatch event.

    Strictly from the payload's ``dispatched_at``/``returned_at`` pair, which
    the controller lifts from the workflow journal. Both are optional, and a
    dispatch missing either contributes no interval — it is counted, never
    timed. The event ``ts`` is a batch collection stamp and cannot stand in for
    a dispatch clock (see module docstring)."""
    for event in _of_type(events, "agent-dispatch"):
        start = parse_iso(_pstamp(event, "dispatched_at"))
        end = parse_iso(_pstamp(event, "returned_at"))
        if start and end and end > start:
            yield (start, end)


def _agent_stats(events):
    """Dispatch count and duration profile by agent, model, and role — the
    dimension a wall-clock regression hides.

    A dispatch's duration is ``returned_at - dispatched_at`` and nothing else;
    one missing either stamp is counted in ``count`` but not in ``timed``, and
    contributes to no duration group."""
    dispatches = _of_type(events, "agent-dispatch")
    if not dispatches:
        return None
    timed = [(e, _dispatch_seconds(e)) for e in dispatches]
    timed = [(e, secs) for e, secs in timed if secs is not None]
    return {
        "basis": BASIS_EVENTS,
        "count": len(dispatches),
        "timed": len(timed),
        "total_s": round(sum(secs for _, secs in timed), 1) if timed else None,
        "by_agent": _duration_group(timed, "agent"),
        "by_model": _duration_group(timed, "model"),
        "by_role": _duration_group(timed, "role"),
        "by_effort": _tally(_pstr(e, "effort") for e in dispatches) or None,
    }


def _dispatch_seconds(event):
    """One dispatch's wall duration from its paired stamps, or None."""
    start = parse_iso(_pstamp(event, "dispatched_at"))
    end = parse_iso(_pstamp(event, "returned_at"))
    if start and end and end >= start:
        return (end - start).total_seconds()
    return None


def _duration_group(timed, field):
    grouped = {}
    for event, secs in timed:
        grouped.setdefault(_dispatch_key(event, field) or "(unknown)",
                           []).append(secs)
    return {
        key: {"count": len(vals), "total_s": round(sum(vals), 1),
              "median_s": round(_median(vals), 1)}
        for key, vals in sorted(grouped.items())
    } or None


def _slice_durations(sidecars):
    durations = {}
    for sc in sidecars:
        start, end = parse_iso(sc["started_at"]), parse_iso(sc["finished_at"])
        if sc["id"] and start and end and end >= start:
            durations[sc["id"]] = round((end - start).total_seconds(), 1)
    return durations or None


def _wave_stats(parsed):
    """Per-wave shape: what the DAG dispatched, how much of it was genuinely
    concurrent according to the sidecar intervals, and what the workflow
    itself reported on completion.

    ``span_s`` is derived here from sidecar intervals; ``workflow_duration_s``
    is the workflow's own measurement from the ``wave-collected`` payload. They
    are reported separately and never reconciled — a gap between them is a real
    signal (dispatch and collection overhead outside the slices' own spans),
    not a discrepancy to average away."""
    waves = (parsed["dag"] or {}).get("waves")
    if not waves:
        return None
    by_id = {sc["id"]: sc for sc in parsed["sidecars"] if sc["id"]}
    collected = _wave_collected_by_index(parsed["events"])
    out = []
    for wave in waves:
        intervals = []
        for slice_id in wave["slice_ids"]:
            sc = by_id.get(slice_id)
            if not sc:
                continue
            start, end = parse_iso(sc["started_at"]), parse_iso(sc["finished_at"])
            if start and end and end >= start:
                intervals.append((start, end))
        event = collected.get(wave["index"])
        out.append({
            "wave": wave["index"],
            "slices": wave["slices"],
            "status": wave["status"],
            "dispatched_via_workflow": wave["workflow_run_id"] is not None,
            "agent_count": _pcount(event, "agent_count") if event else None,
            "max_parallelism": _max_overlap(intervals) if intervals else None,
            "span_s": _interval_union_seconds(intervals),
            "workflow_duration_s": _ms_to_s(_pcount(event, "duration_ms"))
                                   if event else None,
        })
    return out


def _wave_collected_by_index(events):
    """``wave-collected`` events keyed by payload ``index``.

    Last write wins: a resumed run can re-collect a wave, and the later
    notification is the one that describes what finally happened."""
    out = {}
    for event in _of_type(events, "wave-collected"):
        index = _pcount(event, "index")
        if index is not None:
            out[index] = event
    return out


def _ms_to_s(milliseconds):
    return round(milliseconds / 1000.0, 1) if milliseconds is not None else None


# --- tokens ---------------------------------------------------------------

def _token_metrics(parsed):
    """Token accounting from the two independent channels.

    Per-dispatch (``agent-dispatch`` payloads) is the attributable channel but
    is empty in the current harness; per-wave (``wave-collected`` payloads) is
    what the workflow can actually report today. Null only when NEITHER channel
    has anything — never a fabricated zero. When both are present both are
    reported, side by side and unreconciled."""
    dispatch = _dispatch_token_metrics(parsed["events"])
    waves = _wave_token_totals(parsed["events"])
    if dispatch is None and waves is None:
        return None
    fields = dispatch if dispatch is not None \
        else _unattributed_token_fields(parsed["events"])
    return {"basis": _token_basis(dispatch is not None, waves is not None),
            **fields, "wave_totals": waves}


def _token_basis(has_dispatch, has_waves):
    if has_dispatch and has_waves:
        return "%s+%s" % (BASIS_EVENTS, BASIS_WAVE_EVENTS)
    return BASIS_EVENTS if has_dispatch else BASIS_WAVE_EVENTS


def _dispatch_token_metrics(events):
    """Per-dispatch token totals and breakdowns, or None when no dispatch
    reports tokens. ``coverage_rate`` says how much of the run the totals
    cover, so a partial number is never read as a whole one."""
    dispatches = _of_type(events, "agent-dispatch")
    rows = []
    for event in dispatches:
        tin, tout = _pcount(event, "tokens_in"), _pcount(event, "tokens_out")
        if tin is None and tout is None:
            continue
        rows.append({"event": event, "in": tin or 0, "out": tout or 0})
    if not rows:
        return None
    grand = sum(row["in"] + row["out"] for row in rows)
    return {
        "totals": {"in": sum(row["in"] for row in rows),
                   "out": sum(row["out"] for row in rows),
                   "total": grand},
        "dispatches": len(dispatches),
        "dispatches_with_tokens": len(rows),
        "coverage_rate": _ratio(len(rows), len(dispatches)),
        "by_model": _token_group(rows, "model", grand),
        "by_role": _token_group(rows, "role", grand),
        "by_agent": _token_group(rows, "agent", grand),
        "by_scope": _token_group_by_scope(rows, grand),
    }


def _unattributed_token_fields(events):
    """The per-dispatch fields for a run whose only token channel is the wave
    aggregate: every breakdown null, because a wave total is not attributable
    to a model or role and splitting it would be invention.

    ``dispatches`` and ``dispatches_with_tokens`` remain real observations —
    they say how many dispatches happened and that none of them reported
    tokens, which is exactly the current-harness situation and worth seeing."""
    dispatches = _of_type(events, "agent-dispatch")
    return {
        "totals": None,
        "dispatches": len(dispatches),
        "dispatches_with_tokens": 0,
        "coverage_rate": _ratio(0, len(dispatches)),
        "by_model": None,
        "by_role": None,
        "by_agent": None,
        "by_scope": None,
    }


def _wave_token_totals(events):
    """Per-wave and run-total subagent tokens from ``wave-collected`` payloads.

    ``waves_reporting``/``waves_total`` mark partial coverage: when only some
    waves reported, ``total`` is a partial sum and must not be read as the
    run's whole spend. None when no wave reported tokens at all."""
    collected = _of_type(events, "wave-collected")
    if not collected:
        return None
    rows = [{"wave": _pcount(event, "index"),
             "subagent_tokens": _pcount(event, "subagent_tokens")}
            for event in collected]
    reporting = [r for r in rows if r["subagent_tokens"] is not None]
    if not reporting:
        return None
    return {
        "basis": BASIS_WAVE_EVENTS,
        "total": sum(r["subagent_tokens"] for r in reporting),
        "waves": rows,
        "waves_reporting": len(reporting),
        "waves_total": len(rows),
    }


def _token_group(rows, field, grand):
    grouped = {}
    for row in rows:
        key = _dispatch_key(row["event"], field) or "(unknown)"
        grouped.setdefault(key, []).append(row)
    return _token_group_totals(grouped, grand)


def _token_group_by_scope(rows, grand):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["event"]["scope"] or "(unscoped)", []).append(row)
    return _token_group_totals(grouped, grand)


def _token_group_totals(grouped, grand):
    """Per-key totals plus ``share`` of the run's tokens — the dial that says
    which role or model is actually spending the budget."""
    return {
        key: {
            "dispatches": len(group),
            "in": sum(r["in"] for r in group),
            "out": sum(r["out"] for r in group),
            "total": sum(r["in"] + r["out"] for r in group),
            "share": _ratio(sum(r["in"] + r["out"] for r in group), grand),
        }
        for key, group in sorted(grouped.items())
    } or None


# ==========================================================================
# pure core — LEGACY (v1 prose channel)
# ==========================================================================
# Reachable ONLY from `trend`, so a v1 run dir sitting next to v2 runs in the
# same repo still contributes a comparable row. These parsers read the v1
# pinned line grammar of decisions-log.md / escalations.md, which v2 abolished:
# never call them from compute_metrics, never use them to fill a v2 section.
# Anything they produce is marked `basis: "legacy-v1-prose"`.

LEGACY_AT_SUFFIX = re.compile(r"[—–-]\s*AT:\s*(\S+)\s*$")
LEGACY_REVERSIBILITY = re.compile(r"REVERSIBILITY:\s*([A-Za-z/\-]+)", re.IGNORECASE)
LEGACY_MERGE_SHA = re.compile(
    r"\bmerged?(?:\s+commit)?\s*\(?\s*([0-9a-f]{7,40})\b", re.IGNORECASE)
LEGACY_GATE_ITERATIONS = re.compile(r"\bafter\s+(\d+)\b", re.IGNORECASE)
LEGACY_INITIAL_FAIL = re.compile(r"\binitial\s+FAIL\b", re.IGNORECASE)
# Deliberately case-SENSITIVE: v1 gate/integration lines write PASS/FAIL in
# caps; prose like "refactor pass" / "tests pass" must not count.
LEGACY_RESULT_PASS = re.compile(r"\bPASS(?:ED)?\b")
LEGACY_RESULT_FAIL = re.compile(r"\bFAIL(?:ED)?\b")
LEGACY_PRECEDENT = re.compile(r"RATIONALE:\s*precedent\b", re.IGNORECASE)
# A SAFETY mention only counts when not negated ("none SAFETY", "no SAFETY",
# "NOT SAFETY", "non-SAFETY", "0 SAFETY", "without SAFETY").
LEGACY_SAFETY_MENTION = re.compile(
    r"(?:\b(?:none|no|not|non|zero|without)\b[\s—:,-]{0,4}|\b0\s+)?safety\b",
    re.IGNORECASE)

LEGACY_TAG_CLASSES = (
    ("REVIEW-FINDING REFUTED", "refuted"),
    ("IRON COUNCIL", "council"),
    ("COUNCIL", "council"),
    ("DECISION", "decision"),
    ("QUALITY-GATE", "quality_gate"),
    ("INTEGRATION", "integration"),
    ("HUMAN RESOLVED", "human_resolved"),
    ("MERGE", "merge"),
    ("REVIEW", "review"),
    ("DONE", "done"),
)


def legacy_parse_decisions_log(text):
    """v1 decisions-log.md: one event dict per ``[token] TAG…`` line."""
    events = []
    for line in (text or "").splitlines():
        token, rest = _legacy_bracket_prefix(line)
        if token is None or not rest:
            continue
        events.append({
            "token": token,
            "tag": _legacy_classify_tag(rest),
            "rest": rest,
            "at": _legacy_extract_at(rest),
            "reversibility": _legacy_reversibility(rest),
            "shas": LEGACY_MERGE_SHA.findall(rest),
        })
    return events


def _legacy_bracket_prefix(line):
    """Split a ``[token] rest`` line into ``(token, rest)`` or ``(None, "")``."""
    s = line.lstrip("#-* \t")
    if not s.startswith("["):
        return None, ""
    close = s.find("]")
    if close == -1:
        return None, ""
    return s[1:close].strip(), s[close + 1:].strip()


def _legacy_classify_tag(rest):
    upper = rest.upper()
    for prefix, tag in LEGACY_TAG_CLASSES:
        if upper.startswith(prefix):
            return tag
    return "other"


def _legacy_extract_at(rest):
    match = LEGACY_AT_SUFFIX.search(rest)
    return _iso_or_none(match.group(1)) if match else None


def _legacy_reversibility(rest):
    match = LEGACY_REVERSIBILITY.search(rest)
    if not match:
        return None
    value = match.group(1).strip().lower()
    return value if value in REVERSIBILITY_BUCKETS else "other"


def _legacy_line_result(rest):
    """PASS/FAIL verdict of a v1 gate/integration line (caps-only), or None."""
    if LEGACY_RESULT_PASS.search(rest):
        return "PASS"
    if LEGACY_RESULT_FAIL.search(rest):
        return "FAIL"
    return None


def _legacy_mentions_unnegated_safety(text):
    """True when SAFETY appears at least once without a negating prefix.
    (A negated mention is consumed whole by the pattern's prefix group, so its
    group(0) is longer than the bare word.)"""
    return any(match.group(0).lower() == "safety"
               for match in LEGACY_SAFETY_MENTION.finditer(text))


def legacy_parse_escalations(text):
    """v1 escalations.md: one dict per ``## [token] …`` block."""
    out = []
    for header, body in _legacy_split_blocks(text or ""):
        token, title, header_state = _legacy_parse_header(header)
        if token is None:
            continue
        fields = _legacy_body_fields(body)
        status = ("ANSWERED" if header_state == "ANSWERED" or fields["answered"]
                  else header_state)
        out.append({
            "id": token,
            "scope": token,
            "title": title,
            "status": status or "OPEN",
            "trigger": (fields["triggers"] or [None])[0],
            "triggers": fields["triggers"],
            "opened": fields["opened"],
            "answered_at": fields["answered_at"],
        })
    return out


def _legacy_split_blocks(text):
    """Yield ``(header_line, [body_lines])`` for each ``## [...]`` block."""
    header, body = None, []
    for line in text.splitlines():
        if line.startswith("## ["):
            if header is not None:
                yield header, body
            header, body = line, []
        elif header is not None:
            body.append(line)
    if header is not None:
        yield header, body


def _legacy_parse_header(line):
    """Return ``(token, title, state)`` for a header, or ``(None, '', '')``."""
    close = line.find("]", 4)
    if close == -1:
        return None, "", ""
    rest = line[close + 1:]
    if "(status: ANSWERED)" in rest:
        state = "ANSWERED"
    elif "(status: OPEN)" in rest:
        state = "OPEN"
    else:
        state = ""
    return line[4:close].strip(), rest.split("(status:")[0].strip(), state


def _legacy_body_fields(body_lines):
    """Extract Trigger/Opened/Answered-at/filled-Answer from a block body."""
    fields = {"triggers": [], "opened": None, "answered_at": None,
              "answered": False}
    for line in body_lines:
        stripped = line.strip().lstrip("-* ").strip()
        lower = stripped.lower()
        if lower.startswith("trigger:"):
            fields["triggers"] = _legacy_match_triggers(stripped[len("trigger:"):])
        elif lower.startswith("opened:"):
            fields["opened"] = _iso_or_none(stripped[len("opened:"):].strip())
        elif lower.startswith("answered-at:"):
            fields["answered_at"] = _iso_or_none(
                stripped[len("answered-at:"):].strip())
        elif lower.startswith("answer:") and stripped[len("answer:"):].strip():
            fields["answered"] = True
    return fields


def _legacy_match_triggers(text):
    """Keyword-match the canonical triggers; unmatched non-empty -> other."""
    lower = text.lower()
    matched = [t for t in ESCALATION_TRIGGERS if t in lower]
    if matched:
        return matched
    return ["other"] if lower.strip() else []


def legacy_compute_metrics(artifacts):
    """A schema-2 metrics document for a v1 run dir, derived from v1 prose.

    Same document shape as ``compute_metrics`` so ``summary_row`` and the trend
    table do not care which generation a run is — but every section it fills
    carries ``basis: "legacy-v1-prose"``, and everything v1 could not record
    (tokens, per-dispatch timing) stays null."""
    events = legacy_parse_decisions_log(artifacts.get("decisions_text") or "")
    escalations = legacy_parse_escalations(artifacts.get("escalations_text") or "")
    dag = parse_dag(artifacts.get("dag"))
    observed = bool(events or escalations)
    decisions = [e for e in events if e["tag"] == "decision"]
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": artifacts.get("run_id"),
        "run_schema_detected": 1,
        "generated_at": None,
        "sources": {
            "dag": dag is not None,
            "dag_schema_version": None,
            "events": 0,
            "events_skipped": 0,
            "events_truncated": False,
            "event_types": {},
            "sidecars": 0,
            "runbook": False,
            "legacy_decision_lines": len(events),
            "legacy_escalation_blocks": len(escalations),
        },
        "safety": _legacy_safety(events, escalations, decisions, observed),
        "quality": _legacy_quality(events, dag),
        "performance": _legacy_performance(events, escalations, dag),
        "tokens": None,
    }


def _legacy_safety(events, escalations, decisions, observed):
    council = [e for e in events if e["tag"] == "council"]
    verdicts = []
    safety_objections = 0
    for event in council:
        verdict = _legacy_first_verdict(event["rest"].upper())
        if verdict:
            verdicts.append(verdict)
        if verdict == "OBJECT" and _legacy_mentions_unnegated_safety(event["rest"]):
            safety_objections += 1
    precedent = sum(1 for e in decisions if LEGACY_PRECEDENT.search(e["rest"]))
    return {
        "basis": BASIS_LEGACY if observed else None,
        "escalations": {
            "basis": BASIS_LEGACY if observed else None,
            "total": len(escalations) if observed else None,
            "open": sum(1 for e in escalations if e["status"] == "OPEN")
                    if observed else None,
            "answered": sum(1 for e in escalations if e["status"] == "ANSWERED")
                        if observed else None,
            "by_trigger": _tally(t for e in escalations for t in e["triggers"])
                          if observed else None,
            "per_scope": _tally(e["scope"] for e in escalations)
                         if observed else None,
            "unkeyed_events": None,
        },
        "decisions_total": len(decisions) if observed else None,
        "deferrals_total": None,
        "autonomy_ratio": _ratio(len(decisions), len(decisions) + len(escalations))
                          if observed else None,
        "escalation_answer_latency_s": _answer_latency(escalations),
        "council": {
            "basis": BASIS_LEGACY if council else None,
            "verdicts": _tally(verdicts) if council else None,
            "object_rate": _ratio(verdicts.count("OBJECT"), len(council)),
            "safety_objections": safety_objections if council else None,
            "concerns_total": None,
            "concerns_deferred": None,
            "by_member": None,
            "slice_verdicts": None,
            "over_scope_flags": None,
            "over_scope_deferrals": None,
        },
        "reversibility_mix": _tally(e["reversibility"] for e in events) or None,
        "precedent_reuse": {"count": precedent if decisions else None,
                            "rate": _ratio(precedent, len(decisions))},
    }


def _legacy_first_verdict(upper):
    """The council verdict named in an upper-cased v1 line, or ''.
    ENDORSE_WITH_CONCERNS is checked before ENDORSE (it contains 'ENDORSE')."""
    for verdict in ("ENDORSE_WITH_CONCERNS", "OBJECT", "ENDORSE"):
        if verdict in upper:
            return verdict
    return ""


def _legacy_quality(events, dag):
    gate_lines = [e for e in events if e["tag"] == "quality_gate"]
    first_pass = [e for e in gate_lines if not LEGACY_INITIAL_FAIL.search(e["rest"])]
    iterations = None
    if gate_lines:
        iterations = 0
        for event in gate_lines:
            match = LEGACY_GATE_ITERATIONS.search(event["rest"])
            if match:
                iterations += int(match.group(1))
    integration = [e for e in events if e["tag"] == "integration"]
    gate = None
    for event in integration:
        if "INTEGRATION GATE" in event["rest"].upper():
            gate = _legacy_line_result(event["rest"])
    shas = sorted({sha for e in events for sha in e["shas"]})
    return {
        "basis": BASIS_LEGACY if events else None,
        "quality_gate": {
            "basis": BASIS_LEGACY if gate_lines else None,
            "measurements": len(gate_lines) if events else None,
            "scopes": None,
            "first_pass": len(first_pass) if gate_lines else None,
            "first_pass_rate": _ratio(len(first_pass), len(gate_lines)),
            "refactor_passes_total": iterations,
            "failures": sum(1 for e in gate_lines
                            if _legacy_line_result(e["rest"]) == "FAIL")
                        if gate_lines else None,
            "final_status_counts": None,
        },
        "review": {
            "basis": BASIS_LEGACY if events else None,
            "counters": None,
            "verified_findings": None,
            "refuted_rate": None,
            "evidence_failed_drop_rate": None,
            "fix_rounds_total": None,
            "residual_total": None,
            "findings_total": None,
            "reviewer_dispatches": None,
            "findings_per_reviewer_dispatch": None,
            "refuted_by_fixer": None,
            "refuted_by_fixer_rate": None,
            "refuted_findings_logged": sum(1 for e in events
                                           if e["tag"] == "refuted")
                                       if events else None,
            "block_escalations": None,
        },
        "merges": {"basis": BASIS_LEGACY if events else None,
                   "count": len(shas) if events else None,
                   "commits": shas or None},
        "splits": _split_stats(dag),
        "integration": {
            "basis": BASIS_LEGACY if events else None,
            "checks": [{"scope": e["token"],
                        "result": _legacy_line_result(e["rest"])}
                       for e in integration] or None,
            "check_failures": sum(1 for e in integration
                                  if _legacy_line_result(e["rest"]) == "FAIL")
                              if integration else None,
            "gate": gate,
            "remediation_slices": dag["remediation_count"] if dag else None,
        },
        "requirement_coverage": None,
        "slice_outcomes": ({"basis": "dag-json", "counts": dag["status_counts"]}
                           if dag else {"basis": None, "counts": None}),
        "tests": None,
    }


def _legacy_performance(events, escalations, dag):
    """v1 runs recorded no dispatch timing; only the sparse ``AT:`` stamps and
    the DAG's created_at survive, so most of this section stays null."""
    raw = [e["at"] for e in events]
    raw += [e["opened"] for e in escalations] + [e["answered_at"] for e in escalations]
    if dag:
        raw.append(dag["created_at"])
    stamps = sorted(dt for dt in (parse_iso(v) for v in raw) if dt)
    wall = (stamps[-1] - stamps[0]).total_seconds() if len(stamps) >= 2 else None
    return {
        "basis": BASIS_LEGACY if stamps else None,
        "run_wall_clock_s": wall,
        "started_at": stamps[0].isoformat() if stamps else None,
        "finished_at": stamps[-1].isoformat() if stamps else None,
        "slices": None,
        "waves": None,
        "agents": None,
        "engine_active_s": None,
        "human_wait_s": _interval_union_seconds(
            (parse_iso(e["opened"]), parse_iso(e["answered_at"]))
            for e in escalations),
    }


# ==========================================================================
# thin shell — filesystem
# ==========================================================================

def load_run_artifacts(run_dir):
    """Read one v2 run directory into the artifacts dict compute_metrics takes."""
    run_dir = Path(run_dir)
    events_text, truncated = _read_text_flagged(run_dir / "events.jsonl")
    return {
        "run_id": run_dir.name,
        "dag": _load_json(run_dir / "dag.json"),
        "events_text": events_text,
        "events_truncated": truncated,
        "runbook_text": _read_text_capped(run_dir / "runbook.md"),
        "sidecars": [_load_json(p)
                     for p in sorted(run_dir.glob("slice-*-status.json"))],
    }


def load_legacy_artifacts(run_dir):
    """Read one v1 run directory into the artifacts dict
    ``legacy_compute_metrics`` takes (trend only)."""
    run_dir = Path(run_dir)
    return {
        "run_id": run_dir.name,
        "dag": _load_json(run_dir / "dag.json"),
        "decisions_text": _read_text_capped(run_dir / "decisions-log.md"),
        "escalations_text": _read_text_capped(run_dir / "escalations.md"),
    }


def write_metrics(run_dir, metrics):
    """Atomically persist metrics.json into the run dir (tmp + os.replace)."""
    target = Path(run_dir) / "metrics.json"
    tmp = Path(run_dir) / "metrics.json.tmp"
    tmp.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


# ==========================================================================
# thin shell — trend
# ==========================================================================

def discover_run_dirs(root):
    """Run directories under <root>/docs/spec-loop (or under root itself when
    it already IS a docs/spec-loop directory). Accepts both generations: a v2
    dir is recognized by dag.json/events.jsonl, a v1 dir by its prose log."""
    root = Path(root)
    docs = root / "docs" / "spec-loop"
    base = docs if docs.is_dir() else root
    if not base.is_dir():
        return []
    markers = ("dag.json", "events.jsonl", "decisions-log.md")
    return [child for child in sorted(base.iterdir())
            if child.is_dir() and any((child / m).is_file() for m in markers)]


def metrics_for_run_dir(run_dir):
    """The metrics document for one run dir, routed by detected generation.

    This is the ONE place the legacy path is reachable: v2 dirs go through the
    events channel, v1 dirs through the walled-off prose parsers."""
    artifacts = load_run_artifacts(run_dir)
    schema = detect_run_schema(artifacts["dag"],
                              bool((artifacts["events_text"] or "").strip()))
    if schema >= 2:
        return compute_metrics(artifacts)
    return legacy_compute_metrics(load_legacy_artifacts(run_dir))


def trend_rows(root):
    """One summary row per run under root, ordered oldest-first."""
    rows = []
    for run_dir in discover_run_dirs(root):
        rows.append(summary_row(metrics_for_run_dir(run_dir)))
    rows.sort(key=lambda r: (r["started_at"] or "", r["run_id"] or ""))
    return rows


def summary_row(metrics):
    """The fixed small cross-run summary of one metrics document — the trend
    row, also reusable by dashboard_server for its collection payload. Tolerant
    of partially-shaped documents (a committed metrics.json is disk input):
    every missing section degrades to None, never a KeyError."""
    safety = metrics.get("safety") or {}
    quality = metrics.get("quality") or {}
    perf = metrics.get("performance") or {}
    review = quality.get("review") or {}
    tokens = metrics.get("tokens") or {}
    # "What did this run burn" is answered by either channel; the difference
    # between them is attributability, not what is being counted. Prefer the
    # per-dispatch total, fall back to the wave aggregate, never sum the two —
    # and carry `tokens_basis` so a consumer can see which one it got.
    dispatch_total = (tokens.get("totals") or {}).get("total")
    wave_total = (tokens.get("wave_totals") or {}).get("total")
    return {
        "run_id": metrics.get("run_id"),
        "run_schema": metrics.get("run_schema_detected"),
        "started_at": perf.get("started_at"),
        "escalations": (safety.get("escalations") or {}).get("total"),
        "autonomy_ratio": safety.get("autonomy_ratio"),
        "council_object_rate": (safety.get("council") or {}).get("object_rate"),
        "quality_gate_first_pass_rate":
            (quality.get("quality_gate") or {}).get("first_pass_rate"),
        "refuted_rate": review.get("refuted_rate"),
        "evidence_failed_drop_rate": review.get("evidence_failed_drop_rate"),
        "split_rate": (quality.get("splits") or {}).get("split_rate"),
        "integration_gate": (quality.get("integration") or {}).get("gate"),
        "wall_clock_s": perf.get("run_wall_clock_s"),
        "engine_active_s": perf.get("engine_active_s"),
        "human_wait_s": perf.get("human_wait_s"),
        "tokens_total": dispatch_total if dispatch_total is not None
                        else wave_total,
        "tokens_basis": tokens.get("basis"),
    }


TREND_COLUMNS = (
    ("Run", "run_id", "text"),
    ("v", "run_schema", "text"),
    ("Escalations", "escalations", "text"),
    ("Autonomy", "autonomy_ratio", "text"),
    ("Council OBJ", "council_object_rate", "text"),
    ("QG 1st-pass", "quality_gate_first_pass_rate", "text"),
    ("Refuted", "refuted_rate", "text"),
    ("Split rate", "split_rate", "text"),
    ("Gate", "integration_gate", "text"),
    ("Wall clock", "wall_clock_s", "duration"),
    ("Engine", "engine_active_s", "duration"),
    ("Human wait", "human_wait_s", "duration"),
    ("Tokens", "tokens_total", "text"),
)


def render_trend_md(rows):
    """Human trend table (markdown). Nulls render as em dashes — a blank cell
    means "not measurable", which must never look like a zero."""
    lines = ["| " + " | ".join(name for name, _, _ in TREND_COLUMNS) + " |",
             "|" + "---|" * len(TREND_COLUMNS)]
    for row in rows:
        cells = [_fmt_duration(row.get(key)) if kind == "duration"
                 else _fmt(row.get(key))
                 for _, key, kind in TREND_COLUMNS]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _fmt(value):
    if value is None:
        return "—"
    if isinstance(value, float):
        return "%.2f" % value
    return str(value)


def _fmt_duration(seconds):
    if seconds is None:
        return "—"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return "%dh%02dm" % (hours, minutes)
    if minutes:
        return "%dm%02ds" % (minutes, secs)
    return "%ds" % secs


# ==========================================================================
# CLI
# ==========================================================================

def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cmd_compute(args):
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print("error: not a run directory: %s" % run_dir, file=sys.stderr)
        return 2
    metrics = compute_metrics(load_run_artifacts(run_dir))
    metrics["generated_at"] = _now_iso()
    if metrics["run_schema_detected"] < SCHEMA_VERSION:
        print("warning: %s looks like a v1 run dir (no schema_version, no "
              "events.jsonl); v2 sections will be null. Use `trend` to "
              "summarize v1 runs." % run_dir.name, file=sys.stderr)
    if args.write:
        write_metrics(run_dir, metrics)
    print(json.dumps(metrics, indent=2))
    return 0


def cmd_trend(args):
    rows = trend_rows(args.root)
    if not rows:
        print("error: no runs found under %s" % args.root, file=sys.stderr)
        return 2
    if args.md:
        print(render_trend_md(rows))
    else:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "runs": rows},
                         indent=2))
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="run_metrics.py",
        description="Derive safety/quality/performance/token metrics for "
                    "spec-loop v2 runs from their durable artifacts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    comp = sub.add_parser("compute", help="metrics for one run directory")
    comp.add_argument("run_dir", help="docs/spec-loop/<run-id> directory")
    comp.add_argument("--write", action="store_true",
                      help="atomically persist <run-dir>/metrics.json")

    trend = sub.add_parser("trend", help="cross-run comparison (v1 and v2)")
    trend.add_argument("root", nargs="?", default=".",
                       help="repo root (or a docs/spec-loop directory)")
    trend.add_argument("--md", action="store_true",
                       help="markdown table instead of JSON")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.command == "compute":
        return cmd_compute(args)
    return cmd_trend(args)


if __name__ == "__main__":
    sys.exit(main())
