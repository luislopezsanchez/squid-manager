# Actualizar SquidManager

Una actualización trae el código nuevo y aplica las migraciones de base de datos
que hagan falta. **No toca tu configuración**: usuarios, reglas, puertos,
certificados y ajustes se conservan.

El procedimiento depende de cómo esté desplegado. Si no lo sabes, míralo en el
`.env`: `DEPLOY_MODE=native` o `DEPLOY_MODE=docker` (o su ausencia, que
significa Docker).

---

## Instalación nativa (sin Docker)

```bash
cd /opt/squid-manager
sudo git pull
sudo backend/.venv/bin/pip install -q -r backend/requirements.txt
cd frontend && sudo npm install --silent && sudo npm run build
sudo systemctl restart squidmanager
```

**El `npm run build` no es opcional**, y es el equivalente exacto del `--build`
de Docker: nginx sirve los ficheros ya compilados de `frontend/dist`, así que
sin recompilar el panel sigue ejecutando la versión anterior aunque el `git
pull` haya ido bien.

Squid solo hay que reiniciarlo si la actualización cambia su configuración, y de
eso se encarga el propio panel al aplicar cambios.

**Si esta instalación es de antes de la versión 0.18.0 y usa (o vas a usar)
Kerberos/Negotiate**, hace falta un paso más, una sola vez — una instalación
nueva ya lo trae el propio instalador:

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

---

## Instalación con Docker

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
