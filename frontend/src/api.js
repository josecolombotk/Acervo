// Cliente de la API REST. Lanza Error con el mensaje del backend para mostrarlo al usuario.
// La cabecera X-Requested-With es exigida por el backend en POST/PUT/DELETE (defensa contra CSRF).
export async function api(path, method = 'GET', body) {
  let r;
  try {
    r = await fetch('/api' + path, { method, headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'acervo' }, body: body ? JSON.stringify(body) : undefined });
  } catch { throw new Error('No se pudo conectar con el servidor. Verifique que el backend esté iniciado.'); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || 'Error inesperado');
  return d;
}
