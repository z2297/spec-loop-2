#!/usr/bin/env python3
"""Slice worktree and branch lifecycle for a spec-loop run (stdlib only).

Every slice in a wave works in its own git worktree so parallel slices never
share an index or a checkout (paths and branch names pinned in
references/run-state-v2.md):

    worktree  .worktrees/spec-loop/<run-id>/<slice-id>   (gitignored)
    branch    spec-loop/<run-id>/<slice-id>              (cut from base_ref)

`prepare` is called by the controller before a wave is dispatched and `cleanup`
after a slice is merged (or when a run is torn down). Both are idempotent: the
controller may crash and resume at any point, so re-running them must converge
on the intended state rather than fail.

Design decisions:
- **Convergent, per-slice outcomes.** Each slice gets one result object with a
  status the controller can act on (`created`, `reused`, `recreated`, `absent`,
  or `error` with git's own stderr). One slice's problem never aborts its
  siblings — a resume with a missing branch reports that slice as an error and
  still prepares the rest. Only conditions that invalidate the whole call (no
  slices, missing base ref, not a git repository) fail globally.
- **Reuse is verified, not assumed.** A worktree is reused only when git still
  has it registered at that path, the expected branch is checked out, AND the
  directory is really on disk. A registration whose directory vanished, a
  detached HEAD, or somebody else's branch is a stale worktree: it is removed
  with `git worktree remove --force` (falling back to `git worktree prune` when
  the directory is already gone) and recreated.
- **Fresh mode never adopts an existing branch.** `prepare` without `--resume`
  always uses `-b`; if the branch already exists (the integration-failure path
  deliberately keeps slice branches) that slice errors and names `--resume`,
  because silently reusing history the caller did not ask for is worse than
  stopping.
- **git is the source of truth.** State is read back from
  `git worktree list --porcelain` (parsed by the pure `parse_worktree_list`)
  and `git show-ref` rather than from directory guesses, and paths are compared
  by realpath — git reports resolved paths, and on macOS the repo itself often
  lives behind a symlink.
- **We never delete a path git does not own.** An unrelated directory sitting in
  a worktree's place is reported as an error, never removed.

Exit codes: 0 = every slice ok; 1 = at least one slice failed, or the call was
refused (missing base ref, no slices); 2 = the environment is unusable (git
missing, not a git repository, bad arguments).

Usage:
    worktrees.py prepare --run-id <id> --slices s1,s2 --base-ref <branch>
                         [--repo-dir .]
    worktrees.py prepare --run-id <id> --slices s1,s2 --resume [--repo-dir .]
    worktrees.py cleanup --run-id <id> --slices s1 [--delete-branch]
                         [--repo-dir .]
"""

import argparse
import json
import os
import subprocess
import sys

WORKTREE_ROOT = os.path.join(".worktrees", "spec-loop")
BRANCH_PREFIX = "spec-loop"
GITIGNORE_ENTRY = ".worktrees/"
GITIGNORE_BLOCK = "# spec-loop slice worktrees (never committed)\n.worktrees/\n"
GIT_TIMEOUT = 120


class WorktreeError(Exception):
    """The environment is unusable (no git, not a repository) — exit 2."""


class PrepareError(Exception):
    """The call is refused as a whole (bad base ref, no slices) — exit 1."""


# --------------------------------------------------------------------------
# naming
# --------------------------------------------------------------------------

def worktree_path(repo_dir, run_id, slice_id):
    """Absolute path of a slice's worktree inside repo_dir."""
    return os.path.join(os.path.abspath(repo_dir), WORKTREE_ROOT, run_id, slice_id)


def branch_name(run_id, slice_id):
    return "%s/%s/%s" % (BRANCH_PREFIX, run_id, slice_id)


# --------------------------------------------------------------------------
# git plumbing
# --------------------------------------------------------------------------

def run_git(repo_dir, *args):
    """Run git in repo_dir; return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(["git", "-C", repo_dir] + list(args),
                              capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except OSError as exc:
        raise WorktreeError("cannot run git: %s" % exc)
    except subprocess.SubprocessError as exc:
        raise WorktreeError("git %s did not complete: %s" % (args[0] if args else "", exc))
    return proc.returncode, proc.stdout, proc.stderr


def require_repo(repo_dir):
    """Raise WorktreeError unless repo_dir is inside a git work tree."""
    if not os.path.isdir(repo_dir):
        raise WorktreeError("%s is not a directory" % repo_dir)
    code, out, err = run_git(repo_dir, "rev-parse", "--is-inside-work-tree")
    if code != 0 or out.strip() != "true":
        raise WorktreeError("%s is not a git work tree: %s"
                            % (repo_dir, (err or out).strip()))


def parse_worktree_list(text):
    """Parse `git worktree list --porcelain` into records (PURE).

    Each record: {path, head, branch (short name or None), detached, bare,
    prunable}.
    """
    records = []
    current = None
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            current = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current = {"path": value, "head": None, "branch": None,
                       "detached": False, "bare": False, "prunable": False}
            records.append(current)
            continue
        if current is None:
            continue
        if key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value[len("refs/heads/"):] if value.startswith(
                "refs/heads/") else value
        elif key == "detached":
            current["detached"] = True
        elif key == "bare":
            current["bare"] = True
        elif key == "prunable":
            current["prunable"] = True
    return records


def list_worktrees(repo_dir):
    code, out, err = run_git(repo_dir, "worktree", "list", "--porcelain")
    if code != 0:
        raise WorktreeError("git worktree list failed: %s" % (err or out).strip())
    return parse_worktree_list(out)


def registered_worktree(repo_dir, path):
    """The worktree record git has registered at `path`, or None."""
    target = os.path.realpath(path)
    for record in list_worktrees(repo_dir):
        if os.path.realpath(record["path"]) == target:
            return record
    return None


def ref_exists(repo_dir, ref):
    code, _, _ = run_git(repo_dir, "rev-parse", "--verify", "--quiet",
                         "%s^{commit}" % ref)
    return code == 0


def branch_exists(repo_dir, branch):
    code, _, _ = run_git(repo_dir, "show-ref", "--verify", "--quiet",
                         "refs/heads/%s" % branch)
    return code == 0


# --------------------------------------------------------------------------
# .gitignore
# --------------------------------------------------------------------------

def ensure_gitignore(repo_dir):
    """Make sure `.worktrees/` is ignored. Returns present|added|created."""
    path = os.path.join(repo_dir, ".gitignore")
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(GITIGNORE_BLOCK)
            return "created"
        with open(path, "r", encoding="utf-8") as fh:
            body = fh.read()
        for line in body.splitlines():
            if line.strip().rstrip("/") == GITIGNORE_ENTRY.rstrip("/"):
                return "present"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(("" if body.endswith("\n") or not body else "\n")
                     + "\n" + GITIGNORE_BLOCK)
        return "added"
    except OSError as exc:
        raise PrepareError("cannot update %s: %s" % (path, exc))


# --------------------------------------------------------------------------
# prepare
# --------------------------------------------------------------------------

def _remove_stale(repo_dir, path):
    """Drop a stale worktree registration/directory. Returns an error or None."""
    code, out, err = run_git(repo_dir, "worktree", "remove", "--force", path)
    if code == 0:
        return None
    run_git(repo_dir, "worktree", "prune")
    if registered_worktree(repo_dir, path) is None and not os.path.exists(path):
        return None
    return (err or out).strip() or "git worktree remove failed"


def _create(repo_dir, path, branch, base_ref, resume, adopt=False):
    """Add the worktree. Returns an error message or None.

    `adopt` is set when we just tore down this slice's own stale worktree: its
    branch legitimately exists and must be re-attached at its head (the slice's
    commits are on it), so that case behaves like a resume.
    """
    if branch_exists(repo_dir, branch):
        if not (resume or adopt):
            return ("branch %s already exists: re-attach it with --resume rather "
                    "than cutting it again from %s" % (branch, base_ref))
        code, out, err = run_git(repo_dir, "worktree", "add", path, branch)
    elif resume:
        return ("branch %s does not exist: nothing to resume for this slice "
                "(prepare it fresh from the base ref instead)" % branch)
    else:
        code, out, err = run_git(repo_dir, "worktree", "add", path, "-b", branch,
                                 base_ref)
    if code != 0:
        return (err or out).strip() or "git worktree add failed"
    return None


def prepare_slice(repo_dir, run_id, slice_id, base_ref=None, resume=False):
    """Ensure one slice's worktree exists on its own branch. Returns a result."""
    path = worktree_path(repo_dir, run_id, slice_id)
    branch = branch_name(run_id, slice_id)
    result = {"slice": slice_id, "path": path, "branch": branch, "status": None}

    record = registered_worktree(repo_dir, path)
    status = "created"
    if record is not None:
        if (record.get("branch") == branch and not record.get("detached")
                and os.path.isdir(path)):
            result["status"] = "reused"
            return result
        failure = _remove_stale(repo_dir, path)
        if failure:
            result["status"] = "error"
            result["error"] = failure
            return result
        status = "recreated"
    elif os.path.exists(path):
        result["status"] = "error"
        result["error"] = ("%s exists but git has no worktree registered there; "
                           "move it aside — this script never deletes a path git "
                           "does not own" % path)
        return result

    failure = _create(repo_dir, path, branch, base_ref, resume,
                      adopt=(status == "recreated"))
    if failure:
        result["status"] = "error"
        result["error"] = failure
        return result
    result["status"] = status
    return result


def prepare(repo_dir, run_id, slices, base_ref=None, resume=False):
    """Prepare every slice's worktree. Returns one result per slice."""
    require_repo(repo_dir)
    slice_ids = [s for s in (slices or []) if s]
    if not slice_ids:
        raise PrepareError("no slices given: nothing to prepare")
    if not resume:
        if not base_ref:
            raise PrepareError("--base-ref is required unless --resume is used")
        if not ref_exists(repo_dir, base_ref):
            raise PrepareError("base ref %r does not exist in %s"
                               % (base_ref, repo_dir))
    ensure_gitignore(repo_dir)
    return [prepare_slice(repo_dir, run_id, slice_id, base_ref, resume)
            for slice_id in slice_ids]


# --------------------------------------------------------------------------
# cleanup
# --------------------------------------------------------------------------

def cleanup_slice(repo_dir, run_id, slice_id, delete_branch=False):
    """Remove one slice's worktree (and optionally its branch)."""
    path = worktree_path(repo_dir, run_id, slice_id)
    branch = branch_name(run_id, slice_id)
    result = {"slice": slice_id, "path": path, "branch": branch, "status": None}

    if registered_worktree(repo_dir, path) is None and not os.path.exists(path):
        run_git(repo_dir, "worktree", "prune")
        result["status"] = "absent"
    else:
        failure = _remove_stale(repo_dir, path)
        if failure:
            result["status"] = "error"
            result["error"] = failure
        else:
            result["status"] = "removed" if not os.path.exists(path) else "error"
            if result["status"] == "error":
                result["error"] = "%s survived git worktree remove --force" % path

    if delete_branch:
        deleted = False
        if branch_exists(repo_dir, branch):
            code, out, err = run_git(repo_dir, "branch", "-D", branch)
            deleted = code == 0
            if not deleted:
                result["status"] = "error"
                result["error"] = (err or out).strip() or "git branch -D failed"
        result["branch_deleted"] = deleted
    return result


def cleanup(repo_dir, run_id, slices, delete_branch=False):
    """Remove every listed slice's worktree; tolerate what is already gone."""
    require_repo(repo_dir)
    return [cleanup_slice(repo_dir, run_id, slice_id, delete_branch)
            for slice_id in (slices or []) if slice_id]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _split_ids(raw):
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def build_parser():
    ap = argparse.ArgumentParser(
        description="Prepare and clean up spec-loop slice worktrees.")
    subs = ap.add_subparsers(dest="command", required=True)

    def common(parser):
        parser.add_argument("--repo-dir", default=".", help="repository root")
        parser.add_argument("--run-id", required=True, help="spec-loop run id")
        parser.add_argument("--slices", required=True,
                            help="comma-separated slice ids")
        return parser

    prep = common(subs.add_parser("prepare", help="create/reuse slice worktrees"))
    prep.add_argument("--base-ref", help="ref new slice branches are cut from")
    prep.add_argument("--resume", action="store_true",
                      help="re-attach existing slice branches instead of cutting new ones")

    clean = common(subs.add_parser("cleanup", help="remove slice worktrees"))
    clean.add_argument("--delete-branch", action="store_true",
                       help="also delete the slice branch")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            results = prepare(args.repo_dir, args.run_id, _split_ids(args.slices),
                              base_ref=args.base_ref, resume=args.resume)
        else:
            results = cleanup(args.repo_dir, args.run_id, _split_ids(args.slices),
                              delete_branch=args.delete_branch)
    except PrepareError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    except WorktreeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(r["status"] == "error" for r in results) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
