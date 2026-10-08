---
name: pkw-init-knowledge
description: 個人側のknowledge/に、テンプレートの骨格をなければ作成する。新しい環境の初期設定や、骨格の不足を補いたい時に使う
---

# pkw-init-knowledge

## 目的

個人側の `knowledge/` に、テンプレートの骨格（READMEや `projects/INDEX.md` など）を、なければ作成します。既存のファイルは変更しません。実際の作成は、テンプレートリポジトリの `scripts/init_knowledge.py` が行います。

## 手順

1. **場所の確認**: テンプレートリポジトリの場所を、利用者に確認します。推測しません。
2. **dry-run**: テンプレートリポジトリで `python scripts/init_knowledge.py` を実行し、結果を利用者に見せます。`CREATE` は作成される項目で、既存の項目はスキップされます。
3. **承認**: 利用者が内容を承認したことを確認します。承認がなければ、ここで止めます。
4. **適用**: 利用者の承認後だけ、`python scripts/init_knowledge.py --apply --confirm` を実行します。
5. **確認**: 終了コードと、結果の要約（`create` と `skip` の件数）を確認します。`error` の項目があれば、利用者に報告して止めます。レポートは `python scripts/view_bootstrap_report.py --report init` で見られます。

## 出力形式

作成した件数、スキップした件数、エラーの件数を、相対パスで報告します。

## 禁止事項

- 利用者の承認なしに `--apply` を実行しない。
- 既存のファイルを編集、削除、上書きしない。スクリプトの許可リスト（`config/bootstrap.toml` の `[init]`）をこのSkillの中で変更しない。
- 秘密情報、個人情報、絶対パス、ファイルの内容そのものを出力しない。
- `knowledge/01-private/` の中身を読まない。
