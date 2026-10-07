# Scripts

機械的に同じ結果を出せる処理を置きます。

- `bootstrap.py`: TOMLのallowlist/profileに従う非破壊初期適用
- `reverse_bootstrap.py`: default profileのテンプレート変更を作業ツリーへ戻す処理
- `view_bootstrap_report.py`: 固定HTMLとJSONをローカル表示するツール
- `test_bootstrap.py`: 一時fixtureだけを使うbootstrap検証
- `test_reverse_bootstrap.py`: 一時fixtureだけを使うreverse-bootstrap検証
- `validate_structure.py`: リポジトリ構造検証

## Bootstrap

標準設定は`config/bootstrap.toml`、ユーザー固有設定は初回実行時に`config/bootstrap.local.example.toml`からコピーされる`config/bootstrap.local.toml`です。

```powershell
# dry-run（既定）
python scripts/bootstrap.py

# 衝突がない場合だけ適用
python scripts/bootstrap.py --apply --confirm

# bootstrapレポートを表示
python scripts/view_bootstrap_report.py
```

成功したbootstrapの対象状態は、Git管理外の`reports/bootstrap-state.json`へ保存されます。

## Reverse Bootstrap

reverse-bootstrapは、bootstrap後にユーザー環境で検証・修正したdefault profileのテンプレートを、リポジトリの作業ツリーへ戻します。個人factやprivate領域の同期には使いません。

```powershell
# dry-run（既定）
python scripts/reverse_bootstrap.py

# 作業ツリーへ反映
python scripts/reverse_bootstrap.py --apply --confirm

# reverse-bootstrapレポートを表示
python scripts/view_bootstrap_report.py --report reverse

# 反映結果をGitで確認
git status
git diff
```

実行開始時にGit作業ツリーがcleanでない場合、または`bootstrap-state.json`がない場合は停止します。commitとpushは自動実行しません。

外部送信、クラウド接続、ユーザー環境側の削除、公開などの不可逆操作は行いません。リポジトリ側の削除候補はdry-runで表示し、`--apply --confirm`時だけ反映します。
