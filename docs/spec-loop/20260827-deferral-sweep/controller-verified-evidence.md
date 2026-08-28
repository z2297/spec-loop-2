# Controller-verified evidence — run 20260827 intake

Everything here was produced by the controller running real commands at intake, not reported by
an agent. Scripts live in the session scratchpad (`verify-harness.mjs`, `verify-lost.mjs`,
`verify-trunc.mjs`). Reproduce, don't trust.

## 1. A real Node behavioural harness for `slice-wave.workflow.js` WORKS

The skeptic lane claimed this; the controller reproduced it independently from the description
alone, without reusing the skeptic's script (per the graph pattern
*an-audit-of-a-self-report-must-not-itself-be-self-reported*).

**Technique.** The file cannot be imported as an ES module: it has a top-level `return` (:923)
and a top-level `await` (:912), because the Workflow host implicitly wraps the whole script in
an async function. So:

1. One mechanical transform, no content edit: `export const meta = {` → `const meta = {`
   (`export` is illegal inside a function body).
2. `new (Object.getPrototypeOf(async function(){}).constructor)(
   'args','agent','parallel','log','budget','phase','pipeline', src)`
3. Call it with mock sandbox globals.

**Verified prerequisite.** The workflow file uses NO host or Node API — `grep -nE
'\b(require|import|process|__dirname|fs\.|readFile|Date\.now|Math\.random|new Date)\b'` returns
exactly one hit, `:287`, and that is the English word "require" inside a prose string. It is
pure logic over `args` plus injected globals.

**Result — the caught-exception path, agent() always throws:**

```
status      : ESCALATED
escalations : 1
  id       : s1:internal-error
  trigger  : internal-error
  title    : slice crashed after plan
  options  : Retry this slice | Skip this slice | Stop the run
  ctx len  : 860
```

That is `runSlice`'s catch-all → `runSliceError` → `esc` → `escalated` executing for real. It
would catch a wrong trigger string, a wrong option count, a wrong title, or a reordered context.

**Honest limit (state this wherever the harness is described).** It drives the file against a
MOCK `agent`/`parallel`/`log`/`budget` contract that is not formally specified anywhere in the
repo — checked `references/`, `commands/spec-loop.md`: there is no host-sandbox contract doc. So
it verifies the deterministic control-flow logic, NOT that the file behaves correctly against
the real Workflow host's semantics. The host-integration seam stays unverified. It is
"the deterministic majority is testable now", not "3.1 is fully closed".

## 2. The lost-slice / caught-exception option asymmetry is REAL — behaviourally, not inferred

Same harness, with `parallel` yielding `[null]` (a slice that died outside `runSlice`'s
try/catch — the wave-entry fallback at :913-921):

```
LOST-SLICE PATH
 status  : ESCALATED        id: s1:internal-error       trigger: internal-error
 title   : slice lost
 question: Re-run the wave to retry this slice?
 options : ["Proceed with the recommended default"]
 quality : {"status":"SKIPPED","detail":"slice never ran"}
```

Against the caught-exception record's three options above. Cause: `:919` passes `options: []`,
and `esc()` (:255-261) substitutes a single generic option when the array is empty, whereas
`:895-898` passes three explicit options each naming the CONTROLLER as what applies it.

So `CHANGELOG.md`'s "its three options (retry the slice, skip it, stop the run) are controller
actions, and each option's detail names the controller as what applies it" is true of ONE of the
two records. The deferral list asks only to narrow the prose. **The skeptic lane's sharpest
point:** nothing in the previous run's report defends the asymmetry as a design choice, unlike
the last-writer-wins stage attribution which IS explicitly defended — so widening `:919` to the
same three options may be the better fix at the same cost, and would make the existing prose
true rather than narrowing it. This is a live question for the human, not a controller call.

## 3. The truncation thresholds the report cites are CORRECT — re-measured end to end

Workflow JS produces the record → the real `run_state.render_escalation()` truncates it. Raw
context length and what survives the 400-char render:

| exception message | raw context | rendered | stage attribution | "starting point" caveat |
|---|---|---|---|---|
| `BOOM` (4 chars) | 850 | 400 | **present** | **present** |
| 286 chars | 1132 | 400 | present | **GONE** |
| 500 chars | 1346 | 400 | **GONE** | GONE |

Two things follow. (a) The report's measured thresholds (~286 for the stage attribution, ~200
for the caveat) reproduce. (b) **Even with a 4-character exception message the raw context is
850 characters and less than half of it reaches `escalations.md`.** Truncation is not an edge
case on this record; it is the normal case. Worth stating plainly wherever the record is
described.

This chain is also exactly what INTG-1's fixed test should assert: build the record, render it
through the real `render_escalation()`, assert on the rendered output. No local re-render, no
duplicated limit.

## 4. Structural facts verified for the frozen-snapshot decision

- `plugin_root` is consumed at exactly one place: `:346`, building the `review_package.py`
  command. `quality_gate_cmd` at `:366` and `:404`. Nothing in the pipeline resolves a script
  from the worktree or from the repo working tree.
- Therefore a frozen snapshot outside the repo removes the self-modification loop for the
  orchestration JS, the review packager, and the gate — for real, not approximately.
- The modified Python still executes: the suite runs in the worktree, so `test_quality_gate.py`
  really exercises a modified `quality_gate.py`. That is the one genuine behavioural check on
  this run's own code, and it does not feed back into orchestration.
- `node --check` passes on the never-executed 2.2.1 `slice-wave.workflow.js`.
- `plugins/spec-loop/commands/spec-loop.md` is byte-identical between the repo (2.2.1) and the
  installed 2.2.0 cache (`diff -q`), so the controller contract in force is current and a
  `/plugin update` would buy nothing on that axis.

## 5. INTG-2 ground truth (settled)

`TestTheTriggerEnumAgreesAcrossAllFiveHomes` (`test_slice_wave_contract_crash.py:236`) has two
test methods: one asserts the three Python tuples against each other, one asserts the JS enum
line's values against `run_state.ESCALATION_TRIGGERS`. **Four homes.** `TRIGGER_ENUM_LINE`
(`"trigger: { enum: ["`) is the locator string for the JS enum line, carrying no values — not a
fifth home. `slice_wave_contract_base.py:93` says "five homes" then enumerates four. The
genuinely unpinned homes are the PROSE enumerations. The first explorer to look at this
miscounted it exactly as the code does, which is evidence for the finding.
