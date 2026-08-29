"""Seleccion del runtime de Squid segun el modo de despliegue."""

import logging

from app.config import settings

from .base import ProxyRuntime

logger = logging.getLogger(__name__)

_runtime: ProxyRuntime | None = None


def get_runtime() -> ProxyRuntime:
    """Devuelve el runtime del modo configurado (se construye una sola vez).

    El modo por defecto es `docker`: las instalaciones que ya existen no tienen
    que cambiar nada para seguir funcionando igual.
    """
    global _runtime
    if _runtime is not None:
        return _runtime

    modo = (settings.DEPLOY_MODE or "docker").strip().lower()
    if modo == "native":
        from .native_runtime import NativeRuntime

        _runtime = NativeRuntime()
    else:
        if modo != "docker":
            logger.warning(
                f"DEPLOY_MODE='{modo}' no se reconoce; se usa 'docker'. "
                f"Valores validos: docker, native."
            )
        from .docker_runtime import DockerRuntime

        _runtime = DockerRuntime()

    logger.info(f"Runtime de Squid: {_runtime.name}")
    return _runtime


def reset_runtime() -> None:
    """Olvida el runtime cacheado (solo lo usan los tests)."""
    global _runtime
    _runtime = None


__all__ = ["ProxyRuntime", "get_runtime", "reset_runtime"]
