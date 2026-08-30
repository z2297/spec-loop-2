# Conventions — spec-loop-2 (run: heavy-refactor escalation)

This repo IS the spec-loop 2 Claude Code plugin. Product code lives in
`plugins/spec-loop/`. Read this file instead of re-exploring.

## Test / build command (7 segments — run each as its OWN tool call)

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p test_*.py
python3 -m unittest discover -s plugins/spec-loop/scripts -p test_*.py
python3 scripts/measure_coverage.py
node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
claude plugin validate .
```

NEVER chain these into one invocation: a monolithic call has twice been killed by the
10-minute tool ceiling and read as a false red. CI equivalent: `.github/workflows/validate.yml`
(also enforces min-test-count gates: >=12 dashboard-asset tests, >=14 behaviour tests, because
`node --test` exits 0 on zero registered tests).

## Hard constraints

- **Stdlib only.** No third-party Python. Node built-ins only. No package.json, no Makefile,
  no pyproject.toml, no linter config anywhere — style is review-enforced.
- **Coverage floors** (`scripts/measure_coverage.py:143-158`): TOTAL 90; per-file
  `run_state.py 95` (currently ~100 — tightest margin in the repo), `run_metrics.py 93`,
  `quality_gate.py 86`, `dag.py 94`, `worktrees.py 94`, `dashboard_server.py 94`.
  **Any new branch/guard added to run_state.py / run_metrics.py / quality_gate.py needs a test
  that actually EXECUTES it in the same change**, or coverage goes red on a correct diff.
  Floors are set >=5 points below measured max on purpose; never raise a floor to its max.
- **Quality gate on changed code**: `class_lines 300`, `method_lines 50`,
  `cyclomatic_complexity 10`, `cognitive_complexity 15`, `nesting_depth 3`,
  `parameter_count 4`, `crap_score 30`. New files must land at/under 300 non-blank lines —
  this is why the workflow contract tests are split across three files. Pre-existing
  `class_lines` failures on old files are a human-accepted state, not a regression to chase.
- **Coverage OMIT manifest** `scripts/coverage_omit.txt`: every entry MUST carry a
  `# rationale` or the tool refuses to run. Prefer the symbolic `<file>.py:__main__` token over
  pinned line ranges (pinned ranges silently repointed at live code during run 20260827).

## Python conventions (`plugins/spec-loop/scripts/`)

- Shebang `#!/usr/bin/env python3`, then a module docstring that is a **design essay**:
  purpose, numbered stages, `Design decisions:` bullets with bold lead-ins, `Exit codes:`,
  `Usage:` block per subcommand. Templates: `run_state.py:1-60`, `quality_gate.py:1-49`.
- `(PURE)` marker ends the one-line summary of any function with no I/O, no clock, no global
  mutation. `_leading_underscore` = module-internal; unprefixed = the surface tests bind to.
- **Type hints: match the file you are editing.** `run_metrics.py` annotates; `quality_gate.py`
  and `run_state.py` use ZERO hints. Do not cross-contaminate.
- CLI shape: `build_parser()` -> `argparse` + `add_subparsers(dest="command", required=True)`;
  long flags only; every JSON flag also accepts `-` for stdin
  (`json.loads(sys.stdin.read()) if raw == "-" else json.loads(raw)`).
  `main(argv=None)` -> `_run(args)` returning `(payload, exit_code)` -> print
  `json.dumps(payload, ensure_ascii=False, indent=2)`. Entry shim always
  `if __name__ == "__main__":  # pragma: no cover`.
- **One module-level Exception subclass per concern**, caught in `main()`: `RunStateError`,
  `SidecarInvalid`, `DagError`, `ContractError`, `GateError`, `WorktreeError`, `ResolverError`.
  Contract failure -> `{"ok": false, "errors": [...]}` on stdout, exit 1. Usage/unreadable
  input -> `error: %s` on stderr, exit 2.
- **Fail closed, null-honest**: missing stays `null`, never invented; an unusable input is
  never an approval. **No script calls `datetime.now()`** — the controller owns the clock and
  passes `--ts`.
- Writes: `_atomic_write` (temp + `os.replace`) for sidecars/reports; `events.jsonl` and
  `decisions-log.md` are append-only O_APPEND.
- Comments justify a decision **against the rejected alternative**, in full sentences, often
  naming a real incident and a run-id.

### Reuse these — do not reimplement
| helper | location |
|---|---|
| git subprocess wrapper | `worktrees.py:92 run_git(repo_dir, *args)` |
| JS-source contract test base | `slice_wave_contract_base.py:268 WorkflowSourceTestCase` (`self.src`, `line_containing()`, `between()`) |
| loaded workflow text | `slice_wave_contract_base.py:52-53 WORKFLOW` / `SOURCE` |
| the ONE workflow wrapper | `slice_wave_contract_base.py:260 wrapped_source()` (the .mjs harness shells out to it) |
| escalation/sidecar fixtures | `test_run_state.py:33 escalation(**over)`, `:54 sidecar(status=..., **over)` |
| event fixture | `test_run_metrics.py:69 ev(ts, scope, type_, **payload)` |
| dag fixtures | `test_dag.py:30 sl()`, `:47 make_dag()`, `:66 wave()` |
| executable-line set | `scripts/measure_coverage.py:164 executable_lines()` |

## Test conventions

- stdlib `unittest` only, never pytest. One `test_<module>.py` beside the module.
- Test method names are **long full sentences** — the name IS the spec, e.g.
  `test_the_crash_record_names_the_last_dispatched_stage_without_overclaiming`.
- Classes grouped by function-under-test with `# ---- name ----` banner comments.
- Fixtures are plain module-level functions taking `**over`. Assertion helpers are methods on
  the local TestCase subclass, not free functions.
- Required header: `import sys`/`from pathlib import Path`, then
  `sys.path.insert(0, str(Path(__file__).resolve().parent))`, then `import x as y  # noqa: E402`.
- Node tests live inside the plugin, `node:test` + `node:assert/strict` only.

## Workflow JS (`plugins/spec-loop/workflows/slice-wave.workflow.js`, 1061 lines)

- `export const meta = {...}` on line 1 and it must be the ONLY line-initial `export const`.
- Structure: meta -> box-drawn "Hard rules this file owns (single home)" header -> arg
  normalization (`const A = typeof args === 'string' ? JSON.parse(args) : args`; `const CTX =
  A.ctx` with the ctx field list inline at :33) -> `CAPS = {1:10, 2:18, 3:32}`,
  `MAX_FIX_ROUNDS = 2`, `BUDGET_STAGE_FLOOR = 60_000` -> `// -- Schemas --` -> pure helpers ->
  prompt builders -> `dispatch()` -> one `stageX(slice, state)` per stage -> `runSlice` ->
  wave entry with top-level `return`.
- **This file is the single home of every LLM->LLM return JSON Schema.** Agent markdown never
  restates them.
- Forbidden subset (zero hits, verified): `import`, `require(`, `fs.`, `process.`, `Date`,
  `Date.now`, `Math.random`. Only host globals: `args, agent, parallel, log, budget, phase,
  pipeline`. Style: no semicolons, 2-space indent, `const` everywhere, arrows for one-liners.
- The file is NOT a valid ES module (implicit async wrapper gives it top-level return/await);
  `node --check` only works through `wrapped_source()`.
- Two test layers: source-text contracts in the three `test_slice_wave_contract*.py` (pinned JS
  snippets as module-level constants, never inline literals — inline JS strings would be
  misscored by the quality gate's own heuristic) and the executing
  `slice_wave_behaviour.test.mjs` via `slice_wave_harness.mjs`.

## Agent markdown (`plugins/spec-loop/agents/`, 13 files)

Frontmatter, exactly these keys in order: `name` (= filename stem), `description` (one long
paragraph ending in a capability disclaimer; **must be quoted if it contains ": "** — enforced
by `validate_marketplace.py:334-360`), `tools` (unquoted comma list), `model`
(sonnet|haiku|inherit), `color`.

Body: no H1. Unheaded 4-6 line opening stating reason-to-exist and dominant failure mode, in
second person -> `## Inputs (from your dispatch prompt)` -> 2-5 job-specific `##` sections ->
`## Statuses` (enum values with a parenthetical each) -> `## Untrusted-data guard` as the LAST
section. **No JSON schemas in agent files** (`grep -c '```json'` == 0 for all 13).

Skills: two-key frontmatter (`name` matching the directory, `description`). Commands:
`description`, `argument-hint`, `allowed-tools` as a JSON array; a command whose text says
"read-only"/"never edits" must not grant `Edit`.

## Docs — the single-home doctrine

Each contract has exactly ONE home file; when file and code disagree, fix one of them in the
same change.

| file | its one responsibility |
|---|---|
| `references/run-state-v2.md` | dag.json, sidecars, EscalationRecord, events.jsonl, markers, worktrees, global config paths |
| `references/risk-tiers.md` | tier assignment + tier->review shape |
| `references/phase-5-integration.md` | end-of-run gate, runbook, publish |
| `references/split-ingestion.md` | SPLIT graft judgment |
| `references/platform-probes.md` | verified Workflow-tool facts |
| `references/migration-from-v1.md` | v1 -> v2 |

`CHANGELOG.md`: Keep a Changelog 1.1.0 + SemVer. `## [Unreleased]` always present, then
`## [X.Y.Z] - YYYY-MM-DD` newest-first with `### Added/Changed/Fixed/Removed`. Entries are long
multi-sentence bullets **opening with a bold sentence-form claim**, naming files in backticks
and stating honest limits explicitly. Link-reference block at the bottom.

`plugins/spec-loop/README.md` `## Components` carries a COUNTED inventory ("Agents (13)",
"Scripts (11 runtime + tests)") — **update the counts when adding a component.**

Version: `plugins/spec-loop/.claude-plugin/plugin.json:7` is the ONLY live version string
(2.2.2); `.claude-plugin/marketplace.json` holds historical archive pins. Both are edited
mechanically by `scripts/release.py` — do not hand-edit. Commit style: `docs(spec-loop): ...`,
`spec-loop(<run-id>): merge slice sN`, `changelog: <lowercase claim>`.

## THE ESCALATION TRIGGER ENUM — 8 touchpoints for adding one value

Currently SEVEN values. Adding one requires ALL of these, or a pinned test fails:

1. `workflows/slice-wave.workflow.js:50` — `trigger: { enum: [...] }` (ORDER-SENSITIVE)
2. `scripts/run_state.py:73` — `ESCALATION_TRIGGERS` tuple
3. `scripts/run_metrics.py:119` — second copy
4. `scripts/dashboard_server.py:149` — third copy
5. `agents/slice-worker-fallback.md:155-157` — prose list, **and the count word "seven"**
6. `references/run-state-v2.md:107` — the `"trigger": "a | b | ..."` union
7. `scripts/slice_wave_contract_base.py:117` — `TRIGGER_PROSE_LEAD = "one of the seven triggers ("`
8. `scripts/slice_wave_contract_base.py:99-101` — `ANSWERABLE_TRIGGERS` (the five JUDGMENT
   triggers whose answers are injected back into prompts). A judgment trigger MUST join this
   tuple or it is structurally unanswerable by re-dispatch.

Enforced by `test_slice_wave_contract_crash.py:271 TestTheTriggerEnumAgreesAcrossAllSixHomes`
(order-sensitive; asserts the prose lead appears exactly once).

Separately, the "**five JUDGMENT triggers**" prose (a different count from the seven enum
values) lives UNPINNED in four places: `skills/escalation-gate/SKILL.md:50`, `:92`, `:119`,
`README.md:99`, `references/risk-tiers.md:86`.

## Escalation machinery — key anchors

- Record shape: `references/run-state-v2.md:96-129`. Validation:
  `run_state.py:224 validate_escalation` (requires non-empty id/title/question, trigger in enum,
  `options` a NON-EMPTY list of objects each with a `label`; `context`/`if_unanswered` unvalidated).
- Construction in JS: `esc(slice, trigger, content)` :296, `escalated(slice, state, rec)` :307,
  id minting `escRound` :285 / `escId` :289 (`<slice-id>:<trigger>[:<round>]`).
- **Answer injection (generic, per slice+trigger)**: `answerKeysFor` :272, `latestAnswer` :628,
  `answerFor(slice, trigger)` :334 (injected into a prompt as an instruction),
  `answerContext(slice, trigger)` :346 (context-only, does NOT change what is reported).
  A new trigger inherits this for free ONLY if the raising stage's prompt builder calls it.
- Plan stage: `stagePlan` :542; `plan.status === 'ESCALATE'` -> :557
  `esc(slice, plan.escalation.trigger, plan.escalation)` — NOTE `PLAN_RESULT.required` is
  `['status']` only, so `plan.escalation.trigger` is a KNOWN unguarded optional read
  (deliberately unfixed; documented `slice_wave_contract_base.py:22-28`).
- `packet(slice)` :322-329 is prepended to EVERY prompt builder — the template for threading a
  new run-level ctx value to all agents is `scopeCeilingList(ctx)` :259-263 (type-tolerant:
  array -> as-is, non-empty string -> wrapped, anything else -> []).
- Deterministic-decision-in-JS pattern to copy: `qualityStatus()` :203-207 decides PASS/FAIL in
  JS while the verifier agent only TRANSCRIBES numbers. Agents report; JS judges.

## Quality-gate config — the one door

`quality_gate.py:211 load_config(path, overlay_path)`. Merge: thresholds override key-wise,
`custom_gates` CONCAT, `tier3_surfaces` UNION+sorted (an overlay extends, it cannot remove),
all other keys override. **`:246-248` passes every unrecognized key straight through** — this
is the documented extension point for a new config block ("--print-config is the one door to
the effective configuration"). There is NO schema/version validation; `version` is never read.
Global file `~/.claude/spec-loop-2/quality-gate.json`, repo overlay `.spec-loop/quality-gate.json`;
both write-denied by `spec_loop_guard.py:198-206` while `.active` exists.
Config keys are surfaced to the user by `commands/quality-gate.md` (step 1 list at :19-28,
written schema at :59-89, extension-point note at :81-83).

## Prior-run context (knowledge graph)

- `an-escalation-trigger-with-no-answer-injection-path-cannot-be-resolved-by-re-dis`: a trigger
  the orchestrator never reads back is structurally unanswerable. Build the injection path.
- `recording-a-judgement-is-not-acting-on-it-say-which-you-built`: separate LEVERS from
  RECORDS and say plainly which this run built. `over_scope` is a record; the request here
  asks for a lever.
- `a-type-filter-added-as-a-scope-note-becomes-a-permanent-silent-exclusion`: any threshold or
  narrowing predicate must be observable/reported, never silently applied.
- `an-optional-schema-field-read-unguarded-aborts-the-whole-pipeline`: guard optional reads in
  the workflow; there is live history of this aborting a whole wave.
- `a-test-harness-earns-its-keep-before-it-ships`: `slice_wave_behaviour.test.mjs` can EXECUTE
  the workflow — use it to answer design questions, not just to regression-test.
- `a-per-run-patch-to-generated-orchestration-does-not-survive-a-new-dispatch`: the loop resolves
  the workflow from the INSTALLED PLUGIN CACHE, not this working tree. Edits here do not affect
  the currently running loop.
