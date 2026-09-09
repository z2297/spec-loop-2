---
schema_version: 2
run_id: 20260908-jira-intake
generated: 2026-09-09T08:15:07Z
integration_branch: spec-loop-run/20260908-jira-intake
base_branch: main
base_sha: 5bf313aade526424b196814d25cf2c3aa5a9d364
merge_mode: single-branch
integration_gate: green-after-remediation
slice_counts: { complete: 3, split: 0, remediation: 1 }
gap_counts: { known_gaps: 3, deferred: 16, open_findings: 5 }
publish: pending
knowledge_graph: disabled
---

# Runbook — 20260908-jira-intake

## Executive Readout

**What we set out to do.** The user asked spec-loop to accept a Jira card, break the work down,
and surface questions instead of guessing — answered questions get logged back to the card as
decision comments, unanswered ones as open-question comments, and the card gets a refined
description/acceptance-criteria/risks/gaps summary for the human to confirm before anything is
written. None of this may auto-start implementation, and the path must stand alone without ever
running the loop.

**What shipped.** j1: a self-contained, stdlib-only, read-only Jira Cloud REST v3 client
(`jira_client.py`) that resolves one issue key to a normalized record with paginated comments,
authenticating from `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN` and failing closed when any is
unset. j2: the `/spec-loop:jira-intake` command (`jira_intake.py` + `jira-intake.md`) — reads a
card via j1, produces a refined-understanding artifact under a gitignored root, asks every gap in
one batched question round, previews the comments it would post, and prints the
`/spec-loop:spec-loop --from-plan <path>` handoff; it is structurally unable to start the loop,
since `allowed-tools` carries neither `Workflow` nor `Edit`. j3: the comment write-back lane —
posts confirmed-understanding/decision/open-question comments behind a preview-then-confirm gate,
with a visible marker embedded per comment and dedupe read back from the card's own paginated
comment list. r1 (remediation, raised by the Phase 5 cross-slice review after the branch was
already CI-green): mapped a bare `OSError`/`TimeoutError` on the read path into the same
fail-closed `JiraError` contract the write path already had, corrected an error message that
cited an example issue key its own regex rejects, and fixed a stale hand-maintained count in a
test comment.

**Integration status.** Base `main` at `5bf313a`, integration branch
`spec-loop-run/20260908-jira-intake`, final head `8d6328c` (merge commit for r1). The full 7-CI-segment
suite ran first-hand and came back green on the branch at `b875740` (before r1) and again,
independently, at r1's own head `f441f7e`: `validate_marketplace.py` OK; 126 root dev tests;
1741 plugin tests (baseline 1479, so +262 new, none deleted); `measure_coverage.py` PASS, TOTAL
97.1% (7110/7321) against a 90% floor, `jira_client.py` 99.6% (467/469) against a 94% floor,
`jira_intake.py` 96.2% against a 91% floor; Node `slice_wave` suites 98/98; Node
`dashboard_assets` 48/48; `claude plugin validate` passed for both the marketplace root and
`plugins/spec-loop/`. The Phase 5 cross-slice code review (run after that CI-green state; its own
verdict/tier is not separately recorded in `events.jsonl` beyond the resulting decision) surfaced
three findings against the already-green branch, and the controller folded all three into one
remediation slice (r1, tier 3) rather than accepting or deferring any of them. Publish choice:
**pending** — this runbook is written before the publish prompt, by design.

**Gaps you should know about.**
- The repo's quality gate is calibrated for a .NET codebase, not this Python plugin: its
  `tier3_surfaces` are all Migrations/appsettings/Endpoints paths, and run over *untouched*
  history (base = the commit before `pr_resolver.py` existed, head = `main`) it yields 600
  failures on already-shipped code, including 23 whole-file `class_lines` breaches
  (`pr_resolver.py` 424, `test_pr_resolver.py` 593, `run_state.py` 1080, `quality_gate.py` 1403,
  `test_dashboard_server.py` 2467). Every slice this run paid an escalation round for violations
  nobody intends to fix. A `.spec-loop/quality-gate.json` overlay was deliberately **not** added
  — calibrating the gate is the operator's call, not the run's.
- The sidecar's own quality-gate block was stale on multiple dispatches this run — each time a
  pre-fix snapshot the controller had to re-measure and override before it could trust it: j2
  claimed 39 then 12 violations against a controller-measured ground truth of 2 and then 3; j3
  claimed 14 including a `cognitive_complexity` 16 in `_errors_for_comment_entry` that measures 8
  and passes; r1 claimed a `nesting_depth` 4 that does not appear in the measured failures at
  all. The controller's own running tally in its escalation answers labels these the run's 4th,
  5th and 6th stale quality blocks, and separately notes "the same stale-snapshot defect seen in
  j1 across three dispatches."
- `review.residual` replayed byte-identical from the resume cache across all three of j1's
  dispatches, still listing three findings the controller had independently re-verified fixed in
  the shipped code.
- After a resume, the wave's plan stage re-derives from the slice **goal**, finds the goal
  already delivered, and escalates "already implemented" instead of running the controller's
  ordered fix list — the answers map reaches the fix stage, not the plan stage. This cost one j2
  dispatch a full agent with zero tasks completed. The working fix was to re-dispatch as a fresh
  workflow with the slice goal rewritten to *be* the defect list (used for both j2's and j3's
  narrow fix rounds).
- The verify stage is deterministic on the quality gate's exit code, so a slice whose only
  remaining violations are the accepted `class_lines` category escalates forever: j1 escalated
  three times on the identical four violations, the third returning the same head with no new
  commit and 221k subagent tokens spent replaying cached agents. The controller closed it by
  measuring the suite first-hand and writing the DONE sidecar itself, the same mechanism used for
  17+ slices across runs 20260825/26/27/28.
- j3 and r1 each crashed at `verify:1` on the same `StructuredOutput` retry-cap exception, in
  both cases after every task in that dispatch had already committed; the controller confirmed
  the committed work independently through the real callables rather than losing it to a blind
  retry.
- A j2 implementer wrote a documentation task into the primary checkout instead of its slice
  worktree, leaving stray uncommitted edits (`.gitignore`, both READMEs) that blocked the j2
  merge; discarded only after the controller verified the j2 branch already carried the same
  content, correctly line-wrapped.
- Known limitations shipped deliberately (controller-verified, recorded in the sidecar
  residuals): the comment-dedupe gate is per-invocation, not cross-process, so two operators
  arming the write concurrently can both post; a comment that merely *quotes* a marker makes the
  lane report an already-posted comment that was never written (fails safe, toward not writing);
  the corrected partial-failure recovery path depends on the rendered `<tmp>/comments.json`
  still existing; `jira_client.py:241`'s docstring overreaches on which read-path transport
  exceptions map to `JiraError`; `risks[].id`/`gaps[].id` are not delimiter-neutralized (only
  refused outright on a bare newline); and `_comment_results`' `by_marker` collapse survives as
  a latent trap for a future caller that bypasses `validate_comment_entries`.
- Deferred, not built: reading Jira replies back as answers (needs comment threading, reply
  attribution, and stable question ids); a repo-calibrated `.spec-loop/quality-gate.json`
  overlay.

**Key decisions made autonomously.**
- Accepted the quality gate's residual `class_lines`/stdlib-forced `parameter_count` violations
  as pre-existing debt on all four slices, by direct citation of run 20260825-scope-ceiling's
  precedent, while still blocking on and ordering fixes for every new function-level violation
  the run's own code introduced.
- Promoted j3's in-batch duplicate-comment-marker finding to BLOCKING after reproducing an
  actual double-post to a (stubbed) live card, and required a pre-POST refusal fix rather than
  accepting it as a lesser finding.
- Closed j1 by writing its own DONE sidecar from a first-hand suite measurement instead of a
  fourth re-dispatch, after determining the wave's verify stage would loop on the same
  already-accepted residuals indefinitely.
- Created remediation slice r1 from the Phase 5 cross-slice review rather than accepting its
  findings as-is, after reproducing two of its three findings first-hand through the real
  callables.
- Discarded three stray uncommitted edits from the primary checkout that were blocking the j2
  merge, only after verifying the j2 branch already carried the same, better-wrapped content.

Every human-answered escalation this run (four; all other "ANSWERED" escalations in
`escalations.md` were resolved by the controller itself, by precedent or direct measurement, with
no additional human wait — see §5):
- Jira access mechanism → stdlib REST script + env vars (`JIRA_BASE_URL`/`JIRA_EMAIL`/
  `JIRA_API_TOKEN`); the Atlassian MCP connector was rejected as unauthenticated in this
  environment and invisible to every CI gate.
- First irreversible external write → render, confirm, then post; nothing posts by default, a
  second explicit confirmation arms the write, and dedupe reads the card's own paginated comment
  list for a visible marker rather than trusting a local ledger as the gate.
- Card-data residency → card-derived artifacts are untracked by default, written to a gitignored
  path, with the command ensuring that ignore entry exists before it writes anything.
- Breakdown granularity → intake produces a refined request file plus a *printed*
  `/spec-loop:spec-loop --from-plan <path>` handoff; slice decomposition stays with the
  controller, and intake structurally cannot invoke the loop.

**How to verify / operate.** Run, in order, from the repo root on the integration branch:
`python3 scripts/validate_marketplace.py .`; `python3 -m unittest discover -s scripts -p 'test_*.py'`;
`python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'`;
`python3 scripts/measure_coverage.py`;
`node --test --experimental-test-coverage plugins/spec-loop/scripts/dashboard_assets/index.test.mjs`;
`node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs plugins/spec-loop/scripts/slice_wave_radius.test.mjs plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs plugins/spec-loop/scripts/slice_wave_replan.test.mjs`;
`claude plugin validate .` and `claude plugin validate plugins/spec-loop/`. To operate the
feature: set `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` in the environment, then run
`/spec-loop:jira-intake <JIRA-KEY>` (e.g. `ABC-123`); it writes `.spec-loop-jira/<KEY>/intake.md`,
previews the comments it would post, and only arms the write after a separate confirmation and
the `--post` flag. Full metrics: `docs/spec-loop/20260908-jira-intake/metrics.json`.

---

## 1. What Was Built

| Slice | Goal | Files / subsystems | Branch / head | Status |
|---|---|---|---|---|
| j1 (tier 3) | Read-only stdlib Jira Cloud REST v3 client: resolve one issue key to a normalized record (key, summary, description, ACs, status, issue type, url, full paginated comments); Basic auth from env vars; fails closed with no creds; no POST anywhere. | `plugins/spec-loop/scripts/jira_client.py`, `test_jira_client.py`, `scripts/measure_coverage.py` — subsystems: jira-integration, credentials, coverage-gate | `spec-loop/20260908-jira-intake/j1`, `5bf313a…→f79156b` | complete (DONE) |
| j2 (tier 2) | `/spec-loop:jira-intake` command: read via j1, produce a refined-understanding artifact under a gitignored root, one batched `AskUserQuestion` round for the ranked gaps, render (never post) comment bodies, print the `--from-plan` handoff; README command-count updates; doctrine test pinning the artifact schema and the no-Workflow/no-Edit invariant. | `plugins/spec-loop/commands/jira-intake.md`, `scripts/jira_intake.py`, `test_jira_intake.py`, `test_doctrine_jira_intake.py`, both READMEs, `.gitignore`, `scripts/measure_coverage.py` — subsystems: commands, jira-integration, docs, doctrine-tests | `spec-loop/20260908-jira-intake/j2`, `f6ed728…→d3cc117` | complete (DONE) |
| j3 (tier 3, review tier 2) | Comment write-back lane: post confirmed-understanding/decision/open-question comments behind an explicit second confirmation, visible marker per comment, dedupe from the card's paginated comment list so a re-run posts nothing; preview is the default. | `jira_client.py`, `test_jira_client.py`, `jira_intake.py`, `test_jira_intake.py`, `commands/jira-intake.md` — subsystems: jira-integration, external-write, idempotency | `spec-loop/20260908-jira-intake/j3`, `4060156…→43ebdf8` | complete (DONE) |
| r1 (tier 3, **remediation**) | Integration remediation from the Phase 5 cross-slice review: (1) map a bare `OSError` on `_http_get`'s read path to the same `JiraError` contract `_http_post` already had; (2) fix `validate_issue_key`'s rejection message, which cited an example (`A-1`) its own regex rejects, and the test that had pinned it; (3) correct a stale "fourteen targets" count in a test comment to fifteen. | `jira_client.py`, `test_jira_client.py`, `scripts/test_measure_coverage_manifest.py` — subsystems: jira-integration, error-handling | `spec-loop/20260908-jira-intake/r1`, `b875740…→f441f7e` (merged as `8d6328c`) | complete (DONE), remediation |

No slice was split; no merges beyond the four sequential wave merges recorded above
(`metrics.json`: `splits.split_parents: 0`, `merges.count: 0`). All four sidecars report
`status: "DONE"`.

## 2. Business Logic

Rules the shipped code now enforces, from `dag.json.shared_constraints` and the sidecars'
delivered behavior:

- **Stdlib-only, no shared helper module.** Neither `jira_client.py` nor `jira_intake.py` imports
  a third-party package or factors a shared HTTP/util module out of `pr_resolver.py`; each
  duplicates the small helpers it needs locally.
- **Credentials from the environment only.** `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN` are
  read from `os.environ`, never from `argv`; absent credentials fail closed with an actionable
  message. `TestTokenNeverLeaks`-style tests assert the raw token, the account email, and the
  composed `base64(email:token)` string are each absent from exception text, stdout, and stderr.
- **Issue-key and host validation before any URL/path/argv use.** The issue key is checked
  against a strict regex and percent-encoded regardless; the Jira host is allow-listed, HTTPS is
  required, and the `Authorization` header is dropped on any cross-origin redirect (r1 also
  closed the read-path gap where a bare `OSError`/`TimeoutError` could escape this contract as a
  raw traceback instead of the documented `{"ok": false, "errors": [...]}` shape).
- **No Bash string interpolation of Jira data.** Any subprocess call goes through a single
  `shell=False`, list-args choke point, mirroring `pr_resolver.py`'s `_run`.
- **Untrusted card text.** Jira issue summary, description, ACs, and every existing comment are
  treated as data, never instructions; an attempt inside card text to redirect the flow is itself
  a finding to report, not something to act on.
- **Comment write path: render, confirm, then post.** Nothing posts by default. Comment bodies
  are rendered locally and previewed; a second explicit confirmation plus the `--post` flag arms
  the HTTP verb. The dedupe marker is written by, and only by, the function that performs the
  POST; the local rendered-comments file is an audit cache, never the gate. Dedupe reads back the
  card's own **paginated** comment list (a response missing `total` now raises `JiraError`
  fail-closed instead of silently truncating the sweep to one page) and matches a visible marker
  embedded in the comment body.
- **In-batch duplicate-marker refusal.** `validate_comment_entries` refuses a batch containing two
  entries with the same marker before any request is sent, closing the one gap the card read-back
  structurally cannot close (two same-batch POSTs happen after a single read snapshot).
- **Card-derived artifacts are untracked by default.** Written under the gitignored
  `.spec-loop-jira/` root; the command ensures that `.gitignore` entry exists (via a fixed-literal
  `Bash` append, never a `Write`) before writing anything derived from a card.
- **The intake command cannot start the loop.** `allowed-tools` carries neither `Workflow` nor
  `Edit`; the handoff is a printed `/spec-loop:spec-loop --from-plan <path>` line the human runs.
- **Artifact front matter and body are neutralized against card-controlled delimiters.** Every
  card-derived front-matter scalar is quoted/escaped (a status like `Blocked: waiting` no longer
  breaks YAML), and every card-derived body surface (H1 summary, description, AC items, risk
  rows, gap rows, embedded comment blocks) is checked to still contain exactly two `---` lines
  even when the card text itself contains a bare `---` line.
- **New gated modules are registered in both `TARGET_FILES` and `PER_FILE_FLOORS`** in
  `scripts/measure_coverage.py`, floor set to locally-measured coverage minus a ≥5-point margin
  (`jira_client.py` 94%, `jira_intake.py` 91%).
- **Provider write-back supersession is stated explicitly.** The command's security section names
  that this reverses `peer-review.md`'s "provider write-back deliberately deferred" ruling, in a
  bounded way — comments only, never a transition, field edit, assignee change, or sub-task.

## 3. Gaps & Deferred

**Quality-gate miscalibration for this repo** — what: the gate's `tier3_surfaces` are .NET
paths (Migrations/appsettings/Endpoints); measured over untouched shipped history it produces 600
failures including 23 whole-file `class_lines` breaches on code this run never touched · why
deferred: a `.spec-loop/quality-gate.json` overlay is the mechanism, but the standing ruling is
"no threshold weakened," and calibrating the gate for this repo is an operator decision, not
something a run should do to itself · reversibility: fully reversible — adding the overlay is a
config change, not a code change.

**Cross-process comment-dedupe race** — what: the dedupe gate reads the card once per invocation,
so two operators (or an overlapping re-run) can both act on the same pre-write snapshot and both
post · why deferred: closing it needs either a Jira-side idempotency mechanism (none exists on
`addComment`) or a stronger cross-process lock than a local audit cache is allowed to be under
this run's own write-safety ruling · reversibility: the current behavior fails toward *not*
posting in the sibling case (quoted-marker false positive); the true race is a real but narrow
residual, documented in the command's security section rather than built around.

**Marker-quoting false positive** — what: a comment that merely *quotes* a marker (e.g. Jira's
reply-quote, or someone pasting the printed marker list) makes the lane report a comment as
already-posted when it was never written · why deferred: fails safe (toward not writing), and the
alternative — a stronger match — risks the opposite, more dangerous failure mode · reversibility:
reversible; a stricter marker-location check could tighten this later without breaking the
dedupe contract.

**Partial-failure recovery depends on a temp file surviving** — what: the corrected recovery
prose (fixed in j3's second round after the earlier text was itself unsafe — see §5) is
conditioned on `<tmp>/comments.json` still existing; if that `mktemp -d` directory is gone there
is no stated recovery, because re-running the refinement is correctly forbidden (it would
generate new markers and risk a near-duplicate post) · why deferred: the durable fix is to
persist the rendered comments beside the artifact instead of in a temp dir, named as a follow-on
rather than built here · reversibility: reversible, additive.

**`jira_client.py:241` docstring overreach** — what: the comment claims "every transport failure
on the READ path is a `JiraError`," but `http.client.IncompleteRead`/`BadStatusLine`/
`LineTooLong` are not `OSError` subclasses, so they are not actually mapped · why deferred: the
identical gap exists on `_http_post` (precedent-consistent code), so only the wording is absolute
— this is a documentation-accuracy gap, not a behavioral one, and was left as a known limitation
rather than pulled into r1's narrow scope · reversibility: reversible, a wording fix.

**`risks[].id` / `gaps[].id` not delimiter-neutralized** — what: these model-authored id fields
are refused outright on any newline but are not neutralized the way card-derived text is · why
deferred: accepted as controller-verified, lower-severity than the card-text surfaces because the
ids are model-authored, not attacker-controlled Jira prose · reversibility: reversible.

**`_comment_results`' `by_marker` collapse — latent trap** — what: the mechanism that produced
wrong ids (`['2','2']`) for a duplicate-marker batch is left in place, correctly, since
`validate_comment_entries` now refuses duplicates before it can be reached from
`run_comment_lane` · why deferred: unreachable from the shipped call path today, so hardening it
now would be speculative · reversibility: reversible; worth closing if a future caller bypasses
the validator.

**Deferred follow-ons (named, not built), per `dag.json.scope_ceiling` and the run's own
`deferred` events (16 total across the run):** reading Jira replies back as answers (needs
comment threading, reply attribution, and stable question ids); a repo-calibrated
`.spec-loop/quality-gate.json` overlay; factoring a shared HTTP/utility module out of
`pr_resolver.py`; a second work decomposer (explicitly out of scope — decomposition stays with
the controller's Phase 0 step 7); non-Jira trackers; any Jira write beyond adding a comment;
bulk/board-level ingestion.

## 4. Requirement Traceability

| Requirement (from `request.md`) | Status | Evidence |
|---|---|---|
| Fetch a Jira issue (fields, ACs, comments) | delivered | j1 `jira_client.py`: `resolve_issue`, paginated `fetch_comments`; sidecar tests green at `f79156b` |
| Present a refined understanding (description/ACs/risks/gaps) for human confirmation | delivered | j2 `jira_intake.py`: refinement artifact schema, `.spec-loop-jira/<KEY>/intake.md`, pinned by `test_doctrine_jira_intake.py` |
| Confirmed-understanding comment written back to the card | delivered | j3: `run_comment_lane` posts the understanding comment behind the two-confirmation gate; dedupe test proves a second identical run issues zero POSTs |
| Question surfacing: answered → decision comment, unanswered → open-question comment | delivered | j2 batches gap questions in one `AskUserQuestion` round with an explicit "no answer — log as open question" option; j3 renders/posts the corresponding comment kinds |
| Explicit confirmation before any `/spec-loop:spec-loop` handoff | delivered | j2 command has neither `Workflow` nor `Edit` in `allowed-tools`; handoff is a printed line only, pinned by doctrine test |
| Standalone usability (refinement/write-back valuable without the loop) | delivered | `/spec-loop:jira-intake` is a complete command independent of any spec-loop run; `--from-plan` handoff is optional/opt-in |
| Never begin implementation without explicit human confirmation | delivered | structural: no `Workflow` tool available to the command at all |
| Durable local artifacts + tests + docs consistent with repo conventions | delivered | artifact under gitignored `.spec-loop-jira/`; stdlib `unittest` tests beside each module; README command-count and doctrine-test updates in j2 |
| Jira write limited to comments only (no transitions/fields/assignees) | delivered | scope-ceiling constraint honored across j1–r1; no mutating verb outside `jira_client.py`'s comment POST |
| Cross-process dedupe safety | partial | per-invocation dedupe only; documented residual (see §3), not built |
| Reading Jira replies back as resolved answers | deferred | explicitly out of scope per `dag.json.scope_ceiling`; needs comment threading and stable question ids |

## 5. Decisions Summary

**Human-answered (4 total, all at Phase 0/1, ~488s median latency).** Jira access mechanism
(stdlib REST + env vars, MCP rejected as unauthenticated/invisible to CI); write-path safety
(render, confirm, then post; paginated marker dedupe, local cache never the gate); card-data
residency (untracked, gitignored `.spec-loop-jira/` root, since the repo's remote is public);
breakdown granularity (refined request file + printed handoff only, no second decomposer, so
intake structurally cannot start the loop). All four resolved a council OBJECT/safety flag from
plan-critic, guardian, or skeptic.

**Controller-resolved autonomously (9 further "ANSWERED" escalations in `escalations.md`, plus
material decisions in `decisions-log.md`; `metrics.json` puts the run's overall autonomy ratio at
0.88).** Quality-gate residuals were accepted by direct precedent citation on all four slices
(run 20260825-scope-ceiling s1's "ACCEPT AS PRE-EXISTING DEBT, no threshold weakened," re-applied
across runs 20260826/27/28/0904 and again here) — each time the controller re-measured the gate
itself at the slice base rather than trusting either the wave's report or the sidecar's own
(repeatedly stale — see Executive Readout) quality block, and confirmed zero unforced
function-level violations before accepting. j1's third quality-gate escalation was closed
directly by the controller (measuring the suite first-hand and writing the DONE sidecar) rather
than re-dispatched a fourth time, because the wave's verify stage was proven non-terminating on
already-accepted residuals (dispatch 3 returned the same head with no new commit after 221k
tokens). j2's "already implemented" ambiguity escalation was answered by sending a narrow
residual-gap fix list rather than accepting the built code as final or authorizing a rewrite. j3's
in-batch duplicate-marker finding was promoted to BLOCKING after the controller reproduced an
actual double-post through the real callables with a stubbed transport. j3's and r1's
`StructuredOutput` retry-cap crashes were both answered "retry, scoped to the one remaining
defect" (j3) or "closed, no retry needed" (r1) after the controller independently confirmed the
already-committed work was sound. The stray primary-checkout edits blocking the j2 merge were
discarded only after the controller verified the j2 branch already carried the same, better
line-wrapped content. Remediation slice r1 was created from the Phase 5 cross-slice review
findings — two of its three findings were reproduced first-hand — rather than accepting the
review's text as-is.

## 6. Integration Gate Result

Per-wave: each of j1/j2/j3/r1 merged as the sole slice in its wave, and the controller applied
"tree-identity evidence transfer" — the integration branch's tree sha equalled that slice's
sidecar `tests.tree_sha`, so the controller-measured full-suite evidence transferred without a
re-run (`integration-check` events at `03:11:38Z`, `05:20:20Z`, `07:35:59Z`, `08:10:09Z`, all
`result: "green"`).

Phase 5 (full-branch check, before remediation): all seven CI segments run first-hand on
`spec-loop-run/20260908-jira-intake` at `b875740` — marketplace OK; `scripts/` 126 OK;
`plugins/spec-loop/scripts/` 1739 OK (baseline 1479, +260); coverage PASS, TOTAL 97.1%
(7108/7319) vs a 90% floor, `jira_client.py` 99.6% vs 94, `jira_intake.py` 96.2% vs 91; Node
`slice_wave` 98/98; Node `dashboard_assets` 48/48; `claude plugin validate` passed for both the
marketplace root and `plugins/spec-loop/` (`integration-check` event, `07:37:31Z`, `result:
"green"`).

Cross-slice review after that green state surfaced three findings; the controller reproduced two
of them first-hand (the `_http_get` OSError asymmetry and the `validate_issue_key` message citing
an example its own regex rejects) and folded a third (a stale hand-maintained test-comment count)
in alongside them, all as remediation slice r1 rather than accepting any of the three. This
review's own verdict/tier is not separately recorded as an event distinct from the resulting
`decision` payload.

Final state after r1 merged (r1 sidecar, `tests` field, controller-measured at `f441f7e`):
marketplace OK; 126 dev tests; 1741 plugin tests; coverage PASS, TOTAL 97.1% (7110/7321) vs 90%,
`jira_client.py` 99.6% (467/469) vs 94, `jira_intake.py` 96.2% vs 91; Node `slice_wave` 98/98;
Node `dashboard_assets` 48/48. Integration gate: **green-after-remediation**.

## 7. How to Verify & Operate

Per-slice suite command (identical across j1–r1, run as separate invocations from the repo root):

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'
python3 scripts/measure_coverage.py
node --test --experimental-test-coverage plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs plugins/spec-loop/scripts/slice_wave_radius.test.mjs plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs plugins/spec-loop/scripts/slice_wave_replan.test.mjs
```

Phase 5 / CI adds a seventh segment not run by the slice-level command above:

```
claude plugin validate .
claude plugin validate plugins/spec-loop/
```

(`.github/workflows/validate.yml`, ubuntu-latest, Python 3.12 + Node 20, per `conventions.md`.)

**New CI gate this run introduced:** `jira_client.py` and `jira_intake.py` are now registered in
both `TARGET_FILES` and `PER_FILE_FLOORS` in `scripts/measure_coverage.py`, at 94%/91%
respectively (each set at its locally-measured coverage minus a ≥5-point margin, per this repo's
existing convention). No threshold was weakened and nothing was added to `coverage_omit.txt` to
land this run — the quality-gate residuals described in §3/§6 were accepted as pre-existing
debt under established precedent, not exempted.

**To operate the feature:**

```
export JIRA_BASE_URL=https://<your-site>.atlassian.net
export JIRA_EMAIL=<you>@<domain>
export JIRA_API_TOKEN=<token>
/spec-loop:jira-intake ABC-123
```

This reads the card read-only, writes a refined-understanding artifact to
`.spec-loop-jira/ABC-123/intake.md` (gitignored), asks any open gaps in one batched question
round, and previews the comments it would post. Posting requires a separate explicit confirmation
plus the command's `--post` step — nothing is written to the card by default. The command never
invokes `/spec-loop:spec-loop` itself; it only prints the `--from-plan <path>` line for the human
to run.

**Cost of this run, for the record:** 4 slices, 150 agent-dispatch events, 11 wave dispatches
(11 `plan`-role agent-dispatch events; only 6 of these produced a top-level `wave-dispatched`
event, since a same-workflow quality-gate resume does not re-emit one) and 130 agents summed
across the run's 9 `wave-collected` events. Recorded subagent-token total
(`metrics.json.tokens.wave_totals.total`) is **6,033,969**, with `waves_reporting` now 9 of 9.

That total was incomplete when this runbook was first drafted: wave 4 (r1)'s `wave-collected`
event was never appended by the controller at collection time, so its 417,903 subagent tokens
(13 agents, 1,188,910 ms) were absent from the artifacts and the run's measurable cost then read
as 5,616,066 across 8 of 9 waves. The controller appended the missing event during Phase 5, using
the completion notification's own recorded values rather than a reconstruction, once an earlier
draft of this runbook flagged the gap instead of estimating past it; `events.jsonl` now carries
that append with a note naming what happened and why. The total above is complete. Keep the fact
that one wave's aggregate reached the artifacts later than the others as a run-state-discipline
note in its own right, separate from the run's feature work — a real instance of the controller's
own bookkeeping slipping, caught only because the runbook refused to round an unverifiable number
up to close the gap.

A material share of the token spend that *is* fully accounted for went to the loop defects named
in the Executive Readout's "Gaps you should know about" (stale sidecar quality blocks the
controller had to re-measure and override six times by its own count; a stale `review.residual`
cache replayed across j1's three dispatches; a non-terminating verify loop on already-accepted
residuals that cost j1 a third dispatch and 221k tokens for no new commit; a resume-after-fix
defect that cost j2 a zero-task dispatch) rather than to the delivered feature work itself. Full
metrics: `docs/spec-loop/20260908-jira-intake/metrics.json`.
