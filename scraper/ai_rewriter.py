"""
ai_rewriter.py — Motor Editorial y Reescritor de Noticias con IA Avanzada
Modelos prioritarios: Google Gemini 2.5 Flash / Gemini 1.5 Pro / Gemini 2.0 Flash
"""
import re
import json
import html
import logging
import requests
from config import GEMINI_API_KEY, CATEGORIAS, DEFAULT_CATEGORY_IMAGES, DEFAULT_FALLBACK_IMAGE
from news_radar import clean_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

EDITORIAL_SYSTEM_PROMPT = """
Sos el editor de 'Paranacito Noticias', un feed informativo comunitario estilo red social para Villa Paranacito y el Delta de Entre Ríos (Argentina).

REGLA FUNDAMENTAL — ANCLAJE GEOGRÁFICO OBLIGATORIO:
⚠️ Cada post debe ser sobre Villa Paranacito, Ceibas, Islas del Ibicuy o una institución local concreta.
❌ PROHIBIDO escribir posts genéricos sobre el Delta en general, el Litoral, o eventos sin conexión directa con la localidad.
✅ El título DEBE mencionar Villa Paranacito, Ceibas, Islas del Ibicuy, o una institución local reconocida.

FORMATO DEL POST (feed social, NO artículo largo):
1. **Título** — Claro, concreto, periodístico. Máximo 12 palabras. Sin clickbait.
2. **Resumen** — EXACTAMENTE 2 o 3 oraciones cortas. Máximo 300 caracteres en total.
   - Solo hechos verificables presentes en el material crudo.
   - NUNCA inventar porcentajes, nombres, citas, cifras o datos que no estén en la fuente.
   - Responde: ¿Qué pasó? ¿Dónde? ¿A quién afecta?
3. **Resumen WhatsApp** — 1 oración con emoji, lista para compartir por WhatsApp.

FORMATO DE SALIDA — Devolvé ÚNICAMENTE este JSON:
{
  "titulo": "string",
  "resumen": "string (2-3 oraciones, máx 300 chars, solo hechos verificables)",
  "categoria": "string (una de: Río y Clima, Comunidad, Obras y Servicios, Deportes, Salud y Educación, Turismo y Cultura, Sociedad)",
  "tags": ["tag1", "tag2", "tag3"],
  "slug": "string-con-guiones-sin-acentos-max-8-palabras",
  "resumen_whatsapp": "string",
  "ancla_geografica": true
}
"""

def slugify(text: str) -> str:
    """Convierte un texto a slug URL amigable sin acentos ni caracteres especiales."""
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
    minutes = max(1, round(words / 170))
    return f"{minutes} min"

def rewrite_with_gemini(raw_title: str, raw_content: str, source_name: str) -> dict:
    """
    Procesa y enriquece la noticia utilizando los modelos más avanzados de Gemini.
    """
    clean_t = clean_text(raw_title)
    clean_c = clean_text(raw_content)

    if not GEMINI_API_KEY:
        logging.warning("GEMINI_API_KEY no configurada. Aplicando redacción periodística de respaldo.")
        return generate_fallback_rewrite(clean_t, clean_c, source_name)

    prompt_user = f"""
INFORMACIÓN CRUDA RECOLECTADA:
Titular original: {clean_t}
Medio o fuente: {source_name}

Contenido original completo:
{clean_c}

INSTRUCCIÓN:
Redactá una nota periodística completa, profunda, rica y atractiva para la comunidad de Villa Paranacito y el Delta Entrerriano siguiendo todas las pautas de estilo.
"""

    payload = {
        "contents": [{"parts": [{"text": prompt_user}]}],
        "systemInstruction": {"parts": [{"text": EDITORIAL_SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.25,
            "responseMimeType": "application/json"
        }
    }

    # Modelos en orden de potencia periodística
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]

    # 1. Intentar con el SDK oficial
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        
        for model_id in models_to_try:
            try:
                model = genai.GenerativeModel(
                    model_id,
                    system_instruction=EDITORIAL_SYSTEM_PROMPT,
                    generation_config={"temperature": 0.25, "response_mime_type": "application/json"}
                )
                resp = model.generate_content(prompt_user)
                if resp and resp.text:
                    candidate_clean = re.sub(r"^```json\s*", "", resp.text.strip())
                    candidate_clean = re.sub(r"\s*```$", "", candidate_clean.strip())
                    result_json = json.loads(candidate_clean)
                    
                    result_json["titulo"] = clean_text(result_json.get("titulo", clean_t))
                    
                    # Validar resumen (formato de feed social)
                    resumen = clean_text(result_json.get("resumen", ""))
                    if not resumen:
                        # Fallback: primeras 2 oraciones del contenido, máx 300 chars
                        oraciones = [s.strip() for s in clean_c.replace("\n", " ").split(". ") if len(s.strip()) > 20]
                        resumen = ". ".join(oraciones[:2])[:300]
                        if resumen and not resumen.endswith("."):
                            resumen += "."
                    result_json["resumen"] = resumen[:300]
                    
                    if "slug" not in result_json or not result_json["slug"]:
                        result_json["slug"] = slugify(result_json["titulo"])
                    else:
                        result_json["slug"] = slugify(result_json["slug"])
                        
                    if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
                        result_json["categoria"] = "Comunidad"
                        
                    logging.info(f"✨ Post generado exitosamente con {model_id}: '{result_json['titulo'][:50]}'")
                    return result_json
            except Exception as e_sdk:
                logging.debug(f"SDK model {model_id} error: {e_sdk}")
                continue
    except Exception as e_genai_pkg:
        logging.debug(f"SDK package error: {e_genai_pkg}")

    # 2. Intentar vía API REST directa
    for model_id in models_to_try:
        endpoint_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
        try:
            resp = requests.post(endpoint_url, json=payload, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                raw_text_resp = data["candidates"][0]["content"]["parts"][0]["text"]
                candidate_clean = re.sub(r"^```json\s*", "", raw_text_resp.strip())
                candidate_clean = re.sub(r"\s*```$", "", candidate_clean.strip())
                result_json = json.loads(candidate_clean)
                
                result_json["titulo"] = clean_text(result_json.get("titulo", clean_t))
                result_json["slug"] = slugify(result_json.get("slug", result_json["titulo"]))
                
                if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
                    result_json["categoria"] = "Comunidad"
                    
                resumen = clean_text(result_json.get("resumen", ""))
                if not resumen:
                    oraciones = [s.strip() for s in clean_c.replace("\n", " ").split(". ") if len(s.strip()) > 20]
                    resumen = ". ".join(oraciones[:2])[:300]
                    if resumen and not resumen.endswith("."):
                        resumen += "."
                result_json["resumen"] = resumen[:300]
                    
                logging.info(f"✨ Post generado vía REST con {model_id}")
                return result_json
        except Exception:
            continue

    logging.error("No se pudo conectar a los modelos de Gemini. Aplicando redacción de respaldo.")
    return generate_fallback_rewrite(clean_t, clean_c, source_name)


def generate_fallback_rewrite(raw_title: str, raw_content: str, source_name: str) -> dict:
    """Genera un post corto de feed social en modo de respaldo (sin IA)."""
    title = clean_text(raw_title)
    content = clean_text(raw_content)

    # Generar resumen corto: primeras 2 oraciones útiles del contenido, máx 300 chars
    oraciones = [s.strip() for s in content.replace("\n", " ").split(". ") if len(s.strip()) > 20]
    resumen = ". ".join(oraciones[:2])[:300]
    if resumen and not resumen.endswith("."):
        resumen += "."
    if not resumen:
        resumen = title

    # Inferir categoría
    text_check = f"{title} {content}".lower()
    if any(w in text_check for w in ["rio", "río", "crecida", "altura", "lluvia", "clima", "temporal", "nino", "niño", "hidro"]):
        cat = "Río y Clima"
    elif any(w in text_check for w in ["obra", "camino", "puente", "vialidad", "asfalto", "balsa", "electr"]):
        cat = "Obras y Servicios"
    elif any(w in text_check for w in ["futbol", "fútbol", "deporte", "club", "islenos", "isleños", "torneo"]):
        cat = "Deportes"
    elif any(w in text_check for w in ["salud", "hospital", "vacunacion", "escuela", "educacion", "medico"]):
        cat = "Salud y Educación"
    elif any(w in text_check for w in ["turismo", "pesca", "artesano", "fiesta", "cabana"]):
        cat = "Turismo y Cultura"
    else:
        cat = "Comunidad"

    return {
        "titulo": title,
        "resumen": resumen,
        "categoria": cat,
        "tags": ["villa paranacito", "delta", cat.lower()],
        "slug": slugify(title),
        "resumen_whatsapp": f"📰 *{title}* — {source_name}",
        "ancla_geografica": True,
    }
