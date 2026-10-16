import React, { useRef, useEffect, useState } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { Project, ChatSession } from '../types'

marked.setOptions({
  gfm: true,
  breaks: true,
})

function renderMarkdown(content: string): string {
  try {
    return DOMPurify.sanitize(marked.parse(content) as string)
  } catch {
    return DOMPurify.sanitize(content)
  }
}

interface ChatAreaProps {
  activeProject: Project | null
  activeChat: ChatSession | null
  isSendingMessage: boolean
  chatError: string | null
  onSendMessage: (text: string) => Promise<void>
  onInspectCitation: (chunkId: string) => Promise<void>
  isCollapsed: boolean
  onExpandSidebar: () => void
  onReturnToLanding: () => void
  onOpenCreateProject: () => void
  onOpenProjectSettings: () => void
  onNotify: (title: string, description?: string, type?: 'success' | 'info' | 'error') => void
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  activeProject,
  activeChat,
  isSendingMessage,
  chatError,
  onSendMessage,
  onInspectCitation,
  isCollapsed,
  onExpandSidebar,
  onReturnToLanding,
  onOpenCreateProject,
  onOpenProjectSettings,
  onNotify,
}) => {
  const [chatInput, setChatInput] = useState('')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [expandedTraces, setExpandedTraces] = useState<Record<string, boolean>>({})

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeChat?.messages])

  function handleCopyAnswer(text: string, msgId: string) {
    void navigator.clipboard.writeText(text).then(() => {
      setCopiedId(msgId)
      onNotify('Copied to Clipboard', 'Full assistant response copied.', 'info')
      setTimeout(() => setCopiedId(null), 2000)
    })
  }

  function handleFormSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!isSendingMessage && chatInput.trim() && activeProject) {
      const text = chatInput.trim()
      setChatInput('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
      void onSendMessage(text)
    }
  }

  return (
    <main className="workspace-main">
      {/* Top Header */}
      <header className="workspace-header">
        <div className="header-info">
          {isCollapsed && (
            <button
              type="button"
              className="btn-header-sidebar-expand"
              onClick={onExpandSidebar}
              title="Expand sidebar"
              aria-label="Expand sidebar"
            >
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="2" y="2" width="12" height="12" rx="2" />
                <line x1="6" y1="2" x2="6" y2="14" />
              </svg>
            </button>
          )}

          <div className="header-titles-group">
            <h1 className="active-project-heading">
              {activeProject ? activeProject.name : 'Select or Create a Project'}
            </h1>
            {activeChat && (
              <span className="active-chat-heading">&mdash; {activeChat.title}</span>
            )}
          </div>

          {activeProject && (
            <button
              type="button"
              className="btn-header-settings"
              onClick={onOpenProjectSettings}
              title="Project Settings"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
              <span>Settings</span>
            </button>
          )}
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="btn-action-outline"
            onClick={onReturnToLanding}
            title="View Product Landing Page"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M2.5 6.5L8 2l5.5 4.5v7a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1v-7z" />
              <path d="M6 14.5V9h4v5.5" />
            </svg>
            <span>Landing Page</span>
          </button>
          <button
            type="button"
            className="btn-action-outline"
            onClick={onOpenCreateProject}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 2v8M4 6l4-4 4 4M2 13h12" />
            </svg>
            <span>Import GitHub Repo</span>
          </button>
        </div>
      </header>

      {/* Chat Conversation Canvas */}
      <div className="chat-container">
        {/* Empty State when no messages exist */}
        {(!activeChat || activeChat.messages.length === 0) && (
          <div className="chat-empty-state">
            <div className="empty-state-card">
              <div className="empty-state-icon">
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                </svg>
              </div>
              <h2 className="empty-state-title">
                Developer Documentation Agent
              </h2>
              <p className="empty-state-text">
                Your conversational AI assistant connected to technical knowledge across API specifications,
                GitHub repositories, architecture documents, troubleshooting guides, and internal coding standards.
              </p>

              {/* 6-Step Agent Pipeline Card */}
              <div className="agent-pipeline-card">
                <div className="pipeline-card-header">
                  <span className="pipeline-header-title">Multi-Agent Workflow Architecture</span>
                </div>
                <div className="pipeline-steps-horizontal">
                  <span className="pipeline-step-item">Interpret Intent</span>
                  <span className="pipeline-step-arrow">&rarr;</span>
                  <span className="pipeline-step-item">Hybrid Search</span>
                  <span className="pipeline-step-arrow">&rarr;</span>
                  <span className="pipeline-step-item">Inspect Specs</span>
                  <span className="pipeline-step-arrow">&rarr;</span>
                  <span className="pipeline-step-item">Inspect Code AST</span>
                  <span className="pipeline-step-arrow">&rarr;</span>
                  <span className="pipeline-step-item">Synthesize Answer</span>
                  <span className="pipeline-step-arrow">&rarr;</span>
                  <span className="pipeline-step-item">Verify Citations</span>
                </div>
              </div>

              {/* 5 Scenario Chips */}
              <div className="scenario-prompts-group">
                <span className="scenario-prompts-label">Explore across 5 technical documentation intent modes:</span>
                <div className="scenario-prompts-list">
                  <button
                    type="button"
                    className="scenario-prompt-chip"
                    onClick={() =>
                      void onSendMessage('Give me a high-level project overview, purpose, and codebase structure')
                    }
                  >
                    <span className="chip-intent-tag">Overview</span>
                    "Give me a high-level project overview, purpose, and codebase structure"
                  </button>
                  <button
                    type="button"
                    className="scenario-prompt-chip"
                    onClick={() =>
                      void onSendMessage('What route endpoints, parameters, and schema models are defined in the API specs?')
                    }
                  >
                    <span className="chip-intent-tag">API Details</span>
                    "What route endpoints, parameters, and schema models are defined in the API specs?"
                  </button>
                  <button
                    type="button"
                    className="scenario-prompt-chip"
                    onClick={() =>
                      void onSendMessage('Explain the architectural design, component boundaries, and request flow')
                    }
                  >
                    <span className="chip-intent-tag">Architecture</span>
                    "Explain the architectural design, component boundaries, and request flow"
                  </button>
                  <button
                    type="button"
                    className="scenario-prompt-chip"
                    onClick={() =>
                      void onSendMessage('What coding standards and style guide rules apply to this codebase?')
                    }
                  >
                    <span className="chip-intent-tag">Standards</span>
                    "What coding standards and style guide rules apply to this codebase?"
                  </button>
                  <button
                    type="button"
                    className="scenario-prompt-chip"
                    onClick={() =>
                      void onSendMessage('Trace runtime execution and debug why requests fail with 401 Unauthorized')
                    }
                  >
                    <span className="chip-intent-tag">Execution Trace</span>
                    "Trace runtime execution and debug why requests fail with 401 Unauthorized"
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Messages Flow */}
        {activeChat && activeChat.messages.length > 0 && (
          <div className="messages-scroll-area">
            {activeChat.messages.map((msg) => (
              <div key={msg.id} className={`message-bubble message-bubble--${msg.role}`}>
                {msg.role === 'user' ? (
                  <div className="user-message-content">
                    <span className="user-avatar-tag">USER</span>
                    <p className="user-message-text">{msg.content}</p>
                  </div>
                ) : (
                  <div className="assistant-message-content">
                    {/* Assistant Header */}
                    <div className="assistant-header">
                      <div className="assistant-header-left">
                        <img
                          src="/doclore-logo.png"
                          alt="DocLore"
                          className="assistant-avatar-logo"
                          width="18"
                          height="18"
                        />
                        <span className="assistant-label">DocLore Developer Documentation Agent</span>
                        {msg.intent_label && (
                          <span className="assistant-intent-badge">
                            {msg.intent_label}
                          </span>
                        )}
                      </div>
                      <button
                        type="button"
                        className="btn-secondary-sm"
                        onClick={() => handleCopyAnswer(msg.content, msg.id)}
                      >
                        {copiedId === msg.id ? 'Copied Answer' : 'Copy Answer'}
                      </button>
                    </div>

                    {/* Expandable Multi-Agent Reasoning Workflow */}
                    <div className="agent-reasoning-flow">
                      <button
                        type="button"
                        className="reasoning-toggle-btn"
                        onClick={() =>
                          setExpandedTraces((prev) => ({
                            ...prev,
                            [msg.id]: !prev[msg.id],
                          }))
                        }
                      >
                        <span className="reasoning-toggle-left">
                          <span className="reasoning-bullet">&bull;</span>
                          <span className="reasoning-title">Multi-Agent Documentation & Diagnostic Workflow</span>
                        </span>
                        <span className="reasoning-toggle-state">
                          {expandedTraces[msg.id] ? 'Hide Details' : 'View Multi-Agent Reasoning'}
                        </span>
                      </button>

                      {expandedTraces[msg.id] && (
                        <div className="reasoning-diagram-box">
                          <div className="reasoning-steps-sequence">
                            <div className="reasoning-step-item">
                              <span className="step-badge">1</span>
                              <span className="step-name">Intent Agent: Classify mode & routing</span>
                            </div>
                            <span className="step-seq-arrow">&darr;</span>

                            <div className="reasoning-step-item">
                              <span className="step-badge">2</span>
                              <span className="step-name">Retrieval Agent: Multi-source hybrid RRF</span>
                            </div>
                            <span className="step-seq-arrow">&darr;</span>

                            <div className="reasoning-step-item">
                              <span className="step-badge">3</span>
                              <span className="step-name">Spec Agent: Cross-reference contracts & specs</span>
                            </div>
                            <span className="step-seq-arrow">&darr;</span>

                            <div className="reasoning-step-item">
                              <span className="step-badge">4</span>
                              <span className="step-name">Code Agent: Inspect repository AST syntax</span>
                            </div>
                            <span className="step-seq-arrow">&darr;</span>

                            <div className="reasoning-step-item">
                              <span className="step-badge">5</span>
                              <span className="step-name">Correlation Agent: Correlate specs & code</span>
                            </div>
                            <span className="step-seq-arrow">&darr;</span>

                            <div className="reasoning-step-item">
                              <span className="step-badge">6</span>
                              <span className="step-name">Synthesis Agent: Flexible answer & code</span>
                            </div>
                            <span className="step-seq-arrow">&darr;</span>

                            <div className="reasoning-step-item">
                              <span className="step-badge">7</span>
                              <span className="step-name">Verifier Agent: Validate exact line citations</span>
                            </div>
                          </div>

                          {msg.workflow_trace && msg.workflow_trace.length > 0 && (
                            <div className="reasoning-raw-trace">
                              <span className="raw-trace-title">Execution Trace Logs:</span>
                              <ol className="trace-steps-ordered">
                                {msg.workflow_trace.map((step, idx) => (
                                  <li key={idx} className="trace-step-row">
                                    <span className="step-num">{idx + 1}</span>
                                    <span className="step-text">{step}</span>
                                  </li>
                                ))}
                              </ol>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Conversational Markdown Response Body */}
                    <div
                      className="agent-markdown-body"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                    />

                    {/* Verified Source Citations - Only shown when citations exist */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="agent-citations-section">
                        <span className="card-kicker">
                          Verified Source Line Citations ({msg.citations.length})
                        </span>
                        <div className="citations-stack">
                          {msg.citations.map((cite) => (
                            <div key={cite.chunk_id} className="citation-chip-card">
                              <div className="citation-chip-header">
                                <div className="citation-path-wrap">
                                  <span className="citation-badge-type">{cite.source_type}</span>
                                  <span className="citation-path">{cite.canonical_path}</span>
                                  {cite.start_line && (
                                    <span className="citation-lines">
                                      {cite.start_line === cite.end_line
                                        ? `L${cite.start_line}`
                                        : `L${cite.start_line}–${cite.end_line}`}
                                    </span>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  className="btn-inspect-citation"
                                  onClick={() => void onInspectCitation(cite.chunk_id)}
                                >
                                  Inspect Line Context &rarr;
                                </button>
                              </div>
                              <pre className="citation-snippet-preview">
                                <code>{cite.snippet}</code>
                              </pre>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {isSendingMessage && (
              <div className="message-bubble message-bubble--assistant message-bubble--generating">
                <div className="assistant-message-content">
                  <div className="assistant-header">
                    <div className="assistant-header-left">
                      <img
                        src="/doclore-logo.png"
                        alt="DocLore"
                        className="assistant-avatar-logo"
                        width="18"
                        height="18"
                      />
                      <span className="assistant-label">DocLore Reasoning Engine</span>
                    </div>
                  </div>
                  <div className="generating-indicator">
                    <span className="generating-pulse-dot" />
                    <span className="generating-text">
                      Analyzing query &bull; Multi-source hybrid search &bull; Inspecting syntax trees &bull; Grounding resolution...
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Floating Input Dock */}
        <div className="chat-input-dock">
          {chatError && (
            <div className="chat-error-toast" role="alert">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{chatError}</span>
            </div>
          )}

          <div className="chat-floating-card">
            <form className="chat-floating-form" onSubmit={handleFormSubmit}>
              <textarea
                ref={textareaRef}
                className="chat-textarea"
                value={chatInput}
                onChange={(e) => {
                  setChatInput(e.target.value)
                  e.target.style.height = 'auto'
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    if (!isSendingMessage && chatInput.trim() && activeProject) {
                      handleFormSubmit(e)
                    }
                  }
                }}
                placeholder={
                  activeProject
                    ? "Ask any question in simple English (e.g. 'Why does auth fail?' or 'Show me the endpoint parameters')..."
                    : "Select or ingest a project to begin chatting..."
                }
                disabled={isSendingMessage || !activeProject}
                rows={1}
              />

              <div className="chat-input-bottom-bar">
                <div className="input-pills-row">
                  <span className="input-dock-hint">
                    <kbd>Enter</kbd> to send &bull; <kbd>Shift+Enter</kbd> for newline
                  </span>
                </div>

                <div className="input-actions-row">
                  {chatInput.trim().length > 0 && (
                    <button
                      type="button"
                      className="btn-input-clear"
                      onClick={() => {
                        setChatInput('')
                        if (textareaRef.current) {
                          textareaRef.current.style.height = 'auto'
                        }
                      }}
                      title="Clear input"
                      aria-label="Clear input"
                    >
                      Clear
                    </button>
                  )}

                  <button
                    type="submit"
                    className="btn-send-dock"
                    disabled={isSendingMessage || !chatInput.trim() || !activeProject}
                    title={isSendingMessage ? 'Processing request...' : 'Send message (Enter)'}
                    aria-label="Send message"
                  >
                    {isSendingMessage ? (
                      <div className="send-spinner" aria-hidden="true" />
                    ) : (
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <line x1="12" y1="19" x2="12" y2="5" />
                        <polyline points="5 12 12 5 19 12" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            </form>
          </div>

          <div className="input-disclaimer-text">
            DocLore verifies all technical claims against AST syntax trees, OpenAPI specifications, and line-level citations.
          </div>
        </div>
      </div>
    </main>
  )
}
