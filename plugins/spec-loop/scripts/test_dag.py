#!/usr/bin/env python3
"""Tests for dag.py — the run-structure authority (stdlib unittest).

Everything interesting in dag.py is a pure function over a parsed dag dict, so
the bulk of this suite builds fixture dags in memory and asserts on returned
reports (no subprocess, no git, no clock). The persistence layer (atomic
rewrite) and the argparse CLI are exercised against throwaway run directories
built with tempfile, including the "a refused operation leaves dag.json byte
for byte unchanged" property that the controller relies on.

Usage:
    python3 -m unittest test_dag
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

import dag as dagmod  # noqa: E402


def sl(slice_id, deps=(), status="pending", depth=0, parent=None, risk_tier=1, **over):
    """A minimal well-formed slice object."""
    obj = {
        "id": slice_id,
        "goal": "do %s" % slice_id,
        "files": [],
        "subsystems": [],
        "deps": list(deps),
        "risk_tier": risk_tier,
        "depth": depth,
        "parent": parent,
        "status": status,
    }
    obj.update(over)
    return obj


def make_dag(slices=None, waves=None, **over):
    """A minimal well-formed dag.json body."""
    body = {
        "schema_version": 2,
        "run_id": "20260730-demo",
        "base_ref": "csv-export",
        "base_sha": "0" * 40,
        "base_branch": "main",
        "merge_mode": "single-branch",
        "mode": "workflow",
        "created_at": "2026-07-30T00:00:00Z",
        "shared_constraints": [],
        "slices": [sl("s1"), sl("s2", deps=["s1"])] if slices is None else slices,
        "waves": [] if waves is None else waves,
    }
    body.update(over)
    return body


def wave(index, slice_ids, status="dispatched", workflow_run_id=None):
    return {
        "index": index,
        "slice_ids": list(slice_ids),
        "workflow_run_id": workflow_run_id,
        "status": status,
    }


# --------------------------------------------------------------------------
# validate_dag — pure
# --------------------------------------------------------------------------

class TestValidate(unittest.TestCase):
    def assertErrorMentions(self, errors, needle):
        self.assertTrue(errors, "expected at least one error")
        self.assertTrue(
            any(needle in e for e in errors),
            "no error mentioned %r; errors were %r" % (needle, errors),
        )

    def test_well_formed_dag_has_no_errors(self):
        self.assertEqual(dagmod.validate_dag(make_dag()), [])

    def test_split_family_is_valid(self):
        d = make_dag(slices=[
            sl("s1", status="split"),
            sl("s1.1", depth=1, parent="s1"),
            sl("s1.2", depth=1, parent="s1", deps=["s1.1"]),
            sl("s2", deps=["s1"]),
        ], waves=[wave(1, ["s1"], status="collected")])
        self.assertEqual(dagmod.validate_dag(d), [])

    def test_non_object_rejected(self):
        self.assertErrorMentions(dagmod.validate_dag([]), "object")

    def test_wrong_schema_version(self):
        self.assertErrorMentions(dagmod.validate_dag(make_dag(schema_version=1)),
                                 "schema_version")

    def test_missing_schema_version(self):
        d = make_dag()
        del d["schema_version"]
        self.assertErrorMentions(dagmod.validate_dag(d), "schema_version")

    def test_slices_must_be_a_list(self):
        self.assertErrorMentions(dagmod.validate_dag(make_dag(slices={})), "slices")

    def test_scope_ceiling_is_absent_from_a_well_formed_dag_and_that_is_valid(self):
        d = make_dag()
        self.assertNotIn("scope_ceiling", d)
        self.assertEqual(dagmod.validate_dag(d), [])

    def test_scope_ceiling_of_non_empty_strings_is_valid(self):
        d = make_dag(scope_ceiling=["do not touch the tier table",
                                    "no dashboard UI work"])
        self.assertEqual(dagmod.validate_dag(d), [])

    def test_scope_ceiling_may_be_an_empty_list(self):
        self.assertEqual(dagmod.validate_dag(make_dag(scope_ceiling=[])), [])

    def test_scope_ceiling_must_be_a_list(self):
        self.assertErrorMentions(
            dagmod.validate_dag(make_dag(scope_ceiling="no dashboard work")),
            "scope_ceiling must be a list")

    def test_scope_ceiling_rejects_a_non_string_entry(self):
        errors = dagmod.validate_dag(make_dag(scope_ceiling=["ok", 7]))
        self.assertErrorMentions(errors, "scope_ceiling entry 1")

    def test_scope_ceiling_rejects_a_blank_entry(self):
        errors = dagmod.validate_dag(make_dag(scope_ceiling=["   "]))
        self.assertErrorMentions(errors, "scope_ceiling entry 0")

    def test_scope_ceiling_reports_every_bad_entry_without_short_circuiting(self):
        errors = dagmod.validate_dag(make_dag(scope_ceiling=[None, "ok", ""]))
        self.assertEqual(
            len([e for e in errors if e.startswith("scope_ceiling entry")]), 2)

    def test_a_null_scope_ceiling_is_reported_as_a_bad_list_not_ignored(self):
        self.assertErrorMentions(dagmod.validate_dag(make_dag(scope_ceiling=None)),
                                 "scope_ceiling must be a list")

    def test_duplicate_slice_ids(self):
        d = make_dag(slices=[sl("s1"), sl("s1")])
        self.assertErrorMentions(dagmod.validate_dag(d), "duplicate slice id")

    def test_missing_slice_id(self):
        bad = sl("s1")
        del bad["id"]
        self.assertErrorMentions(dagmod.validate_dag(make_dag(slices=[bad])), "id")

    def test_unknown_dependency(self):
        d = make_dag(slices=[sl("s1", deps=["nope"])])
        self.assertErrorMentions(dagmod.validate_dag(d), "unknown slice")

    def test_self_dependency_is_a_cycle(self):
        d = make_dag(slices=[sl("s1", deps=["s1"])])
        self.assertErrorMentions(dagmod.validate_dag(d), "cycle")

    def test_dependency_cycle(self):
        d = make_dag(slices=[sl("s1", deps=["s2"]), sl("s2", deps=["s1"])])
        self.assertErrorMentions(dagmod.validate_dag(d), "cycle")

    def test_longer_dependency_cycle(self):
        d = make_dag(slices=[
            sl("s1", deps=["s3"]), sl("s2", deps=["s1"]), sl("s3", deps=["s2"]),
        ])
        self.assertErrorMentions(dagmod.validate_dag(d), "cycle")

    def test_depth_beyond_cap(self):
        d = make_dag(slices=[
            sl("s1", status="split"),
            sl("s1.1", depth=1, parent="s1", status="split"),
            sl("s1.1.1", depth=2, parent="s1.1", status="split"),
            sl("s1.1.1.1", depth=3, parent="s1.1.1"),
        ])
        self.assertErrorMentions(dagmod.validate_dag(d), "depth")

    def test_depth_at_cap_is_allowed(self):
        d = make_dag(slices=[
            sl("s1", status="split"),
            sl("s1.1", depth=1, parent="s1", status="split"),
            sl("s1.1.1", depth=2, parent="s1.1"),
        ])
        self.assertEqual(dagmod.validate_dag(d), [])

    def test_parent_of_children_must_be_split(self):
        d = make_dag(slices=[sl("s1"), sl("s1.1", depth=1, parent="s1")])
        self.assertErrorMentions(dagmod.validate_dag(d), "split")

    def test_unknown_parent_id(self):
        d = make_dag(slices=[sl("s9.1", depth=1, parent="s9")])
        self.assertErrorMentions(dagmod.validate_dag(d), "unknown parent")

    def test_child_depth_must_be_parent_depth_plus_one(self):
        d = make_dag(slices=[
            sl("s1", status="split"), sl("s1.1", depth=2, parent="s1"),
        ])
        self.assertErrorMentions(dagmod.validate_dag(d), "depth")

    def test_unknown_slice_status(self):
        d = make_dag(slices=[sl("s1", status="FAILED")])
        self.assertErrorMentions(dagmod.validate_dag(d), "status")

    def test_bad_risk_tier(self):
        d = make_dag(slices=[sl("s1", risk_tier=7)])
        self.assertErrorMentions(dagmod.validate_dag(d), "risk_tier")

    def test_wave_slice_ids_must_exist(self):
        d = make_dag(waves=[wave(1, ["s1", "ghost"])])
        self.assertErrorMentions(dagmod.validate_dag(d), "unknown slice")

    def test_wave_status_enum(self):
        d = make_dag(waves=[wave(1, ["s1"], status="running")])
        self.assertErrorMentions(dagmod.validate_dag(d), "status")

    def test_duplicate_wave_index(self):
        d = make_dag(waves=[wave(1, ["s1"]), wave(1, ["s2"])])
        self.assertErrorMentions(dagmod.validate_dag(d), "duplicate wave index")

    def test_wave_index_must_be_one_based(self):
        d = make_dag(waves=[wave(0, ["s1"])])
        self.assertErrorMentions(dagmod.validate_dag(d), "index")

    def test_all_errors_are_reported_together(self):
        d = make_dag(schema_version=1, slices=[sl("s1", deps=["ghost"], status="weird")])
        self.assertGreaterEqual(len(dagmod.validate_dag(d)), 3)

    def test_waves_must_be_a_list(self):
        self.assertErrorMentions(dagmod.validate_dag(make_dag(waves={})), "waves")

    def test_depth_must_be_an_integer(self):
        d = make_dag(slices=[sl("s1", depth="zero")])
        self.assertErrorMentions(dagmod.validate_dag(d), "depth")

    def test_deps_must_be_a_list(self):
        d = make_dag(slices=[dict(sl("s1"), deps="s2")])
        self.assertErrorMentions(dagmod.validate_dag(d), "deps")

    def test_wave_slice_ids_must_be_a_list(self):
        d = make_dag(waves=[{"index": 1, "slice_ids": "s1", "status": "dispatched",
                             "workflow_run_id": None}])
        self.assertErrorMentions(dagmod.validate_dag(d), "slice_ids")


# --------------------------------------------------------------------------
# next_wave — pure
# --------------------------------------------------------------------------

class TestNextWave(unittest.TestCase):
    def test_first_wave_is_index_one(self):
        report = dagmod.next_wave(make_dag())
        self.assertEqual(report["index"], 1)
        self.assertEqual(report["slice_ids"], ["s1"])

    def test_index_follows_last_recorded_wave(self):
        d = make_dag(slices=[sl("s1", status="complete"), sl("s2", deps=["s1"])],
                     waves=[wave(1, ["s1"], status="collected")])
        report = dagmod.next_wave(d)
        self.assertEqual(report["index"], 2)
        self.assertEqual(report["slice_ids"], ["s2"])

    def test_multiple_independent_slices_share_a_wave(self):
        d = make_dag(slices=[sl("a"), sl("b"), sl("c", deps=["a", "b"])])
        self.assertEqual(dagmod.next_wave(d)["slice_ids"], ["a", "b"])

    def test_slice_order_follows_dag_order(self):
        d = make_dag(slices=[sl("z"), sl("a")])
        self.assertEqual(dagmod.next_wave(d)["slice_ids"], ["z", "a"])

    def test_partially_satisfied_deps_block(self):
        d = make_dag(slices=[
            sl("a", status="complete"), sl("b"), sl("c", deps=["a", "b"]),
        ])
        self.assertEqual(dagmod.next_wave(d)["slice_ids"], ["b"])

    def test_split_parent_is_never_scheduled(self):
        d = make_dag(slices=[
            sl("s1", status="split"),
            sl("s1.1", depth=1, parent="s1"),
        ])
        self.assertEqual(dagmod.next_wave(d)["slice_ids"], ["s1.1"])

    def test_dep_on_split_parent_satisfied_when_children_complete(self):
        d = make_dag(slices=[
            sl("s1", status="split"),
            sl("s1.1", depth=1, parent="s1", status="complete"),
            sl("s1.2", depth=1, parent="s1", status="complete"),
            sl("s2", deps=["s1"]),
        ])
        self.assertEqual(dagmod.next_wave(d)["slice_ids"], ["s2"])

    def test_dep_on_split_parent_blocked_while_a_child_is_pending(self):
        d = make_dag(slices=[
            sl("s1", status="split"),
            sl("s1.1", depth=1, parent="s1", status="complete"),
            sl("s1.2", depth=1, parent="s1"),
            sl("s2", deps=["s1"]),
        ])
        report = dagmod.next_wave(d)
        self.assertEqual(report["slice_ids"], ["s1.2"])
        self.assertNotIn("deadlock", report)

    def test_dep_on_nested_split_parent(self):
        d = make_dag(slices=[
            sl("s1", status="split"),
            sl("s1.1", depth=1, parent="s1", status="split"),
            sl("s1.1.1", depth=2, parent="s1.1", status="complete"),
            sl("s1.2", depth=1, parent="s1", status="complete"),
            sl("s2", deps=["s1"]),
        ])
        self.assertEqual(dagmod.next_wave(d)["slice_ids"], ["s2"])

    def test_split_parent_without_children_never_satisfies(self):
        d = make_dag(slices=[sl("s1", status="split"), sl("s2", deps=["s1"])])
        report = dagmod.next_wave(d)
        self.assertEqual(report["slice_ids"], [])
        self.assertTrue(report["deadlock"])
        self.assertEqual([b["slice"] for b in report["blocked"]], ["s2"])

    def test_done_when_everything_is_terminal(self):
        d = make_dag(slices=[sl("s1", status="complete"), sl("s2", status="complete")],
                     waves=[wave(1, ["s1", "s2"], status="collected")])
        report = dagmod.next_wave(d)
        self.assertEqual(report["slice_ids"], [])
        self.assertTrue(report["done"])
        self.assertNotIn("deadlock", report)
        self.assertEqual(report["index"], 2)

    def test_done_with_no_slices_at_all(self):
        report = dagmod.next_wave(make_dag(slices=[]))
        self.assertTrue(report["done"])

    def test_deadlock_on_missing_dependency(self):
        d = make_dag(slices=[sl("s1", deps=["ghost"])])
        report = dagmod.next_wave(d)
        self.assertTrue(report["deadlock"])
        self.assertEqual(report["blocked"], [{"slice": "s1", "blocked_by": ["ghost"]}])

    def test_deadlock_on_cycle_does_not_hang(self):
        d = make_dag(slices=[sl("s1", deps=["s2"]), sl("s2", deps=["s1"])])
        report = dagmod.next_wave(d)
        self.assertTrue(report["deadlock"])
        self.assertEqual(len(report["blocked"]), 2)

    def test_blocked_lists_only_unsatisfied_deps(self):
        d = make_dag(slices=[
            sl("a", status="complete"), sl("b", deps=["a", "ghost"]),
        ])
        report = dagmod.next_wave(d)
        self.assertEqual(report["blocked"], [{"slice": "b", "blocked_by": ["ghost"]}])


# --------------------------------------------------------------------------
# project_waves — the whole remaining schedule, pure and read-only
# --------------------------------------------------------------------------

class TestProjectWaves(unittest.TestCase):
    def test_linear_chain_projects_one_slice_per_wave(self):
        d = make_dag(slices=[sl("a"), sl("b", deps=["a"]), sl("c", deps=["b"])])
        self.assertEqual(dagmod.project_waves(d), [
            {"index": 1, "slice_ids": ["a"]},
            {"index": 2, "slice_ids": ["b"]},
            {"index": 3, "slice_ids": ["c"]},
        ])

    def test_diamond_projects_parallel_waves(self):
        d = make_dag(slices=[sl("a"), sl("b"), sl("c", deps=["a", "b"])])
        self.assertEqual(dagmod.project_waves(d), [
            {"index": 1, "slice_ids": ["a", "b"]},
            {"index": 2, "slice_ids": ["c"]},
        ])

    def test_numbering_continues_after_recorded_waves(self):
        d = make_dag(slices=[sl("a", status="complete"), sl("b", deps=["a"]),
                             sl("c", deps=["b"])],
                     waves=[wave(1, ["a"], status="collected")])
        self.assertEqual([w["index"] for w in dagmod.project_waves(d)], [2, 3])

    def test_first_projected_wave_matches_next_wave(self):
        d = make_dag(slices=[sl("a"), sl("b"), sl("c", deps=["a"])])
        report = dagmod.next_wave(d)
        first = dagmod.project_waves(d)[0]
        self.assertEqual((first["index"], first["slice_ids"]),
                         (report["index"], report["slice_ids"]))

    def test_input_dag_is_never_mutated(self):
        d = make_dag(slices=[sl("a"), sl("b", deps=["a"])])
        before = json.dumps(d, sort_keys=True)
        dagmod.project_waves(d)
        self.assertEqual(json.dumps(d, sort_keys=True), before)

    def test_split_children_are_projected_before_the_dependent(self):
        d = make_dag(slices=[
            sl("s1", status="split"),
            sl("s1.1", depth=1, parent="s1"),
            sl("s1.2", depth=1, parent="s1", deps=["s1.1"]),
            sl("s2", deps=["s1"]),
        ])
        self.assertEqual(dagmod.project_waves(d), [
            {"index": 1, "slice_ids": ["s1.1"]},
            {"index": 2, "slice_ids": ["s1.2"]},
            {"index": 3, "slice_ids": ["s2"]},
        ])

    def test_nothing_left_projects_nothing(self):
        d = make_dag(slices=[sl("a", status="complete"), sl("b", status="split"),
                             sl("b.1", depth=1, parent="b", status="complete"),
                             sl("b.2", depth=1, parent="b", status="complete")])
        self.assertEqual(dagmod.project_waves(d), [])

    def test_deadlocked_slices_are_simply_left_out(self):
        d = make_dag(slices=[sl("a"), sl("b", deps=["ghost"])])
        self.assertEqual(dagmod.project_waves(d), [{"index": 1, "slice_ids": ["a"]}])

    def test_limit_caps_a_pathological_graph(self):
        chain = [sl("s0")]
        for n in range(1, 6):
            chain.append(sl("s%d" % n, deps=["s%d" % (n - 1)]))
        self.assertEqual(len(dagmod.project_waves(make_dag(slices=chain), limit=3)), 3)


# --------------------------------------------------------------------------
# mutators — pure over the dict, raise ContractError when refused
# --------------------------------------------------------------------------

class TestRecordWave(unittest.TestCase):
    def test_appends_dispatched_wave(self):
        d = make_dag()
        recorded = dagmod.record_wave(d, 1, ["s1"], workflow_run_id="wf_abc")
        self.assertEqual(recorded, {"index": 1, "slice_ids": ["s1"],
                                    "workflow_run_id": "wf_abc",
                                    "status": "dispatched"})
        self.assertEqual(d["waves"], [recorded])

    def test_workflow_run_id_defaults_to_null(self):
        d = make_dag()
        self.assertIsNone(dagmod.record_wave(d, 1, ["s1"])["workflow_run_id"])

    def test_rejects_unknown_slice(self):
        d = make_dag()
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.record_wave(d, 1, ["ghost"])
        self.assertIn("unknown slice", " ".join(ctx.exception.errors))
        self.assertEqual(d["waves"], [])

    def test_rejects_duplicate_index(self):
        d = make_dag(waves=[wave(1, ["s1"])])
        with self.assertRaises(dagmod.ContractError):
            dagmod.record_wave(d, 1, ["s2"])

    def test_rejects_empty_slice_ids(self):
        with self.assertRaises(dagmod.ContractError):
            dagmod.record_wave(make_dag(), 1, [])

    def test_rejects_non_pending_slice(self):
        d = make_dag(slices=[sl("s1", status="complete")])
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.record_wave(d, 1, ["s1"])
        self.assertIn("pending", " ".join(ctx.exception.errors))

    def test_rejects_duplicate_ids_within_a_wave(self):
        with self.assertRaises(dagmod.ContractError):
            dagmod.record_wave(make_dag(), 1, ["s1", "s1"])

    def test_rejects_a_zero_index(self):
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.record_wave(make_dag(), 0, ["s1"])
        self.assertIn("1-based", " ".join(ctx.exception.errors))


class TestMark(unittest.TestCase):
    def test_mark_wave_collected(self):
        d = make_dag(waves=[wave(1, ["s1"])])
        self.assertEqual(dagmod.mark_wave(d, 1, "collected")["status"], "collected")
        self.assertEqual(d["waves"][0]["status"], "collected")

    def test_mark_wave_unknown_index(self):
        with self.assertRaises(dagmod.ContractError):
            dagmod.mark_wave(make_dag(), 3, "collected")

    def test_mark_wave_bad_status(self):
        d = make_dag(waves=[wave(1, ["s1"])])
        with self.assertRaises(dagmod.ContractError):
            dagmod.mark_wave(d, 1, "done")

    def test_mark_slice_complete(self):
        d = make_dag()
        self.assertEqual(dagmod.mark_slice(d, "s1", "complete")["status"], "complete")

    def test_mark_slice_unknown_id(self):
        with self.assertRaises(dagmod.ContractError):
            dagmod.mark_slice(make_dag(), "ghost", "complete")

    def test_mark_slice_bad_status(self):
        with self.assertRaises(dagmod.ContractError):
            dagmod.mark_slice(make_dag(), "s1", "DONE")

    def test_split_is_terminal_and_cannot_be_remarked(self):
        d = make_dag(slices=[sl("s1", status="split"), sl("s1.1", depth=1, parent="s1")])
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.mark_slice(d, "s1", "complete")
        self.assertIn("terminal", " ".join(ctx.exception.errors))

    def test_marking_complete_twice_is_idempotent(self):
        d = make_dag()
        dagmod.mark_slice(d, "s1", "complete")
        self.assertEqual(dagmod.mark_slice(d, "s1", "complete")["status"], "complete")


class TestIngestSplit(unittest.TestCase):
    def split(self, children):
        return {"children": children}

    def test_grafts_children_after_the_parent(self):
        d = make_dag(slices=[sl("s0", status="complete"),
                             sl("s1", deps=["s0"], risk_tier=3),
                             sl("s2", deps=["s1"])])
        children = dagmod.ingest_split(d, "s1", self.split([
            {"goal": "part one", "files": ["a.py"], "subsystems": ["api"],
             "internal_deps": []},
            {"goal": "part two", "files": ["b.py"], "subsystems": [],
             "internal_deps": [1]},
        ]))
        self.assertEqual([c["id"] for c in children], ["s1.1", "s1.2"])
        self.assertEqual([s["id"] for s in d["slices"]],
                         ["s0", "s1", "s1.1", "s1.2", "s2"])
        self.assertEqual(d["slices"][1]["status"], "split")
        first, second = children
        self.assertEqual(first["deps"], ["s0"])
        self.assertEqual(second["deps"], ["s0", "s1.1"])
        self.assertEqual(first["depth"], 1)
        self.assertEqual(first["parent"], "s1")
        self.assertEqual(first["risk_tier"], 3)
        self.assertEqual(first["status"], "pending")
        self.assertEqual(first["files"], ["a.py"])
        self.assertEqual(first["subsystems"], ["api"])

    def test_children_are_immediately_schedulable(self):
        d = make_dag(slices=[sl("s1"), sl("s2", deps=["s1"])])
        dagmod.ingest_split(d, "s1", self.split([{"goal": "a"}, {"goal": "b"}]))
        self.assertEqual(dagmod.validate_dag(d), [])
        self.assertEqual(dagmod.next_wave(d)["slice_ids"], ["s1.1", "s1.2"])

    def test_missing_internal_deps_key_defaults_to_empty(self):
        d = make_dag(slices=[sl("s1")])
        children = dagmod.ingest_split(d, "s1", self.split([{"goal": "only"}, {"goal": "second"}]))
        self.assertEqual(children[0]["deps"], [])

    def test_remediation_flag_is_inherited(self):
        d = make_dag(slices=[sl("s1", remediation=True)])
        children = dagmod.ingest_split(d, "s1", self.split([{"goal": "a"}, {"goal": "b"}]))
        self.assertTrue(children[0]["remediation"])

    def test_depth_one_parent_is_allowed(self):
        d = make_dag(slices=[sl("s1", status="split"), sl("s1.1", depth=1, parent="s1")])
        children = dagmod.ingest_split(d, "s1.1", self.split([{"goal": "a"}, {"goal": "b"}]))
        self.assertEqual(children[0]["id"], "s1.1.1")
        self.assertEqual(children[0]["depth"], 2)
        self.assertEqual(dagmod.validate_dag(d), [])

    def test_depth_cap_refuses_a_third_generation(self):
        d = make_dag(slices=[
            sl("s1", status="split"),
            sl("s1.1", depth=1, parent="s1", status="split"),
            sl("s1.1.1", depth=2, parent="s1.1"),
        ])
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(d, "s1.1.1", self.split([{"goal": "a"}, {"goal": "b"}]))
        self.assertIn("depth", " ".join(ctx.exception.errors))
        self.assertEqual(d["slices"][2]["status"], "pending")

    def test_unknown_parent(self):
        with self.assertRaises(dagmod.ContractError):
            dagmod.ingest_split(make_dag(), "ghost", self.split([{"goal": "a"}, {"goal": "b"}]))

    def test_parent_must_be_pending(self):
        d = make_dag(slices=[sl("s1", status="complete")])
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(d, "s1", self.split([{"goal": "a"}, {"goal": "b"}]))
        self.assertIn("pending", " ".join(ctx.exception.errors))

    def test_already_split_parent_is_refused(self):
        d = make_dag(slices=[sl("s1", status="split"), sl("s1.1", depth=1, parent="s1")])
        with self.assertRaises(dagmod.ContractError):
            dagmod.ingest_split(d, "s1", self.split([{"goal": "a"}, {"goal": "b"}]))

    def test_empty_children_refused(self):
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(make_dag(), "s1", self.split([]))
        self.assertIn("children", " ".join(ctx.exception.errors))

    def test_single_child_refused(self):
        # references/split-ingestion.md: fewer than two children is a malformed
        # proposal, not a decomposition.
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(make_dag(), "s1", self.split([{"goal": "only"}]))
        self.assertIn("at least 2 children", " ".join(ctx.exception.errors))

    def test_child_without_goal_refused(self):
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(make_dag(), "s1",
                                self.split([{"files": []}, {"goal": "b"}]))
        self.assertIn("child 1 has no goal", " ".join(ctx.exception.errors))

    def test_internal_dep_out_of_range(self):
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(make_dag(), "s1",
                                self.split([{"goal": "a", "internal_deps": [3]}, {"goal": "b"}]))
        self.assertIn("internal_deps", " ".join(ctx.exception.errors))

    def test_internal_dep_self_reference(self):
        with self.assertRaises(dagmod.ContractError):
            dagmod.ingest_split(make_dag(), "s1",
                                self.split([{"goal": "a", "internal_deps": [1]}, {"goal": "b"}]))

    def test_internal_dep_cycle(self):
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(make_dag(), "s1", self.split([
                {"goal": "a", "internal_deps": [2]},
                {"goal": "b", "internal_deps": [1]},
            ]))
        self.assertIn("cycle", " ".join(ctx.exception.errors))

    def test_non_integer_internal_dep(self):
        with self.assertRaises(dagmod.ContractError):
            dagmod.ingest_split(make_dag(), "s1",
                                self.split([{"goal": "a", "internal_deps": ["s2"]}, {"goal": "b"}]))

    def test_child_id_collision(self):
        d = make_dag(slices=[sl("s1"), sl("s1.1")])
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(d, "s1", self.split([{"goal": "a"}, {"goal": "b"}]))
        self.assertIn("s1.1", " ".join(ctx.exception.errors))

    def test_split_payload_must_be_an_object(self):
        with self.assertRaises(dagmod.ContractError):
            dagmod.ingest_split(make_dag(), "s1", [{"goal": "a"}, {"goal": "b"}])

    def test_child_must_be_an_object(self):
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(make_dag(), "s1", self.split(["just a string", {"goal": "b"}]))
        self.assertIn("child 1", " ".join(ctx.exception.errors))

    def test_internal_deps_must_be_a_list(self):
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(make_dag(), "s1",
                                self.split([{"goal": "a", "internal_deps": 2}, {"goal": "b"}]))
        self.assertIn("internal_deps", " ".join(ctx.exception.errors))

    def test_parent_without_a_usable_depth(self):
        d = make_dag(slices=[sl("s1", depth=None)])
        with self.assertRaises(dagmod.ContractError) as ctx:
            dagmod.ingest_split(d, "s1", self.split([{"goal": "a"}, {"goal": "b"}]))
        self.assertIn("depth", " ".join(ctx.exception.errors))

    def test_accepts_a_full_sidecar_as_the_split_payload(self):
        # The controller may hand over the whole SliceResult sidecar.
        d = make_dag(slices=[sl("s1")])
        children = dagmod.ingest_split(d, "s1", {
            "schema_version": 2, "id": "s1", "status": "SPLIT",
            "split": {"children": [{"goal": "a"}, {"goal": "b"}]},
        })
        self.assertEqual([c["id"] for c in children], ["s1.1", "s1.2"])


# --------------------------------------------------------------------------
# persistence + CLI
# --------------------------------------------------------------------------

class DagCliTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.run_dir = os.path.join(self.root, "docs", "spec-loop", "20260730-demo")
        os.makedirs(self.run_dir)

    def write(self, body):
        with open(os.path.join(self.run_dir, "dag.json"), "w", encoding="utf-8") as fh:
            json.dump(body, fh)

    def raw(self):
        with open(os.path.join(self.run_dir, "dag.json"), "r", encoding="utf-8") as fh:
            return fh.read()

    def read(self):
        return json.loads(self.raw())

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            code = dagmod.main(list(argv) + ["--run-dir", self.run_dir])
        payload = None
        if out.getvalue().strip():
            payload = json.loads(out.getvalue())
        return code, payload, err.getvalue()


class TestPersistence(DagCliTestCase):
    def test_write_dag_is_atomic_and_leaves_no_temp_files(self):
        self.write(make_dag())
        d = dagmod.load_dag(self.run_dir)
        dagmod.mark_slice(d, "s1", "complete")
        dagmod.write_dag(self.run_dir, d)
        self.assertEqual(self.read()["slices"][0]["status"], "complete")
        self.assertEqual(sorted(os.listdir(self.run_dir)), ["dag.json"])

    def test_write_dag_ends_with_a_newline(self):
        self.write(make_dag())
        dagmod.write_dag(self.run_dir, dagmod.load_dag(self.run_dir))
        self.assertTrue(self.raw().endswith("\n"))

    def test_load_missing_file_raises(self):
        with self.assertRaises(dagmod.DagError):
            dagmod.load_dag(self.run_dir)

    def test_write_failure_becomes_a_dag_error(self):
        self.write(make_dag())
        d = dagmod.load_dag(self.run_dir)
        with mock.patch.object(dagmod.os, "replace", side_effect=OSError("read-only")):
            with self.assertRaises(dagmod.DagError):
                dagmod.write_dag(self.run_dir, d)
        self.assertEqual(sorted(os.listdir(self.run_dir)), ["dag.json"])

    def test_load_half_written_file_raises(self):
        with open(os.path.join(self.run_dir, "dag.json"), "w", encoding="utf-8") as fh:
            fh.write('{"schema_version": 2, "slic')
        with self.assertRaises(dagmod.DagError):
            dagmod.load_dag(self.run_dir)


class TestCli(DagCliTestCase):
    def test_validate_ok(self):
        self.write(make_dag())
        code, payload, _ = self.cli("validate")
        self.assertEqual(code, 0)
        self.assertEqual(payload, {"ok": True, "errors": []})

    def test_validate_failure_is_exit_one(self):
        self.write(make_dag(schema_version=1))
        code, payload, _ = self.cli("validate")
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["errors"])

    def test_unreadable_dag_is_exit_two(self):
        code, payload, err = self.cli("validate")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)
        self.assertIn("error:", err)

    def test_next_wave_prints_report(self):
        self.write(make_dag())
        code, payload, _ = self.cli("next-wave")
        self.assertEqual(code, 0)
        self.assertEqual(payload, {"index": 1, "slice_ids": ["s1"]})

    def test_next_wave_done_is_exit_zero(self):
        self.write(make_dag(slices=[sl("s1", status="complete")]))
        code, payload, _ = self.cli("next-wave")
        self.assertEqual(code, 0)
        self.assertTrue(payload["done"])

    def test_next_wave_deadlock_is_exit_one(self):
        self.write(make_dag(slices=[sl("s1", deps=["ghost"])]))
        code, payload, _ = self.cli("next-wave")
        self.assertEqual(code, 1)
        self.assertTrue(payload["deadlock"])

    def test_record_wave_round_trip(self):
        self.write(make_dag())
        code, payload, _ = self.cli("record-wave", "--index", "1",
                                    "--slice-ids", "s1", "--workflow-run-id", "wf_1")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(self.read()["waves"],
                         [{"index": 1, "slice_ids": ["s1"],
                           "workflow_run_id": "wf_1", "status": "dispatched"}])

    def test_record_wave_tolerates_spaces_in_slice_ids(self):
        self.write(make_dag(slices=[sl("s1"), sl("s2")]))
        code, _, _ = self.cli("record-wave", "--index", "1", "--slice-ids", "s1, s2")
        self.assertEqual(code, 0)
        self.assertEqual(self.read()["waves"][0]["slice_ids"], ["s1", "s2"])

    def test_refused_record_wave_leaves_dag_untouched(self):
        self.write(make_dag())
        before = self.raw()
        code, payload, _ = self.cli("record-wave", "--index", "1", "--slice-ids", "ghost")
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(self.raw(), before)

    def test_mark_wave_collected(self):
        self.write(make_dag(waves=[wave(1, ["s1"])]))
        code, payload, _ = self.cli("mark", "--wave", "1", "--status", "collected")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(self.read()["waves"][0]["status"], "collected")

    def test_mark_slice_complete(self):
        self.write(make_dag())
        code, _, _ = self.cli("mark", "--slice", "s1", "--status", "complete")
        self.assertEqual(code, 0)
        self.assertEqual(self.read()["slices"][0]["status"], "complete")

    def test_mark_requires_a_target(self):
        self.write(make_dag())
        with self.assertRaises(SystemExit) as ctx:
            self.cli("mark", "--status", "complete")
        self.assertEqual(ctx.exception.code, 2)

    def test_mark_refuses_both_targets(self):
        self.write(make_dag(waves=[wave(1, ["s1"])]))
        with self.assertRaises(SystemExit):
            self.cli("mark", "--wave", "1", "--slice", "s1", "--status", "complete")

    def test_ingest_split_from_file(self):
        self.write(make_dag(slices=[sl("s1"), sl("s2", deps=["s1"])]))
        path = os.path.join(self.root, "slice-s1-split.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"children": [{"goal": "a"},
                                    {"goal": "b", "internal_deps": [1]}]}, fh)
        code, payload, _ = self.cli("ingest-split", "--slice", "s1", "--file", path)
        self.assertEqual(code, 0)
        self.assertEqual(payload["children"], ["s1.1", "s1.2"])
        after = self.read()
        self.assertEqual([s["id"] for s in after["slices"]],
                         ["s1", "s1.1", "s1.2", "s2"])
        self.assertEqual(after["slices"][0]["status"], "split")

    def test_ingest_split_reads_stdin(self):
        self.write(make_dag(slices=[sl("s1")]))
        payload_in = json.dumps({"children": [{"goal": "a"}, {"goal": "b"}]})
        with mock.patch("sys.stdin", io.StringIO(payload_in)):
            code, payload, _ = self.cli("ingest-split", "--slice", "s1", "--file", "-")
        self.assertEqual(code, 0)
        self.assertEqual(payload["children"], ["s1.1", "s1.2"])

    def test_ingest_split_malformed_json_is_exit_two(self):
        self.write(make_dag())
        path = os.path.join(self.root, "split.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        code, _, err = self.cli("ingest-split", "--slice", "s1", "--file", path)
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err)

    def test_ingest_split_missing_file_is_exit_two(self):
        self.write(make_dag())
        code, _, err = self.cli("ingest-split", "--slice", "s1",
                                "--file", os.path.join(self.root, "nope.json"))
        self.assertEqual(code, 2)
        self.assertIn("error:", err)

    def test_refused_ingest_leaves_dag_untouched(self):
        self.write(make_dag(slices=[sl("s1", status="complete")]))
        before = self.raw()
        path = os.path.join(self.root, "split.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"children": [{"goal": "a"}, {"goal": "b"}]}, fh)
        code, payload, _ = self.cli("ingest-split", "--slice", "s1", "--file", path)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(self.raw(), before)

    def test_mutation_refused_when_the_dag_is_invalid(self):
        # Fail closed: never write on top of a dag that already breaks contract.
        self.write(make_dag(schema_version=1))
        before = self.raw()
        code, payload, _ = self.cli("mark", "--slice", "s1", "--status", "complete")
        self.assertEqual(code, 1)
        self.assertIn("schema_version", " ".join(payload["errors"]))
        self.assertEqual(self.raw(), before)

    def test_a_dag_without_scope_ceiling_validates_and_still_marks(self):
        # scope_ceiling is optional: a pre-existing run with no ceiling must stay
        # contract-valid, so _load_for_mutation still lets `mark` through
        # (run 20260825-scope-ceiling).
        body = make_dag()
        self.assertNotIn("scope_ceiling", body)
        self.write(body)
        code, payload, _ = self.cli("validate")
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        code, _, _ = self.cli("mark", "--slice", "s1", "--status", "complete")
        self.assertEqual(code, 0)
        self.assertEqual(self.read()["slices"][0]["status"], "complete")
        self.assertNotIn("scope_ceiling", self.read())

    def test_a_dag_with_a_malformed_scope_ceiling_refuses_to_mark(self):
        self.write(make_dag(scope_ceiling="not a list"))
        before = self.raw()
        code, payload, _ = self.cli("mark", "--slice", "s1", "--status", "complete")
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertTrue(any("scope_ceiling" in e for e in payload["errors"]))
        self.assertEqual(self.raw(), before)

    def test_unknown_subcommand_is_usage_error(self):
        with self.assertRaises(SystemExit):
            self.cli("frobnicate")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
