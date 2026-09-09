# Request — Jira card intake for spec-loop 2

## Verbatim user request

Problem: I want to provide the loop a jira card and have the loop automatically break down work and surface questions.

Solution: Build a mechanism to injest jira cards. When a question arises prompt me (the user). When I make a decision log the decision in the card as a comment. If I do not have an answer, write the comment as a question so that it can be resolved later.

Enhancement to core solution: Cards often lack definition, show me (the user) the description, acceptance criteria, risks, gaps for me to confirm. Once confirmed write the new understanding as a comment.

This should all occur without the loop automatically starting the work without explicit confirmation. It should not be required to run the loop.

## Controller restatement

Add a Jira-card intake path to the spec-loop 2 plugin: fetch a Jira issue, derive and present a
refined understanding (description, acceptance criteria, risks, gaps) for the human to confirm,
write the confirmed understanding back to the card as a comment, decompose the work and surface
questions to the human, log answered questions as decision comments on the card and unanswered
ones as open-question comments for later resolution, and never begin implementation without an
explicit human confirmation. The path must be usable standalone — refinement and write-back are
valuable on their own, with the handoff into a spec-loop run being an optional, opt-in final step.

## In scope

- A new standalone plugin entry point (command, and any supporting skill/agent/script) for Jira intake.
- Jira read (issue fields, ACs, comments) and Jira write (adding comments).
- Refinement pass producing description / acceptance criteria / risks / gaps for human confirmation.
- Confirmed-understanding comment written back to the card.
- Question surfacing with answered -> decision comment, unanswered -> open-question comment.
- Explicit confirmation gate before any handoff into `/spec-loop:spec-loop`.
- Durable local artifacts + tests + docs consistent with the repo's existing conventions.

## Out of scope (run-level scope ceiling)

- Changing the wave execution engine, slice-wave workflow, or run-state v2 contract.
- Auto-starting implementation work, or any autonomous code execution from a card.
- Non-Jira trackers (Linear, Asana, GitHub Issues, monday.com).
- Jira status/transition changes, field edits, assignee changes, or any Jira write other than comments.
- Bulk/board-level ingestion (multiple cards, sprints, epics-as-a-batch).

## Confirmed intake decisions (human, 2026-09-09)

1. **Jira access = stdlib REST script + env vars.** A self-contained stdlib-only Python module
   beside `pr_resolver.py` over the Jira Cloud REST v3 API, credentials from
   `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN`. Coverage-gated, mocked-transport tests,
   issue-key allow-list, mirrored token-never-leaks test. Rejected: MCP transport (not
   authenticated in this environment; invisible to every CI gate).
2. **Write path = render, confirm, then post.** Posts nothing by default. Comment bodies are
   rendered locally and shown; a second explicit confirmation arms the write. Deduplication reads
   the card's own **paginated** comment list and matches a visible marker embedded in the comment
   body; the local artifact is an audit cache, never the gate.
3. **Card-derived artifacts are untracked by default.** Written to a gitignored path; the command
   ensures the ignore entry exists before writing. Rationale: this plugin's own repo is public and
   the command runs in whatever repo it is invoked from.
4. **Breakdown = refined request + printed handoff.** Intake produces a refined request file and
   PRINTS `/spec-loop:spec-loop --from-plan <path>` for the human to run. Slice decomposition stays
   with the existing controller. Intake structurally cannot start the loop.

Council: plan-critic OBJECT (safety flag), guardian OBJECT (safety flag), skeptic OBJECT — all
three resolved by the four decisions above. Concerns folded into `shared_constraints`; deferred
items recorded in `scope_ceiling`.
