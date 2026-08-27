# Request — 20260826-crash-classification

## Verbatim user request

> Assertion: budget-exhausted is maksing crashes and making runs long. Fix the
> budget-exhausted as a designed resource signal, and the de facto label for every
> unclassified crash.

Invoked as `/spec-loop:spec-loop` with no flags (defaults: `--max-parallel 5`,
`--risk-floor 1`).

## The assertion, verified against artifacts before intake

The user's assertion is CORRECT and was established from run `20260825-scope-ceiling`'s
own artifacts in the session that preceded this run. Evidence:

- `plugins/spec-loop/workflows/slice-wave.workflow.js:856` — `runSliceError()`:
  ```js
  function runSliceError(slice, state, e) {
    if (e && e.escRecord) return escalated(slice, state, e.escRecord)
    return escalated(slice, state, esc(slice, 'budget-exhausted', 'wave interrupted',
      String((e && e.message) || e),
      'The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?', []))
  }
  ```
  `runSlice()` wraps every stage in ONE try/catch. Any throw that does not carry an
  `escRecord` — i.e. every unexpected JS exception — is relabelled `budget-exhausted`
  with the raw exception message stuffed into the `context` field and a resource-shaped
  question the human cannot usefully answer.

- The SAME trigger is the designed signal for three genuine structural limits:
  - `:425` agent cap reached (`CAPS = { 1: 10, 2: 18, 3: 32 }`, line 31)
  - `:427` token stage floor (`BUDGET_STAGE_FLOOR = 60_000`, line 33)
  - `:878` lost slice (slice function returned no result)

- `skills/escalation-gate/SKILL.md:73-75` documents the intended meaning explicitly:
  `budget-exhausted` is "deliberately NOT a judgment trigger ... the workflow's guard
  emits it when a structural cap is hit — agent cap, stage token floor, lost slice; it
  asks for a resource, not a decision." The catch-all violates this contract.

- Measured cost in run `20260825-scope-ceiling` (from its `events.jsonl`, 144 events):
  - Four `budget-exhausted` escalations, NONE of them a real resource limit.
  - Two carried `Context: undefined is not an object (evaluating 'r.commits.head')` — a
    `TypeError`. Two carried `Context: agent({schema}): StructuredOutput retry cap (5)
    exceeded`. All four rendered the resource prompt "The wave hit a hard limit. Raise
    budget/caps and resume..." with a single recommended option that restated the crash.
  - **CORRECTED MEASUREMENT (controller, 2026-08-26).** An earlier draft of this request
    said these two escalations cost 85 and 76 minutes of HUMAN idle time. That was wrong,
    and the error came from the known duplicate-escalation-render bug: each id carries TWO
    `escalation-answered` events, and the first script read the LAST one. Measured from
    first-open to FIRST answer, the human answered the s2 crash in **1.1 min** and the s3
    crash in **0.6 min**. True human answer latency across the ENTIRE run was ~35-39 min
    total (intake 21.5 concurrent, s1 quality gate 16.2, the two crashes 1.7 combined) —
    about **6% of the 568-minute active span**, not 35%.
  - So the masking did NOT cost human idle time. What it cost was **controller diagnosis
    and recovery time**: the 85-min (s2) and 76-min (s3) gaps between the crash and the
    wave resuming were spent working out that a "budget/cap" escalation was really an
    unguarded-read `TypeError`, patching the persisted script copy, and resuming from the
    journal. That misdirection is caused directly by the label — the KG pattern
    `an-optional-schema-field-read-unguarded-aborts-the-whole-pipeline` states it exactly:
    the catch-all "reports the resulting TypeError as whatever it is written to assume (a
    budget or resource limit), sending the diagnosis in exactly the wrong direction."
  - `runbook.md:281` separately records ~57 min and 701k tokens spent re-hitting one
    already-patched crash. That one is a controller dispatch-discipline failure (dispatching
    by workflow name discards a patch to a prior wave's script copy), NOT caused by the
    label.

  **Consequence for scope.** The mechanism by which mislabelling lengthens a run is
  controller misdiagnosis, not human confusion. The lever that matters is therefore making
  the crash record DIAGNOSTIC — naming the stage/role in flight and the real exception —
  not merely renaming the trigger. Scope item 3 (stage attribution) is thus load-bearing,
  not a nice-to-have.

## Scope — IN

1. Separate the two meanings. `budget-exhausted` retains ONLY its designed resource
   meaning (agent cap, token stage floor, lost slice). Unclassified internal failures get
   their own classification, with honest title/context/question/options.
2. Carry the new classification through every consumer that reads the trigger, so no
   downstream layer silently drops or mis-buckets it: the `ESCALATION.trigger` enum in
   `slice-wave.workflow.js`, `run_state.py`, `run_metrics.py` (`by_trigger` buckets),
   `dashboard_server.py` + dashboard assets, `references/run-state-v2.md`,
   `skills/escalation-gate/SKILL.md`, `agents/slice-worker-fallback.md` (the inline-mode
   twin must classify identically), `references/risk-tiers.md`, `references/migration-from-v1.md`.
3. Where a crash is thrown by a stage the workflow can attribute, say WHICH stage and
   WHAT the exception was, rather than a bare message string. The human's real question on
   a crash is "retry, skip this slice, or stop the run?" — not "raise the budget?".
4. Tests. `test_slice_wave_contract.py` already asserts against this file's source text;
   contract tests must pin the new classification and must pin that the catch-all no
   longer emits `budget-exhausted`.
5. Backward compatibility for the ONE existing run on disk
   (`docs/spec-loop/20260825-scope-ceiling`): its `events.jsonl` and sidecars contain
   `budget-exhausted` entries that must keep parsing and rendering after the change.

6. **Answerability of the new trigger — decide it deliberately, and pin it with a test.**
   CORRECTED at intake by the controller after reading the tests (an earlier draft of this
   request had this backwards). The codebase already encodes, WITH A TEST, that
   `budget-exhausted` is deliberately not prompt-injectable —
   `plugins/spec-loop/scripts/test_slice_wave_contract.py:131`:

   ```python
   def test_budget_exhausted_is_still_not_injected_anywhere(self):
       # It asks for a resource, not a decision (escalation-gate SKILL.md):
       # there is nothing for a prompt to apply.
       self.assertNotIn("answerFor(slice, 'budget-exhausted')", self.src)
   ```

   `ANSWERABLE_TRIGGERS` (`slice_wave_contract_base.py:79-81`) is exactly the five
   judgment triggers, and `test_every_human_answerable_trigger_has_at_least_one_injection_site`
   (`:111`) pins that each of those five has an `answerFor` site. So the KG pattern
   `an-escalation-trigger-with-no-answer-injection-path-cannot-be-resolved-by-re-dis`
   described `quality-gate-block` (since fixed via `answerContext`), NOT
   `budget-exhausted`, whose missing path is intentional.

   For the new crash classification the answer is "retry this slice / skip it / stop the
   run" — a CONTROLLER action, applied by re-dispatching or not. There is nothing for an
   agent prompt to apply, so the new trigger belongs in the NON-answerable set alongside
   `budget-exhausted`, and the run must add a mirror of the `:131` test pinning that it has
   no `answerFor` site. Getting this backwards — wiring `answerFor` for a crash — would
   instruct an agent to "apply" a retry decision it cannot act on.

   Whether `budget-exhausted` should GAIN a controller-side answer path (so "raise the cap
   and resume" actually raises the cap) is a real question but is OUT of scope below.

## Scope — OUT (run-level scope ceiling)

- Do NOT fix the underlying crash causes. `r.commits.head` was fixed in 2.2.0 and is in
  the installed cache; the StructuredOutput retry cap is an agent-layer limit outside this
  repo. This run changes CLASSIFICATION and REPORTING, not crash-proofing.
- Do NOT retune `CAPS` or `BUDGET_STAGE_FLOOR` values.
- Do NOT redesign the escalation system, the five-trigger judgment test, or the
  escalation-gate decision procedure beyond adding the new classification to it.
- Do NOT fix the known duplicate-section bug in rendered `escalations.md`
  (deferred by the previous run, recorded in its runbook Gaps section) — related, but a
  separate defect with its own deferral record.
- Do NOT add automatic retry of a crashed stage. Retry POLICY is a design change; this run
  delivers honest classification and the right question. (If the council argues retry is
  inseparable from the fix, that is an intake escalation, not a silent expansion.)
- Do NOT change how the controller (`commands/spec-loop.md`) batches escalation rounds.
- Do NOT add a controller-side answer path that lets a `budget-exhausted` answer actually
  raise `CAPS` or the budget for a re-dispatch. It is a genuine gap (today the answer
  changes nothing mechanical) but it is a capability addition, not a classification fix.
  Record it as a deferral for a future run.

## Success criteria

- A crash inside a slice stage produces an escalation whose trigger is NOT
  `budget-exhausted`, whose context names the failing stage and the exception, and whose
  options are retry/skip/stop rather than raise-the-budget.
- A genuine agent-cap or token-floor hit still produces `budget-exhausted` with its
  existing wording, unchanged.
- Every consumer listed in scope item 2 handles the new trigger; `run_metrics.py` buckets
  it separately in `escalations.by_trigger`.
- The new trigger is pinned as NON-answerable by a mirror of
  `test_slice_wave_contract.py:131`, and `ANSWERABLE_TRIGGERS` is unchanged.
- The full suite is green, and the previous run's artifacts still parse and render.

## Known constraint carried in from the previous run

This run edits `slice-wave.workflow.js` — the machinery that executes its own waves.
`plugin_root` is therefore pinned to the installed 2.2.0 cache (byte-identical to the
pre-run repo, verified by `diff -rq`), NOT to this repo, so the loop is not
self-modifying across wave boundaries. Consequence: nothing this run ships in
`slice-wave.workflow.js` will be executed by this run. Same verifiability ceiling the
previous run recorded.
