"""
news_radar.py — Radar de Descubrimiento de Noticias
Fuentes: GDELT Project API + Google News RSS + Google Alerts
100% gratuitas, sin necesidad de API keys.
"""
import re
import time
import logging
from datetime import datetime
from urllib.parse import urlencode
import feedparser
import requests
from bs4 import BeautifulSoup
from config import GEO_CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Términos de búsqueda para Villa Paranacito y su zona de influencia
SEARCH_TERMS = [
    '"Villa Paranacito"',
    '"Paranacito"',
    '"Islas del Ibicuy"',
    '"Ibicuy"',
    '"Delta entrerriano" Paranacito',
]

GDELT_MAX_RESULTS = 20

def clean_html(raw: str) -> str:
    """Limpia HTML dejando texto legible."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()

# ─────────────────────────────────────────────
# GDELT Project (API pública y gratuita)
# Documentación: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
# ─────────────────────────────────────────────
def fetch_gdelt(query: str, max_records: int = 10) -> list:
    """
    Consulta el API v2 del GDELT Project para descubrir artículos que mencionan
    el término de búsqueda. 100% gratuito, sin key, sin límite de llamadas.
    """
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": max_records,
        "sort": "DateDesc",
        "format": "json",
        "lang": "Spanish",
    }
    url = f"{base_url}?{urlencode(params)}"

    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            logging.warning(f"GDELT retornó código {resp.status_code} para '{query}'")
            return []

        data = resp.json()
        articles = data.get("articles", [])
        results = []

        for art in articles:
            title = art.get("title", "").strip()
            article_url = art.get("url", "").strip()
            seendate = art.get("seendate", "")  # Formato: "20260821T141500Z"

            if not title or not article_url:
                continue

            # Parsear fecha de GDELT al formato ISO
            pub_date = datetime.now().isoformat()
            try:
                if seendate:
                    dt = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ")
                    pub_date = dt.isoformat()
            except ValueError:
                pass

            results.append({
                "raw_title": title,
                "raw_summary": art.get("seendate", ""),
                "raw_content": title,  # GDELT no devuelve cuerpo completo
                "url": article_url,
                "source_name": f"GDELT / {art.get('domain', 'Medio desconocido')}",
                "published_date": pub_date,
                "image_url": art.get("socialimage", "/images/default-paranacito.jpg"),
                "radar_source": "gdelt"
            })

        logging.info(f"GDELT '{query}': {len(results)} resultados")
        return results

    except Exception as e:
        logging.warning(f"Error consultando GDELT para '{query}': {e}")
        return []

def fetch_all_gdelt() -> list:
    """Ejecuta todas las búsquedas de GDELT para los términos de Villa Paranacito."""
    all_results = []
    seen_urls = set()

    for term in SEARCH_TERMS[:3]:  # Limitamos para no sobrecargar
        results = fetch_gdelt(term, max_records=GDELT_MAX_RESULTS)
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)
        time.sleep(0.5)  # Pausa cortés entre llamadas

    return all_results

# ─────────────────────────────────────────────
# Google News RSS (sin API key)
# ─────────────────────────────────────────────
def fetch_google_news_rss(query: str) -> list:
    """
    Google News expone un feed RSS público por consulta de búsqueda.
    No requiere API key y es completamente gratuito.
    URL base: https://news.google.com/rss/search?q=TERMINO&hl=es-419&gl=AR&ceid=AR:es
    """
    from urllib.parse import quote_plus
    encoded = quote_plus(query)
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

            results.append({
                "raw_title": title,
                "raw_summary": summary,
                "raw_content": f"{title}. {summary}",
                "url": link,
                "source_name": f"Google News ({entry.get('source', {}).get('title', 'Medio regional')})",
                "published_date": pub_date,
                "image_url": "/images/default-paranacito.jpg",
                "radar_source": "google_news"
            })

        logging.info(f"Google News '{query}': {len(results)} resultados")
        return results

    except Exception as e:
        logging.warning(f"Error consultando Google News para '{query}': {e}")
        return []

def fetch_all_google_news() -> list:
    """Ejecuta búsquedas en Google News para todos los términos configurados."""
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
# Función principal: Ejecutar todo el Radar
# ─────────────────────────────────────────────
def run_radar() -> list:
    """
    Ejecuta todos los radares de descubrimiento en secuencia.
    Retorna lista unificada de artículos sin duplicados por URL.
    """
    logging.info("=== INICIANDO RADAR DE DESCUBRIMIENTO ===")
    all_articles = []
    seen_urls = set()

    # Google News RSS (el más actualizado)
    gn_articles = fetch_all_google_news()
    for art in gn_articles:
        if art["url"] not in seen_urls:
            seen_urls.add(art["url"])
            all_articles.append(art)
    logging.info(f"Google News: {len(gn_articles)} artículos descubiertos")

    # GDELT Project (cobertura global en español)
    gdelt_articles = fetch_all_gdelt()
    for art in gdelt_articles:
        if art["url"] not in seen_urls:
            seen_urls.add(art["url"])
            all_articles.append(art)
    logging.info(f"GDELT: {len(gdelt_articles)} artículos descubiertos")

    logging.info(f"=== RADAR COMPLETADO: {len(all_articles)} artículos únicos descubiertos ===")
    return all_articles


if __name__ == "__main__":
    articles = run_radar()
    for art in articles[:5]:
        print(f"[{art['radar_source'].upper()}] {art['raw_title']} — {art['url'][:60]}...")
