"""Modelos SQLAlchemy para SquidManager."""

from app.models.admin import Admin
from app.models.proxy_user import ProxyUser
from app.models.acl import Acl
from app.models.access_rule import AccessRule
from app.models.squid_settings import SquidSetting
from app.models.delay_pool import DelayPool
from app.models.ldap_config import LdapConfig
from app.models.audit_log import AuditLog
from app.models.notification_config import NotificationConfig
from app.models.ldap_user import LdapUser
from app.models.user_group import UserGroup, UserGroupMember
from app.models.syslog_config import SyslogConfig
from app.models.parent_proxy import ParentProxy
from app.models.kerberos_config import KerberosConfig

__all__ = [
    "Admin",
    "ProxyUser",
    "Acl",
    "AccessRule",
    "SquidSetting",
    "DelayPool",
    "LdapConfig",
    "AuditLog",
    "NotificationConfig",
    "LdapUser",
    "UserGroup",
    "UserGroupMember",
    "SyslogConfig",
    "ParentProxy",
    "KerberosConfig",
]
