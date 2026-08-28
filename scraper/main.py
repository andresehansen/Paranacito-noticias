"""
Orquestador Principal del Pipeline de Noticias para Villa Paranacito.
v2.1 — Motor de Acontecimient@os Vivos + Extractor de Texto Completo + Gemini Pro/Flash
"""
import sys
import json
import logging
import argparse
from datetime import datetime

from weather_river import update_weather_and_river
from sources_extractor import fetch_all_sources
from news_radar import run_radar, clean_text, is_locally_relevant
from article_extractor import extract_full_article
from ai_rewriter import rewrite_with_gemini
from storage import load_history, get_content_hash, save_history
from events_store import (
    create_new_event, update_event_with_new_info,
    get_recent_events, rebuild_events_index, save_event, EVENTS_DIR
)
from event_matcher import match_article_to_events
from config import DATA_DIR, DEFAULT_CATEGORY_IMAGES, DEFAULT_FALLBACK_IMAGE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def purge_and_clean_events():
    """
    Escanea data/noticias/ eliminando cualquier noticia que no sea 100%
    relevante para Villa Paranacito y corrigiendo caracteres/entidades HTML.
    """
    if not EVENTS_DIR.exists():
        return
        
    purged_count = 0
    cleaned_count = 0
    
    for f in list(EVENTS_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                
            raw_title = data.get("titulo", "")
            raw_copete = data.get("copete", "")
            cuerpo = data.get("cuerpo", [])
            cuerpo_str = " ".join(cuerpo) if isinstance(cuerpo, list) else str(cuerpo)
            
            clean_title = clean_text(raw_title)
            clean_copete = clean_text(raw_copete)
            
            # 1. Comprobar relevancia estricta
            if not is_locally_relevant(clean_title, f"{clean_copete} {cuerpo_str}"):
                f.unlink(missing_ok=True)
                purged_count += 1
                logging.info(f"🗑️ Eliminada noticia descartada: {f.name} ('{clean_title[:40]}')")
                continue
                
            # 2. Limpiar textos de entidades HTML
            data["titulo"] = clean_title
            data["copete"] = clean_copete
            if isinstance(cuerpo, list):
                data["cuerpo"] = [clean_text(p) for p in cuerpo if clean_text(p)]
                
            # 3. Asegurar imagen válida en alta definición
            img = data.get("imagen", "")
            if not img or not img.startswith("http") or "/images/" in img:
                cat = data.get("categoria", "Comunidad")
                data["imagen"] = DEFAULT_CATEGORY_IMAGES.get(cat, DEFAULT_FALLBACK_IMAGE)
                
            with open(f, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            cleaned_count += 1
            
        except Exception as ex:
            logging.error(f"Error procesando {f.name}: {ex}")
            
    logging.info(f"Purga y saneamiento: {purged_count} eliminadas, {cleaned_count} verificadas.")
    rebuild_events_index()

def run_pipeline(use_radar: bool = True):
    """Ejecuta el ciclo completo de ingestión con Motor de Acontecimient@os Vivos."""
    logging.info("════════════════════════════════════════════════════════")
    logging.info("  PARANACITO NOTICIAS — PIPELINE v2.1 — INICIANDO")
    logging.info("════════════════════════════════════════════════════════")

    # 0. Limpieza previa de eventos obsoletos o malformados
    purge_and_clean_events()

    # 1. Actualizar Clima y Río
    try:
        update_weather_and_river()
    except Exception as e:
        logging.error(f"Error en módulo de clima: {e}")

    # 2. Cargar acontecimientos recientes (últimos 7 días / 168 hs) para deduplicar
    recent_events = get_recent_events(hours=168)
    logging.info(f"Acontecimientos activos en ventana de 7 días: {len(recent_events)}")


    # 3. Historial de URLs ya procesadas (deduplicación rápida sin IA)
    processed_hashes = load_history()
    logging.info(f"Historial de URLs procesadas: {len(processed_hashes)}")

    # 4. Recolectar artículos de todas las fuentes
    raw_from_feeds = fetch_all_sources()
    raw_from_radar = run_radar() if use_radar else []
    all_raw = raw_from_feeds + raw_from_radar
    MAX_PROCESS_PER_RUN = 25
    logging.info(f"Total artículos crudos recolectados: {len(all_raw)} ({len(raw_from_feeds)} feeds + {len(raw_from_radar)} radar)")

    stats = {"nuevos": 0, "actualizaciones": 0, "descartados": 0, "errores": 0}

    # 5. Procesar cada artículo con el Motor de Acontecimient@os
    for raw in all_raw[:MAX_PROCESS_PER_RUN]:
        url = raw.get("url", "")
        raw_title = clean_text(raw.get("raw_title", ""))

        if not is_locally_relevant(raw_title, raw.get("raw_content", "")):
            stats["descartados"] += 1
            continue

        # 5a. Deduplicación rápida por URL/título
        content_hash = get_content_hash(url, raw_title)
        if content_hash in processed_hashes:
            stats["descartados"] += 1
            continue

        processed_hashes.add(content_hash)

        # 5b. Motor de acontecimient@os: ¿NEW / UPDATE / DISCARD?
        try:
            match_result = match_article_to_events(raw, recent_events)
        except Exception as e:
            logging.error(f"Error en event_matcher: {e}")
            stats["errores"] += 1
            continue

        action = match_result["action"]
        matched_event = match_result.get("matched_event")
        novelty_pct = match_result.get("novelty_pct", 0)
        new_info_summary = match_result.get("new_info_summary", "")

        logging.info(f"[{action}] ({novelty_pct}%) '{raw_title[:55]}'")

        if action == "DISCARD":
            if matched_event:
                fuentes_existentes = {f.get("url") for f in matched_event.get("fuentes_consultadas", [])}
                if url not in fuentes_existentes:
                    matched_event.setdefault("fuentes_consultadas", []).append({
                        "nombre": raw.get("source_name", "Fuente"),
                        "url": url,
                        "fecha_consulta": datetime.now().isoformat()
                    })
                    save_event(matched_event)
            stats["descartados"] += 1
            continue

        if action == "UPDATE" and matched_event:
            update_event_with_new_info(matched_event, raw, new_info_summary)
            for i, ev in enumerate(recent_events):
                if ev.get("acontecimiento_id") == matched_event.get("acontecimiento_id"):
                    recent_events[i] = matched_event
                    break
            stats["actualizaciones"] += 1
            continue

        # action == "NEW": Extraer contenido completo de la página original y reescribir con IA avanzada
        logging.info(f"Extrayendo texto completo desde origen: {url}...")
        full_article_data = extract_full_article(url)
        content = full_article_data.get("full_text") or raw.get("raw_content", raw.get("raw_summary", ""))
        article_title = full_article_data.get("title") or raw_title
        article_image = full_article_data.get("image_url") or raw.get("image_url")

        if len(content.strip()) < 40:
            stats["descartados"] += 1
            continue

        logging.info(f"Procesando con IA avanzada ({len(content)} caracteres): '{article_title[:50]}'...")
        try:
            rewritten = rewrite_with_gemini(
                raw_title=article_title,
                raw_content=content,
                source_name=full_article_data.get("source_name") or raw.get("source_name", "Fuente Regional")
            )
            rewritten["url_original"] = full_article_data.get("url") or url
            rewritten["fuente_nombre"] = full_article_data.get("source_name") or raw.get("source_name", "Fuente Regional")
            rewritten["imagen"] = article_image or DEFAULT_CATEGORY_IMAGES.get(rewritten.get("categoria", "Comunidad"), DEFAULT_FALLBACK_IMAGE)

            new_event = create_new_event(rewritten, raw)
            recent_events.append(new_event)
            stats["nuevos"] += 1

        except Exception as e:
            logging.error(f"Error procesando con IA '{article_title[:40]}': {e}")
            stats["errores"] += 1

    # 6. Guardar historial, purgar y reconstruir índice
    save_history(processed_hashes)
    purge_and_clean_events()

    logging.info("════════════════════════════════════════════════════════")
    logging.info(f"  PIPELINE COMPLETADO:")
    logging.info(f"  ✅ Nuevos acontecimient@os: {stats['nuevos']}")
    logging.info(f"  🔄 Actualizaciones: {stats['actualizaciones']}")
    logging.info(f"  🗑️  Descartados: {stats['descartados']}")
    logging.info(f"  ❌ Errores: {stats['errores']}")
    logging.info("════════════════════════════════════════════════════════")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestor de Noticias - Villa Paranacito")
    parser.add_argument("--no-radar", action="store_true", help="Desactivar radar de descubrimiento")
    parser.add_argument("--purge", action="store_true", help="Solo ejecutar purga de noticias inválidas")
    args = parser.parse_args()

    if args.purge:
        purge_and_clean_events()
    else:
        run_pipeline(use_radar=not args.no_radar)
