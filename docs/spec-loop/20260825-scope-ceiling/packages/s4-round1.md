# Review package: f2cc7ece1fd3a6603b2bff911611c8d1eb72e787..HEAD  (context: -U5)

## Commits
2381156 docs(migration): the weighted scope lane in the v1-to-v2 council delta
9773d42 docs: note the scope ceiling and the record-only scope judgement in the root README
bc10018 docs(readme): weighted scope lane, the run-level ceiling, and an accurate script count
23ee18b docs(changelog): state the honesty framing, the deferred defects, and the verifiability ceiling
68b8ebf docs(changelog): record the fail-closed over-scope validation, the scope note, and the null-honest counters
fb305bd docs(changelog): correct the scope-ceiling and gate-answer bullets against the shipped workflow

## Files changed
 CHANGELOG.md                                      | 79 +++++++++++++++++++++--
 README.md                                         |  8 +++
 plugins/spec-loop/README.md                       | 19 +++++-
 plugins/spec-loop/references/migration-from-v1.md | 17 +++--
 4 files changed, 111 insertions(+), 12 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
11,
17
],
[
29,
50
],
[
58,
102
]
],
"README.md": [
[
36,
43
]
],
"plugins/spec-loop/README.md": [
[
50,
50
],
[
71,
79
],
[
138,
140
],
[
152,
152
],
[
154,
155
]
],
"plugins/spec-loop/references/migration-from-v1.md": [
[
29,
41
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index e9fded6..e1f3399 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -6,12 +6,17 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 
 ### Added
-- **Run-level scope ceiling** — an optional `scope_ceiling` list in `dag.json`, threaded
-  through `ctx` and into every agent's packet as a binding "do NOT build these" block.
+- **Run-level scope ceiling** — an optional `scope_ceiling` list in `dag.json` (validated
+  only when present; a run without one stays fully valid and mutable), threaded through
+  `ctx` and prefixed to **every** agent prompt by the wave's shared packet as a binding
+  "do NOT build these" block. The read is type-safe, not merely null-safe: an array passes
+  through, a lone non-empty string is coerced to a one-element list (a realistic return
+  from an LLM controller populating `ctx` from prose), and any other non-array value reads
+  as absent rather than throwing. Shape: `references/run-state-v2.md`.
 - **Record-only `critique.over_scope`** — an optional `{flag, reason}` field on the
   council verdict contract, owned by plan-critic's weighted scope lane. It is carried
   into the `council-verdict` event and the slice sidecar untouched by any control-flow
   branch: it never blocks, never suppresses a split, never raises an objection, and is
   never a finding.
@@ -19,20 +24,84 @@ All notable changes to the spec-loop plugin are documented here. The format is
   concern now emits its own `deferred` event (`{summary, source: "plan-critique"}`, plus a
   bare-boolean `over_scope: true` marker when applicable), read by the reviewer as advisory
   context only — never a findings filter.
 - **Weighted scope lane on plan-critic** — plan-critic's existing Scope mandate now owns the
   over-scope record; no new agent, no change to any panel size or objection threshold.
+- **Fail-closed sidecar validation and honest rendering of the scope record** — a present
+  `critique.over_scope` must carry a real boolean `flag` and a string-or-null `reason`; a
+  malformed record invalidates the whole sidecar (`persist_slice` raises and writes nothing)
+  rather than being quietly ignored. Absent and explicit `null` are both valid and mean "no
+  scope judgement was recorded" — which is a different claim from `flag: false`, and the two
+  render differently. One shared renderer produces four distinct human outcomes and collapses
+  none of them into another: nothing at all when no judgement was recorded, `scope: clean` for
+  `flag: false`, `SCOPE-FLAGGED` plus the reason when one was given, and `scope: unreadable`
+  when a present record's own shape cannot be trusted. The decisions-log verdict line and the
+  slice report's `Iron Council` value share that renderer, so the two human surfaces cannot
+  disagree; a `deferred` event whose payload marks `over_scope: true` renders with a `SCOPE `
+  prefix in the decisions log.
+- **Null-honest scope counters in `run_metrics.py`** — `safety.over_scope_deferrals` counts
+  `deferred` events carrying that boolean marker, and therefore lives at the `safety` top
+  level beside `deferrals_total`, **not** inside `safety.council`, whose every other key
+  shares the council-verdict population. Both counters are null-honest:
+  `safety.council.over_scope_flags` counts flagged `council-verdict` payloads and stays `null`
+  when no payload carried a boolean flag, because "no payload recorded a scope judgement" is
+  not evidence that nothing was over scope — and a malformed record counts as no record rather
+  than as a clean one. The legacy v1-prose channel reports both as `null`; it never carried a
+  scope judgement. Both feed reporting only: neither feeds a threshold, a gate or a blocking
+  decision.
 
 ### Fixed
 - **Wave-aborting unguarded `commits` read** — a task that legitimately committed nothing
   returns `DONE` with `commits` absent (not required by `TASK_RESULT`); the Stage-T loop's
   unguarded `r.commits.head` read threw a `TypeError` that the catch-all mislabelled as a
   budget-exhausted "wave interrupted" escalation. The read is now guarded the way the
   fix/debug-fix sites already guard it.
-- **Missing `quality-gate-block` answer injection** — `fixPrompt` and `verifyPrompt` had no
-  `answerFor(slice, 'quality-gate-block')` site, so a human's answer to a quality-gate
-  escalation could not reach the re-dispatched prompt.
+- **Missing `quality-gate-block` answer injection** — no prompt builder had a site for a
+  human's answer to a quality-gate escalation, so the answer could not reach the
+  re-dispatched slice. `fixPrompt` now carries it through `answerFor` ("apply it, do not
+  re-raise"); `verifyPrompt` carries it through a new context-only sibling `answerContext`,
+  which shows the answer without instructing a transcription-only reporter to change what
+  it reports — the suite result and `quality.summary_pass`/`violations` stay verbatim from
+  the real output.
+
+### Scope and limits of this change
+
+Read this before reading "Added" as "scope creep no longer happens". Of everything added
+above, exactly one thing reduces the effort spent expanding scope: the **weighted scope lane
+on `plan-critic`**, which makes the critic look at the run's ceiling and the slice goal and
+say so. The ceiling, the `over_scope` record, the `deferred` channel and both counters do not
+prevent anything — they build durable **recording**, and non-re-admission only in the sense
+that recording buys: a scope judgement is written down with its reason, survives into
+`events.jsonl`, the sidecar and `decisions-log.md`, and is visible to the reviewer and the
+human, so deferred work cannot quietly come back unremarked. Nothing stops it coming back.
+The record blocks nothing, filters no finding, suppresses no split and raises no objection. Work the council judges out of scope and asks
+not to be built is a `defer`-hinted concern, logged as a `deferred` event; the record itself
+is explicitly "flag it and still build it" when the goal genuinely asks for it.
+
+The mechanism was exercised on live input by the run that added it, which is the strongest
+available evidence for both halves of that claim. The two workflow defects fixed above were
+themselves an approved, recorded scope increase. In the same run the council found two more
+defects of the same class in `workflows/slice-wave.workflow.js` — an unguarded
+`plan.escalation.*` read on the ESCALATE branch (:479), which turns a planner returning
+`ESCALATE` with no `escalation` object into the same mislabelled "wave interrupted"
+`TypeError`, and a `plan.split` pass-through on the SPLIT branch (:478) that hands `undefined`
+downstream to fail sidecar validation there instead. Both are one-line guards; both were
+**deferred rather than fixed**, because they fell outside the approved increase. They are
+logged with `file:line` evidence and are deliberately still unbuilt. That is the mechanism
+working as designed, and it is also the plainest possible demonstration that recording a
+scope judgement is not the same as acting on it.
+
+Verifiability ceiling: nothing this change added to `workflows/slice-wave.workflow.js` has
+ever been executed. The loop resolves its workflow from the installed plugin cache, so the
+merged file takes effect only after a plugin reinstall — the run that wrote it ran a patched
+copy of that cache, not this file. That JS carries no coverage gate (`measure_coverage.py`
+measures Python only). Its guarantees rest on a real `node` parse of the source plus
+source-text assertions that prove a guard, a helper call or a schema field is *present*, and
+on three pure helpers (`scopeRecord`, `deferralEvents`, `scopeCeilingList`) extracted from
+that source and executed under real `node` in isolation. Presence is not behaviour, and three
+pure helpers are not the pipeline — treat every runtime claim about the workflow in this entry
+as reviewed and asserted, not observed.
 
 ## [2.1.0] - 2026-08-10
 Runtime and trust fixes from the 2026-08-06/07 production-run analysis
 (Groundworks.Jobs): active runtime was ~3–5h for 3–5 slices, but one run read
 as 15h48m — 7.6h of it a silently-parked publish prompt, 2h20m a discarded
diff --git a/README.md b/README.md
index 0cd1b6b..1b88792 100644
--- a/README.md
+++ b/README.md
@@ -31,10 +31,18 @@ What did **not** change: the escalation-gate autonomy contract (five surface
 triggers, precedent check, one batched question per wave), single-branch
 integration with a guard hook, the scripted quality gate agents cannot weaken,
 knowledge-graph integration (v2 accretes onto the same vault nodes), and
 null-honest metrics.
 
+What 2.x adds on top: a run may declare a **scope ceiling** — things the run must not
+build — which is prefixed to every agent's prompt, and the council records its scope
+judgement in the run's events and sidecars with its reason intact. That record blocks
+nothing. Weighting the critic's scope lane is the only part of it that reduces
+scope-expansion effort; the ceiling and the record exist so a judgement is written down
+and cannot quietly come back, not so that scope creep stops happening. Details:
+`plugins/spec-loop/references/run-state-v2.md`.
+
 ## Install
 
 ```
 /plugin marketplace add z2297/spec-loop-2
 /plugin install spec-loop
diff --git a/plugins/spec-loop/README.md b/plugins/spec-loop/README.md
index 815e245..fec3e46 100644
--- a/plugins/spec-loop/README.md
+++ b/plugins/spec-loop/README.md
@@ -45,11 +45,11 @@ One Workflow invocation per wave (`workflows/slice-wave.workflow.js`). Per
 slice, in deterministic JS:
 
 | Stage | Who | Model / effort |
 |---|---|---|
 | Plan (+ right-size gate) | `slice-planner` | session / low |
-| Critique — Tier 2 | `plan-critic` (all five council mandates) | session / low |
+| Critique — Tier 2 | `plan-critic` (all five council mandates; the Scope lane is weighted and owns the over-scope record) | session / low |
 | Critique — Tier 3 | + `guardian` (risk-only SAFETY veto); `--thorough` adds `skeptic` | session / high |
 | Implement (sequential per task) | `implementer` | haiku / sonnet / session by task lane |
 | Review ∥ quality gate | `pr-reviewer` (two lanes at Tier 3) ∥ `verifier` running `quality_gate.py` | tier-scaled ∥ haiku |
 | Verify findings (Tier 3) | `finding-verifier` — ONE batched pass, CONFIRMED-by-default | sonnet / low |
 | Fix loop (≤2 rounds) | `implementer` in fix mode (refutation right) + `re-reviewer` | sonnet → session |
@@ -66,10 +66,19 @@ promoted deterministically when the implementation touches a `tier3_surfaces`
 glob (auth, migrations, security paths — configurable). An answered
 escalation re-invokes the wave with ONLY its non-terminal slices (merged work
 never re-enters) and the journal cache: the escalated slices' completed
 stages replay free where the cache holds; only the answered stage runs live.
 
+A run may also declare an optional run-level `scope_ceiling` — things this run must not
+build — which is prefixed verbatim to every agent's prompt. The council records a scope
+judgement against it as `critique.over_scope`, and that record is **record-only**: it
+blocks nothing, filters no finding, suppresses no split and raises no escalation trigger.
+The weighting on the critic's Scope lane is the only part of this that reduces
+scope-expansion effort; the ceiling and the record exist to make a judgement durable and
+readable, not to prevent the work. Contracts:
+`references/risk-tiers.md` and `references/run-state-v2.md`.
+
 ## Runtime expectations (Opus 5)
 
 Measured across real multi-slice runs (2026-08, .NET repo with a ~9,400-test
 suite): a slice lands in **~40–70 minutes all-in** — wave pipeline plus the
 controller's serial merge and integration suite — so a 3–5 slice run is a
@@ -124,10 +133,13 @@ Everything durable lives under `docs/spec-loop/<run-id>/` —
 committed `runbook.md`. Contract: `references/run-state-v2.md`. While a run's
 `.active` marker exists, `scripts/spec_loop_guard.py` (PreToolUse hook)
 blocks pushes, broad staging (`git add -A`), commits/merges on
 `main`/`master`, and quality-gate config edits. Markers, not vibes: the run
 ends when the human's publish choice is recorded.
+Work the council judged out of scope and asked not to be built is logged as its own
+`deferred` event and rendered into `decisions-log.md`; a malformed scope record fails the
+sidecar closed rather than reading as clean.
 
 ## Components
 
 - **Commands (7)**: spec-loop, review-pr, peer-review, quality-gate,
   knowledge-graph, dashboard, dashboard-serve.
@@ -135,13 +147,14 @@ ends when the human's publish choice is recorded.
 - **Agents (13)**: slice-planner, plan-critic, guardian, skeptic,
   implementer, pr-reviewer, finding-verifier, re-reviewer, simplifier,
   verifier, runbook-writer, peer-reviewer, slice-worker-fallback.
 - **Skills (5)**: escalation-gate, using-spec-loop, test-driven-development,
   systematic-debugging, verification-before-completion.
-- **Scripts (12 + tests)**: dag, worktrees, run_state, review_package,
+- **Scripts (11 runtime + tests)**: dag, worktrees, run_state, review_package,
   quality_gate, knowledge_graph, run_metrics, pr_resolver, spec_loop_guard,
-  dashboard_server, dashboard_launcher (+ dashboard_assets).
+  dashboard_server, dashboard_launcher (+ dashboard_assets, and the
+  `slice_wave_contract_base` test-support module).
 
 ## Migrating from v1
 
 Read `references/migration-from-v1.md`. Short version: theology unchanged,
 internals rebuilt; config namespace moved (first run offers import); v1 run
diff --git a/plugins/spec-loop/references/migration-from-v1.md b/plugins/spec-loop/references/migration-from-v1.md
index 3c63d19..c64ad6e 100644
--- a/plugins/spec-loop/references/migration-from-v1.md
+++ b/plugins/spec-loop/references/migration-from-v1.md
@@ -24,14 +24,23 @@ Loop bounds (replan ≤1, task retry ≤1, fix rounds ≤2, debug-fix ≤1) and
 (10/18/32 by review tier) are constants in that file rather than instructions an agent might drift
 from. Every LLM→LLM handoff is a schema-forced structured return.
 
 **Critics and reviewers consolidated.** v1's five Iron Council members are now three lanes on two
 agents used tier-scaled (`plan-critic` carries all five mandates; `guardian` and `skeptic` are the
-risk and premise lanes). v1's seven review-aspect specialists are one `pr-reviewer` that covers
-every lane in a single pass with per-aspect attestation — seven agents re-reading the same diff
-cost more than one reviewer thinking harder. Net: **13 agents, down from 22**, and **5 skills, down
-from 21** (the loop's own machinery is agents, one workflow, and reference files — not skills).
+risk and premise lanes). One of those five is weighted differently from v1: the **Scope** mandate
+now owns an over-scope record. Where v1's scope critique lived and died in prose, `plan-critic`
+reads the run's optional `scope_ceiling` out of its packet and returns
+`critique.over_scope: {flag, reason}` — a record, never a verdict. It raises no objection,
+suppresses no split, blocks nothing and is never a finding; it is carried with its reason into the
+`council-verdict` event and the slice sidecar so a human can read what the loop judged out of
+scope. The lever for work that should not be built is unchanged from v1's disposition hints: a
+`defer`-hinted concern, which v2 now also writes out as its own `deferred` event. No panel grew,
+no objection threshold moved, and no new agent was added. v1's seven review-aspect specialists are
+one `pr-reviewer` that covers every lane in a single pass with per-aspect attestation — seven
+agents re-reading the same diff cost more than one reviewer thinking harder. Net: **13 agents,
+down from 22**, and **5 skills, down from 21** (the loop's own machinery is agents, one workflow,
+and reference files — not skills).
 
 **Run state is structured.** v1 pinned line grammars in `decisions-log.md`, `escalations.md`, and
 `slice-*-agents.jsonl`, and metrics scraped them (plus Claude Code transcripts). v2's machine
 channels are `events.jsonl` (append-only, typed events) and one `slice-<id>-status.json` sidecar per
 slice, validated fail-closed on persist. The prose files are *rendered* from those objects for
