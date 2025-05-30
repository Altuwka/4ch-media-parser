import os
import json
import time
import requests
from urllib.parse import urljoin
from pathlib import Path
import re

# === НАСТРОЙКИ ===
BOARD = "b"                   # Доска, например "pol", "mu"
UPDATE_INTERVAL = 600         # Интервал в секундах (10 минут)
BASE_URL = "https://a.4cdn.org" 
IMAGE_HOST = "https://i.4cdn.org" 
CACHE_FILE = "cache.json"
MEDIA_DIR = Path("downloads") / BOARD
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"

# Создаем папку под загрузки
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_filename(name):
    """Очистить строку от недопустимых символов в Windows"""
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)
    return sanitized[:100]  # Ограничиваем длину до 100 символов

def get_catalog_threads():
    """Получить список тредов из catalog.json (4chan)"""
    url = f"{BASE_URL}/{BOARD}/catalog.json"
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()

            threads = []
            for page in data:
                for thread in page.get("threads", []):
                    subject = thread.get("sub", "Без темы")
                    cleaned_subject = sanitize_filename(subject)
                    threads.append({
                        "num": str(thread.get("no", "")),
                        "subject": cleaned_subject or "без_темы"
                    })
            return threads
        else:
            print(f"[HTTP ошибка] Код: {response.status_code}, URL: {url}")
    except Exception as e:
        print(f"[Ошибка при получении каталога] {e}")
    return []

def get_thread_posts(thread_num):
    """Получить все посты из треда по его номеру (4chan)"""
    url = f"{BASE_URL}/{BOARD}/thread/{thread_num}.json"
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get("posts", [])
        else:
            print(f"[HTTP ошибка] Код: {response.status_code}, URL: {url}")
    except Exception as e:
        print(f"[Ошибка при получении постов треда {thread_num}] {e}")
    return []

def download_media(post, thread_dir):
    """Скачать медиафайлы из поста в папку треда (4chan)"""
    tim = post.get("tim")
    ext = post.get("ext")

    if not tim or not ext:
        return []

    file_url = f"{IMAGE_HOST}/{BOARD}/{tim}{ext}"
    filename = f"{tim}{ext}"
    save_path = thread_dir / filename

    if save_path.exists():
        return []

    try:
        print(f"[Загрузка] {file_url}")
        with requests.get(file_url, stream=True, headers={"User-Agent": USER_AGENT}) as r:
            if r.status_code == 403:
                print("[Ошибка] Получен ответ 403 — возможно, CDN блокирует запрос")
                return []
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return [str(save_path)]
    except Exception as e:
        print(f"[Ошибка загрузки файла] {e}")
    return []

def load_cache():
    """Загрузить кэш ранее обработанных тредов и файлов"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {"threads": {}}

def save_cache(cache):
    """Сохранить кэш"""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def main():
    cache = load_cache()
    threads_key = f"{BOARD}_threads"
    if threads_key not in cache:
        cache[threads_key] = {}

    while True:
        print("\n[INFO] Получаю список тредов из каталога...")
        catalog_threads = get_catalog_threads()

        if not catalog_threads:
            print("[Ошибка] Не удалось получить треды из каталога.")
            time.sleep(300)
            continue

        for thread in catalog_threads:
            thread_num = thread["num"]
            thread_subject = thread["subject"] or "без_темы"
            thread_dir = MEDIA_DIR / f"{thread_num}_{thread_subject}"
            thread_dir.mkdir(exist_ok=True)

            print(f"[INFO] Обрабатываю тред {thread_num}: {thread_subject}")

            if thread_num not in cache[threads_key]:
                cache[threads_key][thread_num] = []

            existing_posts = set(cache[threads_key][thread_num])
            posts = get_thread_posts(thread_num)

            new_downloads = []
            for post in posts:
                post_num = str(post.get("no", ""))
                if not post_num or post_num in existing_posts:
                    continue

                print(f"[Новый пост] {thread_num}#{post_num}")
                downloaded = download_media(post, thread_dir)
                new_downloads.extend(downloaded)
                existing_posts.add(post_num)

            if new_downloads:
                print(f"[INFO] Загружено новых файлов: {len(new_downloads)}")
            else:
                print(f"[INFO] Новых файлов в треде {thread_num} нет.")

            # Сохраняем обновления для этого треда
            cache[threads_key][thread_num] = list(existing_posts)

        save_cache(cache)
        print(f"[INFO] Ожидание {UPDATE_INTERVAL // 60} минут...")
        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()