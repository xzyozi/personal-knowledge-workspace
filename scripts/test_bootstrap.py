"""bootstrapのfixture検証。外部接続とユーザー環境を変更しない。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_home_config(worktree: Path, target: Path, allow_home: bool) -> None:
    config = worktree / "config" / "bootstrap.local.toml"
    allow = "allow_home = true\n" if allow_home else ""
    config.write_text(
        "[profile]\n"
        "name = \"default\"\n\n"
        "[target]\n"
        f"root = \"{target.as_posix()}\"\n"
        f"{allow}\n"
        "[report.server]\n"
        "port = 8765\n",
        encoding="utf-8",
        newline="\n",
    )


def run_bootstrap_with_home(worktree: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(worktree / "scripts" / "bootstrap.py"), *args],
        cwd=worktree,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


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
        [sys.executable, "-X", "utf8", str(worktree / "scripts" / "bootstrap.py"), *args],
        cwd=worktree,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def prepare_worktree(root: Path, name: str) -> Path:
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
            "bootstrap-state.json",
        ),
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


def assert_update_case(root: Path) -> None:
    worktree = prepare_worktree(root, "update-worktree")
    target = root / "update-target"
    write_local_config(worktree, target)
    first = run_bootstrap(worktree, "--apply", "--confirm")
    assert first.returncode == 0, first.stderr

    template = worktree / "AGENTS.md"
    deployed = target / "AGENTS.md"
    template.write_bytes(template.read_bytes() + b"\n# template update 1\n")
    dry_run = run_bootstrap(worktree)
    assert dry_run.returncode == 0, dry_run.stderr
    report = json.loads((worktree / "reports" / "bootstrap-report.json").read_text(encoding="utf-8"))
    assert any(item["destination"] == "AGENTS.md" and item["action"] == "update" for item in report["items"])
    assert deployed.read_bytes() != template.read_bytes(), "dry-run must not update the target"

    updated = run_bootstrap(worktree, "--apply", "--confirm")
    assert updated.returncode == 0, updated.stderr
    assert deployed.read_bytes() == template.read_bytes()

    deployed.write_bytes(deployed.read_bytes() + b"\n# user edit\n")
    template.write_bytes(template.read_bytes() + b"\n# template update 2\n")
    conflict = run_bootstrap(worktree, "--apply", "--confirm")
    assert conflict.returncode == 10, conflict.stderr
    assert deployed.read_bytes().endswith(b"# user edit\n"), "user edits must be kept"
    assert b"template update 2" not in deployed.read_bytes()


def assert_home_target_case(root: Path) -> None:
    worktree = prepare_worktree(root, "home-worktree")
    home = root / "fixture-home"
    home.mkdir()

    write_home_config(worktree, home, allow_home=False)
    refused = run_bootstrap_with_home(worktree, home)
    assert refused.returncode == 1, refused.stderr
    assert "allow_home" in refused.stderr
    assert not (home / "AGENTS.md").exists()

    write_home_config(worktree, root, allow_home=True)
    above_home = run_bootstrap_with_home(worktree, home)
    assert above_home.returncode == 1, above_home.stderr
    assert not (root / "AGENTS.md").exists()

    user_file = home / "AGENTS.md"
    user_file.write_text("user-owned content\n", encoding="utf-8", newline="\n")
    write_home_config(worktree, home, allow_home=True)
    conflict = run_bootstrap_with_home(worktree, home, "--apply", "--confirm")
    assert conflict.returncode == 10, conflict.stderr
    assert user_file.read_text(encoding="utf-8") == "user-owned content\n"
    assert not (home / "GEMINI.md").exists(), "conflict must stop the whole apply"

    user_file.unlink()
    applied = run_bootstrap_with_home(worktree, home, "--apply", "--confirm")
    assert applied.returncode == 0, applied.stderr
    assert (home / "AGENTS.md").is_file()
    assert (home / ".kiro" / "steering" / "knowledge-entry.md").is_file()
    assert (home / "knowledge" / "INDEX.md").is_file()
    assert (worktree / "reports" / "bootstrap-state.json").is_file()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkw-bootstrap-") as directory:
        root = Path(directory)
        assert_success_case(root)
        assert_conflict_case(root)
        assert_update_case(root)
        assert_home_target_case(root)
    print("bootstrap fixture validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
