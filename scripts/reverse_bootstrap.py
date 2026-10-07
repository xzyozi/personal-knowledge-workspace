"""検証済みテンプレート変更をリポジトリの作業ツリーへ戻す。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bootstrap import (
    FALLBACK_EXIT_CODE,
    ROOT,
    STATE_SCHEMA_VERSION,
    BootstrapError,
    TargetSpec,
    load_settings,
    sha256_bytes,
    validate_relative_path,
)

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
    r"(^|[._-])(env|secret|secrets|token|credential|credentials|password|passwd)([._-]|$)",
    re.IGNORECASE,
)
SENSITIVE_SUFFIXES = (".key", ".p12", ".pem", ".pfx")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN(?: [A-Z0-9]+)* PRIVATE KEY-----")
SENSITIVE_ASSIGNMENT = re.compile(
    r"^\s*(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|access[_-]?key)\s*[:=]\s*['\"]?([^\s'\"#]+)",
    re.IGNORECASE,
)
REDACTED_VALUES = {"[redacted]", "redacted", "example", "placeholder", "changeme"}


@dataclass
class ReverseItem:
    action: str
    target_id: str
    source: str
    destination: str
    mode: str
    revision: int
    sha256: str
    reason: str
    message: str
    payload: bytes | None = None
    original: bytes | None = None

    def report(self, applying: bool) -> dict[str, Any]:
        action = "delete" if applying and self.action == "delete-candidate" else self.action
        return {
            "action": action,
            "id": self.target_id,
            "source": self.source,
            "destination": self.destination,
            "mode": self.mode,
            "revision": self.revision,
            "sha256": self.sha256,
            "reason": self.reason,
            "message": self.message,
        }


@dataclass(frozen=True)
class Mapping:
    spec: TargetSpec
    source: Path
    source_rel: Path
    destination: Path
    destination_rel: Path


class ReverseError(BootstrapError):
    """reverse-bootstrap固有の安全エラー。"""


def relative_repository_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def resolve_repository_path(relative: Path, label: str) -> Path:
    path = (ROOT / relative).resolve()
    root = ROOT.resolve()
    if path != root and root not in path.parents:
        raise ReverseError("safety_error", f"リポジトリ外のパスです: {label}")
    return path


def resolve_target_path(root: Path, relative: Path, label: str) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ReverseError("safety_error", f"target外の相対パスです: {label}")
    path = root / relative
    resolved = path.resolve()
    resolved_root = root.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ReverseError("safety_error", f"target外のパスです: {label}")
    return path


def ensure_clean_repository() -> None:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise ReverseError("safety_error", "Git作業ツリーを確認できません")
    if result.stdout.strip():
        raise ReverseError("safety_error", "Git作業ツリーに未コミット差分があります")


def read_state(settings: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    state_path = settings["state_path"]
    if not state_path.is_file():
        raise ReverseError("safety_error", "bootstrap-state.jsonがありません。先にbootstrapを実行してください")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReverseError("configuration_error", "bootstrap-state.jsonを読み込めません") from exc
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ReverseError("configuration_error", "bootstrap-state.jsonのschema_versionが未対応です")
    if state.get("profile") != "default":
        raise ReverseError("configuration_error", "default profileのbootstrap-state.jsonが必要です")
    raw_files = state.get("applied_files")
    if not isinstance(raw_files, list):
        raise ReverseError("configuration_error", "bootstrap-state.jsonのapplied_filesが不正です")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in raw_files:
        if not isinstance(raw, dict):
            raise ReverseError("configuration_error", "bootstrap-state.jsonの項目が不正です")
        try:
            source = validate_relative_path(str(raw["source"]), "state.source")
            destination = validate_relative_path(str(raw["destination"]), "state.destination")
        except (KeyError, BootstrapError) as exc:
            raise ReverseError("configuration_error", "bootstrap-state.jsonのパスが不正です") from exc
        result[(source.as_posix(), destination.as_posix())] = {
            "source": source.as_posix(),
            "destination": destination.as_posix(),
            "sha256": str(raw.get("sha256", "")),
        }
    return result


def iter_regular_files(root: Path) -> list[Path]:
    if not root.exists() or root.is_symlink():
        return []
    result: list[Path] = []
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = [name for name in directories if not (current_path / name).is_symlink()]
        for name in files:
            path = current_path / name
            if not path.is_symlink() and path.is_file():
                result.append(path)
    return sorted(result)


def sensitive_path_reason(path: Path) -> str | None:
    if SENSITIVE_NAME.search(path.name) or path.suffix.lower() in SENSITIVE_SUFFIXES:
        return "sensitive_filename"
    return None


def secret_reason(path: Path, data: bytes) -> str | None:
    path_reason = sensitive_path_reason(path)
    if path_reason is not None:
        return path_reason
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if PRIVATE_KEY_PATTERN.search(text):
        return "private_key_content"
    for line in text.splitlines():
        match = SENSITIVE_ASSIGNMENT.match(line)
        if match and match.group(1).strip().lower() not in REDACTED_VALUES:
            return "sensitive_assignment"
    return None


def read_text_candidate(path: Path) -> tuple[bytes | None, str | None]:
    if path.is_symlink():
        return None, "symlink"
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None, "unknown_file_type"
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ReverseError("safety_error", "対象ファイルを読み込めません") from exc
    if b"\x00" in data:
        return None, "binary_file"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "binary_file"
    return data, None


def warning_item(mapping: Mapping, reason: str, message: str) -> ReverseItem:
    return ReverseItem(
        "warning",
        f"{mapping.spec.id}/{mapping.destination_rel.as_posix()}",
        mapping.source_rel.as_posix(),
        mapping.destination_rel.as_posix(),
        mapping.spec.mode,
        mapping.spec.revision,
        "",
        reason,
        message,
    )


def add_mapping(mappings: dict[tuple[str, str], Mapping], mapping: Mapping) -> None:
    key = (mapping.source_rel.as_posix(), mapping.destination_rel.as_posix())
    if key in mappings:
        raise ReverseError("configuration_error", "source/targetのmappingが重複しています")
    mappings[key] = mapping


def make_mappings(settings: dict[str, Any]) -> dict[tuple[str, str], Mapping]:
    mappings: dict[tuple[str, str], Mapping] = {}
    target_root = settings["target_root"]
    for spec in settings["targets"]:
        source_rel = validate_relative_path(spec.source, f"{spec.id}.source")
        destination_rel = validate_relative_path(spec.destination, f"{spec.id}.destination")
        source_root = resolve_repository_path(source_rel, f"{spec.id}.source")
        if source_root.is_symlink():
            raise ReverseError("safety_error", f"sourceがリンクです: {spec.id}")
        if not source_root.exists():
            raise ReverseError("configuration_error", f"sourceがありません: {spec.id}")
        target_root_path = resolve_target_path(target_root, destination_rel, f"{spec.id}.destination")
        if source_root.is_dir():
            for source_file in iter_regular_files(source_root):
                relative = source_file.relative_to(source_root)
                add_mapping(
                    mappings,
                    Mapping(
                        spec,
                        source_file,
                        source_rel / relative,
                        target_root_path / relative,
                        destination_rel / relative,
                    ),
                )
            for target_file in iter_regular_files(target_root_path):
                relative = target_file.relative_to(target_root_path)
                source_file = source_root / relative
                add_mapping(
                    mappings,
                    Mapping(
                        spec,
                        source_file,
                        source_rel / relative,
                        target_file,
                        destination_rel / relative,
                    ),
                )
        else:
            add_mapping(mappings, Mapping(spec, source_root, source_rel, target_root_path, destination_rel))
    return mappings


def make_plan(
    settings: dict[str, Any],
    state: dict[tuple[str, str], dict[str, Any]],
) -> list[ReverseItem]:
    mappings = make_mappings(settings)
    plan: list[ReverseItem] = []
    messages = settings["messages"]
    for key in sorted(mappings):
        mapping = mappings[key]
        source_path = mapping.source
        target_path = mapping.destination
        target_missing = not target_path.exists()
        if target_missing:
            state_entry = state.get(key)
            if state_entry is not None and source_path.is_file():
                original = source_path.read_bytes()
                plan.append(
                    ReverseItem(
                        "delete-candidate",
                        mapping.spec.id,
                        mapping.source_rel.as_posix(),
                        mapping.destination_rel.as_posix(),
                        mapping.spec.mode,
                        mapping.spec.revision,
                        str(state_entry.get("sha256", "")),
                        "target_deleted",
                        "bootstrap適用済み対象がユーザー環境で削除されています",
                        None,
                        original,
                    )
                )
            else:
                plan.append(warning_item(mapping, "target_missing_not_applied", "適用状態がないため削除しません"))
            continue
        if target_path.is_symlink():
            plan.append(warning_item(mapping, "symlink", "シンボリックリンクは反映しません"))
            continue
        if target_path.is_dir():
            plan.append(warning_item(mapping, "target_is_directory", "対象がディレクトリです"))
            continue
        path_secret_reason = sensitive_path_reason(target_path)
        if path_secret_reason is not None:
            raise ReverseError("safety_error", "秘密情報候補を検出したため反映を停止しました")
        data, unsupported_reason = read_text_candidate(target_path)
        if unsupported_reason is not None:
            plan.append(warning_item(mapping, unsupported_reason, "テキストファイルではないため反映しません"))
            continue
        assert data is not None
        reason = secret_reason(target_path, data)
        if reason is not None:
            raise ReverseError("safety_error", "秘密情報候補を検出したため反映を停止しました")
        source_exists = source_path.exists()
        if source_exists and source_path.is_dir():
            plan.append(warning_item(mapping, "source_is_directory", "リポジトリ側の対象がディレクトリです"))
            continue
        if source_exists and source_path.is_symlink():
            raise ReverseError("safety_error", "リポジトリ側の対象がリンクです")
        source_data = source_path.read_bytes() if source_exists else None
        target_hash = sha256_bytes(data)
        if source_data == data:
            plan.append(
                ReverseItem(
                    "skip",
                    mapping.spec.id,
                    mapping.source_rel.as_posix(),
                    mapping.destination_rel.as_posix(),
                    mapping.spec.mode,
                    mapping.spec.revision,
                    target_hash,
                    "same_hash",
                    messages.get("same_hash", "同一内容です"),
                    None,
                    source_data,
                )
            )
            continue
        action = "update" if source_exists else "create"
        plan.append(
            ReverseItem(
                action,
                mapping.spec.id,
                mapping.source_rel.as_posix(),
                mapping.destination_rel.as_posix(),
                mapping.spec.mode,
                mapping.spec.revision,
                target_hash,
                "target_changed" if source_exists else "target_new",
                "ユーザー環境のテンプレート変更を反映します" if source_exists else "新規テンプレートを反映します",
                data,
                source_data,
            )
        )
    return plan


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pkw-reverse-write.tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise ReverseError("internal_error", "作業ツリーへの書き込みに失敗しました") from exc


def apply_plan(settings: dict[str, Any], plan: list[ReverseItem]) -> None:
    for item in plan:
        if item.action not in {"create", "update", "delete-candidate"}:
            continue
        source_path = resolve_repository_path(Path(item.source), "反映先")
        if item.action == "delete-candidate":
            if source_path.exists():
                if source_path.is_symlink() or not source_path.is_file():
                    raise ReverseError("safety_error", "削除対象が通常ファイルではありません")
                if item.original is not None and source_path.read_bytes() != item.original:
                    raise ReverseError("safety_error", "削除対象が実行中に変更されました")
                source_path.unlink()
            continue
        if item.action == "create" and source_path.exists():
            raise ReverseError("safety_error", "作成対象が実行中に出現しました")
        if item.action == "update" and source_path.read_bytes() != item.original:
            raise ReverseError("safety_error", "更新対象が実行中に変更されました")
        atomic_write(source_path, item.payload or b"")


def build_report(settings: dict[str, Any], plan: list[ReverseItem], applying: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "operation": "reverse-bootstrap",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": settings["profile"],
        "mode": "apply" if applying else "dry-run",
        "status": "success",
        "result_key": "success",
        "exit_code": settings["codes"].get("success", FALLBACK_EXIT_CODE),
        "message": "reverse-bootstrapを完了しました",
        "items": [item.report(applying) for item in plan],
    }


def build_error_report(settings: dict[str, Any], error: BootstrapError, applying: bool) -> dict[str, Any]:
    result_key = error.key if error.key in settings["codes"] else "internal_error"
    return {
        "schema_version": 1,
        "operation": "reverse-bootstrap",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": settings.get("profile", "default"),
        "mode": "apply" if applying else "dry-run",
        "status": "error",
        "result_key": result_key,
        "exit_code": settings["codes"].get(result_key, FALLBACK_EXIT_CODE),
        "message": settings["messages"].get(result_key, "reverse-bootstrapでエラーが発生しました"),
        "items": [],
    }


def write_report(settings: dict[str, Any], report: dict[str, Any]) -> None:
    report_path = settings["reverse_report_json"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def safe_detail(detail: str) -> str:
    return detail.replace(str(ROOT), "<repository>")


def print_report(settings: dict[str, Any], report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    print(f"profile: {report['profile']}")
    for item in report["items"]:
        print(f"{item['action'].upper():16} {item['destination']} - {item['message']}")
    print(f"report: {settings['reverse_report_json'].relative_to(ROOT).as_posix()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ユーザー環境のテンプレート変更をリポジトリへ戻す")
    parser.add_argument("--apply", action="store_true", help="計画をリポジトリの作業ツリーへ反映する")
    parser.add_argument("--confirm", action="store_true", help="--applyの明示確認")
    args = parser.parse_args(argv)
    settings: dict[str, Any] | None = None
    applying = bool(args.apply)
    try:
        if args.confirm and not args.apply:
            raise ReverseError("safety_error", "--confirmは--applyと同時に指定してください")
        if args.apply and not args.confirm:
            raise ReverseError("safety_error", "適用には--confirmが必要です")
        settings = load_settings(create_local_config=False)
        if settings["profile"] != "default":
            raise ReverseError("configuration_error", "reverse-bootstrapはdefault profileだけを対象にします")
        ensure_clean_repository()
        state = read_state(settings)
        plan = make_plan(settings, state)
        if applying:
            apply_plan(settings, plan)
        report = build_report(settings, plan, applying)
        write_report(settings, report)
        print_report(settings, report)
        return int(report["exit_code"])
    except BootstrapError as exc:
        if settings is None:
            code = FALLBACK_EXIT_CODE
            print(f"reverse-bootstrap設定エラー: {safe_detail(exc.detail)}", file=sys.stderr)
        else:
            report = build_error_report(settings, exc, applying)
            try:
                write_report(settings, report)
            except OSError:
                pass
            code = report["exit_code"]
            print(f"{report['message']}: {safe_detail(exc.detail)}", file=sys.stderr)
        return int(code)
    except Exception as exc:  # pragma: no cover - 最終フォールバック
        if settings is not None:
            report = build_error_report(settings, BootstrapError("internal_error", "内部エラー"), applying)
            try:
                write_report(settings, report)
            except OSError:
                pass
        print(f"reverse-bootstrap内部エラー: {safe_detail(str(exc))}", file=sys.stderr)
        return FALLBACK_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
