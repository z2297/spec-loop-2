# Review package: c83b8fba90b8a4b5120c60950687866a63cb59bc..049d21b  (context: -U5)

## Commits
049d21b docs(controller): session marker at Phase 1 and Resume, .paused lifecycle
3fea0d7 docs(controller): record escalation-opened before asking the human
f3fcf04 docs(controller): Phase 2 step 9 closes the wave loop in the same turn
f4ba3d4 docs(escalation-gate): a runnable wave boundary is not a stopping point

## Files changed
 plugins/spec-loop/commands/spec-loop.md            |  55 ++++-
 .../scripts/test_doctrine_loop_boundary.py         | 232 +++++++++++++++++++++
 plugins/spec-loop/skills/escalation-gate/SKILL.md  |   9 +-
 3 files changed, 286 insertions(+), 10 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/commands/spec-loop.md": [
[
21,
23
],
[
74,
77
],
[
192,
209
],
[
228,
235
],
[
246,
258
]
],
"plugins/spec-loop/scripts/test_doctrine_loop_boundary.py": [
[
1,
232
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
128,
128
],
[
143,
149
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index 0ab88ce..13375aa 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -16,11 +16,13 @@ Single-home contracts you follow (read on demand, never restate): run-state and
 
 Invariants (non-negotiable): single-branch integration — every slice merges into ONE local
 integration branch, never `main`/`master`; the loop never pushes before the human's publish
 choice (`--per-slice-pr` is the sole exception); merges are yours alone, serial, `--no-ff`;
 timestamps are yours alone (`date -u +%Y-%m-%dT%H:%M:%SZ`) — workflows have no clock; every
-artifact you hand an agent is a file path, never pasted content.
+artifact you hand an agent is a file path, never pasted content; a wave boundary is a
+dispatch point, not a reporting boundary — while any slice is runnable, Phase 2 step 9
+re-dispatches in the SAME turn.
 
 ## Phase 0 — Intake
 
 1. `--resume <run-id>` short-circuits to **Resume** below (wins over every other flag).
 2. Parse flags. Defaults: `--max-parallel 5`, `--risk-floor 1`. `--from-plan` reads the given
@@ -67,10 +69,14 @@ artifact you hand an agent is a file path, never pasted content.
 4. Create `docs/spec-loop/<run-id>/` with `.active`, `request.md`, `conventions.md`,
    `dag.json` (schema per run-state-v2.md, `mode: "workflow"`, plus `shared_constraints` and
    the optional run-level `scope_ceiling` from Phase 0), and empty `events.jsonl`;
    append a `run-created` event via `run_state.py append-event`. Ensure `.worktrees/` is
    gitignored. Validate: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dag.py" validate --run-dir <dir>`.
+   Write `.controller-session` beside `.active`, containing your session id: the
+   loop-boundary gate reads it and tells your turns from any other session's on this machine.
+   Neither marker is ever committed — `.gitignore` covers both, bare and unanchored, and
+   `test_doctrine_marker_hygiene.py` fails if either re-enters the index.
 5. Knowledge graph (if enabled): one `knowledge_graph.py batch` seeding the system hub + run
    MOC (`ensure_base: true`).
 
 ## Phase 2 — Wave loop
 
@@ -181,10 +187,28 @@ deadlock is itself an escalation):
    result arrives for a slice you did not include, discard it without persisting. (A journal
    lost to a session restart just means the remaining slices re-run live — sidecars bound
    the loss to one wave.)
 8. Knowledge graph (if enabled): one `batch` call upserting the wave's `decision` nodes and
    touched `component` hubs, extracted from the wave's events.
+9. **Close**: re-run `dag.py next-wave` and act on it in THIS turn —
+   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dag.py" next-wave --run-dir <dir>`. Non-empty
+   `slice_ids` → return to step 1 immediately, in the same turn, with no status report and no
+   question: a wave boundary is a dispatch point, not a reporting boundary, and what the wave
+   just did is reported at the runbook. `done: true` → Phase 5. `deadlock: true` → escalate
+   with the `blocked` list; that is a real escalation, never a stall to sit on. Judge
+   runnability on `slice_ids` being non-empty and never on the absence of a `done` key — a
+   deadlock report carries no `done` key at all, so reading a missing `done` as "keep going"
+   would swallow both the deadlock question and the Phase 5 publish prompt. If you do end the
+   turn here anyway, say why in your next message so the transcript carries the reason.
+   `.paused` is the one deliberate escape from the loop-boundary gate: the HUMAN asks for it
+   and YOU write `docs/spec-loop/<run-id>/.paused`. It relaxes the loop-boundary gate alone —
+   every other `.active` restriction (pushes before the publish choice, broad staging,
+   default-branch commits and merges, gate-config writes) still applies. You delete it yourself
+   the moment the human says resume; `--resume` does NOT clear it, so a resumed run is unpaused
+   only once you remove the file. Never write it to get past a gate of your own accord. Like a
+   stale `.active`, a stale `.paused` is remediated by resuming the run or clearing the marker,
+   in that order — and it is never committed.
 
 ## Phase 5 — Integration gate & finish
 
 Follow `references/phase-5-integration.md`: full suite on the integration branch → ONE
 cross-slice `pr-reviewer` (mode `integration`, session model, high effort) over
@@ -199,26 +223,39 @@ a fragmented run dir is an escalation, not a `.done`. Your final output is the r
 Executive Readout, verbatim.
 
 ## Resume
 
 `--resume <run-id>`: read `dag.json` (recover branch, mode, wave history), recreate
-`.active`, checkout the integration branch (clean-tree guard), `worktrees.py prepare
---resume` for the incomplete wave's slices, drain EVERY answered escalation of the run into
-the `answers` map (every round, already-dispatched ones included, per step 7's
-cumulative-map invariant), and re-enter the wave loop at the first incomplete wave —
-same-session
-with `resumeFromRunId`, fresh invocation otherwise. All slices terminal → straight to
-Phase 5 (regenerating `runbook.md` is safe).
+`.active`, rewrite `.controller-session` with your NEW session id (the previous
+session's id is stale the moment this one starts), checkout the integration branch
+(clean-tree guard), `worktrees.py prepare --resume` for the incomplete wave's slices, drain
+EVERY answered escalation of the run into the `answers` map (every round,
+already-dispatched ones included, per step 7's cumulative-map invariant), and re-enter the
+wave loop at the first incomplete wave — same-session with `resumeFromRunId`, fresh
+invocation otherwise. All slices terminal → straight to Phase 5 (regenerating `runbook.md`
+is safe).
 
 ## Escalation discipline
 
 You are the only layer that can ask the human. Never ask mid-wave, never one-at-a-time;
 apply the `escalation-gate` six-trigger test and precedent check to every candidate
 question, including your own. Announce every question you do ask: immediately before ANY
 `AskUserQuestion` (escalation rounds, the publish prompt), fire a best-effort desktop alert —
 `printf '\a'; command -v osascript >/dev/null 2>&1 && osascript -e 'display notification
 "spec-loop run needs a decision" with title "spec-loop"' || true` — so an unattended run is
 never silently parked (a finished run once waited 7.6 hours at the publish prompt). An alert
-failure is ignored, never a reason to delay the question. Every autonomous decision = one `decision` event with
+failure is ignored, never a reason to delay the question.
+
+Before ANY controller-originated `AskUserQuestion` — a reported deadlock, a decomposition
+ambiguity, a config first-run choice, the publish prompt, any question you raise yourself
+rather than a wave — append the record FIRST, then ask:
+`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run_state.py" append-event --run-dir <dir> --ts <now>
+--scope run --type escalation-opened --payload <EscalationRecord JSON>`. The order is the
+point: `open-escalations` reads events.jsonl, so a question asked before its record exists is
+invisible to a resume and to anything else reading run state, and the `escalation-answered`
+event you write back pairs by an `id` that was never opened. This excludes records a wave
+raised are already appended by `persist-slice` — never re-append those.
+
+Every autonomous decision = one `decision` event with
 rationale and reversibility. When a workflow result surprises you (empty, malformed,
 contradicting its own events), read the workflow journal before re-dispatching — never
 re-run work you merely failed to look at.
diff --git a/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py b/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
new file mode 100644
index 0000000..fd740c7
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_doctrine_loop_boundary.py
@@ -0,0 +1,232 @@
+#!/usr/bin/env python3
+"""Doctrine checks for the Phase-2 loop-boundary prose.
+
+The loop's failure this slice exists to fix is prose-shaped: a controller
+that reaches a wave boundary with slices still runnable and ends its turn
+to report. Nothing in the shipped prose said the boundary is a dispatch
+point, and the escalation-gate's "Not triggers" list did not name it.
+Those sentences are now load-bearing, so they are pinned here.
+
+Honest limits: these are substring assertions over collapsed prose plus
+one count of bullets on disk. They prove a sentence is present and that
+its superseded form is gone. They prove nothing about whether a
+controller obeys it, and they are NOT a behavioural test of the Stop
+gate - that gate lives in spec_loop_guard.py and is tested there.
+
+A separate module rather than a class in test_doctrine_refactor_scope.py
+or test_doctrine_run_docs.py: those are owned by other slices' doctrine,
+and slice_wave_contract_base.py is at its 300-line class ceiling.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_doctrine_loop_boundary.py'
+"""
+
+import re
+import unittest
+from pathlib import Path
+
+PLUGIN_ROOT = Path(__file__).resolve().parents[1]
+COMMAND_MD = PLUGIN_ROOT / "commands" / "spec-loop.md"
+SKILL_MD = PLUGIN_ROOT / "skills" / "escalation-gate" / "SKILL.md"
+
+NUMBER_WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
+
+NOT_TRIGGERS_HEADING = "### Not triggers (autonomous by design)"
+
+
+def prose(path):
+    """One file's text with every whitespace run collapsed to a space. (PURE)"""
+    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
+
+
+def not_trigger_bullet_count():
+    """Count the `- **` bullets under SKILL.md's "Not triggers" heading.
+
+    Read off the file rather than remembered, so the count word in the
+    section's own opening sentence cannot drift away from the list it
+    counts. The section ends at the next `## ` heading.
+    """
+    lines = SKILL_MD.read_text(encoding="utf-8").splitlines()
+    start = next(i for i, line in enumerate(lines)
+                 if line.strip() == NOT_TRIGGERS_HEADING)
+    count = 0
+    for line in lines[start + 1:]:
+        if line.startswith("## "):
+            break
+        if line.startswith("- **"):
+            count += 1
+    return count
+
+
+# ---- the skill: a runnable wave boundary is not a stopping point ----
+
+SKILL_BOUNDARY_BULLET = "**A wave boundary with slices still runnable.**"
+SKILL_DISPATCH_POINT = "a dispatch point, not a decision"
+SKILL_RUNNABLE_ONLY = "This entry covers the RUNNABLE case ONLY"
+SKILL_DEADLOCK_KEPT = "is the opposite: it is a genuine escalation"
+SKILL_PINNED_TAIL = "exactly the six triggers above"
+SKILL_OTHER_LIST = "Three things that are deliberately NOT judgment triggers"
+SKILL_STALE_COUNT = "Three things that look like stopping points"
+
+
+class TestTheSkillNamesTheRunnableWaveBoundary(unittest.TestCase):
+    """The list of things that look like stopping points but are handled by
+    the loop grows a fourth entry. It must be readable ONLY as the runnable
+    case: a reported deadlock is a real escalation, and a reader who
+    generalised this entry would swallow it."""
+
+    def setUp(self):
+        self.text = prose(SKILL_MD)
+
+    def test_the_fourth_not_trigger_is_the_runnable_wave_boundary(self):
+        self.assertIn(SKILL_BOUNDARY_BULLET, self.text)
+        self.assertIn(SKILL_DISPATCH_POINT, self.text)
+
+    def test_the_entry_is_scoped_to_runnable_and_spares_deadlock(self):
+        self.assertIn(SKILL_RUNNABLE_ONLY, self.text)
+        self.assertIn(SKILL_DEADLOCK_KEPT, self.text)
+
+    def test_the_count_word_matches_the_bullets_on_disk(self):
+        count = not_trigger_bullet_count()
+        self.assertEqual(count, 4)
+        word = NUMBER_WORDS[count]
+        self.assertIn(
+            "%s things that look like stopping points" % word, self.text)
+
+    def test_the_superseded_three_count_is_gone(self):
+        self.assertNotIn(SKILL_STALE_COUNT, self.text)
+
+    def test_the_pinned_tail_clause_and_the_other_list_are_untouched(self):
+        self.assertIn(SKILL_PINNED_TAIL, self.text)
+        self.assertIn(SKILL_OTHER_LIST, self.text)
+
+
+# ---- the command: Phase 2 closes its own loop ----
+
+CLOSE_STEP = "9. **Close**:"
+CLOSE_RECOMPUTE = "re-run `dag.py next-wave` and act on it in THIS turn"
+CLOSE_SAME_TURN = "return to step 1 immediately, in the same turn, with no status report"
+CLOSE_DONE = "`done: true` → Phase 5"
+CLOSE_DEADLOCK = "`deadlock: true` → escalate with the `blocked` list"
+CLOSE_ON_SLICE_IDS = (
+    "Judge runnability on `slice_ids` being non-empty and never on the absence "
+    "of a `done` key")
+CLOSE_NO_DONE_KEY = "a deadlock report carries no `done` key at all"
+CLOSE_VISIBLE_TRACE = "say why in your next message so the transcript carries the reason"
+INVARIANT_BOUNDARY = "a wave boundary is a dispatch point, not a reporting boundary"
+
+
+class TestPhase2ClosesTheWaveLoopInTheSameTurn(unittest.TestCase):
+    """The controller command is the only place the loop's turn discipline is
+    written. Phase 2 ended at step 8 with no instruction to recompute, which
+    is how a turn ends with slices still runnable."""
+
+    def setUp(self):
+        self.text = prose(COMMAND_MD)
+
+    def test_phase_2_has_a_closing_step(self):
+        self.assertIn(CLOSE_STEP, self.text)
+        self.assertIn(CLOSE_RECOMPUTE, self.text)
+
+    def test_the_closing_step_states_all_three_outcomes(self):
+        for pin in (CLOSE_SAME_TURN, CLOSE_DONE, CLOSE_DEADLOCK):
+            self.assertIn(pin, self.text)
+
+    def test_runnability_is_judged_on_slice_ids_not_a_missing_done_key(self):
+        self.assertIn(CLOSE_ON_SLICE_IDS, self.text)
+        self.assertIn(CLOSE_NO_DONE_KEY, self.text)
+
+    def test_a_deliberate_stop_must_leave_a_visible_reason(self):
+        self.assertIn(CLOSE_VISIBLE_TRACE, self.text)
+
+    def test_the_invariants_line_names_the_boundary_as_a_dispatch_point(self):
+        self.assertIn(INVARIANT_BOUNDARY, self.text)
+        head = self.text.index("Invariants (non-negotiable)")
+        self.assertLess(head, self.text.index(INVARIANT_BOUNDARY))
+        self.assertLess(self.text.index(INVARIANT_BOUNDARY),
+                        self.text.index("## Phase 0 — Intake"))
+
+
+# ---- the command: record the escalation BEFORE asking ----
+
+OPEN_FIRST = "append the record FIRST, then ask"
+OPEN_CLI = "--type escalation-opened"
+OPEN_SCOPE = "any question you raise yourself rather than a wave"
+OPEN_WHY = "a question asked before its record exists is invisible to a resume"
+OPEN_NO_DOUBLE = "records a wave raised are already appended by `persist-slice`"
+
+
+class TestControllerQuestionsAreRecordedBeforeTheyAreAsked(unittest.TestCase):
+    """`open-escalations` reads events.jsonl, so an unrecorded question is a
+    question no resume and no run-state reader can see, and an answer written
+    back pairs by an id that was never opened."""
+
+    def setUp(self):
+        self.text = prose(COMMAND_MD)
+
+    def test_the_record_is_appended_before_the_question_is_asked(self):
+        self.assertIn(OPEN_FIRST, self.text)
+        self.assertIn(OPEN_CLI, self.text)
+
+    def test_the_rule_names_which_questions_it_covers(self):
+        self.assertIn(OPEN_SCOPE, self.text)
+
+    def test_the_rule_says_why_the_order_matters(self):
+        self.assertIn(OPEN_WHY, self.text)
+
+    def test_wave_raised_records_are_not_re_appended(self):
+        self.assertIn(OPEN_NO_DOUBLE, self.text)
+
+    def test_the_rule_lives_in_the_escalation_discipline_section(self):
+        head = self.text.index("## Escalation discipline")
+        self.assertLess(head, self.text.index(OPEN_FIRST))
+
+
+# ---- the command: the two session/pause markers ----
+
+SESSION_WRITE = "`.controller-session` beside `.active`, containing your session id"
+SESSION_PURPOSE = "tells your turns from any other session's on this machine"
+SESSION_NEVER_COMMITTED = "Neither marker is ever committed"
+SESSION_RESUME = "rewrite `.controller-session` with your NEW session id"
+PAUSED_WHO = "the HUMAN asks for it and YOU write"
+PAUSED_ONE_GATE = "relaxes the loop-boundary gate alone"
+PAUSED_CLEAR = "delete it yourself the moment the human says resume"
+PAUSED_RESUME = "`--resume` does NOT clear it"
+PAUSED_REMEDIATION = (
+    "a stale `.paused` is remediated by resuming the run or clearing the marker, "
+    "in that order")
+PAUSED_NEVER_SELF = "Never write it to get past a gate of your own accord"
+
+
+class TestTheMarkerLifecyclesAreWrittenDown(unittest.TestCase):
+    """`.controller-session` scopes the gate to the controller and `.paused` is
+    its only deliberate escape. A `.paused` nobody clears is a gate lost with
+    no report, so who writes it, who clears it, and what resume does with it
+    all have to be on the page."""
+
+    def setUp(self):
+        self.text = prose(COMMAND_MD)
+
+    def test_phase_1_writes_the_controller_session_marker(self):
+        self.assertIn(SESSION_WRITE, self.text)
+        self.assertIn(SESSION_PURPOSE, self.text)
+
+    def test_the_markers_are_stated_once_to_be_uncommitted(self):
+        self.assertIn(SESSION_NEVER_COMMITTED, self.text)
+
+    def test_resume_rewrites_the_session_marker(self):
+        self.assertIn(SESSION_RESUME, self.text)
+        self.assertLess(self.text.index("## Resume"),
+                        self.text.index(SESSION_RESUME))
+
+    def test_the_paused_lifecycle_names_who_writes_and_who_clears(self):
+        for pin in (PAUSED_WHO, PAUSED_CLEAR, PAUSED_NEVER_SELF):
+            self.assertIn(pin, self.text)
+
+    def test_paused_relaxes_one_gate_and_survives_a_resume(self):
+        self.assertIn(PAUSED_ONE_GATE, self.text)
+        self.assertIn(PAUSED_RESUME, self.text)
+
+    def test_the_stale_paused_remediation_sentence_is_present(self):
+        self.assertIn(PAUSED_REMEDIATION, self.text)
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index f74c17a..baf3928 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -123,11 +123,11 @@ on the text, never on a pinned format.
 
 The controller repeats this check over every open record at the wave boundary.
 
 ### Not triggers (autonomous by design)
 
-Three things that look like stopping points but are handled by the loop itself, keeping the bar at
+Four things that look like stopping points but are handled by the loop itself, keeping the bar at
 exactly the six triggers above:
 
 - **Slice split.** A slice that turns out to be two-or-more independently shippable changes
   returns `SPLIT`; the controller grafts the children into the DAG (`dag.py ingest-split`) —
   logged, no human contact. Only a proposal that is malformed or already at the depth cap falls
@@ -138,10 +138,17 @@ exactly the six triggers above:
 - **Over-scope and deferred scope.** A plan that exceeds the run's scope ceiling is flagged
   (`over_scope`) and, when the goal genuinely asks for it, still built; work the council
   asks not to be built is a `defer`-hinted concern recorded as one `deferred` event per
   concern. Both are records for the human to read at the runbook, not questions — and
   neither ever suppresses a finding.
+- **A wave boundary with slices still runnable.** When `dag.py next-wave` reports a non-empty
+  `slice_ids`, the boundary is a dispatch point, not a decision: the controller re-dispatches
+  the next wave in the SAME turn, and what the finished wave did is reported at the runbook
+  rather than mid-loop. Ending the turn there is the stall this list exists to prevent, not a
+  question. This entry covers the RUNNABLE case ONLY — a reported `deadlock` (nothing runnable
+  while slices remain) is the opposite: it is a genuine escalation the controller surfaces, and
+  nothing here downgrades it.
 
 ## Batching rule (critical for non-blocking operation)
 
 **Never interrupt mid-wave, never one question at a time.** Workflow stages cannot prompt the
 human, so:
