"""Tests for spec_loop_guard.py's Stop loop-boundary gate.

Split out of test_spec_loop_guard.py (which keeps the PreToolUse coverage)
purely to stay under the per-file class_lines ceiling; GuardTestCase is the
shared fixture base for both files. Standard library only; no live git
required (current_branch is patched).
"""

import io
import json
import os
import sys
import unittest
from unittest import mock

import run_state
import spec_loop_guard as guard
from test_spec_loop_guard import GuardTestCase

PENDING = [{"id": "s4", "status": "pending", "deps": []}]
DEADLOCKED = [
    {"id": "s4", "status": "pending", "deps": ["s9"]},
    {"id": "s9", "status": "pending", "deps": ["s4"]},
]
ALL_DONE = [{"id": "s1", "status": "complete", "deps": []}]


def _remediation_sentence(run_id):
    """The exact _remediation() text every denial and block ends with."""
    return guard._remediation({"run_id": run_id})


class StopGateTests(GuardTestCase):
    def test_runnable_slice_blocks_the_controller_turn(self):
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        reason = guard.evaluate(self.stop(session_id="sess-ctl"))
        self.assertIsNotNone(reason)
        self.assertIn("s4", reason)

    def test_stop_payload_has_no_tool_name_and_still_dispatches(self):
        # Regression guard for the silent no-op: an implementation that keys
        # off tool_name never fires live, because Stop carries no such key.
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        payload = self.stop(session_id="sess-ctl")
        self.assertNotIn("tool_name", payload)
        self.assertIsNotNone(guard.evaluate(payload))

    def test_deadlock_allows(self):
        # next_wave reports {'slice_ids': [], 'deadlock': True} with NO 'done'
        # key: the deadlock escalation question must be askable.
        self.make_run(slices=DEADLOCKED, controller_session="sess-ctl")
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_done_allows_the_publish_prompt(self):
        self.make_run(slices=ALL_DONE, controller_session="sess-ctl")
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_other_session_not_blocked(self):
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-other")))

    def test_labelled_marker_still_matches(self):
        # Matching is substring-tolerant: a marker written with a label or
        # extra lines must still narrow to the same session. It can never
        # match a session whose id is absent from the file.
        self.make_run(
            slices=PENDING,
            controller_session="session_id: sess-ctl (controller)",
        )
        self.assertIsNotNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_missing_controller_session_marker_allows(self):
        self.make_run(slices=PENDING)
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_empty_controller_session_marker_allows(self):
        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
        with open(os.path.join(run_dir, ".controller-session"), "w") as fh:
            fh.write("   \n")
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_payload_without_session_id_allows(self):
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        payload = self.stop()
        del payload["session_id"]
        self.assertIsNone(guard.evaluate(payload))

    def test_open_escalation_allows(self):
        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
        with open(os.path.join(run_dir, "events.jsonl"), "w") as fh:
            fh.write(json.dumps({
                "ts": "2026-09-04T00:00:00Z", "scope": "run",
                "type": "escalation-opened",
                "payload": {"id": "esc-1", "trigger": "ambiguity", "status": "OPEN"},
            }) + "\n")
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_answered_escalation_still_blocks(self):
        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
        with open(os.path.join(run_dir, "events.jsonl"), "w") as fh:
            for event in (
                {"ts": "2026-09-04T00:00:00Z", "scope": "run", "type": "escalation-opened",
                 "payload": {"id": "esc-1", "trigger": "ambiguity", "status": "OPEN"}},
                {"ts": "2026-09-04T00:01:00Z", "scope": "run", "type": "escalation-answered",
                 "payload": {"id": "esc-1", "answer": "option a"}},
            ):
                fh.write(json.dumps(event) + "\n")
        self.assertIsNotNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_no_active_run_allows(self):
        self.make_run(active=False, slices=PENDING, controller_session="sess-ctl")
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))


class StopGateFailOpenTests(GuardTestCase):
    def test_stop_hook_active_allows(self):
        # Empirically (2026-09-04, CC 2.1.260) stop_hook_active is true only
        # on the fire that ends the continuation a block caused, and resets
        # on every new user turn: honouring it makes the gate one push per
        # stop attempt, re-armed per turn, never a fence.
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        self.assertIsNone(
            guard.evaluate(self.stop(session_id="sess-ctl", stop_hook_active=True))
        )

    def test_paused_marker_allows_the_stop_gate(self):
        self.make_run(slices=PENDING, controller_session="sess-ctl", paused=True)
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_paused_marker_does_not_unlock_push_or_main_commits(self):
        # .paused relaxes the loop-boundary gate ALONE. If it leaked into
        # find_active_runs it would silently unlock push-before-publish,
        # broad staging and default-branch commits.
        self.make_run(slices=PENDING, controller_session="sess-ctl", paused=True)
        self.assertIsNotNone(guard.evaluate(self.bash("git push")))
        self.assertIsNotNone(guard.evaluate(self.bash("git add -A")))
        self.branch_mock.return_value = "main"
        self.assertIsNotNone(guard.evaluate(self.bash("git commit -m x")))

    def test_active_marker_without_dag_json_allows(self):
        # Reachable state: find_active_runs tolerates it, dag.load_dag
        # raises DagError on it, and the gate must fail OPEN there.
        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
        os.unlink(os.path.join(run_dir, "dag.json"))
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_half_written_dag_json_allows(self):
        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
        with open(os.path.join(run_dir, "dag.json"), "w") as fh:
            fh.write('{"slices": [')
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_broken_run_does_not_fail_open_for_a_healthy_run(self):
        # Two active runs: run-a's dag.json is missing, run-b is runnable
        # and controlled by this session. The gate must still block. If this
        # fails, the implementation put ONE try around the whole loop.
        broken = self.make_run("20260901-run-a", controller_session="sess-ctl")
        os.unlink(os.path.join(broken, "dag.json"))
        self.make_run("20260902-run-b", slices=PENDING, controller_session="sess-ctl")
        reason = guard.evaluate(self.stop(session_id="sess-ctl"))
        self.assertIsNotNone(reason)
        self.assertIn("20260902-run-b", reason)

    def test_stale_other_run_is_skipped_not_blamed(self):
        # A stale .active owned by a different session must not block this one.
        self.make_run("20260901-stale", slices=PENDING, controller_session="sess-old")
        self.make_run("20260902-mine", slices=ALL_DONE, controller_session="sess-ctl")
        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_import_error_on_dag_allows(self):
        # A None entry in sys.modules makes `import dag` raise ImportError
        # ("import of dag halted; None in sys.modules") — the standard idiom,
        # and unlike patching builtins.__import__ it intercepts nothing else.
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        with mock.patch.dict(sys.modules, {"dag": None}):
            self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_import_error_on_run_state_allows(self):
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        with mock.patch.dict(sys.modules, {"run_state": None}):
            self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_open_escalations_raising_allows(self):
        # Exercises the REAL defensive branch in _has_open_escalation by
        # patching the dependency (run_state.open_escalations), not the
        # function under test. open_escalations does not raise for a missing
        # or unreadable events.jsonl, so this is the only way to reach it.
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        with mock.patch.object(run_state, "open_escalations", side_effect=OSError):
            self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))

    def test_pretooluse_bash_and_write_unaffected_by_the_stop_branch(self):
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        self.assertIsNotNone(guard.evaluate(self.bash("git push")))
        self.assertIsNotNone(
            guard.evaluate(self.write(os.path.expanduser(guard.QUALITY_GATE_CONFIG)))
        )
        self.assertIsNone(guard.evaluate(self.bash("ls -la")))
        self.assertIsNone(guard.evaluate(self.write("/tmp/notes.md")))


class StopEmitTests(GuardTestCase):
    def _run_main(self, payload):
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
            with mock.patch("sys.stdout", io.StringIO()) as out:
                self.assertEqual(guard.main(), 0)
        return out.getvalue()

    def test_stop_block_uses_the_top_level_decision_shape(self):
        # Reusing the PreToolUse hookSpecificOutput shape produces a
        # malformed block that the harness ignores, which reads as allow.
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        emitted = json.loads(self._run_main(self.stop(session_id="sess-ctl")))
        self.assertEqual(emitted["decision"], "block")
        self.assertIn("s4", emitted["reason"])
        self.assertNotIn("hookSpecificOutput", emitted)

    def test_stop_allow_is_silent(self):
        self.make_run(slices=ALL_DONE, controller_session="sess-ctl")
        self.assertEqual(self._run_main(self.stop(session_id="sess-ctl")), "")

    def test_pretooluse_deny_still_uses_hook_specific_output(self):
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        emitted = json.loads(self._run_main(self.bash("git push")))
        self.assertNotIn("decision", emitted)
        self.assertEqual(
            emitted["hookSpecificOutput"]["hookEventName"], "PreToolUse"
        )
        self.assertEqual(emitted["hookSpecificOutput"]["permissionDecision"], "deny")


class StopReasonTextTests(GuardTestCase):
    def _reason(self):
        self.make_run(slices=PENDING, controller_session="sess-ctl")
        reason = guard.evaluate(self.stop(session_id="sess-ctl"))
        self.assertIsNotNone(reason)
        return reason

    def test_reason_names_the_runnable_slices_and_the_compliant_alternative(self):
        reason = self._reason()
        self.assertIn("s4", reason)
        self.assertIn("Phase 2 step 1", reason)

    def test_reason_warns_against_re_dispatching_an_in_flight_wave(self):
        # dag has no in-flight status (SLICE_STATUSES is pending/complete/
        # split) and record_wave leaves slices pending, so a dispatched-but-
        # uncollected wave still reads as runnable. The push must not be
        # readable as an order to double-dispatch.
        reason = self._reason()
        self.assertIn("still in flight", reason)
        self.assertIn("rather than re-dispatching", reason)

    def test_reason_names_the_literal_paused_path(self):
        self.assertIn("docs/spec-loop/20260707-demo/.paused", self._reason())

    def test_reason_carries_the_not_the_controller_clause(self):
        self.assertIn("not the controller", self._reason())

    def test_reason_demands_a_visible_trace(self):
        self.assertIn("say why in your next message", self._reason())

    def test_reason_ends_with_the_standard_remediation_sentence(self):
        reason = self._reason()
        self.assertTrue(
            reason.endswith(_remediation_sentence("20260707-demo")), reason
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
