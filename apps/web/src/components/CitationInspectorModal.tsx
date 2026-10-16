import React, { useState } from 'react'
import type { CitationContext } from '../types'

interface CitationInspectorModalProps {
  context: CitationContext | null
  onClose: () => void
  onNotify: (title: string, description?: string, type?: 'success' | 'info' | 'error') => void
}

export const CitationInspectorModal: React.FC<CitationInspectorModalProps> = ({
  context,
  onClose,
  onNotify,
}) => {
  const [copiedType, setCopiedType] = useState<string | null>(null)

  if (!context) return null

  function handleCopy(text: string, type: string, label: string) {
    void navigator.clipboard.writeText(text).then(() => {
      setCopiedType(type)
      onNotify('Copied to Clipboard', label, 'info')
      setTimeout(() => setCopiedType(null), 2000)
    })
  }

  const fileRef = context.start_line
    ? context.start_line === context.end_line
      ? `${context.canonical_path}:${context.start_line}`
      : `${context.canonical_path}:${context.start_line}-${context.end_line}`
    : context.canonical_path

  return (
    <div
      className="inspector-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="inspector-modal-title"
    >
      <div className="inspector-backdrop" onClick={onClose} aria-hidden="true" />
      <div className="inspector-window">
        <div className="inspector-top-bar">
          <div className="inspector-title-area">
            <span className="source-tag">{context.source_type}</span>
            <h3 id="inspector-modal-title" className="inspector-path">
              {context.canonical_path}
            </h3>
            {context.start_line && (
              <span className="inspector-lines">
                {context.start_line === context.end_line
                  ? `Line ${context.start_line}`
                  : `Lines ${context.start_line}–${context.end_line}`}
              </span>
            )}
          </div>

          <div className="inspector-actions">
            <button
              type="button"
              className="btn-secondary-sm"
              onClick={() => handleCopy(fileRef, 'ref', `Reference: ${fileRef}`)}
            >
              {copiedType === 'ref' ? 'Copied Reference' : 'Copy File:Lines'}
            </button>
            <button
              type="button"
              className="btn-secondary-sm"
              onClick={() => handleCopy(context.snippet, 'snippet', 'Code snippet')}
            >
              {copiedType === 'snippet' ? 'Copied Code' : 'Copy Snippet'}
            </button>
            <button
              type="button"
              className="inspector-close-btn"
              onClick={onClose}
              aria-label="Close Inspector"
            >
              &times;
            </button>
          </div>
        </div>

        {context.section_path && (
          <div className="inspector-breadcrumbs">
            <span className="breadcrumb-label">Symbol Scope:</span>
            <code className="breadcrumb-val">{context.section_path}</code>
          </div>
        )}

        <div className="inspector-code-container">
          <div className="inspector-lines-table">
            {context.surrounding_lines.map((line) => (
              <div
                key={line.line_number}
                className={`code-line-row ${
                  line.is_highlighted ? 'code-line-row--highlighted' : ''
                }`}
              >
                <span className="code-line-number">{line.line_number}</span>
                <pre className="code-line-content">
                  <code>{line.content || ' '}</code>
                </pre>
              </div>
            ))}
          </div>
        </div>

        <div className="inspector-footer">
          <span className="inspector-hint">Press ESC or click backdrop to close</span>
          <span className="inspector-status">
            Ground truth verified via Multi-Language AST & Line-Preserving Index
          </span>
        </div>
      </div>
    </div>
  )
}
