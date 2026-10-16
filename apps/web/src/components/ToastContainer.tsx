import React from 'react'
import type { ToastMessage } from '../types'

interface ToastContainerProps {
  toasts: ToastMessage[]
  onDismiss: (id: string) => void
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null

  return (
    <div className="toast-viewport" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast-card toast-card--${toast.type || 'info'}`}>
          <div className="toast-body">
            <span className="toast-title">{toast.title}</span>
            {toast.description && <span className="toast-desc">{toast.description}</span>}
          </div>
          <button
            type="button"
            className="toast-close"
            onClick={() => onDismiss(toast.id)}
            aria-label="Dismiss toast"
          >
            &times;
          </button>
        </div>
      ))}
    </div>
  )
}
