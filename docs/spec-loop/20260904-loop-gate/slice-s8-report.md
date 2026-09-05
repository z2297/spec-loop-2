# Slice s8 — DONE

- **Wave:** 6
- **Branch:** spec-loop/20260904-loop-gate/s8
- **Commits:** 90ef235a1bacbaafa595d287ae9aac7fd0aac292 → fa9257dd901ef23629b36d6d3d845434c1ad05d6
- **Risk tier:** 3
- **Tasks completed:** 2
- **Tests:** `python3 scripts/validate_marketplace.py . ; python3 -m unittest discover -s scripts -p test_*.py ; python3 -m unittest discover -s plugins/spec-loop/scripts -p test_*.py ; python3 scripts/measure_coverage.py ; node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs ; node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs ; node --test plugins/spec-loop/scripts/slice_wave_radius.test.mjs ; node --test plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs ; node --test plugins/spec-loop/scripts/slice_wave_replan.test.mjs ; claude plugin validate .` — All 10 suite segments passed. Python: 126 + 1479 + 1605 tests = 3210 total with coverage 97.0% (floor 90%). Node: 48 + 35 + 38 + 9 + 16 = 146 tests. Marketplace and plugin validation both OK. (scope: full)
- **Quality gate:** PASS — All 36 builtin-heuristic checks passed. No failures recorded. 2 file types skipped: CHANGELOG.md (unsupported file type) and crap_score (no coverage report).
- **Iron Council:** ENDORSE_WITH_CONCERNS (12 concerns) — scope: clean
- **Review:** 0 confirmed, 0 refuted, 0 evidence-failed, 0 fix rounds
- **Agents used:** 10

## Residual findings

- P2: The pin reads and asserts over the ENTIRE CHANGELOG, but scripts/release.py rolls the [Unreleased] section into a frozen dated section inside the same file (re.subn on '^## \[Unreleased\]' inserts a new empty Unreleased above it). Once this entry is released it becomes immutable history, yet te…
- P3: PROBES_NUMBERED_ITEM_RE counts every '^N. ' line in the whole of platform-probes.md, not just the open-question list, so the cross-check between the register's spelled-out word and its list length is coupled to the file having exactly one numbered list. It has exactly one today (lines 81/87/89,…
- P3: The count assertions are deliberately derived from both files so the pin never needs an edit, but CHANGELOG_TOPICS is three hard-coded literals with no link to the register's numbered items. When a question is settled, both files' counts drop together and the count tests stay green, while test_…
- P2: The new TestCase's docstring documents an honest limit for the numbered-item-count's file-wide scope, but omits the comparable and arguably more fragile limitation that CHANGELOG_TOPICS is three hard-coded literal strings with no mechanical link back to platform-probes.md's numbered questions -…
- P3: CHANGELOG_INSTALL_VERSION_LIMIT is a module-scope name added by the implementer that is not listed in Task 2's Interfaces > Produces list (which enumerates CHANGELOG_MD, WORD_TO_INT, CHANGELOG_OPEN_COUNT_RE, PROBES_OPEN_COUNT_RE, PROBES_NUMBERED_ITEM_RE, CHANGELOG_TOPICS, CHANGELOG_RETRACTED_FR…

_Rendered from slice-s8-status.json; that sidecar is authoritative._
