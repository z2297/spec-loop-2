# Slice s12 — round-2 measured results

Every number in this file was measured first-hand at the hash named beside it. Nothing here
is copied from a plan, from `conventions.md`, or from an earlier commit, except the one block
explicitly attributed to `conventions.md` in the "BEFORE" section, which says so in place.

## Shipped head

- Code head: `f851884` (`f8518847030ff2af267b1d6c19faa5023d45b509`)
  — `refactor(coverage-gate): split the shim resolver into header and block helpers`
- Slice base (branch point): `39f7a28` — `spec-loop(20260827-deferral-sweep): merge slice s9`
- Run base (release 2.2.1): `299f0db`

The commit that adds this report sits directly on top of `f851884`; it changes markdown only,
so every measurement below still describes the shipped code.

## The seven segments, at `f851884`

Each was run as its own tool call from the worktree root.

| # | segment | measured result |
|---|---|---|
| 1 | `python3 scripts/validate_marketplace.py .` | exit 0 — `OK: marketplace and all plugins valid (.)` |
| 2 | `python3 -m unittest discover -s scripts -p 'test_*.py'` | exit 0 — `Ran 126 tests in 22.852s` / `OK` |
| 3 | `python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'` | exit 0 — `Ran 1291 tests in 14.460s` / `OK` |
| 4 | `python3 scripts/measure_coverage.py` | exit 0 — `suite: 1417 tests passed`, `PASS: all per-file and total floors met.` |
| 5 | `node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs` | exit 0 — `# tests 48` / `# pass 48` / `# fail 0` |
| 6 | `node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs` | exit 0 — `# tests 23` / `# pass 23` / `# fail 0` |
| 7 | `claude plugin validate .` | exit 0 — `✔ Validation passed` |

All seven were then run once more with this report committed on top of `f851884` — a commit
that adds markdown and nothing else — and returned the same results: exits 0, `Ran 126` / `Ran 1291`,
`suite: 1417 tests passed`, `# pass 48` / `# pass 23` with `# fail 0`, and a segment-4
coverage table that `diff` reports as identical to the block pasted below.

Segment 3 prints three expected stderr lines from CLI error-path tests
(`error: provide a PR URL...`, `error: unsupported host 'gitlab.com'...`, a `git failed:`
line from a deliberately bad ref); segment 4 reproduces them because it re-runs both suites
under `trace`. They are exercised error paths, not failures — both segments end `OK` at exit 0.

### Test-count deltas, both sides measured first-hand

| suite | at `39f7a28` | at `f851884` | delta |
|---|---|---|---|
| segment 2 (`scripts/`) | `Ran 106 tests` / `OK` | `Ran 126 tests` / `OK` | +20 |
| segment 3 (`plugins/spec-loop/scripts/`) | `Ran 1288 tests` / `OK` | `Ran 1291 tests` / `OK` | +3 |
| segment 4 combined (`measure_coverage.py`) | `suite: 1394 tests passed` | `suite: 1417 tests passed` | +23 |

The `39f7a28` column was measured in the primary checkout, which sits at that hash; the same
checkout caveat given in the BEFORE coverage section below applies to it.

The plan predicted 108 for segment 2. The measurement is 126, and the measurement wins: the
plan's 108 was derived from the run base's 106 plus this task's two new tests, but the slice
carries six earlier commits (`cb7253b`, `f8f69a1`, `dd3485e`, `4f860de`, `4fe5194`, `e10c174`)
that also added tests. The +20 measured here is the whole slice's contribution to that suite,
not this task's alone.

## Coverage — BEFORE and AFTER

**AFTER**, pasted verbatim from segment 4 at `f851884`:

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

**BEFORE** — a first-hand measurement of the run base `299f0db` was NOT possible. The primary
checkout at `/Users/zachmcmurry/Documents/Repos/spec-loop-2` is at `39f7a28`, not `299f0db`
(`git -C ... rev-parse --short HEAD` → `39f7a28`, working tree carrying an unrelated modified
`CHANGELOG.md` and untracked run docs). This slice does not create or switch worktrees, so the
`299f0db` tree was never on disk for it to measure.

What IS measured first-hand is the slice's own base, `39f7a28` — pasted verbatim from
`python3 scripts/measure_coverage.py` run in that checkout:

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

Caveat stated rather than hidden: that base run was taken with the primary checkout's
unrelated `CHANGELOG.md` edit present. `CHANGELOG.md` is not a coverage target and no target
module was modified there, so the tree is code-identical to `39f7a28` for coverage purposes.

For the run base `299f0db` the only figures available are the three rows plus TOTAL that
`conventions.md` records, and they are quoted here **on `conventions.md`'s authority, not on
mine** — I did not run them: `quality_gate.py` 91.7% 638/696, `run_metrics.py` 98.6% 1303/1321,
`run_state.py` 100.0% 671/671, `TOTAL` 96.7% 5972/6173. That is a three-file excerpt; it is
not a full 13-file base table and is not presented as one.

### Which rows moved between `39f7a28` and `f851884`, and why

Three rows moved: `quality_gate.py` 824/880 → 823/879 (93.6% both sides), `run_metrics.py`
1306/1322 → 1307/1322 (98.8% → 98.9%), `run_state.py` 739/740 → 740/740 (99.9% → 100.0%).
TOTAL 6229/6427 → 6230/6426, 96.9% on both sides against the 90% floor. Ten rows are identical.

Those are exactly the three files whose old fixed OMIT range had drifted away from their real
entry shim, which the symbolic `__main__` token now resolves at measure time. Measured with
the shipped resolver against each target's own source:

```
dag.py                       base-range 786-787  resolved [786, 787]  same
dashboard_launcher.py        base-range 558-559  resolved [558, 559]  same
dashboard_server.py          base-range 1645-1646  resolved [1645, 1646]  same
knowledge_graph.py           base-range 1211-1212  resolved [1211, 1212]  same
pr_resolver.py               base-range 488-489  resolved [488, 489]  same
quality_gate.py              base-range 1118-1119  resolved [1570, 1571]  DRIFTED
release.py                   base-range 194-195  resolved [194, 195]  same
review_package.py            base-range 131-132  resolved [131, 132]  same
run_metrics.py               base-range 2175-2176  resolved [2186, 2187]  DRIFTED
run_state.py                 base-range 1104-1105  resolved [1302, 1303]  DRIFTED
spec_loop_guard.py           base-range 250-251  resolved [250, 251]  same
validate_marketplace.py      base-range 417-418  resolved [417, 418]  same
worktrees.py                 base-range 385-386  resolved [385, 386]  same
```

`quality_gate.py` and `run_metrics.py` are byte-identical across this slice's diff, so their
movement is attributable to the manifest re-expression alone. `run_state.py` has two
contributors — the same re-expression plus its own round-1 change and the tests added with it —
so its rise to 100.0% is not claimed for the manifest work by itself.

## Complexity — BEFORE and AFTER, frozen gate

Backend: the FROZEN pre-run gate, `git show 299f0db:plugins/spec-loop/scripts/quality_gate.py`,
via `analyze_builtin` over the whole file. Thresholds: cyclomatic 10, cognitive 15,
method_lines 50, parameter_count 4, nesting_depth 3.

BEFORE, at `e10c174` (one function, over two thresholds):

```
resolve_main_shim {'cyclomatic_complexity': 11, 'method_lines': 32, 'parameter_count': 2, 'cognitive_complexity': 21, 'nesting_depth': 3}
```

AFTER, at `f851884` (three functions, all under every threshold):

```
_sole_shim_header {'cyclomatic_complexity': 4, 'method_lines': 11, 'parameter_count': 2, 'cognitive_complexity': 6, 'nesting_depth': 3}
_guarded_block    {'cyclomatic_complexity': 4, 'method_lines': 14, 'parameter_count': 2, 'cognitive_complexity': 7, 'nesting_depth': 3}
resolve_main_shim {'cyclomatic_complexity': 2, 'method_lines': 18, 'parameter_count': 2, 'cognitive_complexity': 2, 'nesting_depth': 3}
```

The plan's threshold-breach check over those three names returns `[]` at `f851884`.

Two neighbouring functions in the same file remain over the cognitive threshold —
`executable_lines` (cognitive 16, nesting_depth 4) and `validate_omit` (cognitive 22). Both are
byte-identical to their `39f7a28` text and therefore outside the changed range the gate reads,
so the gate does not report them. They are recorded here as known, untouched, pre-existing
state rather than as anything this slice cleared.

## Gate position at the shipped head

The frozen gate run over this slice's full diff
(`--base 39f7a28 --head HEAD --repo-dir .`) reports `checks: 170`, `vacuous: false`, and
exactly three failures — all of them `class_lines`, all of them accepted pre-existing debt:

| file | `class_lines` at `f851884` | `grep -c .` at `f851884` | `grep -c .` at run base `299f0db` |
|---|---|---|---|
| `plugins/spec-loop/scripts/run_state.py` | 1078 | 1078 | 918 |
| `plugins/spec-loop/scripts/test_run_state.py` | 1730 | 1730 | 1269 |
| `scripts/measure_coverage.py` | 535 | 535 | 453 |

All three were already above the 300 threshold at the run base (918, 1269, 453 non-blank), so
all three fall inside the run's accepted-pre-existing-`class_lines` rule; none of them crosses
300 for the first time during this run. `scripts/measure_coverage.py` measures 535, not the 524
the plan quoted — the plan's figure predates this task's decomposition, and the measured value
is the one to use. There is no function-level violation and no other metric failure.

## Control-flow words in the added prose

The claim being backed: the lines this slice adds to `scripts/measure_coverage.py` and
`scripts/test_measure_coverage_manifest.py` keep gate-scored control-flow words out of new
prose. Here is the sweep that checks it, and its complete output — not a summary of it:

```
$ git diff 39f7a28..HEAD -- scripts/measure_coverage.py scripts/test_measure_coverage_manifest.py \
    | grep -n '^+' | grep -E '\b(if|for|while|case|catch|when)\b'
45:+_MAIN_SHIM_RE = re.compile(r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:")
59:+    headers = [n for n, text in enumerate(lines, 1) if _MAIN_SHIM_RE.match(text)]
60:+    if len(headers) != 1:
75:+    for offset in range(start, len(lines)):
77:+        if text.strip() and not text[:1].isspace():
80:+    while resolved and not lines[max(resolved) - 1].strip():
99:+    if len(resolved) > MAX_SHIM_LINES:
112:+    asked for the module's entry shim by name, to be turned into line numbers by
139:+    if line_range == MAIN_SHIM_TOKEN:
179:+    """The concrete omitted line numbers for one target file (PURE).
185:+    if spec.main_shim:
208:+"""Unit tests for measure_coverage.py's __main__-entry-shim resolver and manifest.
239:+        src = "if __name__ == '__main__':  # pragma: no cover\n    sys.exit(main())\n"
243:+        src = "\n" * 40 + "if __name__ == \"__main__\":\n    sys.exit(main())\n"
251:+        src = ("if __name__ == \"__main__\":\n    sys.exit(main())\n"
252:+               "if __name__ == \"__main__\":\n    sys.exit(main())\n")
257:+        body = "".join("    x = %d\n" % n for n in range(mc.MAX_SHIM_LINES + 2))
258:+        src = "if __name__ == \"__main__\":\n" + body
263:+        src = "\n" * 12 + "if __name__ == \"__main__\":\n    sys.exit(main())\n"
267:+        lines = ["if __name__ == \"__main__\":", "    sys.exit(main())", "",
272:+        for relpath in mc.TARGET_FILES:
286:+        for relpath in mc.TARGET_FILES:
295:+        for relpath, spec in self.omit.items():
304:+        for relpath, spec in self.omit.items():
314:+if __name__ == "__main__":
```

Twenty-five hits (`grep -c` on the same pipeline returns 25), each accounted for:

- **Executable code — 22 hits.** Diff lines 45, 59, 60, 75, 77, 80, 99, 139, 185 and 314 are
  real Python statements or the shim-matching regex. Diff lines 239, 243, 251, 252, 257, 258,
  263 and 267 are test fixture strings that must spell a `__main__` guard, because the resolver
  under test exists to recognise exactly that text — narrowing them would make the tests stop
  testing the thing. Diff lines 272, 286, 295 and 304 are loop headers in the manifest tests.
- **English prose — 3 hits, and the claim is narrowed to match.** Diff lines 112, 179 and 208
  use the ordinary English word "for": a sentence in the `OmitSpec` dataclass docstring, the
  one-line summary of `resolve_omit`, and the module docstring of
  `scripts/test_measure_coverage_manifest.py`. The frozen heuristic does score docstring text
  that falls inside a function body. Measured consequence at the shipped head: `resolve_omit`
  is cyclomatic 3 / cognitive 4, far under threshold; the other two sit inside no `def` at all
  (a class docstring and a module docstring), and the frozen backend extracts bodies by `def`,
  so no function record carries them. The gate run quoted above reports no function-level
  finding for either file. So the honest statement is not "no control-flow words reached new
  prose"; it is that three instances of the English word "for" did, that they are measured, and
  that they breach nothing.

The operator half of the same sweep, also pasted rather than asserted:

```
$ git diff 39f7a28..HEAD -- scripts/measure_coverage.py scripts/test_measure_coverage_manifest.py \
    | grep -n '^+' | grep -E '&&|\|\||\?(\?)?'
$ echo $?
1
```

Empty output, exit 1: this slice adds no branch operator to those two files at all — not in
prose, and not in code either.
