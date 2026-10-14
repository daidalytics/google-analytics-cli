"""Guard tests for the agent skill shipped in skills/ga-cli/.

The skill is copied verbatim to every user by `npx skills add` and the Claude
Code plugin, so these tests keep it honest: valid frontmatter, a generated
command reference that matches the CLI, no references to commands that don't
exist, and nothing that shouldn't be distributed.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import typer

from ga_cli.main import app
from ga_cli.utils.describe import build_cli_schema

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
SKILL_DIR = SKILLS_ROOT / "ga-cli"
SKILL_MD = SKILL_DIR / "SKILL.md"

# Import the standalone generator script as a module
GENERATOR_PATH = REPO_ROOT / "scripts" / "gen_skill_reference.py"
_spec = importlib.util.spec_from_file_location("gen_skill_reference", GENERATOR_PATH)
gen_skill_reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen_skill_reference)


@pytest.fixture(scope="module")
def schema() -> dict:
    return build_cli_schema(app)


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the flat `key: value` YAML frontmatter of a SKILL.md by hand.

    Supports single-line values (optionally quoted) and indented continuation
    lines, which covers what skill frontmatter uses. No PyYAML dependency.
    """
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "SKILL.md must start with a '---' line"
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        pytest.fail("SKILL.md frontmatter has no closing '---' line")

    fields: dict[str, str] = {}
    key = None
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z_][\w-]*):(.*)$", line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            if value in (">", "|", ">-", "|-"):
                value = ""
            fields[key] = value
        elif key is not None and line.strip():
            fields[key] = f"{fields[key]} {line.strip()}".strip()

    for k, v in fields.items():
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            fields[k] = v[1:-1]
    return fields


class TestSkillFrontmatter:
    def test_parser_handles_quotes_and_continuations(self):
        fields = _parse_frontmatter('---\nname: "x"\ndescription: >\n  one\n  two\n---\n')
        assert fields == {"name": "x", "description": "one two"}

    def test_name_is_ga_cli(self):
        fields = _parse_frontmatter(SKILL_MD.read_text())
        assert fields.get("name") == "ga-cli"

    def test_name_matches_directory(self):
        fields = _parse_frontmatter(SKILL_MD.read_text())
        assert fields.get("name") == SKILL_DIR.name

    def test_description_is_present(self):
        fields = _parse_frontmatter(SKILL_MD.read_text())
        assert fields.get("description", "").strip()


# ---------------------------------------------------------------------------
# Generated reference drift
# ---------------------------------------------------------------------------


class TestGeneratedReference:
    def test_markers_present_once(self):
        text = gen_skill_reference.COMMANDS_MD.read_text()
        assert text.count(gen_skill_reference.BEGIN_MARKER) == 1
        assert text.count(gen_skill_reference.END_MARKER) == 1
        assert text.index(gen_skill_reference.BEGIN_MARKER) < text.index(
            gen_skill_reference.END_MARKER
        )

    def test_committed_block_matches_fresh_render(self, schema):
        committed = gen_skill_reference.extract_block(gen_skill_reference.COMMANDS_MD.read_text())
        fresh = gen_skill_reference.render(schema)
        assert committed == fresh, (
            "skills/ga-cli/references/commands.md is out of date with the CLI. "
            "Run: uv run python scripts/gen_skill_reference.py --write"
        )

    def test_check_mode_passes(self, capsys):
        assert gen_skill_reference.main(["--check"]) == 0

    def test_check_mode_fails_on_drift(self, tmp_path, capsys):
        stale = tmp_path / "commands.md"
        text = gen_skill_reference.COMMANDS_MD.read_text()
        stale.write_text(text.replace("### ga reports", "### ga reportz"))
        assert gen_skill_reference.main(["--check", "--path", str(stale)]) == 1
        assert "gen_skill_reference.py --write" in capsys.readouterr().err

    def test_write_mode_only_touches_generated_span(self, tmp_path, schema):
        target = tmp_path / "commands.md"
        target.write_text(
            "# Intro\n\nhand-written\n\n"
            f"{gen_skill_reference.BEGIN_MARKER}\nstale\n{gen_skill_reference.END_MARKER}\n"
            "\n## Outro\n\nalso hand-written\n"
        )
        assert gen_skill_reference.main(["--write", "--path", str(target)]) == 0
        written = target.read_text()
        assert written.startswith("# Intro\n\nhand-written\n\n")
        assert written.endswith("\n## Outro\n\nalso hand-written\n")
        assert "stale" not in written
        assert gen_skill_reference.extract_block(written) == gen_skill_reference.render(schema)

    def test_missing_markers_is_an_error(self, tmp_path, capsys):
        target = tmp_path / "commands.md"
        target.write_text("# no markers here\n")
        assert gen_skill_reference.main(["--check", "--path", str(target)]) == 1
        assert "marker" in capsys.readouterr().err.lower()

    def test_print_mode_outputs_block(self, capsys, schema):
        assert gen_skill_reference.main([]) == 0
        assert capsys.readouterr().out == gen_skill_reference.render(schema)


# ---------------------------------------------------------------------------
# Every `ga <group> [<sub>]` in a fenced code block exists in the CLI
# ---------------------------------------------------------------------------

# Root options that may precede the group. --profile takes a value.
_ROOT_FLAGS = frozenset({
    "-q", "--quiet", "--no-color", "--describe", "--version", "-v", "--help", "-h",
})
_ROOT_OPTIONS_WITH_VALUE = frozenset({"--profile"})

_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

# `ga` (or the uvx form of it) in command position: start of the line, or right
# after a pipe, `;`, `&&`, `||`, `(`, `$(` or a backtick, optionally preceded by
# env-var assignments. Anything else (`command -v ga`, `alias ga=…`, `.ga`) is
# not an invocation of this CLI.
_INVOCATION_RE = re.compile(
    r"(?:^|[|;&(`])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
    r"(?:ga|google-analytics-cli|uvx\s+google-analytics-cli|uvx\s+--from\s+\S+\s+ga)"
    r"(?=\s|$|[|;&)`])"
)
# Where the CLI's own arguments stop: the next shell operator or redirection.
_ARGS_END_RE = re.compile(r"[|;&)`<>]")


def _closes_fence(line: str, fence: str) -> bool:
    """A closing fence uses the opening's character, is at least as long, and has no info."""
    match = _FENCE_RE.match(line)
    if not match:
        return False
    marker = match.group(1)
    return marker[0] == fence[0] and len(marker) >= len(fence) and not line[match.end():].strip()


def _fenced_blocks(text: str) -> list[tuple[int, list[str]]]:
    """Return (first line number, lines) for each fenced code block."""
    blocks: list[tuple[int, list[str]]] = []
    fence: str | None = None
    start = 0
    body: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if fence is None:
            match = _FENCE_RE.match(line)
            if match:
                fence, start, body = match.group(1), lineno + 1, []
        elif _closes_fence(line, fence):
            blocks.append((start, body))
            fence = None
        else:
            body.append(line)
    return blocks


def _strip_comment(line: str) -> str:
    return re.sub(r"(^|\s)#.*$", "", line).rstrip()


def _logical_lines(start: int, lines: list[str]) -> list[tuple[int, str]]:
    """Join backslash continuations and drop shell comments.

    Returns (line number of the first physical line, logical line) pairs.
    """
    result: list[tuple[int, str]] = []
    buf, buf_start = "", start
    for offset, line in enumerate(lines):
        if not buf:
            buf_start = start + offset
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
            continue
        result.append((buf_start, _strip_comment(buf + line)))
        buf = ""
    if buf:
        result.append((buf_start, _strip_comment(buf)))
    return result


def _invocations(line: str) -> list[list[str]]:
    """Return the argument tokens following each `ga` invocation in a line."""
    found = []
    for match in _INVOCATION_RE.finditer(line):
        rest = line[match.end():]
        end = _ARGS_END_RE.search(rest)
        if end:
            rest = rest[: end.start()]
        found.append(rest.split())
    return found


def _known_commands(schema: dict) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    """Return (groups, (group, sub) pairs, callback-only groups) the CLI accepts.

    Groups that run from a callback with no subcommands (e.g. `ga upgrade`)
    have no entry in the schema at all, so they come from the Click group.
    """
    pairs = {tuple(key.split()[1:3]) for key in schema["commands"]}
    groups = {group for group, _ in pairs}
    click_group = typer.main.get_group(app)
    top_level = set(click_group.list_commands(None))  # type: ignore[arg-type]
    callback_only = top_level - groups
    return groups | callback_only, pairs, callback_only


def _check_invocation(
    args: list[str],
    groups: set[str],
    pairs: set[tuple[str, str]],
    callback_only: set[str],
) -> str | None:
    """Return a failure reason for one invocation, or None if it is valid."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        token = args[i]
        if token in _ROOT_FLAGS:
            i += 1
        elif token in _ROOT_OPTIONS_WITH_VALUE:
            i += 2
        elif token.split("=", 1)[0] in _ROOT_OPTIONS_WITH_VALUE:
            i += 1
        else:
            return f"unknown root option {token!r}"
    if i >= len(args):
        return None  # e.g. `ga --version`

    group = args[i]
    if group not in groups:
        return f"unknown command group {group!r}"
    sub = args[i + 1] if i + 1 < len(args) else None
    if sub is None or sub.startswith("-"):
        return None
    if group in callback_only:
        return f"'ga {group}' takes no subcommand, got {sub!r}"
    if (group, sub) not in pairs:
        return f"unknown command 'ga {group} {sub}'"
    return None


def _skill_markdown_files() -> list[Path]:
    return sorted(SKILL_DIR.rglob("*.md"))


class TestCommandExistence:
    def test_skill_has_markdown_files(self):
        files = _skill_markdown_files()
        assert SKILL_MD in files
        assert len(files) >= 2

    def test_every_invocation_in_code_blocks_exists(self, schema):
        groups, pairs, callback_only = _known_commands(schema)
        failures: list[str] = []
        checked = 0
        for path in _skill_markdown_files():
            rel = path.relative_to(REPO_ROOT)
            for start, lines in _fenced_blocks(path.read_text()):
                for lineno, line in _logical_lines(start, lines):
                    for args in _invocations(line):
                        checked += 1
                        reason = _check_invocation(args, groups, pairs, callback_only)
                        if reason:
                            failures.append(f"{rel}:{lineno}: {reason}\n    {line.strip()}")
        assert checked > 0, "no ga invocations found in the skill's code blocks"
        assert not failures, (
            f"{len(failures)} skill command(s) don't exist in the CLI "
            "(fix the skill text to match `ga --describe`):\n" + "\n".join(failures)
        )


class TestInvocationParsing:
    """The existence check's parser, against the shapes the skill uses."""

    @pytest.mark.parametrize(
        "line, expected",
        [
            ("ga reports run -p 1 -m sessions", [["reports", "run", "-p", "1", "-m", "sessions"]]),
            ("ga --profile client-a reports run", [["--profile", "client-a", "reports", "run"]]),
            ("GA_CLI_PROFILE=x ga reports run", [["reports", "run"]]),
            ("echo hi && ga auth status", [["auth", "status"]]),
            ("cat x | ga reports run | jq .", [["reports", "run"]]),
            ("ID=$(ga properties list -o json)", [["properties", "list", "-o", "json"]]),
            ("uvx google-analytics-cli reports run", [["reports", "run"]]),
            ("command -v ga", []),
            ("alias ga='git add'", []),
            ("jq '.ga' x.json", []),
            ("ga4 something", []),
        ],
    )
    def test_invocations(self, line, expected):
        assert _invocations(line) == expected

    def test_comments_and_continuations(self):
        lines = ["ga reports run -p 1 \\", "  -m sessions  # trailing comment", "# ga bogus cmd"]
        parsed = [(n, line.split()) for n, line in _logical_lines(10, lines)]
        assert parsed == [(10, ["ga", "reports", "run", "-p", "1", "-m", "sessions"]), (12, [])]

    def test_fenced_blocks(self):
        text = "prose ga bogus\n```bash\nga auth status\n```\n~~~~\nga x y\n```\nstill in\n~~~~\n"
        assert _fenced_blocks(text) == [(3, ["ga auth status"]), (6, ["ga x y", "```", "still in"])]

    @pytest.mark.parametrize(
        "args, ok",
        [
            (["reports", "run", "-p", "1"], True),
            (["--profile", "client-a", "reports", "run"], True),
            (["--profile=client-a", "reports", "run"], True),
            (["-q", "--no-color", "reports", "run"], True),
            (["--version"], True),
            (["reports"], True),
            (["reports", "--help"], True),
            (["upgrade"], True),
            (["upgrade", "--check"], True),
            (["upgrade", "now"], False),
            (["property-settings", "get"], False),
            (["reportz", "run"], False),
            (["-p", "1", "reports", "run"], False),
        ],
    )
    def test_check_invocation(self, schema, args, ok):
        groups, pairs, callback_only = _known_commands(schema)
        assert (_check_invocation(args, groups, pairs, callback_only) is None) is ok


# ---------------------------------------------------------------------------
# Nothing that shouldn't ship
# ---------------------------------------------------------------------------


class TestNoForbiddenContent:
    def test_no_evals_directory(self):
        assert not [p for p in SKILLS_ROOT.rglob("evals") if p.is_dir()]

    def test_no_json_files(self):
        assert not list(SKILLS_ROOT.rglob("*.json"))

    def test_no_ds_store(self):
        assert not list(SKILLS_ROOT.rglob(".DS_Store"))
