# Slice s12 — DONE

- **Wave:** 5
- **Branch:** spec-loop/20260827-deferral-sweep/s12
- **Commits:** ac283ad → af96f69aad9614a00b8cdde31bcaeafb58baa8f2
- **Risk tier:** 3
- **Tasks completed:** 1
- **Tests:** `7-segment suite` — GREEN - CONTROLLER-MEASURED first-hand at af96f69, all seven segments as separate tool calls: marketplace OK; root unittest 126 OK (up from 106 - this slice added the manifest guard module); plugin unittest 1292 OK; coverage PASS TOTAL 96.9% vs 90% floor; node client 48/48; behavioural harness 35/35; claude plugin validate passed. (scope: full)
- **Quality gate:** FAIL — FAIL - ACCEPTED by controller precedent. Exactly THREE violations, all class_lines with function=None: run_state.py 1078, test_run_state.py 1730, scripts/measure_coverage.py 535. ZERO function-level …
- **Iron Council:** OBJECT (11 concerns) — scope: clean
- **Review:** 3 confirmed, 3 refuted, 0 evidence-failed, 2 fix rounds
- **Agents used:** 16

## Residual findings

- P2: `test_an_anchor_embedded_in_prose_does_not_claim_another_section` cannot fail on the defect its name describes: it passes identically with the pre-fix unanchored `_IDENTITY_RE`. I measured this by monkeypatching the old pattern back in-process — the intruder record's fingerprint differs from th…
- P3: Implementer concern, verified: `self.assertLess(SHIPPED_SHIM_LINES, mc.MAX_SHIM_LINES)` compares two module-level constants (2 and 5) and can only change on a deliberate edit to one of them — no product-source change can move it. It is not strictly tautological (a maintainer lowering MAX_SHIM_L…
- P2: Two of the four new pure helper functions added in this diff carry the repo's '(PURE)' docstring marker (resolve_main_shim, resolve_omit) while the other two equally pure helpers (_sole_shim_header, _guarded_block) do not — and this file had zero '(PURE)' markers anywhere before this diff (conf…
- P3: _guarded_block's trailing-blank-line trim is a two-pass approach: it first grows `resolved` forward through every line (blank or not) up to the next column-zero line, then repeatedly recomputes max(resolved) and discards it while that line is blank. A single forward scan that tracks the index o…

## Escalations

- **ANSWERED** `s12:quality-gate-block` — verification failed

_Rendered from slice-s12-status.json; that sidecar is authoritative._
