import { useState, useCallback } from 'react'

interface Toast {
  id: number
  msg: string
  type: 'success' | 'error' | 'warning' | 'info'
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const showToast = useCallback((msg: string, type: 'success' | 'error' | 'warning' | 'info' = 'success') => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  const ToastContainer = () => (
    <div className="fixed top-6 right-6 z-50 space-y-2">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`px-5 py-3 rounded-xl shadow-2xl text-white font-medium animate-slide-in flex items-center gap-2 min-w-[280px] ${
            t.type === 'success' ? 'bg-green-600' :
            t.type === 'error' ? 'bg-red-600' :
            t.type === 'warning' ? 'bg-yellow-600' : 'bg-blue-600'
          }`}
        >
          <span className="text-lg">
            {t.type === 'success' ? '✅' : t.type === 'error' ? '❌' : t.type === 'warning' ? '⚠️' : 'ℹ️'}
          </span>
          {t.msg}
        </div>
      ))}
    </div>
  )

  return { showToast, ToastContainer }
}