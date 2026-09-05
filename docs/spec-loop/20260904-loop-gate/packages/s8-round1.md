# Review package: 90ef235a1bacbaafa595d287ae9aac7fd0aac292..fa9257d  (context: -U5)

## Commits
fa9257d test(doctrine): state the numbered-list cross-check's file-wide scope
0bf35db test(doctrine): hoist the count-helper message to keep nesting at depth 2
9251144 test(doctrine): pin CHANGELOG open-probe-question count against the register
718edbb docs(changelog): correct open-probe-question list to match platform-probes

## Files changed
 CHANGELOG.md                                       | 10 ++-
 .../scripts/test_doctrine_platform_probes.py       | 88 ++++++++++++++++++++++
 2 files changed, 94 insertions(+), 4 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
36,
36
],
[
38,
42
]
],
"plugins/spec-loop/scripts/test_doctrine_platform_probes.py": [
[
85,
109
],
[
214,
276
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 08a45b1..44efbc1 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -31,15 +31,17 @@ All notable changes to the spec-loop plugin are documented here. The format is
   `.controller-session`, skipped when `stop_hook_active` is true — probed on Claude Code
   2.1.260 and CONFIRMED within a single turn to be `false` on the turn-ending fire and `true`
   on the block-caused continuation's fire, which makes the gate one push per stall rather than
   a fence — relaxed by a `.paused` marker that relaxes THIS gate alone, and fails open PER RUN
   (not globally) when a `.controller-session` marker cannot be decoded. The probe evidence and
-  its limits are recorded in `references/platform-probes.md`, together with the four questions
+  its limits are recorded in `references/platform-probes.md`, together with the three questions
   that remain UNTESTED there: whether `AskUserQuestion` emits `PreToolUse` at all, whether
-  `stop_hook_active` resets at the start of a new user turn (so whether the gate re-arms per
-  turn or is one-shot per session is NOT established), whether Ctrl+C routes through `Stop`,
-  and whether `Stop` fires for `Task` subagents. A PreToolUse gate on `AskUserQuestion` was
+  Ctrl+C routes through `Stop`, and whether `Stop` fires for `Task` subagents. The per-turn
+  reset is no longer one of them: `stop_hook_active` returning to `false` at the start of every
+  NEW user turn is CONFIRMED — established by the third `Stop` fire of a two-turn probe session,
+  where the flag read `false` again at the end of turn 2 — so the gate re-arms each turn instead
+  of being one-shot per session. A PreToolUse gate on `AskUserQuestion` was
   considered and DROPPED by human decision; no part of it was built and nothing in this release
   guards that path.
 
 ### Changed
 - **Run-state markers are now untracked, ignored and pinned, and the contract that describes
diff --git a/plugins/spec-loop/scripts/test_doctrine_platform_probes.py b/plugins/spec-loop/scripts/test_doctrine_platform_probes.py
index 6ed558e..0502c80 100644
--- a/plugins/spec-loop/scripts/test_doctrine_platform_probes.py
+++ b/plugins/spec-loop/scripts/test_doctrine_platform_probes.py
@@ -80,10 +80,35 @@ ROOT_PRECEDENCE_BY_SYMBOL = (
 PRECEDENCE_CONSEQUENCE = (
     "the environment variable wins and the payload's `cwd` is only the "
     "first fallback"
 )
 
+# CHANGELOG.md restates this register's open-question list, so the two are
+# cross-checked below. Neither count is written here: both are read out of
+# the files at run time.
+REPO_ROOT = PLUGIN_ROOT.parents[1]
+CHANGELOG_MD = REPO_ROOT / "CHANGELOG.md"
+
+WORD_TO_INT = {
+    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
+    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
+}
+CHANGELOG_OPEN_COUNT_RE = re.compile(
+    r"the (\w+) questions that remain UNTESTED there")
+PROBES_OPEN_COUNT_RE = re.compile(
+    r"(\w+) questions need an INTERACTIVE session to settle")
+PROBES_NUMBERED_ITEM_RE = re.compile(r"^\d+\. ", re.MULTILINE)
+CHANGELOG_TOPICS = (
+    "whether `AskUserQuestion` emits `PreToolUse` at all",
+    "whether Ctrl+C routes through `Stop`",
+    "whether `Stop` fires for `Task` subagents",
+)
+CHANGELOG_RETRACTED_FRAMING = "is one-shot per session is NOT established"
+CHANGELOG_INSTALL_VERSION_LIMIT = (
+    "The installed plugin was 2.2.0 while this repository is 2.3.0"
+)
+
 
 def prose(path):
     """One file's text with every whitespace run collapsed to a space. (PURE)"""
     return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
 
@@ -184,7 +209,70 @@ class TestTheGuardRootSignalClaimStaysTrue(unittest.TestCase):
 
     def test_no_citation_is_pinned_to_a_line_number(self):
         self.assertNotIn("spec_loop_guard.py:", self.text)
 
 
+class TestChangelogAgreesWithTheProbeRegister(unittest.TestCase):
+    """CHANGELOG.md restates this register's open-question list, and a
+    restatement with no test is exactly how it went stale: the entry still
+    said four questions remained UNTESTED after the per-turn reset had been
+    promoted to CONFIRMED here.
+
+    Scoped to THIS module rather than a new one: the subject under test is
+    the probe register's contents, and a user-facing file asserting a
+    different count is a claim about that register. A separate module would
+    have to re-derive the register's own count anyway.
+
+    Both counts are read out of the two files. Hard-coding three in the
+    assertion would make this pin need an edit the next time a question is
+    settled -- and an unedited pin is as stale as the prose it guards. The
+    register's spelled-out word is additionally cross-checked against its
+    numbered list items on disk, so the link is to the list, not to a word.
+
+    Honest limit on that cross-check: it counts every `N. ` line in
+    platform-probes.md, and that register carries exactly one numbered
+    list today. A second, unrelated numbered list there would make this
+    test red without the open-question count having drifted -- a visible
+    false red, not a silent pass, and the fix is to scope the count to the
+    section rather than to drop the check.
+    """
+
+    def setUp(self):
+        self.changelog = prose(CHANGELOG_MD)
+        self.probes = prose(PROBES_MD)
+        self.probes_raw = PROBES_MD.read_text(encoding="utf-8")
+
+    def _count(self, pattern, text, label):
+        match = pattern.search(text)
+        self.assertIsNotNone(match, "%s: count sentence not found" % label)
+        word = match.group(1).lower()
+        # Bound to a name rather than wrapped as a call continuation: an
+        # aligned continuation's leading whitespace reads as nesting depth
+        # 4 to quality_gate.py, over its threshold of 3.
+        not_a_number = "%s: %r is not a number word" % (label, word)
+        self.assertIn(word, WORD_TO_INT, not_a_number)
+        return WORD_TO_INT[word]
+
+    def test_the_register_word_matches_its_numbered_list(self):
+        stated = self._count(PROBES_OPEN_COUNT_RE, self.probes, "probes")
+        items = len(PROBES_NUMBERED_ITEM_RE.findall(self.probes_raw))
+        self.assertEqual(stated, items)
+
+    def test_the_changelog_open_question_count_matches_the_register(self):
+        changelog = self._count(
+            CHANGELOG_OPEN_COUNT_RE, self.changelog, "changelog")
+        probes = self._count(PROBES_OPEN_COUNT_RE, self.probes, "probes")
+        self.assertEqual(changelog, probes)
+
+    def test_the_changelog_names_each_open_question(self):
+        for topic in CHANGELOG_TOPICS:
+            self.assertIn(topic, self.changelog)
+
+    def test_the_changelog_retracted_untested_framing_is_gone(self):
+        self.assertNotIn(CHANGELOG_RETRACTED_FRAMING, self.changelog)
+
+    def test_the_changelog_keeps_its_install_version_limitation(self):
+        self.assertIn(CHANGELOG_INSTALL_VERSION_LIMIT, self.changelog)
+
+
 if __name__ == "__main__":
     unittest.main()
