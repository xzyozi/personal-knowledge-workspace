# Reports

`bootstrap-report.html`はGit管理する固定ビューアです。JSONレポートはスクリプトが更新するローカル実行結果で、Git管理対象外です。

| レポート                        | 生成元                 | 表示                                                       |
| ------------------------------- | ---------------------- | ---------------------------------------------------------- |
| `bootstrap-report.json`         | `bootstrap.py`         | `python scripts/view_bootstrap_report.py`                  |
| `reverse-bootstrap-report.json` | `reverse_bootstrap.py` | `python scripts/view_bootstrap_report.py --report reverse` |
| `migrate-knowledge-report.json` | `migrate_knowledge.py` | `python scripts/view_bootstrap_report.py --report migrate` |
| `init-knowledge-report.json`    | `init_knowledge.py`    | `python scripts/view_bootstrap_report.py --report init`    |

`bootstrap-state.json`は、成功したbootstrapの適用状態を保存するGit管理外のファイルです。

サーバーは`127.0.0.1`だけにbindし、portは`config/bootstrap.toml`またはlocal設定から読みます。
