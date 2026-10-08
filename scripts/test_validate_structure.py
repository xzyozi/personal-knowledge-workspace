"""validate_structureの共有定義の検査を、一時ツリーで検証する。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import validate_structure as checker

AGENT_NAME = "pkw-knowledge-steward"
SKILL_NAME = "pkw-sample-skill"
SKILL_DESCRIPTION = "skill description"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def front(name: str, description: str, extra: str = "") -> str:
    return f"---\nname: {name}\ndescription: {description}\n{extra}---\n\n# {name}\n"


def row(name: str = SKILL_NAME, description: str = SKILL_DESCRIPTION, link: str = f"../skills/{SKILL_NAME}.md") -> str:
    return f"| {name} | {description} | [{name}.md]({link}) |\n"


def agent_text(rows: str) -> str:
    return front(AGENT_NAME, "agent description") + "\n## Skill一覧\n\n| name | description | 本文 |\n|---|---|---|\n" + rows


def make_tree(root: Path) -> None:
    agents = root / checker.AGENT_DIRECTORY
    skills = root / checker.SKILL_DIRECTORY
    write(agents / "README.md", "# Agents\n")
    write(skills / "README.md", "# Skills\n")
    write(agents / f"{AGENT_NAME}.md", agent_text(row()))
    write(skills / f"{SKILL_NAME}.md", front(SKILL_NAME, SKILL_DESCRIPTION))
    for entry in checker.ENTRY_FILES:
        write(root / entry, f"see {AGENT_NAME}.md\n")


def run(root: Path) -> list[str]:
    errors: list[str] = []
    checker.check_shared_definitions(errors, root)
    return errors


def assert_reports(root: Path, fragment: str) -> None:
    errors = run(root)
    assert any(fragment in error for error in errors), (fragment, errors)


ENTRY_CONFIG = (
    "[profiles.default]\n"
    'description = "fixture"\n\n'
    "[[profiles.default.targets]]\n"
    'id = "claude-entry"\n'
    'source = ".claude/CLAUDE.md"\n'
    'destination = ".claude/CLAUDE.md"\n'
    'mode = "managed-block"\n'
    "revision = 1\n"
)


def managed(entry_id: str, body: str) -> str:
    return (
        f'<!-- pkw:managed:start id="{entry_id}" revision="1" -->\n'
        f"{body}"
        f'<!-- pkw:managed:end id="{entry_id}" -->\n'
    )


def make_entry_tree(root: Path) -> None:
    write(root / "AGENTS.md", "# AGENTS\n")
    write(root / "config" / "bootstrap.toml", ENTRY_CONFIG)
    write(root / ".claude" / "CLAUDE.md", managed("claude-entry", "see AGENTS.md\n@../AGENTS.md\n"))
    write(root / checker.GLOBAL_STEERING, "---\ninclusion: always\n---\n\nRead AGENTS.md first.\n")


def run_entries(root: Path) -> list[str]:
    errors: list[str] = []
    checker.check_global_entries(errors, root)
    return errors


def assert_entry_reports(root: Path, fragment: str) -> None:
    errors = run_entries(root)
    assert any(fragment in error for error in errors), (fragment, errors)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkw-validate-") as directory:
        base = Path(directory)
        skill_path = checker.SKILL_DIRECTORY + f"/{SKILL_NAME}.md"
        agent_path = checker.AGENT_DIRECTORY + f"/{AGENT_NAME}.md"

        valid = base / "valid"
        make_tree(valid)
        assert run(valid) == [], run(valid)

        no_frontmatter = base / "no-frontmatter"
        make_tree(no_frontmatter)
        write(no_frontmatter / skill_path, "# no frontmatter\n")
        assert_reports(no_frontmatter, "requires frontmatter")

        bad_name = base / "bad-name"
        make_tree(bad_name)
        write(bad_name / skill_path, front("sample", SKILL_DESCRIPTION))
        assert_reports(bad_name, "pkw- kebab-case")
        assert_reports(bad_name, "must match file name")

        long_description = base / "long-description"
        make_tree(long_description)
        write(long_description / skill_path, front(SKILL_NAME, "x" * 201))
        assert_reports(long_description, "longer than 200")

        pipe_description = base / "pipe-description"
        make_tree(pipe_description)
        write(pipe_description / skill_path, front(SKILL_NAME, "a | b"))
        assert_reports(pipe_description, "must not contain a pipe")

        unknown_key = base / "unknown-key"
        make_tree(unknown_key)
        write(unknown_key / skill_path, front(SKILL_NAME, SKILL_DESCRIPTION, "tags: x\n"))
        assert_reports(unknown_key, "unsupported frontmatter keys")

        unlisted = base / "unlisted"
        make_tree(unlisted)
        write(unlisted / agent_path, agent_text(""))
        assert_reports(unlisted, "not listed in any agent")

        broken_link = base / "broken-link"
        make_tree(broken_link)
        write(broken_link / agent_path, agent_text(row(link="../skills/missing.md")))
        assert_reports(broken_link, "broken or outside skills/")

        table_mismatch = base / "table-mismatch"
        make_tree(table_mismatch)
        write(table_mismatch / agent_path, agent_text(row(description="different description")))
        assert_reports(table_mismatch, "table description differs")

        missing_reference = base / "missing-reference"
        make_tree(missing_reference)
        write(missing_reference / "GEMINI.md", "no reference here\n")
        assert_reports(missing_reference, "entry does not reference agent")

        entries = base / "entries"
        make_entry_tree(entries)
        assert run_entries(entries) == [], run_entries(entries)

        missing_import = base / "missing-import"
        make_entry_tree(missing_import)
        write(missing_import / ".claude" / "CLAUDE.md", managed("claude-entry", "AGENTS.md\n@../MISSING.md\n"))
        assert_entry_reports(missing_import, "import does not resolve")

        other_import = base / "other-import"
        make_entry_tree(other_import)
        write(other_import / "OTHER.md", "# other\n")
        write(other_import / ".claude" / "CLAUDE.md", managed("claude-entry", "AGENTS.md\n@../OTHER.md\n"))
        assert_entry_reports(other_import, "must resolve to AGENTS.md")

        wrong_id = base / "wrong-id"
        make_entry_tree(wrong_id)
        write(wrong_id / ".claude" / "CLAUDE.md", managed("wrong", "AGENTS.md\n@../AGENTS.md\n"))
        assert_entry_reports(wrong_id, "must match target id")

        no_marker = base / "no-marker"
        make_entry_tree(no_marker)
        write(no_marker / ".claude" / "CLAUDE.md", "AGENTS.md\n@../AGENTS.md\n")
        assert_entry_reports(no_marker, "must match target id")

        steering_reference = base / "steering-reference"
        make_entry_tree(steering_reference)
        write(steering_reference / checker.GLOBAL_STEERING, "---\ninclusion: always\n---\n\n#[[file:../../AGENTS.md]]\n")
        assert_entry_reports(steering_reference, "must not use file references")

        legacy = base / "legacy"
        make_entry_tree(legacy)
        write(legacy / "AGENTS.md", "# AGENTS\n" + checker.LEGACY_NAME + "\n")
        legacy_errors: list[str] = []
        checker.check_legacy_names(legacy_errors, legacy)
        assert any("legacy name remains" in error for error in legacy_errors), legacy_errors

    print("validate_structure shared definition checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())