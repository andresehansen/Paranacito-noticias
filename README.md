# 🌊 Paranacito Noticias

**Portal Web de Noticias Comunitarias para Villa Paranacito (Entre Ríos, Argentina)**  
100% Automatizado, Serverless, Adaptado al Delta y de Costo $0/mes.

---

## 🌟 Características Principales

- **Automatización 100% Gratuita**: Pipeline programado con GitHub Actions cada 4 horas.
- **Monitoreo del Río y Clima**: Escala hidrométrica en tiempo real (altura del Río Paranacito, alertas de crecida y bajante) + pronóstico meteorológico con Open-Meteo (sin límite ni costo).
- **Parafraseo y Contextualización con IA**: Procesamiento mediante **Google Gemini 2.5 Flash API (Free Tier)** para redactar noticias claras, neutrales y adaptadas al vecino isleño.
- **Acceso Rápido y Fácil de Tipear**:
  - URLs limpias y legibles: `/noticias/titulo-amigable` y `/clima`.
  - **PWA (Progressive Web App)**: Los usuarios pueden instalar el portal como una App nativa en su celular con 1 solo toque desde el navegador, sin necesidad de tipear la dirección web en el futuro.
  - **Botón de WhatsApp integrado**: Para compartir novedades y alertas hidrológicas en grupos de vecinos con 1 click.
- **Transparencia y Ética Periodística**: Cada noticia parafraseada incluye la atribución destacada y enlace a su fuente original.
- **Git como Base de Datos**: No requiere servidores de bases de datos externos que se suspendan por inactividad. Los datos se almacenan en archivos JSON versionados.

---

## 🏗️ Estructura del Repositorio

```
Paranacito Noticias/
├── .github/
│   └── workflows/
│       └── scraper_cron.yml          # Automatización de GitHub Actions
├── scraper/                          # Pipeline de Ingestión en Python
│   ├── config.py                     # Configuración de feeds, fuentes y coordenadas
│   ├── weather_river.py              # Extractor de Clima (Open-Meteo) y Altura del Río
│   ├── sources_extractor.py          # Extractor de Google Alerts y medios provinciales
│   ├── ai_rewriter.py                # Reescritor con Google Gemini API
│   ├── storage.py                    # Persistencia y control de duplicados
│   ├── main.py                       # Orquestador del pipeline
│   └── requirements.txt              # Dependencias de Python
├── data/                             # Base de datos JSON en Git
│   ├── noticias/                     # Noticias procesadas (.json)
│   ├── clima_actual.json             # Última lectura de clima y río
│   ├── noticias_index.json           # Índice cronológico ligero
│   └── processed_history.json        # Registro de URLs procesadas
├── frontend/                         # Portal Web en Astro + Tailwind CSS
│   ├── public/
│   │   ├── manifest.json             # Configuración PWA
│   │   ├── favicon.svg               # Ícono del portal
│   │   └── robots.txt
│   ├── src/
│   │   ├── components/               # Header, WeatherWidget, NewsCard, WhatsApp, Footer
│   │   ├── layouts/Layout.astro      # Layout base con OpenGraph para WhatsApp
│   │   └── pages/                    # Portada, [slug], [categoria], clima
│   ├── astro.config.mjs
│   └── package.json
└── README.md
```

---

## 🚀 Guía de Puesta en Marcha (Paso a Paso)

### 1. Obtener la clave gratuita de Google Gemini
1. Ingresá en [Google AI Studio](https://aistudio.google.com/).
2. Iniciá sesión con tu cuenta de Google y hacé clic en **"Get API key"**.
3. Creá una clave nueva y guardala (es gratuita y no requiere tarjeta).

### 2. Configurar la alerta de Google Alerts (RSS)
1. Entrá a [Google Alerts](https://www.google.com/alerts).
2. Escribí en la búsqueda: `"Villa Paranacito" OR "Paranacito"`.
3. Hacé clic en **"Mostrar opciones"**:
   - Frecuencia: *Cuando se produzca*.
   - Fuentes: *Automático*.
   - Entregar en: **Feed RSS** (en lugar de correo).
4. Creá la alerta y copiá la URL del icono RSS naranja que aparece junto a ella.

### 3. Subir el proyecto a GitHub y configurar Secretos
1. Creá un repositorio en GitHub (ej. `paranacito-noticias`) y subí esta carpeta.
2. En GitHub, andá a **Settings > Secrets and variables > Actions**.
3. Agregá los siguientes **Repository Secrets**:
   - `GEMINI_API_KEY`: Tu clave de Google AI Studio.
   - `RSS_GOOGLE_ALERTS_PARANACITO`: La URL del feed RSS de Google Alerts obtenida en el paso 2.

### 4. Desplegar la Web Gratis en Cloudflare Pages o Vercel
1. Ingresá a [Vercel](https://vercel.com/) o [Cloudflare Pages](https://pages.cloudflare.com/) (ambos son 100% gratuitos).
2. Hacé clic en **"Add New Project"** y seleccioná tu repositorio de GitHub.
3. Configuración de Build:
   - **Root Directory**: `frontend`
   - **Framework Preset**: `Astro`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Hacé clic en **"Deploy"**. En ~1 minuto tu sitio web estará online con un subdominio gratuito como:
   - `https://paranacitonoticias.vercel.app` o `https://paranacito.pages.dev`

### 5. Dominio Fácil de Recordar
- **Opción Gratuita**: Los subdominios de Vercel y Cloudflare son limpios y fáciles de tipear (ej: `paranacito.pages.dev`).
- **Opción Dominio Propio (.com.ar)**: Podés registrar `paranacitonoticias.com.ar` o `paranacito.com.ar` en [NIC Argentina](https://nic.ar/) y vincularlo en la configuración de dominio de Vercel/Cloudflare con 2 clics (configurando los registros DNS).

---

## 💻 Desarrollo Local

### Ejecutar el Pipeline de Python manualmente
```bash
# Instalar dependencias
pip install -r scraper/requirements.txt

# Probar actualización de Clima y Río
python scraper/weather_river.py

# Generar noticias de muestra iniciales
python scraper/main.py --seed

# Ejecutar el ciclo completo de ingestión con IA
python scraper/main.py
```

### Ejecutar el Frontend Web
```bash
cd frontend
npm install
npm run dev
```
La web abrirá en `http://localhost:4321`.

---

## 🤝 Créditos y Comunidad

Desarrollado para la comunidad de **Villa Paranacito e Islas del Ibicuy**, Entre Ríos.
Open Source, libre y comunitario.
