# Conventions — spec-loop-2 (run 20260904-loop-gate)

Every fact below was verified against the tree this session. If you find it wrong, say so in your
report rather than working around it — a false claim here launders defects into every slice.

## Layout and what ships

- `plugins/spec-loop/` is the plugin: everything that ships. `scripts/` at the REPO ROOT is
  dev/CI tooling (`validate_marketplace.py`, `measure_coverage.py`, `release.py`) — do not confuse
  it with `plugins/spec-loop/scripts/`, which is bundled runtime.
- `docs/spec-loop/<run-id>/` holds run artifacts from dogfooded runs. `.worktrees/` is gitignored.
- Repo version is **2.3.0** (`plugins/spec-loop/.claude-plugin/plugin.json`). The INSTALLED plugin
  in the harness is **2.2.0** (`~/.claude/plugins/cache/spec-loop/spec-loop/2.2.0`), so nothing
  this run adds to `hooks/hooks.json` takes effect until the marketplace copy is reinstalled.
  Do not write any artifact claiming this run protects itself.

## Full test suite — run each segment as its OWN tool call

Ten segments. A monolithic invocation approaches the 10-minute tool ceiling and gets killed
mid-run, which reads as a false red:

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p test_*.py
python3 -m unittest discover -s plugins/spec-loop/scripts -p test_*.py
python3 scripts/measure_coverage.py
node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_radius.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_replan.test.mjs
claude plugin validate .
```

Last recorded green baseline (run 20260828, integration wave 5): marketplace OK; 126 root tests;
1398 plugin tests; coverage PASS TOTAL 97.0% vs 90 floor; 48/48 dashboard; 38/38 radius;
9/9 radius-partial; 16/16 replan; plugin validate OK.

## The file this run changes most: `plugins/spec-loop/scripts/spec_loop_guard.py`

A guard registered by `plugins/spec-loop/hooks/hooks.json` on `PreToolUse` for `Bash` and
`Write|Edit|MultiEdit`, and — since slice s2 of this run — on `Stop` as well. Standard library
only. Verified structure (as it stood at intake, before s2 and s6 added the Stop branch):

- `find_active_runs(project_root)` → list of `{run_id, dir, publish_choice, merge_mode, base_ref}`,
  one per `docs/spec-loop/*/.active` marker; `merge_mode`/`base_ref` come from that run's
  `dag.json` and keep **restrictive defaults** when it is missing or unreadable.
- `current_branch(cwd)`, `_remediation(run)` (the "if run X is stale, resume it or clear
  .active" sentence every denial ends with), `_push_targets_run(command, run)`,
  `check_bash(command, cwd, runs)`, `check_write(file_path, runs, project_root)`.
- `evaluate(payload)` resolves the project root as
  `os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()`, returns `None`
  immediately when no run is active, then dispatches on `payload["tool_name"]`. It returns a
  **deny reason string or None** — it does not build the hook JSON.
- `main(argv=None)` parses stdin JSON, calls `evaluate`, and on a reason prints
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
  "permissionDecisionReason": reason}}`. Always exits 0.
- **Fail-open doctrine, stated in the module docstring**: any unexpected exception allows the
  action, because a crashed guard must not deny every tool call in the session. Denials fail
  closed and name both the compliant alternative and the stale-marker remediation.

Two structural facts the new gates must respect: `main` currently emits ONE shape, so a `Stop`
gate needs its own emit path keyed on `payload["hook_event_name"]`; and `evaluate`'s
reason-string-or-None contract is the idiom to follow rather than replace.

## APIs to import, never reimplement

Wave membership and escalation state each have exactly one implementation. `dag.py`'s module
docstring states the dashboard already imports `next_wave` as a library, so cross-module import
is an established pattern here.

- `dag.next_wave(dag)` → `{"index": int, "slice_ids": [...]}`, plus `{"deadlock": True,
  "blocked": [...]}` when nothing is runnable but slices remain, or `{"done": True}` when none
  remain. Runnable = status `pending` with every dep satisfied. `dag.load_dag(run_dir)` reads it.
- `run_state.open_escalations(run_dir)` → every escalation opened and not yet answered, in the
  order opened; an `escalation-opened` payload with `status == "ANSWERED"`, or a later
  `escalation-answered` event with the same `id`, marks it answered.

Both modules are **standard-library only** (`dag.py`: argparse, json, os, sys, tempfile;
`run_state.py`: argparse, hashlib, json, os, re, sys, tempfile) and both import in ~13ms each,
measured on this machine. Importing them from the guard costs nothing against the hook's
5-second budget and keeps `spec_loop_guard.py` stdlib-only. Both have `__main__` guards, so
importing them runs no argparse and has no side effects. The hook is invoked as
`python3 <plugin_root>/scripts/spec_loop_guard.py`, which puts that scripts directory on
`sys.path[0]`, so a plain `import dag` / `import run_state` resolves without path surgery.

## Prose and doctrine conventions

- **Counted prose is pinned by tests.** `plugins/spec-loop/scripts/test_doctrine_run_docs.py`
  compares README's printed component inventory against a real count on disk: commands
  (`**Commands (%d)**`), agents, skills, `**Scripts (%d runtime + tests)**` (non-test, non
  `slice_wave_contract*` `.py` files), and the Node harness modules from
  `scripts/*.test.mjs` — including their number spelled as a word ("back six Node harness
  modules") and each module named in backticks. It also pins `README.md` and
  `references/risk-tiers.md` at the escalation-gate's **six** triggers and asserts the
  five-trigger predecessor sentences are gone.
  **Consequence:** adding a new `.py` script, a new `*.test.mjs` harness module, a new command,
  agent, or skill drags README's counts with it. Keeping the new gates inside the existing
  `spec_loop_guard.py`, with tests in the existing `test_spec_loop_guard.py`, changes none of
  those counts. That is a reason for the design, not an accident of it.
- `skills/escalation-gate/SKILL.md:126` "### Not triggers (autonomous by design)" opens with
  "Three things that look like stopping points…" (line 128) and line 79 opens another counted
  list with "Three things that are deliberately NOT judgment triggers". A fourth entry means
  updating the count in the same edit. No test pins these two counts yet; the repo's own habit
  (test_doctrine_run_docs exists because counted prose drifted silently) makes adding such a pin
  the consistent move, and it is in scope.
- `commands/spec-loop.md` wraps at ~90 columns, numbers Phase steps `1.`–`8.` with **bold step
  names** (`3. **Dispatch**:`) and three-space continuation indent.
- CHANGELOG follows Keep a Changelog with an `[Unreleased]` section at the top; 2.3.0's entry
  leads each bullet with a **bolded sentence** stating the change in plain terms.
- `references/platform-probes.md` is the single home for empirically probed harness behaviour.
  This run's probe results are already written up at
  `docs/spec-loop/20260904-loop-gate/probe-results.md` — read that file; do not re-probe.

## Testing conventions

- `unittest` only, stdlib only, discovered by `python3 -m unittest discover -p test_*.py`.
- Tests live beside the module they cover, named `test_<module>.py`.
- `scripts/measure_coverage.py` enforces BOTH a per-file floor and a `TOTAL_FLOOR = 90`, so a
  file cannot hide behind the aggregate. The floor that applies to this run is
  `"scripts/spec_loop_guard.py": 86` (measure_coverage.py:152, local 92.0% minus a 6-point
  margin). New gate code that is not covered by tests pushes that file DOWN toward 86 — the
  coverage segment is a real gate here, not a formality.
- `scripts/coverage_omit.txt` is the only place lines may be excluded, every entry needs a
  `# rationale`, and `spec_loop_guard.py:__main__` is already omitted as a process-entry shim.
  The symbolic `__main__` token is resolved from the source at measure time, so file growth can
  never repoint it. Note precisely what it resolves TO: the `if __name__ == "__main__":` shim
  header plus its indented body (two lines here), NOT the `main()` function. Code you add inside
  `main()` is measured normally and must be covered by tests.
  `test_measure_coverage_manifest.py` pins each target's resolved block size, so it fails if that
  shim itself grows until the new size is deliberately accepted in that test.
- Node contract/behaviour harnesses for the workflow are `*.test.mjs` run by `node --test`.

## Knowledge-graph precedent that applies to this run

- *Recording a judgement is not acting on it — say which you built.* A gate that observes but
  cannot deny is a channel, not a lever; every artifact must say which one it is.
- *A per-run patch to generated orchestration does not survive a new dispatch.* Hooks load from
  the INSTALLED plugin, so editing the repo's `hooks.json` changes nothing until reinstall.
- *A wrong shared convention artifact launders defects downstream.* This file included.
- *An objection resolved by one silent retry never reaches the human.* Relevant to the Stop
  gate's one-shot `stop_hook_active` behaviour: it must leave a visible trace, not silently
  give up on the second fire.

## One live hazard, observed at this run's intake

Writing prose that QUOTES a forbidden git command through a shell heredoc gets denied by the
very guard being documented: `check_bash`'s patterns match the quoted example inside the
payload, not a command being run. It happened at intake here, writing a knowledge-graph note
that described the broad-staging denial.

Use the `Write`/`Edit` tools for any file whose content quotes git commands. Do **not** narrow
the guard's patterns to ignore quoted text - that weakens the real guard, and it is outside this
run's scope besides. The defect is recorded as a `deferred` event and as a knowledge-graph
pattern; the workaround is a run-wide shared constraint.
