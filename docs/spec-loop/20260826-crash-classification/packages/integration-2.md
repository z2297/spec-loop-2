# Review package: 8d0e2c1..HEAD  (context: -U5)

## Commits
c5fe56e merge(r1): phase-5 remediation - inline twin classifies identically, crash record survives truncation, five overclaims pinned
3b0bbf8 fix: lost-slice record claims only what a null result proves
234997d fix(phase5): make the crash record survive truncation and stop overclaiming
8558a95 merge(s2): changelog with the downgrade data-loss warning, corrected loop-bound classification, and the third overclaim removed
c190781 fix: budget-exhausted means the agent cap or the stage token floor, nothing else
70f35c1 docs: correct stale budget-exhausted catch-all claim in test_slice_wave_contract_scope.py
53bc482 docs(changelog): internal-error trigger, narrowed budget-exhausted, downgrade data-loss warning
f9f2bd8 merge(s1): internal-error classification for machine failures, narrowing budget-exhausted to a resource signal
6ac5fe7 fix: correct stale importer count and internal-error cause claim in docs
25d17f9 fix: crash record claims only what the loop can prove
2ccfc9d fix(wave): lead the crash context with the real error, not boilerplate
9e8ffe9 test(dashboard): pin that a record-carried internal-error survives _enum_or_none
50fdc32 style(tests): reindent the internal-error bucketing test to clear nesting_depth
d3d0948 style(tests): reindent the crash id-parse test to the 4-space hanging indent
a4d11cd fix(wave): claim only the last dispatched stage, not a stage in flight
99c45aa docs: internal-error in the run-state contract, escalation gate, and inline twin
d23275e Sweep every comment and docstring asserting the old catch-all behaviour
4818011 fix(wave): a lost slice reports internal-error, not budget-exhausted
fd6c0da fix(wave): classify unhandled slice exceptions as internal-error with stage attribution
860f3f9 feat(wave): record the dispatched stage/role on slice state
30a05bb feat(escalations): add internal-error to the trigger enum and all three tuples

## Files changed
 CHANGELOG.md                                       |  71 ++++++
 plugins/spec-loop/agents/slice-worker-fallback.md  |  36 ++-
 plugins/spec-loop/references/risk-tiers.md         |   4 +-
 plugins/spec-loop/references/run-state-v2.md       |  11 +-
 plugins/spec-loop/scripts/dashboard_server.py      |   2 +-
 plugins/spec-loop/scripts/run_metrics.py           |   1 +
 plugins/spec-loop/scripts/run_state.py             |   3 +-
 .../spec-loop/scripts/slice_wave_contract_base.py  |  67 +++++-
 plugins/spec-loop/scripts/test_dashboard_server.py |  27 ++-
 plugins/spec-loop/scripts/test_run_metrics.py      |  18 ++
 plugins/spec-loop/scripts/test_run_state.py        |  11 +
 .../spec-loop/scripts/test_slice_wave_contract.py  |  37 +--
 .../scripts/test_slice_wave_contract_crash.py      | 257 +++++++++++++++++++++
 .../scripts/test_slice_wave_contract_scope.py      |  10 +-
 plugins/spec-loop/skills/escalation-gate/SKILL.md  |  19 +-
 plugins/spec-loop/workflows/slice-wave.workflow.js |  63 ++++-
 scripts/coverage_omit.txt                          |   4 +-
 17 files changed, 583 insertions(+), 58 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
10,
80
]
],
"plugins/spec-loop/agents/slice-worker-fallback.md": [
[
46,
52
],
[
98,
100
],
[
152,
168
]
],
"plugins/spec-loop/references/risk-tiers.md": [
[
89,
91
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
101,
101
],
[
113,
121
]
],
"plugins/spec-loop/scripts/dashboard_server.py": [
[
151,
151
]
],
"plugins/spec-loop/scripts/run_metrics.py": [
[
126,
126
]
],
"plugins/spec-loop/scripts/run_state.py": [
[
68,
69
]
],
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
7,
9
],
[
44,
46
],
[
93,
95
],
[
117,
170
]
],
"plugins/spec-loop/scripts/test_dashboard_server.py": [
[
1247,
1257
],
[
1260,
1260
],
[
1279,
1292
]
],
"plugins/spec-loop/scripts/test_run_metrics.py": [
[
457,
474
]
],
"plugins/spec-loop/scripts/test_run_state.py": [
[
199,
209
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract.py": [
[
8,
13
],
[
30,
36
],
[
62,
65
],
[
150,
152
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_crash.py": [
[
1,
257
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_scope.py": [
[
8,
10
],
[
254,
257
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
72,
72
],
[
74,
84
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
40,
40
],
[
432,
435
],
[
456,
456
],
[
640,
646
],
[
858,
886
],
[
889,
897
],
[
919,
919
]
],
"scripts/coverage_omit.txt": [
[
38,
39
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index f193dcc..35455aa 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -5,10 +5,81 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 
+### Added
+- **`internal-error` escalation trigger** — a seventh `EscalationRecord.trigger` value for machine
+  failure, one string covering both shapes of it: an unhandled exception that aborted a slice
+  (`workflows/slice-wave.workflow.js` — the catch-all at :892) and a slice that returned no result
+  at all (:919). The enum lives at :40. The crash record leads with the real exception text and the
+  last stage/role dispatched before the failure, in that order — a guaranteed ordering, so the
+  400-character limit `render_escalation()` puts on a context cuts the fixed classification prose
+  before either diagnostic. The ordering is not a promise that both diagnostics fit: measured
+  against the longest stage text, an exception message past ~286 characters pushes the stage
+  attribution out of the rendered context entirely (its "starting point, not a culprit" caveat drops
+  at ~200), and only the exception text, which leads, is truncated last. That stage is the most
+  recent dispatch, **not** a per-throw stage: the whole stage sequence sits under one `try`, so the
+  loop cannot know which stage threw, and the record says "after", not "in", and says why. It also
+  refuses to guess the cause: all an exception reaching the catch-all proves is that neither
+  structural guard *raised* its escalation record — not that the crash started outside a guard,
+  since `budget.remaining()` is called inside the token-floor guard itself — so it may be a loop or
+  agent-contract bug and it may equally be a host- or agent-layer resource failure (a rejected agent
+  call on a hard token or rate limit, say) — the exception text is the evidence, not the label. The
+  lost-slice record at :919 follows the same rule in the same words: neither guard *raised* its
+  escalation record, "and that is all a null result proves, not that no guard check ran" — and it no
+  longer denies a resource cause it cannot rule out. It is not a judgment trigger and it is not
+  answerable by re-dispatching an agent: its three options (retry the slice, skip it, stop the run)
+  are controller actions, and each option's detail names the controller as what applies it. Added to
+  `ESCALATION_TRIGGERS` in `run_state.py`, `run_metrics.py` and `dashboard_server.py`, to the record
+  shape in `references/run-state-v2.md`, and to the enumerations in
+  `skills/escalation-gate/SKILL.md` and `agents/slice-worker-fallback.md` — the last of these being
+  the behavioral spec for the inline-mode twin, which must classify identically.
+
+### Changed
+- **`budget-exhausted` narrowed to a resource signal** — the string stays and its position in the
+  enum is unchanged; only its meaning narrows. It is now raised solely by the loop's two structural
+  guards, the per-slice agent cap and the per-stage token floor (`slice-wave.workflow.js:425` and
+  `:427`), both of which keep their existing wording. It no longer covers an unhandled exception or
+  a lost slice: through 2.2.0 the catch-all relabelled every uncaught error as a `budget-exhausted`
+  "wave interrupted" escalation, which in run 20260825-scope-ceiling asked for budget on behalf of
+  an unguarded optional-field read — a `TypeError` that no amount of budget would have prevented —
+  and the lost-slice record carried the same trigger. Both are now `internal-error`. The claim
+  is deliberately about that concrete failure, not about uncaught errors in general — as the
+  Added entry above says, some of those really are resource failures.
+  There are still exactly five *judgment* triggers; neither `budget-exhausted` nor `internal-error`
+  is one, and `internal-error` is deliberately outside the answerable set, which stays at five.
+- **`schema_version` stays `2`** — adding an enum value is an additive change to the sidecar
+  contract, so the version is deliberately not bumped (human-decided). `SCHEMA_VERSION` in
+  `run_state.py` and `run_metrics.py` is unchanged, and existing run directories carrying
+  `budget-exhausted` records still validate and still bucket as `budget-exhausted` rather than
+  degrading to `other`.
+
+#### Compatibility: a plugin downgrade to 2.2.0 DISCARDS an affected run dir
+
+This is worse than a mis-labelled trigger, and it is not symmetric with a normal additive change.
+`run_state.py`'s `persist_slice` validates the whole `SliceResult` **before** it writes anything and
+raises `SidecarInvalid` on an unrecognised `trigger`; only after validation passes does it write the
+sidecar, append the slice's events, and render `slice-<id>-report.md`. Under 2.2.0, whose
+`ESCALATION_TRIGGERS` has no `internal-error`, a slice that escalated with that trigger therefore
+produces **no sidecar, no events and no report at all** — not a wrongly-labelled record. The slice
+reports `ESCALATED` with nothing on disk saying why, and the diagnostic information the escalation
+existed to deliver is gone.
+
+Consequences, stated plainly: a run directory written by this version is **not readable by 2.2.0**,
+and the repository and the installed plugin must be updated together. Re-running the affected slice
+under 2.2.0 will not recover the record, because the record was never written.
+
+### Scope and limits of this change
+
+Verifiability ceiling: nothing this entry describes in `workflows/slice-wave.workflow.js` has been
+executed. The loop resolves its workflow from the installed plugin cache, so the merged file takes
+effect only after a plugin reinstall. Those claims rest on a real `node` parse of the source plus
+source-text contract assertions (`test_slice_wave_contract_crash.py`), which prove a construct is
+present and cannot prove it behaves. The Python-side tuple, validation, metrics and dashboard
+changes are covered by executed tests.
+
 ## [2.2.0] - 2026-08-26
 ### Added
 - **Run-level scope ceiling** — an optional `scope_ceiling` list in `dag.json` (validated
   only when present; a run without one stays fully valid and mutable), threaded through
   `ctx` and prefixed to **every** agent prompt by the wave's shared packet as a binding
diff --git a/plugins/spec-loop/agents/slice-worker-fallback.md b/plugins/spec-loop/agents/slice-worker-fallback.md
index cbfd8c5..d8ea1a0 100644
--- a/plugins/spec-loop/agents/slice-worker-fallback.md
+++ b/plugins/spec-loop/agents/slice-worker-fallback.md
@@ -41,12 +41,17 @@ is handed to you, use it verbatim rather than reconstructing it.
 
 ## Loop bounds (identical to the workflow)
 
 Replan **≤1** · per-task implementer retry **≤1** · fix rounds **≤2** · total agent
 dispatches capped by tier: **10 / 18 / 32** for Tier 1 / 2 / 3. Count every dispatch,
-including re-reviews. Hitting a cap or a bound with work outstanding is a `budget-exhausted`
-escalation, not a reason to continue unbounded or to declare done without evidence.
+including re-reviews. A bound is never a reason to continue unbounded or to declare done
+without evidence — but exhausting one is not a resource problem. Only two things here are
+`budget-exhausted`: the tier agent cap, and the per-stage token floor (the wave budget left is
+below what a single stage needs). Every loop bound escalates instead as the thing that actually
+stalled — a spent replan as `council-objection`, a spent task retry as `ambiguity` or the
+blocker the task reported (Pipeline 3), findings surviving both fix rounds as `review-block`,
+or `quality-gate-block` when the survivors are gate violations.
 
 ## Pipeline
 
 **0 — Worktree.** Capture your start timestamp (`date -u +%Y-%m-%dT%H:%M:%SZ`). Prepare the
 worktree with the handed-in `worktrees.py prepare` invocation:
@@ -88,11 +93,13 @@ of each prompt).
 order, each at the model tier its task's lane maps to. Give each the worktree path, its task
 brief, the plan and conventions paths, `shared_constraints`, and the test/build commands. No
 per-task review below Tier 3; at Tier 3 run the per-task review your tier table specifies.
 Handle statuses: `NEEDS_CONTEXT` → answer from the plan or codebase and re-dispatch once
 (that is the task's one retry); a genuine `BLOCKED`, or a second failure on the same task →
-escalate (`material-assumption` or `review-block` as fits) and return `ESCALATED`. Roll up
+escalate and return `ESCALATED`. Pick the trigger the way the workflow does: a dispatch that
+came back with **no result** is `ambiguity` (see step 4), never `internal-error`; a `BLOCKED`
+that states a real blocker is `material-assumption` or `review-block` as fits. Roll up
 every `concerns[]` and `deviations[]` — the reviewer needs them.
 
 **4 — Review ∥ quality gate (one message).** Build the review package once with the handed-in
 builder over `<slice-base-sha>..HEAD`, then in a single message: dispatch ONE `pr-reviewer` in
 `slice` mode (package path, plan path, tier + blocking bar, `conventions.md`, the rolled-up
@@ -140,16 +147,27 @@ trusts the sidecar over anything you say, and an invalid one makes this slice un
 regardless of how the work went.
 
 ## Escalations
 
 Every escalation is an EscalationRecord in `escalations[]`: stable id `<slice-id>:<trigger>`,
-one of the six triggers (`ambiguity`, `material-assumption`, `review-block`,
-`council-objection`, `quality-gate-block`, `budget-exhausted`), the context, the precise
-question, options with one marked `recommended`, and `if_unanswered`. Proceed-and-log stays the
-default — surface only genuine ambiguity or a material assumption touching behavior, public
-contracts, persisted data, security, or an external integration. A slice with any open
-escalation returns `ESCALATED`.
+one of the seven triggers (`ambiguity`, `material-assumption`, `review-block`,
+`council-objection`, `quality-gate-block`, `budget-exhausted`, `internal-error`), the context,
+the precise question, options with one marked `recommended`, and `if_unanswered`.
+Proceed-and-log stays the default — surface only genuine ambiguity or a material assumption
+touching behavior, public contracts, persisted data, security, or an external integration. A
+slice with any open escalation returns `ESCALATED`. `budget-exhausted` is only for the tier
+agent cap or the per-stage token floor (see Loop bounds), never for a spent loop bound.
+`internal-error` is narrower still: an unhandled exception that aborted the slice, and
+nothing else. A dispatch that comes back with **no result** is not one — the workflow
+classifies both shapes of that as `ambiguity` (a planner returning nothing, and a task whose
+retry also returned nothing, recorded as a terminal dispatch failure), and you classify them
+identically; `ambiguity` is answerable and `internal-error` deliberately is not, so
+mislabelling one costs the human the ability to answer it. An `internal-error` context
+carries the real error text and names the stage/role you were actually running when it
+aborted: you drive every stage serially, so unlike the workflow you DO know which one it was
+— say it. Hedge only for a failure inside step 4's concurrent review ∥ quality-gate message,
+where either dispatch may be the one that died; there, name both and say which is unclear.
 
 ## Return
 
 Statuses: `DONE` · `SPLIT` · `ESCALATED` · `FAILED`. Return a summary of **≤15 lines** —
 status, branch, `base..head`, critique verdict, tasks completed, review outcome (confirmed /
diff --git a/plugins/spec-loop/references/risk-tiers.md b/plugins/spec-loop/references/risk-tiers.md
index 3d88779..a8d90be 100644
--- a/plugins/spec-loop/references/risk-tiers.md
+++ b/plugins/spec-loop/references/risk-tiers.md
@@ -84,11 +84,13 @@ overlay). Any match promotes `review_tier` to 3 and records a `decision` event w
 ## Escalation-relevant consequences
 
 Everything the tier decides funnels into exactly two of `escalation-gate`'s five triggers:
 `review-block` (blocking findings survive the fix loop, or verification cannot pass) and
 `quality-gate-block` (gate violations survive it). The `budget-exhausted` record the per-slice
-agent cap emits is mechanical, not a judgment — the caps in the table above are its only source.
+agent cap emits is mechanical, not a judgment — and the caps in the table above are only one of
+its two sources; the other is the loop's per-stage token floor, which no tier setting changes.
+A spent loop bound is neither: it escalates as whatever actually stalled (`run-state-v2.md`).
 
 An over-scope record (`critique.over_scope`) is **not** in that funnel. It is record-only:
 it is carried into the `council-verdict` event and the sidecar, counted null-honestly by
 `run_metrics.py`, and read by a human — it raises no trigger, blocks nothing, and is never
 a finding. Work the council judged out of scope and asked not to be built is a
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index cbbd777..851eb00 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -96,11 +96,11 @@ prose about the slice.
 ## `EscalationRecord` (embedded in sidecars; rendered into `escalations.md`)
 
 ```jsonc
 {
   "id": "s1:review-block",     // "<slice-id>:<trigger>[:<round>]" — stable across resumes
-  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | budget-exhausted",
+  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | budget-exhausted | internal-error",
   "title": "<short title>",
   "context": "<what the loop was doing and why it cannot decide>",
   "question": "<the precise question>",
   "options": [{ "label": "...", "detail": "...", "recommended": true }],
   "if_unanswered": "pause this slice; continue all independent slices",
@@ -108,10 +108,19 @@ prose about the slice.
   "opened": "<ISO-8601 UTC>",
   "answer": null, "answered_at": null
 }
 ```
 
+`budget-exhausted` is raised only by the loop's two structural guards (agent cap, stage
+token floor); `internal-error` covers the two machine-failure shapes the loop actually
+produces — an unhandled exception that aborted a slice, and a slice that returned no result
+at all — either of which may itself have a host- or agent-layer cause (e.g. a rejected agent
+call on a hard token or rate limit) that the record does not pretend to rule out. It is not
+a catch-all for every other failure: a failure the loop can name keeps the trigger that
+names it, so a spent replan stays `council-objection` and a blocked task — including a task
+dispatch that returned no result — stays `ambiguity`. Neither is a judgment trigger.
+
 ## `events.jsonl` — the machine channel
 
 Append-only, one JSON object per line, written only by the controller
 (`run_state.py` appends; workflow returns carry the payloads; the controller
 stamps `ts` — workflow scripts have no clock).
diff --git a/plugins/spec-loop/scripts/dashboard_server.py b/plugins/spec-loop/scripts/dashboard_server.py
index a2ee2d4..ec8e994 100644
--- a/plugins/spec-loop/scripts/dashboard_server.py
+++ b/plugins/spec-loop/scripts/dashboard_server.py
@@ -146,11 +146,11 @@ PROJECTED = "projected"
 
 # The EscalationRecord triggers (run-state-v2.md). Used both to validate a
 # record's own ``trigger`` field and to read the trigger an escalation id encodes.
 ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
                        "council-objection", "quality-gate-block",
-                       "budget-exhausted")
+                       "budget-exhausted", "internal-error")
 
 # Labels meaning "the sidecar recorded a terminal outcome that the controller has
 # not yet written back into dag.json, and which WILL clear on its own" — a DONE
 # slice awaiting its serial merge, a SPLIT awaiting child ingestion. Neither is
 # runnable, but both are treated as landed by the wave projection so dependents
diff --git a/plugins/spec-loop/scripts/run_metrics.py b/plugins/spec-loop/scripts/run_metrics.py
index 5202194..737db91 100644
--- a/plugins/spec-loop/scripts/run_metrics.py
+++ b/plugins/spec-loop/scripts/run_metrics.py
@@ -121,10 +121,11 @@ ESCALATION_TRIGGERS = (
     "material-assumption",
     "review-block",
     "council-objection",
     "quality-gate-block",
     "budget-exhausted",
+    "internal-error",
 )
 REVERSIBILITY_BUCKETS = ("trivial", "moderate", "high", "n/a")
 GATE_RESULTS = ("PASS", "FAIL", "SKIPPED")
 # The sidecar's review block — the numerically-precise review channel.
 REVIEW_COUNTER_KEYS = ("confirmed", "refuted", "evidence_failed", "fix_rounds")
diff --git a/plugins/spec-loop/scripts/run_state.py b/plugins/spec-loop/scripts/run_state.py
index 1689f79..e44150e 100644
--- a/plugins/spec-loop/scripts/run_state.py
+++ b/plugins/spec-loop/scripts/run_state.py
@@ -63,11 +63,12 @@ import tempfile
 SCHEMA_VERSION = 2
 SLICE_RESULT_STATUSES = ("DONE", "SPLIT", "ESCALATED", "FAILED")
 QUALITY_STATUSES = ("PASS", "FAIL", "SKIPPED")
 VERDICTS = ("ENDORSE", "ENDORSE_WITH_CONCERNS", "OBJECT", "SKIPPED")
 ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
-                       "council-objection", "quality-gate-block", "budget-exhausted")
+                       "council-objection", "quality-gate-block", "budget-exhausted",
+                       "internal-error")
 ESCALATION_STATUSES = ("OPEN", "ANSWERED")
 RISK_TIERS = (1, 2, 3)
 # Matches dag.py: references/split-ingestion.md calls a one-child split a
 # malformed proposal, so a SPLIT sidecar proposing one is refused here too.
 MIN_SPLIT_CHILDREN = 2
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index cafdfb2..dc9a957 100644
--- a/plugins/spec-loop/scripts/slice_wave_contract_base.py
+++ b/plugins/spec-loop/scripts/slice_wave_contract_base.py
@@ -2,12 +2,13 @@
 
 The wave workflow is JavaScript and is not run by any lane of this repo's
 suite: it is resolved at runtime from the installed plugin cache. Its
 correctness has therefore rested entirely on review, and this run paid for
 that twice - an unguarded optional-field read aborted a whole wave and was
-mislabelled as a budget escalation. The two ``test_slice_wave_contract*.py``
-modules that import this one are the cheapest honest coverage available:
+mislabelled as a budget escalation (both the read and the mislabelling are now
+pinned here). The three ``test_slice_wave_contract*.py`` modules that import
+this one are the cheapest honest coverage available:
 they parse the file with node (a real parse, not a substring) and pin the
 handful of source facts whose loss is a known, observed outage - the
 null-guards on TASK_RESULT.commits and its sibling optional arrays, the
 type-safe read of CTX.scope_ceiling, the answer-injection sites, and the
 record-only isolation of the over-scope flag from the four control-flow
@@ -38,12 +39,13 @@ snippets keeps the assertions byte-exact while the metrics stay honest.
 Split out of one 422-non-blank-line module so each importing test module
 stays under the quality gate's 300-line class_lines threshold; this file
 carries no tests of its own (its class exposes no `test_*` method), so
 `unittest discover -p 'test_*.py'` never collects it directly.
 
-Usage: imported by test_slice_wave_contract.py and
-test_slice_wave_contract_scope.py; not runnable on its own.
+Usage: imported by test_slice_wave_contract.py,
+test_slice_wave_contract_scope.py, and test_slice_wave_contract_crash.py;
+not runnable on its own.
 """
 
 import unittest
 from pathlib import Path
 
@@ -86,10 +88,13 @@ OVER_SCOPE_SCHEMA = "over_scope: { type: 'object'"
 CRITIQUE_ROLLUP = "state.critique = { verdict:"
 SPLIT_SUPPRESSION = "return (rec && depth < 2 && verdict !== 'OBJECT') ? rec : null"
 OBJECTION_SELECTION = "ob: (safety || objections[0])"
 REPLAN_VETO = "if (safety || !ob.fixable_by_replan || state.replanned)"
 FINDING_CATEGORIES = "category: { enum: ["
+# The trigger enum has five homes: this line, and the ESCALATION_TRIGGERS
+# tuple in run_state.py, run_metrics.py and dashboard_server.py.
+TRIGGER_ENUM_LINE = "trigger: { enum: ["
 COUNCIL_VERDICT_EVENT = "type: 'council-verdict'"
 SCOPE_HELPER = "function scopeRecord("
 DERIVE_INPUTS_FN = "function deriveCouncilInputs(verdicts) {"
 HELPER_END = "\n}\n"
 SCOPE_LOCAL = "const scope = scopeRecord(verdicts)"
@@ -107,10 +112,64 @@ CONCERN_MARKER = "over_scope: !!(v.over_scope && v.over_scope.flag === true)"
 DEFERRED_ARRAY = (
     "deferred: concerns.filter(c => c.disposition_hint === 'defer')"
     ".map(c => c.text)")
 STATE_DEFERRED_INIT = "deferred: []"
 STATE_DEFERRED = "state.deferred"
+STATE_STAGE_INIT = "stage: null"
+STAGE_ASSIGNMENT = "state.stage = role"
+DISPATCH_GUARD_CALL = "guard(slice, state)"
+CRASH_STAGE_CONTEXT = "Last stage/role dispatched before the failure: ${stageText}"
+CRASH_STAGE_PRECISION = "the most recent dispatch, not a per-throw stage"
+CRASH_STAGE_OVERCLAIM = "in flight"
+CRASH_TRIGGER = "esc(slice, 'internal-error',"
+CRASH_STAGE_FALLBACK = (
+    "const stageText = stage || "
+    "'none (the crash happened before any agent was dispatched)'")
+CRASH_TITLE_BRANCH = (
+    "const title = stage ? `slice crashed after ${stage}` "
+    ": 'slice crashed before any agent was dispatched'")
+CRASH_TITLE_UNGRAMMATICAL = "crashed after ${stageText}"
+CRASH_CLASSIFIED_PASSTHROUGH = "if (e && e.escRecord) return escalated(slice, state, e.escRecord)"
+CRASH_OPTION_RETRY = "label: 'Retry this slice'"
+CRASH_OPTION_SKIP = "label: 'Skip this slice'"
+CRASH_OPTION_STOP = "label: 'Stop the run'"
+CRASH_OPTION_CONTROLLER_ACTS = (
+    "The CONTROLLER must act on this at the next dispatch")
+CRASH_ERROR_FIRST = "`Error: ${String((e && e.message) || e)}."
+CRASH_ERROR_EXPR = "${String((e && e.message) || e)}"
+# The ONLY thing the escRecord check one line above the fallback proves: that
+# neither structural guard RAISED its own record. It does NOT prove the crash
+# originated outside a guard - `budget.remaining()` is called INSIDE the
+# token-floor guard, so a throw from there starts in a guard and still reaches
+# the fallback with no escRecord. The old phrasing asserted the stronger claim.
+CRASH_CLASSIFICATION_SENTENCE = "neither structural guard raised its escalation record"
+CRASH_GUARD_ORIGIN_OVERCLAIM = "so this crash came from neither"
+CRASH_HOST_LAYER_CAVEAT = "host- or agent-layer resource failure"
+# render_escalation() (run_state.py) collapses the context and hard-truncates it
+# at 400 characters, and escalations.md is the corpus the escalation gate's
+# precedent check reads. Both the exception text and the stage attribution have
+# to fit inside that budget, ahead of the fixed classification prose.
+CRASH_CONTEXT_RENDER_LIMIT = 400
+CRASH_STAGE_CAVEAT = "so a starting point, not a culprit"
+# The mirror-image overclaim this module now forbids: asserting "bug, NOT a
+# budget limit" is as unprovable as the old "budget" assertion it replaced.
+CRASH_CAUSE_OVERCLAIM = "This is a loop or agent-contract bug"
+CRASH_BUDGET_DENIAL_OVERCLAIM = "NOT a cap or budget limit"
+GUARD_BUDGET_TRIGGER = "esc(slice, 'budget-exhausted',"
+SLICE_LOST_RECORD = "esc(A.slices[i], 'internal-error', 'slice lost',"
+# Third instance of the same overclaim pattern: a thunk resolved to null
+# proves nothing about the cause, so the lost-slice record must not deny one.
+SLICE_LOST_CAUSE_DENIAL = "Not a resource limit."
+# Fifth instance, and the sibling of CRASH_GUARD_ORIGIN_OVERCLAIM above: a
+# guard "firing" asserts its CHECK never ran, which neither record can know.
+# All either one proves is that no guard RAISED an escalation record - a throw
+# from inside `budget.remaining()` starts in the token-floor guard and still
+# arrives with no escRecord. Forbidden across the WHOLE source, so the phrase
+# cannot come back in either the crash record or the lost-slice one.
+GUARD_FIRED_OVERCLAIM = "structural guard fired"
+SLICE_LOST_GUARD_PROVABLE = "Neither structural guard raised its escalation record"
+SLICE_LOST_CAUSE_UNKNOWN = "the cause is unknown here"
 STAGE_CRITIQUE_START = "async function stageCritique(slice, state, plan) {"
 STAGE_CRITIQUE_END = "// Stage T helpers"
 SPLIT_RETURN = "if (splitRec) return { stop: doneResult(slice, state, 'SPLIT'"
 RECORD_DEFERRALS_FN = "function recordDeferrals(slice, state, concerns) {"
 RECORD_DEFERRALS_CALL = "recordDeferrals(slice, state, concerns)"
diff --git a/plugins/spec-loop/scripts/test_dashboard_server.py b/plugins/spec-loop/scripts/test_dashboard_server.py
index 3452ed0..6c68e39 100644
--- a/plugins/spec-loop/scripts/test_dashboard_server.py
+++ b/plugins/spec-loop/scripts/test_dashboard_server.py
@@ -1242,13 +1242,24 @@ class EscalationSourceTests(unittest.TestCase):
         # empty rather than invented. The trigger, though, is encoded in the id
         # itself by contract, so that much is real.
         self.assertEqual(e["title"], "")
         self.assertEqual(e["trigger"], "budget-exhausted")
 
+    def test_internal_error_parses_out_of_an_escalation_id(self):
+        # The id's second segment is the trigger by contract, so a crash id
+        # must resolve — _trigger_from_id gates on ESCALATION_TRIGGERS.
+        def build(run_dir):
+            write_dag_v2(run_dir, [slice_obj("s1")])
+            write_events(run_dir, [
+                ("s1", "escalation-opened", {"id": "s1:internal-error"}),
+            ])
+        run = self.scan(build)
+        self.assertEqual(run["escalations"][0]["trigger"], "internal-error")
+
     def test_a_malformed_id_yields_no_made_up_trigger(self):
         # The id's second segment is only accepted when it is one of the
-        # contract's six triggers, so a hand-edited id cannot surface garbage.
+        # contract's known triggers, so a hand-edited id cannot surface garbage.
         def build(run_dir):
             write_dag_v2(run_dir, [slice_obj("s1")])
             write_events(run_dir, [
                 ("s1", "escalation-opened", {"id": "s1:not-a-real-trigger"}),
                 ("s2", "escalation-opened", {"id": "noseparator"}),
@@ -1263,10 +1274,24 @@ class EscalationSourceTests(unittest.TestCase):
                           escalations=[escalation_record("s1:review-block",
                                                          trigger="made-up")])
         run = self.scan(build)
         self.assertEqual(run["escalations"][0]["trigger"], "review-block")
 
+    def test_a_record_trigger_of_internal_error_is_kept_as_itself(self):
+        # The record path, not the id path: _enum_or_none nulls any trigger
+        # outside ESCALATION_TRIGGERS, so a crash record must be listed there
+        # or every crash escalation renders with no trigger at all. The id is
+        # deliberately trigger-less here to isolate _enum_or_none from the
+        # _trigger_from_id fallback.
+        def build(run_dir):
+            write_dag_v2(run_dir, [slice_obj("s1")])
+            write_sidecar(run_dir, "s1", status="ESCALATED", escalations=[
+                escalation_record("s1", trigger="internal-error"),
+            ])
+        run = self.scan(build)
+        self.assertEqual(run["escalations"][0]["trigger"], "internal-error")
+
     def test_nested_and_named_payload_id_forms_are_both_accepted(self):
         # v2 pins the EscalationRecord but not how an event wraps it.
         def build(run_dir):
             write_dag_v2(run_dir, [slice_obj("s1")])
             write_events(run_dir, [
diff --git a/plugins/spec-loop/scripts/test_run_metrics.py b/plugins/spec-loop/scripts/test_run_metrics.py
index 72c9657..7f26692 100644
--- a/plugins/spec-loop/scripts/test_run_metrics.py
+++ b/plugins/spec-loop/scripts/test_run_metrics.py
@@ -452,10 +452,28 @@ class EscalationPairingTests(unittest.TestCase):
             json.dumps(ev("2026-07-30T10:00:00Z", "b", "escalation-opened",
                           id="b:x")))
         self.assertEqual([r["trigger"] for r in result["records"]],
                          ["other", None])
 
+    def test_internal_error_buckets_as_itself_not_other(self):
+        # _normalize_trigger degrades unknowns to "other"; a crash must keep
+        # its own by_trigger key so mislabelled resource limits stay visible.
+        opened = ev(
+            "2026-07-30T10:00:00Z", "a", "escalation-opened",
+            id="a:internal-error", trigger="internal-error")
+        result = self.records_for(json.dumps(opened))
+        triggers = [r["trigger"] for r in result["records"]]
+        self.assertEqual(triggers, ["internal-error"])
+
+    def test_internal_error_is_substring_safe_against_every_other_trigger(self):
+        # _legacy_match_triggers() in run_metrics.py matches by containment
+        # (no line number: it moved once already when internal-error landed).
+        others = [t for t in rm.ESCALATION_TRIGGERS if t != "internal-error"]
+        for other in others:
+            self.assertNotIn(other, "internal-error")
+            self.assertNotIn("internal-error", other)
+
     def test_union_counts_a_duplicated_record_once(self):
         metrics = compute_for(v2_files(), run_id="20260730-v2")
         self.assertEqual(metrics["safety"]["escalations"]["total"], 2)
         self.assertEqual(metrics["safety"]["escalations"]["basis"],
                          rm.BASIS_BOTH)
diff --git a/plugins/spec-loop/scripts/test_run_state.py b/plugins/spec-loop/scripts/test_run_state.py
index 2f8c3a8..a6aaff6 100644
--- a/plugins/spec-loop/scripts/test_run_state.py
+++ b/plugins/spec-loop/scripts/test_run_state.py
@@ -194,10 +194,21 @@ class TestValidateSidecar(unittest.TestCase):
 
     def test_escalation_trigger_enum(self):
         body = sidecar("ESCALATED", escalations=[escalation(trigger="vibes")])
         self.assertMentions(body, "trigger")
 
+    def test_escalation_trigger_accepts_internal_error(self):
+        # A machine failure is a first-class trigger: run_state.py:204 is
+        # fail-closed, so an unlisted value would falsely fail the sidecar.
+        body = sidecar("ESCALATED", escalations=[
+            escalation(id="s1:internal-error", trigger="internal-error")])
+        self.assertValid(body)
+
+    def test_escalation_trigger_still_rejects_a_bogus_value(self):
+        body = sidecar("ESCALATED", escalations=[escalation(trigger="kaboom")])
+        self.assertMentions(body, "trigger")
+
     def test_escalation_needs_options(self):
         body = sidecar("ESCALATED", escalations=[escalation(options=[])])
         self.assertMentions(body, "options")
 
     def test_escalation_option_needs_a_label(self):
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract.py b/plugins/spec-loop/scripts/test_slice_wave_contract.py
index 488397e..ef66fbd 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract.py
@@ -3,14 +3,16 @@
 injection, and the record-only `over_scope` critique field.
 
 See `slice_wave_contract_base.py` for the module-wide rationale (why this
 is source-text assertion, why snippets are named constants, and the two
 known-and-deliberately-unguarded instances this module does NOT claim to
-cover). `test_slice_wave_contract_scope.py` is this module's sibling,
-covering the deferred-event and run-scope-ceiling concerns - split out
-purely to keep each module's whole-file `class_lines` under the quality
-gate's 300-line threshold; no test here depends on anything in the sibling.
+cover). Two siblings carry the rest of the same contract:
+`test_slice_wave_contract_scope.py` (deferred events, run scope ceiling)
+and `test_slice_wave_contract_crash.py` (the `internal-error`
+classification of machine failures) - split out purely to keep each
+module's whole-file `class_lines` under the quality gate's 300-line
+threshold; no test here depends on anything in a sibling.
 
 Usage:
     python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_slice_wave_contract.py'
 """
 
@@ -23,17 +25,17 @@ import unittest
 
 from slice_wave_contract_base import (
     ANSWER_CONTEXT_END, ANSWER_CONTEXT_START, ANSWERABLE_TRIGGERS, CLEAN,
     COUNCIL_VERDICT_EVENT, CRITIQUE_REQUIRED, CRITIQUE_ROLLUP,
     FAIL_CLOSED_DEFAULT, FINDING_CATEGORIES, FLAGGED, GATE_ANSWER,
-    GATE_ANSWER_CONTEXT, GUARDED_BASE, GUARDED_CONCERNS, GUARDED_DEVIATIONS,
-    GUARDED_HEAD, GUARDED_LOCAL, GUARDED_TOUCHED, HELPER_END,
-    NO_COMMITS_ESCALATION, OBJECTION_SELECTION, OVER_SCOPE_DEFAULT,
-    OVER_SCOPE_SCHEMA, REPLAN_VETO, SCOPE_DRIVER, SCOPE_HELPER, SCOPE_LOCAL,
-    SCOPE_REASON_KEPT, SCOPE_SPREAD, SIDECAR_SCOPE_ATTACH,
-    SPLIT_SUPPRESSION, TASK_LOOP_END, TASK_LOOP_START, TASK_RESULT_REQUIRED,
-    WorkflowSourceTestCase, wrapped_source,
+    GATE_ANSWER_CONTEXT, GUARDED_BASE, GUARDED_CONCERNS,
+    GUARDED_DEVIATIONS, GUARDED_HEAD, GUARDED_LOCAL, GUARDED_TOUCHED,
+    HELPER_END, NO_COMMITS_ESCALATION, OBJECTION_SELECTION,
+    OVER_SCOPE_DEFAULT, OVER_SCOPE_SCHEMA, REPLAN_VETO, SCOPE_DRIVER,
+    SCOPE_HELPER, SCOPE_LOCAL, SCOPE_REASON_KEPT, SCOPE_SPREAD,
+    SIDECAR_SCOPE_ATTACH, SPLIT_SUPPRESSION, TASK_LOOP_END, TASK_LOOP_START,
+    TASK_RESULT_REQUIRED, WorkflowSourceTestCase, wrapped_source,
 )
 
 
 class TestTheFileStillParses(unittest.TestCase):
     def test_node_parses_the_wrapped_workflow_source(self):
@@ -55,14 +57,14 @@ class TestTheFileStillParses(unittest.TestCase):
 
 
 class TestOptionalTaskResultReadsAreGuarded(WorkflowSourceTestCase):
     """Regression, run 20260825-scope-ceiling wave 2: TASK_RESULT does not
     require `commits`, so a task that legitimately committed nothing returned
-    DONE with the key absent. `state.commits.head = r.commits.head` threw a
-    TypeError, the catch-all re-labelled it 'wave interrupted' /
-    budget-exhausted, and a wave whose five tasks had all committed was
-    reported as a resource failure."""
+    DONE with the key absent. An unguarded `state.commits.head = r.commits.head`
+    threw a TypeError, which is now correctly classified as 'internal-error' by
+    the crash handler. Before crash classification, such errors were mislabeled
+    as budget-exhausted, causing misdirected diagnosis."""
 
     def task_loop(self):
         """The Stage-T task-result-handling region (runTask() and its small
         helpers, through stageTasks()'s loop), where every task-result read
         happens."""
@@ -143,12 +145,13 @@ class TestOverScopeIsRecordOnly(WorkflowSourceTestCase):
         required = self.line_containing(CRITIQUE_REQUIRED)
         self.assertNotIn("over_scope", required)
 
     def test_the_fail_closed_default_supplies_the_field(self):
         # Extended BEFORE any read exists: an unguarded read of a missing
-        # optional field throws, is swallowed by the catch-all, and is
-        # mislabelled as a budget escalation - the defect that killed wave 2.
+        # optional field throws, is swallowed by the catch-all, and is now
+        # correctly classified as 'internal-error' - before crash classification,
+        # such errors were mislabeled as budget escalation, which killed wave 2.
         default = self.line_containing(FAIL_CLOSED_DEFAULT)
         self.assertIn(OVER_SCOPE_DEFAULT, default)
 
     def test_the_read_goes_through_the_pure_helper_not_a_bare_field_access(self):
         helper = self.between(SCOPE_HELPER, HELPER_END)
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
new file mode 100644
index 0000000..cf42db4
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
@@ -0,0 +1,257 @@
+#!/usr/bin/env python3
+"""Contract checks: the `internal-error` classification of machine failures -
+what the crash record names, what it refuses to claim, and whose job its
+options are.
+
+See `slice_wave_contract_base.py` for the module-wide rationale, and
+`test_slice_wave_contract.py` for the sibling module covering guarded
+task-result reads, quality-gate-block answer injection, and the
+record-only `over_scope` critique field. Split purely to keep each
+module's whole-file `class_lines` under the quality gate's 300-line
+threshold; no test here depends on anything in the sibling.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_slice_wave_contract_crash.py'
+"""
+
+import re
+import unittest
+
+import dashboard_server
+import run_metrics
+import run_state
+from slice_wave_contract_base import (
+    ANSWERABLE_TRIGGERS, CRASH_BUDGET_DENIAL_OVERCLAIM, CRASH_CAUSE_OVERCLAIM,
+    CRASH_CLASSIFICATION_SENTENCE, CRASH_CLASSIFIED_PASSTHROUGH,
+    CRASH_CONTEXT_RENDER_LIMIT, CRASH_ERROR_EXPR, CRASH_ERROR_FIRST,
+    CRASH_GUARD_ORIGIN_OVERCLAIM, CRASH_HOST_LAYER_CAVEAT,
+    CRASH_OPTION_CONTROLLER_ACTS,
+    CRASH_OPTION_RETRY, CRASH_OPTION_SKIP, CRASH_OPTION_STOP,
+    CRASH_STAGE_CAVEAT, CRASH_STAGE_CONTEXT, CRASH_STAGE_FALLBACK,
+    CRASH_STAGE_OVERCLAIM,
+    CRASH_STAGE_PRECISION, CRASH_TITLE_BRANCH, CRASH_TITLE_UNGRAMMATICAL,
+    CRASH_TRIGGER, DISPATCH_GUARD_CALL, GUARD_BUDGET_TRIGGER,
+    GUARD_FIRED_OVERCLAIM, SLICE_LOST_CAUSE_DENIAL,
+    SLICE_LOST_CAUSE_UNKNOWN, SLICE_LOST_GUARD_PROVABLE,
+    SLICE_LOST_RECORD, STAGE_ASSIGNMENT,
+    STATE_STAGE_INIT, TRIGGER_ENUM_LINE,
+    WorkflowSourceTestCase,
+)
+
+# A real crash message from run 20260825-scope-ceiling, and the LONGEST stage
+# text the fallback can interpolate (the no-dispatch phrase, longer than any
+# role name), so the render check below measures the worst realistic case.
+SAMPLE_MESSAGE = "Cannot read properties of undefined (reading 'head')"
+LONGEST_STAGE = "none (the crash happened before any agent was dispatched)"
+
+
+class TestTheCrashRecordNamesTheLastDispatchedStage(WorkflowSourceTestCase):
+    """A crash record carrying only an exception string sent run
+    20260825-scope-ceiling's controller looking for a budget problem. The
+    cheapest honest signal is the LAST DISPATCHED role - state.stage is
+    never cleared and dispatch() may fan out via parallel(), so it is not
+    a per-throw stage and the record must not claim to be one."""
+
+    def test_slice_state_initialises_a_stage_field(self):
+        init = self.between("function initSliceState(slice) {", "function doneResult(")
+        self.assertIn(STATE_STAGE_INIT, init)
+
+    def test_dispatch_records_the_role_only_after_the_guards_pass(self):
+        # A cap or token-floor rejection must not advance state.stage to a
+        # role that never dispatched, so the assignment follows guard().
+        fn = self.between(
+            "async function dispatch(slice, state, role, prompt, opts) {",
+            "// ── The slice pipeline")
+        self.assertIn(STAGE_ASSIGNMENT, fn)
+        self.assertLess(fn.index(DISPATCH_GUARD_CALL), fn.index(STAGE_ASSIGNMENT))
+
+
+class TestCrashesAreClassifiedAsInternalError(WorkflowSourceTestCase):
+    """Regression, run 20260825-scope-ceiling: the catch-all relabelled every
+    unclassified JS exception as `budget-exhausted` 'wave interrupted', so a
+    TypeError read as a resource limit and the controller spent ~85 and ~76
+    minutes diagnosing in the wrong direction (the HUMAN answered both in
+    ~1 min - the cost was misdirected diagnosis, not human waiting). The
+    catch-all now says machine failure, names the last dispatched stage, and offers
+    controller actions instead of 'raise budget/caps'."""
+
+    def crash_fallback(self):
+        return self.between(
+            "function runSliceError(slice, state, e) {",
+            "async function runSlice(slice) {")
+
+    def test_the_catch_all_emits_internal_error_not_budget_exhausted(self):
+        fallback = self.crash_fallback()
+        self.assertIn(CRASH_TRIGGER, fallback)
+        self.assertNotIn(GUARD_BUDGET_TRIGGER, fallback)
+
+    def test_a_classified_throw_still_passes_through_unchanged(self):
+        # The two structural guards throw {escRecord} with their own
+        # budget-exhausted record; reclassifying those would be a regression.
+        self.assertIn(CRASH_CLASSIFIED_PASSTHROUGH, self.crash_fallback())
+
+    def test_the_crash_record_names_the_last_dispatched_stage_without_overclaiming(self):
+        fallback = self.crash_fallback()
+        self.assertIn(CRASH_STAGE_FALLBACK, fallback)
+        self.assertIn(CRASH_STAGE_CONTEXT, fallback)
+        self.assertIn(CRASH_STAGE_PRECISION, fallback)
+        self.assertNotIn(CRASH_STAGE_OVERCLAIM, fallback)
+
+    def test_the_crash_record_carries_the_real_exception_text(self):
+        self.assertIn("String((e && e.message) || e)", self.crash_fallback())
+
+    def test_the_crash_record_claims_only_what_the_code_can_prove(self):
+        # The fallback catches EVERY throw without an escRecord, which includes
+        # host- and agent-layer resource failures that never reach guard(): a
+        # rejected agent(...) promise on a hard token or rate limit, or a throw
+        # from budget.remaining() itself. Asserting "bug, NOT a budget limit"
+        # would be the same unprovable assertion as the "budget" label this
+        # trigger replaced, just pointing the other way.
+        fallback = self.crash_fallback()
+        self.assertNotIn(CRASH_CAUSE_OVERCLAIM, fallback)
+        self.assertNotIn(CRASH_BUDGET_DENIAL_OVERCLAIM, fallback)
+        self.assertIn(CRASH_CLASSIFICATION_SENTENCE, fallback)
+        self.assertIn(CRASH_HOST_LAYER_CAVEAT, fallback)
+
+    def test_the_record_claims_only_that_neither_guard_raised_a_record(self):
+        # A fourth instance of the same pattern, one level subtler:
+        # `budget.remaining()` is called INSIDE the token-floor guard, so a
+        # throw from there ORIGINATES in a guard and still arrives with no
+        # escRecord. All the escRecord check proves is that neither guard
+        # RAISED its record - never that the crash came from outside them.
+        fallback = self.crash_fallback()
+        self.assertIn(CRASH_CLASSIFICATION_SENTENCE, fallback)
+        self.assertNotIn(CRASH_GUARD_ORIGIN_OVERCLAIM, fallback)
+
+    def test_the_title_is_grammatical_when_no_agent_was_dispatched(self):
+        # This title is an escalations.md heading and the dashboard label for
+        # the crash shape with the LEAST operator context; interpolating the
+        # no-dispatch fallback phrase after "after" rendered as "slice crashed
+        # after before any agent was dispatched".
+        fallback = self.crash_fallback()
+        self.assertIn(CRASH_TITLE_BRANCH, fallback)
+        self.assertNotIn(CRASH_TITLE_UNGRAMMATICAL, fallback)
+
+    def test_every_option_says_the_controller_must_act_on_it(self):
+        # internal-error is not in ANSWERABLE_TRIGGERS and the controller's
+        # step 7 re-dispatches every non-DONE slice, so nothing in the loop
+        # enforces skip or stop. Each detail says whose job it is.
+        fallback = self.crash_fallback()
+        self.assertEqual(fallback.count(CRASH_OPTION_CONTROLLER_ACTS), 3)
+        self.assertEqual(fallback.count("recommended: true"), 1)
+        self.assertLess(
+            fallback.index(CRASH_OPTION_RETRY), fallback.index("recommended: true"))
+
+    def test_the_options_are_controller_actions_not_resource_requests(self):
+        fallback = self.crash_fallback()
+        self.assertIn(CRASH_OPTION_RETRY, fallback)
+        self.assertIn(CRASH_OPTION_SKIP, fallback)
+        self.assertIn(CRASH_OPTION_STOP, fallback)
+        self.assertNotIn("Raise budget/caps", fallback)
+
+    def test_the_structural_guards_keep_their_budget_exhausted_wording(self):
+        guard = self.between(
+            "function guard(slice, state) {", "async function dispatch(")
+        self.assertIn("agent cap reached", guard)
+        self.assertIn("token budget exhausted", guard)
+        self.assertEqual(guard.count(GUARD_BUDGET_TRIGGER), 2)
+
+    def test_internal_error_is_not_injected_into_any_prompt(self):
+        # Mirror of test_budget_exhausted_is_still_not_injected_anywhere: a
+        # crash answer is a controller action (retry / skip / stop), so there
+        # is nothing for an agent prompt to apply. It is deliberately NOT in
+        # ANSWERABLE_TRIGGERS.
+        self.assertNotIn("answerFor(slice, 'internal-error')", self.src)
+        self.assertNotIn("internal-error", str(ANSWERABLE_TRIGGERS))
+
+    def test_the_real_exception_text_leads_the_context_not_the_boilerplate(self):
+        fallback = self.crash_fallback()
+        error_at = fallback.index(CRASH_ERROR_FIRST)
+        stage_at = fallback.index(CRASH_STAGE_CONTEXT)
+        prose_at = fallback.index(CRASH_CLASSIFICATION_SENTENCE)
+        self.assertLess(error_at, stage_at)
+        self.assertLess(stage_at, prose_at)
+
+    def crash_context(self):
+        """The shipped context template literal, backticks stripped."""
+        fallback = self.crash_fallback()
+        start = fallback.index(CRASH_ERROR_FIRST)
+        return fallback[start + 1:fallback.index("`,", start)]
+
+    def rendered_crash_context(self, message, stage_text):
+        """The context as run_state.render_escalation() would render it."""
+        filled = self.crash_context().replace(CRASH_ERROR_EXPR, message)
+        filled = filled.replace("${stageText}", stage_text)
+        filled = filled.replace("${state.tasksCompleted}", "2")
+        return " ".join(filled.split())[:CRASH_CONTEXT_RENDER_LIMIT - 1]
+
+    def test_the_stage_attribution_survives_the_400_char_context_render(self):
+        # run_state.render_escalation() renders "- Context: %s" through
+        # _one_line(..., 400), so anything past 400 collapsed characters never
+        # reaches escalations.md - which is also the corpus a later run's
+        # escalation-gate precedent check reads. The stage attribution is this
+        # record's headline diagnostic and the title asserts it, so it and its
+        # caveat must sit inside that budget, ahead of the fixed prose.
+        rendered = self.rendered_crash_context(SAMPLE_MESSAGE, LONGEST_STAGE)
+        attribution = CRASH_STAGE_CONTEXT.replace("${stageText}", LONGEST_STAGE)
+        self.assertIn(SAMPLE_MESSAGE, rendered)
+        self.assertIn(attribution, rendered)
+        self.assertIn(CRASH_STAGE_CAVEAT, rendered)
+
+    def test_a_lost_slice_is_an_internal_error_too(self):
+        # parallel() resolved the thunk to null: the slice died with no result
+        # at all, outside runSlice's try/catch. Same one classification, per
+        # the run's human-decided single-value constraint; the honest 'slice
+        # lost' title and its own question are kept.
+        wave_entry = self.between(
+            "const results = await parallel(", "log(`wave ")
+        self.assertIn(SLICE_LOST_RECORD, wave_entry)
+        self.assertIn("Re-run the wave to retry this slice?", wave_entry)
+        self.assertNotIn("'budget-exhausted'", wave_entry)
+
+    def test_the_lost_slice_record_denies_no_cause_it_cannot_prove(self):
+        # Same rule as the crash record, third instance of the pattern: a
+        # thunk that resolved to null says nothing about WHY, so asserting
+        # "Not a resource limit" is as unprovable as the "budget" label this
+        # trigger replaced. A host- or agent-layer rejection dies this way too.
+        wave_entry = self.between(
+            "const results = await parallel(", "log(`wave ")
+        self.assertNotIn(SLICE_LOST_CAUSE_DENIAL, wave_entry)
+        self.assertIn(CRASH_HOST_LAYER_CAVEAT, wave_entry)
+
+    def test_the_lost_slice_record_claims_only_that_no_guard_record_came_back(self):
+        # Fifth instance, and the sibling of the crash record's: a guard that
+        # "fired" asserts its CHECK never ran, which a null result cannot show.
+        # A throw from inside `budget.remaining()` ORIGINATES in the token-floor
+        # guard and still arrives with no escRecord, so both records may claim
+        # only that no guard RAISED one. Forbidden across the whole source so
+        # neither record can reintroduce it.
+        wave_entry = self.between(
+            "const results = await parallel(", "log(`wave ")
+        self.assertIn(SLICE_LOST_GUARD_PROVABLE, wave_entry)
+        self.assertIn(SLICE_LOST_CAUSE_UNKNOWN, wave_entry)
+        self.assertNotIn(GUARD_FIRED_OVERCLAIM, self.src)
+
+
+class TestTheTriggerEnumAgreesAcrossAllFiveHomes(WorkflowSourceTestCase):
+    """The enum has five homes and no test held them against each other.
+    `run_state.persist_slice` validates the whole SliceResult BEFORE it writes
+    anything and raises on an unrecognised trigger, so a value missing from one
+    tuple costs an affected slice its sidecar, its events and its report - not
+    a mislabelled field. A one-home edit would otherwise stay fully green."""
+
+    def triggers(self):
+        return run_state.ESCALATION_TRIGGERS
+
+    def test_the_three_python_tuples_are_identical(self):
+        self.assertEqual(run_metrics.ESCALATION_TRIGGERS, self.triggers())
+        self.assertEqual(dashboard_server.ESCALATION_TRIGGERS, self.triggers())
+
+    def test_the_workflow_enum_carries_exactly_those_values_in_order(self):
+        enum_line = self.line_containing(TRIGGER_ENUM_LINE)
+        self.assertEqual(tuple(re.findall(r"'([^']+)'", enum_line)),
+            self.triggers())
+
+
+if __name__ == "__main__":  # pragma: no cover
+    unittest.main()
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_scope.py b/plugins/spec-loop/scripts/test_slice_wave_contract_scope.py
index daf4666..01bb619 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_scope.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_scope.py
@@ -3,11 +3,13 @@
 ceiling threaded into `packet()`.
 
 See `slice_wave_contract_base.py` for the module-wide rationale, and
 `test_slice_wave_contract.py` for the sibling module covering guarded
 task-result reads, quality-gate-block answer injection, and the
-record-only `over_scope` critique field. Split purely to keep each
+record-only `over_scope` critique field (with
+`test_slice_wave_contract_crash.py` covering `internal-error`). Split
+purely to keep each
 module's whole-file `class_lines` under the quality gate's 300-line
 threshold; no test here depends on anything in the sibling.
 
 Usage:
     python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_slice_wave_contract_scope.py'
@@ -247,12 +249,14 @@ class TestTheRunScopeCeilingReachesEveryAgent(WorkflowSourceTestCase):
 
     def test_the_read_goes_through_the_type_safe_helper_not_a_bare_field_access(self):
         # Regression: `(CTX.scope_ceiling || []).length` was null-safe but not
         # type-safe - truthy for a non-empty STRING too, and the very next
         # read (`.map(...)`) is undefined on a string, throwing a TypeError
-        # that the catch-all mislabels as a budget escalation. packet() must
-        # never touch `CTX.scope_ceiling` directly; only the helper may.
+        # that the catch-all now classifies as 'internal-error' - before crash
+        # classification such errors were mislabeled as a budget escalation.
+        # packet() must never touch `CTX.scope_ceiling` directly; only the
+        # helper may.
         packet = self.between(PACKET_START, PACKET_END)
         self.assertNotIn("CTX.scope_ceiling", packet)
         self.assertIn(SCOPE_CEILING_READ, packet)
         helper = self.between(SCOPE_CEILING_HELPER, HELPER_END)
         self.assertIn("Array.isArray(raw)", helper)
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index bcc2293..c3773db 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -67,18 +67,23 @@ Do not act. Return an `EscalationRecord` and let the controller batch it:
    to avoid this.
 
 When uncertain whether something is "material": if a reasonable reviewer could reject the slice
 over it, it is material → surface it.
 
-The enum lives in `slice-wave.workflow.js` (`ESCALATION.trigger`). Two things that are
+The enum lives in `slice-wave.workflow.js` (`ESCALATION.trigger`). Three things that are
 deliberately NOT judgment triggers, and must never be turned into one: `budget-exhausted` (the
-workflow's guard emits it when a structural cap is hit — agent cap, stage token floor, lost
-slice; it asks for a resource, not a decision) and the council's **over-scope flag**
-(`critique.over_scope.flag`). The flag is a record: it is carried into the `council-verdict`
-payload and the slice sidecar with its reason, and it raises no escalation, changes no verdict,
-suppresses no split, and blocks nothing. There are exactly five triggers; an over-scope flag is
-not a sixth.
+workflow's guard emits it when a structural cap is hit — agent cap, stage token floor; it asks for a
+resource, not a decision), `internal-error` (an unhandled exception aborted a slice, or a slice
+returned no result at all; the exception record carries the real exception text together with the
+last stage/role dispatched before the failure, which is the most recent dispatch rather than a
+per-throw stage — the lost-slice record carries neither, having nothing to carry, and says
+so. This trigger reports a machine failure and asks the controller to retry, skip, or stop
+the run, and no agent prompt can apply such an answer, so the trigger is never answerable by
+re-dispatching an agent), and the council's **over-scope flag** (`critique.over_scope.flag`).
+The flag is a record: it is carried into the `council-verdict` payload and the slice sidecar with
+its reason, and it raises no escalation, changes no verdict, suppresses no split, and blocks
+nothing. There are exactly five JUDGMENT triggers; an over-scope flag is not a sixth.
 
 ### Precedent check (before returning any SURFACE escalation)
 
 Prior runs' human answers are settled decisions — check them before asking a question the human
 may have already answered. Search prior runs (excluding this one): answered escalation records
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index 73c9c99..f30341c 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -35,11 +35,11 @@ const BUDGET_STAGE_FLOOR = 60_000 // skip-and-escalate below this remaining budg
 // ── Schemas ──────────────────────────────────────────────────────────────────
 
 const ESCALATION = {
   type: 'object', additionalProperties: false,
   properties: {
-    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'budget-exhausted'] },
+    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'budget-exhausted', 'internal-error'] },
     title: { type: 'string' }, context: { type: 'string' }, question: { type: 'string' },
     options: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { label: { type: 'string' }, detail: { type: 'string' }, recommended: { type: 'boolean' } }, required: ['label', 'detail'] } },
   },
   required: ['trigger', 'title', 'context', 'question', 'options'],
 }
@@ -427,10 +427,14 @@ function guard(slice, state) {
     throw { escRecord: esc(slice, 'budget-exhausted', 'token budget exhausted', `Wave budget remaining ${Math.round(budget.remaining() / 1000)}k is below the ${BUDGET_STAGE_FLOOR / 1000}k stage floor.`, 'Raise the budget and resume, accept committed work as-is, or drop the slice?', []) }
 }
 
 async function dispatch(slice, state, role, prompt, opts) {
   guard(slice, state)
+  // Last dispatch STARTED, not a per-throw stage: never cleared, and
+  // concurrent fan-outs overwrite each other. After guard() so a cap or
+  // token-floor rejection cannot advance it to a role that never ran.
+  state.stage = role
   state.agentsUsed++
   const r = await agent(prompt, { ...opts, label: `${slice.id}:${role}`, phase: `wave ${A.wave_index}` })
   state.events.push({ scope: slice.id, type: 'agent-dispatch', payload: { role, model: opts.model || 'inherit', effort: opts.effort || null, agent_type: opts.agentType || null } })
   return r // null on user-skip/terminal error — callers fail closed
 }
@@ -447,11 +451,11 @@ async function dispatch(slice, state, role, prompt, opts) {
 
 const TASK_LANE = { transcribe: { model: 'haiku', effort: 'low' }, standard: { model: 'sonnet', effort: 'medium' }, judgment: { model: 'inherit', effort: 'high' } }
 
 function initSliceState(slice) {
   return {
-    agentsUsed: 0, events: [], escalations: [],
+    agentsUsed: 0, stage: null, events: [], escalations: [],
     review_tier: Math.max(slice.risk_tier, CTX.thorough ? Math.min(slice.risk_tier + 1, 3) : slice.risk_tier),
     critique: { verdict: 'SKIPPED', concerns: 0 },
     commits: { base: slice.base_sha, head: null },
     tasksCompleted: 0, implConcerns: [], deferred: [],
     review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
@@ -631,17 +635,17 @@ async function runTask(slice, state, plan, task) {
   if (taskNeedsRetry(r))
     return { stop: escalated(slice, state, esc(slice, 'ambiguity', `task ${task.id} blocked`, taskBlockReason(r), `Task "${task.title}" cannot proceed. How should it resolve?`, [])) }
   state.tasksCompleted++
   // TASK_RESULT requires only status/touched_files/concerns/deviations, so a
   // task that legitimately changed nothing returns DONE with `commits`
-  // absent. Reading it unguarded threw a TypeError that the catch-all below
-  // re-labelled as a budget-exhausted 'wave interrupted' — run
-  // 20260825-scope-ceiling lost a wave to it after all five tasks had
-  // already committed. Guarded the way the fix and debug-fix sites already
-  // guard the identical access; `head` keeps its previous value, so a slice
-  // where NO task committed still leaves it null and falls into the 'plan
-  // produced no commits' escalation below.
+  // absent. Reading it unguarded threw a TypeError that would now be
+  // classified as an 'internal-error' by the catch-all; run 20260825-scope-
+  // ceiling lost a wave to this defect before crash classification was added.
+  // Guarded the way the fix and debug-fix sites already guard the identical
+  // access; `head` keeps its previous value, so a slice where NO task
+  // committed still leaves it null and falls into the 'plan produced no commits'
+  // escalation below.
   mergeTaskCommits(state, r)
   state.implConcerns.push(...(r.concerns || []), ...(r.deviations || []).map(d => `deviation: ${d}`))
   return { touched: r.touched_files || [] }
 }
 
@@ -849,13 +853,50 @@ async function runStages(slice, state) {
 
   await maybePolish(slice, state)
   return stageVerify(slice, state, plan)
 }
 
+// An unclassified throw is a MACHINE failure, not a judgment call, and the
+// record asserts only the cause the code can PROVE. The two structural guards
+// (agent cap, stage token floor) throw {escRecord} with their own
+// budget-exhausted record and are handled on the first line below, so neither
+// of them RAISED the record that reached here -- which is ALL that check
+// proves, and all the record claims. It does not prove the crash originated
+// outside a guard, let alone outside a resource limit: budget.remaining() is
+// called inside the token-floor guard itself, so a throw from in there starts
+// in a guard and still arrives with no escRecord, and a rejected agent(...)
+// promise on a hard token or rate limit lands here the same way. Run
+// 20260825-scope-ceiling showed the cost of a mislabelled crash is misdirected
+// DIAGNOSIS, and asserting "bug, NOT a budget limit" would be exactly as
+// unprovable as the "budget" label it replaced, just aimed the other way, so
+// the record names both possibilities and leans on the exception text instead.
+// It names the LAST DISPATCHED stage: state.stage is the most recent dispatch,
+// not a per-throw stage (it is never cleared, and concurrent fan-outs overwrite
+// it), so the record says "after", not "in", and says so explicitly; the title
+// drops "after" entirely when no agent was ever dispatched, which would
+// otherwise read "crashed after before any agent was dispatched". Context ORDER
+// is load-bearing: render_escalation() (run_state.py) renders the context
+// through _one_line(..., 400), so only the first 400 collapsed characters reach
+// escalations.md -- also the corpus a later run's escalation-gate precedent
+// check reads. Both VARIABLE diagnostics (the exception text, then the stage
+// attribution the title asserts) therefore lead, each with a one-clause caveat,
+// and the fixed classification prose follows them, where truncation costs
+// boilerplate instead of evidence. Retry is deliberately a
+// human/controller decision: internal-error is not in ANSWERABLE_TRIGGERS and
+// the loop implements no automatic retry, skip, or stop, so each option's
+// detail names the CONTROLLER as what applies it.
 function runSliceError(slice, state, e) {
   if (e && e.escRecord) return escalated(slice, state, e.escRecord)
-  return escalated(slice, state, esc(slice, 'budget-exhausted', 'wave interrupted', String((e && e.message) || e), 'The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?', []))
+  const stage = state.stage
+  const stageText = stage || 'none (the crash happened before any agent was dispatched)'
+  const title = stage ? `slice crashed after ${stage}` : 'slice crashed before any agent was dispatched'
+  return escalated(slice, state, esc(slice, 'internal-error', title,
+    `Error: ${String((e && e.message) || e)}. Last stage/role dispatched before the failure: ${stageText} — the most recent dispatch, not a per-throw stage, so a starting point, not a culprit. Cause unknown: neither structural guard raised its escalation record, and that is all the check one line above proves — the stage token floor calls budget.remaining() itself, so a throw from inside a guard reaches here with no record either. It may be a loop or agent-contract bug, and it may equally be a host- or agent-layer resource failure (a rejected agent call on a hard token or rate limit, say) — the exception text above is the evidence, not this classification. state.stage is never cleared and concurrent fan-outs overwrite it, so the failure may also have happened after that role finished, or in a sibling of it. ${state.tasksCompleted} task(s) had already completed and any committed work is on the branch.`,
+    'Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?',
+    [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice, keeping the committed work on its branch.', recommended: true },
+     { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
+     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.' }]))
 }
 
 async function runSlice(slice) {
   const state = initSliceState(slice)
   try {
@@ -873,10 +914,10 @@ const out = results.map((r, i) => r || {
   schema_version: 2, id: A.slices[i].id, status: 'ESCALATED', branch: A.slices[i].branch,
   commits: { base: A.slices[i].base_sha, head: null }, risk_tier: A.slices[i].risk_tier,
   review_tier: A.slices[i].risk_tier, critique: { verdict: 'SKIPPED', concerns: 0 },
   tasks_completed: 0, review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
   tests: null, quality: { status: 'SKIPPED', detail: 'slice never ran' },
-  escalations: [esc(A.slices[i], 'budget-exhausted', 'slice lost', 'The slice function returned no result (terminal failure).', 'Re-run the wave to retry this slice?', [])],
+  escalations: [esc(A.slices[i], 'internal-error', 'slice lost', 'The slice function returned no result (terminal failure) — it died outside runSlice\'s try/catch. Neither structural guard raised its escalation record — each raises budget-exhausted with an escRecord runSlice would have returned — and that is all a null result proves, not that no guard check ran. A host- or agent-layer resource failure dies the same silent way, so the cause is unknown here.', 'Re-run the wave to retry this slice?', [])],
   agents_used: 0, wave: A.wave_index, events: [],
 })
 log(`wave ${A.wave_index} collected: ${out.map(r => `${r.id}=${r.status}`).join(' ')}`)
 return { run_id: A.run_id, wave_index: A.wave_index, results: out }
diff --git a/scripts/coverage_omit.txt b/scripts/coverage_omit.txt
index 0c4e51a..78268c7 100644
--- a/scripts/coverage_omit.txt
+++ b/scripts/coverage_omit.txt
@@ -33,10 +33,10 @@ scripts/dashboard_server.py:1645-1646    # __main__ entry shim (if __name__/sys.
 scripts/knowledge_graph.py:1211-1212     # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/pr_resolver.py:488-489           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/quality_gate.py:1118-1119        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/release.py:194-195               # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/review_package.py:131-132        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/run_metrics.py:2174-2175         # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/run_state.py:1103-1104           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/run_metrics.py:2175-2176         # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/run_state.py:1104-1105           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/spec_loop_guard.py:250-251       # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/validate_marketplace.py:417-418  # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/worktrees.py:385-386             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
