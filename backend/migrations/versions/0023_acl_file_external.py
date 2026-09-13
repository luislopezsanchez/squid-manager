"""ACLs de archivo: el archivo en disco pasa a ser la fuente de verdad

Hasta ahora, una ACL con source='file' (creada por una carga masiva de
dominios, `POST /acls/bulk-domains`) guardaba su contenido completo DOS
veces: en la columna `acls.value` (un TEXT en la base de datos) y en
`/etc/squid/acl_lists/<nombre>.txt` (el archivo que Squid realmente lee).
El archivo era solo una "proyección" que se regeneraba completa desde
`value` en CADA "Aplicar cambios" -con una lista de varios millones de
dominios (el caso real que motivó este cambio: +100 MB, +5M dominios), eso
significaba mover 100 MB entre Postgres y Python en cada apply, más el pico
de memoria de reconstruir el archivo entero con `splitlines()`/`join()`
cada vez, aunque la lista no hubiera cambiado. El mismo `value` de 100 MB
también viajaba en cada `GET /acls/` (para listar) y en cada backup/export.

A partir de ahora, para una ACL 'file' el archivo es la fuente de verdad y
`acls.value` queda en NULL; se guardan en su lugar `content_hash` (sha256
del contenido ya escrito, para saber si el archivo sigue vigente sin
releerlo) y `line_count` (para mostrar un conteo en el panel sin traer el
contenido). Una ACL 'inline' no cambia en nada: sigue usando `value` igual
que siempre.

Esta migración SOLO cambia el esquema (agrega las columnas nuevas y
permite `value` NULL) -no mueve datos ella misma. El contenido de las
ACLs 'file' que ya existan en una instalación sigue estando en su `value`
actual después de actualizar: `squid_service.build_acl_list_files()` migra
cada una de forma perezosa la primera vez que corre "Aplicar cambios"
después de esta migración (confirma que el archivo en disco coincide,
calcula el hash y el conteo, y solo entonces limpia `value`). Así no hace
falta parar el servicio para migrar, y si algo interrumpe el proceso a
mitad de camino, el dato sigue estando en `value` hasta que el siguiente
apply lo complete -en ningún momento hay una ventana donde el contenido no
esté ni en la BD ni en el archivo.

Revision ID: 0023
Revises: 0022
"""
from alembic import op
import sqlalchemy as sa
from pathlib import Path

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

ACL_LISTS_DIR = Path("/etc/squid/acl_lists")


def upgrade() -> None:
    with op.batch_alter_table("acls") as batch:
        batch.alter_column("value", existing_type=sa.Text(), nullable=True)
        batch.add_column(sa.Column("content_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("line_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    # Antes de poder devolver `value` a NOT NULL hay que rellenar toda ACL
    # 'file' que ya haya sido migrada (value NULL) leyendo su archivo en
    # disco -si el archivo no está (instalación restaurada en otra máquina
    # sin /etc/squid/acl_lists, por ejemplo), se aborta con un mensaje claro
    # en vez de perder esa ACL silenciosamente al dejarla en blanco.
    bind = op.get_bind()
    filas = bind.execute(sa.text(
        "SELECT id, name FROM acls WHERE source = 'file' AND value IS NULL"
    )).fetchall()

    faltantes = []
    for fila in filas:
        ruta = ACL_LISTS_DIR / f"{fila.name}.txt"
        if not ruta.exists():
            faltantes.append(fila.name)
            continue
        contenido = ruta.read_text(encoding="utf-8", errors="replace")
        bind.execute(
            sa.text("UPDATE acls SET value = :value WHERE id = :id"),
            {"value": contenido, "id": fila.id},
        )

    if faltantes:
        raise RuntimeError(
            "No se puede revertir: faltan los archivos en disco de estas ACLs "
            f"'file' (no se puede reconstruir su valor): {', '.join(faltantes)}. "
            "Restaurá esos archivos en /etc/squid/acl_lists/ antes de reintentar "
            "el downgrade."
        )

    with op.batch_alter_table("acls") as batch:
        batch.drop_column("line_count")
        batch.drop_column("content_hash")
        batch.alter_column("value", existing_type=sa.Text(), nullable=False)
