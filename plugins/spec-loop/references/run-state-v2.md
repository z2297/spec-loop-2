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
  "id": "s1:review-block",     // "<slice-id>:<trigger>", plus ":<round>" from the second
                                // round of that trigger in that slice onward (escId).
                                // Stable across resumes: the round counts the answers
                                // already recorded for the slice+trigger, so the same
                                // answers map reproduces the same id. Answers are keyed
                                // by this id verbatim; latestAnswer reads the newest
                                // answered round back into the resumed prompts.
  "trigger": "ambiguity | material-assumption | review-block | council-objection | quality-gate-block | refactor-scope | budget-exhausted | internal-error",
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

`budget-exhausted` is raised only by the loop's two structural guards (agent cap, stage
token floor). It stays a resource request rather than a judgment — no prompt ever receives
its answer — and only the agent-cap half is answerable mechanically: the controller supplies
`agent_cap_overrides` on the one re-dispatch the human authorised, and the stage token floor
has no such field. `internal-error` covers the two machine-failure shapes the loop actually
produces — an unhandled exception that aborted a slice, and a slice that returned no result
at all — either of which may itself have a host- or agent-layer cause (e.g. a rejected agent
call on a hard token or rate limit) that the record does not pretend to rule out. It is not
a catch-all for every other failure: a failure the loop can name keeps the trigger that
names it, so a spent replan stays `council-objection` and a blocked task — including a task
dispatch that returned no result — stays `ambiguity`. Neither is a judgment trigger.

`refactor-scope` is the one trigger the workflow raises on its own arithmetic rather than on
an agent's judgment: at plan time, when the plan's declared refactor-to-feature ratio exceeds
the configured threshold. It IS a judgment trigger — its answer is injected back into the
plan prompt — because the only useful answer is a human trade-off between shipping the
refactor with the feature and splitting it out. An absent or unmeasured ratio never raises
it: not-measured proceeds and is recorded as null.

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
`agent-dispatch`, `phase5-gate`, `publish-choice`, `agent-cap-override`,
`refactor-radius`.

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
- **`agent-cap-override`** payload: `{tier, default_cap, effective_cap}` — emitted by
  the wave at slice start, once per dispatch, only after a human-authorised raise has
  actually taken effect. `default_cap` is the review tier's own cap and `effective_cap`
  is the raised number the guard enforces; the pair makes the exception auditable rather
  than inferable from a larger `agents_used`. The raise arrives as the wave arg
  `agent_cap_overrides` (`{"<slice-id>": <integer>}`), belongs to the single dispatch the
  controller hands it to, and can only raise: a value at or below the tier default is
  discarded. `tier` is the review tier at slice start, which a later tier promotion can
  move. A supplied override that does NOT take effect emits no `agent-cap-override` event: a
  value at or below the tier default, or a value that does not read as a whole number, is
  announced once at slice start as a `decision` event whose summary opens `agent cap
  override`, and override keys matching no slice of the dispatched wave are announced the
  same way on the wave's first slice. The value is coerced with `Number()`, so a JSON string
  reading as a whole number — `"14"` — is read as the integer 14 and judged against the tier
  default like any other value.
  The discard is therefore visible without waiting on a second cap record.
- **`refactor-radius`** payload: `{summary, state, exceeded[], measured{rewrite_ratio,
  touched_existing_files, rewritten_lines}, thresholds{enabled, max_rewrite_ratio,
  max_touched_existing_files, min_rewritten_lines}|null, basis, compared[], skipped[]}`, plus
  `suppressed_by_answer: true`
  when — and only when — the state is `EXCEEDED` and a truthy human answer to this slice's
  `refactor-scope` escalation kept it from halting; the key is absent, never `false`, in every
  other case, so counting it counts real waived halts. Emitted by
  the wave's PLAN stage on EVERY evaluation — `state` is one of `NOT_CONFIGURED`,
  `DISABLED`, `NO_USABLE_CEILING`, `NOT_MEASURED`, `WITHIN`, `WITHIN_PARTIAL`, `BELOW_FLOOR`,
  `EXCEEDED`, and only `EXCEEDED` halts. The no-fire cases are emitted precisely because a ceiling that silently declines
  to fire is invisible narrowing: `measured` and `thresholds` are both present in every
  state so a reader never re-derives why nothing happened. `measured` is null-honest —
  an undeclared number is `null`, never `0`, and `0` is a real measurement. The numbers
  are planner-DECLARED: a proxy declared before implementation, not a measured diff, so
  they cannot catch a blowup discovered mid-implementation, and no second,
  post-implementation checkpoint exists. `thresholds` is `null` only when
  `ctx.refactor_radius` was absent or unusable.
  `basis` is the planner's own one-sentence account of how it counted, or `null` when it
  stated none: it is DISPLAY-ONLY — carried so a human weighing the trade-off can see how
  the number was reached — and no state, threshold or comparison reads it.
  `NO_USABLE_CEILING` means the block was present and enabled but neither `max_rewrite_ratio`
  nor `max_touched_existing_files` survived as a number — a mistyped ceiling. It fails open
  like the other no-fire states, and it is separate from `WITHIN` because a plan cannot be
  "under a ceiling" that was never compared.
  `compared[]` and `skipped[]` name, per dimension, which DECLARED maxima numbers
  (`rewrite_ratio`, `touched_existing_files`) were actually judged against a usable ceiling and
  which were not; a number the plan never declared appears in neither. `WITHIN_PARTIAL` is
  `NO_USABLE_CEILING`'s per-dimension twin: the block was usable overall — one ceiling survived —
  but at least one declared number had no ceiling of its own, so nothing compared was over and
  `WITHIN` would have claimed a comparison that never ran. It fails open exactly like `WITHIN`:
  an unusable ceiling never causes a halt, it only stops the record claiming a comparison it did
  not make. HONEST LIMIT: this says which numbers were compared, not whether the declared
  numbers were true — they remain planner declarations, and no measured diff is taken anywhere.
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
  key: `over_scope: true` (a bare boolean). This is MEMBER-level attribution, NOT a
  per-concern judgement: it marks that the council member who raised this concern
  separately flagged the WHOLE PLAN as over-scope, not that this specific concern is
  itself out of scope. A member who flags the plan over-scope while separately
  raising an unrelated `disposition_hint: 'defer'` concern causes that unrelated
  concern to carry the same marker too — there is no per-concern `over_scope` field
  in the council schema to attribute it more precisely. The wave emits ONE such
  event per `defer`-hinted council concern, ONLY on the path where the plan
  proceeds to execution — a SPLIT return discards the plan and re-critiques per
  child, and an unresolved OBJECT escalation means the plan never ran, so either
  case emits ZERO deferred events for that batch — payload `{summary, source:
  "plan-critique"}` plus the marker when it applies — `summary` is read first by the
  decisions-log renderer, so the line is legible prose rather than a JSON blob.
  Advisory prose data only: it suppresses no finding, filters no blocking set, and
  drops no work. The controller also emits `deferred` at intake, and
  `council-verdict.deferred[]` remains the machine channel `run_metrics.concerns_deferred`
  counts.
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

## Markers — guard-hook contract (v1's three, plus two added in v2)

- `.active` — created at Phase 1, recreated on resume. While present,
  `spec_loop_guard.py` blocks pushes, broad staging, main-branch
  commits/merges, and quality-gate config writes.
- `.publish-choice` — written the instant the human answers the publish
  prompt, before the action is performed.
- `.done` — `.active` renamed at run end.
- `.paused` — present only while the human has deliberately suspended the
  loop-boundary gate. It relaxes that one gate and nothing else; every
  `.active` restriction above still applies.
- `.controller-session` — identifies the controller's own session so the
  loop-boundary gate applies to it and not to other sessions. Per-session
  state, meaningful only inside the machine that wrote it. It discriminates
  across SESSIONS and nothing finer: a `Task` subagent inherits its parent's
  `CLAUDE_CODE_SESSION_ID`, so the marker would MATCH at a subagent's turn
  end and the gate would tell an implementer to continue Phase 2 step 1.
  Whether `Stop` fires at a subagent's turn end is untested, and
  `SubagentStop` being a distinct, unregistered event is not evidence
  either way. See `references/platform-probes.md`.

None of these markers is ever committed. They are per-checkout state: the
hooks fire on a marker's PRESENCE, so a committed `.active` would deny pushes
and main-branch commits on every clone and in every fresh worktree, including
sessions with no run at all. In the spec-loop repository itself, `.gitignore`
enforces this with one bare, unanchored entry per marker name and
`test_doctrine_marker_hygiene.py` fails if one re-enters the index. Neither
exists in a repo the plugin is merely installed into: there, a `.paused` or
`.active` is fully committable and nothing will stop it, so adding those five
ignore entries is the installing repo's job. Markers did get committed twice
in this repository before that pin existed; the correction is an
index-only removal (`git rm --cached`) that leaves the files on disk for any
run still reading them — never a history rewrite, and never a plain delete.

A hook denial means the run has not earned that operation yet — never delete
a marker to dodge one. A stale marker is remediated by resuming the run or
clearing the marker, in that order; that applies to a stale `.paused` exactly
as it does to a stale `.active`.

Accepted residual risk: `.paused` disables the loop-boundary gate with ZERO
observable trace. A `Stop` hook can only block or stay silent, so a paused
gate never fires and therefore never gets the chance to explain that it is
paused. A `.paused` left behind after the reason for it passed is a
permanent, silent loss of the loop-boundary gate for that run — detectable
only by a human who remembers the marker exists. This is accepted, not
mitigated.

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
