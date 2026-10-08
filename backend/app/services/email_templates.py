"""Correos de alerta con formato: mismo estilo que el reporte diario.

Cada evento de Notificaciones (cambios, alertas de seguridad, cuota agotada, sitios
bloqueados, nodos caídos…) sale como un correo HTML con: una franja de color y un icono
según la gravedad, el título, lo ocurrido en lenguaje natural, qué significa, qué
conviene hacer, la fecha y hora (en la zona horaria de la instalación) y un pie. El
texto plano se manda también, para clientes de correo que no muestran HTML.
"""
import html

from app.services import timezone_service as tzs

# color de franja, color suave, icono
_TONOS = {
    "info": ("#0B497C", "#e8f1f8", "ℹ️"),
    "cambio": ("#2E93BC", "#e6f4f9", "🛠️"),
    "aviso": ("#C77D0A", "#fdf3e1", "⚠️"),
    "peligro": ("#C0392B", "#fbeae8", "🚨"),
    "ok": ("#2f9e75", "#e5f5ee", "✅"),
}

_EVENTOS = {
    "apply": ("cambio", "apply"),
    "user_change": ("cambio", "user_change"),
    "acl_change": ("cambio", "acl_change"),
    "rule_change": ("cambio", "rule_change"),
    "security_alert": ("peligro", "security_alert"),
    "node_down": ("aviso", "node_down"),
    "quota_reached": ("aviso", "quota_reached"),
    "blocked_access": ("aviso", "blocked_access"),
    "test": ("ok", "test"),
}

# por evento: categoría, qué significa, qué hacer (lista)
_TEXTOS = {
    "es": {
        "cat": {"apply": "Cambios aplicados", "user_change": "Usuarios", "acl_change": "ACLs", "rule_change": "Reglas de acceso",
                "security_alert": "Alerta de seguridad", "node_down": "Estado de nodos", "quota_reached": "Cuota agotada",
                "blocked_access": "Sitios bloqueados", "test": "Prueba"},
        "que": {
            "apply": "Se aplicó la configuración de SquidManager al servicio Squid: desde ahora el proxy trabaja con los cambios hechos.",
            "user_change": "Se modificó la lista de usuarios que pueden navegar por el proxy.",
            "acl_change": "Se modificó una ACL, es decir, una lista de dominios, redes o condiciones que usan las reglas de acceso.",
            "rule_change": "Se modificaron las reglas que deciden qué se permite y qué se bloquea en la navegación.",
            "security_alert": "El sistema detectó un comportamiento fuera de lo normal en el tráfico del proxy.",
            "node_down": "Uno de los servidores monitoreados cambió de estado.",
            "quota_reached": "Esta cuenta consumió todo el tráfico que tenía asignado para el periodo. Según su configuración, se le cortó el acceso o se le redujo la velocidad hasta el próximo reinicio.",
            "blocked_access": "Un usuario está intentando entrar una y otra vez a sitios que una regla tiene bloqueados.",
            "test": "Este es un correo de prueba: si lo estás leyendo, el envío de notificaciones funciona.",
        },
        "hacer": {
            "apply": ["Si no reconoces este cambio, revisa Auditoría para ver quién lo hizo."],
            "user_change": ["Verifica en Usuarios que el cambio es el esperado.", "Si no lo reconoces, revisa Auditoría."],
            "acl_change": ["Comprueba en ACLs que el contenido es el esperado.", "Recuerda pulsar «Aplicar cambios» para que Squid lo use."],
            "rule_change": ["Revisa en Reglas de acceso que el orden y la acción son los correctos.", "Recuerda pulsar «Aplicar cambios» para que Squid lo use."],
            "security_alert": ["Revisa Registros y Actividad de red para ver el detalle.", "Si es una cuenta o IP sospechosa, considera deshabilitarla."],
            "node_down": ["Comprueba que el servidor está encendido y accesible en la red.", "Revisa el Panel central para ver el detalle."],
            "quota_reached": ["Si el límite es bajo para su uso real, súbelo en Cuotas.", "El uso se reinicia solo en la fecha indicada en Actividad de red → Cuota excedida."],
            "blocked_access": ["Consulta en Registros qué intenta abrir exactamente.", "Si es un uso legítimo, ajusta la regla; si no, conviene hablar con la persona."],
            "test": [],
        },
        "cuando": "Cuándo", "que_t": "Qué significa", "hacer_t": "Qué puedes hacer",
        "pie": "Aviso automático de SquidManager. Puedes elegir qué avisos recibir en Integraciones → Notificaciones.",
    },
    "en": {
        "cat": {"apply": "Changes applied", "user_change": "Users", "acl_change": "ACLs", "rule_change": "Access rules",
                "security_alert": "Security alert", "node_down": "Node status", "quota_reached": "Quota reached",
                "blocked_access": "Blocked sites", "test": "Test"},
        "que": {
            "apply": "The SquidManager configuration was applied to the Squid service: the proxy now works with the changes made.",
            "user_change": "The list of users allowed to browse through the proxy was modified.",
            "acl_change": "An ACL was modified, i.e. a list of domains, networks or conditions used by the access rules.",
            "rule_change": "The rules that decide what is allowed and what is blocked were modified.",
            "security_alert": "The system detected unusual behavior in the proxy traffic.",
            "node_down": "One of the monitored servers changed state.",
            "quota_reached": "This account used all the traffic assigned for the period. Depending on its settings, access was cut or speed reduced until the next reset.",
            "blocked_access": "A user keeps trying to reach sites that a rule has blocked.",
            "test": "This is a test email: if you are reading it, notification delivery works.",
        },
        "hacer": {
            "apply": ["If you do not recognize this change, check Audit to see who made it."],
            "user_change": ["Check in Users that the change is the expected one.", "If you do not recognize it, check Audit."],
            "acl_change": ["Check in ACLs that the content is as expected.", "Remember to press “Apply changes” so Squid uses it."],
            "rule_change": ["Check in Access rules that order and action are right.", "Remember to press “Apply changes” so Squid uses it."],
            "security_alert": ["Check Logs and Network activity for details.", "If the account or IP looks suspicious, consider disabling it."],
            "node_down": ["Check that the server is on and reachable on the network.", "Check the Central panel for details."],
            "quota_reached": ["If the limit is too low for real usage, raise it in Quotas.", "Usage resets by itself on the date shown in Network activity → Quota exceeded."],
            "blocked_access": ["Check in Logs what exactly it tries to open.", "If it is legitimate, adjust the rule; if not, talk to the person."],
            "test": [],
        },
        "cuando": "When", "que_t": "What it means", "hacer_t": "What you can do",
        "pie": "Automatic SquidManager notice. You can choose which notices to receive in Integrations → Notifications.",
    },
    "pt": {
        "cat": {"apply": "Alterações aplicadas", "user_change": "Usuários", "acl_change": "ACLs", "rule_change": "Regras de acesso",
                "security_alert": "Alerta de segurança", "node_down": "Estado dos nós", "quota_reached": "Cota esgotada",
                "blocked_access": "Sites bloqueados", "test": "Teste"},
        "que": {
            "apply": "A configuração do SquidManager foi aplicada ao serviço Squid: agora o proxy trabalha com as mudanças feitas.",
            "user_change": "A lista de usuários que podem navegar pelo proxy foi modificada.",
            "acl_change": "Uma ACL foi modificada, ou seja, uma lista de domínios, redes ou condições usada pelas regras de acesso.",
            "rule_change": "As regras que decidem o que é permitido e o que é bloqueado foram modificadas.",
            "security_alert": "O sistema detectou um comportamento fora do normal no tráfego do proxy.",
            "node_down": "Um dos servidores monitorados mudou de estado.",
            "quota_reached": "Esta conta consumiu todo o tráfego atribuído para o período. Conforme a configuração, o acesso foi cortado ou a velocidade reduzida até o próximo reinício.",
            "blocked_access": "Um usuário está tentando acessar repetidamente sites que uma regra bloqueia.",
            "test": "Este é um e-mail de teste: se você está lendo, o envio de notificações funciona.",
        },
        "hacer": {
            "apply": ["Se você não reconhece esta alteração, veja a Auditoria para saber quem a fez."],
            "user_change": ["Verifique em Usuários se a alteração é a esperada.", "Se não a reconhece, veja a Auditoria."],
            "acl_change": ["Confira em ACLs se o conteúdo é o esperado.", "Lembre-se de clicar em «Aplicar alterações» para o Squid usá-lo."],
            "rule_change": ["Confira em Regras de acesso se a ordem e a ação estão corretas.", "Lembre-se de clicar em «Aplicar alterações» para o Squid usá-lo."],
            "security_alert": ["Veja Registros e Atividade de rede para os detalhes.", "Se a conta ou o IP parecer suspeito, considere desabilitá-lo."],
            "node_down": ["Verifique se o servidor está ligado e acessível na rede.", "Veja o Painel central para os detalhes."],
            "quota_reached": ["Se o limite for baixo para o uso real, aumente-o em Cotas.", "O uso reinicia sozinho na data indicada em Atividade de rede → Cota excedida."],
            "blocked_access": ["Veja em Registros o que exatamente tenta abrir.", "Se for legítimo, ajuste a regra; se não, converse com a pessoa."],
            "test": [],
        },
        "cuando": "Quando", "que_t": "O que significa", "hacer_t": "O que você pode fazer",
        "pie": "Aviso automático do SquidManager. Você pode escolher quais avisos receber em Integrações → Notificações.",
    },
}


def construir_correo(evento: str | None, asunto: str, mensaje: str, idioma: str = "es") -> tuple[str, str]:
    """(html, texto plano) del correo de un evento."""
    from app.i18n import traducir_dinamico
    t = _TEXTOS.get(idioma, _TEXTOS["es"])
    tono, clave = _EVENTOS.get(evento or "", ("info", None))
    color, suave, icono = _TONOS[tono]
    titulo = traducir_dinamico(asunto, idioma).replace("SquidManager: ", "").replace("SquidManager - ", "")
    titulo = titulo[:1].upper() + titulo[1:]
    cuerpo = traducir_dinamico(mensaje, idioma)
    categoria = t["cat"].get(clave or "", "SquidManager")
    que = t["que"].get(clave or "", "")
    hacer = t["hacer"].get(clave or "", [])
    cuando = tzs.ahora_local().strftime("%Y-%m-%d %H:%M:%S")
    zona = str(tzs.get_tz())

    e = html.escape
    bloque_que = (f'<div style="margin:18px 0 0"><div style="font-size:12px;font-weight:700;color:{color};text-transform:uppercase;'
                  f'letter-spacing:.04em;margin-bottom:4px">{e(t["que_t"])}</div>'
                  f'<div style="font-size:13.5px;color:#3c4d5a;line-height:1.55">{e(que)}</div></div>') if que else ""
    bloque_hacer = ""
    if hacer:
        items = "".join(f'<li style="margin:0 0 4px">{e(h)}</li>' for h in hacer)
        bloque_hacer = (f'<div style="margin:18px 0 0"><div style="font-size:12px;font-weight:700;color:{color};text-transform:uppercase;'
                        f'letter-spacing:.04em;margin-bottom:4px">{e(t["hacer_t"])}</div>'
                        f'<ul style="margin:0;padding-left:18px;font-size:13.5px;color:#3c4d5a;line-height:1.55">{items}</ul></div>')
    cuerpo_html = (
        '<!doctype html><html><body style="margin:0;background:#eef3f7;font-family:Segoe UI,Helvetica,Arial,sans-serif">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;background:#fff;border-radius:14px;overflow:hidden">'
        f'<tr><td style="background:{color};padding:20px 26px"><div style="color:#ffffffcc;font-size:12px;letter-spacing:.06em;text-transform:uppercase">SquidManager · {e(categoria)}</div>'
        f'<div style="color:#fff;font-size:20px;font-weight:700;margin-top:4px">{icono} {e(titulo)}</div></td></tr>'
        f'<tr><td style="padding:22px 26px">'
        f'<div style="background:{suave};border-left:4px solid {color};border-radius:8px;padding:14px 16px;font-size:15px;color:#1c2b36;line-height:1.55">{e(cuerpo)}</div>'
        f'{bloque_que}{bloque_hacer}'
        f'<div style="margin:20px 0 0;font-size:12px;color:#7a8b97">{e(t["cuando"])}: {e(cuando)} ({e(zona)})</div>'
        '</td></tr>'
        f'<tr><td style="padding:14px 26px;background:#f5f9fc;color:#7a8b97;font-size:11.5px">{e(t["pie"])}</td></tr>'
        '</table></td></tr></table></body></html>'
    )
    lineas = [f"{icono} {titulo}", "", cuerpo, ""]
    if que:
        lineas += [f'{t["que_t"]}:', f"  {que}", ""]
    if hacer:
        lineas += [f'{t["hacer_t"]}:'] + [f"  - {h}" for h in hacer] + [""]
    lineas += [f'{t["cuando"]}: {cuando} ({zona})', "", t["pie"]]
    return cuerpo_html, "\n".join(lineas)
