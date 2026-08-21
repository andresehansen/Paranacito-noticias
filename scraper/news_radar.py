"""
news_radar.py — Radar de Descubrimiento de Noticias Locales
Fuentes: GDELT Project API + Google News RSS + Google Alerts
Filtrado estricto a las últimas 24 horas y relevancia 100% enfocada en Villa Paranacito.
"""
import re
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

# Términos de búsqueda hiper-específicos para evitar falsos positivos
SEARCH_TERMS = [
    '"Villa Paranacito"',
    '"Paranacito"',
    '"Islas del Ibicuy"',
    '"Delta entrerriano"',
    '"Río Paranacito"'
]


GDELT_MAX_RESULTS = 15

def clean_html(raw: str) -> str:
    """Limpia HTML dejando texto legible."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()

def is_locally_relevant(title: str, text: str = "") -> bool:
    """
    Verifica con criterio periodístico estricto que la noticia corresponda
    a Villa Paranacito, el departamento Islas del Ibicuy o el Delta Entrerriano.
    """
    combined = f"{title} {text}".lower()

    # 1. Comprobar si menciona términos obligatorios locales
    has_local_term = any(term in combined for term in LOCAL_REQUIRED_TERMS)
    if not has_local_term:
        return False

    # 2. Descartar falsos positivos de otras provincias/localidades
    has_exclude_term = any(term in combined for term in LOCAL_EXCLUDE_TERMS)
    if has_exclude_term:
        # Solo admitir si menciona explícitamente Villa Paranacito o Islas de Entre Ríos
        if "villa paranacito" not in combined and "islas del ibicuy" not in combined:
            return False

    return True

def extract_og_image(url: str) -> str:
    """
    Intenta extraer la foto real de la noticia desde el sitio original (OpenGraph o Twitter card).
    """
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
    """
    Consulta el API v2 del GDELT Project con filtro temporal y de relevancia local.
    """
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
            logging.warning(f"GDELT retornó código {resp.status_code} para '{query}'")
            return []

        data = resp.json()
        articles = data.get("articles", [])
        results = []

        for art in articles:
            title = art.get("title", "").strip()
            article_url = art.get("url", "").strip()
            seendate = art.get("seendate", "")

            if not title or not article_url:
                continue

            # Filtro de relevancia local estricto
            if not is_locally_relevant(title, article_url):
                continue

            pub_date = datetime.now().isoformat()
            try:
                if seendate:
                    dt = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ")
                    pub_date = dt.isoformat()
            except ValueError:
                pass

            # Intentar obtener imagen de GDELT o extraer og:image
            social_img = art.get("socialimage", "").strip()
            if not social_img or not social_img.startswith("http"):
                social_img = extract_og_image(article_url) or DEFAULT_FALLBACK_IMAGE

            results.append({
                "raw_title": title,
                "raw_summary": art.get("seendate", ""),
                "raw_content": title,
                "url": article_url,
                "source_name": f"GDELT / {art.get('domain', 'Medio regional')}",
                "published_date": pub_date,
                "image_url": social_img,
                "radar_source": "gdelt"
            })

        logging.info(f"GDELT '{query}' (últimas 24h locales): {len(results)} resultados")
        return results

    except Exception as e:
        logging.warning(f"Error consultando GDELT para '{query}': {e}")
        return []

def fetch_all_gdelt() -> list:
    """Ejecuta búsquedas de GDELT filtradas para Villa Paranacito."""
    all_results = []
    seen_urls = set()

    for term in SEARCH_TERMS[:2]:  # Solo términos más específicos
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
    """
    Google News con modificador when:24h y verificación de relevancia local.
    """
    query_24h = f"{query} when:24h"
    encoded = quote_plus(query_24h)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=es-419&gl=AR&ceid=AR:es-419"

    try:
        feed = feedparser.parse(url)
        results = []

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = clean_html(entry.get("summary", ""))
            pub_date = entry.get("published", datetime.now().isoformat())

            if not title or not link:
                continue

            # 1. Antigüedad máxima 24 horas
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub_epoch = time.mktime(entry.published_parsed)
                    age_hours = (time.time() - pub_epoch) / 3600.0
                    if age_hours > MAX_NEWS_AGE_HOURS:
                        continue
                except Exception:
                    pass

            # 2. Verificación de relevancia para Villa Paranacito
            if not is_locally_relevant(title, summary):
                continue

            # 3. Intentar extraer foto real del artículo
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

        logging.info(f"Google News '{query}' (relevantes 24h): {len(results)} resultados")
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
    """
    Ejecuta el radar de descubrimiento y retorna solo noticias
    genuinamente relevantes para Villa Paranacito de las últimas 24 horas.
    """
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
