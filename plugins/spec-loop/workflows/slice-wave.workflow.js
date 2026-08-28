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
//   - per-slice agent caps by review tier: 10 / 18 / 32, raisable in one
//     dispatch through args.agent_cap_overrides (agentCap); the raise never
//     lowers a cap and never changes a default
//   - fail-closed synthesis: an unusable agent return is never an approval
//   - answers injection: args.answers["<sliceId>:<trigger>"], or
//     ["<sliceId>:<trigger>:<round>"] from the second round on, resumes an
//     escalated stage (escId writes the id, latestAnswer reads it back);
//     unchanged stages replay from the journal cache
//
// The controller stamps timestamps and persists results (run_state.py) —
// this script has no clock and no filesystem, by design.
// ─────────────────────────────────────────────────────────────────────────────

// Tolerate stringified args: some harness paths deliver the args value
// JSON-encoded even when the caller passed an object (verified 2026-07-30).
const A = typeof args === 'string' ? JSON.parse(args) : args
const CTX = A.ctx // {run_dir, plugin_root, base_ref, test_command, conventions_path, shared_constraints[], scope_ceiling[] (optional), tier3_surfaces[], quality_gate_cmd, models{reviewer}, thorough, polish}

const CAPS = { 1: 10, 2: 18, 3: 32 }
const MAX_FIX_ROUNDS = 2
const BUDGET_STAGE_FLOOR = 60_000 // skip-and-escalate below this remaining budget

// Per-slice agent-cap raises authorised by the human, keyed by slice id. This map
// arrives in the wave args of ONE dispatch and expires with it: the controller
// writes it after a human answers a budget-exhausted cap record, and no default in
// CAPS moves. See agentCap below.
const CAP_OVERRIDES = A.agent_cap_overrides || {}

// ── Schemas ──────────────────────────────────────────────────────────────────

const ESCALATION = {
  type: 'object', additionalProperties: false,
  properties: {
    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'budget-exhausted', 'internal-error'] },
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
    // RECORD-ONLY, and deliberately absent from `required` below: an absent
    // over_scope means "no scope judgement was recorded", which is a different
    // claim from flag:false (run_state.py renders the two differently, and
    // run_metrics reports null vs 0). No branch in this file reads it — it is
    // carried to the council-verdict payload and the sidecar and nowhere else.
    over_scope: { type: 'object', additionalProperties: false, properties: { flag: { type: 'boolean' }, reason: { type: ['string', 'null'] } }, required: ['flag'] },
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

// The panel's over-scope record for the council-verdict payload and the
// sidecar, or null when no member recorded one (absent ≠ flag:false). A
// flagged record wins over a clean one; the reason is KEPT — unlike
// safety.reason, which is dropped at the source and recorded nowhere.
// RECORD-ONLY: no caller may branch on this result. (PURE)
function scopeRecord(verdicts) {
  const has = v => v && v.over_scope && typeof v.over_scope.flag === 'boolean'
  const v = verdicts.find(x => has(x) && x.over_scope.flag === true) || verdicts.find(has)
  if (!v) return null
  return { flag: v.over_scope.flag, reason: v.over_scope.reason === undefined ? null : v.over_scope.reason }
}

// One durable `deferred` event per defer-hinted concern - the human-facing
// record requirement 5 asks for. `summary` is the first key run_state.py's
// renderer reads (SUMMARY_TEXT_KEYS), so decisions-log.md gets a legible line
// instead of a JSON blob. The scope marker is a BARE BOOLEAN `true`, the shape
// run_state.py pins - and it is OMITTED rather than set to false when nothing
// was flagged, because `over_scope: false` is an explicit "this deferral is
// not about scope". This does not replace the council-verdict payload's
// `deferred[]`: that array has a live run_metrics consumer (concerns_deferred)
// and stays exactly as it is. (PURE)
function deferralEvents(slice, concerns) {
  return concerns.filter(c => c.disposition_hint === 'defer').map(c => ({
    scope: slice.id, type: 'deferred',
    payload: { summary: c.text, source: 'plan-critique', ...(c.over_scope ? { over_scope: true } : {}) },
  }))
}

// Called only on the path where `plan` actually proceeds to execution — a
// SPLIT return discards the plan (and every grafted child re-critiques and
// records its own deferrals), and an escalation return means the plan never
// ran. Recording here unconditionally would give "ONE durable record per
// defer-hinted concern" a plan that was discarded (SPLIT, duplicated across
// children) or one that never executed (escalation, then re-appended on
// every resume — persist_slice/append_event do no de-duplication).
function recordDeferrals(slice, state, concerns) {
  state.deferred = concerns.filter(c => c.disposition_hint === 'defer').map(c => c.text)
  deferralEvents(slice, concerns).forEach(e => state.events.push(e))
}

// Type-safe read of the optional run-level ceiling. Null-safe alone is not
// enough: `(CTX.scope_ceiling || []).length` is truthy for a non-empty
// STRING too, and a bare `.map(...)` on that string throws — the exact
// class of defect this slice exists to eliminate, reproduced in the field
// it added. The producer is an LLM controller populating `ctx` from prose,
// so a lone string in place of a one-element list is a realistic input,
// not a hypothetical: it is coerced to `[string]` rather than dropped or
// thrown on, since the content is clearly meant as ceiling text. Anything
// else non-array (number, object, boolean) is treated as absent — there is
// no reasonable single-value coercion for those. (PURE)
function scopeCeilingList(ctx) {
  const raw = ctx.scope_ceiling
  if (Array.isArray(raw)) return raw
  if (typeof raw === 'string' && raw) return [raw]
  return []
}

// Answer keys belonging to one slice+trigger: the bare "<slice-id>:<trigger>"
// plus every round-suffixed sibling of it. Triggers are a closed enum and the
// base always ends with the whole trigger, so no trigger's family can absorb
// another's key. (PURE over A.answers)
function answerKeysFor(sliceId, trigger) {
  const base = `${sliceId}:${trigger}`
  return Object.keys(A.answers || {}).filter(k => k === base || k.startsWith(`${base}:`))
}

// Which round this dispatch is raising. A round is one DISPATCH of the slice:
// escalated() is terminal, so a slice raises at most one record per dispatch and
// an in-memory counter would reset to 1 on every re-dispatch and collide again.
// The controller keys each answer by the escalation id it answers, so the number
// of answered rounds already in args.answers is the one counter that survives a
// resume unchanged — the same answers map always reproduces the same id. Round 1
// keeps the bare id, so every id and answer key written before the round suffix
// existed still matches. (PURE)
function escRound(sliceId, trigger) {
  return answerKeysFor(sliceId, trigger).length + 1
}

function escId(sliceId, trigger) {
  const round = escRound(sliceId, trigger)
  const base = `${sliceId}:${trigger}`
  return round === 1 ? base : `${base}:${round}`
}

// `content` is `{title, context, question, options}`, grouped into one
// parameter object because those four always travel together (one prompt's
// worth of copy), whereas `slice` and `trigger` each drive a different part
// of the id.
function esc(slice, trigger, content) {
  const { title, context, question, options } = content
  return {
    id: escId(slice.id, trigger),
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
  scopeCeilingList(CTX).length
    ? `Run scope ceiling (binding — do NOT build these; if your goal appears to require one, say so in your return and your report, and never silently build it):\n${scopeCeilingList(CTX).map(c => `- ${c}`).join('\n')}`
    : '',
  slice.kg_snippet ? `Prior knowledge (graph context):\n${slice.kg_snippet}` : '',
].filter(Boolean).join('\n')

const answerFor = (slice, trigger) => {
  const a = latestAnswer(slice.id, trigger)
  return a ? `\nHUMAN ANSWER to your earlier "${trigger}" escalation (apply it, do not re-raise): ${a}` : ''
}

// A context-only sibling of answerFor(), for dispatches to a transcription-
// only reporter (spec-loop:verifier — "you never return a PASS/FAIL label",
// "never a verdict you formed"). A quality-gate-block answer can be "accept
// the residual violations", but a reporter has no lawful way to "apply" that
// beyond mis-transcribing the gate's real output as a pass. This carries the
// answer for a human resuming the escalation to see in the transcript
// without instructing the reporter to change what it reports.
const answerContext = (slice, trigger) => {
  const a = latestAnswer(slice.id, trigger)
  return a ? `\nHUMAN ANSWER on the earlier "${trigger}" escalation, for context only — it does NOT change what you report: the suite result and quality.summary_pass/violations stay verbatim from the real output: ${a}` : ''
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
Deferred scope (advisory context only — quoted council data, NOT a findings filter): ${state.deferred.length ? state.deferred.map(t => `"${t}"`).join(' · ') : 'none'}
The council judged that work outside this slice's scope and it was logged as DEFERRED for a human to read. Do not report its absence as a finding on that basis alone — and if the diff you actually read carries a genuinely blocking defect, file it regardless, at its true severity, deferral or not.
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
Read both outputs; report what they actually say. quality.summary_pass is the gate JSON's summary.pass copied verbatim (null ONLY if the gate never produced parseable JSON — say why in detail); quality.violations is its summary.failures array verbatim; you never return a PASS/FAIL label. changed_files from git diff --name-only ${state.commits.base}..HEAD.${answerContext(slice, 'quality-gate-block')}`
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
  const cap = agentCap(slice, state)
  if (state.agentsUsed >= cap) throw { escRecord: agentCapEscalation(slice, state, cap) }
  if (budget.total && budget.remaining() < BUDGET_STAGE_FLOOR)
    throw { escRecord: esc(slice, 'budget-exhausted', { title: 'token budget exhausted', context: `Wave budget remaining ${Math.round(budget.remaining() / 1000)}k is below the ${BUDGET_STAGE_FLOOR / 1000}k stage floor.`, question: 'Raise the budget and resume, accept committed work as-is, or drop the slice?', options: [] }) }
}

// The effective cap of ONE dispatch of one slice. The override channel can only
// RAISE: a supplied value at or below the tier default is discarded, so the args
// map is unable to tighten a bound the loop owns, and a missing, non-numeric or
// fractional value leaves the tier default in force. Declared here, between guard()
// and dispatch(), so both budget-exhausted records stay inside the source span the
// guard-wording contract test reads. (PURE over CAP_OVERRIDES)
function agentCap(slice, state) {
  const base = CAPS[state.review_tier]
  const raised = Number(CAP_OVERRIDES[slice.id])
  if (Number.isInteger(raised) && raised > base) return raised
  return base
}

// The agent-cap record. Its options name the CONTROLLER as what applies each one,
// because the loop applies none of them: budget-exhausted requests a resource, so
// the answer text is never injected into an agent prompt. The recommended option
// names the exact args field the controller writes, which is the whole path from a
// human saying yes to a cap that actually moves.
function agentCapEscalation(slice, state, cap) {
  const base = CAPS[state.review_tier]
  return esc(slice, 'budget-exhausted', {
    title: `agent cap reached (${cap})`,
    context: `Slice used ${state.agentsUsed} agents (tier ${state.review_tier} default ${base}, effective cap ${cap}).`,
    question: 'Raise the cap and resume, accept the slice as-is, or drop it?',
    options: [
      { label: 'Raise the agent cap and resume', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: put the authorised integer under args.agent_cap_overrides, keyed by this slice id, then re-dispatch the wave. The raise lives in that one args object and moves no default in CAPS.', recommended: true },
      { label: 'Accept the slice as-is', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and take no further work from it. The loop enforces no acceptance by itself.' },
      { label: 'Drop the slice', detail: 'The CONTROLLER must act on this at the next dispatch: exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.' },
    ],
  })
}

async function dispatch(slice, state, role, prompt, opts) {
  guard(slice, state)
  // Last dispatch STARTED, not a per-throw stage: never cleared, and
  // concurrent fan-outs overwrite each other. After guard() so a cap or
  // token-floor rejection cannot advance it to a role that never ran.
  state.stage = role
  state.agentsUsed++
  const r = await agent(prompt, { ...opts, label: `${slice.id}:${role}`, phase: `wave ${A.wave_index}` })
  state.events.push({ scope: slice.id, type: 'agent-dispatch', payload: { role, model: opts.model || 'inherit', effort: opts.effort || null, agent_type: opts.agentType || null } })
  return r // null on user-skip/terminal error — callers fail closed
}

// ── The slice pipeline ───────────────────────────────────────────────────────
//
// runSlice orchestrates seven stages (P/C/T/R/V-F/S/Z) as a flat sequence of
// extracted stage functions below it. Each stage returns either `{ stop }`
// (a terminal slice result — the caller returns it immediately) or the data
// the next stage needs; runSlice itself does no branching beyond "did this
// stage ask to stop". Splitting the pipeline this way keeps every function's
// own complexity/length/nesting small and independently named, instead of
// one function carrying the whole slice's control flow.

const TASK_LANE = { transcribe: { model: 'haiku', effort: 'low' }, standard: { model: 'sonnet', effort: 'medium' }, judgment: { model: 'inherit', effort: 'high' } }

function initSliceState(slice) {
  return {
    agentsUsed: 0, stage: null, events: [], escalations: [],
    review_tier: Math.max(slice.risk_tier, CTX.thorough ? Math.min(slice.risk_tier + 1, 3) : slice.risk_tier),
    critique: { verdict: 'SKIPPED', concerns: 0 },
    commits: { base: slice.base_sha, head: null },
    tasksCompleted: 0, implConcerns: [], deferred: [],
    review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [] },
    tests: null, quality: { status: 'SKIPPED', detail: 'not reached' },
  }
}

function doneResult(slice, state, status, extra) {
  return {
    schema_version: 2, id: slice.id, status,
    branch: slice.branch, commits: state.commits, risk_tier: slice.risk_tier,
    review_tier: state.review_tier, critique: state.critique,
    tasks_completed: state.tasksCompleted, review: state.review,
    tests: state.tests, quality: state.quality, escalations: state.escalations,
    agents_used: state.agentsUsed, wave: A.wave_index, events: state.events, ...extra,
  }
}

// Stage P — plan (+ right-size gate inside the planner)
async function stagePlan(slice, state) {
  const plan = await dispatch(slice, state, 'plan', planPrompt(slice),
    { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
  if (!plan) return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: 'planner returned no result', context: 'The planner dispatch failed terminally.', question: 'Retry the slice, or drop it?', options: [] })) }
  if (plan.status === 'SPLIT') return { stop: doneResult(slice, state, 'SPLIT', { split: plan.split }) }
  if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, esc(slice, plan.escalation.trigger, plan.escalation)) }
  return { plan }
}

// Stage C helpers — panel selection, verdict rollup, and the OBJECT branch.
// Each helper below is kept single-purpose and small on its own terms (own
// complexity/param-count budget), which is what lets stageCritique itself
// stay a short list of calls instead of one large branchy function.

function failClosedCritique() {
  return { verdict: 'OBJECT', safety: { flag: false, reason: null }, over_scope: null, concerns: [], objection: { reason: 'unreadable critic verdict (fail closed)', question: 'The plan critique could not be completed. Proceed anyway, or retry?', recommendation: 'retry the slice' }, fixable_by_replan: false }
}

function selectCouncilPanel(state) {
  if (state.review_tier < 3) return [['full-council', 'spec-loop:plan-critic', 'inherit', 'low', null]]
  if (CTX.thorough) return [['full-council', 'spec-loop:plan-critic', 'inherit', 'high', null], ['risk', 'spec-loop:guardian', 'inherit', 'high', 'risk'], ['premise', 'spec-loop:skeptic', 'sonnet', 'high', 'premise']]
  return [['full-council', 'spec-loop:plan-critic', 'inherit', 'high', null], ['risk', 'spec-loop:guardian', 'inherit', 'high', 'risk']]
}

function computeCritiqueVerdict(safety, objections, verdicts, concerns) {
  if (safety || objections.length * 2 > verdicts.length) return 'OBJECT'
  return concerns.length ? 'ENDORSE_WITH_CONCERNS' : 'ENDORSE'
}

// Each concern is stamped with the RAISING MEMBER's whole-verdict over_scope
// flag, not a per-concern judgement: there is no per-concern over_scope field
// in the CRITIQUE schema (deliberately — adding one would reopen the council
// contract for a non-blocking record channel), so a member who flags the
// PLAN as over-scope while separately raising an unrelated
// disposition_hint:'defer' concern causes that unrelated concern to inherit
// `over_scope: true` too. This is member-level attribution BROADCAST onto
// every concern that member raised, never a claim that the concern itself is
// out of scope. The same caveat is spelled out in run-state-v2.md's
// `deferred` payload bullet and in run_state.py's `_summarize` docstring
// (the `SCOPE `-prefix renderer) — read either before trusting the marker as
// a per-item judgement. Extra keys are inert downstream: concerns are only
// counted, filtered by disposition_hint, and mapped to .text.
function deriveCouncilInputs(verdicts) {
  const objections = verdicts.filter(v => v.verdict === 'OBJECT')
  const safety = verdicts.find(v => v.safety.flag)
  const concerns = verdicts.flatMap(v => v.concerns.map(c => ({ ...c, over_scope: !!(v.over_scope && v.over_scope.flag === true) })))
  const scope = scopeRecord(verdicts)
  return { objections, safety, concerns, scope }
}

// A split is only actionable below the depth cap, and never alongside an
// OBJECT (an objection always wins the turn).
function findSplitRecommendation(verdicts, depth, verdict) {
  const rec = verdicts.find(v => v.split && v.split.recommended && (v.split.children || []).length >= 2)
  return (rec && depth < 2 && verdict !== 'OBJECT') ? rec : null
}

// RECORD-ONLY: `ctx.scope` is carried into the event payload after the
// verdict is already computed elsewhere — this function never feeds back
// into the verdict itself.
function recordCouncilVerdict(slice, state, ctx) {
  const { panel, safety, concerns, scope } = ctx
  state.events.push({ scope: slice.id, type: 'council-verdict', payload: { verdict: state.critique.verdict, panel: panel.map(p => p[0]), safety: !!safety, concerns_folded: concerns.filter(c => c.disposition_hint === 'fold').length, deferred: concerns.filter(c => c.disposition_hint === 'defer').map(c => c.text), ...(scope ? { over_scope: scope } : {}) } })
}

function humanAnswer(id) {
  return (A.answers || {})[id]
}

// The answer to the NEWEST answered round of one slice+trigger. The controller
// keys an answer by the escalation id it answers, so round 2's answer arrives
// under "<slice-id>:<trigger>:2", and an answer written before the suffix
// existed is keyed bare. Both are matched here, deliberately: dropping the bare
// key would make every previously written answer unfindable, and the answer to
// round N is exactly the context the dispatch that raises round N+1 needs. An
// unparsable suffix ranks as round 1 rather than being dropped. (PURE)
function latestAnswer(sliceId, trigger) {
  const base = `${sliceId}:${trigger}`
  const rank = (key) => Number(key.slice(base.length + 1)) || 1
  const keys = answerKeysFor(sliceId, trigger).sort((a, b) => rank(a) - rank(b))
  const newest = keys[keys.length - 1]
  return newest === undefined ? undefined : humanAnswer(newest)
}

function councilObjectionEscalation(slice, state, ob, safety) {
  return escalated(slice, state, esc(slice, 'council-objection', { title: `${safety ? 'SAFETY — ' : ''}council objects: ${ob.objection.reason.slice(0, 60)}`, context: ob.objection.reason, question: ob.objection.question, options: [{ label: ob.objection.recommendation, detail: 'critic-recommended default', recommended: true }] }))
}

// The council OBJECT branch: an unanswered fixable objection gets one replan
// attempt; anything else (safety, unfixable, or a failed replan) escalates.
// answered → proceed with the existing plan; the answer is already injected
// into downstream prompts via answerFor().
async function resolveCouncilObjection(slice, state, ctx) {
  const { plan, ob, safety } = ctx
  if (latestAnswer(slice.id, 'council-objection')) return { plan }
  if (safety || !ob.fixable_by_replan || state.replanned) return { stop: councilObjectionEscalation(slice, state, ob, safety) }
  state.replanned = true
  const revised = await dispatch(slice, state, 'replan', replanPrompt(slice, plan, ob),
    { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
  return (revised && revised.status === 'PLANNED') ? { plan: revised } : { stop: councilObjectionEscalation(slice, state, ob, safety) }
}

// Resolves an OBJECT verdict and records deferrals only if the resolution
// actually lets the plan proceed (see the comment on recordDeferrals above)
// — pulled out of stageCritique so that one extra branch is not counted
// against its own cognitive-complexity budget (stageCritique is already at
// the pre-existing file's inherited complexity baseline; every new branch
// this slice adds goes into a small named helper, per this run's own rule).
async function resolveObjectionAndRecord(slice, state, ctx) {
  const { plan, ob, safety, concerns } = ctx
  const resolved = await resolveCouncilObjection(slice, state, { plan, ob, safety })
  if (!resolved.stop) recordDeferrals(slice, state, concerns)
  return resolved
}

// Stage C — critique (tier ≥ 2)
async function stageCritique(slice, state, plan) {
  if (state.review_tier < 2) return { plan }
  const panel = selectCouncilPanel(state)
  guard(slice, state)
  const raw = await parallel(panel.map(([role, agentType, model, effort, lane]) => () =>
    dispatch(slice, state, `critic:${role}`, criticPrompt(slice, plan, lane),
      { agentType, schema: CRITIQUE, model, effort })))
  const verdicts = raw.map(v => v || failClosedCritique())
  const { objections, safety, concerns, scope } = deriveCouncilInputs(verdicts)
  state.critique = { verdict: computeCritiqueVerdict(safety, objections, verdicts, concerns), concerns: concerns.length }
  // RECORD-ONLY: attached after the verdict is computed, never spread into
  // the rollup literal above, so the verdict expression provably cannot
  // consult it. Omitted entirely when no member judged scope.
  if (scope) state.critique.over_scope = scope
  recordCouncilVerdict(slice, state, { panel, safety, concerns, scope })
  const splitRec = findSplitRecommendation(verdicts, slice.depth, state.critique.verdict)
  if (splitRec) return { stop: doneResult(slice, state, 'SPLIT', { split: { children: splitRec.split.children } }) }
  if (state.critique.verdict !== 'OBJECT') { recordDeferrals(slice, state, concerns); return { plan } }
  return resolveObjectionAndRecord(slice, state, { plan, ob: (safety || objections[0]), safety, concerns })
}

// Stage T helpers — one task attempt (with the lane-lift retry) and the
// guarded commits read (see the comment on the guard below).

function taskNeedsRetry(r) {
  return !r || r.status === 'NEEDS_CONTEXT' || r.status === 'BLOCKED'
}

function taskBlockReason(r) {
  return (r && (r.blocker || (r.questions || []).join(' · '))) || 'terminal dispatch failure'
}

function mergeTaskCommits(state, r) {
  const c = (r.commits && typeof r.commits === 'object') ? r.commits : {}
  if (c.head) state.commits.head = c.head
  // `state.commits.base` is initialised to `slice.base_sha` (never `null`),
  // so an `=== null` check here was dead: it could never adopt a
  // task-reported base. The real failure it should guard is `slice.base_sha`
  // being absent — `base` then stays `undefined` and every packageCmd/git
  // diff string below interpolates the literal text "undefined" with no
  // guard anywhere else. A falsy check catches that real case (and an
  // empty-string base_sha) without ever overwriting a real sha already set.
  if (!state.commits.base && c.base) state.commits.base = c.base
}

async function attemptTask(slice, state, plan, task) {
  const r = await dispatch(slice, state, `task:${task.id}`, taskPrompt(slice, plan, task, null),
    { agentType: 'spec-loop:implementer', schema: TASK_RESULT, ...TASK_LANE[task.lane] })
  if (!taskNeedsRetry(r)) return r
  const lift = task.lane === 'transcribe' ? TASK_LANE.standard : TASK_LANE.judgment
  return dispatch(slice, state, `task:${task.id}:retry`, taskPrompt(slice, plan, task, r || { status: 'BLOCKED', blocker: 'terminal dispatch failure' }),
    { agentType: 'spec-loop:implementer', schema: TASK_RESULT, ...lift })
}

async function runTask(slice, state, plan, task) {
  const r = await attemptTask(slice, state, plan, task)
  if (taskNeedsRetry(r))
    return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: `task ${task.id} blocked`, context: taskBlockReason(r), question: `Task "${task.title}" cannot proceed. How should it resolve?`, options: [] })) }
  state.tasksCompleted++
  // TASK_RESULT requires only status/touched_files/concerns/deviations, so a
  // task that legitimately changed nothing returns DONE with `commits`
  // absent. Reading it unguarded threw a TypeError that would now be
  // classified as an 'internal-error' by the catch-all; run 20260825-scope-
  // ceiling lost a wave to this defect before crash classification was added.
  // Guarded the way the fix and debug-fix sites already guard the identical
  // access; `head` keeps its previous value, so a slice where NO task
  // committed still leaves it null and falls into the 'plan produced no commits'
  // escalation below.
  mergeTaskCommits(state, r)
  state.implConcerns.push(...(r.concerns || []), ...(r.deviations || []).map(d => `deviation: ${d}`))
  return { touched: r.touched_files || [] }
}

// Stage T — sequential task implementation
async function stageTasks(slice, state, plan) {
  const touched = []
  for (const task of plan.tasks || []) {
    const r = await runTask(slice, state, plan, task)
    if (r.stop) return { stop: r.stop }
    touched.push(...r.touched)
  }
  if (!state.commits.head)
    return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: 'plan produced no commits', context: 'All tasks completed but no commit was recorded.', question: 'Drop the slice or retry?', options: [] })) }
  return { touched }
}

// Deterministic tier promotion: implementation touched a Tier-3 surface
function maybePromoteTier(slice, state, touched) {
  if (state.review_tier < 3 && touchesTier3Surface(touched, CTX.tier3_surfaces)) {
    state.review_tier = 3
    state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `review tier promoted to 3: diff touches tier3 surface`, rationale: 'deterministic surface-glob match', reversibility: 'n/a' } })
  }
}

function selectReviewers(state) {
  if (state.review_tier >= 3)
    return [['review:correctness', 'correctness + errors + risk', { model: 'inherit', effort: 'high' }], ['review:tests', 'tests + types + design + comments + conventions', { model: 'sonnet', effort: 'high' }]]
  return [['review:full', null, state.review_tier === 1 ? { model: CTX.models?.reviewer || 'sonnet', effort: 'low' } : { model: CTX.models?.reviewer || 'inherit', effort: 'medium' }]]
}

function buildReviewSummary(reviewParts) {
  const review = {
    findings: reviewParts.filter(Boolean).flatMap((r, i) => r.findings.map(f => ({ ...f, id: `r${i}-${f.id}` }))),
    summary: reviewParts.filter(Boolean).map(r => r.summary).join(' | ') || 'review dispatch failed (fail closed)',
  }
  if (reviewParts.some(r => !r)) review.findings.push({ id: 'failclosed-review', severity: 'P0', category: 'correctness', file: '-', line: 0, claim: 'a reviewer dispatch returned no result — review incomplete (fail closed)', evidence: { quote: 'n/a' }, remedy: 'resume to re-run the review', confidence: 'high', outside_diff: true })
  return review
}

function buildGateViolations(gateStatus, gate) {
  if (gateStatus !== 'FAIL' || !gate) return []
  return (gate.quality.violations || []).map((v, i) => ({ id: `qg-${i}`, severity: 'P1', category: 'quality-gate', file: v.file || '-', line: 0, claim: `${v.metric} ${v.value} > threshold ${v.threshold} in ${v.function || v.file}`, evidence: { quote: JSON.stringify(v) }, remedy: 'behavior-preserving refactor (extract method, guard clauses, parameter object)', confidence: 'high', outside_diff: false }))
}

// Stage R — review ∥ quality gate
async function stageReviewGate(slice, state, plan) {
  guard(slice, state)
  const reviewers = selectReviewers(state)
  const [reviewParts, gate] = await parallel([
    () => parallel(reviewers.map(([role, lanes, opts]) => () =>
      dispatch(slice, state, role, reviewPrompt(slice, plan, state, lanes),
        { agentType: 'spec-loop:pr-reviewer', schema: REVIEW_RESULT, ...opts }))),
    () => dispatch(slice, state, 'gate', gatePrompt(slice, state),
      { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' }),
  ])
  const review = buildReviewSummary(reviewParts)
  const gateStatus = qualityStatus(gate && gate.quality)
  const gateViolations = buildGateViolations(gateStatus, gate)
  state.quality = gate ? { status: gateStatus, detail: gate.quality.detail || `${gateViolations.length} violation(s)` } : { status: 'FAIL', detail: 'gate dispatch failed (fail closed)' }
  state.events.push({ scope: slice.id, type: 'quality-gate', payload: { status: state.quality.status, violations: gateViolations.length } })
  state.reviewersCount = reviewers.length
  return { review, gateViolations }
}

// One fix-loop round: optional batched verification (tier 3), a fix dispatch,
// and a re-review to close or roll over the remaining findings.
async function verifyAndFilterFindings(slice, state, open) {
  const v = await dispatch(slice, state, 'verify-findings', verifierBatchPrompt(slice, state, open),
    { agentType: 'spec-loop:finding-verifier', schema: VERIFIER_RESULT, model: 'sonnet', effort: 'low' })
  const refuted = new Set(((v && v.verdicts) || []).filter(x => x.verdict === 'REFUTED').map(x => x.finding_id))
  state.review.refuted += refuted.size
  refuted.forEach(id => state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `finding ${id} refuted by batched verifier`, rationale: (v.verdicts.find(x => x.finding_id === id) || {}).evidence || '', reversibility: 'n/a' } }))
  return open.filter(f => !refuted.has(f.id))
}

// escape hatch: fix touched files outside the reviewed diff → full re-review next round is the residual's problem; record it
function recordOutsideDiffFix(slice, state, ctx) {
  const { plan, review, fix, round } = ctx
  const outside = fix.touched_files.filter(f => !review.findings.some(x => x.file === f) && !(plan.tasks || []).some(t => t.files.includes(f)))
  if (outside.length) state.events.push({ scope: slice.id, type: 'review-summary', payload: { note: `fix round ${round + 1} touched files outside the original diff: ${outside.join(', ')}`, requires_full_rereview: true } })
}

function fixBlockerReason(fix) {
  return (fix && fix.blocker) || 'terminal dispatch failure'
}

async function dispatchFix(slice, state, ctx) {
  const { plan, open, round } = ctx
  return dispatch(slice, state, `fix:${round + 1}`, fixPrompt(slice, plan, state, open),
    { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: round === 0 ? 'sonnet' : 'inherit', effort: 'medium' })
}

function closeRereviewedFindings(rr, open, round, bar) {
  const closed = new Set(rr.verdicts.filter(x => x.verdict === 'ADDRESSED' || x.verdict === 'REFUTATION_ACCEPTED').map(x => x.finding_id))
  return [...open.filter(f => !closed.has(f.id)), ...blocking(rr.new_breakage, bar).map((f, i) => ({ ...f, id: `nb${round}-${i}` }))]
}

async function maybeVerifyFindings(slice, state, open) {
  return state.review_tier >= 3 ? verifyAndFilterFindings(slice, state, open) : open
}

async function runFixRound(slice, state, ctx) {
  const { plan, review, round, bar } = ctx
  const open = await maybeVerifyFindings(slice, state, ctx.open)
  if (!open.length) return { open }
  state.review.confirmed = open.length
  state.review.fix_rounds = round + 1
  const fix = await dispatchFix(slice, state, { plan, open, round })
  if (!fix || fix.status === 'BLOCKED')
    return { stop: escalated(slice, state, esc(slice, 'review-block', { title: 'fix agent blocked', context: fixBlockerReason(fix), question: 'Blocking findings cannot be fixed automatically. Accept, guide, or drop?', options: [] })) }
  if (fix.commits && fix.commits.head) state.commits.head = fix.commits.head
  const rr = await dispatch(slice, state, `re-review:${round + 1}`, reReviewPrompt(slice, state, open, fix),
    { agentType: 'spec-loop:re-reviewer', schema: REREVIEW_RESULT, model: 'sonnet', effort: 'low' })
  if (!rr) return { open } // fail closed: findings stay open into the next round / escalation
  state.review.refuted += rr.verdicts.filter(x => x.verdict === 'REFUTATION_ACCEPTED').length
  recordOutsideDiffFix(slice, state, { plan, review, fix, round })
  return { open: closeRereviewedFindings(rr, open, round, bar) }
}

// Stage V/F — verify findings + fix loop (≤2 rounds)
async function stageFixLoop(slice, state, ctx) {
  const { plan, review, gateViolations } = ctx
  const bar = state.review_tier === 1 ? 'P0' : 'P0+P1'
  let open = [...blocking(review.findings, bar), ...gateViolations]
  for (let round = 0; open.length && round < MAX_FIX_ROUNDS; round++) {
    const res = await runFixRound(slice, state, { plan, review, open, round, bar })
    if (res.stop) return { stop: res.stop }
    open = res.open
  }
  if (open.length) return { stop: escalated(slice, state, esc(slice, open.some(f => f.category === 'quality-gate') ? 'quality-gate-block' : 'review-block', { title: `${open.length} blocking finding(s) unresolved after ${MAX_FIX_ROUNDS} fix rounds`, context: open.map(f => `${f.severity} ${f.file}:${f.line} — ${f.claim}`).join('\n'), question: 'Accept the residual findings, provide guidance, or drop the slice?', options: [] })) }
  state.review.residual = review.findings.filter(f => !blocking([f], bar).length).map(f => `${f.severity}: ${f.claim}`).slice(0, 10)
  state.events.push({ scope: slice.id, type: 'review-summary', payload: { findings: review.findings.length, confirmed: state.review.confirmed, refuted: state.review.refuted, fix_rounds: state.review.fix_rounds, reviewers: state.reviewersCount } })
  return {}
}

// Stage S — simplify polish (tier 3 / thorough, non-blocking)
async function maybePolish(slice, state) {
  if (state.review_tier >= 3 && CTX.polish !== false)
    await dispatch(slice, state, 'simplify', simplifyPrompt(slice, state),
      { agentType: 'spec-loop:simplifier', model: 'sonnet', effort: 'low' }).then(() => {}, () => {})
}

// Stage Z helpers — verification-outcome predicates and terminal builders.

function verifyPassed(v) {
  return !!(v && v.suite.passed && qualityStatus(v.quality) === 'PASS')
}

function verifySuiteFailed(v) {
  return !!(v && !v.suite.passed)
}

function markVerifiedDone(slice, state, v) {
  state.tests = { command: v.suite.command, result: v.suite.summary, scope: 'full', tree_sha: v.tree_sha }
  state.quality = { status: 'PASS', detail: v.quality.detail || state.quality.detail }
  state.commits.head = v.head_sha
  return doneResult(slice, state, 'DONE')
}

function verificationFailedEscalation(slice, state, v) {
  const trigger = verifySuiteFailed(v) ? 'review-block' : 'quality-gate-block'
  const detail = v
    ? `suite: ${v.suite.summary}; quality: ${qualityStatus(v.quality)} (summary_pass=${String(v.quality.summary_pass)}${v.quality.detail ? ` — ${v.quality.detail}` : ''})`
    : 'verifier dispatch failed terminally'
  return escalated(slice, state, esc(slice, trigger, { title: 'verification failed', context: detail, question: 'Verification cannot pass automatically. Guide, accept, or drop?', options: [] }))
}

async function runDebugFix(slice, state, plan, v) {
  const df = await dispatch(slice, state, 'debug-fix', debugFixPrompt(slice, plan, state, v),
    { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: 'inherit', effort: 'high' })
  if (df && df.commits && df.commits.head) state.commits.head = df.commits.head
}

// Stage Z — full verification (suite + gate re-check), ≤1 debug-fix
async function stageVerify(slice, state, plan) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const v = await dispatch(slice, state, `verify:${attempt + 1}`, verifyPrompt(slice, state),
      { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' })
    if (verifyPassed(v)) return markVerifiedDone(slice, state, v)
    if (attempt === 0 && verifySuiteFailed(v)) { await runDebugFix(slice, state, plan, v); continue }
    return verificationFailedEscalation(slice, state, v)
  }
  return escalated(slice, state, esc(slice, 'review-block', { title: 'verification loop exhausted', context: 'unreachable', question: 'Guide, accept, or drop?', options: [] }))
}

// The seven-stage sequence, unwrapped from the try/catch below so its own
// early-return checks aren't weighted by an extra level of nesting.
async function runStages(slice, state) {
  const p = await stagePlan(slice, state)
  if (p.stop) return p.stop
  let plan = p.plan

  const c = await stageCritique(slice, state, plan)
  if (c.stop) return c.stop
  plan = c.plan

  const t = await stageTasks(slice, state, plan)
  if (t.stop) return t.stop
  maybePromoteTier(slice, state, t.touched)

  const rg = await stageReviewGate(slice, state, plan)
  const f = await stageFixLoop(slice, state, { plan, review: rg.review, gateViolations: rg.gateViolations })
  if (f.stop) return f.stop

  await maybePolish(slice, state)
  return stageVerify(slice, state, plan)
}

// An unclassified throw is a MACHINE failure, not a judgment call, and the
// record asserts only the cause the code can PROVE. The two structural guards
// (agent cap, stage token floor) throw {escRecord} with their own
// budget-exhausted record and are handled on the first line below, so neither
// of them RAISED the record that reached here -- which is ALL that check
// proves, and all the record claims. It does not prove the crash originated
// outside a guard, let alone outside a resource limit: budget.remaining() is
// called inside the token-floor guard itself, so a throw from in there starts
// in a guard and still arrives with no escRecord, and a rejected agent(...)
// promise on a hard token or rate limit lands here the same way. Run
// 20260825-scope-ceiling showed the cost of a mislabelled crash is misdirected
// DIAGNOSIS, and asserting "bug, NOT a budget limit" would be exactly as
// unprovable as the "budget" label it replaced, just aimed the other way, so
// the record names both possibilities and leans on the exception text instead.
// It names the LAST DISPATCHED stage: state.stage is the most recent dispatch,
// not a per-throw stage (it is never cleared, and concurrent fan-outs overwrite
// it), so the record says "after", not "in", and says so explicitly; the title
// drops "after" entirely when no agent was ever dispatched, which would
// otherwise read "crashed after before any agent was dispatched". Context ORDER
// is load-bearing: render_escalation() (run_state.py) renders the context
// through _one_line(..., 400), so only the first 400 collapsed characters reach
// escalations.md -- also the corpus a later run's escalation-gate precedent
// check reads. Both VARIABLE diagnostics (the exception text, then the stage
// attribution the title asserts) therefore lead, each with a one-clause caveat,
// and the fixed classification prose follows them, where truncation costs
// boilerplate instead of evidence. Retry is deliberately a
// human/controller decision: internal-error is not in ANSWERABLE_TRIGGERS and
// the loop implements no automatic retry, skip, or stop, so each option's
// detail names the CONTROLLER as what applies it.
function runSliceError(slice, state, e) {
  if (e && e.escRecord) return escalated(slice, state, e.escRecord)
  const stage = state.stage
  const stageText = stage || 'none (the crash happened before any agent was dispatched)'
  const title = stage ? `slice crashed after ${stage}` : 'slice crashed before any agent was dispatched'
  const context = `Error: ${String((e && e.message) || e)}. Last stage/role dispatched before the failure: ${stageText} — the most recent dispatch, not a per-throw stage, so a starting point, not a culprit. Cause unknown: neither structural guard raised its escalation record, and that is all the check one line above proves — the stage token floor calls budget.remaining() itself, so a throw from inside a guard reaches here with no record either. It may be a loop or agent-contract bug, and it may equally be a host- or agent-layer resource failure (a rejected agent call on a hard token or rate limit, say) — the exception text above is the evidence, not this classification. state.stage is never cleared and concurrent fan-outs overwrite it, so the failure may also have happened after that role finished, or in a sibling of it. ${state.tasksCompleted} task(s) had already completed and any committed work is on the branch.`
  const question = 'Retry this slice, skip it and continue the run, or stop the run to diagnose the exception?'
  const options = [
    { label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice, keeping the committed work on its branch.', recommended: true },
    { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
    { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so the exception can be diagnosed before more agents are spent. Nothing in the loop stops the run by itself.' },
  ]
  return escalated(slice, state, esc(slice, 'internal-error', { title, context, question, options }))
}

// An authorised cap raise is a single-dispatch exception to a bound the loop owns,
// so it belongs in the machine channel rather than being inferable only from a
// larger agents_used. Emitted once per slice dispatch, at slice start, and only
// once the raise has actually taken effect. The payload names the tier as it stands
// at slice start; maybePromoteTier can raise the tier later, and agentCap recomputes
// the effective cap at every dispatch, so the event is a record of the authorisation
// rather than a prediction of the final bound.
function recordCapOverride(slice, state) {
  const base = CAPS[state.review_tier]
  const cap = agentCap(slice, state)
  if (cap === base) return
  state.events.push({ scope: slice.id, type: 'agent-cap-override', payload: { tier: state.review_tier, default_cap: base, effective_cap: cap } })
}

async function runSlice(slice) {
  const state = initSliceState(slice)
  recordCapOverride(slice, state)
  try {
    return await runStages(slice, state)
  } catch (e) {
    return runSliceError(slice, state, e)
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
  escalations: [esc(A.slices[i], 'internal-error', {
    title: 'slice lost',
    context: 'The slice function returned no result (terminal failure) — it died outside runSlice\'s try/catch. Neither structural guard raised its escalation record — each raises budget-exhausted with an escRecord runSlice would have returned — and that is all a null result proves, not that no guard check ran. A host- or agent-layer resource failure dies the same silent way, so the cause is unknown here.',
    question: 'Retry this slice, skip it and continue the run, or stop the run to investigate the silent failure?',
    options: [{ label: 'Retry this slice', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: re-dispatch the wave on this slice. No result came back, so this record carries no exception text to diagnose and no record of committed work — inspect the slice branch before the retry, which starts from its base.', recommended: true },
     { label: 'Skip this slice', detail: 'The CONTROLLER must act on this at the next dispatch: leave the slice ESCALATED and dispatch only the independent slices. Nothing in the loop enforces a skip — the default re-dispatch procedure would retry it.' },
     { label: 'Stop the run', detail: 'The CONTROLLER must act on this at the next dispatch: halt the run instead of dispatching another wave, so a silent host- or agent-layer failure can be investigated before more agents are spent. Nothing in the loop stops the run by itself.' }],
  })],
  agents_used: 0, wave: A.wave_index, events: [],
})
log(`wave ${A.wave_index} collected: ${out.map(r => `${r.id}=${r.status}`).join(' ')}`)
return { run_id: A.run_id, wave_index: A.wave_index, results: out }
