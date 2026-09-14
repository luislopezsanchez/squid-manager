# Primeros pasos

Después de instalar SquidManager (con cualquiera de los dos modos):

> **Recién instalado, el proxy no deja pasar a nadie, y es a propósito.**
> Squid arranca negando todo salvo `localhost`; el panel lo sustituye enseguida
> por la configuración definitiva, que exige usuario y contraseña. Hasta que
> crees el primer usuario del proxy no navegará nadie. Vale para los dos modos
> de despliegue: una instalación recién hecha no puede quedar abierta a la red
> mientras su dueño ni siquiera ha entrado al panel.

1. **Abre el puerto del proxy en el firewall del servidor** (no lo hace ni el
   instalador ni el panel):
   ```bash
   sudo ufw allow 3128/tcp
   sudo ufw enable   # si ufw todavía está inactivo (por defecto lo está en Ubuntu recién instalado)
   ```
2. **Abre el panel** → http://localhost:3000 (o la IP del servidor)
3. **Inicia sesión** con `admin` y la contraseña generada al instalar
4. **Cambia la contraseña** cuando el panel te lo pida
5. **Crea un usuario del proxy** → Página "Usuarios" → "Nuevo usuario"
6. **Configura tu navegador** con el proxy:
   - IP: `localhost` (o la IP del servidor)
   - Puerto: `3128`
   - Usuario: el que creaste
   - Contraseña: la que configuraste
7. **Navega** → Tu tráfico pasa por Squid
8. **Crea una ACL** → Página "ACLs" → "Nueva ACL" (ej: bloquear `.facebook.com`)
9. **Crea una regla** → Página "Reglas de acceso" → "Nueva regla" → `deny` + tu ACL
10. **Aplica cambios** → Botón "Aplicar cambios" en el sidebar
11. **Prueba** → Intenta navegar a Facebook → debería bloquearse

## SSL Bump (HTTPS)

Para que el bloqueo también funcione en HTTPS (no solo HTTP), hace falta
instalar el certificado CA de SquidManager en los clientes. Guía completa,
con instrucciones por sistema operativo, en [ssl-bump.md](ssl-bump.md).

Resumen rápido:

1. Abre el panel → **"Certificado"**
2. Descarga el archivo `squidmanager-ca.crt` (o el instalador para tu sistema)
3. Instálalo en el almacén de **"Entidades de certificación raíz de confianza"** del sistema/navegador
4. Reinicia el navegador
