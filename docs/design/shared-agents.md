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

入口は2種類あります。

### リポジトリの入口（このリポジトリで作業する時）

| 入口 | 書式 |
|---|---|
| `AGENTS.md` | 手順とリンク（共有エージェントを確認する手順を含む） |
| `GEMINI.md` | `@./knowledge/00-rules/agents/pkw-knowledge-steward.md` |

### ツール別のグローバル入口（ホーム直下へ配布）

各ツールが実際に読むファイルです。どれも `AGENTS.md` への薄い参照で、**相対パス**で書くため、リポジトリでもホームでも同じファイルが正しく動きます。

| ファイル | ホーム側 | 書式 | モード |
|---|---|---|---|
| `.claude/CLAUDE.md` | `~/.claude/CLAUDE.md` | `@../AGENTS.md` のimport | `managed-block` |
| `.gemini/GEMINI.md` | `~/.gemini/GEMINI.md` | `@../AGENTS.md` のimport | `managed-block` |
| `.codex/AGENTS.md` | `~/.codex/AGENTS.md` | 「1つ上の `AGENTS.md`（グローバル設定の場合は `~/AGENTS.md`）を読む」という平文の指示 | `managed-block` |
| `.kiro/steering/knowledge-entry.md` | `~/.kiro/steering/knowledge-entry.md` | 「2つ上の `AGENTS.md`（グローバルsteeringの場合は `~/AGENTS.md`）を読む」という平文の指示 | `update-if-unmodified` |

- Kiroは、グローバルsteeringの置き場の外にあるファイルを `#[[file:...]]` で参照できません（#12 で確認）。そのため、参照ではなく平文の指示にします。
- Kiroのファイルだけ、ファイル全体をテンプレートが所有します。steeringはfrontmatterがファイルの先頭に必要で、このファイル名は専用のものだからです。
- Claude Codeは、`CLAUDE.md` が作業ディレクトリの上位にあると、同じ階層の `AGENTS.md` を自動では読みません。`.claude/CLAUDE.md` が `AGENTS.md` を取り込むことで、リポジトリでもホームでも `AGENTS.md` が読まれます。

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

ツール別のグローバル入口のうち、`.claude/CLAUDE.md`、`.codex/AGENTS.md`、`.gemini/GEMINI.md` は、利用者が自分の記述を書くファイルです。ファイル全体ではなく、**管理ブロック**だけをテンプレートが所有します（`managed-block` モード。詳細は `scripts/README.md`）。ファイルがなければ作成し、管理ブロックがなければ末尾に追記し、利用者の記述は変更しません。reverse-bootstrapは、これらを取り込みません。

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
- 管理ブロックのidが、bootstrapのtarget idと一致し、importが `AGENTS.md` に解決する
- グローバルsteeringが `#[[file:]]` を使わず、`AGENTS.md` を指す
- 改名前の表記が、管理対象のファイルに残っていない

## 実機確認

CIで確認できるのは、構造と配布です。各ツールが実際に入口を読むかは、実機で確認します。結果は #14 のコメントに記録します（リポジトリにはファイルとして残しません）。

### 手順

1. `python scripts/bootstrap.py` のdry-runで、ホームへの展開内容を確認する
2. `python scripts/bootstrap.py --apply --confirm` で展開する
3. 各ツールで、ホーム配下のプロジェクトを開き、次のように聞く

> 共有エージェントの名前と、使えるSkillの名前を教えてください。

期待する答えは、`pkw-knowledge-steward` と `pkw-verify-knowledge-load` です。

4. 共有Skill `pkw-verify-knowledge-load` を実行させ、結果の表を #14 に貼る

### 読み込まれたファイルの確認

| ツール | 方法 |
|---|---|
| Claude Code | `/memory`、`/context` で、読み込まれた `CLAUDE.md` と `AGENTS.md` を確認する |
| Gemini CLI | `/memory show` で、連結されたコンテキストを確認する |
| Codex | セッションの冒頭で読み込まれた指示を、ツールに説明させる |
| Kiro | 会話に読み込まれたルール（steering）を確認する |

Claude Codeは、プロジェクト外のファイルのimportに承認を求める場合があります。その挙動も、確認の対象です。

## 旧ファイルの片付け

bootstrapは削除をしません。次の旧ファイルを配布済みの環境では、ホーム側の該当ファイルを手で削除してください（dry-runには表示されません）。

| 旧ファイル（ホーム側） | 理由 |
|---|---|
| `~/.gemeni/`（`README.md`、`knowledge-entry.md`） | `.gemini` に改名したため。どのツールにも読まれない |
| `~/.claude/knowledge-entry.md` | `CLAUDE.md` に置き換えたため |
| `~/.codex/knowledge-entry.md` | `AGENTS.md` に置き換えたため |

`~/.kiro/steering/knowledge-entry.md` は、利用者が未変更であれば、bootstrapが更新します。

## 制約
- ツールが専用ディレクトリのSkillを自動で見つけて起動する仕組みとは別物です。入口の指示にモデルが従って読む方式です。
- ツール固有の機能（サブエージェントの呼び出し、ツールの権限）は、初版では扱いません。
- 各AIツールが入口を実際に読むかは、実機確認の節の手順で確認します。Kiroでは、グローバルsteeringが読み込まれることを確認しました（#12）。
- 秘密情報、個人情報、絶対パスを書きません。

## 範囲外

- 実機での確認結果（#12、#14）は、確認後に追記します。
- ネイティブな置き場（例: `.kiro/skills/`）への配布は、必要になった時点で追加します。正本は `knowledge/00-rules/` のままです。
