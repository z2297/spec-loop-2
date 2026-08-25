# conventions.md — run 20260825-scope-ceiling

Repo: `spec-loop-2` — the source of the spec-loop 2 Claude Code plugin. This run modifies the
plugin's own contracts. Read this file before planning or implementing; it replaces
re-exploration.

## CRITICAL — this run's machinery is NOT the code it edits

The loop executing this run resolves its agents, workflow, and scripts from the **installed
plugin cache** (`~/.claude/plugins/cache/spec-loop/spec-loop/2.0.0/`), not from this repo.
Edits here take effect only after a plugin reinstall. Consequence: **no new mechanism added by
this run is exercised by this run.** Prove everything with unit tests and contract checks;
never with "the loop used it".

## Test / build command (6 segments, CI-mirrored, ~50s total)

```
python3 scripts/validate_marketplace.py . ; python3 -m unittest discover -s scripts -p 'test_*.py' ; python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py' ; python3 scripts/measure_coverage.py ; node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs ; claude plugin validate .
```

Run each segment as its own tool call, from the repo root. Baseline on this branch is fully
green: 106 + 1017 unittests OK, coverage PASS 96.6% (total floor 90%), 48 Node tests,
validate OK.

## The coverage-floor gate is the tightest constraint in this repo

`scripts/measure_coverage.py` — floors are integer percents in `PER_FILE_FLOORS`
(`measure_coverage.py:125-139`), `TOTAL_FLOOR = 90` (:140). Relevant floors:
`scripts/dag.py: 94` (currently ~99.8%, about 30 untested lines of headroom),
`scripts/run_state.py: 95` (currently ~99.8%, about 25-30 lines of headroom).
`MIN_TESTS = 150` — a collapsed suite fails closed. New script code needs tests in the same
task, or the gate reds.

**`scripts/coverage_omit.txt` line-range trap.** Entries name absolute line ranges of the
`if __name__ == "__main__":` shims and are subtracted from numerator *and* denominator.
`dag.py:676-677` is currently correct; `run_state.py:822-823` is **already stale** (the real
shim is at 837-838). Any edit that shifts line counts in `dag.py` or `run_state.py` requires
re-verifying and correcting that manifest in the same task — the file's own header says so.
Rationale text after `#` is mandatory on every entry or the parser hard-fails.

## Python script conventions (`plugins/spec-loop/scripts/*.py`)

Applies to `dag.py` (677 lines) and `run_state.py` (838 lines) — match them exactly:

- **No type hints. No f-strings** — `%`-style formatting throughout. Stdlib only.
- Long narrative module docstring first (design record + exit-code table + `Usage:` block),
  then constants, then `# ----` banner-comment sections, then the CLI at the bottom.
- Enums are **module-level tuples**, not sets or Enum: `SLICE_STATUSES`, `RISK_TIERS = (1,2,3)`,
  `VERDICTS`, `QUALITY_STATUSES`, `ESCALATION_TRIGGERS`.
- Private helpers are `_`-prefixed and placed **immediately after their public caller**.
- Pure functions are marked `(PURE)` in the docstring summary line.
- Validation returns **all messages at once** as a list; it never raises and never
  short-circuits. Unknown/extra fields are **ignored** — there is no `additionalProperties`
  notion on the python side, so a new field is unvalidated until you add a check for it.
- Exceptions carry the exit-code split: `DagError`/`RunStateError` -> exit 2;
  `ContractError`/`SidecarInvalid` (with `.errors`) -> exit 1, printing
  `{"ok": false, "errors": [...]}` to stdout.
- Atomic writes: `tempfile.mkstemp(dir=same_dir, ...)` + `os.replace`, `finally` unlink.
- argparse: `add_subparsers(dest="command", required=True)`; a local `with_run_dir(parser)`
  closure adds the shared required `--run-dir`; `--file -` means stdin. Status values are
  validated in the pure mutator, not by argparse `choices`.
- `if __name__ == "__main__":  # pragma: no cover`.
- `run_state.py` guards every subcommand with `_require_run_dir` (exit 2 unless
  `<run-dir>/dag.json` exists) and `_require_ts` (permissive ISO-8601 regex).

## Test conventions (`test_dag.py` 115 tests, `test_run_state.py` 160 tests)

- Plain `unittest`, no pytest, no third-party. `python3 -m unittest test_<mod>`.
- `sys.path.insert(0, str(Path(__file__).resolve().parent))` then
  `import dag as dagmod  # noqa: E402` / `import run_state as rs  # noqa: E402`.
- Module-level **factory helpers** with a `**over` kwargs escape hatch applied last:
  `sl(...)`, `make_dag(...)`, `wave(...)` in test_dag; `escalation(**over)`,
  `sidecar(status="DONE", **over)`, `returned_events()` in test_run_state.
  Extend these factories rather than hand-rolling bodies in each test.
- Base classes hold the tmpdir + CLI harness: `DagCliTestCase` (test_dag:642),
  `RunStateTestCase` (test_run_state:443). `tempfile.mkdtemp()` +
  `self.addCleanup(shutil.rmtree, ..., ignore_errors=True)` — never `tearDown`.
  `RunStateTestCase.setUp` seeds a stub `dag.json` for the `_require_run_dir` guard.
- `self.cli(*argv)` patches stdout/stderr with `io.StringIO`, appends `--run-dir`, returns
  `(code, payload, stderr)`.
- Custom assertions print the whole error list: `assertErrorMentions`, `assertValid`,
  `assertMentions`.
- Test names are long prose sentences describing the **contract**, not the method. Classes
  group by unit (`TestValidate`, `TestIngestSplit`, `TestPinnedPayloadFacts`, ...).
- `mock` only for I/O failure injection. Regression tests carry a comment naming the run that
  produced the bug.
- `TestPinnedPayloadFacts` (test_run_state:973) is the enforcement suite for
  `run-state-v2.md` section "Pinned payload facts" — a new pinned fact belongs there.

## Workflow JS conventions (`workflows/slice-wave.workflow.js`, 540 lines)

- **Every agent-return schema is `additionalProperties: false`.** A new return field MUST be
  added to the schema constant or the tool layer rejects the agent's return outright.
- No tests and no coverage gate cover this file (it is JS, outside `TARGET_FILES` and outside
  the Node CI lane). Its correctness rests on review; be conservative.
- Structure: schema constants -> small pure helpers -> prompt builders (pure functions of args
  + prior returns) -> `guard()`/`dispatch()` -> `runSlice()` -> wave entry.
- The script has **no clock and no filesystem**. The controller stamps every `ts`.
- Fail-closed everywhere: a null agent return is never an approval (see the synthetic OBJECT
  at :396 and `qualityStatus()` :186).
- `CTX` fields today: `run_dir, plugin_root, base_ref, test_command, conventions_path,
  shared_constraints[], tier3_surfaces[], quality_gate_cmd, models{reviewer}, thorough, polish`.
  A new ctx field must also be added to the controller's arg construction in
  `commands/spec-loop.md`.
- `packet(slice)` (:217-224) is the 6-line preamble prefixed to **every** agent prompt —
  worktree, branch, run dir, conventions path, shared constraints, optional kg snippet.

## `safety.flag` — the end-to-end template a new flag must follow

Twelve touchpoints; a new flag that skips any of them is invisible somewhere:

1. `CRITIQUE.properties.safety = {flag: boolean, reason: string|null}`, listed in
   `CRITIQUE.required` (workflow :64, :70).
2. Fail-closed default supplied for a null critic return (workflow :396).
3. Single read site: `verdicts.find(v => v.safety.flag)` (:398).
4. Control flow, four branches: verdict rollup (:401), split suppression (:403), objection
   selection (:405), replan veto (:408).
5. Escalation record — survives only as a `SAFETY — ` **title prefix** (:414); there is no
   structured field on EscalationRecord.
6. Event: `council-verdict` payload `safety: !!safety` (:402) — **`reason` is dropped here and
   recorded nowhere**.
7. Sidecar: `state.critique` is only `{verdict, concerns:<count>}` — no safety field.
8. `run_state.py` `_returned_events` passes payloads byte-for-byte; the returned `events[]`
   wins over the sidecar-derived fallback (`_slice_events` :677).
9. Prose: `_summarize` (:407-419) prefixes `SAFETY ` in `decisions-log.md`.
10. Metrics: `run_metrics.py:811-819` null-honest `safety_objections`.
11. Docs: pinned in `references/run-state-v2.md:137-138`; agent docs
    `plan-critic.md:43-45`, `guardian.md:16-18,72-75`; `escalation-gate/SKILL.md:61-63,93`;
    inline mode `slice-worker-fallback.md:71-72`.
12. Dashboards: **not surfaced at all** — `_sidecar_view`/`_review_view`/`_council_summary`
    (dashboard_server) and `sidecarLines`/`METRIC_FIELDS` (index.html) are fixed allowlists
    that never iterate payload keys.

## Existing deferred-scope plumbing (reuse it; do not invent a parallel channel)

- The event type **`deferred` already exists** in the pinned 17-type vocabulary
  (`run-state-v2.md:117-118`) and is already a member of `run_state.py` `DECISION_EVENTS`
  (:81), so it already renders into `decisions-log.md` with no new plumbing. Event `type` is
  accepted as any non-empty string — there is no allowlist.
- The **wave never emits `deferred`** today. Defer-hinted concern texts survive only inside
  the `council-verdict` payload's `deferred[]` array (workflow :402). The controller emits
  `deferred` at intake (`commands/spec-loop.md:42-43`).
- `runbook-writer.md:44` section 3 "Gaps & Deferred" **already reads** `deferred` events plus
  sidecars' `review.residual[]` — so events emitted by the wave reach the runbook for free.
- `state.implConcerns` (workflow :365, :436, consumed :279) is **prompt-only plumbing** — not
  in the sidecar, not in any event. It carries implementer `concerns[]` + `deviations[]` into
  the reviewer prompt as "Implementer concerns to verify".
- `state.review.residual` (:496) holds sub-bar findings as `"<severity>: <claim>"`, capped at
  10; rendered into `slice-<id>-report.md`, counted (not quoted) on the dashboard.

## `dag.json` today (`references/run-state-v2.md:14-53` is the single home)

Run-level keys: `schema_version, run_id, base_ref, base_sha, base_branch, merge_mode, mode,
created_at, shared_constraints[]`. Slice keys: `id, goal, files, subsystems, deps, risk_tier,
depth, parent, status, remediation`.

`dag.py validate_dag` (:160-247) validates `schema_version`, `slices` list, per-slice
`id`/`status`/`risk_tier`/`depth`/`deps`, dep+parent cross-refs, cycles, and waves. It
**never validates any run-level key** — including `shared_constraints`. `mark`/`ingest-split`
route through `_load_for_mutation` (:585), which refuses to mutate a contract-invalid dag.
`ingest_split` derives child ids `"<parent>.<n>"`, and children inherit parent `deps`,
`risk_tier`, and `remediation`.

## Docs single-home rule

`run-state-v2.md:6-7` and `risk-tiers.md:5`: **when a doc and the code disagree, fix one of
them in the same change.** A contract change that leaves its reference doc stale is an
incomplete change. `risk-tiers.md:26-33` holds the tier->review-shape table;
`run-state-v2.md` "Pinned payload facts" holds event payload guarantees.

## Agent markdown conventions (`plugins/spec-loop/agents/`)

- Frontmatter: exactly five keys in fixed order — `name`, `description`, `tools`, `model`,
  `color`. `description` is one long sentence-chain (~40-90 words): what it does, when it is
  dispatched, and a read-only/authority disclaimer. **Quote the description with `"` if it
  contains a colon-space.** `validate_marketplace.py:333-363` rejects an unquoted top-level
  scalar containing a colon followed by a space.
- `validate_marketplace.py` requires only `name` + `description` on agents; `tools`, `model`,
  `color` are unvalidated, and there is no agent name-vs-filename check. Every
  `${CLAUDE_PLUGIN_ROOT}/<path>` referenced from an agent/command/skill must resolve
  (`validate_bundled_dependencies` :183).
- Body: no H1. Opens with 1-3 unheaded identity paragraphs ("You are..."), then `##` sections
  only. Canonical order: `## Inputs` -> a domain section (`## The five mandates`, `## What you
  interrogate`) -> `## Verdict semantics` / `## Statuses` -> optional `## Read-only rules` ->
  **always last: `## Untrusted-data guard`**.
- Voice: second person imperative, em-dash-heavy, names the failure mode the agent exists to
  prevent, cites concrete observed costs, "the packet is a floor, not a ceiling", "File paths,
  never pasted content", "read-only and advisory". Wrap ~95 chars. Length 67-106 lines.
- Council trio for reference: `plan-critic.md` (70 lines, all five mandates, `model: inherit`),
  `guardian.md` (91, risk lane only, `model: inherit`, owns the SAFETY veto and has an
  `## Independence` section), `skeptic.md` (88, premise lane only, `model: sonnet`).
- Known pre-existing mismatch: all three council docs write `fixableByReplan`; the schema
  field is `fixable_by_replan` (workflow :66, read :408).

## Tier -> review shape (`references/risk-tiers.md:26-33`, workflow is authoritative)

| | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| Critique | none | `plan-critic` session/low | `plan-critic` + `guardian`, session/high (`--thorough` adds `skeptic`) |
| Reviewers | 1 `pr-reviewer` sonnet/low | 1 `pr-reviewer` session/medium | 2 `pr-reviewer` (correctness+errors+risk session/high; tests+types+design+comments+conventions sonnet/high) |
| Blocking bar | P0 | P0+P1 | P0+P1 |
| Finding verification | none | none | batched `finding-verifier` per fix round |
| Simplify | none | none | one `simplifier`, non-blocking |
| Agent cap | 10 | 18 | 32 |

Quality gate, fix loop (<=2 rounds), and full verification run at every tier.

## Key-file map

| Path | Role |
|---|---|
| `plugins/spec-loop/workflows/slice-wave.workflow.js` | the wave pipeline; all agent-return schemas; `packet()`; hub of this run |
| `plugins/spec-loop/scripts/dag.py` | `dag.json` authority: validate, next-wave, record-wave, mark, ingest-split |
| `plugins/spec-loop/scripts/run_state.py` | sidecar validation, event append, prose rendering |
| `plugins/spec-loop/references/run-state-v2.md` | single home of every on-disk shape |
| `plugins/spec-loop/references/risk-tiers.md` | single home of tier->review shape |
| `plugins/spec-loop/commands/spec-loop.md` | the controller; builds the wave `args`/`ctx` |
| `plugins/spec-loop/agents/*.md` | 13 agent contracts |
| `plugins/spec-loop/skills/escalation-gate/SKILL.md` | the five escalation triggers |
| `plugins/spec-loop/scripts/run_metrics.py` | metrics channels, null-honest |
| `plugins/spec-loop/scripts/dashboard_server.py` + `scripts/dashboard_assets/index.html` | read-only dashboards, fixed allowlists |
| `scripts/measure_coverage.py` + `scripts/coverage_omit.txt` | the coverage-floor gate |
| `scripts/validate_marketplace.py` | frontmatter + bundled-dependency contracts |
| `CHANGELOG.md` | Keep-a-Changelog; an `## [Unreleased]` section exists at the top |
