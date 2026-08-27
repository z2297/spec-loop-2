# Shared constraints (draft) — binding on every slice

Settled at intake before the plan-critic/guardian lanes reported. Numbered for citation.

1. `plugin_root` is the frozen installed cache
   `/Users/zachmcmurry/.claude/plugins/cache/spec-loop/spec-loop/2.2.0/`, byte-identical to
   the pre-run repo. NOTHING this run ships in `slice-wave.workflow.js` executes during this
   run. Do not claim behavioural verification of the JS.
2. Never remove `budget-exhausted` from any enum or tuple. Its MEANING narrows; the string
   stays, so the completed run `20260825-scope-ceiling` keeps validating and rendering.
3. The JS schema enum (`slice-wave.workflow.js:40`) and `run_state.py:67` must land in the
   SAME slice. `run_state.py:204` is fail-closed; a sidecar with an unlisted trigger is
   rejected and its slice becomes ESCALATED.
4. The new trigger name must not contain, nor be contained by, any existing trigger name.
   `run_metrics.py:1692` substring-matches. Disqualifies e.g. `budget-exhausted-crash`.
5. The new trigger is NOT prompt-answerable. Do not add it to `ANSWERABLE_TRIGGERS`
   (`slice_wave_contract_base.py:79-81`); do not give it an `answerFor` site. ADD a mirror
   of `test_slice_wave_contract.py:131` pinning that it has none. A crash answer is a
   controller action (retry / skip / stop), and there is nothing an agent prompt can apply.
6. Do not claim this run shortens runs. It delivers honest, actionable, correctly-bucketed
   escalations. Wall-clock improvement is an unproven hypothesis for the NEXT run.
   [skeptic, accepted]
7. Every success criterion must be reported with HOW it was verified: real test execution,
   or source-text pattern match only. [skeptic, accepted]
8. The true human answer latency on the previous run was ~35-39 min total (~6% of 568 min);
   the two crash escalations were answered in 1.1 and 0.6 min. The 85/76-minute windows were
   CONTROLLER DIAGNOSIS, not human idle. Any reasoning that cites 161 minutes of human idle
   is working from a corrected-away figure. [controller measurement]
9. Automatic retry of a crashed stage is OUT of scope. The skeptic lane considered and
   explicitly declined to escalate for it.
10. A crash's blast radius is exactly one slice: `runSlice()` `:859-866` catches and returns
    an ESCALATED result rather than rethrowing, so `parallel()` `:871` and every sibling
    slice are unaffected. Do not "fix" sibling isolation; it already holds.
11. Contract-test modules were split purely to keep each module's whole-file `class_lines`
    under 300 (`test_slice_wave_contract.py:8-11`). Put new contract tests where they keep
    both modules under the threshold; use named snippet constants in
    `slice_wave_contract_base.py`, never inline literals.
12. `agents/slice-worker-fallback.md` is the behavioural spec for the inline-mode twin, not
    prose. If it keeps the old classification, inline runs keep the defect.
13. Sweep `slice-wave.workflow.js:637-646` — its comment asserts the catch-all relabels to
    `budget-exhausted`, which this change makes false.
