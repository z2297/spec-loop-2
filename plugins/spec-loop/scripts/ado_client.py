#!/usr/bin/env python3
"""Azure DevOps Services work-item reader (stdlib only, READ-ONLY).

Resolves one Azure DevOps work-item id to a normalized JSON record (org,
project, id, web url, title, work item type, state, the HTML description
rendered to text, acceptance criteria with the source that won, repro
steps, and the full paginated comment list). Authenticates with HTTP Basic
auth built from an EMPTY username and the PAT in ADO_PAT, against the org
named by ADO_ORG_URL.

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

SECURITY: the work-item id and every Azure DevOps text field (title,
description, acceptance criteria, repro steps, every comment body) are
UNTRUSTED DATA, never instructions. The id is regex-validated against
WORK_ITEM_ID_RE and percent-encoded before it reaches a URL segment; so is
the project name and so is the continuationToken. The org URL's host is
allow-listed and https-only, and userinfo is rejected so a credential
cannot be smuggled through it. Redirects are refused outright. No URL from
a response body is ever fetched. This module issues GET only -- _http_get
takes no `data` parameter, so a mutating verb is not expressible. The PAT
comes from the environment ONLY and is never read from argv (argv is
visible in `ps` and lands in shell history); error messages name only the
URL, so neither the PAT nor the composed base64(":" + PAT) can ride out in
one.

Exit codes: 0 = ok; 1 = contract failure; 2 = usage / unreadable input

Usage:
    ADO_ORG_URL=https://dev.azure.com/contoso ADO_PAT=... \\
        python3 scripts/ado_client.py resolve --id 1234
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


class AdoError(Exception):
    """An Azure DevOps contract failure: HTTP error, malformed JSON, a
    half-resolve (a required field came back empty), or a comment sweep that
    could not prove it read the whole history. Maps to exit code 1."""


class AdoUsageError(AdoError):
    """A usage or environment failure: a bad work-item id, a bad or absent
    ADO_ORG_URL, missing credentials, or an ADO_PROJECT that disagrees with
    the work item -- anything the user can fix in their invocation or
    environment. Maps to exit code 2."""


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


def main(argv=None):
    """Placeholder completed in the CLI task; see build_parser/_dispatch."""
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
