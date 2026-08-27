#!/usr/bin/env python3
"""Guard tests for run_metrics.py — the v2 run-metrics harness.

Fixture strategy:
* V2_* fixtures build one small but fully-instrumented v2 run: an
  ``events.jsonl`` carrying every event type the harness reads (plus an unknown
  type, a malformed line, and a shapeless line, so tolerance is pinned), a
  ``dag.json`` with ``schema_version: 2`` and a ``waves[]`` array, and two v2
  sidecars with review counters, critique verdicts, and an embedded
  EscalationRecord that duplicates an event-derived one (the union must not
  double-count).
* LEGACY_* fixtures are the v1 prose artifacts, verbatim-shaped, pinning the
  walled-off ``legacy_*`` parsers that only ``trend`` reaches — including the
  drift they must accept (REVERSIBILITY: high / n/a, negated SAFETY mentions,
  "tests pass" prose vs PASS verdict tokens).
* Null-honesty is tested as a first-class property: an unobservable metric is
  ``None``, an observed-and-genuinely-zero metric is ``0``, and the two are
  never allowed to collapse into each other.
* Everything runs against isolated tmp dirs. Standard library only (unittest).
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_metrics as rm


# ---------------------------------------------------------------------------
# v2 fixtures
# ---------------------------------------------------------------------------

V2_DAG = {
    "schema_version": 2,
    "run_id": "20260730-v2",
    "base_ref": "spec-loop/20260730-v2/integration",
    "base_sha": "ac3759b",
    "base_branch": "main",
    "merge_mode": "single-branch",
    "mode": "workflow",
    "created_at": "2026-07-30T10:00:00Z",
    "shared_constraints": [],
    "slices": [
        {"id": "s1", "goal": "a", "deps": [], "risk_tier": 2, "depth": 0,
         "parent": None, "status": "complete"},
        {"id": "s2", "goal": "b", "deps": [], "risk_tier": 2, "depth": 0,
         "parent": None, "status": "split"},
        {"id": "s2.1", "goal": "b1", "deps": [], "risk_tier": 2, "depth": 1,
         "parent": "s2", "status": "complete"},
        {"id": "r1", "goal": "fix integration", "deps": ["s1", "s2.1"],
         "risk_tier": 1, "depth": 0, "parent": None, "status": "complete",
         "remediation": True},
    ],
    "waves": [
        {"index": 1, "slice_ids": ["s1", "s2"], "workflow_run_id": "wf_abc123",
         "status": "collected"},
        {"index": 2, "slice_ids": ["s2.1", "r1"], "workflow_run_id": None,
         "status": "collected"},
    ],
}


def ev(ts, scope, type_, **payload):
    return {"ts": ts, "scope": scope, "type": type_, "payload": payload}


# `ts` on every event below is a batch COLLECTION stamp — deliberately set to
# wave-collection time (11:10 for wave 1) on the agent-dispatch events, so any
# regression that reconstructs durations from `ts` produces visibly wrong
# numbers instead of plausible ones. Real timing lives in the payload pairs:
#   implementer [10:12, 10:30] and reviewer [10:25, 10:40] OVERLAP, so the
#   engine-active union is [10:12, 10:40] (1680s) + integration reviewer 480s = 2160s.
V2_EVENT_OBJECTS = [
    ev("2026-07-30T10:00:00Z", "run", "run-created", run_id="20260730-v2"),
    ev("2026-07-30T10:00:30Z", "run", "baseline", tests="281 passed"),
    ev("2026-07-30T10:01:00Z", "intake", "council-verdict",
       member="skeptic", verdict="ENDORSE", concerns=0, safety=False,
       over_scope={"flag": False, "reason": None}),
    ev("2026-07-30T10:01:30Z", "intake", "council-verdict",
       member="guardian", verdict="OBJECT", concerns_folded=3, safety=True,
       deferred=["P2: rename later", "P2: widen the fixture"],
       over_scope={"flag": True, "reason": "adds a tier heuristic"}),
    ev("2026-07-30T10:02:00Z", "intake", "decision",
       title="reuse the existing helper",
       rationale="precedent — run 20260630-full-coverage answered this",
       reversibility="trivial"),
    ev("2026-07-30T10:03:00Z", "s1", "decision",
       title="keep the function name", rationale="file convention",
       reversibility="moderate"),
    ev("2026-07-30T10:04:00Z", "s1", "deferred", title="dashboard charts",
       over_scope=True),
    ev("2026-07-30T10:05:00Z", "wave1", "wave-dispatched",
       index=1, slice_ids=["s1", "s2"]),
    ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
       agent_type="spec-loop:sdd-implementer", model="sonnet", effort="high",
       role="task-implement", dispatched_at="2026-07-30T10:12:00Z",
       returned_at="2026-07-30T10:30:00Z", tokens_in=12000, tokens_out=3000),
    ev("2026-07-30T11:10:00Z", "s2", "escalation-opened",
       id="s2:council-objection", trigger="council-objection",
       title="Council objects to the plan", status="OPEN",
       opened="2026-07-30T10:30:00Z"),
    ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
       agent_type="spec-loop:pr-reviewer", model="sonnet", effort="medium",
       role="review:tests", dispatched_at="2026-07-30T10:25:00Z",
       returned_at="2026-07-30T10:40:00Z", tokens_in=8000, tokens_out=1000),
    ev("2026-07-30T11:10:00Z", "s2", "escalation-answered",
       id="s2:council-objection", answer="Option 1",
       answered_at="2026-07-30T10:40:00Z"),
    ev("2026-07-30T10:41:00Z", "s1", "review-summary",
       round=1, findings=6, confirmed=2, refuted=1, evidence_failed=1,
       refuted_by_fixer=1),
    ev("2026-07-30T10:50:00Z", "s1", "quality-gate", status="FAIL",
       refactor_passes=0, breaches=2),
    ev("2026-07-30T10:55:00Z", "s1", "quality-gate", status="PASS",
       refactor_passes=2),
    ev("2026-07-30T11:02:00Z", "s2", "split-ingested", parent="s2", children=1),
    ev("2026-07-30T11:05:00Z", "s2", "quality-gate", status="PASS",
       refactor_passes=0),
    ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
       agent_type="spec-loop:pr-reviewer-integration", model="opus", effort="high",
       role="review:correctness", dispatched_at="2026-07-30T11:00:00Z",
       returned_at="2026-07-30T11:08:00Z", tokens_in=5000, tokens_out=1000),
    # Untimed, tokenless dispatch: counted, never timed, never a fabricated 0.
    # (Its ts alone would have been enough to fake a duration from.)
    # Deliberately spelled with the LEGACY `agent` key while the three above
    # use the pinned `agent_type` — both must resolve, neither "(unknown)".
    ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
       agent="spec-loop:slice-planner", model="sonnet", role="plan"),
    ev("2026-07-30T11:09:30Z", "s1", "review-summary",
       round=2, findings=2, refuted_by_fixer=0),
    ev("2026-07-30T11:10:00Z", "wave1", "wave-collected", index=1,
       agent_count=17, subagent_tokens=420000, duration_ms=3_720_000),
    ev("2026-07-30T11:11:00Z", "s1", "slice-merged", sha="f5c84ef"),
    ev("2026-07-30T11:12:00Z", "wave1", "integration-check", status="PASS"),
    ev("2026-07-30T11:15:00Z", "s1", "escalation-opened",
       id="s1:review-block", trigger="review-block", title="Reviewer BLOCK",
       status="OPEN", opened="2026-07-30T11:15:00Z"),
    # Wave 2 collected with NO aggregates: every payload field is optional, so
    # its tokens must stay null rather than 0, and the run total must announce
    # itself as partial (waves_reporting 1 of 2).
    ev("2026-07-30T11:20:00Z", "wave2", "wave-collected", index=2),
    ev("2026-07-30T11:20:00Z", "wave2", "integration-check", result="FAIL"),
    ev("2026-07-30T11:25:00Z", "r1", "slice-merged", merge_commit="fb1a744"),
    ev("2026-07-30T11:30:00Z", "phase5", "phase5-gate", status="PASS"),
    # An event type this harness predates: kept and reported, never skipped.
    ev("2026-07-30T11:31:00Z", "run", "future-event", whatever=1),
]

V2_EVENTS = "\n".join(
    [json.dumps(obj) for obj in V2_EVENT_OBJECTS[:8]]
    + ["this is not json {{{"]                                  # skipped
    + [json.dumps(obj) for obj in V2_EVENT_OBJECTS[8:]]
    + [json.dumps({"ts": "2026-07-30T11:32:00Z", "scope": "run"})]  # skipped
) + "\n"

V2_SIDECAR_S1 = {
    "schema_version": 2, "id": "s1", "status": "DONE",
    "branch": "spec-loop/20260730-v2/s1",
    "commits": {"base": "ac3759b", "head": "a576ce0"},
    "risk_tier": 2, "review_tier": 3,
    "critique": {"verdict": "ENDORSE_WITH_CONCERNS", "concerns": 2},
    "tasks_completed": 4,
    "review": {"confirmed": 2, "refuted": 1, "evidence_failed": 1,
               "fix_rounds": 1, "residual": ["P2: naming nit"]},
    "tests": {"command": "python3 -m unittest", "result": "281 passed",
              "scope": "full", "tree_sha": "deadbee"},
    "quality": {"status": "PASS", "detail": "no breaches"},
    "agents_used": 12, "wave": 1,
    "started_at": "2026-07-30T10:10:00Z",
    "finished_at": "2026-07-30T11:10:00Z",
}

# Deliberately carries an embedded EscalationRecord that duplicates the
# event-derived s2:council-objection: the union must count it once.
V2_SIDECAR_S2 = {
    "schema_version": 2, "id": "s2", "status": "SPLIT",
    "branch": "spec-loop/20260730-v2/s2",
    "commits": {"base": "ac3759b", "head": None},
    "risk_tier": 2, "review_tier": 2,
    # 6, not 3: keeps the sidecar rollup (2 + 6 = 8) distinguishable from the
    # events total (0 + 3 folded + 2 deferred = 5) so precedence is testable.
    "critique": {"verdict": "OBJECT", "concerns": 6},
    "quality": {"status": "SKIPPED", "detail": "no code changed"},
    "split": {"children": [{"goal": "b1", "files": [], "subsystems": [],
                            "internal_deps": []}]},
    "escalations": [{
        "id": "s2:council-objection", "trigger": "council-objection",
        "title": "Council objects to the plan", "status": "ANSWERED",
        "opened": "2026-07-30T10:30:00Z", "answer": "Option 1",
        "answered_at": "2026-07-30T10:40:00Z",
    }],
    "agents_used": 5, "wave": 1,
    "started_at": "2026-07-30T10:20:00Z",
    "finished_at": "2026-07-30T11:00:00Z",
}

V2_RUNBOOK = """\
# Runbook — 20260730-v2

## 4. Requirement Traceability

| Requirement (from request / slice goal) | Status | Evidence (commit / test) |
|------------------------------------------|--------|--------------------------|
| Read events.jsonl | delivered | f5c84ef |
| Cross-run trend report | delivered | f5c84ef |
| Token accounting | partial | null when payloads omit tokens |
| Dashboard charts | deferred | next run |

## 5. Decisions Summary
"""


# ---------------------------------------------------------------------------
# v1 (legacy) fixtures — trend's legacy path only
# ---------------------------------------------------------------------------

LEGACY_DAG = {
    "base_ref": "alpha",
    "base_sha": "ac3759b88f4b3c8f49017a12edd2ef6188c890f9",
    "shared_constraints": [],
    "slices": [
        {"id": "s1", "deps": [], "risk_tier": 2, "depth": 0,
         "parent": None, "status": "complete"},
        {"id": "s2", "deps": ["s1"], "risk_tier": 2, "depth": 0,
         "parent": None, "status": "complete"},
        {"id": "s3", "deps": ["s1"], "risk_tier": 2, "depth": 0,
         "parent": None, "status": "split"},
        {"id": "s3a", "deps": ["s1"], "risk_tier": 2, "depth": 1,
         "parent": "s3", "status": "complete"},
    ],
}

LEGACY_DECISIONS = """\
# Decisions Log — legacy

Append-only. One line per autonomous decision made on the human's behalf.

[intake] COUNCIL: ENDORSE_WITH_CONCERNS — 2/5 OBJECT (skeptic, pragmatist: literal "every line"/100% ill-posed), architect+guardian+historian EWC. No SAFETY. Below majority-halt.
[intake] DECISION: durable coverage gate lives in the REPO's .github/workflows/validate.yml — RATIONALE: repo-scoped, deterministic. — REVERSIBILITY: moderate.
[s1] COUNCIL on plan: ENDORSE_WITH_CONCERNS — 1/5 OBJECT (guardian, explicitly NOT SAFETY), skeptic+architect+pragmatist+historian EWC. — REVERSIBILITY: high.
[s1] QUALITY-GATE: initial FAIL (2 breaches) → PASS after 1 behavior-preserving refactor pass. — REVERSIBILITY: high.
[s1] MERGE: slice merged into alpha via --no-ff (merge commit f5c84ef). — REVERSIBILITY: high.
[s3] QUALITY-GATE: PASS on first measurement, no refactor loop needed.
[s7] COUNCIL: OBJECT — 3/5 object (Architect, Skeptic, Guardian; none SAFETY). Majority-OBJECT halts. — REVERSIBILITY: n/a (no code changed; plan not executed).
[s7] HUMAN RESOLVED — Option 1: apply the council's proven remedy.
[s5] DONE — dashboard_launcher.py 65.7%->72.4%; merge ccce2bb.
[s2] MERGE: slice merged into alpha via --no-ff (merge commit fb1a744; slice commit a576ce0, cut from f5c84ef). — REVERSIBILITY: high.
[wave2] INTEGRATION CHECK: 281 tests pass, coverage gate PASS, TOTAL 54.0%->77.0%.
[phase5] INTEGRATION GATE: PASS. Full suite 313 tests. RUN COMPLETE.
[s7] FAIL-CLOSED verified (local dry-run, reverted): Python gate rc=1 on a floor perturbed to 101%. — REVERSIBILITY: high.
"""

LEGACY_ESCALATIONS = """\
# Escalations — legacy

## [intake] Define "every line tested": target, client-JS scope, and durability   (status: ANSWERED)
- Trigger: ambiguity + material-assumption (Iron Council ENDORSE_WITH_CONCERNS; skeptic + pragmatist OBJECT on well-posedness)
- Context: "Ensure that every line of code is tested" specifies no metric.
- If unanswered: block the run.
- Answer:
  1. Target = **Coverable-max + documented exclusions**.

## [s7] Iron Council objects: coverage-fix ordering splits module identity   (status: ANSWERED)
- Trigger: council-objection
- If unanswered: pause this slice (s7); continue all independent slices.
- Answer: **Option 1 — apply the council's proven remedy, then execute.**
"""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def write_run(root, run_id, files):
    """Write a synthetic run directory; dict/list values become JSON files."""
    run_dir = Path(root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = run_dir / name
        if isinstance(content, (dict, list)):
            path.write_text(json.dumps(content, indent=1), encoding="utf-8")
        else:
            path.write_text(content, encoding="utf-8")
    return run_dir


def v2_files(**overrides):
    files = {
        "dag.json": V2_DAG,
        "events.jsonl": V2_EVENTS,
        "runbook.md": V2_RUNBOOK,
        "slice-s1-status.json": V2_SIDECAR_S1,
        "slice-s2-status.json": V2_SIDECAR_S2,
    }
    files.update(overrides)
    return files


def legacy_files():
    return {"dag.json": LEGACY_DAG, "decisions-log.md": LEGACY_DECISIONS,
            "escalations.md": LEGACY_ESCALATIONS}


def compute_for(files, run_id="fixture-run"):
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = write_run(tmp, run_id, files)
        return rm.compute_metrics(rm.load_run_artifacts(run_dir))


def v2_events():
    return rm.parse_events(V2_EVENTS)["events"]


def _events_without(*payload_keys):
    """The v2 event log with the named payload keys stripped — used to model
    the channels a given harness generation cannot populate."""
    dropped = set(payload_keys)
    return "\n".join(json.dumps(
        dict(obj, payload={k: v for k, v in obj["payload"].items()
                           if k not in dropped}))
        for obj in V2_EVENT_OBJECTS)


# ---------------------------------------------------------------------------
# events.jsonl parsing
# ---------------------------------------------------------------------------

class EventsParseTests(unittest.TestCase):
    def setUp(self):
        self.parsed = rm.parse_events(V2_EVENTS)

    def test_all_well_formed_rows_kept(self):
        self.assertEqual(len(self.parsed["events"]), len(V2_EVENT_OBJECTS))

    def test_malformed_and_shapeless_lines_counted_not_crashed(self):
        self.assertEqual(self.parsed["skipped"], 2)

    def test_unknown_event_type_is_kept_and_reported(self):
        self.assertEqual(self.parsed["types"]["future-event"], 1)
        self.assertEqual(self.parsed["types"]["agent-dispatch"], 4)

    def test_missing_payload_becomes_empty_dict(self):
        parsed = rm.parse_events(
            json.dumps({"ts": "2026-07-30T10:00:00Z", "scope": "run",
                        "type": "decision"}) + "\n"
            + json.dumps({"ts": "x", "scope": None, "type": "decision",
                          "payload": "not-a-dict"}) + "\n")
        self.assertEqual([e["payload"] for e in parsed["events"]], [{}, {}])
        self.assertIsNone(parsed["events"][1]["ts"])
        self.assertIsNone(parsed["events"][1]["scope"])

    def test_blank_lines_ignored_empty_text_is_empty(self):
        self.assertEqual(rm.parse_events("\n\n  \n")["events"], [])
        self.assertEqual(rm.parse_events("")["skipped"], 0)

    def test_unparseable_timestamp_is_null_not_guessed(self):
        parsed = rm.parse_events(json.dumps(
            {"ts": "yesterday-ish", "scope": "s1", "type": "decision"}) + "\n")
        self.assertIsNone(parsed["events"][0]["ts"])


class EscalationPairingTests(unittest.TestCase):
    def records_for(self, *events_json):
        parsed = rm.parse_events("\n".join(events_json))["events"]
        return rm.escalations_from_events(parsed)

    def test_paired_by_payload_id(self):
        result = rm.escalations_from_events(v2_events())
        by_id = {r["id"]: r for r in result["records"]}
        self.assertEqual(set(by_id), {"s2:council-objection", "s1:review-block"})
        self.assertEqual(result["unkeyed"], 0)
        answered = by_id["s2:council-objection"]
        self.assertEqual(answered["status"], "ANSWERED")
        self.assertEqual(answered["opened"], "2026-07-30T10:30:00Z")
        self.assertEqual(answered["answered_at"], "2026-07-30T10:40:00Z")
        self.assertEqual(by_id["s1:review-block"]["status"], "OPEN")
        self.assertIsNone(by_id["s1:review-block"]["answered_at"])

    def test_timing_comes_from_the_record_never_from_the_collection_stamp(self):
        # ts is 11:10 (wave collection) while the record opened at 10:30.
        record = rm.escalations_from_events(v2_events())["records"][0]
        self.assertEqual(record["opened"], "2026-07-30T10:30:00Z")
        self.assertNotEqual(record["opened"], "2026-07-30T11:10:00Z")

    def test_open_without_record_timestamps_has_null_timing(self):
        result = self.records_for(json.dumps(
            ev("2026-07-30T11:10:00Z", "s9", "escalation-opened",
               id="s9:ambiguity", trigger="ambiguity")))
        record = result["records"][0]
        self.assertEqual(record["status"], "OPEN")
        self.assertIsNone(record["opened"])

    def test_same_scope_twice_stays_two_escalations(self):
        result = self.records_for(
            json.dumps(ev("2026-07-30T11:10:00Z", "s9", "escalation-opened",
                          id="s9:ambiguity", trigger="ambiguity",
                          opened="2026-07-30T10:00:00Z")),
            json.dumps(ev("2026-07-30T11:10:00Z", "s9", "escalation-opened",
                          id="s9:review-block", trigger="review-block",
                          opened="2026-07-30T10:30:00Z")))
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual([r["trigger"] for r in result["records"]],
                         ["ambiguity", "review-block"])

    def test_id_less_events_never_pair_and_are_counted(self):
        result = self.records_for(
            json.dumps(ev("2026-07-30T11:10:00Z", "s9", "escalation-opened",
                          trigger="ambiguity")),
            json.dumps(ev("2026-07-30T11:10:00Z", "s9", "escalation-answered")))
        self.assertEqual(result["unkeyed"], 2)
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual([r["status"] for r in result["records"]],
                         ["OPEN", "ANSWERED"])

    def test_unkeyed_count_surfaces_in_the_document(self):
        metrics = compute_for({"events.jsonl": json.dumps(
            ev("2026-07-30T11:10:00Z", "s9", "escalation-opened",
               trigger="ambiguity"))})
        self.assertEqual(
            metrics["safety"]["escalations"]["unkeyed_events"], 1)
        self.assertEqual(
            compute_for(v2_files())["safety"]["escalations"]["unkeyed_events"],
            0)

    def test_answer_without_open_is_kept_with_null_opened(self):
        result = self.records_for(json.dumps(
            ev("2026-07-30T11:10:00Z", "s9", "escalation-answered",
               id="s9:ambiguity", answered_at="2026-07-30T10:05:00Z")))
        self.assertEqual(result["records"][0]["status"], "ANSWERED")
        self.assertIsNone(result["records"][0]["opened"])
        self.assertEqual(result["records"][0]["answered_at"],
                         "2026-07-30T10:05:00Z")

    def test_answered_at_in_an_opened_record_marks_it_answered(self):
        result = self.records_for(json.dumps(
            ev("2026-07-30T11:10:00Z", "s9", "escalation-opened",
               id="s9:x", trigger="ambiguity", status="ANSWERED",
               opened="2026-07-30T10:00:00Z",
               answered_at="2026-07-30T10:05:00Z")))
        self.assertEqual(result["records"][0]["status"], "ANSWERED")

    def test_unknown_trigger_becomes_other_absent_stays_null(self):
        result = self.records_for(
            json.dumps(ev("2026-07-30T10:00:00Z", "a", "escalation-opened",
                          id="a:x", trigger="cosmic rays")),
            json.dumps(ev("2026-07-30T10:00:00Z", "b", "escalation-opened",
                          id="b:x")))
        self.assertEqual([r["trigger"] for r in result["records"]],
                         ["other", None])

    def test_internal_error_buckets_as_itself_not_other(self):
        # _normalize_trigger degrades unknowns to "other"; a crash must keep
        # its own by_trigger key so mislabelled resource limits stay visible.
        opened = ev(
            "2026-07-30T10:00:00Z", "a", "escalation-opened",
            id="a:internal-error", trigger="internal-error")
        result = self.records_for(json.dumps(opened))
        triggers = [r["trigger"] for r in result["records"]]
        self.assertEqual(triggers, ["internal-error"])

    def test_internal_error_is_substring_safe_against_every_other_trigger(self):
        # _legacy_match_triggers() in run_metrics.py matches by containment
        # (no line number: it moved once already when internal-error landed).
        others = [t for t in rm.ESCALATION_TRIGGERS if t != "internal-error"]
        for other in others:
            self.assertNotIn(other, "internal-error")
            self.assertNotIn("internal-error", other)

    def test_union_counts_a_duplicated_record_once(self):
        metrics = compute_for(v2_files(), run_id="20260730-v2")
        self.assertEqual(metrics["safety"]["escalations"]["total"], 2)
        self.assertEqual(metrics["safety"]["escalations"]["basis"],
                         rm.BASIS_BOTH)

    def test_sidecar_answer_survives_an_events_channel_that_only_opened(self):
        from_events = [{"id": "s1:x", "scope": "s1", "trigger": "ambiguity",
                        "title": None, "status": "OPEN",
                        "opened": "2026-07-30T10:00:00Z", "answered_at": None}]
        from_sidecars = [{"id": "s1:x", "scope": "s1", "trigger": None,
                          "title": "t", "status": "ANSWERED", "opened": None,
                          "answered_at": "2026-07-30T10:05:00Z"}]
        merged = rm.merge_escalation_records(from_events, from_sidecars)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["status"], "ANSWERED")
        self.assertEqual(merged[0]["answered_at"], "2026-07-30T10:05:00Z")
        self.assertEqual(merged[0]["opened"], "2026-07-30T10:00:00Z")
        self.assertEqual(merged[0]["trigger"], "ambiguity")


# ---------------------------------------------------------------------------
# dag.json / sidecar / runbook parsing
# ---------------------------------------------------------------------------

class DagParseTests(unittest.TestCase):
    def setUp(self):
        self.dag = rm.parse_dag(V2_DAG)

    def test_structure_counts(self):
        self.assertEqual(self.dag["schema_version"], 2)
        self.assertEqual(self.dag["slice_count"], 4)
        self.assertEqual(self.dag["split_parents"], 1)
        self.assertEqual(self.dag["max_depth"], 1)
        self.assertEqual(self.dag["remediation_count"], 1)
        self.assertEqual(self.dag["status_counts"], {"complete": 3, "split": 1})
        self.assertEqual(self.dag["risk_tiers"], {1: 1, 2: 3})
        self.assertEqual(self.dag["slice_ids"], ["s1", "s2", "s2.1", "r1"])

    def test_waves_normalized(self):
        waves = self.dag["waves"]
        self.assertEqual([w["index"] for w in waves], [1, 2])
        self.assertEqual(waves[0]["slices"], 2)
        self.assertEqual(waves[0]["workflow_run_id"], "wf_abc123")
        self.assertIsNone(waves[1]["workflow_run_id"])

    def test_absent_waves_is_none_not_empty(self):
        self.assertIsNone(rm.parse_dag({"slices": []})["waves"])
        self.assertIsNone(rm.parse_dag({"slices": [], "waves": "nope"})["waves"])

    def test_unusable_dag_is_none(self):
        self.assertIsNone(rm.parse_dag(None))
        self.assertIsNone(rm.parse_dag({"slices": "nope"}))
        self.assertIsNone(rm.parse_dag([1, 2]))

    def test_malformed_slice_entries_skipped_not_fatal(self):
        dag = rm.parse_dag({"slices": [{"id": "s1", "status": "complete"},
                                       "junk", None]})
        self.assertEqual(dag["slice_count"], 1)
        self.assertIsNone(dag["max_depth"])


class SidecarParseTests(unittest.TestCase):
    def test_v2_blocks_normalized(self):
        sc = rm.parse_sidecar(V2_SIDECAR_S1)
        self.assertEqual(sc["status"], "DONE")
        self.assertEqual(sc["review_tier"], 3)
        self.assertEqual(sc["critique"],
                         {"verdict": "ENDORSE_WITH_CONCERNS", "concerns": 2})
        self.assertEqual(sc["review"], {"confirmed": 2, "refuted": 1,
                                        "evidence_failed": 1, "fix_rounds": 1,
                                        "residual": 1})
        self.assertEqual(sc["quality_status"], "PASS")
        self.assertEqual(sc["tests_result"], "281 passed")
        self.assertEqual(sc["agents_used"], 12)
        self.assertEqual(sc["wave"], 1)

    def test_optional_blocks_absent_stays_none(self):
        sc = rm.parse_sidecar({"schema_version": 2, "id": "s9",
                               "status": "FAILED"})
        for key in ("critique", "review", "quality_status", "tests_result",
                    "wave", "started_at", "finished_at", "risk_tier"):
            self.assertIsNone(sc[key], key)
        self.assertEqual(sc["escalations"], [])

    def test_garbage_fields_rejected_never_coerced(self):
        sc = rm.parse_sidecar({
            "id": "s1", "status": "NOPE", "wave": True,
            "started_at": "yesterday-ish", "agents_used": -1,
            "critique": {"verdict": "MAYBE"},
            "review": {"confirmed": -1, "unknown_key": 3, "fix_rounds": 2},
            "quality": {"status": "probably"},
        })
        self.assertIsNone(sc["status"])
        self.assertIsNone(sc["wave"])
        self.assertIsNone(sc["started_at"])
        self.assertIsNone(sc["agents_used"])
        self.assertIsNone(sc["critique"])
        self.assertEqual(sc["review"], {"fix_rounds": 2})
        self.assertIsNone(sc["quality_status"])

    def test_non_dict_sidecar_is_none(self):
        self.assertIsNone(rm.parse_sidecar(None))
        self.assertIsNone(rm.parse_sidecar("not json"))

    def test_embedded_escalation_records_normalized(self):
        records = rm.parse_sidecar(V2_SIDECAR_S2)["escalations"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], "s2:council-objection")
        self.assertEqual(records[0]["scope"], "s2")
        self.assertEqual(records[0]["trigger"], "council-objection")
        self.assertEqual(records[0]["status"], "ANSWERED")

    def test_embedded_records_without_id_skipped(self):
        sc = rm.parse_sidecar({"id": "s1", "status": "ESCALATED",
                               "escalations": [{"trigger": "ambiguity"},
                                               "junk"]})
        self.assertEqual(sc["escalations"], [])


class RunbookParseTests(unittest.TestCase):
    def test_traceability_counts(self):
        self.assertEqual(rm.parse_runbook_traceability(V2_RUNBOOK),
                         {"delivered": 2, "partial": 1, "deferred": 1})

    def test_absent_section_is_none(self):
        self.assertIsNone(rm.parse_runbook_traceability("# Runbook\nprose\n"))
        self.assertIsNone(rm.parse_runbook_traceability(""))


class SchemaDetectionTests(unittest.TestCase):
    def test_declared_schema_version_wins(self):
        self.assertEqual(rm.detect_run_schema({"schema_version": 2}, False), 2)
        self.assertEqual(rm.detect_run_schema({"schema_version": 3}, False), 2)

    def test_events_file_alone_marks_a_v2_run(self):
        self.assertEqual(rm.detect_run_schema(None, True), 2)

    def test_v1_dag_without_schema_version_is_v1(self):
        self.assertEqual(rm.detect_run_schema(LEGACY_DAG, False), 1)
        self.assertEqual(rm.detect_run_schema(None, False), 1)


# ---------------------------------------------------------------------------
# compute_metrics — the fully-instrumented v2 run
# ---------------------------------------------------------------------------

class V2SourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metrics = compute_for(v2_files(), run_id="20260730-v2")

    def test_document_header(self):
        self.assertEqual(self.metrics["schema_version"], 2)
        self.assertEqual(self.metrics["run_id"], "20260730-v2")
        self.assertEqual(self.metrics["run_schema_detected"], 2)
        self.assertIsNone(self.metrics["generated_at"])

    def test_sources_expose_channel_health(self):
        sources = self.metrics["sources"]
        self.assertTrue(sources["dag"])
        self.assertEqual(sources["dag_schema_version"], 2)
        self.assertEqual(sources["events"], len(V2_EVENT_OBJECTS))
        self.assertEqual(sources["events_skipped"], 2)
        self.assertEqual(sources["sidecars"], 2)
        self.assertTrue(sources["runbook"])
        self.assertEqual(sources["event_types"]["quality-gate"], 3)


class V2SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.safety = compute_for(v2_files(), run_id="20260730-v2")["safety"]

    def test_escalation_stats(self):
        escalations = self.safety["escalations"]
        self.assertEqual(escalations["total"], 2)
        self.assertEqual(escalations["open"], 1)
        self.assertEqual(escalations["answered"], 1)
        self.assertEqual(escalations["by_trigger"],
                         {"council-objection": 1, "review-block": 1})
        self.assertEqual(escalations["per_scope"], {"s1": 1, "s2": 1})

    def test_autonomy_ratio_from_decision_vs_escalation_events(self):
        self.assertEqual(self.safety["decisions_total"], 2)
        self.assertEqual(self.safety["deferrals_total"], 1)
        self.assertEqual(self.safety["autonomy_ratio"], 0.5)

    def test_answer_latency(self):
        self.assertEqual(self.safety["escalation_answer_latency_s"],
                         {"count": 1, "median_s": 600.0, "max_s": 600.0})

    def test_council_verdicts_from_events_and_sidecars(self):
        council = self.safety["council"]
        self.assertEqual(council["basis"], rm.BASIS_BOTH)
        self.assertEqual(council["verdicts"], {"ENDORSE": 1, "OBJECT": 1})
        self.assertEqual(council["object_rate"], 0.5)
        self.assertEqual(council["safety_objections"], 1)
        self.assertEqual(council["concerns_total"], 5)   # 0 + (3 folded + 2 deferred)
        self.assertEqual(council["concerns_deferred"], 2)
        self.assertEqual(council["by_member"], {"guardian": 1, "skeptic": 1})
        self.assertEqual(council["slice_verdicts"],
                         {"ENDORSE_WITH_CONCERNS": 1, "OBJECT": 1})

    def test_concerns_total_sums_the_disposition_split(self):
        """skeptic writes `concerns: 0`; guardian writes the workflow split
        `concerns_folded: 3` + 2 deferred. A deferred concern was still raised,
        so the total is 5 — reading concerns_folded alone would report 3."""
        self.assertEqual(self.safety["council"]["concerns_total"], 5)

    def test_reversibility_and_precedent_from_decision_payloads(self):
        self.assertEqual(self.safety["reversibility_mix"],
                         {"moderate": 1, "trivial": 1})
        self.assertEqual(self.safety["precedent_reuse"],
                         {"count": 1, "rate": 0.5})

    def test_over_scope_counters_read_the_recorded_scope_judgements(self):
        council = self.safety["council"]
        self.assertEqual(council["over_scope_flags"], 1)  # guardian flagged
        # over_scope_deferrals is run-wide (deferred events), not council-scoped.
        self.assertEqual(self.safety["over_scope_deferrals"], 1)  # one marked deferral


class CouncilConcernsPrecedenceTests(unittest.TestCase):
    """Events are per-verdict; the sidecar critique is a per-slice rollup.
    Summing both would double-count, so events win and the sidecar is only a
    fallback."""

    def test_events_win_over_the_sidecar_rollup(self):
        # Events total 5; the two sidecar critiques total 8. Expect 5, not 13.
        council = compute_for(v2_files())["safety"]["council"]
        self.assertEqual(council["concerns_total"], 5)

    def test_sidecar_is_the_fallback_when_no_verdict_carries_a_count(self):
        metrics = compute_for(v2_files(**{"events.jsonl": _events_without(
            "concerns", "concerns_folded", "deferred")}))
        council = metrics["safety"]["council"]
        self.assertEqual(council["concerns_total"], 8)   # 2 (s1) + 6 (s2)
        self.assertEqual(council["basis"], rm.BASIS_BOTH)

    def council_total(self, **payload):
        events = json.dumps(ev("2026-07-30T10:00:00Z", "intake",
                               "council-verdict", verdict="OBJECT", **payload))
        return compute_for({"events.jsonl": events})["safety"]["council"]

    def test_folded_plus_deferred_is_the_total_raised(self):
        self.assertEqual(self.council_total(
            concerns_folded=3, deferred=["a", "b"])["concerns_total"], 5)

    def test_folded_alone_and_deferred_alone_each_count(self):
        self.assertEqual(
            self.council_total(concerns_folded=4)["concerns_total"], 4)
        self.assertEqual(
            self.council_total(deferred=["a"])["concerns_total"], 1)

    def test_complete_concerns_count_wins_over_the_split(self):
        """`concerns` is already a total, so it is not added to the split."""
        council = self.council_total(concerns=7, concerns_folded=3,
                                     deferred=["a", "b"])
        self.assertEqual(council["concerns_total"], 7)
        self.assertEqual(council["concerns_deferred"], 2)

    def test_zero_folded_with_no_deferred_is_an_honest_zero(self):
        self.assertEqual(
            self.council_total(concerns_folded=0)["concerns_total"], 0)

    def test_null_when_neither_channel_counts_concerns(self):
        events = json.dumps(ev("2026-07-30T10:00:00Z", "intake",
                               "council-verdict", verdict="ENDORSE"))
        council = compute_for({"events.jsonl": events})["safety"]["council"]
        self.assertIsNone(council["concerns_total"])
        self.assertIsNone(council["concerns_deferred"])

    def test_a_clean_scope_judgement_is_an_honest_zero_not_a_null(self):
        council = self.council_total(over_scope={"flag": False, "reason": None})
        self.assertEqual(council["over_scope_flags"], 0)

    def test_no_scope_judgement_at_all_stays_null(self):
        # "no payload said over_scope" is not evidence that nothing was over scope.
        self.assertIsNone(self.council_total(concerns=1)["over_scope_flags"])

    def test_a_malformed_scope_record_is_not_counted_as_clean(self):
        self.assertIsNone(
            self.council_total(over_scope={"flag": "yes"})["over_scope_flags"])

    def test_deferrals_without_a_scope_marker_stay_null(self):
        # over_scope_deferrals is run-wide (safety, not safety.council): a
        # council-verdict event alone carries no `deferred` events at all.
        events = json.dumps(ev(
            "2026-07-30T10:00:00Z", "intake", "council-verdict",
            verdict="OBJECT", concerns=1))
        safety = compute_for({"events.jsonl": events})["safety"]
        self.assertIsNone(safety["over_scope_deferrals"])

    def test_deferred_events_without_the_scope_marker_stay_null(self):
        events = json.dumps(ev(
            "2026-07-30T10:00:00Z", "s1", "deferred", title="later"))
        safety = compute_for({"events.jsonl": events})["safety"]
        self.assertIsNone(safety["over_scope_deferrals"])

    def test_critique_with_only_concerns_still_reaches_the_document(self):
        metrics = compute_for({"slice-s1-status.json": {
            "schema_version": 2, "id": "s1", "status": "DONE",
            "critique": {"concerns": 4}}})
        council = metrics["safety"]["council"]
        self.assertEqual(council["concerns_total"], 4)
        self.assertIsNone(council["verdicts"])


class DispatchAgentKeyTests(unittest.TestCase):
    """`agent_type` is the pinned payload key; bare `agent` is a legacy alias.
    Neither spelling may ever land in the "(unknown)" bucket."""

    def test_pinned_agent_type_groups_by_name(self):
        perf = compute_for(v2_files())["performance"]
        by_agent = perf["agents"]["by_agent"]
        self.assertEqual(sorted(by_agent), ["spec-loop:pr-reviewer",
                                            "spec-loop:pr-reviewer-integration",
                                            "spec-loop:sdd-implementer"])
        self.assertNotIn("(unknown)", by_agent)

    def test_legacy_agent_alias_still_resolves(self):
        events = "\n".join(json.dumps(e) for e in [
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent="legacy-name", model="sonnet", role="plan",
               dispatched_at="2026-07-30T10:00:00Z",
               returned_at="2026-07-30T10:10:00Z", tokens_in=10, tokens_out=5),
        ])
        metrics = compute_for({"events.jsonl": events})
        self.assertIn("legacy-name",
                      metrics["performance"]["agents"]["by_agent"])
        self.assertIn("legacy-name", metrics["tokens"]["by_agent"])

    def test_agent_type_wins_when_both_spellings_are_present(self):
        events = json.dumps(ev(
            "2026-07-30T11:10:00Z", "s1", "agent-dispatch",
            agent_type="pinned-name", agent="legacy-name", model="sonnet",
            role="plan", dispatched_at="2026-07-30T10:00:00Z",
            returned_at="2026-07-30T10:10:00Z"))
        by_agent = compute_for({"events.jsonl": events})[
            "performance"]["agents"]["by_agent"]
        self.assertEqual(list(by_agent), ["pinned-name"])

    def test_reviewer_dispatch_count_sees_agent_type(self):
        """A reviewer identifiable only by agent_type must still be counted —
        the path that silently under-counted before the fix."""
        events = "\n".join(json.dumps(e) for e in [
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent_type="spec-loop:pr-reviewer", model="opus", role="aspect"),
            ev("2026-07-30T11:10:00Z", "s1", "review-summary", findings=9),
        ])
        review = compute_for({"events.jsonl": events})["quality"]["review"]
        self.assertEqual(review["reviewer_dispatches"], 1)
        self.assertEqual(review["findings_total"], 9)
        self.assertEqual(review["findings_per_reviewer_dispatch"], 9.0)

    def test_re_reviewer_rounds_count_toward_the_denominator(self):
        """`re-review:2` does not trip the role hint's word boundary, so the
        agent family is the only signal. Missing it would divide round-2
        findings by round-1 dispatches only, inflating findings-per-dispatch."""
        events = "\n".join(json.dumps(e) for e in [
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent_type="spec-loop:pr-reviewer", model="opus",
               role="review:tests"),
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent_type="spec-loop:re-reviewer", model="sonnet",
               role="re-review:2"),
            ev("2026-07-30T11:11:00Z", "s1", "review-summary", findings=4),
        ])
        review = compute_for({"events.jsonl": events})["quality"]["review"]
        self.assertEqual(review["reviewer_dispatches"], 2)
        self.assertEqual(review["findings_per_reviewer_dispatch"], 2.0)

    def test_lane_variants_count_via_the_agent_family(self):
        events = "\n".join(json.dumps(e) for e in [
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent_type="spec-loop:pr-reviewer-integration", model="opus",
               role="anything"),
            ev("2026-07-30T11:11:00Z", "s1", "review-summary", findings=1),
        ])
        review = compute_for({"events.jsonl": events})["quality"]["review"]
        self.assertEqual(review["reviewer_dispatches"], 1)

    def test_adjudicators_and_workers_are_not_reviewer_dispatches(self):
        """finding-verifier adjudicates and the implementer implements; neither
        reports findings, so neither belongs in the denominator."""
        events = "\n".join(json.dumps(e) for e in [
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent_type="spec-loop:finding-verifier", model="sonnet",
               role="verify-findings"),
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent_type="spec-loop:implementer", model="sonnet",
               role="task:t1"),
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent_type="spec-loop:slice-planner", model="sonnet",
               role="plan"),
            ev("2026-07-30T11:11:00Z", "s1", "review-summary", findings=3),
        ])
        review = compute_for({"events.jsonl": events})["quality"]["review"]
        self.assertEqual(review["reviewer_dispatches"], 0)
        self.assertIsNone(review["findings_per_reviewer_dispatch"])

    def test_dispatch_with_no_agent_name_at_all_is_unknown(self):
        events = json.dumps(ev(
            "2026-07-30T11:10:00Z", "s1", "agent-dispatch", model="sonnet",
            role="plan", dispatched_at="2026-07-30T10:00:00Z",
            returned_at="2026-07-30T10:10:00Z"))
        by_agent = compute_for({"events.jsonl": events})[
            "performance"]["agents"]["by_agent"]
        self.assertEqual(list(by_agent), ["(unknown)"])


class V2QualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quality = compute_for(v2_files(), run_id="20260730-v2")["quality"]

    def test_quality_gate_first_pass_is_per_scope(self):
        gate = self.quality["quality_gate"]
        self.assertEqual(gate["basis"], rm.BASIS_BOTH)
        self.assertEqual(gate["measurements"], 3)
        self.assertEqual(gate["scopes"], 2)
        self.assertEqual(gate["first_pass"], 1)
        self.assertEqual(gate["first_pass_rate"], 0.5)
        self.assertEqual(gate["refactor_passes_total"], 2)
        self.assertEqual(gate["failures"], 1)
        self.assertEqual(gate["final_status_counts"],
                         {"PASS": 1, "SKIPPED": 1})

    def test_review_counters_come_from_the_sidecar_not_double_counted(self):
        review = self.quality["review"]
        self.assertEqual(review["counters"], {"confirmed": 2, "refuted": 1,
                                              "evidence_failed": 1,
                                              "fix_rounds": 1, "residual": 1})
        self.assertEqual(review["verified_findings"], 3)
        self.assertEqual(review["refuted_rate"], 0.3333)
        self.assertEqual(review["fix_rounds_total"], 1)
        self.assertEqual(review["residual_total"], 1)

    def test_evidence_failed_drop_rate(self):
        self.assertEqual(self.quality["review"]["evidence_failed_drop_rate"],
                         0.25)

    def test_findings_per_reviewer_dispatch(self):
        review = self.quality["review"]
        self.assertEqual(review["findings_total"], 8)
        self.assertEqual(review["reviewer_dispatches"], 2)
        self.assertEqual(review["findings_per_reviewer_dispatch"], 4.0)

    def test_refuted_by_fixer_rate(self):
        review = self.quality["review"]
        self.assertEqual(review["refuted_by_fixer"], 1)
        self.assertEqual(review["refuted_by_fixer_rate"], 0.125)

    def test_review_block_escalations_counted(self):
        self.assertEqual(self.quality["review"]["block_escalations"], 1)

    def test_merges_from_slice_merged_events(self):
        self.assertEqual(self.quality["merges"],
                         {"basis": rm.BASIS_EVENTS, "count": 2,
                          "commits": ["f5c84ef", "fb1a744"]})

    def test_split_rate_from_dag(self):
        splits = self.quality["splits"]
        self.assertEqual(splits["basis"], "dag-json")
        self.assertEqual(splits["split_rate"], 0.25)
        self.assertEqual(splits["max_depth"], 1)
        self.assertEqual(splits["remediation_slices"], 1)

    def test_integration_checks_and_phase5_gate(self):
        integration = self.quality["integration"]
        self.assertEqual(integration["checks"],
                         [{"scope": "wave1", "result": "PASS"},
                          {"scope": "wave2", "result": "FAIL"}])
        self.assertEqual(integration["check_failures"], 1)
        self.assertEqual(integration["gate"], "PASS")
        self.assertEqual(integration["remediation_slices"], 1)

    def test_requirement_coverage_marked_as_prose_derived(self):
        coverage = self.quality["requirement_coverage"]
        self.assertEqual(coverage["basis"], rm.BASIS_RUNBOOK)
        self.assertEqual(coverage["rate"], 0.5)
        self.assertEqual(coverage["delivered"], 2)

    def test_slice_outcomes_and_tests_from_sidecars(self):
        self.assertEqual(self.quality["slice_outcomes"],
                         {"basis": rm.BASIS_SIDECAR,
                          "counts": {"DONE": 1, "SPLIT": 1}})
        self.assertEqual(self.quality["tests"],
                         {"basis": rm.BASIS_SIDECAR,
                          "results": {"281 passed": 1}})


class V2PerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.perf = compute_for(v2_files(), run_id="20260730-v2")["performance"]

    def test_wall_clock_from_dag_created_at_to_last_event(self):
        self.assertEqual(self.perf["basis"], "dag-json+events-jsonl")
        self.assertEqual(self.perf["started_at"], "2026-07-30T10:00:00+00:00")
        self.assertEqual(self.perf["finished_at"], "2026-07-30T11:31:00+00:00")
        self.assertEqual(self.perf["run_wall_clock_s"], 5460.0)

    def test_slice_durations_from_sidecars(self):
        self.assertEqual(self.perf["slices"], {"s1": 3600.0, "s2": 2400.0})

    def test_wave_parallelism_from_dag_waves(self):
        waves = self.perf["waves"]
        self.assertEqual(waves[0], {"wave": 1, "slices": 2,
                                    "status": "collected",
                                    "dispatched_via_workflow": True,
                                    "agent_count": 17,
                                    "max_parallelism": 2, "span_s": 3600.0,
                                    "workflow_duration_s": 3720.0})
        self.assertEqual(waves[1]["dispatched_via_workflow"], False)
        self.assertIsNone(waves[1]["max_parallelism"])
        self.assertIsNone(waves[1]["span_s"])

    def test_workflow_reported_duration_is_separate_from_sidecar_span(self):
        """span_s (3600) is the slices' own union; workflow_duration_s (3720)
        is the workflow's measurement including dispatch/collect overhead.
        Both are reported; neither overwrites the other."""
        wave1 = self.perf["waves"][0]
        self.assertEqual(wave1["span_s"], 3600.0)
        self.assertEqual(wave1["workflow_duration_s"], 3720.0)

    def test_wave_aggregates_absent_stay_null(self):
        wave2 = self.perf["waves"][1]
        self.assertIsNone(wave2["agent_count"])
        self.assertIsNone(wave2["workflow_duration_s"])

    def test_agent_profile_by_agent_model_role(self):
        agents = self.perf["agents"]
        self.assertEqual(agents["count"], 4)
        self.assertEqual(agents["timed"], 3)
        self.assertEqual(agents["total_s"], 2460.0)
        self.assertEqual(agents["by_model"]["sonnet"],
                         {"count": 2, "total_s": 1980.0, "median_s": 990.0})
        self.assertEqual(agents["by_model"]["opus"],
                         {"count": 1, "total_s": 480.0, "median_s": 480.0})
        self.assertEqual(agents["by_role"]["task-implement"]["total_s"], 1080.0)
        self.assertEqual(
            agents["by_agent"]["spec-loop:pr-reviewer-integration"]["median_s"], 480.0)
        self.assertEqual(agents["by_effort"], {"high": 2, "medium": 1})

    def test_engine_active_counts_overlapping_dispatches_once(self):
        self.assertEqual(self.perf["engine_active_s"], 2160.0)

    def test_human_wait_from_escalation_intervals(self):
        self.assertEqual(self.perf["human_wait_s"], 600.0)


class V2TokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens = compute_for(v2_files(), run_id="20260730-v2")["tokens"]

    def test_both_channels_reported_side_by_side(self):
        self.assertEqual(self.tokens["basis"],
                         "events-jsonl+wave-collected-events")
        self.assertEqual(self.tokens["totals"]["total"], 30000)
        self.assertEqual(self.tokens["wave_totals"]["total"], 420000)

    def test_wave_totals_per_wave_and_run_total(self):
        wave_totals = self.tokens["wave_totals"]
        self.assertEqual(wave_totals["basis"], rm.BASIS_WAVE_EVENTS)
        self.assertEqual(wave_totals["waves"],
                         [{"wave": 1, "subagent_tokens": 420000},
                          {"wave": 2, "subagent_tokens": None}])
        self.assertEqual(wave_totals["total"], 420000)

    def test_partial_wave_coverage_is_announced(self):
        wave_totals = self.tokens["wave_totals"]
        self.assertEqual(wave_totals["waves_reporting"], 1)
        self.assertEqual(wave_totals["waves_total"], 2)

    def test_totals_and_coverage(self):
        self.assertEqual(self.tokens["totals"],
                         {"in": 25000, "out": 5000, "total": 30000})
        self.assertEqual(self.tokens["dispatches"], 4)
        self.assertEqual(self.tokens["dispatches_with_tokens"], 3)
        self.assertEqual(self.tokens["coverage_rate"], 0.75)

    def test_per_model_breakdown_and_share(self):
        self.assertEqual(self.tokens["by_model"]["sonnet"],
                         {"dispatches": 2, "in": 20000, "out": 4000,
                          "total": 24000, "share": 0.8})
        self.assertEqual(self.tokens["by_model"]["opus"]["share"], 0.2)

    def test_per_role_token_share(self):
        by_role = self.tokens["by_role"]
        self.assertEqual(by_role["task-implement"]["share"], 0.5)
        self.assertEqual(by_role["review:tests"]["share"], 0.3)
        self.assertEqual(by_role["review:correctness"]["share"], 0.2)
        self.assertAlmostEqual(sum(v["share"] for v in by_role.values()), 1.0)

    def test_scope_breakdown(self):
        self.assertEqual(self.tokens["by_scope"]["s1"]["total"], 30000)

    def test_current_harness_shape_wave_aggregate_only(self):
        """The live case: journal keys are opaque digests, so no dispatch
        reports tokens and only the wave aggregate exists. The section must
        still report the wave total, with every attribution null."""
        metrics = compute_for(v2_files(**{"events.jsonl": _events_without(
            "tokens_in", "tokens_out")}))
        tokens = metrics["tokens"]
        self.assertEqual(tokens["basis"], rm.BASIS_WAVE_EVENTS)
        self.assertEqual(tokens["wave_totals"]["total"], 420000)
        self.assertIsNone(tokens["totals"])
        for key in ("by_model", "by_role", "by_agent", "by_scope"):
            self.assertIsNone(tokens[key], key)
        # The dispatches themselves are still counted — 4 happened, 0 reported.
        self.assertEqual(tokens["dispatches"], 4)
        self.assertEqual(tokens["dispatches_with_tokens"], 0)
        self.assertEqual(tokens["coverage_rate"], 0.0)
        self.assertEqual(metrics["performance"]["agents"]["count"], 4)

    def test_tokens_null_only_when_neither_channel_reports(self):
        metrics = compute_for(v2_files(**{"events.jsonl": _events_without(
            "tokens_in", "tokens_out", "subagent_tokens")}))
        self.assertIsNone(metrics["tokens"])
        self.assertEqual(metrics["performance"]["agents"]["count"], 4)

    def test_wave_totals_null_when_only_dispatches_report(self):
        metrics = compute_for(v2_files(**{"events.jsonl": _events_without(
            "subagent_tokens")}))
        self.assertEqual(metrics["tokens"]["basis"], rm.BASIS_EVENTS)
        self.assertIsNone(metrics["tokens"]["wave_totals"])
        self.assertEqual(metrics["tokens"]["totals"]["total"], 30000)


# ---------------------------------------------------------------------------
# null-honesty: unobservable is None, observed-and-zero is 0
# ---------------------------------------------------------------------------

class NullHonestyTests(unittest.TestCase):
    def test_empty_run_dir_is_all_null_never_zero(self):
        metrics = compute_for({}, run_id="empty")
        self.assertEqual(metrics["schema_version"], 2)
        self.assertEqual(metrics["run_schema_detected"], 1)
        self.assertFalse(metrics["sources"]["dag"])
        safety = metrics["safety"]
        self.assertIsNone(safety["basis"])
        self.assertIsNone(safety["escalations"]["total"])
        self.assertIsNone(safety["decisions_total"])
        self.assertIsNone(safety["autonomy_ratio"])
        self.assertIsNone(safety["council"]["verdicts"])
        self.assertIsNone(safety["council"]["safety_objections"])
        self.assertIsNone(safety["reversibility_mix"])
        quality = metrics["quality"]
        self.assertIsNone(quality["basis"])
        self.assertIsNone(quality["quality_gate"]["measurements"])
        self.assertIsNone(quality["review"]["counters"])
        self.assertIsNone(quality["merges"]["count"])
        self.assertIsNone(quality["splits"])
        self.assertIsNone(quality["integration"]["gate"])
        self.assertIsNone(quality["requirement_coverage"])
        self.assertIsNone(metrics["performance"]["basis"])
        self.assertIsNone(metrics["performance"]["run_wall_clock_s"])
        self.assertIsNone(metrics["tokens"])

    def test_observed_run_with_nothing_to_report_yields_real_zeros(self):
        events = json.dumps(ev("2026-07-30T10:00:00Z", "run", "run-created"))
        metrics = compute_for({"events.jsonl": events + "\n"})
        safety = metrics["safety"]
        self.assertEqual(safety["basis"], rm.BASIS_EVENTS)
        self.assertEqual(safety["escalations"]["total"], 0)
        self.assertEqual(safety["decisions_total"], 0)
        self.assertIsNone(safety["autonomy_ratio"])
        self.assertIsNone(safety["council"]["verdicts"])
        self.assertEqual(metrics["quality"]["merges"]["count"], 0)
        self.assertIsNone(metrics["quality"]["quality_gate"]["measurements"])

    def test_safety_objection_stays_null_when_no_payload_flags_it(self):
        events = json.dumps(ev("2026-07-30T10:00:00Z", "intake",
                               "council-verdict", verdict="OBJECT",
                               member="guardian"))
        council = compute_for({"events.jsonl": events})["safety"]["council"]
        self.assertEqual(council["verdicts"], {"OBJECT": 1})
        self.assertEqual(council["object_rate"], 1.0)
        self.assertIsNone(council["safety_objections"])
        self.assertIsNone(council["concerns_total"])

    def test_over_scope_counters_are_null_on_an_uninstrumented_run(self):
        safety = compute_for({"slice-s1-status.json": {
            "schema_version": 2, "id": "s1", "status": "DONE",
            "critique": {"verdict": "OBJECT"}}})["safety"]
        self.assertIsNone(safety["council"]["over_scope_flags"])
        self.assertIsNone(safety["over_scope_deferrals"])

    def test_gate_events_without_a_status_leave_the_rate_null(self):
        events = "\n".join(json.dumps(e) for e in [
            ev("2026-07-30T10:00:00Z", "s1", "quality-gate", detail="ran"),
            ev("2026-07-30T10:01:00Z", "s2", "quality-gate", status="maybe"),
        ])
        gate = compute_for({"events.jsonl": events})["quality"]["quality_gate"]
        self.assertEqual(gate["measurements"], 2)
        self.assertEqual(gate["scopes"], 2)
        self.assertIsNone(gate["first_pass"])
        self.assertIsNone(gate["first_pass_rate"])
        self.assertIsNone(gate["refactor_passes_total"])

    def test_malformed_dag_and_sidecar_degrade_without_crashing(self):
        metrics = compute_for({"dag.json": "{{{not json",
                               "events.jsonl": V2_EVENTS,
                               "slice-s1-status.json": "not json",
                               "slice-s2-status.json": V2_SIDECAR_S2})
        self.assertFalse(metrics["sources"]["dag"])
        self.assertEqual(metrics["sources"]["sidecars"], 1)
        self.assertIsNone(metrics["quality"]["splits"])
        self.assertIsNone(metrics["performance"]["waves"])
        # A dag-less v2 run still gets its window from the events channel.
        self.assertEqual(metrics["performance"]["basis"], rm.BASIS_EVENTS)
        self.assertEqual(metrics["run_schema_detected"], 2)

    def test_events_file_over_the_size_cap_reports_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = write_run(tmp, "big", v2_files())
            with mock.patch.object(rm, "MAX_FILE_BYTES", 200):
                artifacts = rm.load_run_artifacts(run_dir)
            self.assertTrue(artifacts["events_truncated"])
            self.assertTrue(rm.compute_metrics(artifacts)
                            ["sources"]["events_truncated"])
            # And a file inside the cap is not falsely flagged.
            self.assertFalse(
                rm.load_run_artifacts(run_dir)["events_truncated"])
            self.assertFalse(compute_for(v2_files())
                             ["sources"]["events_truncated"])

    def test_untimed_dispatches_are_counted_but_never_timed(self):
        events = json.dumps(ev("2026-07-30T10:00:00Z", "s1", "agent-dispatch",
                               agent="a", model="sonnet", role="plan"))
        perf = compute_for({"events.jsonl": events})["performance"]
        self.assertEqual(perf["agents"]["count"], 1)
        self.assertEqual(perf["agents"]["timed"], 0)
        self.assertIsNone(perf["agents"]["total_s"])
        self.assertIsNone(perf["agents"]["by_model"])
        self.assertIsNone(perf["engine_active_s"])

    def test_collection_stamp_is_never_used_as_a_dispatch_clock(self):
        """ts is a batch collection stamp: a dispatch with only a ts, or with a
        legacy duration_s and no stamp pair, is untimed — not reconstructed."""
        events = "\n".join(json.dumps(e) for e in [
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent="a", model="sonnet", role="plan"),
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent="b", model="sonnet", role="plan", duration_s=1800),
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent="c", model="sonnet", role="plan",
               dispatched_at="2026-07-30T10:00:00Z"),
        ])
        perf = compute_for({"events.jsonl": events})["performance"]
        self.assertEqual(perf["agents"]["count"], 3)
        self.assertEqual(perf["agents"]["timed"], 0)
        self.assertIsNone(perf["engine_active_s"])

    def test_only_paired_stamps_produce_a_duration(self):
        events = "\n".join(json.dumps(e) for e in [
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent="a", model="sonnet", role="plan",
               dispatched_at="2026-07-30T10:00:00Z",
               returned_at="2026-07-30T10:10:00Z"),
            ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
               agent="b", model="sonnet", role="plan",
               dispatched_at="2026-07-30T10:00:00Z",
               returned_at="not-a-date"),
        ])
        perf = compute_for({"events.jsonl": events})["performance"]
        self.assertEqual(perf["agents"]["count"], 2)
        self.assertEqual(perf["agents"]["timed"], 1)
        self.assertEqual(perf["agents"]["total_s"], 600.0)
        self.assertEqual(perf["engine_active_s"], 600.0)


class ProseIsNotAFallbackTests(unittest.TestCase):
    """v1 prose must never fill a v2 section, even when the files are present."""

    def test_decisions_log_beside_a_v2_run_is_ignored(self):
        metrics = compute_for(v2_files(
            **{"decisions-log.md": LEGACY_DECISIONS,
               "escalations.md": LEGACY_ESCALATIONS}),
            run_id="20260730-v2")
        self.assertEqual(metrics["safety"]["decisions_total"], 2)
        self.assertEqual(metrics["safety"]["escalations"]["total"], 2)
        self.assertEqual(metrics["safety"]["reversibility_mix"],
                         {"moderate": 1, "trivial": 1})
        self.assertEqual(metrics["quality"]["merges"]["count"], 2)

    def test_v1_run_dir_computes_to_an_honestly_null_v2_document(self):
        metrics = compute_for(legacy_files(), run_id="20260101-legacy")
        self.assertEqual(metrics["run_schema_detected"], 1)
        self.assertIsNone(metrics["safety"]["decisions_total"])
        self.assertIsNone(metrics["safety"]["escalations"]["total"])
        self.assertIsNone(metrics["quality"]["integration"]["gate"])
        # dag.json is readable in both generations, so structure still lands.
        self.assertEqual(metrics["quality"]["splits"]["split_rate"], 0.25)


# ---------------------------------------------------------------------------
# LEGACY path (trend only)
# ---------------------------------------------------------------------------

class LegacyProseParserTests(unittest.TestCase):
    def setUp(self):
        self.events = rm.legacy_parse_decisions_log(LEGACY_DECISIONS)

    def test_one_event_per_bracketed_line(self):
        self.assertEqual(len(self.events), 13)
        self.assertEqual(self.events[0]["token"], "intake")

    def test_tag_classification(self):
        tags = [e["tag"] for e in self.events]
        self.assertEqual(tags.count("council"), 3)
        self.assertEqual(tags.count("decision"), 1)
        self.assertEqual(tags.count("quality_gate"), 2)
        self.assertEqual(tags.count("merge"), 2)
        self.assertEqual(tags.count("integration"), 2)

    def test_reversibility_accepts_observed_drift(self):
        mix = [e["reversibility"] for e in self.events if e["reversibility"]]
        self.assertEqual(mix.count("moderate"), 1)
        self.assertEqual(mix.count("high"), 5)
        self.assertEqual(mix.count("n/a"), 1)

    def test_unknown_reversibility_becomes_other(self):
        events = rm.legacy_parse_decisions_log(
            "[s1] DECISION: x — REVERSIBILITY: reversible-ish.")
        self.assertEqual(events[0]["reversibility"], "other")

    def test_merge_shas_collected_slice_commits_ignored(self):
        shas = {sha for e in self.events for sha in e["shas"]}
        self.assertEqual(shas, {"f5c84ef", "fb1a744", "ccce2bb"})

    def test_negated_safety_mentions_do_not_count(self):
        for text in ("none SAFETY", "No SAFETY (guardian explicit)",
                     "explicitly NOT SAFETY", "non-SAFETY: false-red",
                     "0 SAFETY objections"):
            self.assertFalse(rm._legacy_mentions_unnegated_safety(text), text)
        self.assertTrue(rm._legacy_mentions_unnegated_safety(
            "OBJECT — guardian raises a SAFETY blocker on data loss"))

    def test_lowercase_pass_prose_is_not_a_verdict(self):
        self.assertIsNone(rm._legacy_line_result(
            "measurement skipped; one refactor pass noted, tests pass"))
        self.assertEqual(rm._legacy_line_result("coverage gate PASS"), "PASS")
        self.assertEqual(rm._legacy_line_result("gate FAIL after budget"), "FAIL")

    def test_escalation_blocks_statuses_and_triggers(self):
        escs = rm.legacy_parse_escalations(LEGACY_ESCALATIONS)
        self.assertEqual(len(escs), 2)
        self.assertEqual([e["status"] for e in escs], ["ANSWERED", "ANSWERED"])
        self.assertEqual(escs[0]["triggers"],
                         ["ambiguity", "material-assumption"])
        self.assertEqual(escs[1]["triggers"], ["council-objection"])

    def test_filled_answer_overrides_open_header(self):
        escs = rm.legacy_parse_escalations(
            "## [s1] Pick a port   (status: OPEN)\n"
            "- Trigger: material-assumption\n- Answer: use 8080.\n")
        self.assertEqual(escs[0]["status"], "ANSWERED")
        open_escs = rm.legacy_parse_escalations(
            "## [s1] Pick a port   (status: OPEN)\n"
            "- Trigger: material-assumption\n- Answer:\n")
        self.assertEqual(open_escs[0]["status"], "OPEN")


class LegacyComputeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = write_run(tmp, "20260101-legacy", legacy_files())
            cls.metrics = rm.legacy_compute_metrics(
                rm.load_legacy_artifacts(run_dir))

    def test_document_is_schema_2_marked_as_v1_prose(self):
        self.assertEqual(self.metrics["schema_version"], 2)
        self.assertEqual(self.metrics["run_schema_detected"], 1)
        for section in ("safety", "quality"):
            self.assertEqual(self.metrics[section]["basis"], rm.BASIS_LEGACY)
        self.assertEqual(self.metrics["sources"]["legacy_decision_lines"], 13)

    def test_safety_from_prose(self):
        safety = self.metrics["safety"]
        self.assertEqual(safety["escalations"]["total"], 2)
        self.assertEqual(safety["escalations"]["answered"], 2)
        self.assertEqual(safety["escalations"]["by_trigger"],
                         {"ambiguity": 1, "council-objection": 1,
                          "material-assumption": 1})
        self.assertEqual(safety["decisions_total"], 1)
        self.assertAlmostEqual(safety["autonomy_ratio"], 1 / 3, places=3)
        self.assertEqual(safety["council"]["verdicts"],
                         {"ENDORSE_WITH_CONCERNS": 2, "OBJECT": 1})
        self.assertAlmostEqual(safety["council"]["object_rate"], 1 / 3,
                               places=3)
        self.assertEqual(safety["council"]["safety_objections"], 0)
        self.assertEqual(safety["reversibility_mix"],
                         {"high": 5, "moderate": 1, "n/a": 1})

    def test_the_legacy_prose_path_reports_no_scope_judgement(self):
        safety = self.metrics["safety"]
        self.assertIsNone(safety["council"]["over_scope_flags"])
        self.assertIsNone(safety["over_scope_deferrals"])

    def test_quality_from_prose(self):
        quality = self.metrics["quality"]
        self.assertEqual(quality["quality_gate"]["measurements"], 2)
        self.assertEqual(quality["quality_gate"]["first_pass"], 1)
        self.assertEqual(quality["quality_gate"]["first_pass_rate"], 0.5)
        self.assertEqual(quality["quality_gate"]["refactor_passes_total"], 1)
        self.assertEqual(quality["merges"]["count"], 3)
        self.assertEqual(quality["integration"]["gate"], "PASS")
        self.assertEqual(len(quality["integration"]["checks"]), 2)
        self.assertEqual(quality["splits"]["split_rate"], 0.25)

    def test_v1_could_not_record_the_v2_dials(self):
        review = self.metrics["quality"]["review"]
        for key in ("counters", "evidence_failed_drop_rate",
                    "findings_per_reviewer_dispatch", "refuted_by_fixer_rate"):
            self.assertIsNone(review[key], key)
        perf = self.metrics["performance"]
        for key in ("slices", "waves", "agents", "engine_active_s"):
            self.assertIsNone(perf[key], key)
        self.assertIsNone(self.metrics["tokens"])

    def test_untimestamped_v1_run_has_no_wall_clock(self):
        self.assertIsNone(self.metrics["performance"]["basis"])
        self.assertIsNone(self.metrics["performance"]["run_wall_clock_s"])
        self.assertIsNone(self.metrics["performance"]["started_at"])


# ---------------------------------------------------------------------------
# write / trend / CLI
# ---------------------------------------------------------------------------

class WriteMetricsTests(unittest.TestCase):
    def test_atomic_write_leaves_only_metrics_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = write_run(tmp, "r1", v2_files())
            before = {p.name for p in run_dir.iterdir()}
            metrics = rm.compute_metrics(rm.load_run_artifacts(run_dir))
            target = rm.write_metrics(run_dir, metrics)
            self.assertTrue(target.is_file())
            self.assertFalse((run_dir / "metrics.json.tmp").exists())
            self.assertEqual({p.name for p in run_dir.iterdir()},
                             before | {"metrics.json"})
            reread = json.loads(target.read_text())
            self.assertEqual(reread["schema_version"], 2)
            self.assertEqual(reread["quality"]["review"]["refuted_rate"], 0.3333)


class TrendTests(unittest.TestCase):
    def make_root(self, tmp):
        docs = Path(tmp) / "docs" / "spec-loop"
        write_run(docs, "20260101-legacy", legacy_files())
        write_run(docs, "20260730-v2", v2_files())
        return tmp

    def test_mixed_generations_are_routed_per_run_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = rm.trend_rows(self.make_root(tmp))
        self.assertEqual([r["run_id"] for r in rows],
                         ["20260101-legacy", "20260730-v2"])
        legacy, modern = rows
        self.assertEqual(legacy["run_schema"], 1)
        self.assertEqual(modern["run_schema"], 2)
        # The legacy row is only summarizable through the prose parsers.
        self.assertEqual(legacy["escalations"], 2)
        self.assertEqual(legacy["integration_gate"], "PASS")
        self.assertIsNone(legacy["wall_clock_s"])
        self.assertIsNone(legacy["tokens_total"])

    def test_v2_row_carries_the_new_dials(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = rm.trend_rows(self.make_root(tmp))
        modern = rows[1]
        self.assertEqual(modern["wall_clock_s"], 5460.0)
        self.assertEqual(modern["engine_active_s"], 2160.0)
        self.assertEqual(modern["human_wait_s"], 600.0)
        self.assertEqual(modern["tokens_total"], 30000)
        self.assertEqual(modern["refuted_rate"], 0.3333)
        self.assertEqual(modern["evidence_failed_drop_rate"], 0.25)

    def test_metrics_for_run_dir_picks_the_right_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(self.make_root(tmp)) / "docs" / "spec-loop"
            legacy = rm.metrics_for_run_dir(docs / "20260101-legacy")
            modern = rm.metrics_for_run_dir(docs / "20260730-v2")
        self.assertEqual(legacy["safety"]["basis"], rm.BASIS_LEGACY)
        self.assertEqual(modern["safety"]["basis"], rm.BASIS_BOTH)

    def test_discovery_accepts_both_generations_and_bare_docs_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(self.make_root(tmp)) / "docs" / "spec-loop"
            (docs / "not-a-run").mkdir()
            self.assertEqual([p.name for p in rm.discover_run_dirs(tmp)],
                             ["20260101-legacy", "20260730-v2"])
            self.assertEqual([p.name for p in rm.discover_run_dirs(docs)],
                             ["20260101-legacy", "20260730-v2"])

    def test_markdown_uses_em_dash_for_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            table = rm.render_trend_md(rm.trend_rows(self.make_root(tmp)))
        self.assertIn("| Run |", table)
        self.assertIn("| Engine |", table)
        self.assertIn("20260101-legacy", table)
        self.assertIn("36m00s", table)      # engine_active 2160s
        self.assertIn("1h31m", table)       # wall clock 5460s
        self.assertIn("—", table)
        self.assertNotIn("None", table)

    def test_tokens_total_falls_back_to_the_wave_aggregate(self):
        """Without this the trend Tokens column is blank on every real run,
        since no dispatch can report tokens in the current harness."""
        wave_only = compute_for(v2_files(**{"events.jsonl": _events_without(
            "tokens_in", "tokens_out")}))
        row = rm.summary_row(wave_only)
        self.assertEqual(row["tokens_total"], 420000)
        self.assertEqual(row["tokens_basis"], rm.BASIS_WAVE_EVENTS)

    def test_tokens_total_prefers_the_attributable_channel_never_sums(self):
        row = rm.summary_row(compute_for(v2_files()))
        self.assertEqual(row["tokens_total"], 30000)
        self.assertEqual(row["tokens_basis"],
                         "events-jsonl+wave-collected-events")

    def test_summary_row_tolerates_a_partial_document(self):
        row = rm.summary_row({"run_id": "x"})
        self.assertEqual(row["run_id"], "x")
        self.assertIsNone(row["autonomy_ratio"])
        self.assertIsNone(row["tokens_total"])


class CliTests(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = rm.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_compute_prints_document_and_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = write_run(tmp, "20260730-v2", v2_files())
            rc, out, err = self.run_main(["compute", str(run_dir), "--write"])
            self.assertEqual(rc, 0)
            self.assertEqual(err, "")
            document = json.loads(out)
            self.assertEqual(document["run_id"], "20260730-v2")
            self.assertIsNotNone(document["generated_at"])
            self.assertTrue((run_dir / "metrics.json").is_file())

    def test_compute_without_write_does_not_touch_the_run_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = write_run(tmp, "r1", v2_files())
            before = {p.name for p in run_dir.iterdir()}
            rc, _, _ = self.run_main(["compute", str(run_dir)])
            self.assertEqual(rc, 0)
            self.assertEqual({p.name for p in run_dir.iterdir()}, before)

    def test_compute_warns_on_a_v1_run_dir_but_still_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = write_run(tmp, "20260101-legacy", legacy_files())
            rc, out, err = self.run_main(["compute", str(run_dir)])
        self.assertEqual(rc, 0)
        self.assertIn("v1 run dir", err)
        self.assertIn("trend", err)
        self.assertEqual(json.loads(out)["run_schema_detected"], 1)

    def test_compute_missing_dir_is_usage_error(self):
        rc, _, err = self.run_main(["compute", "/no/such/run-dir"])
        self.assertEqual(rc, 2)
        self.assertIn("not a run directory", err)

    def test_trend_md_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp) / "docs" / "spec-loop"
            write_run(docs, "20260730-v2", v2_files())
            rc, out, _ = self.run_main(["trend", tmp, "--md"])
            self.assertEqual(rc, 0)
            self.assertIn("| Run |", out)
            rc, out, _ = self.run_main(["trend", tmp])
            self.assertEqual(rc, 0)
            document = json.loads(out)
            self.assertEqual(document["schema_version"], 2)
            self.assertEqual(len(document["runs"]), 1)

    def test_trend_empty_root_is_usage_error(self):
        with tempfile.TemporaryDirectory() as empty:
            rc, _, err = self.run_main(["trend", empty])
        self.assertEqual(rc, 2)
        self.assertIn("no runs found", err)


if __name__ == "__main__":
    unittest.main()
