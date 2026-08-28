# conventions.md — spec-loop-2, run 20260827

Written at intake by the controller from two `Explore` passes plus the knowledge graph.
**Read this instead of re-exploring.** Every claim below was verified by reading code or
running a command; anything marked `UNVERIFIED:` says how to check it.

Companion file in this same directory: **`findings-map.md`** — per-item verified `path:line`
ground truth, blast radius, and fix shape for every deferral this run closes. Read it for
your own item; do not re-derive it.

Baseline measured at intake, on `main` @ `299f0db` (2.2.1), all six segments green:

| segment | result |
|---|---|
| `python3 scripts/validate_marketplace.py .` | OK |
| `python3 -m unittest discover -s scripts -p 'test_*.py'` | Ran 106, OK (~26s) |
| `python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'` | Ran 1159, OK (~21s) |
| `python3 scripts/measure_coverage.py` | PASS, TOTAL 96.7% vs 90% floor |
| `node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs` | 48 tests, 48 pass |
| `claude plugin validate .` | (run as the last segment; validated OK at intake via validate_marketplace) |

Run each segment as its OWN tool call. A single monolithic invocation has been killed
mid-run in a past run and read as a false red.

---

## Prior decisions and patterns from the knowledge graph

These are settled. Do not re-litigate them, and do not re-discover the patterns the hard way.

**Settled human decisions (run 20260826, `answers-recorded.md`):**

- **A2 — the trigger is exactly ONE value, spelled `internal-error`**, covering both the
  caught-exception case and the slice-returned-nothing case. Not two values. Substring-safe in
  both directions against all six other triggers, because `run_metrics._legacy_match_triggers`
  matches by containment.
- **A3 — automatic retry of a crashed stage is OUT.** Confirmed by the human and independently
  declined by the `skeptic` lane. This run does not revisit it.

**Patterns this run is directly walking into (from the graph, most relevant first):**

1. *"A test that asserts against a re-implementation protects nothing"* — generalised from
   *a-record-that-outgrows-its-render-limit-loses-the-diagnostic-it-added*: when a rendered
   artifact truncates a field at a fixed length, reordering to protect one payload silently
   evicts whatever now sits past the limit. INTG-1 is this pattern's test-side twin.
2. *a-cause-overclaim-recurs-until-you-ban-the-phrase-not-the-instance* — removing an
   unprovable claim from one site does not remove the habit that wrote it; the same claim
   reappears in the next file describing the same thing. **This is why the prose sweep must
   grep for the CLAIM, not visit the five cited line numbers.**
3. *an-audit-of-a-self-report-must-not-itself-be-self-reported* — a slice tasked with
   re-verifying another agent's clean-sweep claim returned its own clean claim with no command
   output, and had missed a live contradiction. **Any "I swept everything" claim in a slice
   report must be backed by the pasted output of the grep that swept it.**
4. *a-per-run-patch-to-generated-orchestration-does-not-survive-a-new-dispatch* — dispatching
   by NAME pulls a clean copy from the installed cache. This is why this run pins `plugin_root`
   to an explicit frozen snapshot and dispatches by `scriptPath`.
5. *an-absent-key-and-a-null-honest-one-are-indistinguishable-through-.get()* — a null-honest
   metric is only readable if the key is PRESENT.
6. *recording-a-judgement-is-not-acting-on-it-say-which-you-built* — separate the levers that
   change behaviour from the channels that merely observe it, and say which you shipped.
7. *a-verdict-that-adjudicates-one-of-two-remedies-is-incomplete* — where a finding offers two
   remedies, refusing one is not a verdict. **INTG-2 offers two remedies (rename to four, or
   add a doc-prose assertion). Whichever you pick, say in the report why you did not pick the
   other.**

---


Repo root `/Users/zachmcmurry/Documents/Repos/spec-loop-2`. Plugin root
`plugins/spec-loop/`. All commands below were actually run on 2026-08-27.

## Test & build

Commands, verbatim from `.github/workflows/validate.yml:15-70`:

1. `python3 scripts/validate_marketplace.py .` — manifest validation. Fast.
2. `python3 -m unittest discover -s scripts -p 'test_*.py'` — ran it: **106
   tests, OK, 19.7s wall**. (This is the dev/CI-tools suite: `release.py`,
   `validate_marketplace.py`, `measure_coverage.py` and their tests, which
   live in root `scripts/`, NOT `plugins/spec-loop/scripts/`.)
3. `python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'`
   — ran it: **1159 tests, OK, ~18-34s wall** (varies run to run; second
   invocation via the coverage tool below reported 1265 because it also
   pulled in `scripts/test_measure_coverage.py`-adjacent counts — see below).
   Stray stderr lines (`error: provide a PR URL...`, `error: unsupported
   host 'gitlab.com'...`) are EXPECTED — `test_pr_resolver.py` and
   `test_review_package.py` deliberately exercise CLI error paths that print
   to stderr; they are not failures. Not slow, but not instant — plan ~20-35s.
4. `python3 scripts/measure_coverage.py` — ran it: **PASS, 1265 tests
   passed, ~20s wall**. This re-discovers and re-runs BOTH suites above
   under `trace`, so it duplicates 2+3's work — it's the slow one if you
   only need a pass/fail signal; run 2/3 individually for fast iteration.
5. `node --test --experimental-test-coverage
   plugins/spec-loop/scripts/dashboard_assets/index.test.mjs` — NOT run by
   me (no node test run performed this pass); CI additionally requires >=12
   tests parsed from the TAP summary (`validate.yml:56-62`).
6. `claude plugin validate .` / per-plugin-dir validate — NOT run (requires
   installing `@anthropic-ai/claude-code` globally); skip unless touching
   plugin manifests.

### Coverage floor mechanics (`scripts/measure_coverage.py`)

Stdlib-only (`trace` module + `compile()`/`co_lines()`), no coverage.py.
Floors are **hardcoded per-file integers**, `PER_FILE_FLOORS` at
`scripts/measure_coverage.py:125-139`, plus one `TOTAL_FLOOR = 90` at
`:140`. Only the 13 files in `TARGET_FILES` (`:85-99`) count toward
coverage, and `run_state.py`, `run_metrics.py`, and `quality_gate.py` are
all three among them (they live under `plugins/spec-loop/scripts/`, but
`TARGET_FILES` keys them by canonical `scripts/<name>.py` string; the
actual on-disk file is located by basename via `_target_source_path` at
`:404-417`, which searches both `SCRIPTS_DIR` and `PLUGIN_SCRIPTS_DIR`).
`test_*.py` files themselves are NEVER measured — only product modules.

Actual measured run today (`scripts/measure_coverage.py` output):
```
scripts/quality_gate.py    91.7%   638/696   floor 86%
scripts/run_metrics.py     98.6%  1303/1321  floor 93%
scripts/run_state.py      100.0%   671/671   floor 95%
TOTAL                      96.7%  5972/6173  floor 90%
```
So current margins above floor: quality_gate ~5.7pts (≈40 executable
lines of slack before breach, since floor is a % not a raw count — a
proportional statement, not literal budget), run_metrics ~5.6pts, run_state
5pts exactly (tightest of the three — **any newly-added, unexercised line
in run_state.py risks tripping its floor immediately** since it's already
at the 95% floor with only rounding room).

**What breaches a floor on a small edit to `quality_gate.py`, `run_state.py`,
`run_metrics.py`, or their `test_*.py` files:**
- Editing the `test_*.py` file alone changes nothing about coverage
  denominator, but CAN reduce numerator if it deletes/weakens an assertion
  path that previously drove product-code branches (e.g. removing a test
  case that was the only caller of an `else` branch).
- Editing the product file adds new executable lines (raises the
  denominator via `executable_lines()`, `:164-183`, which is a real
  `compile()`+`co_lines()` walk, not a text heuristic) — if the new lines
  (a new branch, guard, or helper) aren't hit by any test, numerator stays
  flat while denominator grows, dropping the percentage. `run_state.py` at
  exactly 100%/95%-floor has the least room: adding even a handful of
  untested lines can push it below 95%.
- The OMIT manifest (`scripts/coverage_omit.txt`, parsed by `parse_omit` /
  validated by `validate_omit` at `:270-296`) cannot be used to hide new
  code from measurement beyond `MAX_OMIT_FRACTION = 0.25` (`:82`) of a
  file's executable lines, and any OMIT range must have a `# rationale`
  or `parse_omit` raises — so a floor breach can't be papered over by a
  quick OMIT edit without real justification and it's capped anyway.
- **Rule of thumb for a later agent**: any new branch/line added to these
  three files needs an accompanying test that actually executes it, in
  the SAME slice, or coverage may go red on a change that looks
  behavior-correct.

## Python conventions in `plugins/spec-loop/scripts/`

- **Module docstring is a design essay**, not a one-liner: purpose,
  pipeline/stages as a numbered list, explicit design-decision bullets with
  bold lead-ins, exit codes, `Usage:` block. See `run_state.py:2-46` and
  `quality_gate.py:2-49` for full examples.
- **`(PURE)` marker convention**: any docstring for a function with no I/O,
  no clock, no globals mutated ends its one-line summary with `(PURE)`.
  Concentrated in `run_metrics.py` (19 hits) and `run_state.py` (33 hits),
  e.g. `run_metrics.py:839` `"""The summed count of ... (PURE)."""` and
  `run_metrics.py:846` `"""Non-null critique blocks ... (PURE)."""`. Used to
  signal "safe to unit-test with bare fixture objects, no mocking needed."
- **`_private` helper convention**: leading underscore = internal to the
  module, not part of the CLI/import surface. Pervasive — e.g.
  `quality_gate.py:418 _branch_count`, `:506 _nesting_depth_python`,
  `run_metrics.py:163 _read_text_capped`, `:228 _median`. Public (no
  underscore) names are the ones tests import directly and other modules
  would call (`validate_sidecar`, `render_report`, `compute_metrics`,
  `analyze_builtin`, `parse_diff`).
- **Comment density/tone**: long, argumentative, decision-justifying
  comments right above the code they defend, often citing a real incident.
  Two real examples:
  - `slice_wave_contract_base.py:2-17` — explains WHY this whole module
    exists by naming a real production outage ("an unguarded optional-field
    read aborted a whole wave and was mislabelled as a budget escalation").
  - `quality_gate.py:96-100` — `_BRANCH_WORD_RE`/`_BRANCH_OPS_RE`: "`else
    if` is NOT listed here: its `if` is already counted... would
    double-count the same branch."
  House style: comments justify a design choice against a rejected
  alternative, frequently reference a concrete incident/run-id
  (`20260825-scope-ceiling`), and are written in full sentences, not
  fragments.
- **Line length**: soft ~88-92 cols typical; hard cap not enforced by
  tooling (no linter config found — no `.flake8`/`pyproject.toml` lint
  section located). Measured max line lengths: `quality_gate.py` 102,
  `spec_loop_guard.py` 101, `run_state.py` 127 (one outlier), some test
  files run to 180 (fixture dict literals). Aim ~88-92 for new code to match
  the modal style; don't sweat a single long fixture line.
- **Type hints**: inconsistent by file, not absent project-wide.
  `run_metrics.py` and `scripts/measure_coverage.py` use
  `from __future__ import annotations` plus real annotations (dataclasses,
  `-> GateResult`, `dict[str, FileStat]`). `quality_gate.py` and
  `run_state.py` use **zero** type hints (plain argparse-CLI style,
  docstrings carry the types in prose instead). Match the file you're
  editing — don't introduce hints into `quality_gate.py`/`run_state.py`
  wholesale, that would be a style-inconsistent diff.
- **Import style**: stdlib-only across all scripts (design constraint, not
  incidental — every module docstring says "standard library only").
  Imports grouped stdlib-alphabetical, `from __future__ import annotations`
  first when present, then plain `import x` block, then `from x import y`
  block, e.g. `run_state.py:52-57`, `quality_gate.py` (module top). Test
  files add `sys.path.insert(0, str(Path(__file__).resolve().parent))`
  BEFORE importing the module under test (see next section for the exact
  block).

## Test conventions

- **Structure**: one `test_<module>.py` per product module, stdlib
  `unittest` only, discovered via `python3 -m unittest discover -s
  plugins/spec-loop/scripts -p 'test_*.py'`. Classes group by
  function-under-test with a `# ---- name ----` banner comment, e.g.
  `test_quality_gate.py:33` `# parse_diff — pure, embedded fixtures`,
  `test_run_state.py` groups around `TestValidateSidecar`.
- **No shared base test class across modules** — each `test_*.py` is
  self-contained; the ONE exception is the contract-test family (see next
  section), which shares `WorkflowSourceTestCase`.
- **Fixture/factory helpers**, defined at module top, right after imports,
  as plain functions (not fixtures/pytest):
  - `test_run_state.py:33 def escalation(**over):` — returns a full
    EscalationRecord dict with sane defaults, `over` dict overrides merged
    in with `.update(over)`.
  - `test_run_state.py:54 def sidecar(status="DONE", **over):` — full
    SliceResult sidecar dict; branches internally to add `split`/
    `escalations` keys when `status` is `"SPLIT"`/`"ESCALATED"`.
  - `test_run_metrics.py:69 def ev(ts, scope, type_, **payload):` — builds
    one `{"ts":..,"scope":..,"type":..,"payload":{...}}` event dict; used
    to build big `V2_EVENT_OBJECTS` lists (see `test_run_metrics.py:76+`).
  - `test_dag.py:30 def sl(slice_id, deps=(), status="pending", depth=0,
    parent=None, risk_tier=1, **over):` and `:47 def make_dag(slices=None,
    waves=None, **over):` and `:66 def wave(index, slice_ids,
    status="dispatched", workflow_run_id=None):` — dag.json fixture
    builders.
  - `test_dashboard_server.py:38 slice_obj`, `:85 wave`, `:90
    write_sidecar(run_dir: Path, ...)`, `:119 escalation_record`, `:128
    write_events`, `:157 fake_run_metrics` — the richest fixture set,
    because dashboard tests need real files on disk.
  All are **plain module-level functions**, `**over`/`**overrides` kwarg
  pattern for customizing one fixture without repeating the whole dict.
  A later agent adding fixtures to a NEW test file should follow this same
  pattern (function + `**over`), not introduce a class-based factory or a
  third-party fixture lib.
- **Assertion helpers**: defined as methods on a `TestCase` subclass, not
  free functions. `test_run_state.py:93 def assertValid(self, obj):` (calls
  `rs.validate_sidecar(obj)`, asserts `== []`) and `:96 def
  assertMentions(self, obj, needle):` (asserts errors is non-empty and one
  error string contains `needle`). Scoped to `class TestValidateSidecar`
  only in that file — not shared globally; re-declare locally if a new
  test class in a new file needs the same pattern.
- **Test method naming**: long, full-sentence, no abbreviation —
  `test_the_crash_record_names_the_last_dispatched_stage_without_overclaiming`
  (`test_slice_wave_contract_crash.py:93`), `test_a_lost_slice_is_an_internal_error_too`
  (`:201`), `test_deferred_scope_reaches_the_reviewer_as_quoted_advisory_data`
  (`test_slice_wave_contract_scope.py:76`). The name IS the spec; a docstring
  under it (when present) adds WHY, often citing an incident.
- **WHY-in-comments**: e.g. `test_run_metrics.py:8-16` explains the fixture
  strategy (`V2_*` vs `LEGACY_*`) and WHY (`the drift they must accept`);
  `test_run_metrics.py:77-82` explains a specific timestamp choice
  ("deliberately set to wave-collection time... so any regression that
  reconstructs durations from `ts` produces visibly wrong numbers instead
  of plausible ones").
- **New test file import block** (copy this shape exactly):
  ```python
  import sys
  # ...stdlib imports...
  from pathlib import Path
  from unittest import mock

  sys.path.insert(0, str(Path(__file__).resolve().parent))

  import <module_under_test> as <alias>  # noqa: E402
  ```
  (`test_run_state.py:15-27`, `test_quality_gate.py:21-30` are exact
  templates.)

## The contract-test architecture

`plugins/spec-loop/scripts/slice_wave_contract_base.py` is infrastructure
ONLY — it carries no `test_*` method (its one class,
`WorkflowSourceTestCase` at `:268`, has zero test methods), so `unittest
discover -p 'test_*.py'` never collects it directly even though its name
doesn't match the glob anyway. Rationale in its own docstring
(`:2-38`): the wave workflow is JS, never executed by this repo's Python
suite (it's resolved at runtime from the installed plugin cache), so these
are the cheapest honest coverage available — real `node --check` parsing
plus pinned source-text assertions, not behavioral execution.

- **`WorkflowSourceTestCase`** (`:268-292`, base class every contract test
  class extends): `setUp` sets `self.src = SOURCE` (the raw workflow file
  text, loaded once at module level via `SOURCE = WORKFLOW.read_text(...)`
  at `:53`). Provides `line_containing(needle)` (asserts EXACTLY one source
  line contains `needle`, returns it — fails loudly if an anchor moved or
  duplicated) and `between(start_needle, end_needle)` (source slice between
  two anchors, both required to exist).
- **JS source loading**: `WORKFLOW = Path(__file__).resolve().parents[1] /
  "workflows" / "slice-wave.workflow.js"` (`:52`) — reads the real shipped
  workflow file, not a copy/fixture. `wrapped_source()` (`:260-265`) wraps
  the raw source (which has top-level `return`/`export const`, invalid
  outside the Workflow tool's async wrapper) in
  `async function __wrap(){ ... }` so `node --check` can do a REAL parse —
  used by `TestTheFileStillParses` in `test_slice_wave_contract_scope.py:40-41`.
- **Module-level string constants**: every pinned JS snippet
  (`TASK_RESULT_REQUIRED`, `CRASH_TRIGGER`, `TRIGGER_ENUM_LINE`, etc. —
  ~70 constants, `slice_wave_contract_base.py:62-190`) is named at module
  scope rather than inlined as a literal in a test body. Two stated reasons
  (`:34-38`): (1) keeps assertions byte-exact and refactor-visible; (2)
  **quality_gate.py's own heuristic would misscore these test files** if the
  JS snippets were inline — a `&&`/`if` inside a string literal counts as
  real branching (`cognitive_complexity`), a paren-aligned continuation
  counts as real nesting (`nesting_depth`). This is a DIRECT, explicit
  callout of the exact gap the "strip string literals" work would close.
- **Source-text contract assertion pattern**: `self.assertIn(SOME_CONSTANT,
  self.src)` or use `line_containing`/`between` then assert on the
  substring — proves a guard/behavior is textually present, explicitly
  does NOT prove it behaves at runtime (stated in the base module docstring,
  `:26-28`).
- **Split of responsibility across the three `test_slice_wave_contract*.py`
  files** (all import from the base module, all `WorkflowSourceTestCase`
  subclasses):
  - `test_slice_wave_contract.py` — general contract: file-still-parses,
    optional TASK_RESULT field guards (commits/touched_files/etc.),
    quality-gate-block answer injection, over-scope record-only-ness.
  - `test_slice_wave_contract_scope.py` — deferred/over-scope semantics:
    one event per defer-hinted concern, payload shape, scope marker
    booleans, `recordDeferrals` call-site guarding around SPLIT/ENDORSE/
    OBJECTION branches.
  - `test_slice_wave_contract_crash.py` — **this is the crash/
    internal-error surface** — `TestTheCrashRecordNamesTheLastDispatchedStage`
    (`:48`), `TestCrashesAreClassifiedAsInternalError` (`:69`, the bulk of
    the file — catch-all classification, stage-attribution text, exception
    text passthrough, no-overclaiming assertions, 400-char context render
    limit, lost-slice-is-internal-error, budget-exhausted wording
    preserved), `TestTheTriggerEnumAgreesAcrossAllFiveHomes` (`:236` —
    checks the trigger enum literal string is IDENTICAL across
    `run_state.py`'s `ESCALATION_TRIGGERS` tuple, `run_metrics.py`'s copy,
    `dashboard_server.py`'s copy, and the workflow JS enum — 5 total
    homes per the comment at `slice_wave_contract_base.py:94-95`).
  Rationale for the 3-way split (`:39-42`): each importing module must stay
  under the quality gate's 300-line `class_lines` threshold; split out of
  one prior 422-line module.
- **Constants specifically relevant to crash/internal-error work** (all in
  `slice_wave_contract_base.py`): `CRASH_STAGE_CONTEXT` (:120),
  `CRASH_STAGE_PRECISION` (:121), `CRASH_STAGE_OVERCLAIM` (:122),
  `CRASH_TRIGGER` (:123), `CRASH_STAGE_FALLBACK` (:124-126),
  `CRASH_TITLE_BRANCH` (:127-129), `CRASH_TITLE_UNGRAMMATICAL` (:130),
  `CRASH_CLASSIFIED_PASSTHROUGH` (:131), `CRASH_OPTION_RETRY/SKIP/STOP`
  (:132-134), `CRASH_OPTION_CONTROLLER_ACTS` (:135-136),
  `CRASH_ERROR_FIRST`/`CRASH_ERROR_EXPR` (:137-138),
  `CRASH_CLASSIFICATION_SENTENCE` (:144), `CRASH_GUARD_ORIGIN_OVERCLAIM`
  (:145), `CRASH_HOST_LAYER_CAVEAT` (:146), `CRASH_CONTEXT_RENDER_LIMIT =
  400` (:151), `CRASH_STAGE_CAVEAT` (:152), `CRASH_CAUSE_OVERCLAIM` (:155),
  `CRASH_BUDGET_DENIAL_OVERCLAIM` (:156), `GUARD_BUDGET_TRIGGER` (:157),
  `SLICE_LOST_RECORD` (:158), `SLICE_LOST_CAUSE_DENIAL` (:161),
  `GUARD_FIRED_OVERCLAIM` (:168), `SLICE_LOST_GUARD_PROVABLE` (:169),
  `SLICE_LOST_CAUSE_UNKNOWN` (:170), `TRIGGER_ENUM_LINE` (:95),
  `STAGE_ASSIGNMENT`/`STATE_STAGE_INIT` (:117-118),
  `DISPATCH_GUARD_CALL` (:119). Also the actual JS: workflow trigger enum
  at `plugins/spec-loop/workflows/slice-wave.workflow.js:40` includes
  `'internal-error'` alongside `'budget-exhausted'`; the catch-all crash
  classifier is around `:890-892`; the lost-slice escalation is `:919`.

## Quality gate

`plugins/spec-loop/scripts/quality_gate.py` (1119 lines) — stdlib-only,
measures CHANGED code only (via `git diff --unified=0`), never installs
anything, prefers `lizard`/`radon` if present via `shutil.which`, falls back
to a labelled `builtin-heuristic`.

- **Builtin heuristic backend, keyword scanning**:
  - `_BRANCH_WORDS = ("if", "elif", "case", "catch", "for", "while",
    "when")` (`:95`), compiled as `_BRANCH_WORD_RE = re.compile(r"\b(?:%s)\b"
    % ...)` (`:96`) — whole-word match.
  - `_BRANCH_OPS_RE = re.compile(r"&&|\|\||\?(?!\?)")` (`:100`) — `&&`,
    `||`, ternary `?` (not `??`).
  - `_branch_count(text)` (`:418-423`): `1 + word_hits + op_hits` over the
    WHOLE joined body text (`body_text = "\n".join(body_lines)`, computed
    once in `analyze_builtin` at `:588`) — a single `.findall()` call over
    the full string, not per-line.
  - `_cognitive_approx(body_text_or_lines, lang, base_indent)` (`:533-558`)
    — PER-LINE `_BRANCH_WORD_RE.findall(stripped_or_line)` +
    `_BRANCH_OPS_RE.findall(...)`, weighted by nesting level (indent/4 for
    python at `:546`, brace-depth tracking for c-brace at `:551-557`).
  - `_nesting_depth_python`/`_nesting_depth_braces` (`:506-530`) do NOT scan
    keywords — pure indent/brace counting, unaffected by string-literal
    content except insofar as a string contains a literal `{`/`}` (brace
    variant) or literal leading whitespace pattern (python variant, less
    likely to matter).
  - **Every place raw source text is scanned for branch keywords**: exactly
    two call sites, both taking either `body_text` (str) or `body_lines`
    (list[str]) with NO string-literal or comment stripping beforehand:
    `_branch_count` (`:422-423`) and `_cognitive_approx` (`:547-548` python
    branch, `:553-554` non-python branch). Confirmed via `grep` — no
    `_strip_string`/`in_string`/comment-stripping logic exists anywhere in
    this file today. This is exactly the gap
    `slice_wave_contract_base.py:34-38` calls out by name (see contract
    section above) — its own JS constants would misscore if inlined.
  - **Exact functions "strip string literals before keyword scanning"
    would have to touch**: `_branch_count` (`:418`) and `_cognitive_approx`
    (`:533`) — both take the raw text/lines directly into
    `_BRANCH_WORD_RE.findall`/`_BRANCH_OPS_RE.findall` with no
    preprocessing step. A stripping helper would need to be inserted
    between `analyze_builtin`'s `body_text`/`body_lines` construction
    (`:587-588`) and these two calls, and would need per-language
    string-delimiter awareness (python `'`/`"`/triple-quote vs. c-brace
    `'`/`"`/`` ` `` template literals) since `_lang_for`/`_EXT_LANG`
    (`:372-373`, table above it) already distinguishes `"python"` from
    `"cbrace"` for other purposes.
- **Language detection**: `_lang_for(path)` (`:372-373`) — one-line
  `_EXT_LANG.get(os.path.splitext(path)[1].lower())` dict lookup, extension
  -> `"python"` or `"cbrace"` (js/ts/java/c#/go/c/c++/rust all bucket into
  `"cbrace"`). `_EXT_LANG` table sits directly above `_BRANCH_WORDS`
  (around `:85-93`).
- **Function extraction, JS vs Python**: `_extract_functions_python(lines)`
  (`:426-449`) — indent-based, walks lines after a `_PY_DEF_RE` match until
  indent drops back to/below the def's indent, trims trailing blanks.
  `_extract_functions_cbrace(lines)` (`:452-475`) — regex-signature match
  (`_CBRACE_DEF_RE` name+paren+brace, or `_CBRACE_ARROW_RE` for arrow
  functions) then `_match_brace_end` (`:489-503`) does a real brace-depth
  walk char-by-char to find the matching close. `_looks_like_call_or_control`
  (`:482-486`) filters out `if (...) {` etc. from being misread as function
  defs via a `_CONTROL_WORDS` set (`:478-479`).
- **`test_quality_gate.py` structure** (863 lines): sections banner-commented
  by pipeline stage (`parse_diff`, config loading, metric primitives,
  builtin-heuristic extraction, backend parsing/merging, coverage/CRAP,
  custom gates, thresholds, `main()`). Builtin-heuristic-specific classes:
  `TestBranchCount` (`:260`), `TestNesting` (`:287`, python indent + 2
  brace-depth cases), `TestCognitiveApprox` (`:319`, one test — nested
  branches weighted more), `TestAnalyzeBuiltinPython` (`:336`),
  `TestAnalyzeBuiltinCbrace` (`:379`). **No existing test asserts on
  keyword-inside-a-string-literal behavior** — grepped for
  `string liter`/comment-related test names, found none; this is genuinely
  new test surface, not a modification of an existing case.

## Key-file map

- `plugins/spec-loop/workflows/slice-wave.workflow.js` — the actual wave
  workflow logic (JS, run by the Workflow tool, not by Python tests).
- `plugins/spec-loop/scripts/slice_wave_contract_base.py` — shared infra
  for pinning JS source-text facts from Python (see section above).
- `plugins/spec-loop/scripts/test_slice_wave_contract_crash.py` — crash/
  internal-error contract tests.
- `plugins/spec-loop/scripts/test_slice_wave_contract.py` — general/
  task-result/quality-gate/over-scope contract tests.
- `plugins/spec-loop/scripts/test_slice_wave_contract_scope.py` — deferred/
  scope-record contract tests.
- `plugins/spec-loop/scripts/quality_gate.py` — the quality gate itself
  (heuristic backend detailed above).
- `plugins/spec-loop/scripts/test_quality_gate.py` — its test suite.
- `plugins/spec-loop/scripts/run_state.py` — sidecar/events/prose contract
  (`ESCALATION_TRIGGERS` tuple at `:64-65` is one of the "five homes").
- `plugins/spec-loop/scripts/run_metrics.py` — v2 metrics harness, own
  `ESCALATION_TRIGGERS`-equivalent copy (grep it before editing the enum).
- `plugins/spec-loop/scripts/dashboard_server.py` — read-only dashboard
  HTTP server + data layer; third copy of the trigger enum.
- `plugins/spec-loop/scripts/dag.py` — sole authority on run structure
  (`dag.json`), `sl()`/`make_dag()`/`wave()` fixtures live in its test file.
- `plugins/spec-loop/scripts/worktrees.py` — slice worktree/branch
  lifecycle; owns `run_git(repo_dir, *args)` (`:92`), the canonical git
  subprocess wrapper.
- `plugins/spec-loop/scripts/spec_loop_guard.py` — PreToolUse hook
  enforcing git invariants.
- `plugins/spec-loop/references/run-state-v2.md` — the on-disk contract
  spec; says explicitly "when this file and code disagree, fix one of them
  in the same change" — authoritative shape doc for sidecars/events/dag.
- `scripts/measure_coverage.py` — coverage floor gate (detailed above).
- `scripts/coverage_omit.txt` — OMIT manifest, rationale-required lines.
- `.github/workflows/validate.yml` — CI pipeline, source of truth for
  exact test/build commands.

## Reusable helpers a later agent must NOT reimplement

- `worktrees.py:92 run_git(repo_dir, *args)` — subprocess git wrapper;
  use this instead of hand-rolling `subprocess.run(["git", ...])`.
- `test_run_state.py:33 escalation(**over)` / `:54 sidecar(status="DONE",
  **over)` — sidecar/escalation fixture builders for `run_state.py` tests.
- `test_run_metrics.py:69 ev(ts, scope, type_, **payload)` — event-dict
  fixture builder for `run_metrics.py` tests.
- `test_dag.py:30 sl(...)` / `:47 make_dag(...)` / `:66 wave(...)` — dag.json
  fixture builders.
- `test_dashboard_server.py:38 slice_obj`, `:85 wave`, `:90 write_sidecar`,
  `:119 escalation_record`, `:128 write_events`, `:157 fake_run_metrics` —
  on-disk fixture builders for dashboard tests.
- `test_run_state.py:93 assertValid(self, obj)` / `:96 assertMentions(self,
  obj, needle)` — sidecar-validation assertion helpers (local to
  `TestValidateSidecar`; copy the pattern, don't expect it importable).
- `slice_wave_contract_base.py:268 WorkflowSourceTestCase` — base class for
  ANY new JS-source-text contract test; provides `self.src`,
  `line_containing()`, `between()`. A new crash-related contract test
  belongs in `test_slice_wave_contract_crash.py` extending this, not a
  fresh ad-hoc regex-on-file-text test.
- `slice_wave_contract_base.py:52-53 WORKFLOW`/`SOURCE` — the single
  already-loaded copy of the workflow file text; don't re-read the file in
  a new test module, import these.
- `measure_coverage.py:164 executable_lines(source, filename)` — real
  bytecode-derived executable-line set; if any future tool needs "what
  lines can Python actually land on," reuse this rather than a regex guess.

## Surprising / worth flagging

1. The exact task this brief anticipates — "strip string literals before
   keyword scanning" in `quality_gate.py` — is EXPLICITLY named as a known
   gap in `slice_wave_contract_base.py:34-38`'s own docstring, written by
   whoever built the crash-contract test suite. That module's ~70 pinned
   JS constants exist partly BECAUSE inlining them would trip
   `_branch_count`/`_cognitive_approx` on `&&`/`if`/nesting inside the
   string literals.
2. `run_state.py` sits at exactly 100% measured / 95% floor — the
   tightest margin of the three target files named in the brief. Any
   change there needs full line coverage in the same slice or CI goes red.
3. The two suite-discovery commands (`scripts/` vs
   `plugins/spec-loop/scripts/`) are genuinely separate dev-tool vs.
   shipped-runtime trees; `measure_coverage.py` discovers and RE-RUNS both
   under `trace`, so it's redundant with (and slower than) running the two
   `unittest discover` commands directly — use those two for fast
   iteration, only run `measure_coverage.py` before finalizing.
4. **CONTROLLER CORRECTION — the draft got this wrong, and the error is
   exactly INTG-2's subject.** The trigger enum has **FOUR** code homes that
   must agree verbatim, not five: `run_state.py ESCALATION_TRIGGERS`,
   `run_metrics.py`'s copy, `dashboard_server.py`'s copy, and the workflow JS
   enum. `slice_wave_contract_base.py TRIGGER_ENUM_LINE` is **not** a fifth
   home — it is the string that *locates* the JS enum line so the test can
   read the values out of it (`"trigger: { enum: ["`, a prefix carrying no
   values). Verified by reading
   `TestTheTriggerEnumAgreesAcrossAllFiveHomes`
   (`test_slice_wave_contract_crash.py:236`): its two test methods assert the
   three Python tuples against each other and then the JS enum line against
   `run_state.ESCALATION_TRIGGERS`. Four homes, five in the name. The comment
   at `slice_wave_contract_base.py:93` says "five homes" and then enumerates
   four. The genuinely unpinned homes are the **PROSE** enumerations in the
   docs. That this brief's own explorer miscounted on first read is evidence
   for the finding, not against it: treat the four/five question as settled
   ground truth and see `findings-map.md` item INTG-2 for the definitive
   prose-home list.
5. No linter/formatter config (`.flake8`, `pyproject.toml` lint section,
   `.pylintrc`) was found anywhere in the repo — style consistency here is
   entirely convention-enforced by review, not tooling. UNVERIFIED beyond a
   file-existence check; run `find . -maxdepth 2 -iname '*flake8*' -o
   -iname 'pyproject.toml' -o -iname '.pylintrc'` to confirm none appeared
   after this pass.
