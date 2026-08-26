# Review package: 1376ccf..6be15a0  (context: -U5)

## Commits
6be15a0 fix(quality-gate): clear the remaining complexity findings the first round revealed
035d469 fix(quality-gate): extract helpers to clear the s2 complexity/nesting findings
acec853 feat(run-metrics): null-honest over-scope flag and deferral counters
dec295a docs(run-state-v2): pin the over_scope record on council-verdict and deferred
eb85195 test(run-state): flatten the new scope-record tests past the nesting gate
153dde0 feat(run-state): render the over-scope record in the decisions log and slice report
fe288d8 refactor(run-state): keep _over_scope_errors inside the quality gate's function metrics
9cb2903 feat(run-state): type-check the optional critique.over_scope record

## Files changed
 plugins/spec-loop/references/run-state-v2.md  |  15 +-
 plugins/spec-loop/scripts/run_metrics.py      | 224 +++++++++---
 plugins/spec-loop/scripts/run_state.py        | 480 +++++++++++++++++++-------
 plugins/spec-loop/scripts/test_run_metrics.py |  41 ++-
 plugins/spec-loop/scripts/test_run_state.py   | 200 +++++++++++
 scripts/coverage_omit.txt                     |   4 +-
 6 files changed, 786 insertions(+), 178 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/references/run-state-v2.md": [
[
79,
80
],
[
148,
158
]
],
"plugins/spec-loop/scripts/run_metrics.py": [
[
800,
804
],
[
806,
806
],
[
808,
810
],
[
815,
815
],
[
817,
817
],
[
819,
821
],
[
825,
894
],
[
1723,
1772
],
[
1781,
1791
],
[
1793,
1820
]
],
"plugins/spec-loop/scripts/run_state.py": [
[
93,
105
],
[
280,
283
],
[
288,
302
],
[
305,
305
],
[
310,
310
],
[
312,
327
],
[
329,
336
],
[
338,
338
],
[
340,
345
],
[
347,
349
],
[
351,
373
],
[
376,
378
],
[
380,
392
],
[
394,
395
],
[
397,
399
],
[
401,
443
],
[
518,
518
],
[
523,
569
],
[
596,
602
],
[
604,
604
],
[
606,
621
],
[
629,
630
],
[
632,
659
],
[
661,
662
],
[
664,
673
],
[
675,
682
],
[
684,
694
],
[
696,
715
],
[
717,
720
],
[
722,
724
],
[
727,
732
],
[
734,
744
],
[
746,
774
]
],
"plugins/spec-loop/scripts/test_run_metrics.py": [
[
83,
84
],
[
87,
88
],
[
96,
97
],
[
673,
677
],
[
729,
743
],
[
1128,
1134
],
[
1343,
1347
]
],
"plugins/spec-loop/scripts/test_run_state.py": [
[
258,
308
],
[
435,
506
],
[
561,
592
],
[
1175,
1219
]
],
"scripts/coverage_omit.txt": [
[
33,
34
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/references/run-state-v2.md b/plugins/spec-loop/references/run-state-v2.md
index d1d6cde..dd2a226 100644
--- a/plugins/spec-loop/references/run-state-v2.md
+++ b/plugins/spec-loop/references/run-state-v2.md
@@ -74,11 +74,12 @@ prose about the slice.
   "status": "DONE | SPLIT | ESCALATED | FAILED",
   "branch": "spec-loop/<run-id>/s1",
   "commits": { "base": "<sha>", "head": "<sha>" },   // null head if nothing committed
   "risk_tier": 2,
   "review_tier": 2,             // may exceed risk_tier via surface auto-promotion
-  "critique": { "verdict": "ENDORSE | ENDORSE_WITH_CONCERNS | OBJECT | SKIPPED", "concerns": 2 },
+  "critique": { "verdict": "ENDORSE | ENDORSE_WITH_CONCERNS | OBJECT | SKIPPED", "concerns": 2,
+                "over_scope": { "flag": false, "reason": null } },  // OPTIONAL; absent ≠ flag:false
   "tasks_completed": 4,
   "review": { "confirmed": 1, "refuted": 2, "evidence_failed": 0,
               "fix_rounds": 1, "residual": ["P2: ..."] },
   "tests": { "command": "...", "result": "...", "scope": "full", "tree_sha": "<sha>" },
   "quality": { "status": "PASS | FAIL | SKIPPED", "detail": "..." },
@@ -142,11 +143,21 @@ best-effort):
 - **`wave-collected`** payload carries the per-wave aggregates the workflow
   completion notification reports: `{index, agent_count, subagent_tokens,
   duration_ms}` — the honest wave-level token/duration channel while
   per-dispatch stamps are unavailable. Optional, null-honest.
 - **`council-verdict`** payload carries `safety: bool` — whether the verdict
-  involved a SAFETY flag (the one objection that halts alone).
+  involved a SAFETY flag (the one objection that halts alone) — and the
+  OPTIONAL `over_scope: {flag: bool, reason: string|null}` record. `over_scope`
+  keeps BOTH halves: unlike `safety`, whose reason is dropped at the source, the
+  reason is durable here. It is **record-only**: no verdict, gate, veto or
+  blocking decision reads it, and it is never a finding. Absent means no scope
+  judgement was recorded and is NOT equivalent to `flag: false`; both render
+  distinctly in `decisions-log.md` (`scope: clean` vs nothing at all).
+- **`deferred`** payload is null-honest and otherwise free-form
+  (`title`/`detail`), with one pinned key: `over_scope: true` marks a deferral of
+  work judged outside the slice's scope. Advisory prose data only — it suppresses
+  no finding and drops no work.
 - **`escalation-opened`** payload is the full EscalationRecord, including its
   `id`; `escalation-answered` pairs by that `id` (never by scope alone — one
   slice can open several).
 
 `run_metrics.py` reads events.jsonl as its primary channel. `decisions-log.md`
diff --git a/plugins/spec-loop/scripts/run_metrics.py b/plugins/spec-loop/scripts/run_metrics.py
index edc5be8..f72fb4f 100644
--- a/plugins/spec-loop/scripts/run_metrics.py
+++ b/plugins/spec-loop/scripts/run_metrics.py
@@ -795,38 +795,105 @@ def _council_stats(parsed):
     """Verdict mix from council-verdict events, with the sidecar critique
     verdicts as a parallel per-slice view.
 
     ``safety_objections`` stays null unless at least one verdict payload
     carries a ``safety`` flag: "no payload said safety" is not evidence that no
-    SAFETY objection was raised."""
+    SAFETY objection was raised. ``over_scope_flags`` and
+    ``over_scope_deferrals`` are a record of what the council observed and
+    feed no threshold, gate or blocking decision. Split into small PURE
+    helpers by concern so this function's own branching stays flat as the
+    stats grow new fields."""
     verdict_events = _of_type(parsed["events"], "council-verdict")
-    critiques = [sc["critique"] for sc in parsed["sidecars"] if sc["critique"]]
-    sidecar_verdicts = [c["verdict"] for c in critiques if c["verdict"]]
+    critiques = _sidecar_critiques(parsed)
     if not verdict_events and not critiques:
-        return {"basis": None, "verdicts": None, "object_rate": None,
-                "safety_objections": None, "concerns_total": None,
-                "concerns_deferred": None, "by_member": None,
-                "slice_verdicts": None}
-    verdicts = [_pstr(e, "verdict") for e in verdict_events]
-    verdicts = [v.upper() for v in verdicts if v and v.upper() in COUNCIL_VERDICTS]
-    safety_flagged = [e for e in verdict_events
-                      if isinstance(e["payload"].get("safety"), bool)]
+        return _empty_council_stats()
+    verdicts = _normalized_verdicts(verdict_events)
+    deferred_events = _of_type(parsed["events"], "deferred")
     return {
         "basis": _basis(bool(verdict_events), bool(critiques)),
         "verdicts": _tally(verdicts) if verdict_events else None,
         "object_rate": _ratio(verdicts.count("OBJECT"), len(verdicts)),
-        "safety_objections": sum(1 for e in safety_flagged
-                                 if e["payload"]["safety"]) if safety_flagged
-                             else None,
+        "safety_objections": _safety_objections(verdict_events),
         "concerns_total": _concerns_total(verdict_events, critiques),
-        "concerns_deferred": _sum_optional(_plist_len(e, "deferred")
-                                           for e in verdict_events),
+        "concerns_deferred": _concerns_deferred(verdict_events),
         "by_member": _tally(_pstr(e, "member") for e in verdict_events) or None,
-        "slice_verdicts": _tally(sidecar_verdicts) or None,
+        "slice_verdicts": _tally(_sidecar_verdicts(critiques)) or None,
+        "over_scope_flags": _flag_count(verdict_events, "over_scope"),
+        "over_scope_deferrals": _marked_count(deferred_events, "over_scope"),
     }
 
 
+def _concerns_deferred(verdict_events):
+    """The summed count of `deferred` items across verdict payloads (PURE)."""
+    lengths = (_plist_len(e, "deferred") for e in verdict_events)
+    return _sum_optional(lengths)
+
+
+def _sidecar_critiques(parsed):
+    """Non-null critique blocks from every parsed sidecar (PURE)."""
+    return [sc["critique"] for sc in parsed["sidecars"] if sc["critique"]]
+
+
+def _sidecar_verdicts(critiques):
+    """The non-null `verdict` of each sidecar critique block (PURE)."""
+    return [c["verdict"] for c in critiques if c["verdict"]]
+
+
+def _empty_council_stats():
+    """The all-null council-stats shape for a run with no council data (PURE)."""
+    return {"basis": None, "verdicts": None, "object_rate": None,
+            "safety_objections": None, "concerns_total": None,
+            "concerns_deferred": None, "by_member": None,
+            "slice_verdicts": None, "over_scope_flags": None,
+            "over_scope_deferrals": None}
+
+
+def _normalized_verdicts(verdict_events):
+    """Recognized council verdicts, upper-cased (PURE)."""
+    verdicts = [_pstr(e, "verdict") for e in verdict_events]
+    return [v.upper() for v in verdicts if v and v.upper() in COUNCIL_VERDICTS]
+
+
+def _safety_objections(verdict_events):
+    """How many verdict payloads flagged `safety: true`, or None (PURE)."""
+    safety_flagged = [e for e in verdict_events if _has_bool_safety(e)]
+    if not safety_flagged:
+        return None
+    return sum(1 for e in safety_flagged if e["payload"]["safety"])
+
+
+def _has_bool_safety(event):
+    """True if `event`'s payload carries a boolean `safety` flag (PURE)."""
+    return isinstance(event["payload"].get("safety"), bool)
+
+
+def _flag_count(events, key):
+    """How many payloads carried `{key: {flag: true}}`, or None (PURE).
+
+    Null-honest in the same way as ``safety_objections``: "no payload recorded
+    a scope judgement" is not evidence that nothing was over scope, and a
+    malformed record counts as no record rather than as a clean one."""
+    observed = [e for e in events if _has_bool_flag(e, key)]
+    if not observed:
+        return None
+    return sum(1 for e in observed if e["payload"][key]["flag"])
+
+
+def _has_bool_flag(event, key):
+    """True if `event`'s payload carries `{key: {flag: <bool>}}` (PURE)."""
+    block = event["payload"].get(key)
+    return isinstance(block, dict) and isinstance(block.get("flag"), bool)
+
+
+def _marked_count(events, key):
+    """How many payloads set the boolean marker `key` true, or None (PURE)."""
+    observed = [e for e in events if isinstance(e["payload"].get(key), bool)]
+    if not observed:
+        return None
+    return sum(1 for e in observed if e["payload"][key])
+
+
 def _concerns_total(verdict_events, critiques):
     """Concerns raised across the council.
 
     Events win over sidecars: there is one ``council-verdict`` event per
     verdict, so summing them counts every member's concerns, whereas the
@@ -1651,53 +1718,108 @@ def legacy_compute_metrics(artifacts):
         "tokens": None,
     }
 
 
 def _legacy_safety(events, escalations, decisions, observed):
-    council = [e for e in events if e["tag"] == "council"]
+    """The v1 prose-log safety metrics block. Split into small PURE helpers
+    by sub-block so this function's own branching stays flat as the block
+    grows new fields; the legacy prose channel never carries a scope
+    judgement, so the over-scope counters are honestly ``None`` here."""
+    council = _legacy_council_events(events)
+    verdicts, safety_objections = _legacy_council_tally(council)
+    precedent = _legacy_precedent_count(decisions)
+    return {
+        "basis": BASIS_LEGACY if observed else None,
+        "escalations": _legacy_escalations_block(escalations, observed),
+        "decisions_total": len(decisions) if observed else None,
+        "deferrals_total": None,
+        "autonomy_ratio": _legacy_autonomy_ratio(decisions, escalations, observed),
+        "escalation_answer_latency_s": _answer_latency(escalations),
+        "council": _legacy_council_block(council, verdicts, safety_objections),
+        "reversibility_mix": _legacy_reversibility_mix(events),
+        "precedent_reuse": _legacy_precedent_reuse(precedent, decisions),
+    }
+
+
+def _legacy_council_events(events):
+    """The v1 log lines tagged as council output (PURE)."""
+    return [e for e in events if e["tag"] == "council"]
+
+
+def _legacy_precedent_count(decisions):
+    """How many v1 decision lines mention reusing a precedent (PURE)."""
+    return sum(1 for e in decisions if LEGACY_PRECEDENT.search(e["rest"]))
+
+
+def _legacy_reversibility_mix(events):
+    """The `reversibility_mix` tally across every v1 log line (PURE)."""
+    return _tally(e["reversibility"] for e in events) or None
+
+
+def _legacy_autonomy_ratio(decisions, escalations, observed):
+    """The `autonomy_ratio` field of the legacy safety metrics (PURE)."""
+    if not observed:
+        return None
+    return _ratio(len(decisions), len(decisions) + len(escalations))
+
+
+def _legacy_precedent_reuse(precedent, decisions):
+    """The `precedent_reuse` sub-block of the legacy safety metrics (PURE)."""
+    return {"count": precedent if decisions else None,
+            "rate": _ratio(precedent, len(decisions))}
+
+
+def _legacy_council_tally(council):
+    """`(verdicts, safety_objections)` tallied from v1 council log lines (PURE)."""
     verdicts = []
     safety_objections = 0
     for event in council:
         verdict = _legacy_first_verdict(event["rest"].upper())
         if verdict:
             verdicts.append(verdict)
         if verdict == "OBJECT" and _legacy_mentions_unnegated_safety(event["rest"]):
             safety_objections += 1
-    precedent = sum(1 for e in decisions if LEGACY_PRECEDENT.search(e["rest"]))
+    return verdicts, safety_objections
+
+
+_LEGACY_ESCALATIONS_KEYS = ("basis", "total", "open", "answered", "by_trigger",
+                            "per_scope", "unkeyed_events")
+
+
+def _legacy_escalations_block(escalations, observed):
+    """The `escalations` sub-block of the legacy safety metrics (PURE)."""
+    if not observed:
+        return dict.fromkeys(_LEGACY_ESCALATIONS_KEYS)
     return {
-        "basis": BASIS_LEGACY if observed else None,
-        "escalations": {
-            "basis": BASIS_LEGACY if observed else None,
-            "total": len(escalations) if observed else None,
-            "open": sum(1 for e in escalations if e["status"] == "OPEN")
-                    if observed else None,
-            "answered": sum(1 for e in escalations if e["status"] == "ANSWERED")
-                        if observed else None,
-            "by_trigger": _tally(t for e in escalations for t in e["triggers"])
-                          if observed else None,
-            "per_scope": _tally(e["scope"] for e in escalations)
-                         if observed else None,
-            "unkeyed_events": None,
-        },
-        "decisions_total": len(decisions) if observed else None,
-        "deferrals_total": None,
-        "autonomy_ratio": _ratio(len(decisions), len(decisions) + len(escalations))
-                          if observed else None,
-        "escalation_answer_latency_s": _answer_latency(escalations),
-        "council": {
-            "basis": BASIS_LEGACY if council else None,
-            "verdicts": _tally(verdicts) if council else None,
-            "object_rate": _ratio(verdicts.count("OBJECT"), len(council)),
-            "safety_objections": safety_objections if council else None,
-            "concerns_total": None,
-            "concerns_deferred": None,
-            "by_member": None,
-            "slice_verdicts": None,
-        },
-        "reversibility_mix": _tally(e["reversibility"] for e in events) or None,
-        "precedent_reuse": {"count": precedent if decisions else None,
-                            "rate": _ratio(precedent, len(decisions))},
+        "basis": BASIS_LEGACY,
+        "total": len(escalations),
+        "open": _legacy_escalation_count(escalations, "OPEN"),
+        "answered": _legacy_escalation_count(escalations, "ANSWERED"),
+        "by_trigger": _tally(t for e in escalations for t in e["triggers"]),
+        "per_scope": _tally(e["scope"] for e in escalations),
+        "unkeyed_events": None,
+    }
+
+
+def _legacy_escalation_count(escalations, status):
+    """How many v1 escalation records carry the given `status` (PURE)."""
+    return sum(1 for e in escalations if e["status"] == status)
+
+
+def _legacy_council_block(council, verdicts, safety_objections):
+    """The `council` sub-block of the legacy safety metrics (PURE)."""
+    return {
+        "basis": BASIS_LEGACY if council else None,
+        "verdicts": _tally(verdicts) if council else None,
+        "object_rate": _ratio(verdicts.count("OBJECT"), len(council)),
+        "safety_objections": safety_objections if council else None,
+        "concerns_total": None,
+        "concerns_deferred": None,
+        "by_member": None,
+        "slice_verdicts": None,
+        "over_scope_flags": None,
+        "over_scope_deferrals": None,
     }
 
 
 def _legacy_first_verdict(upper):
     """The council verdict named in an upper-cased v1 line, or ''.
diff --git a/plugins/spec-loop/scripts/run_state.py b/plugins/spec-loop/scripts/run_state.py
index 3524503..3c747c8 100644
--- a/plugins/spec-loop/scripts/run_state.py
+++ b/plugins/spec-loop/scripts/run_state.py
@@ -88,10 +88,23 @@ ESCALATIONS_HEADER = ("# Escalations\n\n"
                       "Rendered from EscalationRecords; answers are written back "
                       "into the matching entry.\n\n")
 
 ID_ANCHOR = "<!-- escalation-id: %s -->"
 SUMMARY_LIMIT = 200
+# Payload keys, in priority order, that may carry a human-readable one-liner.
+# Module-level for the same reason as the messages below: a wrapped literal
+# inside _first_text's loop reads as nesting to the quality gate.
+SUMMARY_TEXT_KEYS = ("summary", "decision", "title", "question", "detail",
+                     "answer", "result", "status", "note")
+# critique.over_scope validation messages. Module-level so _over_scope_errors
+# stays flat: the quality gate derives nesting/cognitive scores from indentation,
+# and wrapped message literals inside the checks push it past both thresholds.
+OVER_SCOPE_NOT_OBJECT = ("critique.over_scope must be a JSON object when "
+                         "present (found %r)")
+OVER_SCOPE_BAD_FLAG = "critique.over_scope.flag must be true or false (found %r)"
+OVER_SCOPE_BAD_REASON = ("critique.over_scope.reason must be a string or null "
+                         "when present (found %r)")
 # Deliberately permissive ISO-8601: date, optional time, optional fraction, and
 # an optional Z / ±HH:MM offset. The controller supplies UTC stamps.
 ISO_TS = re.compile(
     r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
     r"(?:Z|[+-]\d{2}:?\d{2})?)?$")
@@ -262,83 +275,174 @@ def _returned_event_errors(events):
 def validate_sidecar(body):
     """Return every contract violation in a SliceResult sidecar.
 
     Fail-closed by construction: an unknown or missing `status` is itself an
     error, so a sidecar can never slip past the per-status requirements by
-    naming a status this contract does not know.
+    naming a status this contract does not know. The checks are split into
+    focused, PURE helpers by concern (top-level fields, shape/type checks,
+    critique/quality, and per-status requirements) so no single function's
+    branching grows unbounded as the contract grows.
     """
     if not isinstance(body, dict):
         return ["sidecar must contain a JSON object"]
 
+    top_errors, status = _top_level_sidecar_errors(body)
+    errors = list(top_errors)
+    errors.extend(_shape_errors(body))
+    errors.extend(_critique_and_quality_errors(body))
+    split = body.get("split")
+    if isinstance(split, dict):
+        errors.extend(_validate_children(split.get("children")))
+    for position, record in enumerate(body.get("escalations") or []):
+        errors.extend(validate_escalation(record, "escalations[%d]" % (position + 1)))
+    errors.extend(_status_requirement_errors(status, body, split))
+    return errors
+
+
+def _top_level_sidecar_errors(body):
+    """schema_version/id/status checks (PURE). Returns (errors, normalized_status)."""
     errors = []
     if body.get("schema_version") != SCHEMA_VERSION:
-        errors.append("schema_version must be %d (found %r)"
-                      % (SCHEMA_VERSION, body.get("schema_version")))
+        errors.append("schema_version must be %d (found %r)" % (SCHEMA_VERSION, body.get("schema_version")))
     if not _nonempty_str(body.get("id")):
         errors.append("id must be a non-empty slice id")
     status = body.get("status")
     if status not in SLICE_RESULT_STATUSES:
-        errors.append("status must be one of %s (found %r)"
-                      % ("/".join(SLICE_RESULT_STATUSES), status))
+        errors.append("status must be one of %s (found %r)" % ("/".join(SLICE_RESULT_STATUSES), status))
         status = None
+    return errors, status
+
+
+_SHAPE_TYPE_FIELDS = (
+    ("commits", dict, "JSON object"), ("critique", dict, "JSON object"),
+    ("review", dict, "JSON object"), ("tests", dict, "JSON object"),
+    ("quality", dict, "JSON object"), ("split", dict, "JSON object"),
+    ("escalations", list, "list"), ("events", list, "list"),
+)
+
+
+def _shape_errors(body):
+    """Type/shape checks for the optional top-level fields (PURE)."""
+    errors = _shape_type_errors(body)
+    errors.extend(_shape_numeric_errors(body))
+    return errors
 
-    for key in ("commits", "critique", "review", "tests", "quality", "split"):
-        if key in body and body[key] is not None and not isinstance(body[key], dict):
-            errors.append("%s must be a JSON object when present" % key)
-    if "escalations" in body and body["escalations"] is not None \
-            and not isinstance(body["escalations"], list):
-        errors.append("escalations must be a list when present")
-    if "events" in body and body["events"] is not None \
-            and not isinstance(body["events"], list):
-        errors.append("events must be a list when present")
+
+def _shape_type_errors(body):
+    """Type checks on the optional dict/list fields, the event list's own
+    content, and the `branch` string field (PURE)."""
+    errors = []
+    for key, kind, noun in _SHAPE_TYPE_FIELDS:
+        if key in body and body[key] is not None and not isinstance(body[key], kind):
+            errors.append("%s must be a %s when present" % (key, noun))
     errors.extend(_returned_event_errors(body.get("events")))
-    if "branch" in body and body["branch"] is not None \
-            and not _nonempty_str(body["branch"]):
+    if "branch" in body and body["branch"] is not None and not _nonempty_str(body["branch"]):
         errors.append("branch must be a non-empty string when present")
+    return errors
+
+
+def _shape_numeric_errors(body):
+    """The integer fields and the tier-enum fields (PURE)."""
+    errors = []
     for key in ("wave", "tasks_completed", "agents_used"):
-        if body.get(key) is not None and not _is_int(body[key]):
-            errors.append("%s must be an integer when present (found %r)"
-                          % (key, body[key]))
+        message = _int_field_error(body, key)
+        if message:
+            errors.append(message)
     for key in ("risk_tier", "review_tier"):
-        if body.get(key) is not None and body[key] not in RISK_TIERS:
-            errors.append("%s must be 1, 2 or 3 when present (found %r)"
-                          % (key, body[key]))
+        message = _tier_field_error(body, key)
+        if message:
+            errors.append(message)
+    return errors
 
-    critique = body.get("critique")
-    if isinstance(critique, dict) and critique.get("verdict") not in VERDICTS:
-        errors.append("critique.verdict must be one of %s (found %r)"
-                      % ("/".join(VERDICTS), critique.get("verdict")))
+
+def _int_field_error(body, key):
+    """The error for one integer field, or None when it is valid (PURE)."""
+    if body.get(key) is not None and not _is_int(body[key]):
+        return "%s must be an integer when present (found %r)" % (key, body[key])
+    return None
+
+
+def _tier_field_error(body, key):
+    """The error for one risk/review tier field, or None when valid (PURE)."""
+    if body.get(key) is not None and body[key] not in RISK_TIERS:
+        return "%s must be 1, 2 or 3 when present (found %r)" % (key, body[key])
+    return None
+
+
+def _critique_and_quality_errors(body):
+    """critique.verdict/critique.over_scope and quality.status checks (PURE)."""
+    errors = _critique_errors(body.get("critique"))
     quality = body.get("quality")
     if isinstance(quality, dict) and quality.get("status") not in QUALITY_STATUSES:
-        errors.append("quality.status must be one of %s (found %r)"
-                      % ("/".join(QUALITY_STATUSES), quality.get("status")))
-    split = body.get("split")
-    if isinstance(split, dict):
-        errors.extend(_validate_children(split.get("children")))
-    for position, record in enumerate(body.get("escalations") or []):
-        errors.extend(validate_escalation(record, "escalations[%d]" % (position + 1)))
+        errors.append("quality.status must be one of %s (found %r)" % ("/".join(QUALITY_STATUSES), quality.get("status")))
+    return errors
+
 
+def _critique_errors(critique):
+    """critique.verdict and critique.over_scope checks (PURE)."""
+    if not isinstance(critique, dict):
+        return []
+    errors = []
+    if critique.get("verdict") not in VERDICTS:
+        errors.append("critique.verdict must be one of %s (found %r)" % ("/".join(VERDICTS), critique.get("verdict")))
+    errors.extend(_over_scope_errors(critique.get("over_scope")))
+    return errors
+
+
+def _status_requirement_errors(status, body, split):
+    """Per-status required-field checks (PURE)."""
     if status == "DONE":
-        commits = body.get("commits")
-        if not isinstance(commits, dict):
-            errors.append("DONE requires commits with a head sha")
-        elif not _nonempty_str(commits.get("head")):
-            errors.append("DONE requires commits.head (a DONE slice committed "
-                          "something)")
-        tests = body.get("tests")
-        if not isinstance(tests, dict):
-            errors.append("DONE requires tests (command, result, scope)")
-        elif not _nonempty_str(tests.get("result")):
-            errors.append("DONE requires tests.result")
-        if not isinstance(body.get("quality"), dict):
-            errors.append("DONE requires quality (status, detail)")
-    elif status == "SPLIT":
+        return _done_requirement_errors(body)
+    if status == "SPLIT":
         if not isinstance(split, dict):
-            errors.append("SPLIT requires split.children (the proposed children)")
-    elif status == "ESCALATED":
+            return ["SPLIT requires split.children (the proposed children)"]
+        return []
+    if status == "ESCALATED":
         if not body.get("escalations"):
-            errors.append("ESCALATED requires a non-empty escalations list")
+            return ["ESCALATED requires a non-empty escalations list"]
+        return []
+    return []
+
+
+def _done_requirement_errors(body):
+    """The DONE-status field requirements (PURE)."""
+    errors = []
+    commits = body.get("commits")
+    if not isinstance(commits, dict):
+        errors.append("DONE requires commits with a head sha")
+    elif not _nonempty_str(commits.get("head")):
+        errors.append("DONE requires commits.head (a DONE slice committed something)")
+    tests = body.get("tests")
+    if not isinstance(tests, dict):
+        errors.append("DONE requires tests (command, result, scope)")
+    elif not _nonempty_str(tests.get("result")):
+        errors.append("DONE requires tests.result")
+    if not isinstance(body.get("quality"), dict):
+        errors.append("DONE requires quality (status, detail)")
+    return errors
+
+
+def _over_scope_errors(block):
+    """Messages for a `critique.over_scope` record (PURE).
+
+    Absent — and an explicit `null` — mean "no scope judgement was recorded",
+    which is a different claim from `flag: false` and is therefore valid. When
+    the block IS present it must carry both halves of the record: a real
+    boolean `flag`, and a `reason` that is a string or null. Every problem is
+    reported; nothing short-circuits.
+    """
+    if block is None:
+        return []
+    if not isinstance(block, dict):
+        return [OVER_SCOPE_NOT_OBJECT % (block,)]
+    errors = []
+    flag = block.get("flag")
+    reason = block.get("reason")
+    if not isinstance(flag, bool):
+        errors.append(OVER_SCOPE_BAD_FLAG % (flag,))
+    if reason is not None and not isinstance(reason, str):
+        errors.append(OVER_SCOPE_BAD_REASON % (reason,))
     return errors
 
 
 # --------------------------------------------------------------------------
 # renderers — pure
@@ -409,22 +513,62 @@ def _summarize(event):
     payload = event.get("payload") or {}
     if not isinstance(payload, dict):
         return _one_line(payload)
     event_type = event.get("type")
     if event_type == "council-verdict":
-        verdict = payload.get("verdict") or "(no verdict)"
-        concerns = payload.get("concerns")
-        # `safety` is pinned in the contract and is the objection that halts the
-        # loop alone, so it is named in the human line whenever it is set.
-        return "%s%s%s" % ("SAFETY " if payload.get("safety") else "", verdict,
-                           " (%s concerns)" % concerns if concerns else "")
+        return _verdict_summary(payload)
     if event_type in ("quality-gate", "integration-check", "phase5-gate"):
         outcome = payload.get("status") or payload.get("result") or "(no result)"
         detail = payload.get("detail") or payload.get("summary")
         return "%s%s" % (outcome, " — %s" % _one_line(detail) if detail else "")
-    for key in ("summary", "decision", "title", "question", "detail", "answer",
-                "result", "status", "note"):
+    if event_type == "deferred" and payload.get("over_scope") is True:
+        return "SCOPE %s" % _first_text(payload)
+    return _first_text(payload)
+
+
+def _verdict_summary(payload):
+    """The council-verdict line (PURE).
+
+    `safety` is pinned in the contract and is the objection that halts the loop
+    alone, so it is named whenever it is set. The `over_scope` record is
+    rendered whenever the payload carries one — including `flag: false` — so a
+    council that looked and found nothing is distinguishable from a council
+    that never looked. It is a record, never a verdict: it changes no branch.
+    """
+    prefix = "SAFETY " if payload.get("safety") else ""
+    line = "%s%s" % (prefix, payload.get("verdict") or "(no verdict)")
+    if payload.get("concerns"):
+        line += " (%s concerns)" % (payload["concerns"],)
+    note = _scope_note(payload.get("over_scope"))
+    if note:
+        line += " [%s]" % (note,)
+    return line
+
+
+def _scope_note(block):
+    """Human phrase for an over-scope record, or None when none was recorded (PURE).
+
+    Four distinct outcomes, none collapsed into another: absent/null -> None
+    (nothing is rendered at all), `flag: false` -> "scope: clean",
+    `flag: true` -> the flag plus its reason when one was given, and anything
+    malformed -> "scope: unreadable" rather than a silent pass.
+    """
+    if block is None:
+        return None
+    if not isinstance(block, dict) or not isinstance(block.get("flag"), bool):
+        return "scope: unreadable"
+    if not block["flag"]:
+        return "scope: clean"
+    reason = block.get("reason")
+    if isinstance(reason, str) and reason.strip():
+        return "SCOPE-FLAGGED: %s" % _one_line(reason)
+    return "SCOPE-FLAGGED"
+
+
+def _first_text(payload):
+    """The first human-readable field of an arbitrary payload (PURE)."""
+    for key in SUMMARY_TEXT_KEYS:
         if payload.get(key):
             return _one_line(payload[key])
     return _one_line(json.dumps(payload, ensure_ascii=False, sort_keys=True))
 
 
@@ -447,93 +591,189 @@ def _orphan_answer_entry(event):
                _one_line(payload.get("answer") or "", 400),
                payload.get("answered_at") or event.get("ts")))
 
 
 def render_report(body):
-    """Render the short human summary of one sidecar (PURE, null-honest)."""
+    """Render the short human summary of one sidecar (PURE, null-honest).
+
+    The sections below are split into focused, PURE helpers by concern (the
+    top summary bullets, then the optional residual/split/escalations
+    sections) so no single function's branching grows unbounded as the
+    report grows new sections.
+    """
     slice_id = body.get("id") or "?"
+    review = body.get("review") if isinstance(body.get("review"), dict) else {}
     lines = ["# Slice %s — %s" % (slice_id, body.get("status") or "UNKNOWN"), ""]
+    lines += _report_summary_lines(body, review)
+    lines += _report_residual_lines(review)
+    lines += _report_split_lines(body)
+    lines += _report_escalation_lines(body)
+    footer = "_Rendered from slice-%s-status.json; that sidecar is authoritative._" % slice_id
+    lines += ["", footer, ""]
+    return "\n".join(lines)
+
+
+def _report_summary_lines(body, review):
+    """The top `- **Label:** value` bullets of a slice report (PURE).
+
+    Each non-trivial field's value is computed by its own small PURE helper
+    (returning None when the field contributes no bullet) so this function
+    stays a flat dispatch table rather than growing nested per-field logic."""
+    lines = []
 
     def add(label, value):
         if value not in (None, "", []):
             lines.append("- **%s:** %s" % (label, value))
 
     add("Wave", body.get("wave"))
     add("Branch", body.get("branch"))
-    commits = body.get("commits") if isinstance(body.get("commits"), dict) else {}
-    if commits.get("base") or commits.get("head"):
-        add("Commits", "%s → %s" % (commits.get("base") or "(unknown base)",
-                                    commits.get("head") or "nothing committed"))
-    if body.get("risk_tier"):
-        review_tier = body.get("review_tier")
-        add("Risk tier", "%s%s" % (body["risk_tier"],
-                                   " (review tier %s)" % review_tier
-                                   if review_tier and review_tier != body["risk_tier"]
-                                   else ""))
+    add("Commits", _report_commits_value(body))
+    add("Risk tier", _report_risk_tier_value(body))
     add("Tasks completed", body.get("tasks_completed"))
+    add("Tests", _report_tests_value(body))
+    add("Quality gate", _report_quality_value(body))
+    add("Iron Council", _report_council_value(body))
+    if review:
+        add("Review", _review_summary(review))
+    add("Agents used", body.get("agents_used"))
+    add("Window", _report_window_value(body))
+    return lines
+
+
+def _report_commits_value(body):
+    """The `Commits` bullet's value, or None (PURE)."""
+    commits = body.get("commits") if isinstance(body.get("commits"), dict) else {}
+    if not (commits.get("base") or commits.get("head")):
+        return None
+    return "%s → %s" % (commits.get("base") or "(unknown base)", commits.get("head") or "nothing committed")
+
+
+def _report_risk_tier_value(body):
+    """The `Risk tier` bullet's value, or None (PURE)."""
+    if not body.get("risk_tier"):
+        return None
+    review_tier = body.get("review_tier")
+    suffix = ""
+    if review_tier and review_tier != body["risk_tier"]:
+        suffix = " (review tier %s)" % review_tier
+    return "%s%s" % (body["risk_tier"], suffix)
+
 
+def _report_tests_value(body):
+    """The `Tests` bullet's value, or None (PURE)."""
     tests = body.get("tests") if isinstance(body.get("tests"), dict) else {}
-    if tests.get("command") or tests.get("result"):
-        detail = "`%s` — %s" % (tests.get("command") or "(command not recorded)",
-                                tests.get("result") or "(result not recorded)")
-        if tests.get("scope"):
-            detail += " (scope: %s)" % tests["scope"]
-        add("Tests", detail)
+    if not (tests.get("command") or tests.get("result")):
+        return None
+    detail = "`%s` — %s" % (tests.get("command") or "(command not recorded)", tests.get("result") or "(result not recorded)")
+    if tests.get("scope"):
+        detail += " (scope: %s)" % tests["scope"]
+    return detail
+
+
+def _report_quality_value(body):
+    """The `Quality gate` bullet's value, or None (PURE)."""
     quality = body.get("quality") if isinstance(body.get("quality"), dict) else {}
-    if quality.get("status"):
-        add("Quality gate", "%s%s" % (quality["status"],
-                                      " — %s" % _one_line(quality.get("detail"))
-                                      if quality.get("detail") else ""))
+    if not quality.get("status"):
+        return None
+    suffix = " — %s" % _one_line(quality.get("detail")) if quality.get("detail") else ""
+    return "%s%s" % (quality["status"], suffix)
+
+
+def _report_council_value(body):
+    """The `Iron Council` bullet's value, or None (PURE)."""
     critique = body.get("critique") if isinstance(body.get("critique"), dict) else {}
-    if critique.get("verdict"):
-        add("Iron Council", "%s%s" % (critique["verdict"],
-                                      " (%s concerns)" % critique["concerns"]
-                                      if critique.get("concerns") else ""))
-    review = body.get("review") if isinstance(body.get("review"), dict) else {}
-    if review:
-        parts = []
-        for key, label in (("confirmed", "confirmed"), ("refuted", "refuted"),
-                           ("evidence_failed", "evidence-failed"),
-                           ("fix_rounds", "fix round")):
-            value = review.get(key)
-            if value is None:
-                continue
-            plural = "s" if key == "fix_rounds" and value != 1 else ""
-            parts.append("%s %s%s" % (value, label, plural))
-        add("Review", ", ".join(parts))
-    add("Agents used", body.get("agents_used"))
-    if body.get("started_at") or body.get("finished_at"):
-        add("Window", "%s → %s" % (body.get("started_at") or "(unknown)",
-                                   body.get("finished_at") or "(unknown)"))
+    if not critique.get("verdict"):
+        return None
+    return _council_summary(critique)
+
+
+def _report_window_value(body):
+    """The `Window` bullet's value, or None (PURE)."""
+    if not (body.get("started_at") or body.get("finished_at")):
+        return None
+    return "%s → %s" % (body.get("started_at") or "(unknown)", body.get("finished_at") or "(unknown)")
+
 
+_REVIEW_SUMMARY_FIELDS = (
+    ("confirmed", "confirmed"), ("refuted", "refuted"),
+    ("evidence_failed", "evidence-failed"), ("fix_rounds", "fix round"),
+)
+
+
+def _review_summary(review):
+    """The `Review` bullet's value: counts of confirmed/refuted/etc (PURE)."""
+    parts = []
+    for key, label in _REVIEW_SUMMARY_FIELDS:
+        value = review.get(key)
+        if value is None:
+            continue
+        plural = "s" if key == "fix_rounds" and value != 1 else ""
+        parts.append("%s %s%s" % (value, label, plural))
+    return ", ".join(parts)
+
+
+def _report_residual_lines(review):
+    """The `## Residual findings` section, or nothing when there is none (PURE)."""
     residual = [r for r in (review.get("residual") or []) if r]
-    if residual:
-        lines += ["", "## Residual findings", ""]
-        lines += ["- %s" % _one_line(item, 300) for item in residual]
+    if not residual:
+        return []
+    return ["", "## Residual findings", ""] + \
+        ["- %s" % _one_line(item, 300) for item in residual]
 
+
+def _report_split_lines(body):
+    """The `## Proposed split` section, or nothing when there is none (PURE)."""
     split = body.get("split") if isinstance(body.get("split"), dict) else {}
     children = [c for c in (split.get("children") or []) if isinstance(c, dict)]
-    if children:
-        lines += ["", "## Proposed split into %d children" % len(children), ""]
-        for position, child in enumerate(children):
-            refs = [str(r) for r in (child.get("internal_deps") or [])]
-            lines.append("%d. %s%s" % (position + 1,
-                                       _one_line(child.get("goal") or "(no goal)", 300),
-                                       " (after child %s)" % ", ".join(refs)
-                                       if refs else ""))
+    if not children:
+        return []
+    lines = ["", "## Proposed split into %d children" % len(children), ""]
+    for position, child in enumerate(children):
+        lines.append(_report_split_child_line(position, child))
+    return lines
 
+
+def _report_split_child_line(position, child):
+    """One numbered child line of the `## Proposed split` section (PURE)."""
+    refs = [str(r) for r in (child.get("internal_deps") or [])]
+    suffix = " (after child %s)" % ", ".join(refs) if refs else ""
+    goal = _one_line(child.get("goal") or "(no goal)", 300)
+    return "%d. %s%s" % (position + 1, goal, suffix)
+
+
+def _report_escalation_lines(body):
+    """The `## Escalations` section, or nothing when there are none (PURE)."""
     escalations = [e for e in (body.get("escalations") or []) if isinstance(e, dict)]
-    if escalations:
-        lines += ["", "## Escalations", ""]
-        for record in escalations:
-            lines.append("- **%s** `%s` — %s"
-                         % (record.get("status") or "OPEN", record.get("id") or "?",
-                            _one_line(record.get("title") or "(untitled)")))
-
-    lines += ["", "_Rendered from slice-%s-status.json; that sidecar is "
-                 "authoritative._" % slice_id, ""]
-    return "\n".join(lines)
+    if not escalations:
+        return []
+    lines = ["", "## Escalations", ""]
+    for record in escalations:
+        lines.append(_report_escalation_line(record))
+    return lines
+
+
+def _report_escalation_line(record):
+    """One bullet of the `## Escalations` section (PURE)."""
+    status = record.get("status") or "OPEN"
+    escalation_id = record.get("id") or "?"
+    title = _one_line(record.get("title") or "(untitled)")
+    return "- **%s** `%s` — %s" % (status, escalation_id, title)
+
+
+def _council_summary(critique):
+    """The `Iron Council` value of a slice report, from a critique block (PURE).
+
+    Shares `_scope_note` with the decisions log, so the two human surfaces can
+    never disagree about whether a scope judgement was recorded.
+    """
+    line = "%s" % (critique["verdict"],)
+    if critique.get("concerns"):
+        line += " (%s concerns)" % (critique["concerns"],)
+    note = _scope_note(critique.get("over_scope"))
+    if note:
+        line += " — %s" % (note,)
+    return line
 
 
 # --------------------------------------------------------------------------
 # events
 # --------------------------------------------------------------------------
diff --git a/plugins/spec-loop/scripts/test_run_metrics.py b/plugins/spec-loop/scripts/test_run_metrics.py
index 2de5975..0b3516f 100644
--- a/plugins/spec-loop/scripts/test_run_metrics.py
+++ b/plugins/spec-loop/scripts/test_run_metrics.py
@@ -78,22 +78,25 @@ def ev(ts, scope, type_, **payload):
 #   engine-active union is [10:12, 10:40] (1680s) + integration reviewer 480s = 2160s.
 V2_EVENT_OBJECTS = [
     ev("2026-07-30T10:00:00Z", "run", "run-created", run_id="20260730-v2"),
     ev("2026-07-30T10:00:30Z", "run", "baseline", tests="281 passed"),
     ev("2026-07-30T10:01:00Z", "intake", "council-verdict",
-       member="skeptic", verdict="ENDORSE", concerns=0, safety=False),
+       member="skeptic", verdict="ENDORSE", concerns=0, safety=False,
+       over_scope={"flag": False, "reason": None}),
     ev("2026-07-30T10:01:30Z", "intake", "council-verdict",
        member="guardian", verdict="OBJECT", concerns_folded=3, safety=True,
-       deferred=["P2: rename later", "P2: widen the fixture"]),
+       deferred=["P2: rename later", "P2: widen the fixture"],
+       over_scope={"flag": True, "reason": "adds a tier heuristic"}),
     ev("2026-07-30T10:02:00Z", "intake", "decision",
        title="reuse the existing helper",
        rationale="precedent — run 20260630-full-coverage answered this",
        reversibility="trivial"),
     ev("2026-07-30T10:03:00Z", "s1", "decision",
        title="keep the function name", rationale="file convention",
        reversibility="moderate"),
-    ev("2026-07-30T10:04:00Z", "s1", "deferred", title="dashboard charts"),
+    ev("2026-07-30T10:04:00Z", "s1", "deferred", title="dashboard charts",
+       over_scope=True),
     ev("2026-07-30T10:05:00Z", "wave1", "wave-dispatched",
        index=1, slice_ids=["s1", "s2"]),
     ev("2026-07-30T11:10:00Z", "s1", "agent-dispatch",
        agent_type="spec-loop:sdd-implementer", model="sonnet", effort="high",
        role="task-implement", dispatched_at="2026-07-30T10:12:00Z",
@@ -665,10 +668,15 @@ class V2SafetyTests(unittest.TestCase):
         self.assertEqual(self.safety["reversibility_mix"],
                          {"moderate": 1, "trivial": 1})
         self.assertEqual(self.safety["precedent_reuse"],
                          {"count": 1, "rate": 0.5})
 
+    def test_over_scope_counters_read_the_recorded_scope_judgements(self):
+        council = self.safety["council"]
+        self.assertEqual(council["over_scope_flags"], 1)      # guardian flagged
+        self.assertEqual(council["over_scope_deferrals"], 1)  # one marked deferral
+
 
 class CouncilConcernsPrecedenceTests(unittest.TestCase):
     """Events are per-verdict; the sidecar critique is a per-slice rollup.
     Summing both would double-count, so events win and the sidecar is only a
     fallback."""
@@ -716,10 +724,25 @@ class CouncilConcernsPrecedenceTests(unittest.TestCase):
                                "council-verdict", verdict="ENDORSE"))
         council = compute_for({"events.jsonl": events})["safety"]["council"]
         self.assertIsNone(council["concerns_total"])
         self.assertIsNone(council["concerns_deferred"])
 
+    def test_a_clean_scope_judgement_is_an_honest_zero_not_a_null(self):
+        council = self.council_total(over_scope={"flag": False, "reason": None})
+        self.assertEqual(council["over_scope_flags"], 0)
+
+    def test_no_scope_judgement_at_all_stays_null(self):
+        # "no payload said over_scope" is not evidence that nothing was over scope.
+        self.assertIsNone(self.council_total(concerns=1)["over_scope_flags"])
+
+    def test_a_malformed_scope_record_is_not_counted_as_clean(self):
+        self.assertIsNone(
+            self.council_total(over_scope={"flag": "yes"})["over_scope_flags"])
+
+    def test_deferrals_without_a_scope_marker_stay_null(self):
+        self.assertIsNone(self.council_total(concerns=1)["over_scope_deferrals"])
+
     def test_critique_with_only_concerns_still_reaches_the_document(self):
         metrics = compute_for({"slice-s1-status.json": {
             "schema_version": 2, "id": "s1", "status": "DONE",
             "critique": {"concerns": 4}}})
         council = metrics["safety"]["council"]
@@ -1100,10 +1123,17 @@ class NullHonestyTests(unittest.TestCase):
         self.assertEqual(council["verdicts"], {"OBJECT": 1})
         self.assertEqual(council["object_rate"], 1.0)
         self.assertIsNone(council["safety_objections"])
         self.assertIsNone(council["concerns_total"])
 
+    def test_over_scope_counters_are_null_on_an_uninstrumented_run(self):
+        council = compute_for({"slice-s1-status.json": {
+            "schema_version": 2, "id": "s1", "status": "DONE",
+            "critique": {"verdict": "OBJECT"}}})["safety"]["council"]
+        self.assertIsNone(council["over_scope_flags"])
+        self.assertIsNone(council["over_scope_deferrals"])
+
     def test_gate_events_without_a_status_leave_the_rate_null(self):
         events = "\n".join(json.dumps(e) for e in [
             ev("2026-07-30T10:00:00Z", "s1", "quality-gate", detail="ran"),
             ev("2026-07-30T10:01:00Z", "s2", "quality-gate", status="maybe"),
         ])
@@ -1308,10 +1338,15 @@ class LegacyComputeTests(unittest.TestCase):
                                places=3)
         self.assertEqual(safety["council"]["safety_objections"], 0)
         self.assertEqual(safety["reversibility_mix"],
                          {"high": 5, "moderate": 1, "n/a": 1})
 
+    def test_the_legacy_prose_path_reports_no_scope_judgement(self):
+        council = self.metrics["safety"]["council"]
+        self.assertIsNone(council["over_scope_flags"])
+        self.assertIsNone(council["over_scope_deferrals"])
+
     def test_quality_from_prose(self):
         quality = self.metrics["quality"]
         self.assertEqual(quality["quality_gate"]["measurements"], 2)
         self.assertEqual(quality["quality_gate"]["first_pass"], 1)
         self.assertEqual(quality["quality_gate"]["first_pass_rate"], 0.5)
diff --git a/plugins/spec-loop/scripts/test_run_state.py b/plugins/spec-loop/scripts/test_run_state.py
index ee0fc33..9aedef7 100644
--- a/plugins/spec-loop/scripts/test_run_state.py
+++ b/plugins/spec-loop/scripts/test_run_state.py
@@ -253,10 +253,61 @@ class TestValidateSidecar(unittest.TestCase):
     def test_split_internal_deps_must_be_a_list(self):
         body = sidecar("SPLIT")
         body["split"]["children"] = [{"goal": "a", "internal_deps": 2}, {"goal": "b"}]
         self.assertMentions(body, "internal_deps")
 
+    def test_a_sidecar_without_an_over_scope_block_is_valid(self):
+        # over_scope is optional: absence means "no scope judgement recorded",
+        # which is not the same claim as flag=False.
+        body = sidecar()
+        self.assertNotIn("over_scope", body["critique"])
+        self.assertValid(body)
+
+    def test_an_over_scope_record_with_a_flag_and_a_reason_is_valid(self):
+        self.assertValid(sidecar(critique={
+            "verdict": "ENDORSE_WITH_CONCERNS", "concerns": 2,
+            "over_scope": {"flag": True, "reason": "adds a tier heuristic"}}))
+
+    def test_an_over_scope_record_may_carry_a_null_reason(self):
+        self.assertValid(sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0,
+            "over_scope": {"flag": False, "reason": None}}))
+
+    def test_a_null_over_scope_reads_as_absent_and_is_valid(self):
+        self.assertValid(sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0, "over_scope": None}))
+
+    def test_over_scope_must_be_an_object(self):
+        self.assertMentions(sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0, "over_scope": True}),
+            "critique.over_scope must be a JSON object")
+
+    def test_over_scope_flag_must_be_a_boolean(self):
+        self.assertMentions(sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0,
+            "over_scope": {"flag": "yes", "reason": None}}),
+            "critique.over_scope.flag")
+
+    def test_over_scope_without_a_flag_is_refused(self):
+        self.assertMentions(sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0, "over_scope": {"reason": "x"}}),
+            "critique.over_scope.flag")
+
+    def test_over_scope_reason_must_be_a_string_or_null(self):
+        self.assertMentions(sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0,
+            "over_scope": {"flag": True, "reason": 7}}),
+            "critique.over_scope.reason")
+
+    def test_a_bad_flag_and_a_bad_reason_are_reported_together(self):
+        # Validation never short-circuits: one round-trip must show everything.
+        errors = rs.validate_sidecar(sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0,
+            "over_scope": {"flag": None, "reason": []}}))
+        scoped = [e for e in errors if e.startswith("critique.over_scope.")]
+        self.assertEqual(len(scoped), 2)
+
 
 # --------------------------------------------------------------------------
 # renderers — pure
 # --------------------------------------------------------------------------
 
@@ -379,10 +430,82 @@ class TestDecisionLine(unittest.TestCase):
         self.assertIn("[s1] DECISION:", self.line("decision", {}))
 
     def test_non_object_payload_is_tolerated(self):
         self.assertIn("just text", self.line("decision", "just text"))
 
+    def test_a_flagged_scope_record_is_named_in_the_council_line(self):
+        record = {"flag": True, "reason": "adds a tier heuristic"}
+        payload = {"verdict": "ENDORSE", "concerns": 1, "over_scope": record}
+        line = self.line("council-verdict", payload)
+        self.assertIn("SCOPE-FLAGGED: adds a tier heuristic", line)
+
+    def test_a_flagged_scope_record_without_a_reason_still_says_flagged(self):
+        record = {"flag": True, "reason": None}
+        payload = {"verdict": "ENDORSE", "over_scope": record}
+        self.assertIn("SCOPE-FLAGGED", self.line("council-verdict", payload))
+
+    def test_a_clean_scope_record_is_rendered_not_swallowed(self):
+        # Unconditional rendering: "the council looked and found nothing" must
+        # be visible, otherwise it is indistinguishable from "nobody looked".
+        record = {"flag": False, "reason": None}
+        payload = {"verdict": "ENDORSE", "over_scope": record}
+        self.assertIn("scope: clean", self.line("council-verdict", payload))
+
+    def test_an_absent_scope_record_renders_no_scope_phrase_at_all(self):
+        line = self.line("council-verdict", {"verdict": "ENDORSE", "concerns": 0})
+        self.assertNotIn("scope", line.lower())
+
+    def test_a_malformed_scope_record_is_reported_as_unreadable(self):
+        payload = {"verdict": "ENDORSE", "over_scope": {"flag": "yes"}}
+        line = self.line("council-verdict", payload)
+        self.assertIn("scope: unreadable", line)
+
+    def test_a_non_object_scope_record_is_reported_as_unreadable(self):
+        payload = {"verdict": "ENDORSE", "over_scope": True}
+        line = self.line("council-verdict", payload)
+        self.assertIn("scope: unreadable", line)
+
+    def test_the_safety_prefix_and_the_scope_note_coexist(self):
+        record = {"flag": True, "reason": "dashboards"}
+        payload = {"verdict": "OBJECT", "concerns": 2, "safety": True}
+        payload["over_scope"] = record
+        line = self.line("council-verdict", payload)
+        self.assertIn("SAFETY OBJECT (2 concerns)", line)
+        self.assertIn("SCOPE-FLAGGED: dashboards", line)
+
+    def test_a_scope_marked_deferral_is_marked_in_the_decisions_log(self):
+        payload = {"title": "dashboard charts", "over_scope": True}
+        line = self.line("deferred", payload)
+        self.assertIn("DEFERRED: SCOPE dashboard charts", line)
+
+    def test_an_ordinary_deferral_is_unmarked(self):
+        line = self.line("deferred", {"title": "dashboard charts"})
+        self.assertIn("DEFERRED: dashboard charts", line)
+        self.assertNotIn("SCOPE", line)
+
+    def test_a_deferral_marked_false_is_not_a_scope_deferral(self):
+        # over_scope: false is an explicit "not a scope deferral"; only the
+        # boolean true earns the marker.
+        payload = {"title": "dashboard charts", "over_scope": False}
+        line = self.line("deferred", payload)
+        self.assertIn("DEFERRED: dashboard charts", line)
+        self.assertNotIn("SCOPE", line)
+
+    def test_a_non_string_verdict_is_still_rendered_not_crashed_on(self):
+        # decision_line renders arbitrary events.jsonl payloads, so the
+        # extracted _verdict_summary must stay as type-tolerant as the
+        # %-formatted expression it replaced.
+        line = self.line("council-verdict", {"verdict": 7, "concerns": "many"})
+        self.assertIn("COUNCIL-VERDICT: 7 (many concerns)", line)
+
+    def test_the_scope_marker_is_only_read_on_deferred_events(self):
+        # over_scope on some other event type is not a rendering instruction.
+        payload = {"summary": "use the CSV writer", "over_scope": True}
+        line = self.line("decision", payload)
+        self.assertIn("DECISION: use the CSV writer", line)
+        self.assertNotIn("SCOPE", line)
+
 
 class TestRenderReport(unittest.TestCase):
     def test_done_report(self):
         body = rs.render_report(sidecar())
         self.assertIn("# Slice s1 — DONE", body)
@@ -433,10 +556,42 @@ class TestRenderReport(unittest.TestCase):
             self.assertNotIn(absent, body)
 
     def test_report_points_at_the_authoritative_sidecar(self):
         self.assertIn("slice-s1-status.json", rs.render_report(sidecar()))
 
+    def test_the_report_names_a_flagged_scope_beside_the_council_verdict(self):
+        text = rs.render_report(sidecar(critique={
+            "verdict": "ENDORSE_WITH_CONCERNS", "concerns": 2,
+            "over_scope": {"flag": True, "reason": "adds a tier heuristic"}}))
+        self.assertIn("Iron Council", text)
+        self.assertIn("SCOPE-FLAGGED: adds a tier heuristic", text)
+
+    def test_the_report_names_a_clean_scope_verdict_too(self):
+        text = rs.render_report(sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0,
+            "over_scope": {"flag": False, "reason": None}}))
+        self.assertIn("scope: clean", text)
+
+    def test_the_report_says_nothing_about_scope_when_none_was_recorded(self):
+        # The Tests line has always printed the unrelated "(scope: full)"
+        # test-scope field, so the unrecorded-scope contract is asserted
+        # against the Iron Council line itself, not the whole document.
+        text = rs.render_report(sidecar())
+        self.assertEqual(
+            [ln for ln in text.splitlines() if "Iron Council" in ln],
+            ["- **Iron Council:** ENDORSE_WITH_CONCERNS (2 concerns)"])
+        self.assertNotIn("SCOPE", text)
+
+    def test_a_non_string_council_verdict_is_still_rendered_in_the_report(self):
+        text = rs.render_report(sidecar(critique={"verdict": 7, "concerns": 1}))
+        self.assertIn("**Iron Council:** 7 (1 concerns)", text)
+
+    def test_a_malformed_scope_record_is_named_unreadable_in_the_report(self):
+        text = rs.render_report(sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0, "over_scope": {"reason": "x"}}))
+        self.assertIn("scope: unreadable", text)
+
 
 # --------------------------------------------------------------------------
 # filesystem: events, persist-slice, open escalations
 # --------------------------------------------------------------------------
 
@@ -1015,10 +1170,55 @@ class TestPinnedPayloadFacts(RunStateTestCase):
     def test_safety_is_named_in_the_decisions_log(self):
         rs.append_event(self.run_dir, TS, "s1", "council-verdict",
                         {"verdict": "OBJECT", "concerns": 1, "safety": True})
         self.assertIn("SAFETY OBJECT", self.read("decisions-log.md"))
 
+    def test_council_verdict_carries_the_whole_over_scope_record_not_just_a_bool(self):
+        # safety drops its reason and records it nowhere; over_scope must not
+        # repeat that — flag AND reason are both durable.
+        record = {"flag": True, "reason": "adds a tier-assignment heuristic"}
+        rs.persist_slice(self.run_dir, sidecar(critique={
+            "verdict": "OBJECT", "concerns": 3, "over_scope": record}),
+            wave=1, ts=TS)
+        verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
+        self.assertEqual(verdict["payload"]["over_scope"], record)
+
+    def test_a_clean_over_scope_record_survives_persistence(self):
+        rs.persist_slice(self.run_dir, sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0,
+            "over_scope": {"flag": False, "reason": None}}), wave=1, ts=TS)
+        verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
+        self.assertIs(verdict["payload"]["over_scope"]["flag"], False)
+        self.assertIn("scope: clean", self.read("decisions-log.md"))
+
+    def test_a_returned_council_verdict_event_keeps_over_scope_byte_for_byte(self):
+        payload = {"verdict": "ENDORSE_WITH_CONCERNS", "panel": ["plan-critic"],
+                   "safety": False, "concerns_folded": 1, "deferred": ["P2: later"],
+                   "over_scope": {"flag": True, "reason": "dashboard UI work"}}
+        rs.persist_slice(self.run_dir, sidecar(events=[
+            {"scope": "s1", "type": "council-verdict", "payload": payload}]),
+            wave=1, ts=TS)
+        stored = [e for e in self.events() if e["type"] == "council-verdict"][0]
+        self.assertEqual(stored["payload"], payload)
+
+    def test_a_deferred_event_marks_deferred_scope_with_over_scope_true(self):
+        payload = {"title": "dashboard charts", "over_scope": True}
+        rs.append_event(self.run_dir, TS, "s1", "deferred", payload)
+        stored = self.events()[0]["payload"]
+        decisions_log = self.read("decisions-log.md")
+        self.assertEqual(stored, payload)
+        self.assertIn("DEFERRED: SCOPE dashboard charts", decisions_log)
+
+    def test_over_scope_never_changes_the_recorded_verdict(self):
+        # Record-only: the flag is not a vote and not a finding.
+        rs.persist_slice(self.run_dir, sidecar(critique={
+            "verdict": "ENDORSE", "concerns": 0,
+            "over_scope": {"flag": True, "reason": "out of the run ceiling"}}),
+            wave=1, ts=TS)
+        verdict = [e for e in self.events() if e["type"] == "council-verdict"][0]
+        self.assertEqual(verdict["payload"]["verdict"], "ENDORSE")
+
     def test_agent_dispatch_payload_is_passed_through_verbatim(self):
         payload = {"role": "implementer", "model": "claude-opus-5", "effort": "high",
                    "agent_type": "sdd-implementer",
                    "dispatched_at": TS, "returned_at": LATER,
                    "tokens_in": 1200, "tokens_out": 340}
diff --git a/scripts/coverage_omit.txt b/scripts/coverage_omit.txt
index f4d8262..0395234 100644
--- a/scripts/coverage_omit.txt
+++ b/scripts/coverage_omit.txt
@@ -28,10 +28,10 @@ scripts/dashboard_server.py:1645-1646    # __main__ entry shim (if __name__/sys.
 scripts/knowledge_graph.py:1211-1212     # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/pr_resolver.py:488-489           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/quality_gate.py:1104-1105        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/release.py:194-195               # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/review_package.py:131-132        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/run_metrics.py:1825-1826         # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/run_state.py:837-838             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/run_metrics.py:2162-2163         # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/run_state.py:1077-1078           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/spec_loop_guard.py:240-241       # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/validate_marketplace.py:417-418  # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/worktrees.py:385-386             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
