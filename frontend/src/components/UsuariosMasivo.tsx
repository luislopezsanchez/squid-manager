import { useRef, useState } from 'react'
import { traducir } from '../i18n'
import { api, getToken } from '../api/client'
import Modal from './Modal'
import { IconDownload, IconSpinner, IconUpload, IconCheck, IconAlert } from './Icons'

/** Credenciales generadas (carga masiva o «Generar credenciales» a varios):
 * se muestran UNA sola vez, con copiar y descargar CSV -no se guardan en
 * claro en ningún sitio. */
export function CredencialesModal({ credenciales, titulo, onClose }: {
  credenciales: { usuario: string; password: string }[]
  titulo?: string
  onClose: () => void
}) {
  const [copiado, setCopiado] = useState(false)
  const texto = credenciales.map(c => `${c.usuario}\t${c.password}`).join('\n')

  const copiar = async () => {
    try { await navigator.clipboard.writeText(texto); setCopiado(true); setTimeout(() => setCopiado(false), 2500) } catch { /* sin permiso de portapapeles */ }
  }
  const descargar = () => {
    const csv = '﻿usuario,contraseña\n' + credenciales.map(c => `${c.usuario},${c.password}`).join('\n') + '\n'
    const u = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = u; a.download = `credenciales-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(u), 10_000)
  }

  return (
    <Modal title={titulo ?? traducir('Credenciales generadas')} onClose={onClose} maxWidth="max-w-lg">
      <div className="note-warn rounded-lg p-3 text-[13px] mb-4 flex gap-2.5">
        <IconAlert className="w-4 h-4 flex-none mt-0.5" />
        <span>{traducir("Guarda estas contraseñas ahora: no se vuelven a mostrar. En el sistema solo queda su hash.")}</span>
      </div>
      <div className="border border-line-soft rounded-lg max-h-72 overflow-y-auto">
        <table className="table-panel">
          <thead><tr><th>{traducir("Usuario")}</th><th>{traducir("Contraseña")}</th></tr></thead>
          <tbody>
            {credenciales.map(c => (
              <tr key={c.usuario}><td className="font-medium text-ink">{c.usuario}</td><td className="font-mono text-[13px] select-all">{c.password}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-5 flex justify-end gap-2.5">
        <button className="btn btn-outline" onClick={copiar}>{copiado ? traducir('¡Copiado!') : traducir('Copiar todo')}</button>
        <button className="btn btn-outline" onClick={descargar}><IconDownload />{traducir("Descargar CSV")}</button>
        <button className="btn btn-primary" onClick={onClose}>{traducir("Listo")}</button>
      </div>
    </Modal>
  )
}

interface InformeImport {
  simulacion: boolean
  total_filas: number
  a_crear: number
  a_actualizar: number
  creados: number
  actualizados: number
  omitidos: { fila: number; usuario: string; motivo: string }[]
  errores: { fila: number; usuario: string; motivo: string }[]
  credenciales: { usuario: string; password: string }[]
}

/** Carga masiva: elegir archivo -> «Revisar» (simulación, no toca nada) ->
 * «Importar». Las filas con error se listan y se omiten, el resto entra. */
export function ImportarUsuariosModal({ onClose, onImportado }: {
  onClose: () => void
  onImportado: (informe: InformeImport) => void
}) {
  const [archivo, setArchivo] = useState<File | null>(null)
  const [modo, setModo] = useState<'crear' | 'crear_o_actualizar'>('crear')
  const [informe, setInforme] = useState<InformeImport | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const plantilla = async (formato: 'csv' | 'xlsx') => {
    const r = await fetch(api.importTemplateUrl(formato), { headers: { Authorization: `Bearer ${getToken()}` } })
    const u = URL.createObjectURL(await r.blob())
    const a = document.createElement('a'); a.href = u; a.download = `plantilla-usuarios.${formato}`
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 10_000)
  }

  const ejecutar = async (simular: boolean) => {
    if (!archivo) return
    setBusy(true); setErr('')
    try {
      const r: InformeImport = await api.importUsers(archivo, modo, simular)
      if (simular) setInforme(r)
      else { onImportado(r); onClose() }
    } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }

  const hayAlgo = informe && (informe.a_crear + informe.a_actualizar) > 0

  return (
    <Modal title={traducir('Importar usuarios')} onClose={onClose} maxWidth="max-w-2xl">
      <p className="text-[13px] text-ink-3 mb-4">
        {traducir("Sube un archivo CSV, Excel (.xlsx) o de texto con una fila por usuario. Las columnas reconocidas son: usuario, contraseña, nombre, email, habilitado y caduca. Si no pones contraseña, se genera una segura.")}
      </p>
      <div className="flex flex-wrap items-center gap-2 mb-4 text-[13px]">
        <span className="text-ink-3">{traducir("Plantilla:")}</span>
        <button className="btn btn-outline btn-sm" onClick={() => plantilla('xlsx')}><IconDownload />Excel</button>
        <button className="btn btn-outline btn-sm" onClick={() => plantilla('csv')}><IconDownload />CSV</button>
      </div>

      <div className="grid gap-4">
        <div>
          <label className="field-label block mb-1.5">{traducir("Archivo")}</label>
          <input ref={inputRef} type="file" accept=".csv,.xlsx,.txt" className="hidden"
            onChange={e => { setArchivo(e.target.files?.[0] ?? null); setInforme(null); setErr('') }} />
          <button type="button" className="btn btn-outline w-full justify-center" onClick={() => inputRef.current?.click()}>
            <IconUpload />{archivo ? archivo.name : traducir('Elegir archivo…')}
          </button>
        </div>
        <div>
          <label className="field-label block mb-1.5">{traducir("Si el usuario ya existe")}</label>
          <select className="input" value={modo} onChange={e => { setModo(e.target.value as any); setInforme(null) }}>
            <option value="crear">{traducir("Omitirlo (solo crear los nuevos)")}</option>
            <option value="crear_o_actualizar">{traducir("Actualizar sus datos con los del archivo")}</option>
          </select>
        </div>
      </div>

      {err && <div className="mt-4 bg-danger-soft text-danger text-[13px] p-3 rounded-lg">{err}</div>}

      {informe && (
        <div className="mt-5 border border-line-soft rounded-lg p-4 text-[13.5px]">
          <div className="font-medium text-ink mb-2">{traducir("Resultado de la revisión (todavía no se importó nada)")}</div>
          <ul className="space-y-1 text-ink-2">
            <li><IconCheck className="w-3.5 h-3.5 inline text-ok mr-1.5" />{traducir("{n} usuarios se crearán", { n: informe.a_crear })}</li>
            {informe.a_actualizar > 0 && <li><IconCheck className="w-3.5 h-3.5 inline text-ok mr-1.5" />{traducir("{n} usuarios se actualizarán", { n: informe.a_actualizar })}</li>}
            {informe.omitidos.length > 0 && <li>{traducir("{n} se omitirán porque ya existen", { n: informe.omitidos.length })}</li>}
            {informe.errores.length > 0 && <li className="text-danger">{traducir("{n} filas tienen errores y se omitirán", { n: informe.errores.length })}</li>}
          </ul>
          {informe.errores.length > 0 && (
            <div className="mt-3 max-h-40 overflow-y-auto text-[12.5px] border-t border-line-soft pt-2 space-y-1">
              {informe.errores.map((e, i) => (
                <div key={i}><span className="text-ink-3">{traducir("Fila")} {e.fila}</span>{e.usuario && <span className="font-mono"> {e.usuario}</span>}: <span className="text-danger">{e.motivo}</span></div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mt-6 flex justify-end gap-2.5">
        <button className="btn btn-outline" onClick={onClose}>{traducir("Cancelar")}</button>
        {!informe || !hayAlgo ? (
          <button className="btn btn-primary" disabled={!archivo || busy} onClick={() => ejecutar(true)}>
            {busy ? <IconSpinner className="animate-spin" /> : null}{traducir("Revisar archivo")}
          </button>
        ) : (
          <button className="btn btn-primary" disabled={busy} onClick={() => ejecutar(false)}>
            {busy ? <IconSpinner className="animate-spin" /> : <IconUpload />}{traducir("Importar {n} usuarios", { n: informe.a_crear + informe.a_actualizar })}
          </button>
        )}
      </div>
    </Modal>
  )
}
