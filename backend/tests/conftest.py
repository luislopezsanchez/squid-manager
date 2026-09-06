"""Configuración compartida de la suite de tests.

DATABASE_URL ya no tiene un valor por defecto en app.config.Settings (se
quitó a propósito: un default con pinta de credencial real invitaba a que
alguien lo copiara a un .env de verdad, y los dos despliegues soportados
siempre la fijan igual). Ningún test de esta suite se conecta de verdad a
una base de datos — todos usan FakeDB o mocks — pero Settings() se
instancia igual al importar app.config, así que necesita un valor con el
que arrancar. Se fija aquí, antes de que pytest importe ningún módulo de
`app`, para que la ausencia del default en producción no rompa la suite.
"""

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://test:test@localhost/test_no_se_usa"
)
