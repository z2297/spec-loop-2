# Request — an Azure DevOps connector equivalent to the Jira connector

**Verbatim request:** `create a connector equivelant to JIRA for ADO`

## Restatement (two sentences)

Build an Azure DevOps (ADO) **work-item** connector that is the functional twin of the
plugin's existing Jira connector — a read-only work-item resolver with one bounded,
off-by-default comment writer, a pure intake renderer, and a `/spec-loop:ado-intake`
slash command carrying the same locked security boundary — so an operator can refine one
ADO work item into a pinned-schema intake artifact and hand off to `/spec-loop:spec-loop
--from-plan`. It is a **parallel, self-contained implementation** alongside the Jira
connector, not a refactor of it into a shared provider abstraction: this codebase's
standing stance for bundled scripts is duplication over coupling.

## In scope

1. `plugins/spec-loop/scripts/ado_client.py` — resolve one ADO work item to a normalized
   JSON record (read lane, structurally incapable of a mutating verb) + ONE bounded
   comment writer (`comment`, preview-by-default, `--post` arms the POST), mirroring
   `jira_client.py`'s transport doctrine.
2. `plugins/spec-loop/scripts/ado_intake.py` — pure renderer (no network, no clock, no
   filesystem write, no subprocess): normalized record + refinement object → pinned-schema
   intake artifact + the comment bodies it WOULD post, with an in-body dedupe marker.
3. `plugins/spec-loop/commands/ado-intake.md` — the `/spec-loop:ado-intake` command, same
   step structure and the same `allowed-tools` lock as `jira-intake.md`.
4. Unit tests mirroring `test_jira_client.py` / `test_jira_intake.py` conventions
   (stdlib, faked transport, behaviour through the public CLI).
5. `plugins/spec-loop/scripts/test_doctrine_ado_intake.py` — doctrine guards on the
   command's security prose and invariants, mirroring `test_doctrine_jira_intake.py`.
6. Registration and docs: the `.spec-loop-ado/` artifact root in `.gitignore`, plus every
   place a connector must be named (plugin README, root README, CHANGELOG).

## Out of scope — run-level scope ceiling

- **No ADO Repos / pull-request lane.** No ADO support in `pr_resolver.py`, `review-pr`,
  or `peer-review`. Work items only.
- **No generalization of the Jira connector.** No shared provider/base module, no
  extraction of a common HTTP or rendering layer, no edits to `jira_client.py`,
  `jira_intake.py`, or `jira-intake.md` beyond leaving them untouched.
- **No ADO Server / on-prem hosts.** Azure DevOps Services only (`dev.azure.com`, plus the
  legacy `*.visualstudio.com` org form). Deliberately no opt-in extra-hosts env var.
- **No ADO write beyond adding one work-item comment.** No state transition, no field
  edit (`PATCH` of any kind), no assignee change, no work-item or child creation, no
  relation/link edit, no attachment, no comment edit, no comment delete, no reaction.
- **No WIQL / query / board / pipeline surface.** No searching or listing work items; the
  connector addresses exactly one work item per invocation.
- **No Entra ID / OAuth / service-principal auth flow.** PAT-only (see decisions).
- **No changes to the wave loop, dag, run-state, quality gate, or dashboard.**

## Verified external contract (checked against Microsoft Learn, 2026-09-14)

These were read from the live docs, not recalled. Pin them; do not "modernize" them.

- **Work item read** — `GET https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}?api-version=7.1`
  (`7.1` is the current **stable** api-version; `project` is optional on this route).
  Response: `{id, rev, fields{…}, _links{html{href}, …}, url}`. Fields of interest live in
  the flat `fields` map: `System.Title`, `System.Description`, `System.State`,
  `System.WorkItemType`, `System.TeamProject`, `System.Tags`,
  `Microsoft.VSTS.Common.AcceptanceCriteria`. The human-viewable page is
  `_links.html.href`.
- **Comment list** — `GET https://dev.azure.com/{org}/{project}/_apis/wit/workItems/{id}/comments?api-version=7.1-preview.4`
  — **preview**, and `project` is **REQUIRED** on this route (unlike the work-item read).
  Response: `{totalCount, count, comments[], nextPage, continuationToken}`; paginate by
  passing `continuationToken` until it is absent. Query params: `$top`,
  `continuationToken`, `includeDeleted`, `$expand`, `order`.
- **Comment add** — `POST https://dev.azure.com/{org}/{project}/_apis/wit/workItems/{id}/comments?api-version=7.0-preview.3`,
  body `{"text": "…"}`. Note the **deliberate asymmetry**: Add's newest documented
  api-version is `7.0-preview.3` (its "Other Supported Versions" list stops at 6.1/7.0);
  the comment LIST is `7.1-preview.4` and the work-item read is stable `7.1`. Use the
  documented value per endpoint — do not assume one version string spans all three.
- **Comment identity hazard.** The comment-list definition table names the field `id`,
  while Microsoft's own sample payloads on both the list and add pages show `commentId`.
  Read defensively (accept either, prefer whichever is present) and cover both in tests.
- **Comment body format.** A comment carries a `format` enum (`markdown` | `html`) and an
  optional `renderedText`, but the documented Add request body has only `text` — there is
  no documented way to assert the format on write. Render bodies that read correctly
  whether interpreted as markdown or as HTML-ish plain text, and state that limit in the
  command prose.
- **Auth** — PAT as HTTP Basic with an **empty username**: the docs' own sample is
  `curl -u :{PAT} …`, i.e. `Authorization: Basic base64(":" + PAT)`. Read scope `vso.work`;
  the comment write needs `vso.work_write`. Microsoft's current guidance (page updated
  2026-09-04) still supports PATs but recommends Entra tokens where possible — worth a
  note in the command prose, not a reason to build an OAuth flow here.
- **Description is HTML.** `System.Description` and
  `Microsoft.VSTS.Common.AcceptanceCriteria` are both HTML-typed, not Jira's ADF JSON. So
  the ADO analogue of `adf_to_text()` is an `html_to_text()` walker — a different problem
  (tag soup, entities, `<br>`/`<div>`/`<li>`), lossy-by-design in the same way.
- **Acceptance criteria is process-dependent, not universal.**
  `Microsoft.VSTS.Common.AcceptanceCriteria` exists on Bug, Epic, Feature and Product
  Backlog Item (Scrum) — an Agile **User Story and a Task have no such field**. The
  resolver therefore keeps an `acceptance_criteria_source` discriminator and a resolution
  order (field → an "Acceptance Criteria" heading in the description → empty), but needs
  no field-catalogue HTTP call: it is a dict lookup on the `fields` map.
- **A Bug's real detail is in `Microsoft.VSTS.TCM.ReproSteps` (HTML, Bug only)**, not
  `System.Description`. Reading only the description reports most bugs as empty.

## Inherited hazards from the Jira run (knowledge graph, run 20260908-jira-intake)

The ADO connector must not re-learn these. All three are recorded patterns:

1. **`in-batch-duplicates-are-the-one-dedupe-hole-a-read-back-cannot-close`** — the Jira
   lane deduped correctly against the card's paginated comment list but let two identical
   entries in ONE batch both POST, and the marker-keyed results map collapsed them so both
   reported the same comment id. **Reject duplicate bodies at validation, before the first
   request.**
2. **`premark-must-be-written-inside-the-claim-that-does-the-write`** — the dedupe marker
   must live inside the posted body, written by the one call that performs the write. No
   local file may ever be the dedupe gate.
3. **`prose-that-overstates-a-safety-property-is-a-defect-not-a-nit`** — for a mutating
   external call the command's prose is the operator's only safety description. Do not
   claim the item is re-read before every write (it is read once per invocation), do not
   imply a failed batch posts nothing, and do NOT tell the operator "just re-run this
   command" as partial-failure recovery: the marker hashes the model-regenerated
   refinement, so a one-character prose change yields a new marker and a second
   near-identical comment on a live work item.

## Success criteria

- `/spec-loop:ado-intake <id>` resolves one work item, refines it in one batched question
  round, writes `.spec-loop-ado/<id>/intake.md`, previews comment bodies with zero writes,
  and posts only after an explicit confirmation.
- Posting twice is a no-op on the second run (in-body marker dedupe), and two identical
  bodies in one batch are rejected at validation.
- The read lane cannot issue a mutating verb; redirects are refused outright; credentials
  come only from the environment.
- Full suite green, and the doctrine test pins the command's security prose.
