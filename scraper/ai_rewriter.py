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
Sos el Jefe de Redacción y Editor Senior de 'Paranacito Noticias', el principal portal informativo digital de Villa Paranacito y el Delta de Entre Ríos (Argentina).

Tu objetivo es transformar el material crudo o cables periodísticos en NOTAS COMPLETAS, RICAS EN CONTENIDO, PROFUNDAS Y DE ALTA CALIDAD PERIODÍSTICA.

REGLAS EDITORIALES OBLIGATORIAS:
1. **Titular Periodístico (H1)**:
   - Debe ser claro, riguroso, potente y profesional.
   - Prohibido el sensacionalismo o 'clickbait'.

2. **Copete / Bajada (1 a 2 oraciones)**:
   - Resumen ejecutivo que responde: ¿Qué pasó? ¿Quiénes intervienen? ¿Dónde y por qué es importante para la comunidad?

3. **Cuerpo Extenso y Enriquecido (4 a 6 párrafos sustanciosos)**:
   - **Párrafo 1 (El Hecho y Contexto)**: Desarrollo detallado de la noticia con ubicación geográfica precisa (Villa Paranacito, Río Paranacito, arroyos, departamento Islas del Ibicuy o provincia de Entre Ríos).
   - **Párrafo 2 (Declaraciones y Voces Oficiales)**: Citas textuales o conceptos expresados por funcionarios, autoridades, vecinos, especialistas o instituciones involucradas.
   - **Párrafo 3 (Impacto Práctico para los Vecinos)**: Qué significa esta novedad para la vida cotidiana de la comunidad isleña (navegación, estado de caminos, salud, defensas costeras, comercio, educación o turismo).
   - **Párrafo 4 (Datos Técnicos / Medidas Concretas)**: Cifras, presupuesto, maquinarias, hidrómetros, pronósticos hidrológicos o cronograma de trabajos.
   - **Párrafo 5 (Recomendaciones y Próximos Pasos)**: Información útil de servicio, canales de contacto, números de guardia o cómo continúa la situación.

4. **Resumen para WhatsApp**:
   - Mensaje periodístico conciso (2 a 3 líneas) con emojis informativos (📰, 🌊, 🚜, etc.) y llamado a la acción.

5. **Categoría Exacta**:
   - Elegir estrictamente una de: ["Río y Clima", "Comunidad", "Obras y Servicios", "Deportes", "Salud y Educación", "Turismo y Cultura", "Sociedad"].

FORMATO DE SALIDA:
Devolvé ÚNICAMENTE un objeto JSON con este esquema exacto:
{
  "titulo": "string",
  "copete": "string",
  "cuerpo": ["Párrafo 1...", "Párrafo 2...", "Párrafo 3...", "Párrafo 4...", "Párrafo 5..."],
  "categoria": "string",
  "tags": ["tag1", "tag2", "tag3", "tag4"],
  "slug": "string-con-guiones-sin-acentos",
  "tiempo_lectura": "string (ej: '3 min')",
  "resumen_whatsapp": "string"
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
                    result_json["copete"] = clean_text(result_json.get("copete", clean_t))
                    
                    if "slug" not in result_json or not result_json["slug"]:
                        result_json["slug"] = slugify(result_json["titulo"])
                    else:
                        result_json["slug"] = slugify(result_json["slug"])
                        
                    if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
                        result_json["categoria"] = "Comunidad"
                        
                    if "cuerpo" not in result_json or not isinstance(result_json["cuerpo"], list) or len(result_json["cuerpo"]) < 2:
                        result_json["cuerpo"] = [clean_text(p) for p in clean_c.split("\n\n") if len(clean_text(p)) > 30]
                    else:
                        result_json["cuerpo"] = [clean_text(p) for p in result_json["cuerpo"] if clean_text(p)]
                        
                    result_json["tiempo_lectura"] = calculate_reading_time(result_json["cuerpo"])
                    logging.info(f"✨ Noticia enriquecida exitosamente con {model_id} ({len(result_json['cuerpo'])} párrafos)")
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
                result_json["copete"] = clean_text(result_json.get("copete", clean_t))
                result_json["slug"] = slugify(result_json.get("slug", result_json["titulo"]))
                
                if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
                    result_json["categoria"] = "Comunidad"
                    
                if "cuerpo" in result_json and isinstance(result_json["cuerpo"], list):
                    result_json["cuerpo"] = [clean_text(p) for p in result_json["cuerpo"] if clean_text(p)]
                else:
                    result_json["cuerpo"] = [clean_c]
                    
                result_json["tiempo_lectura"] = calculate_reading_time(result_json["cuerpo"])
                logging.info(f"✨ Noticia enriquecida vía REST con {model_id}")
                return result_json
        except Exception:
            continue

    logging.error("No se pudo conectar a los modelos de Gemini. Aplicando redacción periodística de respaldo.")
    return generate_fallback_rewrite(clean_t, clean_c, source_name)

def generate_fallback_rewrite(raw_title: str, raw_content: str, source_name: str) -> dict:
    """Genera una estructura periodística completa y detallada en modo de respaldo."""
    title = clean_text(raw_title)
    content = clean_text(raw_content)

    paragraphs = [clean_text(p) for p in content.split("\n\n") if len(clean_text(p)) > 35]
    if not paragraphs:
        paragraphs = [clean_text(p) for p in content.split(". ") if len(clean_text(p)) > 35]

    if len(paragraphs) < 3:
        paragraphs = [
            f"En el marco del seguimiento de las novedades de interés para la región, se dieron a conocer informaciones relevantes sobre {title}.",
            f"La situación involucra la articulación entre organismos provinciales, el municipio de Villa Paranacito y los sectores productivos y comunitarios del departamento Islas.",
            f"Desde las áreas técnicas y de servicios locales remarcaron la importancia de mantener informada a la población respecto a los avances y medidas operativas que se implementen.",
            f"Para más detalles sobre este acontecimiento, la cobertura continúa en desarrollo a través de los canales informativos oficiales de {source_name}."
        ]

    # Inferir categoría
    text_check = f"{title} {content}".lower()
    if any(w in text_check for w in ["rio", "río", "crecida", "altura", "lluvia", "clima", "temporal", "viento", "alerta", "nino", "niño", "hidro"]):
        cat = "Río y Clima"
    elif any(w in text_check for w in ["obra", "camino", "puente", "vialidad", "luz", "servicio", "asfalto", "balsa", "electr"]):
        cat = "Obras y Servicios"
    elif any(w in text_check for w in ["futbol", "fútbol", "deporte", "club", "islenos", "isleños", "torneo", "liga"]):
        cat = "Deportes"
    elif any(w in text_check for w in ["salud", "hospital", "vacunacion", "escuela", "educacion", "colegio", "medico"]):
        cat = "Salud y Educación"
    elif any(w in text_check for w in ["turismo", "pesca", "delta", "artesano", "fiesta", "cabana"]):
        cat = "Turismo y Cultura"
    else:
        cat = "Comunidad"

    slug = slugify(title)
    copete = paragraphs[0] if len(paragraphs[0]) <= 220 else paragraphs[0][:210] + "..."

    return {
        "titulo": title,
        "copete": copete,
        "cuerpo": paragraphs,
        "categoria": cat,
        "tags": ["villa paranacito", "delta", "entre rios", cat.lower()],
        "slug": slug,
        "tiempo_lectura": calculate_reading_time(paragraphs),
        "resumen_whatsapp": f"📰 *{title}* - Leé todas las novedades de Villa Paranacito y el Delta."
    }
