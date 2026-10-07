"""migrate_knowledgeのfixture検証。CIでのみ実行し、実ユーザー環境を変更しない。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = Path("knowledge/04-sources/04.00-inbox")
SECRET_VALUE = "hunter2hunter2"


def write_local_config(worktree: Path, target: Path, sources: list[str]) -> None:
    config = worktree / "config" / "bootstrap.local.toml"
    config.write_text(
        "[profile]\n"
        'name = "default"\n\n'
        "[target]\n"
        f"root = {json.dumps(target.as_posix())}\n\n"
        "[migration]\n"
        f"sources = {json.dumps(sources)}\n\n"
        "[report.server]\n"
        "port = 8765\n",
        encoding="utf-8",
        newline="\n",
    )


def run_migrate(worktree: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(worktree / "scripts" / "migrate_knowledge.py"), *args],
        cwd=worktree,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def prepare_fixture(root: Path, name: str, sources: list[str]) -> tuple[Path, Path, Path]:
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
    home = root / f"{name}-home"
    target = root / f"{name}-target"
    home.mkdir()
    write_local_config(worktree, target, sources)
    return worktree, home, target


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_report(worktree: Path) -> dict:
    return json.loads((worktree / "reports" / "migrate-knowledge-report.json").read_text(encoding="utf-8"))


def actions_by_source(report: dict) -> dict[str, str]:
    return {item["source"]: item["action"] for item in report["items"]}


def manifest_paths(target: Path) -> list[Path]:
    return sorted((target / INBOX / "manifests").glob("migration-*.json"))


def assert_dry_run_apply_and_verify(root: Path) -> None:
    worktree, home, target = prepare_fixture(root, "basic", ["Documents/notes"])
    notes = home / "Documents" / "notes"
    write_file(notes / "a.md", b"# a\n")
    write_file(notes / "sub" / "b.txt", "日本語のメモ\n".encode("utf-8"))
    write_file(notes / "image.png", b"\x89PNG\x00binary")
    write_file(notes / ".git" / "config", b"[core]\n")

    dry_run = run_migrate(worktree, home)
    assert dry_run.returncode == 0, dry_run.stderr
    assert not target.exists(), "dry-run must not create the target"
    assert actions_by_source(read_report(worktree)) == {
        "Documents/notes/a.md": "create",
        "Documents/notes/image.png": "register",
        "Documents/notes/sub/b.txt": "create",
    }

    without_confirm = run_migrate(worktree, home, "--apply")
    assert without_confirm.returncode == 30, without_confirm.stderr
    assert not target.exists()

    applied = run_migrate(worktree, home, "--apply", "--confirm")
    assert applied.returncode == 0, applied.stderr
    inbox = target / INBOX
    assert (inbox / "Documents" / "notes" / "a.md").read_bytes() == b"# a\n"
    assert (inbox / "Documents" / "notes" / "sub" / "b.txt").read_bytes() == "日本語のメモ\n".encode("utf-8")
    assert not (inbox / "Documents" / "notes" / "image.png").exists()
    assert not (inbox / "Documents" / "notes" / ".git").exists()
    assert (notes / "a.md").read_bytes() == b"# a\n", "source must stay untouched"

    manifests = manifest_paths(target)
    assert len(manifests) == 1
    assert manifests[0].name.endswith("-Documents-notes.json")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert {entry["path"]: entry["status"] for entry in manifest["files"]} == {
        "Documents/notes/a.md": "copied",
        "Documents/notes/image.png": "registered-large",
        "Documents/notes/sub/b.txt": "copied",
    }
    large = json.loads((target / "knowledge" / "06-large" / "manifest.json").read_text(encoding="utf-8"))
    assert [entry["path"] for entry in large["files"]] == ["Documents/notes/image.png"]
    assert large["files"][0]["logical_path"] == "large/Documents/notes/image.png"

    again = run_migrate(worktree, home, "--apply", "--confirm")
    assert again.returncode == 0, again.stderr
    assert len(manifest_paths(target)) == 1, "re-run must not create another manifest"

    verify = run_migrate(worktree, home, "--verify")
    assert verify.returncode == 0, verify.stderr
    verified = read_report(worktree)
    assert verified["mode"] == "verify"
    assert {item["action"] for item in verified["items"]} == {"verified"}


def assert_moved_files_are_not_recopied(root: Path) -> None:
    worktree, home, target = prepare_fixture(root, "moved", ["Documents/notes"])
    write_file(home / "Documents" / "notes" / "a.md", b"# a\n")
    applied = run_migrate(worktree, home, "--apply", "--confirm")
    assert applied.returncode == 0, applied.stderr

    inbox_file = target / INBOX / "Documents" / "notes" / "a.md"
    classified = target / "knowledge" / "02-facts" / "a.md"
    classified.parent.mkdir(parents=True, exist_ok=True)
    inbox_file.replace(classified)

    again = run_migrate(worktree, home, "--apply", "--confirm")
    assert again.returncode == 0, again.stderr
    assert not inbox_file.exists(), "classified files must not return to the inbox"
    items = read_report(worktree)["items"]
    assert [(item["action"], item["reason"]) for item in items] == [("skip", "already_migrated")]

    verify = run_migrate(worktree, home, "--verify")
    assert verify.returncode == 0, verify.stderr
    assert {item["action"] for item in read_report(worktree)["items"]} == {"warning"}


def assert_conflicts_and_secrets_are_excluded(root: Path) -> None:
    worktree, home, target = prepare_fixture(root, "exclude", ["Documents/notes"])
    notes = home / "Documents" / "notes"
    write_file(notes / "ok.md", b"ok\n")
    write_file(notes / "conflict.md", b"mine\n")
    write_file(notes / "diary.md", f'password = "{SECRET_VALUE}"\n'.encode("utf-8"))
    write_file(notes / "token.md", b"plain\n")
    inbox = target / INBOX / "Documents" / "notes"
    write_file(inbox / "conflict.md", b"different\n")

    result = run_migrate(worktree, home, "--apply", "--confirm")
    assert result.returncode == 10, result.stderr
    assert (inbox / "ok.md").read_bytes() == b"ok\n"
    assert (inbox / "conflict.md").read_bytes() == b"different\n"
    assert not (inbox / "diary.md").exists()
    assert not (inbox / "token.md").exists()

    actions = actions_by_source(read_report(worktree))
    assert actions["Documents/notes/ok.md"] == "create"
    assert actions["Documents/notes/conflict.md"] == "conflict"
    assert actions["Documents/notes/diary.md"] == "excluded"
    assert actions["Documents/notes/token.md"] == "excluded"

    recorded = [result.stdout, result.stderr, (worktree / "reports" / "migrate-knowledge-report.json").read_text(encoding="utf-8")]
    recorded.extend(path.read_text(encoding="utf-8") for path in manifest_paths(target))
    assert SECRET_VALUE not in "\n".join(recorded), "secret values must never be recorded"


def assert_unsafe_sources_are_rejected(root: Path) -> None:
    worktree, home, target = prepare_fixture(root, "unsafe", ["Documents"])
    (home / "Documents").mkdir()
    for source in [".ssh/keys", "../outside", "manifests/notes", ".", str(home)]:
        write_local_config(worktree, target, [source])
        result = run_migrate(worktree, home)
        assert result.returncode == 30, (source, result.stderr)
        assert not target.exists()

    write_local_config(worktree, target, [])
    empty = run_migrate(worktree, home)
    assert empty.returncode == 20, empty.stderr


def assert_verify_detects_changes(root: Path) -> None:
    worktree, home, target = prepare_fixture(root, "verify", ["Documents/notes"])
    write_file(home / "Documents" / "notes" / "a.md", b"# a\n")
    applied = run_migrate(worktree, home, "--apply", "--confirm")
    assert applied.returncode == 0, applied.stderr

    (target / INBOX / "Documents" / "notes" / "a.md").write_bytes(b"# changed\n")
    verify = run_migrate(worktree, home, "--verify")
    assert verify.returncode == 10, verify.stderr
    items = read_report(worktree)["items"]
    assert [(item["action"], item["reason"]) for item in items] == [("error", "hash_mismatch")]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkw-migrate-knowledge-") as directory:
        root = Path(directory)
        assert_dry_run_apply_and_verify(root)
        assert_moved_files_are_not_recopied(root)
        assert_conflicts_and_secrets_are_excluded(root)
        assert_unsafe_sources_are_rejected(root)
        assert_verify_detects_changes(root)
    print("migrate-knowledge fixture validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
