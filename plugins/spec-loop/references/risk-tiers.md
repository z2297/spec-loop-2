# Risk tiers — assignment, and what each tier buys

Single home of the tier contract. The controller assigns `risk_tier` per slice during
decomposition (Phase 0.7); `slice-wave.workflow.js` turns it into a review shape. When this file
and the workflow disagree, the workflow is what runs — fix one of them in the same change.

## Tier assignment heuristics (use when decomposing, and when splitting)

- **Tier 3** if the slice touches any of: auth/permissions, secrets/credentials, database schema
  or migrations, money/billing, PII/security, public/exported API or types, error-handling or
  retry/fallback logic, concurrency.
- **Tier 1** only if the slice is provably free of behavioral surface (docs/config/comments/pure
  helper with tests).
- **Tier 2** for everything else — the default.

`--risk-floor N` on `/spec-loop` raises the minimum tier for the whole run (e.g. `--risk-floor 2`
forbids Tier-1 reviews). Split children inherit their parent's tier (`dag.py ingest-split`); the
controller may raise a child but never lowers it below the floor.

## Tier → review shape (as implemented)

`review_tier` starts at `risk_tier`, is promoted one tier by `--thorough`, and can be promoted to 3
mid-slice by the surface check below. Everything in this table keys off `review_tier`.
"session" = the model the run itself is on (`inherit` in the workflow).

| | **Tier 1** | **Tier 2** | **Tier 3** |
|---|---|---|---|
| Plan critique | none | one `plan-critic`, all five mandates, session/low | `plan-critic` (session/high, full council) + `guardian` (session/high, risk lane) |
| Reviewers | one `pr-reviewer`, all lanes, sonnet/low | one `pr-reviewer`, all lanes, session/medium | two `pr-reviewer`s: correctness + errors + risk (session/high); tests + types + design + comments + conventions (sonnet/high) |
| Blocking bar | **P0** | **P0 + P1** | **P0 + P1** |
| Finding verification | none | none | batched `finding-verifier` over all open findings, once per fix round (sonnet/low) |
| Simplify polish | none | none | one `simplifier` pass (sonnet/low), non-blocking, skipped when `ctx.polish === false` |
| Per-slice agent cap | 10 | 18 | 32 |

The panel composition above is fixed: the run's scope ceiling is judged by plan-critic's
weighted **scope lane**, a mandate on the existing member, not a fourteenth agent. Panel
size is load-bearing — a counted extra member raises the objection threshold (a solo
Tier-2 plan-critic loses its veto at n=2; `--thorough` Tier 3 would need 3 objections
instead of 2).

At Tier 1 and 2 the single reviewer's model may be overridden by config
(`models.reviewer`); the Tier-3 pair is fixed. Findings below the bar are never
verified and never fixed — they are recorded as the sidecar's `review.residual`.

### Same at every tier

- **Quality gate** — a `verifier` agent (haiku/low) runs `quality_gate.py` in parallel with the
  review, at every tier. It is **blocking**: each violation becomes a P1 `quality-gate` finding
  that enters the fix loop, and survivors escalate as `quality-gate-block`. Thresholds are never
  weakened to pass. Fixes for these findings are behavior-preserving refactors only.
- **Fix loop ≤2 rounds** — each round: `implementer` in fix mode (sonnet/medium round 1,
  session/medium round 2) receives every open blocking finding at once and may refute one with
  `file:line` counter-evidence, then a `re-reviewer` (sonnet/low) adjudicates ADDRESSED /
  NOT_ADDRESSED / REFUTATION_ACCEPTED and reports new breakage. Findings still open after round 2
  escalate (`review-block`, or `quality-gate-block` if any came from the gate).
- **Full verification** — a `verifier` (haiku/low) runs the full suite plus the quality gate in the
  worktree. A red suite buys exactly one `debug-fix` dispatch (`implementer`, session/high, root
  cause before any change); anything else escalates. `DONE` is only reachable through this stage.
- **Right-size gate** — the planner may return `SPLIT` instead of a plan at any tier, and the
  Tier-2/3 critique panel may recommend one; either is autonomous (see `split-ingestion.md`).

### `--thorough`

Promotes every slice's review shape one tier (`min(risk_tier + 1, 3)`), and at Tier 3 adds a third
critic — `skeptic` (sonnet/high, premise lane) — to the panel. It never changes the recorded
`risk_tier`, only the shape; the sidecar carries both (`risk_tier`, `review_tier`).

### Deterministic auto-promotion by surface

After implementation and before review, the workflow matches the implementers' `touched_files`
against `tier3_surfaces` (glob list from the quality-gate config: global
`~/.claude/spec-loop-2/quality-gate.json`, extended by the per-repo `.spec-loop/quality-gate.json`
overlay). Any match promotes `review_tier` to 3 and records a `decision` event with the rationale.

- Globs are path-anchored loosely (an implicit leading `**/`), `*` stays inside a path segment,
  `**` crosses segments — `*.sql`, `src/auth/**`, `**/migrations/*` all behave as expected.
- This is the mechanism for "never review below what the code warrants": a slice planned as Tier 1
  that turns out to touch auth gets the Tier-3 review, panel of two reviewers, batched finding
  verification, simplify pass, and the 32-agent cap.
- Promotion happens *after* the critique stage, so a critique that already ran is not re-convened —
  only later stages escalate with the tier. A tier-3 surface a human wants critiqued belongs in
  the tier assignment or behind `--thorough`.

## Escalation-relevant consequences

Everything the tier decides funnels into exactly two of `escalation-gate`'s six triggers:
`review-block` (blocking findings survive the fix loop, or verification cannot pass) and
`quality-gate-block` (gate violations survive it). The sixth trigger, `refactor-scope` is
not one of them: it fires at plan time against a run-level ceiling, and no tier setting moves it —
a Tier 1 docs slice and a Tier 3 auth slice are judged against the same declared-rewrite numbers.
The `budget-exhausted` record the per-slice agent cap emits is mechanical, not a judgment — and
the caps in the table above are only one of its two sources; the other is the loop's per-stage
token floor, which no tier setting changes. A spent loop bound is neither: it escalates as
whatever actually stalled (`run-state-v2.md`).

An over-scope record (`critique.over_scope`) is **not** in that funnel. It is record-only:
it is carried into the `council-verdict` event and the sidecar, counted null-honestly by
`run_metrics.py`, and read by a human — it raises no trigger, blocks nothing, and is never
a finding. Work the council judged out of scope and asked not to be built is a
`defer`-hinted concern, recorded as a `deferred` event.
