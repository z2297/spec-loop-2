# Escalations

Rendered from EscalationRecords; answers are written back into the matching entry.

## [run] Does this run build the comment-WRITE lane, or the read lane only?   (status: ANSWERED)
<!-- escalation-id: run:ambiguity -->
<!-- escalation-identity: 39182d2abd43aadd -->
- Trigger: ambiguity
- Opened: 2026-09-14T13:49:04Z
- Context: The Jira connector this is twinning has a bounded comment writer, so full equivalence includes it. But every blocking finding from both council risk lanes lands on the write lane, and one of them - whether the dedupe marker survives the write/read api-version round trip (POST 7.0-preview.3, read back 7.1-preview.4, with ADO free to normalize a body whose format the Add call cannot declare) - cann…
- The decision: Should this run implement the bounded comment-posting lane (slice a2), or stop at preview-only and defer the write lane to a follow-on run?
- Options:
  1. Read + preview only this run — (RECOMMENDED DEFAULT) Slices a1, a3, a4, a5. The command resolves, refines, writes the artifact and PREVIEWS the comment bodies, but has no --post and no POST transport at all. Fully verifiable in this repo; no irreversible external write exists to get wrong. The write lane becomes a separate run with its own council pa…
  2. Full connector including the write lane — All five slices - literal equivalence with the Jira connector. Accepts a Tier-3 irreversible external write whose marker round trip needs one live ADO work item to verify, and whose blast radius if wrong is one duplicate comment on the first armed post ever.
- If unanswered: Build read + preview only (the safer subset); the write lane is additive later.
- Answer: Full connector including the bounded comment-write lane.
- Answered-at: 2026-09-14T14:01:09Z

## [run] Azure DevOps Services only, or also Server / on-prem?   (status: ANSWERED)
<!-- escalation-id: run:material-assumption -->
<!-- escalation-identity: e44fae91cd611a5d -->
- Trigger: material-assumption
- Opened: 2026-09-14T13:49:04Z
- Context: request.md scopes the connector to Azure DevOps Services (dev.azure.com plus the legacy *.visualstudio.com org form), mirroring the Jira connector's Cloud-only stance. The premise lane flagged this as the assumption most likely to be wrong, since Azure DevOps Server is common in regulated enterprises precisely because it is on-prem. It is not a small addition: a Server host is an arbitrary intern…
- The decision: Should the connector support Azure DevOps Server / on-prem hosts, or Services only?
- Options:
  1. Azure DevOps Services only — (RECOMMENDED DEFAULT) Host allow-list stays a fixed regex over dev.azure.com and *.visualstudio.com, exactly as the Jira connector allow-lists *.atlassian.net / *.jira.com with deliberately no opt-in extra-hosts variable. Keeps the strongest transport property. A Server user gets a clear, actionable refusal rather than …
  2. Also support Server / on-prem — Requires an operator-supplied host, which weakens the allow-list from a fixed regex to an opt-in trust decision, plus /tfs/{collection} path handling and per-version api-version negotiation. Materially larger, and it reopens the exact hole the allow-list closes.
- If unanswered: Services only.
- Answer: Azure DevOps Services only.
- Answered-at: 2026-09-14T14:01:09Z

## [run] Is a live ADO work item available to discharge the one unverifiable claim?   (status: ANSWERED)
<!-- escalation-id: run:material-assumption-2 -->
<!-- escalation-identity: d0ed795775b0e394 -->
- Trigger: material-assumption
- Opened: 2026-09-14T13:49:04Z
- Context: Only relevant if the write lane is in scope. The dedupe gate reduces to one claim: the marker we POST comes back findable in the comment list. Construction reduces the risk (extract-by-regex into a set rather than substring matching, a two-tier match, the marker on line 1, and an escaped body so the marker never abuts an escapable character) but cannot eliminate it, because no faked transport can…
- The decision: Do you have an Azure DevOps organization and a disposable work item that can be used for that one live round trip, and are you willing to run it?
- Options:
  1. Yes - I can run the live check — (RECOMMENDED DEFAULT) The run implements the write lane and the arming prose is gated on recorded live evidence. You run the one-item procedure and report the result; I record it in the run.
  2. No live org available — The write lane, if built, ships with its round-trip assumption explicitly UNVERIFIED and said so in the command prose - no claim of round-trip fidelity. This is a strong argument for the preview-only option in the scope question.
  3. Not applicable - preview only — Choose this if you picked read + preview only above; there is no write lane to verify.
- If unanswered: Assume no live org; prefer preview-only and never claim verified round-trip fidelity.
- Answer: Yes - a live ADO organization and a disposable work item are available, and the human will run the one round-trip check.
- Answered-at: 2026-09-14T14:01:09Z

## [a1] 12 quality-gate violation(s) unresolved after 2 fix rounds   (status: ANSWERED)
<!-- escalation-id: a1:quality-gate-block -->
<!-- escalation-identity: f10a757ca422569e -->
- Trigger: quality-gate-block
- Opened: 2026-09-14T15:55:00Z
- Context: The full six-segment suite is GREEN at this head. The only blocker is the scripted quality gate: 12 findings. Two are whole-file class_lines (ado_client.py 865, test_ado_client.py 887 against a 300 threshold, function=null). One is parameter_count 6 on redirect_request, whose signature is dictated by urllib.request.HTTPRedirectHandler.redirect_request and whose `return None` body IS the redirect …
- The decision: Accept the residual gate findings as measurement debt, provide fix guidance, or drop the slice?
- Options:
  1. Accept the whole-file class_lines findings as debt — (RECOMMENDED DEFAULT) Cite the repo's standing human ruling that class_lines is computed over the WHOLE file and is a mis-measurement, not class size.
  2. Provide fix orders — Reshape the function-level findings the slice actually introduced.
  3. Drop the slice — Abandon the branch.
- If unanswered: pause this slice; continue all independent slices
- Answer: PARTIAL ACCEPTANCE PLUS FIX ORDERS. Accepted as measurement debt (3): the two whole-file class_lines findings (ado_client.py 865, test_ado_client.py 887, function=null) under this repo's standing human ruling from run 20260825-scope-ceiling that class_lines reports file length rather than class size; and parameter_count 6 on redirect_request, because urllib.request.HTTPRedirectHandler.redirect_re…
- Answered-at: 2026-09-14T16:15:54Z

## [a3] 3 quality-gate violation(s) unresolved after 2 fix rounds   (status: ANSWERED)
<!-- escalation-id: a3:quality-gate-block -->
<!-- escalation-identity: b6003c5be3195825 -->
- Trigger: quality-gate-block
- Opened: 2026-09-14T15:55:00Z
- Context: The fix loop closed 27 of 30 findings across two rounds; the fixer returned BLOCKED because the three remaining findings are all whole-file class_lines (ado_intake.py 754, test_ado_intake.py 567, and the PRE-EXISTING scripts/measure_coverage.py at 541, all against a 300 threshold with function=null) and cannot be closed by any remedy fix mode sanctions. The slice never reached its verify stage, s…
- The decision: Accept the residual gate findings as measurement debt, provide fix guidance, or drop the slice?
- Options:
  1. Accept the whole-file class_lines findings as debt — (RECOMMENDED DEFAULT) Cite the repo's standing human ruling that class_lines is computed over the WHOLE file and is a mis-measurement, not class size.
  2. Provide fix orders — Reshape the function-level findings the slice actually introduced.
  3. Drop the slice — Abandon the branch.
- If unanswered: pause this slice; continue all independent slices
- Answer: ACCEPTED AS MEASUREMENT DEBT, citing this repo's standing human ruling (run 20260825-scope-ceiling, decision 'A whole-file class_lines block on a file that already violated is pre-existing debt, not the slice's work'): class_lines is computed over the WHOLE file and emitted whenever any changed range touches it, so it reports file length, not class size - verified elsewhere as a false positive ag…
- Answered-at: 2026-09-14T16:15:35Z

## [a1] verification failed   (status: ANSWERED)
<!-- escalation-id: a1:quality-gate-block:2 -->
<!-- escalation-identity: 55c4a20fe00d5ab7 -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All six suite segments passed: (1) marketplace validation OK, (2) scripts tests 126 passed in 32.676s, (3) plugins/spec-loop/scripts tests 1945 passed in 18.764s, (4) coverage 2071 tests passed with PASS on all per-file and total floors, (5) dashboard assets 48 tests passed, (6) slice wave tests 136 tests passed; quality: FAIL (summary_pass=false, 9 open, 3 accepted — Quality gate produced…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Accept the listed violations as pre-existing debt — (RECOMMENDED DEFAULT) The CONTROLLER must act on this at the next dispatch: record the acceptance (redispatch.py accept-violations, then redispatch.py args) and re-dispatch with slice.entry {stage: "verify", head}.
  2. Provide fix orders — The CONTROLLER must act on this at the next dispatch: re-dispatch with slice.entry {stage: "fix", head, orders: [...]} so the FIXER receives them, or — for a red suite — answer this id and re-dispatch with {stage: "verify", head} so the debug-fixer reads it.
  3. Drop the slice — The CONTROLLER must act on this at the next dispatch: exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.
- If unanswered: pause this slice; continue all independent slices
- Answer: ACCEPTED AS HEURISTIC FALSE POSITIVES, on first-hand controller evidence, with one honest caveat. I read all nine flagged functions in the a1 worktree. Five are unambiguous artifacts: test_headings_get_the_heading_prefix and test_entities_are_unescaped are each a SINGLE assertEqual split across two lines (real nesting 1, reported 5), and the two exit-code tests are a single 'with mock.patch(...),…
- Answered-at: 2026-09-14T16:26:46Z

## [a2] verification failed   (status: ANSWERED)
<!-- escalation-id: a2:quality-gate-block -->
<!-- escalation-identity: 2e458f2037a9d35b -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All six test segments passed. Segment 1: marketplace validation OK. Segment 2: 126 Python unit tests in scripts/ passed. Segment 3: 2113 Python tests in plugins/spec-loop/scripts passed. Segment 4: 2239 tests with coverage floors met (97.3% total, all per-file and total floors passed). Segment 5: 48 Node tests for dashboard assets passed. Segment 6: 136 Node tests for slice wave behavior, …
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Accept the listed violations as pre-existing debt — (RECOMMENDED DEFAULT) The CONTROLLER must act on this at the next dispatch: record the acceptance (redispatch.py accept-violations, then redispatch.py args) and re-dispatch with slice.entry {stage: "verify", head}.
  2. Provide fix orders — The CONTROLLER must act on this at the next dispatch: re-dispatch with slice.entry {stage: "fix", head, orders: [...]} so the FIXER receives them, or — for a red suite — answer this id and re-dispatch with {stage: "verify", head} so the debug-fixer reads it.
  3. Drop the slice — The CONTROLLER must act on this at the next dispatch: exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.
- If unanswered: pause this slice; continue all independent slices
- Answer: ACCEPTED plus FIX ORDERS. The single open violation is class_lines 543>300 on scripts/measure_coverage.py with function=null - a PRE-EXISTING whole-file count on a file a2 only touched to register ado_client.py in the coverage gate, and the same fingerprint was already accepted for slice a3 this run under the standing human ruling from run 20260825-scope-ceiling that class_lines reports file leng…
- Answered-at: 2026-09-14T18:06:04Z

## [a4] council objects: The plan's Task 3 Verification asserts all six gates exit 0   (status: ANSWERED)
<!-- escalation-id: a4:council-objection -->
<!-- escalation-identity: c8690f15ce017e33 -->
- Trigger: council-objection
- Opened: (not recorded)
- Context: The plan's Task 3 Verification asserts all six gates exit 0 and its File-structure section asserts 'No pre-existing file is modified'. Both cannot hold. /Users/zachmcmurry/Documents/Repos/spec-loop-2/.worktrees/spec-loop/20260914-ado-connector/a4/plugins/spec-loop/scripts/test_doctrine_run_docs.py counts plugins/spec-loop/commands/*.md on disk (_counted, line 113-118) and asserts the rendered cou…
- The decision: Adding plugins/spec-loop/commands/ado-intake.md makes the on-disk command count 9 while plugins/spec-loop/README.md line 160 says '**Commands (8)**', which fails the existing test_doctrine_run_docs.py inventory assertion and the plugin unittest CI gate. The run ceiling assigns README updates to slice a5. May slice a4 make the minimal gate-forcing edit to plugins/spec-loop/README.md in this slice …
- Options:
  1. Let a4 make the minimal edit: in plugins/spec-loop/README.md only, change '- **Commands (8)**: ... dashboard-serve, jira-intake.' to '(9)' and append 'ado-intake'. Leave the root /Users/zachmcmurry/Documents/Repos/spec-loop-2/README.md prose surfaces, the CHANGELOG and the .gitignore entry to a5, and record the README touch as an over-scope exception. This matches the established precedent in this repo (commits 8d5a981 and 6ae96ee) - the slice that ships the component bumps the counted inventory in the same commit - and keeps the six gates green with a one-line, conflict-cheap doc edit rather than shipping a known-red baseline. — (RECOMMENDED DEFAULT) critic-recommended default
- If unanswered: pause this slice; continue all independent slices
- Answer: GRANTED, and two corrections to the slice's own instructions. (1) CEILING EXCEPTION: a4 MAY edit plugins/spec-loop/README.md, restricted to the single counted-inventory line - change '- **Commands (8)**:' to '(9)' and append 'ado-intake' to that one list. Nothing else in that file. This is the controller's ceiling error, not a planner over-reach: test_doctrine_run_docs.py derives the command coun…
- Answered-at: 2026-09-14T18:30:04Z

## [a5] verification failed   (status: ANSWERED)
<!-- escalation-id: a5:quality-gate-block -->
<!-- escalation-identity: 885e6724099c92ca -->
- Trigger: quality-gate-block
- Opened: (not recorded)
- Context: suite: All suite segments passed: validate_marketplace.py OK; 126 tests in scripts/; 2143 tests in plugins/spec-loop/scripts/; 2269 tests with coverage (97.3% total, all floors met); 48 tests in dashboard_assets/index.test.mjs; 136 tests in slice_wave test files; quality: FAIL (summary_pass=false, 2 open, 0 accepted — Quality gate exit code 1; two class_lines violations detected by builtin-heuris…
- The decision: Verification cannot pass automatically. Guide, accept, or drop?
- Options:
  1. Accept the listed violations as pre-existing debt — (RECOMMENDED DEFAULT) The CONTROLLER must act on this at the next dispatch: record the acceptance (redispatch.py accept-violations, then redispatch.py args) and re-dispatch with slice.entry {stage: "verify", head}.
  2. Provide fix orders — The CONTROLLER must act on this at the next dispatch: re-dispatch with slice.entry {stage: "fix", head, orders: [...]} so the FIXER receives them, or — for a red suite — answer this id and re-dispatch with {stage: "verify", head} so the debug-fixer reads it.
  3. Drop the slice — The CONTROLLER must act on this at the next dispatch: exclude the slice from the re-dispatched wave and record the drop. The loop drops nothing by itself.
- If unanswered: pause this slice; continue all independent slices
- Answer: ACCEPTED. Both open violations are whole-file class_lines with function=null on ado_client.py (1533) and test_ado_client.py (1633) - the identical fingerprints already accepted for slices a1 and a2 this run under the repo's standing human ruling from 20260825-scope-ceiling that class_lines is computed over the WHOLE file and reports file length, not class size. a5 is a behaviour-neutral documenta…
- Answered-at: 2026-09-14T20:09:57Z

## [run] Publish choice for run 20260914-ado-connector   (status: ANSWERED)
<!-- escalation-id: run:publish -->
<!-- escalation-identity: 0e6d6b4857749dcc -->
- Trigger: ambiguity
- Opened: 2026-09-14T20:30:00Z
- Context: All five slices are merged into spec-loop-run/20260914-ado-connector (HEAD d780d8e plus the run-state commit 6c9d2d8), cut from main at ca497d2. The Phase 5 six-segment suite is GREEN controller-measured, the cross-slice integration review returned PASS with no safety flag, run state and the runbook are committed, and the knowledge graph is synthesised. NOTHING has been pushed: the loop never pus…
- The decision: How should this run be published?
- Options:
  1. Push the branch and open a PR — (RECOMMENDED DEFAULT) Pushes spec-loop-run/20260914-ado-connector to origin and opens a pull request against main. Keeps main untouched and gives the connector a review surface - reasonable given it adds a first-of-its-kind irreversible external write to this plugin.
  2. Push the branch only, no PR — Pushes the branch to origin for safekeeping and leaves opening a PR to you.
  3. Merge onto main locally with --no-ff — Merges the run onto the default branch in this clone without pushing. main moves; nothing leaves the machine.
  4. Leave it local — No push and no merge. The branch stays in this clone exactly as it is; you decide later.
- If unanswered: leave it local - the branch is intact and nothing is lost
- Answer: Merge onto main and cut a new release.
- Answered-at: 2026-09-14T20:33:07Z

## [run] Does cutting the release include pushing main and the v2.6.0 tag?   (status: ANSWERED)
<!-- escalation-id: run:publish-2 -->
<!-- escalation-identity: 61650c3bd2a2027c -->
- Trigger: ambiguity
- Opened: 2026-09-14T20:35:00Z
- Context: The human asked to merge to main and cut a new release. Version 2.6.0 is settled on precedent. But release.py neither pushes nor tags: it edits plugin.json, adds a marketplace ARCHIVE entry whose source is pinned to git tag v<version>, and rolls the CHANGELOG. So a release cut without a pushed tag leaves that archive entry pointing at a tag that does not exist. Pushing main and creating a tag on …
- The decision: How far should the release go?
- Options:
  1. Local only — (RECOMMENDED DEFAULT) Merge main, run release.py 2.6.0, commit. Nothing pushed, no tag. You push and tag when ready.
  2. Push main and create the v2.6.0 tag — Also pushes main to origin and creates and pushes the annotated tag, so the marketplace archive entry resolves.
  3. Push main only — Pushes main without the tag; the archive entry stays dangling until you tag.
- If unanswered: local only
- Answer: Push main and create and push the v2.6.0 tag - the full outward-facing release.
- Answered-at: 2026-09-14T20:33:07Z

