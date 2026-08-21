"""
Extractor de noticias desde Feeds RSS (Google Alerts, diarios regionales y portales).
"""
import re
import logging
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup
from config import RSS_SOURCES

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def clean_html(raw_html: str) -> str:
    """Limpia etiquetas HTML y entidades para obtener texto plano legible."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    # Eliminar scripts y estilos
    for s in soup(["script", "style", "nav", "footer", "header"]):
        s.extract()
    text = soup.get_text(separator=" ")
    # Normalizar espacios
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_image_url(entry: dict) -> str:
    """Intenta extraer la mejor URL de imagen de la entrada RSS."""
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
            if not src.startswith("data:") and not "google.com/images" in src:
                return src
                
    # Imagen por defecto representativa del Delta / Paranacito
    return "/images/default-paranacito.jpg"

def is_relevant(text: str, keywords: list) -> bool:
    """Determina si el contenido hace referencia a Villa Paranacito o zonas aledañas."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)

def fetch_rss_feed(source: dict) -> list:
    """Descarga y parsea un feed RSS individual."""
    feed_url = source.get("url")
    if not feed_url or "0000000000" in feed_url:
        logging.debug(f"Fuente {source['nombre']} no configurada o plantilla sin URL real. Omitiendo.")
        return []
        
    logging.info(f"Consultando feed: {source['nombre']}...")
    try:
        parsed = feedparser.parse(feed_url)
        items = []
        
        for entry in parsed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "")
            
            # Contenido completo si está disponible
            content_val = ""
            if "content" in entry and entry["content"]:
                content_val = entry["content"][0].get("value", "")
            
            full_raw_text = clean_html(content_val if content_val else summary)
            
            # Filtro de relevancia si la fuente no es exclusiva de Google Alerts
            if source.get("tipo") != "google_alerts":
                combined_check = f"{title} {full_raw_text}"
                if not is_relevant(combined_check, source.get("keywords", ["paranacito"])):
                    continue
                    
            img_url = extract_image_url(entry)
            
            # Fecha de publicación
            pub_date = entry.get("published", "")
            if not pub_date:
                pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            items.append({
                "raw_title": title,
                "raw_summary": clean_html(summary),
                "raw_content": full_raw_text or clean_html(summary),
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
