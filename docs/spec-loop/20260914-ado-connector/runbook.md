---
schema_version: 2
run_id: 20260914-ado-connector
generated: 2026-09-14T20:23:51Z
integration_branch: spec-loop-run/20260914-ado-connector
base_branch: main
base_sha: ca497d23d221b8cb671fe7bc9d66be61b4283639
merge_mode: single-branch
integration_gate: green
slice_counts: { complete: 5, split: 0, remediation: 0 }
gap_counts: { known_gaps: 3, deferred: 2, open_findings: 3 }
publish: pending
knowledge_graph: disabled
---

## Executive Readout

**What we set out to do.** The verbatim request was "create a connector equivelant to JIRA for ADO." The restated goal: build an Azure DevOps work-item connector that functionally twins the plugin's existing Jira connector — a read-only resolver, one bounded off-by-default comment writer, a pure intake renderer, and a `/spec-loop:ado-intake` slash command with the same locked security boundary — as a parallel, self-contained implementation, not a shared abstraction with Jira.

**What shipped.** a1: `ado_client.py` read lane — resolves one work item to a normalized record (HTML-to-text description, acceptance-criteria resolution order, repro-steps handling) plus the fail-closed paginated comment sweep the dedupe gate depends on. a3: `ado_intake.py` pure renderer — record + refinement to a pinned-schema intake artifact and the comment bodies it would post, with an org+project+id-scoped in-body dedupe marker. a2: the bounded comment-WRITE lane in `ado_client.py` — the sole POST, off by default behind `--post`, with target-triple verification before credentials are read, in-batch duplicate rejection, and extraction-based marker dedupe; a2 also registers `ado_client.py` in the coverage gate. a4: the `/spec-loop:ado-intake` command plus its doctrine test and the one shared cross-provider test pinning that both connector commands carry the same bounded-write claim set. a5: containment (`.gitignore`), docs (CHANGELOG, both READMEs), and eight prose-accuracy fixes to `ado_client.py`, its test module, and `ado-intake.md` — four carried from an a2 review round that was lost to a verifier defect (see below), plus four more from a4's own review residual. No slice split; no remediation slice was needed.

**Integration status.** Integration branch `spec-loop-run/20260914-ado-connector` off `main` at `ca497d2`, single-branch merge mode. The Phase 5 suite is GREEN, controller-measured first-hand on all six segments: marketplace valid; 126 root tests; 2143 plugin tests; coverage 2269 tests at TOTAL 97.3% (8373/8604) with `ado_client.py` at 99.3% (floor 94) and `ado_intake.py` at 96.3% (floor 91), all per-file and total floors met; client JS 48/48; wave harness 136/136. `jira_client.py`, `jira_intake.py`, and `jira-intake.md` are verified byte-identical to `main` (`git diff --quiet` over that range reports no change) — the run's hardest constraint held. The cross-slice integration review returned PASS with no safety flag and all five checked seams sound; it surfaced three non-blocking follow-ons, listed below. Zero remediation slices. Nothing has been pushed or merged to `main`; publish is still pending. No external network write to Azure DevOps was ever made in this run — the write lane exists in code and is unit-tested against a faked transport only.

**Gaps you should know about.**
- The dedupe gate is TOCTOU across invocations: two concurrent armed runs (or an armed run racing a human posting the same marker) both read the comment list once, both compute `already_posted: false` from that stale snapshot, and both post — producing a duplicate comment with no delete lane. No lock is proposed; a local-file gate is structurally forbidden by an inherited Jira hazard. Mitigation is prose-only (state that only one armed run may be in flight per item) and currently lives in the module docstring, which `argparse --help` never prints.
- The marker's live write/read round trip across Azure DevOps's api-version pair (POST `7.0-preview.3`, list-read `7.1-preview.4`) has **not** been verified against a live organization — no external network call was made this run. The command prose correctly states this as unverified rather than claiming it.
- No test pipes `ado_intake.py`'s real render output into `ado_client.py`'s `agreed_target`/`validate_comment_entries` — the client's tests use a hand-authored fixture "shaped like" the renderer's output, so the two modules are consistent by inspection only, not by a pinned regression test. The controller hand-verified this interop manually at Phase 5 (marker fullmatch/extraction across all three kinds, survival through HTML wrapping and through escaping, and distinct markers for differing org/project/id) but nothing in the suite locks it down.
- A4's council deferred the ADO twin of `TestTheArtifactRootIsGitignored` (which pins `.spec-loop-jira/` in `.gitignore` for the Jira connector) as "a5's obligation," to land alongside the `.spec-loop-ado/` `.gitignore` entry. a5 added the `.gitignore` entry but did not add that doctrine test; `test_doctrine_ado_intake.py`'s own docstring notes the omission is deliberate for a different reason (the entry belongs to another slice's file), so the repo-level pin exists for Jira's artifact root but not ADO's.
- The residue-disclosure prose in `ado-intake.md` names only `record.json` as what a `/tmp` scratch directory retains after a run, but `payload.json` (full rendered comment content) and `refinement.json` (the operator's raw gap answers) persist there too; the cleanup instruction already covers all three, but the stated rationale undersells what is actually on disk.

**Key decisions made autonomously.**
- Used hand-rolled stdlib `urllib` REST rather than the Azure CLI (the repo's existing ADO precedent via `pr_resolver.py`'s `az repos pr show`), because azure-cli 2.84.0 / azure-devops 1.0.2 has no command to list a work item's comments — the CLI cannot support the read-back dedupe gate.
- Made `ADO_PROJECT` optional and absent by default: resolve on the project-optional route, derive `project` from `System.TeamProject`, and treat an operator-set `ADO_PROJECT` as an assertion that refuses on mismatch — removing an unnecessary input rather than validating a fragile one, closing half the preview/post drift surface behind the wrong-target-write hazard.
- Corrected its own coverage-gate registration rule mid-run: registration belongs to the LAST slice that modifies a module (`ado_intake.py` → a3, `ado_client.py` → a2), not to a trailing wiring slice or every slice, after an earlier plan had it wrong.
- Corrected a scope-ceiling mistake at the a4 council: a4 could not ship a new command and keep the baseline green without touching `plugins/spec-loop/README.md`'s gate-counted `**Commands (N)**` line (a doctrine test derives the command count from files on disk), so the controller granted a4 a narrow ceiling exception for that one line and amended a5's scope to drop it.
- Narrowed its own mandated body-format wording at the same a4 council: the controller had required prose claiming the connector "guarantees only that the body contains no active markup," which the council correctly flagged as itself an overstatement (only `&`, `<`, `>` are escaped) — the controller adopted the narrower, honest form.
- Human-answered escalations, one line each: (1) build the full connector including the write lane, not read+preview only — literal Jira equivalence, accepting the Tier-3 irreversible-write risk knowingly; (2) Azure DevOps Services only, no Server/on-prem; (3) a live ADO org and disposable work item are available and the human will run the one-item round-trip check; (4) a1's 12 quality-gate findings accepted as measurement debt plus fix orders (whole-file `class_lines`, a mandated-signature `parameter_count`); (5) a3's 3 whole-file `class_lines` findings accepted as debt; (6) a1's re-verification: 9 remaining nesting/cognitive findings accepted as heuristic false positives after first-hand controller code reading; (7) a2's residual `class_lines` on `measure_coverage.py` accepted as pre-existing debt, matching a3's precedent; (8) a4's council objection on the README line: granted, with the two corrections above; (9) a5's 2 `class_lines` findings accepted as the identical pre-existing fingerprint already accepted for a1/a2.

**How to verify / operate.** Run the full six-segment suite from repo root: `python3 scripts/validate_marketplace.py .` then `python3 -m unittest discover -s scripts -p 'test_*.py'` then `python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'` then `python3 scripts/measure_coverage.py` then `node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs` then `node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs plugins/spec-loop/scripts/slice_wave_radius.test.mjs plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs plugins/spec-loop/scripts/slice_wave_reentry.test.mjs plugins/spec-loop/scripts/slice_wave_accepted.test.mjs plugins/spec-loop/scripts/slice_wave_replan.test.mjs`. To operate the connector itself: set `ADO_ORG_URL` and `ADO_PAT` in the environment (never argv), run `/spec-loop:ado-intake <work-item-id>`, inspect the Step 7 preview before answering the Step 8 arming confirmation, and treat the first-ever armed post to a real organization as the live round-trip verification procedure this run left outstanding. Full run metrics are in `docs/spec-loop/20260914-ado-connector/metrics.json`.

## 1. What Was Built

| Slice | Goal | Files / subsystems | Branch — head commit | Status |
|---|---|---|---|---|
| a1 | `ado_client.py` read lane: resolve one work item read-only to the normalized record (HTML-to-text description, acceptance-criteria resolution order, repro steps) plus the fail-closed paginated comment sweep the dedupe gate depends on. | `ado_client.py`, `test_ado_client.py` — ado-connector, external-provider, transport | `spec-loop/20260914-ado-connector/a1` — `6ae96ee` | complete |
| a3 | `ado_intake.py` pure renderer: record + refinement → pinned-schema artifact under `.spec-loop-ado/` and the comment bodies it would post, with the org+project+id-scoped in-body dedupe marker. | `ado_intake.py`, `test_ado_intake.py` — ado-connector, rendering | `spec-loop/20260914-ado-connector/a3` — `ba3e2f8` | complete |
| a2 | `ado_client.py` bounded comment WRITE lane: the sole POST, off by default behind `--post`, target-triple verification before credentials, in-batch duplicate rejection, escaped inert bodies, extraction-based marker dedupe. Registers `ado_client.py` in the coverage gate. | `ado_client.py`, `test_ado_client.py`, `scripts/measure_coverage.py`, `scripts/coverage_omit.txt`, `scripts/test_measure_coverage_manifest.py` — ado-connector, external-provider, mutating-write | `spec-loop/20260914-ado-connector/a2` — `caeaa7d` | complete |
| a4 | The `/spec-loop:ado-intake` command with locked `allowed-tools` and an accurate security boundary, its doctrine test, and the shared cross-provider test pinning both connector commands' bounded-write claim set. | `commands/ado-intake.md`, `test_doctrine_ado_intake.py`, `test_doctrine_intake_parity.py`, one counted line in `plugins/spec-loop/README.md` (ceiling exception) — commands, doctrine | `spec-loop/20260914-ado-connector/a4` — `85c1e77` | complete |
| a5 | Docs, containment, and eight carried prose-accuracy fixes (four from a2's lost review round, four from a4's review residual) — no behaviour change. | `.gitignore`, `CHANGELOG.md`, `README.md`, `plugins/spec-loop/README.md`, `ado_client.py`, `test_ado_client.py`, `commands/ado-intake.md` — ci-gates, docs | `spec-loop/20260914-ado-connector/a5` — `6a4267d` | complete |

No slice was split; no slice required remediation. 13 files changed overall, ~6,041 insertions (`git diff --stat` over `ca497d2..d780d8e`).

## 2. Business Logic (rules the code now enforces)

From `dag.json.shared_constraints` and the merged behaviour:

- **Jira isolation.** `jira_client.py`, `jira_intake.py`, and `jira-intake.md` are never modified; verified byte-identical to `main` at Phase 5. No shared runtime module exists between the two connectors — duplication over coupling is the repo's standing stance. The one sanctioned exception is `test_doctrine_intake_parity.py`, a shared *test* pinning that both commands carry the same bounded-write claim set.
- **stdlib only.** No new dependency, no `requirements.txt`, no Azure CLI dependency — verified against the installed azure-cli 2.84.0 / azure-devops 1.0.2, which has no comment-list command, making the CLI structurally unable to support the dedupe gate.
- **Read lane is structurally incapable of a mutating verb.** `_http_get` takes no `data` parameter and hardcodes `method='GET'`. Confirmed unchanged by a2's write-lane addition (Phase 5 seam check).
- **No URL from a response body is ever fetched.** Every request URL is composed locally from the validated origin plus a literal path; `continuationToken` is regex-validated, percent-encoded, and fails closed.
- **Credentials from environment only**, never argv, never in an artifact, rendered body, or error message.
- **Fail closed on haystack-shrinking ambiguity.** Any value that would silently shrink the dedupe haystack (missing/empty comment text, missing or non-numeric `totalCount`, an unmatched `continuationToken`) raises rather than defaulting to empty.
- **Target-triple verification before credentials.** The bounded comment writer binds to `(org, project, id)` from the resolved record and re-verifies a fresh resolve still agrees before the write, closing the wrong-target hazard unique to ADO's bare-integer work-item IDs (a Jira card key like `PROJ-1234` is self-scoping; a bare ADO integer like `1234` exists in every org). `_assert_target_unchanged`'s docstring (rewritten by a5) states plainly that the record check catches both drift shapes, and the environment comparison is belt-and-braces.
- **In-batch duplicate rejection before the first request** — an inherited Jira hazard (`in-batch-duplicates-are-the-one-dedupe-hole-a-read-back-cannot-close`), closed here at validation time, before any POST.
- **The dedupe marker lives inside the posted body**, written by the one call that performs the write — no local file is ever the dedupe gate (the second inherited Jira hazard).
- **Host allow-list is a fixed regex** over `dev.azure.com` and the legacy `*.visualstudio.com` form, deliberately with no opt-in extra-hosts variable; a Server/on-prem host must produce a clear refusal.
- **`ADO_PROJECT` is optional and absent by default** — derived from `System.TeamProject` in the response, with an operator-set value treated as an assertion that refuses on mismatch (an autonomous run decision; see Executive Readout).
- **Coverage-gate registration is owned by the last slice to modify a module** — `ado_intake.py` by a3 (96.3% vs. floor 91), `ado_client.py` by a2 (99.3% vs. floor 94) — not by a trailing wiring slice and not by every slice (a mid-run controller self-correction).
- **Every new product module carries a ≤5-line `if __name__ == "__main__":` shim**, pinned by `test_measure_coverage_manifest.py`.
- **Command prose must not claim a safety property this repo has not verified** — the marker round trip is stated as unverified, not claimed; and the body-format guarantee is stated as "escapes `&`, `<`, `>`; refuses a body still carrying `<` or `>`," not the broader "no active markup" the controller originally mandated and then narrowed.

## 3. Gaps & Deferred

- **Dedupe-gate TOCTOU across invocations.** *What:* two concurrent armed runs (or an armed run racing a human pasting the same marker) both read the comment list once and both plan `already_posted: false` from that stale snapshot, so both post — a duplicate comment with no delete lane. *Why deferred:* no lock is proposed, and a local-file gate is structurally forbidden by the inherited "premark must be written inside the claim that does the write" hazard; this is inherent to the design, not a plan defect. *Reversibility:* the mitigation is prose-only today (state in the command's user-visible surface, not just the module docstring, that only one armed run may be in flight per work item) — fully reversible/additive as a follow-on.
- **Live marker round-trip unverified.** *What:* the claim that a POSTed marker survives Azure DevOps's asymmetric api-version pair (Add `7.0-preview.3`, List `7.1-preview.4`) and comes back extractable has not been exercised against a live organization in this run. *Why deferred:* the human answered that a live org and disposable work item are available and agreed to run the one-item procedure, but that procedure was not executed as part of this run. *Reversibility:* fully reversible — the command prose already states the limit rather than claiming it away; running the check only adds evidence, changes no code.
- **No regression test pins `ado_intake.py` → `ado_client.py` interop.** *What:* `test_ado_client.py` validates `agreed_target`/`validate_comment_entries` against a hand-authored fixture "shaped like" the renderer's real output, never importing `ado_intake.py`, so the two modules are consistent by inspection only. *Why deferred:* the controller hand-verified the interop manually at Phase 5 (marker fullmatch/extraction, survival through HTML wrapping and escaping, distinct markers across differing org/project/id) and judged the gap additive rather than blocking; the controller does not write product code itself. *Reversibility:* fully reversible — flagged by Phase 5 review as "HIGHEST VALUE" follow-on.
- **ADO twin of `TestTheArtifactRootIsGitignored` was never added.** *What:* a4's council deferred this doctrine test (which pins the Jira connector's `.gitignore` entry) as "a5's obligation" to land beside the `.spec-loop-ado/` entry; a5 added the `.gitignore` entry but not the pinning test, and `test_doctrine_ado_intake.py` documents the omission for an unrelated reason (file ownership), not because it was covered elsewhere. *Why deferred:* fell through a genuine handoff gap between a4 and a5 despite being explicitly logged. *Reversibility:* fully reversible, small, additive.
- **Residue-disclosure prose undersells scratch-directory contents.** *What:* `ado-intake.md` names only `record.json` as what the `mktemp` scratch directory retains; `payload.json` and `refinement.json` also persist there. *Why deferred:* not a safety hole (the cleanup instruction already covers the whole directory), so Phase 5 review classed it non-blocking. *Reversibility:* trivial prose fix.

No open escalations and no un-remediated P1 findings. All `class_lines`/`parameter_count`/nesting findings the run accepted as debt are recorded in §5 and in each sidecar's `quality.accepted`, not silently dropped.

## 4. Requirement Traceability

| Requirement (from `request.md`) | Status | Evidence |
|---|---|---|
| `ado_client.py` read lane: resolve one work item, structurally incapable of a mutating verb | delivered | a1 sidecar (commits `ca497d2`→`6ae96ee`, 7 tasks); Phase 5 seam check confirms `_http_get` still has no `data` param post-a2 |
| `ado_client.py` bounded comment writer, preview-by-default, `--post` arms the POST | delivered | a2 sidecar (commits `a39272b`→`caeaa7d`, 7 tasks); target-triple verification, in-batch dedupe, marker extraction all confirmed sound at Phase 5 |
| `ado_intake.py` pure renderer: record + refinement → pinned-schema artifact + comment bodies with dedupe marker | delivered | a3 sidecar (commits `ca497d2`→`ba3e2f8`, 9 tasks); Phase 5 seam check confirms `MARKER_RE`/`MARKER_DIGEST_RE` byte-identical to a2's copy |
| `/spec-loop:ado-intake` command, same step structure and `allowed-tools` lock as `jira-intake.md` | delivered | a4 sidecar (commits `850a6cb`→`85c1e77`, 2 tasks, 13 agents, council ENDORSE_WITH_CONCERNS); 7 confirmed review findings fixed in-slice, remainder carried to a5 |
| Unit tests mirroring `test_jira_client.py`/`test_jira_intake.py` conventions | delivered | `test_ado_client.py`, `test_ado_intake.py` shipped across a1/a2/a3; full suite 2143 plugin tests green at Phase 5 |
| `test_doctrine_ado_intake.py` doctrine guards on command prose and invariants | delivered | a4 sidecar; 247-line doctrine file pins target binding, web-UI-delete re-arm, body-format, marker round-trip, temp-copy residue claims |
| Registration and docs: `.gitignore`, plugin README, root README, CHANGELOG | partial | a5 sidecar delivers the `.gitignore` entry, CHANGELOG, and both READMEs, but the ADO doctrine-test twin of `TestTheArtifactRootIsGitignored` was never added (see §3) |
| Posting twice is a no-op (in-body marker dedupe); two identical bodies in one batch rejected at validation | delivered, unit-verified only | a2 tests exercise both paths against a faked transport; no live ADO round trip was run (see §3) |
| Full suite green; doctrine test pins command's security prose | delivered | Phase 5 gate event, all six segments GREEN |

## 5. Decisions Summary

**Material autonomous decisions** (full text in `decisions-log.md` / `events.jsonl`):
1. Chose hand-rolled stdlib `urllib` REST over the Azure CLI, verified against the installed azure-cli 2.84.0 / azure-devops 1.0.2, because no CLI command lists a work item's comments.
2. Made `ADO_PROJECT` optional and derived `project` from the response instead of validating an operator-supplied one, closing half the preview/post drift surface behind the wrong-target-write hazard.
3. Corrected the coverage-gate registration rule mid-run to "last slice to modify the module," reassigning `ado_intake.py`→a3 and `ado_client.py`→a2 (previously miscast as a5-exclusive/trailing).
4. Granted a4 a narrow scope-ceiling exception to edit one gate-counted line in `plugins/spec-loop/README.md`, correcting the controller's own ceiling assignment (test-derived command counts structurally couple a new command file to that line), and amended a5's scope to drop it.
5. Narrowed its own mandated body-format prose after the a4 council correctly flagged the controller's original wording ("guarantees only... no active markup") as itself an overstatement — adopted the honest, narrower form (escapes `&`/`<`/`>`; refuses `<`/`>`).
6. Restored the integration branch after a wave-1 agent wrote coverage-gate registration into the main checkout instead of its slice worktree (both diffs preserved under `docs/spec-loop/.../evidence/`).
7. Stopped routing controller fix orders through `slice.entry.orders` at review tier 3 after a loop defect (below) lost two full rounds of prose fixes; moved them into a5's slice GOAL instead.

**A loop defect worth recording.** Controller fix orders routed through `slice.entry.orders` were stamped with a synthetic evidence quote of the literal string `"controller order"`. The finding-verifier's mechanical evidence-quote check requires that quote to appear in the diff/file, and it never does for a controller-authored order — so it mechanically REFUTED all of them before any fixer ran, twice: 7 orders lost on a1 (`qg-fix-1` through `qg-fix-7`) and 4 lost on a2 (`prose-1` through `prose-4`). In both cases the verifier's own rationale conceded the substantive claim was often true (e.g., "line 156 ... does still read 'This module issues GET only'... arguably stale... but the supplied evidence quote does not match"). The workaround that worked: move the fixes into a slice's GOAL text, where the planner turns them into normal tasks that carry real evidence — this is how a5's eight prose-accuracy fixes were ultimately delivered.

**Human-answered escalations** (9 of 9 answered, 0 open):
- `run:ambiguity` — build the full connector including the write lane (not preview-only).
- `run:material-assumption` — Azure DevOps Services only, no Server/on-prem.
- `run:material-assumption-2` — a live org and disposable work item are available; human will run the round trip (not yet executed as of this runbook).
- `a1:quality-gate-block` — partial acceptance (whole-file `class_lines`, mandated-signature `parameter_count`) plus fix orders for the remaining function-level findings.
- `a3:quality-gate-block` — accepted 3 whole-file `class_lines` findings as pre-existing measurement debt.
- `a1:quality-gate-block:2` — accepted 9 nesting/cognitive findings as heuristic false positives after first-hand controller code reading.
- `a2:quality-gate-block` — accepted the residual `class_lines` on `measure_coverage.py` as pre-existing debt (same fingerprint as a3's).
- `a4:council-objection` — granted the README ceiling exception plus the body-format wording correction.
- `a5:quality-gate-block` — accepted 2 `class_lines` findings, identical fingerprints already accepted for a1/a2.

## 6. Integration Gate Result

Phase 5 suite result: **GREEN**, controller-measured first-hand on the integration branch at head `d780d8e` (tree `845328b`): marketplace valid; 126 root tests; 2143 plugin tests; coverage 2269 tests with `ado_client.py` 99.3% (floor 94) and `ado_intake.py` 96.3% (floor 91), TOTAL 97.3% (8373/8604), all per-file and total floors met; client JS 48/48; wave harness 136/136. Jira-unchanged check: `git diff --quiet main..HEAD` over `jira_client.py`, `jira_intake.py`, `jira-intake.md` reports no change.

Cross-slice integration review: **PASS**, no safety flag, range `ca497d2..HEAD`, one reviewer, five seams checked and all five sound (a1/a2 transport boundary, a3/a2 renderer-to-writer contract, a4/a5 prose-vs-code, duplication-vs-drift across connectors, coverage-gate registration). Three non-blocking follow-ons were recorded (interop test gap, residue-disclosure completeness, an optional marker-regex-equality test subsumed by the first). No remediation slice was created — the controller's stated rationale is that the suite is green on all six segments, the review verdict is PASS with no safety flag, and the highest-value finding is an additive regression test the controller itself cannot write (it does not author product code).

Slice-level quality gates: a4 reached a mechanical PASS (0 violations) at final verify; a1, a2, a3, and a5 each carry controller-accepted `class_lines`/`parameter_count` debt (documented per-slice above and in §5) but zero unaddressed violations at final verify.

## 7. How to Verify & Operate

**Full suite** (the exact command run at every slice verify and at Phase 5):
```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'
python3 scripts/measure_coverage.py
node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs plugins/spec-loop/scripts/slice_wave_radius.test.mjs plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs plugins/spec-loop/scripts/slice_wave_reentry.test.mjs plugins/spec-loop/scripts/slice_wave_accepted.test.mjs plugins/spec-loop/scripts/slice_wave_replan.test.mjs
```

**Module-specific tests:**
- `python3 -m unittest plugins.spec_loop.scripts.test_ado_client` (or run via the discover command above) — read lane, write lane, target-triple binding, dedupe.
- `python3 -m unittest plugins.spec_loop.scripts.test_ado_intake` — renderer, marker construction, schema.
- `python3 -m unittest plugins.spec_loop.scripts.test_doctrine_ado_intake` — command security prose, five pinned claims.
- `python3 -m unittest plugins.spec_loop.scripts.test_doctrine_intake_parity` — cross-provider bounded-write claim-set parity between `jira-intake.md` and `ado-intake.md`.

**No new CI gates, scripts, or thresholds were introduced beyond registering the two new modules in the existing coverage manifest** (`scripts/measure_coverage.py` TARGET_FILES/PER_FILE_FLOORS, `scripts/coverage_omit.txt`) with measured floors: `ado_client.py` 94% (measured 99.3%), `ado_intake.py` 91% (measured 96.3%).

**Operating the connector:**
1. Set `ADO_ORG_URL` and `ADO_PAT` in the environment only (never argv, never in an artifact).
2. Run `/spec-loop:ado-intake <work-item-id>`.
3. Review the Step 7 preview (comment bodies, resolved target) before answering Step 8's arming confirmation, which names the work item's title and web URL.
4. Treat the first-ever armed `--post` against a real organization as the outstanding live round-trip verification (see §3) — confirm the marker is extracted on read-back, then run armed again and confirm the second run reports already-posted with no new comment.
5. Do not run two armed invocations against the same work item concurrently (§3, TOCTOU gap).

Full run metrics, including per-wave timing and token totals, are in `docs/spec-loop/20260914-ado-connector/metrics.json`.
