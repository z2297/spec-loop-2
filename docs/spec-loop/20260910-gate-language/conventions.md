# Conventions — quality_gate.py language-support run

Every path below is repo-relative to `/Users/zachmcmurry/Documents/Repos/spec-loop-2`.
`QG:` = `plugins/spec-loop/scripts/quality_gate.py` (1615 lines, 1403 non-blank).
`TEST:` = `plugins/spec-loop/scripts/test_quality_gate.py` (1934 lines, 1629 non-blank).

**Do not re-explore these two files' structure. It is mapped below. Read the specific
anchors you need and go.**

## 1. Test / build command

Seven segments, each its OWN tool call (a monolithic run hits the 10-minute ceiling and reads
as a false red). Source: `.github/workflows/validate.yml`.

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'
python3 scripts/measure_coverage.py
node --test --experimental-test-coverage plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs plugins/spec-loop/scripts/slice_wave_radius.test.mjs plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs plugins/spec-loop/scripts/slice_wave_reentry.test.mjs plugins/spec-loop/scripts/slice_wave_accepted.test.mjs plugins/spec-loop/scripts/slice_wave_replan.test.mjs
claude plugin validate .
```

For a slice touching only `quality_gate.py` + `test_quality_gate.py`, segments 3 and 4 are the
load-bearing ones; run 1, 2, 5, 6, 7 too before claiming DONE (`tests.scope == "full"` is
required for a slice to merge).

Fast inner loop while iterating:
`python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_quality_gate.py'`

## 2. Hard rules — violating any of these fails CI

- **Stdlib only, forever.** No third-party imports. Stated at `README.md:53`, `plugins/spec-loop/README.md:20`, and `QG:2`. `lizard`/`radon` are detected read-only via `shutil.which`, never imported, never installed.
- **No type hints** anywhere in plugin scripts (`QG` has zero; `grep -c "^def .*->"` → 0). Describe shapes in the docstring instead.
- **No new module.** `plugins/spec-loop/scripts/test_doctrine_run_docs.py:147` pins the literal string `**Scripts (14 runtime + tests)**` in `plugins/spec-loop/README.md:167` against a live count of non-test `.py` files on disk. Adding one breaks CI until the README inventory is updated. Combined with the standing "no shared helper module between plugin scripts" rule, **all work lands inside `quality_gate.py` itself**.
- **Coverage floors, two of them, both independent.** `scripts/measure_coverage.py:151` floors `quality_gate.py` at **86%**; `:160` sets `TOTAL_FLOOR = 90` across all 15 targets. Only the 2-line `__main__` shim is omitted, and `test_measure_coverage_manifest.py:23` pins that shim at exactly 2 lines — it cannot be widened. **Every new line you add is in the denominator.**

  **Measured baseline at intake (2026-09-10, this tree):** `quality_gate.py` **93.9%, 841/896**
  executable lines hit, floor 86. TOTAL 97.1% (7160/7371), floor 90. Suite: 1918 tests, green.
  (The floor table's inline comment says "local 91.6% (2026-07-30)" — that is stale; 93.9 is
  the number to reason from.) Arithmetic for the slack: with 841 lines hit, the file stays
  above its floor while `841/(896+N) >= 0.86`, i.e. **N <= 82 wholly untested new lines**.
  That is genuine headroom, not licence — write the tests — but it means a well-tested
  change of this size cannot plausibly breach the floor, and a slice that claims it must
  weaken coverage to land is wrong. There is no per-change exemption; do not touch
  `scripts/coverage_omit.txt`.
- **Docstring on every function.** Mark side-effect-free ones `(PURE)` — 35 existing occurrences; trailing-`(PURE)` form dominates the newer routing block (`QG:534-1075`) and is the form to copy.
- **Atomic writes** via `tempfile.mkstemp` + `os.replace` (not relevant to this run — QG writes nothing).
- **Tests are stdlib `unittest`, never pytest.** `test_<module>.py` beside `<module>.py`.
- Line length: 79-column target, loosely held (44 lines exceed it, max 102). Respect 79 in the routing/mask block, which currently does.

## 3. The module map — language routing

### Two distinct language axes, deliberately separate

- `_lang_for(path)` → `"python"` | `"cbrace"` | `None` — the **extraction/nesting family**. `QG:441`.
- `_scan_lang_for(path)` → `"python"` | `"js"` | `None` — the **scan-mask language**. `QG:445`.

`"cbrace"` is deliberately NOT a mask language; `test_the_extraction_family_name_is_no_longer_a_mask_language` (`TEST:921`) pins that. Rationale for the exclusions is an 8-line measured argument at `QG:120-131` — read it before touching `_JS_MASK_EXTS`.

### `_EXT_LANG` (`QG:107-118`) — 16 entries, exactly two values

`.py` → python. `.js .jsx .mjs .cjs .ts .tsx .java .cs .go .c .h .cpp .cc .hpp .rs` → cbrace.

### Call graph (the ONLY `analyze_builtin` call site is `QG:1279`)

```
main QG:1573 → run_gate QG:1535 → measure QG:1238  [file loop QG:1271]
  ├─ run_lizard / run_radon                      QG:1256-1257
  ├─ analyze_builtin QG:1279
  │    ├─ _lang_for QG:1088        → None ⇒ early return ([], None)  QG:1089-1090
  │    ├─ _scan_lines_for QG:1092  → _strip_for_scan QG:1052 → _mask_for_lang QG:878
  │    ├─ _extract_functions_for QG:1093
  │    │    ├─ _extract_functions_python QG:892
  │    │    └─ _extract_functions_cbrace  QG:918
  │    │         ├─ _looks_like_call_or_control QG:928
  │    │         └─ _match_brace_end            QG:936
  │    ├─ _intersects_changed QG:1097   (skip fn if no overlap)
  │    ├─ _function_metrics QG:1102
  │    │    ├─ _branch_count(scan_body)           → cyclomatic_complexity  QG:1067
  │    │    ├─ _nonblank(body_lines)              → method_lines           QG:1068
  │    │    ├─ _count_params(header_line)         → parameter_count        QG:1069
  │    │    ├─ _cognitive_approx(scan_body, lang) → cognitive_complexity   QG:1070-1071
  │    │    └─ _nesting_depth_for(body_lines,…)   → nesting_depth          QG:1072
  │    └─ class_lines: _spans_overlap + _nonblank(lines)   QG:1105-1107
  ├─ _merge_backend_and_heuristic QG:1295
  └─ _lang_for QG:1300 ⇒ skipped "unsupported file type for analysis"  QG:1301-1302
```

`lang` is computed once at `QG:1088` and threaded as a plain string. The two routers are 3 lines each (`_extract_functions_for` `QG:1031`, `_nesting_depth_for` `QG:1038`) — **these are the natural extension points for a new family.**

### The function-record contract (both extractors return this)

`{"name": str, "start": int, "end": int, "header_idx": int}` — `start`/`end` **1-based inclusive**, `header_idx` **0-based**, always `start - 1`. Built at `QG:915-916` (python) and `QG:940-941` (cbrace). `_function_metrics` slices `lines[fn["header_idx"]:fn["end"]]` (`QG:1062-1064`) — mixing 0-based start with 1-based end is what makes the slice inclusive. **A new extractor MUST return this exact shape.**

The emitted *finding* is a different dict: `{"file", "function", "line_start", "line_end", "metrics"}` (`QG:1099-1103`).

### Indent model as it exists today (the thing to be generalised)

- `_extract_functions_python` (`QG:892-916`): `_PY_DEF_RE.match` per line; body scans forward from `i+1`, skipping blanks, breaking on the first non-blank line with indent `<= indent`. Indent via bare `lstrip()` (strips tabs too).
- `_nesting_depth_python` (`QG:972-982`): indent via `lstrip(" ")` — **spaces only, inconsistent with the extractor's bare `lstrip()`**. Depth = `max(0, indent - base_indent) // 4` — **a hardcoded 4-space step**.
- `_cognitive_approx` python branch (`QG:1005-1013`) repeats the same `// 4` step.

**Both facts are load-bearing for any generalisation.** A 4-space step is a Python convention; Ruby is conventionally 2-space, so reusing `// 4` unchanged would halve every Ruby nesting depth and under-report — the one direction this heuristic is never allowed to move (see §5). Any indent family needs its step size as a parameter, and needs the tab handling made consistent.

### Brace model

- `_extract_functions_cbrace` (`QG:918-941`): `_CBRACE_DEF_RE.search`, guarded by `_looks_like_call_or_control`; falls through to `_CBRACE_ARROW_RE` (which is **not** guarded). `_match_brace_end` returning `None` silently drops the candidate.
- `_nesting_depth_braces` (`QG:985-996`): character walk, returns `max(0, max_depth - 1)`.

### `class_lines` is NOT language-routed

`QG:1105-1107`: whole-file `_nonblank(lines)` count, emitted once per changed file whether or not it contains a class. `_PY_CLASS_RE` (`QG:147`) is **defined and never used** — dead code, do not assume it participates.

## 4. Branch counting — one global, language-blind set

```python
_BRANCH_WORDS = ("if","elif","case","catch","for","while","when")   # QG:136
_BRANCH_OPS_RE = re.compile(r"&&|\|\||\?(?!\?)")                    # QG:141
```

Already mixed-family (`elif` is python-only; `case`/`catch`/`when` are not). Python's `and`/`or` are deliberately NOT counted — pinned by `test_counts_keywords_and_operators` (`TEST:575`). `else if` deliberately absent from the ops regex to avoid double-counting (`QG:138-140`).

**The seam for per-language branch words:** `_branch_count(text)` (`QG:884`) takes no `lang` today, but its single call site `QG:1067` sits inside `_function_metrics`, which holds `lang`. `_cognitive_approx` (`QG:999`) already receives `lang` but uses it only to pick the indent-vs-brace weighting, not the word set. Both dispatch on the extraction family, not the scan language.

## 5. `_CONTROL_WORDS` — defect D1's home

`QG:944-945`, 9 entries, **undocumented** (the only module constant in the file with no explanatory comment block):

```python
_CONTROL_WORDS = {"if","for","while","switch","catch","else","do","return","case"}
```

`_looks_like_call_or_control(line, match)` (`QG:948-953`) — **the `line` parameter is accepted and never used**; the body is a one-line set membership test. Its docstring claims "or a function CALL" but there is no call-detection logic. One call site: `QG:928`, guarding the `_CBRACE_DEF_RE` path only.

**No direct test exists** for `_CONTROL_WORDS`; behaviour is covered indirectly by `test_control_keyword_not_treated_as_function` (`TEST:1138`), which only asserts `"if"` is absent from a JS fixture.

## 6. The safety direction — the design premise you must not break

`QG:116-132` argues it explicitly with a measured counter-example: the heuristic may **over**-count but must never **under**-count, because an over-count is a false alarm a human dismisses while an under-count is a real violation that ships. `.rs`, `.c`, `.cpp`, `.go`, `.java`, `.cs`, `.jsx`, `.tsx` stay on raw text for exactly this reason.

Defect D2 (`foreach` absent from `_BRANCH_WORDS`) breaks this premise for C#. Any fix must move counts in the safe direction or leave them unchanged.

## 7. Known measured holes (context, not necessarily this run's scope)

- **The skip record is an `elif` chain** (`QG:1293-1302`): a file gets a `skipped` entry only when there were no backend records AND no heuristic functions AND `_lang_for` is `None`. **A `.rs` or `.cs` file with zero extractable functions produces neither a measurement nor a skip** — it vanishes silently.
- A diff of only unsupported files yields `summary: {pass: true, checks: 0, vacuous: true}` and exit 0. Measured on a Ruby-only diff. Only `references/phase-5-integration.md:14` tells any reader to check `vacuous`; the per-slice path does not.
- **No user-facing doc anywhere states which languages the gate supports.** Grepped across both READMEs, `commands/quality-gate.md`, `references/*.md`. `commands/quality-gate.md` documents the config schema in full but never names a language or extension.

## 8. Test-file idioms to match

- Stdlib `unittest`; `import quality_gate as qg` after `sys.path.insert` (`TEST:37-40`).
- **Fixtures live at module level, not inside test methods** — banner at `TEST:43-47` explains why: *the gate measures function bodies, so a fixture inside a test method is counted as that method's own branching.* This suite is measured by the gate it tests. Put new multi-line source fixtures at module level.
- Paren-aligned continuations read as real nesting to the metric under test (`TEST:175-177`) — use 4-space hanging indents in new test code.
- **New language-routing tests come in PAIRS**: one unit-level assertion on the helper, one end-to-end `analyze_builtin(path, SOURCE, [(start, end)])` assertion. Doctrine stated at `TEST:896-906`: *"this drives the routing through the product entry point, so a mis-wired analyze_builtin fails here rather than passing on hand-composed calls."*
- Each such test opens with a `#` comment naming the defect and the **measured** before/after numbers. Copy `test_a_rust_lifetime_pair_keeps_both_branches` (`TEST:874-884`) as the model.
- Naming: newer classes use full-sentence assertions — `test_the_other_brace_extensions_are_left_on_raw_text`. Use that form.
- Home for routing tests: `TestScanLangForPath` (`TEST:834`). Home for the cbrace path: `TestAnalyzeBuiltinCbrace` (`TEST:1123`). Home for branch counting: `TestBranchCount` (`TEST:571`). Home for nesting: `TestNesting` (`TEST:598`).
- Gaps you may need to fill: **no test enumerates `_EXT_LANG`**; **no test calls `qg.measure(` at all**, so the `measure()`-level skip record is entirely uncovered.

## 9. Commit + docs shape

- One commit carries **code + its tests + the prose surfaces that describe it**. Verified against `c83a9ab`, `7bdeb1c`, `ea3625c`.
- Conventional-commit subjects: `feat(gate):`, `fix(gate):`. Body names the run id.
- `CHANGELOG.md` has a `## [Unreleased]` section (`:8`, currently empty). Add there. Entry shape: a **bold one-sentence claim**, then prose naming exact files/keys touched and explicit "Known, documented residuals". Model on the `[2.5.0]` block at `:10`.
- **No version bump.** `scripts/release.py` owns `plugin.json` / `marketplace.json`; scripts changes never touch them.
- Seven `test_doctrine_*.py` files pin prose against code. None currently pins quality-gate language prose — but if you ADD such prose, check whether a doctrine test should pin it.

## 10. Prior-run knowledge (from the graph)

- *"A one-line edit to an already-oversized file pulls a pre-existing gate violation into your diff"* (2026-09-08). Both files here are far over the 300-line `class_lines` threshold (1403 and 1629 non-blank). **Every slice in this run will report a `class_lines` FAIL.** It is pre-existing debt, not your code. Do not refactor to chase it; do not weaken the threshold.
- *"Re-measure the quality gate yourself; a sidecar's quality block is often a pre-fix snapshot"* (2026-09-09). If you read a quality block, confirm it against a fresh measurement before acting.

## 11. THE RUN CANNOT MEASURE ITS OWN FIX

`quality_gate_cmd` points every agent at `<plugin_root>/scripts/quality_gate.py` — the frozen
`~/.claude/plugins/cache/spec-loop/spec-loop/2.5.0/` copy, verified byte-identical to the repo
copy at intake. **Editing the repo copy does not change the gate that measures this run's
slices.** That is deliberate and desirable — a stable measuring stick — but it means:

- The ONLY admissible evidence that a defect is fixed is the repo copy's own unit tests, run
  directly against `plugins/spec-loop/scripts/quality_gate.py`.
- No agent may claim a defect fixed because a gate run came back green. A green gate here says
  nothing about the change.
- To demonstrate new behaviour by hand, invoke the REPO copy explicitly by path.

Precedent for the inverse hazard: run 20260826's runbook — *"running them against the frozen
cache makes the check vacuous."*
