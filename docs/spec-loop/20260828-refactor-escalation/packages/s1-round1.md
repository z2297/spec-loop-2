# Review package: d67cff6e255fc363e93cea410e0d7bc2cff1aae6..3a07ef4  (context: -U5)

## Commits
3a07ef4 spec-loop(20260828-refactor-escalation): document refactor_radius in the quality-gate command
bd9c672 spec-loop(20260828-refactor-escalation): merge refactor_radius key-wise across the repo overlay
e0a9fe7 spec-loop(20260828-refactor-escalation): add default-on refactor_radius config block

## Files changed
 plugins/spec-loop/commands/quality-gate.md     |  36 ++++++-
 plugins/spec-loop/scripts/quality_gate.py      |  60 ++++++++++--
 plugins/spec-loop/scripts/test_quality_gate.py | 130 +++++++++++++++++++++++++
 3 files changed, 213 insertions(+), 13 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"plugins/spec-loop/commands/quality-gate.md": [
[
21,
22
],
[
42,
42
],
[
53,
63
],
[
86,
91
],
[
102,
107
],
[
127,
131
]
],
"plugins/spec-loop/scripts/quality_gate.py": [
[
19,
24
],
[
83,
95
],
[
227,
242
],
[
249,
255
],
[
270,
276
],
[
281,
282
],
[
286,
286
]
],
"plugins/spec-loop/scripts/test_quality_gate.py": [
[
334,
371
],
[
421,
477
],
[
498,
532
]
]
}
```

## Diff
diff --git a/plugins/spec-loop/commands/quality-gate.md b/plugins/spec-loop/commands/quality-gate.md
index a1ae3b5..4335c5d 100644
--- a/plugins/spec-loop/commands/quality-gate.md
+++ b/plugins/spec-loop/commands/quality-gate.md
@@ -16,11 +16,12 @@ the config and never measures code or triggers slice work.
 
 ## Steps
 
 1. **Locate / read current config.** If `~/.claude/spec-loop-2/quality-gate.json`
    exists, show its current values (thresholds, `measurement`, `enabled`, `custom_gates`,
-   `tier3_surfaces`, `models`) and stop here unless the user wants changes. If not, this
+   `tier3_surfaces`, `models`, `refactor_radius`) and stop here unless the user wants
+   changes. If not, this
    is first-time setup — and if `~/.claude/spec-loop/quality-gate.json` (spec-loop v1)
    exists, offer **import** as the first option of the step-2 question:
    - **Import from v1** — read the v1 file and carry `enabled`, `measurement`,
      `thresholds`, and `custom_gates` over verbatim; drop `refactor_attempts` (see the
      migration note in step 5) and fill the v2-only keys with the defaults below. Never
@@ -36,21 +37,32 @@ the config and never measures code or triggers slice work.
      nesting_depth 4, class_lines 400, crap 40`
    - **Customize** — walk the thresholds in batches (≤4 questions per round),
      recommended value first, "Other" for exact numbers; also ask `enabled` (default
      true). Do not offer a fix-round or `refactor_attempts` question: v2's wave workflow
      caps fix rounds itself (step 5).
-3. **The two v2 knobs** (one batched round, recommended value first):
+3. **The three v2 knobs** (one batched round, recommended value first):
    - **`tier3_surfaces`** — globs whose presence in a slice's diff deterministically
      promotes that slice's *review* tier to 3 (two-reviewer panel, session model on the
      correctness lane), regardless of the tier the controller assigned. Default
      `["**/auth/**", "**/migrations/**", "**/*.sql", "**/security/**"]`; offer the
      default, "add to it", or a replacement list. This is a review-depth control, not a
      threshold — it never changes what the gate measures.
    - **`models.reviewer`** — `"sonnet"` (default: reviews at risk tier 1–2 run on
      Sonnet) or `"inherit"` (promote them to the session model — stronger reviews, more
      cost). Tier 3 always runs the panel with the session model, so this knob only
      moves the default tiers.
+   - **`refactor_radius`** — the plan-time ceiling on how much EXISTING code one slice
+     may declare it will rewrite. Ships **on**: `{ "enabled": true, "max_rewrite_ratio":
+     0.5, "max_touched_existing_files": 8, "min_rewritten_lines": 150 }`. `max_rewrite_ratio`
+     is declared rewritten-existing-lines ÷ total declared changed lines;
+     `max_touched_existing_files` counts pre-existing files the plan says it will modify;
+     `min_rewritten_lines` is a noise floor below which the check does not fire at all, so a
+     high ratio over a dozen lines is never a halt. Offer the defaults, "tune the numbers",
+     or `enabled: false`. These are **declared** numbers, a proxy the planner states before
+     implementation — not a measured diff — so they cannot catch a blowup discovered
+     mid-implementation. A missing or non-numeric value is a "not measured" state and never
+     a zero.
 4. **Custom gates.** Offer **metric gates only** — `{ "name", "metric", "threshold" }`,
    evaluated by `quality_gate.py` against the measured values, and genuinely blocking.
    **v2.0.0 does not execute command-form gates** (`{ "name", "command", "pass_when" }`):
    the schema still accepts them and the script lists them under `skipped` as
    command-form, but nothing runs them — executing them is a roadmap item. Never offer to
@@ -69,20 +81,32 @@ the config and never measures code or triggers slice work.
        "parameter_count": 4,
        "nesting_depth": 3,
        "class_lines": 300,
        "crap_score": 30
      },
+     "refactor_radius": {
+       "enabled": true,
+       "max_rewrite_ratio": 0.5,
+       "max_touched_existing_files": 8,
+       "min_rewritten_lines": 150
+     },
      "tier3_surfaces": ["**/auth/**", "**/migrations/**", "**/*.sql", "**/security/**"],
      "models": { "reviewer": "sonnet" },
      "custom_gates": []
    }
    ```
    `measurement: "hybrid"` = real analyzer when installed, else clearly-labelled
    heuristics; `crap_score` is skipped with a note when no coverage report exists.
    `quality_gate.py` measures against `enabled`, `thresholds`, and `custom_gates`, and
    passes every other key (`tier3_surfaces`, `models`, `measurement`, …) straight through
    to `--print-config`, which is how the controller reads them — one file, one door.
+   `refactor_radius` is one of those pass-through keys with one difference: the script
+   normalizes it against its shipped defaults, so `--print-config` always reports all four
+   of its keys even when the file names none or only one. The script never evaluates the
+   block — it is the plan stage's pre-execution ceiling, and a `refactor_radius` value that
+   is present but not a JSON object is a hard error (exit 2), never a silently ignored
+   setting.
 
    **Migration from v1:** `refactor_attempts` is gone. v1 used it to bound the refactor
    loop; v2's wave workflow caps a slice at 2 fix rounds and then escalates, so the key
    would have been decoration. An imported v1 config may still carry it — harmless, and
    dropping it on write is correct. Say so when importing, so nobody expects a raised
@@ -98,13 +122,15 @@ keys it changes. The merge is `quality_gate.py`'s own, not something a caller re
 ```
 python3 quality_gate.py --config ~/.claude/spec-loop-2/quality-gate.json \
                         --overlay .spec-loop/quality-gate.json --print-config
 ```
 
-`--overlay` deep-merges over `--config` — `thresholds` keys override, `tier3_surfaces`
-**unions** (an overlay extends the surface list, it can never remove a surface),
-`custom_gates` concatenate, every other key overrides — and the provenance is always
+`--overlay` deep-merges over `--config` — `thresholds` keys override, `refactor_radius`
+keys override **key-wise** (a repo that tunes one radius number keeps the global block's
+other keys; a wholesale replacement would silently hand it defaults it never chose),
+`tier3_surfaces` **unions** (an overlay extends the surface list, it can never remove a
+surface), `custom_gates` concatenate, every other key overrides — and the provenance is always
 reported: `loaded+overlay`, or `defaults+overlay` when no global config exists, in the
 measurement report's `config` field and in `--print-config`'s `source` field. So a reader
 can always tell an overlay was in play. `--print-config` prints the effective merged
 config as JSON and exits 0: that is the single door through which the controller
 reads `tier3_surfaces` and `models` before building the wave args, and the same
diff --git a/plugins/spec-loop/scripts/quality_gate.py b/plugins/spec-loop/scripts/quality_gate.py
index cdabc03..a60f537 100644
--- a/plugins/spec-loop/scripts/quality_gate.py
+++ b/plugins/spec-loop/scripts/quality_gate.py
@@ -14,13 +14,16 @@ Pipeline:
   1. Changed-code discovery -- `git diff --unified=0 <base>..<head>` in
      --repo-dir; parse_diff() (a PURE function) turns the hunk headers into
      {file: [(start, end), ...]} added/modified line ranges. Deleted files and
      binary hunks are skipped so only surviving, changed code is measured.
   2. Config -- read the JSON config (schema in commands/quality-gate.md). A
-     missing file falls back to DEFAULT_THRESHOLDS and records
-     "config": "defaults"; `enabled: false` short-circuits to
-     {"skipped": "gate disabled"} and exit 0.
+     missing file falls back to DEFAULT_THRESHOLDS + DEFAULT_REFACTOR_RADIUS
+     and records "config": "defaults"; `enabled: false` short-circuits to
+     {"skipped": "gate disabled"} and exit 0. `refactor_radius` is carried
+     through as configuration only -- this script never evaluates it; it is the
+     plan stage's pre-execution ceiling, read by the controller through
+     --print-config.
   3. Backends -- detected via shutil.which (never installed). `lizard`
      (multi-language) is preferred for CCN / NLOC / parameter count / function
      spans; for .py files, `radon cc -j` is used when lizard is absent. A
      function is measured only when its line span intersects a changed range.
   4. Builtin heuristic -- for any changed file no backend covers, a pure-stdlib
@@ -75,10 +78,23 @@ DEFAULT_THRESHOLDS = {
     "nesting_depth": 3,
     "class_lines": 300,
     "crap_score": 30,
 }
 
+# The planner-declared refactor-radius proxy. These are NOT measured metrics:
+# they are the ceiling the plan stage declares it will stay under, checked
+# before implementation effort is spent. Shipped default-ON with deliberately
+# conservative numbers -- a checkpoint that fires on an ordinary slice would be
+# trained away within a run, so the floor (min_rewritten_lines) exists to keep
+# small slices entirely out of the check rather than to soften its answer.
+DEFAULT_REFACTOR_RADIUS = {
+    "enabled": True,
+    "max_rewrite_ratio": 0.5,
+    "max_touched_existing_files": 8,
+    "min_rewritten_lines": 150,
+}
+
 # Metrics measured per changed function (as opposed to per file/class).
 _FUNCTION_METRICS = (
     "cyclomatic_complexity",
     "cognitive_complexity",
     "method_lines",
@@ -206,21 +222,39 @@ def _read_config_object(path, what):
     if not isinstance(raw, dict):
         raise GateError(f"{what} {path!r} must be a JSON object")
     return raw
 
 
+def _radius_object(value, what):
+    """Coerce a raw `refactor_radius` config value to a plain dict. (PURE)
+
+    An absent block yields {} so the defaults stand. A PRESENT non-object is a
+    hard error rather than a silently ignored value: dropping a list or a bare
+    number here would leave the operator believing they had set a ceiling they
+    had not, which is exactly the silent-exclusion failure this block exists to
+    avoid.
+    """
+    if value is None:
+        return {}
+    if not isinstance(value, dict):
+        raise GateError(f"{what} key 'refactor_radius' must be a JSON object")
+    return dict(value)
+
+
 def load_config(path, overlay_path=None):
     """Load the gate config, returning (config_dict, source). source is
     "defaults", "loaded", or "loaded+overlay". A missing file (or None path)
     yields the documented defaults.
 
     The per-repo overlay (committed `.spec-loop/quality-gate.json`) deep-merges
-    over the global config: threshold keys override, `tier3_surfaces` unions
-    (the overlay extends, it cannot remove a surface), `custom_gates` concat,
-    other keys override. Both files predate the run — the guard hook denies
-    writes to either while a run is active — so any loosening in an overlay is
-    a deliberate, committed human choice, visible in review.
+    over the global config: threshold keys override, `refactor_radius` keys
+    override KEY-WISE (tuning one number never drops its siblings),
+    `tier3_surfaces` unions (the overlay extends, it cannot remove a surface),
+    `custom_gates` concat, other keys override. Both files predate the run —
+    the guard hook denies writes to either while a run is active — so any
+    loosening in an overlay is a deliberate, committed human choice, visible
+    in review.
     """
     raw = {} if not path or not os.path.exists(path) else _read_config_object(path, "config")
     source = "defaults" if not raw else "loaded"
     if overlay_path and os.path.exists(overlay_path):
         overlay = _read_config_object(overlay_path, "overlay")
@@ -231,17 +265,27 @@ def load_config(path, overlay_path=None):
         merged["thresholds"] = merged_thresholds
         merged["custom_gates"] = (raw.get("custom_gates") or []) + (overlay.get("custom_gates") or [])
         merged["tier3_surfaces"] = sorted(
             set(raw.get("tier3_surfaces") or []) | set(overlay.get("tier3_surfaces") or [])
         )
+        # refactor_radius merges KEY-WISE, like thresholds and unlike the
+        # dict.update() fall-through above. A repo overlay that tunes one number
+        # would otherwise replace the whole block and silently drop the other
+        # three keys, handing the operator defaults they never chose.
+        merged_radius = _radius_object(raw.get("refactor_radius"), "config")
+        merged_radius.update(_radius_object(overlay.get("refactor_radius"), "overlay"))
+        merged["refactor_radius"] = merged_radius
         raw = merged
         source = ("loaded+overlay" if source == "loaded" else "defaults+overlay")
     thresholds = dict(DEFAULT_THRESHOLDS)
     thresholds.update(raw.get("thresholds") or {})
+    refactor_radius = dict(DEFAULT_REFACTOR_RADIUS)
+    refactor_radius.update(_radius_object(raw.get("refactor_radius"), "config"))
     config = {
         "enabled": raw.get("enabled", True),
         "thresholds": thresholds,
+        "refactor_radius": refactor_radius,
         "custom_gates": raw.get("custom_gates") or [],
     }
     # Pass through controller-consumed keys (tier3_surfaces, models, …) so
     # --print-config is the one door to the effective configuration.
     for key, value in raw.items():
diff --git a/plugins/spec-loop/scripts/test_quality_gate.py b/plugins/spec-loop/scripts/test_quality_gate.py
index 4cab26d..6e180b0 100644
--- a/plugins/spec-loop/scripts/test_quality_gate.py
+++ b/plugins/spec-loop/scripts/test_quality_gate.py
@@ -329,10 +329,48 @@ class TestLoadConfig(unittest.TestCase):
             path = fh.name
         self.addCleanup(os.unlink, path)
         with self.assertRaises(qg.GateError):
             qg.load_config(path)
 
+    def test_defaults_carry_the_full_default_on_refactor_radius_block(self):
+        cfg, src = qg.load_config(None)
+        self.assertEqual(src, "defaults")
+        self.assertEqual(cfg["refactor_radius"], qg.DEFAULT_REFACTOR_RADIUS)
+        self.assertTrue(cfg["refactor_radius"]["enabled"])
+
+    def test_a_partial_refactor_radius_block_keeps_its_unmentioned_sibling_keys(self):
+        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
+            json.dump({"refactor_radius": {"max_rewrite_ratio": 0.25}}, fh)
+            path = fh.name
+        self.addCleanup(os.unlink, path)
+        cfg, _ = qg.load_config(path)
+        self.assertEqual(cfg["refactor_radius"]["max_rewrite_ratio"], 0.25)
+        self.assertEqual(cfg["refactor_radius"]["max_touched_existing_files"],
+                         qg.DEFAULT_REFACTOR_RADIUS["max_touched_existing_files"])
+        self.assertEqual(cfg["refactor_radius"]["min_rewritten_lines"],
+                         qg.DEFAULT_REFACTOR_RADIUS["min_rewritten_lines"])
+        self.assertTrue(cfg["refactor_radius"]["enabled"])
+
+    def test_a_refactor_radius_block_can_be_switched_off_by_the_operator(self):
+        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
+            json.dump({"refactor_radius": {"enabled": False}}, fh)
+            path = fh.name
+        self.addCleanup(os.unlink, path)
+        cfg, _ = qg.load_config(path)
+        self.assertFalse(cfg["refactor_radius"]["enabled"])
+        self.assertEqual(cfg["refactor_radius"]["max_rewrite_ratio"],
+                         qg.DEFAULT_REFACTOR_RADIUS["max_rewrite_ratio"])
+
+    def test_a_non_object_refactor_radius_in_the_config_is_a_hard_error(self):
+        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
+            json.dump({"refactor_radius": [0.5]}, fh)
+            path = fh.name
+        self.addCleanup(os.unlink, path)
+        with self.assertRaises(qg.GateError) as ctx:
+            qg.load_config(path)
+        self.assertIn("refactor_radius", str(ctx.exception))
+
     def _tmp_json(self, obj):
         with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
             json.dump(obj, fh)
         self.addCleanup(os.unlink, fh.name)
         return fh.name
@@ -378,10 +416,67 @@ class TestLoadConfig(unittest.TestCase):
             fh.write("{not json")
         self.addCleanup(os.unlink, fh.name)
         with self.assertRaises(qg.GateError):
             qg.load_config(base, fh.name)
 
+    def test_an_overlay_tuning_one_radius_number_does_not_drop_its_siblings(self):
+        base = self._tmp_json({
+            "refactor_radius": {"enabled": True, "max_rewrite_ratio": 0.4,
+                                "max_touched_existing_files": 6,
+                                "min_rewritten_lines": 120},
+        })
+        overlay = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.3}})
+        cfg, src = qg.load_config(base, overlay)
+        self.assertEqual(src, "loaded+overlay")
+        self.assertEqual(cfg["refactor_radius"], {
+            "enabled": True,
+            "max_rewrite_ratio": 0.3,
+            "max_touched_existing_files": 6,
+            "min_rewritten_lines": 120,
+        })
+
+    def test_an_overlay_radius_key_over_a_global_without_the_block_keeps_defaults(self):
+        base = self._tmp_json({"thresholds": {"method_lines": 40}})
+        overlay = self._tmp_json({"refactor_radius": {"max_touched_existing_files": 4}})
+        cfg, _ = qg.load_config(base, overlay)
+        self.assertEqual(cfg["refactor_radius"]["max_touched_existing_files"], 4)
+        self.assertEqual(cfg["refactor_radius"]["max_rewrite_ratio"],
+                         qg.DEFAULT_REFACTOR_RADIUS["max_rewrite_ratio"])
+        self.assertEqual(cfg["refactor_radius"]["min_rewritten_lines"],
+                         qg.DEFAULT_REFACTOR_RADIUS["min_rewritten_lines"])
+
+    def test_a_non_object_refactor_radius_in_the_overlay_is_a_hard_error(self):
+        base = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.4}})
+        overlay = self._tmp_json({"refactor_radius": 0.9})
+        with self.assertRaises(qg.GateError) as ctx:
+            qg.load_config(base, overlay)
+        self.assertIn("refactor_radius", str(ctx.exception))
+
+    def test_a_non_object_refactor_radius_in_the_base_is_a_hard_error_under_an_overlay(self):
+        base = self._tmp_json({"refactor_radius": ["nope"]})
+        overlay = self._tmp_json({"thresholds": {"method_lines": 40}})
+        with self.assertRaises(qg.GateError):
+            qg.load_config(base, overlay)
+
+    def test_print_config_surfaces_the_merged_refactor_radius_block(self):
+        base = self._tmp_json({"refactor_radius": {"max_touched_existing_files": 6}})
+        overlay = self._tmp_json({"refactor_radius": {"max_rewrite_ratio": 0.3}})
+        proc = subprocess.run(
+            [sys.executable, os.path.join(os.path.dirname(__file__), "quality_gate.py"),
+             "--config", base, "--overlay", overlay, "--print-config"],
+            capture_output=True, text=True,
+        )
+        self.assertEqual(proc.returncode, 0, proc.stderr)
+        out = json.loads(proc.stdout)
+        self.assertEqual(out["source"], "loaded+overlay")
+        self.assertEqual(out["config"]["refactor_radius"], {
+            "enabled": True,
+            "max_rewrite_ratio": 0.3,
+            "max_touched_existing_files": 6,
+            "min_rewritten_lines": qg.DEFAULT_REFACTOR_RADIUS["min_rewritten_lines"],
+        })
+
     def test_print_config_cli(self):
         base = self._tmp_json({"tier3_surfaces": ["**/auth/**"]})
         proc = subprocess.run(
             [sys.executable, os.path.join(os.path.dirname(__file__), "quality_gate.py"),
              "--config", base, "--print-config"],
@@ -398,10 +493,45 @@ class TestLoadConfig(unittest.TestCase):
             capture_output=True, text=True,
         )
         self.assertEqual(proc.returncode, 2)
 
 
+# --------------------------------------------------------------------------
+# Command-doc single-home pin. commands/quality-gate.md is the ONE operator-
+# facing home of the config schema; when it and the defaults disagree, one of
+# them is wrong, and this catches the drift in the same suite that owns the
+# defaults.
+# --------------------------------------------------------------------------
+
+COMMAND_DOC = (Path(__file__).resolve().parents[1] / "commands" / "quality-gate.md")
+
+
+class TestCommandDocDocumentsRefactorRadius(unittest.TestCase):
+    def setUp(self):
+        self.doc = COMMAND_DOC.read_text(encoding="utf-8")
+
+    def test_every_refactor_radius_key_is_named_in_the_command_doc(self):
+        for key in qg.DEFAULT_REFACTOR_RADIUS:
+            with self.subTest(key=key):
+                self.assertIn(key, self.doc)
+
+    def test_the_step_one_key_list_names_the_block(self):
+        step_one = self.doc.split("2. **Choose a quality level**")[0]
+        self.assertIn("refactor_radius", step_one)
+
+    def test_the_written_schema_carries_the_shipped_default_numbers(self):
+        schema = self.doc.split("```json")[1].split("```")[0]
+        self.assertIn('"refactor_radius"', schema)
+        for key, value in qg.DEFAULT_REFACTOR_RADIUS.items():
+            with self.subTest(key=key):
+                literal = {True: "true", False: "false"}.get(value, str(value))
+                self.assertIn(f'"{key}": {literal}', schema)
+
+    def test_the_doc_states_the_block_is_a_declared_proxy_not_a_measured_diff(self):
+        self.assertIn("proxy", self.doc.lower())
+
+
 # --------------------------------------------------------------------------
 # Pure metric primitives
 # --------------------------------------------------------------------------
 
 class TestCountParams(unittest.TestCase):
