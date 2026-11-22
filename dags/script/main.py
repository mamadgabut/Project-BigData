import logging
import json
from bs4 import BeautifulSoup

import time
import requests
from pathlib import Path
import sys

# Menambahkan folder script ke sys.path untuk impor modular
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

try:
    from db_connection import get_existing_urls_from_db
except ImportError:
    def get_existing_urls_from_db():
        return set()

logger = logging.getLogger(__name__)

def main():
    index_urls = get_index()
    
    existing_urls = get_existing_urls_from_db()  

    new_urls = [url for url in index_urls if url not in existing_urls]
    
    print(f"Total link ditemukan: {len(index_urls)}, Link baru: {len(new_urls)}")
    
    if not new_urls:
        print("Tidak ada berita baru.")
        return

    articles = []
    for url in new_urls:
        try:
            page = get_page(url)
            articles.append(page)

        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                logger.warning(
                    "Artikel tidak ditemukan (404), dilewati: %s", url
                )
                continue

            raise

    if not articles:
        print("Tidak ada artikel baru yang berhasil diambil.")
        return

    output_path = Path(__file__).resolve().parent / "result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=4, ensure_ascii=False)
    
def get_index():
    base_url = "https://voi.id"
    max_page = 2
    
    links = []
    for i in range(max_page):
        url = f"{base_url}/artikel/indeks?channel=ALL&tanggal=&page={i}"
        soup = request(url)

        for link in soup.select("h3.section-item-title a"):
            links.append(link.get("href"))
            
    return links 

def get_page(url):
    soup = request(url)
    title_element = soup.select_one("h1.mx-0.my-1.px-0")

    breadcrumb = [
        item.get_text(strip=True)
        for item in soup.select("ol.breadcrumb li")
        if item.get_text(strip=True) != "Home"
    ]

    paragraph = [
        p.get_text(strip=True)
        for p in soup.select("div.full-post-body")
    ]

    tags = [
        {
            "href": tag.get("href"),   
            "text": tag.get_text(strip=True)
        }
        for tag in soup.select("div.post-tags-section a")
    ]

    redaksi = [
        {
            "href": redaksi.select_one("a").get("href"),
            "text": redaksi.select_one("a").get_text(strip=True),
            "bagian": redaksi.select_one("small").get_text(strip=True)
        }
        for redaksi in soup.select("ul.editor-team-list li")
    ]

    published_element = soup.select_one("div.col span")

    published_time = (
        published_element.get_text(strip=True)
        if published_element else None
    )
    temp = {
        "url": url,
        "title": title_element.get_text(strip=True) if title_element else None,
        "kategori": breadcrumb[-1] if breadcrumb else None,
        "published_time": published_time,
        "content": ". ".join(paragraph),
        "tim_redaksi": redaksi,
        "tags": tags
    }
    return temp
    
def request(url):
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/58.0.3029.110 Safari/537.3"
    )

    try:
        time.sleep(3)

        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )

        response.raise_for_status()

    except requests.RequestException as error:
        logger.warning("Gagal mengambil %s: %s", url, error)
        raise

    soup = BeautifulSoup(response.text, "html.parser")

    return soup   

run_scraper = main

if __name__ == '__main__':
    main()
