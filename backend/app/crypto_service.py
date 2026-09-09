"""Cifrado en reposo de las credenciales de terceros guardadas en la base.

Siete columnas hoy: bind_password de LDAP, smtp_password, telegram_bot_token,
api_key/embedding_api_key del asistente de IA, la contraseña del proxy padre
y el keytab de Kerberos. Ninguna se devuelve nunca por la API (el patrón de
enmascarado ya existía y se mantiene tal cual), pero hasta ahora vivían en
texto plano en la base -quien obtenga un volcado (ver el hallazgo 11-001,
`.gitignore` de `backups/`) se las lleva sin romper nada (auditoría
2026-09-09, hallazgo 05-003).

Diseño: un `TypeDecorator` de SQLAlchemy (`EncryptedString`/`EncryptedBinary`)
que cifra al escribir y descifra al leer, transparente para el resto del
código -los modelos declaran la columna con este tipo en vez de
`String`/`LargeBinary`, y nada más cambia-.

Migración de doble lectura, sin backfill aparte: si `DATA_KEY` no está
configurada, o si un valor existente no descifra (`InvalidToken` -es texto
plano de antes de este cambio), se trata como texto plano y se devuelve tal
cual. La PRÓXIMA vez que se guarde ese mismo campo, se cifra. Así una
instalación existente no se rompe el día que actualiza: sigue funcionando en
texto plano hasta que alguien configure `DATA_KEY` y vuelva a guardar cada
campo (o lo re-guarde a propósito).
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import LargeBinary, Text
from sqlalchemy.types import TypeDecorator

from app.config import settings

logger = logging.getLogger(__name__)


def _fernet() -> Fernet | None:
    """El objeto Fernet derivado de DATA_KEY, o None si no está configurada.

    Fernet exige una clave de 32 bytes en base64 url-safe; DATA_KEY se
    escribe en el .env como un hex de 64 caracteres (mismo formato que
    SECRET_KEY, generado con `openssl rand -hex 32`) para no inventar un
    formato nuevo -se deriva la clave de Fernet con SHA-256 sobre ese valor,
    no se usa DATA_KEY directo (no está en base64 url-safe tal cual).
    """
    if not settings.DATA_KEY:
        return None
    clave = hashlib.sha256(settings.DATA_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(clave))


class EncryptedString(TypeDecorator):
    """Columna de texto cifrada en reposo con Fernet, transparente en Python.

    impl = Text (sin tope), no String(N): un token Fernet agrega ~57 bytes
    de overhead (IV, timestamp, HMAC) mas la expansion de base64 (~33%)
    sobre el texto plano. Con una columna String(255)/String(500) original,
    guardar una API key o una contrasena de servicio ya larga podia superar
    el limite del cifrado y Postgres rechazaba el INSERT/UPDATE entero -ver
    la migracion que ensancha estas columnas a TEXT junto con este cambio.
    """

    impl = Text
    cache_ok = True

    def compare_values(self, x, y) -> bool:
        """Nunca "iguales" -aunque el texto plano coincida.

        Bug real, encontrado probando esto en vivo: si el admin reenvia el
        mismo valor que ya estaba (texto plano, de antes de configurar
        DATA_KEY), SQLAlchemy compara el texto plano viejo contra el nuevo,
        los ve iguales, y NO marca la columna como modificada -asi que
        process_bind_param nunca se llama y el valor se queda sin cifrar en
        silencio, sin ningun error. Devolver False siempre fuerza a que
        cualquier asignacion explicita se trate como un cambio real y pase
        por el cifrado -Fernet genera un IV distinto cada vez, asi que
        re-cifrar el mismo texto plano es idempotente y no tiene costo
        real."""
        return False

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None or value == "":
            return value
        f = _fernet()
        if f is None:
            return value  # sin DATA_KEY configurada: se guarda en texto plano
        return f.encrypt(value.encode("utf-8")).decode("ascii")

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None or value == "":
            return value
        f = _fernet()
        if f is None:
            return value
        try:
            return f.decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError):
            # No es un token Fernet valido: es texto plano de antes de este
            # cambio (o de una corrida sin DATA_KEY). Se devuelve tal cual,
            # nunca se lanza un error por esto -romper el arranque por un
            # dato preexistente seria peor que dejarlo sin cifrar hasta el
            # proximo guardado.
            return value


class EncryptedBinary(TypeDecorator):
    """Como EncryptedString, para columnas binarias (el keytab de Kerberos)."""

    impl = LargeBinary
    cache_ok = True

    def compare_values(self, x, y) -> bool:
        # Mismo motivo que EncryptedString.compare_values -ver ahi.
        return False

    def process_bind_param(self, value: bytes | None, dialect) -> bytes | None:
        if value is None:
            return value
        f = _fernet()
        if f is None:
            return value
        return f.encrypt(value)

    def process_result_value(self, value: bytes | None, dialect) -> bytes | None:
        if value is None:
            return value
        f = _fernet()
        if f is None:
            return value
        try:
            return f.decrypt(value)
        except InvalidToken:
            return value
