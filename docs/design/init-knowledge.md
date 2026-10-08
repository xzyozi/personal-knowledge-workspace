# init-knowledge 設計

## 目的

個人側（`target.root` の `knowledge/`）に、テンプレートの骨格を、なければ作成します。利用者がデータを書くファイル（例: `projects/INDEX.md`）は、bootstrapの配布モードでは、編集後に衝突して適用が止まります。そのため、bootstrapとは別の明示的な初期設定として分けます。

## 動作

- 既定はdry-runです。`--apply --confirm` を両方指定した時だけ作成します。
- 作成先は `config/bootstrap.local.toml` の `target.root` の `knowledge/` です。bootstrapと同じ安全条件（リポジトリroot禁止、ホームは `allow_home = true` が必要）を使います。
- 許可リスト（`config/bootstrap.toml` の `[init] files`）にあるファイルだけを扱います。
  - リポジトリ相対パスで、`knowledge/` 配下に限ります。絶対パスと `..` は拒否します。
  - 日付付きの `04-sources/` の記録、`00-rules/`、`knowledge/INDEX.md` は含めません。`00-rules/` と `INDEX.md` はbootstrapが配布します。
- 対象が既に存在する場合は、内容にかかわらずスキップします（上書き、削除、更新をしません）。ファイルの作成は排他的に行い、競合時もスキップします。
- 作成先の途中にリンクやファイルがある場合は、その項目を `error` にします。

## レポート

`reports/init-knowledge-report.json`（Git管理外）に、項目ごとの `create` / `skip` / `error` を、相対パスで記録します。絶対パス、ファイルの内容、秘密情報は出力しません。

終了コードは、成功が `0`、作成できない項目があれば `10`、安全条件違反が `30` です。

## 共有Skill

`pkw-init-knowledge` が、利用者への場所の確認、dry-run、承認、適用、確認の手順を案内します。

## テスト

ローカルでは実行せず、GitHub Actionsで `scripts/test_init_knowledge.py` を実行します。

- dry-runが作成先を変更しない
- `--confirm` なしの `--apply` と、`--apply` なしの `--confirm` を拒否する
- 許可リストのとおりに作成し、許可リスト外（`00-rules/`、`INDEX.md`、日付付きの原本）を配らない
- 再実行で変更しない
- 既存のファイルを上書きしない
- 許可リストに `knowledge/` 外を書くと拒否する
- レポートに絶対パスが含まれない
