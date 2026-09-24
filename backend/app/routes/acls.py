"""Rutas de gestión de ACLs."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, Query
from sqlalchemy.orm import Session, defer

from app.database import get_db
from app.models.admin import Admin
from app.models.acl import Acl
from app.models.audit_log import AuditLog
from app.schemas.acl import AclCreate, AclUpdate, AclResponse
from app.services.auth_service import get_current_admin, require_writer
from app.services.notification_service import queue_notification
from app.services.config_state import mark_dirty
from app.services.squid_names import (
    validate_name, validate_acl_type, validate_value, validar_lista_dominios,
    ensure_not_referenced, find_references,
)

router = APIRouter()

# El umbral que decide 'inline' vs 'file' (200 dominios) y el tope combinado
# (MAX_DOMINIOS_POR_CARGA) viven en squid_service.aplicar_lista_dominios,
# que es quien de verdad decide -ver ese docstring para el detalle.
MAX_UPLOAD_BYTES = 250 * 1024 * 1024  # ver MAX_DOMINIOS_POR_CARGA en squid_names.py


def _to_response(acl: Acl) -> AclResponse:
    """Arma la respuesta sin tocar `acl.value` cuando source == 'file' -ni
    siquiera para una ACL vieja que todavía no pasó por la migración
    perezosa (ver squid_service.build_acl_list_files): acceder al atributo
    dispararía su carga completa (potencialmente millones de líneas) solo
    para descartarlo en la siguiente línea. `line_count` es lo que el
    frontend necesita mostrar en su lugar."""
    return AclResponse(
        id=acl.id, name=acl.name, type=acl.type,
        value=None if acl.source == "file" else acl.value,
        source=acl.source, line_count=acl.line_count,
        is_category=acl.is_category, display_name=acl.display_name,
        sync_url=acl.sync_url, last_synced_at=acl.last_synced_at, last_sync_status=acl.last_sync_status,
        description=acl.description, enabled=acl.enabled,
        created_at=acl.created_at, updated_at=acl.updated_at,
    )


# Solo dominios: una "categoría" es una ACL de dominios con nombre
# reutilizable -no tiene sentido categorizar por IP, puerto u horario.
TIPOS_CATEGORIZABLES = ("dstdomain", "dstdom_regex")


async def _leer_archivo_subido(file: UploadFile) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(413, detail=f"El archivo supera el límite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/", response_model=list[AclResponse])
def list_acls(
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    is_category: bool | None = Query(None, description="Filtra por categorías de dominio (true) o ACLs técnicas (false). Sin filtro por defecto."),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista las ACLs, paginadas.

    limit por defecto en 1000 -generoso, para no romper a los consumidores
    actuales de la API que no mandan estos parametros- (auditoria
    2026-09-09, hallazgo 09-001).

    defer(Acl.value): sin esto, listar ACLs traía de la BD el contenido
    completo de cada una -incluidas las 'file', que pueden tener millones
    de líneas- para descartarlo enseguida en _to_response(). Con listas
    grandes, esto por sí solo hacía que abrir la página de ACLs tardara
    varios segundos y moviera cientos de MB por la red hacia el navegador.
    """
    query = db.query(Acl).options(defer(Acl.value))
    if is_category is not None:
        query = query.filter(Acl.is_category == is_category)
    acls = query.order_by(Acl.name).offset(offset).limit(limit).all()
    return [_to_response(a) for a in acls]


@router.get("/unused", response_model=list[str])
def list_unused_acls(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Nombres de ACLs que no usa ninguna regla ni delay pool.

    Una ACL por sí sola no bloquea nada: hasta que una regla de acceso la
    referencia, no tiene ningún efecto sobre el tráfico.
    """
    acls = db.query(Acl).options(defer(Acl.value)).order_by(Acl.name).all()
    return [a.name for a in acls if not find_references(db, a.name)]


@router.post("/", response_model=AclResponse, status_code=201)
def create_acl(
    data: AclCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Crea una nueva ACL."""
    name = validate_name(data.name, "ACL")
    acl_type = validate_acl_type(data.type)
    value = validate_value(data.value)

    if data.is_category and acl_type not in TIPOS_CATEGORIZABLES:
        raise HTTPException(400, detail="Una categoría solo puede ser de tipo dominio (dstdomain o dstdom_regex).")

    existing = db.query(Acl).filter(Acl.name == name).first()
    if existing:
        raise HTTPException(400, detail="Ya existe una ACL con ese nombre")

    acl = Acl(name=name, type=acl_type, value=value, is_category=data.is_category,
              display_name=data.display_name or None,
              description=data.description, enabled=data.enabled)
    db.add(acl)
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="acl", entity_id=acl.id, new_value=f"{name} {acl_type} {value}",
    ))
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "acl_change",
                           "ACL creada",
                           f"El admin {current_admin.username} creó la ACL '{name}' ({acl_type}).")
    return _to_response(acl)


@router.put("/{acl_id}", response_model=AclResponse)
def update_acl(
    acl_id: int,
    data: AclUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Actualiza una ACL."""
    acl = db.query(Acl).filter(Acl.id == acl_id).first()
    if not acl:
        raise HTTPException(404, detail="ACL no encontrada")

    changes = data.model_dump(exclude_unset=True)
    # No leer acl.value para una ACL 'file': si todavía no pasó por la
    # migración perezosa (build_acl_list_files), sigue teniendo el
    # contenido completo -potencialmente millones de líneas- y este log es
    # el único motivo por el que se traería aquí, para un cambio que ni
    # siquiera toca el valor (por ejemplo, activar/desactivar la ACL).
    def _resumen(a: Acl) -> str:
        if a.source == "file":
            return f"{a.name} {a.type} ({a.line_count or 0} dominios, archivo)"
        return f"{a.name} {a.type} {a.value}"

    old_value = _resumen(acl)

    # Una ACL 'file' viene de una carga masiva (backend/app/routes/acls.py
    # bulk-domains): su valor son miles de dominios, uno por línea, y no
    # tiene sentido editarlo a mano en un campo de texto. Se vuelve a subir
    # el archivo (mismo endpoint, mismo nombre) para actualizarla.
    if acl.source == "file" and "value" in changes:
        raise HTTPException(
            400,
            detail=(
                f"«{acl.name}» viene de una carga masiva de dominios; su valor no "
                "se edita a mano. Volvé a subir el archivo actualizado en "
                "«Cargar dominios» con el mismo nombre de ACL para reemplazarlo."
            ),
        )

    # Renombrar rompe las reglas que citan el nombre anterior.
    if "name" in changes and changes["name"] != acl.name:
        if acl.source == "file":
            raise HTTPException(
                400,
                detail=(
                    f"«{acl.name}» viene de una carga masiva de dominios: el archivo "
                    "en disco está nombrado según la ACL. Borrala y volvé a subir el "
                    "archivo con el nombre nuevo en vez de renombrarla."
                ),
            )
        ensure_not_referenced(db, acl.name, "renombrar")
        changes["name"] = validate_name(changes["name"], "ACL")
        if db.query(Acl).filter(Acl.name == changes["name"], Acl.id != acl_id).first():
            raise HTTPException(400, detail="Ya existe una ACL con ese nombre")
    if "type" in changes and changes["type"] is not None:
        if acl.source == "file" and changes["type"] != acl.type:
            raise HTTPException(
                400,
                detail=f"«{acl.name}» viene de una carga masiva: no se le cambia el tipo a mano.",
            )
        changes["type"] = validate_acl_type(changes["type"])
    if "value" in changes and changes["value"] is not None:
        changes["value"] = validate_value(changes["value"])

    tipo_resultante = changes.get("type", acl.type)
    categoria_resultante = changes.get("is_category", acl.is_category)
    if categoria_resultante and tipo_resultante not in TIPOS_CATEGORIZABLES:
        raise HTTPException(400, detail="Una categoría solo puede ser de tipo dominio (dstdomain o dstdom_regex).")

    if "sync_url" in changes and changes["sync_url"]:
        if not changes["sync_url"].startswith("https://"):
            raise HTTPException(400, detail="La URL de sincronización debe empezar con https://.")
    elif "sync_url" in changes:
        changes["sync_url"] = None  # cadena vacía = desconectar la sincronización

    if "display_name" in changes and not changes["display_name"]:
        changes["display_name"] = None  # cadena vacía = volver a mostrar el nombre técnico

    for field, value in changes.items():
        setattr(acl, field, value)

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="acl", entity_id=acl.id,
        old_value=old_value, new_value=_resumen(acl),
    ))
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "acl_change",
                           "ACL actualizada",
                           f"El admin {current_admin.username} actualizó la ACL '{acl.name}'.")
    return _to_response(acl)


@router.delete("/{acl_id}", status_code=204)
def delete_acl(
    acl_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Elimina una ACL."""
    acl = db.query(Acl).filter(Acl.id == acl_id).first()
    if not acl:
        raise HTTPException(404, detail="ACL no encontrada")

    ensure_not_referenced(db, acl.name, "eliminar")

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="acl", entity_id=acl.id, old_value=acl.name,
    ))
    name = acl.name
    db.delete(acl)
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "acl_change",
                           "ACL eliminada",
                           f"El admin {current_admin.username} eliminó la ACL '{name}'.")


@router.post("/bulk-domains")
async def cargar_dominios_masivo(
    file: UploadFile = File(...),
    acl_name: str = Form(...),
    modo: str = Form("reemplazar"),
    acl_type: str = Form("dstdomain"),
    description: str | None = Form(None),
    is_category: bool = Form(False),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Crea o actualiza una ACL de dominios a partir de un archivo (uno por
    línea; líneas vacías o que empiezan con '#' se ignoran).

    Por debajo de 200 dominios, la ACL queda 'inline' (se ve
    y se edita como cualquier otra); por encima, pasa a 'file' -un archivo
    aparte que Squid lee directo, ver squid_service.build_acl_list_files-.
    El umbral se reevalúa en cada carga: una lista que creció puede pasar de
    inline a file, y una que se redujo (con 'reemplazar') puede volver a
    inline.

    `modo`: 'reemplazar' (el archivo define la lista completa) o 'agregar'
    (se suma a lo que ya había, sin duplicar).
    """
    if modo not in ("reemplazar", "agregar"):
        raise HTTPException(400, detail="El modo debe ser 'reemplazar' o 'agregar'.")
    if acl_type not in ("dstdomain", "dstdom_regex"):
        raise HTTPException(400, detail="La carga masiva es solo para ACLs de dominio (dstdomain/dstdom_regex).")

    name = validate_name(acl_name, "ACL")

    contenido = await _leer_archivo_subido(file)
    texto = contenido.decode("utf-8", errors="replace")
    dominios_nuevos, rechazados = validar_lista_dominios(texto.splitlines())

    if not dominios_nuevos:
        raise HTTPException(
            400,
            detail=(
                "El archivo no tiene ningún dominio válido para importar"
                + (f" ({len(rechazados)} línea(s) rechazada(s))." if rechazados else ".")
            ),
        )

    from app.services.squid_service import aplicar_lista_dominios

    acl, info = aplicar_lista_dominios(
        db, name, acl_type, dominios_nuevos, modo,
        description, is_category,
        admin_id=current_admin.id, admin_username=current_admin.username,
    )

    if background_tasks:
        queue_notification(background_tasks, db, "acl_change",
                           "ACL cargada desde archivo",
                           f"El admin {current_admin.username} cargó {info['combinados']} dominios en la ACL '{name}' ({info['source']}).")

    return {
        "acl": _to_response(acl).model_dump(mode="json"),
        "dominios_importados": info["combinados"],
        "dominios_nuevos": len(dominios_nuevos),
        "rechazados": rechazados[:20],
        "total_rechazados": len(rechazados),
    }


@router.post("/hagezi-preset")
def cargar_categorias_hagezi(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Crea (o reconecta) un subconjunto curado de categorías de HaGeZi
    dns-blocklists (gambling, nsfw, anti-piracy) y las sincroniza ahora
    mismo. Cada una queda con `sync_url` cargado, así el hilo de fondo
    (category_sync_service) la refresca sola una vez al día -en modo
    'agregar', nunca 'reemplazar', para no pisar dominios que el admin
    sume a mano encima."""
    from app.services.category_sync_service import cargar_preset_hagezi

    resultados = cargar_preset_hagezi(db)
    mark_dirty()
    return {"resultados": resultados}


@router.post("/{acl_id}/sync-now", response_model=AclResponse)
def sincronizar_categoria_ahora(
    acl_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Dispara una sincronización inmediata de una categoría, sin esperar
    al refresco diario automático. Solo tiene sentido si ya tiene una
    `sync_url` configurada (ver PUT /{acl_id} o /hagezi-preset)."""
    acl = db.query(Acl).filter(Acl.id == acl_id).first()
    if not acl:
        raise HTTPException(404, detail="ACL no encontrada")
    if not acl.sync_url:
        raise HTTPException(400, detail="Esta categoría no tiene una URL de sincronización configurada.")

    from app.services.category_sync_service import sync_one

    sync_one(db, acl)
    db.refresh(acl)
    return _to_response(acl)
