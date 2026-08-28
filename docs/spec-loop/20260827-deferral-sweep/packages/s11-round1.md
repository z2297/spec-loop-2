# Review package: 32c68bebf566524f3aad16e711a19f856957a71f..13525a4  (context: -U5)

## Commits
13525a4 changelog: reconcile the Unreleased section into one release note
8956875 changelog: the symbolic __main__ omission and the staleness it removes
737bad0 changelog: one bullet for the prose surfaces that described the wrong escalation record
5bb7ebe changelog: the three tests that now exercise real code paths
db9b01f changelog: one statement of the round component, verified against escId
0763890 changelog: the behavioural harness and the host contract it only assumes
dcb9be4 changelog: warn that gate figures are not comparable across the measurement change
d37bae0 changelog: the literal and comment mask, its direction of failure and its two limits
d0bed9c changelog: the cap override discard sentence describes the coercion the code performs

## Files changed
 CHANGELOG.md | 114 ++++++++++++++++++++++++++++++++++++++++++++++++-----------
 1 file changed, 93 insertions(+), 21 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
11,
25
],
[
37,
61
],
[
64,
69
],
[
79,
79
],
[
94,
96
],
[
109,
152
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index eb1dce6..077fd54 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -6,10 +6,25 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 
 ### Added
+- **The quality gate counts branch keywords in code, not in prose.** `quality_gate.py` now
+  masks the content of string literals and comments before it scans a source, so a branch word
+  or an operator character inside a docstring, a comment or a message string no longer inflates
+  that file's complexity. Python is masked through the stdlib `tokenize`; four JavaScript and
+  TypeScript extensions — `.js`, `.mjs`, `.cjs`, `.ts`, deliberately not `.jsx` or `.tsx`, whose
+  text nodes the scanner has no model of — through a hand scanner that PRESERVES `${}`
+  interpolation code, since an interpolation holds real executable code that must stay counted.
+  Every other brace language, and every mask failure, falls back to the raw text — the
+  over-counting direction, which is the safe one to fail in. Fills are a non-whitespace
+  sentinel on purpose: a whitespace fill would turn masked prose into indentation and RAISE a
+  whitespace-derived metric. The honest limits. The mask moves `cyclomatic` and `cognitive` in
+  one direction only, down, and it leaves `nesting_depth`, `method_lines` and function spans
+  exactly equal — no file passes a threshold it was failing on those. And it does not rescue
+  `globToRe`, whose cognitive complexity measured 25 before the mask and measures 17 after,
+  against a threshold of 15: still over.
 - **A `budget-exhausted` answer that actually raises the cap.** The wave args gain one optional
   top-level field, `agent_cap_overrides: {"<slice-id>": <integer>}`. `agentCap` in
   `slice-wave.workflow.js` reads it and the per-slice structural guard enforces the number it
   returns, so a human who authorises a raise now has a lever instead of prose. The channel is
   deliberately narrow: it can only RAISE (a value at or below the review tier's own cap in
@@ -17,39 +32,53 @@ All notable changes to the spec-loop plugin are documented here. The format is
   re-dispatch the controller hands it to, and it moves no default. An applied raise emits an
   `agent-cap-override` event carrying `{tier, default_cap, effective_cap}`, so the exception is
   auditable in `events.jsonl` rather than inferable from a larger `agents_used`. The record
   itself now offers three controller-named options and its recommended option names the args
   field to write. `budget-exhausted` remains NOT a judgment trigger — its answer is injected
-  into no agent prompt, pinned by source text and by execution across
-  all eight prompts one slice builds running plan, critique, task, review, gate, fix, re-review
-  and verify — and the per-stage
-  token floor is untouched, having no args-level lever at all: its resource is the wave budget
-  the host supplies. The controller still translates the human's free-text answer into the
-  integer it writes; nothing in the loop parses that text. An override the channel cannot use
-  is no longer discarded in silence: a value at or below the tier default, a non-integer value,
-  or a key naming no slice of the wave emits a `decision` event naming the discarded value, so
-  a mistyped lever is visible at the dispatch that carried it rather than only at the next cap
-  record. Documented in `commands/spec-loop.md`
-  step 7 and `references/run-state-v2.md`.
+  into no agent prompt, pinned by source text and by execution across all eight prompts one
+  slice builds running plan, critique, task, review, gate, fix, re-review and verify — and the
+  per-stage token floor is untouched, having no args-level lever at all: its resource is the
+  wave budget the host supplies. The controller still translates the human's free-text answer
+  into the integer it writes; nothing in the loop parses that text. An override the channel
+  cannot use is no longer discarded in silence: a value at or below the tier default and one
+  that does not coerce to a whole number each emit a `decision` event naming the discarded
+  value, and a key naming no slice of the wave emits one naming the key, so a mistyped lever is
+  visible at the dispatch that carried it rather than only at the next cap record. The coercion
+  is `Number()`, so a JSON string reading as a whole number — `"14"` — becomes `14` and the
+  raise IS applied, emitting `agent-cap-override` and no discard event. Documented in
+  `commands/spec-loop.md` step 7 and `references/run-state-v2.md`.
+- **A behavioural test harness that executes `slice-wave.workflow.js`.** The workflow cannot be
+  imported as a module — the host wraps the whole script in an implicit async function, so the
+  file legally carries a top-level `return` and a top-level `await`. `slice_wave_harness.mjs`
+  loads it through the wrapper that already existed on the Python side,
+  `slice_wave_contract_base.wrapped_source()`, shelling out to it rather than re-implementing
+  it, so the repo holds exactly one wrapper and the two sides cannot drift. The wrapped source
+  becomes an `AsyncFunction` driven with mock sandbox globals, and
+  `slice_wave_behaviour.test.mjs` asserts on behaviour the workflow really executed rather than
+  on its source text — its loader-integrity tests excepted, which hold the wrapper and its name
+  honest. The honest limit, stated plainly: those mock globals are an ASSUMED host contract,
+  which this repo documents nowhere, so the harness verifies deterministic control flow against
+  an assumption. It cannot verify behaviour against the real Workflow host, and a green run
+  here is no evidence about that host.
 
 ### Changed
+- **Gate figures either side of this release are not comparable.** The masking above changes
+  what a scan counts, so the `cyclomatic` and `cognitive` values a run writes to `metrics.json`
+  drop on source that did not change. Recorded runs dated 2026-08-25 and 2026-08-26 were
+  measured under the old semantics, against unmasked text. Reading a later run's numbers as a
+  trend against either of those reads a measurement change as a code change. Compare
+  like against like: post-release runs against post-release runs.
 - **The lost-slice escalation asks the three-way question its options already offered.** The
   record widened to `Retry this slice` / `Skip this slice` / `Stop the run` but still asked
   "Re-run the wave to retry this slice?", so a human answering "no" had chosen none of the
   three and the stored free text bound to no option. It now asks "Retry this slice, skip it and
   continue the run, or stop the run to investigate the silent failure?", matching the crash
   record's shape with its own tail — the lost-slice record has no exception text to diagnose.
   Pinned by execution in `slice_wave_behaviour.test.mjs` and by source text in
   `test_slice_wave_contract_crash.py`.
 
 ### Fixed
-- **The escalation-gate skill describes the lost-slice ask the wave actually emits.**
-  `skills/escalation-gate/SKILL.md` still said the lost-slice record "asks only whether to re-run
-  the wave" after that record widened to the three-way retry/skip/stop question. The sentence now
-  names the three-way ask and its own tail, and `test_slice_wave_contract.py` holds the doc
-  against the wave's real question text, so the next change to the ask breaks the doc pin instead
-  of drifting past it.
 - **`escalations.md` renders one section per distinct escalation question.** An
   `escalation-opened` event whose raw `id`, `context` and `question` match a section already on
   the page now rewrites that section in place (`run_state.place_escalation_section`) instead of
   appending a second copy; a record differing in any of those three raw fields is a different
   question and keeps its own section. Matching compares the fingerprint `escalation_identity`
@@ -60,14 +89,13 @@ All notable changes to the spec-loop plugin are documented here. The format is
   sections. Two behaviours are deliberately unchanged: `run_state.open_escalations()` still lists
   every status-OPEN escalation, so de-duplicating the page never silences the human gate, and a
   matching re-emit that carries no answer leaves an already-answered section untouched rather
   than resetting it. `answer_escalation` now writes into the last section for an id that is still
   marked `(status: OPEN)`, which is a no-op for an id owning a single section and stops the second
-  round's answer landing under the first round's question. Escalation ids now carry a round
-  component from the second round onward (see below), so two rounds are two ids; the identity
-  fingerprint stays load-bearing because it also covers records this workflow did not write and
-  rounds whose id is shared.
+  round's answer landing under the first round's question. The round component the ids now
+  carry (below) makes two rounds two ids; the identity fingerprint stays load-bearing because
+  it also covers records this workflow did not write and rounds whose id is shared.
 - **Two escalations of one trigger in one slice no longer collide on a single id.** `esc()`
   (`workflows/slice-wave.workflow.js`) now builds the id through `escId`, which appends the
   `:<round>` component the `EscalationRecord` contract already documented: round 1 keeps the
   bare `<slice-id>:<trigger>`, and every later round is suffixed. The round is counted from the
   answers already recorded for that slice and trigger — the one counter that survives a
@@ -76,10 +104,54 @@ All notable changes to the spec-loop plugin are documented here. The format is
   returns the newest answered round, so an answer keyed without a round still matches and no
   judgment trigger becomes unanswerable. The planner-`ESCALATE` branch no longer overwrites the
   id it was handed. `run_metrics.merge_escalation_records` needed no logic change — it keys on
   the whole id, so distinct rounds were already distinct records and are now pinned by test —
   and its docstring says so.
+- **Two prose surfaces now describe the escalation records the wave really raises.** One
+  `internal-error` trigger raises two records that carry different evidence, and
+  `skills/escalation-gate/SKILL.md` gave a single account of both in two places: it said the
+  lost-slice record announces the evidence it lacks, and it gave the exception record's
+  retry/skip/stop ask as the ask of the trigger at large. The lost-slice context announces no
+  gap — it states that a null result proves nothing about which guard ran, and that the cause
+  is unknown. The skill now separates the two by what each record carries and what each one
+  asks, and `test_slice_wave_contract.py` holds its account of the lost-slice ask against the
+  wave's own question text, so a later change to that ask breaks the doc pin instead of
+  drifting past it. The inline-mode twin's step 3 in `agents/slice-worker-fallback.md` now
+  states the trigger the workflow really raises on a spent task retry: `ambiguity`,
+  unconditionally, whatever the last status was, and never `internal-error` — a dispatch that
+  returned nothing, a second `NEEDS_CONTEXT`, and a `BLOCKED` naming a real blocker all
+  collapse into that one record, whose context carries the blocker text or the questions
+  returned. The twin is a behavioural spec rather than commentary: an agent driving a slice
+  inline reads it and writes the record it describes, and its earlier mapping of a real
+  blocker to `material-assumption` or `review-block` had the two modes filing one failure
+  under different triggers.
+- **Three guards that did not exercise what they claimed to cover.** The crash-context
+  truncation test renders through the real `run_state.render_escalation()` instead of
+  re-implementing its collapse-and-truncate, and the duplicated copy of the render limit is
+  deleted, so the test reads whatever limit the renderer really applies and cannot drift from
+  it. The substring-safety test drives the real legacy matcher over a v1 `escalations.md`
+  body, rather than comparing two Python literals to each other, so a change to the matcher's
+  containment semantics turns it red. And the trigger-enum guard now covers the enum's true
+  number of homes — six: the three Python tuples in `run_state.py`, `run_metrics.py` and
+  `dashboard_server.py`, the workflow's own enum line, and two PROSE homes —
+  `agents/slice-worker-fallback.md`, the enumeration a worker reads before it names a
+  trigger, and `references/run-state-v2.md`, the `EscalationRecord`'s authoritative shape
+  doc. It previously held four surfaces against each other and named five. The prose pins
+  collapse whitespace on both sides, so a whitespace re-flow of either document leaves them
+  intact.
+- **The coverage manifest names its `__main__` shims symbolically.** Entries in
+  `scripts/coverage_omit.txt` read `scripts/<file>.py:__main__` instead of an absolute line
+  range, and `measure_coverage.resolve_main_shim` locates the guard header and its indented
+  block in the file's own source at measure time. A pinned range went stale the moment the
+  file grew: the omission then pointed at ordinary code further up, with its rationale still
+  claiming the shim, quietly excusing lines the manifest never meant to excuse. Three of the
+  thirteen entries had already drifted that way — the `quality_gate.py`, `run_metrics.py` and
+  `run_state.py` ranges each named lines other than their own file's guard. Symbolic entries
+  carry no line numbers to renumber, so growth cannot repoint them.
+  `test_measure_coverage_manifest.py` pins the resolved block size of every target, so a
+  statement added beneath a guard grows the block and fails the suite until the new size is
+  deliberately accepted.
 
 ## [2.2.1] - 2026-08-27
 ### Added
 - **`internal-error` escalation trigger** — a seventh `EscalationRecord.trigger` value for machine
   failure, one string covering both shapes of it: an unhandled exception that aborted a slice
