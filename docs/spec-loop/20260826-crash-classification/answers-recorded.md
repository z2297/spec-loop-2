# Human answers — recorded 2026-08-26, intake question round

These are settled decisions. A future session picking this up MUST NOT re-ask them.

## A1 — Execution: STOP, fix the harness first

Chosen over (i) inline implementation without waves and (ii) trying one wave and aborting.

Rationale as presented: subagent delivery failed for 5 of 6 dispatches in the launching
session — both `Explore` agents, `plan-critic`, `guardian`, and a trivial control agent whose
entire prompt was "reply with exactly SMOKE-OK, do not use any tools". Only `skeptic`
delivered. Every spec-loop wave depends on subagents returning structured results, so an
autonomous run in that state would be unreliable and would surface its failures as exactly
the mislabelled crashes this run exists to fix.

**No code was changed. No branch was created.** The repo is untouched at `main` @ `8d0e2c1`.

## A2 — Trigger shape: ONE new value, named `internal-error`

Covers both machine-failure cases — the caught exception at `slice-wave.workflow.js:856` and
the slice-returned-nothing case at `:878`. Rationale accepted as presented:

- The existing titles (`wave interrupted`, `slice lost`) already carry the distinction.
- The two cases are mutually exclusive within one slice run, so the shared
  `id` = `${slice.id}:${trigger}` (`esc()` `:255`) cannot collide.
- Each added enum value multiplies across four hardcoded lists, six doc sites and the tests.
- `internal-error` is substring-safe in BOTH directions against all six existing values,
  which `run_metrics.py:1692` requires.

Rejected: two values (`internal-error` + `slice-lost`) — roughly double the surface for
information the title already carries. Rejected: `workflow-fault` — jargon, and invites
confusion with the Workflow tool.

## A3 — Scope: classification + stage attribution, as originally scoped

Auto-retry stays OUT and is recorded as a deferral. The `skeptic` lane independently reached
the same conclusion and explicitly declined to escalate for retry, calling classification "a
real, independently justified fix (honesty, correct metrics bucketing, `escalation-gate`
contract integrity) even if it turns out to save 10 minutes rather than 160."

Stage attribution is IN and is load-bearing, on the corrected measurement: the cost of
mislabelling is misdirected controller diagnosis, not human idle time.

Accepted with the framing correction: **this run must not be sold as shortening runs.** It
delivers honest, actionable, correctly-bucketed escalations and fast diagnosis. Wall-clock
improvement is an unproven hypothesis to be checked against the next run's artifacts.
