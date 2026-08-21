"""
Orquestador Principal del Pipeline de Noticias para Villa Paranacito.
v2.0 — Motor de Acontecimient@os Vivos + Radar GDELT/Google News
"""
import sys
import logging
import argparse

from weather_river import update_weather_and_river
from sources_extractor import fetch_all_sources
from news_radar import run_radar
from ai_rewriter import rewrite_with_gemini
from storage import load_history, get_content_hash, rebuild_master_index
from events_store import (
    create_new_event, update_event_with_new_info,
    get_recent_events, rebuild_events_index, save_event
)
from event_matcher import match_article_to_events

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def run_pipeline(use_radar: bool = True):
    """Ejecuta el ciclo completo de ingestión con Motor de Acontecimient@os Vivos."""
    logging.info("════════════════════════════════════════════════════════")
    logging.info("  PARANACITO NOTICIAS — PIPELINE v2.0 — INICIANDO")
    logging.info("════════════════════════════════════════════════════════")

    # 1. Actualizar Clima y Río
    try:
        update_weather_and_river()
    except Exception as e:
        logging.error(f"Error en módulo de clima: {e}")

    # 2. Cargar acontecimient@os recientes (últimas 72 hs) para comparar
    recent_events = get_recent_events(hours=72)
    logging.info(f"Acontecimient@os activos en ventana de 72 hs: {len(recent_events)}")

    # 3. Historial de URLs ya procesadas (deduplicación rápida sin IA)
    processed_hashes = load_history()
    logging.info(f"Historial de URLs procesadas: {len(processed_hashes)}")

    # 4. Recolectar artículos de todas las fuentes
    raw_from_feeds = fetch_all_sources()
    raw_from_radar = run_radar() if use_radar else []
    all_raw = raw_from_feeds + raw_from_radar
    MAX_PROCESS_PER_RUN = 30
    logging.info(f"Total artículos crudos recolectados: {len(all_raw)} ({len(raw_from_feeds)} feeds + {len(raw_from_radar)} radar)")

    stats = {"nuevos": 0, "actualizaciones": 0, "descartados": 0, "errores": 0}

    # 5. Procesar cada artículo con el Motor de Acontecimient@os (limitado a los 30 más frescos por corrida)
    for raw in all_raw[:MAX_PROCESS_PER_RUN]:

        url = raw.get("url", "")
        raw_title = raw.get("raw_title", "")

        # 5a. Deduplicación rápida por URL/título
        content_hash = get_content_hash(url, raw_title)
        if content_hash in processed_hashes:
            logging.debug(f"URL ya procesada: {raw_title[:50]}")
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
            # Registrar la fuente como consultada en el acontecimiento existente
            if matched_event:
                fuentes_existentes = {f.get("url") for f in matched_event.get("fuentes_consultadas", [])}
                if url not in fuentes_existentes:
                    matched_event.setdefault("fuentes_consultadas", []).append({
                        "nombre": raw.get("source_name", "Fuente"),
                        "url": url,
                        "fecha_consulta": __import__("datetime").datetime.now().isoformat()
                    })
                    save_event(matched_event)
            stats["descartados"] += 1
            continue

        if action == "UPDATE" and matched_event:
            # Actualizar acontecimiento existente con la info nueva
            update_event_with_new_info(matched_event, raw, new_info_summary)
            # Actualizar en recent_events en memoria para siguientes iteraciones
            for i, ev in enumerate(recent_events):
                if ev.get("acontecimiento_id") == matched_event.get("acontecimiento_id"):
                    recent_events[i] = matched_event
                    break
            stats["actualizaciones"] += 1
            continue

        # action == "NEW": Reescribir con IA y crear nuevo acontecimiento
        content = raw.get("raw_content", raw.get("raw_summary", ""))
        if len(content.strip()) < 50:
            logging.debug(f"Contenido insuficiente para procesar: '{raw_title[:40]}'")
            stats["descartados"] += 1
            continue

        logging.info(f"Procesando con IA nuevo acontecimiento: '{raw_title[:50]}'...")
        try:
            rewritten = rewrite_with_gemini(
                raw_title=raw_title,
                raw_content=content,
                source_name=raw.get("source_name", "Fuente Regional")
            )
            rewritten["url_original"] = url
            rewritten["fuente_nombre"] = raw.get("source_name", "Fuente Regional")
            rewritten["imagen"] = raw.get("image_url", "/images/default-paranacito.jpg")

            new_event = create_new_event(rewritten, raw)
            recent_events.append(new_event)  # Agregar a ventana activa
            stats["nuevos"] += 1

        except Exception as e:
            logging.error(f"Error procesando con IA '{raw_title[:40]}': {e}")
            stats["errores"] += 1

    # 6. Reconstruir índices
    rebuild_events_index()
    rebuild_master_index()  # Mantiene compatibilidad con la web actual

    logging.info("════════════════════════════════════════════════════════")
    logging.info(f"  PIPELINE COMPLETADO:")
    logging.info(f"  ✅ Nuevos acontecimient@os: {stats['nuevos']}")
    logging.info(f"  🔄 Actualizaciones: {stats['actualizaciones']}")
    logging.info(f"  🗑️  Descartados (redundantes): {stats['descartados']}")
    logging.info(f"  ❌ Errores: {stats['errores']}")
    logging.info("════════════════════════════════════════════════════════")


def run_seed_sample():
    """Genera acontecimient@os de muestra iniciales."""
    from datetime import datetime

    logging.info("Cargando acontecimient@os de muestra iniciales...")
    update_weather_and_river()

    samples = [
        {
            "titulo": "Río Paranacito: Altura estable en 1.85 metros y pronóstico favorable para la navegación",
            "copete": "Prefectura Naval confirmó que el cauce se mantiene dentro de los valores de seguridad.",
            "cuerpo": [
                "Los registros del hidrómetro en el puerto local marcaron una cota de 1.85 metros con tendencia estacionaria.",
                "Prefectura Naval destacó que no se esperan repuntes significativos en la cuenca baja del Río Uruguay.",
                "Se recuerda a los navegantes mantener la precaución en zonas de curvas cerradas."
            ],
            "categoria": "Río y Clima", "tags": ["río", "prefectura", "navegación"], "slug": "rio-paranacito-altura-estable",
            "tiempo_lectura": "2 min", "resumen_whatsapp": "🌊 Río Paranacito estable en 1.85m. Navegación en condiciones normales."
        },
        {
            "titulo": "Avanzan los trabajos de mantenimiento en el camino de acceso a Villa Paranacito",
            "copete": "Equipos viales municipales intensifican tareas de recomposición del tramo principal.",
            "cuerpo": [
                "Personal de Vialidad continúa tareas de bacheo y reposición de material calcáreo.",
                "Las intervenciones se concentran en los sectores más comprometidos del trazado.",
                "Se recomendó transitar con precaución ante presencia de maquinaria en banquinas."
            ],
            "categoria": "Obras y Servicios", "tags": ["obras", "camino", "vialidad"], "slug": "avanzan-trabajos-mantenimiento-camino-acceso",
            "tiempo_lectura": "2 min", "resumen_whatsapp": "🚜 Avanzan obras de mantenimiento vial en Paranacito."
        },
        {
            "titulo": "El Club Isleños Independientes convoca a una nueva fecha del torneo regional de fútbol",
            "copete": "La institución deportiva será sede de partidos en categorías infantiles y primera división.",
            "cuerpo": [
                "El Club Isleños Independientes recibirá a cientos de familias para disputar una nueva fecha.",
                "La actividad comienza a las 10:00 hs con divisiones formativas y Primera División a las 15:30 hs.",
                "La comisión invitó a toda la comunidad a acompañar a los deportistas locales."
            ],
            "categoria": "Deportes", "tags": ["club isleños", "fútbol", "deportes"], "slug": "club-islenos-nueva-fecha-futbol",
            "tiempo_lectura": "2 min", "resumen_whatsapp": "⚽ Gran fecha de fútbol este finde en Club Isleños Independientes."
        },
        {
            "titulo": "Operativo Sanitario Fluvial: Atención médica en escuelas y parajes del Delta",
            "copete": "La lancha sanitaria recorrerá diferentes arroyos brindando consultas y vacunación.",
            "cuerpo": [
                "El cronograma abarcará escuelas rurales sobre el Arroyo Martínez y Brazo Largo.",
                "Los vecinos podrán acceder a consultas médicas, vacunas y medicamentos de forma gratuita.",
                "El operativo está disponible sin necesidad de trasladarse al casco urbano."
            ],
            "categoria": "Salud y Educación", "tags": ["salud", "lancha sanitaria", "delta"], "slug": "operativo-sanitario-fluvial",
            "tiempo_lectura": "2 min", "resumen_whatsapp": "🏥 Operativo sanitario en lancha para parajes del Delta."
        },
        {
            "titulo": "Temporada de Pesca y Ecoturismo: Crecen reservas en cabañas del Delta",
            "copete": "Prestadores turísticos destacan alto nivel de consultas y demanda de excursiones.",
            "cuerpo": [
                "El sector turístico registra un marcado incremento en la demanda de cabañas y guías de pesca.",
                "La combinación de naturaleza y pesca de temporada convierte al Delta en destino predilecto.",
                "Se recordó respetar las normativas de pesca con devolución para preservar el ecosistema."
            ],
            "categoria": "Turismo y Cultura", "tags": ["turismo", "pesca", "delta"], "slug": "crecen-reservas-turismo-pesca",
            "tiempo_lectura": "2 min", "resumen_whatsapp": "🎣 Crecen reservas para pesca y descanso en el Delta de Paranacito."
        },
        {
            "titulo": "Bomberos Voluntarios de Villa Paranacito renuevan equipamiento para rescate acuático",
            "copete": "El cuerpo activo incorporó chalecos certificados, cabos de remolque y reflectores nocturnos.",
            "cuerpo": [
                "Gracias a la rifa anual y subsidios, Bomberos sumó equipamiento para intervenciones fluviales.",
                "El jefe de cuerpo destacó la importancia para responder a contingencias en ríos y arroyos.",
                "Agradecieron el respaldo de vecinos y comerciantes que hacen posible el crecimiento."
            ],
            "categoria": "Comunidad", "tags": ["bomberos", "rescate", "seguridad"], "slug": "bomberos-renuevan-equipamiento-rescate",
            "tiempo_lectura": "2 min", "resumen_whatsapp": "🚒 Bomberos Voluntarios de Paranacito incorporaron nuevo equipo de rescate."
        }
    ]

    IMAGENES = [
        "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1578885136359-16c8bd4d3a8e?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=1000&q=80",
        "https://images.unsplash.com/photo-1582139329536-e7284fece509?auto=format&fit=crop&w=1000&q=80"
    ]
    FUENTES = [
        "Prefectura Naval & Monitoreo Local",
        "Prensa Municipal",
        "Subcomisión de Prensa del Club",
        "Área de Salud y Acción Social",
        "Cámara de Turismo de Paranacito",
        "Asociación Bomberos Voluntarios"
    ]

    for i, sample in enumerate(samples):
        raw_dummy = {
            "source_name": FUENTES[i],
            "url": f"https://source-{i}.example.com",
            "image_url": IMAGENES[i]
        }
        create_new_event(sample, raw_dummy)

    rebuild_events_index()
    rebuild_master_index()
    logging.info("✅ Acontecimient@os de muestra cargados correctamente.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline de Noticias Villa Paranacito v2.0")
    parser.add_argument("--seed", action="store_true", help="Genera acontecimient@os de muestra")
    parser.add_argument("--no-radar", action="store_true", help="Deshabilita GDELT y Google News")
    args = parser.parse_args()

    if args.seed:
        run_seed_sample()
    else:
        run_pipeline(use_radar=not args.no_radar)
