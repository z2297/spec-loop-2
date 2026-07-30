---
description: "View or update the spec-loop 2 code-quality gate — thresholds (cyclomatic complexity, method length, CRAP, …), Tier-3 review surfaces, the reviewer-model knob, and custom gates, persisted globally across all runs"
argument-hint: "(no args — interactive)"
allowed-tools: ["Bash", "Read", "Write", "Edit", "AskUserQuestion"]
---

# Spec-Loop Quality Gate — setup & update

Configure the objective code-quality bar every `/spec-loop` slice must clear in its
review∥gate stage, before verification and merge. The config is global
(`~/.claude/spec-loop-2/quality-gate.json`) and this command is the only thing that
prompts for it — the loop never re-asks once the file exists. Runtime behavior
(measurement by the bundled `scripts/quality_gate.py`, violations entering the wave's
bounded fix loop as P1 findings) belongs to the wave workflow; this command only edits
the config and never measures code or triggers slice work.

## Steps

1. **Locate / read current config.** If `~/.claude/spec-loop-2/quality-gate.json`
   exists, show its current values (thresholds, `measurement`, `enabled`, `custom_gates`,
   `tier3_surfaces`, `models`) and stop here unless the user wants changes. If not, this
   is first-time setup — and if `~/.claude/spec-loop/quality-gate.json` (spec-loop v1)
   exists, offer **import** as the first option of the step-2 question:
   - **Import from v1** — read the v1 file and carry `enabled`, `measurement`,
     `thresholds`, and `custom_gates` over verbatim; drop `refactor_attempts` (see the
     migration note in step 5) and fill the v2-only keys with the defaults below. Never
     move, edit, or delete the v1 file: both generations can be installed at once and v1
     keeps reading its own path.
2. **Choose a quality level** via `AskUserQuestion` (single select), presenting the
   concrete numbers so the user validates the actual bar:
   - **Recommended (default)** — `cyclomatic 10, cognitive 15, method_lines 50,
     parameter_count 4, nesting_depth 3, class_lines 300, crap 30`
   - **Strict** — `cyclomatic 8, cognitive 12, method_lines 40, parameter_count 3,
     nesting_depth 2, class_lines 250, crap 20`
   - **Lenient** — `cyclomatic 15, cognitive 20, method_lines 75, parameter_count 5,
     nesting_depth 4, class_lines 400, crap 40`
   - **Customize** — walk the thresholds in batches (≤4 questions per round),
     recommended value first, "Other" for exact numbers; also ask `enabled` (default
     true). Do not offer a fix-round or `refactor_attempts` question: v2's wave workflow
     caps fix rounds itself (step 5).
3. **The two v2 knobs** (one batched round, recommended value first):
   - **`tier3_surfaces`** — globs whose presence in a slice's diff deterministically
     promotes that slice's *review* tier to 3 (two-reviewer panel, session model on the
     correctness lane), regardless of the tier the controller assigned. Default
     `["**/auth/**", "**/migrations/**", "**/*.sql", "**/security/**"]`; offer the
     default, "add to it", or a replacement list. This is a review-depth control, not a
     threshold — it never changes what the gate measures.
   - **`models.reviewer`** — `"sonnet"` (default: reviews at risk tier 1–2 run on
     Sonnet) or `"inherit"` (promote them to the session model — stronger reviews, more
     cost). Tier 3 always runs the panel with the session model, so this knob only
     moves the default tiers.
4. **Custom gates.** Offer **metric gates only** — `{ "name", "metric", "threshold" }`,
   evaluated by `quality_gate.py` against the measured values, and genuinely blocking.
   **v2.0.0 does not execute command-form gates** (`{ "name", "command", "pass_when" }`):
   the schema still accepts them and the script lists them under `skipped` as
   command-form, but nothing runs them — executing them is a roadmap item. Never offer to
   create one in the Customize flow; if the user asks for one directly, say plainly that
   it will be recorded and not enforced before writing it.
5. **Write the file** (`mkdir -p ~/.claude/spec-loop-2` first). Schema:
   ```json
   {
     "version": 2,
     "enabled": true,
     "measurement": "hybrid",
     "thresholds": {
       "cyclomatic_complexity": 10,
       "cognitive_complexity": 15,
       "method_lines": 50,
       "parameter_count": 4,
       "nesting_depth": 3,
       "class_lines": 300,
       "crap_score": 30
     },
     "tier3_surfaces": ["**/auth/**", "**/migrations/**", "**/*.sql", "**/security/**"],
     "models": { "reviewer": "sonnet" },
     "custom_gates": []
   }
   ```
   `measurement: "hybrid"` = real analyzer when installed, else clearly-labelled
   heuristics; `crap_score` is skipped with a note when no coverage report exists.
   `quality_gate.py` measures against `enabled`, `thresholds`, and `custom_gates`, and
   passes every other key (`tier3_surfaces`, `models`, `measurement`, …) straight through
   to `--print-config`, which is how the controller reads them — one file, one door.

   **Migration from v1:** `refactor_attempts` is gone. v1 used it to bound the refactor
   loop; v2's wave workflow caps a slice at 2 fix rounds and then escalates, so the key
   would have been decoration. An imported v1 config may still carry it — harmless, and
   dropping it on write is correct. Say so when importing, so nobody expects a raised
   number to buy more rounds.
6. **Confirm.** Print the absolute path and the final values; this applies to all
   future runs until this command is run again.

## Per-repo overlay — `.spec-loop/quality-gate.json`

A repo may commit `.spec-loop/quality-gate.json` next to its source; it needs only the
keys it changes. The merge is `quality_gate.py`'s own, not something a caller reimplements:

```
python3 quality_gate.py --config ~/.claude/spec-loop-2/quality-gate.json \
                        --overlay .spec-loop/quality-gate.json --print-config
```

`--overlay` deep-merges over `--config` — `thresholds` keys override, `tier3_surfaces`
**unions** (an overlay extends the surface list, it can never remove a surface),
`custom_gates` concatenate, every other key overrides — and the provenance is always
reported: `loaded+overlay`, or `defaults+overlay` when no global config exists, in the
measurement report's `config` field and in `--print-config`'s `source` field. So a reader
can always tell an overlay was in play. `--print-config` prints the effective merged
config as JSON and exits 0: that is the single door through which the controller
reads `tier3_surfaces` and `models` before building the wave args, and the same
`--config <global> --overlay <repo>` pair rides in `quality_gate_cmd` so measurement and
review-depth promotion come from one resolved configuration.

The overlay's intent is **tighten-only**: lower a threshold, extend `tier3_surfaces`, add
a metric gate. Nothing in the merge enforces that direction, so an overlay that loosens
the global bar is a review finding about the overlay, not a sanctioned configuration — a
repo cannot opt its way out of the bar its own owner set. Both files predate the run (the
guard denies writes to either while one is active), so a loosening is always a deliberate,
committed, reviewable human choice. This command edits the global config only; write the
overlay by hand and commit it with the repo.

## The mid-run guard

While a run is `.active`, `spec_loop_guard.py` denies Write/Edit to **both** paths —
the global config and the repo overlay — and denies shell writes that mention
`quality-gate.json`. Weakening a threshold to force a failing slice past the gate is
the exact failure it exists to prevent. Change the config after the run, through this
command; never delete a marker to dodge the denial.
