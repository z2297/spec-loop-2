# Review package: a97ccd1..560dceb  (context: -U5)

## Commits
560dceb fix(jira): surface bare OSError on POST response read as a JiraError

## Files changed
 plugins/spec-loop/scripts/jira_client.py      | 12 +++++++++
 plugins/spec-loop/scripts/test_jira_client.py | 38 +++++++++++++++++++++++++++
 2 files changed, 50 insertions(+)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/jira_client.py": [
[
266,
277
]
],
"plugins/spec-loop/scripts/test_jira_client.py": [
[
336,
347
],
[
1162,
1187
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/jira_client.py b/plugins/spec-loop/scripts/jira_client.py
index 4f35e78..71dc3f4 100644
--- a/plugins/spec-loop/scripts/jira_client.py
+++ b/plugins/spec-loop/scripts/jira_client.py
@@ -261,10 +261,22 @@ def _http_post(url, email, token, payload):
         raise JiraError(
             f"HTTP {exc.code} posting to {url}: {exc.reason}") from exc
     except urllib.error.URLError as exc:
         raise JiraError(
             f"network error posting to {url}: {exc.reason}") from exc
+    except OSError as exc:
+        # urllib only wraps an OSError raised by h.request() into a
+        # URLError (see CPython's AbstractHTTPHandler.do_open); an
+        # OSError out of h.getresponse() or resp.read() -- e.g. a
+        # timeout while reading the response to a POST that has
+        # already landed on the card -- propagates unwrapped and would
+        # otherwise slip past the JiraError handling above, past
+        # execute_comment_plan's `except JiraError`, and past main()'s
+        # exit-1 JSON contract. Caught here, terminally, so every
+        # transport failure on the write path is a JiraError and can
+        # still be turned into a partial-batch disclosure.
+        raise JiraError(f"network error posting to {url}: {exc}") from exc
 
 
 def _parse_json(raw, what):
     """json.loads with an actionable JiraError, so a malformed response fails
     with a clear message rather than a raw traceback."""
diff --git a/plugins/spec-loop/scripts/test_jira_client.py b/plugins/spec-loop/scripts/test_jira_client.py
index a74829b..831ec7e 100644
--- a/plugins/spec-loop/scripts/test_jira_client.py
+++ b/plugins/spec-loop/scripts/test_jira_client.py
@@ -331,10 +331,22 @@ class TestHttpPostIsTheOnlyWriter(unittest.TestCase):
         opener = mock.MagicMock()
         opener.open.side_effect = urllib.error.URLError("connection refused")
         with self.assertRaises(jc.JiraError):
             self._post(opener)
 
+    def test_a_bare_timeout_reading_the_response_becomes_a_jira_error(self):
+        # urllib only wraps an OSError raised by h.request() into a
+        # URLError; a timeout while reading the response to a POST that
+        # has already landed on the card raises a bare TimeoutError
+        # (a plain OSError subclass) out of h.getresponse()/resp.read(),
+        # which must still surface as a JiraError rather than an
+        # unhandled traceback on this, the write path.
+        opener = mock.MagicMock()
+        opener.open.side_effect = TimeoutError("timed out")
+        with self.assertRaises(jc.JiraError):
+            self._post(opener)
+
     def test_a_redirect_is_never_followed_on_a_write(self):
         # _NoRedirect returns None for every 3xx, so urllib raises
         # instead of replaying the Authorization header (and the POST
         # body) to another origin.
         self.assertIsNone(jc._NoRedirect().redirect_request(
@@ -1145,10 +1157,36 @@ class TestRunCommentLane(unittest.TestCase):
         # The batch is not atomic: the first comment already landed
         # before the second failed, so the error names its marker
         # rather than silently dropping the fact that it was posted.
         self.assertIn(MARKER, str(ctx.exception))
 
+    def test_a_bare_timeout_on_the_second_post_still_names_the_first_marker(
+            self):
+        # A bare socket TimeoutError (not wrapped in a URLError) raised
+        # while reading the response to the second POST must still
+        # surface as a JiraError -- and, since the first comment already
+        # landed, name its marker -- rather than an unhandled traceback
+        # that hides the partial write from the operator. The real
+        # _http_post runs unmocked here (only the opener is faked) so
+        # this exercises _http_post's own OSError handling, not a stub.
+        first_resp = mock.MagicMock()
+        first_resp.read.return_value = b'{"id": "1"}'
+        first_resp.__enter__.return_value = first_resp
+        first_resp.__exit__.return_value = False
+        opener = mock.MagicMock()
+        opener.open.side_effect = [first_resp, TimeoutError("timed out")]
+        with ExitStack() as stack:
+            stack.enter_context(
+                mock.patch.dict(jc.os.environ, ENV, clear=True))
+            stack.enter_context(mock.patch.object(
+                jc, "_http_get", return_value=card_with([])))
+            stack.enter_context(mock.patch.object(jc, "_OPENER", opener))
+            with self.assertRaises(jc.JiraError) as ctx:
+                jc.run_comment_lane("ABC-1", self.entries, True)
+        self.assertEqual(opener.open.call_count, 2)
+        self.assertIn(MARKER, str(ctx.exception))
+
     def test_a_truncated_comment_sweep_refuses_before_any_post(self):
         # fetch_comments' fail-closed `total` guard is what makes dedupe
         # trustworthy: a page with no numeric total must abort the lane.
         body = json.dumps(
             {"startAt": 0, "maxResults": 100,
