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
        "La lista de reglas a reordenar no puede estar vacía.":
            "The list of rules to reorder cannot be empty.",
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
        "El puerto debe ser un número entre 1 y 65535.":
            "The port must be a number between 1 and 65535.",
        "El puerto del proxy padre no es un número": "The parent proxy port is not a number",
        "El superadmin principal no puede ser degradado":
            "The main superadmin cannot be demoted",
        "El superadmin principal no puede ser desactivado":
            "The main superadmin cannot be deactivated",
        "El superadmin principal no puede ser eliminado":
            "The main superadmin cannot be deleted",
        "El usuario ya está en el grupo": "The user is already in the group",
        "El usuario ya existe": "The user already exists",
        "Ya existe un administrador con ese nombre. Usa otro nombre para evitar confusiones.": "An administrator with that name already exists. Use a different name to avoid confusion.",
        "Ya existe un usuario del proxy con ese nombre. Usa otro nombre para evitar confusiones.": "A proxy user with that name already exists. Use a different name to avoid confusion.",
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
        "Intentos fallidos de inicio de sesión": "Failed sign-in attempts",
        "Se registraron {n} intentos fallidos en un minuto contra la cuenta «{c}», desde la dirección {ip}.": "{n} failed attempts were recorded in one minute against the account «{c}», from address {ip}.",
        "La contraseña supera los 72 bytes (límite de bcrypt).": "The password exceeds 72 bytes (bcrypt limit).",
        "Notificaciones por XMPP deshabilitadas": "XMPP notifications are disabled",
        "Falta el servidor, la cuenta (JID) o la contraseña de XMPP": "The XMPP server, account (JID) or password is missing",
        "Falta al menos un destinatario o una sala de XMPP": "At least one XMPP recipient or room is missing",
        "Tiempo agotado hablando con el servidor XMPP": "Timed out talking to the XMPP server",
        "Error de autenticación XMPP: cuenta o contraseña incorrectas": "XMPP authentication error: wrong account or password",
        "El servidor XMPP no ofreció STARTTLS: elige «Sin cifrar» si es lo que quieres": "The XMPP server did not offer STARTTLS: choose «Unencrypted» if that is what you want",
        "No se pudo conectar al servidor XMPP: revisa host, puerto y cifrado": "Could not connect to the XMPP server: check host, port and encryption",
        "No se pudo conectar al servidor XMPP: revisa host, puerto y cifrado; si el certificado es propio, desmarca «Verificar certificado»": "Could not connect to the XMPP server: check host, port and encryption; if the certificate is self-signed, untick «Verify certificate»",
        "Mensaje XMPP enviado a {n} destino(s)": "XMPP message sent to {n} destination(s)",
        "Error enviando por XMPP: {e}": "Error sending via XMPP: {e}",
        "El servidor XMPP debe ser un nombre de host o una IP": "The XMPP server must be a host name or an IP",
        "La cuenta XMPP (JID) debe tener la forma usuario@dominio": "The XMPP account (JID) must look like user@domain",
        "Destinatario XMPP no válido: {r}": "Invalid XMPP recipient: {r}",
        "La sala XMPP debe tener la forma sala@conference.dominio": "The XMPP room must look like room@conference.domain",
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
        "Hace falta una API key para habilitar el asistente": "An API key is required to enable the assistant",
        "Hace falta la API key de Jina AI para poder buscar en la documentación.":
            "The Jina AI API key is required to be able to search the documentation.",
        "Falta la API key a probar": "The API key to test is missing",
        "Falta la API key de Jina a probar": "The Jina API key to test is missing",
        "La pregunta no puede estar vacía": "The question cannot be empty",
        "El asistente de IA no está activado": "The AI assistant is not enabled",
        "Los parámetros del delay pool no pueden quedar vacíos.": "The delay pool parameters cannot be left empty.",
        "Para activar Kerberos hacen falta el realm y el FQDN del proxy.":
            "The realm and the proxy's FQDN are required to enable Kerberos.",
        "'startup' no puede ser mayor que 'children'.":
            "'startup' cannot be greater than 'children'.",
        "'idle' no puede ser mayor que 'children'.":
            "'idle' cannot be greater than 'children'.",
        "Completa y guarda Realm y FQDN del proxy antes de generar el script.":
            "Fill in and save the Realm and proxy FQDN before generating the script.",
        "No se puede habilitar LDAP con Digest activo: Digest solo autentica usuarios locales del proxy. Cambia el esquema de autenticación a Basic en Configuración antes de habilitar LDAP.":
            "LDAP cannot be enabled with Digest active: Digest only authenticates local proxy users. Change the authentication scheme to Basic in Settings before enabling LDAP.",
        "Nombre de usuario inválido: usa entre 1 y 64 caracteres, solo letras, números, punto, guion y guion bajo.":
            "Invalid username: use between 1 and 64 characters, only letters, numbers, dot, hyphen and underscore.",
        "No se pudieron validar las credenciales": "Could not validate credentials",
        "Tu cuenta es de solo lectura": "Your account is read-only",
        "Solo el superadmin puede realizar esta acción": "Only the superadmin can perform this action",
        "La sesión caducó porque se cambió la contraseña. Vuelve a entrar.":
            "The session expired because the password was changed. Please log in again.",
        "El prefijo 'sni_' lo usa SquidManager para las reglas HTTPS. Elige otro nombre.":
            "The 'sni_' prefix is used by SquidManager for HTTPS rules. Choose another name.",
        "Hay un '!' sin ACL detrás.": "There's a '!' with no ACL after it.",
        "Este servidor": "This server",
        "El modo agéntico no está disponible con Ollama Cloud todavía. Probá con Gemini, Groq o NVIDIA NIM.":
            "The agentic mode is not available with Ollama Cloud yet. Try Gemini, Groq or NVIDIA NIM.",
        "El monitoreo centralizado está deshabilitado en este servidor.":
            "Centralized monitoring is disabled on this server.",
        "El origen del grupo debe ser 'local' o 'ldap'.":
            "The group's origin must be 'local' or 'ldap'.",
        "El periodo de la cuota debe ser 'daily', 'weekly' o 'monthly'.":
            "The quota period must be 'daily', 'weekly' or 'monthly'.",
        "El usuario es obligatorio para un nodo de tipo SquidManager":
            "The username is required for a SquidManager-type node",
        "Ese grupo no tiene ningún pool compartido configurado.":
            "That group doesn't have any shared pool configured.",
        "Ese usuario no tiene ninguna cuota configurada.":
            "That user doesn't have any quota configured.",
        "Esta categoría no tiene una URL de sincronización configurada.":
            "This category doesn't have a sync URL configured.",
        "Este grupo consulta la pertenencia en el directorio LDAP: no tiene miembros propios que agregar.":
            "This group looks up membership in the LDAP directory: it doesn't have its own members to add.",
        "Falta el nombre del grupo en el directorio LDAP.":
            "The group name in the LDAP directory is missing.",
        "Falta la velocidad límite para la acción 'limitar velocidad'.":
            "The speed limit is missing for the 'throttle' action.",
        "La URL de sincronización debe empezar con https://.":
            "The sync URL must start with https://.",
        "La URL del nodo debe empezar con http:// o https://":
            "The node URL must start with http:// or https://",
        "La acción de la cuota debe ser 'cut' o 'throttle'.":
            "The quota action must be 'cut' or 'throttle'.",
        "La contraseña es obligatoria para un nodo de tipo SquidManager":
            "The password is required for a SquidManager-type node",
        "La excepción de SSL Bump por grupo todavía no está disponible para grupos de LDAP.":
            "The per-group SSL Bump exception is not yet available for LDAP groups.",
        "La ruta debe ser una lista de ids separados por coma":
            "The path must be a list of comma-separated ids",
        "La ruta no puede estar vacía": "The path cannot be empty",
        "Nodo no encontrado": "Node not found",
        "Una categoría solo puede ser de tipo dominio (dstdomain o dstdom_regex).":
            "A category can only be of the domain type (dstdomain or dstdom_regex).",
        "Usuario y contraseña son obligatorios para un nodo de tipo SquidManager":
            "Username and password are required for a SquidManager-type node",
        "Este servidor tiene desactivado \"Monitorizar mis nodos\": no reenvía pedidos hacia sus propios nodos configurados.":
            "This server has \"Monitor my nodes\" disabled: it doesn't forward requests to its own configured nodes.",
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
        "La lista de reglas a reordenar no puede estar vacía.":
            "A lista de regras a reordenar não pode estar vazia.",
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
        "El puerto debe ser un número entre 1 y 65535.":
            "A porta deve ser um número entre 1 e 65535.",
        "El puerto del proxy padre no es un número": "A porta do proxy pai não é um número",
        "El superadmin principal no puede ser degradado":
            "O superadmin principal não pode ser rebaixado",
        "El superadmin principal no puede ser desactivado":
            "O superadmin principal não pode ser desativado",
        "El superadmin principal no puede ser eliminado":
            "O superadmin principal não pode ser excluído",
        "El usuario ya está en el grupo": "O usuário já está no grupo",
        "El usuario ya existe": "O usuário já existe",
        "Ya existe un administrador con ese nombre. Usa otro nombre para evitar confusiones.": "Já existe um administrador com esse nome. Use outro nome para evitar confusão.",
        "Ya existe un usuario del proxy con ese nombre. Usa otro nombre para evitar confusiones.": "Já existe um usuário do proxy com esse nome. Use outro nome para evitar confusão.",
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
        "Intentos fallidos de inicio de sesión": "Tentativas de login malsucedidas",
        "Se registraron {n} intentos fallidos en un minuto contra la cuenta «{c}», desde la dirección {ip}.": "Foram registradas {n} tentativas malsucedidas em um minuto contra a conta «{c}», a partir do endereço {ip}.",
        "La contraseña supera los 72 bytes (límite de bcrypt).": "A senha excede 72 bytes (limite do bcrypt).",
        "Notificaciones por XMPP deshabilitadas": "Notificações por XMPP desabilitadas",
        "Falta el servidor, la cuenta (JID) o la contraseña de XMPP": "Falta o servidor, a conta (JID) ou a senha do XMPP",
        "Falta al menos un destinatario o una sala de XMPP": "Falta pelo menos um destinatário ou uma sala XMPP",
        "Tiempo agotado hablando con el servidor XMPP": "Tempo esgotado ao falar com o servidor XMPP",
        "Error de autenticación XMPP: cuenta o contraseña incorrectas": "Erro de autenticação XMPP: conta ou senha incorretas",
        "El servidor XMPP no ofreció STARTTLS: elige «Sin cifrar» si es lo que quieres": "O servidor XMPP não ofereceu STARTTLS: escolha «Sem criptografia» se for o que deseja",
        "No se pudo conectar al servidor XMPP: revisa host, puerto y cifrado": "Não foi possível conectar ao servidor XMPP: verifique host, porta e criptografia",
        "No se pudo conectar al servidor XMPP: revisa host, puerto y cifrado; si el certificado es propio, desmarca «Verificar certificado»": "Não foi possível conectar ao servidor XMPP: verifique host, porta e criptografia; se o certificado for próprio, desmarque «Verificar certificado»",
        "Mensaje XMPP enviado a {n} destino(s)": "Mensagem XMPP enviada para {n} destino(s)",
        "Error enviando por XMPP: {e}": "Erro ao enviar por XMPP: {e}",
        "El servidor XMPP debe ser un nombre de host o una IP": "O servidor XMPP deve ser um nome de host ou um IP",
        "La cuenta XMPP (JID) debe tener la forma usuario@dominio": "A conta XMPP (JID) deve ter a forma usuario@dominio",
        "Destinatario XMPP no válido: {r}": "Destinatário XMPP inválido: {r}",
        "La sala XMPP debe tener la forma sala@conference.dominio": "A sala XMPP deve ter a forma sala@conference.dominio",
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
        "Hace falta una API key para habilitar el asistente": "É necessária uma chave de API para habilitar o assistente",
        "Hace falta la API key de Jina AI para poder buscar en la documentación.":
            "É necessária a chave de API da Jina AI para poder buscar na documentação.",
        "Falta la API key a probar": "Falta a chave de API a testar",
        "Falta la API key de Jina a probar": "Falta a chave de API da Jina a testar",
        "La pregunta no puede estar vacía": "A pergunta não pode ficar vazia",
        "El asistente de IA no está activado": "O assistente de IA não está ativado",
        "Los parámetros del delay pool no pueden quedar vacíos.": "Os parâmetros do delay pool não podem ficar vazios.",
        "Para activar Kerberos hacen falta el realm y el FQDN del proxy.":
            "Para ativar o Kerberos são necessários o realm e o FQDN do proxy.",
        "'startup' no puede ser mayor que 'children'.":
            "'startup' não pode ser maior que 'children'.",
        "'idle' no puede ser mayor que 'children'.":
            "'idle' não pode ser maior que 'children'.",
        "Completa y guarda Realm y FQDN del proxy antes de generar el script.":
            "Preencha e salve o Realm e o FQDN do proxy antes de gerar o script.",
        "No se puede habilitar LDAP con Digest activo: Digest solo autentica usuarios locales del proxy. Cambia el esquema de autenticación a Basic en Configuración antes de habilitar LDAP.":
            "Não é possível habilitar o LDAP com o Digest ativo: o Digest só autentica usuários locais do proxy. Mude o esquema de autenticação para Basic em Configurações antes de habilitar o LDAP.",
        "Nombre de usuario inválido: usa entre 1 y 64 caracteres, solo letras, números, punto, guion y guion bajo.":
            "Nome de usuário inválido: use entre 1 e 64 caracteres, só letras, números, ponto, hífen e sublinhado.",
        "No se pudieron validar las credenciales": "Não foi possível validar as credenciais",
        "Tu cuenta es de solo lectura": "Sua conta é somente leitura",
        "Solo el superadmin puede realizar esta acción": "Só o superadmin pode realizar esta ação",
        "La sesión caducó porque se cambió la contraseña. Vuelve a entrar.":
            "A sessão expirou porque a senha foi alterada. Entre novamente.",
        "El prefijo 'sni_' lo usa SquidManager para las reglas HTTPS. Elige otro nombre.":
            "O prefixo 'sni_' é usado pelo SquidManager para as regras HTTPS. Escolha outro nome.",
        "Hay un '!' sin ACL detrás.": "Há um '!' sem ACL depois.",
        "Este servidor": "Este servidor",
        "El modo agéntico no está disponible con Ollama Cloud todavía. Probá con Gemini, Groq o NVIDIA NIM.":
            "O modo agêntico ainda não está disponível com o Ollama Cloud. Experimente o Gemini, o Groq ou o NVIDIA NIM.",
        "El monitoreo centralizado está deshabilitado en este servidor.":
            "O monitoramento centralizado está desabilitado neste servidor.",
        "El origen del grupo debe ser 'local' o 'ldap'.":
            "A origem do grupo deve ser 'local' ou 'ldap'.",
        "El periodo de la cuota debe ser 'daily', 'weekly' o 'monthly'.":
            "O período da cota deve ser 'daily', 'weekly' ou 'monthly'.",
        "El usuario es obligatorio para un nodo de tipo SquidManager":
            "O usuário é obrigatório para um nó do tipo SquidManager",
        "Ese grupo no tiene ningún pool compartido configurado.":
            "Esse grupo não tem nenhum pool compartilhado configurado.",
        "Ese usuario no tiene ninguna cuota configurada.":
            "Esse usuário não tem nenhuma cota configurada.",
        "Esta categoría no tiene una URL de sincronización configurada.":
            "Essa categoria não tem uma URL de sincronização configurada.",
        "Este grupo consulta la pertenencia en el directorio LDAP: no tiene miembros propios que agregar.":
            "Esse grupo consulta a associação no diretório LDAP: não tem membros próprios para adicionar.",
        "Falta el nombre del grupo en el directorio LDAP.":
            "Falta o nome do grupo no diretório LDAP.",
        "Falta la velocidad límite para la acción 'limitar velocidad'.":
            "Falta o limite de velocidade para a ação de limitar a velocidade.",
        "La URL de sincronización debe empezar con https://.":
            "A URL de sincronização deve começar com https://.",
        "La URL del nodo debe empezar con http:// o https://":
            "A URL do nó deve começar com http:// ou https://",
        "La acción de la cuota debe ser 'cut' o 'throttle'.":
            "A ação da cota deve ser 'cut' ou 'throttle'.",
        "La contraseña es obligatoria para un nodo de tipo SquidManager":
            "A senha é obrigatória para um nó do tipo SquidManager",
        "La excepción de SSL Bump por grupo todavía no está disponible para grupos de LDAP.":
            "A exceção de SSL Bump por grupo ainda não está disponível para grupos de LDAP.",
        "La ruta debe ser una lista de ids separados por coma":
            "O caminho deve ser uma lista de ids separados por vírgula",
        "La ruta no puede estar vacía": "O caminho não pode estar vazio",
        "Nodo no encontrado": "Nó não encontrado",
        "Una categoría solo puede ser de tipo dominio (dstdomain o dstdom_regex).":
            "Uma categoria só pode ser do tipo domínio (dstdomain ou dstdom_regex).",
        "Usuario y contraseña son obligatorios para un nodo de tipo SquidManager":
            "Usuário e senha são obrigatórios para um nó do tipo SquidManager",
        "Este servidor tiene desactivado \"Monitorizar mis nodos\": no reenvía pedidos hacia sus propios nodos configurados.":
            "Este servidor tem \"Monitorar meus nós\" desativado: não encaminha pedidos para os seus próprios nós configurados.",
    },
}


import re as _re

from app.i18n_migracion import NUEVAS as _NUEVAS

for _idioma, _tr in _NUEVAS.items():
    TRADUCCIONES.setdefault(_idioma, {}).update(_tr)

_PLANTILLAS_CACHE: dict[str, list] = {}


def _plantillas(idioma: str) -> list:
    """Claves con partes variables ({nombre}) convertidas en expresiones regulares,
    para reconocer un mensaje ya formateado y reinsertar esas partes en su traducción."""
    if idioma not in _PLANTILLAS_CACHE:
        lista = []
        for clave, destino in TRADUCCIONES.get(idioma, {}).items():
            nombres = _re.findall(r"\{(\w+)\}", clave)
            if not nombres:
                continue
            patron = _re.escape(clave)
            for n in nombres:
                patron = patron.replace(_re.escape("{" + n + "}"), "(.*?)", 1)
            lista.append((_re.compile(patron, _re.DOTALL), destino, nombres))
        # Las plantillas más largas (más específicas) primero.
        lista.sort(key=lambda t: -len(t[0].pattern))
        _PLANTILLAS_CACHE[idioma] = lista
    return _PLANTILLAS_CACHE[idioma]


def traducir_dinamico(texto: str, idioma: str) -> str:
    """Como `traducir`, pero también reconoce mensajes con partes variables
    (nombres de archivo, cantidades...) que el código arma con f-strings."""
    if idioma == IDIOMA_POR_DEFECTO or not isinstance(texto, str):
        return texto
    exacto = TRADUCCIONES.get(idioma, {}).get(texto)
    if exacto is not None:
        return exacto
    for patron, destino, nombres in _plantillas(idioma):
        m = patron.fullmatch(texto)
        if m:
            try:
                return destino.format(**dict(zip(nombres, m.groups())))
            except (KeyError, IndexError):
                return texto
    return texto


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
