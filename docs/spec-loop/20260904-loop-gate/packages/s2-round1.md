# Review package: 080b265f86c921ba4d264011532ff5459880dc50..e18cd3d9f444a8420907c59d573352797d724b93  (context: -U5)

## Commits
e18cd3d feat(hooks): register the Stop event for spec_loop_guard
470d60b feat(guard): emit the Stop block as top-level decision/reason
6c63bb9 test(guard): per-run fail-open, .paused and stop_hook_active coverage for the Stop gate
a3a9570 feat(guard): Stop loop-boundary gate core (check_stop + event dispatch)

## Files changed
 plugins/spec-loop/hooks/hooks.json                |  11 +
 plugins/spec-loop/scripts/spec_loop_guard.py      | 171 +++++++++++--
 plugins/spec-loop/scripts/test_spec_loop_guard.py | 278 +++++++++++++++++++++-
 3 files changed, 444 insertions(+), 16 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/hooks/hooks.json": [
[
24,
34
]
],
"plugins/spec-loop/scripts/spec_loop_guard.py": [
[
2,
2
],
[
4,
5
],
[
23,
33
],
[
50,
55
],
[
153,
220
],
[
297,
341
],
[
349,
355
],
[
371,
385
],
[
387,
387
],
[
389,
389
]
],
"plugins/spec-loop/scripts/test_spec_loop_guard.py": [
[
12,
12
],
[
17,
17
],
[
34,
35
],
[
44,
49
],
[
51,
53
],
[
64,
79
],
[
91,
337
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/hooks/hooks.json b/plugins/spec-loop/hooks/hooks.json
index de5acd4..aa58d09 100644
--- a/plugins/spec-loop/hooks/hooks.json
+++ b/plugins/spec-loop/hooks/hooks.json
@@ -19,8 +19,19 @@
             "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/spec_loop_guard.py\"",
             "timeout": 5
           }
         ]
       }
+    ],
+    "Stop": [
+      {
+        "hooks": [
+          {
+            "type": "command",
+            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/spec_loop_guard.py\"",
+            "timeout": 5
+          }
+        ]
+      }
     ]
   }
 }
diff --git a/plugins/spec-loop/scripts/spec_loop_guard.py b/plugins/spec-loop/scripts/spec_loop_guard.py
index 5e28a8c..470b949 100644
--- a/plugins/spec-loop/scripts/spec_loop_guard.py
+++ b/plugins/spec-loop/scripts/spec_loop_guard.py
@@ -1,9 +1,10 @@
 #!/usr/bin/env python3
-"""PreToolUse guard: deterministic enforcement of spec-loop's git invariants.
+"""PreToolUse + Stop guard: deterministic enforcement of spec-loop's invariants.
 
-Registered by the plugin's hooks/hooks.json for Bash and Write|Edit tool calls.
+Registered by the plugin's hooks/hooks.json for Bash and Write|Edit tool calls and
+for the Stop event.
 While a spec-loop run is active (a `docs/spec-loop/<run-id>/.active` marker
 exists under the project root), this hook mechanically blocks the operations
 the loop's prompts forbid:
 
 - `git push` before the human's publish choice (`.publish-choice` marker) —
@@ -17,10 +18,21 @@ the loop's prompts forbid:
   command that checks out main and commits/merges/pushes) before the publish
   choice.
 - Any write to the quality-gate config — the global file
   (`~/.claude/spec-loop-2/quality-gate.json`) or the per-repo overlay
   (`.spec-loop/quality-gate.json`) — thresholds must never be weakened mid-run.
+- Ending the turn (`Stop`) while an active, unpaused run still has runnable
+  slices and no open escalation — a wave boundary is a dispatch point, not a
+  reporting boundary. Narrowed to the controller session: the payload's
+  `session_id` must appear in the run's `.controller-session` marker, which
+  the controller writes in Phase 1 from its own session. Skipped when
+  `stop_hook_active` is true, and relaxed by a `.paused` marker (which
+  relaxes THIS gate only, never the git rules above). Empirically confirmed
+  on Claude Code 2.1.260: a sync Stop hook honours a top-level
+  `{"decision": "block", "reason": ...}`, and `stop_hook_active` resets on
+  every new user turn, so the gate re-arms per turn and is one push per stop
+  attempt, never a fence.
 
 Design decisions:
 - **Fail-open on internal errors.** This hook is defense-in-depth; the skill
   prompts remain the primary control. A crashed guard must not deny every
   tool call in the session, so any unexpected exception allows the action.
@@ -33,12 +45,16 @@ Design decisions:
   workers. The platform docs don't state this explicitly, so it is worth
   re-probing after major Claude Code upgrades; every controller-owned operation
   (integration merge, runbook commit, publish push) runs in the main session
   regardless.
 
-Standard library only. Reads the hook payload from stdin; a denial is exit 0
-plus a permissionDecision JSON on stdout; an allow is exit 0 with no output.
+Standard library only (the loop-boundary gate imports the sibling `dag` and
+`run_state` modules function-locally, so the tool hot paths pay nothing and
+an absent module fails open). Reads the hook payload from stdin; a PreToolUse
+denial is exit 0 plus a permissionDecision JSON on stdout, a Stop block is
+exit 0 plus a top-level decision/reason JSON, and an allow is exit 0 with no
+output.
 """
 
 from __future__ import annotations
 
 import glob
@@ -132,10 +148,78 @@ def _push_targets_run(command, run):
         if run["base_ref"] and re.search(r"\b%s\b" % re.escape(run["base_ref"]), tail):
             return True
     return False
 
 
+def _controller_marker(run):
+    """Raw text of the run's `.controller-session` marker, or None.
+
+    Absent or blank marker => the gate cannot tell the controller's turn from
+    any other session's on this machine, so it declines to block at all. The
+    controller writes this in Phase 1 from its own session's id
+    (`$CLAUDE_CODE_SESSION_ID`, per commands/spec-loop.md); matching is
+    substring-based in check_stop so a labelled marker still works.
+    """
+    try:
+        with open(os.path.join(run["dir"], ".controller-session"), "r",
+                  encoding="utf-8") as fh:
+            return fh.read().strip() or None
+    except OSError:
+        return None
+
+
+def _runnable_slices(run):
+    """This run's runnable slice ids, or None when readiness is unknowable.
+
+    Wave membership has exactly ONE implementation (`dag.next_wave`); a copy
+    here would fork the split-parent readiness rule. The import is
+    function-local so the Bash/Write hot paths pay nothing for it (the
+    try/import/except ImportError idiom of dashboard_server.py:74-89), and
+    every failure mode — no dag module, an `.active` marker with no dag.json
+    (DagError), a half-written dag — returns None, which ALLOWS. Per run:
+    one broken run must not unlock the gate for another.
+
+    Note: dag has no in-flight status, so a dispatched-but-uncollected slice
+    still reads as runnable. check_stop's reason text accounts for that
+    rather than this function inventing a status dag does not have.
+    """
+    try:
+        import dag as dag_module
+    except ImportError:  # packaging drift, not a logic path
+        return None
+    try:
+        report = dag_module.next_wave(dag_module.load_dag(run["dir"]))
+    except (dag_module.DagError, OSError, ValueError, TypeError, AttributeError):
+        return None
+    slice_ids = report.get("slice_ids")
+    # Runnability is non-empty slice_ids and NEVER a missing 'done' key: a
+    # deadlock report carries no 'done' at all.
+    return slice_ids if isinstance(slice_ids, list) else None
+
+
+def _has_open_escalation(run):
+    """Is a question already open on this run? True on any doubt.
+
+    An open escalation means the human owes an answer, so ending the turn is
+    the correct move and the gate must not block it. Fail-open direction is
+    therefore True.
+
+    The except clause is purely defensive: run_state.open_escalations does
+    NOT raise for a missing or unreadable events.jsonl (_read_text at
+    run_state.py:172-177 swallows OSError and returns ""), so only a genuine
+    internal defect reaches it.
+    """
+    try:
+        import run_state as run_state_module
+    except ImportError:  # packaging drift, not a logic path
+        return True
+    try:
+        return bool(run_state_module.open_escalations(run["dir"]))
+    except (OSError, ValueError, TypeError, AttributeError):
+        return True
+
+
 def check_bash(command, cwd, runs):
     """Return a deny reason for this Bash command, or None to allow."""
     blocking = [r for r in runs if not r["publish_choice"]]
 
     if GIT_ADD_BROAD.search(command):
@@ -208,17 +292,69 @@ def check_write(file_path, runs, project_root):
             % (run["run_id"], _remediation(run))
         )
     return None
 
 
+def check_stop(session_id, runs):
+    """Return a reason to block this turn from ending, or None to allow.
+
+    Unlike check_bash/check_write this gate is narrowed to the controller
+    session: it denies INACTION, so its false positives are not
+    self-limiting the way a typed command's are. `.paused` relaxes THIS gate
+    only — never find_active_runs, where a paused run reading as
+    non-blocking would silently unlock push-before-publish, broad staging
+    and default-branch commits.
+    """
+    for run in runs:
+        if os.path.exists(os.path.join(run["dir"], ".paused")):
+            continue
+        marker = _controller_marker(run)
+        if not marker or not session_id or session_id not in marker:
+            continue
+        runnable = _runnable_slices(run)
+        if not runnable:
+            continue
+        if _has_open_escalation(run):
+            continue
+        return (
+            "spec-loop run %s has %d runnable slice(s) (%s) and no open escalation: a wave "
+            "boundary is a dispatch point, not a reporting boundary. Continue Phase 2 step 1 "
+            "in THIS turn — compute the wave, prepare worktrees, dispatch — instead of "
+            "reporting status. If a wave you already dispatched is still in flight, wait for "
+            "its completion notification rather than re-dispatching: slice status stays "
+            "pending until collection, so these ids can include work already running. If "
+            "you are deliberately ending the turn anyway, say why in your next message so "
+            "the transcript carries the reason. If the human asked you to hold, write "
+            "docs/spec-loop/%s/.paused, which relaxes this gate alone. If you are not the "
+            "controller of this run, this gate is not aimed at you — only the session "
+            "recorded in docs/spec-loop/%s/.controller-session is blocked. %s"
+            % (
+                run["run_id"],
+                len(runnable),
+                ", ".join(runnable),
+                run["run_id"],
+                run["run_id"],
+                _remediation(run),
+            )
+        )
+    return None
+
+
 def evaluate(payload):
     """Return a deny reason for this hook payload, or None to allow."""
     project_root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
     runs = find_active_runs(project_root)
     if not runs:
         return None
 
+    # Branch on the EVENT first: a Stop payload carries no tool_name key at
+    # all, so a tool-keyed branch would pass unit tests and never fire live.
+    if payload.get("hook_event_name") == "Stop":
+        if payload.get("stop_hook_active"):
+            return None  # this fire ends the continuation a block caused
+        return check_stop(payload.get("session_id"), runs)
+
     tool = payload.get("tool_name", "")
     tool_input = payload.get("tool_input") or {}
     if tool == "Bash":
         return check_bash(tool_input.get("command", ""), payload.get("cwd"), runs)
     if tool in ("Write", "Edit", "MultiEdit"):
@@ -230,22 +366,29 @@ def main(argv=None):
     try:
         payload = json.load(sys.stdin)
         reason = evaluate(payload)
     except Exception:  # noqa: BLE001 — deliberate fail-open (see module docstring)
         return 0
-    if reason:
-        print(
-            json.dumps(
-                {
-                    "hookSpecificOutput": {
-                        "hookEventName": "PreToolUse",
-                        "permissionDecision": "deny",
-                        "permissionDecisionReason": reason,
-                    }
+    if not reason:
+        return 0
+    if payload.get("hook_event_name") == "Stop":
+        # A Stop block is a DIFFERENT wire shape: top-level decision/reason,
+        # empirically confirmed on Claude Code 2.1.260. The PreToolUse
+        # hookSpecificOutput shape is ignored here, which reads as allow.
+        print(json.dumps({"decision": "block", "reason": reason}))
+        return 0
+    print(
+        json.dumps(
+            {
+                "hookSpecificOutput": {
+                    "hookEventName": "PreToolUse",
+                    "permissionDecision": "deny",
+                    "permissionDecisionReason": reason,
                 }
-            )
+            }
         )
+    )
     return 0
 
 
 if __name__ == "__main__":  # pragma: no cover
     sys.exit(main())
diff --git a/plugins/spec-loop/scripts/test_spec_loop_guard.py b/plugins/spec-loop/scripts/test_spec_loop_guard.py
index ef8cd1e..3cd3e62 100644
--- a/plugins/spec-loop/scripts/test_spec_loop_guard.py
+++ b/plugins/spec-loop/scripts/test_spec_loop_guard.py
@@ -7,14 +7,16 @@ plus the CLI entry with fixture hook payloads.
 
 import io
 import json
 import os
 import shutil
+import sys
 import tempfile
 import unittest
 from unittest import mock
 
+import run_state
 import spec_loop_guard as guard
 
 
 class GuardTestCase(unittest.TestCase):
     def setUp(self):
@@ -27,31 +29,56 @@ class GuardTestCase(unittest.TestCase):
         branch = mock.patch.object(guard, "current_branch", return_value="csv-export")
         self.branch_mock = branch.start()
         self.addCleanup(branch.stop)
 
     def make_run(self, run_id="20260707-demo", active=True, publish_choice=False,
-                 merge_mode="single-branch", base_ref="csv-export"):
+                 merge_mode="single-branch", base_ref="csv-export",
+                 slices=(), controller_session=None, paused=False):
         run_dir = os.path.join(self.root, "docs", "spec-loop", run_id)
         os.makedirs(run_dir, exist_ok=True)
         if active:
             with open(os.path.join(run_dir, ".active"), "w") as fh:
                 fh.write("2026-07-07T00:00:00 " + run_id)
         if publish_choice:
             with open(os.path.join(run_dir, ".publish-choice"), "w") as fh:
                 fh.write("push-feature-branch")
+        if controller_session:
+            with open(os.path.join(run_dir, ".controller-session"), "w") as fh:
+                fh.write(controller_session + "\n")
+        if paused:
+            with open(os.path.join(run_dir, ".paused"), "w") as fh:
+                fh.write("human asked to hold\n")
         with open(os.path.join(run_dir, "dag.json"), "w") as fh:
-            json.dump({"base_ref": base_ref, "merge_mode": merge_mode, "slices": []}, fh)
+            json.dump(
+                {"base_ref": base_ref, "merge_mode": merge_mode, "slices": list(slices)}, fh
+            )
         return run_dir
 
     @staticmethod
     def bash(command, cwd="/tmp/wt"):
         return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
 
     @staticmethod
     def write(file_path):
         return {"tool_name": "Write", "tool_input": {"file_path": file_path}, "cwd": "/tmp"}
 
+    @staticmethod
+    def stop(session_id="sess-ctl", stop_hook_active=False, cwd="/tmp/wt"):
+        """A realistic Stop payload: the probed key set, and NO tool_name."""
+        return {
+            "hook_event_name": "Stop",
+            "session_id": session_id,
+            "stop_hook_active": stop_hook_active,
+            "cwd": cwd,
+            "transcript_path": "/tmp/transcript.jsonl",
+            "last_assistant_message": "Wave 1 merged. Here is a status report.",
+            "permission_mode": "acceptEdits",
+            "prompt_id": "p-1",
+            "background_tasks": [],
+            "session_crons": [],
+        }
+
 
 class NoActiveRunTests(GuardTestCase):
     def test_everything_allowed_without_marker(self):
         self.make_run(active=False)
         self.assertIsNone(guard.evaluate(self.bash("git push")))
@@ -59,10 +86,257 @@ class NoActiveRunTests(GuardTestCase):
         self.assertIsNone(
             guard.evaluate(self.write(os.path.expanduser(guard.QUALITY_GATE_CONFIG)))
         )
 
 
+PENDING = [{"id": "s4", "status": "pending", "deps": []}]
+DEADLOCKED = [
+    {"id": "s4", "status": "pending", "deps": ["s9"]},
+    {"id": "s9", "status": "pending", "deps": ["s4"]},
+]
+ALL_DONE = [{"id": "s1", "status": "complete", "deps": []}]
+
+
+def _remediation_sentence(run_id):
+    """The exact _remediation() text every denial and block ends with."""
+    return guard._remediation({"run_id": run_id})
+
+
+class StopGateTests(GuardTestCase):
+    def test_runnable_slice_blocks_the_controller_turn(self):
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        reason = guard.evaluate(self.stop(session_id="sess-ctl"))
+        self.assertIsNotNone(reason)
+        self.assertIn("s4", reason)
+
+    def test_stop_payload_has_no_tool_name_and_still_dispatches(self):
+        # Regression guard for the silent no-op: an implementation that keys
+        # off tool_name never fires live, because Stop carries no such key.
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        payload = self.stop(session_id="sess-ctl")
+        self.assertNotIn("tool_name", payload)
+        self.assertIsNotNone(guard.evaluate(payload))
+
+    def test_deadlock_allows(self):
+        # next_wave reports {'slice_ids': [], 'deadlock': True} with NO 'done'
+        # key: the deadlock escalation question must be askable.
+        self.make_run(slices=DEADLOCKED, controller_session="sess-ctl")
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_done_allows_the_publish_prompt(self):
+        self.make_run(slices=ALL_DONE, controller_session="sess-ctl")
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_other_session_not_blocked(self):
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-other")))
+
+    def test_labelled_marker_still_matches(self):
+        # Matching is substring-tolerant: a marker written with a label or
+        # extra lines must still narrow to the same session. It can never
+        # match a session whose id is absent from the file.
+        self.make_run(slices=PENDING,
+                      controller_session="session_id: sess-ctl (controller)")
+        self.assertIsNotNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_missing_controller_session_marker_allows(self):
+        self.make_run(slices=PENDING)
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_empty_controller_session_marker_allows(self):
+        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
+        with open(os.path.join(run_dir, ".controller-session"), "w") as fh:
+            fh.write("   \n")
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_payload_without_session_id_allows(self):
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        payload = self.stop()
+        del payload["session_id"]
+        self.assertIsNone(guard.evaluate(payload))
+
+    def test_open_escalation_allows(self):
+        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
+        with open(os.path.join(run_dir, "events.jsonl"), "w") as fh:
+            fh.write(json.dumps({
+                "ts": "2026-09-04T00:00:00Z", "scope": "run",
+                "type": "escalation-opened",
+                "payload": {"id": "esc-1", "trigger": "ambiguity", "status": "OPEN"},
+            }) + "\n")
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_answered_escalation_still_blocks(self):
+        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
+        with open(os.path.join(run_dir, "events.jsonl"), "w") as fh:
+            for event in (
+                {"ts": "2026-09-04T00:00:00Z", "scope": "run", "type": "escalation-opened",
+                 "payload": {"id": "esc-1", "trigger": "ambiguity", "status": "OPEN"}},
+                {"ts": "2026-09-04T00:01:00Z", "scope": "run", "type": "escalation-answered",
+                 "payload": {"id": "esc-1", "answer": "option a"}},
+            ):
+                fh.write(json.dumps(event) + "\n")
+        self.assertIsNotNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_no_active_run_allows(self):
+        self.make_run(active=False, slices=PENDING, controller_session="sess-ctl")
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+
+class StopGateFailOpenTests(GuardTestCase):
+    def test_stop_hook_active_allows(self):
+        # Empirically (2026-09-04, CC 2.1.260) stop_hook_active is true only
+        # on the fire that ends the continuation a block caused, and resets
+        # on every new user turn: honouring it makes the gate one push per
+        # stop attempt, re-armed per turn, never a fence.
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        self.assertIsNone(
+            guard.evaluate(self.stop(session_id="sess-ctl", stop_hook_active=True))
+        )
+
+    def test_paused_marker_allows_the_stop_gate(self):
+        self.make_run(slices=PENDING, controller_session="sess-ctl", paused=True)
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_paused_marker_does_not_unlock_push_or_main_commits(self):
+        # .paused relaxes the loop-boundary gate ALONE. If it leaked into
+        # find_active_runs it would silently unlock push-before-publish,
+        # broad staging and default-branch commits.
+        self.make_run(slices=PENDING, controller_session="sess-ctl", paused=True)
+        self.assertIsNotNone(guard.evaluate(self.bash("git push")))
+        self.assertIsNotNone(guard.evaluate(self.bash("git add -A")))
+        self.branch_mock.return_value = "main"
+        self.assertIsNotNone(guard.evaluate(self.bash("git commit -m x")))
+
+    def test_active_marker_without_dag_json_allows(self):
+        # Reachable state: find_active_runs tolerates it, dag.load_dag
+        # raises DagError on it, and the gate must fail OPEN there.
+        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
+        os.unlink(os.path.join(run_dir, "dag.json"))
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_half_written_dag_json_allows(self):
+        run_dir = self.make_run(slices=PENDING, controller_session="sess-ctl")
+        with open(os.path.join(run_dir, "dag.json"), "w") as fh:
+            fh.write('{"slices": [')
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_broken_run_does_not_fail_open_for_a_healthy_run(self):
+        # Two active runs: run-a's dag.json is missing, run-b is runnable
+        # and controlled by this session. The gate must still block. If this
+        # fails, the implementation put ONE try around the whole loop.
+        broken = self.make_run("20260901-run-a", controller_session="sess-ctl")
+        os.unlink(os.path.join(broken, "dag.json"))
+        self.make_run("20260902-run-b", slices=PENDING, controller_session="sess-ctl")
+        reason = guard.evaluate(self.stop(session_id="sess-ctl"))
+        self.assertIsNotNone(reason)
+        self.assertIn("20260902-run-b", reason)
+
+    def test_stale_other_run_is_skipped_not_blamed(self):
+        # A stale .active owned by a different session must not block this one.
+        self.make_run("20260901-stale", slices=PENDING, controller_session="sess-old")
+        self.make_run("20260902-mine", slices=ALL_DONE, controller_session="sess-ctl")
+        self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_import_error_on_dag_allows(self):
+        # A None entry in sys.modules makes `import dag` raise ImportError
+        # ("import of dag halted; None in sys.modules") — the standard idiom,
+        # and unlike patching builtins.__import__ it intercepts nothing else.
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        with mock.patch.dict(sys.modules, {"dag": None}):
+            self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_import_error_on_run_state_allows(self):
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        with mock.patch.dict(sys.modules, {"run_state": None}):
+            self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_open_escalations_raising_allows(self):
+        # Exercises the REAL defensive branch in _has_open_escalation by
+        # patching the dependency (run_state.open_escalations), not the
+        # function under test. open_escalations does not raise for a missing
+        # or unreadable events.jsonl, so this is the only way to reach it.
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        with mock.patch.object(run_state, "open_escalations", side_effect=OSError):
+            self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
+
+    def test_pretooluse_bash_and_write_unaffected_by_the_stop_branch(self):
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        self.assertIsNotNone(guard.evaluate(self.bash("git push")))
+        self.assertIsNotNone(
+            guard.evaluate(self.write(os.path.expanduser(guard.QUALITY_GATE_CONFIG)))
+        )
+        self.assertIsNone(guard.evaluate(self.bash("ls -la")))
+        self.assertIsNone(guard.evaluate(self.write("/tmp/notes.md")))
+
+
+class StopEmitTests(GuardTestCase):
+    def _run_main(self, payload):
+        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
+            with mock.patch("sys.stdout", io.StringIO()) as out:
+                self.assertEqual(guard.main(), 0)
+        return out.getvalue()
+
+    def test_stop_block_uses_the_top_level_decision_shape(self):
+        # Reusing the PreToolUse hookSpecificOutput shape produces a
+        # malformed block that the harness ignores, which reads as allow.
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        emitted = json.loads(self._run_main(self.stop(session_id="sess-ctl")))
+        self.assertEqual(emitted["decision"], "block")
+        self.assertIn("s4", emitted["reason"])
+        self.assertNotIn("hookSpecificOutput", emitted)
+
+    def test_stop_allow_is_silent(self):
+        self.make_run(slices=ALL_DONE, controller_session="sess-ctl")
+        self.assertEqual(self._run_main(self.stop(session_id="sess-ctl")), "")
+
+    def test_pretooluse_deny_still_uses_hook_specific_output(self):
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        emitted = json.loads(self._run_main(self.bash("git push")))
+        self.assertNotIn("decision", emitted)
+        self.assertEqual(
+            emitted["hookSpecificOutput"]["hookEventName"], "PreToolUse"
+        )
+        self.assertEqual(emitted["hookSpecificOutput"]["permissionDecision"], "deny")
+
+
+class StopReasonTextTests(GuardTestCase):
+    def _reason(self):
+        self.make_run(slices=PENDING, controller_session="sess-ctl")
+        reason = guard.evaluate(self.stop(session_id="sess-ctl"))
+        self.assertIsNotNone(reason)
+        return reason
+
+    def test_reason_names_the_runnable_slices_and_the_compliant_alternative(self):
+        reason = self._reason()
+        self.assertIn("s4", reason)
+        self.assertIn("Phase 2 step 1", reason)
+
+    def test_reason_warns_against_re_dispatching_an_in_flight_wave(self):
+        # dag has no in-flight status (SLICE_STATUSES is pending/complete/
+        # split) and record_wave leaves slices pending, so a dispatched-but-
+        # uncollected wave still reads as runnable. The push must not be
+        # readable as an order to double-dispatch.
+        reason = self._reason()
+        self.assertIn("still in flight", reason)
+        self.assertIn("rather than re-dispatching", reason)
+
+    def test_reason_names_the_literal_paused_path(self):
+        self.assertIn("docs/spec-loop/20260707-demo/.paused", self._reason())
+
+    def test_reason_carries_the_not_the_controller_clause(self):
+        self.assertIn("not the controller", self._reason())
+
+    def test_reason_demands_a_visible_trace(self):
+        self.assertIn("say why in your next message", self._reason())
+
+    def test_reason_ends_with_the_standard_remediation_sentence(self):
+        reason = self._reason()
+        self.assertTrue(
+            reason.endswith(_remediation_sentence("20260707-demo")), reason
+        )
+
+
 class PushRuleTests(GuardTestCase):
     def test_bare_push_denied(self):
         self.make_run()
         reason = guard.evaluate(self.bash("git push"))
         self.assertIn("publish prompt", reason)
