"""
Extractor de noticias desde Feeds RSS (Google Alerts, diarios regionales y portales).
"""
import re
import html
import logging
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup
from config import (
    RSS_SOURCES,
    MAX_NEWS_AGE_HOURS,
    LOCAL_REQUIRED_TERMS,
    LOCAL_EXCLUDE_TERMS,
    DEFAULT_FALLBACK_IMAGE
)
from news_radar import is_locally_relevant, extract_og_image, clean_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def extract_image_url(entry: dict, article_url: str = "") -> str:
    """Intenta extraer la mejor URL de imagen de la entrada RSS o de la web original."""
    # 1. Verificar media_content
    media_content = entry.get("media_content", [])
    if media_content and isinstance(media_content, list):
        for media in media_content:
            if "url" in media and any(ext in media["url"].lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return media["url"]
            
    # 2. Verificar enclosures
    enclosures = entry.get("enclosures", [])
    if enclosures and isinstance(enclosures, list):
        for enc in enclosures:
            if enc.get("type", "").startswith("image/") and "href" in enc:
                return enc["href"]
            
    # 3. Buscar etiquetas <img> dentro del contenido HTML o resumen
    html_content = ""
    if "content" in entry and entry["content"]:
        html_content = entry["content"][0].get("value", "")
    elif "summary" in entry:
        html_content = entry.get("summary", "")
        
    if html_content:
        soup = BeautifulSoup(html_content, "html.parser")
        img_tag = soup.find("img")
        if img_tag and img_tag.get("src"):
            src = img_tag["src"]
            if not src.startswith("data:") and "google.com/images" not in src:
                return src

    # 4. Extraer de la página web original si hay URL
    if article_url:
        real_img = extract_og_image(article_url)
        if real_img:
            return real_img

    # Imagen por defecto de alta calidad del Delta
    return DEFAULT_FALLBACK_IMAGE

def fetch_rss_feed(source: dict) -> list:
    """Descarga y parsea un feed RSS individual."""
    feed_url = source.get("url")
    if not feed_url or "0000000000" in feed_url:
        return []
        
    logging.info(f"Consultando feed: {source['nombre']}...")
    try:
        parsed = feedparser.parse(feed_url)
        items = []
        
        for entry in parsed.entries:
            raw_title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            raw_summary = entry.get("summary", "")

            if not raw_title or not link:
                continue

            title = clean_text(raw_title)
            
            # Contenido completo si está disponible
            content_val = ""
            if "content" in entry and entry["content"]:
                content_val = entry["content"][0].get("value", "")
            
            full_raw_text = clean_text(content_val if content_val else raw_summary)
            
            # Filtro estricto de relevancia para Villa Paranacito
            if not is_locally_relevant(title, full_raw_text):
                continue
                    
            # Verificar antigüedad máxima (24 horas)
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                import time as t_mod
                try:
                    pub_epoch = t_mod.mktime(entry.published_parsed)
                    age_hours = (t_mod.time() - pub_epoch) / 3600.0
                    if age_hours > MAX_NEWS_AGE_HOURS:
                        continue
                except Exception:
                    pass

            img_url = extract_image_url(entry, link)
            
            pub_date = entry.get("published", "")
            if not pub_date:
                pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            items.append({
                "raw_title": title,
                "raw_summary": full_raw_text[:200],
                "raw_content": full_raw_text or title,
                "url": link,
                "source_name": source.get("nombre", "Fuente Regional"),
                "published_date": pub_date,
                "image_url": img_url
            })
            
        logging.info(f"-> Encontradas {len(items)} noticias relevantes en {source['nombre']}")
        return items
        
    except Exception as e:
        logging.error(f"Error al procesar feed {source['nombre']}: {e}")
        return []

def fetch_all_sources() -> list:
    """Extrae noticias de todas las fuentes RSS configuradas."""
    all_articles = []
    for src in RSS_SOURCES:
        articles = fetch_rss_feed(src)
        all_articles.extend(articles)
    return all_articles
