# Migrate Knowledge 設計リファレンス

## 目的

`migrate_knowledge.py` は、ユーザーのホーム配下にある既存のテキストナレッジを、個人ナレッジ用リポジトリの `knowledge/04-sources/04.00-inbox/` へ安全に取り込みます。取り込んだ内容はmanifestのSHA-256で検証できます。

バイナリは取り込まず、`knowledge/06-large/manifest.json` へ登録します。実体の外部保管（Box等）と復元は手動です。

## 保管モデル

```text
本リポジトリ（テンプレート）
  構造、ルール、スクリプト、CI

個人ナレッジ用のprivateリポジトリ（ユーザーが作成・管理）
  knowledge/ ← bootstrap.local.toml の target.root 直下
```

`target.root` にはホームを指定できます（`allow_home = true` が必要）。その場合、AIツールがグローバル設定として読むファイルはホーム直下へ展開され、取り込み先は `<ホーム>/knowledge/04-sources/04.00-inbox/` になります。ホーム自体はGit作業ツリーにせず、`<ホーム>/knowledge/` を独立したリポジトリにします。

- スクリプトはGit操作を行いません。commit、push、リポジトリ作成はユーザーが行います。
- 取り込み先は `config/bootstrap.local.toml` の `target.root` です。bootstrap、reverse-bootstrapと同じ設定を使います。
- 個人ナレッジはこのテンプレートリポジトリへ入れません。

## 対象範囲

初版の対象は、テキストのフォルダ群です。Notion、OneNote、Obsidianなどの独自形式は、エクスポートしたテキストとして扱います。

次は対象外です。

- 他ツール固有形式の変換
- 自動分類
- `02-facts` への昇格
- Boxなど外部ストレージへの書き込みと復元
- 定期実行

## 移行元の指定

移行元は、ホームを基点にした相対パスの許可リストで指定します。ホームは実行時に `Path.home()` で解決し、ユーザー名や絶対パスは設定、manifest、レポートへ保存しません。

```toml
# config/bootstrap.local.toml（Git管理外）
[migration]
sources = ["Documents/notes", "Documents/work-log"]
```

次の指定は拒否します。

- 空、ホーム直下そのもの
- 絶対パス、ドライブ指定、`..` を含むパス
- 存在しない、ディレクトリではない、リンクである
- 解決後にホーム外を指す
- 取り込み先（`04.00-inbox` と `06-large`）と重なる。`target.root` がホームの場合も、ホーム配下の他のフォルダは指定できる
- 先頭が `manifests` である（inboxの予約名）
- 別の移行元と重なる

`config/bootstrap.toml` の `[migration] deny` に含まれる名前（`.ssh`、`.aws`、`.gemini`、`AppData` など）は固定の拒否リストです。local設定からは変更できません。許可リストに書かれた場合はエラーにし、走査中に見つかったディレクトリは取り込まずに読み飛ばします。

## 取り込み先

移行元のファイルは、ホームからの相対パスを保ったまま次へ取り込みます。

```text
<target.root>/knowledge/04-sources/04.00-inbox/<ホームからの相対パス>
```

例: `Documents/notes/a.md` は `04.00-inbox/Documents/notes/a.md` になります。バイト列はそのままコピーし、改行コードや文字コードは変更しません。

## ファイルの判定

| 判定             | 条件                                                         | 動作                            |
| ---------------- | ------------------------------------------------------------ | ------------------------------- |
| 除外（秘密情報） | 秘密情報らしいファイル名・拡張子、または内容に秘密情報の候補 | コピーしない。理由だけ記録      |
| テキスト         | 許可拡張子、5 MiB以下、NULなし、UTF-8として読める            | `04.00-inbox` へコピー          |
| 大容量・バイナリ | 上記以外                                                     | `06-large/manifest.json` へ登録 |
| 警告             | リンク、読み込めないファイル                                 | コピーしない                    |

許可拡張子は、`.cfg`、`.conf`、`.css`、`.html`、`.ini`、`.json`、`.markdown`、`.md`、`.rst`、`.toml`、`.txt`、`.xml`、`.yaml`、`.yml` です。

秘密情報の検知はこのスクリプトで独立して実装します。`reverse_bootstrap.py` の検知とは対象が異なり、共通化しません。ホーム配下の個人メモは秘密情報が混ざりやすいため、次のパターンを追加で検知します。

- 秘密鍵ブロック
- password、token、secret、api_key などの代入
- AWSアクセスキーID
- GitHub、Slackのトークン
- Bearerトークン、JWT
- パスワード入りの接続文字列

検出した値、ファイル内容、絶対パスは、標準出力、レポート、manifestへ出力しません。

## 衝突の扱い

| ケース                                                 | 動作                                     |
| ------------------------------------------------------ | ---------------------------------------- |
| 同名で内容が同じ                                       | `skip`                                   |
| 過去のmanifestに同じパスとhashがある（分類で移動済み） | `skip`（移行済み）                       |
| 同名で内容が異なる                                     | `conflict`。該当ファイルだけ取り込まない |
| 取り込み先が同名ディレクトリ、リンク、親がファイル     | `conflict`                               |
| 秘密情報の候補                                         | `excluded`。該当ファイルだけ取り込まない |

衝突と秘密情報は、該当ファイルだけを除外して残りを取り込みます。`bootstrap.py` は衝突時に全体を適用しませんが、移行は個人メモの大量取り込みが対象のため、1件の問題で全体を止めない方針にしています。

除外が1件でもあれば、終了コードは `10` です。除外したファイルは一切コピーしません。

## コマンド

```powershell
# dry-run（既定）
python scripts/migrate_knowledge.py

# 取り込み
python scripts/migrate_knowledge.py --apply --confirm

# 取り込み済みの内容をmanifestと照合（読み取り専用）
python scripts/migrate_knowledge.py --verify
```

- `--apply` 単独、`--confirm` 単独では書き込みません。
- `--verify` は `--apply`、`--confirm` と同時に指定できません。
- 移行元は読み取り専用です。削除も上書きもしません。

## manifest

実行ごとの不変の記録として、個人リポジトリに保存します。既存のmanifestは上書きしません。

```text
knowledge/04-sources/04.00-inbox/manifests/migration-<UTC日時>-<label>.json
```

`<label>` は移行元の相対パスから作る論理名です。移行元ごとに1つのmanifestを作ります。何もコピー・登録しなかった実行ではmanifestを作りません。

```json
{
  "schema_version": 1,
  "operation": "migrate-knowledge",
  "generated_at": "2026-10-07T12:00:00+00:00",
  "source_label": "Documents-notes",
  "destination_root": "knowledge/04-sources/04.00-inbox",
  "files": [
    {
      "path": "Documents/notes/a.md",
      "size": 2048,
      "sha256": "...",
      "status": "copied"
    }
  ]
}
```

| 項目              | 内容                                                                                                                                                             |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `path`            | ホームからの相対パス（取り込み先の相対パスと同じ）                                                                                                               |
| `size` / `sha256` | 移行前後の一致確認用。除外したファイルは `null`                                                                                                                  |
| `status`          | `copied`、`skipped-same`、`skipped-migrated`、`registered-large`、`large-unchanged`、`conflict`、`excluded-secret`、`failed-not-copied`、`failed-not-registered` |

`manifests/` は予約名で、再移行の対象になりません。

## バイナリの登録

`knowledge/06-large/manifest.json` に、バイナリの論理名、サイズ、SHA-256、外部保管先の論理パス、最終確認日を登録します。

```json
{
  "schema_version": 1,
  "files": [
    {
      "path": "Documents/notes/image.png",
      "size": 10240,
      "sha256": "...",
      "logical_path": "large/Documents/notes/image.png",
      "last_confirmed": "2026-10-07"
    }
  ]
}
```

- 外部保管先の絶対パスや認証情報は保存しません。
- 登録済みで内容が異なる場合は `conflict` とし、manifestを書き換えません。
- 個人リポジトリの `knowledge/06-large/.gitignore` は、`manifest.json` を追跡できるようにしてください（`!manifest.json`）。

## 検証

`--verify` は読み取り専用で、次を照合します。

- 過去のmanifestの `copied`、`skipped-same` を取り込み先と照合する
  - 一致: `verified`
  - inboxにない（分類で移動した可能性）: `warning`
  - hashが異なる: `error`（終了コード `10`）
- `06-large/manifest.json` の各項目をホーム配下の実ファイルと照合する
  - 一致: `verified`
  - ローカルにない（外部保管済みの可能性）: `warning`
  - hashが異なる: `error`

## 書き込みと失敗時の扱い

- コピーは一時ファイル経由で行い、取り込み先が既に存在する場合は上書きしません。
- 書き込み直前に移行元のhashを再確認し、変化していれば `conflict` として取り込みません。
- 書き込みに失敗した場合は停止し、コピー済み分だけをmanifestに記録します。

## レポート

`reports/migrate-knowledge-report.json` を生成します（Git管理外）。既存の固定HTMLビューアで表示できます。

```powershell
python scripts/view_bootstrap_report.py --report migrate
```

## バックアップ頻度

スクリプトでは規定しません。推奨運用の例です。

| 対象     | 推奨運用の例                                                 |
| -------- | ------------------------------------------------------------ |
| テキスト | 作業区切りごとに個人リポジトリへcommit、週1回push            |
| バイナリ | 追加したタイミングで外部ストレージへコピー、月1回 `--verify` |

定期実行の自動化は初版の対象外です。必要になった時点で別の課題として扱います。

## テスト

ローカルでは実行せず、GitHub Actionsで `scripts/test_migrate_knowledge.py` を実行します。ホームは環境変数で一時ディレクトリへ差し替えます。

- dry-runが取り込み先を変更しない
- `--apply` 単独では書き込まない
- `--apply --confirm` でコピーとmanifest出力を行う
- 再実行しても重複しない
- 分類で移動済みのファイルを再コピーしない
- 衝突と秘密情報は該当ファイルだけ除外し、終了コード10を返す
- 秘密値がレポート、manifest、標準出力に出ない
- 拒否リスト、絶対パス、`..` を拒否する
- `--verify` がhash不一致を検出する
