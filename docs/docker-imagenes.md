# Instalar con Docker usando imágenes ya construidas

`install.sh` clona el repositorio y **compila** Squid y el panel en tu servidor (15-30 minutos). Si solo
quieres probar SquidManager o instalarlo rápido, puedes usar las **imágenes ya construidas** que se publican en
`ghcr.io/luislopezsanchez`: la instalación tarda unos minutos.

| Imagen | Qué contiene |
|---|---|
| `ghcr.io/luislopezsanchez/squid-manager-backend` | La API del panel |
| `ghcr.io/luislopezsanchez/squid-manager-frontend` | El panel web (nginx) |
| `ghcr.io/luislopezsanchez/squid-manager-squid` | Squid compilado con SSL Bump y los helpers del panel |

Etiquetas: `latest` (la última versión) y una por versión (`1.0.1`). Solo `linux/amd64`.

## Instalar

Necesitas Docker con el plugin Compose v2. Como root:

```bash
curl -fsSL https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-imagenes.sh -o install-imagenes.sh
less install-imagenes.sh          # revisa qué hace
sudo bash install-imagenes.sh
```

El script crea `/opt/squid-manager` con un `docker-compose.yml` y un `.env` con claves aleatorias, descarga las
imágenes, arranca todo y al final imprime la URL del panel y la contraseña inicial de `admin` (te pedirá cambiarla).

Variables opcionales: `SQUIDMGR_DIR` (otra carpeta), `SQUIDMANAGER_VERSION` (por ejemplo `1.0.1` en vez de `latest`),
`WEB_PORT` y `PROXY_PORT`. Detrás de un proxy corporativo, mira
[instalacion-tras-proxy.md](instalacion-tras-proxy.md) (el demonio de Docker necesita el proxy para descargar las imágenes).

## Actualizar

```bash
cd /opt/squid-manager
sudo docker compose pull
sudo docker compose up -d
```

Tu configuración, usuarios y datos están en volúmenes de Docker y se conservan.

## Diferencias con la instalación con `install.sh`

| | `install.sh` (compila) | `install-imagenes.sh` (imágenes) |
|---|---|---|
| Tiempo | 15-30 min | unos minutos |
| Copia del código en el servidor | Sí (`/opt/squid-manager` es un repositorio git) | No: solo `docker-compose.yml` y `.env` |
| Actualizar desde **Sistema → Actualizaciones** | Sí | **No**: la pantalla avisa y se actualiza con `docker compose pull` |
| Seguir una rama de pruebas | Sí | No (solo versiones publicadas) |

## Para quien mantiene el proyecto

- `docker-compose.images.yml` se **genera** a partir de `docker-compose.yml` con
  `python3 .github/scripts/generar_compose_imagenes.py` (el CI comprueba que está al día). No se edita a mano.
- El flujo `.github/workflows/publicar-imagenes.yml` construye las tres imágenes, **prueba** la instalación
  completa con `install-imagenes.sh` (arranca el stack y comprueba panel, API y Squid) y solo entonces publica
  las etiquetas `latest` y de versión. Corre al subir una etiqueta `v*` o a mano desde la pestaña Actions.
- La primera vez, cada paquete queda **privado**: hay que hacerlo público en GitHub (perfil → Packages →
  el paquete → Package settings → Change visibility) para que cualquiera pueda descargarlo.
- Publicar una versión: `git tag v1.0.1 && git push origin v1.0.1`.
