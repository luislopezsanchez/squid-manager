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

## Instalación del certificado CA

Para que los navegadores confíen en Squid, debes instalar el certificado CA en cada equipo cliente.

### Descargar el certificado

1. Abre el panel web → **"🔐 Certificado SSL"**
2. Click en **"📥 Descargar squidmanager-ca.crt"**
3. Guarda el archivo

### Instalar en Windows (Chrome, Edge, Brave)

1. Doble clic en `squidmanager-ca.crt`
2. Click en **"Instalar certificado..."**
3. Seleccionar **"Equipo local"** (requiere permisos de administrador)
4. Seleccionar **"Colocar todos los certificados en el siguiente almacén"**
5. Click en **"Examinar..."** y seleccionar **"Entidades de certificación raíz de confianza"**
6. Click en **"Siguiente"** → **"Finalizar"**
7. Reiniciar el navegador

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
- Protege el acceso al panel web (cambia las credenciales por defecto)
- Considera usar HTTPS para el panel web mismo (proxy reverso con Nginx + Let's Encrypt)

### Lo que Squid NO puede hacer con SSL Bump
- **Certificate Pinning:** Algunas apps (banco, Google) usan pinning de certificados y rechazarán el certificado de Squid. No hay forma de evitar esto.
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
Apps como Google, bancos, etc. usan certificate pinning. No se puede evitar. Para estos sitios, puedes configurar `ssl_bump splice` para que pasen sin interceptar.

### Squid no arranca después de habilitar SSL Bump
```bash
docker compose logs squid
```
Verifica que `security_file_certgen` está disponible y que `/tmp/ssl_crtd` se inicializó correctamente.