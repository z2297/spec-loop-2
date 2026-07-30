# Migrating from spec-loop v1

For someone who has run v1. The theology is unchanged — what moved is the machinery underneath it.
If you only read one paragraph: keep using `/spec-loop` the same way, expect the same escalation
behavior, and let in-flight v1 runs finish on v1.

## Requirements

- **Claude Code ≥ 2.1.154** — the Workflow tool and plugin-bundled `workflows/` directories.
- The run must be able to use the Workflow tool. `/spec-loop` is your opt-in; you never type
  "ultracode".
- **Fallback exists.** If the tool is unavailable or you deny it, the controller sets `dag.json`
  `mode: "inline"` and dispatches one `slice-worker-fallback` agent per slice — the same pipeline
  shape, same loop bounds, same caps, dispatched synchronously via `Task`. Slower and more
  expensive per slice, identical contracts.

## What changed

**Waves are Workflow-native.** v1 spent a session-model agent (`spec-loop-slice`) on orchestrating
each slice: it decided what to dispatch next, in prose. v2 puts that control flow in
`workflows/slice-wave.workflow.js` — one invocation per wave, slices under `parallel()`, each
running plan → critique → implement → review ∥ quality gate → fix → verify as deterministic code.
Loop bounds (replan ≤1, task retry ≤1, fix rounds ≤2, debug-fix ≤1) and per-slice agent caps
(10/18/32 by review tier) are constants in that file rather than instructions an agent might drift
from. Every LLM→LLM handoff is a schema-forced structured return.

**Critics and reviewers consolidated.** v1's five Iron Council members are now three lanes on two
agents used tier-scaled (`plan-critic` carries all five mandates; `guardian` and `skeptic` are the
risk and premise lanes). v1's seven review-aspect specialists are one `pr-reviewer` that covers
every lane in a single pass with per-aspect attestation — seven agents re-reading the same diff
cost more than one reviewer thinking harder. Net: **13 agents, down from 22**, and **5 skills, down
from 21** (the loop's own machinery is agents, one workflow, and reference files — not skills).

**Run state is structured.** v1 pinned line grammars in `decisions-log.md`, `escalations.md`, and
`slice-*-agents.jsonl`, and metrics scraped them (plus Claude Code transcripts). v2's machine
channels are `events.jsonl` (append-only, typed events) and one `slice-<id>-status.json` sidecar per
slice, validated fail-closed on persist. The prose files are *rendered* from those objects for
humans and carry no grammar — never hand-write them. `dag.json` is still the sole authority on run
structure, now `schema_version: 2`. Full shapes: `references/run-state-v2.md`.

**Config moved.** `~/.claude/spec-loop/` → `~/.claude/spec-loop-2/` (`quality-gate.json`,
`knowledge-graph.json`). Your first run offers to import the v1 files rather than making you
re-answer; the offer is batched into the single Phase-0 question round with everything else. Two
additions: a per-repo `.spec-loop/quality-gate.json` overlay (committed, deep-merged over the
global config — it may tighten thresholds and extend `tier3_surfaces`, and the guard hook protects
both paths while a run is `.active`), and `tier3_surfaces` — globs that deterministically promote a
slice's review to Tier 3 when the implementation touches them, no judgment involved
(`references/risk-tiers.md`).

**New flag: `--thorough`.** Promotes every slice's review shape one tier and, at Tier 3, adds the
`skeptic` to the critique panel. It does not change recorded risk tiers.

**No budget knob.** v2 deliberately has no `--budget` flag. Bounding is structural: the loop bounds
and agent caps above, plus a per-stage token floor below which a slice reports rather than starts a
dispatch it cannot finish. That report arrives as a `budget-exhausted` escalation — a mechanical
resource request, not a sixth judgment trigger.

## What stayed

- **The autonomy contract.** `escalation-gate`'s five SURFACE triggers, the materiality heuristic,
  the precedent check against prior runs' answered escalations, and PROCEED-plus-log as the default
  — unchanged, including the batching seam: one `AskUserQuestion` round per wave boundary, never
  mid-wave, never one question at a time.
- **`verification-before-completion` is still never overridden**, at any layer, by anything.
- **Single-branch integration.** Every slice merges `--no-ff` into ONE local integration branch,
  serially, by the controller alone; nothing is pushed before your publish choice
  (`--per-slice-pr` remains the sole exception).
- **Guard hook markers.** `.active` / `.publish-choice` / `.done` and `spec_loop_guard.py` behave
  exactly as in v1. A denial still means the run has not earned that operation yet.
- **The quality gate.** Same metrics, same default thresholds, same prohibitions — thresholds are
  never weakened to pass, and gate findings get behavior-preserving refactors only. It runs at
  every tier and blocks.
- **The knowledge graph.** Same vault layout and the same default `subfolder` (`spec-loop`), so v2
  runs accrete onto the nodes your v1 runs wrote instead of starting a parallel graph.
- **Risk-tier assignment.** The Tier 1/2/3 heuristics are the v1 heuristics verbatim; only what
  each tier *buys* was re-expressed as the workflow's review shape.

## What does not carry over

- **v1 run directories are read-only artifacts.** The dashboard renders them, honestly labelled as
  v1 (no sidecars, so waves show as projected and escalations/decisions come from the prose
  scrape), and `run_metrics.py trend` includes them with `basis: "legacy-v1-prose"` so the softness
  is visible. Nothing migrates or rewrites them, and no v2 tool writes into a v1 run dir.
- **In-flight v1 runs should finish on v1.** There is no `--resume` path from a v1 run into v2: the
  state shapes, the sidecar contract, and the wave journal all differ. Let the run reach its
  publish prompt under v1, then start your next run on v2.
- **v1's prose channels are not read as machine input.** If you had tooling parsing
  `decisions-log.md` lines or `slice-*-agents.jsonl`, point it at `events.jsonl` instead.
- **The v1 skills you may have invoked by hand** (`iron-council`, `review-depth-map`,
  `subagent-driven-development`, `writing-plans`, `brainstorming`, `runbook`, …) do not exist in
  v2. Their doctrine lives in the controller command, the agent definitions, and
  `references/risk-tiers.md`; the way to invoke it is `/spec-loop`.
