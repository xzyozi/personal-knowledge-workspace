# Scripts

機械的に同じ結果を出せる処理を置きます。

- `bootstrap.py`: TOMLのallowlist/profileに従う非破壊初期適用
- `view_bootstrap_report.py`: 固定HTMLとJSONをローカル表示するツール
- `test_bootstrap.py`: 一時fixtureだけを使うbootstrap検証
- `validate_structure.py`: リポジトリ構造検証

## Bootstrap

標準設定は`config/bootstrap.toml`、ユーザー固有設定は初回実行時に`config/bootstrap.local.example.toml`からコピーされる`config/bootstrap.local.toml`です。

```powershell
# dry-run（既定）
python scripts/bootstrap.py

# 衝突がない場合だけ適用
python scripts/bootstrap.py --apply --confirm

# ローカルレポートを表示
python scripts/view_bootstrap_report.py
```

外部送信、クラウド接続、削除、公開などの不可逆操作は行いません。実行結果JSONはローカル生成物で、HTMLは固定ビューアです。
