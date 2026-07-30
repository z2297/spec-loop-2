---
description: "Render a read-only terminal-markdown dashboard of a spec-loop run (recorded waves, slice status from the sidecars, escalations, council verdicts, metrics) from its durable artifacts under docs/spec-loop/<run-id>/"
argument-hint: "[run-id]"
allowed-tools: ["Bash", "Glob", "Grep", "Read"]
---

# Spec-Loop Dashboard — read-only run view

Render a human-readable snapshot of a `/spec-loop` run from the durable artifacts under
`docs/spec-loop/<run-id>/`, answering "where is this run, and what can run next?" between
waves or after a pause.

This command is **strictly read-only**: it writes no file, creates no cache, and triggers,
resumes, or mutates no slice work. Read artifacts through `Read`, `Glob`, and `Grep`; `Bash`
is for read-only inspection only (listing directories, reading mtimes), never to write, move,
or delete, and never with the `<run-id>` — or anything derived from it — interpolated into a
command string. There is no `Write`, `Edit`, `Task`, or `AskUserQuestion` here; the authored
frontmatter is what enforces that, since the CI gate only checks `description`.

The run-state contract (dag.json, sidecars, events, marker lifecycle) is pinned in
`${CLAUDE_PLUGIN_ROOT}/references/run-state-v2.md` — read it first.

## Steps

1. **Select the run (path-traversal-safe).** The `<run-id>` argument is optional.
   - `Glob` `docs/spec-loop/*/dag.json` and take each match's parent directory name as the
     set of known run-ids. Resolve a supplied `<run-id>` **only** by exact-equality match
     against that set — never build a path from the raw argument. That is the path-traversal
     guard: `../../etc` can never match an enumerated basename.
   - No match → print `no spec-loop run matching <run-id>` and stop. Do not fall back to the
     newest run; that would misrepresent which run is shown.
   - Omitted → default to the run whose `dag.json` has the newest mtime. Run-ids are
     `<date>-<slug>` with `-2`/`-3` duplicate suffixes and do not sort chronologically, so
     never rely on glob order or lexical sort.
   - No runs at all → print `no spec-loop runs found` and stop. Normal output, not an error.

2. **Read the artifacts.** Three carry the truth: `dag.json` is the authority on run structure
   (slice ids, `deps`, `depth`, `parent`, `status`, and the recorded `waves[]`);
   `slice-<id>-status.json` — the per-slice sidecar, `schema_version: 2` — is authoritative on
   what a slice's last wave returned; `events.jsonl` is the machine channel for escalations,
   council verdicts, and decisions. Then, all optional: `request.md` (a short excerpt for
   context), `escalations.md`, `decisions-log.md`, `plans/<slice-id>.md`,
   `slice-<id>-report.md`, `review-<slice-id>-round<N>.md`, `metrics.json`, and — only after
   Phase 5 — `runbook.md`, whose front-matter carries `integration_gate`, `slice_counts`,
   `gap_counts`, `publish` and whose `## Executive Readout` is self-contained. Ignore a
   sidecar whose `schema_version` is not `2`, and ignore `packages/` (reviewer input, not run
   state).

3. **Waves are read, not guessed.** `dag.json`'s `waves[]` records what the controller
   actually dispatched — `index` (1-based), `slice_ids`, `workflow_run_id` (the workflow
   journal pointer; `null` in inline mode), `status` `dispatched | collected`. Report those
   verbatim, then **derive** waves only for pending slices in no recorded wave, by the
   `next-wave` rule in `references/run-state-v2.md`: a wave is every pending slice whose
   `deps` are all satisfied, where satisfied means `complete` **or** `split` (a `split` parent
   is terminal — never schedules, never blocks). Label those **projected**: they forecast the
   remaining plan, not history. Split children use ids `<parent-id>.1`, `<parent-id>.2`, …
   with `depth = parent.depth + 1`, and are real slices in `dag.json` once `dag.py
   ingest-split` grafts them; before that they exist only as a `split.children` proposal in
   the parent's sidecar — a footnote at most ("parent proposed N children, not yet grafted"),
   never DAG structure.

4. **Label each slice with an honest, derived status**, matching
   `scripts/dashboard_server.py::_derive_label_v2` exactly, in precedence order. These are
   cold artifacts, so **never claim a slice is "running now"** — nothing on disk can tell you
   that.
   - **complete** / **split** — `dag.json` says so; terminal, and it outranks any sidecar.
   - **failed** — sidecar `status: FAILED`.
   - **merge-pending** — sidecar `DONE`, not yet complete in `dag.json`: finished, awaiting
     the controller's serial merge. **split-pending** — sidecar `SPLIT` awaiting ingestion.
     Calling either "runnable" would be a live claim this command cannot make.
   - **awaiting-human** — an OPEN escalation for this slice (Step 5), or sidecar `ESCALATED`
     with no record resolving it either way.
   - **redispatch-pending** — an ANSWERED escalation: the human has unblocked it and it awaits
     re-dispatch. Keeping this distinct from awaiting-human is what stops the rollup showing a
     human blocking an already-unblocked run.
   - **runnable-pending** / **blocked-pending** — pending, no escalation, deps satisfied or not.

5. **Read escalations from the strongest available source**, mirroring the server: the
   `EscalationRecord`s embedded in the sidecars supply ids, titles, and triggers;
   `events.jsonl` then overrides status — an `escalation-opened` with no later
   `escalation-answered` for the same id is OPEN, and since the log is append-only and
   ordered, the **last** transition for an id wins. With neither sidecar records nor an events
   log, fall back to scraping `escalations.md` markers (`(status: OPEN)` with an empty
   `Answer:` line). An escalation id is `<slice-id>:<trigger>[:<round>]`, so its slice is the
   part before the first colon; the scope may also be **`intake`**, which joins to no slice
   row — render it in the escalations block regardless. Say which source you read.

6. **Derive the run's stage** from cold artifacts, matching
   `scripts/dashboard_server.py::_derive_stage` exactly; furthest-progressed wins:
   **final-review** (every slice terminal) · **execution** (work started — any slice terminal,
   any `slice-<id>-report.md`, any persisted sidecar, any recorded wave — but not all
   terminal) · **iron-council** (`dag.json` has slices, no slice work started; in v2 this is
   the intake-challenge window, but keep the server's name) · **preflight** (nothing
   decomposed; a run isn't listed until `dag.json` exists, so essentially never seen here).
   The stage is an honest artifact signal, never a claim that anything is executing now.

7. **Council verdicts and the runbook.** Read `council-verdict` events: the scope is the
   event's own `scope` field (a slice id or `intake`), the verdict is `payload.verdict`
   (`ENDORSE` / `ENDORSE_WITH_CONCERNS` / `OBJECT`) — intake verdicts vet the request,
   per-slice verdicts vet that slice's plan. With no events log, fall back to scraping
   `decisions-log.md` for `[<scope>] COUNCIL…` lines; v2 pins no machine grammar on the prose
   files, so treat that as best-effort. If `runbook.md` exists, take its front-matter and its
   `## Executive Readout` verbatim up to the next `## ` heading.

8. **Render the dashboard (terminal markdown), in order:**
   - **Header** — run-id, `base_ref@base_sha`, `merge_mode`, `mode` (`workflow`/`inline`),
     derived stage, one-line `request.md` excerpt.
   - **Council verdicts** — Step 7's entries as `[scope] VERDICT — summary`, or "no council
     verdicts recorded".
   - **Waves** — recorded first (`Wave 1 (collected, wf_abc123)`), then projected, each with
     its slices and their Step 4 labels.
   - **Slice table** — id, goal (truncated), risk tier, depth, parent, deps, derived status,
     and from the sidecar: `review_tier` (flag it when it exceeds `risk_tier` — surface
     auto-promotion), critique verdict, review counts (`confirmed`/`refuted`/`fix_rounds`),
     quality-gate status, `agents_used`, wave, plus ✓ for plan / report presence.
   - **Status rollup** — counts by derived status, plus explicit lists of which slices are
     runnable now, awaiting-human, and failed.
   - **Final review — Executive Readout** — `runbook.md`'s front-matter chips and readout when
     it exists; otherwise "run not finished — no runbook yet".
   - **Run metrics** — from `metrics.json`: escalations, autonomy ratio, council OBJECT rate,
     quality-gate first-pass rate, refuted rate, split rate, integration gate, wall clock /
     engine-active / human-wait, tokens — rendering `null` as `—` (metrics are null-honest; a
     `—` means unmeasured, never zero). Absent or malformed, print
     `no metrics computed — run: python3 ${CLAUDE_PLUGIN_ROOT}/scripts/run_metrics.py compute docs/spec-loop/<run-id> --write`
     rather than computing them here: this command may not write, and the run-id must never
     reach a Bash string.
   - **Escalations** — every entry with its OPEN/ANSWERED status and trigger, intake-scoped
     included. Always shown.
   - **Recent decisions** — the tail of `decisions-log.md`.

9. **Robustness (never invent or crash).** `dag.json` is rewritten in place at wave boundaries
   with no atomic-write discipline, so a read can catch it half-written. If it fails to parse,
   print `run in progress — state momentarily unreadable` and stop rather than erroring or
   inventing slice state. Skip an unparseable `events.jsonl` line or malformed sidecar with a
   note; treat any missing optional artifact as simply absent and render the rest.

## Notes

- **v1 run dirs still render, by legacy rules.** A `dag.json` with no `schema_version` is a v1
  run: no recorded waves, no sidecars, no events log. Derive every wave, use v1's six labels
  (`complete`, `split`, `awaiting-human`, `redispatch-pending`, `runnable-pending`,
  `blocked-pending`), read escalations and council verdicts from the prose files, and say which
  generation you rendered. One v1 trap is gone in v2: plans are durable now
  (`plans/<slice-id>.md` in the run dir), where a v1 plan lived in the worktree and vanished on
  merge — for a v1 run surface `slice-<id>-report.md` and never claim to show a plan you cannot
  read.
- **Non-goals.** No live-watch or auto-refresh, no TUI, no web server, no HTML artifact (that
  is `/spec-loop:dashboard-serve`), no writes, no slice work triggered or resumed.
- **Read-only contract.** `allowed-tools` stays `Bash`/`Glob`/`Grep`/`Read` — that set is the
  security boundary.
