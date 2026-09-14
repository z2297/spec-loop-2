# Review package: a39272b130ebaec23fac2e0bad82195c4e977963..7dafe52  (context: -U5)

## Commits
7dafe52 test(ado): register ado_client.py in the coverage gate with a measured floor
7ea1a64 feat(ado): add the preview-by-default comment subcommand
2c87a60 style(ado): keep the comment lane and its tests flat for the nesting heuristic
d0fb723 feat(ado): add the off-by-default, target-checked comment lane
b27a92a style(ado): keep the target-triple lane flat for the nesting heuristic
06ff52b feat(ado): bind the comment plan to the resolved record's target triple
1b2749a feat(ado): dedupe by extracting markers from stored text and its rendering
b07ad1c refactor(ado): split entry validation into gate-clean helpers
5f121d1 feat(ado): refuse an in-batch duplicate or a non-inert body before any request
54c2167 feat(ado): add the sole comment writer beside the read-only GET helper

## Files changed
 plugins/spec-loop/scripts/ado_client.py      | 703 ++++++++++++++++++++++-
 plugins/spec-loop/scripts/test_ado_client.py | 796 +++++++++++++++++++++++++++
 scripts/coverage_omit.txt                    |   1 +
 scripts/measure_coverage.py                  |   2 +
 4 files changed, 1496 insertions(+), 6 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/ado_client.py": [
[
2,
2
],
[
9,
10
],
[
102,
147
],
[
168,
173
],
[
189,
189
],
[
869,
1448
],
[
1586,
1617
],
[
1619,
1621
],
[
1627,
1629
],
[
1639,
1656
],
[
1661,
1665
]
],
"plugins/spec-loop/scripts/test_ado_client.py": [
[
968,
1763
]
],
"scripts/coverage_omit.txt": [
[
34,
34
]
],
"scripts/measure_coverage.py": [
[
102,
102
],
[
146,
146
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/ado_client.py b/plugins/spec-loop/scripts/ado_client.py
index b1ce2a6..c41473b 100644
--- a/plugins/spec-loop/scripts/ado_client.py
+++ b/plugins/spec-loop/scripts/ado_client.py
@@ -1,14 +1,15 @@
 #!/usr/bin/env python3
-"""Azure DevOps Services work-item reader (stdlib only, READ-ONLY).
+"""Azure DevOps Services work-item reader with ONE bounded comment writer (stdlib only).
 
 Resolves one Azure DevOps work-item id to a normalized JSON record (org,
 project, id, web url, title, work item type, state, the HTML description
 rendered to text, acceptance criteria with the source that won, repro
 steps, and the full paginated comment list). Authenticates with HTTP Basic
 auth built from an EMPTY username and the PAT in ADO_PAT, against the org
-named by ADO_ORG_URL.
+named by ADO_ORG_URL. Also previews -- and, only under an explicit --post,
+adds -- the spec-loop intake comments on one work item.
 
 Design decisions:
   - Mirrors plugins/spec-loop/scripts/jira_client.py's transport doctrine by
     COPY AND ADAPT, never by import: there is deliberately no shared helper
     module with jira_client.py or pr_resolver.py -- duplication over
@@ -96,10 +97,56 @@ Design decisions:
     LOSSY BY DESIGN: it produces review-readable text, not a document that
     round-trips back into HTML.
   - No subprocess, no filesystem writes, and no clock read anywhere in this
     module: the controller owns the clock. Azure DevOps' own createdDate /
     modifiedDate strings are echoed verbatim.
+  - THE WRITE IS OFF BY DEFAULT AND BOUNDED TO ONE VERB. `comment` previews
+    by default, issuing GETs only; `--post` is the only thing that arms the
+    HTTP verb. _http_post is the module's SOLE writer and adds one work-item comment
+    and nothing else: no state transition, no field edit or PATCH, no
+    assignee change, no work-item or child creation, no relation/link edit,
+    no attachment, no comment edit, no comment delete, no reaction. It is a
+    SEPARATE function from _http_get, which still takes no `data` parameter
+    and no `method` parameter -- that absence is the read lane's proof, so
+    the writer is added beside it rather than by widening it.
+  - THE WRONG-TARGET WRITE IS THE WRITE LANE'S DEFINING HAZARD. An Azure
+    DevOps work item is a bare integer plus an org and a project that come
+    from outside the id, so item 1234 exists in every org: if the org
+    changed between the preview and the armed post, the lane would put one
+    item's refinement on another AND the read-back dedupe gate would report a
+    clean success, with no comment-delete lane to retract it. So the comments
+    payload carries the (org, project, id) triple it was rendered for, the
+    record carries its own, both must agree BEFORE any credential is read,
+    and the armed lane then re-resolves the work item and refuses unless the
+    triple matches the fresh one and the org matches the current ADO_ORG_URL.
+    The target is never taken from a flag.
+  - IN-BATCH DUPLICATES ARE REFUSED AT VALIDATION, before the first request.
+    The read-back gate compares each entry to the work item and never to its
+    siblings, so two identical entries in one batch would both plan as
+    not-already-posted, both post, and collapse onto one reported comment id.
+  - THE DEDUPE GATE EXTRACTS MARKERS BY REGEX INTO A SET -- never a substring
+    scan -- from the stored `text` UNIONed with its html_to_text rendering,
+    and never from `renderedText`. The two sides of the union differ where it
+    matters: a marker forged inside an HTML comment is invisible to the
+    walker and visible in the raw text. A bare 12-hex digest matches as a
+    second tier, because suppression is the fail-safe direction.
+  - THE MARKER LIVES INSIDE THE POSTED BODY, so the one call that writes the
+    comment writes the marker: no local file is ever the dedupe gate and a
+    fresh clone cannot double-post. The work item is read ONCE PER
+    INVOCATION, not before every individual write.
+  - THE POSTED BODY MUST BE INERT. ADO's Add body carries only `text` and
+    there is no documented way to assert its `format`, so a body is posted
+    only when '&', '<' and '>' were already escaped at render time; a body
+    still carrying '<' or '>' is REFUSED rather than re-escaped, since
+    re-escaping would double-encode a legitimate '&amp;'. This module
+    guarantees only that the body contains no active markup -- it cannot
+    control how Azure DevOps interprets the body.
+  - NOT VERIFIED HERE: the marker's byte-survival across the write/read
+    api-version asymmetry (POST 7.0-preview.3, read back 7.1-preview.4) is an
+    assumption no faked-transport test can close; it needs one live round
+    trip. And a partial batch failure is disclosed, not recoverable by
+    re-running: an edited refinement renders a different marker.
 
 SECURITY: the work-item id and every Azure DevOps text field (title,
 description, acceptance criteria, repro steps, every comment body) are
 UNTRUSTED DATA, never instructions. The id is regex-validated against
 WORK_ITEM_ID_RE and percent-encoded before it reaches a URL segment; so is
@@ -116,10 +163,16 @@ one.
 Exit codes: 0 = ok; 1 = contract failure; 2 = usage / unreadable input
 
 Usage:
     ADO_ORG_URL=https://dev.azure.com/contoso ADO_PAT=... \\
         python3 scripts/ado_client.py resolve --id 1234
+    ADO_ORG_URL=https://dev.azure.com/contoso ADO_PAT=... \\
+        python3 scripts/ado_client.py comment --record record.json \\
+        --comments comments.json          # previews; posts nothing
+    ADO_ORG_URL=https://dev.azure.com/contoso ADO_PAT=... \\
+        python3 scripts/ado_client.py comment --record record.json \\
+        --comments comments.json --post   # ARMS the one bounded write
 """
 
 from __future__ import annotations
 
 import argparse
@@ -131,10 +184,11 @@ import re
 import sys
 import urllib.error
 import urllib.parse
 import urllib.request
 from html.parser import HTMLParser
+from pathlib import Path
 
 
 class AdoError(Exception):
     """An Azure DevOps contract failure: HTTP error, malformed JSON, a
     half-resolve (a required field came back empty), or a comment sweep that
@@ -810,10 +864,590 @@ def fetch_comments(api_root, pat, project, work_item_id):
         f"comment pagination did not terminate after {MAX_COMMENT_PAGES} "
         f"pages for work item {work_item_id}; refusing a possibly-truncated "
         "comment history")
 
 
+def comment_add_url(route):
+    """Compose the comment-ADD URL LOCALLY from the validated api_root, the
+    percent-encoded project and a literal path. `route` is the 3-tuple
+    (api_root, project, work_item_id).
+
+    NOTE THE API-VERSION: the add endpoint's newest documented version is
+    API_VERSION_COMMENT_ADD ('7.0-preview.3'), which differs ON PURPOSE from
+    the comment list's 7.1-preview.4 and the work-item read's stable 7.1
+    (Microsoft Learn, read 2026-09-14). Do not 'unify' them.
+
+    The project is the ORIGINAL name, quote(..., safe='')-encoded -- never an
+    artifact slug, which would 404 on every project whose name has a space.
+    The id is re-validated here even though the caller validated it: an
+    untrusted value is encoded regardless before it reaches a URL segment."""
+    api_root, project, work_item_id = route
+    encoded_project = urllib.parse.quote(project, safe="")
+    encoded_id = urllib.parse.quote(validate_work_item_id(work_item_id), safe="")
+    return (f"{api_root}/{encoded_project}/_apis/wit/workItems/{encoded_id}"
+            f"/comments?api-version={API_VERSION_COMMENT_ADD}")
+
+
+def _http_post(url, pat, payload):
+    """HTTP POST of one JSON `payload` object through the same no-redirect
+    opener. THE ONLY MUTATING ENTRY POINT IN THIS MODULE.
+
+    Deliberately a SEPARATE function from _http_get rather than a `method=`
+    parameter on it: the read lane's never-a-mutating-verb guarantee is the
+    ABSENCE of `data` and `method` from _http_get's signature, and widening
+    that signature would erase the proof.
+
+    Errors reference only the URL -- the credential rides in a header, so
+    neither the PAT nor the composed base64(':' + PAT) can appear in an
+    exception message. A 3xx is terminal (_NoRedirect), so a write never
+    replays its Authorization header or its body to another origin."""
+    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
+    headers = {
+        "Authorization": _auth_header(pat),
+        "Accept": "application/json",
+        "Content-Type": "application/json",
+    }
+    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
+    try:
+        with _OPENER.open(req, timeout=30) as resp:
+            return resp.read()
+    except urllib.error.HTTPError as exc:
+        raise AdoError(
+            f"HTTP {exc.code} posting to {url}: {exc.reason}") from exc
+    except urllib.error.URLError as exc:
+        raise AdoError(
+            f"network error posting to {url}: {exc.reason}") from exc
+    except OSError as exc:
+        # urllib only wraps an OSError raised by h.request() into a URLError
+        # (CPython's AbstractHTTPHandler.do_open); an OSError out of
+        # h.getresponse() or resp.read() -- a timeout while reading the
+        # response to a POST THAT HAS ALREADY LANDED on the work item --
+        # propagates unwrapped and would otherwise slip past the AdoError
+        # handling above, past execute_comment_plan's `except AdoError`, and
+        # past main()'s exit-1 JSON contract as a raw traceback. Caught here,
+        # terminally, so every write-path transport failure is an AdoError and
+        # can still be turned into a partial-batch disclosure. The message
+        # names only the URL, so no credential can ride out in it.
+        raise AdoError(f"network error posting to {url}: {exc}") from exc
+
+
+def post_comment(route, pat, body):
+    """POST ONE comment to ONE Azure DevOps work item. THE SOLE WRITER.
+
+    Bounded on purpose: this adds a comment and nothing else -- no state
+    transition, no field edit or PATCH, no assignee change, no work-item or
+    child creation, no relation/link edit, no attachment, no comment edit,
+    no comment delete, no reaction.
+
+    THE DEDUPE MARKER LIVES INSIDE `body`, so the one network call that
+    writes the comment is the same call that writes the marker: no local file
+    can make a later run skip a comment that was never actually posted, and a
+    fresh clone cannot double-post.
+
+    Verified against Microsoft Learn's Add Comment operation (read
+    2026-09-14): the request body is {"text": <string>} -- there is no
+    documented way to assert the stored `format` -- and the created comment's
+    id appears as `id` in the definition table and `commentId` in the sample
+    payload, so both spellings are read. A response carrying neither is
+    refused rather than reported as a confirmed write."""
+    url = comment_add_url(route)
+    created = _parse_json(_http_post(url, pat, {"text": body}).decode("utf-8"),
+                          "created comment")
+    if not isinstance(created, dict):
+        created = {}
+    comment_id = _comment_id(created)
+    if not comment_id:
+        raise AdoError(
+            "Azure DevOps accepted the comment POST for work item "
+            f"{route[2]} but returned no comment id; refusing to report a "
+            "write that cannot be confirmed")
+    return comment_id
+
+
+COMMENT_KINDS = ("understanding", "decision", "open-question")
+COMMENT_ENTRY_KEYS = ("kind", "marker", "body")
+
+# THIS MODULE'S OWN COPIES, on purpose: ado_intake.py builds the markers and
+# exports the same two patterns, and there is deliberately no shared runtime
+# module between them (duplication over coupling), so neither module's change
+# can loosen the other's gate. ado_intake's own tests pin the shape both have
+# to agree on.
+MARKER_RE = re.compile(
+    r"\[spec-loop-intake:(?:understanding|decision|open-question):"
+    r"[0-9a-f]{12}\]")
+# The bare digest, for the dedupe gate's second tier: a round trip that
+# rewrote the wrapper but kept the digest must still SUPPRESS a re-post,
+# because a false suppression only skips a write while a false miss
+# duplicates a comment on a live work item with no delete lane to retract it.
+MARKER_DIGEST_RE = re.compile(r"\b[0-9a-f]{12}\b")
+
+# The only two characters that can open active markup. The rendered body was
+# escaped at render time (& -> &amp;, < -> &lt;, > -> &gt;), so a body still
+# carrying one of these did not come through that escaping and is REFUSED
+# rather than posted. It is deliberately not re-escaped here: re-applying the
+# transform would double-encode every legitimate '&amp;' and corrupt the body
+# the operator previewed. '&' alone cannot activate markup, so it is left
+# alone -- the marker contains none of the three characters either way, which
+# test_escaping_leaves_the_marker_byte_identical pins.
+ACTIVE_MARKUP_CHARS = ("<", ">")
+
+
+def _entry_field_errors(item, where):
+    """Error strings for a comment entry missing one of its string fields.
+    Reported before any other check, because every later check indexes one
+    of these keys. (PURE)"""
+    template = "%s.%s is missing or not a string"
+    return [
+        template % (where, key)
+        for key in COMMENT_ENTRY_KEYS
+        if not isinstance(item.get(key), str) or not item.get(key)
+    ]
+
+
+def _entry_kind_errors(item, where):
+    """Error strings for an entry whose kind is not one this lane renders.
+    ado_intake.py builds only the three; anything else did not come from the
+    renderer. (PURE)"""
+    if item["kind"] in COMMENT_KINDS:
+        return []
+    template = "%s.kind %r is not one of %s"
+    kinds = ", ".join(COMMENT_KINDS)
+    return [template % (where, item["kind"], kinds)]
+
+
+def _entry_marker_errors(item, where):
+    """Error strings for a marker that is malformed or is not alone on line 1
+    of the body. (PURE)
+
+    Both halves are load-bearing. The marker must match MARKER_RE because the
+    dedupe gate EXTRACTS markers by regex rather than matching a substring.
+    And it must sit inside the body, on line 1, because the body is what the
+    POST writes: the marker being inside the posted body is exactly what makes
+    it written by, and only by, the call that performs the write, and line 1
+    maximizes its survival under truncation or a rendering change. A body that
+    lost its marker could never be deduped by a later run, so it is refused
+    here rather than posted."""
+    marker, body = item["marker"], item["body"]
+    if not MARKER_RE.fullmatch(marker):
+        template = "%s.marker %r does not match %s"
+        return [template % (where, marker, MARKER_RE.pattern)]
+    if body.splitlines()[0].strip() == marker:
+        return []
+    template = (
+        "%s.body must carry its marker %s alone on line 1; a comment whose "
+        "body lost its marker could never be deduped by a later run")
+    return [template % (where, marker)]
+
+
+def _entry_inertness_errors(body, where):
+    """Error strings for a body that still carries active markup. (PURE)
+
+    The body must be inert whether Azure DevOps stores it as markdown or as
+    HTML, and the Add call cannot declare the format. The renderer escaped
+    '&', '<' and '>' at render time, so a body still carrying '<' or '>' did
+    not come through that escaping and is REFUSED -- see ACTIVE_MARKUP_CHARS
+    for why it is not re-escaped here instead."""
+    found = [char for char in ACTIVE_MARKUP_CHARS if char in body]
+    if not found:
+        return []
+    template = (
+        "%s.body is not inert: it still contains %s. Azure DevOps' Add body "
+        "cannot declare its format, so a body is posted only when '&', '<' "
+        "and '>' were escaped at render time.")
+    chars = " and ".join(repr(char) for char in found)
+    return [template % (where, chars)]
+
+
+def _errors_for_comment_entry(item, index):
+    """Error strings for ONE comment entry; [] means valid. (PURE)
+
+    Entries come from ado_intake.py render's payload
+    ({"kind", "gap_id", "marker", "body"}); this module NEVER builds a marker
+    of its own. A missing field short-circuits the rest, because every later
+    check indexes one of the keys it guards."""
+    where = "comments[%d]" % index
+    if not isinstance(item, dict):
+        template = "%s must be an object with the keys %s"
+        return [template % (where, ", ".join(COMMENT_ENTRY_KEYS))]
+    missing = _entry_field_errors(item, where)
+    if missing:
+        return missing
+    errors = _entry_kind_errors(item, where)
+    errors += _entry_marker_errors(item, where)
+    errors += _entry_inertness_errors(item["body"], where)
+    return errors
+
+
+def _duplicate_marker_errors(entries):
+    """Error strings for a marker used by two entries in ONE batch. (PURE)
+
+    plan_comments dedupes each entry against the WORK ITEM's comment list; it
+    cannot see an entry's siblings, so two identical entries in one batch
+    would both plan as not-already-posted and both POST, and _comment_results'
+    by-marker map would then collapse the two writes onto one comment id.
+    Measured on the Jira twin of this lane in run 20260908-jira-intake.
+    Refusing the batch here means the duplicate is caught before the first
+    request, so nothing partial is left on the work item."""
+    first_seen = {}
+    errors = []
+    for index, item in enumerate(entries):
+        marker = item["marker"]
+        if marker not in first_seen:
+            first_seen[marker] = index
+            continue
+        errors.append(
+            "comments[%d].marker duplicates comments[%d].marker (%s)"
+            % (index, first_seen[marker], marker))
+    return errors
+
+
+def validate_comment_entries(entries):
+    """Error strings for the batch to post; [] means valid. (PURE)
+
+    Runs BEFORE any credential is read and BEFORE the first request, so a
+    refusal leaves nothing partial on the work item. Shape errors
+    short-circuit the duplicate scan, which indexes entry['marker']."""
+    if not isinstance(entries, list) or not entries:
+        return ["comments must be a non-empty list of comment entries"]
+    errors = []
+    for index, item in enumerate(entries):
+        errors += _errors_for_comment_entry(item, index)
+    if errors:
+        return errors
+    return _duplicate_marker_errors(entries)
+
+
+def marker_tokens(text):
+    """Every dedupe token visible in one blob of text, as a SET. (PURE)
+
+    Two tiers: the full marker, and the bare 12-hex digest as a standalone
+    token. EXTRACTION, NOT SUBSTRING MATCHING: pulling tokens out and
+    comparing sets survives HTML wrapping ('<div>[marker]</div>'), whitespace
+    and newline normalization, and entity-escaping of NEIGHBOURING characters
+    -- the plausible mutations across the write/read api-version asymmetry
+    (POST 7.0-preview.3, read back 7.1-preview.4). The second tier strictly
+    increases suppression, which is the FAIL-SAFE direction: a false
+    suppression skips a write, a false miss duplicates a comment on a live
+    work item that this connector has no lane to delete."""
+    return set(MARKER_RE.findall(text)) | set(MARKER_DIGEST_RE.findall(text))
+
+
+def comment_haystack_tokens(comments):
+    """The dedupe token set for a work item's FULL comment history. (PURE)
+
+    THE HAYSTACK IS THE STORED `text`, UNIONED WITH ITS html_to_text
+    RENDERING -- and never the optional HTML *rendering* Azure DevOps can
+    return alongside it, which a renderer may entity-encode or strip (see
+    _comment_text, which is where that field is refused as a data source).
+    Both sides of this union fail safe, and they differ exactly where it
+    matters: a marker forged inside an HTML comment is INVISIBLE to the
+    walker (which drops comments) and VISIBLE in the raw text, while a marker
+    split across markup is visible to the walker.
+
+    A comment with no usable `text` RAISES rather than contribute nothing:
+    silently shrinking the haystack is the failure mode that double-posts on
+    every run. (_comment_text already enforces this on the read path; this
+    call re-asserts it because the entries arrive here as plain dicts.)"""
+    tokens = set()
+    for raw in comments:
+        if not isinstance(raw, dict):
+            raise AdoError(_MISSING_TEXT_MSG)
+        text = _comment_text(raw)
+        tokens |= marker_tokens(text)
+        tokens |= marker_tokens(html_to_text(text))
+    return tokens
+
+
+def plan_comments(entries, tokens):
+    """Decide, per entry, whether it is already on the work item. (PURE)
+
+    `tokens` comes from comment_haystack_tokens over the work item's FULL
+    paginated comment list, read back over the network -- THE WORK ITEM'S OWN
+    COMMENT LIST IS THE DEDUPE GATE, never a local file, so a fresh clone
+    cannot double-post. An entry whose marker (or whose bare digest) is
+    already in the set is reported as already-posted rather than posted again
+    or silently dropped. IN-BATCH duplicates are not this function's job:
+    validate_comment_entries refuses them before the lane gets here, because
+    this gate compares each entry to the work item and never to its
+    siblings."""
+    planned = []
+    for item in entries:
+        marker = item["marker"]
+        digest = marker[-13:-1]
+        planned.append({
+            "kind": item["kind"], "marker": marker,
+            "already_posted": marker in tokens or digest in tokens})
+    return planned
+
+
+# THE WRONG-TARGET REFUSAL. An Azure DevOps work item is a bare integer plus an
+# org and a project that come from OUTSIDE the id, so item 1234 exists in every
+# org and project -- a hazard Jira's self-describing ABC-123 key cannot even
+# express. The record names one triple, the rendered comments payload names the
+# triple it was rendered FOR, and agreed_target refuses unless the two are
+# EQUAL -- it is pure, so the comment lane can run it before it reads a
+# credential or issues a request.
+TRIPLE_FIELDS = ("org", "project", "id")
+PAYLOAD_TRIPLE_FIELDS = ("work_item_org", "work_item_project", "work_item_id")
+
+_RECORD_TRIPLE_MSG = (
+    "the record does not name its own target: the field(s) %s are missing or "
+    "empty. A record that cannot name its (org, project, id) cannot be "
+    "checked against the work item a write would land on.")
+_PAYLOAD_TRIPLE_MSG = (
+    "the comments file does not name the work item it was rendered for: the "
+    "field(s) %s are missing or empty. Pass the whole payload object printed "
+    "by ado_intake.py render (which carries %s), not a bare comments array.")
+_WRONG_TARGET_MSG = (
+    "REFUSING THE WRITE: the comment plan does not belong to %s (%s). An "
+    "Azure DevOps work-item id is a bare integer, so id %s exists in every "
+    "org and project: posting here would put one item's refinement on "
+    "another, and the read-back dedupe gate would report a clean success. "
+    "Re-resolve the work item and re-render the comments.")
+
+
+def _triple_from(source, keys, missing_error):
+    """Read an (org, project, id) triple out of `source` under `keys`,
+    fail-closed. Every field must be a non-empty string, and the id must
+    survive validate_work_item_id -- it reaches a URL segment. (PURE apart
+    from raising)"""
+    if not isinstance(source, dict):
+        raise missing_error(", ".join(keys))
+    missing = [
+        key for key in keys
+        if not isinstance(source.get(key), str) or not source[key].strip()
+    ]
+    if missing:
+        raise missing_error(", ".join(missing))
+    org, project, work_item_id = (source[key].strip() for key in keys)
+    return (org, project, validate_work_item_id(work_item_id))
+
+
+def _record_triple_error(names):
+    """A record that cannot name its own target is a CONTRACT failure (exit
+    1): all three fields are in REQUIRED_FIELDS, so a missing one means the
+    record did not come from resolve_work_item."""
+    return AdoError(_RECORD_TRIPLE_MSG % names)
+
+
+def _payload_triple_error(names):
+    """A comments payload that cannot name its target is USAGE (exit 2): the
+    operator passed the wrong file, or a bare comments array."""
+    return AdoUsageError(
+        _PAYLOAD_TRIPLE_MSG % (names, ", ".join(PAYLOAD_TRIPLE_FIELDS)))
+
+
+def record_triple(record):
+    """The (org, project, id) triple of a resolve record. (PURE apart from
+    raising) All three are in the record's REQUIRED_FIELDS, so an empty one is
+    a half-resolve; reaching this function with one missing means the record
+    did not come from resolve_work_item and is a contract failure."""
+    return _triple_from(record, TRIPLE_FIELDS, _record_triple_error)
+
+
+def payload_triple(payload):
+    """The (org, project, id) triple the comments payload was RENDERED FOR.
+    (PURE apart from raising)
+
+    THE BINDING BETWEEN A PREVIEW AND THE ITEM IT WAS RENDERED FOR. A bare
+    comments array carries no triple and is refused here: the target must come
+    from the rendered payload and the resolved record, never from ambient
+    environment addressing."""
+    return _triple_from(payload, PAYLOAD_TRIPLE_FIELDS, _payload_triple_error)
+
+
+def assert_same_target(expected, actual, what):
+    """Refuse unless two (org, project, id) triples are EQUAL, naming both
+    sides and preferring neither.
+
+    THE COMPARISON IS DELIBERATELY EXACT. Azure DevOps org and project names
+    are case-preserving, this path fails closed, and a case-insensitive or
+    punctuation-folding compare would quietly widen what it accepts -- on the
+    one lane in this plugin whose mistakes cannot be undone. Do not 'fix' it
+    into one."""
+    diffs = [
+        "%s %r != %r" % (name, want, got)
+        for name, want, got in zip(TRIPLE_FIELDS, expected, actual)
+        if want != got
+    ]
+    if diffs:
+        raise AdoError(_WRONG_TARGET_MSG % (what, "; ".join(diffs), actual[2]))
+    return None
+
+
+def agreed_target(record, payload):
+    """The one (org, project, id) triple the record and the comments payload
+    BOTH name, or a refusal. (PURE apart from raising)
+
+    Runs BEFORE any credential is read and before the first request, so a
+    mismatched pair costs nothing and leaks nothing."""
+    target = record_triple(record)
+    assert_same_target(target, payload_triple(payload), "the resolved record")
+    return target
+
+
+# THE COMMENT LANE. Posting is OFF BY DEFAULT: without `arm` the lane issues
+# GETs only and reports what it WOULD post. The order below IS the safety
+# design -- pure entry validation first, then ONE fresh re-resolve that proves
+# the target and supplies the dedupe haystack at once, then the refusal, and
+# only then the single bounded write.
+_INVALID_PLAN_MSG = "refusing to post from an invalid comment plan: %s"
+_PARTIAL_BATCH_MSG = (
+    "%s; %d comment(s) already posted to work item %s before the failure: "
+    "%s. Those comments are on the work item now and this connector has no "
+    "lane to delete them. A later run suppresses exactly those markers, and "
+    "only while the refinement still renders byte-identically.")
+
+
+def _partial_batch_error(work_item_id, posted, exc):
+    """The AdoError raised when a batch POST fails part-way through.
+
+    The BATCH is not atomic -- only each individual comment is (see
+    execute_comment_plan) -- so a failure after N comments have already
+    landed must SAY SO: the work item has been mutated even though the whole
+    operation is being reported as failed, and there is no comment-delete
+    lane to retract it. Every already-posted marker is named, so the operator
+    can tell exactly what happened from the refusal alone.
+
+    DELIBERATELY NOT A RECOVERY INSTRUCTION. A later run suppresses a landed
+    comment only while the refinement still renders byte-identically:
+    measured on the Jira twin of this lane, dropping a single period from the
+    refinement changed the marker, so a second pass over an edited refinement
+    would post NEW comments beside the landed ones. The disclosure states
+    what happened and names the markers; what to do next is the operator's
+    call, with the work item in front of them.
+
+    The message carries the underlying AdoError, which names only a URL, plus
+    markers this module never invents -- so no credential can ride out in
+    it."""
+    if not posted:
+        return AdoError(str(exc))
+    markers = ", ".join(item["marker"] for item in posted)
+    return AdoError(
+        _PARTIAL_BATCH_MSG % (exc, len(posted), work_item_id, markers))
+
+
+def _posted_result(item, comment_id):
+    """One result row for a comment that LANDED. (PURE)"""
+    return {
+        "kind": item["kind"], "marker": item["marker"],
+        "status": "posted", "comment_id": comment_id}
+
+
+def execute_comment_plan(route, pat, pending):
+    """POST each pending comment in order and return one result each.
+
+    Fail closed and ATOMIC PER COMMENT: every entry was shape-validated
+    before any request was issued, and the FIRST failure propagates
+    immediately, so no later comment is posted. One comment is written whole
+    by one POST or not at all -- there is no partial body.
+
+    The BATCH is not atomic, and that partial mutation is DISCLOSED rather
+    than swallowed (see _partial_batch_error): this is the only irreversible
+    external call in this module."""
+    posted = []
+    for item in pending:
+        try:
+            comment_id = post_comment(route, pat, item["body"])
+        except AdoError as exc:
+            raise _partial_batch_error(route[2], posted, exc) from exc
+        posted.append(_posted_result(item, comment_id))
+    return posted
+
+
+def _preview_result(item, planned):
+    """One result row for a comment that was NOT posted on this invocation:
+    either already on the work item, or awaiting an armed run. (PURE)"""
+    status = "already-posted" if planned["already_posted"] else "would-post"
+    return {
+        "kind": item["kind"], "marker": planned["marker"],
+        "status": status, "comment_id": None}
+
+
+def _comment_results(entries, plan, posted):
+    """Merge the dedupe plan and the POST results into one ordered result per
+    REQUESTED comment, in the requested order. (PURE)
+
+    Keyed by marker, which is safe ONLY because validate_comment_entries
+    already refused an in-batch duplicate: two entries sharing a marker would
+    collapse onto one row here and both report the same comment id -- the
+    exact collapse measured on the Jira twin of this lane."""
+    by_marker = {item["marker"]: item for item in posted}
+    return [
+        by_marker.get(planned["marker"]) or _preview_result(item, planned)
+        for item, planned in zip(entries, plan)
+    ]
+
+
+def _assert_target_unchanged(target, fresh, org):
+    """Refuse unless `target` still names BOTH the work item the fresh read
+    just returned AND the organization the current ADO_ORG_URL points at.
+
+    Two checks because there are two ways to drift. The record check catches
+    a comments payload rendered for a different item; the environment check
+    catches the org moving between the preview invocation and the armed one
+    -- a different shell tab, a re-sourced .env, a mistyped re-export. Both
+    land one item's refinement on another, and the read-back dedupe gate
+    SUCCEEDS on the wrong item (it carries no such marker), so the operator
+    would otherwise see a clean success."""
+    assert_same_target(
+        target, record_triple(fresh), "the freshly resolved work item")
+    assert_same_target(
+        target, (org, target[1], target[2]),
+        "the organization named by the current ADO_ORG_URL")
+    return None
+
+
+def run_comment_lane(target, entries, arm):
+    """Preview -- or, when armed, post -- the intake comments for ONE work
+    item, target-checked and dedupe-gated. `target` is the agreed
+    (org, project, id) triple; `arm` alone decides whether a write happens.
+
+    POSTING IS OFF BY DEFAULT: with `arm` false this issues GETs only and
+    reports what it WOULD post, so the default path performs zero writes.
+
+    THE ORDER IS THE SAFETY DESIGN:
+      1. Every entry is shape-validated -- marker shape, marker alone on line
+         1 of the body, an inert body, and no in-batch duplicate -- BEFORE
+         any credential is read and BEFORE the first request, so a refusal
+         leaves nothing partial on the work item.
+      2. The work item is RE-RESOLVED fresh. That one read serves both
+         purposes at once: it proves the target and it supplies the comment
+         history, so the lane issues no extra request. The preview and the
+         armed post are separate invocations, so the target is re-proved here
+         rather than trusted from the payload.
+      3. The write REFUSES unless `target` equals the freshly resolved
+         (org, project, id) triple AND the org derived from the current
+         ADO_ORG_URL.
+      4. Only then, and only when armed, is a POST issued -- one per pending
+         comment, on a route composed from the validated api_root.
+
+    THE WORK ITEM IS READ ONCE PER INVOCATION, not before every individual
+    write: within one armed batch every comment is posted from the single
+    snapshot taken in step 2. A comment added by someone else mid-batch is
+    invisible to this run."""
+    errors = validate_comment_entries(entries)
+    if errors:
+        raise AdoError(_INVALID_PLAN_MSG % "; ".join(errors))
+    api_root, org, pat = credentials()
+    fresh = resolve_work_item(target[2])
+    _assert_target_unchanged(target, fresh, org)
+    plan = plan_comments(entries, comment_haystack_tokens(fresh["comments"]))
+    done = [bool(item["already_posted"]) for item in plan]
+    pending = [item for item, seen in zip(entries, done) if not seen]
+    posted = []
+    if arm:
+        posted = execute_comment_plan(
+            (api_root, target[1], target[2]), pat, pending)
+    return {
+        "ok": True, "org": target[0], "project": target[1],
+        "work_item_id": target[2], "title": fresh["title"],
+        "web_url": fresh["web_url"], "armed": bool(arm),
+        "posted_count": len(posted), "already_posted_count": done.count(True),
+        "results": _comment_results(entries, plan, posted)}
+
+
 # A rendered heading is either html_to_text's HEADING_PREFIX (from an <h1>-<h6>
 # tag) or a bare 'Acceptance Criteria:' line, which is how the section is
 # commonly styled with <b>. KNOWN LOSSINESS, stated rather than claimed away: a
 # <b>-styled pseudo-heading does NOT terminate the section, because the walker
 # renders it as ordinary prose, so a following bold-styled section is included.
@@ -947,33 +1581,90 @@ def resolve_work_item(work_item_id):
     })
     record["comments"] = fetch_comments(api_root, pat, project, resolved_id)
     return record
 
 
+def _load_json_file(path, what):
+    """Read one JSON file, mapping any read or parse failure to a usage error
+    the caller can fix. No credential is read and no request is issued before
+    this succeeds."""
+    try:
+        raw = Path(path).read_text(encoding="utf-8")
+    except OSError as exc:
+        raise AdoUsageError(
+            f"cannot read the {what} file {path}: {exc}") from exc
+    try:
+        return json.loads(raw)
+    except ValueError as exc:
+        raise AdoUsageError(
+            f"the {what} file {path} is not valid JSON: {exc}") from exc
+
+
+def _comment_payload(args):
+    """Load the resolved record and the rendered comments, agree on ONE target
+    triple, and run the comment lane.
+
+    THE TARGET COMES FROM THE RESOLVED RECORD AND THE RENDERED PAYLOAD, never
+    from ambient environment addressing and never from a flag: there is no
+    --id, no --project and no --org on this subcommand. The two files must
+    name the same (org, project, id) or the lane refuses -- before a
+    credential is read and before the first request."""
+    record = _load_json_file(args.record, "record")
+    payload = _load_json_file(args.comments, "comments")
+    target = agreed_target(record, payload)
+    entries = payload.get("comments") if isinstance(payload, dict) else None
+    return run_comment_lane(target, entries, args.post)
+
+
 def build_parser():
-    """Build the CLI parser. The read lane exposes exactly one subcommand,
-    `resolve --id`, and it issues no write.
+    """Build the CLI parser. The read lane exposes `resolve --id`, which
+    issues no write, and the write lane exposes `comment`, which previews by
+    default and issues its one bounded POST only under --post.
 
     There is deliberately NO credential flag and NO --project flag on any
     subcommand: credentials are read from the environment only, so they
     cannot appear on a command line that `ps` can see, and the project is
     read from the work item's own System.TeamProject, so a flag could only
-    disagree with it."""
+    disagree with it. `comment` also has no --id: its target comes from the
+    resolved record and the rendered comments payload agreeing, never from a
+    flag."""
     parser = argparse.ArgumentParser(
         description="Azure DevOps Services work-item reader (read-only).")
     sub = parser.add_subparsers(dest="command", required=True)
     resolve = sub.add_parser(
         "resolve",
         help="Resolve one work-item id to a normalized JSON record.")
     resolve.add_argument(
         "--id", required=True, dest="work_item_id",
         help="Azure DevOps work-item id, e.g. 1234.")
+    comment = sub.add_parser(
+        "comment",
+        help=("Preview the spec-loop intake comments for one work item -- "
+              "or, with --post, actually add them."))
+    comment.add_argument(
+        "--record", required=True,
+        help=("path to this module's `resolve` output (JSON). The write "
+              "target comes from this record, never from the environment "
+              "alone."))
+    comment.add_argument(
+        "--comments", required=True,
+        help=("path to the whole payload object printed by ado_intake.py "
+              "render, which carries both the comment bodies and the "
+              "(org, project, id) triple they were rendered for"))
+    comment.add_argument(
+        "--post", action="store_true",
+        help=("ARM THE WRITE. Without this flag nothing is posted: the lane "
+              "issues GETs only and reports what it would post."))
     return parser
 
 
 def _dispatch(args):
-    """Run the requested subcommand and return the object to print."""
+    """Run the requested subcommand and return the object to print. The
+    comment lane is reached only through its own subcommand, and it previews
+    unless args.post armed it."""
+    if args.command == "comment":
+        return _comment_payload(args)
     return resolve_work_item(args.work_item_id)
 
 
 def main(argv=None):
     """Parse args, dispatch, print one JSON object. Exit 0 ok, 1 contract
diff --git a/plugins/spec-loop/scripts/test_ado_client.py b/plugins/spec-loop/scripts/test_ado_client.py
index 9da2119..897e2b3 100644
--- a/plugins/spec-loop/scripts/test_ado_client.py
+++ b/plugins/spec-loop/scripts/test_ado_client.py
@@ -963,10 +963,806 @@ class TestTheReadLaneStaysReadOnly(unittest.TestCase):
         for fn in (ac.fetch_work_item, ac.fetch_comments):
             with self.subTest(fn=fn.__name__):
                 self.assertIn("_http_get(", inspect.getsource(fn))
 
 
+class TestHttpPostIsTheOnlyWriter(unittest.TestCase):
+    """The writer is a SEPARATE function from _http_get, and the GET helper
+    never grows a body or a method parameter -- the absence of `data` on
+    _http_get is the read lane's security proof."""
+
+    def test_http_get_still_has_no_data_or_method_parameter(self):
+        params = inspect.signature(ac._http_get).parameters
+        self.assertNotIn("data", params)
+        self.assertNotIn("method", params)
+
+    def test_http_post_is_a_distinct_function_that_takes_a_payload(self):
+        params = inspect.signature(ac._http_post).parameters
+        self.assertEqual(list(params), ["url", "pat", "payload"])
+
+    def test_http_post_sends_a_post_with_a_json_body(self):
+        seen = {}
+
+        class _Resp:
+            def __enter__(self_inner):
+                return self_inner
+
+            def __exit__(self_inner, *exc):
+                return False
+
+            def read(self_inner):
+                return b'{"id": 7}'
+
+        def _open(req, timeout=None):
+            seen["method"] = req.get_method()
+            seen["data"] = req.data
+            seen["ctype"] = req.get_header("Content-type")
+            return _Resp()
+
+        with mock.patch.object(ac._OPENER, "open", _open):
+            raw = ac._http_post("https://dev.azure.com/o/x", "tok", {"text": "hi"})
+        self.assertEqual(raw, b'{"id": 7}')
+        self.assertEqual(seen["method"], "POST")
+        self.assertEqual(json.loads(seen["data"].decode("utf-8")), {"text": "hi"})
+        self.assertEqual(seen["ctype"], "application/json")
+
+    def test_an_http_error_on_the_write_names_only_the_url(self):
+        error = urllib.error.HTTPError(
+            "https://dev.azure.com/o/x", 403, "Forbidden", {}, None)
+        # Closed deterministically, exactly as TestTheSecretNeverLeaks does:
+        # an HTTPError IS a response object, so an unclosed one emits a
+        # ResourceWarning into whichever test is capturing stderr when the
+        # collector reaches it.
+        self.addCleanup(error.close)
+        with mock.patch.object(ac._OPENER, "open", side_effect=error):
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac._http_post("https://dev.azure.com/o/x", "sekrit", {"text": "x"})
+        message = str(ctx.exception)
+        self.assertIn("https://dev.azure.com/o/x", message)
+        self.assertNotIn("sekrit", message)
+        self.assertNotIn(base64.b64encode(b":sekrit").decode("ascii"), message)
+
+    def test_a_url_error_on_the_write_is_an_ado_error(self):
+        with mock.patch.object(ac._OPENER, "open",
+                               side_effect=urllib.error.URLError("down")):
+            with self.assertRaises(ac.AdoError):
+                ac._http_post("https://dev.azure.com/o/x", "tok", {"text": "x"})
+
+    def test_a_bare_oserror_while_reading_the_write_response_is_an_ado_error(self):
+        with mock.patch.object(ac._OPENER, "open",
+                               side_effect=OSError("connection reset")):
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac._http_post("https://dev.azure.com/o/x", "sekrit", {"text": "x"})
+        self.assertNotIn("sekrit", str(ctx.exception))
+
+
+class TestPostOneComment(unittest.TestCase):
+    ROUTE = ("https://dev.azure.com/contoso", "My Team", "1234")
+
+    def test_the_add_url_is_composed_locally_with_the_add_api_version(self):
+        url = ac.comment_add_url(self.ROUTE)
+        self.assertEqual(
+            url,
+            "https://dev.azure.com/contoso/My%20Team/_apis/wit/workItems/1234"
+            "/comments?api-version=7.0-preview.3")
+
+    def test_the_add_api_version_differs_from_the_read_versions(self):
+        url = ac.comment_add_url(self.ROUTE)
+        self.assertIn(ac.API_VERSION_COMMENT_ADD, url)
+        self.assertNotIn(ac.API_VERSION_COMMENTS_READ, url)
+
+    def test_a_bad_id_is_refused_before_a_url_exists(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.comment_add_url(("https://dev.azure.com/contoso", "P", "../x"))
+
+    def test_post_comment_returns_the_created_comment_id(self):
+        with mock.patch.object(ac, "_http_post",
+                               return_value=b'{"id": 42}') as post:
+            comment_id = ac.post_comment(self.ROUTE, "tok", "body")
+        self.assertEqual(comment_id, "42")
+        url, pat, payload = post.call_args.args
+        self.assertEqual(payload, {"text": "body"})
+        self.assertEqual(pat, "tok")
+        self.assertTrue(url.startswith("https://dev.azure.com/contoso/"))
+
+    def test_the_commentid_spelling_is_accepted_too(self):
+        with mock.patch.object(ac, "_http_post", return_value=b'{"commentId": 9}'):
+            self.assertEqual(ac.post_comment(self.ROUTE, "tok", "b"), "9")
+
+    def test_a_response_without_an_id_refuses_rather_than_confirm_the_write(self):
+        with mock.patch.object(ac, "_http_post", return_value=b"{}"):
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac.post_comment(self.ROUTE, "tok", "b")
+        self.assertIn("1234", str(ctx.exception))
+
+    def test_a_non_object_response_refuses(self):
+        with mock.patch.object(ac, "_http_post", return_value=b"[]"):
+            with self.assertRaises(ac.AdoError):
+                ac.post_comment(self.ROUTE, "tok", "b")
+
+
+def entry(kind, marker, body=None):
+    """One comment entry in ado_intake render's shape, marker on line 1."""
+    return {"kind": kind, "gap_id": None, "marker": marker,
+            "body": body if body is not None else "%s\n\nheading" % marker}
+
+
+MARKER_A = "[spec-loop-intake:understanding:0123456789ab]"
+MARKER_B = "[spec-loop-intake:decision:ba9876543210]"
+
+
+class TestADuplicateBatchIsRefusedBeforeAnyPost(unittest.TestCase):
+    """Hazard 1 from run 20260908-jira-intake, measured on the Jira twin: the
+    read-back dedupe gate compares each entry to the work item and never to
+    its siblings, so two identical entries in ONE batch both plan as
+    not-already-posted, both POST, and a results map keyed by marker collapses
+    them onto one comment id. Refuse the batch at validation, before the first
+    request, which is the only point at which it is still a no-op."""
+
+    def test_two_entries_sharing_a_marker_are_refused(self):
+        errors = ac.validate_comment_entries(
+            [entry("understanding", MARKER_A), entry("decision", MARKER_A)])
+        self.assertEqual(len(errors), 1)
+        self.assertIn(MARKER_A, errors[0])
+        self.assertIn("comments[1]", errors[0])
+        self.assertIn("comments[0]", errors[0])
+
+    def test_distinct_markers_are_accepted(self):
+        self.assertEqual(
+            ac.validate_comment_entries(
+                [entry("understanding", MARKER_A), entry("decision", MARKER_B)]),
+            [])
+
+    def test_a_third_copy_is_reported_too(self):
+        errors = ac.validate_comment_entries([entry("understanding", MARKER_A)] * 3)
+        self.assertEqual(len(errors), 2)
+
+
+class TestAPostedBodyMustBeInertAndCarryItsMarker(unittest.TestCase):
+    def test_an_empty_batch_is_refused(self):
+        for bad in ([], None, {}, "nope"):
+            with self.subTest(value=bad):
+                self.assertTrue(ac.validate_comment_entries(bad))
+
+    def test_a_missing_key_is_reported_with_its_index(self):
+        errors = ac.validate_comment_entries([{"kind": "decision"}])
+        self.assertTrue(any("comments[0]" in e and "marker" in e for e in errors))
+
+    def test_a_non_object_entry_is_reported(self):
+        errors = ac.validate_comment_entries(["x"])
+        self.assertTrue(any("comments[0]" in e for e in errors))
+
+    def test_a_marker_outside_the_marker_shape_is_refused(self):
+        errors = ac.validate_comment_entries([entry("decision", "[nope]")])
+        self.assertTrue(any("marker" in e for e in errors))
+
+    def test_a_body_that_lost_its_marker_is_refused(self):
+        errors = ac.validate_comment_entries(
+            [entry("decision", MARKER_B, body="heading only")])
+        self.assertTrue(any("body" in e for e in errors))
+
+    def test_the_marker_must_be_on_line_one(self):
+        errors = ac.validate_comment_entries(
+            [entry("decision", MARKER_B, body="heading\n\n%s" % MARKER_B)])
+        self.assertTrue(any("line 1" in e for e in errors))
+
+    def test_a_body_carrying_active_markup_is_refused(self):
+        for bad in ("<b>x</b>", "a > b", "<script>"):
+            with self.subTest(body=bad):
+                body = "%s\n\n%s" % (MARKER_B, bad)
+                entries = [entry("decision", MARKER_B, body=body)]
+                errors = ac.validate_comment_entries(entries)
+                self.assertTrue(any("inert" in e for e in errors), errors)
+
+    def test_an_escaped_body_is_accepted(self):
+        body = "%s\n\nRisks\n\n- Tom &amp; Jerry &lt;br&gt;" % MARKER_B
+        self.assertEqual(
+            ac.validate_comment_entries([entry("decision", MARKER_B, body=body)]),
+            [])
+
+    def test_escaping_leaves_the_marker_byte_identical(self):
+        """The posted body is escaped (&, <, > -- in that order) because ADO's
+        Add body cannot declare its format. The marker contains none of those
+        characters, so dedupe is provably unaffected: asserted here rather
+        than reasoned about."""
+        body = "%s\n\nTom & Jerry <b>x</b> a > b" % MARKER_A
+        escaped = body
+        for needle, replacement in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;")):
+            escaped = escaped.replace(needle, replacement)
+        self.assertEqual(ac.MARKER_RE.findall(escaped), [MARKER_A])
+        self.assertEqual(escaped.splitlines()[0], MARKER_A)
+        self.assertIn(MARKER_A, escaped)
+
+    def test_a_bad_kind_is_refused(self):
+        errors = ac.validate_comment_entries([entry("transition", MARKER_A)])
+        self.assertTrue(any("kind" in e for e in errors))
+
+    def test_shape_errors_short_circuit_the_duplicate_scan(self):
+        """A batch with a malformed entry reports the shape error only: the
+        duplicate scan indexes entry['marker'] and must not run on an entry
+        that has no marker."""
+        errors = ac.validate_comment_entries(
+            [{"kind": "decision"}, entry("decision", MARKER_A)])
+        self.assertTrue(errors)
+        self.assertFalse(any("duplicates" in e for e in errors))
+
+
+class TestTheDedupeGateExtractsMarkersIntoASet(unittest.TestCase):
+    """Extract-and-compare-SETS, never substring, and over the raw stored
+    `text` UNIONed with its html_to_text rendering -- never the optional HTML
+    rendering ADO can return under $expand."""
+
+    def _comment(self, text):
+        return {"id": "1", "author": "a", "created": "", "modified": "",
+                "text": text}
+
+    def test_a_marker_wrapped_in_html_is_still_found(self):
+        tokens = ac.comment_haystack_tokens(
+            [self._comment("<div>%s</div>\n<p>body</p>" % MARKER_A)])
+        self.assertIn(MARKER_A, tokens)
+
+    def test_a_marker_forged_inside_an_html_comment_is_found_via_raw_text(self):
+        """html_to_text drops HTML comments, so the walker alone is blind to
+        this one; the raw `text` side of the union sees it. Suppression is the
+        fail-safe direction: a false suppression skips a write, a false miss
+        duplicates a comment on a live work item."""
+        raw = "<!-- %s -->\nvisible" % MARKER_A
+        self.assertNotIn(MARKER_A, ac.html_to_text(raw))
+        self.assertIn(MARKER_A, ac.comment_haystack_tokens([self._comment(raw)]))
+
+    def test_an_entity_escaped_neighbour_does_not_hide_the_marker(self):
+        raw = "%s &amp; more" % MARKER_A
+        self.assertIn(MARKER_A, ac.comment_haystack_tokens([self._comment(raw)]))
+
+    def test_the_bare_digest_alone_suppresses_as_the_second_tier(self):
+        digest = MARKER_A[-13:-1]
+        tokens = ac.comment_haystack_tokens(
+            [self._comment("wrapper rewritten, digest kept: %s" % digest)])
+        plan = ac.plan_comments([entry("understanding", MARKER_A)], tokens)
+        self.assertTrue(plan[0]["already_posted"])
+
+    def test_an_unrelated_comment_does_not_suppress(self):
+        tokens = ac.comment_haystack_tokens([self._comment("ordinary chatter")])
+        plan = ac.plan_comments([entry("understanding", MARKER_A)], tokens)
+        self.assertFalse(plan[0]["already_posted"])
+
+    def test_the_gate_never_consults_rendered_text(self):
+        """Pinned in a named test so a later change cannot repoint the gate at
+        the optional HTML rendering: a marker an HTML renderer altered would go
+        unmatched, every entry would plan as not-already-posted, and the lane
+        would post again on a live work item."""
+        for fn in (ac.comment_haystack_tokens, ac.marker_tokens,
+                   ac.plan_comments):
+            with self.subTest(fn=fn.__name__):
+                self.assertNotIn("renderedText", inspect.getsource(fn))
+
+    def test_a_comment_without_text_fails_closed_rather_than_shrink_the_haystack(self):
+        for bad in ({"id": "1"}, {"id": "1", "text": ""},
+                    {"id": "1", "text": None}, "not a comment"):
+            with self.subTest(comment=bad):
+                with self.assertRaises(ac.AdoError):
+                    ac.comment_haystack_tokens([bad])
+
+    def test_an_empty_history_yields_an_empty_token_set(self):
+        self.assertEqual(ac.comment_haystack_tokens([]), set())
+
+    def test_plan_preserves_order_and_reports_each_entry(self):
+        tokens = ac.comment_haystack_tokens([self._comment(MARKER_B)])
+        plan = ac.plan_comments(
+            [entry("understanding", MARKER_A), entry("decision", MARKER_B)],
+            tokens)
+        self.assertEqual([p["marker"] for p in plan], [MARKER_A, MARKER_B])
+        self.assertEqual([p["already_posted"] for p in plan], [False, True])
+        self.assertEqual([p["kind"] for p in plan],
+                         ["understanding", "decision"])
+
+
+def ado_record(org="contoso", project="My Team", work_item_id="1234"):
+    """One resolve record, as resolve_work_item returns it."""
+    return {
+        "org": org,
+        "project": project,
+        "id": work_item_id,
+        "web_url": "https://dev.azure.com/contoso/_workitems/edit/1234",
+        "title": "T",
+        "work_item_type": "Bug",
+        "state": "Active",
+        "comments": [],
+    }
+
+
+def render_payload(
+        org="contoso", project="My Team", work_item_id="1234", comments=None):
+    """The whole payload object ado_intake.py render prints, which carries the
+    (org, project, id) triple the comments were rendered FOR."""
+    if comments is None:
+        comments = [entry("understanding", MARKER_A)]
+    return {
+        "ok": True,
+        "work_item_org": org,
+        "work_item_project": project,
+        "work_item_id": work_item_id,
+        "posted": False,
+        "comments": comments,
+    }
+
+
+class TestTheWriteRefusesAWrongTarget(unittest.TestCase):
+    """An Azure DevOps work item is a bare integer plus an org and a project
+    that come from OUTSIDE the id, so work item 1234 exists in every org. The
+    preview and the armed post are separate invocations: if the org changes
+    between them the connector would post item A's refinement onto item B, and
+    the read-back dedupe gate would SUCCEED (item B has no such marker), so the
+    operator would see a clean success. There is no comment-delete lane."""
+
+    def test_the_agreed_target_is_the_triple_both_sides_name(self):
+        target = ac.agreed_target(ado_record(), render_payload())
+        self.assertEqual(target, ("contoso", "My Team", "1234"))
+
+    def test_a_payload_naming_another_org_is_refused(self):
+        with self.assertRaises(ac.AdoError) as ctx:
+            ac.agreed_target(ado_record(), render_payload(org="fabrikam"))
+        message = str(ctx.exception)
+        self.assertIn("contoso", message)
+        self.assertIn("fabrikam", message)
+        self.assertIn("org", message)
+
+    def test_a_payload_naming_another_project_is_refused(self):
+        with self.assertRaises(ac.AdoError):
+            ac.agreed_target(ado_record(), render_payload(project="Other"))
+
+    def test_a_payload_naming_another_work_item_is_refused(self):
+        with self.assertRaises(ac.AdoError):
+            ac.agreed_target(ado_record(), render_payload(work_item_id="9999"))
+
+    def test_the_comparison_is_exact_not_case_folded(self):
+        with self.assertRaises(ac.AdoError):
+            ac.agreed_target(ado_record(), render_payload(project="my team"))
+
+    def test_a_record_missing_a_triple_field_is_refused(self):
+        broken = ado_record()
+        del broken["project"]
+        with self.assertRaises(ac.AdoError) as ctx:
+            ac.record_triple(broken)
+        self.assertIn("project", str(ctx.exception))
+
+    def test_a_payload_without_the_triple_is_a_usage_error(self):
+        with self.assertRaises(ac.AdoUsageError) as ctx:
+            ac.payload_triple({"comments": []})
+        self.assertIn("work_item_org", str(ctx.exception))
+
+    def test_a_payload_that_is_a_bare_array_is_a_usage_error(self):
+        """A bare comments array carries no (org, project, id) triple, so it
+        cannot be bound to the item it was rendered for and is refused."""
+        with self.assertRaises(ac.AdoUsageError):
+            ac.payload_triple([entry("understanding", MARKER_A)])
+
+    def test_a_non_numeric_id_in_the_payload_is_refused(self):
+        with self.assertRaises(ac.AdoUsageError):
+            ac.payload_triple(render_payload(work_item_id="12/comments"))
+
+    def test_assert_same_target_names_both_sides_and_prefers_neither(self):
+        what = "the freshly resolved work item"
+        expected = ("contoso", "A", "1")
+        actual = ("contoso", "B", "1")
+        with self.assertRaises(ac.AdoError) as ctx:
+            ac.assert_same_target(expected, actual, what)
+        message = str(ctx.exception)
+        self.assertIn(what, message)
+        self.assertIn("'A'", message)
+        self.assertIn("'B'", message)
+
+
+def posted_comment(text, cid="5"):
+    """One already-stored comment, in the shape resolve_work_item returns,
+    so a test can seed the work item's dedupe haystack."""
+    return {"id": cid, "author": "a", "created": "", "modified": "",
+            "text": text}
+
+
+class TestTheCommentLanePreviewsByDefault(unittest.TestCase):
+    """Posting is OFF BY DEFAULT: the unarmed lane issues GETs only and
+    reports what it WOULD post. The whole safety chain -- entry validation,
+    then ONE fresh re-resolve, then the target agreement -- runs before a
+    POST can exist at all."""
+
+    ENV = {"ADO_ORG_URL": "https://dev.azure.com/contoso", "ADO_PAT": "tok"}
+    TARGET = ("contoso", "My Team", "1234")
+
+    @contextlib.contextmanager
+    def _lane(self, fresh=None, env=None):
+        """Patch the environment, the fresh re-resolve and the writer on one
+        stack, so no test can reach a socket."""
+        record = fresh if fresh is not None else ado_record()
+        with contextlib.ExitStack() as stack:
+            stack.enter_context(
+                mock.patch.dict(ac.os.environ, env or self.ENV, clear=True))
+            patched = mock.patch.object(
+                ac, "resolve_work_item", return_value=record)
+            resolve = stack.enter_context(patched)
+            post = stack.enter_context(mock.patch.object(ac, "_http_post"))
+            yield resolve, post
+
+    def test_the_default_path_posts_nothing_and_reports_what_it_would_post(self):
+        batch = [entry("understanding", MARKER_A)]
+        with self._lane() as (_resolve, post):
+            out = ac.run_comment_lane(self.TARGET, batch, False)
+        post.assert_not_called()
+        self.assertFalse(out["armed"])
+        self.assertEqual(out["posted_count"], 0)
+        self.assertEqual(out["results"][0]["status"], "would-post")
+        self.assertIsNone(out["results"][0]["comment_id"])
+
+    def test_the_payload_names_the_target_and_the_item_for_the_operator(self):
+        batch = [entry("understanding", MARKER_A)]
+        with self._lane() as (_resolve, _post):
+            out = ac.run_comment_lane(self.TARGET, batch, False)
+        named = (out["org"], out["project"], out["work_item_id"])
+        self.assertEqual(named, self.TARGET)
+        self.assertTrue(out["ok"])
+        self.assertEqual(out["title"], "T")
+        self.assertEqual(
+            out["web_url"],
+            "https://dev.azure.com/contoso/_workitems/edit/1234")
+
+    def test_the_fresh_reresolve_is_issued_for_the_targets_own_id(self):
+        batch = [entry("understanding", MARKER_A)]
+        with self._lane() as (resolve, _post):
+            ac.run_comment_lane(self.TARGET, batch, False)
+        resolve.assert_called_once_with("1234")
+
+    def test_an_already_posted_marker_is_reported_not_posted_again(self):
+        batch = [entry("understanding", MARKER_A)]
+        fresh = ado_record()
+        fresh["comments"] = [posted_comment("<div>%s</div>" % MARKER_A)]
+        with self._lane(fresh=fresh) as (_resolve, post):
+            out = ac.run_comment_lane(self.TARGET, batch, True)
+        post.assert_not_called()
+        self.assertEqual(out["already_posted_count"], 1)
+        self.assertEqual(out["posted_count"], 0)
+        self.assertEqual(out["results"][0]["status"], "already-posted")
+        self.assertIsNone(out["results"][0]["comment_id"])
+
+    def test_only_the_pending_entries_are_posted_from_a_mixed_batch(self):
+        batch = [
+            entry("understanding", MARKER_A), entry("decision", MARKER_B)]
+        fresh = ado_record()
+        fresh["comments"] = [posted_comment(MARKER_B)]
+        with self._lane(fresh=fresh) as (_resolve, post):
+            post.return_value = b'{"id": 88}'
+            out = ac.run_comment_lane(self.TARGET, batch, True)
+        self.assertEqual(post.call_count, 1)
+        statuses = [r["status"] for r in out["results"]]
+        self.assertEqual(statuses, ["posted", "already-posted"])
+        ids = [r["comment_id"] for r in out["results"]]
+        self.assertEqual(ids, ["88", None])
+        self.assertEqual(out["posted_count"], 1)
+        self.assertEqual(out["already_posted_count"], 1)
+
+    def test_an_invalid_batch_is_refused_before_any_credential_is_read(self):
+        batch = [entry("understanding", MARKER_A)] * 2
+        with contextlib.ExitStack() as stack:
+            stack.enter_context(mock.patch.dict(ac.os.environ, {}, clear=True))
+            creds = stack.enter_context(mock.patch.object(ac, "credentials"))
+            resolve = stack.enter_context(
+                mock.patch.object(ac, "resolve_work_item"))
+            with self.assertRaises(ac.AdoError):
+                ac.run_comment_lane(self.TARGET, batch, True)
+        creds.assert_not_called()
+        resolve.assert_not_called()
+
+    def test_validation_precedes_the_credential_read_in_the_source(self):
+        source = inspect.getsource(ac.run_comment_lane)
+        validated_at = source.index("validate_comment_entries")
+        credential_at = source.index("credentials()")
+        self.assertLess(validated_at, credential_at)
+
+    def test_a_target_drift_between_preview_and_post_refuses_before_any_write(
+            self):
+        batch = [entry("understanding", MARKER_A)]
+        with self._lane(fresh=ado_record(org="fabrikam")) as (_resolve, post):
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac.run_comment_lane(self.TARGET, batch, True)
+        post.assert_not_called()
+        self.assertIn("freshly resolved", str(ctx.exception))
+
+    def test_an_org_change_in_the_environment_refuses_before_any_write(self):
+        """The org is the residual environment input: a different shell tab or
+        a re-sourced .env between the preview and the armed post would
+        otherwise post item A's refinement onto item B.
+
+        The record check catches the usual shape of that drift, because the
+        fresh read follows the drifted org and comes back naming it. THIS
+        pins the second, belt-and-braces check -- the one on ADO_ORG_URL
+        itself -- which is the only one that can fire when the resolved
+        record still agrees with the target but the environment does not."""
+        env = {"ADO_ORG_URL": "https://dev.azure.com/fabrikam", "ADO_PAT": "t"}
+        batch = [entry("understanding", MARKER_A)]
+        with self._lane(env=env) as (_resolve, post):
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac.run_comment_lane(self.TARGET, batch, True)
+        post.assert_not_called()
+        self.assertIn("ADO_ORG_URL", str(ctx.exception))
+        self.assertIn("fabrikam", str(ctx.exception))
+
+    def test_a_comment_history_missing_its_text_fails_closed(self):
+        """A haystack that silently shrinks double-posts on every run, so a
+        text-less comment raises rather than planning the entry as pending."""
+        batch = [entry("understanding", MARKER_A)]
+        fresh = ado_record()
+        fresh["comments"] = [{"id": "5", "text": ""}]
+        with self._lane(fresh=fresh) as (_resolve, post):
+            with self.assertRaises(ac.AdoError):
+                ac.run_comment_lane(self.TARGET, batch, True)
+        post.assert_not_called()
+
+    def test_the_armed_lane_posts_each_pending_comment_once(self):
+        batch = [
+            entry("understanding", MARKER_A), entry("decision", MARKER_B)]
+        with self._lane() as (_resolve, post):
+            post.return_value = b'{"id": 77}'
+            out = ac.run_comment_lane(self.TARGET, batch, True)
+        self.assertEqual(post.call_count, 2)
+        self.assertEqual(out["posted_count"], 2)
+        self.assertTrue(out["armed"])
+        statuses = [r["status"] for r in out["results"]]
+        self.assertEqual(statuses, ["posted", "posted"])
+        ids = [r["comment_id"] for r in out["results"]]
+        self.assertEqual(ids, ["77", "77"])
+
+    def test_the_armed_lane_posts_on_the_api_root_route(self):
+        """The route is composed from the validated api_root and the agreed
+        project, never from the record's human web_url."""
+        batch = [entry("understanding", MARKER_A)]
+        expected = (
+            "https://dev.azure.com/contoso/My%20Team/_apis/wit/workItems/1234"
+            "/comments?api-version=" + ac.API_VERSION_COMMENT_ADD)
+        with self._lane() as (_resolve, post):
+            post.return_value = b'{"id": 1}'
+            ac.run_comment_lane(self.TARGET, batch, True)
+        self.assertEqual(post.call_args.args[0], expected)
+
+    def test_the_marker_rides_inside_the_posted_body(self):
+        """The marker lives INSIDE the posted body, so the one call that
+        writes the comment writes the marker: no local file is ever the
+        dedupe gate, and a fresh clone cannot double-post."""
+        batch = [entry("understanding", MARKER_A)]
+        with self._lane() as (_resolve, post):
+            post.return_value = b'{"id": 1}'
+            ac.run_comment_lane(self.TARGET, batch, True)
+        payload = post.call_args.args[2]
+        self.assertIn(MARKER_A, payload["text"])
+        self.assertEqual(payload["text"].splitlines()[0], MARKER_A)
+
+    def test_the_lane_never_claims_it_rereads_before_every_write(self):
+        """Hazard 3 from the Jira twin: prose that overstates a safety
+        property is a defect on a mutating lane. The item is read ONCE per
+        invocation, and the armed batch posts from that one snapshot."""
+        overclaims = (
+            "before every write", "before each write", "re-read before every")
+        source = inspect.getsource(ac.run_comment_lane)
+        for overclaim in overclaims:
+            self.assertNotIn(overclaim, source)
+        self.assertIn("READ ONCE PER INVOCATION", source)
+
+
+class TestTheArmedLaneDisclosesAPartialBatch(unittest.TestCase):
+    """The batch is NOT atomic -- only each individual comment is -- so a
+    failure after N comments have landed must say so: they are on the work
+    item now and there is no comment-delete lane to retract them."""
+
+    ROUTE = ("https://dev.azure.com/contoso", "My Team", "1234")
+
+    def test_every_pending_comment_is_posted_in_order(self):
+        pending = [
+            entry("understanding", MARKER_A), entry("decision", MARKER_B)]
+        with mock.patch.object(ac, "post_comment") as post:
+            post.side_effect = ["7", "8"]
+            results = ac.execute_comment_plan(self.ROUTE, "tok", pending)
+        self.assertEqual([r["marker"] for r in results], [MARKER_A, MARKER_B])
+        self.assertEqual([r["comment_id"] for r in results], ["7", "8"])
+        self.assertEqual([r["status"] for r in results], ["posted", "posted"])
+        bodies = [call.args[2] for call in post.call_args_list]
+        self.assertEqual(bodies, [pending[0]["body"], pending[1]["body"]])
+
+    def test_an_empty_pending_list_issues_no_write(self):
+        with mock.patch.object(ac, "post_comment") as post:
+            results = ac.execute_comment_plan(self.ROUTE, "tok", [])
+        self.assertEqual(results, [])
+        post.assert_not_called()
+
+    def test_the_first_failure_stops_the_batch(self):
+        pending = [
+            entry("understanding", MARKER_A), entry("decision", MARKER_B)]
+        with mock.patch.object(ac, "post_comment") as post:
+            post.side_effect = ac.AdoError("HTTP 500")
+            with self.assertRaises(ac.AdoError):
+                ac.execute_comment_plan(self.ROUTE, "tok", pending)
+        self.assertEqual(post.call_count, 1)
+
+    def test_a_failure_after_a_landed_write_names_what_already_posted(self):
+        pending = [
+            entry("understanding", MARKER_A), entry("decision", MARKER_B)]
+        with mock.patch.object(ac, "post_comment") as post:
+            post.side_effect = ["7", ac.AdoError("HTTP 500")]
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac.execute_comment_plan(self.ROUTE, "tok", pending)
+        message = str(ctx.exception)
+        self.assertIn("HTTP 500", message)
+        self.assertIn(MARKER_A, message)
+        self.assertIn("1 comment(s) already posted", message)
+        self.assertIn("1234", message)
+
+    def test_a_failure_before_any_write_is_reported_unchanged(self):
+        batch = [entry("understanding", MARKER_A)]
+        with mock.patch.object(ac, "post_comment") as post:
+            post.side_effect = ac.AdoError("HTTP 403")
+            with self.assertRaises(ac.AdoError) as ctx:
+                ac.execute_comment_plan(self.ROUTE, "tok", batch)
+        self.assertEqual(str(ctx.exception), "HTTP 403")
+
+    def test_the_disclosure_never_leaks_the_credential(self):
+        landed = [{"kind": "decision", "marker": MARKER_B}]
+        cause = ac.AdoError("HTTP 500 posting to https://dev.azure.com/o/x")
+        error = ac._partial_batch_error("1234", landed, cause)
+        self.assertNotIn("sekrit", str(error))
+        self.assertIn(MARKER_B, str(error))
+
+    def test_the_disclosure_never_claims_a_rerun_recovers_the_batch(self):
+        """Measured on the Jira twin: dropping one period from a refinement
+        changes the marker, so 're-run this command' is NOT a safe
+        partial-failure recovery. The disclosure must not say it."""
+        overclaims = (
+            "re-run this command", "Re-running is a no-op", "simply re-run")
+        source = inspect.getsource(ac._partial_batch_error)
+        for overclaim in overclaims:
+            self.assertNotIn(overclaim, source)
+
+
+class TestTheResultsMergePreservesTheRequestedOrder(unittest.TestCase):
+    def test_one_result_per_requested_entry_in_the_requested_order(self):
+        entries = [
+            entry("understanding", MARKER_A), entry("decision", MARKER_B)]
+        plan = ac.plan_comments(entries, {MARKER_B})
+        results = ac._comment_results(entries, plan, [])
+        self.assertEqual([r["marker"] for r in results], [MARKER_A, MARKER_B])
+        statuses = [r["status"] for r in results]
+        self.assertEqual(statuses, ["would-post", "already-posted"])
+        kinds = [r["kind"] for r in results]
+        self.assertEqual(kinds, ["understanding", "decision"])
+
+    def test_a_posted_result_replaces_its_preview(self):
+        entries = [entry("understanding", MARKER_A)]
+        plan = ac.plan_comments(entries, set())
+        posted = [ac._posted_result(entries[0], "9")]
+        results = ac._comment_results(entries, plan, posted)
+        self.assertEqual(results, posted)
+        self.assertEqual(results[0]["status"], "posted")
+        self.assertEqual(results[0]["comment_id"], "9")
+
+
+class TestTheCommentSubcommandIsOffByDefault(unittest.TestCase):
+    def _files(self, tmp, record, payload):
+        record_path = Path(tmp) / "record.json"
+        comments_path = Path(tmp) / "comments.json"
+        record_path.write_text(json.dumps(record), encoding="utf-8")
+        comments_path.write_text(json.dumps(payload), encoding="utf-8")
+        return str(record_path), str(comments_path)
+
+    def test_the_parser_arms_the_write_only_with_post(self):
+        parser = ac.build_parser()
+        args = parser.parse_args(
+            ["comment", "--record", "r.json", "--comments", "c.json"])
+        self.assertFalse(args.post)
+        armed = parser.parse_args(
+            ["comment", "--record", "r.json", "--comments", "c.json", "--post"])
+        self.assertTrue(armed.post)
+
+    def test_the_comment_subcommand_takes_exactly_three_options(self):
+        parser = ac.build_parser()
+        actions = [a for a in parser._actions
+                   if isinstance(a, argparse._SubParsersAction)]
+        options = {opt for action in actions[0].choices["comment"]._actions
+                   for opt in action.option_strings}
+        self.assertEqual(options - {"-h", "--help"},
+                         {"--record", "--comments", "--post"})
+
+    def test_there_is_no_id_flag_so_the_target_comes_from_the_record(self):
+        parser = ac.build_parser()
+        actions = [a for a in parser._actions
+                   if isinstance(a, argparse._SubParsersAction)]
+        options = {opt for action in actions[0].choices["comment"]._actions
+                   for opt in action.option_strings}
+        self.assertNotIn("--id", options)
+
+    def test_the_lane_runs_unarmed_through_the_cli(self):
+        import tempfile
+        with tempfile.TemporaryDirectory() as tmp:
+            record_path, comments_path = self._files(
+                tmp, ado_record(), render_payload())
+            with mock.patch.object(ac, "run_comment_lane",
+                                   return_value={"ok": True}) as lane, \
+                 mock.patch("sys.stdout", new_callable=io.StringIO) as out:
+                code = ac.main(["comment", "--record", record_path,
+                                "--comments", comments_path])
+        self.assertEqual(code, 0)
+        self.assertEqual(json.loads(out.getvalue()), {"ok": True})
+        target, entries, arm = lane.call_args.args
+        self.assertEqual(target, ("contoso", "My Team", "1234"))
+        self.assertEqual(entries[0]["marker"], MARKER_A)
+        self.assertFalse(arm)
+
+    def test_post_passes_the_arm_flag_through(self):
+        import tempfile
+        with tempfile.TemporaryDirectory() as tmp:
+            record_path, comments_path = self._files(
+                tmp, ado_record(), render_payload())
+            with mock.patch.object(ac, "run_comment_lane",
+                                   return_value={"ok": True}) as lane, \
+                 mock.patch("sys.stdout", new_callable=io.StringIO):
+                ac.main(["comment", "--record", record_path,
+                         "--comments", comments_path, "--post"])
+        self.assertTrue(lane.call_args.args[2])
+
+    def test_an_unreadable_file_is_exit_two_and_never_reaches_the_network(self):
+        with mock.patch.object(ac, "_http_post") as post, \
+             mock.patch.object(ac, "_http_get") as get, \
+             mock.patch("sys.stderr", new_callable=io.StringIO) as err:
+            code = ac.main(["comment", "--record", "/nonexistent/r.json",
+                            "--comments", "/nonexistent/c.json"])
+        self.assertEqual(code, 2)
+        self.assertIn("cannot read", err.getvalue())
+        post.assert_not_called()
+        get.assert_not_called()
+
+    def test_malformed_json_is_exit_two(self):
+        import tempfile
+        with tempfile.TemporaryDirectory() as tmp:
+            path = Path(tmp) / "r.json"
+            path.write_text("{not json", encoding="utf-8")
+            with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
+                code = ac.main(["comment", "--record", str(path),
+                                "--comments", str(path)])
+        self.assertEqual(code, 2)
+        self.assertIn("not valid JSON", err.getvalue())
+
+    def test_a_mismatched_pair_refuses_before_any_request(self):
+        import tempfile
+        with tempfile.TemporaryDirectory() as tmp:
+            record_path, comments_path = self._files(
+                tmp, ado_record(), render_payload(org="fabrikam"))
+            with mock.patch.object(ac, "credentials") as creds, \
+                 mock.patch.object(ac, "_http_get") as get, \
+                 mock.patch("sys.stdout", new_callable=io.StringIO) as out:
+                code = ac.main(["comment", "--record", record_path,
+                                "--comments", comments_path, "--post"])
+        self.assertEqual(code, 1)
+        self.assertFalse(json.loads(out.getvalue())["ok"])
+        creds.assert_not_called()
+        get.assert_not_called()
+
+
+class TestTheDocstringStatesTheWriteBoundary(unittest.TestCase):
+    """The module docstring is load-bearing prose on a mutating lane: it must
+    name the bound and must not claim a property this repo has not verified."""
+
+    def test_it_names_the_one_write_and_the_off_by_default_rule(self):
+        doc = ac.__doc__
+        for phrase in ("--post", "one work-item comment", "_http_post"):
+            self.assertIn(phrase, doc)
+
+    def test_it_does_not_overclaim_the_round_trip(self):
+        doc = ac.__doc__.lower()
+        for overclaim in ("guarantees the marker survives",
+                          "re-run this command to recover",
+                          "verified against a live"):
+            self.assertNotIn(overclaim, doc)
+
+    def test_it_still_states_the_read_lanes_structural_guarantee(self):
+        self.assertIn("no `data` parameter", ac.__doc__)
+
+
 class TestMain(unittest.TestCase):
     ENV = {"ADO_ORG_URL": "https://dev.azure.com/contoso", "ADO_PAT": "tok"}
 
     def test_resolve_prints_the_record_as_json_and_exits_zero(self):
         record = {"org": "contoso", "project": "P", "id": "1234"}
diff --git a/scripts/coverage_omit.txt b/scripts/coverage_omit.txt
index 8fdcca1..5718594 100644
--- a/scripts/coverage_omit.txt
+++ b/scripts/coverage_omit.txt
@@ -29,10 +29,11 @@
 #
 # Plugin scripts live in plugins/spec-loop/scripts/ but keys stay
 # scripts/<name>.py because measure_coverage.normalize_key canonicalizes either
 # scripts dir.
 
+scripts/ado_client.py:__main__           # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/ado_intake.py:__main__           # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/dag.py:__main__                  # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/dashboard_launcher.py:__main__   # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/dashboard_server.py:__main__     # process-entry shim; the module is imported, not run as __main__, under unittest
 scripts/jira_client.py:__main__          # process-entry shim; the module is imported, not run as __main__, under unittest
diff --git a/scripts/measure_coverage.py b/scripts/measure_coverage.py
index 4820321..1c5699a 100644
--- a/scripts/measure_coverage.py
+++ b/scripts/measure_coverage.py
@@ -97,10 +97,11 @@ MAX_SHIM_LINES = 5
 
 _MAIN_SHIM_RE = re.compile(r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:")
 
 # Product modules that count toward coverage (basename -> relpath key).
 TARGET_FILES = (
+    "scripts/ado_client.py",
     "scripts/ado_intake.py",
     "scripts/dag.py",
     "scripts/dashboard_launcher.py",
     "scripts/dashboard_server.py",
     "scripts/jira_client.py",
@@ -140,10 +141,11 @@ TARGET_MODULES = tuple(Path(t).stem for t in TARGET_FILES)
 # ~85.4% (roughly 40 lines that go unhit on 3.12 but are hit locally); its floor is
 # set from THAT lower figure minus the margin (a real, healthy floor — not a bug,
 # and not chased in this slice), not from the optimistic local 100%. The TOTAL floor
 # likewise sits well under the py3.12 aggregate that pr_resolver drags down.
 PER_FILE_FLOORS = {
+    "scripts/ado_client.py": 94,           # local 99.2% (2026-09-14) - >=5
     "scripts/ado_intake.py": 91,           # local 96.3% (2026-09-14) - >=5
     "scripts/dag.py": 94,                  # local 99.8% (2026-07-30) - 5
     "scripts/dashboard_launcher.py": 95,   # local 100% - 5
     "scripts/dashboard_server.py": 94,     # local 99.5% (2026-07-30) - 5
     "scripts/jira_client.py": 94,          # local 99.5% (2026-09-09) - >=5 (CI py3.12 co_lines drift margin)
