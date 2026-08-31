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
Sos el editor de 'Paranacito Noticias', el portal y feed informativo comunitario de Villa Paranacito y el Delta de Entre Ríos (Argentina).

Tu misión es transformar el material periodístico crudo en NOTAS CON PROFUNDIDAD, RIGOR Y ALTA CALIDAD INFORMATIVA para los vecinos de la región.

REGLA FUNDAMENTAL — ANCLAJE GEOGRÁFICO OBLIGATORIO:
⚠️ Cada noticia debe ser sobre Villa Paranacito, Ceibas, Islas del Ibicuy o una institución local concreta (Hospital, Bomberos, Prefectura, Escuelas, Club Isleños, Municipio).
❌ PROHIBIDO escribir sobre sucesos ajenos sin impacto local (ej. hechos policiales en GBA o noticias nacionales genéricas).
✅ El título y el copete DEBEN mencionar Villa Paranacito, Ceibas, Islas del Ibicuy, o una institución local reconocida.

ESTRUCTURA DE LA NOTICIA:
1. **Título** — Riguroso, potente, periodístico. Debe mencionar el lugar o institución.
2. **Copete / Bajada** — 1 a 2 oraciones que sintetizan el hecho principal.
3. **Cuerpo Extenso (3 a 5 párrafos sustanciosos)**:
   - Párrafo 1: El hecho, contexto y ubicación geográfica precisa en el Delta.
   - Párrafo 2: Declaraciones oficiales, datos de fuentes o protagonistas (solo datos reales).
   - Párrafo 3: Impacto directo para la vida cotidiana de los isleños (servicios, salud, transporte fluvial, caminos, producción).
   - Párrafo 4+: Medidas tomadas, recomendaciones prácticas, cronogramas o canales de contacto.
4. **Resumen Breve** — 2 a 3 oraciones claras (hasta 350 caracteres) para lectura rápida.
5. **Resumen WhatsApp** — 1 línea concisa con emojis informativos.

FORMATO DE SALIDA — Devolvé ÚNICAMENTE este JSON:
{
  "titulo": "string",
  "copete": "string",
  "cuerpo": ["Párrafo 1 con desarrollo...", "Párrafo 2...", "Párrafo 3...", "Párrafo 4..."],
  "resumen": "string (2-3 oraciones claras)",
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
                    result_json["copete"] = clean_text(result_json.get("copete", clean_t))
                    
                    # Validar cuerpo (lista de párrafos bien estructurados)
                    raw_cuerpo = result_json.get("cuerpo", [])
                    if isinstance(raw_cuerpo, list) and len(raw_cuerpo) > 0:
                        result_json["cuerpo"] = [clean_text(p) for p in raw_cuerpo if len(clean_text(p)) > 20]
                    elif isinstance(raw_cuerpo, str) and len(raw_cuerpo) > 30:
                        result_json["cuerpo"] = [clean_text(p) for p in raw_cuerpo.split("\n\n") if len(clean_text(p)) > 20]
                    else:
                        result_json["cuerpo"] = [clean_text(p) for p in clean_c.split("\n\n") if len(clean_text(p)) > 20]
                    
                    # Validar resumen
                    resumen = clean_text(result_json.get("resumen", ""))
                    if not resumen:
                        resumen = result_json["copete"] or (result_json["cuerpo"][0] if result_json["cuerpo"] else clean_t)
                    result_json["resumen"] = resumen[:350]
                    
                    if "slug" not in result_json or not result_json["slug"]:
                        result_json["slug"] = slugify(result_json["titulo"])
                    else:
                        result_json["slug"] = slugify(result_json["slug"])
                        
                    if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
                        result_json["categoria"] = "Comunidad"
                        
                    logging.info(f"✨ Noticia enriquecida exitosamente con {model_id}: '{result_json['titulo'][:50]}'")
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
                
                raw_cuerpo = result_json.get("cuerpo", [])
                if isinstance(raw_cuerpo, list) and len(raw_cuerpo) > 0:
                    result_json["cuerpo"] = [clean_text(p) for p in raw_cuerpo if len(clean_text(p)) > 20]
                else:
                    result_json["cuerpo"] = [clean_text(p) for p in clean_c.split("\n\n") if len(clean_text(p)) > 20]

                resumen = clean_text(result_json.get("resumen", ""))
                if not resumen:
                    resumen = result_json["copete"] or (result_json["cuerpo"][0] if result_json["cuerpo"] else clean_t)
                result_json["resumen"] = resumen[:350]
                
                if "categoria" not in result_json or result_json["categoria"] not in CATEGORIAS:
                    result_json["categoria"] = "Comunidad"
                    
                logging.info(f"✨ Noticia enriquecida vía REST con {model_id}")
                return result_json
        except Exception:
            continue

    logging.error("No se pudo conectar a los modelos de Gemini. Aplicando redacción de respaldo.")
    return generate_fallback_rewrite(clean_t, clean_c, source_name)


def generate_fallback_rewrite(raw_title: str, raw_content: str, source_name: str) -> dict:
    """Genera una noticia completa con desarrollo y resumen en modo de respaldo (sin IA)."""
    title = clean_text(raw_title)
    content = clean_text(raw_content)

    paragraphs = [clean_text(p) for p in content.split("\n\n") if len(clean_text(p)) > 30]
    if not paragraphs:
        paragraphs = [clean_text(p) for p in content.split(". ") if len(clean_text(p)) > 30]

    if len(paragraphs) < 2:
        paragraphs = [
            f"En el marco del seguimiento informativo de Villa Paranacito y el Delta de Entre Ríos, se dieron a conocer detalles sobre {title}.",
            f"La situación involucra la articulación entre organismos provinciales, el municipio y las instituciones comunitarias del departamento Islas.",
            f"Para más detalles sobre este acontecimiento, la cobertura continúa en desarrollo a través de las fuentes informativas oficiales de {source_name}."
        ]

    copete = paragraphs[0] if len(paragraphs[0]) <= 250 else paragraphs[0][:240] + "..."
    resumen = copete

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
    elif any(w in text_check for w in ["justicia", "polic", "deten", "fiscal"]):
        cat = "Sociedad"
    else:
        cat = "Comunidad"

    return {
        "titulo": title,
        "copete": copete,
        "cuerpo": paragraphs,
        "resumen": resumen,
        "categoria": cat,
        "tags": ["villa paranacito", "delta", cat.lower()],
        "slug": slugify(title),
        "resumen_whatsapp": f"📰 *{title}* — {source_name}",
        "ancla_geografica": True,
    }

