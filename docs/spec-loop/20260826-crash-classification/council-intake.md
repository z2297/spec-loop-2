# Intake council — 20260826-crash-classification

Panel: `plan-critic` (all five mandates), `guardian` (risk lane), `skeptic` (premise lane).
Dispatched 2026-08-26T19:26Z in one message. Note: all three read `request.md` as it stood
at dispatch, i.e. BEFORE the controller's corrected human-latency measurement landed. Where
a verdict reasons from the stale 161-minute figure, the controller's adjudication says so.

---

## skeptic — premise lane — ENDORSE_WITH_CONCERNS (no safety flag)

**Bottom line (verbatim):** "The premise 'budget-exhausted is masking crashes' is factually
verified and worth fixing. But the premise 'fixing the label will make runs shorter' is NOT
established by the cited evidence and the scope explicitly excludes the two mechanisms that
would actually shorten wall clock. This is not a block — it's a framing/success-criteria
correction."

### Its #1 — two rival causal stories, and how the controller settled it

The skeptic said the 161 min was consistent with either (a) the human being confused by a
nonsensical "raise budget/caps?" question, or (b) the human simply being unavailable — and
that no artifact distinguished them.

**CONTROLLER RESOLUTION: neither.** Measured first-open to FIRST answer,
`s2:budget-exhausted` = **1.1 min**, `s3:budget-exhausted` = **0.6 min**. The human answered
both crash escalations in about a minute. The 85/76-minute figures came from reading the
SECOND `escalation-answered` event per id (the duplicate-render bug). The 85/76-min windows
were real elapsed time but were **controller diagnosis and recovery** — realising a
"budget/cap" escalation was an unguarded-read `TypeError`, patching the persisted script
copy, resuming from the journal.

This *strengthens* the skeptic's conclusion while removing its uncertainty: the mislabelling
costs almost no human idle time at all. It costs misdirected diagnosis. Its recommendation
to stop claiming "shorter runs" is ACCEPTED, and its rival hypothesis (b) is refuted.

### Its #3 — does a crash stall sibling slices? — CONTROLLER SETTLED FROM CODE

The skeptic flagged this as a question it could not answer without the dispatch code.
Answer: **no — blast radius is exactly one slice.** `runSlice()` `:859-866` catches and
RETURNS an ESCALATED result rather than rethrowing, so the `parallel()` at `:871` is
unaffected and every sibling slice runs to completion. Matches `esc()`'s
`if_unanswered: 'pause this slice; continue all independent slices'` (`:260`). Caveat, not a
defect: the wave does not RETURN until its slowest slice finishes, and the human round comes
at the wave boundary — that is the controller's batching design, not crash-specific.

### Accepted, folded into the run as shared constraints

1. **Do not claim this run shortens runs.** Claim honest, actionable, correctly-bucketed
   escalations. Wall-clock improvement is an UNPROVEN HYPOTHESIS to be checked against the
   NEXT run's artifacts.
2. **Every success criterion must be marked with how it was verified** — (a) real test
   execution, or (b) source-text pattern match only. The JS side cannot be behaviourally
   verified this run (frozen-cache self-mod guard); the Python side genuinely executes under
   `unittest discover`, so its criteria ARE verifiable now. The runbook must not let
   "criteria met" read as "we watched a crash get classified correctly."

### Judged and NOT escalated

- The skeptic explicitly DECLINED to pull automatic retry into scope, calling classification
  "a real, independently justified fix (honesty, correct metrics bucketing, `escalation-gate`
  contract integrity) even if it turns out to save 10 minutes rather than 160." The request's
  own escape valve ("if the council argues retry is inseparable, that is an intake
  escalation") was therefore NOT triggered by this lane. Retry stays OUT.
- Enum-vs-structured-field: skeptic judged the enum approach "the right call for the right
  reason, not chosen by default," matching the triplicated tuples, fail-closed validation and
  JSON-schema enum already in place. No change.
- Its note that "as scoped, a crash always escalates the human" is recorded as a named
  design choice, not a gap.

---

## plan-critic — NO VERDICT DELIVERED (lane lost)

Dispatched 19:26Z. Went idle at 19:35:32Z with no output. Re-prompted explicitly for
text-only delivery; went idle again at 19:37:29Z with no output. Stopped at 19:38Z.

**This lane's mandates (premise, design, scope, risk, codebase consistency) were NOT
independently exercised.** The controller substituted its own first-hand analysis, recorded
in `controller-positions.md` with file:line evidence, and its own risk lane below. That is a
weaker guarantee than an independent critic and is recorded as a run limitation, not papered
over. Do not describe this run as having had a full intake council.

## guardian — NO VERDICT DELIVERED (lane lost); risk assessment performed by the controller

Dispatched 19:26Z, idle 19:35:55Z with no output, re-prompted, idle again, stopped 19:40Z.
The risk mandate below was executed by the controller directly, with commands run and output
read. Findings:

### R1 — Public contract: the breaking direction is FORWARD, not backward

Adding a value is safe for backward compatibility (new reader, old artifacts): verified by
the executable baseline above — the historical run still validates, reports no open
escalations, and buckets `budget-exhausted` as itself.

The hazard is the OTHER direction. `run_state.py:204` fails CLOSED, so **a sidecar carrying
the new trigger cannot be persisted by an older install of the plugin.** Concretely: a repo
updated to emit `internal-error`, paired with an installed cache still at 2.2.0, produces a
sidecar that `persist-slice` REJECTS, and the slice is then treated as ESCALATED — a good
slice's work reported as a failure. This is a genuine version-skew hazard and it is exactly
the failure class this run exists to stop mislabelling.

Mitigation required: the CHANGELOG entry must state that the new trigger requires the
installed plugin and the repo to be updated together. `schema_version` stays 2 — the change
is additive to an enum, not a shape change (`references/run-state-v2.md:18,72`).

### R2 — Fail-closed blast radius: NOT reachable during this run

Verified: the workflow script never touches `run_state.py` — it has no filesystem by design
(`slice-wave.workflow.js:22`). The controller persists, using the CACHE copy
(`.../2.2.0/scripts/run_state.py`), and every in-wave command the workflow builds resolves
through `CTX.plugin_root`, also the cache (`:346`, `:366`, `:404`).

So during this run, workflow + validator + gate are all the same frozen 2.2.0 snapshot and
cannot disagree. The three sub-cases asked about:

- **(a) partial merge** — an intermediate commit on the integration branch where the JS enum
  has the new value but `run_state.py:67` does not would be internally inconsistent for
  anyone checking out that commit (bisect, or a release cut there). It would NOT break this
  run. Keeping them atomic (shared constraint 3) is justified on bisectability and
  release-safety, NOT on intra-run safety. The earlier framing overstated this; corrected.
- **(b) resumed wave replaying a cached stage** — safe. The journal replays results from the
  frozen cache's script; no repo code participates.
- **(c) inline-mode run against an un-updated `slice-worker-fallback.md`** — real but
  out-of-run: inline mode is only entered when the Workflow tool is unavailable, and it would
  run the cache's agent definition. Still a reason the doc must be updated in this run
  (shared constraint 12).

### R3 — Irreversibility: nothing, this run

`events.jsonl` is append-only, but this run's waves execute the frozen cache, which can only
emit the SIX existing triggers. This run's own artifacts therefore cannot contain the new
value. Nothing about the new trigger becomes irreversible until the next run dispatches from
an updated cache. Low risk; the first real exercise is deferred, which is also the ceiling.

### R4 — Self-modification: mitigation sufficient, with one named path

`diff -rq` confirms the cache is byte-identical to the pre-run repo. Paths by which the repo
copy could still influence a wave:

- Dispatching by `scriptPath` pointed at the repo instead of by workflow name / cache path —
  controller discipline, and the documented fallback path must use the CACHE path.
- Slice worktrees contain the MODIFIED repo code, and slices run the test suite there. So the
  modified Python IS really executed — by `unittest`, in a worktree. This is intended and is
  the only genuine behavioural verification this run gets (it satisfies the skeptic's #5 for
  the Python side). It does not feed back into orchestration.

No other path found.

### R5 — Coverage: the paths that MUST be tested, beyond floor compliance

1. `run_state.py` validation ACCEPTS the new trigger and still REJECTS a bogus one — both
   directions, or the fail-closed guarantee is untested.
2. `run_metrics.py` buckets the new trigger under its own key in
   `safety.escalations.by_trigger`, and does NOT fall through to `"other"`
   (`_normalize_trigger` `:450`).
3. `dashboard_server.py:1047` parses the new trigger out of an escalation id
   `<slice>:<trigger>[:<round>]`, and `:1017` `_enum_or_none` returns it rather than `None`.
4. Contract tests: `runSliceError` no longer emits `budget-exhausted`; the new trigger has no
   `answerFor` site; `budget-exhausted` retains its wording at `:425`/`:427`.

`run_state.py` is at 100% against a 95% floor, so item 1 is also a floor necessity.

### R6 — Historical run: verified safe, with an executable check

See the three-command baseline in `conventions.md`. Pre-change output captured. What would
break it: removing `budget-exhausted` from any tuple (then `_normalize_trigger` demotes those
two records to `"other"` and `by_trigger` changes), or renaming it.

### Verdict (controller, risk lane)

ENDORSE_WITH_CONCERNS. `safety.flag = false`. No irreversibility, no data loss, no security
exposure. One real concern (R1 forward-compat / version skew) requiring a CHANGELOG
mitigation, and one correction to the run's own earlier framing (R2: atomicity is a
release-safety requirement, not an intra-run safety requirement).
