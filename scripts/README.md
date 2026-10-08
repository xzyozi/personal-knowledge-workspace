# Scripts

機械的に同じ結果を出せる処理を置きます。

- `bootstrap.py`: TOMLのallowlist/profileに従う非破壊初期適用
- `reverse_bootstrap.py`: default profileのテンプレート変更を作業ツリーへ戻す処理
- `migrate_knowledge.py`: ホーム配下のテキストを`04.00-inbox`へ取り込み、manifestで検証する処理
- `view_bootstrap_report.py`: 固定HTMLとJSONをローカル表示するツール
- `test_bootstrap.py`: 一時fixtureだけを使うbootstrap検証
- `test_reverse_bootstrap.py`: 一時fixtureだけを使うreverse-bootstrap検証
- `test_migrate_knowledge.py`: 一時fixtureだけを使う移行検証
- `test_validate_structure.py`: 共有エージェント・Skillの検査を、一時ツリーで検証する
- `validate_structure.py`: リポジトリ構造、共有エージェント・Skill、ツール別の入口、Markdownの書式の検証（詳細はルートの`README.md`の「検証」）

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

`default` profileの配布対象は、更新モード`update-if-unmodified`です。

| 配布先の状態 | 動作 |
|---|---|
| ファイルがない | 作成 |
| テンプレートと同一内容 | skip |
| 内容が違い、前回適用時のhashと一致（利用者が未変更） | 更新 |
| 内容が違い、前回適用時のhashと不一致、または適用記録がない | 衝突（全体を適用しない） |

前回適用時のhashは`bootstrap-state.json`に記録されています。利用者が変更したファイルは上書きしません。

### 管理ブロック（`managed-block`モード）

利用者が自分の記述を書くファイル（例: ツールのグローバル設定）は、ファイル全体ではなく、管理ブロックだけをテンプレートが所有します。

```markdown
<!-- pkw:managed:start id="example" revision="1" -->
テンプレートが管理する内容
<!-- pkw:managed:end id="example" -->
```

| 配布先の状態 | 動作 |
|---|---|
| ファイルがない | 作成 |
| 管理ブロックがない | 末尾に空行を入れて追記（利用者の記述は変更しない） |
| 管理ブロックの本文が同じ | skip |
| 管理ブロックの本文が違い、利用者が未編集 | ブロックだけを更新 |
| 利用者がブロック内を編集 | 衝突（全体を適用しない） |
| 開始マーカーだけがあり、終了マーカーがない | 衝突（追記しない） |

- 配布先の開始マーカーには、ブロック本文のhash（`sha256`）が書き込まれます。更新時に、このhashと現在の本文を比べて、利用者の編集を検出します。テンプレート側にhashを書く必要はありません。
- dry-runで追記内容を表示し、`--apply --confirm`の時だけ書き込みます。

### ホーム直下への展開

AIツールにグローバル設定として読ませる場合は、`config/bootstrap.local.toml`でホームをtargetにします。ホームを指定するには、`allow_home = true`の明示が必要です。

```toml
[target]
root = "~/"
allow_home = true
```

- 展開は`config/bootstrap.toml`の許可リストだけです。既存ファイルは、利用者が変更していない場合に限りテンプレートの更新を反映し、変更されている場合は衝突として全体を適用しません。
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

`managed-block`モードの対象は、reverse-bootstrapの対象外です。利用者の個人的な記述が混ざるファイルを、テンプレートへ取り込まないためです。dry-runには、除外した旨の警告が表示されます。

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
