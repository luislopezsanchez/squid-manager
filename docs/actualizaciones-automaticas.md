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
  GitHub.
- **Página "Actualizaciones"**: versión instalada vs. la última publicada,
  botón para comprobar en el momento, la lista de commits nuevos (para saber
  qué cambia antes de aprobar), y el resultado de la última actualización
  aplicada.
- **Aprobar**: "Actualizar ahora" o elegir una fecha/hora futura. Se puede
  cancelar una programación mientras no haya arrancado.

La comprobación automática corre cada 6 horas en segundo plano (se puede
apagar en la propia página); no manda ningún dato del servidor a GitHub, solo
consulta su API pública para comparar el commit desplegado contra el último
del repositorio.

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
