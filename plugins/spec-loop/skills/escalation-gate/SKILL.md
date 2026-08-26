---
name: escalation-gate
description: Use when running the spec-loop autonomously and about to stop, ask the human a question, request approval, or pause on a review BLOCK — decides whether to proceed-and-log or surface to the human, and how to record the decision
---

# Escalation Gate — the spec-loop autonomy contract

## Overview

This is the single decision procedure every spec-loop layer (controller, wave workflow stage,
fallback slice worker, and any skill they invoke) runs **before stopping or asking the human
anything**. Its job is to keep the loop autonomous by default and interrupt the human **only**
when a decision genuinely cannot be made.

In v2 the transport is structural: a workflow stage has no channel to the human at all. A stage
that would ask returns an `EscalationRecord` in its `SliceResult` (status `ESCALATED`); only the
controller can reach a person. The judgment below is still yours, at every layer.

This contract **intentionally overrides** the human checkpoints its chained doctrine would
otherwise raise: a design-approval gate before implementation, consent-before-`main` (satisfied
structurally — every slice works in its own worktree and merges only onto the run's integration
branch), and a review finding at or above the slice's blocking bar (routed here after the bounded
fix loop, never straight to a person).

`spec-loop:verification-before-completion` is **not** overridden — it remains a hard, no-human
gate (evidence before any completion claim), at every layer, always.

## The decision procedure

For any point where you would otherwise stop or ask, classify it:

### PROCEED + log (the default)

Take the action yourself and record one `decision` event when all of these hold:

- The choice is determinable from the spec, the codebase, existing conventions, or an
  unambiguous best practice, **OR**
- The assumption is trivial, cosmetic, and cheaply reversible (naming, formatting, internal
  helper placement, test fixture details), **AND**
- Getting it wrong does not silently change observable behavior, public contracts, persisted
  data, or security posture.

The record is one `decision` event, payload
`{summary, rationale, reversibility: trivial|moderate|high|n/a}` — appended by the controller
(`run_state.py append-event --type decision`, stamped with its clock), or pushed onto a stage's
`events[]` for the controller to stamp at collection (workflow scripts have no clock).
`decisions-log.md` is *rendered* from those events: never hand-write an entry, and never rely on its
wording — v2 pins no line grammar.

### SURFACE to human (only these five triggers)

Do not act. Return an `EscalationRecord` and let the controller batch it:

1. **Genuine ambiguity** — there are ≥2 valid interpretations that materially change scope or
   behavior, and the codebase/spec cannot resolve which is intended.
2. **Material assumption** — you would be assuming something non-trivial that affects behavior,
   scope, public contracts, persisted data, security, or external integrations. (Material
   assumptions must be stated and confirmed — never silently made.)
3. **Unfixable review BLOCK** — findings at or above the slice's blocking bar
   (`references/risk-tiers.md`) survive the bounded fix loop (≤2 rounds).
4. **Council objection** — the plan critique deems a request or plan **unworthy**: a majority
   of the panel OBJECTs, or any member raises a `safety.flag` (irreversible data loss, security
   hole, broken public contract). Lesser concerns (ENDORSE_WITH_CONCERNS, minority non-safety
   objections) are folded into the plan and logged — they do **not** surface.
5. **Unfixable quality-gate block** — the quality gate's metrics still exceed the configured
   thresholds after the fix loop's behavior-preserving refactors. Thresholds are never weakened
   to avoid this.

When uncertain whether something is "material": if a reasonable reviewer could reject the slice
over it, it is material → surface it.

The enum lives in `slice-wave.workflow.js` (`ESCALATION.trigger`). Three things that are
deliberately NOT judgment triggers, and must never be turned into one: `budget-exhausted` (the
workflow's guard emits it when a structural cap is hit — agent cap, stage token floor; it asks for a
resource, not a decision), `internal-error` (an unhandled exception aborted a slice, or a slice
returned no result at all; the record carries the real exception text together with the last
stage/role dispatched before the failure, which is the most recent dispatch rather than a per-throw
stage. This trigger reports a machine failure and asks the controller to retry, skip, or stop the
run, and no agent prompt can apply such an answer, so the trigger is never answerable by
re-dispatching an agent), and the council's **over-scope flag** (`critique.over_scope.flag`).
The flag is a record: it is carried into the `council-verdict` payload and the slice sidecar with
its reason, and it raises no escalation, changes no verdict, suppresses no split, and blocks
nothing. There are exactly five JUDGMENT triggers; an over-scope flag is not a sixth.

### Precedent check (before returning any SURFACE escalation)

Prior runs' human answers are settled decisions — check them before asking a question the human
may have already answered. Search prior runs (excluding this one): answered escalation records
under `docs/spec-loop/*/escalations.md` and the Decisions Summary of any
`docs/spec-loop/*/runbook.md`. v1 run directories are equally valid precedent — match loosely
on the text, never on a pinned format.

- **A prior human answer squarely resolves this decision** (same question in substance, answer
  still applicable to this codebase state) → do not surface. PROCEED + log a `decision` event
  whose `rationale` names the precedent: the run id, the escalation title, and a one-line
  summary of what the human answered. This is what keeps run N's adjudication from becoming run
  N+1's escalation.
- **A prior answer is related but not squarely on point** → still surface, but quote the prior
  answer in the record's `recommended: true` option so the human confirms rather than re-derives.
- **Guard:** precedent only resolves what a human has *already* adjudicated. It never downgrades
  a new material assumption, a safety flag, or a decision whose context has materially changed.
  When in doubt, surface with the precedent as the default.

The controller repeats this check over every open record at the wave boundary.

### Not triggers (autonomous by design)

Three things that look like stopping points but are handled by the loop itself, keeping the bar at
exactly the five triggers above:

- **Slice split.** A slice that turns out to be two-or-more independently shippable changes
  returns `SPLIT`; the controller grafts the children into the DAG (`dag.py ingest-split`) —
  logged, no human contact. Only a proposal that is malformed or already at the depth cap falls
  back to a trigger above (see `references/split-ingestion.md`).
- **Integration remediation.** A merge conflict or red integration check opens a remediation
  slice that runs the normal pipeline; the human is reached only if that slice exhausts its own
  fix budget (trigger 3).
- **Over-scope and deferred scope.** A plan that exceeds the run's scope ceiling is flagged
  (`over_scope`) and, when the goal genuinely asks for it, still built; work the council
  asks not to be built is a `defer`-hinted concern recorded as one `deferred` event per
  concern. Both are records for the human to read at the runbook, not questions — and
  neither ever suppresses a finding.

## Batching rule (critical for non-blocking operation)

**Never interrupt mid-wave, never one question at a time.** Workflow stages cannot prompt the
human, so:

1. The stage returns its `EscalationRecord` (`status: "ESCALATED"`). Only that slice pauses;
   `parallel()` keeps every independent slice running.
2. The controller collects **all** open records at the **wave boundary**
   (`run_state.py open-escalations`), runs the precedent check on each, and surfaces everything that
   survives as ONE `AskUserQuestion` round — recommended default first.
3. Answers are written back (`escalation-answered` events) and the wave is re-dispatched with
   `answers["<slice-id>:<trigger>"]` filled in; completed stages replay from the workflow journal,
   so only the answered stage runs live.

The wave boundary is the only seam where a human is asked anything — unchanged from v1; only the
transport moved from prose files to structured returns.

## The escalation record

Shape and field semantics live in `references/run-state-v2.md` (`EscalationRecord`) and the
`ESCALATION` schema in `slice-wave.workflow.js`. Never hand-write into `escalations.md`; it is
rendered from the records. Two rules the shape cannot enforce:

- **Always include a recommended default.** Make the human's decision as cheap as possible
  (confirm vs. redirect). A record whose options are all equally weighted is unfinished.
- **`context` explains why the loop cannot decide**, not merely what happened — the human reads it
  cold, alongside other questions.

The `id` is `<slice-id>:<trigger>`, stable across resumes: that stability is what lets an answer be
injected back into exactly the stage that raised it.

## Violations of the contract

- Asking the human something resolvable from the codebase, a convention, or a prior run's answered
  escalation (run the precedent check first).
- Proceeding silently on a material assumption — it must be logged *and* surfaced.
- Asking mid-wave or one escalation at a time; hand-writing `decisions-log.md` / `escalations.md`
  instead of emitting events and records.
- Skipping `verification-before-completion` because this gate said proceed; that gate is separate
  and never skipped.
