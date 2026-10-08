# Scripts

機械的に同じ結果を出せる処理を置きます。

- `bootstrap.py`: TOMLのallowlist/profileに従う非破壊初期適用
- `reverse_bootstrap.py`: default profileのテンプレート変更を作業ツリーへ戻す処理
- `migrate_knowledge.py`: ホーム配下のテキストを`04.00-inbox`へ取り込み、manifestで検証する処理
- `view_bootstrap_report.py`: 固定HTMLとJSONをローカル表示するツール
- `test_bootstrap.py`: 一時fixtureだけを使うbootstrap検証
- `test_reverse_bootstrap.py`: 一時fixtureだけを使うreverse-bootstrap検証
- `test_migrate_knowledge.py`: 一時fixtureだけを使う移行検証
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

### ホーム直下への展開

AIツールにグローバル設定として読ませる場合は、`config/bootstrap.local.toml`でホームをtargetにします。ホームを指定するには、`allow_home = true`の明示が必要です。

```toml
[target]
root = "~/"
allow_home = true
```

- 展開は`config/bootstrap.toml`の許可リストの新規作成だけです。ホーム直下の既存ファイルは上書きせず、同名があれば衝突として全体を適用しません。
- ホームより上位のディレクトリと、このリポジトリのrootはtargetにできません。
- ホーム自体はGit作業ツリーにしません。個人ナレッジを管理する場合は、ホーム直下の`knowledge/`を独立したリポジトリ（`git init`）にします。

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

## Migrate Knowledge

migrate_knowledgeは、ホームを基点にした相対パスの許可リスト（`config/bootstrap.local.toml`の`[migration] sources`）から、テキストを`<target.root>/knowledge/04-sources/04.00-inbox/`へ取り込みます。個人ナレッジ用リポジトリのGit操作は行いません。

```powershell
# dry-run（既定）
python scripts/migrate_knowledge.py

# 取り込み
python scripts/migrate_knowledge.py --apply --confirm

# manifestと取り込み先を照合（読み取り専用）
python scripts/migrate_knowledge.py --verify

# 移行レポートを表示
python scripts/view_bootstrap_report.py --report migrate
```

- `.ssh`、`.aws`、`.gemini`、`AppData`などの固定の拒否リスト（`config/bootstrap.toml`の`[migration] deny`）は、移行元に指定できず、走査中も取り込みません。
- 実行ごとに`04.00-inbox/manifests/migration-<UTC日時>-<label>.json`を作成し、上書きしません。
- バイナリは`knowledge/06-large/manifest.json`へ登録します。個人リポジトリの`06-large/.gitignore`で`manifest.json`を追跡対象にしてください。
- 除外（秘密情報の候補）や衝突が1件でもあれば、終了コードは`10`です。
