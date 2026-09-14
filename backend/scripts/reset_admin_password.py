#!/usr/bin/env python3
"""Resetea la contraseña de un administrador, sin necesitar la actual.

Última red de seguridad si se pierde el acceso web -mismo rol que
`pihole -a -p` en Pi-hole-: se corre en el propio servidor (nativo, con
sudo, o dentro del contenedor en Docker), nunca desde la API, así que
solo quien ya tiene acceso a la máquina puede usarlo. No pide la
contraseña vieja porque el punto es justo no necesitarla.

Uso:
    python -m scripts.reset_admin_password [usuario] [contraseña]

Sin `contraseña`, se genera una aleatoria y se imprime UNA sola vez
-igual que hace install-nativo.sh con ADMIN_INITIAL_PASSWORD-. Sin
`usuario`, usa "admin".

Además de la contraseña: reactiva la cuenta (`is_active`), fuerza a
cambiarla en el próximo login (`must_change_password`) y actualiza
`password_changed_at` -esto último invalida cualquier token JWT ya
emitido (ver auth_service.crear_token), por si el motivo del reset fue
justamente sospechar que alguien más tiene una sesión abierta.

Mismo aviso que purge_audit_log.py sobre variables de entorno: en modo
nativo hace falta cargar el .env del proyecto antes de invocar esto (lo
hace reset-admin-password.sh); en Docker, `docker exec` ya las hereda
del contenedor.
"""

import secrets
import string
import sys

from app.database import SessionLocal
from app.models.admin import Admin
from app.services.auth_service import get_password_hash
from app.utils import utcnow


def _generar_password() -> str:
    # Mismo alfabeto y longitud que install-nativo.sh para la contraseña
    # inicial: legible al copiar a mano desde una terminal, sin
    # ambigüedades visuales que compliquen tipearla si hace falta.
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(16))


def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    password = sys.argv[2] if len(sys.argv) > 2 else None
    generada = password is None
    if generada:
        password = _generar_password()

    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.username == username).first()
        if not admin:
            existentes = [a.username for a in db.query(Admin.username).all()]
            print(f"No existe ningún administrador llamado '{username}'.", file=sys.stderr)
            if existentes:
                print(f"Administradores existentes: {', '.join(existentes)}", file=sys.stderr)
            return 1

        admin.password_hash = get_password_hash(password)
        admin.must_change_password = True
        admin.is_active = True
        admin.password_changed_at = utcnow()
        db.commit()
    finally:
        db.close()

    print("Contraseña reseteada correctamente.")
    print(f"  Usuario:    {username}")
    if generada:
        print(f"  Contraseña: {password}")
        print("  (se pedirá cambiarla en el próximo inicio de sesión)")
    print("  Cualquier sesión abierta con la contraseña anterior quedó invalidada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
