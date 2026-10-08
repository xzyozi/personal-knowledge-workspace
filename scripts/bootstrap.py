"""TOML設定に従って共有入口とルールを非破壊に初期適用する。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
STANDARD_CONFIG = CONFIG_DIR / "bootstrap.toml"
LOCAL_CONFIG = CONFIG_DIR / "bootstrap.local.toml"
LOCAL_EXAMPLE = CONFIG_DIR / "bootstrap.local.example.toml"
SUPPORTED_SCHEMA_VERSION = 1
STATE_SCHEMA_VERSION = 1
FALLBACK_EXIT_CODE = 1

START_MARKER = re.compile(
    r'<!--\s*pkw:managed:start\s+id="([^"]+)"(?:\s+revision="([^"]+)")?(?:\s+sha256="([0-9a-f]+)")?\s*-->'
)
END_MARKER = re.compile(r'<!--\s*pkw:managed:end\s+id="([^"]+)"\s*-->')


class BootstrapError(Exception):
    def __init__(self, key: str, detail: str) -> None:
        super().__init__(detail)
        self.key = key
        self.detail = detail
        self.codes: dict[str, int] | None = None
        self.messages: dict[str, str] | None = None


@dataclass(frozen=True)
class TargetSpec:
    id: str
    source: str
    destination: str
    mode: str
    revision: int


@dataclass
class PlannedItem:
    action: str
    target_id: str
    source: str
    destination: str
    mode: str
    revision: int
    source_sha256: str
    reason: str
    message: str
    payload: bytes | None = None
    original: bytes | None = None

    def report(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "id": self.target_id,
            "source": self.source,
            "destination": self.destination,
            "mode": self.mode,
            "revision": self.revision,
            "sha256": self.source_sha256,
            "reason": self.reason,
            "message": self.message,
        }


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BootstrapError("configuration_error", f"設定ファイルがありません: {path}") from exc
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise BootstrapError("configuration_error", f"設定ファイルを読めません: {path}") from exc


def copy_local_config() -> bool:
    if LOCAL_CONFIG.exists():
        return False
    if not LOCAL_EXAMPLE.is_file():
        raise BootstrapError("configuration_error", f"local設定の雛形がありません: {LOCAL_EXAMPLE}")
    try:
        LOCAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LOCAL_EXAMPLE, LOCAL_CONFIG)
    except OSError as exc:
        raise BootstrapError("configuration_error", "local設定のコピーに失敗しました") from exc
    return True


def merge_local_config(standard: dict[str, Any], local: dict[str, Any]) -> dict[str, Any]:
    allowed = {"profile", "target", "storage", "report", "migration"}
    unknown = set(local) - allowed
    if unknown:
        raise BootstrapError("configuration_error", f"local設定に許可されない項目があります: {sorted(unknown)}")

    result = copy.deepcopy(standard)
    profile = local.get("profile", {})
    if profile:
        if set(profile) - {"name"}:
            raise BootstrapError("configuration_error", "local設定のprofileはnameだけ指定できます")
        result["profile"] = copy.deepcopy(profile)

    target = local.get("target", {})
    if target:
        if set(target) - {"root", "allow_home"}:
            raise BootstrapError("configuration_error", "local設定のtargetはrootとallow_homeだけ指定できます")
        if "allow_home" in target and not isinstance(target["allow_home"], bool):
            raise BootstrapError("configuration_error", "target.allow_homeはtrueまたはfalseで指定してください")
        result["target"] = copy.deepcopy(target)

    if "storage" in local:
        result["storage"] = copy.deepcopy(local["storage"])

    report = local.get("report", {})
    if report:
        if set(report) - {"server"} or set(report.get("server", {})) - {"port"}:
            raise BootstrapError("configuration_error", "local設定のreportはserver.portだけ指定できます")
        result.setdefault("report", {}).setdefault("server", {}).update(report.get("server", {}))

    migration = local.get("migration", {})
    if migration:
        if set(migration) - {"sources"}:
            raise BootstrapError("configuration_error", "local設定のmigrationはsourcesだけ指定できます")
        sources = migration.get("sources", [])
        if not isinstance(sources, list) or not all(isinstance(value, str) for value in sources):
            raise BootstrapError("configuration_error", "migration.sourcesは文字列の配列で指定してください")
        result.setdefault("migration", {})["sources"] = list(sources)
    return result


def resolve_profile(data: dict[str, Any], name: str, stack: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or name not in profiles:
        raise BootstrapError("configuration_error", f"未定義のprofileです: {name}")
    if name in stack:
        raise BootstrapError("configuration_error", "profileのextendsが循環しています")
    profile = profiles[name]
    if not isinstance(profile, dict):
        raise BootstrapError("configuration_error", f"profileの形式が不正です: {name}")
    targets: list[dict[str, Any]] = []
    parent = profile.get("extends")
    if parent:
        targets.extend(resolve_profile(data, str(parent), stack + (name,)))
    own_targets = profile.get("targets", [])
    if not isinstance(own_targets, list):
        raise BootstrapError("configuration_error", f"profile.targetsの形式が不正です: {name}")
    targets.extend(own_targets)
    return targets


def validate_relative_path(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise BootstrapError("safety_error", f"相対パスだけ指定できます: {label}")
    return path


def safe_report_path(data: dict[str, Any], key: str) -> Path:
    report = data.get("report", {})
    directory = validate_relative_path(str(report.get("directory", "reports")), "report.directory")
    name = validate_relative_path(str(report.get(key, f"bootstrap-report.{key}")), f"report.{key}")
    if len(name.parts) != 1:
        raise BootstrapError("configuration_error", f"report.{key}はファイル名だけ指定してください")
    return ROOT / directory / name


def load_settings(*, create_local_config: bool = True) -> dict[str, Any]:
    standard = read_toml(STANDARD_CONFIG)
    codes = standard.get("exit_codes")
    messages = standard.get("messages")
    if not isinstance(codes, dict) or not isinstance(messages, dict):
        raise BootstrapError("configuration_error", "exit_codesまたはmessagesがありません")
    required_messages = {
        "success",
        "conflict",
        "configuration_error",
        "safety_error",
        "internal_error",
        "target_missing",
        "same_hash",
        "destination_is_directory",
        "unmanaged_existing_file",
        "source_managed_block_missing",
        "managed_block_missing",
        "managed_block_modified",
        "managed_block_not_utf8",
        "same_managed_block",
        "managed_block_updated",
    }
    missing_messages = required_messages - set(messages)
    if missing_messages:
        raise BootstrapError("configuration_error", f"messagesに必須項目がありません: {sorted(missing_messages)}")
    if standard.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise BootstrapError("configuration_error", "未対応のschema_versionです")

    try:
        local_created = copy_local_config() if create_local_config else False
        local = read_toml(LOCAL_CONFIG)
        effective = merge_local_config(standard, local)
        profile_name = str(effective.get("profile", {}).get("name", standard.get("default_profile", "default")))
        raw_targets = resolve_profile(effective, profile_name)
        target_root_value = effective.get("target", {}).get("root")
        if not target_root_value:
            raise BootstrapError("configuration_error", "target.rootがありません")
        target_root = Path(os.path.expanduser(os.path.expandvars(str(target_root_value))))
        if not target_root.is_absolute():
            target_root = ROOT / target_root
        target_root = target_root.resolve()
        home = Path.home().resolve()
        if target_root == ROOT.resolve():
            raise BootstrapError("safety_error", "リポジトリrootはtargetにできません")
        if target_root in home.parents:
            raise BootstrapError("safety_error", "ホームより上位のディレクトリはtargetにできません")
        if target_root == home and effective.get("target", {}).get("allow_home") is not True:
            raise BootstrapError(
                "safety_error",
                "ホームをtargetにするには、local設定の[target]にallow_home = trueを指定してください",
            )
        targets: list[TargetSpec] = []
        ids: set[str] = set()
        for raw in raw_targets:
            if not isinstance(raw, dict):
                raise BootstrapError("configuration_error", "targetの形式が不正です")
            required = {"id", "source", "destination"}
            if not required.issubset(raw):
                raise BootstrapError("configuration_error", f"targetに必須項目がありません: {required}")
            target_id = str(raw["id"])
            if target_id in ids:
                raise BootstrapError("configuration_error", f"target idが重複しています: {target_id}")
            ids.add(target_id)
            mode = str(raw.get("mode", "create-only"))
            if mode not in {"create-only", "managed-block", "update-if-unmodified"}:
                raise BootstrapError("configuration_error", f"未対応のtarget modeです: {mode}")
            targets.append(TargetSpec(target_id, str(raw["source"]), str(raw["destination"]), mode, int(raw.get("revision", 1))))
        port = int(effective.get("report", {}).get("server", {}).get("port", 8765))
        if not 1 <= port <= 65535:
            raise BootstrapError("configuration_error", "report.server.portは1から65535で指定してください")
        migration_data = effective.get("migration", {})
        migration_deny = migration_data.get("deny", [])
        migration_sources = migration_data.get("sources", [])
        for label, values in (("deny", migration_deny), ("sources", migration_sources)):
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise BootstrapError("configuration_error", f"migration.{label}は文字列の配列で指定してください")
        return {
            "data": effective,
            "codes": {str(k): int(v) for k, v in codes.items()},
            "messages": {str(k): str(v) for k, v in messages.items()},
            "profile": profile_name,
            "target_root": target_root,
            "targets": targets,
            "report_json": safe_report_path(standard, "json"),
            "reverse_report_json": safe_report_path(standard, "reverse_json"),
            "migrate_report_json": safe_report_path(standard, "migrate_json"),
            "migration": {"sources": list(migration_sources), "deny": list(migration_deny)},
            "report_html": safe_report_path(standard, "html"),
            "state_path": safe_report_path(standard, "state"),
            "port": port,
            "local_created": local_created,
        }
    except BootstrapError as exc:
        exc.codes = {str(k): int(v) for k, v in codes.items()}
        exc.messages = {str(k): str(v) for k, v in messages.items()}
        raise


def expand_targets(settings: dict[str, Any]) -> list[tuple[TargetSpec, Path, Path, str]]:
    result: list[tuple[TargetSpec, Path, Path, str]] = []
    for spec in settings["targets"]:
        source_rel = validate_relative_path(spec.source, f"{spec.id}.source")
        destination_rel = validate_relative_path(spec.destination, f"{spec.id}.destination")
        source = (ROOT / source_rel).resolve()
        if ROOT.resolve() not in source.parents and source != ROOT.resolve():
            raise BootstrapError("safety_error", f"sourceがリポジトリ外です: {spec.source}")
        if not source.exists():
            raise BootstrapError("configuration_error", f"sourceがありません: {spec.source}")
        if source.is_dir():
            for source_file in sorted(path for path in source.rglob("*") if path.is_file()):
                relative = source_file.relative_to(source)
                destination = destination_rel / relative
                result.append((spec, source_file, destination, f"{spec.id}/{relative.as_posix()}"))
        else:
            result.append((spec, source, destination_rel, spec.id))
    return result


def find_managed_block(text: str, target_id: str) -> tuple[re.Match[str], re.Match[str], str] | None:
    for start in START_MARKER.finditer(text):
        if start.group(1) != target_id:
            continue
        for end in END_MARKER.finditer(text, start.end()):
            if end.group(1) == target_id:
                return start, end, text[start.end():end.start()]
    return None


def managed_update(source: bytes, existing: bytes, target_id: str) -> tuple[bytes | None, str]:
    try:
        source_text = source.decode("utf-8")
        existing_text = existing.decode("utf-8")
    except UnicodeDecodeError:
        return None, "managed_block_not_utf8"
    source_block = find_managed_block(source_text, target_id)
    existing_block = find_managed_block(existing_text, target_id)
    if source_block is None:
        return None, "source_managed_block_missing"
    if existing_block is None:
        return None, "managed_block_missing"
    recorded_hash = existing_block[0].group(3)
    if recorded_hash and recorded_hash != sha256_bytes(existing_block[2].encode("utf-8")):
        return None, "managed_block_modified"
    source_body_hash = sha256_bytes(source_block[2].encode("utf-8"))
    if sha256_bytes(existing_block[2].encode("utf-8")) == source_body_hash:
        return existing, "same_managed_block"
    updated = existing_text[:existing_block[0].start()] + source_text[source_block[0].start():source_block[1].end()] + existing_text[existing_block[1].end():]
    return updated.encode("utf-8"), "managed_block_updated"


def load_applied_hashes(settings: dict[str, Any]) -> dict[str, str]:
    """前回の適用で記録した、配布先ごとのテンプレートのhashを返す。読めなければ空にする。"""
    try:
        state = json.loads(settings["state_path"].read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA_VERSION:
        return {}
    if state.get("profile") != settings["profile"] or not isinstance(state.get("applied_files"), list):
        return {}
    hashes: dict[str, str] = {}
    for entry in state["applied_files"]:
        if isinstance(entry, dict) and isinstance(entry.get("destination"), str) and isinstance(entry.get("sha256"), str):
            hashes[entry["destination"]] = entry["sha256"]
    return hashes


def make_plan(settings: dict[str, Any]) -> list[PlannedItem]:
    plan: list[PlannedItem] = []
    messages = settings["messages"]
    applied_hashes = load_applied_hashes(settings)
    for spec, source, destination_rel, report_id in expand_targets(settings):
        source_bytes = source.read_bytes()
        source_hash = sha256_bytes(source_bytes)
        destination = settings["target_root"] / destination_rel
        relative_destination = destination_rel.as_posix()
        source_name = source.relative_to(ROOT).as_posix()
        if not destination.exists():
            plan.append(PlannedItem("create", report_id, source_name, relative_destination, spec.mode, spec.revision, source_hash, "target_missing", messages.get("target_missing", "対象がありません"), source_bytes, None))
            continue
        if destination.is_dir():
            plan.append(PlannedItem("conflict", report_id, source_name, relative_destination, spec.mode, spec.revision, source_hash, "destination_is_directory", messages.get("destination_is_directory", "保存先がディレクトリです")))
            continue
        existing = destination.read_bytes()
        if existing == source_bytes:
            plan.append(PlannedItem("skip", report_id, source_name, relative_destination, spec.mode, spec.revision, source_hash, "same_hash", messages.get("same_hash", "同一内容です"), None, existing))
            continue
        if spec.mode == "managed-block":
            updated, reason = managed_update(source_bytes, existing, spec.id)
            if updated is not None and updated != existing:
                plan.append(PlannedItem("update", report_id, source_name, relative_destination, spec.mode, spec.revision, source_hash, reason, messages.get(reason, "管理ブロックを更新します"), updated, existing))
            elif updated is not None:
                plan.append(PlannedItem("skip", report_id, source_name, relative_destination, spec.mode, spec.revision, source_hash, reason, messages.get(reason, "管理ブロックは同一です"), None, existing))
            else:
                plan.append(PlannedItem("conflict", report_id, source_name, relative_destination, spec.mode, spec.revision, source_hash, reason, messages.get(reason, "管理ブロックを安全に更新できません")))
        elif spec.mode == "update-if-unmodified":
            recorded = applied_hashes.get(relative_destination)
            if recorded is not None and sha256_bytes(existing) == recorded:
                plan.append(PlannedItem("update", report_id, source_name, relative_destination, spec.mode, spec.revision, source_hash, "template_updated", messages.get("template_updated", "テンプレートの更新を反映します"), source_bytes, existing))
            else:
                reason = "user_modified" if recorded is not None else "no_apply_record"
                default_message = "利用者が変更したため更新しません" if recorded is not None else "適用記録がないため更新しません"
                plan.append(PlannedItem("conflict", report_id, source_name, relative_destination, spec.mode, spec.revision, source_hash, reason, messages.get(reason, default_message), None, existing))
        else:
            plan.append(PlannedItem("conflict", report_id, source_name, relative_destination, spec.mode, spec.revision, source_hash, "unmanaged_existing_file", messages.get("unmanaged_existing_file", "未管理の既存ファイルと衝突しました"), None, existing))
    return plan


def apply_plan(settings: dict[str, Any], plan: list[PlannedItem]) -> None:
    if any(item.action == "conflict" for item in plan):
        return
    for item in plan:
        if item.action not in {"create", "update"}:
            continue
        destination = settings["target_root"] / item.destination
        if item.action == "create" and destination.exists():
            raise BootstrapError("conflict", f"適用中に対象が出現しました: {item.destination}")
        if item.action == "update" and destination.read_bytes() != item.original:
            raise BootstrapError("conflict", f"適用中に対象が変更されました: {item.destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".pkw-write.tmp")
        temporary.write_bytes(item.payload or b"")
        temporary.replace(destination)


def build_report(settings: dict[str, Any], plan: list[PlannedItem], applying: bool) -> dict[str, Any]:
    conflicts = any(item.action == "conflict" for item in plan)
    result_key = "conflict" if conflicts else "success"
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": settings["profile"],
        "target_root": str(settings["target_root"]),
        "mode": "apply" if applying else "dry-run",
        "status": "conflict" if conflicts else "success",
        "result_key": result_key,
        "exit_code": settings["codes"].get(result_key, FALLBACK_EXIT_CODE),
        "message": settings["messages"].get(result_key, result_key),
        "local_config_created": settings["local_created"],
        "items": [item.report() for item in plan],
    }


def write_report(settings: dict[str, Any], report: dict[str, Any]) -> None:
    report_path = settings["report_json"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def build_state(settings: dict[str, Any], plan: list[PlannedItem]) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": settings["profile"],
        "applied_files": [
            {
                "source": item.source,
                "destination": item.destination,
                "mode": item.mode,
                "revision": item.revision,
                "sha256": item.source_sha256,
            }
            for item in plan
            if item.action in {"create", "update", "skip"}
        ],
    }


def write_state(settings: dict[str, Any], plan: list[PlannedItem]) -> None:
    state_path = settings["state_path"]
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_name(state_path.name + ".pkw-write.tmp")
    temporary.write_text(json.dumps(build_state(settings, plan), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(state_path)


def print_report(settings: dict[str, Any], report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    print(f"profile: {report['profile']}")
    print(f"target: {report['target_root']}")
    for item in report["items"]:
        print(f"{item['action'].upper():8} {item['destination']} - {item['message']}")
    print(f"report: {settings['report_json']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Non-destructive workspace bootstrap")
    parser.add_argument("--apply", action="store_true", help="衝突がない場合だけ対象へ適用する")
    parser.add_argument("--confirm", action="store_true", help="--applyの明示確認")
    args = parser.parse_args(argv)
    settings: dict[str, Any] | None = None
    try:
        settings = load_settings()
        if args.confirm and not args.apply:
            raise BootstrapError("safety_error", "--confirmは--applyと同時に指定してください")
        if args.apply and not args.confirm:
            raise BootstrapError("safety_error", "適用には--confirmが必要です")
        plan = make_plan(settings)
        applying = bool(args.apply)
        if applying:
            apply_plan(settings, plan)
        report = build_report(settings, plan, applying)
        if applying and report["status"] == "success":
            write_state(settings, plan)
        write_report(settings, report)
        print_report(settings, report)
        return int(report["exit_code"])
    except BootstrapError as exc:
        if settings is not None:
            code = settings["codes"].get(exc.key, FALLBACK_EXIT_CODE)
            message = settings["messages"].get(exc.key, exc.detail)
        else:
            code = FALLBACK_EXIT_CODE
            message = "bootstrap設定を読み込めません"
        print(f"{message}: {exc.detail}", file=sys.stderr)
        return code
    except Exception as exc:  # pragma: no cover - 最終フォールバック
        print(f"bootstrap内部エラー: {exc}", file=sys.stderr)
        return FALLBACK_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
