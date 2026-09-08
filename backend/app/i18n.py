"""Traduccion de los mensajes que el backend devuelve al navegador.

Sin esto, traducir solo el panel deja una aplicacion que esta en ingles hasta
que algo falla, y entonces contesta en espanol: justo en el momento de mas
friccion para quien la usa.

La clave de cada mensaje es el propio mensaje en espanol, igual que en el
frontend. Asi no hay que tocar los 66 sitios donde se lanzan, y un mensaje que
no este traducido sale en espanol en vez de como un codigo interno.

El idioma se toma de la cabecera `Accept-Language` de cada peticion. El panel
la manda con el idioma que haya elegido el administrador, que no tiene por que
coincidir con el del navegador.
"""

from __future__ import annotations

IDIOMAS_SOPORTADOS = ("es", "en", "pt")
IDIOMA_POR_DEFECTO = "es"

# Los mensajes puramente internos (fallos de Docker Compose, sincronizacion del
# .env) no estan aqui a proposito: no los ve un administrador en su dia a dia,
# los ve quien lee un log, y ahi el espanol del proyecto es lo util.
TRADUCCIONES: dict[str, dict[str, str]] = {
    "en": {
        "ACL no encontrada": "ACL not found",
        "Administrador no encontrado": "Administrator not found",
        "Archivo JSON inválido": "Invalid JSON file",
        "Certificado CA no encontrado. Reinicia el contenedor Squid.":
            "CA certificate not found. Restart the Squid container.",
        "Certificado CA no encontrado. Vuelve a ejecutar install-nativo.sh para regenerarla.":
            "CA certificate not found. Run install-nativo.sh again to regenerate it.",
        "Certificado válido": "Valid certificate",
        "Contraseña actual incorrecta": "Current password is incorrect",
        "Delay pool no encontrado": "Delay pool not found",
        "Demasiados intentos fallidos para esta cuenta. Espera un minuto.":
            "Too many failed attempts for this account. Wait a minute.",
        "Demasiados intentos de login. Espera un minuto.":
            "Too many login attempts. Wait a minute.",
        "Demasiadas peticiones. Espera un momento.":
            "Too many requests. Wait a moment.",
        "Destino válido": "Valid destination",
        "Direcciones válidas": "Valid addresses",
        "El análisis expiró o ya se aplicó. Vuelve a subir el archivo y analízalo de nuevo.":
            "The analysis expired or was already applied. Upload the file again and analyze it once more.",
        "El certificado está incompleto: falta la línea final.":
            "The certificate is incomplete: the final line is missing.",
        "El esquema de autenticación debe ser \"basic\", \"digest\" o \"none\".":
            "The authentication scheme must be \"basic\", \"digest\" or \"none\".",
        "El modo debe ser 'reemplazar' o 'agregar'.":
            "The mode must be 'reemplazar' or 'agregar'.",
        "El valor de «ssl_bump_enabled» debe ser \"true\" o \"false\".":
            "The value of «ssl_bump_enabled» must be \"true\" or \"false\".",
        "La carga masiva es solo para ACLs de dominio (dstdomain/dstdom_regex).":
            "Bulk upload is only for domain ACLs (dstdomain/dstdom_regex).",
        "No se puede activar Digest con LDAP habilitado: Digest solo "
        "autentica usuarios locales del proxy, no hay forma estándar de "
        "guardar el hash que necesita en un directorio LDAP/Active "
        "Directory. Desactiva LDAP en Configuración LDAP antes de activar "
        "Digest, o mantén Basic si necesitas los dos.":
            "Digest cannot be enabled with LDAP enabled: Digest only "
            "authenticates local proxy users, and there is no standard way "
            "to store the hash it needs in an LDAP/Active Directory "
            "directory. Disable LDAP in LDAP Configuration before enabling "
            "Digest, or keep Basic if you need both.",
        "No se pueden crear grupos de usuarios con el esquema de "
        "autenticación del proxy en 'none': los grupos dependen de "
        "la autenticación local, que está desactivada. Cambia el "
        "esquema a 'basic' o 'digest' en Configuración antes de "
        "crear grupos.":
            "User groups cannot be created with the proxy authentication "
            "scheme set to 'none': groups depend on local authentication, "
            "which is disabled. Change the scheme to 'basic' or 'digest' "
            "in Settings before creating groups.",
        "El grupo ya existe": "The group already exists",
        "El nombre de usuario ya existe": "That username already exists",
        "El puerto del proxy padre no es un número": "The parent proxy port is not a number",
        "El superadmin principal no puede ser degradado":
            "The main superadmin cannot be demoted",
        "El superadmin principal no puede ser desactivado":
            "The main superadmin cannot be deactivated",
        "El superadmin principal no puede ser eliminado":
            "The main superadmin cannot be deleted",
        "El usuario ya está en el grupo": "The user is already in the group",
        "El usuario ya existe": "The user already exists",
        "Error de autenticación SMTP: usuario o contraseña incorrectos":
            "SMTP authentication error: wrong username or password",
        "Falta el destinatario (email_recipients)": "The recipient is missing (email_recipients)",
        "Falta el host de destino": "The destination host is missing",
        "Falta el servidor SMTP (host)": "The SMTP server (host) is missing",
        "Falta el token del bot o el chat_id de Telegram":
            "The Telegram bot token or chat_id is missing",
        "Falta la dirección del proxy padre": "The parent proxy address is missing",
        "Grupo no encontrado": "Group not found",
        "Hace falta un host de destino para habilitar el reenvío":
            "A destination host is required to enable forwarding",
        "LDAP no está configurado o está deshabilitado":
            "LDAP is not configured or is disabled",
        "La contraseña nueva debe ser distinta de la actual":
            "The new password must be different from the current one",
        "Mensaje de Telegram enviado": "Telegram message sent",
        "No es un backup válido de SquidManager": "This is not a valid SquidManager backup",
        "No hay destinatarios válidos": "There are no valid recipients",
        "No puedes cambiar tu propio rol de superadmin":
            "You cannot change your own superadmin role",
        "No puedes eliminar tu propia cuenta": "You cannot delete your own account",
        "No se encontró el binario de Squid en el sistema":
            "The Squid binary was not found on the system",
        "No se encontró systemctl: no se puede reiniciar Squid":
            "systemctl was not found: Squid cannot be restarted",
        "No se encontró el comando htpasswd en el backend. Reconstruye la imagen.":
            "The htpasswd command was not found in the backend. Rebuild the image.",
        "No se encontró el comando htpasswd en el backend. Instala el paquete apache2-utils: sudo apt install apache2-utils":
            "The htpasswd command was not found in the backend. Install the apache2-utils package: sudo apt install apache2-utils",
        "No se encontró http_port en la BD": "http_port was not found in the database",
        "Nombre de usuario inválido": "Invalid username",
        "Notificaciones por Telegram deshabilitadas": "Telegram notifications are disabled",
        "Notificaciones por email deshabilitadas": "Email notifications are disabled",
        "Orígenes válidos": "Valid sources",
        "Regla no encontrada": "Rule not found",
        "Rol inválido. Debe ser: superadmin, admin o viewer":
            "Invalid role. It must be: superadmin, admin or viewer",
        "Salida directa a Internet (sin proxy padre)":
            "Direct egress to the Internet (no parent proxy)",
        "Sin certificado (el padre no intercepta HTTPS)":
            "No certificate (the parent does not intercept HTTPS)",
        "Sin servidores propios: se usará la resolución del sistema":
            "No custom servers: the system resolver will be used",
        "Squid reconfigurado correctamente": "Squid reconfigured successfully",
        "Squid reiniciado": "Squid restarted",
        "Squid tarda en arrancar tras el reinicio": "Squid is slow to start after the restart",
        "Usuario LDAP no encontrado": "LDAP user not found",
        "Usuario no encontrado": "User not found",
        "Usuario o contraseña incorrectos": "Wrong username or password",
        "Ya existe un grupo con ese nombre": "A group with that name already exists",
        "Ya existe una ACL con ese nombre": "An ACL with that name already exists",
        "htpasswd tardó demasiado en responder.": "htpasswd took too long to respond.",
        "log_format debe ser 'raw' o 'ndjson'": "log_format must be 'raw' or 'ndjson'",
        "protocol debe ser 'udp' o 'tcp'": "protocol must be 'udp' or 'tcp'",
        "rfc_format debe ser 'rfc3164' o 'rfc5424'":
            "rfc_format must be 'rfc3164' or 'rfc5424'",
        "Configuración válida": "Valid configuration",
    },
    "pt": {
        "ACL no encontrada": "ACL não encontrada",
        "Administrador no encontrado": "Administrador não encontrado",
        "Archivo JSON inválido": "Arquivo JSON inválido",
        "Certificado CA no encontrado. Reinicia el contenedor Squid.":
            "Certificado CA não encontrado. Reinicie o contêiner do Squid.",
        "Certificado CA no encontrado. Vuelve a ejecutar install-nativo.sh para regenerarla.":
            "Certificado CA não encontrado. Execute install-nativo.sh novamente para regenerá-lo.",
        "Certificado válido": "Certificado válido",
        "Contraseña actual incorrecta": "Senha atual incorreta",
        "Delay pool no encontrado": "Delay pool não encontrado",
        "Demasiados intentos fallidos para esta cuenta. Espera un minuto.":
            "Tentativas falhas demais para esta conta. Aguarde um minuto.",
        "Demasiados intentos de login. Espera un minuto.":
            "Tentativas de login demais. Aguarde um minuto.",
        "Demasiadas peticiones. Espera un momento.":
            "Requisições demais. Aguarde um momento.",
        "Destino válido": "Destino válido",
        "Direcciones válidas": "Endereços válidos",
        "El análisis expiró o ya se aplicó. Vuelve a subir el archivo y analízalo de nuevo.":
            "A análise expirou ou já foi aplicada. Envie o arquivo novamente e analise-o de novo.",
        "El certificado está incompleto: falta la línea final.":
            "O certificado está incompleto: falta a linha final.",
        "El esquema de autenticación debe ser \"basic\", \"digest\" o \"none\".":
            "O esquema de autenticação deve ser \"basic\", \"digest\" ou \"none\".",
        "El modo debe ser 'reemplazar' o 'agregar'.":
            "O modo deve ser 'reemplazar' ou 'agregar'.",
        "El valor de «ssl_bump_enabled» debe ser \"true\" o \"false\".":
            "O valor de «ssl_bump_enabled» deve ser \"true\" ou \"false\".",
        "La carga masiva es solo para ACLs de dominio (dstdomain/dstdom_regex).":
            "O carregamento em massa é só para ACLs de domínio (dstdomain/dstdom_regex).",
        "No se puede activar Digest con LDAP habilitado: Digest solo "
        "autentica usuarios locales del proxy, no hay forma estándar de "
        "guardar el hash que necesita en un directorio LDAP/Active "
        "Directory. Desactiva LDAP en Configuración LDAP antes de activar "
        "Digest, o mantén Basic si necesitas los dos.":
            "Não é possível ativar o Digest com o LDAP habilitado: o Digest "
            "só autentica usuários locais do proxy, e não há forma padrão "
            "de guardar o hash que ele precisa num diretório LDAP/Active "
            "Directory. Desative o LDAP em Configuração LDAP antes de "
            "ativar o Digest, ou mantenha o Basic se precisar dos dois.",
        "No se pueden crear grupos de usuarios con el esquema de "
        "autenticación del proxy en 'none': los grupos dependen de "
        "la autenticación local, que está desactivada. Cambia el "
        "esquema a 'basic' o 'digest' en Configuración antes de "
        "crear grupos.":
            "Não é possível criar grupos de usuários com o esquema de "
            "autenticação do proxy em 'none': os grupos dependem da "
            "autenticação local, que está desativada. Mude o esquema "
            "para 'basic' ou 'digest' em Configurações antes de criar "
            "grupos.",
        "El grupo ya existe": "O grupo já existe",
        "El nombre de usuario ya existe": "Esse nome de usuário já existe",
        "El puerto del proxy padre no es un número": "A porta do proxy pai não é um número",
        "El superadmin principal no puede ser degradado":
            "O superadmin principal não pode ser rebaixado",
        "El superadmin principal no puede ser desactivado":
            "O superadmin principal não pode ser desativado",
        "El superadmin principal no puede ser eliminado":
            "O superadmin principal não pode ser excluído",
        "El usuario ya está en el grupo": "O usuário já está no grupo",
        "El usuario ya existe": "O usuário já existe",
        "Error de autenticación SMTP: usuario o contraseña incorrectos":
            "Erro de autenticação SMTP: usuário ou senha incorretos",
        "Falta el destinatario (email_recipients)": "Falta o destinatário (email_recipients)",
        "Falta el host de destino": "Falta o host de destino",
        "Falta el servidor SMTP (host)": "Falta o servidor SMTP (host)",
        "Falta el token del bot o el chat_id de Telegram":
            "Falta o token do bot ou o chat_id do Telegram",
        "Falta la dirección del proxy padre": "Falta o endereço do proxy pai",
        "Grupo no encontrado": "Grupo não encontrado",
        "Hace falta un host de destino para habilitar el reenvío":
            "É preciso um host de destino para habilitar o encaminhamento",
        "LDAP no está configurado o está deshabilitado":
            "O LDAP não está configurado ou está desabilitado",
        "La contraseña nueva debe ser distinta de la actual":
            "A nova senha deve ser diferente da atual",
        "Mensaje de Telegram enviado": "Mensagem do Telegram enviada",
        "No es un backup válido de SquidManager": "Não é um backup válido do SquidManager",
        "No hay destinatarios válidos": "Não há destinatários válidos",
        "No puedes cambiar tu propio rol de superadmin":
            "Você não pode alterar seu próprio papel de superadmin",
        "No puedes eliminar tu propia cuenta": "Você não pode excluir sua própria conta",
        "No se encontró el binario de Squid en el sistema":
            "O binário do Squid não foi encontrado no sistema",
        "No se encontró systemctl: no se puede reiniciar Squid":
            "systemctl não encontrado: não é possível reiniciar o Squid",
        "No se encontró el comando htpasswd en el backend. Reconstruye la imagen.":
            "O comando htpasswd não foi encontrado no backend. Reconstrua a imagem.",
        "No se encontró el comando htpasswd en el backend. Instala el paquete apache2-utils: sudo apt install apache2-utils":
            "O comando htpasswd não foi encontrado no backend. Instale o pacote apache2-utils: sudo apt install apache2-utils",
        "No se encontró http_port en la BD": "http_port não foi encontrado no banco de dados",
        "Nombre de usuario inválido": "Nome de usuário inválido",
        "Notificaciones por Telegram deshabilitadas":
            "Notificações por Telegram desabilitadas",
        "Notificaciones por email deshabilitadas": "Notificações por e-mail desabilitadas",
        "Orígenes válidos": "Origens válidas",
        "Regla no encontrada": "Regra não encontrada",
        "Rol inválido. Debe ser: superadmin, admin o viewer":
            "Papel inválido. Deve ser: superadmin, admin ou viewer",
        "Salida directa a Internet (sin proxy padre)":
            "Saída direta para a Internet (sem proxy pai)",
        "Sin certificado (el padre no intercepta HTTPS)":
            "Sem certificado (o pai não intercepta HTTPS)",
        "Sin servidores propios: se usará la resolución del sistema":
            "Sem servidores próprios: será usada a resolução do sistema",
        "Squid reconfigurado correctamente": "Squid reconfigurado com sucesso",
        "Squid reiniciado": "Squid reiniciado",
        "Squid tarda en arrancar tras el reinicio":
            "O Squid está demorando a iniciar após o reinício",
        "Usuario LDAP no encontrado": "Usuário LDAP não encontrado",
        "Usuario no encontrado": "Usuário não encontrado",
        "Usuario o contraseña incorrectos": "Usuário ou senha incorretos",
        "Ya existe un grupo con ese nombre": "Já existe um grupo com esse nome",
        "Ya existe una ACL con ese nombre": "Já existe uma ACL com esse nome",
        "htpasswd tardó demasiado en responder.": "O htpasswd demorou demais para responder.",
        "log_format debe ser 'raw' o 'ndjson'": "log_format deve ser 'raw' ou 'ndjson'",
        "protocol debe ser 'udp' o 'tcp'": "protocol deve ser 'udp' ou 'tcp'",
        "rfc_format debe ser 'rfc3164' o 'rfc5424'":
            "rfc_format deve ser 'rfc3164' ou 'rfc5424'",
        "Configuración válida": "Configuração válida",
    },
}


def idioma_de_cabecera(accept_language: str | None) -> str:
    """Idioma pedido por el cliente, o espanol si no pide ninguno conocido.

    No se implementa la negociacion completa de RFC 9110 con factores de
    calidad: el panel manda un unico idioma, y para un navegador que mande su
    lista basta con quedarse con la primera coincidencia.
    """
    if not accept_language:
        return IDIOMA_POR_DEFECTO

    for parte in accept_language.split(","):
        codigo = parte.split(";")[0].strip().lower()[:2]
        if codigo in IDIOMAS_SOPORTADOS:
            return codigo
    return IDIOMA_POR_DEFECTO


def traducir(texto: str, idioma: str) -> str:
    """Traduce un mensaje del backend, o lo devuelve tal cual si no esta."""
    if idioma == IDIOMA_POR_DEFECTO:
        return texto
    return TRADUCCIONES.get(idioma, {}).get(texto, texto)
