# Review package: 35409a84ff41b3fe139b62182a36e01cc08c8901..7fe5a49  (context: -U5)

## Commits
7fe5a49 docs: name the real discard condition for agent_cap_overrides in run-state-v2
4f2c24a docs: name the real discard condition for agent_cap_overrides in the controller contract

## Files changed
 plugins/spec-loop/commands/spec-loop.md      |  8 +++++---
 plugins/spec-loop/references/run-state-v2.md | 10 ++++++----
 2 files changed, 11 insertions(+), 7 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/commands/spec-loop.md": [
[
149,
153
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
170,
175
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/commands/spec-loop.md b/plugins/spec-loop/commands/spec-loop.md
index 7ec8520..ddfdc56 100644
--- a/plugins/spec-loop/commands/spec-loop.md
+++ b/plugins/spec-loop/commands/spec-loop.md
@@ -144,13 +144,15 @@ deadlock is itself an escalation):
    AGENT-CAP variant of that record ("agent cap reached (N)") has a lever — after the
    human authorises a raise, hand the very next dispatch `agent_cap_overrides:
    {"<slice-id>": <integer>}` alongside the usual `answers` map. `agentCap` in the wave
    reads it, the structural guard enforces the raised number, and an `agent-cap-override`
    event records the authorisation. An override the wave cannot use — at or below the tier
-   default, non-integer, or keyed to a slice this wave never dispatched — raises nothing and
-   says so: it emits a `decision` event naming the discarded value, so a mistyped key surfaces
-   at the dispatch that carried it. Two rules bind you. The override is single-dispatch:
+   default, not reading as a whole number, or keyed to a slice this wave never dispatched —
+   raises nothing and says so: it emits a `decision` event naming the discarded value, so a
+   mistyped key surfaces at the dispatch that carried it. The value is coerced with `Number()`,
+   so a JSON string reading as a whole number — `"14"` — is accepted and raises the cap. Two
+   rules bind you. The override is single-dispatch:
    it belongs to the one re-dispatch the human authorised, so drop it from every later
    dispatch of the run rather than carrying it forward like `answers`. And it only ever
    raises — a value at or below the tier default is discarded by the wave, so it is no
    route to a tighter bound either. The TOKEN-FLOOR variant ("token budget exhausted")
    has no such lever: its resource is the wave budget the host supplies, and no args
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 2a7fcf1..7347a76 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -165,14 +165,16 @@ best-effort):
   than inferable from a larger `agents_used`. The raise arrives as the wave arg
   `agent_cap_overrides` (`{"<slice-id>": <integer>}`), belongs to the single dispatch the
   controller hands it to, and can only raise: a value at or below the tier default is
   discarded. `tier` is the review tier at slice start, which a later tier promotion can
   move. A supplied override that does NOT take effect emits no `agent-cap-override` event: a
-  value at or below the tier default, or a non-integer value, is announced once at slice
-  start as a `decision` event whose summary opens `agent cap override`, and override keys
-  matching no slice of the dispatched wave are announced the same way on the wave's first
-  slice. The discard is therefore visible without waiting on a second cap record.
+  value at or below the tier default, or a value that does not read as a whole number, is
+  announced once at slice start as a `decision` event whose summary opens `agent cap
+  override`, and override keys matching no slice of the dispatched wave are announced the
+  same way on the wave's first slice. The value is coerced with `Number()`, so a JSON string
+  reading as a whole number — `"14"` — is accepted and takes effect like the integer.
+  The discard is therefore visible without waiting on a second cap record.
 - **`wave-collected`** payload carries the per-wave aggregates the workflow
   completion notification reports: `{index, agent_count, subagent_tokens,
   duration_ms}` — the honest wave-level token/duration channel while
   per-dispatch stamps are unavailable. Optional, null-honest.
 - **`council-verdict`** payload carries `safety: bool` — whether the verdict
