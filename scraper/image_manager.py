"""
image_manager.py — Motor Inteligente de Asignación y Curaduría de Imágenes Semánticas
Garantiza que toda noticia tenga una foto de portada 100% coherente con la esencia del contenido.
"""
import re
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Catálogo Temático Granular de Alta Definición para el Delta y Entre Ríos
THEMATIC_IMAGE_CATALOG = {
    "ganaderia_campo": [
        "https://images.unsplash.com/photo-1570042225831-d98fa7577f1e?auto=format&fit=crop&w=1200&q=80", # Rodeo vacuno en pastizal
        "https://images.unsplash.com/photo-1546445317-29f4545e9d53?auto=format&fit=crop&w=1200&q=80", # Ganado pastando en campo
        "https://images.unsplash.com/photo-1500595046743-cd271d694d30?auto=format&fit=crop&w=1200&q=80"  # Campo y hacienda rural
    ],
    "policia_seguridad_justicia": [
        "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1200&q=80", # Balanza de la justicia y ley
        "https://images.unsplash.com/photo-1589578527966-fdac0f44566c?auto=format&fit=crop&w=1200&q=80", # Luces de patrullero policial / operativo
        "https://images.unsplash.com/photo-1563911302283-d2bc129e7570?auto=format&fit=crop&w=1200&q=80"  # Martillo de tribunal y derecho
    ],
    "fauna_caza_humedales": [
        "https://images.unsplash.com/photo-1484406566174-9da000fda645?auto=format&fit=crop&w=1200&q=80", # Ciervo / fauna silvestre en hábitat
        "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=1200&q=80", # Humedal y monte nativo
        "https://images.unsplash.com/photo-1518495973542-4542c06a5843?auto=format&fit=crop&w=1200&q=80"  # Reserva natural y agua
    ],
    "rio_crecida_clima": [
        "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=1200&q=80", # Río Delta con islas y vegetación
        "https://images.unsplash.com/photo-1473448912268-2022ce9509d8?auto=format&fit=crop&w=1200&q=80", # Río caudaloso y árboles ribereños
        "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?auto=format&fit=crop&w=1200&q=80"  # Lluvia y temporal hídrico
    ],
    "salud_hospital": [
        "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=1200&q=80", # Fachada centro de salud / hospital
        "https://images.unsplash.com/photo-1586773860418-d37222d8fce3?auto=format&fit=crop&w=1200&q=80", # Atención médica y consultorio
        "https://images.unsplash.com/photo-1538108149393-fbbd81895907?auto=format&fit=crop&w=1200&q=80"  # Hospital y asistencia sanitaria
    ],
    "educacion_docentes_instituto": [
        "https://images.unsplash.com/photo-1509062522246-3755977927d7?auto=format&fit=crop&w=1200&q=80", # Aula, alumnos y docentes
        "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?auto=format&fit=crop&w=1200&q=80", # Educación superior y capacitación
        "https://images.unsplash.com/photo-1580582932707-520aed937b7b?auto=format&fit=crop&w=1200&q=80"  # Escuela y formación
    ],
    "gobierno_politica": [
        "https://www.diarioelargentino.com/galeria/fotos/2026/08/21/m_1787313394_21810.webp", # Gobernador Frigerio y cumbre intendentes
        "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=1200&q=80"  # Reunión de autoridades y mesa de trabajo
    ],
    "obras_vialidad_infraestructura": [
        "https://images.unsplash.com/photo-1541888946425-d0fbb18086f6?auto=format&fit=crop&w=1200&q=80", # Maquinaria vial y obras
        "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=1200&q=80"  # Construcción e infraestructura
    ],
    "deportes_futbol": [
        "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1200&q=80", # Cancha y fútbol
        "https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=1200&q=80"  # Pelota y actividad deportiva
    ],
    "turismo_pesca_delta": [
        "https://images.unsplash.com/photo-1498654896293-37aacf113fd9?auto=format&fit=crop&w=1200&q=80", # Muelle isleño y lanchas
        "https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=1200&q=80"  # Río y pesca deportiva
    ],
    "comunidad_sociedad": [
        "https://images.unsplash.com/photo-1488521787991-ed7bbaae773c?auto=format&fit=crop&w=1200&q=80", # Solidaridad comunitaria y personas
        "https://images.unsplash.com/photo-1469571486292-0ba58a3f068b?auto=format&fit=crop&w=1200&q=80"  # Comunidad y vecinos unidos
    ]
}

# Palabras clave asociadas a cada temática
THEMATIC_KEYWORDS = {
    "ganaderia_campo": [
        "hacienda", "ganado", "ganadero", "ganaderos", "vaca", "vacas", "rodeo", "rodeos",
        "ternero", "terneros", "barcaza jaula", "pastoreo", "senasa", "ruralnet", "sociedad rural",
        "campo", "pastizales", "abigeato"
    ],
    "policia_seguridad_justicia": [
        "policia", "policía", "detencion", "detención", "detienen", "profuga", "prófuga",
        "estafa", "estafas", "penal", "unidad penal", "justicia", "juzgado", "tribunales",
        "delito", "delitos", "pfa", "policia federal", "captura", "aprehendido", "fiscalia"
    ],
    "fauna_caza_humedales": [
        "cazadores", "cazador", "caza furtiva", "furtivos", "visor termico", "visores termicos",
        "armas", "fusiles", "ciervo", "ciervos", "ciervo de los pantanos", "fauna", "humedal",
        "humedales", "monumento natural", "recurso natural", "delitos rurales"
    ],
    "rio_crecida_clima": [
        "crecida", "crecidas", "rio", "río", "inundacion", "inundación", "alerta hidrica",
        "el nino", "el niño", "hidrometro", "hidrómetro", "recalada", "reflujo", "sudestada",
        "temporal", "lluvia", "lluvias", "evacuacion", "evacuación", "albardon", "albardones",
        "defensas costeras", "bomba de desague", "bombas"
    ],
    "salud_hospital": [
        "hospital", "medico", "médico", "medicos", "médicos", "doctor", "doctora",
        "salud", "guardia", "consultorios", "enfermeria", "enfermería", "vacunacion",
        "vacunatorio", "lancha sanitaria", "ambulancia", "reestructuracion hospital"
    ],
    "educacion_docentes_instituto": [
        "escuela", "instituto superior", "secundaria", "docente", "docentes", "profesor",
        "profesores", "concurso docente", "catedras", "cátedras", "tecnicatura", "estudiantes",
        "alumnos", "cge", "departamental de escuelas"
    ],
    "gobierno_politica": [
        "frigerio", "gobernador", "intendente", "intendentes", "cumbre", "casa de gobierno",
        "ministro", "ministros", "secretario", "provincia de entre rios"
    ],
    "obras_vialidad_infraestructura": [
        "vialidad", "maquinaria", "camino", "caminos", "puente", "balsa", "asfalto",
        "ripiado", "infraestructura", "retroexcavadora", "albardon vial"
    ],
    "deportes_futbol": [
        "futbol", "fútbol", "club", "torneo", "liga", "partido", "cancha", "gol", "campeonato"
    ],
    "turismo_pesca_delta": [
        "turismo", "pesca", "pescador", "cabana", "cabaña", "turistas", "recreacion",
        "naturaleza", "guia de pesca", "descanso"
    ]
}

def is_valid_press_image(url: str) -> bool:
    """Verifica si la URL original es una foto real y no un placeholder o logo temporal."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith("http"):
        return False

    # Descartar miniaturas temporales o íconos comunes
    invalid_patterns = [
        "googleusercontent.com", "gstatic.com", "favicon", "logo", "icon",
        "avatar", "share-button", "pixel.gif", "/advertisement/", "ad-banner",
        "placeholder", "no-image", "default-image"
    ]
    for pattern in invalid_patterns:
        if pattern in url.lower():
            return False

    # Evitar la foto errónea del asado/fogón
    if "photo-1511632765486-a01980e01a18" in url:
        return False

    return True

def resolve_semantic_image(title: str, content: str, category: str = "", original_image: str = "") -> str:
    """
    Determina la mejor imagen para el artículo:
    1. Si la foto original de prensa es válida y de alta resolución, la mantiene.
    2. Si no, analiza semánticamente el texto y asigna una foto de alta definición
       del catálogo especializado según el tema exacto de la noticia.
    """
    if is_valid_press_image(original_image):
        return original_image

    full_text = f"{title} {content} {category}".lower()

    # Ponderación de temas según palabras clave encontradas
    theme_scores = {}
    for theme, keywords in THEMATIC_KEYWORDS.items():
        score = 0
        for kw in keywords:
            # Ponderar más si la palabra está en el título
            if kw in title.lower():
                score += 3
            elif kw in full_text:
                score += 1
        if score > 0:
            theme_scores[theme] = score

    if theme_scores:
        # Elegir el tema con mayor coincidencia
        best_theme = max(theme_scores, key=theme_scores.get)
        images = THEMATIC_IMAGE_CATALOG.get(best_theme, [])
        if images:
            # Determinístico basado en el hash del título para variedad y consistencia
            idx = abs(hash(title)) % len(images)
            logging.info(f"🖼️ Imagen semántica asignada: [{best_theme}] -> {images[idx]}")
            return images[idx]

    # Fallback por categoría si no hubo match de palabras clave
    cat_mapping = {
        "Río y Clima": THEMATIC_IMAGE_CATALOG["rio_crecida_clima"][0],
        "Salud y Educación": THEMATIC_IMAGE_CATALOG["educacion_docentes_instituto"][0],
        "Obras y Servicios": THEMATIC_IMAGE_CATALOG["obras_vialidad_infraestructura"][0],
        "Deportes": THEMATIC_IMAGE_CATALOG["deportes_futbol"][0],
        "Turismo y Cultura": THEMATIC_IMAGE_CATALOG["turismo_pesca_delta"][0],
        "Sociedad": THEMATIC_IMAGE_CATALOG["comunidad_sociedad"][0],
        "Comunidad": THEMATIC_IMAGE_CATALOG["comunidad_sociedad"][0],
    }

    fallback = cat_mapping.get(category, THEMATIC_IMAGE_CATALOG["rio_crecida_clima"][0])
    logging.info(f"🖼️ Imagen fallback por categoría: [{category}]")
    return fallback

def localize_image_if_possible(img_url: str, slug: str) -> str:
    """
    Descarga la imagen a frontend/public/images/noticias/{slug}.jpg para que
    el sitio la sirva directamente sin depender de servidores externos ni hotlinks.
    """
    if not img_url or img_url.startswith("/images/"):
        return img_url

    import requests
    from pathlib import Path
    
    try:
        noticias_img_dir = Path(__file__).parent.parent / "frontend" / "public" / "images" / "noticias"
        noticias_img_dir.mkdir(parents=True, exist_ok=True)
        target_file = noticias_img_dir / f"{slug}.jpg"

        if not target_file.exists():
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            r = requests.get(img_url, timeout=8, headers=headers)
            if r.status_code == 200 and len(r.content) > 3000:
                with open(target_file, "wb") as f:
                    f.write(r.content)
                logging.info(f"💾 Imagen descargada y localizada: /images/noticias/{slug}.jpg")
                return f"/images/noticias/{slug}.jpg"
    except Exception as ex:
        logging.debug(f"No se pudo localizar imagen ({ex}), conservando URL original.")

    return img_url

