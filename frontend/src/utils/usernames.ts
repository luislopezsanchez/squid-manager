// Los nombres de usuario del proxy no admiten espacios ni acentos (regex del
// backend: ^[A-Za-z0-9._-]{1,64}$, ver USERNAME_PATTERN en proxy_users.py).
// A diferencia de un nombre de ACL, sí conserva mayúsculas -Squid es
// sensible a mayúsculas/minúsculas en las credenciales, así que forzarlas a
// minúsculas cambiaría el usuario y la contraseña con los que se autentica
// de verdad. Se normaliza en vivo mientras se escribe, mismo criterio que
// normalizarNombreAcl (ver aclNames.ts).
export function normalizarUsername(texto: string): string {
  return texto
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^A-Za-z0-9._-]+/g, '')
    .slice(0, 64)
}
