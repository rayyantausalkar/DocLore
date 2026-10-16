import React, { useState } from 'react'
import type { ProjectSource } from '../types'

interface AddSourceModalProps {
  isOpen: boolean
  projectId: string
  onClose: () => void
  onSourceAdded: (newSource: ProjectSource) => void
  onNotify: (title: string, description?: string, type?: 'success' | 'info' | 'error') => void
}

export const AddSourceModal: React.FC<AddSourceModalProps> = ({
  isOpen,
  projectId,
  onClose,
  onSourceAdded,
  onNotify,
}) => {
  const [sourceType, setSourceType] = useState('openapi')
  const [name, setName] = useState('')
  const [sourceUri, setSourceUri] = useState('')
  const [branch, setBranch] = useState('')
  const [subpath, setSubpath] = useState('')
  const [sourceFile, setSourceFile] = useState<{ name: string; content: string } | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      setError('Source name is required.')
      return
    }

    let config: Record<string, unknown>
    if (sourceType === 'repository') {
      if (!sourceUri.trim()) {
        setError('GitHub repository URL is required.')
        return
      }
      config = {
        github_url: sourceUri.trim(),
        branch: branch.trim() || undefined,
        subpath: subpath.trim() || undefined,
      }
    } else {
      if (!sourceFile) {
        setError('Choose a specification, diagram, or documentation file to upload.')
        return
      }
      config = { raw_content: sourceFile.content, canonical_path: sourceFile.name }
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const res = await fetch(`/api/v1/projects/${projectId}/sources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_type: sourceType,
          name: name.trim(),
          config,
        }),
      })

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Failed to add source: HTTP ${res.status}`)
      }

      const created: ProjectSource = await res.json()

      // Automatically sync and index the source
      const syncRes = await fetch(`/api/v1/sources/${created.id}/sync`, { method: 'POST' })
      if (!syncRes.ok) {
        const errJson = await syncRes.json().catch(() => ({}))
        throw new Error(errJson.detail || `Source created but sync failed: HTTP ${syncRes.status}`)
      }

      onSourceAdded(created)
      onNotify('Source Connected', `Attached and indexed "${created.name}"`, 'success')
      onClose()

      // Reset
      setName('')
      setSourceUri('')
      setBranch('')
      setSubpath('')
      setSourceFile(null)
      setSourceType('openapi')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error adding knowledge source.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="add-source-title">
      <div className="modal-backdrop" onClick={onClose} aria-hidden="true" />
      <div className="modal-content">
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 id="add-source-title" className="modal-title">
              Attach Knowledge Silo Source
            </h2>
            <p className="modal-subtext">
              Connect OpenAPI specs, architecture diagrams, style guides, or troubleshooting runbooks to ground the hybrid retrieval engine.
            </p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="source-type-select" className="form-label">
              Knowledge Silo Type
            </label>
            <select
              id="source-type-select"
              className="modal-input"
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
            >
              <option value="openapi">OpenAPI Specification (JSON / YAML)</option>
              <option value="architecture_diagram">Architecture Diagram / Topology (Mermaid / Spec)</option>
              <option value="style_guide">Coding Standards & Style Guide (Markdown / Linter Rules)</option>
              <option value="markdown">Troubleshooting Runbook / Markdown Docs</option>
              <option value="issue_logs">Historical Incident & Bug Postmortems</option>
              <option value="repository">Additional Source Repository (Path / Git)</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="source-name-input" className="form-label">
              Source Name / Identifier
            </label>
            <input
              id="source-name-input"
              type="text"
              className="modal-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Orders API Spec or Python Style Rules"
              required
            />
          </div>

          {sourceType === 'repository' ? (
            <>
              <div className="form-group">
                <label htmlFor="source-uri-input" className="form-label">
                  GitHub Repository URL
                </label>
                <input
                  id="source-uri-input"
                  type="text"
                  className="modal-input"
                  value={sourceUri}
                  onChange={(e) => setSourceUri(e.target.value)}
                  placeholder="https://github.com/owner/repository"
                  required
                />
              </div>
              <div className="form-row-2col">
                <div className="form-group">
                  <label htmlFor="source-branch-input" className="form-label">
                    Branch / Tag (Optional)
                  </label>
                  <input
                    id="source-branch-input"
                    type="text"
                    className="modal-input"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    placeholder="main, master, or v1.0.0"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="source-subpath-input" className="form-label">
                    Subpath (Optional)
                  </label>
                  <input
                    id="source-subpath-input"
                    type="text"
                    className="modal-input"
                    value={subpath}
                    onChange={(e) => setSubpath(e.target.value)}
                    placeholder="e.g. backend/ or src/"
                  />
                </div>
              </div>
            </>
          ) : (
            <div className="form-group">
              <label htmlFor="source-file-input" className="form-label">
                File (OpenAPI JSON/YAML, Markdown, Mermaid, or Text)
              </label>
              <input
                id="source-file-input"
                type="file"
                className="modal-input"
                accept=".json,.yaml,.yml,.md,.markdown,.txt,.mmd,.py,.ts,.tsx,.js,.jsx,.go,.rs,.sql,.sh"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (!file) {
                    setSourceFile(null)
                    return
                  }
                  if (file.size > 2 * 1024 * 1024) {
                    setSourceFile(null)
                    setError('File exceeds 2 MB limit.')
                    return
                  }
                  setError(null)
                  void file.text().then((content) => setSourceFile({ name: file.name, content }))
                }}
                required
              />
            </div>
          )}

          {error && (
            <div className="modal-error-banner" role="alert">
              {error}
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </button>
            <button type="submit" className="btn-submit-project" disabled={isSubmitting}>
              {isSubmitting ? 'Indexing & Syncing...' : 'Attach & Index Silo'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
