# Platform probes — empirically verified Workflow facts

Verified 2026-07-30 on Claude Code with a live 3-agent probe workflow
(`platform-probe`), plus the claude-code-guide docs check. Re-probe after
major Claude Code upgrades — the design notes below say what breaks if a
fact changes.

| Fact | Verified result | Design that depends on it |
|---|---|---|
| `agent(prompt, {schema, model, effort})` | Works; schema-forced structured output returned validated; `model: 'haiku'`, `effort: 'low'` honored | All slice-wave handoffs; model/effort tiering |
| `agentType: 'spec-loop:<agent>'` (plugin-namespaced) | Resolves a plugin agent and composes with `schema` | Every slice-wave `agent()` call uses plugin agent types; if this breaks, prompts are written self-sufficient so a plain agent still works |
| Bash/git inside workflow-spawned agents | Works; agent cwd = the session's repo root | Implementers/verifiers run git + test suites + `quality_gate.py`; worktree paths must be passed absolute since cwd is the primary checkout, NOT the worktree |
| Workflow scripts/journals location | `~/.claude/projects/<munged-cwd>/<session-id>/workflows/scripts/` and `.../subagents/workflows/<run-id>/journal.jsonl` | Session-scoped: cross-session `--resume` must come from `dag.json` + sidecars, never the journal. `journal.jsonl` has one `{"type":"result",...}` line per agent — `run_metrics.py`'s agent-dispatch events are extracted from it by the controller at wave collection |
| Plugin ships workflows | `workflows/` dir + manifest `workflows` field, namespaced `/spec-loop:<meta.name>` (docs-verified, not yet live-probed — first run of the installed plugin should confirm; fallback: invoke with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/slice-wave.workflow.js`) | Controller invocation path |
| Slash command instructing Workflow satisfies opt-in | Docs-verified | /spec-loop can orchestrate without the user typing "ultracode" |
| Hooks inside workflow agents | UNVERIFIED (undocumented) | Guard hook stays defense-in-depth; prompts remain the primary control (v1 doctrine). v1's probe method (instrumented hook + headless run) can settle it later |
| Cached replays vs token budget | UNVERIFIED | Per-wave budgets keep headroom on resume until measured |

Probe agents' cwd being the primary checkout (not a worktree) is load-bearing:
every dispatch prompt that expects work inside a slice worktree must state the
absolute worktree path as its first instruction.

Two more facts verified 2026-07-30 by the E2E dry run:

- **Workflow `args` must be a real JSON object in the tool call.** A
  JSON-encoded string reaches the script as one string; the wave dies
  instantly on `args.slices` (`undefined is not an object`). The failure is
  cheap (0 agents) but total.
- **The integration branch name must not prefix the slice-branch namespace**:
  git rejects creating `spec-loop/<run-id>/<slice-id>` when a branch
  `spec-loop/<run-id>` exists (ref-directory collision). Hence the
  `spec-loop-run/<run-id>` default.

Four more facts from the 2026-09-04 hook probes, on Claude Code 2.1.260
(darwin arm64); the raw payloads are in
`docs/spec-loop/20260904-loop-gate/probe-results.md`:

- **`PreToolUse` fires in a headless (`claude -p`) session and a `.*`
  matcher matches (control, PASS).** Established before either real probe
  was trusted, so a silent non-firing could not be mistaken for a negative
  result. The payload carries **no** `project_dir` key. That does not make
  `cwd` the guard's root signal: `spec_loop_guard.py`'s `evaluate()`
  resolves the project root as `CLAUDE_PROJECT_DIR` from the environment,
  then the payload's `cwd`, then `os.getcwd()` — so the environment
  variable wins and the payload's `cwd` is only the first fallback. The
  `Stop` payload likewise carries no
  `project_dir`.
- **A sync `Stop` hook honours a top-level `{"decision":"block","reason":…}`
  (CONFIRMED).** Evidence, not inference: the harness model was asked to
  reply with one word, the hook blocked its turn end with a `reason`
  instructing a different token, and the session output was that token — so
  the reason text reached the model and the model continued its turn
  instead of ending it. This is the loop-boundary gate's one proven lever.
- **Within a single turn, `stop_hook_active` is `false` on the fire that
  ends the turn and `true` on the fire that ends the block-caused
  continuation, and it resets to `false` again at the start of every NEW
  user turn (CONFIRMED).** Both single-turn fires were logged in one turn of
  probe B; the per-turn reset is established by the THIRD fire of a two-turn
  session (probe B2), where the flag reads `false` at the end of turn 1,
  `true` on the block-caused continuation, and `false` AGAIN at the end of
  turn 2 — reproduced byte-identically on re-run. That third fire closes both
  readings probe B left open, in opposite directions. Not a fence: a gate
  that skips while the flag is true always yields on the immediately
  following fire, so it pushes ONCE PER STALL rather than blocking
  indefinitely. Not a one-shot per session: the gate re-arms on every user
  turn, so it stands at every wave boundary, not only the first. Honouring
  the flag is therefore required, not optional.
- **Whether `AskUserQuestion` emits `PreToolUse` at all is UNRESOLVED.**
  This is an absence of opportunity, not a negative result: the tool is not
  exposed in print mode — the headless model reported it is neither in its
  tool list nor fetchable via ToolSearch — so the `AskUserQuestion` matcher
  never had a call to match. Nothing here licenses the claim that the event
  does or does not fire.

Three questions need an INTERACTIVE session to settle. None is answered
today, and no shipped behaviour may be described as depending on an answer:

1. Does `AskUserQuestion` emit `PreToolUse`? Register a logging-only
   `PreToolUse` hook with matcher `.*` in a settings file, start an
   interactive session, and trigger one `AskUserQuestion` call **and one
   `Bash` call**. The `Bash` call is the control and is not optional:
   without it, a log missing `AskUserQuestion` cannot be told apart from a
   hook that never loaded.
2. Does Ctrl+C route through `Stop`? Same logging hook; interrupt a turn
   and check whether a `Stop` payload is written. Untested.
3. Does `Stop` fire at the end of a `Task` subagent's turn? Same logging
   hook; run a Task subagent and look for a `Stop` payload carrying the
   subagent's turn. Untested — and `SubagentStop` being a distinct,
   unregistered event is not evidence either way.
