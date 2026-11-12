#!/usr/bin/env python3
"""Tests for markdown-list-checker-cli.

Standard library unittest only. Run from the repo root:

    python3 tests/test_markdown_list_checker.py

or:

    python3 -m unittest discover -s tests

The tests pass from any working directory, not just the
repo root: every path is built from this file's own
location, and the CLI is run with its working directory
pinned to the repo root.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "markdown_list_checker.py"
sys.path.insert(0, str(ROOT / "src"))

import markdown_list_checker as tool  # noqa: E402


def run_cli(*args, stdin_text=None):
    """Run the tool as a subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(SRC), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return result.returncode, result.stdout, result.stderr


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestParseItem(unittest.TestCase):
    def test_dash_bullet(self):
        self.assertEqual(
            tool.parse_item("- item"), (0, "bullet", "-", "-")
        )

    def test_star_bullet(self):
        self.assertEqual(
            tool.parse_item("* item"), (0, "bullet", "*", "*")
        )

    def test_plus_bullet(self):
        self.assertEqual(
            tool.parse_item("+ item"), (0, "bullet", "+", "+")
        )

    def test_indented_bullet(self):
        self.assertEqual(
            tool.parse_item("  - item"), (2, "bullet", "-", "-")
        )

    def test_tab_indent_counts_four(self):
        self.assertEqual(
            tool.parse_item("\t- item"), (4, "bullet", "-", "-")
        )

    def test_ordered_dot(self):
        self.assertEqual(
            tool.parse_item("1. item"), (0, "ordered", ".", ".")
        )

    def test_ordered_paren(self):
        self.assertEqual(
            tool.parse_item("12) item"), (0, "ordered", ")", ")")
        )

    def test_no_space_after_marker_not_an_item(self):
        self.assertIsNone(tool.parse_item("-item"))

    def test_dashes_not_an_item(self):
        self.assertIsNone(tool.parse_item("---"))

    def test_spaced_dashes_not_an_item(self):
        self.assertIsNone(tool.parse_item("- - -"))

    def test_stars_not_an_item(self):
        self.assertIsNone(tool.parse_item("***"))

    def test_plain_text_not_an_item(self):
        self.assertIsNone(tool.parse_item("plain text"))

    def test_bare_marker_is_an_item(self):
        self.assertEqual(
            tool.parse_item("-"), (0, "bullet", "-", "-")
        )

    def test_decimal_not_an_item(self):
        self.assertIsNone(tool.parse_item("2.5 things"))


class TestCheckLines(unittest.TestCase):
    def test_clean_bullets(self):
        self.assertEqual(tool.check_lines(["- a", "- b"]), [])

    def test_clean_ordered(self):
        self.assertEqual(tool.check_lines(["1. a", "2. b"]), [])

    def test_clean_nested_two_spaces(self):
        lines = ["- a", "  - b", "  - c", "- d"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_clean_deep_nesting(self):
        lines = ["- a", "  - b", "    - c", "      - d"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_clean_task_list(self):
        self.assertEqual(
            tool.check_lines(["- [ ] a", "- [x] b"]), []
        )

    def test_nested_ordered_under_bullets(self):
        lines = ["- a", "  1. one", "  2. two", "- b"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_different_marker_under_different_parent(self):
        # A nested list under another parent may use its
        # own marker — only one level under one parent
        # must stay consistent.
        lines = ["- a", "  - a1", "- b", "  * b1"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_mixed_bullet_markers(self):
        problems = tool.check_lines(["- a", "* b"])
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 2)
        self.assertEqual(
            problems[0]["reason"],
            "list mixes bullet markers: '-' and '*' "
            "— use one marker per list",
        )

    def test_mixed_plus_marker(self):
        problems = tool.check_lines(["- a", "+ b"])
        self.assertEqual(len(problems), 1)
        self.assertIn("'-' and '+'", problems[0]["reason"])

    def test_mixed_ordered_delimiters(self):
        problems = tool.check_lines(["1. a", "2) b"])
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 2)
        self.assertEqual(
            problems[0]["reason"],
            "list mixes ordered markers: '.' and ')' "
            "— use one marker per list",
        )

    def test_mixed_types_ordered_in_bullets(self):
        problems = tool.check_lines(["- a", "1. b"])
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 2)
        self.assertIn(
            "list mixes ordered and unordered items",
            problems[0]["reason"],
        )

    def test_mixed_types_bullet_in_ordered(self):
        problems = tool.check_lines(["1. a", "- b"])
        self.assertEqual(len(problems), 1)
        self.assertIn(
            "list mixes unordered and ordered items",
            problems[0]["reason"],
        )

    def test_bad_nesting_step(self):
        lines = ["- a", "  - b", "   - c"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 3)
        self.assertEqual(
            problems[0]["reason"],
            "bad indent: item is indented 3 spaces, "
            "but this list nests by 2 spaces",
        )

    def test_indent_matching_no_level(self):
        lines = ["- a", "  - b", "    - c", "   - d"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 4)
        self.assertEqual(
            problems[0]["reason"],
            "bad indent: 3 spaces does not match any "
            "level in this list",
        )

    def test_nested_marker_under_same_parent_flagged(self):
        lines = ["- a", "  - b", "  * c"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 3)
        self.assertIn("'-' and '*'", problems[0]["reason"])

    def test_blank_lines_do_not_split_a_list(self):
        lines = ["- a", "", "- b", "", "* c"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 5)

    def test_paragraph_ends_a_list(self):
        lines = ["- a", "Some text", "* b"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_less_indented_item_starts_a_new_list(self):
        lines = ["  - a", "  - b", "- c", "* d"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 4)

    def test_numbered_line_in_prose_not_a_list(self):
        lines = ["I bought", "2. apples today"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_one_starts_a_list_after_prose(self):
        lines = ["I bought", "1. apples", "2. oranges"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_numbered_after_blank_starts_a_list(self):
        lines = ["Some text", "", "2. apples", "3. oranges"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_numbered_after_heading_starts_a_list(self):
        lines = ["# Title", "2. apples"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_numbered_after_heading_mixed_types(self):
        lines = ["# Title", "2. apples", "- oranges"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 3)

    def test_fenced_code_block_skipped(self):
        lines = [
            "```",
            "- a",
            "* b",
            "```",
            "- c",
            "- d",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_tilde_fence_skipped(self):
        lines = ["~~~", "- a", "* b", "~~~"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_indented_code_block_skipped(self):
        lines = ["Some text", "", "    - not a list", "    * also not"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_numbered_item_after_indented_code_starts_a_list(self):
        # An indented code block is a block boundary, so a
        # numbered item after it can start a list — and a
        # bullet after that is a mixed-type problem.
        lines = ["Some text", "", "    - code", "2. apples", "- oranges"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 5)

    def test_indented_item_inside_a_list_is_nested(self):
        lines = ["- a", "    - b"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_horizontal_rule_not_an_item(self):
        lines = ["---", "- a", "- b"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_two_lists_both_checked(self):
        lines = ["- a", "* b", "Some text", "- c", "+ d"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 2)
        self.assertEqual([p["line"] for p in problems], [2, 5])

    def test_nesting_step_inconsistent_across_parents(self):
        lines = ["- a", "  - b", "- c", "   - d"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 4)

    def test_deep_jump_nesting_allowed(self):
        lines = ["- a", "      - b"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_ordered_paren_list_clean(self):
        self.assertEqual(tool.check_lines(["1) a", "2) b"]), [])

    def test_empty_item(self):
        self.assertEqual(tool.check_lines(["-", "- b"]), [])

    def test_year_line_after_blank_is_a_list(self):
        lines = ["", "2024. a year", "2025. another"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_empty_input(self):
        self.assertEqual(tool.check_lines([]), [])

    def test_no_lists(self):
        self.assertEqual(
            tool.check_lines(["# Title", "", "Some text."]), []
        )


class TestCheckFile(unittest.TestCase):
    def test_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "doc.md", "- a\n- b\n")
            problems, skipped = tool.check_file(path)
            self.assertEqual(problems, [])
            self.assertFalse(skipped)

    def test_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "doc.md", "- a\n* b\n")
            problems, _ = tool.check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertEqual(problems[0]["line"], 2)

    def test_missing_file_is_a_problem(self):
        problems, _ = tool.check_file(Path("/nonexistent/doc.md"))
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot read file", problems[0]["reason"])

    def test_non_utf8_file_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_bytes(b"\xff\xfe bad bytes\n")
            problems, _ = tool.check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertIn("UTF-8", problems[0]["reason"])

    def test_file_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "doc.md", "- a\n* b\n")
            before = path.read_bytes()
            tool.check_file(path)
            self.assertEqual(path.read_bytes(), before)


class TestGather(unittest.TestCase):
    def test_direct_file_always_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "notes.txt", "- a\n* b\n")
            entries, checked, _ = tool.gather([str(path)], [], True)
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(entries), 1)

    def test_folder_only_checks_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "- a\n* b\n")
            write(root / "b.markdown", "- a\n* b\n")
            write(root / "c.txt", "- a\n* b\n")
            entries, checked, _ = tool.gather([str(root)], [], True)
            self.assertEqual(len(checked), 2)
            self.assertEqual(len(entries), 2)

    def test_git_folder_never_walked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".git" / "a.md", "- a\n* b\n")
            write(root / "a.md", "- a\n- b\n")
            _entries, checked, _ = tool.gather([str(root)], [], True)
            self.assertEqual(len(checked), 1)
            self.assertEqual(checked[0]["file"], str(root / "a.md"))

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "- a\n- b\n")
            write(root / "sub" / "b.md", "- a\n* b\n")
            _entries, checked, _ = tool.gather([str(root)], [], False)
            self.assertEqual(len(checked), 1)

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "- a\n* b\n")
            write(root / "sub" / "b.md", "- a\n* b\n")
            entries, checked, skipped = tool.gather(
                [str(root)], ["sub/b.md"], True
            )
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(entries), 1)
            self.assertEqual(len(skipped), 1)

    def test_direct_file_checked_even_if_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / "a.md", "- a\n* b\n")
            entries, checked, _ = tool.gather([str(path)], ["a.md"], True)
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(entries), 1)

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            tool.gather(["/nonexistent/path"], [], True)


class TestCLI(unittest.TestCase):
    def test_clean_file_exit_0(self):
        code, out, _err = run_cli("examples/good.md")
        self.assertEqual(code, 0)
        self.assertIn("examples/good.md: lists OK", out)
        self.assertIn("all lists are consistent", out)

    def test_bad_file_exit_1(self):
        code, out, _err = run_cli("examples/bad.md")
        self.assertEqual(code, 1)
        self.assertIn(
            "FAIL examples/bad.md:5: list mixes bullet markers: '-' and '*'",
            out,
        )
        self.assertIn(
            "FAIL examples/bad.md:9: bad indent: item is indented 3 spaces",
            out,
        )
        self.assertIn(
            "FAIL examples/bad.md:11: list mixes ordered and unordered items",
            out,
        )
        self.assertIn(
            "FAIL examples/bad.md:12: list mixes ordered and unordered items",
            out,
        )
        self.assertIn(
            "FAIL examples/bad.md:18: bad indent: 3 spaces does not match",
            out,
        )
        self.assertIn("Checked 1 file(s), 5 problem(s) in 1 file(s).", out)

    def test_fenced_file_exit_0(self):
        code, out, _err = run_cli("examples/fenced.md")
        self.assertEqual(code, 0)
        self.assertIn("lists OK", out)

    def test_folder_walk(self):
        code, out, _err = run_cli("examples/")
        self.assertEqual(code, 1)
        self.assertIn("Checked 5 file(s), 6 problem(s) in 2 file(s).", out)
        self.assertIn(
            "FAIL examples/sub/nested.md:5: list mixes bullet markers: '-' and '+'",
            out,
        )

    def test_no_recursive_flag(self):
        code, out, _err = run_cli("--no-recursive", "examples/")
        self.assertEqual(code, 1)
        self.assertIn("Checked 4 file(s), 5 problem(s) in 1 file(s).", out)

    def test_exclude_flag(self):
        code, out, _err = run_cli(
            "--exclude", "sub/nested.md", "examples/"
        )
        self.assertEqual(code, 1)
        self.assertIn("Checked 4 file(s), 5 problem(s) in 1 file(s).", out)
        self.assertNotIn("nested.md", out)

    def test_stdin(self):
        code, out, _err = run_cli(
            "--stdin", stdin_text="- a\n* b\n"
        )
        self.assertEqual(code, 1)
        self.assertIn("FAIL <stdin>:2:", out)

    def test_stdin_clean(self):
        code, out, _err = run_cli(
            "--stdin", stdin_text="- a\n- b\n"
        )
        self.assertEqual(code, 0)
        self.assertIn("all lists are consistent", out)

    def test_json_output(self):
        code, out, err = run_cli("--json", "examples/bad.md")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["summary"]["checked"], 1)
        self.assertEqual(data["summary"]["problems"], 5)
        self.assertEqual(data["summary"]["files_with_problems"], 1)
        self.assertEqual(len(data["files"][0]["problems"]), 5)
        self.assertEqual(data["files"][0]["problems"][0]["line"], 5)
        self.assertIn("Checked 1 file(s), 5 problem(s)", err)

    def test_json_clean(self):
        code, out, err = run_cli("--json", "examples/good.md")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["summary"]["problems"], 0)
        self.assertIn("all lists are consistent", err)

    def test_version(self):
        code, out, _err = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "markdown-list-checker-cli 1.0.0")

    def test_missing_path_exit_2(self):
        code, _out, err = run_cli("/nonexistent/doc.md")
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_no_paths_exit_2(self):
        code, _out, err = run_cli()
        self.assertEqual(code, 2)
        self.assertIn("no Markdown files to check", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _out, err = run_cli(tmp)
            self.assertEqual(code, 2)
            self.assertIn("no Markdown files to check", err)

    def test_bad_flag_exit_2(self):
        code, _out, err = run_cli("--nope")
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments", err)


class TestBundledExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        expected = (ROOT / "examples" / "sample-output.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(result.stdout, expected)

    def test_run_example_script_exits_zero(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)

    def test_readme_quotes_real_output(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for line in [
            "examples/good.md: lists OK",
            "OK — 1 file(s) checked, all lists are consistent.",
            "FAIL examples/bad.md:5: list mixes bullet markers: '-' and '*' — use one marker per list",
            "FAIL examples/bad.md:9: bad indent: item is indented 3 spaces, but this list nests by 2 spaces",
            "FAIL examples/bad.md:11: list mixes ordered and unordered items — use one type per list",
            "FAIL examples/bad.md:12: list mixes ordered and unordered items — use one type per list",
            "FAIL examples/bad.md:18: bad indent: 3 spaces does not match any level in this list",
            "Checked 1 file(s), 5 problem(s) in 1 file(s).",
            "FAIL examples/sub/nested.md:5: list mixes bullet markers: '-' and '+' — use one marker per list",
            "Checked 5 file(s), 6 problem(s) in 2 file(s).",
            "Checked 4 file(s), 5 problem(s) in 1 file(s).",
        ]:
            self.assertIn(line, readme, f"README is missing real output: {line}")


class TestHygiene(unittest.TestCase):
    def _repo_files(self):
        # Hygiene scans exclude .git, __pycache__, and tests/ —
        # the test file itself names the banned words it scans
        # for, and its own path strings are not shipped content.
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = sorted(
                d
                for d in dirnames
                if d not in (".git", "__pycache__", "tests")
            )
            for name in filenames:
                yield Path(dirpath) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "Lorem", "FIXME", "XXX"]
        for path in self._repo_files():
            if path.suffix in (".pyc",):
                continue
            text = path.read_bytes().decode("utf-8", errors="ignore")
            for word in banned:
                self.assertNotIn(
                    word, text, f"{word} found in {path.relative_to(ROOT)}"
                )

    def test_no_absolute_local_paths(self):
        for path in self._repo_files():
            text = path.read_bytes().decode("utf-8", errors="ignore")
            self.assertNotIn(
                "/home/hatch", text, f"absolute path in {path.relative_to(ROOT)}"
            )

    def test_stdlib_imports_only(self):
        source = (ROOT / "src" / "markdown_list_checker.py").read_text(
            encoding="utf-8"
        )
        stdlib = {
            "argparse",
            "fnmatch",
            "json",
            "os",
            "re",
            "sys",
            "pathlib",
        }
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                names = stripped[7:].split(",")
                for name in names:
                    self.assertIn(
                        name.strip().split()[0], stdlib, f"non-stdlib import: {line}"
                    )
            elif stripped.startswith("from "):
                module = stripped[5:].split()[0]
                self.assertIn(
                    module.split(".")[0], stdlib, f"non-stdlib import: {line}"
                )

    def test_gitignore_first_line_is_env(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_file_runs_the_test_file(self):
        # Substring marker checks only — never an exact
        # comparison against another repo's ci.yml, and
        # never a read of another repo's files.
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("tests/test_markdown_list_checker.py", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("checkout", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)


if __name__ == "__main__":
    unittest.main()
