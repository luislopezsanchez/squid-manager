# Actualizar SquidManager

Una actualización trae el código nuevo, reconstruye las imágenes y aplica las
migraciones de base de datos que hagan falta. **No toca tu configuración**:
usuarios, reglas, puertos, certificados y ajustes se conservan.

---

## Actualizar

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

```bash
cd /ruta/a/squid-manager && git log --oneline -1 && git status --porcelain | wc -l && docker exec squidmgr-db psql -U squid -d squidmanager -tAc "select version_num from alembic_version;" && docker compose ps
```

Lo que debes ver:

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
docker exec -w /app squidmgr-backend python -m pytest tests/ -q
```

### El panel no muestra algo nuevo

Casi siempre es el `--build` olvidado. Reconstruye explícitamente:

```bash
docker compose build backend frontend && docker compose up -d
```

### Una migración falla y el backend no arranca

El backend queda reiniciándose en bucle. El motivo está en su registro:

```bash
docker compose logs backend | grep -B5 -A5 -iE "error|traceback" | head -40
```

La revisión de la base te dice hasta dónde llegó:

```bash
docker exec squidmgr-db psql -U squid -d squidmanager -tAc "select version_num from alembic_version;"
```

Las migraciones son transaccionales: la que falla no deja nada a medias, se
queda en la anterior. Corregido el motivo, basta con reiniciar el backend.

---

## Volver a una versión anterior

```bash
cd /ruta/a/squid-manager && git log --oneline -10
```

```bash
git checkout <commit> && docker compose up -d --build
```

> **Cuidado con las migraciones.** Volver atrás en el código **no deshace los
> cambios en la base de datos**. Si la versión que abandonas añadió tablas o
> columnas, seguirán ahí: normalmente no molesta, porque el código antiguo
> simplemente las ignora. Lo que sí da problemas es que la versión anterior no
> reconozca la revisión en la que quedó la base. Para deshacer también el
> esquema:
>
> ```bash
> docker exec -w /app squidmgr-backend python -m alembic downgrade <revision>
> ```
>
> Haz copia de seguridad antes: `docker exec squidmgr-db pg_dump -U squid squidmanager > copia.sql`

---

## Si tienes varios proxies encadenados

Actualízalos por separado; el orden da igual. La configuración de la cascada
—quién intercepta, quién autentica, los certificados— vive en la base de datos
y **una actualización no la modifica**.

Después de actualizar, conviene comprobar que la cadena sigue en pie: en el
registro del proxy de abajo, las peticiones deben seguir saliendo con
`FIRSTUP_PARENT`.

```bash
docker exec squidmgr-proxy tail -20 /var/log/squid/access.log
```

Ver [proxy-padre.md](proxy-padre.md) si algo dejó de funcionar.

---

## Copia de seguridad antes de actualizar

Para una instalación en producción, antes de tocar nada:

```bash
docker exec squidmgr-db pg_dump -U squid squidmanager > ~/squidmanager-$(date +%Y%m%d).sql
```

Eso guarda toda la configuración. Los volúmenes de Squid (certificado CA,
caché) no se incluyen; el certificado se puede descargar aparte desde el panel,
en **Certificado CA**, y conviene tenerlo guardado porque si se pierde hay que
reinstalarlo en todos los clientes.
