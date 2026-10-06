"""bootstrapのfixture検証。外部接続とユーザー環境を変更しない。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_local_config(worktree: Path, target: Path) -> None:
    config = worktree / "config" / "bootstrap.local.toml"
    config.write_text(
        "[profile]\n"
        "name = \"default\"\n\n"
        "[target]\n"
        f"root = \"{target.as_posix()}\"\n\n"
        "[storage.knowledge]\n"
        "provider = \"local\"\n"
        "namespace = \"fixture\"\n"
        "prefix = \"knowledge\"\n\n"
        "[report.server]\n"
        "port = 8765\n",
        encoding="utf-8",
        newline="\n",
    )


def run_bootstrap(worktree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(worktree / "scripts" / "bootstrap.py"), *args],
        cwd=worktree,
        text=True,
        capture_output=True,
        check=False,
    )


def prepare_worktree(root: Path, name: str) -> Path:
    worktree = root / name
    shutil.copytree(
        ROOT,
        worktree,
        ignore=shutil.ignore_patterns(".git", "bootstrap.local.toml", "bootstrap-report.json"),
    )
    return worktree


def assert_success_case(root: Path) -> None:
    worktree = prepare_worktree(root, "success-worktree")
    target = root / "empty-target"
    write_local_config(worktree, target)
    dry_run = run_bootstrap(worktree)
    assert dry_run.returncode == 0, dry_run.stderr
    assert not target.exists(), "dry-run must not create target files"
    apply = run_bootstrap(worktree, "--apply", "--confirm")
    assert apply.returncode == 0, apply.stderr
    assert (target / "AGENTS.md").is_file()
    assert (target / ".kiro" / "steering" / "knowledge-entry.md").is_file()
    report = json.loads((worktree / "reports" / "bootstrap-report.json").read_text(encoding="utf-8"))
    assert report["status"] == "success"


def assert_conflict_case(root: Path) -> None:
    worktree = prepare_worktree(root, "conflict-worktree")
    target = root / "conflict-target"
    target.mkdir()
    original = "user-owned content\n"
    (target / "AGENTS.md").write_text(original, encoding="utf-8", newline="\n")
    write_local_config(worktree, target)
    result = run_bootstrap(worktree)
    assert result.returncode == 10, result.stderr
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == original
    report = json.loads((worktree / "reports" / "bootstrap-report.json").read_text(encoding="utf-8"))
    assert report["status"] == "conflict"
    assert any(item["destination"] == "AGENTS.md" for item in report["items"])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkw-bootstrap-") as directory:
        root = Path(directory)
        assert_success_case(root)
        assert_conflict_case(root)
    print("bootstrap fixture validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
