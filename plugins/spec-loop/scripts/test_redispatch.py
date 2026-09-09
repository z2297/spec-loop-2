#!/usr/bin/env python3
"""Tests for redispatch.py — the controller's mechanical re-dispatch builder.

Run 20260908-jira-intake hand-assembled every re-dispatch: it dropped an
answered round's key (re-opening j1:quality-gate-block:2 after :3 was
answered), re-planned a delivered slice from its goal, and accepted the same
gate violations in prose three times. `redispatch.py args` builds the wave's
`slices` (non-terminal only, each with a `slice.entry` from its sidecar), the
cumulative `answers` map and the `accepted_violations` map from the run's own
artifacts; `redispatch.py accept-violations` records an acceptance BY
ESCALATION ID as one decision event plus the answer, so acceptance and answer
cannot diverge. Filesystem paths run against throwaway run dirs; the last
class replays the real 20260908 corpus committed under docs/spec-loop/.

Usage:
    python3 -m unittest test_redispatch
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import redispatch as rd  # noqa: E402
import run_state as rs  # noqa: E402
import worktrees as wt  # noqa: E402

TS = "2026-09-09T10:00:00Z"
RUN_ID = "20260909-demo"
REAL_RUN = Path(__file__).resolve().parents[3] / "docs" / "spec-loop" / "20260908-jira-intake"
CL = {"metric": "class_lines", "file": "a.py", "function": None, "value": 536, "threshold": 300}
PC = {"metric": "parameter_count", "file": "a.py", "function": "redirect", "value": 6, "threshold": 5}


def dag(slices, wave_ids):
    return {"schema_version": 2, "run_id": RUN_ID, "base_ref": "main", "base_sha": "b" * 40,
            "slices": slices, "waves": [{"index": 1, "slice_ids": wave_ids, "workflow_run_id": "wf_1", "status": "collected"}]}


def dag_slice(slice_id, status="running"):
    return {"id": slice_id, "goal": "goal of " + slice_id, "files": ["a.py"], "subsystems": ["x"],
            "deps": [], "risk_tier": 2, "depth": 0, "parent": None, "status": status}


def sidecar(slice_id, status, head="c0bdca3", **over):
    review = {"confirmed": 1, "refuted": 0, "evidence_failed": 0, "fix_rounds": 2, "residual": ["P2: naming"]}
    review["open"] = [{"id": "r0-f1", "claim": "still broken"}]
    body = {"schema_version": 2, "id": slice_id, "status": status, "branch": wt.branch_name(RUN_ID, slice_id)}
    body.update({"commits": {"base": "a" * 7, "head": head}, "risk_tier": 2, "review_tier": 3})
    body.update({"critique": {"verdict": "ENDORSE", "concerns": 0}, "tasks_completed": 4, "review": review})
    body.update({"tests": {"command": "true", "result": "ok", "scope": "full", "tree_sha": "t"}})
    body.update({"quality": {"status": "FAIL", "detail": "debt"}, "agents_used": 9, "wave": 1})
    if status == "ESCALATED":
        body["escalations"] = [gate_record(slice_id + ":quality-gate-block", [CL, PC])]
    body.update(over)
    return body


def gate_record(record_id, violations):
    return {"id": record_id, "trigger": "quality-gate-block", "title": "verification failed",
            "context": "quality FAIL", "question": "accept?", "options": [{"label": "accept", "detail": "d"}],
            "status": "OPEN", "violations": violations}


class RedispatchTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.run_dir = os.path.join(self.root, "docs", "spec-loop", RUN_ID)
        os.makedirs(self.run_dir)

    def write(self, name, obj):
        with open(os.path.join(self.run_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    def event(self, ts, scope, event_type, payload):
        rs.append_event(self.run_dir, rs.build_event(ts, scope, event_type, payload))

    def cli(self, *argv, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        patches = [mock.patch("sys.stdout", out), mock.patch("sys.stderr", err)]
        if stdin is not None:
            patches.append(mock.patch("sys.stdin", io.StringIO(stdin)))
        for patch in patches:
            patch.start()
        try:
            code = rd.main(list(argv) + ["--run-dir", self.run_dir])
        finally:
            for patch in reversed(patches):
                patch.stop()
        payload = json.loads(out.getvalue()) if out.getvalue().strip() else None
        return code, payload, err.getvalue()

    def seed_three_slices(self):
        self.write("dag.json", dag([dag_slice("d1", "complete"), dag_slice("e1"), dag_slice("h1")], ["d1", "e1", "h1"]))
        self.write("slice-d1-status.json", sidecar("d1", "DONE"))
        self.write("slice-e1-status.json", sidecar("e1", "ESCALATED"))
        self.write("slice-h1-status.json", sidecar("h1", "ESCALATED", head=None))
        self.event(TS, "e1", "escalation-opened", gate_record("e1:quality-gate-block", [CL, PC]))
        self.event(TS, "e1", "escalation-answered", {"id": "e1:quality-gate-block", "answer": "first", "answered_at": TS})
        self.event(TS, "e1", "escalation-opened", gate_record("e1:quality-gate-block:2", [CL]))
        self.event(TS, "e1", "escalation-answered", {"id": "e1:quality-gate-block:2", "answer": "second", "answered_at": TS})


class TestArgsBuildsTheWave(RedispatchTestCase):
    def setUp(self):
        super().setUp()
        self.seed_three_slices()

    def args(self, *extra):
        return self.cli("args", "--wave", "1", "--repo-dir", self.root, *extra)

    def test_done_slices_are_excluded_and_the_others_kept(self):
        code, out, _ = self.args("--stage", "e1=fix")
        self.assertEqual(code, 0)
        self.assertEqual([s["id"] for s in out["slices"]], ["e1", "h1"])

    def test_a_headed_slice_gets_a_full_entry_from_its_sidecar(self):
        _, out, _ = self.args("--stage", "e1=fix")
        entry = out["slices"][0]["entry"]
        self.assertEqual(entry["stage"], "fix")
        self.assertEqual(entry["head"], "c0bdca3")
        self.assertEqual(entry["fix_rounds"], 2)
        self.assertEqual(entry["review_tier"], 3)
        self.assertEqual(entry["tasks_completed"], 4)
        self.assertEqual(entry["residual"], ["P2: naming"])
        self.assertEqual(entry["orders"][0]["id"], "r0-f1")

    def test_a_headless_slice_has_no_entry_and_a_resume_is_advised(self):
        _, out, _ = self.args("--stage", "e1=fix")
        headless = out["slices"][1]
        self.assertNotIn("entry", headless)
        self.assertTrue(out["resume"]["advised"])
        self.assertIn("h1", out["resume"]["reason"])

    def test_a_missing_stage_for_a_headed_slice_is_refused_naming_it(self):
        code, _, err = self.args()
        self.assertEqual(code, 2)
        self.assertIn("e1", err)
        self.assertIn("--stage", err)

    def test_an_unknown_stage_is_refused(self):
        code, _, err = self.args("--stage", "e1=polish")
        self.assertEqual(code, 2)
        self.assertIn("polish", err)

    def test_answers_carry_every_round(self):
        _, out, _ = self.args("--stage", "e1=fix")
        self.assertEqual(out["answers"]["e1:quality-gate-block"], "first")
        self.assertEqual(out["answers"]["e1:quality-gate-block:2"], "second")

    def test_a_head_override_wins_over_the_sidecar(self):
        _, out, _ = self.args("--stage", "e1=verify", "--head", "e1=deadbeef")
        self.assertEqual(out["slices"][0]["entry"]["head"], "deadbeef")

    def test_orders_from_a_file_replace_the_sidecars_open_list(self):
        path = os.path.join(self.root, "orders.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(["defuse the delimiters"], fh)
        _, out, _ = self.args("--stage", "e1=fix", "--orders", "e1=" + path)
        self.assertEqual(out["slices"][0]["entry"]["orders"], ["defuse the delimiters"])

    def test_branch_and_worktree_come_from_the_worktrees_helpers(self):
        _, out, _ = self.args("--stage", "e1=fix")
        e1 = out["slices"][0]
        self.assertEqual(e1["branch"], wt.branch_name(RUN_ID, "e1"))
        self.assertEqual(e1["worktree"], wt.worktree_path(self.root, RUN_ID, "e1"))
        self.assertEqual(e1["base_sha"], "a" * 7)
        self.assertEqual(e1["goal"], "goal of e1")

    def test_recorded_acceptances_reach_the_map_deduplicated(self):
        accepted = {"summary": "accepted", "kind": "accepted-violations", "slice": "e1", "accepted": [CL, CL, PC]}
        accepted["from_escalation"] = "e1:quality-gate-block"
        self.event(TS, "e1", "decision", accepted)
        _, out, _ = self.args("--stage", "e1=verify")
        fps = out["accepted_violations"]["e1"]
        self.assertEqual(len(fps), 2)
        self.assertEqual(fps[0], {"metric": "class_lines", "file": "a.py", "function": None})

    def test_a_wave_with_only_terminal_slices_returns_no_slices_and_says_so(self):
        self.write("dag.json", dag([dag_slice("d1", "complete")], ["d1"]))
        _, out, _ = self.args("--stage", "d1=verify")
        self.assertEqual(out["slices"], [])
        self.assertTrue(any("d1" in n and "DONE" in n for n in out["notes"]))


class TestAcceptViolations(RedispatchTestCase):
    def setUp(self):
        super().setUp()
        self.seed_three_slices()

    def accept(self, *extra, **kw):
        return self.cli("accept-violations", "--ts", TS, "--slice", "e1", "--from-escalation", "e1:quality-gate-block:2", *extra, **kw)

    def test_all_copies_the_fingerprints_from_the_opened_record(self):
        code, out, _ = self.accept("--all")
        self.assertEqual(code, 0)
        decisions = [e for e in rs.read_events(self.run_dir) if e["type"] == "decision"]
        self.assertEqual(len(decisions), 1)
        payload = decisions[0]["payload"]
        self.assertEqual(payload["kind"], "accepted-violations")
        self.assertEqual(payload["from_escalation"], "e1:quality-gate-block:2")
        self.assertEqual(payload["accepted"], [{"metric": "class_lines", "file": "a.py", "function": None}])
        self.assertEqual(out["accepted"], 1)

    def test_an_answer_lands_with_the_acceptance(self):
        self.accept("--all", "--answer", "ACCEPT as pre-existing debt")
        answered = [e for e in rs.read_events(self.run_dir) if e["type"] == "escalation-answered"]
        self.assertEqual(answered[-1]["payload"]["id"], "e1:quality-gate-block:2")
        self.assertEqual(answered[-1]["payload"]["answer"], "ACCEPT as pre-existing debt")

    def test_the_acceptance_renders_into_the_decisions_log(self):
        self.accept("--all")
        with open(os.path.join(self.run_dir, "decisions-log.md"), encoding="utf-8") as fh:
            self.assertIn("class_lines", fh.read())

    def test_a_wildcard_is_refused(self):
        code, _, err = self.accept("--json", "-", stdin=json.dumps([{"metric": "class_lines", "file": "*"}]))
        self.assertEqual(code, 2)
        self.assertIn("wildcard", err)

    def test_an_unknown_escalation_is_refused(self):
        code, _, err = self.cli("accept-violations", "--ts", TS, "--slice", "e1", "--from-escalation", "e1:nope", "--all")
        self.assertEqual(code, 2)
        self.assertIn("e1:nope", err)

    def test_a_slice_that_does_not_own_the_escalation_is_refused(self):
        code, _, err = self.cli("accept-violations", "--ts", TS, "--slice", "h1", "--from-escalation", "e1:quality-gate-block", "--all")
        self.assertEqual(code, 2)
        self.assertIn("h1", err)


@unittest.skipUnless(REAL_RUN.is_dir(), "real run corpus not present")
class TestRealRunReplay(unittest.TestCase):
    """The 20260908 corpus: every j1 round is drained and a DONE slice never
    re-enters a wave, whatever --stage says about it."""

    def test_every_answered_round_of_j1_is_drained(self):
        out = rd.build_args(str(REAL_RUN), 1, str(REAL_RUN.parents[2]), {"stages": {"j1": "verify"}})
        for key in ("j1:quality-gate-block", "j1:quality-gate-block:2", "j1:quality-gate-block:3"):
            with self.subTest(key=key):
                self.assertIn(key, out["answers"])
        self.assertEqual(out["slices"], [])
        self.assertTrue(any("j1" in n for n in out["notes"]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
