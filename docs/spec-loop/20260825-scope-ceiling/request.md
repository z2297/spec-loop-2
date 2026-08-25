# Request — scope-expansion containment mechanisms

Run: 20260825-scope-ceiling · repo: spec-loop-2 (the plugin's own source)

## Verbatim request

> Implement mechanisms to minimize scope expansion.
>
> Take these steps to address from the listed points of the conversation.
>
> 1. Build a scope ceiling in the data model.
> 2. Create a council member or add a role to an existing member that adds weight to scope increases
> 3. Add an over-scope flag
> 4. this is intended functionality. Flag is as scope creep, but ensure that the work is done
> 5. Log the deffered scope, but do not re implement

## Restatement (two sentences)

spec-loop 2 has no durable representation of a scope *ceiling* — `dag.json` records only
what a slice must achieve, never what it must not grow into — and its council/review layers
are structurally one-directional: every lane that adds work scales with risk tier and runs at
high effort, while the sole minimality lane is one of five mandates inside one agent and has
no flag with halting or recording power. This run adds a scope ceiling to the run-state data
model that reaches every agent, gives the scope lane explicit weight in the council, and adds
a non-blocking over-scope flag whose firing is recorded as scope creep while the flagged work
still proceeds — with deferred scope logged durably and never re-admitted.

## The five points, as binding requirements

1. **Scope ceiling in the data model.** A durable, machine-readable scope ceiling in
   `dag.json` (run-level and/or per-slice) that survives a resume, is validated by `dag.py`,
   and is threaded into the agent packet so planner, critic, reviewer, and implementer all
   receive the same ceiling. Today the controller's Phase-0.4 in/out-of-scope determination
   reaches no agent.
2. **Weighted scope lane in the council.** The scope/minimality mandate gets explicit weight —
   either a dedicated council member or a promoted role on an existing member — so that
   minimality pressure scales with tier the way risk pressure already does.
3. **Over-scope flag.** A first-class flag on the critique/review contract for "this exceeds
   the ceiling", structurally parallel to `safety.flag` but with different consequences (see 4).
4. **The flag records; it does not veto.** An over-scope flag is NOT a halt, NOT an
   escalation-by-itself, and NOT a reason to drop or shrink the work. The flagged work is
   still implemented and still ships. The flag's entire job is to mark the excess as scope
   creep, durably, where a human can see it. Contrast `safety.flag`, which halts the loop.
5. **Deferred scope is logged, never re-implemented.** Scope identified and deliberately not
   taken on gets one durable record (event → sidecar → runbook). Once deferred it must not be
   silently re-admitted later in the same run — notably it must not re-enter as a review
   finding and become mandatory work. "Do not re-implement" means: do not build it in this run.

## In scope

- `dag.json` schema + `references/run-state-v2.md` (the single home) + `scripts/dag.py`
  validation and its tests.
- Threading the ceiling through the wave packet in `workflows/slice-wave.workflow.js`.
- Council contract: the CRITIQUE schema, the over-scope flag, and the workflow's handling of
  it; the agent(s) that own the scope lane.
- Deferred-scope recording: events, the per-slice sidecar, `run_state.py` persistence, and
  the runbook section that surfaces it.
- Suppressing re-admission of deferred scope into the fix loop.
- Docs kept truthful in the same change (single-home rule) and CHANGELOG.

## Out of scope (do not build)

- Changing risk-tier assignment heuristics or the tier→review-shape table itself.
- Changing quality-gate thresholds, metrics, or the gate's blocking semantics.
- Adding or removing any of escalation-gate's five triggers.
- Dashboard UI/UX work beyond rendering fields that already have to exist.
- v1 migration paths, knowledge-graph schema changes, peer-review/review-pr commands.
- Any rewrite of the wave pipeline's stage order or loop bounds.
