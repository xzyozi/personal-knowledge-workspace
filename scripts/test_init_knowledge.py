"""init_knowledgeのfixture検証。CIでのみ実行し、実ユーザー環境を変更しない。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFETY_ERROR = 30
KEEP = "利用者が書いた内容\n"


def write_local_config(worktree: Path, target: Path) -> None:
    (worktree / "config" / "bootstrap.local.toml").write_text(
        "[profile]\n"
        'name = "default"\n\n'
        "[target]\n"
        f"root = {json.dumps(target.as_posix())}\n\n"
        "[report.server]\n"
        "port = 8765\n",
        encoding="utf-8",
        newline="\n",
    )


def run_init(worktree: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(worktree / "scripts" / "init_knowledge.py"), *args],
        cwd=worktree,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def prepare_fixture(root: Path, name: str) -> tuple[Path, Path, Path]:
    worktree = root / name
    shutil.copytree(
        ROOT,
        worktree,
        ignore=shutil.ignore_patterns(
            ".git",
            "bootstrap.local.toml",
            "bootstrap-report.json",
            "reverse-bootstrap-report.json",
            "migrate-knowledge-report.json",
            "init-knowledge-report.json",
            "bootstrap-state.json",
        ),
    )
    home = root / f"{name}-home"
    target = root / f"{name}-target"
    home.mkdir()
    target.mkdir()
    write_local_config(worktree, target)
    return worktree, home, target


def snapshot(target: Path) -> dict[str, bytes]:
    return {path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()}


def read_report(worktree: Path) -> dict:
    return json.loads((worktree / "reports" / "init-knowledge-report.json").read_text(encoding="utf-8"))


def allowlist() -> list[str]:
    import tomllib

    data = tomllib.loads((ROOT / "config" / "bootstrap.toml").read_text(encoding="utf-8"))
    return list(data["init"]["files"])


def main() -> int:
    expected = allowlist()
    with tempfile.TemporaryDirectory(prefix="pkw-init-") as directory:
        root = Path(directory)

        worktree, home, target = prepare_fixture(root, "dry-run")
        result = run_init(worktree, home)
        assert result.returncode == 0, result.stderr
        assert snapshot(target) == {}, "dry-runで作成してはならない"
        report = read_report(worktree)
        assert report["mode"] == "dry-run"
        assert [item["path"] for item in report["items"]] == expected
        assert all(item["action"] == "create" for item in report["items"])

        result = run_init(worktree, home, "--apply")
        assert result.returncode == SAFETY_ERROR, result.returncode
        assert snapshot(target) == {}, "--confirmなしで作成してはならない"
        result = run_init(worktree, home, "--confirm")
        assert result.returncode == SAFETY_ERROR, result.returncode

        result = run_init(worktree, home, "--apply", "--confirm")
        assert result.returncode == 0, result.stderr
        created = snapshot(target)
        assert sorted(created) == sorted(expected), sorted(created)
        for relative, data in created.items():
            assert data == (ROOT / relative).read_bytes(), relative
        assert not any(path.startswith("knowledge/00-rules") for path in created)
        assert "knowledge/INDEX.md" not in created
        assert not any(path.startswith("knowledge/04-sources/04.01-periodic-captures/2026") for path in created)
        report = read_report(worktree)
        assert all(item["status"] == "created" for item in report["items"])
        report_text = json.dumps(report, ensure_ascii=False)
        for secret in (str(worktree), str(target), str(home), target.as_posix()):
            assert secret not in report_text, "レポートに絶対パスが含まれている"

        result = run_init(worktree, home, "--apply", "--confirm")
        assert result.returncode == 0, result.stderr
        assert snapshot(target) == created, "再実行で変更してはならない"
        assert all(item["action"] == "skip" for item in read_report(worktree)["items"])

        worktree, home, target = prepare_fixture(root, "existing")
        (target / "knowledge" / "projects").mkdir(parents=True)
        existing = target / "knowledge" / "projects" / "INDEX.md"
        existing.write_text(KEEP, encoding="utf-8", newline="\n")
        result = run_init(worktree, home, "--apply", "--confirm")
        assert result.returncode == 0, result.stderr
        assert existing.read_text(encoding="utf-8") == KEEP, "既存ファイルを上書きしてはならない"
        statuses = {item["path"]: item["status"] for item in read_report(worktree)["items"]}
        assert statuses["knowledge/projects/INDEX.md"] == "exists"
        assert statuses["knowledge/99-archive/README.md"] == "created"

        worktree, home, target = prepare_fixture(root, "outside-allowlist")
        config = worktree / "config" / "bootstrap.toml"
        text = config.read_text(encoding="utf-8")
        config.write_text(text.replace('files = [\n', 'files = [\n  "AGENTS.md",\n', 1), encoding="utf-8", newline="\n")
        result = run_init(worktree, home, "--apply", "--confirm")
        assert result.returncode == SAFETY_ERROR, result.returncode
        assert snapshot(target) == {}, "knowledge/外は作成してはならない"

    print("init_knowledge checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
