# Instalación nativa (sin Docker)

SquidManager puede desplegarse sin Docker, con Squid, el panel, PostgreSQL y
nginx corriendo como servicios del sistema. Es la alternativa al despliegue con
contenedores, no un complemento: en una misma máquina se usa uno **o** el otro.

Para quién tiene sentido:

- Redes donde la política interna no permite Docker.
- Un equipo que ya hace de proxy y donde meter un runtime de contenedores es
  añadir una pieza que nadie quería.
- Appliances o máquinas pequeñas, donde ahorrarse la capa de contenedores se
  nota.

## Requisitos

- Ubuntu 22.04/24.04 o Debian 12, x86_64.
- Acceso root.
- Salida a internet para descargar paquetes y clonar el repositorio.

## Instalación

```bash
wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-nativo.sh
less install-nativo.sh          # revisa qué va a hacer en tu servidor
chmod +x install-nativo.sh
sudo ./install-nativo.sh
```

Al terminar imprime la URL del panel y la contraseña inicial de `admin`, que hay
que cambiar en el primer acceso.

Se puede ajustar con variables de entorno:

```bash
WEB_PORT=8080 PROXY_PORT=3130 sudo -E ./install-nativo.sh
```

| Variable | Por defecto | Qué es |
|---|---|---|
| `WEB_PORT` | `3000` | Puerto del panel |
| `PROXY_PORT` | `3128` | Puerto del proxy |
| `API_PORT` | `8000` | Puerto interno de la API (solo escucha en localhost) |
| `INSTALL_DIR` | `/opt/squid-manager` | Dónde vive el código |
| `APP_USER` | `squidmgr` | Usuario con el que corre el panel |
| `BRANCH` | `main` | Rama del repositorio a desplegar |

## Qué instala, y por qué así

### `squid-openssl`, no `squid`

Debian y Ubuntu empaquetan Squid dos veces. El paquete `squid` a secas es la
variante **GnuTLS**: no trae `--with-openssl`, no trae `--enable-ssl-crtd` y no
incluye `security_file_certgen`. Con él, el SSL Bump del panel no puede
funcionar, y el fallo aparecería mucho más tarde y sin relación aparente con la
causa.

`squid-openssl` sí trae todo lo que el proyecto necesita —OpenSSL, ssl-crtd,
delay pools, autenticación básica NCSA y LDAP, 65536 descriptores— así que **no
hay que compilar nada**. El instalador lo comprueba explícitamente y aborta si
el binario que encuentra no está compilado con OpenSSL.

Los dos paquetes instalan el mismo binario `/usr/sbin/squid` y no pueden
convivir: instalar uno desinstala el otro.

### Privilegios: usuario propio y tres órdenes

El panel **no corre como root**. Se crea el usuario `squidmgr`, cuyo grupo
primario es `proxy`, y un fichero de sudoers con tres órdenes literales, sin
comodines:

```
squidmgr ALL=(root) NOPASSWD: /usr/sbin/squid -f /etc/squid/squid.conf -k reconfigure
squidmgr ALL=(root) NOPASSWD: /usr/sbin/squid -k parse -f /etc/squid/squid.conf.candidate
squidmgr ALL=(root) NOPASSWD: /usr/bin/systemctl restart squid
```

Es bastante menos de lo que concede el modo Docker, donde el backend necesita el
socket del daemon —que es equivalente a root en la máquina—.

Que el grupo primario sea `proxy` no es un detalle: es lo que permite al panel
escribir los ficheros que Squid tiene que leer (el htpasswd de los usuarios, la
configuración de LDAP) sin necesidad de `chown`, que exigiría privilegios. Los
ficheros con secretos se crean con modo 640 y grupo `proxy`, de modo que sólo
root, el panel y Squid pueden leerlos.

### Base de datos

PostgreSQL en la misma máquina. **SQLite no sirve**: hay nueve operaciones en
las migraciones (`drop_column`, `drop_constraint`, `create_foreign_key`…) que
SQLite no soporta sin `batch_alter_table`, y el proyecto no lo usa.

### Rotación de logs

El paquete de Squid trae su propio `/etc/logrotate.d/squid`; el instalador lo
aparta como `squid.dpkg-orig` y pone el del proyecto. La diferencia importa: el
nuestro fuerza a Squid a reabrir el fichero después de rotarlo. Sin eso, Squid
sigue escribiendo en el fichero ya renombrado, `/var/log/squid/access.log` deja
de existir, y el panel se queda a cero —tarjetas, gráficas, registros y
estadísticas salen todas de ahí— mientras la navegación sigue funcionando con
normalidad, así que nada delata el fallo.

## Diferencias de comportamiento frente a Docker

Son tres, todas deliberadas.

**El puerto vive en el `squid.conf`.** En Docker, Squid escucha siempre en un
puerto interno fijo y Docker publica hacia fuera el que elige el panel. En
nativo no hay traducción: Squid escucha directamente donde diga el panel, y
cambiar de puerto es reescribir el fichero y reiniciar el servicio, sin recrear
nada.

**El tráfico se mide de la máquina entera**, no de una interfaz virtual
dedicada al proxy. En un equipo que hace de proxy y poco más la diferencia es
despreciable; si la máquina hace otras cosas, su tráfico también cuenta en la
tarjeta de tráfico en tiempo real.

**El estado se consulta a systemd.** El panel muestra `active` / `failed` en
lugar de `running` / `exited`.

## Operación

```bash
systemctl status squid squidmanager nginx    # estado
journalctl -u squidmanager -f                # registros del panel
journalctl -u squid -f                       # registros de Squid
```

Configuración en `/opt/squid-manager/.env`. Tras editarla:

```bash
systemctl restart squidmanager
```

## Actualizar

```bash
cd /opt/squid-manager
sudo git pull
sudo backend/.venv/bin/pip install -q -r backend/requirements.txt
cd frontend && sudo npm install --silent && sudo npm run build
sudo systemctl restart squidmanager
```

El panel aplica las migraciones de base de datos al arrancar, así que no hay
paso aparte para eso.

## Desinstalar

```bash
sudo systemctl disable --now squidmanager squid
sudo rm -f /etc/systemd/system/squidmanager.service /etc/sudoers.d/squidmanager
sudo rm -f /etc/nginx/sites-enabled/squidmanager
sudo systemctl daemon-reload && sudo systemctl reload nginx
sudo rm -rf /opt/squid-manager
```

La base de datos, `/etc/squid` y los certificados se conservan a propósito:
bórralos aparte si de verdad quieres empezar de cero.
