# Actualizaciones desde el panel

Comprueba si hay una versión nueva de SquidManager publicada en GitHub, muestra
qué cambió, y permite aprobarla —de inmediato o programada para una fecha y
hora concretas— sin tener que entrar por SSH. Funciona igual en instalación
nativa y en Docker; la única diferencia real está en cuánto tarda en
arrancar una aprobación "ahora" (ver la nota al final).

---

## Cómo funciona, en una frase

**El panel nunca ejecuta la actualización.** Solo puede *avisar* cuándo hacen
falta ganas de mirar (comprobación contra GitHub) y *dejar aprobada* una
actualización, con fecha u "ahora mismo". Quien de verdad la aplica es un
mecanismo aparte, ya instalado, con sus propios permisos fijos desde antes —
el panel jamás gana la capacidad de ejecutar algo nuevo con privilegios de
root.

## Qué se ve en el panel

- **Versión instalada**, debajo del logo en la barra lateral: `vX.Y.Z ·
  commit`. Un punto en la campanita indica que hay una versión más nueva en
  GitHub; haciendo clic ahí se entra a la página "Actualizaciones".
- **Página "Actualizaciones"** (menú lateral, o el enlace de la campanita):
  versión instalada vs. la última publicada, botón "Comprobar ahora", la
  lista de commits nuevos (para saber qué cambia antes de aprobar), y el
  resultado de la última actualización aplicada.

La comprobación automática corre cada 6 horas en segundo plano (se puede
apagar con el casillero "Comprobar automáticamente" de la propia página); no
manda ningún dato del servidor a GitHub, solo consulta su API pública para
comparar el commit desplegado contra el último del repositorio.

## Paso a paso: aplicar una actualización ahora

Requiere una cuenta **superadministrador** — un admin común solo puede
consultar el estado, no aprobar nada.

1. Entrá a **Actualizaciones** en el menú lateral.
2. Si no aparece la tarjeta "Hay una actualización disponible", pulsá
   **"Comprobar ahora"** para forzar la consulta contra GitHub (si no, esperá
   a la comprobación automática, cada 6 horas).
3. Revisá la lista de **"Novedades"**: son los commits reales, con su mensaje,
   entre lo que tenés instalado y lo último publicado.
4. Pulsá **"Actualizar ahora"**. Queda aprobada al instante. En instalación
   nativa se aplica en los segundos siguientes (aprobar "ahora" adelanta el
   temporizador vía sudo); en Docker, el backend no tiene forma de tocar
   nada fuera de su contenedor, así que el servicio `updater` del propio
   stack (o, de respaldo, el temporizador del host) la nota solo en su
   próximo ciclo (unos segundos).
5. Mientras se aplica, la tarjeta muestra "Actualización en curso…" — el
   panel puede quedarse sin responder un momento (reinicia sus propios
   servicios). Cuando termina, aparece un aviso en la parte superior de
   **cualquier página** ("Se aplicó una actualización…") con un botón
   **"Recargar"**.

## Paso a paso: programar una actualización para más tarde

Mismos pasos 1 a 3 de arriba, y después:

4. Elegí una fecha y hora en el selector (no deja elegir una fecha ya
   pasada) y pulsá **"Programar"**.
5. La tarjeta pasa a mostrar "Programada para: `<fecha>` (aprobada por
   `<usuario>`)", con un botón **"Cancelar"** por si te arrepentís antes de
   que llegue la hora.
6. El sistema revisa **una vez por minuto** (nativo) o cada pocos segundos
   (Docker) si ya es la hora: puede tardar hasta un minuto después de lo
   elegido en arrancar. Si pasan más de 3 minutos sin arrancar, la tarjeta lo
   marca como **"atrasada"** — señal de que quien la aplica no está
   corriendo, hay que revisarlo por SSH (`systemctl status
   squidmanager-autoupdate.timer` en nativo, `docker compose ps updater` en
   Docker).
7. Igual que aplicar "ahora": al terminar, aparece el aviso de "Recargar" en
   cualquier página.

## Por qué es seguro: separar "decidir cuándo" de "ejecutar"

El backend web corre con el mismo usuario restringido de siempre (en nativo,
sin ser superusuario de su propia base de datos y con exactamente 4 líneas
fijas de `sudoers` — ninguna genérica; en Docker, sin ningún permiso nuevo
sobre el host en absoluto). Aprobar una actualización, desde el panel, solo
escribe un archivo de estado (igual de privilegios que guardar cualquier otro
ajuste; en Docker, ese archivo vive en el mismo volumen del proyecto que ya
está montado en el mismo path dentro y fuera del contenedor, así que el host
lo ve sin ningún mecanismo nuevo). Quien de verdad decide si corresponde
actuar es un proceso aparte, con privilegios, que el backend no controla: en
nativo, un temporizador de systemd **en el host** (root, cada minuto); en
Docker, el servicio `updater` del stack (que además cuenta con el
temporizador del host como respaldo):

- **Nativo**: puede además adelantarse al toque con la única orden de sudo
  que existe para esto, sin argumentos, e invoca `upgrade-nativo.sh` en una
  unidad de systemd aparte —para que reiniciar el panel a mitad de la
  actualización no la mate a mitad de camino—.
- **Docker**: no hay ningún "adelantar" posible desde el panel (no hay sudo
  hacia el host desde dentro de un contenedor), así que siempre espera al
  próximo tic. El servicio `updater` no ejecuta la actualización él mismo
  (al reconstruir el stack se recrearía a sí mismo y se cortaría): lanza un
  contenedor auxiliar desacoplado que invoca `upgrade-docker.sh`. Es
  el único componente con el socket de Docker completo; el backend no lo
  tiene. Ver [actualizacion.md](actualizacion.md#actualizar-desde-el-panel-en-instalaciones-docker).

## Si una programación no arranca a tiempo

Quien la aplica revisa cada minuto (nativo) o cada pocos segundos (Docker), así
que una actualización programada debería empezar enseguida tras la hora
elegida. Si pasan más de 3 minutos sin que arranque, el panel lo marca como
"atrasada" y avisa —no se cancela sola, pero deja de mostrar "programada" en
silencio para siempre. Suele significar que no está corriendo: `systemctl
status squidmanager-autoupdate.timer` (nativo) o `docker compose ps updater`
(Docker) en el servidor. Desde la 1.0.4 el panel lo detecta solo y muestra el
comando exacto para arreglarlo.

## Diferencias entre nativo y Docker

| | Nativo | Docker |
|---|---|---|
| Comprobar y aprobar desde el panel | Sí | Sí |
| Demora de "actualizar ahora" | Segundos | Segundos (hasta 20 s) |
| Quién aplica de verdad | Temporizador del host: `autoupdate-check.sh` + `upgrade-nativo.sh` | Servicio `updater` del stack (respaldo: temporizador del host): `docker-autoupdate-check.sh` + `upgrade-docker.sh` |
| Instalado por | `install-nativo.sh` | `docker compose up` (cualquier despliegue); el respaldo del host, por `install.sh` / `upgrade-docker.sh` |

En ambos casos el panel web nunca gana la capacidad de ejecutar algo con
privilegios de root: solo escribe el mismo archivo de estado que ya escribía
antes de que este mecanismo existiera para cualquier otro ajuste.
