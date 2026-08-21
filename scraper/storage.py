"""
Gestor de persistencia en disco (Git as Database) y control de duplicados.
Compatible con el Motor de Acontecimient@os Vivos (v2.0).
"""
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from config import NOTICIAS_DIR, HISTORY_FILE, DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

INDEX_FILE = DATA_DIR / "noticias_index.json"

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def format_friendly_date(dt: datetime) -> str:
    """Devuelve fecha en formato amigable (ej: 21 de Agosto de 2026, 14:00 hs)."""
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}, {dt.strftime('%H:%M')} hs"

def get_content_hash(url: str, title: str) -> str:
    """Genera un hash único a partir de la URL o el título."""
    key = f"{url.strip()}|{title.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def load_history() -> set:
    """Carga el conjunto de hashes ya procesados."""
    if not HISTORY_FILE.exists():
        return set()
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("processed_hashes", []))
    except Exception as e:
        logging.warning(f"No se pudo cargar historial: {e}. Iniciando vacío.")
        return set()

def save_history(hashes: set):
    """Guarda el historial actualizado."""
    payload = {
        "ultima_actualizacion": datetime.now().isoformat(),
        "total_procesadas": len(hashes),
        "processed_hashes": list(hashes)
    }
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def save_article(article_data: dict, processed_hashes: set) -> bool:
    """
    Guarda una noticia individual en data/noticias/{slug}.json y actualiza el historial.
    """
    slug = article_data.get("slug")
    if not slug:
        logging.warning("Noticia sin slug. Omitiendo guardado.")
        return False

    now = datetime.now()
    fecha_archivo = now.strftime("%Y-%m-%d")
    filename = f"{fecha_archivo}-{slug}.json"
    filepath = NOTICIAS_DIR / filename

    # Enriquecer datos con fechas y metadatos del sitio
    article_data["id"] = f"{fecha_archivo}-{slug}"
    article_data["fecha_iso"] = now.isoformat()
    article_data["fecha_publicacion"] = format_friendly_date(now)
    article_data["archivo"] = filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(article_data, f, ensure_ascii=False, indent=2)

    # Registrar en historial
    content_hash = get_content_hash(article_data.get("url_original", ""), article_data.get("titulo", ""))
    processed_hashes.add(content_hash)
    save_history(processed_hashes)

    logging.info(f"Noticia guardada con éxito: {filename}")
    return True

def rebuild_master_index():
    """
    Genera data/noticias_index.json ordenado cronológicamente con resúmenes ligeros.
    Esto permite que la web cargue instantáneamente sin leer archivo por archivo.
    """
    articles = []
    for json_file in sorted(NOTICIAS_DIR.glob("*.json"), reverse=True):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Resumen ligero para el índice
                articles.append({
                    "id": data.get("id"),
                    "slug": data.get("slug"),
                    "titulo": data.get("titulo"),
                    "copete": data.get("copete"),
                    "categoria": data.get("categoria"),
                    "tags": data.get("tags", []),
                    "fecha_publicacion": data.get("fecha_publicacion"),
                    "fecha_iso": data.get("fecha_iso"),
                    "imagen": data.get("imagen", "/images/default-paranacito.jpg"),
                    "tiempo_lectura": data.get("tiempo_lectura", "2 min"),
                    "fuente_nombre": data.get("fuente_nombre", "Fuente Local"),
                    "resumen_whatsapp": data.get("resumen_whatsapp", "")
                })
        except Exception as e:
            logging.error(f"Error leyendo {json_file}: {e}")

    # Ordenar por fecha_iso descendente
    articles.sort(key=lambda x: x.get("fecha_iso", ""), reverse=True)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    logging.info(f"Índice maestro actualizado: {len(articles)} noticias en {INDEX_FILE}")
    return articles
