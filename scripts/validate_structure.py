"""リポジトリの安全な初期構成を標準ライブラリだけで検証する。"""

from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote as url_unquote

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DIRECTORIES = (
    ".kiro",
    ".kiro/steering",
    "config",
    "docs",
    "docs/design",
    "reports",
    "knowledge",
    "knowledge/00-rules",
    "knowledge/00-rules/agents",
    "knowledge/00-rules/skills",
    "knowledge/01-private",
    "knowledge/02-facts",
    "knowledge/03-output",
    "knowledge/04-sources",
    "knowledge/04-sources/04.00-inbox",
    "knowledge/05-tasks",
    "knowledge/06-large",
    "knowledge/99-archive",
    "knowledge/projects",
    "scripts",
)
REQUIRED_FILES = (
    "README.md",
    "PROJECT.md",
    "AGENTS.md",
    "GEMINI.md",
    ".kiro/README.md",
    ".kiro/steering/knowledge-entry.md",
    "config/bootstrap.toml",
    "config/bootstrap.local.example.toml",
    "docs/design/reverse-bootstrap.md",
    "docs/design/migrate-knowledge.md",
    "docs/design/shared-agents.md",
    "reports/bootstrap-report.html",
    "reports/README.md",
    ".gemini/GEMINI.md",
    ".claude/CLAUDE.md",
    ".codex/AGENTS.md",
    "knowledge/INDEX.md",
    "knowledge/00-rules/00.01-entry-rule.md",
    "knowledge/00-rules/00.02-read-policy.md",
    "knowledge/00-rules/00.03-write-policy.md",
    "knowledge/00-rules/00.04-classification-rule.md",
    "knowledge/00-rules/agents/README.md",
    "knowledge/00-rules/agents/pkw-knowledge-steward.md",
    "knowledge/00-rules/skills/README.md",
    "knowledge/01-private/.gitignore",
    "knowledge/06-large/.gitignore",
    "knowledge/projects/INDEX.md",
    "scripts/validate_structure.py",
    "scripts/bootstrap.py",
    "scripts/reverse_bootstrap.py",
    "scripts/migrate_knowledge.py",
    "scripts/view_bootstrap_report.py",
    "scripts/test_bootstrap.py",
    "scripts/test_reverse_bootstrap.py",
    "scripts/test_migrate_knowledge.py",
    "scripts/test_validate_structure.py",
)
AI_DIRECTORIES = (".kiro", ".gemini", ".claude", ".codex")
EXCLUDED_DIRECTORY_NAMES = {".git", ".kiro", "__pycache__"}
SENSITIVE_NAME = re.compile(
    r"(^|[._-])(env|secret|secrets|token|credential|credentials|password|passwd)([._-]|$)",
    re.IGNORECASE,
)
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def iter_files_without_excluded_directories(root: Path):
    """除外ディレクトリへ入らず、検証対象ファイルだけを列挙する。"""
    for current, directories, files in __import__("os").walk(root):
        directories[:] = [
            name for name in directories if name not in EXCLUDED_DIRECTORY_NAMES
        ]
        current_path = Path(current)
        for name in files:
            yield current_path / name


def check_required_paths(errors: list[str]) -> None:
    for relative in REQUIRED_DIRECTORIES:
        path = ROOT / relative
        if not path.is_dir():
            errors.append(f"missing directory: {relative}")
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing file: {relative}")


def check_ai_directories(errors: list[str]) -> None:
    for name in AI_DIRECTORIES:
        directory = ROOT / name
        if directory.is_dir() and not (directory / "README.md").is_file():
            errors.append(f"AI directory requires README.md: {name}")


def check_sensitive_names(errors: list[str]) -> None:
    ignored_roots = {
        ROOT / "knowledge" / "01-private",
        ROOT / "knowledge" / "06-large",
    }
    for path in iter_files_without_excluded_directories(ROOT):
        if any(root == path or root in path.parents for root in ignored_roots):
            continue
        if path.name == ".gitignore":
            continue
        if SENSITIVE_NAME.search(path.name) or path.suffix.lower() in SENSITIVE_SUFFIXES:
            relative = path.relative_to(ROOT).as_posix()
            errors.append(f"sensitive-looking filename outside local-only areas: {relative}")


AGENT_DIRECTORY = "knowledge/00-rules/agents"
SKILL_DIRECTORY = "knowledge/00-rules/skills"
ENTRY_FILES = (
    "AGENTS.md",
    "GEMINI.md",
)
SHARED_NAME = re.compile(r"^pkw-[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_KEYS = frozenset({"name", "description"})
MAX_DESCRIPTION_LENGTH = 200
TABLE_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TABLE_SEPARATOR_CELL = re.compile(r"^:?-+:?$")


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """先頭のfrontmatterを読む。閉じていない、または無い場合はNoneを返す。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            data[match.group(1)] = unquote(match.group(2).strip())
        elif line.strip():
            data[line.strip()] = ""
    return None


def load_definitions(root: Path, directory: str, kind: str, errors: list[str]) -> dict[str, dict]:
    """共有エージェントまたはSkillの定義を読み、frontmatterを検査する。"""
    base = root / directory
    definitions: dict[str, dict] = {}
    if not base.is_dir():
        return definitions
    for path in sorted(base.glob("*.md")):
        if path.name == "README.md":
            continue
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            errors.append(f"{kind} definition is unreadable: {relative}")
            continue
        meta = parse_frontmatter(text)
        if meta is None:
            errors.append(f"{kind} requires frontmatter: {relative}")
            continue
        unknown = sorted(set(meta) - FRONTMATTER_KEYS)
        if unknown:
            errors.append(f"{kind} has unsupported frontmatter keys {unknown}: {relative}")
        name = meta.get("name", "")
        description = meta.get("description", "")
        if not name:
            errors.append(f"{kind} requires name: {relative}")
        else:
            if not SHARED_NAME.match(name):
                errors.append(f"{kind} name must be pkw- kebab-case: {relative}")
            if name != path.stem:
                errors.append(f"{kind} name must match file name: {relative}")
        if not description:
            errors.append(f"{kind} requires description: {relative}")
        else:
            if len(description) > MAX_DESCRIPTION_LENGTH:
                errors.append(f"{kind} description is longer than {MAX_DESCRIPTION_LENGTH} characters: {relative}")
            if "|" in description:
                errors.append(f"{kind} description must not contain a pipe: {relative}")
        definitions[path.stem] = {
            "path": path,
            "relative": relative,
            "name": name,
            "description": description,
            "text": text,
        }
    return definitions


def parse_skill_rows(text: str) -> list[list[str]]:
    """エージェント定義の「Skill一覧」の表から、データ行のセルを返す。"""
    rows: list[list[str]] = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_section = line.strip() == "## Skill一覧"
            continue
        stripped = line.strip()
        if not in_section or not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(TABLE_SEPARATOR_CELL.match(cell) for cell in cells):
            continue
        if cells == ["name", "description", "本文"]:
            continue
        rows.append(cells)
    return rows


def check_shared_definitions(errors: list[str], root: Path = ROOT) -> None:
    agents = load_definitions(root, AGENT_DIRECTORY, "agent", errors)
    skills = load_definitions(root, SKILL_DIRECTORY, "skill", errors)

    seen: dict[str, str] = {}
    for definitions in (agents, skills):
        for definition in definitions.values():
            name = definition["name"]
            if not name:
                continue
            if name in seen:
                errors.append(f"shared name is duplicated: {name} in {definition['relative']} and {seen[name]}")
            else:
                seen[name] = definition["relative"]

    listed: set[str] = set()
    for agent in agents.values():
        for cells in parse_skill_rows(agent["text"]):
            if len(cells) != 3:
                errors.append(f"skill row must have three columns in {agent['relative']}")
                continue
            name = cells[0].strip("`")
            description = cells[1]
            link = TABLE_LINK.search(cells[2])
            if link is None:
                errors.append(f"skill row requires a link: {name} in {agent['relative']}")
                continue
            target = (agent["path"].parent / link.group(1)).resolve()
            skill = next((value for value in skills.values() if value["path"].resolve() == target), None)
            if skill is None:
                errors.append(f"skill link is broken or outside skills/: {link.group(1)} in {agent['relative']}")
                continue
            listed.add(skill["path"].stem)
            if skill["name"] != name:
                errors.append(f"skill table name differs from frontmatter: {name} in {agent['relative']}")
            if skill["description"] != description:
                errors.append(f"skill table description differs from frontmatter: {name} in {agent['relative']}")
    for stem, skill in skills.items():
        if stem not in listed:
            errors.append(f"skill is not listed in any agent: {skill['relative']}")

    for agent in agents.values():
        reference = f"{agent['path'].stem}.md"
        for entry in ENTRY_FILES:
            entry_path = root / entry
            if not entry_path.is_file():
                errors.append(f"missing entry file: {entry}")
                continue
            try:
                entry_text = entry_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                errors.append(f"entry file is unreadable: {entry}")
                continue
            if reference not in entry_text:
                errors.append(f"entry does not reference agent {reference}: {entry}")


MANAGED_START = re.compile(r'<!--\s*pkw:managed:start\s+id="([^"]+)"')
MANAGED_END = re.compile(r'<!--\s*pkw:managed:end\s+id="([^"]+)"')
IMPORT_LINE = re.compile(r"^@(\S+)\s*$", re.MULTILINE)
FILE_REFERENCE_LINE = re.compile(r"^#\[\[file:", re.MULTILINE)
GLOBAL_STEERING = ".kiro/steering/knowledge-entry.md"
LEGACY_NAME = "gem" + "eni"
LEGACY_CHECK_FILES = ("AGENTS.md", "README.md", "PROJECT.md", ".gitignore", "config/bootstrap.toml")
LEGACY_CHECK_DIRECTORIES = ("knowledge/00-rules", ".claude", ".codex", ".gemini")


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def check_global_entries(errors: list[str], root: Path = ROOT) -> None:
    """ツール別のグローバル入口が、AGENTS.mdへ正しく辿れることを検査する。"""
    config_text = read_text(root / "config" / "bootstrap.toml")
    if config_text is None:
        errors.append("config/bootstrap.toml is unreadable")
        return
    try:
        config = tomllib.loads(config_text)
    except tomllib.TOMLDecodeError:
        errors.append("config/bootstrap.toml is not valid TOML")
        return
    targets = config.get("profiles", {}).get("default", {}).get("targets", [])
    if not isinstance(targets, list):
        errors.append("default profile targets must be a list")
        return
    agents = (root / "AGENTS.md").resolve()
    for target in targets:
        if not isinstance(target, dict) or target.get("mode") != "managed-block":
            continue
        target_id = str(target.get("id", ""))
        source = str(target.get("source", ""))
        path = root / source
        text = read_text(path) if path.is_file() else None
        if text is None:
            errors.append(f"managed-block source is missing or unreadable: {source}")
            continue
        starts = [match.group(1) for match in MANAGED_START.finditer(text)]
        ends = [match.group(1) for match in MANAGED_END.finditer(text)]
        if starts != [target_id] or ends != [target_id]:
            errors.append(f"managed block id must match target id {target_id}: {source}")
            continue
        if "AGENTS.md" not in text:
            errors.append(f"managed block must point to AGENTS.md: {source}")
        for match in IMPORT_LINE.finditer(text):
            resolved = (path.parent / match.group(1)).resolve()
            if not resolved.is_file():
                errors.append(f"managed block import does not resolve: {match.group(1)} in {source}")
            elif resolved != agents:
                errors.append(f"managed block import must resolve to AGENTS.md: {match.group(1)} in {source}")

    steering = root / GLOBAL_STEERING
    steering_text = read_text(steering) if steering.is_file() else None
    if steering_text is None:
        errors.append(f"global steering is missing or unreadable: {GLOBAL_STEERING}")
        return
    if FILE_REFERENCE_LINE.search(steering_text):
        errors.append(f"global steering must not use file references: {GLOBAL_STEERING}")
    if "AGENTS.md" not in steering_text:
        errors.append(f"global steering must point to AGENTS.md: {GLOBAL_STEERING}")


def check_legacy_names(errors: list[str], root: Path = ROOT) -> None:
    """改名前の表記が、管理対象のファイルへ再び混入していないことを検査する。"""
    paths = [root / name for name in LEGACY_CHECK_FILES]
    for directory in LEGACY_CHECK_DIRECTORIES:
        base = root / directory
        if base.is_dir():
            paths.extend(sorted(path for path in base.rglob("*.md") if path.is_file()))
    for path in paths:
        text = read_text(path) if path.is_file() else None
        if text is not None and LEGACY_NAME in text:
            errors.append(f"legacy name remains: {path.relative_to(root).as_posix()}")


MARKDOWN_EXCLUDED_DIRECTORIES = frozenset({".git", "__pycache__", "node_modules"})
MARKDOWN_EXCLUDED_PREFIXES = ("knowledge/01-private/", "knowledge/04-sources/", "knowledge/06-large/")
FENCE_LINE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
ABSOLUTE_WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]")
ABSOLUTE_UNIX_PATH = re.compile(r"(?<![\w.~])/(?:home|Users)/[^/\s]+")
EXTERNAL_LINK = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|#)")


def iter_markdown_files(root: Path):
    """書式検査の対象のMarkdownを列挙する。原本とローカル専用の領域は除く。"""
    for current, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name not in MARKDOWN_EXCLUDED_DIRECTORIES]
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = Path(current) / name
            if path.relative_to(root).as_posix().startswith(MARKDOWN_EXCLUDED_PREFIXES):
                continue
            yield path


def strip_code(text: str) -> str:
    """コードブロックとインラインコードを除いた本文を返す。書式の例を、リンク検査の対象にしないため。"""
    visible: list[str] = []
    in_fence = False
    for line in text.split("\n"):
        if FENCE_LINE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            visible.append(INLINE_CODE.sub("", line))
    return "\n".join(visible)


def check_markdown_hygiene(errors: list[str], root: Path = ROOT) -> None:
    """Markdownの書式（改行コード、タブ、コードブロック、絶対パス、リンク）を検査する。"""
    for path in iter_markdown_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            data = path.read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            errors.append(f"markdown is unreadable or not UTF-8: {relative}")
            continue
        if b"\r" in data:
            errors.append(f"markdown must use LF line endings: {relative}")
        if "\t" in text:
            errors.append(f"markdown must not contain tab characters: {relative}")
        if sum(1 for line in text.split("\n") if FENCE_LINE.match(line)) % 2 != 0:
            errors.append(f"markdown has an unclosed code fence: {relative}")
        if ABSOLUTE_WINDOWS_PATH.search(text) or ABSOLUTE_UNIX_PATH.search(text):
            errors.append(f"markdown contains an absolute path: {relative}")
        for match in MARKDOWN_LINK.finditer(strip_code(text)):
            target = match.group(1)
            if EXTERNAL_LINK.match(target) or any(char in target for char in "<>{}"):
                continue
            link_path = url_unquote(target.split("#", 1)[0])
            if link_path and not (path.parent / link_path).exists():
                errors.append(f"markdown link is broken: {target} in {relative}")


def main() -> int:
    errors: list[str] = []
    check_required_paths(errors)
    check_ai_directories(errors)
    check_sensitive_names(errors)
    check_shared_definitions(errors)
    check_global_entries(errors)
    check_legacy_names(errors)
    check_markdown_hygiene(errors)
    if errors:
        print("Structure validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Structure validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
