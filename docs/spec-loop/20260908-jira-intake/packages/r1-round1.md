# Review package: b87574015f80d7de9d2bee6e63f6adec2d521c6d..spec-loop/20260908-jira-intake/r1  (context: -U5)

## Commits
9ab445e docs(coverage): correct the target count in the shim-pin comment
0c98b9a fix(jira): cite a valid issue key in the rejection message
57435c5 fix(jira): map a bare OSError on the GET path to JiraError

## Files changed
 plugins/spec-loop/scripts/jira_client.py      | 14 +++++++++-
 plugins/spec-loop/scripts/test_jira_client.py | 40 ++++++++++++++++++++++++++-
 scripts/test_measure_coverage_manifest.py     |  2 +-
 3 files changed, 53 insertions(+), 3 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/jira_client.py": [
[
111,
111
],
[
233,
244
]
],
"plugins/spec-loop/scripts/test_jira_client.py": [
[
74,
77
],
[
80,
87
],
[
280,
306
]
],
"scripts/test_measure_coverage_manifest.py": [
[
22,
22
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/jira_client.py b/plugins/spec-loop/scripts/jira_client.py
index 71dc3f4..e32a17e 100644
--- a/plugins/spec-loop/scripts/jira_client.py
+++ b/plugins/spec-loop/scripts/jira_client.py
@@ -106,11 +106,11 @@ def validate_issue_key(key):
     Rejects lowercase, path separators, a leading '-' (argument injection) and
     anything else outside ISSUE_KEY_RE."""
     if not ISSUE_KEY_RE.fullmatch(key or ""):
         raise JiraUsageError(
             f"invalid Jira issue key {key!r}: must match {ISSUE_KEY_RE.pattern} "
-            "(an uppercase project key, a hyphen, then digits -- e.g. A-1 or PROJ-42)"
+            "(an uppercase project key, a hyphen, then digits -- e.g. AB-1 or PROJ-42)"
         )
     return key
 
 
 def _split_base_url(raw):
@@ -228,10 +228,22 @@ def _http_get(url, email, token):
             return resp.read()
     except urllib.error.HTTPError as exc:
         raise JiraError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
     except urllib.error.URLError as exc:
         raise JiraError(f"network error fetching {url}: {exc.reason}") from exc
+    except OSError as exc:
+        # urllib only wraps an OSError raised by h.request() into a
+        # URLError (see CPython's AbstractHTTPHandler.do_open); an
+        # OSError out of h.getresponse() or resp.read() -- e.g. a
+        # timeout or a reset while reading a GET response --
+        # propagates unwrapped and would otherwise slip past the
+        # JiraError handling above and past main()'s exit-1 JSON
+        # contract as a raw traceback. Caught here, terminally, so
+        # every transport failure on the READ path is a JiraError too.
+        # Mirrors the identical guard on _http_post; the message names
+        # only the URL, so no credential can ride out in it.
+        raise JiraError(f"network error fetching {url}: {exc}") from exc
 
 
 def _http_post(url, email, token, payload):
     """HTTP POST of one JSON `payload` object through the same
     no-redirect opener. THE ONLY mutating entry point in this module.
diff --git a/plugins/spec-loop/scripts/test_jira_client.py b/plugins/spec-loop/scripts/test_jira_client.py
index 831ec7e..30d99df 100644
--- a/plugins/spec-loop/scripts/test_jira_client.py
+++ b/plugins/spec-loop/scripts/test_jira_client.py
@@ -69,13 +69,24 @@ class TestIssueKeyValidation(unittest.TestCase):
     def test_an_embedded_newline_is_rejected(self):
         with self.assertRaises(jc.JiraUsageError):
             jc.validate_issue_key("ABC-123\nrm -rf /")
 
     def test_the_rejection_message_names_the_expected_pattern(self):
+        # The message's own worked examples must be keys this function
+        # ACCEPTS. Asserting a bare substring is what let 'A-1' -- which
+        # ISSUE_KEY_RE rejects, since it requires two to ten characters
+        # before the hyphen -- sit in the message unchallenged.
         with self.assertRaises(jc.JiraUsageError) as ctx:
             jc.validate_issue_key("nope")
-        self.assertIn("A-1", str(ctx.exception))
+        message = str(ctx.exception)
+        self.assertIn("e.g. ", message)
+        tail = message.split("e.g. ", 1)[1].strip().rstrip(")")
+        examples = [part.strip() for part in tail.split(" or ")]
+        self.assertTrue(examples)
+        for example in examples:
+            with self.subTest(example=example):
+                self.assertEqual(jc.validate_issue_key(example), example)
 
 
 class TestBaseUrlValidation(unittest.TestCase):
     def test_an_allowed_https_host_returns_the_bare_origin(self):
         self.assertEqual(
@@ -264,10 +275,37 @@ class TestHttpGetIsReadOnly(unittest.TestCase):
         opener.open.side_effect = urllib.error.URLError("connection refused")
         with mock.patch.object(jc, "_OPENER", opener):
             with self.assertRaises(jc.JiraError):
                 jc._http_get("https://acme.atlassian.net/x", "fred@example.com", "tok")
 
+    def test_a_bare_timeout_reading_the_response_becomes_a_jira_error(self):
+        # urllib only wraps an OSError raised by h.request() into a
+        # URLError; a timeout or reset while READING the response to a
+        # GET raises a bare TimeoutError (a plain OSError subclass) out
+        # of h.getresponse()/resp.read() and propagates unwrapped. GET is
+        # the path every invocation takes, so an unmapped OSError here
+        # escapes main()'s exit-1 JSON contract as a raw traceback.
+        opener = mock.MagicMock()
+        opener.open.side_effect = TimeoutError("timed out")
+        with mock.patch.object(jc, "_OPENER", opener):
+            with self.assertRaises(jc.JiraError):
+                jc._http_get(
+                    "https://acme.atlassian.net/x", "fred@example.com", "tok")
+
+    def test_the_bare_oserror_message_leaks_no_credential(self):
+        email = "fred@example.com"
+        token = "s3cr3t-token"
+        pair = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
+        opener = mock.MagicMock()
+        opener.open.side_effect = ConnectionResetError("reset by peer")
+        with mock.patch.object(jc, "_OPENER", opener):
+            with self.assertRaises(jc.JiraError) as ctx:
+                jc._http_get("https://acme.atlassian.net/x", email, token)
+        message = str(ctx.exception)
+        for secret in (token, email, pair):
+            self.assertNotIn(secret, message)
+
 
 class TestHttpPostIsTheOnlyWriter(unittest.TestCase):
     """The plugin's FIRST mutating external call. It is a separate
     function from _http_get on purpose: the read lane's
     never-a-mutating-verb guarantee must survive unchanged."""
diff --git a/scripts/test_measure_coverage_manifest.py b/scripts/test_measure_coverage_manifest.py
index b64a890..90f3461 100644
--- a/scripts/test_measure_coverage_manifest.py
+++ b/scripts/test_measure_coverage_manifest.py
@@ -17,11 +17,11 @@ from pathlib import Path
 
 sys.path.insert(0, str(Path(__file__).resolve().parent))
 import measure_coverage as mc  # noqa: E402
 
 # Every shipped target's entry shim is a guard header plus a single-line body, so the
-# resolved omission is exactly this many lines. One pin covers all fourteen targets:
+# resolved omission is exactly this many lines. One pin covers all fifteen targets:
 # raising it relaxes every target at once, not just the one that grew.
 SHIPPED_SHIM_LINES = 2
 
 
 class ResolveMainShimTests(unittest.TestCase):
