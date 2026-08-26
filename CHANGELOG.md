# Changelog

All notable changes to the spec-loop plugin are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/). History before 2.0.0 lives in the
[v1 repository](https://github.com/z2297/spec-loop).

## [Unreleased]

### Added
- **Run-level scope ceiling** — an optional `scope_ceiling` list in `dag.json` (validated
  only when present; a run without one stays fully valid and mutable), threaded through
  `ctx` and prefixed to **every** agent prompt by the wave's shared packet as a binding
  "do NOT build these" block. The read is type-safe, not merely null-safe: an array passes
  through, a lone non-empty string is coerced to a one-element list (a realistic return
  from an LLM controller populating `ctx` from prose), and any other non-array value reads
  as absent rather than throwing. Shape: `references/run-state-v2.md`.
- **Record-only `critique.over_scope`** — an optional `{flag, reason}` field on the
  council verdict contract, owned by plan-critic's weighted scope lane. It is carried
  into the `council-verdict` event and the slice sidecar untouched by any control-flow
  branch: it never blocks, never suppresses a split, never raises an objection, and is
  never a finding.
- **One durable `deferred` event per defer-hinted concern** — each `defer`-hinted council
  concern now emits its own `deferred` event (`{summary, source: "plan-critique"}`, plus a
  bare-boolean `over_scope: true` marker when applicable), read by the reviewer as advisory
  context only — never a findings filter.
- **Weighted scope lane on plan-critic** — plan-critic's existing Scope mandate now owns the
  over-scope record; no new agent, no change to any panel size or objection threshold.
- **Fail-closed sidecar validation and honest rendering of the scope record** — a present
  `critique.over_scope` must carry a real boolean `flag` and a string-or-null `reason`; a
  malformed record invalidates the whole sidecar (`persist_slice` raises and writes nothing)
  rather than being quietly ignored. Absent and explicit `null` are both valid and mean "no
  scope judgement was recorded" — which is a different claim from `flag: false`, and the two
  render differently. One shared renderer produces four distinct human outcomes and collapses
  none of them into another: nothing at all when no judgement was recorded, `scope: clean` for
  `flag: false`, `SCOPE-FLAGGED` plus the reason when one was given, and `scope: unreadable`
  when a present record's own shape cannot be trusted. The decisions-log verdict line and the
  slice report's `Iron Council` value share that renderer, so the two human surfaces cannot
  disagree; a `deferred` event whose payload marks `over_scope: true` renders with a `SCOPE `
  prefix in the decisions log.
- **Null-honest scope counters in `run_metrics.py`** — `safety.over_scope_deferrals` counts
  `deferred` events carrying that boolean marker, and therefore lives at the `safety` top
  level beside `deferrals_total`, **not** inside `safety.council`, whose every other key
  shares the council-verdict population. Both counters are null-honest:
  `safety.council.over_scope_flags` counts flagged `council-verdict` payloads and stays `null`
  when no payload carried a boolean flag, because "no payload recorded a scope judgement" is
  not evidence that nothing was over scope — and a malformed record counts as no record rather
  than as a clean one. The legacy v1-prose channel reports both as `null`; it never carried a
  scope judgement. Both feed reporting only: neither feeds a threshold, a gate or a blocking
  decision.

### Fixed
- **Wave-aborting unguarded `commits` read** — a task that legitimately committed nothing
  returns `DONE` with `commits` absent (not required by `TASK_RESULT`); the Stage-T loop's
  unguarded `r.commits.head` read threw a `TypeError` that the catch-all mislabelled as a
  budget-exhausted "wave interrupted" escalation. The read is now guarded the way the
  fix/debug-fix sites already guard it.
- **Missing `quality-gate-block` answer injection** — no prompt builder had a site for a
  human's answer to a quality-gate escalation, so the answer could not reach the
  re-dispatched slice. `fixPrompt` now carries it through `answerFor` ("apply it, do not
  re-raise"); `verifyPrompt` carries it through a new context-only sibling `answerContext`,
  which shows the answer without instructing a transcription-only reporter to change what
  it reports — the suite result and `quality.summary_pass`/`violations` stay verbatim from
  the real output.

## [2.1.0] - 2026-08-10
Runtime and trust fixes from the 2026-08-06/07 production-run analysis
(Groundworks.Jobs): active runtime was ~3–5h for 3–5 slices, but one run read
as 15h48m — 7.6h of it a silently-parked publish prompt, 2h20m a discarded
re-run of an already-merged slice, plus controller time re-verifying two
false-PASS gate labels caused by a guard-hook false positive.

### Fixed
- **Guard hook redirect false positive** — `spec_loop_guard.py` denied any
  command containing `quality-gate.json` plus any redirect character, so the
  verifier's read-only gate invocation with `2>&1` was blocked (two false
  PASS labels in run 20260807). A write must now actually target a
  `quality-gate.json` path (redirect into it, `tee`/`mv`/`cp` naming it,
  `sed -i` on it).
- **Wave re-dispatch re-ran merged slices** — the controller re-dispatched
  the full wave after escalation answers, relying on journal replay to make
  DONE slices free; a cache miss re-ran a merged slice against a deleted
  worktree for 140 minutes and the result was discarded. Re-dispatch now
  includes only non-terminal slices.
- **Agent-labeled gate verdicts** — the verifier returned a self-labeled
  PASS/FAIL enum that twice contradicted its own detail text. It now
  transcribes the gate JSON's `summary.pass` verbatim (`summary_pass`,
  null when no JSON was produced) and the workflow computes the status
  deterministically — null or any violation is FAIL, fail closed.
- **Run-state fragments from a drifted cwd** — `run_state.py` silently
  created `server/docs/spec-loop/<run-id>/` fragments when a `cd server &&`
  test command left the session cwd in a subdirectory. Every subcommand now
  refuses a `--run-dir` that lacks `dag.json` (exit 2) instead of creating
  one; Phase 5 verifies the run dir is whole at the repo root before `.done`.
- **Vacuous quality-gate passes** — a whole-run gate measurement could return
  `pass: true` with zero checks over a 60-file range, indistinguishable from
  a measured pass. `summary` now carries `checks` and `vacuous`; Phase 5
  treats a vacuous pass over a code-changing range as unmeasured, never green.

### Added
- **Human-wait alerts** — the controller fires a best-effort desktop
  notification (`osascript` + terminal bell) before every AskUserQuestion
  round and the publish prompt (observed: a finished run waited 7.6h
  overnight at the publish prompt).
- **Suite segmentation contract** — a `test_command` may be a ` ; `-joined
  segment list; the baseline step splits any invocation near the 10-minute
  tool ceiling per test project, and every runner executes each segment as
  its own tool call (a monolithic call at the ceiling was killed mid-suite
  twice in run 20260807's Phase 5).
- **Runtime expectations** — README documents the measured Opus 5 envelope
  (~40–70 min per slice all-in; 3–5 slice runs are 3–5 hour jobs) and that
  v1-on-Opus-4.8 timings are not the comparison baseline.

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

[Unreleased]: https://github.com/z2297/spec-loop-2/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.1.0
[2.0.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.0.0
