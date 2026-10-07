"""固定HTMLからローカルのbootstrap/reverse-bootstrap/migrateレポートを表示する。"""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
import urllib.parse
import webbrowser
from pathlib import Path

from bootstrap import BootstrapError, load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ローカルのworkspaceレポートを表示する")
    parser.add_argument(
        "--report",
        choices=("bootstrap", "reverse", "migrate"),
        default="bootstrap",
        help="表示するレポートの種類",
    )
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        html_path = settings["report_html"]
        report_paths = {
            "bootstrap": settings["report_json"],
            "reverse": settings["reverse_report_json"],
            "migrate": settings["migrate_report_json"],
        }
        report_path = report_paths[args.report]
        report_dir = html_path.parent
        if not html_path.is_file():
            raise BootstrapError("configuration_error", f"HTMLレポートがありません: {html_path}")
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(report_dir))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", settings["port"]), handler)
        query = urllib.parse.urlencode({"report": report_path.name})
        url = f"http://127.0.0.1:{server.server_port}/{html_path.name}?{query}"
        print(f"Workspace report: {url}")
        print("停止するにはCtrl+Cを押してください。")
        webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nレポートサーバーを停止しました。")
        return 0
    except (BootstrapError, OSError) as exc:
        print(f"レポートサーバーを起動できません: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
