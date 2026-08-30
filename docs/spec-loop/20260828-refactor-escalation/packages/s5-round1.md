# Review package: e5479765c38247df97d5de9571a7f401b8deaff4..2b48a07  (context: -U5)

## Commits
2b48a07 docs(spec-loop): controller doctrine and changelog for the refactor-scope trigger
c558fc5 docs(spec-loop): the slice planner declares its refactor radius as numbers
0e62d95 docs(spec-loop): promote the escalation-gate doctrine to six judgment triggers

## Files changed
 CHANGELOG.md                                       |  15 ++
 plugins/spec-loop/agents/slice-planner.md          |  23 ++-
 plugins/spec-loop/commands/spec-loop.md            |  13 +-
 .../scripts/test_doctrine_refactor_scope.py        | 182 +++++++++++++++++++++
 plugins/spec-loop/skills/escalation-gate/SKILL.md  |  18 +-
 5 files changed, 245 insertions(+), 6 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
26,
40
]
],
"plugins/spec-loop/agents/slice-planner.md": [
[
3,
3
],
[
87,
107
]
],
"plugins/spec-loop/commands/spec-loop.md": [
[
164,
174
],
[
215,
215
]
],
"plugins/spec-loop/scripts/test_doctrine_refactor_scope.py": [
[
1,
182
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
50,
50
],
[
68,
74
],
[
99,
103
],
[
129,
129
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 45c585d..519785c 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -21,10 +21,25 @@ All notable changes to the spec-loop plugin are documented here. The format is
   a planner-declared proxy rather than a measured diff, so this cannot catch a blowup
   discovered mid-implementation; the check runs once, on the first plan, and a post-OBJECT
   replan is not re-evaluated; and a controller that does not thread `ctx.refactor_radius`
   records `NOT_CONFIGURED` and never halts.
 
+### Changed
+- **The autonomy contract now names six judgment triggers instead of five.**
+  `skills/escalation-gate/SKILL.md` adds `refactor-scope` as the sixth SURFACE trigger and
+  describes it accurately as the only one raised by the workflow's own arithmetic, at plan
+  time, on a measured breach; the same file keeps its separate, unchanged point that the
+  council's `over_scope` flag is a record that decides nothing and is still not a trigger.
+  `agents/slice-planner.md` gains the doctrine for declaring `rewrite_ratio`,
+  `touched_existing_files`, `rewritten_lines` and `basis` — numbers only, never a verdict, and
+  omitted rather than guessed as a zero — and `commands/spec-loop.md` applies the six-trigger
+  test and states how a `refactor-scope` answer is threaded back. Honest limits: this change is
+  prose and its new tests are substring assertions over that prose, so they prove the doctrine
+  is present and its five-trigger predecessor is gone, and nothing about whether an agent obeys
+  it; no runtime behaviour changes here, and the five-trigger sentences in `README.md` and
+  `references/risk-tiers.md` are not touched by this change.
+
 ## [2.2.2] - 2026-08-28
 ### Added
 - **The quality gate counts branch keywords in code, not in prose.** `quality_gate.py` now
   masks the content of string literals and comments before it scans a source, so a branch word
   or an operator character inside a docstring, a comment or a message string no longer inflates
diff --git a/plugins/spec-loop/agents/slice-planner.md b/plugins/spec-loop/agents/slice-planner.md
index 116d0ad..9ac2ed3 100644
--- a/plugins/spec-loop/agents/slice-planner.md
+++ b/plugins/spec-loop/agents/slice-planner.md
@@ -1,8 +1,8 @@
 ---
 name: slice-planner
-description: "Turns ONE slice goal into a small, bite-sized, TDD, no-placeholder plan a zero-context engineer could execute — each task carrying exact files, test-first steps, a verification command, and a model lane (transcribe|standard|judgment). Owns the right-size gate: a slice that bundles 2+ independently shippable changes returns SPLIT instead of a plan. Dispatched by the slice-wave workflow and by slice-worker-fallback; writes the plan file and nothing else."
+description: "Turns ONE slice goal into a small, bite-sized, TDD, no-placeholder plan a zero-context engineer could execute — each task carrying exact files, test-first steps, a verification command, and a model lane (transcribe|standard|judgment). Owns the right-size gate: a slice that bundles 2+ independently shippable changes returns SPLIT instead of a plan. Declares the plan's refactor radius as numbers for the workflow to judge against the run's ceiling, never as its own verdict. Dispatched by the slice-wave workflow and by slice-worker-fallback; writes the plan file and nothing else."
 tools: Read, Write, Bash, Grep, Glob
 model: inherit
 color: blue
 ---
 
@@ -82,10 +82,31 @@ to Task N" (repeat it — tasks are read out of order); a step that says what to
 showing how; a reference to a type or function no task defines. Before returning, re-read the
 plan against the slice goal with fresh eyes: every part of the goal maps to a task, no
 placeholder survived, and later tasks' signatures match what earlier tasks produce. Fix what
 you find inline.
 
+## Declaring the refactor radius
+
+With the plan you also return three numbers describing how much EXISTING code your final task
+list rewrites: `rewrite_ratio` — existing lines your tasks rewrite or delete ÷ total lines the
+plan changes; `touched_existing_files` — how many pre-existing files your tasks modify;
+`rewritten_lines` — the absolute count of existing lines rewritten or deleted; plus `basis`, one
+sentence naming how you counted. Count from the task list once it is final, not from the goal:
+a `Create:` file contributes to the denominator only, a `Modify:` file is the existing side.
+
+Report numbers, never a verdict. The workflow judges them against the run's configured ceiling
+and, on a measured breach and only then, raises a `refactor-scope` escalation asking the human to
+narrow the slice, approve the rewrite, or carve the refactor into its own slice. Deciding for
+yourself that a large rewrite is fine — or shading a number toward the ceiling — removes the
+human's one pre-execution look at it.
+
+Omit any number you genuinely cannot estimate rather than guessing. An absent number is read as
+unmeasured and never as a zero; an invented zero reads as a measured "no rewrite at all" and
+silently disarms the ceiling. If your dispatch prompt already carries a human answer to an
+earlier `refactor-scope` escalation for this slice, that question is already settled: plan to it
+and do not re-raise the question.
+
 ## Escalation
 
 Proceed-and-log is the default: anything determinable from the goal, the codebase, or the
 conventions is yours to decide, and trivial reversible choices (naming, fixture details,
 helper placement) never warrant a human. `ESCALATE` only for genuine ambiguity — two valid
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index 591648b..0ab88ce 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -159,10 +159,21 @@ deadlock is itself an escalation):
    raises — a value at or below the tier default is discarded by the wave, so it is no
    route to a tighter bound either. The TOKEN-FLOOR variant ("token budget exhausted")
    has no such lever: its resource is the wave budget the host supplies, and no args
    field in this contract changes the stage floor.
 
+   A `refactor-scope` record is the one trigger the wave raises from its own arithmetic
+   rather than from an agent's judgment: the plan stage compared the planner's declared
+   rewrite numbers against `ctx.refactor_radius` and stopped the slice before any
+   implementation dispatch. Write the answer back like any other, keyed
+   `answers["<slice-id>:refactor-scope"]` verbatim; the wave injects it into the
+   re-dispatched plan prompt and stops raising the halt for that slice. Answering it is the
+   only thing that unblocks the slice — re-dispatching without the answer recomputes the same
+   breach and stops again, and the ceiling itself is operator config, so there is no other
+   lever. Narrowing the slice instead is your call to make explicit: the wave does not split a
+   refactor out on its own.
+
    Then **re-dispatch the wave with ONLY its non-terminal slices** — filter `slices` to the ones
    whose sidecars are not DONE/SPLIT (merged work never re-enters a wave; its worktree is
    already gone) — same `ctx`, `answers` filled in, and `resumeFromRunId: <wf_id>` so the
    escalated slices' completed stages replay from the journal where the cache holds. Never
    rely on replay to make a terminal slice free: a cache miss re-runs it live against a
@@ -199,11 +210,11 @@ with `resumeFromRunId`, fresh invocation otherwise. All slices terminal → stra
 Phase 5 (regenerating `runbook.md` is safe).
 
 ## Escalation discipline
 
 You are the only layer that can ask the human. Never ask mid-wave, never one-at-a-time;
-apply the `escalation-gate` five-trigger test and precedent check to every candidate
+apply the `escalation-gate` six-trigger test and precedent check to every candidate
 question, including your own. Announce every question you do ask: immediately before ANY
 `AskUserQuestion` (escalation rounds, the publish prompt), fire a best-effort desktop alert —
 `printf '\a'; command -v osascript >/dev/null 2>&1 && osascript -e 'display notification
 "spec-loop run needs a decision" with title "spec-loop"' || true` — so an unattended run is
 never silently parked (a finished run once waited 7.6 hours at the publish prompt). An alert
diff --git a/plugins/spec-loop/scripts/test_doctrine_refactor_scope.py b/plugins/spec-loop/scripts/test_doctrine_refactor_scope.py
new file mode 100644
index 0000000..dedd98d
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_doctrine_refactor_scope.py
@@ -0,0 +1,182 @@
+#!/usr/bin/env python3
+"""Contract checks for the doctrine surfaces of the refactor-scope trigger.
+
+The gate itself is JavaScript and already pinned by
+test_slice_wave_contract_radius.py. This module pins the three PROSE
+surfaces a human or an agent actually reads - the escalation-gate skill,
+the slice-planner agent, and the controller command - against the shipped
+behaviour, because prose is a live plugin surface and drift in it is
+silent. The precedent is TestTheSkillDescribesTheLostSliceAsk in
+test_slice_wave_contract.py, which exists because exactly this drift
+happened once already.
+
+Honest limit: these are substring assertions over collapsed prose. They
+prove a sentence is present and that its superseded form is gone. They
+prove nothing about whether an agent obeys it, and they are not a
+behavioural test of the gate.
+
+A separate module rather than a class in an existing one:
+slice_wave_contract_base.py sits at 299 non-blank lines and
+test_slice_wave_contract_radius.py at 301, both at or over the quality
+gate's 300-line class_lines threshold.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_doctrine_refactor_scope.py'
+"""
+
+import re
+import sys
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+from slice_wave_contract_base import COMMAND_MD  # noqa: E402
+
+PLUGIN_ROOT = Path(__file__).resolve().parents[1]
+SKILL_MD = PLUGIN_ROOT / "skills" / "escalation-gate" / "SKILL.md"
+PLANNER_MD = PLUGIN_ROOT / "agents" / "slice-planner.md"
+
+
+def prose(path):
+    """One file's text with every whitespace run collapsed to a space. (PURE)"""
+    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
+
+
+# ---- the escalation-gate skill: six triggers, over-scope still not one ----
+
+SIX_HEADING = "### SURFACE to human (only these six triggers)"
+SIX_COUNT = "There are exactly six JUDGMENT triggers"
+SIX_BAR = "exactly the six triggers above"
+TRIGGER_NAME = "**Refactor scope** (`refactor-scope`)"
+TRIGGER_ARITHMETIC = "raised by the workflow's own arithmetic"
+TRIGGER_MEASURED = "an absent or unmeasured number is never a breach"
+OVER_SCOPE_KEPT = "raises no escalation, changes no verdict, suppresses no split"
+OVER_SCOPE_NOT_ONE = "an over-scope flag is not one of them"
+STALE_FIVE_HEADING = "only these five triggers"
+STALE_FIVE_COUNT = "exactly five JUDGMENT triggers"
+STALE_FIVE_BAR = "exactly the five triggers above"
+STALE_NOT_SIXTH = "an over-scope flag is not a sixth"
+STALE_FIVE_FORMS = (
+    STALE_FIVE_HEADING,
+    STALE_FIVE_COUNT,
+    STALE_FIVE_BAR,
+    STALE_NOT_SIXTH,
+)
+
+
+class TestTheSkillCountsSixJudgmentTriggers(unittest.TestCase):
+    """Three places in this file stated FIVE and one of them explicitly
+    denied a sixth. refactor-scope makes six. The over-scope flag must stay
+    excluded on its own separate grounds - it is a record, not a count."""
+
+    def setUp(self):
+        self.text = prose(SKILL_MD)
+
+    def test_all_three_five_trigger_statements_now_say_six(self):
+        for pin in (SIX_HEADING, SIX_COUNT, SIX_BAR):
+            self.assertIn(pin, self.text)
+
+    def test_no_superseded_five_trigger_sentence_survives(self):
+        for stale in STALE_FIVE_FORMS:
+            self.assertNotIn(stale, self.text)
+
+    def test_the_sixth_trigger_is_named_and_described_as_arithmetic(self):
+        self.assertIn(TRIGGER_NAME, self.text)
+        self.assertIn(TRIGGER_ARITHMETIC, self.text)
+
+    def test_the_sixth_trigger_fires_only_on_a_measured_breach(self):
+        self.assertIn(TRIGGER_MEASURED, self.text)
+
+    def test_the_over_scope_flag_is_still_a_record_and_still_not_a_trigger(self):
+        self.assertIn(OVER_SCOPE_KEPT, self.text)
+        self.assertIn(OVER_SCOPE_NOT_ONE, self.text)
+
+
+# ---- the planner agent: declares numbers, never a verdict ----
+
+PLANNER_SECTION = "## Declaring the refactor radius"
+PLANNER_THREE = "`rewrite_ratio`"
+PLANNER_FILES = "`touched_existing_files`"
+PLANNER_LINES = "`rewritten_lines`"
+PLANNER_BASIS = "`basis`"
+PLANNER_NO_VERDICT = "Report numbers, never a verdict"
+PLANNER_NO_ZERO = "Omit any number you genuinely cannot estimate rather than guessing"
+PLANNER_ABSENT = "An absent number is read as unmeasured and never as a zero"
+PLANNER_ANSWER = "already settled: plan to it and do not re-raise the question"
+PLANNER_LAST_TWO = ("## Statuses", "## Untrusted-data guard")
+
+
+class TestThePlannerIsToldToDeclareItsOwnRadius(unittest.TestCase):
+    """The workflow asks for these numbers in its dispatch prompt, but the
+    agent's own doctrine is what a planner reads when it decides HOW to
+    count them - and an invented zero reads as a measured 'no rewrite',
+    which silently disarms the ceiling."""
+
+    def setUp(self):
+        self.text = prose(PLANNER_MD)
+
+    def test_the_agent_has_a_section_naming_all_four_declared_fields(self):
+        self.assertIn(PLANNER_SECTION, self.text)
+        for field in (PLANNER_THREE, PLANNER_FILES, PLANNER_LINES, PLANNER_BASIS):
+            self.assertIn(field, self.text)
+
+    def test_the_planner_is_forbidden_from_reaching_its_own_verdict(self):
+        self.assertIn(PLANNER_NO_VERDICT, self.text)
+
+    def test_an_unknown_is_omitted_and_never_guessed_as_a_zero(self):
+        self.assertIn(PLANNER_NO_ZERO, self.text)
+        self.assertIn(PLANNER_ABSENT, self.text)
+
+    def test_an_answered_refactor_scope_question_is_not_re_raised(self):
+        self.assertIn(PLANNER_ANSWER, self.text)
+
+    def test_the_agent_body_keeps_its_two_mandatory_closing_sections_last(self):
+        raw = PLANNER_MD.read_text(encoding="utf-8")
+        statuses, guard = (raw.index(h) for h in PLANNER_LAST_TWO)
+        self.assertLess(raw.index(PLANNER_SECTION), statuses)
+        self.assertLess(statuses, guard)
+
+    def test_the_agent_file_still_carries_no_json_schema_block(self):
+        self.assertEqual(PLANNER_MD.read_text(encoding="utf-8").count("```json"), 0)
+
+
+# ---- the controller command: six triggers, and the answer's one route ----
+
+CMD_SIX = "`escalation-gate` six-trigger test"
+CMD_STALE_FIVE = "`escalation-gate` five-trigger test"
+CMD_ANSWER_KEY = '`answers["<slice-id>:refactor-scope"]`'
+CMD_ARITHMETIC = "the one trigger the wave raises from its own arithmetic"
+CMD_NO_OTHER_LEVER = "there is no other lever"
+CMD_CTX_KEY = "refactor_radius (the merged block verbatim from --print-config"
+CMD_ONE_DOOR = "--print-config"
+
+
+class TestTheControllerCarriesTheSixthTriggerEndToEnd(unittest.TestCase):
+    """The controller is the only layer that can ask a human, so its own
+    trigger count is load-bearing; and refactor-scope is the only trigger
+    whose answer is the sole thing that unblocks the slice, since no
+    re-dispatch clears a breach the arithmetic will just recompute."""
+
+    def setUp(self):
+        self.text = prose(COMMAND_MD)
+
+    def test_the_controller_applies_the_six_trigger_test(self):
+        self.assertIn(CMD_SIX, self.text)
+        self.assertNotIn(CMD_STALE_FIVE, self.text)
+
+    def test_the_answer_is_keyed_by_the_refactor_scope_id_verbatim(self):
+        self.assertIn(CMD_ANSWER_KEY, self.text)
+
+    def test_the_command_names_the_trigger_as_the_workflows_own_arithmetic(self):
+        self.assertIn(CMD_ARITHMETIC, self.text)
+        self.assertIn(CMD_NO_OTHER_LEVER, self.text)
+
+    def test_the_ctx_key_still_travels_from_the_one_config_door(self):
+        self.assertIn(CMD_ONE_DOOR, self.text)
+        self.assertIn(CMD_CTX_KEY, self.text)
+
+
+if __name__ == "__main__":  # pragma: no cover
+    unittest.main()
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index 410f703..f74c17a 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -45,11 +45,11 @@ The record is one `decision` event, payload
 (`run_state.py append-event --type decision`, stamped with its clock), or pushed onto a stage's
 `events[]` for the controller to stamp at collection (workflow scripts have no clock).
 `decisions-log.md` is *rendered* from those events: never hand-write an entry, and never rely on its
 wording — v2 pins no line grammar.
 
-### SURFACE to human (only these five triggers)
+### SURFACE to human (only these six triggers)
 
 Do not act. Return an `EscalationRecord` and let the controller batch it:
 
 1. **Genuine ambiguity** — there are ≥2 valid interpretations that materially change scope or
    behavior, and the codebase/spec cannot resolve which is intended.
@@ -63,10 +63,17 @@ Do not act. Return an `EscalationRecord` and let the controller batch it:
    hole, broken public contract). Lesser concerns (ENDORSE_WITH_CONCERNS, minority non-safety
    objections) are folded into the plan and logged — they do **not** surface.
 5. **Unfixable quality-gate block** — the quality gate's metrics still exceed the configured
    thresholds after the fix loop's behavior-preserving refactors. Thresholds are never weakened
    to avoid this.
+6. **Refactor scope** (`refactor-scope`) — the plan a slice just produced declares a rewrite of
+   existing code larger than the run's configured ceiling (`ctx.refactor_radius`). This is the one
+   trigger raised by the workflow's own arithmetic on planner-declared numbers rather than by an
+   agent's judgment, and it is raised at plan time, before a single implementation dispatch is
+   spent. It asks the human to narrow the slice, approve the rewrite, or carve the refactor out.
+   It fires only on a MEASURED breach: an absent or unmeasured number is never a breach, and no
+   number is ever inferred to be zero.
 
 When uncertain whether something is "material": if a reasonable reviewer could reject the slice
 over it, it is material → surface it.
 
 The enum lives in `slice-wave.workflow.js` (`ESCALATION.trigger`). Three things that are
@@ -87,12 +94,15 @@ passes to `esc`, alongside the one `runSliceError` already passed. What still se
 is the evidence and the ask: the exception record carries the exception text and the last
 stage/role dispatched and asks which of the three to take, while the lost-slice record carries
 neither and asks the same three-way question with its own tail, ending "or stop the run to investigate the silent failure"),
 and the council's **over-scope flag** (`critique.over_scope.flag`). The flag is a record: it is
 carried into the `council-verdict` payload and the slice sidecar with its reason, and it raises no
-escalation, changes no verdict, suppresses no split, and blocks nothing. There are exactly five
-JUDGMENT triggers; an over-scope flag is not a sixth.
+escalation, changes no verdict, suppresses no split, and blocks nothing. There are exactly six
+JUDGMENT triggers, and the sixth is `refactor-scope` — a threshold comparison the workflow performs
+on itself, which is why it belongs on the list even though no agent asked for it. Still, an
+over-scope flag is not one of them, and not because of the count: it stays a record because it
+decides nothing.
 
 ### Precedent check (before returning any SURFACE escalation)
 
 Prior runs' human answers are settled decisions — check them before asking a question the human
 may have already answered. Search prior runs (excluding this one): answered escalation records
@@ -114,11 +124,11 @@ on the text, never on a pinned format.
 The controller repeats this check over every open record at the wave boundary.
 
 ### Not triggers (autonomous by design)
 
 Three things that look like stopping points but are handled by the loop itself, keeping the bar at
-exactly the five triggers above:
+exactly the six triggers above:
 
 - **Slice split.** A slice that turns out to be two-or-more independently shippable changes
   returns `SPLIT`; the controller grafts the children into the DAG (`dag.py ingest-split`) —
   logged, no human contact. Only a proposal that is malformed or already at the depth cap falls
   back to a trigger above (see `references/split-ingestion.md`).
