# Review package: 5d4a8e6..3f10b96  (context: -U5)

## Commits
3f10b96 refactor(guard): rewrap module docstring to bring class_lines under the 300 floor

## Files changed
 plugins/spec-loop/scripts/spec_loop_guard.py | 70 +++++++++++++---------------
 1 file changed, 32 insertions(+), 38 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/spec_loop_guard.py": [
[
4,
6
],
[
8,
21
],
[
24,
32
],
[
34,
37
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/spec_loop_guard.py b/plugins/spec-loop/scripts/spec_loop_guard.py
index 8c1e149..1bead42 100644
--- a/plugins/spec-loop/scripts/spec_loop_guard.py
+++ b/plugins/spec-loop/scripts/spec_loop_guard.py
@@ -1,48 +1,42 @@
 #!/usr/bin/env python3
 """PreToolUse + Stop guard: deterministic enforcement of spec-loop's invariants.
 
-Registered by the plugin's hooks/hooks.json for Bash and Write|Edit tool calls
-and for the Stop event. While a spec-loop run is active (a
-`docs/spec-loop/<run-id>/.active` marker exists under the project root), this
-hook mechanically blocks the operations the loop's prompts forbid:
-
-- `git push` before the human's publish choice (`.publish-choice` marker),
-  except in `per-slice-pr` merge mode where slices legitimately push. Only
-  pushes that plausibly belong to the run are denied: bare pushes, pushes
-  naming the run's integration branch (`base_ref`), or `spec-loop/` branches.
-- `git add -A` / `--all` / `git add .` — the runbook commit must stage only
-  the run directory, by explicit pathspec.
-- `git commit` / `git merge` while sitting on `main`/`master` (or a compound
-  command that checks out main and commits/merges/pushes) before that choice.
-- Any write to the quality-gate config, global
-  (`~/.claude/spec-loop-2/quality-gate.json`) or per-repo overlay
-  (`.spec-loop/quality-gate.json`): thresholds are never weakened mid-run.
-- Ending the turn (`Stop`) while an active, unpaused run still has runnable
-  slices and no open escalation — a wave boundary is a dispatch point, not a
-  reporting boundary. Narrowed to the controller session: the payload's
-  `session_id` must appear in the run's `.controller-session` marker, written
-  in Phase 1. Skipped when `stop_hook_active` is true, and relaxed by a
+Registered by the plugin's hooks/hooks.json for Bash and Write|Edit tool calls and for the Stop
+event. While a spec-loop run is active (a `docs/spec-loop/<run-id>/.active` marker exists under
+the project root), this hook mechanically blocks the operations the loop's prompts forbid:
+
+- `git push` before the human's publish choice (`.publish-choice` marker), except in
+  `per-slice-pr` merge mode where slices legitimately push. Only pushes that plausibly belong to
+  the run are denied: bare pushes, pushes naming the run's integration branch (`base_ref`), or
+  `spec-loop/` branches.
+- `git add -A` / `--all` / `git add .` — the runbook commit must stage only the run directory,
+  by explicit pathspec.
+- `git commit` / `git merge` while sitting on `main`/`master` (or a compound command that checks
+  out main and commits/merges/pushes) before that choice.
+- Any write to the quality-gate config, global (`~/.claude/spec-loop-2/quality-gate.json`) or
+  per-repo overlay (`.spec-loop/quality-gate.json`): thresholds are never weakened mid-run.
+- Ending the turn (`Stop`) while an active, unpaused run still has runnable slices and no open
+  escalation — a wave boundary is a dispatch point, not a reporting boundary. Narrowed to the
+  controller session: the payload's `session_id` must appear in the run's `.controller-session`
+  marker, written in Phase 1. Skipped when `stop_hook_active` is true, and relaxed by a
   `.paused` marker, which relaxes THIS gate only, never the rules above.
 
-Design decisions. **Fail-open on internal errors:** this hook is
-defense-in-depth and the skill prompts remain the primary control, so any
-unexpected exception allows the action rather than denying every tool call in
-the session. Denials **fail closed**, naming the compliant alternative and the
-stale-marker remediation (`/spec-loop --resume <run-id>` or clearing the
-`.active` marker). Subagent coverage is empirical (2026-07-07, instrumented
-hook + headless `claude -p` probe): PreToolUse fires for Bash calls made inside
-Task subagents as well as the main session, so this guard also covers slice
-workers. The platform docs don't state that, so it is worth re-probing after
-major Claude Code upgrades; every controller-owned operation (integration
-merge, runbook commit, publish push) runs in the main session regardless.
-
-Standard library only; the loop-boundary gate imports the sibling `dag` and
-`run_state` modules function-locally, so the tool hot paths pay nothing and an
-absent module fails open. Reads the payload from stdin; a PreToolUse denial is
-exit 0 plus a permissionDecision JSON, a Stop block is exit 0 plus a top-level
-decision/reason JSON, and an allow is exit 0 with no output.
+Design decisions. **Fail-open on internal errors:** this hook is defense-in-depth and the skill
+prompts remain the primary control, so any unexpected exception allows the action rather than
+denying every tool call in the session. Denials **fail closed**, naming the compliant
+alternative and the stale-marker remediation (`/spec-loop --resume <run-id>` or clearing the
+`.active` marker). Subagent coverage is empirical (2026-07-07, instrumented hook + headless
+`claude -p` probe): PreToolUse fires for Bash calls made inside Task subagents as well as the
+main session, so this guard also covers slice workers. The platform docs don't state that, so it
+is worth re-probing after major Claude Code upgrades; every controller-owned operation
+(integration merge, runbook commit, publish push) runs in the main session regardless.
+
+Standard library only; the loop-boundary gate imports the sibling `dag` and `run_state` modules
+function-locally, so the tool hot paths pay nothing and an absent module fails open. Reads the
+payload from stdin; a PreToolUse denial is exit 0 plus a permissionDecision JSON, a Stop block
+is exit 0 plus a top-level decision/reason JSON, and an allow is exit 0 with no output.
 """
 
 from __future__ import annotations
 
 import glob
