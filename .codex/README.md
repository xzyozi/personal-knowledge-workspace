# .codex

Codexの共有可能な入口・テンプレートを置くためのディレクトリです。

共通ルールの正本はルートの `AGENTS.md` と `knowledge/00-rules/` に置き、このディレクトリへ全文を重複させません。認証情報、ローカル設定、セッション状態はコミットしません。

## 入口

- [AGENTS.md](./AGENTS.md): ルートの `AGENTS.md` を読む指示です。管理ブロックで囲まれており、ホームの `~/.codex/AGENTS.md` に配布されます。ファイルがすでにある場合は、末尾に追記し、利用者の記述は変更しません。

## 共通参照入口

- [共通AI入口](../AGENTS.md)
- [ナレッジ索引](../knowledge/INDEX.md)
- [読み取りルール](../knowledge/00-rules/00.02-read-policy.md)
- [書き込みルール](../knowledge/00-rules/00.03-write-policy.md)
- [共有エージェント](../knowledge/00-rules/agents/pkw-knowledge-steward.md)
