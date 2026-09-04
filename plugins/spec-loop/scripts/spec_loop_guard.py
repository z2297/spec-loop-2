#!/usr/bin/env python3
"""PreToolUse + Stop guard: deterministic enforcement of spec-loop's invariants.

Registered by the plugin's hooks/hooks.json for Bash and Write|Edit tool calls and for the Stop
event. While a spec-loop run is active (a `docs/spec-loop/<run-id>/.active` marker exists under
the project root), this hook mechanically blocks the operations the loop's prompts forbid:

- `git push` before the human's publish choice (`.publish-choice` marker), except in
  `per-slice-pr` merge mode where slices legitimately push. Only pushes that plausibly belong to
  the run are denied: bare pushes, pushes naming the run's integration branch (`base_ref`), or
  `spec-loop/` branches.
- `git add -A` / `--all` / `git add .` — the runbook commit must stage only the run directory,
  by explicit pathspec.
- `git commit` / `git merge` while sitting on `main`/`master` (or a compound command that checks
  out main and commits/merges/pushes) before that choice.
- Any write to the quality-gate config, global (`~/.claude/spec-loop-2/quality-gate.json`) or
  per-repo overlay (`.spec-loop/quality-gate.json`): thresholds are never weakened mid-run.
- Ending the turn (`Stop`) while an active, unpaused run still has runnable slices and no open
  escalation — a wave boundary is a dispatch point, not a reporting boundary. Narrowed to the
  controller session: the payload's `session_id` must appear in the run's `.controller-session`
  marker, written in Phase 1. Skipped when `stop_hook_active` is true, and relaxed by a
  `.paused` marker, which relaxes THIS gate only, never the rules above.

Design decisions. **Fail-open on internal errors:** this hook is defense-in-depth and the skill
prompts remain the primary control, so any unexpected exception allows the action rather than
denying every tool call in the session. Denials **fail closed**, naming the compliant
alternative and the stale-marker remediation (`/spec-loop --resume <run-id>` or clearing the
`.active` marker). Subagent coverage is empirical (2026-07-07, instrumented hook + headless
`claude -p` probe): PreToolUse fires for Bash calls made inside Task subagents as well as the
main session, so this guard also covers slice workers. The platform docs don't state that, so it
is worth re-probing after major Claude Code upgrades; every controller-owned operation
(integration merge, runbook commit, publish push) runs in the main session regardless.

Standard library only; the loop-boundary gate imports the sibling `dag` and `run_state` modules
function-locally, so the tool hot paths pay nothing and an absent module fails open. Reads the
payload from stdin; a PreToolUse denial is exit 0 plus a permissionDecision JSON, a Stop block
is exit 0 plus a top-level decision/reason JSON, and an allow is exit 0 with no output.
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

QUALITY_GATE_CONFIG = os.path.join("~", ".claude", "spec-loop-2", "quality-gate.json")
# Per-repo overlay (committed; hosts threshold overrides and tier3_surfaces).
# Protected the same way: it must predate the run, so agents cannot weaken it.
QUALITY_GATE_OVERLAY = os.path.join(".spec-loop", "quality-gate.json")

GIT_PUSH = re.compile(r"\bgit\b(?:\s+-\S+|\s+-C\s+\S+)*\s+push\b")
GIT_ADD_BROAD = re.compile(
    r"\bgit\b(?:\s+-\S+|\s+-C\s+\S+)*\s+add\s+(?:[^;|&]*\s)?(?:-A\b|--all\b|\.(?:\s|$|;))"
)
GIT_COMMIT_OR_MERGE = re.compile(r"\bgit\b(?:\s+-\S+|\s+-C\s+\S+)*\s+(?:commit|merge)\b")
CHECKOUT_MAIN = re.compile(r"\bgit\b[^;|&]*\b(?:checkout|switch)\s+(?:main|master)\b")
COMMIT_MERGE_PUSH_WORD = re.compile(r"\b(?:commit|merge|push)\b")
# A write must TARGET a quality-gate.json path to count. A bare redirect
# elsewhere in the command (`2>&1`, `> /tmp/out.json`) alongside a --config
# flag is a read-only gate invocation and must stay allowed.
QUALITY_GATE_WRITE = re.compile(
    r"(?:>>?\s*\S*quality-gate\.json"  # redirect into the config
    r"|\b(?:tee|mv|cp)\b[^;|&>]*quality-gate\.json"  # tee/mv/cp naming it
    r"|\bsed\s+-i\b[^;|&]*quality-gate\.json)"  # in-place sed on it
)


def find_active_runs(project_root):
    """Return info for every run with an `.active` marker under project_root."""
    runs = []
    for marker in sorted(glob.glob(os.path.join(project_root, "docs", "spec-loop", "*", ".active"))):
        run_dir = os.path.dirname(marker)
        info = {
            "run_id": os.path.basename(run_dir),
            "dir": run_dir,
            "publish_choice": os.path.exists(os.path.join(run_dir, ".publish-choice")),
            "merge_mode": "single-branch",
            "base_ref": None,
        }
        try:
            with open(os.path.join(run_dir, "dag.json"), "r", encoding="utf-8") as fh:
                dag = json.load(fh)
            info["merge_mode"] = dag.get("merge_mode", "single-branch")
            info["base_ref"] = dag.get("base_ref")
        except (OSError, ValueError):
            pass  # missing/unreadable dag.json: keep restrictive defaults
        runs.append(info)
    return runs


def current_branch(cwd):
    """The checked-out branch in cwd, or None if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _remediation(run):
    return (
        "If run %s is stale, resume it (/spec-loop --resume %s) or clear "
        "docs/spec-loop/%s/.active." % (run["run_id"], run["run_id"], run["run_id"])
    )


def _push_targets_run(command, run):
    """Does this push plausibly belong to the run? Bare pushes count."""
    for segment in re.split(r"(?:&&|\|\||[;|])", command):
        if not GIT_PUSH.search(segment):
            continue
        tail = segment[GIT_PUSH.search(segment).end():]
        args = [a for a in tail.split() if not a.startswith("-")]
        if len(args) <= 1:  # bare `git push` or remote-only
            return True
        # Slice branches (spec-loop/<run>/<slice>) and the default integration
        # namespace (spec-loop-run/<run>) both belong to the run even when
        # dag.json is unreadable and base_ref is unknown.
        if "spec-loop/" in tail or "spec-loop-run/" in tail:
            return True
        if run["base_ref"] and re.search(r"\b%s\b" % re.escape(run["base_ref"]), tail):
            return True
    return False


def _controller_marker(run):
    """Raw text of the run's `.controller-session` marker, or None.

    Absent or blank => no recorded controller, so the gate declines to block
    at all; check_stop matches it as a substring (a labelled marker works).
    ValueError is caught alongside OSError — an undecodable marker raises
    UnicodeDecodeError, which is a ValueError, not an OSError — so this run
    fails open on its own, matching _blocking_slices and never escaping to
    main()'s blanket handler, which would unlock the gate for every run.
    """
    marker_path = os.path.join(run["dir"], ".controller-session")
    try:
        with open(marker_path, "r", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except (OSError, ValueError):
        return None


def _blocking_slices(run):
    """Runnable slice ids that make ending the turn wrong, or None to ALLOW.

    `dag.next_wave` is the ONE implementation of wave membership; a copy here
    would fork the split-parent rule. An open escalation means the human owes
    an answer, so the turn must be free to end: that too returns None. The
    imports are function-local (the dashboard_server.py:74-89 idiom) so the
    tool hot paths pay nothing, and every failure mode returns None per run,
    so one broken run cannot unlock the gate for another.
    """
    try:
        import dag as dag_module
        import run_state as run_state_module
    except ImportError:  # packaging drift, not a logic path
        return None
    try:
        report = dag_module.next_wave(dag_module.load_dag(run["dir"]))
        if run_state_module.open_escalations(run["dir"]):
            return None
    except (dag_module.DagError, OSError, ValueError, TypeError, AttributeError):
        return None
    # Runnability is non-empty slice_ids, NEVER a missing 'done' key: a
    # deadlock report carries no 'done' at all.
    slice_ids = report.get("slice_ids")
    return slice_ids if isinstance(slice_ids, list) else None


def check_bash(command, cwd, runs):
    """Return a deny reason for this Bash command, or None to allow."""
    blocking = [r for r in runs if not r["publish_choice"]]

    if GIT_ADD_BROAD.search(command):
        run = runs[0]
        return (
            "spec-loop run %s is active: broad staging (`git add -A`/`--all`/`.`) would sweep "
            "unrelated changes into the commit. Stage only the run directory by explicit "
            "pathspec: git add -- docs/spec-loop/%s/. %s"
            % (run["run_id"], run["run_id"], _remediation(run))
        )

    if QUALITY_GATE_WRITE.search(command):
        run = runs[0]
        return (
            "spec-loop run %s is active: the quality-gate config must not be modified "
            "mid-run (thresholds are never weakened to force a pass). Adjust it after the "
            "run via /spec-loop:quality-gate. %s" % (run["run_id"], _remediation(run))
        )

    if blocking and GIT_PUSH.search(command):
        push_blockers = [
            r for r in blocking
            if r["merge_mode"] != "per-slice-pr" and _push_targets_run(command, r)
        ]
        if push_blockers:
            run = push_blockers[0]
            return (
                "spec-loop run %s is active and has not reached the publish prompt "
                "(Phase 5): the loop never pushes until the human chooses how to publish. %s"
                % (run["run_id"], _remediation(run))
            )

    if blocking:
        compound = CHECKOUT_MAIN.search(command) and COMMIT_MERGE_PUSH_WORD.search(
            CHECKOUT_MAIN.sub("", command)
        )
        on_main = GIT_COMMIT_OR_MERGE.search(command) and current_branch(cwd) in ("main", "master")
        if compound or on_main:
            run = blocking[0]
            return (
                "spec-loop run %s is active: commits/merges on main/master are reserved for "
                "the human's publish choice (Phase 5). Work happens on the integration "
                "branch%s. %s"
                % (
                    run["run_id"],
                    " (%s)" % run["base_ref"] if run["base_ref"] else "",
                    _remediation(run),
                )
            )

    return None


def check_write(file_path, runs, project_root):
    """Return a deny reason for this Write/Edit target, or None to allow."""
    if not file_path:
        return None
    target = os.path.realpath(os.path.expanduser(file_path))
    protected = {
        os.path.realpath(os.path.expanduser(QUALITY_GATE_CONFIG)),
        os.path.realpath(os.path.join(project_root, QUALITY_GATE_OVERLAY)),
    }
    if target in protected:
        run = runs[0]
        return (
            "spec-loop run %s is active: never edit the quality-gate config (global "
            "~/.claude/spec-loop-2/quality-gate.json or the repo overlay "
            ".spec-loop/quality-gate.json) mid-run — weakening thresholds to force a pass "
            "is forbidden. Adjust it after the run via /spec-loop:quality-gate. %s"
            % (run["run_id"], _remediation(run))
        )
    return None


def _stop_block_reason(run, runnable):
    """The block text for one runnable, unescalated, controller-owned run."""
    rid = run["run_id"]
    return (
        "spec-loop run %s has %d runnable slice(s) (%s) and no open escalation: a wave "
        "boundary is a dispatch point, not a reporting boundary. Continue Phase 2 step 1 "
        "in THIS turn — compute the wave, prepare worktrees, dispatch — instead of "
        "reporting status. If a wave you already dispatched is still in flight, wait for "
        "its completion notification rather than re-dispatching: slice status stays "
        "pending until collection, so these ids can include work already running. If "
        "you are deliberately ending the turn anyway, say why in your next message so "
        "the transcript carries the reason. If the human asked you to hold, write "
        "docs/spec-loop/%s/.paused, which relaxes this gate alone. If you are not the "
        "controller of this run, this gate is not aimed at you — only the session "
        "recorded in docs/spec-loop/%s/.controller-session is blocked. %s"
        % (rid, len(runnable), ", ".join(runnable), rid, rid, _remediation(run))
    )


def check_stop(session_id, runs):
    """Return a reason to block this turn from ending, or None to allow.

    Narrowed to the controller session, unlike check_bash/check_write: this
    gate denies INACTION, so its false positives are not self-limiting.
    `.paused` relaxes THIS gate only, never find_active_runs.
    """
    for run in runs:
        if os.path.exists(os.path.join(run["dir"], ".paused")):
            continue
        marker = _controller_marker(run)
        if not marker or not session_id or session_id not in marker:
            continue
        runnable = _blocking_slices(run)
        if not runnable:
            continue
        return _stop_block_reason(run, runnable)
    return None


def evaluate(payload):
    """Return a deny reason for this hook payload, or None to allow."""
    project_root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    runs = find_active_runs(project_root)
    if not runs:
        return None

    # Branch on the EVENT first: a Stop payload carries no tool_name key at
    # all, so a tool-keyed branch would pass unit tests and never fire live.
    if payload.get("hook_event_name") == "Stop":
        if payload.get("stop_hook_active"):
            return None  # this fire ends the continuation a block caused
        return check_stop(payload.get("session_id"), runs)

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    if tool == "Bash":
        return check_bash(tool_input.get("command", ""), payload.get("cwd"), runs)
    if tool in ("Write", "Edit", "MultiEdit"):
        return check_write(tool_input.get("file_path"), runs, project_root)
    return None


def main(argv=None):
    try:
        payload = json.load(sys.stdin)
        reason = evaluate(payload)
    except Exception:  # noqa: BLE001 — deliberate fail-open (see module docstring)
        return 0
    if not reason:
        return 0
    if payload.get("hook_event_name") == "Stop":
        # A Stop block is a DIFFERENT wire shape: top-level decision/reason,
        # confirmed on Claude Code 2.1.260. The shape below is ignored here.
        print(json.dumps({"decision": "block", "reason": reason}))
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
