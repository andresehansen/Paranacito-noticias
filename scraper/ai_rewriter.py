"""
Motor de IA para parafraseo, contextualización local y clasificación periodística.
Utiliza Google Gemini API (Free Tier) con fallback automático.
"""
import re
import json
import logging
import unicodedata
import requests
from config import GEMINI_API_KEY, AI_SYSTEM_PROMPT, CATEGORIAS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def slugify(text: str) -> str:
    """Convierte texto en un slug URL limpio y fácil de tipear."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s-]", "", text).lower().strip()
    text = re.sub(r"[-\s]+", "-", text)
    # Limitar longitud para que la URL sea corta y amigable
    words = text.split("-")
    if len(words) > 7:
        text = "-".join(words[:7])
    return text

def calculate_reading_time(paragraphs: list) -> str:
    """Calcula el tiempo estimado de lectura en minutos."""
    total_words = sum(len(p.split()) for p in paragraphs)
    minutes = max(1, round(total_words / 180))
    return f"{minutes} min"

def rewrite_with_gemini(raw_title: str, raw_content: str, source_name: str) -> dict:
    """Envía el contenido crudo a Gemini para reescritura periodística."""
    if not GEMINI_API_KEY:
        logging.warning("GEMINI_API_KEY no configurada. Generando versión de respaldo adaptada.")
        return generate_fallback_rewrite(raw_title, raw_content, source_name)

    prompt_user = f"""
Fuente Original: {source_name}
Título Original: {raw_title}
Texto Crudo:
{raw_content}

Por favor reescribí esta noticia para los vecinos de Villa Paranacito y el Delta, devolviendo el JSON con la estructura solicitada.
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": AI_SYSTEM_PROMPT},
                    {"text": prompt_user}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json"
        }
    }

    # 1. Intentar con el SDK oficial (google-generativeai)
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Modelos disponibles en Google AI Studio
        for model_id in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
            try:
                model = genai.GenerativeModel(
                    model_id,
                    system_instruction=AI_SYSTEM_PROMPT,
                    generation_config={"temperature": 0.3, "response_mime_type": "application/json"}
                )
                import time
                time.sleep(1.0)
                resp = model.generate_content(prompt_user)
                if resp and resp.text:
                    candidate_clean = re.sub(r"^```json\s*", "", resp.text.strip())
                    candidate_clean = re.sub(r"\s*```$", "", candidate_clean.strip())
                    result_json = json.loads(candidate_clean)
                    
                    if "slug" not in result_json or not result_json["slug"]:
                        result_json["slug"] = slugify(result_json.get("titulo", raw_title))
                    else:
                        result_json["slug"] = slugify(result_json["slug"])
                        
                    if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
                        result_json["categoria"] = "Comunidad"
                        
                    if "cuerpo" not in result_json or not isinstance(result_json["cuerpo"], list):
                        result_json["cuerpo"] = [raw_content]
                        
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
        import time
        time.sleep(1.5)

        response = None
        last_error = None

        for endpoint_url in endpoints:
            try:
                resp = requests.post(endpoint_url, json=payload, timeout=20)
                if resp.status_code == 200:
                    response = resp
                    break
                else:
                    last_error = f"{resp.status_code}: {resp.text[:100]}"
            except Exception as e_req:
                last_error = str(e_req)

        if not response or response.status_code != 200:
            raise Exception(f"No se pudo conectar a los endpoints de Gemini ({last_error})")

        data = response.json()



        candidate = data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Limpieza de posibles bloques ```json si vinieran en el texto
        candidate_clean = re.sub(r"^```json\s*", "", candidate.strip())
        candidate_clean = re.sub(r"\s*```$", "", candidate_clean.strip())
        
        result_json = json.loads(candidate_clean)
        
        # Normalizaciones de seguridad
        if "slug" not in result_json or not result_json["slug"]:
            result_json["slug"] = slugify(result_json.get("titulo", raw_title))
        else:
            result_json["slug"] = slugify(result_json["slug"])
            
        if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
            result_json["categoria"] = "Comunidad"
            
        if "cuerpo" not in result_json or not isinstance(result_json["cuerpo"], list):
            result_json["cuerpo"] = [raw_content]
            
        result_json["tiempo_lectura"] = calculate_reading_time(result_json["cuerpo"])
        
        return result_json

    except Exception as e:
        logging.error(f"Error llamando a Gemini API: {e}. Aplicando reescritura de respaldo.")
        return generate_fallback_rewrite(raw_title, raw_content, source_name)

def generate_fallback_rewrite(raw_title: str, raw_content: str, source_name: str) -> dict:
    """Genera una estructura de noticia válida sin requerir API externa."""
    # Dividir texto en párrafos limpios
    paragraphs = [p.strip() for p in raw_content.split("\n") if len(p.strip()) > 30]
    if not paragraphs:
        paragraphs = [raw_content if raw_content else f"Información provista por {source_name}."]

    # Inferir categoría por palabras clave
    text_check = f"{raw_title} {raw_content}".lower()
    if any(w in text_check for w in ["rio", "río", "crecida", "altura", "lluvia", "clima", "temporal", "viento", "alerta"]):
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

    clean_title = raw_title.replace(" - Diario El Día", "").replace(" - R2820", "").strip()
    slug = slugify(clean_title)
    
    return {
        "titulo": clean_title,
        "copete": paragraphs[0][:180] + "..." if len(paragraphs[0]) > 180 else paragraphs[0],
        "cuerpo": paragraphs[:4],
        "categoria": cat,
        "tags": ["paranacito", "delta", cat.lower()],
        "slug": slug,
        "tiempo_lectura": calculate_reading_time(paragraphs),
        "resumen_whatsapp": f"📰 *{clean_title}* - Novedades de Villa Paranacito."
    }
