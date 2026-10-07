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


```powershell
python scripts/validate_structure.py
```

同じ検証はGitHub Actionsでも実行します。

## ライセンス

Apache License 2.0。著作権表示の権利者・年は、配布方針を確定した時点で設定します。
