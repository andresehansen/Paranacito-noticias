"""
Configuración general para el Ingestor de Noticias de Villa Paranacito.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

# Directorios de datos
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
NOTICIAS_DIR = DATA_DIR / "noticias"
CLIMA_FILE = DATA_DIR / "clima_actual.json"
HISTORY_FILE = DATA_DIR / "processed_history.json"

# Asegurar existencia de directorios
DATA_DIR.mkdir(parents=True, exist_ok=True)
NOTICIAS_DIR.mkdir(parents=True, exist_ok=True)

# Claves de API (obtenidas de variables de entorno)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Antigüedad máxima permitida para procesar una noticia (en horas)
MAX_NEWS_AGE_HOURS = 24

# Configuración Geográfica de Villa Paranacito
GEO_CONFIG = {
    "nombre": "Villa Paranacito",
    "departamento": "Islas del Ibicuy",
    "provincia": "Entre Ríos",
    "pais": "Argentina",
    "lat": -33.7144,
    "lon": -58.6575,
    "timezone": "America/Argentina/Buenos_Aires",
}

# Categorías oficiales del portal
CATEGORIAS = [
    "Comunidad",
    "Río y Clima",
    "Deportes",
    "Obras y Servicios",
    "Sociedad",
    "Turismo y Cultura",
    "Salud y Educación"
]

# Imágenes temáticas de alta calidad para el Delta de Entre Ríos
DEFAULT_CATEGORY_IMAGES = {
    "Río y Clima": "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=1200&q=80",
    "Comunidad": "https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=1200&q=80",
    "Obras y Servicios": "https://images.unsplash.com/photo-1541888946425-d0fbb18086f6?auto=format&fit=crop&w=1200&q=80",
    "Deportes": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1200&q=80",
    "Salud y Educación": "https://images.unsplash.com/photo-1580582932707-520aed937b7b?auto=format&fit=crop&w=1200&q=80",
    "Turismo y Cultura": "https://images.unsplash.com/photo-1498654896293-37aacf113fd9?auto=format&fit=crop&w=1200&q=80",
    "Sociedad": "https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=1200&q=80"
}
DEFAULT_FALLBACK_IMAGE = "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=1200&q=80"


# Filtros geográficos estrictos para evitar falsos positivos
LOCAL_REQUIRED_TERMS = [
    "villa paranacito", "paranacito", "islas del ibicuy", "río paranacito", "rio paranacito",
    "delta entrerriano", "arroyo sagastume", "brazo largo", "ceibas", "villa ceibas",
    "departamento islas", "gualeguaychu", "ibicuy", "pueblo brugo", "médano a médano"
]

LOCAL_EXCLUDE_TERMS = [
    "puerto vilelas", "chaco", "vaca muerta", "neuquén", "neuquen", "corrientes",
    "misiones", "formosa", "salta", "jujuy", "san juan", "mendoza", "bahía blanca",
    "bahia blanca", "tucumán", "tucuman", "santiago del estero", "la pampa"
]

# Fuentes RSS de Noticias Regionales y Búsquedas
RSS_SOURCES = [
    {
        "nombre": "Ceibas Noticias",
        "tipo": "local",
        "url": "https://ceibasnoticias.com.ar/feed/",
        "keywords": ["paranacito", "villa paranacito", "islas del ibicuy", "ceibas", "delta"]
    },
    {
        "nombre": "Google Alerts - Villa Paranacito",
        "tipo": "google_alerts",
        "url": os.getenv(
            "RSS_GOOGLE_ALERTS_PARANACITO",
            "https://www.google.com/alerts/feeds/00000000000000000000/00000000000000000000"
        ),
        "keywords": ["paranacito", "villa paranacito", "islas del ibicuy", "delta entrerriano"]
    },
    {
        "nombre": "Diario El Día (Gualeguaychú)",
        "tipo": "regional",
        "url": "https://www.eldiaonline.com/rss",
        "keywords": ["paranacito", "villa paranacito", "islas del ibicuy"]
    },
    {
        "nombre": "R2820 Radio y Noticias",
        "tipo": "regional",
        "url": "https://r2820.com/rss",
        "keywords": ["paranacito", "villa paranacito", "islas del ibicuy"]
    },
    {
        "nombre": "El Entre Ríos",
        "tipo": "provincial",
        "url": "https://www.elentrerios.com/rss",
        "keywords": ["paranacito", "villa paranacito", "islas del ibicuy"]
    },
    {
        "nombre": "APFDigital",
        "tipo": "provincial",
        "url": "https://www.apfdigital.com.ar/rss.php",
        "keywords": ["paranacito", "villa paranacito", "islas del ibicuy"]
    }
]



# Prompt del sistema para el LLM (Gemini)
AI_SYSTEM_PROMPT = """
Sos el redactor jefe del portal oficial de noticias comunitarias de Villa Paranacito (Entre Ríos, Argentina), en pleno corazón del Delta.
Tu misión es procesar y reescribir noticias crudas para adaptarlas al público local con las siguientes reglas estrictas:

1. **Tono y Estilo**:
   - Periodístico, claro, respetuoso, neutral y cercano a la comunidad isleña.
   - Si la noticia menciona arroyos, ríos, caminos (como Ruta 46/12), escuelas o instituciones locales, preservá con absoluta precisión esos nombres propios.

2. **Estructura Requerida**:
   - Generá un título atractivo y claro.
   - Generá un copete o bajada de 1 a 2 oraciones.
   - Desarrollá el cuerpo en 3 a 5 párrafos bien redactados en Markdown.
   - Creá un resumen ultra-corto de 1 oración ideal para reenviar por WhatsApp con emoticonos informativos.
   - Clasificá la noticia en una de las siguientes categorías exactas:
     ["Comunidad", "Río y Clima", "Deportes", "Obras y Servicios", "Sociedad", "Turismo y Cultura", "Salud y Educación"]
   - Asigná 3 a 5 tags representativos (en minúsculas, sin '#').
   - Generá un slug URL amigable y sin acentos ni caracteres especiales (ej: "avanzan-obras-camino-acceso").

3. **Formato de Salida**:
   - Devolvé EXCLUSIVAMENTE un objeto JSON válido (sin etiquetas ```json adicionales si no son necesarias).

Esquema JSON:
{
  "titulo": "string",
  "copete": "string",
  "cuerpo": ["párrafo 1...", "párrafo 2...", "párrafo 3..."],
  "categoria": "string",
  "tags": ["tag1", "tag2", "tag3"],
  "slug": "string",
  "tiempo_lectura": "string (ej: '2 min')",
  "resumen_whatsapp": "string"
}
"""
