# Review package: b1a2d0d..284f9ab  (context: -U5)

## Commits
284f9ab slice-wave: keep stageFixLoop/runSliceError under the cognitive-complexity and nesting-depth thresholds
598e190 fix round: precise round-suffix docs, reduced complexity in merge_escalation_records/esc, and lower nesting in escalation-record tests

## Files changed
 plugins/spec-loop/agents/slice-worker-fallback.md  |  3 +-
 plugins/spec-loop/scripts/run_metrics.py           | 30 +++++++-----
 .../spec-loop/scripts/slice_wave_contract_base.py  |  2 +-
 plugins/spec-loop/scripts/test_run_metrics.py      | 55 +++++++++++++---------
 .../scripts/test_slice_wave_contract_crash.py      |  7 ++-
 plugins/spec-loop/skills/escalation-gate/SKILL.md  | 11 +++--
 plugins/spec-loop/workflows/slice-wave.workflow.js | 52 +++++++++++---------
 7 files changed, 95 insertions(+), 65 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/agents/slice-worker-fallback.md": [
[
155,
156
]
],
"plugins/spec-loop/scripts/run_metrics.py": [
[
467,
467
],
[
471,
487
]
],
"plugins/spec-loop/scripts/slice_wave_contract_base.py": [
[
176,
176
]
],
"plugins/spec-loop/scripts/test_run_metrics.py": [
[
344,
354
],
[
510,
513
],
[
522,
527
],
[
529,
534
],
[
537,
541
]
],
"plugins/spec-loop/scripts/test_slice_wave_contract_crash.py": [
[
176,
179
],
[
182,
182
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
145,
148
],
[
164,
166
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
284,
289
],
[
459,
459
],
[
461,
461
],
[
515,
515
],
[
517,
517
],
[
597,
597
],
[
685,
685
],
[
710,
710
],
[
807,
807
],
[
827,
827
],
[
862,
862
],
[
880,
880
],
[
940,
945
],
[
967,
971
],
[
973,
974
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/agents/slice-worker-fallback.md b/plugins/spec-loop/agents/slice-worker-fallback.md
index 564e1e9..706fd00 100644
--- a/plugins/spec-loop/agents/slice-worker-fallback.md
+++ b/plugins/spec-loop/agents/slice-worker-fallback.md
@@ -150,11 +150,12 @@ trusts the sidecar over anything you say, and an invalid one makes this slice un
 regardless of how the work went.
 
 ## Escalations
 
 Every escalation is an EscalationRecord in `escalations[]`: stable id `<slice-id>:<trigger>`,
-one of the seven triggers (`ambiguity`, `material-assumption`, `review-block`,
+plus `:<round>` from the second round of that trigger in that slice onward, one of the seven
+triggers (`ambiguity`, `material-assumption`, `review-block`,
 `council-objection`, `quality-gate-block`, `budget-exhausted`, `internal-error`), the context,
 the precise question, options with one marked `recommended`, and `if_unanswered`.
 Proceed-and-log stays the default — surface only genuine ambiguity or a material assumption
 touching behavior, public contracts, persisted data, security, or an external integration. A
 slice with any open escalation returns `ESCALATED`. `budget-exhausted` is only for the tier
diff --git a/plugins/spec-loop/scripts/run_metrics.py b/plugins/spec-loop/scripts/run_metrics.py
index 812a157..b4d17e3 100644
--- a/plugins/spec-loop/scripts/run_metrics.py
+++ b/plugins/spec-loop/scripts/run_metrics.py
@@ -462,25 +462,31 @@ def merge_escalation_records(from_events, from_sidecars):
     Sidecars are authoritative about a slice, but a run that escalated at
     intake has no sidecar at all, and an interrupted run may have events with
     no persisted sidecar yet — so neither channel alone is complete."""
     merged, order = {}, []
     for record in list(from_sidecars) + list(from_events):
-        key = record["id"]
-        if key not in merged:
-            order.append(key)
-            merged[key] = dict(record)
-            continue
-        existing = merged[key]
-        answered = "ANSWERED" in (existing["status"], record["status"])
-        existing.update({k: v for k, v in record.items() if v is not None})
-        # An answer recorded in either channel happened; a channel that only
-        # saw the open must not walk the escalation back to OPEN.
-        if answered:
-            existing["status"] = "ANSWERED"
+        _fold_escalation_record_into(merged, order, record)
     return [merged[key] for key in order]
 
 
+def _fold_escalation_record_into(merged, order, record):
+    """Fold one escalation record into the accumulating ``merged``/``order``
+    pair, in place. A key seen for the first time is recorded verbatim and
+    its arrival order preserved; a repeat key is unioned onto the existing
+    entry, non-``None`` fields winning, with an answer recorded in either
+    channel never walked back to OPEN by the other."""
+    key = record["id"]
+    if key not in merged:
+        order.append(key)
+        merged[key] = dict(record)
+        return
+    existing = merged[key]
+    answered = "ANSWERED" in (existing["status"], record["status"])
+    existing.update({k: v for k, v in record.items() if v is not None})
+    existing["status"] = "ANSWERED" if answered else existing["status"]
+
+
 # ==========================================================================
 # pure core — dag.json / sidecars / runbook.md
 # ==========================================================================
 
 def parse_dag(obj):
diff --git a/plugins/spec-loop/scripts/slice_wave_contract_base.py b/plugins/spec-loop/scripts/slice_wave_contract_base.py
index aff3495..835f37c 100644
--- a/plugins/spec-loop/scripts/slice_wave_contract_base.py
+++ b/plugins/spec-loop/scripts/slice_wave_contract_base.py
@@ -171,11 +171,11 @@ CRASH_STAGE_CAVEAT = "so a starting point, not a culprit"
 # The mirror-image overclaim this module now forbids: asserting "bug, NOT a
 # budget limit" is as unprovable as the old "budget" assertion it replaced.
 CRASH_CAUSE_OVERCLAIM = "This is a loop or agent-contract bug"
 CRASH_BUDGET_DENIAL_OVERCLAIM = "NOT a cap or budget limit"
 GUARD_BUDGET_TRIGGER = "esc(slice, 'budget-exhausted',"
-SLICE_LOST_RECORD = "esc(A.slices[i], 'internal-error', 'slice lost',"
+SLICE_LOST_RECORD = "esc(A.slices[i], 'internal-error', {\n    title: 'slice lost',"
 # Third instance of the same overclaim pattern: a thunk resolved to null
 # proves nothing about the cause, so the lost-slice record must not deny one.
 SLICE_LOST_CAUSE_DENIAL = "Not a resource limit."
 # Fifth instance, and the sibling of CRASH_GUARD_ORIGIN_OVERCLAIM above: a
 # guard "firing" asserts its CHECK never ran, which neither record can know.
diff --git a/plugins/spec-loop/scripts/test_run_metrics.py b/plugins/spec-loop/scripts/test_run_metrics.py
index c36808d..5ba913e 100644
--- a/plugins/spec-loop/scripts/test_run_metrics.py
+++ b/plugins/spec-loop/scripts/test_run_metrics.py
@@ -339,10 +339,21 @@ def _events_without(*payload_keys):
         dict(obj, payload={k: v for k, v in obj["payload"].items()
                            if k not in dropped}))
         for obj in V2_EVENT_OBJECTS)
 
 
+def _escalation_record(**overrides):
+    """One escalation record as `merge_escalation_records` consumes it, with
+    the fields a round-2 `s1:internal-error` record shares held as defaults so
+    a test states only what makes it distinct."""
+    record = {"id": "s1:internal-error", "scope": "s1", "trigger": "internal-error",
+              "title": None, "status": "OPEN", "opened": "2026-07-30T10:00:00Z",
+              "answered_at": None}
+    record.update(overrides)
+    return record
+
+
 # ---------------------------------------------------------------------------
 # events.jsonl parsing
 # ---------------------------------------------------------------------------
 
 class EventsParseTests(unittest.TestCase):
@@ -494,44 +505,42 @@ class EscalationPairingTests(unittest.TestCase):
         self.assertEqual(metrics["safety"]["escalations"]["total"], 2)
         self.assertEqual(metrics["safety"]["escalations"]["basis"],
                          rm.BASIS_BOTH)
 
     def test_sidecar_answer_survives_an_events_channel_that_only_opened(self):
-        from_events = [{"id": "s1:x", "scope": "s1", "trigger": "ambiguity",
-                        "title": None, "status": "OPEN",
-                        "opened": "2026-07-30T10:00:00Z", "answered_at": None}]
-        from_sidecars = [{"id": "s1:x", "scope": "s1", "trigger": None,
-                          "title": "t", "status": "ANSWERED", "opened": None,
-                          "answered_at": "2026-07-30T10:05:00Z"}]
+        from_events = [_escalation_record(id="s1:x", trigger="ambiguity", title=None)]
+        from_sidecars = [_escalation_record(
+            id="s1:x", trigger=None, title="t", status="ANSWERED", opened=None,
+            answered_at="2026-07-30T10:05:00Z")]
         merged = rm.merge_escalation_records(from_events, from_sidecars)
         self.assertEqual(len(merged), 1)
         self.assertEqual(merged[0]["status"], "ANSWERED")
         self.assertEqual(merged[0]["answered_at"], "2026-07-30T10:05:00Z")
         self.assertEqual(merged[0]["opened"], "2026-07-30T10:00:00Z")
         self.assertEqual(merged[0]["trigger"], "ambiguity")
 
     def test_two_rounds_of_one_trigger_stay_two_records(self):
-        first = {"id": "s1:internal-error", "scope": "s1",
-                 "trigger": "internal-error", "title": "round one",
-                 "status": "ANSWERED", "opened": "2026-07-30T10:00:00Z",
-                 "answered_at": "2026-07-30T10:05:00Z"}
-        second = dict(first, id="s1:internal-error:2", title="round two",
-                      status="OPEN", answered_at=None)
+        first_id, second_id = "s1:internal-error", "s1:internal-error:2"
+        first = _escalation_record(
+            id=first_id, title="round one", status="ANSWERED",
+            answered_at="2026-07-30T10:05:00Z")
+        second = _escalation_record(
+            id=second_id, title="round two", status="OPEN", answered_at=None)
         merged = rm.merge_escalation_records([], [first, second])
-        self.assertEqual([r["id"] for r in merged],
-                         ["s1:internal-error", "s1:internal-error:2"])
-        self.assertEqual([r["title"] for r in merged],
-                         ["round one", "round two"])
-        self.assertEqual([r["status"] for r in merged], ["ANSWERED", "OPEN"])
+        ids = [r["id"] for r in merged]
+        titles = [r["title"] for r in merged]
+        statuses = [r["status"] for r in merged]
+        self.assertEqual(ids, [first_id, second_id])
+        self.assertEqual(titles, ["round one", "round two"])
+        self.assertEqual(statuses, ["ANSWERED", "OPEN"])
 
     def test_one_round_seen_in_both_channels_stays_one_record(self):
-        events = [{"id": "s1:internal-error:2", "scope": "s1",
-                   "trigger": "internal-error", "title": None, "status": "OPEN",
-                   "opened": "2026-07-30T10:00:00Z", "answered_at": None}]
-        sidecars = [{"id": "s1:internal-error:2", "scope": "s1",
-                     "trigger": None, "title": "round two", "status": "ANSWERED",
-                     "opened": None, "answered_at": "2026-07-30T10:05:00Z"}]
+        round_id = "s1:internal-error:2"
+        events = [_escalation_record(id=round_id, title=None, status="OPEN")]
+        sidecars = [_escalation_record(
+            id=round_id, trigger=None, title="round two", status="ANSWERED",
+            opened=None, answered_at="2026-07-30T10:05:00Z")]
         merged = rm.merge_escalation_records(events, sidecars)
         self.assertEqual(len(merged), 1)
         self.assertEqual(merged[0]["status"], "ANSWERED")
         self.assertEqual(merged[0]["title"], "round two")
 
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
index cf42db4..db27992 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract_crash.py
@@ -171,14 +171,17 @@ class TestCrashesAreClassifiedAsInternalError(WorkflowSourceTestCase):
         prose_at = fallback.index(CRASH_CLASSIFICATION_SENTENCE)
         self.assertLess(error_at, stage_at)
         self.assertLess(stage_at, prose_at)
 
     def crash_context(self):
-        """The shipped context template literal, backticks stripped."""
+        r"""The shipped context template literal, backticks stripped. The
+        literal is its own statement (`const context = \`...\``), so its
+        closing backtick is followed by a newline, not the trailing comma an
+        inline call argument would carry."""
         fallback = self.crash_fallback()
         start = fallback.index(CRASH_ERROR_FIRST)
-        return fallback[start + 1:fallback.index("`,", start)]
+        return fallback[start + 1:fallback.index("`\n", start)]
 
     def rendered_crash_context(self, message, stage_text):
         """The context as run_state.render_escalation() would render it."""
         filled = self.crash_context().replace(CRASH_ERROR_EXPR, message)
         filled = filled.replace("${stageText}", stage_text)
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index 600c373..5dc505d 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -140,12 +140,14 @@ human, so:
    `parallel()` keeps every independent slice running.
 2. The controller collects **all** open records at the **wave boundary**
    (`run_state.py open-escalations`), runs the precedent check on each, and surfaces everything that
    survives as ONE `AskUserQuestion` round — recommended default first.
 3. Answers are written back (`escalation-answered` events) and the wave is re-dispatched with
-   `answers["<slice-id>:<trigger>"]` filled in; completed stages replay from the workflow journal,
-   so only the answered stage runs live.
+   the answer keyed by the escalation's `id` verbatim (`answers["<slice-id>:<trigger>"]`, or
+   `answers["<slice-id>:<trigger>:<round>"]` from the second round of that trigger onward)
+   filled in; completed stages replay from the workflow journal, so only the answered stage
+   runs live.
 
 The wave boundary is the only seam where a human is asked anything — unchanged from v1; only the
 transport moved from prose files to structured returns.
 
 ## The escalation record
@@ -157,12 +159,13 @@ rendered from the records. Two rules the shape cannot enforce:
 - **Always include a recommended default.** Make the human's decision as cheap as possible
   (confirm vs. redirect). A record whose options are all equally weighted is unfinished.
 - **`context` explains why the loop cannot decide**, not merely what happened — the human reads it
   cold, alongside other questions.
 
-The `id` is `<slice-id>:<trigger>`, stable across resumes: that stability is what lets an answer be
-injected back into exactly the stage that raised it.
+The `id` is `<slice-id>:<trigger>`, plus `:<round>` from the second round of that trigger in that
+slice onward, stable across resumes: that stability is what lets an answer be injected back into
+exactly the stage that raised it.
 
 ## Violations of the contract
 
 - Asking the human something resolvable from the codebase, a convention, or a prior run's answered
   escalation (run the precedent check first).
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index db51db7..cca24cd 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -279,11 +279,16 @@ function escId(sliceId, trigger) {
   const round = escRound(sliceId, trigger)
   const base = `${sliceId}:${trigger}`
   return round === 1 ? base : `${base}:${round}`
 }
 
-function esc(slice, trigger, title, context, question, options) {
+// `content` is `{title, context, question, options}`, grouped into one
+// parameter object because those four always travel together (one prompt's
+// worth of copy) while `slice` and `trigger` each drive a different part of
+// the id.
+function esc(slice, trigger, content) {
+  const { title, context, question, options } = content
   return {
     id: escId(slice.id, trigger),
     trigger, title, context, question,
     options: options && options.length ? options : [{ label: 'Proceed with the recommended default', detail: context, recommended: true }],
     if_unanswered: 'pause this slice; continue all independent slices',
@@ -449,13 +454,13 @@ Polish the diff ${state.commits.base}..HEAD in the worktree: behavior-preserving
 
 // ── Guarded dispatch ─────────────────────────────────────────────────────────
 
 function guard(slice, state) {
   if (state.agentsUsed >= CAPS[state.review_tier])
-    throw { escRecord: esc(slice, 'budget-exhausted', `agent cap reached (${CAPS[state.review_tier]})`, `Slice used ${state.agentsUsed} agents (tier ${state.review_tier} cap).`, 'Raise the cap and resume, accept the slice as-is, or drop it?', []) }
+    throw { escRecord: esc(slice, 'budget-exhausted', { title: `agent cap reached (${CAPS[state.review_tier]})`, context: `Slice used ${state.agentsUsed} agents (tier ${state.review_tier} cap).`, question: 'Raise the cap and resume, accept the slice as-is, or drop it?', options: [] }) }
   if (budget.total && budget.remaining() < BUDGET_STAGE_FLOOR)
-    throw { escRecord: esc(slice, 'budget-exhausted', 'token budget exhausted', `Wave budget remaining ${Math.round(budget.remaining() / 1000)}k is below the ${BUDGET_STAGE_FLOOR / 1000}k stage floor.`, 'Raise the budget and resume, accept committed work as-is, or drop the slice?', []) }
+    throw { escRecord: esc(slice, 'budget-exhausted', { title: 'token budget exhausted', context: `Wave budget remaining ${Math.round(budget.remaining() / 1000)}k is below the ${BUDGET_STAGE_FLOOR / 1000}k stage floor.`, question: 'Raise the budget and resume, accept committed work as-is, or drop the slice?', options: [] }) }
 }
 
 async function dispatch(slice, state, role, prompt, opts) {
   guard(slice, state)
   // Last dispatch STARTED, not a per-throw stage: never cleared, and
@@ -505,13 +510,13 @@ function doneResult(slice, state, status, extra) {
 
 // Stage P — plan (+ right-size gate inside the planner)
 async function stagePlan(slice, state) {
   const plan = await dispatch(slice, state, 'plan', planPrompt(slice),
     { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
-  if (!plan) return { stop: escalated(slice, state, esc(slice, 'ambiguity', 'planner returned no result', 'The planner dispatch failed terminally.', 'Retry the slice, or drop it?', [])) }
+  if (!plan) return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: 'planner returned no result', context: 'The planner dispatch failed terminally.', question: 'Retry the slice, or drop it?', options: [] })) }
   if (plan.status === 'SPLIT') return { stop: doneResult(slice, state, 'SPLIT', { split: plan.split }) }
-  if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, esc(slice, plan.escalation.trigger, plan.escalation.title, plan.escalation.context, plan.escalation.question, plan.escalation.options)) }
+  if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, esc(slice, plan.escalation.trigger, plan.escalation)) }
   return { plan }
 }
 
 // Stage C helpers — panel selection, verdict rollup, and the OBJECT branch.
 // Each helper below is kept single-purpose and small on its own terms (own
@@ -587,11 +592,11 @@ function latestAnswer(sliceId, trigger) {
   const newest = keys[keys.length - 1]
   return newest === undefined ? undefined : humanAnswer(newest)
 }
 
 function councilObjectionEscalation(slice, state, ob, safety) {
-  return escalated(slice, state, esc(slice, 'council-objection', `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, ob.objection.reason, ob.objection.question, [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }]))
+  return escalated(slice, state, esc(slice, 'council-objection', { title: `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, context: ob.objection.reason, question: ob.objection.question, options: [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }] }))
 }
 
 // The council OBJECT branch: an unanswered fixable objection gets one replan
 // attempt; anything else (safety, unfixable, or a failed replan) escalates.
 // answered → proceed with the existing plan; the answer is already injected
@@ -675,11 +680,11 @@ async function attemptTask(slice, state, plan, task) {
 }
 
 async function runTask(slice, state, plan, task) {
   const r = await attemptTask(slice, state, plan, task)
   if (taskNeedsRetry(r))
-    return { stop: escalated(slice, state, esc(slice, 'ambiguity', `task ${task.id} blocked`, taskBlockReason(r), `Task "${task.title}" cannot proceed. How should it resolve?`, [])) }
+    return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: `task ${task.id} blocked`, context: taskBlockReason(r), question: `Task "${task.title}" cannot proceed. How should it resolve?`, options: [] })) }
   state.tasksCompleted++
   // TASK_RESULT requires only status/touched_files/concerns/deviations, so a
   // task that legitimately changed nothing returns DONE with `commits`
   // absent. Reading it unguarded threw a TypeError that would now be
   // classified as an 'internal-error' by the catch-all; run 20260825-scope-
@@ -700,11 +705,11 @@ async function stageTasks(slice, state, plan) {
     const r = await runTask(slice, state, plan, task)
     if (r.stop) return { stop: r.stop }
     touched.push(...r.touched)
   }
   if (!state.commits.head)
-    return { stop: escalated(slice, state, esc(slice, 'ambiguity', 'plan produced no commits', 'All tasks completed but no commit was recorded.', 'Drop the slice or retry?', [])) }
+    return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: 'plan produced no commits', context: 'All tasks completed but no commit was recorded.', question: 'Drop the slice or retry?', options: [] })) }
   return { touched }
 }
 
 // Deterministic tier promotion: implementation touched a Tier-3 surface
 function maybePromoteTier(slice, state, touched) {
@@ -797,11 +802,11 @@ async function runFixRound(slice, state, ctx) {
   if (!open.length) return { open }
   state.review.confirmed = open.length
   state.review.fix_rounds = round + 1
   const fix = await dispatchFix(slice, state, { plan, open, round })
   if (!fix || fix.status === 'BLOCKED')
-    return { stop: escalated(slice, state, esc(slice, 'review-block', 'fix agent blocked', fixBlockerReason(fix), 'Blocking findings cannot be fixed automatically. Accept, guide, or drop?', [])) }
+    return { stop: escalated(slice, state, esc(slice, 'review-block', { title: 'fix agent blocked', context: fixBlockerReason(fix), question: 'Blocking findings cannot be fixed automatically. Accept, guide, or drop?', options: [] })) }
   if (fix.commits && fix.commits.head) state.commits.head = fix.commits.head
   const rr = await dispatch(slice, state, `re-review:${round + 1}`, reReviewPrompt(slice, state, open, fix),
     { agentType: 'spec-loop:re-reviewer', schema: REREVIEW_RESULT, model: 'sonnet', effort: 'low' })
   if (!rr) return { open } // fail closed: findings stay open into the next round / escalation
   state.review.refuted += rr.verdicts.filter(x => x.verdict === 'REFUTATION_ACCEPTED').length
@@ -817,12 +822,11 @@ async function stageFixLoop(slice, state, ctx) {
   for (let round = 0; open.length && round < MAX_FIX_ROUNDS; round++) {
     const res = await runFixRound(slice, state, { plan, review, open, round, bar })
     if (res.stop) return { stop: res.stop }
     open = res.open
   }
-  if (open.length)
-    return { stop: escalated(slice, state, esc(slice, open.some(f => f.category === 'quality-gate') ? 'quality-gate-block' : 'review-block', `${open.length} blocking finding(s) unresolved after ${MAX_FIX_ROUNDS} fix rounds`, open.map(f => `${f.severity} ${f.file}:${f.line} — ${f.claim}`).join('\n'), 'Accept the residual findings, provide guidance, or drop the slice?', [])) }
+  if (open.length) return { stop: escalated(slice, state, esc(slice, open.some(f => f.category === 'quality-gate') ? 'quality-gate-block' : 'review-block', { title: `${open.length} blocking finding(s) unresolved after ${MAX_FIX_ROUNDS} fix rounds`, context: open.map(f => `${f.severity} ${f.file}:${f.line} — ${f.claim}`).join('\n'), question: 'Accept the residual findings, provide guidance, or drop the slice?', options: [] })) }
   state.review.residual = review.findings.filter(f => !blocking([f], bar).length).map(f => `${f.severity}: ${f.claim}`).slice(0, 10)
   state.events.push({ scope: slice.id, type: 'review-summary', payload: { findings: review.findings.length, confirmed: state.review.confirmed, refuted: state.review.refuted, fix_rounds: state.review.fix_rounds, reviewers: state.reviewersCount } })
   return {}
 }
 
@@ -853,11 +857,11 @@ function markVerifiedDone(slice, state, v) {
 function verificationFailedEscalation(slice, state, v) {
   const trigger = verifySuiteFailed(v) ? 'review-block' : 'quality-gate-block'
   const detail = v
     ? `suite: ${v.suite.summary}; quality: ${qualityStatus(v.quality)} (summary_pass=${String(v.quality.summary_pass)}${v.quality.detail ? ` — ${v.quality.detail}` : ''})`
     : 'verifier dispatch failed terminally'
-  return escalated(slice, state, esc(slice, trigger, 'verification failed', detail, 'Verification cannot pass automatically. Guide, accept, or drop?', []))
+  return escalated(slice, state, esc(slice, trigger, { title: 'verification failed', context: detail, question: 'Verification cannot pass automatically. Guide, accept, or drop?', options: [] }))
 }
 
 async function runDebugFix(slice, state, plan, v) {
   const df = await dispatch(slice, state, 'debug-fix', debugFixPrompt(slice, plan, state, v),
     { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: 'inherit', effort: 'high' })
@@ -871,11 +875,11 @@ async function stageVerify(slice, state, plan) {
       { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' })
     if (verifyPassed(v)) return markVerifiedDone(slice, state, v)
     if (attempt === 0 && verifySuiteFailed(v)) { await runDebugFix(slice, state, plan, v); continue }
     return verificationFailedEscalation(slice, state, v)
   }
-  return escalated(slice, state, esc(slice, 'review-block', 'verification loop exhausted', 'unreachable', 'Guide, accept, or drop?', []))
+  return escalated(slice, state, esc(slice, 'review-block', { title: 'verification loop exhausted', context: 'unreachable', question: 'Guide, accept, or drop?', options: [] }))
 }
 
 // The seven-stage sequence, unwrapped from the try/catch below so its own
 // early-return checks aren't weighted by an extra level of nesting.
 async function runStages(slice, state) {
@@ -931,16 +935,16 @@ async function runStages(slice, state) {
 function runSliceError(slice, state, e) {
   if (e && e.escRecord) return escalated(slice, state, e.escRecord)
   const stage = state.stage
   const stageText = stage || 'none (the crash happened before any agent was dispatched)'
   const title = stage ? `slice crashed after ${stage}` : 'slice crashed before any agent was dispatched'
-  return escalated(slice, state, esc(slice, 'internal-error', title,
-    `Error: ${String((e && e.message) || e)}. Last stage/role dispatched before the failure: ${stageText} — the most recent dispatch, not a per-throw stage, so a starting point, not a culprit. Cause unknown: neither structural guard raised its escalation record, and that is all the check one line above proves — the stage token floor calls budget.remaining() itself, so a throw from inside a guard reaches here with no record either. It may be a loop or agent-contract bug, and it may equally be a host- or agent-layer resource failure (a rejected agent call on a hard token or rate limit, say) — the exception text above is the evidence, not this classification. state.stage is never cleared and concurrent fan-outs overwrite it, so the failure may also have happened after that role finished, or in a sibling of it. ${state.tasksCompleted} task(s) had already completed and any committed work is on the branch.`,
-    'Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?',
-    [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice, keeping the committed work on its branch.', recommended: true },
-     { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
-     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.' }]))
+  const context = `Error: ${String((e && e.message) || e)}. Last stage/role dispatched before the failure: ${stageText} — the most recent dispatch, not a per-throw stage, so a starting point, not a culprit. Cause unknown: neither structural guard raised its escalation record, and that is all the check one line above proves — the stage token floor calls budget.remaining() itself, so a throw from inside a guard reaches here with no record either. It may be a loop or agent-contract bug, and it may equally be a host- or agent-layer resource failure (a rejected agent call on a hard token or rate limit, say) — the exception text above is the evidence, not this classification. state.stage is never cleared and concurrent fan-outs overwrite it, so the failure may also have happened after that role finished, or in a sibling of it. ${state.tasksCompleted} task(s) had already completed and any committed work is on the branch.`
+  const question = 'Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?'
+  const options = [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice, keeping the committed work on its branch.', recommended: true }]
+  options.push({ label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' })
+  options.push({ label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.' })
+  return escalated(slice, state, esc(slice, 'internal-error', { title, context, question, options }))
 }
 
 async function runSlice(slice) {
   const state = initSliceState(slice)
   try {
@@ -958,13 +962,17 @@ const out = results.map((r, i) => r || {
   schema_version: 2, id: A.slices[i].id, status: 'ESCALATED', branch: A.slices[i].branch,
   commits: { base: A.slices[i].base_sha, head: null }, risk_tier: A.slices[i].risk_tier,
   review_tier: A.slices[i].risk_tier, critique: { verdict: 'SKIPPED', concerns: 0 },
   tasks_completed: 0, review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
   tests: null, quality: { status: 'SKIPPED', detail: 'slice never ran' },
-  escalations: [esc(A.slices[i], 'internal-error', 'slice lost', 'The slice function returned no result (terminal failure) — it died outside runSlice\'s try/catch. Neither structural guard raised its escalation record — each raises budget-exhausted with an escRecord runSlice would have returned — and that is all a null result proves, not that no guard check ran. A host- or agent-layer resource failure dies the same silent way, so the cause is unknown here.', 'Re-run the wave to retry this slice?',
-    [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice. No result came back, so this record carries no exception text to diagnose and no record of committed work — inspect the slice branch before the retry, which starts from its base.', recommended: true },
+  escalations: [esc(A.slices[i], 'internal-error', {
+    title: 'slice lost',
+    context: 'The slice function returned no result (terminal failure) — it died outside runSlice\'s try/catch. Neither structural guard raised its escalation record — each raises budget-exhausted with an escRecord runSlice would have returned — and that is all a null result proves, not that no guard check ran. A host- or agent-layer resource failure dies the same silent way, so the cause is unknown here.',
+    question: 'Re-run the wave to retry this slice?',
+    options: [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice. No result came back, so this record carries no exception text to diagnose and no record of committed work — inspect the slice branch before the retry, which starts from its base.', recommended: true },
      { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
-     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so a silent host- or agent-layer failure can be investigated before more agents are spent. Nothing in the loop stops the run by itself.' }])],
+     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so a silent host- or agent-layer failure can be investigated before more agents are spent. Nothing in the loop stops the run by itself.' }],
+  })],
   agents_used: 0, wave: A.wave_index, events: [],
 })
 log(`wave ${A.wave_index} collected: ${out.map(r => `${r.id}=${r.status}`).join(' ')}`)
 return { run_id: A.run_id, wave_index: A.wave_index, results: out }
