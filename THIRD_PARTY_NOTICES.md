# Componentes de terceros

SquidManager es software libre bajo la AGPL-3.0-or-later (ver `LICENSE`). Funciona gracias a los
componentes siguientes, **cada uno con su propia licencia y sus autores**, que se conservan. Ninguno se
modifica. Esta lista corresponde a la versión 1.0.0; las versiones exactas están en `backend/requirements.txt`
y `frontend/package-lock.json`.

Todas las licencias de esta lista son compatibles con la AGPL-3.0-or-later.

## Software con el que trabaja (no se distribuye en este repositorio)

| Componente | Licencia | Cómo se usa |
|---|---|---|
| [Squid](https://www.squid-cache.org/) | GPL-2.0-or-later | El proxy que SquidManager configura. Se instala del paquete de la distribución o se compila de su tarball oficial sin cambios (`squid/Dockerfile`). SquidManager no lo enlaza ni lo modifica. |
| [PostgreSQL](https://www.postgresql.org/) y [pgvector](https://github.com/pgvector/pgvector) | PostgreSQL License | Base de datos. |
| [nginx](https://nginx.org/) | BSD-2-Clause | Sirve el panel web. |
| [Docker / Compose](https://www.docker.com/) | Apache-2.0 | Despliegue en contenedores (opcional). |
| Ubuntu / Debian / Python / Node.js | Varias (libres) | Imágenes y entorno de ejecución. |
| [libarchive (bsdtar)](https://www.libarchive.org/) | BSD-2-Clause | Leer backups `.rar` / `.7z`. |

## Datos de terceros descargados por cada instalación

| Datos | Licencia | Notas |
|---|---|---|
| [HaGeZi DNS Blocklists](https://github.com/hagezi/dns-blocklists) | GPL-3.0 | Listas de bloqueo que cada instalación **descarga por sí misma** si el administrador las activa. No se incluyen en este repositorio. La atribución aparece en la descripción de cada categoría. |

## Fuentes (incluidas en `frontend/public/fonts`)

| Fuente | Licencia | Texto de la licencia |
|---|---|---|
| Figtree (© The Figtree Project Authors) | SIL Open Font License 1.1 | `frontend/public/fonts/OFL-Figtree.txt` |
| JetBrains Mono (© The JetBrains Mono Project Authors) | SIL Open Font License 1.1 | `frontend/public/fonts/OFL-JetBrainsMono.txt` |

## Librerías de Python (backend)

`psycopg` y `ldap3` son **LGPL-3.0**: se usan como librerías externas sin modificar (se instalan con `pip` y
se pueden sustituir por otra versión). `certifi` es **MPL-2.0**, sin modificar.

| Paquete | Versión | Licencia |
|---|---|---|
| alembic | 1.13.3 | MIT |
| aiodns | 4.0.4 | MIT |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| bcrypt | 4.2.1 | Apache-2.0 |
| certifi | 2026.7.22 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| chardet | 7.6.0 | 0BSD |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause |
| docker | 7.1.0 | Apache-2.0 |
| et_xmlfile | 2.0.0 | MIT |
| fastapi | 0.136.0 | MIT |
| greenlet | 3.5.6 | MIT AND PSF-2.0 |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.27.2 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| Jinja2 | 3.1.6 | BSD License |
| ldap3 | 2.9.1 | LGPL v3 |
| Mako | 1.4.3 | MIT |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| openpyxl | 3.1.5 | MIT |
| pgvector | 0.5.0 | MIT |
| pillow | 12.3.0 | MIT-CMU |
| psycopg | 3.2.13 | LGPL-3.0-only |
| pyasn1 | 0.6.4 | BSD-2-Clause |
| pyasn1-modules | 0.4.2 | BSD |
| pycares | 5.1.0 | MIT |
| pycparser | 3.0 | BSD-3-Clause |
| pydantic | 2.9.2 | MIT |
| pydantic-settings | 2.5.2 | MIT |
| pydantic_core | 2.23.4 | MIT |
| PyJWT | 2.15.1 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-multipart | 0.0.31 | Apache-2.0 |
| reportlab | 4.2.5 | BSD License |
| requests | 2.34.2 | Apache-2.0 |
| slixmpp | 1.17.0 | MIT |
| sniffio | 1.3.1 | MIT OR Apache-2.0 |
| SQLAlchemy | 2.0.35 | MIT |
| starlette | 1.6.0 | BSD-3-Clause |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.30.6 | BSD-3-Clause |

## Librerías de JavaScript (interfaz, en producción)

| Paquete | Versión | Licencia |
|---|---|---|
| @babel/runtime | 7.29.7 | MIT |
| @types/d3-array | 3.2.2 | MIT |
| @types/d3-color | 3.1.3 | MIT |
| @types/d3-ease | 3.0.2 | MIT |
| @types/d3-interpolate | 3.0.4 | MIT |
| @types/d3-path | 3.1.1 | MIT |
| @types/d3-scale | 4.0.9 | MIT |
| @types/d3-shape | 3.2.0 | MIT |
| @types/d3-time | 3.0.4 | MIT |
| @types/d3-timer | 3.0.2 | MIT |
| clsx | 2.1.1 | MIT |
| cookie | 1.1.1 | MIT |
| csstype | 3.2.3 | MIT |
| d3-array | 3.2.4 | ISC |
| d3-color | 3.1.0 | ISC |
| d3-ease | 3.0.1 | BSD-3-Clause |
| d3-format | 3.1.2 | ISC |
| d3-interpolate | 3.0.1 | ISC |
| d3-path | 3.1.0 | ISC |
| d3-scale | 4.0.2 | ISC |
| d3-shape | 3.2.0 | ISC |
| d3-time | 3.1.0 | ISC |
| d3-time-format | 4.1.0 | ISC |
| d3-timer | 3.0.1 | ISC |
| decimal.js-light | 2.5.1 | MIT |
| dom-helpers | 5.2.1 | MIT |
| eventemitter3 | 4.0.7 | MIT |
| fast-equals | 5.4.3 | MIT |
| internmap | 2.0.3 | ISC |
| js-tokens | 4.0.0 | MIT |
| lodash | 4.18.1 | MIT |
| loose-envify | 1.4.0 | MIT |
| object-assign | 4.1.1 | MIT |
| prop-types | 15.8.1 | MIT |
| react | 18.3.1 | MIT |
| react-dom | 18.3.1 | MIT |
| react-is | 18.3.1 | MIT |
| react-router | 7.18.3 | MIT |
| react-router-dom | 7.18.3 | MIT |
| react-smooth | 4.0.4 | MIT |
| react-transition-group | 4.4.5 | BSD-3-Clause |
| recharts | 2.15.4 | MIT |
| recharts-scale | 0.4.5 | MIT |
| scheduler | 0.23.2 | MIT |
| set-cookie-parser | 2.7.2 | MIT |
| tiny-invariant | 1.3.3 | MIT |
| victory-vendor | 36.9.2 | MIT AND ISC |

## Icono y logo

El logo y los iconos del panel son propios del proyecto (ver `NOTICE` y `TRADEMARK.md`). No se usa ninguna
librería de iconos de terceros.
