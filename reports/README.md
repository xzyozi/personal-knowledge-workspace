# Reports

`bootstrap-report.html`はGit管理する固定ビューアです。`bootstrap-report.json`は`bootstrap.py`が更新するローカル実行結果で、Git管理対象外です。

ローカル表示:

```powershell
python scripts/view_bootstrap_report.py
```

サーバーは`127.0.0.1`だけにbindし、portは`config/bootstrap.toml`またはlocal設定から読みます。
