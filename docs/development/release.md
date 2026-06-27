# リリース（npm / CI）

LocalAnt と同様、**git タグ `v*`** で GitHub Actions が npm に公開します。

## 初回準備

1. [npm](https://www.npmjs.com/package/note-connector) — **公開済み**（`note-connector@0.1.0`）
2. リポジトリ **Settings → Secrets → Actions** に `NPM_TOKEN`（Automation または Publish トークン）を登録（タグ `v*` で自動 publish 用）
3. npm で [Trusted Publishing](https://docs.npmjs.com/trusted-publishers)（GitHub Actions）を設定（推奨）

## バージョンを上げて公開

```bash
cd chatgpt
# 1. package.json の version を上げる（またはタグから CI が上書き）
npm version patch   # 0.1.0 → 0.1.1

# 2. リポジトリ全体のバージョンを揃える
cd ..
node scripts/sync-versions.mjs

git add chatgpt/package.json chatgpt/package-lock.json server.json pyproject.toml
git commit -m "chore: release v0.1.1"
git tag v0.1.1
git push origin main --tags
```

タグ `v0.1.1` の push で `.github/workflows/release.yml` が走り:

- `sync-versions.mjs` で `server.json` / `pyproject.toml` を同期
- `chatgpt/` で build / test
- `npm publish --provenance`

## ユーザー側のアップデート

```bash
note-connector update
note-connector update --check
```

## ローカル検証（publish 前）

```bash
cd chatgpt && npm ci && npm run build && npm test
npm pack --dry-run
```
