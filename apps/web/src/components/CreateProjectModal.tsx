import React, { useState } from 'react'
import type { Project } from '../types'

interface CreateProjectModalProps {
  isOpen: boolean
  onClose: () => void
  onProjectCreated: (project: Project) => void
  onNotify: (title: string, description?: string, type?: 'success' | 'info' | 'error') => void
}

export const CreateProjectModal: React.FC<CreateProjectModalProps> = ({
  isOpen,
  onClose,
  onProjectCreated,
  onNotify,
}) => {
  const [name, setName] = useState('')
  const [githubUrl, setGithubUrl] = useState('')
  const [branch, setBranch] = useState('')
  const [subpath, setSubpath] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      setError('Project name is required.')
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const res = await fetch('/api/v1/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          github_url: githubUrl.trim() || undefined,
          branch: branch.trim() || undefined,
          subpath: subpath.trim() || undefined,
        }),
      })

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Failed to create project: HTTP ${res.status}`)
      }

      const created: Project = await res.json()
      onProjectCreated(created)
      onNotify('Project Created', `Created "${created.name}" and initialized workspace.`, 'success')
      onClose()

      // Reset
      setName('')
      setGithubUrl('')
      setBranch('')
      setSubpath('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creating project.')
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleSelectSample(sampleName: string, url: string, b: string, sp: string) {
    setName(sampleName)
    setGithubUrl(url)
    setBranch(b)
    setSubpath(sp)
    setError(null)
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="create-project-title">
      <div className="modal-backdrop" onClick={onClose} aria-hidden="true" />
      <div className="modal-content">
        <div className="modal-header">
          <div className="modal-title-group">
            <h2 id="create-project-title" className="modal-title">
              Create Project & Ingest Repository
            </h2>
            <p className="modal-subtext">
              DocLore will clone the repository, analyze functions and routes via Python AST, and index all line-level evidence.
            </p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="create-proj-name" className="form-label">
              Project Name
            </label>
            <input
              id="create-proj-name"
              type="text"
              className="modal-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Orders Service"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="create-proj-url" className="form-label">
              GitHub Repository Link (Optional)
            </label>
            <input
              id="create-proj-url"
              type="text"
              className="modal-input"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              placeholder="https://github.com/owner/repository"
            />
          </div>

          <div className="form-row-2col">
            <div className="form-group">
              <label htmlFor="create-proj-branch" className="form-label">
                Branch (Optional)
              </label>
              <input
                id="create-proj-branch"
                type="text"
                className="modal-input"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="main or master"
              />
            </div>
            <div className="form-group">
              <label htmlFor="create-proj-subpath" className="form-label">
                Subpath (Optional)
              </label>
              <input
                id="create-proj-subpath"
                type="text"
                className="modal-input"
                value={subpath}
                onChange={(e) => setSubpath(e.target.value)}
                placeholder="e.g. src/"
              />
            </div>
          </div>

          <div className="modal-sample-links">
            <span className="sample-label">Or test with real public repo:</span>
            <div className="sample-chips">
              <button
                type="button"
                className="sample-chip-btn"
                onClick={() =>
                  handleSelectSample(
                    'FastAPI',
                    'https://github.com/fastapi/fastapi',
                    'master',
                    'fastapi'
                  )
                }
              >
                fastapi/fastapi
              </button>
              <button
                type="button"
                className="sample-chip-btn"
                onClick={() =>
                  handleSelectSample(
                    'Flask',
                    'https://github.com/pallets/flask',
                    'main',
                    'src/flask'
                  )
                }
              >
                pallets/flask
              </button>
              <button
                type="button"
                className="sample-chip-btn"
                onClick={() =>
                  handleSelectSample(
                    'Express',
                    'https://github.com/expressjs/express',
                    'master',
                    'lib'
                  )
                }
              >
                expressjs/express
              </button>
            </div>
          </div>

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
              {isSubmitting ? 'Cloning & Indexing AST...' : 'Create & Ingest Repository'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
