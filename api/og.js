/**
 * Vercel Serverless Function: /api/og
 * 
 * Genera imágenes Open Graph dinámicas en alta definición (1200x630)
 * para compartir noticias en WhatsApp, Facebook y Twitter con vista previa profesional.
 */

function escapeXml(unsafe) {
  return String(unsafe || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function wrapText(text, maxCharsPerLine = 35, maxLines = 3) {
  const words = (text || 'Paranacito Noticias | Feed en Vivo del Delta').split(' ');
  const lines = [];
  let currentLine = '';

  for (const word of words) {
    if ((currentLine + ' ' + word).trim().length <= maxCharsPerLine) {
      currentLine = (currentLine + ' ' + word).trim();
    } else {
      if (currentLine) lines.push(currentLine);
      currentLine = word;
      if (lines.length >= maxLines - 1) break;
    }
  }
  if (currentLine && lines.length < maxLines) {
    lines.push(currentLine);
  }
  return lines;
}

export default function handler(req, res) {
  const { title = 'Paranacito Noticias', cat = 'Comunidad', source = 'Prensa Local' } = req.query;

  const cleanTitle = escapeXml(title);
  const cleanCat = escapeXml(cat.toUpperCase());
  const cleanSource = escapeXml(source);
  const titleLines = wrapText(cleanTitle, 32, 3);

  const isAlert = cleanCat.includes('ALERTA') || cleanCat.includes('URGENTE');
  const catColor = isAlert ? '#e11d48' : '#0284c7';
  const catBg = isAlert ? '#ffe4e6' : '#e0f2fe';

  const svg = `
  <svg width="1200" height="630" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#091427"/>
        <stop offset="60%" stop-color="#0f2b46"/>
        <stop offset="100%" stop-color="#0284c7"/>
      </linearGradient>
      <linearGradient id="overlayGrad" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="rgba(0,0,0,0.85)"/>
        <stop offset="100%" stop-color="rgba(0,0,0,0.2)"/>
      </linearGradient>
    </defs>

    <!-- Fondo Degradado Delta -->
    <rect width="1200" height="630" fill="url(#bgGrad)"/>

    <!-- Ondas del Río sutiles de fondo -->
    <path d="M0 450 Q 300 410, 600 460 T 1200 430 L 1200 630 L 0 630 Z" fill="rgba(2, 132, 199, 0.25)"/>
    <path d="M0 490 Q 300 460, 600 500 T 1200 480 L 1200 630 L 0 630 Z" fill="rgba(3, 105, 161, 0.35)"/>

    <!-- Tarjeta Central de Cristal -->
    <rect x="60" y="60" width="1080" height="510" rx="32" fill="rgba(15, 23, 42, 0.75)" stroke="rgba(255, 255, 255, 0.15)" stroke-width="2"/>

    <!-- Cabecera / Marca -->
    <g transform="translate(100, 110)">
      <!-- Logo Icono -->
      <rect width="48" height="48" rx="14" fill="#0284c7"/>
      <text x="24" y="32" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="24" fill="#ffffff" text-anchor="middle">🌊</text>
      
      <!-- Nombre del Sitio -->
      <text x="64" y="33" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="26" font-weight="900" fill="#ffffff" letter-spacing="-0.5">
        Paranacito<tspan fill="#38bdf8">Noticias</tspan>
      </text>

      <!-- Badge de Categoría -->
      <rect x="740" y="4" width="${cleanCat.length * 13 + 30}" height="40" rx="20" fill="${catBg}" />
      <text x="${740 + (cleanCat.length * 13 + 30)/2}" y="29" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="800" fill="${catColor}" text-anchor="middle">
        ${cleanCat}
      </text>
    </g>

    <!-- Línea Divisoria -->
    <line x1="100" y1="180" x2="1100" y2="180" stroke="rgba(255, 255, 255, 0.1)" stroke-width="1.5"/>

    <!-- Titular de la Noticia -->
    <g transform="translate(100, 260)">
      ${titleLines.map((line, i) => `
        <text x="0" y="${i * 68}" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="48" font-weight="900" fill="#ffffff" letter-spacing="-0.8">
          ${line}
        </text>
      `).join('')}
    </g>

    <!-- Pie de Página / Metadatos -->
    <g transform="translate(100, 510)">
      <text x="0" y="0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="18" font-weight="600" fill="#94a3b8">
        📍 Villa Paranacito, Ceibas e Islas del Ibicuy
      </text>
      <text x="1000" y="0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="18" font-weight="700" fill="#38bdf8" text-anchor="end">
        paranacito-noticias.vercel.app ↗
      </text>
    </g>
  </svg>
  `;

  res.setHeader('Content-Type', 'image/svg+xml');
  res.setHeader('Cache-Control', 'public, max-age=86400, stale-while-revalidate=43200');
  return res.status(200).send(svg.trim());
}
