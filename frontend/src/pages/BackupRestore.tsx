import { traducir } from '../i18n'
import { useRef, useState } from 'react'
import { IconDownload, IconUpload, IconSpinner, IconAlert, IconCheck, IconShield, IconFile } from '../components/Icons'
import { api, getToken, notificarCambioPendiente } from '../api/client'
import { useToast } from '../components/Toast'
import Modal from '../components/Modal'
import RequiereAplicar from '../components/RequiereAplicar'
import { confirmar } from '../components/ConfirmDialog'
import { formatBytes } from '../utils/format'

function guardarArchivo(blob: Blob, nombre: string) {
  const u = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = u; a.download = nombre
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(u), 10_000)
}

// ---------------------------------------------------------------------------
// 1. Crear backup
// ---------------------------------------------------------------------------

function CrearBackupModal({ onClose, onHecho }: { onClose: () => void; onHecho: (msg: string) => void }) {
  const [protegido, setProtegido] = useState(true)
  const [clave, setClave] = useState('')
  const [clave2, setClave2] = useState('')
  const [listas, setListas] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const crear = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    if (protegido && clave.length < 8) { setErr(traducir("La contraseña debe tener al menos 8 caracteres.")); return }
    if (protegido && clave !== clave2) { setErr(traducir("Las contraseñas no coinciden.")); return }
    setBusy(true)
    try {
      const r = await fetch(api.exportBackupV2Url(), {
        method: 'POST',
        headers: { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ contrasena: protegido ? clave : null, incluir_listas: listas }),
      })
      if (!r.ok) {
        let m = `HTTP ${r.status}`
        try { const j = await r.json(); if (j.detail) m = j.detail } catch { /* no JSON */ }
        throw new Error(m)
      }
      const blob = await r.blob()
      guardarArchivo(blob, `squidmanager-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '').replace(/-/g, '')}.smbackup`)
      onHecho(traducir("Backup creado ({tam})", { tam: formatBytes(blob.size) }))
      onClose()
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal title={traducir("Crear backup")} onClose={onClose} maxWidth="max-w-lg">
      <form onSubmit={crear}>
        <p className="text-[13px] text-ink-3 mb-4">
          {traducir("El backup contiene toda la configuración para dejar otro SquidManager idéntico a este: ajustes, ACLs, reglas, usuarios, grupos, cuotas, ancho de banda, LDAP, proxy padre, Kerberos, SMTP, notificaciones y más.")}
        </p>
        <label className="flex items-start gap-2.5 text-sm text-ink-2 cursor-pointer mb-2">
          <input type="checkbox" className="mt-1" checked={protegido} onChange={e => setProtegido(e.target.checked)} />
          <span>
            <strong>{traducir("Incluir contraseñas y credenciales (recomendado)")}</strong>
            <span className="block text-[12.5px] text-ink-3">
              {traducir("Las contraseñas de los usuarios, las claves de LDAP, SMTP, Telegram y del asistente, y el keytab de Kerberos viajan cifrados con la contraseña que elijas. Sin ella, los usuarios se restauran sin contraseña.")}
            </span>
          </span>
        </label>
        {protegido && (
          <div className="grid gap-3 sm:grid-cols-2 ml-6 mb-3">
            <div>
              <label className="field-label block mb-1">{traducir("Contraseña del backup")}</label>
              <input type="password" className="input" value={clave} onChange={e => setClave(e.target.value)} autoComplete="new-password" autoFocus />
            </div>
            <div>
              <label className="field-label block mb-1">{traducir("Repetir contraseña")}</label>
              <input type="password" className="input" value={clave2} onChange={e => setClave2(e.target.value)} autoComplete="new-password" />
            </div>
            <p className="sm:col-span-2 text-[12px] text-warn">{traducir("Guárdala: sin ella no se pueden recuperar las credenciales del backup, y no se puede restablecer.")}</p>
          </div>
        )}
        <label className="flex items-start gap-2.5 text-sm text-ink-2 cursor-pointer mb-4">
          <input type="checkbox" className="mt-1" checked={listas} onChange={e => setListas(e.target.checked)} />
          <span>
            <strong>{traducir("Incluir las listas grandes de dominios")}</strong>
            <span className="block text-[12.5px] text-ink-3">{traducir("Las cargadas desde archivo. Pueden pesar decenas de MB. Las categorías en línea (HaGeZi) no hacen falta: se vuelven a descargar solas.")}</span>
          </span>
        </label>
        {err && <div className="mb-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}
        <div className="flex justify-end gap-2.5">
          <button type="button" className="btn btn-outline" onClick={onClose}>{traducir("Cancelar")}</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? <IconSpinner className="animate-spin" /> : <IconDownload />}{busy ? traducir('Creando…') : traducir('Crear y descargar')}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// 2. Restaurar
// ---------------------------------------------------------------------------

function TablaCambios({ entidades }: { entidades: any[] }) {
  if (!entidades.length) return <p className="text-sm text-ink-3">{traducir("No hay cambios: el servidor ya está igual que el backup.")}</p>
  return (
    <table className="table-panel text-[13px]">
      <thead><tr>
        <th className="text-left">{traducir("Qué")}</th>
        <th className="text-right">{traducir("Se crean")}</th>
        <th className="text-right">{traducir("Se actualizan")}</th>
        <th className="text-right">{traducir("Se eliminan")}</th>
      </tr></thead>
      <tbody>
        {entidades.map(e => (
          <tr key={e.clave}>
            <td>{traducir(e.nombre)}</td>
            <td className="text-right tabular">{e.crear || '—'}</td>
            <td className="text-right tabular">{e.actualizar || '—'}</td>
            <td className={`text-right tabular ${e.eliminar ? 'text-danger font-semibold' : ''}`}>{e.eliminar || '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Restaurar({ showToast }: { showToast: (m: string, t?: 'success' | 'error' | 'warning' | 'info') => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [archivo, setArchivo] = useState<File | null>(null)
  const [clave, setClave] = useState('')
  const [modo, setModo] = useState<'combinar' | 'reemplazar'>('reemplazar')
  const [aplicar, setAplicar] = useState(false)
  const [informe, setInforme] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const esLegado = archivo?.name.toLowerCase().endsWith('.json')

  const elegir = (f: File | null) => { setArchivo(f); setInforme(null); setErr('') }

  const revisar = async () => {
    if (!archivo) return
    setBusy(true); setErr('')
    try { setInforme(await api.restoreBackupV2(archivo, clave, modo, true, false)) }
    catch (e: any) { setErr(e.message); setInforme(null) } finally { setBusy(false) }
  }

  const restaurar = async () => {
    if (!archivo) return
    const mensaje = modo === 'reemplazar'
      ? traducir("Esto deja este servidor IGUAL que el backup: lo que no esté en el backup se elimina. ¿Continuar?")
      : traducir("Esto agrega y actualiza lo que trae el backup sin eliminar nada. ¿Continuar?")
    if (!(await confirmar(mensaje, { titulo: traducir("Restaurar backup"), confirmar: traducir("Restaurar"), tono: modo === 'reemplazar' ? 'peligro' : 'normal' }))) return
    setBusy(true); setErr('')
    try {
      const r = await api.restoreBackupV2(archivo, clave, modo, false, aplicar)
      notificarCambioPendiente()
      showToast(traducir("Backup restaurado"), 'success')
      setInforme({ ...r, hecho: true })
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }

  const restaurarLegado = async () => {
    if (!archivo) return
    if (!(await confirmar(traducir("Este backup es del formato antiguo (JSON): no incluye contraseñas de usuarios ni muchos ajustes. ¿Restaurarlo igualmente?"), { confirmar: traducir("Restaurar") }))) return
    setBusy(true); setErr('')
    try {
      const r = await api.restoreBackup(archivo)
      notificarCambioPendiente()
      showToast(traducir("Backup restaurado: {a} ACLs, {r} reglas, {u} usuarios", { a: r.details.acls, r: r.details.rules, u: r.details.users }), 'success')
      setArchivo(null)
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }

  const b = informe?.backup
  return (
    <div className="card p-6 mb-6">
      <h3 className="font-medium text-ink mb-1">{traducir("Restaurar un backup")}</h3>
      <p className="text-sm text-ink-3 mb-4">{traducir("Sube un backup de SquidManager (.smbackup) de este u otro servidor. Primero verás exactamente qué cambiaría; nada se toca hasta que confirmes.")}</p>

      <input ref={inputRef} type="file" accept=".smbackup,.json" className="hidden" onChange={e => { elegir(e.target.files?.[0] ?? null); if (inputRef.current) inputRef.current.value = '' }} />
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <button className="btn btn-outline" onClick={() => inputRef.current?.click()} disabled={busy}>
          <IconUpload />{archivo ? archivo.name : traducir('Elegir backup…')}
        </button>
        {archivo && <span className="text-xs text-ink-3">{formatBytes(archivo.size)}</span>}
      </div>

      {archivo && esLegado && (
        <div>
          <div className="note note-warn mb-3"><p className="note-text">{traducir("Formato antiguo (JSON). Se puede restaurar, pero no incluye contraseñas de usuarios ni la mayoría de ajustes. Crea un backup nuevo (.smbackup) para no perder nada.")}</p></div>
          <button className="btn btn-primary" onClick={restaurarLegado} disabled={busy}>{busy ? <IconSpinner className="animate-spin" /> : null}{traducir("Restaurar")}</button>
        </div>
      )}

      {archivo && !esLegado && !informe?.hecho && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 mb-4">
            <div>
              <label className="field-label block mb-1.5">{traducir("Contraseña del backup (si lo protegiste)")}</label>
              <input type="password" className="input" value={clave} onChange={e => { setClave(e.target.value); setInforme(null) }} autoComplete="off" />
            </div>
            <div>
              <div className="field-label mb-1.5">{traducir("Cómo restaurar")}</div>
              <label className="flex items-start gap-2 text-sm text-ink-2 cursor-pointer mb-1.5">
                <input type="radio" className="mt-1" checked={modo === 'reemplazar'} onChange={() => { setModo('reemplazar'); setInforme(null) }} />
                <span>{traducir("Dejar este servidor idéntico al backup (elimina lo que no esté en él)")}</span>
              </label>
              <label className="flex items-start gap-2 text-sm text-ink-2 cursor-pointer">
                <input type="radio" className="mt-1" checked={modo === 'combinar'} onChange={() => { setModo('combinar'); setInforme(null) }} />
                <span>{traducir("Combinar: agregar y actualizar, sin eliminar nada")}</span>
              </label>
            </div>
          </div>
          {!informe && (
            <button className="btn btn-primary" onClick={revisar} disabled={busy}>
              {busy ? <IconSpinner className="animate-spin" /> : <IconShield />}{traducir("Revisar qué cambiaría")}
            </button>
          )}
        </>
      )}

      {err && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}

      {informe && b && (
        <div className="mt-4 border border-line-soft rounded-xl p-4">
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-[12.5px] text-ink-3 mb-3">
            <span>{traducir("Creado")}: <strong className="text-ink-2">{b.creado ? new Date(b.creado).toLocaleString() : '—'}</strong></span>
            <span>{traducir("Versión")}: <strong className="text-ink-2">{b.app_version}</strong></span>
            <span>{traducir("Credenciales")}: <strong className="text-ink-2">{b.contiene_secretos ? traducir('incluidas (cifradas)') : traducir('no incluidas')}</strong></span>
          </div>
          {b.aviso_contrasena && !informe.hecho && <div className="note note-warn mb-3"><p className="note-text">{traducir(b.aviso_contrasena)}</p></div>}
          <div className="font-medium text-ink mb-2">{informe.hecho ? traducir("Resultado de la restauración") : traducir("Esto es lo que pasaría (todavía no se cambió nada)")}</div>
          <TablaCambios entidades={informe.entidades} />
          {informe.avisos?.length > 0 && (
            <ul className="mt-3 space-y-1 text-[13px] text-warn">
              {informe.avisos.map((a: string, i: number) => <li key={i} className="flex gap-2"><IconAlert className="w-4 h-4 flex-none mt-0.5" />{a}</li>)}
            </ul>
          )}
          {informe.usuarios_sin_contrasena?.length > 0 && (
            <details className="mt-2 text-[12.5px]"><summary className="cursor-pointer text-ink-3">{traducir("Usuarios sin contraseña")} ({informe.usuarios_sin_contrasena.length})</summary>
              <p className="mt-1 font-mono text-ink-3 break-words">{informe.usuarios_sin_contrasena.join(', ')}</p></details>
          )}
          {informe.aplicado && <p className="mt-3 text-sm flex items-center gap-2"><IconCheck className="w-4 h-4 text-ok" />{informe.aplicado.message}</p>}
          {!informe.hecho && (
            <div className="mt-4 flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-ink-2 cursor-pointer">
                <input type="checkbox" checked={aplicar} onChange={e => setAplicar(e.target.checked)} />
                {traducir("Aplicar a Squid al terminar")}
              </label>
              <button className="btn btn-primary" onClick={restaurar} disabled={busy}>{busy ? <IconSpinner className="animate-spin" /> : null}{traducir("Restaurar ahora")}</button>
              <button className="btn btn-outline" onClick={() => setInforme(null)} disabled={busy}>{traducir("Cancelar")}</button>
              <RequiereAplicar />
            </div>
          )}
          {informe.hecho && <div className="mt-3"><button className="btn btn-outline" onClick={() => { setArchivo(null); setInforme(null); setClave('') }}>{traducir("Listo")}</button></div>}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// 3. Migrar desde otro Squid
// ---------------------------------------------------------------------------

function Casillero({ etiqueta, valor, tono = 'ok' }: { etiqueta: string; valor: number; tono?: 'ok' | 'aviso' | 'neutro' }) {
  const clase = tono === 'ok' ? 'bg-ok-soft text-ok' : tono === 'aviso' ? 'bg-warn-soft text-warn' : 'bg-line-soft text-ink-2'
  return (
    <div className={`rounded-lg p-3 text-center ${clase}`}>
      <div className="text-xl font-bold tabular">{valor}</div>
      <div className="text-[11px]">{etiqueta}</div>
    </div>
  )
}

function Migrar({ showToast }: { showToast: (m: string, t?: 'success' | 'error' | 'warning' | 'info') => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [analizando, setAnalizando] = useState(false)
  const [aplicando, setAplicando] = useState(false)
  const [informe, setInforme] = useState<any>(null)
  const [importarUsuarios, setImportarUsuarios] = useState(true)
  const [resultado, setResultado] = useState<any>(null)

  const elegir = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0) return
    setAnalizando(true); setInforme(null); setResultado(null)
    try { setInforme(await api.analyzeSquidConf(files)) }
    catch (err: any) { showToast(err.message, 'error') } finally { setAnalizando(false); if (inputRef.current) inputRef.current.value = '' }
  }

  const aplicar = async () => {
    if (!informe?.token) return
    setAplicando(true)
    try {
      const r = await api.applySquidImport(informe.token, importarUsuarios)
      notificarCambioPendiente()
      setResultado(r.details); setInforme(null)
      showToast(traducir("Importación aplicada"), 'success')
    } catch (err: any) { showToast(err.message, 'error') } finally { setAplicando(false) }
  }

  const r = informe?.resumen
  const nadaImportable = r && r.acls_a_importar === 0 && r.reglas_a_importar === 0 && r.settings_a_importar === 0 &&
    r.delay_pools_a_importar === 0 && !r.parent_proxy && r.usuarios_a_importar === 0 && r.usuarios_sin_credencial === 0

  return (
    <div className="card p-6 mb-6">
      <h3 className="font-medium text-ink mb-1">{traducir("Migrar desde un Squid que no usa SquidManager")}</h3>
      <p className="text-sm text-ink-3 mb-4">
        {traducir("Sube la carpeta de configuración de tu Squid comprimida (.zip o .tar.gz) o sus archivos sueltos: el squid.conf, las listas que referencia (IPs, dominios, regex) y los archivos de usuarios (htpasswd / htdigest). Verás un informe detallado antes de importar nada.")}
      </p>

      {!informe && !resultado && (
        <>
          <input ref={inputRef} type="file" multiple className="hidden" onChange={elegir} />
          <button className="btn btn-primary" onClick={() => inputRef.current?.click()} disabled={analizando}>
            {analizando ? <IconSpinner className="animate-spin" /> : <IconFile />}{analizando ? traducir('Analizando…') : traducir('Elegir archivos y analizar')}
          </button>
          <p className="text-[12px] text-ink-3 mt-3">{traducir("Si tu copia es un .rar o .7z, descomprímela y vuelve a comprimirla como .zip o .tar.gz.")}</p>
        </>
      )}

      {informe && (
        <div>
          <p className="text-xs text-ink-3 mb-3">
            {traducir("Archivo principal")}: <strong>{informe.principal}</strong> · {traducir("{n} archivos leídos", { n: informe.archivos_leidos.length })}
          </p>
          {informe.includes_faltantes?.length > 0 && (
            <div className="bg-danger-soft text-danger text-[13px] p-3 rounded-lg mb-3">
              <strong>{traducir("Archivos incluidos que no se subieron (su contenido no se analizó):")}</strong> {informe.includes_faltantes.join(', ')}
            </div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            <Casillero etiqueta={traducir("ACLs")} valor={r.acls_a_importar + r.acls_alias} />
            <Casillero etiqueta={traducir("Reglas de acceso")} valor={r.reglas_a_importar} />
            <Casillero etiqueta={traducir("Usuarios")} valor={r.usuarios_a_importar + r.usuarios_sin_credencial} />
            <Casillero etiqueta={traducir("No se importan")} valor={r.directivas_no_soportadas + r.acls_ignoradas + r.reglas_ignoradas} tono="aviso" />
            <Casillero etiqueta={traducir("No reconocidas")} valor={r.directivas_desconocidas} tono="neutro" />
          </div>

          {informe.notas?.map((n: string, i: number) => <div key={i} className="note note-info mb-2"><p className="note-text">{n}</p></div>)}

          {informe.usuarios?.length > 0 && (
            <div className="border border-line-soft rounded-lg p-3 mb-3 text-[13px]">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                <strong className="text-ink">{traducir("Usuarios encontrados")}</strong>
                <label className="flex items-center gap-2 text-ink-2 cursor-pointer">
                  <input type="checkbox" checked={importarUsuarios} onChange={e => setImportarUsuarios(e.target.checked)} />{traducir("Importar usuarios")}
                </label>
              </div>
              <ul className="space-y-0.5 text-ink-2">
                <li><IconCheck className="w-3.5 h-3.5 inline text-ok mr-1.5" />{traducir("{n} usuarios conservan su contraseña de siempre", { n: r.usuarios_a_importar })}
                  {informe.esquema_auth && <span className="text-ink-3"> ({traducir("esquema")}: {informe.esquema_auth}{informe.esquema_auth === 'digest' && informe.realm_auth ? `, realm ${informe.realm_auth}` : ''})</span>}</li>
                {r.usuarios_sin_credencial > 0 && <li className="text-warn"><IconAlert className="w-3.5 h-3.5 inline mr-1.5" />{traducir("{n} se importan DESHABILITADOS: no tienen credencial para ese esquema (hay que restablecer su contraseña)", { n: r.usuarios_sin_credencial })}</li>}
                {r.usuarios_ya_existen > 0 && <li>{traducir("{n} ya existen y no se tocan", { n: r.usuarios_ya_existen })}</li>}
              </ul>
              <p className="text-[12px] text-ink-3 mt-1.5">{traducir("Archivos de usuarios")}: {informe.archivos_usuarios.join(', ')}</p>
            </div>
          )}

          {(informe.extra_safe_ports?.length > 0 || informe.extra_ssl_ports?.length > 0) && (
            <div className="border border-line-soft rounded-lg p-3 mb-3 text-[13px] text-ink-2">
              <strong className="text-ink">{traducir("Puertos propios que se conservan")}</strong>
              {informe.extra_safe_ports.length > 0 && <div>{traducir("Puertos de destino permitidos")}: <span className="font-mono">{informe.extra_safe_ports.join(' ')}</span></div>}
              {informe.extra_ssl_ports.length > 0 && <div>{traducir("Puertos HTTPS (CONNECT) permitidos")}: <span className="font-mono">{informe.extra_ssl_ports.join(' ')}</span></div>}
            </div>
          )}

          {informe.parent_proxy && (
            <div className={`text-[13px] p-2.5 rounded-lg mb-3 ${informe.parent_proxy.estado === 'importar' ? 'bg-ok-soft text-ok' : 'bg-warn-soft text-warn'}`}>
              {traducir("Proxy padre detectado")}: {informe.parent_proxy.host}:{informe.parent_proxy.port}
              {informe.parent_proxy.estado === 'importar'
                ? ` — ${traducir('se importará DESACTIVADO: pruébalo antes de activarlo')}${informe.never_direct ? ` · ${traducir('todo el tráfico saldrá por él')}` : ''}${informe.direct_domains?.length ? ` · ${traducir('{n} dominios van directo', { n: informe.direct_domains.length })}` : ''}`
                : ` — ${traducir('no se importa')}: ${informe.parent_proxy.motivo}`}
            </div>
          )}

          {(r.acls_ignoradas > 0 || r.reglas_ignoradas > 0) && (
            <details className="mb-3 text-xs" open>
              <summary className="cursor-pointer text-ink-3 font-medium">{traducir("ACLs y reglas que no se importan")} ({r.acls_ignoradas + r.reglas_ignoradas})</summary>
              <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
                {informe.acls.filter((a: any) => !['importar', 'alias'].includes(a.estado)).map((a: any, i: number) => (
                  <div key={`a${i}`} className="font-mono">{a.name} ({a.type}): <span className="text-ink-3">{a.motivo}</span></div>
                ))}
                {informe.reglas.filter((x: any) => x.estado !== 'importar').map((x: any, i: number) => (
                  <div key={`r${i}`} className="font-mono">{x.action} {x.acl_names}: <span className="text-ink-3">{x.motivo}</span></div>
                ))}
              </div>
            </details>
          )}

          {(informe.no_soportadas.length > 0 || informe.desconocidas.length > 0) && (
            <details className="mb-4 text-xs">
              <summary className="cursor-pointer text-ink-3 font-medium">{traducir("Directivas que no se importan")} ({informe.no_soportadas.length + informe.desconocidas.length})</summary>
              <div className="mt-2 space-y-1 max-h-64 overflow-y-auto">
                {informe.no_soportadas.map((h: any, i: number) => (
                  <div key={`ns${i}`} className="font-mono"><span className="text-warn">{h.directiva}</span>{h.archivo ? ` (${h.archivo}:${h.linea})` : ''}: <span className="text-ink-3">{h.motivo}</span></div>
                ))}
                {informe.desconocidas.map((h: any, i: number) => (
                  <div key={`dc${i}`} className="font-mono"><span className="text-ink-3">{h.directiva}</span> ({h.archivo}:{h.linea}): {h.motivo}</div>
                ))}
              </div>
            </details>
          )}

          {nadaImportable && <p className="text-sm text-ink-3 mb-3">{traducir("No hay nada importable en estos archivos.")}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <button className="btn btn-primary" onClick={aplicar} disabled={aplicando || nadaImportable}>
              {aplicando ? <IconSpinner className="animate-spin" /> : null}{traducir("Confirmar e importar")}
            </button>
            <button className="btn btn-outline" onClick={() => setInforme(null)} disabled={aplicando}>{traducir("Cancelar")}</button>
            <RequiereAplicar />
          </div>
        </div>
      )}

      {resultado && (
        <div>
          <p className="text-sm text-ink flex items-center gap-2 mb-2"><IconCheck className="w-4 h-4 text-ok" />
            {traducir("Importado: {a} ACLs, {r} reglas, {u} usuarios, {s} ajustes", { a: resultado.acls, r: resultado.reglas, u: resultado.usuarios ?? 0, s: resultado.settings })}
          </p>
          <ul className="space-y-1 text-[13px] text-warn mb-3">{resultado.avisos?.map((a: string, i: number) => <li key={i}>• {a}</li>)}</ul>
          <button className="btn btn-outline" onClick={() => setResultado(null)}>{traducir("Listo")}</button>
        </div>
      )}
    </div>
  )
}

export default function BackupRestore() {
  const { showToast, ToastContainer } = useToast()
  const [crear, setCrear] = useState(false)

  return (
    <div className="p-6 md:p-7 max-w-5xl">
      <ToastContainer />
      <h1 className="page-title mb-1">{traducir("Backup, Restore y Migración")}</h1>
      <p className="page-sub mb-6">{traducir("Guarda la configuración, llévala a otro SquidManager idéntica, o trae la de un Squid que administrabas a mano.")}</p>

      <div className="card p-6 mb-6">
        <h3 className="font-medium text-ink mb-1">{traducir("Backup de SquidManager")}</h3>
        <p className="text-sm text-ink-3 mb-4">{traducir("Un archivo (.smbackup) con toda la configuración. Sirve para volver atrás en este servidor o para dejar otro SquidManager exactamente igual.")}</p>
        <button className="btn btn-primary" onClick={() => setCrear(true)}><IconDownload />{traducir("Crear backup")}</button>
      </div>
      {crear && <CrearBackupModal onClose={() => setCrear(false)} onHecho={m => showToast(m, 'success')} />}

      <Restaurar showToast={showToast} />
      <Migrar showToast={showToast} />
    </div>
  )
}
