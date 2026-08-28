import type { APIRoute } from 'astro';

export const prerender = false; // Este endpoint es dinámico (server-side)

const GH_REPO = 'andresehansen/Paranacito-noticias';
const GH_BRANCH = 'main';

function getEnv(key: string): string {
  return process.env[key] || import.meta.env[key] || '';
}

async function ghFetch(path: string, method: string, token: string, body?: object) {
  const url = `https://api.github.com/repos/${GH_REPO}/contents/${path}`;
  const res = await fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
      'User-Agent': 'Paranacito-Noticias-Editor/1.0',
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || `GitHub ${res.status}`);
  return data;
}

function toBase64(str: string): string {
  // Encode UTF-8 safely
  const bytes = new TextEncoder().encode(str);
  let binary = '';
  bytes.forEach(b => binary += String.fromCharCode(b));
  return btoa(binary);
}

export const POST: APIRoute = async ({ request }) => {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
  };

  try {
    const body = await request.json();
    const { action, pin, payload } = body;

    // ── Validar PIN ──────────────────────────────────────────────────
    const adminPin = getEnv('ADMIN_PIN') || '0453';
    if (!pin || pin !== adminPin) {
      return new Response(JSON.stringify({ ok: false, error: 'PIN incorrecto.' }), {
        status: 401, headers: corsHeaders,
      });
    }

    // ── Obtener token de GitHub ──────────────────────────────────────
    const token = getEnv('GITHUB_TOKEN');
    if (!token) {
      return new Response(JSON.stringify({
        ok: false,
        error: 'GITHUB_TOKEN no configurado en las variables de entorno de Vercel.'
      }), { status: 500, headers: corsHeaders });
    }

    // ── Ejecutar acción ──────────────────────────────────────────────
    if (action === 'save') {
      // Crear o actualizar un archivo de noticia
      const { filename, content } = payload;
      if (!filename || !content) throw new Error('Faltan filename o content.');

      const path = `data/noticias/${filename}`;
      const jsonStr = JSON.stringify(content, null, 2);

      // Intentar obtener el SHA existente (para actualizar en vez de crear)
      let sha: string | undefined;
      try {
        const existing = await ghFetch(path, 'GET', token);
        sha = existing?.sha;
      } catch {
        // El archivo no existe aún → se crea nuevo
      }

      await ghFetch(path, 'PUT', token, {
        message: `${sha ? 'Editar' : 'Publicar'}: ${content.slug || filename}`,
        content: toBase64(jsonStr),
        branch: GH_BRANCH,
        ...(sha ? { sha } : {}),
      });

      return new Response(JSON.stringify({ ok: true, action: sha ? 'updated' : 'created' }), {
        status: 200, headers: corsHeaders,
      });
    }

    if (action === 'delete') {
      const { filename } = payload;
      if (!filename) throw new Error('Falta filename.');

      const path = `data/noticias/${filename}`;
      const existing = await ghFetch(path, 'GET', token);
      if (!existing?.sha) throw new Error('No se encontró el archivo en GitHub.');

      await ghFetch(path, 'DELETE', token, {
        message: `Eliminar: ${filename}`,
        sha: existing.sha,
        branch: GH_BRANCH,
      });

      return new Response(JSON.stringify({ ok: true, action: 'deleted' }), {
        status: 200, headers: corsHeaders,
      });
    }

    return new Response(JSON.stringify({ ok: false, error: `Acción desconocida: ${action}` }), {
      status: 400, headers: corsHeaders,
    });

  } catch (err: any) {
    return new Response(JSON.stringify({ ok: false, error: err.message || 'Error interno.' }), {
      status: 500, headers: corsHeaders,
    });
  }
};

// Responder preflight CORS
export const OPTIONS: APIRoute = async () => {
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
};
