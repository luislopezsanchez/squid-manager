"""Informe en PDF de "Actividad de red".

Recoge lo mismo que ve la pantalla, pestaña por pestaña: usuarios, sitios
visitados, sitios bloqueados, usuarios con más bloqueos, IPs compartidas y
cuotas excedidas, cada uno con su gráfica de evolución cuando hay datos, el
periodo (ventana o rango libre) y la zona horaria. Se redacta en el idioma
del panel. No calcula nada nuevo: reusa metrics_service y rollup_service.
"""

from datetime import datetime
from io import BytesIO

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

from app.services import metrics_service, rollup_service
from app.services import timezone_service as tzs
from app.services.quota_service import cuotas_excedidas

_AZUL = colors.HexColor("#0B497C")
_NARANJA = colors.HexColor("#E0A036")
_ROJO = colors.HexColor("#C0392B")

_L = {
    "es": {
        "titulo": "SquidManager — Actividad de red", "gen": "generado el", "zona": "zona horaria",
        "v_none": "Últimas 1.000 peticiones registradas", "1h": "Última hora", "24h": "Últimas 24 horas",
        "7d": "Últimos 7 días", "30d": "Últimos 30 días", "rango": "Del {a} al {b}",
        "usuarios": "Usuarios por consumo", "sitios": "Sitios visitados", "bloq": "Sitios bloqueados",
        "bloq_u": "Usuarios con más bloqueos", "ips": "IPs compartidas (cuentas en un mismo equipo)",
        "cuotas": "Cuota excedida ({n} en este momento)",
        "tot_u": "total real: {b}, {r} peticiones, {n} usuarios", "tot_d": "total real: {r} peticiones, {n} dominios distintos",
        "tot_b": "total real: {r} peticiones denegadas, {n} dominios distintos",
        "tot_bu": "total real: {r} peticiones denegadas, {a} sin usuario identificado",
        "usuario": "Usuario", "datos": "Datos", "pet": "Peticiones", "dominio": "Dominio", "den": "Peticiones denegadas",
        "bloqueos": "Bloqueos", "cuenta": "Cuenta", "deshab": "Deshabilitada", "activa_c": "Activa",
        "ip": "IP", "usuarios_h": "Usuarios", "visto": "Visto (primera – última)", "nombre": "Nombre", "tipo": "Tipo",
        "consumido": "Consumido", "limite": "Límite", "estado": "Estado", "excedida": "Excedida el", "reinicio": "Se restablece",
        "grupo": "Grupo", "usuario_t": "Usuario", "activa": "Activa", "limitada": "Limitada", "cortada": "Cortada",
        "sin_cuotas": "Ninguna cuota está excedida en este momento.", "sin_datos": "Sin datos en este periodo.",
        "g_usuarios": "Usuarios activos por periodo", "g_sitios": "Sitios distintos por periodo",
        "g_bloq": "Peticiones bloqueadas por periodo", "g_bloq_u": "Usuarios con bloqueos por periodo",
        "g_ips": "IPs compartidas por periodo", "g_datos": "Datos transferidos por periodo (MB)",
        "estado_actual": "Estado actual, no depende del periodo elegido.", "desconocido": "—", "sin_reg": "sin registro",
    },
    "en": {
        "titulo": "SquidManager — Network activity", "gen": "generated on", "zona": "time zone",
        "v_none": "Last 1,000 logged requests", "1h": "Last hour", "24h": "Last 24 hours",
        "7d": "Last 7 days", "30d": "Last 30 days", "rango": "From {a} to {b}",
        "usuarios": "Users by usage", "sitios": "Sites visited", "bloq": "Blocked sites",
        "bloq_u": "Users with most blocks", "ips": "Shared IPs (accounts on the same machine)",
        "cuotas": "Quota reached ({n} right now)",
        "tot_u": "real total: {b}, {r} requests, {n} users", "tot_d": "real total: {r} requests, {n} distinct domains",
        "tot_b": "real total: {r} denied requests, {n} distinct domains",
        "tot_bu": "real total: {r} denied requests, {a} without an identified user",
        "usuario": "User", "datos": "Data", "pet": "Requests", "dominio": "Domain", "den": "Denied requests",
        "bloqueos": "Blocks", "cuenta": "Account", "deshab": "Disabled", "activa_c": "Active",
        "ip": "IP", "usuarios_h": "Users", "visto": "Seen (first – last)", "nombre": "Name", "tipo": "Type",
        "consumido": "Used", "limite": "Limit", "estado": "Status", "excedida": "Reached on", "reinicio": "Resets",
        "grupo": "Group", "usuario_t": "User", "activa": "Active", "limitada": "Limited", "cortada": "Cut off",
        "sin_cuotas": "No quota is exceeded right now.", "sin_datos": "No data in this period.",
        "g_usuarios": "Active users per period", "g_sitios": "Distinct sites per period",
        "g_bloq": "Blocked requests per period", "g_bloq_u": "Users with blocks per period",
        "g_ips": "Shared IPs per period", "g_datos": "Data transferred per period (MB)",
        "estado_actual": "Current state, independent of the chosen period.", "desconocido": "—", "sin_reg": "not recorded",
    },
    "pt": {
        "titulo": "SquidManager — Atividade de rede", "gen": "gerado em", "zona": "fuso horário",
        "v_none": "Últimas 1.000 requisições registradas", "1h": "Última hora", "24h": "Últimas 24 horas",
        "7d": "Últimos 7 dias", "30d": "Últimos 30 dias", "rango": "De {a} a {b}",
        "usuarios": "Usuários por consumo", "sitios": "Sites visitados", "bloq": "Sites bloqueados",
        "bloq_u": "Usuários com mais bloqueios", "ips": "IPs compartilhados (contas no mesmo equipamento)",
        "cuotas": "Cota excedida ({n} neste momento)",
        "tot_u": "total real: {b}, {r} requisições, {n} usuários", "tot_d": "total real: {r} requisições, {n} domínios distintos",
        "tot_b": "total real: {r} requisições negadas, {n} domínios distintos",
        "tot_bu": "total real: {r} requisições negadas, {a} sem usuário identificado",
        "usuario": "Usuário", "datos": "Dados", "pet": "Requisições", "dominio": "Domínio", "den": "Requisições negadas",
        "bloqueos": "Bloqueios", "cuenta": "Conta", "deshab": "Desabilitada", "activa_c": "Ativa",
        "ip": "IP", "usuarios_h": "Usuários", "visto": "Visto (primeira – última)", "nombre": "Nome", "tipo": "Tipo",
        "consumido": "Consumido", "limite": "Limite", "estado": "Estado", "excedida": "Excedida em", "reinicio": "Reinicia",
        "grupo": "Grupo", "usuario_t": "Usuário", "activa": "Ativa", "limitada": "Limitada", "cortada": "Cortada",
        "sin_cuotas": "Nenhuma cota está excedida neste momento.", "sin_datos": "Sem dados neste período.",
        "g_usuarios": "Usuários ativos por período", "g_sitios": "Sites distintos por período",
        "g_bloq": "Requisições bloqueadas por período", "g_bloq_u": "Usuários com bloqueios por período",
        "g_ips": "IPs compartilhados por período", "g_datos": "Dados transferidos por período (MB)",
        "estado_actual": "Estado atual, não depende do período escolhido.", "desconocido": "—", "sin_reg": "sem registro",
    },
}


def _formatear_bytes(n: float) -> str:
    n = float(n or 0)
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unidad}" if unidad != "B" else f"{int(n)} {unidad}"
        n /= 1024
    return f"{n:.1f} PB"


def _fecha(ts, dia: bool = False) -> str:
    if not ts:
        return "—"
    d = datetime.fromtimestamp(ts, tzs.get_tz())
    return d.strftime("%Y-%m-%d") if dia else d.strftime("%Y-%m-%d %H:%M")


def _grafica(puntos: list[tuple[str, float]], color, ancho=17 * cm, alto=4.2 * cm) -> Drawing:
    d = Drawing(ancho, alto)
    g = VerticalBarChart()
    g.x, g.y, g.width, g.height = 40, 26, ancho - 55, alto - 40
    g.data = [[v for _, v in puntos]]
    g.bars[0].fillColor = color
    g.bars[0].strokeColor = None
    g.barWidth = 6
    g.groupSpacing = 2
    g.valueAxis.valueMin = 0
    g.valueAxis.labels.fontSize = 7
    g.valueAxis.strokeColor = colors.HexColor("#B8C8D3")
    g.valueAxis.gridStrokeColor = colors.HexColor("#E4E7EB")
    g.valueAxis.visibleGrid = True
    g.categoryAxis.categoryNames = [n for n, _ in puntos]
    g.categoryAxis.labels.fontSize = 6
    g.categoryAxis.labels.angle = 35
    g.categoryAxis.labels.boxAnchor = "ne"
    g.categoryAxis.strokeColor = colors.HexColor("#B8C8D3")
    paso = max(1, len(puntos) // 12)  # no amontonar etiquetas
    g.categoryAxis.categoryNames = [n if i % paso == 0 else "" for i, (n, _) in enumerate(puntos)]
    d.add(g)
    return d


def _serie(tipo: str, campo: str, seconds, desde, hasta, factor: float = 1.0) -> list[tuple[str, float]]:
    if not rollup_service.disponible(seconds, desde, hasta):
        return []
    r = rollup_service.actividad_serie(tipo, seconds, desde, hasta)
    dia = r["granularidad"] == "dia"
    return [((_fecha(p["timestamp"], dia) if dia else datetime.fromtimestamp(p["timestamp"], tzs.get_tz()).strftime("%d %Hh")),
             (p.get(campo) or 0) * factor) for p in r["puntos"]]


def generar_pdf_actividad(ventana: str | None, db=None, idioma: str = "es",
                          desde: float | None = None, hasta: float | None = None) -> bytes:
    t = _L.get(idioma, _L["es"])
    rango = desde is not None and hasta is not None
    seconds = None if rango else (metrics_service.VENTANAS_SEGUNDOS.get(ventana) if ventana else None)
    kw = {"seconds": seconds, "desde": desde, "hasta": hasta}

    usuarios = metrics_service.get_top_users(10, **kw)
    dominios = metrics_service.get_top_domains(10, denied_only=False, **kw)
    bloqueados_dominio = metrics_service.get_top_domains(10, denied_only=True, **kw)
    bloqueados_usuario = metrics_service.get_top_blocked_users(10, db=db, **kw)
    totales = metrics_service.get_totales_actividad(**kw)
    ips = metrics_service.get_ips_compartidas(10, **kw)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm, title=t["titulo"])
    estilos = getSampleStyleSheet()
    e_titulo = ParagraphStyle("T", parent=estilos["Title"], fontSize=18, spaceAfter=4)
    e_sub = ParagraphStyle("S", parent=estilos["Normal"], textColor=colors.HexColor("#5F6B7A"), spaceAfter=10)
    e_sec = ParagraphStyle("H", parent=estilos["Heading2"], spaceBefore=14, spaceAfter=4, textColor=_AZUL)
    e_nota = ParagraphStyle("N", parent=estilos["Normal"], fontSize=8, textColor=colors.HexColor("#6b7c88"), spaceAfter=6)
    e_graf = ParagraphStyle("G", parent=estilos["Normal"], fontSize=8, textColor=colors.HexColor("#56697a"), spaceBefore=4)

    if rango:
        periodo = t["rango"].format(a=_fecha(desde, True), b=_fecha(hasta, True))
    else:
        periodo = t.get(ventana or "v_none", t["v_none"]) if ventana in (None, "1h", "24h", "7d", "30d") else str(ventana)
    zona = str(tzs.get_tz())
    el = [Paragraph(t["titulo"], e_titulo),
          Paragraph(f"{periodo} · {t['gen']} {_fecha(datetime.now().timestamp())} · {t['zona']}: {zona}", e_sub)]

    estilo_tabla = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F1FB")), ("TEXTCOLOR", (0, 0), (-1, 0), _AZUL),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E4E7EB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])

    def seccion(titulo, nota, grafico, filas, anchos):
        bloque = [Paragraph(titulo, e_sec), Paragraph(nota, e_nota)]
        if grafico is not None:
            bloque += [grafico[0], Paragraph(grafico[1], e_graf)]
        if len(filas) > 1:
            bloque.append(Table(filas, colWidths=anchos, style=estilo_tabla, repeatRows=1))
        else:
            bloque.append(Paragraph(t["sin_datos"], estilos["Normal"]))
        el.append(KeepTogether(bloque[:4]))
        el.extend(bloque[4:])

    def graf(tipo, campo, etiqueta, color, factor=1.0):
        p = _serie(tipo, campo, seconds, desde, hasta, factor)
        return (_grafica(p, color), etiqueta) if len(p) >= 2 else None

    # --- Usuarios ---
    filas = [["#", t["usuario"], t["datos"], t["pet"]]]
    for i, u in enumerate(usuarios, 1):
        filas.append([str(i), u["user"], _formatear_bytes(u["bytes"]), str(u["requests"])])
    seccion(t["usuarios"], t["tot_u"].format(b=_formatear_bytes(totales["usuarios"]["bytes"]), r=totales["usuarios"]["requests"], n=totales["usuarios"]["count"]),
            graf("usuarios", "bytes", t["g_datos"], _AZUL, 1 / 1048576), filas, [1 * cm, 7 * cm, 4.5 * cm, 4.5 * cm])
    # Usuarios activos por periodo: segunda gráfica de esta pestaña.
    g2 = graf("usuarios", "usuarios", t["g_usuarios"], colors.HexColor("#2E93BC"))
    if g2:
        el += [g2[0], Paragraph(g2[1], e_graf)]

    # --- Sitios visitados ---
    filas = [["#", t["dominio"], t["pet"], t["datos"]]]
    for i, d in enumerate(dominios, 1):
        filas.append([str(i), d["domain"], str(d["requests"]), _formatear_bytes(d["bytes"])])
    seccion(t["sitios"], t["tot_d"].format(r=totales["dominios"]["requests"], n=totales["dominios"]["count"]),
            graf("dominios", "sitios", t["g_sitios"], colors.HexColor("#2E93BC")), filas, [1 * cm, 8 * cm, 4 * cm, 4 * cm])

    # --- Sitios bloqueados ---
    filas = [["#", t["dominio"], t["den"]]]
    for i, d in enumerate(bloqueados_dominio, 1):
        filas.append([str(i), d["domain"], str(d["requests"])])
    seccion(t["bloq"], t["tot_b"].format(r=totales["dominios_bloqueados"]["requests"], n=totales["dominios_bloqueados"]["count"]),
            graf("bloqueados-dominio", "bloqueadas", t["g_bloq"], _ROJO), filas, [1 * cm, 10 * cm, 6 * cm])

    # --- Usuarios con más bloqueos ---
    filas = [["#", t["usuario"], t["bloqueos"], t["cuenta"]]]
    for i, u in enumerate(bloqueados_usuario["users"], 1):
        estado = {"disabled": t["deshab"], "enabled": t["activa_c"], "unknown": "—"}[u["account_status"]]
        filas.append([str(i), u["user"], str(u["blocked_requests"]), estado])
    seccion(t["bloq_u"], t["tot_bu"].format(r=totales["usuarios_bloqueados_requests"], a=bloqueados_usuario["anonymous_blocked"]),
            graf("bloqueados-usuario", "usuarios", t["g_bloq_u"], _ROJO), filas, [1 * cm, 7 * cm, 4.5 * cm, 4.5 * cm])

    # --- IPs compartidas ---
    filas = [["#", t["ip"], t["usuarios_h"], t["pet"], t["visto"]]]
    for i, r in enumerate(ips, 1):
        visto = f"{_fecha(r.get('primera_vez'))} – {_fecha(r.get('ultima_vez'))}" if r.get("primera_vez") else "—"
        nombres = ", ".join(r["usuarios"][:2]) + (f" +{len(r['usuarios']) - 2}" if len(r["usuarios"]) > 2 else "")
        filas.append([str(i), r["ip"], f"{len(r['usuarios'])}: {nombres}", str(r["requests"]), visto])
    seccion(t["ips"], "", graf("ips-compartidas", "ips", t["g_ips"], _NARANJA), filas, [0.8 * cm, 3.4 * cm, 5.4 * cm, 1.8 * cm, 5.6 * cm])

    # --- Cuota excedida (estado actual) ---
    excedidas = cuotas_excedidas(db) if db is not None else []
    filas = [["#", t["nombre"], t["tipo"], t["consumido"], t["limite"], t["estado"], t["excedida"], t["reinicio"]]]
    for i, q in enumerate(excedidas, 1):
        estado = t["activa"] if not q["quota_action_applied"] else (t["limitada"] if q["quota_action"] == "throttle" else t["cortada"])
        filas.append([str(i), q["nombre"], t["grupo"] if q["tipo"] == "grupo" else t["usuario_t"],
                      _formatear_bytes(q["quota_bytes_used"]), _formatear_bytes(q["quota_bytes"]), estado,
                      _fecha(q.get("excedida_en")) if q.get("excedida_en") else t["sin_reg"], _fecha(q.get("proximo_reinicio"))])
    el.append(Paragraph(t["cuotas"].format(n=len(excedidas)), e_sec))
    el.append(Paragraph(t["estado_actual"], e_nota))
    if excedidas:
        el.append(Table(filas, colWidths=[0.7 * cm, 3 * cm, 1.8 * cm, 2.1 * cm, 2.1 * cm, 1.9 * cm, 2.7 * cm, 2.7 * cm], style=estilo_tabla, repeatRows=1))
    else:
        el.append(Paragraph(t["sin_cuotas"], estilos["Normal"]))

    doc.build(el)
    return buffer.getvalue()
