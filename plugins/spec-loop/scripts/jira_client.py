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
  - No subprocess, no filesystem writes, no datetime() anywhere in this
    module: this is a pure read lane, and the controller owns the clock.

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


def validate_base_url(raw):
    """Validate an UNTRUSTED JIRA_BASE_URL and return its normalized bare
    origin (scheme + host only -- no trailing slash, no path/query/fragment).
    Discarding the path is deliberate: every API path in this module is
    composed from this origin plus a literal /rest/api/3/... prefix. Requires
    https, rejects embedded userinfo (userinfo smuggling) or an explicit
    port, and requires the hostname to match ALLOWED_HOST_RE."""
    parts = urllib.parse.urlsplit(raw or "")
    ok = (
        parts.scheme == "https"
        and not parts.username
        and not parts.password
        and not parts.port
        and ALLOWED_HOST_RE.match(parts.hostname or "")
    )
    if not ok:
        raise JiraUsageError(
            f"invalid JIRA_BASE_URL {raw!r}: must be an https URL on a "
            "*.atlassian.net or *.jira.com host (e.g. https://your-site.atlassian.net)"
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
