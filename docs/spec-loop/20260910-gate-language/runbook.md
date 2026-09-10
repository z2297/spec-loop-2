---
schema_version: 2
run_id: 20260910-gate-language
generated: 2026-09-10T18:56:46Z
integration_branch: spec-loop-run/20260910-gate-language
base_branch: main
base_sha: fa01826d50b011e0666b2d5ce36ea5dc1a684837
merge_mode: single-branch
integration_gate: green-after-remediation
slice_counts: { complete: 4, split: 0, remediation: 1 }
gap_counts: { known_gaps: 4, deferred: 6, open_findings: 13 }
publish: pending
knowledge_graph: not recorded
---

# Runbook — 20260910-gate-language

## Executive Readout

**What we set out to do.** The request was "Fix the two defects found and enhance with an
indent-based model" — repair the two measured defects in the quality gate's builtin C-family
heuristic (`plugins/spec-loop/scripts/quality_gate.py`), and extend the analyzer's language
reach by generalising its indent-based model. The intake escalation on that third item was
answered by the human with "Neither — just fix the two defects", so the extension was dropped
and the run shipped defect repairs only.

**What shipped.** Four slices, all merged serially onto `spec-loop-run/20260910-gate-language`
(18 commits, base `fa01826d50b011e0666b2d5ce36ea5dc1a684837`, head
`2c22dd33654b616b055c8ef122cb5bdb5be3f31a`), no splits, one of them a remediation slice.
`s1`: control keywords (`foreach`/`using`/`lock`/`fixed` for C#, `synchronized` for Java) are
no longer extracted as phantom functions — but the suppression is CONDITIONAL ON ENCLOSURE, so
the phantom record is KEPT wherever no extracted function encloses it, because there it is the
only measurement that method body has. That conditionality is a human ruling, made after the
council raised a safety objection against the naive fix; s1 also makes every changed file the
gate cannot measure leave a skip record with a distinguishing reason instead of vanishing from
the report. `s2`: `foreach` now counts as a cyclomatic branch — it never did, because
`\bfor\b` does not match `foreach` — plus two false-prose corrections carried over from s1's
review. `s3`: tab-indented Python no longer measures as if it had no nesting; a new
`_py_indent_width` expands tabs at 4 columns across the extraction, nesting and cognitive
sites. `r1` (remediation): completes the tab fix so it survives literal-masking, corrects two
measurably false CHANGELOG claims, pins the downward direction with a test, and collapses a
duplicated enclosure bound whose unguarded `next()` could have aborted the gate for every
file. The run needed nine wave dispatches for four slices — s1 three, s2 one, s3 three, r1 two
— and one full remediation pass; roughly four hours wall clock, 63 agent dispatches, ~3.22M
subagent tokens.

**Integration status.** Integration branch `spec-loop-run/20260910-gate-language` at
`2c22dd33654b616b055c8ef122cb5bdb5be3f31a`. Phase 5 passed on attempt 2, after one remediation
slice: full seven-segment suite GREEN, measured fresh on the assembled whole (marketplace OK;
126 scripts tests; 1825 plugin tests, up from 1792 at baseline; coverage PASS with
`quality_gate.py` at 94.6% (912/964) against a floor of 86 and TOTAL 97.2% against a floor of
90 — coverage ROSE from the 93.9% intake baseline despite ~68 added executable lines; 48/48
node dashboard; 136/136 node wave harness; `claude plugin validate` twice). Whole-run quality
gate over `fa01826..HEAD`: 312 checks, vacuous FALSE read explicitly, 3 failures — all three
pre-existing and accepted under a standing ruling (whole-file `class_lines` on
`quality_gate.py` and `test_quality_gate.py`, plus `nesting_depth` on `_cognitive_approx`,
which measures byte-identically at `fa01826` and at HEAD). Cross-slice review verdict:
APPROVE_WITH_FINDINGS at tier 3, no P0 and no P1, over the 18-commit range. Nine escalations
were raised and all nine were answered; none is open. Publish state: PENDING — the human has
authorised merging to `main` and cutting a tagged release via `scripts/release.py`, with the
version level to be confirmed first, but nothing has been pushed.

**Gaps you should know about.**
- THE BIGGEST FINDING OF THE RUN, and it dwarfs both defects the run was called to fix:
  **function-level metrics do not fire on idiomatic C# at all.** `_CBRACE_DEF_RE` requires the
  `{` to sit on the signature line, and C# convention puts the method brace on its own line, so
  a pure-Allman C# class (the Microsoft/Visual Studio default) extracts ZERO functions —
  `cyclomatic_complexity`, `cognitive_complexity`, `method_lines`, `parameter_count` and
  `nesting_depth` never apply to it, and only whole-file `class_lines` does. Controller-measured
  first-hand through `analyze_builtin`, not inferred. It is pre-existing, not introduced here,
  and it was deferred because the only remedy is letting the signature detector span the
  newline — regex work the run's scope ceiling forbids, since `_CBRACE_DEF_RE` is shared by all
  15 brace extensions and its failure mode is dropping real definitions. The requester's own
  gate configuration (`tier3_surfaces` full of Migrations/Authentication/appsettings) is
  unmistakably .NET, so this very likely describes their real codebases.
- Three residuals from the final integration review ship unfixed. **N1 (P2)** is the
  highest-value follow-up: the downward path of the tab fix has its numbers pinned but its
  FAIL-to-PASS VERDICT FLIP is not — the new fixture in `TestTabIndentedPython`
  (`plugins/spec-loop/scripts/test_quality_gate.py`; exact line not recorded) deliberately chose
  a shape whose pass/fail verdict does not change, while a shape that does flip exists and was
  reproduced (cognitive 18 FAIL at base to 14 PASS at head, crossing a threshold of 15).
  **N2 (P3)**: `CHANGELOG.md:38` claims a change retires an existing violation and cites
  `nesting_depth` 10 to 9 and cognitive 21 to 18 — but 9 and 18 both still violate thresholds of
  3 and 15, so the cited method retires nothing; the general claim is true, the attached evidence
  does not demonstrate it. **N3 (P3)**: the docstring at
  `plugins/spec-loop/scripts/quality_gate.py:588-589` says the mask site and `_py_indent_width`
  use "the same bare `lstrip()`", inviting a substitution of the expanded column width for the
  raw character index that `:601` actually needs — they differ 4x on a tab row.
- Also shipping as recorded residuals: attempt 1's F5-F8 (`_has_any_callable` duplicating
  `analyze_builtin`'s preamble; two missing `(PURE)` markers; `_py_indent_width` called on
  non-python headers, verified harmless; a CHANGELOG bullet naming `_encloses_line`, since
  renamed `_strictly_encloses_line`), and r1's own four (the scan-mask SECTION HEADER comment
  in `quality_gate.py`, which still gives "a masked docstring continuation line starts at column
  0" as its reason and which r1's own change made false — line not recorded; `_cbrace_name_at`
  now sitting at `nesting_depth` 3 against a threshold of 3, passing with zero headroom; a
  doubled "hardcoded" phrase in the CHANGELOG residual paragraph; and `TestEnclosingRecord`
  being unit-only rather than paired), plus s2's two cosmetic P3s. Thirteen open findings in
  total, none at or above the tier-3 blocking bar.
- Deferred for successor runs: the Allman C# gap above; Java try-with-resources (`try (var r =
  open()) {`) extracting as a function named `try`, since `try` is absent from the nine global
  `_CONTROL_WORDS`; wiring `summary.vacuous` into the per-slice pipeline, so a slice touching
  only unsupported files stops passing with `checks: 0` and exit 0; and reading (B), a generic
  indent fallback for every unsupported extension, rejected on the merits by both plan-critic
  and guardian and logged deferred rather than dropped.
- WHAT WAS DELIBERATELY NOT BUILT: the indent-model EXTENSION, in full. No Ruby, no Kotlin, no
  new `_EXT_LANG` entry, no generic indent fallback, no step-size parameterisation — the
  hardcoded `// 4` stays, because no 2-space language is routed. This was the human's answer to
  the run's one intake question, not an omission.
- THE RUN'S CENTRAL STRUCTURAL CONSTRAINT: the gate that MEASURED this run is the frozen
  plugin-cache copy (`~/.claude/plugins/cache/spec-loop/spec-loop/2.5.0`, sha256
  `dc9f231adf375dc4d6aebee0542452df9caefeee79c198f3b19593c97b2a6e52`), verified byte-identical
  to the repo copy at intake. Editing the repo copy does not change the instrument. The run
  could therefore never measure its own fix, and unit tests executed directly against the repo
  copy were the only admissible evidence, at every stage, for every slice. No green gate result
  in this run is evidence that any defect was fixed.

**Key decisions made autonomously.**
- STANDING RULING at intake, precedent-resolved without asking: whole-file `class_lines` on
  `quality_gate.py` and `test_quality_gate.py` is accepted as pre-existing debt for every slice
  in this run (both were already far over the 300 threshold at base — 1403 and 1629 non-blank).
  A NEW function-level violation a slice's own code introduces remains a genuine block.
- Slices run fully serial (s1 to s2 to s3) rather than s1 then s2+s3 in parallel, because all
  three edit the same two files and the same `CHANGELOG.md [Unreleased]` section, where a
  conflict is certain rather than probable.
- The two intake answers were reconciled explicitly: the indent-model EXTENSION is dropped, the
  tab-handling DEFECT inside the existing Python model is fixed — the more specific answer
  governs where the two overlap.
- The prose-residual chase was capped, then the cap was bent once for exactly one order and the
  bend was recorded rather than quietly widened. Each prose correction this run made surfaced
  the next one; three prose rounds plus one remediation slice is where it stops.
- N1-N3 from Phase 5 attempt 2 ship as recorded residuals; no third remediation slice was spent.
- HUMAN-ANSWERED ESCALATIONS, all nine: (1) the intake ambiguity — "Neither, just fix the two
  defects", dropping the indent-model extension; (2) the corrected, larger scope for the phantom
  fix — language-scope the guard AND fix the skip record; (3) fix the tab under-count with its
  own regression test and CHANGELOG line, accepting that it changes existing Python results;
  (4) the s1 council safety objection — HUMAN RULING: make the suppression conditional on
  coverage, never unconditional; (5) the s1 quality-gate block — mechanical acceptance under the
  standing `class_lines` ruling; (6) the s3 crash — retry the slice, resolve the gate by
  acceptance; (7) the s3 review block — controller determination that the order was addressed,
  proceed to verify; (8) after Phase 5 attempt 1 — remediate F1-F4 in one slice, then publish,
  with the human additionally choosing a publish path beyond the offered options: push to main
  and cut a new release; (9) the r1 crash — retry at verify.

**PROCESS FINDINGS worth carrying forward** — as valuable as the code:
- A controller fix ORDER becomes a synthetic P1 finding with file `-` and line 0, and the
  re-reviewer adjudicates findings positionally against the fix diff, so it can never be marked
  ADDRESSED however completely the work is done. A slice given orders will escalate as
  `review-block` regardless of the fixer's work. Observed in the sharpest possible form on s3:
  the fixer satisfied the order twice, editing exactly the ordered bullet and nothing else, and
  the finding stayed open both times. Cost: two wasted fix rounds and one escalation.
- The verify-stage verifier died TWICE on an identical `StructuredOutput` schema failure — same
  stage (`verify:1`), same agent type, same four missing properties (`suite`, `quality`,
  `head_sha`, `tree_sha`), two different slices (s3 and r1), hours apart, two occurrences out of
  five verify dispatches. Each cost a full escalation cycle plus a re-dispatch. Both times the
  slice code was fine and a plain verify re-entry succeeded.
- The controller piped a `git merge` through `tail`, so the shell took `tail`'s exit status,
  `set -e` never saw the merge failure, and worktree cleanup DELETED the s3 branch before the
  merge had happened — for a moment the run state claimed a merged, complete slice that was not
  merged and whose branch no longer existed. Recovered by SHA, each step verified before the
  next. NEVER pipe a merge whose failure must stop a script.
- A wave-3 agent wrote to the MAIN repository working tree instead of its own worktree (the
  same CHANGELOG edit it had correctly committed on its branch), which is what caused the merge
  to be refused. Blast radius was small only because the stray content was identical to
  committed branch content.
- A stale s1-era `quality_gate.py` prototype in the session scratchpad SHADOWED the repo module
  for ambient `sys.path` imports and produced plausible-but-wrong numbers in one reviewer probe
  until it switched to explicit `importlib` loading. Every controller measurement was audited
  against this and none was contaminated; the file has been renamed.
- `dag.py record-wave` refuses a duplicate wave index and offers no update path, so a
  re-dispatched wave keeps a stale `workflow_run_id` unless the field is patched by hand.

**How to verify / operate.** From the repo root at
`spec-loop-run/20260910-gate-language`, run the seven suite segments as SEPARATE invocations (a
monolithic run hits the 10-minute ceiling and reads as a false red):
`python3 scripts/validate_marketplace.py .` ;
`python3 -m unittest discover -s scripts -p 'test_*.py'` ;
`python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'` ;
`python3 scripts/measure_coverage.py` ;
`node --test --experimental-test-coverage plugins/spec-loop/scripts/dashboard_assets/index.test.mjs` ;
`node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs plugins/spec-loop/scripts/slice_wave_radius.test.mjs plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs plugins/spec-loop/scripts/slice_wave_reentry.test.mjs plugins/spec-loop/scripts/slice_wave_accepted.test.mjs plugins/spec-loop/scripts/slice_wave_replan.test.mjs` ;
`claude plugin validate .`.
The fast inner loop for this run's own work is
`python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_quality_gate.py'` — and
because the run cannot measure its own fix, that command against the REPO copy is the only
admissible evidence any of these defects is fixed. Expect 1825 plugin tests, TOTAL coverage
97.2%, and `quality_gate.py` at 94.6% against its 86% floor
(`scripts/measure_coverage.py:151`; TOTAL floor 90 at `:160`). Expect the quality gate to exit
1 with exactly three accepted pre-existing violations; that is the recorded steady state, not a
regression. No new CI gate, script or threshold was introduced by this run. Run metrics are at
`docs/spec-loop/20260910-gate-language/metrics.json`.

---

## 1. What Was Built

| Slice | Goal (abridged) | Files / subsystems | Branch → head | Status |
|---|---|---|---|---|
| s1 (tier 3) | Language-scope the C-family control-keyword guard with COVERAGE-CONDITIONAL suppression; keep the phantom record where no extracted function encloses it; give every unmeasured changed file a skip record; correct the `_looks_like_call_or_control` docstring. | `plugins/spec-loop/scripts/quality_gate.py`, `plugins/spec-loop/scripts/test_quality_gate.py`, `CHANGELOG.md` — quality-gate, language-routing, gate-reporting | `spec-loop/20260910-gate-language/s1` → `c52d9f2d0c550c72cf79caf1af893a839d87f4db` (merge `b574405e4b90c33a56ba02658a63ee37c6a5d8e4`) | complete (DONE) |
| s2 (tier 2) | Append `foreach` to `_BRANCH_WORDS` — global, case-sensitive, boundary-anchored; fold in three non-blocking prose residuals from s1's review, including a blanket safety claim measured FALSE for `parameter_count`. | same three files — quality-gate, branch-counting | `spec-loop/20260910-gate-language/s2` → `5ba3c6bf41598a826edfee0d865fce2109e79a1a` (merge `26adcad3c1c9ed2b2260bc2e2e11f1ca3ee5edcd`) | complete (DONE) |
| s3 (tier 3) | Fix the tab-indentation under-count in the EXISTING Python indent model: unify tab handling across the extraction, nesting and cognitive sites, expanding tabs before the divide; pin with a named regression test; fix one dangling CHANGELOG reference. | same three files — quality-gate, indent-model | `spec-loop/20260910-gate-language/s3` → `a5803509a7cc917f103731b5d4ee0f35cd6310e8` (merge `892a2aab98f10174fc296a8c8cd56a92a71a304c`) | complete (DONE) |
| r1 (tier 3, REMEDIATION) | The four actionable findings of Phase 5 attempt 1: complete the tab fix so it survives literal-masking (F1), correct two false shipped CHANGELOG claims (F2), pin the downward direction with a test (F3), collapse the duplicated enclosure bound and retire the stringly-keyed `state` bag (F4). | same three files — quality-gate, indent-model, gate-reporting | `spec-loop/20260910-gate-language/r1` → `7aba97ea7d05498a264b6378854d04f49025d206` (merge `2c22dd33654b616b055c8ef122cb5bdb5be3f31a`) | complete (DONE) |

No slice was split; `split_parents: 0`, `max_depth: 0`. Merge mode is single-branch: every
slice merged `--no-ff` onto `spec-loop-run/20260910-gate-language`, serially, in wave order.
Nine wave dispatches were spent on four slices (s1 ×3, s2 ×1, s3 ×3, r1 ×2). Per-wave
integration checks for waves 1, 2 and 4 were satisfied BY TREE IDENTITY — exactly one slice
merged and `git rev-parse <branch>^{tree}` equalled the sidecar's `tests.tree_sha`, checked
first-hand — which Phase 2 step 6 permits; wave 3's integration check is not recorded as an
`integration-check` event (its merge is the one described under the controller-error finding in
§5). The Phase 5 checkpoint itself was run fresh at both attempts, never transferred.

Iron Council: SKIPPED for s1, s3 and r1 at the slice level per tier routing;
ENDORSE_WITH_CONCERNS for s2 with 6 concerns folded and no over-scope flag. Across the run the
council returned 3 OBJECT and 2 ENDORSE_WITH_CONCERNS verdicts with 41 concerns total and one
safety objection — the s1 objection that produced the human ruling on conditional suppression.
Refactor radius was measured WITHIN its ceiling on all five occasions it was checked.

## 2. Business Logic

Rules the code now enforces, and the invariants they were built against.

**Phantom control-keyword suppression is conditional, never unconditional.** The reserved-word
guard is now language-scoped: today's nine words stay global, and a per-extension map adds
`foreach`/`using`/`lock`/`fixed` for `.cs` and `synchronized` for `.java`. A per-extension
keyword match is suppressed ONLY when an already-collected function record's `[start, end]`
span strictly encloses the match line. Otherwise the record is KEPT — an over-count, which is
the permitted direction, and the only measurement that code has. This is a human ruling, not a
design preference, and it exists because of a measured fact: on MIXED-brace C# (method brace on
its own line, control brace on the same line) the phantom `foreach` record is the SOLE
measurement of the method body, and unconditional gating collapsed a measured
`cyclomatic 6 / cognitive 15 / method_lines 7 / nesting 3` record and `checks: 6, vacuous:
false` down to `checks: 1` (class_lines only) and exit 0 — the council measured a richer example
going from cyclomatic 11 / cognitive 20 / exit 1 to a silent pass. A `.js` class with methods
genuinely named `lock`/`fixed`/`using` is still extracted with every metric intact; that is the
safety regression the extension-scoping exists to prevent, and it now has a test.

**`foreach` is a cyclomatic branch.** `_BRANCH_WORDS` gains `foreach`, globally and without
language threading, because a global `foreach` can only over-count. The match stays
case-sensitive and boundary-anchored: camelCase `forEach` in JS/Java/Kotlin must NOT match, and
the differential harness's exact-equality floors depend on that.

**Python indentation is measured in expanded columns, tabs included, everywhere.** A new
`_py_indent_width` expands tabs at 4 columns, and the extraction, nesting and cognitive sites
now agree. Before this, `_extract_functions_python` used bare `lstrip()` while
`_nesting_depth_python` and `_cognitive_approx` used `lstrip(' ')`, so every line of a
tab-indented file read as indent 0 and `nesting_depth` collapsed to 0 at any real depth — a
six-level body scored nesting 5 / cognitive 14 (FAIL) with spaces and 0 / 4 (PASS) with tabs.
After r1 the fix also survives literal-masking: the mask sentinel fill no longer erases leading
tabs, and at head the tab and space metric dicts are EQUAL where pre-r1 they read cognitive 10
versus 13, with tab/space mismatches across 4000 randomised mixed-indent bodies going 4000/4000
at base to 1043/4000 pre-r1 to 0/4000 at head. This change is observable on existing `.py`
results and can move them in BOTH directions; the downward direction is documented and,
per N1 below, only partly pinned.

**Every changed file the gate cannot measure leaves a record.** The skip chain's terminal
`elif _lang_for(path) is None:` is replaced by an unconditional else-arm carrying a
distinguishing reason, so a supported-extension file that yields zero extracted functions is
reported as unmeasured instead of disappearing from the gate JSON entirely.

**The enclosure bound is resolved in exactly one place.** r1 collapsed the duplicated
`fn['start'] <= line_no < fn['end']` test into a single helper resolved once and passed down,
retiring both the bare `next(...)` — which would have raised `StopIteration` and aborted the
gate for EVERY file, not just one, if the two copies ever drifted — and the stringly-keyed
`state` bag. Selection semantics were preserved exactly: the bound selects the OUTERMOST
enclosing record, verified safe because whichever record it picks encloses the phantom and is
always emitted alongside, and re-verified at head on a purpose-built discriminating case.

**Run-level constraints the code is held to** (from `dag.json.shared_constraints`, all still in
force): stdlib-only Python forever, `lizard`/`radon` detected read-only via `shutil.which` and
never imported; no type hints in plugin scripts, docstring on every function with `(PURE)` on
side-effect-free ones; NO NEW MODULE, because a doctrine test pins a literal script count in
the plugin README — all work lands inside `quality_gate.py` itself; NEVER UNDER-COUNT (the
heuristic may over-count but must never under-count, since an over-count is a false alarm a
human dismisses and an under-count is a real violation that ships); the function-record
contract `{name, start, end, header_idx}` with 1-based-inclusive `start`/`end` and 0-based
`header_idx`; stdlib `unittest`, never pytest, with fixtures at module level; coverage floors
of 86% on `quality_gate.py` and 90% TOTAL, with `coverage_omit.txt` untouchable; and the
standing `class_lines` ruling described above.

The composed never-under-count invariant was re-established at head across 62 real repo files,
15 adversarial C#/Java fixtures and 8000 randomised Python sources with ZERO metric drops and
zero lost function records; C-family and JS output was confirmed byte-identical across 12000
randomised cbrace sources and 34074 records; the four differential floors are identical at all
four commits.

## 3. Gaps & Deferred

**G1 — Function-level metrics do not fire on idiomatic (Allman-brace) C# at all.**
*What:* `_CBRACE_DEF_RE` (`quality_gate.py:149-151`, intake numbering) matches only a signature
whose `{` is on the SAME line. C# convention places the method brace on its own line, so a
pure-Allman C# class extracts zero functions — controller-measured through `analyze_builtin` —
and `cyclomatic_complexity`, `cognitive_complexity`, `method_lines`, `parameter_count` and
`nesting_depth` never apply; only whole-file `class_lines` does.
*Why deferred:* it dwarfs both defects the run was called to fix, but it is pre-existing and the
only remedy is letting the signature detector span the newline. "Tightening `_CBRACE_DEF_RE`"
is an explicit scope-ceiling entry: the regex is shared by all 15 brace extensions and its
failure mode is dropping real definitions — the same under-count risk this run exists to avoid.
*Reversibility:* high as a decision (nothing was built on it); the fix itself needs its own run,
its own risk sign-off and a differential pass over real C# source.

**G2 — Java try-with-resources extracts as a function named `try`.**
*What:* `try (var r = open()) {` is extracted as a function, because `try` is absent from the
nine global `_CONTROL_WORDS` (`quality_gate.py:944-945`, intake numbering). Same defect family
as D1, over-count direction.
*Why deferred:* surfaced in the same critique as G1, outside the answered scope of s1.
*Reversibility:* high — a one-word addition plus its paired tests, subject to the same
enclosure-conditional treatment s1 established.

**G3 — `summary.vacuous` is not wired into the per-slice pipeline.**
*What:* only `references/phase-5-integration.md:14` tells any reader to check `summary.vacuous`;
the per-slice path never reads it, so a slice touching only unsupported files passes with
`checks: 0` and exit 0. Controller-measured on a Ruby-only diff at intake.
*Why deferred:* it is a different change to a different file, and folding it in would have
doubled this run's blast radius. Named in the run's scope ceiling.
*Reversibility:* high; it is the real fix for the hole reading (B) tried to paper over.

**G4 — Reading (B), a generic indent fallback for every unsupported extension: rejected on the
merits, logged deferred rather than dropped.**
*What:* today anything outside `_EXT_LANG` is reported as "unsupported file type for analysis".
A language-agnostic indent guess would close that hole with a much weaker signal.
*Why deferred:* both plan-critic and guardian rejected it — choosing it means a passing gate can
no longer distinguish "analysed and clean" from "not analysable", in every future run.
*Reversibility:* high; nothing was built toward it.

**Deliberately not built (not a gap — a human ruling).** The entire indent-model EXTENSION: no
Ruby, no Kotlin, no `.swift`/`.scala`, no new `_EXT_LANG` entry, no generic fallback, no
step-size parameterisation (the hardcoded `// 4` stays, since no 2-space language is routed).
Separately measured at intake and recorded in the scope ceiling: routing `.swift` or `.scala`
would yield zero extracted functions AND no skip record — silent non-measurement, strictly
worse than today's honest "unsupported file type".

**Open findings shipped as recorded residuals (13).** None is at or above the tier-3 blocking
bar, and Phase 5 attempt 2 returned no P0 and no P1.

From Phase 5 attempt 2:
- **N1 (P2, tests) — the highest-value follow-up this run leaves behind.** The downward path's
  numbers are pinned but its FAIL-to-PASS verdict flip is not: the mixed-indent fixture r1 added
  to `TestTabIndentedPython` in `plugins/spec-loop/scripts/test_quality_gate.py` (exact line not
  recorded) deliberately chose a shape whose verdict does not change, while a flipping shape
  exists and was reproduced — cognitive 18 FAIL at base to 14 PASS at head, across a threshold
  of 15. This should be the first task of any successor run.
- **N2 (P3, docs).** `CHANGELOG.md:38` cites "`nesting_depth` 10 → 9, cognitive 21 → 18,
  retiring an existing violation", but 9 and 18 both still violate thresholds of 3 and 15, so
  the cited method retires nothing. The general claim is true and was constructed; the attached
  evidence does not demonstrate it. These are the exact numbers the controller flagged mid-run
  as coming from the implementer's own unnamed fixture and not independently reproduced — that
  caveat is now vindicated. It errs conservative, claiming more risk than exists.
- **N3 (P3, docs).** `plugins/spec-loop/scripts/quality_gate.py:588-589` describes the mask site
  and `_py_indent_width` as using "the same bare `lstrip()`", inviting a wrong refactor that
  substitutes the expanded column width for the raw character index `:601` needs; they differ 4x
  on a tab row and the substitution would re-open a duplication path.

From Phase 5 attempt 1, carried past remediation by design (r1's goal listed them OUT of scope):
- **F5** `_has_any_callable` duplicates `analyze_builtin`'s preamble.
- **F6** two missing `(PURE)` markers.
- **F7** `_py_indent_width` called on non-python headers — verified harmless.
- **F8** a CHANGELOG bullet naming `_encloses_line`, since renamed `_strictly_encloses_line`.

From r1's own review:
- The scan-mask SECTION HEADER comment in `plugins/spec-loop/scripts/quality_gate.py` (line not
  recorded) still gives "a masked docstring continuation line starts at column 0" as the reason
  extraction and `method_lines` keep reading raw text — which r1's own `lstrip(' ')` → `lstrip()`
  change makes FALSE. Verified by sweeping all 52 maskable tracked `.py` files and finding zero
  rows where masked and raw indent widths now differ. r1 swept two other now-false invariant
  claims for exactly this reason and missed this third one. Not remediated: it is an internal
  code comment rather than a user-facing release note, it is P2, and each prose correction this
  run made surfaced the next.
- `_cbrace_name_at` now sits at `nesting_depth` 3 against a threshold of 3 — it passes, since the
  check is strictly greater, but with zero headroom. Controller-verified at both revisions.
- A doubled "hardcoded" phrase in the CHANGELOG residual paragraph.
- `TestEnclosingRecord` is unit-only rather than paired, which `conventions.md` prefers; existing
  end-to-end fixtures cover the behaviour.

From s2's review (the two the controller permanently capped):
- A blank-line inconsistency around the `CS_FOREACH_CONTROL_SOURCE` module fixture.
- A ragged docstring paragraph wrap in `test_quality_gate.py`.

**Also deferred, r1 scope:** the new `_cbrace_name_at` resolves the enclosure helpers for EVERY
`_CBRACE_DEF_RE` match where the old code reached them only for a per-extension reserved word,
making extraction O(defs²) over the record list instead of O(defs) on the common path. Measured
harmless at repo scale across 3000 randomised C#/Java files, and it is what buys the
single-place enclosure bound — but it should not be read as free on a pathological file with
thousands of signatures.

## 4. Requirement Traceability

| Requirement (from `request.md`) | Status | Evidence |
|---|---|---|
| D1 — control keywords extracted as phantom functions | **delivered**, with a human-ruled conditionality the original request did not anticipate | s1 commits `29aa74b`, `2f2b7c7`, `c52d9f2`; escalation `s1:council-objection` (ANSWERED, human ruling); K&R `.cs`, mixed-brace `.cs`, and `.js`-methods-named-`lock`/`fixed`/`using` fixtures required by the slice goal; suite green at 1809 plugin tests on s1's head |
| D2 — `foreach` contributes nothing to cyclomatic complexity | **delivered** | s2 commits `acf8dcf`, `e933d5e`, `5ba3c6b`; suite green at 1813 plugin tests (up 4 on s1) |
| "Enhance with an indent-based model" — readings (A)/(B)/(C) | **deferred by human answer**, not attempted | escalation `run:ambiguity` (ANSWERED): "Neither — just fix the two defects. The indent-model EXTENSION is dropped: no Ruby, no Kotlin, no new `_EXT_LANG` entry, no generic fallback." Reading (B) logged DEFERRED (G4); `.swift`/`.scala` routing recorded in the scope ceiling as measurably worse than today |
| Tab-indentation under-count in the EXISTING Python indent model (discovered at intake, not in the request) | **delivered**, completed by remediation | s3 commits `aa28c6a`, `24f9529`, `fb7a3f1`, `6d9a213`, `a580350`; r1 commits `9e20e1c`, `75aa33b`; escalation `s3:material-assumption` (ANSWERED: "Fix it, with its own named regression test and a CHANGELOG line"); at head tab and space metric dicts are equal, 0/4000 randomised mismatches |
| Skip record for every unmeasured changed file (folded into s1 by the human's answer) | **delivered** | s1 commit `2f2b7c7`; the suite's first-ever `qg.measure()`-level test, required by the slice goal |
| Correct the `_looks_like_call_or_control` docstring, which advertised function-call detection its body does not implement | **delivered** | s1, clause (d) of the slice goal |
| Downward-direction test for the tab fix | **partial** | r1 commit `75aa33b` pins the numbers (cognitive 25/nesting 7 pre-s3 → 20/6 at head, verified exactly); the verdict FLIP remains unpinned — residual N1 |
| Accuracy of the shipped release notes | **partial** | two measurably false CHANGELOG claims corrected in r1 (F2, verified as substantively corrected rather than reworded — the false residual sentence was deleted outright); `CHANGELOG.md:38`'s unsupporting evidence (N2) and one now-false internal comment ship as recorded residuals |

`metrics.json` records `quality.requirement_coverage: null` — the run produced no machine
requirement-coverage mapping, so the table above is synthesized from `request.md`, the slice
goals in `dag.json` and the sidecars.

## 5. Decisions Summary

Thirty `decision` events and six `deferred` events are recorded; autonomy ratio 0.77; three
precedent reuses. The material ones:

- **Standing `class_lines` ruling, precedent-resolved without asking** (2026-09-10T14:06:07Z).
  Whole-file `class_lines` on `quality_gate.py` and `test_quality_gate.py` is accepted as
  pre-existing debt for every slice of this run, citing run 20260825-scope-ceiling's human
  answer and run 20260826-crash-classification's runbook. Scope of the ruling is those two files
  only; any NEW function-level violation a slice's own code introduces remains a genuine block.
  Reversibility: moderate.
- **Reconciling two intake answers that touch the same code** (14:12:03Z). The extension is
  dropped, the tab defect is fixed; the more specific answer governs the overlap.
- **Fully serial slices** (14:12:03Z). All three slices edit the same two files and the same
  `CHANGELOG.md [Unreleased]` section; a shared changelog section conflicts deterministically,
  and a conflict costs a remediation slice. The parallelism forgone was one wave of two small
  slices.
- **Controller-measured correction of the council objection** (14:28:38Z), which is what exposed
  G1: three C# brace shapes measured first-hand through `analyze_builtin` — pure Allman extracts
  `[]`, mixed extracts only the phantom, K&R extracts both the real method and a redundant
  phantom.
- **s1's three non-blocking residuals folded into s2's goal** (15:32:53Z) rather than fixed in
  s1 (which would deviate from the tier contract) or left to ship (which would contradict the
  standard this run enforced end to end).
- **Capping the prose-residual chase** (16:11:46Z), then **bending the cap for exactly one
  order** (16:57:07Z) and saying so rather than quietly widening it — the distinction held was
  correctness defects IN, style nits OUT.
- **MECHANISM GAP recorded for the runbook** (17:04:50Z): a controller fix order becomes an
  unclosable synthetic P1 (`order-0`, file `-`, line 0, `outside_diff: true`), so a slice given
  orders cannot reach DONE through the normal loop. See the Executive Readout for the full cost.
- **CONTROLLER ERROR and recovery** (17:10:40Z): the piped `git merge`, the masked failure, the
  deleted s3 branch, and the SHA-based recovery — each step verified before the next.
- **Two findings refuted by the batched verifier** on s3 (`r0-F2` on reproduced byte-identical
  metric dicts; `qg-0` on a `:0` file:line outside every hunk range with non-quoted evidence),
  and one acceptance fingerprint that **matched no measured violation** on r1
  (`nesting_depth _cognitive_approx`, announced so the drift is diagnosable).
- **N1-N3 ship as recorded residuals; no third remediation** (18:52:47Z).

**Human-answered escalations — all nine, none open.** Triggers: 1 ambiguity, 1
council-objection, 2 internal-error, 3 material-assumption, 1 quality-gate-block, 1
review-block. In order:
1. `run:ambiguity` — "Neither — just fix the two defects. The indent-model EXTENSION is dropped:
   no Ruby, no Kotlin, no new `_EXT_LANG` entry, no generic fallback."
2. `s1:material-assumption` — "Language-scope the guard AND fix the skip record", confirming a
   larger scope than the controller had originally described to the human.
3. `s3:material-assumption` — "Fix the tab-indentation under-count, with its own named
   regression test and a CHANGELOG line."
4. `s1:council-objection` (SAFETY) — "HUMAN RULING — adopt the critic-recommended default: make
   the suppression CONDITIONAL ON COVERAGE, not unconditional." This is the single most
   consequential answer in the run.
5. `s1:quality-gate-block` — mechanical acceptance under the standing ruling, not re-adjudicated.
6. `s3:internal-error` — retry the slice; the gate result resolved by acceptance rather than by
   a fix, both determinations controller-measured first-hand.
7. `s3:review-block` — controller determination that the synthetic order was ADDRESSED, verified
   clause by clause against the diff `fb7a3f1..a580350`; proceed to verify.
8. `phase5:material-assumption` — "REMEDIATE F1-F4 in one slice, then publish", with the human
   additionally choosing a publish path beyond the offered options: **push to main and cut a new
   release**, authorising the merge, the push and `scripts/release.py` (version bump,
   `[Unreleased]` rolled into a dated section, marketplace archive entry, git tag) — to be run
   only after remediation and a fresh Phase 5 pass, with the version level confirmed first.
9. `r1:internal-error` — retry at verify; the second occurrence of an identical schema failure,
   recorded separately as a run-level finding.

## 6. Integration Gate Result

**Attempt 1** (2026-09-10T17:29:08Z, at `892a2aab98f10174fc296a8c8cd56a92a71a304c`) — PASS on
both halves. Suite GREEN, run fresh (Phase 5 step 1 forbids evidence transfer for this
checkpoint): 126 scripts tests; 1818 plugin tests against a 1792 baseline; coverage PASS with
`quality_gate.py` 94.6% (910/962) vs floor 86 and TOTAL 97.2% (7229/7437) vs floor 90; 48/48
dashboard; 136/136 wave harness; plugin validate twice. Whole-run gate over `fa01826..HEAD`:
272 checks, vacuous FALSE, 3 failures, all three the accepted pre-existing set, zero new
violations attributable to the run. Review: APPROVE_WITH_FINDINGS, tier 3, over 14 commits — no
P0, no P1, eight findings (three P2, one P2-simplify, four P3). The reviewer did not reason
alone: it re-measured base vs head with explicitly loaded module copies and ran 62 real repo
files, 8 adversarial C#/Java fixtures and 4000 randomised mixed tab/space Python shapes through
both revisions, finding zero metric drops and zero lost function records.

Because three of those P2s concerned the honesty of what the run was about to ship, the
controller escalated rather than proceeding silently, and the human authorised **one**
remediation slice (r1) for F1-F4.

**Attempt 2** (2026-09-10T18:52:47Z, at `2c22dd33654b616b055c8ef122cb5bdb5be3f31a`) — PASS on
both halves; this is the run's final gate result, hence `integration_gate:
green-after-remediation`. Suite GREEN, run fresh: 126 scripts tests; 1825 plugin tests;
coverage PASS with 1951 tests, `quality_gate.py` 94.6% (912/964) vs floor 86 and TOTAL 97.2%
(7231/7439) vs floor 90; 48/48 dashboard; 136/136 wave harness; plugin validate twice.
Whole-run gate over `fa01826..HEAD`: **312 checks, vacuous FALSE read explicitly, 3 failures,
all three pre-existing and accepted** — and the provenance of the one function-level member of
that set was re-established against the RUN base rather than a mid-run base: `_cognitive_approx`
measures nesting 5, cognitive 12, cyclomatic 5, params 3, 26 lines at BOTH `fa01826` and HEAD,
byte-identical, so it predates the run. Review: APPROVE_WITH_FINDINGS, tier 3, over the
18-commit range, no P0 and no P1. All four remediation targets verdicted ADDRESSED against the
shipped tree with independent re-measurement rather than accepted on report; three new advisory
findings N1-N3 (one P2, two P3) recorded as residuals.

Remediation slices: 1 (`r1`). Per-wave integration checks: 3 recorded, 0 failures, all GREEN by
tree identity. Publish: **pending** — the human-authorised path is merge to `main` plus a
tagged release, not yet executed.

## 7. How to Verify & Operate

**The one thing to understand before running anything.** The gate that MEASURED this run is the
frozen plugin-cache copy at `~/.claude/plugins/cache/spec-loop/spec-loop/2.5.0`, sha256
`dc9f231adf375dc4d6aebee0542452df9caefeee79c198f3b19593c97b2a6e52`, verified byte-identical to
the repo copy at intake. Editing the repo copy does not change that instrument. A green gate
result is therefore NOT evidence that any defect in this run is fixed; the repo copy's own unit
tests, executed directly, are the only admissible evidence. The frozen instrument picks up
these fixes only when the plugin cache is refreshed to a release containing them.

**Full suite — seven segments, each its own invocation** (a monolithic run hits the 10-minute
ceiling and reads as a false red; source `.github/workflows/validate.yml`). This is the exact
command recorded in all four sidecars and used for the Phase 5 checkpoint:

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'
python3 scripts/measure_coverage.py
node --test --experimental-test-coverage plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs plugins/spec-loop/scripts/slice_wave_radius.test.mjs plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs plugins/spec-loop/scripts/slice_wave_reentry.test.mjs plugins/spec-loop/scripts/slice_wave_accepted.test.mjs plugins/spec-loop/scripts/slice_wave_replan.test.mjs
claude plugin validate .
```

**Fast inner loop for this run's own work:**

```
python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_quality_gate.py'
```

**Expected results at head `2c22dd33654b616b055c8ef122cb5bdb5be3f31a`:** marketplace OK; 126
scripts tests; 1825 plugin tests; coverage PASS with 1951 tests, `quality_gate.py` 94.6%
(912/964) and TOTAL 97.2% (7231/7439); 48/48 node dashboard; 136/136 node wave harness; plugin
validate passes.

**Thresholds and gates that already existed and still bind** — this run introduced no new CI
gate, script or threshold:
- Coverage floors: `quality_gate.py` at 86% (`scripts/measure_coverage.py:151`), TOTAL at 90%
  (`:160`). Do not add to `scripts/coverage_omit.txt`; `test_measure_coverage_manifest.py:23`
  pins the omitted `__main__` shim at exactly 2 lines. `evaluate()` compares `pct + 1e-9 <
  floor` with no rounding, so do not lean on the boundary.
- Differential-harness floors sit at EQUALITY (`test_quality_gate.py:1827-1836`): `globToRe`
  cognitive exactly 17, `stageFixLoop` 13, `runSliceError` 12, unmasked `stageFixLoop` cognitive
  exactly 15. Any change that lowers one by 1 fails CI. `_extract_functions_cbrace`'s cognitive
  complexity is pinned at exactly 15 — this is why s1's enclosure test had to go in a new
  helper rather than inline.
- `test_doctrine_run_docs.py:147` pins the literal script-count string in
  `plugins/spec-loop/README.md:167`, so adding a plugin script breaks CI until that inventory is
  updated. All work stays inside `quality_gate.py`.

**Operating the gate after this run.** Expect exit 1 with exactly three violations — whole-file
`class_lines` on `quality_gate.py` and `test_quality_gate.py`, and `nesting_depth` on
`_cognitive_approx` — all three pre-existing, all three accepted under this run's standing
ruling, and the last one byte-identical at `fa01826` and HEAD. That is the recorded steady
state, not a regression. The ruling covers whole-file `class_lines` on those two files only; a
new function-level violation introduced by a future slice's own code remains a genuine block.
Two operational habits this run paid for: never pipe a `git merge` whose failure must stop a
script (the shell takes the last command's exit status and `set -e` will not fire), and verify
the tracked-file cleanliness of the integration checkout BEFORE a merge rather than discovering
it by the merge's failure.

**Run artifacts.** Metrics: `docs/spec-loop/20260910-gate-language/metrics.json` (wall clock
14551s; 63 agent dispatches; ~3.22M subagent tokens across four waves; 9 escalations, 0 open;
30 decisions; 6 deferrals; 5 fix rounds; 17 findings). The per-slice sidecars
(`slice-<id>-status.json`) are authoritative over any prose here, including this runbook.
