"""
Orquestador Principal del Pipeline de Noticias para Villa Paranacito.
v2.2 — Motor de Acontecimient@os Vivos + Quality Gate Editorial
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
from image_manager import resolve_semantic_image
from quality_gate import assess_quality, is_worth_fetching, sanitize_alert_status
from config import DATA_DIR, DEFAULT_CATEGORY_IMAGES, DEFAULT_FALLBACK_IMAGE


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def purge_and_clean_events():
    """
    Escanea data/noticias/ eliminando:
    1. Falsos positivos (apodos "Paranacito" en GBA, Florencio Varela, Quilmes).
    2. Noticias sin relevancia local.
    3. Archivos JSON duplicados que traten sobre el mismo hecho noticioso.
    """
    if not EVENTS_DIR.exists():
        return
        
    from quality_gate import STRICT_EXCLUDE_TERMS
    from event_matcher import keyword_overlap_score

    all_files = list(EVENTS_DIR.glob("*.json"))
    valid_events = []
    purged_count = 0
    cleaned_count = 0
    
    # 1. Primera pasada: filtrar relevancia estricta y falsos positivos
    for f in all_files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                
            raw_title = data.get("titulo", "")
            raw_copete = data.get("copete", "")
            cuerpo = data.get("cuerpo", [])
            cuerpo_str = " ".join(cuerpo) if isinstance(cuerpo, list) else str(cuerpo)
            full_text = f"{raw_title} {raw_copete} {cuerpo_str}".lower()
            
            # Descartar si contiene términos de exclusión estricta (GBA, apodos, etc.)
            if any(term in full_text for term in STRICT_EXCLUDE_TERMS):
                f.unlink(missing_ok=True)
                purged_count += 1
                logging.info(f"🗑️ Eliminado falso positivo de GBA: {f.name}")
                continue

            clean_title = clean_text(raw_title)
            clean_copete = clean_text(raw_copete)
            
            # Comprobar relevancia local estricta
            if not is_locally_relevant(clean_title, f"{clean_copete} {cuerpo_str}"):
                f.unlink(missing_ok=True)
                purged_count += 1
                logging.info(f"🗑️ Eliminada noticia sin ancla local: {f.name}")
                continue
                
            data["titulo"] = clean_title
            data["copete"] = clean_copete
            if isinstance(cuerpo, list):
                data["cuerpo"] = [clean_text(p) for p in cuerpo if clean_text(p)]
                
            current_img = data.get("imagen", "")
            cat = data.get("categoria", "Comunidad")
            data["imagen"] = resolve_semantic_image(clean_title, f"{clean_copete} {cuerpo_str}", cat, current_img)
            
            valid_events.append({"file": f, "data": data, "date": data.get("fecha_iso", "")})
            
        except Exception as ex:
            logging.error(f"Error analizando {f.name}: {ex}")

    # 2. Segunda pasada: deduplicar entre archivos válidos (conservar el más reciente)
    valid_events.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    kept_events = []

    for item in valid_events:
        item_data = item["data"]
        item_text = f"{item_data.get('titulo', '')} {item_data.get('copete', '')}"
        
        is_duplicate = False
        for kept in kept_events:
            kept_data = kept["data"]
            kept_text = f"{kept_data.get('titulo', '')} {kept_data.get('copete', '')}"
            overlap = keyword_overlap_score(item_text, kept_text)
            
            if overlap >= 0.35:
                # Duplicado encontrado: eliminar el archivo más antiguo
                item["file"].unlink(missing_ok=True)
                purged_count += 1
                logging.info(f"🗑️ Eliminado JSON duplicado ({int(overlap*100)}% coincidencia): {item['file'].name}")
                is_duplicate = True
                break
                
        if not is_duplicate:
            # Guardar versión saneada
            with open(item["file"], "w", encoding="utf-8") as file:
                json.dump(item_data, file, ensure_ascii=False, indent=2)
            kept_events.append(item)
            cleaned_count += 1
            
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

    stats = {"nuevos": 0, "actualizaciones": 0, "descartados": 0, "errores": 0, "revision": 0}

    # 5. Procesar cada artículo con el Motor de Acontecimient@os
    for raw in all_raw[:MAX_PROCESS_PER_RUN]:
        url = raw.get("url", "")
        raw_title = clean_text(raw.get("raw_title", ""))
        raw_summary = clean_text(raw.get("raw_summary", raw.get("raw_content", "")))
        source_name = raw.get("source_name", "Fuente Regional")

        # ── FILTRO 0: relevancia geográfica básica (igual que antes) ──────────
        if not is_locally_relevant(raw_title, raw_summary):
            stats["descartados"] += 1
            continue

        # ── FILTRO 1: quality gate PREVIO a la descarga del artículo ──────────
        # Evita gastar tiempo descargando y créditos de IA en artículos que
        # no van a pasar el filtro editorial de todas formas.
        if not is_worth_fetching(raw_title, raw_summary, url):
            logging.info(f"[PRE-GATE] Sin ancla local clara, omitido sin descargar: '{raw_title[:55]}'")
            stats["descartados"] += 1
            continue

        # ── Deduplicación rápida por URL/título ───────────────────────────────
        content_hash = get_content_hash(url, raw_title)
        if content_hash in processed_hashes:
            stats["descartados"] += 1
            continue

        processed_hashes.add(content_hash)

        # ── Motor de acontecimient@os: ¿NEW / UPDATE / DISCARD? ──────────────
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

        # ── action == "NEW": Descargar, reescribir con IA, evaluar calidad ────
        logging.info(f"Extrayendo texto completo desde origen: {url}...")
        full_article_data = extract_full_article(url)
        content = full_article_data.get("full_text") or raw.get("raw_content", raw.get("raw_summary", ""))
        article_title = full_article_data.get("title") or raw_title
        article_image = full_article_data.get("image_url") or raw.get("image_url")
        effective_source = full_article_data.get("source_name") or source_name

        if len(content.strip()) < 40:
            stats["descartados"] += 1
            continue

        logging.info(f"Procesando con IA avanzada ({len(content)} caracteres): '{article_title[:50]}'...")
        try:
            rewritten = rewrite_with_gemini(
                raw_title=article_title,
                raw_content=content,
                source_name=effective_source
            )
            rewritten["url_original"] = full_article_data.get("url") or url
            rewritten["fuente_nombre"] = effective_source
            rewritten["imagen"] = resolve_semantic_image(
                article_title, content, rewritten.get("categoria", "Comunidad"), article_image
            )

            # ── QUALITY GATE POST-IA ──────────────────────────────────────────
            # Decisión editorial final: ¿publicamos, mandamos a revisión o descartamos?
            gate = assess_quality(rewritten, raw, effective_source)
            logging.info(f"[QUALITY GATE] {gate['reason']}")

            if not gate["publish"] and not gate["requires_review"]:
                # Descarte definitivo: la noticia no tiene suficiente ancla local
                logging.info(f"🗑️  Descartada por quality gate: '{article_title[:50]}'")
                stats["descartados"] += 1
                continue

            # Corregir estado de alerta según criterio estricto
            rewritten["es_alerta"] = sanitize_alert_status(
                rewritten.get("titulo", ""),
                rewritten.get("copete", ""),
                gate["is_alert"]
            )

            # Crear el evento con los flags de calidad correctos
            new_event = create_new_event(rewritten, raw)

            # Sobreescribir flags con los del quality gate (más estrictos)
            new_event["nivel_confiabilidad"] = gate["confidence"]
            new_event["requiere_revision"] = gate["requires_review"]
            new_event["publicado"] = gate["publish"] and not gate["requires_review"]
            new_event["es_alerta"] = rewritten["es_alerta"]

            save_event(new_event)

            recent_events.append(new_event)

            if gate["requires_review"]:
                logging.info(f"📋 Enviada a revisión humana: '{article_title[:50]}'")
                stats["revision"] += 1
            else:
                stats["nuevos"] += 1

        except Exception as e:
            logging.error(f"Error procesando con IA '{article_title[:40]}': {e}")
            stats["errores"] += 1


    # 6. Guardar historial, purgar y reconstruir índice
    save_history(processed_hashes)
    purge_and_clean_events()

    logging.info("════════════════════════════════════════════════════════")
    logging.info(f"  PIPELINE COMPLETADO (v2.2 + Quality Gate):")
    logging.info(f"  ✅ Publicados automáticamente: {stats['nuevos']}")
    logging.info(f"  🔄 Actualizaciones: {stats['actualizaciones']}")
    logging.info(f"  📋 En revisión humana: {stats['revision']}")
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
