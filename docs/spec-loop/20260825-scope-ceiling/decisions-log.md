# Decisions log

Rendered from the run's events; append-only, and nothing parses it back.

[intake] DECISION: plugin_root pinned to the installed 2.0.0 cache, not this repo — AT: 2026-08-25T17:51:52Z
[intake] DECISION: serial s1->s2->s3->s4 chain, overriding the full-council recommendation to parallelise s1 and s2 — AT: 2026-08-25T17:51:52Z
[intake] DECISION: scope ceiling is run-level only, mirroring shared_constraints[]; no per-slice non_goals field — AT: 2026-08-25T17:51:52Z
[intake] COUNCIL-VERDICT: SAFETY OBJECT — AT: 2026-08-25T17:51:52Z
[intake] DEFERRED: run_metrics by_member reads payload.member, a key the workflow never emits (it emits panel[]), so per-lane attribution of a scope flag will read null — AT: 2026-08-25T17:52:29Z
[intake] DEFERRED: metrics will double-count deferrals once the wave emits deferred events: _safety_metrics counts deferrals_total while _council_stats independently counts the same texts as concerns_deferred — AT: 2026-08-25T17:52:29Z
[intake] DEFERRED: the pre-existing fixableByReplan vs fixable_by_replan casing mismatch in all three council agent docs is left unfixed — AT: 2026-08-25T17:52:29Z
[intake] DEFERRED: dashboard surfacing of the new over-scope flag is not built - three server allowlists and two client allowlists would need changes — AT: 2026-08-25T17:52:29Z
[run] DECISION: human chose to update the installed plugin to 2.1.0 and resume, rather than run four waves on stale 2.0.0 machinery — AT: 2026-08-25T17:57:44Z
