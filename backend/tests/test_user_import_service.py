"""Importar/exportar usuarios masivamente (app/services/user_import_service.py)."""
import io

import pytest

from app.services import user_import_service as svc


def _csv(texto: str) -> bytes:
    return texto.encode("utf-8")


def test_csv_basico_con_encabezados_en_espanol():
    filas, errores = svc.parse_archivo("u.csv", _csv(
        "usuario,contraseña,nombre,email,habilitado,caduca\n"
        "jperez,,Juan Pérez,jperez@empresa.com,si,2026-12-31\n"
        "mgomez,Clave-Segura-2026,María,,no,\n"))
    assert errores == []
    assert [f["username"] for f in filas] == ["jperez", "mgomez"]
    assert filas[0]["display_name"] == "Juan Pérez" and filas[0]["email"] == "jperez@empresa.com"
    assert filas[0]["enabled"] is True and filas[0]["expires_at"].year == 2026
    assert filas[1]["enabled"] is False and filas[1]["password"] == "Clave-Segura-2026"


def test_acepta_punto_y_coma_y_bom_de_excel():
    filas, errores = svc.parse_archivo("u.csv", _csv("﻿usuario;email\nana;ana@x.com\n"))
    assert errores == [] and filas[0]["email"] == "ana@x.com"


def test_encabezados_en_ingles_y_sin_acentos():
    filas, _ = svc.parse_archivo("u.csv", _csv("Username,Password,Display_Name\nbob,Abcdefg123,Bob\n"))
    assert filas[0]["username"] == "bob" and filas[0]["display_name"] == "Bob"


def test_txt_una_linea_por_usuario():
    filas, errores = svc.parse_archivo("u.txt", _csv("# comentario\nana\nbob:Clave12345\ncarla,Otra-Clave-9\n\n"))
    assert errores == []
    assert [(f["username"], f["password"]) for f in filas] == [("ana", ""), ("bob", "Clave12345"), ("carla", "Otra-Clave-9")]


def test_xlsx_ida_y_vuelta():
    datos = svc.plantilla("xlsx")
    filas, errores = svc.parse_archivo("plantilla.xlsx", datos)
    assert errores == [] and [f["username"] for f in filas] == ["jperez", "mgomez"]


def test_fila_con_problemas_se_reporta_y_las_demas_siguen():
    filas, errores = svc.parse_archivo("u.csv", _csv(
        "usuario,contraseña,email,habilitado,caduca\n"
        "bien,,,,\n"
        "mal usuario,,,,\n"
        "corta,123,,,\n"
        "conmail,,no-es-un-correo,,\n"
        "estado,,,quizas,\n"
        "fecha,,,,31-31-2026\n"
        "bien,,,,\n"
        ",,,,\n"))
    assert [f["username"] for f in filas] == ["bien"]
    motivos = {e["fila"]: e["motivo"] for e in errores}
    assert "inválido" in motivos[3] and "8 y 100" in motivos[4] and "Correo" in motivos[5]
    assert "habilitado" in motivos[6] and "fecha" in motivos[7].lower() and "repetido" in motivos[8]


def test_sin_columna_de_usuario_es_un_error_claro():
    with pytest.raises(ValueError, match="columna del usuario"):
        svc.parse_archivo("u.csv", _csv("nombre,email\nJuan,j@x.com\n"))


def test_formato_no_soportado_y_archivo_vacio():
    with pytest.raises(ValueError, match="Formato"):
        svc.parse_archivo("u.pdf", b"x")
    with pytest.raises(ValueError, match="vacío"):
        svc.parse_archivo("u.csv", b"\n\n")


def test_limite_de_filas():
    cuerpo = "usuario\n" + "\n".join(f"u{i}" for i in range(svc.MAX_FILAS + 1))
    with pytest.raises(ValueError, match="Demasiadas filas"):
        svc.parse_archivo("u.csv", _csv(cuerpo))


def test_exportar_csv_lleva_bom_para_excel():
    datos = svc.exportar("csv", [["ana", "Ana", "a@x.com", "local", "si", ""]])
    assert datos.startswith("﻿".encode("utf-8")) and b"ana,Ana,a@x.com,local,si," in datos
