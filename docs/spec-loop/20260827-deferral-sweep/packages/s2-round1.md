# Review package: 299f0dbd1f700f8f3b3991ea7d601df797dd3749..2bb9250  (context: -U5)

## Commits
2bb9250 docs: match the inline twin's step 3 to runTask's unconditional ambiguity trigger
c017cdf docs: stop the escalation gate claiming the lost-slice record describes its own gap
2d15f4d docs: attribute the crash record's three options to the record that has them

## Files changed
 CHANGELOG.md                                      |  9 ++++++--
 plugins/spec-loop/agents/slice-worker-fallback.md |  9 +++++---
 plugins/spec-loop/skills/escalation-gate/SKILL.md | 27 ++++++++++++++---------
 3 files changed, 29 insertions(+), 16 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
32,
38
]
],
"plugins/spec-loop/agents/slice-worker-fallback.md": [
[
98,
103
]
],
"plugins/spec-loop/skills/escalation-gate/SKILL.md": [
[
74,
89
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 84b352f..42d57e4 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -27,12 +27,17 @@ All notable changes to the spec-loop plugin are documented here. The format is
   agent-contract bug and it may equally be a host- or agent-layer resource failure (a rejected agent
   call on a hard token or rate limit, say) — the exception text is the evidence, not the label. The
   lost-slice record at :919 follows the same rule in the same words: neither guard *raised* its
   escalation record, "and that is all a null result proves, not that no guard check ran" — and it no
   longer denies a resource cause it cannot rule out. It is not a judgment trigger and it is not
-  answerable by re-dispatching an agent: its three options (retry the slice, skip it, stop the run)
-  are controller actions, and each option's detail names the controller as what applies it. Added to
+  answerable by re-dispatching an agent. The two records offer different things. The crash record
+  from `runSliceError` passes three explicit options — retry the slice, skip it, stop the run —
+  and each option's detail names the controller as what applies it, because the loop itself
+  implements none of the three. The lost-slice record passes an empty options array, so `esc()`
+  substitutes a single generic option labelled "Proceed with the recommended default" whose detail
+  repeats the context; its retry ask lives in its question, "Re-run the wave to retry this slice?",
+  not in an option. Either way the controller is what acts. Added to
   `ESCALATION_TRIGGERS` in `run_state.py`, `run_metrics.py` and `dashboard_server.py`, to the record
   shape in `references/run-state-v2.md`, and to the enumerations in
   `skills/escalation-gate/SKILL.md` and `agents/slice-worker-fallback.md` — the last of these being
   the behavioral spec for the inline-mode twin, which must classify identically.
 
diff --git a/plugins/spec-loop/agents/slice-worker-fallback.md b/plugins/spec-loop/agents/slice-worker-fallback.md
index d8ea1a0..564e1e9 100644
--- a/plugins/spec-loop/agents/slice-worker-fallback.md
+++ b/plugins/spec-loop/agents/slice-worker-fallback.md
@@ -93,13 +93,16 @@ of each prompt).
 order, each at the model tier its task's lane maps to. Give each the worktree path, its task
 brief, the plan and conventions paths, `shared_constraints`, and the test/build commands. No
 per-task review below Tier 3; at Tier 3 run the per-task review your tier table specifies.
 Handle statuses: `NEEDS_CONTEXT` → answer from the plan or codebase and re-dispatch once
 (that is the task's one retry); a genuine `BLOCKED`, or a second failure on the same task →
-escalate and return `ESCALATED`. Pick the trigger the way the workflow does: a dispatch that
-came back with **no result** is `ambiguity` (see step 4), never `internal-error`; a `BLOCKED`
-that states a real blocker is `material-assumption` or `review-block` as fits. Roll up
+escalate and return `ESCALATED`. Pick the trigger the way the workflow does: an exhausted task
+retry is `ambiguity`, unconditionally, whatever the last status was. A dispatch that came back
+with no result, a second `NEEDS_CONTEXT`, and a `BLOCKED` naming a real blocker all collapse
+to the same `ambiguity` record, and none of them is `internal-error` — the trigger rules are
+under `## Escalations` below. Put the real blocker text, or the questions, in that record's
+context, since `ambiguity` is the trigger a human can actually answer. Roll up
 every `concerns[]` and `deviations[]` — the reviewer needs them.
 
 **4 — Review ∥ quality gate (one message).** Build the review package once with the handed-in
 builder over `<slice-base-sha>..HEAD`, then in a single message: dispatch ONE `pr-reviewer` in
 `slice` mode (package path, plan path, tier + blocking bar, `conventions.md`, the rolled-up
diff --git a/plugins/spec-loop/skills/escalation-gate/SKILL.md b/plugins/spec-loop/skills/escalation-gate/SKILL.md
index c3773db..602dd4d 100644
--- a/plugins/spec-loop/skills/escalation-gate/SKILL.md
+++ b/plugins/spec-loop/skills/escalation-gate/SKILL.md
@@ -69,21 +69,26 @@ Do not act. Return an `EscalationRecord` and let the controller batch it:
 When uncertain whether something is "material": if a reasonable reviewer could reject the slice
 over it, it is material → surface it.
 
 The enum lives in `slice-wave.workflow.js` (`ESCALATION.trigger`). Three things that are
 deliberately NOT judgment triggers, and must never be turned into one: `budget-exhausted` (the
-workflow's guard emits it when a structural cap is hit — agent cap, stage token floor; it asks for a
-resource, not a decision), `internal-error` (an unhandled exception aborted a slice, or a slice
-returned no result at all; the exception record carries the real exception text together with the
-last stage/role dispatched before the failure, which is the most recent dispatch rather than a
-per-throw stage — the lost-slice record carries neither, having nothing to carry, and says
-so. This trigger reports a machine failure and asks the controller to retry, skip, or stop
-the run, and no agent prompt can apply such an answer, so the trigger is never answerable by
-re-dispatching an agent), and the council's **over-scope flag** (`critique.over_scope.flag`).
-The flag is a record: it is carried into the `council-verdict` payload and the slice sidecar with
-its reason, and it raises no escalation, changes no verdict, suppresses no split, and blocks
-nothing. There are exactly five JUDGMENT triggers; an over-scope flag is not a sixth.
+workflow's guard emits it when a structural cap is hit — agent cap, stage token floor; it asks for
+a resource, not a decision), `internal-error` (an unhandled exception aborted a slice, or a slice
+returned no result at all — one trigger, two records that carry different evidence. The exception
+record from `runSliceError` carries the real exception text together with the last stage/role
+dispatched before the failure, which is the most recent dispatch rather than a per-throw stage,
+and its context says exactly that about itself. The lost-slice record carries neither, having
+nothing to carry, and its context does not announce the gap: it states only that a null result
+proves nothing about which guard ran. Read that absence as absence, not as a claim about the
+cause. The trigger reports a machine failure and is never answerable by re-dispatching an agent,
+so only a human or the controller resolves it — and only the exception record spells the choice
+out as three options, retry the slice, skip it, or stop the run; the lost-slice record asks one
+question, whether to re-run the wave, and carries a single generic recommended-default option),
+and the council's **over-scope flag** (`critique.over_scope.flag`). The flag is a record: it is
+carried into the `council-verdict` payload and the slice sidecar with its reason, and it raises no
+escalation, changes no verdict, suppresses no split, and blocks nothing. There are exactly five
+JUDGMENT triggers; an over-scope flag is not a sixth.
 
 ### Precedent check (before returning any SURFACE escalation)
 
 Prior runs' human answers are settled decisions — check them before asking a question the human
 may have already answered. Search prior runs (excluding this one): answered escalation records
