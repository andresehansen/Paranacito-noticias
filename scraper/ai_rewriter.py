"""
ai_rewriter.py — Reescritor de Noticias y Adaptación Comunitaria con IA
Modelo: Google Gemini 2.0 Flash / 1.5 Flash (Free Tier)
"""
import re
import json
import html
import logging
import requests
from config import GEMINI_API_KEY, AI_SYSTEM_PROMPT, CATEGORIAS
from news_radar import clean_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def slugify(text: str) -> str:
    """Convierte un texto a formato slug URL amigable."""
    text = clean_text(text).lower()
    text = re.sub(r"[áäàâ]", "a", text)
    text = re.sub(r"[éëèê]", "e", text)
    text = re.sub(r"[íïìî]", "i", text)
    text = re.sub(r"[óöòô]", "o", text)
    text = re.sub(r"[úüùû]", "u", text)
    text = re.sub(r"ñ", "n", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    parts = text.split("-")
    return "-".join(parts[:8])

def calculate_reading_time(paragraphs: list) -> str:
    """Calcula el tiempo estimado de lectura en minutos."""
    full_text = " ".join(paragraphs) if isinstance(paragraphs, list) else str(paragraphs)
    words = len(full_text.split())
    minutes = max(1, round(words / 180))
    return f"{minutes} min"

def rewrite_with_gemini(raw_title: str, raw_content: str, source_name: str) -> dict:
    """
    Toma una noticia cruda y la procesa con Gemini para adaptarla al público de Villa Paranacito.
    """
    clean_t = clean_text(raw_title)
    clean_c = clean_text(raw_content)

    if not GEMINI_API_KEY:
        logging.warning("GEMINI_API_KEY no configurada. Aplicando reescritura de respaldo.")
        return generate_fallback_rewrite(clean_t, clean_c, source_name)

    prompt_user = f"""
NOTICIA CRUDA:
Título: {clean_t}
Fuente original: {source_name}
Contenido:
{clean_c}

Instrucciones:
Adaptá esta noticia para el portal comunitario de Villa Paranacito (Delta de Entre Ríos).
Devolvé ÚNICAMENTE un objeto JSON válido con la estructura solicitada (titulo, copete, cuerpo, categoria, tags, slug, tiempo_lectura, resumen_whatsapp).
"""

    payload = {
        "contents": [{"parts": [{"text": prompt_user}]}],
        "systemInstruction": {"parts": [{"text": AI_SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    # 1. Intentar con el SDK oficial (google-generativeai)
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        
        for model_id in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
            try:
                model = genai.GenerativeModel(
                    model_id,
                    system_instruction=AI_SYSTEM_PROMPT,
                    generation_config={"temperature": 0.2, "response_mime_type": "application/json"}
                )
                resp = model.generate_content(prompt_user)
                if resp and resp.text:
                    candidate_clean = re.sub(r"^```json\s*", "", resp.text.strip())
                    candidate_clean = re.sub(r"\s*```$", "", candidate_clean.strip())
                    result_json = json.loads(candidate_clean)
                    
                    result_json["titulo"] = clean_text(result_json.get("titulo", clean_t))
                    result_json["copete"] = clean_text(result_json.get("copete", clean_t))
                    
                    if "slug" not in result_json or not result_json["slug"]:
                        result_json["slug"] = slugify(result_json["titulo"])
                    else:
                        result_json["slug"] = slugify(result_json["slug"])
                        
                    if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
                        result_json["categoria"] = "Comunidad"
                        
                    if "cuerpo" not in result_json or not isinstance(result_json["cuerpo"], list):
                        result_json["cuerpo"] = [clean_c]
                    else:
                        result_json["cuerpo"] = [clean_text(p) for p in result_json["cuerpo"] if clean_text(p)]
                        
                    result_json["tiempo_lectura"] = calculate_reading_time(result_json["cuerpo"])
                    logging.info(f"Noticia procesada con éxito usando {model_id}")
                    return result_json
            except Exception as e_sdk:
                logging.debug(f"SDK model {model_id} error: {e_sdk}")
                continue
    except Exception as e_genai_pkg:
        logging.debug(f"No se pudo usar google.generativeai package: {e_genai_pkg}")

    # 2. Fallback con REST API directa
    endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}",
    ]

    try:
        response = None
        for endpoint_url in endpoints:
            try:
                resp = requests.post(endpoint_url, json=payload, timeout=20)
                if resp.status_code == 200:
                    response = resp
                    break
            except Exception:
                pass

        if not response:
            raise Exception("No se pudo conectar a los endpoints de Gemini")

        data = response.json()
        raw_text_resp = data["candidates"][0]["content"]["parts"][0]["text"]
        candidate_clean = re.sub(r"^```json\s*", "", raw_text_resp.strip())
        candidate_clean = re.sub(r"\s*```$", "", candidate_clean.strip())
        
        result_json = json.loads(candidate_clean)
        result_json["titulo"] = clean_text(result_json.get("titulo", clean_t))
        result_json["copete"] = clean_text(result_json.get("copete", clean_t))
        
        if "slug" not in result_json or not result_json["slug"]:
            result_json["slug"] = slugify(result_json["titulo"])
        else:
            result_json["slug"] = slugify(result_json["slug"])
            
        if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
            result_json["categoria"] = "Comunidad"
            
        if "cuerpo" not in result_json or not isinstance(result_json["cuerpo"], list):
            result_json["cuerpo"] = [clean_c]
        else:
            result_json["cuerpo"] = [clean_text(p) for p in result_json["cuerpo"] if clean_text(p)]
            
        result_json["tiempo_lectura"] = calculate_reading_time(result_json["cuerpo"])
        return result_json

    except Exception as e:
        logging.error(f"Error llamando a Gemini API: {e}. Aplicando reescritura de respaldo limpia.")
        return generate_fallback_rewrite(clean_t, clean_c, source_name)

def generate_fallback_rewrite(raw_title: str, raw_content: str, source_name: str) -> dict:
    """Genera una estructura periodística limpia y profesional sin API externa."""
    title = clean_text(raw_title)
    content = clean_text(raw_content)

    # Dividir texto en párrafos limpios
    paragraphs = [clean_text(p) for p in content.split("\n") if len(clean_text(p)) > 30]
    if not paragraphs:
        paragraphs = [
            f"Las autoridades y medios regionales informaron sobre las novedades vinculadas a {title}.",
            f"El seguimiento de la información se realiza en articulación con los organismos locales de Villa Paranacito.",
            f"Información suministrada por {source_name}."
        ]

    # Inferir categoría
    text_check = f"{title} {content}".lower()
    if any(w in text_check for w in ["rio", "río", "crecida", "altura", "lluvia", "clima", "temporal", "viento", "alerta", "nino", "niño"]):
        cat = "Río y Clima"
    elif any(w in text_check for w in ["futbol", "fútbol", "deporte", "club", "islenos", "isleños", "torneo", "liga"]):
        cat = "Deportes"
    elif any(w in text_check for w in ["obra", "camino", "puente", "vialidad", "luz", "servicio", "asfalto", "balsa"]):
        cat = "Obras y Servicios"
    elif any(w in text_check for w in ["salud", "hospital", "vacunacion", "escuela", "educacion", "colegio"]):
        cat = "Salud y Educación"
    elif any(w in text_check for w in ["turismo", "pesca", "delta", "artesano", "fiesta"]):
        cat = "Turismo y Cultura"
    else:
        cat = "Comunidad"

    slug = slugify(title)
    copete = paragraphs[0] if len(paragraphs[0]) <= 180 else paragraphs[0][:175] + "..."

    return {
        "titulo": title,
        "copete": copete,
        "cuerpo": paragraphs[:4],
        "categoria": cat,
        "tags": ["villa paranacito", "delta", cat.lower()],
        "slug": slug,
        "tiempo_lectura": calculate_reading_time(paragraphs),
        "resumen_whatsapp": f"📰 *{title}* - Novedades de Villa Paranacito."
    }
