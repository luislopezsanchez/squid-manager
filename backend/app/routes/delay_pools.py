"""Rutas de gestión de Delay Pools (control de ancho de banda).

Dos formas de regla conviven:
- Nueva (con `targets`): varios objetivos y límite de velocidad de descarga,
  ver services/bandwidth_service.py.
- Antigua (sin `targets`): una ACL y los parámetros de Squid tal cual. Es lo
  que ya había guardado y lo que crea quota_service.py; sigue funcionando igual.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.admin import Admin
from app.models.delay_pool import DelayPool
from app.models.audit_log import AuditLog
from app.services import bandwidth_service as bw
from app.services.auth_service import get_current_admin, require_writer
from app.services.config_state import mark_dirty
from app.services.squid_names import validate_value

router = APIRouter()


class Objetivo(BaseModel):
    kind: str = Field(..., description="acl, user, group, tipo o all")
    value: str = Field("", max_length=255)


class DelayPoolCreate(BaseModel):
    pool_class: int | None = Field(None, ge=1, le=5, description="Clase 1-5 (reglas antiguas)")
    parameters: str | None = Field(None, description="Parámetros en formato Squid (reglas antiguas)")
    acl_name: str | None = Field(None, description="ACL asociada al pool (reglas antiguas)")
    description: str | None = None
    enabled: bool = True
    # Reglas nuevas
    targets: list[Objetivo] | None = None
    download_bps: int | None = Field(None, ge=1)
    shared: bool = True


class DelayPoolUpdate(BaseModel):
    pool_class: int | None = Field(None, ge=1, le=5)
    parameters: str | None = None
    acl_name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    targets: list[Objetivo] | None = None
    download_bps: int | None = Field(None, ge=1)
    shared: bool | None = None


def _resp(p: DelayPool) -> dict:
    return {
        "id": p.id, "pool_class": p.pool_class, "parameters": p.parameters,
        "acl_name": p.acl_name, "description": p.description, "enabled": p.enabled,
        "targets": bw.cargar_objetivos(p) if p.targets is not None else None,
        "download_bps": p.download_bps, "shared": bool(p.shared),
        "gestionado": bool(p.quota_id or p.group_quota_id),
    }


@router.get("/presets")
def presets(_: Admin = Depends(get_current_admin)):
    """Tipos de tráfico que se pueden elegir sin escribir expresiones regulares."""
    return [
        {"clave": k, "etiqueta": v["etiqueta"], "descripcion": v["descripcion"]}
        for k, v in bw.TIPOS_TRAFICO.items()
    ]


@router.get("/")
def list_delay_pools(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todos los delay pools."""
    return [_resp(p) for p in db.query(DelayPool).order_by(DelayPool.id).all()]


def _aplicar_v2(db: Session, pool: DelayPool, targets, download_bps, shared: bool) -> None:
    resueltos = bw.resolver_objetivos(db, [t if isinstance(t, dict) else t.model_dump() for t in targets])
    bw.validar_limite(download_bps)
    pool.targets, pool.acl_names = bw.serializar_objetivos(resueltos)
    pool.download_bps = download_bps
    pool.shared = shared
    # Campos antiguos coherentes: la primera ACL y un resumen de los parámetros, para
    # que lo que aún lee `acl_name` / `parameters` (buscador, backups viejos) no se rompa.
    pool.acl_name = resueltos[0]["acl"]
    pool.pool_class, pool.parameters = bw.parametros_descarga(download_bps, shared)


@router.post("/", status_code=201)
def create_delay_pool(
    data: DelayPoolCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Crea un nuevo delay pool."""
    pool = DelayPool(description=data.description, enabled=data.enabled, pool_class=1, parameters="")
    if data.targets is not None:
        _aplicar_v2(db, pool, data.targets, data.download_bps, data.shared)
        resumen = f"{pool.acl_names}: descarga {data.download_bps} B/s"
    else:
        if not data.pool_class or not data.parameters:
            raise HTTPException(400, detail="Falta la clase o los parámetros del delay pool.")
        # parameters y acl_name acaban tal cual en delay_parameters/delay_access:
        # sin esto, un salto de línea en cualquiera de los dos inserta una
        # directiva arbitraria en el squid.conf generado.
        pool.pool_class = data.pool_class
        pool.parameters = validate_value(data.parameters, field="parámetros del delay pool")
        pool.acl_name = validate_value(data.acl_name, field="ACL del delay pool") if data.acl_name else None
        resumen = f"class {data.pool_class}: {data.parameters}"
    db.add(pool)
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="delay_pool", entity_id=pool.id, new_value=resumen,
    ))
    db.commit()
    mark_dirty()
    return _resp(pool)


@router.put("/{pool_id}")
def update_delay_pool(
    pool_id: int,
    data: DelayPoolUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Actualiza un delay pool."""
    pool = db.query(DelayPool).filter(DelayPool.id == pool_id).first()
    if not pool:
        raise HTTPException(404, detail="Delay pool no encontrado")

    updates = data.model_dump(exclude_unset=True)

    if "targets" in updates and updates["targets"] is not None:
        # Regla nueva (o una antigua que se edita con el formulario nuevo).
        _aplicar_v2(
            db, pool, updates["targets"],
            updates.get("download_bps", pool.download_bps),
            updates.get("shared", bool(pool.shared)),
        )
        for k in ("description", "enabled"):
            if k in updates:
                setattr(pool, k, updates[k])
    else:
        # "parameters" no admite NULL en la BD (a diferencia de "acl_name"): un
        # PUT con {"parameters": null} pasaba antes el guard "is not None" (falso
        # para None) sin validar, y el setattr de abajo intentaba grabar NULL en
        # una columna NOT NULL, reventando con un IntegrityError/500 sin manejar
        # en vez del 400 limpio que el resto de esta validacion garantiza.
        if "parameters" in updates:
            if not updates["parameters"]:
                raise HTTPException(400, detail="Los parámetros del delay pool no pueden quedar vacíos.")
            updates["parameters"] = validate_value(updates["parameters"], field="parámetros del delay pool")
        if "acl_name" in updates:
            # Vacio/None limpia la ACL (igual que al crear un pool sin ACL);
            # cualquier otro valor se valida igual que el resto de campos.
            updates["acl_name"] = validate_value(updates["acl_name"], field="ACL del delay pool") if updates["acl_name"] else None
        for k in ("targets", "download_bps", "shared"):
            updates.pop(k, None)
        for field, value in updates.items():
            setattr(pool, field, value)
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="delay_pool", entity_id=pool.id,
    ))
    db.commit()
    mark_dirty()
    return _resp(pool)


@router.delete("/{pool_id}", status_code=204)
def delete_delay_pool(
    pool_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Elimina un delay pool."""
    pool = db.query(DelayPool).filter(DelayPool.id == pool_id).first()
    if not pool:
        raise HTTPException(404, detail="Delay pool no encontrado")

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="delay_pool", entity_id=pool.id,
        old_value=f"class {pool.pool_class}: {pool.parameters}",
    ))
    db.delete(pool)
    db.commit()
    mark_dirty()
