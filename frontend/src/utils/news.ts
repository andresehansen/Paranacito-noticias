/**
 * Utilidad centralizada para cargar, ordenar y deduplicar noticias
 * Garantiza que la portada, categorías y redactor nunca muestren notas repetidas sobre el mismo tema.
 */

export function getCleanAndDeduplicatedNews(): any[] {
  const newsFiles = import.meta.glob('../../../data/noticias/*.json', { eager: true });
  const rawList = Object.values(newsFiles)
    .map((file: any) => file.default || file)
    .filter((n: any) => n && n.slug && n.publicado !== false && !n.requiere_revision);

  // Ordenar por fecha más reciente primero
  rawList.sort((a: any, b: any) => 
    String(b.fecha_iso || b.fecha_inicio_iso || '').localeCompare(String(a.fecha_iso || a.fecha_inicio_iso || ''))
  );

  const seenTopics = new Set<string>();
  const seenSlugs = new Set<string>();
  const cleanList: any[] = [];

  // Tópicos y entidades clave para evitar notas duplicadas
  const topicPatterns = [
    { id: 'amparito', regex: /amparito|profuga/i },
    { id: 'hacienda', regex: /hacienda|ganad|retiran.*ganado/i },
    { id: 'cazadores', regex: /cazador|furtiv|visor.*termic/i },
    { id: 'hospital', regex: /hospital.*paranacito|obras.*hospital/i },
    { id: 'enfermeria', regex: /enfermeria|concurso.*docente/i },
    { id: 'frigerio', regex: /frigerio/i },
    { id: 'bomberos', regex: /bomberos.*voluntarios/i },
    { id: 'camino_acceso', regex: /mantenimiento.*camino|vialidad.*camino/i },
    { id: 'futbol_islenos', regex: /islenos.*independientes|torneo.*futbol/i },
    { id: 'turismo_pesca', regex: /turismo.*pesca|reservas.*turismo/i },
    { id: 'operativo_sanitario', regex: /operativo.*sanitario.*fluvial/i },
    { id: 'rio_estable', regex: /altura.*estable.*pronostico/i }
  ];

  for (const item of rawList) {
    if (seenSlugs.has(item.slug)) continue;

    const fullText = `${item.titulo || ''} ${item.copete || ''} ${item.slug || ''}`.toLowerCase();
    let matchedTopic: string | null = null;

    for (const t of topicPatterns) {
      if (t.regex.test(fullText)) {
        matchedTopic = t.id;
        break;
      }
    }

    if (matchedTopic) {
      if (seenTopics.has(matchedTopic)) {
        // Ya incluimos la versión más reciente de este tema -> ignorar duplicado viejo
        continue;
      }
      seenTopics.add(matchedTopic);
    }

    seenSlugs.add(item.slug);
    cleanList.push(item);
  }

  return cleanList;
}
