# Actualizaciones desde el panel

Comprueba si hay una versión nueva de SquidManager publicada en GitHub, muestra
qué cambió, y permite aprobarla —de inmediato o programada para una fecha y
hora concretas— sin tener que entrar por SSH. Solo para **instalación
nativa** por ahora (ver la nota al final).

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
4. Pulsá **"Actualizar ahora"**. Queda aprobada al instante y se aplica en
   los segundos siguientes (no hace falta esperar al temporizador: aprobar
   "ahora" lo adelanta).
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
6. El sistema revisa **una vez por minuto** si ya es la hora: puede tardar
   hasta un minuto después de lo elegido en arrancar. Si pasan más de 3
   minutos sin arrancar, la tarjeta lo marca como **"atrasada"** — señal de
   que el temporizador del servidor no está corriendo, hay que revisarlo por
   SSH (`systemctl status squidmanager-autoupdate.timer`).
7. Igual que aplicar "ahora": al terminar, aparece el aviso de "Recargar" en
   cualquier página.

## Por qué es seguro: separar "decidir cuándo" de "ejecutar"

El backend web corre con el mismo usuario restringido de siempre (sin ser
superusuario de su propia base de datos, y con exactamente 4 líneas fijas de
`sudoers` — ninguna genérica). Aprobar una actualización, desde el panel, solo
escribe un archivo de estado (igual de privilegios que guardar cualquier otro
ajuste). Un temporizador de systemd, corriendo como root cada minuto —o
adelantado al toque con la única orden de sudo que existe para esto, sin
argumentos—, es quien de verdad decide si corresponde actuar y, si es así,
invoca el mismo script de actualización (`upgrade-nativo.sh`) que ya se usa a
mano desde hace tiempo, en una unidad de systemd aparte —para que reiniciar el
panel a mitad de la actualización no la mate a mitad de camino—.

## Si una programación no arranca a tiempo

El temporizador revisa cada minuto, así que una actualización programada
debería empezar dentro del minuto de la hora elegida. Si pasan más de 3
minutos sin que arranque, el panel lo marca como "atrasada" y avisa —no se
cancela sola, pero deja de mostrar "programada" en silencio para siempre.
Suele significar que el temporizador está caído: `systemctl status
squidmanager-autoupdate.timer` en el servidor.

## Solo instalación nativa

En Docker, el contenedor del backend no puede reconstruirse ni reiniciar a
sus hermanos sin el socket de Docker montado —el mismo riesgo, ya conocido,
que evitamos sumar acá—. Para Docker sigue existiendo `upgrade-docker.sh`,
a mano, como hasta ahora.
