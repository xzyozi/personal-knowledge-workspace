# Shared Agents 設計リファレンス

## 目的

入口ファイルから、このプロジェクトが管理する共有エージェントを読めるようにします。共有エージェントが内部のSkillを持ち、Skillを一元管理します。

正本は `knowledge/00-rules/` の下の1か所です。bootstrapとreverse-bootstrapの対象に、すでに含まれています。

## 構造

```text
入口（AGENTS.md、GEMINI.md、.kiro/steering/knowledge-entry.md など。薄いまま）
  ↓ 参照
knowledge/00-rules/agents/pkw-knowledge-steward.md
  ↓ Skill一覧（name、description、リンク）
knowledge/00-rules/skills/<skill>.md
  ↓ 該当する時だけ本文を読む
```

```text
knowledge/00-rules/
├─ agents/
│  ├─ README.md
│  └─ pkw-knowledge-steward.md
└─ skills/
   └─ README.md
```

## エージェント

初版は1つです。役割が増えた時に分割します。

| name | 担当 |
|---|---|
| `pkw-knowledge-steward` | 個人ナレッジの読み書きと分類 |

エージェント定義の本文は、次の3節です。

1. 役割
2. 参照するルール（リンク）
3. Skill一覧

読む順序と禁止事項は、`knowledge/00-rules/` の既存ルールと `AGENTS.md` に定義があります。エージェント定義には重複して書かず、リンクだけを置きます。

## ファイル形式

frontmatter は `name` と `description` の2項目だけです。

```markdown
---
name: pkw-knowledge-steward
description: 個人ナレッジの読み書きと分類を担当する共有エージェント
---
```

- `description` は空にせず、200文字以内にします。表に載せるため `|` を含めません。
- 日本語で書いて構いません。
- ツールのネイティブなSkillと同じ形式のため、将来ネイティブな置き場へ配る場合に機械的に変換できます。

## 命名規則

- 名前は `pkw-` で始め、ASCIIのkebab-caseにします（例: `pkw-verify-knowledge-load`）。
- ファイル名は `<name>.md` にして、`name` と一致させます。
- `name` は `agents/` と `skills/` を通して一意にします。
- `pkw-` は、利用者がすでに持つグローバルSkillとの名前の衝突を避けるための識別子です。

## Skill一覧

エージェント定義の「Skill一覧」に、表で書きます。

```markdown
| name | description | 本文 |
|---|---|---|
| pkw-example | 例の説明 | [pkw-example.md](../skills/pkw-example.md) |
```

- 現在の作業が `description` に該当する場合だけ、リンク先の本文を読みます。該当しないSkillは開きません。
- 表の `name` と `description` は、Skill本文のfrontmatterと一致させます。
- 一覧は手で更新します。更新漏れは `validate_structure.py` が検出します。
- 最初のSkillは `pkw-verify-knowledge-load` です（#14）。移行後のナレッジが正しく読み込めているかを確認します。

## 入口からの参照

各入口の既存の書式に合わせて、エージェント定義への参照を1行追加します。

| 入口 | 書式 |
|---|---|
| `AGENTS.md` | 手順とリンク |
| `GEMINI.md` | `@./knowledge/00-rules/agents/pkw-knowledge-steward.md` |
| `.kiro/steering/knowledge-entry.md` | `#[[file:../../knowledge/00-rules/agents/pkw-knowledge-steward.md]]` |
| `.gemeni/`、`.claude/`、`.codex/` の `knowledge-entry.md` | リンク |

Skill本文は、どの入口でも取り込みません。

## 配布と更新

`knowledge/00-rules/` は、bootstrapの `default` profile に含まれます。ホームへの展開は、`target.root` にホームを指定します（`allow_home = true` が必要）。

`default` profile の全対象には、更新モード `update-if-unmodified` を適用します。

| ホーム側の状態 | 動作 |
|---|---|
| ファイルがない | 作成 |
| テンプレートと同一内容 | skip |
| 内容が違い、前回適用時のhashと一致（利用者が未変更） | 更新 |
| 内容が違い、前回適用時のhashと不一致、または適用記録がない | 衝突（全体を適用しない） |

前回適用時のhashは、Git管理外の `reports/bootstrap-state.json` に記録されたものです。ホーム側のファイルが、過去にテンプレートから配布した内容と一致する場合だけ更新するため、利用者の編集は上書きしません。

ホーム側で検証・修正した内容は、reverse-bootstrapでテンプレートへ戻せます。

## 検証

`validate_structure.py` が次を検査します。

- frontmatter に `name` と `description` があり、それ以外の項目がない
- `name` が `pkw-` で始まり、kebab-caseで、ファイル名と一致する
- `description` が空でなく、200文字以内で、`|` を含まない
- `name` が `agents/` と `skills/` を通して一意
- Skill一覧の表について、リンク切れがなく、表の `name` と `description` がSkill本文のfrontmatterと一致する
- すべてのSkillが、いずれかのエージェントの表に載っている
- 各入口が、エージェント定義への参照を持っている

## 制約

- ツールが専用ディレクトリのSkillを自動で見つけて起動する仕組みとは別物です。入口の指示にモデルが従って読む方式です。
- ツール固有の機能（サブエージェントの呼び出し、ツールの権限）は、初版では扱いません。
- 各AIツールがホーム直下の入口ファイルを実際に読むかは、#12 で検証します。
- 秘密情報、個人情報、絶対パスを書きません。

## 範囲外

- 実機での確認結果（#12、#14）は、確認後に追記します。
- ネイティブな置き場（例: `.kiro/skills/`）への配布は、必要になった時点で追加します。正本は `knowledge/00-rules/` のままです。