"""
quality_gate.py — Puerta de Calidad Editorial para Paranacito Noticias
Responsabilidad única: decidir si una noticia es digna de publicarse automáticamente.

Criterios (todos deben cumplirse para publicación automática):
  1. Ancla geográfica CONCRETA y EXPLÍCITA en Villa Paranacito o instituciones reconocidas del lugar.
  2. Fuente verificable (no puede ser una búsqueda de Google genérica o GDELT sin fuente real).
  3. Sin datos inventados (porcentajes sin fuente, nombres de personas sin confirmar, etc).
  4. ALERTA solo para emergencias hídricas o de seguridad reales con datos concretos.
"""

import re
import logging

# ── Anclas geográficas FUERTES (DEBEN aparecer explícitamente en el texto) ────
# Al menos una debe estar presente en el título o copete directamente.
STRONG_LOCAL_ANCHORS = [
    # Villa Paranacito y variantes
    "villa paranacito",
    "paranacito",
    "río paranacito",
    "rio paranacito",
    # Departamento Islas del Ibicuy (incluye Ceibas, Ibicuy, Pueblo Brugo)
    "islas del ibicuy",
    "departamento islas",
    "ceibas",
    "villa ceibas",
    "ibicuy",
    "pueblo brugo",
    # Geografía local
    "arroyo sagastume",
    "arroyo nogoyá",
    "laguna del pescado",
    "médano a médano",
    "delta entrerriano",
]


# ── Instituciones locales reconocidas que actúan como ancla fuerte ─────────────
LOCAL_INSTITUTIONS = [
    "municipalidad de villa paranacito",
    "intendente de paranacito",
    "municipio de paranacito",
    "hospital de paranacito",
    "hospital local",
    "bomberos voluntarios de paranacito",
    "escuela secundaria n° 2",
    "escuela secundaria n",
    "instituto superior de paranacito",
    "club isleños independientes",
    "club atlético isleños",
    "prefectura naval paranacito",
    "jefatura departamental islas",
    "policía departamental islas",
    "defensa civil paranacito",
    "vialidad paranacito",
    "cooperativa paranacito",
]

# ── Palabras que deben OBLIGAR revisión humana antes de publicar ──────────────
ALWAYS_REQUIRES_REVIEW = [
    "fallecimiento", "fallecida", "fallecido", "muerto", "muertos", "víctima", "victima",
    "homicidio", "femicidio", "abuso", "violación", "violacion",
    "denuncia penal", "imputado", "condenado", "condena",
]

# ── Términos de exclusión TERMINANTE (descarta automáticamente falsos positivos) ─
# Evita noticias sobre individuos con apodo "Paranacito" o hechos en GBA/Conurbano
STRICT_EXCLUDE_TERMS = [
    "alias 'paranacito'", 'alias "paranacito"', "alias paranacito",
    "apodado 'paranacito'", 'apodado "paranacito"', "apodado paranacito",
    "conocido como 'paranacito'", 'conocido como "paranacito"',
    "florencio varela", "quilmes", "conurbano", "gran buenos aires", "gba",
    "la matanza", "lomas de zamora", "lanús", "avellaneda", "morón", "san martín",
]


# ── Palabras que INVALIDAN la publicación automática como ALERTA ──────────────
# Solo son alertas reales las crisis hídricas con datos concretos del río Paranacito.
VALID_ALERT_TRIGGERS = [
    "alerta naranja",
    "alerta roja",
    "evacuación",
    "evacuacion",
    "crecida del río paranacito",
    "crecida del rio paranacito",
    "inundación en villa paranacito",
    "inundacion en villa paranacito",
    "nivel del río paranacito",
    "corte de ruta",
    "emergencia hídrica",
    "emergencia hidrica",
]

# ── Fuentes confiables que aumentan la calidad ────────────────────────────────
HIGH_CONFIDENCE_SOURCES = [
    "prefectura", "municipalidad", "municipio", "gobierno de entre ríos", "gobierno de entre rios",
    "ministerio", "policia", "policía", "inta", "senasa", "ina ",
    "bomberos", "defensa civil",
]

MEDIUM_CONFIDENCE_SOURCES = [
    "r2820", "diario el argentino", "el argentino", "diario el día", "el dia",
    "voz isleña", "voz islena", "maxima online", "maximaonline",
    "entre ríos ahora", "entre rios ahora", "mirador provincial", "apfdigital",
    "ceibasnoticias", "ceibas noticias",
]

# ── Fuentes que señalan contenido de baja confiabilidad ──────────────────────
LOW_CONFIDENCE_SIGNALS = [
    "gdelt", "google news", "google alert", "twitter", "facebook",
    "redes sociales", "se dice", "versiones", "trascendió", "trascendio",
    "habría", "habria", "se estima", "proyecciones indican",
]


def assess_quality(rewritten: dict, raw_article: dict, source_name: str) -> dict:
    """
    Evalúa la calidad editorial de una noticia y devuelve una decisión de publicación.

    Returns:
        dict: {
            "publish": bool,          # True si debe publicarse automáticamente
            "requires_review": bool,  # True si debe ir a revisión humana
            "is_alert": bool,         # True solo si es emergencia verificada
            "confidence": str,        # "Alta" | "Media" | "Baja"
            "reason": str,            # Razón de la decisión (para logs)
        }
    """
    titulo = (rewritten.get("titulo") or "").lower()
    copete = (rewritten.get("copete") or "").lower()
    cuerpo = " ".join(rewritten.get("cuerpo") or []).lower()
    source = (source_name or "").lower()
    url = (raw_article.get("url") or "").lower()

    full_text = f"{titulo} {copete} {cuerpo}"
    title_and_lead = f"{titulo} {copete}"

    # ── 0. Descarte inmediato por falsos positivos (apodos, GBA, etc.) ─────────
    for exclude_term in STRICT_EXCLUDE_TERMS:
        if exclude_term in full_text:
            return {
                "publish": False, "requires_review": False, "is_alert": False,
                "confidence": "Baja",
                "reason": f"Falso positivo descartado automáticamente: contiene '{exclude_term}'."
            }

    # ── 1. Verificar ancla geográfica FUERTE en título/copete ─────────────────
    has_strong_anchor_in_lead = any(anchor in title_and_lead for anchor in STRONG_LOCAL_ANCHORS)
    has_institution_in_lead = any(inst in title_and_lead for inst in LOCAL_INSTITUTIONS)
    has_strong_anchor_in_body = any(anchor in full_text for anchor in STRONG_LOCAL_ANCHORS)

    if not has_strong_anchor_in_lead and not has_institution_in_lead:
        if not has_strong_anchor_in_body:
            return {
                "publish": False, "requires_review": False, "is_alert": False,
                "confidence": "Baja",
                "reason": "Sin ancla geográfica explícita en título, copete ni cuerpo."
            }
        # Ancla solo en el cuerpo → va a revisión, no descarte
        return {
            "publish": False, "requires_review": True, "is_alert": False,
            "confidence": "Media",
            "reason": "Ancla geográfica solo en el cuerpo (no en título/copete). Requiere revisión."
        }

    # ── 2. Siempre requiere revisión (contenido sensible) ──────────────────────
    for term in ALWAYS_REQUIRES_REVIEW:
        if term in full_text:
            return {
                "publish": False, "requires_review": True, "is_alert": False,
                "confidence": "Media",
                "reason": f"Contenido sensible detectado: '{term}'. Requiere revisión humana."
            }

    # ── 3. Determinar confiabilidad por fuente ────────────────────────────────
    confidence = "Media"
    if any(k in source for k in HIGH_CONFIDENCE_SOURCES):
        confidence = "Alta"
    elif any(k in source for k in LOW_CONFIDENCE_SIGNALS):
        confidence = "Baja"
    elif any(k in source for k in MEDIUM_CONFIDENCE_SOURCES):
        confidence = "Media"

    if any(sig in full_text for sig in LOW_CONFIDENCE_SIGNALS):
        confidence = "Baja"

    # ── 4. Decidir publicación según confiabilidad ────────────────────────────
    if confidence == "Baja":
        return {
            "publish": False, "requires_review": True, "is_alert": False,
            "confidence": "Baja",
            "reason": "Fuente o contenido de baja confiabilidad. Requiere revisión."
        }

    # ── 5. Evaluar si es ALERTA real ──────────────────────────────────────────
    is_alert = any(trigger in full_text for trigger in VALID_ALERT_TRIGGERS)

    # Si la IA marcó es_alerta pero no hay trigger real → no es alerta
    # (Evita alertas sobre "El Niño en general" o "crecidas nacionales")
    if is_alert and not any(trigger in title_and_lead for trigger in VALID_ALERT_TRIGGERS):
        is_alert = False  # Alerta solo si aparece en título o copete, no solo en el cuerpo

    # ── 6. Publicación automática ─────────────────────────────────────────────
    # Solo se publica automáticamente si:
    #   - Hay ancla fuerte en título/copete
    #   - La fuente es Media o Alta confiabilidad
    #   - No tiene contenido sensible

    return {
        "publish": True,
        "requires_review": False,
        "is_alert": is_alert,
        "confidence": confidence,
        "reason": f"Publicación automática aprobada. Ancla: ✓ Fuente: {source_name} ({confidence})"
    }


def is_worth_fetching(raw_title: str, raw_summary: str, source_url: str) -> bool:
    """
    Filtro previo a la descarga del artículo completo.
    Si no pasa este filtro, no se descarga ni se usa crédito de IA.
    """
    combined = f"{raw_title} {raw_summary}".lower()

    # Descartar inmediatamente si contiene términos de exclusión estricta
    if any(exclude in combined for exclude in STRICT_EXCLUDE_TERMS):
        return False

    # Debe tener ancla local en el título o resumen crudo
    has_anchor = any(anchor in combined for anchor in STRONG_LOCAL_ANCHORS)
    has_institution = any(inst in combined for inst in LOCAL_INSTITUTIONS)

    return has_anchor or has_institution



def sanitize_alert_status(titulo: str, copete: str, es_alerta_propuesto: bool) -> bool:
    """
    Valida que el estado de ALERTA sea justificado.
    Devuelve True solo si hay una alerta hídrica o de seguridad REAL y CONCRETA.
    """
    if not es_alerta_propuesto:
        return False
    combined = f"{titulo} {copete}".lower()
    return any(trigger in combined for trigger in VALID_ALERT_TRIGGERS)
