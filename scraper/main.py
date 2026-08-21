"""
Orquestador Principal del Pipeline de Noticias para Villa Paranacito.
Ejecutado periódicamente por GitHub Actions o manualmente.
"""
import sys
import logging
import argparse
from datetime import datetime

from weather_river import update_weather_and_river
from sources_extractor import fetch_all_sources
from ai_rewriter import rewrite_with_gemini
from storage import load_history, save_article, rebuild_master_index, get_content_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

SAMPLE_NEWS = [
    {
        "titulo": "Río Paranacito: Altura estable en 1.85 metros y pronóstico favorable para la navegación",
        "copete": "Prefectura Naval y el área de monitoreo confirmaron que el cauce se mantiene dentro de los valores habituales de seguridad en todo el sector de islas.",
        "cuerpo": [
            "Durante las primeras horas de este viernes, los registros del hidrómetro en el puerto local marcaron una cota de 1.85 metros, registrando una tendencia estacionaria respecto a las jornadas anteriores.",
            "Las autoridades de Prefectura Naval Argentina destacaron que no se esperan repuntes significativos en la cuenca baja del Río Uruguay en el corto plazo, lo que asegura condiciones óptimas tanto para los traslados escolares como para la actividad comercial de lanchas almaceneras y de pasajeros.",
            "Se recuerda a los navegantes deportivos y comerciales mantener la precaución en las zonas de curvas cerradas y respetar las velocidades de paso frente a viviendas ribereñas y amarraderos para evitar oleajes perjudiciales."
        ],
        "categoria": "Río y Clima",
        "tags": ["rio paranacito", "prefectura", "navegacion", "delta"],
        "slug": "rio-paranacito-altura-estable-pronostico-favorable",
        "tiempo_lectura": "2 min",
        "fuente_nombre": "Prefectura Naval & Monitoreo Local",
        "url_original": "https://prefecturanaval.gob.ar",
        "imagen": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1000&q=80",
        "resumen_whatsapp": "🌊 *Río Paranacito:* Altura estable en 1.85m con condiciones normales de navegación en el Delta."
    },
    {
        "titulo": "Avanzan los trabajos de mantenimiento y perfilado en el camino de acceso a Villa Paranacito",
        "copete": "Equipos viales provinciales y municipales intensifican las tareas de recomposición de ripio y desagües a lo largo del tramo principal.",
        "cuerpo": [
            "Con el objetivo de garantizar la conectividad terrestre de la comunidad isleña, personal de la Dirección Provincial de Vialidad en conjunto con maquinaria municipal continúa ejecutando tareas de bacheo superficial, limpieza de cunetas y reposición de material calcáreo.",
            "Las intervenciones se concentran en los sectores más comprometidos del trazado, optimizando la circulación de vehículos particulares, transporte de cargas y el servicio diario de colectivos que une la localidad con la Ruta Nacional 12.",
            "Desde la secretaría de obras públicas recomendaron transitar con extrema precaución ante la presencia de operarios y maquinarias pesadas trabajando en banquinas durante el horario diurno."
        ],
        "categoria": "Obras y Servicios",
        "tags": ["obras", "camino de acceso", "vialidad", "villa paranacito"],
        "slug": "avanzan-trabajos-mantenimiento-camino-acceso",
        "tiempo_lectura": "2 min",
        "fuente_nombre": "Prensa Municipal",
        "url_original": "https://villaparanacito.gob.ar",
        "imagen": "https://images.unsplash.com/photo-1541888946425-d0fbb18086f6?auto=format&fit=crop&w=1000&q=80",
        "resumen_whatsapp": "🚜 *Vialidad:* Avanzan los trabajos de mantenimiento en el camino de acceso a Paranacito."
    },
    {
        "titulo": "El Club Isleños Independientes convoca a una nueva fecha del torneo regional de fútbol",
        "copete": "Este fin de semana la institución deportiva albiverde será sede de una emocionante jornada comunitaria con partidos en categorías infantiles y primera división.",
        "cuerpo": [
            "El Club Deportivo Isleños Independientes se prepara para recibir a cientos de familias isleñas en sus instalaciones para disputar una nueva fecha del certamen departamental.",
            "La actividad comenzará desde las 10:00 hs con los encuentros de las divisiones formativas, mientras que el plato fuerte de Primera División está programado para las 15:30 hs. Habrá servicio completo de cantina a beneficio de las obras del gimnasio cubierto.",
            "La comisión directiva invitó a toda la comunidad de Villa Paranacito y parajes vecinos a sumarse y acompañar a los deportistas locales en una jornada que promete gran concurrencia."
        ],
        "categoria": "Deportes",
        "tags": ["club islenos", "futbol", "deportes", "comunidad"],
        "slug": "club-islenos-independientes-nueva-fecha-futbol",
        "tiempo_lectura": "2 min",
        "fuente_nombre": "Subcomisión de Prensa del Club",
        "url_original": "https://facebook.com/clubislenos",
        "imagen": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1000&q=80",
        "resumen_whatsapp": "⚽ *Deportes:* ¡Gran fecha de fútbol este finde en el Club Isleños Independientes de Paranacito!"
    },
    {
        "titulo": "Operativo Sanitario Fluvial: Atención médica y vacunación en escuelas y parajes isleños",
        "copete": "El equipo de salud del Hospital local recorrerá diferentes arroyos para brindar consultas pediátricas, odontología y completar esquemas de calendario.",
        "cuerpo": [
            "En el marco del programa de atención primaria en el Delta, la lancha sanitaria municipal y provincial desplegará un amplio operativo médico itinerante a lo largo de la próxima semana.",
            "El cronograma abarcará escuelas rurales y muelles comunitarios situados sobre el Arroyo Martínez, Brazo Largo y zonas adyacentes, facilitando el acceso a controles integrales sin que las familias deban trasladarse al casco urbano.",
            "Los vecinos podrán realizar consultas de clínica médica, enfermería, aplicación de vacunas obligatorias y retiro de medicamentos esenciales de manera completamente gratuita."
        ],
        "categoria": "Salud y Educación",
        "tags": ["salud", "lancha sanitaria", "hospital", "escuelas isleñas"],
        "slug": "operativo-sanitario-fluvial-atencion-parajes",
        "tiempo_lectura": "2 min",
        "fuente_nombre": "Área de Salud y Acción Social",
        "url_original": "https://salud.entrerios.gov.ar",
        "imagen": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1000&q=80",
        "resumen_whatsapp": "🏥 *Salud:* Nuevo operativo sanitario en lancha para recorrer escuelas y parajes del Delta."
    },
    {
        "titulo": "Temporada de Pesca y Ecoturismo: Crecen las reservas en cabañas y guiadas del Delta",
        "copete": "Los prestadores turísticos destacan un alto nivel de consultas atraídos por la tranquilidad, la gastronomía isleña y la riqueza ictícola de la región.",
        "cuerpo": [
            "Con la llegada de temperaturas templadas, el sector turístico de Villa Paranacito registra un marcado incremento en la demanda de alojamiento en complejos de cabañas y excursiones guiadas de pesca deportiva.",
            "La combinación de naturaleza agreste, safaris fotográficos en lancha y la pesca de especies de temporada convierte a nuestro destino en una de las escapadas predilectas para visitantes de Buenos Aires, Rosario y el interior entrerriano.",
            "Desde la Asociación de Prestadores Turísticos recordaron la vigencia de las normativas de pesca con devolución y el compromiso colectivo de preservar la fauna y flora nativa de nuestros humedales."
        ],
        "categoria": "Turismo y Cultura",
        "tags": ["turismo", "pesca deportiva", "delta", "cabanas"],
        "slug": "crecen-reservas-turismo-pesca-delta",
        "tiempo_lectura": "2 min",
        "fuente_nombre": "Cámara de Turismo de Paranacito",
        "url_original": "https://turismoentrerios.com",
        "imagen": "https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=1000&q=80",
        "resumen_whatsapp": "🎣 *Turismo:* Excelente expectativa y reservas para la pesca y descanso en el Delta."
    },
    {
        "titulo": "Bomberos Voluntarios de Villa Paranacito renuevan equipamiento para rescate acuático",
        "copete": "El cuerpo activo incorporó nuevos chalecos salvavidas certificados, cabos de remolque y reflectores de alta potencia para emergencias nocturnas.",
        "cuerpo": [
            "Gracias al aporte de la comunidad a través de la rifa anual y subsidios específicos, el cuartel de Bomberos Voluntarios sumó valiosos elementos de protección y auxilio para intervenciones fluviales.",
            "El jefe de cuerpo activo destacó que estos equipos resultan fundamentales para brindar una respuesta ágil y segura ante contingencias climáticas, rescates en ríos y arroyos o incendios de pastizales en zonas de difícil acceso.",
            "Asimismo, agradecieron el continuo respaldo de los vecinos y comerciantes locales que hacen posible el crecimiento constante de la institución de servicio."
        ],
        "categoria": "Comunidad",
        "tags": ["bomberos", "rescate", "seguridad", "solidaridad"],
        "slug": "bomberos-voluntarios-renuevan-equipamiento-rescate",
        "tiempo_lectura": "2 min",
        "fuente_nombre": "Asociación Bomberos Voluntarios",
        "url_original": "https://facebook.com/bomberosparanacito",
        "imagen": "https://images.unsplash.com/photo-1582139329536-e7284fece509?auto=format&fit=crop&w=1000&q=80",
        "resumen_whatsapp": "🚒 *Comunidad:* Bomberos Voluntarios de Paranacito incorporaron nuevo equipo de rescate fluvial."
    }
]

def run_seed_sample():
    """Genera noticias iniciales de alta calidad para poblar el portal."""
    logging.info("Cargando noticias iniciales de muestra para Villa Paranacito...")
    processed_hashes = load_history()
    
    for item in SAMPLE_NEWS:
        save_article(item, processed_hashes)
        
    rebuild_master_index()
    logging.info("Noticias de muestra cargadas con éxito.")

def run_pipeline():
    """Ejecuta el ciclo completo de ingestión, IA y actualización."""
    logging.info("=== INICIANDO PIPELINE DE NOTICIAS: VILLA PARANACITO ===")
    
    # 1. Clima y Río
    try:
        update_weather_and_river()
    except Exception as e:
        logging.error(f"Error en módulo de clima: {e}")

    # 2. Historial de duplicados
    processed_hashes = load_history()
    logging.info(f"Historial actual: {len(processed_hashes)} artículos registrados previamente.")

    # 3. Extracción de fuentes
    raw_articles = fetch_all_sources()
    logging.info(f"Total de notas crudas extraídas de feeds: {len(raw_articles)}")

    new_articles_count = 0

    # 4. Procesamiento con IA
    for raw in raw_articles:
        url = raw.get("url", "")
        raw_title = raw.get("raw_title", "")
        content_hash = get_content_hash(url, raw_title)

        if content_hash in processed_hashes:
            logging.debug(f"Nota ya procesada anteriormente: {raw_title}")
            continue

        logging.info(f"Procesando con IA nueva noticia: '{raw_title}' de {raw.get('source_name')}...")
        
        rewritten = rewrite_with_gemini(
            raw_title=raw_title,
            raw_content=raw.get("raw_content", raw.get("raw_summary", "")),
            source_name=raw.get("source_name", "Fuente Regional")
        )

        # Asociar URL original e imagen
        rewritten["url_original"] = url
        rewritten["fuente_nombre"] = raw.get("source_name", "Fuente Regional")
        rewritten["imagen"] = raw.get("image_url", "/images/default-paranacito.jpg")

        save_article(rewritten, processed_hashes)
        new_articles_count += 1

    # 5. Reconstruir índice maestro
    rebuild_master_index()
    logging.info(f"=== PIPELINE FINALIZADO: {new_articles_count} nuevas noticias publicadas. ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline de Noticias Villa Paranacito")
    parser.add_argument("--seed", action="store_true", help="Genera noticias de muestra iniciales")
    args = parser.parse_args()

    if args.seed:
        update_weather_and_river()
        run_seed_sample()
    else:
        run_pipeline()
