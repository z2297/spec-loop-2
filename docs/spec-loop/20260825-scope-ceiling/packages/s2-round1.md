# Review package: 1376ccf03e1610e6ecc8b19dc879609228a2d5ec..acec853  (context: -U5)

## Commits
acec853 feat(run-metrics): null-honest over-scope flag and deferral counters
dec295a docs(run-state-v2): pin the over_scope record on council-verdict and deferred
eb85195 test(run-state): flatten the new scope-record tests past the nesting gate
153dde0 feat(run-state): render the over-scope record in the decisions log and slice report
fe288d8 refactor(run-state): keep _over_scope_errors inside the quality gate's function metrics
9cb2903 feat(run-state): type-check the optional critique.over_scope record

## Files changed
 plugins/spec-loop/references/run-state-v2.md  |  15 +-
 plugins/spec-loop/scripts/run_metrics.py      |  38 ++++-
 plugins/spec-loop/scripts/run_state.py        | 113 +++++++++++++--
 plugins/spec-loop/scripts/test_run_metrics.py |  41 +++++-
 plugins/spec-loop/scripts/test_run_state.py   | 200 ++++++++++++++++++++++++++
 scripts/coverage_omit.txt                     |   4 +-
 6 files changed, 391 insertions(+), 20 deletions(-)

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
802
],
[
810,
811
],
[
828,
830
],
[
834,
859
],
[
1727,
1728
]
],
"plugins/spec-loop/scripts/run_state.py": [
[
93,
105
],
[
323,
324
],
[
358,
380
],
[
452,
452
],
[
457,
503
],
[
566,
566
],
[
613,
627
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
index edc5be8..a67decc 100644
--- a/plugins/spec-loop/scripts/run_metrics.py
+++ b/plugins/spec-loop/scripts/run_metrics.py
@@ -795,19 +795,22 @@ def _council_stats(parsed):
     """Verdict mix from council-verdict events, with the sidecar critique
     verdicts as a parallel per-slice view.
 
     ``safety_objections`` stays null unless at least one verdict payload
     carries a ``safety`` flag: "no payload said safety" is not evidence that no
-    SAFETY objection was raised."""
+    SAFETY objection was raised. ``over_scope_flags`` and
+    ``over_scope_deferrals`` are a record of what the council observed and
+    feed no threshold, gate or blocking decision."""
     verdict_events = _of_type(parsed["events"], "council-verdict")
     critiques = [sc["critique"] for sc in parsed["sidecars"] if sc["critique"]]
     sidecar_verdicts = [c["verdict"] for c in critiques if c["verdict"]]
     if not verdict_events and not critiques:
         return {"basis": None, "verdicts": None, "object_rate": None,
                 "safety_objections": None, "concerns_total": None,
                 "concerns_deferred": None, "by_member": None,
-                "slice_verdicts": None}
+                "slice_verdicts": None, "over_scope_flags": None,
+                "over_scope_deferrals": None}
     verdicts = [_pstr(e, "verdict") for e in verdict_events]
     verdicts = [v.upper() for v in verdicts if v and v.upper() in COUNCIL_VERDICTS]
     safety_flagged = [e for e in verdict_events
                       if isinstance(e["payload"].get("safety"), bool)]
     return {
@@ -820,13 +823,42 @@ def _council_stats(parsed):
         "concerns_total": _concerns_total(verdict_events, critiques),
         "concerns_deferred": _sum_optional(_plist_len(e, "deferred")
                                            for e in verdict_events),
         "by_member": _tally(_pstr(e, "member") for e in verdict_events) or None,
         "slice_verdicts": _tally(sidecar_verdicts) or None,
+        "over_scope_flags": _flag_count(verdict_events, "over_scope"),
+        "over_scope_deferrals": _marked_count(
+            _of_type(parsed["events"], "deferred"), "over_scope"),
     }
 
 
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
@@ -1690,10 +1722,12 @@ def _legacy_safety(events, escalations, decisions, observed):
             "safety_objections": safety_objections if council else None,
             "concerns_total": None,
             "concerns_deferred": None,
             "by_member": None,
             "slice_verdicts": None,
+            "over_scope_flags": None,
+            "over_scope_deferrals": None,
         },
         "reversibility_mix": _tally(e["reversibility"] for e in events) or None,
         "precedent_reuse": {"count": precedent if decisions else None,
                             "rate": _ratio(precedent, len(decisions))},
     }
diff --git a/plugins/spec-loop/scripts/run_state.py b/plugins/spec-loop/scripts/run_state.py
index 3524503..8a9cf6b 100644
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
@@ -305,10 +318,12 @@ def validate_sidecar(body):
 
     critique = body.get("critique")
     if isinstance(critique, dict) and critique.get("verdict") not in VERDICTS:
         errors.append("critique.verdict must be one of %s (found %r)"
                       % ("/".join(VERDICTS), critique.get("verdict")))
+    if isinstance(critique, dict):
+        errors.extend(_over_scope_errors(critique.get("over_scope")))
     quality = body.get("quality")
     if isinstance(quality, dict) and quality.get("status") not in QUALITY_STATUSES:
         errors.append("quality.status must be one of %s (found %r)"
                       % ("/".join(QUALITY_STATUSES), quality.get("status")))
     split = body.get("split")
@@ -338,10 +353,33 @@ def validate_sidecar(body):
         if not body.get("escalations"):
             errors.append("ESCALATED requires a non-empty escalations list")
     return errors
 
 
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
+    return errors
+
+
 # --------------------------------------------------------------------------
 # renderers — pure
 # --------------------------------------------------------------------------
 
 def _ordered_options(record):
@@ -409,22 +447,62 @@ def _summarize(event):
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
 
 
@@ -483,13 +561,11 @@ def render_report(body):
         add("Quality gate", "%s%s" % (quality["status"],
                                       " — %s" % _one_line(quality.get("detail"))
                                       if quality.get("detail") else ""))
     critique = body.get("critique") if isinstance(body.get("critique"), dict) else {}
     if critique.get("verdict"):
-        add("Iron Council", "%s%s" % (critique["verdict"],
-                                      " (%s concerns)" % critique["concerns"]
-                                      if critique.get("concerns") else ""))
+        add("Iron Council", _council_summary(critique))
     review = body.get("review") if isinstance(body.get("review"), dict) else {}
     if review:
         parts = []
         for key, label in (("confirmed", "confirmed"), ("refuted", "refuted"),
                            ("evidence_failed", "evidence-failed"),
@@ -532,10 +608,25 @@ def render_report(body):
     lines += ["", "_Rendered from slice-%s-status.json; that sidecar is "
                  "authoritative._" % slice_id, ""]
     return "\n".join(lines)
 
 
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
+
+
 # --------------------------------------------------------------------------
 # events
 # --------------------------------------------------------------------------
 
 def events_path(run_dir):
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
index ee0fc33..66b3243 100644
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
+        rs.append_event(self.run_dir, TS, "s1", "deferred",
+                        {"title": "dashboard charts", "over_scope": True})
+        self.assertEqual(self.events()[0]["payload"],
+                         {"title": "dashboard charts", "over_scope": True})
+        self.assertIn("DEFERRED: SCOPE dashboard charts",
+                      self.read("decisions-log.md"))
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
index f4d8262..b3a4f7b 100644
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
+scripts/run_metrics.py:2074-2075         # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/run_state.py:928-929             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/spec_loop_guard.py:240-241       # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/validate_marketplace.py:417-418  # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
 scripts/worktrees.py:385-386             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
