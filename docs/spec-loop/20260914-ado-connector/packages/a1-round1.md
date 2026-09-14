# Review package: ca497d23d221b8cb671fe7bc9d66be61b4283639..7aa6bdb  (context: -U5)

## Commits
7aa6bdb test(ado): reshape three record-contract literals to hanging indents
a3ad807 feat(ado): resolve the normalized work-item record with the acceptance-criteria order
a2877e6 test(ado): flatten the sweep refusal loops to three levels of nesting
6dfd278 feat(ado): add the fail-closed paginated comment sweep
201342a feat(ado): read one work item, deriving the project and closing the org against the response
85d115e feat(ado): add html_to_text, the lossy HTML description walker
83b5fd7 test(ado): reshape four transport assertions to hanging indents and locals
aecacc4 feat(ado): add the read-only transport, env-only credentials and the three api-version constants
0db8109 test(ado): reshape three org-URL assertions to a 4-space hanging indent
4d13631 feat(ado): add the ado_client read-lane skeleton with id and org-URL validation

## Files changed
 plugins/spec-loop/scripts/ado_client.py      | 945 +++++++++++++++++++++++++++
 plugins/spec-loop/scripts/test_ado_client.py | 945 +++++++++++++++++++++++++++
 2 files changed, 1890 insertions(+)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/ado_client.py": [
[
1,
945
]
],
"plugins/spec-loop/scripts/test_ado_client.py": [
[
1,
945
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/ado_client.py b/plugins/spec-loop/scripts/ado_client.py
new file mode 100644
index 0000000..fd8d0b6
--- /dev/null
+++ b/plugins/spec-loop/scripts/ado_client.py
@@ -0,0 +1,945 @@
+#!/usr/bin/env python3
+"""Azure DevOps Services work-item reader (stdlib only, READ-ONLY).
+
+Resolves one Azure DevOps work-item id to a normalized JSON record (org,
+project, id, web url, title, work item type, state, the HTML description
+rendered to text, acceptance criteria with the source that won, repro
+steps, and the full paginated comment list). Authenticates with HTTP Basic
+auth built from an EMPTY username and the PAT in ADO_PAT, against the org
+named by ADO_ORG_URL.
+
+Design decisions:
+  - Mirrors plugins/spec-loop/scripts/jira_client.py's transport doctrine by
+    COPY AND ADAPT, never by import: there is deliberately no shared helper
+    module with jira_client.py or pr_resolver.py -- duplication over
+    coupling, so loosening one provider cannot loosen another.
+  - THE READ LANE IS STRUCTURALLY INCAPABLE OF A MUTATING VERB: _http_get
+    takes no `data` parameter at all -- and no `method` parameter for a
+    caller to widen -- and hardcodes method="GET". urllib.request.Request
+    infers POST from a non-None `data`, so the ABSENCE of that parameter is
+    the proof, not a comment. Any writer added to this module in future is
+    a separate function with its own bounded surface and its own tests; it
+    cannot loosen the read lane, and the read lane's tests are scoped to
+    _http_get's own source so that stays true.
+  - This repo already reaches Azure DevOps for pull requests through the
+    `az` CLI (pr_resolver.py), and this module deliberately does NOT: the
+    CLI has no command that lists a work item's comments, so the read-back
+    dedupe gate the comment lane depends on is impossible through it, and
+    `az boards work-item update` is the general mutation command rather
+    than a structurally comment-only surface. Raw REST on urllib is the
+    only transport that can carry the safety design. No subprocess, and no
+    dependency on `az`, including `az devops invoke`.
+  - Host allow-list: ADO_ORG_URL must be https and its hostname must match
+    ALLOWED_HOST_RE -- dev.azure.com (with the org as the first path
+    segment) or the legacy <org>.visualstudio.com form. Azure DevOps
+    Server / on-prem hosts are out of scope and are refused with a message
+    naming both supported forms; there is deliberately no opt-in
+    extra-hosts env var, since that would re-open the exact hole the
+    allow-list closes.
+  - Redirects are refused outright (a custom HTTPRedirectHandler whose
+    redirect_request returns None), not followed-with-header-stripped. The
+    org URL is user-supplied, so pr_resolver's hardcoded-origin property is
+    gone and an Authorization header must never be replayed to another
+    origin.
+  - NO URL TAKEN FROM A RESPONSE BODY IS EVER FETCHED. Every request URL is
+    composed locally from the validated api_root plus a literal path. The
+    comment list returns both a `continuationToken` and a fully-formed
+    `nextPage` URL chosen by the server; `nextPage` is never read and never
+    fetched -- it would pass through neither the host allow-list (which
+    validates the org URL, not a URL the client volunteers to fetch) nor
+    the redirect refusal (there is no 3xx to refuse). Pages are composed
+    from the validated api_root plus the regex-validated,
+    percent-encoded continuationToken.
+  - THE PROJECT COMES FROM THE READ, NEVER FROM THE ENVIRONMENT. The
+    work-item GET takes `project` as an optional path segment, so the read
+    is issued with org + id alone and the project is taken from the
+    response's System.TeamProject field -- which the comment endpoints
+    (where project is REQUIRED) then use. ADO_PROJECT is therefore optional
+    and, when set, is only an assertion: a mismatch refuses and names both
+    values, preferring neither. You cannot mis-set what you do not set.
+  - `org` is the one unavoidable environment input, so it is closed against
+    the response too: the body-supplied _links.html.href must start with
+    the already-validated api_root, or the resolve refuses. The href is
+    stored and displayed, never fetched -- and it is displayed at the
+    moment an operator authorizes a write, so it is validated before it can
+    be printed.
+  - Three api-versions, three constants, and they differ ON PURPOSE (the
+    work-item read is stable 7.1, the comment list is 7.1-preview.4, the
+    comment add is 7.0-preview.3). A test asserts they are not all equal so
+    a well-meaning "consistency" edit fails loudly.
+  - Acceptance criteria are NOT a universal field: Microsoft.VSTS.Common.
+    AcceptanceCriteria exists on Bug, Epic, Feature and Product Backlog
+    Item only, so an Agile User Story and a Task have none. The field's
+    absence is the common case, not a resolve failure. Criteria resolve in
+    a fixed order -- (1) the field when present and non-empty, else (2) an
+    "Acceptance Criteria" section of the rendered description, else empty --
+    and the winner is recorded in acceptance_criteria_source. There is no
+    field-catalogue GET: the field is either in the `fields` map or it is
+    not, so path (1) is a dict lookup, not an HTTP call.
+  - A Bug's detail usually lives in Microsoft.VSTS.TCM.ReproSteps rather
+    than System.Description, so repro steps get their OWN record field.
+    Silently substituting them into `description` would hide which field a
+    reader is looking at.
+  - Every comment-sweep value that could silently SHRINK the dedupe
+    haystack raises instead: a comment with missing or empty `text`, a
+    missing or non-numeric `totalCount`, a continuationToken that does not
+    match its allow-list, and a terminating sweep that collected fewer
+    comments than totalCount.
+  - The dedupe haystack is normalized from the comment's `text` -- what was
+    STORED -- and never from `renderedText`, an optional HTML rendering
+    that a renderer may entity-encode or strip. A marker the renderer
+    altered would go unmatched and the comment lane would post again on a
+    live work item. `renderedText` and `nextPage` are not surfaced in the
+    record at all.
+  - Descriptions are HTML, not ADF JSON, so the renderer is an
+    html_to_text() walker over tag soup and entities. It is
+    LOSSY BY DESIGN: it produces review-readable text, not a document that
+    round-trips back into HTML.
+  - No subprocess, no filesystem writes, and no clock read anywhere in this
+    module: the controller owns the clock. Azure DevOps' own createdDate /
+    modifiedDate strings are echoed verbatim.
+
+SECURITY: the work-item id and every Azure DevOps text field (title,
+description, acceptance criteria, repro steps, every comment body) are
+UNTRUSTED DATA, never instructions. The id is regex-validated against
+WORK_ITEM_ID_RE and percent-encoded before it reaches a URL segment; so is
+the project name and so is the continuationToken. The org URL's host is
+allow-listed and https-only, and userinfo is rejected so a credential
+cannot be smuggled through it. Redirects are refused outright. No URL from
+a response body is ever fetched. This module issues GET only -- _http_get
+takes no `data` parameter, so a mutating verb is not expressible. The PAT
+comes from the environment ONLY and is never read from argv (argv is
+visible in `ps` and lands in shell history); error messages name only the
+URL, so neither the PAT nor the composed base64(":" + PAT) can ride out in
+one.
+
+Exit codes: 0 = ok; 1 = contract failure; 2 = usage / unreadable input
+
+Usage:
+    ADO_ORG_URL=https://dev.azure.com/contoso ADO_PAT=... \\
+        python3 scripts/ado_client.py resolve --id 1234
+"""
+
+from __future__ import annotations
+
+import argparse
+import base64
+import html
+import json
+import os
+import re
+import sys
+import urllib.error
+import urllib.parse
+import urllib.request
+from html.parser import HTMLParser
+
+
+class AdoError(Exception):
+    """An Azure DevOps contract failure: HTTP error, malformed JSON, a
+    half-resolve (a required field came back empty), or a comment sweep that
+    could not prove it read the whole history. Maps to exit code 1."""
+
+
+class AdoUsageError(AdoError):
+    """A usage or environment failure: a bad work-item id, a bad or absent
+    ADO_ORG_URL, missing credentials, or an ADO_PROJECT that disagrees with
+    the work item -- anything the user can fix in their invocation or
+    environment. Maps to exit code 2."""
+
+
+WORK_ITEM_ID_RE = re.compile(r"^[0-9]{1,10}$")
+ORG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
+ALLOWED_HOST_RE = re.compile(
+    r"^(?:dev\.azure\.com|[A-Za-z0-9][A-Za-z0-9-]{0,60}\.visualstudio\.com)$")
+
+_SUPPORTED_FORMS = (
+    "https://dev.azure.com/<org> or the legacy https://<org>.visualstudio.com "
+    "(Azure DevOps SERVICES only -- Azure DevOps Server / on-prem hosts are "
+    "not supported by this connector)")
+
+
+def validate_work_item_id(raw):
+    """Validate an UNTRUSTED work-item id and return it as a string. An Azure
+    DevOps work item is addressed by a bare integer -- there is no
+    self-describing ABC-123 key -- so the allow-list is digits only. Rejects a
+    leading '-' (argument injection), path separators, whitespace and
+    newlines. Accepts an int for convenience since the API returns one."""
+    text = str(raw) if isinstance(raw, int) else (raw or "")
+    if not WORK_ITEM_ID_RE.fullmatch(text):
+        raise AdoUsageError(
+            f"invalid Azure DevOps work-item id {raw!r}: must match "
+            f"{WORK_ITEM_ID_RE.pattern} (1-10 digits, e.g. 1234)")
+    return text
+
+
+def _split_org_url(raw):
+    """Split an UNTRUSTED ADO_ORG_URL into urlsplit's parts, or None when the
+    value cannot be split at all (a malformed IPv6 host) or carries a port
+    that cannot be parsed as an integer (both raise a bare ValueError from
+    urllib.parse, since parts.port is computed lazily on attribute access).
+    Isolating that ValueError here keeps every malformed org URL on the
+    fail-closed AdoUsageError path instead of an uncaught traceback."""
+    try:
+        parts = urllib.parse.urlsplit(raw or "")
+        parts.port  # noqa: B018 -- force the lazy, possibly-raising parse now
+    except ValueError:
+        return None
+    return parts
+
+
+def _redacted_org_url(raw, parts):
+    """Render raw for the rejection message with any userinfo stripped, so a
+    credential smuggled into ADO_ORG_URL's userinfo is never echoed back into
+    the machine-readable error object. Falls back to '<unparsable>' when the
+    value could not even be split (parts is None)."""
+    if parts is None:
+        return "<unparsable>"
+    if parts.username or parts.password:
+        return f"{parts.scheme}://<redacted>@{parts.hostname or ''}"
+    return f"{parts.scheme}://{parts.hostname or ''}"
+
+
+def _org_url_refusal(raw, parts):
+    """The one AdoUsageError every org-URL rejection raises. Names both
+    supported forms, per the run constraint that an unsupported host produces
+    a clear refusal rather than a partially working path."""
+    return AdoUsageError(
+        f"invalid ADO_ORG_URL {_redacted_org_url(raw, parts)!r}: must be "
+        f"{_SUPPORTED_FORMS}")
+
+
+def _org_from_parts(parts):
+    """Extract the org from already-scheme/host-validated urlsplit parts, or
+    None when the URL does not name exactly one org. dev.azure.com carries the
+    org as its FIRST AND ONLY path segment; the legacy form carries it as the
+    hostname's first label and must have no path. An extra path segment is
+    rejected rather than ignored: silently dropping '/MyProject' would let an
+    operator believe they had scoped the connector to a project when the
+    project actually comes from the work-item read."""
+    host = (parts.hostname or "").lower()
+    segments = [s for s in parts.path.split("/") if s]
+    if host == "dev.azure.com":
+        if len(segments) != 1:
+            return None
+        return segments[0]
+    if segments:
+        return None
+    return host.split(".")[0]
+
+
+def validate_org_url(raw):
+    """Validate an UNTRUSTED ADO_ORG_URL and return (api_root, org).
+
+    api_root is the LOCALLY COMPOSED prefix every request URL in this module
+    is built from -- 'https://dev.azure.com/<org>' for the modern form, the
+    bare 'https://<org>.visualstudio.com' origin for the legacy form -- with
+    no trailing slash, no path beyond the org, no query and no fragment.
+    Discarding anything else is deliberate: every API path is composed from
+    api_root plus a literal '/_apis/...' suffix.
+
+    Requires https, rejects embedded userinfo (userinfo smuggling) and an
+    explicit port, requires the hostname to match ALLOWED_HOST_RE, and
+    requires the org to match ORG_RE -- the org is a URL path segment, so a
+    '..' or a '/' in it must never get that far."""
+    parts = _split_org_url(raw)
+    ok = bool(
+        parts is not None
+        and parts.scheme == "https"
+        and not parts.username
+        and not parts.password
+        and not parts.port
+        and not parts.query
+        and not parts.fragment
+        and ALLOWED_HOST_RE.fullmatch(parts.hostname or "")
+    )
+    org = _org_from_parts(parts) if ok else None
+    if not org or not ORG_RE.fullmatch(org):
+        raise _org_url_refusal(raw, parts)
+    host = parts.hostname.lower()
+    if host == "dev.azure.com":
+        return (f"https://{host}/{urllib.parse.quote(org, safe='')}", org)
+    return (f"https://{host}", org)
+
+
+# Three api-versions, three constants, and they differ ON PURPOSE (verified on
+# Microsoft Learn, 2026-09-14). Do not "modernize" or unify them: the comment
+# list's newest documented version is a 7.1 preview and the comment add's is a
+# 7.0 preview. TestApiVersionsAreThreeDistinctConstants fails if they collapse.
+API_VERSION_WORK_ITEM = "7.1"            # GET .../_apis/wit/workitems/{id}
+API_VERSION_COMMENTS_READ = "7.1-preview.4"  # GET .../workItems/{id}/comments
+# Referenced by no code path in THIS read lane -- it is the documented version
+# for the bounded comment-add lane, which lives in THIS module and POSTs with
+# THIS constant, so pinning it here beside its siblings keeps the value the
+# write lane uses under the not-all-equal test rather than letting a second
+# copy drift.
+API_VERSION_COMMENT_ADD = "7.0-preview.3"
+
+PROJECT_ENV_VAR = "ADO_PROJECT"
+
+
+class _NoRedirect(urllib.request.HTTPRedirectHandler):
+    """Refuse every 3xx. ADO_ORG_URL is user-supplied, so pr_resolver's
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
+CRED_VARS = ("ADO_ORG_URL", "ADO_PAT")
+
+
+def credentials():
+    """Read the Azure DevOps credentials from the ENVIRONMENT ONLY and fail
+    closed with an actionable message when either is unset. Never read from
+    argv: argv is visible in `ps` and lands in shell history.
+
+    Only ADO_ORG_URL and ADO_PAT are required. ADO_PROJECT is deliberately
+    OPTIONAL -- the project comes from the work item's own System.TeamProject
+    -- and the message says so, because demanding a variable the design says
+    to leave unset would push operators into the wrong-target failure mode
+    that optionality exists to close."""
+    values = {name: (os.environ.get(name) or "").strip() for name in CRED_VARS}
+    missing = [name for name in CRED_VARS if not values[name]]
+    if missing:
+        raise AdoUsageError(
+            "Azure DevOps access requires the environment variable(s) "
+            + ", ".join(missing)
+            + f". Set ADO_ORG_URL to {_SUPPORTED_FORMS}, and ADO_PAT to a "
+            "personal access token with the 'Work Items (Read)' scope. "
+            f"{PROJECT_ENV_VAR} is OPTIONAL: the project is read from the "
+            "work item itself, and setting this variable only asserts that "
+            "the work item lives in that project. Pass these in the "
+            "environment, never on the command line."
+        )
+    api_root, org = validate_org_url(values["ADO_ORG_URL"])
+    return (api_root, org, values["ADO_PAT"])
+
+
+def _auth_header(pat):
+    """Build the Azure DevOps Basic auth header: base64(":" + pat), i.e. a PAT
+    with an EMPTY username. Verified against Microsoft Learn's own sample,
+    which is `curl -u :{PAT}` (read 2026-09-14). Microsoft now recommends
+    Entra tokens where possible; PATs remain supported and are the only auth
+    flow in scope for this connector."""
+    raw = f":{pat}".encode("utf-8")
+    return "Basic " + base64.b64encode(raw).decode("ascii")
+
+
+def _http_get(url, pat):
+    """HTTP GET via the no-redirect opener. THE ONLY network entry point in
+    this module, and it is READ-ONLY BY CONSTRUCTION: there is no `data`
+    parameter for a caller to pass a body through and no `method` parameter
+    for a caller to widen, so a mutating verb is not expressible here.
+    urllib.request.Request infers POST from a non-None `data`, which is
+    exactly why `data` is absent from the signature rather than defaulted to
+    None.
+
+    Errors reference only the URL -- the credential rides in a header, so
+    neither the PAT nor the composed base64(":" + PAT) can appear in an
+    exception message."""
+    headers = {
+        "Authorization": _auth_header(pat),
+        "Accept": "application/json",
+    }
+    req = urllib.request.Request(url, headers=headers, method="GET")
+    try:
+        with _OPENER.open(req, timeout=30) as resp:
+            return resp.read()
+    except urllib.error.HTTPError as exc:
+        raise AdoError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
+    except urllib.error.URLError as exc:
+        raise AdoError(f"network error fetching {url}: {exc.reason}") from exc
+    except OSError as exc:
+        # urllib only wraps an OSError raised by h.request() into a URLError
+        # (see CPython's AbstractHTTPHandler.do_open); an OSError out of
+        # h.getresponse() or resp.read() -- a timeout or a reset while reading
+        # the response body -- propagates unwrapped and would otherwise slip
+        # past the AdoError handling above and past main()'s exit-1 JSON
+        # contract as a raw traceback. Caught here, terminally, so every
+        # transport failure is an AdoError. The message names only the URL, so
+        # no credential can ride out in it.
+        raise AdoError(f"network error fetching {url}: {exc}") from exc
+
+
+def _parse_json(raw, what):
+    """json.loads with an actionable AdoError, so a malformed response fails
+    with a clear message rather than a raw traceback."""
+    try:
+        return json.loads(raw)
+    except json.JSONDecodeError as exc:
+        raise AdoError(
+            f"Azure DevOps returned a {what} response that is not valid JSON "
+            f"({exc})") from exc
+
+
+HEADING_PREFIX = "## "
+
+# Tags whose boundaries are a paragraph break in the rendered text.
+_BLOCK_TAGS = frozenset({
+    "p", "div", "section", "article", "blockquote", "pre", "table", "tr",
+    "ul", "ol", "dl", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6",
+})
+_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
+# Tags whose text content is markup, not prose, and is dropped entirely.
+_DROP_TAGS = frozenset({"script", "style"})
+_BLANK_RUN_RE = re.compile(r"\n{3,}")
+_TRAILING_SPACE_RE = re.compile(r"[ \t]+\n")
+
+
+class _HtmlToText(HTMLParser):
+    """Collect an HTML fragment's prose into blank-line-separated blocks.
+
+    Deliberately small and forgiving: html.parser never raises on tag soup
+    (convert_charrefs handles entities for us), an unrecognized tag
+    contributes its text rather than vanishing, and an unclosed tag just
+    leaves the block open. HTML COMMENTS ARE DROPPED -- handle_comment is not
+    implemented -- which is why the comment lane's dedupe haystack also
+    searches the raw stored text: a marker hidden inside an HTML comment is
+    invisible to this walker and visible there."""
+
+    def __init__(self):
+        super().__init__(convert_charrefs=True)
+        self.parts = []
+        self._dropping = 0
+
+    def handle_starttag(self, tag, attrs):
+        """Open a tag: suppress markup-only content, break blocks, bullet a
+        list item, and treat <br> as a single newline."""
+        if tag in _DROP_TAGS:
+            self._dropping += 1
+        elif tag == "br":
+            self.parts.append("\n")
+        elif tag == "li":
+            self.parts.append("\n- ")
+        elif tag in _BLOCK_TAGS:
+            self.parts.append("\n\n")
+            if tag in _HEADING_TAGS:
+                self.parts.append(HEADING_PREFIX)
+
+    def handle_startendtag(self, tag, attrs):
+        """A self-closing tag (<br/>) opens and closes in one token; only the
+        open side has any effect here."""
+        self.handle_starttag(tag, attrs)
+
+    def handle_endtag(self, tag):
+        """Close a tag: stop suppressing, or end the current block."""
+        if tag in _DROP_TAGS:
+            self._dropping = max(0, self._dropping - 1)
+        elif tag == "li":
+            # DELIBERATELY NOTHING. handle_starttag already opens every list
+            # item with "\n- ", so appending anything here doubles the break
+            # and renders consecutive items as "- a\n\n- b" instead of the
+            # contracted "- a\n- b". The enclosing </ul>/</ol> is a _BLOCK_TAG
+            # and supplies the paragraph break that closes the list.
+            # Verified against the prescribed _tidy_text: "- a\n- b" for
+            # <ul><li>a</li><li>b</li></ul>, "- a\n\nafter" for a list
+            # followed by <p>after</p>.
+            return
+        elif tag in _BLOCK_TAGS:
+            self.parts.append("\n\n")
+
+    def handle_data(self, data):
+        """Append literal text unless inside a markup-only element."""
+        if not self._dropping:
+            self.parts.append(data)
+
+    def text(self):
+        """The collected parts as one string."""
+        return "".join(self.parts)
+
+
+def _tidy_text(raw):
+    """Normalize a walked fragment: unescape any entity html.parser left
+    behind, drop trailing spaces before a newline, collapse a run of three or
+    more newlines to one blank line, and strip the ends."""
+    text = html.unescape(raw).replace("\r\n", "\n").replace("\r", "\n")
+    text = text.replace("\xa0", " ")
+    text = _TRAILING_SPACE_RE.sub("\n", text)
+    return _BLANK_RUN_RE.sub("\n\n", text).strip()
+
+
+def html_to_text(raw):
+    """Render an Azure DevOps HTML field (System.Description,
+    Microsoft.VSTS.Common.AcceptanceCriteria, Microsoft.VSTS.TCM.ReproSteps,
+    or a comment's stored text) to plain, review-readable text. (PURE)
+
+    LOSSY BY DESIGN, in exactly the way jira_client.adf_to_text is: it
+    produces text for humans to read, not a document that round-trips back
+    into HTML. Headings of every level render with the same HEADING_PREFIX --
+    the level is discarded, and that prefix is what lets
+    acceptance_criteria_from_description find a section boundary. Anything
+    that is not a string (None, a number, a list) renders as '' rather than
+    raising, because a field of an unexpected shape is not prose."""
+    if not isinstance(raw, str) or not raw:
+        return ""
+    parser = _HtmlToText()
+    parser.feed(raw)
+    parser.close()
+    return _tidy_text(parser.text())
+
+
+# Verified reference names (Microsoft Learn field index, read 2026-09-14).
+# Fields are a FLAT map under `fields`, keyed by reference name.
+FIELD_TITLE = "System.Title"                  # String, all types
+FIELD_DESCRIPTION = "System.Description"      # HTML, all types
+FIELD_TYPE = "System.WorkItemType"            # String, all types
+FIELD_PROJECT = "System.TeamProject"          # String, all types
+FIELD_STATE = "System.State"                  # String, all types
+# HTML, and present on Bug / Epic / Feature / Product Backlog Item ONLY. An
+# Agile User Story and a Task have NO acceptance-criteria field at all, so its
+# absence is the common case and never a resolve failure.
+FIELD_ACCEPTANCE_CRITERIA = "Microsoft.VSTS.Common.AcceptanceCriteria"
+# HTML, Bug only -- and usually where a Bug's real detail lives, which is why
+# it gets its own record field instead of being substituted into description.
+FIELD_REPRO_STEPS = "Microsoft.VSTS.TCM.ReproSteps"
+
+COMMENT_PAGE_SIZE = 100
+
+_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
+
+
+def work_item_url(api_root, work_item_id):
+    """Compose the work-item read URL LOCALLY from the validated api_root plus
+    a literal path. The project segment is deliberately OMITTED: it is
+    optional on this endpoint, and issuing the read without it is what lets
+    the project be discovered from the response instead of supplied from the
+    environment. The id is re-validated and percent-encoded here even though
+    the caller validated it -- defence in depth, per the rule that an
+    untrusted value is encoded regardless before it reaches a URL segment."""
+    encoded = urllib.parse.quote(validate_work_item_id(work_item_id), safe="")
+    return (f"{api_root}/_apis/wit/workitems/{encoded}"
+            f"?api-version={API_VERSION_WORK_ITEM}")
+
+
+def comments_url(api_root, project, work_item_id, continuation_token=None):
+    """Compose a comment-list page URL LOCALLY from the validated api_root, the
+    percent-encoded project (REQUIRED on this endpoint) and a literal path.
+
+    NOTE THE TWO DISTINCT TRANSFORMS OF ONE PROJECT NAME: this URL needs the
+    ORIGINAL name, quote(..., safe="")-encoded. An artifact path needs a lossy
+    filesystem slug instead. Reusing a slug here would 404 on every project
+    whose name contains a space.
+
+    The continuation token is an opaque SERVER-CHOSEN string: it is validated
+    against CONTINUATION_TOKEN_RE by the caller and percent-encoded here. The
+    response's fully-formed `nextPage` URL is never read and never fetched --
+    composing the URL locally is what keeps every request inside the
+    already-validated origin."""
+    encoded_project = urllib.parse.quote(project, safe="")
+    encoded_id = urllib.parse.quote(validate_work_item_id(work_item_id), safe="")
+    url = (f"{api_root}/{encoded_project}/_apis/wit/workItems/{encoded_id}"
+           f"/comments?api-version={API_VERSION_COMMENTS_READ}"
+           f"&$top={COMMENT_PAGE_SIZE}")
+    if continuation_token:
+        token = urllib.parse.quote(continuation_token, safe="")
+        url += f"&continuationToken={token}"
+    return url
+
+
+def fetch_work_item(api_root, pat, work_item_id):
+    """GET one work item READ-ONLY and return the raw response object. The id
+    is validated before any request is issued (inside work_item_url). A
+    response that is not a JSON object is a contract failure rather than
+    something to index into."""
+    url = work_item_url(api_root, work_item_id)
+    payload = _parse_json(_http_get(url, pat).decode("utf-8"), "work item")
+    if not isinstance(payload, dict):
+        raise AdoError(
+            "Azure DevOps returned a work-item response that is not an "
+            "object; refusing to read fields from it")
+    return payload
+
+
+def resolve_project(fields):
+    """Resolve the project from the work item's own System.TeamProject, which
+    is present on every work-item type. THE PROJECT IS NEVER TAKEN FROM THE
+    ENVIRONMENT: the comment endpoints require it, and an operator-supplied
+    project could disagree with where the item actually lives -- a 404 at
+    best, a comment addressed to another item's route at worst.
+
+    An absent or empty value is a HALF-RESOLVE and raises: the record would
+    otherwise carry no way to reconstruct the comment route. A name carrying a
+    control character or a line break is REFUSED, never rewritten -- it also
+    lands in artifact front matter downstream, where a raw newline inside a
+    quoted scalar is a hazard."""
+    raw = fields.get(FIELD_PROJECT)
+    project = raw.strip() if isinstance(raw, str) else ""
+    if not project:
+        raise AdoError(
+            f"Azure DevOps returned a work item with no {FIELD_PROJECT}; "
+            "refusing to emit a record that cannot name its own project")
+    if _CONTROL_CHAR_RE.search(project):
+        raise AdoError(
+            f"the work item's {FIELD_PROJECT} contains a control character or "
+            "line break; refusing it rather than rewriting a project name")
+    return project
+
+
+def assert_project_matches_env(project):
+    """Treat ADO_PROJECT, when set, as an ASSERTION about the resolved project
+    and refuse on a mismatch, naming both values and preferring neither. When
+    unset -- the recommended state -- this asserts nothing: you cannot mis-set
+    what you do not set, and removing the input is strictly stronger than
+    validating it.
+
+    THE COMPARISON IS DELIBERATELY EXACT (after stripping surrounding
+    whitespace only). Azure DevOps project names are case-preserving, this is
+    an assertion-only path that fails closed and names both values preferring
+    neither, and a case-insensitive or punctuation-folding compare would
+    quietly widen what the assertion accepts. Do not 'fix' it into one."""
+    expected = (os.environ.get(PROJECT_ENV_VAR) or "").strip()
+    if expected and expected != project:
+        raise AdoUsageError(
+            f"{PROJECT_ENV_VAR} is set to {expected!r} but the work item "
+            f"lives in project {project!r}; refusing to continue. Unset "
+            f"{PROJECT_ENV_VAR} (the project is read from the work item) or "
+            "correct it to match.")
+    return None
+
+
+def validate_web_url(href, api_root):
+    """Validate the work item's body-supplied _links.html.href and return it.
+
+    THIS URL IS NEVER FETCHED -- it is stored in the record and DISPLAYED. It
+    is validated anyway, and for a specific reason: it is displayed in the
+    confirmation prompt where an operator authorizes an irreversible write, so
+    a spoofed href would look to them like a genuine work-item link at exactly
+    the wrong moment.
+
+    Requiring it to start with the already-validated api_root plus '/' does
+    double duty: it re-applies the host allow-list to a value that never
+    passed through it, and it asserts the org the response reports is the org
+    that was asked for -- a wrong org mis-targets exactly like a wrong
+    project. The '/' is load-bearing: without it 'contoso-evil' would pass as
+    'contoso'."""
+    text = href if isinstance(href, str) else ""
+    prefix = f"{api_root}/"
+    if not text.lower().startswith(prefix.lower()):
+        raise AdoError(
+            "the work item's web URL does not sit under the requested "
+            f"organization {api_root} (the response's URL is on "
+            f"{_href_origin(text)}); refusing to emit or display it. If your "
+            "organization has both host forms, set ADO_ORG_URL to the form "
+            "Azure DevOps itself returns.")
+    return text
+
+
+def _href_origin(text):
+    """Render just the scheme+host of a body-supplied href, for a refusal
+    message. SCHEME AND HOST ONLY: the path and query are untrusted response
+    data and must never be echoed. Returns '<unparseable>' rather than raise,
+    because this runs only on an error path.
+
+    Without this, the realistic trigger -- an org whose _links.html.href comes
+    back on the legacy <org>.visualstudio.com host while ADO_ORG_URL is the
+    dev.azure.com form, or the reverse -- produces a correct, fail-closed exit
+    1 that reads to the operator as an unexplained outage. The mocked
+    transport suite cannot surface that; the message has to."""
+    try:
+        parts = urllib.parse.urlsplit(text)
+    except ValueError:
+        return "<unparseable>"
+    if not parts.scheme or not parts.hostname:
+        return "<unparseable>"
+    return f"{parts.scheme}://{parts.hostname}"
+
+
+MAX_COMMENT_PAGES = 100
+
+# The continuationToken is an opaque SERVER-CHOSEN string that lands in a
+# query string. It is allow-listed rather than trusted, and a token that does
+# not match RAISES -- dropping it would silently truncate the sweep, which is
+# the same failure mode as a missing totalCount.
+CONTINUATION_TOKEN_RE = re.compile(r"^[A-Za-z0-9+/=_.\-]{1,512}$")
+
+_MISSING_COMMENTS_MSG = (
+    "Azure DevOps comment page is missing the 'comments' list; cannot read "
+    "the full comment history")
+_MISSING_TOTAL_MSG = (
+    "Azure DevOps comment page is missing a numeric 'totalCount'; cannot "
+    "tell whether the full comment history has been read")
+_MISSING_TEXT_MSG = (
+    "Azure DevOps returned a comment with no 'text'; refusing to dedupe "
+    "against a comment history with a hole in it")
+_BAD_TOKEN_MSG = (
+    "Azure DevOps returned a 'continuationToken' outside "
+    + CONTINUATION_TOKEN_RE.pattern
+    + "; refusing a possibly-truncated comment history rather than dropping "
+      "the token")
+
+
+def _comment_id(raw):
+    """Read a comment's id, accepting either documented spelling. The
+    comment-list DEFINITION table names the field `id`, while Microsoft's own
+    SAMPLE PAYLOADS on the list and add pages show `commentId`. Read
+    defensively: prefer whichever is present."""
+    for key in ("id", "commentId"):
+        value = raw.get(key)
+        if value is not None:
+            return str(value)
+    return ""
+
+
+def _comment_text(raw):
+    """Read a comment's STORED text, fail-closed.
+
+    This is the dedupe haystack, and it comes from `text` -- never from
+    `renderedText`, an optional HTML rendering of the same body. A marker that
+    an HTML renderer entity-encoded or stripped would go UNMATCHED, every
+    entry would plan as not-already-posted, and the comment lane would post
+    again on a live work item.
+
+    `text` is on the base Comment definition and is returned without $expand
+    (verified 2026-09-14), so a missing one is a shape surprise -- and three
+    real shapes still produce one: a redacted comment surfaced under
+    includeDeleted, a legitimately empty comment, and any future projection
+    change. A documented default projection is not a runtime guarantee, so
+    this raises rather than contribute an empty string to the haystack."""
+    text = raw.get("text")
+    if not isinstance(text, str) or not text:
+        raise AdoError(_MISSING_TEXT_MSG)
+    return text
+
+
+def _normalize_comment(raw):
+    """Normalize one raw comment to
+    {"id", "author", "created", "modified", "text"}. `renderedText` and
+    `nextPage` are deliberately NOT surfaced: one would tempt a later change
+    to dedupe against a rendering, the other is a server-chosen URL nothing
+    may fetch."""
+    if not isinstance(raw, dict):
+        raise AdoError(_MISSING_TEXT_MSG)
+    created_by = raw.get("createdBy")
+    author = ""
+    if isinstance(created_by, dict):
+        author = created_by.get("displayName")
+    return {
+        "id": _comment_id(raw),
+        "author": author or "",
+        "created": raw.get("createdDate") or "",
+        "modified": raw.get("modifiedDate") or "",
+        "text": _comment_text(raw),
+    }
+
+
+def _page_total(page):
+    """Extract one page's reported `totalCount` as an int, fail-closed. A
+    missing or non-numeric totalCount must NOT be treated as 0 -- collapsing
+    it to 0 would make the very first page look complete and silently truncate
+    the sweep, defeating comment-based dedupe on a chatty work item."""
+    total = page.get("totalCount")
+    if isinstance(total, bool) or not isinstance(total, (int, float, str)):
+        raise AdoError(_MISSING_TOTAL_MSG)
+    try:
+        return int(total)
+    except (TypeError, ValueError):
+        raise AdoError(_MISSING_TOTAL_MSG) from None
+
+
+def _page_token(page):
+    """Extract one page's `continuationToken`, or None when the sweep is done.
+    A present token that fails CONTINUATION_TOKEN_RE RAISES -- dropping it
+    would end the sweep early and dedupe against a truncated history."""
+    token = page.get("continuationToken")
+    if token is None or token == "":
+        return None
+    if not isinstance(token, str) or not CONTINUATION_TOKEN_RE.fullmatch(token):
+        raise AdoError(_BAD_TOKEN_MSG)
+    return token
+
+
+def _page_comments(page):
+    """The page's `comments` list, fail-closed on any other shape: swallowing
+    a shape change here would silently degrade to 'no comments' and defeat
+    dedupe."""
+    if not isinstance(page, dict):
+        raise AdoError(_MISSING_COMMENTS_MSG)
+    comments = page.get("comments")
+    if not isinstance(comments, list):
+        raise AdoError(_MISSING_COMMENTS_MSG)
+    return comments
+
+
+def _assert_sweep_complete(collected, total, work_item_id):
+    """Refuse a sweep that terminated with fewer comments than the server's
+    own totalCount: deduping against a truncated history double-posts."""
+    if len(collected) < total:
+        raise AdoError(
+            f"read {len(collected)} comment(s) for work item {work_item_id} "
+            f"but Azure DevOps reported totalCount {total}; refusing a "
+            "possibly-truncated comment history")
+
+
+def fetch_comments(api_root, pat, project, work_item_id):
+    """GET the FULL, paginated comment list for one work item, normalized to
+    [{"id", "author", "created", "modified", "text"}, ...] in server order.
+
+    Sweeps until no `continuationToken` comes back, capped at
+    MAX_COMMENT_PAGES so a misbehaving server cannot loop forever, then
+    cross-checks the collected count against the reported totalCount. Every
+    page URL is composed LOCALLY from the validated api_root plus the
+    regex-validated, percent-encoded token: the response's own fully-formed
+    `nextPage` URL is never fetched, because it would pass through neither the
+    host allow-list (which validated the ORG URL, not a URL this client
+    volunteers to fetch) nor the redirect refusal (there is no 3xx to refuse).
+
+    includeDeleted stays at its DEFAULT, so deleted comments are excluded.
+    The consequence is deliberate and belongs in the command's prose: deleting
+    a spec-loop comment in the Azure DevOps web UI RE-ARMS it, and a later
+    armed run posts it again. Setting includeDeleted to true to 'fix' that
+    would make a deleted comment permanently suppress a legitimate re-post."""
+    collected = []
+    total = 0
+    token = None
+    for _ in range(MAX_COMMENT_PAGES):
+        url = comments_url(api_root, project, work_item_id, token)
+        page = _parse_json(_http_get(url, pat).decode("utf-8"), "comment page")
+        total = _page_total(page)
+        collected.extend(_normalize_comment(c) for c in _page_comments(page))
+        token = _page_token(page)
+        if token is None:
+            _assert_sweep_complete(collected, total, work_item_id)
+            return collected
+    raise AdoError(
+        f"comment pagination did not terminate after {MAX_COMMENT_PAGES} "
+        f"pages for work item {work_item_id}; refusing a possibly-truncated "
+        "comment history")
+
+
+# A rendered heading is either html_to_text's HEADING_PREFIX (from an <h1>-<h6>
+# tag) or a bare 'Acceptance Criteria:' line, which is how the section is
+# commonly styled with <b>. KNOWN LOSSINESS, stated rather than claimed away: a
+# <b>-styled pseudo-heading does NOT terminate the section, because the walker
+# renders it as ordinary prose, so a following bold-styled section is included.
+# A real heading tag does terminate it.
+AC_HEADING_RE = re.compile(
+    r"^\s{0,3}(?:#{1,6}\s*)?acceptance\s+criteria\s*:?\s*$", re.IGNORECASE)
+ANY_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
+
+
+def acceptance_criteria_from_description(text):
+    """Extract the 'Acceptance Criteria' section of an already-rendered
+    description: every line after the heading, up to the next heading or the
+    end. Returns '' when no such heading is present. (PURE)"""
+    collected = []
+    inside = False
+    for line in (text or "").splitlines():
+        if not inside:
+            inside = bool(AC_HEADING_RE.match(line))
+            continue
+        if ANY_HEADING_RE.match(line):
+            break
+        collected.append(line)
+    return "\n".join(collected).strip()
+
+
+def resolve_acceptance_criteria(fields, description_text):
+    """Resolve the acceptance criteria in the fixed order and report which
+    source won: the Microsoft.VSTS.Common.AcceptanceCriteria field when it is
+    present and renders non-empty ('field'), else the rendered description's
+    'Acceptance Criteria' section ('description'), else ('', '').
+
+    THE FIELD'S ABSENCE IS NOT A FAILURE. It exists on Bug, Epic, Feature and
+    Product Backlog Item only -- an Agile User Story and a Task have no such
+    field -- so the missing case is the common one. There is no field-catalogue
+    GET to make: the field is either in the flat `fields` map or it is not, so
+    path (1) is a dict lookup rather than an HTTP call. Recording the winning
+    source is what makes the fallback safe: a reader can always tell where the
+    text came from. A field of some other shape (a number, an array) is not
+    criteria text, so it degrades to the description fallback rather than
+    crashing the resolve. (PURE)"""
+    raw = fields.get(FIELD_ACCEPTANCE_CRITERIA)
+    rendered = html_to_text(raw).strip() if isinstance(raw, str) else ""
+    if rendered:
+        return (rendered, "field")
+    from_description = acceptance_criteria_from_description(description_text)
+    if from_description:
+        return (from_description, "description")
+    return ("", "")
+
+
+RECORD_FIELDS = (
+    "org", "project", "id", "web_url", "title", "work_item_type", "state",
+    "description", "acceptance_criteria", "acceptance_criteria_source",
+    "repro_steps", "comments")
+# org, project and id are ALL required: an Azure DevOps work item is a bare
+# integer plus an org and a project, so the triple is what identifies it. A
+# record that cannot name its own org or project cannot be checked against a
+# post-time target, which is the whole defence against a wrong-target write.
+REQUIRED_FIELDS = (
+    "org", "project", "id", "web_url", "title", "work_item_type", "state")
+
+
+def _normalized(values):
+    """Build the inter-slice record in RECORD_FIELDS order -- the single source
+    of truth for the JSON contract shape, so it cannot drift between callers.
+    An empty REQUIRED_FIELDS entry means the API response was incomplete: that
+    is a half-resolve and raises, because a partial record must never be
+    emitted as if it were a whole one. description, acceptance_criteria,
+    acceptance_criteria_source, repro_steps and an empty comments list are all
+    legitimately empty."""
+    record = {name: values[name] for name in RECORD_FIELDS}
+    empty = [name for name in REQUIRED_FIELDS if not record[name]]
+    if empty:
+        raise AdoError(
+            "Azure DevOps returned an incomplete work item: the required "
+            "field(s) " + ", ".join(empty)
+            + " came back empty; refusing to emit a partial record")
+    return record
+
+
+def resolve_work_item(work_item_id):
+    """Resolve one Azure DevOps work-item id READ-ONLY to the normalized
+    record. Credentials come from the environment (see credentials()); every
+    call is fail-closed.
+
+    The read is issued with org + id alone on the project-OPTIONAL route, the
+    project is then taken from the response's own System.TeamProject, and the
+    comment sweep -- where the project is REQUIRED -- uses that derived value.
+    ADO_PROJECT, if set, is only an assertion. The body-supplied web URL is
+    validated against the requested org before it is stored, since it is later
+    displayed where an operator authorizes a write."""
+    api_root, org, pat = credentials()
+    resolved_id = validate_work_item_id(work_item_id)
+    item = fetch_work_item(api_root, pat, resolved_id)
+    fields = item.get("fields") or {}
+    project = resolve_project(fields)
+    assert_project_matches_env(project)
+    description = html_to_text(fields.get(FIELD_DESCRIPTION))
+    criteria, source = resolve_acceptance_criteria(fields, description)
+    href = ((item.get("_links") or {}).get("html") or {}).get("href")
+    # ORDER IS LOAD-BEARING: validate the scalar record FIRST, with an empty
+    # comment list, so a half-resolve (an empty required field, or a spoofed
+    # _links.html.href) refuses BEFORE the comment sweep spends up to
+    # MAX_COMMENT_PAGES network round trips it is going to throw away.
+    record = _normalized({
+        "org": org,
+        "project": project,
+        "id": resolved_id,
+        "web_url": validate_web_url(href, api_root),
+        "title": (fields.get(FIELD_TITLE) or "").strip(),
+        "work_item_type": (fields.get(FIELD_TYPE) or "").strip(),
+        "state": (fields.get(FIELD_STATE) or "").strip(),
+        "description": description,
+        "acceptance_criteria": criteria,
+        "acceptance_criteria_source": source,
+        "repro_steps": html_to_text(fields.get(FIELD_REPRO_STEPS)),
+        "comments": [],
+    })
+    record["comments"] = fetch_comments(api_root, pat, project, resolved_id)
+    return record
+
+
+def main(argv=None):
+    """Placeholder completed in the CLI task; see build_parser/_dispatch."""
+    raise NotImplementedError
+
+
+if __name__ == "__main__":
+    sys.exit(main())
diff --git a/plugins/spec-loop/scripts/test_ado_client.py b/plugins/spec-loop/scripts/test_ado_client.py
new file mode 100644
index 0000000..5ba8dba
--- /dev/null
+++ b/plugins/spec-loop/scripts/test_ado_client.py
@@ -0,0 +1,945 @@
+#!/usr/bin/env python3
+"""Tests for the read-only Azure DevOps work-item reader (stdlib unittest).
+
+Covers work-item-id and org-URL validation (allow-list + argument/URL-injection
+defence), credential resolution and its fail-closed message, the HTML -> text
+renderer, work-item and continuationToken-paginated comment resolution against a
+mocked opener, the normalized-record contract, that the PAT and the composed
+base64(":" + PAT) never leak into an error, stdout or stderr, and the READ-ONLY
+guarantee (the GET helper has no `data` parameter; the module spawns no
+subprocess).
+
+`scripts/validate_marketplace.py` does NOT lint scripts/*.py, so this is the
+sole automated guard on the client. Standard library only. No live network.
+
+Usage:
+    python3 -m unittest test_ado_client
+"""
+
+import argparse
+import base64
+import contextlib
+import inspect
+import io
+import json
+import sys
+import unittest
+import urllib.error
+from pathlib import Path
+from unittest import mock
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+import ado_client as ac  # noqa: E402
+
+
+class TestWorkItemIdValidation(unittest.TestCase):
+    def test_a_plain_integer_id_is_returned_unchanged(self):
+        self.assertEqual(ac.validate_work_item_id("1234"), "1234")
+
+    def test_an_integer_id_is_accepted_as_an_int(self):
+        self.assertEqual(ac.validate_work_item_id(42), "42")
+
+    def test_a_leading_dash_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_work_item_id("-1")
+
+    def test_a_path_traversal_attempt_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_work_item_id("../../etc/passwd")
+
+    def test_an_embedded_slash_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_work_item_id("12/comments")
+
+    def test_a_jira_style_key_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_work_item_id("ABC-123")
+
+    def test_whitespace_and_newlines_are_rejected(self):
+        for bad in (" 12", "12 ", "1\n2", "12\n", ""):
+            with self.assertRaises(ac.AdoUsageError):
+                ac.validate_work_item_id(bad)
+
+    def test_an_over_long_id_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_work_item_id("1" * 11)
+
+
+class TestOrgUrlValidation(unittest.TestCase):
+    def test_the_modern_form_yields_the_org_qualified_api_root(self):
+        expected = ("https://dev.azure.com/contoso", "contoso")
+        self.assertEqual(
+            ac.validate_org_url("https://dev.azure.com/contoso"), expected)
+
+    def test_a_trailing_slash_is_tolerated(self):
+        expected = ("https://dev.azure.com/contoso", "contoso")
+        self.assertEqual(
+            ac.validate_org_url("https://dev.azure.com/contoso/"), expected)
+
+    def test_the_legacy_visualstudio_form_yields_the_bare_origin(self):
+        expected = ("https://contoso.visualstudio.com", "contoso")
+        self.assertEqual(
+            ac.validate_org_url("https://contoso.visualstudio.com"), expected)
+
+    def test_http_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_org_url("http://dev.azure.com/contoso")
+
+    def test_an_on_prem_server_host_is_refused_naming_the_supported_forms(self):
+        with self.assertRaises(ac.AdoUsageError) as ctx:
+            ac.validate_org_url("https://tfs.internal.example.com/tfs/DefaultCollection")
+        message = str(ctx.exception)
+        self.assertIn("dev.azure.com", message)
+        self.assertIn("visualstudio.com", message)
+
+    def test_userinfo_is_rejected_and_never_echoed(self):
+        with self.assertRaises(ac.AdoUsageError) as ctx:
+            ac.validate_org_url("https://user:sekrit@dev.azure.com/contoso")
+        self.assertNotIn("sekrit", str(ctx.exception))
+        self.assertIn("<redacted>", str(ctx.exception))
+
+    def test_an_explicit_port_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_org_url("https://dev.azure.com:8443/contoso")
+
+    def test_a_malformed_ipv6_host_is_a_usage_error_not_a_traceback(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_org_url("https://[oops/contoso")
+
+    def test_a_modern_url_with_no_org_segment_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_org_url("https://dev.azure.com")
+
+    def test_an_extra_path_segment_after_the_org_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_org_url("https://dev.azure.com/contoso/MyProject")
+
+    def test_a_traversal_org_segment_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_org_url("https://dev.azure.com/..")
+
+    def test_a_query_string_is_rejected(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.validate_org_url("https://dev.azure.com/contoso?x=1")
+
+
+class TestApiVersionsAreThreeDistinctConstants(unittest.TestCase):
+    """The work-item read, the comment list and the comment add document
+    DIFFERENT api-versions on purpose. A well-meaning 'consistency' edit that
+    collapses them to one string must fail here rather than silently break
+    either the comment sweep or the write."""
+
+    def test_the_three_api_versions_are_not_all_equal(self):
+        versions = {
+            ac.API_VERSION_WORK_ITEM,
+            ac.API_VERSION_COMMENTS_READ,
+            ac.API_VERSION_COMMENT_ADD,
+        }
+        self.assertEqual(len(versions), 3)
+
+    def test_each_api_version_is_the_documented_literal(self):
+        self.assertEqual(ac.API_VERSION_WORK_ITEM, "7.1")
+        self.assertEqual(ac.API_VERSION_COMMENTS_READ, "7.1-preview.4")
+        self.assertEqual(ac.API_VERSION_COMMENT_ADD, "7.0-preview.3")
+
+
+class TestCredentialsComeFromTheEnvironmentOnly(unittest.TestCase):
+    def test_the_org_url_and_pat_resolve_to_an_api_root(self):
+        env = {"ADO_ORG_URL": "https://dev.azure.com/contoso", "ADO_PAT": "tok"}
+        with mock.patch.dict(ac.os.environ, env, clear=True):
+            self.assertEqual(
+                ac.credentials(),
+                ("https://dev.azure.com/contoso", "contoso", "tok"))
+
+    def test_a_missing_variable_is_named_in_a_fail_closed_message(self):
+        with mock.patch.dict(ac.os.environ, {}, clear=True):
+            with self.assertRaises(ac.AdoUsageError) as ctx:
+                ac.credentials()
+        message = str(ctx.exception)
+        self.assertIn("ADO_ORG_URL", message)
+        self.assertIn("ADO_PAT", message)
+
+    def test_the_message_describes_ado_project_as_optional_not_required(self):
+        with mock.patch.dict(ac.os.environ, {}, clear=True):
+            with self.assertRaises(ac.AdoUsageError) as ctx:
+                ac.credentials()
+        message = str(ctx.exception)
+        self.assertIn("ADO_PROJECT", message)
+        # Case-insensitive on purpose: the message says "is OPTIONAL".
+        self.assertIn("optional", message.lower())
+
+    def test_only_the_org_url_and_pat_are_required_credentials(self):
+        self.assertEqual(ac.CRED_VARS, ("ADO_ORG_URL", "ADO_PAT"))
+
+    def test_no_cli_flag_can_supply_a_credential(self):
+        """Deliberately MODULE-WIDE, and one of only three scans here that
+        is (the others are import subprocess and renderedText): a credential
+        flag must not exist on ANY lane, including the bounded write lane a
+        later slice adds, and these exact spellings appear in no docstring in
+        this module -- the prose names the ENV VARS (ADO_PAT, ADO_ORG_URL),
+        never a flag. Task 7 adds the stronger companion assertion against
+        the parser's real option strings."""
+        source = inspect.getsource(ac)
+        for forbidden in ("--pat", "--token", "--password", "--org-url"):
+            self.assertNotIn(forbidden, source, forbidden)
+
+
+class TestHttpGetIsStructurallyIncapableOfWriting(unittest.TestCase):
+    def test_http_get_has_no_data_parameter(self):
+        """urllib.request.Request infers POST from a non-None `data`, so
+        omitting the parameter from the signature ENTIRELY -- rather than
+        passing data=None -- means this function has no expressible write
+        path. That absence is the proof."""
+        params = list(inspect.signature(ac._http_get).parameters)
+        self.assertEqual(params, ["url", "pat"])
+
+    def test_http_get_has_no_method_parameter_for_a_caller_to_widen(self):
+        self.assertNotIn("method", inspect.signature(ac._http_get).parameters)
+
+    def test_the_get_helper_names_no_mutating_verb(self):
+        """Scoped to _http_get's OWN source, not the whole module -- exactly
+        as test_jira_client.py:1544-1552 does. A later slice adds a bounded
+        writer to this module; that must not be able to loosen THIS
+        guarantee, and this test must not have to be deleted to allow it."""
+        source = inspect.getsource(ac._http_get)
+        verbs = (
+            '"POST"', '"PUT"', '"PATCH"', '"DELETE"',
+            "'POST'", "'PUT'", "'PATCH'", "'DELETE'",
+        )
+        for verb in verbs:
+            self.assertNotIn(verb, source, verb)
+
+    def test_the_get_helper_sets_no_body_and_pins_get(self):
+        source = inspect.getsource(ac._http_get)
+        self.assertNotIn("data=", source)
+        self.assertIn('method="GET"', source)
+
+    # NOTE: the companion assertion that no READ FUNCTION can reach a writer
+    # needs fetch_comments and resolve_work_item to exist, so it lands in
+    # Task 6 as TestTheReadLaneStaysReadOnly. Do not add it here; the
+    # functions it iterates are not defined yet and it would AttributeError.
+
+    def test_the_module_never_imports_subprocess(self):
+        """Module-wide on purpose (test_jira_client.py:1560 makes the same
+        exception for this exact token): no subprocess anywhere means no `az`
+        CLI, on any lane, now or later. The word appears in no docstring in
+        this module -- the prose says "No subprocess", not "import
+        subprocess"."""
+        source = inspect.getsource(ac)
+        self.assertNotIn("import subprocess", source)
+        self.assertNotIn("shutil.which", source)
+
+    def test_the_request_is_a_get_with_no_body(self):
+        captured = {}
+
+        class _Resp:
+            def __enter__(self):
+                return self
+
+            def __exit__(self, *exc):
+                return False
+
+            def read(self):
+                return b"{}"
+
+        def _open(req, timeout=None):
+            captured["req"] = req
+            captured["timeout"] = timeout
+            return _Resp()
+
+        with mock.patch.object(ac._OPENER, "open", _open):
+            self.assertEqual(
+                ac._http_get("https://dev.azure.com/x", "tok"), b"{}")
+        self.assertEqual(captured["req"].get_method(), "GET")
+        self.assertIsNone(captured["req"].data)
+        self.assertEqual(captured["timeout"], 30)
+
+
+class TestRedirectsAreRefused(unittest.TestCase):
+    def test_redirect_request_returns_none(self):
+        handler = ac._NoRedirect()
+        self.assertIsNone(handler.redirect_request(
+            None, None, 302, "Found", {}, "https://evil.example.com/"))
+
+    def test_the_module_opener_installs_the_no_redirect_handler(self):
+        handlers = ac._OPENER.handlers
+        self.assertTrue(any(isinstance(h, ac._NoRedirect) for h in handlers))
+
+
+class TestTheSecretNeverLeaks(unittest.TestCase):
+    def test_the_auth_header_is_basic_with_an_empty_username(self):
+        expected = "Basic " + base64.b64encode(b":tok").decode("ascii")
+        self.assertEqual(ac._auth_header("tok"), expected)
+
+    def test_an_http_error_message_names_only_the_url(self):
+        url = "https://dev.azure.com/contoso/_apis/wit/workitems/1"
+        error = urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)
+        # An HTTPError IS a response object (addinfourl extends
+        # tempfile._TemporaryFileWrapper), so an unclosed one emits a
+        # ResourceWarning to stderr whenever the collector gets to it --
+        # landing in whichever test happens to be capturing stderr then.
+        # Closed deterministically here so this file leaks no warning into
+        # another test module.
+        self.addCleanup(error.close)
+        with mock.patch.object(ac._OPENER, "open", side_effect=error):
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac._http_get(url, "sekrit-pat")
+        message = str(ctx.exception)
+        self.assertIn("401", message)
+        self.assertNotIn("sekrit-pat", message)
+        self.assertNotIn(
+            base64.b64encode(b":sekrit-pat").decode("ascii"), message)
+
+    def test_a_url_error_is_an_ado_error_not_a_traceback(self):
+        error = urllib.error.URLError("no route to host")
+        with mock.patch.object(ac._OPENER, "open", side_effect=error):
+            with self.assertRaises(ac.AdoError):
+                ac._http_get("https://dev.azure.com/x", "tok")
+
+    def test_a_bare_oserror_while_reading_is_also_an_ado_error(self):
+        reset = OSError("connection reset")
+        with mock.patch.object(ac._OPENER, "open", side_effect=reset):
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac._http_get("https://dev.azure.com/x", "sekrit-pat")
+        self.assertNotIn("sekrit-pat", str(ctx.exception))
+
+
+class TestJsonParseFailsClosed(unittest.TestCase):
+    def test_a_malformed_response_is_an_actionable_ado_error(self):
+        with self.assertRaises(ac.AdoError) as ctx:
+            ac._parse_json("{not json", "work item")
+        self.assertIn("work item", str(ctx.exception))
+
+
+class TestHtmlToTextIsLossyButFaithful(unittest.TestCase):
+    def test_none_and_a_non_string_render_empty(self):
+        for raw in (None, "", 17, [], {}):
+            self.assertEqual(ac.html_to_text(raw), "")
+
+    def test_plain_text_survives(self):
+        self.assertEqual(ac.html_to_text("hello world"), "hello world")
+
+    def test_divs_and_paragraphs_become_blank_line_separated_blocks(self):
+        self.assertEqual(
+            ac.html_to_text("<div>one</div><div>two</div>"), "one\n\ntwo")
+        self.assertEqual(
+            ac.html_to_text("<p>one</p><p>two</p>"), "one\n\ntwo")
+
+    def test_a_br_is_a_single_line_break(self):
+        self.assertEqual(ac.html_to_text("one<br>two"), "one\ntwo")
+        self.assertEqual(ac.html_to_text("one<br/>two"), "one\ntwo")
+
+    def test_list_items_render_as_dash_bullets(self):
+        self.assertEqual(
+            ac.html_to_text("<ul><li>a</li><li>b</li></ul>"), "- a\n- b")
+
+    def test_nested_lists_still_render_every_item(self):
+        rendered = ac.html_to_text(
+            "<ul><li>a<ul><li>b</li></ul></li></ul>")
+        self.assertIn("- a", rendered)
+        self.assertIn("- b", rendered)
+
+    def test_headings_get_the_heading_prefix(self):
+        self.assertEqual(ac.html_to_text("<h3>Details</h3><p>x</p>"),
+                         "## Details\n\nx")
+
+    def test_entities_are_unescaped(self):
+        self.assertEqual(ac.html_to_text("a &amp; b &lt;c&gt; &nbsp;d"),
+                         "a & b <c>  d")
+
+    def test_script_and_style_content_is_dropped(self):
+        self.assertEqual(
+            ac.html_to_text("<p>keep</p><script>alert(1)</script>"), "keep")
+        self.assertEqual(
+            ac.html_to_text("<style>p{color:red}</style><p>keep</p>"), "keep")
+
+    def test_an_html_comment_is_dropped(self):
+        self.assertEqual(ac.html_to_text("<p>keep</p><!-- hidden -->"), "keep")
+
+    def test_runs_of_blank_lines_collapse_to_one(self):
+        self.assertEqual(
+            ac.html_to_text("<div>a</div><div></div><div></div><div>b</div>"),
+            "a\n\nb")
+
+    def test_unclosed_and_unknown_tags_do_not_lose_their_text(self):
+        self.assertEqual(ac.html_to_text("<div><span>a<div>b"), "a\n\nb")
+        self.assertIn("a", ac.html_to_text("<marquee>a</marquee>"))
+
+    def test_malformed_tag_soup_never_raises(self):
+        for raw in ("<<<>>>", "<div", "a < b", "</p></p>", "<br" * 200):
+            ac.html_to_text(raw)
+
+
+def work_item(**overrides):
+    """One raw work-item response object, shaped like the documented payload.
+    Field overrides are merged into `fields`; a top-level override (e.g.
+    _links) replaces that key."""
+    fields = {
+        ac.FIELD_TITLE: "Make the widget spin",
+        ac.FIELD_DESCRIPTION: "<div>spin it</div>",
+        ac.FIELD_TYPE: "User Story",
+        ac.FIELD_PROJECT: "Contoso Platform",
+        ac.FIELD_STATE: "Active",
+    }
+    fields.update({k: v for k, v in overrides.items() if k.count(".")})
+    href = ("https://dev.azure.com/contoso/Contoso%20Platform"
+            "/_workitems/edit/1234")
+    payload = {
+        "id": 1234,
+        "fields": fields,
+        "_links": {"html": {"href": href}},
+    }
+    payload.update({k: v for k, v in overrides.items() if not k.count(".")})
+    return payload
+
+
+class TestUrlsAreComposedLocally(unittest.TestCase):
+    def test_the_work_item_url_omits_the_project_and_pins_its_api_version(self):
+        url = ac.work_item_url("https://dev.azure.com/contoso", "1234")
+        self.assertEqual(
+            url,
+            "https://dev.azure.com/contoso/_apis/wit/workitems/1234"
+            "?api-version=7.1")
+
+    def test_the_work_item_url_percent_encodes_the_id_it_was_given(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.work_item_url("https://dev.azure.com/contoso", "1/../2")
+
+    def test_the_comments_url_carries_the_encoded_project_and_its_api_version(self):
+        url = ac.comments_url(
+            "https://dev.azure.com/contoso", "Contoso Platform", "1234")
+        self.assertEqual(
+            url,
+            "https://dev.azure.com/contoso/Contoso%20Platform/_apis/wit/"
+            "workItems/1234/comments?api-version=7.1-preview.4"
+            "&$top=100")
+
+    def test_the_comments_url_encodes_a_slash_in_a_project_name(self):
+        url = ac.comments_url("https://dev.azure.com/contoso", "a/b", "1")
+        self.assertIn("a%2Fb", url)
+        self.assertNotIn("/a/b/", url)
+
+    def test_no_url_composer_reads_anything_from_a_response_body(self):
+        """Function-scoped, and docstring-stripped, ON PURPOSE. The module's
+        docstrings are load-bearing doctrine whose JOB is to discuss
+        `nextPage`, so a whole-module token scan would fail against the
+        repo's own required prose (and would tempt an executor to weaken the
+        assertion instead of the code). What must hold is that the URL
+        composers read nothing from a response body. The behavioural proof
+        that the hostile `nextPage` in the fixture is never fetched lives in
+        Task 5's test_the_server_supplied_next_page_url_is_never_fetched;
+        this is the structural companion. Never weaken either -- conventions
+        §23 is a blocking rule."""
+        for fn in (ac.work_item_url, ac.comments_url):
+            with self.subTest(fn=fn.__name__):
+                source = inspect.getsource(fn)
+                parts = source.split('"""')
+                code = parts[2] if len(parts) >= 3 else source
+                self.assertNotIn("nextPage", code)
+                self.assertNotIn("_links", code)
+
+
+class TestTheProjectComesFromTheRead(unittest.TestCase):
+    def test_the_project_is_taken_from_system_teamproject(self):
+        fields = {ac.FIELD_PROJECT: "Contoso Platform"}
+        self.assertEqual(ac.resolve_project(fields), "Contoso Platform")
+
+    def test_a_missing_project_is_a_half_resolve_and_raises(self):
+        shapes = (
+            {},
+            {ac.FIELD_PROJECT: ""},
+            {ac.FIELD_PROJECT: "   "},
+            {ac.FIELD_PROJECT: 7},
+        )
+        for fields in shapes:
+            with self.assertRaises(ac.AdoError):
+                ac.resolve_project(fields)
+
+    def test_a_project_name_with_a_control_character_is_refused_not_rewritten(self):
+        for bad in ("a\nb", "a\rb", "a\x00b", "a\tb"):
+            with self.assertRaises(ac.AdoError):
+                ac.resolve_project({ac.FIELD_PROJECT: bad})
+
+    def test_an_unset_ado_project_asserts_nothing(self):
+        with mock.patch.dict(ac.os.environ, {}, clear=True):
+            self.assertIsNone(ac.assert_project_matches_env("Contoso Platform"))
+
+    def test_a_matching_ado_project_passes(self):
+        env = {"ADO_PROJECT": " Contoso Platform "}
+        with mock.patch.dict(ac.os.environ, env, clear=True):
+            self.assertIsNone(ac.assert_project_matches_env("Contoso Platform"))
+
+    def test_a_mismatched_ado_project_refuses_and_names_both_values(self):
+        env = {"ADO_PROJECT": "Other"}
+        with mock.patch.dict(ac.os.environ, env, clear=True):
+            with self.assertRaises(ac.AdoUsageError) as ctx:
+                ac.assert_project_matches_env("Contoso Platform")
+        message = str(ctx.exception)
+        self.assertIn("Other", message)
+        self.assertIn("Contoso Platform", message)
+
+
+class TestTheWebUrlIsValidatedBeforeItIsEverDisplayed(unittest.TestCase):
+    def test_an_href_under_the_validated_api_root_is_returned(self):
+        href = ("https://dev.azure.com/contoso/Contoso%20Platform"
+                "/_workitems/edit/1234")
+        root = "https://dev.azure.com/contoso"
+        self.assertEqual(ac.validate_web_url(href, root), href)
+
+    def test_the_host_comparison_is_case_insensitive(self):
+        href = "https://DEV.AZURE.COM/contoso/_workitems/edit/1"
+        root = "https://dev.azure.com/contoso"
+        self.assertEqual(ac.validate_web_url(href, root), href)
+
+    def test_an_href_on_another_origin_is_refused(self):
+        hrefs = (
+            "https://evil.example.com/contoso/_workitems/edit/1",
+            "http://dev.azure.com/contoso/_workitems/edit/1",
+            "https://dev.azure.com/otherorg/_workitems/edit/1",
+            "https://dev.azure.com.evil.example/contoso/x",
+            "javascript:alert(1)", "", None, 42,
+        )
+        for bad in hrefs:
+            with self.assertRaises(ac.AdoError):
+                ac.validate_web_url(bad, "https://dev.azure.com/contoso")
+
+    def test_a_prefix_lookalike_org_is_refused(self):
+        bad = "https://dev.azure.com/contoso-evil/_workitems/edit/1"
+        with self.assertRaises(ac.AdoError):
+            ac.validate_web_url(bad, "https://dev.azure.com/contoso")
+
+    def test_a_mismatched_href_names_the_other_host_but_not_its_path(self):
+        bad = ("https://contoso.visualstudio.com/Contoso%20Platform"
+               "/_workitems/edit/1234?secret=leak")
+        with self.assertRaises(ac.AdoError) as ctx:
+            ac.validate_web_url(bad, "https://dev.azure.com/contoso")
+        message = str(ctx.exception)
+        self.assertIn("https://dev.azure.com/contoso", message)
+        self.assertIn("https://contoso.visualstudio.com", message)
+        self.assertNotIn("_workitems", message)
+        self.assertNotIn("secret", message)
+
+
+class TestFetchWorkItem(unittest.TestCase):
+    def test_the_read_issues_one_get_to_the_locally_composed_url(self):
+        payload = json.dumps(work_item()).encode("utf-8")
+        with mock.patch.object(ac, "_http_get", return_value=payload) as get:
+            item = ac.fetch_work_item(
+                "https://dev.azure.com/contoso", "tok", "1234")
+        self.assertEqual(item["id"], 1234)
+        get.assert_called_once_with(
+            "https://dev.azure.com/contoso/_apis/wit/workitems/1234"
+            "?api-version=7.1", "tok")
+
+    def test_a_non_object_response_is_a_contract_failure(self):
+        with mock.patch.object(ac, "_http_get", return_value=b"[]"):
+            with self.assertRaises(ac.AdoError):
+                ac.fetch_work_item("https://dev.azure.com/contoso", "tok", "1")
+
+
+def raw_comment(cid, text, author="Ada", id_key="id"):
+    """One raw comment object. `id_key` selects which of the two documented
+    spellings carries the id: the definition table names it `id`, while
+    Microsoft's own sample payloads show `commentId`."""
+    return {
+        id_key: cid,
+        "text": text,
+        "createdBy": {"displayName": author},
+        "createdDate": "2026-09-14T10:00:00Z",
+        "modifiedDate": "2026-09-14T10:00:00Z",
+    }
+
+
+def comment_page(comments, total, token=None):
+    """One raw comment-list page. Every page also carries a server-chosen
+    `nextPage` URL, which this client must never fetch -- it is included in
+    the fixture pointing at a hostile origin precisely so a test can prove the
+    client ignores it."""
+    page = {
+        "comments": comments,
+        "totalCount": total,
+        "nextPage": "https://evil.example.com/steal-the-pat",
+    }
+    if token is not None:
+        page["continuationToken"] = token
+    return page
+
+
+class TestTheCommentSweepIsFailClosed(unittest.TestCase):
+    API_ROOT = "https://dev.azure.com/contoso"
+    SWEEP_ARGS = (API_ROOT, "tok", "Contoso Platform", "1234")
+
+    def _sweep(self, pages):
+        bodies = [json.dumps(p).encode("utf-8") for p in pages]
+        with mock.patch.object(ac, "_http_get", side_effect=bodies) as get:
+            result = ac.fetch_comments(*self.SWEEP_ARGS)
+        return result, get
+
+    def _assert_sweep_refuses(self, page):
+        """Sweep one fail-closed page and require the refusal. Extracted so
+        each integrity rule below reads `for case -> subTest -> assert` at
+        three levels of nesting instead of four."""
+        with self.assertRaises(ac.AdoError):
+            self._sweep([page])
+
+    def test_a_single_page_sweep_normalizes_every_comment(self):
+        raws = [raw_comment(1, "hello"), raw_comment(2, "world")]
+        comments, _ = self._sweep([comment_page(raws, 2)])
+        self.assertEqual([c["text"] for c in comments], ["hello", "world"])
+        self.assertEqual([c["id"] for c in comments], ["1", "2"])
+        self.assertEqual(comments[0]["author"], "Ada")
+        self.assertEqual(comments[0]["created"], "2026-09-14T10:00:00Z")
+
+    def test_an_empty_history_is_a_legitimate_empty_list(self):
+        comments, _ = self._sweep([comment_page([], 0)])
+        self.assertEqual(comments, [])
+
+    def test_the_sweep_follows_the_continuation_token_it_composes_itself(self):
+        pages = [
+            comment_page([raw_comment(1, "a")], 2, token="TOKEN-2"),
+            comment_page([raw_comment(2, "b")], 2),
+        ]
+        comments, get = self._sweep(pages)
+        self.assertEqual([c["text"] for c in comments], ["a", "b"])
+        second_url = get.call_args_list[1].args[0]
+        self.assertIn("continuationToken=TOKEN-2", second_url)
+        self.assertTrue(
+            second_url.startswith("https://dev.azure.com/contoso/"))
+
+    def test_the_server_supplied_next_page_url_is_never_fetched(self):
+        pages = [
+            comment_page([raw_comment(1, "a")], 2, token="TOKEN-2"),
+            comment_page([raw_comment(2, "b")], 2),
+        ]
+        _, get = self._sweep(pages)
+        for call in get.call_args_list:
+            self.assertNotIn("evil.example.com", call.args[0])
+
+    def test_a_comment_id_spelled_commentid_is_accepted(self):
+        raws = [raw_comment(9, "a", id_key="commentId")]
+        comments, _ = self._sweep([comment_page(raws, 1)])
+        self.assertEqual(comments[0]["id"], "9")
+
+    def test_a_comment_with_no_text_raises_rather_than_shrink_the_haystack(self):
+        broken_comments = (
+            {"id": 1},
+            {"id": 1, "text": ""},
+            {"id": 1, "text": None},
+            {"id": 1, "text": 7},
+        )
+        for broken in broken_comments:
+            with self.subTest(broken=broken):
+                self._assert_sweep_refuses(comment_page([broken], 1))
+
+    def test_a_missing_or_non_numeric_total_count_raises(self):
+        pages = (
+            {"comments": []},
+            {"comments": [], "totalCount": None},
+            {"comments": [], "totalCount": "lots"},
+        )
+        for page in pages:
+            with self.subTest(page=page):
+                self._assert_sweep_refuses(page)
+
+    def test_a_page_missing_the_comments_list_raises(self):
+        pages = (
+            {"totalCount": 1},
+            {"comments": {}, "totalCount": 1},
+            {"comments": "a", "totalCount": 1},
+        )
+        for page in pages:
+            with self.subTest(page=page):
+                self._assert_sweep_refuses(page)
+
+    def test_terminating_with_fewer_comments_than_total_count_raises(self):
+        with self.assertRaises(ac.AdoError) as ctx:
+            self._sweep([comment_page([raw_comment(1, "a")], 5)])
+        self.assertIn("5", str(ctx.exception))
+
+    def test_a_continuation_token_that_fails_its_allow_list_raises(self):
+        for bad in ("tok en", "tok\n", "a" * 513, "tok&x=1", 42, []):
+            with self.subTest(bad=bad):
+                page = comment_page([raw_comment(1, "a")], 2, token=bad)
+                self._assert_sweep_refuses(page)
+
+    def test_a_traversal_shaped_token_is_neutralised_by_percent_encoding(self):
+        """CONTINUATION_TOKEN_RE is pinned verbatim by conventions §31 and it
+        permits '.', '/' and '-', so '../etc' MATCHES the allow-list. That is
+        not a hole, and the regex is NOT what defends here: the token only
+        ever lands in a query PARAMETER, quote(safe="")-encoded, so no path
+        traversal is expressible. Assert the real defence directly rather
+        than asserting a rejection that does not (and need not) happen."""
+        url = ac.comments_url(
+            "https://dev.azure.com/contoso", "P", "1", "../etc")
+        self.assertIn("continuationToken=..%2Fetc", url)
+        self.assertNotIn("../etc", url)
+        self.assertNotIn("/etc", url)
+
+    def test_an_unterminated_sweep_is_capped_and_raises(self):
+        page = comment_page([raw_comment(1, "a")], 10 ** 6, token="TOKEN")
+        bodies = [json.dumps(page).encode("utf-8")] * (ac.MAX_COMMENT_PAGES + 1)
+        with mock.patch.object(ac, "_http_get", side_effect=bodies):
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac.fetch_comments(*self.SWEEP_ARGS)
+        self.assertIn(str(ac.MAX_COMMENT_PAGES), str(ctx.exception))
+
+    def test_deleted_comments_stay_excluded(self):
+        """includeDeleted stays at its default. Setting it would let a comment
+        deleted in the web UI permanently suppress a legitimate re-post.
+
+        Scoped to comments_url -- the only function that can send the
+        parameter -- and matched as `includeDeleted=`, because conventions
+        §24.3 REQUIRES the module and fetch_comments docstrings to document
+        this consequence by name. A whole-module scan for the bare word would
+        fail against that mandated prose."""
+        source = inspect.getsource(ac.comments_url)
+        self.assertNotIn("includeDeleted=", source)
+        self.assertNotIn(
+            "includeDeleted=true", inspect.getsource(ac.fetch_comments))
+
+
+class TestTheDedupeHaystackComesFromStoredTextOnly(unittest.TestCase):
+    """A marker is matched against what was STORED. renderedText is an
+    optional HTML RENDERING that a renderer may entity-encode or strip; a
+    marker it altered would go unmatched and the comment lane would post
+    again on a live work item. This test fails if the gate is ever
+    repointed."""
+
+    def test_the_normalized_text_is_the_stored_text_not_the_rendered_text(self):
+        raw = raw_comment(1, "[spec-loop-intake:decision:0123456789ab] body")
+        raw["renderedText"] = "<p>totally different</p>"
+        normalized = ac._normalize_comment(raw)
+        self.assertEqual(normalized["text"], raw["text"])
+        self.assertNotIn("renderedText", normalized)
+
+    def test_the_module_never_mentions_rendered_text_as_a_data_source(self):
+        """Module-wide but QUOTE-SCOPED: it looks for the field being used as
+        a dict KEY ('"renderedText"'), not for the bare word. The docstrings
+        must stay free to explain why renderedText is not the haystack, and
+        they name it with backticks, so this cannot fire on its own required
+        prose."""
+        source = inspect.getsource(ac)
+        self.assertNotIn('"renderedText"', source)
+        self.assertNotIn("'renderedText'", source)
+
+
+class TestAcceptanceCriteriaResolveInAFixedOrder(unittest.TestCase):
+    def test_the_field_wins_when_present_and_non_empty(self):
+        fields = {ac.FIELD_ACCEPTANCE_CRITERIA: "<ul><li>it spins</li></ul>"}
+        resolved = ac.resolve_acceptance_criteria(
+            fields, "## Acceptance Criteria\n\nfrom desc")
+        self.assertEqual(resolved, ("- it spins", "field"))
+
+    def test_an_absent_field_is_the_common_case_not_a_failure(self):
+        """An Agile User Story and a Task have no acceptance-criteria field at
+        all, so its absence must fall through to the description."""
+        rendered = "intro\n\n## Acceptance Criteria\n\n- it spins\n- it stops"
+        self.assertEqual(
+            ac.resolve_acceptance_criteria({}, rendered),
+            ("- it spins\n- it stops", "description"))
+
+    def test_an_empty_field_falls_through_to_the_description(self):
+        fields = {ac.FIELD_ACCEPTANCE_CRITERIA: "<div>   </div>"}
+        rendered = "## Acceptance Criteria\n\n- it spins"
+        self.assertEqual(
+            ac.resolve_acceptance_criteria(fields, rendered),
+            ("- it spins", "description"))
+
+    def test_a_field_of_an_unexpected_shape_degrades_rather_than_crashes(self):
+        for raw in (7, [], {}, None):
+            fields = {ac.FIELD_ACCEPTANCE_CRITERIA: raw}
+            self.assertEqual(
+                ac.resolve_acceptance_criteria(fields, ""), ("", ""))
+
+    def test_neither_source_yields_an_empty_pair(self):
+        self.assertEqual(
+            ac.resolve_acceptance_criteria({}, "just prose"), ("", ""))
+
+    def test_the_section_stops_at_the_next_heading(self):
+        rendered = (
+            "## Acceptance Criteria\n\n- it spins\n\n"
+            "## Notes\n\nnot criteria")
+        criteria, source = ac.resolve_acceptance_criteria({}, rendered)
+        self.assertEqual(criteria, "- it spins")
+        self.assertEqual(source, "description")
+        self.assertNotIn("not criteria", criteria)
+
+    def test_the_heading_match_is_case_and_colon_insensitive(self):
+        headings = (
+            "## acceptance criteria", "## ACCEPTANCE CRITERIA:",
+            "Acceptance Criteria:", "acceptance  criteria")
+        for heading in headings:
+            resolved = ac.resolve_acceptance_criteria(
+                {}, f"{heading}\n\n- it spins")
+            self.assertEqual(resolved, ("- it spins", "description"))
+
+
+class TestTheNormalizedRecord(unittest.TestCase):
+    def _values(self, **overrides):
+        """Every RECORD_FIELDS value for a whole, resolvable work item, with
+        the optional ones already at their legitimately-empty value."""
+        values = {
+            "org": "contoso",
+            "project": "Contoso Platform",
+            "id": "1234",
+            "web_url": "https://dev.azure.com/contoso/_workitems/edit/1234",
+            "title": "Make the widget spin",
+            "work_item_type": "User Story",
+            "state": "Active",
+            "description": "",
+            "acceptance_criteria": "",
+            "acceptance_criteria_source": "",
+            "repro_steps": "",
+            "comments": [],
+        }
+        values.update(overrides)
+        return values
+
+    def test_the_record_is_built_in_record_fields_order(self):
+        record = ac._normalized(self._values())
+        self.assertEqual(list(record), list(ac.RECORD_FIELDS))
+
+    def test_org_project_and_id_are_all_required(self):
+        for field in ("org", "project", "id"):
+            self.assertIn(field, ac.REQUIRED_FIELDS)
+
+    def test_an_empty_required_field_is_a_half_resolve_and_raises(self):
+        for field in ac.REQUIRED_FIELDS:
+            values = self._values(**{field: ""})
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac._normalized(values)
+            self.assertIn(field, str(ctx.exception))
+
+    def test_the_optional_fields_are_legitimately_empty(self):
+        record = ac._normalized(self._values())
+        self.assertEqual(record["description"], "")
+        self.assertEqual(record["comments"], [])
+
+    def test_rendered_text_and_next_page_are_not_record_fields(self):
+        absent = ("rendered_text", "renderedText", "next_page", "nextPage")
+        for name in absent:
+            self.assertNotIn(name, ac.RECORD_FIELDS)
+
+
+class TestResolveWorkItem(unittest.TestCase):
+    ENV = {"ADO_ORG_URL": "https://dev.azure.com/contoso", "ADO_PAT": "tok"}
+
+    def _patched(self, item, comments=None, env=None):
+        """Enter the environment patch and both transport patches on ONE
+        contextlib.ExitStack and return it, already entered, alongside the
+        fetch_work_item and fetch_comments mocks. One stack rather than three
+        nested `with` blocks keeps each test flat, and holding the two mocks is
+        what lets a test assert an ORDER property -- that a refusal costs zero
+        requests."""
+        stack = contextlib.ExitStack()
+        stack.enter_context(
+            mock.patch.dict(ac.os.environ, env or self.ENV, clear=True))
+        read = stack.enter_context(
+            mock.patch.object(ac, "fetch_work_item", return_value=item))
+        comment_patch = mock.patch.object(
+            ac, "fetch_comments", return_value=comments or [])
+        sweep = stack.enter_context(comment_patch)
+        return stack, read, sweep
+
+    def _resolve(self, item, comments=None, env=None):
+        stack, _read, _sweep = self._patched(item, comments, env)
+        with stack:
+            return ac.resolve_work_item("1234")
+
+    def test_a_user_story_resolves_to_the_whole_record(self):
+        record = self._resolve(work_item())
+        self.assertEqual(record["org"], "contoso")
+        self.assertEqual(record["project"], "Contoso Platform")
+        self.assertEqual(record["id"], "1234")
+        self.assertEqual(record["title"], "Make the widget spin")
+        self.assertEqual(record["work_item_type"], "User Story")
+        self.assertEqual(record["state"], "Active")
+        self.assertEqual(record["description"], "spin it")
+        self.assertEqual(record["acceptance_criteria_source"], "")
+        self.assertEqual(record["repro_steps"], "")
+
+    def test_a_bugs_repro_steps_land_in_their_own_field_not_the_description(self):
+        item = work_item(**{
+            ac.FIELD_TYPE: "Bug",
+            ac.FIELD_DESCRIPTION: "",
+            ac.FIELD_REPRO_STEPS: "<ol><li>click it</li></ol>",
+        })
+        record = self._resolve(item)
+        self.assertEqual(record["repro_steps"], "- click it")
+        self.assertEqual(record["description"], "")
+
+    def test_the_resolved_comments_are_the_swept_comments(self):
+        comment = {
+            "id": "1", "author": "Ada", "created": "", "modified": "",
+            "text": "hello",
+        }
+        comments = [comment]
+        record = self._resolve(work_item(), comments=comments)
+        self.assertEqual(record["comments"], comments)
+
+    def test_the_comment_sweep_is_called_with_the_project_from_the_read(self):
+        stack, _read, sweep = self._patched(work_item())
+        with stack:
+            ac.resolve_work_item("1234")
+        sweep.assert_called_once_with(
+            "https://dev.azure.com/contoso", "tok", "Contoso Platform", "1234")
+
+    def test_a_mismatched_ado_project_refuses_the_resolve(self):
+        env = dict(self.ENV, ADO_PROJECT="SomethingElse")
+        with self.assertRaises(ac.AdoUsageError):
+            self._resolve(work_item(), env=env)
+
+    def test_an_href_on_another_origin_refuses_the_resolve(self):
+        item = work_item(_links={"html": {"href": "https://evil.example.com/x"}})
+        with self.assertRaises(ac.AdoError):
+            self._resolve(item)
+
+    def test_a_work_item_with_no_title_is_a_half_resolve(self):
+        item = work_item(**{ac.FIELD_TITLE: ""})
+        with self.assertRaises(ac.AdoError):
+            self._resolve(item)
+
+    def test_the_id_is_validated_before_any_request(self):
+        stack, read, _sweep = self._patched(work_item())
+        with stack:
+            with self.assertRaises(ac.AdoUsageError):
+                ac.resolve_work_item("../../etc/passwd")
+        read.assert_not_called()
+
+    def test_a_half_resolve_refuses_before_it_sweeps_any_comment(self):
+        """An empty required field is a half-resolve. It must cost ZERO
+        comment requests, not a full MAX_COMMENT_PAGES sweep."""
+        item = work_item(**{ac.FIELD_TITLE: "   "})
+        stack, _read, sweep = self._patched(item)
+        with stack:
+            with self.assertRaises(ac.AdoError):
+                ac.resolve_work_item("1234")
+        sweep.assert_not_called()
+
+
+class TestTheReadLaneStaysReadOnly(unittest.TestCase):
+    """The read path is CLOSED: no read function so much as names a writer,
+    so any bounded writer added to this module later is reachable only from
+    its own explicitly-authorized entry point. Scoped per function on
+    purpose (the shape of
+    plugins/spec-loop/scripts/test_jira_client.py:1554), so a later slice
+    ADDS a writer and its own tests rather than deleting these."""
+
+    WRITERS = ("_http_post", "_http_patch", "_http_put", "_http_delete")
+
+    def test_no_read_function_can_reach_a_writer(self):
+        reads = (ac.fetch_work_item, ac.fetch_comments, ac.resolve_work_item,
+                 ac.work_item_url, ac.comments_url)
+        for fn in reads:
+            with self.subTest(fn=fn.__name__):
+                self._assert_names_no_writer(inspect.getsource(fn))
+
+    def _assert_names_no_writer(self, source):
+        for writer in self.WRITERS:
+            self.assertNotIn(writer, source, writer)
+
+    def test_the_only_network_entry_point_the_read_lane_uses_is_http_get(self):
+        for fn in (ac.fetch_work_item, ac.fetch_comments):
+            with self.subTest(fn=fn.__name__):
+                self.assertIn("_http_get(", inspect.getsource(fn))
