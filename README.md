# SquidManager

**Español · [English](README.en.md) · [Português](README.pt.md)**

<p align="center">
  <strong>Panel web de gestión para Squid Proxy, con FastAPI, React y SSL Bump</strong><br>
  Se despliega <strong>con Docker</strong> o <strong>sin Docker</strong>
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-Freeware-orange.svg">
  <img alt="Squid" src="https://img.shields.io/badge/Squid-6.12%20%7C%206.14-green">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.136-teal">
  <img alt="React" src="https://img.shields.io/badge/React-18-blue">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-blue">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-blue">
</p>

> ### 🌍 Idiomas de la documentación
>
> | | Español | English | Português |
> |---|---|---|---|
> | **README** | este | [README.en.md](README.en.md) | [README.pt.md](README.pt.md) |
> | **Instalación con Docker** | [ver](docs/installation.md) | [view](docs/installation.en.md) | [ver](docs/installation.pt.md) |
> | **Instalación sin Docker** | [ver](docs/instalacion-nativa.md) | [view](docs/instalacion-nativa.en.md) | [ver](docs/instalacion-nativa.pt.md) |
>
> El resto de la documentación está solo en español. El **panel y los mensajes
> de la API** sí hablan los tres idiomas: se elige en el selector de la barra
> superior — ver [docs/idiomas.md](docs/idiomas.md).

---

## 📖 Qué es

**SquidManager** es una plataforma de gestión de Squid Proxy que permite
configurar y administrar un proxy Squid desde una interfaz web, sin editar
`squid.conf` a mano: ACLs, reglas de acceso, usuarios, LDAP/Kerberos, delay
pools, SSL Bump, dashboard en vivo, auditoría, backups y más — ver el listado
completo en [docs/caracteristicas.md](docs/caracteristicas.md).

Gestiona **un nodo Squid** por instancia: la base de datos es la fuente de
verdad, `squid.conf` se genera dinámicamente, y todo corre en contenedores
Docker **o como servicios del sistema**, según el modo que elijas — mismo
producto, mismas funciones, distinto despliegue. Para más de un nodo, se
despliega una instancia de SquidManager por nodo (ver
[docs/production.md](docs/production.md)).

---

## ✅ Estado del proyecto y requisitos

| | |
|---|---|
| **Última versión** | v0.24.9 ([CHANGELOG.md](CHANGELOG.md)) |
| **Probado con éxito en** | Ubuntu 24.04 LTS (Docker y nativo) y Ubuntu 22.04 / Debian 12 (nativo) |
| **No soportado todavía** | Ubuntu 26.04 (Python 3.14 sin binarios de `psycopg`/`pydantic-core` aún) |
| **Docker** | Docker 20.10+, Docker Compose v2+ y `git` (para clonar el repo — no viene preinstalado en toda imagen "mínima" de Ubuntu) |
| **Nativo (sin Docker)** | Ubuntu 22.04 / 24.04 o Debian 12, x86_64 — necesita `squid-openssl`, no cualquier Linux |
| **Hardware mínimo** | 2 CPU (con 1 CPU la primera instalación puede tardar más de una hora, no minutos), 2 GB RAM (con swap ≥ 1 GB si es 1 GB), 5 GB disco |

Detalle completo, con las excepciones probadas en vivo, en
[docs/instalacion-nativa.md](docs/instalacion-nativa.md#requisitos) (nativo) y
[docs/installation.md](docs/installation.md#requisitos-previos) (Docker).

> ## ⚠️ Importante si venís de una versión **0.24.2 a 0.24.7**
>
> La actualización disparada **desde el panel** (botón "Actualizar ahora", o
> el temporizador automático) puede fallar siempre con `fatal: $HOME not
> set`, sin lograr avanzar nunca, en instalaciones nativas o Docker que estén
> en alguna de estas versiones. No es intermitente: si te pasa, te va a
> seguir pasando en cada intento hasta que lo destrabes una vez a mano.
>
> **No se autorepara solo reintentando** — el arreglo vive en los mismos
> archivos que esa actualización rota nunca llega a traer del repositorio.
> Hace falta un único comando por SSH para destrabarla:
>
> ```bash
> sudo systemctl set-environment HOME=/root
> ```
>
> Después de eso, "Actualizar ahora" completa con normalidad y la instalación
> queda al día — a partir de ahí se sigue actualizando sola sin este problema.
> Explicación completa de por qué pasó y cómo se corrigió de raíz en
> [docs/actualizacion.md](docs/actualizacion.md#la-actualización-desde-el-panel-falla-con-fatal-home-not-set).

---

## 🚀 Instalación rápida

Elegí el modo — son excluyentes, una máquina usa uno **o** el otro. Guías
completas paso a paso: [docs/installation.md](docs/installation.md) (Docker) y
[docs/instalacion-nativa.md](docs/instalacion-nativa.md) (nativa).

**Con Docker:**

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
sudo ./install.sh
```

**Sin Docker (nativa):**

```bash
wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-nativo.sh
less install-nativo.sh   # revisa qué va a hacer en tu servidor, siempre
chmod +x install-nativo.sh
sudo ./install-nativo.sh
```

Al terminar (3-5 min nativo, 15-30 min Docker por la compilación de Squid),
cada instalador imprime la URL del panel, el usuario y la contraseña inicial.
Primeros pasos después de instalar: [docs/primeros-pasos.md](docs/primeros-pasos.md).

¿Tu servidor sale a internet por un proxy corporativo? Ver
[docs/instalacion-tras-proxy.md](docs/instalacion-tras-proxy.md) antes de instalar.

---

## 🔄 Actualizar

```bash
# Con Docker
cd /ruta/a/squid-manager
wget -O upgrade-docker.sh https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/upgrade-docker.sh
sudo bash upgrade-docker.sh

# Sin Docker (nativo)
cd /opt/squid-manager
wget -O upgrade-nativo.sh https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/upgrade-nativo.sh
sudo bash upgrade-nativo.sh
```

Backup previo de la base, código traído de forma segura, todo reconstruido y
reiniciado — tu configuración (usuarios, reglas, puertos, certificados) se
conserva siempre. Ver el aviso de arriba si tu versión instalada es 0.24.2 a
0.24.7. Guía completa, verificación post-upgrade y solución de problemas del
propio proceso de actualización: [docs/actualizacion.md](docs/actualizacion.md).

---

## 📚 Documentación

| Tema | Documento |
|---|---|
| **Instalación** | [Con Docker](docs/installation.md) · [Sin Docker (nativa)](docs/instalacion-nativa.md) · [Detrás de un proxy corporativo](docs/instalacion-tras-proxy.md) |
| **Actualización** | [Actualizar, verificar, volver atrás](docs/actualizacion.md) · [Actualizaciones desde el panel](docs/actualizaciones-automaticas.md) |
| **Primeros pasos** | [Después de instalar](docs/primeros-pasos.md) · [Panel web: qué hace cada sección](docs/panel-web.md) |
| **Funciones** | [Lista completa de características](docs/caracteristicas.md) · [SSL Bump y certificados](docs/ssl-bump.md) |
| **Autenticación** | [Cuentas, roles, Basic/Digest/none](docs/authentication.md) · [Kerberos / Negotiate (SSO)](docs/kerberos.md) |
| **Redes** | [Proxy padre encadenado](docs/proxy-padre.md) |
| **Asistente de IA** | [Qué ve, qué no, cómo activarlo](docs/asistente-ia.md) |
| **Backup** | [Backup, restore y migración](docs/backup-restore.md) |
| **Idiomas** | [Arquitectura de traducciones](docs/idiomas.md) |
| **Técnico** | [Arquitectura](docs/architecture.md) · [Configuración (`.env`)](docs/configuration.md) · [Estructura del proyecto](docs/estructura-proyecto.md) · [API REST](docs/api-reference.md) |
| **Producción** | [Guía de despliegue en producción](docs/production.md) |
| **Problemas** | [Solución de problemas](docs/solucion-problemas.md) |
| **Proyecto** | [CHANGELOG](CHANGELOG.md) · [Cómo contribuir](CONTRIBUTING.md) · [Bitácora](docs/project-log.md) |
| **Backups de referencia** | [backups/](backups/README.md) — despliegue completo listo para restaurar en Proxmox |

---

## 📝 Licencia

Freeware — uso personal o interno permitido; **no se permite modificar, redistribuir ni comercializar** el software. Ver [LICENSE](LICENSE) para el texto completo.

## 🤝 Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para saber cómo contribuir al proyecto.
