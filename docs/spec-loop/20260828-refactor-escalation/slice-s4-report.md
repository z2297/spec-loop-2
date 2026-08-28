# Slice s4 — ESCALATED

- **Wave:** 3
- **Branch:** spec-loop/20260828-refactor-escalation/s4
- **Commits:** e5479765c38247df97d5de9571a7f401b8deaff4 → 3e03074
- **Risk tier:** 3
- **Tasks completed:** 4
- **Quality gate:** FAIL — 1 violation(s)
- **Iron Council:** ENDORSE_WITH_CONCERNS (15 concerns) — scope: clean
- **Review:** 2 confirmed, 1 refuted, 0 evidence-failed, 1 fix round
- **Agents used:** 15

## Residual findings

- P2: The re-check's own `concerns` are read by nothing and recorded nowhere. `recordDeferrals` in `resolveObjectionAndRecord` is called with the ORIGINAL panel's `concerns` (stageCritique passes them through `ctx`), so a `critic:replan` seat that returns ENDORSE_WITH_CONCERNS with `disposition_hint:…
- P2: `usableSplit` accepts any non-empty children array (`length > 0`), but a ONE-child split is exactly as unusable as a zero-child one: `PLAN_RESULT.split.children` declares `minItems: 2`, `run_state.MIN_SPLIT_CHILDREN` is 2 and `_validate_children` rejects it with 'a one-child split is the same s…
- P2: The re-check dispatch reuses `criticPrompt(slice, plan, null)`, whose text is a from-scratch plan critique ('You are the full council: all five mandates') that never mentions that this plan is a REVISION, never carries the objection it was revised to resolve, and never asks whether that objecti…
- P2: A fourth site reads `fix.commits` under its own inline optional-read guard, duplicating exactly the shape check the new `fixCommits()` helper (introduced in this same diff to be the canonical guard for `fix.commits` optionality) already centralizes. `fixCommits()` is not reused here, so the sam…
- P3: The module docstring still claims 'The three `test_slice_wave_contract*.py` modules that import this one,' but this diff adds the FIFTH importer (`test_slice_wave_contract_replan.py`), widening an already-stale count without correction, even though this same diff edits this docstring for a diff…
- P2: The new `replan-recheck` event type is not added to run-state-v2.md's event-type list, breaking the repo's own single-home doctrine for this contract and departing from precedent: the prior slice's new `refactor-radius` trigger was added both to this list AND to a pinned contract test. The list…

## Escalations

- **OPEN** `s4:quality-gate-block` — verification failed

_Rendered from slice-s4-status.json; that sidecar is authoritative._
