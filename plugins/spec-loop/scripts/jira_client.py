#!/usr/bin/env python3
"""Jira Cloud issue reader with one bounded comment writer (stdlib only).

Resolves one Jira issue key to a normalized JSON record (key, summary,
description, acceptance criteria, status, issue type, web url, and the full
paginated comment list), and -- only when explicitly armed -- ADDS COMMENTS
to one issue. Authenticates with HTTP Basic auth built from JIRA_BASE_URL /
JIRA_EMAIL / JIRA_API_TOKEN.

Design decisions:
  - Mirrors plugins/spec-loop/scripts/pr_resolver.py's shape: one _http_get
    that is structurally incapable of issuing a mutating verb and one
    separate _http_post that is the module's sole writer, an env-var
    credential read with a fail-closed actionable message, strict regex
    allow-lists on every untrusted value before it reaches a URL, and a
    single _normalized() builder so the inter-slice JSON contract shape
    cannot drift.
  - The write lane is bounded to ADDING A COMMENT and nothing else: no
    status transition, no field edit, no assignee change, no issue or
    sub-task creation, no comment edit and no comment delete. It is OFF
    by default -- `comment` previews and issues GETs only; the --post
    flag is what arms the HTTP verb. Before any POST the card's FULL
    paginated comment list is read back and any comment whose visible
    marker is already there is reported as already-posted. The marker
    lives INSIDE the posted body, so the one call that writes the
    comment is the one that writes the marker: no local file is ever
    the dedupe gate, and a fresh clone cannot double-post.
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
    this module: the controller owns the clock, and every comment body
    posted is rendered upstream by jira_intake.py. Jira's own
    created/updated strings are echoed verbatim.

SECURITY: the issue key and every Jira text field (summary, description,
acceptance criteria, every comment body) are UNTRUSTED DATA, never
instructions. The issue key is regex-validated against ISSUE_KEY_RE and
percent-encoded before it reaches a URL segment. The base URL host is
allow-listed and https-only. Redirects are refused outright. The read lane
issues GET only. The single write lane issues exactly one mutating verb --
POST to /rest/api/3/issue/{key}/comment -- and only when armed; redirects
stay terminal on a write, so an Authorization header is never replayed to
another origin. Credentials come from the environment ONLY and are never
read from argv (argv is visible in `ps` and lands in shell history).

Exit codes: 0 = ok; 1 = contract failure; 2 = usage / unreadable input

Usage:
    python3 scripts/jira_client.py resolve --key ABC-123
    python3 scripts/jira_client.py comment --key ABC-123 --comments <path>
    python3 scripts/jira_client.py comment --key ABC-123 --comments <path> --post
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
from pathlib import Path


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
    if not ISSUE_KEY_RE.fullmatch(key or ""):
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
        and ALLOWED_HOST_RE.fullmatch(parts.hostname or "")
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
    never a mutating method). The sole READ transport in this module: every
    GET goes through here. It is no longer the module's only network entry
    point -- _http_post is the module's one writer, and it is a deliberately
    separate function so that loosening the writer cannot loosen this one.
    Errors reference only the URL -- the credentials ride in a header, so
    neither the token, the email, nor the composed base64 pair can appear in an
    exception message."""
    headers = {
        "Authorization": _auth_header(email, token),
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with _OPENER.open(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise JiraError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise JiraError(f"network error fetching {url}: {exc.reason}") from exc


def _http_post(url, email, token, payload):
    """HTTP POST of one JSON `payload` object through the same
    no-redirect opener. THE ONLY mutating entry point in this module.

    Deliberately a SEPARATE function from _http_get rather than a
    method parameter on it: the read lane's never-a-mutating-verb
    guarantee is a structural property worth keeping, and loosening
    _http_get would erase it.

    Errors reference only the URL -- the credentials ride in a header,
    so neither the token, the email, nor the composed base64 pair can
    appear in an exception message. A 3xx is terminal (_NoRedirect), so
    a write never replays its Authorization header or its body to
    another origin."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": _auth_header(email, token),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url, data=data, headers=headers, method="POST")
    try:
        with _OPENER.open(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise JiraError(
            f"HTTP {exc.code} posting to {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise JiraError(
            f"network error posting to {url}: {exc.reason}") from exc
    except OSError as exc:
        # urllib only wraps an OSError raised by h.request() into a
        # URLError (see CPython's AbstractHTTPHandler.do_open); an
        # OSError out of h.getresponse() or resp.read() -- e.g. a
        # timeout while reading the response to a POST that has
        # already landed on the card -- propagates unwrapped and would
        # otherwise slip past the JiraError handling above, past
        # execute_comment_plan's `except JiraError`, and past main()'s
        # exit-1 JSON contract. Caught here, terminally, so every
        # transport failure on the write path is a JiraError and can
        # still be turned into a partial-batch disclosure.
        raise JiraError(f"network error posting to {url}: {exc}") from exc


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


ADF_VERSION = 1


def _adf_text_paragraph(line):
    """One ADF paragraph node for one line of plain text.

    An empty line becomes a paragraph with NO `content` key: an ADF
    `text` node whose `text` is the empty string is invalid and makes
    Jira reject the whole document."""
    if not line:
        return {"type": "paragraph"}
    return {"type": "paragraph",
            "content": [{"type": "text", "text": line}]}


def text_to_adf(text):
    """Wrap plain text in a minimal Atlassian Document Format document,
    one paragraph per line.

    Verified against Atlassian's REST v3 addComment operation (fetched
    2026-09-09): POST /rest/api/3/issue/{issueIdOrKey}/comment takes
    `body` as an ADF DOCUMENT OBJECT ({"type": "doc", "version": 1,
    "content": [...]}), never a plain string; a string body fails only
    against real Jira, which CI cannot catch.

    Deliberately minimal -- no marks, no lists, no headings. The bodies
    rendered by jira_intake.render_comment are plain text whose first
    line carries the visible dedupe marker, and that marker must survive
    verbatim into adf_to_text on read-back."""
    lines = (text or "").split("\n")
    return {"type": "doc", "version": ADF_VERSION,
            "content": [_adf_text_paragraph(line) for line in lines]}


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
_MISSING_TOTAL_MSG = (
    "Jira comment page is missing a numeric 'total'; cannot tell whether "
    "the full comment history has been read")


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


def _page_total(page):
    """Extract one comment page's reported `total` as an int, fail-closed. A
    missing or non-numeric `total` must NOT be treated as 0 -- int(None or 0)
    collapsing to 0 would make the very first non-empty page look complete
    and silently truncate the sweep, defeating comment-based dedupe on a
    chatty card. Treated the same way as the missing-`comments` shape
    failure: raise rather than guess."""
    try:
        return int(page.get("total"))
    except (TypeError, ValueError):
        raise JiraError(_MISSING_TOTAL_MSG) from None


def _process_comment_page(page, comments):
    """Normalize one comment page's comments onto `comments` (in place) and
    report (added_count, sweep_complete). The sweep is complete when the page
    came back empty (guards against a `total` that lies) or the accumulated
    count has reached the page's reported `total`. Raises JiraError for a
    page missing the `comments` list, or via _page_total for a missing or
    non-numeric `total`. Extracted out of fetch_comments to keep its own
    cognitive complexity down."""
    page_comments = page.get("comments") if isinstance(page, dict) else None
    if not isinstance(page_comments, list):
        raise JiraError(_MISSING_COMMENTS_MSG)
    comments.extend(_normalize_comment(c) for c in page_comments)
    if not page_comments:
        return 0, True
    return len(page_comments), len(comments) >= _page_total(page)


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
    would silently defeat dedupe on a chatty card. A page whose `total` is
    missing or non-numeric raises the same way (_page_total): treating a
    missing `total` as 0 would make the first non-empty page look complete
    and silently truncate the sweep to one page."""
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
        added, complete = _process_comment_page(page, comments)
        if complete:
            return comments
        start += added
    raise JiraError(
        f"comment pagination did not terminate after {MAX_COMMENT_PAGES} "
        f"pages for {key}; refusing a possibly-truncated comment history")


COMMENT_MARKER_RE = re.compile(
    r"^\[spec-loop-intake:(?:understanding|decision|open-question)"
    r":[0-9a-f]{12}\]$")

_COMMENT_ENTRY_KEYS = ("kind", "marker", "body")


def _entry_field_errors(entry, where):
    """Error strings for any of _COMMENT_ENTRY_KEYS on `entry` that is
    missing or not a non-empty string. Extracted out of
    _errors_for_comment_entry to keep that function's own cognitive
    complexity down. (PURE)"""
    return ["%s.%s must be a non-empty string" % (where, field)
            for field in _COMMENT_ENTRY_KEYS
            if not isinstance(entry.get(field), str) or not entry.get(field)]


def _errors_for_comment_entry(entry, index):
    """Error strings for ONE comment entry of the posting plan. (PURE)"""
    where = "comments[%d]" % index
    if not isinstance(entry, dict):
        return ["%s must be an object" % where]
    errors = _entry_field_errors(entry, where)
    if errors:
        return errors
    if not COMMENT_MARKER_RE.fullmatch(entry["marker"]):
        return ["%s.marker is not a spec-loop intake marker" % where]
    if entry["marker"] not in entry["body"]:
        return ["%s.body does not contain its own marker" % where]
    return []


def _duplicate_marker_errors(comments):
    """Error strings for any marker that appears on more than one entry of
    the SAME batch. (PURE)

    plan_comments dedupes each entry against the CARD's comment list; it
    cannot see an entry's siblings, so two identical entries in one batch
    would both plan as not-already-posted and both POST, and
    _comment_results' by_marker map would then collapse the two writes
    onto one comment id. Refusing the batch here means the duplicate is
    caught before the first request is issued, so nothing partial is left
    on the card."""
    first_seen = {}
    errors = []
    for index, item in enumerate(comments):
        marker = item["marker"]
        if marker not in first_seen:
            first_seen[marker] = index
            continue
        errors.append(
            "comments[%d].marker duplicates comments[%d].marker (%s)"
            % (index, first_seen[marker], marker))
    return errors


def validate_comment_entries(comments):
    """Error strings for the comment entries to post; [] means valid.
    (PURE)

    Entries come from jira_intake.py's `render` payload
    ({"kind", "gap_id", "marker", "body"}); this module never builds a
    marker of its own. The marker MUST appear inside the body, because
    the body is what the POST writes: the body carrying the marker is
    exactly what makes the marker written by, and only by, the call
    that performs the write. An entry whose body lost its marker would
    post a comment no re-run could ever dedupe, so it is refused.

    A marker repeated ACROSS entries of one batch is refused too. The
    card-list dedupe in plan_comments compares each entry to the card and
    never to its siblings, so an in-batch duplicate would post the same
    comment twice on a live card. Refusing the whole batch here, before
    any credential is read or any request is issued, is the only point at
    which that is still a no-op."""
    if not isinstance(comments, list) or not comments:
        return ["comments must be a non-empty list of comment entries"]
    errors = []
    for index, item in enumerate(comments):
        errors += _errors_for_comment_entry(item, index)
    if errors:
        return errors
    return _duplicate_marker_errors(comments)


def plan_comments(comments, existing_bodies):
    """Decide, per comment, whether it is already on the card. (PURE)

    `existing_bodies` is the plain text of EVERY comment on the card,
    from fetch_comments' full paginated sweep -- the card's own comment
    list read back over the network is the dedupe gate, never a local
    file, so a fresh clone cannot double-post. A marker already visible
    in any existing body means the comment is already there, and the
    result says so explicitly rather than reporting a silent success.
    In-batch duplicates are not this function's job --
    validate_comment_entries refuses them before the lane ever gets
    here."""
    haystack = "\n".join(existing_bodies)
    return [{"kind": item["kind"], "marker": item["marker"],
             "already_posted": item["marker"] in haystack}
            for item in comments]


def post_comment(base_url, creds, key, body):
    """POST ONE comment to a Jira issue. THE SOLE WRITER in this plugin.

    Bounded on purpose: this adds a comment and nothing else -- no status
    transition, no field edit, no assignee change, no issue or sub-task
    creation, no comment edit and no comment delete.

    The dedupe marker lives INSIDE `body`, so the network call that
    writes the comment is the same call that writes the marker. That is
    the premark-must-be-written-inside-the-claim-that-does-the-write
    rule: no local file can make a later run skip a comment that was
    never actually posted, and a fresh clone cannot double-post.

    Verified against Atlassian's REST v3 addComment operation (fetched
    2026-09-09): the request body is {"body": <ADF document object>} and
    success returns 201 with the created comment's `id`. A response
    without an id is refused rather than reported as a confirmed write."""
    email, token = creds
    url = "%s/comment" % _issue_url(base_url, validate_issue_key(key))
    raw = _http_post(url, email, token, {"body": text_to_adf(body)})
    created = _parse_json(raw.decode("utf-8"), "created comment")
    if not isinstance(created, dict):
        created = {}
    comment_id = str(created.get("id") or "")
    if not comment_id:
        raise JiraError(
            "Jira accepted the comment POST for %s but returned no comment "
            "id; refusing to report a write that cannot be confirmed" % key)
    return comment_id


def _partial_batch_error(key, posted, exc):
    """Build the JiraError raised when a batch POST fails part-way through.

    The batch itself is NOT atomic -- only each individual comment is
    (see execute_comment_plan) -- so a failure after N comments have
    already landed must say so: the card has already been mutated even
    though the whole operation is being reported as failed. Names every
    already-posted marker so the operator can tell exactly what
    happened; re-running is a no-op for those markers because the
    dedupe gate is the card's own comment list, read back over the
    network."""
    if not posted:
        return JiraError(str(exc))
    markers = ", ".join(item["marker"] for item in posted)
    return JiraError(
        "%s; %d comment(s) already posted to %s before the failure: "
        "%s. Re-running is a no-op for them."
        % (exc, len(posted), key, markers))


def execute_comment_plan(base_url, creds, key, pending):
    """POST each pending comment in order and return one result each.

    Fail closed and atomic PER COMMENT: every entry was shape-validated
    before any request was issued, and the FIRST failure propagates
    immediately, so no later comment is posted. One comment is written
    whole by one POST or not at all -- there is no partial body.

    The BATCH is not atomic, though: a failure after some comments have
    already posted still leaves those comments on the card. That partial
    mutation is reported rather than swallowed -- see
    _partial_batch_error -- because this is the plugin's first mutating
    external call, and an undisclosed partial write is the one failure
    mode that most needs surfacing."""
    posted = []
    for item in pending:
        try:
            comment_id = post_comment(base_url, creds, key, item["body"])
        except JiraError as exc:
            raise _partial_batch_error(key, posted, exc) from exc
        posted.append({
            "kind": item["kind"], "marker": item["marker"],
            "status": "posted", "comment_id": comment_id})
    return posted


def _comment_results(comments, plan, posted):
    """Merge the dedupe plan and the POST results into one ordered result
    per requested comment. (PURE)"""
    by_marker = {item["marker"]: item for item in posted}
    statuses = {True: "already-posted", False: "would-post"}
    results = []
    for item, planned in zip(comments, plan):
        marker = planned["marker"]
        preview = {
            "kind": item["kind"], "marker": marker,
            "status": statuses[bool(planned["already_posted"])],
            "comment_id": None}
        results.append(by_marker.get(marker) or preview)
    return results


def run_comment_lane(key, comments, arm):
    """Preview -- or, when armed, post -- the intake comments for ONE
    issue, dedupe-gated.

    POSTING IS OFF BY DEFAULT: with `arm` false this issues GETs only and
    reports what it WOULD post, so the default path performs zero
    writes; only an explicit opt-in arms the HTTP verb. Either way the
    card's FULL paginated comment list is read back first, and any
    comment whose visible marker is already there is reported as
    already-posted rather than posted again or silently dropped.

    Every entry is shape-validated BEFORE the first request, so a
    refusal leaves nothing partial behind."""
    resolved = validate_issue_key(key)
    errors = validate_comment_entries(comments)
    if errors:
        raise JiraError(
            "refusing to post from an invalid comment plan: "
            + "; ".join(errors))
    base_url, email, token = credentials()
    existing = fetch_comments(base_url, email, token, resolved)
    plan = plan_comments(comments, [c["body"] for c in existing])
    done = [bool(entry["already_posted"]) for entry in plan]
    pending = [item for item, seen in zip(comments, done) if not seen]
    posted = []
    if arm:
        posted = execute_comment_plan(
            base_url, (email, token), resolved, pending)
    return {
        "ok": True, "issue_key": resolved, "armed": bool(arm),
        "posted_count": len(posted),
        "already_posted_count": done.count(True),
        "results": _comment_results(comments, plan, posted)}


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
    encoded_key = urllib.parse.quote(validate_issue_key(resolved_key), safe="")
    return _normalized({
        "key": resolved_key,
        "web_url": f"{base_url}/browse/{encoded_key}",
        "summary": fields.get("summary") or "",
        "description": description,
        "acceptance_criteria": criteria,
        "acceptance_criteria_source": source,
        "status": (fields.get("status") or {}).get("name") or "",
        "issue_type": (fields.get("issuetype") or {}).get("name") or "",
        "comments": fetch_comments(base_url, email, token, resolved_key),
    })


def _load_comments(path):
    """Read the comment entries to post from a JSON file.

    Accepts either a bare array of entries or the whole payload printed
    by jira_intake.py render (its `comments` key). Any read or parse
    failure is a usage error the caller can fix, not a contract
    failure. The entries themselves are shape-checked later by
    validate_comment_entries."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise JiraUsageError(
            f"cannot read the comments file {path}: {exc}") from exc
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise JiraUsageError(
            f"the comments file {path} is not valid JSON: {exc}") from exc
    if isinstance(payload, dict):
        return payload.get("comments")
    return payload


def build_parser():
    """Build the CLI parser: a read-only `resolve --key` subcommand and a
    bounded `comment` subcommand that previews by default and posts only
    with `--post`. There is deliberately no credential flag on either --
    credentials are read from the environment only, never from argv."""
    parser = argparse.ArgumentParser(
        description="Jira Cloud issue reader with one bounded comment writer.")
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser(
        "resolve", help="Resolve one issue key to a normalized JSON record.")
    resolve.add_argument(
        "--key", required=True, help="Jira issue key, e.g. ABC-123.")

    comment = sub.add_parser(
        "comment",
        help=("Preview the spec-loop intake comments for one issue -- or, "
              "with --post, actually add them."))
    comment.add_argument(
        "--key", required=True, help="Jira issue key, e.g. ABC-123.")
    comment.add_argument(
        "--comments", required=True,
        help=("path to a JSON file holding the `comments` array printed by "
              "jira_intake.py render (or that whole payload object)"))
    comment.add_argument(
        "--post", action="store_true",
        help=("ARM THE WRITE. Without this flag nothing is posted: the "
              "lane issues GETs only and reports what it would post."))
    return parser


def _dispatch(args):
    """Run the requested subcommand and return the object to print."""
    if args.command == "comment":
        return run_comment_lane(
            args.key, _load_comments(args.comments), args.post)
    return resolve_issue(args.key)


def main(argv=None):
    """Parse args, dispatch, print one JSON object. Exit 0 ok, 1 contract
    failure, 2 usage / unreadable input. JiraUsageError is caught BEFORE
    JiraError: it subclasses JiraError, so the reverse order would collapse
    exit 2 into exit 1.

    The two refusal shapes match dag.py:775-782 / run_state.py:1289-1295's
    established idiom, so downstream tooling can tell them apart by stream:
    a contract failure (exit 1) prints the {"ok": false, "errors": [...]}
    JSON to STDOUT; a usage failure (exit 2) prints plain 'error: %s' text
    to STDERR."""
    args = build_parser().parse_args(argv)
    try:
        payload = _dispatch(args)
    except JiraUsageError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except JiraError as exc:
        refusal = {"ok": False, "errors": [str(exc)]}
        print(json.dumps(refusal, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
