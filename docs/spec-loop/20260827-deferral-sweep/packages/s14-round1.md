# Review package: 5ecc25de055f813bdc1a004d6cd962804b0d5ad0..2116ec6  (context: -U5)

## Commits
2116ec6 docs(changelog): the coerced override is judged against the tier default

## Files changed
 CHANGELOG.md | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
48,
50
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 982035a..4d351ce 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -43,13 +43,13 @@ All notable changes to the spec-loop plugin are documented here. The format is
   wave budget the host supplies. The controller still translates the human's free-text answer
   into the integer it writes; nothing in the loop parses that text. An override the channel
   cannot use is no longer discarded in silence: a value at or below the tier default and one
   that does not coerce to a whole number each emit a `decision` event naming the discarded
   value, and a key naming no slice of the wave emits one naming the key, so a mistyped lever is
-  visible at the dispatch that carried it rather than only at the next cap record. The coercion
-  is `Number()`, so a JSON string reading as a whole number — `"14"` — becomes `14` and the
-  raise IS applied, emitting `agent-cap-override` and no discard event. Documented in
+  visible at the dispatch that carried it rather than only at the next cap record. The value is
+  coerced with `Number()`, so a JSON string reading as a whole number — `"14"` — is read as the
+  integer 14 and judged against the tier default like any other value. Documented in
   `commands/spec-loop.md` step 7 and `references/run-state-v2.md`.
 - **A behavioural test harness that executes `slice-wave.workflow.js`.** The workflow cannot be
   imported as a module — the host wraps the whole script in an implicit async function, so the
   file legally carries a top-level `return` and a top-level `await`. `slice_wave_harness.mjs`
   loads it through the wrapper that already existed on the Python side,
