"""Servicio de autenticación: JWT + bcrypt."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.admin import Admin
from app.models.proxy_user import ProxyUser
from app.utils import utcnow

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Marca (claim "typ") de los tokens del portal de autoservicio de los usuarios
# del proxy. Los de administrador no la llevan.
TOKEN_TYPE_PROXY_USER = "proxy_user"

# bcrypt ignora todo lo que pase de 72 bytes. Se trunca de forma explícita
# para que el comportamiento sea el mismo al crear y al verificar.
_BCRYPT_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def get_password_hash(password: str) -> str:
    """Hash bcrypt de una contraseña de administrador."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt(rounds=settings.BCRYPT_COST)).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        # htpasswd escribe el prefijo $2y$; bcrypt de Python espera $2b$.
        # Es el mismo algoritmo, solo cambia la etiqueta.
        stored = hashed_password.replace("$2y$", "$2b$", 1).encode()
        return bcrypt.checkpw(_prepare(plain_password), stored)
    except (ValueError, TypeError):
        return False


# Hash válido y sin contraseña conocida; solo sirve para igualar tiempos en authenticate_admin.
_HASH_FALSO = bcrypt.hashpw(b"sin-usuario", bcrypt.gensalt(rounds=settings.BCRYPT_COST)).decode()


def authenticate_admin(db: Session, username: str, password: str) -> Admin | None:
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or not admin.is_active:
        # Mismo coste de bcrypt que con un usuario real: sin esto, el tiempo de respuesta
        # delata qué nombres de usuario existen.
        verify_password(password, _HASH_FALSO)
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # `iat` permite invalidar los tokens emitidos antes del último cambio
    # de contraseña.
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_admin(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    # def normal (no async): hace una consulta SÍNCRONA a la base
    # (db.query(...)), y esta dependencia se evalúa en TODA ruta protegida.
    # Declarada `async def`, esa consulta se ejecutaba directamente sobre el
    # único hilo del event loop de uvicorn -con el dashboard pidiendo ~15
    # rutas cada 5s por pestaña abierta, eso bloqueaba el loop lo bastante
    # seguido como para que otros requests, que ya habían tomado una
    # conexión del pool en su propio get_db(), quedaran "colgados a mitad de
    # camino" sosteniendo esa conexión -Postgres los mostraba como "idle in
    # transaction" sobre un SELECT a admins, hasta agotar el pool entero y
    # tumbar el panel entero (2026-09-28). `def` a secas hace que FastAPI la
    # corra en threadpool, igual que ya hacen todas las rutas de metrics.py.

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        issued_at = payload.get("iat")
        if username is None:
            raise credentials_exception
        # Un token de usuario del proxy (portal de autoservicio) nunca vale como
        # administrador, aunque su nombre coincida con el de una cuenta admin.
        if payload.get("typ") == TOKEN_TYPE_PROXY_USER:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    admin = db.query(Admin).filter(Admin.username == username).first()
    if admin is None or not admin.is_active:
        raise credentials_exception

    # Cambiar la contraseña cierra las sesiones abiertas.
    # iat se trunca a segundos enteros al codificar el JWT, mientras que
    # password_changed_at conserva microsegundos. Sin margen, un login en el
    # mismo segundo que el cambio de contraseña compara iat < changed_at por
    # error y cierra la sesión recién creada. Un margen de 2s cubre eso sin
    # debilitar la protección real (revocar sesiones más viejas).
    if admin.password_changed_at and issued_at is not None:
        changed_at = admin.password_changed_at.replace(tzinfo=timezone.utc) - timedelta(seconds=2)
        if datetime.fromtimestamp(issued_at, tz=timezone.utc) < changed_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La sesión caducó porque se cambió la contraseña. Vuelve a entrar.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Mientras la cuenta tenga la contraseña inicial pendiente de cambiar, la API solo deja cambiarla
    # (antes solo lo exigía la pantalla: con el token se podía usar todo el API sin cambiarla).
    if admin.must_change_password is True and not request.url.path.endswith(("/admins/change-password", "/auth/me")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes cambiar tu contraseña antes de continuar.",
        )

    return admin


async def require_writer(admin: Admin = Depends(get_current_admin)) -> Admin:
    """Permite la operación a admin y superadmin, no a viewer.

    Se aplica a todo endpoint que modifique algo. Antes solo la usaban dos
    rutas, así que el rol viewer no restringía nada en la práctica.
    """
    if admin.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta es de solo lectura",
        )
    return admin


async def require_superadmin(admin: Admin = Depends(get_current_admin)) -> Admin:
    """Reserva la operación al superadmin."""
    if admin.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el superadmin puede realizar esta acción",
        )
    return admin


# ---------------------------------------------------------------------------
# Portal de autoservicio: usuarios locales del proxy
# ---------------------------------------------------------------------------

def authenticate_proxy_user(db: Session, username: str, password: str) -> ProxyUser | None:
    """Valida usuario y contraseña de un usuario local del proxy.

    Solo entran cuentas que hoy pueden navegar (habilitadas y sin caducar): una
    cuenta deshabilitada o vencida tampoco entra al portal.
    """
    user = db.query(ProxyUser).filter(ProxyUser.username == username).first()
    if not user or not _proxy_user_activo(user):
        verify_password(password, _HASH_FALSO)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def _proxy_user_activo(user: ProxyUser) -> bool:
    if not user.enabled:
        return False
    return user.expires_at is None or user.expires_at > utcnow()


def _huella_password(user: ProxyUser) -> str:
    """Huella corta del hash vigente: va dentro del token para que cambiar la
    contraseña (el propio usuario o el admin) cierre las sesiones abiertas, sin
    necesitar una columna nueva en la base."""
    return hashlib.sha256((user.password_hash or "").encode()).hexdigest()[:16]


def create_proxy_user_token(user: ProxyUser) -> str:
    return create_access_token({
        "sub": user.username,
        "typ": TOKEN_TYPE_PROXY_USER,
        "pwf": _huella_password(user),
    })


def get_current_proxy_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> ProxyUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        raise credentials_exception
    if payload.get("typ") != TOKEN_TYPE_PROXY_USER or not payload.get("sub"):
        raise credentials_exception

    user = db.query(ProxyUser).filter(ProxyUser.username == payload["sub"]).first()
    if user is None or not _proxy_user_activo(user):
        raise credentials_exception
    if not hmac.compare_digest(str(payload.get("pwf", "")), _huella_password(user)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión caducó porque se cambió la contraseña. Vuelve a entrar.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
