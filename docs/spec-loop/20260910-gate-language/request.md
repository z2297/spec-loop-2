# Request

**Verbatim user request:** "Fix the two defects found and enhance with an indent-based model"

**Origin:** the immediately preceding investigation of `plugins/spec-loop/scripts/quality_gate.py`,
which answered "will the quality gate checks work outside of C#?". The investigation was
measurement-based: the gate was run at HEAD over a purpose-built multi-language sample repo, and
every claim below was observed in its JSON output, not inferred from reading.

## Restatement (two sentences)

Repair the two measured defects in the quality gate's builtin C-family heuristic — control
keywords being extracted as phantom functions, and `foreach` contributing nothing to cyclomatic
complexity — and extend the analyzer's language reach by generalising its indent-based model.

## The two defects (both measured, not inferred)

**D1 — control keywords extracted as phantom functions.**
`_CONTROL_WORDS` (`plugins/spec-loop/scripts/quality_gate.py:944`) is
`{"if", "for", "while", "switch", "catch", "else", "do", "return", "case"}` — a JS/Java-shaped
list. `_looks_like_call_or_control` (`:948`) is its only consumer, guarding
`_extract_functions_cbrace` (`:918`). C#'s `foreach`, `using`, `lock`, `fixed` and Java's
`synchronized` are absent, so a statement like `foreach (var x in Items) {` matches
`_CBRACE_DEF_RE` (`:147`) and is extracted as a function.

Measured on a C# sample (`public class G` with `if`/`while`/`using`/`lock` blocks), the gate
reported functions `Run`, `using`, and `lock` — `if` and `while` were correctly suppressed. On a
second sample a `foreach` block was reported as a function named `foreach` carrying its own five
metric rows.

Impact: mostly noise (phantom functions are small and pass), but a control block whose body
exceeds a threshold — a 60-line `foreach`, a deeply nested `using` — is reported as a FAILING
function that does not exist. That is a false-positive block, and a false block costs a fix
cycle or an escalation.

**D2 — `foreach` is not a branch.**
`_BRANCH_WORDS` (`:135`) is `("if", "elif", "case", "catch", "for", "while", "when")` and
`_BRANCH_WORD_RE` matches on `\b` boundaries, so `\bfor\b` does NOT match `foreach`. Every C#
(and PHP) `foreach` loop therefore contributes 0 to cyclomatic complexity.

Measured: a C# method containing one `foreach`, one `if` with an `&&`, and one `switch` `case`
scored `cyclomatic_complexity 4` = 1 base + if + && + case. The `foreach` contributed nothing.

Impact: a genuine undercount, in the unsafe direction — the heuristic's whole design premise
(documented at `:116-132`) is that it may over-count but must never under-count, because an
over-count is a false alarm a human dismisses while an under-count is a real violation that
ships. D2 breaks that premise for C#.

Note the two defects interact: adding `foreach` to `_BRANCH_WORDS` without also adding it to
`_CONTROL_WORDS` would leave the phantom `foreach` function counting its own branch keyword.

## The third item — MATERIALLY AMBIGUOUS, must be resolved before planning

"enhance with an indent-based model" admits at least three readings that produce different work:

- **(A) Generalise the existing Python indent model into a reusable indent/`end` family**, and
  route genuinely non-brace languages to it — principally Ruby (`def`/`end`), and arguably
  CoffeeScript/Nim. This is the narrowest reading and the one closest to the words: the file
  already HAS an indent model (`_extract_functions_python` `:892`, `_nesting_depth_python` `:972`),
  so "enhance with" reads as "lift it out of Python-only and reuse it".
- **(B) Add a generic indent-based FALLBACK for every currently-unsupported extension**, so that
  no changed file is silently skipped. Today anything outside `_EXT_LANG` (`:107`) — Ruby,
  Kotlin, Swift, PHP, Scala, shell, SQL, `.vue`, `.svelte` — is reported as
  `"unsupported file type for analysis"`, and a slice touching only such files passes with
  `checks: 0, vacuous: true` and exit 0. Measured on a Ruby-only diff. This is the reading that
  closes a real hole, but a language-agnostic indent guess is a much weaker signal and risks
  false positives on languages whose indentation is not structural.
- **(C) Both, plus the free win**: (A) or (B) AND extend `_EXT_LANG` with the brace languages
  that need no new model at all — `.kt`, `.swift`, `.scala` are C-family and would be covered by
  routing alone.

These are not stylistic variants. (A) is one new language family; (B) changes the meaning of a
passing gate for every unsupported file in every future run; (C) is a superset. The decomposition,
the slice count and the risk tier all differ. **This is the run's one intake question.**

## Explicitly OUT of scope (candidate run-level scope_ceiling)

- Installing, vendoring, or requiring `lizard` or `radon`. The gate detects them read-only via
  `shutil.which` and must keep working without them; neither is installed on this machine, so
  every measurement here runs on `builtin-heuristic`.
- Weakening any threshold, or adding anything to `coverage_omit.txt`, to get a gate result green.
- Reworking the string/comment scan mask for non-JS brace languages (`_JS_MASK_EXTS` `:132`).
  The over-count for C#/Java/Go/Rust/C++/JSX is a DELIBERATE, documented safety choice
  (`:116-132`); changing it is a separate decision with its own risk argument.
- Adding coverage-report formats (e.g. jacoco XML). CRAP currently parses cobertura and lcov only.
- Refactoring `quality_gate.py` or `test_quality_gate.py` to get under the 300-line `class_lines`
  threshold. Both are far over it already and that is pre-existing debt, not this run's work.
- Making the per-slice pipeline read `summary.vacuous`. Only `references/phase-5-integration.md:14`
  instructs a reader to check it; wiring it into the slice path is a real gap but a DIFFERENT
  change to a different file, and folding it in here would double the run's blast radius.

## Hard constraints discovered at intake

1. **The run cannot measure its own fix.** `quality_gate_cmd` points every wave agent at
   `<plugin_root>/scripts/quality_gate.py` — the frozen `~/.claude/plugins/cache/.../2.5.0` copy,
   verified byte-identical to the repo copy at intake. Editing the repo copy does NOT change the
   gate that measures this run's slices. That is desirable (a stable measuring stick), but it
   means the ONLY evidence that the fix works is the repo copy's own unit tests, executed
   directly. No agent may claim the defect is fixed because a gate run came back green.
   Prior precedent for the inverse hazard: run 20260826's runbook, "running them against the
   frozen cache makes the check vacuous".
2. **Every slice in this run will produce a `class_lines` gate FAIL.** `quality_gate.py` is 1403
   non-blank lines and `test_quality_gate.py` is 1629, against a 300 threshold. Any edit to either
   pulls that whole-file violation into the slice diff. Precedent exists (runs 20260825 and
   20260826 accepted class_lines as pre-existing debt under one ruling, with new function-level
   violations still blocking) but that ruling was scoped to those runs and named other files.
   A standing ruling for THIS run is requested at intake so it does not become a mid-wave stall.
3. **Neither backend is installed**, so builtin-heuristic behaviour is the whole product here.
