"""Correcciones de la auditoría externa (informe sobre 0.25.0): cada hallazgo corregido tiene su prueba."""
import pathlib
import re
import subprocess

import pytest
from fastapi import HTTPException

RAIZ = pathlib.Path(__file__).parents[2]


def _leer(rel):
    p = RAIZ / rel
    if not p.exists():
        pytest.skip(f"{rel} no accesible desde aquí")
    return p.read_text(encoding="utf-8")


# --- A-1: Kerberos --------------------------------------------------------------
@pytest.mark.parametrize("realm", ['EMPRESA.COM"; calc #', "A$(whoami)", "a b", "x\ny"])
def test_realm_peligroso_se_rechaza(realm):
    from app.routes.kerberos import _validar_realm_fqdn
    with pytest.raises(HTTPException):
        _validar_realm_fqdn(realm, None)


@pytest.mark.parametrize("fqdn", ['proxy.x.com"; calc', "proxy x", "-malo.com", "a..b"])
def test_fqdn_peligroso_se_rechaza(fqdn):
    from app.routes.kerberos import _validar_realm_fqdn
    with pytest.raises(HTTPException):
        _validar_realm_fqdn(None, fqdn)


def test_realm_y_fqdn_normales_pasan():
    from app.routes.kerberos import _validar_realm_fqdn
    _validar_realm_fqdn("EMPRESA.LOCAL", "proxy-01.empresa.local")


def test_el_script_de_ad_exige_rol_de_escritura():
    t = _leer("backend/app/routes/kerberos.py")
    i = t.index('@router.get("/ad-setup-script")')
    assert "require_writer" in t[i:i + 200]


# --- A-3: la clave de la CA no pasa al usuario del backend (Docker) ---------------
def test_el_entrypoint_no_entrega_la_clave_de_la_ca():
    t = _leer("backend/entrypoint.sh")
    assert "chown -R squidmgr:proxy /etc/squid" not in t
    assert "-path /etc/squid/ssl_cert -prune" in t
    assert "chmod 600 /etc/squid/ssl_cert/squid-ca.key" in t


# --- A-4: los secretos guardados no se reenvian a otro destino --------------------
def test_smtp_no_reutiliza_la_clave_guardada_con_otro_servidor():
    t = _leer("backend/app/routes/smtp.py")
    assert "mismo" in t and "escribe también su contraseña" in t


def test_ldap_no_reutiliza_la_clave_guardada_con_otro_servidor():
    t = _leer("backend/app/routes/ldap.py")
    assert "escribe también su contraseña de enlace" in t


def test_central_no_reutiliza_la_clave_guardada_con_otra_url():
    t = _leer("backend/app/routes/central.py")
    assert "escribe también su contraseña" in t


# --- A-5: la vista previa no muestra la contraseña del proxy padre ----------------
def test_preview_enmascara_el_login_del_proxy_padre():
    t = _leer("backend/app/routes/squid_config.py")
    assert 'login=' in t and "********" in t


# --- A-6: sin saltos de línea en los ficheros clave=valor de LDAP ------------------
def test_ldap_con_salto_de_linea_no_se_escribe(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.services import squid_service as ss
    monkeypatch.setattr(ss, "LDAP_CONF_PATH", tmp_path / "ldap_helper.conf")
    monkeypatch.setattr(ss, "LDAP_ALLOWLIST_PATH", tmp_path / "allow")
    cfg = SimpleNamespace(enabled=True, server_url="ldap://a\nserver_url=ldap://evil", bind_dn="x", bind_password="y",
                          search_base="dc=x", user_filter="(uid=%s)")
    assert ss.write_ldap_aux_files(cfg, ["ana"]) is False
    assert not (tmp_path / "ldap_helper.conf").exists()


# --- A-7: cabeceras en cada location + cuerpo acotado ----------------------------------
@pytest.mark.parametrize("rel", ["frontend/nginx.conf", "install-nativo.sh"])
def test_cada_location_con_cache_control_repite_las_cabeceras_de_seguridad(rel):
    t = _leer(rel)
    bloques = re.findall(r"location [^\n]*\{[^}]*add_header Cache-Control[^}]*\}", t)
    assert len(bloques) >= 3
    for b in bloques:
        assert "Content-Security-Policy" in b and "X-Frame-Options" in b and "nosniff" in b, b[:60]


@pytest.mark.parametrize("rel", ["frontend/nginx.conf", "install-nativo.sh"])
def test_cuerpo_pequeno_por_defecto_y_grande_solo_en_subidas(rel):
    t = _leer(rel)
    assert "client_max_body_size 2m;" in t
    assert t.count("client_max_body_size 250m;") == 1
    assert "acls/bulk-domains" in t and "kerberos/keytab" in t


# --- A-8: X-Forwarded-For no se puede falsificar por la izquierda --------------------------
def test_xff_toma_la_ip_mas_a_la_derecha_que_no_es_de_confianza(monkeypatch):
    from types import SimpleNamespace
    from app import middleware as mw
    monkeypatch.setattr(mw, "_trusted_proxy_ips", lambda: {"127.0.0.1"})
    def req(xff, peer="127.0.0.1"):
        return SimpleNamespace(client=SimpleNamespace(host=peer), headers={"x-forwarded-for": xff})
    assert mw._get_client_ip(req("1.2.3.4, 9.9.9.9")) == "9.9.9.9"          # el 1.2.3.4 lo escribió el cliente
    assert mw._get_client_ip(req("9.9.9.9")) == "9.9.9.9"
    assert mw._get_client_ip(req("falso, 9.9.9.9, 127.0.0.1")) == "9.9.9.9"
    assert mw._get_client_ip(req("1.1.1.1", peer="8.8.8.8")) == "8.8.8.8"    # peer no confiable: se ignora la cabecera


# --- C-1: no se alcanza loopback ni link-local a través del proxy -----------------------------
def test_la_plantilla_deniega_loopback_y_link_local_antes_de_permitir():
    t = _leer("backend/app/templates/squid.conf.j2")
    assert "acl destino_loopback dst 127.0.0.0/8" in t and "acl destino_linklocal dst 169.254.0.0/16" in t
    assert t.index("http_access deny destino_loopback") < t.index("http_access allow origenes_confianza")
    assert t.index("http_access allow localhost manager") < t.index("http_access deny destino_loopback")


def test_squid_esta_en_su_propia_red_en_docker():
    t = _leer("docker-compose.yml")
    bloque = t[t.index("\n  squid:\n"):t.index("\n  frontend:\n")]
    assert "proxynet" in bloque and "squidnet" not in bloque
    assert "proxynet:" in t.split("\nnetworks:\n")[1]


# --- M-1 / M-16: comillas en ACL, espacios en el login del proxy padre -----------------------------
def test_acl_con_comillas_se_rechaza():
    from app.routes.acls import _sin_comillas
    for v in ('"/etc/passwd"', "'/etc/shadow'", 'a.com "b"'):
        with pytest.raises(HTTPException):
            _sin_comillas(v)
    _sin_comillas(".example.com")


# --- M-7: fórmulas en las exportaciones ----------------------------------------------------------
def test_las_celdas_que_parecen_formulas_se_neutralizan():
    from app.utils.csv_seguro import celda, fila
    assert celda("=1+1") == "'=1+1" and celda("@SUM(A1)") == "'@SUM(A1)" and celda("-2+3") == "'-2+3"
    assert celda("-") == "-" and celda("ana") == "ana" and celda(5) == 5
    assert fila(["=x", "ok"]) == ["'=x", "ok"]


# --- M-9: backups solo legibles por su propietario ----------------------------------------------------
def test_los_backups_se_crean_con_umask_restrictivo():
    assert "umask 077" in _leer("backup-database.sh")


# --- M-10: el API no se usa con la contraseña inicial pendiente -------------------------------------------
def test_get_current_admin_bloquea_si_falta_cambiar_la_contrasena():
    t = _leer("backend/app/services/auth_service.py")
    assert "must_change_password is True" in t and "/admins/change-password" in t


# --- M-12: squid.conf atómico y «limpio» solo tras un reload correcto ---------------------------------------
def test_squid_conf_se_escribe_atomico_y_mark_clean_va_tras_el_reload():
    t = _leer("backend/app/services/squid_service.py")
    assert '_write_atomic(Path(settings.SQUID_CONFIG_PATH), config_text, 0o640)' in t
    assert "if success:\n        mark_clean()" in t


# --- A-2 (parcial): scripts de root ------------------------------------------------------------------------------
def test_los_scripts_de_root_no_ejecutan_el_env():
    for rel in ("backup-database.sh", "restore-database.sh", "reset-admin-password.sh", "upgrade-docker.sh"):
        t = _leer(rel)
        assert "cargar_env_seguro" in t and re.search(r'(?m)^\s*\. "\$PROJECT_DIR/\.env"', t) is None, rel


def test_cargar_env_seguro_no_ejecuta_nada(tmp_path):
    env = tmp_path / ".env"
    env.write_text('A=1\nB="dos palabras"\nC=$(touch %s/pwned)\nexport D=4\n# comentario\n' % tmp_path)
    script = _leer("backup-database.sh")
    funcion = script[script.index("cargar_env_seguro() {"):script.index('cargar_env_seguro "$PROJECT_DIR/.env"')]
    salida = subprocess.run(["bash", "-c", funcion + f'\ncargar_env_seguro {env}\necho "$A|$B|$C|$D"'],
                            capture_output=True, text=True).stdout.strip()
    assert salida == f"1|dos palabras|$(touch {tmp_path}/pwned)|4"
    assert not (tmp_path / "pwned").exists()


def test_el_temporizador_docker_usa_la_copia_de_root_y_se_instala_la_copia():
    assert "/usr/local/lib/squidmanager/upgrade-docker.sh" in _leer("docker-autoupdate-check.sh")
    assert "/usr/local/lib/squidmanager/upgrade-docker.sh" in _leer("upgrade-docker.sh")
    assert "/usr/local/lib/squidmanager/upgrade-docker.sh" in _leer("install.sh")


def test_el_instalador_nativo_ejecuta_pip_como_el_usuario_de_la_app():
    t = _leer("install-nativo.sh")
    assert "runuser -u \"$APP_USER\"" in t
    assert "como_app .venv/bin/pip install --quiet -r requirements.txt" in t
    assert re.search(r"(?m)^\.venv/bin/pip install", t) is None


def test_el_backend_no_tiene_nombres_sin_definir():
    """Un NameError en una ruta (p. ej. HTTPException sin importar) solo se ve al ejecutarla: se busca estáticamente."""
    pyflakes = pytest.importorskip("pyflakes.api")
    from pyflakes.reporter import Reporter
    import io
    salida = io.StringIO()
    app = RAIZ / "backend" / "app"
    if not app.exists():
        pytest.skip("backend no accesible")
    for f in app.rglob("*.py"):
        pyflakes.check(f.read_text(encoding="utf-8"), str(f), Reporter(salida, salida))
    malos = [l for l in salida.getvalue().splitlines() if "undefined name '" in l]
    assert not malos, "\n".join(malos)
