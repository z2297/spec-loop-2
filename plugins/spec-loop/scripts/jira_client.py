#!/usr/bin/env python3
"""Read-only Jira Cloud issue reader (standard library only).

Resolves one Jira issue key to a normalized JSON record (key, summary,
description, acceptance criteria, status, issue type, web url, and the full
paginated comment list), authenticating with HTTP Basic auth built from
JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN. It never mutates a Jira issue.

Design decisions:
  - Mirrors plugins/spec-loop/scripts/pr_resolver.py's shape: one _http_get
    that is structurally incapable of issuing a mutating verb, an env-var
    credential read with a fail-closed actionable message, strict regex
    allow-lists on every untrusted value before it reaches a URL, and a
    single _normalized() builder so the inter-slice JSON contract shape
    cannot drift.
  - Host allow-list: JIRA_BASE_URL must be https and its hostname must match
    ALLOWED_HOST_RE (*.atlassian.net or *.jira.com). Jira Data Center /
    on-prem hosts are out of scope; there is deliberately no opt-in
    extra-hosts env var, since that would re-open the exact hole the
    allow-list closes.
  - Redirects are refused outright (a custom HTTPRedirectHandler whose
    redirect_request returns None), not followed-with-header-stripped: the
    base URL is user-supplied, so pr_resolver's hardcoded-origin property is
    gone, and this is simpler to prove correct than header stripping.
  - Jira Cloud REST v3 uses HTTP Basic auth over base64(email:api_token), not
    Bearer (verified against Atlassian's basic-auth-for-rest-apis page,
    2026-09-08).
  - Acceptance criteria resolve in a fixed order: (1) a custom field whose
    catalogue name casefolds to "acceptance criteria", if present and
    non-empty; else (2) an "Acceptance Criteria" heading section of the
    rendered description; else empty. The field-catalogue GET is
    best-effort (a 403 degrades to path (2) rather than failing the
    resolve); every other GET is fail-closed.
  - ADF (Atlassian Document Format) description/comment bodies are rendered
    to plain text by a pure adf_to_text() walker. The renderer is
    lossy-by-design: it produces review-readable text, not a
    round-trippable document.
  - No subprocess, no filesystem writes, and no clock read anywhere in
    this module: this is a pure read lane, and the controller owns the
    clock. Jira's own created/updated strings are echoed verbatim.

SECURITY: the issue key and every Jira text field (summary, description,
acceptance criteria, every comment body) are UNTRUSTED DATA, never
instructions. The issue key is regex-validated against ISSUE_KEY_RE and
percent-encoded before it reaches a URL segment. The base URL host is
allow-listed and https-only. Redirects are refused outright. This module
issues GET only and never a mutating verb. Credentials come from the
environment ONLY and are never read from argv (argv is visible in `ps` and
lands in shell history).

Exit codes: 0 = ok; 1 = contract failure; 2 = usage / unreadable input

Usage:
    python3 scripts/jira_client.py resolve --key ABC-123
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


class JiraError(Exception):
    """A Jira contract failure: HTTP error, malformed JSON, or a half-resolve
    (a required field came back empty). Maps to exit code 1."""


class JiraUsageError(JiraError):
    """A usage or environment failure: a bad issue key, a bad or absent base
    URL, or missing credentials -- anything the user can fix in their
    invocation or environment. Maps to exit code 2."""


ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}-[0-9]{1,10}$")
ALLOWED_HOST_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9-]{0,60}\.(atlassian\.net|jira\.com)$")


def validate_issue_key(key):
    """Validate an UNTRUSTED Jira issue key before it reaches a URL segment.
    Rejects lowercase, path separators, a leading '-' (argument injection) and
    anything else outside ISSUE_KEY_RE."""
    if not ISSUE_KEY_RE.match(key or ""):
        raise JiraUsageError(
            f"invalid Jira issue key {key!r}: must match {ISSUE_KEY_RE.pattern} "
            "(an uppercase project key, a hyphen, then digits -- e.g. A-1 or PROJ-42)"
        )
    return key


def _split_base_url(raw):
    """Split an UNTRUSTED JIRA_BASE_URL into urlsplit's parts, or None when the
    value cannot be split at all (a malformed IPv6 host) or carries a port
    that cannot be parsed as an integer (both raise a bare ValueError from
    urllib.parse, since parts.port is computed lazily on attribute access).
    Isolating that ValueError here is what keeps every malformed base URL on
    the fail-closed JiraUsageError path instead of an uncaught traceback."""
    try:
        parts = urllib.parse.urlsplit(raw or "")
        parts.port  # noqa: B018 -- force the lazy, possibly-raising parse now
    except ValueError:
        return None
    return parts


def _redacted_base_url(raw, parts):
    """Render raw for the rejection message with any userinfo stripped, so a
    credential smuggled into JIRA_BASE_URL's userinfo is never echoed back
    into the machine-readable error object. Falls back to '<unparsable>' when
    the value could not even be split (parts is None)."""
    if parts is None:
        return "<unparsable>"
    if parts.username or parts.password:
        return f"{parts.scheme}://<redacted>@{parts.hostname or ''}"
    return f"{parts.scheme}://{parts.hostname or ''}"


def validate_base_url(raw):
    """Validate an UNTRUSTED JIRA_BASE_URL and return its normalized bare
    origin (scheme + host only -- no trailing slash, no path/query/fragment).
    Discarding the path is deliberate: every API path in this module is
    composed from this origin plus a literal /rest/api/3/... prefix. Requires
    https, rejects embedded userinfo (userinfo smuggling) or an explicit
    port, and requires the hostname to match ALLOWED_HOST_RE."""
    parts = _split_base_url(raw)
    ok = bool(
        parts is not None
        and parts.scheme == "https"
        and not parts.username
        and not parts.password
        and not parts.port
        and ALLOWED_HOST_RE.match(parts.hostname or "")
    )
    if not ok:
        raise JiraUsageError(
            f"invalid JIRA_BASE_URL {_redacted_base_url(raw, parts)!r}: must be "
            "an https URL on a *.atlassian.net or *.jira.com host (e.g. "
            "https://your-site.atlassian.net)"
        )
    return f"https://{parts.hostname.lower()}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every 3xx. The base URL is user-supplied, so pr_resolver's
    hardcoded-origin property is gone: following a redirect could replay the
    Authorization header to another origin. Returning None makes urllib raise
    the HTTPError instead of following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Return None so urllib treats the 3xx as a terminal error."""
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

CRED_VARS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")


def credentials():
    """Read the Jira credentials from the ENVIRONMENT ONLY and fail closed with
    an actionable message when any is unset. Never read from argv: argv is
    visible in `ps` and lands in shell history."""
    values = {name: (os.environ.get(name) or "").strip() for name in CRED_VARS}
    missing = [name for name in CRED_VARS if not values[name]]
    if missing:
        raise JiraUsageError(
            "Jira access requires the environment variable(s) "
            + ", ".join(missing)
            + ". Set JIRA_BASE_URL to your site origin (e.g. "
            "https://your-site.atlassian.net), JIRA_EMAIL to your Atlassian "
            "account email, and JIRA_API_TOKEN to an API token created at "
            "https://id.atlassian.com/manage-profile/security/api-tokens. "
            "Pass them in the environment, never on the command line."
        )
    return (validate_base_url(values["JIRA_BASE_URL"]),
            values["JIRA_EMAIL"], values["JIRA_API_TOKEN"])


def _auth_header(email, token):
    """Build the Jira Cloud Basic auth header: base64("email:api_token").
    Verified against Atlassian's basic-auth-for-rest-apis page (2026-09-08) --
    Jira Cloud REST v3 uses Basic with an API token, NOT Bearer."""
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _http_get(url, email, token):
    """HTTP GET via the no-redirect opener (READ-ONLY: never sets a body and
    never a mutating method). The sole network entry point in this module.
    Errors reference only the URL -- the credentials ride in a header, so
    neither the token, the email, nor the composed base64 pair can appear in an
    exception message."""
    req = urllib.request.Request(
        url,
        headers={"Authorization": _auth_header(email, token),
                 "Accept": "application/json"},
        method="GET",
    )
    try:
        with _OPENER.open(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise JiraError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise JiraError(f"network error fetching {url}: {exc.reason}") from exc


def _parse_json(raw, what):
    """json.loads with an actionable JiraError, so a malformed response fails
    with a clear message rather than a raw traceback."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JiraError(
            f"Jira returned a {what} response that is not valid JSON ({exc})"
        ) from exc


_ADF_MAX_DEPTH = 50
_ADF_INLINE_TYPES = ("text", "hardBreak", "mention", "inlineCard")


def _adf_inline_text(child):
    """Render a 'text' inline node: its literal text."""
    return child.get("text", "")


def _adf_inline_mention(child):
    """Render a 'mention' inline node as '@<attrs.text>'. attrs.text already
    carries the '@' from Jira, so it is used as-is when present."""
    text = (child.get("attrs") or {}).get("text", "")
    return text if text.startswith("@") else f"@{text}"


def _adf_inline_card(child):
    """Render an 'inlineCard' inline node as its bare attrs.url."""
    return (child.get("attrs") or {}).get("url", "")


# Maps an inline node's ADF type to a (child) -> str renderer. Looked up once
# per child in _adf_inline; a type absent here falls back to _adf_block, so an
# inline node with an unexpected nested block still contributes its rendered
# text instead of vanishing.
_INLINE_RENDERERS = {
    "text": _adf_inline_text,
    "hardBreak": lambda child: "\n",
    "mention": _adf_inline_mention,
    "inlineCard": _adf_inline_card,
}


def _adf_inline(node, depth):
    """Render a node's inline children into one string via _INLINE_RENDERERS;
    any child of an unrecognized type falls back to _adf_block."""
    if depth > _ADF_MAX_DEPTH:
        return ""
    parts = []
    for child in node.get("content") or []:
        renderer = _INLINE_RENDERERS.get(child.get("type"))
        parts.append(renderer(child) if renderer else _adf_block(child, depth + 1))
    return "".join(parts)


def _adf_block_children(node, depth):
    """Render node's direct children as blocks at depth + 1 (a small shared
    helper for the several block types that recurse over `content`)."""
    return [_adf_block(child, depth + 1) for child in node.get("content") or []]


def _adf_heading(node, depth):
    """Render a 'heading' block as '#' * level + ' ' + its inline text."""
    level = (node.get("attrs") or {}).get("level", 1)
    return "#" * level + " " + _adf_inline(node, depth)


def _adf_code_block(node, depth):
    """Render a 'codeBlock' block fenced with triple backticks."""
    return "```\n" + _adf_inline(node, depth) + "\n```"


def _adf_list_item(node, depth):
    """Render a 'listItem' block by joining its own blocks with one newline."""
    return "\n".join(_adf_block_children(node, depth))


def _adf_bullet_list(node, depth):
    """Render a 'bulletList' block as '- '-prefixed lines."""
    items = _adf_block_children(node, depth)
    return "\n".join(f"- {item}" for item in items)


def _adf_ordered_list(node, depth):
    """Render an 'orderedList' block as '1. '-prefixed, numbered lines."""
    items = _adf_block_children(node, depth)
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))


def _adf_paragraph(node, depth):
    """Render a 'paragraph' block as its inline text."""
    return _adf_inline(node, depth)


# Maps a block node's ADF type to a (node, depth) -> str renderer. A type
# absent here falls through to _adf_block_fallback, so an unrecognized future
# node type still renders its children instead of disappearing.
_BLOCK_RENDERERS = {
    "heading": _adf_heading,
    "codeBlock": _adf_code_block,
    "listItem": _adf_list_item,
    "bulletList": _adf_bullet_list,
    "orderedList": _adf_ordered_list,
    "paragraph": _adf_paragraph,
}


def _adf_block_fallback(node, depth):
    """Render a block node of an unrecognized (or plain 'doc'-child) type:
    as inline text when every child is an inline node type, else as a
    blank-line-joined sequence of child blocks -- so it still renders its
    children instead of disappearing."""
    children = node.get("content") or []
    if children and all(c.get("type") in _ADF_INLINE_TYPES for c in children):
        return _adf_inline(node, depth)
    rendered = [_adf_block(child, depth + 1) for child in children]
    return "\n\n".join(rendered)


def _adf_block(node, depth):
    """Render one ADF block node to plain text, guarded against pathological
    nesting: at depth > 50 this returns '' and stops recursing rather than
    blowing the stack. Dispatches by node type via _BLOCK_RENDERERS, falling
    back to _adf_block_fallback for any type not listed there."""
    if depth > _ADF_MAX_DEPTH:
        return ""
    renderer = _BLOCK_RENDERERS.get(node.get("type"), _adf_block_fallback)
    return renderer(node, depth)


def adf_to_text(node):
    """Render an Atlassian Document Format document (or None, or a plain
    string -- both occur in the wild in Jira description/comment bodies) to
    plain, review-readable text. This renderer is LOSSY BY DESIGN: it
    produces text for humans to read, not a document that round-trips back
    into ADF. Blocks are joined with a blank line and the result is
    stripped of trailing whitespace."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    blocks = [_adf_block(child, 0) for child in node.get("content") or []]
    return "\n\n".join(blocks).strip()


ISSUE_FIELDS = ("summary", "description", "status", "issuetype")
AC_FIELD_NAME = "acceptance criteria"
AC_HEADING_RE = re.compile(
    r"^\s{0,3}#{1,6}\s*acceptance\s+criteria\s*:?\s*$", re.IGNORECASE)
ANY_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")


def _issue_url(base_url, key):
    """Compose the REST v3 issue URL for one key. The key has already been
    validated against ISSUE_KEY_RE by the caller, and is percent-encoded here
    anyway: defence in depth, per the run constraint that an untrusted id is
    encoded regardless before it reaches a URL segment."""
    return f"{base_url}/rest/api/3/issue/{urllib.parse.quote(key, safe='')}"


def find_ac_field_id(base_url, email, token):
    """Locate the id of the custom field whose catalogue display name casefolds
    to AC_FIELD_NAME, via GET /rest/api/3/field. Returns None when no such
    field exists, when the payload is not the documented flat array, or when
    the call fails.

    This is the ONE best-effort call in the module -- every other GET is
    fail-closed. A 403 here is common on locked-down sites (the field
    catalogue is an admin-adjacent read), the acceptance criteria have a
    defined description fallback, and the winner is recorded in the record's
    acceptance_criteria_source, so degrading to None is not a half-resolve."""
    try:
        raw = _http_get(f"{base_url}/rest/api/3/field", email, token)
        catalogue = _parse_json(raw.decode("utf-8"), "field catalogue")
    except JiraError:
        return None
    if not isinstance(catalogue, list):
        return None
    for entry in catalogue:
        # A non-object entry is malformed; skip it rather than raising, since
        # this whole lookup degrades to None instead of failing the resolve.
        if not isinstance(entry, dict):
            continue
        if (entry.get("name") or "").strip().casefold() == AC_FIELD_NAME:
            return entry.get("id") or None
    return None


def fetch_issue(base_url, creds, key, ac_field_id):
    """GET the raw IssueBean for one issue key, requesting ISSUE_FIELDS plus
    the acceptance-criteria custom field when one was located. `creds` is the
    (email, token) pair, bundled as a parameter object to keep this
    function's own parameter count down. The key is validated BEFORE any
    request is issued, so a malformed key never reaches the network.
    Fail-closed: an HTTP error or a malformed body raises."""
    email, token = creds
    validate_issue_key(key)
    fields = list(ISSUE_FIELDS) + ([ac_field_id] if ac_field_id else [])
    query = urllib.parse.urlencode({"fields": ",".join(fields)})
    url = f"{_issue_url(base_url, key)}?{query}"
    return _parse_json(_http_get(url, email, token).decode("utf-8"), "issue")


def acceptance_criteria_from_description(text):
    """Extract the section under an 'Acceptance Criteria' heading from ALREADY
    RENDERED description text. The heading match is case-insensitive and
    tolerates a trailing colon; the section runs to the next heading of any
    level, or to the end of the text. Returns '' when no such heading is
    present."""
    lines = (text or "").splitlines()
    collected = []
    inside = False
    for line in lines:
        if not inside:
            inside = bool(AC_HEADING_RE.match(line))
            continue
        if ANY_HEADING_RE.match(line):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def resolve_acceptance_criteria(issue, ac_field_id, description_text):
    """Resolve the acceptance criteria in the fixed two-step order and report
    which source won: the custom field named in the catalogue when it exists
    and renders non-empty ('field'), else the description's 'Acceptance
    Criteria' section ('description'), else ('', ''). Recording the source is
    what makes the best-effort catalogue lookup safe -- a reader can always
    tell where the text came from."""
    if ac_field_id:
        raw = (issue.get("fields") or {}).get(ac_field_id)
        # Only an ADF document or a plain string is renderable. A field of
        # some other shape (a multi-select array, a number) is not acceptance
        # criteria text, so it degrades to the description fallback rather
        # than crashing the resolve.
        rendered = adf_to_text(raw).strip() if isinstance(raw, (str, dict)) else ""
        if rendered:
            return (rendered, "field")
    from_description = acceptance_criteria_from_description(description_text)
    if from_description:
        return (from_description, "description")
    return ("", "")


COMMENT_PAGE_SIZE = 100
MAX_COMMENT_PAGES = 100

_MISSING_COMMENTS_MSG = (
    "Jira comment page is missing the 'comments' list; cannot read the "
    "full comment history")


def _normalize_comment(raw):
    """Normalize one raw REST v3 comment object to
    {"id", "author", "created", "updated", "body"}. Extracted out of
    fetch_comments so its per-field literal stays out of that function's own
    (indentation-measured) nesting depth."""
    return {
        "id": str(raw.get("id") or ""),
        "author": ((raw.get("author") or {}).get("displayName") or ""),
        "created": raw.get("created") or "",
        "updated": raw.get("updated") or "",
        "body": adf_to_text(raw.get("body")),
    }


def fetch_comments(base_url, email, token, key):
    """GET the FULL, paginated comment list for one issue key via a
    startAt-paginated sweep of /rest/api/3/issue/{key}/comment, normalized to
    [{"id", "author", "created", "updated", "body"}, ...] in server order.

    Verified against Atlassian's REST v3 docs (2026-09-08): the server default
    maxResults is 50, so a single unpaginated GET silently truncates a chatty
    card and would defeat comment-based dedupe downstream. This sweep asks for
    COMMENT_PAGE_SIZE per page and keeps requesting until the accumulated
    count reaches the page's reported `total`, or a page comes back empty
    (guarding against a `total` that lies). MAX_COMMENT_PAGES bounds a
    runaway/misbehaving server so this cannot loop forever.

    The key is validated BEFORE any request is issued. A page missing the
    `comments` list (the REST v3 shape; NOT `values`, which belongs to the
    unrelated POST /rest/api/3/comment/list endpoint) raises rather than
    silently degrading to "no comments" -- swallowing a shape change here
    would silently defeat dedupe on a chatty card."""
    validate_issue_key(key)
    comments = []
    start = 0
    base = f"{_issue_url(base_url, key)}/comment"
    for _ in range(MAX_COMMENT_PAGES):
        query = urllib.parse.urlencode(
            {"startAt": start, "maxResults": COMMENT_PAGE_SIZE})
        url = f"{base}?{query}"
        page = _parse_json(
            _http_get(url, email, token).decode("utf-8"), "comment page")
        page_comments = page.get("comments") if isinstance(page, dict) else None
        if not isinstance(page_comments, list):
            raise JiraError(_MISSING_COMMENTS_MSG)
        comments.extend(_normalize_comment(c) for c in page_comments)
        if not page_comments or len(comments) >= int(page.get("total") or 0):
            return comments
        start += len(page_comments)
    raise JiraError(
        f"comment pagination did not terminate after {MAX_COMMENT_PAGES} "
        f"pages for {key}; refusing a possibly-truncated comment history")


RECORD_FIELDS = ("key", "web_url", "summary", "description",
                 "acceptance_criteria", "acceptance_criteria_source",
                 "status", "issue_type", "comments")
REQUIRED_FIELDS = ("key", "web_url", "summary", "status", "issue_type")


def _normalized(values):
    """Build the inter-slice record in RECORD_FIELDS order -- the single source
    of truth for the JSON contract shape, so it cannot drift between callers.
    An empty REQUIRED_FIELDS entry means the API response was incomplete: that
    is a half-resolve and raises, because a partial record must never be
    emitted as if it were a whole one. description, acceptance_criteria,
    acceptance_criteria_source and an empty comments list are all legitimately
    empty."""
    record = {name: values[name] for name in RECORD_FIELDS}
    empty = [name for name in REQUIRED_FIELDS if not record[name]]
    if empty:
        raise JiraError(
            "Jira returned an incomplete issue: the required field(s) "
            + ", ".join(empty)
            + " came back empty; refusing to emit a partial record")
    return record


def resolve_issue(key):
    """Resolve one Jira issue key READ-ONLY to the normalized record.
    Credentials come from the environment (see credentials()); the field
    catalogue lookup is best effort, every other call is fail-closed."""
    base_url, email, token = credentials()
    key = validate_issue_key(key)
    ac_field_id = find_ac_field_id(base_url, email, token)
    issue = fetch_issue(base_url, (email, token), key, ac_field_id)
    fields = issue.get("fields") or {}
    resolved_key = issue.get("key") or key
    description = adf_to_text(fields.get("description"))
    criteria, source = resolve_acceptance_criteria(issue, ac_field_id, description)
    return _normalized({
        "key": resolved_key,
        "web_url": f"{base_url}/browse/"
                   f"{urllib.parse.quote(validate_issue_key(resolved_key), safe='')}",
        "summary": fields.get("summary") or "",
        "description": description,
        "acceptance_criteria": criteria,
        "acceptance_criteria_source": source,
        "status": (fields.get("status") or {}).get("name") or "",
        "issue_type": (fields.get("issuetype") or {}).get("name") or "",
        "comments": fetch_comments(base_url, email, token, resolved_key),
    })


def build_parser():
    """Build the CLI parser: one read-only subcommand, `resolve --key`. There
    is deliberately no credential flag -- credentials are read from the
    environment only, never from argv."""
    parser = argparse.ArgumentParser(
        description="Read-only Jira Cloud issue reader.")
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser(
        "resolve", help="Resolve one issue key to a normalized JSON record.")
    resolve.add_argument("--key", required=True,
                         help="Jira issue key, e.g. ABC-123.")
    return parser


def main(argv=None):
    """Parse args, resolve, print one JSON object. Exit 0 ok, 1 contract
    failure, 2 usage / unreadable input. JiraUsageError is caught BEFORE
    JiraError: it subclasses JiraError, so the reverse order would collapse
    exit 2 into exit 1."""
    args = build_parser().parse_args(argv)
    try:
        record = resolve_issue(args.key)
    except JiraUsageError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}), file=sys.stderr)
        return 2
    except JiraError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}), file=sys.stderr)
        return 1
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
