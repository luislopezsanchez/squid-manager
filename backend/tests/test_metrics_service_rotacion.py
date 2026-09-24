"""Bug real encontrado el 2026-09-24: con rotación diaria (squid-logrotate.
native), el access.log activo casi nunca tiene más de ~24-36h de datos.
Pedir una ventana de "7d" o "30d" (get_top_users, get_top_domains, etc., que
delegan en _read_recent_logs) agotaba el archivo activo sin llegar nunca al
corte real, y la función devolvía en silencio solo esas horas, como si fuera
la ventana completa pedida -sin ningún aviso de que la ventana no se cumplió.
"""

import gzip

from app.services import metrics_service


def _linea(ts: float, ip="10.0.0.1", user="-"):
    return f"{ts:.3f}      1 {ip} TCP_MISS/200 100 GET http://ejemplo.com/ {user} HIER_DIRECT/1.2.3.4 text/html"


def test_rotated_log_files_ordena_del_mas_reciente_al_mas_viejo(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "access.log-20260920.gz").write_bytes(b"")
    (archive / "access.log-20260924").write_text("")  # el mas reciente, sin comprimir (delaycompress)
    (archive / "access.log-20260922.gz").write_bytes(b"")
    (archive / "otro-archivo.txt").write_text("")  # no matchea el patron, se ignora
    monkeypatch.setattr(metrics_service, "ACCESS_LOG_PATH", str(tmp_path / "access.log"))

    rutas = metrics_service._rotated_log_files()
    nombres = [p.split("/")[-1] for p in rutas]
    assert nombres == ["access.log-20260924", "access.log-20260922.gz", "access.log-20260920.gz"]


def test_rotated_log_files_sin_directorio_de_archivo_no_revienta(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics_service, "ACCESS_LOG_PATH", str(tmp_path / "access.log"))
    assert metrics_service._rotated_log_files() == []


def test_iter_rotated_lines_reverse_lee_gz_y_texto_plano(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "access.log-20260924").write_text(_linea(200) + "\n" + _linea(300) + "\n")
    with gzip.open(archive / "access.log-20260923.gz", "wt") as f:
        f.write(_linea(100) + "\n")
    monkeypatch.setattr(metrics_service, "ACCESS_LOG_PATH", str(tmp_path / "access.log"))

    lineas = list(metrics_service._iter_rotated_lines_reverse())
    # El archivo mas reciente primero, y dentro de cada uno, de la ultima
    # linea a la primera.
    assert lineas == [_linea(300), _linea(200), _linea(100)]


def test_ventana_que_el_activo_cubre_solo_no_toca_los_rotados(monkeypatch):
    """Caso normal (el activo tiene de sobra para la ventana pedida, ej. 1h
    de ventana con 18h en el activo): la lectura corta apenas pasa el cutoff
    -no hace falta ni tocar archivos rotados. Si se llamaran, este test lo
    detecta."""
    ahora = 2_000_000.0
    monkeypatch.setattr(metrics_service.time, "time", lambda: ahora)
    # La más vieja (hace 2h) ya está fuera de la ventana de 1h pedida: ahí
    # el activo llega al corte solo, sin agotarse. Lista en orden
    # cronológico (más vieja primero); reversed() imita el orden real de
    # iter_lines_reverse (más nueva primero).
    lineas_activo = [_linea(ahora - 7200), _linea(ahora - 10), _linea(ahora - 5)]
    monkeypatch.setattr(
        "app.services.log_service.iter_lines_reverse",
        lambda path, max_lines: reversed(lineas_activo),
    )

    def _rotados_no_deberia_llamarse():
        raise AssertionError("no debería leer rotados si el activo ya cubrió la ventana")
        yield  # pragma: no cover

    monkeypatch.setattr(metrics_service, "_iter_rotated_lines_reverse", _rotados_no_deberia_llamarse)

    resultado = metrics_service._read_recent_logs(seconds=3600)
    assert len(resultado) == 2


def test_ventana_grande_sigue_en_los_rotados_si_el_activo_no_alcanza(monkeypatch):
    """El bug en sí: el activo tiene solo un puñado de líneas recientes (se
    agota sin llegar al corte de 7 días) -antes esto se devolvía tal cual,
    como si fueran los 7 días completos."""
    ahora = 2_000_000.0
    monkeypatch.setattr(metrics_service.time, "time", lambda: ahora)
    # Activo: un par de líneas de "hoy", nada más -se agota sin llegar al
    # corte de 7 días (604800s atrás).
    lineas_activo = [_linea(ahora - 10), _linea(ahora - 5)]
    monkeypatch.setattr(
        "app.services.log_service.iter_lines_reverse",
        lambda path, max_lines: reversed(lineas_activo),
    )
    # Rotados: una línea de "ayer", dentro de la ventana de 7 días.
    lineas_rotadas = [_linea(ahora - 86400)]
    monkeypatch.setattr(metrics_service, "_iter_rotated_lines_reverse", lambda: iter(lineas_rotadas))

    resultado = metrics_service._read_recent_logs(seconds=7 * 86400)
    assert len(resultado) == 3
    # Orden: de la más vieja a la más nueva (mismo criterio que el resto).
    assert resultado[0]["timestamp"] == ahora - 86400


def test_se_detiene_al_pasar_el_corte_dentro_de_un_rotado(monkeypatch):
    """Una vez que una línea de un rotado ya es más vieja que el corte, no
    hace falta -ni corresponde- seguir agregando entradas."""
    ahora = 2_000_000.0
    monkeypatch.setattr(metrics_service.time, "time", lambda: ahora)
    monkeypatch.setattr(
        "app.services.log_service.iter_lines_reverse",
        lambda path, max_lines: iter(()),  # activo vacío
    )
    lineas_rotadas = [
        _linea(ahora - 3600),      # dentro de la ventana de 24h
        _linea(ahora - 90000),     # ya fuera (>24h)
        _linea(ahora - 200000),    # mas vieja todavia -no deberia ni mirarse
    ]
    monkeypatch.setattr(metrics_service, "_iter_rotated_lines_reverse", lambda: iter(lineas_rotadas))

    resultado = metrics_service._read_recent_logs(seconds=86400)
    assert len(resultado) == 1
    assert resultado[0]["timestamp"] == ahora - 3600


def test_respeta_max_lines_entre_activo_y_rotados(monkeypatch):
    ahora = 2_000_000.0
    monkeypatch.setattr(metrics_service.time, "time", lambda: ahora)
    lineas_activo = [_linea(ahora - i) for i in range(3)]
    monkeypatch.setattr(
        "app.services.log_service.iter_lines_reverse",
        lambda path, max_lines: reversed(lineas_activo),
    )
    lineas_rotadas = [_linea(ahora - 86400 - i) for i in range(10)]
    monkeypatch.setattr(metrics_service, "_iter_rotated_lines_reverse", lambda: iter(lineas_rotadas))

    resultado = metrics_service._read_recent_logs(seconds=30 * 86400, max_lines=5)
    assert len(resultado) == 5


# --- _read_rango() / _entradas() (rango de fechas libre) --------------------

def test_read_rango_filtra_por_desde_y_hasta(monkeypatch):
    lineas = [_linea(100), _linea(200), _linea(300), _linea(400)]
    monkeypatch.setattr(
        "app.services.log_service.iter_lines_reverse",
        lambda path, max_lines: reversed(lineas),
    )
    monkeypatch.setattr(metrics_service, "_iter_rotated_lines_reverse", lambda: iter(()))

    resultado = metrics_service._read_rango(desde=150, hasta=350)
    assert [e["timestamp"] for e in resultado] == [200, 300]


def test_read_rango_sigue_en_rotados_si_desde_es_mas_viejo_que_el_activo(monkeypatch):
    lineas_activo = [_linea(300), _linea(400)]
    monkeypatch.setattr(
        "app.services.log_service.iter_lines_reverse",
        lambda path, max_lines: reversed(lineas_activo),
    )
    lineas_rotadas = [_linea(200), _linea(100)]
    monkeypatch.setattr(metrics_service, "_iter_rotated_lines_reverse", lambda: iter(lineas_rotadas))

    resultado = metrics_service._read_rango(desde=150, hasta=1000)
    assert [e["timestamp"] for e in resultado] == [200, 300, 400]


def test_entradas_usa_rango_solo_si_estan_los_dos_extremos(monkeypatch):
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: [{"marca": "ventana", "seconds": seconds}])
    monkeypatch.setattr(metrics_service, "_read_rango", lambda desde, hasta: [{"marca": "rango"}])

    # Sin desde/hasta (o con uno solo): usa la ventana relativa de siempre.
    assert metrics_service._entradas(seconds=3600) == [{"marca": "ventana", "seconds": 3600}]
    assert metrics_service._entradas(seconds=3600, desde=100) == [{"marca": "ventana", "seconds": 3600}]
    # Con los dos extremos: rango libre, sin importar que tambien venga seconds.
    assert metrics_service._entradas(seconds=3600, desde=100, hasta=200) == [{"marca": "rango"}]
