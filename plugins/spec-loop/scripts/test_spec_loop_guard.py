"""Tests for spec_loop_guard.py.

Standard library only; no live git required (current_branch is patched).
Builds throwaway run-state directories with tempfile and drives evaluate()
plus the CLI entry with fixture hook payloads.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import run_state
import spec_loop_guard as guard


class GuardTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        env = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.root})
        env.start()
        self.addCleanup(env.stop)
        # Default: no git subprocess in tests; feature branch unless overridden.
        branch = mock.patch.object(guard, "current_branch", return_value="csv-export")
        self.branch_mock = branch.start()
        self.addCleanup(branch.stop)

    def make_run(self, run_id="20260707-demo", active=True, publish_choice=False,
                 merge_mode="single-branch", base_ref="csv-export",
                 slices=(), controller_session=None, paused=False):
        run_dir = os.path.join(self.root, "docs", "spec-loop", run_id)
        os.makedirs(run_dir, exist_ok=True)
        if active:
            with open(os.path.join(run_dir, ".active"), "w") as fh:
                fh.write("2026-07-07T00:00:00 " + run_id)
        if publish_choice:
            with open(os.path.join(run_dir, ".publish-choice"), "w") as fh:
                fh.write("push-feature-branch")
        if controller_session:
            with open(os.path.join(run_dir, ".controller-session"), "w") as fh:
                fh.write(controller_session + "\n")
        if paused:
            with open(os.path.join(run_dir, ".paused"), "w") as fh:
                fh.write("human asked to hold\n")
        with open(os.path.join(run_dir, "dag.json"), "w") as fh:
            json.dump(
                {"base_ref": base_ref, "merge_mode": merge_mode, "slices": list(slices)}, fh
            )
        return run_dir

    @staticmethod
    def bash(command, cwd="/tmp/wt"):
        return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}

    @staticmethod
    def write(file_path):
        return {"tool_name": "Write", "tool_input": {"file_path": file_path}, "cwd": "/tmp"}

    @staticmethod
    def stop(session_id="sess-ctl", stop_hook_active=False, cwd="/tmp/wt"):
        """A realistic Stop payload: the probed key set, and NO tool_name."""
        return {
            "hook_event_name": "Stop",
            "session_id": session_id,
            "stop_hook_active": stop_hook_active,
            "cwd": cwd,
            "transcript_path": "/tmp/transcript.jsonl",
            "last_assistant_message": "Wave 1 merged. Here is a status report.",
            "permission_mode": "acceptEdits",
            "prompt_id": "p-1",
            "background_tasks": [],
            "session_crons": [],
        }


class NoActiveRunTests(GuardTestCase):
    def test_everything_allowed_without_marker(self):
        self.make_run(active=False)
        self.assertIsNone(guard.evaluate(self.bash("git push")))
        self.assertIsNone(guard.evaluate(self.bash("git add -A")))
        self.assertIsNone(
            guard.evaluate(self.write(os.path.expanduser(guard.QUALITY_GATE_CONFIG)))
        )


PENDING = [{"id": "s4", "status": "pending", "deps": []}]
DEADLOCKED = [
    {"id": "s4", "status": "pending", "deps": ["s9"]},
    {"id": "s9", "status": "pending", "deps": ["s4"]},
]
ALL_DONE = [{"id": "s1", "status": "complete", "deps": []}]


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
        self.make_run(slices=PENDING,
                      controller_session="session_id: sess-ctl (controller)")
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


class PushRuleTests(GuardTestCase):
    def test_bare_push_denied(self):
        self.make_run()
        reason = guard.evaluate(self.bash("git push"))
        self.assertIn("publish prompt", reason)
        self.assertIn("--resume 20260707-demo", reason)

    def test_push_of_integration_branch_denied(self):
        self.make_run(base_ref="csv-export")
        self.assertIsNotNone(guard.evaluate(self.bash("git push origin csv-export")))

    def test_push_of_spec_loop_branch_denied(self):
        self.make_run()
        self.assertIsNotNone(
            guard.evaluate(self.bash("git push origin spec-loop/20260707-demo/s1"))
        )

    def test_push_of_integration_namespace_denied_without_dag(self):
        # dag.json unreadable → base_ref unknown → the spec-loop-run/ default
        # integration namespace must still be recognized as run-owned.
        run_dir = self.make_run()
        os.unlink(os.path.join(run_dir, "dag.json"))
        self.assertIsNotNone(
            guard.evaluate(self.bash("git push origin spec-loop-run/20260707-demo"))
        )

    def test_push_of_unrelated_branch_allowed(self):
        self.make_run(base_ref="csv-export")
        self.assertIsNone(guard.evaluate(self.bash("git push origin hotfix-typo")))

    def test_push_allowed_after_publish_choice(self):
        self.make_run(publish_choice=True)
        self.assertIsNone(guard.evaluate(self.bash("git push")))

    def test_push_allowed_in_per_slice_pr_mode(self):
        self.make_run(merge_mode="per-slice-pr")
        self.assertIsNone(guard.evaluate(self.bash("git push -u origin spec-loop/20260707-demo/s1")))

    def test_push_denied_when_any_run_blocks(self):
        self.make_run("run-a", merge_mode="per-slice-pr")
        self.make_run("run-b")
        self.assertIsNotNone(guard.evaluate(self.bash("git push")))

    def test_git_dash_c_push_denied(self):
        self.make_run()
        self.assertIsNotNone(guard.evaluate(self.bash("git -C /some/dir push")))


class BroadStagingTests(GuardTestCase):
    def test_add_all_variants_denied(self):
        self.make_run()
        for cmd in ("git add -A", "git add --all", "git add .", "git add . && git commit -m x"):
            reason = guard.evaluate(self.bash(cmd))
            self.assertIsNotNone(reason, cmd)
            self.assertIn("git add -- docs/spec-loop/20260707-demo/", reason)

    def test_scoped_add_allowed(self):
        self.make_run()
        self.assertIsNone(
            guard.evaluate(self.bash("git add -- docs/spec-loop/20260707-demo/"))
        )
        self.assertIsNone(guard.evaluate(self.bash("git add src/app.py")))

    def test_broad_add_denied_even_after_publish_choice(self):
        # Publish choice covers push/main, not sloppy staging.
        self.make_run(publish_choice=True)
        self.assertIsNotNone(guard.evaluate(self.bash("git add -A")))


class MainBranchTests(GuardTestCase):
    def test_commit_on_main_denied(self):
        self.make_run()
        self.branch_mock.return_value = "main"
        reason = guard.evaluate(self.bash("git commit -m 'oops'"))
        self.assertIn("main/master", reason)

    def test_merge_on_master_denied(self):
        self.make_run()
        self.branch_mock.return_value = "master"
        self.assertIsNotNone(guard.evaluate(self.bash("git merge --no-ff csv-export")))

    def test_commit_on_feature_branch_allowed(self):
        self.make_run()
        self.assertIsNone(guard.evaluate(self.bash("git commit -m 'slice work'")))

    def test_compound_checkout_main_and_merge_denied(self):
        self.make_run()
        self.assertIsNotNone(
            guard.evaluate(self.bash("git checkout main && git merge --no-ff csv-export"))
        )

    def test_compound_switch_master_and_push_denied(self):
        self.make_run()
        self.assertIsNotNone(guard.evaluate(self.bash("git switch master && git push")))

    def test_checkout_main_alone_allowed(self):
        self.make_run()
        self.assertIsNone(guard.evaluate(self.bash("git checkout main")))

    def test_publish_choice_unlocks_main(self):
        self.make_run(publish_choice=True)
        self.branch_mock.return_value = "main"
        self.assertIsNone(
            guard.evaluate(self.bash("git checkout main && git merge --no-ff csv-export"))
        )


class QualityGateConfigTests(GuardTestCase):
    def test_bash_overwrite_denied(self):
        self.make_run()
        for cmd in (
            "echo '{}' > ~/.claude/spec-loop-2/quality-gate.json",
            "sed -i '' 's/10/99/' ~/.claude/spec-loop-2/quality-gate.json",
            "cp /tmp/x ~/.claude/spec-loop-2/quality-gate.json",
            "echo '{}' > .spec-loop/quality-gate.json",
        ):
            self.assertIsNotNone(guard.evaluate(self.bash(cmd)), cmd)

    def test_bash_read_allowed(self):
        self.make_run()
        self.assertIsNone(
            guard.evaluate(self.bash("cat ~/.claude/spec-loop-2/quality-gate.json"))
        )

    def test_readonly_gate_invocation_with_stderr_redirect_allowed(self):
        # Regression (run 20260807-upsell-lines-invoice-status): the verifier's
        # read-only gate command was denied because `2>&1` matched the old
        # any-redirect heuristic, cascading into false PASS labels downstream.
        self.make_run()
        cmd = (
            "python3 scripts/quality_gate.py "
            "--config ~/.claude/spec-loop-2/quality-gate.json "
            "--overlay .spec-loop/quality-gate.json "
            "--base abc123 --head def456 --repo-dir /tmp/wt 2>&1"
        )
        self.assertIsNone(guard.evaluate(self.bash(cmd)))

    def test_readonly_gate_invocation_redirected_elsewhere_allowed(self):
        self.make_run()
        cmd = (
            "python3 scripts/quality_gate.py "
            "--config ~/.claude/spec-loop-2/quality-gate.json "
            "--base abc123 --head def456 > /tmp/gate-out.json"
        )
        self.assertIsNone(guard.evaluate(self.bash(cmd)))

    def test_tee_append_move_into_config_denied(self):
        self.make_run()
        for cmd in (
            "cat /tmp/x | tee .spec-loop/quality-gate.json",
            "echo '{}' >> ~/.claude/spec-loop-2/quality-gate.json",
            "mv /tmp/x .spec-loop/quality-gate.json",
        ):
            self.assertIsNotNone(guard.evaluate(self.bash(cmd)), cmd)

    def test_write_tool_denied(self):
        self.make_run()
        reason = guard.evaluate(self.write("~/.claude/spec-loop-2/quality-gate.json"))
        self.assertIn("quality-gate.json", reason)

    def test_write_tool_repo_overlay_denied(self):
        self.make_run()
        overlay = os.path.join(self.root, ".spec-loop", "quality-gate.json")
        reason = guard.evaluate(self.write(overlay))
        self.assertIn("quality-gate.json", reason)

    def test_write_tool_other_files_allowed(self):
        self.make_run()
        self.assertIsNone(guard.evaluate(self.write("/tmp/notes.md")))


class RobustnessTests(GuardTestCase):
    def test_missing_dag_json_still_guards(self):
        run_dir = self.make_run()
        os.unlink(os.path.join(run_dir, "dag.json"))
        self.assertIsNotNone(guard.evaluate(self.bash("git push")))

    def test_other_tools_ignored(self):
        self.make_run()
        self.assertIsNone(
            guard.evaluate({"tool_name": "Read", "tool_input": {"file_path": "x"}, "cwd": "/"})
        )

    def test_main_fail_open_on_garbage_stdin(self):
        with mock.patch("sys.stdin", io.StringIO("not json")):
            with mock.patch("sys.stdout", io.StringIO()) as out:
                self.assertEqual(guard.main(), 0)
        self.assertEqual(out.getvalue(), "")

    def test_main_emits_deny_json(self):
        self.make_run()
        payload = json.dumps(self.bash("git push"))
        with mock.patch("sys.stdin", io.StringIO(payload)):
            with mock.patch("sys.stdout", io.StringIO()) as out:
                self.assertEqual(guard.main(), 0)
        decision = json.loads(out.getvalue())["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("publish prompt", decision["permissionDecisionReason"])

    def test_main_silent_allow(self):
        self.make_run(active=False)
        payload = json.dumps(self.bash("git push"))
        with mock.patch("sys.stdin", io.StringIO(payload)):
            with mock.patch("sys.stdout", io.StringIO()) as out:
                self.assertEqual(guard.main(), 0)
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
