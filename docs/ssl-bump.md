# SSL Bump — Interceptación HTTPS

SquidManager incluye SSL Bump, que permite a Squid interceptar, desencriptar y filtrar tráfico HTTPS.

---

## ¿Qué es SSL Bump?

Sin SSL Bump, Squid solo puede ver el destino de una conexión HTTPS (la IP y el puerto), pero no puede ver el dominio ni el contenido. El tráfico pasa como un túnel ciego (`CONNECT`).

Con SSL Bump, Squid:
1. Intercepta la conexión HTTPS
2. Genera un certificado dinámico para el sitio destino, firmado por una CA local
3. Desencripta el tráfico
4. Aplica las reglas (ACLs, delay pools, bloqueos)
5. Vuelve a encriptar y lo envía al cliente

Esto permite:
- ✅ Bloquear dominios por HTTPS (ej: `https://www.facebook.com`)
- ✅ Limitar velocidad de descargas HTTPS (delay pools)
- ✅ Filtrar por tipo de contenido en HTTPS
- ✅ Ver qué sitios visita cada usuario por HTTPS

---

## Excluir dominios del descifrado

Algunos sitios no se pueden interceptar sin romperlos (ver "Lo que Squid NO puede hacer" más abajo). Para esos casos, SquidManager permite dejarlos pasar cifrados de extremo a extremo, sin desencriptar:

1. Panel → **Configuración** → categoría **Seguridad**
2. Edita el parámetro **dominios excluidos del descifrado** (`ssl_bump_exclude`)
3. Añade los dominios separados por espacios, por ejemplo: `.tubanco.com .miobrasocial.gob`
4. **Aplicar cambios**

Internamente, esto genera una ACL por SNI y una directiva `ssl_bump splice` que se evalúa antes del `bump`, así que esos dominios nunca llegan a desencriptarse.

---

## Instalación del certificado CA

Para que los navegadores confíen en Squid, debes instalar el certificado CA en cada equipo cliente.

### Descargar el certificado

1. Abre el panel web → **"Certificado"**
2. Click en **"Descargar squidmanager-ca.crt"** (o usa uno de los instaladores automáticos: `.bat` para Windows, script para GPO, `.mobileconfig` para iOS/macOS)
3. Guarda el archivo

### Instalar en Windows (Chrome, Edge, Brave)

1. Doble clic en `squidmanager-ca.crt`
2. Click en **"Instalar certificado..."**
3. Seleccionar **"Equipo local"** (requiere permisos de administrador)
4. Seleccionar **"Colocar todos los certificados en el siguiente almacén"**
5. Click en **"Examinar..."** y seleccionar **"Entidades de certificación raíz de confianza"**
6. Click en **"Siguiente"** → **"Finalizar"**
7. Reiniciar el navegador

> Para varios equipos en un dominio de Windows, descarga el script de despliegue por GPO desde la página "Certificado" del panel en vez de instalarlo uno a uno.

### Instalar en Firefox (Windows, Linux, Mac)

1. Abrir Firefox → `about:preferences` en la barra
2. Buscar "certificados" → Click en **"Ver certificados..."**
3. Pestaña **"Entidades"** → Click en **"Importar..."**
4. Seleccionar `squidmanager-ca.crt`
5. Marcar **"Confiar en esta CA para identificar sitios web"**
6. Click en **"Aceptar"**

### Instalar en Linux (sistema)

```bash
# Ubuntu / Debian
sudo cp squidmanager-ca.crt /usr/local/share/ca-certificates/squidmanager-ca.crt
sudo update-ca-certificates

# CentOS / RHEL / Fedora
sudo cp squidmanager-ca.crt /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust
```

### Instalar en macOS

1. Doble clic en `squidmanager-ca.crt`
2. Se abre "Acceso a Llaveros" (Keychain Access)
3. Buscar "SquidManager CA" y doble clic
4. Sección **"Confianza"** → Cambiar a **"Confiar siempre"**
5. Cerrar y escribir contraseña de administrador
6. Reiniciar el navegador

### Instalar en iOS

1. Descarga el perfil `.mobileconfig` desde la página "Certificado" del panel
2. Ajustes → Perfil descargado → Instalar
3. Ajustes → General → Información → Ajustes de confianza de certificados → activa la confianza total para "SquidManager CA"

---

## ¿Se puede usar un certificado público (Let's Encrypt) en vez de la CA autofirmada?

**No — no es una limitación de SquidManager, es un límite de diseño de SSL Bump y de las CA públicas.**

- **Por el lado de Squid:** SSL Bump funciona firmando, al vuelo, un certificado
  nuevo por cada dominio de destino que visita cada usuario, usando la **clave
  privada** de una CA que Squid controla localmente (por eso el panel genera y
  te hace instalar una CA propia). La [documentación oficial de Squid sobre
  generación dinámica de certificados](https://wiki.squid-cache.org/Features/DynamicSslCert)
  lo dice sin rodeos: hacer esto te convierte a vos en una CA raíz. Para que
  Squid pudiera firmar con un certificado de Let's Encrypt, necesitaría tener
  la clave privada de esa CA — algo que ninguna CA pública, Let's Encrypt
  incluida, entrega jamás a un tercero para firmar dominios ajenos a demanda.
- **Por el lado de Let's Encrypt:** aunque fuera técnicamente posible, está
  prohibido explícitamente. Su [CPS (Certificate Practice Statement), sección
  1.4.2 "Prohibited certificate uses"](https://letsencrypt.org/documents/isrg-cps-v2.6/)
  prohíbe usar sus certificados en arquitecturas que faciliten interferencia
  con comunicaciones cifradas, "incluyendo pero no limitado a eavesdropping
  activo (ej. ataques man-in-the-middle)" — que es exactamente lo que hace SSL
  Bump.

En resumen: SSL Bump es un MITM autorizado por la organización sobre sus
propios equipos, con una CA interna instalada a mano en cada cliente — es
estructuralmente incompatible con una CA pública, que por definición solo
emite certificados al dueño legítimo de un dominio, nunca a un tercero que
quiere interceptar tráfico ajeno. Esto no va a cambiar en ninguna versión
futura de SquidManager porque no depende de SquidManager: es así en Squid, y
en cualquier otro proxy con inspección HTTPS (Fortinet, Palo Alto, etc. tienen
la misma limitación y la misma solución: CA interna instalada en los equipos).

> ℹ️ **No confundir con el certificado del panel web.** Usar Let's Encrypt
> **sí** es válido y recomendable para servir el propio panel de SquidManager
> por HTTPS (`https://panel.empresa.com` vía Nginx) — eso es un certificado
> normal para un dominio que controlás, sin relación con SSL Bump. Ver
> [production.md](production.md#4-https-para-el-panel).

---

## Verificación

Después de instalar el certificado:

1. Configura el proxy en tu navegador (IP:3128, usuario, contraseña)
2. Navega a `https://httpbin.org/ip` → debería cargar normalmente
3. Navega a `https://www.facebook.com` → debería mostrar "Access Denied" (si está bloqueado)

Si ves una advertencia de certificado, el certificado CA no se instaló correctamente.

---

## Consideraciones de seguridad

### Privacidad
SSL Bump permite a Squid ver todo el tráfico HTTPS, incluyendo contenido. Esto es necesario para aplicar reglas, pero significa que el administrador del proxy puede teóricamente ver el tráfico cifrado.

### Recomendaciones
- Usa SSL Bump solo en entornos corporativos donde sea necesario
- Informa a los usuarios que su tráfico HTTPS está siendo inspeccionado
- Excluye del descifrado la banca, la sanidad y cualquier dato especialmente sensible (ver arriba)
- Considera usar HTTPS para el panel web mismo (proxy reverso con Nginx + Let's Encrypt)

### Lo que Squid NO puede hacer con SSL Bump
- **Certificate Pinning:** Algunas apps (banco, Google) usan pinning de certificados y rechazarán el certificado de Squid. Añade esos dominios a la lista de exclusión en vez de intentar interceptarlos.
- **HTTP/2:** Squid 6.x tiene soporte limitado para HTTP/2 sobre SSL Bump.

---

## Solución de problemas

### "Su conexión no es privada" / NET::ERR_CERT_AUTHORITY_INVALID
El certificado CA no está instalado. Sigue las instrucciones de arriba.

### El antivirus bloquea el sitio
Algunos antivirus inspeccionan HTTPS y detectan el certificado de Squid como sospechoso. Opciones:
1. Instalar el certificado CA en el almacén del sistema (no solo del navegador)
2. Añadir una excepción en el antivirus para el certificado de Squid
3. Desactivar la inspección HTTPS del antivirus temporalmente

### Algunos sitios no funcionan (certificate pinning)
Apps como Google, bancos, etc. usan certificate pinning. No se puede evitar. Añade esos dominios a **Configuración → dominios excluidos del descifrado** para que pasen sin interceptar.

### Squid no arranca después de habilitar SSL Bump

```bash
docker compose logs squid
```

Verifica que la base de certificados dinámicos está en buen estado y con los permisos correctos:

```bash
docker exec squidmgr-proxy ls -l /var/lib/ssl_crtd/db/index.txt
```

Debe existir y pertenecer al usuario `proxy` (no a `root`). Si el propietario es incorrecto, Squid no podrá escribir su índice de certificados y el generador (`security_file_certgen`) morirá repetidamente con errores `Database search failure` en `cache.log`. La base vive en el volumen persistente `squid-crtd`, montado en `/var/lib/ssl_crtd`, no en un directorio temporal del contenedor.
