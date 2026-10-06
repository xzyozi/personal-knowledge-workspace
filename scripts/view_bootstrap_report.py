"""固定HTMLからローカルbootstrapレポートを表示する。"""

from __future__ import annotations

import functools
import http.server
import sys
import webbrowser
from pathlib import Path

from bootstrap import BootstrapError, load_settings


def main() -> int:
    try:
        settings = load_settings()
        html_path = settings["report_html"]
        report_dir = html_path.parent
        if not html_path.is_file():
            raise BootstrapError("configuration_error", f"HTMLレポートがありません: {html_path}")
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(report_dir))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", settings["port"]), handler)
        url = f"http://127.0.0.1:{server.server_port}/{html_path.name}"
        print(f"Bootstrap report: {url}")
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
