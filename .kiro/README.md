# .kiro

Kiro用の共有アダプターです。

このディレクトリでは、他のAIツールと同じ共通入口・共有ルール参照だけを管理します。

## 管理対象

- `steering/knowledge-entry.md`
- 共有テンプレートとして安全なSteering参照

## 管理対象外

- 個人の認証情報
- ローカルのspec、hook、lesson、state
- セッション履歴、キャッシュ、一時ファイル
- ユーザー固有の絶対パス

`.kiro` はプロジェクト自動検知のマーカーとしては使用しません。Kiroの共有入口として、必要なファイルだけをbootstrap/installのallowlistで展開します。
