#!/usr/bin/env python3
"""The run-structure authority for a spec-loop run (standard library only).

`docs/spec-loop/<run-id>/dag.json` is the sole authority on run structure
(shape pinned in references/run-state-v2.md). This script is the ONE
implementation of every question and every mutation over it: is the file
contract-valid, which slices may run next, what was dispatched, what completed,
and how a SPLIT verdict is grafted into the graph. Nothing else re-derives wave
membership — if a caller wants to know the next wave, it runs `next-wave`.

Design decisions:
- **Pure core, thin shell.** Every rule is a pure function over the parsed dict
  (`validate_dag`, `next_wave`, `record_wave`, `mark_*`, `ingest_split`), so the
  whole contract is testable without a filesystem, a clock, or git. The shell
  only loads, delegates, and writes.
- **Split parents are terminal.** A slice with status `split` is never
  scheduled and never blocks: a dependency on it is satisfied when all of its
  children are satisfied (recursively, so a child that split in turn resolves
  through its own children) — NOT merely because the parent is `split`. A
  `split` parent with no children can never be satisfied — that is reported as
  a deadlock rather than silently stalling.
- **One readiness rule, reused rather than copied.** Read-only consumers (the
  dashboard) import `next_wave` for the next wave and `project_waves` for the
  whole remaining schedule instead of re-deriving readiness; both are pure and
  leave the dag untouched. Import is side-effect free and needs no repository.
- **Fail closed, and never write on top of a broken file.** Every mutating
  subcommand re-validates the whole dag before touching it; a refused operation
  (unknown slice, duplicate wave index, depth cap, non-pending split parent)
  exits 1 with `{"ok": false, "errors": [...]}` and leaves dag.json byte for
  byte unchanged. Only read paths tolerate a contract-invalid dag, and only so
  a broken run can still be inspected.
- **Atomic writes.** dag.json is rewritten via a temp file in the same
  directory plus `os.replace`, so a concurrent reader (dashboard, guard hook)
  sees either the old or the new file, never a half-written one.
- **Reports, not prose.** Every subcommand prints one JSON object (or array) on
  stdout for machine consumers; humans read the rendered artifacts instead.

Exit codes: 0 = ok; 1 = contract failure (validation errors, refused mutation,
deadlocked graph); 2 = usage / unreadable input (missing or half-written
dag.json, bad JSON payload, bad arguments).

Usage:
    dag.py validate      --run-dir <dir>
    dag.py next-wave     --run-dir <dir>
    dag.py record-wave   --run-dir <dir> --index N --slice-ids s1,s2
                         [--workflow-run-id wf_x]
    dag.py mark          --run-dir <dir> (--wave N | --slice s1) --status <s>
    dag.py ingest-split  --run-dir <dir> --slice s1 --file <split.json|->
"""

import argparse
import json
import os
import sys
import tempfile

SCHEMA_VERSION = 2
MAX_DEPTH = 2
# A "split" into one child is the same slice under a new id; references/
# split-ingestion.md treats that as a malformed proposal, not a decomposition.
MIN_SPLIT_CHILDREN = 2
# Guard on the read-only wave projection: a graph that cannot drain in this many
# waves is pathological, and a viewer must never spin on it.
MAX_PROJECTED_WAVES = 100
SLICE_STATUSES = ("pending", "complete", "split")
TERMINAL_SLICE_STATUSES = ("complete", "split")
WAVE_STATUSES = ("dispatched", "collected")
RISK_TIERS = (1, 2, 3)


class DagError(Exception):
    """The dag (or a payload) could not be read at all — exit 2."""


class ContractError(Exception):
    """The operation is refused by the run-state contract — exit 1."""

    def __init__(self, errors):
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("; ".join(self.errors))


# --------------------------------------------------------------------------
# persistence
# --------------------------------------------------------------------------

def dag_path(run_dir):
    return os.path.join(run_dir, "dag.json")


def load_dag(run_dir):
    """Parse dag.json, or raise DagError (missing / half-written / not JSON)."""
    path = dag_path(run_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise DagError("cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise DagError("%s is not valid JSON (half-written?): %s" % (path, exc))


def write_dag(run_dir, dag):
    """Rewrite dag.json atomically (temp file in the same dir + os.replace)."""
    path = dag_path(run_dir)
    body = json.dumps(dag, ensure_ascii=False, indent=2) + "\n"
    directory = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".dag-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except OSError as exc:
        raise DagError("cannot write %s: %s" % (path, exc))


# --------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------

def slices_of(dag):
    """The slices list, or [] when the dag is too broken to have one."""
    value = dag.get("slices") if isinstance(dag, dict) else None
    return [s for s in value if isinstance(s, dict)] if isinstance(value, list) else []


def waves_of(dag):
    value = dag.get("waves") if isinstance(dag, dict) else None
    return [w for w in value if isinstance(w, dict)] if isinstance(value, list) else []


def slice_index(dag):
    """{slice id: slice object} for every slice carrying a usable id."""
    index = {}
    for item in slices_of(dag):
        sid = item.get("id")
        if isinstance(sid, str) and sid and sid not in index:
            index[sid] = item
    return index


def children_of(dag, slice_id):
    return [s for s in slices_of(dag) if s.get("parent") == slice_id]


def deps_of(item):
    value = item.get("deps")
    return [d for d in value if isinstance(d, str)] if isinstance(value, list) else []


# --------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------

def validate_dag(dag):
    """Return every contract violation in `dag` as a list of messages.

    Run-level keys are deliberately asymmetric: `scope_ceiling` is checked only
    when present, while its neighbours (`run_id`, `base_ref`, `merge_mode`,
    `shared_constraints`, ...) stay unvalidated. Absence must never be an error:
    `_load_for_mutation` refuses to mutate a contract-invalid dag, so making any
    run-level key required would make every pre-existing run un-resumable and
    hard-fail mark/record-wave/ingest-split mid-run.
    """
    if not isinstance(dag, dict):
        return ["dag.json must contain a JSON object"]

    errors = []
    if dag.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be %d (found %r)"
                      % (SCHEMA_VERSION, dag.get("schema_version")))
    if not isinstance(dag.get("slices"), list):
        errors.append("slices must be a list")
    if "waves" in dag and not isinstance(dag.get("waves"), list):
        errors.append("waves must be a list")
    if "scope_ceiling" in dag:
        ceiling = dag.get("scope_ceiling")
        if not isinstance(ceiling, list):
            errors.append("scope_ceiling must be a list of strings")
        else:
            for position, entry in enumerate(ceiling):
                if not isinstance(entry, str) or not entry.strip():
                    errors.append("scope_ceiling entry %d must be a non-empty string "
                                  "(found %r)" % (position, entry))

    seen = set()
    for position, item in enumerate(slices_of(dag)):
        sid = item.get("id")
        if not isinstance(sid, str) or not sid:
            errors.append("slice at position %d has no usable id" % position)
            continue
        if sid in seen:
            errors.append("duplicate slice id %r" % sid)
            continue
        seen.add(sid)

        if item.get("status") not in SLICE_STATUSES:
            errors.append("slice %s: status must be one of %s (found %r)"
                          % (sid, "/".join(SLICE_STATUSES), item.get("status")))
        if item.get("risk_tier") not in RISK_TIERS:
            errors.append("slice %s: risk_tier must be 1, 2 or 3 (found %r)"
                          % (sid, item.get("risk_tier")))
        depth = item.get("depth")
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
            errors.append("slice %s: depth must be a non-negative integer (found %r)"
                          % (sid, depth))
        elif depth > MAX_DEPTH:
            errors.append("slice %s: depth %d exceeds the cap of %d"
                          % (sid, depth, MAX_DEPTH))
        if not isinstance(item.get("deps", []), list):
            errors.append("slice %s: deps must be a list" % sid)

    index = slice_index(dag)
    for item in slices_of(dag):
        sid = item.get("id")
        if not isinstance(sid, str) or not sid:
            continue
        for dep in deps_of(item):
            if dep not in index:
                errors.append("slice %s: dep %r references an unknown slice" % (sid, dep))
        parent_id = item.get("parent")
        if parent_id is None:
            continue
        parent = index.get(parent_id)
        if parent is None:
            errors.append("slice %s: unknown parent %r" % (sid, parent_id))
            continue
        if parent.get("status") != "split":
            errors.append("slice %s: parent %s must have status \"split\" (found %r)"
                          % (sid, parent_id, parent.get("status")))
        if isinstance(item.get("depth"), int) and isinstance(parent.get("depth"), int):
            if item["depth"] != parent["depth"] + 1:
                errors.append("slice %s: depth %r must be parent %s depth + 1 (%d)"
                              % (sid, item["depth"], parent_id, parent["depth"] + 1))

    errors.extend(_cycle_errors(dag, index))

    wave_indexes = set()
    for position, item in enumerate(waves_of(dag)):
        wave_index = item.get("index")
        label = wave_index if isinstance(wave_index, int) else "at position %d" % position
        if not isinstance(wave_index, int) or isinstance(wave_index, bool) or wave_index < 1:
            errors.append("wave %s: index must be a 1-based integer" % label)
        elif wave_index in wave_indexes:
            errors.append("duplicate wave index %d" % wave_index)
        else:
            wave_indexes.add(wave_index)
        if item.get("status") not in WAVE_STATUSES:
            errors.append("wave %s: status must be one of %s (found %r)"
                          % (label, "/".join(WAVE_STATUSES), item.get("status")))
        ids = item.get("slice_ids")
        if not isinstance(ids, list):
            errors.append("wave %s: slice_ids must be a list" % label)
            continue
        for sid in ids:
            if sid not in index:
                errors.append("wave %s: slice_ids entry %r references an unknown slice"
                              % (label, sid))
    return errors


def _cycle_errors(dag, index):
    """One message per slice that participates in a dependency cycle."""
    state = {}  # sid -> 0 unvisited / 1 on stack / 2 done
    in_cycle = set()

    def walk(sid, stack):
        state[sid] = 1
        stack.append(sid)
        for dep in deps_of(index[sid]):
            if dep not in index:
                continue
            if state.get(dep, 0) == 1:
                in_cycle.update(stack[stack.index(dep):])
            elif state.get(dep, 0) == 0:
                walk(dep, stack)
        stack.pop()
        state[sid] = 2

    for sid in index:
        if state.get(sid, 0) == 0:
            walk(sid, [])
    return ["slice %s: dependency cycle" % sid for sid in sorted(in_cycle)]


# --------------------------------------------------------------------------
# next-wave
# --------------------------------------------------------------------------

def _satisfied(sid, index, dag, resolving=None):
    """Is dependency `sid` satisfied? Split parents resolve via their children."""
    resolving = resolving or set()
    item = index.get(sid)
    if item is None or sid in resolving:  # unknown dep, or a cycle through splits
        return False
    status = item.get("status")
    if status == "complete":
        return True
    if status == "split":
        kids = children_of(dag, sid)
        if not kids:
            return False
        resolving = resolving | {sid}
        return all(_satisfied(k.get("id"), index, dag, resolving) for k in kids)
    return False


def _next_index(dag):
    """One past the highest recorded wave index (waves are 1-based)."""
    return max(
        [w["index"] for w in waves_of(dag)
         if isinstance(w.get("index"), int) and not isinstance(w.get("index"), bool)],
        default=0,
    ) + 1


def next_wave(dag):
    """Compute the next wave: {index, slice_ids} (+ done / deadlock detail).

    Runnable = status `pending` and every dep satisfied. This is the ONE
    implementation of wave membership; `waves[]` only records what was actually
    dispatched. Read-only and tolerant: a contract-invalid dag still yields a
    report (an unsatisfiable dep shows up as a deadlock) rather than an error.
    """
    index = slice_index(dag)
    wave_index = _next_index(dag)

    runnable, blocked = [], []
    for item in slices_of(dag):
        sid = item.get("id")
        if not isinstance(sid, str) or not sid or item.get("status") != "pending":
            continue
        unsatisfied = [d for d in deps_of(item) if not _satisfied(d, index, dag)]
        if unsatisfied:
            blocked.append({"slice": sid, "blocked_by": unsatisfied})
        else:
            runnable.append(sid)

    report = {"index": wave_index, "slice_ids": runnable}
    if runnable:
        return report
    if blocked:
        report["deadlock"] = True
        report["blocked"] = blocked
    else:
        report["done"] = True
    return report


def project_waves(dag, limit=MAX_PROJECTED_WAVES):
    """Project every remaining wave, not just the next one (PURE).

    Repeatedly applies `next_wave` to a working copy in which each projected
    wave is optimistically completed, so read-only consumers (the dashboard's
    "what is left" view) get a schedule without re-deriving the readiness rule.
    Returns `[{index, slice_ids}, ...]`; `dag` is never mutated. Projection
    stops when nothing more is runnable — slices still pending at that point are
    the deadlocked ones `next_wave` reports under `blocked`.
    """
    working = {"slices": [dict(item) for item in slices_of(dag)]}
    wave_index = _next_index(dag)
    projected = []
    while len(projected) < limit:
        runnable = next_wave(working)["slice_ids"]
        if not runnable:
            break
        projected.append({"index": wave_index, "slice_ids": runnable})
        by_id = slice_index(working)
        for slice_id in runnable:
            by_id[slice_id]["status"] = "complete"
        wave_index += 1
    return projected


# --------------------------------------------------------------------------
# mutators
# --------------------------------------------------------------------------

def record_wave(dag, index, slice_ids, workflow_run_id=None):
    """Append a dispatched wave to waves[]; return the recorded object."""
    errors = []
    if not isinstance(index, int) or isinstance(index, bool) or index < 1:
        errors.append("wave index must be a 1-based integer (got %r)" % (index,))
    elif any(w.get("index") == index for w in waves_of(dag)):
        errors.append("duplicate wave index %d: wave already recorded" % index)

    ids = list(slice_ids or [])
    if not ids:
        errors.append("a wave must dispatch at least one slice")
    if len(set(ids)) != len(ids):
        errors.append("duplicate slice ids in the wave: %s" % ", ".join(ids))

    known = slice_index(dag)
    for sid in ids:
        item = known.get(sid)
        if item is None:
            errors.append("%r references an unknown slice" % sid)
        elif item.get("status") != "pending":
            errors.append("slice %s is %r, only pending slices may be dispatched"
                          % (sid, item.get("status")))
    if errors:
        raise ContractError(errors)

    recorded = {"index": index, "slice_ids": ids,
                "workflow_run_id": workflow_run_id, "status": "dispatched"}
    dag.setdefault("waves", []).append(recorded)
    return recorded


def mark_wave(dag, index, status):
    """Set a recorded wave's status; return the wave."""
    if status not in WAVE_STATUSES:
        raise ContractError("wave status must be one of %s (got %r)"
                            % ("/".join(WAVE_STATUSES), status))
    for item in waves_of(dag):
        if item.get("index") == index:
            item["status"] = status
            return item
    raise ContractError("no wave with index %r is recorded" % (index,))


def mark_slice(dag, slice_id, status):
    """Set a slice's status; return the slice. `split` is terminal."""
    if status not in SLICE_STATUSES:
        raise ContractError("slice status must be one of %s (got %r)"
                            % ("/".join(SLICE_STATUSES), status))
    item = slice_index(dag).get(slice_id)
    if item is None:
        raise ContractError("unknown slice %r" % (slice_id,))
    if item.get("status") == "split" and status != "split":
        raise ContractError("slice %s is split: split is terminal, mark its children "
                            "instead" % slice_id)
    item["status"] = status
    return item


def ingest_split(dag, slice_id, split):
    """Graft a SPLIT verdict's children onto `slice_id`; return the children.

    Accepts either the `split` object (`{"children": [...]}`) or a whole
    SliceResult sidecar containing one. Children are inserted directly after
    the parent so dag order stays readable, the parent becomes terminal
    (`split`), and each child inherits the parent's deps and risk tier plus its
    own `internal_deps` (1-based sibling indices) mapped to the new child ids.
    """
    parent = slice_index(dag).get(slice_id)
    if parent is None:
        raise ContractError("unknown slice %r" % (slice_id,))
    if parent.get("status") != "pending":
        raise ContractError("slice %s is %r: only a pending slice may be split"
                            % (slice_id, parent.get("status")))

    parent_depth = parent.get("depth")
    if not isinstance(parent_depth, int) or isinstance(parent_depth, bool):
        raise ContractError("slice %s has no usable depth (%r)" % (slice_id, parent_depth))
    if parent_depth + 1 > MAX_DEPTH:
        raise ContractError(
            "slice %s is at depth %d: its children would be depth %d, past the cap of "
            "%d — the slice must be escalated instead of split again"
            % (slice_id, parent_depth, parent_depth + 1, MAX_DEPTH))

    proposals = _split_children(split)
    errors = _child_errors(proposals)
    existing = slice_index(dag)
    child_ids = ["%s.%d" % (slice_id, n) for n in range(1, len(proposals) + 1)]
    for cid in child_ids:
        if cid in existing:
            errors.append("child id %s already exists: the split was already ingested"
                          % cid)
    if errors:
        raise ContractError(errors)

    parent_deps = deps_of(parent)
    children = []
    for position, proposal in enumerate(proposals):
        deps = list(parent_deps)
        for ref in proposal.get("internal_deps") or []:
            sibling = child_ids[int(ref) - 1]
            if sibling not in deps:
                deps.append(sibling)
        child = {
            "id": child_ids[position],
            "goal": proposal["goal"],
            "files": list(proposal.get("files") or []),
            "subsystems": list(proposal.get("subsystems") or []),
            "deps": deps,
            "risk_tier": parent.get("risk_tier"),
            "depth": parent_depth + 1,
            "parent": slice_id,
            "status": "pending",
        }
        if parent.get("remediation"):
            child["remediation"] = True
        children.append(child)

    parent["status"] = "split"
    at = dag["slices"].index(parent) + 1
    dag["slices"][at:at] = children
    return children


def _split_children(split):
    """Pull the children list out of a split object or a whole sidecar."""
    if not isinstance(split, dict):
        raise ContractError("split payload must be a JSON object")
    if "children" not in split and isinstance(split.get("split"), dict):
        split = split["split"]
    children = split.get("children")
    if not isinstance(children, list) or len(children) < MIN_SPLIT_CHILDREN:
        raise ContractError("split.children must list at least %d children — a "
                            "one-child split is the same slice, not a "
                            "decomposition" % MIN_SPLIT_CHILDREN)
    return children


def _child_errors(proposals):
    """Validate child proposals, including internal_deps and sibling cycles."""
    errors = []
    count = len(proposals)
    edges = {}
    for position, proposal in enumerate(proposals):
        number = position + 1
        if not isinstance(proposal, dict):
            errors.append("child %d must be a JSON object" % number)
            continue
        goal = proposal.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            errors.append("child %d has no goal" % number)
        refs = proposal.get("internal_deps") or []
        if not isinstance(refs, list):
            errors.append("child %d: internal_deps must be a list" % number)
            continue
        clean = []
        for ref in refs:
            if not isinstance(ref, int) or isinstance(ref, bool):
                errors.append("child %d: internal_deps entry %r is not a 1-based "
                              "sibling index" % (number, ref))
            elif ref < 1 or ref > count:
                errors.append("child %d: internal_deps entry %d is out of range 1..%d"
                              % (number, ref, count))
            elif ref == number:
                errors.append("child %d: internal_deps references itself" % number)
            else:
                clean.append(ref)
        edges[number] = clean

    if not errors:
        errors.extend(_sibling_cycle_errors(edges))
    return errors


def _sibling_cycle_errors(edges):
    state = {}
    found = set()

    def walk(node, stack):
        state[node] = 1
        stack.append(node)
        for dep in edges.get(node, []):
            if state.get(dep, 0) == 1:
                found.update(stack[stack.index(dep):])
            elif state.get(dep, 0) == 0:
                walk(dep, stack)
        stack.pop()
        state[node] = 2

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            walk(node, [])
    if found:
        return ["internal_deps form a cycle among children %s"
                % ", ".join(str(n) for n in sorted(found))]
    return []


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _read_json_arg(path):
    """Read a JSON payload from a file path, or from stdin when path is '-'."""
    try:
        if path == "-":
            return json.loads(sys.stdin.read())
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        raise DagError("cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise DagError("%s is not valid JSON: %s" % (path, exc))


def _split_ids(raw):
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _load_for_mutation(run_dir):
    """Load a dag that is safe to write back: contract-valid or nothing."""
    dag = load_dag(run_dir)
    errors = validate_dag(dag)
    if errors:
        raise ContractError(
            ["refusing to mutate a contract-invalid dag.json"] + errors)
    return dag


def _run(args):
    """Return (payload, exit_code) for a parsed argv."""
    if args.command == "validate":
        errors = validate_dag(load_dag(args.run_dir))
        return {"ok": not errors, "errors": errors}, (1 if errors else 0)

    if args.command == "next-wave":
        report = next_wave(load_dag(args.run_dir))
        return report, (1 if report.get("deadlock") else 0)

    dag = _load_for_mutation(args.run_dir)
    if args.command == "record-wave":
        recorded = record_wave(dag, args.index, _split_ids(args.slice_ids),
                               args.workflow_run_id)
        payload = {"ok": True, "wave": recorded}
    elif args.command == "mark":
        if args.wave is not None:
            payload = {"ok": True, "wave": mark_wave(dag, args.wave, args.status)}
        else:
            payload = {"ok": True, "slice": mark_slice(dag, args.slice, args.status)}
    elif args.command == "ingest-split":
        children = ingest_split(dag, args.slice, _read_json_arg(args.file))
        payload = {"ok": True, "parent": args.slice,
                   "children": [c["id"] for c in children]}
    else:  # pragma: no cover — argparse rejects unknown subcommands
        raise DagError("unknown command %r" % args.command)

    write_dag(args.run_dir, dag)
    return payload, 0


def build_parser():
    ap = argparse.ArgumentParser(
        description="Run-structure authority over a spec-loop run's dag.json.")
    subs = ap.add_subparsers(dest="command", required=True)

    def with_run_dir(parser):
        parser.add_argument("--run-dir", required=True,
                            help="docs/spec-loop/<run-id> directory")
        return parser

    with_run_dir(subs.add_parser("validate", help="check dag.json against the contract"))
    with_run_dir(subs.add_parser("next-wave", help="compute the next runnable wave"))

    record = with_run_dir(subs.add_parser("record-wave", help="append a dispatched wave"))
    record.add_argument("--index", type=int, required=True, help="1-based wave index")
    record.add_argument("--slice-ids", required=True,
                        help="comma-separated slice ids dispatched in this wave")
    record.add_argument("--workflow-run-id", default=None,
                        help="workflow run id (omitted in inline mode)")

    mark = with_run_dir(subs.add_parser("mark", help="update a wave or slice status"))
    target = mark.add_mutually_exclusive_group(required=True)
    target.add_argument("--wave", type=int, help="wave index to mark")
    target.add_argument("--slice", help="slice id to mark")
    mark.add_argument("--status", required=True,
                      help="wave: dispatched|collected; slice: pending|complete|split")

    ingest = with_run_dir(subs.add_parser("ingest-split",
                                         help="graft a SPLIT verdict's children"))
    ingest.add_argument("--slice", required=True, help="the parent slice id")
    ingest.add_argument("--file", required=True,
                        help="split JSON (sidecar or split object); - for stdin")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        payload, code = _run(args)
    except ContractError as exc:
        print(json.dumps({"ok": False, "errors": exc.errors},
                         ensure_ascii=False, indent=2))
        return 1
    except DagError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
