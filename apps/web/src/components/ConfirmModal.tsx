import React, { useEffect } from 'react'

interface ConfirmModalProps {
  isOpen: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  isDangerous?: boolean
  isLoading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  isDangerous = false,
  isLoading = false,
  onConfirm,
  onCancel,
}) => {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !isLoading) {
        onCancel()
      }
    }
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown)
      return () => window.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, isLoading, onCancel])

  if (!isOpen) return null

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
      <div className="modal-backdrop" onClick={isLoading ? undefined : onCancel} aria-hidden="true" />
      <div className="modal-content modal-content--sm">
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 id="confirm-modal-title" className="modal-title">
              {title}
            </h2>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onCancel}
            disabled={isLoading}
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-confirm-text">{message}</p>
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="btn-cancel"
            onClick={onCancel}
            disabled={isLoading}
          >
            {cancelText}
          </button>
          <button
            type="button"
            className={`btn-action-primary ${isDangerous ? 'btn-danger' : 'btn-submit-project'}`}
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? 'Processing...' : confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
