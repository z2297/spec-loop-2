# Request

## Verbatim

In the last run in the jobs repository the loop correctly identified increased scope for a
refactor that changes ~5k lines for a 30 line real diff. Create an escalation point when
existing code will need to be heavily refactored so that the human can weigh the trade offs.
This loop should work in a rapid iterating team with minimal disruption to others working in
the same repository.

## Controller restatement

Add a new, genuinely blocking escalation trigger to spec-loop 2 that fires when a slice's
plan implies heavy refactoring of PRE-EXISTING code — large churn against lines that already
exist, disproportionate to the net behavioral change being delivered — so the human weighs
the trade-off BEFORE the loop spends the work. Because the target users are a fast-iterating
team sharing one repository, the signal must account for disruption to teammates (blast
radius across shared/hot files, merge-conflict surface), not raw line count alone.

## In scope

- A refactor-blast-radius signal computed from the slice PLAN (pre-execution), so the human is
  asked before the effort is spent.
- Thresholds carried in the existing quality-gate config file (the established config home),
  with a repo-level overlay so a team can tune them per repository.
- A new escalation kind emitted through the existing escalation record channel, WITH a working
  answer-injection path so a re-dispatched wave actually changes behavior.
- Controller / workflow / agent-packet plumbing and the docs + CHANGELOG updates.

## Out of scope

- Changing the semantics of the existing run-level `scope_ceiling` or the record-only
  `critique.over_scope` marker. Those govern NEW scope; this governs churn on EXISTING code.
  The new mechanism must sit alongside them, not redefine them.
- Any git-hosting or CI integration (no PR-size bots, no server-side hooks).
- Post-hoc measurement of an already-implemented diff as the ONLY trigger — the point is to ask
  before the work is done. (A post-implementation confirmation may complement it, not replace it.)

## Constraints carried from prior runs (knowledge graph)

- An escalation trigger the orchestrator never reads back is unanswerable by re-dispatch:
  the new kind MUST have an answer-injection path into the agent packet, or it is structurally
  broken. (pattern: an-escalation-trigger-with-no-answer-injection-path-cannot-be-resolved-by-re-dis)
- Recording a judgement is not acting on it. The request asks for an escalation POINT — a real
  halt-and-ask — not another record-only flag like `over_scope`. Build the lever, and say plainly
  which parts are lever and which are record.
  (pattern: recording-a-judgement-is-not-acting-on-it-say-which-you-built)
- A narrowing predicate added to bound blast radius becomes a permanent silent exclusion unless
  it is observable. Any threshold/filter must be reported, never silently applied.
  (pattern: a-type-filter-added-as-a-scope-note-becomes-a-permanent-silent-exclusion)
- Optional schema fields must be read guarded; slice-wave.workflow.js has a live history of
  unguarded optional reads aborting the pipeline.
  (pattern: an-optional-schema-field-read-unguarded-aborts-the-whole-pipeline)

## Human decisions at intake (2026-08-28)

The intake council returned a UNANIMOUS OBJECT (plan-critic, guardian, skeptic; no safety
flag). All four questions below were put to the human in one batched round.

1. **What failed in the jobs run: "It asked, but too late."** The escalation arrived after the
   work was already done, so the trade-off could not be weighed in advance. The defect is
   TIMING, not detection. This is the decisive constraint on the design: the checkpoint must
   sit at PLAN time, before implementation effort is spent.
2. **Scope: ratio trigger + fix the replan leak.** Build the `refactor-scope` trigger fired on
   the planner's declared ratio of existing-lines-rewritten to net-behavior-lines, judged
   deterministically in JS; AND close the silent-replan leak found at
   `slice-wave.workflow.js:643-652`. NO git blast-radius mining this run.
3. **"Minimal disruption" means BOTH, in that order.** "Do not interrupt the operator often" is
   the HARD constraint and governs threshold choice. Teammate blast radius is a secondary
   input, DEFERRED to a later run (see scope_ceiling).
4. **Defaults: DEFAULT ON with conservative thresholds.** This deliberately overrides
   guardian's opt-in recommendation. The human accepted the stated consequence: every existing
   installation gains this halt on its next run after upgrade. Two things become load-bearing
   rather than optional as a result:
   - the explicit null/type guard BEFORE any threshold comparison, so no halt is ever decided
     by JavaScript coercion (`undefined >= n` is false, `null >= 0` is true);
   - the overlay merge fix, because teams will now actually tune these numbers and
     `quality_gate.py:230` currently replaces a non-special config block wholesale.

### Council findings carried into the build (verified by the controller, not taken on trust)

- `resolveCouncilObjection` (`slice-wave.workflow.js:643-652`) accepts a replan on
  `revised.status === 'PLANNED'` alone — no re-critique, no re-measurement, no human contact.
  A `fixable_by_replan: true` objection is silently absorbed. VERIFIED by reading the source.
- `planPrompt` (`:357`) injects `answerFor(slice,'ambiguity')` and
  `answerFor(slice,'material-assumption')`; `latestAnswer` returns only the NEWEST answered
  round per slice+trigger. Riding a refactor question on `material-assumption` would let a
  later refactor answer shadow an earlier material-assumption answer out of the prompt. This
  is the real correctness justification for a distinct enum value — not doctrine tidiness.
- `quality_gate.py:230` `merged.update(overlay)` replaces any non-special key wholesale;
  only `thresholds`, `custom_gates` and `tier3_surfaces` merge key-wise. VERIFIED by reading.
- Agent docs say `fixableByReplan` (camelCase) while the enforced schema key is
  `fixable_by_replan`; `additionalProperties: false` means the tool layer forces snake_case.
  Pre-existing prose drift in `plan-critic.md:65`, `guardian.md:70`, `skeptic.md:73`,
  `slice-worker-fallback.md:76`.
- Guardian CLEARED, so do not build: enum backward-compat migration (old sidecars keep old
  triggers; nothing re-validates persisted sidecars), forward-compat handling
  (`_normalize_trigger` -> "other", `_enum_or_none` -> None), version-skew handling (JS and
  Python resolve from the same `${CLAUDE_PLUGIN_ROOT}`), and answer-key family collision
  (`refactor-scope` is neither a prefix of nor prefixed by any existing trigger).
