"""
test_quality_gate.py — Test autocontenido del sistema de filtrado
No requiere Gemini ni conexión a internet para las pruebas de lógica.
Solo necesita: feedparser, requests (para el test real de Ceibas)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from news_radar import clean_text, is_locally_relevant
from quality_gate import is_worth_fetching, assess_quality, sanitize_alert_status

# ─── Test 1: Filtro geográfico ────────────────────────────────────────────────
print("\n" + "="*60)
print("TEST 1: Filtro geográfico is_locally_relevant()")
print("="*60)

casos = [
    ("Roban bicicletas en Ceibas",                       "ceibas", True),
    ("Noticias de Villa Paranacito",                     "",        True),
    ("El Niño se fortalece en Argentina",                "",        False),
    ("Inundaciones en Santa Fe capital",                 "",        False),
    ("Bomberos de Paranacito atienden emergencia",       "",        True),
    ("Obras en Islas del Ibicuy",                        "",        True),
    ("Noticias de Corrientes",                           "",        False),
    ("Hospital de Villa Paranacito suma equipamiento",   "",        True),
    ("Cazadores furtivos detenidos en Delta entrerriano","",        True),
]

ok_count = 0
for titulo, extra, esperado in casos:
    resultado = is_locally_relevant(titulo, extra)
    icono = "✅" if resultado == esperado else "❌ FALLO"
    status = "PASA" if resultado else "NO pasa"
    print(f"  {icono}  {status} | '{titulo}'")
    if resultado == esperado:
        ok_count += 1

print(f"\n  → {ok_count}/{len(casos)} correctos\n")


# ─── Test 2: Pre-gate (is_worth_fetching) ────────────────────────────────────
print("="*60)
print("TEST 2: Pre-gate is_worth_fetching()")
print("="*60)

casos2 = [
    ("Roban bicicletas en Ceibas",                              "", True),
    ("Operativo sanitario fluvial en Villa Paranacito",         "", True),
    ("El Niño y las lluvias en Argentina",                      "", False),
    ("Club Isleños Independientes suma triunfos",               "", True),
    ("Hospital de Ibicuy incorpora nuevo equipamiento",         "", True),
    ("Noticias nacionales",                                     "", False),
]

ok_count2 = 0
for titulo, summary, esperado in casos2:
    resultado = is_worth_fetching(titulo, summary, "")
    icono = "✅" if resultado == esperado else "❌ FALLO"
    status = "PASA" if resultado else "NO pasa"
    print(f"  {icono}  {status} | '{titulo}'")
    if resultado == esperado:
        ok_count2 += 1

print(f"\n  → {ok_count2}/{len(casos2)} correctos\n")


# ─── Test 3: Quality Gate post-IA ────────────────────────────────────────────
print("="*60)
print("TEST 3: Quality Gate assess_quality()")
print("="*60)

nota_buena = {
    "titulo": "Bomberos Voluntarios de Villa Paranacito Renuevan Equipamiento",
    "copete": "La institución local recibió un subsidio municipal para adquirir nuevas herramientas de rescate en Villa Paranacito.",
    "cuerpo": ["Los bomberos voluntarios de Villa Paranacito celebraron hoy la entrega de equipamiento..."],
    "categoria": "Comunidad"
}
raw_buena = {"url": "https://ceibasnoticias.com.ar/bomberos", "source_name": "Ceibas Noticias"}
gate1 = assess_quality(nota_buena, raw_buena, "Ceibas Noticias")
print(f"  Nota BUENA: publish={gate1['publish']}, review={gate1['requires_review']}, conf={gate1['confidence']}")
print(f"    → {gate1['reason']}")

nota_generica = {
    "titulo": "El Fenómeno El Niño se Fortalece en Argentina con Alta Probabilidad",
    "copete": "Las últimas proyecciones confirman un evento hidrológico de gran magnitud en la región del Litoral.",
    "cuerpo": ["Las autoridades meteorológicas reportaron..."],
    "categoria": "Río y Clima"
}
raw_generica = {"url": "https://infobae.com/123", "source_name": "Infobae"}
gate2 = assess_quality(nota_generica, raw_generica, "Infobae")
print(f"\n  Nota GENÉRICA: publish={gate2['publish']}, review={gate2['requires_review']}, conf={gate2['confidence']}")
print(f"    → {gate2['reason']}")

nota_sensible = {
    "titulo": "Detenido por agresión en Villa Paranacito",
    "copete": "Un vecino de Villa Paranacito fue detenido luego de una denuncia penal por violencia.",
    "cuerpo": ["La Policía departamental intervino..."],
    "categoria": "Sociedad"
}
raw_sensible = {"url": "https://ceibasnoticias.com.ar/deten", "source_name": "Ceibas Noticias"}
gate3 = assess_quality(nota_sensible, raw_sensible, "Ceibas Noticias")
print(f"\n  Nota SENSIBLE: publish={gate3['publish']}, review={gate3['requires_review']}, conf={gate3['confidence']}")
print(f"    → {gate3['reason']}")


# ─── Test 4: Validación de alertas ───────────────────────────────────────────
print("\n" + "="*60)
print("TEST 4: sanitize_alert_status()")
print("="*60)

alertas = [
    ("Alerta naranja en el Río Paranacito", "El nivel del río supera la cota de alerta naranja.", True, True),
    ("El Niño se fortalece en el país",     "Alta probabilidad de crecidas.",                   True, False),
    ("Traslado de hacienda por El Niño",    "Productores trasladan ganado a zonas altas.",       True, False),
    ("Crecida del Río Paranacito inunda",   "Evacuación de familias en Villa Paranacito.",       True, True),
]

for titulo, copete, propuesto, esperado in alertas:
    resultado = sanitize_alert_status(titulo, copete, propuesto)
    icono = "✅" if resultado == esperado else "❌ FALLO"
    print(f"  {icono}  ALERTA={resultado} (esperado={esperado}) | '{titulo}'")


# ─── Test 5: Feed real de Ceibas (requiere internet) ─────────────────────────
print("\n" + "="*60)
print("TEST 5: Feed REAL de Ceibas Noticias")
print("="*60)

try:
    import feedparser
    feed = feedparser.parse("https://ceibasnoticias.com.ar/feed/")
    print(f"  Items en el feed: {len(feed.entries)}")

    aprobados = []
    rechazados = []

    for entry in feed.entries:
        title = clean_text(entry.get("title", ""))
        summary = clean_text(entry.get("summary", ""))
        link = entry.get("link", "")

        local_ok = is_locally_relevant(title, summary)
        worth = is_worth_fetching(title, summary, link)

        if local_ok and worth:
            aprobados.append(title)
        else:
            rechazados.append(title)

    print(f"\n  ✅ APROBADAS para scraping ({len(aprobados)}):")
    for t in aprobados:
        print(f"    • {t[:75]}")

    print(f"\n  ❌ DESCARTADAS ({len(rechazados)}):")
    for t in rechazados:
        print(f"    • {t[:75]}")

    total = len(feed.entries)
    print(f"\n  RESUMEN: {len(aprobados)} aprobadas de {total} ({100*len(aprobados)//total if total else 0}%)")

except ImportError:
    print("  feedparser no disponible para test 5")
except Exception as e:
    print(f"  Error en test 5: {e}")

print("\n" + "="*60)
print("TESTS COMPLETOS")
print("="*60 + "\n")
