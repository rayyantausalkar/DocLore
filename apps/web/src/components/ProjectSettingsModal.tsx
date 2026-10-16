import React, { useState } from 'react'
import type { Project } from '../types'

interface ProjectSettingsModalProps {
  isOpen: boolean
  project: Project
  onClose: () => void
  onUpdate: (updated: Project) => void
  onDeleteRequest: (projectId: string, projectName: string) => void
}

export const ProjectSettingsModal: React.FC<ProjectSettingsModalProps> = ({
  isOpen,
  project,
  onClose,
  onUpdate,
  onDeleteRequest,
}) => {
  const [name, setName] = useState(project.name)
  const [description, setDescription] = useState(project.description || '')
  const [branch, setBranch] = useState(project.branch || '')
  const [subpath, setSubpath] = useState(project.subpath || '')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [prevProjectId, setPrevProjectId] = useState(project.id)
  if (project.id !== prevProjectId) {
    setPrevProjectId(project.id)
    setName(project.name)
    setDescription(project.description || '')
    setBranch(project.branch || '')
    setSubpath(project.subpath || '')
    setError(null)
  }

  if (!isOpen) return null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      setError('Project name is required.')
      return
    }

    setIsSaving(true)
    setError(null)
    try {
      const res = await fetch(`/api/v1/projects/${project.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim(),
          branch: branch.trim() || null,
          subpath: subpath.trim() || null,
        }),
      })

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Failed to update project: HTTP ${res.status}`)
      }

      const updatedProject: Project = await res.json()
      onUpdate(updatedProject)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error updating project.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="settings-modal-title">
      <div className="modal-backdrop" onClick={onClose} aria-hidden="true" />
      <div className="modal-content">
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 id="settings-modal-title" className="modal-title">
              Project Settings
            </h2>
            <p className="modal-subtext">Manage metadata, connected repository details, and project lifecycle.</p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="edit-proj-name" className="form-label">
              Project Name
            </label>
            <input
              id="edit-proj-name"
              type="text"
              className="modal-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="edit-proj-desc" className="form-label">
              Description (Optional)
            </label>
            <textarea
              id="edit-proj-desc"
              className="modal-input modal-textarea-sm"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Core authentication microservice documentation"
              rows={2}
            />
          </div>

          {project.github_url && (
            <div className="form-group">
              <label className="form-label">Connected Repository</label>
              <div className="form-readonly-box">
                <span className="readonly-val">{project.github_url}</span>
                {project.commit_hash && (
                  <span className="readonly-sub">Revision: <code>{project.commit_hash}</code></span>
                )}
              </div>
            </div>
          )}

          <div className="form-row-2col">
            <div className="form-group">
              <label htmlFor="edit-proj-branch" className="form-label">
                Branch
              </label>
              <input
                id="edit-proj-branch"
                type="text"
                className="modal-input"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="main"
              />
            </div>
            <div className="form-group">
              <label htmlFor="edit-proj-subpath" className="form-label">
                Subpath
              </label>
              <input
                id="edit-proj-subpath"
                type="text"
                className="modal-input"
                value={subpath}
                onChange={(e) => setSubpath(e.target.value)}
                placeholder="e.g. src/"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Indexed Documents</label>
            <div className="form-stats-row">
              <span className="stat-pill">{project.document_count} files indexed</span>
              <span className="stat-pill stat-pill--status">Status: {project.repo_status || 'synced'}</span>
            </div>
          </div>

          {error && (
            <div className="modal-error-banner" role="alert">
              {error}
            </div>
          )}

          <div className="modal-danger-zone">
            <div className="danger-zone-content">
              <span className="danger-title">Delete Project</span>
              <span className="danger-desc">
                Permanently remove this project and all associated chat sessions and indexed documents.
              </span>
            </div>
            <button
              type="button"
              className="btn-danger-sm"
              onClick={() => {
                onClose()
                onDeleteRequest(project.id, project.name)
              }}
            >
              Delete Project
            </button>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-cancel" onClick={onClose} disabled={isSaving}>
              Cancel
            </button>
            <button type="submit" className="btn-submit-project" disabled={isSaving}>
              {isSaving ? 'Saving Changes...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
