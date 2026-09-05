# Review package: 26779c8..d2b1fbb  (context: -U5)

## Commits
d2b1fbb fix(guard): behavior-preserving refactors for quality-gate nesting/class-lines findings
e18cd3d feat(hooks): register the Stop event for spec_loop_guard
470d60b feat(guard): emit the Stop block as top-level decision/reason
6c63bb9 test(guard): per-run fail-open, .paused and stop_hook_active coverage for the Stop gate
a3a9570 feat(guard): Stop loop-boundary gate core (check_stop + event dispatch)
080b265 spec-loop(20260904-loop-gate): merge slice s1 — Phase-2 step 9 Close, wave-boundary invariant, escalation-opened ordering, controller-session and paused lifecycle
159dca7 fix(spec-loop): reformat continuation lines in test_doctrine_loop_boundary.py
d0333b8 docs(changelog): loop-boundary prose and its doctrine pin
049d21b docs(controller): session marker at Phase 1 and Resume, .paused lifecycle
3fea0d7 docs(controller): record escalation-opened before asking the human
f3fcf04 docs(controller): Phase 2 step 9 closes the wave loop in the same turn
f4ba3d4 docs(escalation-gate): a runnable wave boundary is not a stopping point
c83b8fb spec-loop(20260904-loop-gate): merge slice s3 — marker hygiene: untrack run-state markers, gitignore all five
8dc2887 fix(tests): reduce nesting depth in marker-hygiene unanchored test
d0e0102 docs(run-state): state marker hygiene the repo now enforces
4b0e9a7 fix(hygiene): untrack run-state markers and ignore the marker names
4b91d69 docs(spec-loop): commit run-completion markers for 20260827 and 20260828

## Files changed
 .gitignore                                         |  12 +
 CHANGELOG.md                                       |  16 ++
 docs/spec-loop/20260825-scope-ceiling/.done        |   0
 .../20260825-scope-ceiling/.publish-choice         |   1 -
 docs/spec-loop/20260826-crash-classification/.done |   0
 .../20260826-crash-classification/.publish-choice  |   1 -
 plugins/spec-loop/commands/spec-loop.md            |  55 ++++-
 plugins/spec-loop/hooks/hooks.json                 |  11 +
 plugins/spec-loop/references/run-state-v2.md       |  24 +-
 plugins/spec-loop/scripts/spec_loop_guard.py       | 182 ++++++++++++--
 .../scripts/test_doctrine_loop_boundary.py         | 238 ++++++++++++++++++
 .../scripts/test_doctrine_marker_hygiene.py        | 159 ++++++++++++
 plugins/spec-loop/scripts/test_spec_loop_guard.py  |  36 ++-
 .../spec-loop/scripts/test_spec_loop_guard_stop.py | 270 +++++++++++++++++++++
 plugins/spec-loop/skills/escalation-gate/SKILL.md  |   9 +-
 15 files changed, 980 insertions(+), 34 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
".gitignore": [
[
7,
18
]
],
"CHANGELOG.md": [
[
10,
25
]
],
"plugins/spec-loop/commands/spec-loop.md": [
[
21,
23
],
[
74,
77
],
[
192,
209
],
[
228,
235
],
[
246,
258
]
],
"plugins/spec-loop/hooks/hooks.json": [
[
24,
34
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
272,
273
],
[
278,
293
],
[
296,
298
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
346
],
[
354,
360
],
[
370,
381
],
[
388,
396
]
],
"plugins/spec-loop/scripts/test_doctrine_loop_boundary.py": [
[
1,
238
]
],
"plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py": [
[
1,
159
]
],
"plugins/spec-loop/scripts/test_spec_loop_guard.py": [
[
1,
6
],
[
37,
38
],
[
47,
52
],
[
54,
56
],
[
67,
82
]
],
"plugins/spec-loop/scripts/test_spec_loop_guard_stop.py": [
[
1,
270
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
128,
128
],
[
143,
149
]
]
}
```

## Diff
diff --git a/.gitignore b/.gitignore
index 9320d7f..900817b 100644
--- a/.gitignore
+++ b/.gitignore
@@ -2,5 +2,17 @@
 .worktrees/
 
 # Python cache (release/validation scripts)
 __pycache__/
 *.pyc
+
+# spec-loop run-state markers (never commit)
+# The guard hooks fire on these files' PRESENCE. A committed marker arrives on
+# every clone and every fresh worktree, so a committed .active would deny
+# pushes and main-branch commits in sessions that have no run at all. They are
+# per-checkout, per-session state, like .worktrees/. Bare names on purpose:
+# they must be ignored at any depth, under any run directory.
+.active
+.controller-session
+.done
+.paused
+.publish-choice
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 2e88e18..ef2a962 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -5,10 +5,26 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 
+### Added
+- **The controller's Phase-2 loop now closes itself in prose: a wave boundary with slices
+  still runnable is a dispatch point, not a place to stop and report.** `commands/spec-loop.md`
+  gains a Phase 2 step 9 **Close** that re-runs `dag.py next-wave` in the same turn and routes
+  the three outcomes — runnable back to step 1, `done` to Phase 5, `deadlock` to an escalation
+  — judging runnability on a non-empty `slice_ids` rather than on a missing `done` key, which a
+  deadlock report does not carry. The Invariants line states the same rule, an
+  `escalation-opened` event is now mandatory before any controller-originated
+  `AskUserQuestion`, Phase 1 and Resume write `.controller-session` beside `.active`, and the
+  `.paused` lifecycle (human asks, controller writes, controller clears, `--resume` does not)
+  is written down with its stale-marker remediation. `skills/escalation-gate/SKILL.md` adds a
+  fourth "Not triggers" entry for the RUNNABLE boundary only — a reported deadlock stays a
+  genuine escalation — and `scripts/test_doctrine_loop_boundary.py` pins every one of those
+  sentences, counting the list's bullets on disk rather than trusting the number in the prose.
+  This is prose and a pin; the enforcing gate is separate.
+
 ## [2.3.0] - 2026-08-29
 ### Added
 - **The wave now halts a slice at PLAN time when its plan declares a rewrite of existing code
   larger than the run's configured ceiling — the run's one new LEVER.**
   `slice-wave.workflow.js` gains an optional `refactor_radius` block on `PLAN_RESULT` that the
diff --git a/docs/spec-loop/20260825-scope-ceiling/.done b/docs/spec-loop/20260825-scope-ceiling/.done
deleted file mode 100644
index e69de29..0000000
diff --git a/docs/spec-loop/20260825-scope-ceiling/.publish-choice b/docs/spec-loop/20260825-scope-ceiling/.publish-choice
deleted file mode 100644
index 8976109..0000000
--- a/docs/spec-loop/20260825-scope-ceiling/.publish-choice
+++ /dev/null
@@ -1 +0,0 @@
-push-feature-branch-and-open-pr
diff --git a/docs/spec-loop/20260826-crash-classification/.done b/docs/spec-loop/20260826-crash-classification/.done
deleted file mode 100644
index e69de29..0000000
diff --git a/docs/spec-loop/20260826-crash-classification/.publish-choice b/docs/spec-loop/20260826-crash-classification/.publish-choice
deleted file mode 100644
index 8976109..0000000
--- a/docs/spec-loop/20260826-crash-classification/.publish-choice
+++ /dev/null
@@ -1 +0,0 @@
-push-feature-branch-and-open-pr
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index 0ab88ce..13375aa 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -16,11 +16,13 @@ Single-home contracts you follow (read on demand, never restate): run-state and
 
 Invariants (non-negotiable): single-branch integration — every slice merges into ONE local
 integration branch, never `main`/`master`; the loop never pushes before the human's publish
 choice (`--per-slice-pr` is the sole exception); merges are yours alone, serial, `--no-ff`;
 timestamps are yours alone (`date -u +%Y-%m-%dT%H:%M:%SZ`) — workflows have no clock; every
-artifact you hand an agent is a file path, never pasted content.
+artifact you hand an agent is a file path, never pasted content; a wave boundary is a
+dispatch point, not a reporting boundary — while any slice is runnable, Phase 2 step 9
+re-dispatches in the SAME turn.
 
 ## Phase 0 — Intake
 
 1. `--resume <run-id>` short-circuits to **Resume** below (wins over every other flag).
 2. Parse flags. Defaults: `--max-parallel 5`, `--risk-floor 1`. `--from-plan` reads the given
@@ -67,10 +69,14 @@ artifact you hand an agent is a file path, never pasted content.
 4. Create `docs/spec-loop/<run-id>/` with `.active`, `request.md`, `conventions.md`,
    `dag.json` (schema per run-state-v2.md, `mode: "workflow"`, plus `shared_constraints` and
    the optional run-level `scope_ceiling` from Phase 0), and empty `events.jsonl`;
    append a `run-created` event via `run_state.py append-event`. Ensure `.worktrees/` is
    gitignored. Validate: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dag.py" validate --run-dir <dir>`.
+   Write `.controller-session` beside `.active`, containing your session id: the
+   loop-boundary gate reads it and tells your turns from any other session's on this machine.
+   Neither marker is ever committed — `.gitignore` covers both, bare and unanchored, and
+   `test_doctrine_marker_hygiene.py` fails if either re-enters the index.
 5. Knowledge graph (if enabled): one `knowledge_graph.py batch` seeding the system hub + run
    MOC (`ensure_base: true`).
 
 ## Phase 2 — Wave loop
 
@@ -181,10 +187,28 @@ deadlock is itself an escalation):
    result arrives for a slice you did not include, discard it without persisting. (A journal
    lost to a session restart just means the remaining slices re-run live — sidecars bound
    the loss to one wave.)
 8. Knowledge graph (if enabled): one `batch` call upserting the wave's `decision` nodes and
    touched `component` hubs, extracted from the wave's events.
+9. **Close**: re-run `dag.py next-wave` and act on it in THIS turn —
+   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dag.py" next-wave --run-dir <dir>`. Non-empty
+   `slice_ids` → return to step 1 immediately, in the same turn, with no status report and no
+   question: a wave boundary is a dispatch point, not a reporting boundary, and what the wave
+   just did is reported at the runbook. `done: true` → Phase 5. `deadlock: true` → escalate
+   with the `blocked` list; that is a real escalation, never a stall to sit on. Judge
+   runnability on `slice_ids` being non-empty and never on the absence of a `done` key — a
+   deadlock report carries no `done` key at all, so reading a missing `done` as "keep going"
+   would swallow both the deadlock question and the Phase 5 publish prompt. If you do end the
+   turn here anyway, say why in your next message so the transcript carries the reason.
+   `.paused` is the one deliberate escape from the loop-boundary gate: the HUMAN asks for it
+   and YOU write `docs/spec-loop/<run-id>/.paused`. It relaxes the loop-boundary gate alone —
+   every other `.active` restriction (pushes before the publish choice, broad staging,
+   default-branch commits and merges, gate-config writes) still applies. You delete it yourself
+   the moment the human says resume; `--resume` does NOT clear it, so a resumed run is unpaused
+   only once you remove the file. Never write it to get past a gate of your own accord. Like a
+   stale `.active`, a stale `.paused` is remediated by resuming the run or clearing the marker,
+   in that order — and it is never committed.
 
 ## Phase 5 — Integration gate & finish
 
 Follow `references/phase-5-integration.md`: full suite on the integration branch → ONE
 cross-slice `pr-reviewer` (mode `integration`, session model, high effort) over
@@ -199,26 +223,39 @@ a fragmented run dir is an escalation, not a `.done`. Your final output is the r
 Executive Readout, verbatim.
 
 ## Resume
 
 `--resume <run-id>`: read `dag.json` (recover branch, mode, wave history), recreate
-`.active`, checkout the integration branch (clean-tree guard), `worktrees.py prepare
---resume` for the incomplete wave's slices, drain EVERY answered escalation of the run into
-the `answers` map (every round, already-dispatched ones included, per step 7's
-cumulative-map invariant), and re-enter the wave loop at the first incomplete wave —
-same-session
-with `resumeFromRunId`, fresh invocation otherwise. All slices terminal → straight to
-Phase 5 (regenerating `runbook.md` is safe).
+`.active`, rewrite `.controller-session` with your NEW session id (the previous
+session's id is stale the moment this one starts), checkout the integration branch
+(clean-tree guard), `worktrees.py prepare --resume` for the incomplete wave's slices, drain
+EVERY answered escalation of the run into the `answers` map (every round,
+already-dispatched ones included, per step 7's cumulative-map invariant), and re-enter the
+wave loop at the first incomplete wave — same-session with `resumeFromRunId`, fresh
+invocation otherwise. All slices terminal → straight to Phase 5 (regenerating `runbook.md`
+is safe).
 
 ## Escalation discipline
 
 You are the only layer that can ask the human. Never ask mid-wave, never one-at-a-time;
 apply the `escalation-gate` six-trigger test and precedent check to every candidate
 question, including your own. Announce every question you do ask: immediately before ANY
 `AskUserQuestion` (escalation rounds, the publish prompt), fire a best-effort desktop alert —
 `printf '\a'; command -v osascript >/dev/null 2>&1 && osascript -e 'display notification
 "spec-loop run needs a decision" with title "spec-loop"' || true` — so an unattended run is
 never silently parked (a finished run once waited 7.6 hours at the publish prompt). An alert
-failure is ignored, never a reason to delay the question. Every autonomous decision = one `decision` event with
+failure is ignored, never a reason to delay the question.
+
+Before ANY controller-originated `AskUserQuestion` — a reported deadlock, a decomposition
+ambiguity, a config first-run choice, the publish prompt, any question you raise yourself
+rather than a wave — append the record FIRST, then ask:
+`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run_state.py" append-event --run-dir <dir> --ts <now>
+--scope run --type escalation-opened --payload <EscalationRecord JSON>`. The order is the
+point: `open-escalations` reads events.jsonl, so a question asked before its record exists is
+invisible to a resume and to anything else reading run state, and the `escalation-answered`
+event you write back pairs by an `id` that was never opened. This excludes records a wave
+raised are already appended by `persist-slice` — never re-append those.
+
+Every autonomous decision = one `decision` event with
 rationale and reversibility. When a workflow result surprises you (empty, malformed,
 contradicting its own events), read the workflow journal before re-dispatching — never
 re-run work you merely failed to look at.
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
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 10fcc6d..0019058 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -267,19 +267,37 @@ no pinned machine grammar in v2.
 | `runbook.md` | runbook-writer agent | end-of-run synthesis, committed |
 | `metrics.json` | `run_metrics.py --write` | atomic write |
 
 ## Markers — guard-hook contract (unchanged from v1)
 
-- `.active` — created at Phase 1, recreated on resume, never committed. While
-  present, `spec_loop_guard.py` blocks pushes, broad staging, main-branch
+- `.active` — created at Phase 1, recreated on resume. While present,
+  `spec_loop_guard.py` blocks pushes, broad staging, main-branch
   commits/merges, and quality-gate config writes.
 - `.publish-choice` — written the instant the human answers the publish
   prompt, before the action is performed.
 - `.done` — `.active` renamed at run end.
+- `.paused` — present only while the human has deliberately suspended the
+  loop-boundary gate. It relaxes that one gate and nothing else; every
+  `.active` restriction above still applies.
+- `.controller-session` — identifies the controller's own session so the
+  loop-boundary gate applies to it and not to other sessions. Per-session
+  state, meaningful only inside the machine that wrote it.
+
+None of these markers is ever committed. They are per-checkout state: the
+hooks fire on a marker's PRESENCE, so a committed `.active` would deny pushes
+and main-branch commits on every clone and in every fresh worktree, including
+sessions with no run at all. `.gitignore` enforces this with one bare,
+unanchored entry per marker name, and `test_doctrine_marker_hygiene.py` fails
+if one re-enters the index. Markers did get committed twice before that pin
+existed; the correction is an index-only removal (`git rm --cached`) that
+leaves the files on disk for any run still reading them — never a history
+rewrite, and never a plain delete.
 
 A hook denial means the run has not earned that operation yet — never delete
-a marker to dodge one.
+a marker to dodge one. A stale marker is remediated by resuming the run or
+clearing the marker, in that order; that applies to a stale `.paused` exactly
+as it does to a stale `.active`.
 
 ## Worktrees & branches
 
 - Worktree: `.worktrees/spec-loop/<run-id>/<slice-id>` (gitignored).
 - Branch: `spec-loop/<run-id>/<slice-id>`, cut from the current tip of
diff --git a/plugins/spec-loop/scripts/spec_loop_guard.py b/plugins/spec-loop/scripts/spec_loop_guard.py
index 5e28a8c..77209f3 100644
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
+    marker_path = os.path.join(run["dir"], ".controller-session")
+    try:
+        with open(marker_path, "r", encoding="utf-8") as fh:
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
@@ -208,44 +292,110 @@ def check_write(file_path, runs, project_root):
             % (run["run_id"], _remediation(run))
         )
     return None
 
 
+def _stop_block_reason(run, runnable):
+    """The block text for one runnable, unescalated, controller-owned run."""
+    return (
+        "spec-loop run %s has %d runnable slice(s) (%s) and no open escalation: a wave "
+        "boundary is a dispatch point, not a reporting boundary. Continue Phase 2 step 1 "
+        "in THIS turn — compute the wave, prepare worktrees, dispatch — instead of "
+        "reporting status. If a wave you already dispatched is still in flight, wait for "
+        "its completion notification rather than re-dispatching: slice status stays "
+        "pending until collection, so these ids can include work already running. If "
+        "you are deliberately ending the turn anyway, say why in your next message so "
+        "the transcript carries the reason. If the human asked you to hold, write "
+        "docs/spec-loop/%s/.paused, which relaxes this gate alone. If you are not the "
+        "controller of this run, this gate is not aimed at you — only the session "
+        "recorded in docs/spec-loop/%s/.controller-session is blocked. %s"
+        % (
+            run["run_id"],
+            len(runnable),
+            ", ".join(runnable),
+            run["run_id"],
+            run["run_id"],
+            _remediation(run),
+        )
+    )
+
+
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
+        return _stop_block_reason(run, runnable)
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
         return check_write(tool_input.get("file_path"), runs, project_root)
     return None
 
 
+def _pretooluse_deny_payload(reason):
+    """The PreToolUse hookSpecificOutput deny shape, as its own literal so
+    main() doesn't carry the dict's nesting on top of its own control flow."""
+    return {
+        "hookSpecificOutput": {
+            "hookEventName": "PreToolUse",
+            "permissionDecision": "deny",
+            "permissionDecisionReason": reason,
+        }
+    }
+
+
 def main(argv=None):
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
-                }
-            )
-        )
+    if not reason:
+        return 0
+    if payload.get("hook_event_name") == "Stop":
+        # A Stop block is a DIFFERENT wire shape: top-level decision/reason,
+        # empirically confirmed on Claude Code 2.1.260. The PreToolUse
+        # hookSpecificOutput shape is ignored here, which reads as allow.
+        print(json.dumps({"decision": "block", "reason": reason}))
+        return 0
+    print(json.dumps(_pretooluse_deny_payload(reason)))
     return 0
 
 
 if __name__ == "__main__":  # pragma: no cover
     sys.exit(main())
diff --git a/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py b/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
new file mode 100644
index 0000000..fa68fda
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
@@ -0,0 +1,238 @@
+#!/usr/bin/env python3
+"""Doctrine checks for the Phase-2 loop-boundary prose.
+
+The loop's failure this slice exists to fix is prose-shaped: a controller
+that reaches a wave boundary with slices still runnable and ends its turn
+to report. Nothing in the shipped prose said the boundary is a dispatch
+point, and the escalation-gate's "Not triggers" list did not name it.
+Those sentences are now load-bearing, so they are pinned here.
+
+Honest limits: these are substring assertions over collapsed prose plus
+one count of bullets on disk. They prove a sentence is present and that
+its superseded form is gone. They prove nothing about whether a
+controller obeys it, and they are NOT a behavioural test of the Stop
+gate - that gate lives in spec_loop_guard.py and is tested there.
+
+A separate module rather than a class in test_doctrine_refactor_scope.py
+or test_doctrine_run_docs.py: those are owned by other slices' doctrine,
+and slice_wave_contract_base.py is at its 300-line class ceiling.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_doctrine_loop_boundary.py'
+"""
+
+import re
+import unittest
+from pathlib import Path
+
+PLUGIN_ROOT = Path(__file__).resolve().parents[1]
+COMMAND_MD = PLUGIN_ROOT / "commands" / "spec-loop.md"
+SKILL_MD = PLUGIN_ROOT / "skills" / "escalation-gate" / "SKILL.md"
+
+NUMBER_WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
+
+NOT_TRIGGERS_HEADING = "### Not triggers (autonomous by design)"
+
+
+def prose(path):
+    """One file's text with every whitespace run collapsed to a space. (PURE)"""
+    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
+
+
+def not_trigger_bullet_count():
+    """Count the `- **` bullets under SKILL.md's "Not triggers" heading.
+
+    Read off the file rather than remembered, so the count word in the
+    section's own opening sentence cannot drift away from the list it
+    counts. The section ends at the next `## ` heading.
+    """
+    lines = SKILL_MD.read_text(encoding="utf-8").splitlines()
+    start = next(
+        i for i, line in enumerate(lines)
+        if line.strip() == NOT_TRIGGERS_HEADING
+    )
+    count = 0
+    for line in lines[start + 1:]:
+        if line.startswith("## "):
+            break
+        if line.startswith("- **"):
+            count += 1
+    return count
+
+
+# ---- the skill: a runnable wave boundary is not a stopping point ----
+
+SKILL_BOUNDARY_BULLET = "**A wave boundary with slices still runnable.**"
+SKILL_DISPATCH_POINT = "a dispatch point, not a decision"
+SKILL_RUNNABLE_ONLY = "This entry covers the RUNNABLE case ONLY"
+SKILL_DEADLOCK_KEPT = "is the opposite: it is a genuine escalation"
+SKILL_PINNED_TAIL = "exactly the six triggers above"
+SKILL_OTHER_LIST = "Three things that are deliberately NOT judgment triggers"
+SKILL_STALE_COUNT = "Three things that look like stopping points"
+
+
+class TestTheSkillNamesTheRunnableWaveBoundary(unittest.TestCase):
+    """The list of things that look like stopping points but are handled by
+    the loop grows a fourth entry. It must be readable ONLY as the runnable
+    case: a reported deadlock is a real escalation, and a reader who
+    generalised this entry would swallow it."""
+
+    def setUp(self):
+        self.text = prose(SKILL_MD)
+
+    def test_the_fourth_not_trigger_is_the_runnable_wave_boundary(self):
+        self.assertIn(SKILL_BOUNDARY_BULLET, self.text)
+        self.assertIn(SKILL_DISPATCH_POINT, self.text)
+
+    def test_the_entry_is_scoped_to_runnable_and_spares_deadlock(self):
+        self.assertIn(SKILL_RUNNABLE_ONLY, self.text)
+        self.assertIn(SKILL_DEADLOCK_KEPT, self.text)
+
+    def test_the_count_word_matches_the_bullets_on_disk(self):
+        count = not_trigger_bullet_count()
+        self.assertEqual(count, 4)
+        word = NUMBER_WORDS[count]
+        self.assertIn(
+            "%s things that look like stopping points" % word, self.text)
+
+    def test_the_superseded_three_count_is_gone(self):
+        self.assertNotIn(SKILL_STALE_COUNT, self.text)
+
+    def test_the_pinned_tail_clause_and_the_other_list_are_untouched(self):
+        self.assertIn(SKILL_PINNED_TAIL, self.text)
+        self.assertIn(SKILL_OTHER_LIST, self.text)
+
+
+# ---- the command: Phase 2 closes its own loop ----
+
+CLOSE_STEP = "9. **Close**:"
+CLOSE_RECOMPUTE = "re-run `dag.py next-wave` and act on it in THIS turn"
+CLOSE_SAME_TURN = "return to step 1 immediately, in the same turn, with no status report"
+CLOSE_DONE = "`done: true` → Phase 5"
+CLOSE_DEADLOCK = "`deadlock: true` → escalate with the `blocked` list"
+CLOSE_ON_SLICE_IDS = (
+    "Judge runnability on `slice_ids` being non-empty and never on the absence "
+    "of a `done` key")
+CLOSE_NO_DONE_KEY = "a deadlock report carries no `done` key at all"
+CLOSE_VISIBLE_TRACE = "say why in your next message so the transcript carries the reason"
+INVARIANT_BOUNDARY = "a wave boundary is a dispatch point, not a reporting boundary"
+
+
+class TestPhase2ClosesTheWaveLoopInTheSameTurn(unittest.TestCase):
+    """The controller command is the only place the loop's turn discipline is
+    written. Phase 2 ended at step 8 with no instruction to recompute, which
+    is how a turn ends with slices still runnable."""
+
+    def setUp(self):
+        self.text = prose(COMMAND_MD)
+
+    def test_phase_2_has_a_closing_step(self):
+        self.assertIn(CLOSE_STEP, self.text)
+        self.assertIn(CLOSE_RECOMPUTE, self.text)
+
+    def test_the_closing_step_states_all_three_outcomes(self):
+        for pin in (CLOSE_SAME_TURN, CLOSE_DONE, CLOSE_DEADLOCK):
+            self.assertIn(pin, self.text)
+
+    def test_runnability_is_judged_on_slice_ids_not_a_missing_done_key(self):
+        self.assertIn(CLOSE_ON_SLICE_IDS, self.text)
+        self.assertIn(CLOSE_NO_DONE_KEY, self.text)
+
+    def test_a_deliberate_stop_must_leave_a_visible_reason(self):
+        self.assertIn(CLOSE_VISIBLE_TRACE, self.text)
+
+    def test_the_invariants_line_names_the_boundary_as_a_dispatch_point(self):
+        self.assertIn(INVARIANT_BOUNDARY, self.text)
+        head = self.text.index("Invariants (non-negotiable)")
+        self.assertLess(head, self.text.index(INVARIANT_BOUNDARY))
+        self.assertLess(
+            self.text.index(INVARIANT_BOUNDARY),
+            self.text.index("## Phase 0 — Intake"),
+        )
+
+
+# ---- the command: record the escalation BEFORE asking ----
+
+OPEN_FIRST = "append the record FIRST, then ask"
+OPEN_CLI = "--type escalation-opened"
+OPEN_SCOPE = "any question you raise yourself rather than a wave"
+OPEN_WHY = "a question asked before its record exists is invisible to a resume"
+OPEN_NO_DOUBLE = "records a wave raised are already appended by `persist-slice`"
+
+
+class TestControllerQuestionsAreRecordedBeforeTheyAreAsked(unittest.TestCase):
+    """`open-escalations` reads events.jsonl, so an unrecorded question is a
+    question no resume and no run-state reader can see, and an answer written
+    back pairs by an id that was never opened."""
+
+    def setUp(self):
+        self.text = prose(COMMAND_MD)
+
+    def test_the_record_is_appended_before_the_question_is_asked(self):
+        self.assertIn(OPEN_FIRST, self.text)
+        self.assertIn(OPEN_CLI, self.text)
+
+    def test_the_rule_names_which_questions_it_covers(self):
+        self.assertIn(OPEN_SCOPE, self.text)
+
+    def test_the_rule_says_why_the_order_matters(self):
+        self.assertIn(OPEN_WHY, self.text)
+
+    def test_wave_raised_records_are_not_re_appended(self):
+        self.assertIn(OPEN_NO_DOUBLE, self.text)
+
+    def test_the_rule_lives_in_the_escalation_discipline_section(self):
+        head = self.text.index("## Escalation discipline")
+        self.assertLess(head, self.text.index(OPEN_FIRST))
+
+
+# ---- the command: the two session/pause markers ----
+
+SESSION_WRITE = "`.controller-session` beside `.active`, containing your session id"
+SESSION_PURPOSE = "tells your turns from any other session's on this machine"
+SESSION_NEVER_COMMITTED = "Neither marker is ever committed"
+SESSION_RESUME = "rewrite `.controller-session` with your NEW session id"
+PAUSED_WHO = "the HUMAN asks for it and YOU write"
+PAUSED_ONE_GATE = "relaxes the loop-boundary gate alone"
+PAUSED_CLEAR = "delete it yourself the moment the human says resume"
+PAUSED_RESUME = "`--resume` does NOT clear it"
+PAUSED_REMEDIATION = (
+    "a stale `.paused` is remediated by resuming the run or clearing the marker, "
+    "in that order")
+PAUSED_NEVER_SELF = "Never write it to get past a gate of your own accord"
+
+
+class TestTheMarkerLifecyclesAreWrittenDown(unittest.TestCase):
+    """`.controller-session` scopes the gate to the controller and `.paused` is
+    its only deliberate escape. A `.paused` nobody clears is a gate lost with
+    no report, so who writes it, who clears it, and what resume does with it
+    all have to be on the page."""
+
+    def setUp(self):
+        self.text = prose(COMMAND_MD)
+
+    def test_phase_1_writes_the_controller_session_marker(self):
+        self.assertIn(SESSION_WRITE, self.text)
+        self.assertIn(SESSION_PURPOSE, self.text)
+
+    def test_the_markers_are_stated_once_to_be_uncommitted(self):
+        self.assertIn(SESSION_NEVER_COMMITTED, self.text)
+
+    def test_resume_rewrites_the_session_marker(self):
+        self.assertIn(SESSION_RESUME, self.text)
+        self.assertLess(
+            self.text.index("## Resume"),
+            self.text.index(SESSION_RESUME),
+        )
+
+    def test_the_paused_lifecycle_names_who_writes_and_who_clears(self):
+        for pin in (PAUSED_WHO, PAUSED_CLEAR, PAUSED_NEVER_SELF):
+            self.assertIn(pin, self.text)
+
+    def test_paused_relaxes_one_gate_and_survives_a_resume(self):
+        self.assertIn(PAUSED_ONE_GATE, self.text)
+        self.assertIn(PAUSED_RESUME, self.text)
+
+    def test_the_stale_paused_remediation_sentence_is_present(self):
+        self.assertIn(PAUSED_REMEDIATION, self.text)
diff --git a/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py b/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py
new file mode 100644
index 0000000..6d0fbc3
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py
@@ -0,0 +1,159 @@
+#!/usr/bin/env python3
+"""Doctrine checks for spec-loop run-state marker hygiene.
+
+The guard hooks key off on-disk markers under docs/spec-loop/<run-id>/:
+.active, .done, .publish-choice, .paused, and .controller-session. A marker
+that is COMMITTED arrives on every clone and every fresh worktree, which
+turns the guard against the repo - a committed .active denies pushes and
+main-branch commits forever, for everyone, in sessions that have no run at
+all.
+
+This happened: .active entered the index twice (commits 5de8f42 and
+a413b93) and two runs' .done / .publish-choice markers rode in on the
+feature merges 7fdd7e2 and e9460f8, while references/run-state-v2.md
+already said .active is "never committed". Prose alone did not hold the
+line, so this module pins it.
+
+Honest limits: the tracking assertion shells out to `git ls-files` and is
+skipped only when there is no .git entry at REPO_ROOT (a source tarball).
+When git IS present it fails loudly rather than skipping, so the pin cannot
+degrade into a silent no-op. The .gitignore assertions check literal
+entries and the absence of a leading slash; they prove the patterns are
+present and unanchored, not that git's matcher behaves as intended - that
+part is covered by the tracking assertion, which is the property that
+actually matters.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_doctrine_marker_hygiene.py'
+"""
+
+import re
+import subprocess
+import unittest
+from pathlib import Path
+
+REPO_ROOT = Path(__file__).resolve().parents[3]
+GITIGNORE = REPO_ROOT / ".gitignore"
+RUN_STATE_MD = (
+    Path(__file__).resolve().parents[1] / "references" / "run-state-v2.md"
+)
+MARKERS = (
+    ".active",
+    ".controller-session",
+    ".done",
+    ".paused",
+    ".publish-choice",
+)
+
+
+def prose(path):
+    """One file's text with every whitespace run collapsed to a space. (PURE)"""
+    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
+
+
+def ignore_lines():
+    """The non-blank, non-comment lines of .gitignore, stripped."""
+    return [
+        line.strip()
+        for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
+        if line.strip() and not line.strip().startswith("#")
+    ]
+
+
+def marker_suffix(line):
+    """The marker `line` ends with, or None. (PURE)"""
+    for marker in MARKERS:
+        if line.endswith(marker):
+            return marker
+    return None
+
+
+def repo_has_git():
+    """True when REPO_ROOT has a .git dir OR a .git file (linked worktree)."""
+    return (REPO_ROOT / ".git").exists()
+
+
+def git(*args):
+    """Stripped stdout of a git command in REPO_ROOT. Raises on failure."""
+    done = subprocess.run(
+        ("git", "-C", str(REPO_ROOT)) + args,
+        capture_output=True,
+        text=True,
+        timeout=30,
+    )
+    if done.returncode != 0:
+        raise RuntimeError(
+            "git %s failed with exit %d: %s"
+            % (" ".join(args), done.returncode, done.stderr.strip())
+        )
+    return done.stdout.strip()
+
+
+class TestMarkersAreNotTracked(unittest.TestCase):
+    """No run-state marker may be in the index, and all five are ignored."""
+
+    def test_no_run_state_marker_is_tracked(self):
+        if not repo_has_git():
+            self.skipTest("no .git at repo root (source tarball)")
+        listing = git("ls-files", "--", "docs/spec-loop")
+        tracked = [
+            path
+            for path in listing.splitlines()
+            if Path(path).name in MARKERS
+        ]
+        self.assertEqual(
+            tracked,
+            [],
+            "these run-state markers are committed and will fire the guard "
+            "on every checkout; remove them from the index only, leaving "
+            "them on disk: %s" % tracked,
+        )
+
+    def test_every_marker_name_is_gitignored(self):
+        lines = ignore_lines()
+        for marker in MARKERS:
+            self.assertIn(
+                marker,
+                lines,
+                "%s is not a literal .gitignore entry, so the next run can "
+                "commit it again" % marker,
+            )
+
+    def test_marker_ignore_patterns_are_unanchored(self):
+        for line in ignore_lines():
+            marker = marker_suffix(line)
+            if marker is None:
+                continue
+            self.assertEqual(
+                line,
+                marker,
+                "%s must be matched at any depth, so its .gitignore "
+                "entry must be the bare name, not %r" % (marker, line),
+            )
+
+
+class TestRunStateDocStatesMarkerHygiene(unittest.TestCase):
+    """The Markers section must name every marker and the ignore rule."""
+
+    def test_every_marker_is_documented(self):
+        text = prose(RUN_STATE_MD)
+        for marker in MARKERS:
+            self.assertIn("`%s`" % marker, text, "%s undocumented" % marker)
+
+    def test_the_class_wide_never_committed_rule_is_stated(self):
+        self.assertIn(
+            "None of these markers is ever committed",
+            prose(RUN_STATE_MD),
+        )
+
+    def test_gitignore_is_named_as_the_enforcement(self):
+        text = prose(RUN_STATE_MD)
+        self.assertIn("`.gitignore`", text)
+        self.assertIn("index-only removal", text)
+
+    def test_the_do_not_delete_a_marker_sentence_survives(self):
+        self.assertIn(
+            "never delete a marker to dodge one",
+            prose(RUN_STATE_MD),
+        )
diff --git a/plugins/spec-loop/scripts/test_spec_loop_guard.py b/plugins/spec-loop/scripts/test_spec_loop_guard.py
index ef8cd1e..b320be7 100644
--- a/plugins/spec-loop/scripts/test_spec_loop_guard.py
+++ b/plugins/spec-loop/scripts/test_spec_loop_guard.py
@@ -1,6 +1,11 @@
-"""Tests for spec_loop_guard.py.
+"""Tests for spec_loop_guard.py's PreToolUse gates (push/staging/main-branch/
+quality-gate-config) plus the shared GuardTestCase fixture.
+
+test_spec_loop_guard_stop.py covers the Stop loop-boundary gate separately
+(split out to stay under the per-file class_lines ceiling) and imports
+GuardTestCase from this module.
 
 Standard library only; no live git required (current_branch is patched).
 Builds throwaway run-state directories with tempfile and drives evaluate()
 plus the CLI entry with fixture hook payloads.
 """
@@ -27,31 +32,56 @@ class GuardTestCase(unittest.TestCase):
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
diff --git a/plugins/spec-loop/scripts/test_spec_loop_guard_stop.py b/plugins/spec-loop/scripts/test_spec_loop_guard_stop.py
new file mode 100644
index 0000000..da91c7c
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_spec_loop_guard_stop.py
@@ -0,0 +1,270 @@
+"""Tests for spec_loop_guard.py's Stop loop-boundary gate.
+
+Split out of test_spec_loop_guard.py (which keeps the PreToolUse coverage)
+purely to stay under the per-file class_lines ceiling; GuardTestCase is the
+shared fixture base for both files. Standard library only; no live git
+required (current_branch is patched).
+"""
+
+import io
+import json
+import os
+import sys
+import unittest
+from unittest import mock
+
+import run_state
+import spec_loop_guard as guard
+from test_spec_loop_guard import GuardTestCase
+
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
+        self.make_run(
+            slices=PENDING,
+            controller_session="session_id: sess-ctl (controller)",
+        )
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
+if __name__ == "__main__":  # pragma: no cover
+    unittest.main()
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index f74c17a..baf3928 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -123,11 +123,11 @@ on the text, never on a pinned format.
 
 The controller repeats this check over every open record at the wave boundary.
 
 ### Not triggers (autonomous by design)
 
-Three things that look like stopping points but are handled by the loop itself, keeping the bar at
+Four things that look like stopping points but are handled by the loop itself, keeping the bar at
 exactly the six triggers above:
 
 - **Slice split.** A slice that turns out to be two-or-more independently shippable changes
   returns `SPLIT`; the controller grafts the children into the DAG (`dag.py ingest-split`) —
   logged, no human contact. Only a proposal that is malformed or already at the depth cap falls
@@ -138,10 +138,17 @@ exactly the six triggers above:
 - **Over-scope and deferred scope.** A plan that exceeds the run's scope ceiling is flagged
   (`over_scope`) and, when the goal genuinely asks for it, still built; work the council
   asks not to be built is a `defer`-hinted concern recorded as one `deferred` event per
   concern. Both are records for the human to read at the runbook, not questions — and
   neither ever suppresses a finding.
+- **A wave boundary with slices still runnable.** When `dag.py next-wave` reports a non-empty
+  `slice_ids`, the boundary is a dispatch point, not a decision: the controller re-dispatches
+  the next wave in the SAME turn, and what the finished wave did is reported at the runbook
+  rather than mid-loop. Ending the turn there is the stall this list exists to prevent, not a
+  question. This entry covers the RUNNABLE case ONLY — a reported `deadlock` (nothing runnable
+  while slices remain) is the opposite: it is a genuine escalation the controller surfaces, and
+  nothing here downgrades it.
 
 ## Batching rule (critical for non-blocking operation)
 
 **Never interrupt mid-wave, never one question at a time.** Workflow stages cannot prompt the
 human, so:
