import { getCleanAndDeduplicatedNews } from '../utils/news';

export async function GET() {
  const news = getCleanAndDeduplicatedNews();
  const siteUrl = 'https://paranacito-noticias.vercel.app';

  const itemsXml = news.map((item: any) => `
    <item>
      <title><![CDATA[${item.titulo || ''}]]></title>
      <link>${siteUrl}/</link>
      <guid isPermaLink="false">${item.slug || item.id || ''}</guid>
      <description><![CDATA[${item.copete || item.resumen || ''}]]></description>
      <category>${item.categoria || 'Comunidad'}</category>
      <pubDate>${new Date(item.fecha_iso || item.fecha_inicio_iso || Date.now()).toUTCString()}</pubDate>
    </item>
  `).join('');

  const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Paranacito Noticias | Feed en Vivo del Delta</title>
    <link>${siteUrl}</link>
    <description>Noticias e información en vivo de Villa Paranacito, Ceibas y el Delta Entrerriano.</description>
    <language>es-AR</language>
    <atom:link href="${siteUrl}/rss.xml" rel="self" type="application/rss+xml"/>
    ${itemsXml}
  </channel>
</rss>`.trim();

  return new Response(rss, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600'
    }
  });
}
