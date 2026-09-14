# conventions.md — spec-loop-2, for the ADO connector run

Everything below was read first-hand from this repo, its CI config, the live effective
quality-gate config, and Microsoft Learn on 2026-09-14. Do not re-explore these; point
here. Where a fact is version-sensitive it says so.

## 1. Test & build commands

CI is ONE workflow, `.github/workflows/validate.yml` (python 3.12, node 20). Six gates,
all must pass. The run's `test_command` is these as ` ; `-joined segments — **run each as
its OWN tool call**:

```
python3 scripts/validate_marketplace.py .
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m unittest discover -s plugins/spec-loop/scripts -p 'test_*.py'
python3 scripts/measure_coverage.py
node --test plugins/spec-loop/scripts/dashboard_assets/index.test.mjs
node --test plugins/spec-loop/scripts/slice_wave_behaviour.test.mjs plugins/spec-loop/scripts/slice_wave_radius.test.mjs plugins/spec-loop/scripts/slice_wave_radius_partial.test.mjs plugins/spec-loop/scripts/slice_wave_reentry.test.mjs plugins/spec-loop/scripts/slice_wave_accepted.test.mjs plugins/spec-loop/scripts/slice_wave_replan.test.mjs
```

Measured baseline on this branch (2026-09-14): dev-tools lane 38s, plugin lane 19s,
coverage gate 32s (**1982 tests, TOTAL 97.2%, all floors met**). Nothing is near the
10-minute tool ceiling. There is no Makefile and no pytest — **`unittest` only**.

The two `unittest discover` lanes exist because the suite spans two directories:
dev/CI tooling in `scripts/`, and the shipped runtime + its tests in
`plugins/spec-loop/scripts/`. **A new connector's code and tests go in
`plugins/spec-loop/scripts/`** (the shipped plugin), not in `scripts/`.

## 2. The coverage floor gate — MANDATORY wiring for any new product module

`scripts/measure_coverage.py` is a hard CI gate, and a new module is invisible to it
until it is registered in THREE places. `scripts/test_measure_coverage_manifest.py`
enforces the consistency, so a half-registration fails the suite:

1. **`TARGET_FILES`** (`scripts/measure_coverage.py:101`) — a tuple of `scripts/<name>.py`
   keys, alphabetical. Note the key is `scripts/<name>.py` **even for plugin modules**:
   `normalize_key` canonicalizes either scripts dir (see the note at
   `scripts/coverage_omit.txt:31`). `TARGET_MODULES` is derived automatically.
2. **`PER_FILE_FLOORS`** (`scripts/measure_coverage.py:143`) — integer percent per file,
   with a trailing comment recording the locally measured figure and the date. **House
   rule: set the floor at the measured local percentage minus AT LEAST 5 points, rounded
   down**, because CI runs py3.12 and `co_lines()` attribution drifts across versions; a
   floor set AT the coverable max wedges CI with a false red. Precedent:
   `jira_client.py: 94  # local 99.5% (2026-09-09) - >=5`.
3. **`scripts/coverage_omit.txt`** — one line per target,
   `scripts/<name>.py:__main__      # process-entry shim; the module is imported, not run as __main__, under unittest`.
   `test_every_target_names_its_shim_symbolically` requires EVERY target to have this
   entry, so **every new module must have an `if __name__ == "__main__":` shim** of at
   most `MAX_SHIM_LINES = 5` lines (header + indented body). `__main__` is a symbolic
   token resolved from source at measure time — never pin a literal line range.
   `test_each_resolved_omission_is_the_pinned_block_size` pins each resolved block size,
   so the new entry's size must be added there deliberately.

Other guards: `MIN_TESTS = 150` (fails closed on a collapsed suite),
`MAX_OMIT_FRACTION = 0.25`, `TOTAL_FLOOR = 90`. Every OMIT entry must carry a
`# rationale` or the tool refuses to run.

## 3. Python conventions

- **Stdlib only.** No `requirements.txt`; bundled scripts import only stdlib
  (`argparse`, `base64`, `json`, `os`, `re`, `sys`, `urllib.*`, `hashlib`, `pathlib`,
  `dataclasses`). Do not add a dependency — HTTP is hand-rolled on `urllib.request`.
- **Python 3.12** is the CI target. `from __future__ import annotations` at the top.
- **Self-contained modules, duplication over coupling.** `jira_client.py` states it
  explicitly: "no shared helper module with jira_client.py or pr_resolver.py, duplication
  over coupling." So the ADO connector **copies and adapts** the transport, validation,
  and JSON-loading shapes — it must NOT import from `jira_client.py`, `jira_intake.py`, or
  `pr_resolver.py`, and must NOT refactor them into a shared base.
- **Module docstring template** (every bundled script follows it, in this order): a
  one-line summary naming "stdlib only"; a prose paragraph of what it resolves/does; a
  `Design decisions:` bullet list holding the real rationale; a `SECURITY:` paragraph
  naming what is untrusted data and what the transport guarantees; `Exit codes: 0 = ok;
  1 = contract failure; 2 = usage / unreadable input`; and a `Usage:` block of literal
  command lines. This docstring is load-bearing — the doctrine tests assert against it.
- **Error hierarchy**: `class XError(Exception)` for contract failure (exit 1), and
  `class XUsageError(XError)` for usage/unreadable input (exit 2). Mirror
  `JiraError`/`JiraUsageError` (`jira_client.py:88,93`) and
  `IntakeError`/`IntakeUsageError` (`jira_intake.py:55,60`).
- **Validation style**: hand-rolled pure functions returning **lists of error strings**
  (never a schema library), then one caller raises on a non-empty list. See
  `_errors_for_*` / `validate_*` in `jira_intake.py:113-306`.
- **argparse**: a `build_parser()` returning subcommand parsers, a per-subcommand
  `_<name>_payload(args)` handler, and `main(argv=None)` that maps exceptions to exit
  codes. `jira_intake.py:559-613`.

## 4. External-provider transport doctrine (mirror this exactly)

From `jira_client.py` (and `pr_resolver.py`, which is read-only-only):

- **Two transports, structurally separated.** `_http_get(url, ...)` (`:212`) is incapable
  of a mutating verb — it sets no body and no method. `_http_post(url, ..., payload)`
  (`:247`) is the module's SOLE writer. Keep them separate functions; do not unify them
  behind a `method=` parameter, because the separation is the proof.
- **Redirects refused outright**, not followed-with-header-stripping: a custom
  `class _NoRedirect(urllib.request.HTTPRedirectHandler)` whose `redirect_request`
  returns `None` (`:168`), installed on one module-level `_OPENER =
  urllib.request.build_opener(_NoRedirect)` (`:179`). The base URL is user-supplied, so
  an `Authorization` header must never be replayed to another origin.
- **Host allow-list + https-only**, enforced by regex on the hostname before any request
  (`ALLOWED_HOST_RE`, `:100`; `validate_base_url`, `:143`). Deliberately **no opt-in
  extra-hosts env var** — that would re-open the hole the allow-list closes.
- **Credentials from the environment ONLY**, never argv (argv is visible in `ps` and lands
  in shell history). One `CRED_VARS` tuple (`:181`) and one `credentials()` (`:184`) that
  fails closed with an actionable message naming the missing variable.
- **Every untrusted value regex-validated with `re.fullmatch` and percent-encoded**
  (`urllib.parse.quote(..., safe="")`) before it reaches a URL segment.
- **Redaction**: `_redacted_base_url` (`:131`) exists so an error message can name the URL
  without leaking credentials. There is a dedicated test class `TestSecretsNeverLeak`.
- **One `_normalized()` builder** (`:902`) is the single source of truth for the emitted
  JSON contract, with a `REQUIRED_FIELDS` emptiness check that **raises rather than emit a
  partial record**. Copy this shape.
- **Bounded pagination**: `COMMENT_PAGE_SIZE = 100`, `MAX_COMMENT_PAGES = 100` (`:571`) —
  a page loop must have a hard cap, and a missing expected key is a fail-closed error with
  a named message constant.
- **No subprocess, no filesystem write, no clock read** in the client. The controller owns
  the clock; timestamps arrive as `--ts`.

## 5. The renderer is PURE

`jira_intake.py` has no network, no clock, no filesystem write, no subprocess. The command
does every side effect: it shells the client for the record, shells the renderer, and does
the `Write` itself. Keep the ADO renderer equally pure — it is what makes it testable.

Pinned contracts to mirror (names are the ADO analogues' template, not to be copied blind):

- `jira_client.py`: `RECORD_FIELDS = ("key", "web_url", "summary", "description",
  "acceptance_criteria", "acceptance_criteria_source", "status", "issue_type", "comments")`
  and `REQUIRED_FIELDS = ("key", "web_url", "summary", "status", "issue_type")` (`:895`).
- `jira_intake.py`: `ARTIFACT_ROOT = ".spec-loop-jira"`, `ARTIFACT_SCHEMA_VERSION = 2`
  (`:65`); `REFINEMENT_KEYS = ("description", "acceptance_criteria", "risks", "gaps",
  "injection_findings", "answers")` (`:104`); `ARTIFACT_FIELDS = ("schema_version",
  "issue_key", "issue_url", "issue_status", "issue_type", "acceptance_criteria_source",
  "gap_count", "open_question_count", "generated")` (`:416`); `ARTIFACT_SECTIONS` is the
  six `## N. …` headings (`:419`); `COMMENT_KINDS = ("understanding", "decision",
  "open-question")` with `COMMENT_HEADINGS` (`:331`).
- `artifact_path(key, artifact_root)` (`:82`) is **sanitize-and-assert**: it validates the
  key, composes the path, then re-asserts the result sits under the artifact root, so a
  later change to the composition cannot escape unnoticed. Keep both halves.
- `comment_marker(key, kind, payload)` (`:339`) **deliberately excludes the timestamp**
  from its hash — hashing `--ts` would make a re-run at a later time look like a brand-new
  comment and defeat dedupe. It DOES hash the refinement payload (see hazard 3 below).
- `_neutralize_delimiters` (`:427`) defangs text before it lands in the artifact.

## 6. The three hazards this connector inherits (do not re-learn them)

Recorded knowledge-graph patterns from run `20260908-jira-intake`:

1. **In-batch duplicates.** A read-back dedupe gate is blind to two identical entries in
   the batch it is gating: both are planned against one pre-write snapshot and both get
   written, and a results map keyed by marker collapses them so both report the same
   comment id. **Reject duplicate markers at validation, before the first request.** Jira
   now does this in `_duplicate_marker_errors` (`jira_client.py:698`), covered by
   `TestADuplicateBatchIsRefusedBeforeAnyPost` (`test_jira_client.py:1253`). Build the ADO
   lane with this from the start.
2. **The marker must be written by the writer.** The dedupe marker lives INSIDE the posted
   body, so the one call that writes the comment writes the marker. No local file may ever
   be the dedupe gate, and a fresh clone must not be able to double-post.
3. **Prose that overstates a safety property is a defect, not a nit.** For a mutating
   external call the command's prose is the operator's only description of what is safe.
   Do NOT write that the item is re-read before every write (it is read once per
   invocation); do NOT imply a failed batch posts nothing (earlier comments may be live);
   and **never** offer "re-run this command" as partial-failure recovery — the marker
   hashes the model-regenerated refinement, so dropping a single period was measured to
   change the marker and produce a second near-identical comment on a live card.

## 7. Test conventions

`unittest` only. Tests sit beside the code in `plugins/spec-loop/scripts/` as
`test_<module>.py`. Structure from `test_jira_client.py`:

- A `sys.path` insert then `import jira_client as jc  # noqa: E402` (`:33`).
- **One `unittest.TestCase` class per behaviour**, named as a sentence asserting the
  property: `TestHttpGetIsReadOnly`, `TestHttpPostIsTheOnlyWriter`,
  `TestRedirectsAreRefused`, `TestSecretsNeverLeak`,
  `TestADuplicateBatchIsRefusedBeforeAnyPost`, `TestNormalizedRecord`, `TestMain`.
- **Module-level fixture builders** between the classes that use them — `issue_bean(**f)`
  (`:665`), `raw_comment(cid, text, author=...)` (`:813`), `comment_page(...)` (`:822`),
  `entry(kind, marker, body)` (`:931`), `card_with(bodies)` (`:1049`).
- **Transport is faked with `unittest.mock`** (`mock.patch` on the module's opener /
  `_http_get` / `_http_post`), plus `ExitStack` for layered patches and `inspect` to
  assert structural properties of functions. **No real socket, ever.** `tempfile` +
  `shutil` for any filesystem work.
- Behaviour is exercised **through the public CLI** (`TestMain` drives `main(argv)` and
  asserts exit codes and printed JSON) as well as at function level for the pure helpers.
- Mock only the true external dependency (the HTTP transport). Everything else runs real.

## 8. Doctrine tests

`plugins/spec-loop/scripts/test_doctrine_*.py` assert properties of the **repo's own
source and command prose**, not runtime behaviour — they read the markdown/python as text
and assert invariants hold (e.g. that a command's `allowed-tools` has not grown, that the
security section still says what it must). Existing ones:
`test_doctrine_jira_intake.py`, `test_doctrine_accepted_violations.py`,
`test_doctrine_loop_boundary.py`, `test_doctrine_marker_hygiene.py`,
`test_doctrine_platform_probes.py`, `test_doctrine_refactor_scope.py`,
`test_doctrine_run_docs.py`, `test_doctrine_run_recording.py`.
A new `test_doctrine_ado_intake.py` should mirror `test_doctrine_jira_intake.py`'s
mechanism and pin the ADO command's security boundary and the three hazards above.

## 9. Command markdown conventions & the CI frontmatter gate

Commands are auto-discovered from `plugins/spec-loop/commands/*.md` — **there is no
manifest list to update** (`plugins/spec-loop/.claude-plugin/plugin.json` declares only
`workflows`). `scripts/validate_marketplace.py` gates them:

- Frontmatter `---` block is required, and `description` is a **required key**
  (`:296-300`).
- **A frontmatter value containing `': '` must be quoted** (`_frontmatter_value_error`,
  `:334`) — an unquoted colon-space loads as empty YAML. `jira-intake.md` quotes its long
  description; do the same.
- A command whose text marks it read-only must not grant `Edit` (`:310`). The ADO command
  grants no `Edit` at all, so this is satisfied structurally.
- No absolute filesystem paths or env-var references in command/skill/agent content
  (`:184`) — a packaging gate.

`jira-intake.md`'s frontmatter is the template: a quoted one-sentence `description`, an
`argument-hint`, and `allowed-tools: ["AskUserQuestion", "Bash", "Read", "Write"]`. Its
body opens with a `## The security boundary` section enumerating what the command
structurally cannot do (no `Workflow`, no `Edit`, one bounded write, no credential
handling, `Write` scoped to the artifact, `Bash`'s exactly-N sanctioned writes, untrusted
input). **Keep that section's shape and keep every claim in it literally true.**

## 10. Artifact root & .gitignore

`.gitignore` ends with:
```
# spec-loop Jira intake artifacts (card text; never commit)
.spec-loop-jira/
```
The ADO run must add the analogous `.spec-loop-ado/` entry with its own comment. The root
is gitignored because the command runs in whatever repo invokes it and work-item text may
be private while the repo may be public. The command ensures the ignore entry exists
(a constant-string `Bash` append, never a `Write`, and nothing provider-derived in it)
BEFORE it writes any artifact.

## 11. Effective quality gate (resolved via the one door, 2026-09-14)

`--print-config` with the global config and no repo overlay (`.spec-loop/quality-gate.json`
does not exist; source `loaded`):

- thresholds: `cyclomatic_complexity 10`, `cognitive_complexity 15`, `method_lines 50`,
  `parameter_count 4`, `nesting_depth 3`, `class_lines 300`, `crap_score 30`
- `refactor_radius`: enabled, `max_rewrite_ratio 0.5`,
  `max_touched_existing_files 8`, `min_rewritten_lines 150`
- `measurement: hybrid`, `refactor_attempts 3`, `custom_gates: []`, `models: {}`
- `tier3_surfaces` includes `**/auth/**`, `**/Endpoints/External/**`, `**/secrets*`,
  `.env*` — a credential-reading external-provider client is squarely Tier-3 territory.

`parameter_count 4` and `method_lines 50` are the two that bite hardest on a hand-rolled
HTTP client: `jira_client.py` keeps functions small and passes `(base_url, email, token)`
as a threshold-respecting trio. Note `_http_get(url, email, token)` is 3 params; an ADO
equivalent needs only `(url, pat)`. Prefer many small functions over one big one — the
existing `_adf_*` renderer is split into ~12 tiny functions with two dispatch dicts
(`_INLINE_RENDERERS`, `_BLOCK_RENDERERS`) precisely to stay under these thresholds. The
`html_to_text` walker should be structured the same way.

## 12. Verified ADO REST contract (Microsoft Learn, read 2026-09-14)

**Pin these; do not "modernize" them.** Full detail and the hazards are in `request.md`
§"Verified external contract" — summary:

| Operation | Method & path | api-version | Notes |
|---|---|---|---|
| Read work item | `GET https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}` | `7.1` (**stable**) | `project` optional here |
| List comments | `GET .../{project}/_apis/wit/workItems/{id}/comments` | `7.1-preview.4` | `project` **required**; paginate on `continuationToken` |
| Add comment | `POST .../{project}/_apis/wit/workItems/{id}/comments` | `7.0-preview.3` | body `{"text": "…"}` |

The three api-versions differ **on purpose** — Add's newest documented version is
`7.0-preview.3`. Use the documented value per endpoint; do not assume one string spans all
three.

- **Auth**: PAT as HTTP Basic with an **empty username** — the docs' own sample is
  `curl -u :{PAT}`, i.e. `Authorization: Basic base64(":" + PAT)`. Read scope `vso.work`;
  the write needs `vso.work_write`.
- **Addressing**: a work item is an **integer id** plus an org and a project — there is no
  self-describing `ABC-123` key. So the ADO id regex is `^[0-9]{1,10}$` and the org/project
  come from the environment alongside the PAT. This is the one place the ADO contract
  genuinely cannot mirror Jira's shape.
- **Fields are a flat map** under `fields`, keyed by reference name. Verified reference
  names and data types (Microsoft Learn, read 2026-09-14):

  | Field | Reference name | Data type | Applies to |
  |---|---|---|---|
  | Title | `System.Title` | String | All |
  | Description | `System.Description` | **HTML** | All |
  | ID | `System.Id` | Integer | All |
  | Work Item Type | `System.WorkItemType` | String | All |
  | Team Project | `System.TeamProject` | String | All |
  | State | `System.State` | String | All |
  | Acceptance Criteria | `Microsoft.VSTS.Common.AcceptanceCriteria` | **HTML** | **Bug, Epic, Feature, Product Backlog Item (Scrum) ONLY** |
  | Repro Steps | `Microsoft.VSTS.TCM.ReproSteps` | **HTML** | **Bug only** |

- **CORRECTION — acceptance criteria is NOT universally present.** It is annotated
  "(Scrum)" in the field index and the field table scopes it to Bug, Epic, Feature and
  Product Backlog Item. An **Agile User Story and a Task have no Acceptance Criteria
  field at all.** So the ADO resolver still needs a resolution ORDER and an
  `acceptance_criteria_source` discriminator, much like Jira's — though the paths differ:
  (1) the `Microsoft.VSTS.Common.AcceptanceCriteria` field when present and non-empty;
  else (2) an "Acceptance Criteria" heading section of the rendered description; else
  (3) empty. Unlike Jira there is **no field-catalogue GET** — the field either appears in
  the `fields` map or it does not, so path (1) is a dict lookup, not an HTTP call. Do not
  treat a missing field as a resolve failure; it is the common case for User Stories.
- **A Bug's detail usually lives in `Microsoft.VSTS.TCM.ReproSteps`, not
  `System.Description`.** A resolver that reads only `System.Description` will report an
  empty description for most bugs. Decide deliberately how to surface Repro Steps (a
  separate record field is cleaner than silently substituting it) and record the choice.
- **Description is HTML**, not ADF JSON. The analogue of `adf_to_text()` is an
  `html_to_text()` walker over tag soup and entities (`<br>`, `<div>`, `<ul>/<li>`,
  `&amp;`), lossy-by-design in the same way. `html.parser` / `html.unescape` are stdlib.
- **Human URL** is `_links.html.href` on the work-item response.
- **Comment id hazard**: the comment-list *definition table* names the field `id`, while
  Microsoft's own *sample payloads* on both the list and add pages show `commentId`. Read
  defensively (accept either, prefer whichever is present) and cover both in tests.
- **Comment format**: a comment carries a `format` enum (`markdown` | `html`) and an
  optional `renderedText`, but the documented Add body has only `text` — there is no
  documented way to assert the format on write. Render bodies that read correctly either
  way, and say that limit in the command prose rather than claiming control you lack.
- **Version-sensitivity note**: PATs are still supported (page updated 2026-09-04) but
  Microsoft now recommends Entra tokens "whenever possible". Note this in the command
  prose; building an OAuth flow is explicitly out of scope for this run.

## 13. Key-file map

- `plugins/spec-loop/scripts/` — shipped runtime. `jira_client.py` / `jira_intake.py`
  (the connector to mirror), `pr_resolver.py` (read-only provider precedent),
  `dag.py`, `run_state.py`, `redispatch.py`, `worktrees.py`, `quality_gate.py`,
  `run_metrics.py`, `knowledge_graph.py`, `review_package.py`, `dashboard_*.py`,
  `spec_loop_guard.py` (the marker/`.active` guard hooks), `slice_wave_*` (workflow
  harness + node tests).
- `plugins/spec-loop/commands/` — the eight slash commands, incl. `jira-intake.md`.
- `plugins/spec-loop/{agents,references,skills,workflows,hooks}/` — agent definitions,
  the single-home contracts, skills, `slice-wave.workflow.js`, guard hooks.
- `scripts/` — dev/CI tooling only: `measure_coverage.py` + `coverage_omit.txt`,
  `validate_marketplace.py`, `release.py`, and their tests.
- Root: `.gitignore`, `CHANGELOG.md`, `README.md`, `.claude-plugin/marketplace.json`,
  `.github/workflows/validate.yml`.

## 14. Docs to update

`CHANGELOG.md` (Keep-a-Changelog; add under `[Unreleased]`), `plugins/spec-loop/README.md`
and the root `README.md` wherever the Jira connector is listed. `release.py` rolls
`[Unreleased]` into a version section — **do not** hand-edit a released section or bump
the plugin version; version bumps are a separate release step and, per the loop's
invariants, a release-version question is the human's.

## 15. This repo ALREADY talks to Azure DevOps — and why this connector still uses raw REST

**Read this before choosing a transport.** `plugins/spec-loop/scripts/pr_resolver.py`
already supports Azure DevOps for **pull requests**, and it does so by shelling out to the
**Azure CLI**, not by calling REST:

- Host map: `"dev.azure.com": "azure"` (`pr_resolver.py:72`), plus `<org>.visualstudio.com`
  (`:86`, `:159`).
- `_parse_azure_path` (`:145`) parses `/<org>/<project>/_git/<repo>/pullrequest/<n>`.
- `_resolve_azure` (`:297`) requires `shutil.which("az")` and runs
  `az repos pr show --id <n> --org <org_url> --output json` (`:306-311`).

So there are two competing in-repo precedents for reaching Azure DevOps: `pr_resolver`'s
`az` subprocess, and `jira_client`'s hand-rolled `urllib` REST. **This run deliberately
follows `jira_client`, NOT `pr_resolver`.** The reason is not stylistic — the CLI path
cannot implement the safety design, verified against the installed CLI (azure-cli 2.84.0,
azure-devops extension 1.0.2) on 2026-09-14:

- `az boards work-item show|create|update|delete` and `az boards query` are the ONLY
  work-item commands; the sole subgroup is `relation`. **There is no command that lists a
  work item's comments** (`az boards --help`, `az devops --help`).
- The comment **write** does exist, as `az boards work-item update --id N --discussion
  "<text>"`. But with no way to LIST comments, the read-back dedupe gate is impossible —
  and that gate is the only thing standing between a re-run and a duplicate comment on a
  live work item. That is hazard 1 and 2 in §6, unmitigated.
- `az boards work-item update` is also the **general mutation command** (`--fields`,
  `--state`, `--assigned-to`, `--title`). Routing the comment write through it means the
  "bounded write" is an argv-discipline promise rather than a structural property. A REST
  `POST .../workItems/{id}/comments` is structurally comment-only: it cannot transition a
  state or edit a field no matter what you put in the body.
- The one escape hatch, `az devops invoke`, is a generic REST passthrough — that is raw
  REST again, only wrapped in a subprocess, with argv exposure, and `jira_client`'s
  docstring forbids subprocess in a client outright.
- `az devops login` stores a **PAT** anyway, so the CLI path is not even a credential-model
  improvement; it just moves the same secret into a store this connector would then have to
  read.

**Therefore**: `ado_client.py` is stdlib `urllib` REST with an env-var PAT, mirroring
`jira_client.py`'s transport doctrine (§4). Do **not** add an `az` dependency, do **not**
call `az devops invoke`, and do **not** modify `pr_resolver.py` — its ADO PR lane is
out of scope (see request.md's scope ceiling) and is a different resource entirely.

One thing worth BORROWING from `pr_resolver.py`: its `<org>.visualstudio.com` handling and
its URL-path parsing shape are a tested precedent for the legacy org host form. Copy the
shape (duplication over coupling), do not import it.

## 16. Two structural details worth copying exactly

**(a) How a GET is made structurally incapable of writing.** `pr_resolver._http_get`
(`pr_resolver.py:191-202`) does NOT take a `data` parameter at all:

```python
def _http_get(url, headers=None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()
```

`urllib.request.Request` infers POST from a non-`None` `data`, so **omitting the parameter
from the signature entirely** — rather than passing `data=None` — means the function has no
expressible write path, and no `method=` parameter exists for a caller to widen. That is the
whole proof. Keep the literal `method="GET"` and keep `data` off the signature.
`timeout=30` on every call.

**(b) Redirects: follow `jira_client`, NOT `pr_resolver`.** `pr_resolver` uses bare
`urlopen`, so it FOLLOWS redirects and urllib copies `Authorization` to the new URL. That is
defensible there only because its origin is a hardcoded literal
(`https://api.bitbucket.org/2.0/...`, `:330-333`) — a trust decision already made. **The ADO
org URL is user-supplied, exactly like Jira's base URL**, so the `pr_resolver` property is
gone and the `jira_client` treatment is mandatory: refuse redirects outright via a
`_NoRedirect` handler on a module-level opener (`jira_client.py:168-179`). `jira_client`'s
docstring (`:33-36`) records this as a deliberate divergence from `pr_resolver`; do not
regress it.

Also worth copying from `pr_resolver`: `_run` as the SOLE subprocess entry point with
`shell=False` and never a secret in argv (`:170-188`), and `--end-of-options` before any
untrusted value in a git/CLI argv. (The ADO client needs no subprocess at all — see §15 —
but the intake command's `Bash` discipline is the same idea.)

## 17. The Jira command's step structure (the template for ado-intake.md)

From `commands/jira-intake.md`. Mirror the shape and the ordering guarantees:

1. **Validate the id, then ensure the ignore entry** (`:78-90`). Full-match the id regex
   (no whitespace, no newline, no path segment); on failure print `error: invalid …` and
   stop — nothing fetched, nothing written. Then ensure the artifact-root line exists in
   the invoking repo's `.gitignore`, appended by `Bash` as a **constant string** with
   nothing provider-derived in it. **Containment comes before anything else** because work
   item text may be private while the repo may be public.
2. **Resolve, read-only** (`:92-100`). Id passed as a **separate argv token**, never
   spliced into a shell string. Save the record JSON **verbatim** to `<tmp>/record.json`
   (`<tmp>` from `mktemp -d`). Exit 1 → `{"ok": false, "errors": [...]}` on stdout; exit 2 →
   `error: …` on stderr; either way surface verbatim and stop — **no fallback, no retry
   against another source, no partial intake**.
3. **Refine** (`:102-115`). No script. From the record ALONE — no repo search, no web
   lookup — derive `description`, `acceptance_criteria` (testable statements, saying plainly
   where tightened), `risks` as `{id, risk, severity}` (`high|medium|low`), `gaps` as
   `{id, question, impact, blocking}` (`blocking` true when work cannot honestly start
   without the answer), and `injection_findings` for every place the item text tries to
   direct the flow. **Decomposing into slices/waves/a DAG is explicitly out of scope here.**
4. **Ask every gap in ONE batched `AskUserQuestion` round** (`:117-123`). Recommended
   default first; never one at a time; never a second round to chase a skipped answer. Every
   gap's options carry a final **"No answer — log as an open question"**. An unanswered gap
   is a legitimate outcome and becomes an `open-question` comment body. Build
   `answers = {"<gap id>": {"answer": <str|null>, "logged_as": "decision"|"open-question"}}`,
   with `"decision"` only where the human actually answered.
5. **Render** (`:125-135`). Write the refinement object to `<tmp>/refinement.json`, then
   shell the renderer with `--record`, `--refinement`, `--ts <ISO-8601 now>`. **"You own the
   clock: pass the timestamp; the script never reads one."** Payload carries `ok`,
   `issue_key`, `artifact_path`, `artifact`, `comments`, `ranked_gaps`, `posted`
   (**always `false`** at this stage).
6. **Persist the artifact** (`:137-163`). No script. **Assert `artifact_path` starts with
   the artifact root BEFORE writing** — if not, stop and say so rather than writing
   anywhere else — then `Write` the `artifact` string verbatim, never re-rendering by hand.
7. **Preview the comment bodies** — zero writes.
8. **Confirm, then post** — a separate `AskUserQuestion`, and only then the `--post` flag.

## 18. The project comes from the READ, never from the environment

The council's sharpest design catch, and it is verifiable from the two endpoint contracts:

- The work-item read takes `project` as an **optional** path segment — the
  `GET .../{organization}/_apis/wit/workitems/{id}?api-version=7.1` form is valid (the
  URI-parameter table marks `organization` required and `project` not).
- The comment list and comment add both take `project` as **REQUIRED**.
- The work-item response carries **`System.TeamProject`** (String, present on all work
  item types) in its `fields` map.

So the correct shape is: **resolve the work item with org + id alone, then take the project
for every comment call from the resolved record's `System.TeamProject`.** Consequences:

- **`ADO_PROJECT` is OPTIONAL, never required — and when set it is an assertion.** The
  council split here and the synthesis matters. `plan-critic` wanted the read issued on the
  project-qualified route using an env project, then `System.TeamProject` asserted equal to
  it, arguing that discovering the project afterwards leaves the env value unvalidated.
  That argument presupposes an env value exists. Removing the input is strictly stronger
  than validating it — **you cannot mis-set what you do not set** — and it deletes half of
  the preview/post drift surface in §19. So: resolve on the project-optional route with
  org + id, take `project` from `System.TeamProject`, and if `ADO_PROJECT` happens to be
  set, treat it as an assertion and **refuse on mismatch, naming both values, preferring
  neither**. The required credential surface is just `ADO_ORG_URL` and `ADO_PAT`.
- An operator-supplied project can no longer *disagree* with the work item's actual
  project. A mismatched env var would otherwise let the comment lane address a
  project-qualified route for an item that lives elsewhere, and the failure mode is a
  confusing 404 at best and a comment on the wrong item's route at worst.
- Therefore `project` must be a field of the normalized record (so the comment lane, which
  is a separate invocation reading `--comments` plus the id, can reconstruct the route),
  and it belongs in `REQUIRED_FIELDS` — an empty `System.TeamProject` is a half-resolve and
  must raise rather than emit a partial record.
- The comment lane must **re-resolve or be handed the record**, not trust an argv project.
  Mirror `jira_client.run_comment_lane`'s shape, but note it needs the project too: derive
  it, never accept it as a flag (a flag re-opens exactly the disagreement this closes).

## 19. THE WRONG-TARGET WRITE — the write lane's defining hazard (no Jira analogue)

Jira's `ABC-123` names its own project and is unique within a site. An ADO work item is a
bare integer plus an org and a project that come from outside the id. Three consequences,
none of which Jira can even express:

1. **Marker collision across orgs.** A marker hashing `id + kind + payload` is
   **identical** for work item 1234 in org A and work item 1234 in org B.
2. **Preview/post target drift — the unrecoverable one.** The preview (step 7) and the
   armed post (step 8) are separate invocations. If the org changes between them — a
   different shell tab, a sourced `.env`, a mistyped re-export — the connector posts
   *item A's* refinement onto *item B*. The dedupe read-back **succeeds** (item B has no
   such marker), so the operator sees a clean success. There is no comment-delete lane, so
   it cannot be undone.
3. **Artifact path collision.** `.spec-loop-ado/1234/intake.md` is the same path for every
   org and project; two intakes silently overwrite each other and the survivor is
   indistinguishable from the other.

### Required remedy (merging the two council lanes — read this carefully, they interlock)

`plan-critic` requires the project to come from the READ (§18). `guardian` requires the
armed post to refuse on a target mismatch. Naively combined these conflict, because there
is no `ADO_PROJECT` in the environment to compare against. The coherent merge is:

- **Resolve** with `ADO_ORG_URL` + `id` only. The record carries **`org`, `project`
  (from `System.TeamProject`), and `id`** — all three in `REQUIRED_FIELDS`, so an empty
  one is a half-resolve that raises.
- **`comment_marker` hashes `org + project + id + kind + payload`** (still excluding the
  timestamp, per §5).
- **The comments payload carries the `(org, project, id)` triple**, not just the entries
  array. This is the binding between a rendered preview and the item it was rendered for.
- **At post time, before any write**, the comment lane re-resolves the work item (it must
  GET anyway — the dedupe read-back needs the comment list, which needs the project) and
  **refuses unless the payload's `(org, project, id)` equals the freshly resolved triple**,
  with `org` also checked against the current `ADO_ORG_URL`. Order the refusal **before
  `credentials()` is read**, mirroring `jira_client.py:861-875`.
  The project is therefore *derived*, never accepted as a flag — a flag would re-open the
  exact disagreement this closes.
- **`artifact_path` includes validated org and project segments.** Both are now
  path-bearing, so both get `re.fullmatch` allow-lists, and `artifact_path`'s
  sanitize-and-assert (`jira_intake.py:82`) stays intact — validate, compose, then
  re-assert the result is under the artifact root.
- **Step 8's confirmation prose must name the resolved `System.Title` and the
  `_links.html.href` URL**, not just the numeric id. An integer typo lands on a real,
  different work item; a Jira key typo usually 404s. Seeing *which* item is the operator's
  only defence.

## 20. What this repo's tests CANNOT verify about the write lane

`guardian` flags that the dedupe gate reduces to one claim — *the marker we POST comes back
findable in the comment list* — and part of that chain is unverifiable against a faked
transport:

- **RESOLVED from the docs.** Whether `comments[].text` is returned without `$expand`: it
  is. The Get Comments sample request passes only `$top=2&api-version=7.1-preview.4` (no
  `$expand`) and every comment in the sample response carries `text`. `$expand`
  (`CommentExpandOptions`) only adds `reactions` / `renderedText`; `text` is in the base
  `Comment` definition. So the dedupe haystack is populated by default. Still, **assert it**:
  a comment page whose entries lack `text` must be a **fail-closed error**, never a silently
  empty haystack (that failure mode double-posts on every run).
- **NOT resolvable locally.** The marker's byte-survival across the **write/read
  api-version asymmetry** (POST `7.0-preview.3`, read back `7.1-preview.4`) is an
  assumption. ADO may normalize a comment body on write (it carries a `format` enum the Add
  body cannot set). No faked-transport test can close this; it needs one live round trip
  against a real org.

**Doctrine consequence**: the command's prose must not claim a guarantee this repo has not
verified (§6 hazard 3). Prefer a marker built from characters no HTML/markdown normalizer
will rewrite (plain ASCII alphanumerics in a stable literal wrapper — avoid characters that
an HTML renderer may entity-encode, and avoid anything markdown treats as emphasis), and
state the live-verification limit plainly rather than asserting round-trip fidelity.


## 21. The dedupe gate must search `text`, NOT `renderedText` (BLOCKING)

ADO comments carry **both** `text` (what was stored) and `renderedText` (an optional HTML
*rendering* of it, returned only under `$expand`). Jira's gate searches what was stored —
`_normalize_comment` → `body` → `plan_comments(comments, existing_bodies)`
(`jira_client.py:582,750`).

An implementer mirroring "use the readable body" will reach for `renderedText`, because it
reads better. That is a double-post bug: a marker that the HTML renderer alters, entity-
encodes, or strips goes **unmatched**, so every entry plans as not-already-posted and the
lane posts again on a live work item — the exact outcome the whole dedupe design exists to
prevent.

**Required:**
- Normalize the dedupe haystack from **`text`** only.
- Pin it in a **named test** that would fail if a later change repointed the gate at
  `renderedText`.
- If `renderedText` is surfaced in the record at all, make it a **separate field the gate
  never consults**, and say so in the field's comment.
- A comment page whose entries lack `text` is a **fail-closed error** (§20), never a
  silently empty haystack.

## 22. Artifact path must carry the project (BLOCKING)

`jira_intake.artifact_path` (`:82`) composes `<root>/<KEY>/intake.md` and leans on the key
being unique within a site. `.spec-loop-ado/42/intake.md` is **not** unique — work item 42
exists in every project — so two different items silently overwrite each other's intake and
the survivor is indistinguishable from the other.

**Required:** put the project (derived from the record per §18) in the path, e.g.
`.spec-loop-ado/<project>/<id>/intake.md`. Both new path-bearing segments (`project`, and
`org` if included) need their own `re.fullmatch` allow-lists, and `artifact_path`'s
**sanitize-and-assert** shape must stay intact: validate every segment, compose, then
re-assert the composed result sits under the artifact root. An ADO project name is far more
permissive than a Jira key — it may contain spaces and unicode — so the allow-list and any
path-safe encoding of it is a real design decision, not a copy of `ISSUE_KEY_RE`.

## 23. NEVER follow the server-supplied `nextPage` URL (BLOCKING — security)

The Get Comments response carries **both** `continuationToken` and `nextPage`, a
fully-formed URL **chosen by the server**. Fetching `nextPage` re-sends
`Authorization: Basic base64(":" + PAT)` to whatever origin that URL names.

**This walks around both of the transport's defences at once:**
- The **host allow-list** validates the *base URL* (§4). `nextPage` never passes through
  it — it is a URL the client fetches voluntarily.
- The **redirect refusal** (§16b) does not apply either, because this is **not a redirect**.
  There is no 3xx to refuse; the client simply asks for a URL the response body handed it.

**Required:** never fetch `nextPage`. **Compose every page URL yourself** from the
already-validated base URL plus the `continuationToken` value (which must itself be
regex-validated and percent-encoded before it reaches a query string). This is what the
Jira lane effectively does — it composes its own paged URLs rather than following a
server-supplied link. If `nextPage` is surfaced in the record at all, it is inert data that
nothing ever fetches, and its field comment should say so.

## 24. Comment-sweep integrity rules

All four are fail-closed, in the doctrine of `_page_total` (`jira_client.py:596`): a value
that would silently *shrink* the dedupe haystack must raise, never default to empty.

1. **Missing or empty `text` on a returned comment raises.** 2(b) is resolved — `text` is
   on the base `Comment` definition and is returned without `$expand` — but keep the check,
   because three real shapes still produce a text-less comment: a redacted/deleted comment
   surfaced under `includeDeleted`, a legitimately empty comment, and any future projection
   change. A documented default projection is not a runtime guarantee.
2. **`totalCount` cross-check.** Sweep until `continuationToken` is absent, cap at
   `MAX_COMMENT_PAGES`, **and** assert `len(collected) >= totalCount` at the end.
   Terminating with fewer comments than `totalCount` must **raise** rather than dedupe
   against a truncated history. A missing or non-numeric `totalCount` also raises — never
   treat it as 0.
3. **`includeDeleted` stays at its default (deleted comments excluded).** Consequence,
   which **must be in the command prose**: deleting a spec-loop comment in the ADO web UI
   *re-arms* that comment, so a later armed run will post it again. That is the correct
   behaviour — do **not** set `includeDeleted=true` to "fix" it, because that would make a
   deleted comment permanently suppress a legitimate re-post.
4. **Match markers by regex extraction into a set, not by substring** (see §25).

## 25. Making the marker robust to the write/read format round trip

§20's irreducible unknown (POST `7.0-preview.3`, read back `7.1-preview.4`, and ADO may
normalize a body it stores with a `format` the Add call cannot set) is **partially
reducible by construction**. The marker shape
`[spec-loop-intake:<kind>:<12 hex>]` already contains no HTML-escapable character
(`& < > " '`) and no destructive markdown construct. Four constructions close the residual:

1. **Extract-and-compare-sets, never substring.** Pull
   `\[spec-loop-intake:(?:understanding|decision|open-question):[0-9a-f]{12}\]` out of each
   read-back body and compare sets. This survives HTML wrapping (`<div>[marker]</div>`),
   whitespace/newline normalization, and entity-escaping of *neighbouring* characters — the
   plausible round-trip mutations.
2. **Two-tier match: the full marker OR the bare 12-hex digest as a standalone token.**
   This strictly increases suppression, which is the **fail-safe direction**: a false
   suppression skips a write, a false miss duplicates on a live item.
3. **Keep the marker on line 1 of the body**, as `render_comment` already does — maximal
   survival under truncation or a rendering change.
4. **Escape the body so the marker is never adjacent to an escapable character**, removing
   the one way escaping could perturb it.

**What is not available:** no local-state substitute (hazard 2 forbids a file as the dedupe
gate), and the add response's comment id cannot help a later run.

**So it stays one live-org verification item — but the blast radius is bounded**: exactly
one duplicate comment on one work item, on the **first armed post ever**. Discharge it as a
named procedure: take one work item, post once, read the list back, confirm the marker is
extracted, run armed again, confirm `already-posted`. Record that evidence in the run and
**gate the arming prose on it**. The property is self-reinforcing — after the first
success every later armed run carries live proof in hand, because its own read-back
contains prior markers.

## 26. `org` is the residual env input — close it against `_links.html.href`

Making `ADO_PROJECT` optional (§18) removes half the wrong-target surface, but **`org` is
unavoidably an environment input**, and a wrong org mis-targets exactly like a wrong
project. Close it the same way the project is closed — against the response itself:

- The work-item response's **`_links.html.href`** carries the org in its path. **Assert the
  resolved org appears there and refuse on mismatch.**
- `credentials()`'s fail-closed message must list only **`ADO_ORG_URL` + `ADO_PAT`** as
  required, describing `ADO_PROJECT` as an *optional assertion* — otherwise the message
  demands a variable the design says to leave unset.

## 27. Path composition for a project name (BLOCKING) — slug, do not sanitize

`jira_intake.artifact_path` is safe *by accident*: `ISSUE_KEY_RE` already yields a
filesystem-safe key, so the `startswith(root + "/")` re-assert is pure defence-in-depth.
Put a project name in the path and the allow-list becomes load-bearing — and an ADO project
name may contain **spaces, unicode, and dots**.

**Do not allow-list the project name.** A regex permissive enough to accept real names
(`My Team – Platform`) is too permissive to be a security control; one tight enough to be a
control rejects legitimate projects. Instead:

- **Slug by an explicit, lossy, total transform**: casefold → replace every character
  outside `[a-z0-9._-]` with `-` → collapse runs → strip leading/trailing `-` and `.` →
  cap at ~48 chars → **refuse an empty result**. This is whitelist-by-construction, so
  `..`, `/`, `\`, NUL and every unicode path trick are **structurally unrepresentable**
  rather than checked-for.
- **Append a stable discriminator from the ORIGINAL name** (first 8 hex of its sha256) so
  two projects that slug identically cannot collide:
  `.spec-loop-ado/<slug>-<hash8>/<id>/intake.md`.
- **Keep the re-assert anyway**, exactly as Jira does and for the same stated reason: a
  later change to the composition cannot escape unnoticed.
- **Refuse — never rewrite — a project name containing a control character or a line
  break.** `_errors_for_id_newline` (`jira_intake.py:113`) already establishes that idiom;
  the project name also lands in the artifact front matter, where `_neutralize_delimiters`
  (`:427`) handles delimiters but a raw newline inside a `"`-quoted scalar is still a
  hazard.
- **URL encoding is a SEPARATE concern and must not reuse the slug.** The comment URLs need
  the **original** project name, `urllib.parse.quote(..., safe="")`-encoded. Two distinct
  transforms from one source value — **say this in the docstring**, because an implementer
  who reuses the slug in the URL gets a 404 on every project whose name contains a space.

## 28. A direct port of `render_comment` posts a MANGLED comment (BLOCKING)

`jira_intake.render_comment` (`:353`) joins body lines with `"\n"` and relies on
`text_to_adf` (`jira_client.py:453`) to convert each line into an ADF paragraph at POST
time. **ADO has no conversion step**: the Add body is `{"text": …}` and there is no
documented way to assert `format` (§12).

If the project renders comments as **markdown**, single newlines are not line breaks — the
heading, the marker, the timestamp and every bullet collapse into **one run-on paragraph**.

**Correction:** render **blank-line-separated blocks**, so the body reads correctly whether
interpreted as markdown or as plain text. Per the council, this is the failure **most likely
of all of them to be noticed by a human on the first real post** — and it interacts with
§25.3 (keep the marker on line 1) and §25.4 (keep the marker away from escapable
characters).

## 29. Three api-versions, three constants

Jira has one api-version literal; ADO has three that differ **on purpose** (§12). Give each
its own named module constant and **add a test asserting they are not all equal**, so a
well-meaning "consistency" edit that collapses them to one string fails loudly instead of
silently breaking either the comment sweep or the write.

## 30. The undeclarable body format is an INJECTION problem, not just a readability one (BLOCKING)

§28 treats the unassertable `format` as a *rendering* defect. It is also an **injection**
defect, and this is the single place where "mirror the Jira lane exactly" is actively
insufficient — **the mirror loses a safety property the original got for free.**

**Defect.** The posted payload is the model's refinement, derived from the work item's HTML
`System.Description`, `Microsoft.VSTS.Common.AcceptanceCriteria` and
`Microsoft.VSTS.TCM.ReproSteps`. Jira cannot write active markup: `text_to_adf`
(`jira_client.py:453`) emits **ADF text nodes, escaped by construction** — the inertness is
structural, not something anyone had to remember. ADO's Add body is an undeclared-format
string, so that guarantee silently disappears.

**Failure scenario.** If ADO stores or renders the posted text as HTML, the connector writes
**attacker-influenced markup into a live work item, under the operator's PAT**, readable by
everyone with access to that item, **with no comment-delete lane to retract it**.

**Required remedy.**
- **Escape `&`, `<`, `>` in the rendered body before it is posted.** The body is then inert
  under either interpretation. The marker contains no escapable character, so dedupe is
  provably unaffected — **assert that in a test** rather than reasoning about it.
- **Union the dedupe haystack**: match the marker against the raw `text` field **and**
  against the `html_to_text` rendering. Both fail safe, but they differ where it matters —
  a marker forged inside an HTML comment is **invisible to the walker** (which drops
  comments) and **visible in raw `text`**.
- **State the limit in prose; do not overclaim.** The connector cannot control how ADO
  interprets the body; it guarantees only that the body contains **no active markup**. Pin
  that sentence in `test_doctrine_ado_intake.py` — per §6 hazard 3, claiming control you do
  not have is a defect on a mutating lane.

## 31. Generalize the no-body-URLs rule — including the one URL the design *does* keep

Additions to §23:

- **`continuationToken` must fail closed.** It is an opaque server-chosen string:
  regex-validate it (`^[A-Za-z0-9+/=_.\-]{1,512}$`), percent-encode with
  `quote(..., safe="")`, and **raise on a token that does not match** — do **not** drop it.
  Dropping it silently truncates the haystack, which is exactly the §24 failure mode.
- **State the general rule in the module docstring**: *no URL from a response body is ever
  fetched; every URL is composed locally from the validated origin plus a literal path.*
- **Apply it to `_links.html.href`, the one body-supplied URL the design keeps.** It is
  **displayed and stored, never fetched** — but it is displayed in **Step 8's confirmation
  prompt**, which is precisely where the operator decides whether to authorize an
  irreversible write. So **validate its host against the same allow-list before printing
  it**, or a spoofed href appears to the operator as a genuine work-item link at the moment
  of authorization. (Note this also carries the org assertion in §26 — same field, two
  checks.)
