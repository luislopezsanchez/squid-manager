"""Interfaz comun para controlar Squid, viva donde viva.

El panel necesita seis cosas de Squid, y solo seis: recargarlo, reiniciarlo,
validar una configuracion, saber si esta vivo, leer sus contadores y hacer
efectivo un cambio de puerto. Todo lo demas —generar el squid.conf, escribir
los ficheros de usuarios, hablar con la base de datos— es identico en
cualquier despliegue.

Aislar esas seis operaciones detras de una interfaz es lo que permite que el
mismo panel controle un Squid en contenedor o uno instalado en el sistema, sin
que el resto del codigo se entere de la diferencia.
"""

from __future__ import annotations


# Puerto en el que Squid escucha DENTRO del contenedor. Es una constante a
# proposito: en modo Docker el puerto que el administrador elige en el panel es
# el que se publica hacia fuera y se mapea contra este, de modo que el puerto
# solo se guarda en un sitio. En modo nativo no hay mapeo y esta constante no
# se usa: Squid escucha directamente donde diga el panel.
INTERNAL_SQUID_PORT = "3128"


class ProxyRuntime:
    """Operaciones que el panel necesita del proceso de Squid."""

    #: Nombre corto del modo, para mensajes y diagnostico.
    name = "base"

    def reconfigure(self) -> tuple[bool, str]:
        """Relee la configuracion sin cortar las conexiones en curso."""
        raise NotImplementedError

    def restart(self) -> tuple[bool, str]:
        """Reinicia Squid por completo."""
        raise NotImplementedError

    def parse_config(self, path: str) -> tuple[int, str]:
        """Ejecuta `squid -k parse` sobre un fichero y devuelve (codigo, salida).

        Tiene que ejecutarse donde este el binario de Squid. Cuando esto se
        hacia en el backend, el binario no existia, la excepcion se capturaba y
        cualquier configuracion se daba por valida.
        """
        raise NotImplementedError

    def status(self) -> dict:
        """Estado del servicio: {running, state, pid, errors}."""
        raise NotImplementedError

    def read_stats_raw(self) -> str:
        """Vuelca /proc/net/dev y los contadores de cgroup, ya etiquetados.

        Devuelve texto crudo con el mismo formato en los dos modos, para que
        quien lo interpreta (metrics_service) no dependa del despliegue.
        """
        raise NotImplementedError

    def apply_port(self, new_port: str) -> tuple[bool, str]:
        """Hace efectivo un puerto nuevo.

        En contenedor obliga a recrearlo, porque el puerto publicado se fija al
        crearlo. En una instalacion del sistema basta con reiniciar, porque el
        puerto ya esta en el squid.conf que se acaba de escribir.
        """
        raise NotImplementedError

    def verify_port(self, expected_port: str) -> tuple[bool, str]:
        """Comprueba que el proxy es accesible de verdad en ese puerto.

        Es la comprobacion que evita el fallo mas silencioso de todos: Squid
        vivo y aparentemente sano, escuchando donde nadie le habla.
        """
        raise NotImplementedError

    def sync_port_state(self, port: str) -> tuple[bool, str]:
        """Deja constancia del puerto fuera del squid.conf, si hace falta.

        En contenedor el puerto vive tambien en el .env, que es lo que alimenta
        el mapeo: si las dos copias divergen, Docker publica un puerto donde
        Squid ya no escucha. En una instalacion del sistema no hay segunda
        copia que mantener, y por eso el comportamiento por defecto es no hacer
        nada.
        """
        return True, "sin estado externo que sincronizar"

    def cache_manager_report(self, report: str, port: str) -> tuple[bool, str]:
        """Reporte del Cache Manager de Squid ('info', 'storedir', ...), en crudo.

        Squid lo expone por HTTP normal en su propio puerto de proxy
        (/squid-internal-mgr/<report>), protegido en el squid.conf generado
        con "http_access allow localhost manager" -en modo nativo eso alcanza
        sin tocar nada, porque el backend corre en el mismo host. En modo
        Docker NO alcanza: el backend esta en otro contenedor, y su IP de
        origen no matchea el ACL "localhost" de Squid -ensanchar esa regla a
        la red interna de Docker seria abrir un permiso nuevo, justo lo que
        se evito a proposito, ver DockerRuntime.cache_manager_report.
        """
        raise NotImplementedError

    def listen_port(self, desired_port: str) -> str:
        """Puerto que hay que escribir en la directiva `http_port`.

        En contenedor es una constante, porque quien traduce al puerto elegido
        es el mapeo de Docker. En instalacion nativa no hay traduccion: Squid
        escucha directamente donde diga el panel.
        """
        raise NotImplementedError
