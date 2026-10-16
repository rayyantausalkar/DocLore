import React, { useState } from 'react'
import type { Project, ProjectSource, ChatSession, ApiStatus } from '../types'

interface SidebarProps {
  projects: Project[]
  activeProjectId: string | null
  isLoadingProjects: boolean
  onSelectProject: (projectId: string) => void
  onOpenCreateProject: () => void
  onOpenProjectSettings: () => void

  projectSources: ProjectSource[]
  onOpenAddSource: () => void
  onSelectSource: (source: ProjectSource) => void

  chats: ChatSession[]
  activeChatId: string | null
  isLoadingChats: boolean
  onSelectChat: (chatId: string) => void
  onCreateChat: () => void
  onRenameChat: (chatId: string, newTitle: string) => void
  onDeleteChat: (chatId: string, chatTitle: string) => void

  isCollapsed: boolean
  onToggleCollapse: () => void
  onReturnToLanding: () => void
  apiStatus: ApiStatus
}

export const Sidebar: React.FC<SidebarProps> = ({
  projects,
  activeProjectId,
  isLoadingProjects,
  onSelectProject,
  onOpenCreateProject,
  onOpenProjectSettings,
  projectSources,
  onOpenAddSource,
  onSelectSource,
  chats,
  activeChatId,
  isLoadingChats,
  onSelectChat,
  onCreateChat,
  onRenameChat,
  onDeleteChat,
  isCollapsed,
  onToggleCollapse,
  onReturnToLanding,
  apiStatus,
}) => {
  const [editingChatId, setEditingChatId] = useState<string | null>(null)
  const [chatTitleDraft, setChatTitleDraft] = useState('')

  const activeProject = projects.find((p) => p.id === activeProjectId) || null

  const statusLabel = {
    checking: 'Checking API',
    connected: 'API Connected',
    error: 'API Unavailable',
  }[apiStatus.kind]

  function startRenaming(chat: ChatSession, e: React.MouseEvent) {
    e.stopPropagation()
    setEditingChatId(chat.id)
    setChatTitleDraft(chat.title)
  }

  function commitRename(chatId: string) {
    if (chatTitleDraft.trim()) {
      onRenameChat(chatId, chatTitleDraft.trim())
    }
    setEditingChatId(null)
  }

  return (
    <aside className={`workspace-sidebar ${isCollapsed ? 'workspace-sidebar--collapsed' : ''}`}>
      {/* Brand Header */}
      <div className="sidebar-brand">
        <div
          className="sidebar-brand-clickable"
          onClick={onReturnToLanding}
          title="Return to Landing Page"
        >
          <img
            src="/doclore-logo.png"
            alt="DocLore Logo"
            className="sidebar-logo"
            width="28"
            height="28"
          />
          {!isCollapsed && <span className="sidebar-title">DocLore</span>}
        </div>
        <button
          type="button"
          className="btn-sidebar-toggle"
          onClick={onToggleCollapse}
          title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          aria-label={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="2" y="2" width="12" height="12" rx="2" />
            <line x1="6" y1="2" x2="6" y2="14" />
          </svg>
        </button>
      </div>

      {!isCollapsed && (
        <>
          {/* Project Selector & Management */}
          <div className="sidebar-section">
            <div className="section-label-row">
              <span className="section-label">PROJECT</span>
              <div className="section-label-actions">
                {activeProject && (
                  <button
                    type="button"
                    className="btn-icon-subtle"
                    onClick={onOpenProjectSettings}
                    title="Project Settings"
                    aria-label="Project Settings"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="3" />
                      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                    </svg>
                  </button>
                )}
                <button
                  type="button"
                  className="btn-create-proj"
                  onClick={onOpenCreateProject}
                  title="Add New Project"
                >
                  + New
                </button>
              </div>
            </div>

            <select
              className="project-select"
              value={activeProjectId || ''}
              onChange={(e) => onSelectProject(e.target.value)}
              disabled={isLoadingProjects}
            >
              {isLoadingProjects ? (
                <option value="">Loading projects...</option>
              ) : projects.length === 0 ? (
                <option value="">No projects yet</option>
              ) : (
                projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Active Project Repository Badge */}
          {activeProject && (
            <div className="project-repo-card">
              <div className="repo-card-top">
                <svg className="repo-icon" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="5" cy="4" r="2" />
                  <circle cx="5" cy="12" r="2" />
                  <circle cx="12" cy="7" r="2" />
                  <path d="M5 6v4M5 7c0-1.5 2-3 7-3" />
                </svg>
                <span className="repo-name" title={activeProject.github_url || 'Local Knowledge Base'}>
                  {activeProject.github_url
                    ? activeProject.github_url.replace(/^https?:\/\/github\.com\//, '').replace(/\.git$/, '')
                    : 'Local Knowledge Base'}
                </span>
              </div>
              <div className="repo-meta-row">
                <span
                  className={`repo-status-pill ${
                    !activeProject.github_url || activeProject.repo_status === 'synced'
                      ? 'repo-status-pill--synced'
                      : activeProject.repo_status === 'failed'
                      ? 'repo-status-pill--failed'
                      : ''
                  }`}
                >
                  {activeProject.github_url
                    ? activeProject.repo_status === 'synced'
                      ? 'Synced'
                      : activeProject.repo_status === 'failed'
                      ? 'Failed'
                      : 'Syncing'
                    : 'Active'}
                </span>
                <span className="repo-files-count">
                  {activeProject.document_count} files indexed
                </span>
              </div>
              {activeProject.commit_hash && (
                <div className="repo-commit">
                  Commit: <code>{activeProject.commit_hash}</code>
                </div>
              )}
            </div>
          )}

          {/* Knowledge Silos Section */}
          {activeProject && (
            <div className="sidebar-section sidebar-section--sources">
              <div className="section-label-row">
                <span className="section-label">KNOWLEDGE SILOS</span>
                <button
                  type="button"
                  className="btn-create-proj"
                  onClick={onOpenAddSource}
                  title="Attach Knowledge Source"
                >
                  + Add
                </button>
              </div>

              <div className="sources-list-compact">
                {projectSources.length === 0 ? (
                  <div className="empty-sources-hint">No extra silos attached yet.</div>
                ) : (
                  projectSources.map((src) => (
                    <button
                      key={src.id}
                      type="button"
                      className="source-row-item-btn"
                      onClick={() => onSelectSource(src)}
                      title={`Inspect source: ${src.name}`}
                    >
                      <span className="source-type-pill">{src.source_type}</span>
                      <span className="source-item-name">{src.name}</span>
                      <span className={`source-status-dot status-dot--${src.status}`} />
                    </button>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Chats in this Project */}
          <div className="sidebar-section sidebar-section--chats">
            <div className="section-label-row">
              <span className="section-label">CHATS</span>
              <button
                type="button"
                className="btn-new-chat"
                onClick={onCreateChat}
                title="Start New Chat"
                disabled={!activeProjectId}
              >
                + Chat
              </button>
            </div>

            <div className="chat-sessions-list">
              {isLoadingChats ? (
                <div className="empty-chats-hint">Loading chats...</div>
              ) : chats.length === 0 ? (
                <div className="empty-chats-hint">No chats yet.</div>
              ) : (
                chats.map((session) => (
                  <div
                    key={session.id}
                    className={`chat-session-row ${
                      session.id === activeChatId ? 'chat-session-row--active' : ''
                    }`}
                    onClick={() => onSelectChat(session.id)}
                  >
                    <svg className="chat-btn-icon" width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M2.5 4a1.5 1.5 0 0 1 1.5-1.5h8A1.5 1.5 0 0 1 13.5 4v6a1.5 1.5 0 0 1-1.5 1.5H6l-3.5 2.5V4z" />
                    </svg>

                    {editingChatId === session.id ? (
                      <input
                        type="text"
                        className="chat-rename-input"
                        value={chatTitleDraft}
                        onChange={(e) => setChatTitleDraft(e.target.value)}
                        onBlur={() => commitRename(session.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') commitRename(session.id)
                          if (e.key === 'Escape') setEditingChatId(null)
                        }}
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span className="chat-btn-title" title={session.title}>
                        {session.title}
                      </span>
                    )}

                    <div className="chat-row-actions">
                      <button
                        type="button"
                        className="btn-chat-action"
                        onClick={(e) => startRenaming(session, e)}
                        title="Rename chat"
                        aria-label="Rename chat"
                      >
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
                        </svg>
                      </button>
                      <button
                        type="button"
                        className="btn-chat-action btn-chat-action--delete"
                        onClick={(e) => {
                          e.stopPropagation()
                          onDeleteChat(session.id, session.title)
                        }}
                        title="Delete chat"
                        aria-label="Delete chat"
                      >
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Status Pill in Footer */}
          <div className="sidebar-footer">
            <div className={`status-indicator-pill status-indicator-pill--${apiStatus.kind}`}>
              <span className="status-dot" />
              <span>{statusLabel}</span>
            </div>
          </div>
        </>
      )}

      {isCollapsed && (
        <div className="sidebar-collapsed-actions">
          <button
            type="button"
            className="btn-sidebar-rail-icon"
            onClick={onCreateChat}
            title="New Chat Session"
            aria-label="New Chat Session"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
          <button
            type="button"
            className="btn-sidebar-rail-icon"
            onClick={onOpenCreateProject}
            title="Import Repository"
            aria-label="Import Repository"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              <line x1="12" y1="11" x2="12" y2="17" />
              <line x1="9" y1="14" x2="15" y2="14" />
            </svg>
          </button>
          {activeProject && (
            <button
              type="button"
              className="btn-sidebar-rail-icon"
              onClick={onOpenProjectSettings}
              title="Project Settings"
              aria-label="Project Settings"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
          )}
          <div style={{ marginTop: 'auto', paddingBottom: '4px' }}>
            <span
              className={`status-dot status-dot--${apiStatus.kind}`}
              title={statusLabel}
              style={{ display: 'block', width: '8px', height: '8px', borderRadius: '50%' }}
            />
          </div>
        </div>
      )}
    </aside>
  )
}
