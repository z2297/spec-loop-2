# Review package: 25b7b6c57fa4a67804578f15c25024cf46cfe184..ca89a10748f946b00a4c085217bafdb2163c30e2  (context: -U5)

## Commits
ca89a10 changelog: consolidate the refactor-escalation run into one honest entry
70ea795 docs(spec-loop): the component inventory names the new test-support modules
2259855 docs(spec-loop): risk tiers name six triggers and exclude the plan-time one
e7da94e docs(spec-loop): the readme counts six judgment triggers

## Files changed
 CHANGELOG.md                                       | 107 ++++++++-------
 plugins/spec-loop/README.md                        |  19 ++-
 plugins/spec-loop/references/risk-tiers.md         |  13 +-
 .../spec-loop/scripts/test_doctrine_run_docs.py    | 145 +++++++++++++++++++++
 4 files changed, 228 insertions(+), 56 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
10,
27
],
[
30,
43
],
[
45,
51
],
[
54,
55
],
[
61,
82
]
],
"plugins/spec-loop/README.md": [
[
99,
99
],
[
101,
108
],
[
158,
160
]
],
"plugins/spec-loop/references/risk-tiers.md": [
[
86,
86
],
[
88,
94
]
],
"plugins/spec-loop/scripts/test_doctrine_run_docs.py": [
[
1,
145
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index e888418..294e9d3 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -5,64 +5,83 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 ### Added
-- **The wave workflow now halts a slice at PLAN time when its plan declares a rewrite of
-  existing code larger than the run's configured ceiling.** `slice-wave.workflow.js` gains
-  an optional `refactor_radius` block on `PLAN_RESULT` that the planner fills with declared
-  numbers, a pure `refactorRadiusStatus()` predicate that judges them in JS — mirroring
-  `qualityStatus()`, with every comparison behind an explicit null guard because
-  `undefined >= n` is false and `null >= 0` is true — and a `refactor-scope` escalation
-  offering three trade-offs (narrow, approve, carve out) when a measured number exceeds a
-  ceiling. Thresholds arrive only through `ctx.refactor_radius`, resolved by the controller
-  from `quality_gate.py --print-config`. Every evaluation emits a `refactor-radius` event
-  carrying both the measured numbers and the thresholds compared, including the no-fire and
-  not-measured cases, and it renders into `decisions-log.md`. Honest limits: the numbers are
-  a planner-declared proxy rather than a measured diff, so this cannot catch a blowup
-  discovered mid-implementation; the check runs once, on the first plan, and a post-OBJECT
-  replan is not re-evaluated; and a controller that does not thread `ctx.refactor_radius`
-  records `NOT_CONFIGURED` and never halts.
+- **The wave now halts a slice at PLAN time when its plan declares a rewrite of existing code
+  larger than the run's configured ceiling — the run's one new LEVER.**
+  `slice-wave.workflow.js` gains an optional `refactor_radius` block on `PLAN_RESULT` that the
+  slice planner fills with declared numbers (`rewrite_ratio`, `touched_existing_files`,
+  `rewritten_lines`, and a `basis` string saying how it counted), a pure
+  `refactorRadiusStatus()` predicate that judges them in JS — mirroring `qualityStatus()`, with
+  every comparison behind an explicit null guard because `undefined >= n` is false and
+  `null >= 0` is true — and a `refactor-scope` escalation offering three trade-offs (narrow,
+  approve, carve out) when a measured number exceeds its ceiling. The verdict is reached
+  PER DIMENSION: a ceiling that is usable for one number and unusable for another is reported
+  as exactly that, and never as a blanket claim that every declared number is within bounds.
+  Thresholds arrive only through `ctx.refactor_radius`, resolved by the controller from
+  `quality_gate.py --print-config`, the one door to the effective configuration; a controller
+  that does not thread it records `NOT_CONFIGURED` and never halts. Every evaluation emits a
+  `refactor-radius` event carrying the measured numbers, the thresholds compared and the
+  planner's basis — including the no-fire and not-measured cases — and it renders into
+  `decisions-log.md`. Only a truthy human answer disarms the halt, and a suppression is claimed
+  only where an answer actually waived a real breach.
 
 ### Changed
-- **The autonomy contract now names six judgment triggers instead of five.**
-  `skills/escalation-gate/SKILL.md` adds `refactor-scope` as the sixth SURFACE trigger and
-  describes it accurately as the only one raised by the workflow's own arithmetic, at plan
-  time, on a measured breach; the same file keeps its separate, unchanged point that the
-  council's `over_scope` flag is a record that decides nothing and is still not a trigger.
-  `agents/slice-planner.md` gains the doctrine for declaring `rewrite_ratio`,
-  `touched_existing_files`, `rewritten_lines` and `basis` — numbers only, never a verdict, and
-  omitted rather than guessed as a zero — and `commands/spec-loop.md` applies the six-trigger
-  test and states how a `refactor-scope` answer is threaded back. Honest limits: this change is
-  prose and its new tests are substring assertions over that prose, so they prove the doctrine
-  is present and its five-trigger predecessor is gone, and nothing about whether an agent obeys
-  it; no runtime behaviour changes here, and the five-trigger sentences in `README.md` and
-  `references/risk-tiers.md` are not touched by this change.
+- **The autonomy contract now names six judgment triggers instead of five, everywhere it is
+  stated.** `skills/escalation-gate/SKILL.md` adds `refactor-scope` as the sixth SURFACE trigger
+  and describes it accurately as the only one raised by the workflow's own arithmetic, at plan
+  time, on a measured breach; `agents/slice-planner.md` gains the doctrine for declaring the
+  radius numbers — numbers only, never a verdict, and omitted rather than guessed as a zero;
+  `commands/spec-loop.md` applies the six-trigger test and states how a `refactor-scope` answer
+  is threaded back; and `README.md` and `references/risk-tiers.md` are reconciled to six, with
+  `risk-tiers.md` stating that `refactor-scope` is NOT in the tier funnel because it fires at
+  plan time against a run-level ceiling that no tier setting moves. The same files keep their
+  separate, unchanged point that the council's `over_scope` flag is a RECORD that decides
+  nothing and is still not a trigger. `README.md`'s counted component inventory is re-verified
+  against the tree: this run added test-support and harness modules and changed no agent,
+  command, skill or runtime-script count.
+
 ### Fixed
-- **A council objection resolved by a replan no longer passes on the revision's status
-  alone.** `slice-wave.workflow.js` used to accept a post-`OBJECT` revision whenever it came
-  back `PLANNED`, so one silent retry absorbed the objection: nobody re-read the plan the
-  council had rejected and the human never saw it, while the doctrine described the mechanism
-  as blocking. `acceptRevisedPlan()` now sends the revision back to one `plan-critic` seat
-  (`critic:replan`), records a `replan-recheck` event carrying the verdict and the reason, and
-  escalates `council-objection` on a second objection, a fresh safety flag, or an unreadable
-  re-critique. Honest limits: the re-check is a SINGLE seat, not the original panel, so a
-  tier-3 objection raised by `guardian` or `skeptic` is re-checked by `plan-critic` alone; it
-  runs once, because `state.replanned` already vetoes a second replan; and the plan-time
-  refactor-radius ceiling is deliberately NOT re-measured on the revised plan.
+- **A council objection resolved by a replan no longer passes on the revision's status alone.**
+  `slice-wave.workflow.js` used to accept a post-`OBJECT` revision whenever it came back
+  `PLANNED`, so one silent retry absorbed the objection: nobody re-read the plan the council had
+  rejected and the human never saw it, while the doctrine described the mechanism as blocking.
+  `acceptRevisedPlan()` now sends the revision back to one `plan-critic` seat (`critic:replan`),
+  records a `replan-recheck` event carrying the verdict and the reason, and escalates
+  `council-objection` on a second objection, a fresh safety flag, or an unreadable re-critique.
 - **The last three unguarded optional agent-return reads in the wave are guarded.**
   `PLAN_RESULT.required` is `['status']` only and `FIX_RESULT.commits` is optional, so
-  `fix.commits.base` (which threw during wave 1 of run 20260828 and was mislabelled a
-  `budget-exhausted` escalation, losing the wave), `plan.escalation.trigger` and the
+  `fix.commits.base` (which threw during wave 1 of this run, was mislabelled a
+  `budget-exhausted` escalation, and lost the wave), `plan.escalation.trigger` and the
   `plan.split` pass-through were each one absent object away from aborting a whole wave.
   `fixCommits()` falls back to the slice's own shas, `planEscalation()` substitutes a usable
   record so the slice pauses instead of crashing, and `usableSplit()` escalates a childless
   SPLIT at the cause instead of writing a sidecar the validator rejects a stage later.
   `slice_wave_contract_base.py`'s docstring, which recorded two of these as deliberately
-  unfixed, is corrected. Honest limit: the trigger guard is a TYPE check, so an unrecognized
-  trigger string still fails `validate_escalation` downstream exactly as it does today, and
-  the catch-all that mislabels a `TypeError` as `budget-exhausted` is unchanged.
+  unfixed, is corrected.
+
+### Honest limits of this run
+- The radius numbers are the PLANNER'S PRE-EXECUTION DECLARATION — a proxy, not a measured
+  diff. A rewrite that blows up mid-implementation is invisible to this gate. No git
+  blast-radius measurement script and no second, post-implementation checkpoint were built;
+  both were deferred by human decision.
+- The gate ships DEFAULT ON, so every installation gains this halt on its next run after
+  upgrade rather than opting into it.
+- A plan revised after a council `OBJECT` is NOT re-radius-evaluated. Known gap, left
+  deliberately.
+- The replan re-check is a SINGLE `plan-critic` seat, not the original panel: a tier-3
+  objection raised by `guardian` or `skeptic` is re-checked by a different member, and the
+  re-check prompt does not carry the objection text. It also runs once, because
+  `state.replanned` already vetoes a second replan.
+- Teammate blast radius — other-author churn, competing branches — was deliberately not built.
+- The catch-all that mislabels a `TypeError` as `budget-exhausted` is unchanged, and the
+  `refactor-scope` trigger guard is a TYPE check, so an unrecognized trigger string still fails
+  `validate_escalation` downstream exactly as it does today.
+- The doctrine changes are prose, and their tests are substring assertions over that prose:
+  they prove the doctrine is present and its five-trigger predecessor is gone, and nothing
+  about whether an agent obeys it.
 
 ## [2.2.2] - 2026-08-28
 ### Added
 - **The quality gate counts branch keywords in code, not in prose.** `quality_gate.py` now
   masks the content of string literals and comments before it scans a source, so a branch word
diff --git a/plugins/spec-loop/README.md b/plugins/spec-loop/README.md
index fec3e46..39e09a9 100644
--- a/plugins/spec-loop/README.md
+++ b/plugins/spec-loop/README.md
@@ -94,17 +94,20 @@ architecture on the same model. Second, wall clock ≠ compute: the loop is
 built to run unattended, and question rounds + the publish prompt fire a
 desktop alert so a finished run is never silently parked overnight.
 
 ## Escalations
 
-The loop surfaces a question only on the escalation-gate's five triggers:
+The loop surfaces a question only on the escalation-gate's six triggers:
 genuine ambiguity, a material assumption, an unfixable review block, a
-council objection, or an unfixable quality-gate block — after checking prior
-runs for a precedent that already answers it. Everything else proceeds and is
-logged as a decision event with rationale and reversibility. All open
-escalations arrive as ONE question round per wave boundary, recommended
-default first.
+council objection, an unfixable quality-gate block, or a plan-time
+refactor-scope breach — after checking prior runs for a precedent that
+already answers it. The last is the only one the wave raises from its own
+arithmetic: the slice planner declares how much existing code its plan
+rewrites, and the workflow compares those numbers to the configured ceiling
+before a single line is implemented. Everything else proceeds and is logged
+as a decision event with rationale and reversibility. All open escalations
+arrive as ONE question round per wave boundary, recommended default first.
 
 ## Quality gate
 
 `scripts/quality_gate.py` measures the slice diff (cyclomatic/cognitive
 complexity, method/class length, parameters, nesting, CRAP with coverage) —
@@ -150,11 +153,13 @@ sidecar closed rather than reading as clean.
 - **Skills (5)**: escalation-gate, using-spec-loop, test-driven-development,
   systematic-debugging, verification-before-completion.
 - **Scripts (11 runtime + tests)**: dag, worktrees, run_state, review_package,
   quality_gate, knowledge_graph, run_metrics, pr_resolver, spec_loop_guard,
   dashboard_server, dashboard_launcher (+ dashboard_assets, and the
-  `slice_wave_contract_base` test-support module).
+  `slice_wave_contract_base` and `slice_wave_contract_radius_driver`
+  test-support modules, which back three Node harness modules:
+  `slice_wave_behaviour`, `slice_wave_radius` and `slice_wave_replan`).
 
 ## Migrating from v1
 
 Read `references/migration-from-v1.md`. Short version: theology unchanged,
 internals rebuilt; config namespace moved (first run offers import); v1 run
diff --git a/plugins/spec-loop/references/risk-tiers.md b/plugins/spec-loop/references/risk-tiers.md
index a8d90be..a58ee9f 100644
--- a/plugins/spec-loop/references/risk-tiers.md
+++ b/plugins/spec-loop/references/risk-tiers.md
@@ -81,16 +81,19 @@ overlay). Any match promotes `review_tier` to 3 and records a `decision` event w
   only later stages escalate with the tier. A tier-3 surface a human wants critiqued belongs in
   the tier assignment or behind `--thorough`.
 
 ## Escalation-relevant consequences
 
-Everything the tier decides funnels into exactly two of `escalation-gate`'s five triggers:
+Everything the tier decides funnels into exactly two of `escalation-gate`'s six triggers:
 `review-block` (blocking findings survive the fix loop, or verification cannot pass) and
-`quality-gate-block` (gate violations survive it). The `budget-exhausted` record the per-slice
-agent cap emits is mechanical, not a judgment — and the caps in the table above are only one of
-its two sources; the other is the loop's per-stage token floor, which no tier setting changes.
-A spent loop bound is neither: it escalates as whatever actually stalled (`run-state-v2.md`).
+`quality-gate-block` (gate violations survive it). The sixth trigger, `refactor-scope` is
+not one of them: it fires at plan time against a run-level ceiling, and no tier setting moves it —
+a Tier 1 docs slice and a Tier 3 auth slice are judged against the same declared-rewrite numbers.
+The `budget-exhausted` record the per-slice agent cap emits is mechanical, not a judgment — and
+the caps in the table above are only one of its two sources; the other is the loop's per-stage
+token floor, which no tier setting changes. A spent loop bound is neither: it escalates as
+whatever actually stalled (`run-state-v2.md`).
 
 An over-scope record (`critique.over_scope`) is **not** in that funnel. It is record-only:
 it is carried into the `council-verdict` event and the sidecar, counted null-honestly by
 `run_metrics.py`, and read by a human — it raises no trigger, blocks nothing, and is never
 a finding. Work the council judged out of scope and asked not to be built is a
diff --git a/plugins/spec-loop/scripts/test_doctrine_run_docs.py b/plugins/spec-loop/scripts/test_doctrine_run_docs.py
new file mode 100644
index 0000000..1a7cf36
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_doctrine_run_docs.py
@@ -0,0 +1,145 @@
+#!/usr/bin/env python3
+"""Contract checks for the two run-level doc surfaces s6 reconciled.
+
+`skills/escalation-gate/SKILL.md` is the single home of the judgment-trigger
+doctrine; README.md and references/risk-tiers.md only REFER to its count, and
+an uncounted reference is exactly the kind of prose that drifts silently. This
+module pins both references at six, pins that their five-trigger predecessors
+are gone, and pins README's counted component inventory against a real count of
+the tree rather than against a remembered number.
+
+Honest limit: these are substring assertions over collapsed prose plus a
+directory count. They prove a sentence is present and its superseded form is
+absent; they prove nothing about whether a reader or an agent acts on it, and
+they are not a behavioural test of any gate. The component test counts files on
+disk, so it fails on a real inventory change - which is the point.
+
+A separate module rather than a class in test_doctrine_refactor_scope.py:
+that module is owned by the doctrine slice and this one by the docs close-out;
+slice_wave_contract_base.py is at its 300-line ceiling and must not grow.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_doctrine_run_docs.py'
+"""
+
+import re
+import sys
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+PLUGIN_ROOT = Path(__file__).resolve().parents[1]
+README_MD = PLUGIN_ROOT / "README.md"
+RISK_TIERS_MD = PLUGIN_ROOT / "references" / "risk-tiers.md"
+
+
+def prose(path):
+    """One file's text with every whitespace run collapsed to a space. (PURE)"""
+    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
+
+
+# ---- README: the escalations section ----
+
+README_SIX = "the escalation-gate's six triggers"
+README_SIXTH = "or a plan-time refactor-scope breach"
+README_ARITHMETIC = "the only one the wave raises from its own arithmetic"
+README_STALE_FIVE = "the escalation-gate's five triggers"
+
+
+class TestTheReadmeNamesSixJudgmentTriggers(unittest.TestCase):
+    """README is the first surface a new user reads; a stale count here
+    understates what the loop will stop for, which is the failure direction
+    that surprises a human mid-run."""
+
+    def setUp(self):
+        self.text = prose(README_MD)
+
+    def test_the_readme_counts_six_judgment_triggers(self):
+        self.assertIn(README_SIX, self.text)
+
+    def test_the_five_trigger_predecessor_sentence_is_gone(self):
+        self.assertNotIn(README_STALE_FIVE, self.text)
+
+    def test_the_readme_names_the_sixth_trigger_and_who_raises_it(self):
+        self.assertIn(README_SIXTH, self.text)
+        self.assertIn(README_ARITHMETIC, self.text)
+
+
+# ---- risk-tiers: which of the six the tier actually funnels into ----
+
+TIERS_SIX = "exactly two of `escalation-gate`'s six triggers"
+TIERS_NOT_TIERED = "`refactor-scope` is not one of them"
+TIERS_PLAN_TIME = "it fires at plan time against a run-level ceiling, and no tier setting moves it"
+TIERS_STALE_FIVE = "exactly two of `escalation-gate`'s five triggers"
+TIERS_OVER_SCOPE_KEPT = "An over-scope record (`critique.over_scope`) is **not** in that funnel."
+
+
+class TestRiskTiersSeparatesTierTriggersFromThePlanTimeOne(unittest.TestCase):
+    """risk-tiers.md is the single home of tier -> review shape. Its funnel
+    sentence is a claim about which triggers a tier CAN cause; adding a
+    trigger the tier does not affect must widen the count without widening
+    the funnel, or the file over-promises what a tier buys."""
+
+    def setUp(self):
+        self.text = prose(RISK_TIERS_MD)
+
+    def test_the_funnel_sentence_counts_six_triggers(self):
+        self.assertIn(TIERS_SIX, self.text)
+        self.assertNotIn(TIERS_STALE_FIVE, self.text)
+
+    def test_refactor_scope_is_named_as_outside_the_tier_funnel(self):
+        self.assertIn(TIERS_NOT_TIERED, self.text)
+        self.assertIn(TIERS_PLAN_TIME, self.text)
+
+    def test_the_over_scope_record_is_still_called_record_only(self):
+        self.assertIn(TIERS_OVER_SCOPE_KEPT, self.text)
+
+
+# ---- README: the counted component inventory ----
+
+INVENTORY_COUNTS = (
+    ("commands", "**Commands (%d)**"),
+    ("agents", "**Agents (%d)**"),
+    ("skills", "**Skills (%d)**"),
+)
+RADIUS_DRIVER = "`slice_wave_contract_radius_driver`"
+THREE_HARNESS_MODULES = "three Node harness modules"
+
+
+def _counted(kind):
+    """How many components of one kind actually exist on disk. (PURE)"""
+    if kind == "commands":
+        return len(list((PLUGIN_ROOT / "commands").glob("*.md")))
+    if kind == "agents":
+        return len(list((PLUGIN_ROOT / "agents").glob("*.md")))
+    return len([p for p in (PLUGIN_ROOT / "skills").iterdir() if p.is_dir()])
+
+
+class TestTheComponentInventoryIsCountedNotRemembered(unittest.TestCase):
+    """The README inventory is the only place a reader learns how big the
+    plugin is. It drifted before because a contributor trusted the printed
+    number instead of the tree, so this test compares it to the tree."""
+
+    def setUp(self):
+        self.text = prose(README_MD)
+
+    def test_each_printed_count_equals_the_number_of_files_on_disk(self):
+        for kind, template in INVENTORY_COUNTS:
+            with self.subTest(kind=kind):
+                self.assertIn(template % _counted(kind), self.text)
+
+    def test_the_runtime_script_count_matches_the_non_test_modules(self):
+        runtime = [p for p in (PLUGIN_ROOT / "scripts").glob("*.py")
+                   if not p.name.startswith("test_")
+                   and not p.name.startswith("slice_wave_contract")]
+        self.assertIn("**Scripts (%d runtime + tests)**" % len(runtime), self.text)
+
+    def test_the_inventory_names_this_runs_new_test_support_modules(self):
+        self.assertIn(RADIUS_DRIVER, self.text)
+        self.assertIn(THREE_HARNESS_MODULES, self.text)
+
+
+if __name__ == "__main__":  # pragma: no cover
+    unittest.main()
