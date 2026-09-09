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
//     ["<sliceId>:<trigger>:<round>"] from the second round on, is read back
//     by the prompt of the agent that ACTS on it (escId writes the id,
//     latestAnswer reads it back): plan-raised triggers by the planner,
//     review-block and quality-gate-block by the fixer, a task-blocked
//     ambiguity by the task retry
//   - accepted violations: args.accepted_violations["<sliceId>"] lists
//     {metric, file, function|null} fingerprints a human accepted; a gate
//     whose every violation is accepted stops blocking (gateAcceptable) while
//     the sidecar still says FAIL and lists them under quality.accepted.
//     Cumulative like answers; no wildcards; never a threshold change
//   - escalation rounds: the third round of one trigger on one slice is
//     reframed non-terminating (MAX_ESC_ROUNDS) with controller-only options
//   - re-entry: slices[].entry {stage: plan|review|fix|verify, head, ...}
//     resumes an ESCALATED slice at that stage against the branch head the
//     sidecar recorded, instead of replaying the whole pipeline from the
//     slice goal (entryOf / seedEntryState / runBuildStages)
//
// The controller stamps timestamps and persists results (run_state.py) —
// this script has no clock and no filesystem, by design.
// ─────────────────────────────────────────────────────────────────────────────

// Tolerate stringified args: some harness paths deliver the args value
// JSON-encoded even when the caller passed an object (verified 2026-07-30).
const A = typeof args === 'string' ? JSON.parse(args) : args
const CTX = A.ctx // {run_dir, plugin_root, base_ref, test_command, conventions_path, shared_constraints[], scope_ceiling[] (optional), tier3_surfaces[], refactor_radius{enabled,max_rewrite_ratio,max_touched_existing_files,min_rewritten_lines} (optional), quality_gate_cmd, models{reviewer}, thorough, polish}

const CAPS = { 1: 10, 2: 18, 3: 32 }
const MAX_FIX_ROUNDS = 2
const MAX_ESC_ROUNDS = 2 // answered rounds of one trigger on one slice before the record is reframed non-terminating
const BUDGET_STAGE_FLOOR = 60_000 // skip-and-escalate below this remaining budget

// Per-slice agent-cap raises authorised by the human, keyed by slice id. This map
// arrives in the wave args of ONE dispatch and expires with it: the controller
// writes it after a human answers a budget-exhausted cap record, and no default in
// CAPS moves. See agentCap below.
const CAP_OVERRIDES = A.agent_cap_overrides || {}

// Accepted quality-gate violations, keyed by slice id: [{metric, file, function|null}].
// CUMULATIVE like answers — rebuilt from events by redispatch.py args — unlike the
// single-dispatch cap override: an acceptance that expired with one dispatch would
// fail the same gate on the next. Matched by fingerprint, never by value and never
// by wildcard: a metric-wide acceptance would also accept a NEW breach the fix
// introduced. Run 20260908's slice j1 escalated three times on four violations
// the controller had already accepted, because nothing here could read that.
const ACCEPTED = A.accepted_violations || {}

// ── Schemas ──────────────────────────────────────────────────────────────────

const ESCALATION = {
  type: 'object', additionalProperties: false,
  properties: {
    trigger: { enum: ['ambiguity', 'material-assumption', 'review-block', 'council-objection', 'quality-gate-block', 'refactor-scope', 'budget-exhausted', 'internal-error'] },
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
    // OPTIONAL, and deliberately absent from `required` below: an absent block
    // means "the planner declared no estimate", which is a different claim
    // from a zero ratio. Every read of it runs through radiusNumbers(), which
    // guards each field individually — PLAN_RESULT.required is ['status']
    // only, and an unguarded optional read here aborted a whole wave of this
    // run. `basis` is the planner's one-sentence account of how it counted,
    // carried for a human reading the escalation and never parsed.
    refactor_radius: { type: 'object', additionalProperties: false, properties: { rewrite_ratio: { type: ['number', 'null'] }, touched_existing_files: { type: ['integer', 'null'] }, rewritten_lines: { type: ['integer', 'null'] }, basis: { type: 'string' } } },
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
    // The covering test the fixer added or extended per addressed finding. A
    // correctness/errors finding closed ADDRESSED with no entry here stays open
    // (closeRereviewedFindings): a behavioural fix without a pinning test is a claim.
    tests_added: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { finding_id: { type: 'string' }, test: { type: 'string' } }, required: ['finding_id', 'test'] } },
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

// ── Accepted violations: fingerprints, matching, and the acceptable verdict ──

const normPath = (f) => String(f).replace(/\\/g, '/').replace(/^\.\//, '')
const normFingerprint = (v) => ({ metric: String(v.metric), file: normPath(v.file), function: v.function == null ? null : String(v.function) })
const fpKey = (fp) => [fp.metric, fp.file, fp.function === null ? '' : fp.function].join('\u001f')
const describeFp = (fp) => `${fp.metric} ${fp.file}${fp.function ? `:${fp.function}` : ''}`
const withNumbers = (v) => ({ ...normFingerprint(v), value: v.value, threshold: v.threshold })
const nonEmpty = (x) => typeof x === 'string' && x.length > 0
const noWildcard = (x) => x == null || !String(x).includes('*')

// {metric, file} non-empty strings, function a string or null, no '*' anywhere.
function usableFingerprint(fp) {
  if (!fp || typeof fp !== 'object') return false
  if (!nonEmpty(fp.metric) || !nonEmpty(fp.file)) return false
  return noWildcard(fp.metric) && noWildcard(fp.file) && noWildcard(fp.function)
}

function acceptedFingerprints(sliceId) {
  const raw = ACCEPTED[sliceId]
  if (!Array.isArray(raw)) return []
  return raw.filter(usableFingerprint).map(normFingerprint)
}

// The gate's violations split against the slice's accepted fingerprints:
// `open` still block, `matched` are accepted, `unmatched` are accepted
// fingerprints no measured violation carries (drift: renamed, moved, fixed). (PURE)
function splitViolations(q, accepted) {
  const keys = new Set(accepted.map(fpKey))
  const violations = ((q && q.violations) || []).filter(v => !!v && typeof v === 'object')
  const matched = violations.filter(v => keys.has(fpKey(normFingerprint(v))))
  const open = violations.filter(v => !keys.has(fpKey(normFingerprint(v))))
  const seen = new Set(matched.map(v => fpKey(normFingerprint(v))))
  return { open, matched, unmatched: accepted.filter(fp => !seen.has(fpKey(fp))) }
}

// A gate return the slice may FINISH on: a real PASS, or a measured FAIL whose
// every violation is accepted. A gate that produced no JSON (summary_pass null)
// is never acceptable — there is nothing to match against. (PURE)
function gateAcceptable(q, accepted) {
  if (!q || typeof q.summary_pass !== 'boolean') return false
  const s = splitViolations(q, accepted)
  if (s.open.length) return false
  return q.summary_pass === true || s.matched.length > 0
}

// The ONE writer of state.quality and of the quality-gate event. Every
// measurement — stage R's gate, the re-measure before a fix-loop escalation,
// each verify attempt — lands here, so the sidecar's quality block is always
// the LAST measurement taken, stamped with the head/tree it measured and the
// role that measured it. Run 20260908 shipped six pre-fix quality blocks
// because the block was written once at stage R and rewritten only on the
// DONE path; the controller re-measured every one by hand.
function qualityDetail(v, violations) {
  if (!v) return 'gate dispatch failed (fail closed)'
  return v.quality.detail || `${violations} violation(s)`
}

// One verifier return (or a null one) reduced to the fields the sidecar keeps.
// The head falls back to the slice's own so a failed dispatch still names the
// tree it was asked about. (PURE)
function measurementOf(v, state) {
  const q = v ? v.quality : null
  const s = splitViolations(q, state.accepted)
  const head_sha = (v && v.head_sha) || state.commits.head || null
  return { status: qualityStatus(q), detail: qualityDetail(v, s.open.length), head_sha, tree_sha: v ? v.tree_sha : null, violations: s.open.length, accepted: s.matched.map(withNumbers), unmatched: s.unmatched }
}

// Announced once per dispatch: an acceptance that matches nothing accepts
// nothing, and silence would hide the drift until the gate fails again.
function recordUnmatchedAcceptances(slice, state, unmatched) {
  if (!unmatched.length || state.unmatchedAnnounced) return
  state.unmatchedAnnounced = true
  state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `accepted fingerprint(s) matched no measured violation: ${unmatched.map(describeFp).join(', ')} (stale, renamed, or already refactored)`, rationale: 'an acceptance that matches nothing accepts nothing; it is announced so the drift is diagnosable', reversibility: 'n/a' } })
}

const shortSha = (sha) => String(sha || 'unknown').slice(0, 7)

function stampQuality(slice, state, v, role) {
  const m = measurementOf(v, state)
  const accepted = m.accepted.length ? { accepted: m.accepted } : {}
  state.quality = { status: m.status, detail: m.detail, head_sha: m.head_sha, tree_sha: m.tree_sha, measured_at: role, violations: m.violations, ...accepted }
  state.events.push({ scope: slice.id, type: 'quality-gate', payload: { summary: `measured at ${role} on ${shortSha(m.head_sha)}: ${m.violations} violation(s), ${m.accepted.length} accepted`, status: m.status, violations: m.violations, accepted: m.accepted.length, head_sha: m.head_sha, tree_sha: m.tree_sha, stage: role } })
  recordUnmatchedAcceptances(slice, state, m.unmatched)
}

// Tests + quality + head from one verifier return, recorded BEFORE the result
// is judged, so a failing verification leaves the same evidence as a passing one.
function recordVerification(slice, state, v, role) {
  if (v) state.tests = { command: v.suite.command, result: v.suite.summary, passed: v.suite.passed, scope: 'full', tree_sha: v.tree_sha }
  stampQuality(slice, state, v, role)
  if (v && v.head_sha) state.commits.head = v.head_sha
}

// ── Refactor radius: the plan-time ceiling on churn to EXISTING code ────────
//
// The second instance of qualityStatus()'s pattern: the PLANNER reports
// numbers, this file judges them. The numbers are DECLARED before any
// implementation runs, which is the whole point (the incident that motivated
// this was "it asked, but too late") and also its honest limit: a declared
// ratio is a PROXY, not a measured diff, and it cannot catch a blowup
// discovered mid-implementation. No second, post-implementation measurement
// exists — that was deliberately deferred, not forgotten.
const RADIUS_NULL = { rewrite_ratio: null, touched_existing_files: null, rewritten_lines: null }

// A real finite number, or null. Deliberately NOT Number(v): a string "0.9"
// from a sloppy return is not a measurement, and coercing it would let a
// typo halt or fail to halt an installation. NaN and Infinity are not
// measurements either. (PURE)
const radiusNum = (v) => (typeof v === 'number' && Number.isFinite(v)) ? v : null

// Type-tolerant read of ctx.refactor_radius — the ONLY channel by which a
// threshold reaches this file. The workflow has no fs and no process access
// by design; the controller resolves the effective config once through
// quality_gate.py --print-config and threads this block into ctx, the same
// path tier3_surfaces takes. Anything that is not a plain object is "not
// configured" rather than a guessed default: hardcoding the shipped numbers
// here would give the repo two sources of truth for a value the operator is
// invited to tune, and the two would drift in silence. (PURE)
function refactorLimits(ctx) {
  const raw = ctx.refactor_radius
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  return {
    enabled: raw.enabled !== false,
    max_rewrite_ratio: radiusNum(raw.max_rewrite_ratio),
    max_touched_existing_files: radiusNum(raw.max_touched_existing_files),
    min_rewritten_lines: radiusNum(raw.min_rewritten_lines),
  }
}

// The plan's OPTIONAL refactor_radius block normalised to three explicit
// nulls. PLAN_RESULT.required is ['status'] only, so every field here is an
// optional agent-return read — the defect class that aborted a whole wave of
// this very run. Absent stays null and NEVER becomes 0: a 0 ratio is a claim
// that nothing is rewritten, which is not what silence means. (PURE)
function radiusNumbers(radius) {
  if (!radius || typeof radius !== 'object' || Array.isArray(radius)) return { ...RADIUS_NULL }
  return {
    rewrite_ratio: radiusNum(radius.rewrite_ratio),
    touched_existing_files: radiusNum(radius.touched_existing_files),
    rewritten_lines: radiusNum(radius.rewritten_lines),
  }
}

// The planner's one-sentence account of how it counted, or null. DISPLAY-ONLY
// and deliberately kept OUT of `measured`: no comparison, threshold or state
// reads it, and `measured` is the object two test layers deep-equal against
// three numeric nulls. A non-string is dropped rather than stringified,
// because "17" as a basis sentence is worse than an honest absence — the
// whole point of the field is that a human weighing the trade-off can see HOW
// the number was reached. (PURE)
const radiusBasis = (radius) => {
  if (!radius || typeof radius !== 'object' || Array.isArray(radius)) return null
  return (typeof radius.basis === 'string' && radius.basis) ? radius.basis : null
}

// Which measured metrics sit ABOVE their ceiling. Both sides are checked for
// null before the one comparison, so no comparison is ever reached by
// coercion. Strictly greater-than: both settings are MAXIMA, so a plan
// exactly at max_touched_existing_files: 8 is at the ceiling, not over it.
// (PURE)
function radiusBreaches(m, limits) {
  const over = (v, max) => v !== null && max !== null && v > max
  const out = []
  if (over(m.rewrite_ratio, limits.max_rewrite_ratio)) out.push('rewrite_ratio')
  if (over(m.touched_existing_files, limits.max_touched_existing_files)) out.push('touched_existing_files')
  return out
}

// The noise floor. It can only SUPPRESS a fire, never cause one, and it
// applies only when BOTH the declared line count and the configured floor
// are real numbers: an unmeasured rewritten_lines cannot be read as "small",
// so a measured breach beside it still stands. (PURE)
function radiusBelowFloor(m, limits) {
  const known = m.rewritten_lines !== null && limits.min_rewritten_lines !== null
  return known && m.rewritten_lines < limits.min_rewritten_lines
}

// Whether an enabled block carries NO comparable ceiling at all. Only the two
// MAXIMA count: min_rewritten_lines can only suppress a fire, never cause one,
// so its absence never makes a configuration unusable. An explicit === null on
// each side rather than a falsy test, because a ceiling of 0 is a real, if
// severe, ceiling. Its own named predicate rather than an inline condition,
// like radiusBreaches and radiusBelowFloor beside it: inlined, the branch took
// refactorRadiusStatus over its cognitive-complexity threshold. (PURE)
function radiusNoCeiling(limits) {
  return limits.max_rewrite_ratio === null && limits.max_touched_existing_files === null
}

// The two MAXIMA dimensions paired with the ceiling key each is judged
// against. A table rather than two more inline conditions, because the
// coverage split and radiusBreaches must never disagree about which
// dimensions exist: they used to, and that disagreement was the defect.
const RADIUS_DIMS = [['rewrite_ratio', 'max_rewrite_ratio'], ['touched_existing_files', 'max_touched_existing_files']]

// A list rendered for a reason sentence, or the word none. An empty join
// would render "compared: " and read as a truncated sentence rather than as
// an empty set. Explicit === 0 rather than a falsy length test, to keep the
// whole block free of decisions reached by coercion. (PURE)
const radiusList = (xs) => xs.length === 0 ? 'none' : xs.join(', ')

// Per-dimension split of the DECLARED numbers into the ones this evaluation
// actually compared and the ones it SKIPPED for want of a usable ceiling.
// radiusNoCeiling only catches the BOTH-null config; one usable ceiling
// beside one mistyped one let radiusBreaches short-circuit on the null side
// and the verdict then claimed "every declared number is at or under its
// ceiling" about a number nothing had compared - the same silent narrowing
// NO_USABLE_CEILING was added to end, one config away. A ceiling of 0 is a
// real ceiling, so usability is an explicit radiusNum() !== null and never a
// falsy test. (PURE)
function radiusCoverage(m, limits) {
  const ceiling = (key) => (limits && limits.enabled !== false) ? radiusNum(limits[key]) : null
  const declared = RADIUS_DIMS.filter((d) => m[d[0]] !== null)
  return {
    compared: declared.filter((d) => ceiling(d[1]) !== null).map((d) => d[0]),
    skipped: declared.filter((d) => ceiling(d[1]) === null).map((d) => d[0]),
  }
}

// The sentence fragment naming what was NOT compared, or an empty string
// when every declared number had a ceiling. Appended to the reason of every
// state that DID compare something, so a reader of the event never has to
// re-derive the coverage from `thresholds` by hand. The phrase "no usable
// ceiling" is deliberate and load-bearing: it is the same wording
// NO_USABLE_CEILING's own reason uses, so one search finds every record in
// which a ceiling failed to be a number. (PURE)
const radiusSkipNote = (cover) => cover.skipped.length === 0 ? '' : ` Not compared, because these declared numbers had no usable ceiling: ${radiusList(cover.skipped)}.`

// The no-breach verdict, split by coverage. WITHIN keeps exactly its old
// meaning - every declared number was compared, none was over - and
// WITHIN_PARTIAL is its honest sibling: nothing compared was over, and at
// least one declared number was never compared at all. Both FAIL OPEN, and
// only EXCEEDED halts, so this can never turn a WITHIN into a halt: it only
// stops claiming a comparison that did not happen. (PURE)
function radiusWithin(cover) {
  const compared = `compared: ${radiusList(cover.compared)}`
  if (cover.skipped.length === 0) return { state: 'WITHIN', reason: `every declared number is at or under its ceiling (${compared})` }
  return { state: 'WITHIN_PARTIAL', reason: `no compared number is over its ceiling (${compared}).${radiusSkipNote(cover)}` }
}

// Eight states, none collapsed into another, and only EXCEEDED halts anything.
// The two halves of this check have opposite answers on purpose: a
// measurement that is missing, unconfigured, unusable or disabled FAILS OPEN
// (proceed, and the caller records it loudly), while a measurement that
// succeeded and is over its ceiling FAILS CLOSED (halt and ask). Collapsing
// them would either halt every run with an old controller or halt none of
// them. NO_USABLE_CEILING is checked BEFORE NOT_MEASURED deliberately: a
// mistyped ceiling is an operator-config defect, and blaming the planner for
// it would leave the real defect invisible. It is its own state rather than a
// WITHIN, because "every declared number is at or under its ceiling" is a
// claim no comparison supported when there is no ceiling to compare against —
// a mistyped threshold used to report success while silently never firing.
// WITHIN_PARTIAL is NO_USABLE_CEILING's per-dimension twin, and the last
// instance of the same defect: a config with one valid ceiling and one
// mistyped one is USABLE, so it got past radiusNoCeiling, and the declared
// number on the null side was then reported as being under a ceiling that
// was never compared. It fails open exactly like WITHIN - an unusable
// ceiling never causes a halt, it only stops claiming a comparison.
// (PURE)
function refactorRadiusStatus(radius, limits) {
  const measured = radiusNumbers(radius)
  const cover = radiusCoverage(measured, limits)
  const base = { measured, basis: radiusBasis(radius), thresholds: limits, exceeded: [], compared: cover.compared, skipped: cover.skipped }
  if (!limits) return { ...base, thresholds: null, state: 'NOT_CONFIGURED', reason: 'ctx.refactor_radius is absent or is not an object, so no ceiling was compared' }
  if (!limits.enabled) return { ...base, state: 'DISABLED', reason: 'refactor_radius.enabled is false in the effective gate config' }
  if (radiusNoCeiling(limits)) return { ...base, state: 'NO_USABLE_CEILING', reason: 'refactor_radius is configured and enabled but neither ceiling is a usable number, so nothing was compared' }
  if (measured.rewrite_ratio === null && measured.touched_existing_files === null) return { ...base, state: 'NOT_MEASURED', reason: 'the plan declared no usable refactor-radius number' }
  const exceeded = radiusBreaches(measured, limits)
  if (!exceeded.length) return { ...base, ...radiusWithin(cover) }
  if (radiusBelowFloor(measured, limits)) return { ...base, exceeded, state: 'BELOW_FLOOR', reason: `over a ceiling but under the ${limits.min_rewritten_lines}-line noise floor.${radiusSkipNote(cover)}` }
  return { ...base, exceeded, state: 'EXCEEDED', reason: `declared rewrite of existing code is over the configured ceiling (${exceeded.join(', ')}).${radiusSkipNote(cover)}` }
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

// ── Re-entry: resume an ESCALATED slice at a stage, against its real head ──
//
// Run 20260908-jira-intake: a re-dispatched slice replayed plan/critique/tasks
// from the slice GOAL, found the goal already delivered on the branch,
// escalated "already implemented", and the controller's fix orders never
// reached any agent (1 planner, 0 tasks). The controller's workaround was a
// fresh workflow with the goal rewritten to be the defect list; slice.entry
// is that workaround made mechanical. `stage` names the FIRST stage this
// dispatch runs; `head` is the sidecar's commits.head. An unusable entry is a
// zero-dispatch internal-error, never a silent full run.

const ENTRY_STAGES = ['plan', 'review', 'fix', 'verify']

// Type-tolerant like scopeCeilingList: an object passes, anything else is "no
// entry" and the slice runs the plain pipeline. Validity is entryError's job.
const entryOf = (slice) => (slice.entry && typeof slice.entry === 'object' && !Array.isArray(slice.entry)) ? slice.entry : null

const controllerActs = 'The CONTROLLER must act on this at the next dispatch: '
const ENTRY_OPTIONS = [
  { label: 'Fix slice.entry and re-dispatch', detail: `Recommended default. ${controllerActs}re-dispatch with entry.stage one of ${ENTRY_STAGES.join('/')} and entry.head set to the sidecar's commits.head.`, recommended: true },
  { label: 'Re-dispatch without an entry', detail: `${controllerActs}drop slice.entry so the slice runs the full pipeline from its goal — only right when nothing on the branch delivers the goal yet.` },
  { label: 'Drop the slice', detail: `${controllerActs}exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.` },
]

function entryError(slice, state, entry) {
  const stageOk = ENTRY_STAGES.includes(entry.stage)
  const headOk = typeof entry.head === 'string' && entry.head.length > 0
  if (stageOk && headOk) return null
  const context = `slice.entry must carry stage ∈ {${ENTRY_STAGES.join(', ')}} and a non-empty head sha; received stage=${JSON.stringify(entry.stage)} head=${JSON.stringify(entry.head)}. No agent was dispatched: a mistyped entry running the full pipeline against a delivered goal is the trap this record exists to avoid.`
  return escalated(slice, state, esc(slice, 'internal-error', { title: 'unusable slice.entry', context, question: 'Fix the entry and re-dispatch, re-dispatch without an entry, or drop the slice?', options: ENTRY_OPTIONS }))
}

// A controller order becomes a FINDING the fix loop can carry: a string is a
// claim with no diff anchor (outside_diff, anchored on its text against the
// worktree); an object is merged over the same defaults. Orders bypass the
// blocking bar — the controller ordered them.
const ORDER_DEFAULTS = { severity: 'P1', category: 'correctness', file: '-', line: 0, evidence: { quote: 'controller order' }, confidence: 'high', outside_diff: true }
const isOrder = (o) => typeof o === 'string' || (!!o && typeof o === 'object')
function normalizeOrders(orders) {
  if (!Array.isArray(orders)) return []
  return orders.filter(isOrder).map((o, i) => typeof o === 'string'
    ? { ...ORDER_DEFAULTS, id: `order-${i}`, claim: o, remedy: o }
    : { ...ORDER_DEFAULTS, ...o, id: o.id || `order-${i}` })
}

// Carry-overs from the sidecar the controller built the entry from, so the
// re-entered slice's own sidecar stays cumulative (fix rounds, tasks, critique)
// rather than reading "0 tasks / SKIPPED" for work an earlier dispatch did.
function seedEntryCounters(state, entry) {
  const rounds = Number.isInteger(entry.fix_rounds) && entry.fix_rounds > 0 ? entry.fix_rounds : 0
  state.review.fix_rounds = rounds
  state.fixPackage = rounds ? `fix${rounds}` : null
  if ([1, 2, 3].includes(entry.review_tier)) state.review_tier = Math.max(state.review_tier, entry.review_tier)
  if (Number.isInteger(entry.tasks_completed)) state.tasksCompleted = entry.tasks_completed
  if (entry.critique && typeof entry.critique === 'object') state.critique = entry.critique
}

function seedEntryState(slice, state, entry) {
  state.commits.head = entry.head
  seedEntryCounters(state, entry)
  state.orders = normalizeOrders(entry.orders)
  state.entryResidual = Array.isArray(entry.residual) ? entry.residual.filter(r => typeof r === 'string') : []
  state.events.push({ scope: slice.id, type: 're-entry', payload: { summary: `re-entered at ${entry.stage} from head ${shortSha(entry.head)} (${state.orders.length} order(s), ${state.review.fix_rounds} fix round(s) already spent)`, stage: entry.stage, head: entry.head, fix_rounds: state.review.fix_rounds, orders: state.orders.map(o => o.claim) } })
}

// The plan a non-plan re-entry runs under: the plan file the first dispatch
// wrote, with no tasks to implement.
const entryPlan = (slice, entry) => ({ status: 'PLANNED', plan_path: entry.plan_path || `${CTX.run_dir}/plans/${slice.id}.md`, tasks: [] })

// The paragraph a plan-mode re-entry adds to the planner's prompt: the branch
// already carries work, and PLANNED with zero tasks is a legal return.
function reentryNote(slice) {
  const e = entryOf(slice)
  if (!e || e.stage !== 'plan') return ''
  return `\nRE-ENTRY: commits ${slice.base_sha}..${e.head} on the branch already deliver part or all of this goal — read that diff first. Plan ONLY the remaining work; PLANNED with an empty tasks list is a valid return when the goal is fully delivered. Append a "Re-entry" section to the existing plan file rather than rewriting it.`
}

// Options for the escalations a re-dispatch can act on. Each detail names the
// CONTROLLER and the entry it builds, because the loop applies none of them.
function reentryOptions(trigger) {
  const gate = trigger === 'quality-gate-block'
  return [
    { label: gate ? 'Accept the listed violations as pre-existing debt' : 'Accept the residual as-is', detail: `${controllerActs}${gate ? 'record the acceptance (redispatch.py accept-violations, then redispatch.py args) and re-dispatch with slice.entry {stage: "verify", head}' : 'leave the slice ESCALATED and take no further work from it — never hand-write a DONE sidecar'}.`, recommended: gate },
    { label: 'Provide fix orders', detail: `${controllerActs}re-dispatch with slice.entry {stage: "fix", head, orders: [...]} so the FIXER receives them, or — for a red suite — answer this id and re-dispatch with {stage: "verify", head} so the debug-fixer reads it.`, recommended: !gate },
    { label: 'Drop the slice', detail: `${controllerActs}exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.` },
  ]
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

// `content` is `{title, context, question, options, violations?}`, grouped into
// one parameter object because those travel together (one prompt's worth of
// copy), whereas `slice` and `trigger` each drive a different part of the id.
// `violations` rides only on quality-gate-block records: the open, unaccepted
// fingerprints, so the controller accepts BY ESCALATION ID (redispatch.py
// accept-violations) instead of transcribing prose.
function esc(slice, trigger, content) {
  const { title, context, question, options, violations } = content
  const record = {
    id: escId(slice.id, trigger),
    trigger, title, context, question,
    options: options && options.length ? options : [{ label: 'Proceed with the recommended default', detail: context, recommended: true }],
    if_unanswered: 'pause this slice; continue all independent slices',
    status: 'OPEN',
    ...(Array.isArray(violations) ? { violations } : {}),
  }
  const round = escRound(slice.id, trigger)
  return settleAnswered(round > MAX_ESC_ROUNDS ? nonTerminating(record, trigger, round) : record)
}

// By construction escId mints an id no answer holds; a truncated answers map
// (an earlier round's key dropped) can still produce one that does. Returning
// it ANSWERED keeps persist-slice from re-opening a settled question.
function settleAnswered(record) {
  const answer = (A.answers || {})[record.id]
  return answer ? { ...record, status: 'ANSWERED', answer } : record
}

// The third round of one trigger on one slice: run 20260908's j1 raised
// quality-gate-block three times on the same four accepted violations and
// would have gone on forever. The id still advances (so an answer can land),
// but the ask changes to the three things a controller can actually do.
function nonTerminating(record, trigger, round) {
  return {
    ...record,
    title: `non-terminating: same ${trigger} after ${round - 1} answered rounds — ${record.title}`,
    context: `${record.context}\n\nThis slice has raised ${trigger} ${round - 1} time(s) and each was answered, and the same trigger fired again: re-dispatching with another prose answer is provably non-terminating for this trigger.`,
    options: nonTerminatingOptions(trigger),
  }
}

function nonTerminatingOptions(trigger) {
  const gate = trigger === 'quality-gate-block'
  return [
    { label: 'Accept the residual and close the slice mechanically', detail: `${controllerActs}${gate ? 'record the acceptance by escalation id (redispatch.py accept-violations --from-escalation <this id> --all), rebuild the args (redispatch.py args) and re-dispatch with slice.entry {stage: "verify", head} — the accepted fingerprints then stop blocking the gate' : 'answer this id with the explicit acceptance and re-dispatch with slice.entry {stage: "verify", head}; a residual the loop cannot close mechanically leaves the slice ESCALATED'}.`, recommended: gate },
    { label: 'Drop the slice', detail: `${controllerActs}exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.`, recommended: !gate },
    { label: 'Leave the slice ESCALATED', detail: `${controllerActs}take no further work from it and never hand-write a DONE sidecar to close it — a DONE without the wave's own verification is the one record this loop must never carry.` },
  ]
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

// refactor-scope is raised by the plan stage, so its answer is read back HERE and nowhere
// else: a trigger whose answer never re-enters the prompt of the stage that raised it is
// structurally unanswerable by re-dispatch and the human's answer is silently discarded
// (the quality-gate-block outage this file already carries). The planner is an actor, not a
// transcriber, so this is answerFor (an instruction) rather than answerContext. replanPrompt
// interpolates planPrompt(slice), so it inherits the read-back and must not repeat the call.
function planPrompt(slice) {
  return `${packet(slice)}

Plan slice ${slice.id} of run ${A.run_id}: ${slice.goal}
Named files: ${slice.files.join(', ') || '(none named)'} · Subsystems: ${slice.subsystems.join(', ') || '—'}
Risk tier: ${slice.risk_tier} · Split depth: ${slice.depth} (split allowed only below depth 2)
Write the plan to exactly: ${CTX.run_dir}/plans/${slice.id}.md
Test/build command for verification steps: ${CTX.test_command}
Also return refactor_radius: your DECLARED estimate of how much EXISTING code this plan rewrites — {rewrite_ratio: existing lines your tasks rewrite or delete ÷ total lines the plan changes, touched_existing_files: how many pre-existing files your tasks modify, rewritten_lines: the absolute count of existing lines rewritten or deleted, basis: one sentence on how you counted}. Report the numbers only, never a verdict: the workflow judges them against the run's ceiling. If you genuinely cannot estimate one, omit it rather than guessing a zero.${answerFor(slice, 'ambiguity')}${answerFor(slice, 'material-assumption')}${answerFor(slice, 'refactor-scope')}${reentryNote(slice)}`
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
Commit in the worktree when green.${retryNote(slice, retry)}`
}

// The retry paragraph of a task prompt. The ambiguity answer rides ONLY here:
// first attempts stay byte-identical, so a plain re-dispatch still replays the
// completed tasks from the journal, and the retry — the attempt after the
// blocked one — is where the human's answer has to change something.
function retryNote(slice, retry) {
  if (!retry) return ''
  const blocker = retry.blocker ? ` — ${retry.blocker}` : ''
  const questions = (retry.questions || []).map(q => `${q} → resolve from the plan/conventions; if genuinely impossible, BLOCKED`).join(' · ')
  const answers = questions ? `; answers: ${questions}` : ''
  return `\nRETRY: the previous attempt returned ${retry.status}${blocker}${answers}. Something must change this attempt.${answerFor(slice, 'ambiguity')}`
}

function packageCmd(slice, base, head, roundTag) {
  return `python3 "${CTX.plugin_root}/scripts/review_package.py" --repo-dir "${slice.worktree}" --base ${base} --head ${head} --out "${CTX.run_dir}/packages/${slice.id}-${roundTag}.md"`
}

// The packages that exist for this slice right now. Run 20260908's fix prompts
// named packages/<slice>-round2.md, a file nothing ever writes: the tag was
// derived from fix_rounds AFTER runFixRound had incremented it. The tags live in
// state now (reviewPackage / fixPackage), set by the stage that writes the file.
function anchorPackages(slice, state) {
  const paths = [`${CTX.run_dir}/packages/${slice.id}-${state.reviewPackage}.md`]
  if (state.fixPackage) paths.push(`${CTX.run_dir}/packages/${slice.id}-${state.fixPackage}.md`)
  return paths
}

function reviewPrompt(slice, plan, state, lanes) {
  return `${packet(slice)}

Mode: slice. Review the diff of slice ${slice.id} (plan: ${plan.plan_path}).
Build the package first by running exactly:
  ${packageCmd(slice, state.commits.base, state.commits.head, state.reviewPackage)}
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

Adversarially verify EVERY finding below against the actual code. Package(s): ${anchorPackages(slice, state).join(' and ')} (read each once). First do the mechanical check: a finding whose file:line is outside the package's hunk-index ranges (and not marked outside_diff) or whose evidence quote does not appear in the package/file is REFUTED with that as evidence. Then judge substance. CONFIRMED is your default; REFUTED requires quoted counter-evidence.
Findings:
${JSON.stringify(confirmed, null, 1)}`
}

function fixPrompt(slice, plan, state, findings) {
  return `${packet(slice)}

Mode: fix. Address EVERY finding below (plan for context: ${plan.plan_path}).
Package(s) for anchor checks: ${anchorPackages(slice, state).join(' and ')} — a finding whose location/quote does not match the code may be REFUTED with file:line counter-evidence instead of a change. quality-gate findings: behavior-preserving refactors only.
Covering tests + commit when done.${answerFor(slice, 'quality-gate-block')}${answerFor(slice, 'review-block')}
Findings:
${JSON.stringify(findings, null, 1)}`
}

// FIX_RESULT.commits is optional (`required` is status/touched_files/addressed/
// refuted), so reading `base` straight off `fix.commits` dereferences an object
// that need not exist. It threw exactly that way during wave 1 of run 20260828
// (the raw read is spelled out nowhere in this file on purpose: a contract test
// pins its absence by source text) and the catch-all mislabelled the TypeError
// as budget-exhausted, losing the whole wave. Same type tolerance as
// scopeCeilingList: an object passes through, anything else becomes {} and the
// caller falls back to the shas the slice already holds.
// HONEST LIMIT: those fallback shas are the slice's own base/head, so a package
// built from them can be WIDER than the fix round's own diff. That is
// deliberate — a wider real package beats a `--base undefined` command that
// cannot run at all.
const fixCommits = (fix) => (fix && typeof fix.commits === 'object' && fix.commits) ? fix.commits : {}

function reReviewPrompt(slice, state, findings, fix) {
  return `${packet(slice)}

Re-review after a fix round for slice ${slice.id}. Build the fix-only package:
  ${packageCmd(slice, fixCommits(fix).base || state.commits.base, fixCommits(fix).head || state.commits.head, `fix${state.review.fix_rounds}`)}
Prior blocking findings (verdict each): ${JSON.stringify(findings, null, 1)}
Fixer report (unverified claims): addressed ${JSON.stringify(fix.addressed)}; tests_added ${JSON.stringify(fix.tests_added || [])}; tests ${JSON.stringify(fix.tests || null)}. An ADDRESSED verdict on a correctness/errors finding requires the named covering test to exist in the fix diff and to pin the defect; a behavioural fix with no named test is NOT_ADDRESSED.
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
Plan: ${plan.plan_path}. Fix the root cause, run the full suite (${CTX.test_command}), commit. Return DONE only with fresh green output you read; otherwise BLOCKED with what you found.${answerFor(slice, 'review-block')}`
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
    // Controller orders and the residual carried in by a re-entry (empty on a
    // plain dispatch); see seedEntryState.
    orders: [], entryResidual: [],
    // The slice's usable accepted-violation fingerprints (see ACCEPTED).
    accepted: acceptedFingerprints(slice.id),
    review: { confirmed: 0, refuted: 0, evidence_failed: 0, fix_rounds: 0, residual: [], open: [] },
    tests: null, quality: { status: 'SKIPPED', detail: 'not reached' },
    // Package tags for the files that exist right now: the review round's
    // (written at stage R) and the latest fix-only one (written by the
    // re-reviewer). Set by the stage that causes each file to exist.
    reviewPackage: 'round1', fixPackage: null,
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

// One line of copy naming every number on both sides of the comparison. A
// human answering this needs the measurements AND the ceilings they were
// judged against in the record itself, not a pointer to a config file they
// would have to resolve by hand. (PURE)
const radiusPhrase = (v) => `declared rewrite ratio ${v.measured.rewrite_ratio}, touched existing files ${v.measured.touched_existing_files}, rewritten lines ${v.measured.rewritten_lines}; ceilings ${v.thresholds.max_rewrite_ratio} ratio / ${v.thresholds.max_touched_existing_files} files, noise floor ${v.thresholds.min_rewritten_lines} lines; the planner counted this as: ${v.basis === null ? 'not stated' : v.basis}; compared: ${radiusList(v.compared)}; not compared for want of a usable ceiling: ${radiusList(v.skipped)}`

// The trade-off ask. Three options because a yes/no would leave a human who
// wants neither with nothing to pick, and because each of the three costs
// something different: narrowing leaves existing structure uncleaned,
// approving buys a large diff for one reviewer with no second measurement
// after implementation, and carving out defers the work to a slice a human
// must schedule. Each detail names the CONTROLLER as what applies it — the
// loop narrows, approves and splits nothing by itself. (PURE)
function refactorAsk(slice, verdict) {
  return {
    title: `plan for ${slice.id} declares a heavy rewrite of existing code (${verdict.exceeded.join(', ')})`,
    context: `The plan is written and NOT implemented — this fires before implementation effort is spent. ${radiusPhrase(verdict)}. These are numbers the PLANNER DECLARED: a pre-execution proxy, not a measured diff, so they can be wrong in either direction and cannot catch a blowup discovered mid-implementation. Goal: ${slice.goal}`,
    question: 'Approve the rewrite as planned, narrow the plan to the smallest change that meets the goal, or carve the rewrite out into its own slice?',
    options: [
      { label: 'Narrow the plan to the smallest change that meets the goal', detail: 'Recommended default. The CONTROLLER must act on this at the next dispatch: put the instruction in args.answers under this record id and re-dispatch the wave — the planner reads it back in its own prompt and replans against it. Trade-off: existing structure this rewrite would have cleaned up stays as it is.', recommended: true },
      { label: 'Approve the rewrite as planned', detail: 'The CONTROLLER must act on this at the next dispatch: answer this record with the approval and re-dispatch. The same plan proceeds and this check does not raise again for this slice. Trade-off: one reviewer judges a large diff in one slice, and no second measurement runs after implementation.' },
      { label: 'Carve the rewrite out into its own slice', detail: 'The CONTROLLER must act on this at the next dispatch: re-plan the run so the rewrite is a slice of its own, then re-dispatch. The loop splits nothing by itself — it never turns a refactor into its own slice without this answer.' },
    ],
  }
}

// Every evaluation is recorded, including the ones that decline to fire. A
// threshold that silently declines is a permanent invisible narrowing — the
// exact silent-exclusion defect this repo's knowledge graph already names —
// so the payload carries the measured numbers AND the thresholds they were
// compared against, in every state, and a reader never has to re-derive why
// nothing happened. `summary` is the FIRST key because run_state.py's
// decisions-log renderer reads the first text-ish field of a payload
// (SUMMARY_TEXT_KEYS), so the line is prose rather than a JSON blob. (PURE)
function radiusEvent(slice, verdict, answered) {
  // A suppression is a fire that did NOT happen. The flag used to be set from
  // `answered` alone, so an ordinary post-answer success — the human says
  // narrow it, the planner narrows, the verdict comes back WITHIN — emitted an
  // event claiming a suppression that never occurred, and anyone auditing
  // which halts a human had waived would have counted it. Only EXCEEDED can be
  // suppressed, because only EXCEEDED halts. The key stays ABSENT rather than
  // false when nothing was suppressed: `false` would be an explicit claim
  // about a state in which suppression is not even possible.
  const suppressed = answered && verdict.state === 'EXCEEDED'
  return {
    scope: slice.id, type: 'refactor-radius',
    payload: {
      summary: `refactor radius ${verdict.state}: ${verdict.reason}`,
      state: verdict.state, exceeded: verdict.exceeded,
      measured: verdict.measured, thresholds: verdict.thresholds,
      compared: verdict.compared, skipped: verdict.skipped,
      basis: verdict.basis,
      ...(suppressed ? { suppressed_by_answer: true } : {}),
    },
  }
}

// Fail OPEN on absence, CLOSED on a measured breach — the two halves have
// opposite answers and are never collapsed. HONEST LIMITS, both deliberate:
// this runs ONCE, on the plan the planner returned, so a replan after a
// council OBJECT is not re-evaluated; and the numbers are pre-execution
// declarations, so a blowup discovered mid-implementation is invisible here.
function refactorRadiusGate(slice, state, plan) {
  const verdict = refactorRadiusStatus(plan.refactor_radius, refactorLimits(CTX))
  // A truthy ANSWER, not the presence of an answer KEY. The same map reaches
  // the planner through answerFor()/latestAnswer(), which both require a
  // truthy value, so an empty or null entry used to disarm this halt
  // permanently for the slice while injecting nothing into the prompt the
  // halt exists to change — the question disappeared and the answer never
  // arrived. This is the shape resolveCouncilObjection already uses.
  const answered = !!latestAnswer(slice.id, 'refactor-scope')
  state.events.push(radiusEvent(slice, verdict, answered))
  // Answered means the human already ruled on this slice's radius. Raising
  // the same question again would deadlock the slice at the same stage
  // forever, so the verdict stays EXCEEDED in the event (with
  // suppressed_by_answer) and the slice proceeds.
  if (verdict.state !== 'EXCEEDED' || answered) return null
  return esc(slice, 'refactor-scope', refactorAsk(slice, verdict))
}

// PLAN_RESULT.required is ['status'] only, so both branches below read a field
// the schema never promised. Neither read is guarded upstream, and this exact
// defect class has aborted a whole wave of this repo twice.

// A split with no children array is schema-legal and unusable: passing it
// through produced a sidecar that run_state.py's validator rejects one stage
// later, far from the cause. Fail closed HERE instead. (PURE)
const usableSplit = (s) => !!s && typeof s === 'object' && Array.isArray(s.children) && s.children.length > 0

function splitResult(slice, state, plan) {
  if (usableSplit(plan.split)) return doneResult(slice, state, 'SPLIT', { split: plan.split })
  return escalated(slice, state, esc(slice, 'ambiguity', { title: 'planner returned SPLIT with no usable split object', context: 'The planner returned status SPLIT but no `split.children`. That is schema-legal (PLAN_RESULT requires only `status`) and unusable: passing it through writes a sidecar the run-state validator rejects one stage later. The slice is paused here, at the cause.', question: 'Re-dispatch the planner for this slice, split it by hand, or drop it?', options: [] }))
}

// One optional string field of an escalation record, or the substitute copy.
// Every one of the four fields below needs the identical explicit type test,
// and inlining it four times put planEscalation over the gate's
// cyclomatic/cognitive thresholds for no gain in clarity. An empty string is
// NOT a readable field: it would render as a blank line in the human's
// decisions log, so it takes the fallback too. (PURE)
const escText = (v, fallback) => (typeof v === 'string' && v) ? v : fallback

// The substitute copy for a planner that escalated without saying anything.
// Module-level so planEscalation stays a short list of guarded reads.
const BARE_ESCALATION = {
  title: 'planner escalated without a readable escalation record',
  context: 'The planner returned status ESCALATE with no usable escalation object. The wave substituted this record so the slice pauses for a human instead of crashing the wave with a TypeError.',
  question: 'The planner escalated without saying what it needs. Re-dispatch the planner, answer the slice goal directly, or drop the slice?',
}

// The trigger is TYPE-guarded, not enum-guarded: an unrecognized non-empty
// string still passes through and will fail run_state.py's validate_escalation
// downstream, exactly as it does today. Widening this to an enum check would
// need a second copy of the enum in this file, and that enum has eight homes
// already. Stated as a limit rather than silently half-fixed.
function planEscalation(slice, plan) {
  const e = (plan.escalation && typeof plan.escalation === 'object') ? plan.escalation : {}
  const trigger = (typeof e.trigger === 'string' && e.trigger) ? e.trigger : 'ambiguity'
  return esc(slice, trigger, {
    title: escText(e.title, BARE_ESCALATION.title),
    context: escText(e.context, BARE_ESCALATION.context),
    question: escText(e.question, BARE_ESCALATION.question),
    options: Array.isArray(e.options) ? e.options : [],
  })
}

// Stage P — plan (+ right-size gate inside the planner)
async function stagePlan(slice, state) {
  const plan = await dispatch(slice, state, 'plan', planPrompt(slice),
    { agentType: 'spec-loop:slice-planner', schema: PLAN_RESULT, effort: 'low' })
  if (!plan) return { stop: escalated(slice, state, esc(slice, 'ambiguity', { title: 'planner returned no result', context: 'The planner dispatch failed terminally.', question: 'Retry the slice, or drop it?', options: [] })) }
  if (plan.status === 'SPLIT') return { stop: splitResult(slice, state, plan) }
  if (plan.status === 'ESCALATE') return { stop: escalated(slice, state, planEscalation(slice, plan)) }
  const radius = refactorRadiusGate(slice, state, plan)
  if (radius) return { stop: escalated(slice, state, radius) }
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

// The re-check itself is a CRITIQUE, not an objection: `objection` is optional
// on that schema (required is verdict/safety/concerns), so a re-check that
// flags a NEW safety risk on a clean ENDORSE verdict — RECHECK_SAFETY's exact
// shape — carries no `objection` block at all. Falling back to the ORIGINAL
// council objection in that case would describe the wrong risk to the human:
// the concern the revision was written to fix, not the one the re-check just
// raised. This builds the escalation straight from the re-check's own
// `safety.reason` so that text — otherwise written nowhere — reaches the
// human and the events log. (PURE)
function safetyRecheckEscalation(slice, state, reason) {
  return escalated(slice, state, esc(slice, 'council-objection', {
    title: `SAFETY — re-check flags: ${reason.slice(0, 60)}`,
    context: reason,
    question: 'The revised plan raises a new safety risk. Accept it, revise by hand, or drop the slice?',
  }))
}

// A revision is a REMEDY CLAIM, not a remedy. Accepting `status: 'PLANNED'` on
// its own meant one silent retry absorbed the objection: nobody ever re-read
// the plan the council rejected, so a well-formed revision that fixed nothing
// reached implementation and the objection never reached the human, while the
// doctrine described the mechanism as blocking. The revision therefore goes
// back to ONE plan-critic seat and only a non-OBJECT, non-safety verdict
// proceeds. HONEST LIMITS, all deliberate: the re-check is a single
// full-council seat, NOT the original panel (guardian and skeptic do not
// re-run, so a tier-3 objection is re-checked by one member); it happens once,
// because state.replanned already vetoes a second replan; and the plan-time
// refactor-radius gate is NOT re-evaluated on the revised plan - that remains
// this run's logged, deliberate gap and would mean raising the trigger from a
// stage other than plan.

// Explicit null/type guards before any comparison: null, a non-object, or any
// status other than the literal 'PLANNED' is not a plan, and no truthiness
// shortcut gets to decide that. (PURE)
const isRevisedPlan = (r) => !!r && typeof r === 'object' && r.status === 'PLANNED'

// The human needs the reason the REVISION was rejected. `objection` is optional
// on CRITIQUE (required is verdict/safety/concerns), so a verdict without a
// readable one falls back to the original objection rather than throwing the
// same class of TypeError this file is closing elsewhere. (PURE)
const objectionSource = (v, fallback) => (v && v.objection && typeof v.objection.reason === 'string') ? v : fallback

async function recritiqueRevisedPlan(slice, state, plan) {
  const v = await dispatch(slice, state, 'critic:replan', criticPrompt(slice, plan, null),
    { agentType: 'spec-loop:plan-critic', schema: CRITIQUE, effort: 'high' })
  return v || failClosedCritique()
}

// The five judgements a re-check produces, computed once in one place: was a
// safety flag raised, is there a readable reason for it, does the revision
// proceed, and which reason does the human get. Split out of
// acceptRevisedPlan, which carried all of it plus two escalation shapes at
// cyclomatic 12 / cognitive 22 against thresholds of 10 and 15 — a function a
// reviewer had to hold entirely in their head to check any one of its
// branches. `rc` travels back out in the result so the caller never has to
// pass both the outcome and the critique to the next helper. (PURE)
function recheckOutcome(rc, ob) {
  const flagged = !!(rc.safety && rc.safety.flag === true)
  const safetyReason = flagged && typeof rc.safety.reason === 'string' ? rc.safety.reason : null
  const accepted = rc.verdict !== 'OBJECT' && !flagged
  const reason = accepted ? null : (safetyReason || objectionSource(rc, ob).objection.reason)
  return { rc, flagged, safetyReason, accepted, reason }
}

// Which of the two escalation shapes a rejected revision gets. The re-check's
// OWN safety reason wins whenever it exists, because falling back to the
// original council objection would describe the wrong risk to the human: the
// concern the revision was written to fix, not the one the re-check just
// raised. `o` and `ctx` travel as objects because parameter_count's threshold
// is 4 and this decision genuinely needs five values.
function recheckStop(slice, state, o, ctx) {
  if (o.safetyReason) return safetyRecheckEscalation(slice, state, o.safetyReason)
  return councilObjectionEscalation(slice, state, objectionSource(o.rc, ctx.ob), o.flagged || ctx.safety)
}

async function acceptRevisedPlan(slice, state, ctx) {
  const { revised, ob, safety } = ctx
  if (!isRevisedPlan(revised)) return { stop: councilObjectionEscalation(slice, state, ob, safety) }
  const rc = await recritiqueRevisedPlan(slice, state, revised)
  const o = recheckOutcome(rc, ob)
  state.events.push({ scope: slice.id, type: 'replan-recheck', payload: { verdict: rc.verdict, safety: o.flagged, accepted: o.accepted, reason: o.reason, safety_reason: o.safetyReason } })
  if (o.accepted) return { plan: revised }
  return { stop: recheckStop(slice, state, o, ctx) }
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
  return acceptRevisedPlan(slice, state, { revised, ob, safety })
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
// A re-entered slice whose plan has no tasks has nothing new to critique.
function emptyReentryPlan(slice, plan) {
  if (!entryOf(slice)) return false
  return (plan.tasks || []).length === 0
}

async function stageCritique(slice, state, plan) {
  if (state.review_tier < 2) return { plan }
  if (emptyReentryPlan(slice, plan)) return { plan }
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

// The OPEN (unaccepted) gate violations as P1 findings for the fix loop; each
// carries its fingerprint so an escalation can list it for acceptance by id.
function buildGateViolations(gate, state) {
  if (!gate) return []
  return splitViolations(gate.quality, state.accepted).open.map((v, i) => ({ id: `qg-${i}`, severity: 'P1', category: 'quality-gate', file: v.file || '-', line: 0, claim: `${v.metric} ${v.value} > threshold ${v.threshold} in ${v.function || v.file}`, evidence: { quote: JSON.stringify(v) }, remedy: 'behavior-preserving refactor (extract method, guard clauses, parameter object)', confidence: 'high', outside_diff: false, violation: withNumbers(v) }))
}

// The gate-only verifier dispatch, shared by stage R and the pre-escalation
// re-measure so the two cannot drift.
function dispatchGate(slice, state, role) {
  return dispatch(slice, state, role, gatePrompt(slice, state),
    { agentType: 'spec-loop:verifier', schema: VERIFY_RESULT, model: 'haiku', effort: 'low' })
}

// Stage R — review ∥ quality gate
async function stageReviewGate(slice, state, plan) {
  guard(slice, state)
  state.reviewPackage = `round${state.review.fix_rounds + 1}`
  const reviewers = selectReviewers(state)
  const [reviewParts, gate] = await parallel([
    () => parallel(reviewers.map(([role, lanes, opts]) => () =>
      dispatch(slice, state, role, reviewPrompt(slice, plan, state, lanes),
        { agentType: 'spec-loop:pr-reviewer', schema: REVIEW_RESULT, ...opts }))),
    () => dispatchGate(slice, state, 'gate'),
  ])
  const review = buildReviewSummary(reviewParts)
  const gateViolations = buildGateViolations(gate, state)
  stampQuality(slice, state, gate, 'gate')
  state.reviewersCount = reviewers.length
  return { review, gateViolations }
}

// Stage R for a fix-mode re-entry: gate only, no fresh review. The open set
// is the controller's orders plus whatever the gate measures at entry.head.
async function stageGateOnly(slice, state) {
  guard(slice, state)
  const gate = await dispatchGate(slice, state, 'gate')
  const gateViolations = buildGateViolations(gate, state)
  stampQuality(slice, state, gate, 'gate')
  state.reviewersCount = 0
  return { review: { findings: [], summary: 're-entry at fix: no fresh review; the open set is the controller\'s orders plus the measured gate violations' }, gateViolations }
}

// Re-measure the gate at the CURRENT head before a fix-loop escalation, so the
// record and the sidecar describe the tree the fix rounds left, not the one
// stage R saw. A throw here (agent cap, token floor, host failure) must not
// replace the caller's record with a budget one: the skip is written onto the
// quality block and as a decision, and the caller's own record goes out.
async function remeasureGate(slice, state) {
  try {
    stampQuality(slice, state, await dispatchGate(slice, state, 'gate:remeasure'), 'gate:remeasure')
  } catch (e) {
    recordSkippedRemeasure(slice, state, e)
  }
}

// A guard throw carries its own record ({escRecord}); anything else is read
// through its message. (PURE)
function throwReason(e) {
  if (e && e.escRecord) return e.escRecord.title
  return String((e && e.message) || e)
}

function recordSkippedRemeasure(slice, state, e) {
  const reason = throwReason(e)
  state.quality = { ...state.quality, detail: `${state.quality.detail}; re-measure skipped: ${reason}` }
  state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `gate re-measure before escalation skipped: ${reason}`, rationale: 'the fix-loop record keeps its own trigger; a throw during the re-measure never replaces it with a budget record', reversibility: 'n/a' } })
}

// Every fix-loop escalation leaves through here: the open findings go onto the
// sidecar as structured data (the datum the controller reconstructed by hand
// in run 20260908) and the gate is re-measured before the record goes out.
async function fixLoopEscalation(slice, state, ctx) {
  state.review.open = ctx.open
  await remeasureGate(slice, state)
  const violations = ctx.open.filter(f => f.category === 'quality-gate' && f.violation).map(f => f.violation)
  const content = ctx.trigger === 'quality-gate-block' ? { ...ctx.content, violations } : ctx.content
  return { stop: escalated(slice, state, esc(slice, ctx.trigger, content)) }
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
  if (outside.length) state.events.push({ scope: slice.id, type: 'review-summary', payload: { note: `fix round ${state.review.fix_rounds} touched files outside the original diff: ${outside.join(', ')}`, requires_full_rereview: true } })
}

function fixBlockerReason(fix) {
  return (fix && fix.blocker) || 'terminal dispatch failure'
}

async function dispatchFix(slice, state, ctx) {
  const { plan, open, round } = ctx
  return dispatch(slice, state, `fix:${state.review.fix_rounds}`, fixPrompt(slice, plan, state, open),
    { agentType: 'spec-loop:implementer', schema: FIX_RESULT, model: round === 0 ? 'sonnet' : 'inherit', effort: 'medium' })
}

const BEHAVIOURAL_CATEGORIES = ['correctness', 'errors']
const testedFindingIds = (fix) => new Set((Array.isArray(fix.tests_added) ? fix.tests_added : []).map(t => t && t.finding_id))

// A verdict closes a finding when it says ADDRESSED or REFUTATION_ACCEPTED —
// except an ADDRESSED behavioural finding the fixer named no covering test for,
// which stays open with a decision saying why. A fix without a pinning test is a
// claim; run 20260908 shipped ~16 such claims in code every report called green.
function keepsOpen(slice, state, finding, ctx) {
  const verdict = ctx.verdicts.get(finding.id)
  if (verdict !== 'ADDRESSED' && verdict !== 'REFUTATION_ACCEPTED') return true
  const untested = BEHAVIOURAL_CATEGORIES.includes(finding.category) && !ctx.tested.has(finding.id)
  if (verdict !== 'ADDRESSED' || !untested) return false
  state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `finding ${finding.id} closed without test evidence — kept open: the fixer named no covering test (tests_added) for a ${finding.category} finding`, rationale: 'a behavioural fix without a pinning test is a claim, not evidence; the next round must name the test', reversibility: 'n/a' } })
  return true
}

function closeRereviewedFindings(slice, state, rr, ctx) {
  const { open, round, bar, fix } = ctx
  const verdicts = new Map(rr.verdicts.map(x => [x.finding_id, x.verdict]))
  const kept = open.filter(f => keepsOpen(slice, state, f, { verdicts, tested: testedFindingIds(fix) }))
  return [...kept, ...blocking(rr.new_breakage, bar).map((f, i) => ({ ...f, id: `nb${round}-${i}` }))]
}

async function maybeVerifyFindings(slice, state, open) {
  return state.review_tier >= 3 ? verifyAndFilterFindings(slice, state, open) : open
}

async function runFixRound(slice, state, ctx) {
  const { plan, review, round, bar } = ctx
  const open = await maybeVerifyFindings(slice, state, ctx.open)
  if (!open.length) return { open }
  state.review.confirmed = open.length
  state.review.fix_rounds += 1
  const fix = await dispatchFix(slice, state, { plan, open, round })
  if (!fix || fix.status === 'BLOCKED')
    return fixLoopEscalation(slice, state, { open, trigger: 'review-block', content: { title: 'fix agent blocked', context: fixBlockerReason(fix), question: 'Blocking findings cannot be fixed automatically. Accept, guide, or drop?', options: reentryOptions('review-block') } })
  if (fix.commits && fix.commits.head) state.commits.head = fix.commits.head
  const rr = await dispatch(slice, state, `re-review:${state.review.fix_rounds}`, reReviewPrompt(slice, state, open, fix),
    { agentType: 'spec-loop:re-reviewer', schema: REREVIEW_RESULT, model: 'sonnet', effort: 'low' })
  state.fixPackage = `fix${state.review.fix_rounds}`
  if (!rr) return { open } // fail closed: findings stay open into the next round / escalation
  state.review.refuted += rr.verdicts.filter(x => x.verdict === 'REFUTATION_ACCEPTED').length
  recordOutsideDiffFix(slice, state, { plan, review, fix, round })
  return { open: closeRereviewedFindings(slice, state, rr, { open, round, bar, fix }) }
}

// Stage V/F — verify findings + fix loop (≤2 rounds)
async function stageFixLoop(slice, state, ctx) {
  const { plan, review, gateViolations } = ctx
  const bar = state.review_tier === 1 ? 'P0' : 'P0+P1'
  let open = [...blocking(review.findings, bar), ...gateViolations]
  open.push(...state.orders)
  for (let round = 0; open.length && round < MAX_FIX_ROUNDS; round++) {
    const res = await runFixRound(slice, state, { plan, review, open, round, bar })
    if (res.stop) return { stop: res.stop }
    open = res.open
  }
  if (!open.length) return fixLoopClean(slice, state, review, bar)
  const trigger = open.some(f => f.category === 'quality-gate') ? 'quality-gate-block' : 'review-block'
  return fixLoopEscalation(slice, state, { open, trigger, content: { title: `${open.length} blocking finding(s) unresolved after ${MAX_FIX_ROUNDS} fix rounds`, context: open.map(f => `${f.severity} ${f.file}:${f.line} — ${f.claim}`).join('\n'), question: 'Accept the residual findings, provide guidance, or drop the slice?', options: reentryOptions(trigger) } })
}

function fixLoopClean(slice, state, review, bar) {
  state.review.open = []
  state.review.residual = [...state.entryResidual, ...review.findings.filter(f => !blocking([f], bar).length).map(f => `${f.severity}: ${f.claim}`)].slice(0, 10)
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

function verifyAcceptable(v, state) {
  return !!(v && v.suite.passed && gateAcceptable(v.quality, state.accepted))
}

function verifyDetail(v, state) {
  const s = splitViolations(v.quality, state.accepted)
  const tail = v.quality.detail ? ` — ${v.quality.detail}` : ''
  return `suite: ${v.suite.summary}; quality: ${qualityStatus(v.quality)} (summary_pass=${String(v.quality.summary_pass)}, ${s.open.length} open, ${s.matched.length} accepted${tail})`
}

function verifySuiteFailed(v) {
  return !!(v && !v.suite.passed)
}

function verificationFailedEscalation(slice, state, v) {
  const trigger = verifySuiteFailed(v) ? 'review-block' : 'quality-gate-block'
  const detail = v ? verifyDetail(v, state) : 'verifier dispatch failed terminally'
  const gateBlock = !!v && trigger === 'quality-gate-block'
  const violations = gateBlock ? splitViolations(v.quality, state.accepted).open.map(withNumbers) : undefined
  return escalated(slice, state, esc(slice, trigger, { title: 'verification failed', context: detail, question: 'Verification cannot pass automatically. Guide, accept, or drop?', options: reentryOptions(trigger), violations }))
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
    recordVerification(slice, state, v, `verify:${attempt + 1}`)
    if (verifyAcceptable(v, state)) return doneResult(slice, state, 'DONE')
    if (attempt === 0 && verifySuiteFailed(v)) { await runDebugFix(slice, state, plan, v); continue }
    return verificationFailedEscalation(slice, state, v)
  }
  return escalated(slice, state, esc(slice, 'review-block', { title: 'verification loop exhausted', context: 'unreachable', question: 'Guide, accept, or drop?', options: [] }))
}

// The seven-stage sequence, unwrapped from the try/catch below so its own
// early-return checks aren't weighted by an extra level of nesting.
async function runStages(slice, state) {
  const entry = entryOf(slice)
  if (entry) {
    const bad = entryError(slice, state, entry)
    if (bad) return bad
    seedEntryState(slice, state, entry)
  }
  const built = await runBuildStages(slice, state, entry)
  if (built.stop) return built.stop
  return runQualityStages(slice, state, built.plan, entry)
}

// P/C/T — skipped entirely by a review/fix/verify re-entry, which runs under
// the plan file the first dispatch wrote.
async function runBuildStages(slice, state, entry) {
  if (entry && entry.stage !== 'plan') return { plan: entryPlan(slice, entry) }
  const p = await stagePlan(slice, state)
  if (p.stop) return p
  const c = await stageCritique(slice, state, p.plan)
  if (c.stop) return c
  const t = await stageTasks(slice, state, c.plan)
  if (t.stop) return t
  maybePromoteTier(slice, state, t.touched)
  return { plan: c.plan }
}

// R / V-F / S / Z — a verify re-entry runs Z alone; a fix re-entry replaces
// the review with a gate-only measurement; everything else runs the full tail.
async function runQualityStages(slice, state, plan, entry) {
  const stage = entry ? entry.stage : null
  if (stage === 'verify') return stageVerify(slice, state, plan)
  const rg = stage === 'fix' ? await stageGateOnly(slice, state) : await stageReviewGate(slice, state, plan)
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
// rather than a prediction of the final bound. A supplied override that took no
// effect is announced by recordDiscardedOverride instead.

// A supplied override the channel cannot use leaves the tier default in force.
// Announcing that once, at slice start, is the point: silence hides the discard
// until the slice reaches the cap a second time. It stays OUT of the
// agent-cap-override event, whose payload means a raise that took effect.
function recordDiscardedOverride(slice, state, base) {
  const supplied = JSON.stringify(CAP_OVERRIDES[slice.id])
  state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `agent cap override ${supplied} discarded: the channel takes an integer above the tier ${state.review_tier} default ${base}`, rationale: 'the override raises only, on an integer value; the tier default stays in force', reversibility: 'n/a' } })
}

// A key naming no slice of this wave raises nothing and belongs to no slice's
// own record, so it is announced once, on the wave's first slice, rather than
// dying silent.
function recordUnmatchedOverrides(slice, state) {
  const ids = A.slices.map(s => s.id)
  const unmatched = Object.keys(CAP_OVERRIDES).filter(k => !ids.includes(k))
  if (!unmatched.length || slice.id !== ids[0]) return
  state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `agent cap override keys naming no slice of this wave, raising nothing: ${unmatched.join(', ')}`, rationale: 'the override map is keyed by slice id; a key matching none of the dispatched slices reaches no guard', reversibility: 'n/a' } })
}

function recordCapOverride(slice, state) {
  const base = CAPS[state.review_tier]
  const cap = agentCap(slice, state)
  const supplied = Object.prototype.hasOwnProperty.call(CAP_OVERRIDES, slice.id)
  if (cap === base) {
    if (supplied) recordDiscardedOverride(slice, state, base)
    return
  }
  state.events.push({ scope: slice.id, type: 'agent-cap-override', payload: { tier: state.review_tier, default_cap: base, effective_cap: cap } })
}

// Every supplied acceptance is announced at slice start — the usable set, each
// discarded entry, and keys naming no slice of the wave — so an acceptance is
// never inferable only from a gate that stopped blocking.
function recordAcceptances(slice, state) {
  const raw = ACCEPTED[slice.id]
  if (Array.isArray(raw)) announceAcceptances(slice, state, raw)
  recordUnmatchedAcceptanceKeys(slice, state)
}

function announceAcceptances(slice, state, raw) {
  state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `${state.accepted.length} accepted violation fingerprint(s) supplied for ${slice.id}: ${state.accepted.map(describeFp).join(', ') || 'none usable'}`, rationale: 'controller-recorded acceptances (redispatch.py accept-violations); matched violations stop blocking the gate and are listed under quality.accepted', reversibility: 'moderate' } })
  raw.filter(fp => !usableFingerprint(fp)).forEach(fp => state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `accepted violation fingerprint ${JSON.stringify(fp)} discarded: a fingerprint is {metric, file, function|null} with no wildcard`, rationale: 'a metric-wide or wildcard acceptance would also accept a NEW breach the fix introduced', reversibility: 'n/a' } }))
}

function recordUnmatchedAcceptanceKeys(slice, state) {
  const ids = A.slices.map(s => s.id)
  const unmatched = Object.keys(ACCEPTED).filter(k => !ids.includes(k))
  if (!unmatched.length || slice.id !== ids[0]) return
  state.events.push({ scope: slice.id, type: 'decision', payload: { summary: `accepted violation keys naming no slice of this wave, accepting nothing: ${unmatched.join(', ')}`, rationale: 'the map is keyed by slice id; a key matching none of the dispatched slices reaches no gate', reversibility: 'n/a' } })
}

async function runSlice(slice) {
  const state = initSliceState(slice)
  recordCapOverride(slice, state)
  recordUnmatchedOverrides(slice, state)
  recordAcceptances(slice, state)
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
