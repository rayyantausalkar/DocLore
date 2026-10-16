import { useEffect, useState, useCallback } from 'react'
import { LandingPage } from './LandingPage'
import { Sidebar } from './components/Sidebar'
import { ChatArea } from './components/ChatArea'
import { CreateProjectModal } from './components/CreateProjectModal'
import { ProjectSettingsModal } from './components/ProjectSettingsModal'
import { AddSourceModal } from './components/AddSourceModal'
import { SourceDetailModal } from './components/SourceDetailModal'
import { CitationInspectorModal } from './components/CitationInspectorModal'
import { ConfirmModal } from './components/ConfirmModal'
import { ToastContainer } from './components/ToastContainer'
import type {
  ApiStatus,
  Project,
  ProjectSource,
  ChatSession,
  CitationContext,
  ToastMessage,
} from './types'
import './App.css'

export function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>({ kind: 'checking' })
  const [viewMode, setViewMode] = useState<'landing' | 'workspace'>('landing')

  // Projects state
  const [projects, setProjects] = useState<Project[]>([])
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [isLoadingProjects, setIsLoadingProjects] = useState(false)

  // Knowledge Sources state
  const [projectSources, setProjectSources] = useState<ProjectSource[]>([])

  // Chats state
  const [chats, setChats] = useState<ChatSession[]>([])
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [isLoadingChats, setIsLoadingChats] = useState(false)

  // Message sending state
  const [isSendingMessage, setIsSendingMessage] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)

  // Sidebar collapse
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)

  // Modals state
  const [isCreateProjectModalOpen, setIsCreateProjectModalOpen] = useState(false)
  const [isProjectSettingsOpen, setIsProjectSettingsOpen] = useState(false)
  const [isAddSourceModalOpen, setIsAddSourceModalOpen] = useState(false)
  const [inspectingSource, setInspectingSource] = useState<ProjectSource | null>(null)
  const [activeCitationContext, setActiveCitationContext] = useState<CitationContext | null>(null)

  // Generic Confirm Modal state
  const [confirmModalState, setConfirmModalState] = useState<{
    isOpen: boolean
    title: string
    message: string
    confirmText?: string
    isDangerous?: boolean
    isLoading?: boolean
    action: () => Promise<void>
  }>({
    isOpen: false,
    title: '',
    message: '',
    action: async () => {},
  })

  // Toasts state
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const addToast = useCallback(
    (title: string, description?: string, type: 'success' | 'info' | 'error' = 'info') => {
      const id = 'toast-' + Math.random().toString(36).substring(2, 9)
      setToasts((prev) => [...prev, { id, title, description, type }])
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, 3500)
    },
    []
  )

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  // Active items helpers
  const activeProject = projects.find((p) => p.id === activeProjectId) || null
  const activeChat = chats.find((c) => c.id === activeChatId) || null

  // Check API health and load projects on startup
  useEffect(() => {
    let isActive = true
    async function init() {
      try {
        const healthRes = await fetch('/api/v1/health')
        if (!healthRes.ok) throw new Error('API returned unhealthy status.')
        if (isActive) setApiStatus({ kind: 'connected' })

        setIsLoadingProjects(true)
        const projRes = await fetch('/api/v1/projects')
        if (projRes.ok && isActive) {
          const list: Project[] = await projRes.json()
          setProjects(list)
          if (list.length > 0) {
            setActiveProjectId(list[0].id)
          }
        }
      } catch (err) {
        if (isActive) {
          setApiStatus({
            kind: 'error',
            message: err instanceof Error ? err.message : 'API unavailable.',
          })
        }
      } finally {
        if (isActive) setIsLoadingProjects(false)
      }
    }

    void init()
    return () => {
      isActive = false
    }
  }, [])

  // Create chat session
  const createChatSession = useCallback(
    async (title = 'New Chat') => {
      if (!activeProjectId) return
      try {
        const res = await fetch(`/api/v1/projects/${activeProjectId}/chats`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title }),
        })
        if (res.ok) {
          const newSession: ChatSession = await res.json()
          setChats((prev) => [newSession, ...prev])
          setActiveChatId(newSession.id)
          addToast('New Chat Created', `Started "${newSession.title}"`, 'info')
        }
      } catch {
        addToast('Error', 'Unable to create chat session.', 'error')
      }
    },
    [activeProjectId, addToast]
  )

  // Load chats and sources when active project changes
  useEffect(() => {
    if (!activeProjectId) return

    let isActive = true
    async function loadData() {
      setIsLoadingChats(true)
      try {
        const [chatRes, srcRes] = await Promise.all([
          fetch(`/api/v1/projects/${activeProjectId}/chats`),
          fetch(`/api/v1/projects/${activeProjectId}/sources`),
        ])

        if (srcRes.ok && isActive) {
          const sourcesList: ProjectSource[] = await srcRes.json()
          setProjectSources(sourcesList)
        }

        if (chatRes.ok && isActive) {
          const list: ChatSession[] = await chatRes.json()
          setChats(list)
          if (list.length > 0) {
            setActiveChatId(list[0].id)
          } else {
            // Auto-create a welcome chat session if none exist
            const createRes = await fetch(`/api/v1/projects/${activeProjectId}/chats`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ title: 'Welcome Chat' }),
            })
            if (createRes.ok && isActive) {
              const newSession: ChatSession = await createRes.json()
              setChats([newSession])
              setActiveChatId(newSession.id)
            }
          }
        }
      } catch {
        // quiet error
      } finally {
        if (isActive) setIsLoadingChats(false)
      }
    }

    void loadData()
    return () => {
      isActive = false
    }
  }, [activeProjectId])

  // Refresh active project document count helper
  const refreshProject = useCallback(async (projectId: string) => {
    try {
      const res = await fetch(`/api/v1/projects/${projectId}`)
      if (res.ok) {
        const updated: Project = await res.json()
        setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
      }
    } catch {
      // quiet
    }
  }, [])

  // Send message
  async function handleSendMessage(queryText: string) {
    const trimmed = queryText.trim()
    if (!trimmed) return

    if (!activeProjectId) {
      addToast('No Project Selected', 'Please create or select a project to begin chatting.', 'error')
      setIsCreateProjectModalOpen(true)
      return
    }

    let targetChatId = activeChatId

    // If no active chat exists (e.g. user deleted all chats), auto-create one seamlessly
    if (!targetChatId) {
      try {
        const titleDraft = trimmed.slice(0, 32) + (trimmed.length > 32 ? '...' : '')
        const createRes = await fetch(`/api/v1/projects/${activeProjectId}/chats`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: titleDraft || 'New Chat' }),
        })
        if (createRes.ok) {
          const newSession: ChatSession = await createRes.json()
          setChats((prev) => [newSession, ...prev])
          setActiveChatId(newSession.id)
          targetChatId = newSession.id
        } else {
          throw new Error('Could not initialize chat session.')
        }
      } catch (err) {
        addToast('Chat Error', err instanceof Error ? err.message : 'Could not create chat session.', 'error')
        return
      }
    }

    setIsSendingMessage(true)
    setChatError(null)

    try {
      const res = await fetch(
        `/api/v1/projects/${activeProjectId}/chats/${targetChatId}/messages`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: trimmed }),
        }
      )

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}))
        throw new Error(errJson.detail || `Failed to send message: HTTP ${res.status}`)
      }

      const updatedSession: ChatSession = await res.json()
      setChats((prev) =>
        prev.map((c) => (c.id === updatedSession.id ? updatedSession : c))
      )
    } catch (err) {
      setChatError(err instanceof Error ? err.message : 'Error sending message.')
      addToast('Message Error', err instanceof Error ? err.message : 'Error', 'error')
    } finally {
      setIsSendingMessage(false)
    }
  }

  // Rename chat
  async function handleRenameChat(chatId: string, newTitle: string) {
    if (!activeProjectId) return
    try {
      const res = await fetch(`/api/v1/projects/${activeProjectId}/chats/${chatId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle }),
      })
      if (res.ok) {
        const updated: ChatSession = await res.json()
        setChats((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
        addToast('Chat Renamed', `Title updated to "${updated.title}"`, 'success')
      }
    } catch {
      addToast('Error', 'Unable to rename chat.', 'error')
    }
  }

  // Delete chat
  function handleDeleteChatPrompt(chatId: string, chatTitle: string) {
    if (!activeProjectId) return
    setConfirmModalState({
      isOpen: true,
      title: 'Delete Chat Session',
      message: `Are you sure you want to delete "${chatTitle}"? All conversation messages in this session will be permanently erased.`,
      confirmText: 'Delete Chat',
      isDangerous: true,
      action: async () => {
        try {
          const res = await fetch(`/api/v1/projects/${activeProjectId}/chats/${chatId}`, {
            method: 'DELETE',
          })
          if (res.ok || res.status === 204) {
            setChats((prev) => {
              const remaining = prev.filter((c) => c.id !== chatId)
              if (activeChatId === chatId) {
                if (remaining.length > 0) {
                  setActiveChatId(remaining[0].id)
                } else {
                  setActiveChatId(null)
                  void createChatSession('Welcome Chat')
                }
              }
              return remaining
            })
            addToast('Chat Deleted', `Removed "${chatTitle}"`, 'info')
          }
        } catch {
          addToast('Error', 'Unable to delete chat session.', 'error')
        }
      },
    })
  }

  // Delete project
  function handleDeleteProjectPrompt(projectId: string, projectName: string) {
    setConfirmModalState({
      isOpen: true,
      title: 'Delete Project',
      message: `Are you sure you want to permanently delete "${projectName}"? This will delete all attached knowledge sources, indexed documents, and chat sessions. This action cannot be undone.`,
      confirmText: 'Delete Project Forever',
      isDangerous: true,
      action: async () => {
        try {
          const res = await fetch(`/api/v1/projects/${projectId}`, {
            method: 'DELETE',
          })
          if (res.ok || res.status === 204) {
            setProjects((prev) => {
              const remaining = prev.filter((p) => p.id !== projectId)
              if (activeProjectId === projectId) {
                setActiveProjectId(remaining.length > 0 ? remaining[0].id : null)
              }
              return remaining
            })
            addToast('Project Deleted', `Permanently deleted "${projectName}"`, 'info')
          }
        } catch {
          addToast('Error', 'Unable to delete project.', 'error')
        }
      },
    })
  }

  // Citation inspection
  async function handleInspectCitation(chunkId: string) {
    try {
      const res = await fetch(`/api/v1/citations/${chunkId}/context`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: CitationContext = await res.json()
      setActiveCitationContext(data)
    } catch (err) {
      addToast('Error', 'Unable to load citation context: ' + (err instanceof Error ? err.message : 'Error'), 'error')
    }
  }

  // ESC key closes modals
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setActiveCitationContext(null)
        setIsCreateProjectModalOpen(false)
        setIsProjectSettingsOpen(false)
        setIsAddSourceModalOpen(false)
        setInspectingSource(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  if (viewMode === 'landing') {
    return (
      <div className="doclore-root-wrap">
        <LandingPage
          onEnterWorkspace={() => setViewMode('workspace')}
          onImportRepo={() => {
            setViewMode('workspace')
            setIsCreateProjectModalOpen(true)
          }}
        />

        {/* Global Toast Container */}
        <ToastContainer toasts={toasts} onDismiss={dismissToast} />

        {/* Create Project Modal from Landing */}
        <CreateProjectModal
          isOpen={isCreateProjectModalOpen}
          onClose={() => setIsCreateProjectModalOpen(false)}
          onProjectCreated={(newProj) => {
            setProjects((prev) => [newProj, ...prev])
            setActiveProjectId(newProj.id)
            setViewMode('workspace')
          }}
          onNotify={addToast}
        />
      </div>
    )
  }

  return (
    <div className={`doclore-workspace ${isSidebarCollapsed ? 'doclore-workspace--collapsed' : ''}`}>
      {/* Sidebar: Projects & Chats Navigation */}
      <Sidebar
        projects={projects}
        activeProjectId={activeProjectId}
        isLoadingProjects={isLoadingProjects}
        onSelectProject={(id) => setActiveProjectId(id)}
        onOpenCreateProject={() => setIsCreateProjectModalOpen(true)}
        onOpenProjectSettings={() => setIsProjectSettingsOpen(true)}
        projectSources={projectSources}
        onOpenAddSource={() => setIsAddSourceModalOpen(true)}
        onSelectSource={(src) => setInspectingSource(src)}
        chats={chats}
        activeChatId={activeChatId}
        isLoadingChats={isLoadingChats}
        onSelectChat={(id) => setActiveChatId(id)}
        onCreateChat={() => void createChatSession()}
        onRenameChat={(id, title) => void handleRenameChat(id, title)}
        onDeleteChat={handleDeleteChatPrompt}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
        onReturnToLanding={() => setViewMode('landing')}
        apiStatus={apiStatus}
      />

      {/* Main Chat and Knowledge Workspace */}
      <ChatArea
        activeProject={activeProject}
        activeChat={activeChat}
        isSendingMessage={isSendingMessage}
        chatError={chatError}
        onSendMessage={handleSendMessage}
        onInspectCitation={handleInspectCitation}
        isCollapsed={isSidebarCollapsed}
        onExpandSidebar={() => setIsSidebarCollapsed(false)}
        onReturnToLanding={() => setViewMode('landing')}
        onOpenCreateProject={() => setIsCreateProjectModalOpen(true)}
        onOpenProjectSettings={() => setIsProjectSettingsOpen(true)}
        onNotify={addToast}
      />

      {/* Modal: Create Project */}
      <CreateProjectModal
        isOpen={isCreateProjectModalOpen}
        onClose={() => setIsCreateProjectModalOpen(false)}
        onProjectCreated={(newProj) => {
          setProjects((prev) => [newProj, ...prev])
          setActiveProjectId(newProj.id)
        }}
        onNotify={addToast}
      />

      {/* Modal: Project Settings */}
      {activeProject && (
        <ProjectSettingsModal
          isOpen={isProjectSettingsOpen}
          project={activeProject}
          onClose={() => setIsProjectSettingsOpen(false)}
          onUpdate={(updated) => {
            setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
            addToast('Project Updated', `Settings saved for "${updated.name}"`, 'success')
          }}
          onDeleteRequest={handleDeleteProjectPrompt}
        />
      )}

      {/* Modal: Attach Knowledge Source */}
      {activeProjectId && (
        <AddSourceModal
          isOpen={isAddSourceModalOpen}
          projectId={activeProjectId}
          onClose={() => setIsAddSourceModalOpen(false)}
          onSourceAdded={(newSrc) => {
            setProjectSources((prev) => [...prev, newSrc])
            if (activeProjectId) void refreshProject(activeProjectId)
          }}
          onNotify={addToast}
        />
      )}

      {/* Modal: Inspect & Manage Knowledge Source */}
      <SourceDetailModal
        isOpen={Boolean(inspectingSource)}
        source={inspectingSource}
        onClose={() => setInspectingSource(null)}
        onUpdateSource={(updated) => {
          setProjectSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
          setInspectingSource(updated)
          if (activeProjectId) void refreshProject(activeProjectId)
        }}
        onDeleteSource={(sourceId) => {
          setProjectSources((prev) => prev.filter((s) => s.id !== sourceId))
          if (activeProjectId) void refreshProject(activeProjectId)
        }}
        onNotify={addToast}
      />

      {/* Modal: Interactive Citation Context Inspector */}
      <CitationInspectorModal
        context={activeCitationContext}
        onClose={() => setActiveCitationContext(null)}
        onNotify={addToast}
      />

      {/* Modal: Confirm Action (Delete Project / Delete Chat) */}
      <ConfirmModal
        isOpen={confirmModalState.isOpen}
        title={confirmModalState.title}
        message={confirmModalState.message}
        confirmText={confirmModalState.confirmText}
        isDangerous={confirmModalState.isDangerous}
        isLoading={confirmModalState.isLoading}
        onConfirm={async () => {
          setConfirmModalState((prev) => ({ ...prev, isLoading: true }))
          try {
            await confirmModalState.action()
          } finally {
            setConfirmModalState((prev) => ({ ...prev, isOpen: false, isLoading: false }))
          }
        }}
        onCancel={() => setConfirmModalState((prev) => ({ ...prev, isOpen: false }))}
      />

      {/* Transient Notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}

export default App
