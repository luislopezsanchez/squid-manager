"""Rutas de la API REST de SquidManager."""

from app.routes import auth, proxy_users, acls, access_rules, squid_config

routes_config = [
    {"router": auth.router, "prefix": "/api/auth", "tags": ["Autenticación"]},
    {"router": proxy_users.router, "prefix": "/api/proxy-users", "tags": ["Usuarios del Proxy"]},
    {"router": acls.router, "prefix": "/api/acls", "tags": ["ACLs"]},
    {"router": access_rules.router, "prefix": "/api/access-rules", "tags": ["Reglas de Acceso"]},
    {"router": squid_config.router, "prefix": "/api/squid", "tags": ["Configuración Squid"]},
]