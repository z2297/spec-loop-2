# spec-loop 2

A Claude Code plugin marketplace hosting **spec-loop 2.x** — the Opus 5-native,
Workflow-orchestrated revision of the spec-driven autonomous development loop.

Give it one feature request; it decomposes the work into targeted slices, then
drives each wave of slices through a **deterministic Workflow script** — plan →
plan-critique → TDD implementation → consolidated review in parallel with a
scripted quality gate → bounded auto-fix → full verification — merging each
verified slice serially into one integration branch, and surfacing to you
**only** when it genuinely cannot decide.

## Why a second major version

v1 orchestrated everything in prompt space: a session-model slice agent carried
~23k tokens of skill text for hours, five-member councils convened twice per
slice, six review aspects re-read the same diff, and every finding got its own
verifier agent. Measured on an Opus 5-class model, one real Tier-3 slice cost
**3h27m and 261M tokens**. v2 moves the orchestration into deterministic
JavaScript (the Claude Code Workflow tool) and consolidates the review
machinery — same theology, a fraction of the dispatches:

| | v1 | v2 |
|---|---|---|
| Agents per typical (Tier-2) slice | ~25 | ~7 |
| Agents per worst-case slice | ~90 | ~25–30 |
| Slice orchestrator | Opus-class agent, hours | JS control flow, zero tokens |
| Escalation re-dispatch | replays the review stages | journal replay — only the answered stage runs |

What did **not** change: the escalation-gate autonomy contract (five surface
triggers, precedent check, one batched question per wave), single-branch
integration with a guard hook, the scripted quality gate agents cannot weaken,
knowledge-graph integration (v2 accretes onto the same vault nodes), and
null-honest metrics.

What 2.x adds on top: a run may declare a **scope ceiling** — things the run must not
build — which is prefixed to every agent's prompt, and the council records its scope
judgement in the run's events and sidecars with its reason intact. That record blocks
nothing. Weighting the critic's scope lane is the only part of it that reduces
scope-expansion effort; the ceiling and the record exist so a judgement is written down
and cannot quietly come back, not so that scope creep stops happening. Details:
`plugins/spec-loop/references/run-state-v2.md`.

## Install

```
/plugin marketplace add z2297/spec-loop-2
/plugin install spec-loop
```

Requirements: Claude Code ≥ 2.1.154 with the Workflow tool (an inline fallback
runs slices as background agents when Workflow is unavailable), `git`,
`python3` (all bundled scripts are stdlib-only — zero dependencies).

## Usage

```
/spec-loop <request>
/spec-loop --from-plan            # execute the most recent plan-mode plan
/spec-loop --thorough <request>   # promote every slice's review one tier
/spec-loop --resume <run-id>
```

See `plugins/spec-loop/README.md` for the full manual: flags, risk tiers, the
review pipeline, quality-gate and knowledge-graph configuration, the dashboard,
and `/spec-loop:peer-review`. `/spec-loop:jira-intake` turns a single Jira card
into a refined, gitignored intake artifact and prints the loop handoff — it
never starts the loop, and its only Jira write is adding a comment, off by
default and behind an explicit confirmation. Migrating from v1? Read
`plugins/spec-loop/references/migration-from-v1.md`.

## Repo layout

```
.claude-plugin/marketplace.json   the marketplace manifest
plugins/spec-loop/                the plugin (everything that ships)
scripts/                          dev/CI tooling (validators, coverage gate, release)
docs/                             run artifacts from dogfooded runs
```

## CI

`validate_marketplace.py` (manifest + frontmatter contracts), the unittest
suites for every bundled script, a stdlib-only coverage floor gate
(`measure_coverage.py`), Node built-in tests for the dashboard client, and
`claude plugin validate` — all must pass.

## License

MIT
