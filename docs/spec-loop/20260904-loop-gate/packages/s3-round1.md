# Review package: 4b91d69393a02e233a000130f6baf7def7713c95..d0e0102  (context: -U5)

## Commits
d0e0102 docs(run-state): state marker hygiene the repo now enforces
4b0e9a7 fix(hygiene): untrack run-state markers and ignore the marker names

## Files changed
 .gitignore                                         |  12 ++
 docs/spec-loop/20260825-scope-ceiling/.done        |   0
 .../20260825-scope-ceiling/.publish-choice         |   1 -
 docs/spec-loop/20260826-crash-classification/.done |   0
 .../20260826-crash-classification/.publish-choice  |   1 -
 docs/spec-loop/20260827-deferral-sweep/.done       |   0
 .../20260827-deferral-sweep/.publish-choice        |   1 -
 docs/spec-loop/20260828-refactor-escalation/.done  |   0
 .../20260828-refactor-escalation/.publish-choice   |  13 --
 plugins/spec-loop/references/run-state-v2.md       |  24 +++-
 .../scripts/test_doctrine_marker_hygiene.py        | 150 +++++++++++++++++++++
 11 files changed, 183 insertions(+), 19 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
".gitignore": [
[
7,
18
]
],
"plugins/spec-loop/references/run-state-v2.md": [
[
272,
273
],
[
278,
293
],
[
296,
298
]
],
"plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py": [
[
1,
150
]
]
}
```

## Diff
diff --git a/.gitignore b/.gitignore
index 9320d7f..900817b 100644
--- a/.gitignore
+++ b/.gitignore
@@ -2,5 +2,17 @@
 .worktrees/
 
 # Python cache (release/validation scripts)
 __pycache__/
 *.pyc
+
+# spec-loop run-state markers (never commit)
+# The guard hooks fire on these files' PRESENCE. A committed marker arrives on
+# every clone and every fresh worktree, so a committed .active would deny
+# pushes and main-branch commits in sessions that have no run at all. They are
+# per-checkout, per-session state, like .worktrees/. Bare names on purpose:
+# they must be ignored at any depth, under any run directory.
+.active
+.controller-session
+.done
+.paused
+.publish-choice
diff --git a/docs/spec-loop/20260825-scope-ceiling/.done b/docs/spec-loop/20260825-scope-ceiling/.done
deleted file mode 100644
index e69de29..0000000
diff --git a/docs/spec-loop/20260825-scope-ceiling/.publish-choice b/docs/spec-loop/20260825-scope-ceiling/.publish-choice
deleted file mode 100644
index 8976109..0000000
--- a/docs/spec-loop/20260825-scope-ceiling/.publish-choice
+++ /dev/null
@@ -1 +0,0 @@
-push-feature-branch-and-open-pr
diff --git a/docs/spec-loop/20260826-crash-classification/.done b/docs/spec-loop/20260826-crash-classification/.done
deleted file mode 100644
index e69de29..0000000
diff --git a/docs/spec-loop/20260826-crash-classification/.publish-choice b/docs/spec-loop/20260826-crash-classification/.publish-choice
deleted file mode 100644
index 8976109..0000000
--- a/docs/spec-loop/20260826-crash-classification/.publish-choice
+++ /dev/null
@@ -1 +0,0 @@
-push-feature-branch-and-open-pr
diff --git a/docs/spec-loop/20260827-deferral-sweep/.done b/docs/spec-loop/20260827-deferral-sweep/.done
deleted file mode 100644
index e69de29..0000000
diff --git a/docs/spec-loop/20260827-deferral-sweep/.publish-choice b/docs/spec-loop/20260827-deferral-sweep/.publish-choice
deleted file mode 100644
index c090cc4..0000000
--- a/docs/spec-loop/20260827-deferral-sweep/.publish-choice
+++ /dev/null
@@ -1 +0,0 @@
-merge-onto-main-and-cut-patch-release
diff --git a/docs/spec-loop/20260828-refactor-escalation/.done b/docs/spec-loop/20260828-refactor-escalation/.done
deleted file mode 100644
index e69de29..0000000
diff --git a/docs/spec-loop/20260828-refactor-escalation/.publish-choice b/docs/spec-loop/20260828-refactor-escalation/.publish-choice
deleted file mode 100644
index d086a9c..0000000
--- a/docs/spec-loop/20260828-refactor-escalation/.publish-choice
+++ /dev/null
@@ -1,13 +0,0 @@
-choice: merge-main-and-push
-decided: 2026-08-29
-run_id: 20260828-refactor-escalation
-integration_branch: spec-loop-run/20260828-refactor-escalation
-base_branch: main
-head: b2e65a2
-detail: >
-  Human chose to merge the integration branch onto local main with --no-ff and
-  push main to origin. Recorded BEFORE any publish action was taken.
-note: >
-  origin/main was 117 commits behind local main before this run, from prior runs
-  that were never pushed. Pushing main therefore publishes those 117 commits plus
-  this run's 45.
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index 10fcc6d..0019058 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -267,19 +267,37 @@ no pinned machine grammar in v2.
 | `runbook.md` | runbook-writer agent | end-of-run synthesis, committed |
 | `metrics.json` | `run_metrics.py --write` | atomic write |
 
 ## Markers — guard-hook contract (unchanged from v1)
 
-- `.active` — created at Phase 1, recreated on resume, never committed. While
-  present, `spec_loop_guard.py` blocks pushes, broad staging, main-branch
+- `.active` — created at Phase 1, recreated on resume. While present,
+  `spec_loop_guard.py` blocks pushes, broad staging, main-branch
   commits/merges, and quality-gate config writes.
 - `.publish-choice` — written the instant the human answers the publish
   prompt, before the action is performed.
 - `.done` — `.active` renamed at run end.
+- `.paused` — present only while the human has deliberately suspended the
+  loop-boundary gate. It relaxes that one gate and nothing else; every
+  `.active` restriction above still applies.
+- `.controller-session` — identifies the controller's own session so the
+  loop-boundary gate applies to it and not to other sessions. Per-session
+  state, meaningful only inside the machine that wrote it.
+
+None of these markers is ever committed. They are per-checkout state: the
+hooks fire on a marker's PRESENCE, so a committed `.active` would deny pushes
+and main-branch commits on every clone and in every fresh worktree, including
+sessions with no run at all. `.gitignore` enforces this with one bare,
+unanchored entry per marker name, and `test_doctrine_marker_hygiene.py` fails
+if one re-enters the index. Markers did get committed twice before that pin
+existed; the correction is an index-only removal (`git rm --cached`) that
+leaves the files on disk for any run still reading them — never a history
+rewrite, and never a plain delete.
 
 A hook denial means the run has not earned that operation yet — never delete
-a marker to dodge one.
+a marker to dodge one. A stale marker is remediated by resuming the run or
+clearing the marker, in that order; that applies to a stale `.paused` exactly
+as it does to a stale `.active`.
 
 ## Worktrees & branches
 
 - Worktree: `.worktrees/spec-loop/<run-id>/<slice-id>` (gitignored).
 - Branch: `spec-loop/<run-id>/<slice-id>`, cut from the current tip of
diff --git a/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py b/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py
new file mode 100644
index 0000000..01d3b2e
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_doctrine_marker_hygiene.py
@@ -0,0 +1,150 @@
+#!/usr/bin/env python3
+"""Doctrine checks for spec-loop run-state marker hygiene.
+
+The guard hooks key off on-disk markers under docs/spec-loop/<run-id>/:
+.active, .done, .publish-choice, .paused, and .controller-session. A marker
+that is COMMITTED arrives on every clone and every fresh worktree, which
+turns the guard against the repo - a committed .active denies pushes and
+main-branch commits forever, for everyone, in sessions that have no run at
+all.
+
+This happened: .active entered the index twice (commits 5de8f42 and
+a413b93) and two runs' .done / .publish-choice markers rode in on the
+feature merges 7fdd7e2 and e9460f8, while references/run-state-v2.md
+already said .active is "never committed". Prose alone did not hold the
+line, so this module pins it.
+
+Honest limits: the tracking assertion shells out to `git ls-files` and is
+skipped only when there is no .git entry at REPO_ROOT (a source tarball).
+When git IS present it fails loudly rather than skipping, so the pin cannot
+degrade into a silent no-op. The .gitignore assertions check literal
+entries and the absence of a leading slash; they prove the patterns are
+present and unanchored, not that git's matcher behaves as intended - that
+part is covered by the tracking assertion, which is the property that
+actually matters.
+
+Usage:
+    python3 -m unittest discover -s plugins/spec-loop/scripts \\
+        -p 'test_doctrine_marker_hygiene.py'
+"""
+
+import re
+import subprocess
+import unittest
+from pathlib import Path
+
+REPO_ROOT = Path(__file__).resolve().parents[3]
+GITIGNORE = REPO_ROOT / ".gitignore"
+RUN_STATE_MD = (
+    Path(__file__).resolve().parents[1] / "references" / "run-state-v2.md"
+)
+MARKERS = (
+    ".active",
+    ".controller-session",
+    ".done",
+    ".paused",
+    ".publish-choice",
+)
+
+
+def prose(path):
+    """One file's text with every whitespace run collapsed to a space. (PURE)"""
+    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
+
+
+def ignore_lines():
+    """The non-blank, non-comment lines of .gitignore, stripped."""
+    return [
+        line.strip()
+        for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
+        if line.strip() and not line.strip().startswith("#")
+    ]
+
+
+def repo_has_git():
+    """True when REPO_ROOT has a .git dir OR a .git file (linked worktree)."""
+    return (REPO_ROOT / ".git").exists()
+
+
+def git(*args):
+    """Stripped stdout of a git command in REPO_ROOT. Raises on failure."""
+    done = subprocess.run(
+        ("git", "-C", str(REPO_ROOT)) + args,
+        capture_output=True,
+        text=True,
+        timeout=30,
+    )
+    if done.returncode != 0:
+        raise RuntimeError(
+            "git %s failed with exit %d: %s"
+            % (" ".join(args), done.returncode, done.stderr.strip())
+        )
+    return done.stdout.strip()
+
+
+class TestMarkersAreNotTracked(unittest.TestCase):
+    """No run-state marker may be in the index, and all five are ignored."""
+
+    def test_no_run_state_marker_is_tracked(self):
+        if not repo_has_git():
+            self.skipTest("no .git at repo root (source tarball)")
+        listing = git("ls-files", "--", "docs/spec-loop")
+        tracked = [
+            path
+            for path in listing.splitlines()
+            if Path(path).name in MARKERS
+        ]
+        self.assertEqual(
+            tracked,
+            [],
+            "these run-state markers are committed and will fire the guard "
+            "on every checkout; remove them from the index only, leaving "
+            "them on disk: %s" % tracked,
+        )
+
+    def test_every_marker_name_is_gitignored(self):
+        lines = ignore_lines()
+        for marker in MARKERS:
+            self.assertIn(
+                marker,
+                lines,
+                "%s is not a literal .gitignore entry, so the next run can "
+                "commit it again" % marker,
+            )
+
+    def test_marker_ignore_patterns_are_unanchored(self):
+        for line in ignore_lines():
+            for marker in MARKERS:
+                if line.endswith(marker):
+                    self.assertEqual(
+                        line,
+                        marker,
+                        "%s must be matched at any depth, so its .gitignore "
+                        "entry must be the bare name, not %r" % (marker, line),
+                    )
+
+
+class TestRunStateDocStatesMarkerHygiene(unittest.TestCase):
+    """The Markers section must name every marker and the ignore rule."""
+
+    def test_every_marker_is_documented(self):
+        text = prose(RUN_STATE_MD)
+        for marker in MARKERS:
+            self.assertIn("`%s`" % marker, text, "%s undocumented" % marker)
+
+    def test_the_class_wide_never_committed_rule_is_stated(self):
+        self.assertIn(
+            "None of these markers is ever committed",
+            prose(RUN_STATE_MD),
+        )
+
+    def test_gitignore_is_named_as_the_enforcement(self):
+        text = prose(RUN_STATE_MD)
+        self.assertIn("`.gitignore`", text)
+        self.assertIn("index-only removal", text)
+
+    def test_the_do_not_delete_a_marker_sentence_survives(self):
+        self.assertIn(
+            "never delete a marker to dodge one",
+            prose(RUN_STATE_MD),
+        )
