"""reverse-bootstrapのfixture検証。CIでのみ実行し、実ユーザー環境を変更しない。"""

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


def run_script(worktree: Path, script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(worktree / "scripts" / script), *args],
        cwd=worktree,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def run_git(worktree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(worktree), *args],
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
            "bootstrap-state.json",
        ),
    )
    return worktree


def initialize_git(worktree: Path) -> None:
    result = run_git(worktree, "init")
    assert result.returncode == 0, result.stderr
    result = run_git(worktree, "add", "--all")
    assert result.returncode == 0, result.stderr
    result = run_git(
        worktree,
        "-c",
        "user.name=reverse-bootstrap fixture",
        "-c",
        "user.email=reverse-bootstrap-fixture@example.invalid",
        "commit",
        "-m",
        "fixture",
    )
    assert result.returncode == 0, result.stderr


def prepare_fixture(root: Path, name: str) -> tuple[Path, Path]:
    worktree = prepare_worktree(root, name)
    target = root / f"{name}-target"
    write_local_config(worktree, target)
    initialize_git(worktree)
    result = run_script(worktree, "bootstrap.py", "--apply", "--confirm")
    assert result.returncode == 0, result.stderr
    assert (worktree / "reports" / "bootstrap-state.json").is_file()
    return worktree, target


def read_reverse_report(worktree: Path) -> dict:
    return json.loads((worktree / "reports" / "reverse-bootstrap-report.json").read_text(encoding="utf-8"))


def assert_dry_run_and_apply(root: Path) -> None:
    worktree, target = prepare_fixture(root, "change-worktree")
    source = worktree / "AGENTS.md"
    original = source.read_bytes()
    destination = target / "AGENTS.md"
    destination.write_bytes(destination.read_bytes() + b"\n# verified in fixture\n")

    dry_run = run_script(worktree, "reverse_bootstrap.py")
    assert dry_run.returncode == 0, dry_run.stderr
    assert source.read_bytes() == original
    report = read_reverse_report(worktree)
    assert report["operation"] == "reverse-bootstrap"
    assert report["mode"] == "dry-run"
    assert any(item["action"] == "update" and item["source"] == "AGENTS.md" for item in report["items"])

    apply = run_script(worktree, "reverse_bootstrap.py", "--apply", "--confirm")
    assert apply.returncode == 0, apply.stderr
    assert source.read_bytes() == destination.read_bytes()


def assert_new_file_is_reversed(root: Path) -> None:
    worktree, target = prepare_fixture(root, "new-file-worktree")
    destination = target / "knowledge" / "00-rules" / "new-rule.md"
    destination.write_text("# New rule\n", encoding="utf-8", newline="\n")

    result = run_script(worktree, "reverse_bootstrap.py", "--apply", "--confirm")
    assert result.returncode == 0, result.stderr
    assert (worktree / "knowledge" / "00-rules" / "new-rule.md").read_text(encoding="utf-8") == "# New rule\n"


def assert_delete_candidate_is_git_visible(root: Path) -> None:
    worktree, target = prepare_fixture(root, "delete-worktree")
    destination = target / "knowledge" / "00-rules" / "00.04-classification-rule.md"
    source = worktree / "knowledge" / "00-rules" / "00.04-classification-rule.md"
    destination.unlink()

    dry_run = run_script(worktree, "reverse_bootstrap.py")
    assert dry_run.returncode == 0, dry_run.stderr
    report = read_reverse_report(worktree)
    assert any(item["action"] == "delete-candidate" for item in report["items"])
    assert source.is_file()

    apply = run_script(worktree, "reverse_bootstrap.py", "--apply", "--confirm")
    assert apply.returncode == 0, apply.stderr
    assert not source.exists()
    assert any(item["action"] == "delete" for item in read_reverse_report(worktree)["items"])


def assert_safety_guards(root: Path) -> None:
    worktree = prepare_worktree(root, "missing-state-worktree")
    target = root / "missing-state-target"
    write_local_config(worktree, target)
    initialize_git(worktree)
    missing_state = run_script(worktree, "reverse_bootstrap.py")
    assert missing_state.returncode == 30

    dirty_worktree, dirty_target = prepare_fixture(root, "dirty-worktree")
    (dirty_worktree / "AGENTS.md").write_text("dirty\n", encoding="utf-8", newline="\n")
    dirty = run_script(dirty_worktree, "reverse_bootstrap.py")
    assert dirty.returncode == 30
    assert "AGENTS.md" not in dirty.stdout

    secret_worktree, secret_target = prepare_fixture(root, "secret-worktree")
    (secret_target / "AGENTS.md").write_text('api_key = "supersecretvalue"\n', encoding="utf-8", newline="\n")
    secret = run_script(secret_worktree, "reverse_bootstrap.py")
    assert secret.returncode == 30
    assert (secret_worktree / "AGENTS.md").read_text(encoding="utf-8") != 'api_key = "supersecretvalue"\n'


def assert_managed_block_is_excluded(root: Path) -> None:
    worktree = prepare_worktree(root, "managed-worktree")
    managed = (
        "# Fixture entry\n\n"
        '<!-- pkw:managed:start id="fixture-managed" revision="1" -->\n'
        "managed body\n"
        '<!-- pkw:managed:end id="fixture-managed" -->\n'
    )
    source = worktree / "fixture-managed.md"
    source.write_text(managed, encoding="utf-8", newline="\n")
    config = worktree / "config" / "bootstrap.toml"
    text = config.read_text(encoding="utf-8")
    target_entry = (
        "[[profiles.default.targets]]\n"
        'id = "fixture-managed"\n'
        'source = "fixture-managed.md"\n'
        'destination = "fixture-managed.md"\n'
        'mode = "managed-block"\n'
        "revision = 1\n\n"
    )
    assert "[profiles.personal]" in text
    config.write_text(text.replace("[profiles.personal]", target_entry + "[profiles.personal]", 1), encoding="utf-8", newline="\n")
    target = root / "managed-target"
    write_local_config(worktree, target)
    initialize_git(worktree)
    deployed_result = run_script(worktree, "bootstrap.py", "--apply", "--confirm")
    assert deployed_result.returncode == 0, deployed_result.stderr

    deployed = target / "fixture-managed.md"
    deployed.write_text(deployed.read_text(encoding="utf-8") + "\nmy personal text\n", encoding="utf-8", newline="\n")
    dry_run = run_script(worktree, "reverse_bootstrap.py")
    assert dry_run.returncode == 0, dry_run.stderr
    items = read_reverse_report(worktree)["items"]
    assert any(item["id"] == "fixture-managed" and item["reason"] == "managed_block_excluded" for item in items)

    applied = run_script(worktree, "reverse_bootstrap.py", "--apply", "--confirm")
    assert applied.returncode == 0, applied.stderr
    assert source.read_text(encoding="utf-8") == managed, "personal text must never reach the template"
    status = run_git(worktree, "status", "--porcelain")
    assert status.returncode == 0, status.stderr
    assert status.stdout.strip() == "", status.stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkw-reverse-bootstrap 日本語 ") as directory:
        root = Path(directory)
        assert_dry_run_and_apply(root)
        assert_new_file_is_reversed(root)
        assert_delete_candidate_is_git_visible(root)
        assert_safety_guards(root)
        assert_managed_block_is_excluded(root)
    print("reverse-bootstrap fixture validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
