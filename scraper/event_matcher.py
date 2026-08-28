"""
event_matcher.py — Motor de Detección de Acontecimientos y Deduplicación Semántica
Evita duplicación de noticias del mismo hecho mediante solapamiento de palabras clave,
entidades propias (nombres, instituciones, temas) y análisis con IA.
"""
import re
import json
import logging
import unicodedata
import requests
from difflib import SequenceMatcher
from config import GEMINI_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

STOPWORDS = {
    "de", "la", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para", "con",
    "no", "una", "su", "al", "lo", "como", "mas", "pero", "sus", "le", "ya", "o", "fue",
    "este", "ha", "si", "porque", "esta", "son", "entre", "esta", "cuando", "muy", "sin",
    "sobre", "ser", "tiene", "tambien", "me", "hasta", "hay", "donde", "quien", "desde",
    "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra", "otros", "ese", "eso",
    "ante", "ellos", "e", "esto", "mi", "antes", "algunos", "que", "villa", "paranacito",
    "delta", "entrerriano", "entre", "rios", "noticias", "departamento", "islas", "ibicuy"
}

def normalize_text(text: str) -> str:
    """Normaliza texto removiendo acentos, puntuación y caracteres especiales."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()

def extract_significant_keywords(text: str) -> set:
    """Extrae palabras clave significativas (nombres, verbos, sustantivos) excluyendo stopwords."""
    norm = normalize_text(text)
    words = [w for w in norm.split() if len(w) >= 4 and w not in STOPWORDS]
    return set(words)

def keyword_overlap_score(text_a: str, text_b: str) -> float:
    """
    Calcula el solapamiento de palabras clave significativas (Jaccard / Asymmetric Recall).
    Mide qué porcentaje de las palabras clave del texto más corto están presentes en el más largo.
    """
    kw_a = extract_significant_keywords(text_a)
    kw_b = extract_significant_keywords(text_b)
    if not kw_a or not kw_b:
        return 0.0

    intersection = kw_a & kw_b
    # Recall relativo al conjunto más pequeño (para comparar titulares cortos contra notas largas)
    min_len = min(len(kw_a), len(kw_b))
    return len(intersection) / min_len if min_len > 0 else 0.0

def check_same_event_with_gemini(text_new: str, text_existing: str, titulo_new: str, titulo_existing: str) -> dict:
    """
    Usa Gemini API para determinar si dos coberturas pertenecen al mismo hecho.
    """
    kw_overlap = keyword_overlap_score(f"{titulo_new} {text_new}", f"{titulo_existing} {text_existing}")

    # Si el solapamiento de palabras clave esenciales es muy alto (>50%), es sin duda el mismo hecho
    if kw_overlap >= 0.50:
        return {
            "mismo_acontecimiento": True,
            "porcentaje_novedad": 10,
            "informacion_nueva": "",
            "razon": f"Alto solapamiento de entidades clave ({int(kw_overlap*100)}%)"
        }

    if not GEMINI_API_KEY:
        return {
            "mismo_acontecimiento": kw_overlap >= 0.35,
            "porcentaje_novedad": max(0, 100 - int(kw_overlap * 100)),
            "informacion_nueva": "",
            "razon": "Análisis por palabras clave"
        }

    prompt = f"""Sos un editor del portal Paranacito Noticias.
Compará estos dos textos y determiná si corresponden al MISMO acontecimiento o hecho noticioso (incluso si tienen distinto enfoque o medio).

NOTICIA YA PUBLICADA:
Título: {titulo_existing}
Contenido: {text_existing[:600]}

NUEVO CABLE/ARTÍCULO:
Título: {titulo_new}
Contenido: {text_new[:600]}

Respondé ÚNICAMENTE con este JSON:
{{
  "mismo_acontecimiento": true/false,
  "porcentaje_novedad": 0-100,
  "informacion_nueva": "resumen de datos nuevos o vacío"
}}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
    ]

    for ep in endpoints:
        try:
            r = requests.post(ep, json=payload, timeout=10)
            if r.status_code == 200:
                data = r.json()
                text_resp = data["candidates"][0]["content"]["parts"][0]["text"]
                clean_json = re.sub(r"^```json\s*", "", text_resp.strip()).rstrip("`").strip()
                return json.loads(clean_json)
        except Exception:
            pass

    return {
        "mismo_acontecimiento": kw_overlap >= 0.35,
        "porcentaje_novedad": max(0, 100 - int(kw_overlap * 100)),
        "informacion_nueva": "",
        "razon": "Fallback: análisis de palabras clave"
    }

def match_article_to_events(raw_article: dict, recent_events: list) -> dict:
    """
    Determina si un artículo entrante es NUEVO, ACTUALIZACIÓN de un evento existente o REDUNDANTE.
    """
    title_new = raw_article.get("raw_title", "")
    content_new = raw_article.get("raw_content", raw_article.get("raw_summary", ""))
    combined_new = f"{title_new} {content_new}"

    best_match = None
    best_score = 0.0

    # 1. Comparar contra todos los eventos recientes
    for event in recent_events:
        title_existing = event.get("titulo", "")
        cuerpo_existing = " ".join(event.get("cuerpo", [])) if isinstance(event.get("cuerpo"), list) else str(event.get("cuerpo", ""))
        combined_existing = f"{title_existing} {cuerpo_existing}"

        score = keyword_overlap_score(combined_new, combined_existing)
        if score > best_score:
            best_score = score
            best_match = event

    logging.info(f"Deduplicación: Mejor coincidencia ({int(best_score*100)}%): '{title_new[:45]}' vs '{best_match.get('titulo','')[:45] if best_match else 'ninguno'}'")

    # Si no hay coincidencia temática significativa (<25%), es una noticia NUEVA
    if best_score < 0.25 or best_match is None:
        return {
            "action": "NEW",
            "matched_event": None,
            "novelty_pct": 100,
            "new_info_summary": ""
        }

    # Si hay coincidencia muy alta (>45%), es el mismo acontecimiento
    if best_score >= 0.45:
        return {
            "action": "DISCARD" if best_score > 0.70 else "UPDATE",
            "matched_event": best_match,
            "novelty_pct": 15,
            "new_info_summary": title_new
        }

    # 2. Para casos intermedios (score 0.25 a 0.45), consultar a Gemini
    analysis = check_same_event_with_gemini(
        text_new=content_new,
        text_existing=" ".join(best_match.get("cuerpo", [])),
        titulo_new=title_new,
        titulo_existing=best_match.get("titulo", "")
    )

    if analysis.get("mismo_acontecimiento", False):
        novedad = analysis.get("porcentaje_novedad", 0)
        if novedad < 20:
            return {"action": "DISCARD", "matched_event": best_match, "novelty_pct": novedad, "new_info_summary": ""}
        else:
            return {"action": "UPDATE", "matched_event": best_match, "novelty_pct": novedad, "new_info_summary": analysis.get("informacion_nueva", "")}

    return {"action": "NEW", "matched_event": None, "novelty_pct": 100, "new_info_summary": ""}
