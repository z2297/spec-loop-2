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
