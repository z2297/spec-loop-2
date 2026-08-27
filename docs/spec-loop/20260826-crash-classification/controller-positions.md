# Controller positions on the four design questions

Formed independently before the plan-critic/guardian lanes reported, so the run is not
blocked on them. Where a lane disagrees, its reasoning wins on its own mandate and this
file records the change.

## Q1 — ONE new trigger, not two

Cases 2 (caught exception, `:856`) and 3 (slice returned nothing, `:878`) are both "the
loop's own machinery failed". Reasons for one value:

- The human action is the same class either way: retry this slice / skip it / stop the run.
- The distinction already lives where it belongs — the `title` and `context` fields. Today
  `:856` says `wave interrupted` and `:878` says `slice lost`; both titles survive unchanged
  under a shared trigger.
- Every added enum value multiplies across FOUR hardcoded lists (JS enum + three Python
  tuples), six doc sites, and the test modules. Two values double that cost for information
  the title already carries.
- No id collision risk: `esc()` `:255` builds `id` as `${slice.id}:${trigger}`, and cases 2
  and 3 are mutually exclusive within one slice run — case 3 means the slice never returned
  at all, so it cannot also have thrown into `runSliceError`.
- Metrics can still separate them: `by_trigger` gives the combined bucket, and the title
  distinguishes within it if anyone needs the split later.

Counter-argument acknowledged: case 2 carries an exception string and partial state
(`tasks_completed`, `commits.head`), case 3 carries nothing at all. If the guardian or
plan-critic argues those need separate metric buckets to drive loop reliability work, two
values is defensible. Not my default.

## Q2 — `internal-error`

Substring-safe against every existing value (`ambiguity`, `material-assumption`,
`review-block`, `council-objection`, `quality-gate-block`, `budget-exhausted`) in BOTH
directions, which `run_metrics.py:1692` requires.

Chosen over the alternatives:
- `workflow-fault` — precise but jargon; also invites confusion with the *workflow tool*.
- `unclassified-failure` — accurate but self-defeating as the name of a classification, and
  long in a rendered `escalations.md` heading.
- `slice-lost` — only describes case 3, so it forces Q1 to two values.
- `machine-failure` — fine, but less conventional than `internal-error`.

"Internal" correctly signals *internal to the loop machinery*, distinguishing it from the
slice's own code failing (which surfaces as `review-block` or a red suite), and from a
resource limit (`budget-exhausted`). Reads correctly as a heading: `## [s2] internal-error`.

## Q3 — stage attribution is LOAD-BEARING, keep it in the core slice

Not separable. The controller's corrected measurement shows the cost of mislabelling is
misdirected DIAGNOSIS, not human idle (~1 min human latency on both crash escalations; the
85/76-min windows were the controller working out that a "budget" escalation was a
`TypeError`). Attribution is exactly the thing that shortens that window. A rename with a
bare exception string in `context` fixes the honesty complaint and leaves the expensive
problem in place.

Cheap to do: `dispatch()` `:430` already receives a `role` string and already pushes it into
an `agent-dispatch` event. Recording the last dispatched role (and/or a stage label set at
each `runStages` boundary, `:833-853`) on `state` gives the catch-all something real to
report, with no new agent traffic and no new schema field on the sidecar.

## Q4 — NO, the run is not half-done

Narrowing `budget-exhausted` to its designed meaning and giving machine failures an honest,
diagnostic record is a complete and coherent deliverable. That a `budget-exhausted` answer
has no mechanical effect (the human says "raise the cap" and nothing raises it) is a
PRE-EXISTING gap, unchanged by this run, and is a capability addition rather than a
classification fix — it needs a controller-side path to thread a raised cap into a
re-dispatch, which touches `commands/spec-loop.md` and the wave args contract.

Record it as an explicit deferral with the reason, so it is deferred rather than hidden.

## Decomposition — keep the coarse 2 slices

The atomicity constraint (shared constraint 3) binds the JS enum to `run_state.py:67`, so
the natural "JS slice / Python slice" cut is unavailable. The remaining candidate cut is
classification (enum + tuples + `runSliceError` + `:878` + tests) vs. stage attribution —
but both edit the same function's inputs in the same file, so splitting them buys a second
wave and a merge-order dependency for no isolation benefit.

Wave count is a direct wall-clock multiplier (the previous run: 4 slices, 4 waves, 9h28m,
strictly serial). Staying at two slices is the right call. `slice-planner` owns the
right-size gate and may still return SPLIT with a better cut than either of us sees; that is
autonomous and needs no human round.
