# Slice s4 — DONE

- **Wave:** 1
- **Branch:** spec-loop/20260827-deferral-sweep/s4
- **Commits:** 299f0dbd1f700f8f3b3991ea7d601df797dd3749 → d3c3ddd3ebd050b166903c5dd987e49611f92ca5
- **Risk tier:** 3
- **Tasks completed:** 4
- **Tests:** `python3 scripts/validate_marketplace.py . ; python3 -m unittest discover -s scripts -p test_*.py ; python3 -m unittest discover -s plugins/spec-loop/scripts -p test_*.py ; python3 scripts/measure_coverage.py ; node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs ; claude plugin validate .` — GREEN - CONTROLLER-MEASURED first-hand in the slice worktree at d3c3ddd, all six segments run as separate tool calls: marketplace OK; root unittest 106 OK; plugin unittest 1184 OK; coverage PASS (TOTAL 96.7-96.8% vs 90% floor, every per-file floor met); node client 48/48 pass; claude plugin validate passed. (scope: full)
- **Quality gate:** FAIL — FAIL - ACCEPTED by controller precedent. Exactly TWO violations, controller-measured first-hand in the worktree at d3c3ddd: class_lines on plugins/spec-loop/scripts/quality_gate.py (1102 non-blank) a…
- **Iron Council:** ENDORSE_WITH_CONCERNS (13 concerns) — scope: clean
- **Review:** 4 confirmed, 2 refuted, 0 evidence-failed, 1 fix round
- **Agents used:** 15

## Residual findings

- P2: `_scan_lines_for`'s fall-back is a FOURTH uncovered new statement, not one of the three the implementer's concern list names, and it is the guard that keeps the masked body slice aligned with the raw body slice (the invariant that stops a metric rising). Nothing executes it: it fires only when …
- P2: The 'every failure path returns the raw text' property is empirical, not structural. `_token_mask_spans` indexes `rows[row - 1]` with no bounds guard and `_mask_python_literals` wraps none of the span arithmetic in a try, so an unexpected IndexError (or any non-tokenizer exception) escapes `_st…
- P3: Two of `_scan_tokens`' three guards are unreachable through `tokenize.generate_tokens`, so they are dead defensive code that cannot receive the executing test the plan's Task 4 step 5 and conventions.md demand. Measured: of 10,025 fuzz inputs that tokenized without raising, zero produced an emp…
- P3: Masking adds a new output side effect the gate never had: tokenizing an analyzed file emits SyntaxWarning to the gate's stderr for invalid escape sequences in f-strings, with a misleading `<string>:N` location instead of the analyzed path. Reproduced: analyzing `def f(a):\n return f"\\{a}"\n` p…
- P3: The new `unmasked(text, lang)` helper's docstring contains the word 'for' ('Identity stand-in for qg._strip_for_scan...'), and two new module-level banner comments contain branch-scan keywords as ordinary English words -- 'case' in quality_gate.py:439 ('the worst case remains today's over-count…

## Escalations

- **ANSWERED** `s4:quality-gate-block` — verification failed

_Rendered from slice-s4-status.json; that sidecar is authoritative._
