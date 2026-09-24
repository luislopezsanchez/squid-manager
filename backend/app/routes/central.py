"""Rutas de monitoreo centralizado: nodos remotos de SquidManager que este
panel consulta para mostrar sus métricas junto a las propias.

Ver app/services/central_monitor_service.py para el mecanismo (login +
GET /api/metrics/dashboard del nodo, sin token propio) y
docs/project-log.md ("Monitoreo centralizado de varias instancias") para
el diseño.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.monitored_node import MonitoredNode
from app.services.auth_service import get_current_admin, require_writer
from app.services.central_monitor_service import consultar_nodo, consultar_todos, sincronizar_configuracion
from app.services.metrics_service import get_dashboard
from app.routes.backup import build_backup_dict
from app.i18n import idioma_de_cabecera, traducir

router = APIRouter()

_MASCARA = "***"


class NodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    enabled: bool = True


class NodeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    url: str | None = Field(None, min_length=1, max_length=255)
    username: str | None = Field(None, min_length=1, max_length=100)
    password: str | None = None
    enabled: bool | None = None


class NodeTest(BaseModel):
    url: str
    username: str
    password: str
    # Si se está probando un nodo ya guardado y la contraseña no se
    # reescribió (llega como "***"), esto permite resolverla contra la
    # guardada -sin esto, probar la conexión de un nodo existente sin
    # tocar la contraseña mandaba el placeholder "***" tal cual como si
    # fuera la contraseña real, y la prueba fallaba siempre por
    # "credenciales rechazadas" aunque las guardadas fueran correctas.
    id: int | None = None


def _validar_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, detail="La URL del nodo debe empezar con http:// o https://")
    return url.rstrip("/")


def _to_response(node: MonitoredNode) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "url": node.url,
        "username": node.username,
        "password": _MASCARA,
        "enabled": node.enabled,
    }


@router.get("/nodes")
def list_nodes(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    return [_to_response(n) for n in db.query(MonitoredNode).order_by(MonitoredNode.name).all()]


@router.post("/nodes")
def create_node(
    data: NodeCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    node = MonitoredNode(
        name=data.name.strip(),
        url=_validar_url(data.url),
        username=data.username.strip(),
        password=data.password,
        enabled=data.enabled,
    )
    db.add(node)
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="monitored_node", entity_id=node.id,
        new_value=f"{node.name} ({node.url})",
    ))
    db.commit()
    return _to_response(node)


@router.put("/nodes/{node_id}")
def update_node(
    node_id: int,
    data: NodeUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    node = db.query(MonitoredNode).filter(MonitoredNode.id == node_id).first()
    if not node:
        raise HTTPException(404, detail="Nodo no encontrado")

    if data.name is not None:
        node.name = data.name.strip()
    if data.url is not None:
        node.url = _validar_url(data.url)
    if data.username is not None:
        node.username = data.username.strip()
    if data.password is not None and data.password != _MASCARA:
        node.password = data.password
    if data.enabled is not None:
        node.enabled = data.enabled

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="monitored_node", entity_id=node.id,
        new_value=f"{node.name} ({node.url})",
    ))
    db.commit()
    return _to_response(node)


@router.delete("/nodes/{node_id}", status_code=204)
def delete_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    node = db.query(MonitoredNode).filter(MonitoredNode.id == node_id).first()
    if not node:
        raise HTTPException(404, detail="Nodo no encontrado")
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="monitored_node", entity_id=node.id,
        old_value=f"{node.name} ({node.url})",
    ))
    db.delete(node)
    db.commit()


@router.post("/test")
def test_node(
    data: NodeTest,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_writer),
):
    """Prueba login + dashboard contra un nodo sin necesidad de guardarlo
    antes -mismo patrón que POST /api/ldap/test."""
    password_a_usar = data.password
    if password_a_usar == _MASCARA and data.id is not None:
        existente = db.query(MonitoredNode).filter(MonitoredNode.id == data.id).first()
        if existente:
            password_a_usar = existente.password

    class _NodoTemporal:
        id = 0
        name = "(prueba)"
        url = data.url
        username = data.username
        password = password_a_usar

    resultado = consultar_nodo(_NodoTemporal())
    return resultado


@router.get("/dashboard")
def central_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """El dashboard de este servidor + el de cada nodo remoto habilitado,
    en una sola llamada."""
    nodes = db.query(MonitoredNode).order_by(MonitoredNode.name).all()
    remotos = consultar_todos(nodes)
    idioma = idioma_de_cabecera(request.headers.get("accept-language"))
    local = {
        "id": None,
        "name": traducir("Este servidor", idioma),
        "url": None,
        "status": "ok",
        "data": get_dashboard(db=db),
    }
    return {"nodes": [local, *remotos]}


@router.post("/nodes/{node_id}/sync")
def sync_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Envía la configuración de ESTE servidor al nodo remoto, sobrescribiendo
    la suya -mismo backup/restore JSON que ya existe para un archivo
    descargado a mano, sin archivo intermedio de por medio.

    Requiere que la cuenta guardada para el nodo tenga permisos de
    escritura ahí (una cuenta "viewer" -la recomendada para solo
    monitorear- no alcanza y se informa con claridad, no falla en
    silencio)."""
    node = db.query(MonitoredNode).filter(MonitoredNode.id == node_id).first()
    if not node:
        raise HTTPException(404, detail="Nodo no encontrado")

    backup = build_backup_dict(db, current_admin.username)
    resultado = sincronizar_configuracion(node, backup)

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="sync", entity="monitored_node", entity_id=node.id,
        new_value=f"{node.name} ({node.url}): {resultado['status']}",
    ))
    db.commit()
    return resultado
