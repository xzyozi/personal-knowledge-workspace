# personal-knowledge-workspace

個人ナレッジ、定期記録、プロジェクト管理、AIツール向けの運用ルールを、MarkdownとGitで管理するためのワークスペースです。

## 目的

- 情報の原本・検証済み事実・成果物を分離する
- Johnny.Decimalの考え方で、情報の場所を固定する
- 定周期で作業の観測記録を保存する
- 必要な事実だけをAIに読ませ、全体の一括読み込みを避ける
- `GEMINI.md` と `.kiro`、`.gemeni`、`.claude`、`.codex` のAIツール連携を同居させる
- プロジェクトの現在状態と実装仕様を別々に管理する

## 基本構成

```text
.
├─ AGENTS.md
├─ PROJECT.md
├─ GEMINI.md
├─ knowledge/
│  ├─ INDEX.md
│  ├─ 00-rules/
│  ├─ 01-private/
│  ├─ 02-facts/
│  ├─ 03-output/
│  ├─ 04-sources/
│  ├─ 05-tasks/
│  ├─ 06-large/
│  └─ 99-archive/
├─ projects/
├─ scripts/
├─ templates/
├─ .kiro/
│  └─ steering/
├─ .gemeni/
├─ .claude/
├─ .codex/
└─ .github/workflows/
```

## 情報の流れ

```text
作業・ログ・外部資料
        ↓
knowledge/04-sources/
        ↓ 整理・検証
knowledge/02-facts/
        ↓ 必要に応じて生成
knowledge/03-output/
```

定期的な観測記録は `knowledge/04-sources/04.01-periodic-captures/` に追記します。現在有効な事実だけを `knowledge/02-facts/` に整理し、成果物やレポートは `knowledge/03-output/` に置きます。

## 読み取り方針

作業開始時にナレッジ全体を一括で読みません。まず `AGENTS.md`、`PROJECT.md`、`knowledge/00-rules/` を確認し、現在の作業に直接関係する `02-facts/` だけを選択的に読みます。

個人情報やローカル専用情報は `knowledge/01-private/` に置けますが、パスワード、APIキー、トークン、秘密鍵そのものは保存しません。大容量ファイルは `knowledge/06-large/` に置き、Gitには登録しません。

## AIツール対象

このリポジトリで共有テンプレートの対象にするAIツール入口は次のとおりです。

### 自動入口

- `AGENTS.md`: Claude Code、Codex、共通入口
- `GEMINI.md`: Gemini CLI
- `.kiro/steering/knowledge-entry.md`: Kiro

### 補助アダプター

- `.kiro/`
- `.gemeni/`
- `.claude/`
- `.codex/`

補助アダプターは共通入口とナレッジルールへの参照を提供します。ローカル設定、認証情報、セッション状態、個人パスはコミットしません。`.kiro`はプロジェクト自動検知のマーカーには使わず、共有READMEとSteering入口だけをテンプレート管理します。

## Reverse Bootstrap

bootstrap後にユーザー環境で検証・修正したテンプレートを、リポジトリの作業ツリーへ戻す場合は、default profileの対象だけを扱います。個人fact、private、sources、tasks、largeは標準対象外です。

```powershell
# dry-run（既定）
python scripts/reverse_bootstrap.py

# 作業ツリーへ反映
python scripts/reverse_bootstrap.py --apply --confirm

# レポートを表示
python scripts/view_bootstrap_report.py --report reverse

# 最終確認
git status
git diff
```

reverse-bootstrapはcommit・pushを行いません。詳細な設計と安全条件は`docs/design/reverse-bootstrap.md`を参照してください。

## 個人ナレッジの移行

ホーム配下の既存テキストを、個人ナレッジ用リポジトリの`knowledge/04-sources/04.00-inbox/`へ取り込みます。個人ナレッジはこのテンプレートリポジトリではなく、別のprivateリポジトリで管理します。スクリプトはGit操作を行いません。

移行元は、`config/bootstrap.local.toml`（Git管理外）にホームからの相対パスで指定します。

```toml
[migration]
sources = ["Documents/notes"]
```

```powershell
# dry-run（既定）
python scripts/migrate_knowledge.py

# 取り込み
python scripts/migrate_knowledge.py --apply --confirm

# 取り込み済みの内容をmanifestと照合（読み取り専用）
python scripts/migrate_knowledge.py --verify

# レポートを表示
python scripts/view_bootstrap_report.py --report migrate
```

- 全件を`04.00-inbox`へ、ホームからの相対パスを保ったまま取り込みます。`02-facts`などへの分類は手動で行います。
- 同名で内容が異なるファイルと、秘密情報の候補は、該当ファイルだけ取り込まず、残りを取り込みます。除外があれば終了コードは`10`です。
- バイナリは取り込まず、`knowledge/06-large/manifest.json`へ登録します。外部ストレージへのコピーと復元は手動です。
- 移行元は読み取り専用で、削除も上書きもしません。

推奨運用の例:

| 対象     | 推奨運用の例                                                |
| -------- | ----------------------------------------------------------- |
| テキスト | 作業区切りごとに個人リポジトリへcommit、週1回push           |
| バイナリ | 追加したタイミングで外部ストレージへコピー、月1回`--verify` |

詳細な設計と安全条件は`docs/design/migrate-knowledge.md`を参照してください。

## 共有エージェント

入口ファイルから、このプロジェクトが管理する共有エージェント（`knowledge/00-rules/agents/pkw-knowledge-steward.md`）を読めます。エージェントは、内部のSkillの一覧（名前と説明）を持ち、現在の作業に該当するSkillだけ本文を読みます。

```text
入口（AGENTS.md など） → knowledge/00-rules/agents/ → knowledge/00-rules/skills/
```

- `agents/` と `skills/` は`knowledge/00-rules/`の下にあるため、bootstrapで配布し、reverse-bootstrapでテンプレートへ戻せます。
- 名前は`pkw-`で始めます。frontmatterは`name`と`description`だけです。
- `python scripts/validate_structure.py`が、形式、Skill一覧との整合、入口からの参照を検査します。

詳細は`docs/design/shared-agents.md`を参照してください。

## 検証

追加依存関係なしで構造を検証できます。

```powershell
python scripts/validate_structure.py
```

同じ検証はGitHub Actionsでも実行します。

## ライセンス

Apache License 2.0。著作権表示の権利者・年は、配布方針を確定した時点で設定します。
