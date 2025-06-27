import requests
from bs4 import BeautifulSoup
import time
from tqdm.notebook import tqdm
import pandas as pd
import os
import re

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
    
    