# AIツールの自動入口と共通参照入口

- 確認日: 2026-10-05
- カテゴリ: AIツール連携・ナレッジ入口
- 対象: Kiro、Claude Code、Codex、Gemini CLI
- 保存理由: 各AIツールの自動読込入口と、このリポジトリの薄いアダプターの役割を区別するため

## 結論

AIツール固有ディレクトリに `knowledge-entry.md` を置くだけでは、各ツールが自動的に読み込むとは限りません。自動入口と補助参照入口を分けます。

| ツール | 自動読込の標準入口 | このリポジトリでの状態 |
| --- | --- | --- |
| Kiro | `.kiro/steering/*.md` | `.kiro/steering/knowledge-entry.md`で参照済み |
| Claude Code | `CLAUDE.md` または `AGENTS.md` | ルート`AGENTS.md`を共通入口として利用 |
| Codex | `AGENTS.md` | ルート`AGENTS.md`を共通入口として利用 |
| Gemini CLI | `GEMINI.md` | ルート`GEMINI.md`は未作成。`.gemeni/knowledge-entry.md`は補助入口 |

## 共通ルールの参照先

各入口から次の正本を参照します。

- `AGENTS.md`
- `knowledge/INDEX.md`
- `knowledge/00-rules/00.02-read-policy.md`
- `knowledge/00-rules/00.03-write-policy.md`

ルール本文をAIツールごとに複製せず、ツール固有ファイルは薄いアダプターにします。

## ツール別の整理

### Kiro

Kiroの共有入口は `.kiro/steering/knowledge-entry.md` です。Steeringからルートの `AGENTS.md`、ナレッジ索引、読み書きルールを参照します。

### Claude Code

Claude Codeでは、ルートの `AGENTS.md` をプロジェクト指示の共通入口として利用できます。`.claude/knowledge-entry.md` は補助参照であり、`.claude/`に置くだけで自動入口になるとは扱いません。

### Codex

Codexでは、プロジェクトルートの `AGENTS.md` を自動入口として利用します。`.codex/knowledge-entry.md` は補助参照です。

### Gemini CLI

Gemini CLIの標準入口は `GEMINI.md` です。グローバル入口はユーザーホーム配下の `.gemini/GEMINI.md`、プロジェクト入口はリポジトリルートの `GEMINI.md` が候補になります。

Gemini CLIでは `@` 形式の相対参照を使い、共通ルールを取り込む構成が考えられます。

```markdown
# Gemini Universal Knowledge Entry

@./AGENTS.md
@./knowledge/INDEX.md
@./knowledge/00-rules/00.02-read-policy.md
@./knowledge/00-rules/00.03-write-policy.md
```

このリポジトリの `.gemeni/knowledge-entry.md` は、ユーザー指定の `.gemeni` アダプターとして保持します。ただし、Gemini CLIの自動入口として機能させるには、別途 `GEMINI.md` を追加する必要があります。

## 設計判断

- 共通ルールの正本はルート `AGENTS.md` と `knowledge/00-rules/` に置く。
- Kiro、Claude Code、Codexは、現在のルート入口を利用する。
- `.kiro`、`.gemeni`、`.claude`、`.codex` の `knowledge-entry.md` は、ツール固有の補助アダプターとする。
- Gemini CLIの自動読込対応は、ルート `GEMINI.md` の追加を別作業として扱う。
- ユーザー固有の絶対パス、認証情報、セッション状態はこの記録に保存しない。

## 公式情報

- [Kiro Steering](https://kiro.dev/docs/steering/)
- [Claude Code: CLAUDE.md and AGENTS.md](https://code.claude.com/docs/en/claude-md)
- [Codex: AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- [Gemini CLI: GEMINI.md](https://geminicli.com/docs/cli/gemini-md)

外部仕様は確認日時点の公式ドキュメントを要約したものです。仕様変更時は各公式情報を再確認します。
