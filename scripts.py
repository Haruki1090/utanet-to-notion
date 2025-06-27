import requests
from bs4 import BeautifulSoup
import time
from tqdm.notebook import tqdm
import pandas as pd
import os
import re
from dotenv import load_dotenv
from datetime import datetime, timezone

# 環境変数を読み込み
load_dotenv()

# Notion API設定
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# song_idのリストを取得し、CSVに保存/読み込みする（ページネーション対応）
def get_and_save_song_ids(artist_page_url, filepath=None):
    # アーティストIDを抽出（URLから）
    artist_id = artist_page_url.rstrip('/').split('/')[-1]
    
    # ファイルパスが指定されていない場合、アーティストIDを含むファイル名を作成
    if filepath is None:
        filepath = f'song_ids_{artist_id}.csv'
    
    existing_song_ids = []
    if os.path.exists(filepath):
        print(f"{filepath}が見つかりました。既存のsong_idを読み込みます。")
        df = pd.read_csv(filepath)
        existing_song_ids = df['song_id'].astype(str).tolist()
        print(f"既存のsong_id数: {len(existing_song_ids)}件")
    else:
        print(f"{filepath}が見つかりません。新規でsong_idをスクレイピングします。")
    
    print(f"アーティストID {artist_id} の全ページをスクレイピングして最新の曲リストを取得します。")
    
    song_id_list = []
    page = 1
    max_pages = 100  # 最大ページ数の推定値（実際の処理では動的に調整）
    
    # ページ処理の進行状況バー
    page_pbar = tqdm(desc="ページを取得中", unit="page")
    
    while True:
        page_pbar.set_description(f"ページ{page}を取得中")
        page_pbar.update(0)  # 表示更新
        
        # ページURLを構築
        if page == 1:
            current_url = artist_page_url
        else:
            # 2ページ目以降のURL構造: /artist/{artist_id}/0/{page}/
            current_url = f"https://www.uta-net.com/artist/{artist_id}/0/{page}/"
        
        try:
            # ページのHTMLを取得
            response = requests.get(current_url)
            if response.status_code != 200:
                page_pbar.set_description(f"ページ{page}の取得失敗 (ステータス: {response.status_code})")
                break
                
            page_html = response.text
            time.sleep(1)  # サーバー負荷軽減
            
            # BeautifulSoupで解析
            soup = BeautifulSoup(page_html, "html.parser")
            
            # このページの曲リンクを取得
            page_song_links = soup.find_all("a", class_="py-2 py-lg-0")
            
            if not page_song_links:
                page_pbar.set_description(f"ページ{page}に曲が見つかりません")
                break
            
            # 曲のIDを抽出（このページ用の進行状況バー）
            page_song_count = 0
            for song_link in tqdm(page_song_links, desc=f"ページ{page}の曲を処理中", leave=False):
                href = song_link.get("href")
                if href and "/song/" in href:
                    try:
                        song_id = href.split("/")[-2]
                        song_id_list.append(song_id)
                        page_song_count += 1
                    except IndexError:
                        continue  # エラーは静かに処理
            
            page_pbar.set_description(f"ページ{page}完了 ({page_song_count}曲)")
            page_pbar.update(1)
            
            # 次のページが存在するかチェック
            next_page_exists = False
            
            # ページネーションのリンクをチェック
            pagination_links = soup.find_all("a", class_="page-link")
            for link in pagination_links:
                href = link.get("href")
                if href and f"/artist/{artist_id}/0/{page + 1}/" in href:
                    next_page_exists = True
                    break
            
            # または、現在のページに曲数が多い場合は次のページが存在する可能性が高い
            if page_song_count >= 20:
                next_page_exists = True
            
            if not next_page_exists:
                page_pbar.set_description(f"全{page}ページ完了")
                break
                
            page += 1
            
        except Exception as e:
            page_pbar.set_description(f"ページ{page}でエラー: {str(e)[:30]}...")
            break
    
    page_pbar.close()
    
    # 重複を除去してソート
    song_id_list = sorted(list(set(song_id_list)))
    print(f"スクレイピングで取得した総曲数: {len(song_id_list)}件")
    
    # 新しいsong_idを特定
    new_song_ids = [sid for sid in song_id_list if sid not in existing_song_ids]
    
    if new_song_ids:
        print(f"新しいsong_idが{len(new_song_ids)}件見つかりました。CSVに追加保存します。")
        
        # 全てのsong_idをCSVに保存（既存 + 新規）
        all_song_ids = sorted(list(set(existing_song_ids + song_id_list)))
        df = pd.DataFrame({'song_id': all_song_ids})
        df.to_csv(filepath, index=False)
        print(f"{filepath}に合計{len(all_song_ids)}件のsong_idを保存しました。")
    else:
        print("新しいsong_idは見つかりませんでした。")
    
    # 最終的な全song_idのリストを返す
    final_song_ids = sorted(list(set(existing_song_ids + song_id_list)))
    return final_song_ids

# 歌詞をスクレイピングしてCSVに保存する
def scrape_and_save_lyrics(song_id_list, filepath=None, artist_id=None):
    
    # ファイルパスが指定されていない場合、アーティストIDを含むファイル名を作成
    if filepath is None:
        if artist_id:
            filepath = f'lyrics_data_{artist_id}.csv'
        else:
            filepath = 'lyrics_data.csv'
    
    # 既に取得済みのsong_idを読み込む
    processed_ids = []
    if os.path.exists(filepath):
        try:
            processed_df = pd.read_csv(filepath)
            if 'song_id' in processed_df.columns:
                processed_ids = processed_df['song_id'].astype(str).tolist()
        except (pd.errors.EmptyDataError, FileNotFoundError):
            print(f"{filepath}は空か、見つかりませんでした。")


    # これから処理するsong_idのリスト
    target_ids = [sid for sid in song_id_list if str(sid) not in processed_ids]

    if not target_ids:
        print("すべての曲の歌詞を取得済みです。")
        return

    print(f"合計{len(song_id_list)}曲のうち、{len(target_ids)}件の新しい曲の歌詞を取得します。")

    # ヘッダーの書き込み（ファイルが空か、存在しない場合）
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        pd.DataFrame(columns=['song_id', 'title', 'artist', 'main_theme', 'lyricist', 'composer', 'arranger', 'release_date', 'cover_url', 'lyrics']).to_csv(filepath, index=False, encoding='utf-8-sig')

    # 曲の詳細情報と歌詞を取得してCSVに追記
    for song_id in tqdm(target_ids, desc="楽曲情報を取得中"):
        try:
            song_data = get_song_details_and_lyrics(song_id)
            
            # データをDataFrameにしてCSVに追記
            new_data = pd.DataFrame([song_data])
            new_data.to_csv(filepath, mode='a', header=False, index=False, encoding='utf-8-sig')

        except Exception as e:
            print(f"song_id: {song_id} の処理中にエラーが発生しました: {e}")
            # エラーログなどをここに記述可能
            continue
            
    print("楽曲情報の取得と保存が完了しました。")

# 曲のIDを渡すと、その曲の詳細情報と歌詞を取得する
def get_song_details_and_lyrics(song_id):
    # 曲のページのURLを作成
    song_page_url = f"https://www.uta-net.com/song/{song_id}/"
    
    # 曲のページのHTMLを取得
    song_page_html = requests.get(song_page_url).text
    time.sleep(1) # サーバー負荷軽減
    
    # BeautifulSoupで解析の準備
    soup_song = BeautifulSoup(song_page_html, "html.parser")
    
    # 楽曲詳細情報を含むエリアを取得
    song_details = soup_song.find("div", class_="blur-filter row py-3")
    
    # デフォルト値を設定
    song_data = {
        "song_id": song_id,
        "title": "",
        "artist": "",
        "main_theme": "",
        "lyricist": "",
        "composer": "",
        "arranger": "",
        "release_date": "",
        "cover_url": "",
        "lyrics": ""
    }
    
    try:
        # 曲のタイトルを取得
        title_tag = song_details.find("h2", class_="ms-2 ms-md-3 kashi-title")
        if not title_tag:
            title_tag = soup_song.find("h2", class_="ms-2")
        song_data["title"] = title_tag.text.strip() if title_tag else ""
        
        # アーティスト名を取得
        artist_tag = song_details.find("h3", class_="ms-2 ms-md-3")
        song_data["artist"] = artist_tag.text.strip() if artist_tag else ""
        
        # 主題歌情報を取得
        main_theme_tag = song_details.find("p", class_="ms-2 ms-md-3 mb-0")
        song_data["main_theme"] = main_theme_tag.text.strip().replace("\xa0", "") if main_theme_tag else ""
        
        # 詳細情報（作詞者、作曲者、編曲者、発売日）を取得
        detail_section = song_details.find("p", class_="ms-2 ms-md-3 detail mb-0")
        if detail_section:
            # 作詞者
            lyricist_link = detail_section.find("a", href=re.compile(r"/lyricist/"))
            song_data["lyricist"] = lyricist_link.text.strip() if lyricist_link else ""
            
            # 作曲者
            composer_link = detail_section.find("a", href=re.compile(r"/composer/"))
            song_data["composer"] = composer_link.text.strip() if composer_link else ""
            
            # 編曲者
            arranger_link = detail_section.find("a", href=re.compile(r"/arranger/"))
            song_data["arranger"] = arranger_link.text.strip() if arranger_link else ""
            
            # 発売日
            detail_text = detail_section.text
            if "発売日：" in detail_text:
                release_date_match = detail_text.split("発売日：")[1].split()[0]
                song_data["release_date"] = release_date_match
        
        # カバー画像URLを取得
        cover_img = song_details.find("img", class_="img-fluid")
        song_data["cover_url"] = cover_img["src"] if cover_img and cover_img.get("src") else ""
        
    except Exception as e:
        print(f"楽曲詳細情報の取得中にエラーが発生しました (song_id: {song_id}): {e}")
    
    try:
        # 曲の歌詞を取得
        kashi_area = soup_song.find("div", id="kashi_area")
        if kashi_area:
            # <br>タグを改行文字に置換
            for br in kashi_area.find_all("br"):
                br.replace_with("\n")
            song_data["lyrics"] = kashi_area.get_text().strip()
    except Exception as e:
        print(f"歌詞の取得中にエラーが発生しました (song_id: {song_id}): {e}")

    return song_data

# 後方互換性のために古い関数名も残す
def get_song_title_and_lyrics(song_id):
    """後方互換性のための関数（非推奨）"""
    song_data = get_song_details_and_lyrics(song_id)
    return song_data["title"], song_data["lyrics"]

# Notionにデータを送信する関数
def upload_to_notion(song_data, max_retries=3):
    """
    楽曲データをNotionデータベースに追加する
    
    Args:
        song_data (dict): 楽曲データ
        max_retries (int): 最大リトライ回数
    
    Returns:
        bool: 成功した場合True、失敗した場合False
    """
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        print("Notion APIの設定が不完全です。NOTION_TOKENとNOTION_DATABASE_IDを環境変数に設定してください。")
        return False
    
    # NotionAPIに送信するためのデータ形式に変換
    notion_data = convert_to_notion_format(song_data)
    
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": notion_data
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=NOTION_HEADERS, json=payload)
            
            if response.status_code == 200 or response.status_code == 201:
                return True
            elif response.status_code == 429:  # Rate limit
                retry_after = int(response.headers.get('Retry-After', 1))
                print(f"レートリミットが発生しました。{retry_after}秒待機します...")
                time.sleep(retry_after)
                continue
            else:
                print(f"Notion APIエラー (song_id: {song_data.get('song_id', 'unknown')}): {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"リクエスト中にエラーが発生しました (song_id: {song_data.get('song_id', 'unknown')}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数バックオフ
                continue
            return False
    
    return False

def convert_to_notion_format(song_data):
    """
    楽曲データをNotion API形式に変換する
    
    Args:
        song_data (dict): 楽曲データ
    
    Returns:
        dict: Notion API形式のデータ
    """
    def is_valid_data(value):
        """データが有効かどうかをチェック（nan、None、空文字列を除外）"""
        if value is None:
            return False
        if pd.isna(value):  # pandas NaN をチェック
            return False
        str_value = str(value).strip().lower()
        if str_value in ['', 'nan', 'none', 'null']:
            return False
        return True
    
    def get_clean_text(value, max_length=2000):
        """テキストデータをクリーンアップして返す"""
        if not is_valid_data(value):
            return ""
        cleaned_text = str(value).strip()
        if max_length is not None:
            return cleaned_text[:max_length]
        return cleaned_text
    
    notion_data = {}
    
    # song_id (number)
    if song_data.get('song_id') and is_valid_data(song_data['song_id']):
        try:
            notion_data["song_id"] = {"number": int(song_data['song_id'])}
        except (ValueError, TypeError):
            notion_data["song_id"] = {"number": None}
    
    # title (title) - Notionのタイトルプロパティ
    title_text = get_clean_text(song_data.get('title'))
    if title_text:
        notion_data["title"] = {
            "title": [{"text": {"content": title_text}}]
        }
    
    # artist (text)
    artist_text = get_clean_text(song_data.get('artist'))
    if artist_text:
        notion_data["artist"] = {
            "rich_text": [{"text": {"content": artist_text}}]
        }
    
    # main_theme (text) - 主題歌情報
    main_theme_text = get_clean_text(song_data.get('main_theme'))
    if main_theme_text:
        notion_data["main_theme"] = {
            "rich_text": [{"text": {"content": main_theme_text}}]
        }
    
    # lyricist (text)
    lyricist_text = get_clean_text(song_data.get('lyricist'))
    if lyricist_text:
        notion_data["lyricist"] = {
            "rich_text": [{"text": {"content": lyricist_text}}]
        }
    
    # composer (text)
    composer_text = get_clean_text(song_data.get('composer'))
    if composer_text:
        notion_data["composer"] = {
            "rich_text": [{"text": {"content": composer_text}}]
        }
    
    # arranger (text)
    arranger_text = get_clean_text(song_data.get('arranger'))
    if arranger_text:
        notion_data["arranger"] = {
            "rich_text": [{"text": {"content": arranger_text}}]
        }
    
    # release_date (date)
    if song_data.get('release_date') and is_valid_data(song_data['release_date']):
        try:
            # 日付形式を変換 (YYYY/MM/DD → YYYY-MM-DD)
            date_str = str(song_data['release_date']).replace('/', '-')
            # 日付の妥当性をチェック
            datetime.strptime(date_str, '%Y-%m-%d')
            notion_data["release_date"] = {"date": {"start": date_str}}
        except (ValueError, TypeError):
            # 無効な日付の場合はNullに設定
            notion_data["release_date"] = {"date": None}
    
    # cover (file) - URLから
    cover_url = get_clean_text(song_data.get('cover_url'))
    if cover_url and cover_url.startswith('http'):
        notion_data["cover"] = {
            "files": [{
                "type": "external",
                "name": f"cover_{song_data.get('song_id', 'unknown')}.jpg",
                "external": {"url": cover_url}
            }]
        }
    
    # lyrics (text) - 長いテキストの場合は分割
    lyrics_text = get_clean_text(song_data.get('lyrics'), max_length=None)  # 歌詞は長いので制限なし
    if lyrics_text:
        # Notionのrich_textは2000文字制限があるため、必要に応じて分割
        if len(lyrics_text) <= 2000:
            notion_data["lyrics"] = {
                "rich_text": [{"text": {"content": lyrics_text}}]
            }
        else:
            # 2000文字を超える場合は複数のtextブロックに分割
            chunks = [lyrics_text[i:i+2000] for i in range(0, len(lyrics_text), 2000)]
            notion_data["lyrics"] = {
                "rich_text": [{"text": {"content": chunk}} for chunk in chunks[:100]]  # 最大100ブロック
            }
    
    return notion_data

def upload_csv_to_notion(csv_filepath, batch_size=10, delay_between_requests=1.0):
    """
    CSVファイルの全データをNotionにアップロードする
    
    Args:
        csv_filepath (str): CSVファイルのパス
        batch_size (int): バッチサイズ（一度に処理する件数）
        delay_between_requests (float): リクエスト間の待機時間（秒）
    
    Returns:
        dict: アップロード結果の統計情報
    """
    if not os.path.exists(csv_filepath):
        print(f"CSVファイルが見つかりません: {csv_filepath}")
        return {"success": 0, "failed": 0, "total": 0}
    
    # CSVファイルを読み込み
    try:
        df = pd.read_csv(csv_filepath)
        print(f"CSVファイルを読み込みました: {len(df)}件のデータ")
    except Exception as e:
        print(f"CSVファイルの読み込みに失敗しました: {e}")
        return {"success": 0, "failed": 0, "total": 0}
    
    # 既にNotionに存在するsong_idをチェック（オプション）
    existing_song_ids = get_existing_notion_song_ids()
    
    # アップロード対象をフィルタリング
    if existing_song_ids:
        df_to_upload = df[~df['song_id'].astype(str).isin(existing_song_ids)]
        print(f"既にNotionに存在する{len(df) - len(df_to_upload)}件をスキップします。")
        print(f"新規アップロード対象: {len(df_to_upload)}件")
    else:
        df_to_upload = df
        print(f"全{len(df_to_upload)}件をアップロードします。")
    
    if len(df_to_upload) == 0:
        print("アップロードする新しいデータがありません。")
        return {"success": 0, "failed": 0, "total": 0}
    
    # 結果カウンター
    success_count = 0
    failed_count = 0
    total_count = len(df_to_upload)
    
    # プログレスバーを設定
    progress_bar = tqdm(df_to_upload.iterrows(), total=total_count, desc="Notionにアップロード中")
    
    # バッチ処理
    for i, (index, row) in enumerate(progress_bar):
        song_data = row.to_dict()
        
        # Notionにアップロード
        if upload_to_notion(song_data):
            success_count += 1
            progress_bar.set_description(f"成功: {success_count}, 失敗: {failed_count}")
        else:
            failed_count += 1
            progress_bar.set_description(f"成功: {success_count}, 失敗: {failed_count}")
        
        # バッチ間での待機
        if (i + 1) % batch_size == 0:
            time.sleep(delay_between_requests * 2)  # バッチ後は長めに待機
        else:
            time.sleep(delay_between_requests)
    
    progress_bar.close()
    
    result = {
        "success": success_count,
        "failed": failed_count,
        "total": total_count
    }
    
    print(f"\nアップロード完了!")
    print(f"成功: {success_count}件")
    print(f"失敗: {failed_count}件")
    print(f"合計: {total_count}件")
    
    return result

def get_existing_notion_song_ids():
    """
    Notionデータベースから既存のsong_idリストを取得する
    
    Returns:
        list: 既存のsong_idのリスト
    """
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        return []
    
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    existing_ids = []
    start_cursor = None
    
    try:
        while True:
            payload = {"page_size": 100}
            if start_cursor:
                payload["start_cursor"] = start_cursor
            
            response = requests.post(url, headers=NOTION_HEADERS, json=payload)
            
            if response.status_code != 200:
                print(f"Notionからのデータ取得でエラーが発生しました: {response.status_code}")
                break
            
            data = response.json()
            
            for page in data.get("results", []):
                props = page.get("properties", {})
                song_id_prop = props.get("song_id", {})
                if song_id_prop.get("number") is not None:
                    existing_ids.append(str(song_id_prop["number"]))
            
            if not data.get("has_more", False):
                break
            
            start_cursor = data.get("next_cursor")
            time.sleep(0.5)  # レートリミット対策
            
    except Exception as e:
        print(f"既存データの取得中にエラーが発生しました: {e}")
    
    return existing_ids

# Jupyter notebook用の簡潔な関数群
def check_notion_setup():
    """
    Notion APIの設定状況を確認し、結果を表示する
    
    Returns:
        bool: 設定が完了している場合True
    """
    try:
        notion_token = os.getenv('NOTION_TOKEN')
        notion_db_id = os.getenv('NOTION_DATABASE_ID')
        
        print(f"NOTION_TOKEN: {'✅ 設定済み' if notion_token else '❌ 未設定'}")
        print(f"NOTION_DATABASE_ID: {'✅ 設定済み' if notion_db_id else '❌ 未設定'}")
        
        if not notion_token or not notion_db_id:
            print("\n⚠️ 環境変数が設定されていません。")
            print("env_example.txtを参考に.envファイルを作成し、適切な値を設定してください。")
            return False
        else:
            print("\n✅ 環境変数の設定が完了しています。")
            return True
            
    except Exception as e:
        print(f"❌ 設定確認中にエラーが発生しました: {e}")
        return False

def check_csv_data(csv_file='lyrics_data.csv'):
    """
    CSVファイルの存在と内容を確認し、結果を表示する
    
    Args:
        csv_file (str): チェック対象のCSVファイルパス
    
    Returns:
        bool: CSVファイルが存在し、読み込み可能な場合True
    """
    try:
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            print(f"✅ {csv_file}が見つかりました。")
            print(f"総レコード数: {len(df)}件")
            print(f"\nデータサンプル:")
            print(df[['song_id', 'title', 'artist', 'release_date']].head())
            return True
        else:
            print(f"❌ {csv_file}が見つかりません。")
            print("まず、楽曲データのスクレイピングを実行してください。")
            return False
            
    except Exception as e:
        print(f"❌ CSVファイル確認中にエラーが発生しました: {e}")
        return False

def check_existing_notion_data():
    """
    Notionの既存データ数を確認し、結果を表示する
    
    Returns:
        list: 既存のsong_idリスト
    """
    try:
        print("Notionから既存データを確認中...")
        existing_ids = get_existing_notion_song_ids()
        
        if existing_ids:
            print(f"✅ Notionに既に存在するデータ: {len(existing_ids)}件")
            print(f"既存のsong_id例: {existing_ids[:5]}")
        else:
            print("📋 Notionにデータは存在しません。全データが新規アップロード対象です。")
        
        return existing_ids
        
    except Exception as e:
        print(f"❌ 既存データ確認中にエラーが発生しました: {e}")
        return []

def test_notion_upload(csv_file='lyrics_data.csv'):
    """
    1件のテストアップロードを実行する
    
    Args:
        csv_file (str): CSVファイルのパス
    
    Returns:
        bool: テストが成功した場合True
    """
    try:
        if not os.path.exists(csv_file):
            print(f"❌ {csv_file}が見つかりません。")
            return False
        
        df = pd.read_csv(csv_file)
        
        # 最初の1件を取得
        test_data = df.iloc[0].to_dict()
        
        print(f"🧪 テストデータ: song_id={test_data['song_id']}, title={test_data['title']}")
        
        # アップロード実行
        result = upload_to_notion(test_data)
        
        if result:
            print("✅ テストアップロードが成功しました！")
            print("Notionデータベースを確認してください。")
            return True
        else:
            print("❌ テストアップロードが失敗しました。")
            print("エラーメッセージを確認し、設定を見直してください。")
            return False
            
    except Exception as e:
        print(f"❌ テストアップロード中にエラーが発生しました: {e}")
        return False

def run_full_notion_upload(csv_file='lyrics_data.csv', batch_size=5, delay=1.5):
    """
    全データのNotionアップロードを実行する（エラーハンドリング込み）
    
    Args:
        csv_file (str): CSVファイルのパス
        batch_size (int): バッチサイズ
        delay (float): リクエスト間隔（秒）
    
    Returns:
        dict: アップロード結果の統計情報
    """
    try:
        if not os.path.exists(csv_file):
            print(f"❌ {csv_file}が見つかりません。")
            return {"success": 0, "failed": 0, "total": 0, "error": "CSV file not found"}
        
        print("🚀 全データのアップロードを開始します...")
        print(f"設定: バッチサイズ={batch_size}件, リクエスト間隔={delay}秒")
        
        result = upload_csv_to_notion(
            csv_filepath=csv_file,
            batch_size=batch_size,
            delay_between_requests=delay
        )
        
        print(f"\n📊 最終結果:")
        print(f"✅ 成功: {result['success']}件")
        print(f"❌ 失敗: {result['failed']}件")
        print(f"📈 合計: {result['total']}件")
        
        if result['failed'] > 0:
            print(f"\n⚠️ {result['failed']}件の失敗がありました。")
            print("エラーログを確認し、必要に応じて再実行してください。")
        else:
            print("\n🎉 全データのアップロードが正常に完了しました！")
        
        return result
        
    except Exception as e:
        print(f"❌ アップロード中に予期しないエラーが発生しました: {e}")
        return {"success": 0, "failed": 0, "total": 0, "error": str(e)}

def notion_upload_workflow(csv_file='lyrics_data.csv', skip_test=False, batch_size=5, delay=1.5):
    """
    Notionアップロードの全ワークフローを実行する
    
    Args:
        csv_file (str): CSVファイルのパス
        skip_test (bool): テストアップロードをスキップするか
        batch_size (int): バッチサイズ
        delay (float): リクエスト間隔（秒）
    
    Returns:
        dict: 実行結果
    """
    print("=== Notion アップロード ワークフロー ===\n")
    
    # Step 1: 環境変数チェック
    if not check_notion_setup():
        return {"status": "failed", "step": "setup_check", "message": "環境変数の設定が不完全です"}
    
    print("\n" + "="*50 + "\n")
    
    # Step 2: CSVファイルチェック
    if not check_csv_data(csv_file):
        return {"status": "failed", "step": "csv_check", "message": "CSVファイルの確認に失敗しました"}
    
    print("\n" + "="*50 + "\n")
    
    # Step 3: 既存データチェック
    existing_data = check_existing_notion_data()
    
    print("\n" + "="*50 + "\n")
    
    # Step 4: テストアップロード（オプション）
    if not skip_test:
        print("🧪 テストアップロードを実行中...")
        if not test_notion_upload(csv_file):
            return {"status": "failed", "step": "test_upload", "message": "テストアップロードに失敗しました"}
        print("\n" + "="*50 + "\n")
    
    # Step 5: 全データアップロード
    result = run_full_notion_upload(csv_file, batch_size, delay)
    
    if result.get("error"):
        return {"status": "failed", "step": "full_upload", "message": result["error"], "result": result}
    
    return {"status": "success", "step": "completed", "result": result}
    
    