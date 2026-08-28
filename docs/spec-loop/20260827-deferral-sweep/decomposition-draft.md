# Decomposition draft — run 20260827 (PROVISIONAL, for the intake council to challenge)

This is the controller's provisional slicing, written before the council ran so the council can
attack it. It is not final. `--max-parallel 5`, `--risk-floor 1`, no `--thorough`.

## Wave 1 — four slices, no shared files

### s1 — Make the two contract tests protect what they claim (INTG-1 + INTG-2). Tier 2
**Goal.** Two P2 test-integrity defects in the crash-contract suite, both instances of "an
assertion that claims more than it checks".

- **INTG-1**: `test_slice_wave_contract_crash.py`'s `rendered_crash_context()` re-implements
  `run_state._one_line()`'s collapse-and-truncate (`" ".join(text.split())`, then
  `[:limit - 1] + "…"`) and duplicates the limit as `CRASH_CONTEXT_RENDER_LIMIT = 400` in
  `slice_wave_contract_base.py` against a bare `400` literal inside
  `run_state.render_escalation()`. If either the production limit or the collapsing changes,
  the test stays green while the stage attribution silently vanishes from `escalations.md` —
  the exact regression it exists to prevent. Fix: name the `400` in `run_state.py` as a module
  constant, import it, and assert against real `run_state.render_escalation()` output rather
  than a local re-render.
- **INTG-2**: `slice_wave_contract_base.py:93` says the trigger enum has "five homes" and then
  enumerates four; `TestTheTriggerEnumAgreesAcrossAllFiveHomes` asserts across those four code
  homes. The unpinned homes are the PROSE enumerations. Two remedies are on offer — rename to
  four and record the prose as deliberately unpinned, OR add a doc-prose assertion. **Preferred:
  add the prose assertion** (it pins the exact file where the last run found a P1 divergence)
  **and** correct the name and comment to say what is actually covered. If you choose the
  rename-only remedy, say in the report why you rejected the assertion.

**Files (exclusive to s1 this wave).** `plugins/spec-loop/scripts/slice_wave_contract_base.py`,
`plugins/spec-loop/scripts/test_slice_wave_contract_crash.py`,
`plugins/spec-loop/scripts/run_state.py`.
**Note.** `run_state.py` is at 100.0% coverage against a 95% floor — the tightest margin in the
repo. A new constant adds no executable line; anything more must carry coverage.

### s2 — Quality gate: stop counting branch keywords inside string literals. Tier 3
**Goal.** `quality_gate.py`'s builtin heuristic scans raw source text, so control-flow words in
prose score as real branching. Three occurrences of the word "when" inside user-facing strings
pushed `runSliceError` to cyclomatic 12 / cognitive 22 on a function whose real branching is one
ternary. Today it sits at cognitive 14 against a threshold of 15 — thin headroom that exists only
because prose counts, so the next editor who writes `if` into an operator-facing message trips the
gate and the natural "fix" is to degrade the message.

**The correctness crux, and why this is Tier 3.** The strip must NOT blank template-literal
interpolations: the text inside `${ ... }` is real code and its `?:`/`&&`/`||`/`if` genuinely
branch. Blanking a whole template literal including its interpolations would under-count real
complexity and silently weaken a blocking gate for every future run, in every language — the
same code path measures Python, whose docstrings in this repo are long and prose-heavy. The
change may only ever LOWER a metric, never raise one, and must be demonstrated on both languages.

**Files (exclusive).** `plugins/spec-loop/scripts/quality_gate.py`,
`plugins/spec-loop/scripts/test_quality_gate.py`.
**Known co-change the slice must NOT make.** `slice_wave_contract_base.py:32-37`'s docstring
justifies its "every pinned JS snippet is a module-level constant" discipline partly by this very
gate behaviour. That rationale goes half-historical once this lands. **Do not edit that file** —
it belongs to s1 this wave. Report it and the controller will route it to wave 2.
**Coverage.** `quality_gate.py` is 91.7% against an 86% floor (638/696) — ~5.7 points of
headroom, the only realistic floor risk in this run. New code carries its own tests.

### s3 — Prose honesty: the lost-slice record, and the inline twin's step-3 trigger. Tier 2
**Goal.** Five residual prose defects, all one defect class: prose that describes
`internal-error` generically while asserting things true only of the caught-exception record.
Ground truth is `slice-wave.workflow.js`, never any prose. The two records are DIFFERENT shapes
— the caught-exception record passes three controller-named options; the lost-slice record
passes `options: []`, so `esc()` substitutes a single generic option.

- `CHANGELOG.md` (~:31) asserts the record carries three controller-named options; the
  lost-slice record does not.
- `skills/escalation-gate/SKILL.md` (~:78) says the lost-slice record states its own missing
  diagnostics (it does not) and implies skip/stop options it does not offer.
- `agents/slice-worker-fallback.md` (~:99) has a broken cross-reference — the no-result rule
  lives under Escalations, not Pipeline step 4 — and (~:98) describes behaviour for a real
  `BLOCKED` the workflow does not have.
- `agents/slice-worker-fallback.md` (~:98) **also** diverges on WHICH non-budget trigger an
  exhausted per-task retry raises: it says "material-assumption or review-block as fits" while
  the workflow classifies exactly that as `ambiguity`. `references/run-state-v2.md` is a third
  voice and appears to agree with the workflow. The workflow is what runs; move the docs to it,
  and quote the code line you matched to.
- `scripts/test_run_state.py` (~:200) cites a line number this same diff invalidated
  (`:204` → `:205`). Fix by citing behaviour, not a line number.

**Do not visit only the five cited line numbers.** The graph pattern
*a-cause-overclaim-recurs-until-you-ban-the-phrase-not-the-instance* says the claim reappears in
the next file that describes the same thing. Grep for the CLAIM across `references/`,
`commands/`, `agents/`, `skills/`, both `README.md`s — and paste the sweep's output in the
report. An unbacked "I swept everything" is not evidence.

**Files (exclusive).** `CHANGELOG.md`, `plugins/spec-loop/skills/escalation-gate/SKILL.md`,
`plugins/spec-loop/agents/slice-worker-fallback.md`,
`plugins/spec-loop/scripts/test_run_state.py`, plus any further prose site the sweep finds
EXCEPT `slice_wave_contract_base.py` (s1) and `quality_gate.py` (s2).

### s4 — Make the substring-safety test actually drive the matcher. Tier 2
**Goal.** `test_internal_error_is_substring_safe_against_every_other_trigger` asserts pairwise
containment between Python string literals and never calls
`run_metrics._legacy_match_triggers` — the containment-matching code the constraint exists to
protect. It would stay green if that matcher's semantics changed. Fix: drive real v1 prose
containing `internal-error` through the legacy path and assert the matched set, keeping the
naming constraint as well.
**Files (exclusive).** `plugins/spec-loop/scripts/test_run_metrics.py`.
**Tier rationale.** Test-only, so Tier 1 by the letter of `risk-tiers.md` — raised to 2
deliberately: this item exists *because* a test lied about what it covered, and a Tier-1 shape
is the one most likely to accept a new test that looks like it drives the matcher but does not.

## Wave 2 — one slice

### s5 — CHANGELOG `[Unreleased]` entry, and the rationale wave 1 made stale. Tier 2
deps `[s1, s2, s3, s4]`. Cannot run in wave 1: an accurate entry needs to know what actually
shipped, and writing it from a prediction would be this run's own defect class.
**Files.** `CHANGELOG.md` (the `[Unreleased]` section only — `## [2.2.1]` is s3's),
`plugins/spec-loop/scripts/slice_wave_contract_base.py` (the docstring rationale s2 made
half-historical, if s2 reports it).
**Not in scope.** No version bump, no release. Controller decision: entry under `[Unreleased]`,
publish handled at the Phase 5 prompt.

## Why this slicing

- **Exclusive file ownership per wave** is the ordering principle: no two slices in one wave
  name the same file, so a merge conflict is structurally impossible rather than merely
  unlikely. It is what forces `slice_wave_contract_base.py`'s docstring and `CHANGELOG.md`'s
  new entry into wave 2.
- s1 and s4 are the same defect class (a test asserting against a re-implementation) but sit in
  different files and are independently shippable, so they are two slices, not one — a bundle
  would fail the right-size gate.
- s2 is the run's only genuine behaviour change and the only Tier 3.

## Questions the controller is holding for the human (not for the council)

1. Which tier of the deferral list to close — trivial-only, or plus the twice-deferred
   `escalations.md` duplicate-section bug, or plus the two capability additions.
2. How to close 3.1 (the verifiability ceiling): frozen pre-run snapshot of the repo plugin tree
   as `plugin_root` + `scriptPath` dispatch, vs. staying on the installed 2.2.0 cache.
3. Whether to normalise `test_dashboard_server.py`'s knowingly-mixed indentation, which the
   source report recorded as a deliberate state rather than a fix request.
