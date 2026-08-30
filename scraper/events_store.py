"""
events_store.py — Motor de almacenamiento de "Acontecimietos Vivos"
Cada acontecimiento consolida múltiples fuentes sobre un mismo hecho.
"""
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from config import DATA_DIR, DEFAULT_CATEGORY_IMAGES, DEFAULT_FALLBACK_IMAGE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

EVENTS_DIR = DATA_DIR / "noticias"
EVENTS_INDEX = DATA_DIR / "noticias_index.json"
ALERTS_FILE = DATA_DIR / "alertas_activas.json"

EVENTS_DIR.mkdir(parents=True, exist_ok=True)



# Categorías que requieren revisión humana antes de publicar
REVISION_REQUERIDA = {
    "accidente", "fallecimiento", "muerto", "muertos", "detenido", "detenidos",
    "denuncia", "allanamiento", "conflicto", "disputa", "herido", "heridos",
    "arresto", "imputado", "condena", "condenas", "violencia"
}

# Categorías de ALERTA que deben aparecer en el banner urgente
CATEGORIAS_ALERTA = {
    "crecida", "inundación", "inundaciones", "evacuación", "alerta naranja",
    "alerta roja", "temporal", "tornado", "corte de ruta", "ruta cortada",
    "emergencia", "incendio", "incendio de campo", "accidente grave"
}

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def friendly_date(dt: datetime) -> str:
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}, {dt.strftime('%H:%M')} hs"

def generate_event_fingerprint(text: str, date_str: str = "") -> str:
    """Genera un fingerprint del acontecimiento para búsquedas rápidas."""
    normalized = f"{text.lower().strip()} {date_str}".strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def load_event(event_id: str) -> dict | None:
    """Carga un acontecimiento existente por ID."""
    event_file = EVENTS_DIR / f"{event_id}.json"
    if event_file.exists():
        try:
            with open(event_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error cargando acontecimiento {event_id}: {e}")
    return None

def save_event(event: dict) -> bool:
    """Persiste un acontecimiento en disco."""
    event_id = event.get("acontecimiento_id")
    if not event_id:
        return False
    event_file = EVENTS_DIR / f"{event_id}.json"
    with open(event_file, "w", encoding="utf-8") as f:
        json.dump(event, f, ensure_ascii=False, indent=2)
    return True

def create_new_event(rewritten: dict, raw_article: dict) -> dict:
    """
    Crea la estructura de un nuevo acontecimiento (post de feed social) a partir de una noticia reescrita.
    """
    now = datetime.now()
    slug = rewritten.get("slug", "acontecimiento")
    event_id = f"{now.strftime('%Y-%m-%d')}-{slug}"

    # El texto de revisión ahora usa el resumen (más corto y confiable)
    text_check = f"{rewritten.get('titulo','')} {rewritten.get('resumen','')}".lower()
    requires_review = any(w in text_check for w in REVISION_REQUERIDA)

    # Detectar si es una alerta urgente
    is_alert = any(w in text_check for w in CATEGORIAS_ALERTA)

    # Nivel de confiabilidad basado en el tipo de fuente
    fuente_nombre = raw_article.get("source_name", "").lower()
    if any(k in fuente_nombre for k in ["prefectura", "municipalidad", "gobierno", "ministerio", "policia"]):
        confiabilidad = "Alta"
    elif any(k in fuente_nombre for k in ["diario", "r2820", "argentino", "día", "voz isleña", "ceibas"]):
        confiabilidad = "Media"
    else:
        confiabilidad = "Media"

    event = {
        "acontecimiento_id": event_id,
        "titulo": rewritten.get("titulo"),
        "resumen": rewritten.get("resumen", ""),          # ← Formato feed social (2-3 oraciones)
        "categoria": rewritten.get("categoria", "Comunidad"),
        "tags": rewritten.get("tags", []),
        "slug": slug,
        "resumen_whatsapp": rewritten.get("resumen_whatsapp", ""),
        "imagen": raw_article.get("image_url") if (raw_article.get("image_url") and raw_article.get("image_url").startswith("http")) else DEFAULT_CATEGORY_IMAGES.get(rewritten.get("categoria", "Comunidad"), DEFAULT_FALLBACK_IMAGE),
        "fuente_nombre": raw_article.get("source_name", "Fuente regional"),
        "fuente_url": raw_article.get("url", ""),
        "url_original": raw_article.get("url", ""),

        # Metadatos del sistema
        "estado": "En desarrollo" if is_alert else "Publicado",
        "nivel_confiabilidad": confiabilidad,
        "es_alerta": is_alert,
        "requiere_revision": requires_review,
        "publicado": not requires_review,

        # Trazabilidad de fuentes y actualizaciones
        "fuentes_consultadas": [
            {
                "nombre": raw_article.get("source_name", "Fuente regional"),
                "url": raw_article.get("url", ""),
                "fecha_consulta": now.isoformat()
            }
        ],
        "cronologia_actualizaciones": [
            {
                "hora": now.strftime("%H:%M"),
                "fecha": now.strftime("%Y-%m-%d"),
                "fuente": raw_article.get("source_name", "Fuente regional"),
                "dato": rewritten.get("resumen", "")[:200],
                "es_dato_nuevo": True
            }
        ],

        # Huellas para detección de duplicados / similitud
        "fingerprints": [
            generate_event_fingerprint(
                f"{rewritten.get('titulo','')} {raw_article.get('url','')}",
                now.strftime("%Y-%m")
            )
        ],

        # Fechas
        "fecha_iso": now.isoformat(),
        "fecha_inicio_iso": now.isoformat(),
        "fecha_ultima_actualizacion_iso": now.isoformat(),
        "fecha_publicacion": friendly_date(now),
        "fecha_ultima_actualizacion": friendly_date(now),
        "archivo": f"{event_id}.json",
    }

    save_event(event)
    logging.info(f"Nuevo post creado: {event_id}")
    return event

def update_event_with_new_info(event: dict, raw_article: dict, new_info_summary: str) -> dict:
    """
    Actualiza un acontecimiento existente con nueva información.
    """
    now = datetime.now()
    fuente = raw_article.get("source_name", "Fuente regional")
    url = raw_article.get("url", "")

    # Agregar a la cronología
    event.setdefault("cronologia_actualizaciones", []).append({
        "hora": now.strftime("%H:%M"),
        "fecha": now.strftime("%Y-%m-%d"),
        "fuente": fuente,
        "dato": new_info_summary[:300],
        "es_dato_nuevo": True
    })

    # Agregar fuente si no estaba ya registrada
    urls_existentes = {f.get("url") for f in event.get("fuentes_consultadas", [])}
    if url not in urls_existentes:
        event.setdefault("fuentes_consultadas", []).append({
            "nombre": fuente,
            "url": url,
            "fecha_consulta": now.isoformat()
        })

    # Incorporar nuevo fingerprint
    fp = generate_event_fingerprint(f"{raw_article.get('raw_title','')} {url}", now.strftime("%Y-%m"))
    if fp not in event.get("fingerprints", []):
        event.setdefault("fingerprints", []).append(fp)

    event["estado"] = "En desarrollo"
    event["fecha_ultima_actualizacion_iso"] = now.isoformat()
    event["fecha_ultima_actualizacion"] = friendly_date(now)

    save_event(event)
    logging.info(f"Acontecimiento actualizado: {event['acontecimiento_id']}")
    return event

def get_recent_events(hours: int = 72) -> list:
    """
    Carga los acontecimient@os de las últimas N horas para comparar contra nuevas entradas.
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    events = []
    for event_file in sorted(EVENTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(event_file, "r", encoding="utf-8") as f:
                event = json.load(f)
            # Filtrar por fecha de inicio
            fecha_str = event.get("fecha_inicio_iso", "")
            if fecha_str:
                fecha = datetime.fromisoformat(fecha_str)
                if fecha >= cutoff:
                    events.append(event)
        except Exception:
            pass
    return events

def rebuild_events_index():
    """Reconstruye el índice ligero de acontecimient@os para la web."""
    events = []
    for event_file in sorted(EVENTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(event_file, "r", encoding="utf-8") as f:
                e = json.load(f)
            if not e.get("publicado", True) or e.get("requiere_revision", False):
                continue
            events.append({
                "acontecimiento_id": e.get("acontecimiento_id"),
                "slug": e.get("slug"),
                "titulo": e.get("titulo"),
                "copete": e.get("copete"),
                "categoria": e.get("categoria"),
                "tags": e.get("tags", []),
                "estado": e.get("estado", "Publicado"),
                "es_alerta": e.get("es_alerta", False),
                "nivel_confiabilidad": e.get("nivel_confiabilidad", "Media"),
                "imagen": e.get("imagen") if (e.get("imagen") and e.get("imagen").startswith("http")) else DEFAULT_CATEGORY_IMAGES.get(e.get("categoria", "Comunidad"), DEFAULT_FALLBACK_IMAGE),
                "tiempo_lectura": e.get("tiempo_lectura", "2 min"),

                "fuentes_consultadas": [f.get("nombre") for f in e.get("fuentes_consultadas", [])],
                "num_actualizaciones": len(e.get("cronologia_actualizaciones", [])),
                "fecha_publicacion": e.get("fecha_publicacion"),
                "fecha_ultima_actualizacion": e.get("fecha_ultima_actualizacion"),
                "fecha_inicio_iso": e.get("fecha_inicio_iso"),
                "fecha_ultima_actualizacion_iso": e.get("fecha_ultima_actualizacion_iso"),
                "resumen_whatsapp": e.get("resumen_whatsapp", "")
            })
        except Exception as ex:
            logging.error(f"Error indexando {event_file}: {ex}")

    # Ordenar de forma segura convirtiendo a string (evita NoneType error)
    events.sort(
        key=lambda x: str(x.get("fecha_ultima_actualizacion_iso") or x.get("fecha_inicio_iso") or x.get("fecha_iso") or ""),
        reverse=True
    )

    with open(EVENTS_INDEX, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    # Actualizar alertas activas separadas
    alertas = [e for e in events if e.get("es_alerta")]
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alertas, f, ensure_ascii=False, indent=2)

    logging.info(f"Índice de acontecimient@os: {len(events)} eventos ({len(alertas)} alertas activas)")
    return events
