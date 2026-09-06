# Kerberos / Negotiate (SSO transparente) — SquidManager

Este documento explica cómo activar la autenticación **Kerberos/Negotiate** contra un
Active Directory (o cualquier KDC Kerberos v5), de forma que los usuarios del dominio
naveguen a través del proxy **sin que el navegador pida usuario y contraseña**: la
identidad se toma del ticket Kerberos de la sesión de Windows ya iniciada.

---

## Qué hace y qué no hace SquidManager

- **Coexiste con Basic Auth**, no lo reemplaza. `auth_param negotiate` se declara
  **antes** que `auth_param basic` en el `squid.conf` generado: un cliente que soporte
  Negotiate lo usa automáticamente; el resto sigue viendo el diálogo de usuario/contraseña
  de siempre.
- El bloque Negotiate **solo se emite si hay un keytab subido**. Si Kerberos está
  activado pero no hay keytab, no se referencia un archivo inexistente (eso tumbaría el
  helper de autenticación y dejaría a todos sin poder navegar, Basic incluido).
- **SquidManager no genera el keytab ni pide credenciales de dominio.** Crear la cuenta
  de servicio y el keytab es una operación que hace el administrador del Active
  Directory, fuera de este panel — SquidManager solo lo recibe, lo valida (cabecera de
  keytab v5) y lo instala en `/etc/squid/HTTP.keytab` (permisos `640`) al aplicar
  cambios.

---

## Requisitos previos

1. Un registro DNS que resuelva el **FQDN del proxy** a la IP donde escucha Squid (por
   ejemplo `proxy.empresa.com → 10.0.0.5`). El SPN del keytab se arma con este FQDN.
2. Reloj sincronizado entre el proxy y el AD. Kerberos rechaza tickets si la diferencia
   supera unos minutos (normalmente 5) — un `chrony`/`ntpd` funcionando alcanza.
3. Acceso de administrador al Active Directory para crear la cuenta de servicio y
   generar el keytab con `ktpass`.

---

## Paso a paso en el Active Directory

> 💡 **Atajo:** con el Realm y el FQDN del proxy ya guardados en el panel
> (Sistema → Kerberos), el botón **«Descargar script de configuración
> (Windows Server)»** genera un `.zip` con esos dos valores ya completados —
> crea la cuenta de servicio si no existe y corre `ktpass -crypto All` por
> vos. Evita el error más común de copiar los pasos de abajo a mano: editar
> el realm o el FQDN en un paso y olvidarse de cambiarlo en el siguiente. El
> script no incluye ninguna contraseña: la pide por consola al correr y no
> la guarda en ningún lado. Sigue haciendo falta correrlo en el AD con
> permisos de administrador de dominio, y revisarlo antes como cualquier
> script con ese nivel de acceso — lo de abajo es exactamente lo que hace,
> explicado paso a paso, para quien prefiera correrlo a mano o entender qué
> hizo el script.
>
> El zip trae dos archivos: `kerberos-ad-setup.ps1` (el script en sí, para
> revisar) y `Ejecutar.cmd`. **Corré `Ejecutar.cmd`, no el `.ps1`
> directamente** — Windows bloquea por defecto cualquier `.ps1` sin firma
> digital (`... no está firmado digitalmente. No se puede ejecutar este
> script en el sistema actual.`), venga de donde venga. El `.cmd` es un
> lanzador de una línea que llama a `powershell.exe -ExecutionPolicy Bypass
> -File kerberos-ad-setup.ps1`: el `Bypass` aplica solo a esa ejecución
> puntual, no cambia la política del sistema. Si preferís correr el `.ps1`
> a mano igual, el mismo comando sirve desde una consola de PowerShell:
> ```powershell
> powershell -ExecutionPolicy Bypass -File .\kerberos-ad-setup.ps1
> ```

### 1. Crear la cuenta de servicio ANTES de generar el keytab

`ktpass` **no crea la cuenta**, solo mapea un SPN a una cuenta que ya debe existir. Si se
invierte el orden aparece el error `DsCrackNames returned 0x2`.

```powershell
New-ADUser -Name "proxy-squidmanager" -SamAccountName "proxy-squidmanager" `
  -AccountPassword (ConvertTo-SecureString "UnaContraseñaFuerte" -AsPlainText -Force) `
  -Enabled $true -PasswordNeverExpires $true
```

### 2. Generar el keytab con `-crypto All`

```powershell
ktpass -princ HTTP/proxy.empresa.com@EMPRESA.COM `
  -mapuser EMPRESA\proxy-squidmanager `
  -pass "UnaContraseñaFuerte" `
  -crypto All -ptype KRB5_NT_PRINCIPAL -out C:\HTTP.keytab
```

> ⚠️ **`-mapuser` en formato `DOMINIO\usuario`, no `usuario@dominio`.** Con el
> formato UPN (`usuario@dominio`), `ktpass` falla con `DsCrackNames returned
> 0x5` / `failed getting target domain for specified user` salvo que la
> cuenta tenga un `UserPrincipalName` real con ese valor exacto — y
> `New-ADUser` no lo asigna solo, así que una cuenta recién creada no lo
> tiene. El formato NetBIOS (`DOMINIO\usuario`) se resuelve por
> `SamAccountName`, que sí existe siempre. Visto en una prueba real.

> ⚠️ **Hallazgo importante, no usar un solo tipo de cifrado.** Con `-crypto
> AES256-SHA1` (un único tipo) la autenticación fallaba con `gss_accept_sec_context()
> failed: ... Service key not available`. La causa: `ktpass` **no rellena**
> `msDS-SupportedEncryptionTypes` en la cuenta de AD, así que el tipo de cifrado real
> que el KDC va a usar al emitir el ticket es impredecible de antemano. Usando
> `-crypto All`, el keytab queda con DES-CBC-CRC, DES-CBC-MD5, RC4-HMAC, AES128 y
> AES256 — cubre cualquier posibilidad que elija el KDC, y con eso funcionó en la
> primera prueba. Regenerar el keytab con `-crypto All` es la solución si aparece ese
> error.

### 3. Subir el keytab y configurar SquidManager

En **Sistema → Kerberos**:

1. Subir `HTTP.keytab` (botón "Subir keytab").
2. Completar **Realm** (`EMPRESA.COM`, en mayúsculas) y **FQDN del proxy**
   (`proxy.empresa.com`, en minúsculas) — SquidManager normaliza ambos igual si se
   escriben distinto.
3. Marcar **Habilitar**.
4. Pulsar **Guardar Configuración** y luego **Aplicar cambios** (barra lateral) para que
   Squid empiece a ofrecer Negotiate.

---

## Validar sin un cliente Windows con GUI

Se puede comprobar la autenticación real, con un ticket Kerberos genuino, sin tener a
mano un PC de dominio con navegador:

```bash
# En cualquier máquina Linux con krb5-user instalado, apuntando al KDC real:
apt install krb5-user
# /etc/krb5.conf con [libdefaults] default_realm = EMPRESA.COM y el KDC del dominio

kinit usuario@EMPRESA.COM        # pide la contraseña del usuario de dominio, obtiene un TGT real

curl --proxy-negotiate --proxy-user : -x http://proxy.empresa.com:3128 http://example.com/
```

> ⚠️ Usar **`--proxy-negotiate --proxy-user :`**, no `--negotiate`/`-u` a secas — esos
> autentican contra el **sitio de destino**, no contra el proxy, y el test parece fallar
> por una razón equivocada.

Un `HTTP/200` con `curl` confirma que el proxy acepta el ticket. En
`/var/log/squid/access.log` debería aparecer la traza con la identidad real del usuario
(`usuario@EMPRESA.COM`), que es el objetivo final: navegar dejando la traza de quién iba
detrás, sin que el navegador pida nada.

Esto valida la criptografía y el intercambio Kerberos reales, pero no reemplaza una
prueba con un cliente Windows unido al dominio y un navegador real (Chrome/Edge/Firefox
configurados para SPNEGO) antes de darlo por cerrado en producción.

---

## Solución de problemas

| Síntoma | Causa probable |
|---|---|
| `DsCrackNames returned 0x2` al correr `ktpass` | La cuenta de servicio no existe todavía — crearla primero con `New-ADUser`. |
| `DsCrackNames returned 0x5` / `failed getting target domain for specified user` | `-mapuser` en formato `usuario@dominio` (UPN) sin que la cuenta tenga ese `UserPrincipalName` asignado. Usar `DOMINIO\usuario` (NetBIOS) en su lugar. |
| `gss_accept_sec_context() failed: ... Service key not available` | El keytab se generó con un solo tipo de cifrado y no coincide con el que eligió el KDC. Regenerar con `-crypto All`. |
| El navegador sigue pidiendo usuario/contraseña | Revisar que el FQDN del proxy resuelva por DNS, que el SPN del keytab sea `HTTP/<ese mismo FQDN>`, y que el navegador tenga ese dominio en su lista de sitios de confianza para SPNEGO (en Chrome/Edge: política `AuthServerAllowlist`). |
| Diferencia de reloj | Sincronizar NTP entre el proxy y el AD; más de ~5 minutos de diferencia invalida los tickets. |
| `ktpass` avisa `Failed to set property 'servicePrincipalName' ... 0x13` y `setspn -L <cuenta>` no muestra el SPN | El aviso de `ktpass` no siempre es benigno pese a lo que dice el propio mensaje. Registrar el SPN a mano: `setspn -A HTTP/<fqdn del proxy> <cuenta>`, y confirmar con `setspn -L <cuenta>`. El keytab ya generado sigue siendo válido — el SPN es un atributo aparte de la cuenta, no hace falta generar el keytab de nuevo. |

---

## Pendiente / fuera de alcance de este documento

- No hay UI todavía para decidir si el keytab se incluye en backup/restore — hoy no se
  exporta, igual que la contraseña de bind LDAP.
- No probado todavía con un cliente Windows real con GUI unido al dominio (solo
  validado con `kinit` + `curl` desde línea de comandos, ver arriba).
