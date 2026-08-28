# Slice s12 — round-3 (final) measured results

Every number in this file was measured first-hand at the hash named beside it, in this
worktree, on the day of this commit. Nothing here is copied from a plan, from
`conventions.md`, or from an earlier commit, except the one three-row block explicitly
attributed to `conventions.md` in the "BEFORE" coverage section, which says so in place.

## A note on this file's history

An earlier version of this report (commit `c48d3ce`) cited a "shipped head" of `f851884`
and a "slice base" of `39f7a28`. Between that commit and this one, the branch was rebased
onto the merged `s10` slice: `f851884` is a real commit object still present in this repo's
object store, but `git merge-base --is-ancestor f851884 HEAD` fails — it is not an ancestor
of the head this report now describes, and `39f7a28` is one merge point behind this slice's
actual branch point. Every number below was re-measured at the hashes named in this
revision; none of it is carried forward from the earlier revision's text.

## Shipped head

- Code head: `3006fbc` (`3006fbcac54610e6e2ea21ddd4e73d73372d6cc1`)
  — `test(coverage-gate): pin the resolved __main__ block size so the manifest guard can fail`
- Slice base (branch point): `ac283ad` — `spec-loop(20260827-deferral-sweep): merge slice s10`
- Run base (release 2.2.1): `299f0db`

This slice's own commits on top of `ac283ad`, in order: `5849716`, `3326697`, `12548d4`,
`ffb4a25`, `1891617`, `34b66fa`, `fb3d2a0`, `c48d3ce`, `8a6e02d`, `3006fbc`. The final one,
`3006fbc`, is this round's Task 1: it touches exactly `scripts/coverage_omit.txt` (header
comment only) and `scripts/test_measure_coverage_manifest.py` (one test method replaced,
one module constant added, one docstring sentence narrowed).

## The seven segments, at `3006fbc`

Each was run as its own tool call from the worktree root.

| # | segment | measured result |
|---|---|---|
| 1 | `python3 scripts/validate_marketplace.py .` | exit 0 — `OK: marketplace and all plugins valid (.)` |
| 2 | `python3 -m unittest discover -s scripts -p 'test_*.py'` | exit 0 — `Ran 126 tests in 23.430s` / `OK` |
| 3 | `python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'` | exit 0 — `Ran 1292 tests in 14.439s` / `OK` |
| 4 | `python3 scripts/measure_coverage.py` | exit 0 — `suite: 1418 tests passed`, `PASS: all per-file and total floors met.` |
| 5 | `node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs` | exit 0 — `# tests 48` / `# pass 48` / `# fail 0` |
| 6 | `node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs` | exit 0 — `# tests 35` / `# pass 35` / `# fail 0` |
| 7 | `claude plugin validate .` | exit 0 — `✔ Validation passed` |

Segment 6's `# tests 35` corrects the earlier revision's `# tests 23`: the earlier number
was measured at the pre-rebase `f851884`, and the intervening commits (`ac283ad`'s merge of
`s10` plus this slice's own `T1`–`T4` and refactor commits) added JS tests to that file
independently of this round's work. `git show 3006fbc:plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs | grep -cE '^\s*test\('` also reads `35`.

Segment 3 prints three expected stderr lines from CLI error-path tests
(`error: provide a PR URL...`, `error: unsupported host 'gitlab.com'...`, a `git failed:`
line from a deliberately bad ref); segment 4 reproduces them because it re-runs both suites
under `trace`. They are exercised error paths, not failures — both segments end `OK` at exit 0.

## Task 1 verification, measured directly

- `python3 -m unittest scripts.test_measure_coverage_manifest` → `Ran 14 tests in 0.051s` /
  `OK` (one method replaced by one method; the manifest-module count does not move from the
  measured 14).
- Fault injection: inserting one extra `pass` statement inside `scripts/release.py`'s
  guarded `__main__` block (a real path, not a fixture) and re-running the same command
  fails exactly one test:
  `AssertionError: 3 != 2 : scripts/release.py` on
  `test_each_resolved_omission_is_the_pinned_block_size`. The file was restored via a `trap`
  in the same tool call; a follow-up call confirmed `git status --porcelain scripts/release.py`
  is empty and the suite is back to `Ran 14 tests` / `OK`. This demonstrates the guard is not
  tautological: a real code change under a target's shim makes it fail for the stated reason.

This diff touches only a test module (`scripts/test_measure_coverage_manifest.py`) and a
`.txt` header comment (`scripts/coverage_omit.txt`), neither of which is in `TARGET_FILES`
nor measured by `measure_coverage.py`, so no per-file or TOTAL coverage percentage can move
from this round's own change. Confirmed against segment 4's measured output above and against
the "Coverage — BEFORE and AFTER" table below, whose two sides bracket this round's commit
and are numerically identical.

### Test-count deltas, both sides measured first-hand at this revision

| suite | at `ac283ad` | at `3006fbc` | delta |
|---|---|---|---|
| segment 2 (`scripts/`) | `Ran 106 tests` / `OK` | `Ran 126 tests` / `OK` | +20 |
| segment 3 (`plugins/spec-loop/scripts/`) | `Ran 1289 tests` / `OK` | `Ran 1292 tests` / `OK` | +3 |
| segment 4 combined (`measure_coverage.py`) | `suite: 1395 tests passed` | `suite: 1418 tests passed` | +23 |

The `ac283ad` column was measured from a `git archive ac283ad` export into scratch space
(this slice's own worktree stays on `3006fbc` throughout; no branch switch or new worktree
was used). The +20 / +3 / +23 deltas are the whole slice's contribution across its ten
commits listed above, not this round's Task 1 alone — Task 1 itself adds no new test to
`scripts/` or `plugins/spec-loop/scripts/` beyond the one-for-one method replacement noted
above (manifest suite count stays at 14).

## Coverage — BEFORE and AFTER

**AFTER**, pasted verbatim from segment 4 at `3006fbc`:

```
coverage report (stdlib trace; scripts/*.py minus OMIT manifest)
  file                                         cov     run/able  floor
  scripts/dag.py                             99.8%   515/516       94%
  scripts/dashboard_launcher.py             100.0%   239/239       95%
  scripts/dashboard_server.py                99.5%   845/849       94%
  scripts/knowledge_graph.py                 86.5%   648/749       81%
  scripts/pr_resolver.py                    100.0%   274/274       80%
  scripts/quality_gate.py                    93.6%   823/879       86%
  scripts/release.py                        100.0%   125/125       95%
  scripts/review_package.py                  94.3%    83/88        89%
  scripts/run_metrics.py                     98.9%  1307/1322      93%
  scripts/run_state.py                      100.0%   740/740       95%
  scripts/spec_loop_guard.py                 92.0%   127/138       86%
  scripts/validate_marketplace.py            99.3%   275/277       94%
  scripts/worktrees.py                       99.6%   229/230       94%
  TOTAL                                      96.9%  6230/6426      90%
PASS: all per-file and total floors met.
```

**BEFORE**, pasted verbatim from `python3 scripts/measure_coverage.py` run against a
`git archive ac283ad` export (the slice's true branch point):

```
coverage report (stdlib trace; scripts/*.py minus OMIT manifest)
  file                                         cov     run/able  floor
  scripts/dag.py                             99.8%   515/516       94%
  scripts/dashboard_launcher.py             100.0%   239/239       95%
  scripts/dashboard_server.py                99.5%   845/849       94%
  scripts/knowledge_graph.py                 86.5%   648/749       81%
  scripts/pr_resolver.py                    100.0%   274/274       80%
  scripts/quality_gate.py                    93.6%   824/880       86%
  scripts/release.py                        100.0%   125/125       95%
  scripts/review_package.py                  94.3%    83/88        89%
  scripts/run_metrics.py                     98.8%  1306/1322      93%
  scripts/run_state.py                       99.9%   739/740       95%
  scripts/spec_loop_guard.py                 92.0%   127/138       86%
  scripts/validate_marketplace.py            99.3%   275/277       94%
  scripts/worktrees.py                       99.6%   229/230       94%
  TOTAL                                      96.9%  6229/6427      90%
PASS: all per-file and total floors met.
```

For the run base `299f0db` the only figures available are the three rows plus TOTAL that
`conventions.md` records, and they are quoted here **on `conventions.md`'s authority, not on
mine** — I did not run them: `quality_gate.py` 91.7% 638/696, `run_metrics.py` 98.6% 1303/1321,
`run_state.py` 100.0% 671/671, `TOTAL` 96.7% 5972/6173. That is a three-file excerpt; it is
not a full 13-file base table and is not presented as one.

### Which rows moved between `ac283ad` and `3006fbc`, and why

Three rows moved: `quality_gate.py` 824/880 → 823/879 (93.6% both sides), `run_metrics.py`
1306/1322 → 1307/1322 (98.8% → 98.9%), `run_state.py` 739/740 → 740/740 (99.9% → 100.0%).
TOTAL 6229/6427 → 6230/6426, 96.9% on both sides against the 90% floor. Ten rows are identical.

Those are the same three files whose old fixed OMIT range had drifted away from their real
entry shim, which the symbolic `__main__` token now resolves at measure time (this slice's
`T1`–`T3` commits); `run_state.py`'s move to 100.0% also carries a contribution from its own
`T4` change and companion tests, so its rise is not attributed to the manifest work alone.
This round's own commit (`3006fbc`) moves none of these rows: it touches no `TARGET_FILES`
member.

## Complexity — BEFORE and AFTER, frozen gate

Backend: the FROZEN pre-run gate, `git show 299f0db:plugins/spec-loop/scripts/quality_gate.py`,
via `analyze_builtin` over the whole file. Thresholds: cyclomatic 10, cognitive 15,
method_lines 50, parameter_count 4, nesting_depth 3.

BEFORE, at `34b66fa` (the last commit on this branch before the shim-resolver split; one
function, over two thresholds):

```
resolve_main_shim {'cyclomatic_complexity': 11, 'method_lines': 32, 'parameter_count': 2, 'cognitive_complexity': 21, 'nesting_depth': 3}
```

AFTER, at `3006fbc` (three functions, all under every threshold):

```
_sole_shim_header {'cyclomatic_complexity': 4, 'method_lines': 11, 'parameter_count': 2, 'cognitive_complexity': 6, 'nesting_depth': 3}
_guarded_block    {'cyclomatic_complexity': 4, 'method_lines': 14, 'parameter_count': 2, 'cognitive_complexity': 7, 'nesting_depth': 3}
resolve_main_shim {'cyclomatic_complexity': 2, 'method_lines': 18, 'parameter_count': 2, 'cognitive_complexity': 2, 'nesting_depth': 3}
```

Two neighbouring functions in the same file remain over the cognitive threshold —
`executable_lines` (cognitive 16, nesting_depth 4) and `validate_omit` (cognitive 22). Both
were verified byte-identical between `ac283ad` and `3006fbc` (a direct text diff of each
function body returns no difference) and therefore outside the changed range the gate reads
here; they are recorded as known, untouched, pre-existing state rather than as anything this
slice cleared.

## Gate position at the shipped head

The frozen gate run over this slice's full diff from its true branch point
(`--base ac283ad --head HEAD --repo-dir .`, `HEAD` = `3006fbc`) reports `checks: 170`,
`vacuous: false`, and exactly three failures — all of them `class_lines`, all of them
accepted pre-existing debt:

| file | `class_lines` at `3006fbc` | `grep -c .` at `3006fbc` | `grep -c .` at run base `299f0db` |
|---|---|---|---|
| `plugins/spec-loop/scripts/run_state.py` | 1078 | 1078 | 918 |
| `plugins/spec-loop/scripts/test_run_state.py` | 1730 | 1730 | 1269 |
| `scripts/measure_coverage.py` | 535 | 535 | 453 |

All three were already above the 300 threshold at the run base (918, 1269, 453 non-blank), so
all three fall inside the run's accepted-pre-existing-`class_lines` rule; none of them crosses
300 for the first time during this slice. There is no function-level violation and no other
metric failure. **These are the only remaining gate violations; the controller can accept on
this evidence.**

## Control-flow words in the added prose

The claim being backed: the lines this slice adds to `scripts/measure_coverage.py` and
`scripts/test_measure_coverage_manifest.py`, across all ten of this slice's commits since its
true branch point `ac283ad`, keep gate-scored control-flow words out of new prose. Here is the
sweep that checks it, run fresh at `3006fbc`:

```
$ git diff ac283ad..HEAD -- scripts/measure_coverage.py scripts/test_measure_coverage_manifest.py \
    | grep -n '^+' | grep -E '\b(if|for|while|case|catch|when)\b' | wc -l
25
```

Twenty-five hits, each accounted for:

- **Executable code — 22 hits.** Real Python statements, the shim-matching regex, loop
  headers in the manifest tests, and test fixture strings that must spell a `__main__` guard
  because the resolver under test exists to recognise exactly that text.
- **English prose — 3 hits, and the claim is narrowed to match.** Three uses of the ordinary
  English word "for" appear inside a dataclass docstring sentence, a one-line function
  summary, and the module docstring of `scripts/test_measure_coverage_manifest.py`. The
  frozen heuristic does score docstring text that falls inside a function body; none of these
  three sits inside a `def`, so the gate run above reports no function-level finding tied to
  either. The honest statement is not "no control-flow words reached new prose"; it is that
  three instances of the English word "for" did, that they are measured, and that they breach
  nothing.

This round's own Task 1 commit (`3006fbc`) adds one new comment block (the
`SHIPPED_SHIM_LINES` constant comment), one new docstring (on
`test_each_resolved_omission_is_the_pinned_block_size`), and one new comment paragraph (in
`scripts/coverage_omit.txt`); none of the three contains a whole-word control-flow token or
`&&`/`||`/`?`, confirmed by the same `grep -nE` pattern scoped to `git show 3006fbc`.

The operator half of the same sweep, also run fresh:

```
$ git diff ac283ad..HEAD -- scripts/measure_coverage.py scripts/test_measure_coverage_manifest.py \
    | grep -n '^+' | grep -E '&&|\|\||\?(\?)?'
$ echo $?
1
```

Empty output, exit 1: this slice adds no branch operator to those two files at all — not in
prose, and not in code either.
