"""
article_extractor.py — Extractor de Contenido Completo de Artículos Periodísticos
Descarga la página web original de la noticia, resuelve redirecciones de Google News,
y extrae el cuerpo completo (500-2000 palabras) y la foto original en alta resolución.
"""
import re
import html
import logging
from urllib.parse import urlparse, parse_qs, unquote
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

def resolve_real_url(url: str) -> str:
    """Si la URL proviene de Google News RSS o agregadores, resuelve la URL final de destino."""
    if not url:
        return ""
    if "news.google.com" in url:
        try:
            resp = requests.head(url, headers=HEADERS, timeout=5, allow_redirects=True)
            if resp.url and "news.google.com" not in resp.url:
                return resp.url
        except Exception:
            pass
    return url

def extract_full_article(url: str) -> dict:
    """
    Descarga la página web de la noticia y extrae:
    - title: Título limpio
    - full_text: Texto completo de todos los párrafos de la noticia
    - image_url: Foto principal original en alta resolución
    - source_name: Nombre del diario o medio
    """
    real_url = resolve_real_url(url)
    result = {
        "url": real_url,
        "title": "",
        "full_text": "",
        "paragraphs": [],
        "image_url": "",
        "source_name": ""
    }

    if not real_url or not real_url.startswith("http"):
        return result

    try:
        domain = urlparse(real_url).netloc.replace("www.", "")
        result["source_name"] = domain

        resp = requests.get(real_url, headers=HEADERS, timeout=8, allow_redirects=True)
        if resp.status_code != 200:
            return result

        # Decodificar correctamente según encoding
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Extraer título
        h1 = soup.find("h1")
        if h1:
            result["title"] = html.unescape(h1.get_text(separator=" ").strip())
        else:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                result["title"] = html.unescape(og_title["content"].strip())

        # 2. Extraer imagen principal de alta resolución
        og_img = (
            soup.find("meta", property="og:image") or
            soup.find("meta", attrs={"name": "twitter:image"}) or
            soup.find("meta", attrs={"property": "twitter:image"})
        )
        if og_img and og_img.get("content"):
            img_src = og_img["content"].strip()
            if img_src.startswith("http") and not img_src.endswith(".svg"):
                result["image_url"] = img_src

        # 3. Remover elementos basura antes de extraer párrafos
        for tag in soup([
            "script", "style", "nav", "footer", "header", "aside", "form",
            "noscript", "iframe", "button"
        ]):
            tag.extract()

        # Buscar contenedores principales de artículos comunes en medios argentinos
        main_container = (
            soup.find("article") or
            soup.find("div", class_=re.compile(r"(cuerpo|cuerpo-nota|nota-cuerpo|entry-content|post-content|article-body|article__body|news-body|story-body)", re.I)) or
            soup.find("main") or
            soup.body
        )

        paragraphs = []
        if main_container:
            for p in main_container.find_all("p"):
                p_text = html.unescape(p.get_text(separator=" ").strip())
                # Filtrar párrafos vacíos, avisos de cookies o créditos repetidos
                if len(p_text) >= 40 and not any(junk in p_text.lower() for junk in [
                    "compartir en facebook", "leé también", "te puede interesar",
                    "suscribite", "todos los derechos reservados", "newsletter",
                    "hacé clic aquí", "seguinos en"
                ]):
                    paragraphs.append(p_text)

        result["paragraphs"] = paragraphs
        result["full_text"] = "\n\n".join(paragraphs)

        logging.info(f"Extraído contenido completo de '{domain}': {len(paragraphs)} párrafos ({len(result['full_text'])} caracteres)")
        return result

    except Exception as e:
        logging.warning(f"No se pudo extraer contenido completo de {real_url}: {e}")
        return result
