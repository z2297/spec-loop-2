# findings-map.md — per-item verified ground truth

Written by the controller from one `Explore` pass, with the load-bearing claims re-verified by
the controller directly (marked **[controller-verified]**). Read your own item; do not re-derive
it. Companion: `controller-verified-evidence.md` (the behavioural harness and truncation chain).

Repo at `main` @ `299f0db`, plugin 2.2.1. Working tree was clean throughout intake.

---

## INTG-1 — the truncation test re-implements the renderer

**Cites are exact, no drift.** `test_slice_wave_contract_crash.py:181-186` `rendered_crash_context()`
ends `return " ".join(filled.split())[:CRASH_CONTEXT_RENDER_LIMIT - 1]`.

**It is a WORSE copy than a faithful port**, which sharpens the finding: `run_state._one_line()`
(`:188-190`) slices `[:limit-1] + "…"` **only when** `len(collapsed) > limit`, and appends an
ellipsis. The test's version slices unconditionally, with no length guard and no ellipsis. So it
does not merely duplicate the renderer — it disagrees with it on two of three behaviours.

**The test file already does `import run_state` (line 22).** Nothing needs adding to fix it.

**Every truncation limit in `run_state.py`** — three budgets, ten sites, one name:

| Limit | Sites | Governs |
|---|---|---|
| `SUMMARY_LIMIT = 200` (`:93`) — the only NAMED one | `:463`, `:529`, `:536`, `:579`, `:598-599`, `:704`, `:785` | escalation title, `_summarize`, `_scope_note`, `_first_text`, gate suffix, report title |
| `400` (bare literal ×5) | `:467`, `:468-469`, `:479`, `:506`, `:618` | context, question, answer, answer write-back, orphan answer |
| `300` (bare literal ×4) | `:473`, `:477`, `:747`, `:766` | option detail, if-unanswered, residual lines, split-child goal |

`CRASH_CONTEXT_RENDER_LIMIT = 400` in `slice_wave_contract_base.py:151` is an **independent
second 400**, not imported. Nothing keeps them equal except the one defective test.

**Dependent tests.** `test_run_state.py::test_long_summary_is_truncated` asserts only
`assertLess(len(line), 300)` — a loose bound that passes for any limit up to ~299.
`TestRenderEscalation` (`:324-361`) exercises shape, never truncation length. `dashboard_server.py`
has no re-implementation (its `truncated`/`_read_tail_capped` is an unrelated file-read cap).

**Fix shape.** Build a synthetic record from the pinned crash-context constants, render it
through **real `run_state.render_escalation()`**, and assert on the rendered line. **No
`run_state.py` change is required** — and none should be made: see the scope ceiling. The
duplicated `CRASH_CONTEXT_RENDER_LIMIT` then has no reason to exist, since the test no longer
needs to know the limit at all.

---

## INTG-2 — the guard covers FOUR homes; the report itself undercounts the total by one

**[controller-verified]** `TestTheTriggerEnumAgreesAcrossAllFiveHomes`
(`test_slice_wave_contract_crash.py:236-253`) has two methods: three Python tuples against each
other, then the JS enum line's values against `run_state.ESCALATION_TRIGGERS`. **Four homes, five
in the name.** `slice_wave_contract_base.py:93-94` says "five homes" then enumerates four.
`TRIGGER_ENUM_LINE` (`"trigger: { enum: ["`) is the *locator* for the JS enum line and carries no
values — it is not a fifth home.

**The definitive home list — SIX, not five:**

| # | Site | Form | Pinned? |
|---|---|---|---|
| 1 | `run_state.py:67-69` | Python tuple | yes |
| 2 | `run_metrics.py:119-126` | Python tuple | yes |
| 3 | `dashboard_server.py:149-151` | Python tuple | yes |
| 4 | `slice-wave.workflow.js:40` | JS `trigger: { enum: [...] }` | yes |
| 5 | `agents/slice-worker-fallback.md:152-153` | prose, "one of the seven triggers (…)" | **NO** |
| 6 | `references/run-state-v2.md:101` | prose/JSONC, full 7-value union | **NO** |

**[controller-verified]** Home 6 is real: `run-state-v2.md:101` reads
`"trigger": "ambiguity | material-assumption | review-block | council-objection |
quality-gate-block | budget-exhausted | internal-error"`. **The source report names only home 5
and never mentions home 6.** So the run's own deferral report commits a milder version of the
defect it is reporting.

**Ruled out as homes** (checked): both `README.md`s, all `commands/*.md`, all other `agents/*.md`,
all other `skills/*/SKILL.md`. `escalation-gate/SKILL.md` mentions `internal-error` but makes a
different, smaller claim ("exactly five JUDGMENT triggers") — not a full-enum home.
`slice_wave_contract_base.py:81-83` `ANSWERABLE_TRIGGERS` (5 items) is a legitimately different
subset — **do not conflate it with the 7-value enum.**

**Fix shape — two remedies, pick one and say why you rejected the other.** (a) Rename the class
and comment to the true four-code-home count and record homes 5 and 6 as deliberately unpinned.
(b) Extend the guard with regex-extracted assertions over homes 5 and 6 and rename to six homes.
The module already has a path-constant pattern (`:190`) to extend for (b).

---

## INTG-3..7 — lost-slice vs caught-exception record: the prose overclaims

**Ground truth [controller-verified behaviourally — see `controller-verified-evidence.md` §2].**
`esc()` (`:255-263`) substitutes, when `options` is `[]`, exactly ONE synthetic option labelled
`"Proceed with the recommended default"` whose `detail` is the whole context repeated, and
`recommended: true`. **This substitution is documented nowhere in the maintained docs.**

| | caught-exception (`runSliceError`, `:887-898`) | lost-slice (wave entry, `:919`) |
|---|---|---|
| title | branches on whether a stage dispatched | `'slice lost'`, fixed |
| context | exception text → stage attribution + caveat → classification prose → task count | fixed prose only; no exception text, no stage |
| question | 3-way retry/skip/stop | `'Re-run the wave to retry this slice?'` |
| options | **3 explicit**, each detail naming the CONTROLLER | `[]` → **1 substituted generic option** |

**The report is imprecise here**: it says the lost-slice record "offers only 'Re-run the wave to
retry this slice'". That string is the **question**, not an option label. The record's single
option is labelled "Proceed with the recommended default".

**Per-site verdicts:**

- **`CHANGELOG.md:32`** (cited "~31", off by one) — "its three options (retry the slice, skip it,
  stop the run) are controller actions"; the grammatical subject two clauses back is "The
  lost-slice record at :919", which has one option. **Confirmed overclaim.**
- **`escalation-gate/SKILL.md:75-79`** (cited ":78") — "the lost-slice record carries neither,
  having nothing to carry, **and says so**": the record's context never states its own gap, only
  SKILL.md's prose does. And "asks the controller to retry, skip, or stop" is true only of the
  caught-exception record. **Confirmed on both counts.**
- **`agents/slice-worker-fallback.md:97-100`** (cited ":98"/":99", 1-2 line drift) — the
  "(see step 4)" cross-reference is broken: the no-result→ambiguity rule lives at `:158-160` under
  `## Escalations` (heading at `:149`), while step 4 (`:103`) is "Review ∥ quality gate" and never
  mentions task no-result handling. **Confirmed.** The BLOCKED claim at `:97-100` is the SAME
  underlying defect as the step-3 divergence item below — one defect, two entries in the report.
- **`test_run_state.py:200`** — comment cites `run_state.py:204`; the fail-closed check
  `if record.get("trigger") not in ESCALATION_TRIGGERS:` is at **`:205`** (`:204` is the tail of
  the previous error message). **Confirmed.** Fix by citing behaviour, not a line number.

**Negative result worth recording — do NOT "fix" this.** `references/run-state-v2.md:112-119` is
**clean**: it correctly hedges ("…that the record does not pretend to rule out… It is not a
catch-all…"). **[controller-verified.]** `references/phase-5-integration.md` has zero mentions of
`internal-error`. Both READMEs, all `commands/*.md`, all other agent and skill docs: zero.

**Out of scope.** `docs/spec-loop/*/` run artifacts contain full-enum prose but are immutable
historical records, not maintained docs.

---

## quality-gate string-literal miscount — the run's one real code change

**All numbers below are [controller-verified] by running `quality_gate.analyze_builtin` directly.**

Threshold: cyclomatic 10, cognitive 15. Measured over `slice-wave.workflow.js` (71 functions),
the three that matter, raw versus with **single/double-quoted string contents blanked only**
(backticks deliberately left alone, so `${…}` code is untouched):

| function | raw cyc | raw cog | blanked cyc | blanked cog | verdict |
|---|---|---|---|---|---|
| `globToRe` (`:166-177`) | 9 | **25** | 6 | **17** | over threshold either way |
| `stageFixLoop` (`:769-783`) | 8 | **15** | 7 | 13 | **ZERO headroom today** |
| `runSliceError` (`:887-898`) | 8 | 14 | 7 | 12 | 1 point of headroom today |

**The headline live instance is `stageFixLoop`, not `runSliceError`.** It measures cognitive
**exactly 15 against a threshold of 15** and passes only because `_finding()` uses
`value <= threshold` (`:861-866`). Its miscount is the literal `?` ending the human question
`'Accept the residual findings, provide guidance, or drop the slice?'` — counted as a ternary.
The report never mentions this function.

**The most vivid instance is `globToRe`.** Its three counted "ternaries" are all punctuation
inside string literals: the `?` in the escape set `'.+^$()|[]{}\\?'` and the two in the regex
source `'^(?:.*/)?'`. Not one is a ternary. Counted branch words are `['for','if','if','if','if']`
— all real. **Honest limit: blanking strings takes it 25 → 17, so it stays over threshold. The
miscount inflates it by 8 points; it does not create the violation.** Do not claim the fix
rescues `globToRe`.

**Structural, not isolated.** `grep -n "?'[,)]"` finds **11** places where an `esc(...)` question
argument ends in a literal `?` before the closing quote. Every one is a ternary miscount.

**A naive "blank every string literal" fix is WRONG, demonstrated.** Blanking whole backtick
template literals including `${…}` deletes real operators — e.g. the genuine `&&`/`||` in
`${String((e && e.message) || e)}` — reporting `runSliceError` at cyc 5 / cog 8 instead of the
correct 7 / 12. **Any fix must preserve `${…}` expression content.**

**Python is materially harder and is NOT optional.** `_branch_count` (`:418-424`) is not
language-branched at all; `_cognitive_approx` (`:533-558`) branches but both arms call the same
two regexes. Both are called only from `analyze_builtin` (`:565-609`) — exactly two raw-scan
sites, no others. The explorer's regex-based Python stripper was **unreliable and its numbers are
NOT reported as fact**: it recovered 0 functions from `quality_gate.py`/`run_state.py`
post-strip, and produced an impossible result on `dashboard_server.py` (`_scan_one_run` cyclomatic
*rising* 5→35, a mismatched-quote artifact corrupting the rest of the file). **A trustworthy
Python implementation needs stdlib `tokenize`, not regex.** Whether any Python file's gate outcome
would flip is **genuinely unknown** and must be measured by the slice, not assumed.

**Comments.** The report says nothing about comments, but the same argument applies verbatim —
this repo's Python carries unusually long explanatory comments. Whether to strip comments too is a
design decision the slice must make explicitly and justify either way.

**Existing tests.** `TestBranchCount` (`:260`), `TestNesting` (`:287`), `TestCognitiveApprox`
(`:319`), `TestAnalyzeBuiltinPython` (`:336`), `TestAnalyzeBuiltinCbrace` (`:379`). **No fixture
anywhere puts a branch keyword or operator inside a string literal**, so no existing expected
value blocks the change — and nothing currently pins the new behaviour either.

**Blast radius.** `quality_gate.py` (`_branch_count`, `_cognitive_approx`) and
`test_quality_gate.py`. No other caller in the repo.

---

## slice-worker-fallback.md Pipeline step 3 — the trigger divergence

**Ground truth (`slice-wave.workflow.js:603-637`).** `taskNeedsRetry(r)` is true for `!r`,
`NEEDS_CONTEXT`, or `BLOCKED`. `attemptTask` retries once on any of the three. `runTask` re-tests
the retry's result and, if still true, escalates with trigger **`'ambiguity'`, unconditionally**
(`:636`). The workflow does **not** distinguish an exhausted genuine `BLOCKED` from an exhausted
`NEEDS_CONTEXT` — both collapse to the same call.

**`agents/slice-worker-fallback.md:96-100`** says: "Pick the trigger the way the workflow does: a
dispatch that came back with **no result** is `ambiguity` (see step 4), never `internal-error`; a
`BLOCKED` that states a real blocker is `material-assumption` or `review-block` as fits."

**Agree:** both retry once, both escalate on exhaustion, both map a bare no-result to `ambiguity`.
**Diverge:** for an exhausted retry whose last status is a genuine `BLOCKED`, the workflow still
says `ambiguity`; the doc offers a three-way choice the workflow never makes. The doc's own
preceding clause — "Pick the trigger the way the workflow does" — is contradicted by the sentence
that follows it.

**Fix shape.** Rewrite `:96-100` so an exhausted retry is `ambiguity` unconditionally regardless of
originating status; drop the material-assumption/review-block branch; repair the "(see step 4)"
cross-reference to `## Escalations`. **This is the SAME edit as INTG-3's fallback.md fix — one
coordinated edit, never two parallel agents.**

---

## substring-safety test never exercises the matcher

**`_legacy_match_triggers` (`run_metrics.py:1690-1696`)**: lower-cases the text, returns every
canonical trigger that is a raw substring (no word boundaries), collecting **all** matches;
`["other"]` for non-empty unmatched, `[]` for empty. **One caller:** `:1679` inside
`_legacy_body_fields` (`:1671-1687`) on a `- Trigger:` line. Chain:
`legacy_parse_escalations` (`:1619-1640`) → `_legacy_split_blocks`/`_legacy_parse_header`
(`:1642-1669`) → `_legacy_body_fields` → `_legacy_match_triggers`.

**A real v1 prose fixture already exists**: `LEGACY_ESCALATIONS` (`test_run_metrics.py:259-273`),
used by `test_escalation_blocks_statuses_and_triggers` (`:322-329`) and `LegacyComputeTests`
(`:1340-1349`). It contains e.g. `- Trigger: ambiguity + material-assumption (Iron Council
ENDORSE_WITH_CONCERNS; …)` — free-form narrative genuinely multi-matching. It is correctly
exercised for the other six triggers and never with `internal-error`.

**The defect (`test_run_metrics.py:466-472`)**: two bare `assertNotIn` calls between Python string
literals; never imports or calls the matcher or the parse chain. Green under any refactor of it.

**Fix shape.** Add a `- Trigger:` line containing `internal-error` in the `LEGACY_ESCALATIONS`
shape, drive it through the real `legacy_parse_escalations` chain, assert the returned list
includes `internal-error` and excludes spurious others. Keep the naming constraint too — it is
cheap and it is what makes the matcher safe. **Blast radius: `test_run_metrics.py` only.**

---

## test_dashboard_server.py mixed indentation

**Cites drifted** — consistent with the whole sweep, since commit `7fdd7e2` (the very commit this
deferral list came from) touched this file.

- cited "~1246-1249 col 36" → actual **`:1234-1236`**, 36 leading spaces, inside
  `test_an_id_known_only_to_the_events_log_is_carried_honestly` (`:1231`), immediately before the
  clean 4-space `test_internal_error_parses_out_of_an_escalation_id` (`:1247`).
- cited "~1267 col 55" → actual **`:1274-1276`**, 57 leading spaces, inside
  `test_a_record_trigger_outside_the_contract_falls_back_to_the_id` (`:1270`).

The underlying claim holds; only the numbers moved.

**Does the gate flag them? Measured.** The gate is diff-scoped. Re-running it over the originating
commit (`--base d86ceae --head 7fdd7e2`) surfaces only that commit's newly-touched functions — all
passing, several at exactly `nesting_depth` 3 with zero headroom — and **the two old-style sibling
functions do not appear at all.** Empirically confirmed: they escape only by being outside the diff.

**The decisive context the report omits.** Paren-alignment at these columns is the file's
**long-standing dominant style**, recurring at `:642-646`, `:1178`, `:1180`, `:1211`, `:1213`,
`:1318`, `:1472`, `:1483`, `:1513` and more — all predating this commit. So the true state is not
"a reindent left two stragglers" but "a mostly-old-style file has a few new clean-style
functions". Normalising only the two flagged spots would make the file *less* internally
consistent, not more.

**Mechanically safe?** Yes in isolation — pure whitespace on balanced continuations; Python is
indifferent, and `python3 -m unittest test_dashboard_server` self-verifies.

---

## The one hard scheduling constraint

| File | Items | Conflict |
|---|---|---|
| `agents/slice-worker-fallback.md` | INTG-3 (`:97-100`), step-3 divergence (`:96-100`), INTG-2 (`:152-153`) | **INTG-3 and the step-3 divergence are the identical span — ONE coordinated edit.** INTG-2's span is a different paragraph but the same file: not a concurrent worktree edit. |
| `slice_wave_contract_base.py` | INTG-1 (`:151`), INTG-2 (`:93-94`) | disjoint regions, same file |
| `test_slice_wave_contract_crash.py` | INTG-1 (`:181-199`), INTG-2 (`:236-253`) | disjoint classes, same file |
| everything else | one item each | fully independent |
