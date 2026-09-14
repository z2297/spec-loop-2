#!/usr/bin/env python3
"""Azure DevOps Services work-item reader with ONE bounded comment writer (stdlib only).

Resolves one Azure DevOps work-item id to a normalized JSON record (org,
project, id, web url, title, work item type, state, the HTML description
rendered to text, acceptance criteria with the source that won, repro
steps, and the full paginated comment list). Authenticates with HTTP Basic
auth built from an EMPTY username and the PAT in ADO_PAT, against the org
named by ADO_ORG_URL. Also previews -- and, only under an explicit --post,
adds -- the spec-loop intake comments on one work item.

Design decisions:
  - Mirrors plugins/spec-loop/scripts/jira_client.py's transport doctrine by
    COPY AND ADAPT, never by import: there is deliberately no shared helper
    module with jira_client.py or pr_resolver.py -- duplication over
    coupling, so loosening one provider cannot loosen another.
  - THE READ LANE IS STRUCTURALLY INCAPABLE OF A MUTATING VERB: _http_get
    takes no `data` parameter at all -- and no `method` parameter for a
    caller to widen -- and hardcodes method="GET". urllib.request.Request
    infers POST from a non-None `data`, so the ABSENCE of that parameter is
    the proof, not a comment. Any writer added to this module in future is
    a separate function with its own bounded surface and its own tests; it
    cannot loosen the read lane, and the read lane's tests are scoped to
    _http_get's own source so that stays true.
  - This repo already reaches Azure DevOps for pull requests through the
    `az` CLI (pr_resolver.py), and this module deliberately does NOT: the
    CLI has no command that lists a work item's comments, so the read-back
    dedupe gate the comment lane depends on is impossible through it, and
    `az boards work-item update` is the general mutation command rather
    than a structurally comment-only surface. Raw REST on urllib is the
    only transport that can carry the safety design. No subprocess, and no
    dependency on `az`, including `az devops invoke`.
  - Host allow-list: ADO_ORG_URL must be https and its hostname must match
    ALLOWED_HOST_RE -- dev.azure.com (with the org as the first path
    segment) or the legacy <org>.visualstudio.com form. Azure DevOps
    Server / on-prem hosts are out of scope and are refused with a message
    naming both supported forms; there is deliberately no opt-in
    extra-hosts env var, since that would re-open the exact hole the
    allow-list closes.
  - Redirects are refused outright (a custom HTTPRedirectHandler whose
    redirect_request returns None), not followed-with-header-stripped. The
    org URL is user-supplied, so pr_resolver's hardcoded-origin property is
    gone and an Authorization header must never be replayed to another
    origin.
  - NO URL TAKEN FROM A RESPONSE BODY IS EVER FETCHED. Every request URL is
    composed locally from the validated api_root plus a literal path. The
    comment list returns both a `continuationToken` and a fully-formed
    `nextPage` URL chosen by the server; `nextPage` is never read and never
    fetched -- it would pass through neither the host allow-list (which
    validates the org URL, not a URL the client volunteers to fetch) nor
    the redirect refusal (there is no 3xx to refuse). Pages are composed
    from the validated api_root plus the regex-validated,
    percent-encoded continuationToken.
  - THE PROJECT COMES FROM THE READ, NEVER FROM THE ENVIRONMENT. The
    work-item GET takes `project` as an optional path segment, so the read
    is issued with org + id alone and the project is taken from the
    response's System.TeamProject field -- which the comment endpoints
    (where project is REQUIRED) then use. ADO_PROJECT is therefore optional
    and, when set, is only an assertion: a mismatch refuses and names both
    values, preferring neither. You cannot mis-set what you do not set.
  - `org` is the one unavoidable environment input, so it is closed against
    the response too: the body-supplied _links.html.href must start with
    the already-validated api_root, or the resolve refuses. The href is
    stored and displayed, never fetched -- and it is displayed at the
    moment an operator authorizes a write, so it is validated before it can
    be printed.
  - Three api-versions, three constants, and they differ ON PURPOSE (the
    work-item read is stable 7.1, the comment list is 7.1-preview.4, the
    comment add is 7.0-preview.3). A test asserts they are not all equal so
    a well-meaning "consistency" edit fails loudly.
  - Acceptance criteria are NOT a universal field: Microsoft.VSTS.Common.
    AcceptanceCriteria exists on Bug, Epic, Feature and Product Backlog
    Item only, so an Agile User Story and a Task have none. The field's
    absence is the common case, not a resolve failure. Criteria resolve in
    a fixed order -- (1) the field when present and non-empty, else (2) an
    "Acceptance Criteria" section of the rendered description, else empty --
    and the winner is recorded in acceptance_criteria_source. There is no
    field-catalogue GET: the field is either in the `fields` map or it is
    not, so path (1) is a dict lookup, not an HTTP call.
  - A Bug's detail usually lives in Microsoft.VSTS.TCM.ReproSteps rather
    than System.Description, so repro steps get their OWN record field.
    Silently substituting them into `description` would hide which field a
    reader is looking at.
  - Every comment-sweep value that could silently SHRINK the dedupe
    haystack raises instead: a comment with missing or empty `text`, a
    missing or non-numeric `totalCount`, a continuationToken that does not
    match its allow-list, and a terminating sweep that collected fewer
    comments than totalCount.
  - The dedupe haystack is normalized from the comment's `text` -- what was
    STORED -- and never from `renderedText`, an optional HTML rendering
    that a renderer may entity-encode or strip. A marker the renderer
    altered would go unmatched and the comment lane would post again on a
    live work item. `renderedText` and `nextPage` are not surfaced in the
    record at all.
  - Descriptions are HTML, not ADF JSON, so the renderer is an
    html_to_text() walker over tag soup and entities. It is
    LOSSY BY DESIGN: it produces review-readable text, not a document that
    round-trips back into HTML.
  - No subprocess, no filesystem writes, and no clock read anywhere in this
    module: the controller owns the clock. Azure DevOps' own createdDate /
    modifiedDate strings are echoed verbatim.
  - THE WRITE IS OFF BY DEFAULT AND BOUNDED TO ONE VERB. `comment` previews
    by default, issuing GETs only; `--post` is the only thing that arms the
    HTTP verb. _http_post is the module's SOLE writer and adds one work-item comment
    and nothing else: no state transition, no field edit or PATCH, no
    assignee change, no work-item or child creation, no relation/link edit,
    no attachment, no comment edit, no comment delete, no reaction. It is a
    SEPARATE function from _http_get, which still takes no `data` parameter
    and no `method` parameter -- that absence is the read lane's proof, so
    the writer is added beside it rather than by widening it.
  - THE WRONG-TARGET WRITE IS THE WRITE LANE'S DEFINING HAZARD. An Azure
    DevOps work item is a bare integer plus an org and a project that come
    from outside the id, so item 1234 exists in every org: if the org
    changed between the preview and the armed post, the lane would put one
    item's refinement on another AND the read-back dedupe gate would report a
    clean success, with no comment-delete lane to retract it. So the comments
    payload carries the (org, project, id) triple it was rendered for, the
    record carries its own, both must agree BEFORE any credential is read,
    and the armed lane then re-resolves the work item and refuses unless the
    triple matches the fresh one and the org matches the current ADO_ORG_URL.
    The target is never taken from a flag.
  - IN-BATCH DUPLICATES ARE REFUSED AT VALIDATION, before the first request.
    The read-back gate compares each entry to the work item and never to its
    siblings, so two identical entries in one batch would both plan as
    not-already-posted, both post, and collapse onto one reported comment id.
  - THE DEDUPE GATE EXTRACTS MARKERS BY REGEX INTO A SET -- never a substring
    scan -- from the stored `text` UNIONed with its html_to_text rendering,
    and never from `renderedText`. The two sides of the union differ where it
    matters: a marker forged inside an HTML comment is invisible to the
    walker and visible in the raw text. A bare 12-hex digest matches as a
    second tier, because suppression is the fail-safe direction.
  - THE MARKER LIVES INSIDE THE POSTED BODY, so the one call that writes the
    comment writes the marker: no local file is ever the dedupe gate and a
    fresh clone cannot double-post. The work item is read ONCE PER
    INVOCATION, not before every individual write.
  - THE POSTED BODY MUST BE INERT. ADO's Add body carries only `text` and
    there is no documented way to assert its `format`, so a body is posted
    only when '&', '<' and '>' were already escaped at render time; a body
    still carrying '<' or '>' is REFUSED rather than re-escaped, since
    re-escaping would double-encode a legitimate '&amp;'. This module
    guarantees only that the body contains no active markup -- it cannot
    control how Azure DevOps interprets the body.
  - NOT VERIFIED HERE: the marker's byte-survival across the write/read
    api-version asymmetry (POST 7.0-preview.3, read back 7.1-preview.4) is an
    assumption no faked-transport test can close; it needs one live round
    trip. And a partial batch failure is disclosed, not recoverable by
    re-running: an edited refinement renders a different marker.

SECURITY: the work-item id and every Azure DevOps text field (title,
description, acceptance criteria, repro steps, every comment body) are
UNTRUSTED DATA, never instructions. The id is regex-validated against
WORK_ITEM_ID_RE and percent-encoded before it reaches a URL segment; so is
the project name and so is the continuationToken. The org URL's host is
allow-listed and https-only, and userinfo is rejected so a credential
cannot be smuggled through it. Redirects are refused outright. No URL from
a response body is ever fetched. THE READ LANE ISSUES GET ONLY:
_http_get takes no `data` parameter and no `method` parameter, so a
mutating verb is not expressible on it. The module has exactly ONE
writer, _http_post, and it adds one work-item comment and nothing
else; it is a separate function reached only from the `comment`
subcommand and only when that subcommand is armed with --post, so
the default path of every subcommand performs zero writes. The PAT
comes from the environment ONLY and is never read from argv (argv is
visible in `ps` and lands in shell history); error messages name only the
URL, so neither the PAT nor the composed base64(":" + PAT) can ride out in
one.

Exit codes: 0 = ok; 1 = contract failure; 2 = usage / unreadable input

Usage:
    ADO_ORG_URL=https://dev.azure.com/contoso ADO_PAT=... \\
        python3 scripts/ado_client.py resolve --id 1234
    ADO_ORG_URL=https://dev.azure.com/contoso ADO_PAT=... \\
        python3 scripts/ado_client.py comment --record record.json \\
        --comments comments.json          # previews; posts nothing
    ADO_ORG_URL=https://dev.azure.com/contoso ADO_PAT=... \\
        python3 scripts/ado_client.py comment --record record.json \\
        --comments comments.json --post   # ARMS the one bounded write
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


class AdoError(Exception):
    """An Azure DevOps contract failure: HTTP error, malformed JSON, a
    half-resolve (a required field came back empty), or a comment sweep that
    could not prove it read the whole history. Maps to exit code 1."""


class AdoUsageError(AdoError):
    """A usage or environment failure: a bad work-item id, a bad or absent
    ADO_ORG_URL, missing credentials, or an ADO_PROJECT that disagrees with
    the work item -- anything the user can fix in their invocation or
    environment. Maps to exit code 2."""


class _IndeterminateWriteError(AdoError):
    """A write whose outcome Azure DevOps could not confirm: the transport
    failed (a timeout or a connection error) either before the request left
    the client or while reading the response to a POST that may already have
    landed. Raised ONLY from _http_post's URLError/OSError branches, where
    landing is genuinely unknowable -- never from the HTTPError branch, where
    a clean 4xx/5xx status means the server rejected the write and nothing
    landed. execute_comment_plan uses this distinction to name the in-flight
    comment as indeterminate rather than silently excluding it from the
    partial-batch disclosure."""


WORK_ITEM_ID_RE = re.compile(r"^[0-9]{1,10}$")
ORG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
ALLOWED_HOST_RE = re.compile(
    r"^(?:dev\.azure\.com|[A-Za-z0-9][A-Za-z0-9-]{0,60}\.visualstudio\.com)$")

_SUPPORTED_FORMS = (
    "https://dev.azure.com/<org> or the legacy https://<org>.visualstudio.com "
    "(Azure DevOps SERVICES only -- Azure DevOps Server / on-prem hosts are "
    "not supported by this connector)")


def validate_work_item_id(raw):
    """Validate an UNTRUSTED work-item id and return it as a string. An Azure
    DevOps work item is addressed by a bare integer -- there is no
    self-describing ABC-123 key -- so the allow-list is digits only. Rejects a
    leading '-' (argument injection), path separators, whitespace and
    newlines. Accepts an int for convenience since the API returns one."""
    text = str(raw) if isinstance(raw, int) else (raw or "")
    if not WORK_ITEM_ID_RE.fullmatch(text):
        raise AdoUsageError(
            f"invalid Azure DevOps work-item id {raw!r}: must match "
            f"{WORK_ITEM_ID_RE.pattern} (1-10 digits, e.g. 1234)")
    return text


def _split_org_url(raw):
    """Split an UNTRUSTED ADO_ORG_URL into urlsplit's parts, or None when the
    value cannot be split at all (a malformed IPv6 host) or carries a port
    that cannot be parsed as an integer (both raise a bare ValueError from
    urllib.parse, since parts.port is computed lazily on attribute access).
    Isolating that ValueError here keeps every malformed org URL on the
    fail-closed AdoUsageError path instead of an uncaught traceback."""
    try:
        parts = urllib.parse.urlsplit(raw or "")
        parts.port  # noqa: B018 -- force the lazy, possibly-raising parse now
    except ValueError:
        return None
    return parts


def _redacted_org_url(raw, parts):
    """Render raw for the rejection message with any userinfo stripped, so a
    credential smuggled into ADO_ORG_URL's userinfo is never echoed back into
    the machine-readable error object. Falls back to '<unparsable>' when the
    value could not even be split (parts is None)."""
    if parts is None:
        return "<unparsable>"
    if parts.username or parts.password:
        return f"{parts.scheme}://<redacted>@{parts.hostname or ''}"
    return f"{parts.scheme}://{parts.hostname or ''}"


def _org_url_refusal(raw, parts):
    """The one AdoUsageError every org-URL rejection raises. Names both
    supported forms, per the run constraint that an unsupported host produces
    a clear refusal rather than a partially working path."""
    return AdoUsageError(
        f"invalid ADO_ORG_URL {_redacted_org_url(raw, parts)!r}: must be "
        f"{_SUPPORTED_FORMS}")


def _org_from_parts(parts):
    """Extract the org from already-scheme/host-validated urlsplit parts, or
    None when the URL does not name exactly one org. dev.azure.com carries the
    org as its FIRST AND ONLY path segment; the legacy form carries it as the
    hostname's first label and must have no path. An extra path segment is
    rejected rather than ignored: silently dropping '/MyProject' would let an
    operator believe they had scoped the connector to a project when the
    project actually comes from the work-item read."""
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]
    if host == "dev.azure.com":
        if len(segments) != 1:
            return None
        return segments[0]
    if segments:
        return None
    return host.split(".")[0]


def validate_org_url(raw):
    """Validate an UNTRUSTED ADO_ORG_URL and return (api_root, org).

    api_root is the LOCALLY COMPOSED prefix every request URL in this module
    is built from -- 'https://dev.azure.com/<org>' for the modern form, the
    bare 'https://<org>.visualstudio.com' origin for the legacy form -- with
    no trailing slash, no path beyond the org, no query and no fragment.
    Discarding anything else is deliberate: every API path is composed from
    api_root plus a literal '/_apis/...' suffix.

    Requires https, rejects embedded userinfo (userinfo smuggling) and an
    explicit port, requires the hostname to match ALLOWED_HOST_RE, and
    requires the org to match ORG_RE -- the org is a URL path segment, so a
    '..' or a '/' in it must never get that far."""
    parts = _split_org_url(raw)
    ok = bool(
        parts is not None
        and parts.scheme == "https"
        and not parts.username
        and not parts.password
        and not parts.port
        and not parts.query
        and not parts.fragment
        and ALLOWED_HOST_RE.fullmatch(parts.hostname or "")
    )
    org = _org_from_parts(parts) if ok else None
    if not org or not ORG_RE.fullmatch(org):
        raise _org_url_refusal(raw, parts)
    host = parts.hostname.lower()
    if host == "dev.azure.com":
        return (f"https://{host}/{urllib.parse.quote(org, safe='')}", org)
    return (f"https://{host}", org)


# Three api-versions, three constants, and they differ ON PURPOSE (verified on
# Microsoft Learn, 2026-09-14). Do not "modernize" or unify them: the comment
# list's newest documented version is a 7.1 preview and the comment add's is a
# 7.0 preview. TestApiVersionsAreThreeDistinctConstants fails if they collapse.
API_VERSION_WORK_ITEM = "7.1"            # GET .../_apis/wit/workitems/{id}
API_VERSION_COMMENTS_READ = "7.1-preview.4"  # GET .../workItems/{id}/comments
# Referenced by no code path in THIS read lane -- it is the documented version
# for the bounded comment-add lane, which lives in THIS module and POSTs with
# THIS constant, so pinning it here beside its siblings keeps the value the
# write lane uses under the not-all-equal test rather than letting a second
# copy drift.
API_VERSION_COMMENT_ADD = "7.0-preview.3"

PROJECT_ENV_VAR = "ADO_PROJECT"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every 3xx. ADO_ORG_URL is user-supplied, so pr_resolver's
    hardcoded-origin property is gone: following a redirect could replay the
    Authorization header to another origin. Returning None makes urllib raise
    the HTTPError instead of following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Return None so urllib treats the 3xx as a terminal error."""
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

CRED_VARS = ("ADO_ORG_URL", "ADO_PAT")


def credentials():
    """Read the Azure DevOps credentials from the ENVIRONMENT ONLY and fail
    closed with an actionable message when either is unset. Never read from
    argv: argv is visible in `ps` and lands in shell history.

    Only ADO_ORG_URL and ADO_PAT are required. ADO_PROJECT is deliberately
    OPTIONAL -- the project comes from the work item's own System.TeamProject
    -- and the message says so, because demanding a variable the design says
    to leave unset would push operators into the wrong-target failure mode
    that optionality exists to close."""
    values = {name: (os.environ.get(name) or "").strip() for name in CRED_VARS}
    missing = [name for name in CRED_VARS if not values[name]]
    if missing:
        raise AdoUsageError(
            "Azure DevOps access requires the environment variable(s) "
            + ", ".join(missing)
            + f". Set ADO_ORG_URL to {_SUPPORTED_FORMS}, and ADO_PAT to a "
            "personal access token with the 'Work Items (Read)' scope. "
            f"{PROJECT_ENV_VAR} is OPTIONAL: the project is read from the "
            "work item itself, and setting this variable only asserts that "
            "the work item lives in that project. Pass these in the "
            "environment, never on the command line."
        )
    api_root, org = validate_org_url(values["ADO_ORG_URL"])
    return (api_root, org, values["ADO_PAT"])


def _auth_header(pat):
    """Build the Azure DevOps Basic auth header: base64(":" + pat), i.e. a PAT
    with an EMPTY username. Verified against Microsoft Learn's own sample,
    which is `curl -u :{PAT}` (read 2026-09-14). Microsoft now recommends
    Entra tokens where possible; PATs remain supported and are the only auth
    flow in scope for this connector."""
    raw = f":{pat}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _http_get(url, pat):
    """HTTP GET via the no-redirect opener. THE ONLY network entry point in
    this module, and it is READ-ONLY BY CONSTRUCTION: there is no `data`
    parameter for a caller to pass a body through and no `method` parameter
    for a caller to widen, so a mutating verb is not expressible here.
    urllib.request.Request infers POST from a non-None `data`, which is
    exactly why `data` is absent from the signature rather than defaulted to
    None.

    Errors reference only the URL -- the credential rides in a header, so
    neither the PAT nor the composed base64(":" + PAT) can appear in an
    exception message."""
    headers = {
        "Authorization": _auth_header(pat),
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with _OPENER.open(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise AdoError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise AdoError(f"network error fetching {url}: {exc.reason}") from exc
    except OSError as exc:
        # urllib only wraps an OSError raised by h.request() into a URLError
        # (see CPython's AbstractHTTPHandler.do_open); an OSError out of
        # h.getresponse() or resp.read() -- a timeout or a reset while reading
        # the response body -- propagates unwrapped and would otherwise slip
        # past the AdoError handling above and past main()'s exit-1 JSON
        # contract as a raw traceback. Caught here, terminally, so every
        # transport failure is an AdoError. The message names only the URL, so
        # no credential can ride out in it.
        raise AdoError(f"network error fetching {url}: {exc}") from exc


def _parse_json(raw, what):
    """json.loads with an actionable AdoError, so a malformed response fails
    with a clear message rather than a raw traceback."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdoError(
            f"Azure DevOps returned a {what} response that is not valid JSON "
            f"({exc})") from exc


HEADING_PREFIX = "## "

# Tags whose boundaries are a paragraph break in the rendered text.
_BLOCK_TAGS = frozenset({
    "p", "div", "section", "article", "blockquote", "pre", "table", "tr",
    "ul", "ol", "dl", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6",
})
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
# Tags whose text content is markup, not prose, and is dropped entirely.
_DROP_TAGS = frozenset({"script", "style"})
_BLANK_RUN_RE = re.compile(r"\n{3,}")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+\n")


class _HtmlToText(HTMLParser):
    """Collect an HTML fragment's prose into blank-line-separated blocks.

    Deliberately small and forgiving: html.parser never raises on tag soup
    (convert_charrefs handles entities for us), an unrecognized tag
    contributes its text rather than vanishing, and an unclosed tag just
    leaves the block open. HTML COMMENTS ARE DROPPED -- handle_comment is not
    implemented -- which is why the comment lane's dedupe haystack also
    searches the raw stored text: a marker hidden inside an HTML comment is
    invisible to this walker and visible there."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._dropping = 0

    def handle_starttag(self, tag, attrs):
        """Open a tag: suppress markup-only content, break blocks, bullet a
        list item, and treat <br> as a single newline."""
        if tag in _DROP_TAGS:
            self._dropping += 1
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")
            if tag in _HEADING_TAGS:
                self.parts.append(HEADING_PREFIX)

    def handle_startendtag(self, tag, attrs):
        """A self-closing tag (<br/>) opens and closes in one token; only the
        open side has any effect here."""
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        """Close a tag: stop suppressing, or end the current block."""
        if tag in _DROP_TAGS:
            self._dropping = max(0, self._dropping - 1)
        elif tag == "li":
            # DELIBERATELY NOTHING. handle_starttag already opens every list
            # item with "\n- ", so appending anything here doubles the break
            # and renders consecutive items as "- a\n\n- b" instead of the
            # contracted "- a\n- b". The enclosing </ul>/</ol> is a _BLOCK_TAG
            # and supplies the paragraph break that closes the list.
            # Verified against the prescribed _tidy_text: "- a\n- b" for
            # <ul><li>a</li><li>b</li></ul>, "- a\n\nafter" for a list
            # followed by <p>after</p>.
            return
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data):
        """Append literal text unless inside a markup-only element."""
        if not self._dropping:
            self.parts.append(data)

    def text(self):
        """The collected parts as one string."""
        return "".join(self.parts)


def _tidy_text(raw):
    """Normalize a walked fragment: unescape any entity html.parser left
    behind, drop trailing spaces before a newline, collapse a run of three or
    more newlines to one blank line, and strip the ends."""
    text = html.unescape(raw).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ")
    text = _TRAILING_SPACE_RE.sub("\n", text)
    return _BLANK_RUN_RE.sub("\n\n", text).strip()


def html_to_text(raw):
    """Render an Azure DevOps HTML field (System.Description,
    Microsoft.VSTS.Common.AcceptanceCriteria, Microsoft.VSTS.TCM.ReproSteps,
    or a comment's stored text) to plain, review-readable text. (PURE)

    LOSSY BY DESIGN, in exactly the way jira_client.adf_to_text is: it
    produces text for humans to read, not a document that round-trips back
    into HTML. Headings of every level render with the same HEADING_PREFIX --
    the level is discarded, and that prefix is what lets
    acceptance_criteria_from_description find a section boundary. Anything
    that is not a string (None, a number, a list) renders as '' rather than
    raising, because a field of an unexpected shape is not prose."""
    if not isinstance(raw, str) or not raw:
        return ""
    parser = _HtmlToText()
    parser.feed(raw)
    parser.close()
    return _tidy_text(parser.text())


# Verified reference names (Microsoft Learn field index, read 2026-09-14).
# Fields are a FLAT map under `fields`, keyed by reference name.
FIELD_TITLE = "System.Title"                  # String, all types
FIELD_DESCRIPTION = "System.Description"      # HTML, all types
FIELD_TYPE = "System.WorkItemType"            # String, all types
FIELD_PROJECT = "System.TeamProject"          # String, all types
FIELD_STATE = "System.State"                  # String, all types
# HTML, and present on Bug / Epic / Feature / Product Backlog Item ONLY. An
# Agile User Story and a Task have NO acceptance-criteria field at all, so its
# absence is the common case and never a resolve failure.
FIELD_ACCEPTANCE_CRITERIA = "Microsoft.VSTS.Common.AcceptanceCriteria"
# HTML, Bug only -- and usually where a Bug's real detail lives, which is why
# it gets its own record field instead of being substituted into description.
FIELD_REPRO_STEPS = "Microsoft.VSTS.TCM.ReproSteps"

COMMENT_PAGE_SIZE = 100

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def work_item_url(api_root, work_item_id):
    """Compose the work-item read URL LOCALLY from the validated api_root plus
    a literal path. The project segment is deliberately OMITTED: it is
    optional on this endpoint, and issuing the read without it is what lets
    the project be discovered from the response instead of supplied from the
    environment. The id is re-validated and percent-encoded here even though
    the caller validated it -- defence in depth, per the rule that an
    untrusted value is encoded regardless before it reaches a URL segment."""
    encoded = urllib.parse.quote(validate_work_item_id(work_item_id), safe="")
    return (f"{api_root}/_apis/wit/workitems/{encoded}"
            f"?api-version={API_VERSION_WORK_ITEM}")


def comments_url(api_root, project, work_item_id, continuation_token=None):
    """Compose a comment-list page URL LOCALLY from the validated api_root, the
    percent-encoded project (REQUIRED on this endpoint) and a literal path.

    NOTE THE TWO DISTINCT TRANSFORMS OF ONE PROJECT NAME: this URL needs the
    ORIGINAL name, quote(..., safe="")-encoded. An artifact path needs a lossy
    filesystem slug instead. Reusing a slug here would 404 on every project
    whose name contains a space.

    The continuation token is an opaque SERVER-CHOSEN string: it is validated
    against CONTINUATION_TOKEN_RE by the caller and percent-encoded here. The
    response's fully-formed `nextPage` URL is never read and never fetched --
    composing the URL locally is what keeps every request inside the
    already-validated origin."""
    encoded_project = urllib.parse.quote(project, safe="")
    encoded_id = urllib.parse.quote(validate_work_item_id(work_item_id), safe="")
    url = (f"{api_root}/{encoded_project}/_apis/wit/workItems/{encoded_id}"
           f"/comments?api-version={API_VERSION_COMMENTS_READ}"
           f"&$top={COMMENT_PAGE_SIZE}")
    if continuation_token:
        token = urllib.parse.quote(continuation_token, safe="")
        url += f"&continuationToken={token}"
    return url


def fetch_work_item(api_root, pat, work_item_id):
    """GET one work item READ-ONLY and return the raw response object. The id
    is validated before any request is issued (inside work_item_url). A
    response that is not a JSON object is a contract failure rather than
    something to index into."""
    url = work_item_url(api_root, work_item_id)
    payload = _parse_json(_http_get(url, pat).decode("utf-8"), "work item")
    if not isinstance(payload, dict):
        raise AdoError(
            "Azure DevOps returned a work-item response that is not an "
            "object; refusing to read fields from it")
    return payload


def resolve_project(fields):
    """Resolve the project from the work item's own System.TeamProject, which
    is present on every work-item type. THE PROJECT IS NEVER TAKEN FROM THE
    ENVIRONMENT: the comment endpoints require it, and an operator-supplied
    project could disagree with where the item actually lives -- a 404 at
    best, a comment addressed to another item's route at worst.

    An absent or empty value is a HALF-RESOLVE and raises: the record would
    otherwise carry no way to reconstruct the comment route. A name carrying a
    control character or a line break is REFUSED, never rewritten -- it also
    lands in artifact front matter downstream, where a raw newline inside a
    quoted scalar is a hazard."""
    raw = fields.get(FIELD_PROJECT)
    project = raw.strip() if isinstance(raw, str) else ""
    if not project:
        raise AdoError(
            f"Azure DevOps returned a work item with no {FIELD_PROJECT}; "
            "refusing to emit a record that cannot name its own project")
    if _CONTROL_CHAR_RE.search(project):
        raise AdoError(
            f"the work item's {FIELD_PROJECT} contains a control character or "
            "line break; refusing it rather than rewriting a project name")
    return project


def assert_project_matches_env(project):
    """Treat ADO_PROJECT, when set, as an ASSERTION about the resolved project
    and refuse on a mismatch, naming both values and preferring neither. When
    unset -- the recommended state -- this asserts nothing: you cannot mis-set
    what you do not set, and removing the input is strictly stronger than
    validating it.

    THE COMPARISON IS DELIBERATELY EXACT (after stripping surrounding
    whitespace only). Azure DevOps project names are case-preserving, this is
    an assertion-only path that fails closed and names both values preferring
    neither, and a case-insensitive or punctuation-folding compare would
    quietly widen what the assertion accepts. Do not 'fix' it into one."""
    expected = (os.environ.get(PROJECT_ENV_VAR) or "").strip()
    if expected and expected != project:
        raise AdoUsageError(
            f"{PROJECT_ENV_VAR} is set to {expected!r} but the work item "
            f"lives in project {project!r}; refusing to continue. Unset "
            f"{PROJECT_ENV_VAR} (the project is read from the work item) or "
            "correct it to match.")
    return None


def validate_web_url(href, api_root):
    """Validate the work item's body-supplied _links.html.href and return it.

    THIS URL IS NEVER FETCHED -- it is stored in the record and DISPLAYED. It
    is validated anyway, and for a specific reason: it is displayed in the
    confirmation prompt where an operator authorizes an irreversible write, so
    a spoofed href would look to them like a genuine work-item link at exactly
    the wrong moment.

    Requiring it to start with the already-validated api_root plus '/' does
    double duty: it re-applies the host allow-list to a value that never
    passed through it, and it asserts the org the response reports is the org
    that was asked for -- a wrong org mis-targets exactly like a wrong
    project. The '/' is load-bearing: without it 'contoso-evil' would pass as
    'contoso'."""
    text = href if isinstance(href, str) else ""
    prefix = f"{api_root}/"
    if not text.lower().startswith(prefix.lower()):
        raise AdoError(
            "the work item's web URL does not sit under the requested "
            f"organization {api_root} (the response's URL is on "
            f"{_href_origin(text)}); refusing to emit or display it. If your "
            "organization has both host forms, set ADO_ORG_URL to the form "
            "Azure DevOps itself returns.")
    return text


def _href_origin(text):
    """Render just the scheme+host of a body-supplied href, for a refusal
    message. SCHEME AND HOST ONLY: the path and query are untrusted response
    data and must never be echoed. Returns '<unparseable>' rather than raise,
    because this runs only on an error path.

    Without this, the realistic trigger -- an org whose _links.html.href comes
    back on the legacy <org>.visualstudio.com host while ADO_ORG_URL is the
    dev.azure.com form, or the reverse -- produces a correct, fail-closed exit
    1 that reads to the operator as an unexplained outage. The mocked
    transport suite cannot surface that; the message has to."""
    try:
        parts = urllib.parse.urlsplit(text)
    except ValueError:
        return "<unparseable>"
    if not parts.scheme or not parts.hostname:
        return "<unparseable>"
    return f"{parts.scheme}://{parts.hostname}"


MAX_COMMENT_PAGES = 100

# The continuationToken is an opaque SERVER-CHOSEN string that lands in a
# query string. It is allow-listed rather than trusted, and a token that does
# not match RAISES -- dropping it would silently truncate the sweep, which is
# the same failure mode as a missing totalCount.
CONTINUATION_TOKEN_RE = re.compile(r"^[A-Za-z0-9+/=_.\-]{1,512}$")

_MISSING_COMMENTS_MSG = (
    "Azure DevOps comment page is missing the 'comments' list; cannot read "
    "the full comment history")
_MISSING_TOTAL_MSG = (
    "Azure DevOps comment page is missing a numeric 'totalCount'; cannot "
    "tell whether the full comment history has been read")
_MISSING_TEXT_MSG = (
    "Azure DevOps returned a comment with no 'text'; refusing to dedupe "
    "against a comment history with a hole in it")
_BAD_TOKEN_MSG = (
    "Azure DevOps returned a 'continuationToken' outside "
    + CONTINUATION_TOKEN_RE.pattern
    + "; refusing a possibly-truncated comment history rather than dropping "
      "the token")


def _comment_id(raw):
    """Read a comment's id, accepting either documented spelling. The
    comment-list DEFINITION table names the field `id`, while Microsoft's own
    SAMPLE PAYLOADS on the list and add pages show `commentId`. Read
    defensively: prefer whichever is present."""
    for key in ("id", "commentId"):
        value = raw.get(key)
        if value is not None:
            return str(value)
    return ""


def _comment_text(raw):
    """Read a comment's STORED text, fail-closed.

    This is the dedupe haystack, and it comes from `text` -- never from
    `renderedText`, an optional HTML rendering of the same body. A marker that
    an HTML renderer entity-encoded or stripped would go UNMATCHED, every
    entry would plan as not-already-posted, and the comment lane would post
    again on a live work item.

    `text` is on the base Comment definition and is returned without $expand
    (verified 2026-09-14), so a missing one is a shape surprise -- and three
    real shapes still produce one: a redacted comment surfaced under
    includeDeleted, a legitimately empty comment, and any future projection
    change. A documented default projection is not a runtime guarantee, so
    this raises rather than contribute an empty string to the haystack."""
    text = raw.get("text")
    if not isinstance(text, str) or not text:
        raise AdoError(_MISSING_TEXT_MSG)
    return text


def _normalize_comment(raw):
    """Normalize one raw comment to
    {"id", "author", "created", "modified", "text"}. `renderedText` and
    `nextPage` are deliberately NOT surfaced: one would tempt a later change
    to dedupe against a rendering, the other is a server-chosen URL nothing
    may fetch."""
    if not isinstance(raw, dict):
        raise AdoError(_MISSING_TEXT_MSG)
    created_by = raw.get("createdBy")
    author = ""
    if isinstance(created_by, dict):
        author = created_by.get("displayName")
    return {
        "id": _comment_id(raw),
        "author": author or "",
        "created": raw.get("createdDate") or "",
        "modified": raw.get("modifiedDate") or "",
        "text": _comment_text(raw),
    }


def _page_total(page):
    """Extract one page's reported `totalCount` as an int, fail-closed. A
    missing or non-numeric totalCount must NOT be treated as 0 -- collapsing
    it to 0 would make the very first page look complete and silently truncate
    the sweep, defeating comment-based dedupe on a chatty work item."""
    total = page.get("totalCount")
    if isinstance(total, bool) or not isinstance(total, (int, float, str)):
        raise AdoError(_MISSING_TOTAL_MSG)
    try:
        return int(total)
    except (TypeError, ValueError):
        raise AdoError(_MISSING_TOTAL_MSG) from None


def _page_token(page):
    """Extract one page's `continuationToken`, or None when the sweep is done.
    A present token that fails CONTINUATION_TOKEN_RE RAISES -- dropping it
    would end the sweep early and dedupe against a truncated history."""
    token = page.get("continuationToken")
    if token is None or token == "":
        return None
    if not isinstance(token, str) or not CONTINUATION_TOKEN_RE.fullmatch(token):
        raise AdoError(_BAD_TOKEN_MSG)
    return token


def _page_comments(page):
    """The page's `comments` list, fail-closed on any other shape: swallowing
    a shape change here would silently degrade to 'no comments' and defeat
    dedupe."""
    if not isinstance(page, dict):
        raise AdoError(_MISSING_COMMENTS_MSG)
    comments = page.get("comments")
    if not isinstance(comments, list):
        raise AdoError(_MISSING_COMMENTS_MSG)
    return comments


def _assert_sweep_complete(collected, total, work_item_id):
    """Refuse a sweep that terminated with fewer comments than the server's
    own totalCount: deduping against a truncated history double-posts."""
    if len(collected) < total:
        raise AdoError(
            f"read {len(collected)} comment(s) for work item {work_item_id} "
            f"but Azure DevOps reported totalCount {total}; refusing a "
            "possibly-truncated comment history")


def fetch_comments(api_root, pat, project, work_item_id):
    """GET the FULL, paginated comment list for one work item, normalized to
    [{"id", "author", "created", "modified", "text"}, ...] in server order.

    Sweeps until no `continuationToken` comes back, capped at
    MAX_COMMENT_PAGES so a misbehaving server cannot loop forever, then
    cross-checks the collected count against the reported totalCount. Every
    page URL is composed LOCALLY from the validated api_root plus the
    regex-validated, percent-encoded token: the response's own fully-formed
    `nextPage` URL is never fetched, because it would pass through neither the
    host allow-list (which validated the ORG URL, not a URL this client
    volunteers to fetch) nor the redirect refusal (there is no 3xx to refuse).

    includeDeleted stays at its DEFAULT, so deleted comments are excluded.
    The consequence is deliberate and belongs in the command's prose: deleting
    a spec-loop comment in the Azure DevOps web UI RE-ARMS it, and a later
    armed run posts it again. Setting includeDeleted to true to 'fix' that
    would make a deleted comment permanently suppress a legitimate re-post."""
    collected = []
    total = 0
    token = None
    for _ in range(MAX_COMMENT_PAGES):
        url = comments_url(api_root, project, work_item_id, token)
        page = _parse_json(_http_get(url, pat).decode("utf-8"), "comment page")
        total = _page_total(page)
        collected.extend(_normalize_comment(c) for c in _page_comments(page))
        token = _page_token(page)
        if token is None:
            _assert_sweep_complete(collected, total, work_item_id)
            return collected
    raise AdoError(
        f"comment pagination did not terminate after {MAX_COMMENT_PAGES} "
        f"pages for work item {work_item_id}; refusing a possibly-truncated "
        "comment history")


def comment_add_url(route):
    """Compose the comment-ADD URL LOCALLY from the validated api_root, the
    percent-encoded project and a literal path. `route` is the 3-tuple
    (api_root, project, work_item_id).

    NOTE THE API-VERSION: the add endpoint's newest documented version is
    API_VERSION_COMMENT_ADD ('7.0-preview.3'), which differs ON PURPOSE from
    the comment list's 7.1-preview.4 and the work-item read's stable 7.1
    (Microsoft Learn, read 2026-09-14). Do not 'unify' them.

    The project is the ORIGINAL name, quote(..., safe='')-encoded -- never an
    artifact slug, which would 404 on every project whose name has a space.
    The id is re-validated here even though the caller validated it: an
    untrusted value is encoded regardless before it reaches a URL segment."""
    api_root, project, work_item_id = route
    encoded_project = urllib.parse.quote(project, safe="")
    encoded_id = urllib.parse.quote(validate_work_item_id(work_item_id), safe="")
    return (f"{api_root}/{encoded_project}/_apis/wit/workItems/{encoded_id}"
            f"/comments?api-version={API_VERSION_COMMENT_ADD}")


def _http_post(url, pat, payload):
    """HTTP POST of one JSON `payload` object through the same no-redirect
    opener. THE ONLY MUTATING ENTRY POINT IN THIS MODULE.

    Deliberately a SEPARATE function from _http_get rather than a `method=`
    parameter on it: the read lane's never-a-mutating-verb guarantee is the
    ABSENCE of `data` and `method` from _http_get's signature, and widening
    that signature would erase the proof.

    Errors reference only the URL -- the credential rides in a header, so
    neither the PAT nor the composed base64(':' + PAT) can appear in an
    exception message. A 3xx is terminal (_NoRedirect), so a write never
    replays its Authorization header or its body to another origin."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": _auth_header(pat),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with _OPENER.open(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise AdoError(
            f"HTTP {exc.code} posting to {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        # A URLError here means the request may never have reached the
        # server, OR it may have landed and only the response was lost --
        # urllib cannot distinguish the two. Raised as _IndeterminateWriteError
        # (never plain AdoError) so execute_comment_plan can disclose the
        # in-flight comment as INDETERMINATE rather than silently excluding
        # it, unlike a clean HTTPError status below.
        raise _IndeterminateWriteError(
            f"network error posting to {url}: {exc.reason}") from exc
    except OSError as exc:
        # urllib only wraps an OSError raised by h.request() into a URLError
        # (CPython's AbstractHTTPHandler.do_open); an OSError out of
        # h.getresponse() or resp.read() -- a timeout while reading the
        # response to a POST THAT HAS ALREADY LANDED on the work item --
        # propagates unwrapped and would otherwise slip past the AdoError
        # handling above, past execute_comment_plan's `except AdoError`, and
        # past main()'s exit-1 JSON contract as a raw traceback. Caught here,
        # terminally, as _IndeterminateWriteError, so every write-path
        # transport failure becomes a partial-batch disclosure that names the
        # in-flight comment as indeterminate rather than implying it did not
        # land. The message names only the URL, so no credential can ride out
        # in it.
        raise _IndeterminateWriteError(
            f"network error posting to {url}: {exc}") from exc


def post_comment(route, pat, body):
    """POST ONE comment to ONE Azure DevOps work item. THE SOLE WRITER.

    Bounded on purpose: this adds a comment and nothing else -- no state
    transition, no field edit or PATCH, no assignee change, no work-item or
    child creation, no relation/link edit, no attachment, no comment edit,
    no comment delete, no reaction.

    THE DEDUPE MARKER LIVES INSIDE `body`, so the one network call that
    writes the comment is the same call that writes the marker: no local file
    can make a later run skip a comment that was never actually posted, and a
    fresh clone cannot double-post.

    Verified against Microsoft Learn's Add Comment operation (read
    2026-09-14): the request body is {"text": <string>} -- there is no
    documented way to assert the stored `format` -- and the created comment's
    id appears as `id` in the definition table and `commentId` in the sample
    payload, so both spellings are read. A response carrying neither is
    refused rather than reported as a confirmed write."""
    url = comment_add_url(route)
    raw = _http_post(url, pat, {"text": body}).decode("utf-8")
    created = _parse_json(raw, "created comment")
    if not isinstance(created, dict):
        created = {}
    comment_id = _comment_id(created)
    if comment_id:
        return comment_id
    raise AdoError(
        "Azure DevOps accepted the comment POST for work item "
        f"{route[2]} but returned no comment id; refusing to report a "
        "write that cannot be confirmed")


COMMENT_KINDS = ("understanding", "decision", "open-question")
COMMENT_ENTRY_KEYS = ("kind", "marker", "body")

# THIS MODULE'S OWN COPIES, on purpose: ado_intake.py builds the markers and
# exports the same two patterns, and there is deliberately no shared runtime
# module between them (duplication over coupling), so neither module's change
# can loosen the other's gate. ado_intake's own tests pin the shape both have
# to agree on.
MARKER_RE = re.compile(
    r"\[spec-loop-intake:(?:understanding|decision|open-question):"
    r"[0-9a-f]{12}\]")
# The bare digest, for the dedupe gate's second tier: a round trip that
# rewrote the wrapper but kept the digest must still SUPPRESS a re-post,
# because a false suppression only skips a write while a false miss
# duplicates a comment on a live work item with no delete lane to retract it.
MARKER_DIGEST_RE = re.compile(r"\b[0-9a-f]{12}\b")

# The only two characters that can open active markup. The rendered body was
# escaped at render time (& -> &amp;, < -> &lt;, > -> &gt;), so a body still
# carrying one of these did not come through that escaping and is REFUSED
# rather than posted. It is deliberately not re-escaped here: re-applying the
# transform would double-encode every legitimate '&amp;' and corrupt the body
# the operator previewed. '&' alone cannot activate markup, so it is left
# alone -- the marker contains none of the three characters either way, which
# test_escaping_leaves_the_marker_byte_identical pins.
ACTIVE_MARKUP_CHARS = ("<", ">")


def _entry_field_errors(item, where):
    """Error strings for a comment entry missing one of its string fields.
    Reported before any other check, because every later check indexes one
    of these keys. (PURE)"""
    template = "%s.%s is missing or not a string"
    return [
        template % (where, key)
        for key in COMMENT_ENTRY_KEYS
        if not isinstance(item.get(key), str) or not item.get(key)
    ]


def _entry_kind_errors(item, where):
    """Error strings for an entry whose kind is not one this lane renders.
    ado_intake.py builds only the three; anything else did not come from the
    renderer. (PURE)"""
    if item["kind"] in COMMENT_KINDS:
        return []
    template = "%s.kind %r is not one of %s"
    kinds = ", ".join(COMMENT_KINDS)
    return [template % (where, item["kind"], kinds)]


def _entry_marker_errors(item, where):
    """Error strings for a marker that is malformed or is not alone on line 1
    of the body. (PURE)

    Both halves are load-bearing. The marker must match MARKER_RE because the
    dedupe gate EXTRACTS markers by regex rather than matching a substring.
    And it must sit inside the body, on line 1, because the body is what the
    POST writes: the marker being inside the posted body is exactly what makes
    it written by, and only by, the call that performs the write, and line 1
    maximizes its survival under truncation or a rendering change. A body that
    lost its marker could never be deduped by a later run, so it is refused
    here rather than posted."""
    marker, body = item["marker"], item["body"]
    if not MARKER_RE.fullmatch(marker):
        template = "%s.marker %r does not match %s"
        return [template % (where, marker, MARKER_RE.pattern)]
    if body.splitlines()[0].strip() == marker:
        return []
    template = (
        "%s.body must carry its marker %s alone on line 1; a comment whose "
        "body lost its marker could never be deduped by a later run")
    return [template % (where, marker)]


def _entry_inertness_errors(body, where):
    """Error strings for a body that still carries active markup. (PURE)

    The body must be inert whether Azure DevOps stores it as markdown or as
    HTML, and the Add call cannot declare the format. The renderer escaped
    '&', '<' and '>' at render time, so a body still carrying '<' or '>' did
    not come through that escaping and is REFUSED -- see ACTIVE_MARKUP_CHARS
    for why it is not re-escaped here instead."""
    found = [char for char in ACTIVE_MARKUP_CHARS if char in body]
    if not found:
        return []
    template = (
        "%s.body is not inert: it still contains %s. Azure DevOps' Add body "
        "cannot declare its format, so a body is posted only when '&', '<' "
        "and '>' were escaped at render time.")
    chars = " and ".join(repr(char) for char in found)
    return [template % (where, chars)]


def _errors_for_comment_entry(item, index):
    """Error strings for ONE comment entry; [] means valid. (PURE)

    Entries come from ado_intake.py render's payload
    ({"kind", "gap_id", "marker", "body"}); this module NEVER builds a marker
    of its own. A missing field short-circuits the rest, because every later
    check indexes one of the keys it guards."""
    where = "comments[%d]" % index
    if not isinstance(item, dict):
        template = "%s must be an object with the keys %s"
        return [template % (where, ", ".join(COMMENT_ENTRY_KEYS))]
    missing = _entry_field_errors(item, where)
    if missing:
        return missing
    errors = _entry_kind_errors(item, where)
    errors += _entry_marker_errors(item, where)
    errors += _entry_inertness_errors(item["body"], where)
    return errors


def _duplicate_marker_errors(entries):
    """Error strings for a marker used by two entries in ONE batch. (PURE)

    plan_comments dedupes each entry against the WORK ITEM's comment list; it
    cannot see an entry's siblings, so two identical entries in one batch
    would both plan as not-already-posted and both POST, and _comment_results'
    by-marker map would then collapse the two writes onto one comment id.
    Measured on the Jira twin of this lane in run 20260908-jira-intake.
    Refusing the batch here means the duplicate is caught before the first
    request, so nothing partial is left on the work item."""
    first_seen = {}
    errors = []
    for index, item in enumerate(entries):
        marker = item["marker"]
        if marker not in first_seen:
            first_seen[marker] = index
            continue
        errors.append(
            "comments[%d].marker duplicates comments[%d].marker (%s)"
            % (index, first_seen[marker], marker))
    return errors


def validate_comment_entries(entries):
    """Error strings for the batch to post; [] means valid. (PURE)

    Runs BEFORE any credential is read and BEFORE the first request, so a
    refusal leaves nothing partial on the work item. Shape errors
    short-circuit the duplicate scan, which indexes entry['marker']."""
    if not isinstance(entries, list) or not entries:
        return ["comments must be a non-empty list of comment entries"]
    errors = []
    for index, item in enumerate(entries):
        errors += _errors_for_comment_entry(item, index)
    if errors:
        return errors
    return _duplicate_marker_errors(entries)


def marker_tokens(text):
    """Every dedupe token visible in one blob of text, as a SET. (PURE)

    Two tiers: the full marker, and the bare 12-hex digest as a standalone
    token. EXTRACTION, NOT SUBSTRING MATCHING: pulling tokens out and
    comparing sets survives HTML wrapping ('<div>[marker]</div>'), whitespace
    and newline normalization, and entity-escaping of NEIGHBOURING characters
    -- the plausible mutations across the write/read api-version asymmetry
    (POST 7.0-preview.3, read back 7.1-preview.4). The second tier strictly
    increases suppression, which is the FAIL-SAFE direction: a false
    suppression skips a write, a false miss duplicates a comment on a live
    work item that this connector has no lane to delete."""
    return set(MARKER_RE.findall(text)) | set(MARKER_DIGEST_RE.findall(text))


def comment_haystack_tokens(comments):
    """The dedupe token set for a work item's FULL comment history. (PURE)

    THE HAYSTACK IS THE STORED `text`, UNIONED WITH ITS html_to_text
    RENDERING -- and never the optional HTML *rendering* Azure DevOps can
    return alongside it, which a renderer may entity-encode or strip (see
    _comment_text, which is where that field is refused as a data source).
    Both sides of this union fail safe, and they differ exactly where it
    matters: a marker forged inside an HTML comment is INVISIBLE to the
    walker (which drops comments) and VISIBLE in the raw text, while a marker
    split across markup is visible to the walker.

    A comment with no usable `text` RAISES rather than contribute nothing:
    silently shrinking the haystack is the failure mode that double-posts on
    every run. (_comment_text already enforces this on the read path; this
    call re-asserts it because the entries arrive here as plain dicts.)"""
    tokens = set()
    for raw in comments:
        if not isinstance(raw, dict):
            raise AdoError(_MISSING_TEXT_MSG)
        text = _comment_text(raw)
        tokens |= marker_tokens(text)
        tokens |= marker_tokens(html_to_text(text))
    return tokens


def plan_comments(entries, tokens):
    """Decide, per entry, whether it is already on the work item. (PURE)

    `tokens` comes from comment_haystack_tokens over the work item's FULL
    paginated comment list, read back over the network -- THE WORK ITEM'S OWN
    COMMENT LIST IS THE DEDUPE GATE, never a local file, so a fresh clone
    cannot double-post. An entry whose marker (or whose bare digest) is
    already in the set is reported as already-posted rather than posted again
    or silently dropped. IN-BATCH duplicates are not this function's job:
    validate_comment_entries refuses them before the lane gets here, because
    this gate compares each entry to the work item and never to its
    siblings."""
    planned = []
    for item in entries:
        marker = item["marker"]
        digest = marker[-13:-1]
        planned.append({
            "kind": item["kind"], "marker": marker,
            "already_posted": marker in tokens or digest in tokens})
    return planned


# THE WRONG-TARGET REFUSAL. An Azure DevOps work item is a bare integer plus an
# org and a project that come from OUTSIDE the id, so item 1234 exists in every
# org and project -- a hazard Jira's self-describing ABC-123 key cannot even
# express. The record names one triple, the rendered comments payload names the
# triple it was rendered FOR, and agreed_target refuses unless the two are
# EQUAL -- it is pure, so the comment lane can run it before it reads a
# credential or issues a request.
TRIPLE_FIELDS = ("org", "project", "id")
PAYLOAD_TRIPLE_FIELDS = ("work_item_org", "work_item_project", "work_item_id")

_RECORD_TRIPLE_MSG = (
    "the record does not name its own target: the field(s) %s are missing or "
    "empty. A record that cannot name its (org, project, id) cannot be "
    "checked against the work item a write would land on.")
_PAYLOAD_TRIPLE_MSG = (
    "the comments file does not name the work item it was rendered for: the "
    "field(s) %s are missing or empty. Pass the whole payload object printed "
    "by ado_intake.py render (which carries %s), not a bare comments array.")
_WRONG_TARGET_MSG = (
    "REFUSING THE WRITE: the comment plan does not belong to %s (%s). An "
    "Azure DevOps work-item id is a bare integer, so id %s exists in every "
    "org and project: posting here would put one item's refinement on "
    "another, and the read-back dedupe gate would report a clean success. "
    "Re-resolve the work item and re-render the comments.")


def _triple_from(source, keys, missing_error):
    """Read an (org, project, id) triple out of `source` under `keys`,
    fail-closed. Every field must be a non-empty string, and the id must
    survive validate_work_item_id -- it reaches a URL segment. (PURE apart
    from raising)"""
    if not isinstance(source, dict):
        raise missing_error(", ".join(keys))
    missing = [
        key for key in keys
        if not isinstance(source.get(key), str) or not source[key].strip()
    ]
    if missing:
        raise missing_error(", ".join(missing))
    org, project, work_item_id = (source[key].strip() for key in keys)
    return (org, project, validate_work_item_id(work_item_id))


def _record_triple_error(names):
    """A record that cannot name its own target is a CONTRACT failure (exit
    1): all three fields are in REQUIRED_FIELDS, so a missing one means the
    record did not come from resolve_work_item."""
    return AdoError(_RECORD_TRIPLE_MSG % names)


def _payload_triple_error(names):
    """A comments payload that cannot name its target is USAGE (exit 2): the
    operator passed the wrong file, or a bare comments array."""
    return AdoUsageError(
        _PAYLOAD_TRIPLE_MSG % (names, ", ".join(PAYLOAD_TRIPLE_FIELDS)))


def record_triple(record):
    """The (org, project, id) triple of a resolve record. (PURE apart from
    raising) All three are in the record's REQUIRED_FIELDS, so an empty one is
    a half-resolve; reaching this function with one missing means the record
    did not come from resolve_work_item and is a contract failure."""
    return _triple_from(record, TRIPLE_FIELDS, _record_triple_error)


def payload_triple(payload):
    """The (org, project, id) triple the comments payload was RENDERED FOR.
    (PURE apart from raising)

    THE BINDING BETWEEN A PREVIEW AND THE ITEM IT WAS RENDERED FOR. A bare
    comments array carries no triple and is refused here: the target must come
    from the rendered payload and the resolved record, never from ambient
    environment addressing."""
    return _triple_from(payload, PAYLOAD_TRIPLE_FIELDS, _payload_triple_error)


def assert_same_target(expected, actual, what):
    """Refuse unless two (org, project, id) triples are EQUAL, naming both
    sides and preferring neither.

    THE COMPARISON IS DELIBERATELY EXACT. Azure DevOps org and project names
    are case-preserving, this path fails closed, and a case-insensitive or
    punctuation-folding compare would quietly widen what it accepts -- on the
    one lane in this plugin whose mistakes cannot be undone. Do not 'fix' it
    into one."""
    diffs = [
        "%s %r != %r" % (name, want, got)
        for name, want, got in zip(TRIPLE_FIELDS, expected, actual)
        if want != got
    ]
    if diffs:
        raise AdoError(_WRONG_TARGET_MSG % (what, "; ".join(diffs), actual[2]))
    return None


def agreed_target(record, payload):
    """The one (org, project, id) triple the record and the comments payload
    BOTH name, or a refusal. (PURE apart from raising)

    Runs BEFORE any credential is read and before the first request, so a
    mismatched pair costs nothing and leaks nothing."""
    target = record_triple(record)
    assert_same_target(target, payload_triple(payload), "the resolved record")
    return target


# THE COMMENT LANE. Posting is OFF BY DEFAULT: without `arm` the lane issues
# GETs only and reports what it WOULD post. The order below IS the safety
# design -- pure entry validation first, then ONE fresh re-resolve that proves
# the target and supplies the dedupe haystack at once, then the refusal, and
# only then the single bounded write.
_INVALID_PLAN_MSG = "refusing to post from an invalid comment plan: %s"
_PARTIAL_BATCH_MSG = (
    "%s; %d comment(s) already posted to work item %s before the failure: "
    "%s. Those comments are on the work item now and this connector has no "
    "lane to delete them. A later run suppresses exactly those markers, and "
    "only while the refinement still renders byte-identically.")
_INDETERMINATE_MSG = (
    "%s; comment %s was in flight when the transport failed and MAY be on "
    "work item %s -- Azure DevOps was not able to confirm it%s. There is no "
    "comment-delete lane to retract it.")
_INDETERMINATE_LANDED_CLAUSE = (
    "; %d earlier comment(s) are confirmed on the work item: %s")


def _landed_clause(posted):
    """The '; N earlier comment(s) are confirmed...' clause, or '' when
    nothing landed before the in-flight comment. (PURE)"""
    if not posted:
        return ""
    markers = ", ".join(item["marker"] for item in posted)
    return _INDETERMINATE_LANDED_CLAUSE % (len(posted), markers)


def _partial_batch_error(work_item_id, posted, exc, in_flight=None):
    """The AdoError raised when a batch POST fails part-way through.

    The BATCH is not atomic -- only each individual comment is (see
    execute_comment_plan) -- so a failure after N comments have already
    landed must SAY SO: the work item has been mutated even though the whole
    operation is being reported as failed, and there is no comment-delete
    lane to retract it. Every already-posted marker is named, so the operator
    can tell exactly what happened from the refusal alone.

    `in_flight`, when given, is the entry that was being POSTed when a
    _IndeterminateWriteError was raised (a transport failure, not a clean
    HTTP status): Azure DevOps could not confirm whether that particular
    comment landed, so it is named EXPLICITLY as indeterminate rather than
    silently excluded from the disclosure the way a clean HTTPError status
    (nothing sent, nothing landed) is. Without this, an operator reading a
    plain 'network error' message could reasonably conclude nothing was
    written and post the comment by hand, producing the exact duplicate this
    slice exists to prevent.

    DELIBERATELY NOT A RECOVERY INSTRUCTION. A later run suppresses a landed
    comment only while the refinement still renders byte-identically:
    measured on the Jira twin of this lane, dropping a single period from the
    refinement changed the marker, so a second pass over an edited refinement
    would post NEW comments beside the landed ones. The disclosure states
    what happened and names the markers; what to do next is the operator's
    call, with the work item in front of them.

    The message carries the underlying AdoError, which names only a URL, plus
    markers this module never invents -- so no credential can ride out in
    it."""
    if in_flight is not None:
        landed_clause = _landed_clause(posted)
        return AdoError(
            _INDETERMINATE_MSG
            % (exc, in_flight["marker"], work_item_id, landed_clause))
    if not posted:
        return AdoError(str(exc))
    markers = ", ".join(item["marker"] for item in posted)
    return AdoError(
        _PARTIAL_BATCH_MSG % (exc, len(posted), work_item_id, markers))


def _posted_result(item, comment_id):
    """One result row for a comment that LANDED. (PURE)"""
    return {
        "kind": item["kind"], "marker": item["marker"],
        "status": "posted", "comment_id": comment_id}


def execute_comment_plan(route, pat, pending):
    """POST each pending comment in order and return one result each.

    Fail closed and ATOMIC PER COMMENT: every entry was shape-validated
    before any request was issued, and the FIRST failure propagates
    immediately, so no later comment is posted. One comment is written whole
    by one POST or not at all -- there is no partial body.

    The BATCH is not atomic, and that partial mutation is DISCLOSED rather
    than swallowed (see _partial_batch_error): this is the only irreversible
    external call in this module."""
    posted = []
    for item in pending:
        try:
            comment_id = post_comment(route, pat, item["body"])
        except AdoError as exc:
            raise _write_failure(route[2], posted, item, exc) from exc
        posted.append(_posted_result(item, comment_id))
    return posted


def _write_failure(work_item_id, posted, item, exc):
    """The AdoError to raise for one failed POST in a batch: names `item` as
    in-flight only when the failure was transport-indeterminate. (PURE)"""
    in_flight = item if isinstance(exc, _IndeterminateWriteError) else None
    return _partial_batch_error(work_item_id, posted, exc, in_flight)


def _preview_result(item, planned):
    """One result row for a comment that was NOT posted on this invocation:
    either already on the work item, or awaiting an armed run. (PURE)"""
    status = "already-posted" if planned["already_posted"] else "would-post"
    return {
        "kind": item["kind"], "marker": planned["marker"],
        "status": status, "comment_id": None}


def _comment_results(entries, plan, posted):
    """Merge the dedupe plan and the POST results into one ordered result per
    REQUESTED comment, in the requested order. (PURE)

    Keyed by marker, which is safe ONLY because validate_comment_entries
    already refused an in-batch duplicate: two entries sharing a marker would
    collapse onto one row here and both report the same comment id -- the
    exact collapse measured on the Jira twin of this lane."""
    by_marker = {item["marker"]: item for item in posted}
    return [
        by_marker.get(planned["marker"]) or _preview_result(item, planned)
        for item, planned in zip(entries, plan)
    ]


def _assert_target_unchanged(target, fresh, org):
    """Refuse unless `target` still names BOTH the work item the fresh read
    just returned AND the organization the current ADO_ORG_URL points at.

    Two checks because there are two ways to drift. The record check catches
    a comments payload rendered for a different item; the environment check
    catches the org moving between the preview invocation and the armed one
    -- a different shell tab, a re-sourced .env, a mistyped re-export. Both
    land one item's refinement on another, and the read-back dedupe gate
    SUCCEEDS on the wrong item (it carries no such marker), so the operator
    would otherwise see a clean success."""
    assert_same_target(
        target, record_triple(fresh), "the freshly resolved work item")
    assert_same_target(
        target, (org, target[1], target[2]),
        "the organization named by the current ADO_ORG_URL")
    return None


def run_comment_lane(target, entries, arm):
    """Preview -- or, when armed, post -- the intake comments for ONE work
    item, target-checked and dedupe-gated. `target` is the agreed
    (org, project, id) triple; `arm` alone decides whether a write happens.

    POSTING IS OFF BY DEFAULT: with `arm` false this issues GETs only and
    reports what it WOULD post, so the default path performs zero writes.

    THE ORDER IS THE SAFETY DESIGN:
      1. Every entry is shape-validated -- marker shape, marker alone on line
         1 of the body, an inert body, and no in-batch duplicate -- BEFORE
         any credential is read and BEFORE the first request, so a refusal
         leaves nothing partial on the work item.
      2. The work item is RE-RESOLVED fresh. That one read serves both
         purposes at once: it proves the target and it supplies the comment
         history, so the lane issues no extra request. The preview and the
         armed post are separate invocations, so the target is re-proved here
         rather than trusted from the payload.
      3. The write REFUSES unless `target` equals the freshly resolved
         (org, project, id) triple AND the org derived from the current
         ADO_ORG_URL.
      4. Only then, and only when armed, is a POST issued -- one per pending
         comment, on a route composed from the validated api_root.

    THE WORK ITEM IS READ ONCE PER INVOCATION, not before every individual
    write: within one armed batch every comment is posted from the single
    snapshot taken in step 2. A comment added by someone else mid-batch is
    invisible to this run."""
    errors = validate_comment_entries(entries)
    if errors:
        raise AdoError(_INVALID_PLAN_MSG % "; ".join(errors))
    api_root, org, pat = credentials()
    fresh = resolve_work_item(target[2])
    _assert_target_unchanged(target, fresh, org)
    plan = plan_comments(entries, comment_haystack_tokens(fresh["comments"]))
    done = [bool(item["already_posted"]) for item in plan]
    pending = [item for item, seen in zip(entries, done) if not seen]
    posted = []
    if arm:
        posted = execute_comment_plan(
            (api_root, target[1], target[2]), pat, pending)
    return {
        "ok": True, "org": target[0], "project": target[1],
        "work_item_id": target[2], "title": fresh["title"],
        "web_url": fresh["web_url"], "armed": bool(arm),
        "posted_count": len(posted), "already_posted_count": done.count(True),
        "results": _comment_results(entries, plan, posted)}


# A rendered heading is either html_to_text's HEADING_PREFIX (from an <h1>-<h6>
# tag) or a bare 'Acceptance Criteria:' line, which is how the section is
# commonly styled with <b>. KNOWN LOSSINESS, stated rather than claimed away: a
# <b>-styled pseudo-heading does NOT terminate the section, because the walker
# renders it as ordinary prose, so a following bold-styled section is included.
# A real heading tag does terminate it.
AC_HEADING_RE = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*)?acceptance\s+criteria\s*:?\s*$", re.IGNORECASE)
ANY_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")


def acceptance_criteria_from_description(text):
    """Extract the 'Acceptance Criteria' section of an already-rendered
    description: every line after the heading, up to the next heading or the
    end. Returns '' when no such heading is present. (PURE)"""
    collected = []
    inside = False
    for line in (text or "").splitlines():
        if not inside:
            inside = bool(AC_HEADING_RE.match(line))
            continue
        if ANY_HEADING_RE.match(line):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def resolve_acceptance_criteria(fields, description_text):
    """Resolve the acceptance criteria in the fixed order and report which
    source won: the Microsoft.VSTS.Common.AcceptanceCriteria field when it is
    present and renders non-empty ('field'), else the rendered description's
    'Acceptance Criteria' section ('description'), else ('', '').

    THE FIELD'S ABSENCE IS NOT A FAILURE. It exists on Bug, Epic, Feature and
    Product Backlog Item only -- an Agile User Story and a Task have no such
    field -- so the missing case is the common one. There is no field-catalogue
    GET to make: the field is either in the flat `fields` map or it is not, so
    path (1) is a dict lookup rather than an HTTP call. Recording the winning
    source is what makes the fallback safe: a reader can always tell where the
    text came from. A field of some other shape (a number, an array) is not
    criteria text, so it degrades to the description fallback rather than
    crashing the resolve. (PURE)"""
    raw = fields.get(FIELD_ACCEPTANCE_CRITERIA)
    rendered = html_to_text(raw).strip() if isinstance(raw, str) else ""
    if rendered:
        return (rendered, "field")
    from_description = acceptance_criteria_from_description(description_text)
    if from_description:
        return (from_description, "description")
    return ("", "")


RECORD_FIELDS = (
    "org", "project", "id", "web_url", "title", "work_item_type", "state",
    "description", "acceptance_criteria", "acceptance_criteria_source",
    "repro_steps", "comments")
# org, project and id are ALL required: an Azure DevOps work item is a bare
# integer plus an org and a project, so the triple is what identifies it. A
# record that cannot name its own org or project cannot be checked against a
# post-time target, which is the whole defence against a wrong-target write.
REQUIRED_FIELDS = (
    "org", "project", "id", "web_url", "title", "work_item_type", "state")


def _normalized(values):
    """Build the inter-slice record in RECORD_FIELDS order -- the single source
    of truth for the JSON contract shape, so it cannot drift between callers.
    An empty REQUIRED_FIELDS entry means the API response was incomplete: that
    is a half-resolve and raises, because a partial record must never be
    emitted as if it were a whole one. description, acceptance_criteria,
    acceptance_criteria_source, repro_steps and an empty comments list are all
    legitimately empty."""
    record = {name: values[name] for name in RECORD_FIELDS}
    empty = [name for name in REQUIRED_FIELDS if not record[name]]
    if empty:
        raise AdoError(
            "Azure DevOps returned an incomplete work item: the required "
            "field(s) " + ", ".join(empty)
            + " came back empty; refusing to emit a partial record")
    return record


def _text_field(fields, key):
    """Read a plain-string field (System.Title, System.WorkItemType or
    System.State) the same way resolve_project reads System.TeamProject: a
    non-string value (a malformed or malicious tenant response returning a
    dict, list or number where the API contract promises a string) degrades
    to '' rather than crashing .strip() with an unhandled AttributeError. The
    empty result still flows through _normalized's REQUIRED_FIELDS check, so
    a genuinely missing/wrong-shaped field still fails closed as an AdoError,
    never a raw traceback. (PURE)"""
    raw = fields.get(key)
    return raw.strip() if isinstance(raw, str) else ""


def resolve_work_item(work_item_id):
    """Resolve one Azure DevOps work-item id READ-ONLY to the normalized
    record. Credentials come from the environment (see credentials()); every
    call is fail-closed.

    The read is issued with org + id alone on the project-OPTIONAL route, the
    project is then taken from the response's own System.TeamProject, and the
    comment sweep -- where the project is REQUIRED -- uses that derived value.
    ADO_PROJECT, if set, is only an assertion. The body-supplied web URL is
    validated against the requested org before it is stored, since it is later
    displayed where an operator authorizes a write."""
    api_root, org, pat = credentials()
    resolved_id = validate_work_item_id(work_item_id)
    item = fetch_work_item(api_root, pat, resolved_id)
    fields = item.get("fields") or {}
    project = resolve_project(fields)
    assert_project_matches_env(project)
    description = html_to_text(fields.get(FIELD_DESCRIPTION))
    criteria, source = resolve_acceptance_criteria(fields, description)
    href = ((item.get("_links") or {}).get("html") or {}).get("href")
    # ORDER IS LOAD-BEARING: validate the scalar record FIRST, with an empty
    # comment list, so a half-resolve (an empty required field, or a spoofed
    # _links.html.href) refuses BEFORE the comment sweep spends up to
    # MAX_COMMENT_PAGES network round trips it is going to throw away.
    record = _normalized({
        "org": org,
        "project": project,
        "id": resolved_id,
        "web_url": validate_web_url(href, api_root),
        "title": _text_field(fields, FIELD_TITLE),
        "work_item_type": _text_field(fields, FIELD_TYPE),
        "state": _text_field(fields, FIELD_STATE),
        "description": description,
        "acceptance_criteria": criteria,
        "acceptance_criteria_source": source,
        "repro_steps": html_to_text(fields.get(FIELD_REPRO_STEPS)),
        "comments": [],
    })
    record["comments"] = fetch_comments(api_root, pat, project, resolved_id)
    return record


def _load_json_file(path, what):
    """Read one JSON file, mapping any read or parse failure to a usage error
    the caller can fix. No credential is read and no request is issued before
    this succeeds."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise AdoUsageError(
            f"cannot read the {what} file {path}: {exc}") from exc
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise AdoUsageError(
            f"the {what} file {path} is not valid JSON: {exc}") from exc


def _comment_payload(args):
    """Load the resolved record and the rendered comments, agree on ONE target
    triple, and run the comment lane.

    THE TARGET COMES FROM THE RESOLVED RECORD AND THE RENDERED PAYLOAD, never
    from ambient environment addressing and never from a flag: there is no
    --id, no --project and no --org on this subcommand. The two files must
    name the same (org, project, id) or the lane refuses -- before a
    credential is read and before the first request."""
    record = _load_json_file(args.record, "record")
    payload = _load_json_file(args.comments, "comments")
    target = agreed_target(record, payload)
    entries = payload.get("comments") if isinstance(payload, dict) else None
    return run_comment_lane(target, entries, args.post)


def build_parser():
    """Build the CLI parser. The read lane exposes `resolve --id`, which
    issues no write, and the write lane exposes `comment`, which previews by
    default and issues its one bounded POST only under --post.

    There is deliberately NO credential flag and NO --project flag on any
    subcommand: credentials are read from the environment only, so they
    cannot appear on a command line that `ps` can see, and the project is
    read from the work item's own System.TeamProject, so a flag could only
    disagree with it. `comment` also has no --id: its target comes from the
    resolved record and the rendered comments payload agreeing, never from a
    flag."""
    parser = argparse.ArgumentParser(
        description=(
            "Azure DevOps Services work-item reader, plus ONE bounded "
            "writer: `resolve` is read-only, and `comment` previews the "
            "intake comments by default and adds them only when armed "
            "with --post."))
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser(
        "resolve",
        help="Resolve one work-item id to a normalized JSON record.")
    resolve.add_argument(
        "--id", required=True, dest="work_item_id",
        help="Azure DevOps work-item id, e.g. 1234.")
    comment = sub.add_parser(
        "comment",
        help=("Preview the spec-loop intake comments for one work item -- "
              "or, with --post, actually add them."))
    comment.add_argument(
        "--record", required=True,
        help=("path to this module's `resolve` output (JSON). The write "
              "target comes from this record, never from the environment "
              "alone."))
    comment.add_argument(
        "--comments", required=True,
        help=("path to the whole payload object printed by ado_intake.py "
              "render, which carries both the comment bodies and the "
              "(org, project, id) triple they were rendered for"))
    comment.add_argument(
        "--post", action="store_true",
        help=("ARM THE WRITE. Without this flag nothing is posted: the lane "
              "issues GETs only and reports what it would post."))
    return parser


def _dispatch(args):
    """Run the requested subcommand and return the object to print. The
    comment lane is reached only through its own subcommand, and it previews
    unless args.post armed it."""
    if args.command == "comment":
        return _comment_payload(args)
    return resolve_work_item(args.work_item_id)


def main(argv=None):
    """Parse args, dispatch, print one JSON object. Exit 0 ok, 1 contract
    failure, 2 usage / unreadable input. AdoUsageError is caught BEFORE
    AdoError: it subclasses AdoError, so the reverse order would collapse
    exit 2 into exit 1.

    The two refusal shapes match this repo's established idiom, so downstream
    tooling can tell them apart by stream: a contract failure (exit 1) prints
    the {"ok": false, "errors": [...]} JSON to STDOUT; a usage failure
    (exit 2) prints plain 'error: %s' text to STDERR. Neither ever carries a
    credential -- every message in this module names only a URL."""
    args = build_parser().parse_args(argv)
    try:
        payload = _dispatch(args)
    except AdoUsageError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except AdoError as exc:
        refusal = {"ok": False, "errors": [str(exc)]}
        print(json.dumps(refusal, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
