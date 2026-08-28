/**
 * Vercel Serverless Function: /api/gh
 * 
 * Maneja operaciones de GitHub (guardar/eliminar noticias) de forma segura.
 * El GITHUB_TOKEN nunca sale del servidor — el browser solo envía el PIN.
 * 
 * Variables de entorno requeridas en Vercel:
 *   GITHUB_TOKEN  — Personal Access Token con scope "repo"
 *   ADMIN_PIN     — PIN del panel de redacción (ej: 0453)
 */

const GH_REPO = 'andresehansen/Paranacito-noticias';
const GH_BRANCH = 'main';

function toBase64(str) {
  return Buffer.from(str, 'utf-8').toString('base64');
}

async function ghFetch(path, method, token, body) {
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
  if (!res.ok) throw new Error(data.message || `GitHub error ${res.status}`);
  return data;
}

export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ ok: false, error: 'Método no permitido.' });
  }

  try {
    const { action, pin, payload } = req.body;

    // ── Validar PIN ────────────────────────────────────────────────
    const adminPin = process.env.ADMIN_PIN || '0453';
    if (!pin || pin !== adminPin) {
      return res.status(401).json({ ok: false, error: 'PIN incorrecto.' });
    }

    // ── Obtener token de GitHub ────────────────────────────────────
    const token = process.env.GITHUB_TOKEN;
    if (!token) {
      return res.status(500).json({
        ok: false,
        error: 'GITHUB_TOKEN no configurado. Agregar en Vercel → Settings → Environment Variables.'
      });
    }

    // ── Acción: save (crear o actualizar) ─────────────────────────
    if (action === 'save') {
      const { filename, content } = payload;
      if (!filename || !content) throw new Error('Faltan filename o content.');

      const path = `data/noticias/${filename}`;
      const jsonStr = JSON.stringify(content, null, 2);

      // Obtener SHA existente para actualizar (o crear si no existe)
      let sha;
      try {
        const existing = await ghFetch(path, 'GET', token);
        sha = existing?.sha;
      } catch {
        // No existe aún → se crea
      }

      await ghFetch(path, 'PUT', token, {
        message: `${sha ? 'Editar' : 'Publicar'}: ${content.slug || filename}`,
        content: toBase64(jsonStr),
        branch: GH_BRANCH,
        ...(sha ? { sha } : {}),
      });

      return res.status(200).json({ ok: true, action: sha ? 'updated' : 'created' });
    }

    // ── Acción: delete ─────────────────────────────────────────────
    if (action === 'delete') {
      const { filename } = payload;
      if (!filename) throw new Error('Falta filename.');

      const path = `data/noticias/${filename}`;
      const existing = await ghFetch(path, 'GET', token);
      if (!existing?.sha) throw new Error('Archivo no encontrado en GitHub.');

      await ghFetch(path, 'DELETE', token, {
        message: `Eliminar: ${filename}`,
        sha: existing.sha,
        branch: GH_BRANCH,
      });

      return res.status(200).json({ ok: true, action: 'deleted' });
    }

    return res.status(400).json({ ok: false, error: `Acción desconocida: ${action}` });

  } catch (err) {
    console.error('[/api/gh] Error:', err.message);
    return res.status(500).json({ ok: false, error: err.message || 'Error interno del servidor.' });
  }
}
