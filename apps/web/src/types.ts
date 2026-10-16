export type ApiStatus =
  | { kind: 'checking' }
  | { kind: 'connected' }
  | { kind: 'error'; message: string }

export interface Project {
  id: string
  name: string
  description?: string
  github_url?: string
  branch?: string
  subpath?: string
  repo_status?: string
  commit_hash?: string
  document_count: number
  created_at: string
}

export interface ProjectSource {
  id: string
  project_id: string
  source_type: string
  name: string
  config?: Record<string, unknown>
  status: string
  last_synced_at?: string
  metadata?: Record<string, unknown>
}

export interface SourceDocument {
  id: string
  source_id: string
  title: string
  canonical_path: string
  chunks: Array<{
    id: string
    text: string
    provenance: {
      canonical_path: string
      start_line: number | null
      end_line: number | null
      section_path: string | null
    }
  }>
}

export interface Citation {
  source_id: string
  document_id: string
  chunk_id: string
  source_type: string
  canonical_path: string
  start_line: number | null
  end_line: number | null
  section_path: string | null
  snippet: string
  relevance_note: string | null
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  intent_label?: string
  summary?: string
  root_cause?: string
  code_diff?: string
  recommended_actions?: string[]
  citations?: Citation[]
  workflow_trace?: string[]
  created_at: string
}

export interface ChatSession {
  id: string
  project_id: string
  title: string
  created_at: string
  messages: ChatMessage[]
}

export interface CitationLine {
  line_number: number
  content: string
  is_highlighted: boolean
}

export interface CitationContext {
  chunk_id: string
  document_id: string
  source_id: string
  source_type: string
  canonical_path: string
  section_path: string | null
  start_line: number | null
  end_line: number | null
  snippet: string
  document_title: string
  surrounding_lines: CitationLine[]
}

export interface ToastMessage {
  id: string
  title: string
  description?: string
  type?: 'success' | 'info' | 'error'
}
