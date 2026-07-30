"""Build a review package: commit list, stat, -U5 diff, and a hunk index.

Python port of v1's bash `review-package`, with two v2 additions the review
machinery depends on:

- **Hunk index** — a fenced JSON block ``{file: [[start, end], ...]}`` of the
  changed line ranges on the HEAD side, computed from ``git diff -U0``. The
  fixer and finding-verifier use it as the mechanical anchor check: a finding
  whose file:line falls outside these ranges (and is not marked outside_diff)
  is refuted without further judgment.
- **Size fallback** — the default -U5 context (v1 used -U10; with 1-2
  reviewers instead of 7, narrower context plus targeted Reads is the better
  trade) falls back to -U3, then to stat + hunk index only, keeping the
  package under a byte cap so it never dominates a reviewer's context.

Named per range so a re-review after fixes gets a distinct fresh file.
Stdlib only; read-only over git. Exit 0 ok / 2 usage or git error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

MAX_BYTES = 300_000
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def run_git(repo_dir, *argv):
    """Read-only git; raises CalledProcessError with stderr on failure."""
    return subprocess.run(
        ["git", "-C", repo_dir, *argv],
        capture_output=True, text=True, check=True,
    ).stdout


def hunk_index(repo_dir, base, head):
    """{file: [[start, end], ...]} of HEAD-side changed ranges, from -U0."""
    diff = run_git(repo_dir, "diff", "-U0", f"{base}..{head}")
    index: dict[str, list[list[int]]] = {}
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+++ /dev/null"):
            current = None  # deletion: no HEAD-side lines to anchor to
        elif current is not None:
            m = HUNK_RE.match(line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                # A pure deletion (count 0) still anchors reviewers to the seam.
                index.setdefault(current, []).append([start, max(start, start + count - 1)])
    return index


def build(repo_dir, base, head, context):
    parts = [
        f"# Review package: {base}..{head}  (context: -U{context})",
        "",
        "## Commits",
        run_git(repo_dir, "log", "--oneline", f"{base}..{head}").rstrip(),
        "",
        "## Files changed",
        run_git(repo_dir, "diff", "--stat", f"{base}..{head}").rstrip(),
        "",
        "## Hunk index (HEAD-side changed line ranges)",
        "```hunk-index",
        json.dumps(hunk_index(repo_dir, base, head), indent=0, sort_keys=True),
        "```",
        "",
        "## Diff",
        run_git(repo_dir, "diff", f"-U{context}", f"{base}..{head}").rstrip(),
        "",
    ]
    return "\n".join(parts)


def build_capped(repo_dir, base, head):
    """(text, note) — degrade context until the package fits MAX_BYTES."""
    for context in (5, 3):
        text = build(repo_dir, base, head, context)
        if len(text.encode()) <= MAX_BYTES:
            return text, f"-U{context}"
    text = build(repo_dir, base, head, 0)
    if len(text.encode()) <= MAX_BYTES:
        return text, "-U0 (oversize diff; Read the files for context)"
    # Even -U0 is oversize: stat + hunk index only, reviewers must Read files.
    head_part = text.split("## Diff")[0]
    return (
        head_part
        + "## Diff\n(omitted: diff exceeds the package byte cap even at -U0 — "
        "use the hunk index and Read the changed files directly)\n",
        "stat+index only",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--out", required=True)
    ns = parser.parse_args(argv)

    try:
        for ref in (ns.base, ns.head):
            run_git(ns.repo_dir, "rev-parse", "--verify", "--quiet", ref)
        text, note = build_capped(ns.repo_dir, ns.base, ns.head)
    except subprocess.CalledProcessError as err:
        print(f"error: git failed: {err.stderr.strip() or err}", file=sys.stderr)
        return 2
    except OSError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    os.makedirs(os.path.dirname(os.path.abspath(ns.out)) or ".", exist_ok=True)
    tmp = ns.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, ns.out)
    commits = run_git(ns.repo_dir, "rev-list", "--count", f"{ns.base}..{ns.head}").strip()
    print(f"wrote {ns.out}: {commits} commit(s), {len(text.encode())} bytes, {note}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
