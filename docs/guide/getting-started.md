# はじめに

新しい環境で、このテンプレートを使い始めるまでの手順です。コマンドは、テンプレートリポジトリのrootで実行します。

`--apply` を付けるコマンドは、先にdry-run（`--apply` なし）の結果を確認してから実行してください。

## 前提

- Python 3.11以降（標準ライブラリだけを使います）
- ホームに展開する場合は、`config/bootstrap.local.toml` で `root = "~/"` と `allow_home = true` を指定している
- ホームの `knowledge/` は、独立したリポジトリ（個人側）として扱います。ホーム自体はGit作業ツリーにしません

初回の実行時に、`config/bootstrap.local.example.toml` から `config/bootstrap.local.toml` がコピーされます。このファイルはGit管理外です。

## 1. 共有の入口とルールを展開する（bootstrap）

```powershell
python scripts/bootstrap.py
python scripts/bootstrap.py --apply --confirm
```

- 配られるのは、各ツールの入口、`knowledge/INDEX.md`、`knowledge/00-rules/`（共有エージェントとSkill）です。
- 利用者が変更したファイルは上書きされず、衝突として止まります。

## 2. 個人側の骨格を作る（init）

```powershell
python scripts/init_knowledge.py
python scripts/init_knowledge.py --apply --confirm
```

- 作成先は `<target.root>/knowledge/` です。既存のファイルは、内容にかかわらずスキップします。
- 作るのは、READMEや `projects/INDEX.md` などの骨格だけです。テンプレート作者の原本は配りません。

## 3. 既存のナレッジを取り込む（migrate、必要な場合）

`config/bootstrap.local.toml` の `[migration] sources` に、ホームからの相対パスを書いてから実行します。

```powershell
python scripts/migrate_knowledge.py
python scripts/migrate_knowledge.py --apply --confirm
python scripts/migrate_knowledge.py --verify
```

- 取り込み先は `knowledge/04-sources/04.00-inbox/` です。`02-facts` などへの分類は手動で行います。
- `--verify` は、manifestと取り込み先を照合します（読み取り専用）。

## 4. 検証する

```powershell
python scripts/validate_structure.py
```

実行結果は、レポートで見られます。

```powershell
python scripts/view_bootstrap_report.py --report bootstrap
python scripts/view_bootstrap_report.py --report init
python scripts/view_bootstrap_report.py --report migrate
```

## 5. AIツールで確認する（実機確認）

CIで確認できるのは、構造と配布です。各ツールが実際に入口を読むかは、実機で確認します。

各ツール（Claude Code、Codex、Gemini CLI、Kiro）で、ホーム配下のプロジェクトを開き、次のように聞きます。

> 共有エージェントの名前と、使えるSkillの名前を教えてください。

期待する答えは、共有エージェント `pkw-knowledge-steward` と、Skill `pkw-verify-knowledge-load`、`pkw-init-knowledge` です。

次に、`pkw-verify-knowledge-load` を実行させ、結果の表を確認します。読み込まれたファイルの確認方法は、`../design/shared-agents.md` の「実機確認」を参照してください。

## 関連する文書

- [shared-agents.md](../design/shared-agents.md): 共有エージェントとSkill、実機確認
- [init-knowledge.md](../design/init-knowledge.md): 骨格の初期設定
- [migrate-knowledge.md](../design/migrate-knowledge.md): ナレッジの取り込み
- [reverse-bootstrap.md](../design/reverse-bootstrap.md): 環境側の修正をテンプレートへ戻す
- [path-design.md](../design/path-design.md): パスの扱いと未検証の制約

## 注意

- bootstrapは削除をしません。旧ファイルを配布済みの環境では、ホーム側で手で削除してください（`../design/shared-agents.md` の「旧ファイルの片付け」）。
- OneDrive配下と、権限不足の環境は、未検証です。
- 秘密情報（パスワード、APIキー、トークン、秘密鍵）は保存しません。
