# Review package: 560dceb..43ebdf8  (context: -U5)

## Commits
43ebdf8 test(jira-intake): pin the corrected recovery and concurrency prose
c4bd1a4 docs(jira-intake): name the cross-process dedupe window
a7c2a99 docs(jira-intake): scope the partial-post recovery to the posting step

## Files changed
 plugins/spec-loop/commands/jira-intake.md          | 35 +++++++++++++++-------
 .../spec-loop/scripts/test_doctrine_jira_intake.py | 16 ++++++++++
 2 files changed, 40 insertions(+), 11 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/commands/jira-intake.md": [
[
69,
74
],
[
188,
205
]
],
"plugins/spec-loop/scripts/test_doctrine_jira_intake.py": [
[
107,
122
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/commands/jira-intake.md b/plugins/spec-loop/commands/jira-intake.md
index ab674b9..82d6dc7 100644
--- a/plugins/spec-loop/commands/jira-intake.md
+++ b/plugins/spec-loop/commands/jira-intake.md
@@ -64,10 +64,16 @@ the tool set and this section exact.
   substring search for the marker in the card's comment bodies, so a comment that merely
   *quotes* a marker — including one a card author pasted in — makes this lane report that
   comment as `already-posted` and skip the write. This fails safe (it can only skip a write,
   never cause one) and is accepted deliberately: the alternative, parsing authorship out of
   untrusted comment text, would make untrusted card content decide whether a write happens.
+- **Known limitation: the dedupe gate is per-invocation, not cross-process.** The card's
+  comment list is read once per invocation, before the first write, so two operators arming the
+  lane concurrently — or a re-run overlapping a slow first run — can both act on the same
+  pre-write snapshot and both post. Jira offers no compare-and-set on comment creation, so the
+  window is accepted rather than closed; arm this lane one operator at a time, and if two runs
+  did overlap, read the card before arming again.
 
 ## Steps
 
 1. **Validate the key and ensure the ignore entry.** `$1` must match
    `^[A-Z][A-Z0-9]{1,9}-[0-9]{1,10}$` exactly (full match, no leading or trailing whitespace, no
@@ -177,21 +183,28 @@ the tool set and this section exact.
    ```
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jira_client.py" comment --key <KEY> --comments <tmp>/comments.json --post
    ```
    It re-reads the card's full comment list ONCE, before the first write of the run — not before
    each individual comment — so a comment already on the card when that read happened is skipped
-   rather than duplicated, and a re-run of this whole command is a genuine no-op. A duplicate
-   marker appearing twice inside one batch is refused outright before the first request. Exit 1
-   prints `{"ok": false, "errors": [...]}` on stdout and exit 2 prints `error: ...` on stderr —
-   surface either verbatim and stop. **A mid-sequence failure is fail-closed per comment but NOT transactional.** Each comment is
-   written whole by one POST or not at all, and the first failure stops the run so no later
-   comment is posted — but comments earlier in the same batch may already be live on the card,
-   and nothing rolls them back. The exit-1 error names every marker already posted before the
-   failure; an undisclosed partial mutation is the one failure mode that most needs surfacing
-   on this plugin's first mutating external call. **The correct recovery is to re-run this command**,
-   which the marker dedupe makes safe: the already-live comments come back as `already-posted` and
-   only the remaining ones are offered. Do not post the remaining comments by hand.
+   rather than duplicated, and re-running the POSTING step with the same rendered comments file is
+   a genuine no-op. A duplicate marker appearing twice inside one batch is refused outright before
+   the first request. Exit 1 prints `{"ok": false, "errors": [...]}` on stdout and exit 2 prints
+   `error: ...` on stderr — surface either verbatim and stop. **A mid-sequence failure is
+   fail-closed per comment but NOT transactional.** Each comment is written whole by one POST or
+   not at all, and the first failure stops the run so no later comment is posted — but comments
+   earlier in the same batch may already be live on the card, and nothing rolls them back. The
+   exit-1 error names every marker already posted before the failure; an undisclosed partial
+   mutation is the one failure mode that most needs surfacing on this plugin's first mutating
+   external call.
+   **The correct recovery is to re-run the POSTING step with the same rendered comments file** —
+   the same `<tmp>/comments.json`, re-armed with `--post` — which the marker dedupe makes safe:
+   the already-live comments come back as `already-posted` and only the remaining ones are
+   written. **Do NOT re-run the refinement** (and so do not re-run this whole slash command to
+   recover): a regenerated refinement produces new markers that will not dedupe against what is
+   already on the card, because `comment_marker` hashes the payload text and a single character
+   of drift yields a different marker and a second near-identical comment. Do not post the
+   remaining comments by hand.
    On success print each result's `kind`, `marker` and `status`. Never echo, log, or quote
    a credential.
 
 9. **Print the handoff.** Print, as the final user-facing output, the single line
    ```
diff --git a/plugins/spec-loop/scripts/test_doctrine_jira_intake.py b/plugins/spec-loop/scripts/test_doctrine_jira_intake.py
index 51164db..aed14bd 100644
--- a/plugins/spec-loop/scripts/test_doctrine_jira_intake.py
+++ b/plugins/spec-loop/scripts/test_doctrine_jira_intake.py
@@ -102,10 +102,26 @@ class TestTheJiraWriteIsBoundedToComments(unittest.TestCase):
 
     def test_the_dedupe_gate_is_the_cards_own_comment_list(self):
         self.assertIn("card's own full comment list", self.text)
         self.assertIn("already-posted", self.text)
 
+    def test_recovery_is_the_posting_step_not_the_whole_command(self):
+        """A regenerated refinement yields new markers, so 'just re-run the
+        command' would double-post. The prose must scope recovery to
+        re-posting the SAME rendered comments file."""
+        self.assertIn(
+            "re-run the POSTING step with the same rendered comments file",
+            self.text)
+        self.assertIn("NOT re-run the refinement", self.text)
+        self.assertIn(
+            "a regenerated refinement produces new markers", self.text)
+
+    def test_the_cross_process_dedupe_window_is_disclosed(self):
+        """The pre-write read is per-invocation, so concurrent arming can
+        double-post. That window is disclosed, not implied."""
+        self.assertIn("read once per invocation", self.text)
+
     def test_it_records_the_supersession_it_reverses(self):
         self.assertIn("peer-review.md", self.text)
         self.assertIn("pr_resolver.py", self.text)
 
     def test_it_carries_the_untrusted_input_framing(self):
