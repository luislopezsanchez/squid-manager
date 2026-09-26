"""Rutas de monitoreo centralizado: nodos remotos de SquidManager que este
panel consulta para mostrar sus métricas junto a las propias.

Ver app/services/central_monitor_service.py para el mecanismo (login +
GET /api/metrics/dashboard del nodo, sin token propio) y
docs/project-log.md ("Monitoreo centralizado de varias instancias") para
el diseño.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.monitored_node import MonitoredNode
from app.models.central_config import CentralMonitorConfig
from app.models.squid_settings import SquidSetting
from app.services.auth_service import get_current_admin, require_writer
from app.services.central_monitor_service import (
    probar_nodo, sincronizar_configuracion,
    consultar_arbol_de_todos, consultar_detalle_nodo, consultar_detalle_relay,
    PROFUNDIDAD_DEFECTO, PROFUNDIDAD_MAXIMA,
)
from app.services.metrics_service import get_dashboard
from app.routes.backup import build_backup_dict
from app.i18n import idioma_de_cabecera, traducir

router = APIRouter()

_MASCARA = "***"


class CentralConfigIn(BaseModel):
    enabled: bool
    # Independiente de `enabled`: ver el docstring del modelo
    # (CentralMonitorConfig) para el porqué de los dos interruptores.
    monitorizar_hijos: bool = True


def _obtener_o_crear_config(db: Session) -> CentralMonitorConfig:
    config = db.query(CentralMonitorConfig).first()
    if not config:
        config = CentralMonitorConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _requerir_habilitado(db: Session) -> None:
    """Gatea el lado SALIENTE del feature -listar/crear/editar/borrar los
    nodos propios, probarlos, sincronizarles la config, reenviar una ruta
    de detalle hacia ellos-: todo lo que significa "estoy usando esto para
    monitorear a otros". Apagado por defecto significa que esas acciones ni
    siquiera están disponibles, no solo que se ocultan en el frontend.

    A propósito NO gatea el lado ENTRANTE (que otro SquidManager me
    consulte a MÍ como nodo, GET /dashboard): ese nunca necesitó este
    interruptor -alcanza con que quien pregunta tenga una cuenta válida acá,
    ni más ni menos que lo que ya hace falta para cualquier otro endpoint
    de métricas de este proyecto (get_dashboard vía /api/metrics/dashboard
    tampoco pide esto). Antes si lo gateaba, y quien apagaba este
    interruptor pensando "quiero dejar de monitorear a mis nodos" de paso
    dejaba de responderle a SU PROPIO padre -confusión real, reportada en
    vivo 2026-09-26: "se supone que no se necesita habilitar esa función en
    los nodos hijos para poder monitorearlo". Ver
    CentralMonitorConfig.monitorizar_hijos para el interruptor que sí
    corresponde acá (si expongo o no mis propios nodos al respondar)."""
    config = db.query(CentralMonitorConfig).first()
    if not config or not config.enabled:
        raise HTTPException(403, detail="El monitoreo centralizado está deshabilitado en este servidor.")


def _squid_port(db: Session) -> str | None:
    """Puerto donde escucha Squid en ESTE servidor, para que un admin que
    esté monitoreando esto desde otro SquidManager sepa a qué apuntar -no
    hace falta resolver la IP, la ya tiene: es la misma URL con la que
    guardó este servidor como nodo."""
    setting = db.query(SquidSetting).filter(SquidSetting.key == "http_port").first()
    return str(setting.value).strip() if setting else None


_TIPOS_VALIDOS = ("squidmanager", "squid_basico")


def _validar_tipo(tipo: str) -> str:
    if tipo not in _TIPOS_VALIDOS:
        raise HTTPException(400, detail=f"Tipo de nodo inválido: {tipo!r}")
    return tipo


class NodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    # "squidmanager" (otra instancia de SquidManager, con login) o
    # "squid_basico" (Squid puro, sin panel -se lee su Cache Manager
    # directo, sin cuenta). Ver el docstring de MonitoredNode.
    tipo: str = "squidmanager"
    url: str = Field(..., min_length=1, max_length=255)
    # Solo obligatorios para "squidmanager" -un "squid_basico" no tiene
    # cuenta que validar. Se valida en create_node/update_node, no acá:
    # acá no se sabe todavía el `tipo` final en el momento en que Pydantic
    # evalúa cada campo por separado.
    username: str | None = Field(None, max_length=100)
    password: str | None = None
    enabled: bool = True


class NodeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    tipo: str | None = None
    url: str | None = Field(None, min_length=1, max_length=255)
    username: str | None = Field(None, max_length=100)
    password: str | None = None
    enabled: bool | None = None


class NodeTest(BaseModel):
    tipo: str = "squidmanager"
    url: str
    username: str | None = None
    password: str | None = None
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
    # node.tipo puede venir None en memoria (el default de la columna solo
    # se aplica al insertar, ver Column(default=...) en el modelo) -por eso
    # `or "squidmanager"`, no `node.tipo` a secas.
    tipo = node.tipo or "squidmanager"
    return {
        "id": node.id,
        "name": node.name,
        "tipo": tipo,
        "url": node.url,
        "username": node.username,
        "password": _MASCARA if tipo == "squidmanager" else None,
        "enabled": node.enabled,
    }


@router.get("/config")
def get_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Sin gate: hay que poder ver y prender el interruptor aunque esté
    apagado -si esto también se negara con `_requerir_habilitado`, nadie
    podría encenderlo nunca desde el panel."""
    config = _obtener_o_crear_config(db)
    return {
        "enabled": config.enabled,
        "monitorizar_hijos": config.monitorizar_hijos,
        "instance_id": config.instance_id,
    }


@router.put("/config")
def update_config(
    data: CentralConfigIn,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    config = _obtener_o_crear_config(db)
    config.enabled = data.enabled
    config.monitorizar_hijos = data.monitorizar_hijos
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="central_monitor_config",
        new_value=(
            f"{'habilitado' if data.enabled else 'deshabilitado'}, "
            f"monitorizar_hijos={'sí' if data.monitorizar_hijos else 'no'}"
        ),
    ))
    db.commit()
    return {
        "enabled": config.enabled,
        "monitorizar_hijos": config.monitorizar_hijos,
        "instance_id": config.instance_id,
    }


@router.get("/nodes")
def list_nodes(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    _requerir_habilitado(db)
    return [_to_response(n) for n in db.query(MonitoredNode).order_by(MonitoredNode.name).all()]


@router.post("/nodes")
def create_node(
    data: NodeCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    _requerir_habilitado(db)
    tipo = _validar_tipo(data.tipo)
    if tipo == "squidmanager":
        if not data.username or not data.username.strip():
            raise HTTPException(400, detail="El usuario es obligatorio para un nodo de tipo SquidManager")
        if not data.password:
            raise HTTPException(400, detail="La contraseña es obligatoria para un nodo de tipo SquidManager")
    node = MonitoredNode(
        name=data.name.strip(),
        tipo=tipo,
        url=_validar_url(data.url),
        username=data.username.strip() if tipo == "squidmanager" else None,
        password=data.password if tipo == "squidmanager" else None,
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
    _requerir_habilitado(db)
    node = db.query(MonitoredNode).filter(MonitoredNode.id == node_id).first()
    if not node:
        raise HTTPException(404, detail="Nodo no encontrado")

    if data.name is not None:
        node.name = data.name.strip()
    if data.tipo is not None:
        node.tipo = _validar_tipo(data.tipo)
        if node.tipo == "squid_basico":
            # Sin cuenta que validar -limpia lo que hubiera de un tipo
            # SquidManager anterior, no se queda una credencial vieja sin uso.
            node.username = None
            node.password = None
    if data.url is not None:
        node.url = _validar_url(data.url)
    if data.username is not None:
        node.username = data.username.strip()
    if data.password is not None and data.password != _MASCARA:
        node.password = data.password
    if data.enabled is not None:
        node.enabled = data.enabled

    if node.tipo == "squidmanager" and (not node.username or not node.password):
        raise HTTPException(400, detail="Usuario y contraseña son obligatorios para un nodo de tipo SquidManager")

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
    _requerir_habilitado(db)
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
    antes -mismo patrón que POST /api/ldap/test. También chequea si ese
    nodo tiene el monitoreo centralizado habilitado (ver probar_nodo): sin
    esto, la prueba decía "conexión exitosa" aunque el remoto fuera a
    rechazar después la consulta real del árbol."""
    _requerir_habilitado(db)
    tipo = _validar_tipo(data.tipo)
    password_a_usar = data.password
    if tipo == "squidmanager" and password_a_usar == _MASCARA and data.id is not None:
        existente = db.query(MonitoredNode).filter(MonitoredNode.id == data.id).first()
        if existente:
            password_a_usar = existente.password

    class _NodoTemporal:
        id = 0
        name = "(prueba)"
        url = data.url
        username = data.username
        password = password_a_usar

    _NodoTemporal.tipo = tipo

    resultado = probar_nodo(_NodoTemporal())
    return resultado


@router.get("/dashboard")
def central_dashboard(
    request: Request,
    profundidad: int = Query(PROFUNDIDAD_DEFECTO, ge=0, le=PROFUNDIDAD_MAXIMA),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """El dashboard de este servidor (`self`) y, si `profundidad` > 0 Y este
    servidor tiene el monitoreo habilitado (`enabled`) Y `monitorizar_hijos`
    prendido, el árbol de sus propios nodos remotos habilitados
    (`children`).

    Mismo endpoint para dos llamadores distintos: el panel de este servidor
    (llamada normal, con su propio token) y cualquier OTRO SquidManager que
    tenga a este como nodo (login + token de una cuenta de acá, ver
    central_monitor_service.consultar_arbol) -así la jerarquía se arma sola,
    nivel por nivel, sin que un servidor necesite conocer ni tener
    credenciales de nada más allá de sus propios nodos directos.

    A propósito SIN _requerir_habilitado(): a diferencia del resto de esta
    sección, esto responde siempre que quien pregunte tenga una cuenta
    válida acá, esté o no prendido el interruptor local -"dejarse
    monitorear" nunca debería depender de un interruptor propio, alcanza
    con las credenciales que el padre ya tiene guardadas (ver el docstring
    de _requerir_habilitado). Confusión real, reportada en vivo
    2026-09-26: un admin apagaba el interruptor pensando "dejo de
    monitorear a mis nodos" y de paso su propio padre empezaba a verlo
    "Sin conexión" (403), sin haber tocado nada del lado del padre.

    `children` sale vacío si falta cualquiera de los dos -`enabled` o
    `monitorizar_hijos`-, para cualquiera de los dos llamadores por igual:
    no hay forma de distinguir "mi propio panel" de "un padre" en la
    petición en sí (los dos autentican igual), así que la única forma
    limpia de no exponer los nodos propios es no recorrerlos en absoluto,
    sea quien sea el que pregunta."""
    config = _obtener_o_crear_config(db)
    idioma = idioma_de_cabecera(request.headers.get("accept-language"))

    nodes = db.query(MonitoredNode).order_by(MonitoredNode.name).all() if (config.enabled and config.monitorizar_hijos) else []
    children = consultar_arbol_de_todos(nodes, profundidad_restante=profundidad - 1) if profundidad > 0 else []

    return {
        "self": {
            "instance_id": config.instance_id,
            "name": traducir("Este servidor", idioma),
            "squid_port": _squid_port(db),
            "status": "ok",
            "data": get_dashboard(db=db),
        },
        "children": children,
    }


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
    _requerir_habilitado(db)
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


@router.get("/nodes/detalle-por-ruta")
def node_detalle_por_ruta(
    ruta: str = Query(..., description="ids separados por coma: del hijo directo de quien pregunta hacia el nieto/bisnieto pedido"),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Top usuarios, top dominios y últimas conexiones de CUALQUIER nodo del
    árbol, no solo un hijo directo -datos adicionales para el modal "Ver
    más". Un hijo directo es una ruta de un solo id (ej. «7»); un nieto o
    bisnieto es una ruta más larga (ej. «7,1,1»: mi nodo 7, después su nodo
    1, después el nodo 1 de ese).

    Cada salto resuelve el PRIMER id de la ruta con sus propias
    credenciales; si queda más ruta, se la reenvía tal cual a ESE nodo, que
    hace lo mismo con la suya (ver consultar_detalle_relay) -mismo
    principio que ya usa el árbol de dashboards (self+children) para la
    jerarquía multi-nivel: este servidor nunca necesita las credenciales de
    nada más allá de sus propios nodos directos. Reemplaza a la vieja
    GET /nodes/{id}/detalle (un id suelto, sin nunca poder alcanzar más
    allá de un hijo directo -bug real, visto en pruebas en vivo con una
    jerarquía de 4 niveles, 2026-09-26)."""
    _requerir_habilitado(db)
    try:
        ids = [int(x) for x in ruta.split(",") if x.strip() != ""]
    except ValueError:
        raise HTTPException(400, detail="La ruta debe ser una lista de ids separados por coma")
    if not ids:
        raise HTTPException(400, detail="La ruta no puede estar vacía")
    if len(ids) > PROFUNDIDAD_MAXIMA:
        raise HTTPException(400, detail=f"La ruta no puede tener más de {PROFUNDIDAD_MAXIMA} saltos")

    primero, resto = ids[0], ids[1:]

    if resto:
        # Reenviar el resto de la ruta es "prestar" uno de mis propios
        # nodos para que alguien vea a través de mí -si decidí no
        # monitorizarlos, tampoco presto el acceso a ellos, aunque el nodo
        # en sí siga configurado acá.
        config = _obtener_o_crear_config(db)
        if not config.monitorizar_hijos:
            raise HTTPException(
                403,
                detail="Este servidor tiene desactivado \"Monitorizar mis nodos\": no reenvía pedidos hacia sus propios nodos configurados.",
            )

    node = db.query(MonitoredNode).filter(MonitoredNode.id == primero).first()
    if not node:
        raise HTTPException(404, detail="Nodo no encontrado")

    if not resto:
        return consultar_detalle_nodo(node)
    return consultar_detalle_relay(node, resto)
