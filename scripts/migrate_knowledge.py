"""個人ナレッジを04.00-inboxへ安全に取り込み、manifestで検証する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bootstrap import (
    FALLBACK_EXIT_CODE,
    ROOT,
    BootstrapError,
    load_settings,
    sha256_bytes,
    validate_relative_path,
)

INBOX = Path("knowledge/04-sources/04.00-inbox")
MANIFEST_DIR = INBOX / "manifests"
LARGE_MANIFEST = Path("knowledge/06-large/manifest.json")
RESERVED_FIRST_COMPONENT = "manifests"
MANIFEST_SCHEMA_VERSION = 1
MAX_TEXT_BYTES = 5 * 1024 * 1024
HASH_CHUNK_BYTES = 1024 * 1024
PRINT_LIMIT = 200
MIGRATED_STATUSES = {"copied", "skipped-same"}
PROBLEM_ACTIONS = {"conflict", "excluded", "error"}
QUIET_ACTIONS = {"skip", "verified"}

TEXT_SUFFIXES = {
    ".cfg",
    ".conf",
    ".css",
    ".html",
    ".ini",
    ".json",
    ".markdown",
    ".md",
    ".rst",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SENSITIVE_NAME = re.compile(
    r"(^|[._-])(env|secret|secrets|token|credential|credentials|password|passwd|id_rsa|id_ed25519)([._-]|$)",
    re.IGNORECASE,
)
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".ppk", ".kdbx"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s:/@]+:[^\s@/]+@"),
)
ASSIGNMENT_PATTERN = re.compile(
    r"^\s*(?:[-*+]\s+)?[\"']?[\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)"
    r"[\"']?\s*[:=]\s*[\"']?([^\s\"'#,;]{6,})",
    re.IGNORECASE | re.MULTILINE,
)
PLACEHOLDER_VALUES = {"redacted", "example", "placeholder", "changeme", "none", "null", "true", "false"}

MESSAGES = {
    "text": "04.00-inboxへコピーします",
    "same_hash": "同一内容です",
    "already_migrated": "移行済みです",
    "content_differs": "同名で内容が異なるため取り込みません",
    "parent_is_file": "取り込み先の親がファイルのため取り込みません",
    "parent_is_symlink": "取り込み先の親がリンクのため取り込みません",
    "destination_is_symlink": "取り込み先がリンクのため取り込みません",
    "destination_is_directory": "取り込み先がディレクトリのため取り込みません",
    "destination_not_regular": "取り込み先が通常ファイルではないため取り込みません",
    "destination_unreadable": "取り込み先を読み込めないため取り込みません",
    "sensitive_filename": "秘密情報の可能性があるファイル名のため取り込みません",
    "sensitive_content": "秘密情報の可能性がある内容のため取り込みません",
    "large_or_binary": "06-large/manifest.jsonへ登録します(実体は外部保管)",
    "large_unchanged": "登録済みで変更ありません",
    "large_manifest_mismatch": "登録済みの内容と異なるため更新しません",
    "symlink": "リンクは取り込みません",
    "unreadable": "読み込めないため取り込みません",
    "source_changed": "実行中に移行元が変更されたため取り込みません",
    "destination_appeared": "実行中に取り込み先が作成されたため取り込みません",
    "verified": "一致しました",
    "moved_or_missing": "inboxにありません(分類で移動済みの可能性)",
    "hash_mismatch": "hashが一致しません",
    "local_file_absent": "ローカルにありません(外部保管済みの可能性)",
}


class MigrationError(BootstrapError):
    """migrate_knowledge固有の安全エラー。"""


@dataclass(frozen=True)
class SourceRoot:
    relative: Path
    label: str
    root: Path


@dataclass
class Classified:
    kind: str
    reason: str
    size: int | None = None
    sha256: str | None = None


@dataclass
class MigrationItem:
    action: str
    status: str
    source_label: str
    path: str
    destination: str
    reason: str
    size: int | None = None
    sha256: str | None = None
    source_path: Path | None = None
    done: bool = False

    @property
    def message(self) -> str:
        return MESSAGES.get(self.reason, self.reason)

    def report(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "id": self.source_label,
            "source": self.path,
            "destination": self.destination,
            "status": self.status,
            "reason": self.reason,
            "message": self.message,
            "size": self.size,
            "sha256": self.sha256,
        }


@dataclass
class RunResult:
    plan: list[MigrationItem]
    failure: BootstrapError | None = None


def normalize_name(value: str) -> str:
    return value.casefold()


def sha256_stream(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def safe_detail(detail: str) -> str:
    return detail.replace(str(ROOT), "<repository>").replace(str(Path.home()), "<home>")


def check_item_path(value: str, label: str) -> Path:
    relative = validate_relative_path(value, label)
    if not relative.parts or relative.anchor:
        raise MigrationError("safety_error", f"ホームからの相対パスだけ指定できます: {label}")
    return relative


def deny_set(settings: dict[str, Any]) -> frozenset[str]:
    return frozenset(normalize_name(value) for value in settings["migration"]["deny"])


def reject_denied(parts: tuple[str, ...], denied: frozenset[str]) -> None:
    for part in parts:
        if normalize_name(part) in denied:
            raise MigrationError("safety_error", f"拒否リストに含まれる名前は指定できません: {part}")


def make_label(relative: Path) -> str:
    label = re.sub(r"[^\w.-]+", "-", relative.as_posix()).strip("-.")
    if not label:
        label = "source-" + hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()[:12]
    return label


def ensure_plain_directories(root: Path, relative: Path) -> None:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise MigrationError("safety_error", "取り込み先にリンクが含まれています")
        if current.exists() and not current.is_dir():
            raise MigrationError("safety_error", "取り込み先の構成が不正です")


def resolve_sources(settings: dict[str, Any]) -> list[SourceRoot]:
    raw_sources = settings["migration"]["sources"]
    if not raw_sources:
        raise MigrationError(
            "configuration_error",
            "migration.sourcesが空です。bootstrap.local.tomlにホームからの相対パスを指定してください",
        )
    denied = deny_set(settings)
    home = Path.home().resolve()
    target_root = settings["target_root"]
    protected_areas = (target_root / INBOX, target_root / LARGE_MANIFEST.parent)
    sources: list[SourceRoot] = []
    for raw in raw_sources:
        relative = check_item_path(raw, "migration.sources")
        if normalize_name(relative.parts[0]) == RESERVED_FIRST_COMPONENT:
            raise MigrationError("safety_error", "manifestsは予約名のため移行元にできません")
        reject_denied(relative.parts, denied)
        candidate = home / relative
        if candidate.is_symlink():
            raise MigrationError("safety_error", f"リンクは移行元にできません: {relative.as_posix()}")
        if not candidate.is_dir():
            raise MigrationError("configuration_error", f"移行元フォルダがありません: {relative.as_posix()}")
        resolved = candidate.resolve()
        if home not in resolved.parents:
            raise MigrationError("safety_error", "ホーム外を指す移行元は指定できません")
        reject_denied(resolved.relative_to(home).parts, denied)
        for area in protected_areas:
            if resolved == area or resolved in area.parents or area in resolved.parents:
                raise MigrationError("safety_error", "取り込み先と重なる移行元は指定できません")
        label = make_label(relative)
        for existing in sources:
            if (
                existing.label == label
                or existing.relative == relative
                or existing.relative in relative.parents
                or relative in existing.relative.parents
            ):
                raise MigrationError("configuration_error", "移行元が重複または重なっています")
        sources.append(SourceRoot(relative, label, resolved))
    return sources


def iter_source_files(source: SourceRoot, denied: frozenset[str]):
    """リンクと拒否リストのディレクトリへ入らず、ファイルを列挙する。"""
    for current, directories, files in os.walk(source.root, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name
            for name in sorted(directories)
            if normalize_name(name) not in denied and not (current_path / name).is_symlink()
        ]
        for name in sorted(files):
            yield current_path / name


def is_sensitive_name(path: Path) -> bool:
    return bool(SENSITIVE_NAME.search(path.name)) or path.suffix.lower() in SENSITIVE_SUFFIXES


def is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in PLACEHOLDER_VALUES:
        return True
    if lowered.startswith(("$", "<", "{", "%", "[")):
        return True
    return set(lowered) <= {"x", "*", "."}


def contains_secret(text: str) -> bool:
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        return True
    for match in ASSIGNMENT_PATTERN.finditer(text):
        if not is_placeholder(match.group(1)):
            return True
    return False


def decode_text(data: bytes) -> str | None:
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def classify(path: Path) -> Classified:
    if is_sensitive_name(path):
        return Classified("excluded", "sensitive_filename")
    try:
        size = path.stat().st_size
        if path.suffix.lower() in TEXT_SUFFIXES and size <= MAX_TEXT_BYTES:
            data = path.read_bytes()
            text = decode_text(data)
            if text is not None:
                if contains_secret(text):
                    return Classified("excluded", "sensitive_content")
                return Classified("text", "text", len(data), sha256_bytes(data))
        digest, streamed_size = sha256_stream(path)
    except OSError:
        return Classified("warning", "unreadable")
    return Classified("large", "large_or_binary", streamed_size, digest)


def inspect_destination(inbox_root: Path, destination: Path) -> str:
    relative = destination.relative_to(inbox_root)
    current = inbox_root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            return "parent_is_symlink"
        if current.exists() and not current.is_dir():
            return "parent_is_file"
    if destination.is_symlink():
        return "destination_is_symlink"
    if destination.is_dir():
        return "destination_is_directory"
    if destination.is_file():
        return "file"
    if destination.exists():
        return "destination_not_regular"
    return "missing"


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MigrationError("configuration_error", f"{label}を読み込めません") from exc


def validate_manifest(data: Any, name: str) -> None:
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or not isinstance(data.get("files"), list)
    ):
        raise MigrationError("configuration_error", f"manifestの形式が不正です: {name}")
    for entry in data["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("status"), str):
            raise MigrationError("configuration_error", f"manifestの項目が不正です: {name}")
        check_item_path(entry["path"], f"{name}.path")
        sha = entry.get("sha256")
        if sha is not None and not isinstance(sha, str):
            raise MigrationError("configuration_error", f"manifestのsha256が不正です: {name}")


def load_prior_manifests(manifest_dir: Path) -> list[dict[str, Any]]:
    if not manifest_dir.is_dir():
        return []
    result: list[dict[str, Any]] = []
    for path in sorted(manifest_dir.glob("migration-*.json")):
        if path.is_symlink() or not path.is_file():
            continue
        data = read_json(path, f"過去のmanifest({path.name})")
        validate_manifest(data, path.name)
        result.append(data)
    return result


def migrated_pairs(manifests: list[dict[str, Any]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for data in manifests:
        for entry in data["files"]:
            sha = entry.get("sha256")
            if entry["status"] in MIGRATED_STATUSES and isinstance(sha, str):
                pairs.add((entry["path"], sha))
    return pairs


def load_large_manifest(target_root: Path) -> dict[str, dict[str, Any]]:
    path = target_root / LARGE_MANIFEST
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file():
        raise MigrationError("safety_error", "06-large/manifest.jsonが通常ファイルではありません")
    data = read_json(path, "06-large/manifest.json")
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or not isinstance(data.get("files"), list)
    ):
        raise MigrationError("configuration_error", "06-large/manifest.jsonの形式が不正です")
    entries: dict[str, dict[str, Any]] = {}
    for entry in data["files"]:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not isinstance(entry.get("sha256"), str)
            or not isinstance(entry.get("size"), int)
            or isinstance(entry.get("size"), bool)
        ):
            raise MigrationError("configuration_error", "06-large/manifest.jsonの項目が不正です")
        check_item_path(entry["path"], "06-large/manifest.json.path")
        entries[entry["path"]] = entry
    return entries


def plan_file(
    source: SourceRoot,
    file_path: Path,
    item_path: str,
    inbox_root: Path,
    prior: set[tuple[str, str]],
    large_entries: dict[str, dict[str, Any]],
) -> MigrationItem:
    text_destination = f"{INBOX.as_posix()}/{item_path}"
    large_destination = f"{LARGE_MANIFEST.as_posix()}#{item_path}"

    def make(
        action: str,
        status: str,
        reason: str,
        destination: str = text_destination,
        size: int | None = None,
        sha256: str | None = None,
        keep_source: bool = False,
    ) -> MigrationItem:
        return MigrationItem(
            action,
            status,
            source.label,
            item_path,
            destination,
            reason,
            size,
            sha256,
            file_path if keep_source else None,
        )

    if file_path.is_symlink():
        return make("warning", "skipped-symlink", "symlink")
    classified = classify(file_path)
    if classified.kind == "excluded":
        return make("excluded", "excluded-secret", classified.reason)
    if classified.kind == "warning":
        return make("warning", "skipped-unreadable", classified.reason)
    size = classified.size
    sha = classified.sha256
    if classified.kind == "large":
        entry = large_entries.get(item_path)
        if entry is None:
            return make("register", "registered-large", "large_or_binary", large_destination, size, sha, True)
        if entry["sha256"] == sha and entry["size"] == size:
            return make("skip", "large-unchanged", "large_unchanged", large_destination, size, sha)
        return make("conflict", "conflict", "large_manifest_mismatch", large_destination, size, sha)

    destination = inbox_root / item_path
    state = inspect_destination(inbox_root, destination)
    if state == "file":
        try:
            existing_hash, _ = sha256_stream(destination)
        except OSError:
            return make("conflict", "conflict", "destination_unreadable", size=size, sha256=sha)
        if existing_hash == sha:
            return make("skip", "skipped-same", "same_hash", size=size, sha256=sha)
        if (item_path, str(sha)) in prior:
            return make("skip", "skipped-migrated", "already_migrated", size=size, sha256=sha)
        return make("conflict", "conflict", "content_differs", size=size, sha256=sha)
    if state == "missing":
        if (item_path, str(sha)) in prior:
            return make("skip", "skipped-migrated", "already_migrated", size=size, sha256=sha)
        return make("create", "copied", "text", size=size, sha256=sha, keep_source=True)
    return make("conflict", "conflict", state, size=size, sha256=sha)


def build_plan(
    sources: list[SourceRoot],
    denied: frozenset[str],
    inbox_root: Path,
    prior: set[tuple[str, str]],
    large_entries: dict[str, dict[str, Any]],
) -> list[MigrationItem]:
    plan: list[MigrationItem] = []
    for source in sources:
        for file_path in iter_source_files(source, denied):
            item_path = (source.relative / file_path.relative_to(source.root)).as_posix()
            plan.append(plan_file(source, file_path, item_path, inbox_root, prior, large_entries))
    return plan


def mark(item: MigrationItem, action: str, status: str, reason: str) -> None:
    item.action = action
    item.status = status
    item.reason = reason


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".pkw-migrate.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(text, encoding="utf-8", newline="\n")
        temporary.replace(path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise MigrationError("internal_error", "書き込みに失敗しました") from exc


def apply_plan(plan: list[MigrationItem], inbox_root: Path) -> None:
    for item in plan:
        if item.action != "create" or item.source_path is None:
            continue
        destination = inbox_root / item.path
        try:
            data = item.source_path.read_bytes()
        except OSError:
            mark(item, "warning", "skipped-unreadable", "unreadable")
            continue
        if sha256_bytes(data) != item.sha256:
            mark(item, "conflict", "conflict", "source_changed")
            continue
        if inspect_destination(inbox_root, destination) != "missing":
            mark(item, "conflict", "conflict", "destination_appeared")
            continue
        temporary = destination.with_name(destination.name + ".pkw-migrate.tmp")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(data)
            temporary.replace(destination)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise MigrationError("internal_error", "取り込み先への書き込みに失敗しました") from exc
        item.done = True


def write_large_manifest(
    target_root: Path,
    existing: dict[str, dict[str, Any]],
    plan: list[MigrationItem],
    generated_at: datetime,
) -> None:
    registrations = [item for item in plan if item.action == "register"]
    if not registrations:
        return
    entries = dict(existing)
    for item in registrations:
        entries[item.path] = {
            "path": item.path,
            "size": item.size,
            "sha256": item.sha256,
            "logical_path": f"large/{item.path}",
            "last_confirmed": generated_at.date().isoformat(),
        }
    data = {"schema_version": MANIFEST_SCHEMA_VERSION, "files": [entries[key] for key in sorted(entries)]}
    atomic_write_text(target_root / LARGE_MANIFEST, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def write_manifests(target_root: Path, plan: list[MigrationItem], generated_at: datetime) -> None:
    if not any((item.action == "create" and item.done) or item.action == "register" for item in plan):
        return
    stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    grouped: dict[str, list[MigrationItem]] = {}
    for item in plan:
        if item.action == "warning":
            continue
        grouped.setdefault(item.source_label, []).append(item)
    manifest_dir = target_root / MANIFEST_DIR
    for label in sorted(grouped):
        files = [
            {"path": item.path, "size": item.size, "sha256": item.sha256, "status": item.status}
            for item in sorted(grouped[label], key=lambda value: value.path)
        ]
        data = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "operation": "migrate-knowledge",
            "generated_at": generated_at.isoformat(),
            "source_label": label,
            "destination_root": INBOX.as_posix(),
            "files": files,
        }
        path = manifest_dir / f"migration-{stamp}-{label}.json"
        if path.exists():
            raise MigrationError("safety_error", "同名のmanifestが既に存在します")
        atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def run_migrate(settings: dict[str, Any], applying: bool) -> RunResult:
    target_root = settings["target_root"]
    if target_root.exists() and not target_root.is_dir():
        raise MigrationError("configuration_error", "target.rootがディレクトリではありません")
    ensure_plain_directories(target_root, INBOX)
    ensure_plain_directories(target_root, LARGE_MANIFEST.parent)
    sources = resolve_sources(settings)
    inbox_root = target_root / INBOX
    manifests = load_prior_manifests(target_root / MANIFEST_DIR)
    large_entries = load_large_manifest(target_root)
    plan = build_plan(sources, deny_set(settings), inbox_root, migrated_pairs(manifests), large_entries)
    if not applying:
        return RunResult(plan)
    generated_at = datetime.now(timezone.utc)
    failure: BootstrapError | None = None
    try:
        apply_plan(plan, inbox_root)
    except BootstrapError as exc:
        failure = exc
        for item in plan:
            if item.action == "create" and not item.done:
                item.status = "failed-not-copied"
            elif item.action == "register":
                item.status = "failed-not-registered"
    try:
        if failure is None:
            write_large_manifest(target_root, large_entries, plan, generated_at)
        write_manifests(target_root, plan, generated_at)
    except BootstrapError as exc:
        failure = failure or exc
    return RunResult(plan, failure)


def run_verify(settings: dict[str, Any]) -> list[MigrationItem]:
    target_root = settings["target_root"]
    denied = deny_set(settings)
    home = Path.home().resolve()
    manifests = load_prior_manifests(target_root / MANIFEST_DIR)
    large_entries = load_large_manifest(target_root)
    if not manifests and not large_entries:
        raise MigrationError("configuration_error", "検証するmanifestがありません")
    inbox_root = target_root / INBOX
    plan: list[MigrationItem] = []
    for data in manifests:
        label = str(data.get("source_label", ""))
        for entry in sorted(data["files"], key=lambda value: value["path"]):
            sha = entry.get("sha256")
            if entry["status"] not in MIGRATED_STATUSES or not isinstance(sha, str):
                continue
            path = entry["path"]
            relative = check_item_path(path, "manifest.path")
            display = f"{INBOX.as_posix()}/{path}"
            size = entry.get("size") if isinstance(entry.get("size"), int) else None
            state = inspect_destination(inbox_root, inbox_root / relative)
            if state == "missing":
                plan.append(MigrationItem("warning", "moved", label, path, display, "moved_or_missing", size, sha))
            elif state != "file":
                plan.append(MigrationItem("error", "mismatch", label, path, display, state, size, sha))
            else:
                try:
                    digest, _ = sha256_stream(inbox_root / relative)
                except OSError:
                    plan.append(MigrationItem("warning", "unreadable", label, path, display, "unreadable", size, sha))
                    continue
                if digest == sha:
                    plan.append(MigrationItem("verified", "verified", label, path, display, "verified", size, sha))
                else:
                    plan.append(MigrationItem("error", "mismatch", label, path, display, "hash_mismatch", size, sha))
    for path in sorted(large_entries):
        entry = large_entries[path]
        relative = check_item_path(path, "06-large/manifest.json.path")
        reject_denied(relative.parts, denied)
        display = f"{LARGE_MANIFEST.as_posix()}#{path}"
        sha = entry["sha256"]
        size = entry["size"]
        local = home / relative
        if local.is_symlink() or not local.is_file() or home not in local.resolve().parents:
            plan.append(MigrationItem("warning", "absent", "large", path, display, "local_file_absent", size, sha))
            continue
        try:
            digest, _ = sha256_stream(local)
        except OSError:
            plan.append(MigrationItem("warning", "unreadable", "large", path, display, "unreadable", size, sha))
            continue
        if digest == sha:
            plan.append(MigrationItem("verified", "verified", "large", path, display, "verified", size, sha))
        else:
            plan.append(MigrationItem("error", "mismatch", "large", path, display, "hash_mismatch", size, sha))
    return plan


def build_report(
    settings: dict[str, Any],
    plan: list[MigrationItem],
    mode: str,
    failure: BootstrapError | None = None,
) -> dict[str, Any]:
    if failure is not None:
        result_key = failure.key if failure.key in settings["codes"] else "internal_error"
        status = "error"
        message = settings["messages"].get(result_key, "移行処理でエラーが発生しました")
    elif any(item.action in PROBLEM_ACTIONS for item in plan):
        result_key, status, message = "conflict", "conflict", "除外または不一致の項目があります"
    else:
        result_key, status, message = "success", "success", "移行処理を完了しました"
    return {
        "schema_version": 1,
        "operation": "migrate-knowledge",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": settings["profile"],
        "mode": mode,
        "status": status,
        "result_key": result_key,
        "exit_code": settings["codes"].get(result_key, FALLBACK_EXIT_CODE),
        "message": message,
        "items": [item.report() for item in plan],
    }


def write_report(settings: dict[str, Any], report: dict[str, Any]) -> None:
    report_path = settings["migrate_report_json"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def print_report(settings: dict[str, Any], report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    print(f"mode: {report['mode']}")
    counts = Counter(item["action"] for item in report["items"])
    summary = ", ".join(f"{name}={counts[name]}" for name in sorted(counts)) or "items=0"
    print(f"summary: {summary}")
    shown = 0
    hidden = 0
    for item in report["items"]:
        if item["action"] in QUIET_ACTIONS:
            continue
        if shown >= PRINT_LIMIT:
            hidden += 1
            continue
        print(f"{item['action'].upper():10} {item['source']} - {item['message']}")
        shown += 1
    if hidden:
        print(f"... 他{hidden}件はレポートを参照してください")
    print(f"report: {settings['migrate_report_json'].relative_to(ROOT).as_posix()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="個人ナレッジを04.00-inboxへ安全に取り込む")
    parser.add_argument("--apply", action="store_true", help="計画を取り込み先へ反映する")
    parser.add_argument("--confirm", action="store_true", help="--applyの明示確認")
    parser.add_argument("--verify", action="store_true", help="manifestと取り込み先を照合する(読み取り専用)")
    args = parser.parse_args(argv)
    mode = "verify" if args.verify else ("apply" if args.apply else "dry-run")
    settings: dict[str, Any] | None = None
    try:
        settings = load_settings(create_local_config=False)
        if args.verify and (args.apply or args.confirm):
            raise MigrationError("safety_error", "--verifyは--apply/--confirmと同時に指定できません")
        if args.confirm and not args.apply:
            raise MigrationError("safety_error", "--confirmは--applyと同時に指定してください")
        if args.apply and not args.confirm:
            raise MigrationError("safety_error", "適用には--confirmが必要です")
        failure: BootstrapError | None = None
        if args.verify:
            plan = run_verify(settings)
        else:
            result = run_migrate(settings, bool(args.apply))
            plan, failure = result.plan, result.failure
        report = build_report(settings, plan, mode, failure)
        write_report(settings, report)
        print_report(settings, report)
        if failure is not None:
            print(f"{report['message']}: {safe_detail(failure.detail)}", file=sys.stderr)
        return int(report["exit_code"])
    except BootstrapError as exc:
        if settings is None:
            print(f"migrate-knowledge設定エラー: {safe_detail(exc.detail)}", file=sys.stderr)
            return FALLBACK_EXIT_CODE
        report = build_report(settings, [], mode, exc)
        try:
            write_report(settings, report)
        except OSError:
            pass
        print(f"{report['message']}: {safe_detail(exc.detail)}", file=sys.stderr)
        return int(report["exit_code"])
    except Exception as exc:  # pragma: no cover - 最終フォールバック
        print(f"migrate-knowledge内部エラー: {safe_detail(str(exc))}", file=sys.stderr)
        return FALLBACK_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
