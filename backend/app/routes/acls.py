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
    ensure_not_referenced, find_references, MAX_DOMINIOS_POR_CARGA,
)

router = APIRouter()

# Umbral que decide 'inline' vs 'file' para una carga masiva: por debajo,
# la lista sigue siendo una ACL normal (se ve y se edita como cualquier
# otra en el panel); por encima, se escribe a un archivo aparte -ver
# squid_service.build_acl_list_files- porque una sola línea de squid.conf
# con miles de dominios es impracticable de editar y más lenta de parsear.
UMBRAL_ACL_ARCHIVO = 200

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
        description=acl.description, enabled=acl.enabled,
        created_at=acl.created_at, updated_at=acl.updated_at,
    )


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
async def list_acls(
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
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
    acls = (
        db.query(Acl).options(defer(Acl.value)).order_by(Acl.name)
        .offset(offset).limit(limit).all()
    )
    return [_to_response(a) for a in acls]


@router.get("/unused", response_model=list[str])
async def list_unused_acls(
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
async def create_acl(
    data: AclCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Crea una nueva ACL."""
    name = validate_name(data.name, "ACL")
    acl_type = validate_acl_type(data.type)
    value = validate_value(data.value)

    existing = db.query(Acl).filter(Acl.name == name).first()
    if existing:
        raise HTTPException(400, detail="Ya existe una ACL con ese nombre")

    acl = Acl(name=name, type=acl_type, value=value,
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
async def update_acl(
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
async def delete_acl(
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
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Crea o actualiza una ACL de dominios a partir de un archivo (uno por
    línea; líneas vacías o que empiezan con '#' se ignoran).

    Por debajo de UMBRAL_ACL_ARCHIVO dominios, la ACL queda 'inline' (se ve
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

    acl = db.query(Acl).filter(Acl.name == name).first()

    if acl and modo == "agregar":
        # El archivo en disco es la fuente de verdad para una ACL 'file'
        # desde la migración 0023; `acl.value` solo puede tener algo todavía
        # si esta ACL viene de antes de esa migración y ningún apply la
        # migró todavía -se cubren los dos casos, prefiriendo el archivo
        # cuando existe.
        if acl.source == "file":
            from app.services.squid_service import ACL_LISTS_DIR

            ruta = ACL_LISTS_DIR / f"{acl.name}.txt"
            if ruta.exists():
                existentes = [d.strip() for d in ruta.read_text(encoding="utf-8", errors="replace").splitlines() if d.strip()]
            elif acl.value:
                existentes = [d.strip() for d in acl.value.splitlines() if d.strip()]
            else:
                existentes = []
        else:
            existentes = acl.value.split()
        combinados = list(dict.fromkeys(existentes + dominios_nuevos))  # dedup, conserva orden
    else:
        combinados = dominios_nuevos

    if len(combinados) > MAX_DOMINIOS_POR_CARGA:
        raise HTTPException(
            400,
            detail=f"La lista combinada tiene {len(combinados)} dominios, por encima del límite de {MAX_DOMINIOS_POR_CARGA}.",
        )

    nuevo_source = "file" if len(combinados) > UMBRAL_ACL_ARCHIVO else "inline"

    old_value = None
    if acl:
        old_count = acl.line_count if acl.source == "file" else len(acl.value.split())
        old_value = f"{acl.name} {acl.type} ({old_count} dominios)"

    if nuevo_source == "file":
        # El archivo se escribe DIRECTO -nunca pasa por `Acl.value`-: es la
        # diferencia central con el esquema anterior (migración 0023). Con
        # una lista de millones de dominios, evitar ese viaje de ida y
        # vuelta por una columna TEXT es lo que hace que la carga y los
        # applies siguientes sigan siendo rápidos.
        from app.services.squid_service import write_acl_list_file, hash_domain_list

        nuevo_value = None
        hash_nuevo = hash_domain_list(combinados)
        if acl and acl.source == "file" and acl.content_hash == hash_nuevo:
            # Exactamente la misma lista que ya había (re-subir la misma
            # blocklist sin cambios, típico de una sincronización
            # automática): no hay nada que reescribir en disco.
            content_hash, line_count = acl.content_hash, acl.line_count
        else:
            content_hash, line_count = write_acl_list_file(name, combinados)
    else:
        # 'inline' sigue exigiendo una sola línea sin saltos (validate_value):
        # el separador ahí es el espacio, igual que cualquier ACL creada a mano.
        nuevo_value = validate_value(" ".join(combinados))
        content_hash, line_count = None, None

    accion = "update" if acl else "create"
    if acl:
        acl.type = acl_type
        acl.value = nuevo_value
        acl.source = nuevo_source
        acl.content_hash = content_hash
        acl.line_count = line_count
        if description is not None:
            acl.description = description
    else:
        acl = Acl(
            name=name, type=acl_type, value=nuevo_value, source=nuevo_source,
            content_hash=content_hash, line_count=line_count,
            description=description or "Cargado desde archivo", enabled=True,
        )
        db.add(acl)

    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action=accion, entity="acl", entity_id=acl.id,
        old_value=old_value,
        new_value=f"{acl.name} {acl.type} ({len(combinados)} dominios, {nuevo_source}, {len(rechazados)} rechazados)",
    ))
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "acl_change",
                           "ACL cargada desde archivo",
                           f"El admin {current_admin.username} cargó {len(combinados)} dominios en la ACL '{name}' ({nuevo_source}).")

    return {
        "acl": _to_response(acl).model_dump(mode="json"),
        "dominios_importados": len(combinados),
        "dominios_nuevos": len(dominios_nuevos),
        "rechazados": rechazados[:20],
        "total_rechazados": len(rechazados),
    }
