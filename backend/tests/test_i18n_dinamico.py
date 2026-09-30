"""Traducción de mensajes del backend con partes variables (app/i18n.py)."""
from app.i18n import traducir_dinamico


def test_mensaje_fijo_se_traduce_por_clave_exacta():
    assert traducir_dinamico("La contraseña del backup no es correcta.", "en") == "The backup password is not correct."
    assert traducir_dinamico("La contraseña del backup no es correcta.", "pt") == "A senha do backup não está correta."


def test_mensaje_con_partes_variables_reinserta_los_valores():
    m = "la lista «/etc/squid/x» no se subió junto con el squid.conf (súbela para importar esta ACL)"
    assert traducir_dinamico(m, "en") == "the list «/etc/squid/x» was not uploaded with squid.conf (upload it to import this ACL)"
    assert traducir_dinamico("27 entradas leídas de «ip_moviles»", "en") == "27 entries read from «ip_moviles»"
    assert traducir_dinamico("27 entradas leídas de «ip_moviles»", "pt") == "27 entradas lidas de «ip_moviles»"


def test_espanol_no_se_toca_y_lo_desconocido_sale_igual():
    assert traducir_dinamico("27 entradas leídas de «x»", "es") == "27 entradas leídas de «x»"
    assert traducir_dinamico("un mensaje que nadie tradujo 123", "en") == "un mensaje que nadie tradujo 123"


def test_plantilla_mas_especifica_gana():
    assert traducir_dinamico("Usuario no válido en el backup: «ana».", "en") == "Invalid user in the backup: «ana»."
    assert traducir_dinamico("«datos.json» es demasiado grande.", "en") == "«datos.json» is too large."
