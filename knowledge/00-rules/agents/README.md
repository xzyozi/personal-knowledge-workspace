# Agents

共有エージェントの定義を置きます。設計は `docs/design/shared-agents.md` を参照してください。

エージェントは、入口ファイル（`AGENTS.md`、`GEMINI.md`、各ツールの `knowledge-entry.md`）から直接参照します。

## 書き方

- ファイル名は `<name>.md` にします。
- 名前は `pkw-` で始め、ASCIIのkebab-caseにします。
- frontmatter は `name` と `description` の2項目だけです。`description` は200文字以内で、`|` を含めません。
- 本文は「役割」「参照するルール」「Skill一覧」の3節にします。読む順序と禁止事項は、`knowledge/00-rules/` の既存ルールへリンクし、重複して書きません。
- 秘密情報、個人情報、絶対パスを書きません。

## 追加の手順

1. このディレクトリに `<name>.md` を追加します。
2. すべての入口ファイルから、新しいエージェントを参照します。
3. `python scripts/validate_structure.py` で検査します。