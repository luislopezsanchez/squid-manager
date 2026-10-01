"""Importar y exportar usuarios locales del proxy desde archivos CSV / Excel /
texto plano (carga masiva).

Este módulo solo LEE y VALIDA (sin base de datos, sin tocar Squid): devuelve
filas ya normalizadas y una lista de errores por fila. Crear los usuarios de
verdad lo hace routes/proxy_users.py, que necesita la sesión y los hashes.

Formatos aceptados:
- .csv  (coma o punto y coma, UTF-8 con o sin BOM; la primera fila son los
  encabezados)
- .xlsx (primera hoja; la primera fila son los encabezados)
- .txt  (una línea por usuario: `usuario`, `usuario:contraseña` o
  `usuario,contraseña`)

Encabezados reconocidos (español, inglés o portugués, sin importar
mayúsculas ni acentos): usuario/username/user/login, contraseña/password/
clave/senha, nombre/display_name/name/nome, email/correo/mail/e-mail,
habilitado/enabled/activo/ativo, caduca/expires_at/expira/vencimento.
"""

import csv
import io
import re
import unicodedata
from datetime import datetime

MAX_FILAS = 5000
MAX_BYTES = 5 * 1024 * 1024

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_ALIAS = {
    "username": {"usuario", "username", "user", "login", "cuenta", "conta"},
    "password": {"contrasena", "contrasenia", "password", "clave", "senha", "pass"},
    "display_name": {"nombre", "nombre para mostrar", "display_name", "displayname", "name", "nome", "nombre completo"},
    "email": {"email", "correo", "mail", "e-mail", "correo electronico", "correo electrónico"},
    "enabled": {"habilitado", "enabled", "activo", "ativo", "estado", "status"},
    "expires_at": {"caduca", "caducidad", "expires_at", "expira", "expires", "vencimiento", "vence"},
}

_SI = {"1", "si", "sí", "s", "yes", "y", "true", "verdadero", "activo", "habilitado", "ativo", "sim"}
_NO = {"0", "no", "n", "false", "falso", "inactivo", "deshabilitado", "desabilitado", "nao", "não"}

COLUMNAS_PLANTILLA = ["usuario", "contraseña", "nombre", "email", "habilitado", "caduca"]
FILAS_EJEMPLO = [
    ["jperez", "", "Juan Pérez", "jperez@empresa.com", "si", ""],
    ["mgomez", "Clave-Segura-2026", "María Gómez", "", "si", "2026-12-31"],
]


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _clave_columna(encabezado: str) -> str | None:
    limpio = _sin_acentos((encabezado or "").strip().lower().lstrip("﻿"))
    for campo, alias in _ALIAS.items():
        if limpio in {_sin_acentos(a) for a in alias}:
            return campo
    return None


def _leer_csv(datos: bytes) -> list[list[str]]:
    texto = datos.decode("utf-8-sig", errors="replace")
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    return [[c.strip() for c in fila] for fila in csv.reader(io.StringIO(texto), dialecto)]


def _leer_xlsx(datos: bytes) -> list[list[str]]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(datos), read_only=True, data_only=True)
    ws = wb.active
    filas = []
    for fila in ws.iter_rows(values_only=True):
        filas.append(["" if c is None else (c.strftime("%Y-%m-%d") if isinstance(c, datetime) else str(c).strip()) for c in fila])
        if len(filas) > MAX_FILAS + 2:  # basta para que quien llama diga «demasiadas filas»: no se lee el resto
            break
    wb.close()
    return filas


def _leer_txt(datos: bytes) -> list[list[str]]:
    filas = [["usuario", "contraseña"]]
    for linea in datos.decode("utf-8-sig", errors="replace").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        partes = re.split(r"[:,;\t]", linea, maxsplit=1)
        filas.append([partes[0].strip(), partes[1].strip() if len(partes) > 1 else ""])
    return filas


def _parse_bool(valor: str) -> bool | None:
    v = _sin_acentos(valor.strip().lower())
    if v in {_sin_acentos(x) for x in _SI}:
        return True
    if v in {_sin_acentos(x) for x in _NO}:
        return False
    return None


def _parse_fecha(valor: str) -> datetime | None:
    v = valor.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            pass
    return None


def parse_archivo(nombre: str, datos: bytes) -> tuple[list[dict], list[dict]]:
    """Devuelve (filas_validas, errores). Cada fila válida es un dict con
    username, password ('' si no vino), display_name, email, enabled
    (None si no vino), expires_at (None si no vino) y `fila` (nº en el
    archivo, contando el encabezado como 1). Cada error: {fila, usuario,
    motivo}. Las filas con problemas se reportan y NO se importan; el resto
    sigue adelante."""
    if len(datos) > MAX_BYTES:
        raise ValueError(f"El archivo supera el máximo de {MAX_BYTES // (1024 * 1024)} MB.")
    ext = (nombre or "").lower().rsplit(".", 1)[-1] if "." in (nombre or "") else ""
    if ext == "xlsx":
        filas = _leer_xlsx(datos)
    elif ext == "txt":
        filas = _leer_txt(datos)
    elif ext in ("csv", ""):
        filas = _leer_csv(datos)
    else:
        raise ValueError("Formato no soportado: usa .csv, .xlsx o .txt.")

    filas = [f for f in filas if any(c for c in f)]
    if not filas:
        raise ValueError("El archivo está vacío.")

    columnas = [_clave_columna(c) for c in filas[0]]
    if "username" not in columnas:
        raise ValueError(
            "No se encontró la columna del usuario. La primera fila debe ser el encabezado "
            "y tener una columna llamada «usuario» (o username)."
        )
    cuerpo = filas[1:]
    if len(cuerpo) > MAX_FILAS:
        raise ValueError(f"Demasiadas filas ({len(cuerpo)}): el máximo es {MAX_FILAS} por archivo.")

    validas, errores, vistos = [], [], set()
    for i, fila in enumerate(cuerpo, start=2):
        d = {c: (fila[j].strip() if j < len(fila) else "") for j, c in enumerate(columnas) if c}
        usuario = d.get("username", "")
        if not usuario:
            errores.append({"fila": i, "usuario": "", "motivo": "Falta el usuario."})
            continue
        if not USERNAME_PATTERN.match(usuario):
            errores.append({"fila": i, "usuario": usuario, "motivo":
                            "Usuario inválido: 1 a 64 caracteres, solo letras, números, punto, guion y guion bajo."})
            continue
        if usuario.lower() in vistos:
            errores.append({"fila": i, "usuario": usuario, "motivo": "Usuario repetido en el archivo."})
            continue
        password = d.get("password", "")
        if password and not (8 <= len(password) <= 100):
            errores.append({"fila": i, "usuario": usuario, "motivo": "La contraseña debe tener entre 8 y 100 caracteres (déjala vacía para generar una)."})
            continue
        email = d.get("email", "")
        if email and (len(email) > 255 or not EMAIL_PATTERN.match(email)):
            errores.append({"fila": i, "usuario": usuario, "motivo": f"Correo inválido: {email}"})
            continue
        nombre_m = d.get("display_name", "")
        if len(nombre_m) > 255:
            errores.append({"fila": i, "usuario": usuario, "motivo": "El nombre supera los 255 caracteres."})
            continue
        habilitado = None
        if d.get("enabled"):
            habilitado = _parse_bool(d["enabled"])
            if habilitado is None:
                errores.append({"fila": i, "usuario": usuario, "motivo": f"Valor de «habilitado» no reconocido: {d['enabled']} (usa si/no)."})
                continue
        caduca = None
        if d.get("expires_at"):
            caduca = _parse_fecha(d["expires_at"])
            if caduca is None:
                errores.append({"fila": i, "usuario": usuario, "motivo": f"Fecha de caducidad inválida: {d['expires_at']} (usa AAAA-MM-DD)."})
                continue
        vistos.add(usuario.lower())
        validas.append({
            "fila": i, "username": usuario, "password": password,
            "display_name": nombre_m or None, "email": email or None,
            "enabled": habilitado, "expires_at": caduca,
        })
    return validas, errores


# ---------------------------------------------------------------------------
# Salida: plantilla y exportación
# ---------------------------------------------------------------------------

def _xlsx_bytes(encabezado: list[str], filas: list[list]) -> bytes:
    from app.utils.csv_seguro import fila as _seguro
    filas = [_seguro(f) for f in filas]
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Usuarios"
    ws.append(encabezado)
    for c in ws[1]:
        c.font = Font(bold=True)
    for f in filas:
        ws.append(f)
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = max(12, min(40, max(len(str(c.value or "")) for c in col) + 2))
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _csv_bytes(encabezado: list[str], filas: list[list]) -> bytes:
    from app.utils.csv_seguro import fila as _seguro
    filas = [_seguro(f) for f in filas]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(encabezado)
    w.writerows(filas)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def plantilla(formato: str) -> bytes:
    if formato == "xlsx":
        return _xlsx_bytes(COLUMNAS_PLANTILLA, FILAS_EJEMPLO)
    return _csv_bytes(COLUMNAS_PLANTILLA, FILAS_EJEMPLO)


COLUMNAS_EXPORT = ["usuario", "nombre", "email", "origen", "habilitado", "caduca"]


def exportar(formato: str, filas: list[list]) -> bytes:
    if formato == "xlsx":
        return _xlsx_bytes(COLUMNAS_EXPORT, filas)
    return _csv_bytes(COLUMNAS_EXPORT, filas)
