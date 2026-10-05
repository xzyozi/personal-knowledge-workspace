# Project: personal-knowledge-workspace

## Status

- 状態: bootstrap
- 目的: 個人ナレッジ、定期記録、プロジェクト管理、AI運用ルールを一つのGitワークスペースで管理する
- 正本: このリポジトリ
- 次の確認: 実際の定期記録とAIツール設定を追加し、運用ルールを検証する

## Scope

- Markdownを正本としたナレッジ管理
- `00-rules`〜`99-archive` の固定分類
- Johnny.Decimal風の番号付きサブフォルダ
- `04-sources` への定周期キャプチャ
- `02-facts` への検証済み事実の昇格
- `PROJECT.md` と `projects/` によるプロジェクト管理
- `.kiro`、`.gemeni`、`.claude`、`.codex` のAIツール連携

## Non-goals

- 認証情報・秘密鍵・APIキーの保存
- `.kiro` をプロジェクト自動検知のマーカーとして使うこと
- `.kiro` のローカルspec、hook、lesson、stateの収集・分析
- AIによる事実の無承認な確定
- 大容量ファイルのGit管理
- 自動処理による送信・削除・公開などの不可逆操作

## Canonical locations

| 内容                   | 保存先                                      |
| ---------------------- | ------------------------------------------- |
| 入口と共通方針         | `AGENTS.md`                                 |
| プロジェクトの現在状態 | `PROJECT.md`                                |
| 読み書き・分類ルール   | `knowledge/00-rules/`                       |
| 検証済み事実           | `knowledge/02-facts/`                       |
| 生成成果物             | `knowledge/03-output/`                      |
| 原本・定期記録         | `knowledge/04-sources/`                     |
| タスク・次のアクション | `knowledge/05-tasks/`                       |
| プロジェクト一覧       | `projects/`                                 |
| 決定的な処理           | `scripts/`                                  |
| AIツール固有の入口     | `.kiro/`, `.gemeni/`, `.claude/`, `.codex/` |

## Change policy

1. 原本は `04-sources` に追記し、既存記録を上書きしない。
2. `02-facts` は検証済みの現在情報だけを置く。
3. `03-output` は再生成可能な成果物として扱う。
4. 秘密情報はファイルに書き込まず、ローカル設定もコミットしない。
5. ルール変更は成果物だけでなく、原因となるルール・スクリプト・テンプレートを修正する。
6. 不明点・矛盾・承認が必要な操作では停止し、推測で完了させない。
