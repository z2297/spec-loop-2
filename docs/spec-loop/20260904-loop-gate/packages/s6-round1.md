# Review package: 46feefc1af99d9882dfdc62ec004618f1cafc7e5..ed753a7e46362b0c679a2039e149a76aafdbe798  (context: -U5)

## Commits
ed753a7 fix(guard): fail open per run on an undecodable controller marker

## Files changed
 plugins/spec-loop/scripts/spec_loop_guard.py           |  6 +++++-
 plugins/spec-loop/scripts/test_spec_loop_guard_stop.py | 17 +++++++++++++++++
 2 files changed, 22 insertions(+), 1 deletion(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/spec_loop_guard.py": [
[
146,
149
],
[
155,
155
]
],
"plugins/spec-loop/scripts/test_spec_loop_guard_stop.py": [
[
164,
180
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/spec_loop_guard.py b/plugins/spec-loop/scripts/spec_loop_guard.py
index 22a4095..8c1e149 100644
--- a/plugins/spec-loop/scripts/spec_loop_guard.py
+++ b/plugins/spec-loop/scripts/spec_loop_guard.py
@@ -141,16 +141,20 @@ def _push_targets_run(command, run):
 def _controller_marker(run):
     """Raw text of the run's `.controller-session` marker, or None.
 
     Absent or blank => no recorded controller, so the gate declines to block
     at all; check_stop matches it as a substring (a labelled marker works).
+    ValueError is caught alongside OSError — an undecodable marker raises
+    UnicodeDecodeError, which is a ValueError, not an OSError — so this run
+    fails open on its own, matching _blocking_slices and never escaping to
+    main()'s blanket handler, which would unlock the gate for every run.
     """
     marker_path = os.path.join(run["dir"], ".controller-session")
     try:
         with open(marker_path, "r", encoding="utf-8") as fh:
             return fh.read().strip() or None
-    except OSError:
+    except (OSError, ValueError):
         return None
 
 
 def _blocking_slices(run):
     """Runnable slice ids that make ending the turn wrong, or None to ALLOW.
diff --git a/plugins/spec-loop/scripts/test_spec_loop_guard_stop.py b/plugins/spec-loop/scripts/test_spec_loop_guard_stop.py
index 4d8c935..ec5221f 100644
--- a/plugins/spec-loop/scripts/test_spec_loop_guard_stop.py
+++ b/plugins/spec-loop/scripts/test_spec_loop_guard_stop.py
@@ -159,10 +159,27 @@ class StopGateFailOpenTests(GuardTestCase):
         self.make_run("20260902-run-b", slices=PENDING, controller_session="sess-ctl")
         reason = guard.evaluate(self.stop(session_id="sess-ctl"))
         self.assertIsNotNone(reason)
         self.assertIn("20260902-run-b", reason)
 
+    def test_undecodable_marker_does_not_fail_open_for_a_healthy_run(self):
+        # A .controller-session that is not valid UTF-8 raises
+        # UnicodeDecodeError — a ValueError, NOT an OSError. If
+        # _controller_marker lets it escape, main()'s blanket handler
+        # swallows it and the gate unlocks for EVERY run, not just this
+        # one. The property under test is that isolation, so a second
+        # healthy run controlled by the same session must still block.
+        broken = self.make_run("20260901-run-a", controller_session="sess-ctl")
+        with open(os.path.join(broken, ".controller-session"), "wb") as fh:
+            fh.write(b"\xff\xfe\x00bad")
+        self.make_run(
+            "20260902-run-b", slices=PENDING, controller_session="sess-ctl")
+        reason = guard.evaluate(self.stop(session_id="sess-ctl"))
+        self.assertIsNotNone(reason)
+        self.assertIn("20260902-run-b", reason)
+        self.assertIn("s4", reason)
+
     def test_stale_other_run_is_skipped_not_blamed(self):
         # A stale .active owned by a different session must not block this one.
         self.make_run("20260901-stale", slices=PENDING, controller_session="sess-old")
         self.make_run("20260902-mine", slices=ALL_DONE, controller_session="sess-ctl")
         self.assertIsNone(guard.evaluate(self.stop(session_id="sess-ctl")))
