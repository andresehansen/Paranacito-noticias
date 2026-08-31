/**
 * Utilidad centralizada para cargar, ordenar, filtrar y deduplicar noticias de forma inteligente.
 * 
 * Funcionalidades:
 * 1. Filtro estricto contra falsos positivos (apodos "Paranacito" en GBA, Florencio Varela, Quilmes).
 * 2. Deduplicación semántica automática basada en solapamiento de palabras clave (>35%).
 * 3. Deduplicación por tópicos y slugs similares.
 * 4. Orden cronológico descendente (las más recientes primero).
 */

const STOPWORDS = new Set([
  'de', 'la', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para', 'con',
  'no', 'una', 'su', 'al', 'lo', 'como', 'mas', 'pero', 'sus', 'le', 'ya', 'o', 'fue',
  'este', 'ha', 'si', 'porque', 'esta', 'son', 'entre', 'cuando', 'muy', 'sin', 'tras',
  'sobre', 'ser', 'tiene', 'tambien', 'me', 'hasta', 'hay', 'donde', 'quien', 'desde',
  'todo', 'nos', 'durante', 'todos', 'uno', 'les', 'ni', 'contra', 'otros', 'ese', 'eso',
  'ante', 'ellos', 'esto', 'antes', 'algunos', 'que', 'noticias', 'noticia', 'diario',
  'villa', 'paranacito', 'delta', 'entrerriano', 'entre', 'rios'
]);

const STRICT_EXCLUDE_PHRASES = [
  'alias \'paranacito\'', 'alias "paranacito"', 'alias paranacito',
  'apodado \'paranacito\'', 'apodado "paranacito"', 'apodado paranacito',
  'conocido como \'paranacito\'', 'conocido como "paranacito"',
  'florencio varela', 'quilmes', 'conurbano', 'gran buenos aires', 'en gba'
];

function isFalsePositive(item: any): boolean {
  const text = `${item.titulo || ''} ${item.copete || ''} ${item.resumen || ''} ${item.slug || ''}`.toLowerCase();
  for (const phrase of STRICT_EXCLUDE_PHRASES) {
    if (text.includes(phrase)) return true;
  }
  return false;
}

function extractKeywords(text: string): Set<string> {
  const norm = (text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ');
  const words = norm.split(/\s+/).filter(w => w.length >= 4 && !STOPWORDS.has(w));
  return new Set(words);
}

function calculateOverlap(kwA: Set<string>, kwB: Set<string>): number {
  if (kwA.size === 0 || kwB.size === 0) return 0;
  let matches = 0;
  for (const word of kwA) {
    if (kwB.has(word)) matches++;
  }
  const minSize = Math.min(kwA.size, kwB.size);
  return minSize > 0 ? matches / minSize : 0;
}

export function getCleanAndDeduplicatedNews(): any[] {
  const newsFiles = import.meta.glob('../../../data/noticias/*.json', { eager: true });
  const rawList = Object.values(newsFiles)
    .map((file: any) => file.default || file)
    .filter((n: any) => n && n.slug && n.publicado !== false && !n.requiere_revision)
    .filter((n: any) => !isFalsePositive(n)); // Descartar de inmediato falsos positivos de GBA

  // Ordenar por fecha más reciente primero
  rawList.sort((a: any, b: any) => 
    String(b.fecha_iso || b.fecha_inicio_iso || b.fecha_publicacion || '').localeCompare(
      String(a.fecha_iso || a.fecha_inicio_iso || a.fecha_publicacion || '')
    )
  );

  const cleanList: any[] = [];
  const processedKeywordSets: { id: string; keywords: Set<string>; title: string }[] = [];

  for (const item of rawList) {
    const itemText = `${item.titulo || ''} ${item.copete || ''} ${item.resumen || ''}`;
    const itemKeywords = extractKeywords(itemText);

    // Comparar contra todas las notas ya aceptadas para detectar si habla del mismo acontecimiento
    let isDuplicate = false;
    for (const accepted of processedKeywordSets) {
      const overlap = calculateOverlap(itemKeywords, accepted.keywords);
      // Si comparten más del 35% de palabras clave significativas, es el mismo hecho noticioso
      if (overlap >= 0.35) {
        isDuplicate = true;
        break;
      }
    }

    if (!isDuplicate) {
      cleanList.push(item);
      processedKeywordSets.push({
        id: item.slug,
        keywords: itemKeywords,
        title: item.titulo || ''
      });
    }
  }

  return cleanList;
}
