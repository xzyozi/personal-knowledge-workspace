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


def managed_source(body: str) -> str:
    return (
        "# Fixture entry\n\n"
        '<!-- pkw:managed:start id="fixture-managed" revision="1" -->\n'
        f"{body}"
        '<!-- pkw:managed:end id="fixture-managed" -->\n'
    )


def add_managed_target(worktree: Path) -> None:
    config = worktree / "config" / "bootstrap.toml"
    text = config.read_text(encoding="utf-8")
    target = (
        "[[profiles.default.targets]]\n"
        'id = "fixture-managed"\n'
        'source = "fixture-managed.md"\n'
        'destination = "fixture-managed.md"\n'
        'mode = "managed-block"\n'
        "revision = 1\n\n"
    )
    assert "[profiles.personal]" in text
    config.write_text(text.replace("[profiles.personal]", target + "[profiles.personal]", 1), encoding="utf-8", newline="\n")


def assert_managed_block_case(root: Path) -> None:
    worktree = prepare_worktree(root, "managed-worktree")
    add_managed_target(worktree)
    source = worktree / "fixture-managed.md"
    target = root / "managed-target"
    target.mkdir()
    write_local_config(worktree, target)
    deployed = target / "fixture-managed.md"

    # 利用者のファイルがあり、管理ブロックがない: 末尾へ追記する。dry-runでは変更しない
    user_text = "# My notes\n\nmy own text\n"
    deployed.write_text(user_text, encoding="utf-8", newline="\n")
    source.write_text(managed_source("managed body v1\n"), encoding="utf-8", newline="\n")
    dry_run = run_bootstrap(worktree)
    assert dry_run.returncode == 0, dry_run.stderr
    assert deployed.read_text(encoding="utf-8") == user_text, "dry-run must not append"
    appended = run_bootstrap(worktree, "--apply", "--confirm")
    assert appended.returncode == 0, appended.stderr
    content = deployed.read_text(encoding="utf-8")
    assert content.startswith(user_text + "\n"), "user text must stay, followed by a blank line"
    assert "managed body v1" in content
    assert 'sha256="' in content, "the deployed marker must record the body hash"
    assert content.count("pkw:managed:start") == 1

    # テンプレートのブロックを更新: 利用者の記述は残る
    source.write_text(managed_source("managed body v2\n"), encoding="utf-8", newline="\n")
    updated = run_bootstrap(worktree, "--apply", "--confirm")
    assert updated.returncode == 0, updated.stderr
    content = deployed.read_text(encoding="utf-8")
    assert content.startswith(user_text), "user text must stay"
    assert "managed body v2" in content and "managed body v1" not in content
    assert content.count("pkw:managed:start") == 1

    # 利用者がブロック内を編集: 衝突にして、更新しない
    edited = content.replace("managed body v2", "managed body EDITED")
    deployed.write_text(edited, encoding="utf-8", newline="\n")
    source.write_text(managed_source("managed body v3\n"), encoding="utf-8", newline="\n")
    conflict = run_bootstrap(worktree, "--apply", "--confirm")
    assert conflict.returncode == 10, conflict.stderr
    assert deployed.read_text(encoding="utf-8") == edited, "edits inside the block must be kept"

    # 終了マーカーがない: 追記せず衝突にする
    broken = 'my text\n<!-- pkw:managed:start id="fixture-managed" revision="1" -->\nno end marker\n'
    deployed.write_text(broken, encoding="utf-8", newline="\n")
    incomplete = run_bootstrap(worktree)
    assert incomplete.returncode == 10, incomplete.stderr
    assert deployed.read_text(encoding="utf-8") == broken

    # ファイルがない: 新規作成し、hashつきのマーカーを書く
    deployed.unlink()
    created = run_bootstrap(worktree, "--apply", "--confirm")
    assert created.returncode == 0, created.stderr
    content = deployed.read_text(encoding="utf-8")
    assert content.startswith("# Fixture entry")
    assert "managed body v3" in content
    assert 'sha256="' in content


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
        assert_managed_block_case(root)
        assert_home_target_case(root)
    print("bootstrap fixture validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
