# Changelog

All notable changes to the spec-loop plugin are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/). History before 2.0.0 lives in the
[v1 repository](https://github.com/z2297/spec-loop).

## [Unreleased]
### Fixed
- **A tab-indented python file was measured as if it had no nesting at all, and now
  measures the same as the identical space-indented file.** `_nesting_depth_python` and the
  python arm of `_cognitive_approx` in `plugins/spec-loop/scripts/quality_gate.py` stripped
  leading SPACES only (`lstrip(" ")`) before dividing by the model's 4-column step, so every
  line of a tab-indented file read as indent 0 and the whole file collapsed to
  `nesting_depth` 0 at any real depth. Measured on one six-level-deep body: space-indented it
  reports cognitive 20 / nesting_depth 6 and FAILS the nesting threshold of 3; the
  byte-identical tab-indented body reported cognitive 5 / nesting_depth 0 and PASSED, on the
  same branch count (cyclomatic 6 either way). The new PURE `_py_indent_width` is now the
  single place leading whitespace becomes a column count — it expands tabs at 4 columns,
  matching the `// 4` the nesting and cognitive models divide by, so one tab is exactly one
  level — and the three space-only sites (`_nesting_depth_python`, the `_cognitive_approx`
  python arm, and `_function_metrics`' `base_indent`) call it. `test_quality_gate.py` gains
  `TestTabIndentedPython`, pinning tab/space parity and the helper itself, including a
  tab-indented method whose own `def` header is indented (not just a top-level function at
  column 0), which is the shape that exercises `_function_metrics`'s `base_indent` call
  specifically. **This changes
  existing `.py` results upward**: a tab-indented python function that passes the gate today
  can fail after this change. That is the safe direction under the never-under-count rule and
  is the intended effect, but it is an observable behaviour change, not merely internal.
  It can also move a result down where a tab-indented `def` header is combined with
  space-indented body lines: `_function_metrics`'s `base_indent` now expands the header's tab
  while the body lines' indent (already space-only) is unchanged, so the gap between them can
  shrink and retire an existing nesting/cognitive violation on that mixed-indent shape — the
  new values are closer to truth in both directions, a reduction in over-count rather than a
  new under-count.
  Known, documented residuals: `_extract_functions_python` still measures indent with a bare
  `lstrip()` and is deliberately left alone — it compares a header against its own body with
  one consistent measure, so it already spans a tab-indented file correctly, and expanding
  there was measured to SHRINK a mixed tab-and-space function's span (a four-line method
  dropping to one), which would be a new under-count. The 4-column tab step is HARDCODED,
  deliberately: the indent step stays at 4 and is not parameterised, since no 2-space
  language is routed to this model. A file mixing tabs and spaces inconsistently is measured
  by column width alone, which can disagree with python's own tokenizer (tabs at 8); no such
  file exists in this repo and none is handled specially. The mask-span helper's own
  `lstrip(" ")` is left as-is on purpose: it picks a raw column index, not a width.
- **The quality gate's C-family control-keyword guard is now scoped to the language that
  reserves the word, and suppresses a phantom record only when the real enclosing method was
  itself measured.** `plugins/spec-loop/scripts/quality_gate.py` keys the new
  `_CONTROL_WORDS_BY_EXT` map by file extension — `foreach`/`using`/`lock`/`fixed` for `.cs`,
  `synchronized` for `.java` — while the nine words in `_CONTROL_WORDS` stay global; the
  extension is threaded from `analyze_builtin` through `_extract_functions_for` and
  `_extract_functions_cbrace` into `_looks_like_call_or_control`, whose unused `line`
  parameter it replaces and whose docstring no longer claims a function-call detection the
  body never implemented. Suppression is conditional on coverage by design: the new PURE
  `_encloses_line` helper drops a `foreach` record only when an already-extracted function's
  1-based inclusive span contains it. **The retained phantom is DELIBERATE, not a residual
  defect** — on a C# method whose opening brace sits on its own line, `_CBRACE_DEF_RE` never
  sees the method, so the `foreach` record is the only measurement of that body (measured:
  cyclomatic 5, cognitive 8); suppressing it unconditionally would take the file to
  `class_lines` alone and turn a real reading into a silent pass. An over-count is the one
  direction this heuristic is permitted to move. That safety argument is PER-METRIC, not
  blanket: an enclosed phantom's cyclomatic, cognitive, method_lines and nesting_depth are
  all dominated by the enclosing record whose body contains it, but its `parameter_count` is
  read from its own header and is NOT — see the `_phantom_has_more_params` entry below.
  Known, documented residuals: a pure-Allman C# file (every brace on its own line, the
  Visual Studio default) still extracts nothing at all, because `_CBRACE_DEF_RE` requires
  the `{` on the signature line — deferred to its own run. (A related residual — `foreach`
  absent from `_BRANCH_WORDS` — is fixed below in this same Unreleased section.)
- **A changed file the quality gate could not measure can no longer vanish from the report.**
  `measure()` in `plugins/spec-loop/scripts/quality_gate.py` ended its skip chain in
  `elif _lang_for(path) is None`, so a file with a supported extension that yielded zero
  callables produced neither a function measurement nor a `skipped` entry — measured on a
  pure-Allman `.cs` file and a `def`-less `.py` file, `skipped` named neither. The chain now
  ends in an unconditional `else` carrying the new PURE `_skip_reason(path)`, which keeps the
  existing `"unsupported file type for analysis"` text and adds `"no callable found by the
  builtin heuristic"` for the supported case, so the two are distinguishable in the report.
  `plugins/spec-loop/scripts/test_quality_gate.py` gains `TestMeasureSkipRecord`, the suite's
  first `qg.measure()`-level test. Known, documented residuals: a `skipped` entry still feeds
  no threshold and no exit code, and `summary.vacuous` is still read by nothing in the
  per-slice pipeline — only `references/phase-5-integration.md:14` tells any reader to check
  it. Both are deferred, not fixed here.
- **The control-keyword suppression could itself under-count, on two separate paths, and both
  are closed.** `plugins/spec-loop/scripts/quality_gate.py`'s `_encloses_line` (now
  `_strictly_encloses_line`) tested only `fn["start"] <= line_no <= fn["end"]`; because `.cs`
  and `.java` are excluded from `_JS_MASK_EXTS`, `_match_brace_end` counts a `}` inside a
  string or char literal on the enclosing method's own header line — e.g.
  `raw.Split('}')` — as a real close, ending the enclosing record's span exactly AT the
  phantom's header line. That equality used to count as enclosure, suppressing the phantom
  even though the enclosing record measures almost none of its body; the bound is now
  exclusive (`line_no < fn["end"]`), and `TestExtensionScopedControlWords` gains
  `test_a_literal_brace_on_the_control_header_line_keeps_its_phantom` pinning the retained
  `foreach` record. Separately, suppression assumed an enclosed phantom's own metrics were
  always dominated by the enclosing record, which is false for `parameter_count`: a C#
  `using (a, b, c, d, e)` can declare more comma-separated items than the enclosing method's
  own signature. The new PURE `_phantom_has_more_params` compares the phantom's own header
  against the enclosing record's header and keeps the phantom whenever its count is higher;
  `test_an_enclosed_multi_declaration_using_keeps_its_own_finding` pins a 5-parameter `using`
  surviving inside a 1-parameter `Import` method (5 > `DEFAULT_THRESHOLDS["parameter_count"]`
  == 4). Both are the same failure family the run's NEVER-UNDER-COUNT constraint names.
  Known, documented residuals: the parameter_count guarantee is an ARGUMENT the code does
  not assert. `_phantom_has_more_params` keeps a phantom only when its own count is strictly
  higher, so a phantom whose count is equal or lower is still dropped; that is safe only
  because the enclosing record's own count is then at least as high AND is always emitted
  alongside — the enclosing span strictly contains the phantom's, so any changed range that
  reaches the phantom reaches the enclosing record too. Measured both halves on `.cs`:
  `using (Stream p = A(), q = B(), r = C(), s = D(), t = E())` inside `Go(int a)` reports
  `Go` 1 AND `using` 5 (the phantom survives, 5 > the threshold of 4); the same `using`
  inside `Go(int a,int b,int c,int d,int e,int f)` reports `Go` 6 alone, for a full range and
  for a narrow range covering only the `using` block. `test_quality_gate.py`'s
  `test_a_dominated_using_is_dropped_only_behind_a_higher_count` pins that second half. A
  related measured non-result, recorded so no reader re-derives it: the nested-call form
  `foreach (var x in Zip(a, b, c))` does NOT reach this path at all — `_count_params` splits
  commas only at paren depth 0, so it measures 1. The multi-declarator `using` is the only
  shape that reaches it.
- **A skip record could itself misreport why a file went unmeasured.** `measure()`'s new
  unconditional `else` arm (see above) reached `_skip_reason(path)` whenever a file yielded
  zero IN-RANGE findings — which also fires for an import-only edit, a docstring tweak, or any
  changed hunk that simply falls outside every callable in an otherwise fully-measurable file.
  Such a file got the same `"no callable found by the builtin heuristic"` text as a file with
  no callables at all, a false claim on the common path. `_skip_reason` now takes the file's
  `source` too and calls the new PURE `_has_any_callable` (a changed-range-free extraction) to
  tell the two apart, returning `"no changed callable found by the builtin heuristic"` when
  callables exist outside the diff. `measure()` is also refactored into `_read_changed_source`,
  `_backend_records_for`, `_measurements_for_file`, `_heuristic_measurement`,
  `_class_measurement`, `_python_only`, `_detect_backend_records` and `_used_backend_names`,
  which brings its own cyclomatic/cognitive/method_lines/nesting_depth back under threshold
  (measured before: 14/36/66/5 against 10/15/50/3; after: 5/11/40/3) without changing its
  return contract; `_extract_functions_cbrace` is similarly split out into `_cbrace_name_at`,
  bringing its nesting_depth from 5 to 3. `TestMeasureSkipRecord` gains
  `test_an_import_only_edit_does_not_falsely_claim_no_callable_exists`. Known, documented
  residuals: `_extract_functions_python`, `_match_brace_end` and `_match_changed` carry
  pre-existing cognitive_complexity/nesting_depth violations this slice did not introduce and
  does not fix here, and `class_lines` on both `quality_gate.py` and `test_quality_gate.py`
  remains accepted debt per standing ruling.
- **A C# `foreach` now contributes a cyclomatic branch.** `_BRANCH_WORDS` in
  `plugins/spec-loop/scripts/quality_gate.py:142` gains `foreach`, so both `_branch_count`
  and `_cognitive_approx` see C#'s loop keyword. Measured on a K&R `.cs` method containing
  one `foreach`, one `if` with `&&` and one `switch`/`case`: cyclomatic_complexity 4 → 5 and
  cognitive_complexity 8 → 10, the foreach having contributed nothing before. The word set
  stays GLOBAL rather than per-language, because a `foreach` in a language that does not
  reserve it can only over-count, the one direction this heuristic is permitted to move.
  The match stays case-sensitive and word-boundary-anchored, so JS/Java/Kotlin
  `arr.forEach(...)` — a method call, not a loop — is not counted, and `for` inside
  `foreach` fails its own trailing boundary so the keyword adds exactly one branch, not two.
  `plugins/spec-loop/scripts/test_quality_gate.py` gains
  `test_csharp_foreach_counts_exactly_one_branch`,
  `test_camel_case_for_each_is_not_a_branch_word` and the end-to-end
  `test_a_csharp_foreach_adds_a_branch_to_its_enclosing_method` over the new
  `CS_FOREACH_CONTROL_SOURCE` fixture, whose enclosing method is genuinely extracted (the
  phantom is suppressed there by the enclosure guard above, which is why this change is
  sequenced after it); two pre-existing pinned metric dicts move with it, `Import` 2/3 → 3/5
  and the deliberately retained `foreach` phantom 5/8 → 6/9. Known, documented residuals:
  a `foreach` written in a language that does not reserve the word is counted as a branch by
  design (an over-count); a pure-Allman C# file still extracts no method at all, so its
  `foreach` is attributed to nothing — deferred to its own run.

## [2.5.0] - 2026-09-09
### Added
- **`/spec-loop:jira-intake`: read a Jira card, refine it, confirm, and write decisions back.**
  `scripts/jira_client.py` is a stdlib-only, read-first Jira Cloud REST v3 client that resolves
  one issue key to a normalized record with paginated comments, authenticating from
  `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN` and failing closed when any is unset;
  `scripts/jira_intake.py` plus `commands/jira-intake.md` produce a refined-understanding
  artifact under the gitignored `.spec-loop-jira/` root, ask every gap in one batched question
  round, preview the comments they would post, and print the `/spec-loop:spec-loop --from-plan
  <path>` handoff — the command carries neither `Workflow` nor `Edit`, so it structurally cannot
  start the loop. The comment write-back lane posts confirmed-understanding, decision and
  open-question comments only behind a preview-then-confirm gate and `--post`, embeds a visible
  marker per comment, dedupes against the card's own paginated comment list, and refuses a batch
  with duplicate markers before any request is sent. Both modules are registered in
  `scripts/measure_coverage.py` at 94% and 91% floors. Known, documented residuals: the dedupe is
  per invocation, not cross-process; a comment that merely quotes a marker reads as already
  posted (fails toward not writing); the partial-post recovery depends on the rendered
  `comments.json` surviving. Run 20260908-jira-intake.
- **Re-entry: a re-dispatched slice resumes at a stage against its real head instead of
  replaying the pipeline from its goal.** `slices[].entry {stage: plan|review|fix|verify, head,
  fix_rounds, review_tier, residual, orders}` on the wave args — `verify` runs stage Z alone,
  `fix` runs a gate-only measurement then the fix loop with the controller's orders as
  `order-<N>` findings, `review` re-reviews `base..head` under the next round tag, `plan` tells
  the planner what the branch already delivers and accepts zero tasks. An unusable entry is a
  zero-dispatch `internal-error` titled `unusable slice.entry`. Run 20260908-jira-intake lost a
  whole dispatch when a resumed wave re-planned a delivered slice and dropped three fix orders.
- **Accepted quality-gate violations.** `args.accepted_violations["<slice>"]` lists
  `{metric, file, function|null}` fingerprints a human accepted; cumulative like `answers`, no
  wildcards, never a threshold change. A gate whose every violation is accepted stops blocking
  while the sidecar still says FAIL and lists them under `quality.accepted`; the `quality-gate`
  event carries the accepted count; a fingerprint matching nothing is announced as drift.
  `quality-gate-block` records carry `violations[]` so an acceptance is made by escalation id.
- **`scripts/redispatch.py`.** `args` builds a wave re-dispatch from the run's own artifacts —
  non-terminal slices with `slice.entry` from their sidecars, the cumulative `answers` map, the
  `accepted_violations` map, a `resume.advised` flag — and `accept-violations` records an
  acceptance by escalation id as one `decision` event (`kind: accepted-violations`) plus the
  `escalation-answered` event, so acceptance and answer cannot diverge.
- **An escalation round bound.** The third round of one trigger on one slice (`MAX_ESC_ROUNDS =
  2`) is reframed `non-terminating:` with the three actions a controller can take; a record
  whose id already holds an answer is returned ANSWERED. `run_state.py open-escalations` marks a
  record that repeats an answered one (same violation set, else same context and question) as
  `repeat_of`.
- **Test evidence per addressed finding.** `FIX_RESULT.tests_added: [{finding_id, test}]`; the
  re-reviewer sees the fixer's `addressed`, `tests_added` and `tests`, and a `correctness`/
  `errors` finding closed ADDRESSED with no named test stays open with a `decision` saying so.

### Changed
- **The sidecar's `quality` block is always the LAST measurement taken**, on every exit path,
  stamped `{head_sha, tree_sha, measured_at, violations}`; the `quality-gate` event carries the
  same and a `stage`. Verification is recorded before it is judged (`tests.passed`), every
  fix-loop escalation re-measures the gate at the current head first (`gate:remeasure`, one
  haiku dispatch) and carries the open findings on `review.open`. Run 20260908 shipped six
  pre-fix quality blocks the controller re-measured by hand.
- **Answers reach the agent that acts on them**: `review-block` is read by the fixer and the
  debug-fixer, a task-blocked `ambiguity` by the task retry (first attempts stay byte-identical
  so plain re-dispatch cache hits survive), plan-raised triggers by the planner as before.
  Escalation options name the controller action and the entry it builds.
- `commands/spec-loop.md` step 7 and Resume drain answers and build entries through
  `redispatch.py args`; `skills/escalation-gate/SKILL.md` gains a same-run precedent bullet and
  two violations (accepting in prose alone; hand-writing a DONE sidecar).

### Fixed
- **The fix prompt named `packages/<slice>-round2.md`, a file nothing writes**: the tag was
  derived from `fix_rounds` after the round counter had advanced. Package tags now live in state
  (`reviewPackage`/`fixPackage`), set by the stage that writes each file.
- **`run_state.py persist-slice` re-opened an answered escalation** when a sidecar still
  embedded the record with `status: OPEN` (run 20260908, `j1:quality-gate-block:2`, rendered OPEN
  on a DONE slice). It now reads the log first, never re-emits `escalation-opened` for an
  answered id, and settles embedded records to ANSWERED.

## [2.4.0] - 2026-09-08
### Added
- **The controller's Phase-2 loop now closes itself in prose: a wave boundary with slices
  still runnable is a dispatch point, not a place to stop and report.** `commands/spec-loop.md`
  gains a Phase 2 step 9 **Close** that re-runs `dag.py next-wave` in the same turn and routes
  the three outcomes — runnable back to step 1, `done` to Phase 5, `deadlock` to an escalation
  — judging runnability on a non-empty `slice_ids` rather than on a missing `done` key, which a
  deadlock report does not carry. The Invariants line states the same rule, an
  `escalation-opened` event is now mandatory before any controller-originated
  `AskUserQuestion`, Phase 1 and Resume write `.controller-session` beside `.active`, and the
  `.paused` lifecycle (human asks, controller writes, controller clears, `--resume` does not)
  is written down with its stale-marker remediation. `skills/escalation-gate/SKILL.md` adds a
  fourth "Not triggers" entry for the RUNNABLE boundary only — a reported deadlock stays a
  genuine escalation — and `scripts/test_doctrine_loop_boundary.py` pins every one of those
  sentences, counting the list's bullets on disk rather than trusting the number in the prose.
  This is prose and a pin; the enforcing gate is separate.
- **The loop-boundary gate itself: a `Stop` hook that blocks the controller's turn from ending
  while its run still has runnable slices and no open escalation — the run's one proven
  LEVER.** `scripts/spec_loop_guard.py` gains `check_stop()` plus event dispatch in
  `evaluate()`/`main()`, and `hooks/hooks.json` registers the `Stop` event; a `Stop` block is a
  different wire shape from a `PreToolUse` denial (top-level `decision`/`reason`, not a
  `permissionDecision`). The gate is narrowed to the session recorded in
  `.controller-session`, skipped when `stop_hook_active` is true — probed on Claude Code
  2.1.260 and CONFIRMED within a single turn to be `false` on the turn-ending fire and `true`
  on the block-caused continuation's fire, which makes the gate one push per stall rather than
  a fence — relaxed by a `.paused` marker that relaxes THIS gate alone, and fails open PER RUN
  (not globally) when a `.controller-session` marker cannot be decoded. The probe evidence and
  its limits are recorded in `references/platform-probes.md`, together with the three questions
  that remain UNTESTED there: whether `AskUserQuestion` emits `PreToolUse` at all, whether
  Ctrl+C routes through `Stop`, and whether `Stop` fires for `Task` subagents. The per-turn
  reset is no longer one of them: `stop_hook_active` returning to `false` at the start of every
  NEW user turn is CONFIRMED — established by the third `Stop` fire of a two-turn probe session,
  where the flag read `false` again at the end of turn 2 — so the gate re-arms each turn instead
  of being one-shot per session. A PreToolUse gate on `AskUserQuestion` was
  considered and DROPPED by human decision; no part of it was built and nothing in this release
  guards that path.

### Changed
- **Run-state markers are now untracked, ignored and pinned, and the contract that describes
  them says what it actually enforces and where.** Eight previously committed markers across
  four runs are removed from the index (index-only, leaving the files on disk for any run still
  reading them), `.gitignore` gains one bare unanchored entry per marker name for all five
  (`.active`, `.publish-choice`, `.done`, `.paused`, `.controller-session`), and
  `scripts/test_doctrine_marker_hygiene.py` fails if one re-enters the index.
  `references/run-state-v2.md` documents the two markers v2 adds, scopes that enforcement claim
  to this repository — an installing repo has neither the ignore entries nor the pin — declines
  to claim the `.controller-session` narrowing separates a `Task` subagent from its parent (it
  inherits the same session id), and records as an ACCEPTED residual risk that `.paused`
  disables the loop-boundary gate with zero observable trace, since a silent hook cannot
  announce that it is paused. `README.md` stops describing `spec_loop_guard.py` as a
  PreToolUse-only hook and adds the loop-boundary block to its exhaustive blocked-actions list.
- **The escalation-ordering rule now states both halves**, in `commands/spec-loop.md`: the
  mandatory `escalation-opened` event before any controller-originated `AskUserQuestion`, and
  the write-back once the human answers. The wave-raised exclusion is scoped to the append half
  only, so a wave-raised escalation still gets its answer recorded.

### Known limitation
- **Nothing this release added to `hooks/hooks.json` protected the run that produced it.** The
  installed plugin was 2.2.0 while this repository is 2.3.0, so the `Stop` registration shipped
  here was never loaded during the run, and no test in the suite would have failed if the gate
  had been inert — the suite pins the script's behaviour, not the running session's hooks. The
  gate's effect on a live controller session is therefore unobserved as of this entry.

## [2.3.0] - 2026-08-29
### Added
- **The wave now halts a slice at PLAN time when its plan declares a rewrite of existing code
  larger than the run's configured ceiling — the run's one new LEVER.**
  `slice-wave.workflow.js` gains an optional `refactor_radius` block on `PLAN_RESULT` that the
  slice planner fills with declared numbers (`rewrite_ratio`, `touched_existing_files`,
  `rewritten_lines`, and a `basis` string saying how it counted), a pure
  `refactorRadiusStatus()` predicate that judges them in JS — mirroring `qualityStatus()`, with
  every comparison behind an explicit null guard because `undefined >= n` is false and
  `null >= 0` is true — and a `refactor-scope` escalation offering three trade-offs (narrow,
  approve, carve out) when a measured number exceeds its ceiling. The verdict is reached
  PER DIMENSION: a ceiling that is usable for one number and unusable for another is reported
  as exactly that, and never as a blanket claim that every declared number is within bounds.
  Thresholds arrive only through `ctx.refactor_radius`, resolved by the controller from
  `quality_gate.py --print-config`, the one door to the effective configuration; a controller
  that does not thread it records `NOT_CONFIGURED` and never halts. Every evaluation emits a
  `refactor-radius` event carrying the measured numbers, the thresholds compared and the
  planner's basis — including the no-fire and not-measured cases — and it renders into
  `decisions-log.md`. Only a truthy human answer disarms the halt, and a suppression is claimed
  only where an answer actually waived a real breach.

### Changed
- **The autonomy contract now names six judgment triggers instead of five, everywhere it is
  stated.** `skills/escalation-gate/SKILL.md` adds `refactor-scope` as the sixth SURFACE trigger
  and describes it accurately as the only one raised by the workflow's own arithmetic, at plan
  time, on a measured breach; `agents/slice-planner.md` gains the doctrine for declaring the
  radius numbers — numbers only, never a verdict, and omitted rather than guessed as a zero;
  `commands/spec-loop.md` applies the six-trigger test and states how a `refactor-scope` answer
  is threaded back; and `README.md` and `references/risk-tiers.md` are reconciled to six, with
  `risk-tiers.md` stating that `refactor-scope` is NOT in the tier funnel because it fires at
  plan time against a run-level ceiling that no tier setting moves. The same files keep their
  separate, unchanged point that the council's `over_scope` flag is a RECORD that decides
  nothing and is still not a trigger. `README.md`'s counted component inventory is re-verified
  against the tree: this run added test-support and harness modules and changed no agent,
  command, skill or runtime-script count.

### Fixed
- **A council objection resolved by a replan no longer passes on the revision's status alone.**
  `slice-wave.workflow.js` used to accept a post-`OBJECT` revision whenever it came back
  `PLANNED`, so one silent retry absorbed the objection: nobody re-read the plan the council had
  rejected and the human never saw it, while the doctrine described the mechanism as blocking.
  `acceptRevisedPlan()` now sends the revision back to one `plan-critic` seat (`critic:replan`),
  records a `replan-recheck` event carrying the verdict and the reason, and escalates
  `council-objection` on a second objection, a fresh safety flag, or an unreadable re-critique.
- **The last three unguarded optional agent-return reads in the wave are guarded.**
  `PLAN_RESULT.required` is `['status']` only and `FIX_RESULT.commits` is optional, so
  `fix.commits.base` (which threw during wave 1 of this run, was mislabelled a
  `budget-exhausted` escalation, and lost the wave), `plan.escalation.trigger` and the
  `plan.split` pass-through were each one absent object away from aborting a whole wave.
  `fixCommits()` falls back to the slice's own shas, `planEscalation()` substitutes a usable
  record so the slice pauses instead of crashing, and `usableSplit()` escalates a childless
  SPLIT at the cause instead of writing a sidecar the validator rejects a stage later.
  `slice_wave_contract_base.py`'s docstring, which recorded two of these as deliberately
  unfixed, is corrected.

### Honest limits of this run
- The radius numbers are the PLANNER'S PRE-EXECUTION DECLARATION — a proxy, not a measured
  diff. A rewrite that blows up mid-implementation is invisible to this gate. No git
  blast-radius measurement script and no second, post-implementation checkpoint were built;
  both were deferred by human decision.
- The gate ships DEFAULT ON, so every installation gains this halt on its next run after
  upgrade rather than opting into it.
- A plan revised after a council `OBJECT` is NOT re-radius-evaluated. Known gap, left
  deliberately.
- The replan re-check is a SINGLE `plan-critic` seat, not the original panel: a tier-3
  objection raised by `guardian` or `skeptic` is re-checked by a different member, and the
  re-check prompt does not carry the objection text. It also runs once, because
  `state.replanned` already vetoes a second replan.
- Teammate blast radius — other-author churn, competing branches — was deliberately not built.
- The catch-all that mislabels a `TypeError` as `budget-exhausted` is unchanged, and the
  `refactor-scope` trigger guard is a TYPE check, so an unrecognized trigger string still fails
  `validate_escalation` downstream exactly as it does today.
- The doctrine changes are prose, and their tests are substring assertions over that prose:
  they prove the doctrine is present and its five-trigger predecessor is gone, and nothing
  about whether an agent obeys it.

## [2.2.2] - 2026-08-28
### Added
- **The quality gate counts branch keywords in code, not in prose.** `quality_gate.py` now
  masks the content of string literals and comments before it scans a source, so a branch word
  or an operator character inside a docstring, a comment or a message string no longer inflates
  that file's complexity. Python is masked through the stdlib `tokenize`; four JavaScript and
  TypeScript extensions — `.js`, `.mjs`, `.cjs`, `.ts`, deliberately not `.jsx` or `.tsx`, whose
  text nodes the scanner has no model of — through a hand scanner that PRESERVES `${}`
  interpolation code, since an interpolation holds real executable code that must stay counted.
  Every other brace language, and every mask failure, falls back to the raw text — the
  over-counting direction, which is the safe one to fail in. Fills are a non-whitespace
  sentinel on purpose: a whitespace fill would turn masked prose into indentation and RAISE a
  whitespace-derived metric. The honest limits. The mask moves `cyclomatic` and `cognitive` in
  one direction only, down, and it leaves `nesting_depth`, `method_lines` and function spans
  exactly equal — no file passes a threshold it was failing on those. And it does not rescue
  `globToRe`, whose cognitive complexity measured 25 before the mask and measures 17 after,
  against a threshold of 15: still over.
- **A `budget-exhausted` answer that actually raises the cap.** The wave args gain one optional
  top-level field, `agent_cap_overrides: {"<slice-id>": <integer>}`. `agentCap` in
  `slice-wave.workflow.js` reads it and the per-slice structural guard enforces the number it
  returns, so a human who authorises a raise now has a lever instead of prose. The channel is
  deliberately narrow: it can only RAISE (a value at or below the review tier's own cap in
  `CAPS` is discarded), it is keyed per slice, it lives in the args object of the single
  re-dispatch the controller hands it to, and it moves no default. An applied raise emits an
  `agent-cap-override` event carrying `{tier, default_cap, effective_cap}`, so the exception is
  auditable in `events.jsonl` rather than inferable from a larger `agents_used`. The record
  itself now offers three controller-named options and its recommended option names the args
  field to write. `budget-exhausted` remains NOT a judgment trigger — its answer is injected
  into no agent prompt, pinned by source text and by execution across the eight pipeline
  roles the one-task fixture drives — plan, critique, task, review, gate, fix, re-review
  and verify. A real slice run builds more prompts than these eight: the tier-3 council
  dispatches several critics, and the fix loop repeats fix and re-review across rounds —
  and the
  per-stage token floor is untouched, having no args-level lever at all: its resource is the
  wave budget the host supplies. The controller still translates the human's free-text answer
  into the integer it writes; nothing in the loop parses that text. An override the channel
  cannot use is no longer discarded in silence: a value at or below the tier default and one
  that does not coerce to a whole number each emit a `decision` event naming the discarded
  value, and a key naming no slice of the wave emits one naming the key, so a mistyped lever is
  visible at the dispatch that carried it rather than only at the next cap record. The value is
  coerced with `Number()`, so a JSON string reading as a whole number — `"14"` — is read as the
  integer 14 and judged against the tier default like any other value. Documented in
  `commands/spec-loop.md` step 7 and `references/run-state-v2.md`.
- **A behavioural test harness that executes `slice-wave.workflow.js`.** The workflow cannot be
  imported as a module — the host wraps the whole script in an implicit async function, so the
  file legally carries a top-level `return` and a top-level `await`. `slice_wave_harness.mjs`
  loads it through the wrapper that already existed on the Python side,
  `slice_wave_contract_base.wrapped_source()`, shelling out to it rather than re-implementing
  it, so the repo holds exactly one wrapper and the two sides cannot drift. The wrapped source
  becomes an `AsyncFunction` driven with mock sandbox globals, and
  `slice_wave_behaviour.test.mjs` asserts on behaviour the workflow really executed rather than
  on its source text — its loader-integrity tests excepted, which hold the wrapper and its name
  honest. The honest limit, stated plainly: those mock globals are an ASSUMED host contract,
  which this repo documents nowhere, so the harness verifies deterministic control flow against
  an assumption. It cannot verify behaviour against the real Workflow host, and a green run
  here is no evidence about that host.

### Changed
- **Gate figures either side of this release are not comparable.** The masking above changes
  what a scan counts, so the `cyclomatic` and `cognitive` values a run writes to `metrics.json`
  drop on source that did not change. Recorded runs dated 2026-08-25 and 2026-08-26 were
  measured under the old semantics, against unmasked text. Reading a later run's numbers as a
  trend against either of those reads a measurement change as a code change. Compare
  like against like: post-release runs against post-release runs.
- **The lost-slice escalation now names its options and asks a matching question.** At 2.2.1
  the record carried an empty options list and a single yes/no ask, "Re-run the wave to retry
  this slice?", so a human's stored free text bound to no option. The record now carries the
  three controller-named options `Retry this slice` / `Skip this slice` / `Stop the run` and
  asks "Retry this slice, skip it and continue the run, or stop the run to investigate the
  silent failure?", matching the crash record's shape with its own tail — the lost-slice record
  has no exception text to diagnose. Pinned by execution in `slice_wave_behaviour.test.mjs` and
  by source text in `test_slice_wave_contract_crash.py`.

### Fixed
- **`escalations.md` renders one section per distinct escalation question.** An
  `escalation-opened` event whose raw `id`, `context` and `question` match a section already on
  the page now rewrites that section in place (`run_state.place_escalation_section`) instead of
  appending a second copy; a record differing in any of those three raw fields is a different
  question and keeps its own section. Matching compares the fingerprint `escalation_identity`
  takes from the raw record, carried on the page as a second HTML-comment anchor, so two rounds
  whose contexts differ only past the renderer's truncation cap are still two questions.
  Replaying run 20260825's recorded `events.jsonl` renders 9 sections where the committed
  artifact has 12, and both rounds of the one id that genuinely re-escalated survive as separate
  sections. Two behaviours are deliberately unchanged: `run_state.open_escalations()` still lists
  every status-OPEN escalation, so de-duplicating the page never silences the human gate, and a
  matching re-emit that carries no answer leaves an already-answered section untouched rather
  than resetting it. `answer_escalation` now writes into the last section for an id that is still
  marked `(status: OPEN)`, which is a no-op for an id owning a single section and stops the second
  round's answer landing under the first round's question. The round component the ids now
  carry (below) makes two rounds two ids; the identity fingerprint stays load-bearing because
  it also covers records this workflow did not write and rounds whose id is shared.
- **Two escalations of one trigger in one slice no longer collide on a single id.** `esc()`
  (`workflows/slice-wave.workflow.js`) now builds the id through `escId`, which appends the
  `:<round>` component the `EscalationRecord` contract already documented: round 1 keeps the
  bare `<slice-id>:<trigger>`, and every later round is suffixed. The round is counted from the
  answers already recorded for that slice and trigger — the one counter that survives a
  re-dispatch — so an id is stable across resumes and the same `answers` map always reproduces
  it. Answer lookup moved with the scheme: `latestAnswer` matches the whole key family and
  returns the newest answered round, so an answer keyed without a round still matches and no
  judgment trigger becomes unanswerable. The planner-`ESCALATE` branch no longer overwrites the
  id it was handed. `run_metrics.merge_escalation_records` needed no change to its merge
  semantics — it keys on the whole id, so distinct rounds were already distinct records and are
  now pinned by test — and its docstring says so. The function itself was edited this cycle:
  its loop body moved into the `_fold_escalation_record_into` helper, leaving the keying
  behaviour identical.
- **Two prose surfaces now describe the escalation records the wave really raises.** One
  `internal-error` trigger raises two records that carry different evidence, and
  `skills/escalation-gate/SKILL.md` gave a single account of both in two places: it said the
  lost-slice record announces the evidence it lacks, and it gave the exception record's
  retry/skip/stop ask as the ask of the trigger at large. The lost-slice context announces no
  gap — it states that a null result proves nothing about which guard ran, and that the cause
  is unknown. The skill now separates the two by what each record carries and what each one
  asks, and `test_slice_wave_contract.py` holds its account of the lost-slice ask against the
  wave's own question text, so a later change to that ask breaks the doc pin instead of
  drifting past it. The inline-mode twin's step 3 in `agents/slice-worker-fallback.md` now
  states the trigger the workflow really raises on a spent task retry: `ambiguity`,
  unconditionally, whatever the last status was, and never `internal-error` — a dispatch that
  returned nothing, a second `NEEDS_CONTEXT`, and a `BLOCKED` naming a real blocker all
  collapse into that one record, whose context carries the blocker text or the questions
  returned. The twin is a behavioural spec rather than commentary: an agent driving a slice
  inline reads it and writes the record it describes, and its earlier mapping of a real
  blocker to `material-assumption` or `review-block` had the two modes filing one failure
  under different triggers.
- **Three guards that did not exercise what they claimed to cover.** The crash-context
  truncation test renders through the real `run_state.render_escalation()` instead of
  re-implementing its collapse-and-truncate, and the duplicated copy of the render limit is
  deleted, so the test reads whatever limit the renderer really applies and cannot drift from
  it. The substring-safety test drives the real legacy matcher over a v1 `escalations.md`
  body, rather than comparing two Python literals to each other, so a change to the matcher's
  containment semantics turns it red. And the trigger-enum guard now covers the enum's true
  number of homes — six: the three Python tuples in `run_state.py`, `run_metrics.py` and
  `dashboard_server.py`, the workflow's own enum line, and two PROSE homes —
  `agents/slice-worker-fallback.md`, the enumeration a worker reads before it names a
  trigger, and `references/run-state-v2.md`, the `EscalationRecord`'s authoritative shape
  doc. It previously held four surfaces against each other and named five. The prose pins
  collapse whitespace on both sides, so a whitespace re-flow of either document leaves them
  intact.
- **The coverage manifest names its `__main__` shims symbolically.** Entries in
  `scripts/coverage_omit.txt` read `scripts/<file>.py:__main__` instead of an absolute line
  range, and `measure_coverage.resolve_main_shim` locates the guard header and its indented
  block in the file's own source at measure time. A pinned range went stale the moment the
  file grew: the omission then pointed at ordinary code further up, with its rationale still
  claiming the shim, quietly excusing lines the manifest never meant to excuse. Three of the
  thirteen entries had already drifted that way — the `quality_gate.py`, `run_metrics.py` and
  `run_state.py` ranges each named lines other than their own file's guard. Symbolic entries
  carry no line numbers to renumber, so growth cannot repoint them.
  `test_measure_coverage_manifest.py` pins the resolved block size of every target, so a
  statement added beneath a guard grows the block and fails the suite until the new size is
  deliberately accepted.

## [2.2.1] - 2026-08-27
### Added
- **`internal-error` escalation trigger** — a seventh `EscalationRecord.trigger` value for machine
  failure, one string covering both shapes of it: an unhandled exception that aborted a slice
  (`workflows/slice-wave.workflow.js` — the catch-all at :892) and a slice that returned no result
  at all (:919). The enum lives at :40. The crash record leads with the real exception text and the
  last stage/role dispatched before the failure, in that order — a guaranteed ordering, so the
  400-character limit `render_escalation()` puts on a context cuts the fixed classification prose
  before either diagnostic. The ordering is not a promise that both diagnostics fit: measured
  against the longest stage text, an exception message past ~286 characters pushes the stage
  attribution out of the rendered context entirely (its "starting point, not a culprit" caveat drops
  at ~200), and only the exception text, which leads, is truncated last. That stage is the most
  recent dispatch, **not** a per-throw stage: the whole stage sequence sits under one `try`, so the
  loop cannot know which stage threw, and the record says "after", not "in", and says why. It also
  refuses to guess the cause: all an exception reaching the catch-all proves is that neither
  structural guard *raised* its escalation record — not that the crash started outside a guard,
  since `budget.remaining()` is called inside the token-floor guard itself — so it may be a loop or
  agent-contract bug and it may equally be a host- or agent-layer resource failure (a rejected agent
  call on a hard token or rate limit, say) — the exception text is the evidence, not the label. The
  lost-slice record at :919 follows the same rule in the same words: neither guard *raised* its
  escalation record, "and that is all a null result proves, not that no guard check ran" — and it no
  longer denies a resource cause it cannot rule out. It is not a judgment trigger and it is not
  answerable by re-dispatching an agent. The two records offer different things. The crash record
  from `runSliceError` passes three explicit options — retry the slice, skip it, stop the run —
  and each option's detail names the controller as what applies it, because the loop itself
  implements none of the three. The lost-slice record passes an empty options array, so `esc()`
  substitutes a single generic option labelled "Proceed with the recommended default" whose detail
  repeats the context; its retry ask lives in its question, "Re-run the wave to retry this slice?",
  not in an option. Either way the controller is what acts. Added to
  `ESCALATION_TRIGGERS` in `run_state.py`, `run_metrics.py` and `dashboard_server.py`, to the record
  shape in `references/run-state-v2.md`, and to the enumerations in
  `skills/escalation-gate/SKILL.md` and `agents/slice-worker-fallback.md` — the last of these being
  the behavioral spec for the inline-mode twin, which must classify identically.

### Changed
- **`budget-exhausted` narrowed to a resource signal** — the string stays and its position in the
  enum is unchanged; only its meaning narrows. It is now raised solely by the loop's two structural
  guards, the per-slice agent cap and the per-stage token floor (`slice-wave.workflow.js:425` and
  `:427`), both of which keep their existing wording. It no longer covers an unhandled exception or
  a lost slice: through 2.2.0 the catch-all relabelled every uncaught error as a `budget-exhausted`
  "wave interrupted" escalation, which in run 20260825-scope-ceiling asked for budget on behalf of
  an unguarded optional-field read — a `TypeError` that no amount of budget would have prevented —
  and the lost-slice record carried the same trigger. Both are now `internal-error`. The claim
  is deliberately about that concrete failure, not about uncaught errors in general — as the
  Added entry above says, some of those really are resource failures.
  There are still exactly five *judgment* triggers; neither `budget-exhausted` nor `internal-error`
  is one, and `internal-error` is deliberately outside the answerable set, which stays at five.
- **`schema_version` stays `2`** — adding an enum value is an additive change to the sidecar
  contract, so the version is deliberately not bumped (human-decided). `SCHEMA_VERSION` in
  `run_state.py` and `run_metrics.py` is unchanged, and existing run directories carrying
  `budget-exhausted` records still validate and still bucket as `budget-exhausted` rather than
  degrading to `other`.

#### Compatibility: a plugin downgrade to 2.2.0 DISCARDS an affected run dir

This is worse than a mis-labelled trigger, and it is not symmetric with a normal additive change.
`run_state.py`'s `persist_slice` validates the whole `SliceResult` **before** it writes anything and
raises `SidecarInvalid` on an unrecognised `trigger`; only after validation passes does it write the
sidecar, append the slice's events, and render `slice-<id>-report.md`. Under 2.2.0, whose
`ESCALATION_TRIGGERS` has no `internal-error`, a slice that escalated with that trigger therefore
produces **no sidecar, no events and no report at all** — not a wrongly-labelled record. The slice
reports `ESCALATED` with nothing on disk saying why, and the diagnostic information the escalation
existed to deliver is gone.

Consequences, stated plainly: a run directory written by this version is **not readable by 2.2.0**,
and the repository and the installed plugin must be updated together. Re-running the affected slice
under 2.2.0 will not recover the record, because the record was never written.

### Scope and limits of this change

Verifiability ceiling: nothing this entry describes in `workflows/slice-wave.workflow.js` has been
executed. The loop resolves its workflow from the installed plugin cache, so the merged file takes
effect only after a plugin reinstall. Those claims rest on a real `node` parse of the source plus
source-text contract assertions (`test_slice_wave_contract_crash.py`), which prove a construct is
present and cannot prove it behaves. The Python-side tuple, validation, metrics and dashboard
changes are covered by executed tests.

## [2.2.0] - 2026-08-26
### Added
- **Run-level scope ceiling** — an optional `scope_ceiling` list in `dag.json` (validated
  only when present; a run without one stays fully valid and mutable), threaded through
  `ctx` and prefixed to **every** agent prompt by the wave's shared packet as a binding
  "do NOT build these" block. The read is type-safe, not merely null-safe: an array passes
  through, a lone non-empty string is coerced to a one-element list (a realistic return
  from an LLM controller populating `ctx` from prose), and any other non-array value reads
  as absent rather than throwing. Shape: `references/run-state-v2.md`.
- **Record-only `critique.over_scope`** — an optional `{flag, reason}` field on the
  council verdict contract, owned by plan-critic's weighted scope lane. It is carried
  into the `council-verdict` event and the slice sidecar untouched by any control-flow
  branch: it never blocks, never suppresses a split, never raises an objection, and is
  never a finding.
- **One durable `deferred` event per defer-hinted concern** — each `defer`-hinted council
  concern now emits its own `deferred` event (`{summary, source: "plan-critique"}`, plus a
  bare-boolean `over_scope: true` marker when applicable), read by the reviewer as advisory
  context only — never a findings filter.
- **Weighted scope lane on plan-critic** — plan-critic's existing Scope mandate now owns the
  over-scope record; no new agent, no change to any panel size or objection threshold.
- **Fail-closed sidecar validation and honest rendering of the scope record** — a present
  `critique.over_scope` must carry a real boolean `flag` and a string-or-null `reason`; a
  malformed record invalidates the whole sidecar (`persist_slice` raises and writes nothing)
  rather than being quietly ignored. Absent and explicit `null` are both valid and mean "no
  scope judgement was recorded" — which is a different claim from `flag: false`, and the two
  render differently. One shared renderer produces four distinct human outcomes and collapses
  none of them into another: nothing at all when no judgement was recorded, `scope: clean` for
  `flag: false`, `SCOPE-FLAGGED` plus the reason when one was given, and `scope: unreadable`
  when a present record's own shape cannot be trusted. The decisions-log verdict line and the
  slice report's `Iron Council` value share that renderer, so the two human surfaces cannot
  disagree; a `deferred` event whose payload marks `over_scope: true` renders with a `SCOPE `
  prefix in the decisions log.
- **Null-honest scope counters in `run_metrics.py`** — `safety.over_scope_deferrals` counts
  `deferred` events carrying that boolean marker, and therefore lives at the `safety` top
  level beside `deferrals_total`, **not** inside `safety.council`, whose every other key
  shares the council-verdict population. Both counters are null-honest:
  `safety.council.over_scope_flags` counts flagged `council-verdict` payloads and stays `null`
  when no payload carried a boolean flag, because "no payload recorded a scope judgement" is
  not evidence that nothing was over scope — and a malformed record counts as no record rather
  than as a clean one. The legacy v1-prose channel reports both as `null`; it never carried a
  scope judgement. Both feed reporting only: neither feeds a threshold, a gate or a blocking
  decision.

### Fixed
- **Wave-aborting unguarded `commits` read** — a task that legitimately committed nothing
  returns `DONE` with `commits` absent (not required by `TASK_RESULT`); the Stage-T loop's
  unguarded `r.commits.head` read threw a `TypeError` that the catch-all mislabelled as a
  budget-exhausted "wave interrupted" escalation. The read is now guarded the way the
  fix/debug-fix sites already guard it.
- **Missing `quality-gate-block` answer injection** — no prompt builder had a site for a
  human's answer to a quality-gate escalation, so the answer could not reach the
  re-dispatched slice. `fixPrompt` now carries it through `answerFor` ("apply it, do not
  re-raise"); `verifyPrompt` carries it through a new context-only sibling `answerContext`,
  which shows the answer without instructing a transcription-only reporter to change what
  it reports — the suite result and `quality.summary_pass`/`violations` stay verbatim from
  the real output.

### Scope and limits of this change

Read this before reading "Added" as "scope creep no longer happens". Of everything added
above, exactly one thing reduces the effort spent expanding scope: the **weighted scope lane
on `plan-critic`**, which makes the critic look at the run's ceiling and the slice goal and
say so. The ceiling, the `over_scope` record, the `deferred` channel and both counters do not
prevent anything — they build durable **recording**, and non-re-admission only in the sense
that recording buys: a scope judgement is written down with its reason, survives into
`events.jsonl`, the sidecar and `decisions-log.md`, and is visible to the reviewer and the
human, so deferred work cannot quietly come back unremarked. Nothing stops it coming back.
The record blocks nothing, filters no finding, suppresses no split and raises no objection. Work the council judges out of scope and asks
not to be built is a `defer`-hinted concern, logged as a `deferred` event; the record itself
is explicitly "flag it and still build it" when the goal genuinely asks for it.

The mechanism was exercised on live input by the run that added it, which is the strongest
available evidence for both halves of that claim. The two workflow defects fixed above were
themselves an approved, recorded scope increase. In the same run the council found two more
defects of the same class in `workflows/slice-wave.workflow.js` — an unguarded
`plan.escalation.*` read on the ESCALATE branch (:479), which turns a planner returning
`ESCALATE` with no `escalation` object into the same mislabelled "wave interrupted"
`TypeError`, and a `plan.split` pass-through on the SPLIT branch (:478) that hands `undefined`
downstream to fail sidecar validation there instead. Both are one-line guards; both were
**deferred rather than fixed**, because they fell outside the approved increase. They are
logged with `file:line` evidence and are deliberately still unbuilt. That is the mechanism
working as designed, and it is also the plainest possible demonstration that recording a
scope judgement is not the same as acting on it.

Verifiability ceiling: nothing this change added to `workflows/slice-wave.workflow.js` has
ever been executed. The loop resolves its workflow from the installed plugin cache, so the
merged file takes effect only after a plugin reinstall — the run that wrote it ran a patched
copy of that cache, not this file. That JS carries no coverage gate (`measure_coverage.py`
measures Python only). Its guarantees rest on a real `node` parse of the source plus
source-text assertions that prove a guard, a helper call or a schema field is *present*, and
on three pure helpers (`scopeRecord`, `deferralEvents`, `scopeCeilingList`) extracted from
that source and executed under real `node` in isolation. Presence is not behaviour, and three
pure helpers are not the pipeline — treat every runtime claim about the workflow in this entry
as reviewed and asserted, not observed.

## [2.1.0] - 2026-08-10
Runtime and trust fixes from the 2026-08-06/07 production-run analysis
(Groundworks.Jobs): active runtime was ~3–5h for 3–5 slices, but one run read
as 15h48m — 7.6h of it a silently-parked publish prompt, 2h20m a discarded
re-run of an already-merged slice, plus controller time re-verifying two
false-PASS gate labels caused by a guard-hook false positive.

### Fixed
- **Guard hook redirect false positive** — `spec_loop_guard.py` denied any
  command containing `quality-gate.json` plus any redirect character, so the
  verifier's read-only gate invocation with `2>&1` was blocked (two false
  PASS labels in run 20260807). A write must now actually target a
  `quality-gate.json` path (redirect into it, `tee`/`mv`/`cp` naming it,
  `sed -i` on it).
- **Wave re-dispatch re-ran merged slices** — the controller re-dispatched
  the full wave after escalation answers, relying on journal replay to make
  DONE slices free; a cache miss re-ran a merged slice against a deleted
  worktree for 140 minutes and the result was discarded. Re-dispatch now
  includes only non-terminal slices.
- **Agent-labeled gate verdicts** — the verifier returned a self-labeled
  PASS/FAIL enum that twice contradicted its own detail text. It now
  transcribes the gate JSON's `summary.pass` verbatim (`summary_pass`,
  null when no JSON was produced) and the workflow computes the status
  deterministically — null or any violation is FAIL, fail closed.
- **Run-state fragments from a drifted cwd** — `run_state.py` silently
  created `server/docs/spec-loop/<run-id>/` fragments when a `cd server &&`
  test command left the session cwd in a subdirectory. Every subcommand now
  refuses a `--run-dir` that lacks `dag.json` (exit 2) instead of creating
  one; Phase 5 verifies the run dir is whole at the repo root before `.done`.
- **Vacuous quality-gate passes** — a whole-run gate measurement could return
  `pass: true` with zero checks over a 60-file range, indistinguishable from
  a measured pass. `summary` now carries `checks` and `vacuous`; Phase 5
  treats a vacuous pass over a code-changing range as unmeasured, never green.

### Added
- **Human-wait alerts** — the controller fires a best-effort desktop
  notification (`osascript` + terminal bell) before every AskUserQuestion
  round and the publish prompt (observed: a finished run waited 7.6h
  overnight at the publish prompt).
- **Suite segmentation contract** — a `test_command` may be a ` ; `-joined
  segment list; the baseline step splits any invocation near the 10-minute
  tool ceiling per test project, and every runner executes each segment as
  its own tool call (a monolithic call at the ceiling was killed mid-suite
  twice in run 20260807's Phase 5).
- **Runtime expectations** — README documents the measured Opus 5 envelope
  (~40–70 min per slice all-in; 3–5 slice runs are 3–5 hour jobs) and that
  v1-on-Opus-4.8 timings are not the comparison baseline.

## [2.0.0] - 2026-07-30

Ground-up Opus 5-native rewrite. Same theology — autonomous spec-driven
development, surface only genuine decisions, built-in review, scripted quality
gates, knowledge-graph integration — rebuilt on the Claude Code Workflow tool
so orchestration is deterministic code instead of prompt text. Clean break:
schemas, agents, and internals redesigned; see
`plugins/spec-loop/references/migration-from-v1.md`.

### Added
- **Workflow-native waves** — one Workflow invocation per wave
  (`workflows/slice-wave.workflow.js`): slices run as deterministic JS
  pipelines with schema-forced structured handoffs, per-tier agent caps
  (10/18/32), bounded loops (fix ≤2, replan ≤1, task retry ≤1), fail-closed
  synthesis on unusable returns, and journal-cached resume — an answered
  escalation replays completed stages at zero cost and re-runs only the
  answered stage.
- **Consolidated review machinery** — one `plan-critic` carrying all five
  council mandates (premise/design/scope/risk/consistency) and one
  `pr-reviewer` carrying all review aspects with per-aspect attestation.
  Panels survive where independence pays: guardian (risk-only SAFETY veto) on
  intake/Tier-3, skeptic (premise-only) on intake/`--thorough`, two-reviewer
  split + ONE batched finding-verifier at Tier 3.
- **Mechanical finding-anchor checks** — review packages
  (`scripts/review_package.py`, `-U5`) embed a hunk index; a finding whose
  location or evidence quote doesn't match the code is refuted without
  judgment by the fixer (refutation right) or the batched verifier.
- **Deterministic run-state scripts** — `dag.py` (wave computation, split
  grafting), `worktrees.py` (worktree/branch lifecycle), `run_state.py`
  (fail-closed sidecar validation, `events.jsonl`, prose rendering) replace
  prompt-space scheduling.
- **`events.jsonl` machine channel** — pinned payload contracts (timing only
  from journal-extracted stamps, escalations paired by id, SAFETY flags);
  prose logs are rendered from the same objects and carry no machine grammar.
- **Tier auto-promotion** — implementer-touched files matched against
  `tier3_surfaces` globs promote the review shape deterministically.
- **`--thorough` flag**; per-repo quality-gate overlay
  (`.spec-loop/quality-gate.json`, guard-protected); `models` promotion knob.
- **Inline fallback** — `slice-worker-fallback` agent runs the same pipeline
  shape when the Workflow tool is unavailable (`dag.json` `mode: "inline"`).

### Changed
- Agent inventory 23 → 13; skills reduced to the judgment layers
  (escalation-gate, TDD, systematic-debugging, verification-before-completion,
  router); the 282-line slice-worker agent and the SDD/worktree/review-depth
  orchestration skills are deleted — their job is JS control flow now.
- Global config namespace `~/.claude/spec-loop/` → `~/.claude/spec-loop-2/`
  (first run offers import); the guard hook protects both the global config
  and the per-repo overlay.
- `run_metrics.py` reads events.jsonl + sidecars (schema_version 2); v1
  transcript scraping and prose-grammar parsing dropped (v1 run dirs still
  render in `trend` via a walled-off legacy path). Durations derive only from
  journal-extracted payload stamps — never the batch collection stamp.
- Dashboard reads recorded `waves[]` + sidecar v2 + events.jsonl; v1 run dirs
  render via legacy rules; container/state names moved to `spec-loop-2-*`.
- `/spec-loop:peer-review` consolidated to `peer-reviewer` + report-only
  `pr-reviewer` + a report-only quality-gate run; report `schema_version: 2`.
- Per-finding verifier agents, the whole-branch `code-reviewer` double-pass,
  and per-task reviewers below Tier 3 are gone; `code-simplifier` runs only at
  Tier 3/`--thorough` (at Tier 2, "simplify" is a finding category the fixer
  applies).

### Removed
- `council_contracts.py` (verdict validation is tool-layer schema enforcement;
  sidecar validation moved to `run_state.py`), `slice-*-agents.jsonl`, the
  pinned decisions-log/QUALITY-GATE line grammars, transcript token scraping,
  and the `--budget` flag (cost control is structural: caps + bounds; the
  Workflow token ceiling activates when the session sets a token target).

[Unreleased]: https://github.com/z2297/spec-loop-2/compare/v2.5.0...HEAD
[2.5.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.5.0
[2.4.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.4.0
[2.3.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.3.0
[2.2.2]: https://github.com/z2297/spec-loop-2/releases/tag/v2.2.2
[2.2.1]: https://github.com/z2297/spec-loop-2/releases/tag/v2.2.1
[2.2.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.2.0
[2.1.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.1.0
[2.0.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.0.0
