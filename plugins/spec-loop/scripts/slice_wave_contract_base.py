"""Shared source-contract infrastructure for slice-wave.workflow.js.

The wave workflow is JavaScript and is not run by any lane of this repo's
suite: it is resolved at runtime from the installed plugin cache. Its
correctness has therefore rested entirely on review, and this run paid for
that twice - an unguarded optional-field read aborted a whole wave and was
mislabelled as a budget escalation (both the read and the mislabelling are now
pinned here). The three ``test_slice_wave_contract*.py`` modules that import
this one are the cheapest honest coverage available:
they parse the file with node (a real parse, not a substring) and pin the
handful of source facts whose loss is a known, observed outage - the
null-guards on TASK_RESULT.commits and its sibling optional arrays, the
type-safe read of CTX.scope_ceiling, the answer-injection sites, and the
record-only isolation of the over-scope flag from the four control-flow
branches, and the ONE-durable-record-per-defer-hinted-concern guarantee.

This module (and its importers) do NOT claim every optional agent-return
field is guarded. Two known instances of the same defect class remain
unguarded BY DECISION, deferred and logged by this run's own council rather
than fixed here: `plan.escalation.trigger` is read unguarded on the
ESCALATE branch (`PLAN_RESULT.required` is `['status']` only), and
`plan.split` is passed through as `undefined` on a SPLIT return that
carries no `split` object. Fixing either would exceed this task's scope
router; these modules pin what actually exists, not what a docstring would
prefer existed.

These are source-text assertions. They prove a guard is present; they
cannot prove it behaves. Any change to the workflow that trips one of them
is either a regression or an intentional contract change that belongs in
one of the importing modules too.

Every pinned JS snippet is a module-level constant rather than a literal in
a test body, and continuation lines use a 4-space hanging indent. Both are
deliberate: quality_gate.py's heuristics are line-based, so a `&&` or an `if`
inside a string literal scores as real branching (cognitive_complexity) and a
paren-aligned continuation scores as real nesting (nesting_depth). Naming the
snippets keeps the assertions byte-exact while the metrics stay honest.

Split out of one 422-non-blank-line module so each importing test module
stays under the quality gate's 300-line class_lines threshold; this file
carries no tests of its own (its class exposes no `test_*` method), so
`unittest discover -p 'test_*.py'` never collects it directly.

Usage: imported by test_slice_wave_contract.py,
test_slice_wave_contract_scope.py, and test_slice_wave_contract_crash.py;
not runnable on its own.
"""

import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "slice-wave.workflow.js"
SOURCE = WORKFLOW.read_text(encoding="utf-8")
# The file has a top-level `return` and `export const` (it is executed by the
# Workflow tool inside an async wrapper), so `node --check` refuses it as-is.
# Wrapping it the way the runtime does is what makes a real parse possible.
WRAP_HEAD = "async function __wrap(){\n"
WRAP_TAIL = "\n}\n"

# Anchors and pinned source lines (see the module docstring for why these are
# constants and not literals inside the test bodies).
TASK_RESULT_REQUIRED = "required: ['status', 'touched_files', 'concerns', 'deviations']"
# The task-result-handling region: taskNeedsRetry() through the end of
# stageTasks()'s loop, right before the "no commits at all" escalation below
# it. All of a TASK_RESULT's optional reads (commits/touched_files/concerns/
# deviations) are guarded somewhere in this span, split across runTask() and
# its small helpers rather than inlined in one loop body.
TASK_LOOP_START = "function taskNeedsRetry(r) {"
TASK_LOOP_END = "if (!state.commits.head)"
NO_COMMITS_ESCALATION = "'plan produced no commits'"
GUARDED_LOCAL = "const c = (r.commits && typeof r.commits === 'object') ? r.commits : {}"
GUARDED_HEAD = "if (c.head) state.commits.head = c.head"
GUARDED_BASE = "if (!state.commits.base && c.base) state.commits.base = c.base"
GUARDED_TOUCHED = "touched: r.touched_files || []"
GUARDED_CONCERNS = "...(r.concerns || [])"
GUARDED_DEVIATIONS = "...(r.deviations || []).map("
GATE_ANSWER = "answerFor(slice, 'quality-gate-block')"
GATE_ANSWER_CONTEXT = "answerContext(slice, 'quality-gate-block')"
ANSWER_CONTEXT_START = "const answerContext = (slice, trigger) => {"
ANSWER_CONTEXT_END = "\n}\n"
ANSWERABLE_TRIGGERS = (
    "ambiguity", "material-assumption", "review-block",
    "council-objection", "quality-gate-block")
CRITIQUE_REQUIRED = "required: ['verdict', 'safety', 'concerns']"
FAIL_CLOSED_DEFAULT = "unreadable critic verdict (fail closed)"
OVER_SCOPE_DEFAULT = "over_scope: null"
OVER_SCOPE_SCHEMA = "over_scope: { type: 'object'"
CRITIQUE_ROLLUP = "state.critique = { verdict:"
SPLIT_SUPPRESSION = "return (rec && depth < 2 && verdict !== 'OBJECT') ? rec : null"
OBJECTION_SELECTION = "ob: (safety || objections[0])"
REPLAN_VETO = "if (safety || !ob.fixable_by_replan || state.replanned)"
FINDING_CATEGORIES = "category: { enum: ["
# The trigger enum has five homes: this line, and the ESCALATION_TRIGGERS
# tuple in run_state.py, run_metrics.py and dashboard_server.py.
TRIGGER_ENUM_LINE = "trigger: { enum: ["
COUNCIL_VERDICT_EVENT = "type: 'council-verdict'"
SCOPE_HELPER = "function scopeRecord("
DERIVE_INPUTS_FN = "function deriveCouncilInputs(verdicts) {"
HELPER_END = "\n}\n"
SCOPE_LOCAL = "const scope = scopeRecord(verdicts)"
SCOPE_SPREAD = "...(scope ? { over_scope: scope } : {})"
SCOPE_REASON_KEPT = "reason: v.over_scope.reason"
SIDECAR_SCOPE_ATTACH = "if (scope) state.critique.over_scope = scope"
DEFERRAL_HELPER = "function deferralEvents("
DEFER_FILTER = "c.disposition_hint === 'defer'"
DEFERRED_TYPE = "type: 'deferred'"
DEFERRAL_EMIT = "deferralEvents(slice, concerns).forEach"
DEFERRAL_PAYLOAD = "payload: { summary: c.text"
DEFERRAL_MARKER = "...(c.over_scope ? { over_scope: true } : {})"
DEFERRAL_MARKER_FALSE = "over_scope: false"
CONCERN_MARKER = "over_scope: !!(v.over_scope && v.over_scope.flag === true)"
DEFERRED_ARRAY = (
    "deferred: concerns.filter(c => c.disposition_hint === 'defer')"
    ".map(c => c.text)")
STATE_DEFERRED_INIT = "deferred: []"
STATE_DEFERRED = "state.deferred"
STATE_STAGE_INIT = "stage: null"
STAGE_ASSIGNMENT = "state.stage = role"
DISPATCH_GUARD_CALL = "guard(slice, state)"
CRASH_STAGE_CONTEXT = "Last stage/role dispatched before the failure: ${stageText}"
CRASH_STAGE_PRECISION = "the most recent dispatch, not a per-throw stage"
CRASH_STAGE_OVERCLAIM = "in flight"
CRASH_TRIGGER = "esc(slice, 'internal-error',"
CRASH_STAGE_FALLBACK = (
    "const stageText = stage || "
    "'none (the crash happened before any agent was dispatched)'")
CRASH_TITLE_BRANCH = (
    "const title = stage ? `slice crashed after ${stage}` "
    ": 'slice crashed before any agent was dispatched'")
CRASH_TITLE_UNGRAMMATICAL = "crashed after ${stageText}"
CRASH_CLASSIFIED_PASSTHROUGH = "if (e && e.escRecord) return escalated(slice, state, e.escRecord)"
CRASH_OPTION_RETRY = "label: 'Retry this slice'"
CRASH_OPTION_SKIP = "label: 'Skip this slice'"
CRASH_OPTION_STOP = "label: 'Stop the run'"
CRASH_OPTION_CONTROLLER_ACTS = (
    "The CONTROLLER must act on this at the next dispatch")
CRASH_ERROR_FIRST = "`Error: ${String((e && e.message) || e)}."
CRASH_ERROR_EXPR = "${String((e && e.message) || e)}"
# The ONLY thing the escRecord check one line above the fallback proves: that
# neither structural guard RAISED its own record. It does NOT prove the crash
# originated outside a guard - `budget.remaining()` is called INSIDE the
# token-floor guard, so a throw from there starts in a guard and still reaches
# the fallback with no escRecord. The old phrasing asserted the stronger claim.
CRASH_CLASSIFICATION_SENTENCE = "neither structural guard raised its escalation record"
CRASH_GUARD_ORIGIN_OVERCLAIM = "so this crash came from neither"
CRASH_HOST_LAYER_CAVEAT = "host- or agent-layer resource failure"
# render_escalation() (run_state.py) collapses the context and hard-truncates it
# at 400 characters, and escalations.md is the corpus the escalation gate's
# precedent check reads. Both the exception text and the stage attribution have
# to fit inside that budget, ahead of the fixed classification prose.
CRASH_CONTEXT_RENDER_LIMIT = 400
CRASH_STAGE_CAVEAT = "so a starting point, not a culprit"
# The mirror-image overclaim this module now forbids: asserting "bug, NOT a
# budget limit" is as unprovable as the old "budget" assertion it replaced.
CRASH_CAUSE_OVERCLAIM = "This is a loop or agent-contract bug"
CRASH_BUDGET_DENIAL_OVERCLAIM = "NOT a cap or budget limit"
GUARD_BUDGET_TRIGGER = "esc(slice, 'budget-exhausted',"
SLICE_LOST_RECORD = "esc(A.slices[i], 'internal-error', 'slice lost',"
# Third instance of the same overclaim pattern: a thunk resolved to null
# proves nothing about the cause, so the lost-slice record must not deny one.
SLICE_LOST_CAUSE_DENIAL = "Not a resource limit."
STAGE_CRITIQUE_START = "async function stageCritique(slice, state, plan) {"
STAGE_CRITIQUE_END = "// Stage T helpers"
SPLIT_RETURN = "if (splitRec) return { stop: doneResult(slice, state, 'SPLIT'"
RECORD_DEFERRALS_FN = "function recordDeferrals(slice, state, concerns) {"
RECORD_DEFERRALS_CALL = "recordDeferrals(slice, state, concerns)"
RECORD_DEFERRALS_ON_ENDORSE = (
    "if (state.critique.verdict !== 'OBJECT') "
    "{ recordDeferrals(slice, state, concerns); return { plan } }")
RECORD_DEFERRALS_GUARDED = "if (!resolved.stop) recordDeferrals(slice, state, concerns)"
REVIEW_PROMPT = "function reviewPrompt("
GATE_PROMPT = "function gatePrompt("
ADVISORY_NOT_A_FILTER = "NOT a findings filter"
ADVISORY_FILE_ANYWAY = "file it regardless"
BLOCKING_HELPER = "function blocking(findings, bar)"
OPEN_SET = "let open = [...blocking(review.findings, bar), ...gateViolations]"
PACKET_START = "const packet = (slice) => ["
PACKET_END = "const answerFor"
SCOPE_CEILING_HELPER = "function scopeCeilingList(ctx) {"
SCOPE_CEILING_READ = "scopeCeilingList(CTX).length"
COMMAND_MD = Path(__file__).resolve().parents[1] / "commands" / "spec-loop.md"
CTX_TRAVELS_LINE = "the scope ceiling is run-level and travels in ctx"

# Drivers for the behavioural checks in the importing modules: each pairs the
# extracted pure-function source with a JSON argument list, run under real
# node. %s is the function source, then the JSON argument list.
SCOPE_DRIVER = """%s
const cases = %s
console.log(JSON.stringify(cases.map(c => scopeRecord(c))))
"""
DEFERRAL_DRIVER = """%s
const cases = %s
console.log(JSON.stringify(cases.map(c => deferralEvents(c[0], c[1]))))
"""
SCOPE_CEILING_DRIVER = """%s
const cases = %s
console.log(JSON.stringify(cases.map(c => scopeCeilingList(c))))
"""
# deriveCouncilInputs() calls scopeRecord() internally, so its driver source
# is both functions concatenated (see test_the_marker_is_broadcast_from_the_
# whole_verdict_not_the_concern for why this is the production wiring site,
# not a fixture already carrying the marker).
DERIVE_INPUTS_DRIVER = """%s
const cases = %s
console.log(JSON.stringify(cases.map(c => deriveCouncilInputs(c).concerns)))
"""

CLEAN = {"over_scope": {"flag": False, "reason": None}}
FLAGGED = {"over_scope": {"flag": True, "reason": "dashboard UI work"}}

# Two full CRITIQUE-shaped verdicts for deriveCouncilInputs(): one member
# flags the whole PLAN as over-scope while raising two concerns, only one of
# which is actually about scope; a second, clean member raises an unrelated
# concern of its own. Pins the real (member-broadcast) semantics: BOTH of
# the flagging member's concerns come back stamped `over_scope: True` -
# including the one with nothing to do with scope - while the clean member's
# concern comes back `over_scope: False`.
FLAGGING_MEMBER_VERDICT = {
    "verdict": "ENDORSE_WITH_CONCERNS",
    "safety": {"flag": False, "reason": None},
    "over_scope": {"flag": True, "reason": "plan pulls in a dashboard rewrite"},
    "concerns": [
        {"text": "this pulls in a dashboard rewrite", "disposition_hint": "defer"},
        {"text": "the retry helper needs a doc comment", "disposition_hint": "defer"},
    ],
}
CLEAN_MEMBER_VERDICT = {
    "verdict": "ENDORSE",
    "safety": {"flag": False, "reason": None},
    "concerns": [{"text": "clean concern from a clean member", "disposition_hint": "defer"}],
}

# Concern fixtures for the deferral behavioural checks, and the one event a
# plain deferral must produce. Module-level for the same reason the pinned
# snippets are: nesting_depth is measured from raw indentation, so a hanging
# literal inside a test body scores as real block nesting.
SLICE = {"id": "s1"}
FOLD_ME = {"text": "fold me", "disposition_hint": "fold"}
DEFER_ME = {"text": "defer me", "disposition_hint": "defer"}
NO_HINT = {"text": "no hint at all"}
CHARTS = {"text": "dashboard charts", "disposition_hint": "defer"}
MARKED = {"text": "flagged", "disposition_hint": "defer", "over_scope": True}
UNMARKED = {"text": "clean", "disposition_hint": "defer", "over_scope": False}
CHARTS_PAYLOAD = {"summary": "dashboard charts", "source": "plan-critique"}
CHARTS_EVENT = {"scope": "s1", "type": "deferred", "payload": CHARTS_PAYLOAD}
THREE_DEFERRALS = [{"text": "first", "disposition_hint": "defer"},
                    {"text": "second", "disposition_hint": "defer"},
                    {"text": "third", "disposition_hint": "defer"}]


def wrapped_source():
    """The workflow source in the async wrapper node can actually parse."""
    body = SOURCE.replace("\nexport const", "\nconst")
    if body.startswith("export const"):
        body = body[len("export "):]
    return WRAP_HEAD + body + WRAP_TAIL


class WorkflowSourceTestCase(unittest.TestCase):
    """Source-text helpers shared by every contract class in both importing
    modules. Carries no `test_*` method itself, so a bare `unittest
    discover` would collect zero tests from it even if this module were
    ever matched by a `test_*.py` glob (it currently is not - see module
    docstring)."""

    def setUp(self):
        self.src = SOURCE

    def line_containing(self, needle):
        """The one source line holding `needle` (a moved anchor fails loudly)."""
        hits = [l for l in self.src.splitlines() if needle in l]
        self.assertEqual(
            len(hits), 1,
            "expected exactly one line containing %r, found %d" % (needle, len(hits)))
        return hits[0]

    def between(self, start_needle, end_needle):
        """The source between two anchors, both of which must exist."""
        start = self.src.find(start_needle)
        end = self.src.find(end_needle, start + 1)
        self.assertNotEqual(start, -1, "missing anchor %r" % (start_needle,))
        self.assertNotEqual(end, -1, "missing anchor %r" % (end_needle,))
        return self.src[start:end]
