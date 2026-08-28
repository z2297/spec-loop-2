# Changelog

All notable changes to the spec-loop plugin are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/). History before 2.0.0 lives in the
[v1 repository](https://github.com/z2297/spec-loop).

## [Unreleased]

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

[Unreleased]: https://github.com/z2297/spec-loop-2/compare/v2.2.2...HEAD
[2.2.2]: https://github.com/z2297/spec-loop-2/releases/tag/v2.2.2
[2.2.1]: https://github.com/z2297/spec-loop-2/releases/tag/v2.2.1
[2.2.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.2.0
[2.1.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.1.0
[2.0.0]: https://github.com/z2297/spec-loop-2/releases/tag/v2.0.0
