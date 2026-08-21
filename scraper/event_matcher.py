"""
event_matcher.py — Motor de Detección de Acontecimient@os y Novedad
Implementa el principio: "Un acontecimiento = Una noticia viva"

Flujo:
1. Recibe un artículo nuevo.
2. Lo compara contra los acontecimient@os de las últimas 72 horas.
3. Determina si es: NUEVO / ACTUALIZACIÓN / REDUNDANTE.
4. Calcula % de novedad usando Gemini API o comparación semántica simple.
"""
import re
import json
import logging
import requests
from difflib import SequenceMatcher
from config import GEMINI_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ─── Umbrales de novedad ────────────────────────────────────
# < 15%  → REDUNDANTE (descartar, solo registrar fuente consultada)
# 15-45% → EVALUAR (información parcialmente nueva, actualizar si supera análisis IA)
# > 45%  → NUEVO / ACTUALIZACIÓN clara
THRESHOLD_REDUNDANT = 15
THRESHOLD_UPDATE = 45

# Entidades que son "huellas" de acontecimient@os de Paranacito
LOCAL_ENTITIES = [
    "paranacito", "ibicuy", "prefectura", "municipalidad", "municipio",
    "policía", "bomberos", "hospital", "escuela", "ruta 46", "ruta 12",
    "arroyo", "río paranacito", "delta", "isleños", "isla", "lancha",
    "cancha", "club", "balsa", "puente", "ruta provincial"
]

def normalize_text(text: str) -> str:
    """Normaliza texto para comparación."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s]", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_key_entities(text: str) -> set:
    """Extrae entidades clave locales mencionadas en el texto."""
    norm = normalize_text(text)
    found = set()
    for entity in LOCAL_ENTITIES:
        if entity in norm:
            found.add(entity)
    # Extraer números que pueden ser significativos (cantidades, fechas, horarios)
    numbers = set(re.findall(r'\b\d+(?:[.,]\d+)?\b', norm))
    found.update(numbers)
    return found

def similarity_ratio(text_a: str, text_b: str) -> float:
    """Calcula similitud entre dos textos (0.0 a 1.0)."""
    norm_a = normalize_text(text_a)
    norm_b = normalize_text(text_b)
    return SequenceMatcher(None, norm_a, norm_b).ratio()

def entity_overlap_score(text_new: str, text_existing: str) -> float:
    """
    Calcula el solapamiento de entidades locales entre dos textos.
    Un alto solapamiento indica que hablan del mismo acontecimiento.
    """
    entities_new = extract_key_entities(text_new)
    entities_existing = extract_key_entities(text_existing)
    if not entities_new or not entities_existing:
        return 0.0
    intersection = entities_new & entities_existing
    union = entities_new | entities_existing
    return len(intersection) / len(union) if union else 0.0

def check_same_event_with_gemini(text_new: str, text_existing: str, titulo_new: str, titulo_existing: str) -> dict:
    """
    Usa Gemini API para determinar:
    - ¿Hablan del mismo acontecimiento?
    - ¿Qué % de información nueva aporta el nuevo texto?
    - Resumen de la información nueva si la hay.
    """
    if not GEMINI_API_KEY:
        # Fallback sin IA: solo similitud textual
        ratio = similarity_ratio(text_new, text_existing)
        novelty = max(0, 100 - int(ratio * 100))
        return {
            "mismo_acontecimiento": ratio > 0.35,
            "porcentaje_novedad": novelty,
            "informacion_nueva": "" if novelty < THRESHOLD_REDUNDANT else text_new[:200],
            "razon": "Análisis por similitud textual (sin API de IA)"
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""Sos un editor periodístico del portal Paranacito Noticias (Villa Paranacito, Argentina).

Recibiste un artículo nuevo y debés compararlo con una noticia ya publicada para decidir si:
A) Es el MISMO acontecimiento (puede ser actualización o redundante)
B) Es un acontecimiento DIFERENTE

**NOTICIA EXISTENTE:**
Título: {titulo_existing}
Contenido: {text_existing[:600]}

**ARTÍCULO NUEVO:**
Título: {titulo_new}
Contenido: {text_new[:600]}

Respondé EXCLUSIVAMENTE con este JSON (sin bloques ```):
{{
  "mismo_acontecimiento": true/false,
  "porcentaje_novedad": 0-100,
  "informacion_nueva": "resumen breve de los datos nuevos si los hay, o cadena vacía",
  "razon": "explicación corta de tu decisión"
}}

El porcentaje_novedad indica qué tan nueva es la información del artículo recibido respecto a la noticia existente:
- 0-14%: completamente redundante
- 15-44%: algo nuevo pero menor
- 45-100%: información claramente nueva o acontecimiento diferente"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    ]

    try:
        resp = None
        for ep in endpoints:
            try:
                r = requests.post(ep, json=payload, timeout=15)
                if r.status_code == 200:
                    resp = r
                    break
            except Exception:
                pass

        if not resp or resp.status_code != 200:
            raise Exception("Ningún endpoint de Gemini respondió 200")

        data = resp.json()
        text_resp = data["candidates"][0]["content"]["parts"][0]["text"]
        text_clean = re.sub(r"^```json\s*", "", text_resp.strip())
        text_clean = re.sub(r"\s*```$", "", text_clean.strip())
        return json.loads(text_clean)


    except Exception as e:
        logging.warning(f"Error en análisis Gemini: {e}. Usando similitud textual.")
        ratio = similarity_ratio(text_new, text_existing)
        novelty = max(0, 100 - int(ratio * 100))
        return {
            "mismo_acontecimiento": ratio > 0.40,
            "porcentaje_novedad": novelty,
            "informacion_nueva": "" if novelty < THRESHOLD_REDUNDANT else text_new[:200],
            "razon": "Fallback: similitud textual"
        }

def match_article_to_events(raw_article: dict, recent_events: list) -> dict:
    """
    Función principal del motor de acontecimient@os.
    
    Recibe:
    - raw_article: artículo nuevo extraído de las fuentes.
    - recent_events: lista de acontecimient@os de las últimas 72 horas.
    
    Retorna un dict con:
    - action: "NEW" | "UPDATE" | "DISCARD"
    - matched_event: el acontecimiento coincidente (o None si es NEW)
    - novelty_pct: porcentaje de novedad calculado
    - new_info_summary: resumen del dato nuevo (si aplica)
    """
    title_new = raw_article.get("raw_title", "")
    content_new = raw_article.get("raw_content", raw_article.get("raw_summary", ""))
    combined_new = f"{title_new} {content_new}"

    best_match = None
    best_entity_score = 0.0

    # 1. Pre-filtro rápido por solapamiento de entidades (sin IA, muy veloz)
    for event in recent_events:
        title_existing = event.get("titulo", "")
        cuerpo_existing = " ".join(event.get("cuerpo", []))
        combined_existing = f"{title_existing} {cuerpo_existing}"

        entity_score = entity_overlap_score(combined_new, combined_existing)
        text_score = similarity_ratio(combined_new[:400], combined_existing[:400])

        # Combinamos entity overlap y similitud textual
        combined_score = (entity_score * 0.6) + (text_score * 0.4)

        if combined_score > best_entity_score:
            best_entity_score = combined_score
            best_match = event

    logging.debug(f"Mejor coincidencia pre-filtro: {best_entity_score:.2f} — {best_match.get('titulo','')[:60] if best_match else 'ninguno'}")

    # Si el solapamiento es muy bajo, es un acontecimiento nuevo sin duda
    if best_entity_score < 0.20 or best_match is None:
        return {
            "action": "NEW",
            "matched_event": None,
            "novelty_pct": 100,
            "new_info_summary": ""
        }

    # 2. Análisis profundo con IA para los casos ambiguos (score 0.20 - 0.80)
    title_existing = best_match.get("titulo", "")
    cuerpo_existing = " ".join(best_match.get("cuerpo", []))

    analysis = check_same_event_with_gemini(
        text_new=content_new,
        text_existing=cuerpo_existing,
        titulo_new=title_new,
        titulo_existing=title_existing
    )

    mismo = analysis.get("mismo_acontecimiento", False)
    novedad = analysis.get("porcentaje_novedad", 0)
    info_nueva = analysis.get("informacion_nueva", "")

    if not mismo:
        return {"action": "NEW", "matched_event": None, "novelty_pct": 100, "new_info_summary": ""}

    if novedad < THRESHOLD_REDUNDANT:
        logging.info(f"Redundante ({novedad}%): '{title_new[:50]}'")
        return {"action": "DISCARD", "matched_event": best_match, "novelty_pct": novedad, "new_info_summary": ""}

    if novedad >= THRESHOLD_UPDATE:
        logging.info(f"Actualización ({novedad}%): '{title_new[:50]}' → '{title_existing[:50]}'")
        return {"action": "UPDATE", "matched_event": best_match, "novelty_pct": novedad, "new_info_summary": info_nueva}

    # Zona gris: información parcial
    if novedad >= THRESHOLD_REDUNDANT:
        return {"action": "UPDATE", "matched_event": best_match, "novelty_pct": novedad, "new_info_summary": info_nueva}

    return {"action": "DISCARD", "matched_event": best_match, "novelty_pct": novedad, "new_info_summary": ""}
