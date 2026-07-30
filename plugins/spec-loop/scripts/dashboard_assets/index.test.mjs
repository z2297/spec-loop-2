// index.test.mjs — the sole automated guard on the dashboard client's behavior.
//
// Node BUILT-INS ONLY (node:test + node:assert; node:fs/os/path/url). No npm
// dependency, no package.json, no third-party test runner or DOM library — this
// preserves the repo's zero-dependency posture, mirroring test_dashboard_server.py's
// "stdlib only" intent on the client side.
//
// The page (index.html) stays a self-contained single file that works opened
// directly in a browser: its logic lives in one inline <script> and the browser
// loads nothing else. To bring that inline JS under test WITHOUT a bundler or a
// network fetch, this harness:
//   1. reads index.html and extracts the single <script> body,
//   2. strips the browser-inert `/* test-export */` UMD tail,
//   3. appends an equivalent ESM `export { ... }`,
//   4. writes the result to a temp .mjs and `import()`s it as a REAL module.
// Loading a real on-disk module (rather than node:vm-evaluating a string) is what
// lets `node --test --experimental-test-coverage` attribute coverage to the client
// code. No document/window exist under Node, so the script's HAS_DOM guard keeps
// the bootstrap (listeners, timers, fetch) dormant on import.
//
// Behavior asserted here mirrors the verified server contract in
// test_dashboard_server.py: single/multi-root grouping, the namespaced-id
// (<root>:<runId>) hash round-trip, and — for run-state v2 — recorded-vs-projected
// wave rows, the sidecar-derived labels and outcome cards, and the fact that every
// unknown value renders as an em dash rather than "undefined".

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const HTML_PATH = join(HERE, "index.html");

// The exact surface the page exposes for test. Kept identical to the page's
// /* test-export */ list; the loader asserts the page's tail matches this set so
// the two can never silently drift.
const EXPORTS = [
  "labelClass", "verdictClass", "waveStatusClass", "outcomeClass", "metricsSourceLabel",
  "tokensBasisLabel", "sha7", "truncate", "dash", "groupRunsByRoot", "parseHashFrom",
  "el", "overviewCard", "rootGroupSection", "sliceRow", "__setDocument",
  "stageStrip", "councilSection", "executionSection", "finalReviewSection", "escalationsSection",
  "wavesSection", "waveTitle", "outcomesSection", "sidecarLines", "constraintsSection",
  "provenancePills", "metricsSection", "overviewMetricPills", "fmtMetric", "fmtDuration",
];

// Extract the inline <script> body and rewrite it into an importable ES module:
// strip the browser-inert UMD /* test-export */ tail and append an equivalent ESM
// `export { ... }`. Also asserts the page's export tail lists EXACTLY the EXPORTS
// surface (bidirectional — neither the page nor the harness may drift silently).
function extractClientSource() {
  const html = readFileSync(HTML_PATH, "utf8");
  const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)];
  assert.equal(scripts.length, 1, "expected exactly one inline <script> in index.html");
  let body = scripts[0][1];

  const tail = body.match(/\/\* test-export \*\/[\s\S]*$/);
  assert.ok(tail, "index.html is missing the /* test-export */ tail");
  // Compare only the identifiers inside the `module.exports = { ... }` object
  // literal against EXPORTS, as exact sets — this catches drift in BOTH directions
  // (a name added to the page but not here, or removed from the page but still here).
  const objMatch = tail[0].match(/module\.exports\s*=\s*\{([\s\S]*?)\}/);
  assert.ok(objMatch, "test-export tail must assign a module.exports object literal");
  const listed = [...objMatch[1].matchAll(/\b([A-Za-z_$][\w$]*)\b/g)].map((m) => m[1]);
  assert.deepEqual(
    [...new Set(listed)].sort(),
    [...EXPORTS].sort(),
    "page /* test-export */ tail must list exactly the EXPORTS surface",
  );

  body = body.replace(/\/\* test-export \*\/[\s\S]*$/, "");
  body += `\nexport { ${EXPORTS.join(", ")} };\n`;
  return body;
}

// Write the rewritten source to a fresh temp .mjs and import it as a REAL module
// so `node --test --experimental-test-coverage` attributes coverage to it (a
// node:vm-evaluated string gets no coverage). A unique temp dir per call yields a
// distinct module URL, so callers can import a fresh (un-cached) copy on demand.
function loadClientModule(source) {
  const dir = mkdtempSync(join(tmpdir(), "dashboard-client-"));
  const modPath = join(dir, "index.client.mjs");
  writeFileSync(modPath, source, "utf8");
  return import(pathToFileURL(modPath).href);
}

// ---- minimal pure-JS DOM shim (only the API index.html's el()/render use) ----
// A node exposes textContent that recursively serializes its element+text children,
// and children (element nodes only) so tests can assert "zero child elements".
function makeDom() {
  function makeNode(tag) {
    return {
      tagName: String(tag).toUpperCase(),
      className: "",
      hidden: false,
      _text: "",
      childNodes: [],           // elements AND text nodes, in insertion order
      get children() { return this.childNodes.filter((n) => n.nodeType === 1); },
      set textContent(v) { this._text = String(v); this.childNodes = []; },
      get textContent() {
        if (this.childNodes.length === 0) return this._text;
        return this.childNodes.map((n) => n.textContent).join("");
      },
      appendChild(child) { this.childNodes.push(child); return child; },
      append(...kids) { for (const k of kids) this.childNodes.push(k); },
      addEventListener() { /* no-op: click/nav wiring is out of scope for these tests */ },
      nodeType: 1,
    };
  }
  return {
    createElement(tag) { return makeNode(tag); },
    createTextNode(text) {
      return {
        nodeType: 3,
        _text: String(text),
        get textContent() { return this._text; },
        set textContent(v) { this._text = String(v); },
      };
    },
  };
}

const CLIENT_SOURCE = extractClientSource();
const mod = await loadClientModule(CLIENT_SOURCE);
mod.__setDocument(makeDom());

// A complete v2 sidecar view, exactly as dashboard_server._sidecar_view emits it.
// Tests override individual fields rather than hand-building partial shapes, so a
// field the server adds shows up in one place here.
function sidecar(overrides) {
  return {
    status: "DONE",
    branch: "spec-loop/run-1/s1",
    risk_tier: 2,
    review_tier: 3,
    critique: { verdict: "ENDORSE_WITH_CONCERNS", concerns: 2 },
    tasks_completed: 4,
    review: { confirmed: 1, refuted: 2, evidence_failed: 0, fix_rounds: 1, residual_count: 1 },
    tests: { result: "pass", scope: "full" },
    quality: { status: "PASS", detail: "" },
    agents_used: 12,
    wave: 1,
    started_at: "2026-07-30T10:00:00Z",
    finished_at: "2026-07-30T10:42:00Z",
    ...(overrides || {}),
  };
}

// ---- 1. loader + smoke: exposes exactly the expected surface, no bootstrap ----
test("module exposes exactly the expected function surface", () => {
  const names = Object.keys(mod).filter((k) => k !== "default").sort();
  assert.deepEqual(names, [...EXPORTS].sort());
  for (const name of EXPORTS) assert.equal(typeof mod[name], "function", `${name} is a function`);
});

test("importing under Node arms no timer, registers no listener, and fires no fetch", async () => {
  // The HAS_DOM guard must keep the whole bootstrap dormant on import. Prove it:
  // install counting spies over the exact globals the bootstrap would touch
  // (fetch is a real Node global, as are setInterval/setTimeout), then import a
  // FRESH copy of the client module under them. A regression that dropped the
  // HAS_DOM guard would fire fetch()/setInterval()/window.addEventListener and
  // trip these counters.
  const calls = { fetch: 0, setInterval: 0, setTimeout: 0, addEventListener: 0 };
  const orig = {
    fetch: globalThis.fetch,
    setInterval: globalThis.setInterval,
    setTimeout: globalThis.setTimeout,
    window: globalThis.window,
  };
  globalThis.fetch = () => { calls.fetch++; return Promise.resolve(); };
  globalThis.setInterval = () => { calls.setInterval++; return 0; };
  globalThis.setTimeout = () => { calls.setTimeout++; return 0; };
  globalThis.window = { addEventListener() { calls.addEventListener++; } };
  try {
    await loadClientModule(CLIENT_SOURCE);   // fresh temp module → real (re)evaluation
  } finally {
    globalThis.fetch = orig.fetch;
    globalThis.setInterval = orig.setInterval;
    globalThis.setTimeout = orig.setTimeout;
    if (orig.window === undefined) delete globalThis.window;
    else globalThis.window = orig.window;
  }
  assert.deepEqual(calls, { fetch: 0, setInterval: 0, setTimeout: 0, addEventListener: 0 });
});

// ---- 2. groupRunsByRoot (mirrors server single/multi-root grouping contract) ----
test("groupRunsByRoot: single root is transparent (one empty-keyed group)", () => {
  const { multiRoot, groups } = mod.groupRunsByRoot([{ run_id: "a" }, { run_id: "b" }]);
  assert.equal(multiRoot, false);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].root, "");
  assert.deepEqual(groups[0].runs.map((r) => r.run_id), ["a", "b"]);
});

test("groupRunsByRoot: multi-root partitions and preserves first-appearance order", () => {
  const runs = [
    { run_id: "a", root: "repoY" },
    { run_id: "b", root: "repoX" },
    { run_id: "c", root: "repoY" },
  ];
  const { multiRoot, groups } = mod.groupRunsByRoot(runs);
  assert.equal(multiRoot, true);
  assert.deepEqual(groups.map((g) => g.root), ["repoY", "repoX"]);
  assert.deepEqual(groups[0].runs.map((r) => r.run_id), ["a", "c"]);
  assert.deepEqual(groups[1].runs.map((r) => r.run_id), ["b"]);
});

test("groupRunsByRoot: empty and null input yield a single empty group", () => {
  for (const input of [[], null, undefined]) {
    const { multiRoot, groups } = mod.groupRunsByRoot(input);
    assert.equal(multiRoot, false);
    assert.equal(groups.length, 1);
    assert.deepEqual(groups[0], { root: "", runs: [] });
  }
});

test("groupRunsByRoot: mixed keyed/unkeyed and non-string roots coerce to the empty group", () => {
  // A run with no `root`, a null root, or a non-string root all fall into the ""
  // group; a single keyed run flips multiRoot on. This is the boundary that
  // decides how a partially-namespaced batch renders.
  const runs = [
    { run_id: "a" },                 // missing root -> ""
    { run_id: "b", root: "repoX" },  // keyed
    { run_id: "c", root: null },     // null -> ""
    { run_id: "d", root: 7 },        // non-string -> ""
  ];
  const { multiRoot, groups } = mod.groupRunsByRoot(runs);
  assert.equal(multiRoot, true);
  assert.deepEqual(groups.map((g) => g.root), ["", "repoX"]);
  assert.deepEqual(groups[0].runs.map((r) => r.run_id), ["a", "c", "d"]);
  assert.deepEqual(groups[1].runs.map((r) => r.run_id), ["b"]);
});

// ---- 3. parseHashFrom namespaced-id round-trip (mirrors server colon round-trip) ----
test("parseHashFrom: overview for empty/bare/non-run hashes", () => {
  for (const h of ["", "#", "#overview", "run/", "#run/"]) {
    assert.deepEqual(mod.parseHashFrom(h), { kind: "overview" });
  }
});

test("parseHashFrom: namespaced run-id survives the encode->parse round-trip", () => {
  // navigate() builds "#run/" + encodeURIComponent(runId); a multi-root id is
  // "<root>:<runId>" — the colon (and any slash) must round-trip intact.
  const runId = "myrepo:20260730-full-coverage";
  const hash = "#run/" + encodeURIComponent(runId);
  assert.deepEqual(mod.parseHashFrom(hash), { kind: "detail", runId, stage: null });

  const slashy = "grp/sub:run-1";
  assert.deepEqual(
    mod.parseHashFrom("#run/" + encodeURIComponent(slashy)),
    { kind: "detail", runId: slashy, stage: null },
  );
});

test("parseHashFrom parses an optional stage segment; run-id ':' survives, first '/' splits", () => {
  assert.deepEqual(mod.parseHashFrom("#"), { kind: "overview" });
  assert.deepEqual(mod.parseHashFrom("#run/r1"), { kind: "detail", runId: "r1", stage: null });
  assert.deepEqual(mod.parseHashFrom("#run/r1/execution"), { kind: "detail", runId: "r1", stage: "execution" });
  // a namespaced <root>:<id> run-id round-trips; only the FIRST '/' splits off the stage
  assert.deepEqual(
    mod.parseHashFrom("#run/" + encodeURIComponent("repoA:r1") + "/final-review"),
    { kind: "detail", runId: "repoA:r1", stage: "final-review" },
  );
});

// ---- 4. small pure formatters ----
test("sha7, truncate, and dash edge cases (incl. exact-length boundaries)", () => {
  assert.equal(mod.sha7(null), "?");
  assert.equal(mod.sha7(""), "");            // empty string is distinct from null
  assert.equal(mod.sha7("abc"), "abc");
  assert.equal(mod.sha7("0123456"), "0123456");   // exactly 7 — unchanged
  assert.equal(mod.sha7("0123456789"), "0123456");
  assert.equal(mod.truncate(null, 5), "");
  assert.equal(mod.truncate("short", 10), "short");
  assert.equal(mod.truncate("abcd", 4), "abcd");  // length === n — NOT truncated
  assert.equal(mod.truncate("0123456789", 4), "0123…");
  // dash is the single "we don't know" renderer: only null/undefined become an
  // em dash, so a real 0 or "" is never disguised as missing.
  assert.equal(mod.dash(null), "—");
  assert.equal(mod.dash(undefined), "—");
  assert.equal(mod.dash(0), "0");
  assert.equal(mod.dash(""), "");
  assert.equal(mod.dash(false), "false");
});

// ---- 5. class allowlists (the load-bearing anti-injection guards) ----
test("labelClass allowlists via hasOwnProperty and rejects inherited/proto keys", () => {
  // The hasOwnProperty guard is the load-bearing detail: a plain LABEL_CLASS[label]
  // lookup would resolve "constructor"/"toString"/"__proto__" to inherited members
  // and leak a garbage class. Assert those all fall back to lbl-unknown.
  assert.equal(mod.labelClass("complete"), "lbl-complete");
  assert.equal(mod.labelClass("split"), "lbl-split");
  assert.equal(mod.labelClass("totally-unknown"), "lbl-unknown");
  for (const proto of ["constructor", "toString", "hasOwnProperty", "__proto__", "valueOf"]) {
    assert.equal(mod.labelClass(proto), "lbl-unknown", `${proto} must not resolve to an inherited member`);
  }
});

test("labelClass covers the three v2-only labels", () => {
  // failed / merge-pending / split-pending exist only under run-state v2 and must
  // each get their own treatment rather than the unknown fallback.
  assert.equal(mod.labelClass("failed"), "lbl-failed");
  assert.equal(mod.labelClass("merge-pending"), "lbl-merge-pending");
  assert.equal(mod.labelClass("split-pending"), "lbl-split-pending");
});

test("verdictClass allowlists council verdicts and falls back for unknown/proto keys", () => {
  assert.equal(mod.verdictClass("ENDORSE"), "v-endorse");
  assert.equal(mod.verdictClass("ENDORSE_WITH_CONCERNS"), "v-ewc");
  assert.equal(mod.verdictClass("OBJECT"), "v-object");
  assert.equal(mod.verdictClass("weird"), "v-unknown");
  for (const proto of ["constructor", "__proto__", "toString"]) {
    assert.equal(mod.verdictClass(proto), "v-unknown", `${proto} must not resolve to an inherited member`);
  }
});

test("waveStatusClass separates recorded statuses from a projection", () => {
  // The visual distinction is the whole point: dispatched/collected are RECORDED
  // in dag.json, projected is the server's forecast of undispatched work.
  assert.equal(mod.waveStatusClass("dispatched"), "w-dispatched");
  assert.equal(mod.waveStatusClass("collected"), "w-collected");
  assert.equal(mod.waveStatusClass("projected"), "w-projected");
  assert.equal(mod.waveStatusClass("unknown"), "w-unknown");
  for (const proto of ["constructor", "__proto__"]) {
    assert.equal(mod.waveStatusClass(proto), "w-unknown");
  }
});

test("outcomeClass allowlists the four sidecar statuses", () => {
  assert.equal(mod.outcomeClass("DONE"), "o-done");
  assert.equal(mod.outcomeClass("SPLIT"), "o-split");
  assert.equal(mod.outcomeClass("ESCALATED"), "o-esc");
  assert.equal(mod.outcomeClass("FAILED"), "o-failed");
  assert.equal(mod.outcomeClass("unknown"), "o-unknown");
  for (const proto of ["constructor", "__proto__"]) {
    assert.equal(mod.outcomeClass(proto), "o-unknown");
  }
});

test("metricsSourceLabel names each provenance, including v2's unavailable", () => {
  assert.equal(mod.metricsSourceLabel("file"), "committed");
  assert.equal(mod.metricsSourceLabel("live"), "live");
  assert.equal(mod.metricsSourceLabel("unavailable"), "unavailable");
  assert.equal(mod.metricsSourceLabel("__proto__"), "__proto__");  // no inherited leak
});

// ---- 6. overview cards ----
test("overviewCard renders a .run card carrying run_id and base_ref@sha7", () => {
  const card = mod.overviewCard({
    run_id: "run-42", base_ref: "alpha", base_sha: "abcdef1234567", counts: {},
  });
  assert.match(card.className, /\brun\b/);
  const text = card.textContent;
  assert.match(text, /run-42/);
  assert.match(text, /alpha@abcdef1/);   // base_ref@sha7 (first 7 of the sha)
});

test("overviewCard short-circuits to a transient placeholder for an unreadable run", () => {
  const card = mod.overviewCard({ run_id: "mid-run", status: "unreadable" });
  assert.match(card.className, /transient/);
  assert.doesNotMatch(card.className, /\bclickable\b/);  // not a normal clickable run card
  assert.match(card.textContent, /mid-run/);
  assert.match(card.textContent, /in progress/);
});

// ---- 7. untrusted-root XSS invariant (the load-bearing security guarantee) ----
test("rootGroupSection renders the raw root key as text only, never as markup", () => {
  const hostile = '<img src=x onerror=alert(1)>';
  const sec = mod.rootGroupSection({ root: hostile, runs: [] });
  const h3 = sec.children.find((n) => n.tagName === "H3");
  assert.ok(h3, "section has an <h3> for the root label");
  // POSITIVE: the raw string is present verbatim as text.
  assert.equal(h3.textContent, hostile);
  // NEGATIVE (the real guarantee): no child ELEMENT nodes were created from the
  // string — it was set via textContent, never parsed as HTML.
  assert.equal(h3.children.length, 0, "root key must not become child elements");
});

// ---- 8. slice table rows (10 columns under v2) ----
test("sliceRow yields 10 cells, truncating the goal and allowlisting the label class", () => {
  const longGoal = "g".repeat(150);
  const row = mod.sliceRow({
    id: "s1", goal: longGoal, risk_tier: 2, depth: 0, parent: null,
    deps: ["s0"], label: "complete", has_report: true, sidecar: sidecar(),
  });
  const cells = row.children;
  assert.equal(cells.length, 10);
  assert.equal(cells[0].textContent, "s1");
  assert.ok(cells[1].textContent.endsWith("…"), "long goal is truncated with an ellipsis");
  assert.ok(cells[1].textContent.length < longGoal.length);
  assert.equal(cells[2].textContent, "2");   // risk_tier
  assert.equal(cells[3].textContent, "0");   // depth
  assert.equal(cells[4].textContent, "—");   // null parent renders as em dash
  assert.equal(cells[5].textContent, "s0");  // deps joined
  assert.match(cells[6].children[0].className, /lbl-complete/);
  assert.equal(cells[7].textContent, "1");   // sidecar wave
  assert.match(cells[8].children[0].className, /o-done/);   // sidecar outcome pill
  assert.equal(cells[9].textContent, "✓");   // has_report -> check
});

test("sliceRow maps an unknown label to lbl-unknown and em-dashes an absent sidecar", () => {
  const row = mod.sliceRow({
    id: "s2", goal: "x", risk_tier: 1, depth: 0, parent: "s1", deps: [],
    label: "some-bogus-label",
  });
  const cells = row.children;
  assert.equal(cells[4].textContent, "s1");  // non-null parent shown verbatim
  assert.equal(cells[5].textContent, "—");   // empty deps render as em dash
  assert.match(cells[6].children[0].className, /lbl-unknown/);
  // No sidecar: wave and outcome are honestly blank, not "undefined", and the
  // outcome cell holds no pill at all.
  assert.equal(cells[7].textContent, "—");
  assert.equal(cells[8].textContent, "—");
  assert.equal(cells[8].children.length, 0);
  assert.equal(cells[9].textContent, "—");   // no report
});

// ---- 9. waves: recorded rows vs projected rows ----
test("waveTitle numbers a wave and tolerates a missing index", () => {
  assert.equal(mod.waveTitle({ index: 3 }), "Wave 3");
  assert.equal(mod.waveTitle({}), "Wave ?");
  assert.equal(mod.waveTitle(null), "Wave ?");
});

test("wavesSection renders one card per wave with its status pill and journal pointer", () => {
  const run = {
    slices: [
      { id: "s1", label: "complete" },
      { id: "s2", label: "runnable-pending" },
    ],
    waves: [
      { index: 1, slice_ids: ["s1"], workflow_run_id: "wf_abc123", status: "collected" },
      { index: 2, slice_ids: ["s2"], workflow_run_id: null, status: "projected" },
    ],
  };
  const sec = mod.wavesSection(run);
  const cards = sec.children.filter((n) => /\bwave\b/.test(n.className));
  assert.equal(cards.length, 2);

  const first = cards[0].textContent;
  assert.match(first, /Wave 1/);
  assert.match(first, /collected/);
  assert.match(first, /journal wf_abc123/);   // the durable pointer to the workflow journal
  assert.match(first, /s1 · complete/);

  const second = cards[1].textContent;
  assert.match(second, /Wave 2/);
  assert.match(second, /projected/);
  assert.doesNotMatch(second, /journal/);     // nothing dispatched -> no journal id
});

test("wavesSection styles a recorded wave differently from a projected one", () => {
  const run = {
    slices: [{ id: "s1", label: "runnable-pending" }],
    waves: [
      { index: 1, slice_ids: ["s1"], status: "dispatched" },
      { index: 2, slice_ids: [], status: "projected" },
    ],
  };
  const cards = mod.wavesSection(run).children.filter((n) => /\bwave\b/.test(n.className));
  const statusPill = (card) => card.children[0].children[1];   // [0]=title span, [1]=status pill
  assert.match(statusPill(cards[0]).className, /w-dispatched/);
  assert.match(statusPill(cards[1]).className, /w-projected/);
});

test("wavesSection says so plainly when there is nothing recorded and nothing runnable", () => {
  assert.match(mod.wavesSection({ waves: [] }).textContent, /no waves recorded/);
  assert.match(mod.wavesSection({}).textContent, /no waves recorded/);
});

test("wavesSection labels a wave member the slice list does not carry as unknown", () => {
  // A wave recorded for a slice that has since vanished from dag.json must render
  // as unknown rather than crash or claim a status.
  const sec = mod.wavesSection({
    slices: [], waves: [{ index: 1, slice_ids: ["ghost"], status: "collected" }],
  });
  assert.match(sec.textContent, /ghost · unknown/);
});

// ---- 10. sidecar outcome cards (v2) ----
test("sidecarLines renders the fixed field allowlist in order", () => {
  const lines = mod.sidecarLines(sidecar());
  assert.equal(lines.length, 6);
  assert.match(lines[0], /^branch spec-loop\/run-1\/s1$/);
  assert.match(lines[1], /risk tier 2 · review tier 3/);
  assert.match(lines[2], /critique ENDORSE_WITH_CONCERNS · concerns 2 · tasks 4/);
  assert.match(lines[3], /review confirmed 1 · refuted 2 · evidence-failed 0 · fix rounds 1 · residual 1/);
  assert.match(lines[4], /tests full → pass · quality PASS/);
  assert.match(lines[5], /agents 12/);
});

test("sidecarLines em-dashes every absent nested block instead of showing undefined", () => {
  const bare = mod.sidecarLines({ status: "FAILED" });
  const joined = bare.join("\n");
  assert.doesNotMatch(joined, /undefined|null|NaN/);
  assert.match(joined, /branch —/);
  assert.match(joined, /critique — · concerns —/);
  assert.match(joined, /review confirmed — · refuted —/);
  assert.match(joined, /tests — → — · quality —/);
});

test("outcomesSection renders a card per slice with a sidecar, and a note when none has one", () => {
  assert.match(mod.outcomesSection({ slices: [] }).textContent,
               /no slice has reported an outcome/);
  assert.match(mod.outcomesSection({ slices: [{ id: "s1" }] }).textContent,
               /no slice has reported an outcome/);
  const sec = mod.outcomesSection({
    slices: [
      { id: "s1", sidecar: sidecar() },
      { id: "s2" },                                        // no outcome yet -> skipped
      { id: "s3", sidecar: sidecar({ status: "FAILED", wave: 2 }) },
    ],
  });
  const cards = sec.children.filter((n) => /\boutcome\b/.test(n.className));
  assert.equal(cards.length, 2);
  assert.match(cards[0].textContent, /s1/);
  assert.match(cards[0].textContent, /DONE/);
  assert.match(cards[1].textContent, /FAILED/);
  assert.match(cards[1].textContent, /wave: 2/);
  // The status pill carries the allowlisted outcome class.
  assert.match(cards[1].children[0].children[1].className, /o-failed/);
});

// ---- 11. shared constraints (v2) ----
test("constraintsSection lists declared constraints as text, or says none", () => {
  assert.match(mod.constraintsSection({}).textContent, /none declared/);
  assert.match(mod.constraintsSection({ shared_constraints: [] }).textContent, /none declared/);
  const hostile = "<script>alert(1)</script> keep the public API stable";
  const sec = mod.constraintsSection({ shared_constraints: [hostile, "no new deps"] });
  const items = sec.children.find((n) => n.tagName === "UL").children;
  assert.equal(items.length, 2);
  assert.equal(items[0].textContent, hostile);       // verbatim as text
  assert.equal(items[0].children.length, 0);         // never parsed as markup
  assert.equal(items[1].textContent, "no new deps");
});

// ---- 12. provenance pills ----
test("provenancePills always names the generation and adds only the fields present", () => {
  const v1 = mod.provenancePills({}).map((p) => p.textContent);
  assert.deepEqual(v1, ["run-state: v1"]);   // no schema_version -> a v1 run
  const v2 = mod.provenancePills({
    schema_version: 2, mode: "workflow", merge_mode: "single-branch",
    escalations_source: "events", readiness_rule: "dag.py",
  }).map((p) => p.textContent);
  assert.deepEqual(v2, [
    "run-state: v2", "mode: workflow", "merge: single-branch",
    "escalations via: events", "waves via: dag.py",
  ]);
});

test("provenancePills distinguishes the controller's readiness rule from the fallback", () => {
  // "waves via" is the load-bearing one: a wave view derived by the controller's
  // own rule is a stronger claim than one derived by the older local fallback, so
  // the two must never look the same.
  const delegated = mod.provenancePills({ schema_version: 2, readiness_rule: "dag.py" })
    .map((p) => p.textContent);
  const fallback = mod.provenancePills({ schema_version: 2, readiness_rule: "v1" })
    .map((p) => p.textContent);
  assert.ok(delegated.includes("waves via: dag.py"));
  assert.ok(fallback.includes("waves via: v1"));
  assert.notDeepEqual(delegated, fallback);
});

// ---- 13. stage builders ----
test("stageStrip renders all three stages, marking the current and the active one", () => {
  const strip = mod.stageStrip({ run_id: "r1", stage: "execution" }, "iron-council");
  const items = strip.children;
  assert.equal(items.length, 3);
  const current = items.find((i) => /\bcurrent\b/.test(i.className));
  const active = items.find((i) => /\bactive\b/.test(i.className));
  assert.match(current.textContent, /Execution/);       // current = run's derived stage
  assert.match(active.textContent, /Iron Council/);      // active = the selected stage
});

test("councilSection renders findings with an allowlisted verdict pill, or an empty note", () => {
  const empty = mod.councilSection({ council: [] });
  assert.match(empty.textContent, /no council verdicts/);
  const sec = mod.councilSection({ council: [
    { scope: "intake", verdict: "OBJECT", summary: "[skeptic] premise unclear" },
  ] });
  assert.match(sec.textContent, /\[intake\]/);
  assert.match(sec.textContent, /premise unclear/);
  const finding = sec.children[1];        // [0]=h3, [1]=first finding
  const verdictPill = finding.children[1]; // [0]=scope, [1]=verdict pill, [2]=summary
  assert.match(verdictPill.className, /v-object/);
});

test("finalReviewSection shows a not-finished note without a runbook, and chips + readout with one", () => {
  const none = mod.finalReviewSection({});
  assert.match(none.textContent, /no runbook/);
  const sec = mod.finalReviewSection({ runbook: {
    front_matter: { integration_gate: "green", publish: "left-local" },
    executive_readout: "**What we set out to do.** Ship it.",
  } });
  assert.match(sec.textContent, /integration_gate: green/);
  assert.match(sec.textContent, /publish: left-local/);
  assert.match(sec.textContent, /Ship it/);
});

test("executionSection composes waves, slices, rollup, outcomes, constraints, decisions", () => {
  const run = {
    schema_version: 2,
    slices: [{
      id: "s1", goal: "g", risk_tier: 2, depth: 0, parent: null, deps: [],
      label: "complete", has_report: true, sidecar: sidecar(),
    }],
    waves: [{ index: 1, slice_ids: ["s1"], workflow_run_id: "wf_1", status: "collected" }],
    counts: { complete: 1 },
    shared_constraints: ["do not change the CLI surface"],
    decisions_tail: ["[s1] did a thing"],
  };
  const t = mod.executionSection(run).textContent;
  assert.match(t, /waves/);
  assert.match(t, /slices/);
  assert.match(t, /status rollup/);
  assert.match(t, /slice outcomes/);
  assert.match(t, /shared constraints/);
  assert.match(t, /do not change the CLI surface/);
  assert.match(t, /recent decisions/);
  assert.match(t, /did a thing/);
});

test("executionSection renders a v1 run (no sidecars, no constraints) without inventing state", () => {
  // A pre-v2 run dir in a mixed repo: projected waves only, no sidecar outcomes,
  // no shared constraints. Every absent v2 field must read as honestly absent.
  const run = {
    schema_version: 1,
    slices: [{
      id: "s1", goal: "g", risk_tier: 2, depth: 0, parent: null, deps: [],
      label: "runnable-pending", has_report: false,
    }],
    waves: [{ index: 1, slice_ids: ["s1"], workflow_run_id: null, status: "projected" }],
    counts: { "runnable-pending": 1 },
  };
  const t = mod.executionSection(run).textContent;
  assert.match(t, /Wave 1/);
  assert.match(t, /projected/);
  assert.match(t, /no slice has reported an outcome/);
  assert.match(t, /none declared/);
  assert.doesNotMatch(t, /undefined|NaN/);
});

// ---- 14. escalations panel ----
test("escalationsSection lists all with status, shows triggers, falls back, handles empty", () => {
  const sec = mod.escalationsSection({ escalations: [
    { id: "intake:council-objection", token: "intake", title: "scope",
      trigger: "council-objection", status: "ANSWERED" },
    { id: "s2:ambiguity", token: "s2", title: "ambiguous",
      trigger: "ambiguity", status: "OPEN" },
  ] });
  assert.match(sec.textContent, /\[intake\]/);
  assert.match(sec.textContent, /ANSWERED/);
  assert.match(sec.textContent, /\[s2\]/);
  assert.match(sec.textContent, /OPEN/);
  assert.match(sec.textContent, /trigger: ambiguity/);
  // back-compat: only open_escalations present -> each treated as OPEN
  const fb = mod.escalationsSection({ open_escalations: [{ token: "s9", title: "x" }] });
  assert.match(fb.textContent, /\[s9\]/);
  assert.match(fb.textContent, /OPEN/);
  assert.doesNotMatch(fb.textContent, /trigger/);   // prose carries no trigger
  // truly empty
  assert.match(mod.escalationsSection({ escalations: [] }).textContent, /none/);
});

// ---- 15. run-metrics panel (run_metrics.py summary; nulls render as "—") ----
test("fmtMetric renders nulls as em dash, ratios to 2dp, durations humanized", () => {
  assert.equal(mod.fmtMetric("autonomy_ratio", null), "—");
  assert.equal(mod.fmtMetric("autonomy_ratio", undefined), "—");
  assert.equal(mod.fmtMetric("autonomy_ratio", 0.6667), "0.67");
  assert.equal(mod.fmtMetric("escalations", 0), "0");         // 0 is real, not "—"
  assert.equal(mod.fmtMetric("integration_gate", "PASS"), "PASS");
  // Every second-valued key ends in _s, so all three humanize the same way.
  assert.equal(mod.fmtMetric("wall_clock_s", 5400), "1h30m");
  assert.equal(mod.fmtMetric("engine_active_s", 150), "2m30s");
  assert.equal(mod.fmtMetric("human_wait_s", 42), "42s");
});

test("fmtDuration covers seconds, minutes, and hours", () => {
  assert.equal(mod.fmtDuration(42), "42s");
  assert.equal(mod.fmtDuration(150), "2m30s");
  assert.equal(mod.fmtDuration(16425), "4h33m");
  assert.equal(mod.fmtDuration(-5), "0s");                    // clamped, never negative
});

test("metricsSection renders one pill per allowlisted field with a provenance chip", () => {
  // The payload here is exactly run_metrics.summary_row()'s v2 key set.
  const sec = mod.metricsSection({
    metrics: {
      run_id: "r1", run_schema: 2, started_at: "2026-07-30T10:00:00Z",
      escalations: 2, autonomy_ratio: 0.6, council_object_rate: 0.0909,
      quality_gate_first_pass_rate: 0.75, refuted_rate: 0.4,
      evidence_failed_drop_rate: 0.1, split_rate: 0, integration_gate: "PASS",
      wall_clock_s: 16425, engine_active_s: 9000, human_wait_s: 0,
      tokens_total: null,
    },
    metrics_source: "file",
  });
  const text = sec.textContent;
  assert.match(text, /run metrics/);
  assert.match(text, /committed/);            // metrics_source: "file" chip
  assert.match(text, /autonomy: 0\.60/);
  assert.match(text, /refuted: 0\.40/);
  assert.match(text, /gate: PASS/);
  assert.match(text, /wall clock: 4h33m/);
  assert.match(text, /engine: 2h30m/);
  assert.match(text, /human wait: 0s/);       // a real zero, not an em dash
  assert.match(text, /tokens: —/);            // null renders as em dash
  assert.doesNotMatch(text, /NaN|undefined|null/);
  const row = sec.children.find((n) => /pill-row/.test(n.className));
  assert.equal(row.children.length, 12);      // exactly the fixed field allowlist
  // run_id / started_at are in the summary but NOT in the allowlist, so they
  // must not leak into the panel.
  assert.doesNotMatch(text, /2026-07-30/);
});

test("metricsSection tolerates absent metrics and hostile payload keys never render", () => {
  const none = mod.metricsSection({});
  assert.match(none.textContent, /no metrics available/);
  // Extra/hostile keys in the payload are ignored — only the fixed allowlist
  // renders (payload keys are never iterated), and values are textContent-only.
  const hostile = mod.metricsSection({
    metrics: { "<img src=x>": "x", __proto__: { evil: 1 }, escalations: 1 },
    metrics_source: "live",
  });
  assert.doesNotMatch(hostile.textContent, /img src/);
  assert.match(hostile.textContent, /live/);
  const row = hostile.children.find((n) => /pill-row/.test(n.className));
  assert.equal(row.children.length, 12);
  for (const pillNode of row.children) assert.equal(pillNode.children.length, 0);
});

test("tokensBasisLabel names each channel and never implies attribution it lacks", () => {
  assert.equal(mod.tokensBasisLabel("events-jsonl"), "tokens: per-dispatch");
  // The load-bearing one: a wave aggregate is a real total but is NOT splittable
  // by model/role/agent, so the label must say so rather than let a reader assume
  // the number is attributable.
  assert.match(mod.tokensBasisLabel("wave-collected-events"), /not attributable/);
  assert.match(mod.tokensBasisLabel("events-jsonl+wave-collected-events"), /mixed/);
  // An unknown basis surfaces verbatim rather than being silently dropped.
  assert.equal(mod.tokensBasisLabel("something-new"), "tokens basis: something-new");
  assert.equal(mod.tokensBasisLabel("__proto__"), "tokens basis: __proto__");
});

test("metricsSection shows the tokens basis only alongside a real token total", () => {
  const attributed = mod.metricsSection({
    metrics: { tokens_total: 420000, tokens_basis: "events-jsonl" },
    metrics_source: "live",
  });
  assert.match(attributed.textContent, /tokens: 420000/);
  assert.match(attributed.textContent, /tokens: per-dispatch/);

  const waveBasis = mod.metricsSection({
    metrics: { tokens_total: 420000, tokens_basis: "wave-collected-events" },
    metrics_source: "live",
  });
  assert.match(waveBasis.textContent, /not attributable/);

  // A basis for an absent total is noise — the pill already reads "—".
  const noTotal = mod.metricsSection({
    metrics: { tokens_total: null, tokens_basis: "events-jsonl" },
    metrics_source: "live",
  });
  assert.match(noTotal.textContent, /tokens: —/);
  assert.doesNotMatch(noTotal.textContent, /per-dispatch/);
});

test("metricsSection warns when the event log was truncated", () => {
  // events.jsonl is unbounded, so counts computed from part of it UNDERSTATE.
  // A silently low number reads as fact, so the caveat has to be visible.
  const truncated = mod.metricsSection({
    metrics: { escalations: 3 }, metrics_source: "live", metrics_truncated: true,
  });
  assert.match(truncated.textContent, /event log truncated/);
  assert.match(truncated.textContent, /understate/);
  // ...and stays absent when the whole log was read.
  const whole = mod.metricsSection({
    metrics: { escalations: 3 }, metrics_source: "live",
  });
  assert.doesNotMatch(whole.textContent, /truncated/);
});

test("metricsSection distinguishes 'no metrics' from a metrics module that did not answer", () => {
  // metrics_source "unavailable" means run_metrics is deployed but its API did not
  // line up — a different fact from having no metrics module at all, and the panel
  // must say which.
  const skewed = mod.metricsSection({ metrics: null, metrics_source: "unavailable" });
  assert.match(skewed.textContent, /metrics unavailable/);
  assert.match(skewed.textContent, /did not answer/);
});

test("overviewMetricPills yields 3 headline pills, or none when metrics absent", () => {
  assert.deepEqual(mod.overviewMetricPills({}), []);
  const pills = mod.overviewMetricPills({
    metrics: { escalations: 1, autonomy_ratio: 0.5, wall_clock_s: 60 },
  });
  assert.equal(pills.length, 3);
  assert.match(pills.map((p) => p.textContent).join("|"), /esc: 1\|autonomy: 0\.50\|wall: 1m00s/);
});

test("overviewCard carries the headline metric pills when metrics are present", () => {
  const card = mod.overviewCard({
    run_id: "r1", base_ref: "alpha", base_sha: "abc", counts: {},
    metrics: { escalations: 2, autonomy_ratio: 0.6, wall_clock_s: null },
  });
  assert.match(card.textContent, /esc: 2/);
  assert.match(card.textContent, /wall: —/);
});
