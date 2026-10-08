# Skills

共有Skillの本文を置きます。設計は `docs/design/shared-agents.md` を参照してください。

Skillは、共有エージェントの「Skill一覧」から参照します。現在の作業が `description` に該当する場合だけ、本文を読みます。

## 書き方

- ファイル名は `<name>.md` にします。
- 名前は `pkw-` で始め、ASCIIのkebab-caseにします。`agents/` と `skills/` を通して一意にします。
- frontmatter は `name` と `description` の2項目だけです。`description` は200文字以内で、`|` を含めません。
- 本文は「目的」「手順」「出力形式」「禁止事項」を推奨します。
- 秘密情報、個人情報、絶対パスを書きません。

## 追加の手順

1. このディレクトリに `<name>.md` を追加します。
2. エージェント定義の「Skill一覧」の表に、行を追加します。`name` と `description` は、Skillのfrontmatterと一致させます。
3. `python scripts/validate_structure.py` で検査します。