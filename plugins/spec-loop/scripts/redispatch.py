#!/usr/bin/env python3
"""redispatch.py — build a wave re-dispatch from the run's own artifacts.

Run 20260908-jira-intake hand-assembled every re-dispatch and paid three ways: a
dropped answer key re-opened an answered round, a re-plan from the slice goal lost
the controller's fix orders, and one acceptance was ruled in prose three times.

`args --run-dir D --wave N --repo-dir R --stage <slice>=<plan|review|fix|verify>
[--orders <slice>=<file|->] [--head <slice>=<sha>]` prints {slices (non-terminal,
each with slice.entry when its sidecar has commits.head), answers (every answered
id), accepted_violations, notes, resume{advised, reason}}. `accept-violations
--run-dir D --ts TS --slice S --from-escalation ESC (--all | --json <file|->)
[--answer TEXT]` appends ONE decision event (kind: accepted-violations) plus the
escalation-answered event under --answer, so the two cannot diverge. Writes only
through run_state.append_event; paths come from worktrees.py. Exit 0 / 2 (stderr).
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dag as dagmod  # noqa: E402
import run_state as rs  # noqa: E402
import worktrees as wt  # noqa: E402

ENTRY_STAGES = ("plan", "review", "fix", "verify")
TERMINAL_SIDECAR = ("DONE", "SPLIT")
ACCEPTANCE_KIND = "accepted-violations"
SLICE_ARG_KEYS = ("id", "goal", "files", "subsystems", "risk_tier", "depth")


def normalize_fingerprint(raw):
    """{metric, file, function|null} with a normalized path (PURE). Raises
    RunStateError on a shape the wave would discard, so a bad acceptance is
    refused here instead of announced-and-ignored there."""
    if not isinstance(raw, dict):
        raise rs.RunStateError("fingerprint must be an object: %r" % (raw,))
    metric, path, function = raw.get("metric"), raw.get("file"), raw.get("function")
    if not _nonempty(metric) or not _nonempty(path):
        raise rs.RunStateError("fingerprint needs non-empty metric and file: %r" % (raw,))
    if function is not None and not isinstance(function, str):
        raise rs.RunStateError("fingerprint function must be a string or null: %r" % (raw,))
    if any("*" in str(part) for part in (metric, path, function or "")):
        raise rs.RunStateError("fingerprint carries a wildcard, refused: %r — a metric-wide "
            "acceptance would also accept a NEW breach" % (raw,))
    normalized_path = str(path).replace("\\", "/")
    if normalized_path.startswith("./"):
        normalized_path = normalized_path[2:]
    return {"metric": str(metric), "file": normalized_path, "function": function}


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def dedupe_fingerprints(fingerprints):
    """Order-preserving, keyed on (metric, file, function) (PURE)."""
    seen = {}
    for fp in fingerprints:
        seen.setdefault((fp["metric"], fp["file"], fp["function"] or ""), fp)
    return list(seen.values())


def read_sidecar(run_dir, slice_id):
    """The slice's sidecar, or None when it was never persisted."""
    path = os.path.join(run_dir, "slice-%s-status.json" % slice_id)
    if not os.path.isfile(path):
        return None
    body = rs.read_json(path)
    return body if isinstance(body, dict) else None


def answers_from_events(events):
    """{id: answer} for every escalation-answered event, all rounds, last
    write wins — the cumulative map the wave's round counter depends on (PURE)."""
    return {esc_id: payload.get("answer")
        for esc_id, payload in rs.answered_escalations(events).items() if payload.get("answer")}


def acceptances_from_events(events):
    """{slice: [fingerprints]} from every decision of kind accepted-violations (PURE)."""
    out = {}
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict) or payload.get("kind") != ACCEPTANCE_KIND:
            continue
        slice_id = payload.get("slice") or event.get("scope")
        raw = payload.get("accepted") if isinstance(payload.get("accepted"), list) else []
        out.setdefault(slice_id, []).extend(_lenient_fingerprints(raw))
    return {slice_id: dedupe_fingerprints(fps) for slice_id, fps in out.items()}


def _lenient_fingerprints(raw):
    """Recorded fingerprints were validated on the way in; a stale one is skipped."""
    out = []
    for item in raw:
        try:
            out.append(normalize_fingerprint(item))
        except rs.RunStateError:
            continue
    return out


def wave_slice_ids(dag, wave_index):
    for wave in dag.get("waves") or []:
        if wave.get("index") == wave_index:
            return list(wave.get("slice_ids") or [])
    raise rs.RunStateError("dag.json has no wave with index %d" % wave_index)


def parse_assignments(pairs, label):
    """['s1=fix', ...] -> {'s1': 'fix'}; a malformed pair is a usage error."""
    for pair in pairs or []:
        if "=" not in pair:
            raise rs.RunStateError("--%s expects <slice>=<value>, got %r" % (label, pair))
    return dict(pair.split("=", 1) for pair in pairs or [])


def build_entry(sidecar, stage, head_override, orders_override):
    """The slice.entry the wave resumes at, from the sidecar the controller
    already trusts (PURE)."""
    review = sidecar.get("review") if isinstance(sidecar.get("review"), dict) else {}
    entry = {"stage": stage, "head": head_override or sidecar["commits"]["head"]}
    if isinstance(review.get("fix_rounds"), int):
        entry["fix_rounds"] = review["fix_rounds"]
    for key in ("review_tier", "tasks_completed", "critique"):
        if sidecar.get(key) is not None:
            entry[key] = sidecar[key]
    if isinstance(review.get("residual"), list):
        entry["residual"] = review["residual"]
    orders = orders_override if orders_override is not None else review.get("open")
    if stage in ("review", "fix") and isinstance(orders, list) and orders:
        entry["orders"] = orders
    return entry


def slice_args(dag_slice, sidecar, ctx):
    """The per-slice wave arg the controller documents, minus the entry."""
    out = {key: dag_slice.get(key) for key in SLICE_ARG_KEYS}
    commits = sidecar.get("commits") if sidecar and isinstance(sidecar.get("commits"), dict) else {}
    out["base_sha"] = commits.get("base") or ctx["dag"].get("base_sha")
    out["worktree"] = wt.worktree_path(ctx["repo_dir"], ctx["run_id"], dag_slice["id"])
    out["branch"] = wt.branch_name(ctx["run_id"], dag_slice["id"])
    return out


def _sidecar_head(sidecar):
    commits = sidecar.get("commits") if sidecar else None
    return commits.get("head") if isinstance(commits, dict) else None


def _branch_tip(repo_dir, branch):
    """The branch's current sha, or None when the branch or repo is unavailable."""
    argv = ["git", "-C", repo_dir, "rev-parse", "--verify", "--quiet", branch]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, shell=False, check=False)
    except OSError:
        return None
    return (proc.stdout.strip() or None) if proc.returncode == 0 else None


def _skipped_note(dag_slice, sidecar):
    """Why a slice of the wave is left out of the re-dispatch, or None (PURE)."""
    if sidecar and sidecar.get("status") in TERMINAL_SIDECAR:
        return "%s's sidecar is %s (dag: %s): merged work never re-enters a wave" % (
            dag_slice["id"], sidecar["status"], dag_slice.get("status"))
    if dag_slice.get("status") in dagmod.TERMINAL_SLICE_STATUSES:
        return "%s is %s in dag.json: merged work never re-enters a wave" % (dag_slice["id"], dag_slice["status"])
    return None


def _drift_note(repo_dir, slice_arg, entry):
    tip = _branch_tip(repo_dir, slice_arg["branch"])
    if tip and not tip.startswith(entry["head"]) and not entry["head"].startswith(tip):
        return ("%s: entry.head %s is not the tip of %s (%s) — pass --head %s=<sha> if the branch "
            "was committed to by hand" % (slice_arg["id"], entry["head"], slice_arg["branch"], tip[:7], slice_arg["id"]))
    return None


def _one_slice(dag_slice, ctx):
    """(slice_arg or None, notes) for one wave member. `ctx` carries run_dir,
    run_id, repo_dir, dag and the three override maps (stages, heads, orders)."""
    slice_id, stages = dag_slice["id"], ctx["stages"]
    sidecar = read_sidecar(ctx["run_dir"], slice_id)
    skipped = _skipped_note(dag_slice, sidecar)
    if skipped:
        return None, [skipped]
    arg = slice_args(dag_slice, sidecar, ctx)
    notes = [] if sidecar else ["%s has no sidecar: dispatched without an entry, base from dag.json" % slice_id]
    if not _sidecar_head(sidecar):
        if slice_id in stages:
            notes.append("%s has no commits.head, so --stage %s is ignored: it runs the plain pipeline" % (slice_id, stages[slice_id]))
        return arg, notes
    if slice_id not in stages:
        raise rs.RunStateError("%s has commits.head %s and needs --stage %s=<%s>" % (
            slice_id, _sidecar_head(sidecar), slice_id, "|".join(ENTRY_STAGES)))
    arg["entry"] = build_entry(sidecar, stages[slice_id], ctx["heads"].get(slice_id), ctx["orders"].get(slice_id))
    drift = _drift_note(ctx["repo_dir"], arg, arg["entry"])
    return arg, notes + ([drift] if drift else [])


def _check_stages(stages):
    for slice_id, stage in stages.items():
        if stage not in ENTRY_STAGES:
            raise rs.RunStateError("--stage %s=%s: stage must be one of %s" % (slice_id, stage, "/".join(ENTRY_STAGES)))


def build_args(run_dir, wave_index, repo_dir, overrides):
    """The re-dispatch args object for one wave. `overrides` holds the optional
    maps `stages`, `heads` and `orders`, each keyed by slice id."""
    stages = overrides.get("stages") or {}
    _check_stages(stages)
    dag = rs.read_json(os.path.join(run_dir, "dag.json"))
    events = rs.read_events(run_dir)
    by_id = {s["id"]: s for s in dagmod.slices_of(dag)}
    ctx = {"run_dir": run_dir, "run_id": dag.get("run_id"), "repo_dir": repo_dir, "dag": dag,
        "stages": stages, "heads": overrides.get("heads") or {}, "orders": overrides.get("orders") or {}}
    slices, notes = [], []
    for slice_id in wave_slice_ids(dag, wave_index):
        if slice_id not in by_id:
            raise rs.RunStateError("wave %d names %s, which dag.json has no slice for" % (wave_index, slice_id))
        arg, slice_notes = _one_slice(by_id[slice_id], ctx)
        notes.extend(slice_notes)
        if arg:
            slices.append(arg)
    return {"slices": slices, "answers": answers_from_events(events),
        "accepted_violations": acceptances_from_events(events), "notes": notes,
        "resume": _resume_advice(slices)}


def _resume_advice(slices):
    without = [s["id"] for s in slices if "entry" not in s]
    if without:
        return {"advised": True, "reason": "%s carry no entry and may replay completed stages from the journal" % ", ".join(without)}
    return {"advised": False, "reason": "every dispatched slice carries an entry; its first prompt differs, so the journal cannot help it"}


def _opened_record(events, esc_id):
    for event in reversed(events):
        payload = event.get("payload")
        if event.get("type") == "escalation-opened" and isinstance(payload, dict) and payload.get("id") == esc_id:
            return payload
    raise rs.RunStateError("no escalation-opened event carries id %r" % (esc_id,))


def _requested_fingerprints(record, take_all, json_path):
    if take_all:
        raw = record.get("violations")
        if not isinstance(raw, list) or not raw:
            raise rs.RunStateError("%s carries no violations[] to accept with --all; pass --json" % record.get("id"))
        return raw, None
    body = rs.read_json(json_path)
    if isinstance(body, list):
        return body, None
    if isinstance(body, dict) and isinstance(body.get("accepted"), list):
        return body["accepted"], body.get("rationale")
    raise rs.RunStateError("--json must be a list of fingerprints or {accepted: [...], rationale}")


def accept_violations(run_dir, ts, request):
    """Record an acceptance by escalation id: one decision event, plus the
    answer when given. `request` carries slice, esc_id, take_all, json_path and
    answer. Returns the CLI payload."""
    slice_id, esc_id, answer = request["slice"], request["esc_id"], request.get("answer")
    if esc_id.split(":")[0] != slice_id:
        raise rs.RunStateError("escalation %s does not belong to slice %s" % (esc_id, slice_id))
    record = _opened_record(rs.read_events(run_dir), esc_id)
    raw, rationale = _requested_fingerprints(record, request["take_all"], request.get("json_path"))
    accepted = dedupe_fingerprints([normalize_fingerprint(fp) for fp in raw])
    described = ", ".join(_describe(fp) for fp in accepted)
    payload = {"summary": "accepted %d quality-gate violation(s) for %s: %s" % (len(accepted), slice_id, described),
        "rationale": rationale or (answer or "controller acceptance recorded by escalation id"),
        "reversibility": "moderate", "kind": ACCEPTANCE_KIND, "slice": slice_id,
        "from_escalation": esc_id, "accepted": accepted}
    emitted = [rs.append_event(run_dir, rs.build_event(ts, slice_id, "decision", payload))["type"]]
    if answer:
        answered = {"id": esc_id, "answer": answer, "answered_at": ts}
        emitted.append(rs.append_event(run_dir, rs.build_event(ts, slice_id, "escalation-answered", answered))["type"])
    return {"ok": True, "slice": slice_id, "from_escalation": esc_id, "accepted": len(accepted),
        "fingerprints": accepted, "events": emitted}


def _describe(fp):
    return "%s %s%s" % (fp["metric"], fp["file"], ":" + fp["function"] if fp["function"] else "")


def _orders_arg(pairs):
    """--orders <slice>=<file|-> -> {slice: list}; each file is a JSON list."""
    out = {}
    for slice_id, path in parse_assignments(pairs, "orders").items():
        body = rs.read_json(path)
        if not isinstance(body, list):
            raise rs.RunStateError("--orders %s: %s must hold a JSON list" % (slice_id, path))
        out[slice_id] = body
    return out


def _run(args):
    rs._require_run_dir(args.run_dir)
    if args.command == "args":
        overrides = {"stages": parse_assignments(args.stage, "stage"),
            "heads": parse_assignments(args.head, "head"), "orders": _orders_arg(args.orders)}
        return build_args(args.run_dir, args.wave, args.repo_dir, overrides)
    rs._require_ts(args.ts)
    request = {"slice": args.slice, "esc_id": args.from_escalation, "take_all": args.all,
        "json_path": args.json, "answer": args.answer}
    return accept_violations(args.run_dir, args.ts, request)


def build_parser():
    ap = argparse.ArgumentParser(description="Build a spec-loop wave re-dispatch from the run's artifacts.")
    subs = ap.add_subparsers(dest="command", required=True)
    a = subs.add_parser("args", help="print the re-dispatch wave args for one wave")
    a.add_argument("--run-dir", required=True, help="docs/spec-loop/<run-id> directory")
    a.add_argument("--wave", type=int, required=True, help="wave index to re-dispatch")
    a.add_argument("--repo-dir", required=True, help="repository root (worktree paths, branch tips)")
    a.add_argument("--stage", action="append", help="<slice>=<plan|review|fix|verify>; required per headed slice")
    a.add_argument("--orders", action="append", help="<slice>=<file|->: JSON list replacing the sidecar's review.open")
    a.add_argument("--head", action="append", help="<slice>=<sha>: override the sidecar's commits.head")
    c = subs.add_parser("accept-violations", help="record accepted gate violations by escalation id")
    c.add_argument("--run-dir", required=True, help="docs/spec-loop/<run-id> directory")
    c.add_argument("--ts", required=True, help="ISO-8601 UTC timestamp")
    c.add_argument("--slice", required=True, help="slice id owning the escalation")
    c.add_argument("--from-escalation", required=True, help="escalation id whose violations are accepted")
    group = c.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="accept every violation the record lists")
    group.add_argument("--json", help="fingerprint list, or {accepted, rationale}; - for stdin")
    c.add_argument("--answer", help="also record this text as the escalation's answer")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        payload = _run(args)
    except rs.RunStateError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
