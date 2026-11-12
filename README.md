# markdown-list-checker-cli

Check Markdown lists are consistent, fail CI on a broken list.

[![CI](https://github.com/haiderstudio/markdown-list-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/markdown-list-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`markdown_list_checker` reads each Markdown file,
finds its lists, and checks they are consistent:

- A list that mixes `-` and `*` markers, or nests
  some items by two spaces and others by three,
  renders as two lists, or as flat text — and the
  writer only finds out when a reader complains. This
  tool reports every mixed marker and bad indent with
  its file and line number, and exits 1 when any
  problem is found — so it can fail a CI run. A clean
  file exits 0.
- One marker per list, at each level: the first item
  at a level sets that level's marker. A later item at
  the same level with a different bullet (`-` then
  `*`), a different ordered delimiter (`1.` then `2)`),
  or a different kind (ordered among unordered) is one
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
- A list is a run of list items. Blank lines between
  items do not split a list, but any other line — a
  paragraph, a heading — ends it, and a new list starts
  after it.
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
- A line like `-item` with no space after the marker
  is not a list item, and neither is a line of dashes
  used as a horizontal rule (`---`, or `- - -`).
- Files come from the command line (one or more), or
  from a folder walk: every `.md` and `.markdown` file
  under a folder, recursively by default
  (`--no-recursive` stops at the top level). `.git`
  folders are never walked, and directory links are
  never followed, so a link cycle cannot loop the
  check.
- `--exclude PATTERN` skips files by glob, for example
  `--exclude 'sub/nested.md'`. It can be repeated. A
  file passed directly on the command line is always
  checked, even if it matches an exclude pattern and
  even if it has no Markdown extension.
- `--stdin` reads one Markdown file from standard input.
- `--json` prints the result as machine-readable JSON
  (the summary goes to standard error, so standard
  output stays clean JSON).
- It is report-only and runs fully offline: it never
  rewrites a file, sends nothing anywhere, and needs no
  API key. Python standard library only.

## What it does NOT do

- It does not rewrite or tidy a Markdown list. A mixed
  marker or a bad indent is reported; fixing it is your
  job.
- It does not check links, headings, tables, or
  anything else in a Markdown file. This tool's one job
  is list shape.
- It does not check list numbering. Markdown renders
  any numbers in order, so `1.`, `5.`, `9.` is a
  perfectly good ordered list.
- It does not check lists inside blockquotes. A list
  quoted with `>` is left alone.
- It does not fetch anything from a live site. Every
  input is a local file or standard input.

## Who it is for

Every docs writer: a blogger adding a CI step that
fails the build when a list mixes markers or nests at
random widths, or anyone tidying a README before a
release. A broken list is invisible in the file itself
— this catches it before a reader sees it.

## How this differs from similar tools

The exact name `markdown-list-checker-cli` matches 0
repositories on GitHub (checked Nov 11, 2026), and the
wider field is nearly empty: `markdown list checker`
matches 7 repositories. The top ones are
gmperkinsmba/markdown-link-checker, 0 stars — broken
Markdown links (a different job);
abubakarsiddique360/Awesome-List-Checker, 1 star — a
linter for curated link lists (duplicate links,
unsorted entries — link lists, not bullet lists); the
rest are noise (a property due-diligence tool, a C#
symptom checker, an essay draft checker, an uptime
checker). No rival checks list shape. This tool does
one job: a Python standard-library-only CLI that checks
Markdown lists are consistent, reports each mixed
marker and bad indent with file and line, and exits 1
for CI — no install beyond Python, no website, no
network.

## Install

Python standard library only — no packages to download. You need
Python 3.8 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/markdown-list-checker-cli.git
cd markdown-list-checker-cli
python3 src/markdown_list_checker.py examples/good.md
```

```
examples/good.md: lists OK
OK — 1 file(s) checked, all lists are consistent.
```

## Usage

Check one clean file:

```
python3 src/markdown_list_checker.py examples/good.md
```

```
examples/good.md: lists OK
OK — 1 file(s) checked, all lists are consistent.
```

Check a file with broken lists — a mixed marker, two
bad indents, and two ordered items in a bullet list:

```
python3 src/markdown_list_checker.py examples/bad.md
```

```
FAIL examples/bad.md:5: list mixes bullet markers: '-' and '*' — use one marker per list
FAIL examples/bad.md:9: bad indent: item is indented 3 spaces, but this list nests by 2 spaces
FAIL examples/bad.md:11: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:12: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:18: bad indent: 3 spaces does not match any level in this list
Checked 1 file(s), 5 problem(s) in 1 file(s).
```

A broken list inside a code block is skipped:

```
python3 src/markdown_list_checker.py examples/fenced.md
```

```
examples/fenced.md: lists OK
OK — 1 file(s) checked, all lists are consistent.
```

Check a whole folder:

```
python3 src/markdown_list_checker.py examples/
```

```
FAIL examples/bad.md:5: list mixes bullet markers: '-' and '*' — use one marker per list
FAIL examples/bad.md:9: bad indent: item is indented 3 spaces, but this list nests by 2 spaces
FAIL examples/bad.md:11: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:12: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:18: bad indent: 3 spaces does not match any level in this list
examples/fenced.md: lists OK
examples/good.md: lists OK
examples/sample-output.md: lists OK
FAIL examples/sub/nested.md:5: list mixes bullet markers: '-' and '+' — use one marker per list
Checked 5 file(s), 6 problem(s) in 2 file(s).
```

Skip one file with `--exclude`:

```
python3 src/markdown_list_checker.py --exclude 'sub/nested.md' examples/
```

```
FAIL examples/bad.md:5: list mixes bullet markers: '-' and '*' — use one marker per list
FAIL examples/bad.md:9: bad indent: item is indented 3 spaces, but this list nests by 2 spaces
FAIL examples/bad.md:11: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:12: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:18: bad indent: 3 spaces does not match any level in this list
examples/fenced.md: lists OK
examples/good.md: lists OK
examples/sample-output.md: lists OK
Checked 4 file(s), 5 problem(s) in 1 file(s).
```

Check one file from standard input:

```
python3 src/markdown_list_checker.py --stdin < examples/bad.md
```

```
FAIL <stdin>:5: list mixes bullet markers: '-' and '*' — use one marker per list
FAIL <stdin>:9: bad indent: item is indented 3 spaces, but this list nests by 2 spaces
FAIL <stdin>:11: list mixes ordered and unordered items — use one type per list
FAIL <stdin>:12: list mixes ordered and unordered items — use one type per list
FAIL <stdin>:18: bad indent: 3 spaces does not match any level in this list
Checked 1 file(s), 5 problem(s) in 1 file(s).
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output stays clean JSON):

```
python3 src/markdown_list_checker.py --json examples/bad.md
```

```
{
  "files": [
    {
      "file": "examples/bad.md",
      "problems": [
        {
          "line": 5,
          "reason": "list mixes bullet markers: '-' and '*' \u2014 use one marker per list"
        },
        {
          "line": 9,
          "reason": "bad indent: item is indented 3 spaces, but this list nests by 2 spaces"
        },
        {
          "line": 11,
          "reason": "list mixes ordered and unordered items \u2014 use one type per list"
        },
        {
          "line": 12,
          "reason": "list mixes ordered and unordered items \u2014 use one type per list"
        },
        {
          "line": 18,
          "reason": "bad indent: 3 spaces does not match any level in this list"
        }
      ]
    }
  ],
  "summary": {
    "checked": 1,
    "files_with_problems": 1,
    "problems": 5,
    "skipped": 0
  }
}
```

Exit codes: 0 when every list is consistent, 1 when
any problem is found, 2 for a usage problem (no Markdown
files given, a bad flag, or a missing file or folder).

## Examples

### 1. A file with five broken lists

`examples/bad.md` holds a mixed bullet marker (line 5:
`*` among `-`), a nested item at 3 spaces where the
list nests by 2 (line 9), two ordered items inside a
bullet list (lines 11–12), and an item at 3 spaces that
matches no level in the list (line 18):

```
python3 src/markdown_list_checker.py examples/bad.md
```

```
FAIL examples/bad.md:5: list mixes bullet markers: '-' and '*' — use one marker per list
FAIL examples/bad.md:9: bad indent: item is indented 3 spaces, but this list nests by 2 spaces
FAIL examples/bad.md:11: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:12: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:18: bad indent: 3 spaces does not match any level in this list
Checked 1 file(s), 5 problem(s) in 1 file(s).
```

### 2. A broken list inside a code block is not a list

`examples/fenced.md` has a mixed-marker, badly
indented list inside a fenced code block — it is an
example, so the tool skips it and passes the file:

```
python3 src/markdown_list_checker.py examples/fenced.md
```

```
examples/fenced.md: lists OK
OK — 1 file(s) checked, all lists are consistent.
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks one clean file (pass), then the file
with broken lists (fail, on purpose), then the fenced
example (pass — the broken list inside the code block
is skipped), then the whole `examples/` folder (fail,
on purpose — it picks up the five problems in `bad.md`
plus the one in `examples/sub/nested.md`). Its full
output is in `examples/sample-output.md`, ending with
`Checked 5 file(s), 6 problem(s) in 2 file(s).` The
failing runs exit 1, which is the expected result — the
script ends with exit 0 so it can be run as a demo.

## How it is tested

Tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_markdown_list_checker.py
```

The tests cover: item parsing (each bullet marker,
ordered markers with both delimiters, no space after
the marker not an item, horizontal rules not items,
tab indents, empty items), list checks (clean lists,
mixed bullet markers, mixed ordered delimiters, mixed
list types, a bad nesting step, an indent matching no
level, a nested list under a different parent using
its own marker, a nested ordered list under bullets,
blank lines not splitting a list, a paragraph ending a
list, a less-indented item starting a new list, a
numbered line in prose not starting a list, a `1.`
item starting a list after prose, a numbered item
after a blank line or a heading starting a list,
fenced code blocks with backticks and tildes skipped,
an indented code block skipped, two lists both
checked, empty input, no lists), file checks (clean
file, bad file, missing file, non-UTF-8 file, input
file left unchanged), folder walking (a direct file
always checked, only Markdown files inside a folder,
`.git` never walked, `--no-recursive`, `--exclude`, a
direct file checked even if excluded, missing path),
the CLI (exit 0/1/2, each flag, `--stdin` good and bad,
`--json` output, `--version`, bad flags, missing paths,
empty folders), the bundled examples (sample output
compared byte-for-byte against a fresh run, and the
README-quoted outputs checked against it), and hygiene
checks (no placeholder text, no absolute paths, stdlib
imports only, `.env` first in `.gitignore`, CI file
runs the test file). The tests pass from any working
directory, not just the repo root.

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking Markdown lists is not new — the
similar tools named above (the broken-link checker and
the curated link-list linter) are listed in "How this
differs" — but every line of code here is original, and
the tool builds on nothing but Python's standard
library.
