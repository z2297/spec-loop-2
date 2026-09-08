# Review package: df124fa..6f1b874  (context: -U5)

## Commits
6f1b874 docs(spec-loop): scope the per-turn reset bullet to its evidence
c5cbd5a docs(spec-loop): README names both guard branches by symbol
f43b45c docs(spec-loop): cite the guard root precedence by symbol, not line
5c5d9be docs(spec-loop): promote stop_hook_active per-turn reset to CONFIRMED

## Files changed
 plugins/spec-loop/README.md                        |   6 +-
 plugins/spec-loop/references/platform-probes.md    |  42 ++++----
 .../scripts/test_doctrine_platform_probes.py       | 110 +++++++++++++++++----
 3 files changed, 116 insertions(+), 42 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/README.md": [
[
116,
118
]
],
"plugins/spec-loop/references/platform-probes.md": [
[
42,
46
],
[
56,
70
],
[
78,
78
],
[
87,
87
],
[
89,
89
]
],
"plugins/spec-loop/scripts/test_doctrine_platform_probes.py": [
[
11,
19
],
[
43,
84
],
[
114,
115
],
[
120,
120
],
[
122,
122
],
[
126,
130
],
[
142,
161
],
[
168,
172
],
[
182,
186
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/README.md b/plugins/spec-loop/README.md
index a9005ed..e5a5443 100644
--- a/plugins/spec-loop/README.md
+++ b/plugins/spec-loop/README.md
@@ -111,13 +111,13 @@ arrive as ONE question round per wave boundary, recommended default first.
 
 `scripts/quality_gate.py` measures the slice diff (cyclomatic/cognitive
 complexity, method/class length, parameters, nesting, CRAP with coverage) —
 deterministic, script-first, agents cannot weaken it: while a run is
 active the guard hook denies both a `Write`/`Edit`/`MultiEdit` targeting
-the config (`spec_loop_guard.py:235-252`) and a shell-side write to it —
-redirect, `tee`, `mv`, `cp` or `sed -i` (`spec_loop_guard.py:64-68`,
-`193-199`). Global config
+the config (`check_write` in `spec_loop_guard.py`) and a shell-side write
+to it — redirect, `tee`, `mv`, `cp` or `sed -i` (the
+`QUALITY_GATE_WRITE` pattern, enforced in `check_bash`). Global config
 `~/.claude/spec-loop-2/quality-gate.json` (first run offers presets or import
 from v1); a committed per-repo overlay `.spec-loop/quality-gate.json`
 deep-merges over it and hosts `tier3_surfaces`. Gate violations join review
 findings in the same fix loop as behavior-preserving refactors.
 
diff --git a/plugins/spec-loop/references/platform-probes.md b/plugins/spec-loop/references/platform-probes.md
index db74380..5244dea 100644
--- a/plugins/spec-loop/references/platform-probes.md
+++ b/plugins/spec-loop/references/platform-probes.md
@@ -37,52 +37,56 @@ Four more facts from the 2026-09-04 hook probes, on Claude Code 2.1.260
 
 - **`PreToolUse` fires in a headless (`claude -p`) session and a `.*`
   matcher matches (control, PASS).** Established before either real probe
   was trusted, so a silent non-firing could not be mistaken for a negative
   result. The payload carries **no** `project_dir` key. That does not make
-  `cwd` the guard's root signal: `spec_loop_guard.py:297` resolves the root
-  as `CLAUDE_PROJECT_DIR` from the environment, then the payload's `cwd`,
-  then `os.getcwd()` — so the environment variable wins and the payload's
-  `cwd` is only the first fallback. The `Stop` payload likewise carries no
+  `cwd` the guard's root signal: `spec_loop_guard.py`'s `evaluate()`
+  resolves the project root as `CLAUDE_PROJECT_DIR` from the environment,
+  then the payload's `cwd`, then `os.getcwd()` — so the environment
+  variable wins and the payload's `cwd` is only the first fallback. The
+  `Stop` payload likewise carries no
   `project_dir`.
 - **A sync `Stop` hook honours a top-level `{"decision":"block","reason":…}`
   (CONFIRMED).** Evidence, not inference: the harness model was asked to
   reply with one word, the hook blocked its turn end with a `reason`
   instructing a different token, and the session output was that token — so
   the reason text reached the model and the model continued its turn
   instead of ending it. This is the loop-boundary gate's one proven lever.
 - **Within a single turn, `stop_hook_active` is `false` on the fire that
   ends the turn and `true` on the fire that ends the block-caused
-  continuation (CONFIRMED).** Both fires were logged in one turn of the
-  probe session. This is why a gate that skips when `stop_hook_active` is
-  true pushes ONCE PER STALL rather than fencing: it cannot re-block the
-  continuation it just caused. Honouring the flag is therefore required,
-  not optional. What this evidence does **not** cover: whether the flag
-  starts at `false` again on a NEW user turn, i.e. whether the gate re-arms
-  per turn or is one-shot for the whole session. No second user turn was
-  observed; that question is untested and listed below.
+  continuation, and it resets to `false` again at the start of every NEW
+  user turn (CONFIRMED).** Both single-turn fires were logged in one turn of
+  probe B; the per-turn reset is established by the THIRD fire of a two-turn
+  session (probe B2), where the flag reads `false` at the end of turn 1,
+  `true` on the block-caused continuation, and `false` AGAIN at the end of
+  turn 2 — reproduced byte-identically on re-run. That third fire closes both
+  readings probe B left open, in opposite directions. Not a fence: a gate
+  that skips while the flag is true always yields on the immediately
+  following fire, so it pushes ONCE PER STALL rather than blocking
+  indefinitely. Not a one-shot per session: the gate re-arms on every user
+  turn, so it stands at the first `Stop` attempt of every turn — but within
+  that same turn the fire that ends a block-caused continuation carries the
+  flag true and is skipped, so a turn that drives several wave boundaries is
+  only guarded at its first one. Honouring the flag is therefore required,
+  not optional.
 - **Whether `AskUserQuestion` emits `PreToolUse` at all is UNRESOLVED.**
   This is an absence of opportunity, not a negative result: the tool is not
   exposed in print mode — the headless model reported it is neither in its
   tool list nor fetchable via ToolSearch — so the `AskUserQuestion` matcher
   never had a call to match. Nothing here licenses the claim that the event
   does or does not fire.
 
-Four questions need an INTERACTIVE session to settle. None is answered
+Three questions need an INTERACTIVE session to settle. None is answered
 today, and no shipped behaviour may be described as depending on an answer:
 
 1. Does `AskUserQuestion` emit `PreToolUse`? Register a logging-only
    `PreToolUse` hook with matcher `.*` in a settings file, start an
    interactive session, and trigger one `AskUserQuestion` call **and one
    `Bash` call**. The `Bash` call is the control and is not optional:
    without it, a log missing `AskUserQuestion` cannot be told apart from a
    hook that never loaded.
-2. Does `stop_hook_active` reset to `false` at the start of a new user
-   turn? Same logging hook plus a `Stop` hook that blocks once; take two
-   user turns in one session and compare the flag on the first fire of
-   each. Untested.
-3. Does Ctrl+C route through `Stop`? Same logging hook; interrupt a turn
+2. Does Ctrl+C route through `Stop`? Same logging hook; interrupt a turn
    and check whether a `Stop` payload is written. Untested.
-4. Does `Stop` fire at the end of a `Task` subagent's turn? Same logging
+3. Does `Stop` fire at the end of a `Task` subagent's turn? Same logging
    hook; run a Task subagent and look for a `Stop` payload carrying the
    subagent's turn. Untested — and `SubagentStop` being a distinct,
    unregistered event is not evidence either way.
diff --git a/plugins/spec-loop/scripts/test_doctrine_platform_probes.py b/plugins/spec-loop/scripts/test_doctrine_platform_probes.py
index 47fe770..6ed558e 100644
--- a/plugins/spec-loop/scripts/test_doctrine_platform_probes.py
+++ b/plugins/spec-loop/scripts/test_doctrine_platform_probes.py
@@ -6,13 +6,19 @@ what was not. The failure mode it must survive is a quiet promotion: an
 UNRESOLVED probe re-worded as a settled fact, or a CONFIRMED fact losing
 the evidence sentence that earns the label, with the suite still green.
 The vocabulary is therefore pinned here.
 
 A second failure mode is already realised history: the file once said the
-guard relies on the payload's `cwd` as its only root signal, which
-`spec_loop_guard.py:297` contradicts. The corrected precedence sentence is
-pinned so it cannot silently revert.
+guard relies on the payload's `cwd` as its only root signal, which the
+guard's `evaluate()` contradicts. The corrected precedence sentence, and
+its citation-by-symbol form, are both pinned so neither can silently
+revert.
+
+A third: the per-turn reset of stop_hook_active was written as Untested
+while the run's evidence file was missing probe B2. It is CONFIRMED by that
+probe's two-turn log, and the promotion is pinned in both directions here so
+neither the fact nor what it rules out can be dropped.
 
 Its own module rather than a class in test_doctrine_loop_boundary.py:
 that module's docstring scopes it to commands/spec-loop.md and the
 escalation-gate skill, and this file is neither.
 
@@ -32,10 +38,52 @@ import unittest
 from pathlib import Path
 
 PLUGIN_ROOT = Path(__file__).resolve().parents[1]
 PROBES_MD = PLUGIN_ROOT / "references" / "platform-probes.md"
 
+# Expected substrings live at module scope, not inside the test bodies:
+# quality_gate.py derives python nesting depth from leading whitespace, so a
+# visually-aligned call continuation reads as depth 4. Hoisting keeps every
+# assertion body at depth 1 with the assertion set unchanged.
+PER_TURN_CONFIRMED = (
+    "resets to `false` again at the start of every NEW user turn "
+    "(CONFIRMED).**"
+)
+PER_TURN_EVIDENCE = (
+    "established by the THIRD fire of a two-turn session (probe B2)"
+)
+PER_TURN_NOT_A_FENCE = (
+    "pushes ONCE PER STALL rather than blocking indefinitely"
+)
+PER_TURN_NOT_ONE_SHOT = (
+    "Not a one-shot per session: the gate re-arms on every user turn"
+)
+PER_TURN_SCOPED_TO_FIRST_STOP = (
+    "so it stands at the first `Stop` attempt of every turn"
+)
+PER_TURN_WITHIN_TURN_GAP = (
+    "within that same turn the fire that ends a block-caused continuation "
+    "carries the flag true and is skipped, so a turn that drives several "
+    "wave boundaries is only guarded at its first one"
+)
+RETRACTED_UNTESTED_FRAMING = (
+    "whether the gate re-arms per turn or is one-shot for the whole session"
+)
+RETRACTED_FOLLOWUP_QUESTION = (
+    "Does `stop_hook_active` reset to `false` at the start of a new user "
+    "turn?"
+)
+ROOT_PRECEDENCE_BY_SYMBOL = (
+    "`spec_loop_guard.py`'s `evaluate()` resolves the project root as "
+    "`CLAUDE_PROJECT_DIR` from the environment, then the payload's `cwd`, "
+    "then `os.getcwd()`"
+)
+PRECEDENCE_CONSEQUENCE = (
+    "the environment variable wins and the payload's `cwd` is only the "
+    "first fallback"
+)
+
 
 def prose(path):
     """One file's text with every whitespace run collapsed to a space. (PURE)"""
     return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
 
@@ -61,24 +109,27 @@ class TestUnresolvedProbesStayUnresolved(unittest.TestCase):
             "Nothing here licenses the claim that the event does or does "
             "not fire", self.text)
 
     def test_the_interactive_followups_stay_listed_as_unsettled(self):
         self.assertIn(
-            "Four questions need an INTERACTIVE session to settle", self.text)
+            "Three questions need an INTERACTIVE session to settle",
+            self.text)
         self.assertIn("Does Ctrl+C route through `Stop`?", self.text)
         self.assertIn(
             "Does `Stop` fire at the end of a `Task` subagent's turn?",
             self.text)
-        # Three of the four carry an explicit "Untested." marker; the
+        # Two of the three carry an explicit "Untested." marker; the
         # AskUserQuestion entry is covered by its own bullet above.
-        self.assertEqual(self.text.count("Untested"), 3)
+        self.assertEqual(self.text.count("Untested"), 2)
 
 
 class TestConfirmedFactsKeepTheirEvidence(unittest.TestCase):
-    """Only two hook facts were established. Each keeps its CONFIRMED label
-    AND the sentence that earns it, so a label cannot outlive its
-    evidence."""
+    """Only two hook facts were established, and each keeps its CONFIRMED
+    label AND the sentence that earns it, so a label cannot outlive its
+    evidence. The per-turn reset was promoted from Untested once probe B2
+    was recorded; the framing that called it untested must not survive
+    alongside the promotion."""
 
     def setUp(self):
         self.text = prose(PROBES_MD)
 
     def test_the_stop_block_fact_is_confirmed_with_its_evidence(self):
@@ -86,35 +137,54 @@ class TestConfirmedFactsKeepTheirEvidence(unittest.TestCase):
             "A sync `Stop` hook honours a top-level "
             "`{\"decision\":\"block\",\"reason\":…}` (CONFIRMED).", self.text)
         self.assertIn("Evidence, not inference", self.text)
 
     def test_the_per_turn_flag_fact_is_confirmed_with_its_evidence(self):
-        self.assertIn("(CONFIRMED).** Both fires were logged in one turn",
-                      self.text)
-        self.assertIn(
-            "pushes ONCE PER STALL rather than fencing", self.text)
+        self.assertIn(PER_TURN_CONFIRMED, self.text)
+        self.assertIn(PER_TURN_EVIDENCE, self.text)
+        self.assertIn(PER_TURN_NOT_A_FENCE, self.text)
+        self.assertIn(PER_TURN_NOT_ONE_SHOT, self.text)
+
+    def test_the_per_turn_reset_does_not_overclaim_per_boundary_coverage(
+            self):
+        # evaluate() returns None whenever stop_hook_active is true, so a
+        # turn with several wave boundaries is only guarded at its first
+        # Stop attempt -- the register must say so, not claim coverage at
+        # every boundary.
+        self.assertIn(PER_TURN_SCOPED_TO_FIRST_STOP, self.text)
+        self.assertIn(PER_TURN_WITHIN_TURN_GAP, self.text)
+        self.assertNotIn(
+            "it stands at every wave boundary, not only the first",
+            self.text)
+
+    def test_the_retracted_untested_framing_is_gone(self):
+        self.assertNotIn(RETRACTED_UNTESTED_FRAMING, self.text)
+        self.assertNotIn(RETRACTED_FOLLOWUP_QUESTION, self.text)
 
     def test_exactly_two_hook_facts_are_labelled_confirmed(self):
         self.assertEqual(self.text.count("(CONFIRMED)"), 2)
 
 
 class TestTheGuardRootSignalClaimStaysTrue(unittest.TestCase):
-    """The shipped false claim: that the payload's `cwd` is what the guard
-    relies on. `spec_loop_guard.py:297` prefers CLAUDE_PROJECT_DIR. The
-    corrected sentence carries its own citation."""
+    """The shipped false claim: that the payload's cwd is what the guard
+    relies on. The guard's evaluate() prefers CLAUDE_PROJECT_DIR. The
+    corrected sentence names that symbol, not a line number — a citation
+    pinned by its digits rots silently on the next insertion above it,
+    which is the failure this module exists to close."""
 
     def setUp(self):
         self.text = prose(PROBES_MD)
 
     def test_the_false_only_root_signal_claim_is_gone(self):
         self.assertNotIn("is the only root signal", self.text)
 
     def test_the_true_precedence_is_stated_and_cited(self):
         self.assertIn("carries **no** `project_dir` key", self.text)
-        self.assertIn("`spec_loop_guard.py:297`", self.text)
-        self.assertIn(
-            "the environment variable wins and the payload's `cwd` is only "
-            "the first fallback", self.text)
+        self.assertIn(ROOT_PRECEDENCE_BY_SYMBOL, self.text)
+        self.assertIn(PRECEDENCE_CONSEQUENCE, self.text)
+
+    def test_no_citation_is_pinned_to_a_line_number(self):
+        self.assertNotIn("spec_loop_guard.py:", self.text)
 
 
 if __name__ == "__main__":
     unittest.main()
