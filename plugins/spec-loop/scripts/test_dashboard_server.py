#!/usr/bin/env python3
"""Tests for the read-only spec-loop-2 dashboard server (stdlib unittest).

Covers the pure data layer — v2 wave composition (recorded waves read verbatim,
undispatched work projected), sidecar-derived labels, escalations from
events.jsonl, council verdicts from events, and the v1 back-compat path — plus
the read-only HTTP layer's risky security paths (path traversal, foreign Host
header, non-GET method), which are exercised over a real socket.

Standard library only.

Usage:
    python3 scripts/test_dashboard_server.py
"""

import contextlib
import http.client
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dashboard_server as ds  # noqa: E402


# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------

def slice_obj(sid, **overrides):
    """Build a slice dict; override any field via kwargs
    (deps, status, depth, parent, goal, risk_tier, ...)."""
    base = {
        "id": sid,
        "goal": "g",
        "files": [],
        "subsystems": [],
        "deps": [],
        "risk_tier": 2,
        "depth": 0,
        "parent": None,
        "status": "pending",
    }
    base.update(overrides)
    return base


def write_dag_v1(run_dir: Path, slices: list, base_ref="alpha", base_sha="abc123"):
    """A v1 dag.json: NO schema_version, NO waves[] — the back-compat shape."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "dag.json").write_text(
        json.dumps({"base_ref": base_ref, "base_sha": base_sha, "slices": slices})
    )


def write_dag_v2(run_dir: Path, slices: list, waves=None, base_ref="alpha",
                 base_sha="abc123", **extra):
    """A v2 dag.json: schema_version 2 plus the recorded waves[] array."""
    run_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 2,
        "run_id": run_dir.name,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "base_branch": "main",
        "merge_mode": "single-branch",
        "mode": "workflow",
        "created_at": "2026-07-30T09:00:00Z",
        "shared_constraints": [],
        "slices": slices,
        "waves": waves if waves is not None else [],
    }
    doc.update(extra)
    (run_dir / "dag.json").write_text(json.dumps(doc))


def wave(index, slice_ids, status="collected", workflow_run_id=None):
    return {"index": index, "slice_ids": list(slice_ids),
            "workflow_run_id": workflow_run_id, "status": status}


def write_sidecar(run_dir: Path, sid, status="DONE", escalations=None, **extra):
    """A schema-2 per-slice sidecar (slice-<id>-status.json)."""
    doc = {
        "schema_version": 2,
        "id": sid,
        "status": status,
        "branch": f"spec-loop/{run_dir.name}/{sid}",
        "commits": {"base": "aaa", "head": "bbb"},
        "risk_tier": 2,
        "review_tier": 2,
        "critique": {"verdict": "ENDORSE", "concerns": 0},
        "tasks_completed": 3,
        "review": {"confirmed": 1, "refuted": 0, "evidence_failed": 0,
                   "fix_rounds": 0, "residual": ["P2: minor"]},
        "tests": {"command": "pytest", "result": "pass", "scope": "full",
                  "tree_sha": "ccc"},
        "quality": {"status": "PASS", "detail": ""},
        "agents_used": 7,
        "wave": 1,
        "started_at": "2026-07-30T10:00:00Z",
        "finished_at": "2026-07-30T10:30:00Z",
    }
    if escalations is not None:
        doc["escalations"] = escalations
    doc.update(extra)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / f"slice-{sid}-status.json").write_text(json.dumps(doc))


def escalation_record(esc_id, trigger="ambiguity", title="needs a call",
                      status="OPEN"):
    return {"id": esc_id, "trigger": trigger, "title": title,
            "context": "ctx", "question": "q?", "options": [],
            "if_unanswered": "pause this slice", "status": status,
            "opened": "2026-07-30T10:05:00Z", "answer": None,
            "answered_at": None}


def write_events(run_dir: Path, events):
    """Write events.jsonl from a list of (scope, type, payload) tuples or dicts."""
    run_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for ev in events:
        if isinstance(ev, dict):
            lines.append(json.dumps(ev))
            continue
        scope, etype, payload = ev
        lines.append(json.dumps({"ts": "2026-07-30T10:00:00Z", "scope": scope,
                                 "type": etype, "payload": payload}))
    (run_dir / "events.jsonl").write_text("\n".join(lines) + "\n")


# --- a stub run_metrics, so the metrics WIRING is tested independently of the
# --- sibling module's own suite (and works even if it is not deployed).

METRICS_DOC = {
    "schema_version": 2,
    "run_id": "run-normal",
    "safety": {"escalations": {"total": 2}, "autonomy_ratio": 0.75},
    "quality": {"integration": {"gate": "PASS"}},
    "performance": {"run_wall_clock_s": 1800},
}

SUMMARY_KEYS = ("run_id", "escalations", "autonomy_ratio", "integration_gate",
                "wall_clock_s")


def fake_run_metrics(doc=None, **overrides):
    """A stand-in exposing exactly the names dashboard_server calls.

    ``metrics_for_run_dir`` is the generation-routing entry point the server
    prefers for a live recompute; ``load_run_artifacts``/``compute_metrics`` are
    kept so the older-module degrade path stays testable."""
    document = dict(doc if doc is not None else METRICS_DOC)
    ns = SimpleNamespace(
        SCHEMA_VERSION=2,
        load_run_artifacts=lambda run_dir: {"run_dir": str(run_dir)},
        compute_metrics=lambda artifacts: dict(document),
        metrics_for_run_dir=lambda run_dir: dict(document),
        summary_row=lambda d: {
            "run_id": d.get("run_id"),
            "escalations": (d.get("safety", {}).get("escalations") or {}).get("total"),
            "autonomy_ratio": d.get("safety", {}).get("autonomy_ratio"),
            "integration_gate": (d.get("quality", {}).get("integration") or {}).get("gate"),
            "wall_clock_s": d.get("performance", {}).get("run_wall_clock_s"),
        },
    )
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


# --------------------------------------------------------------------------
# Fixture trees
# --------------------------------------------------------------------------

def build_v1_fixture(tmp: Path) -> Path:
    """A docs/spec-loop/ tree of PRE-v2 runs, exercising every v1 branch."""
    docs = tmp / "docs" / "spec-loop"

    # --- normal run: mixed complete + dependent pending (waves) ---
    write_dag_v1(docs / "run-normal", [
        slice_obj("s1", status="complete"),
        slice_obj("s2", deps=["s1"], status="pending"),       # runnable-pending
        slice_obj("s3", deps=["s2"], status="pending"),       # blocked-pending
    ])
    (docs / "run-normal" / "request.md").write_text(
        "# Request\n\nFirst meaningful line of the request.\nSecond line.\n"
    )
    (docs / "run-normal" / "decisions-log.md").write_text(
        "[intake] COUNCIL: ENDORSE_WITH_CONCERNS — folded scope concerns.\n"
        "[intake] DECISION: not a council line — must be ignored.\n"
        "[s1] IRON COUNCIL on plan: OBJECT — 3/5 object.\n"
        "- s1 DONE VERIFIED by controller: merge abc.\n"
        "[s2] line three\n"
    )
    (docs / "run-normal" / "slice-s1-report.md").write_text("done")
    (docs / "run-normal" / "runbook.md").write_text(
        "---\n"
        "schema_version: 1\n"
        "run_id: run-normal\n"
        "integration_gate: green\n"
        "slice_counts: { complete: 1, split: 0, remediation: 0 }\n"
        "publish: left-local\n"
        "---\n\n"
        "# RUNBOOK — run-normal\n\n"
        "## Executive Readout\n\n"
        "**What we set out to do.** Ship the thing.\n\n"
        "## 1. What Was Built\n\n"
        "table goes here\n"
    )

    # --- split run: split parent + its <parent>.N children ---
    write_dag_v1(docs / "run-split", [
        slice_obj("a", status="split"),                       # terminal, non-blocking
        slice_obj("a.1", deps=[], status="complete", depth=1, parent="a"),
        slice_obj("a.2", deps=["a.1"], status="pending", depth=1, parent="a"),
        # b depends on the SPLIT parent a -> a is terminal so b is NOT blocked
        slice_obj("b", deps=["a"], status="pending"),
    ])

    # --- escalation run: OPEN (escalation-gate) + ANSWERED forms ---
    write_dag_v1(docs / "run-esc", [
        slice_obj("s1", status="complete"),
        slice_obj("s2", deps=["s1"], status="pending"),       # OPEN -> awaiting-human
        slice_obj("s3", deps=["s1"], status="pending"),       # ANSWERED -> redispatch
    ])
    (docs / "run-esc" / "escalations.md").write_text(
        "# Escalations\n\n"
        "## [s2] something ambiguous   (status: OPEN)\n"
        "Answer:\n\n"
        "## [s3] resolved thing   (status: ANSWERED)\n"
        "Answer: do it this way\n\n"
        "## [intake] Iron Council objects: premise unclear   (status: OPEN)\n"
        "Answer:\n"
    )

    # --- corrupt run: deliberately broken dag.json -> unreadable ---
    (docs / "run-corrupt").mkdir(parents=True)
    (docs / "run-corrupt" / "dag.json").write_text('{ "base_ref": "alpha", "slices": [ {bad')

    return docs


def build_v2_fixture(tmp: Path) -> Path:
    """A docs/spec-loop/ tree of v2 runs covering the new derivations."""
    docs = tmp / "docs" / "spec-loop"

    # --- mid-run: wave 1 collected, wave 2 dispatched, s4 still to come ---
    run = docs / "run-mid"
    write_dag_v2(run, [
        slice_obj("s1", status="complete"),
        slice_obj("s2", status="pending"),                    # in flight (wave 2)
        slice_obj("s3", deps=["s1"], status="pending"),       # in flight (wave 2)
        slice_obj("s4", deps=["s3"], status="pending"),       # not dispatched
    ], waves=[
        wave(1, ["s1"], status="collected", workflow_run_id="wf_one"),
        wave(2, ["s2", "s3"], status="dispatched", workflow_run_id="wf_two"),
    ], shared_constraints=["do not break the CLI surface"])
    write_sidecar(run, "s1", status="DONE")
    write_events(run, [
        ("run", "run-created", {}),
        ("intake", "council-verdict", {"role": "skeptic", "verdict": "OBJECT",
                                       "summary": "premise unclear"}),
        ("intake", "council-verdict", {"role": "architect",
                                       "verdict": "ENDORSE_WITH_CONCERNS",
                                       "summary": "layering is fine"}),
        ("wave1", "wave-dispatched", {"index": 1}),
    ])
    (run / "request.md").write_text("# Request\n\nShip the v2 dashboard.\n")

    # --- outcomes run: one slice of each sidecar status ---
    run = docs / "run-outcomes"
    write_dag_v2(run, [
        slice_obj("d", status="pending"),      # sidecar DONE  -> merge-pending
        slice_obj("p", status="pending"),      # sidecar SPLIT -> split-pending
        slice_obj("e", status="pending"),      # sidecar ESCALATED + OPEN esc
        slice_obj("f", status="pending"),      # sidecar FAILED -> failed
        slice_obj("n", status="pending"),      # no sidecar -> runnable-pending
    ], waves=[wave(1, ["d", "p", "e", "f"], status="collected")])
    write_sidecar(run, "d", status="DONE")
    write_sidecar(run, "p", status="SPLIT")
    write_sidecar(run, "e", status="ESCALATED",
                  escalations=[escalation_record("e:ambiguity")])
    write_sidecar(run, "f", status="FAILED")
    write_events(run, [
        ("e", "escalation-opened", {"id": "e:ambiguity"}),
    ])

    return docs


# ==========================================================================
# v1 back-compat data layer
# ==========================================================================

class ScanRunsV1Tests(unittest.TestCase):
    """A pre-v2 run dir must still render by the v1 rules, so a repo holding both
    generations displays both."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.docs = build_v1_fixture(self.tmp)

    def tearDown(self):
        self.tmpdir.cleanup()

    def runs_by_id(self):
        return {r["run_id"]: r for r in ds.scan_runs(self.docs)}

    def wave_ids(self, run):
        return [w["slice_ids"] for w in run["waves"]]

    def test_v1_dag_is_reported_as_generation_one(self):
        self.assertEqual(self.runs_by_id()["run-normal"]["schema_version"], 1)

    def test_corrupt_dag_is_unreadable_and_others_survive(self):
        runs = self.runs_by_id()
        self.assertEqual(runs["run-corrupt"]["status"], "unreadable")
        for rid in ("run-normal", "run-split", "run-esc"):
            self.assertNotEqual(runs[rid].get("status"), "unreadable")
            self.assertIn("slices", runs[rid])

    def test_wave_derivation_normal(self):
        run = self.runs_by_id()["run-normal"]
        # s1 complete; s2 (deps s1) runnable in wave 1; s3 (deps s2) wave 2.
        self.assertEqual(self.wave_ids(run), [["s2"], ["s3"]])

    def test_v1_waves_are_all_projected_and_one_based(self):
        # A v1 run records nothing, so every wave row is a forecast — never a
        # claim that anything was dispatched. Indices are 1-based like v2's.
        run = self.runs_by_id()["run-normal"]
        self.assertEqual([w["status"] for w in run["waves"]],
                         ["projected", "projected"])
        self.assertEqual([w["index"] for w in run["waves"]], [1, 2])
        self.assertTrue(all(w["workflow_run_id"] is None for w in run["waves"]))

    def test_honest_labels_normal(self):
        labels = {s["id"]: s["label"] for s in self.runs_by_id()["run-normal"]["slices"]}
        self.assertEqual(labels["s1"], "complete")
        self.assertEqual(labels["s2"], "runnable-pending")
        self.assertEqual(labels["s3"], "blocked-pending")

    def test_v1_slices_carry_no_sidecar(self):
        for s in self.runs_by_id()["run-normal"]["slices"]:
            self.assertIsNone(s["sidecar"])

    def test_split_parent_terminal_does_not_block_dependents(self):
        run = self.runs_by_id()["run-split"]
        labels = {s["id"]: s["label"] for s in run["slices"]}
        self.assertEqual(labels["a"], "split")
        # b depends on split parent a, which is terminal -> b is runnable, not blocked.
        self.assertEqual(labels["b"], "runnable-pending")
        # a.2 depends on a.1 (complete) -> runnable; child convention preserved.
        self.assertEqual(labels["a.2"], "runnable-pending")
        child = next(s for s in run["slices"] if s["id"] == "a.2")
        self.assertEqual(child["depth"], 1)
        self.assertEqual(child["parent"], "a")
        # split parent must not appear in any wave (terminal).
        flat = [sid for w in run["waves"] for sid in w["slice_ids"]]
        self.assertNotIn("a", flat)
        self.assertIn("b", flat)

    def test_escalation_open_and_answered_labels(self):
        run = self.runs_by_id()["run-esc"]
        labels = {s["id"]: s["label"] for s in run["slices"]}
        self.assertEqual(labels["s2"], "awaiting-human")
        self.assertEqual(labels["s3"], "redispatch-pending")

    def test_v1_escalations_are_sourced_from_prose(self):
        run = self.runs_by_id()["run-esc"]
        self.assertEqual(run["escalations_source"], "prose")
        # Prose carries no escalation id and no trigger — reported as absent
        # rather than fabricated.
        for e in run["escalations"]:
            self.assertIsNone(e["id"])
            self.assertIsNone(e["trigger"])

    def test_filled_answer_overrides_open_header(self):
        # A filled-in Answer: line means ANSWERED even if the header still says
        # OPEN (a partial write) -> redispatch-pending, not awaiting-human.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v1(docs / "r", [
                slice_obj("s1", status="complete"),
                slice_obj("s2", deps=["s1"], status="pending"),
            ])
            (docs / "r" / "escalations.md").write_text(
                "## [s2] thing   (status: OPEN)\n- Answer: human said go ahead\n"
            )
            run = next(x for x in ds.scan_runs(docs) if x["run_id"] == "r")
            labels = {s["id"]: s["label"] for s in run["slices"]}
            self.assertEqual(labels["s2"], "redispatch-pending")
            # ...and it is no longer reported as an OPEN escalation.
            self.assertNotIn("s2", {e["token"] for e in run["open_escalations"]})

    def test_intake_open_escalation_attaches_to_no_slice(self):
        run = self.runs_by_id()["run-esc"]
        tokens = {e["token"] for e in run["open_escalations"]}
        self.assertIn("intake", tokens)
        self.assertIn("s2", tokens)
        # intake escalation is not a slice id.
        self.assertNotIn("intake", {s["id"] for s in run["slices"]})

    def test_missing_optional_artifacts_are_absent_not_errors(self):
        run = self.runs_by_id()["run-split"]
        self.assertEqual(run["request_excerpt"], "")
        self.assertEqual(run["decisions_tail"], [])
        for s in run["slices"]:
            self.assertFalse(s["has_report"])

    def test_report_presence_detected(self):
        reports = {s["id"]: s["has_report"]
                   for s in self.runs_by_id()["run-normal"]["slices"]}
        self.assertTrue(reports["s1"])
        self.assertFalse(reports["s2"])

    def test_runbook_presence_detected(self):
        runs = self.runs_by_id()
        self.assertTrue(runs["run-normal"]["has_runbook"])
        self.assertFalse(runs["run-split"]["has_runbook"])

    def test_v1_run_carries_no_v2_only_dag_fields(self):
        run = self.runs_by_id()["run-normal"]
        self.assertIsNone(run["mode"])
        self.assertEqual(run["shared_constraints"], [])

    # ---- stage derivation (cold-artifact only) -------------------------------

    def test_derive_stage_preflight_when_no_slices(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ds._derive_stage([], Path(d)), "preflight")

    def test_derive_stage_iron_council_when_decomposed_but_unstarted(self):
        with tempfile.TemporaryDirectory() as d:
            slices = [slice_obj("s1"), slice_obj("s2")]
            self.assertEqual(ds._derive_stage(slices, Path(d)), "iron-council")

    def test_derive_stage_execution_when_a_report_exists_but_not_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d)
            (run_dir / "slice-s1-report.md").write_text("done")
            slices = [slice_obj("s1"), slice_obj("s2")]
            self.assertEqual(ds._derive_stage(slices, run_dir), "execution")

    def test_derive_stage_final_review_when_all_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            slices = [slice_obj("s1", status="complete"),
                      slice_obj("s2", status="split")]
            self.assertEqual(ds._derive_stage(slices, Path(d)), "final-review")

    def test_derive_stage_started_flag_promotes_to_execution(self):
        # The v2 caller's own start signals (a recorded wave, a sidecar) reach the
        # shared derivation through `started`, with no artifact on disk.
        with tempfile.TemporaryDirectory() as d:
            slices = [slice_obj("s1"), slice_obj("s2")]
            self.assertEqual(ds._derive_stage(slices, Path(d), started=True),
                             "execution")

    def test_stage_field_on_scanned_runs(self):
        # run-normal: s1 complete, s2/s3 pending -> execution.
        self.assertEqual(self.runs_by_id()["run-normal"]["stage"], "execution")

    # ---- Iron Council findings (v1 prose scrape) -----------------------------

    def test_council_findings_parsed_with_verdicts(self):
        council = self.runs_by_id()["run-normal"]["council"]
        # Two council lines; the plain DECISION line and the DONE bullet are ignored.
        self.assertEqual(len(council), 2)
        self.assertEqual(council[0]["scope"], "intake")
        self.assertEqual(council[0]["verdict"], "ENDORSE_WITH_CONCERNS")
        self.assertEqual(council[1]["scope"], "s1")
        self.assertEqual(council[1]["verdict"], "OBJECT")

    def test_council_empty_when_no_decisions_log(self):
        self.assertEqual(self.runs_by_id()["run-split"]["council"], [])

    # ---- all escalations, with status ----------------------------------------

    def test_all_escalations_include_answered_with_status(self):
        escs = {e["token"]: e["status"]
                for e in self.runs_by_id()["run-esc"]["escalations"]}
        self.assertEqual(escs["s2"], "OPEN")
        self.assertEqual(escs["s3"], "ANSWERED")
        self.assertEqual(escs["intake"], "OPEN")

    # ---- runbook (final-review executive source) -----------------------------

    def test_runbook_front_matter_and_executive_readout_parsed(self):
        rb = self.runs_by_id()["run-normal"]["runbook"]
        self.assertIsNotNone(rb)
        self.assertEqual(rb["front_matter"]["integration_gate"], "green")
        self.assertEqual(rb["front_matter"]["publish"], "left-local")
        # inline {...} value kept raw
        self.assertIn("complete: 1", rb["front_matter"]["slice_counts"])
        # section body captured up to the next "## " heading (table excluded)
        self.assertIn("Ship the thing", rb["executive_readout"])
        self.assertNotIn("What Was Built", rb["executive_readout"])

    def test_runbook_is_none_when_absent(self):
        self.assertIsNone(self.runs_by_id()["run-split"]["runbook"])

    def test_runbook_without_front_matter_still_parses_its_readout(self):
        # The front-matter fences are optional prose, not a pinned grammar — a
        # runbook that opens straight into headings must still yield its readout.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v1(run_dir, [slice_obj("s1", status="complete")])
            (run_dir / "runbook.md").write_text(
                "# RUNBOOK\n\n## Executive Readout\n\nWe shipped it.\n"
            )
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["runbook"]["front_matter"], {})
            self.assertIn("We shipped it.", run["runbook"]["executive_readout"])
        # An entirely empty file yields empty front matter too, not a crash.
        self.assertEqual(ds._parse_front_matter(""), {})

    # ---- artifact inventory --------------------------------------------------

    def test_artifacts_lists_present_run_files(self):
        arts = self.runs_by_id()["run-normal"]["artifacts"]
        self.assertIn("dag.json", arts)
        self.assertIn("decisions-log.md", arts)
        self.assertIn("runbook.md", arts)
        self.assertIn("slice-s1-report.md", arts)
        self.assertEqual(arts, sorted(arts))

    def test_request_excerpt_skips_heading(self):
        self.assertEqual(self.runs_by_id()["run-normal"]["request_excerpt"],
                         "First meaningful line of the request.")

    def test_slices_not_a_list_is_unreadable_via_type_raise(self):
        # A dag.json that is valid JSON but whose "slices" is the WRONG TYPE (an
        # object, not a list) must degrade to unreadable — the explicit
        # `raise ValueError("slices is not a list")` path, distinct from the
        # broken-JSON path the corrupt-run fixture already covers.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            (docs / "run-badtype").mkdir(parents=True)
            (docs / "run-badtype" / "dag.json").write_text(
                json.dumps({"base_ref": "alpha", "slices": {"not": "a list"}})
            )
            write_dag_v1(docs / "run-ok", [slice_obj("s1")])
            runs = {r["run_id"]: r for r in ds.scan_runs(docs)}
            self.assertEqual(runs["run-badtype"]["status"], "unreadable")
            self.assertNotEqual(runs["run-ok"].get("status"), "unreadable")

    def test_dependency_cycle_yields_no_infinite_loop_and_omits_stuck_slices(self):
        # Two pending slices depending on each OTHER can never become ready, so the
        # wave derivation must break out (not loop forever) and honestly omit them
        # from every wave.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v1(docs / "r", [
                slice_obj("s1", status="complete"),
                slice_obj("x", deps=["y"]),                  # cycle: x<->y
                slice_obj("y", deps=["x"]),
                slice_obj("z", deps=["missing"]),            # dep never exists
            ])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            flat = [sid for w in run["waves"] for sid in w["slice_ids"]]
            self.assertNotIn("x", flat)
            self.assertNotIn("y", flat)
            self.assertNotIn("z", flat)
            labels = {s["id"]: s["label"] for s in run["slices"]}
            self.assertEqual(labels["x"], "blocked-pending")
            self.assertEqual(labels["z"], "blocked-pending")

    def test_escalation_header_without_close_bracket_is_ignored(self):
        # A `## [`-prefixed line with NO closing `]` is silently skipped: no crash,
        # no phantom escalation.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v1(docs / "r", [slice_obj("s1")])
            (docs / "r" / "escalations.md").write_text(
                "# Escalations\n\n## [unclosed header with no bracket\nAnswer:\n"
            )
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["open_escalations"], [])
            labels = {s["id"]: s["label"] for s in run["slices"]}
            self.assertEqual(labels["s1"], "runnable-pending")

    def test_escalation_header_no_status_marker_is_unknown_state(self):
        # A header with a bracket token but NEITHER a (status: ...) marker NOR a
        # filled Answer -> unknown. The slice is then neither awaiting-human nor
        # redispatch-pending; it derives from deps.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v1(docs / "r", [
                slice_obj("s1", status="complete"),
                slice_obj("s2", deps=["s1"]),
            ])
            (docs / "r" / "escalations.md").write_text(
                "# Escalations\n\n## [s2] a note with no status and no answer\nAnswer:\n"
            )
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertNotIn("s2", {e["token"] for e in run["open_escalations"]})
            labels = {s["id"]: s["label"] for s in run["slices"]}
            self.assertEqual(labels["s2"], "runnable-pending")


# ==========================================================================
# v2 data layer
# ==========================================================================

class ScanRunsV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.docs = build_v2_fixture(self.tmp)

    def tearDown(self):
        self.tmpdir.cleanup()

    def runs_by_id(self):
        return {r["run_id"]: r for r in ds.scan_runs(self.docs)}

    def test_v2_dag_is_reported_as_generation_two_with_its_fields(self):
        run = self.runs_by_id()["run-mid"]
        self.assertEqual(run["schema_version"], 2)
        self.assertEqual(run["mode"], "workflow")
        self.assertEqual(run["merge_mode"], "single-branch")
        self.assertEqual(run["shared_constraints"],
                         ["do not break the CLI surface"])

    def test_recorded_waves_are_reported_verbatim_with_journal_pointers(self):
        # The whole point of v2: what was dispatched is READ, not re-derived, so
        # the display can never disagree with what the controller actually did.
        waves = self.runs_by_id()["run-mid"]["waves"]
        self.assertEqual(waves[0], {"index": 1, "slice_ids": ["s1"],
                                    "workflow_run_id": "wf_one",
                                    "status": "collected"})
        self.assertEqual(waves[1], {"index": 2, "slice_ids": ["s2", "s3"],
                                    "workflow_run_id": "wf_two",
                                    "status": "dispatched"})

    def test_undispatched_work_is_projected_after_the_last_recorded_wave(self):
        # s4 was never dispatched, so it appears as a PROJECTED wave numbered
        # after the recorded ones — with no journal id, since none exists.
        waves = self.runs_by_id()["run-mid"]["waves"]
        self.assertEqual(len(waves), 3)
        self.assertEqual(waves[2]["index"], 3)
        self.assertEqual(waves[2]["status"], "projected")
        self.assertEqual(waves[2]["slice_ids"], ["s4"])
        self.assertIsNone(waves[2]["workflow_run_id"])

    def test_in_flight_slices_are_not_double_counted_in_the_projection(self):
        # s2/s3 sit in a DISPATCHED wave — that row already accounts for them, so
        # projecting them again would show the same work twice.
        waves = self.runs_by_id()["run-mid"]["waves"]
        projected = [sid for w in waves if w["status"] == "projected"
                     for sid in w["slice_ids"]]
        self.assertNotIn("s2", projected)
        self.assertNotIn("s3", projected)
        # ...but s4, which depends on the in-flight s3, is still forecast. A
        # projection answers "if the work underway lands, what runs next", so
        # dependents of in-flight work must chain off it rather than dropping out
        # of the wave view entirely.
        self.assertIn("s4", projected)

    def test_a_dependent_of_a_merge_pending_slice_is_still_projected(self):
        # A DONE slice awaiting its serial merge will become complete without
        # another wave, so its dependents belong in the forecast.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [
                slice_obj("a", status="pending"),          # sidecar DONE
                slice_obj("b", deps=["a"], status="pending"),
            ], waves=[wave(1, ["a"], status="collected")])
            write_sidecar(run_dir, "a", status="DONE")
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            projected = [sid for w in run["waves"] if w["status"] == "projected"
                         for sid in w["slice_ids"]]
            self.assertEqual(projected, ["b"])

    def test_a_dependent_of_a_failed_slice_is_honestly_left_out(self):
        # A FAILED slice will NOT clear on its own, so anything behind it is
        # genuinely blocked — forecasting it would imply progress that is not
        # coming without intervention.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [
                slice_obj("a", status="pending"),          # sidecar FAILED
                slice_obj("b", deps=["a"], status="pending"),
            ], waves=[wave(1, ["a"], status="collected")])
            write_sidecar(run_dir, "a", status="FAILED")
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            projected = [sid for w in run["waves"] if w["status"] == "projected"
                         for sid in w["slice_ids"]]
            self.assertEqual(projected, [])
            labels = {s["id"]: s["label"] for s in run["slices"]}
            self.assertEqual(labels["a"], "failed")
            self.assertEqual(labels["b"], "blocked-pending")

    def test_pending_slices_of_a_collected_wave_are_projected_again(self):
        # A slice dispatched in a COLLECTED wave that came back without
        # completing genuinely needs another wave, so it must be projected.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [
                slice_obj("s1", status="pending"),   # came back not complete
            ], waves=[wave(1, ["s1"], status="collected")])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            projected = [w for w in run["waves"] if w["status"] == "projected"]
            self.assertEqual(len(projected), 1)
            self.assertEqual(projected[0]["slice_ids"], ["s1"])
            self.assertEqual(projected[0]["index"], 2)

    def test_sidecar_outcomes_drive_the_v2_only_labels(self):
        labels = {s["id"]: s["label"]
                  for s in self.runs_by_id()["run-outcomes"]["slices"]}
        # dag.json still says pending for all five; the sidecar is what
        # distinguishes them.
        self.assertEqual(labels["d"], "merge-pending")     # DONE, awaiting merge
        self.assertEqual(labels["p"], "split-pending")     # SPLIT, awaiting ingest
        self.assertEqual(labels["e"], "awaiting-human")    # ESCALATED + OPEN esc
        self.assertEqual(labels["f"], "failed")            # FAILED
        self.assertEqual(labels["n"], "runnable-pending")  # no sidecar at all

    def test_a_controller_owed_write_is_never_projected_as_runnable(self):
        # merge-pending / split-pending / failed slices are waiting on a
        # controller write, not on a wave — projecting them would claim they can
        # run now, which is exactly the live claim this server must never make.
        run = self.runs_by_id()["run-outcomes"]
        projected = [sid for w in run["waves"] if w["status"] == "projected"
                     for sid in w["slice_ids"]]
        for sid in ("d", "p", "f"):
            self.assertNotIn(sid, projected)
        self.assertIn("n", projected)

    def test_dag_terminal_status_outranks_the_sidecar(self):
        # dag.json is the authority on run structure: once it says complete, that
        # is the label, whatever the sidecar last recorded.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1", status="complete")])
            write_sidecar(run_dir, "s1", status="FAILED")
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["slices"][0]["label"], "complete")

    def test_sidecar_view_is_a_bounded_allowlist(self):
        s1 = next(s for s in self.runs_by_id()["run-mid"]["slices"]
                  if s["id"] == "s1")
        sc = s1["sidecar"]
        self.assertEqual(sc["status"], "DONE")
        self.assertEqual(sc["wave"], 1)
        self.assertEqual(sc["critique"], {"verdict": "ENDORSE", "concerns": 0})
        self.assertEqual(sc["tests"], {"result": "pass", "scope": "full"})
        self.assertEqual(sc["quality"], {"status": "PASS", "detail": ""})
        # residual findings are counted, not carried as prose.
        self.assertEqual(sc["review"]["residual_count"], 1)
        self.assertNotIn("residual", sc["review"])
        # Fields NOT on the allowlist never reach the payload.
        for leaked in ("commits", "schema_version", "escalations", "id"):
            self.assertNotIn(leaked, sc)
        # The tests block's command/tree_sha are deliberately excluded.
        self.assertNotIn("command", sc["tests"])
        self.assertNotIn("tree_sha", sc["tests"])

    def test_sidecar_with_a_bogus_status_reports_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="TOTALLY-MADE-UP")
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["slices"][0]["sidecar"]["status"], "unknown")
            # An unknown outcome names no v2 label, so deps decide.
            self.assertEqual(run["slices"][0]["label"], "runnable-pending")

    def test_half_written_and_wrong_schema_sidecars_read_as_absent(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1"), slice_obj("s2")])
            (run_dir / "slice-s1-status.json").write_text('{"schema_version": 2, "st')
            (run_dir / "slice-s2-status.json").write_text(
                json.dumps({"schema_version": 1, "id": "s2", "status": "DONE"}))
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            by_id = {s["id"]: s for s in run["slices"]}
            # Both read as "no recorded outcome yet" — never a crash, never a
            # guessed status.
            self.assertIsNone(by_id["s1"]["sidecar"])
            self.assertIsNone(by_id["s2"]["sidecar"])
            self.assertEqual(by_id["s1"]["label"], "runnable-pending")

    def test_a_slice_with_no_id_is_skipped_and_never_drops_a_sibling_run(self):
        # A hand-edited or half-written dag.json can carry a slice with no id. It
        # cannot own a sidecar (there is no filename for it) and can never be
        # scheduled — but crucially it must not raise: the wave derivation runs
        # OUTSIDE _scan_one_run's tolerate-the-parse guard, so an unguarded
        # s["id"] there would fail the whole /api/runs request and take every
        # other run down with it.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [{"goal": "no id here", "status": "pending"},
                                   slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="DONE")
            write_dag_v2(docs / "healthy", [slice_obj("t1", status="complete")])
            runs = {r["run_id"]: r for r in ds.scan_runs(docs)}
            # The sibling run survived — that is the load-bearing assertion.
            self.assertEqual(set(runs), {"r", "healthy"})
            self.assertNotEqual(runs["healthy"].get("status"), "unreadable")
            broken = runs["r"]
            self.assertEqual(len(broken["slices"]), 2)
            self.assertIsNone(broken["slices"][0]["sidecar"])
            self.assertEqual(broken["slices"][1]["sidecar"]["status"], "DONE")
            # The id-less slice appears in no wave; the real one still projects.
            flat = [sid for w in broken["waves"] for sid in w["slice_ids"]]
            self.assertNotIn(None, flat)

    def test_wrongly_typed_sidecar_sub_blocks_degrade_to_none(self):
        # critique/tests/quality/review are objects by contract. A string or list
        # where one belongs must read as "no such block", not raise.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="DONE", critique="ENDORSE",
                          tests=["pass"], quality=None, review="all good")
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            sc = run["slices"][0]["sidecar"]
            self.assertIsNone(sc["critique"])
            self.assertIsNone(sc["tests"])
            self.assertIsNone(sc["quality"])
            self.assertIsNone(sc["review"])
            # The slice still labels off its (valid) status.
            self.assertEqual(run["slices"][0]["label"], "merge-pending")

    def test_a_non_list_residual_counts_as_unknown_not_zero(self):
        # residual is a list of findings; anything else means "we don't know how
        # many", which is not the same claim as "there were none".
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="DONE",
                          review={"confirmed": 1, "residual": "P2: something"})
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertIsNone(run["slices"][0]["sidecar"]["review"]["residual_count"])

    def test_v2_stage_is_execution_once_a_wave_is_recorded(self):
        # Nothing terminal and no report file, but a recorded wave means work has
        # been dispatched — a stronger, v2-only start signal.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [slice_obj("s1"), slice_obj("s2")],
                         waves=[wave(1, ["s1"], status="dispatched")])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["stage"], "execution")

    def test_v2_stage_is_iron_council_before_any_wave_or_sidecar(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [slice_obj("s1"), slice_obj("s2")])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["stage"], "iron-council")

    def test_v2_artifacts_list_events_and_sidecars(self):
        arts = self.runs_by_id()["run-outcomes"]["artifacts"]
        self.assertIn("events.jsonl", arts)
        self.assertIn("slice-d-status.json", arts)
        self.assertIn("slice-f-status.json", arts)

    def test_unknown_dag_enum_values_are_dropped_not_forwarded(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [slice_obj("s1")],
                         mode="turbo", merge_mode="whatever")
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertIsNone(run["mode"])
            self.assertIsNone(run["merge_mode"])

    def test_shared_constraints_of_the_wrong_type_degrade_to_empty(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [slice_obj("s1")],
                         shared_constraints={"not": "a list"})
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["shared_constraints"], [])

    def test_shared_constraints_are_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [slice_obj("s1")],
                         shared_constraints=[f"c{i}" for i in range(200)])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(len(run["shared_constraints"]), ds.MAX_CONSTRAINTS)


class ReadinessRuleDelegationTests(unittest.TestCase):
    """A v2 run's labels and waves must come from dag.py's readiness rule — the
    one the controller actually schedules with — not from a copy of it. The rules
    genuinely differ on split parents, so that difference is the proof."""

    def scan(self, build, run_id="r"):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        docs = Path(self._tmp.name) / "docs" / "spec-loop"
        build(docs)
        return {r["run_id"]: r for r in ds.scan_runs(docs)}[run_id]

    @staticmethod
    def _split_family(writer):
        """A split parent `a` whose children are NOT all done, plus `b` depending
        on the parent."""
        def build(docs):
            writer(docs / "r", [
                slice_obj("a", status="split"),
                slice_obj("a.1", status="complete", depth=1, parent="a"),
                slice_obj("a.2", status="pending", depth=1, parent="a"),
                slice_obj("b", deps=["a"], status="pending"),
            ])
        return build

    def test_v2_split_dep_resolves_through_children_not_the_parent_status(self):
        # dag.py: a dep on a `split` parent is satisfied only when ALL of its
        # children are satisfied. a.2 is still pending, so b is genuinely BLOCKED.
        run = self.scan(self._split_family(write_dag_v2))
        labels = {s["id"]: s["label"] for s in run["slices"]}
        self.assertEqual(run["readiness_rule"], "dag.py")
        self.assertEqual(labels["a"], "split")
        self.assertEqual(labels["a.2"], "runnable-pending")
        self.assertEqual(labels["b"], "blocked-pending")

    def test_v1_split_dep_stays_unconditionally_non_blocking(self):
        # The SAME graph under the v1 rules, where a `split` parent never blocks:
        # b is runnable. A pre-v2 run dir must keep rendering as it always did.
        run = self.scan(self._split_family(write_dag_v1))
        labels = {s["id"]: s["label"] for s in run["slices"]}
        self.assertEqual(run["readiness_rule"], "v1")
        self.assertEqual(labels["b"], "runnable-pending")

    def test_v2_split_dep_clears_once_every_child_is_done(self):
        def build(docs):
            write_dag_v2(docs / "r", [
                slice_obj("a", status="split"),
                slice_obj("a.1", status="complete", depth=1, parent="a"),
                slice_obj("a.2", status="complete", depth=1, parent="a"),
                slice_obj("b", deps=["a"], status="pending"),
            ])
        run = self.scan(build)
        labels = {s["id"]: s["label"] for s in run["slices"]}
        self.assertEqual(labels["b"], "runnable-pending")

    def test_v2_split_parent_with_no_ingested_children_still_blocks(self):
        # A SPLIT recorded in dag.json whose children have not been ingested can
        # never be satisfied, so its dependents are blocked rather than quietly
        # treated as runnable.
        def build(docs):
            write_dag_v2(docs / "r", [
                slice_obj("a", status="split"),      # no children at all
                slice_obj("b", deps=["a"], status="pending"),
            ])
        run = self.scan(build)
        labels = {s["id"]: s["label"] for s in run["slices"]}
        self.assertEqual(labels["b"], "blocked-pending")
        # ...and nothing is forecast, because nothing can run.
        self.assertEqual([w for w in run["waves"] if w["status"] == "projected"], [])

    def test_the_projection_numbering_comes_from_dag_pys_own_index(self):
        def build(docs):
            write_dag_v2(docs / "r", [
                slice_obj("s1", status="complete"),
                slice_obj("s2", status="pending"),
                slice_obj("s3", deps=["s2"], status="pending"),
            ], waves=[wave(4, ["s1"], status="collected")])
        run = self.scan(build)
        self.assertEqual([w["index"] for w in run["waves"]], [4, 5, 6])
        self.assertEqual([w["slice_ids"] for w in run["waves"]],
                         [["s1"], ["s2"], ["s3"]])

    def test_a_v2_run_without_dag_py_keeps_the_SAME_answer_via_the_local_mirror(self):
        # The tolerant-import contract, with the sharp edge state-scripts flagged:
        # a stale image must not answer a DIFFERENT question. The local mirror
        # reimplements dag.py's rule (recursive split resolution included), so a
        # v2 run gets the same readiness answer either way — only the provenance
        # differs. Falling back to v1's rule here would reintroduce exactly the
        # divergence this port exists to remove.
        build = self._split_family(write_dag_v2)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        docs = Path(self._tmp.name) / "docs" / "spec-loop"
        build(docs)

        delegated = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
        with mock.patch.object(ds, "dag", None):
            mirrored = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")

        self.assertEqual(delegated["readiness_rule"], "dag.py")
        self.assertEqual(mirrored["readiness_rule"], "v2-fallback")
        # The ANSWER is identical: b is blocked because a's children are not all done.
        self.assertEqual({s["id"]: s["label"] for s in mirrored["slices"]},
                         {s["id"]: s["label"] for s in delegated["slices"]})
        self.assertEqual(mirrored["slices"][3]["label"], "blocked-pending")
        # ...and so is the wave composition.
        self.assertEqual(mirrored["waves"], delegated["waves"])
        self.assertEqual(mirrored["schema_version"], 2)

    def test_the_mirror_matches_dag_py_across_a_range_of_graph_shapes(self):
        # One shape could match by luck; these cover the cases the two rules could
        # plausibly disagree on — nested splits, a childless split, a diamond, a
        # cycle, and a dep on a slice that does not exist.
        shapes = {
            "nested-split": [
                slice_obj("a", status="split"),
                slice_obj("a.1", status="split", depth=1, parent="a"),
                slice_obj("a.1.1", status="complete", depth=2, parent="a.1"),
                slice_obj("a.1.2", status="pending", depth=2, parent="a.1"),
                slice_obj("a.2", status="complete", depth=1, parent="a"),
                slice_obj("b", deps=["a"], status="pending"),
            ],
            "childless-split": [
                slice_obj("a", status="split"),
                slice_obj("b", deps=["a"], status="pending"),
            ],
            "diamond": [
                slice_obj("a", status="complete"),
                slice_obj("b", deps=["a"], status="pending"),
                slice_obj("c", deps=["a"], status="pending"),
                slice_obj("d", deps=["b", "c"], status="pending"),
            ],
            "cycle": [
                slice_obj("x", deps=["y"], status="pending"),
                slice_obj("y", deps=["x"], status="pending"),
            ],
            "missing-dep": [
                slice_obj("a", deps=["nope"], status="pending"),
            ],
        }
        for name, slices in shapes.items():
            with self.subTest(shape=name):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                docs = Path(tmp.name) / "docs" / "spec-loop"
                write_dag_v2(docs / "r", slices)
                delegated = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
                with mock.patch.object(ds, "dag", None):
                    mirrored = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
                self.assertEqual(
                    {s["id"]: s["label"] for s in mirrored["slices"]},
                    {s["id"]: s["label"] for s in delegated["slices"]},
                    f"{name}: mirror disagrees with dag.py on labels")
                self.assertEqual(
                    [w["slice_ids"] for w in mirrored["waves"]],
                    [w["slice_ids"] for w in delegated["waves"]],
                    f"{name}: mirror disagrees with dag.py on waves")

    def test_a_v1_run_dir_is_unaffected_by_dag_pys_absence(self):
        # v1 runs never delegated, so their rendering is identical either way.
        build = self._split_family(write_dag_v1)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        docs = Path(self._tmp.name) / "docs" / "spec-loop"
        build(docs)
        with_dag = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
        with mock.patch.object(ds, "dag", None):
            without = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
        self.assertEqual(with_dag["readiness_rule"], "v1")
        self.assertEqual(without["readiness_rule"], "v1")
        self.assertEqual(with_dag["waves"], without["waves"])

    def test_the_fallback_projection_still_honors_in_flight_and_failed(self):
        # The local fallback must keep the same honesty properties as the
        # delegated path: in-flight work is not double-counted, a failed slice is
        # not forecast, and its dependents stay out of the forecast.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        docs = Path(self._tmp.name) / "docs" / "spec-loop"
        run_dir = docs / "r"
        write_dag_v2(run_dir, [
            slice_obj("f", status="pending"),               # sidecar FAILED
            slice_obj("g", deps=["f"], status="pending"),   # behind the failure
            slice_obj("h", status="pending"),               # in flight
            slice_obj("i", deps=["h"], status="pending"),   # behind the in-flight
        ], waves=[wave(1, ["f"], status="collected"),
                  wave(2, ["h"], status="dispatched")])
        write_sidecar(run_dir, "f", status="FAILED")
        with mock.patch.object(ds, "dag", None):
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
        projected = [sid for w in run["waves"] if w["status"] == "projected"
                     for sid in w["slice_ids"]]
        self.assertNotIn("f", projected)   # failed: not forecast
        self.assertNotIn("g", projected)   # behind a failure: not forecast
        self.assertNotIn("h", projected)   # in flight: already accounted for
        self.assertIn("i", projected)      # chains off the in-flight h


class RecordedWaveToleranceTests(unittest.TestCase):
    """A half-written or hand-edited waves[] must degrade, never crash."""

    def scan(self, waves):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [slice_obj("s1", status="complete")],
                         waves=waves)
            return next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")

    def test_non_list_waves_yields_no_recorded_waves(self):
        run = self.scan({"not": "a list"})
        self.assertEqual(run["waves"], [])

    def test_non_dict_entries_are_skipped(self):
        run = self.scan(["oops", 42, wave(1, ["s1"])])
        self.assertEqual(len(run["waves"]), 1)
        self.assertEqual(run["waves"][0]["slice_ids"], ["s1"])

    def test_missing_index_falls_back_to_the_one_based_position(self):
        run = self.scan([{"slice_ids": ["s1"], "status": "collected"},
                         {"slice_ids": [], "status": "collected"}])
        self.assertEqual([w["index"] for w in run["waves"]], [1, 2])

    def test_a_boolean_index_is_not_mistaken_for_an_int(self):
        # bool is an int subclass in Python, so True would otherwise become
        # "Wave True" in the UI.
        run = self.scan([{"index": True, "slice_ids": ["s1"]}])
        self.assertEqual(run["waves"][0]["index"], 1)

    def test_status_outside_the_contract_reports_unknown(self):
        run = self.scan([{"index": 1, "slice_ids": ["s1"], "status": "running"}])
        self.assertEqual(run["waves"][0]["status"], "unknown")

    def test_absent_slice_ids_yields_an_empty_membership(self):
        run = self.scan([{"index": 1, "status": "collected"}])
        self.assertEqual(run["waves"][0]["slice_ids"], [])

    def test_recorded_waves_are_bounded(self):
        run = self.scan([wave(i, []) for i in range(1, ds.MAX_WAVES + 50)])
        self.assertEqual(len(run["waves"]), ds.MAX_WAVES)

    def test_projection_numbering_continues_past_the_highest_recorded_index(self):
        # Numbering follows the MAX recorded index, not the wave count, so a
        # resumed run with a gap still numbers its forecast after its history.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [
                slice_obj("s1", status="complete"),
                slice_obj("s2", status="pending"),
            ], waves=[wave(7, ["s1"], status="collected")])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual([w["index"] for w in run["waves"]], [7, 8])


# ==========================================================================
# Escalations: events.jsonl primary, sidecars for detail, prose as fallback
# ==========================================================================

class EscalationSourceTests(unittest.TestCase):
    def scan(self, build):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        docs = Path(self._tmp.name) / "docs" / "spec-loop"
        run_dir = docs / "r"
        build(run_dir)
        return next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")

    def test_opened_without_an_answer_is_open(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1", status="complete"),
                                   slice_obj("s2", deps=["s1"])])
            write_sidecar(run_dir, "s2", status="ESCALATED",
                          escalations=[escalation_record("s2:review-block",
                                                         trigger="review-block")])
            write_events(run_dir, [("s2", "escalation-opened",
                                    {"id": "s2:review-block"})])
        run = self.scan(build)
        self.assertEqual(run["escalations_source"], "events")
        self.assertEqual([e["status"] for e in run["escalations"]], ["OPEN"])
        self.assertEqual(run["escalations"][0]["trigger"], "review-block")
        labels = {s["id"]: s["label"] for s in run["slices"]}
        self.assertEqual(labels["s2"], "awaiting-human")

    def test_a_later_answer_for_the_same_id_closes_it(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1", status="complete"),
                                   slice_obj("s2", deps=["s1"])])
            write_sidecar(run_dir, "s2", status="ESCALATED",
                          escalations=[escalation_record("s2:ambiguity")])
            write_events(run_dir, [
                ("s2", "escalation-opened", {"id": "s2:ambiguity"}),
                ("s2", "escalation-answered", {"id": "s2:ambiguity"}),
            ])
        run = self.scan(build)
        self.assertEqual([e["status"] for e in run["escalations"]], ["ANSWERED"])
        self.assertEqual(run["open_escalations"], [])
        labels = {s["id"]: s["label"] for s in run["slices"]}
        self.assertEqual(labels["s2"], "redispatch-pending")

    def test_events_override_a_stale_sidecar_status(self):
        # The sidecar is a snapshot taken when its wave was collected; the answer
        # is written afterwards. The events log therefore wins.
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="ESCALATED",
                          escalations=[escalation_record("s1:ambiguity",
                                                         status="OPEN")])
            write_events(run_dir, [("s1", "escalation-answered",
                                    {"id": "s1:ambiguity"})])
        run = self.scan(build)
        self.assertEqual(run["escalations"][0]["status"], "ANSWERED")
        # ...and the title still comes from the sidecar's full record.
        self.assertEqual(run["escalations"][0]["title"], "needs a call")

    def test_an_answered_then_reopened_id_ends_open(self):
        # Append-only log: the LAST transition is the truth.
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [
                ("s1", "escalation-opened", {"id": "s1:x"}),
                ("s1", "escalation-answered", {"id": "s1:x"}),
                ("s1", "escalation-opened", {"id": "s1:x"}),
            ])
        run = self.scan(build)
        self.assertEqual(run["escalations"][0]["status"], "OPEN")

    def test_an_id_known_only_to_the_events_log_is_carried_honestly(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [("s1", "escalation-opened",
                                    {"id": "s1:budget-exhausted:2"})])
        run = self.scan(build)
        e = run["escalations"][0]
        self.assertEqual(e["id"], "s1:budget-exhausted:2")
        self.assertEqual(e["token"], "s1")
        self.assertEqual(e["status"], "OPEN")
        # No sidecar record exists, so there is no title to show — reported as
        # empty rather than invented. The trigger, though, is encoded in the id
        # itself by contract, so that much is real.
        self.assertEqual(e["title"], "")
        self.assertEqual(e["trigger"], "budget-exhausted")

    def test_a_malformed_id_yields_no_made_up_trigger(self):
        # The id's second segment is only accepted when it is one of the
        # contract's six triggers, so a hand-edited id cannot surface garbage.
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [
                ("s1", "escalation-opened", {"id": "s1:not-a-real-trigger"}),
                ("s2", "escalation-opened", {"id": "noseparator"}),
            ])
        run = self.scan(build)
        self.assertEqual([e["trigger"] for e in run["escalations"]], [None, None])

    def test_a_record_trigger_outside_the_contract_falls_back_to_the_id(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="ESCALATED",
                          escalations=[escalation_record("s1:review-block",
                                                         trigger="made-up")])
        run = self.scan(build)
        self.assertEqual(run["escalations"][0]["trigger"], "review-block")

    def test_nested_and_named_payload_id_forms_are_both_accepted(self):
        # v2 pins the EscalationRecord but not how an event wraps it.
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [
                ("s1", "escalation-opened",
                 {"escalation": {"id": "s1:nested", "title": "x"}}),
                ("s2", "escalation-opened", {"escalation_id": "s2:named"}),
            ])
        run = self.scan(build)
        self.assertEqual({e["id"] for e in run["escalations"]},
                         {"s1:nested", "s2:named"})

    def test_an_escalation_event_naming_no_id_changes_nothing(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [("s1", "escalation-opened", {"note": "oops"})])
        run = self.scan(build)
        self.assertEqual(run["escalations"], [])
        self.assertEqual(run["escalations_source"], "events")

    def test_intake_escalation_joins_no_slice(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [("intake", "escalation-opened",
                                    {"id": "intake:council-objection"})])
        run = self.scan(build)
        self.assertEqual(run["open_escalations"][0]["token"], "intake")
        # The intake token must not make a slice look like it is awaiting a human.
        self.assertEqual(run["slices"][0]["label"], "runnable-pending")

    def test_sidecar_records_alone_are_used_when_there_is_no_events_log(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="ESCALATED",
                          escalations=[escalation_record("s1:ambiguity")])
        run = self.scan(build)
        self.assertEqual(run["escalations_source"], "sidecars")
        self.assertEqual(run["escalations"][0]["status"], "OPEN")
        self.assertEqual(run["slices"][0]["label"], "awaiting-human")

    def test_v2_falls_back_to_prose_when_neither_events_nor_records_exist(self):
        # An early-stage v2 run whose escalations.md exists before any wave has
        # been collected must still report honestly.
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1", status="complete"),
                                   slice_obj("s2", deps=["s1"])])
            (run_dir / "escalations.md").write_text(
                "## [s2] ambiguous thing   (status: OPEN)\nAnswer:\n")
        run = self.scan(build)
        self.assertEqual(run["escalations_source"], "prose")
        self.assertEqual(run["slices"][1]["label"], "awaiting-human")

    def test_escalated_sidecar_with_no_locatable_record_still_awaits_a_human(self):
        # It escalated but nothing resolves it either way: surface it as owing a
        # human rather than quietly calling it runnable.
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="ESCALATED")
            write_events(run_dir, [("run", "run-created", {})])
        run = self.scan(build)
        self.assertEqual(run["escalations"], [])
        self.assertEqual(run["slices"][0]["label"], "awaiting-human")

    def test_a_record_without_an_id_is_skipped(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="ESCALATED",
                          escalations=[{"trigger": "ambiguity", "title": "no id"}])
        run = self.scan(build)
        self.assertEqual(run["escalations"], [])

    def test_records_that_are_not_objects_or_carry_a_bad_id_are_skipped(self):
        # The escalations[] array is a list of objects by contract; a string, a
        # null, or an object whose id is the wrong type or empty must be dropped
        # rather than crash the run or become a phantom escalation.
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="ESCALATED", escalations=[
                "just a string",
                None,
                42,
                {"id": 7, "title": "numeric id"},
                {"id": "", "title": "empty id"},
                escalation_record("s1:ambiguity"),      # the one good record
            ])
        run = self.scan(build)
        self.assertEqual([e["id"] for e in run["escalations"]], ["s1:ambiguity"])

    def test_a_non_list_escalations_field_is_ignored(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="ESCALATED",
                          escalations="not a list")
        run = self.scan(build)
        self.assertEqual(run["escalations"], [])
        # The sidecar itself still parsed, so the label still reflects ESCALATED.
        self.assertEqual(run["slices"][0]["label"], "awaiting-human")

    def test_a_record_status_outside_the_contract_reports_unknown(self):
        def build(run_dir):
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_sidecar(run_dir, "s1", status="ESCALATED",
                          escalations=[escalation_record("s1:x", status="MAYBE")])
        run = self.scan(build)
        self.assertEqual(run["escalations"][0]["status"], "unknown")
        # unknown is neither OPEN nor ANSWERED, so it is not reported as open.
        self.assertEqual(run["open_escalations"], [])


class EventsLogToleranceTests(unittest.TestCase):
    """events.jsonl is a LIVE append-only log: a partial last line is its normal
    state, not an error."""

    def _iter(self, text):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d)
            (run_dir / "events.jsonl").write_text(text)
            return list(ds._iter_events(run_dir))

    def test_a_half_written_final_line_is_skipped_not_fatal(self):
        text = json.dumps({"type": "a"}) + "\n" + '{"type": "b", "pay'
        self.assertEqual([e["type"] for e in self._iter(text)], ["a"])

    def test_blank_lines_and_non_object_lines_are_skipped(self):
        text = "\n".join([json.dumps({"type": "a"}), "", "  ", "[1,2,3]",
                          '"a string"', json.dumps({"type": "b"})])
        self.assertEqual([e["type"] for e in self._iter(text)], ["a", "b"])

    def test_absent_log_yields_nothing_and_is_not_present(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(list(ds._iter_events(Path(d))), [])
            self.assertFalse(ds._has_events(Path(d)))

    def test_a_log_over_the_byte_cap_is_read_from_its_TAIL(self):
        # For a growing log the tail holds the latest transitions, so capping from
        # the head would read the wrong end. The possibly-partial first line of a
        # truncated read is dropped.
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d)
            filler = json.dumps({"ts": "t", "scope": "s", "type": "agent-dispatch",
                                 "payload": {"pad": "x" * 200}})
            last = json.dumps({"ts": "t", "scope": "s1", "type": "escalation-opened",
                               "payload": {"id": "s1:late"}})
            lines = [filler] * (ds.MAX_FILE_BYTES // len(filler) + 50) + [last]
            (run_dir / "events.jsonl").write_text("\n".join(lines) + "\n")
            self.assertGreater(os.path.getsize(run_dir / "events.jsonl"),
                               ds.MAX_FILE_BYTES)
            events = list(ds._iter_events(run_dir))
            # The newest event survived the cap — that is the whole point.
            self.assertEqual(events[-1]["payload"]["id"], "s1:late")
            statuses = ds._escalation_event_statuses(run_dir)
            self.assertEqual(statuses, {"s1:late": "OPEN"})


# ==========================================================================
# Iron Council: council-verdict events, prose as fallback
# ==========================================================================

class CouncilSourceTests(unittest.TestCase):
    def test_v2_reads_verdicts_from_council_verdict_events(self):
        with tempfile.TemporaryDirectory() as d:
            docs = build_v2_fixture(Path(d))
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "run-mid")
            council = run["council"]
            self.assertEqual(len(council), 2)
            self.assertEqual(council[0]["scope"], "intake")
            self.assertEqual(council[0]["verdict"], "OBJECT")
            # The role is the useful part — the council is five reviewers.
            self.assertIn("[skeptic]", council[0]["summary"])
            self.assertIn("premise unclear", council[0]["summary"])
            self.assertEqual(council[1]["verdict"], "ENDORSE_WITH_CONCERNS")

    def test_ewc_is_matched_before_plain_endorse(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [("s1", "council-verdict",
                                    {"verdict": "endorse_with_concerns"})])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["council"][0]["verdict"],
                             "ENDORSE_WITH_CONCERNS")

    def test_a_rationale_key_serves_as_the_summary(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [("s1", "council-verdict",
                                    {"verdict": "OBJECT",
                                     "rationale": "scope is unbounded"})])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["council"][0]["summary"], "scope is unbounded")

    def test_an_unrecognized_verdict_reports_empty_not_a_guess(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [("s1", "council-verdict", {"verdict": "meh"})])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["council"][0]["verdict"], "")

    def test_council_from_events_is_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [("s1", "council-verdict", {"verdict": "ENDORSE"})]
                         * (ds.COUNCIL_MAX + 20))
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(len(run["council"]), ds.COUNCIL_MAX)

    def test_a_long_summary_is_capped(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1")])
            write_events(run_dir, [("s1", "council-verdict",
                                    {"verdict": "OBJECT", "summary": "x" * 5000})])
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertLessEqual(len(run["council"][0]["summary"]),
                                 ds.COUNCIL_SUMMARY_CHARS)

    def test_the_prose_scrape_is_bounded_too(self):
        # The v1 fallback path has its own COUNCIL_MAX break.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v1(run_dir, [slice_obj("s1")])
            (run_dir / "decisions-log.md").write_text(
                "[intake] COUNCIL: ENDORSE — fine.\n" * (ds.COUNCIL_MAX + 20))
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(len(run["council"]), ds.COUNCIL_MAX)

    def test_v2_without_an_events_log_falls_back_to_the_prose_scrape(self):
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            run_dir = docs / "r"
            write_dag_v2(run_dir, [slice_obj("s1")])
            (run_dir / "decisions-log.md").write_text(
                "[intake] COUNCIL: OBJECT — premise unclear.\n")
            run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "r")
            self.assertEqual(run["council"][0]["scope"], "intake")
            self.assertEqual(run["council"][0]["verdict"], "OBJECT")


# ==========================================================================
# Mixed-generation repo
# ==========================================================================

class MixedGenerationRepoTests(unittest.TestCase):
    """One docs/spec-loop holding both a v1 and a v2 run must display both, each
    by its own rules, with no cross-contamination."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.docs = self.tmp / "docs" / "spec-loop"

        # A v1 run: no schema_version, prose escalations, derived waves only.
        write_dag_v1(self.docs / "old-run", [
            slice_obj("s1", status="complete"),
            slice_obj("s2", deps=["s1"]),
        ])
        (self.docs / "old-run" / "escalations.md").write_text(
            "## [s2] legacy question   (status: OPEN)\nAnswer:\n")
        (self.docs / "old-run" / "decisions-log.md").write_text(
            "[intake] COUNCIL: ENDORSE — fine.\n")

        # A v2 run: recorded waves, sidecars, events.
        new_run = self.docs / "new-run"
        write_dag_v2(new_run, [
            slice_obj("t1", status="complete"),
            slice_obj("t2", deps=["t1"]),
        ], waves=[wave(1, ["t1"], status="collected", workflow_run_id="wf_x")])
        write_sidecar(new_run, "t1", status="DONE")
        write_events(new_run, [
            ("t2", "escalation-opened", {"id": "t2:material-assumption"}),
            ("intake", "council-verdict", {"verdict": "ENDORSE", "role": "guardian"}),
        ])

        # And a corrupt run alongside, to prove neither generation is dropped.
        (self.docs / "broken").mkdir(parents=True)
        (self.docs / "broken" / "dag.json").write_text("{ nope")

    def tearDown(self):
        self.tmpdir.cleanup()

    def runs(self):
        return {r["run_id"]: r for r in ds.scan_runs(self.docs)}

    def test_both_generations_and_the_corrupt_run_all_appear(self):
        runs = self.runs()
        self.assertEqual(set(runs), {"old-run", "new-run", "broken"})
        self.assertEqual(runs["broken"]["status"], "unreadable")

    def test_each_run_reports_its_own_generation(self):
        runs = self.runs()
        self.assertEqual(runs["old-run"]["schema_version"], 1)
        self.assertEqual(runs["new-run"]["schema_version"], 2)

    def test_each_run_reports_its_own_escalation_source(self):
        runs = self.runs()
        self.assertEqual(runs["old-run"]["escalations_source"], "prose")
        self.assertEqual(runs["new-run"]["escalations_source"], "events")

    def test_the_v1_run_gets_projected_waves_and_the_v2_run_its_recorded_one(self):
        runs = self.runs()
        self.assertEqual([w["status"] for w in runs["old-run"]["waves"]],
                         ["projected"])
        v2_waves = runs["new-run"]["waves"]
        self.assertEqual(v2_waves[0]["status"], "collected")
        self.assertEqual(v2_waves[0]["workflow_run_id"], "wf_x")

    def test_only_the_v2_run_carries_sidecars(self):
        runs = self.runs()
        self.assertTrue(all(s["sidecar"] is None
                            for s in runs["old-run"]["slices"]))
        t1 = next(s for s in runs["new-run"]["slices"] if s["id"] == "t1")
        self.assertEqual(t1["sidecar"]["status"], "DONE")

    def test_both_runs_reach_awaiting_human_through_their_own_channel(self):
        runs = self.runs()
        old = {s["id"]: s["label"] for s in runs["old-run"]["slices"]}
        new = {s["id"]: s["label"] for s in runs["new-run"]["slices"]}
        self.assertEqual(old["s2"], "awaiting-human")   # via escalations.md
        self.assertEqual(new["t2"], "awaiting-human")   # via events.jsonl

    def test_the_payload_shape_is_identical_across_generations(self):
        # One client renders both, so both must carry the same keys.
        runs = self.runs()
        self.assertEqual(set(runs["old-run"]), set(runs["new-run"]))
        for run in (runs["old-run"], runs["new-run"]):
            for s in run["slices"]:
                self.assertEqual(
                    {"label", "has_report", "sidecar"} - set(s), set())


# ==========================================================================
# Metrics wiring (against a stub, so it is independent of run_metrics' own suite)
# ==========================================================================

class MetricsWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.docs = self.tmp / "docs" / "spec-loop"
        self.run_dir = self.docs / "r"
        write_dag_v2(self.run_dir, [slice_obj("s1", status="complete")])

    def tearDown(self):
        self.tmpdir.cleanup()

    def scan(self, fake):
        with mock.patch.object(ds, "run_metrics", fake):
            return next(r for r in ds.scan_runs(self.docs) if r["run_id"] == "r")

    def test_live_recompute_when_there_is_no_committed_file(self):
        run = self.scan(fake_run_metrics())
        self.assertEqual(run["metrics_source"], "live")
        self.assertEqual(run["metrics"]["autonomy_ratio"], 0.75)

    def test_a_live_recompute_routes_through_metrics_for_run_dir(self):
        # load_run_artifacts + compute_metrics reads only the v2 channels, so
        # pointing that pair at a v1 run dir yields an all-null row. This server
        # aggregates across every repo the user launches from and WILL meet v1
        # dirs, so it must use the generation-routing entry point instead —
        # otherwise it reports "no data" about a run that has data.
        called = []
        fake = fake_run_metrics()
        fake.metrics_for_run_dir = lambda run_dir: (called.append(("router", str(run_dir)))
                                                    or dict(METRICS_DOC))
        fake.compute_metrics = lambda artifacts: (called.append(("v2only", None))
                                                  or dict(METRICS_DOC))
        run = self.scan(fake)
        self.assertEqual(run["metrics_source"], "live")
        self.assertEqual([c[0] for c in called], ["router"])
        self.assertNotIn("v2only", [c[0] for c in called])

    def test_an_older_module_without_the_router_degrades_rather_than_losing_metrics(self):
        # A run_metrics predating metrics_for_run_dir should still produce metrics
        # via the v2-only pair — correct for v2 runs, null for v1 ones, which is
        # the best such a module can honestly offer. Never "unavailable".
        older = fake_run_metrics()
        del older.metrics_for_run_dir
        run = self.scan(older)
        self.assertEqual(run["metrics_source"], "live")
        self.assertEqual(run["metrics"]["autonomy_ratio"], 0.75)

    def test_a_truncated_event_log_is_surfaced_as_a_caveat(self):
        # events.jsonl is unbounded; counts computed from part of it UNDERSTATE.
        # A silently low number reads as fact, so the payload must say so.
        doc = dict(METRICS_DOC)
        doc["sources"] = {"events_truncated": True}
        self.assertTrue(self.scan(fake_run_metrics(doc))["metrics_truncated"])

    def test_an_untruncated_or_shapeless_document_reports_no_caveat(self):
        self.assertFalse(self.scan(fake_run_metrics())["metrics_truncated"])
        doc = dict(METRICS_DOC)
        doc["sources"] = {"events_truncated": False}
        self.assertFalse(self.scan(fake_run_metrics(doc))["metrics_truncated"])
        doc["sources"] = "not a dict"
        self.assertFalse(self.scan(fake_run_metrics(doc))["metrics_truncated"])

    def test_committed_file_is_preferred_over_a_live_recompute(self):
        doc = dict(METRICS_DOC)
        doc["safety"] = {"escalations": {"total": 9}, "autonomy_ratio": 0.4242}
        (self.run_dir / "metrics.json").write_text(json.dumps(doc))
        run = self.scan(fake_run_metrics())
        self.assertEqual(run["metrics_source"], "file")
        self.assertEqual(run["metrics"]["autonomy_ratio"], 0.4242)

    def test_malformed_committed_file_falls_back_to_live(self):
        (self.run_dir / "metrics.json").write_text("{{{ not json")
        run = self.scan(fake_run_metrics())
        self.assertEqual(run["metrics_source"], "live")
        self.assertIsNotNone(run["metrics"])

    def test_wrong_schema_version_falls_back_to_live(self):
        (self.run_dir / "metrics.json").write_text(
            json.dumps({"schema_version": 999}))
        self.assertEqual(self.scan(fake_run_metrics())["metrics_source"], "live")

    def test_metrics_json_participates_in_artifacts_and_the_run_etag(self):
        run = self.scan(fake_run_metrics())
        self.assertNotIn("metrics.json", run["artifacts"])
        before = ds._run_etag(self.run_dir)
        (self.run_dir / "metrics.json").write_text(json.dumps(METRICS_DOC))
        self.assertIn("metrics.json", self.scan(fake_run_metrics())["artifacts"])
        self.assertNotEqual(before, ds._run_etag(self.run_dir))

    def test_metrics_unavailable_when_the_module_is_not_deployed(self):
        # The tolerant-import contract: a stale image without run_metrics.py must
        # still serve runs, with metrics honestly null.
        run = self.scan(None)
        self.assertIsNone(run["metrics"])
        self.assertIsNone(run["metrics_source"])

    def test_an_api_skew_is_reported_as_unavailable_not_a_crash(self):
        # A run_metrics offering NEITHER live entry point (version skew between the
        # server and the metrics module) must degrade this one panel, not the run.
        broken = fake_run_metrics()
        del broken.metrics_for_run_dir
        del broken.compute_metrics
        run = self.scan(broken)
        self.assertIsNone(run["metrics"])
        self.assertEqual(run["metrics_source"], "unavailable")
        # The rest of the run still rendered.
        self.assertEqual(run["slices"][0]["label"], "complete")

    def test_a_missing_summary_row_is_also_unavailable_not_a_crash(self):
        # summary_row sits inside the same guard as compute_metrics — a module
        # that answers one but not the other must not take down the scan.
        broken = fake_run_metrics()
        del broken.summary_row
        run = self.scan(broken)
        self.assertIsNone(run["metrics"])
        self.assertEqual(run["metrics_source"], "unavailable")
        self.assertEqual(run["slices"][0]["label"], "complete")

    def test_a_raising_live_recompute_is_unavailable_not_a_crash(self):
        def boom(_run_dir):
            raise ValueError("bad artifacts")
        run = self.scan(fake_run_metrics(metrics_for_run_dir=boom))
        self.assertEqual(run["metrics_source"], "unavailable")
        self.assertIsNone(run["metrics"])
        # The run itself still rendered around the failed panel.
        self.assertEqual(run["slices"][0]["label"], "complete")

    def test_a_raising_degrade_path_is_also_unavailable_not_a_crash(self):
        # Same guarantee on the older-module path, which is reached only when
        # metrics_for_run_dir is absent.
        def boom(_run_dir):
            raise ValueError("bad artifacts")
        older = fake_run_metrics(load_run_artifacts=boom)
        del older.metrics_for_run_dir
        self.assertEqual(self.scan(older)["metrics_source"], "unavailable")

    def test_unreadable_run_carries_no_metrics_key_at_all(self):
        (self.docs / "bad").mkdir(parents=True)
        (self.docs / "bad" / "dag.json").write_text("{ nope")
        with mock.patch.object(ds, "run_metrics", fake_run_metrics()):
            run = next(r for r in ds.scan_runs(self.docs) if r["run_id"] == "bad")
        self.assertEqual(run["status"], "unreadable")
        self.assertNotIn("metrics", run)


class RealRunMetricsIntegrationTests(unittest.TestCase):
    """One end-to-end check against the REAL run_metrics module when it is
    deployed, so the four names this server calls are pinned to the real API and
    not only to the stub above. Skipped when the module is absent — the tolerant
    import is itself a supported deployment."""

    def setUp(self):
        if ds.run_metrics is None:
            self.skipTest("run_metrics.py is not deployed")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.docs = Path(self.tmpdir.name) / "docs" / "spec-loop"
        self.run_dir = self.docs / "r"
        write_dag_v2(self.run_dir, [slice_obj("s1", status="complete")],
                     waves=[wave(1, ["s1"], status="collected")])
        write_sidecar(self.run_dir, "s1", status="DONE")
        write_events(self.run_dir, [("run", "run-created", {})])

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_the_real_module_answers_all_four_names_the_server_calls(self):
        for name in ("SCHEMA_VERSION", "load_run_artifacts", "compute_metrics",
                     "summary_row"):
            self.assertTrue(hasattr(ds.run_metrics, name),
                            f"run_metrics is missing {name}")
        self.assertEqual(ds.run_metrics.SCHEMA_VERSION, ds.SCHEMA_V2)

    def test_a_live_recompute_against_the_real_module_yields_a_summary(self):
        run = next(r for r in ds.scan_runs(self.docs) if r["run_id"] == "r")
        self.assertEqual(run["metrics_source"], "live")
        self.assertIsInstance(run["metrics"], dict)

    def test_a_v1_run_dir_reports_its_REAL_metrics_not_an_all_null_row(self):
        # The regression this guards: reading a v1 run dir through the v2-only
        # pair returns nulls, so the dashboard would claim a run with real
        # escalations has none measurable. Asserted against the REAL module so a
        # stub cannot paper over it.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        docs = Path(tmp.name) / "docs" / "spec-loop"
        legacy = docs / "old"
        write_dag_v1(legacy, [slice_obj("s1", status="complete"),
                              slice_obj("s2", deps=["s1"], status="pending")])
        (legacy / "escalations.md").write_text(
            "## [s2] a real question   (status: OPEN)\nAnswer:\n")
        (legacy / "decisions-log.md").write_text(
            "[s1] DECISION: proceeded autonomously.\n")

        run = next(r for r in ds.scan_runs(docs) if r["run_id"] == "old")
        self.assertEqual(run["schema_version"], 1)
        self.assertEqual(run["metrics_source"], "live")
        self.assertIsNotNone(run["metrics"])
        # The load+compute pair would report None here; the router reports the
        # real count. That difference IS the bug this test exists for.
        self.assertIsNotNone(
            run["metrics"]["escalations"],
            "a v1 run dir with a real escalation must not report null escalations")
        self.assertGreaterEqual(run["metrics"]["escalations"], 1)

    def test_every_client_rendered_metric_key_exists_in_the_real_summary(self):
        # The client renders a FIXED field allowlist; if the metrics module drops
        # or renames one of those keys the pill would silently read "—" forever.
        # Assert the contract here instead.
        run = next(r for r in ds.scan_runs(self.docs) if r["run_id"] == "r")
        client_fields = (
            "escalations", "autonomy_ratio", "council_object_rate",
            "quality_gate_first_pass_rate", "refuted_rate",
            "evidence_failed_drop_rate", "split_rate", "integration_gate",
            "wall_clock_s", "engine_active_s", "human_wait_s", "tokens_total",
            # Not a pill — rendered as the tokens provenance chip, but just as
            # load-bearing: if it vanished the chip would silently never appear.
            "tokens_basis",
        )
        for key in client_fields:
            self.assertIn(key, run["metrics"],
                          f"index.html renders {key!r} but summary_row omits it")


# --------------------------------------------------------------------------
# Escalation prose-parser unit tests (their fallthrough return branches)
# --------------------------------------------------------------------------

class EscalationHelperUnitTests(unittest.TestCase):
    def test_parse_header_without_close_bracket_returns_none_token(self):
        self.assertEqual(
            ds._parse_escalation_header("## [no closing bracket here"),
            (None, "", ""),
        )

    def test_parse_header_with_close_bracket_and_no_status(self):
        token, title, state = ds._parse_escalation_header("## [s2] plain title")
        self.assertEqual(token, "s2")
        self.assertEqual(title, "plain title")
        self.assertEqual(state, "")

    def test_header_state_unknown_returns_empty(self):
        self.assertEqual(ds._header_state("no marker present"), "")
        self.assertEqual(ds._header_state("(status: OPEN)"), "OPEN")
        self.assertEqual(ds._header_state("(status: ANSWERED)"), "ANSWERED")

    def test_has_filled_answer_false_when_no_answer_line(self):
        self.assertFalse(ds._has_filled_answer(["some prose", "- not an answer line"]))
        self.assertFalse(ds._has_filled_answer([]))
        self.assertTrue(ds._has_filled_answer(["- Answer: yes go ahead"]))
        self.assertFalse(ds._has_filled_answer(["Answer:   "]))

    def test_escalation_token_is_the_part_before_the_first_colon(self):
        self.assertEqual(ds._escalation_token("s1:review-block:2"), "s1")
        self.assertEqual(ds._escalation_token("intake:council-objection"), "intake")
        self.assertEqual(ds._escalation_token("noseparator"), "noseparator")

    def test_bracket_prefix_rejects_lines_without_a_bracket_token(self):
        self.assertEqual(ds._bracket_prefix("plain prose"), (None, ""))
        self.assertEqual(ds._bracket_prefix("## [unclosed"), (None, ""))
        self.assertEqual(ds._bracket_prefix("- [s1] rest here"), ("s1", "rest here"))


# --------------------------------------------------------------------------
# Containment-helper unit tests
# --------------------------------------------------------------------------

class ContainmentTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "root"
        self.root.mkdir()
        (self.root / "ok.txt").write_text("ok")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_inside_root_resolves(self):
        self.assertIsNotNone(ds.resolve_within(self.root, "ok.txt"))

    def test_traversal_rejected(self):
        self.assertIsNone(ds.resolve_within(self.root, "../etc/passwd"))

    def test_absolute_rejected(self):
        self.assertIsNone(ds.resolve_within(self.root, "/etc/passwd"))

    def test_null_byte_rejected(self):
        self.assertIsNone(ds.resolve_within(self.root, "ok.txt\x00"))

    def test_prefix_collision_sibling_rejected(self):
        sibling = self.root.parent / (self.root.name + "-evil")
        sibling.mkdir()
        (sibling / "secret").write_text("x")
        # A name that would pass a naive startswith but is outside root.
        self.assertIsNone(
            ds.resolve_within(self.root, "../" + self.root.name + "-evil/secret"))

    def test_escaping_symlink_rejected(self):
        outside = Path(self.tmpdir.name) / "outside"
        outside.mkdir()
        (outside / "leak").write_text("secret")
        link = self.root / "link"
        try:
            link.symlink_to(outside / "leak")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported on this platform")
        self.assertIsNone(ds.resolve_within(self.root, "link"))

    def test_commonpath_valueerror_denies_containment(self):
        # SECURITY contract: if the final commonpath containment check itself
        # errors, resolve_within must DENY (return None), never fall through to a
        # permit. On POSIX both args are absolute realpaths, so a crafted relpath
        # cannot make commonpath raise ValueError through the public interface —
        # the only way to reach that except-branch is if commonpath raises, so we
        # force exactly that. The real isabs / null-byte / realpath checks still
        # run; only the collision-detector (a stdlib helper, NOT a security
        # primitive) is made to error, proving deny-on-error.
        with mock.patch("dashboard_server.os.path.commonpath",
                        side_effect=ValueError("mixed drives")):
            self.assertIsNone(ds.resolve_within(self.root, "ok.txt"))


# --------------------------------------------------------------------------
# HTTP-layer tests (risky paths first) — ephemeral port, real socket
# --------------------------------------------------------------------------

class HttpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls.tmpdir.name)
        cls.docs = build_v2_fixture(cls.tmp)
        write_dag_v1(cls.docs / "run-legacy", [slice_obj("s1", status="complete")])
        (cls.docs / "run-corrupt").mkdir(parents=True)
        (cls.docs / "run-corrupt" / "dag.json").write_text('{ "slices": [ {bad')
        assets = cls.tmp / "assets"
        assets.mkdir()
        (assets / "index.html").write_text("<!doctype html><title>dash</title>")
        (cls.tmp / "outside_secret.txt").write_text("TOP SECRET")
        cls.server = ds.build_server(cls.tmp, assets_dir=assets, port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmpdir.cleanup()

    def request(self, method, path, host=None, extra=None):
        host = host if host is not None else f"127.0.0.1:{self.port}"
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        # Use the low-level API so we control the Host header exactly:
        # skip_host suppresses the auto-added Host so we can omit or forge it.
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        if host != "__OMIT__":
            conn.putheader("Host", host)
        for k, v in (extra or {}).items():
            conn.putheader(k, v)
        conn.endheaders()
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body, resp.getheader("ETag")

    # --- risky security paths (written first) ---

    def test_run_id_traversal_returns_404(self):
        status, body, _ = self.request("GET", "/api/runs/..%2f..%2fetc%2fpasswd")
        self.assertEqual(status, 404)
        self.assertNotIn(b"root:", body)
        status2, _, _ = self.request("GET", "/api/runs/../../etc/passwd")
        self.assertEqual(status2, 404)

    def test_static_traversal_returns_404(self):
        for path in ("/../dashboard_server.py", "/../../outside_secret.txt",
                     "/..%2foutside_secret.txt"):
            status, body, _ = self.request("GET", path)
            self.assertEqual(status, 404, f"{path} -> {status}")
            self.assertNotIn(b"TOP SECRET", body)

    def test_foreign_host_rejected(self):
        status, _, _ = self.request("GET", "/api/runs", host="evil.com")
        self.assertEqual(status, 421)

    def test_substring_host_attack_rejected(self):
        status, _, _ = self.request(
            "GET", "/api/runs", host=f"localhost:{self.port}.evil.com")
        self.assertEqual(status, 421)

    def test_absent_host_rejected(self):
        status, _, _ = self.request("GET", "/api/runs", host="__OMIT__")
        self.assertEqual(status, 421)

    def test_non_get_method_returns_405(self):
        for method in ("POST", "PUT", "DELETE"):
            status, _, _ = self.request(method, "/api/runs")
            self.assertEqual(status, 405, f"{method} -> {status}")

    def test_404_body_has_no_path_oracle(self):
        # "no such run" and "escapes root" must look identical.
        missing, body_missing, _ = self.request("GET", "/api/runs/does-not-exist")
        escape, body_escape, _ = self.request("GET", "/api/runs/../../etc/passwd")
        self.assertEqual(missing, 404)
        self.assertEqual(escape, 404)
        self.assertEqual(body_missing, body_escape)

    # --- endpoint behavior ---

    def test_api_runs_lists_all_runs_of_both_generations(self):
        status, body, _ = self.request("GET", "/api/runs")
        self.assertEqual(status, 200)
        runs = {r["run_id"]: r for r in json.loads(body)["runs"]}
        self.assertEqual(set(runs),
                         {"run-mid", "run-outcomes", "run-legacy", "run-corrupt"})
        self.assertEqual(runs["run-mid"]["schema_version"], 2)
        self.assertEqual(runs["run-legacy"]["schema_version"], 1)

    def test_api_run_detail_carries_the_v2_payload(self):
        status, body, _ = self.request("GET", "/api/runs/run-mid")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["run_id"], "run-mid")
        self.assertEqual(data["mode"], "workflow")
        self.assertEqual([w["status"] for w in data["waves"]],
                         ["collected", "dispatched", "projected"])
        self.assertIn("decisions_tail", data)
        self.assertIn("escalations_source", data)

    def test_detail_carries_full_metrics_and_the_collection_only_a_summary(self):
        with mock.patch.object(ds, "run_metrics", fake_run_metrics()):
            _s, body, _e = self.request("GET", "/api/runs/run-mid")
            run = json.loads(body)
            self.assertIn("metrics_full", run)
            self.assertIn("safety", run["metrics_full"])
            self.assertEqual(run["metrics_source"], "live")
            _s, body, _e = self.request("GET", "/api/runs")
            runs = {r["run_id"]: r for r in json.loads(body)["runs"]}
            self.assertNotIn("metrics_full", runs["run-mid"])
            self.assertIn("autonomy_ratio", runs["run-mid"]["metrics"])

    def test_unreadable_run_detail_is_200_envelope(self):
        status, body, _ = self.request("GET", "/api/runs/run-corrupt")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "unreadable")

    def test_etag_304_on_unchanged(self):
        status, _, etag = self.request("GET", "/api/runs/run-mid")
        self.assertEqual(status, 200)
        self.assertIsNotNone(etag)
        status2, _, _ = self.request(
            "GET", "/api/runs/run-mid", extra={"If-None-Match": etag})
        self.assertEqual(status2, 304)

    def test_etag_busts_when_a_sidecar_is_written(self):
        # Sidecars decide the labels, so a new one MUST invalidate the cache or
        # the client would keep a stale 304 view of the run.
        _s, _b, etag = self.request("GET", "/api/runs/run-mid")
        write_sidecar(self.docs / "run-mid", "s2", status="FAILED")
        try:
            status, _, _ = self.request(
                "GET", "/api/runs/run-mid", extra={"If-None-Match": etag})
            self.assertEqual(status, 200)
        finally:
            (self.docs / "run-mid" / "slice-s2-status.json").unlink()

    def test_etag_busts_when_events_are_appended(self):
        # events.jsonl decides escalation + council truth, so it must be in the tag.
        _s, _b, etag = self.request("GET", "/api/runs/run-outcomes")
        path = self.docs / "run-outcomes" / "events.jsonl"
        original = path.read_text()
        with open(path, "a") as fh:
            fh.write(json.dumps({"ts": "t", "scope": "f", "type": "decision",
                                 "payload": {}}) + "\n")
        try:
            status, _, _ = self.request(
                "GET", "/api/runs/run-outcomes", extra={"If-None-Match": etag})
            self.assertEqual(status, 200)
        finally:
            path.write_text(original)

    def test_collection_etag_busts_when_run_added(self):
        _, _, etag = self.request("GET", "/api/runs")
        self.assertIsNotNone(etag)
        write_dag_v2(self.docs / "run-new", [slice_obj("s1")])
        try:
            status, _, _ = self.request(
                "GET", "/api/runs", extra={"If-None-Match": etag})
            self.assertEqual(status, 200)  # cache busted, not 304
        finally:
            import shutil
            shutil.rmtree(self.docs / "run-new")

    def test_index_served_at_root(self):
        status, body, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"<!doctype html>", body.lower())

    def test_head_allowed(self):
        status, body, _ = self.request("HEAD", "/api/runs")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")


# --------------------------------------------------------------------------
# Bind host / advertised-port decoupling (security: anti-rebinding)
# --------------------------------------------------------------------------

class BindHostAllowlistTests(unittest.TestCase):
    """The Host-header allowlist must derive from the ADVERTISED port and stay
    hardcoded to loopback host strings — binding 0.0.0.0 must NEVER widen it."""

    def test_allowlist_derives_from_advertised_port_only(self):
        allowed = ds._host_allowlist(9999)
        self.assertEqual(allowed, {"127.0.0.1:9999", "localhost:9999"})

    def test_allowlist_never_contains_bind_host_zero(self):
        for port in (0, 8787, 9999):
            allowed = ds._host_allowlist(port)
            self.assertFalse(any("0.0.0.0" in h for h in allowed),
                             f"allowlist leaked 0.0.0.0: {allowed}")

    def test_build_server_binds_configured_host(self):
        with tempfile.TemporaryDirectory() as d:
            server = ds.build_server(Path(d), port=0,
                                     net=ds.NetworkConfig(bind_host="0.0.0.0"))
            try:
                # Bound host reflects the request; allowlist stays loopback-only.
                self.assertEqual(server.server_address[0], "0.0.0.0")
                handler = server.RequestHandlerClass
                self.assertFalse(any("0.0.0.0" in h for h in handler.allowed_hosts))
            finally:
                server.server_close()

    def test_foreign_and_star_host_421_when_bound_zero(self):
        # The load-bearing anti-DNS-rebinding assertion: binding 0.0.0.0 does not
        # relax the Host allowlist. We connect over loopback (reachable) but forge
        # the Host header.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [slice_obj("s1")])
            assets = Path(d) / "assets"
            assets.mkdir()
            (assets / "index.html").write_text("<!doctype html>")
            server = ds.build_server(Path(d), assets_dir=assets, port=0,
                                     net=ds.NetworkConfig(bind_host="0.0.0.0"))
            port = server.server_address[1]
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                for bad_host in ("evil.com", "*", f"0.0.0.0:{port}",
                                 f"container-host:{port}"):
                    status = self._request_host(port, bad_host)
                    self.assertEqual(status, 421, f"{bad_host!r} -> {status}")
                # ...but the advertised loopback Host still works.
                self.assertEqual(self._request_host(port, f"127.0.0.1:{port}"), 200)
            finally:
                server.shutdown()
                server.server_close()

    def test_advertise_port_overrides_bound_port_in_allowlist(self):
        # When advertise_port is set, the allowlist uses it, not the bound port,
        # so a Host on the ADVERTISED port is accepted even though the socket is
        # bound to a different (ephemeral) port.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [slice_obj("s1")])
            server = ds.build_server(
                Path(d), port=0,
                net=ds.NetworkConfig(bind_host="0.0.0.0", advertise_port=8080))
            port = server.server_address[1]
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                self.assertEqual(self._request_host(port, "127.0.0.1:8080"), 200)
                # Host on the (real) bound port -> NOT in allowlist -> 421.
                self.assertEqual(self._request_host(port, f"127.0.0.1:{port}"), 421)
            finally:
                server.shutdown()
                server.server_close()

    def test_advertise_port_zero_falls_back_to_bound_port(self):
        # An explicit advertise_port=0 is falsy and must degrade to the real bound
        # port (a reachable loopback allowlist), never an unreachable ":0" entry.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs" / "spec-loop"
            write_dag_v2(docs / "r", [slice_obj("s1")])
            server = ds.build_server(Path(d), port=0,
                                     net=ds.NetworkConfig(advertise_port=0))
            port = server.server_address[1]
            handler = server.RequestHandlerClass
            self.assertNotIn("127.0.0.1:0", handler.allowed_hosts)
            self.assertIn(f"127.0.0.1:{port}", handler.allowed_hosts)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                self.assertEqual(self._request_host(port, f"127.0.0.1:{port}"), 200)
            finally:
                server.shutdown()
                server.server_close()

    @staticmethod
    def _request_host(port, host):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.putrequest("GET", "/api/runs", skip_host=True,
                        skip_accept_encoding=True)
        conn.putheader("Host", host)
        conn.endheaders()
        resp = conn.getresponse()
        resp.read()
        conn.close()
        return resp.status


# --------------------------------------------------------------------------
# Multi-root aggregation, namespacing, per-root containment
# --------------------------------------------------------------------------

class MultiRootTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _root(self, name):
        """Create a repo root <tmp>/<name> with a docs/spec-loop dir."""
        root = self.tmp / name
        (root / "docs" / "spec-loop").mkdir(parents=True)
        return root

    def test_single_root_is_transparent_no_namespacing(self):
        root = self._root("repo")
        write_dag_v2(root / "docs" / "spec-loop" / "run-x", [slice_obj("s1")])
        runs = ds.scan_all_roots([str(root)])
        self.assertEqual([r["run_id"] for r in runs], ["run-x"])
        self.assertNotIn("root", runs[0])

    def test_multi_root_namespaces_run_ids_no_collision(self):
        a = self._root("repo-a")
        b = self._root("repo-b")
        write_dag_v2(a / "docs" / "spec-loop" / "run-x", [slice_obj("s1")])
        write_dag_v1(b / "docs" / "spec-loop" / "run-x", [slice_obj("s1")])
        runs = ds.scan_all_roots([str(a), str(b)])
        self.assertEqual(sorted(r["run_id"] for r in runs),
                         ["repo-a:run-x", "repo-b:run-x"])
        self.assertTrue(all("root" in r for r in runs))
        # Each root's run keeps its own generation across the namespacing.
        by_id = {r["run_id"]: r for r in runs}
        self.assertEqual(by_id["repo-a:run-x"]["schema_version"], 2)
        self.assertEqual(by_id["repo-b:run-x"]["schema_version"], 1)

    def test_multi_root_ordering_is_deterministic_and_stable(self):
        outer1 = self.tmp / "x" / "repo"
        outer2 = self.tmp / "y" / "repo"
        for r in (outer1, outer2):
            (r / "docs" / "spec-loop").mkdir(parents=True)
            write_dag_v2(r / "docs" / "spec-loop" / "run-x", [slice_obj("s1")])
        first = sorted(r["run_id"] for r in
                       ds.scan_all_roots([str(outer1), str(outer2)]))
        second = sorted(r["run_id"] for r in
                        ds.scan_all_roots([str(outer1), str(outer2)]))
        self.assertEqual(first, second)
        self.assertEqual(len(set(first)), 2)

    def test_colliding_basenames_get_concrete_disjoint_suffixes(self):
        outer1 = self.tmp / "x" / "repo"
        outer2 = self.tmp / "y" / "repo"
        for r in (outer1, outer2):
            (r / "docs" / "spec-loop").mkdir(parents=True)
            write_dag_v2(r / "docs" / "spec-loop" / "run-x", [slice_obj("s1")])
        ids = sorted(r["run_id"] for r in
                     ds.scan_all_roots([str(outer1), str(outer2)]))
        self.assertEqual(ids, ["repo#1:run-x", "repo#2:run-x"])

    def test_single_root_run_id_with_colon_resolves_transparently(self):
        # A single-root run whose basename literally contains ':' must NOT be
        # split/namespaced — the empty-key branch resolves it as-is.
        root = self._root("repo")
        write_dag_v2(root / "docs" / "spec-loop" / "a:b", [slice_obj("s1")])
        runs = ds.scan_all_roots([str(root)])
        self.assertEqual([r["run_id"] for r in runs], ["a:b"])
        self.assertNotIn("root", runs[0])


class MultiRootHttpTests(unittest.TestCase):
    """Per-root containment over a real socket — a namespaced id may never reach
    a sibling root, and crafted ids return a uniform no-oracle 404."""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls.tmpdir.name)
        cls.root_a = cls.tmp / "repo-a"
        cls.root_b = cls.tmp / "repo-b"
        for root, only_run in ((cls.root_a, "only-a"), (cls.root_b, "only-b")):
            (root / "docs" / "spec-loop").mkdir(parents=True)
            write_dag_v2(root / "docs" / "spec-loop" / only_run,
                         [slice_obj("s1", status="complete")])
        # A secret file under root A, outside its docs/spec-loop, to prove no escape.
        (cls.root_a / "SECRET.txt").write_text("TOP SECRET A")
        assets = cls.tmp / "assets"
        assets.mkdir()
        (assets / "index.html").write_text("<!doctype html>")
        cls.server = ds.build_server([str(cls.root_a), str(cls.root_b)],
                                     assets_dir=assets, port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmpdir.cleanup()

    def _get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("GET", path, skip_accept_encoding=True)
        conn.putheader("Host", f"127.0.0.1:{self.port}")
        conn.endheaders()
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def test_api_runs_aggregates_both_roots_namespaced(self):
        status, body = self._get("/api/runs")
        self.assertEqual(status, 200)
        ids = {r["run_id"] for r in json.loads(body)["runs"]}
        self.assertEqual(ids, {"repo-a:only-a", "repo-b:only-b"})

    def test_namespaced_detail_resolves_to_owning_root(self):
        status, body = self._get("/api/runs/repo-a%3Aonly-a")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["run_id"], "repo-a:only-a")

    def test_run_from_one_root_not_reachable_under_another(self):
        status, _ = self._get("/api/runs/repo-a%3Aonly-b")
        self.assertEqual(status, 404)

    def test_bogus_root_key_and_bare_id_miss_uniformly(self):
        # A syntactically valid but unknown key, and a bare (unqualified) id, must
        # both return the SAME no-oracle 404 body as a matched-key missing run —
        # never a fall-back that searches all roots.
        _, plain_miss = self._get("/api/runs/repo-a%3Adoes-not-exist")
        for path in ("/api/runs/nosuchrepo%3Aonly-a",  # unknown key
                     "/api/runs/only-a",               # bare id, no key
                     "/api/runs/%3Aonly-a"):           # empty key
            status, body = self._get(path)
            self.assertEqual(status, 404, f"{path} -> {status}")
            self.assertEqual(body, plain_miss, f"path oracle on {path}")

    def test_crafted_namespaced_id_cannot_escape_or_oracle(self):
        # Uniform no-path-oracle 404: a crafted traversal id and a plain miss must
        # be byte-identical, and neither leaks the sibling root or a secret.
        _, plain_miss = self._get("/api/runs/repo-a%3Adoes-not-exist")
        crafted = (
            "/api/runs/repo-a%3A..%2f..%2frepo-b%2fdocs%2fspec-loop%2fonly-b",
            "/api/runs/repo-a%3A..%2f..%2fSECRET.txt",
            "/api/runs/..%2f..%2frepo-b%2fdocs%2fspec-loop%2fonly-b",
        )
        for path in crafted:
            status, body = self._get(path)
            self.assertEqual(status, 404, f"{path} -> {status}")
            self.assertEqual(body, plain_miss, f"path oracle on {path}")
            self.assertNotIn(b"SECRET", body)

    def test_multi_root_foreign_host_still_421(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("GET", "/api/runs", skip_host=True,
                        skip_accept_encoding=True)
        conn.putheader("Host", "evil.com")
        conn.endheaders()
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 421)


# --------------------------------------------------------------------------
# In-thread handler unit tests — exercise the request/response path on the
# TEST thread so measure_coverage's per-thread trace can see it.
#
# WHY: measure_coverage.py runs the suite under trace.Trace(count=1), which
# records ONLY the calling thread. The socket tests above drive the handler on
# a daemon serve_forever thread, so the handler body is behaviorally exercised
# but invisible to the line tracer. These tests call the same methods directly
# on the test thread. They are ADDITIVE coverage-visibility mirrors — the
# real-socket suites above remain the authoritative security check for the
# loopback bind / Host allowlist / traversal-confinement / no-oracle-404
# invariants, and are left untouched. No security primitive is stubbed here:
# the real _host_allowed / resolve_within / os.path.isfile run.
# --------------------------------------------------------------------------

def make_handler(tmp: Path):
    """Return (bound_handler_instance, docs_path). Build the bound handler class
    via build_server (the single wiring authority) so roots/assets_root/
    allowed_hosts are injected exactly as in production, then instantiate it
    WITHOUT the socket handshake (__new__, no __init__). The minimal attributes
    _emit needs on the test thread are set; send_response/send_header/end_headers
    run FOR REAL against a BytesIO wfile — no call-spies."""
    docs = build_v2_fixture(tmp)
    assets = tmp / "assets"
    assets.mkdir()
    (assets / "index.html").write_text("<!doctype html><title>dash</title>")
    (assets / "app.css").write_text("body{color:#fff}")
    (tmp / "outside_secret.txt").write_text("TOP SECRET")
    server = ds.build_server(tmp, assets_dir=assets, port=0)
    bound = server.RequestHandlerClass
    server.server_close()  # we never serve; we invoke methods directly

    handler = bound.__new__(bound)
    handler.wfile = io.BytesIO()
    handler.request_version = "HTTP/1.1"
    handler.requestline = "GET / HTTP/1.1"
    handler.command = "GET"
    handler.headers = {}
    return handler, docs


def emit_wire(handler, resp, write_body=True):
    """Run _emit for real and return the raw emitted bytes."""
    handler.wfile = io.BytesIO()
    handler._emit(resp, write_body=write_body)
    return handler.wfile.getvalue()


class ContentTypeTests(unittest.TestCase):
    def test_known_extensions_map_exactly(self):
        cases = {
            "index.html": "text/html; charset=utf-8",
            "app.css": "text/css; charset=utf-8",
            "app.js": "application/javascript; charset=utf-8",
            "data.json": "application/json; charset=utf-8",
            "icon.svg": "image/svg+xml",
            "ICON.SVG": "image/svg+xml",  # case-insensitive suffix
        }
        for name, expected in cases.items():
            self.assertEqual(ds._content_type(name), expected, name)

    def test_unknown_extension_is_octet_stream(self):
        self.assertEqual(ds._content_type("archive.tar"), "application/octet-stream")
        self.assertEqual(ds._content_type("noext"), "application/octet-stream")


class ResponseHelperTests(unittest.TestCase):
    def test_json_response_shape(self):
        resp = ds._json_response({"a": 1})
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.content_type, "application/json; charset=utf-8")
        self.assertEqual(json.loads(resp.body), {"a": 1})
        self.assertIsNone(resp.etag)

    def test_text_helper_shape(self):
        resp = ds._text(404, b"not found")
        self.assertEqual(resp.status, 404)
        self.assertEqual(resp.body, b"not found")
        self.assertEqual(resp.content_type, "text/plain")


class HandlerUnitTests(unittest.TestCase):
    """Direct, in-thread invocation of the handler methods (real primitives)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.handler, self.docs = make_handler(self.tmp)
        # A single-root server -> exactly one ("", data_root) pair.
        self.host = next(iter(self.handler.allowed_hosts))

    def tearDown(self):
        self.tmpdir.cleanup()

    # --- _emit runs for real; assert the emitted wire bytes (behavioral) ---

    def test_emit_includes_security_and_length_headers(self):
        wire = emit_wire(self.handler, ds._json_response({"ok": True})).decode("latin-1")
        head, body = wire.split("\r\n\r\n", 1)
        self.assertIn("HTTP/1.1 200", head)
        # nosniff is a real security header asserted by NO socket test.
        self.assertIn("X-Content-Type-Options: nosniff", head)
        self.assertIn("Content-Type: application/json; charset=utf-8", head)
        self.assertIn(f"Content-Length: {len(body.encode('latin-1'))}", head)
        self.assertEqual(json.loads(body), {"ok": True})

    def test_emit_etag_present_only_when_set(self):
        with_etag = emit_wire(
            self.handler, ds.Response(200, b"x", "text/plain", '"tag123"')
        ).decode("latin-1")
        self.assertIn('ETag: "tag123"', with_etag)
        without = emit_wire(
            self.handler, ds.Response(200, b"x", "text/plain")
        ).decode("latin-1")
        self.assertNotIn("ETag:", without)

    def test_emit_head_writes_no_body(self):
        wire = emit_wire(
            self.handler, ds._json_response({"ok": True}), write_body=False
        ).decode("latin-1")
        _head, body = wire.split("\r\n\r\n", 1)
        self.assertEqual(body, "")

    # --- _content_type / static via real resolve_within ---

    def test_serve_static_index_and_css(self):
        idx = self.handler._serve_static("/")
        self.assertEqual(idx.status, 200)
        self.assertTrue(idx.content_type.startswith("text/html"))
        css = self.handler._serve_static("/app.css")
        self.assertEqual(css.status, 200)
        self.assertEqual(css.content_type, "text/css; charset=utf-8")

    def test_serve_static_missing_file_is_404(self):
        self.assertEqual(self.handler._serve_static("/nope.html").status, 404)

    def test_serve_static_traversal_is_404_real_resolve_within(self):
        # Real resolve_within runs; a traversal must NOT reach outside_secret.txt.
        for route in ("/../outside_secret.txt", "/../../etc/passwd"):
            resp = self.handler._serve_static(route)
            self.assertEqual(resp.status, 404, route)
            self.assertNotIn(b"TOP SECRET", resp.body)

    def test_read_asset_returns_bytes_and_none_on_error(self):
        target = ds.resolve_within(self.handler.assets_root, "index.html")
        self.assertIsNotNone(target)
        self.assertIn(b"<!doctype html>", self.handler._read_asset(target).lower())
        # A directory (not a file) -> OSError inside open() -> None.
        self.assertIsNone(self.handler._read_asset(self.handler.assets_root))

    # --- _host_allowed / _route with the REAL allowlist (no stubbing) ---

    def test_host_allowed_true_for_allowlisted_host(self):
        self.handler.headers = {"Host": self.host}
        self.assertTrue(self.handler._host_allowed())

    def test_host_allowed_false_for_foreign_host(self):
        self.handler.headers = {"Host": "evil.com"}
        self.assertFalse(self.handler._host_allowed())

    def test_host_allowed_false_for_absent_host(self):
        self.handler.headers = {}  # .get("Host") is None -> distinct branch
        self.assertFalse(self.handler._host_allowed())

    def test_route_disallowed_host_returns_421(self):
        self.handler.headers = {"Host": "evil.com"}
        self.handler.path = "/api/runs"
        self.assertEqual(self.handler._route().status, 421)

    def test_route_api_runs_ok(self):
        self.handler.headers = {"Host": self.host}
        self.handler.path = "/api/runs"
        resp = self.handler._route()
        self.assertEqual(resp.status, 200)
        self.assertIn(b"run-mid", resp.body)

    def test_route_api_run_detail_ok_and_missing(self):
        self.handler.headers = {"Host": self.host}
        self.handler.path = "/api/runs/run-mid"
        ok = self.handler._route()
        self.assertEqual(ok.status, 200)
        self.assertEqual(json.loads(ok.body)["run_id"], "run-mid")
        self.handler.path = "/api/runs/does-not-exist"
        self.assertEqual(self.handler._route().status, 404)

    def test_route_static_index(self):
        self.handler.headers = {"Host": self.host}
        self.handler.path = "/"
        resp = self.handler._route()
        self.assertEqual(resp.status, 200)
        self.assertIn(b"<!doctype html>", resp.body.lower())

    # --- _not_modified with the real If-None-Match header ---

    def test_not_modified_returns_304_on_match(self):
        self.handler.headers = {"If-None-Match": '"etag-1"'}
        resp = self.handler._not_modified('"etag-1"')
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status, 304)
        self.assertEqual(resp.body, b"")

    def test_not_modified_returns_none_on_mismatch(self):
        self.handler.headers = {"If-None-Match": '"other"'}
        self.assertIsNone(self.handler._not_modified('"etag-1"'))

    def test_api_runs_304_via_route(self):
        # End-to-end in-thread: fetch etag, then a matching If-None-Match -> 304.
        self.handler.headers = {"Host": self.host}
        self.handler.path = "/api/runs/run-mid"
        first = self.handler._route()
        self.assertEqual(first.status, 200)
        self.assertIsNotNone(first.etag)
        self.handler.headers = {"Host": self.host, "If-None-Match": first.etag}
        self.assertEqual(self.handler._route().status, 304)

    def test_collection_material_ok(self):
        self.handler.headers = {"Host": self.host}
        self.handler.path = "/api/runs"
        self.assertEqual(self.handler._route().status, 200)

    def test_collection_material_weak_key_when_run_unresolvable(self):
        # A run listed at scan time but not resolvable within its owning root
        # (e.g. a concurrent delete between the two globs) yields the weaker "-"
        # cache key rather than crashing.
        material = self.handler._collection_material([{"run_id": "vanished"}])
        self.assertEqual(material, ["vanished:-"])

    # --- verb entry points invoked directly (trace-visible on the test thread) ---

    def test_do_get_emits_full_response_with_body(self):
        self.handler.headers = {"Host": self.host}
        self.handler.path = "/api/runs"
        self.handler.wfile = io.BytesIO()
        self.handler.do_GET()
        wire = self.handler.wfile.getvalue().decode("latin-1")
        head, body = wire.split("\r\n\r\n", 1)
        self.assertIn("HTTP/1.1 200", head)
        self.assertIn("run-mid", body)  # GET writes the real body

    def test_do_head_emits_headers_but_no_body(self):
        self.handler.headers = {"Host": self.host}
        self.handler.path = "/api/runs"
        self.handler.wfile = io.BytesIO()
        self.handler.do_HEAD()
        wire = self.handler.wfile.getvalue().decode("latin-1")
        head, body = wire.split("\r\n\r\n", 1)
        self.assertIn("HTTP/1.1 200", head)
        # A Content-Length is still advertised, but no body bytes are written.
        self.assertIn("Content-Length:", head)
        self.assertEqual(body, "")

    def test_rejected_verb_entry_emits_405(self):
        # do_POST is bound to _reject_method (as are PUT/DELETE/PATCH/OPTIONS).
        self.handler.headers = {"Host": self.host}
        self.handler.path = "/api/runs"
        self.handler.wfile = io.BytesIO()
        self.handler.do_POST()
        wire = self.handler.wfile.getvalue().decode("latin-1")
        head, body = wire.split("\r\n\r\n", 1)
        self.assertIn("HTTP/1.1 405", head)
        self.assertIn("method not allowed", body)

    def test_do_get_foreign_host_emits_421_on_wire(self):
        # The anti-DNS-rebinding deny, exercised through the REAL do_GET -> _route
        # -> _host_allowed on the test thread.
        self.handler.headers = {"Host": "evil.com"}
        self.handler.path = "/api/runs"
        self.handler.wfile = io.BytesIO()
        self.handler.do_GET()
        wire = self.handler.wfile.getvalue().decode("latin-1")
        head, body = wire.split("\r\n\r\n", 1)
        self.assertIn("HTTP/1.1 421", head)
        self.assertIn("misdirected request", body)

    def test_serve_static_unreadable_file_is_404_no_partial_body(self):
        # A target that PASSES resolve_within + os.path.isfile but whose read
        # fails (e.g. a concurrent unlink / permission flip between the checks)
        # must return a clean 404 with no body, never a partial/garbled asset.
        with mock.patch.object(self.handler, "_read_asset", return_value=None):
            resp = self.handler._serve_static("/")
        self.assertEqual(resp.status, 404)
        self.assertEqual(resp.body, b"not found")


class MultiRootHandlerUnitTests(unittest.TestCase):
    """In-thread (trace-visible) invocation of the MULTI-root owning-root /
    run-dir resolution miss branches. A single-root handler short-circuits
    _owning_root at its len==1/empty-key guard and never reaches the partition/
    match/miss branches, so these need a genuine two-root bound handler."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.root_a = self.tmp / "repo-a"
        self.root_b = self.tmp / "repo-b"
        for root, only_run in ((self.root_a, "only-a"), (self.root_b, "only-b")):
            write_dag_v2(root / "docs" / "spec-loop" / only_run,
                         [slice_obj("s1", status="complete")])
        assets = self.tmp / "assets"
        assets.mkdir()
        (assets / "index.html").write_text("<!doctype html>")
        server = ds.build_server([str(self.root_a), str(self.root_b)],
                                 assets_dir=assets, port=0)
        self.handler = server.RequestHandlerClass.__new__(server.RequestHandlerClass)
        server.server_close()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_owning_root_matches_known_key_and_returns_bare_id(self):
        root_key, data_root, run_id = self.handler._owning_root("repo-b:only-b")
        self.assertEqual(root_key, "repo-b")
        self.assertEqual(run_id, "only-b")
        self.assertTrue(str(data_root).endswith(os.path.join(
            "repo-b", "docs", "spec-loop")))

    def test_owning_root_unknown_key_returns_none(self):
        self.assertEqual(
            self.handler._owning_root("nosuchrepo:only-a"), ("", None, None))
        # A bare (keyless) id also matches no root key in multi-root mode.
        self.assertEqual(self.handler._owning_root("only-a"), ("", None, None))

    def test_resolve_run_dir_unknown_root_key_returns_empty_none(self):
        # data_root is None (no owning root) -> ("", None), the uniform "no such
        # run" miss (no oracle for key-exists-vs-not).
        self.assertEqual(
            self.handler._resolve_run_dir("nosuchrepo:only-a"), ("", None))

    def test_resolve_run_dir_known_key_missing_run_returns_key_none(self):
        # Matched key but the bare run id isn't among that root's discovered runs
        # -> (root_key, None). 'only-b' lives only in root B.
        root_key, run_dir = self.handler._resolve_run_dir("repo-a:only-b")
        self.assertEqual(root_key, "repo-a")
        self.assertIsNone(run_dir)


# --------------------------------------------------------------------------
# main() entrypoint — argparse + wiring, no blocking serve_forever
# --------------------------------------------------------------------------

class MainEntrypointTests(unittest.TestCase):
    """Drive main(argv) with the ThreadingHTTPServer seam mocked so the real
    build_server wiring (_resolve_roots + _host_allowlist) runs but the process
    never blocks on serve_forever. Every invocation pins --port 0."""

    def _fake_server(self):
        srv = mock.MagicMock()
        srv.server_address = ("127.0.0.1", 0)
        srv.serve_forever.side_effect = KeyboardInterrupt  # graceful-stop branch
        return srv

    @contextlib.contextmanager
    def _mocked_serve(self):
        """Patch the ThreadingHTTPServer seam and capture both streams so main()
        runs its real wiring without blocking. Yields (fake_server, out, err)."""
        fake = self._fake_server()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(ds, "ThreadingHTTPServer", return_value=fake), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            yield fake, out, err

    def test_main_wires_server_and_stops_gracefully(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_dag_v2(root / "docs" / "spec-loop" / "r", [slice_obj("s1")])
            with self._mocked_serve() as (fake, out, _err):
                rc = ds.main(["--root", str(root), "--port", "0"])
            self.assertEqual(rc, 0)
            fake.serve_forever.assert_called_once()
            fake.server_close.assert_called_once()  # finally: ran
            self.assertIn("stopping", out.getvalue())

    def test_main_warns_on_nonexistent_root(self):
        with tempfile.TemporaryDirectory() as d:
            # A root with NO docs/spec-loop -> warning to stderr.
            root = Path(d) / "empty-root"
            root.mkdir()
            with self._mocked_serve() as (_fake, _out, err):
                rc = ds.main(["--root", str(root), "--port", "0"])
            self.assertEqual(rc, 0)
            self.assertIn("does not exist", err.getvalue())

    def test_main_default_root_is_cwd(self):
        # No --root -> defaults to "." (cwd). Run inside a fresh tmp cwd so the
        # default-root branch is exercised without touching the live checkout.
        with tempfile.TemporaryDirectory() as d:
            prev = os.getcwd()
            os.chdir(d)
            try:
                # Wrap the real build_server to capture the resolved root the
                # default branch (raw_roots = ["."]) produced.
                captured = {}
                real_build = ds.build_server

                def spy_build(root, *a, **kw):
                    captured["root"] = root
                    return real_build(root, *a, **kw)

                with self._mocked_serve() as (_fake, out, _err), \
                        mock.patch.object(ds, "build_server", side_effect=spy_build):
                    rc = ds.main(["--port", "0"])
                self.assertEqual(rc, 0)
                # The default root "." resolved to the current (tmp) cwd, not the
                # live checkout — an observable effect of the default-root branch.
                self.assertEqual(
                    [os.path.realpath(r) for r in captured["root"]],
                    [os.path.realpath(d)],
                )
                self.assertIn("serving 1 root(s)", out.getvalue())
            finally:
                os.chdir(prev)


if __name__ == "__main__":
    unittest.main()
