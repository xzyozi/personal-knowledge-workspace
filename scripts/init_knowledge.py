"""個人側のknowledge/へ、許可リストにある骨格だけを、なければ作成する。

既存のファイルは内容にかかわらずスキップし、上書きも削除もしない。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bootstrap import FALLBACK_EXIT_CODE, ROOT, BootstrapError, load_settings, validate_relative_path

ALLOWED_PREFIX = "knowledge"


class InitError(BootstrapError):
    """init-knowledge固有のエラー。"""


@dataclass
class InitItem:
    path: str
    action: str
    status: str
    message: str

    def report(self) -> dict[str, str]:
        # HTMLビューアが読む destination / id も、相対パスで出す
        return {
            "id": self.path,
            "path": self.path,
            "destination": self.path,
            "action": self.action,
            "status": self.status,
            "message": self.message,
        }


def safe_detail(detail: str) -> str:
    return detail.replace(str(ROOT), "<repository>").replace(str(Path.home()), "<home>")


def load_allowlist(settings: dict[str, Any]) -> list[Path]:
    """設定の許可リストを検証して返す。knowledge/配下のリポジトリ相対パスだけを許す。"""
    raw = settings["data"].get("init", {}).get("files", [])
    if not isinstance(raw, list) or not all(isinstance(value, str) for value in raw):
        raise InitError("configuration_error", "init.filesは文字列の配列で指定してください")
    result: list[Path] = []
    seen: set[str] = set()
    for value in raw:
        relative = validate_relative_path(value, "init.files")
        if len(relative.parts) < 2 or relative.parts[0] != ALLOWED_PREFIX:
            raise InitError("safety_error", f"init.filesはknowledge/配下だけ指定できます: {value}")
        key = relative.as_posix()
        if key in seen:
            raise InitError("configuration_error", f"init.filesが重複しています: {key}")
        seen.add(key)
        result.append(relative)
    return result


def ensure_plain_parents(root: Path, relative: Path) -> bool:
    """作成先までの途中がリンクやファイルでなければTrueを返す。"""
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            return False
        if current.exists() and not current.is_dir():
            return False
    return True


def plan_item(target_root: Path, relative: Path) -> tuple[InitItem, Path | None]:
    label = relative.as_posix()
    source = ROOT / relative
    if source.is_symlink() or not source.is_file():
        return InitItem(label, "error", "source-missing", "テンプレート側に対象のファイルがありません"), None
    destination = target_root / relative
    if not ensure_plain_parents(target_root, relative):
        return InitItem(label, "error", "unsafe-destination", "作成先の途中にリンクまたはファイルがあります"), None
    if os.path.lexists(destination):
        return InitItem(label, "skip", "exists", "既に存在するためスキップします"), None
    return InitItem(label, "create", "planned", "作成します"), source


def run_init(settings: dict[str, Any], applying: bool) -> list[InitItem]:
    target_root = settings["target_root"]
    if target_root.exists() and not target_root.is_dir():
        raise InitError("configuration_error", "target.rootがディレクトリではありません")
    items: list[InitItem] = []
    for relative in load_allowlist(settings):
        item, source = plan_item(target_root, relative)
        items.append(item)
        if not applying or source is None:
            continue
        destination = target_root / relative
        try:
            data = source.read_bytes()
            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, "xb") as handle:
                handle.write(data)
        except FileExistsError:
            item.action, item.status, item.message = "skip", "exists", "既に存在するためスキップします"
        except OSError:
            item.action, item.status, item.message = "error", "failed", "書き込みに失敗しました"
        else:
            item.status, item.message = "created", "作成しました"
    return items


def build_report(settings: dict[str, Any], items: list[InitItem], mode: str, failure: BootstrapError | None = None) -> dict[str, Any]:
    if failure is not None:
        result_key = failure.key if failure.key in settings["codes"] else "internal_error"
        status, message = "error", settings["messages"].get(result_key, "初期設定でエラーが発生しました")
    elif any(item.action == "error" for item in items):
        result_key, status, message = "conflict", "conflict", "作成できない項目があります"
    else:
        result_key, status, message = "success", "success", "初期設定を完了しました"
    return {
        "schema_version": 1,
        "operation": "init-knowledge",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": settings["profile"],
        "mode": mode,
        "status": status,
        "result_key": result_key,
        "exit_code": settings["codes"].get(result_key, FALLBACK_EXIT_CODE),
        "message": message,
        "items": [item.report() for item in items],
    }


def write_report(settings: dict[str, Any], report: dict[str, Any]) -> None:
    path = settings["init_report_json"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def print_report(settings: dict[str, Any], report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    print(f"mode: {report['mode']}")
    counts = Counter(item["action"] for item in report["items"])
    print("summary: " + (", ".join(f"{name}={counts[name]}" for name in sorted(counts)) or "items=0"))
    for item in report["items"]:
        if item["action"] != "skip":
            print(f"{item['action'].upper():8} {item['path']} - {item['message']}")
    print(f"report: {settings['init_report_json'].relative_to(ROOT).as_posix()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="個人側のknowledge/の骨格を、なければ作成する")
    parser.add_argument("--apply", action="store_true", help="計画を作成先へ反映する")
    parser.add_argument("--confirm", action="store_true", help="--applyの明示確認")
    args = parser.parse_args(argv)
    mode = "apply" if args.apply else "dry-run"
    settings: dict[str, Any] | None = None
    try:
        settings = load_settings(create_local_config=False)
        if args.confirm and not args.apply:
            raise InitError("safety_error", "--confirmは--applyと同時に指定してください")
        if args.apply and not args.confirm:
            raise InitError("safety_error", "適用には--confirmが必要です")
        items = run_init(settings, bool(args.apply))
        report = build_report(settings, items, mode)
        write_report(settings, report)
        print_report(settings, report)
        return int(report["exit_code"])
    except BootstrapError as exc:
        if settings is None:
            print(f"init-knowledge設定エラー: {safe_detail(exc.detail)}", file=sys.stderr)
            return FALLBACK_EXIT_CODE
        report = build_report(settings, [], mode, exc)
        try:
            write_report(settings, report)
        except OSError:
            pass
        print(f"{report['message']}: {safe_detail(exc.detail)}", file=sys.stderr)
        return int(report["exit_code"])
    except Exception as exc:  # pragma: no cover - 最終フォールバック
        print(f"init-knowledge内部エラー: {safe_detail(str(exc))}", file=sys.stderr)
        return FALLBACK_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
