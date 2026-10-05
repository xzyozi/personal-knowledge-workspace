"""リポジトリの安全な初期構成を標準ライブラリだけで検証する。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DIRECTORIES = (
    ".kiro",
    ".kiro/steering",
    "knowledge",
    "knowledge/00-rules",
    "knowledge/01-private",
    "knowledge/02-facts",
    "knowledge/03-output",
    "knowledge/04-sources",
    "knowledge/04-sources/04.00-inbox",
    "knowledge/05-tasks",
    "knowledge/06-large",
    "knowledge/99-archive",
    "projects",
    "scripts",
)
REQUIRED_FILES = (
    "README.md",
    "PROJECT.md",
    "AGENTS.md",
    "GEMINI.md",
    ".kiro/README.md",
    ".kiro/steering/knowledge-entry.md",
    ".gemeni/knowledge-entry.md",
    ".claude/knowledge-entry.md",
    ".codex/knowledge-entry.md",
    "knowledge/INDEX.md",
    "knowledge/00-rules/00.01-entry-rule.md",
    "knowledge/00-rules/00.02-read-policy.md",
    "knowledge/00-rules/00.03-write-policy.md",
    "knowledge/00-rules/00.04-classification-rule.md",
    "knowledge/01-private/.gitignore",
    "knowledge/06-large/.gitignore",
    "scripts/validate_structure.py",
)
AI_DIRECTORIES = (".kiro", ".gemeni", ".claude", ".codex")
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


def main() -> int:
    errors: list[str] = []
    check_required_paths(errors)
    check_ai_directories(errors)
    check_sensitive_names(errors)
    if errors:
        print("Structure validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Structure validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
