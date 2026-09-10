# Actualizar SquidManager

Una actualización trae el código nuevo y aplica las migraciones de base de datos
que hagan falta. **No toca tu configuración**: usuarios, reglas, puertos,
certificados y ajustes se conservan.

El procedimiento depende de cómo esté desplegado. Si no lo sabes, míralo en el
`.env`: `DEPLOY_MODE=native` o `DEPLOY_MODE=docker` (o su ausencia, que
significa Docker).

---

## Instalación nativa (sin Docker)

**Forma recomendada: `upgrade-nativo.sh`.** Es un script aparte del
instalador, pensado para bajarse fresco cada vez —nunca la copia que ya
tenés en `/opt/squid-manager`—:

```bash
cd /ruta/a/tu/squid-manager   # el directorio donde está instalado, sea cual sea
wget -O upgrade-nativo.sh https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/upgrade-nativo.sh
sudo BRANCH=main bash upgrade-nativo.sh   # o la rama que corresponda
```

El script trabaja sobre **el directorio donde lo corras**, no sobre una
ruta fija: si tu instalación no está en `/opt/squid-manager`, no hace falta
pasar nada extra, alcanza con bajarlo y correrlo ahí dentro.

Con esto, en una sola corrida:

- Hace un backup de la base con `backup-database.sh` antes de tocar nada
  (si el script no existe todavía en tu instalación —versiones previas a
  que se agregara—, avisa y sigue sin backup en vez de abortar).
- Trae el código nuevo (`git fetch` + `checkout` + `reset --hard`, descartando
  cualquier modificación local del propio checkout —nunca la de `.env`, que es
  un archivo aparte, gitignored, y no lo toca `git clean`—) y purga
  `__pycache__` (gitignoreado, así que `git clean` tampoco lo toca, y un
  `.pyc` viejo ahí puede quedar sirviendo código de antes del upgrade).
- Invoca, como proceso nuevo, el `install-nativo.sh` que quedó en el
  checkout ya actualizado —nunca el que estaba corriendo antes—, que es
  quien deja instalada la extensión `pgvector` de Postgres si faltaba,
  reinstala el drop-in de systemd de Kerberos, el `logrotate` y el script
  de `cron.monthly` si el código de alguno cambió, reinstala las
  dependencias de Python, recompila el frontend, y reinicia el servicio de
  verdad (no solo si estaba caído).

**Por qué un script aparte, y no alcanza con volver a correr
`install-nativo.sh` directamente** —que sigue siendo seguro de re-ejecutar
sobre una instalación que ya existe, y es lo que `upgrade-nativo.sh` invoca
por dentro—: ese script hace su propio `git checkout`/`reset` sobre sí
mismo como parte de la actualización. Si la versión ya instalada difiere de
la versión destino en la lógica de esa misma sección —como pasó al pasar de
una versión sin este mecanismo a una con él—, bash sigue ejecutando en
memoria el código VIEJO durante el resto de la corrida mientras los
archivos de disco, el propio script incluido, ya cambiaron por debajo: el
fix de `git checkout`, la instalación de `pgvector` y el reinicio de
servicios pueden no llegar a aplicarse, sin ningún error que lo delate.
Bug real, encontrado y aislado probando el upgrade en vivo. `upgrade-nativo.sh`
lo evita por diseño —nunca se modifica a sí mismo— y de paso resuelve
también el reinicio: **`systemctl enable --now` no reinicia un servicio que
ya está activo**, así que sin este cambio el código podía quedar
actualizado en disco mientras el proceso seguía corriendo la versión
anterior.

**Qué NO toca**: tu `.env` (`SECRET_KEY`, contraseña de la base, puerto del
panel, orígenes CORS...) se preserva tal cual —se lee del `.env` existente
antes de escribir el nuevo—, y los datos de la base (usuarios, ACLs, reglas,
certificados) ni se rozan: el instalador nunca borra una base que ya existe,
solo la crea si falta. Verificado en vivo, más de una vez, con datos reales
cargados antes de actualizar.

Si preferís no correr el script, el equivalente manual —y lo que hace falta
revisar caso por caso si un futuro cambio toca algo que el instalador no
cubre— es:

**Antes de nada, la extensión `pgvector`.** Desde la versión 0.22.0 hay una
migración de base de datos que ejecuta `CREATE EXTENSION vector`, y eso exige
ser **superusuario de Postgres** —el rol de la aplicación (`squid`) no lo es,
a propósito—. Si el `systemctl restart` de más abajo llega a las migraciones
sin la extensión ya creada, el backend se queda **en bucle de reinicio** con
`permission denied to create extension "vector"`. Se prepara una sola vez,
como `postgres`:

```bash
PG_MAJOR=$(sudo -u postgres psql -tAc 'SHOW server_version;' | cut -d. -f1)
sudo apt-get install -y "postgresql-$PG_MAJOR-pgvector"
sudo -u postgres psql -d squidmanager -c "CREATE EXTENSION IF NOT EXISTS vector"
```

`upgrade-nativo.sh` hace exactamente esto por vos (por eso es el camino
recomendado). Y si ya corriste el `restart` y el backend quedó caído: este
mismo bloque, seguido de otro `sudo systemctl restart squidmanager`, lo
levanta —la migración 0014 es transaccional, no dejó nada a medias, se
quedó en la revisión anterior—.

Hecho eso, el resto:

```bash
cd /opt/squid-manager
sudo git pull
sudo backend/.venv/bin/pip install -q -r backend/requirements.txt
cd frontend && sudo npm install --silent && sudo npm run build
sudo systemctl restart squidmanager
```

(En modo nativo la base la crea `install-nativo.sh` con locale `C`, que no
tiene el problema de reordenamiento de índices que sí afecta a Docker —ver
la sección de Docker más abajo—, así que acá no hay que reindexar nada.)

**El `npm run build` no es opcional**, y es el equivalente exacto del `--build`
de Docker: nginx sirve los ficheros ya compilados de `frontend/dist`, así que
sin recompilar el panel sigue ejecutando la versión anterior aunque el `git
pull` haya ido bien.

Squid solo hay que reiniciarlo si la actualización cambia su configuración, y de
eso se encarga el propio panel al aplicar cambios.

### Por qué el camino manual necesita revisión caso por caso

`git pull` trae el código nuevo al repositorio clonado, pero **no vuelve a
copiar** los archivos que `install-nativo.sh` deja fuera de `/opt/squid-manager`
la primera vez —el paquete `postgresql-N-pgvector` y la extensión en la base,
la configuración de `logrotate`, el script de `cron.monthly`, el drop-in de
systemd de Kerberos—. Si una versión nueva cambia alguno de esos, hace falta
reinstalarlo a mano después del `git pull` (o, más simple, volver a correr el
instalador completo, que es justo lo que resuelve esto). Este caso solo existe
en modo nativo: en Docker, `--build` reconstruye la imagen entera con lo que el
`Dockerfile` copia.

Ejemplo concreto del paso manual, para quien no quiera re-correr el
instalador — Kerberos/Negotiate, desde la versión 0.18.0:

```bash
sudo mkdir -p /etc/systemd/system/squid.service.d
sudo tee /etc/systemd/system/squid.service.d/squidmanager-kerberos.conf > /dev/null <<'EOF'
[Service]
Environment=KRB5_CONFIG=/etc/squid/krb5.conf
EOF
sudo systemctl daemon-reload
sudo systemctl restart squid
```

Sin esto, Squid no ve la variable de entorno que le dice dónde está el
`/etc/squid/krb5.conf` que el panel genera al aplicar cambios: la
autenticación Negotiate falla siempre con `Bad encryption type` pese a un
keytab correcto. Detalle completo en [kerberos.md](kerberos.md).

Rotación de logs por fecha, retención a 30 días y consolidación mensual, desde
la versión 0.20.0:

```bash
cd /opt/squid-manager
sudo install -o root -g root -m 644 squid/squid-logrotate.native /etc/logrotate.d/squid
sudo install -o root -g root -m 755 squid/consolidate-monthly-logs.sh /etc/cron.monthly/squidmanager-log-archive
```

No hace falta reiniciar nada después de esto: `logrotate` y `cron.monthly` los
ejecuta el sistema por su cuenta cuando corresponde, no un servicio de
SquidManager.

**Si esta instalación ya venía consolidando logs mensuales antes de la
reorganización del histórico por año/mes** (módulo "Histórico de logs" del
panel), los meses viejos quedaron en el layout plano anterior
(`archive/monthly/{access,cache}-AAAAMM.log.gz`) y el panel no los va a
listar ahí —espera `archive/historical/AAAA/MM/`—. Migralos una sola vez:

```bash
cd /opt/squid-manager
sudo bash squid/migrate-old-monthly-logs.sh
```

Es seguro correrlo aunque no haga falta (una instalación nueva, o que nunca
llegó a consolidar un mes, simplemente no encuentra nada que mover) y
también correrlo dos veces (no duplica ni sobreescribe nada ya migrado).
Genera además el `index.json` que le falta a cada mes de `access` migrado,
usando el mismo indexador que ya instala `install-nativo.sh`.

---

## Instalación con Docker

**Forma recomendada: `upgrade-docker.sh`.** También aparte del `install.sh`,
también bajado fresco cada vez:

```bash
cd /ruta/a/squid-manager
wget -O upgrade-docker.sh https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/upgrade-docker.sh
sudo BRANCH=main bash upgrade-docker.sh   # o la rama que corresponda
```

Hace, en una sola corrida: backup de la base con `backup-database.sh` antes
de tocar nada (si falla, avisa y sigue igual —preferible actualizar sin
backup que no actualizar—), trae el código nuevo con el mismo mecanismo
seguro que en modo nativo (descarta cambios locales antes de cambiar de
rama, para que un `git checkout` no aborte el script entero por una
modificación sin commitear), reconstruye con `docker compose up -d
--build`, **reconstruye los índices de la base** (ver abajo) y verifica que
`/health` responda al final. Trabaja sobre el directorio donde lo corras,
no sobre una ruta fija.

**Reindexado de la base, una sola vez.** Hasta la 0.21.0 la imagen de
Postgres era `postgres:16-alpine` (musl); desde la 0.22.0 es
`pgvector/pgvector:pg16` (glibc, necesaria para el Asistente de IA). musl no
registra versión de *collation*, así que al cambiar de imagen Postgres **no
emite ningún warning**, pero el orden con el que compara texto sí cambia:
los índices B-tree de columnas de texto —incluido el `UNIQUE` de
`proxy_users.username`— quedan ordenados con el criterio viejo y son
lógicamente inconsistentes (un `SELECT ... WHERE username = X` por índice
puede no encontrar la fila; el `UNIQUE` puede dejar pasar un duplicado).
`upgrade-docker.sh` corre `REINDEX DATABASE` después del `up -d` para
arreglarlo —es rápido (los índices de este esquema son chicos) e
idempotente—. Si actualizás a mano, hacelo vos:

```bash
docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c 'REINDEX DATABASE "'"$DB_NAME"'";'
```

Las instalaciones nuevas ya no tienen este problema: el `docker-compose.yml`
crea la base con locale `C.UTF-8`, que no tiene versión de *collation* y es
inmune a cualquier cambio futuro de imagen o de libc.

**Si esta instalación es de antes del Asistente de IA**, en teoría hace
falta crear la extensión `vector` a mano en el volumen de Postgres ya
existente (`db-init/01-pgvector.sql` solo corre solo al inicializar un
volumen vacío, no en uno que ya tenía datos). En la práctica, el usuario de
base de datos de la aplicación (`POSTGRES_USER` del `.env`) es superusuario
por defecto en la imagen oficial de Postgres, así que la migración
correspondiente lo resuelve sola sin este paso —verificado en vivo—. Si en
tu caso falla con `permission denied to create extension "vector"` (por
ejemplo, si en algún momento le quitaste el rol de superusuario a ese
usuario), corré esto antes de reintentar:

```bash
docker exec squidmgr-db psql -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Desde el directorio de la instalación:

```bash
cd /ruta/a/squid-manager && git pull && docker compose up -d --build
```

**El `--build` no es opcional.** Sin él, Docker reutiliza las imágenes que ya
tiene y el código nuevo no llega a ejecutarse, aunque el `git pull` haya ido
bien. Es el fallo más fácil de cometer, porque todo parece correcto: el
repositorio está al día y los contenedores arrancan, pero siguen ejecutando la
versión anterior.

Las migraciones se aplican solas cuando arranca el backend. No hay que
ejecutarlas a mano.

---

## Comprobar que fue bien

El más directo, en cualquiera de los dos modos: `/health` devuelve la versión
y el commit que corre de verdad, no lo que crees que desplegaste.

```bash
curl -s http://localhost:8000/health
```

Debe mostrar la versión esperada y el commit al que apuntaste (`git log
--oneline -1` te da ese hash para comparar).

**Docker:**

```bash
cd /ruta/a/squid-manager && git log --oneline -1 && git status --porcelain | wc -l && docker exec squidmgr-db psql -U squid -d squidmanager -tAc "select version_num from alembic_version;" && docker compose ps
```

| | Esperado |
|---|---|
| Último commit | El de la versión que querías |
| Ficheros pendientes | `0` |
| Revisión de la base | El número de migración más alto de `backend/migrations/versions/` |
| Contenedores | Los cuatro en `healthy` |

Si algo del frontend no aparece en el panel, mira si la imagen se reconstruyó:

```bash
docker compose logs backend --since 5m | grep -iE "Migraciones aplicadas|error"
```

**Nativo:**

```bash
cd /opt/squid-manager && git log --oneline -1 && git status --porcelain | wc -l && sudo -u postgres psql -d squidmanager -tAc "select version_num from alembic_version;" && systemctl status squid squidmanager nginx --no-pager
```

| | Esperado |
|---|---|
| Último commit | El de la versión que querías |
| Ficheros pendientes | `0` |
| Revisión de la base | El número de migración más alto de `backend/migrations/versions/` |
| Servicios | Los tres `active (running)` |

Si algo del frontend no aparece en el panel, confirma que `npm run build`
corrió de verdad (no basta con `npm install`):

```bash
journalctl -u squidmanager --since "5 min ago" | grep -iE "Migraciones aplicadas|error"
```

---

## Problemas frecuentes

### El `git pull` dice «Aborting»

Hay ficheros en el directorio que la actualización sobrescribiría. Suele pasar
cuando se han copiado archivos a mano en lugar de traerlos con Git.

```bash
git status --short
```

- Las líneas con `??` son ficheros sin rastrear que bloquean el pull
- Las líneas con `M` son modificaciones locales

Si no son cambios tuyos que quieras conservar, se retiran y se vuelve a
intentar:

```bash
git checkout -- . && git clean -fd && git pull
```

> `git clean -fd` **borra** los ficheros sin rastrear del proyecto. Revisa antes
> lo que aparece en `git status --short`: el `.env` está excluido y no se toca,
> pero cualquier otro fichero propio que hayas dejado ahí sí se perdería.

Ojo con el estado a medias: si un pull aborta después de haber tocado algunos
ficheros, el proyecto queda mezclado —parte antiguo, parte nuevo— y los
síntomas son incoherentes. Las pruebas lo detectan:

```bash
# Docker
docker exec -w /app squidmgr-backend python -m pytest tests/ -q

# Nativo
cd /opt/squid-manager/backend && set -a && . ../.env && set +a && .venv/bin/python -m pytest tests/ -q
```

### El panel no muestra algo nuevo

Casi siempre es el rebuild del frontend olvidado. Reconstruye explícitamente:

```bash
# Docker
docker compose build backend frontend && docker compose up -d

# Nativo
cd /opt/squid-manager/frontend && sudo npm run build && sudo systemctl restart squidmanager
```

### Una migración falla y el backend no arranca

El backend queda reiniciándose en bucle. El motivo está en su registro:

```bash
# Docker
docker compose logs backend | grep -B5 -A5 -iE "error|traceback" | head -40

# Nativo
journalctl -u squidmanager -n 100 --no-pager | grep -B5 -A5 -iE "error|traceback"
```

La revisión de la base te dice hasta dónde llegó:

```bash
# Docker
docker exec squidmgr-db psql -U squid -d squidmanager -tAc "select version_num from alembic_version;"

# Nativo
sudo -u postgres psql -d squidmanager -tAc "select version_num from alembic_version;"
```

Las migraciones son transaccionales: la que falla no deja nada a medias, se
queda en la anterior. Corregido el motivo, basta con reiniciar el backend
(`docker compose up -d` en Docker, `sudo systemctl restart squidmanager` en
nativo).

---

## Volver a una versión anterior

```bash
cd /ruta/a/squid-manager && git log --oneline -10
```

> Si la versión que buscas está etiquetada (`git tag --sort=-v:refname`),
> usa la etiqueta como `<commit>` en vez de buscar el hash a mano —
> `git checkout v0.23.2` en lugar de `git checkout dbb5694`.

```bash
# Docker
git checkout <commit> && docker compose up -d --build

# Nativo
git checkout <commit> && cd backend && .venv/bin/pip install -q -r requirements.txt && cd ../frontend && sudo npm install --silent && sudo npm run build && sudo systemctl restart squidmanager
```

> **Cuidado con las migraciones.** Volver atrás en el código **no deshace los
> cambios en la base de datos**. Si la versión que abandonas añadió tablas o
> columnas, seguirán ahí: normalmente no molesta, porque el código antiguo
> simplemente las ignora. Lo que sí da problemas es que la versión anterior no
> reconozca la revisión en la que quedó la base. Para deshacer también el
> esquema:
>
> ```bash
> # Docker
> docker exec -w /app squidmgr-backend python -m alembic downgrade <revision>
>
> # Nativo
> cd /opt/squid-manager/backend && set -a && . ../.env && set +a && .venv/bin/python -m alembic downgrade <revision>
> ```
>
> Haz copia de seguridad antes:
> - Docker: `docker exec squidmgr-db pg_dump -U squid squidmanager > copia.sql`
> - Nativo: `sudo -u postgres pg_dump squidmanager > copia.sql`

---

## Si tienes varios proxies encadenados

Actualízalos por separado; el orden da igual. La configuración de la cascada
—quién intercepta, quién autentica, los certificados— vive en la base de datos
y **una actualización no la modifica**.

Después de actualizar, conviene comprobar que la cadena sigue en pie: en el
registro del proxy de abajo, las peticiones deben seguir saliendo con
`FIRSTUP_PARENT`.

```bash
# Docker
docker exec squidmgr-proxy tail -20 /var/log/squid/access.log

# Nativo
tail -20 /var/log/squid/access.log
```

Ver [proxy-padre.md](proxy-padre.md) si algo dejó de funcionar.

---

## Copia de seguridad antes de actualizar

Para una instalación en producción, antes de tocar nada:

```bash
# Docker
docker exec squidmgr-db pg_dump -U squid squidmanager > ~/squidmanager-$(date +%Y%m%d).sql

# Nativo
sudo -u postgres pg_dump squidmanager > ~/squidmanager-$(date +%Y%m%d).sql
```

Eso guarda toda la configuración. Los volúmenes de Squid (certificado CA,
caché) no se incluyen; el certificado se puede descargar aparte desde el panel,
en **Certificado CA**, y conviene tenerlo guardado porque si se pierde hay que
reinstalarlo en todos los clientes.

---

## Para quien publica una versión nueva

Las tres fuentes de versión (`backend/app/config.py`, `frontend/package.json`
y `CHANGELOG.md`) tienen que moverse juntas, y el commit que las mueve se
etiqueta en git — sin la etiqueta no hay forma de hacer `git diff
v0.22.0..v0.23.0` para saber qué entró en una versión concreta, ni de volver a
una versión publicada con un identificador estable (ver la sección de arriba).

```bash
git tag -a vX.Y.Z <commit-del-changelog> -m "SquidManager X.Y.Z - <resumen corto>"
git push --tags
```
