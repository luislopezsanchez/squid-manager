"""Servidores DNS propios para las consultas de Squid

Squid resuelve los nombres por su cuenta, asi que se le puede indicar a que
servidores preguntar. Sirve, por ejemplo, para que la navegacion del proxy pase
por un Pi-hole y herede su filtrado.

Ambos ajustes se crean VACIOS a proposito: vacio significa "usa la resolucion
del sistema", que es como se ha comportado hasta ahora. Sembrar aqui una IP
concreta romperia cualquier instalacion donde esa direccion no exista. Se crean
igualmente para que el campo aparezca en el panel y se pueda rellenar sin tener
que tocar la base de datos.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


AJUSTES = [
    (
        "dns_nameservers",
        "network",
        "IPs de los servidores DNS a los que preguntara Squid, separadas por "
        "espacios (ej: 172.27.0.1 1.1.1.1). Vacio = usar la resolucion del "
        "sistema. Solo IPs, no nombres. Squid reparte las consultas entre "
        "todos: para que TODO pase por un filtro, deja uno solo.",
    ),
    (
        "dns_v4_first",
        "network",
        "Poner 'true' para consultar IPv4 antes que IPv6. Util en redes sin "
        "IPv6 real, donde intentarlo primero anade una espera en cada "
        "resolucion. Vacio = comportamiento por defecto de Squid.",
    ),
]


def upgrade() -> None:
    ajustes = sa.table(
        "squid_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.String),
        sa.column("category", sa.String),
        sa.column("description", sa.String),
    )
    conexion = op.get_bind()

    for clave, categoria, descripcion in AJUSTES:
        # Puede existir ya si alguien lo creo a mano: no se pisa su valor.
        existe = conexion.execute(
            sa.text("SELECT 1 FROM squid_settings WHERE key = :k"), {"k": clave}
        ).first()
        if existe:
            continue
        op.bulk_insert(ajustes, [{
            "key": clave,
            "value": "",
            "category": categoria,
            "description": descripcion,
        }])


def downgrade() -> None:
    conexion = op.get_bind()
    for clave, _, _ in AJUSTES:
        conexion.execute(
            sa.text("DELETE FROM squid_settings WHERE key = :k"), {"k": clave}
        )
