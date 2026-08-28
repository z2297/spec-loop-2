#!/usr/bin/env python3
"""Read-only HTTP server + data layer for the spec-loop-2 dashboard.

Serves a strictly READ-ONLY view of spec-loop runs from their durable artifacts
under ``docs/spec-loop/<run-id>/``, per ``references/run-state-v2.md`` — the
single home of the on-disk contract. Standard library only: zero third-party
dependencies, no node/npm/build tooling.

Two clean layers:

  (A) ``scan_runs(docs_root)`` — a PURE, importable function that discovers
      runs, parses each ``dag.json``, and derives waves + honest per-slice
      labels. It tolerates a half-written ``dag.json`` by emitting that run as
      ``unreadable`` without dropping siblings or inventing state.

  (B) A read-only ``http.server`` layer with hard security guardrails:
      GET/HEAD only (405 otherwise); binds 127.0.0.1 only; a Host-header
      allowlist (anti-DNS-rebinding); path-traversal-safe run resolution that
      enumerates discovered run dirs and matches by exact basename; every file
      read canonicalized via ``os.path.realpath`` and asserted to stay under a
      bounded root; bounded counts and bytes; ETag/304. It mutates nothing,
      shells out to nothing, and writes no files.

TWO GENERATIONS, ONE PAYLOAD. A run whose ``dag.json`` declares
``schema_version: 2`` is read with the v2 rules; a run whose ``dag.json`` has no
``schema_version`` is read with the v1 rules. Both render into the SAME payload
shape (every run carries ``schema_version``), so a repo holding runs from both
generations displays them side by side.

What v2 changes, and why each change is a truth upgrade rather than a rewrite:

  * Waves are READ, not guessed. ``dag.json`` records the waves that were
    actually dispatched (``waves[]``, with ``dispatched``/``collected`` status
    and the workflow journal pointer). The server reports those verbatim and
    only ever DERIVES waves for slices that have not been dispatched yet —
    emitted with status ``projected``. v1 had to re-derive the entire wave
    plan, which meant its display could disagree with what the controller
    actually did; reading the record first removes that hazard.
  * Per-slice truth comes from the sidecar ``slice-<id>-status.json``
    (schema_version 2, status DONE|SPLIT|ESCALATED|FAILED), which is
    authoritative over any prose about the slice.
  * OPEN escalations come from ``events.jsonl`` (an ``escalation-opened`` with
    no later ``escalation-answered`` for the same id), with the embedded
    EscalationRecords in the sidecars supplying titles and triggers, and a
    fallback to parsing ``escalations.md`` markers when neither exists.
  * Iron Council verdicts come from ``council-verdict`` events, falling back to
    the v1 prose scrape of ``decisions-log.md`` when ``events.jsonl`` is absent
    (v2 pins no machine grammar on the prose files).

The v1 doctrine is carried over verbatim: labels are HONEST (this server reads
cold artifacts, so it never claims a slice is "running now"), a half-written
``dag.json`` degrades to ``unreadable``, and the HTTP layer stays hardened.

Usage:
    python3 scripts/dashboard_server.py [--port 8787] [--root .]

    # then open the printed http://127.0.0.1:<port>/ URL.
"""

import argparse
import glob
import hashlib
import json
import os
import sys
import urllib.parse
from collections import namedtuple
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Sibling module (same scripts/ dir) providing the run-metrics pure core.
# Tolerated as absent so an older deployment (e.g. a stale Docker image built
# before run_metrics.py shipped) still serves runs — with metrics honestly
# reported as null rather than crashing the whole dashboard.
try:
    import run_metrics
except ImportError:  # pragma: no cover - packaging drift, not a logic path
    run_metrics = None

# Sibling module owning the ONE implementation of wave readiness. run-state-v2.md
# is explicit that nothing re-derives it, and dag.py exposes `next_wave` /
# `project_waves` as pure, side-effect-free reads for exactly this consumer — so a
# v2 run's labels and waves come from the same rule the controller schedules with,
# not a copy that can drift from it. Tolerated as absent (like run_metrics) so a
# stale image still serves, falling back to the v1 rule and saying so in the
# payload's `readiness_rule`.
try:
    import dag
except ImportError:  # pragma: no cover - packaging drift, not a logic path
    dag = None

# A response value object: groups the four output fields so handler helpers
# pass one argument instead of four (etag defaults to None).
Response = namedtuple("Response", "status body content_type etag")
Response.__new__.__defaults__ = (None,)

# Network settings value object: groups the two decoupled network knobs so
# build_server takes one argument instead of two (mirrors Response). ``bind_host``
# is the socket bind address ONLY (0.0.0.0 is intended for inside a container);
# ``advertise_port`` is the published port a browser targets and is the SOLE
# driver of the Host-header allowlist. Binding 0.0.0.0 never widens the allowlist.
NetworkConfig = namedtuple("NetworkConfig", "bind_host advertise_port")
NetworkConfig.__new__.__defaults__ = ("127.0.0.1", None)

# Everything a label/wave derivation needs about a run, gathered once per scan so
# the per-slice helpers take one argument instead of six. ``generation`` selects
# the v1 or v2 rules; ``sidecars`` is empty for a v1 run (v1 had no sidecars).
RunContext = namedtuple(
    "RunContext", "generation statuses open_tokens answered_tokens sidecars")


def _text(status, message):
    return Response(status, message, "text/plain")

# --- bounds (real guardrails, not aspirational) ---
MAX_RUNS = 500              # cap runs scanned per request
MAX_FILE_BYTES = 1_000_000  # cap any single artifact read into memory
MAX_EVENTS = 20_000         # cap parsed events.jsonl lines per run
MAX_WAVES = 200             # cap recorded waves read from dag.json
# Spin guard on the wave projection, mirroring dag.py's own limit: a graph that
# cannot drain in this many waves is pathological and a viewer must not loop on it.
MAX_PROJECTED_WAVES = 100
MAX_CONSTRAINTS = 20        # cap shared_constraints carried in the payload
DECISIONS_TAIL_LINES = 12   # cap decisions-log tail length
REQUEST_EXCERPT_CHARS = 240 # cap the one-line request excerpt
COUNCIL_MAX = 50            # cap parsed Iron Council verdict lines per run
COUNCIL_SUMMARY_CHARS = 240 # cap each council summary line

DEFAULT_PORT = 8787
DATA_SUBPATH = ("docs", "spec-loop")
ASSETS_SUBPATH = "dashboard_assets"  # relative to this script's dir

# The run-state generation this server reads natively. A dag.json without a
# schema_version is a v1 run and takes the v1 code paths throughout.
SCHEMA_V2 = 2

# The sidecar's four terminal outcomes (run-state-v2.md). Anything else in the
# file's ``status`` field is reported as "unknown" rather than passed through.
SIDECAR_STATUSES = ("DONE", "SPLIT", "ESCALATED", "FAILED")

# Recorded wave statuses (run-state-v2.md). "projected" is this server's own
# marker for a wave it DERIVED because the work has not been dispatched yet, and
# can therefore never appear in dag.json.
RECORDED_WAVE_STATUSES = ("dispatched", "collected")
PROJECTED = "projected"

# The EscalationRecord triggers (run-state-v2.md). Used both to validate a
# record's own ``trigger`` field and to read the trigger an escalation id encodes.
ESCALATION_TRIGGERS = ("ambiguity", "material-assumption", "review-block",
                       "council-objection", "quality-gate-block", "refactor-scope",
                       "budget-exhausted", "internal-error")

# Labels meaning "the sidecar recorded a terminal outcome that the controller has
# not yet written back into dag.json, and which WILL clear on its own" — a DONE
# slice awaiting its serial merge, a SPLIT awaiting child ingestion. Neither is
# runnable, but both are treated as landed by the wave projection so dependents
# can chain off them. `failed` is deliberately NOT in this list: it does not clear
# without intervention (see _projection_view).
SETTLING_LABELS = ("merge-pending", "split-pending")


# ==========================================================================
# Shared path-containment helper (used for BOTH data reads and asset reads)
# ==========================================================================

def resolve_within(root, relpath):
    """Resolve ``relpath`` under ``root``, returning a safe absolute path or
    ``None`` if it escapes the root.

    Rejects null bytes and absolute paths, then canonicalizes via
    ``os.path.realpath`` (collapsing ``..`` and following symlinks) and asserts
    the result stays under ``realpath(root)`` using ``os.path.commonpath`` — so
    ``..`` traversal cannot escape, and a sibling like
    ``<root>-evil`` cannot pass a naive prefix check, and a symlink escaping the
    root is rejected. ``root`` is realpath'd too (macOS ``/tmp`` -> ``/private/tmp``).
    """
    relpath = str(relpath)
    if "\x00" in relpath or os.path.isabs(relpath):
        return None
    real_root = os.path.realpath(str(root))
    candidate = os.path.realpath(os.path.join(real_root, relpath))
    try:
        if os.path.commonpath([real_root, candidate]) != real_root:
            return None
    except ValueError:
        # Different drives / mixed absolute-relative -> not contained.
        return None
    return candidate


def _read_text_capped(path):
    """Read up to MAX_FILE_BYTES of text, or return '' if absent/unreadable."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(MAX_FILE_BYTES)
    except (OSError, ValueError):
        return ""


def _read_tail_capped(path):
    """Read up to the LAST MAX_FILE_BYTES of a file, returning
    ``(text, truncated)``.

    Used for the append-only ``events.jsonl``: for a growing log the TAIL is the
    load-bearing part (the latest transitions), so capping from the head — as a
    plain capped read would — is the wrong end to keep. ``truncated`` tells the
    caller the first line may be a partial record and must be dropped."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            truncated = size > MAX_FILE_BYTES
            if truncated:
                fh.seek(size - MAX_FILE_BYTES)
            raw = fh.read(MAX_FILE_BYTES)
    except (OSError, ValueError):
        return "", False
    return raw.decode("utf-8", errors="replace"), truncated


# ==========================================================================
# Layer (A): pure data layer
# ==========================================================================

def scan_runs(docs_root):
    """Discover and parse every run under ``docs_root`` (a ``docs/spec-loop``
    directory). Returns a list of run dicts. A run with a half-written
    ``dag.json`` is emitted as ``{"run_id", "status": "unreadable"}`` rather
    than dropped. Pure: reads files, never writes."""
    docs_root = Path(docs_root)
    runs = []
    pattern = str(docs_root / "*" / "dag.json")
    for dag_path in sorted(glob.glob(pattern))[:MAX_RUNS]:
        run_dir = Path(dag_path).parent
        runs.append(_scan_one_run(run_dir))
    return runs


def scan_all_roots(roots):
    """Aggregate ``scan_runs`` across one or more roots.

    ``roots`` is either a bare list of repo-root paths, or an ordered list of
    ``(root_key, data_root)`` pairs (as produced by ``_resolve_roots``). With a
    single root the result is transparent — bare ``run_id``, no ``root`` field.
    With multiple roots each run's ``run_id`` is namespaced
    ``<root_key>:<run_id>`` and carries its ``root`` key, so identically-named
    runs across repos never collide. Pure: never writes."""
    resolved = _as_root_pairs(roots)
    aggregated = []
    for root_key, data_root in resolved:
        for run in scan_runs(data_root):
            aggregated.append(_namespace_run(run, root_key))
    return aggregated[:MAX_RUNS]


def _as_root_pairs(roots):
    """Accept either ``[(key, data_root), ...]`` or a bare list of repo roots and
    return the ``(root_key, data_root)`` form."""
    items = list(roots)
    if items and isinstance(items[0], tuple):
        return items
    return _resolve_roots(items)


def _namespace_run(run, root_key):
    """Prefix a run's id with its root key (when namespaced) and attach the
    ``root`` field. An empty key means single-root/transparent -> unchanged."""
    if not root_key:
        return run
    return {**run, "run_id": f"{root_key}:{run['run_id']}", "root": root_key}


def _scan_one_run(run_dir):
    run_id = run_dir.name
    try:
        # `dag_doc`, not `dag` — the module-level `dag` is the imported dag.py.
        dag_doc = json.loads((run_dir / "dag.json").read_text())
        slices = dag_doc["slices"]
        if not isinstance(slices, list):
            raise ValueError("slices is not a list")
    except (OSError, ValueError, KeyError, TypeError):
        # Mirrors the command's "state momentarily unreadable" degrade.
        return {"run_id": run_id, "status": "unreadable"}

    generation = _generation(dag_doc)
    escalations, esc_source = _read_escalations(run_dir, generation)
    ctx = _build_context(generation, slices, escalations, run_dir)
    enriched = _label_slices(slices, ctx, run_dir)
    recorded = _recorded_waves(dag_doc) if generation == SCHEMA_V2 else []
    runbook = _parse_runbook(run_dir)
    metrics_summary, metrics_doc, metrics_source = _run_metrics(run_dir)
    return {
        "run_id": run_id,
        "schema_version": generation,
        "base_ref": dag_doc.get("base_ref"),
        "base_sha": dag_doc.get("base_sha"),
        "mode": _enum_or_none(dag_doc.get("mode"), ("workflow", "inline")),
        "merge_mode": _enum_or_none(dag_doc.get("merge_mode"),
                                    ("single-branch", "per-slice-pr")),
        "shared_constraints": _shared_constraints(dag_doc),
        "stage": _derive_stage(slices, run_dir,
                               started=bool(recorded) or bool(ctx.sidecars)),
        "slices": enriched,
        "waves": _compose_waves(enriched, recorded, ctx),
        "readiness_rule": _readiness_rule(ctx.generation),
        "open_escalations": [{"token": e["token"], "title": e["title"]}
                             for e in escalations if e["status"] == "OPEN"],
        "escalations": escalations,
        "escalations_source": esc_source,
        "council": _read_council(run_dir, generation),
        "request_excerpt": _request_excerpt(run_dir),
        "decisions_tail": _decisions_tail(run_dir),
        "counts": _count_labels(enriched),
        "artifacts": _list_artifacts(run_dir),
        "runbook": runbook,
        "has_runbook": runbook is not None,
        "metrics": metrics_summary,
        "metrics_source": metrics_source,
        "metrics_truncated": _metrics_truncated(metrics_doc),
    }


def _generation(dag):
    """The run-state generation to read this dag.json with: 2 when it declares
    ``schema_version: 2``, else 1 (a v1 run, or anything unrecognized — read
    with the older, more forgiving rules rather than refused)."""
    return SCHEMA_V2 if dag.get("schema_version") == SCHEMA_V2 else 1


def _enum_or_none(value, allowed):
    """Pass ``value`` through only when it is one of ``allowed``; else None. Keeps
    an unexpected dag.json field out of the payload instead of forwarding it."""
    return value if value in allowed else None


def _shared_constraints(dag):
    """The run-wide must-not-regress constraints (v2), as a bounded list of
    strings. A missing or wrongly-typed field yields []."""
    raw = dag.get("shared_constraints")
    if not isinstance(raw, list):
        return []
    return [str(c) for c in raw[:MAX_CONSTRAINTS]]


def _build_context(generation, slices, escalations, run_dir):
    """Gather the whole-run facts the per-slice derivations need, once."""
    sidecars = _read_sidecars(run_dir, slices) if generation == SCHEMA_V2 else {}
    return RunContext(
        generation=generation,
        statuses={s.get("id"): s.get("status") for s in slices},
        open_tokens={e["token"] for e in escalations
                     if e["status"] == "OPEN" and e["token"] != "intake"},
        answered_tokens={e["token"] for e in escalations
                         if e["status"] == "ANSWERED"},
        sidecars=sidecars,
    )


# --- run metrics (run_metrics.py pure core; read-only) -----------------------

def _run_metrics(run_dir):
    """The run's metrics as ``(summary, full_document, source)``.

    The document is the committed ``metrics.json`` when it is valid
    (``source: "file"``), else a live artifact-only recompute via the run_metrics
    pure core (``source: "live"`` — reads files, never git or transcripts,
    keeping this server's shells-out-to-nothing guarantee). The summary is the
    fixed small dict carried on every run in the collection payload; the full
    document is served only on the run-detail endpoint.

    Three honest outcomes, all distinguishable by the caller:
      * ``(None, None, None)``          run_metrics is not deployed at all;
      * ``(None, None, "unavailable")``  it is deployed but its API does not line
                                        up (a version skew between this server
                                        and the metrics module) — reported,
                                        never crashed on;
      * ``(summary, doc, "file"|"live")`` real metrics, and where they came from.

    Every call into run_metrics sits inside the one guard, summary_row included:
    a module that answers ``compute_metrics`` but not ``summary_row`` would
    otherwise take down the whole scan, not just its own panel."""
    if run_metrics is None:
        return None, None, None
    try:
        doc, source = _metrics_document(run_dir)
        return run_metrics.summary_row(doc), doc, source
    except (AttributeError, TypeError, ValueError, KeyError, OSError):
        return None, None, "unavailable"


def _metrics_truncated(doc):
    """True when the metrics document reports that the run's ``events.jsonl``
    exceeded run_metrics' read cap.

    ``events.jsonl`` is append-only and unbounded, so a long run's counts can be
    computed from only part of it — which UNDERSTATES them. That is worth saying
    out loud: a silently low number reads as fact, and the whole point of the
    null-honest contract is that the viewer can tell a real value from a soft
    one."""
    if not isinstance(doc, dict):
        return False
    sources = doc.get("sources")
    return bool(isinstance(sources, dict) and sources.get("events_truncated"))


def _metrics_document(run_dir):
    """``(document, source)``: the committed file when valid, else a live
    recompute. Raises whatever run_metrics raises — ``_run_metrics`` owns the
    guard.

    The live recompute goes through ``metrics_for_run_dir``, NOT
    ``load_run_artifacts`` + ``compute_metrics``. That pair reads only the v2
    channels by design, so pointing it at a v1 run dir yields an all-null row —
    and this server aggregates across every repo the user has launched from, so it
    WILL meet v1 run dirs. Reporting "unavailable" for a v1 run that really does
    have escalations would be a false claim about real data, not a null-honest
    one. ``metrics_for_run_dir`` detects the generation per run dir and routes v1
    through the walled-off legacy prose parsers, returning the same document shape
    either way. It does its own artifact loading and still shells out to nothing."""
    committed = _load_metrics_file(run_dir / "metrics.json")
    if committed is not None:
        return committed, "file"
    return _live_metrics(run_dir), "live"


def _live_metrics(run_dir):
    """A live recompute, generation-routed when the deployed run_metrics can do
    it. An older module without ``metrics_for_run_dir`` degrades to the v2-only
    pair rather than losing metrics entirely — correct for v2 runs, null for v1
    ones, which is the best a module that cannot read v1 can honestly offer."""
    router = getattr(run_metrics, "metrics_for_run_dir", None)
    if router is not None:
        return router(run_dir)
    return run_metrics.compute_metrics(run_metrics.load_run_artifacts(run_dir))


def _load_metrics_file(path):
    """Parse a committed metrics.json, or None when absent/malformed/wrong
    schema (malformed falls back to a live recompute, never an error page)."""
    try:
        doc = json.loads(_read_text_capped(path) or "null")
    except ValueError:
        return None
    if isinstance(doc, dict) and doc.get("schema_version") == run_metrics.SCHEMA_VERSION:
        return doc
    return None


# --- per-slice sidecars (slice-<id>-status.json, schema_version 2) ------------

def _read_sidecars(run_dir, slices):
    """Map ``slice id -> allowlisted sidecar view`` for every slice that has a
    readable, schema-2 ``slice-<id>-status.json``. Slices without one are simply
    absent from the map."""
    out = {}
    for s in slices:
        sid = s.get("id")
        if sid is None:
            continue
        doc = _load_sidecar(run_dir / f"slice-{sid}-status.json")
        if doc is not None:
            out[sid] = _sidecar_view(doc)
    return out


def _load_sidecar(path):
    """Parse a sidecar, or None when absent / malformed / not schema 2. A
    half-written sidecar is indistinguishable from an absent one here, which is
    the honest degrade: the slice simply has no recorded outcome yet."""
    if not path.is_file():
        return None
    try:
        doc = json.loads(_read_text_capped(path) or "null")
    except ValueError:
        return None
    if not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA_V2:
        return None
    return doc


def _sidecar_view(doc):
    """The FIXED subset of a sidecar carried in the payload.

    An allowlist, not a passthrough: the payload stays bounded and an unexpected
    field in a sidecar can never reach the client. ``status`` is narrowed to the
    four contract values so a garbage status renders as "unknown"."""
    return {
        "status": _enum_or_none(doc.get("status"), SIDECAR_STATUSES) or "unknown",
        "branch": doc.get("branch"),
        "risk_tier": doc.get("risk_tier"),
        "review_tier": doc.get("review_tier"),
        "critique": _pick(doc.get("critique"), ("verdict", "concerns")),
        "tasks_completed": doc.get("tasks_completed"),
        "review": _review_view(doc.get("review")),
        "tests": _pick(doc.get("tests"), ("result", "scope")),
        "quality": _pick(doc.get("quality"), ("status", "detail")),
        "agents_used": doc.get("agents_used"),
        "wave": doc.get("wave"),
        "started_at": doc.get("started_at"),
        "finished_at": doc.get("finished_at"),
    }


def _pick(obj, keys):
    """``{k: obj[k]}`` for the allowlisted keys, or None when obj is not a dict."""
    if not isinstance(obj, dict):
        return None
    return {k: obj.get(k) for k in keys}


def _review_view(review):
    """The review block plus a ``residual_count`` (the residual findings are a
    list of prose strings; the dashboard shows how many, not their text)."""
    picked = _pick(review, ("confirmed", "refuted", "evidence_failed",
                            "fix_rounds"))
    if picked is None:
        return None
    residual = review.get("residual")
    picked["residual_count"] = len(residual) if isinstance(residual, list) else None
    return picked


# --- honest per-slice labels --------------------------------------------------

def _readiness_rule(generation):
    """Which readiness rule this run's labels and waves were derived with —
    payload provenance, in the same spirit as ``escalations_source``.

    Three honest values:
      * ``"dag.py"``       the controller's own ``next_wave`` decided it;
      * ``"v2-fallback"``  a v2 run on a deployment without dag.py — decided by
                           a local mirror of dag.py's rule (recursive split
                           resolution included), so the ANSWER matches even
                           though the code path does not;
      * ``"v1"``           a pre-v2 run dir, decided by v1's simpler rule in
                           which a ``split`` parent never blocks."""
    if generation != SCHEMA_V2:
        return "v1"
    return "dag.py" if dag is not None else "v2-fallback"


def _v2_ready_ids_fallback(slices):
    """dag.py's readiness rule, reimplemented locally for the case where dag.py is
    not deployed next to this server.

    This mirror exists ONLY so a stale image does not silently answer a different
    question: a v2 run must not be shown v1's readiness answer, in which a
    ``split`` parent is satisfied on its own. Here — as in dag.py — a dep on a
    ``split`` parent is satisfied only when ALL of that parent's children are
    satisfied, resolved recursively so a child that itself split resolves through
    its grandchildren; a ``split`` parent with no ingested children can never be
    satisfied; and a dep naming a slice that does not exist is never satisfied.

    The delegated path stays the real one — ``readiness_rule`` reports which
    answered."""
    index = {s.get("id"): s for s in slices
             if isinstance(s.get("id"), str) and s.get("id")}
    children = {}
    for s in slices:
        children.setdefault(s.get("parent"), []).append(s.get("id"))

    def satisfied(sid, resolving):
        item = index.get(sid)
        if item is None or sid in resolving:
            return False  # unknown dep, or a cycle through splits
        status = item.get("status")
        if status == "complete":
            return True
        if status != "split":
            return False
        kids = [k for k in children.get(sid, []) if k is not None]
        if not kids:
            return False  # a split with no ingested children never clears
        return all(satisfied(k, resolving | {sid}) for k in kids)

    ready = set()
    for s in slices:
        sid = s.get("id")
        if not isinstance(sid, str) or not sid or s.get("status") != "pending":
            continue
        deps = s.get("deps")
        deps = [d for d in deps if isinstance(d, str)] if isinstance(deps, list) else []
        if all(satisfied(d, frozenset()) for d in deps):
            ready.add(sid)
    return ready


def _label_slices(slices, ctx, run_dir):
    """Attach the honest label, report presence, and (v2) the sidecar view to
    every slice.

    Two phases, because the dep-based labels must come from the SAME readiness
    rule the controller schedules with rather than a copy of it. First the
    currently-runnable set is resolved once for the whole run; then each slice
    takes the label its own sidecar/escalation state dictates, falling back to
    that set only when nothing else decides it."""
    runnable = _runnable_ids(slices, ctx)
    return [_label_slice(s, ctx, run_dir, runnable) for s in slices]


def _runnable_ids(slices, ctx):
    """The ids of pending slices whose deps are ALL satisfied as things stand.

    v2 delegates to ``dag.next_wave`` — the one implementation of the rule, in
    which a ``split`` dep is satisfied only once all of its children are (not
    merely because the parent is ``split``), and a ``split`` parent with no
    ingested children therefore still blocks. v1 runs keep v1's simpler rule,
    where a ``split`` parent is unconditionally non-blocking, so a pre-v2 run dir
    in a mixed repo keeps rendering exactly as it did.

    Deliberately judged against the RAW dag statuses: a dep that is merely in
    flight, or DONE-awaiting-merge, is not satisfied yet, so its dependents are
    honestly blocked right now. The optimistic view belongs to the wave
    projection (``_projection_view``), which is labelled ``projected``."""
    if ctx.generation == SCHEMA_V2:
        if dag is not None:
            report = dag.next_wave({"slices": list(slices), "waves": []})
            return set(report.get("slice_ids") or [])
        return _v2_ready_ids_fallback(slices)
    return set(_ready_ids(_pending_slices(slices), _completed_ids(slices)))


def _label_slice(s, ctx, run_dir, runnable):
    """Attach the honest derived label, report presence, and (v2) the sidecar
    view to a slice dict."""
    sid = s.get("id")
    return {
        **s,
        "label": _derive_label(s, ctx, runnable),
        "has_report": (run_dir / f"slice-{sid}-report.md").is_file(),
        "sidecar": ctx.sidecars.get(sid),
    }


def _derive_label(s, ctx, runnable):
    if ctx.generation == SCHEMA_V2:
        return _derive_label_v2(s, ctx, runnable)
    return _derive_label_v1(s, ctx, runnable)


def _derive_label_v1(s, ctx, runnable):
    """The six honest v1 labels, in precedence order. Kept as the back-compat
    path so a pre-v2 run dir in a mixed repo still renders exactly as it did."""
    sid, status = s.get("id"), s.get("status")
    if status in ("complete", "split"):
        return status
    if sid in ctx.open_tokens:
        return "awaiting-human"
    if sid in ctx.answered_tokens:
        return "redispatch-pending"
    return _dep_label(sid, runnable)


def _derive_label_v2(s, ctx, runnable):
    """The v2 labels, in precedence order.

    dag.json is the authority on run structure, so a slice it calls terminal is
    terminal. Below that, the sidecar is authoritative on what the slice's last
    wave actually returned — including the two states v1 could not express: a
    slice whose work FAILED, and a slice whose outcome the controller has
    recorded but not yet written back into dag.json (DONE awaiting the serial
    merge, SPLIT awaiting child ingestion). Calling either of those
    "runnable-pending" would be a live claim this server cannot make, so each
    gets its own label. Escalation state then decides between waiting on a human
    and being ready for re-dispatch, and only then do deps decide."""
    sid, status = s.get("id"), s.get("status")
    if status in ("complete", "split"):
        return status
    sidecar_status = (ctx.sidecars.get(sid) or {}).get("status")
    if sidecar_status == "FAILED":
        return "failed"
    if sidecar_status == "DONE":
        return "merge-pending"
    if sidecar_status == "SPLIT":
        return "split-pending"
    if sid in ctx.open_tokens:
        return "awaiting-human"
    if sid in ctx.answered_tokens:
        return "redispatch-pending"
    if sidecar_status == "ESCALATED":
        # It escalated, but no matching record resolves it either way. Surface it
        # as still owing a human rather than quietly calling it runnable.
        return "awaiting-human"
    return _dep_label(sid, runnable)


def _dep_label(sid, runnable):
    return "runnable-pending" if sid in runnable else "blocked-pending"


# --- waves: recorded first, derived only for undispatched work ---------------

def _compose_waves(enriched, recorded, ctx):
    """The wave rows for a run, as ``{index, slice_ids, workflow_run_id, status}``.

    v1 runs have nothing recorded, so every wave is ``projected`` — the v1
    derivation, unchanged, just labelled honestly.

    v2 runs report their recorded ``waves[]`` verbatim (the durable pointer from
    run state to the workflow journals) and then append a PROJECTION of the work
    that has not been dispatched yet, numbered after the last recorded wave.

    Slices still in flight — members of a recorded wave that is ``dispatched``
    and not yet ``collected`` — are excluded from the projection: that wave row
    already accounts for them, and projecting them again would double-count
    in-flight work. Slices in a ``collected`` wave that are still pending DO get
    projected: they came back without completing and genuinely need another
    wave."""
    if ctx.generation != SCHEMA_V2:
        return _projected_waves(_derive_waves(enriched), start_index=0)
    in_flight = {sid for w in recorded if w["status"] == "dispatched"
                 for sid in w["slice_ids"]}
    view = _projection_view(enriched, recorded, in_flight)
    if dag is not None:
        return recorded + [
            {"index": w["index"], "slice_ids": w["slice_ids"],
             "workflow_run_id": None, "status": PROJECTED}
            for w in dag.project_waves(view)
        ]
    start = max((w["index"] for w in recorded), default=0)
    return recorded + _projected_waves(
        _project_waves_fallback(view), start_index=start)


def _project_waves_fallback(view):
    """A local mirror of ``dag.project_waves`` for a deployment without dag.py.

    Same shape as dag.py's: repeatedly take the ready set over a working copy in
    which each projected wave is optimistically completed, stopping when nothing
    more is runnable (whatever is still pending then is deadlocked). Bounded by
    ``MAX_PROJECTED_WAVES`` so a pathological graph can never spin a viewer.
    Returns the id groups; the caller numbers them."""
    working = [dict(s) for s in view["slices"]]
    groups = []
    while len(groups) < MAX_PROJECTED_WAVES:
        ready = _v2_ready_ids_fallback(working)
        if not ready:
            break
        groups.append([s["id"] for s in working if s["id"] in ready])
        for s in working:
            if s["id"] in ready:
                s["status"] = "complete"
    return groups


def _projection_view(enriched, recorded, in_flight):
    """A working dag whose slice statuses encode what the dashboard knows, so
    ``dag.project_waves`` can be applied to it unchanged.

    The projection answers "if the work now underway lands, what runs next", so
    the view marks as ``complete`` everything expected to get there without
    another wave: slices in flight in a dispatched wave, a DONE slice awaiting its
    serial merge, and a SPLIT slice awaiting child ingestion. That both keeps them
    out of the forecast (a dispatched wave row already accounts for them) and lets
    their dependents chain off them.

    A ``failed`` slice is DROPPED from the view rather than marked either way: it
    will not clear on its own, so dag.py sees its dependents referring to an
    unknown id and reports them blocked — which is the honest answer, and keeps
    the failed slice itself out of the forecast too.

    The recorded waves ride along so dag.py's own ``_next_index`` numbers the
    projection after the run's real history."""
    slices = []
    for s in enriched:
        if s.get("label") == "failed":
            continue
        status = s.get("status")
        if s.get("id") in in_flight or s.get("label") in SETTLING_LABELS:
            status = "complete"
        slices.append({"id": s.get("id"), "parent": s.get("parent"),
                       "deps": s.get("deps", []), "status": status})
    return {"slices": slices, "waves": recorded}


def _projected_waves(id_groups, start_index):
    """Wrap derived id groups as wave rows numbered from ``start_index + 1``."""
    return [{"index": start_index + n, "slice_ids": ids,
             "workflow_run_id": None, "status": PROJECTED}
            for n, ids in enumerate(id_groups, start=1)]


def _recorded_waves(dag_doc):
    """The waves dag.json says were actually dispatched, normalized and bounded.

    Tolerant by design: a non-list ``waves`` yields [], a non-dict entry is
    skipped, a missing ``index`` falls back to its 1-based position, and a status
    outside the contract's two values reports as ``unknown`` rather than being
    passed through."""
    raw = dag_doc.get("waves")
    if not isinstance(raw, list):
        return []
    out = []
    for position, wave in enumerate(raw[:MAX_WAVES], start=1):
        if not isinstance(wave, dict):
            continue
        index = wave.get("index")
        ids = wave.get("slice_ids")
        out.append({
            "index": index if isinstance(index, int) and not isinstance(index, bool)
                     else position,
            "slice_ids": [str(i) for i in ids] if isinstance(ids, list) else [],
            "workflow_run_id": wave.get("workflow_run_id"),
            "status": _enum_or_none(wave.get("status"),
                                    RECORDED_WAVE_STATUSES) or "unknown",
        })
    return out


def _derive_waves(slices):
    """Derive waves for a run with nothing recorded: a wave = every pending slice
    whose deps are all satisfied (complete or split). ``split`` slices are
    terminal and never appear in a wave."""
    return _derive_waves_from(_pending_slices(slices), _completed_ids(slices))


def _derive_waves_from(pending, done):
    """Group ``pending`` slices into successive waves, given the ids already
    satisfied. Iterate, assigning each later pending slice to the first wave at
    which its deps are met.

    This mirrors ``dag.py``'s next-wave rule, which is the authority for what the
    controller actually dispatches. For a v2 run it only ever runs over work that
    has NOT been dispatched, so it is a forecast of the remaining plan and never
    contradicts the recorded history."""
    done = set(done)
    remaining = list(pending)
    waves = []
    while remaining:
        ready_ids = _ready_ids(remaining, done)
        if not ready_ids:
            break  # unsatisfiable deps (cycle / missing) — stop, don't loop
        waves.append(ready_ids)
        done |= set(ready_ids)
        remaining = _without(remaining, ready_ids)
    return waves


def _completed_ids(slices):
    """Ids whose status is terminal-satisfied (complete or split)."""
    return {s.get("id") for s in slices
            if s.get("status") in ("complete", "split")}


def _pending_slices(slices):
    return [s for s in slices if s.get("status") == "pending"]


def _ready_ids(remaining, done):
    """Ids of pending slices whose every dep is already satisfied.

    A slice carrying no ``id`` at all (a hand-edited or half-written dag.json) is
    skipped rather than indexed: it can never be scheduled, and reading it as
    ``s["id"]`` would raise from OUTSIDE ``_scan_one_run``'s tolerate-the-parse
    guard, taking down every other run in the same request."""
    return [s.get("id") for s in remaining
            if s.get("id") is not None
            and all(d in done for d in s.get("deps", []))]


def _without(slices, exclude_ids):
    excluded = set(exclude_ids)
    return [s for s in slices if s.get("id") not in excluded]


def _count_labels(enriched):
    counts = {}
    for s in enriched:
        counts[s["label"]] = counts.get(s["label"], 0) + 1
    return counts


# ==========================================================================
# events.jsonl — the machine channel
# ==========================================================================

def _iter_events(run_dir):
    """Yield each decoded event object from ``events.jsonl``, bounded.

    Reads the TAIL of the file (see ``_read_tail_capped``) and drops the first
    line when the read was truncated, since that line may be a partial record.
    A line that is not a JSON object is skipped: a half-written final line is
    the expected state of a live append-only log, not an error."""
    text, truncated = _read_tail_capped(run_dir / "events.jsonl")
    lines = text.splitlines()
    if truncated and lines:
        lines = lines[1:]
    for line in lines[:MAX_EVENTS]:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


def _has_events(run_dir):
    return (run_dir / "events.jsonl").is_file()


def _payload(event):
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


# ==========================================================================
# Escalations
# ==========================================================================

def _read_escalations(run_dir, generation):
    """Every escalation for a run as ``[{id, token, title, trigger, status}]``,
    plus the source it was read from (``"events"`` / ``"sidecars"`` /
    ``"prose"``) so the UI can say where its truth came from.

    v2 layers three sources, strongest last:
      1. the EscalationRecords embedded in the per-slice sidecars — the full
         records, with titles and triggers;
      2. ``events.jsonl`` — an ``escalation-opened`` with no later
         ``escalation-answered`` for the same id is OPEN. Events win over the
         sidecar's recorded status, because a sidecar is a snapshot taken when
         its wave was collected while the answer is written afterwards;
      3. ids seen only in events, carried with whatever title the event offers.

    With neither sidecar records nor an events log, v2 falls back to v1's scrape
    of ``escalations.md`` markers, so an early-stage run still reports honestly.
    v1 runs always take that prose path."""
    if generation != SCHEMA_V2:
        return _escalations_from_prose(run_dir), "prose"
    records = _escalations_from_sidecars(run_dir)
    events_present = _has_events(run_dir)
    if not records and not events_present:
        return _escalations_from_prose(run_dir), "prose"
    if not events_present:
        return list(records.values()), "sidecars"
    return _overlay_event_statuses(records, run_dir), "events"


def _overlay_event_statuses(records, run_dir):
    """Apply the events log's open/answered transitions over the sidecar records,
    appending any id the events know about that no sidecar carried."""
    merged = dict(records)
    for esc_id, status in _escalation_event_statuses(run_dir).items():
        base = merged.get(esc_id) or _bare_escalation(esc_id)
        merged[esc_id] = {**base, "status": status}
    return list(merged.values())


def _escalation_event_statuses(run_dir):
    """``{escalation id: "OPEN"|"ANSWERED"}`` from the events log.

    The log is append-only and ordered, so the LAST transition for an id wins —
    an escalation answered and then reopened ends up OPEN, which is the honest
    reading of the record."""
    statuses = {}
    for event in _iter_events(run_dir):
        etype = event.get("type")
        if etype not in ("escalation-opened", "escalation-answered"):
            continue
        esc_id = _event_escalation_id(event)
        if esc_id is None:
            continue
        statuses[esc_id] = "OPEN" if etype == "escalation-opened" else "ANSWERED"
    return statuses


def _event_escalation_id(event):
    """The escalation id an escalation event refers to.

    v2 pins the EscalationRecord's shape but not how an event wraps it, so this
    accepts the record inline (``payload.id``), nested (``payload.escalation.id``),
    or named (``payload.escalation_id``). Returns None when no id is present —
    an event that names no escalation cannot change any escalation's status."""
    payload = _payload(event)
    nested = payload.get("escalation")
    for candidate in (payload.get("id"),
                      nested.get("id") if isinstance(nested, dict) else None,
                      payload.get("escalation_id")):
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _escalations_from_sidecars(run_dir):
    """The EscalationRecords embedded in every readable schema-2 sidecar, keyed
    by escalation id in file order. Sidecars are found by glob (not by slice id)
    so a record survives even when its slice has vanished from dag.json."""
    found = {}
    for path in sorted(glob.glob(str(run_dir / "slice-*-status.json"))):
        doc = _load_sidecar(Path(path))
        if doc is None:
            continue
        raw = doc.get("escalations")
        if not isinstance(raw, list):
            continue
        for record in raw:
            view = _escalation_record_view(record)
            if view is not None:
                found[view["id"]] = view
    return found


def _escalation_record_view(record):
    """One EscalationRecord narrowed to the fields the dashboard shows, or None
    when it carries no usable id."""
    if not isinstance(record, dict):
        return None
    esc_id = record.get("id")
    if not isinstance(esc_id, str) or not esc_id:
        return None
    status = record.get("status")
    return {
        "id": esc_id,
        "token": _escalation_token(esc_id),
        "title": str(record.get("title") or ""),
        "trigger": _enum_or_none(record.get("trigger"), ESCALATION_TRIGGERS)
                   or _trigger_from_id(esc_id),
        "status": status if status in ("OPEN", "ANSWERED") else "unknown",
    }


def _bare_escalation(esc_id):
    """The placeholder for an escalation known only by id (seen in the events log
    with no sidecar record). Honest about what is missing — an empty title rather
    than a fabricated one — but the id itself encodes the trigger, so that much
    is real and worth showing."""
    return {"id": esc_id, "token": _escalation_token(esc_id),
            "title": "", "trigger": _trigger_from_id(esc_id),
            "status": "unknown"}


def _escalation_token(esc_id):
    """The slice-or-``intake`` token an escalation id belongs to. Ids are
    ``<slice-id>:<trigger>[:<round>]``, so the token is the part before the
    first colon."""
    return esc_id.split(":", 1)[0]


def _trigger_from_id(esc_id):
    """The trigger an escalation id encodes, or None.

    Ids are ``<slice-id>:<trigger>[:<round>]`` by contract, so the second segment
    IS the trigger — accepted only when it is one of the contract's values, so a
    hand-edited or malformed id can never surface a made-up trigger."""
    parts = esc_id.split(":")
    if len(parts) >= 2 and parts[1] in ESCALATION_TRIGGERS:
        return parts[1]
    return None


# --- v1 prose escalations (escalations.md) — the back-compat / early path -----

def _escalations_from_prose(run_dir):
    """Every escalation entry parsed out of escalations.md, in both v1 marker
    forms, as the same view shape the structured sources produce (with no id or
    trigger — the prose carries neither).

    Forms:
      - escalation-gate: ``## [<slice-id>] <title>   (status: OPEN)``
      - iron-council:    ``## [<id-or-intake>] Iron Council objects: … (status: OPEN)``
    The bracket token may be a slice id or the literal ``intake`` (which joins no
    slice row)."""
    return [
        {"id": None, "token": tok, "title": title, "trigger": None,
         "status": state or "unknown"}
        for tok, title, state in _iter_escalation_headers(run_dir)
    ]


def _iter_escalation_headers(run_dir):
    """Yield ``(token, title, state)`` for each escalation block, where state
    is 'OPEN', 'ANSWERED', or '' (unknown).

    An entry is ANSWERED when EITHER its header carries ``(status: ANSWERED)``
    OR its ``Answer:`` line is filled in — two independent signals — so a partial
    write (Answer filled, header still OPEN) is treated as ANSWERED/redispatch-
    pending, not awaiting-human. So this scans each block's body lines for a
    non-empty ``Answer:`` and lets it override an OPEN header."""
    text = _read_text_capped(run_dir / "escalations.md")
    for header, body in _split_escalation_blocks(text):
        token, title, header_state = _parse_escalation_header(header)
        if token is None:
            continue
        state = "ANSWERED" if (header_state == "ANSWERED" or
                               _has_filled_answer(body)) else header_state
        yield token, title, state


def _split_escalation_blocks(text):
    """Yield ``(header_line, [body_lines])`` for each ``## [...]`` block."""
    header, body = None, []
    for line in text.splitlines():
        if line.startswith("## ["):
            if header is not None:
                yield header, body
            header, body = line, []
        elif header is not None:
            body.append(line)
    if header is not None:
        yield header, body


def _parse_escalation_header(line):
    """Return ``(token, title, state)`` for a header, or ``(None, '', '')``."""
    close = line.find("]", 4)
    if close == -1:
        return None, "", ""
    rest = line[close + 1:]
    state = _header_state(rest)
    return line[4:close].strip(), rest.split("(status:")[0].strip(), state


def _header_state(rest):
    """Map the part after the bracket to 'OPEN', 'ANSWERED', or '' (unknown)."""
    if "(status: OPEN)" in rest:
        return "OPEN"
    if "(status: ANSWERED)" in rest:
        return "ANSWERED"
    return ""


def _has_filled_answer(body_lines):
    """True if any body line is a non-empty ``Answer: <text>``."""
    for line in body_lines:
        stripped = line.strip().lstrip("-* ").strip()
        if stripped.lower().startswith("answer:"):
            return bool(stripped[len("answer:"):].strip())
    return False


def _request_excerpt(run_dir):
    """One-line excerpt of request.md: the first non-blank, non-heading line."""
    text = _read_text_capped(run_dir / "request.md")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:REQUEST_EXCERPT_CHARS]
    return ""


def _decisions_tail(run_dir):
    """Last few non-blank lines of decisions-log.md (bounded). Display only —
    v2 pins no machine grammar on this file, so nothing is derived from it."""
    text = _read_text_capped(run_dir / "decisions-log.md")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-DECISIONS_TAIL_LINES:]


# --- stage derivation (cold-artifact only — never a live "running" claim) ---

def _derive_stage(slices, run_dir, started=False):
    """The run's furthest-progressed stage, derived from cold artifacts:
    ``preflight`` (no slices decomposed yet) < ``iron-council`` (decomposed but
    no slice work has started) < ``execution`` (some work done, not all terminal)
    < ``final-review`` (every slice terminal — complete/split).

    ``started`` lets a v2 caller add the generation's own strong start signals (a
    recorded wave, a persisted sidecar) to the artifact signals checked here.
    Read-only; this is an honest artifact signal, not a claim that anything is
    running right now."""
    if not slices:
        return "preflight"
    if all(s.get("status") in ("complete", "split") for s in slices):
        return "final-review"
    started = started or \
        any(s.get("status") in ("complete", "split") for s in slices) or \
        any((run_dir / f"slice-{s.get('id')}-report.md").is_file() for s in slices)
    return "execution" if started else "iron-council"


# ==========================================================================
# Iron Council verdicts
# ==========================================================================

def _read_council(run_dir, generation):
    """Iron Council verdicts as ``[{scope, verdict, summary}]``.

    v2 reads ``council-verdict`` events, whose scope is the event's own ``scope``
    field (a slice id or ``intake``) — a pinned machine channel, unlike the prose
    log. When a v2 run has no events log yet it falls back to v1's scrape of
    ``decisions-log.md``; v1 runs always take that path."""
    if generation == SCHEMA_V2 and _has_events(run_dir):
        return _council_from_events(run_dir)
    return _parse_council(run_dir)


def _council_from_events(run_dir):
    """Council verdicts from the events log, bounded to COUNCIL_MAX.

    v2 pins the event type but not its payload keys, so the verdict is taken from
    ``payload.verdict`` and the summary from ``payload.summary`` or
    ``payload.rationale``, with the role appended when present (the council is
    five reviewers, so knowing which one objected is the useful part)."""
    out = []
    for event in _iter_events(run_dir):
        if event.get("type") != "council-verdict":
            continue
        payload = _payload(event)
        out.append({
            "scope": str(event.get("scope") or "?"),
            "verdict": _first_verdict(str(payload.get("verdict") or "").upper()),
            "summary": _council_summary(payload),
        })
        if len(out) >= COUNCIL_MAX:
            break
    return out


def _council_summary(payload):
    role = payload.get("role") or payload.get("agent")
    body = payload.get("summary") or payload.get("rationale") or ""
    text = f"[{role}] {body}" if role else str(body)
    return text[:COUNCIL_SUMMARY_CHARS]


def _bracket_prefix(line):
    """Split a ``[token] rest`` line (tolerating leading #/-/* whitespace) into
    ``(token, rest)``, or ``(None, "")`` when it has no leading bracket token."""
    s = line.lstrip("#-* \t")
    if not s.startswith("["):
        return None, ""
    close = s.find("]")
    if close == -1:
        return None, ""
    return s[1:close].strip(), s[close + 1:].strip()


def _first_verdict(upper):
    """The strongest council verdict named in an upper-cased line, or ''.
    ENDORSE_WITH_CONCERNS is checked before ENDORSE (it contains 'ENDORSE')."""
    for v in ("ENDORSE_WITH_CONCERNS", "OBJECT", "ENDORSE"):
        if v in upper:
            return v
    return ""


def _parse_council(run_dir):
    """Iron Council verdicts scraped from decisions-log.md (the v1 grammar). Each
    ``[<scope>] COUNCIL…`` or ``[<scope>] IRON COUNCIL…`` line yields
    ``{scope, verdict, summary}``. Pure; bounded to COUNCIL_MAX entries."""
    text = _read_text_capped(run_dir / "decisions-log.md")
    out = []
    for line in text.splitlines():
        token, rest = _bracket_prefix(line)
        if token is None:
            continue
        upper = rest.upper()
        if not (upper.startswith("COUNCIL") or upper.startswith("IRON COUNCIL")):
            continue
        out.append({
            "scope": token,
            "verdict": _first_verdict(upper),
            "summary": rest[:COUNCIL_SUMMARY_CHARS],
        })
        if len(out) >= COUNCIL_MAX:
            break
    return out


# --- runbook (the final-review executive dashboard source) ------------------

def _parse_front_matter(text):
    """Top-level ``key: value`` pairs between the leading ``---`` fences of a
    Markdown file. Nested inline ``{...}`` values are kept as raw strings. Returns
    {} when there is no leading front-matter block."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, val = line.partition(":")
        if sep and key.strip() and not key.startswith((" ", "\t")):
            fm[key.strip()] = val.strip()
    return fm


def _section_text(text, heading):
    """The body of a Markdown section: lines after ``heading`` up to the next
    ``## `` heading (exclusive), stripped."""
    out, capturing = [], False
    for line in text.splitlines():
        if line.strip() == heading:
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def _parse_runbook(run_dir):
    """Parse runbook.md into ``{front_matter, executive_readout}``, or ``None`` when
    absent. Feeds the final-review executive dashboard."""
    path = run_dir / "runbook.md"
    if not path.is_file():
        return None
    text = _read_text_capped(path)
    return {
        "front_matter": _parse_front_matter(text),
        "executive_readout": _section_text(text, "## Executive Readout"),
    }


# --- artifact inventory (files created along the way) -----------------------

# The fixed run-state files an inventory reports when present. Spans both
# generations: v2 adds events.jsonl / conventions.md, and a v1 run simply has
# neither.
KNOWN_ARTIFACTS = ("dag.json", "request.md", "conventions.md",
                   "decisions-log.md", "escalations.md", "events.jsonl",
                   "runbook.md", "metrics.json")

# Per-slice artifact globs. ``slice-*-status.json`` is the v2 sidecar;
# ``slice-*-split.json`` is its v1 predecessor, kept so a v1 run dir in a mixed
# repo still lists everything it has.
ARTIFACT_GLOBS = ("slice-*-report.md", "slice-*-status.json",
                  "slice-*-split.json")


def _list_artifacts(run_dir):
    """Sorted names of the known run artifacts present in ``run_dir``."""
    names = {name for name in KNOWN_ARTIFACTS if (run_dir / name).is_file()}
    for pattern in ARTIFACT_GLOBS:
        for path in glob.glob(str(run_dir / pattern)):
            names.add(Path(path).name)
    return sorted(names)


def _run_etag(run_dir):
    """Per-run ETag from the mtimes of dag.json and its sibling artifacts.

    Every file the payload derives from must appear here or a change to it would
    serve a stale 304: that includes events.jsonl (escalation + council truth),
    every per-slice sidecar (label truth), and metrics.json (so a mid-run
    ``run_metrics.py --write`` refresh invalidates the cache like any other
    artifact change)."""
    parts = []
    for name in KNOWN_ARTIFACTS:
        parts.append(f"{name}:{_mtime_token(run_dir / name)}")
    for path in sorted(glob.glob(str(run_dir / "slice-*-status.json"))):
        parts.append(f"{Path(path).name}:{_mtime_token(path)}")
    return _etag(";".join(parts))


def _mtime_token(path):
    try:
        return f"{os.path.getmtime(path):.6f}"
    except OSError:
        return "-"


def _etag(material):
    return '"' + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32] + '"'


# ==========================================================================
# Layer (B): read-only HTTP handler
# ==========================================================================

class DashboardHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # Injected by build_server:
    roots = ()         # ordered ((root_key, data_root), ...); key "" == single-root
    assets_root = ""   # realpath of the bundled assets dir
    allowed_hosts = set()

    server_version = "spec-loop-2-dashboard"

    # --- only GET and HEAD exist; everything else is 405 ---

    def do_GET(self):
        self._emit(self._route(), write_body=True)

    def do_HEAD(self):
        self._emit(self._route(), write_body=False)

    def _route(self):
        """Dispatch the request to a handler, returning a Response."""
        if not self._host_allowed():
            return _text(421, b"misdirected request")
        route = self.path.split("?", 1)[0]
        if route == "/api/runs":
            return self._serve_api_runs()
        if route.startswith("/api/runs/"):
            return self._serve_api_run_detail(route[len("/api/runs/"):])
        return self._serve_static(route)

    # Any other verb is rejected uniformly.
    def _reject_method(self):
        self._emit(_text(405, b"method not allowed"), write_body=True)

    do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _reject_method

    # --- security gates ---

    def _host_allowed(self):
        host = self.headers.get("Host")
        return host is not None and host in self.allowed_hosts

    # --- endpoints (each returns a Response) ---

    def _serve_api_runs(self):
        runs = scan_all_roots(self.roots)
        etag = _etag("|".join(self._collection_material(runs)))
        return (self._not_modified(etag)
                or _json_response({"runs": runs}, etag))

    def _collection_material(self, runs):
        """ETag material keyed on each run's namespaced id + its dir mtimes,
        resolved within the run's OWNING root only."""
        material = []
        for run in runs:
            _root_key, run_dir = self._resolve_run_dir(run["run_id"])
            # "-" only if a run listed at scan time fails re-resolution (e.g. a
            # concurrent delete between the two globs) — an intentional weaker
            # cache key, never a wrong body. Correctness never depends on it.
            etag = _run_etag(Path(run_dir)) if run_dir else "-"
            material.append(f"{run['run_id']}:{etag}")
        return material

    def _serve_api_run_detail(self, raw_id):
        # The client URL-encodes the namespaced id (the ':' separator arrives as
        # %3A); decode before parsing. Containment (resolve_within) remains the
        # safety net for any traversal a decode might reveal.
        namespaced = urllib.parse.unquote(raw_id).rstrip("/")
        root_key, run_dir = self._resolve_run_dir(namespaced)
        if run_dir is None:
            return _text(404, b"not found")
        run = _namespace_run(_scan_one_run(Path(run_dir)), root_key)
        _summary, doc, _source = _run_metrics(Path(run_dir))
        run = {**run, "metrics_full": doc}
        etag = _run_etag(Path(run_dir))
        return self._not_modified(etag) or _json_response(run, etag)

    def _resolve_run_dir(self, namespaced_id):
        """Path-traversal-safe, per-root: identify the OWNING root by its key, then
        enumerate ONLY that root's discovered run dirs, exact-match the (bare)
        run-id basename, and realpath-confine within that ONE root. A namespaced id
        from root A can never enumerate or resolve within root B. Returns
        ``(root_key, run_dir)`` or ``(root_key, None)`` — one uniform miss for "no
        such run" and "escapes root" (no oracle)."""
        root_key, data_root, run_id = self._owning_root(namespaced_id)
        if data_root is None:
            return "", None
        known = {Path(p).parent.name for p in
                 glob.glob(str(Path(data_root) / "*" / "dag.json"))}
        if run_id not in known:
            return root_key, None
        run_dir = resolve_within(data_root, run_id)
        confined = run_dir if run_dir and os.path.isdir(run_dir) else None
        return root_key, confined

    def _owning_root(self, namespaced_id):
        """Resolve a (possibly namespaced) id to ``(root_key, data_root,
        bare_run_id)``, or ``("", None, None)`` if no root owns it. Single-root ->
        the sole root (empty key), id as-is. Multi-root -> split on the FIRST ':'
        and match the key exactly so a bare id is never mis-split."""
        if len(self.roots) == 1 and self.roots[0][0] == "":
            return "", self.roots[0][1], namespaced_id
        key, _, run_id = namespaced_id.partition(":")
        for root_key, data_root in self.roots:
            if root_key == key:
                return root_key, data_root, run_id
        return "", None, None

    def _serve_static(self, route):
        rel = route.lstrip("/") or "index.html"
        target = resolve_within(self.assets_root, rel)
        if target is None or not os.path.isfile(target):
            return _text(404, b"not found")
        body = self._read_asset(target)
        if body is None:
            return _text(404, b"not found")
        return Response(200, body, _content_type(target))

    def _read_asset(self, target):
        try:
            with open(target, "rb") as fh:
                return fh.read(MAX_FILE_BYTES)
        except OSError:
            return None

    # --- response helpers ---

    def _not_modified(self, etag):
        """Return a 304 Response if the client's If-None-Match matches, else None."""
        if self.headers.get("If-None-Match") == etag:
            return Response(304, b"", "application/json", etag)
        return None

    def _emit(self, resp, write_body):
        self.send_response(resp.status)
        self.send_header("Content-Type", resp.content_type)
        self.send_header("Content-Length", str(len(resp.body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if resp.etag:
            self.send_header("ETag", resp.etag)
        self.end_headers()
        if write_body and resp.body:
            self.wfile.write(resp.body)

    def log_message(self, *args):
        pass  # quiet by default


def _json_response(obj, etag=None):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return Response(200, body, "application/json; charset=utf-8", etag)


_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


def _content_type(path):
    return _CONTENT_TYPES.get(Path(path).suffix.lower(), "application/octet-stream")


# ==========================================================================
# Wiring
# ==========================================================================

def build_server(root, assets_dir=None, port=DEFAULT_PORT, net=NetworkConfig()):
    """Build (but do not start) a ThreadingHTTPServer.

    ``root`` is a repo root (str/Path) OR a list of repo roots. Each root's data
    root is fixed to ``realpath(root/docs/spec-loop)`` and namespaced by a stable
    per-root key (empty for a single root -> transparent).
    ``assets_dir`` defaults to this script's bundled ``dashboard_assets/``.

    ``net`` (a ``NetworkConfig``) carries the bind host and advertised port. The
    bind host is the socket bind address ONLY and is decoupled from — and NEVER
    widens — the Host-header allowlist. The allowlist is derived from the
    advertised port (the published port a browser targets), defaulting to the
    effective bound port. Port 0 -> an ephemeral port (used by tests). This is the
    load-bearing anti-DNS-rebinding invariant: binding ``0.0.0.0`` does not add
    any host to the allowlist."""
    roots = _resolve_roots(root)
    if assets_dir is None:
        assets_dir = Path(__file__).resolve().parent / ASSETS_SUBPATH
    assets_root = os.path.realpath(str(assets_dir))

    handler = type("BoundDashboardHandler", (DashboardHandler,), {
        "roots": roots,
        "assets_root": assets_root,
        "allowed_hosts": set(),  # fixed below once the real port is known
    })
    server = ThreadingHTTPServer((net.bind_host, port), handler)
    # The advertised port drives the allowlist. A falsy advertise_port (None or 0)
    # means "use the effective bound port" — so an ephemeral port 0, with or
    # without an explicit advertise_port=0, still yields a reachable loopback
    # allowlist and never an unreachable ":0" entry.
    effective_advertise = net.advertise_port or server.server_address[1]
    handler.allowed_hosts = _host_allowlist(effective_advertise)
    return server


def _resolve_roots(root):
    """Normalize ``root`` (a single repo root or a list) into an ordered list of
    ``(root_key, data_root)`` pairs, where ``data_root`` is the realpath'd
    ``<root>/docs/spec-loop`` trust boundary. A single root gets an empty key
    (transparent, un-namespaced); multiple roots get stable, deterministic keys."""
    raw = [root] if isinstance(root, (str, os.PathLike)) else list(root)
    data_roots = [os.path.realpath(os.path.join(str(r), *DATA_SUBPATH))
                  for r in raw]
    if len(data_roots) == 1:
        return [("", data_roots[0])]
    return list(zip(_root_keys(raw), data_roots))


def _root_keys(raw_roots):
    """Deterministic, stable, collision-free key per root, derived from its
    basename. Preserves input order; disambiguates duplicate basenames with a
    stable index suffix so identically-named repos never share a namespace."""
    basenames = [os.path.basename(os.path.normpath(str(r))) for r in raw_roots]
    seen = {}
    for name in basenames:
        seen[name] = seen.get(name, 0) + 1
    counters, keys = {}, []
    for name in basenames:
        if seen[name] == 1:
            keys.append(name)
        else:
            counters[name] = counters.get(name, 0) + 1
            keys.append(f"{name}#{counters[name]}")
    return keys


def _host_allowlist(port):
    """Loopback-only allowlist keyed on the ADVERTISED port. Intentionally
    hardcoded to 127.0.0.1/localhost — the bind host is never a member, so
    binding 0.0.0.0 cannot widen it."""
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="read-only spec-loop-2 dashboard server")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"port to serve on (default: {DEFAULT_PORT})")
    ap.add_argument("--root", action="append", default=None,
                    help="repo root containing docs/spec-loop; repeat for "
                         "multiple roots (default: cwd)")
    ap.add_argument("--bind-host", default="127.0.0.1",
                    help="socket bind address; use 0.0.0.0 ONLY inside a "
                         "container (default: 127.0.0.1). Does NOT widen the "
                         "Host-header allowlist.")
    ap.add_argument("--advertise-port", type=int, default=None,
                    help="published port a browser targets; drives the Host "
                         "allowlist (default: --port).")
    args = ap.parse_args(argv)

    raw_roots = args.root or ["."]
    roots = [str(Path(r).resolve()) for r in raw_roots]
    for _key, data_root in _resolve_roots(roots):
        if not os.path.isdir(data_root):
            print(f"warning: {data_root} does not exist — no runs from it",
                  file=sys.stderr)

    server = build_server(roots, port=args.port,
                          net=NetworkConfig(args.bind_host, args.advertise_port))
    bound_port = server.server_address[1]
    advertised = args.advertise_port or bound_port
    print(f"spec-loop-2 dashboard (read-only) serving {len(roots)} root(s)")
    print(f"  bind {args.bind_host}:{bound_port}; "
          f"open http://127.0.0.1:{advertised}/   (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
