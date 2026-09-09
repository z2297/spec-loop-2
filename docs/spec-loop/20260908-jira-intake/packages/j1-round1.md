# Review package: 5bf313aade526424b196814d25cf2c3aa5a9d364..07faa13  (context: -U5)

## Commits
07faa13 chore(coverage): gate jira_client.py and update the runtime script inventory
db6459a feat(jira): normalized record, resolve_issue orchestration and CLI entry point
e6cca3c feat(jira): paginated comment sweep with a runaway guard
843ef6b feat(jira): issue fetch with acceptance-criteria field lookup and fallback
574e3c5 feat(jira): lossy ADF-to-plain-text renderer
6c54d30 feat(jira): env-only credentials, Basic auth, and a no-redirect read-only GET
9404ad6 feat(jira): issue-key and base-URL validation for the read lane

## Files changed
 plugins/spec-loop/README.md                   |   6 +-
 plugins/spec-loop/scripts/jira_client.py      | 511 +++++++++++++++++
 plugins/spec-loop/scripts/test_jira_client.py | 781 ++++++++++++++++++++++++++
 scripts/coverage_omit.txt                     |   1 +
 scripts/measure_coverage.py                   |   2 +
 scripts/test_measure_coverage_manifest.py     |   2 +-
 6 files changed, 1299 insertions(+), 4 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/README.md": [
[
164,
166
]
],
"plugins/spec-loop/scripts/jira_client.py": [
[
1,
511
]
],
"plugins/spec-loop/scripts/test_jira_client.py": [
[
1,
781
]
],
"scripts/coverage_omit.txt": [
[
37,
37
]
],
"scripts/measure_coverage.py": [
[
105,
105
],
[
146,
146
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
diff --git a/plugins/spec-loop/README.md b/plugins/spec-loop/README.md
index e5a5443..e5207d2 100644
--- a/plugins/spec-loop/README.md
+++ b/plugins/spec-loop/README.md
@@ -159,13 +159,13 @@ sidecar closed rather than reading as clean.
 - **Agents (13)**: slice-planner, plan-critic, guardian, skeptic,
   implementer, pr-reviewer, finding-verifier, re-reviewer, simplifier,
   verifier, runbook-writer, peer-reviewer, slice-worker-fallback.
 - **Skills (5)**: escalation-gate, using-spec-loop, test-driven-development,
   systematic-debugging, verification-before-completion.
-- **Scripts (11 runtime + tests)**: dag, worktrees, run_state, review_package,
-  quality_gate, knowledge_graph, run_metrics, pr_resolver, spec_loop_guard,
-  dashboard_server, dashboard_launcher (+ dashboard_assets, and the
+- **Scripts (12 runtime + tests)**: dag, worktrees, run_state, review_package,
+  quality_gate, knowledge_graph, run_metrics, pr_resolver, jira_client,
+  spec_loop_guard, dashboard_server, dashboard_launcher (+ dashboard_assets, and the
   `slice_wave_contract_base` and `slice_wave_contract_radius_driver`
   test-support modules, which back four Node harness modules:
   `slice_wave_behaviour`, `slice_wave_radius`, `slice_wave_radius_partial`
   and `slice_wave_replan`).
 
diff --git a/plugins/spec-loop/scripts/jira_client.py b/plugins/spec-loop/scripts/jira_client.py
new file mode 100644
index 0000000..010b3fd
--- /dev/null
+++ b/plugins/spec-loop/scripts/jira_client.py
@@ -0,0 +1,511 @@
+#!/usr/bin/env python3
+"""Read-only Jira Cloud issue reader (standard library only).
+
+Resolves one Jira issue key to a normalized JSON record (key, summary,
+description, acceptance criteria, status, issue type, web url, and the full
+paginated comment list), authenticating with HTTP Basic auth built from
+JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN. It never mutates a Jira issue.
+
+Design decisions:
+  - Mirrors plugins/spec-loop/scripts/pr_resolver.py's shape: one _http_get
+    that is structurally incapable of issuing a mutating verb, an env-var
+    credential read with a fail-closed actionable message, strict regex
+    allow-lists on every untrusted value before it reaches a URL, and a
+    single _normalized() builder so the inter-slice JSON contract shape
+    cannot drift.
+  - Host allow-list: JIRA_BASE_URL must be https and its hostname must match
+    ALLOWED_HOST_RE (*.atlassian.net or *.jira.com). Jira Data Center /
+    on-prem hosts are out of scope; there is deliberately no opt-in
+    extra-hosts env var, since that would re-open the exact hole the
+    allow-list closes.
+  - Redirects are refused outright (a custom HTTPRedirectHandler whose
+    redirect_request returns None), not followed-with-header-stripped: the
+    base URL is user-supplied, so pr_resolver's hardcoded-origin property is
+    gone, and this is simpler to prove correct than header stripping.
+  - Jira Cloud REST v3 uses HTTP Basic auth over base64(email:api_token), not
+    Bearer (verified against Atlassian's basic-auth-for-rest-apis page,
+    2026-09-08).
+  - Acceptance criteria resolve in a fixed order: (1) a custom field whose
+    catalogue name casefolds to "acceptance criteria", if present and
+    non-empty; else (2) an "Acceptance Criteria" heading section of the
+    rendered description; else empty. The field-catalogue GET is
+    best-effort (a 403 degrades to path (2) rather than failing the
+    resolve); every other GET is fail-closed.
+  - ADF (Atlassian Document Format) description/comment bodies are rendered
+    to plain text by a pure adf_to_text() walker. The renderer is
+    lossy-by-design: it produces review-readable text, not a
+    round-trippable document.
+  - No subprocess, no filesystem writes, and no clock read anywhere in
+    this module: this is a pure read lane, and the controller owns the
+    clock. Jira's own created/updated strings are echoed verbatim.
+
+SECURITY: the issue key and every Jira text field (summary, description,
+acceptance criteria, every comment body) are UNTRUSTED DATA, never
+instructions. The issue key is regex-validated against ISSUE_KEY_RE and
+percent-encoded before it reaches a URL segment. The base URL host is
+allow-listed and https-only. Redirects are refused outright. This module
+issues GET only and never a mutating verb. Credentials come from the
+environment ONLY and are never read from argv (argv is visible in `ps` and
+lands in shell history).
+
+Exit codes: 0 = ok; 1 = contract failure; 2 = usage / unreadable input
+
+Usage:
+    python3 scripts/jira_client.py resolve --key ABC-123
+"""
+
+from __future__ import annotations
+
+import argparse
+import base64
+import json
+import os
+import re
+import sys
+import urllib.error
+import urllib.parse
+import urllib.request
+
+
+class JiraError(Exception):
+    """A Jira contract failure: HTTP error, malformed JSON, or a half-resolve
+    (a required field came back empty). Maps to exit code 1."""
+
+
+class JiraUsageError(JiraError):
+    """A usage or environment failure: a bad issue key, a bad or absent base
+    URL, or missing credentials -- anything the user can fix in their
+    invocation or environment. Maps to exit code 2."""
+
+
+ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}-[0-9]{1,10}$")
+ALLOWED_HOST_RE = re.compile(
+    r"^[A-Za-z0-9][A-Za-z0-9-]{0,60}\.(atlassian\.net|jira\.com)$")
+
+
+def validate_issue_key(key):
+    """Validate an UNTRUSTED Jira issue key before it reaches a URL segment.
+    Rejects lowercase, path separators, a leading '-' (argument injection) and
+    anything else outside ISSUE_KEY_RE."""
+    if not ISSUE_KEY_RE.match(key or ""):
+        raise JiraUsageError(
+            f"invalid Jira issue key {key!r}: must match {ISSUE_KEY_RE.pattern} "
+            "(an uppercase project key, a hyphen, then digits -- e.g. A-1 or PROJ-42)"
+        )
+    return key
+
+
+def validate_base_url(raw):
+    """Validate an UNTRUSTED JIRA_BASE_URL and return its normalized bare
+    origin (scheme + host only -- no trailing slash, no path/query/fragment).
+    Discarding the path is deliberate: every API path in this module is
+    composed from this origin plus a literal /rest/api/3/... prefix. Requires
+    https, rejects embedded userinfo (userinfo smuggling) or an explicit
+    port, and requires the hostname to match ALLOWED_HOST_RE."""
+    parts = urllib.parse.urlsplit(raw or "")
+    ok = (
+        parts.scheme == "https"
+        and not parts.username
+        and not parts.password
+        and not parts.port
+        and ALLOWED_HOST_RE.match(parts.hostname or "")
+    )
+    if not ok:
+        raise JiraUsageError(
+            f"invalid JIRA_BASE_URL {raw!r}: must be an https URL on a "
+            "*.atlassian.net or *.jira.com host (e.g. https://your-site.atlassian.net)"
+        )
+    return f"https://{parts.hostname.lower()}"
+
+
+class _NoRedirect(urllib.request.HTTPRedirectHandler):
+    """Refuse every 3xx. The base URL is user-supplied, so pr_resolver's
+    hardcoded-origin property is gone: following a redirect could replay the
+    Authorization header to another origin. Returning None makes urllib raise
+    the HTTPError instead of following it."""
+
+    def redirect_request(self, req, fp, code, msg, headers, newurl):
+        """Return None so urllib treats the 3xx as a terminal error."""
+        return None
+
+
+_OPENER = urllib.request.build_opener(_NoRedirect)
+
+CRED_VARS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
+
+
+def credentials():
+    """Read the Jira credentials from the ENVIRONMENT ONLY and fail closed with
+    an actionable message when any is unset. Never read from argv: argv is
+    visible in `ps` and lands in shell history."""
+    values = {name: (os.environ.get(name) or "").strip() for name in CRED_VARS}
+    missing = [name for name in CRED_VARS if not values[name]]
+    if missing:
+        raise JiraUsageError(
+            "Jira access requires the environment variable(s) "
+            + ", ".join(missing)
+            + ". Set JIRA_BASE_URL to your site origin (e.g. "
+            "https://your-site.atlassian.net), JIRA_EMAIL to your Atlassian "
+            "account email, and JIRA_API_TOKEN to an API token created at "
+            "https://id.atlassian.com/manage-profile/security/api-tokens. "
+            "Pass them in the environment, never on the command line."
+        )
+    return (validate_base_url(values["JIRA_BASE_URL"]),
+            values["JIRA_EMAIL"], values["JIRA_API_TOKEN"])
+
+
+def _auth_header(email, token):
+    """Build the Jira Cloud Basic auth header: base64("email:api_token").
+    Verified against Atlassian's basic-auth-for-rest-apis page (2026-09-08) --
+    Jira Cloud REST v3 uses Basic with an API token, NOT Bearer."""
+    raw = f"{email}:{token}".encode("utf-8")
+    return "Basic " + base64.b64encode(raw).decode("ascii")
+
+
+def _http_get(url, email, token):
+    """HTTP GET via the no-redirect opener (READ-ONLY: never sets a body and
+    never a mutating method). The sole network entry point in this module.
+    Errors reference only the URL -- the credentials ride in a header, so
+    neither the token, the email, nor the composed base64 pair can appear in an
+    exception message."""
+    req = urllib.request.Request(
+        url,
+        headers={"Authorization": _auth_header(email, token),
+                 "Accept": "application/json"},
+        method="GET",
+    )
+    try:
+        with _OPENER.open(req, timeout=30) as resp:
+            return resp.read()
+    except urllib.error.HTTPError as exc:
+        raise JiraError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
+    except urllib.error.URLError as exc:
+        raise JiraError(f"network error fetching {url}: {exc.reason}") from exc
+
+
+def _parse_json(raw, what):
+    """json.loads with an actionable JiraError, so a malformed response fails
+    with a clear message rather than a raw traceback."""
+    try:
+        return json.loads(raw)
+    except json.JSONDecodeError as exc:
+        raise JiraError(
+            f"Jira returned a {what} response that is not valid JSON ({exc})"
+        ) from exc
+
+
+_ADF_MAX_DEPTH = 50
+_ADF_INLINE_TYPES = ("text", "hardBreak", "mention", "inlineCard")
+
+
+def _adf_inline(node, depth):
+    """Render a node's inline children into one string: 'text' nodes render
+    their text, 'hardBreak' becomes a newline, 'mention' renders
+    '@<attrs.text>' (attrs.text already carries the '@' from Jira, so it is
+    used as-is when present), and 'inlineCard' renders attrs.url. Any other
+    child falls back to _adf_block, so an inline node with an unexpected
+    nested block still contributes its rendered text instead of vanishing."""
+    if depth > _ADF_MAX_DEPTH:
+        return ""
+    parts = []
+    for child in node.get("content") or []:
+        ctype = child.get("type")
+        if ctype == "text":
+            parts.append(child.get("text", ""))
+        elif ctype == "hardBreak":
+            parts.append("\n")
+        elif ctype == "mention":
+            text = (child.get("attrs") or {}).get("text", "")
+            parts.append(text if text.startswith("@") else f"@{text}")
+        elif ctype == "inlineCard":
+            parts.append((child.get("attrs") or {}).get("url", ""))
+        else:
+            parts.append(_adf_block(child, depth + 1))
+    return "".join(parts)
+
+
+def _adf_block(node, depth):
+    """Render one ADF block node to plain text, guarded against pathological
+    nesting: at depth > 50 this returns '' and stops recursing rather than
+    blowing the stack. 'heading' renders '#' * level + ' ' + text;
+    'bulletList' / 'orderedList' items render '- ' / '1. '-prefixed lines
+    joined by a single newline; 'listItem' joins its own blocks with a single
+    newline; 'codeBlock' renders fenced with triple backticks; anything else
+    (including an unrecognized future node type) either renders as inline
+    text, when every child is an inline node type, or as a blank-line-joined
+    sequence of child blocks otherwise -- so an unknown node type still
+    renders its children instead of disappearing."""
+    if depth > _ADF_MAX_DEPTH:
+        return ""
+    ntype = node.get("type")
+    if ntype == "heading":
+        level = (node.get("attrs") or {}).get("level", 1)
+        return "#" * level + " " + _adf_inline(node, depth)
+    if ntype == "codeBlock":
+        return "```\n" + _adf_inline(node, depth) + "\n```"
+    if ntype == "listItem":
+        blocks = [_adf_block(child, depth + 1) for child in node.get("content") or []]
+        return "\n".join(blocks)
+    if ntype == "bulletList":
+        items = [_adf_block(child, depth + 1) for child in node.get("content") or []]
+        return "\n".join(f"- {item}" for item in items)
+    if ntype == "orderedList":
+        items = [_adf_block(child, depth + 1) for child in node.get("content") or []]
+        return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))
+    if ntype == "paragraph":
+        return _adf_inline(node, depth)
+    children = node.get("content") or []
+    if children and all(c.get("type") in _ADF_INLINE_TYPES for c in children):
+        return _adf_inline(node, depth)
+    rendered = [_adf_block(child, depth + 1) for child in children]
+    return "\n\n".join(rendered)
+
+
+def adf_to_text(node):
+    """Render an Atlassian Document Format document (or None, or a plain
+    string -- both occur in the wild in Jira description/comment bodies) to
+    plain, review-readable text. This renderer is LOSSY BY DESIGN: it
+    produces text for humans to read, not a document that round-trips back
+    into ADF. Blocks are joined with a blank line and the result is
+    stripped of trailing whitespace."""
+    if not node:
+        return ""
+    if isinstance(node, str):
+        return node
+    blocks = [_adf_block(child, 0) for child in node.get("content") or []]
+    return "\n\n".join(blocks).strip()
+
+
+ISSUE_FIELDS = ("summary", "description", "status", "issuetype")
+AC_FIELD_NAME = "acceptance criteria"
+AC_HEADING_RE = re.compile(
+    r"^\s{0,3}#{1,6}\s*acceptance\s+criteria\s*:?\s*$", re.IGNORECASE)
+ANY_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
+
+
+def _issue_url(base_url, key):
+    """Compose the REST v3 issue URL for one key. The key has already been
+    validated against ISSUE_KEY_RE by the caller, and is percent-encoded here
+    anyway: defence in depth, per the run constraint that an untrusted id is
+    encoded regardless before it reaches a URL segment."""
+    return f"{base_url}/rest/api/3/issue/{urllib.parse.quote(key, safe='')}"
+
+
+def find_ac_field_id(base_url, email, token):
+    """Locate the id of the custom field whose catalogue display name casefolds
+    to AC_FIELD_NAME, via GET /rest/api/3/field. Returns None when no such
+    field exists, when the payload is not the documented flat array, or when
+    the call fails.
+
+    This is the ONE best-effort call in the module -- every other GET is
+    fail-closed. A 403 here is common on locked-down sites (the field
+    catalogue is an admin-adjacent read), the acceptance criteria have a
+    defined description fallback, and the winner is recorded in the record's
+    acceptance_criteria_source, so degrading to None is not a half-resolve."""
+    try:
+        raw = _http_get(f"{base_url}/rest/api/3/field", email, token)
+        catalogue = _parse_json(raw.decode("utf-8"), "field catalogue")
+    except JiraError:
+        return None
+    if not isinstance(catalogue, list):
+        return None
+    for entry in catalogue:
+        # A non-object entry is malformed; skip it rather than raising, since
+        # this whole lookup degrades to None instead of failing the resolve.
+        if not isinstance(entry, dict):
+            continue
+        if (entry.get("name") or "").strip().casefold() == AC_FIELD_NAME:
+            return entry.get("id") or None
+    return None
+
+
+def fetch_issue(base_url, email, token, key, ac_field_id):
+    """GET the raw IssueBean for one issue key, requesting ISSUE_FIELDS plus
+    the acceptance-criteria custom field when one was located. The key is
+    validated BEFORE any request is issued, so a malformed key never reaches
+    the network. Fail-closed: an HTTP error or a malformed body raises."""
+    validate_issue_key(key)
+    fields = list(ISSUE_FIELDS) + ([ac_field_id] if ac_field_id else [])
+    query = urllib.parse.urlencode({"fields": ",".join(fields)})
+    url = f"{_issue_url(base_url, key)}?{query}"
+    return _parse_json(_http_get(url, email, token).decode("utf-8"), "issue")
+
+
+def acceptance_criteria_from_description(text):
+    """Extract the section under an 'Acceptance Criteria' heading from ALREADY
+    RENDERED description text. The heading match is case-insensitive and
+    tolerates a trailing colon; the section runs to the next heading of any
+    level, or to the end of the text. Returns '' when no such heading is
+    present."""
+    lines = (text or "").splitlines()
+    collected = []
+    inside = False
+    for line in lines:
+        if inside:
+            if ANY_HEADING_RE.match(line):
+                break
+            collected.append(line)
+        elif AC_HEADING_RE.match(line):
+            inside = True
+    return "\n".join(collected).strip()
+
+
+def resolve_acceptance_criteria(issue, ac_field_id, description_text):
+    """Resolve the acceptance criteria in the fixed two-step order and report
+    which source won: the custom field named in the catalogue when it exists
+    and renders non-empty ('field'), else the description's 'Acceptance
+    Criteria' section ('description'), else ('', ''). Recording the source is
+    what makes the best-effort catalogue lookup safe -- a reader can always
+    tell where the text came from."""
+    if ac_field_id:
+        raw = (issue.get("fields") or {}).get(ac_field_id)
+        # Only an ADF document or a plain string is renderable. A field of
+        # some other shape (a multi-select array, a number) is not acceptance
+        # criteria text, so it degrades to the description fallback rather
+        # than crashing the resolve.
+        rendered = adf_to_text(raw).strip() if isinstance(raw, (str, dict)) else ""
+        if rendered:
+            return (rendered, "field")
+    from_description = acceptance_criteria_from_description(description_text)
+    if from_description:
+        return (from_description, "description")
+    return ("", "")
+
+
+COMMENT_PAGE_SIZE = 100
+MAX_COMMENT_PAGES = 100
+
+
+def fetch_comments(base_url, email, token, key):
+    """GET the FULL, paginated comment list for one issue key via a
+    startAt-paginated sweep of /rest/api/3/issue/{key}/comment, normalized to
+    [{"id", "author", "created", "updated", "body"}, ...] in server order.
+
+    Verified against Atlassian's REST v3 docs (2026-09-08): the server default
+    maxResults is 50, so a single unpaginated GET silently truncates a chatty
+    card and would defeat comment-based dedupe downstream. This sweep asks for
+    COMMENT_PAGE_SIZE per page and keeps requesting until the accumulated
+    count reaches the page's reported `total`, or a page comes back empty
+    (guarding against a `total` that lies). MAX_COMMENT_PAGES bounds a
+    runaway/misbehaving server so this cannot loop forever.
+
+    The key is validated BEFORE any request is issued. A page missing the
+    `comments` list (the REST v3 shape; NOT `values`, which belongs to the
+    unrelated POST /rest/api/3/comment/list endpoint) raises rather than
+    silently degrading to "no comments" -- swallowing a shape change here
+    would silently defeat dedupe on a chatty card."""
+    validate_issue_key(key)
+    comments = []
+    start = 0
+    base = f"{_issue_url(base_url, key)}/comment"
+    for _ in range(MAX_COMMENT_PAGES):
+        query = urllib.parse.urlencode(
+            {"startAt": start, "maxResults": COMMENT_PAGE_SIZE})
+        url = f"{base}?{query}"
+        page = _parse_json(
+            _http_get(url, email, token).decode("utf-8"), "comment page")
+        page_comments = page.get("comments") if isinstance(page, dict) else None
+        if not isinstance(page_comments, list):
+            raise JiraError(
+                "Jira comment page is missing the 'comments' list; cannot "
+                "read the full comment history")
+        for c in page_comments:
+            comments.append({
+                "id": str(c.get("id") or ""),
+                "author": ((c.get("author") or {}).get("displayName") or ""),
+                "created": c.get("created") or "",
+                "updated": c.get("updated") or "",
+                "body": adf_to_text(c.get("body")),
+            })
+        if not page_comments or len(comments) >= int(page.get("total") or 0):
+            return comments
+        start += len(page_comments)
+    raise JiraError(
+        f"comment pagination did not terminate after {MAX_COMMENT_PAGES} "
+        f"pages for {key}; refusing a possibly-truncated comment history")
+
+
+RECORD_FIELDS = ("key", "web_url", "summary", "description",
+                 "acceptance_criteria", "acceptance_criteria_source",
+                 "status", "issue_type", "comments")
+REQUIRED_FIELDS = ("key", "web_url", "summary", "status", "issue_type")
+
+
+def _normalized(values):
+    """Build the inter-slice record in RECORD_FIELDS order -- the single source
+    of truth for the JSON contract shape, so it cannot drift between callers.
+    An empty REQUIRED_FIELDS entry means the API response was incomplete: that
+    is a half-resolve and raises, because a partial record must never be
+    emitted as if it were a whole one. description, acceptance_criteria,
+    acceptance_criteria_source and an empty comments list are all legitimately
+    empty."""
+    record = {name: values[name] for name in RECORD_FIELDS}
+    empty = [name for name in REQUIRED_FIELDS if not record[name]]
+    if empty:
+        raise JiraError(
+            "Jira returned an incomplete issue: the required field(s) "
+            + ", ".join(empty)
+            + " came back empty; refusing to emit a partial record")
+    return record
+
+
+def resolve_issue(key):
+    """Resolve one Jira issue key READ-ONLY to the normalized record.
+    Credentials come from the environment (see credentials()); the field
+    catalogue lookup is best effort, every other call is fail-closed."""
+    base_url, email, token = credentials()
+    key = validate_issue_key(key)
+    ac_field_id = find_ac_field_id(base_url, email, token)
+    issue = fetch_issue(base_url, email, token, key, ac_field_id)
+    fields = issue.get("fields") or {}
+    resolved_key = issue.get("key") or key
+    description = adf_to_text(fields.get("description"))
+    criteria, source = resolve_acceptance_criteria(issue, ac_field_id, description)
+    return _normalized({
+        "key": resolved_key,
+        "web_url": f"{base_url}/browse/"
+                   f"{urllib.parse.quote(validate_issue_key(resolved_key), safe='')}",
+        "summary": fields.get("summary") or "",
+        "description": description,
+        "acceptance_criteria": criteria,
+        "acceptance_criteria_source": source,
+        "status": (fields.get("status") or {}).get("name") or "",
+        "issue_type": (fields.get("issuetype") or {}).get("name") or "",
+        "comments": fetch_comments(base_url, email, token, resolved_key),
+    })
+
+
+def build_parser():
+    """Build the CLI parser: one read-only subcommand, `resolve --key`. There
+    is deliberately no credential flag -- credentials are read from the
+    environment only, never from argv."""
+    parser = argparse.ArgumentParser(
+        description="Read-only Jira Cloud issue reader.")
+    sub = parser.add_subparsers(dest="command", required=True)
+    resolve = sub.add_parser(
+        "resolve", help="Resolve one issue key to a normalized JSON record.")
+    resolve.add_argument("--key", required=True,
+                         help="Jira issue key, e.g. ABC-123.")
+    return parser
+
+
+def main(argv=None):
+    """Parse args, resolve, print one JSON object. Exit 0 ok, 1 contract
+    failure, 2 usage / unreadable input. JiraUsageError is caught BEFORE
+    JiraError: it subclasses JiraError, so the reverse order would collapse
+    exit 2 into exit 1."""
+    args = build_parser().parse_args(argv)
+    try:
+        record = resolve_issue(args.key)
+    except JiraUsageError as exc:
+        print(json.dumps({"ok": False, "errors": [str(exc)]}), file=sys.stderr)
+        return 2
+    except JiraError as exc:
+        print(json.dumps({"ok": False, "errors": [str(exc)]}), file=sys.stderr)
+        return 1
+    print(json.dumps(record, ensure_ascii=False, indent=2))
+    return 0
+
+
+if __name__ == "__main__":
+    sys.exit(main())
diff --git a/plugins/spec-loop/scripts/test_jira_client.py b/plugins/spec-loop/scripts/test_jira_client.py
new file mode 100644
index 0000000..800a1ae
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_jira_client.py
@@ -0,0 +1,781 @@
+#!/usr/bin/env python3
+"""Tests for the read-only Jira Cloud issue reader (stdlib unittest).
+
+Covers issue-key and base-URL validation (allow-list + argument/URL-injection
+defence), credential resolution and its fail-closed message, the ADF -> text
+renderer, issue and paginated-comment resolution against a mocked urlopen, the
+normalized-record contract, that the API token / account email / composed
+base64(email:token) never leak into an error, stdout or stderr, and the
+READ-ONLY guarantee (every urllib Request is a GET; the module spawns no
+subprocess).
+
+`scripts/validate_marketplace.py` does NOT lint scripts/*.py, so this is the
+sole automated guard on the client. Standard library only. No live network.
+
+Usage:
+    python3 -m unittest test_jira_client
+"""
+
+import base64
+import json
+import sys
+import unittest
+import urllib.error
+from pathlib import Path
+from unittest import mock
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+import jira_client as jc  # noqa: E402
+
+
+class TestIssueKeyValidation(unittest.TestCase):
+    def test_a_well_formed_key_is_returned_unchanged(self):
+        self.assertEqual(jc.validate_issue_key("ABC-123"), "ABC-123")
+
+    def test_a_single_letter_project_with_digits_is_accepted(self):
+        self.assertEqual(jc.validate_issue_key("A1B2-7"), "A1B2-7")
+
+    def test_lowercase_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_issue_key("abc-123")
+
+    def test_a_path_traversal_attempt_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_issue_key("../../etc/passwd")
+
+    def test_a_leading_dash_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_issue_key("-ABC-1")
+
+    def test_an_embedded_slash_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_issue_key("ABC-1/comment")
+
+    def test_an_empty_key_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_issue_key("")
+
+    def test_the_rejection_message_names_the_expected_pattern(self):
+        with self.assertRaises(jc.JiraUsageError) as ctx:
+            jc.validate_issue_key("nope")
+        self.assertIn("A-1", str(ctx.exception))
+
+
+class TestBaseUrlValidation(unittest.TestCase):
+    def test_an_allowed_https_host_returns_the_bare_origin(self):
+        self.assertEqual(
+            jc.validate_base_url("https://acme.atlassian.net/"),
+            "https://acme.atlassian.net")
+
+    def test_a_path_on_the_base_url_is_discarded(self):
+        self.assertEqual(
+            jc.validate_base_url("https://acme.atlassian.net/jira/software"),
+            "https://acme.atlassian.net")
+
+    def test_the_jira_com_suffix_is_allowed(self):
+        self.assertEqual(
+            jc.validate_base_url("https://acme.jira.com"),
+            "https://acme.jira.com")
+
+    def test_http_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_base_url("http://acme.atlassian.net")
+
+    def test_an_unlisted_host_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_base_url("https://evil.example.com")
+
+    def test_a_lookalike_suffix_host_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_base_url("https://evil-atlassian.net")
+
+    def test_a_subdomain_of_an_attacker_domain_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_base_url("https://acme.atlassian.net.evil.com")
+
+    def test_userinfo_smuggling_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_base_url("https://acme.atlassian.net@evil.com/")
+
+    def test_an_empty_base_url_is_rejected(self):
+        with self.assertRaises(jc.JiraUsageError):
+            jc.validate_base_url("")
+
+
+class TestCredentials(unittest.TestCase):
+    ENV = {
+        "JIRA_BASE_URL": "https://acme.atlassian.net",
+        "JIRA_EMAIL": "fred@example.com",
+        "JIRA_API_TOKEN": "s3cr3t-api-token",
+    }
+
+    def test_all_three_present_returns_the_validated_triple(self):
+        with mock.patch.dict(jc.os.environ, self.ENV, clear=True):
+            self.assertEqual(
+                jc.credentials(),
+                ("https://acme.atlassian.net", "fred@example.com", "s3cr3t-api-token"))
+
+    def test_a_trailing_slash_base_url_is_normalized(self):
+        env = dict(self.ENV, JIRA_BASE_URL="https://acme.atlassian.net/")
+        with mock.patch.dict(jc.os.environ, env, clear=True):
+            self.assertEqual(jc.credentials()[0], "https://acme.atlassian.net")
+
+    def test_each_missing_variable_is_named_in_the_message(self):
+        for missing in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
+            env = {k: v for k, v in self.ENV.items() if k != missing}
+            with self.subTest(missing=missing):
+                with mock.patch.dict(jc.os.environ, env, clear=True):
+                    with self.assertRaises(jc.JiraUsageError) as ctx:
+                        jc.credentials()
+                self.assertIn(missing, str(ctx.exception))
+
+    def test_all_three_missing_names_all_three(self):
+        with mock.patch.dict(jc.os.environ, {}, clear=True):
+            with self.assertRaises(jc.JiraUsageError) as ctx:
+                jc.credentials()
+        for name in self.ENV:
+            self.assertIn(name, str(ctx.exception))
+
+    def test_an_empty_value_counts_as_unset(self):
+        env = dict(self.ENV, JIRA_API_TOKEN="")
+        with mock.patch.dict(jc.os.environ, env, clear=True):
+            with self.assertRaises(jc.JiraUsageError):
+                jc.credentials()
+
+    def test_the_message_says_how_to_fix_it(self):
+        with mock.patch.dict(jc.os.environ, {}, clear=True):
+            with self.assertRaises(jc.JiraUsageError) as ctx:
+                jc.credentials()
+        self.assertIn("id.atlassian.com", str(ctx.exception))
+
+
+class TestAuthHeader(unittest.TestCase):
+    def test_scheme_is_basic_over_base64_of_email_colon_token(self):
+        header = jc._auth_header("fred@example.com", "tok")
+        expected = base64.b64encode(b"fred@example.com:tok").decode("ascii")
+        self.assertEqual(header, "Basic " + expected)
+
+    def test_it_is_not_bearer(self):
+        self.assertNotIn("Bearer", jc._auth_header("a@b.c", "tok"))
+
+    def test_non_ascii_credentials_encode_as_utf8(self):
+        header = jc._auth_header("frédé@example.com", "tok")
+        expected = base64.b64encode("frédé@example.com:tok".encode("utf-8")).decode("ascii")
+        self.assertEqual(header, "Basic " + expected)
+
+
+class TestHttpGetIsReadOnly(unittest.TestCase):
+    def _fake_opener(self, payload=b"{}"):
+        resp = mock.MagicMock()
+        resp.read.return_value = payload
+        resp.__enter__.return_value = resp
+        resp.__exit__.return_value = False
+        opener = mock.MagicMock()
+        opener.open.return_value = resp
+        return opener
+
+    def test_the_request_method_is_get(self):
+        opener = self._fake_opener()
+        with mock.patch.object(jc, "_OPENER", opener):
+            jc._http_get("https://acme.atlassian.net/rest/api/3/field",
+                         "fred@example.com", "tok")
+        req = opener.open.call_args.args[0]
+        self.assertEqual(req.get_method(), "GET")
+
+    def test_the_request_carries_no_body(self):
+        opener = self._fake_opener()
+        with mock.patch.object(jc, "_OPENER", opener):
+            jc._http_get("https://acme.atlassian.net/rest/api/3/field",
+                         "fred@example.com", "tok")
+        self.assertIsNone(opener.open.call_args.args[0].data)
+
+    def test_the_authorization_header_is_basic(self):
+        opener = self._fake_opener()
+        with mock.patch.object(jc, "_OPENER", opener):
+            jc._http_get("https://acme.atlassian.net/rest/api/3/field",
+                         "fred@example.com", "tok")
+        req = opener.open.call_args.args[0]
+        self.assertTrue(req.get_header("Authorization").startswith("Basic "))
+
+    def _http_error(self, url, code, reason):
+        """A closed-on-teardown HTTPError. HTTPError owns an internal file
+        object; closing it avoids a ResourceWarning at GC time (mirrors
+        test_pr_resolver.py's helper of the same name)."""
+        err = urllib.error.HTTPError(url, code, reason, {}, None)
+        self.addCleanup(err.close)
+        return err
+
+    def test_an_http_error_becomes_an_actionable_jira_error(self):
+        err = self._http_error("https://acme.atlassian.net/x", 404, "Not Found")
+        opener = mock.MagicMock()
+        opener.open.side_effect = err
+        with mock.patch.object(jc, "_OPENER", opener):
+            with self.assertRaises(jc.JiraError) as ctx:
+                jc._http_get("https://acme.atlassian.net/x", "fred@example.com", "tok")
+        self.assertIn("404", str(ctx.exception))
+
+    def test_a_network_error_becomes_a_jira_error(self):
+        opener = mock.MagicMock()
+        opener.open.side_effect = urllib.error.URLError("connection refused")
+        with mock.patch.object(jc, "_OPENER", opener):
+            with self.assertRaises(jc.JiraError):
+                jc._http_get("https://acme.atlassian.net/x", "fred@example.com", "tok")
+
+
+class TestRedirectsAreRefused(unittest.TestCase):
+    def test_the_redirect_handler_returns_none(self):
+        handler = jc._NoRedirect()
+        self.assertIsNone(handler.redirect_request(
+            mock.MagicMock(), mock.MagicMock(), 302, "Found", {},
+            "https://evil.example.com/"))
+
+    def test_the_module_opener_installs_the_no_redirect_handler(self):
+        self.assertTrue(any(isinstance(h, jc._NoRedirect)
+                            for h in jc._OPENER.handlers))
+
+
+class TestParseJson(unittest.TestCase):
+    def test_valid_json_round_trips(self):
+        self.assertEqual(jc._parse_json('{"a": 1}', "issue"), {"a": 1})
+
+    def test_malformed_json_raises_an_actionable_jira_error(self):
+        with self.assertRaises(jc.JiraError) as ctx:
+            jc._parse_json("not json", "issue")
+        self.assertIn("issue", str(ctx.exception))
+
+
+class TestSecretsNeverLeak(unittest.TestCase):
+    """Mirrors and extends test_pr_resolver.py::TestTokenNeverLeaks: the raw
+    token, the account email, AND the composed base64(email:token) must each be
+    absent from the exception text, stdout and stderr."""
+
+    TOKEN = "s3cr3t-api-token-value"
+    EMAIL = "fred@example.com"
+    ENV = {
+        "JIRA_BASE_URL": "https://acme.atlassian.net",
+        "JIRA_EMAIL": EMAIL,
+        "JIRA_API_TOKEN": TOKEN,
+    }
+
+    @property
+    def COMPOSED(self):
+        return base64.b64encode(f"{self.EMAIL}:{self.TOKEN}".encode("utf-8")).decode("ascii")
+
+    def _assert_clean(self, text):
+        self.assertNotIn(self.TOKEN, text)
+        self.assertNotIn(self.EMAIL, text)
+        self.assertNotIn(self.COMPOSED, text)
+
+    def _http_error(self, url, code, reason):
+        """A closed-on-teardown HTTPError. HTTPError owns an internal file
+        object; closing it avoids a ResourceWarning at GC time (mirrors
+        test_pr_resolver.py's helper of the same name)."""
+        err = urllib.error.HTTPError(url, code, reason, {}, None)
+        self.addCleanup(err.close)
+        return err
+
+    def test_secrets_absent_from_an_http_error_message(self):
+        err = self._http_error(
+            "https://acme.atlassian.net/rest/api/3/issue/ABC-1", 401,
+            "Unauthorized")
+        opener = mock.MagicMock()
+        opener.open.side_effect = err
+        with mock.patch.object(jc, "_OPENER", opener):
+            with self.assertRaises(jc.JiraError) as ctx:
+                jc._http_get("https://acme.atlassian.net/rest/api/3/issue/ABC-1",
+                             self.EMAIL, self.TOKEN)
+        self._assert_clean(str(ctx.exception))
+
+    def test_secrets_absent_from_a_network_error_message(self):
+        opener = mock.MagicMock()
+        opener.open.side_effect = urllib.error.URLError("connection refused")
+        with mock.patch.object(jc, "_OPENER", opener):
+            with self.assertRaises(jc.JiraError) as ctx:
+                jc._http_get("https://acme.atlassian.net/x", self.EMAIL, self.TOKEN)
+        self._assert_clean(str(ctx.exception))
+
+
+def adf(*content):
+    """Wrap block nodes in a minimal ADF document (hand-built fixture helper)."""
+    return {"type": "doc", "version": 1, "content": list(content)}
+
+
+def para(text):
+    """A single-text-node ADF paragraph."""
+    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}
+
+
+def heading(level, text):
+    """An ADF heading of the given level."""
+    return {"type": "heading", "attrs": {"level": level},
+            "content": [{"type": "text", "text": text}]}
+
+
+def bullets(*items):
+    """An ADF bulletList of single-paragraph list items."""
+    return {"type": "bulletList",
+            "content": [{"type": "listItem", "content": [para(t)]} for t in items]}
+
+
+class TestAdfToText(unittest.TestCase):
+    def test_none_renders_as_empty(self):
+        self.assertEqual(jc.adf_to_text(None), "")
+
+    def test_a_plain_string_passes_through(self):
+        self.assertEqual(jc.adf_to_text("already text"), "already text")
+
+    def test_a_single_paragraph(self):
+        self.assertEqual(jc.adf_to_text(adf(para("hello world"))), "hello world")
+
+    def test_two_paragraphs_are_blank_line_separated(self):
+        self.assertEqual(jc.adf_to_text(adf(para("one"), para("two"))), "one\n\ntwo")
+
+    def test_a_heading_renders_with_hash_markers(self):
+        self.assertEqual(jc.adf_to_text(adf(heading(2, "Acceptance Criteria"))),
+                         "## Acceptance Criteria")
+
+    def test_bullets_render_as_dash_lines(self):
+        self.assertEqual(jc.adf_to_text(adf(bullets("a", "b"))), "- a\n- b")
+
+    def test_ordered_list_items_are_numbered(self):
+        node = {"type": "orderedList",
+                "content": [{"type": "listItem", "content": [para("a")]},
+                            {"type": "listItem", "content": [para("b")]}]}
+        self.assertEqual(jc.adf_to_text(adf(node)), "1. a\n2. b")
+
+    def test_a_hard_break_becomes_a_newline(self):
+        node = {"type": "paragraph", "content": [
+            {"type": "text", "text": "a"},
+            {"type": "hardBreak"},
+            {"type": "text", "text": "b"}]}
+        self.assertEqual(jc.adf_to_text(adf(node)), "a\nb")
+
+    def test_a_code_block_is_fenced(self):
+        node = {"type": "codeBlock", "attrs": {"language": "python"},
+                "content": [{"type": "text", "text": "x = 1"}]}
+        self.assertEqual(jc.adf_to_text(adf(node)), "```\nx = 1\n```")
+
+    def test_a_mention_renders_with_an_at_sign(self):
+        node = {"type": "paragraph", "content": [
+            {"type": "mention", "attrs": {"text": "@Mia", "id": "5b1"}}]}
+        self.assertEqual(jc.adf_to_text(adf(node)), "@Mia")
+
+    def test_an_inline_card_renders_its_url(self):
+        node = {"type": "paragraph", "content": [
+            {"type": "inlineCard", "attrs": {"url": "https://example.com/x"}}]}
+        self.assertEqual(jc.adf_to_text(adf(node)), "https://example.com/x")
+
+    def test_an_unknown_node_type_still_renders_its_children(self):
+        node = {"type": "someFutureNode", "content": [
+            {"type": "text", "text": "kept"}]}
+        self.assertEqual(jc.adf_to_text(adf(node)), "kept")
+
+    def test_an_empty_document_renders_as_empty(self):
+        self.assertEqual(jc.adf_to_text(adf()), "")
+
+    def test_a_deeply_nested_structure_does_not_recurse_forever(self):
+        node = para("x")
+        for _ in range(30):
+            node = {"type": "blockquote", "content": [node]}
+        self.assertIn("x", jc.adf_to_text(adf(node)))
+
+
+def issue_bean(**fields):
+    """A minimal Jira IssueBean fixture; kwargs override the `fields` object."""
+    base = {"summary": "Add a widget",
+            "description": adf(para("Some background.")),
+            "status": {"name": "In Progress"},
+            "issuetype": {"name": "Story"}}
+    base.update(fields)
+    return {"key": "ABC-123", "id": "10001", "fields": base}
+
+
+class TestIssueUrl(unittest.TestCase):
+    def test_the_key_is_appended_to_the_v3_issue_path(self):
+        self.assertEqual(
+            jc._issue_url("https://acme.atlassian.net", "ABC-123"),
+            "https://acme.atlassian.net/rest/api/3/issue/ABC-123")
+
+    def test_the_key_is_percent_encoded(self):
+        self.assertEqual(
+            jc._issue_url("https://acme.atlassian.net", "A B"),
+            "https://acme.atlassian.net/rest/api/3/issue/A%20B")
+
+
+class TestFindAcFieldId(unittest.TestCase):
+    CATALOGUE = json.dumps([
+        {"id": "summary", "name": "Summary", "custom": False},
+        {"id": "customfield_10039", "name": "Acceptance Criteria", "custom": True},
+    ]).encode("utf-8")
+
+    def test_it_finds_the_field_by_display_name(self):
+        with mock.patch.object(jc, "_http_get", return_value=self.CATALOGUE):
+            self.assertEqual(
+                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"),
+                "customfield_10039")
+
+    def test_the_name_match_is_case_insensitive(self):
+        payload = json.dumps(
+            [{"id": "customfield_1", "name": "ACCEPTANCE criteria"}]).encode("utf-8")
+        with mock.patch.object(jc, "_http_get", return_value=payload):
+            self.assertEqual(
+                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"),
+                "customfield_1")
+
+    def test_an_absent_field_returns_none(self):
+        payload = json.dumps([{"id": "summary", "name": "Summary"}]).encode("utf-8")
+        with mock.patch.object(jc, "_http_get", return_value=payload):
+            self.assertIsNone(
+                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"))
+
+    def test_a_403_on_the_catalogue_degrades_to_none_rather_than_failing(self):
+        with mock.patch.object(jc, "_http_get",
+                               side_effect=jc.JiraError("HTTP 403")):
+            self.assertIsNone(
+                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"))
+
+    def test_a_non_list_catalogue_degrades_to_none(self):
+        with mock.patch.object(jc, "_http_get", return_value=b'{"oops": 1}'):
+            self.assertIsNone(
+                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"))
+
+    def test_a_catalogue_entry_that_is_not_an_object_is_skipped(self):
+        payload = json.dumps(
+            ["junk", {"id": "customfield_2", "name": "Acceptance Criteria"}]
+        ).encode("utf-8")
+        with mock.patch.object(jc, "_http_get", return_value=payload):
+            self.assertEqual(
+                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"),
+                "customfield_2")
+
+
+class TestFetchIssue(unittest.TestCase):
+    def test_it_requests_the_default_field_set(self):
+        payload = json.dumps(issue_bean()).encode("utf-8")
+        with mock.patch.object(jc, "_http_get", return_value=payload) as get:
+            jc.fetch_issue("https://acme.atlassian.net", "e", "t", "ABC-123", None)
+        url = get.call_args.args[0]
+        self.assertIn("fields=summary%2Cdescription%2Cstatus%2Cissuetype", url)
+
+    def test_the_ac_field_id_is_appended_to_the_field_set(self):
+        payload = json.dumps(issue_bean()).encode("utf-8")
+        with mock.patch.object(jc, "_http_get", return_value=payload) as get:
+            jc.fetch_issue("https://acme.atlassian.net", "e", "t", "ABC-123",
+                           "customfield_10039")
+        self.assertIn("customfield_10039", get.call_args.args[0])
+
+    def test_an_invalid_key_is_rejected_before_any_request(self):
+        with mock.patch.object(jc, "_http_get") as get:
+            with self.assertRaises(jc.JiraUsageError):
+                jc.fetch_issue("https://acme.atlassian.net", "e", "t", "../x", None)
+        get.assert_not_called()
+
+    def test_a_malformed_payload_raises(self):
+        with mock.patch.object(jc, "_http_get", return_value=b"nope"):
+            with self.assertRaises(jc.JiraError):
+                jc.fetch_issue("https://acme.atlassian.net", "e", "t", "ABC-1", None)
+
+
+class TestAcceptanceCriteria(unittest.TestCase):
+    DESC = ("Some background.\n\n"
+            "## Acceptance Criteria\n\n"
+            "- one\n- two\n\n"
+            "## Notes\n\nignore me")
+
+    def test_the_description_section_is_extracted(self):
+        self.assertEqual(
+            jc.acceptance_criteria_from_description(self.DESC), "- one\n- two")
+
+    def test_the_heading_match_is_case_insensitive_and_colon_tolerant(self):
+        text = "### acceptance criteria:\n\n- x"
+        self.assertEqual(jc.acceptance_criteria_from_description(text), "- x")
+
+    def test_an_absent_section_yields_empty(self):
+        self.assertEqual(
+            jc.acceptance_criteria_from_description("just prose"), "")
+
+    def test_a_trailing_section_runs_to_the_end_of_the_text(self):
+        text = "## Acceptance Criteria\n\n- last"
+        self.assertEqual(jc.acceptance_criteria_from_description(text), "- last")
+
+    def test_the_custom_field_wins_over_the_description(self):
+        issue = issue_bean(customfield_10039=adf(para("from the field")))
+        text, source = jc.resolve_acceptance_criteria(
+            issue, "customfield_10039", self.DESC)
+        self.assertEqual(text, "from the field")
+        self.assertEqual(source, "field")
+
+    def test_a_plain_string_custom_field_is_accepted(self):
+        issue = issue_bean(customfield_10039="plain AC text")
+        text, source = jc.resolve_acceptance_criteria(issue, "customfield_10039", "")
+        self.assertEqual((text, source), ("plain AC text", "field"))
+
+    def test_an_empty_custom_field_falls_back_to_the_description(self):
+        issue = issue_bean(customfield_10039=None)
+        text, source = jc.resolve_acceptance_criteria(
+            issue, "customfield_10039", self.DESC)
+        self.assertEqual((text, source), ("- one\n- two", "description"))
+
+    def test_an_unrenderable_field_shape_falls_back_to_the_description(self):
+        issue = issue_bean(customfield_10039=[{"value": "multi-select"}])
+        text, source = jc.resolve_acceptance_criteria(
+            issue, "customfield_10039", self.DESC)
+        self.assertEqual((text, source), ("- one\n- two", "description"))
+
+    def test_no_field_and_no_section_yields_empty_and_no_source(self):
+        text, source = jc.resolve_acceptance_criteria(issue_bean(), None, "prose")
+        self.assertEqual((text, source), ("", ""))
+
+
+def raw_comment(cid, text, author="Mia Krystof"):
+    """A minimal Jira comment fixture in REST v3 shape (ADF body)."""
+    return {"id": str(cid),
+            "author": {"displayName": author, "accountId": "5b10a284"},
+            "body": adf(para(text)),
+            "created": "2021-01-17T12:34:00.000+0000",
+            "updated": "2021-01-18T23:45:00.000+0000"}
+
+
+def comment_page(start, total, comments, max_results=100):
+    """A PageOfComments payload -- note the key is `comments`, not `values`."""
+    return json.dumps({"startAt": start, "maxResults": max_results,
+                       "total": total, "comments": comments}).encode("utf-8")
+
+
+class TestFetchComments(unittest.TestCase):
+    def test_a_single_page_is_normalized(self):
+        page = comment_page(0, 1, [raw_comment(10000, "hello")])
+        with mock.patch.object(jc, "_http_get", return_value=page):
+            got = jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
+        self.assertEqual(got, [{
+            "id": "10000", "author": "Mia Krystof",
+            "created": "2021-01-17T12:34:00.000+0000",
+            "updated": "2021-01-18T23:45:00.000+0000",
+            "body": "hello"}])
+
+    def test_every_page_is_followed_until_total_is_reached(self):
+        pages = [
+            comment_page(0, 3, [raw_comment(1, "a"), raw_comment(2, "b")]),
+            comment_page(2, 3, [raw_comment(3, "c")]),
+        ]
+        with mock.patch.object(jc, "_http_get", side_effect=pages) as get:
+            got = jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
+        self.assertEqual([c["id"] for c in got], ["1", "2", "3"])
+        self.assertEqual(get.call_count, 2)
+
+    def test_the_first_request_asks_for_the_configured_page_size(self):
+        page = comment_page(0, 0, [])
+        with mock.patch.object(jc, "_http_get", return_value=page) as get:
+            jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
+        url = get.call_args.args[0]
+        self.assertIn("/rest/api/3/issue/ABC-1/comment?", url)
+        self.assertIn("startAt=0", url)
+        self.assertIn("maxResults=%d" % jc.COMMENT_PAGE_SIZE, url)
+
+    def test_the_second_request_advances_start_at(self):
+        pages = [comment_page(0, 3, [raw_comment(1, "a"), raw_comment(2, "b")]),
+                 comment_page(2, 3, [raw_comment(3, "c")])]
+        with mock.patch.object(jc, "_http_get", side_effect=pages) as get:
+            jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
+        self.assertIn("startAt=2", get.call_args_list[1].args[0])
+
+    def test_no_comments_yields_an_empty_list(self):
+        with mock.patch.object(jc, "_http_get", return_value=comment_page(0, 0, [])):
+            self.assertEqual(
+                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1"), [])
+
+    def test_an_empty_page_short_circuits_a_lying_total(self):
+        pages = [comment_page(0, 999, [raw_comment(1, "a")]),
+                 comment_page(1, 999, [])]
+        with mock.patch.object(jc, "_http_get", side_effect=pages) as get:
+            got = jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
+        self.assertEqual(len(got), 1)
+        self.assertEqual(get.call_count, 2)
+
+    def test_a_runaway_server_is_capped_by_max_pages(self):
+        endless = comment_page(0, 10 ** 9, [raw_comment(1, "a")])
+        with mock.patch.object(jc, "_http_get", return_value=endless) as get:
+            with self.assertRaises(jc.JiraError) as ctx:
+                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
+        self.assertEqual(get.call_count, jc.MAX_COMMENT_PAGES)
+        self.assertIn("pages", str(ctx.exception))
+
+    def test_a_missing_author_object_renders_as_empty(self):
+        c = raw_comment(1, "a")
+        del c["author"]
+        with mock.patch.object(jc, "_http_get", return_value=comment_page(0, 1, [c])):
+            got = jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
+        self.assertEqual(got[0]["author"], "")
+
+    def test_a_page_missing_the_comments_key_raises(self):
+        payload = json.dumps({"startAt": 0, "maxResults": 100, "total": 1,
+                              "values": []}).encode("utf-8")
+        with mock.patch.object(jc, "_http_get", return_value=payload):
+            with self.assertRaises(jc.JiraError):
+                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
+
+    def test_an_invalid_key_is_rejected_before_any_request(self):
+        with mock.patch.object(jc, "_http_get") as get:
+            with self.assertRaises(jc.JiraUsageError):
+                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "x/y")
+        get.assert_not_called()
+
+
+
+class TestNormalizedRecord(unittest.TestCase):
+    VALUES = {"key": "ABC-123",
+              "web_url": "https://acme.atlassian.net/browse/ABC-123",
+              "summary": "Add a widget", "description": "Some background.",
+              "acceptance_criteria": "- one", "acceptance_criteria_source": "field",
+              "status": "In Progress", "issue_type": "Story", "comments": []}
+
+    def test_the_record_has_exactly_the_contract_fields_in_order(self):
+        self.assertEqual(list(jc._normalized(self.VALUES)), list(jc.RECORD_FIELDS))
+
+    def test_an_empty_description_is_allowed(self):
+        rec = jc._normalized(dict(self.VALUES, description=""))
+        self.assertEqual(rec["description"], "")
+
+    def test_an_empty_comment_list_is_allowed(self):
+        self.assertEqual(jc._normalized(self.VALUES)["comments"], [])
+
+    def test_each_required_field_being_empty_is_a_half_resolve(self):
+        for field in jc.REQUIRED_FIELDS:
+            with self.subTest(field=field):
+                with self.assertRaises(jc.JiraError) as ctx:
+                    jc._normalized(dict(self.VALUES, **{field: ""}))
+                self.assertIn(field, str(ctx.exception))
+
+
+class TestResolveIssue(unittest.TestCase):
+    ENV = {"JIRA_BASE_URL": "https://acme.atlassian.net",
+           "JIRA_EMAIL": "fred@example.com",
+           "JIRA_API_TOKEN": "tok"}
+
+    def _resolve(self, issue=None, comments=None, ac_field_id=None):
+        with mock.patch.dict(jc.os.environ, self.ENV, clear=True), \
+             mock.patch.object(jc, "find_ac_field_id", return_value=ac_field_id), \
+             mock.patch.object(jc, "fetch_issue",
+                               return_value=issue if issue else issue_bean()), \
+             mock.patch.object(jc, "fetch_comments", return_value=comments or []):
+            return jc.resolve_issue("ABC-123")
+
+    def test_the_full_record_is_assembled(self):
+        rec = self._resolve(comments=[{"id": "1", "author": "Mia",
+                                       "created": "c", "updated": "u",
+                                       "body": "hi"}])
+        self.assertEqual(rec["key"], "ABC-123")
+        self.assertEqual(rec["summary"], "Add a widget")
+        self.assertEqual(rec["status"], "In Progress")
+        self.assertEqual(rec["issue_type"], "Story")
+        self.assertEqual(rec["description"], "Some background.")
+        self.assertEqual(rec["web_url"],
+                         "https://acme.atlassian.net/browse/ABC-123")
+        self.assertEqual(len(rec["comments"]), 1)
+
+    def test_the_server_returned_key_wins_over_the_requested_one(self):
+        rec = self._resolve(issue=dict(issue_bean(), key="MOVED-9"))
+        self.assertEqual(rec["key"], "MOVED-9")
+        self.assertEqual(rec["web_url"],
+                         "https://acme.atlassian.net/browse/MOVED-9")
+
+    def test_a_missing_status_is_a_half_resolve(self):
+        with self.assertRaises(jc.JiraError):
+            self._resolve(issue=issue_bean(status={}))
+
+    def test_missing_credentials_raise_a_usage_error_before_any_call(self):
+        with mock.patch.dict(jc.os.environ, {}, clear=True), \
+             mock.patch.object(jc, "fetch_issue") as fetch:
+            with self.assertRaises(jc.JiraUsageError):
+                jc.resolve_issue("ABC-123")
+        fetch.assert_not_called()
+
+
+class TestMain(unittest.TestCase):
+    RECORD = {"key": "ABC-123", "web_url": "https://acme.atlassian.net/browse/ABC-123",
+              "summary": "s", "description": "", "acceptance_criteria": "",
+              "acceptance_criteria_source": "", "status": "Open",
+              "issue_type": "Task", "comments": []}
+
+    def _run(self, argv, **patches):
+        out, err = [], []
+        with mock.patch.object(jc.sys, "stdout") as so, \
+             mock.patch.object(jc.sys, "stderr") as se, \
+             mock.patch.object(jc, "resolve_issue", **patches):
+            rc = jc.main(argv)
+            out = "".join(c.args[0] for c in so.write.call_args_list if c.args)
+            err = "".join(c.args[0] for c in se.write.call_args_list if c.args)
+        return rc, out, err
+
+    def test_success_prints_one_json_object_and_exits_zero(self):
+        rc, out, _ = self._run(["resolve", "--key", "ABC-123"],
+                               return_value=self.RECORD)
+        self.assertEqual(rc, 0)
+        self.assertEqual(json.loads(out), self.RECORD)
+
+    def test_a_usage_error_exits_two_with_the_refusal_shape(self):
+        rc, _, err = self._run(["resolve", "--key", "ABC-123"],
+                               side_effect=jc.JiraUsageError("no creds"))
+        self.assertEqual(rc, 2)
+        self.assertEqual(json.loads(err), {"ok": False, "errors": ["no creds"]})
+
+    def test_a_contract_error_exits_one(self):
+        rc, _, err = self._run(["resolve", "--key", "ABC-123"],
+                               side_effect=jc.JiraError("HTTP 500"))
+        self.assertEqual(rc, 1)
+        self.assertEqual(json.loads(err), {"ok": False, "errors": ["HTTP 500"]})
+
+    def test_secrets_never_reach_stdout_or_stderr(self):
+        token, email = "s3cr3t-api-token-value", "fred@example.com"
+        composed = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
+        env = {"JIRA_BASE_URL": "https://acme.atlassian.net",
+               "JIRA_EMAIL": email, "JIRA_API_TOKEN": token}
+        opener = mock.MagicMock()
+        opener.open.side_effect = urllib.error.URLError("connection refused")
+        with mock.patch.dict(jc.os.environ, env, clear=True), \
+             mock.patch.object(jc, "_OPENER", opener), \
+             mock.patch.object(jc.sys, "stdout") as so, \
+             mock.patch.object(jc.sys, "stderr") as se:
+            rc = jc.main(["resolve", "--key", "ABC-123"])
+            out = "".join(c.args[0] for c in so.write.call_args_list if c.args)
+            err = "".join(c.args[0] for c in se.write.call_args_list if c.args)
+        self.assertNotEqual(rc, 0)
+        for secret in (token, email, composed):
+            self.assertNotIn(secret, out)
+            self.assertNotIn(secret, err)
+
+
+class TestReadOnlyContract(unittest.TestCase):
+    """The module must be structurally incapable of mutating Jira."""
+
+    SOURCE = (Path(__file__).resolve().parent / "jira_client.py").read_text()
+
+    def test_the_module_never_imports_subprocess(self):
+        self.assertNotIn("import subprocess", self.SOURCE)
+
+    def test_the_module_never_calls_datetime_now(self):
+        self.assertNotIn("datetime", self.SOURCE.replace("# ", ""))
+
+    def test_no_mutating_http_method_appears_in_the_source(self):
+        for verb in ('"POST"', '"PUT"', '"PATCH"', '"DELETE"',
+                     "'POST'", "'PUT'", "'PATCH'", "'DELETE'"):
+            self.assertNotIn(verb, self.SOURCE, verb)
+
+    def test_the_only_request_construction_sets_method_get(self):
+        self.assertEqual(self.SOURCE.count("urllib.request.Request("), 1)
+        self.assertIn('method="GET"', self.SOURCE)
+
+    def test_the_only_network_call_goes_through_the_module_opener(self):
+        self.assertEqual(self.SOURCE.count("_OPENER.open("), 1)
+
+    def test_the_entry_shim_is_exactly_two_lines(self):
+        lines = [ln for ln in self.SOURCE.splitlines()
+                 if ln.startswith("if __name__")]
+        self.assertEqual(len(lines), 1)
+        idx = self.SOURCE.splitlines().index(lines[0])
+        self.assertEqual(self.SOURCE.splitlines()[idx + 1].strip(),
+                         "sys.exit(main())")
+
+if __name__ == "__main__":
+    unittest.main()
diff --git a/scripts/coverage_omit.txt b/scripts/coverage_omit.txt
index 3b42e74..64e9d0e 100644
--- a/scripts/coverage_omit.txt
+++ b/scripts/coverage_omit.txt
@@ -32,10 +32,11 @@
 # scripts dir.
 
 scripts/dag.py:__main__                  # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/dashboard_launcher.py:__main__   # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/dashboard_server.py:__main__     # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/jira_client.py:__main__          # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/knowledge_graph.py:__main__      # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/pr_resolver.py:__main__          # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/quality_gate.py:__main__         # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/release.py:__main__              # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/review_package.py:__main__       # process-entry shim; the module is imported, not run as __main__, under unittest
diff --git a/scripts/measure_coverage.py b/scripts/measure_coverage.py
index f0d7d2e..38c518c 100644
--- a/scripts/measure_coverage.py
+++ b/scripts/measure_coverage.py
@@ -100,10 +100,11 @@ _MAIN_SHIM_RE = re.compile(r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:")
 # Product modules that count toward coverage (basename -> relpath key).
 TARGET_FILES = (
     "scripts/dag.py",
     "scripts/dashboard_launcher.py",
     "scripts/dashboard_server.py",
+    "scripts/jira_client.py",
     "scripts/knowledge_graph.py",
     "scripts/pr_resolver.py",
     "scripts/quality_gate.py",
     "scripts/release.py",
     "scripts/review_package.py",
@@ -140,10 +141,11 @@ TARGET_MODULES = tuple(Path(t).stem for t in TARGET_FILES)
 # likewise sits well under the py3.12 aggregate that pr_resolver drags down.
 PER_FILE_FLOORS = {
     "scripts/dag.py": 94,                  # local 99.8% (2026-07-30) - 5
     "scripts/dashboard_launcher.py": 95,   # local 100% - 5
     "scripts/dashboard_server.py": 94,     # local 99.5% (2026-07-30) - 5
+    "scripts/jira_client.py": 93,          # local 98.8% (2026-09-08) - >=5 (CI py3.12 co_lines drift margin)
     "scripts/knowledge_graph.py": 81,      # local 86.5% (2026-07-30) - 5
     "scripts/pr_resolver.py": 80,          # py3.12 preview 85.4% - 5 (not local 100%)
     "scripts/quality_gate.py": 86,         # local 91.6% (2026-07-30) - 5
     "scripts/release.py": 95,              # local 100% - 5
     "scripts/review_package.py": 89,       # local 94.3% (2026-07-30) - 5
diff --git a/scripts/test_measure_coverage_manifest.py b/scripts/test_measure_coverage_manifest.py
index 971982e..b64a890 100644
--- a/scripts/test_measure_coverage_manifest.py
+++ b/scripts/test_measure_coverage_manifest.py
@@ -17,11 +17,11 @@ from pathlib import Path
 
 sys.path.insert(0, str(Path(__file__).resolve().parent))
 import measure_coverage as mc  # noqa: E402
 
 # Every shipped target's entry shim is a guard header plus a single-line body, so the
-# resolved omission is exactly this many lines. One pin covers all thirteen targets:
+# resolved omission is exactly this many lines. One pin covers all fourteen targets:
 # raising it relaxes every target at once, not just the one that grew.
 SHIPPED_SHIM_LINES = 2
 
 
 class ResolveMainShimTests(unittest.TestCase):
