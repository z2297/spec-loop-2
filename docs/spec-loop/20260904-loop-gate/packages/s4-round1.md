# Review package: b4141b6dbc2443c08312717ffa69d7012d578ab0..dae2404  (context: -U5)

## Commits
dae2404 docs(changelog): extend the Unreleased entry with the Stop gate, marker hygiene and the docs corrections
36cd4ce docs(run-state): truthful marker heading, repo-scoped enforcement, paused residual risk
9801b2e docs(readme): describe the guard's real registrations and the loop-boundary block
890aee4 docs(probes): record the 2026-09-04 hook probe results and the interactive follow-ups

## Files changed
 CHANGELOG.md                                    | 44 +++++++++++++++++++++++
 plugins/spec-loop/README.md                     | 19 ++++++----
 plugins/spec-loop/references/platform-probes.md | 48 +++++++++++++++++++++++++
 plugins/spec-loop/references/run-state-v2.md    | 33 ++++++++++++-----
 4 files changed, 130 insertions(+), 14 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
25,
68
]
],
"plugins/spec-loop/README.md": [
[
114,
116
],
[
138,
147
]
],
"plugins/spec-loop/references/platform-probes.md": [
[
33,
80
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
270,
270
],
[
283,
289
],
[
294,
302
],
[
309,
316
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index ef2a962..08a45b1 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -20,10 +20,54 @@ All notable changes to the spec-loop plugin are documented here. The format is
   is written down with its stale-marker remediation. `skills/escalation-gate/SKILL.md` adds a
   fourth "Not triggers" entry for the RUNNABLE boundary only — a reported deadlock stays a
   genuine escalation — and `scripts/test_doctrine_loop_boundary.py` pins every one of those
   sentences, counting the list's bullets on disk rather than trusting the number in the prose.
   This is prose and a pin; the enforcing gate is separate.
+- **The loop-boundary gate itself: a `Stop` hook that blocks the controller's turn from ending
+  while its run still has runnable slices and no open escalation — the run's one proven
+  LEVER.** `scripts/spec_loop_guard.py` gains `check_stop()` plus event dispatch in
+  `evaluate()`/`main()`, and `hooks/hooks.json` registers the `Stop` event; a `Stop` block is a
+  different wire shape from a `PreToolUse` denial (top-level `decision`/`reason`, not a
+  `permissionDecision`). The gate is narrowed to the session recorded in
+  `.controller-session`, skipped when `stop_hook_active` is true — probed on Claude Code
+  2.1.260 and CONFIRMED within a single turn to be `false` on the turn-ending fire and `true`
+  on the block-caused continuation's fire, which makes the gate one push per stall rather than
+  a fence — relaxed by a `.paused` marker that relaxes THIS gate alone, and fails open PER RUN
+  (not globally) when a `.controller-session` marker cannot be decoded. The probe evidence and
+  its limits are recorded in `references/platform-probes.md`, together with the four questions
+  that remain UNTESTED there: whether `AskUserQuestion` emits `PreToolUse` at all, whether
+  `stop_hook_active` resets at the start of a new user turn (so whether the gate re-arms per
+  turn or is one-shot per session is NOT established), whether Ctrl+C routes through `Stop`,
+  and whether `Stop` fires for `Task` subagents. A PreToolUse gate on `AskUserQuestion` was
+  considered and DROPPED by human decision; no part of it was built and nothing in this release
+  guards that path.
+
+### Changed
+- **Run-state markers are now untracked, ignored and pinned, and the contract that describes
+  them says what it actually enforces and where.** Eight previously committed markers across
+  four runs are removed from the index (index-only, leaving the files on disk for any run still
+  reading them), `.gitignore` gains one bare unanchored entry per marker name for all five
+  (`.active`, `.publish-choice`, `.done`, `.paused`, `.controller-session`), and
+  `scripts/test_doctrine_marker_hygiene.py` fails if one re-enters the index.
+  `references/run-state-v2.md` documents the two markers v2 adds, scopes that enforcement claim
+  to this repository — an installing repo has neither the ignore entries nor the pin — declines
+  to claim the `.controller-session` narrowing separates a `Task` subagent from its parent (it
+  inherits the same session id), and records as an ACCEPTED residual risk that `.paused`
+  disables the loop-boundary gate with zero observable trace, since a silent hook cannot
+  announce that it is paused. `README.md` stops describing `spec_loop_guard.py` as a
+  PreToolUse-only hook and adds the loop-boundary block to its exhaustive blocked-actions list.
+- **The escalation-ordering rule now states both halves**, in `commands/spec-loop.md`: the
+  mandatory `escalation-opened` event before any controller-originated `AskUserQuestion`, and
+  the write-back once the human answers. The wave-raised exclusion is scoped to the append half
+  only, so a wave-raised escalation still gets its answer recorded.
+
+### Known limitation
+- **Nothing this release added to `hooks/hooks.json` protected the run that produced it.** The
+  installed plugin was 2.2.0 while this repository is 2.3.0, so the `Stop` registration shipped
+  here was never loaded during the run, and no test in the suite would have failed if the gate
+  had been inert — the suite pins the script's behaviour, not the running session's hooks. The
+  gate's effect on a live controller session is therefore unobserved as of this entry.
 
 ## [2.3.0] - 2026-08-29
 ### Added
 - **The wave now halts a slice at PLAN time when its plan declares a rewrite of existing code
   larger than the run's configured ceiling — the run's one new LEVER.**
diff --git a/plugins/spec-loop/README.md b/plugins/spec-loop/README.md
index cabfaf6..15d0b20 100644
--- a/plugins/spec-loop/README.md
+++ b/plugins/spec-loop/README.md
@@ -109,12 +109,13 @@ arrive as ONE question round per wave boundary, recommended default first.
 
 ## Quality gate
 
 `scripts/quality_gate.py` measures the slice diff (cyclomatic/cognitive
 complexity, method/class length, parameters, nesting, CRAP with coverage) —
-deterministic, script-first, agents cannot weaken it: a PreToolUse guard
-denies writes to the config while a run is active. Global config
+deterministic, script-first, agents cannot weaken it: the guard hook's
+PreToolUse Write/Edit branch denies writes to the config while a run is
+active. Global config
 `~/.claude/spec-loop-2/quality-gate.json` (first run offers presets or import
 from v1); a committed per-repo overlay `.spec-loop/quality-gate.json`
 deep-merges over it and hosts `tier3_surfaces`. Gate violations join review
 findings in the same fix loop as behavior-preserving refactors.
 
@@ -132,14 +133,20 @@ subfolder.
 
 Everything durable lives under `docs/spec-loop/<run-id>/` —
 `dag.json` (structure + recorded waves), per-slice sidecars, `events.jsonl`
 (the machine channel `run_metrics.py` reads), rendered prose logs, and the
 committed `runbook.md`. Contract: `references/run-state-v2.md`. While a run's
-`.active` marker exists, `scripts/spec_loop_guard.py` (PreToolUse hook)
-blocks pushes, broad staging (`git add -A`), commits/merges on
-`main`/`master`, and quality-gate config edits. Markers, not vibes: the run
-ends when the human's publish choice is recorded.
+`.active` marker exists, `scripts/spec_loop_guard.py` — registered on
+`PreToolUse` for `Bash` and `Write|Edit|MultiEdit`, and on `Stop` — blocks,
+in ANY session, pushes, broad staging (`git add -A`), commits/merges on
+`main`/`master` and quality-gate config edits. One further block applies
+only in the session recorded in `.controller-session`: that session may not
+end its turn at a wave boundary while the run still has runnable slices and
+no open escalation. That loop-boundary block is additionally skipped when
+`stop_hook_active` is true, so it pushes once per stall rather than fencing,
+and is relaxed — alone among the blocks — by a `.paused` marker. Markers,
+not vibes: the run ends when the human's publish choice is recorded.
 Work the council judged out of scope and asked not to be built is logged as its own
 `deferred` event and rendered into `decisions-log.md`; a malformed scope record fails the
 sidecar closed rather than reading as clean.
 
 ## Components
diff --git a/plugins/spec-loop/references/platform-probes.md b/plugins/spec-loop/references/platform-probes.md
index 20bfc40..8956576 100644
--- a/plugins/spec-loop/references/platform-probes.md
+++ b/plugins/spec-loop/references/platform-probes.md
@@ -28,5 +28,53 @@ Two more facts verified 2026-07-30 by the E2E dry run:
   cheap (0 agents) but total.
 - **The integration branch name must not prefix the slice-branch namespace**:
   git rejects creating `spec-loop/<run-id>/<slice-id>` when a branch
   `spec-loop/<run-id>` exists (ref-directory collision). Hence the
   `spec-loop-run/<run-id>` default.
+
+Four more facts from the 2026-09-04 hook probes, on Claude Code 2.1.260 (darwin
+arm64); the raw payloads are in `docs/spec-loop/20260904-loop-gate/probe-results.md`:
+
+- **`PreToolUse` fires in a headless (`claude -p`) session and a `.*` matcher
+  matches (control, PASS).** Established before either real probe was trusted, so
+  a silent non-firing could not be mistaken for a negative result. The payload
+  carries **no** `project_dir` key — `cwd` is the only root signal, which is what
+  `spec_loop_guard.py` already relies on. The `Stop` payload likewise carries no
+  `project_dir`.
+- **A sync `Stop` hook honours a top-level `{"decision":"block","reason":…}`
+  (CONFIRMED).** Evidence, not inference: the harness model was asked to reply
+  with one word, the hook blocked its turn end with a `reason` instructing a
+  different token, and the session output was that token — so the reason text
+  reached the model and the model continued its turn instead of ending it. This
+  is the loop-boundary gate's one proven lever.
+- **Within a single turn, `stop_hook_active` is `false` on the fire that ends the
+  turn and `true` on the fire that ends the block-caused continuation
+  (CONFIRMED).** Both fires were logged in one turn of the probe session. This is
+  why a gate that skips when `stop_hook_active` is true pushes ONCE PER STALL
+  rather than fencing: it cannot re-block the continuation it just caused.
+  Honouring the flag is therefore required, not optional. What this evidence does
+  **not** cover: whether the flag starts at `false` again on a NEW user turn, i.e.
+  whether the gate re-arms per turn or is one-shot for the whole session. No
+  second user turn was observed; that question is untested and listed below.
+- **Whether `AskUserQuestion` emits `PreToolUse` at all is UNRESOLVED.** This is an
+  absence of opportunity, not a negative result: the tool is not exposed in print
+  mode — the headless model reported it is neither in its tool list nor fetchable
+  via ToolSearch — so the `AskUserQuestion` matcher never had a call to match.
+  Nothing here licenses the claim that the event does or does not fire.
+
+Four questions need an INTERACTIVE session to settle. None is answered today, and
+no shipped behaviour may be described as depending on an answer:
+
+1. Does `AskUserQuestion` emit `PreToolUse`? Register a logging-only `PreToolUse`
+   hook with matcher `.*` in a settings file, start an interactive session, and
+   trigger one `AskUserQuestion` call **and one `Bash` call**. The `Bash` call is
+   the control and is not optional: without it, a log missing `AskUserQuestion`
+   cannot be told apart from a hook that never loaded.
+2. Does `stop_hook_active` reset to `false` at the start of a new user turn? Same
+   logging hook plus a `Stop` hook that blocks once; take two user turns in one
+   session and compare the flag on the first fire of each. Untested.
+3. Does Ctrl+C route through `Stop`? Same logging hook; interrupt a turn and check
+   whether a `Stop` payload is written. Untested.
+4. Does `Stop` fire at the end of a `Task` subagent's turn? Same logging hook; run
+   a Task subagent and look for a `Stop` payload carrying the subagent's turn.
+   Untested — and `SubagentStop` being a distinct, unregistered event is not
+   evidence either way.
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 0019058..cc69f9f 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -265,11 +265,11 @@ no pinned machine grammar in v2.
 | `review-<slice-id>-round<N>.md` | pr-reviewer agent | findings prose (the structured findings live in the workflow return) |
 | `slice-<id>-report.md` | controller | short human summary rendered from the sidecar |
 | `runbook.md` | runbook-writer agent | end-of-run synthesis, committed |
 | `metrics.json` | `run_metrics.py --write` | atomic write |
 
-## Markers — guard-hook contract (unchanged from v1)
+## Markers — guard-hook contract (v1's three, plus two added in v2)
 
 - `.active` — created at Phase 1, recreated on resume. While present,
   `spec_loop_guard.py` blocks pushes, broad staging, main-branch
   commits/merges, and quality-gate config writes.
 - `.publish-choice` — written the instant the human answers the publish
@@ -278,27 +278,44 @@ no pinned machine grammar in v2.
 - `.paused` — present only while the human has deliberately suspended the
   loop-boundary gate. It relaxes that one gate and nothing else; every
   `.active` restriction above still applies.
 - `.controller-session` — identifies the controller's own session so the
   loop-boundary gate applies to it and not to other sessions. Per-session
-  state, meaningful only inside the machine that wrote it.
+  state, meaningful only inside the machine that wrote it. It discriminates
+  across SESSIONS and nothing finer: a `Task` subagent inherits its parent's
+  `CLAUDE_CODE_SESSION_ID`, so the marker would MATCH at a subagent's turn
+  end and the gate would tell an implementer to continue Phase 2 step 1.
+  Whether `Stop` fires at a subagent's turn end is untested, and
+  `SubagentStop` being a distinct, unregistered event is not evidence
+  either way. See `references/platform-probes.md`.
 
 None of these markers is ever committed. They are per-checkout state: the
 hooks fire on a marker's PRESENCE, so a committed `.active` would deny pushes
 and main-branch commits on every clone and in every fresh worktree, including
-sessions with no run at all. `.gitignore` enforces this with one bare,
-unanchored entry per marker name, and `test_doctrine_marker_hygiene.py` fails
-if one re-enters the index. Markers did get committed twice before that pin
-existed; the correction is an index-only removal (`git rm --cached`) that
-leaves the files on disk for any run still reading them — never a history
-rewrite, and never a plain delete.
+sessions with no run at all. In the spec-loop repository itself, `.gitignore`
+enforces this with one bare, unanchored entry per marker name and
+`test_doctrine_marker_hygiene.py` fails if one re-enters the index. Neither
+exists in a repo the plugin is merely installed into: there, a `.paused` or
+`.active` is fully committable and nothing will stop it, so adding those five
+ignore entries is the installing repo's job. Markers did get committed twice
+in this repository before that pin existed; the correction is an
+index-only removal (`git rm --cached`) that leaves the files on disk for any
+run still reading them — never a history rewrite, and never a plain delete.
 
 A hook denial means the run has not earned that operation yet — never delete
 a marker to dodge one. A stale marker is remediated by resuming the run or
 clearing the marker, in that order; that applies to a stale `.paused` exactly
 as it does to a stale `.active`.
 
+Accepted residual risk: `.paused` disables the loop-boundary gate with ZERO
+observable trace. A `Stop` hook can only block or stay silent, so a paused
+gate never fires and therefore never gets the chance to explain that it is
+paused. A `.paused` left behind after the reason for it passed is a
+permanent, silent loss of the loop-boundary gate for that run — detectable
+only by a human who remembers the marker exists. This is accepted, not
+mitigated.
+
 ## Worktrees & branches
 
 - Worktree: `.worktrees/spec-loop/<run-id>/<slice-id>` (gitignored).
 - Branch: `spec-loop/<run-id>/<slice-id>`, cut from the current tip of
   `base_ref` by `worktrees.py prepare` before the wave is dispatched.
