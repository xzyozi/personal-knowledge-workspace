# パス設計

clone先やユーザーが異なっても動くように、パスを扱う方針と、検証できている範囲をまとめます。

## 方針

- Markdownのリンクは、リポジトリ相対パスにします。
- スクリプトは、実行時にリポジトリrootを解決します。
- 追跡ファイルに、ユーザー固有の絶対パスやユーザー名を書きません。
- ユーザー固有の設定は、Git管理外の `config/bootstrap.local.toml` に置きます。
- 個人リポジトリの索引（`knowledge/projects/INDEX.md`）のリポジトリ列は、`owner/repo` または認証情報を含まないリモートURLの論理IDにします。ローカルの実パスは書きません。

## 検査

`python scripts/validate_structure.py` が次を検査します。

- Markdownの書式（絶対パス、リンク切れなど）。ただし `knowledge/04-sources/`、`knowledge/01-private/`、`knowledge/06-large/` は対象外です。
- `git ls-files` で追跡されている全テキストファイルの絶対パス。Markdown以外（設定、スクリプト、ワークフローなど）も含みます。除外は上の3つの領域と `scripts/test_*.py`（テストが検出対象の文字列を意図して書くため）です。バイナリや、UTF-8として読めないファイルは対象外です。
- ローカルだけのファイル（`reports/*.json`、`config/bootstrap.local.toml`）は追跡されないため、対象になりません。

## 空白と日本語を含むパス

`test_bootstrap.py`、`test_reverse_bootstrap.py`、`test_migrate_knowledge.py`、`test_init_knowledge.py` は、fixtureの一時ディレクトリ名に空白と日本語を含めます。これらのパスで、スクリプトが動作することをCI（WindowsとUbuntu）で確認します。

## 未検証の制約

次は、CIでも手元でも検証していません。

- OneDrive配下（オンライン専用のプレースホルダーのファイル）に、リポジトリや `target.root` を置いた場合の動作
- 権限が不足しているディレクトリやファイルを対象にした場合の動作

これらの環境で使う場合は、先にdry-runで確認してください。問題が見つかった場合は、別の課題として扱います。

## 外部バイナリ

バイナリの実体は、Gitにもスクリプトの設定にも保存先を持ちません。`knowledge/06-large/manifest.json` に、論理パス、サイズ、SHA-256、最終確認日だけを登録します。外部ストレージへのコピーと復元は、手動で行います。論理パスとローカルパスの対応表は持ちません。

詳細は `migrate-knowledge.md` を参照してください。
