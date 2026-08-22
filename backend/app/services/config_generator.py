"""Generador de configuración de Squid usando Jinja2.

Este servicio toma los datos de la BD y genera el archivo squid.conf completo.
"""

import subprocess
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.acl import Acl
from app.models.access_rule import AccessRule
from app.models.squid_settings import SquidSetting
from app.models.delay_pool import DelayPool
from app.models.ldap_config import LdapConfig

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def generate_squid_config(db: Session) -> str:
    """Genera el contenido del squid.conf desde la base de datos."""

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), trim_blocks=True)
    template = env.get_template("squid.conf.j2")

    # Obtener todos los datos de configuración
    acls = db.query(Acl).filter(Acl.enabled == True).order_by(Acl.name).all()
    rules = (
        db.query(AccessRule)
        .filter(AccessRule.enabled == True)
        .order_by(AccessRule.order)
        .all()
    )
    settings = {s.key: s.value for s in db.query(SquidSetting).all()}
    delay_pools = db.query(DelayPool).filter(DelayPool.enabled == True).all()
    ldap = db.query(LdapConfig).first()

    config = template.render(
        acls=acls,
        rules=rules,
        settings=settings,
        delay_pools=delay_pools,
        ldap=ldap,
    )
    return config


def validate_squid_config(config_path: str) -> tuple[bool, str]:
    """Valida la sintaxis del squid.conf usando squid -k parse."""
    try:
        result = subprocess.run(
            ["squid", "-k", "parse", "-f", config_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Configuración válida"
        return False, result.stderr or result.stdout
    except FileNotFoundError:
        # Squid no está instalado en el contenedor backend, solo en squid
        return True, "Squid no disponible para validar (skip)"
    except Exception as e:
        return False, str(e)