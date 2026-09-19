// Los nombres de ACL de Squid no admiten espacios, mayúsculas ni acentos
// (regex del backend: ^[A-Za-z][A-Za-z0-9_-]{0,63}$, ver squid_names.py).
// En vez de dejar que el admin escriba "Redes Sociales" y recién enterarse
// del error al guardar, se normaliza en vivo mientras escribe -mismo patrón
// que un campo de "slug" de URL en cualquier CMS.
export function normalizarNombreAcl(texto: string): string {
  return texto
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^[^a-z]+/, '')
    .replace(/_+$/, '')
    .slice(0, 64)
}
