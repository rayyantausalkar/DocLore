import React, { useState, useEffect, useCallback } from 'react'
import type { ProjectSource, SourceDocument } from '../types'

interface SourceDetailModalProps {
  isOpen: boolean
  source: ProjectSource | null
  onClose: () => void
  onUpdateSource: (updated: ProjectSource) => void
  onDeleteSource: (sourceId: string) => void
  onNotify: (title: string, description?: string, type?: 'success' | 'info' | 'error') => void
}

export const SourceDetailModal: React.FC<SourceDetailModalProps> = ({
  isOpen,
  source,
  onClose,
  onUpdateSource,
  onDeleteSource,
  onNotify,
}) => {
  const [documents, setDocuments] = useState<SourceDocument[]>([])
  const [isLoadingDocs, setIsLoadingDocs] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [isEditingName, setIsEditingName] = useState(false)
  const [editedName, setEditedName] = useState('')
  const [isSavingName, setIsSavingName] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadDocuments = useCallback(async (sourceId: string) => {
    setIsLoadingDocs(true)
    setError(null)
    try {
      const res = await fetch(`/api/v1/sources/${sourceId}/documents`)
      if (res.ok) {
        const docs: SourceDocument[] = await res.json()
        setDocuments(docs)
      } else {
        throw new Error(`HTTP ${res.status}`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading documents.')
    } finally {
      setIsLoadingDocs(false)
    }
  }, [])

  const [prevSourceId, setPrevSourceId] = useState(source?.id)
  if (source && source.id !== prevSourceId) {
    setPrevSourceId(source.id)
    setEditedName(source.name)
    setIsEditingName(false)
  }

  useEffect(() => {
    if (source && isOpen) {
      let active = true
      void Promise.resolve().then(() => {
        if (active) void loadDocuments(source.id)
      })
      return () => {
        active = false
      }
    }
  }, [source, isOpen, loadDocuments])

  if (!isOpen || !source) return null

  async function handleSync() {
    if (!source) return
    setIsSyncing(true)
    setError(null)
    try {
      const res = await fetch(`/api/v1/sources/${source.id}/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true }),
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Sync failed: HTTP ${res.status}`)
      }
      const syncResult = await res.json()
      onNotify('Source Synced', `${syncResult.document_count} documents, ${syncResult.chunk_count} chunks indexed.`, 'success')
      // Refresh documents
      await loadDocuments(source.id)
      // Refresh source details
      const srcRes = await fetch(`/api/v1/sources/${source.id}`)
      if (srcRes.ok) {
        const updated: ProjectSource = await srcRes.json()
        onUpdateSource(updated)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error syncing source.')
      onNotify('Sync Error', err instanceof Error ? err.message : 'Error syncing source', 'error')
    } finally {
      setIsSyncing(false)
    }
  }

  async function handleSaveName() {
    if (!source || !editedName.trim()) return
    setIsSavingName(true)
    setError(null)
    try {
      const res = await fetch(`/api/v1/sources/${source.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editedName.trim() }),
      })
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Failed to update name: HTTP ${res.status}`)
      }
      const updated: ProjectSource = await res.json()
      onUpdateSource(updated)
      setIsEditingName(false)
      onNotify('Source Renamed', `Updated to "${updated.name}"`, 'success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error saving name.')
    } finally {
      setIsSavingName(false)
    }
  }

  async function handleDelete() {
    if (!source) return
    setIsDeleting(true)
    setError(null)
    try {
      const res = await fetch(`/api/v1/sources/${source.id}`, {
        method: 'DELETE',
      })
      if (!res.ok && res.status !== 204) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Delete failed: HTTP ${res.status}`)
      }
      onDeleteSource(source.id)
      onNotify('Source Removed', `Removed "${source.name}" and purged indexed chunks.`, 'info')
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error deleting source.')
      setIsDeleting(false)
    }
  }

  const totalChunks = documents.reduce((acc, d) => acc + (d.chunks?.length || 0), 0)

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="source-detail-title">
      <div className="modal-backdrop" onClick={onClose} aria-hidden="true" />
      <div className="modal-content modal-content--wide">
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="source-title-row">
              <span className="source-type-pill">{source.source_type}</span>
              {isEditingName ? (
                <div className="inline-edit-group">
                  <input
                    type="text"
                    className="modal-input modal-input--inline"
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    disabled={isSavingName}
                    autoFocus
                  />
                  <button
                    type="button"
                    className="btn-action-primary-sm"
                    onClick={() => void handleSaveName()}
                    disabled={isSavingName || !editedName.trim()}
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    className="btn-cancel-sm"
                    onClick={() => {
                      setEditedName(source.name)
                      setIsEditingName(false)
                    }}
                    disabled={isSavingName}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="source-name-display-wrap">
                  <h2 id="source-detail-title" className="modal-title">
                    {source.name}
                  </h2>
                  <button
                    type="button"
                    className="btn-icon-subtle"
                    onClick={() => setIsEditingName(true)}
                    title="Rename source"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
                    </svg>
                  </button>
                </div>
              )}
            </div>
            <p className="modal-subtext">
              Status: <strong className="status-highlight">{source.status}</strong> &bull; {documents.length} document{documents.length === 1 ? '' : 's'} &bull; {totalChunks} chunks indexed
            </p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <div className="source-actions-bar">
          <button
            type="button"
            className="btn-sync-action"
            onClick={() => void handleSync()}
            disabled={isSyncing}
          >
            <svg
              className={`sync-spin-icon ${isSyncing ? 'spinning' : ''}`}
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
            <span>{isSyncing ? 'Syncing...' : 'Force Re-sync'}</span>
          </button>

          <button
            type="button"
            className="btn-danger-outline-sm"
            onClick={() => void handleDelete()}
            disabled={isDeleting || isSyncing}
          >
            {isDeleting ? 'Deleting...' : 'Delete Source'}
          </button>
        </div>

        {error && (
          <div className="modal-error-banner" role="alert">
            {error}
          </div>
        )}

        <div className="source-docs-section">
          <h3 className="section-subheading">Indexed Documents ({documents.length})</h3>
          {isLoadingDocs ? (
            <div className="loading-hint">Loading indexed documents...</div>
          ) : documents.length === 0 ? (
            <div className="empty-docs-box">
              <span>No documents indexed for this source yet. Click "Force Re-sync" to index.</span>
            </div>
          ) : (
            <div className="source-docs-list">
              {documents.map((doc) => (
                <div key={doc.id} className="source-doc-row">
                  <div className="doc-row-left">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <span className="doc-row-title">{doc.title}</span>
                    <span className="doc-row-path">{doc.canonical_path}</span>
                  </div>
                  <div className="doc-row-right">
                    <span className="doc-chunk-count">{doc.chunks?.length || 0} chunks</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="modal-actions">
          <button type="button" className="btn-cancel" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
