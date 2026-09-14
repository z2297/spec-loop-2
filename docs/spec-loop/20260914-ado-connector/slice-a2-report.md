# Slice a2 — DONE

- **Wave:** 2
- **Branch:** spec-loop/20260914-ado-connector/a2
- **Commits:** a39272b130ebaec23fac2e0bad82195c4e977963 → caeaa7d9b838f5b5fbcb1cfce1af5cfa16716cf5
- **Risk tier:** 3
- **Tasks completed:** 7
- **Tests:** `python3 scripts/validate_marketplace.py . ; python3 -m unittest discover -s scripts -p 'test_*.py' ; python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py' ; python3 scripts/measure_coverage.py ; node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs ; node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs plugins/spec-loop/scripts/slice_wave_radius.test.mjs plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs plugins/spec-loop/scripts/slice_wave_reentry.test.mjs plugins/spec-loop/scripts/slice_wave_accepted.test.mjs plugins/spec-loop/scripts/slice_wave_replan.test.mjs` — All six suite segments passed. Segment 1: marketplace validation OK. Segment 2: 126 tests passed. Segment 3: 2113 tests passed. Segment 4: 2239 tests passed with coverage floors met (97.3% total, 90% floor). Segment 5: 48 Node tests passed. Segment 6: 136 Node slice-wave tests passed. (scope: full)
- **Quality gate:** FAIL — Quality gate exited 1 (measured failure). Three class_lines violations reported: ado_client.py (1510>300), test_ado_client.py (1625>300), measure_coverage.py (543>300). The measure_coverage.py violat…
- **Iron Council:** SKIPPED
- **Review:** 0 confirmed, 4 refuted, 0 evidence-failed, 1 fix round
- **Agents used:** 4

## Residual findings

- P2: _load_json_file catches only OSError, so a non-UTF-8 --record or --comments file raises UnicodeDecodeError out of main instead of the documented exit 2. The identical hole exists in jira_client.py, jira_intake.py and ado_intake.py, so it is a copied pattern, not a new deviation.
- P2: execute_comment_plan catches only AdoError, but post_comment decodes the POST response with no handler, so a non-UTF-8 response body escapes as UnicodeDecodeError AFTER the comment has already been written.
- P3: plan_comments derives its second-tier dedupe token as the positional slice marker[-13:-1], correct only because validate_comment_entries fullmatched MARKER_RE first; nothing structurally enforces that ordering.
- P3: route=(api_root, project, id) and target=(org, project, id) are same-shape 3-tuples with different first-element semantics on the module's self-described defining hazard.

_Rendered from slice-a2-status.json; that sidecar is authoritative._
