# spec-loop 2

Spec-driven autonomous development loop for Claude Code, Opus 5-native.

Give `/spec-loop` one request. It decomposes the work into small vertical
slices, then runs each **wave** of independent slices as a deterministic
Workflow script: every slice gets a plan, a plan critique, test-first
implementation, a consolidated PR review running in parallel with a scripted
quality gate, a bounded auto-fix loop, and full verification — in an isolated
git worktree on its own branch. The controller merges verified slices
serially into one integration branch, batches every open question into a
single prompt per wave boundary, and finishes with a committed runbook and a
publish choice. It never pushes until you choose how.

## Requirements

- Claude Code ≥ 2.1.154 with the Workflow tool (invoking `/spec-loop` is the
  opt-in; when Workflow is unavailable the loop falls back to inline
  background agents — same pipeline, slower, recorded as `mode: "inline"`).
- `git`, `python3`. All bundled scripts are stdlib-only; `lizard` or `radon`
  are used for quality metrics when already installed, never installed.

## Usage

```
/spec-loop add CSV export with per-column filters to the reports page
/spec-loop --from-plan                  # execute the most recent plan-mode plan
/spec-loop --thorough <request>         # promote every slice's review one tier
/spec-loop --resume 20260730-csv-export
```

Flags: `--branch <name>` `--base-branch <name>` `--max-parallel N` (default 5)
`--risk-floor 1|2|3` `--thorough` `--per-slice-pr` `--from-plan [path]`
`--resume <run-id>`.

Other commands: `/spec-loop:review-pr` (one consolidated review of any diff),
`/spec-loop:peer-review` (read-only review of a real PR against business
requirements), `/spec-loop:quality-gate` and `/spec-loop:knowledge-graph`
(config), `/spec-loop:dashboard` (terminal) and `/spec-loop:dashboard-serve`
(web, Docker-preferred singleton on port 8787), `/spec-loop:jira-intake` (read
one Jira card, refine it with you, render the comments it would post, and print
the loop handoff).

## The pipeline

One Workflow invocation per wave (`workflows/slice-wave.workflow.js`). Per
slice, in deterministic JS:

| Stage | Who | Model / effort |
|---|---|---|
| Plan (+ right-size gate) | `slice-planner` | session / low |
| Critique — Tier 2 | `plan-critic` (all five council mandates; the Scope lane is weighted and owns the over-scope record) | session / low |
| Critique — Tier 3 | + `guardian` (risk-only SAFETY veto); `--thorough` adds `skeptic` | session / high |
| Implement (sequential per task) | `implementer` | haiku / sonnet / session by task lane |
| Review ∥ quality gate | `pr-reviewer` (two lanes at Tier 3) ∥ `verifier` running `quality_gate.py` | tier-scaled ∥ haiku |
| Verify findings (Tier 3) | `finding-verifier` — ONE batched pass, CONFIRMED-by-default | sonnet / low |
| Fix loop (≤2 rounds) | `implementer` in fix mode (refutation right) + `re-reviewer` | sonnet → session |
| Simplify (Tier 3 only) | `simplifier`, non-blocking | sonnet / low |
| Verify | `verifier` — full suite + gate re-check, ≤1 debug-fix | haiku / low |

Loop bounds and per-tier agent caps (10/18/32) are workflow constants;
exceeding one is an escalation, never a silent truncation. Cost lands around
**2 agents for a Tier-1 slice, ~7 for a typical Tier-2, ~25–30 worst case** —
versus roughly 7 / 25 / 90 in v1.

Risk tiers are assigned at decomposition (`references/risk-tiers.md`) and
promoted deterministically when the implementation touches a `tier3_surfaces`
glob (auth, migrations, security paths — configurable). An answered
escalation re-invokes the wave with ONLY its non-terminal slices (merged work
never re-enters) and the journal cache: the escalated slices' completed
stages replay free where the cache holds; only the answered stage runs live.

A run may also declare an optional run-level `scope_ceiling` — things this run must not
build — which is prefixed verbatim to every agent's prompt. The council records a scope
judgement against it as `critique.over_scope`, and that record is **record-only**: it
blocks nothing, filters no finding, suppresses no split and raises no escalation trigger.
The weighting on the critic's Scope lane is the only part of this that reduces
scope-expansion effort; the ceiling and the record exist to make a judgement durable and
readable, not to prevent the work. Contracts:
`references/risk-tiers.md` and `references/run-state-v2.md`.

## Runtime expectations (Opus 5)

Measured across real multi-slice runs (2026-08, .NET repo with a ~9,400-test
suite): a slice lands in **~40–70 minutes all-in** — wave pipeline plus the
controller's serial merge and integration suite — so a 3–5 slice run is a
**3–5 hour job by design**, not a hang. Tier-3 work costs more: the critic
panel, batched finding verification, simplify pass, and high-effort reviews
put an observed Tier-3 remediation wave at ~1.5–2 hours. A Phase-5 cross-slice
review that confirms a real integration defect adds a remediation slice — one
more wave — and that is the loop working, not overrunning.

Two calibration notes. First, v1-on-Opus-4.8 timings are not the baseline:
v1 on Opus 5 measured ~3.5 hours per Tier-3 slice; v2 is the cheaper
architecture on the same model. Second, wall clock ≠ compute: the loop is
built to run unattended, and question rounds + the publish prompt fire a
desktop alert so a finished run is never silently parked overnight.

## Escalations

The loop surfaces a question only on the escalation-gate's six triggers:
genuine ambiguity, a material assumption, an unfixable review block, a
council objection, an unfixable quality-gate block, or a plan-time
refactor-scope breach — after checking prior runs for a precedent that
already answers it. The last is the only one the wave raises from its own
arithmetic: the slice planner declares how much existing code its plan
rewrites, and the workflow compares those numbers to the configured ceiling
before a single line is implemented. Everything else proceeds and is logged
as a decision event with rationale and reversibility. All open escalations
arrive as ONE question round per wave boundary, recommended default first.

## Quality gate

`scripts/quality_gate.py` measures the slice diff (cyclomatic/cognitive
complexity, method/class length, parameters, nesting, CRAP with coverage) —
deterministic, script-first, agents cannot weaken it: while a run is
active the guard hook denies both a `Write`/`Edit`/`MultiEdit` targeting
the config (`check_write` in `spec_loop_guard.py`) and a shell-side write
to it — redirect, `tee`, `mv`, `cp` or `sed -i` (the
`QUALITY_GATE_WRITE` pattern, enforced in `check_bash`). Global config
`~/.claude/spec-loop-2/quality-gate.json` (first run offers presets or import
from v1); a committed per-repo overlay `.spec-loop/quality-gate.json`
deep-merges over it and hosts `tier3_surfaces`. Gate violations join review
findings in the same fix loop as behavior-preserving refactors.

## Knowledge graph (optional)

Opt-in Obsidian integration (`~/.claude/spec-loop-2/knowledge-graph.json`):
the controller upserts decision/pattern/system/domain nodes at wave
boundaries and the runbook, reads context once per wave, and injects ≤120
words of prior knowledge per slice. Idempotent by `(type, id)` — v2 runs
accrete onto v1 vault nodes. Workers never touch the graph. Secrets are
redacted by a deterministic floor; writes never leave the configured
subfolder.

## Run state & guard

Everything durable lives under `docs/spec-loop/<run-id>/` —
`dag.json` (structure + recorded waves), per-slice sidecars, `events.jsonl`
(the machine channel `run_metrics.py` reads), rendered prose logs, and the
committed `runbook.md`. Contract: `references/run-state-v2.md`. While a run's
`.active` marker exists, `scripts/spec_loop_guard.py` — registered on
`PreToolUse` for `Bash` and `Write|Edit|MultiEdit`, and on `Stop` — blocks,
in ANY session, pushes, broad staging (`git add -A`), commits/merges on
`main`/`master` and quality-gate config edits. One further block applies
only in the session recorded in `.controller-session`: that session may not
end its turn at a wave boundary while the run still has runnable slices and
no open escalation. That loop-boundary block is additionally skipped when
`stop_hook_active` is true, so it pushes once per stall rather than fencing,
and is relaxed — alone among the blocks — by a `.paused` marker. Markers,
not vibes: the run ends when the human's publish choice is recorded.
Work the council judged out of scope and asked not to be built is logged as its own
`deferred` event and rendered into `decisions-log.md`; a malformed scope record fails the
sidecar closed rather than reading as clean.

## Components

- **Commands (8)**: spec-loop, review-pr, peer-review, quality-gate,
  knowledge-graph, dashboard, dashboard-serve, jira-intake.
- **Workflow (1)**: slice-wave.
- **Agents (13)**: slice-planner, plan-critic, guardian, skeptic,
  implementer, pr-reviewer, finding-verifier, re-reviewer, simplifier,
  verifier, runbook-writer, peer-reviewer, slice-worker-fallback.
- **Skills (5)**: escalation-gate, using-spec-loop, test-driven-development,
  systematic-debugging, verification-before-completion.
- **Scripts (13 runtime + tests)**: dag, worktrees, run_state, review_package,
  quality_gate, knowledge_graph, run_metrics, pr_resolver, jira_client, jira_intake,
  spec_loop_guard, dashboard_server, dashboard_launcher (+ dashboard_assets, and the
  `slice_wave_contract_base` and `slice_wave_contract_radius_driver`
  test-support modules, which back four Node harness modules:
  `slice_wave_behaviour`, `slice_wave_radius`, `slice_wave_radius_partial`
  and `slice_wave_replan`).

## Migrating from v1

Read `references/migration-from-v1.md`. Short version: theology unchanged,
internals rebuilt; config namespace moved (first run offers import); v1 run
dirs stay readable in `trend` and the dashboard; finish in-flight v1 runs on
v1.

## License

MIT
