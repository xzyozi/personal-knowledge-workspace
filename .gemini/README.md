# .gemini

Gemini CLIの共有可能な入口・テンプレートを置くためのディレクトリです。

共通ルールの正本はルートの `AGENTS.md` と `knowledge/00-rules/` に置き、このディレクトリへ全文を重複させません。認証情報、ローカル設定、セッション状態、個人パスはコミットしません。

## 入口

- [GEMINI.md](./GEMINI.md): `AGENTS.md` を取り込む薄い参照です。管理ブロックで囲まれており、ホームの `~/.gemini/GEMINI.md` に配布されます。ファイルがすでにある場合は、末尾に追記し、利用者の記述は変更しません。
- [ルートのGEMINI.md](../GEMINI.md): このリポジトリで作業する時の自動入口です。

## 共通参照入口

- [共通AI入口](../AGENTS.md)
- [ナレッジ索引](../knowledge/INDEX.md)
- [読み取りルール](../knowledge/00-rules/00.02-read-policy.md)
- [書き込みルール](../knowledge/00-rules/00.03-write-policy.md)
- [共有エージェント](../knowledge/00-rules/agents/pkw-knowledge-steward.md)
