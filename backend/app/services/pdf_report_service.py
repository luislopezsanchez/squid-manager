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
from reportlab.graphics.shapes import Drawing
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



_X = {
    "es": {
        "resumen": "Resumen", "destacado": "Lo más destacado", "pagina": "Página",
        "k_usuarios": "Usuarios activos", "k_sitios": "Sitios distintos", "k_datos": "Datos transferidos",
        "k_pet": "Peticiones", "k_bloq": "Peticiones bloqueadas", "k_pct": "% bloqueado",
        "intro": "Este informe resume la navegación de los usuarios a través del proxy en el periodo indicado. Cada sección explica qué se mide y cómo leerlo.",
        "e_usuarios": "Quién consume más ancho de banda. Un consumo alto no es necesariamente un problema (puede ser trabajo legítimo), pero es el primer lugar donde mirar si el enlace va lento o si conviene revisar una cuota. La gráfica muestra los datos transferidos en el tiempo.",
        "e_sitios": "Qué sitios se visitan más, estén permitidos o no. Sirve para decidir con datos si vale la pena bloquear algo que aparece seguido y no es productivo. La gráfica cuenta cuántos sitios distintos se visitaron en cada periodo.",
        "e_bloq": "Contra qué reglas chocan los usuarios. Si un dominio se repite mucho, la regla que lo bloquea está funcionando. La gráfica muestra cuándo hubo más intentos bloqueados.",
        "e_bloq_u": "Quién insiste más contra la política de acceso. Unos pocos bloqueos son ruido normal (un enlace viejo, una redirección); una cifra alta y sostenida de la misma persona merece una conversación.",
        "e_ips": "Direcciones IP desde las que navegó más de un usuario distinto. No es un veredicto (puede ser un equipo compartido de verdad), pero es una señal a revisar: credenciales que circulan entre personas se ven así.",
        "e_cuotas": "Cuentas o grupos que llegaron a su límite de datos. Según su configuración se les cortó el acceso o se les redujo la velocidad hasta la fecha de restablecimiento.",
        "l_usuarios": "{u} concentra el {p}% de los datos del periodo.",
        "l_pico": "El momento de mayor tráfico fue {t}, con {v}.",
        "l_sitios": "{d} es el sitio más visitado ({p}% de las peticiones).",
        "l_bloq": "{d} es lo más bloqueado, con {n} intentos.",
        "l_bloq_u": "{u} acumula {n} peticiones bloqueadas.",
        "l_ips": "Se detectaron {n} IP con más de una cuenta; la mayor tiene {m} cuentas distintas.",
        "l_cuotas": "{n} cuota(s) agotada(s) en este momento.",
        "l_nada": "Sin actividad destacable.",
        "graf": "Gráfica",
    },
    "en": {
        "resumen": "Summary", "destacado": "Highlights", "pagina": "Page",
        "k_usuarios": "Active users", "k_sitios": "Distinct sites", "k_datos": "Data transferred",
        "k_pet": "Requests", "k_bloq": "Blocked requests", "k_pct": "% blocked",
        "intro": "This report summarizes users' browsing through the proxy in the stated period. Each section explains what is measured and how to read it.",
        "e_usuarios": "Who uses the most bandwidth. High usage is not necessarily a problem (it may be legitimate work), but it is the first place to look if the link is slow or a quota needs review. The chart shows data transferred over time.",
        "e_sitios": "Which sites are visited most, allowed or not. It helps decide, with data, whether something frequent and unproductive is worth blocking. The chart counts how many distinct sites were visited in each period.",
        "e_bloq": "Which rules users run into. If a domain repeats a lot, the rule blocking it is working. The chart shows when most blocked attempts happened.",
        "e_bloq_u": "Who insists most against the access policy. A few blocks are normal noise (an old link, a redirect); a high, sustained figure from the same person deserves a conversation.",
        "e_ips": "IP addresses from which more than one distinct user browsed. It is not a verdict (it can be a genuinely shared machine), but it is a signal to check: credentials circulating among people look like this.",
        "e_cuotas": "Accounts or groups that reached their data limit. Depending on their settings, access was cut or speed reduced until the reset date.",
        "l_usuarios": "{u} accounts for {p}% of the period's data.",
        "l_pico": "Peak traffic was {t}, with {v}.",
        "l_sitios": "{d} is the most visited site ({p}% of requests).",
        "l_bloq": "{d} is the most blocked, with {n} attempts.",
        "l_bloq_u": "{u} has {n} blocked requests.",
        "l_ips": "{n} IPs with more than one account were detected; the largest has {m} distinct accounts.",
        "l_cuotas": "{n} quota(s) exhausted right now.",
        "l_nada": "Nothing noteworthy.",
        "graf": "Chart",
    },
    "pt": {
        "resumen": "Resumo", "destacado": "Destaques", "pagina": "Página",
        "k_usuarios": "Usuários ativos", "k_sitios": "Sites distintos", "k_datos": "Dados transferidos",
        "k_pet": "Requisições", "k_bloq": "Requisições bloqueadas", "k_pct": "% bloqueado",
        "intro": "Este relatório resume a navegação dos usuários pelo proxy no período indicado. Cada seção explica o que é medido e como interpretar.",
        "e_usuarios": "Quem consome mais banda. Um consumo alto não é necessariamente um problema (pode ser trabalho legítimo), mas é o primeiro lugar para olhar se o link está lento ou se convém rever uma cota. O gráfico mostra os dados transferidos ao longo do tempo.",
        "e_sitios": "Quais sites são mais visitados, permitidos ou não. Serve para decidir com dados se vale bloquear algo frequente e improdutivo. O gráfico conta quantos sites distintos foram visitados em cada período.",
        "e_bloq": "Contra quais regras os usuários esbarram. Se um domínio se repete muito, a regra que o bloqueia está funcionando. O gráfico mostra quando houve mais tentativas bloqueadas.",
        "e_bloq_u": "Quem mais insiste contra a política de acesso. Poucos bloqueios são ruído normal (um link antigo, um redirecionamento); um número alto e sustentado da mesma pessoa merece uma conversa.",
        "e_ips": "Endereços IP a partir dos quais navegou mais de um usuário distinto. Não é um veredito (pode ser um equipamento realmente compartilhado), mas é um sinal a revisar: credenciais que circulam entre pessoas têm esta aparência.",
        "e_cuotas": "Contas ou grupos que atingiram seu limite de dados. Conforme a configuração, o acesso foi cortado ou a velocidade reduzida até a data de reinício.",
        "l_usuarios": "{u} concentra {p}% dos dados do período.",
        "l_pico": "O momento de maior tráfego foi {t}, com {v}.",
        "l_sitios": "{d} é o site mais visitado ({p}% das requisições).",
        "l_bloq": "{d} é o mais bloqueado, com {n} tentativas.",
        "l_bloq_u": "{u} acumula {n} requisições bloqueadas.",
        "l_ips": "Foram detectados {n} IPs com mais de uma conta; o maior tem {m} contas distintas.",
        "l_cuotas": "{n} cota(s) esgotada(s) neste momento.",
        "l_nada": "Nada digno de nota.",
        "graf": "Gráfico",
    },
}
for _i, _d in _X.items():
    _L[_i].update(_d)


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


def _grafica(puntos: list[tuple[str, float]], color, ancho=7.6 * cm, alto=4.0 * cm) -> Drawing:
    d = Drawing(ancho, alto)
    g = VerticalBarChart()
    g.x, g.y, g.width, g.height = 34, 24, ancho - 42, alto - 34
    g.data = [[v for _, v in puntos]]
    g.bars[0].fillColor = color
    g.bars[0].strokeColor = None
    g.barWidth = 4
    g.groupSpacing = 1.5
    g.valueAxis.valueMin = 0
    g.valueAxis.labels.fontSize = 6.5
    g.valueAxis.strokeColor = colors.HexColor("#B8C8D3")
    g.valueAxis.gridStrokeColor = colors.HexColor("#E4E7EB")
    g.valueAxis.visibleGrid = True
    g.categoryAxis.labels.fontSize = 6
    g.categoryAxis.labels.angle = 35
    g.categoryAxis.labels.boxAnchor = "ne"
    g.categoryAxis.strokeColor = colors.HexColor("#B8C8D3")
    paso = max(1, len(puntos) // 6)  # pocas etiquetas: que se lean
    g.categoryAxis.categoryNames = [n if i % paso == 0 else "" for i, (n, _) in enumerate(puntos)]
    d.add(g)
    return d


def _serie(tipo: str, campo: str, seconds, desde, hasta, factor: float = 1.0) -> list[tuple[str, float]]:
    if not rollup_service.disponible(seconds, desde, hasta):
        return []
    r = rollup_service.actividad_serie(tipo, seconds, desde, hasta)
    dia = r["granularidad"] == "dia"
    fmt = "%m-%d" if dia else "%d %Hh"
    return [(datetime.fromtimestamp(p["timestamp"], tzs.get_tz()).strftime(fmt), (p.get(campo) or 0) * factor) for p in r["puntos"]]


def _pie(canvas, doc, t):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#7a8b97"))
    canvas.drawString(2 * cm, 1.1 * cm, "SquidManager")
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"{t['pagina']} {doc.page}")
    canvas.restoreState()


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
    excedidas = cuotas_excedidas(db) if db is not None else []

    serie_tr = _serie("usuarios", "bytes", seconds, desde, hasta, 1 / 1048576)
    serie_si = _serie("dominios", "sitios", seconds, desde, hasta)
    serie_bl = _serie("bloqueados-dominio", "bloqueadas", seconds, desde, hasta)
    serie_bu = _serie("bloqueados-usuario", "usuarios", seconds, desde, hasta)
    serie_ip = _serie("ips-compartidas", "ips", seconds, desde, hasta)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.6 * cm, bottomMargin=1.9 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm, title=t["titulo"])
    ancho = A4[0] - 4 * cm
    est = getSampleStyleSheet()
    e_h = ParagraphStyle("H", parent=est["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=3, textColor=_AZUL)
    e_txt = ParagraphStyle("T", parent=est["Normal"], fontSize=8.8, leading=12, textColor=colors.HexColor("#3c4d5a"), spaceAfter=5)
    e_lect = ParagraphStyle("L", parent=e_txt, fontName="Helvetica-Bold", textColor=_AZUL, spaceBefore=2, spaceAfter=8)
    e_cap = ParagraphStyle("C", parent=est["Normal"], fontSize=7.5, textColor=colors.HexColor("#6b7c88"), alignment=1)
    e_kv = ParagraphStyle("KV", parent=est["Normal"], fontSize=15, leading=18, fontName="Helvetica-Bold", textColor=_AZUL, alignment=1)
    e_kl = ParagraphStyle("KL", parent=est["Normal"], fontSize=7.8, textColor=colors.HexColor("#56697a"), alignment=1)
    e_w = ParagraphStyle("W", parent=est["Normal"], fontSize=18, leading=22, fontName="Helvetica-Bold", textColor=colors.white)
    e_ws = ParagraphStyle("WS", parent=est["Normal"], fontSize=9, textColor=colors.HexColor("#c7dcec"))
    e_b = ParagraphStyle("B", parent=e_txt, leftIndent=10, bulletIndent=0)

    if rango:
        periodo = t["rango"].format(a=_fecha(desde, True), b=_fecha(hasta, True))
    else:
        periodo = t.get(ventana or "v_none", t["v_none"]) if ventana in (None, "1h", "24h", "7d", "30d") else str(ventana)

    el = []
    banda = Table([[Paragraph(t["titulo"], e_w)],
                   [Paragraph(f"{periodo} · {t['gen']} {_fecha(datetime.now().timestamp())} · {t['zona']}: {tzs.get_tz()}", e_ws)]],
                  colWidths=[ancho])
    banda.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _AZUL), ("LEFTPADDING", (0, 0), (-1, -1), 14),
                               ("TOPPADDING", (0, 0), (0, 0), 14), ("BOTTOMPADDING", (0, -1), (-1, -1), 12)]))
    el += [banda, Spacer(1, 8), Paragraph(t["intro"], e_txt)]

    # --- Resumen: indicadores + lo más destacado ---
    pet = totales["usuarios"]["requests"] or totales["dominios"]["requests"]
    bloq = totales["usuarios_bloqueados_requests"]
    pct = f"{(bloq / pet * 100):.1f}%" if pet else "—"
    tarjetas = [(str(totales["usuarios"]["count"]), t["k_usuarios"]), (str(totales["dominios"]["count"]), t["k_sitios"]),
                (_formatear_bytes(totales["usuarios"]["bytes"]), t["k_datos"]), (f"{pet:,}".replace(",", "."), t["k_pet"]),
                (f"{bloq:,}".replace(",", "."), t["k_bloq"]), (pct, t["k_pct"])]
    celdas = [[[Paragraph(v, e_kv), Paragraph(l, e_kl)] for v, l in tarjetas[i:i + 3]] for i in (0, 3)]
    kp = Table(celdas, colWidths=[ancho / 3] * 3, rowHeights=[1.45 * cm, 1.45 * cm])
    kp.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F6FB")), ("BOX", (0, 0), (-1, -1), 3, colors.white),
                            ("INNERGRID", (0, 0), (-1, -1), 3, colors.white), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    el += [Paragraph(t["resumen"], e_h), kp, Spacer(1, 6)]

    destacados = []
    if usuarios and totales["usuarios"]["bytes"]:
        destacados.append(t["l_usuarios"].format(u=usuarios[0]["user"], p=round(usuarios[0]["bytes"] / totales["usuarios"]["bytes"] * 100)))
    if serie_tr and max(v for _, v in serie_tr) > 0:
        n, v = max(serie_tr, key=lambda x: x[1])
        destacados.append(t["l_pico"].format(t=n, v=_formatear_bytes(v * 1048576)))
    if dominios and totales["dominios"]["requests"]:
        destacados.append(t["l_sitios"].format(d=dominios[0]["domain"], p=round(dominios[0]["requests"] / totales["dominios"]["requests"] * 100)))
    if bloqueados_dominio:
        destacados.append(t["l_bloq"].format(d=bloqueados_dominio[0]["domain"], n=bloqueados_dominio[0]["requests"]))
    if ips:
        destacados.append(t["l_ips"].format(n=len(ips), m=max(len(r["usuarios"]) for r in ips)))
    if excedidas:
        destacados.append(t["l_cuotas"].format(n=len(excedidas)))
    el.append(Paragraph(t["destacado"], ParagraphStyle("D", parent=e_txt, fontName="Helvetica-Bold", spaceBefore=4)))
    for d in destacados or [t["l_nada"]]:
        el.append(Paragraph(d, e_b, bulletText="•"))

    estilo_tabla = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F1FB")), ("TEXTCOLOR", (0, 0), (-1, 0), _AZUL),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#E4E7EB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])

    def seccion(clave, titulo, lectura, serie, color, etiqueta_graf, filas, anchos):
        """Título, qué significa, tabla a la izquierda + gráfica a la derecha, y la lectura."""
        bloque = [Paragraph(titulo, e_h), Paragraph(t["e_" + clave], e_txt)]
        tabla = Table(filas, colWidths=anchos, style=estilo_tabla, repeatRows=1) if len(filas) > 1 else Paragraph(t["sin_datos"], e_txt)
        if len(serie) >= 2:
            graf = [_grafica(serie, color), Paragraph(etiqueta_graf, e_cap)]
            fila = Table([[tabla, graf]], colWidths=[ancho - 7.9 * cm, 7.9 * cm])
            fila.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                      ("RIGHTPADDING", (0, 0), (0, 0), 8)]))
            bloque.append(fila)
        else:
            bloque.append(tabla)
        if lectura:
            bloque.append(Paragraph(lectura, e_lect))
        el.append(KeepTogether(bloque))

    w = ancho - 7.9 * cm - 8  # ancho disponible para la tabla cuando hay gráfica al lado
    # --- Usuarios ---
    filas = [["#", t["usuario"], t["datos"], t["pet"]]] + [[str(i), u["user"], _formatear_bytes(u["bytes"]), str(u["requests"])] for i, u in enumerate(usuarios, 1)]
    seccion("usuarios", f"{t['usuarios']} — {t['tot_u'].format(b=_formatear_bytes(totales['usuarios']['bytes']), r=totales['usuarios']['requests'], n=totales['usuarios']['count'])}",
            destacados[0] if usuarios and totales["usuarios"]["bytes"] else "", serie_tr, _AZUL, t["g_datos"], filas, [0.6 * cm, w - 4.1 * cm, 2 * cm, 1.5 * cm])
    # --- Sitios ---
    filas = [["#", t["dominio"], t["pet"], t["datos"]]] + [[str(i), d["domain"], str(d["requests"]), _formatear_bytes(d["bytes"])] for i, d in enumerate(dominios, 1)]
    seccion("sitios", f"{t['sitios']} — {t['tot_d'].format(r=totales['dominios']['requests'], n=totales['dominios']['count'])}",
            t["l_sitios"].format(d=dominios[0]["domain"], p=round(dominios[0]["requests"] / max(totales["dominios"]["requests"], 1) * 100)) if dominios else "",
            serie_si, colors.HexColor("#2E93BC"), t["g_sitios"], filas, [0.6 * cm, w - 4.1 * cm, 1.5 * cm, 2 * cm])
    # --- Sitios bloqueados ---
    filas = [["#", t["dominio"], t["den"]]] + [[str(i), d["domain"], str(d["requests"])] for i, d in enumerate(bloqueados_dominio, 1)]
    seccion("bloq", f"{t['bloq']} — {t['tot_b'].format(r=totales['dominios_bloqueados']['requests'], n=totales['dominios_bloqueados']['count'])}",
            t["l_bloq"].format(d=bloqueados_dominio[0]["domain"], n=bloqueados_dominio[0]["requests"]) if bloqueados_dominio else "",
            serie_bl, _ROJO, t["g_bloq"], filas, [0.6 * cm, w - 2.6 * cm, 2 * cm])
    # --- Usuarios con más bloqueos ---
    filas = [["#", t["usuario"], t["bloqueos"], t["cuenta"]]]
    for i, u in enumerate(bloqueados_usuario["users"], 1):
        filas.append([str(i), u["user"], str(u["blocked_requests"]), {"disabled": t["deshab"], "enabled": t["activa_c"], "unknown": "—"}[u["account_status"]]])
    bu = bloqueados_usuario["users"]
    seccion("bloq_u", f"{t['bloq_u']} — {t['tot_bu'].format(r=totales['usuarios_bloqueados_requests'], a=bloqueados_usuario['anonymous_blocked'])}",
            t["l_bloq_u"].format(u=bu[0]["user"], n=bu[0]["blocked_requests"]) if bu else "",
            serie_bu, _ROJO, t["g_bloq_u"], filas, [0.6 * cm, w - 4.1 * cm, 1.5 * cm, 2 * cm])
    # --- IPs compartidas (tabla ancha: va debajo de la gráfica) ---
    filas = [["#", t["ip"], t["usuarios_h"], t["pet"], t["visto"]]]
    for i, r in enumerate(ips, 1):
        visto = f"{_fecha(r.get('primera_vez'))} – {_fecha(r.get('ultima_vez'))}" if r.get("primera_vez") else "—"
        nombres = ", ".join(r["usuarios"][:2]) + (f" +{len(r['usuarios']) - 2}" if len(r["usuarios"]) > 2 else "")
        filas.append([str(i), r["ip"], f"{len(r['usuarios'])}: {nombres}", str(r["requests"]), visto])
    el.append(Paragraph(t["ips"], e_h))
    el.append(Paragraph(t["e_ips"], e_txt))
    if len(serie_ip) >= 2:
        el += [_grafica(serie_ip, _NARANJA, ancho=ancho, alto=3.4 * cm), Paragraph(t["g_ips"], e_cap), Spacer(1, 4)]
    if len(filas) > 1:
        tb = Table(filas, colWidths=[0.7 * cm, 3 * cm, 5.6 * cm, 1.8 * cm, ancho - 11.1 * cm], style=estilo_tabla, repeatRows=1)
        tb.setStyle(TableStyle([("ALIGN", (2, 0), (2, -1), "LEFT"), ("ALIGN", (3, 0), (3, -1), "RIGHT"), ("ALIGN", (4, 0), (4, -1), "LEFT")]))
        el.append(tb)
        el.append(Paragraph(t["l_ips"].format(n=len(ips), m=max(len(r["usuarios"]) for r in ips)), e_lect))
    else:
        el.append(Paragraph(t["sin_datos"], e_txt))

    # --- Cuota excedida (estado actual) ---
    el.append(Paragraph(t["cuotas"].format(n=len(excedidas)), e_h))
    el.append(Paragraph(t["e_cuotas"] + " " + t["estado_actual"], e_txt))
    if excedidas:
        filas = [["#", t["nombre"], t["tipo"], t["consumido"], t["limite"], t["estado"], t["excedida"], t["reinicio"]]]
        for i, q in enumerate(excedidas, 1):
            estado = t["activa"] if not q["quota_action_applied"] else (t["limitada"] if q["quota_action"] == "throttle" else t["cortada"])
            filas.append([str(i), q["nombre"], t["grupo"] if q["tipo"] == "grupo" else t["usuario_t"],
                          _formatear_bytes(q["quota_bytes_used"]), _formatear_bytes(q["quota_bytes"]), estado,
                          _fecha(q.get("excedida_en")) if q.get("excedida_en") else t["sin_reg"], _fecha(q.get("proximo_reinicio"))])
        tb = Table(filas, colWidths=[0.6 * cm, 2.8 * cm, 1.7 * cm, 2 * cm, 2 * cm, 1.8 * cm, ancho - 15.2 * cm + 2.7 * cm, 2.7 * cm], style=estilo_tabla, repeatRows=1)
        tb.setStyle(TableStyle([("ALIGN", (2, 0), (2, -1), "LEFT"), ("ALIGN", (5, 0), (7, -1), "LEFT"), ("FONTSIZE", (0, 0), (-1, -1), 7.5)]))
        el.append(tb)
    else:
        el.append(Paragraph(t["sin_cuotas"], e_txt))

    doc.build(el, onFirstPage=lambda c, d: _pie(c, d, t), onLaterPages=lambda c, d: _pie(c, d, t))
    return buffer.getvalue()
