"""Servicio de autenticación: JWT + bcrypt."""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.admin import Admin

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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


def authenticate_admin(db: Session, username: str, password: str) -> Admin | None:
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or not admin.is_active:
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


async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        issued_at = payload.get("iat")
        if username is None:
            raise credentials_exception
    except JWTError:
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
