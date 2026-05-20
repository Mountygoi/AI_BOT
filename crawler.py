import asyncio
import os
import chromadb
from crawl4ai import AsyncWebCrawler
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="./db")

# Пересоздаем коллекцию, чтобы стереть старые выдумки
try:
    client.delete_collection("centr_krasok")
except Exception:
    pass

collection = client.create_collection("centr_krasok")
visited = set()

# Расширенный список разделов строго по вашей шапке сайта (со скриншота)
important_urls = [
    "https://centr-krasok.kz/",
    "https://centr-krasok.kz/catalog/",
    "https://centr-krasok.kz/brands/",
    "https://centr-krasok.kz/aktsii/",
    "https://centr-krasok.kz/help/",
    "https://centr-krasok.kz/about/",
    "https://centr-krasok.kz/about/delivery/",  # Теперь доставка тут!
    "https://centr-krasok.kz/about/contacts/",
    "https://centr-krasok.kz/partners/",
    "https://centr-krasok.kz/articles/",
]

async def crawl_page(crawler, url):
    if url in visited or len(visited) > 150:
        return
    if "centr-krasok.kz" not in url:
        return

    # Исключаем корзины, личные кабинеты и медиа-файлы
    blocked = ["javascript", "void(0)", "#", ".jpg", ".png", ".webp", ".svg", "?", "basket", "account", "personal"]
    if any(x in url for x in blocked):
        return

    # Разрешаем обход только ключевых информационных веток
    allowed = ["/catalog/", "/brands/", "/about/", "/partners/", "/help/", "/aktsii/", "/articles/"]
    if url != "https://centr-krasok.kz/" and not any(x in url for x in allowed):
        return

    visited.add(url)
    print(f"Сканирую раздел: {url}")

    try:
        result = await crawler.arun(url=url, word_count_threshold=10)
        if not result or not result.markdown:
            return

        text = result.markdown.raw_markdown
        if not text:
            return

        # Умный чанкинг по логическим абзацам
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""
        
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if len(current_chunk) + len(p) < 700:
                current_chunk += "\n" + p
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = p
        if current_chunk:
            chunks.append(current_chunk.strip())

        for i, chunk in enumerate(chunks):
            embedding = model.encode(chunk).tolist()
            collection.add(
                documents=[chunk],
                embeddings=[embedding],
                metadatas=[{"url": url}],
                ids=[f"{url}_{i}"]
            )

        # Рекурсивный поиск вложенных страниц только внутри этих же разделов
        links = result.links.get("internal", [])
        for link in links:
            href = link.get("href")
            if href:
                if href.startswith("/"):
                    href = f"https://centr-krasok.kz{href}"
                await crawl_page(crawler, href)

    except Exception as e:
        print(f"Ошибка сканирования {url}: {e}")

async def main():
    async with AsyncWebCrawler() as crawler:
        for url in important_urls:
            await crawl_page(crawler, url)
    print(f"\n Наполнение базы завершено! Успешно обработано информационных страниц: {len(visited)}")

if __name__ == "__main__":
    asyncio.run(main())