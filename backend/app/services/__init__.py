"""Servicios del backend."""

from app.services.auth_service import (
    authenticate_admin, create_access_token, get_current_admin,
    get_password_hash, verify_password, require_writer, require_superadmin,
)
from app.services.config_generator import generate_squid_config
from app.services.squid_service import (
    reload_squid, get_squid_status, write_passwd_file, validate_squid_config,
    apply_squid_config, purge_credentials, active_proxy_users,
)

__all__ = [
    "authenticate_admin", "create_access_token", "get_current_admin",
    "get_password_hash", "verify_password", "require_writer", "require_superadmin",
    "generate_squid_config", "validate_squid_config",
    "reload_squid", "get_squid_status", "write_passwd_file",
    "apply_squid_config", "purge_credentials", "active_proxy_users",
]
