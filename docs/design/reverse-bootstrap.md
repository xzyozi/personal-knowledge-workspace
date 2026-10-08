# Reverse Bootstrap 設計リファレンス

## 目的

`reverse-bootstrap` は、bootstrapでユーザー環境へ配布したテンプレートをユーザー環境で動作確認・修正した後、その変更をテンプレートリポジトリの作業ツリーへ戻すための開発用スクリプトです。

個人ナレッジをテンプレートリポジトリへ同期する機能ではありません。

```text
テンプレートリポジトリ
        │ bootstrap
        ▼
ユーザー環境で動作確認・修正
        │ reverse-bootstrap
        ▼
テンプレートリポジトリの作業ツリー
        │ git status / git diff
        ▼
ユーザーがcommit・push
```

## 対象範囲

reverse-bootstrapは、`config/bootstrap.toml`の`default` profileを対象にします。sourceとtargetの対応は、bootstrapのtarget定義を逆方向に利用します。

対象は次のとおりです。

- bootstrapの`default` profileで配布するテンプレート
- AIツール共通入口
- `knowledge/INDEX.md`
- `knowledge/00-rules/**`
- 分類ルール
- 管理対象ディレクトリ配下でユーザーが追加したUTF-8テキストファイル

次は初版の対象外です。

- `personal` profile
- 個人fact
- `knowledge/01-private/`
- `knowledge/04-sources/`
- `knowledge/05-tasks/`
- `knowledge/06-large/`
- バイナリ実体
- ユーザーホーム全体の自動走査
- 外部ストレージとの同期
- `managed-block` モードの対象（利用者の記述が混ざるファイル。個人的な記述がテンプレートに入るのを防ぐ）

factの昇格条件・承認方法・個人ナレッジの保管方法は、reverse-bootstrapとは別の課題で扱います。

## 設定とパス

ユーザー環境側のtarget rootは、bootstrapと同じ`config/bootstrap.local.toml`から解決します。reverse-bootstrapはlocal設定を自動作成しません。設定がない場合は停止し、先にbootstrapを実行して設定を用意します。

`bootstrap.toml`が対象定義の正本です。

```text
bootstrap:
  repository source → user target

reverse-bootstrap:
  user target → repository source
```

sourceとtargetの相対パスは維持します。絶対パス、`..`を含むパス、target root外へのリンクは許可しません。

## 実行インターフェース

既定はdry-runです。

```powershell
python scripts/reverse_bootstrap.py
```

作業ツリーへ反映するには、2つの明示指定が必要です。

```powershell
python scripts/reverse_bootstrap.py --apply --confirm
```

`--apply`単独、`--confirm`単独では反映しません。commitとpushも自動実行しません。

## Gitの扱い

reverse-bootstrap開始時に、テンプレートリポジトリのGit作業ツリーがcleanでなければ停止します。

reverse-bootstrap自身は、テンプレート側とユーザー側の同時編集を競合として判定しません。反映後の確認はGitの通常運用に委ねます。

```powershell
git status
git diff
```

Gitの差分が変更の採否、競合解消、commit、pushのレビュー境界です。

## ファイルの扱い

### 反映候補

- `default` profileのファイル対象
- 管理対象ディレクトリ配下の新規ファイル
- UTF-8として読み取れるテキスト
- 許可されたテキスト拡張子のファイル

### 反映しないもの

- バイナリ
- 未知のファイル形式
- シンボリックリンク経由のファイル
- 管理対象ディレクトリ外のファイル
- 秘密情報を含むファイル

新規ファイルは作成候補として表示し、`--apply --confirm`時だけリポジトリへ作成します。

## 削除

ユーザー環境側で配布済みファイルが削除された場合、dry-runでは削除候補として表示します。

```text
delete-candidate
```

`--apply --confirm`時だけリポジトリ側のファイルを削除します。削除候補にできるのは、過去に成功したbootstrap適用状態に記録されたファイルだけです。適用状態に記録がないファイルは削除しません。

## 適用状態

適用状態はGit管理外の次のファイルに保存します。

```text
reports/bootstrap-state.json
```

状態には、profile、リポジトリ側sourceの相対パス、ユーザー環境側targetの相対パス、適用時のhashだけを保存します。絶対パス、個人fact、ファイル内容、秘密情報は保存しません。

bootstrap全体が成功した場合だけ状態を一括更新します。dry-runや途中失敗では状態を更新しません。reverse-bootstrapは状態を更新しません。

状態ファイルがない場合、reverse-bootstrapは推測で処理せず停止します。先にbootstrapを成功させてください。

## 秘密情報検知

reverse-bootstrapは反映前に、候補ファイルの次を検査します。

- ファイル名
- 拡張子
- 内容

password、token、secret、API key、秘密鍵などの候補を検出した場合、反映全体を停止します。秘密値・絶対パスは標準出力やレポートへ出しません。

## 反映失敗

反映前に対象を検証し、各ファイルは一時ファイル経由で安全に置き換えます。途中で書き込みに失敗した場合は、その時点で停止します。

部分的な作業ツリー変更が残る可能性がありますが、Git作業ツリーは実行前にcleanであるため、変更は`git status`と`git diff`で確認できます。bootstrap-stateは更新しません。

## レポート

bootstrapの固定HTMLレポートビューアをreverse-bootstrapでも利用します。reverse-bootstrapは専用のJSONレポートを生成し、ビューアの対象レポートを切り替えて表示します。

レポートは実行計画・結果の補助情報です。最終的な変更確認の正本はGitの作業ツリーとdiffです。

## テスト

実装テストは`test_reverse_bootstrap.py`として既存bootstrapテストから分離します。ローカル環境ではテストを実行せず、GitHub Actionsで次を検証します。

- dry-runが作業ツリーを変更しない
- `--apply`単独では反映しない
- `--apply --confirm`で反映する
- source/targetの相対パスを保持する
- 新規テキストファイルを反映する
- 適用済みファイルの削除候補を表示・反映する
- stateなし、dirty作業ツリーで停止する
- 秘密情報検出時に反映しない
- 途中失敗時にstateを更新しない
- JSONレポートとHTMLビューア用の形式を生成する

タグ管理は初版の必須要件とせず、必要になった時点で追加します。
