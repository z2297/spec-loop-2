# Review package: cb59858..ba3e2f8  (context: -U5)

## Commits
ba3e2f8 fix(ado): reflow paren-aligned continuations that mis-score as nesting

## Files changed
 plugins/spec-loop/scripts/ado_intake.py      |  58 +++++----
 plugins/spec-loop/scripts/test_ado_intake.py | 175 +++++++++++++++------------
 2 files changed, 133 insertions(+), 100 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/scripts/ado_intake.py": [
[
604,
617
],
[
620,
623
],
[
665,
668
],
[
875,
888
]
],
"plugins/spec-loop/scripts/test_ado_intake.py": [
[
68,
68
],
[
84,
84
],
[
88,
88
],
[
190,
207
],
[
213,
214
],
[
216,
216
],
[
229,
230
],
[
233,
234
],
[
237,
241
],
[
245,
246
],
[
249,
254
],
[
257,
259
],
[
261,
262
],
[
265,
268
],
[
271,
277
],
[
288,
289
],
[
332,
334
],
[
337,
338
],
[
341,
346
],
[
351,
351
],
[
354,
355
],
[
360,
361
],
[
364,
365
],
[
486,
489
],
[
491,
494
],
[
505,
506
],
[
555,
557
],
[
575,
576
],
[
581,
583
],
[
592,
593
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/scripts/ado_intake.py b/plugins/spec-loop/scripts/ado_intake.py
index cf684a4..0439235 100644
--- a/plugins/spec-loop/scripts/ado_intake.py
+++ b/plugins/spec-loop/scripts/ado_intake.py
@@ -599,19 +599,30 @@ def render_comment(triple, kind, payload, ts):
         "Recorded %s by /spec-loop:ado-intake." % ts,
         payload,
     ])
 
 
+def _criterion_line(item):
+    """One acceptance-criterion bullet, escaped. (PURE)"""
+    return "- %s" % escape_for_comment(item)
+
+
+def _risk_line(risk):
+    """One risk bullet, escaped. (PURE)"""
+    return "- [%s] %s: %s" % (
+        escape_for_comment(risk["severity"]),
+        escape_for_comment(risk["id"]),
+        escape_for_comment(risk["risk"]),
+    )
+
+
 def _understanding_payload(refinement):
     """The confirmed-understanding comment's payload, escaped. (PURE)"""
-    criteria = "\n".join("- %s" % escape_for_comment(item)
-                         for item in refinement["acceptance_criteria"])
-    risks = "\n".join(
-        "- [%s] %s: %s" % (escape_for_comment(risk["severity"]),
-                           escape_for_comment(risk["id"]),
-                           escape_for_comment(risk["risk"]))
-        for risk in refinement["risks"])
+    criteria = "\n".join(
+        _criterion_line(item) for item in refinement["acceptance_criteria"]
+    )
+    risks = "\n".join(_risk_line(risk) for risk in refinement["risks"])
     blocks = ["Description", escape_for_comment(refinement["description"]),
               "Acceptance criteria", criteria or "- (none stated)",
               "Risks", risks or "- (none identified)"]
     return "\n\n".join(blocks)
 
@@ -649,14 +660,14 @@ def _duplicate_marker_errors(entries):
     marker collapses them. Refuse the batch here, before the first
     request."""
     seen = set()
     errors = []
     for entry in entries:
-        if entry["marker"] in seen:
-            errors.append("two comments share the dedupe marker %s"
-                          % entry["marker"])
-        seen.add(entry["marker"])
+        marker = entry["marker"]
+        if marker in seen:
+            errors.append("two comments share the dedupe marker %s" % marker)
+        seen.add(marker)
     return errors
 
 
 def build_comment_bodies(record, refinement, ts):
     """Every comment this intake WOULD post, in order. Posts nothing. (PURE)
@@ -859,21 +870,24 @@ def build_parser():
 def _render_payload(args):
     """Build the success payload for `render`. Writes nothing."""
     record = _load_json(args.record, "record")
     refinement = _load_json(args.refinement, "refinement")
     _require_valid_record(record)
-    org, project, work_item_id = record_triple(record)
-    return {"ok": True,
-            "work_item_org": org,
-            "work_item_project": project,
-            "work_item_id": work_item_id,
-            "artifact_path": artifact_path(
-                (org, project, work_item_id), args.artifact_root),
-            "artifact": render_artifact(record, refinement, args.ts),
-            "comments": build_comment_bodies(record, refinement, args.ts),
-            "ranked_gaps": rank_gaps(refinement["gaps"]),
-            "posted": False}
+    triple = record_triple(record)
+    org, project, work_item_id = triple
+    path = artifact_path(triple, args.artifact_root)
+    return {
+        "ok": True,
+        "work_item_org": org,
+        "work_item_project": project,
+        "work_item_id": work_item_id,
+        "artifact_path": path,
+        "artifact": render_artifact(record, refinement, args.ts),
+        "comments": build_comment_bodies(record, refinement, args.ts),
+        "ranked_gaps": rank_gaps(refinement["gaps"]),
+        "posted": False,
+    }
 
 
 def main(argv=None):
     """Entry point: 0 = ok, 1 = contract failure, 2 = usage."""
     args = build_parser().parse_args(argv)
diff --git a/plugins/spec-loop/scripts/test_ado_intake.py b/plugins/spec-loop/scripts/test_ado_intake.py
index 0322a99..3d03f2e 100644
--- a/plugins/spec-loop/scripts/test_ado_intake.py
+++ b/plugins/spec-loop/scripts/test_ado_intake.py
@@ -63,13 +63,11 @@ class TestWorkItemIdValidation(unittest.TestCase):
 
     def test_a_traversal_or_typed_id_is_refused(self):
         bad = ("../1", "1/../..", "1 ", "1\n", "", "0" * 11, "12a",
                "-1", 1234, None)
         for value in bad:
-            with self.subTest(value=value), \
-                    self.assertRaises(intake.IntakeUsageError):
-                intake.validate_work_item_id(value)
+            assert_refused(self, intake.validate_work_item_id, value)
 
 
 class TestProjectNameIsRefusedNotRewritten(unittest.TestCase):
     """A project name lands in YAML front matter and in a slug. A control
     character or line break is refused outright (jira_intake's
@@ -81,19 +79,15 @@ class TestProjectNameIsRefusedNotRewritten(unittest.TestCase):
             with self.subTest(good=good):
                 self.assertEqual(intake.validate_project_name(good), good)
 
     def test_a_control_character_or_break_is_refused(self):
         for bad in ("a\nb", "a\rb", "a\tb", "a\x00b", "", "   ", 7, None):
-            with self.subTest(bad=bad), \
-                    self.assertRaises(intake.IntakeUsageError):
-                intake.validate_project_name(bad)
+            assert_refused(self, intake.validate_project_name, bad)
 
     def test_an_org_with_a_path_segment_is_refused(self):
         for bad in ("../org", "org/x", "", "org name", None):
-            with self.subTest(bad=bad), \
-                    self.assertRaises(intake.IntakeUsageError):
-                intake.validate_org(bad)
+            assert_refused(self, intake.validate_org, bad)
 
 
 TRIPLE = ("contoso", "My Team – Platform", "1234")
 
 
@@ -191,22 +185,37 @@ class TestArtifactPathGuard(unittest.TestCase):
     def test_the_target_dir_carries_the_slug_and_the_id(self):
         discriminated = path_for_triple(TRIPLE).split("/")[1]
         self.assertEqual(intake.target_dir(TRIPLE), discriminated + "/1234")
 
 
+RISK_R1 = {
+    "id": "R1",
+    "risk": "No migration for existing rows.",
+    "severity": "high",
+}
+
+GAP_G1 = {
+    "id": "G1",
+    "question": "Which roles see the toggle?",
+    "impact": "high",
+    "blocking": True,
+}
+
+ANSWER_G1_DECISION = {
+    "G1": {"answer": "Admins only.", "logged_as": "decision"}
+}
+
+
 def make_refinement(**over):
     """A minimal valid refinement dict; keyword args override one key."""
     base = {
         "description": "Add a widget toggle to the settings pane.",
         "acceptance_criteria": ["Toggle persists across reload."],
-        "risks": [{"id": "R1", "risk": "No migration for existing rows.",
-                   "severity": "high"}],
-        "gaps": [{"id": "G1", "question": "Which roles see the toggle?",
-                  "impact": "high", "blocking": True}],
+        "risks": [RISK_R1],
+        "gaps": [GAP_G1],
         "injection_findings": [],
-        "answers": {"G1": {"answer": "Admins only.",
-                           "logged_as": "decision"}},
+        "answers": dict(ANSWER_G1_DECISION),
     }
     base.update(over)
     return base
 
 
@@ -215,67 +224,71 @@ class TestRefinementValidation(unittest.TestCase):
         self.assertEqual(intake.validate_refinement(make_refinement()), [])
 
     def test_a_missing_key_is_reported_by_name(self):
         bad = make_refinement()
         del bad["risks"]
-        self.assertEqual(intake.validate_refinement(bad),
-                         ["missing required key: risks"])
+        errors = intake.validate_refinement(bad)
+        self.assertEqual(errors, ["missing required key: risks"])
 
     def test_a_non_object_refinement_is_reported(self):
-        self.assertEqual(intake.validate_refinement(["x"]),
-                         ["refinement must be a JSON object"])
+        errors = intake.validate_refinement(["x"])
+        self.assertEqual(errors, ["refinement must be a JSON object"])
 
     def test_a_bad_impact_severity_and_blocking_are_each_reported(self):
-        bad = make_refinement(
-            gaps=[{"id": "G1", "question": "q", "impact": "urgent",
-                   "blocking": "yes"}],
-            risks=[{"id": "R1", "risk": "r", "severity": "fatal"}],
-            answers={})
+        bad_gap = {
+            "id": "G1", "question": "q", "impact": "urgent", "blocking": "yes"
+        }
+        bad_risk = {"id": "R1", "risk": "r", "severity": "fatal"}
+        bad = make_refinement(gaps=[bad_gap], risks=[bad_risk], answers={})
         errors = intake.validate_refinement(bad)
         self.assertIn("gaps[0].impact must be one of high|medium|low", errors)
         self.assertIn("gaps[0].blocking must be a boolean", errors)
-        self.assertIn("risks[0].severity must be one of high|medium|low",
-                      errors)
+        self.assertIn(
+            "risks[0].severity must be one of high|medium|low", errors)
 
     def test_a_newline_in_an_id_is_refused(self):
-        bad = make_refinement(
-            gaps=[{"id": "G\n1", "question": "q", "impact": "low",
-                   "blocking": False}], answers={})
-        self.assertIn("gaps[0].id must not contain a newline",
-                      intake.validate_refinement(bad))
+        bad_gap = {
+            "id": "G\n1", "question": "q", "impact": "low", "blocking": False
+        }
+        bad = make_refinement(gaps=[bad_gap], answers={})
+        errors = intake.validate_refinement(bad)
+        self.assertIn("gaps[0].id must not contain a newline", errors)
 
     def test_a_duplicate_gap_id_makes_an_answer_unattributable(self):
-        gap = {"id": "G1", "question": "q", "impact": "low",
-               "blocking": False}
+        gap = {
+            "id": "G1", "question": "q", "impact": "low", "blocking": False
+        }
         bad = make_refinement(gaps=[gap, dict(gap)], answers={})
-        self.assertIn("gaps have duplicate id: G1",
-                      intake.validate_refinement(bad))
+        errors = intake.validate_refinement(bad)
+        self.assertIn("gaps have duplicate id: G1", errors)
 
     def test_an_answer_with_no_matching_gap_is_reported(self):
-        bad = make_refinement(
-            answers={"G9": {"answer": None, "logged_as": "open-question"}})
-        self.assertIn("answers has no matching gap for id G9",
-                      intake.validate_refinement(bad))
+        stray = {"G9": {"answer": None, "logged_as": "open-question"}}
+        bad = make_refinement(answers=stray)
+        errors = intake.validate_refinement(bad)
+        self.assertIn("answers has no matching gap for id G9", errors)
 
     def test_a_bad_logged_as_is_reported(self):
-        bad = make_refinement(answers={"G1": {"answer": "a",
-                                              "logged_as": "note"}})
-        self.assertIn(
-            "answers[G1].logged_as must be one of decision|open-question",
-            intake.validate_refinement(bad))
+        bad_answer = {"G1": {"answer": "a", "logged_as": "note"}}
+        bad = make_refinement(answers=bad_answer)
+        errors = intake.validate_refinement(bad)
+        expected = (
+            "answers[G1].logged_as must be one of decision|open-question"
+        )
+        self.assertIn(expected, errors)
 
 
 class TestGapRanking(unittest.TestCase):
     def test_blocking_then_impact_then_id(self):
         gaps = [
             {"id": "G3", "impact": "high", "blocking": False},
             {"id": "G1", "impact": "low", "blocking": True},
             {"id": "G2", "impact": "high", "blocking": True},
             {"id": "G0", "impact": "high", "blocking": False},
         ]
-        self.assertEqual([g["id"] for g in intake.rank_gaps(gaps)],
-                         ["G2", "G1", "G0", "G3"])
+        ranked_ids = [g["id"] for g in intake.rank_gaps(gaps)]
+        self.assertEqual(ranked_ids, ["G2", "G1", "G0", "G3"])
 
     def test_ranking_does_not_mutate_the_input(self):
         gaps = [{"id": "G2", "impact": "low", "blocking": False},
                 {"id": "G1", "impact": "high", "blocking": True}]
         intake.rank_gaps(gaps)
@@ -314,41 +327,44 @@ class TestRecordValidation(unittest.TestCase):
             intake.validate_record(make_record(rendered_text="<b>x</b>")), [])
 
     def test_a_missing_key_is_reported_by_name(self):
         bad = make_record()
         del bad["repro_steps"]
-        self.assertEqual(intake.validate_record(bad),
-                         ["record is missing required key: repro_steps"])
+        errors = intake.validate_record(bad)
+        self.assertEqual(
+            errors, ["record is missing required key: repro_steps"])
 
     def test_a_none_scalar_is_reported_not_rendered(self):
-        self.assertIn("record key title must be a string",
-                      intake.validate_record(make_record(title=None)))
+        errors = intake.validate_record(make_record(title=None))
+        self.assertIn("record key title must be a string", errors)
 
     def test_comments_must_be_a_list(self):
-        self.assertIn("record key comments must be a list",
-                      intake.validate_record(make_record(comments={})))
+        errors = intake.validate_record(make_record(comments={}))
+        self.assertIn("record key comments must be a list", errors)
+
+    def assert_empty_field_reported(self, field):
+        errors = intake.validate_record(make_record(**{field: ""}))
+        self.assertIn("record key %s must not be empty" % field, errors)
 
     def test_an_empty_triple_field_is_a_half_resolve(self):
         for field in ("org", "project", "id"):
             with self.subTest(field=field):
-                self.assertIn(
-                    "record key %s must not be empty" % field,
-                    intake.validate_record(make_record(**{field: ""})))
+                self.assert_empty_field_reported(field)
 
     def test_a_numeric_id_is_refused(self):
-        self.assertIn("record key id must be a string",
-                      intake.validate_record(make_record(id=1234)))
+        errors = intake.validate_record(make_record(id=1234))
+        self.assertIn("record key id must be a string", errors)
 
     def test_require_valid_record_raises_with_every_error_joined(self):
         with self.assertRaises(intake.IntakeError) as caught:
             intake._require_valid_record(make_record(title=None))
-        self.assertIn("refusing to render from an invalid record",
-                      str(caught.exception))
+        message = str(caught.exception)
+        self.assertIn("refusing to render from an invalid record", message)
 
     def test_record_triple_is_the_validated_target(self):
-        self.assertEqual(intake.record_triple(make_record()),
-                         ("contoso", "My Team – Platform", "1234"))
+        triple = intake.record_triple(make_record())
+        self.assertEqual(triple, ("contoso", "My Team – Platform", "1234"))
 
 
 class TestTheBodyCarriesNoActiveMarkup(unittest.TestCase):
     """BLOCKING: the ADO Add-comment body has no declarable format, so the
     ADF-text-node inertness the Jira lane got for free is gone. The body is
@@ -465,29 +481,31 @@ class TestCommentBodiesAreBuiltNotPosted(unittest.TestCase):
         built = intake.build_comment_bodies(
             make_record(), make_refinement(), TS)
         self.assertEqual(built[0]["kind"], "understanding")
         self.assertIsNone(built[0]["gap_id"])
 
+    def assert_entry_shape(self, entry):
+        self.assertEqual(set(entry), {"kind", "gap_id", "marker", "body"})
+        self.assertTrue(entry["body"].startswith(entry["marker"]))
+
     def test_each_entry_has_exactly_the_pinned_keys(self):
-        for entry in intake.build_comment_bodies(
-                make_record(), make_refinement(), TS):
-            self.assertEqual(set(entry),
-                             {"kind", "gap_id", "marker", "body"})
-            self.assertTrue(entry["body"].startswith(entry["marker"]))
+        built = intake.build_comment_bodies(
+            make_record(), make_refinement(), TS)
+        for entry in built:
+            self.assert_entry_shape(entry)
 
     def test_an_answered_gap_is_a_decision(self):
         built = intake.build_comment_bodies(
             make_record(), make_refinement(), TS)
         gap_entry = built[1]
         self.assertEqual(gap_entry["kind"], "decision")
         self.assertEqual(gap_entry["gap_id"], "G1")
         self.assertIn("Admins only.", gap_entry["body"])
 
     def test_an_unanswered_gap_is_an_open_question(self):
-        refinement = make_refinement(
-            answers={"G1": {"answer": None,
-                            "logged_as": "open-question"}})
+        open_answer = {"G1": {"answer": None, "logged_as": "open-question"}}
+        refinement = make_refinement(answers=open_answer)
         built = intake.build_comment_bodies(make_record(), refinement, TS)
         self.assertEqual(built[1]["kind"], "open-question")
         self.assertIn("Open question (G1", built[1]["body"])
 
     def test_a_decision_logged_as_with_no_answer_degrades_to_open_question(self):
@@ -532,12 +550,13 @@ class TestCommentBodiesAreBuiltNotPosted(unittest.TestCase):
             ["two comments share the dedupe marker [m]"])
 
 
 class TestArtifactRendering(unittest.TestCase):
     def artifact(self, record=None, refinement=None):
-        return intake.render_artifact(record or make_record(),
-                                      refinement or make_refinement(), TS)
+        record = record or make_record()
+        refinement = refinement or make_refinement()
+        return intake.render_artifact(record, refinement, TS)
 
     def test_the_front_matter_holds_every_pinned_field_in_order(self):
         lines = self.artifact().split("\n")
         self.assertEqual(lines[0], "---")
         names = [line.split(":", 1)[0]
@@ -551,29 +570,29 @@ class TestArtifactRendering(unittest.TestCase):
         self.assertIn('work_item_project: "My Team – Platform"', art)
         self.assertIn('work_item_id: "1234"', art)
 
     def test_counts_are_bare_numbers_not_strings(self):
         art = self.artifact()
-        self.assertIn("schema_version: %d" % intake.ARTIFACT_SCHEMA_VERSION,
-                      art)
+        version_line = "schema_version: %d" % intake.ARTIFACT_SCHEMA_VERSION
+        self.assertIn(version_line, art)
         self.assertIn("gap_count: 1", art)
         self.assertIn("open_question_count: 0", art)
 
     def test_an_open_question_is_counted(self):
-        art = self.artifact(refinement=make_refinement(
-            answers={"G1": {"answer": None,
-                            "logged_as": "open-question"}}))
+        open_answer = {"G1": {"answer": None, "logged_as": "open-question"}}
+        refinement = make_refinement(answers=open_answer)
+        art = self.artifact(refinement=refinement)
         self.assertIn("open_question_count: 1", art)
 
     def test_a_colon_space_project_name_stays_a_single_scalar(self):
         art = self.artifact(make_record(project="Ops: Platform"))
         self.assertIn('work_item_project: "Ops: Platform"', art)
 
     def test_every_section_heading_is_present_in_order(self):
         art = self.artifact()
-        positions = [art.index(section)
-                     for section in intake.ARTIFACT_SECTIONS]
+        sections = intake.ARTIFACT_SECTIONS
+        positions = [art.index(section) for section in sections]
         self.assertEqual(positions, sorted(positions))
 
     def test_work_item_text_cannot_forge_the_front_matter_delimiter(self):
         art = self.artifact(refinement=make_refinement(
             description="intro\n---\noutro"))
