# 画像操作

note-mcpでは、ChatGPTが生成・アップロードした画像を Apps SDK file parameter 経由で note.com に転送します。
すべての画像操作ツールはこの方式で動作し、`file_path` や `base64` の受け渡しは不要です。

## サポートされる形式

| 形式 | MIME Type |
|------|-----------|
| JPEG | image/jpeg |
| PNG | image/png |
| GIF | image/gif |
| WebP | image/webp |

**最大ファイルサイズ**: 10MB

## アイキャッチ画像

`note_set_eyecatch_image_file` ツールで記事の見出し（アイキャッチ）画像を設定します。
ChatGPTが生成した画像を Apps SDK file parameter として受け取り、note.com にアップロードします。
アイキャッチ画像は note 推奨サイズ（1280×670）に自動リサイズされます。

```
記事 n1234567890ab のアイキャッチ画像を設定してください
（画像はChatGPTが生成したものをfile parameterで渡します）
```

### パラメータ

| パラメータ | 説明 |
|-----------|------|
| `note_id` | noteの記事ID、または n... 形式の記事キー |
| `image_file` | Apps SDK file reference（download_url/file_id必須） |

### 戻り値

```json
{"ok": true, "data": {"note_id": "...", "article_url": "...", "eyecatch_url": "..."}}
```

## 本文への画像挿入

`note_insert_body_image` ツールで画像を記事本文に直接挿入します。
ChatGPTが生成した画像を Apps SDK file parameter として受け取り、
API経由で画像をアップロードした後、ProseMirrorで直接挿入します。

```
記事 n1234567890ab に画像を挿入してください
キャプション: 図1. システム構成図
（画像はChatGPTが生成したものをfile parameterで渡します）
```

### パラメータ

| パラメータ | 説明 |
|-----------|------|
| `article_id` | 画像を挿入する記事のキー（n... 形式） |
| `image_file` | Apps SDK file reference（download_url/file_id必須） |
| `caption` | 画像のキャプション（オプション） |

### 戻り値

```json
{"ok": true, "article_id": "...", "article_key": "...", "image_url": "..."}
```

## 下書き作成＋画像一括挿入

`note_create_draft_with_images` ツールで下書き作成と画像挿入を一度に行います。

```
タイトル「画像付き記事」、本文「...」で下書きを作成し、
画像を挿入してください
（画像はChatGPTが生成したものをfile parameterで渡します）
```

### パラメータ

| パラメータ | 説明 |
|-----------|------|
| `title` | 記事タイトル |
| `body` | 本文（Markdown） |
| `tags` | タグ（オプション） |
| `images` | Apps SDK file reference の配列 |

### 戻り値

```json
{"ok": true, "article_id": "...", "article_key": "...", "inserted": 2, "errors": []}
```

## 記事IDの確認

画像操作には記事キー（n... 形式）が必要です。`note_list_articles` で記事一覧を取得し、キーを確認できます。

```
記事一覧を取得してください
```

## エラーハンドリング

すべての画像ツールは `{"ok": false, "error": "..."}` 形式でエラーを返します。

| エラー | 原因 |
|--------|------|
| 未認証 | `note_login` が必要 |
| 画像形式無効 | サポートされる形式（JPEG/PNG/GIF/WebP）以外 |
| ファイルサイズ超過 | 10MB超 |
| SVG画像 | SVGは非対応 |
| ダウンロード失敗 | file reference が無効または期限切れ |

## ワークフロー例

### 記事作成から画像設定まで

1. 下書き記事を作成：
   ```
   タイトル「画像付き記事」で下書きを作成してください
   ```

2. 記事キーを確認：
   ```
   下書き記事の一覧を取得してください
   ```

3. アイキャッチ画像を設定：
   ```
   記事 n1234567890ab のアイキャッチ画像を設定してください
   ```

4. 本文に画像を挿入：
   ```
   記事 n1234567890ab に画像を挿入してください
   キャプション: 図1の説明
   ```

5. プレビューで確認：
   ```
   記事 n1234567890ab のプレビューを表示してください
   ```
