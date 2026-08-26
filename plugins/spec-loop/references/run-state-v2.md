# Run state v2 — the on-disk contract

Single home of the durable run-state contract. Everything lives under
`docs/spec-loop/<run-id>/` in the operated repo. Scripts (`dag.py`,
`run_state.py`, `run_metrics.py`, `dashboard_server.py`), the wave workflow,
and the controller all read/write exactly these shapes; when this file and
code disagree, fix one of them in the same change.

Design rules carried from v1: the controller owns every write to `dag.json`;
readers tolerate a half-written file (report the run as momentarily
unreadable, never crash or invent); prose files are generated from structured
objects and are never machine-load-bearing; metrics are null-honest.

## `dag.json` — sole authority on run structure

```jsonc
{
  "schema_version": 2,
  "run_id": "20260730-example",
  "base_ref": "<integration branch name>",
  "base_sha": "<sha at its creation point>",
  "base_branch": "<branch it was cut from>",
  "merge_mode": "single-branch | per-slice-pr",
  "mode": "workflow | inline",              // inline = slice-worker-fallback path
  "created_at": "<ISO-8601 UTC>",
  "shared_constraints": ["<run-wide must-not-regress constraints; [] if none>"],
  "scope_ceiling": ["<things this run must not build; OPTIONAL, may be absent>"],
  "slices": [{
    "id": "s1",
    "goal": "<one shippable change>",
    "files": ["..."], "subsystems": ["..."],
    "deps": ["<slice ids>"],
    "risk_tier": 1,            // 1|2|3; --risk-floor is the minimum
    "depth": 0,                // split generation; intake slices = 0, cap 2
    "parent": null,            // split children point at their parent id
    "status": "pending",       // pending | complete | split (split is terminal)
    "remediation": true        // present only on Phase-5 remediation slices
  }],
  "waves": [{
    "index": 1,                            // 1-based
    "slice_ids": ["s1", "s2"],
    "workflow_run_id": "wf_abc123",        // null in inline mode
    "status": "dispatched | collected"
  }]
}
```

Wave *membership* is computed, never guessed: the next wave = every `pending`
slice whose `deps` are all `complete` (a `split` parent is terminal — never
schedules, never blocks). `dag.py next-wave` is the one implementation;
nothing else re-derives it. The `waves[]` array records what was actually
dispatched (the durable pointer from run state to workflow journals), not a
prediction. Split children use ids `<parent>.1`, `<parent>.2`, …, with
`depth = parent.depth + 1`.

`scope_ceiling` is **optional**: `dag.py validate_dag` checks it only when
the key is present (a list of non-empty strings), and a `dag.json` without
it is fully valid and fully mutable. That is deliberate asymmetry — the
neighbouring run-level keys (`run_id`, `base_ref`, `merge_mode`,
`shared_constraints`, …) are not validated at all, and making any run-level
key required would make every pre-existing run un-resumable, because
`_load_for_mutation` refuses to mutate a contract-invalid dag.

## `slice-<id>-status.json` — per-slice sidecar

Persisted by the controller (via `run_state.py persist-slice`) from the
tool-validated SliceResult a wave workflow returns. Authoritative over any
prose about the slice.

```jsonc
{
  "schema_version": 2,
  "id": "s1",
  "status": "DONE | SPLIT | ESCALATED | FAILED",
  "branch": "spec-loop/<run-id>/s1",
  "commits": { "base": "<sha>", "head": "<sha>" },   // null head if nothing committed
  "risk_tier": 2,
  "review_tier": 2,             // may exceed risk_tier via surface auto-promotion
  "critique": { "verdict": "ENDORSE | ENDORSE_WITH_CONCERNS | OBJECT | SKIPPED", "concerns": 2,
                "over_scope": { "flag": false, "reason": null } },  // OPTIONAL; absent ≠ flag:false
  "tasks_completed": 4,
  "review": { "confirmed": 1, "refuted": 2, "evidence_failed": 0,
              "fix_rounds": 1, "residual": ["P2: ..."] },
  "tests": { "command": "...", "result": "...", "scope": "full", "tree_sha": "<sha>" },
  "quality": { "status": "PASS | FAIL | SKIPPED", "detail": "..." },
  "split": { "children": [{ "goal": "...", "files": [], "subsystems": [],
                            "internal_deps": [] }] },   // SPLIT only; ≥2 children (a 1-child
                                                        // split is not a split); 1-based sibling indices
  "escalations": [ /* EscalationRecord, below */ ],      // ESCALATED only
  "agents_used": 12,
  "wave": 1,
  "started_at": "<ISO-8601 UTC>", "finished_at": "<ISO-8601 UTC>"
}
```

## `EscalationRecord` (embedded in sidecars; rendered into `escalations.md`)

```jsonc
{
  "id": "s1:review-block",     // "<slice-id>:<trigger>[:<round>]" — stable across resumes
  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | budget-exhausted",
  "title": "<short title>",
  "context": "<what the loop was doing and why it cannot decide>",
  "question": "<the precise question>",
  "options": [{ "label": "...", "detail": "...", "recommended": true }],
  "if_unanswered": "pause this slice; continue all independent slices",
  "status": "OPEN | ANSWERED",
  "opened": "<ISO-8601 UTC>",
  "answer": null, "answered_at": null
}
```

## `events.jsonl` — the machine channel

Append-only, one JSON object per line, written only by the controller
(`run_state.py` appends; workflow returns carry the payloads; the controller
stamps `ts` — workflow scripts have no clock).

```jsonc
{ "ts": "<ISO-8601 UTC>", "scope": "<slice-id | intake | wave<N> | phase5 | run>",
  "type": "<event type>", "payload": { } }
```

Event types (extensible; consumers ignore unknown types): `run-created`,
`baseline`, `council-verdict`, `decision`, `deferred`, `escalation-opened`,
`escalation-answered`, `wave-dispatched`, `wave-collected`, `slice-merged`,
`integration-check`, `split-ingested`, `quality-gate`, `review-summary`,
`agent-dispatch`, `phase5-gate`, `publish-choice`.

Pinned payload facts (consumers rely on these; everything else is
best-effort):

- **`ts` is a collection stamp, not a duration source.** The controller
  appends a wave's events in one batch at collection, so their `ts` values
  cluster — deriving durations or interval unions from `ts` is forbidden.
- **`agent-dispatch`** payload: `{role, model, effort, agent_type}` from the
  workflow, plus `dispatched_at`/`returned_at`/`tokens_in`/`tokens_out` when a
  future harness exposes per-dispatch identity — all optional and null-honest.
  (Verified 2026-07-30: workflow journal keys are opaque digests, so
  per-dispatch timing/tokens are NOT extractable today.) `engine_active_s`
  derives ONLY from `dispatched_at`/`returned_at` pairs; when absent it is
  `null`, never a `ts`-based guess.
- **`wave-collected`** payload carries the per-wave aggregates the workflow
  completion notification reports: `{index, agent_count, subagent_tokens,
  duration_ms}` — the honest wave-level token/duration channel while
  per-dispatch stamps are unavailable. Optional, null-honest.
- **`council-verdict`** payload carries `safety: bool` — whether the verdict
  involved a SAFETY flag (the one objection that halts alone) — and the
  OPTIONAL `over_scope: {flag: bool, reason: string|null}` record. `over_scope`
  keeps BOTH halves: unlike `safety`, whose reason is dropped at the source, the
  reason is durable here. It is **record-only**: no verdict, gate, veto or
  blocking decision reads it, and it is never a finding. Absent means no scope
  judgement was recorded and is NOT equivalent to `flag: false`; both render
  distinctly in `decisions-log.md` (`scope: clean` vs nothing at all).
- **`deferred`** payload is null-honest and otherwise free-form, with one pinned
  key: `over_scope: true` (a bare boolean) marks a deferral of work judged outside
  the slice's scope. The wave emits ONE such event per `defer`-hinted council
  concern, payload `{summary, source: "plan-critique"}` plus the marker when it
  applies — `summary` is read first by the decisions-log renderer, so the line is
  legible prose rather than a JSON blob. Advisory prose data only: it suppresses no
  finding, filters no blocking set, and drops no work. The controller also emits
  `deferred` at intake, and `council-verdict.deferred[]` remains the machine channel
  `run_metrics.concerns_deferred` counts.
- **`escalation-opened`** payload is the full EscalationRecord, including its
  `id`; `escalation-answered` pairs by that `id` (never by scope alone — one
  slice can open several).

`run_metrics.py` reads events.jsonl as its primary channel. `decisions-log.md`
and `escalations.md` are rendered from the same objects for humans; they have
no pinned machine grammar in v2.

## Prose artifacts

| File | Written by | Notes |
|---|---|---|
| `request.md` | controller | verbatim request (or plan content + `Source:` line) |
| `conventions.md` | controller | Phase-0 exploration summary; read by every agent packet |
| `decisions-log.md` | controller | human-readable render of `decision`/`deferred`/gate events, append-only |
| `escalations.md` | controller | render of EscalationRecords, answers written back |
| `plans/<slice-id>.md` | slice-planner agent | the slice plan, written from inside the worktree to this absolute path |
| `review-<slice-id>-round<N>.md` | pr-reviewer agent | findings prose (the structured findings live in the workflow return) |
| `slice-<id>-report.md` | controller | short human summary rendered from the sidecar |
| `runbook.md` | runbook-writer agent | end-of-run synthesis, committed |
| `metrics.json` | `run_metrics.py --write` | atomic write |

## Markers — guard-hook contract (unchanged from v1)

- `.active` — created at Phase 1, recreated on resume, never committed. While
  present, `spec_loop_guard.py` blocks pushes, broad staging, main-branch
  commits/merges, and quality-gate config writes.
- `.publish-choice` — written the instant the human answers the publish
  prompt, before the action is performed.
- `.done` — `.active` renamed at run end.

A hook denial means the run has not earned that operation yet — never delete
a marker to dodge one.

## Worktrees & branches

- Worktree: `.worktrees/spec-loop/<run-id>/<slice-id>` (gitignored).
- Branch: `spec-loop/<run-id>/<slice-id>`, cut from the current tip of
  `base_ref` by `worktrees.py prepare` before the wave is dispatched.
- Resume re-attaches the existing branch at its head (`prepare --resume`,
  never `-b`).
- The controller merges each verified DONE slice serially
  (`git merge --no-ff`) on `base_ref`, then removes the worktree and deletes
  the branch. Conflict = integration failure → remediation slice, branch kept.

## Config files (global, outside the repo)

- `~/.claude/spec-loop-2/quality-gate.json` — thresholds, `refactor_attempts`,
  `custom_gates`, plus v2 additions `tier3_surfaces` (glob list) and
  `models` (role→model promotion overrides).
- `.spec-loop/quality-gate.json` (per-repo, committed) — deep-merged overlay;
  may tighten thresholds and extend `tier3_surfaces`; both paths are
  guard-protected while a run is `.active`.
- `~/.claude/spec-loop-2/knowledge-graph.json` — same schema as v1; same
  vault `subfolder` default (`spec-loop`) so v2 runs accrete onto v1 nodes.
