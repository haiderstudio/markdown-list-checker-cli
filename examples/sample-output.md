== good.md: consistent lists, passes ==
examples/good.md: lists OK
OK — 1 file(s) checked, all lists are consistent.

== bad.md: mixed markers, bad indents, mixed types ==
FAIL examples/bad.md:5: list mixes bullet markers: '-' and '*' — use one marker per list
FAIL examples/bad.md:9: bad indent: item is indented 3 spaces, but this list nests by 2 spaces
FAIL examples/bad.md:11: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:12: list mixes ordered and unordered items — use one type per list
FAIL examples/bad.md:18: bad indent: 3 spaces does not match any level in this list
Checked 1 file(s), 5 problem(s) in 1 file(s).

== fenced.md: a broken list inside a code block is skipped ==
examples/fenced.md: lists OK
OK — 1 file(s) checked, all lists are consistent.

== examples/: a folder walk, six problems ==
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
