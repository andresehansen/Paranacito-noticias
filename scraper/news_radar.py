"""
news_radar.py — Radar de Descubrimiento de Noticias Locales
Fuentes: GDELT Project API + Google News RSS + Google Alerts
Filtrado estricto a las últimas 24 horas y relevancia 100% enfocada en Villa Paranacito.
"""
import re
import html
import time
import logging
from datetime import datetime
from urllib.parse import urlencode, quote_plus
import feedparser
import requests
from bs4 import BeautifulSoup
from config import (
    MAX_NEWS_AGE_HOURS,
    LOCAL_REQUIRED_TERMS,
    LOCAL_EXCLUDE_TERMS,
    DEFAULT_FALLBACK_IMAGE,
    DEFAULT_CATEGORY_IMAGES
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Términos de búsqueda estrictamente locales para Villa Paranacito
SEARCH_TERMS = [
    '"Villa Paranacito"',
    '"Paranacito"',
    '"Delta entrerriano"'
]

GDELT_MAX_RESULTS = 10

def clean_text(raw: str) -> str:
    """Limpia entidades HTML (&quot;, &#38;), etiquetas y sufijos de diarios."""
    if not raw:
        return ""
    # 1. Decodificar entidades HTML
    text = html.unescape(raw)
    # 2. Remover etiquetas HTML si existen
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator=" ")
    # 3. Remover sufijos de medios al final del título
    text = re.sub(
        r"\s*-\s*(Letra P|TN|Perfil|Clarín|Infobae|Diario El Día|R2820|El Entre Ríos|APFDigital|examedia\.com\.ar|Google News|Elonce|Uno Entre Ríos)\b.*$",
        "",
        text,
        flags=re.IGNORECASE
    )
    # 4. Limpiar elipsis iniciales / repetidas
    text = re.sub(r"^\s*(\.\.\.|\.\.|\-)\s*", "", text)
    # 5. Normalizar espacios
    return re.sub(r"\s+", " ", text).strip()

def is_locally_relevant(title: str, text: str = "") -> bool:
    """
    Verifica con criterio periodístico estricto que la noticia corresponda
    específicamente a Villa Paranacito o al Delta Entrerriano.
    """
    clean_t = clean_text(title)
    clean_b = clean_text(text)
    combined = f"{clean_t} {clean_b}".lower()

    # 1. Debe mencionar obligatoriamente Villa Paranacito o el Delta Entrerriano
    local_strong = ["villa paranacito", "paranacito", "rio paranacito", "río paranacito", "delta entrerriano", "arroyo sagastume"]
    if not any(term in combined for term in local_strong):
        return False

    # 2. Descartar falsos positivos de otras provincias o localidades sin relación
    exclusiones = [
        "puerto vilelas", "chaco", "vaca muerta", "neuquén", "neuquen", "corrientes",
        "la rioja", "chachos", "misiones", "formosa", "basavilbaso", "concordia", "paraná ciudad",
        "santa fe capital"
    ]
    if any(ex in combined for ex in exclusiones):
        if "villa paranacito" not in combined:
            return False

    return True

def extract_og_image(url: str) -> str:
    """Intenta extraer la foto real de la noticia desde el sitio original."""
    if not url or not url.startswith("http"):
        return ""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=3.5, allow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            og_img = (
                soup.find("meta", property="og:image") or
                soup.find("meta", attrs={"name": "twitter:image"}) or
                soup.find("meta", attrs={"property": "twitter:image"})
            )
            if og_img and og_img.get("content"):
                img_candidate = og_img["content"].strip()
                if img_candidate.startswith("http") and not img_candidate.endswith(".svg"):
                    return img_candidate
    except Exception:
        pass
    return ""

# ─────────────────────────────────────────────
# GDELT Project (API pública y gratuita)
# ─────────────────────────────────────────────
def fetch_gdelt(query: str, max_records: int = 10) -> list:
    """Consulta GDELT con filtro estricto de Villa Paranacito."""
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": max_records,
        "timespan": "24h",
        "sort": "DateDesc",
        "format": "json",
        "lang": "Spanish",
    }
    url = f"{base_url}?{urlencode(params)}"

    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code != 200:
            return []

        data = resp.json()
        articles = data.get("articles", [])
        results = []

        for art in articles:
            raw_title = art.get("title", "").strip()
            article_url = art.get("url", "").strip()
            seendate = art.get("seendate", "")

            if not raw_title or not article_url:
                continue

            title = clean_text(raw_title)

            # Filtro de relevancia estricta
            if not is_locally_relevant(title, article_url):
                continue

            pub_date = datetime.now().isoformat()
            try:
                if seendate:
                    dt = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ")
                    pub_date = dt.isoformat()
            except ValueError:
                pass

            social_img = art.get("socialimage", "").strip()
            if not social_img or not social_img.startswith("http"):
                social_img = extract_og_image(article_url) or DEFAULT_FALLBACK_IMAGE

            results.append({
                "raw_title": title,
                "raw_summary": title,
                "raw_content": title,
                "url": article_url,
                "source_name": f"GDELT / {art.get('domain', 'Medio regional')}",
                "published_date": pub_date,
                "image_url": social_img,
                "radar_source": "gdelt"
            })

        return results

    except Exception as e:
        logging.warning(f"Error consultando GDELT para '{query}': {e}")
        return []

def fetch_all_gdelt() -> list:
    """Ejecuta búsquedas de GDELT filtradas para Villa Paranacito."""
    all_results = []
    seen_urls = set()

    for term in SEARCH_TERMS[:2]:
        results = fetch_gdelt(term, max_records=GDELT_MAX_RESULTS)
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)
        time.sleep(0.5)

    return all_results

# ─────────────────────────────────────────────
# Google News RSS (Filtrado estricto a 24 horas y relevancia)
# ─────────────────────────────────────────────
def fetch_google_news_rss(query: str) -> list:
    """Google News con modificador when:24h y limpieza de entidades HTML."""
    query_24h = f"{query} when:24h"
    encoded = quote_plus(query_24h)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=es-419&gl=AR&ceid=AR:es-419"

    try:
        feed = feedparser.parse(url)
        results = []

        for entry in feed.entries:
            raw_title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            raw_summary = entry.get("summary", "")
            pub_date = entry.get("published", datetime.now().isoformat())

            if not raw_title or not link:
                continue

            title = clean_text(raw_title)
            summary = clean_text(raw_summary)

            # 1. Antigüedad máxima 24 horas
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub_epoch = time.mktime(entry.published_parsed)
                    age_hours = (time.time() - pub_epoch) / 3600.0
                    if age_hours > MAX_NEWS_AGE_HOURS:
                        continue
                except Exception:
                    pass

            # 2. Verificación de relevancia estricta para Villa Paranacito
            if not is_locally_relevant(title, summary):
                continue

            # 3. Extraer foto real o asignar imagen de fallback
            real_img = extract_og_image(link) or DEFAULT_FALLBACK_IMAGE

            results.append({
                "raw_title": title,
                "raw_summary": summary,
                "raw_content": f"{title}. {summary}",
                "url": link,
                "source_name": f"Google News ({entry.get('source', {}).get('title', 'Medio regional')})",
                "published_date": pub_date,
                "image_url": real_img,
                "radar_source": "google_news"
            })

        return results

    except Exception as e:
        logging.warning(f"Error consultando Google News para '{query}': {e}")
        return []

def fetch_all_google_news() -> list:
    """Búsquedas específicas en Google News con filtro de relevancia."""
    all_results = []
    seen_urls = set()

    for term in SEARCH_TERMS:
        results = fetch_google_news_rss(term)
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)
        time.sleep(0.3)

    return all_results

# ─────────────────────────────────────────────
# Función principal: Ejecutar Radar Local
# ─────────────────────────────────────────────
def run_radar() -> list:
    """Ejecuta el radar de descubrimiento local de Villa Paranacito."""
    logging.info("=== INICIANDO RADAR DE DESCUBRIMIENTO LOCAL ===")
    all_articles = []
    seen_urls = set()

    # 1. Google News RSS
    gn_articles = fetch_all_google_news()
    for art in gn_articles:
        if art["url"] not in seen_urls:
            seen_urls.add(art["url"])
            all_articles.append(art)

    # 2. GDELT Project
    gdelt_articles = fetch_all_gdelt()
    for art in gdelt_articles:
        if art["url"] not in seen_urls:
            seen_urls.add(art["url"])
            all_articles.append(art)

    logging.info(f"=== RADAR LOCAL COMPLETADO: {len(all_articles)} artículos filtrados y relevantes ===")
    return all_articles
