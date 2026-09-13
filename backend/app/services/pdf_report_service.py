"""Informe ejecutivo en PDF de "Actividad de red".

Reusa exactamente los mismos datos que ya se ven en el panel (metrics_service):
no hay ningun calculo nuevo acá, solo otro formato de salida para poder
adjuntar/imprimir un resumen sin tener que sacar capturas de pantalla.
"""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from app.services import metrics_service
from app.utils import utcnow

_ETIQUETA_VENTANA = {
    None: "Últimas 1.000 peticiones registradas",
    "1h": "Última hora",
    "24h": "Últimas 24 horas",
    "7d": "Últimos 7 días",
}


def _formatear_bytes(n: int) -> str:
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unidad}" if unidad != "B" else f"{n} {unidad}"
        n /= 1024
    return f"{n:.1f} PB"


def generar_pdf_actividad(ventana: str | None, db=None) -> bytes:
    """Arma el PDF y devuelve los bytes listos para servir como adjunto."""
    seconds = metrics_service.VENTANAS_SEGUNDOS.get(ventana) if ventana else None

    usuarios = metrics_service.get_top_users(10, seconds=seconds)
    dominios = metrics_service.get_top_domains(10, denied_only=False, seconds=seconds)
    bloqueados_dominio = metrics_service.get_top_domains(10, denied_only=True, seconds=seconds)
    bloqueados_usuario = metrics_service.get_top_blocked_users(10, db=db, seconds=seconds)
    totales = metrics_service.get_totales_actividad(seconds=seconds)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle("TituloReporte", parent=estilos["Title"], fontSize=18, spaceAfter=4)
    estilo_subtitulo = ParagraphStyle("Subtitulo", parent=estilos["Normal"], textColor=colors.HexColor("#5F6B7A"), spaceAfter=16)
    estilo_seccion = ParagraphStyle("Seccion", parent=estilos["Heading2"], spaceBefore=18, spaceAfter=8, textColor=colors.HexColor("#0B497C"))

    elementos = []
    elementos.append(Paragraph("SquidManager — Actividad de red", estilo_titulo))
    ventana_texto = _ETIQUETA_VENTANA.get(ventana, ventana)
    generado = utcnow().strftime("%Y-%m-%d %H:%M UTC")
    elementos.append(Paragraph(f"{ventana_texto} · generado el {generado}", estilo_subtitulo))

    estilo_tabla = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F1FB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0B497C")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E4E7EB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    # --- Usuarios ---
    elementos.append(Paragraph(
        f"Usuarios por consumo (total real: {_formatear_bytes(totales['usuarios']['bytes'])}, "
        f"{totales['usuarios']['requests']} peticiones, {totales['usuarios']['count']} usuarios)",
        estilo_seccion,
    ))
    filas = [["#", "Usuario", "Datos", "Peticiones"]]
    for i, u in enumerate(usuarios, 1):
        filas.append([str(i), u["user"], _formatear_bytes(u["bytes"]), str(u["requests"])])
    elementos.append(Table(filas, colWidths=[1.2 * cm, 6 * cm, 4 * cm, 4 * cm], style=estilo_tabla))

    # --- Sitios visitados ---
    elementos.append(Paragraph(
        f"Sitios visitados (total real: {totales['dominios']['requests']} peticiones, "
        f"{totales['dominios']['count']} dominios distintos)",
        estilo_seccion,
    ))
    filas = [["#", "Dominio", "Peticiones", "Datos"]]
    for i, d in enumerate(dominios, 1):
        filas.append([str(i), d["domain"], str(d["requests"]), _formatear_bytes(d["bytes"])])
    elementos.append(Table(filas, colWidths=[1.2 * cm, 6 * cm, 4 * cm, 4 * cm], style=estilo_tabla))

    # --- Sitios bloqueados ---
    elementos.append(Paragraph(
        f"Sitios bloqueados (total real: {totales['dominios_bloqueados']['requests']} peticiones denegadas, "
        f"{totales['dominios_bloqueados']['count']} dominios distintos)",
        estilo_seccion,
    ))
    filas = [["#", "Dominio", "Peticiones denegadas"]]
    for i, d in enumerate(bloqueados_dominio, 1):
        filas.append([str(i), d["domain"], str(d["requests"])])
    elementos.append(Table(filas, colWidths=[1.2 * cm, 8 * cm, 5.2 * cm], style=estilo_tabla))

    # --- Usuarios con más bloqueos ---
    elementos.append(Paragraph(
        f"Usuarios con más bloqueos (total real: {totales['usuarios_bloqueados_requests']} peticiones denegadas, "
        f"{bloqueados_usuario['anonymous_blocked']} sin usuario identificado)",
        estilo_seccion,
    ))
    filas = [["#", "Usuario", "Bloqueos", "Cuenta"]]
    for i, u in enumerate(bloqueados_usuario["users"], 1):
        estado = {"disabled": "Deshabilitada", "enabled": "Activa", "unknown": "—"}[u["account_status"]]
        filas.append([str(i), u["user"], str(u["blocked_requests"]), estado])
    elementos.append(Table(filas, colWidths=[1.2 * cm, 6 * cm, 4 * cm, 4 * cm], style=estilo_tabla))

    doc.build(elementos)
    return buffer.getvalue()
