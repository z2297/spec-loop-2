# Changelog

All notable changes to the spec-loop plugin are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/). History before 2.0.0 lives in the
[v1 repository](https://github.com/z2297/spec-loop).

## [2.0.0] - 2026-07-30

Ground-up Opus 5-native rewrite. Same theology — autonomous spec-driven
development, surface only genuine decisions, built-in review, scripted quality
gates, knowledge-graph integration — rebuilt on the Claude Code Workflow tool
so orchestration is deterministic code instead of prompt text. Clean break:
schemas, agents, and internals redesigned; see
`plugins/spec-loop/references/migration-from-v1.md`.

### Added
- **Workflow-native waves** — one Workflow invocation per wave
  (`workflows/slice-wave.workflow.js`): slices run as deterministic JS
  pipelines with schema-forced structured handoffs, per-tier agent caps
  (10/18/32), bounded loops (fix ≤2, replan ≤1, task retry ≤1), fail-closed
  synthesis on unusable returns, and journal-cached resume — an answered
  escalation replays completed stages at zero cost and re-runs only the
  answered stage.
- **Consolidated review machinery** — one `plan-critic` carrying all five
  council mandates (premise/design/scope/risk/consistency) and one
  `pr-reviewer` carrying all review aspects with per-aspect attestation.
  Panels survive where independence pays: guardian (risk-only SAFETY veto) on
  intake/Tier-3, skeptic (premise-only) on intake/`--thorough`, two-reviewer
  split + ONE batched finding-verifier at Tier 3.
- **Mechanical finding-anchor checks** — review packages
  (`scripts/review_package.py`, `-U5`) embed a hunk index; a finding whose
  location or evidence quote doesn't match the code is refuted without
  judgment by the fixer (refutation right) or the batched verifier.
- **Deterministic run-state scripts** — `dag.py` (wave computation, split
  grafting), `worktrees.py` (worktree/branch lifecycle), `run_state.py`
  (fail-closed sidecar validation, `events.jsonl`, prose rendering) replace
  prompt-space scheduling.
- **`events.jsonl` machine channel** — pinned payload contracts (timing only
  from journal-extracted stamps, escalations paired by id, SAFETY flags);
  prose logs are rendered from the same objects and carry no machine grammar.
- **Tier auto-promotion** — implementer-touched files matched against
  `tier3_surfaces` globs promote the review shape deterministically.
- **`--thorough` flag**; per-repo quality-gate overlay
  (`.spec-loop/quality-gate.json`, guard-protected); `models` promotion knob.
- **Inline fallback** — `slice-worker-fallback` agent runs the same pipeline
  shape when the Workflow tool is unavailable (`dag.json` `mode: "inline"`).

### Changed
- Agent inventory 23 → 13; skills reduced to the judgment layers
  (escalation-gate, TDD, systematic-debugging, verification-before-completion,
  router); the 282-line slice-worker agent and the SDD/worktree/review-depth
  orchestration skills are deleted — their job is JS control flow now.
- Global config namespace `~/.claude/spec-loop/` → `~/.claude/spec-loop-2/`
  (first run offers import); the guard hook protects both the global config
  and the per-repo overlay.
- `run_metrics.py` reads events.jsonl + sidecars (schema_version 2); v1
  transcript scraping and prose-grammar parsing dropped (v1 run dirs still
  render in `trend` via a walled-off legacy path). Durations derive only from
  journal-extracted payload stamps — never the batch collection stamp.
- Dashboard reads recorded `waves[]` + sidecar v2 + events.jsonl; v1 run dirs
  render via legacy rules; container/state names moved to `spec-loop-2-*`.
- `/spec-loop:peer-review` consolidated to `peer-reviewer` + report-only
  `pr-reviewer` + a report-only quality-gate run; report `schema_version: 2`.
- Per-finding verifier agents, the whole-branch `code-reviewer` double-pass,
  and per-task reviewers below Tier 3 are gone; `code-simplifier` runs only at
  Tier 3/`--thorough` (at Tier 2, "simplify" is a finding category the fixer
  applies).

### Removed
- `council_contracts.py` (verdict validation is tool-layer schema enforcement;
  sidecar validation moved to `run_state.py`), `slice-*-agents.jsonl`, the
  pinned decisions-log/QUALITY-GATE line grammars, transcript token scraping,
  and the `--budget` flag (cost control is structural: caps + bounds; the
  Workflow token ceiling activates when the session sets a token target).

[2.0.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.0.0
