# UTA-NET 歌詞スクレイピングツール 🎵

uta-net.comから楽曲情報と歌詞を自動収集するPythonスクレイピングツールです。

## 📋 概要

このプロジェクトは、uta-net.com（日本最大級の歌詞検索サイト）から特定のアーティストの楽曲データを効率的に収集するためのツールです。楽曲ID収集から歌詞取得まで、完全自動化されたワークフローを提供します。

## ✨ 主要機能

### 🔍 楽曲ID収集 (`get_and_save_song_ids`)
- **ページネーション対応**: アーティストの全楽曲を自動で網羅
- **増分更新**: 既存データを保持して新規楽曲のみ追加
- **進行状況表示**: リアルタイム進捗バーで処理状況を可視化
- **エラー耐性**: ネットワークエラーやページ構造変更に対応

### 📝 歌詞スクレイピング (`scrape_and_save_lyrics`)
- **一括処理**: 大量の楽曲を効率的に処理
- **重複防止**: 既に取得済みの楽曲をスキップ
- **データ整形**: HTML形式から読みやすいテキストに変換
- **CSV保存**: 構造化されたデータとして保存

### 🎯 個別楽曲処理 (`get_song_title_and_lyrics`)
- **正確な抽出**: 楽曲タイトルと歌詞を正確に分離
- **フォーマット変換**: HTML改行タグを自然な改行に変換
- **エラーハンドリング**: データ欠損時の適切な対応

## 🚀 使用方法

### 基本的な使用例

```python
import scripts

# 1. 楽曲IDを収集
artist_url = "https://www.uta-net.com/artist/134/"  # アーティストのURL
song_ids = scripts.get_and_save_song_ids(artist_url)

# 2. 歌詞を一括取得
scripts.scrape_and_save_lyrics(song_ids, artist_id="134")
```

### 詳細な使用例

```python
# カスタムファイル名で保存
song_ids = scripts.get_and_save_song_ids(
    artist_page_url="https://www.uta-net.com/artist/134/",
    filepath="my_song_ids.csv"
)

# 特定の楽曲リストから歌詞を取得
scripts.scrape_and_save_lyrics(
    song_id_list=["123456", "234567", "345678"],
    filepath="my_lyrics.csv",
    artist_id="134"
)

# 個別楽曲の処理
title, lyrics = scripts.get_song_title_and_lyrics("123456")
print(f"タイトル: {title}")
print(f"歌詞: {lyrics}")
```

## 📦 必要なライブラリ

```bash
pip install requests beautifulsoup4 pandas tqdm
```

または

```bash
pip install -r requirements.txt
```

### ライブラリの詳細
- `requests`: HTTP通信
- `beautifulsoup4`: HTML解析
- `pandas`: データ処理・CSV操作
- `tqdm`: 進行状況バー表示

## 📁 ファイル構成

```
uta-net/
├── scripts.py              # メインスクレイピングスクリプト
├── lyrics_data.csv          # 取得済み歌詞データ
├── song_ids_134.csv         # 楽曲IDリスト
├── dev.ipynb               # 開発用Jupyter notebook
├── main.ipynb              # メイン処理用Jupyter notebook
└── README.md               # このファイル
```

## 🔧 設定とカスタマイズ

### サーバー負荷対策
```python
# scripts.py内で調整可能
time.sleep(1)  # リクエスト間隔（秒）
```

### ページネーション設定
```python
max_pages = 100  # 最大取得ページ数
```

### プログレスバー設定
```python
# tqdmの表示形式をカスタマイズ可能
tqdm(desc="処理中", unit="件")
```

## ⚠️ 注意事項

### 利用規約遵守
- uta-net.comの利用規約を必ず確認してください
- 過度なアクセスはサーバーに負荷をかけるため控えてください
- 商用利用については事前に許可を得てください

### 技術的制約
- **レート制限**: 各リクエスト後に1秒の待機時間を設けています
- **HTML構造依存**: サイトの構造変更により動作しなくなる可能性があります
- **ネットワーク環境**: 安定したインターネット接続が必要です

### データの取り扱い
- 取得したデータの著作権は各権利者に帰属します
- 個人利用の範囲内での使用を推奨します
- データの再配布時は適切な権利処理を行ってください

## 🛠️ トラブルシューティング

### よくある問題

**Q: HTTPエラー（403, 404など）が発生する**
```python
# User-Agentヘッダーを追加
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
response = requests.get(url, headers=headers)
```

**Q: CSVファイルの文字化け**
```python
# エンコーディングを明示指定
df = pd.read_csv('lyrics_data.csv', encoding='utf-8-sig')
```

**Q: メモリ不足エラー**
```python
# バッチ処理で分割実行
batch_size = 100
for i in range(0, len(song_ids), batch_size):
    batch = song_ids[i:i+batch_size]
    scrape_and_save_lyrics(batch)
```

## 📊 パフォーマンス

### 処理速度の目安
- 楽曲ID収集: 約20件/分（ページネーション含む）
- 歌詞取得: 約30件/分
- 1,000曲の完全処理: 約60-90分

### 最適化のヒント
- **並列処理**: 複数アーティストを同時処理
- **キャッシング**: 取得済みデータの再利用
- **バッチ処理**: メモリ効率の向上

## 🤝 貢献

プロジェクトへの貢献を歓迎します！

1. このリポジトリをフォーク
2. 機能ブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## 📄 ライセンス

このプロジェクトは個人利用・学習目的で作成されています。商用利用時は適切な権利処理を行ってください。

## 👨‍💻 作者

- データ収集・解析用途で開発
- 音楽データ研究プロジェクトの一環

## 🔗 関連リンク

- [uta-net.com](https://www.uta-net.com/) - 楽曲データソース
- [Beautiful Soup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Pandas Documentation](https://pandas.pydata.org/docs/)
- [Requests Documentation](https://docs.python-requests.org/)

---

**⚡ クイックスタート**
```bash
# プロジェクトを取得
git clone <repository-url>
cd uta-net

# 依存関係をインストール
pip install -r requirements.txt

# サンプル実行
python -c "import scripts; scripts.get_and_save_song_ids('https://www.uta-net.com/artist/134/')"
``` # utanet-to-notion
