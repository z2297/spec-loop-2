# Review package: 0d2f84a..6ae96ee  (context: -U5)

## Commits
6ae96ee fix(ado): count ado_client in the README script inventory

## Files changed
 plugins/spec-loop/README.md | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/README.md": [
[
168,
168
],
[
170,
171
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/README.md b/plugins/spec-loop/README.md
index 7a35385..6bd376c 100644
--- a/plugins/spec-loop/README.md
+++ b/plugins/spec-loop/README.md
@@ -163,14 +163,14 @@ sidecar closed rather than reading as clean.
 - **Agents (13)**: slice-planner, plan-critic, guardian, skeptic,
   implementer, pr-reviewer, finding-verifier, re-reviewer, simplifier,
   verifier, runbook-writer, peer-reviewer, slice-worker-fallback.
 - **Skills (5)**: escalation-gate, using-spec-loop, test-driven-development,
   systematic-debugging, verification-before-completion.
-- **Scripts (14 runtime + tests)**: dag, worktrees, run_state, redispatch, review_package,
+- **Scripts (15 runtime + tests)**: dag, worktrees, run_state, redispatch, review_package,
   quality_gate, knowledge_graph, run_metrics, pr_resolver, jira_client, jira_intake,
-  spec_loop_guard, dashboard_server, dashboard_launcher (+ dashboard_assets, and the
-  `slice_wave_contract_base` and `slice_wave_contract_radius_driver`
+  ado_client, spec_loop_guard, dashboard_server, dashboard_launcher (+ dashboard_assets,
+  and the `slice_wave_contract_base` and `slice_wave_contract_radius_driver`
   test-support modules, which back six Node harness modules:
   `slice_wave_accepted`, `slice_wave_behaviour`, `slice_wave_radius`,
   `slice_wave_radius_partial`, `slice_wave_reentry` and `slice_wave_replan`).
 
 ## Migrating from v1
