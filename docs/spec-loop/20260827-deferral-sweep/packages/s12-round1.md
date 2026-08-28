# Review package: ac283ad159dbc7e9d94ae614cd24643a6459a07d..3006fbc  (context: -U5)

## Commits
3006fbc test(coverage-gate): pin the resolved __main__ block size so the manifest guard can fail
8a6e02d polish: fix awkward mid-sentence line wrap in test module docstring
c48d3ce docs(spec-loop): record s12 round-2 measured results
fb3d2a0 refactor(coverage-gate): split the shim resolver into header and block helpers
34b66fa fix(quality-gate): split manifest tests out of test_measure_coverage.py; unbend nesting-depth false positive
1891617 T4: flatten a paren-aligned continuation the nesting heuristic misreads
ffb4a25 T4: match the escalation identity anchor as a whole line
12548d4 T3: resolve shim omissions by pattern and re-express the manifest
3326697 T2: parse and resolve a symbolic __main__ OMIT token
5849716 T1: resolve a __main__ entry shim from source by pattern

## Files changed
 .../20260827-deferral-sweep/slice-s12-report.md    | 263 +++++++++++++++++++++
 plugins/spec-loop/scripts/run_state.py             |   6 +-
 plugins/spec-loop/scripts/test_run_state.py        |  37 +++
 scripts/coverage_omit.txt                          |  78 +++---
 scripts/measure_coverage.py                        | 136 +++++++++--
 scripts/test_measure_coverage.py                   |  40 +++-
 scripts/test_measure_coverage_manifest.py          | 120 ++++++++++
 7 files changed, 623 insertions(+), 57 deletions(-)

## Hunk index (HEAD-side changed line ranges)
```hunk-index
{
"docs/spec-loop/20260827-deferral-sweep/slice-s12-report.md": [
[
1,
263
]
],
"plugins/spec-loop/scripts/run_state.py": [
[
101,
101
],
[
563,
566
]
],
"plugins/spec-loop/scripts/test_run_state.py": [
[
527,
563
]
],
"scripts/coverage_omit.txt": [
[
3,
5
],
[
7,
17
],
[
19,
32
],
[
34,
46
]
],
"scripts/measure_coverage.py": [
[
32,
37
],
[
51,
51
],
[
87,
99
],
[
217,
282
],
[
298,
299
],
[
315,
317
],
[
319,
319
],
[
322,
323
],
[
325,
331
],
[
333,
333
],
[
338,
341
],
[
345,
356
],
[
538,
538
]
],
"scripts/test_measure_coverage.py": [
[
12,
15
],
[
93,
95
],
[
109,
139
]
],
"scripts/test_measure_coverage_manifest.py": [
[
1,
120
]
]
}
```

## Diff
diff --git a/docs/spec-loop/20260827-deferral-sweep/slice-s12-report.md b/docs/spec-loop/20260827-deferral-sweep/slice-s12-report.md
new file mode 100644
index 0000000..478e89f
--- /dev/null
+++ b/docs/spec-loop/20260827-deferral-sweep/slice-s12-report.md
@@ -0,0 +1,263 @@
+# Slice s12 — round-2 measured results
+
+Every number in this file was measured first-hand at the hash named beside it. Nothing here
+is copied from a plan, from `conventions.md`, or from an earlier commit, except the one block
+explicitly attributed to `conventions.md` in the "BEFORE" section, which says so in place.
+
+## Shipped head
+
+- Code head: `f851884` (`f8518847030ff2af267b1d6c19faa5023d45b509`)
+  — `refactor(coverage-gate): split the shim resolver into header and block helpers`
+- Slice base (branch point): `39f7a28` — `spec-loop(20260827-deferral-sweep): merge slice s9`
+- Run base (release 2.2.1): `299f0db`
+
+The commit that adds this report sits directly on top of `f851884`; it changes markdown only,
+so every measurement below still describes the shipped code.
+
+## The seven segments, at `f851884`
+
+Each was run as its own tool call from the worktree root.
+
+| # | segment | measured result |
+|---|---|---|
+| 1 | `python3 scripts/validate_marketplace.py .` | exit 0 — `OK: marketplace and all plugins valid (.)` |
+| 2 | `python3 -m unittest discover -s scripts -p 'test_*.py'` | exit 0 — `Ran 126 tests in 22.852s` / `OK` |
+| 3 | `python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'` | exit 0 — `Ran 1291 tests in 14.460s` / `OK` |
+| 4 | `python3 scripts/measure_coverage.py` | exit 0 — `suite: 1417 tests passed`, `PASS: all per-file and total floors met.` |
+| 5 | `node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs` | exit 0 — `# tests 48` / `# pass 48` / `# fail 0` |
+| 6 | `node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs` | exit 0 — `# tests 23` / `# pass 23` / `# fail 0` |
+| 7 | `claude plugin validate .` | exit 0 — `✔ Validation passed` |
+
+All seven were then run once more with this report committed on top of `f851884` — a commit
+that adds markdown and nothing else — and returned the same results: exits 0, `Ran 126` / `Ran 1291`,
+`suite: 1417 tests passed`, `# pass 48` / `# pass 23` with `# fail 0`, and a segment-4
+coverage table that `diff` reports as identical to the block pasted below.
+
+Segment 3 prints three expected stderr lines from CLI error-path tests
+(`error: provide a PR URL...`, `error: unsupported host 'gitlab.com'...`, a `git failed:`
+line from a deliberately bad ref); segment 4 reproduces them because it re-runs both suites
+under `trace`. They are exercised error paths, not failures — both segments end `OK` at exit 0.
+
+### Test-count deltas, both sides measured first-hand
+
+| suite | at `39f7a28` | at `f851884` | delta |
+|---|---|---|---|
+| segment 2 (`scripts/`) | `Ran 106 tests` / `OK` | `Ran 126 tests` / `OK` | +20 |
+| segment 3 (`plugins/spec-loop/scripts/`) | `Ran 1288 tests` / `OK` | `Ran 1291 tests` / `OK` | +3 |
+| segment 4 combined (`measure_coverage.py`) | `suite: 1394 tests passed` | `suite: 1417 tests passed` | +23 |
+
+The `39f7a28` column was measured in the primary checkout, which sits at that hash; the same
+checkout caveat given in the BEFORE coverage section below applies to it.
+
+The plan predicted 108 for segment 2. The measurement is 126, and the measurement wins: the
+plan's 108 was derived from the run base's 106 plus this task's two new tests, but the slice
+carries six earlier commits (`cb7253b`, `f8f69a1`, `dd3485e`, `4f860de`, `4fe5194`, `e10c174`)
+that also added tests. The +20 measured here is the whole slice's contribution to that suite,
+not this task's alone.
+
+## Coverage — BEFORE and AFTER
+
+**AFTER**, pasted verbatim from segment 4 at `f851884`:
+
+```
+coverage report (stdlib trace; scripts/*.py minus OMIT manifest)
+  file                                         cov     run/able  floor
+  scripts/dag.py                             99.8%   515/516       94%
+  scripts/dashboard_launcher.py             100.0%   239/239       95%
+  scripts/dashboard_server.py                99.5%   845/849       94%
+  scripts/knowledge_graph.py                 86.5%   648/749       81%
+  scripts/pr_resolver.py                    100.0%   274/274       80%
+  scripts/quality_gate.py                    93.6%   823/879       86%
+  scripts/release.py                        100.0%   125/125       95%
+  scripts/review_package.py                  94.3%    83/88        89%
+  scripts/run_metrics.py                     98.9%  1307/1322      93%
+  scripts/run_state.py                      100.0%   740/740       95%
+  scripts/spec_loop_guard.py                 92.0%   127/138       86%
+  scripts/validate_marketplace.py            99.3%   275/277       94%
+  scripts/worktrees.py                       99.6%   229/230       94%
+  TOTAL                                      96.9%  6230/6426      90%
+PASS: all per-file and total floors met.
+```
+
+**BEFORE** — a first-hand measurement of the run base `299f0db` was NOT possible. The primary
+checkout at `/Users/zachmcmurry/Documents/Repos/spec-loop-2` is at `39f7a28`, not `299f0db`
+(`git -C ... rev-parse --short HEAD` → `39f7a28`, working tree carrying an unrelated modified
+`CHANGELOG.md` and untracked run docs). This slice does not create or switch worktrees, so the
+`299f0db` tree was never on disk for it to measure.
+
+What IS measured first-hand is the slice's own base, `39f7a28` — pasted verbatim from
+`python3 scripts/measure_coverage.py` run in that checkout:
+
+```
+coverage report (stdlib trace; scripts/*.py minus OMIT manifest)
+  file                                         cov     run/able  floor
+  scripts/dag.py                             99.8%   515/516       94%
+  scripts/dashboard_launcher.py             100.0%   239/239       95%
+  scripts/dashboard_server.py                99.5%   845/849       94%
+  scripts/knowledge_graph.py                 86.5%   648/749       81%
+  scripts/pr_resolver.py                    100.0%   274/274       80%
+  scripts/quality_gate.py                    93.6%   824/880       86%
+  scripts/release.py                        100.0%   125/125       95%
+  scripts/review_package.py                  94.3%    83/88        89%
+  scripts/run_metrics.py                     98.8%  1306/1322      93%
+  scripts/run_state.py                       99.9%   739/740       95%
+  scripts/spec_loop_guard.py                 92.0%   127/138       86%
+  scripts/validate_marketplace.py            99.3%   275/277       94%
+  scripts/worktrees.py                       99.6%   229/230       94%
+  TOTAL                                      96.9%  6229/6427      90%
+PASS: all per-file and total floors met.
+```
+
+Caveat stated rather than hidden: that base run was taken with the primary checkout's
+unrelated `CHANGELOG.md` edit present. `CHANGELOG.md` is not a coverage target and no target
+module was modified there, so the tree is code-identical to `39f7a28` for coverage purposes.
+
+For the run base `299f0db` the only figures available are the three rows plus TOTAL that
+`conventions.md` records, and they are quoted here **on `conventions.md`'s authority, not on
+mine** — I did not run them: `quality_gate.py` 91.7% 638/696, `run_metrics.py` 98.6% 1303/1321,
+`run_state.py` 100.0% 671/671, `TOTAL` 96.7% 5972/6173. That is a three-file excerpt; it is
+not a full 13-file base table and is not presented as one.
+
+### Which rows moved between `39f7a28` and `f851884`, and why
+
+Three rows moved: `quality_gate.py` 824/880 → 823/879 (93.6% both sides), `run_metrics.py`
+1306/1322 → 1307/1322 (98.8% → 98.9%), `run_state.py` 739/740 → 740/740 (99.9% → 100.0%).
+TOTAL 6229/6427 → 6230/6426, 96.9% on both sides against the 90% floor. Ten rows are identical.
+
+Those are exactly the three files whose old fixed OMIT range had drifted away from their real
+entry shim, which the symbolic `__main__` token now resolves at measure time. Measured with
+the shipped resolver against each target's own source:
+
+```
+dag.py                       base-range 786-787  resolved [786, 787]  same
+dashboard_launcher.py        base-range 558-559  resolved [558, 559]  same
+dashboard_server.py          base-range 1645-1646  resolved [1645, 1646]  same
+knowledge_graph.py           base-range 1211-1212  resolved [1211, 1212]  same
+pr_resolver.py               base-range 488-489  resolved [488, 489]  same
+quality_gate.py              base-range 1118-1119  resolved [1570, 1571]  DRIFTED
+release.py                   base-range 194-195  resolved [194, 195]  same
+review_package.py            base-range 131-132  resolved [131, 132]  same
+run_metrics.py               base-range 2175-2176  resolved [2186, 2187]  DRIFTED
+run_state.py                 base-range 1104-1105  resolved [1302, 1303]  DRIFTED
+spec_loop_guard.py           base-range 250-251  resolved [250, 251]  same
+validate_marketplace.py      base-range 417-418  resolved [417, 418]  same
+worktrees.py                 base-range 385-386  resolved [385, 386]  same
+```
+
+`quality_gate.py` and `run_metrics.py` are byte-identical across this slice's diff, so their
+movement is attributable to the manifest re-expression alone. `run_state.py` has two
+contributors — the same re-expression plus its own round-1 change and the tests added with it —
+so its rise to 100.0% is not claimed for the manifest work by itself.
+
+## Complexity — BEFORE and AFTER, frozen gate
+
+Backend: the FROZEN pre-run gate, `git show 299f0db:plugins/spec-loop/scripts/quality_gate.py`,
+via `analyze_builtin` over the whole file. Thresholds: cyclomatic 10, cognitive 15,
+method_lines 50, parameter_count 4, nesting_depth 3.
+
+BEFORE, at `e10c174` (one function, over two thresholds):
+
+```
+resolve_main_shim {'cyclomatic_complexity': 11, 'method_lines': 32, 'parameter_count': 2, 'cognitive_complexity': 21, 'nesting_depth': 3}
+```
+
+AFTER, at `f851884` (three functions, all under every threshold):
+
+```
+_sole_shim_header {'cyclomatic_complexity': 4, 'method_lines': 11, 'parameter_count': 2, 'cognitive_complexity': 6, 'nesting_depth': 3}
+_guarded_block    {'cyclomatic_complexity': 4, 'method_lines': 14, 'parameter_count': 2, 'cognitive_complexity': 7, 'nesting_depth': 3}
+resolve_main_shim {'cyclomatic_complexity': 2, 'method_lines': 18, 'parameter_count': 2, 'cognitive_complexity': 2, 'nesting_depth': 3}
+```
+
+The plan's threshold-breach check over those three names returns `[]` at `f851884`.
+
+Two neighbouring functions in the same file remain over the cognitive threshold —
+`executable_lines` (cognitive 16, nesting_depth 4) and `validate_omit` (cognitive 22). Both are
+byte-identical to their `39f7a28` text and therefore outside the changed range the gate reads,
+so the gate does not report them. They are recorded here as known, untouched, pre-existing
+state rather than as anything this slice cleared.
+
+## Gate position at the shipped head
+
+The frozen gate run over this slice's full diff
+(`--base 39f7a28 --head HEAD --repo-dir .`) reports `checks: 170`, `vacuous: false`, and
+exactly three failures — all of them `class_lines`, all of them accepted pre-existing debt:
+
+| file | `class_lines` at `f851884` | `grep -c .` at `f851884` | `grep -c .` at run base `299f0db` |
+|---|---|---|---|
+| `plugins/spec-loop/scripts/run_state.py` | 1078 | 1078 | 918 |
+| `plugins/spec-loop/scripts/test_run_state.py` | 1730 | 1730 | 1269 |
+| `scripts/measure_coverage.py` | 535 | 535 | 453 |
+
+All three were already above the 300 threshold at the run base (918, 1269, 453 non-blank), so
+all three fall inside the run's accepted-pre-existing-`class_lines` rule; none of them crosses
+300 for the first time during this run. `scripts/measure_coverage.py` measures 535, not the 524
+the plan quoted — the plan's figure predates this task's decomposition, and the measured value
+is the one to use. There is no function-level violation and no other metric failure.
+
+## Control-flow words in the added prose
+
+The claim being backed: the lines this slice adds to `scripts/measure_coverage.py` and
+`scripts/test_measure_coverage_manifest.py` keep gate-scored control-flow words out of new
+prose. Here is the sweep that checks it, and its complete output — not a summary of it:
+
+```
+$ git diff 39f7a28..HEAD -- scripts/measure_coverage.py scripts/test_measure_coverage_manifest.py \
+    | grep -n '^+' | grep -E '\b(if|for|while|case|catch|when)\b'
+45:+_MAIN_SHIM_RE = re.compile(r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:")
+59:+    headers = [n for n, text in enumerate(lines, 1) if _MAIN_SHIM_RE.match(text)]
+60:+    if len(headers) != 1:
+75:+    for offset in range(start, len(lines)):
+77:+        if text.strip() and not text[:1].isspace():
+80:+    while resolved and not lines[max(resolved) - 1].strip():
+99:+    if len(resolved) > MAX_SHIM_LINES:
+112:+    asked for the module's entry shim by name, to be turned into line numbers by
+139:+    if line_range == MAIN_SHIM_TOKEN:
+179:+    """The concrete omitted line numbers for one target file (PURE).
+185:+    if spec.main_shim:
+208:+"""Unit tests for measure_coverage.py's __main__-entry-shim resolver and manifest.
+239:+        src = "if __name__ == '__main__':  # pragma: no cover\n    sys.exit(main())\n"
+243:+        src = "\n" * 40 + "if __name__ == \"__main__\":\n    sys.exit(main())\n"
+251:+        src = ("if __name__ == \"__main__\":\n    sys.exit(main())\n"
+252:+               "if __name__ == \"__main__\":\n    sys.exit(main())\n")
+257:+        body = "".join("    x = %d\n" % n for n in range(mc.MAX_SHIM_LINES + 2))
+258:+        src = "if __name__ == \"__main__\":\n" + body
+263:+        src = "\n" * 12 + "if __name__ == \"__main__\":\n    sys.exit(main())\n"
+267:+        lines = ["if __name__ == \"__main__\":", "    sys.exit(main())", "",
+272:+        for relpath in mc.TARGET_FILES:
+286:+        for relpath in mc.TARGET_FILES:
+295:+        for relpath, spec in self.omit.items():
+304:+        for relpath, spec in self.omit.items():
+314:+if __name__ == "__main__":
+```
+
+Twenty-five hits (`grep -c` on the same pipeline returns 25), each accounted for:
+
+- **Executable code — 22 hits.** Diff lines 45, 59, 60, 75, 77, 80, 99, 139, 185 and 314 are
+  real Python statements or the shim-matching regex. Diff lines 239, 243, 251, 252, 257, 258,
+  263 and 267 are test fixture strings that must spell a `__main__` guard, because the resolver
+  under test exists to recognise exactly that text — narrowing them would make the tests stop
+  testing the thing. Diff lines 272, 286, 295 and 304 are loop headers in the manifest tests.
+- **English prose — 3 hits, and the claim is narrowed to match.** Diff lines 112, 179 and 208
+  use the ordinary English word "for": a sentence in the `OmitSpec` dataclass docstring, the
+  one-line summary of `resolve_omit`, and the module docstring of
+  `scripts/test_measure_coverage_manifest.py`. The frozen heuristic does score docstring text
+  that falls inside a function body. Measured consequence at the shipped head: `resolve_omit`
+  is cyclomatic 3 / cognitive 4, far under threshold; the other two sit inside no `def` at all
+  (a class docstring and a module docstring), and the frozen backend extracts bodies by `def`,
+  so no function record carries them. The gate run quoted above reports no function-level
+  finding for either file. So the honest statement is not "no control-flow words reached new
+  prose"; it is that three instances of the English word "for" did, that they are measured, and
+  that they breach nothing.
+
+The operator half of the same sweep, also pasted rather than asserted:
+
+```
+$ git diff 39f7a28..HEAD -- scripts/measure_coverage.py scripts/test_measure_coverage_manifest.py \
+    | grep -n '^+' | grep -E '&&|\|\||\?(\?)?'
+$ echo $?
+1
+```
+
+Empty output, exit 1: this slice adds no branch operator to those two files at all — not in
+prose, and not in code either.
diff --git a/plugins/spec-loop/scripts/run_state.py b/plugins/spec-loop/scripts/run_state.py
index 5b4548e..5db0311 100644
--- a/plugins/spec-loop/scripts/run_state.py
+++ b/plugins/spec-loop/scripts/run_state.py
@@ -96,11 +96,11 @@ ESCALATIONS_HEADER = ("# Escalations\n\n"
                       "into the matching entry.\n\n")
 
 ID_ANCHOR = "<!-- escalation-id: %s -->"
 ID_ANCHOR_PREFIX = ID_ANCHOR.split("%s")[0]
 IDENTITY_ANCHOR = "<!-- escalation-identity: %s -->"
-_IDENTITY_RE = re.compile(r"<!-- escalation-identity: (\w+) -->")
+_IDENTITY_RE = re.compile(r"^<!-- escalation-identity: (\w+) -->\s*$", re.MULTILINE)
 STATUS_OPEN_MARK = "(status: OPEN)"
 STATUS_ANSWERED_MARK = "(status: ANSWERED)"
 SUMMARY_LIMIT = 200
 # Payload keys, in priority order, that may carry a human-readable one-liner.
 # Module-level for the same reason as the messages below: a wrapped literal
@@ -558,10 +558,14 @@ def _section_identity(section):
     """The identity fingerprint carried by a rendered section, or "" (PURE).
 
     A section rendered before the fingerprint existed carries none and
     yields the empty string, which equals no record's fingerprint. Such a
     section is left exactly as it stands and a re-emit is appended beside it.
+    The anchor is matched as a line of its own, since `render_escalation`
+    emits it that way: anchor text quoted inside a rendered body line belongs
+    to the prose, and a section carrying no anchor line of its own still
+    yields the empty string.
     """
     found = _IDENTITY_RE.search(section)
     return found.group(1) if found else ""
 
 
diff --git a/plugins/spec-loop/scripts/test_run_state.py b/plugins/spec-loop/scripts/test_run_state.py
index 3f32b98..de179ec 100644
--- a/plugins/spec-loop/scripts/test_run_state.py
+++ b/plugins/spec-loop/scripts/test_run_state.py
@@ -522,10 +522,47 @@ class TestPlaceEscalationSection(unittest.TestCase):
         body = rs.place_escalation_section(body, "s2", second)
         self.assertIn(rs.IDENTITY_ANCHOR % rs.escalation_identity(first), body)
         parsed = run_metrics.legacy_parse_escalations(body)
         self.assertEqual([item["id"] for item in parsed], ["s1", "s2"])
 
+    def test_a_legacy_section_quoting_an_anchor_is_left_standing(self):
+        # The reproduction. A section rendered before the fingerprint existed
+        # carries no anchor line of its own, so an unanchored match over the
+        # whole section reached into its prose and handed the record's own
+        # fingerprint back. place_escalation_section then rewrote that
+        # unrelated section in place and the older render was lost.
+        record = escalation()
+        stolen = rs.IDENTITY_ANCHOR % rs.escalation_identity(record)
+        legacy = (rs.ESCALATIONS_HEADER
+                  + "## [s9] Older render   (status: OPEN)\n"
+                  + (rs.ID_ANCHOR % "s9:ambiguity") + "\n"
+                  + "- Context: an unrelated note quoting " + stolen + " inline\n"
+                  + "- Answer:\n- Answered-at:\n\n")
+        body = rs.place_escalation_section(legacy, "s1", record)
+        self.assertEqual(len(self.sections(body)), 2)
+        self.assertIn("## [s9] Older render   (status: OPEN)", body)
+        self.assertIn(rs.IDENTITY_ANCHOR % rs.escalation_identity(record), body)
+
+    def test_an_anchor_embedded_in_prose_does_not_claim_another_section(self):
+        first = escalation()
+        body = rs.place_escalation_section(rs.ESCALATIONS_HEADER, "s1", first)
+        stolen = rs.IDENTITY_ANCHOR % rs.escalation_identity(first)
+        quoting = "unrelated question mentioning " + stolen
+        intruder = escalation(id="s2:ambiguity", context=quoting)
+        body = rs.place_escalation_section(body, "s2", intruder)
+        self.assertEqual(len(self.sections(body)), 2)
+        self.assertIn("## [s2]", body)
+        self.assertIn(rs.IDENTITY_ANCHOR % rs.escalation_identity(first), body)
+
+    def test_a_section_carrying_only_an_embedded_anchor_has_no_identity(self):
+        first = escalation()
+        stolen = rs.IDENTITY_ANCHOR % rs.escalation_identity(first)
+        section = ("## [s9] Legacy render   (status: OPEN)\n"
+                   + (rs.ID_ANCHOR % "s9:ambiguity") + "\n"
+                   + "- Context: prose containing " + stolen + " inline\n")
+        self.assertEqual(rs._section_identity(section), "")
+
 
 class TestAnswerWriteBack(unittest.TestCase):
     def setUp(self):
         self.body = (rs.ESCALATIONS_HEADER
                      + rs.render_escalation("s1", escalation())
diff --git a/scripts/coverage_omit.txt b/scripts/coverage_omit.txt
index 78268c7..3b42e74 100644
--- a/scripts/coverage_omit.txt
+++ b/scripts/coverage_omit.txt
@@ -1,42 +1,46 @@
 # coverage_omit.txt — lines excluded from measure_coverage.py's ratios.
 #
-# Format (one exclusion per line):   scripts/<file>.py:START[-END]  # rationale
-# Blank lines and full-line '#' comments are ignored. Every data entry MUST
-# carry a '# rationale'; measure_coverage.py refuses to run on a malformed or
-# rationale-less entry so this manifest stays auditable and cannot silently
-# grow into a place to hide genuinely-untested code. A range is also rejected if
-# it overshoots end-of-file or would remove more than 25% of a file's executable
-# lines (see validate_omit) — so it cannot collapse a file to a false 0/0 = 100%.
+# Format (one exclusion per line):
+#   scripts/<file>.py:START[-END]   # rationale     (literal line range)
+#   scripts/<file>.py:__main__      # rationale     (symbolic, resolved from source)
 #
-# Only two legitimate categories are excluded, and both are inherent to running
-# the suite under `trace` rather than gaps in the tests:
-#   1. `if __name__ == "__main__": sys.exit(main())` process-entry shims — the
-#      module is imported (not run as __main__) under unittest, so this branch and
-#      its sys.exit line never execute. Each is the file's last two lines.
-#   2. The blocking serve_forever() daemon tail in dashboard_server — the server
-#      loop plus its KeyboardInterrupt/finally shutdown cannot run to completion
-#      inside a unit test (it would block forever), so those lines never execute.
+# Blank lines and full-line '#' comments are ignored. Every data entry MUST carry
+# a '# rationale'; measure_coverage.py refuses to run on a malformed or
+# rationale-less entry, so this manifest stays auditable and cannot silently grow
+# into a place to hide genuinely-untested code.
+# Each symbolic entry resolves to the guard header plus its indented body.
+# scripts/test_measure_coverage_manifest.py pins the resolved block size of
+# every target, so a statement added beneath a guard grows the block and fails
+# the suite until the new size is deliberately accepted in that test.
+# An entry is also rejected by validate_omit on overshooting end-of-file, or on
+# removing more than 25% of a file's executable lines, so it cannot collapse a
+# file to a false 0/0 = 100%.
 #
-# Line numbers verified against source on 2026-08-25 (run 20260825-scope-ceiling
-# s3): every entry re-read against its file's own `if __name__` / exit lines, not
-# against any number quoted in a plan or a report. That check found two stale
-# ranges (quality_gate.py 1104-1105 and spec_loop_guard.py 240-241 had drifted
-# from their shims at 1118-1119 and 250-251) and corrected them; validate_omit
-# cannot catch that class of error, because it never asserts an omitted line is
-# unhit. Re-verify whenever these files change length. Plugin scripts live
-# in plugins/spec-loop/scripts/ but keys stay scripts/<name>.py because
-# measure_coverage.normalize_key canonicalizes either scripts/ dir.
+# WHY THE SYMBOLIC TOKEN EXISTS. Every entry below names a process-entry shim: the
+# module is imported rather than run as __main__ under unittest, so the shim header
+# and its body never execute. Those omissions used to be pinned by absolute line
+# range, and a pinned range goes wrong the moment the file grows — the omission
+# then silently points at ordinary executed code further up, with its rationale
+# still claiming the shim. That happened to three entries during run
+# 20260827-deferral-sweep. The token '__main__' is resolved instead by
+# measure_coverage.resolve_main_shim, which locates the header and its indented
+# block in the file's own source at measure time, so growth can never repoint it
+# and these entries never need renumbering again.
+#
+# Plugin scripts live in plugins/spec-loop/scripts/ but keys stay
+# scripts/<name>.py because measure_coverage.normalize_key canonicalizes either
+# scripts dir.
 
-scripts/dag.py:786-787                   # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/dashboard_launcher.py:558-559    # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/dashboard_server.py:1645-1646    # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/knowledge_graph.py:1211-1212     # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/pr_resolver.py:488-489           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/quality_gate.py:1118-1119        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/release.py:194-195               # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/review_package.py:131-132        # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/run_metrics.py:2175-2176         # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/run_state.py:1104-1105           # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/spec_loop_guard.py:250-251       # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/validate_marketplace.py:417-418  # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
-scripts/worktrees.py:385-386             # __main__ entry shim (if __name__/sys.exit(main())); not run as __main__ under unittest
+scripts/dag.py:__main__                  # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/dashboard_launcher.py:__main__   # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/dashboard_server.py:__main__     # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/knowledge_graph.py:__main__      # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/pr_resolver.py:__main__          # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/quality_gate.py:__main__         # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/release.py:__main__              # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/review_package.py:__main__       # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/run_metrics.py:__main__          # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/run_state.py:__main__            # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/spec_loop_guard.py:__main__      # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/validate_marketplace.py:__main__ # process-entry shim; the module is imported, not run as __main__, under unittest
+scripts/worktrees.py:__main__            # process-entry shim; the module is imported, not run as __main__, under unittest
diff --git a/scripts/measure_coverage.py b/scripts/measure_coverage.py
index 18f2e2e..f0d7d2e 100644
--- a/scripts/measure_coverage.py
+++ b/scripts/measure_coverage.py
@@ -27,14 +27,16 @@ statements, ``def``/``class`` header lines, decorators) run under the tracer and
 ARE counted, while the discovered test modules still bind and ``mock.patch`` the
 same freshly-traced module objects (single module identity — the ordering is
 load-bearing; discovering before the re-import splits identity and breaks the
 patches). A module's percentage therefore reflects lines the suite actually
 reaches, and a fully-exercised module reads at ~100%. The only lines that remain
-uncounted are ones that genuinely never run under a unit test — the
-``if __name__ == "__main__"`` process-entry shims and the blocking
-``serve_forever()`` daemon tail — which the audited OMIT manifest removes from both
-numerator and denominator (it may not zero out a file; see ``validate_omit``).
+uncounted are ones that genuinely never run under a unit test: each module's
+process-entry shim, which the audited OMIT manifest removes from both numerator
+and denominator. The manifest names that shim symbolically rather than by line
+number, and ``resolve_main_shim`` locates it in the module's own source at
+measure time, so a file that grows can never repoint the omission at ordinary
+executed code. An omission may not zero out a file; see ``validate_omit``.
 
 Anti-false-green guards: the gate refuses to report coverage unless the suite
 actually ran a plausible number of tests (``MIN_TESTS``), and the OMIT manifest
 cannot zero out a file — omitted lines must be real executable lines and OMIT may
 not remove more than ``MAX_OMIT_FRACTION`` of a file's executable lines.
@@ -44,10 +46,11 @@ Usage: python3 scripts/measure_coverage.py
 from __future__ import annotations
 
 import importlib
 import json
 import os
+import re
 import sys
 import trace
 import unittest
 from dataclasses import dataclass, field
 from pathlib import Path
@@ -79,10 +82,23 @@ MIN_TESTS = 150
 
 # Anti-false-green: OMIT may not remove more than this fraction of any one
 # file's executable lines — a runaway range can't collapse a file to 0/0=100%.
 MAX_OMIT_FRACTION = 0.25
 
+# The one symbolic OMIT token. A manifest entry written as ``path:__main__`` is
+# resolved against the target's own source at measure time by ``resolve_main_shim``,
+# so a file that grows can never repoint the omission at ordinary executed code —
+# the failure mode that a pinned line range has and that this token removes.
+MAIN_SHIM_TOKEN = "__main__"
+
+# Anti-false-green: a resolved entry shim is a header plus a one-line body. Refusing
+# anything longer keeps the token from quietly omitting a large block that someone
+# indented beneath the header.
+MAX_SHIM_LINES = 5
+
+_MAIN_SHIM_RE = re.compile(r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:")
+
 # Product modules that count toward coverage (basename -> relpath key).
 TARGET_FILES = (
     "scripts/dag.py",
     "scripts/dashboard_launcher.py",
     "scripts/dashboard_server.py",
@@ -196,10 +212,76 @@ def normalize_key(path: str) -> str | None:
         rel = Path(*parts[idx:])
         return rel.as_posix()
     return None
 
 
+def _sole_shim_header(lines: list[str], relpath: str) -> int:
+    """The 1-based line number of the module's single ``__main__`` guard header.
+
+    Raises ``ValueError`` unless the source carries exactly one such header.
+    """
+    headers = [n for n, text in enumerate(lines, 1) if _MAIN_SHIM_RE.match(text)]
+    if len(headers) != 1:
+        raise ValueError(
+            f"{relpath}: expected exactly one __main__ entry shim, "
+            f"found {len(headers)} — resolve the OMIT entry by hand."
+        )
+    return headers[0]
+
+
+def _guarded_block(lines: list[str], start: int) -> set[int]:
+    """The 1-based numbers of the header at ``start`` plus its indented block.
+
+    The block ends at the next line that returns to column zero; trailing blank
+    lines are dropped from the result.
+    """
+    resolved = {start}
+    for offset in range(start, len(lines)):
+        text = lines[offset]
+        if text.strip() and not text[:1].isspace():
+            break
+        resolved.add(offset + 1)
+    while resolved and not lines[max(resolved) - 1].strip():
+        resolved.discard(max(resolved))
+    return resolved
+
+
+def resolve_main_shim(source: str, relpath: str) -> set[int]:
+    """The 1-based line numbers of a module's ``__main__`` entry shim (PURE).
+
+    Locates the module's single entry-guard header via ``_sole_shim_header`` and
+    takes it together with the indented block beneath it via ``_guarded_block``.
+    Matching on the block rather than on a fixed body text keeps the resolver
+    correct across both spellings of the entry body — ``sys.exit(main())`` and
+    ``raise SystemExit(main())`` — and keeps it correct after the file grows.
+
+    Raises ``ValueError`` unless the source carries exactly one such header, and
+    unless the resolved block stays within ``MAX_SHIM_LINES``.
+    """
+    lines = source.splitlines()
+    resolved = _guarded_block(lines, _sole_shim_header(lines, relpath))
+    if len(resolved) > MAX_SHIM_LINES:
+        raise ValueError(
+            f"{relpath}: __main__ entry shim resolved to {len(resolved)} lines "
+            f"(max {MAX_SHIM_LINES}) — refusing to omit a block that large."
+        )
+    return resolved
+
+
+@dataclass
+class OmitSpec:
+    """One target's manifest omission: literal line numbers plus symbolic tokens.
+
+    A literal range stays a literal range. ``main_shim`` records that the manifest
+    asked for the module's entry shim by name, to be turned into line numbers by
+    ``resolve_omit`` against the file's own source at measure time.
+    """
+
+    lines: set[int] = field(default_factory=set)
+    main_shim: bool = False
+
+
 def _parse_line_range(line_range: str, raw: str) -> tuple[int, int]:
     """Parse ``START`` or ``START-END`` into an inclusive (start, end) pair."""
     try:
         if "-" in line_range:
             start_s, end_s = line_range.split("-", 1)
@@ -211,12 +293,12 @@ def _parse_line_range(line_range: str, raw: str) -> tuple[int, int]:
     if start < 1 or end < start:
         raise ValueError(f"invalid OMIT line range: {raw!r}")
     return start, end
 
 
-def _parse_omit_line(raw: str) -> tuple[str, range] | None:
-    """Parse one manifest line into ``(relpath, line_range)``, or None to skip.
+def _parse_omit_line(raw: str) -> tuple[str, OmitSpec] | None:
+    """Parse one manifest line into ``(relpath, OmitSpec)``, or None to skip.
 
     Raises ``ValueError`` on a malformed entry or one missing a rationale.
     """
     stripped = raw.strip()
     if not stripped or stripped.startswith("#"):
@@ -228,32 +310,52 @@ def _parse_omit_line(raw: str) -> tuple[str, range] | None:
         raise ValueError(f"OMIT entry has empty rationale: {raw!r}")
     spec = spec.strip()
     if ":" not in spec:
         raise ValueError(f"malformed OMIT entry (expected path:range): {raw!r}")
     relpath, line_range = spec.rsplit(":", 1)
+    line_range = line_range.strip()
+    if line_range == MAIN_SHIM_TOKEN:
+        return relpath.strip(), OmitSpec(main_shim=True)
     start, end = _parse_line_range(line_range, raw)
-    return relpath.strip(), range(start, end + 1)
+    return relpath.strip(), OmitSpec(lines=set(range(start, end + 1)))
 
 
-def parse_omit(text: str) -> dict[str, set[int]]:
-    """Parse the OMIT manifest into ``{relpath: {lineno, ...}}``.
+def parse_omit(text: str) -> dict[str, OmitSpec]:
+    """Parse the OMIT manifest into ``{relpath: OmitSpec}``.
 
-    Each data line must be ``scripts/<file>.py:START[-END]  # rationale``.
-    Blank lines and full-line ``#`` comments are ignored. A malformed entry, or
-    one missing a rationale, raises ``ValueError`` — the manifest must stay
-    auditable and cannot silently grow into a place to hide untested code.
+    Each data line is either ``scripts/<file>.py:START[-END]  # rationale`` (a
+    literal line range) or ``scripts/<file>.py:__main__  # rationale`` (the
+    symbolic entry-shim token, resolved later by ``resolve_omit``). Blank lines
+    and full-line ``#`` comments are ignored. A malformed entry, one missing a
+    rationale, or an unrecognised symbolic token falls through to the numeric
+    parser and raises ``ValueError`` — the manifest must stay auditable and
+    cannot silently grow into a place to hide untested code.
     """
-    result: dict[str, set[int]] = {}
+    result: dict[str, OmitSpec] = {}
     for raw in text.splitlines():
         parsed = _parse_omit_line(raw)
         if parsed is None:
             continue
-        relpath, lines = parsed
-        result.setdefault(relpath, set()).update(lines)
+        relpath, spec = parsed
+        merged = result.setdefault(relpath, OmitSpec())
+        merged.lines |= spec.lines
+        merged.main_shim = merged.main_shim or spec.main_shim
     return result
 
 
+def resolve_omit(spec: OmitSpec, source: str, relpath: str) -> set[int]:
+    """The concrete omitted line numbers for one target file (PURE).
+
+    Literal ranges pass through untouched. A ``main_shim`` spec is resolved against
+    the source given, so the omission tracks the shim wherever it now sits.
+    """
+    resolved = set(spec.lines)
+    if spec.main_shim:
+        resolved |= resolve_main_shim(source, relpath)
+    return resolved
+
+
 def apply_omit(
     executable: set[int], executed: set[int], omit: set[int]
 ) -> tuple[set[int], set[int]]:
     """Remove omitted lines from both the executable and executed sets."""
     return executable - omit, executed - omit
@@ -431,11 +533,11 @@ def _build_stats(counts: dict) -> dict[str, FileStat]:
     stats: dict[str, FileStat] = {}
     for relpath in TARGET_FILES:
         source = _target_source_path(relpath).read_text()
         executable = executable_lines(source, relpath)
         run = executed[relpath] & executable
-        file_omit = omit.get(relpath, set())
+        file_omit = resolve_omit(omit.get(relpath, OmitSpec()), source, relpath)
         validate_omit(
             FileLines(relpath, executable, source.count("\n") + 1), file_omit
         )
         executable, run = apply_omit(executable, run, file_omit)
         stats[relpath] = FileStat(executed=len(run), executable=len(executable))
diff --git a/scripts/test_measure_coverage.py b/scripts/test_measure_coverage.py
index 7a7b0ad..5f79e4f 100644
--- a/scripts/test_measure_coverage.py
+++ b/scripts/test_measure_coverage.py
@@ -7,10 +7,14 @@ runner (I/O shell) is exercised end-to-end by running the tool in CI.
 
 The corrected run-under-trace seam is exercised end-to-end in ``TracedRunTests``
 by invoking the real tool in a clean subprocess (never in-process — see that
 class's docstring for why).
 
+The ``__main__``-entry-shim resolver and the shipped manifest's integrity are
+covered separately in ``test_measure_coverage_manifest.py``, kept in its own
+module so this file stays a manageable size.
+
 Usage: python3 -m unittest scripts.test_measure_coverage
        (or) python3 scripts/test_measure_coverage.py
 """
 import json
 import os
@@ -84,12 +88,13 @@ class ParseOmitTests(unittest.TestCase):
             scripts/pr_resolver.py:488   # single line
 
             """
         )
         omit = mc.parse_omit(text)
-        self.assertEqual(omit["scripts/release.py"], {194, 195})
-        self.assertEqual(omit["scripts/pr_resolver.py"], {488})
+        self.assertEqual(omit["scripts/release.py"].lines, {194, 195})
+        self.assertFalse(omit["scripts/release.py"].main_shim)
+        self.assertEqual(omit["scripts/pr_resolver.py"].lines, {488})
 
     def test_ignores_comments_and_blank_lines(self):
         text = "# only comments\n\n   \n"
         self.assertEqual(mc.parse_omit(text), {})
 
@@ -99,10 +104,41 @@ class ParseOmitTests(unittest.TestCase):
 
     def test_raises_on_malformed_entry(self):
         with self.assertRaises(ValueError):
             mc.parse_omit("this is not a valid entry  # rationale\n")
 
+    def test_parses_the_symbolic_main_shim_token(self):
+        omit = mc.parse_omit("scripts/dag.py:%s  # entry shim\n" % mc.MAIN_SHIM_TOKEN)
+        self.assertTrue(omit["scripts/dag.py"].main_shim)
+        self.assertEqual(omit["scripts/dag.py"].lines, set())
+
+    def test_raises_on_an_unknown_symbolic_token(self):
+        with self.assertRaises(ValueError):
+            mc.parse_omit("scripts/dag.py:__nonsense__  # rationale\n")
+
+
+class ResolveOmitTests(unittest.TestCase):
+    SRC = "a = 1\nb = 2\nif __name__ == \"__main__\":\n    sys.exit(main())\n"
+
+    def test_literal_lines_pass_through_unchanged(self):
+        spec = mc.OmitSpec(lines={1, 2})
+        self.assertEqual(mc.resolve_omit(spec, self.SRC, "synthetic.py"), {1, 2})
+
+    def test_symbolic_token_resolves_to_the_shim_lines(self):
+        spec = mc.OmitSpec(main_shim=True)
+        self.assertEqual(mc.resolve_omit(spec, self.SRC, "synthetic.py"), {3, 4})
+
+    def test_the_resolved_position_follows_the_file_as_it_grows(self):
+        grown = "z = 0\n" + self.SRC
+        spec = mc.OmitSpec(main_shim=True)
+        self.assertEqual(mc.resolve_omit(spec, grown, "synthetic.py"), {4, 5})
+
+    def test_empty_spec_resolves_to_nothing(self):
+        self.assertEqual(
+            mc.resolve_omit(mc.OmitSpec(), self.SRC, "synthetic.py"), set()
+        )
+
 
 class ApplyOmitTests(unittest.TestCase):
     def test_subtracts_omitted_lines_from_both_sets(self):
         executable = {1, 2, 3, 4, 5}
         executed = {1, 2, 3}
diff --git a/scripts/test_measure_coverage_manifest.py b/scripts/test_measure_coverage_manifest.py
new file mode 100644
index 0000000..971982e
--- /dev/null
+++ b/scripts/test_measure_coverage_manifest.py
@@ -0,0 +1,120 @@
+"""Unit tests for measure_coverage.py's __main__-entry-shim resolver and manifest.
+
+Split out of ``test_measure_coverage.py`` (which keeps the executable-line,
+path-key, OMIT-parsing and threshold tests) to keep each test module a
+manageable size. Covers ``resolve_main_shim`` and its two extracted helpers
+directly, and separately asserts that the shipped ``coverage_omit.txt``
+manifest — parsed and resolved through the real code paths, never a fixture
+copy — names every target's shim symbolically and resolves to a block of the
+size pinned by SHIPPED_SHIM_LINES in this module.
+
+Usage: python3 -m unittest scripts.test_measure_coverage_manifest
+       (or) python3 scripts/test_measure_coverage_manifest.py
+"""
+import sys
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+import measure_coverage as mc  # noqa: E402
+
+# Every shipped target's entry shim is a guard header plus a single-line body, so the
+# resolved omission is exactly this many lines. One pin covers all thirteen targets:
+# raising it relaxes every target at once, not just the one that grew.
+SHIPPED_SHIM_LINES = 2
+
+
+class ResolveMainShimTests(unittest.TestCase):
+    def test_resolves_header_and_sys_exit_body(self):
+        src = "a = 1\nif __name__ == \"__main__\":\n    sys.exit(main())\n"
+        self.assertEqual(mc.resolve_main_shim(src, "synthetic.py"), {2, 3})
+
+    def test_resolves_a_raise_systemexit_body(self):
+        src = "a = 1\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n"
+        self.assertEqual(mc.resolve_main_shim(src, "synthetic.py"), {2, 3})
+
+    def test_tolerates_a_pragma_comment_on_the_header(self):
+        src = "if __name__ == '__main__':  # pragma: no cover\n    sys.exit(main())\n"
+        self.assertEqual(mc.resolve_main_shim(src, "synthetic.py"), {1, 2})
+
+    def test_position_moves_with_the_file(self):
+        src = "\n" * 40 + "if __name__ == \"__main__\":\n    sys.exit(main())\n"
+        self.assertEqual(mc.resolve_main_shim(src, "synthetic.py"), {41, 42})
+
+    def test_absent_shim_raises(self):
+        with self.assertRaises(ValueError):
+            mc.resolve_main_shim("a = 1\n", "synthetic.py")
+
+    def test_two_shims_raise(self):
+        src = ("if __name__ == \"__main__\":\n    sys.exit(main())\n"
+               "if __name__ == \"__main__\":\n    sys.exit(main())\n")
+        with self.assertRaises(ValueError):
+            mc.resolve_main_shim(src, "synthetic.py")
+
+    def test_oversized_block_raises(self):
+        body = "".join("    x = %d\n" % n for n in range(mc.MAX_SHIM_LINES + 2))
+        src = "if __name__ == \"__main__\":\n" + body
+        with self.assertRaises(ValueError):
+            mc.resolve_main_shim(src, "synthetic.py")
+
+    def test_sole_shim_header_reports_the_headers_own_line(self):
+        src = "\n" * 12 + "if __name__ == \"__main__\":\n    sys.exit(main())\n"
+        self.assertEqual(mc._sole_shim_header(src.splitlines(), "synthetic.py"), 13)
+
+    def test_guarded_block_stops_at_the_next_column_zero_line(self):
+        lines = ["if __name__ == \"__main__\":", "    sys.exit(main())", "",
+                 "TRAILER = 1"]
+        self.assertEqual(mc._guarded_block(lines, 1), {1, 2})
+
+    def test_every_manifest_target_resolves_against_its_real_source(self):
+        for relpath in mc.TARGET_FILES:
+            source = mc._target_source_path(relpath).read_text()
+            resolved = mc.resolve_main_shim(source, relpath)
+            self.assertTrue(resolved, relpath)
+            self.assertLessEqual(max(resolved), source.count("\n") + 1, relpath)
+
+
+class ManifestIntegrityTests(unittest.TestCase):
+    """The shipped manifest, parsed and resolved by the real code paths."""
+
+    def setUp(self):
+        self.omit = mc.parse_omit(mc.OMIT_FILE.read_text())
+
+    def test_every_target_names_its_shim_symbolically(self):
+        for relpath in mc.TARGET_FILES:
+            self.assertIn(relpath, self.omit)
+            self.assertTrue(self.omit[relpath].main_shim, relpath)
+            self.assertEqual(self.omit[relpath].lines, set(), relpath)
+
+    def test_no_manifest_key_is_outside_the_target_set(self):
+        self.assertEqual(set(self.omit) - set(mc.TARGET_FILES), set())
+
+    def test_each_resolved_omission_is_the_pinned_block_size(self):
+        """The resolved block stays at its pinned size, so it cannot absorb code.
+
+        This is the guard that can fail: a statement added beneath a target's
+        entry guard grows the resolved block, the count stops matching
+        SHIPPED_SHIM_LINES, and the pinned size must be deliberately raised in
+        this module to go green again. The companion assertLess is a pin too,
+        not a check - it restates that the shipped size sits under the resolver
+        cap and moves only on a source edit.
+        """
+        self.assertLess(SHIPPED_SHIM_LINES, mc.MAX_SHIM_LINES)
+        for relpath, spec in self.omit.items():
+            source = mc._target_source_path(relpath).read_text()
+            resolved = mc.resolve_omit(spec, source, relpath)
+            self.assertEqual(len(resolved), SHIPPED_SHIM_LINES, relpath)
+
+    def test_each_resolved_omission_passes_validate_omit(self):
+        for relpath, spec in self.omit.items():
+            source = mc._target_source_path(relpath).read_text()
+            resolved = mc.resolve_omit(spec, source, relpath)
+            target = mc.FileLines(
+                relpath, mc.executable_lines(source, relpath),
+                source.count("\n") + 1,
+            )
+            mc.validate_omit(target, resolved)
+
+
+if __name__ == "__main__":
+    unittest.main()
