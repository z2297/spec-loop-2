# Platform probe results — 2026-09-04, Claude Code 2.1.260 (darwin arm64)

Run by the controller at Phase 0, before slice planning, so the plan does not rest on an
assumption about hook behaviour. Harness: `claude -p --model haiku --settings <file>` with
logging hooks writing each payload to a file. Harness validity was established by a control
case before either probe was trusted.

## Control — PreToolUse fires in a headless session and `.*` matches (PASS)

Registered two PreToolUse entries, matcher `AskUserQuestion` and matcher `.*`, both logging.
Prompted the model to run one Bash command. Result: the `.*` entry fired.

```json
{"label": "MATCH_ANY", "hook_event_name": "PreToolUse", "tool_name": "Bash",
 "keys": ["cwd", "hook_event_name", "permission_mode", "prompt_id", "session_id",
          "tool_input", "tool_name", "tool_use_id", "transcript_path"]}
```

PreToolUse payload carries **no** `project_dir` key, so `cwd` is the only root signal the
PAYLOAD offers. That is not the same as saying the guard relies on it: `spec_loop_guard.py:297`
resolves `os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()`, so the
environment variable wins and payload `cwd` is a fallback.

**Correction, 2026-09-04.** An earlier revision of this file ended the sentence "…must be
resolved from `cwd`, which is what `spec_loop_guard.py` already does", conflating the payload's
only root key with the guard's actual precedence. Slice s4 copied that claim verbatim into the
shipped `references/platform-probes.md`, where its reviewer caught it against the real line. The
error is the controller's, not the slice's, and it is exactly the "a wrong shared convention
artifact launders defects downstream" pattern this run cited at intake — recorded here rather
than quietly overwritten, because the propagation path is the lesson.

## Probe B — a sync `Stop` hook honours top-level `{"decision":"block","reason":…}` (CONFIRMED)

Registered a `Stop` hook (no `asyncRewake`) that, on its first fire, printed
`{"decision":"block","reason":"PROBE_STOP_BLOCK: reply with exactly the token
BLOCKED_THEN_CONTINUED and nothing else."}` and, on any later fire or when `stop_hook_active`
was true, printed nothing.

Prompt: "Reply with exactly the word HI and nothing else."
Session output: `BLOCKED_THEN_CONTINUED`

So the block took effect, the `reason` text reached the model, and the model continued its turn
instead of ending it. Two fires were logged:

```json
{"label": "STOP", "hook_event_name": "Stop", "stop_hook_active": false, "already_blocked_once": false}
{"label": "STOP", "hook_event_name": "Stop", "stop_hook_active": true,  "already_blocked_once": true}
```

Two facts the gate design depends on, both established here:

- `stop_hook_active` is **false** on the fire that ends a normal turn and **true** on the fire
  that ends the continuation the block caused. A gate that does not skip on
  `stop_hook_active` would re-block its own continuation, so honouring it is required, not
  optional — and it makes the gate a ONE-SHOT push per stall, never a fence.
- `Stop` payload keys: `background_tasks`, `cwd`, `hook_event_name`, `last_assistant_message`,
  `permission_mode`, `prompt_id`, `session_crons`, `session_id`, `stop_hook_active`,
  `transcript_path`. Again no `project_dir` key, so `cwd` is the only root signal the PAYLOAD
  offers — which is not the same as the guard relying on it. `spec_loop_guard.py`'s
  `evaluate()` prefers the `CLAUDE_PROJECT_DIR` environment variable and falls back to payload
  `cwd`, then `os.getcwd()`. Stated with the precedence because the bare form of this sentence
  is what became a false claim in a shipped reference; see the correction note above.

## Probe B2 — does `stop_hook_active` reset on a NEW user turn? (CONFIRMED)

Probe B left a real ambiguity that Probe B's own data cannot settle: both its fires were in ONE
turn, so `true` on the second fire is equally consistent with "resets each turn" and with "latches
for the session". Those two readings have opposite consequences — if it latched, the gate would
be a one-shot per SESSION and would protect only the first wave boundary, which is precisely the
failure this run exists to fix, and nobody would notice.

Harness: the same `Stop` hook, blocking on any fire where the flag is false (capped at three
blocks), driven with `--input-format stream-json` so ONE session receives TWO user turns.

Assistant output, in order: `ONE`, `B1`, `TWO`, `B2` — the model answered turn 1, was blocked and
appended `B1`, answered turn 2, was blocked again and appended `B2`. Fires:

```json
{"fire": true, "stop_hook_active": false, "blocks_so_far": 0, "last_msg": "ONE"}
{"fire": true, "stop_hook_active": true,  "blocks_so_far": 1, "last_msg": "B1"}
{"fire": true, "stop_hook_active": false, "blocks_so_far": 1, "last_msg": "TWO"}
{"fire": true, "stop_hook_active": true,  "blocks_so_far": 2, "last_msg": "B2"}
```

The third fire is the whole result: `stop_hook_active` is **false** again at the end of turn 2,
after having been `true` at the end of turn 1's continuation. It resets per user turn. Re-run
2026-09-04 and reproduced byte-identically, and the second run also showed the block reaching the
model as `Stop hook feedback: <reason>`.

So the gate **re-arms every turn**: one push per stop attempt, never a fence (it always yields on
the immediately following fire), and never a one-shot per session. Both readings Probe B left open
are now closed, in opposite directions: guardian's worry that the gate might protect only the
first boundary is dead, and plan-critic's blast-radius flag is confirmed, which is what made the
controller-session narrowing necessary rather than merely tidy.

**Recorded late — 2026-09-04, and that is itself a finding.** This probe was run before slice s1
was dispatched, but its result was never written into this file. Slices s4 and s7 then read this
file as the run's ground truth, correctly found no evidence for the per-turn reset, and wrote
`Untested` into the shipped `references/platform-probes.md` — while the run's `shared_constraints`
asserted the same fact as proven. s7's council met that contradiction, could not resolve it from
the evidence, and chose the conservative register, which was the right call on what it could see.
The defect is the controller's: an evidence file that is missing a probe is as much a laundering
vector as one that states a probe wrongly, and this run produced both.

## Probe A — does PreToolUse fire for `AskUserQuestion`? (UNRESOLVED)

Not answerable with this harness. `AskUserQuestion` is **not exposed in print mode**: asked to
call it, the headless model replied "I don't have access to an 'AskUserQuestion' tool. It's not
listed in my available tools, and it's not among the deferred tools that can be fetched via
ToolSearch." The matcher-`AskUserQuestion` entry therefore never had a call to match, which is
an absence of opportunity, not an absence of firing — it must not be read as a negative result.

Escalating the probe was also ruled out: the CLI at
`~/.local/share/claude/versions/2.1.260` is a compiled Mach-O binary, so static inspection would
yield string proximity rather than control flow, and `--plugin-dir` does not change print mode's
tool list.

**Consequence for the plan.** `Stop` (probe B) is the load-bearing gate and the only one whose
firing is proven; it catches the failure this run exists to fix — a turn ending while slices are
runnable. The `AskUserQuestion` gate must be built and registered, but every artifact that
describes it has to state that its firing is unverified on 2.1.260, and the plan must not claim
the run is protected against a spurious mid-loop question. Verifying it requires an INTERACTIVE
session, which is the documented follow-up procedure:

1. Register a logging-only `PreToolUse` hook with matcher `.*` in a settings file.
2. Start an interactive session, trigger one `AskUserQuestion` and one `Bash` call.
3. If the log shows `Bash` but not `AskUserQuestion`, the tool does not emit `PreToolUse` and
   Gate A is dead code to be removed. If it shows both, Gate A is verified.

Step 3's control (`Bash`) is what separates "the tool is exempt" from "the hook never loaded";
without it the observation is worthless.
