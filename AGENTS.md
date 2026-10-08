# AGENTS.md

このファイルは、AIツール共通の入口です。詳細な本文をここへ重複して書かず、正本を各参照先に置きます。

## 作業開始時

1. `PROJECT.md` で目的・状態・対象範囲を確認する。
2. `knowledge/INDEX.md` と `knowledge/00-rules/` を確認する。
3. 共有エージェント `knowledge/00-rules/agents/pkw-knowledge-steward.md` を確認し、現在の作業に該当するSkillだけを読む。
4. 現在の作業に直接関係する `knowledge/02-facts/` だけを選択的に読む。
5. 必要な場合だけ `knowledge/04-sources/`、`knowledge/05-tasks/`、`projects/` を読む。

## 読み取りルール

- `knowledge/02-facts/` 全体を一括で読まない。
- 作業と無関係なファイルを推測で読まない。
- `knowledge/01-private/` は自動的に読まない。
- `knowledge/06-large/` は明示的に必要な場合だけ参照する。
- 原本と成果物を事実として混同しない。
- `.kiro` はプロジェクト自動検知のマーカーとして扱わない。共有テンプレートのREADMEとSteering入口だけを対象にする。
- `.kiro` のローカルspec、hook、lesson、stateは自動的に読まない。
- `.gemini`、`.claude`、`.codex` は、該当するAIツールの作業時だけ対象にする。

## 書き込みルール

- 新しい情報は `knowledge/00-rules/00.04-classification-rule.md` で分類する。
- 原本・観測記録は `knowledge/04-sources/` に追記する。
- 検証済みの事実だけを `knowledge/02-facts/` に整理する。
- 生成物は `knowledge/03-output/` に置く。
- 認証情報、パスワード、APIキー、トークン、秘密鍵を保存しない。
- 不明点や承認が必要な操作は、勝手に補完せず停止する。

## 正本

- 共通入口: `AGENTS.md`
- プロジェクト状態: `PROJECT.md`
- ナレッジ運用: `knowledge/00-rules/`
- 共有エージェント: `knowledge/00-rules/agents/pkw-knowledge-steward.md`
- Gemini CLI入口: `GEMINI.md`
- Kiro入口: `.kiro/README.md`、`.kiro/steering/knowledge-entry.md`
- ツール別のグローバル入口（`AGENTS.md` への薄い参照）: `.claude/CLAUDE.md`、`.codex/AGENTS.md`、`.gemini/GEMINI.md`
