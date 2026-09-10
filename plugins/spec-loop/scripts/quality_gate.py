#!/usr/bin/env python3
"""Objective code-quality gate for a spec-loop slice (standard library only).

Measures the slice's CHANGED code against the user's persisted thresholds
(cyclomatic/cognitive complexity, method/class length, parameter count, nesting
depth, and CRAP) and emits a single JSON report on stdout. It is the
measurement of record for the `quality-gate` skill: the skill runs this script
and quotes its JSON summary rather than eyeballing metrics by hand. It NEVER
installs anything, NEVER mutates the repo, and NEVER weakens a threshold --
detected analyzers are used read-only and everything else falls back to a
transparent, clearly-labelled builtin heuristic.

Pipeline:
  1. Changed-code discovery -- `git diff --unified=0 <base>..<head>` in
     --repo-dir; parse_diff() (a PURE function) turns the hunk headers into
     {file: [(start, end), ...]} added/modified line ranges. Deleted files and
     binary hunks are skipped so only surviving, changed code is measured.
  2. Config -- read the JSON config (schema in commands/quality-gate.md). A
     missing file falls back to DEFAULT_THRESHOLDS + DEFAULT_REFACTOR_RADIUS
     and records "config": "defaults"; `enabled: false` short-circuits to
     {"skipped": "gate disabled"} and exit 0. `refactor_radius` is carried
     through as configuration only -- this script never evaluates it; it is the
     plan stage's pre-execution ceiling, read by the controller through
     --print-config.
  3. Backends -- detected via shutil.which (never installed). `lizard`
     (multi-language) is preferred for CCN / NLOC / parameter count / function
     spans; for .py files, `radon cc -j` is used when lizard is absent. A
     function is measured only when its line span intersects a changed range.
  4. Builtin heuristic -- for any changed file no backend covers, a pure-stdlib
     analyzer splits the source into functions by signature regex (python / js /
     ts / java / c# / go styles, language by extension) and estimates each
     metric by branch-keyword counting, signature parsing, and indent/brace
     nesting. Branch counting reads a masked copy of the source in which the
     content of string literals and comments has been replaced by a sentinel
     -- python via stdlib tokenize, brace languages via a hand scanner that
     keeps ${} interpolation code visible -- so words and punctuation inside
     them are not measured as branching; a scanner failure falls back to the
     raw text. Every such finding is marked "source": "builtin-heuristic".
     cognitive_complexity is ONLY ever produced by this heuristic (a
     nesting-weighted approximation) or skipped -- it is never attributed to a
     real tool.
  5. crap_score -- only when a coverage report is found (--coverage, else a
     probe of the repo root for coverage.xml / lcov.info / cobertura*.xml).
     CRAP = comp^2 * (1 - coverage)^3 + comp per changed function whose file has
     coverage data; otherwise CRAP is skipped with a reason.
  6. Custom gates -- metric-form entries ({name, metric, threshold}) are
     evaluated against the measured values here; command-form entries are NOT
     run by this script (the skill runs those) and are listed in `skipped`.

Exit codes: 0 = every threshold and metric-form gate passed (or the gate is
disabled); 1 = one or more measured metrics failed; 2 = usage / git / config
error.

Usage:
    quality_gate.py --config <path> --base <ref> [--head HEAD]
                    [--repo-dir .] [--coverage <path>]
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tokenize
import xml.etree.ElementTree as ET

# The default thresholds mirror the quality-gate skill's table (SKILL.md) and
# the /spec-loop:quality-gate command's "Recommended" level, so the builtin
# fallback and any custom config stay consistent with the documented bar.
DEFAULT_THRESHOLDS = {
    "cyclomatic_complexity": 10,
    "cognitive_complexity": 15,
    "method_lines": 50,
    "parameter_count": 4,
    "nesting_depth": 3,
    "class_lines": 300,
    "crap_score": 30,
}

# The planner-declared refactor-radius proxy. These are NOT measured metrics:
# they are the ceiling the plan stage declares it will stay under, checked
# before implementation effort is spent. Shipped default-ON with deliberately
# conservative numbers -- a checkpoint that fires on an ordinary slice would be
# trained away within a run, so the floor (min_rewritten_lines) exists to keep
# small slices entirely out of the check rather than to soften its answer.
DEFAULT_REFACTOR_RADIUS = {
    "enabled": True,
    "max_rewrite_ratio": 0.5,
    "max_touched_existing_files": 8,
    "min_rewritten_lines": 150,
}

# Metrics measured per changed function (as opposed to per file/class).
_FUNCTION_METRICS = (
    "cyclomatic_complexity",
    "cognitive_complexity",
    "method_lines",
    "parameter_count",
    "nesting_depth",
)

# File extension -> heuristic language family. Governs which signature regex and
# nesting model (indent vs brace) the builtin analyzer uses.
_EXT_LANG = {
    ".py": "python",
    ".js": "cbrace", ".jsx": "cbrace", ".mjs": "cbrace", ".cjs": "cbrace",
    ".ts": "cbrace", ".tsx": "cbrace",
    ".java": "cbrace", ".cs": "cbrace", ".go": "cbrace",
    ".c": "cbrace", ".h": "cbrace", ".cpp": "cbrace", ".cc": "cbrace",
    ".hpp": "cbrace", ".rs": "cbrace",
}

# The subset of the brace extensions whose scan mask may be lexed by the hand
# scanner below. It implements plain JS/TypeScript quoting rules alone, where
# a single quote always opens a string. In Rust a single quote usually opens
# a lifetime, in C++ it also serves as a digit separator, so two of them on
# one line pair into a phantom string covering the real code between them --
# measured, that turns 2 branches into 1 with no signal, the one direction
# this mask is never allowed to move a count. Rust, C, C++, Go, Java and C#
# therefore keep their raw text: they stay on today's over-count, which is
# the safe direction, rather than being lexed by quoting rules that are not
# theirs. JSX and TSX carry the same residual for a different reason: the
# scanner has no model of a JSX text node, where an apostrophe is prose, not
# a string opener, so two contractions on one JSX text line pair into a
# phantom string over real code between them -- measured on
# `function Row(p) { return (<p>It's {p.a && p.b} - don't worry</p>); }`,
# cyclomatic_complexity 1 where the raw branch count is 2. `.jsx` and `.tsx`
# therefore also stay on raw text.
_JS_MASK_EXTS = frozenset({".js", ".mjs", ".cjs", ".ts"})

# Branch keywords whose occurrence adds one to cyclomatic complexity. Matched as
# whole words (or operators) so an identifier like `ifield` is not counted.
_BRANCH_WORDS = ("if", "elif", "case", "catch", "for", "while", "when")
_BRANCH_WORD_RE = re.compile(r"\b(?:%s)\b" % "|".join(_BRANCH_WORDS))
# Boolean operators and the ternary each add a branch. `else if` is NOT listed
# here: its `if` is already counted by _BRANCH_WORD_RE, so matching it again
# would double-count the same branch. The `?(?!\?)` avoids matching `??`.
_BRANCH_OPS_RE = re.compile(r"&&|\|\||\?(?!\?)")

# Signature detectors per language family. Each returns the callable's name for
# a matching source line, or None. Kept deliberately simple -- the builtin path
# is a labelled heuristic, not an authoritative parser.
_PY_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")
_PY_CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_]\w*)\b")
# C-family: `<name>(` preceding a `{` or `=>`, tolerating modifiers/return types.
_CBRACE_DEF_RE = re.compile(
    r"(?:function\s+)?([A-Za-z_]\w*)\s*\([^;{]*\)\s*(?:[:A-Za-z_<>\[\], \t*&]*)?\{"
)
_CBRACE_ARROW_RE = re.compile(
    r"\b([A-Za-z_]\w*)\s*=\s*(?:async\s+)?\([^;{]*\)\s*=>"
)


class GateError(Exception):
    """Raised for any unrecoverable gate condition (bad args, git failure, or a
    malformed config). Carries an actionable, user-facing message; main() maps
    it to exit code 2."""


# --------------------------------------------------------------------------
# Changed-code discovery (pure diff parsing)
# --------------------------------------------------------------------------

_DIFF_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_diff(text):
    """Parse `git diff --unified=0` output into {file: [(start, end), ...]} of
    ADDED/MODIFIED line ranges on the new (head) side. PURE: no I/O.

    Only the `+` side matters (the surviving code we measure). A deleted file
    (its new path is /dev/null) is skipped, as is a binary hunk (which carries
    no `@@` ranges). Ranges use 1-based inclusive line numbers; a hunk with a
    zero-length new side (a pure deletion) contributes no range."""
    ranges = {}
    current = None
    for line in text.splitlines():
        m = _DIFF_FILE_RE.match(line)
        if m:
            path = m.group(1).strip()
            current = None if path == "/dev/null" else path
            if current is not None:
                ranges.setdefault(current, [])
            continue
        hm = _HUNK_RE.match(line)
        if hm and current is not None:
            start = int(hm.group(1))
            count = int(hm.group(2)) if hm.group(2) is not None else 1
            if count > 0:
                ranges[current].append((start, start + count - 1))
    # Drop files that ended up with no added/modified ranges (pure deletions).
    return {f: rs for f, rs in ranges.items() if rs}


def _spans_overlap(a_start, a_end, b_start, b_end):
    """True if inclusive line spans [a_start, a_end] and [b_start, b_end] touch."""
    return a_start <= b_end and b_start <= a_end


def _intersects_changed(start, end, changed_ranges):
    """True if a function's line span intersects any changed range for its file."""
    return any(_spans_overlap(start, end, cs, ce) for cs, ce in changed_ranges)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def _read_config_object(path, what):
    """Read one config JSON object. Present-but-malformed is a hard error
    (exit 2) rather than a silent fallback, so a broken config is never
    mistaken for the default bar."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {what} {path!r}: {exc}") from exc
    if not isinstance(raw, dict):
        raise GateError(f"{what} {path!r} must be a JSON object")
    return raw


def _radius_object(value, what):
    """Coerce a raw `refactor_radius` config value to a plain dict. (PURE)

    An absent block yields {} so the defaults stand. A PRESENT non-object is a
    hard error rather than a silently ignored value: dropping a list or a bare
    number here would leave the operator believing they had set a ceiling they
    had not, which is exactly the silent-exclusion failure this block exists to
    avoid.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise GateError(f"{what} key 'refactor_radius' must be a JSON object")
    return dict(value)


def load_config(path, overlay_path=None):
    """Load the gate config, returning (config_dict, source). source is
    "defaults", "loaded", or "loaded+overlay". A missing file (or None path)
    yields the documented defaults.

    The per-repo overlay (committed `.spec-loop/quality-gate.json`) deep-merges
    over the global config: threshold keys override, `refactor_radius` keys
    override KEY-WISE (tuning one number never drops its siblings),
    `tier3_surfaces` unions (the overlay extends, it cannot remove a surface),
    `custom_gates` concat, other keys override. Both files predate the run —
    the guard hook denies writes to either while a run is active — so any
    loosening in an overlay is a deliberate, committed human choice, visible
    in review.
    """
    raw = {} if not path or not os.path.exists(path) else _read_config_object(path, "config")
    source = "defaults" if not raw else "loaded"
    if overlay_path and os.path.exists(overlay_path):
        overlay = _read_config_object(overlay_path, "overlay")
        merged_thresholds = dict(raw.get("thresholds") or {})
        merged_thresholds.update(overlay.get("thresholds") or {})
        merged = dict(raw)
        merged.update(overlay)
        merged["thresholds"] = merged_thresholds
        merged["custom_gates"] = (raw.get("custom_gates") or []) + (overlay.get("custom_gates") or [])
        merged["tier3_surfaces"] = sorted(
            set(raw.get("tier3_surfaces") or []) | set(overlay.get("tier3_surfaces") or [])
        )
        # refactor_radius merges KEY-WISE, like thresholds and unlike the
        # dict.update() fall-through above. A repo overlay that tunes one number
        # would otherwise replace the whole block and silently drop the other
        # three keys, handing the operator defaults they never chose.
        merged_radius = _radius_object(raw.get("refactor_radius"), "config")
        merged_radius.update(_radius_object(overlay.get("refactor_radius"), "overlay"))
        merged["refactor_radius"] = merged_radius
        raw = merged
        source = ("loaded+overlay" if source == "loaded" else "defaults+overlay")
    thresholds = dict(DEFAULT_THRESHOLDS)
    thresholds.update(raw.get("thresholds") or {})
    refactor_radius = dict(DEFAULT_REFACTOR_RADIUS)
    refactor_radius.update(_radius_object(raw.get("refactor_radius"), "config"))
    config = {
        "enabled": raw.get("enabled", True),
        "thresholds": thresholds,
        "refactor_radius": refactor_radius,
        "custom_gates": raw.get("custom_gates") or [],
    }
    # Pass through controller-consumed keys (tier3_surfaces, models, …) so
    # --print-config is the one door to the effective configuration.
    for key, value in raw.items():
        config.setdefault(key, value)
    return config, source


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------

def _run_git(argv, repo_dir):
    """Run a READ-ONLY git command (list-args, shell=False). User-derived refs
    are option-terminated by the caller. Raises GateError on failure so a git
    problem maps to exit 2, not a stack trace."""
    try:
        proc = subprocess.run(
            ["git", *argv], cwd=repo_dir, shell=False,
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError as exc:
        raise GateError(f"git not found: {exc}") from exc
    if proc.returncode != 0:
        raise GateError(
            f"git {argv[0]} failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def git_changed_ranges(base, head, repo_dir):
    """The {file: [(start, end), ...]} changed-line map for base..head. The refs
    are UNTRUSTED, so the range expression is followed by a trailing `--` so a
    leading-dash ref cannot be parsed as a git flag."""
    text = _run_git(["diff", "--unified=0", f"{base}..{head}", "--"], repo_dir)
    return parse_diff(text)


# --------------------------------------------------------------------------
# Backend: lizard (multi-language)
# --------------------------------------------------------------------------

def _lizard_available():
    return shutil.which("lizard") is not None


def _radon_available():
    return shutil.which("radon") is not None


def run_lizard(files, repo_dir):
    """Run `lizard --csv` over `files` and return a list of function records:
    {file, function, line_start, line_end, cyclomatic_complexity, method_lines,
     parameter_count}. Returns [] on any failure so a flaky backend degrades to
    the builtin heuristic rather than aborting the gate.

    lizard's --csv columns are: nloc, ccn, token, param, length, location,
    file, function-name, long-name, start-line, end-line."""
    if not files:
        return []
    try:
        proc = subprocess.run(
            ["lizard", "--csv", *files], cwd=repo_dir, shell=False,
            capture_output=True, text=True, check=False,
        )
    except (FileNotFoundError, OSError):
        return []
    if proc.returncode not in (0, 1):  # lizard exits 1 when warnings emitted
        return []
    return _parse_lizard_csv(proc.stdout)


def _parse_lizard_csv(text):
    """Parse lizard --csv text (PURE) into function records. Tolerant of extra
    trailing columns; a row that doesn't parse cleanly is skipped."""
    import csv
    import io
    out = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 11:
            continue
        try:
            nloc = int(row[0])
            ccn = int(row[1])
            param = int(row[3])
            filename = row[6]
            func = row[7]
            start = int(row[9])
            end = int(row[10])
        except (ValueError, IndexError):
            continue
        out.append({
            "file": filename, "function": func,
            "line_start": start, "line_end": end,
            "cyclomatic_complexity": ccn, "method_lines": nloc,
            "parameter_count": param,
        })
    return out


def run_radon(py_files, repo_dir):
    """Run `radon cc -j` over the Python files and return function records with
    cyclomatic_complexity and line spans (radon reports no NLOC/param, so those
    metrics fall through to the builtin heuristic for those functions). [] on
    any failure."""
    if not py_files:
        return []
    try:
        proc = subprocess.run(
            ["radon", "cc", "-j", *py_files], cwd=repo_dir, shell=False,
            capture_output=True, text=True, check=False,
        )
    except (FileNotFoundError, OSError):
        return []
    if proc.returncode != 0:
        return []
    return _parse_radon_json(proc.stdout)


def _parse_radon_json(text):
    """Parse `radon cc -j` JSON (PURE) into function records. radon maps each
    file to a list of blocks; only function/method blocks (type f/m) carry the
    complexity we gate on."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    out = []
    for filename, blocks in (data.items() if isinstance(data, dict) else ()):
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") not in ("f", "m"):
                continue
            try:
                start = int(block["lineno"])
                end = int(block.get("endline", block["lineno"]))
                ccn = int(block["complexity"])
            except (KeyError, ValueError, TypeError):
                continue
            out.append({
                "file": filename, "function": block.get("name", "?"),
                "line_start": start, "line_end": end,
                "cyclomatic_complexity": ccn,
            })
    return out


# --------------------------------------------------------------------------
# Builtin heuristic analyzer (pure, stdlib only)
# --------------------------------------------------------------------------

def _lang_for(path):
    return _EXT_LANG.get(os.path.splitext(path)[1].lower())


def _scan_lang_for(path):
    """The language family whose scan mask may be applied to `path`, else None
    to leave the file on raw text. Distinct from _lang_for on purpose: that one
    picks the extraction and nesting model, this one picks the mask, and only
    the JS/TypeScript subset of the brace extensions has a mask that lexes its
    quoting correctly. (PURE)"""
    lang = _lang_for(path)
    if lang != "cbrace":
        return lang
    if os.path.splitext(path)[1].lower() in _JS_MASK_EXTS:
        return "js"
    return None


def _count_params(sig):
    """Count parameters in a parenthesized signature substring. PURE. Splits the
    top-level parameter list on commas ignoring nested brackets, and drops a
    leading python `self`/`cls`."""
    depth = 0
    inner = None
    for i, ch in enumerate(sig):
        if ch == "(":
            if depth == 0:
                inner = i + 1
                start_depth = depth
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and inner is not None:
                params_str = sig[inner:i]
                break
    else:
        return 0
    params_str = params_str.strip()
    if not params_str:
        return 0
    parts = []
    depth = 0
    cur = ""
    for ch in params_str:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    names = [p.strip() for p in parts if p.strip()]
    if names and names[0] in ("self", "cls"):
        names = names[1:]
    return len(names)


# --------------------------------------------------------------------------
# Scan mask -- what the two branch scans are allowed to see
# --------------------------------------------------------------------------
# The builtin heuristic used to scan raw source text, so a branch word or a
# piece of operator punctuation inside a string literal or a comment was
# measured as real branching. The worst measured example in this repo was a
# human question ending in a question mark, counted as a ternary and pushing a
# function to exactly its cognitive threshold. Masking is applied ONLY to the
# text handed to _branch_count and _cognitive_approx: function extraction,
# brace depth, method_lines and class_lines all keep reading raw text, because
# a masked docstring continuation line starts at column 0 and would move the
# indent-derived end of the enclosing function. Masked spans are filled with a
# non-whitespace sentinel rather than spaces, because _cognitive_approx derives
# its nesting level from leading whitespace: space-fill would RAISE the measured
# cognitive complexity of dozens of functions. Every failure path returns the
# raw text, so the worst case remains today's over-count. Two maskers sit
# behind this seam: python via stdlib tokenize, the plain JS/TypeScript family
# (.js, .mjs, .cjs, .ts) via the hand scanner below. The remaining brace
# extensions -- .rs, .c, .h, .cpp, .cc, .hpp, .go, .java, .cs -- are
# deliberately NOT masked, because the hand scanner lexes JS quoting rules
# alone. .jsx and .tsx are ALSO deliberately NOT masked, because the scanner
# has no model of a JSX text node and an apostrophe inside one is prose, not
# a string opener. _scan_lang_for holds that routing.

_SCAN_SENTINEL = "x"

# The corruption trip-wire, expressed as a denominator: a mask that leaves more
# than one line in _MASK_LOST_DENOM of the non-blank lines with no content at
# all is discarded in favour of raw text. A correct mask empties nothing (the
# sentinel is non-blank), so any trip here means the span arithmetic went wrong.
_MASK_LOST_DENOM = 20


def _masked_token_types():
    """Token types whose text is masked out of a branch scan: string literals,
    comments, and the literal segments of an f-string. An f-string's embedded
    expression arrives as ordinary tokens and stays visible, so genuine
    operators inside one are still measured. (PURE)"""
    types = {tokenize.STRING, tokenize.COMMENT}
    types.add(getattr(tokenize, "FSTRING_MIDDLE", None))
    types.discard(None)
    return frozenset(types)


_MASKED_TOKEN_TYPES = _masked_token_types()


def _scan_tokens(text):
    """Tokenized `text`, or None on any tokenizer failure or a non-default end
    state. Every None return sends the caller back to the raw text. (PURE)"""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return None
    if not toks:
        return None
    if toks[-1].type != tokenize.ENDMARKER:
        return None
    return toks


def _masked_tokens(toks):
    """The subset of `toks` whose text gets masked out of a branch scan.
    (PURE)"""
    return [tok for tok in toks if tok.type in _MASKED_TOKEN_TYPES]


def _mask_line_range(row, start_col, end_col):
    """`row` with the half-open column range replaced by sentinel characters, so
    the line keeps its original length. (PURE)"""
    stop = min(end_col, len(row))
    width = max(0, stop - start_col)
    return row[:start_col] + (_SCAN_SENTINEL * width) + row[stop:]


def _token_mask_spans(tok, rows):
    """The (row_index, start_col, end_col) spans one masked token covers, one per
    physical line it reaches. Row indexes are 0-based into `rows`. On the
    opening physical line, masking starts at the token's own start column. On
    every later physical line, masking starts after that row's own leading
    spaces rather than at column 0, so the sentinel fill never erases the
    leading whitespace a downstream nesting-level reader derives from that
    row: leading whitespace carries no branch words or operator punctuation,
    so leaving it unmasked is measurement-neutral. (PURE)"""
    (first_row, first_col), (last_row, last_col) = tok.start, tok.end
    spans = []
    for row in range(first_row, last_row + 1):
        line = rows[row - 1]
        start = first_col if row == first_row else (
            len(line) - len(line.lstrip(" ")))
        end = len(line)
        if row == last_row:
            end = last_col
        spans.append((row - 1, start, end))
    return spans


def _mask_lost_too_much(raw_rows, masked_rows):
    """True once the mask has emptied more than one line in _MASK_LOST_DENOM of
    the non-blank lines -- the corruption signal that sends the scan back to raw
    text. (PURE)"""
    nonblank = sum(1 for row in raw_rows if row.strip())
    lost = sum(1 for raw, masked in zip(raw_rows, masked_rows)
               if raw.strip() and not masked.strip())
    return bool(nonblank) and (lost * _MASK_LOST_DENOM > nonblank)


def _mask_python_literals(text):
    """`text` with every string-literal, comment and f-string-literal span filled
    with the non-whitespace sentinel, preserving line count and line lengths, or
    None to fall back to the raw text. (PURE)"""
    toks = _scan_tokens(text)
    if toks is None:
        return None
    rows = text.split("\n")
    masked = list(rows)
    for tok in _masked_tokens(toks):
        for row_idx, start, end in _token_mask_spans(tok, rows):
            masked[row_idx] = _mask_line_range(masked[row_idx], start, end)
    if _mask_lost_too_much(rows, masked):
        return None
    return "\n".join(masked)


# --------------------------------------------------------------------------
# Brace-language scan mask
# --------------------------------------------------------------------------
# Brace languages get no stdlib tokenizer, so this is a hand character
# scanner over five constructs: the two comment forms and the three string
# forms. Template literals are handled separately from the flat forms
# because a ${...} interpolation holds real code -- blanking a whole template
# deletes genuine operators and UNDER-counts a function, the dangerous
# direction. The scanner stops short of one construct on purpose: a regex
# literal. Telling a regex literal from a division operator needs the
# parser's expectation of the next token, which a character scanner does not
# have, so a lone slash outside a comment is stepped over and a regex
# literal's interior stays visible. Four residuals follow from that. First,
# a quote character inside a regex literal opens a phantom string, and that
# phantom can cover real operator punctuation lying between it and a later
# quote, which lowers a count silently. Two limits a reader might expect are
# NOT there, both measured against _mask_cbrace_literals and pinned by
# TestRegexQuotePhantom. An odd number of quote characters on the line does
# not force the whole-file fallback: a trailing line comment swallows the
# unpaired quote before end-of-line, so the mask succeeds with a real
# boolean operator hidden, and that line's branch count drops from 2 to 1.
# Nor is the phantom held to one line: the quote alternative accepts a
# backslash followed by any character, the newline included, so a backslash
# in final position on the opening line carries the phantom onto the next
# line and hides real operator punctuation there, with the same shape
# repeatable to extend it further. Second, a doubled slash inside a regex
# literal reads as a line comment and masks the rest of that line, which
# lowers a count silently as well. Neither residual is guarded; both are
# recorded rather than fixed, and hardening the scanner against them is
# deferred to a slice that can carry its own differential re-measurement.
# Third, and unbounded: a star-slash sequence inside a regex literal's
# character contents reads as a block-comment opener, and the block-comment
# alternative's closing search crosses newlines, so it would otherwise pair
# with the next real block comment anywhere later in the source and blank
# every line between the two.
# The scanner guards against this one directly: once a bare slash has been
# stepped over on the current source line, a later star-slash sequence on
# that same line is refused rather than treated as a comment opener, and the
# whole scan fails toward raw text instead of silently under-counting. Fourth,
# also unbounded: a backtick inside a regex literal's character contents
# reads as a template-literal opener, and the template alternative's closing
# search crosses newlines with no escape needed, so it would otherwise pair
# with the next real backtick anywhere later in the source and blank every
# line between the two, exactly as the star-slash shape above does. The
# scanner guards against this one the same way: once a bare slash has been
# stepped over on the current source line, a later backtick on that same
# line is refused rather than treated as a template-literal opener, and the
# whole scan fails toward raw text instead. Both guards are verified by a
# dedicated test rather than a repo sweep, because a sweep can only bound
# occurrences that already exist, not ones a later file introduces. Measured
# at the time this landed, the sweep of regex-literal
# uses in this repo surfaced none containing a quote character, every
# doubled slash the scanner treated as a line comment was a genuine trailing
# comment after a properly closed regex literal, and the scanner closes every
# construct it recognises in every brace source here. The sweeping greps
# behind those statements are recorded in the slice report.

_CB_FLAT_RE = re.compile(
    r"//[^\n]*"
    r"|/\*[\s\S]*?\*/"
    r"|'(?:\\[\s\S]|[^'\\\n])*'"
    r'|"(?:\\[\s\S]|[^"\\\n])*"'
)
_CB_OPENERS = "/'\""
_CB_TPL_RE = re.compile(r"\\[\s\S]|\$\{|`")
_CB_DEPTH = {"{": 1, "}": -1}


def _cb_flat_step(text, pos, stop, slash_since_newline):
    """One scanner step at a comment or a quote opener: (next_pos, spans,
    slash_since_newline) once the flat regex closed the construct, else None
    to fail toward raw text. A lone slash is division or a regex literal, so
    it is stepped over and remembered for the rest of the line. A star-slash
    match reached after such a lone slash on the same line is refused rather
    than treated as a block-comment opener, since its unbounded closing
    search would otherwise pair with a real block comment far later in the
    file and blank real code in between; refusing sends the whole scan back
    to raw text instead. (PURE)"""
    is_block_open = text.startswith("/*", pos)
    if slash_since_newline and is_block_open:
        return None
    m = _CB_FLAT_RE.match(text, pos, stop)
    if m is not None:
        return m.end(), [(m.start(), m.end())], slash_since_newline
    if text[pos] == "/" and not is_block_open:
        return pos + 1, [], True
    return None


def _cb_step(text, pos, stop, slash_since_newline):
    """One scanner step from `pos`: (next_pos, mask_spans,
    slash_since_newline), else None to fail toward raw text. The
    lone-slash memory resets at the newline that ends its line. A backtick
    reached after a lone slash on the same line is refused rather than
    treated as a template-literal opener, mirroring the star-slash guard in
    `_cb_flat_step`: its closing search would otherwise cross newlines and
    pair with a real backtick far later in the file, blanking real code in
    between; refusing sends the whole scan back to raw text instead. (PURE)"""
    ch = text[pos]
    if ch == "\n":
        return pos + 1, [], False
    if ch == "`":
        if slash_since_newline:
            return None
        got = _cb_template_step(text, pos, stop)
        if got is None:
            return None
        nxt, spans = got
        return nxt, spans, slash_since_newline
    if ch in _CB_OPENERS:
        return _cb_flat_step(text, pos, stop, slash_since_newline)
    return pos + 1, [], slash_since_newline


def _cbrace_spans(text, start, stop):
    """The mask spans over text[start:stop] as half-open (begin, end)
    character ranges covering comment and string content, else None once a
    construct never closes, which sends the caller back to raw text.
    (PURE)"""
    spans = []
    pos = start
    slash_since_newline = False
    while pos < stop:
        got = _cb_step(text, pos, stop, slash_since_newline)
        if got is None:
            return None
        pos, found, slash_since_newline = got
        spans.extend(found)
    return spans


def _cb_depth_delta(text, pos, got):
    """The brace-depth change one scanner step makes: nonzero only on a plain
    code character, so braces inside a literal or a comment are ignored.
    (PURE)"""
    plain = (got[0] == pos + 1) and not got[1]
    if not plain:
        return 0
    return _CB_DEPTH.get(text[pos], 0)


def _cb_interp_end(text, start, stop):
    """The index just past the brace closing the ${ that opens at `start`,
    paired with the mask spans found inside it, else None. Nested literals
    and comments are stepped over with the same scanner, so a brace inside
    one does not close the interpolation; their spans are returned here so
    the caller reuses this single walk rather than repeating it. (PURE)"""
    depth = 1
    pos = start + 2
    spans = []
    slash_since_newline = False
    while pos < stop:
        got = _cb_step(text, pos, stop, slash_since_newline)
        if got is None:
            return None
        depth += _cb_depth_delta(text, pos, got)
        if depth == 0:
            return pos + 1, spans
        spans.extend(got[1])
        pos, _found, slash_since_newline = got
    return None


def _cb_template_hop(text, m, stop, chunk):
    """The scanner state after one non-closing hit inside a template literal:
    (next_pos, next_chunk_start, spans). A backslash escape masks straight
    through. A ${ ends the current masked chunk, scans the interpolation as
    ordinary code, and restarts the chunk past its closing brace.
    (None, None, []) once the interpolation never closes. (PURE)"""
    if m.group(0) != "${":
        return m.end(), chunk, []
    got = _cb_interp_end(text, m.start(), stop)
    if got is None:
        return None, None, []
    end, inner = got
    return end, end, [(chunk, m.start())] + inner


def _cb_template_step(text, pos, stop):
    """The whole template literal opening at the backtick at `pos`:
    (next_pos, mask_spans). Literal content is masked and every ${...}
    interpolation is scanned as ordinary code, so real operators inside one
    stay visible. None once the literal never closes. (PURE)"""
    spans = []
    chunk = pos
    m = _CB_TPL_RE.search(text, pos + 1, stop)
    while m is not None:
        if m.group(0) == "`":
            spans.append((chunk, m.end()))
            return m.end(), spans
        nxt, chunk, inner = _cb_template_hop(text, m, stop, chunk)
        if nxt is None:
            return None
        spans.extend(inner)
        m = _CB_TPL_RE.search(text, nxt, stop)
    return None


# The fill preserves the newline and the two brace characters. Line count and
# line lengths matter because a masked body must cover exactly the same lines
# as its raw body, and brace positions matter because _cognitive_approx's
# brace-language arm derives its nesting level from the brace counts it sees
# on the masked text: dropping a brace out of a literal could RAISE the
# weight of every following line, and the mask is only ever allowed to lower
# a count. Neither character carries a branch word or operator punctuation,
# so preserving both is measurement-neutral. Same shape as the reason the
# sentinel is non-whitespace.
_CB_PRESERVED = "\n{}"


def _cb_masked_char(ch):
    """The mask character of one source character: the newline and the two
    brace characters survive, everything else becomes the sentinel.
    (PURE)"""
    if ch in _CB_PRESERVED:
        return ch
    return _SCAN_SENTINEL


def _mask_cbrace_literals(text):
    """`text` with comment and string content replaced by the non-whitespace
    sentinel, preserving line count, line lengths and brace positions, else
    None to fall back to the raw text. Code inside a ${} interpolation stays
    visible. (PURE)"""
    spans = _cbrace_spans(text, 0, len(text))
    if spans is None:
        return None
    chars = list(text)
    for begin, end in spans:
        chars[begin:end] = [_cb_masked_char(ch) for ch in chars[begin:end]]
    masked = "".join(chars)
    if _mask_lost_too_much(text.split("\n"), masked.split("\n")):
        return None
    return masked


def _mask_for_lang(text, lang):
    """The masked form of `text` in one SCAN language, else None once no mask
    applies. Keyed by the value _scan_lang_for produces, never by the
    extraction family. (PURE)"""
    if lang == "python":
        return _mask_python_literals(text)
    if lang == "js":
        return _mask_cbrace_literals(text)
    return None


def _strip_for_scan(text, lang):
    """`text` with string-literal and comment content masked out, so words and
    punctuation inside literals stop being measured as real branching. Python
    is masked via stdlib tokenize, the JS/TypeScript family via the hand
    scanner that keeps ${} interpolation code visible. Every other language
    family, plus every mask failure, returns the raw text. (PURE)"""
    masked = _mask_for_lang(text, lang)
    if masked is None:
        return text
    return masked


def _branch_count(text):
    """Cyclomatic branch count for a block of code (PURE): 1 base path plus one
    per branch keyword / boolean operator / ternary occurrence."""
    return (1
            + len(_BRANCH_WORD_RE.findall(text))
            + len(_BRANCH_OPS_RE.findall(text)))


def _extract_functions_python(lines):
    """Split python source (list of lines, 0-based) into functions by indent.
    Returns [{name, start, end, header_idx}] with 1-based inclusive line spans.
    A function's body runs to the LAST non-blank line more-indented than its
    `def`; trailing blank lines (and the blank gap before the next definition)
    are excluded so a function's span never spuriously reaches into the changed
    range of the following function."""
    funcs = []
    for i, line in enumerate(lines):
        m = _PY_DEF_RE.match(line)
        if not m:
            continue
        indent = len(line) - len(line.lstrip())
        last_body = i  # header itself, if the body turns out empty
        for j in range(i + 1, len(lines)):
            nxt = lines[j]
            if not nxt.strip():
                continue
            if len(nxt) - len(nxt.lstrip()) <= indent:
                break
            last_body = j
        funcs.append({"name": m.group(1), "start": i + 1, "end": last_body + 1,
                      "header_idx": i})
    return funcs


def _extract_functions_cbrace(lines, ext=""):
    """Split brace-language source into functions by matching the brace that
    opens each detected signature. Returns [{name, start, end, header_idx}] with
    1-based inclusive spans. Best-effort: a signature whose opening brace can't
    be balanced is skipped. `ext` is the file's extension, used only to scope
    the per-language reserved words in _looks_like_call_or_control; it defaults
    to "" so a caller with no path gets the global words alone."""
    funcs = []
    text_by_line = lines
    for i, line in enumerate(lines):
        name = None
        m = _CBRACE_DEF_RE.search(line)
        if m and not _looks_like_call_or_control(ext, m, funcs, i + 1):
            name = m.group(1)
        else:
            am = _CBRACE_ARROW_RE.search(line)
            if am:
                name = am.group(1)
        if not name:
            continue
        end = _match_brace_end(text_by_line, i)
        if end is None:
            continue
        funcs.append({"name": name, "start": i + 1, "end": end + 1,
                      "header_idx": i})
    return funcs


# The 9 words below are reserved in EVERY brace language this analyzer reads,
# so they stay global. `foreach`/`using`/`lock`/`fixed` (C#) and
# `synchronized` (Java) are reserved only in their own language -- a .js class
# may legitimately define a method named `lock`, and measured on a fixture
# with methods named lock/fixed/using, adding those words globally drops all
# three real functions from the report. They are therefore keyed by EXTENSION,
# not by the "cbrace" family, which .ts and .cs share.
_CONTROL_WORDS = {"if", "for", "while", "switch", "catch", "else", "do",
                  "return", "case"}
_CONTROL_WORDS_BY_EXT = {
    ".cs": frozenset({"foreach", "using", "lock", "fixed"}),
    ".java": frozenset({"synchronized"}),
}


def _control_words_for(ext):
    """The extra reserved words for one file extension (a frozenset, possibly
    empty). `ext` is a leading-dot extension; None, "" and any unknown
    extension yield the empty set. (PURE)"""
    return _CONTROL_WORDS_BY_EXT.get((ext or "").lower(), frozenset())


def _encloses_line(funcs, line_no):
    """True if any already-collected function record contains `line_no`.
    `funcs` is a list of {name, start, end, header_idx} records whose
    start/end are 1-BASED INCLUSIVE; `line_no` is 1-based. (PURE)"""
    return any(fn["start"] <= line_no <= fn["end"] for fn in funcs)


def _looks_like_call_or_control(ext, match, funcs, line_no):
    """True if the C-family signature match is really a control keyword
    (`if (...) {`) rather than a definition, so the caller should not record it
    as a function. `ext` is the file's extension, `match` the _CBRACE_DEF_RE
    match, `funcs` the records collected so far and `line_no` the match's
    1-based line.

    A globally reserved word is always rejected. A per-extension word is
    rejected ONLY when an already-collected record encloses `line_no`, i.e.
    when the real enclosing method was itself extracted and the phantom is
    redundant. When nothing encloses it the phantom is the sole measurement of
    that method body -- measured on a C# method whose brace sits on its own
    line, dropping it takes the file from a reported cyclomatic 5 / cognitive 8
    to no function measurement at all -- so it is deliberately kept. That is an
    over-count, the one direction this heuristic is allowed to move. (PURE)"""
    word = match.group(1)
    if word in _CONTROL_WORDS:
        return True
    return word in _control_words_for(ext) and _encloses_line(funcs, line_no)


def _match_brace_end(lines, header_idx):
    """Return the 0-based index of the line holding the closing brace that
    balances the first `{` at/after header_idx, or None. PURE over `lines`."""
    depth = 0
    seen_open = False
    for j in range(header_idx, len(lines)):
        for ch in lines[j]:
            if ch == "{":
                depth += 1
                seen_open = True
            elif ch == "}":
                depth -= 1
                if seen_open and depth == 0:
                    return j
    return None


def _nesting_depth_python(body_lines, base_indent):
    """Max block-nesting depth of a python function body by indentation, in
    4-space-equivalent steps beyond the def's own indent. PURE."""
    max_depth = 0
    for line in body_lines:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        depth = max(0, (indent - base_indent)) // 4
        max_depth = max(max_depth, depth)
    return max_depth


def _nesting_depth_braces(body_text):
    """Max brace-nesting depth of a function body (PURE). The signature's own
    opening brace is depth 1; we report the deepest additional nesting."""
    depth = 0
    max_depth = 0
    for ch in body_text:
        if ch == "{":
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == "}":
            depth = max(0, depth - 1)
    return max(0, max_depth - 1)


def _cognitive_approx(body_text_or_lines, lang, base_indent):
    """A nesting-weighted cognitive-complexity APPROXIMATION (PURE). Each branch
    keyword contributes 1 + its nesting level, so deeply-nested control flow is
    penalised more heavily than flat control flow -- the spirit of cognitive
    complexity without claiming parity with a real analyzer. ONLY the builtin
    path ever produces this metric."""
    score = 0
    if lang == "python":
        for line in body_text_or_lines:
            stripped = line.strip()
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip(" "))
            level = max(0, (indent - base_indent)) // 4
            hits = (len(_BRANCH_WORD_RE.findall(stripped))
                    + len(_BRANCH_OPS_RE.findall(stripped)))
            score += hits * (1 + level)
    else:
        depth = 0
        for line in body_text_or_lines:
            hits = (len(_BRANCH_WORD_RE.findall(line))
                    + len(_BRANCH_OPS_RE.findall(line)))
            score += hits * (1 + max(0, depth))
            depth += line.count("{") - line.count("}")
            depth = max(0, depth)
    return score


def _nonblank(lines):
    return sum(1 for line in lines if line.strip())


def _extract_functions_for(lines, lang, ext=""):
    """The extracted callables of one file, by language family. `ext` scopes
    the brace extractor's per-language reserved words; the python branch
    ignores it. (PURE)"""
    if lang == "python":
        return _extract_functions_python(lines)
    return _extract_functions_cbrace(lines, ext)


def _nesting_depth_for(body_lines, lang, base_indent):
    """Nesting depth of one RAW function body, by language family. Always
    measured on raw text: the mask is for branch scanning only. (PURE)"""
    if lang == "python":
        return _nesting_depth_python(body_lines[1:], base_indent)
    return _nesting_depth_braces("\n".join(body_lines))


def _scan_lines_for(source, scan_lang, lines):
    """The masked counterpart of `lines`, for the two branch scans only. Falls
    back to `lines` unless the mask preserved the physical line count exactly,
    so a masked body always covers the same lines as its raw body. The
    language here is the SCAN language from _scan_lang_for, not the extraction
    family. (PURE)"""
    scan_lines = _strip_for_scan(source, scan_lang).splitlines()
    if len(scan_lines) != len(lines):
        return lines
    return scan_lines


def _function_metrics(lines, scan_lines, fn, lang):
    """Measured metric values for one extracted function. `lines` is raw source;
    `scan_lines` is its masked counterpart, read by the two branch scans alone,
    so span, indentation and length metrics all stay on raw text. (PURE)"""
    body_lines = lines[fn["header_idx"]:fn["end"]]
    scan_body = scan_lines[fn["header_idx"]:fn["end"]]
    header_line = lines[fn["header_idx"]]
    base_indent = len(header_line) - len(header_line.lstrip(" "))
    return {
        "cyclomatic_complexity": _branch_count("\n".join(scan_body)),
        "method_lines": _nonblank(body_lines),
        "parameter_count": _count_params(header_line),
        "cognitive_complexity": _cognitive_approx(
            scan_body, lang, base_indent),
        "nesting_depth": _nesting_depth_for(body_lines, lang, base_indent),
    }


def analyze_builtin(path, source, changed_ranges):
    """Pure-stdlib heuristic analysis of one changed file. Returns
    (function_findings, class_finding_or_None) where each finding is a dict of
    measured metric values for functions intersecting `changed_ranges`, tagged
    source="builtin-heuristic". `source` is the file text; changed_ranges is the
    file's list of (start, end) changed spans. The two branch scans read a
    masked copy of the source (see _strip_for_scan); the mask is selected by
    _scan_lang_for, so a brace language outside the JS family keeps its raw
    text. Every other metric reads the raw text.

    An unsupported/binary file (no known language) yields ([], None); the caller
    records a skip for it."""
    lang = _lang_for(path)
    if lang is None:
        return [], None
    lines = source.splitlines()
    scan_lines = _scan_lines_for(source, _scan_lang_for(path), lines)
    funcs = _extract_functions_for(
        lines, lang, os.path.splitext(path)[1].lower())

    findings = []
    for fn in funcs:
        if not _intersects_changed(fn["start"], fn["end"], changed_ranges):
            continue
        findings.append({
            "file": path, "function": fn["name"],
            "line_start": fn["start"], "line_end": fn["end"],
            "metrics": _function_metrics(lines, scan_lines, fn, lang),
        })

    class_finding = None
    if any(_spans_overlap(1, len(lines), cs, ce) for cs, ce in changed_ranges):
        class_finding = {"file": path, "class_lines": _nonblank(lines)}
    return findings, class_finding


# --------------------------------------------------------------------------
# Coverage (for CRAP)
# --------------------------------------------------------------------------

_COVERAGE_CANDIDATES = ("coverage.xml", "lcov.info")


def find_coverage(explicit, repo_dir):
    """Resolve a coverage report path: the explicit --coverage first, else probe
    the repo root for coverage.xml / lcov.info / cobertura*.xml. Returns an
    absolute path or None."""
    if explicit:
        return explicit if os.path.exists(explicit) else None
    for name in _COVERAGE_CANDIDATES:
        cand = os.path.join(repo_dir, name)
        if os.path.exists(cand):
            return cand
    import glob
    for cand in sorted(glob.glob(os.path.join(repo_dir, "cobertura*.xml"))):
        return cand
    return None


def parse_coverage(path, repo_dir):
    """Parse a coverage report into {file: coverage_fraction} where fraction is
    covered_lines / total_lines in [0, 1]. Supports cobertura/coverage.xml (via
    xml.etree) and lcov.info (text). Returns {} on any parse failure so CRAP
    degrades to skipped rather than aborting the gate. File keys are normalised
    to repo-relative POSIX paths where possible."""
    if not path:
        return {}
    try:
        if path.endswith(".info"):
            return _parse_lcov(path, repo_dir)
        return _parse_cobertura(path, repo_dir)
    except (OSError, ET.ParseError):
        return {}


def _norm_cov_path(filename, repo_dir):
    """Normalise a coverage-report filename to a repo-relative POSIX path. A
    filename that is already relative is kept verbatim (only the separator is
    normalised); only an absolute path is relativised against repo_dir, so a
    relative report entry like `src/m.py` is not mangled into `../../src/m.py`."""
    filename = filename.replace("\\", "/")
    if not os.path.isabs(filename):
        return filename
    try:
        rel = os.path.relpath(filename, repo_dir)
    except ValueError:
        rel = filename
    return rel.replace("\\", "/")


def _parse_cobertura(path, repo_dir):
    tree = ET.parse(path)
    root = tree.getroot()
    out = {}
    for cls in root.iter("class"):
        filename = cls.get("filename")
        if not filename:
            continue
        total = covered = 0
        for ln in cls.iter("line"):
            total += 1
            if int(ln.get("hits", "0")) > 0:
                covered += 1
        if total:
            key = _norm_cov_path(filename, repo_dir)
            prev = out.get(key)
            frac = covered / total
            # Multiple <class> per file: keep the aggregate best-effort.
            out[key] = frac if prev is None else (prev + frac) / 2
    return out


def _parse_lcov(path, repo_dir):
    out = {}
    current = None
    total = covered = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("SF:"):
                current = _norm_cov_path(line[3:], repo_dir)
                total = covered = 0
            elif line.startswith("DA:") and current is not None:
                parts = line[3:].split(",")
                if len(parts) >= 2:
                    total += 1
                    try:
                        if int(parts[1]) > 0:
                            covered += 1
                    except ValueError:
                        pass
            elif line == "end_of_record" and current is not None:
                if total:
                    out[current] = covered / total
                current = None
    return out


def crap_score(complexity, coverage_fraction):
    """CRAP = comp^2 * (1 - coverage)^3 + comp. PURE. coverage_fraction in [0,1]."""
    uncovered = max(0.0, 1.0 - coverage_fraction)
    return complexity * complexity * (uncovered ** 3) + complexity


# --------------------------------------------------------------------------
# Measurement orchestration
# --------------------------------------------------------------------------

def _backend_records_by_file(records):
    """Group backend function records by their (normalised) file path."""
    by_file = {}
    for rec in records:
        by_file.setdefault(rec["file"].replace("\\", "/"), []).append(rec)
    return by_file


def _match_changed(records, changed_ranges):
    """Keep only backend records whose span intersects a changed range."""
    return [r for r in records
            if _intersects_changed(r["line_start"], r["line_end"],
                                    changed_ranges)]


def _skip_reason(path):
    """Why one changed file produced no function measurement. Returns the
    unsupported-extension reason when _lang_for(path) is None, otherwise the
    supported-but-empty reason.

    The second case used to produce NO record at all: the skip chain ended in
    `elif _lang_for(path) is None`, so a .cs or .rs file whose callables the
    signature detector could not see -- a pure-Allman C# file, for instance,
    where every brace sits on its own line -- vanished from the report rather
    than reporting that it had not been measured. (PURE)"""
    if _lang_for(path) is None:
        return "unsupported file type for analysis"
    return "no callable found by the builtin heuristic"


def measure(changed, repo_dir, backends):
    """Measure every changed file, preferring detected backends and falling back
    to the builtin heuristic per file. Returns (function_measurements,
    class_measurements, skipped, used_backends) where each function measurement
    is {file, function, metrics: {...}, source} and skipped is a list of
    {"metric"|"file", "reason"} entries. EVERY changed
    file that yielded no function measurement gets a `skipped` entry -- an
    unreadable file, an unsupported extension, or a supported extension whose
    callables the heuristic could not see (see _skip_reason) -- so a file can
    never leave the report silently unmeasured.

    A backend supplies cyclomatic_complexity / method_lines / parameter_count
    (lizard) or cyclomatic_complexity only (radon); every remaining metric for
    that function -- always cognitive_complexity, plus nesting_depth and any
    metric the backend omitted -- is filled from the builtin heuristic and
    tagged accordingly, so no metric is silently dropped and cognitive is never
    attributed to a tool."""
    files = sorted(changed)
    py_files = [f for f in files if f.endswith(".py")]

    lizard_recs = run_lizard(files, repo_dir) if "lizard" in backends else []
    radon_recs = (run_radon(py_files, repo_dir)
                  if "radon" in backends and not lizard_recs else [])
    lizard_by_file = _backend_records_by_file(lizard_recs)
    radon_by_file = _backend_records_by_file(radon_recs)

    used_backends = []
    if lizard_recs:
        used_backends.append("lizard")
    if radon_recs:
        used_backends.append("radon")

    func_measurements = []
    class_measurements = []
    skipped = []

    for path in files:
        try:
            with open(os.path.join(repo_dir, path), encoding="utf-8",
                      errors="replace") as fh:
                source = fh.read()
        except (OSError, IsADirectoryError):
            skipped.append({"file": path, "reason": "file not readable"})
            continue

        heur_funcs, heur_class = analyze_builtin(path, source, changed[path])
        heur_by_name = {(f["function"], f["line_start"]): f for f in heur_funcs}

        norm = path.replace("\\", "/")
        backend_recs = _match_changed(
            lizard_by_file.get(norm, []) or lizard_by_file.get(path, []),
            changed[path])
        if not backend_recs:
            backend_recs = _match_changed(
                radon_by_file.get(norm, []) or radon_by_file.get(path, []),
                changed[path])

        if backend_recs:
            func_measurements.extend(
                _merge_backend_and_heuristic(backend_recs, heur_funcs, norm))
        elif heur_funcs:
            for hf in heur_funcs:
                func_measurements.append({
                    "file": path, "function": hf["function"],
                    "metrics": hf["metrics"], "source": "builtin-heuristic",
                })
        else:
            skipped.append({"file": path, "reason": _skip_reason(path)})

        if heur_class is not None:
            class_measurements.append({
                "file": path, "class_lines": heur_class["class_lines"],
                "source": "builtin-heuristic",
            })

    return func_measurements, class_measurements, skipped, used_backends


def _nearest_heuristic(heur_funcs, name, line_start):
    """Find the heuristic finding for a backend function by name, preferring the
    one whose start line is closest (backends and the heuristic may disagree by
    a line or two). Returns None if no same-named heuristic finding exists."""
    candidates = [h for h in heur_funcs if h["function"] == name]
    if not candidates:
        return None
    return min(candidates, key=lambda h: abs(h["line_start"] - line_start))


def _merge_backend_and_heuristic(backend_recs, heur_funcs, norm_file):
    """Merge each backend record with its heuristic counterpart. The backend
    owns the metrics it measured (source=<backend>); cognitive_complexity and
    any metric the backend didn't supply come from the heuristic
    (source=builtin-heuristic). Returns per-function measurement dicts whose
    `metrics` map each carry a per-metric source."""
    merged = []
    for rec in backend_recs:
        heur = _nearest_heuristic(heur_funcs, rec["function"],
                                  rec["line_start"])
        heur_metrics = heur["metrics"] if heur else {}
        backend_name = "lizard" if "method_lines" in rec else "radon"
        metrics = {}
        sources = {}
        for metric in _FUNCTION_METRICS:
            if metric in rec and metric != "cognitive_complexity":
                metrics[metric] = rec[metric]
                sources[metric] = backend_name
            elif metric in heur_metrics:
                metrics[metric] = heur_metrics[metric]
                sources[metric] = "builtin-heuristic"
        merged.append({
            "file": norm_file, "function": rec["function"],
            "metrics": metrics, "metric_sources": sources,
            "source": backend_name,
        })
    return merged


# --------------------------------------------------------------------------
# Threshold evaluation + custom gates + CRAP assembly
# --------------------------------------------------------------------------

def _finding(file, function, metric, value, threshold, source):
    passed = value <= threshold
    return {
        "file": file, "function": function, "metric": metric,
        "value": value, "threshold": threshold, "pass": passed,
        "source": source,
    }


def evaluate(func_measurements, class_measurements, thresholds,
             coverage_map, coverage_available):
    """Turn measurements into findings, evaluating each against its threshold.
    Emits crap_score findings only where coverage data exists for the function's
    file. Returns (findings, skipped)."""
    findings = []
    skipped = []
    cognitive_skipped_note = False

    for fm in func_measurements:
        metrics = fm["metrics"]
        sources = fm.get("metric_sources", {})
        default_source = fm.get("source", "builtin-heuristic")
        for metric in _FUNCTION_METRICS:
            if metric not in thresholds:
                continue
            if metric not in metrics:
                if metric == "cognitive_complexity" and not cognitive_skipped_note:
                    skipped.append({
                        "metric": "cognitive_complexity",
                        "reason": "function unparseable by builtin heuristic",
                    })
                    cognitive_skipped_note = True
                continue
            source = sources.get(metric, default_source)
            findings.append(_finding(
                fm["file"], fm["function"], metric, metrics[metric],
                thresholds[metric], source))

    for cm in class_measurements:
        if "class_lines" in thresholds:
            findings.append(_finding(
                cm["file"], None, "class_lines", cm["class_lines"],
                thresholds["class_lines"], cm.get("source",
                                                  "builtin-heuristic")))

    if "crap_score" in thresholds:
        if not coverage_available:
            skipped.append({"metric": "crap_score",
                            "reason": "no coverage report"})
        else:
            _append_crap_findings(func_measurements, thresholds["crap_score"],
                                  coverage_map, findings, skipped)

    return findings, skipped


def _append_crap_findings(func_measurements, threshold, coverage_map, findings,
                          skipped):
    """Append a crap_score finding per changed function whose file has coverage
    data. Functions in files with no coverage entry are noted once as skipped."""
    noted_missing = set()
    for fm in func_measurements:
        comp = fm["metrics"].get("cyclomatic_complexity")
        if comp is None:
            continue
        cov = _coverage_for(fm["file"], coverage_map)
        if cov is None:
            if fm["file"] not in noted_missing:
                skipped.append({"metric": "crap_score",
                                "reason": f"no coverage for {fm['file']}"})
                noted_missing.add(fm["file"])
            continue
        value = round(crap_score(comp, cov), 2)
        source = fm.get("metric_sources", {}).get(
            "cyclomatic_complexity", fm.get("source", "builtin-heuristic"))
        findings.append(_finding(fm["file"], fm["function"], "crap_score",
                                 value, threshold, source))


def _coverage_for(path, coverage_map):
    """Look up a file's coverage fraction, tolerating path-normalisation drift by
    also matching on basename when an exact key miss occurs."""
    norm = path.replace("\\", "/")
    if norm in coverage_map:
        return coverage_map[norm]
    base = os.path.basename(norm)
    for key, val in coverage_map.items():
        if os.path.basename(key) == base:
            return val
    return None


def evaluate_custom_gates(custom_gates, func_measurements, class_measurements):
    """Evaluate metric-form custom gates against the measured values; list
    command-form gates in skipped (the skill runs those). A metric-form gate
    checks whether EVERY measured value for its metric is within threshold.
    Returns (findings, skipped)."""
    findings = []
    skipped = []
    measured = _all_metric_values(func_measurements, class_measurements)
    for gate in custom_gates:
        if not isinstance(gate, dict):
            continue
        name = gate.get("name", "custom")
        if "command" in gate:
            skipped.append({"gate": name,
                            "reason": "command-form gate — evaluated by the "
                                      "skill"})
            continue
        metric = gate.get("metric")
        threshold = gate.get("threshold")
        if metric is None or threshold is None:
            skipped.append({"gate": name,
                            "reason": "malformed metric gate (needs metric + "
                                      "threshold)"})
            continue
        values = measured.get(metric)
        if not values:
            skipped.append({"gate": name,
                            "reason": f"metric {metric!r} not measured"})
            continue
        for file, function, value, source in values:
            f = _finding(file, function, metric, value, threshold, source)
            f["gate"] = name
            findings.append(f)
    return findings, skipped


def _all_metric_values(func_measurements, class_measurements):
    """Index measured values by metric name for custom-gate lookup:
    {metric: [(file, function, value, source), ...]}."""
    out = {}
    for fm in func_measurements:
        default_source = fm.get("source", "builtin-heuristic")
        sources = fm.get("metric_sources", {})
        for metric, value in fm["metrics"].items():
            out.setdefault(metric, []).append(
                (fm["file"], fm["function"], value,
                 sources.get(metric, default_source)))
    for cm in class_measurements:
        out.setdefault("class_lines", []).append(
            (cm["file"], None, cm["class_lines"],
             cm.get("source", "builtin-heuristic")))
    return out


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------

def build_report(base, head, config_source, backends, findings, skipped,
                 changed_files=0):
    """Assemble the single JSON report. summary.pass is True iff every finding
    passed; summary.failures lists the failing findings verbatim.

    summary.vacuous marks a pass earned by measuring NOTHING over a non-empty
    diff (zero checks, one or more changed files). Such a pass is not evidence
    that the code meets the bar — files may have been unreadable, or no
    function matched the changed ranges — and callers gating a code-changing
    range must treat it as unmeasured, not as green (run 20260807 Phase 5
    accepted-then-caught exactly this by hand)."""
    failures = [f for f in findings if not f["pass"]]
    return {
        "version": 1,
        "backends": backends,
        "base": base,
        "head": head,
        "config": config_source,
        "findings": findings,
        "skipped": skipped,
        "summary": {
            "pass": not failures,
            "failures": failures,
            "checks": len(findings),
            "vacuous": not failures and not findings and changed_files > 0,
        },
    }


def run_gate(args):
    """Full gate run: load config (honouring enabled=false), discover changed
    code, measure it, evaluate thresholds + custom gates + CRAP, and return the
    report dict. Raises GateError (exit 2) for git/config failures."""
    config, config_source = load_config(args.config, getattr(args, "overlay", None))
    if not config.get("enabled", True):
        return {"skipped": "gate disabled"}, config_source

    changed = git_changed_ranges(args.base, args.head, args.repo_dir)
    thresholds = config["thresholds"]

    backends = []
    if _lizard_available():
        backends.append("lizard")
    if _radon_available():
        backends.append("radon")

    func_m, class_m, measure_skips, used_backends = measure(
        changed, args.repo_dir, backends)

    coverage_path = find_coverage(args.coverage, args.repo_dir)
    coverage_map = parse_coverage(coverage_path, args.repo_dir)
    coverage_available = bool(coverage_map)

    findings, eval_skips = evaluate(
        func_m, class_m, thresholds, coverage_map, coverage_available)
    custom_findings, custom_skips = evaluate_custom_gates(
        config["custom_gates"], func_m, class_m)

    report = build_report(
        args.base, args.head, config_source,
        used_backends or (["builtin-heuristic"] if changed else []),
        findings + custom_findings,
        measure_skips + eval_skips + custom_skips,
        changed_files=len(changed))
    return report, config_source


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Objective code-quality gate for a spec-loop slice.")
    ap.add_argument("--config", help="path to quality-gate.json (defaults used "
                                     "if absent)")
    ap.add_argument("--overlay", help="per-repo overlay (.spec-loop/quality-gate.json) "
                                      "deep-merged over --config")
    ap.add_argument("--print-config", action="store_true",
                    help="print the effective merged config as JSON and exit 0 "
                         "(the one door to tier3_surfaces/models for callers)")
    ap.add_argument("--base", help="base ref of the slice diff")
    ap.add_argument("--head", default="HEAD", help="head ref (default HEAD)")
    ap.add_argument("--repo-dir", default=".", help="repo/worktree to measure")
    ap.add_argument("--coverage", help="coverage report path (for CRAP)")
    args = ap.parse_args(argv)

    if args.print_config:
        try:
            config, source = load_config(args.config, args.overlay)
        except GateError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"config": config, "source": source},
                         ensure_ascii=False, indent=2))
        return 0

    if not args.base:
        ap.error("--base is required unless --print-config is given")

    try:
        report, _ = run_gate(args)
    except GateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if "skipped" in report and report.get("skipped") == "gate disabled":
        return 0
    return 0 if report["summary"]["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
