# Request — loop-continuation gate

## Observation that prompted the run (human, verbatim)

> Because I stopped the loop instead of continuing it. The Phase-2 contract is to repeat
> until next-wave returns nothing runnable, and after closing wave 3 there was no blocker —
> no open escalations, clean tree, s4 runnable. I ended the turn at a reporting boundary and
> asked instead of proceeding. That was my error, not a gate.

## What this run builds

A deterministic backstop for the one Phase-2 invariant that has none: **loop continuation**.
Approved scope (human, this session): "Gates + prose".

Root cause, two parts:

1. **The instruction sits far from its point of use.** `commands/spec-loop.md` states "Repeat
   until `dag.py next-wave` returns no runnable slices" at the top of Phase 2, ~130 lines above
   where a wave actually closes. Phase 2 ends after step 8 (knowledge graph) with no instruction
   to return to step 1, and step 7 closes on "re-dispatch the wave", which reads terminal.
2. **The run's GIT-shaped invariants have a mechanical backstop; loop continuation is a
   non-git invariant with none.** `scripts/spec_loop_guard.py` denies push-before-publish, broad
   staging, and commit-on-`main` — all of them positive acts an agent typed, and all
   pattern-matchable. Loop continuation, like max-parallel, serial `--no-ff` merges,
   never-ask-mid-wave, and the DONE-evidence rule, is controller prose with nothing behind it.
   Continuation rests entirely on controller judgment at the moment the controller has the
   strongest pull toward summarising a just-merged wave.

   (An earlier draft of this file claimed *every* other Phase-2 invariant had a backstop. That
   was false and the intake council caught it: the guard covers git-shaped invariants only. The
   corrected claim is narrower and still sufficient. Note the asymmetry it exposes — every
   existing gate denies something an agent TYPED, whereas a Stop gate denies INACTION, which is
   why its false-positive surface is not self-limiting the way the others' are.)

The failure has two distinct exits, and they need different gates: ending the turn with a prose
report, and calling `AskUserQuestion` when nothing is actually open.

## In scope

- **Gate A — `PreToolUse` on `AskUserQuestion`** in `spec_loop_guard.py`: deny when an active run
  has runnable slices AND `open-escalations` is empty. Reason names the runnable slice ids and the
  compliant alternative (continue Phase 2 step 1, or open the escalation record first).
- **Gate B — `Stop`** in `spec_loop_guard.py`: block ending the turn while an active run has
  runnable slices; honour `stop_hook_active` as a one-shot so a genuinely wedged controller still
  gets out after one push.
- Both gates reuse `find_active_runs()`, import `dag.next_wave` and `run_state.open_escalations`
  rather than reimplementing wave membership, and fail open on any exception per the module's
  existing doctrine.
- Escape valve: a `.paused` marker (controller writes it when the human says hold) allows both
  gates; the existing stale-marker remediation (`--resume` / clear `.active`) still applies.
- `hooks/hooks.json`: register the `AskUserQuestion` matcher and the `Stop` event.
- Empirical hook probes BEFORE relying on either gate: (a) does `PreToolUse` fire for
  `AskUserQuestion`? (b) does a sync `Stop` hook honour top-level `{"decision":"block","reason":…}`
  in this Claude Code version? Record results in `references/platform-probes.md` alongside the
  existing 2026-07-07 subagent-coverage probe. A probe that comes back negative degrades that gate
  to prose — it does not get shipped as a gate that silently does nothing.
- **Prose, at the point of failure**: a new Phase-2 **step 9 "Close"** — re-run `next-wave`;
  non-empty → return to step 1 in the SAME turn with no status report; `done` → Phase 5;
  `deadlock` → escalate. Plus one Invariants line: a wave boundary is a dispatch point, not a
  reporting boundary. Plus one entry under `escalation-gate`'s "Not triggers": **Wave boundary** —
  closing a wave decides nothing, so it is never a question.
- Tests in the existing `plugins/spec-loop/scripts/test_spec_loop_guard.py`: runnable + no
  escalations → deny; open escalation → allow; `next_wave` done → allow (the publish prompt);
  `.paused` → allow; `stop_hook_active` → allow; malformed `dag.json` → allow (fail-open).
- CHANGELOG entry under `[Unreleased]`; docs kept truthful (plugin README, references).

## Out of scope (run-level scope ceiling)

- The `loop-boundary` audit event and its `run-state-v2.md` event type — explicitly deferred by
  the human when choosing "Gates + prose" over "Gates + prose + audit event".
- Any change to `slice-wave.workflow.js`, `dag.py`, `run_state.py`, or `worktrees.py` logic.
  The gates import from `dag.py`/`run_state.py`; they do not modify them.
- Fixing Phase 5's marker-vs-commit ordering (the reason prior runs leave `.done` /
  `.publish-choice` untracked). Observed this run, recorded as deferred, not built.
- A new standalone hook script. Both gates live in `spec_loop_guard.py`.
- Any release/version bump. The repo sits at 2.3.0; this lands under `[Unreleased]`.
- Weakening or re-tuning quality-gate thresholds.

## Notes on the running environment

The installed plugin is **2.2.0** (`~/.claude/plugins/cache/spec-loop/spec-loop/2.2.0`) while this
repo is at **2.3.0**. The gates built here therefore do NOT protect this run — they take effect
once the marketplace copy is reinstalled. The controller's own continuation discipline this run is
still prose-only.

Tree state at intake: clean except one untracked user artifact,
`docs/spec-loop/spec-loop-last-two-runs.pdf`, deliberately left untracked (not the run's to
commit); the four prior-run completion markers were committed as pre-run housekeeping.
