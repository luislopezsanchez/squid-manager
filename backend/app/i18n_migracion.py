"""Traducciones (en / pt) de los mensajes del importador de squid.conf, del
backup v2 y de las funciones añadidas en el plan de mejora.

La clave es el mensaje en español tal como lo produce el código. Si lleva
partes variables, se escriben como {nombre}: `traducir_dinamico` (app/i18n.py)
reconoce el mensaje ya formateado y reinserta esas partes en la traducción."""

NUEVAS: dict[str, dict[str, str]] = {
    "en": {
        # --- importador: listas de ACL
        "la lista «{ruta}» no se subió junto con el squid.conf (súbela para importar esta ACL)":
            "the list «{ruta}» was not uploaded with squid.conf (upload it to import this ACL)",
        "la ACL no tiene ningún valor": "the ACL has no value",
        "un patrón regex contiene espacios y no se puede llevar a una sola línea de squid.conf sin partirlo; revisa esa lista a mano":
            "a regex pattern contains spaces and cannot be put on a single squid.conf line without splitting it; review that list by hand",
        "lista de {n} dominios leída de «{o}»; se carga como ACL de archivo":
            "list of {n} domains read from «{o}»; it is loaded as a file ACL",
        "{n} entradas leídas de «{o}»": "{n} entries read from «{o}»",
        " ({n} líneas no válidas se omiten)": " ({n} invalid lines are skipped)",
        # --- importador: ACL y reglas
        "equivale a «authenticated» (cualquier usuario autenticado), que el panel ya trae: las reglas que la usaban se importan apuntando a esa":
            "equivalent to «authenticated» (any authenticated user), which the panel already has: the rules that used it are imported pointing to that one",
        "usa Grupos de usuarios en el panel para esto, no una ACL suelta": "use User groups in the panel for this, not a standalone ACL",
        "es de uso interno de SSL Bump (step1/step2/step3); no se importa": "it is internal to SSL Bump (step1/step2/step3); it is not imported",
        "depende de un helper externo (external_acl_type) que el import no reconstruye":
            "it depends on an external helper (external_acl_type) that the import does not rebuild",
        "línea de ACL con formato irreconocible": "ACL line with an unrecognizable format",
        "línea de regla con formato irreconocible": "rule line with an unrecognizable format",
        "tipo de ACL '{t}' no reconocido": "ACL type '{t}' not recognized",
        "nombre no válido o reservado por Squid": "invalid name or reserved by Squid",
        "ya hay una ACL con ese nombre en SquidManager": "an ACL with that name already exists in SquidManager",
        "referencia una ACL no soportada o inexistente: {n}": "references an unsupported or non-existent ACL: {n}",
        "es una lista de dominios de SquidManager (categoría «{c}»); su contenido no viaja en este archivo. Volvé a cargarla en «ACLs» > «Cargar dominios» con el nombre «{n}» para recrearla.":
            "it is a SquidManager domain list (category «{c}»); its content does not travel in this file. Load it again in «ACLs» > «Load domains» with the name «{n}» to recreate it.",
        # --- importador: directivas sin equivalente
        "el esquema de autenticación del proxy se elige en Configuración (basic/digest/none); NTLM, Negotiate y Kerberos vía winbind no tienen equivalente ahí -Kerberos/Negotiate contra Active Directory sí se soporta, pero se configura aparte, en Kerberos-":
            "the proxy authentication scheme is chosen in Configuration (basic/digest/none); NTLM, Negotiate and Kerberos via winbind have no equivalent there -Kerberos/Negotiate against Active Directory is supported, but configured separately, in Kerberos-",
        "grupos externos resueltos por un helper (AD/winbind, LDAP a medida) no tienen equivalente; usa Grupos de usuarios o LDAP en el panel":
            "external groups resolved by a helper (AD/winbind, custom LDAP) have no equivalent; use User groups or LDAP in the panel",
        "un reescritor de URL externo (p. ej. squidGuard) no tiene equivalente en el panel":
            "an external URL rewriter (e.g. squidGuard) has no equivalent in the panel",
        "depende de url_rewrite_program, ver arriba": "it depends on url_rewrite_program, see above",
        "gestionado internamente por SquidManager; además es una contraseña en texto plano, no debería quedar en un archivo de configuración":
            "managed internally by SquidManager; it is also a plain-text password and should not be left in a configuration file",
        "no tiene equivalente en el panel": "it has no equivalent in the panel",
        "gestionado internamente por SquidManager": "managed internally by SquidManager",
        "usa el ajuste 'error_language' en Configuración": "use the 'error_language' setting in Configuration",
        "el puerto de escucha se cambia en Configuración; no se importa desde acá para no pisar el que ya está en uso":
            "the listening port is changed in Configuration; it is not imported from here so as not to overwrite the one in use",
        "SquidManager no gestiona un https_port propio (usa SSL Bump sobre http_port)":
            "SquidManager does not manage its own https_port (it uses SSL Bump over http_port)",
        "hay un patrón de refresco en Configuración, pero admite solo uno; con varias líneas refresh_pattern no hay un mapeo 1:1 seguro -revísalo a mano":
            "there is a refresh pattern in Configuration, but it only accepts one; with several refresh_pattern lines there is no safe 1:1 mapping -review it by hand",
        "revísalo a mano en Configuración: el formato (módulo, ruta y tipo de log) no siempre se traduce 1:1 al que usa SquidManager":
            "review it by hand in Configuration: the format (module, path and log type) does not always translate 1:1 to the one SquidManager uses",
        "revísalo a mano en Configuración, por el mismo motivo que access_log": "review it by hand in Configuration, for the same reason as access_log",
        "es una directiva de Squid sin equivalente en el panel: no se conserva; si la necesitas, revisa si el valor por defecto de Squid te sirve":
            "it is a Squid directive with no equivalent in the panel: it is not kept; if you need it, check whether Squid's default value works for you",
        "no es una directiva de Squid que este importador conozca": "it is not a Squid directive this importer knows",
        "solo se importa un cache_peer de tipo 'parent' simple; revisa el proxy padre a mano":
            "only a simple 'parent' cache_peer is imported; review the parent proxy by hand",
        "login={v} no se importa; configúralo a mano en Proxy padre": "login={v} is not imported; configure it by hand in Parent proxy",
        "opción login='{v}' no reconocida": "login option '{v}' not recognized",
        "solo se importa «never_direct allow all» (todo por el proxy padre); una condición por ACL no tiene equivalente":
            "only «never_direct allow all» is imported (everything through the parent proxy); a per-ACL condition has no equivalent",
        "«always_direct deny {n}» no tiene equivalente: el proxy padre solo admite una lista de dominios que van directo":
            "«always_direct deny {n}» has no equivalent: the parent proxy only accepts a list of domains that go direct",
        "«always_direct allow {n}»{t}: solo se convierten las ACL de dominios de destino; esta condición no se conserva (añade a mano las redes internas a «Dominios que van directo» del proxy padre si hace falta)":
            "«always_direct allow {n}»{t}: only destination-domain ACLs are converted; this condition is not kept (add the internal networks by hand to the parent proxy's «Domains that go direct» if needed)",
        "las reglas sobre la respuesta (http_reply_access) no existen en el panel; si solo era «allow all», ya es el comportamiento por defecto":
            "reply rules (http_reply_access) do not exist in the panel; if it was just «allow all», that is already the default behavior",
        "ICP/HTCP (cachés hermanas) no se usa en el panel; no se conserva": "ICP/HTCP (sibling caches) is not used in the panel; it is not kept",
        "umbral de limpieza de la caché: Squid usa su valor por defecto (90)": "cache cleanup threshold: Squid uses its default value (90)",
        "umbral de limpieza de la caché: Squid usa su valor por defecto (95)": "cache cleanup threshold: Squid uses its default value (95)",
        "la rotación de logs la hace logrotate del sistema, no Squid": "log rotation is done by the system's logrotate, not Squid",
        "opción interna de conexiones: Squid usa su valor por defecto": "internal connection option: Squid uses its default value",
        "correo de los avisos de Squid: el panel envía sus avisos por Notificaciones/SMTP":
            "Squid's notification email: the panel sends its alerts through Notifications/SMTP",
        "FTP a través del proxy no se gestiona desde el panel": "FTP through the proxy is not managed from the panel",
        "las páginas de error propias no se importan: el panel muestra las suyas en el idioma elegido":
            "custom error pages are not imported: the panel shows its own in the chosen language",
        "se reconstruye a partir de delay_pools/delay_class/delay_parameters; revisa el «Aplica a» de cada regla en Ancho de banda":
            "it is rebuilt from delay_pools/delay_class/delay_parameters; review each rule's «Applies to» in Bandwidth",
        "el acceso por ACL a cada proxy padre no tiene equivalente; el panel usa un solo padre para todo el tráfico (salvo los dominios directos)":
            "per-ACL access to each parent proxy has no equivalent; the panel uses a single parent for all traffic (except direct domains)",
        "tiempo de espera de lectura: Squid usa su valor por defecto": "read timeout: Squid uses its default value",
        "tiempo de espera de conexión: Squid usa su valor por defecto": "connect timeout: Squid uses its default value",
        # --- importador: usuarios y notas
        "ya hay un usuario con ese nombre": "a user with that name already exists",
        "Este SquidManager tiene LDAP activo y Digest solo autentica usuarios locales: se mantiene el esquema actual y los usuarios se importan con su hash de Basic si lo tienen.":
            "This SquidManager has LDAP active and Digest only authenticates local users: the current scheme is kept and users are imported with their Basic hash if they have one.",
        "{n} línea(s) de usuarios de otro realm de Digest se descartaron: la clave lleva el realm dentro y solo sirve con «{r}».":
            "{n} user line(s) from another Digest realm were discarded: the key has the realm inside and only works with «{r}».",
        "solo tiene {a} y el esquema elegido ({e}) necesita su {b}: se importa DESHABILITADO; restablece su contraseña para activarlo":
            "it only has {a} and the chosen scheme ({e}) needs its {b}: it is imported DISABLED; reset its password to enable it",
        "contraseña de Basic": "Basic password", "clave de Digest": "Digest key", "hash de Basic": "Basic hash",
        "Puertos no válidos en «{k}»: {v}": "Invalid ports in «{k}»: {v}",
        "El proxy padre se importó DESACTIVADO. Pruébalo en «Proxy padre» antes de activarlo: activarlo sin probar puede cortar toda la navegación.":
            "The parent proxy was imported DISABLED. Test it in «Parent proxy» before enabling it: enabling it untested can cut all browsing.",
        "{n} directiva(s) reconocida(s) pero sin equivalente en el panel no se importaron. Revisa el informe.":
            "{n} recognized directive(s) with no equivalent in the panel were not imported. Check the report.",
        "{n} directiva(s) no reconocida(s) no se importaron. Revisa el informe.": "{n} unrecognized directive(s) were not imported. Check the report.",
        "Estos archivos incluidos con 'include' no se subieron, así que su contenido no se analizó: {f}":
            "These files included with 'include' were not uploaded, so their content was not analyzed: {f}",
        "El usuario «{u}» tiene caracteres no admitidos y no se importó.": "The user «{u}» has unsupported characters and was not imported.",
        "{n} usuario(s) se importaron DESHABILITADOS por no tener credencial para el esquema {e}: restablece su contraseña en Usuarios para activarlos.":
            "{n} user(s) were imported DISABLED because they have no credential for the {e} scheme: reset their password in Users to enable them.",
        "Revisa la configuración importada y pulsa «Aplicar cambios» para activarla.":
            "Review the imported configuration and click «Apply changes» to activate it.",
        # --- backup v2
        "La contraseña del backup no es correcta.": "The backup password is not correct.",
        "La parte cifrada del backup está dañada: {e}": "The encrypted part of the backup is damaged: {e}",
        "El archivo es demasiado grande.": "The file is too large.",
        "No es un backup de SquidManager válido (el archivo está dañado o no es un .smbackup).":
            "Not a valid SquidManager backup (the file is damaged or is not a .smbackup).",
        "Al backup le falta «{n}».": "The backup is missing «{n}».",
        "«{n}» es demasiado grande.": "«{n}» is too large.",
        "No es un backup de SquidManager.": "It is not a SquidManager backup.",
        "Este backup es de un formato más nuevo (v{a}) que el que entiende esta versión ({b}). Actualiza este SquidManager antes de restaurarlo.":
            "This backup is in a newer format (v{a}) than this version understands ({b}). Update this SquidManager before restoring it.",
        "El backup está dañado: «{n}» no coincide con su firma.": "The backup is damaged: «{n}» does not match its signature.",
        "Ajuste «{k}»: «{t}» no es un puerto válido.": "Setting «{k}»: «{t}» is not a valid port.",
        "Modo de restauración desconocido.": "Unknown restore mode.",
        "La ACL «{n}» es una lista de archivo y este backup no trae su contenido: vuelve a cargarla con «Cargar dominios».":
            "The ACL «{n}» is a file list and this backup does not include its content: load it again with «Load domains».",
        "Las categorías con fuente en línea (HaGeZi) se vuelven a descargar solas en unos minutos.":
            "Categories with an online source (HaGeZi) are downloaded again on their own in a few minutes.",
        "Usuario no válido en el backup: «{u}».": "Invalid user in the backup: «{u}».",
        "{n} usuario(s) se crearon SIN contraseña porque el backup no incluye credenciales: restablécelas en Usuarios. (Para conservarlas, crea el backup con una contraseña de protección.)":
            "{n} user(s) were created WITHOUT a password because the backup does not include credentials: reset them in Users. (To keep them, create the backup with a protection password.)",
        "«{n}»: el backup no trae sus credenciales; revísalas en su pantalla.": "«{n}»: the backup does not include its credentials; check them on its screen.",
        "Este backup incluye credenciales cifradas: pide la contraseña para restaurarlas.":
            "This backup includes encrypted credentials: it asks for the password to restore them.",
        "La contraseña del backup debe tener al menos 8 caracteres.": "The backup password must be at least 8 characters long.",
        "La configuración restaurada ya se aplicó a Squid.": "The restored configuration has already been applied to Squid.",
        "La configuración restaurada está pendiente: pulsa «Aplicar cambios» para activarla.":
            "The restored configuration is pending: click «Apply changes» to activate it.",
        "Lo subido supera el tamaño máximo para analizar.": "What was uploaded exceeds the maximum size to analyze.",
        "El .zip tiene demasiados archivos.": "The .zip has too many files.",
        "El archivo comprimido tiene demasiados archivos.": "The compressed file has too many files.",
        "Los .rar y .7z no se pueden leer aquí: descomprímelo y sube los archivos (o un .zip / .tar.gz).":
            "Files .rar and .7z cannot be read here: extract it and upload the files (or a .zip / .tar.gz).",
        "No se encontró el squid.conf entre lo subido. Incluye el archivo squid.conf.":
            "squid.conf was not found among what was uploaded. Include the squid.conf file.",
        # --- usuarios, ancho de banda, módulos, auditoría
        "Correo electrónico inválido.": "Invalid email address.",
        "Fecha inválida: usa el formato YYYY-MM-DD.": "Invalid date: use the YYYY-MM-DD format.",
        "Módulo desconocido": "Unknown module",
        "Indica el límite de velocidad de descarga.": "Enter the download speed limit.",
        "El límite debe estar entre 1 byte/s y 10 GB/s.": "The limit must be between 1 byte/s and 10 GB/s.",
        "Elige al menos un objetivo para la regla (ACL, usuario, grupo, tipo de tráfico o todo el tráfico).":
            "Choose at least one target for the rule (ACL, user, group, traffic type or all traffic).",
        "Demasiados objetivos en una misma regla (máximo 200).": "Too many targets in a single rule (maximum 200).",
        "Falta la clase o los parámetros del delay pool.": "The delay pool class or parameters are missing.",
        "Formato no soportado: usa .csv, .xlsx o .txt.": "Unsupported format: use .csv, .xlsx or .txt.",
        "El archivo está vacío.": "The file is empty.",
        "No se encontró la columna del usuario. La primera fila debe ser el encabezado y tener una columna llamada «usuario» (o username).":
            "The user column was not found. The first row must be the header and have a column named «usuario» (or username).",
        "Usuario inválido: 1 a 64 caracteres, solo letras, números, punto, guion y guion bajo.":
            "Invalid user: 1 to 64 characters, only letters, numbers, dot, hyphen and underscore.",
        "Falta el usuario.": "The user is missing.", "Usuario repetido en el archivo.": "User repeated in the file.",
        "La contraseña debe tener entre 8 y 100 caracteres (déjala vacía para generar una).":
            "The password must be 8 to 100 characters long (leave it empty to generate one).",
        "Un usuario LDAP se gestiona en el directorio: aquí solo se puede deshabilitar.":
            "An LDAP user is managed in the directory: here it can only be disabled.",
        "Solo se puede generar credenciales de usuarios locales.": "Credentials can only be generated for local users.",
        "No existe.": "It does not exist.",
        "Ya existe un usuario LDAP con ese nombre.": "An LDAP user with that name already exists.",
    },
    "pt": {
        "la lista «{ruta}» no se subió junto con el squid.conf (súbela para importar esta ACL)":
            "a lista «{ruta}» não foi enviada junto com o squid.conf (envie-a para importar esta ACL)",
        "la ACL no tiene ningún valor": "a ACL não tem nenhum valor",
        "un patrón regex contiene espacios y no se puede llevar a una sola línea de squid.conf sin partirlo; revisa esa lista a mano":
            "um padrão regex contém espaços e não pode ir em uma única linha do squid.conf sem ser dividido; revise essa lista à mão",
        "lista de {n} dominios leída de «{o}»; se carga como ACL de archivo":
            "lista de {n} domínios lida de «{o}»; é carregada como ACL de arquivo",
        "{n} entradas leídas de «{o}»": "{n} entradas lidas de «{o}»",
        " ({n} líneas no válidas se omiten)": " ({n} linhas inválidas são ignoradas)",
        "equivale a «authenticated» (cualquier usuario autenticado), que el panel ya trae: las reglas que la usaban se importan apuntando a esa":
            "equivale a «authenticated» (qualquer usuário autenticado), que o painel já traz: as regras que a usavam são importadas apontando para essa",
        "usa Grupos de usuarios en el panel para esto, no una ACL suelta": "use Grupos de usuários no painel para isso, não uma ACL solta",
        "es de uso interno de SSL Bump (step1/step2/step3); no se importa": "é de uso interno do SSL Bump (step1/step2/step3); não é importada",
        "depende de un helper externo (external_acl_type) que el import no reconstruye":
            "depende de um helper externo (external_acl_type) que a importação não reconstrói",
        "línea de ACL con formato irreconocible": "linha de ACL com formato irreconhecível",
        "línea de regla con formato irreconocible": "linha de regra com formato irreconhecível",
        "tipo de ACL '{t}' no reconocido": "tipo de ACL '{t}' não reconhecido",
        "nombre no válido o reservado por Squid": "nome inválido ou reservado pelo Squid",
        "ya hay una ACL con ese nombre en SquidManager": "já existe uma ACL com esse nome no SquidManager",
        "referencia una ACL no soportada o inexistente: {n}": "referencia uma ACL não suportada ou inexistente: {n}",
        "es una lista de dominios de SquidManager (categoría «{c}»); su contenido no viaja en este archivo. Volvé a cargarla en «ACLs» > «Cargar dominios» con el nombre «{n}» para recrearla.":
            "é uma lista de domínios do SquidManager (categoria «{c}»); seu conteúdo não viaja neste arquivo. Carregue-a novamente em «ACLs» > «Carregar domínios» com o nome «{n}» para recriá-la.",
        "el esquema de autenticación del proxy se elige en Configuración (basic/digest/none); NTLM, Negotiate y Kerberos vía winbind no tienen equivalente ahí -Kerberos/Negotiate contra Active Directory sí se soporta, pero se configura aparte, en Kerberos-":
            "o esquema de autenticação do proxy é escolhido em Configuração (basic/digest/none); NTLM, Negotiate e Kerberos via winbind não têm equivalente lá -Kerberos/Negotiate contra o Active Directory é suportado, mas configurado à parte, em Kerberos-",
        "grupos externos resueltos por un helper (AD/winbind, LDAP a medida) no tienen equivalente; usa Grupos de usuarios o LDAP en el panel":
            "grupos externos resolvidos por um helper (AD/winbind, LDAP sob medida) não têm equivalente; use Grupos de usuários ou LDAP no painel",
        "un reescritor de URL externo (p. ej. squidGuard) no tiene equivalente en el panel":
            "um reescritor de URL externo (p. ex. squidGuard) não tem equivalente no painel",
        "depende de url_rewrite_program, ver arriba": "depende de url_rewrite_program, veja acima",
        "gestionado internamente por SquidManager; además es una contraseña en texto plano, no debería quedar en un archivo de configuración":
            "gerenciado internamente pelo SquidManager; além disso é uma senha em texto puro, não deveria ficar em um arquivo de configuração",
        "no tiene equivalente en el panel": "não tem equivalente no painel",
        "gestionado internamente por SquidManager": "gerenciado internamente pelo SquidManager",
        "usa el ajuste 'error_language' en Configuración": "use o ajuste 'error_language' em Configuração",
        "el puerto de escucha se cambia en Configuración; no se importa desde acá para no pisar el que ya está en uso":
            "a porta de escuta é alterada em Configuração; não é importada daqui para não sobrescrever a que já está em uso",
        "SquidManager no gestiona un https_port propio (usa SSL Bump sobre http_port)":
            "o SquidManager não gerencia um https_port próprio (usa SSL Bump sobre http_port)",
        "hay un patrón de refresco en Configuración, pero admite solo uno; con varias líneas refresh_pattern no hay un mapeo 1:1 seguro -revísalo a mano":
            "há um padrão de atualização em Configuração, mas aceita apenas um; com várias linhas refresh_pattern não há um mapeamento 1:1 seguro -revise à mão",
        "revísalo a mano en Configuración: el formato (módulo, ruta y tipo de log) no siempre se traduce 1:1 al que usa SquidManager":
            "revise à mão em Configuração: o formato (módulo, caminho e tipo de log) nem sempre se traduz 1:1 ao que o SquidManager usa",
        "revísalo a mano en Configuración, por el mismo motivo que access_log": "revise à mão em Configuração, pelo mesmo motivo do access_log",
        "es una directiva de Squid sin equivalente en el panel: no se conserva; si la necesitas, revisa si el valor por defecto de Squid te sirve":
            "é uma diretiva do Squid sem equivalente no painel: não é mantida; se precisar, verifique se o valor padrão do Squid serve",
        "no es una directiva de Squid que este importador conozca": "não é uma diretiva do Squid que este importador conheça",
        "solo se importa un cache_peer de tipo 'parent' simple; revisa el proxy padre a mano":
            "só é importado um cache_peer simples do tipo 'parent'; revise o proxy pai à mão",
        "login={v} no se importa; configúralo a mano en Proxy padre": "login={v} não é importado; configure-o à mão em Proxy pai",
        "opción login='{v}' no reconocida": "opção login='{v}' não reconhecida",
        "solo se importa «never_direct allow all» (todo por el proxy padre); una condición por ACL no tiene equivalente":
            "só é importado «never_direct allow all» (tudo pelo proxy pai); uma condição por ACL não tem equivalente",
        "«always_direct deny {n}» no tiene equivalente: el proxy padre solo admite una lista de dominios que van directo":
            "«always_direct deny {n}» não tem equivalente: o proxy pai só aceita uma lista de domínios que vão direto",
        "«always_direct allow {n}»{t}: solo se convierten las ACL de dominios de destino; esta condición no se conserva (añade a mano las redes internas a «Dominios que van directo» del proxy padre si hace falta)":
            "«always_direct allow {n}»{t}: só as ACLs de domínios de destino são convertidas; esta condição não é mantida (adicione à mão as redes internas em «Domínios que vão direto» do proxy pai, se necessário)",
        "las reglas sobre la respuesta (http_reply_access) no existen en el panel; si solo era «allow all», ya es el comportamiento por defecto":
            "as regras sobre a resposta (http_reply_access) não existem no painel; se era só «allow all», esse já é o comportamento padrão",
        "ICP/HTCP (cachés hermanas) no se usa en el panel; no se conserva": "ICP/HTCP (caches irmãos) não é usado no painel; não é mantido",
        "umbral de limpieza de la caché: Squid usa su valor por defecto (90)": "limite de limpeza do cache: o Squid usa seu valor padrão (90)",
        "umbral de limpieza de la caché: Squid usa su valor por defecto (95)": "limite de limpeza do cache: o Squid usa seu valor padrão (95)",
        "la rotación de logs la hace logrotate del sistema, no Squid": "a rotação de logs é feita pelo logrotate do sistema, não pelo Squid",
        "opción interna de conexiones: Squid usa su valor por defecto": "opção interna de conexões: o Squid usa seu valor padrão",
        "correo de los avisos de Squid: el panel envía sus avisos por Notificaciones/SMTP":
            "e-mail dos avisos do Squid: o painel envia seus avisos por Notificações/SMTP",
        "FTP a través del proxy no se gestiona desde el panel": "FTP através do proxy não é gerenciado pelo painel",
        "las páginas de error propias no se importan: el panel muestra las suyas en el idioma elegido":
            "as páginas de erro próprias não são importadas: o painel mostra as suas no idioma escolhido",
        "se reconstruye a partir de delay_pools/delay_class/delay_parameters; revisa el «Aplica a» de cada regla en Ancho de banda":
            "é reconstruído a partir de delay_pools/delay_class/delay_parameters; revise o «Aplica-se a» de cada regra em Largura de banda",
        "el acceso por ACL a cada proxy padre no tiene equivalente; el panel usa un solo padre para todo el tráfico (salvo los dominios directos)":
            "o acesso por ACL a cada proxy pai não tem equivalente; o painel usa um único pai para todo o tráfego (exceto os domínios diretos)",
        "tiempo de espera de lectura: Squid usa su valor por defecto": "tempo limite de leitura: o Squid usa seu valor padrão",
        "tiempo de espera de conexión: Squid usa su valor por defecto": "tempo limite de conexão: o Squid usa seu valor padrão",
        "ya hay un usuario con ese nombre": "já existe um usuário com esse nome",
        "Este SquidManager tiene LDAP activo y Digest solo autentica usuarios locales: se mantiene el esquema actual y los usuarios se importan con su hash de Basic si lo tienen.":
            "Este SquidManager tem LDAP ativo e o Digest só autentica usuários locais: o esquema atual é mantido e os usuários são importados com seu hash de Basic, se tiverem.",
        "{n} línea(s) de usuarios de otro realm de Digest se descartaron: la clave lleva el realm dentro y solo sirve con «{r}».":
            "{n} linha(s) de usuários de outro realm do Digest foram descartadas: a chave leva o realm dentro e só serve com «{r}».",
        "solo tiene {a} y el esquema elegido ({e}) necesita su {b}: se importa DESHABILITADO; restablece su contraseña para activarlo":
            "só tem {a} e o esquema escolhido ({e}) precisa de {b}: é importado DESABILITADO; redefina a senha para ativá-lo",
        "contraseña de Basic": "senha de Basic", "clave de Digest": "chave de Digest", "hash de Basic": "hash de Basic",
        "Puertos no válidos en «{k}»: {v}": "Portas inválidas em «{k}»: {v}",
        "El proxy padre se importó DESACTIVADO. Pruébalo en «Proxy padre» antes de activarlo: activarlo sin probar puede cortar toda la navegación.":
            "O proxy pai foi importado DESATIVADO. Teste-o em «Proxy pai» antes de ativá-lo: ativá-lo sem testar pode cortar toda a navegação.",
        "{n} directiva(s) reconocida(s) pero sin equivalente en el panel no se importaron. Revisa el informe.":
            "{n} diretiva(s) reconhecida(s) sem equivalente no painel não foram importadas. Verifique o relatório.",
        "{n} directiva(s) no reconocida(s) no se importaron. Revisa el informe.": "{n} diretiva(s) não reconhecida(s) não foram importadas. Verifique o relatório.",
        "Estos archivos incluidos con 'include' no se subieron, así que su contenido no se analizó: {f}":
            "Estes arquivos incluídos com 'include' não foram enviados, então seu conteúdo não foi analisado: {f}",
        "El usuario «{u}» tiene caracteres no admitidos y no se importó.": "O usuário «{u}» tem caracteres não permitidos e não foi importado.",
        "{n} usuario(s) se importaron DESHABILITADOS por no tener credencial para el esquema {e}: restablece su contraseña en Usuarios para activarlos.":
            "{n} usuário(s) foram importados DESABILITADOS por não terem credencial para o esquema {e}: redefina a senha em Usuários para ativá-los.",
        "Revisa la configuración importada y pulsa «Aplicar cambios» para activarla.":
            "Revise a configuração importada e clique em «Aplicar alterações» para ativá-la.",
        "La contraseña del backup no es correcta.": "A senha do backup não está correta.",
        "La parte cifrada del backup está dañada: {e}": "A parte criptografada do backup está danificada: {e}",
        "El archivo es demasiado grande.": "O arquivo é grande demais.",
        "No es un backup de SquidManager válido (el archivo está dañado o no es un .smbackup).":
            "Não é um backup válido do SquidManager (o arquivo está danificado ou não é um .smbackup).",
        "Al backup le falta «{n}».": "Faltou «{n}» no backup.",
        "«{n}» es demasiado grande.": "«{n}» é grande demais.",
        "No es un backup de SquidManager.": "Não é um backup do SquidManager.",
        "Este backup es de un formato más nuevo (v{a}) que el que entiende esta versión ({b}). Actualiza este SquidManager antes de restaurarlo.":
            "Este backup é de um formato mais novo (v{a}) do que esta versão entende ({b}). Atualize este SquidManager antes de restaurá-lo.",
        "El backup está dañado: «{n}» no coincide con su firma.": "O backup está danificado: «{n}» não coincide com sua assinatura.",
        "Ajuste «{k}»: «{t}» no es un puerto válido.": "Ajuste «{k}»: «{t}» não é uma porta válida.",
        "Modo de restauración desconocido.": "Modo de restauração desconhecido.",
        "La ACL «{n}» es una lista de archivo y este backup no trae su contenido: vuelve a cargarla con «Cargar dominios».":
            "A ACL «{n}» é uma lista de arquivo e este backup não traz seu conteúdo: carregue-a novamente com «Carregar domínios».",
        "Las categorías con fuente en línea (HaGeZi) se vuelven a descargar solas en unos minutos.":
            "As categorias com fonte online (HaGeZi) são baixadas novamente sozinhas em alguns minutos.",
        "Usuario no válido en el backup: «{u}».": "Usuário inválido no backup: «{u}».",
        "{n} usuario(s) se crearon SIN contraseña porque el backup no incluye credenciales: restablécelas en Usuarios. (Para conservarlas, crea el backup con una contraseña de protección.)":
            "{n} usuário(s) foram criados SEM senha porque o backup não inclui credenciais: redefina-as em Usuários. (Para mantê-las, crie o backup com uma senha de proteção.)",
        "«{n}»: el backup no trae sus credenciales; revísalas en su pantalla.": "«{n}»: o backup não traz suas credenciais; verifique-as na tela correspondente.",
        "Este backup incluye credenciales cifradas: pide la contraseña para restaurarlas.":
            "Este backup inclui credenciais criptografadas: peça a senha para restaurá-las.",
        "La contraseña del backup debe tener al menos 8 caracteres.": "A senha do backup deve ter pelo menos 8 caracteres.",
        "La configuración restaurada ya se aplicó a Squid.": "A configuração restaurada já foi aplicada ao Squid.",
        "La configuración restaurada está pendiente: pulsa «Aplicar cambios» para activarla.":
            "A configuração restaurada está pendente: clique em «Aplicar alterações» para ativá-la.",
        "Lo subido supera el tamaño máximo para analizar.": "O que foi enviado excede o tamanho máximo para análise.",
        "El .zip tiene demasiados archivos.": "O .zip tem arquivos demais.",
        "El archivo comprimido tiene demasiados archivos.": "O arquivo compactado tem arquivos demais.",
        "Los .rar y .7z no se pueden leer aquí: descomprímelo y sube los archivos (o un .zip / .tar.gz).":
            "Arquivos .rar e .7z não podem ser lidos aqui: descompacte-o e envie os arquivos (ou um .zip / .tar.gz).",
        "No se encontró el squid.conf entre lo subido. Incluye el archivo squid.conf.":
            "O squid.conf não foi encontrado entre o que foi enviado. Inclua o arquivo squid.conf.",
        "Correo electrónico inválido.": "Endereço de e-mail inválido.",
        "Fecha inválida: usa el formato YYYY-MM-DD.": "Data inválida: use o formato YYYY-MM-DD.",
        "Módulo desconocido": "Módulo desconhecido",
        "Indica el límite de velocidad de descarga.": "Informe o limite de velocidade de download.",
        "El límite debe estar entre 1 byte/s y 10 GB/s.": "O limite deve estar entre 1 byte/s e 10 GB/s.",
        "Elige al menos un objetivo para la regla (ACL, usuario, grupo, tipo de tráfico o todo el tráfico).":
            "Escolha pelo menos um alvo para a regra (ACL, usuário, grupo, tipo de tráfego ou todo o tráfego).",
        "Demasiados objetivos en una misma regla (máximo 200).": "Alvos demais em uma mesma regra (máximo 200).",
        "Falta la clase o los parámetros del delay pool.": "Faltam a classe ou os parâmetros do delay pool.",
        "Formato no soportado: usa .csv, .xlsx o .txt.": "Formato não suportado: use .csv, .xlsx ou .txt.",
        "El archivo está vacío.": "O arquivo está vazio.",
        "No se encontró la columna del usuario. La primera fila debe ser el encabezado y tener una columna llamada «usuario» (o username).":
            "A coluna do usuário não foi encontrada. A primeira linha deve ser o cabeçalho e ter uma coluna chamada «usuário» (ou username).",
        "Usuario inválido: 1 a 64 caracteres, solo letras, números, punto, guion y guion bajo.":
            "Usuário inválido: 1 a 64 caracteres, apenas letras, números, ponto, hífen e sublinhado.",
        "Falta el usuario.": "Falta o usuário.", "Usuario repetido en el archivo.": "Usuário repetido no arquivo.",
        "La contraseña debe tener entre 8 y 100 caracteres (déjala vacía para generar una).":
            "A senha deve ter entre 8 e 100 caracteres (deixe em branco para gerar uma).",
        "Un usuario LDAP se gestiona en el directorio: aquí solo se puede deshabilitar.":
            "Um usuário LDAP é gerenciado no diretório: aqui só pode ser desabilitado.",
        "Solo se puede generar credenciales de usuarios locales.": "Só é possível gerar credenciais de usuários locais.",
        "No existe.": "Não existe.",
        "Ya existe un usuario LDAP con ese nombre.": "Já existe um usuário LDAP com esse nome.",
    },
}


# --- Asistente de IA (routes/ai.py, services/ai_service.py)
_IA = {
    "en": {
        "Indica la URL base del proveedor (por ejemplo https://mi-servidor/v1).": "Enter the provider's base URL (for example https://my-server/v1).",
        "La URL base debe empezar por http:// o https:// y no puede llevar usuario ni contraseña.": "The base URL must start with http:// or https:// and cannot carry a user or password.",
        "Elige el modelo con el que responderá el asistente (usa «Probar conexión» para ver los disponibles).": "Choose the model the assistant will answer with (use «Test connection» to see the available ones).",
        "El modo agéntico no está disponible con este proveedor todavía.": "Agentic mode is not available with this provider yet.",
        "Falta la API key a probar.": "The API key to test is missing.",
        "Falta la URL base del proveedor (por ejemplo https://mi-servidor/v1).": "The provider's base URL is missing (for example https://my-server/v1).",
        "El asistente de IA no está activado.": "The AI assistant is not enabled.",
        "El modo agéntico todavía no está disponible con este proveedor. Prueba con Anthropic, OpenAI, Gemini, Groq, OpenRouter u otro compatible con OpenAI.":
            "Agentic mode is not available with this provider yet. Try Anthropic, OpenAI, Gemini, Groq, OpenRouter or another OpenAI-compatible one.",
        "Proveedor desconocido: {p}": "Unknown provider: {p}",
        "Anthropic devolvió una respuesta vacía.": "Anthropic returned an empty response.",
        "No se pudo conectar con Anthropic: {e}": "Could not connect to Anthropic: {e}",
        "Anthropic rechazó la petición: {e}": "Anthropic rejected the request: {e}",
    },
    "pt": {
        "Indica la URL base del proveedor (por ejemplo https://mi-servidor/v1).": "Informe a URL base do provedor (por exemplo https://meu-servidor/v1).",
        "La URL base debe empezar por http:// o https:// y no puede llevar usuario ni contraseña.": "A URL base deve começar com http:// ou https:// e não pode conter usuário nem senha.",
        "Elige el modelo con el que responderá el asistente (usa «Probar conexión» para ver los disponibles).": "Escolha o modelo com o qual o assistente responderá (use «Testar conexão» para ver os disponíveis).",
        "El modo agéntico no está disponible con este proveedor todavía.": "O modo agêntico ainda não está disponível com este provedor.",
        "Falta la API key a probar.": "Falta a API key a testar.",
        "Falta la URL base del proveedor (por ejemplo https://mi-servidor/v1).": "Falta a URL base do provedor (por exemplo https://meu-servidor/v1).",
        "El asistente de IA no está activado.": "O assistente de IA não está ativado.",
        "El modo agéntico todavía no está disponible con este proveedor. Prueba con Anthropic, OpenAI, Gemini, Groq, OpenRouter u otro compatible con OpenAI.":
            "O modo agêntico ainda não está disponível com este provedor. Tente Anthropic, OpenAI, Gemini, Groq, OpenRouter ou outro compatível com OpenAI.",
        "Proveedor desconocido: {p}": "Provedor desconhecido: {p}",
        "Anthropic devolvió una respuesta vacía.": "A Anthropic devolveu uma resposta vazia.",
        "No se pudo conectar con Anthropic: {e}": "Não foi possível conectar à Anthropic: {e}",
        "Anthropic rechazó la petición: {e}": "A Anthropic rejeitou a requisição: {e}",
    },
}
for _i, _d in _IA.items():
    NUEVAS[_i].update(_d)
