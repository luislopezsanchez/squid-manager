# Instalar detrás de un proxy corporativo

`install.sh` da por hecho que el servidor tiene salida directa a Internet. Cuando
la red obliga a pasar por un proxy, la instalación falla a mitad de un build con
un error que no explica la causa:

```
ERROR [backend 3/7] RUN apt-get update && apt-get install -y ...
Could not resolve 'deb.debian.org'
```

Hay dos caminos: el script, que lo configura todo solo, o el procedimiento
manual de esta guía.

---

## Por qué son tres configuraciones y no una

Este es el punto que hace fallar la mayoría de los intentos. **Tres capas
distintas necesitan el proxy, cada una lo lee de un sitio diferente**, y
configurar solo una deja la instalación a medias:

| Capa | Qué necesita salir | Dónde lee el proxy |
|---|---|---|
| **1. El host** | `apt` y `git`: instalar Docker, clonar el repositorio | Variables de entorno |
| **2. El demonio de Docker** | `docker pull` de las imágenes base | systemd, **no** el entorno |
| **3. Los builds** | `apt`, `pip`, `npm` y `wget` dentro de los contenedores | Configuración del cliente Docker |

La capa 2 es la que se salta casi todo el mundo: el demonio corre como servicio
de systemd y **no ve las variables de entorno del shell**. Aunque el resto esté
bien puesto, los `docker pull` siguen fallando hasta configurarla aparte.

> Saber en qué capa falla ahorra mucho tiempo. Si el `FROM` de la imagen base
> descarga bien y el error aparece recién en un `RUN apt-get`, las capas 1 y 2
> ya funcionan y el problema es solo la 3.

---

## Opción A — con el script

```bash
cp proxy.conf.example proxy.conf
```

Pon tus datos en `proxy.conf`:

```bash
PROXY_HOST=192.168.1.10
PROXY_PORT=8080
PROXY_USER=juan.perez
PROXY_PASS=P@ss#123
```

No hace falta escapar nada: el script codifica los caracteres especiales antes
de armar la URL. Después:

```bash
sudo ./install-tras-proxy.sh
```

Configura las tres capas, comprueba que cada una sale a Internet y solo entonces
lanza `install.sh`. Si algo falla, falla al principio y diciendo qué capa es, en
vez de a los quince minutos de build.

Opciones:

| Opción | Qué hace |
|---|---|
| `--nativo` | Instalación sin Docker: solo capa 1, guarda el proxy para el panel y las actualizaciones y lanza `install-nativo.sh` (ver [Instalación nativa](#instalación-nativa-sin-docker)) |
| `--solo-configurar` | Deja el proxy configurado y no ejecuta el instalador |
| `--sin-verificar` | Se salta las comprobaciones de las tres capas |

Las credenciales viven en `proxy.conf`, que está en `.gitignore`. **No se edita
ningún archivo del repositorio a propósito**: `install.sh` aborta al encontrar
cambios locales sin confirmar, así que poner el proxy a mano en los `Dockerfile`
deja la instalación bloqueada.

---

## Opción B — manual, paso a paso

### Paso 1: Codificar la contraseña si tiene caracteres especiales

Las credenciales viajan dentro de una URL, así que hay caracteres que ahí
significan otra cosa y parten la URL en dos. El síntoma es un `407` del proxy
que no explica nada.

| Carácter | Se escribe |
|---|---|
| `@` | `%40` |
| `#` | `%23` |
| `:` | `%3A` |
| `/` | `%2F` |
| `\` | `%5C` |
| espacio | `%20` |

### Paso 2: Definir las variables

Todo lo que sigue reutiliza estas dos.

```bash
export PROXY_URL='http://USUARIO:CLAVE@IP_PROXY:PUERTO'
```

```bash
export NO_PROXY_LIST='localhost,127.0.0.1,::1,db,backend,frontend,squid'
```

La segunda lista es obligatoria: sin ella el backend intenta hablar con la base
de datos a través del proxy corporativo y no llega.

### Paso 3: Proxy para el shell — capa 1

```bash
export http_proxy="$PROXY_URL" https_proxy="$PROXY_URL" no_proxy="$NO_PROXY_LIST" HTTP_PROXY="$PROXY_URL" HTTPS_PROXY="$PROXY_URL" NO_PROXY="$NO_PROXY_LIST"
```

### Paso 4: Proxy para apt — capa 1

```bash
sudo tee /etc/apt/apt.conf.d/95proxy > /dev/null <<EOF
Acquire::http::Proxy "${PROXY_URL}";
Acquire::https::Proxy "${PROXY_URL}";
EOF
```

### Paso 5: Proxy para git — capa 1

```bash
sudo git config --global http.proxy "$PROXY_URL"
```

### Paso 6: Proxy para el demonio de Docker — capa 2

El reinicio corta brevemente todos los contenedores que ya estén corriendo en la
máquina.

```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
```

```bash
sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf > /dev/null <<EOF
[Service]
Environment="HTTP_PROXY=${PROXY_URL}"
Environment="HTTPS_PROXY=${PROXY_URL}"
Environment="NO_PROXY=${NO_PROXY_LIST}"
EOF
```

```bash
sudo systemctl daemon-reload && sudo systemctl restart docker
```

### Paso 7: Proxy para los builds — capa 3

```bash
sudo mkdir -p /root/.docker
```

```bash
sudo tee /root/.docker/config.json > /dev/null <<EOF
{
  "proxies": {
    "default": {
      "httpProxy": "${PROXY_URL}",
      "httpsProxy": "${PROXY_URL}",
      "noProxy": "${NO_PROXY_LIST}"
    }
  }
}
EOF
```

```bash
sudo chmod 600 /root/.docker/config.json
```

Docker inyecta esto como *build args* predefinidos (`http_proxy`, `https_proxy`,
`no_proxy`) en todos los builds. No hace falta declarar `ARG` en ningún
`Dockerfile`, y además **quedan fuera de `docker history`**: el proxy no se
hornea en la imagen.

> Si `/root/.docker/config.json` ya existía con credenciales de registry, hay
> que añadir la sección `proxies` a mano en vez de sobrescribir el archivo.

### Paso 8: Revertir los Dockerfiles editados a mano

Si se intentó resolver el proxy poniendo `ENV http_proxy` en los `Dockerfile`,
hay que deshacerlo. Son dos problemas distintos: **el instalador aborta al
encontrar cambios locales sin confirmar**, y `ENV` hornea las credenciales del
proxy en la imagen, visibles con `docker history` y `docker inspect`.

```bash
cd /opt/squid-manager && git restore backend/Dockerfile frontend/Dockerfile squid/Dockerfile
```

```bash
git status --porcelain
```

Tiene que salir **vacío**. Si aparece cualquier otra cosa, revertirla también.

### Paso 9: Comprobar las tres capas

No seguir si alguna falla. Un minuto aquí evita descubrir el fallo a los quince
minutos de build, y dice exactamente qué capa está mal.

Capa 1 — el host:

```bash
curl -sI https://deb.debian.org | head -1
```

Capa 2 — el demonio:

```bash
sudo docker pull hello-world
```

Capa 3 — los builds:

```bash
printf 'FROM debian:trixie-slim\nRUN apt-get update\n' > /tmp/ptest.Dockerfile && sudo docker build -f /tmp/ptest.Dockerfile -t ptest /tmp
```

### Paso 10: Ejecutar el instalador

El `-E` es obligatorio: sin él, `sudo` descarta las variables del paso 3 y la
instalación falla igual que antes.

```bash
cd /opt/squid-manager && sudo -E ./install.sh
```

---

## Instalación nativa (sin Docker)

La instalación nativa (`install-nativo.sh`, ver [instalacion-nativa.md](instalacion-nativa.md))
solo necesita la **capa 1**: no hay demonio de Docker ni builds en contenedores. Pero hay dos
diferencias importantes con la instalación Docker:

- El instalador descarga desde varios sitios: `apt` (paquetes, PostgreSQL, pgvector), `git`
  (el repositorio), `pip` (dependencias de Python, **ejecutado como el usuario `squidmgr`**) y `npm`
  (compilar la interfaz).
- El proxy hace falta **también después de instalar**: el panel comprueba si hay versiones nuevas en
  GitHub, y el temporizador y el script de actualización ejecutan `git`, `pip` y `npm` por su cuenta,
  sin las variables de tu shell.

### Con el script (recomendado)

```bash
cp proxy.conf.example proxy.conf
nano proxy.conf
sudo ./install-tras-proxy.sh --nativo
```

El script:

1. Codifica la contraseña (`@`, `#`, `:`, espacios…) y arma la URL del proxy.
2. Instala la CA corporativa en el sistema si indicas `PROXY_CA_CERT`.
3. Configura `apt` y `git`.
4. **Guarda el proxy en `/etc/squidmanager/proxy.env`** (propiedad de `root`, permisos `600`).
5. Comprueba la salida real: `apt-get update`, GitHub, PyPI y npm. Si algo no sale, se detiene
   **antes** de instalar y dice qué destino falló, para que redes lo habilite.
6. Lanza `install-nativo.sh`, que lee ese fichero por sí solo (no hace falta `sudo -E`).

Con `--solo-configurar` deja todo preparado sin instalar; luego basta con `sudo ./install-nativo.sh`.

### Qué hace el fichero `/etc/squidmanager/proxy.env`

| Quién lo usa | Para qué |
|---|---|
| `install-nativo.sh` | `apt`, `git`, `curl`, `pip` y `npm` durante la instalación |
| `squidmanager.service` (el panel) | La comprobación de versiones en GitHub y las llamadas HTTP salientes del panel (por ejemplo, el Asistente de IA) |
| `squidmanager-autoupdate.service` y `upgrade-nativo.sh` | El `git fetch`, `pip` y `npm` de las actualizaciones, también las programadas desde el panel |

Lo leen `systemd` (como root, antes de ceder privilegios) y los scripts de root **como datos**: nunca
se ejecuta. Si cambias de proxy o de contraseña, vuelve a ejecutar
`sudo ./install-tras-proxy.sh --nativo --solo-configurar` y reinicia el panel
(`sudo systemctl restart squidmanager`).

> **Destinos internos:** el panel también habla con servidores de tu red (nodos del panel central, por
> ejemplo) y esas llamadas no deben pasar por el proxy corporativo. Añádelos en
> `PROXY_NO_PROXY_EXTRA` de `proxy.conf` (dominios o rangos separados por comas). `localhost` y `127.0.0.1`
> ya están incluidos. LDAP y SMTP no usan el proxy HTTP, así que no les afecta.

### Si el proxy inspecciona HTTPS

Indica la CA en `PROXY_CA_CERT`. Además de instalarla en el sistema, el script exporta
`NODE_EXTRA_CA_CERTS`, `PIP_CERT`, `REQUESTS_CA_BUNDLE` y `SSL_CERT_FILE` para que `npm`, `pip` y el
panel la reconozcan.

### Manual

```bash
# 1. URL del proxy (contraseña codificada, ver el paso 1 de la opción B)
export PROXY_URL='http://USUARIO:CLAVE@IP_PROXY:PUERTO'
sudo tee /etc/apt/apt.conf.d/95proxy > /dev/null <<EOF
Acquire::http::Proxy "${PROXY_URL}";
Acquire::https::Proxy "${PROXY_URL}";
EOF

# 2. Guardarlo para el panel y las actualizaciones
sudo mkdir -p /etc/squidmanager
sudo tee /etc/squidmanager/proxy.env > /dev/null <<EOF
http_proxy=${PROXY_URL}
https_proxy=${PROXY_URL}
no_proxy=localhost,127.0.0.1,::1
HTTP_PROXY=${PROXY_URL}
HTTPS_PROXY=${PROXY_URL}
NO_PROXY=localhost,127.0.0.1,::1
EOF
sudo chmod 600 /etc/squidmanager/proxy.env

# 3. Instalar (lee el fichero solo)
cd /opt/squid-manager && sudo ./install-nativo.sh
```

El fichero va **sin comillas**, una variable por línea.

---

## Si falla con un error de certificado

Significa que el proxy hace inspección TLS: descifra el tráfico HTTPS y lo
vuelve a firmar con su propia CA, que el servidor no conoce. Hay que pedir el
`.crt` de esa CA al área de redes.

```bash
sudo cp ca-corporativa.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates && sudo systemctl restart docker
```

Después, repetir el paso 9 y el 10.

Con el script, basta con indicar la ruta del certificado en `proxy.conf`:

```bash
PROXY_CA_CERT=/root/ca-corporativa.crt
```

---

## Después de instalar: el proxy padre

Todo lo anterior es **solo para instalar**. Para que Squid salga a Internet a
través del proxy corporativo durante la operación normal, se configura desde el
panel, en la sección **Proxy padre**: servidor, puerto y credenciales.

No hay que poner variables de proxy en los contenedores. Ver
[proxy-padre.md](proxy-padre.md) para el detalle del encadenamiento padre-hijo.

---

## Problemas frecuentes

| Síntoma | Causa |
|---|---|
| `Could not resolve` en un `RUN apt-get` | Falta la capa 3 |
| El `FROM` no descarga la imagen base | Falta la capa 2, o no se reinició Docker |
| `git pull` o `git clone` se quedan colgados | Falta la capa 1 (paso 5) |
| El proxy responde `407` con las credenciales correctas | La contraseña tiene caracteres sin codificar (paso 1) |
| Errores de certificado en `pip`, `npm` o `docker pull` | El proxy inspecciona TLS: falta su CA |
| El instalador se detiene por cambios locales | Hay `Dockerfile` editados a mano (paso 8) |
| Todo verifica bien pero `install.sh` falla igual | Se ejecutó sin `-E` y `sudo` descartó las variables |
| Instalación nativa: funciona al instalar pero «Buscar actualizaciones» o la actualización fallan | No existe `/etc/squidmanager/proxy.env` (se instaló sin `--nativo`): créalo con `sudo ./install-tras-proxy.sh --nativo --solo-configurar` y reinicia el panel |
| Instalación nativa: el panel no llega a un nodo interno | Falta ese destino en `PROXY_NO_PROXY_EXTRA` |
