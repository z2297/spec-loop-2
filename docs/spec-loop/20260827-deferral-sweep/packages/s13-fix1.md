# Review package: 34dbeed..b7a5d80  (context: -U5)

## Commits
b7a5d80 docs: fix round-2 overclaims in agent_cap_overrides and prompt-count wording

## Files changed
 CHANGELOG.md                                 | 9 +++++----
 plugins/spec-loop/commands/spec-loop.md      | 8 ++++----
 plugins/spec-loop/references/run-state-v2.md | 3 ++-
 3 files changed, 11 insertions(+), 9 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
37,
41
]
],
"plugins/spec-loop/commands/spec-loop.md": [
[
152,
155
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
174,
175
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 96c806b..982035a 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -32,14 +32,15 @@ All notable changes to the spec-loop plugin are documented here. The format is
   re-dispatch the controller hands it to, and it moves no default. An applied raise emits an
   `agent-cap-override` event carrying `{tier, default_cap, effective_cap}`, so the exception is
   auditable in `events.jsonl` rather than inferable from a larger `agents_used`. The record
   itself now offers three controller-named options and its recommended option names the args
   field to write. `budget-exhausted` remains NOT a judgment trigger — its answer is injected
-  into no agent prompt, pinned by source text and by execution across every prompt of a
-  one-task slice run — the eight pipeline roles plan, critique, task, review, gate, fix,
-  re-review and verify; a slice carrying more tasks builds more prompts, repeating the task
-  and re-review roles — and the
+  into no agent prompt, pinned by source text and by execution across the eight pipeline
+  roles the one-task fixture drives — plan, critique, task, review, gate, fix, re-review
+  and verify. A real slice run builds more prompts than these eight: the tier-3 council
+  dispatches several critics, and the fix loop repeats fix and re-review across rounds —
+  and the
   per-stage token floor is untouched, having no args-level lever at all: its resource is the
   wave budget the host supplies. The controller still translates the human's free-text answer
   into the integer it writes; nothing in the loop parses that text. An override the channel
   cannot use is no longer discarded in silence: a value at or below the tier default and one
   that does not coerce to a whole number each emit a `decision` event naming the discarded
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index ddfdc56..d05cd94 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -147,14 +147,14 @@ deadlock is itself an escalation):
    reads it, the structural guard enforces the raised number, and an `agent-cap-override`
    event records the authorisation. An override the wave cannot use — at or below the tier
    default, not reading as a whole number, or keyed to a slice this wave never dispatched —
    raises nothing and says so: it emits a `decision` event naming the discarded value, so a
    mistyped key surfaces at the dispatch that carried it. The value is coerced with `Number()`,
-   so a JSON string reading as a whole number — `"14"` — is accepted and raises the cap. Two
-   rules bind you. The override is single-dispatch:
-   it belongs to the one re-dispatch the human authorised, so drop it from every later
-   dispatch of the run rather than carrying it forward like `answers`. And it only ever
+   so a JSON string reading as a whole number — `"14"` — is read as the integer 14 and judged
+   against the tier default like any other value. Two rules bind you. The override is
+   single-dispatch: it belongs to the one re-dispatch the human authorised, so drop it from
+   every later dispatch of the run rather than carrying it forward like `answers`. And it only ever
    raises — a value at or below the tier default is discarded by the wave, so it is no
    route to a tighter bound either. The TOKEN-FLOOR variant ("token budget exhausted")
    has no such lever: its resource is the wave budget the host supplies, and no args
    field in this contract changes the stage floor.
 
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 7347a76..7cbad95 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -169,11 +169,12 @@ best-effort):
   move. A supplied override that does NOT take effect emits no `agent-cap-override` event: a
   value at or below the tier default, or a value that does not read as a whole number, is
   announced once at slice start as a `decision` event whose summary opens `agent cap
   override`, and override keys matching no slice of the dispatched wave are announced the
   same way on the wave's first slice. The value is coerced with `Number()`, so a JSON string
-  reading as a whole number — `"14"` — is accepted and takes effect like the integer.
+  reading as a whole number — `"14"` — is read as the integer 14 and judged against the tier
+  default like any other value.
   The discard is therefore visible without waiting on a second cap record.
 - **`wave-collected`** payload carries the per-wave aggregates the workflow
   completion notification reports: `{index, agent_count, subagent_tokens,
   duration_ms}` — the honest wave-level token/duration channel while
   per-dispatch stamps are unavailable. Optional, null-honest.
