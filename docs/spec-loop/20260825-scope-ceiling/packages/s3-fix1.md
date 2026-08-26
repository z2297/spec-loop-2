# Review package: f4449bd..7db4048  (context: -U5)

## Commits
7db4048 fix(wave): resolve r0-s3-c1 reporter-answer defect and quality-gate scope findings

## Files changed
 .../spec-loop/scripts/test_slice_wave_contract.py  |  40 +-
 plugins/spec-loop/workflows/slice-wave.workflow.js | 563 ++++++++++++++-------
 2 files changed, 425 insertions(+), 178 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/test_slice_wave_contract.py": [
[
50,
55
],
[
61,
61
],
[
65,
67
],
[
75,
77
],
[
198,
200
],
[
234,
241
],
[
253,
253
],
[
255,
260
]
],
"plugins/spec-loop/workflows/slice-wave.workflow.js": [
[
268,
279
],
[
376,
376
],
[
410,
417
],
[
419,
422
],
[
431,
434
],
[
441,
773
],
[
775,
804
],
[
806,
806
],
[
808,
808
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/test_slice_wave_contract.py b/plugins/spec-loop/scripts/test_slice_wave_contract.py
index af33325..dd4f1b9 100644
--- a/plugins/spec-loop/scripts/test_slice_wave_contract.py
+++ b/plugins/spec-loop/scripts/test_slice_wave_contract.py
@@ -45,30 +45,38 @@ WRAP_HEAD = "async function __wrap(){\n"
 WRAP_TAIL = "\n}\n"
 
 # Anchors and pinned source lines (see the module docstring for why these are
 # constants and not literals inside the test bodies).
 TASK_RESULT_REQUIRED = "required: ['status', 'touched_files', 'concerns', 'deviations']"
-TASK_LOOP_START = "for (const task of plan.tasks || [])"
+# The task-result-handling region: taskNeedsRetry() through the end of
+# stageTasks()'s loop, right before the "no commits at all" escalation below
+# it. All of a TASK_RESULT's optional reads (commits/touched_files/concerns/
+# deviations) are guarded somewhere in this span, split across runTask() and
+# its small helpers rather than inlined in one loop body.
+TASK_LOOP_START = "function taskNeedsRetry(r) {"
 TASK_LOOP_END = "if (!state.commits.head)"
 NO_COMMITS_ESCALATION = "'plan produced no commits'"
 GUARDED_LOCAL = "const c = (r.commits && typeof r.commits === 'object') ? r.commits : {}"
 GUARDED_HEAD = "if (c.head) state.commits.head = c.head"
 GUARDED_BASE = "if (state.commits.base === null && c.base) state.commits.base = c.base"
-GUARDED_TOUCHED = "touched.push(...(r.touched_files || []))"
+GUARDED_TOUCHED = "touched: r.touched_files || []"
 GUARDED_CONCERNS = "...(r.concerns || [])"
 GUARDED_DEVIATIONS = "...(r.deviations || []).map("
 GATE_ANSWER = "answerFor(slice, 'quality-gate-block')"
+GATE_ANSWER_CONTEXT = "answerContext(slice, 'quality-gate-block')"
+ANSWER_CONTEXT_START = "const answerContext = (slice, trigger) => {"
+ANSWER_CONTEXT_END = "\n}\n"
 ANSWERABLE_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
                        "council-objection", "quality-gate-block")
 CRITIQUE_REQUIRED = "required: ['verdict', 'safety', 'concerns']"
 FAIL_CLOSED_DEFAULT = "unreadable critic verdict (fail closed)"
 OVER_SCOPE_DEFAULT = "over_scope: null"
 OVER_SCOPE_SCHEMA = "over_scope: { type: 'object'"
 CRITIQUE_ROLLUP = "state.critique = { verdict:"
-SPLIT_SUPPRESSION = "if (splitRec && slice.depth < 2"
-OBJECTION_SELECTION = "const ob = (safety || objections[0])"
-REPLAN_VETO = "if (!safety && ob.fixable_by_replan"
+SPLIT_SUPPRESSION = "return (rec && depth < 2 && verdict !== 'OBJECT') ? rec : null"
+OBJECTION_SELECTION = "ob: (safety || objections[0])"
+REPLAN_VETO = "if (safety || !ob.fixable_by_replan || state.replanned)"
 FINDING_CATEGORIES = "category: { enum: ["
 COUNCIL_VERDICT_EVENT = "type: 'council-verdict'"
 SCOPE_HELPER = "function scopeRecord("
 HELPER_END = "\n}\n"
 SCOPE_LOCAL = "const scope = scopeRecord(verdicts)"
@@ -185,11 +193,13 @@ class TestOptionalTaskResultReadsAreGuarded(WorkflowSourceTestCase):
     TypeError, the catch-all re-labelled it 'wave interrupted' /
     budget-exhausted, and a wave whose five tasks had all committed was
     reported as a resource failure."""
 
     def task_loop(self):
-        """The Stage-T task loop body, where every task-result read happens."""
+        """The Stage-T task-result-handling region (runTask() and its small
+        helpers, through stageTasks()'s loop), where every task-result read
+        happens."""
         return self.between(TASK_LOOP_START, TASK_LOOP_END)
 
     def test_commits_is_not_required_by_the_task_result_schema(self):
         # The premise of the guard: absent `commits` is a legal DONE return.
         required = self.line_containing(TASK_RESULT_REQUIRED)
@@ -219,11 +229,18 @@ class TestOptionalTaskResultReadsAreGuarded(WorkflowSourceTestCase):
 
 
 class TestQualityGateBlockAnswersHaveAnInjectionPath(WorkflowSourceTestCase):
     """A quality-gate-block escalation had no answerFor() site, so a human
     answer could not be carried by the re-dispatch: this run's controller
-    hand-resolved one twice."""
+    hand-resolved one twice. The fix loop (fixPrompt) can legitimately act on
+    such an answer, so it gets the real answerFor() (apply it). The Stage-Z
+    reporter (verifyPrompt -> spec-loop:verifier) cannot: it is transcription
+    -only ("you never return a PASS/FAIL label"), so an "apply it" answer
+    there has no lawful effect except a mis-transcribed false pass. It gets
+    answerContext() instead: the human's answer is still carried into the
+    resumed dispatch (so it is not silently lost / re-asked), but worded as
+    context only, never as an instruction to change what gets reported."""
 
     def test_every_human_answerable_trigger_has_at_least_one_injection_site(self):
         for trigger in ANSWERABLE_TRIGGERS:
             self.assertIn(
                 "answerFor(slice, '%s')" % (trigger,), self.src,
@@ -231,13 +248,18 @@ class TestQualityGateBlockAnswersHaveAnInjectionPath(WorkflowSourceTestCase):
 
     def test_the_fix_prompt_carries_the_gate_answer(self):
         fix = self.between("function fixPrompt(", "function reReviewPrompt(")
         self.assertIn(GATE_ANSWER, fix)
 
-    def test_the_verify_prompt_carries_the_gate_answer(self):
+    def test_the_verify_prompt_carries_the_gate_answer_as_context_only(self):
         verify = self.between("function verifyPrompt(", "function debugFixPrompt(")
-        self.assertIn(GATE_ANSWER, verify)
+        self.assertIn(GATE_ANSWER_CONTEXT, verify)
+        self.assertNotIn(GATE_ANSWER, verify)
+
+    def test_the_context_only_answer_never_instructs_the_reporter_to_apply_it(self):
+        answer_context_fn = self.between(ANSWER_CONTEXT_START, ANSWER_CONTEXT_END)
+        self.assertNotIn("apply it", answer_context_fn)
 
     def test_budget_exhausted_is_still_not_injected_anywhere(self):
         # It asks for a resource, not a decision (escalation-gate SKILL.md):
         # there is nothing for a prompt to apply.
         self.assertNotIn("answerFor(slice, 'budget-exhausted')", self.src)
diff --git a/plugins/spec-loop/workflows/slice-wave.workflow.js b/plugins/spec-loop/workflows/slice-wave.workflow.js
index 283267e..194e5c6 100644
--- a/plugins/spec-loop/workflows/slice-wave.workflow.js
+++ b/plugins/spec-loop/workflows/slice-wave.workflow.js
@@ -263,10 +263,22 @@ const packet = (slice) => [
 const answerFor = (slice, trigger) => {
   const a = (A.answers || {})[`${slice.id}:${trigger}`]
   return a ? `\nHUMAN ANSWER to your earlier "${trigger}" escalation (apply it, do not re-raise): ${a}` : ''
 }
 
+// A context-only sibling of answerFor(), for dispatches to a transcription-
+// only reporter (spec-loop:verifier — "you never return a PASS/FAIL label",
+// "never a verdict you formed"). A quality-gate-block answer can be "accept
+// the residual violations", but a reporter has no lawful way to "apply" that
+// beyond mis-transcribing the gate's real output as a pass. This carries the
+// answer for a human resuming the escalation to see in the transcript
+// without instructing the reporter to change what it reports.
+const answerContext = (slice, trigger) => {
+  const a = (A.answers || {})[`${slice.id}:${trigger}`]
+  return a ? `\nHUMAN ANSWER on the earlier "${trigger}" escalation, for context only — it does NOT change what you report: the suite result and quality.summary_pass/violations stay verbatim from the real output: ${a}` : ''
+}
+
 function planPrompt(slice) {
   return `${packet(slice)}
 
 Plan slice ${slice.id} of run ${A.run_id}: ${slice.goal}
 Named files: ${slice.files.join(', ') || '(none named)'} · Subsystems: ${slice.subsystems.join(', ') || '—'}
@@ -359,11 +371,11 @@ function verifyPrompt(slice, state) {
 
 Reporter mode, full verification. In the worktree run the full suite exactly: ${CTX.test_command}
 (a " ; "-joined command is a segment list: run each segment as its own tool call, in order, all to completion; the suite passed only if every segment passed)
 Then the quality gate exactly:
   ${CTX.quality_gate_cmd} --base ${state.commits.base} --head HEAD --repo-dir "${slice.worktree}"
-Read both outputs; report what they actually say. quality.summary_pass is the gate JSON's summary.pass copied verbatim (null ONLY if the gate never produced parseable JSON — say why in detail); quality.violations is its summary.failures array verbatim; you never return a PASS/FAIL label. changed_files from git diff --name-only ${state.commits.base}..HEAD.${answerFor(slice, 'quality-gate-block')}`
+Read both outputs; report what they actually say. quality.summary_pass is the gate JSON's summary.pass copied verbatim (null ONLY if the gate never produced parseable JSON — say why in detail); quality.violations is its summary.failures array verbatim; you never return a PASS/FAIL label. changed_files from git diff --name-only ${state.commits.base}..HEAD.${answerContext(slice, 'quality-gate-block')}`
 }
 
 function debugFixPrompt(slice, plan, state, verify) {
   return `${packet(slice)}
 
@@ -393,196 +405,409 @@ async function dispatch(slice, state, role, prompt, opts) {
   state.events.push({ scope: slice.id, type: 'agent-dispatch', payload: { role, model: opts.model || 'inherit', effort: opts.effort || null, agent_type: opts.agentType || null } })
   return r // null on user-skip/terminal error — callers fail closed
 }
 
 // ── The slice pipeline ───────────────────────────────────────────────────────
+//
+// runSlice orchestrates seven stages (P/C/T/R/V-F/S/Z) as a flat sequence of
+// extracted stage functions below it. Each stage returns either `{ stop }`
+// (a terminal slice result — the caller returns it immediately) or the data
+// the next stage needs; runSlice itself does no branching beyond "did this
+// stage ask to stop". Splitting the pipeline this way keeps every function's
+// own complexity/length/nesting small and independently named, instead of
+// one function carrying the whole slice's control flow.
 
-async function runSlice(slice) {
-  const state = {
+const TASK_LANE = { transcribe: { model: 'haiku', effort: 'low' }, standard: { model: 'sonnet', effort: 'medium' }, judgment: { model: 'inherit', effort: 'high' } }
+
+function initSliceState(slice) {
+  return {
     agentsUsed: 0, events: [], escalations: [],
     review_tier: Math.max(slice.risk_tier, CTX.thorough ? Math.min(slice.risk_tier + 1, 3) : slice.risk_tier),
     critique: { verdict: 'SKIPPED', concerns: 0 },
     commits: { base: slice.base_sha, head: null },
     tasksCompleted: 0, implConcerns: [], deferred: [],
     review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
     tests: null, quality: { status: 'SKIPPED', detail: 'not reached' },
   }
-  const done = (status, extra) => ({
+}
+
+function doneResult(slice, state, status, extra) {
+  return {
     schema_version: 2, id: slice.id, status,
     branch: slice.branch, commits: state.commits, risk_tier: slice.risk_tier,
     review_tier: state.review_tier, critique: state.critique,
     tasks_completed: state.tasksCompleted, review: state.review,
     tests: state.tests, quality: state.quality, escalations: state.escalations,
     agents_used: state.agentsUsed, wave: A.wave_index, events: state.events, ...extra,
-  })
+  }
+}
+
+// Stage P — plan (+ right-size gate inside the planner)
+async function stagePlan(slice, state) {
+  const plan = await dispatch(slice, state, 'plan', planPrompt(slice),
+    { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
+  if (!plan) return { stop: escalated(slice, state, esc(slice, 'ambiguity', 'planner returned no result', 'The planner dispatch failed terminally.', 'Retry the slice, or drop it?', [])) }
+  if (plan.status === 'SPLIT') return { stop: doneResult(slice, state, 'SPLIT', { split: plan.split }) }
+  if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, { ...esc(slice, plan.escalation.trigger, plan.escalation.title, plan.escalation.context, plan.escalation.question, plan.escalation.options), id: `${slice.id}:${plan.escalation.trigger}` }) }
+  return { plan }
+}
+
+// Stage C helpers — panel selection, verdict rollup, and the OBJECT branch.
+// Each helper below is kept single-purpose and small on its own terms (own
+// complexity/param-count budget), which is what lets stageCritique itself
+// stay a short list of calls instead of one large branchy function.
+
+function failClosedCritique() {
+  return { verdict: 'OBJECT', safety: { flag: false, reason: null }, over_scope: null, concerns: [], objection: { reason: 'unreadable critic verdict (fail closed)', question: 'The plan critique could not be completed. Proceed anyway, or retry?', recommendation: 'retry the slice' }, fixable_by_replan: false }
+}
+
+function selectCouncilPanel(state) {
+  if (state.review_tier < 3) return [['full-council', 'spec-loop:plan-critic', 'inherit', 'low', null]]
+  if (CTX.thorough) return [['full-council', 'spec-loop:plan-critic', 'inherit', 'high', null], ['risk', 'spec-loop:guardian', 'inherit', 'high', 'risk'], ['premise', 'spec-loop:skeptic', 'sonnet', 'high', 'premise']]
+  return [['full-council', 'spec-loop:plan-critic', 'inherit', 'high', null], ['risk', 'spec-loop:guardian', 'inherit', 'high', 'risk']]
+}
+
+function computeCritiqueVerdict(safety, objections, verdicts, concerns) {
+  if (safety || objections.length * 2 > verdicts.length) return 'OBJECT'
+  return concerns.length ? 'ENDORSE_WITH_CONCERNS' : 'ENDORSE'
+}
+
+// Each concern remembers whether the member that raised it flagged the plan
+// as over-scope, so a deferral can be marked without any member needing a
+// second field. Extra keys are inert downstream: concerns are only counted,
+// filtered by disposition_hint, and mapped to .text.
+function deriveCouncilInputs(verdicts) {
+  const objections = verdicts.filter(v => v.verdict === 'OBJECT')
+  const safety = verdicts.find(v => v.safety.flag)
+  const concerns = verdicts.flatMap(v => v.concerns.map(c => ({ ...c, over_scope: !!(v.over_scope && v.over_scope.flag === true) })))
+  const scope = scopeRecord(verdicts)
+  return { objections, safety, concerns, scope }
+}
+
+// A split is only actionable below the depth cap, and never alongside an
+// OBJECT (an objection always wins the turn).
+function findSplitRecommendation(verdicts, depth, verdict) {
+  const rec = verdicts.find(v => v.split && v.split.recommended && (v.split.children || []).length >= 2)
+  return (rec && depth < 2 && verdict !== 'OBJECT') ? rec : null
+}
+
+// RECORD-ONLY: `ctx.scope` is carried into the event payload after the
+// verdict is already computed elsewhere — this function never feeds back
+// into the verdict itself.
+function recordCouncilVerdict(slice, state, ctx) {
+  const { panel, safety, concerns, scope } = ctx
+  state.events.push({ scope: slice.id, type: 'council-verdict', payload: { verdict: state.critique.verdict, panel: panel.map(p => p[0]), safety: !!safety, concerns_folded: concerns.filter(c => c.disposition_hint === 'fold').length, deferred: concerns.filter(c => c.disposition_hint === 'defer').map(c => c.text), ...(scope ? { over_scope: scope } : {}) } })
+}
+
+function humanAnswer(id) {
+  return (A.answers || {})[id]
+}
+
+function councilObjectionEscalation(slice, state, ob, safety) {
+  return escalated(slice, state, esc(slice, 'council-objection', `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, ob.objection.reason, ob.objection.question, [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }]))
+}
+
+// The council OBJECT branch: an unanswered fixable objection gets one replan
+// attempt; anything else (safety, unfixable, or a failed replan) escalates.
+// answered → proceed with the existing plan; the answer is already injected
+// into downstream prompts via answerFor().
+async function resolveCouncilObjection(slice, state, ctx) {
+  const { plan, ob, safety } = ctx
+  if (humanAnswer(`${slice.id}:council-objection`)) return { plan }
+  if (safety || !ob.fixable_by_replan || state.replanned) return { stop: councilObjectionEscalation(slice, state, ob, safety) }
+  state.replanned = true
+  const revised = await dispatch(slice, state, 'replan', replanPrompt(slice, plan, ob),
+    { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
+  return (revised && revised.status === 'PLANNED') ? { plan: revised } : { stop: councilObjectionEscalation(slice, state, ob, safety) }
+}
+
+// Stage C — critique (tier ≥ 2)
+async function stageCritique(slice, state, plan) {
+  if (state.review_tier < 2) return { plan }
+  const panel = selectCouncilPanel(state)
+  guard(slice, state)
+  const raw = await parallel(panel.map(([role, agentType, model, effort, lane]) => () =>
+    dispatch(slice, state, `critic:${role}`, criticPrompt(slice, plan, lane),
+      { agentType, schema: CRITIQUE, model, effort })))
+  const verdicts = raw.map(v => v || failClosedCritique())
+  const { objections, safety, concerns, scope } = deriveCouncilInputs(verdicts)
+  state.critique = { verdict: computeCritiqueVerdict(safety, objections, verdicts, concerns), concerns: concerns.length }
+  // RECORD-ONLY: attached after the verdict is computed, never spread into
+  // the rollup literal above, so the verdict expression provably cannot
+  // consult it. Omitted entirely when no member judged scope.
+  if (scope) state.critique.over_scope = scope
+  recordCouncilVerdict(slice, state, { panel, safety, concerns, scope })
+  state.deferred = concerns.filter(c => c.disposition_hint === 'defer').map(c => c.text)
+  deferralEvents(slice, concerns).forEach(e => state.events.push(e))
+  const splitRec = findSplitRecommendation(verdicts, slice.depth, state.critique.verdict)
+  if (splitRec) return { stop: doneResult(slice, state, 'SPLIT', { split: { children: splitRec.split.children } }) }
+  if (state.critique.verdict !== 'OBJECT') return { plan }
+  return resolveCouncilObjection(slice, state, { plan, ob: (safety || objections[0]), safety })
+}
+
+// Stage T helpers — one task attempt (with the lane-lift retry) and the
+// guarded commits read (see the comment on the guard below).
+
+function taskNeedsRetry(r) {
+  return !r || r.status === 'NEEDS_CONTEXT' || r.status === 'BLOCKED'
+}
+
+function taskBlockReason(r) {
+  return (r && (r.blocker || (r.questions || []).join(' · '))) || 'terminal dispatch failure'
+}
+
+function mergeTaskCommits(state, r) {
+  const c = (r.commits && typeof r.commits === 'object') ? r.commits : {}
+  if (c.head) state.commits.head = c.head
+  if (state.commits.base === null && c.base) state.commits.base = c.base
+}
+
+async function attemptTask(slice, state, plan, task) {
+  const r = await dispatch(slice, state, `task:${task.id}`, taskPrompt(slice, plan, task, null),
+    { agentType: 'spec-loop:implementer', schema: TASK_RESULT, ...TASK_LANE[task.lane] })
+  if (!taskNeedsRetry(r)) return r
+  const lift = task.lane === 'transcribe' ? TASK_LANE.standard : TASK_LANE.judgment
+  return dispatch(slice, state, `task:${task.id}:retry`, taskPrompt(slice, plan, task, r || { status: 'BLOCKED', blocker: 'terminal dispatch failure' }),
+    { agentType: 'spec-loop:implementer', schema: TASK_RESULT, ...lift })
+}
+
+async function runTask(slice, state, plan, task) {
+  const r = await attemptTask(slice, state, plan, task)
+  if (taskNeedsRetry(r))
+    return { stop: escalated(slice, state, esc(slice, 'ambiguity', `task ${task.id} blocked`, taskBlockReason(r), `Task "${task.title}" cannot proceed. How should it resolve?`, [])) }
+  state.tasksCompleted++
+  // TASK_RESULT requires only status/touched_files/concerns/deviations, so a
+  // task that legitimately changed nothing returns DONE with `commits`
+  // absent. Reading it unguarded threw a TypeError that the catch-all below
+  // re-labelled as a budget-exhausted 'wave interrupted' — run
+  // 20260825-scope-ceiling lost a wave to it after all five tasks had
+  // already committed. Guarded the way the fix and debug-fix sites already
+  // guard the identical access; `head` keeps its previous value, so a slice
+  // where NO task committed still leaves it null and falls into the 'plan
+  // produced no commits' escalation below.
+  mergeTaskCommits(state, r)
+  state.implConcerns.push(...(r.concerns || []), ...(r.deviations || []).map(d => `deviation: ${d}`))
+  return { touched: r.touched_files || [] }
+}
+
+// Stage T — sequential task implementation
+async function stageTasks(slice, state, plan) {
+  const touched = []
+  for (const task of plan.tasks || []) {
+    const r = await runTask(slice, state, plan, task)
+    if (r.stop) return { stop: r.stop }
+    touched.push(...r.touched)
+  }
+  if (!state.commits.head)
+    return { stop: escalated(slice, state, esc(slice, 'ambiguity', 'plan produced no commits', 'All tasks completed but no commit was recorded.', 'Drop the slice or retry?', [])) }
+  return { touched }
+}
+
+// Deterministic tier promotion: implementation touched a Tier-3 surface
+function maybePromoteTier(slice, state, touched) {
+  if (state.review_tier < 3 && touchesTier3Surface(touched, CTX.tier3_surfaces)) {
+    state.review_tier = 3
+    state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `review tier promoted to 3: diff touches tier3 surface`, rationale: 'deterministic surface-glob match', reversibility: 'n/a' } })
+  }
+}
+
+function selectReviewers(state) {
+  if (state.review_tier >= 3)
+    return [['review:correctness', 'correctness + errors + risk', { model: 'inherit', effort: 'high' }], ['review:tests', 'tests + types + design + comments + conventions', { model: 'sonnet', effort: 'high' }]]
+  return [['review:full', null, state.review_tier === 1 ? { model: CTX.models?.reviewer || 'sonnet', effort: 'low' } : { model: CTX.models?.reviewer || 'inherit', effort: 'medium' }]]
+}
+
+function buildReviewSummary(reviewParts) {
+  const review = {
+    findings: reviewParts.filter(Boolean).flatMap((r, i) => r.findings.map(f => ({ ...f, id: `r${i}-${f.id}` }))),
+    summary: reviewParts.filter(Boolean).map(r => r.summary).join(' | ') || 'review dispatch failed (fail closed)',
+  }
+  if (reviewParts.some(r => !r)) review.findings.push({ id: 'failclosed-review', severity: 'P0', category: 'correctness', file: '-', line: 0, claim: 'a reviewer dispatch returned no result — review incomplete (fail closed)', evidence: { quote: 'n/a' }, remedy: 'resume to re-run the review', confidence: 'high', outside_diff: true })
+  return review
+}
+
+function buildGateViolations(gateStatus, gate) {
+  if (gateStatus !== 'FAIL' || !gate) return []
+  return (gate.quality.violations || []).map((v, i) => ({ id: `qg-${i}`, severity: 'P1', category: 'quality-gate', file: v.file || '-', line: 0, claim: `${v.metric} ${v.value} > threshold ${v.threshold} in ${v.function || v.file}`, evidence: { quote: JSON.stringify(v) }, remedy: 'behavior-preserving refactor (extract method, guard clauses, parameter object)', confidence: 'high', outside_diff: false }))
+}
+
+// Stage R — review ∥ quality gate
+async function stageReviewGate(slice, state, plan) {
+  guard(slice, state)
+  const reviewers = selectReviewers(state)
+  const [reviewParts, gate] = await parallel([
+    () => parallel(reviewers.map(([role, lanes, opts]) => () =>
+      dispatch(slice, state, role, reviewPrompt(slice, plan, state, lanes),
+        { agentType: 'spec-loop:pr-reviewer', schema: REVIEW_RESULT, ...opts }))),
+    () => dispatch(slice, state, 'gate', gatePrompt(slice, state),
+      { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' }),
+  ])
+  const review = buildReviewSummary(reviewParts)
+  const gateStatus = qualityStatus(gate && gate.quality)
+  const gateViolations = buildGateViolations(gateStatus, gate)
+  state.quality = gate ? { status: gateStatus, detail: gate.quality.detail || `${gateViolations.length} violation(s)` } : { status: 'FAIL', detail: 'gate dispatch failed (fail closed)' }
+  state.events.push({ scope: slice.id, type: 'quality-gate', payload: { status: state.quality.status, violations: gateViolations.length } })
+  state.reviewersCount = reviewers.length
+  return { review, gateViolations }
+}
+
+// One fix-loop round: optional batched verification (tier 3), a fix dispatch,
+// and a re-review to close or roll over the remaining findings.
+async function verifyAndFilterFindings(slice, state, open) {
+  const v = await dispatch(slice, state, 'verify-findings', verifierBatchPrompt(slice, state, open),
+    { agentType: 'spec-loop:finding-verifier', schema: VERIFIER_RESULT, model: 'sonnet', effort: 'low' })
+  const refuted = new Set(((v && v.verdicts) || []).filter(x => x.verdict === 'REFUTED').map(x => x.finding_id))
+  state.review.refuted += refuted.size
+  refuted.forEach(id => state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `finding ${id} refuted by batched verifier`, rationale: (v.verdicts.find(x => x.finding_id === id) || {}).evidence || '', reversibility: 'n/a' } }))
+  return open.filter(f => !refuted.has(f.id))
+}
+
+// escape hatch: fix touched files outside the reviewed diff → full re-review next round is the residual's problem; record it
+function recordOutsideDiffFix(slice, state, ctx) {
+  const { plan, review, fix, round } = ctx
+  const outside = fix.touched_files.filter(f => !review.findings.some(x => x.file === f) && !(plan.tasks || []).some(t => t.files.includes(f)))
+  if (outside.length) state.events.push({ scope: slice.id, type: 'review-summary', payload: { note: `fix round ${round + 1} touched files outside the original diff: ${outside.join(', ')}`, requires_full_rereview: true } })
+}
+
+function fixBlockerReason(fix) {
+  return (fix && fix.blocker) || 'terminal dispatch failure'
+}
+
+async function dispatchFix(slice, state, ctx) {
+  const { plan, open, round } = ctx
+  return dispatch(slice, state, `fix:${round + 1}`, fixPrompt(slice, plan, state, open),
+    { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: round === 0 ? 'sonnet' : 'inherit', effort: 'medium' })
+}
+
+function closeRereviewedFindings(rr, open, round, bar) {
+  const closed = new Set(rr.verdicts.filter(x => x.verdict === 'ADDRESSED' || x.verdict === 'REFUTATION_ACCEPTED').map(x => x.finding_id))
+  return [...open.filter(f => !closed.has(f.id)), ...blocking(rr.new_breakage, bar).map((f, i) => ({ ...f, id: `nb${round}-${i}` }))]
+}
+
+async function maybeVerifyFindings(slice, state, open) {
+  return state.review_tier >= 3 ? verifyAndFilterFindings(slice, state, open) : open
+}
+
+async function runFixRound(slice, state, ctx) {
+  const { plan, review, round, bar } = ctx
+  const open = await maybeVerifyFindings(slice, state, ctx.open)
+  if (!open.length) return { open }
+  state.review.confirmed = open.length
+  state.review.fix_rounds = round + 1
+  const fix = await dispatchFix(slice, state, { plan, open, round })
+  if (!fix || fix.status === 'BLOCKED')
+    return { stop: escalated(slice, state, esc(slice, 'review-block', 'fix agent blocked', fixBlockerReason(fix), 'Blocking findings cannot be fixed automatically. Accept, guide, or drop?', [])) }
+  if (fix.commits && fix.commits.head) state.commits.head = fix.commits.head
+  const rr = await dispatch(slice, state, `re-review:${round + 1}`, reReviewPrompt(slice, state, open, fix),
+    { agentType: 'spec-loop:re-reviewer', schema: REREVIEW_RESULT, model: 'sonnet', effort: 'low' })
+  if (!rr) return { open } // fail closed: findings stay open into the next round / escalation
+  state.review.refuted += rr.verdicts.filter(x => x.verdict === 'REFUTATION_ACCEPTED').length
+  recordOutsideDiffFix(slice, state, { plan, review, fix, round })
+  return { open: closeRereviewedFindings(rr, open, round, bar) }
+}
+
+// Stage V/F — verify findings + fix loop (≤2 rounds)
+async function stageFixLoop(slice, state, ctx) {
+  const { plan, review, gateViolations } = ctx
+  const bar = state.review_tier === 1 ? 'P0' : 'P0+P1'
+  let open = [...blocking(review.findings, bar), ...gateViolations]
+  for (let round = 0; open.length && round < MAX_FIX_ROUNDS; round++) {
+    const res = await runFixRound(slice, state, { plan, review, open, round, bar })
+    if (res.stop) return { stop: res.stop }
+    open = res.open
+  }
+  if (open.length)
+    return { stop: escalated(slice, state, esc(slice, open.some(f => f.category === 'quality-gate') ? 'quality-gate-block' : 'review-block', `${open.length} blocking finding(s) unresolved after ${MAX_FIX_ROUNDS} fix rounds`, open.map(f => `${f.severity} ${f.file}:${f.line} — ${f.claim}`).join('\n'), 'Accept the residual findings, provide guidance, or drop the slice?', [])) }
+  state.review.residual = review.findings.filter(f => !blocking([f], bar).length).map(f => `${f.severity}: ${f.claim}`).slice(0, 10)
+  state.events.push({ scope: slice.id, type: 'review-summary', payload: { findings: review.findings.length, confirmed: state.review.confirmed, refuted: state.review.refuted, fix_rounds: state.review.fix_rounds, reviewers: state.reviewersCount } })
+  return {}
+}
+
+// Stage S — simplify polish (tier 3 / thorough, non-blocking)
+async function maybePolish(slice, state) {
+  if (state.review_tier >= 3 && CTX.polish !== false)
+    await dispatch(slice, state, 'simplify', simplifyPrompt(slice, state),
+      { agentType: 'spec-loop:simplifier', model: 'sonnet', effort: 'low' }).then(() => {}, () => {})
+}
+
+// Stage Z helpers — verification-outcome predicates and terminal builders.
+
+function verifyPassed(v) {
+  return !!(v && v.suite.passed && qualityStatus(v.quality) === 'PASS')
+}
+
+function verifySuiteFailed(v) {
+  return !!(v && !v.suite.passed)
+}
+
+function markVerifiedDone(slice, state, v) {
+  state.tests = { command: v.suite.command, result: v.suite.summary, scope: 'full', tree_sha: v.tree_sha }
+  state.quality = { status: 'PASS', detail: v.quality.detail || state.quality.detail }
+  state.commits.head = v.head_sha
+  return doneResult(slice, state, 'DONE')
+}
+
+function verificationFailedEscalation(slice, state, v) {
+  const trigger = verifySuiteFailed(v) ? 'review-block' : 'quality-gate-block'
+  const detail = v
+    ? `suite: ${v.suite.summary}; quality: ${qualityStatus(v.quality)} (summary_pass=${String(v.quality.summary_pass)}${v.quality.detail ? ` — ${v.quality.detail}` : ''})`
+    : 'verifier dispatch failed terminally'
+  return escalated(slice, state, esc(slice, trigger, 'verification failed', detail, 'Verification cannot pass automatically. Guide, accept, or drop?', []))
+}
+
+async function runDebugFix(slice, state, plan, v) {
+  const df = await dispatch(slice, state, 'debug-fix', debugFixPrompt(slice, plan, state, v),
+    { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: 'inherit', effort: 'high' })
+  if (df && df.commits && df.commits.head) state.commits.head = df.commits.head
+}
+
+// Stage Z — full verification (suite + gate re-check), ≤1 debug-fix
+async function stageVerify(slice, state, plan) {
+  for (let attempt = 0; attempt < 2; attempt++) {
+    const v = await dispatch(slice, state, `verify:${attempt + 1}`, verifyPrompt(slice, state),
+      { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' })
+    if (verifyPassed(v)) return markVerifiedDone(slice, state, v)
+    if (attempt === 0 && verifySuiteFailed(v)) { await runDebugFix(slice, state, plan, v); continue }
+    return verificationFailedEscalation(slice, state, v)
+  }
+  return escalated(slice, state, esc(slice, 'review-block', 'verification loop exhausted', 'unreachable', 'Guide, accept, or drop?', []))
+}
 
+// The seven-stage sequence, unwrapped from the try/catch below so its own
+// early-return checks aren't weighted by an extra level of nesting.
+async function runStages(slice, state) {
+  const p = await stagePlan(slice, state)
+  if (p.stop) return p.stop
+  let plan = p.plan
+
+  const c = await stageCritique(slice, state, plan)
+  if (c.stop) return c.stop
+  plan = c.plan
+
+  const t = await stageTasks(slice, state, plan)
+  if (t.stop) return t.stop
+  maybePromoteTier(slice, state, t.touched)
+
+  const rg = await stageReviewGate(slice, state, plan)
+  const f = await stageFixLoop(slice, state, { plan, review: rg.review, gateViolations: rg.gateViolations })
+  if (f.stop) return f.stop
+
+  await maybePolish(slice, state)
+  return stageVerify(slice, state, plan)
+}
+
+function runSliceError(slice, state, e) {
+  if (e && e.escRecord) return escalated(slice, state, e.escRecord)
+  return escalated(slice, state, esc(slice, 'budget-exhausted', 'wave interrupted', String((e && e.message) || e), 'The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?', []))
+}
+
+async function runSlice(slice) {
+  const state = initSliceState(slice)
   try {
-    // Stage P — plan (+ right-size gate inside the planner)
-    let plan = await dispatch(slice, state, 'plan', planPrompt(slice),
-      { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
-    if (!plan) return escalated(slice, state, esc(slice, 'ambiguity', 'planner returned no result', 'The planner dispatch failed terminally.', 'Retry the slice, or drop it?', []))
-    if (plan.status === 'SPLIT') return done('SPLIT', { split: plan.split })
-    if (plan.status === 'ESCALATE') return escalated(slice, state, { ...esc(slice, plan.escalation.trigger, plan.escalation.title, plan.escalation.context, plan.escalation.question, plan.escalation.options), id: `${slice.id}:${plan.escalation.trigger}` })
-
-    // Stage C — critique (tier ≥ 2)
-    if (state.review_tier >= 2) {
-      const panel = state.review_tier >= 3
-        ? (CTX.thorough
-          ? [['full-council', 'spec-loop:plan-critic', 'inherit', 'high', null], ['risk', 'spec-loop:guardian', 'inherit', 'high', 'risk'], ['premise', 'spec-loop:skeptic', 'sonnet', 'high', 'premise']]
-          : [['full-council', 'spec-loop:plan-critic', 'inherit', 'high', null], ['risk', 'spec-loop:guardian', 'inherit', 'high', 'risk']])
-        : [['full-council', 'spec-loop:plan-critic', 'inherit', 'low', null]]
-      guard(slice, state)
-      const verdicts = (await parallel(panel.map(([role, agentType, model, effort, lane]) => () =>
-        dispatch(slice, state, `critic:${role}`, criticPrompt(slice, plan, lane), { agentType, schema: CRITIQUE, model, effort }))))
-        .map(v => v || { verdict: 'OBJECT', safety: { flag: false, reason: null }, over_scope: null, concerns: [], objection: { reason: 'unreadable critic verdict (fail closed)', question: 'The plan critique could not be completed. Proceed anyway, or retry?', recommendation: 'retry the slice' }, fixable_by_replan: false })
-      const objections = verdicts.filter(v => v.verdict === 'OBJECT')
-      const safety = verdicts.find(v => v.safety.flag)
-      const splitRec = verdicts.find(v => v.split && v.split.recommended && (v.split.children || []).length >= 2)
-      // Each concern remembers whether the member that raised it flagged the
-      // plan as over-scope, so a deferral can be marked without any member
-      // needing a second field. Extra keys are inert downstream: concerns are
-      // only counted, filtered by disposition_hint, and mapped to .text.
-      const concerns = verdicts.flatMap(v => v.concerns.map(c => ({ ...c, over_scope: !!(v.over_scope && v.over_scope.flag === true) })))
-      const scope = scopeRecord(verdicts)
-      state.critique = { verdict: safety || objections.length * 2 > verdicts.length ? 'OBJECT' : concerns.length ? 'ENDORSE_WITH_CONCERNS' : 'ENDORSE', concerns: concerns.length }
-      // RECORD-ONLY: attached after the verdict is computed, never spread
-      // into the rollup literal above, so the verdict expression provably
-      // cannot consult it. Omitted entirely when no member judged scope.
-      if (scope) state.critique.over_scope = scope
-      state.events.push({ scope: slice.id, type: 'council-verdict', payload: { verdict: state.critique.verdict, panel: panel.map(p => p[0]), safety: !!safety, concerns_folded: concerns.filter(c => c.disposition_hint === 'fold').length, deferred: concerns.filter(c => c.disposition_hint === 'defer').map(c => c.text), ...(scope ? { over_scope: scope } : {}) } })
-      state.deferred = concerns.filter(c => c.disposition_hint === 'defer').map(c => c.text)
-      deferralEvents(slice, concerns).forEach(e => state.events.push(e))
-      if (splitRec && slice.depth < 2 && state.critique.verdict !== 'OBJECT') return done('SPLIT', { split: { children: splitRec.split.children } })
-      if (state.critique.verdict === 'OBJECT') {
-        const ob = (safety || objections[0])
-        const answered = (A.answers || {})[`${slice.id}:council-objection`]
-        if (!answered) {
-          if (!safety && ob.fixable_by_replan && !state.replanned) {
-            state.replanned = true
-            const revised = await dispatch(slice, state, 'replan', replanPrompt(slice, plan, ob), { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
-            if (revised && revised.status === 'PLANNED') { plan = revised }
-            else return escalated(slice, state, esc(slice, 'council-objection', `council objects: ${ob.objection.reason.slice(0, 60)}`, ob.objection.reason, ob.objection.question, [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }]))
-          } else {
-            return escalated(slice, state, esc(slice, 'council-objection', `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, ob.objection.reason, ob.objection.question, [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }]))
-          }
-        }
-        // answered → proceed; the answer is already injected into downstream prompts via answerFor()
-      }
-    }
-
-    // Stage T — sequential task implementation
-    const LANE = { transcribe: { model: 'haiku', effort: 'low' }, standard: { model: 'sonnet', effort: 'medium' }, judgment: { model: 'inherit', effort: 'high' } }
-    const touched = []
-    for (const task of plan.tasks || []) {
-      let r = await dispatch(slice, state, `task:${task.id}`, taskPrompt(slice, plan, task, null), { agentType: 'spec-loop:implementer', schema: TASK_RESULT, ...LANE[task.lane] })
-      if (!r || r.status === 'NEEDS_CONTEXT' || r.status === 'BLOCKED') {
-        const lift = task.lane === 'transcribe' ? LANE.standard : LANE.judgment
-        r = await dispatch(slice, state, `task:${task.id}:retry`, taskPrompt(slice, plan, task, r || { status: 'BLOCKED', blocker: 'terminal dispatch failure' }), { agentType: 'spec-loop:implementer', schema: TASK_RESULT, ...lift })
-      }
-      if (!r || r.status === 'NEEDS_CONTEXT' || r.status === 'BLOCKED')
-        return escalated(slice, state, esc(slice, 'ambiguity', `task ${task.id} blocked`, (r && (r.blocker || (r.questions || []).join(' · '))) || 'terminal dispatch failure', `Task "${task.title}" cannot proceed. How should it resolve?`, []))
-      state.tasksCompleted++
-      // TASK_RESULT requires only status/touched_files/concerns/deviations, so a
-      // task that legitimately changed nothing returns DONE with `commits`
-      // absent. Reading it unguarded threw a TypeError that the catch-all below
-      // re-labelled as a budget-exhausted 'wave interrupted' — run
-      // 20260825-scope-ceiling lost a wave to it after all five tasks had
-      // already committed. Guarded the way the fix and debug-fix sites already
-      // guard the identical access; `head` keeps its previous value, so a
-      // slice where NO task committed still leaves it null and falls into the
-      // 'plan produced no commits' escalation below.
-      const c = (r.commits && typeof r.commits === 'object') ? r.commits : {}
-      if (c.head) state.commits.head = c.head
-      if (state.commits.base === null && c.base) state.commits.base = c.base
-      touched.push(...(r.touched_files || []))
-      state.implConcerns.push(...(r.concerns || []), ...(r.deviations || []).map(d => `deviation: ${d}`))
-    }
-    if (!state.commits.head)
-      return escalated(slice, state, esc(slice, 'ambiguity', 'plan produced no commits', 'All tasks completed but no commit was recorded.', 'Drop the slice or retry?', []))
-
-    // Deterministic tier promotion: implementation touched a Tier-3 surface
-    if (state.review_tier < 3 && touchesTier3Surface(touched, CTX.tier3_surfaces)) {
-      state.review_tier = 3
-      state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `review tier promoted to 3: diff touches tier3 surface`, rationale: 'deterministic surface-glob match', reversibility: 'n/a' } })
-    }
-
-    // Stage R — review ∥ quality gate
-    guard(slice, state)
-    const reviewers = state.review_tier >= 3
-      ? [['review:correctness', 'correctness + errors + risk', { model: 'inherit', effort: 'high' }], ['review:tests', 'tests + types + design + comments + conventions', { model: 'sonnet', effort: 'high' }]]
-      : [['review:full', null, state.review_tier === 1 ? { model: CTX.models?.reviewer || 'sonnet', effort: 'low' } : { model: CTX.models?.reviewer || 'inherit', effort: 'medium' }]]
-    const [reviewParts, gate] = await parallel([
-      () => parallel(reviewers.map(([role, lanes, opts]) => () =>
-        dispatch(slice, state, role, reviewPrompt(slice, plan, state, lanes), { agentType: 'spec-loop:pr-reviewer', schema: REVIEW_RESULT, ...opts }))),
-      () => dispatch(slice, state, 'gate', gatePrompt(slice, state), { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' }),
-    ])
-    let review = {
-      findings: reviewParts.filter(Boolean).flatMap((r, i) => r.findings.map(f => ({ ...f, id: `r${i}-${f.id}` }))),
-      summary: reviewParts.filter(Boolean).map(r => r.summary).join(' | ') || 'review dispatch failed (fail closed)',
-    }
-    if (reviewParts.some(r => !r)) review.findings.push({ id: 'failclosed-review', severity: 'P0', category: 'correctness', file: '-', line: 0, claim: 'a reviewer dispatch returned no result — review incomplete (fail closed)', evidence: { quote: 'n/a' }, remedy: 'resume to re-run the review', confidence: 'high', outside_diff: true })
-    const gateStatus = qualityStatus(gate && gate.quality)
-    const gateViolations = (gateStatus === 'FAIL' && gate) ? (gate.quality.violations || []).map((v, i) => ({ id: `qg-${i}`, severity: 'P1', category: 'quality-gate', file: v.file || '-', line: 0, claim: `${v.metric} ${v.value} > threshold ${v.threshold} in ${v.function || v.file}`, evidence: { quote: JSON.stringify(v) }, remedy: 'behavior-preserving refactor (extract method, guard clauses, parameter object)', confidence: 'high', outside_diff: false })) : []
-    state.quality = gate ? { status: gateStatus, detail: gate.quality.detail || `${gateViolations.length} violation(s)` } : { status: 'FAIL', detail: 'gate dispatch failed (fail closed)' }
-    state.events.push({ scope: slice.id, type: 'quality-gate', payload: { status: state.quality.status, violations: gateViolations.length } })
-
-    // Stage V/F — verify findings + fix loop (≤2 rounds)
-    const bar = state.review_tier === 1 ? 'P0' : 'P0+P1'
-    let open = [...blocking(review.findings, bar), ...gateViolations]
-    for (let round = 0; open.length && round < MAX_FIX_ROUNDS; round++) {
-      if (state.review_tier >= 3) {
-        const v = await dispatch(slice, state, 'verify-findings', verifierBatchPrompt(slice, state, open), { agentType: 'spec-loop:finding-verifier', schema: VERIFIER_RESULT, model: 'sonnet', effort: 'low' })
-        const refuted = new Set(((v && v.verdicts) || []).filter(x => x.verdict === 'REFUTED').map(x => x.finding_id))
-        state.review.refuted += refuted.size
-        refuted.forEach(id => state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `finding ${id} refuted by batched verifier`, rationale: (v.verdicts.find(x => x.finding_id === id) || {}).evidence || '', reversibility: 'n/a' } }))
-        open = open.filter(f => !refuted.has(f.id))
-        if (!open.length) break
-      }
-      state.review.confirmed = open.length
-      state.review.fix_rounds = round + 1
-      const fix = await dispatch(slice, state, `fix:${round + 1}`, fixPrompt(slice, plan, state, open), { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: round === 0 ? 'sonnet' : 'inherit', effort: 'medium' })
-      if (!fix || fix.status === 'BLOCKED')
-        return escalated(slice, state, esc(slice, 'review-block', 'fix agent blocked', (fix && fix.blocker) || 'terminal dispatch failure', 'Blocking findings cannot be fixed automatically. Accept, guide, or drop?', []))
-      if (fix.commits && fix.commits.head) state.commits.head = fix.commits.head
-      const rr = await dispatch(slice, state, `re-review:${round + 1}`, reReviewPrompt(slice, state, open, fix), { agentType: 'spec-loop:re-reviewer', schema: REREVIEW_RESULT, model: 'sonnet', effort: 'low' })
-      if (!rr) { continue } // fail closed: findings stay open into the next round / escalation
-      state.review.refuted += rr.verdicts.filter(x => x.verdict === 'REFUTATION_ACCEPTED').length
-      const closed = new Set(rr.verdicts.filter(x => x.verdict === 'ADDRESSED' || x.verdict === 'REFUTATION_ACCEPTED').map(x => x.finding_id))
-      open = [...open.filter(f => !closed.has(f.id)), ...blocking(rr.new_breakage, bar).map((f, i) => ({ ...f, id: `nb${round}-${i}` }))]
-      // escape hatch: fix touched files outside the reviewed diff → full re-review next round is the residual's problem; record it
-      const outside = fix.touched_files.filter(f => !review.findings.some(x => x.file === f) && !(plan.tasks || []).some(t => t.files.includes(f)))
-      if (outside.length) state.events.push({ scope: slice.id, type: 'review-summary', payload: { note: `fix round ${round + 1} touched files outside the original diff: ${outside.join(', ')}`, requires_full_rereview: true } })
-    }
-    if (open.length)
-      return escalated(slice, state, esc(slice, open.some(f => f.category === 'quality-gate') ? 'quality-gate-block' : 'review-block', `${open.length} blocking finding(s) unresolved after ${MAX_FIX_ROUNDS} fix rounds`, open.map(f => `${f.severity} ${f.file}:${f.line} — ${f.claim}`).join('\n'), 'Accept the residual findings, provide guidance, or drop the slice?', []))
-    state.review.residual = review.findings.filter(f => !blocking([f], bar).length).map(f => `${f.severity}: ${f.claim}`).slice(0, 10)
-    state.events.push({ scope: slice.id, type: 'review-summary', payload: { findings: review.findings.length, confirmed: state.review.confirmed, refuted: state.review.refuted, fix_rounds: state.review.fix_rounds, reviewers: reviewers.length } })
-
-    // Stage S — simplify polish (tier 3 / thorough, non-blocking)
-    if (state.review_tier >= 3 && CTX.polish !== false)
-      await dispatch(slice, state, 'simplify', simplifyPrompt(slice, state), { agentType: 'spec-loop:simplifier', model: 'sonnet', effort: 'low' }).then(() => {}, () => {})
-
-    // Stage Z — full verification (suite + gate re-check), ≤1 debug-fix
-    for (let attempt = 0; attempt < 2; attempt++) {
-      const v = await dispatch(slice, state, `verify:${attempt + 1}`, verifyPrompt(slice, state), { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' })
-      if (v && v.suite.passed && qualityStatus(v.quality) === 'PASS') {
-        state.tests = { command: v.suite.command, result: v.suite.summary, scope: 'full', tree_sha: v.tree_sha }
-        state.quality = { status: 'PASS', detail: v.quality.detail || state.quality.detail }
-        state.commits.head = v.head_sha
-        return done('DONE')
-      }
-      if (attempt === 0 && v && !v.suite.passed) {
-        const df = await dispatch(slice, state, 'debug-fix', debugFixPrompt(slice, plan, state, v), { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: 'inherit', effort: 'high' })
-        if (df && df.commits && df.commits.head) state.commits.head = df.commits.head
-        continue
-      }
-      return escalated(slice, state, esc(slice, v && !v.suite.passed ? 'review-block' : 'quality-gate-block', 'verification failed', v ? `suite: ${v.suite.summary}; quality: ${qualityStatus(v.quality)} (summary_pass=${String(v.quality.summary_pass)}${v.quality.detail ? ` — ${v.quality.detail}` : ''})` : 'verifier dispatch failed terminally', 'Verification cannot pass automatically. Guide, accept, or drop?', []))
-    }
-    return escalated(slice, state, esc(slice, 'review-block', 'verification loop exhausted', 'unreachable', 'Guide, accept, or drop?', []))
+    return await runStages(slice, state)
   } catch (e) {
-    if (e && e.escRecord) return escalated(slice, state, e.escRecord)
-    return escalated(slice, state, esc(slice, 'budget-exhausted', 'wave interrupted', String((e && e.message) || e), 'The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?', []))
+    return runSliceError(slice, state, e)
   }
 }
 
 // ── Wave entry ───────────────────────────────────────────────────────────────
