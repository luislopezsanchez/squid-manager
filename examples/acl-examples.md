# Ejemplos de ACLs — SquidManager

Esta guía muestra ejemplos prácticos de cada tipo de ACL y cómo configurarlos desde el panel web.

---

## Flujo correcto

```
Paso 1: Crear ACL → define qué coincide
Paso 2: Crear regla → define allow o deny sobre esa ACL
Paso 3: Aplicar cambios → genera squid.conf y recarga Squid
Paso 4: Probar → curl -x http://usuario:clave@IP:3128 http://sitio
```

> **Importante:** Crear una ACL sin crear una regla no hace nada. La ACL define qué coincide, la regla define qué hacer.

---

## 1. dstdomain — Bloquear/Permitir dominios completos

**Bloquear redes sociales:**

| Campo | Valor |
|-------|-------|
| Nombre | `redes_sociales` |
| Tipo | `dstdomain` |
| Valor | `.facebook.com .twitter.com .instagram.com .tiktok.com .snapchat.com` |

Regla: `deny` → `redes_sociales`

> El punto inicial `.facebook.com` bloquea también subdominios como `m.facebook.com`, `login.facebook.com`, etc.

---

## 2. dstdom_regex — Bloquear por patrón de dominio

**Bloquear cualquier dominio que contenga "social":**

| Campo | Valor |
|-------|-------|
| Nombre | `patron_social` |
| Tipo | `dstdom_regex` |
| Valor | `social` |

Regla: `deny` → `patron_social`

> Bloquearía: `socialmedia.com`, `mysocial.net`, `antisocial.org`

---

## 3. src — Permitir/Bloquear por IP de origen

**Permitir solo una red específica:**

| Campo | Valor |
|-------|-------|
| Nombre | `mi_red` |
| Tipo | `src` |
| Valor | `192.168.1.0/24` |

Regla: `allow` → `mi_red authenticated` (antes del deny all)

---

## 4. dst — Bloquear por IP de destino

**Bloquear acceso a una IP específica:**

| Campo | Valor |
|-------|-------|
| Nombre | `ip_bloqueada` |
| Tipo | `dst` |
| Valor | `10.0.0.5` |

Regla: `deny` → `ip_bloqueada`

---

## 5. url_regex — Bloquear por patrón de URL

**Bloquear descargas de archivos multimedia:**

| Campo | Valor |
|-------|-------|
| Nombre | `videos_descargas` |
| Tipo | `url_regex` |
| Valor | `\.mp4$ \.avi$ \.mkv$ \.mov$ \.wmv$ \.flv$ \.torrent$` |

Regla: `deny` → `videos_descargas`

---

## 6. urlpath_regex — Bloquear rutas específicas

**Bloquear acceso a paneles de administración:**

| Campo | Valor |
|-------|-------|
| Nombre | `rutas_prohibidas` |
| Tipo | `urlpath_regex` |
| Valor | `/admin/ /wp-admin/ /phpmyadmin/ /administrator/` |

Regla: `deny` → `rutas_prohibidas`

---

## 7. port — Restringir puertos de destino

**Bloquear puertos de juegos online:**

| Campo | Valor |
|-------|-------|
| Nombre | `puertos_juegos` |
| Tipo | `port` |
| Valor | `25565 27015 6112 3074 3478` |

Regla: `deny` → `puertos_juegos`

---

## 8. proto — Restringir protocolos

**Solo permitir HTTP y FTP:**

| Campo | Valor |
|-------|-------|
| Nombre | `protocolos_permitidos` |
| Tipo | `proto` |
| Valor | `HTTP FTP` |

Regla: `allow` → `protocolos_permitidos` (antes del deny all)

---

## 9. method — Restringir métodos HTTP

**Bloquear métodos peligrosos:**

| Campo | Valor |
|-------|-------|
| Nombre | `metodos_peligrosos` |
| Tipo | `method` |
| Valor | `PUT DELETE TRACE` |

Regla: `deny` → `metodos_peligrosos`

---

## 10. time — Restringir por horario

**Permitir acceso solo en horario laboral:**

| Campo | Valor |
|-------|-------|
| Nombre | `horario_laboral` |
| Tipo | `time` |
| Valor | `M-F 09:00-17:00` |

Regla: `allow` → `horario_laboral authenticated` (antes del deny all)

**Días de la semana:**
- S = Domingo
- M = Lunes
- T = Martes
- W = Miércoles
- H = Jueves
- F = Viernes
- A = Sábado

**Ejemplos:**
- `M-F 09:00-17:00` → Lunes a Viernes, 9am a 5pm
- `MWF 08:00-12:00` → Lunes, Miércoles, Viernes, 8am a 12pm
- `A S 00:00-23:59` → Solo fines de semana

---

## 11. proxy_auth — Usuario autenticado

**Requerir autenticación (ya viene predefinido):**

| Campo | Valor |
|-------|-------|
| Nombre | (usar `authenticated` predefinida) |
| Tipo | `proxy_auth` |
| Valor | `REQUIRED` |

> La ACL `authenticated` ya está predefinida en el sistema. No necesitas crearla.

---

## 12. maxconn — Limitar conexiones concurrentes

**Evitar que un usuario abra demasiadas conexiones:**

| Campo | Valor |
|-------|-------|
| Nombre | `limite_conexiones` |
| Tipo | `maxconn` |
| Valor | `20` |

Regla: `deny` → `limite_conexiones`

---

## 13. browser — Bloquear por User-Agent

**Bloquear un navegador específico:**

| Campo | Valor |
|-------|-------|
| Nombre | `navegador_bloqueado` |
| Tipo | `browser` |
| Valor | `Chrome` |

Regla: `deny` → `navegador_bloqueado`

---

## 14. rep_mime_type — Bloquear por tipo de contenido

**Bloquear video/audio:**

| Campo | Valor |
|-------|-------|
| Nombre | `media_streaming` |
| Tipo | `rep_mime_type` |
| Valor | `video/ audio/ application/x-shockwave-flash` |

> Nota: `rep_mime_type` se evalúa en la respuesta, no en la petición. Funciona después del bump en HTTPS.

---

## Ejemplos de reglas combinadas

### Solo permitir red local autenticada en horario laboral

1. Crear ACL: `mi_red` (src, `192.168.1.0/24`)
2. Crear ACL: `horario_laboral` (time, `M-F 09:00-17:00`)
3. Crear regla: `allow` → `mi_red authenticated horario_laboral` (orden 0)
4. La regla por defecto `deny all` bloquea el resto

### Bloquear todo excepto sitios permitidos (lista blanca)

1. Crear ACL: `sitios_permitidos` (dstdomain, `.empresa.com .google.com .wikipedia.org`)
2. Crear regla: `allow` → `sitios_permitidos` (orden 0)
3. Crear una segunda regla: `deny` → `all` (orden 1)

> ⚠️ La plantilla siempre añade, después de tus reglas, un `allow authenticated` y un `deny all` fijos —no son editables desde el panel—, para que cualquier usuario autenticado navegue salvo que una regla anterior lo haya denegado. Para una lista blanca real, tu propia regla `deny all` debe ir justo después de la de `allow`, con un orden menor que el resto de tus reglas: así corta el tráfico antes de llegar al `allow authenticated` automático del final.

### Restringir un grupo a un conjunto de dominios

1. Panel → Grupos → crear el grupo `comercial` y añadir sus miembros (usuarios locales o LDAP)
2. Crear ACL: `dominios_comercial` (dstdomain, `.crm.empresa.com .correo.empresa.com`)
3. Crear regla: `allow` → `comercial dominios_comercial` (orden 0)
4. Crear regla: `deny` → `comercial` (orden 1) — deniega el resto del tráfico de ese grupo a cualquier otro sitio
5. El resto de usuarios autenticados, que no pertenecen al grupo, siguen navegando con normalidad por el `allow authenticated` automático del final

---

## Probar las ACLs

### HTTP (siempre funciona)
```bash
curl -x http://usuario:clave@IP:3128 http://www.facebook.com -o /dev/null -w "%{http_code}"
# 403 = bloqueado ✅
# 200 = permitido ✅
```

### HTTPS (requiere SSL Bump + certificado CA instalado)
```bash
curl -x http://usuario:clave@IP:3128 https://www.facebook.com -k -o /dev/null -w "%{http_code}"
# 403 = bloqueado ✅
# 200 = permitido ✅
```

> Sin SSL Bump, el bloqueo HTTPS no funciona (Squid no puede ver el dominio en el túnel CONNECT).