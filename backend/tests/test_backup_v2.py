"""Backup formato 2 (app/services/backup_v2_service.py): empaquetado, firma,
cifrado de secretos y validación. La ida y vuelta completa contra PostgreSQL se
probó contra una base real; aquí, lo que no necesita base de datos."""
import io
import json
import zipfile

import pytest

from app.services import backup_v2_service as b2


def _paquete_zip(config=None, secretos=None, pasw=None, listas=None, version_formato=2, alterar=None):
    config = config if config is not None else {"squid_settings": [], "modulos": {"analisis": True}}
    partes = {"config.json": json.dumps(config).encode()}
    if secretos is not None:
        partes["secrets.enc"] = b2.cifrar_secretos(secretos, pasw)
    for n, d in (listas or {}).items():
        partes[f"acl_lists/{n}.txt.gz"] = d
    manifest = {"formato": b2.FORMATO, "version_formato": version_formato, "app_version": "0.0.0",
                "creado": "2026-01-01T00:00:00Z", "contiene_secretos": secretos is not None,
                "conteos": {"squid_settings": 0}, "sha256": {n: b2._sha256(d) for n, d in partes.items()}}
    if alterar:
        alterar(manifest, partes)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        for n, d in partes.items():
            z.writestr(n, d)
    return salida.getvalue()


def test_secretos_cifrados_ida_y_vuelta():
    s = {"proxy_users": {"ana": {"password_hash": "$2b$x", "digest_ha1": "abc"}}}
    blob = b2.cifrar_secretos(s, "una-clave-larga")
    assert b"password_hash" not in blob and b"$2b$x" not in blob        # nada en claro
    assert b2.descifrar_secretos(blob, "una-clave-larga") == s


def test_contrasena_incorrecta_se_explica():
    blob = b2.cifrar_secretos({"a": 1}, "correcta-123")
    with pytest.raises(b2.BackupError, match="no es correcta"):
        b2.descifrar_secretos(blob, "otra-clave-1")


def test_paquete_valido_sin_secretos():
    p = b2.leer_paquete(_paquete_zip())
    assert p.secretos is None and not p.requiere_passphrase and p.config["modulos"] == {"analisis": True}


def test_paquete_con_secretos_pide_contrasena_y_la_usa():
    datos = _paquete_zip(secretos={"x": {"_": {"k": "v"}}}, pasw="clave-secreta")
    sin = b2.leer_paquete(datos)
    assert sin.requiere_passphrase and sin.secretos is None
    con = b2.leer_paquete(datos, "clave-secreta")
    assert con.secretos == {"x": {"_": {"k": "v"}}}
    with pytest.raises(b2.BackupError):
        b2.leer_paquete(datos, "equivocada")


def test_una_parte_alterada_se_detecta_por_la_firma():
    def alterar(manifest, partes):
        manifest["sha256"]["config.json"] = "0" * 64
    with pytest.raises(b2.BackupError, match="dañado"):
        b2.leer_paquete(_paquete_zip(alterar=alterar))


def test_formato_mas_nuevo_que_el_soportado_se_rechaza_con_indicacion():
    with pytest.raises(b2.BackupError, match="más nuevo"):
        b2.leer_paquete(_paquete_zip(version_formato=99))


def test_archivo_que_no_es_zip_o_no_es_nuestro():
    with pytest.raises(b2.BackupError, match="válido"):
        b2.leer_paquete(b"esto no es un zip")
    sal = io.BytesIO()
    with zipfile.ZipFile(sal, "w") as z:
        z.writestr("manifest.json", json.dumps({"formato": "otro"}))
    with pytest.raises(b2.BackupError, match="No es un backup"):
        b2.leer_paquete(sal.getvalue())


def test_listas_de_acl_se_leen_por_nombre():
    import gzip
    p = b2.leer_paquete(_paquete_zip(listas={"mi_lista": gzip.compress(b"a.com\nb.com\n")}))
    assert list(p.listas) == ["mi_lista"]
    assert gzip.decompress(p.listas["mi_lista"]).split() == [b"a.com", b"b.com"]


def test_inspeccion_resume_sin_ceros():
    p = b2.leer_paquete(_paquete_zip())
    r = b2.inspeccionar(p)
    assert r["app_version"] == "0.0.0" and r["conteos"] == {}


def test_ajustes_peligrosos_se_rechazan_al_restaurar():
    with pytest.raises(b2.BackupError):
        b2._validar_setting("dns_nameservers", "no-es-una-ip")
    with pytest.raises(b2.BackupError):
        b2._validar_setting("extra_safe_ports", "80 abc")
    assert b2._validar_setting("extra_safe_ports", "873 9000-9100") == "873 9000-9100"
    with pytest.raises(b2.BackupError):
        b2._validar_setting("visible_hostname", "a\nhttp_access allow all")


def test_entidades_no_repiten_nombre_ni_exportan_secretos_como_publicos():
    nombres = [e.nombre for e in b2.ENTIDADES]
    assert len(nombres) == len(set(nombres))
    # Un secreto nunca puede estar también en la lista de columnas excluidas ni duplicado.
    for e in b2.ENTIDADES:
        assert not (e.secretas & e.excluir)


def test_ninguna_tabla_sensible_a_medias_todas_las_columnas_secretas_existen():
    """Cada columna secreta declarada existe de verdad en su modelo (si alguien
    la renombra, el backup dejaría de protegerla sin que nada lo avise)."""
    from sqlalchemy import inspect as sa_inspect
    for e in b2.ENTIDADES:
        cols = {c.key for c in sa_inspect(b2._modelo(e)).columns}
        assert e.secretas <= cols, (e.nombre, e.secretas - cols)
        assert e.excluir <= cols, (e.nombre, e.excluir - cols)
        assert set(e.clave) <= cols, (e.nombre, set(e.clave) - cols)
