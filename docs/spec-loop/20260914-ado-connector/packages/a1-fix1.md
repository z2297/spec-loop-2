# Review package: 4fcf416..0d2f84a  (context: -U5)

## Commits
0d2f84a fix(ado): cover the lazy-port ValueError path and guard non-string fields

## Files changed
 plugins/spec-loop/scripts/ado_client.py      | 19 ++++++++++++++++---
 plugins/spec-loop/scripts/test_ado_client.py | 20 ++++++++++++++++++++
 2 files changed, 36 insertions(+), 3 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/ado_client.py": [
[
897,
909
],
[
939,
941
]
],
"plugins/spec-loop/scripts/test_ado_client.py": [
[
110,
117
],
[
911,
922
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/ado_client.py b/plugins/spec-loop/scripts/ado_client.py
index d49f693..b1ce2a6 100644
--- a/plugins/spec-loop/scripts/ado_client.py
+++ b/plugins/spec-loop/scripts/ado_client.py
@@ -892,10 +892,23 @@ def _normalized(values):
             "field(s) " + ", ".join(empty)
             + " came back empty; refusing to emit a partial record")
     return record
 
 
+def _text_field(fields, key):
+    """Read a plain-string field (System.Title, System.WorkItemType or
+    System.State) the same way resolve_project reads System.TeamProject: a
+    non-string value (a malformed or malicious tenant response returning a
+    dict, list or number where the API contract promises a string) degrades
+    to '' rather than crashing .strip() with an unhandled AttributeError. The
+    empty result still flows through _normalized's REQUIRED_FIELDS check, so
+    a genuinely missing/wrong-shaped field still fails closed as an AdoError,
+    never a raw traceback. (PURE)"""
+    raw = fields.get(key)
+    return raw.strip() if isinstance(raw, str) else ""
+
+
 def resolve_work_item(work_item_id):
     """Resolve one Azure DevOps work-item id READ-ONLY to the normalized
     record. Credentials come from the environment (see credentials()); every
     call is fail-closed.
 
@@ -921,13 +934,13 @@ def resolve_work_item(work_item_id):
     record = _normalized({
         "org": org,
         "project": project,
         "id": resolved_id,
         "web_url": validate_web_url(href, api_root),
-        "title": (fields.get(FIELD_TITLE) or "").strip(),
-        "work_item_type": (fields.get(FIELD_TYPE) or "").strip(),
-        "state": (fields.get(FIELD_STATE) or "").strip(),
+        "title": _text_field(fields, FIELD_TITLE),
+        "work_item_type": _text_field(fields, FIELD_TYPE),
+        "state": _text_field(fields, FIELD_STATE),
         "description": description,
         "acceptance_criteria": criteria,
         "acceptance_criteria_source": source,
         "repro_steps": html_to_text(fields.get(FIELD_REPRO_STEPS)),
         "comments": [],
diff --git a/plugins/spec-loop/scripts/test_ado_client.py b/plugins/spec-loop/scripts/test_ado_client.py
index 1f65bda..9da2119 100644
--- a/plugins/spec-loop/scripts/test_ado_client.py
+++ b/plugins/spec-loop/scripts/test_ado_client.py
@@ -105,10 +105,18 @@ class TestOrgUrlValidation(unittest.TestCase):
 
     def test_a_malformed_ipv6_host_is_a_usage_error_not_a_traceback(self):
         with self.assertRaises(ac.AdoUsageError):
             ac.validate_org_url("https://[oops/contoso")
 
+    def test_an_unparsable_port_is_a_usage_error_not_a_traceback(self):
+        """urlsplit() itself does not raise on 'https://dev.azure.com:abc/x'
+        -- parts.port is computed LAZILY, so the ValueError only surfaces on
+        attribute access. _split_org_url forces that access; without it, this
+        would propagate as an uncaught ValueError instead of AdoUsageError."""
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_org_url("https://dev.azure.com:abc/contoso")
+
     def test_a_modern_url_with_no_org_segment_is_rejected(self):
         with self.assertRaises(ac.AdoUsageError):
             ac.validate_org_url("https://dev.azure.com")
 
     def test_an_extra_path_segment_after_the_org_is_rejected(self):
@@ -898,10 +906,22 @@ class TestResolveWorkItem(unittest.TestCase):
     def test_a_work_item_with_no_title_is_a_half_resolve(self):
         item = work_item(**{ac.FIELD_TITLE: ""})
         with self.assertRaises(ac.AdoError):
             self._resolve(item)
 
+    def test_a_non_string_title_type_or_state_is_a_half_resolve_not_a_crash(self):
+        """A malformed or malicious tenant response could return a dict, list
+        or number for a field the API contract promises is a string. Each
+        must degrade to '' and hit the REQUIRED_FIELDS half-resolve path as
+        an AdoError, never an unhandled AttributeError from a bare
+        .strip()."""
+        for field in (ac.FIELD_TITLE, ac.FIELD_TYPE, ac.FIELD_STATE):
+            with self.subTest(field=field):
+                item = work_item(**{field: {"unexpected": "shape"}})
+                with self.assertRaises(ac.AdoError):
+                    self._resolve(item)
+
     def test_the_id_is_validated_before_any_request(self):
         stack, read, _sweep = self._patched(work_item())
         with stack:
             with self.assertRaises(ac.AdoUsageError):
                 ac.resolve_work_item("../../etc/passwd")
