#!/usr/bin/env python3
"""Check Markdown lists are consistent, fail CI on a broken list.

Run: python3 src/markdown_list_checker.py examples/good.md
     python3 src/markdown_list_checker.py examples/
     python3 src/markdown_list_checker.py --json examples/bad.md

The problem is quiet: a list that mixes `-` and `*`
markers, or nests some items by two spaces and others
by three, renders as two lists, or as flat text — and
the writer only finds out when a reader complains. This
tool reads each Markdown file, finds its lists, checks
that one list uses one bullet marker and one nesting
width, reports every mixed marker and bad indent with
its file and line number, and exits 1 when any problem
is found, so it can fail a CI run. A clean file exits 0.

What counts as a list here, in plain terms:

- A list item is a line starting with a bullet marker
  (`-`, `*`, or `+`) or an ordered marker (`1.`, `2)`,
  and so on), followed by a space. A line like `-item`
  with no space after the marker is not a list item,
  and neither is a line of dashes used as a horizontal
  rule (`---`, or `- - -`).
- A list is a run of list items. Blank lines between
  items do not split a list, but any other line — a
  paragraph, a heading — ends it, and a new list starts
  after it.
- One marker per list, at each level: the first item at
  a level sets that level's marker. A later item at the
  same level with a different bullet (`-` then `*`), a
  different ordered delimiter (`1.` then `2)`), or a
  different kind (ordered among unordered) is one
  problem. A nested list under a different parent may
  use its own marker — a nested ordered list under a
  bullet item is normal, and is not flagged.
- One nesting width per list: the first nested item
  sets the step — how many spaces deeper a nested item
  sits. Every nested item must sit at a multiple of
  that step from the list's base indent. A list that
  nests some items by 2 spaces and others by 3 is
  flagged, even though both render — pick one width
  and use it everywhere. An item whose indent matches
  no level in the list is one problem.
- Lists inside fenced code blocks are skipped — they
  are examples, not lists. Lists inside blockquotes
  (`> - item`) are not checked.
- A line indented by 4 or more spaces when no list is
  running is an indented code block, not a list item,
  so a code example that looks like a list is skipped.
  Inside a running list, an indented item is a nested
  item and is checked.
- An ordered item numbered other than 1 can only start
  a list after a blank line, a heading, or a fenced
  block — a line like `2. apples` in the middle of a
  paragraph is ordinary prose, not a list. A `1.` item
  can start a list anywhere, and any number can
  continue a list that is already running. List
  numbering itself is never checked: Markdown renders
  `1.`, `5.`, `9.` as 1, 2, 3, so the numbers do not
  matter.

It never rewrites a file. It is report-only and runs
fully offline: it sends nothing anywhere and needs no
API key.

Exit codes: 0 when every list is consistent, 1 when
any problem is found, 2 for a usage or input problem (a
missing path, a bad flag, a bad --exclude value, or no
Markdown file to check).

Python standard library only.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

MARKDOWN_EXTENSIONS = {".md", ".markdown"}

_ITEM = re.compile(r"^([ \t]*)([-*+]|\d+[.)])(?:[ \t]+|$)")
_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^#{1,6}(?:[ \t]+|$)")
_THEMATIC_BREAK = re.compile(r"^([-*_])(?:[ \t]*\1){2,}[ \t]*$")

# A list-looking line this far indented, with no list
# running, is an indented code block, not a list item.
_CODE_INDENT = 4


def _indent_width(leading):
    """Return the indent width of leading whitespace.

    A tab counts as 4 spaces, the way Markdown counts it.
    """
    return len(leading.expandtabs(4))


def parse_item(line):
    """Return (indent, kind, key, display) for a list item line.

    kind is "bullet" or "ordered". key is what must stay
    the same within one level: the bullet character for a
    bullet item, the delimiter ("." or ")") for an ordered
    item. display is the marker as shown in messages.
    Return None when the line is not a list item: no
    marker, no space after the marker, or a horizontal
    rule made of dashes or stars.
    """
    stripped = line.strip()
    if _THEMATIC_BREAK.match(stripped):
        return None
    match = _ITEM.match(line)
    if not match:
        return None
    leading, marker = match.group(1), match.group(2)
    if marker[0].isdigit():
        kind = "ordered"
        key = marker[-1]
        display = marker[-1]
    else:
        kind = "bullet"
        key = marker
        display = marker
    return (_indent_width(leading), kind, key, display)


def check_lines(lines):
    """Return the list problems in one file's lines.

    lines is a list of the file's lines in order. Each
    problem is a dict with "line" (the bad item's line
    number, starting at 1) and "reason". Lists inside
    fenced code blocks are skipped.
    """
    problems = []
    in_fence = False
    # A running list: its base indent, the nesting step
    # (None until the first nested item sets it), and a
    # stack of (indent, kind, key, display) frames, one
    # per level, deepest last.
    active = False
    base = 0
    step = None
    stack = []
    # An ordered item numbered other than 1 can only
    # start a list after a blank line, a heading, a
    # fence, or the start of the file — after ordinary
    # prose it is a sentence, not a list.
    can_start_numbered = True

    for number, line in enumerate(lines, start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            can_start_numbered = True
            continue
        if in_fence:
            continue
        if not line.strip():
            can_start_numbered = True
            continue
        item = parse_item(line)
        if item is None:
            # Any other line ends the running list.
            active = False
            stack = []
            step = None
            can_start_numbered = bool(_HEADING.match(line))
            continue
        indent, kind, key, display = item
        if not active:
            if indent >= _CODE_INDENT:
                # Indented code, not a list item. A code
                # block is a block boundary, so a numbered
                # item after it can still start a list.
                can_start_numbered = True
                continue
            if kind == "ordered" and not can_start_numbered:
                number_text = line.lstrip().split(".", 1)[0].split(")", 1)[0]
                if number_text != "1":
                    # A numbered line inside prose.
                    can_start_numbered = False
                    continue
            active = True
            base = indent
            step = None
            stack = [(indent, kind, key, display)]
            can_start_numbered = False
            continue
        if indent < base:
            # Less indented than the list's base: the old
            # list ends and a new one starts here.
            active = True
            base = indent
            step = None
            stack = [(indent, kind, key, display)]
            can_start_numbered = False
            continue
        if indent > stack[-1][0]:
            # A nested item, one level deeper than the
            # item above it.
            if step is None:
                step = indent - base
            elif (indent - base) % step != 0:
                problems.append(
                    {
                        "line": number,
                        "reason": (
                            f"bad indent: item is indented "
                            f"{indent} spaces, but this list "
                            f"nests by {step} spaces"
                        ),
                    }
                )
            stack.append((indent, kind, key, display))
            can_start_numbered = False
            continue
        # Same level as the item above, or shallower.
        while len(stack) > 1 and stack[-1][0] > indent:
            stack.pop()
        if stack[-1][0] == indent:
            level_kind, level_key, level_display = (
                stack[-1][1],
                stack[-1][2],
                stack[-1][3],
            )
            if kind != level_kind:
                if kind == "ordered":
                    problems.append(
                        {
                            "line": number,
                            "reason": (
                                "list mixes ordered and "
                                "unordered items — use one "
                                "type per list"
                            ),
                        }
                    )
                else:
                    problems.append(
                        {
                            "line": number,
                            "reason": (
                                "list mixes unordered and "
                                "ordered items — use one "
                                "type per list"
                            ),
                        }
                    )
            elif key != level_key:
                if kind == "bullet":
                    problems.append(
                        {
                            "line": number,
                            "reason": (
                                f"list mixes bullet markers: "
                                f"'{level_display}' and "
                                f"'{display}' — use one "
                                f"marker per list"
                            ),
                        }
                    )
                else:
                    problems.append(
                        {
                            "line": number,
                            "reason": (
                                f"list mixes ordered markers: "
                                f"'{level_display}' and "
                                f"'{display}' — use one "
                                f"marker per list"
                            ),
                        }
                    )
        else:
            # Shallower than the level above, but matching
            # no level in the list.
            problems.append(
                {
                    "line": number,
                    "reason": (
                        f"bad indent: {indent} spaces does "
                        f"not match any level in this list"
                    ),
                }
            )
            stack.append((indent, kind, key, display))
        can_start_numbered = False
    return problems


def check_file(path):
    """Return (problems, skipped) for one Markdown file.

    skipped is always False — nothing is skipped, a file
    that cannot be read is a problem.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return (
            [{"line": 0, "reason": "not readable as UTF-8 text"}],
            False,
        )
    except OSError as exc:
        return (
            [{"line": 0, "reason": f"cannot read file: {exc.strerror}"}],
            False,
        )
    return check_lines(text.splitlines()), False


def _is_markdown(name):
    return Path(name).suffix.lower() in MARKDOWN_EXTENSIONS


def gather(paths, exclude, recursive):
    """Walk the given paths and return (entries, checked, skipped).

    entries is a list of (file, problem); checked is a list
    of one dict per file the tool tried, with file and
    problems; skipped is a list of files skipped by
    --exclude. A file passed on the command line is always
    checked, even if it matches --exclude and even if it
    has no Markdown extension. Inside a folder, only
    .md and .markdown files are checked.
    """
    entries = []
    checked = []
    skipped = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(raw)
        if path.is_file():
            problems, _was_skipped = check_file(path)
            checked.append({"file": str(path), "problems": problems})
            for problem in problems:
                entries.append((str(path), problem))
            continue
        if recursive:
            for dirpath, dirnames, filenames in _walk(path):
                for name in filenames:
                    if not _is_markdown(name):
                        continue
                    candidate = Path(dirpath) / name
                    if _excluded(candidate, path, exclude):
                        skipped.append(str(candidate))
                        continue
                    problems, _was_skipped = check_file(candidate)
                    checked.append(
                        {"file": str(candidate), "problems": problems}
                    )
                    for problem in problems:
                        entries.append((str(candidate), problem))
        else:
            for candidate in sorted(path.iterdir()):
                if not candidate.is_file():
                    continue
                if not _is_markdown(candidate.name):
                    continue
                if _excluded(candidate, path, exclude):
                    skipped.append(str(candidate))
                    continue
                problems, _was_skipped = check_file(candidate)
                checked.append(
                    {"file": str(candidate), "problems": problems}
                )
                for problem in problems:
                    entries.append((str(candidate), problem))
    return entries, checked, skipped


def _walk(root):
    """os.walk that never enters .git and never follows links."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        yield dirpath, dirnames, sorted(filenames)


def _excluded(candidate, root, patterns):
    name = candidate.name
    try:
        rel = str(candidate.relative_to(root))
    except ValueError:
        rel = name
    return any(
        fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern)
        for pattern in patterns
    )


def _format_problem(location, problem):
    return f"FAIL {location}:{problem['line']}: {problem['reason']}"


def _summary_line(checked, problems):
    total = len(problems)
    bad_files = len({f for f, _p in problems})
    if total:
        return (
            f"Checked {len(checked)} file(s), {total} "
            f"problem(s) in {bad_files} file(s)."
        )
    return (
        f"OK — {len(checked)} file(s) checked, "
        f"all lists are consistent."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="markdown-list-checker-cli",
        description="Check Markdown lists are consistent.",
    )
    parser.add_argument(
        "paths", nargs="*", help="files or folders to check"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read one Markdown file from standard input",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="skip files matching this glob (repeatable)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="do not walk into subfolders",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON (summary goes to stderr)",
    )
    parser.add_argument("--version", action="store_true", help="print the version")
    args = parser.parse_args(argv)

    if args.version:
        print(f"markdown-list-checker-cli {VERSION}")
        return 0

    entries = []
    checked = []
    skipped = []
    try:
        if args.paths:
            found, found_checked, found_skipped = gather(
                args.paths,
                args.exclude,
                not args.no_recursive,
            )
            entries.extend(found)
            checked.extend(found_checked)
            skipped.extend(found_skipped)
    except FileNotFoundError as exc:
        print(f"error: no such file or folder: {exc}", file=sys.stderr)
        return 2

    if args.stdin:
        text = sys.stdin.read()
        problems = check_lines(text.splitlines())
        checked.append({"file": "<stdin>", "problems": problems})
        for problem in problems:
            entries.append(("<stdin>", problem))

    if not checked:
        print("error: no Markdown files to check", file=sys.stderr)
        return 2

    problems = entries
    bad_files = len({f for f, _p in problems})
    total = len(problems)
    summary = _summary_line(checked, problems)

    if args.json:
        files = []
        for entry in checked:
            files.append(
                {
                    "file": entry["file"],
                    "problems": entry["problems"],
                }
            )
        result = {
            "files": files,
            "summary": {
                "checked": len(checked),
                "files_with_problems": bad_files,
                "problems": total,
                "skipped": len(skipped),
            },
        }
        print(json.dumps(result, indent=2))
        print(summary, file=sys.stderr)
        return 1 if problems else 0

    for entry in checked:
        if entry["problems"]:
            for problem in entry["problems"]:
                print(_format_problem(entry["file"], problem))
        else:
            print(f"{entry['file']}: lists OK")
    print(summary)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
