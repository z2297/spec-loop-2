export const meta = {
  name: 'slice-wave',
  description: 'Execute one spec-loop wave: each slice runs plan → critique → implement → review∥gate → fix → verify as deterministic control flow',
  whenToUse: 'Invoked by the /spec-loop controller once per wave with {run_id, wave_index, ctx, slices, answers}. Never invoke directly.',
}

// ─────────────────────────────────────────────────────────────────────────────
// spec-loop 2 wave workflow.
//
// One invocation = one wave. Slices are plain async JS functions run under
// parallel() — the orchestration that v1 spent a session-model agent on is
// deterministic code here. Everything an agent needs arrives as an absolute
// file path; every LLM→LLM handoff is a schema-forced structured return.
//
// Hard rules this file owns (single home):
//   - loop bounds: replan ≤1, task retry ≤1, fix rounds ≤2, debug-fix ≤1
//   - per-slice agent caps by review tier: 10 / 18 / 32
//   - fail-closed synthesis: an unusable agent return is never an approval
//   - answers injection: args.answers["<sliceId>:<trigger>"] resumes an
//     escalated stage; unchanged stages replay from the journal cache
//
// The controller stamps timestamps and persists results (run_state.py) —
// this script has no clock and no filesystem, by design.
// ─────────────────────────────────────────────────────────────────────────────

// Tolerate stringified args: some harness paths deliver the args value
// JSON-encoded even when the caller passed an object (verified 2026-07-30).
const A = typeof args === 'string' ? JSON.parse(args) : args
const CTX = A.ctx // {run_dir, plugin_root, base_ref, test_command, conventions_path, shared_constraints[], tier3_surfaces[], quality_gate_cmd, models{reviewer}, thorough, polish}

const CAPS = { 1: 10, 2: 18, 3: 32 }
const MAX_FIX_ROUNDS = 2
const BUDGET_STAGE_FLOOR = 60_000 // skip-and-escalate below this remaining budget

// ── Schemas ──────────────────────────────────────────────────────────────────

const ESCALATION = {
  type: 'object', additionalProperties: false,
  properties: {
    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'budget-exhausted'] },
    title: { type: 'string' }, context: { type: 'string' }, question: { type: 'string' },
    options: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { label: { type: 'string' }, detail: { type: 'string' }, recommended: { type: 'boolean' } }, required: ['label', 'detail'] } },
  },
  required: ['trigger', 'title', 'context', 'question', 'options'],
}

const PLAN_RESULT = {
  type: 'object', additionalProperties: false,
  properties: {
    status: { enum: ['PLANNED', 'SPLIT', 'ESCALATE'] },
    plan_path: { type: 'string' },
    tasks: { type: 'array', maxItems: 10, items: { type: 'object', additionalProperties: false, properties: { id: { type: 'string' }, title: { type: 'string' }, lane: { enum: ['transcribe', 'standard', 'judgment'] }, files: { type: 'array', items: { type: 'string' } } }, required: ['id', 'title', 'lane', 'files'] } },
    split: { type: 'object', additionalProperties: false, properties: { children: { type: 'array', minItems: 2, items: { type: 'object', additionalProperties: false, properties: { goal: { type: 'string' }, files: { type: 'array', items: { type: 'string' } }, subsystems: { type: 'array', items: { type: 'string' } }, internal_deps: { type: 'array', items: { type: 'integer' } } }, required: ['goal', 'files', 'subsystems', 'internal_deps'] } } }, required: ['children'] },
    escalation: ESCALATION,
  },
  required: ['status'],
}

const CRITIQUE = {
  type: 'object', additionalProperties: false,
  properties: {
    verdict: { enum: ['ENDORSE', 'ENDORSE_WITH_CONCERNS', 'OBJECT'] },
    mandates: { type: 'object' },
    safety: { type: 'object', additionalProperties: false, properties: { flag: { type: 'boolean' }, reason: { type: ['string', 'null'] } }, required: ['flag'] },
    split: { type: 'object', additionalProperties: false, properties: { recommended: { type: 'boolean' }, children: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { goal: { type: 'string' }, files: { type: 'array', items: { type: 'string' } }, subsystems: { type: 'array', items: { type: 'string' } }, internal_deps: { type: 'array', items: { type: 'integer' } } }, required: ['goal', 'files', 'subsystems', 'internal_deps'] } } }, required: ['recommended'] },
    fixable_by_replan: { type: 'boolean' },
    objection: { type: 'object', additionalProperties: false, properties: { reason: { type: 'string' }, question: { type: 'string' }, recommendation: { type: 'string' } }, required: ['reason', 'question', 'recommendation'] },
    concerns: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { text: { type: 'string' }, disposition_hint: { enum: ['fold', 'defer'] } }, required: ['text', 'disposition_hint'] } },
  },
  required: ['verdict', 'safety', 'concerns'],
}

const TASK_RESULT = {
  type: 'object', additionalProperties: false,
  properties: {
    status: { enum: ['DONE', 'DONE_WITH_CONCERNS', 'NEEDS_CONTEXT', 'BLOCKED'] },
    commits: { type: 'object', additionalProperties: false, properties: { base: { type: 'string' }, head: { type: 'string' } }, required: ['base', 'head'] },
    touched_files: { type: 'array', items: { type: 'string' } },
    tests: { type: 'object', additionalProperties: false, properties: { command: { type: 'string' }, result: { type: 'string' } }, required: ['command', 'result'] },
    concerns: { type: 'array', items: { type: 'string' } },
    deviations: { type: 'array', items: { type: 'string' } },
    questions: { type: 'array', items: { type: 'string' } },
    blocker: { type: 'string' },
  },
  required: ['status', 'touched_files', 'concerns', 'deviations'],
}

const FINDING = {
  type: 'object', additionalProperties: false,
  properties: {
    id: { type: 'string' }, severity: { enum: ['P0', 'P1', 'P2', 'P3'] },
    category: { enum: ['correctness', 'errors', 'tests', 'types', 'comments', 'conventions', 'design', 'simplify', 'quality-gate'] },
    file: { type: 'string' }, line: { type: 'integer' },
    claim: { type: 'string' },
    evidence: { type: 'object', additionalProperties: false, properties: { quote: { type: 'string' }, refs: { type: 'array', items: { type: 'string' } } }, required: ['quote'] },
    remedy: { type: 'string' }, confidence: { enum: ['high', 'medium', 'low'] },
    outside_diff: { type: 'boolean' },
  },
  required: ['id', 'severity', 'category', 'file', 'line', 'claim', 'evidence', 'remedy', 'confidence'],
}

const REVIEW_RESULT = {
  type: 'object', additionalProperties: false,
  properties: {
    verdict: { enum: ['APPROVE', 'APPROVE_WITH_FINDINGS', 'BLOCK'] },
    findings: { type: 'array', items: FINDING },
    aspects_examined: { type: 'object' },
    tier_escalation_recommended: { type: 'boolean' },
    summary: { type: 'string' },
  },
  required: ['verdict', 'findings', 'aspects_examined', 'summary'],
}

const VERIFIER_RESULT = {
  type: 'object', additionalProperties: false,
  properties: { verdicts: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { finding_id: { type: 'string' }, verdict: { enum: ['CONFIRMED', 'REFUTED'] }, evidence: { type: 'string' } }, required: ['finding_id', 'verdict'] } } },
  required: ['verdicts'],
}

const FIX_RESULT = {
  type: 'object', additionalProperties: false,
  properties: {
    status: { enum: ['DONE', 'DONE_WITH_CONCERNS', 'BLOCKED'] },
    commits: { type: 'object', additionalProperties: false, properties: { base: { type: 'string' }, head: { type: 'string' } }, required: ['base', 'head'] },
    touched_files: { type: 'array', items: { type: 'string' } },
    addressed: { type: 'array', items: { type: 'string' } },
    refuted: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { finding_id: { type: 'string' }, evidence: { type: 'string' } }, required: ['finding_id', 'evidence'] } },
    tests: { type: 'object', additionalProperties: false, properties: { command: { type: 'string' }, result: { type: 'string' } }, required: ['command', 'result'] },
    blocker: { type: 'string' },
  },
  required: ['status', 'touched_files', 'addressed', 'refuted'],
}

const REREVIEW_RESULT = {
  type: 'object', additionalProperties: false,
  properties: {
    verdicts: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { finding_id: { type: 'string' }, verdict: { enum: ['ADDRESSED', 'NOT_ADDRESSED', 'REFUTATION_ACCEPTED'] }, note: { type: 'string' } }, required: ['finding_id', 'verdict'] } },
    new_breakage: { type: 'array', items: FINDING },
  },
  required: ['verdicts', 'new_breakage'],
}

const VERIFY_RESULT = {
  type: 'object', additionalProperties: false,
  properties: {
    suite: { type: 'object', additionalProperties: false, properties: { command: { type: 'string' }, passed: { type: 'boolean' }, summary: { type: 'string' } }, required: ['command', 'passed', 'summary'] },
    // summary_pass is the gate JSON's summary.pass transcribed verbatim (null
    // only when the gate produced no parseable JSON). The PASS/FAIL enum the
    // sidecar carries is computed by qualityStatus() below, never self-labeled:
    // agent self-labels produced two false PASSes in run 20260807.
    quality: { type: 'object', additionalProperties: false, properties: { summary_pass: { type: ['boolean', 'null'] }, violations: { type: 'array', items: { type: 'object' } }, detail: { type: 'string' } }, required: ['summary_pass', 'violations'] },
    changed_files: { type: 'array', items: { type: 'string' } },
    head_sha: { type: 'string' }, tree_sha: { type: 'string' },
  },
  required: ['suite', 'quality', 'head_sha', 'tree_sha'],
}

// ── Small pure helpers ───────────────────────────────────────────────────────

function globToRe(glob) {
  let re = ''
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i]
    if (c === '*') {
      if (glob[i + 1] === '*') { re += '.*'; i++; if (glob[i + 1] === '/') i++ }
      else re += '[^/]*'
    } else if ('.+^$()|[]{}\\?'.includes(c)) re += '\\' + c
    else re += c
  }
  return new RegExp('^(?:.*/)?' + re + '$')
}

function touchesTier3Surface(files, surfaces) {
  const res = (surfaces || []).map(globToRe)
  return files.some(f => res.some(r => r.test(f)))
}

function blocking(findings, bar) {
  const block = bar === 'P0' ? ['P0'] : ['P0', 'P1']
  return findings.filter(f => block.includes(f.severity))
}

// Deterministic gate verdict: PASS requires summary.pass === true AND zero
// violations. A missing return, a null summary_pass (gate never produced
// JSON), or a true/violations contradiction is FAIL — fail closed.
function qualityStatus(q) {
  if (!q) return 'FAIL'
  if ((q.violations || []).length) return 'FAIL'
  return q.summary_pass === true ? 'PASS' : 'FAIL'
}

function esc(slice, trigger, title, context, question, options) {
  return {
    id: `${slice.id}:${trigger}`,
    trigger, title, context, question,
    options: options && options.length ? options : [{ label: 'Proceed with the recommended default', detail: context, recommended: true }],
    if_unanswered: 'pause this slice; continue all independent slices',
    status: 'OPEN',
  }
}

function escalated(slice, state, record) {
  state.escalations.push(record)
  return {
    schema_version: 2, id: slice.id, status: 'ESCALATED',
    branch: slice.branch, commits: state.commits, risk_tier: slice.risk_tier,
    review_tier: state.review_tier, critique: state.critique,
    tasks_completed: state.tasksCompleted, review: state.review,
    tests: state.tests, quality: state.quality,
    escalations: state.escalations, agents_used: state.agentsUsed, wave: A.wave_index,
    events: state.events,
  }
}

// ── Prompt builders (pure functions of args + prior returns) ─────────────────

const packet = (slice) => [
  `Worktree (do all work here, absolute path): ${slice.worktree}`,
  `Branch: ${slice.branch} (already checked out in the worktree; never switch or push)`,
  `Run dir: ${CTX.run_dir}`,
  `Conventions: ${CTX.conventions_path}`,
  `Shared constraints (binding, verbatim):\n${(CTX.shared_constraints || []).map(c => `- ${c}`).join('\n') || '- none'}`,
  slice.kg_snippet ? `Prior knowledge (graph context):\n${slice.kg_snippet}` : '',
].filter(Boolean).join('\n')

const answerFor = (slice, trigger) => {
  const a = (A.answers || {})[`${slice.id}:${trigger}`]
  return a ? `\nHUMAN ANSWER to your earlier "${trigger}" escalation (apply it, do not re-raise): ${a}` : ''
}

function planPrompt(slice) {
  return `${packet(slice)}

Plan slice ${slice.id} of run ${A.run_id}: ${slice.goal}
Named files: ${slice.files.join(', ') || '(none named)'} · Subsystems: ${slice.subsystems.join(', ') || '—'}
Risk tier: ${slice.risk_tier} · Split depth: ${slice.depth} (split allowed only below depth 2)
Write the plan to exactly: ${CTX.run_dir}/plans/${slice.id}.md
Test/build command for verification steps: ${CTX.test_command}${answerFor(slice, 'ambiguity')}${answerFor(slice, 'material-assumption')}`
}

function criticPrompt(slice, plan, role) {
  return `${packet(slice)}

Mode: plan. Review the plan for slice ${slice.id} (goal: ${slice.goal}) at ${plan.plan_path}.
Risk tier ${slice.risk_tier}.${role ? ` Your lane on this panel: ${role} only.` : ' You are the full council: all five mandates.'}${answerFor(slice, 'council-objection')}`
}

function replanPrompt(slice, plan, verdict) {
  return `${planPrompt(slice)}

REVISION PASS. Your previous plan is at ${plan.plan_path}. The plan critic OBJECTED:
${verdict.objection.reason}
Required remedy: ${verdict.objection.recommendation}
Concerns to fold in: ${verdict.concerns.filter(c => c.disposition_hint === 'fold').map(c => c.text).join(' · ') || 'none'}
Rewrite the plan at the same path resolving the objection. Return PLANNED (or ESCALATE if the objection genuinely needs a human).`
}

function taskPrompt(slice, plan, task, retry) {
  return `${packet(slice)}

Mode: task. Implement task ${task.id} ("${task.title}") of the plan at ${plan.plan_path}.
Your scope is this one task; the plan is context. Expected files: ${task.files.join(', ')}.
Covering tests: derive from your touched files; full command if unsure: ${CTX.test_command}
Commit in the worktree when green.${retry ? `\nRETRY: the previous attempt returned ${retry.status}${retry.blocker ? ` — ${retry.blocker}` : ''}${(retry.questions || []).length ? `; answers: ${retry.questions.map(q => `${q} → resolve from the plan/conventions; if genuinely impossible, BLOCKED`).join(' · ')}` : ''}. Something must change this attempt.` : ''}`
}

function packageCmd(slice, base, head, roundTag) {
  return `python3 "${CTX.plugin_root}/scripts/review_package.py" --repo-dir "${slice.worktree}" --base ${base} --head ${head} --out "${CTX.run_dir}/packages/${slice.id}-${roundTag}.md"`
}

function reviewPrompt(slice, plan, state, lanes) {
  return `${packet(slice)}

Mode: slice. Review the diff of slice ${slice.id} (plan: ${plan.plan_path}).
Build the package first by running exactly:
  ${packageCmd(slice, state.commits.base, state.commits.head, `round${state.review.fix_rounds + 1}`)}
then read it from the --out path. Range: ${state.commits.base}..${state.commits.head}.
Review tier: ${state.review_tier} · Blocking bar: ${state.review_tier === 1 ? 'P0' : 'P0+P1'}.${lanes ? `\nThis is a two-reviewer panel; your lanes ONLY: ${lanes}.` : ''}
Implementer concerns to verify: ${state.implConcerns.join(' · ') || 'none'}${answerFor(slice, 'review-block')}`
}

function gatePrompt(slice, state) {
  return `${packet(slice)}

Reporter mode, quality gate ONLY (no test suite this dispatch). In the worktree run exactly:
  ${CTX.quality_gate_cmd} --base ${state.commits.base} --head ${state.commits.head} --repo-dir "${slice.worktree}"
Read the JSON output. Also run: git -C "${slice.worktree}" diff --name-only ${state.commits.base}..${state.commits.head}
Return quality {summary_pass: the gate JSON's summary.pass copied verbatim — null ONLY if the gate never produced parseable JSON (say why in detail), violations: its summary.failures array verbatim, detail}, changed_files, plus head_sha/tree_sha (git rev-parse HEAD / HEAD^{tree}). You never return a PASS/FAIL label — the workflow computes it. Set suite to {command:"skipped", passed:true, summary:"gate-only dispatch"}.`
}

function verifierBatchPrompt(slice, state, confirmed) {
  return `${packet(slice)}

Adversarially verify EVERY finding below against the actual code. Package: ${CTX.run_dir}/packages/${slice.id}-round${state.review.fix_rounds + 1}.md (read once). First do the mechanical check: a finding whose file:line is outside the package's hunk-index ranges (and not marked outside_diff) or whose evidence quote does not appear in the package/file is REFUTED with that as evidence. Then judge substance. CONFIRMED is your default; REFUTED requires quoted counter-evidence.
Findings:
${JSON.stringify(confirmed, null, 1)}`
}

function fixPrompt(slice, plan, state, findings) {
  return `${packet(slice)}

Mode: fix. Address EVERY finding below (plan for context: ${plan.plan_path}).
Package for anchor checks: ${CTX.run_dir}/packages/${slice.id}-round${state.review.fix_rounds + 1}.md — a finding whose location/quote does not match the code may be REFUTED with file:line counter-evidence instead of a change. quality-gate findings: behavior-preserving refactors only.
Covering tests + commit when done.${answerFor(slice, 'quality-gate-block')}
Findings:
${JSON.stringify(findings, null, 1)}`
}

function reReviewPrompt(slice, state, findings, fix) {
  return `${packet(slice)}

Re-review after a fix round for slice ${slice.id}. Build the fix-only package:
  ${packageCmd(slice, fix.commits.base, fix.commits.head, `fix${state.review.fix_rounds}`)}
Prior blocking findings (verdict each): ${JSON.stringify(findings, null, 1)}
Fixer refutations to adjudicate: ${JSON.stringify(fix.refuted, null, 1)}`
}

function verifyPrompt(slice, state) {
  return `${packet(slice)}

Reporter mode, full verification. In the worktree run the full suite exactly: ${CTX.test_command}
(a " ; "-joined command is a segment list: run each segment as its own tool call, in order, all to completion; the suite passed only if every segment passed)
Then the quality gate exactly:
  ${CTX.quality_gate_cmd} --base ${state.commits.base} --head HEAD --repo-dir "${slice.worktree}"
Read both outputs; report what they actually say. quality.summary_pass is the gate JSON's summary.pass copied verbatim (null ONLY if the gate never produced parseable JSON — say why in detail); quality.violations is its summary.failures array verbatim; you never return a PASS/FAIL label. changed_files from git diff --name-only ${state.commits.base}..HEAD.${answerFor(slice, 'quality-gate-block')}`
}

function debugFixPrompt(slice, plan, state, verify) {
  return `${packet(slice)}

Mode: fix. The full suite is RED after all scoped runs were green — find the root cause before changing anything (attribute via the per-task commits: git -C "${slice.worktree}" log --oneline ${state.commits.base}..HEAD). Suite output summary: ${verify.suite.summary}
Plan: ${plan.plan_path}. Fix the root cause, run the full suite (${CTX.test_command}), commit. Return DONE only with fresh green output you read; otherwise BLOCKED with what you found.`
}

function simplifyPrompt(slice, state) {
  return `${packet(slice)}

Polish the diff ${state.commits.base}..HEAD in the worktree: behavior-preserving clarity/maintainability only. Run covering tests before committing. Non-blocking: if nothing is worth changing, change nothing.`
}

// ── Guarded dispatch ─────────────────────────────────────────────────────────

function guard(slice, state) {
  if (state.agentsUsed >= CAPS[state.review_tier])
    throw { escRecord: esc(slice, 'budget-exhausted', `agent cap reached (${CAPS[state.review_tier]})`, `Slice used ${state.agentsUsed} agents (tier ${state.review_tier} cap).`, 'Raise the cap and resume, accept the slice as-is, or drop it?', []) }
  if (budget.total && budget.remaining() < BUDGET_STAGE_FLOOR)
    throw { escRecord: esc(slice, 'budget-exhausted', 'token budget exhausted', `Wave budget remaining ${Math.round(budget.remaining() / 1000)}k is below the ${BUDGET_STAGE_FLOOR / 1000}k stage floor.`, 'Raise the budget and resume, accept committed work as-is, or drop the slice?', []) }
}

async function dispatch(slice, state, role, prompt, opts) {
  guard(slice, state)
  state.agentsUsed++
  const r = await agent(prompt, { ...opts, label: `${slice.id}:${role}`, phase: `wave ${A.wave_index}` })
  state.events.push({ scope: slice.id, type: 'agent-dispatch', payload: { role, model: opts.model || 'inherit', effort: opts.effort || null, agent_type: opts.agentType || null } })
  return r // null on user-skip/terminal error — callers fail closed
}

// ── The slice pipeline ───────────────────────────────────────────────────────

async function runSlice(slice) {
  const state = {
    agentsUsed: 0, events: [], escalations: [],
    review_tier: Math.max(slice.risk_tier, CTX.thorough ? Math.min(slice.risk_tier + 1, 3) : slice.risk_tier),
    critique: { verdict: 'SKIPPED', concerns: 0 },
    commits: { base: slice.base_sha, head: null },
    tasksCompleted: 0, implConcerns: [],
    review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
    tests: null, quality: { status: 'SKIPPED', detail: 'not reached' },
  }
  const done = (status, extra) => ({
    schema_version: 2, id: slice.id, status,
    branch: slice.branch, commits: state.commits, risk_tier: slice.risk_tier,
    review_tier: state.review_tier, critique: state.critique,
    tasks_completed: state.tasksCompleted, review: state.review,
    tests: state.tests, quality: state.quality, escalations: state.escalations,
    agents_used: state.agentsUsed, wave: A.wave_index, events: state.events, ...extra,
  })

  try {
    // Stage P — plan (+ right-size gate inside the planner)
    let plan = await dispatch(slice, state, 'plan', planPrompt(slice),
      { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
    if (!plan) return escalated(slice, state, esc(slice, 'ambiguity', 'planner returned no result', 'The planner dispatch failed terminally.', 'Retry the slice, or drop it?', []))
    if (plan.status === 'SPLIT') return done('SPLIT', { split: plan.split })
    if (plan.status === 'ESCALATE') return escalated(slice, state, { ...esc(slice, plan.escalation.trigger, plan.escalation.title, plan.escalation.context, plan.escalation.question, plan.escalation.options), id: `${slice.id}:${plan.escalation.trigger}` })

    // Stage C — critique (tier ≥ 2)
    if (state.review_tier >= 2) {
      const panel = state.review_tier >= 3
        ? (CTX.thorough
          ? [['full-council', 'spec-loop:plan-critic', 'inherit', 'high', null], ['risk', 'spec-loop:guardian', 'inherit', 'high', 'risk'], ['premise', 'spec-loop:skeptic', 'sonnet', 'high', 'premise']]
          : [['full-council', 'spec-loop:plan-critic', 'inherit', 'high', null], ['risk', 'spec-loop:guardian', 'inherit', 'high', 'risk']])
        : [['full-council', 'spec-loop:plan-critic', 'inherit', 'low', null]]
      guard(slice, state)
      const verdicts = (await parallel(panel.map(([role, agentType, model, effort, lane]) => () =>
        dispatch(slice, state, `critic:${role}`, criticPrompt(slice, plan, lane), { agentType, schema: CRITIQUE, model, effort }))))
        .map(v => v || { verdict: 'OBJECT', safety: { flag: false, reason: null }, concerns: [], objection: { reason: 'unreadable critic verdict (fail closed)', question: 'The plan critique could not be completed. Proceed anyway, or retry?', recommendation: 'retry the slice' }, fixable_by_replan: false })
      const objections = verdicts.filter(v => v.verdict === 'OBJECT')
      const safety = verdicts.find(v => v.safety.flag)
      const splitRec = verdicts.find(v => v.split && v.split.recommended && (v.split.children || []).length >= 2)
      const concerns = verdicts.flatMap(v => v.concerns)
      state.critique = { verdict: safety || objections.length * 2 > verdicts.length ? 'OBJECT' : concerns.length ? 'ENDORSE_WITH_CONCERNS' : 'ENDORSE', concerns: concerns.length }
      state.events.push({ scope: slice.id, type: 'council-verdict', payload: { verdict: state.critique.verdict, panel: panel.map(p => p[0]), safety: !!safety, concerns_folded: concerns.filter(c => c.disposition_hint === 'fold').length, deferred: concerns.filter(c => c.disposition_hint === 'defer').map(c => c.text) } })
      if (splitRec && slice.depth < 2 && state.critique.verdict !== 'OBJECT') return done('SPLIT', { split: { children: splitRec.split.children } })
      if (state.critique.verdict === 'OBJECT') {
        const ob = (safety || objections[0])
        const answered = (A.answers || {})[`${slice.id}:council-objection`]
        if (!answered) {
          if (!safety && ob.fixable_by_replan && !state.replanned) {
            state.replanned = true
            const revised = await dispatch(slice, state, 'replan', replanPrompt(slice, plan, ob), { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
            if (revised && revised.status === 'PLANNED') { plan = revised }
            else return escalated(slice, state, esc(slice, 'council-objection', `council objects: ${ob.objection.reason.slice(0, 60)}`, ob.objection.reason, ob.objection.question, [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }]))
          } else {
            return escalated(slice, state, esc(slice, 'council-objection', `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, ob.objection.reason, ob.objection.question, [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }]))
          }
        }
        // answered → proceed; the answer is already injected into downstream prompts via answerFor()
      }
    }

    // Stage T — sequential task implementation
    const LANE = { transcribe: { model: 'haiku', effort: 'low' }, standard: { model: 'sonnet', effort: 'medium' }, judgment: { model: 'inherit', effort: 'high' } }
    const touched = []
    for (const task of plan.tasks || []) {
      let r = await dispatch(slice, state, `task:${task.id}`, taskPrompt(slice, plan, task, null), { agentType: 'spec-loop:implementer', schema: TASK_RESULT, ...LANE[task.lane] })
      if (!r || r.status === 'NEEDS_CONTEXT' || r.status === 'BLOCKED') {
        const lift = task.lane === 'transcribe' ? LANE.standard : LANE.judgment
        r = await dispatch(slice, state, `task:${task.id}:retry`, taskPrompt(slice, plan, task, r || { status: 'BLOCKED', blocker: 'terminal dispatch failure' }), { agentType: 'spec-loop:implementer', schema: TASK_RESULT, ...lift })
      }
      if (!r || r.status === 'NEEDS_CONTEXT' || r.status === 'BLOCKED')
        return escalated(slice, state, esc(slice, 'ambiguity', `task ${task.id} blocked`, (r && (r.blocker || (r.questions || []).join(' · '))) || 'terminal dispatch failure', `Task "${task.title}" cannot proceed. How should it resolve?`, []))
      state.tasksCompleted++
      // TASK_RESULT requires only status/touched_files/concerns/deviations, so a
      // task that legitimately changed nothing returns DONE with `commits`
      // absent. Reading it unguarded threw a TypeError that the catch-all below
      // re-labelled as a budget-exhausted 'wave interrupted' — run
      // 20260825-scope-ceiling lost a wave to it after all five tasks had
      // already committed. Guarded the way the fix and debug-fix sites already
      // guard the identical access; `head` keeps its previous value, so a
      // slice where NO task committed still leaves it null and falls into the
      // 'plan produced no commits' escalation below.
      const c = (r.commits && typeof r.commits === 'object') ? r.commits : {}
      if (c.head) state.commits.head = c.head
      if (state.commits.base === null && c.base) state.commits.base = c.base
      touched.push(...(r.touched_files || []))
      state.implConcerns.push(...(r.concerns || []), ...(r.deviations || []).map(d => `deviation: ${d}`))
    }
    if (!state.commits.head)
      return escalated(slice, state, esc(slice, 'ambiguity', 'plan produced no commits', 'All tasks completed but no commit was recorded.', 'Drop the slice or retry?', []))

    // Deterministic tier promotion: implementation touched a Tier-3 surface
    if (state.review_tier < 3 && touchesTier3Surface(touched, CTX.tier3_surfaces)) {
      state.review_tier = 3
      state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `review tier promoted to 3: diff touches tier3 surface`, rationale: 'deterministic surface-glob match', reversibility: 'n/a' } })
    }

    // Stage R — review ∥ quality gate
    guard(slice, state)
    const reviewers = state.review_tier >= 3
      ? [['review:correctness', 'correctness + errors + risk', { model: 'inherit', effort: 'high' }], ['review:tests', 'tests + types + design + comments + conventions', { model: 'sonnet', effort: 'high' }]]
      : [['review:full', null, state.review_tier === 1 ? { model: CTX.models?.reviewer || 'sonnet', effort: 'low' } : { model: CTX.models?.reviewer || 'inherit', effort: 'medium' }]]
    const [reviewParts, gate] = await parallel([
      () => parallel(reviewers.map(([role, lanes, opts]) => () =>
        dispatch(slice, state, role, reviewPrompt(slice, plan, state, lanes), { agentType: 'spec-loop:pr-reviewer', schema: REVIEW_RESULT, ...opts }))),
      () => dispatch(slice, state, 'gate', gatePrompt(slice, state), { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' }),
    ])
    let review = {
      findings: reviewParts.filter(Boolean).flatMap((r, i) => r.findings.map(f => ({ ...f, id: `r${i}-${f.id}` }))),
      summary: reviewParts.filter(Boolean).map(r => r.summary).join(' | ') || 'review dispatch failed (fail closed)',
    }
    if (reviewParts.some(r => !r)) review.findings.push({ id: 'failclosed-review', severity: 'P0', category: 'correctness', file: '-', line: 0, claim: 'a reviewer dispatch returned no result — review incomplete (fail closed)', evidence: { quote: 'n/a' }, remedy: 'resume to re-run the review', confidence: 'high', outside_diff: true })
    const gateStatus = qualityStatus(gate && gate.quality)
    const gateViolations = (gateStatus === 'FAIL' && gate) ? (gate.quality.violations || []).map((v, i) => ({ id: `qg-${i}`, severity: 'P1', category: 'quality-gate', file: v.file || '-', line: 0, claim: `${v.metric} ${v.value} > threshold ${v.threshold} in ${v.function || v.file}`, evidence: { quote: JSON.stringify(v) }, remedy: 'behavior-preserving refactor (extract method, guard clauses, parameter object)', confidence: 'high', outside_diff: false })) : []
    state.quality = gate ? { status: gateStatus, detail: gate.quality.detail || `${gateViolations.length} violation(s)` } : { status: 'FAIL', detail: 'gate dispatch failed (fail closed)' }
    state.events.push({ scope: slice.id, type: 'quality-gate', payload: { status: state.quality.status, violations: gateViolations.length } })

    // Stage V/F — verify findings + fix loop (≤2 rounds)
    const bar = state.review_tier === 1 ? 'P0' : 'P0+P1'
    let open = [...blocking(review.findings, bar), ...gateViolations]
    for (let round = 0; open.length && round < MAX_FIX_ROUNDS; round++) {
      if (state.review_tier >= 3) {
        const v = await dispatch(slice, state, 'verify-findings', verifierBatchPrompt(slice, state, open), { agentType: 'spec-loop:finding-verifier', schema: VERIFIER_RESULT, model: 'sonnet', effort: 'low' })
        const refuted = new Set(((v && v.verdicts) || []).filter(x => x.verdict === 'REFUTED').map(x => x.finding_id))
        state.review.refuted += refuted.size
        refuted.forEach(id => state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `finding ${id} refuted by batched verifier`, rationale: (v.verdicts.find(x => x.finding_id === id) || {}).evidence || '', reversibility: 'n/a' } }))
        open = open.filter(f => !refuted.has(f.id))
        if (!open.length) break
      }
      state.review.confirmed = open.length
      state.review.fix_rounds = round + 1
      const fix = await dispatch(slice, state, `fix:${round + 1}`, fixPrompt(slice, plan, state, open), { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: round === 0 ? 'sonnet' : 'inherit', effort: 'medium' })
      if (!fix || fix.status === 'BLOCKED')
        return escalated(slice, state, esc(slice, 'review-block', 'fix agent blocked', (fix && fix.blocker) || 'terminal dispatch failure', 'Blocking findings cannot be fixed automatically. Accept, guide, or drop?', []))
      if (fix.commits && fix.commits.head) state.commits.head = fix.commits.head
      const rr = await dispatch(slice, state, `re-review:${round + 1}`, reReviewPrompt(slice, state, open, fix), { agentType: 'spec-loop:re-reviewer', schema: REREVIEW_RESULT, model: 'sonnet', effort: 'low' })
      if (!rr) { continue } // fail closed: findings stay open into the next round / escalation
      state.review.refuted += rr.verdicts.filter(x => x.verdict === 'REFUTATION_ACCEPTED').length
      const closed = new Set(rr.verdicts.filter(x => x.verdict === 'ADDRESSED' || x.verdict === 'REFUTATION_ACCEPTED').map(x => x.finding_id))
      open = [...open.filter(f => !closed.has(f.id)), ...blocking(rr.new_breakage, bar).map((f, i) => ({ ...f, id: `nb${round}-${i}` }))]
      // escape hatch: fix touched files outside the reviewed diff → full re-review next round is the residual's problem; record it
      const outside = fix.touched_files.filter(f => !review.findings.some(x => x.file === f) && !(plan.tasks || []).some(t => t.files.includes(f)))
      if (outside.length) state.events.push({ scope: slice.id, type: 'review-summary', payload: { note: `fix round ${round + 1} touched files outside the original diff: ${outside.join(', ')}`, requires_full_rereview: true } })
    }
    if (open.length)
      return escalated(slice, state, esc(slice, open.some(f => f.category === 'quality-gate') ? 'quality-gate-block' : 'review-block', `${open.length} blocking finding(s) unresolved after ${MAX_FIX_ROUNDS} fix rounds`, open.map(f => `${f.severity} ${f.file}:${f.line} — ${f.claim}`).join('\n'), 'Accept the residual findings, provide guidance, or drop the slice?', []))
    state.review.residual = review.findings.filter(f => !blocking([f], bar).length).map(f => `${f.severity}: ${f.claim}`).slice(0, 10)
    state.events.push({ scope: slice.id, type: 'review-summary', payload: { findings: review.findings.length, confirmed: state.review.confirmed, refuted: state.review.refuted, fix_rounds: state.review.fix_rounds, reviewers: reviewers.length } })

    // Stage S — simplify polish (tier 3 / thorough, non-blocking)
    if (state.review_tier >= 3 && CTX.polish !== false)
      await dispatch(slice, state, 'simplify', simplifyPrompt(slice, state), { agentType: 'spec-loop:simplifier', model: 'sonnet', effort: 'low' }).then(() => {}, () => {})

    // Stage Z — full verification (suite + gate re-check), ≤1 debug-fix
    for (let attempt = 0; attempt < 2; attempt++) {
      const v = await dispatch(slice, state, `verify:${attempt + 1}`, verifyPrompt(slice, state), { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' })
      if (v && v.suite.passed && qualityStatus(v.quality) === 'PASS') {
        state.tests = { command: v.suite.command, result: v.suite.summary, scope: 'full', tree_sha: v.tree_sha }
        state.quality = { status: 'PASS', detail: v.quality.detail || state.quality.detail }
        state.commits.head = v.head_sha
        return done('DONE')
      }
      if (attempt === 0 && v && !v.suite.passed) {
        const df = await dispatch(slice, state, 'debug-fix', debugFixPrompt(slice, plan, state, v), { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: 'inherit', effort: 'high' })
        if (df && df.commits && df.commits.head) state.commits.head = df.commits.head
        continue
      }
      return escalated(slice, state, esc(slice, v && !v.suite.passed ? 'review-block' : 'quality-gate-block', 'verification failed', v ? `suite: ${v.suite.summary}; quality: ${qualityStatus(v.quality)} (summary_pass=${String(v.quality.summary_pass)}${v.quality.detail ? ` — ${v.quality.detail}` : ''})` : 'verifier dispatch failed terminally', 'Verification cannot pass automatically. Guide, accept, or drop?', []))
    }
    return escalated(slice, state, esc(slice, 'review-block', 'verification loop exhausted', 'unreachable', 'Guide, accept, or drop?', []))
  } catch (e) {
    if (e && e.escRecord) return escalated(slice, state, e.escRecord)
    return escalated(slice, state, esc(slice, 'budget-exhausted', 'wave interrupted', String((e && e.message) || e), 'The wave hit a hard limit. Raise budget/caps and resume, or accept committed work?', []))
  }
}

// ── Wave entry ───────────────────────────────────────────────────────────────

log(`wave ${A.wave_index}: ${A.slices.length} slice(s) — ${A.slices.map(s => s.id).join(', ')}`)
const results = await parallel(A.slices.map(s => () => runSlice(s)))
const out = results.map((r, i) => r || {
  schema_version: 2, id: A.slices[i].id, status: 'ESCALATED', branch: A.slices[i].branch,
  commits: { base: A.slices[i].base_sha, head: null }, risk_tier: A.slices[i].risk_tier,
  review_tier: A.slices[i].risk_tier, critique: { verdict: 'SKIPPED', concerns: 0 },
  tasks_completed: 0, review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
  tests: null, quality: { status: 'SKIPPED', detail: 'slice never ran' },
  escalations: [esc(A.slices[i], 'budget-exhausted', 'slice lost', 'The slice function returned no result (terminal failure).', 'Re-run the wave to retry this slice?', [])],
  agents_used: 0, wave: A.wave_index, events: [],
})
log(`wave ${A.wave_index} collected: ${out.map(r => `${r.id}=${r.status}`).join(' ')}`)
return { run_id: A.run_id, wave_index: A.wave_index, results: out }
