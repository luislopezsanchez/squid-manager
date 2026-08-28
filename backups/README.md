# Backups de despliegue — Proxmox LXC

Backups completos de un contenedor LXC de Proxmox con SquidManager ya
desplegado y funcionando: útil para no tener que compilar Squid desde cero
(10-15 minutos, o más en hardware modesto) ni resolver problemas de red al
instalar. Se restaura y arranca en minutos.

Los archivos pesan varios GB y no viven en este repositorio — Git y GitHub no
están pensados para binarios de ese tamaño. Se alojan aparte; cada entrada de
la tabla de abajo tiene su enlace de descarga y su checksum.

## Backups disponibles

| Archivo | Fecha | Commit de SquidManager | Tamaño | SHA-256 |
|---|---|---|---|---|
| [vzdump-lxc-888-2026_08_28-16_27_41.tar.lzo](https://ftp.innovanet.uy/Proxmox_Container/vzdump-lxc-888-2026_08_28-16_27_41.tar.lzo) | 2026-08-28 | [`913a1e8`](https://github.com/luislopezsanchez/squid-manager/commit/913a1e8) | 2.99 GB | `4ea522c3f6c834337312c3c5bb1618d30631a5f47a6303af659a768fd175f1a6` |

**Verificá siempre el checksum después de descargar** — un archivo de este
tamaño se puede corromper en la transferencia sin que se note hasta que falla
la restauración a mitad de camino:

```bash
sha256sum vzdump-lxc-888-2026_08_28-16_27_41.tar.lzo
```

Tiene que coincidir exactamente con el valor de la tabla.

## Qué trae adentro

- Ubuntu 24.04, con SquidManager clonado en `/opt/squid-manager` en el commit
  de la tabla.
- Los cuatro contenedores Docker construidos: backend, frontend, Squid
  (compilado) y PostgreSQL.
- Los datos de PostgreSQL, con la cuenta `admin` inicial ya creada.
- El `.env` con `DB_PASS` y `SECRET_KEY` **tal como los generó `install.sh`
  en el despliegue original** — es decir, **no son valores de ejemplo, son
  las claves reales de esa instalación**. Ver la advertencia de abajo.

## Requisitos para restaurar

- Un host Proxmox VE.
- Al menos **4 GB de RAM y 2 CPU** asignados al contenedor. Con menos, la
  restauración funciona, pero si alguna vez necesitás reconstruir alguna
  imagen (por ejemplo tras una actualización), compilar Squid con menos
  memoria puede hacer que el contenedor se reinicie a mitad de la
  compilación por falta de RAM.
- Al menos 10 GB de disco libres.

## Cómo restaurar

Desde la consola del host Proxmox (no desde dentro de un contenedor):

```bash
pct restore <ID-nuevo> /ruta/donde/lo/descargaste/vzdump-lxc-888-2026_08_28-16_27_41.tar.lzo --storage <tu-storage>
```

Reemplazá `<ID-nuevo>` por un ID de contenedor libre en tu Proxmox, y
`<tu-storage>` por el storage donde querés que viva (`local-lvm` es el más
común). Después:

```bash
pct start <ID-nuevo>
```

Esperá unos segundos a que los contenedores Docker internos terminen de
arrancar, y entrá al panel en `http://<IP-del-contenedor>:3000`.

## Antes de exponerlo a una red real — pasos obligatorios

Este backup es una instalación real, no una plantilla en blanco. Si lo vas a
usar más allá de una prueba rápida y descartable, hay que hacer esto **antes**
de dejarlo accesible desde la red:

### 1. Cambiar la contraseña de `admin`

Al entrar por primera vez el panel va a pedir cambiarla — es un paso
obligatorio del propio sistema, no hay que olvidarse de hacerlo, pero tampoco
hay forma de saltearlo.

### 2. Regenerar `SECRET_KEY` y `DB_PASS` — esto sí hay que acordarse solo

A diferencia de la contraseña de `admin`, **nada fuerza este cambio**. Y es el
paso más importante de los dos: `SECRET_KEY` firma las sesiones del panel.
Cualquiera que tenga el valor que trae este backup puede fabricarse una
sesión válida como `admin` sin pasar por el login —sin usuario, sin
contraseña, sin que el cambio del paso 1 lo proteja de nada—, porque nunca se
autentica: arma el token directamente. `DB_PASS` es la contraseña de la base
de datos por detrás del panel.

Entrá al contenedor y editá el `.env`:

```bash
cd /opt/squid-manager
nano .env
```

Reemplazá `SECRET_KEY` con un valor nuevo:

```bash
openssl rand -hex 32
```

Y `DB_PASS` con otro:

```bash
openssl rand -hex 16
```

Aplicá los cambios:

```bash
docker compose up -d
```

**Sin este paso, cualquiera que haya descargado este backup —ahora o dentro
de un año— tiene una puerta de entrada al panel que ningún cambio de
contraseña cierra.**

## Puertos que quedan publicados al arrancar

| Puerto | Servicio |
|---|---|
| 3000 | Panel web |
| 3128 | Proxy Squid |

Si necesitás otros puertos (por ejemplo si ya usás el 3128 en esa red), se
cambian desde el propio panel, en Configuración.
