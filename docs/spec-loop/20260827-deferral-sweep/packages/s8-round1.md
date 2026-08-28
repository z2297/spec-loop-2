# Review package: 299f0dbd1f700f8f3b3991ea7d601df797dd3749..7c0c0e0  (context: -U5)

## Commits
7c0c0e0 CHANGELOG: state escalation identity as the raw fields it now compares
e5fd0b0 run_state: identity from the raw record, carried as a fingerprint anchor
27e65b4 run_state: an unreadable escalations.md aborts instead of being replaced
1ee227f test_run_state: keep the four functions this slice touched at a legal nesting depth
c1876c8 run_state: narrow append_event to two parameters via a pure build_event
a7b4812 run_state: flatten append_event's deep continuation lines for the quality gate
8c05066 test_run_state: cite the fail-closed trigger check by behaviour, not a line number
3c55d7c test_run_state: keep the corpus replay flat for the quality gate
dc857b5 escalations.md: pin the de-duplication against the two recorded runs
e6ae844 run_state: say in _answer_target why the newest open round wins
ea4f74c run_state: keep the answer write-back flat and short for the quality gate
7b0eeda escalations.md: write an answer into the round that is still open
6cc73c5 escalations.md: one section per distinct question in append_event
3401870 run_state: keep _section_line flat for the quality gate
005be80 escalations.md: pure identity-based section placement

## Files changed
 CHANGELOG.md                                |  20 +
 plugins/spec-loop/scripts/run_state.py      | 298 ++++++++++---
 plugins/spec-loop/scripts/test_run_state.py | 624 +++++++++++++++++++++++++---
 3 files changed, 826 insertions(+), 116 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"CHANGELOG.md": [
[
10,
29
]
],
"plugins/spec-loop/scripts/run_state.py": [
[
10,
11
],
[
29,
33
],
[
62,
62
],
[
99,
103
],
[
178,
193
],
[
486,
501
],
[
503,
509
],
[
511,
525
],
[
529,
531
],
[
533,
533
],
[
537,
538
],
[
540,
542
],
[
543,
543
],
[
545,
555
],
[
557,
632
],
[
635,
644
],
[
647,
647
],
[
652,
667
],
[
986,
1028
],
[
1030,
1035
],
[
1037,
1037
],
[
1039,
1039
],
[
1041,
1042
],
[
1180,
1180
],
[
1239,
1240
]
],
"plugins/spec-loop/scripts/test_run_state.py": [
[
88,
101
],
[
214,
216
],
[
379,
526
],
[
563,
648
],
[
939,
944
],
[
946,
947
],
[
955,
959
],
[
962,
963
],
[
968,
969
],
[
975,
978
],
[
985,
991
],
[
993,
996
],
[
999,
1000
],
[
1008,
1012
],
[
1019,
1024
],
[
1028,
1030
],
[
1035,
1085
],
[
1087,
1088
],
[
1092,
1093
],
[
1096,
1097
],
[
1104,
1105
],
[
1115,
1115
],
[
1123,
1173
],
[
1327,
1330
],
[
1333,
1336
],
[
1376,
1378
],
[
1389,
1390
],
[
1393,
1505
],
[
1693,
1701
],
[
1704,
1708
],
[
1724,
1726
],
[
1784,
1784
],
[
1804,
1804
],
[
1810,
1814
]
]
}
```

## Diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 84b352f..b2bdb59 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -5,10 +5,30 @@ All notable changes to the spec-loop plugin are documented here. The format is
 [SemVer](https://semver.org/). History before 2.0.0 lives in the
 [v1 repository](https://github.com/z2297/spec-loop).
 
 ## [Unreleased]
 
+### Fixed
+- **`escalations.md` renders one section per distinct escalation question.** An
+  `escalation-opened` event whose raw `id`, `context` and `question` match a section already on
+  the page now rewrites that section in place (`run_state.place_escalation_section`) instead of
+  appending a second copy; a record differing in any of those three raw fields is a different
+  question and keeps its own section. Matching compares the fingerprint `escalation_identity`
+  takes from the raw record, carried on the page as a second HTML-comment anchor, so two rounds
+  whose contexts differ only past the renderer's truncation cap are still two questions.
+  Replaying run 20260825's recorded `events.jsonl` renders 9 sections where the committed
+  artifact has 12, and both rounds of the one id that genuinely re-escalated survive as separate
+  sections. Two behaviours are deliberately unchanged: `run_state.open_escalations()` still lists
+  every status-OPEN escalation, so de-duplicating the page never silences the human gate, and a
+  matching re-emit that carries no answer leaves an already-answered section untouched rather
+  than resetting it. `answer_escalation` now writes into the last section for an id that is still
+  marked `(status: OPEN)`, which is a no-op for an id owning a single section and stops the second
+  round's answer landing under the first round's question. Escalation ids still carry no round
+  component, so two rounds of one id remain distinguishable on the page only by their rendered
+  question and context, or — where those render identically — by the identity fingerprint comment
+  alone.
+
 ## [2.2.1] - 2026-08-27
 ### Added
 - **`internal-error` escalation trigger** — a seventh `EscalationRecord.trigger` value for machine
   failure, one string covering both shapes of it: an unhandled exception that aborted a slice
   (`workflows/slice-wave.workflow.js` — the catch-all at :892) and a slice that returned no result
diff --git a/plugins/spec-loop/scripts/run_state.py b/plugins/spec-loop/scripts/run_state.py
index e44150e..5b4548e 100644
--- a/plugins/spec-loop/scripts/run_state.py
+++ b/plugins/spec-loop/scripts/run_state.py
@@ -5,11 +5,12 @@ Every durable per-slice fact a wave produces enters run state through this
 script (shapes pinned in references/run-state-v2.md):
 
     slice-<id>-status.json   the tool-validated SliceResult sidecar
     events.jsonl             the append-only machine channel (run_metrics reads it)
     decisions-log.md         human render of decision/deferred/gate events
-    escalations.md           human render of EscalationRecords, answers written back
+    escalations.md           human render of EscalationRecords, one section per
+                             distinct question, answers written back
     slice-<id>-report.md     short human summary of one sidecar
 
 Design decisions:
 - **Validation is the gate, and it fails closed.** `persist-slice` validates the
   SliceResult against the sidecar contract BEFORE writing anything; an invalid
@@ -23,11 +24,15 @@ Design decisions:
   stamped `ts` is the controller's, consistently.
 - **One writer, one path.** All prose is rendered from the structured objects as
   a side effect of appending the event, so a fact can never reach events.jsonl
   without reaching the human surface (or vice versa). Nothing parses the prose
   back — `escalations.md` carries an HTML-comment id anchor purely so an answer
-  can be written back to the right entry deterministically.
+  can be written back to the right entry deterministically. An
+  `escalation-opened` whose raw id, context and question already appear on
+  the page rewrites that section instead of adding a second copy
+  (`place_escalation_section`); the machine channel keeps every event either
+  way, and the human gate reads `open_escalations`, not the page.
 - **The sidecar is the single home of per-slice facts.** `persist-slice` emits
   only events that have their own type in the contract (`council-verdict`,
   `review-summary`, `quality-gate`, `escalation-*`); it never re-emits the
   slice's own outcome — status, commits, tiers, counts, timings — as an event.
   Readers that want those read the sidecar, so there is nothing to drift.
@@ -52,10 +57,11 @@ Usage:
     run_state.py open-escalations  --run-dir <dir>
     run_state.py validate-sidecar  --run-dir <dir> --file <file|->
 """
 
 import argparse
+import hashlib
 import json
 import os
 import re
 import sys
 import tempfile
@@ -88,10 +94,15 @@ DECISIONS_HEADER = ("# Decisions log\n\n"
 ESCALATIONS_HEADER = ("# Escalations\n\n"
                       "Rendered from EscalationRecords; answers are written back "
                       "into the matching entry.\n\n")
 
 ID_ANCHOR = "<!-- escalation-id: %s -->"
+ID_ANCHOR_PREFIX = ID_ANCHOR.split("%s")[0]
+IDENTITY_ANCHOR = "<!-- escalation-identity: %s -->"
+_IDENTITY_RE = re.compile(r"<!-- escalation-identity: (\w+) -->")
+STATUS_OPEN_MARK = "(status: OPEN)"
+STATUS_ANSWERED_MARK = "(status: ANSWERED)"
 SUMMARY_LIMIT = 200
 # Payload keys, in priority order, that may carry a human-readable one-liner.
 # Module-level for the same reason as the messages below: a wrapped literal
 # inside _first_text's loop reads as nesting to the quality gate.
 SUMMARY_TEXT_KEYS = ("summary", "decision", "title", "question", "detail",
@@ -162,10 +173,26 @@ def _read_text(path):
             return fh.read()
     except OSError:
         return ""
 
 
+def _read_page(path):
+    """The text of an existing prose page, or None absent a file.
+
+    A page on disk that cannot be read raises RunStateError instead of
+    reporting empty text: a caller treating an unreadable page as an empty
+    one rewrites it from a bare header and drops every section already on it.
+    """
+    if not os.path.exists(path):
+        return None
+    try:
+        with open(path, "r", encoding="utf-8") as fh:
+            return fh.read()
+    except OSError as exc:
+        raise RunStateError("cannot read %s: %s" % (path, exc))
+
+
 def read_json(path):
     """Read a JSON object from a path, or from stdin when path is '-'."""
     try:
         if path == "-":
             return json.loads(sys.stdin.read())
@@ -454,60 +481,192 @@ def _ordered_options(record):
     options = [o for o in (record.get("options") or []) if isinstance(o, dict)]
     return ([o for o in options if o.get("recommended")]
             + [o for o in options if not o.get("recommended")])
 
 
+def escalation_identity(record):
+    """A fingerprint of the fields that identify one EscalationRecord (PURE).
+
+    Computed from the RAW id, context and question, whitespace-collapsed. A
+    context longer than the render cap makes a fingerprint taken from the
+    rendered lines merge distinct questions, so the raw fields are the only
+    sound source. Title, options, status and answer are deliberately
+    excluded: they may legitimately differ between a record and its own
+    re-emit.
+    """
+    keys = ("id", "context", "question")
+    fields = [" ".join(str(record.get(key) or "").split()) for key in keys]
+    joined = "\x1f".join(fields)
+    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
+
+
 def render_escalation(scope, record):
-    """Render one EscalationRecord as its escalations.md entry (PURE)."""
+    """Render one EscalationRecord as its escalations.md entry (PURE).
+
+    The section carries two HTML-comment anchors: the id anchor an answer is
+    written back through, and the identity fingerprint de-duplication
+    matches on (see `escalation_identity`). Body lines are appended one at a
+    time by this single producer of a section's bytes.
+    """
     status = record.get("status") or "OPEN"
-    lines = ["## [%s] %s   (status: %s)"
-             % (scope, _one_line(record.get("title") or "(untitled)"), status),
-             ID_ANCHOR % (record.get("id") or "?"),
-             "- Trigger: %s" % (record.get("trigger") or "(not recorded)"),
-             "- Opened: %s" % (record.get("opened") or "(not recorded)"),
-             "- Context: %s" % _one_line(record.get("context") or "(not recorded)", 400),
-             "- The decision: %s" % _one_line(record.get("question") or "(not recorded)",
-                                              400),
-             "- Options:"]
+    title = _one_line(record.get("title") or "(untitled)")
+    context = _one_line(record.get("context") or "(not recorded)", 400)
+    question = _one_line(record.get("question") or "(not recorded)", 400)
+    unanswered = _one_line(record.get("if_unanswered") or "(not recorded)", 300)
+    answer = record.get("answer")
+    answered_at = record.get("answered_at")
+    lines = []
+    lines.append("## [%s] %s   (status: %s)" % (scope, title, status))
+    lines.append(ID_ANCHOR % (record.get("id") or "?"))
+    lines.append(IDENTITY_ANCHOR % escalation_identity(record))
+    lines.append("- Trigger: %s" % (record.get("trigger") or "(not recorded)"))
+    lines.append("- Opened: %s" % (record.get("opened") or "(not recorded)"))
+    lines.append("- Context: %s" % context)
+    lines.append("- The decision: %s" % question)
+    lines.append("- Options:")
     for position, option in enumerate(_ordered_options(record)):
         marker = "(RECOMMENDED DEFAULT) " if option.get("recommended") else ""
         detail = _one_line(option.get("detail") or "", 300)
-        lines.append("  %d. %s — %s%s" % (position + 1, option.get("label"),
-                                          marker, detail))
-    lines.append("- If unanswered: %s"
-                 % _one_line(record.get("if_unanswered") or "(not recorded)", 300))
-    answer = record.get("answer")
+        label = option.get("label")
+        lines.append("  %d. %s — %s%s" % (position + 1, label, marker, detail))
+    lines.append("- If unanswered: %s" % unanswered)
     lines.append("- Answer:%s" % (" " + _one_line(answer, 400) if answer else ""))
-    lines.append("- Answered-at:%s"
-                 % (" " + record["answered_at"] if record.get("answered_at") else ""))
+    lines.append("- Answered-at:%s" % (" " + answered_at if answered_at else ""))
     return "\n".join(lines) + "\n\n"
 
 
-def answer_escalation(body, escalation_id, answer, answered_at):
-    """Write an answer into the matching escalations.md entry (PURE).
+def _escalation_sections(body):
+    """Split an escalations.md body into its head and its `## ` sections (PURE).
 
-    Returns (updated markdown, matched?). The entry is located by its id
-    anchor, so re-titled or reordered entries still resolve.
+    The head is everything before the first heading. Joining the head with
+    every section reproduces the input exactly, so one section can be
+    rewritten and every other stays byte-identical to its rendering.
     """
-    anchor = ID_ANCHOR % escalation_id
     lines = body.splitlines(True)
-    try:
-        at = next(i for i, line in enumerate(lines) if line.strip() == anchor)
-    except StopIteration:
-        return body, False
+    starts = [index for index, line in enumerate(lines) if line.startswith("## ")]
+    bounds = starts + [len(lines)]
+    head = "".join(lines[:starts[0]]) if starts else body
+    sections = ["".join(lines[bounds[i]:bounds[i + 1]]) for i in range(len(starts))]
+    return head, sections
+
+
+def _section_line(section, prefix):
+    """The section's first line starting with `prefix`, or "" (PURE)."""
+    return next((line for line in section.splitlines() if line.startswith(prefix)), "")
+
 
+def _section_identity(section):
+    """The identity fingerprint carried by a rendered section, or "" (PURE).
+
+    A section rendered before the fingerprint existed carries none and
+    yields the empty string, which equals no record's fingerprint. Such a
+    section is left exactly as it stands and a re-emit is appended beside it.
+    """
+    found = _IDENTITY_RE.search(section)
+    return found.group(1) if found else ""
+
+
+def _section_has_answer(section):
+    """True given a rendered Answer line that carries text (PURE)."""
+    line = _section_line(section, "- Answer:")
+    return bool(line[len("- Answer:"):].strip())
+
+
+def place_escalation_section(body, scope, record):
+    """The escalations.md body with `record` rendered exactly once (PURE).
+
+    De-duplication is by true identity alone: the fingerprint
+    `escalation_identity` takes from the record's raw id, context and
+    question. A record matching a section already on the page rewrites that
+    section in place, keeping its position, so a re-emitted escalation-opened
+    stops adding a second copy of the same question. A record differing in any
+    of those three raw fields is a different question and gets its own section
+    appended: no two questions are ever merged, and no recorded answer is ever
+    moved onto a question that did not receive it. One rule protects an
+    existing decision: a matching record carrying no answer of its own leaves
+    an already-answered section untouched, so a bare re-emit cannot blank an
+    answer or reset a status. This function decides rendering only. Whether the
+    human gate still sees the escalation is `open_escalations`, which is
+    deliberately separate and stays fail-safe.
+    """
+    section = render_escalation(scope, record)
+    head, sections = _escalation_sections(body)
+    identity = escalation_identity(record)
+    at = next((index for index, existing in enumerate(sections)
+               if _section_identity(existing) == identity), None)
+    if at is None:
+        return body + section
+    keep = _section_has_answer(sections[at]) and not _section_has_answer(section)
+    sections[at] = sections[at] if keep else section
+    return head + "".join(sections)
+
+
+def _anchor_section_is_open(lines, at):
+    """True given a heading above `lines[at]` still reading status OPEN (PURE)."""
+    above = reversed(lines[:at + 1])
+    heading = next((line for line in above if line.startswith("## ")), "")
+    return STATUS_OPEN_MARK in heading
+
+
+def _answer_target(lines, anchor):
+    """The anchor-line index an incoming answer belongs to, or None (PURE).
+
+    One id ordinarily owns one section, and that single occurrence is
+    returned, unchanged from before. An id owning several sections asked
+    several distinct questions (see `place_escalation_section`), and the answer
+    belongs to the last section still marked open, which is the round that is
+    waiting for one: `open_escalations` carries a single record per id,
+    replaced by each escalation-opened it reads, so the newest round is the
+    question the human was actually shown. An answer arriving once every
+    section is answered rewrites the first, as it always did.
+    """
+    hits = [index for index, line in enumerate(lines) if line.strip() == anchor]
+    still_open = [index for index in hits if _anchor_section_is_open(lines, index)]
+    return (still_open[-1:] or hits[:1] or [None])[0]
+
+
+def _mark_heading_answered(lines, at):
+    """Rewrite the nearest heading at or above index `at` to read ANSWERED.
+
+    Only the status mark changes, so a heading already reading ANSWERED and a
+    heading carrying any other status both survive untouched.
+    """
     for index in range(at, -1, -1):
         if lines[index].startswith("## "):
-            lines[index] = lines[index].replace("(status: OPEN)", "(status: ANSWERED)")
-            break
+            lines[index] = lines[index].replace(STATUS_OPEN_MARK, STATUS_ANSWERED_MARK)
+            return
+
+
+def _fill_answer_fields(lines, at, answer, answered_at):
+    """Rewrite the Answer and Answered-at lines of the section holding `at`.
+
+    The walk stops at the next heading, which keeps one answer inside the one
+    section it was written for.
+    """
     for index in range(at + 1, len(lines)):
         if lines[index].startswith("## "):
-            break
+            return
         if lines[index].startswith("- Answer:"):
             lines[index] = "- Answer: %s\n" % _one_line(answer or "", 400)
         elif lines[index].startswith("- Answered-at:"):
             lines[index] = "- Answered-at: %s\n" % answered_at
+
+
+def answer_escalation(body, escalation_id, answer, answered_at):
+    """Write an answer into the matching escalations.md entry (PURE).
+
+    Returns (updated markdown, matched?). The entry is located by its id
+    anchor, so re-titled or reordered entries still resolve. Where one id owns
+    several sections, the target is chosen by `_answer_target`.
+    """
+    anchor = ID_ANCHOR % escalation_id
+    lines = body.splitlines(True)
+    at = _answer_target(lines, anchor)
+    if at is None:
+        return body, False
+    _mark_heading_answered(lines, at)
+    _fill_answer_fields(lines, at, answer, answered_at)
     return "".join(lines), True
 
 
 def _summarize(event):
     """One-line human summary of an event payload (PURE).
@@ -822,33 +981,67 @@ def read_events(run_dir):
         if isinstance(event, dict):
             events.append(event)
     return events
 
 
-def append_event(run_dir, ts, scope, event_type, payload):
-    """Append one event and render it onto the human surface it belongs to."""
-    event = {"ts": ts, "scope": scope, "type": event_type,
-             "payload": payload if payload is not None else {}}
-    _append_text(events_path(run_dir),
-                 json.dumps(event, ensure_ascii=False, sort_keys=False) + "\n")
+def _place_escalation(run_dir, scope, record):
+    """Render one opened escalation onto escalations.md, once per question.
+
+    The whole page is rewritten atomically because placement may rewrite a
+    section that is already on it (see `place_escalation_section`). A missing
+    page starts from the header, so the first escalation of a run produces the
+    same bytes it always did.
+    """
+    path = os.path.join(run_dir, ESCALATIONS_MD)
+    page = _read_page(path)
+    # A read that failed has already raised. A genuinely 0-byte page has no
+    # section to lose, so it starts from the header, as an absent one does.
+    body = page or ESCALATIONS_HEADER
+    _atomic_write(path, place_escalation_section(body, scope, record))
+
+
+def build_event(ts, scope, event_type, payload):
+    """One event object, ready to append (PURE).
+
+    The four fields travel as one value, which keeps `append_event` at two
+    parameters. A null payload becomes an empty object, so a caller passing
+    nothing records the same shape as a caller passing an empty dict.
+    """
+    body = payload if payload is not None else {}
+    return {"ts": ts, "scope": scope, "type": event_type, "payload": body}
+
+
+def _answer_on_page(run_dir, event):
+    """Write one escalation-answered event into escalations.md.
+
+    An answer with no matching entry is appended as its own orphan entry, so
+    a recorded answer always reaches the page.
+    """
+    path = os.path.join(run_dir, ESCALATIONS_MD)
+    payload = event["payload"]
+    answered_at = payload.get("answered_at") or event["ts"]
+    body = _read_page(path) or ""
+    answer = payload.get("answer")
+    updated, matched = answer_escalation(body, payload.get("id"), answer, answered_at)
+    if matched:
+        _atomic_write(path, updated)
+    else:
+        _append_text(path, _orphan_answer_entry(event), ESCALATIONS_HEADER)
 
+
+def append_event(run_dir, event):
+    """Append one event and render it onto the human surface it belongs to."""
+    line = json.dumps(event, ensure_ascii=False, sort_keys=False) + "\n"
+    _append_text(events_path(run_dir), line)
+    event_type = event["type"]
     if event_type == "escalation-opened":
-        _append_text(os.path.join(run_dir, ESCALATIONS_MD),
-                     render_escalation(scope, event["payload"]), ESCALATIONS_HEADER)
+        _place_escalation(run_dir, event["scope"], event["payload"])
     elif event_type == "escalation-answered":
-        path = os.path.join(run_dir, ESCALATIONS_MD)
-        body = _read_text(path)
-        updated, matched = answer_escalation(
-            body, event["payload"].get("id"), event["payload"].get("answer"),
-            event["payload"].get("answered_at") or ts)
-        if matched:
-            _atomic_write(path, updated)
-        else:
-            _append_text(path, _orphan_answer_entry(event), ESCALATIONS_HEADER)
+        _answer_on_page(run_dir, event)
     elif event_type in DECISION_EVENTS:
-        _append_text(os.path.join(run_dir, DECISIONS_LOG),
-                     decision_line(event) + "\n", DECISIONS_HEADER)
+        decision = decision_line(event) + "\n"
+        _append_text(os.path.join(run_dir, DECISIONS_LOG), decision, DECISIONS_HEADER)
     return event
 
 
 def open_escalations(run_dir):
     """Every escalation opened and not yet answered, in the order opened."""
@@ -982,11 +1175,11 @@ def persist_slice(run_dir, body, wave, ts):
     sidecar_path = os.path.join(run_dir, "slice-%s-status.json" % slice_id)
     _atomic_write(sidecar_path, json.dumps(body, ensure_ascii=False, indent=2) + "\n")
 
     emitted = []
     for scope, event_type, payload in _slice_events(body, ts, slice_id):
-        append_event(run_dir, ts, scope, event_type, payload)
+        append_event(run_dir, build_event(ts, scope, event_type, payload))
         emitted.append(event_type)
 
     report_path = os.path.join(run_dir, "slice-%s-report.md" % slice_id)
     _atomic_write(report_path, render_report(body))
 
@@ -1041,11 +1234,12 @@ def _run(args):
         return persist_slice(args.run_dir, body, args.wave, args.ts), 0
 
     if args.command == "append-event":
         _require_ts(args.ts)
         payload = _payload_arg(args.payload)
-        return append_event(args.run_dir, args.ts, args.scope, args.type, payload), 0
+        event = build_event(args.ts, args.scope, args.type, payload)
+        return append_event(args.run_dir, event), 0
 
     if args.command == "open-escalations":
         return open_escalations(args.run_dir), 0
 
     errors = validate_sidecar(read_json(args.file))
diff --git a/plugins/spec-loop/scripts/test_run_state.py b/plugins/spec-loop/scripts/test_run_state.py
index a6aaff6..3f32b98 100644
--- a/plugins/spec-loop/scripts/test_run_state.py
+++ b/plugins/spec-loop/scripts/test_run_state.py
@@ -83,10 +83,24 @@ def sidecar(status="DONE", **over):
         body["escalations"] = [escalation()]
     body.update(over)
     return body
 
 
+def refuse_reads(blocked_path):
+    """A builtins.open replacement that raises OSError on a read of one path."""
+    real_open = open
+    blocked = os.path.abspath(str(blocked_path))
+
+    def guard(target, mode="r", *args, **kwargs):
+        hit = os.path.abspath(str(target)) == blocked
+        if hit and "r" in mode:
+            raise OSError(5, "simulated I/O error")
+        return real_open(target, mode, *args, **kwargs)
+
+    return guard
+
+
 # --------------------------------------------------------------------------
 # validate_sidecar — pure, fail-closed
 # --------------------------------------------------------------------------
 
 class TestValidateSidecar(unittest.TestCase):
@@ -195,12 +209,13 @@ class TestValidateSidecar(unittest.TestCase):
     def test_escalation_trigger_enum(self):
         body = sidecar("ESCALATED", escalations=[escalation(trigger="vibes")])
         self.assertMentions(body, "trigger")
 
     def test_escalation_trigger_accepts_internal_error(self):
-        # A machine failure is a first-class trigger: run_state.py:204 is
-        # fail-closed, so an unlisted value would falsely fail the sidecar.
+        # A machine failure is a first-class trigger: validate_escalation's
+        # membership check against ESCALATION_TRIGGERS is fail-closed, so an
+        # unlisted value would falsely fail the sidecar.
         body = sidecar("ESCALATED", escalations=[
             escalation(id="s1:internal-error", trigger="internal-error")])
         self.assertValid(body)
 
     def test_escalation_trigger_still_rejects_a_bogus_value(self):
@@ -359,10 +374,158 @@ class TestRenderEscalation(unittest.TestCase):
         body = rs.render_escalation("s1", record)
         self.assertIn("(status: ANSWERED)", body)
         self.assertIn("- Answer: bound them", body)
         self.assertIn("- Answered-at: %s" % LATER, body)
 
+    def test_the_identity_fingerprint_is_embedded_for_de_duplication(self):
+        body = rs.render_escalation("s1", escalation())
+        anchor = rs.IDENTITY_ANCHOR % rs.escalation_identity(escalation())
+        self.assertIn(anchor, body)
+
+
+class TestPlaceEscalationSection(unittest.TestCase):
+    """place_escalation_section: one section per distinct question."""
+
+    def sections(self, body):
+        return [line for line in body.splitlines() if line.startswith("## ")]
+
+    def test_an_empty_page_gains_the_section(self):
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        self.assertEqual(len(self.sections(body)), 1)
+        self.assertTrue(body.startswith(rs.ESCALATIONS_HEADER))
+
+    def test_an_identical_re_emit_replaces_rather_than_appends(self):
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        again = rs.place_escalation_section(body, "s1", escalation())
+        self.assertEqual(len(self.sections(again)), 1)
+        self.assertEqual(again, body)
+
+    def test_a_different_context_under_the_same_id_gets_its_own_section(self):
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        second = escalation(context="A different incident with its own decision.")
+        again = rs.place_escalation_section(body, "s1", second)
+        self.assertEqual(len(self.sections(again)), 2)
+        self.assertIn("A different incident", again)
+
+    def test_a_different_question_under_the_same_id_gets_its_own_section(self):
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        second = escalation(question="Something else entirely?")
+        again = rs.place_escalation_section(body, "s1", second)
+        self.assertEqual(len(self.sections(again)), 2)
+
+    def test_a_different_id_gets_its_own_section(self):
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        again = rs.place_escalation_section(body, "s1", escalation(id="s1:ambiguity"))
+        self.assertEqual(len(self.sections(again)), 2)
+
+    def test_a_re_emit_without_an_answer_leaves_a_recorded_answer_standing(self):
+        answered = escalation(status="ANSWERED", answer="bound them", answered_at=LATER)
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", answered)
+        again = rs.place_escalation_section(body, "s1", escalation())
+        self.assertEqual(again, body)
+        self.assertIn("- Answer: bound them", again)
+        self.assertIn("(status: ANSWERED)", again)
+
+    def test_a_re_emit_carrying_an_answer_updates_the_section_in_place(self):
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        answered = escalation(status="ANSWERED", answer="bound them", answered_at=LATER)
+        again = rs.place_escalation_section(body, "s1", answered)
+        self.assertEqual(len(self.sections(again)), 1)
+        self.assertIn("- Answer: bound them", again)
+
+    def test_replacement_keeps_the_original_position(self):
+        first = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        both = rs.place_escalation_section(first, "s2", escalation(id="s2:ambiguity"))
+        answered = escalation(status="ANSWERED", answer="bound them", answered_at=LATER)
+        final = rs.place_escalation_section(both, "s1", answered)
+        self.assertEqual(len(self.sections(final)), 2)
+        self.assertIn("[s1]", self.sections(final)[0])
+        self.assertIn("[s2]", self.sections(final)[1])
+
+    def test_the_anchor_prefix_comes_from_the_anchor_template(self):
+        self.assertEqual(rs.ID_ANCHOR_PREFIX, rs.ID_ANCHOR.split("%s")[0])
+
+    def test_splitting_a_page_is_lossless(self):
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        body = rs.place_escalation_section(body, "s2", escalation(id="s2:ambiguity"))
+        head, sections = rs._escalation_sections(body)
+        self.assertEqual(head + "".join(sections), body)
+        self.assertEqual(len(sections), 2)
+
+    def test_a_page_with_no_sections_splits_to_no_sections(self):
+        head, sections = rs._escalation_sections(rs.ESCALATIONS_HEADER)
+        self.assertEqual(head, rs.ESCALATIONS_HEADER)
+        self.assertEqual(sections, [])
+
+    def test_two_rounds_sharing_a_truncated_render_are_still_two_questions(self):
+        # The renderer caps context at 400 characters, so these two rounds
+        # render one identical Context line. They are distinct questions and
+        # each keeps its own section: identity comes from the raw record.
+        shared = "x" * 450
+        first = escalation(context=shared + " tail one")
+        second = escalation(context=shared + " tail two")
+        line_one = rs._section_line(rs.render_escalation("s1", first), "- Context:")
+        line_two = rs._section_line(rs.render_escalation("s1", second), "- Context:")
+        self.assertEqual(line_one, line_two)
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", first)
+        body = rs.place_escalation_section(body, "s1", second)
+        self.assertEqual(len(self.sections(body)), 2)
+        self.assertIn(rs.IDENTITY_ANCHOR % rs.escalation_identity(first), body)
+        self.assertIn(rs.IDENTITY_ANCHOR % rs.escalation_identity(second), body)
+
+    def test_the_two_sections_are_distinguishable_only_by_the_fingerprint(self):
+        # A documented consequence of raw-field identity: a human reading
+        # the page sees two sections with one id and byte-identical Context
+        # lines, told apart only by the fingerprint comment.
+        shared = "y" * 450
+        first = escalation(context=shared + " tail one")
+        second = escalation(context=shared + " tail two")
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", first)
+        body = rs.place_escalation_section(body, "s1", second)
+        head, sections = rs._escalation_sections(body)
+        self.assertEqual(len(sections), 2)
+        anchors = [rs._section_line(item, rs.ID_ANCHOR_PREFIX) for item in sections]
+        self.assertEqual(anchors[0], anchors[1])
+        contexts = [rs._section_line(item, "- Context:") for item in sections]
+        self.assertEqual(contexts[0], contexts[1])
+        prints = [rs._section_identity(item) for item in sections]
+        self.assertNotEqual(prints[0], prints[1])
+
+    def test_identity_comes_from_the_raw_id_context_and_question(self):
+        text = ("  The reviewer   says retries must be "
+                "bounded; the plan says otherwise.  ")
+        record = escalation()
+        base = rs.escalation_identity(record)
+        self.assertEqual(base, rs.escalation_identity(dict(record)))
+        self.assertNotEqual(base, rs.escalation_identity(escalation(id="s2:x")))
+        other = escalation(question="Something else")
+        self.assertNotEqual(base, rs.escalation_identity(other))
+        self.assertEqual(base, rs.escalation_identity(escalation(context=text)))
+
+    def test_a_section_without_a_fingerprint_is_never_rewritten(self):
+        legacy = (rs.ESCALATIONS_HEADER
+                  + "## [s1] Older render   (status: OPEN)\n"
+                  + (rs.ID_ANCHOR % "s1:review-block") + "\n"
+                  + "- Context: whatever\n- The decision: whatever\n"
+                  + "- Answer:\n- Answered-at:\n\n")
+        body = rs.place_escalation_section(legacy, "s1", escalation())
+        self.assertEqual(len(self.sections(body)), 2)
+        self.assertIn("## [s1] Older render   (status: OPEN)", body)
+
+    def test_the_back_compat_prose_readers_still_split_the_page(self):
+        # Both back-compat prose readers key a block only on a line starting
+        # "## [" and read body fields by a "- " prefix, so the new anchor
+        # line is inert to them, exactly as the id anchor already is.
+        import run_metrics
+        first = escalation()
+        second = escalation(id="s2:ambiguity")
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", first)
+        body = rs.place_escalation_section(body, "s2", second)
+        self.assertIn(rs.IDENTITY_ANCHOR % rs.escalation_identity(first), body)
+        parsed = run_metrics.legacy_parse_escalations(body)
+        self.assertEqual([item["id"] for item in parsed], ["s1", "s2"])
+
 
 class TestAnswerWriteBack(unittest.TestCase):
     def setUp(self):
         self.body = (rs.ESCALATIONS_HEADER
                      + rs.render_escalation("s1", escalation())
@@ -395,10 +558,96 @@ class TestAnswerWriteBack(unittest.TestCase):
     def test_multiline_answer_is_collapsed(self):
         updated, _ = rs.answer_escalation(self.body, "s1:review-block",
                                           "do this\nthen that", LATER)
         self.assertIn("- Answer: do this then that", updated)
 
+    ROUND_ID = "s3:budget-exhausted"
+
+    def round_record(self, context):
+        return escalation(id=self.ROUND_ID, trigger="budget-exhausted", context=context)
+
+    def two_rounds(self):
+        """Two distinct rounds of one id placed back to back, both still open."""
+        first = rs.place_escalation_section(
+            rs.ESCALATIONS_HEADER, "s3",
+            self.round_record("undefined is not an object"))
+        return rs.place_escalation_section(
+            first, "s3", self.round_record("StructuredOutput retry cap"))
+
+    def rounds_answered_in_order(self):
+        """The page the recorded event stream builds: open, answer, open, answer.
+
+        Run 20260825 recorded exactly this order for its one id that
+        re-escalated on a genuinely new incident, so this is the shape the
+        answer targeting has to get right.
+        """
+        body = rs.place_escalation_section(
+            rs.ESCALATIONS_HEADER, "s3",
+            self.round_record("undefined is not an object"))
+        body, first = rs.answer_escalation(body, self.ROUND_ID, "first ruling", TS)
+        body = rs.place_escalation_section(
+            body, "s3", self.round_record("StructuredOutput retry cap"))
+        body, second = rs.answer_escalation(
+            body, self.ROUND_ID, "genuine agent failure this time", LATER)
+        self.assertEqual([first, second], [True, True])
+        return body
+
+    def test_an_answer_lands_on_the_round_still_open(self):
+        head, sections = rs._escalation_sections(self.rounds_answered_in_order())
+        self.assertEqual(len(sections), 2)
+        self.assertIn("undefined is not an object", sections[0])
+        self.assertIn("- Answer: first ruling", sections[0])
+        self.assertIn("StructuredOutput retry cap", sections[1])
+        self.assertIn("- Answer: genuine agent failure this time", sections[1])
+
+    def test_both_rounds_end_answered(self):
+        body = self.rounds_answered_in_order()
+        self.assertEqual(body.count(rs.STATUS_ANSWERED_MARK), 2)
+        self.assertEqual(body.count(rs.STATUS_OPEN_MARK), 0)
+
+    def test_a_re_answer_after_everything_is_answered_rewrites_the_first(self):
+        body, matched = rs.answer_escalation(
+            self.rounds_answered_in_order(), self.ROUND_ID, "c", LATER)
+        self.assertTrue(matched)
+        head, sections = rs._escalation_sections(body)
+        self.assertIn("- Answer: c", sections[0])
+        self.assertIn("- Answer: genuine agent failure this time", sections[1])
+
+    def test_two_rounds_open_at_once_hand_the_answer_to_the_newest(self):
+        # Two rounds of one id sit open at the same time only through a gap in
+        # the event stream. `open_escalations` keeps a single record per id,
+        # replaced by each escalation-opened, so the question the human was
+        # actually shown is the newest one, and the newest still-open section
+        # is the one an arriving answer belongs to. The older section keeps its
+        # own question and stays visibly unanswered rather than borrowing an
+        # answer it did not receive.
+        body, matched = rs.answer_escalation(
+            self.two_rounds(), self.ROUND_ID, "one ruling", LATER)
+        self.assertTrue(matched)
+        head, sections = rs._escalation_sections(body)
+        self.assertIn("- Answer: one ruling", sections[1])
+        self.assertIn(rs.STATUS_ANSWERED_MARK, rs._section_line(sections[1], "## "))
+        self.assertEqual(rs._section_has_answer(sections[0]), False)
+        self.assertIn(rs.STATUS_OPEN_MARK, rs._section_line(sections[0], "## "))
+
+    def test_a_single_section_page_is_unaffected(self):
+        page = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        body, matched = rs.answer_escalation(page, "s1:review-block", "bound them", LATER)
+        self.assertTrue(matched)
+        self.assertIn("- Answer: bound them", body)
+        self.assertIn(rs.STATUS_ANSWERED_MARK, body)
+
+    def test_an_unknown_id_still_does_not_match(self):
+        page = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", escalation())
+        body, matched = rs.answer_escalation(page, "s1:ghost", "x", LATER)
+        self.assertFalse(matched)
+        self.assertEqual(body, page)
+
+    def test_the_status_marks_are_the_ones_the_renderer_writes(self):
+        page = rs.render_escalation("s1", escalation())
+        self.assertIn(rs.STATUS_OPEN_MARK, page)
+
 
 class TestDecisionLine(unittest.TestCase):
     def line(self, event_type, payload, scope="s1"):
         return rs.decision_line({"ts": TS, "scope": scope, "type": event_type,
                                  "payload": payload})
@@ -685,120 +934,245 @@ class TestRunDirGuard(RunStateTestCase):
         self.assertEqual(code, 0, err)
         self.assertIsNotNone(self.read("events.jsonl"))
 
 
 class TestAppendEvent(RunStateTestCase):
+    def test_build_event_defaults_a_null_payload(self):
+        event = rs.build_event(TS, "run", "run-created", None)
+        expected = {"ts": TS, "scope": "run", "type": "run-created", "payload": {}}
+        self.assertEqual(event, expected)
+        self.assertEqual(list(event), ["ts", "scope", "type", "payload"])
+
     def test_creates_events_jsonl(self):
-        rs.append_event(self.run_dir, TS, "run", "run-created", {"run_id": "x"})
+        event = rs.build_event(TS, "run", "run-created", {"run_id": "x"})
+        rs.append_event(self.run_dir, event)
         lines = self.read("events.jsonl").splitlines()
         self.assertEqual(len(lines), 1)
         self.assertEqual(json.loads(lines[0]), {
             "ts": TS, "scope": "run", "type": "run-created",
             "payload": {"run_id": "x"}})
 
     def test_appends_in_order(self):
-        rs.append_event(self.run_dir, TS, "run", "run-created", {})
-        rs.append_event(self.run_dir, LATER, "wave1", "wave-dispatched", {"index": 1})
-        self.assertEqual([e["type"] for e in self.events()],
-                         ["run-created", "wave-dispatched"])
+        rs.append_event(self.run_dir, rs.build_event(TS, "run", "run-created", {}))
+        event = rs.build_event(LATER, "wave1", "wave-dispatched", {"index": 1})
+        rs.append_event(self.run_dir, event)
+        types = [e["type"] for e in self.events()]
+        self.assertEqual(types, ["run-created", "wave-dispatched"])
 
     def test_unrendered_event_writes_no_prose(self):
-        rs.append_event(self.run_dir, TS, "wave1", "wave-dispatched", {"index": 1})
+        event = rs.build_event(TS, "wave1", "wave-dispatched", {"index": 1})
+        rs.append_event(self.run_dir, event)
         self.assertIsNone(self.read("decisions-log.md"))
         self.assertIsNone(self.read("escalations.md"))
 
     def test_decision_event_renders_a_log_line(self):
-        rs.append_event(self.run_dir, TS, "s1", "decision",
-                        {"summary": "reuse the CSV writer"})
+        event = rs.build_event(TS, "s1", "decision", {"summary": "reuse the CSV writer"})
+        rs.append_event(self.run_dir, event)
         body = self.read("decisions-log.md")
         self.assertIn("# Decisions log", body)
         self.assertIn("[s1] DECISION: reuse the CSV writer — AT: %s" % TS, body)
 
     def test_decision_log_is_append_only(self):
-        rs.append_event(self.run_dir, TS, "s1", "decision", {"summary": "one"})
-        rs.append_event(self.run_dir, LATER, "s2", "deferred", {"summary": "two"})
+        event = rs.build_event(TS, "s1", "decision", {"summary": "one"})
+        rs.append_event(self.run_dir, event)
+        event = rs.build_event(LATER, "s2", "deferred", {"summary": "two"})
+        rs.append_event(self.run_dir, event)
         body = self.read("decisions-log.md")
         self.assertIn("one", body)
         self.assertIn("two", body)
         self.assertEqual(body.count("# Decisions log"), 1)
 
     def test_every_gate_event_type_is_logged(self):
-        for index, event_type in enumerate(
-                ("decision", "deferred", "council-verdict", "quality-gate",
-                 "integration-check", "phase5-gate")):
-            rs.append_event(self.run_dir, TS, "s%d" % index, event_type,
-                            {"summary": "s", "verdict": "ENDORSE", "status": "PASS",
-                             "result": "PASS"})
+        payload = {"summary": "s", "verdict": "ENDORSE", "status": "PASS",
+                   "result": "PASS"}
+        emitted = ("decision", "deferred", "council-verdict", "quality-gate",
+                   "integration-check", "phase5-gate")
+        for index, event_type in enumerate(emitted):
+            event = rs.build_event(TS, "s%d" % index, event_type, payload)
+            rs.append_event(self.run_dir, event)
         body = self.read("decisions-log.md")
-        for event_type in ("DECISION", "DEFERRED", "COUNCIL-VERDICT",
-                           "QUALITY-GATE", "INTEGRATION-CHECK", "PHASE5-GATE"):
-            self.assertIn(event_type, body)
+        logged = ("DECISION", "DEFERRED", "COUNCIL-VERDICT", "QUALITY-GATE",
+                  "INTEGRATION-CHECK", "PHASE5-GATE")
+        for marker in logged:
+            self.assertIn(marker, body)
 
     def test_escalation_opened_writes_a_full_entry(self):
-        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
         body = self.read("escalations.md")
         self.assertIn("# Escalations", body)
         self.assertIn("(status: OPEN)", body)
         self.assertIn("- The decision: Bound the retries", body)
         self.assertIsNone(self.read("decisions-log.md"))
 
     def test_escalation_answered_fills_in_the_entry(self):
-        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
-        rs.append_event(self.run_dir, LATER, "s1", "escalation-answered",
-                        {"id": "s1:review-block", "answer": "bound them"})
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        payload = {"id": "s1:review-block", "answer": "bound them"}
+        event = rs.build_event(LATER, "s1", "escalation-answered", payload)
+        rs.append_event(self.run_dir, event)
         body = self.read("escalations.md")
         self.assertIn("- Answer: bound them", body)
         self.assertIn("- Answered-at: %s" % LATER, body)
         self.assertIn("(status: ANSWERED)", body)
 
     def test_escalation_answered_honours_an_explicit_answered_at(self):
-        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
-        rs.append_event(self.run_dir, LATER, "s1", "escalation-answered",
-                        {"id": "s1:review-block", "answer": "x",
-                         "answered_at": "2026-08-01T00:00:00Z"})
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        payload = {"id": "s1:review-block", "answer": "x",
+                   "answered_at": "2026-08-01T00:00:00Z"}
+        event = rs.build_event(LATER, "s1", "escalation-answered", payload)
+        rs.append_event(self.run_dir, event)
         self.assertIn("- Answered-at: 2026-08-01T00:00:00Z", self.read("escalations.md"))
 
     def test_orphan_answer_is_still_surfaced(self):
-        rs.append_event(self.run_dir, LATER, "s1", "escalation-answered",
-                        {"id": "s1:ghost", "answer": "whatever"})
+        payload = {"id": "s1:ghost", "answer": "whatever"}
+        event = rs.build_event(LATER, "s1", "escalation-answered", payload)
+        rs.append_event(self.run_dir, event)
         body = self.read("escalations.md")
         self.assertIn("s1:ghost", body)
         self.assertIn("whatever", body)
 
+    def sections(self, body):
+        return [line for line in body.splitlines() if line.startswith("## ")]
+
+    def test_an_identical_re_open_does_not_add_a_second_section(self):
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        event = rs.build_event(LATER, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        body = self.read("escalations.md")
+        self.assertEqual(len(self.sections(body)), 1)
+        self.assertEqual(body.count(rs.ID_ANCHOR % "s1:review-block"), 1)
+
+    def test_both_re_opens_stay_in_the_event_log(self):
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        event = rs.build_event(LATER, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        types = [event["type"] for event in self.events()]
+        self.assertEqual(types.count("escalation-opened"), 2)
+
+    def test_a_new_incident_under_one_id_gets_its_own_section(self):
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        second = escalation(context="Genuine agent failure this time.")
+        event = rs.build_event(LATER, "s1", "escalation-opened", second)
+        rs.append_event(self.run_dir, event)
+        body = self.read("escalations.md")
+        self.assertEqual(len(self.sections(body)), 2)
+        self.assertIn("Genuine agent failure this time", body)
+
+    def test_a_bare_re_open_never_blanks_a_recorded_answer(self):
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        answer_payload = {"id": "s1:review-block", "answer": "bound them"}
+        event = rs.build_event(LATER, "s1", "escalation-answered", answer_payload)
+        rs.append_event(self.run_dir, event)
+        event = rs.build_event(LATER, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        body = self.read("escalations.md")
+        self.assertEqual(len(self.sections(body)), 1)
+        self.assertIn("- Answer: bound them", body)
+        self.assertIn("(status: ANSWERED)", body)
+
+    def test_the_header_is_written_once(self):
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        second = escalation(id="s2:ambiguity")
+        event = rs.build_event(LATER, "s2", "escalation-opened", second)
+        rs.append_event(self.run_dir, event)
+        self.assertEqual(self.read("escalations.md").count("# Escalations"), 1)
+
     def test_events_survive_a_prose_render(self):
-        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
         self.assertEqual([e["type"] for e in self.events()], ["escalation-opened"])
 
     def test_malformed_lines_are_skipped_by_the_reader(self):
-        rs.append_event(self.run_dir, TS, "s1", "decision", {"summary": "ok"})
+        event = rs.build_event(TS, "s1", "decision", {"summary": "ok"})
+        rs.append_event(self.run_dir, event)
         with open(os.path.join(self.run_dir, "events.jsonl"), "a", encoding="utf-8") as fh:
             fh.write("{half written\n")
-        rs.append_event(self.run_dir, LATER, "s1", "decision", {"summary": "also ok"})
+        event = rs.build_event(LATER, "s1", "decision", {"summary": "also ok"})
+        rs.append_event(self.run_dir, event)
         self.assertEqual(len(self.events()), 2)
 
     def test_reader_tolerates_a_missing_file(self):
         self.assertEqual(rs.read_events(self.run_dir), [])
 
     def test_reader_skips_blank_lines(self):
-        rs.append_event(self.run_dir, TS, "s1", "decision", {"summary": "ok"})
+        event = rs.build_event(TS, "s1", "decision", {"summary": "ok"})
+        rs.append_event(self.run_dir, event)
         with open(os.path.join(self.run_dir, "events.jsonl"), "a", encoding="utf-8") as fh:
             fh.write("\n\n")
         self.assertEqual(len(self.events()), 1)
 
     def test_unwritable_run_dir_is_a_run_state_error(self):
         blocked = os.path.join(self.root, "not-a-dir")
         with open(blocked, "w", encoding="utf-8") as fh:
             fh.write("x")
         with self.assertRaises(rs.RunStateError):
-            rs.append_event(blocked, TS, "run", "run-created", {})
+            rs.append_event(blocked, rs.build_event(TS, "run", "run-created", {}))
 
     def test_sidecar_write_failure_is_a_run_state_error(self):
         with mock.patch.object(rs.os, "replace", side_effect=OSError("read-only")):
             with self.assertRaises(rs.RunStateError):
                 rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
 
 
+class TestEscalationPageReadFailure(RunStateTestCase):
+    """A page on disk that cannot be read must never be rewritten.
+
+    Regression: placement read the page through a reader that reported an
+    OSError as empty text, so a page holding three sections was replaced by
+    a fresh header plus one section and nothing was raised.
+    """
+
+    def sections(self, body):
+        return [line for line in body.splitlines() if line.startswith("## ")]
+
+    def open_three(self):
+        for index in (1, 2, 3):
+            record = escalation(
+                id="s%d:review-block" % index,
+                context="Round %d context." % index)
+            event = rs.build_event(TS, "s%d" % index, "escalation-opened", record)
+            rs.append_event(self.run_dir, event)
+
+    def page_path(self):
+        return os.path.join(self.run_dir, rs.ESCALATIONS_MD)
+
+    def test_a_page_that_cannot_be_read_is_not_replaced(self):
+        self.open_three()
+        before = self.read("escalations.md")
+        self.assertEqual(len(self.sections(before)), 3)
+        record = escalation(id="s4:ambiguity")
+        event = rs.build_event(LATER, "s4", "escalation-opened", record)
+        guard = refuse_reads(self.page_path())
+        with mock.patch("builtins.open", guard), self.assertRaises(rs.RunStateError):
+            rs.append_event(self.run_dir, event)
+        self.assertEqual(self.read("escalations.md"), before)
+
+    def test_an_unreadable_page_does_not_swallow_an_answer_either(self):
+        self.open_three()
+        before = self.read("escalations.md")
+        payload = {"id": "s1:review-block", "answer": "bound them"}
+        event = rs.build_event(LATER, "s1", "escalation-answered", payload)
+        guard = refuse_reads(self.page_path())
+        with mock.patch("builtins.open", guard), self.assertRaises(rs.RunStateError):
+            rs.append_event(self.run_dir, event)
+        self.assertEqual(self.read("escalations.md"), before)
+
+    def test_an_absent_page_is_still_created_from_the_header(self):
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        body = self.read("escalations.md")
+        self.assertTrue(body.startswith(rs.ESCALATIONS_HEADER))
+        self.assertEqual(len(self.sections(body)), 1)
+
+
 class TestPersistSlice(RunStateTestCase):
     def test_writes_the_sidecar_atomically(self):
         report = rs.persist_slice(self.run_dir, sidecar(), wave=1, ts=TS)
         self.assertTrue(report["ok"])
         stored = json.loads(self.read("slice-s1-status.json"))
@@ -948,17 +1322,20 @@ class TestPersistSlice(RunStateTestCase):
             "expected %r among %r" % (needle, errors))
 
 
 class TestOpenEscalations(RunStateTestCase):
     def open_one(self, escalation_id, ts=TS, **over):
-        rs.append_event(self.run_dir, ts, escalation_id.split(":")[0],
-                        "escalation-opened", escalation(id=escalation_id, **over))
+        scope = escalation_id.split(":")[0]
+        record = escalation(id=escalation_id, **over)
+        event = rs.build_event(ts, scope, "escalation-opened", record)
+        rs.append_event(self.run_dir, event)
 
     def answer(self, escalation_id, ts=LATER):
-        rs.append_event(self.run_dir, ts, escalation_id.split(":")[0],
-                        "escalation-answered",
-                        {"id": escalation_id, "answer": "done"})
+        scope = escalation_id.split(":")[0]
+        payload = {"id": escalation_id, "answer": "done"}
+        event = rs.build_event(ts, scope, "escalation-answered", payload)
+        rs.append_event(self.run_dir, event)
 
     def test_no_events_no_escalations(self):
         self.assertEqual(rs.open_escalations(self.run_dir), [])
 
     def test_lists_open_records(self):
@@ -994,25 +1371,140 @@ class TestOpenEscalations(RunStateTestCase):
         self.open_one("s1:review-block", ts="2026-07-31T00:00:00Z")
         self.assertEqual([r["id"] for r in rs.open_escalations(self.run_dir)],
                          ["s1:review-block"])
 
     def test_record_already_marked_answered_is_not_open(self):
-        rs.append_event(self.run_dir, TS, "s1", "escalation-opened",
-                        escalation(status="ANSWERED", answer="x", answered_at=TS))
+        record = escalation(status="ANSWERED", answer="x", answered_at=TS)
+        event = rs.build_event(TS, "s1", "escalation-opened", record)
+        rs.append_event(self.run_dir, event)
         self.assertEqual(rs.open_escalations(self.run_dir), [])
 
     def test_non_object_payloads_are_ignored(self):
         with open(os.path.join(self.run_dir, "events.jsonl"), "w", encoding="utf-8") as fh:
             fh.write(json.dumps({"ts": TS, "scope": "s1",
                                  "type": "escalation-opened",
                                  "payload": ["not a record"]}) + "\n")
         self.assertEqual(rs.open_escalations(self.run_dir), [])
 
     def test_payloads_without_an_id_are_ignored(self):
-        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", {"title": "no id"})
+        event = rs.build_event(TS, "s1", "escalation-opened", {"title": "no id"})
+        rs.append_event(self.run_dir, event)
         self.assertEqual(rs.open_escalations(self.run_dir), [])
 
+    def test_a_deduplicated_re_open_still_reaches_the_human_gate(self):
+        # The renderer collapses an identical re-emit onto one section; the
+        # gate is a separate, fail-safe reader and must still list the id.
+        record = escalation(id="s1:budget-exhausted", trigger="budget-exhausted")
+        rs.append_event(self.run_dir, rs.build_event(TS, "s1", "escalation-opened", record))
+        event = rs.build_event(LATER, "s1", "escalation-opened", record)
+        rs.append_event(self.run_dir, event)
+        ids = [item["id"] for item in rs.open_escalations(self.run_dir)]
+        self.assertEqual(ids, ["s1:budget-exhausted"])
+        body = self.read("escalations.md")
+        sections = [line for line in body.splitlines() if line.startswith("## ")]
+        self.assertEqual(len(sections), 1)
+
+
+# --------------------------------------------------------------------------
+# replay of the recorded runs under docs/spec-loop/ — the real corpus
+# --------------------------------------------------------------------------
+
+class TestRecordedCorpusReplay(RunStateTestCase):
+    """Replays the escalation events of the two completed runs recorded under
+    docs/spec-loop/ into a throwaway run dir. Those run directories are the
+    read-only reproduction corpus: this class reads them and writes only
+    inside self.run_dir.
+    """
+
+    def corpus(self, run_id):
+        root = Path(__file__).resolve().parents[3]
+        return root / "docs" / "spec-loop" / run_id
+
+    def escalation_events(self, run_id):
+        path = self.corpus(run_id) / "events.jsonl"
+        self.assertTrue(path.exists(), path)
+        raw = path.read_text(encoding="utf-8").splitlines()
+        events = [json.loads(line) for line in raw if line.strip()]
+        return [item for item in events if item.get("type") in rs.ESCALATION_EVENTS]
+
+    def replay(self, run_id):
+        for event in self.escalation_events(run_id):
+            payload = event.get("payload") or {}
+            fields = (event.get("ts"), event.get("scope"), event["type"], payload)
+            rs.append_event(self.run_dir, rs.build_event(*fields))
+        return self.read("escalations.md")
+
+    def headings(self, body):
+        return [line for line in body.splitlines() if line.startswith("## ")]
+
+    def answered_sections(self, sections):
+        return [item for item in sections if self.is_answered(item)]
+
+    def is_answered(self, section):
+        return rs.STATUS_ANSWERED_MARK in rs._section_line(section, "## ")
+
+    def headings_without_answer_text(self, sections):
+        blank = [item for item in sections if not rs._section_has_answer(item)]
+        return [rs._section_line(item, "## ") for item in blank]
+
+    def test_the_replayed_events_keep_their_recorded_type_and_scope(self):
+        recorded = self.escalation_events("20260825-scope-ceiling")
+        expected = [(item["type"], item.get("scope")) for item in recorded]
+        self.replay("20260825-scope-ceiling")
+        actual = [(item["type"], item.get("scope")) for item in self.events()]
+        self.assertEqual(actual, expected)
+
+    def test_the_recorded_page_has_twelve_sections_and_the_replay_has_nine(self):
+        # The recorded artifact is the defect: 11 escalation-opened events over
+        # 7 ids rendered 11 sections plus 1 orphan-answer entry. Three of those
+        # opens re-asked a question already on the page.
+        page = self.corpus("20260825-scope-ceiling") / "escalations.md"
+        recorded = page.read_text(encoding="utf-8")
+        self.assertEqual(len(self.headings(recorded)), 12)
+        replayed = self.replay("20260825-scope-ceiling")
+        self.assertEqual(len(self.headings(replayed)), 9)
+
+    def test_a_second_incident_under_one_id_keeps_its_own_section_and_answer(self):
+        body = self.replay("20260825-scope-ceiling")
+        head, sections = rs._escalation_sections(body)
+        anchor = rs.ID_ANCHOR % "s3:budget-exhausted"
+        rounds = [item for item in sections if anchor in item]
+        self.assertEqual(len(rounds), 2)
+        self.assertIn("undefined is not an object", rounds[0])
+        self.assertIn("StructuredOutput retry", rounds[1])
+        second = rs._section_line(rounds[1], "- Answer:")
+        self.assertIn("Genuine agent failure this time", second)
+
+    def test_the_one_answered_section_without_answer_text_is_the_recorded_one(self):
+        # Every section the replay renders ends ANSWERED, and exactly one of
+        # them carries no answer text. That one is recorded that way in the
+        # corpus, not produced by placement: the s2:quality-gate-block
+        # escalation-opened payload itself says status ANSWERED with a null
+        # answer, and its answer had already arrived before that id had any
+        # section on the page, so it stands in the orphan-answer entry above.
+        # Copying that text down onto this record is carry-answer-forward,
+        # which this slice deliberately does not do. The recorded artifact has
+        # three such sections; the replay has this one. A second entry in this
+        # list means a de-duplicated round was marked answered without having
+        # received an answer.
+        body = self.replay("20260825-scope-ceiling")
+        head, sections = rs._escalation_sections(body)
+        answered = self.answered_sections(sections)
+        self.assertEqual(len(answered), 9)
+        expected = "## [s2] verification failed   " + rs.STATUS_ANSWERED_MARK
+        self.assertEqual(self.headings_without_answer_text(answered), [expected])
+
+    def test_the_second_recorded_run_is_unchanged_at_one_section(self):
+        body = self.replay("20260826-crash-classification")
+        self.assertEqual(len(self.headings(body)), 1)
+
+    def test_the_replay_writes_nothing_into_the_corpus(self):
+        path = self.corpus("20260825-scope-ceiling") / "escalations.md"
+        before = path.read_bytes()
+        self.replay("20260825-scope-ceiling")
+        self.assertEqual(path.read_bytes(), before)
+
 
 # --------------------------------------------------------------------------
 # the workflow's returned events[] — the rich channel
 # --------------------------------------------------------------------------
 
@@ -1196,24 +1688,26 @@ class TestPinnedPayloadFacts(RunStateTestCase):
         self.assertEqual(opened["payload"]["id"], "s1:review-block")
 
     def test_answers_pair_by_id_not_by_scope(self):
         # One slice can open several escalations; answering one must not close
         # its siblings.
-        first, second = escalation(), escalation(id="s1:ambiguity",
-                                                 trigger="ambiguity")
-        rs.persist_slice(self.run_dir,
-                         sidecar("ESCALATED", escalations=[first, second]),
-                         wave=1, ts=TS)
-        rs.append_event(self.run_dir, LATER, "s1", "escalation-answered",
-                        {"id": "s1:ambiguity", "answer": "ISO-8601"})
-        self.assertEqual([r["id"] for r in rs.open_escalations(self.run_dir)],
-                         ["s1:review-block"])
+        first = escalation()
+        second = escalation(id="s1:ambiguity", trigger="ambiguity")
+        body = sidecar("ESCALATED", escalations=[first, second])
+        rs.persist_slice(self.run_dir, body, wave=1, ts=TS)
+        payload = {"id": "s1:ambiguity", "answer": "ISO-8601"}
+        event = rs.build_event(LATER, "s1", "escalation-answered", payload)
+        rs.append_event(self.run_dir, event)
+        still_open = [r["id"] for r in rs.open_escalations(self.run_dir)]
+        self.assertEqual(still_open, ["s1:review-block"])
 
     def test_an_answer_from_another_scope_still_pairs_by_id(self):
-        rs.append_event(self.run_dir, TS, "s1", "escalation-opened", escalation())
-        rs.append_event(self.run_dir, LATER, "run", "escalation-answered",
-                        {"id": "s1:review-block", "answer": "bound them"})
+        event = rs.build_event(TS, "s1", "escalation-opened", escalation())
+        rs.append_event(self.run_dir, event)
+        payload = {"id": "s1:review-block", "answer": "bound them"}
+        event = rs.build_event(LATER, "run", "escalation-answered", payload)
+        rs.append_event(self.run_dir, event)
         self.assertEqual(rs.open_escalations(self.run_dir), [])
 
     def test_council_verdict_passes_safety_through(self):
         rs.persist_slice(self.run_dir, sidecar(critique={
             "verdict": "OBJECT", "concerns": 3, "safety": True}), wave=1, ts=TS)
@@ -1225,12 +1719,13 @@ class TestPinnedPayloadFacts(RunStateTestCase):
             "verdict": "ENDORSE", "concerns": 0, "safety": False}), wave=1, ts=TS)
         verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
         self.assertIs(verdict["payload"]["safety"], False)
 
     def test_safety_is_named_in_the_decisions_log(self):
-        rs.append_event(self.run_dir, TS, "s1", "council-verdict",
-                        {"verdict": "OBJECT", "concerns": 1, "safety": True})
+        payload = {"verdict": "OBJECT", "concerns": 1, "safety": True}
+        event = rs.build_event(TS, "s1", "council-verdict", payload)
+        rs.append_event(self.run_dir, event)
         self.assertIn("SAFETY OBJECT", self.read("decisions-log.md"))
 
     def test_council_verdict_carries_the_whole_over_scope_record_not_just_a_bool(self):
         # safety drops its reason and records it nowhere; over_scope must not
         # repeat that — flag AND reason are both durable.
@@ -1284,11 +1779,11 @@ class TestPinnedPayloadFacts(RunStateTestCase):
             "over_scope": {"flag": False, "reason": None}}), wave=1, ts=TS)
         self.assertIn("scope: clean", self.read("slice-s1-report.md"))
 
     def test_a_deferred_event_marks_deferred_scope_with_over_scope_true(self):
         payload = {"title": "dashboard charts", "over_scope": True}
-        rs.append_event(self.run_dir, TS, "s1", "deferred", payload)
+        rs.append_event(self.run_dir, rs.build_event(TS, "s1", "deferred", payload))
         stored = self.events()[0]["payload"]
         decisions_log = self.read("decisions-log.md")
         self.assertEqual(stored, payload)
         self.assertIn("DEFERRED: SCOPE dashboard charts", decisions_log)
 
@@ -1304,20 +1799,21 @@ class TestPinnedPayloadFacts(RunStateTestCase):
     def test_agent_dispatch_payload_is_passed_through_verbatim(self):
         payload = {"role": "implementer", "model": "claude-opus-5", "effort": "high",
                    "agent_type": "sdd-implementer",
                    "dispatched_at": TS, "returned_at": LATER,
                    "tokens_in": 1200, "tokens_out": 340}
-        rs.append_event(self.run_dir, TS, "s1", "agent-dispatch", payload)
+        rs.append_event(self.run_dir, rs.build_event(TS, "s1", "agent-dispatch", payload))
         stored = self.events()[0]
         self.assertEqual(stored["payload"], payload)
         self.assertIsNone(self.read("decisions-log.md"))
 
     def test_agent_dispatch_absent_timings_stay_absent(self):
-        rs.append_event(self.run_dir, TS, "s1", "agent-dispatch",
-                        {"role": "reviewer", "model": None})
-        self.assertEqual(self.events()[0]["payload"], {"role": "reviewer",
-                                                      "model": None})
+        payload = {"role": "reviewer", "model": None}
+        event = rs.build_event(TS, "s1", "agent-dispatch", payload)
+        rs.append_event(self.run_dir, event)
+        stored = self.events()[0]["payload"]
+        self.assertEqual(stored, {"role": "reviewer", "model": None})
 
     def test_no_emitted_payload_derives_a_duration(self):
         # ts is a batch collection stamp: nothing here may turn it into elapsed
         # time. The sidecar's own started_at/finished_at pass through untouched.
         rs.persist_slice(self.run_dir, sidecar("ESCALATED",
