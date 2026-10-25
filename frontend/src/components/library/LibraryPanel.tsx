'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { CloudUpload, Database, FileText, GraduationCap, Loader2, Search, Sparkles, Trash2 } from 'lucide-react'
import { api, streamPost } from '@/lib/api'
import ChatMessage from '@/components/chat/ChatMessage'
import type { Source } from './SourceList'

interface LibraryDocument {
  id: string
  filename: string
  source_type: 'upload' | 'lesson'
  size_bytes: number
  num_pages: number | null
  num_chunks: number
  embedding_model: string | null
  status: 'ready' | 'failed'
  error: string | null
  created_at: string | null
}

interface RagStatus {
  model: string | null
  embedding_backends: string[]
  retrieval: string
  top_k: number
}

const ACCEPT = '.pdf,.md,.markdown,.txt'

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function LibraryPanel() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const [docs, setDocs] = useState<LibraryDocument[]>([])
  const [status, setStatus] = useState<RagStatus | null>(null)
  const [uploading, setUploading] = useState<string[]>([])
  const [dragging, setDragging] = useState(false)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<{ content: string; sources: Source[] } | null>(null)
  const [asking, setAsking] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const loadDocs = useCallback(async () => {
    const res = await api.get(`/rag/${subjectId}/documents`)
    setDocs(res.data)
  }, [subjectId])

  useEffect(() => {
    if (!subjectId) return
    loadDocs().catch(() => toast.error('Could not load your library'))
    api.get('/rag/status').then((res) => setStatus(res.data)).catch(() => {})
  }, [subjectId, loadDocs])

  const uploadFiles = async (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      setUploading((u) => [...u, file.name])
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await api.post(`/rag/${subjectId}/documents`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 180000, // large PDFs: parsing + embedding
        })
        if (res.data.status === 'failed') toast.error(`${file.name}: ${res.data.error}`)
        else toast.success(`${file.name} indexed · ${res.data.num_chunks} chunks`)
      } catch (err: any) {
        toast.error(err.response?.data?.detail || `Upload failed: ${file.name}`)
      } finally {
        setUploading((u) => u.filter((name) => name !== file.name))
      }
    }
    loadDocs().catch(() => {})
  }

  const handleDelete = async (doc: LibraryDocument) => {
    if (!window.confirm(`Remove "${doc.filename}" from your library?`)) return
    try {
      await api.delete(`/rag/documents/${doc.id}`)
      setDocs((prev) => prev.filter((d) => d.id !== doc.id))
    } catch {
      toast.error('Could not delete document')
    }
  }

  const handleAsk = async () => {
    const q = question.trim()
    if (!q || asking) return
    setAsking(true)
    setAnswer({ content: '', sources: [] })
    try {
      await streamPost(
        `/rag/${subjectId}/ask`,
        { question: q },
        (chunk) => setAnswer((a) => (a ? { ...a, content: a.content + chunk } : a)),
        undefined,
        (event) => {
          if (event.type === 'sources') {
            setAnswer((a) => (a ? { ...a, sources: event.sources as Source[] } : a))
          }
        }
      )
    } catch {
      toast.error('Could not reach the library')
    }
    setAsking(false)
  }

  const uploads = docs.filter((d) => d.source_type === 'upload')
  const lessons = docs.filter((d) => d.source_type === 'lesson')

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-5 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-display text-2xl text-lead">Study Library</h2>
            <p className="text-sm text-muted mt-1 max-w-xl">
              Upload notes, slides or papers. Your tutor retrieves from them while teaching and cites the exact
              passage it used.
            </p>
          </div>
          {status && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-surface text-[11px] font-mono text-muted">
              <Database size={12} />
              <span>{status.retrieval}</span>
              {status.model && <span className="text-accent-dim">· {status.model}</span>}
            </div>
          )}
        </div>

        {/* Upload */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files)
          }}
          onClick={() => fileInput.current?.click()}
          className={[
            'rounded-xl border-2 border-dashed px-6 py-8 text-center cursor-pointer transition-colors',
            dragging ? 'border-accent bg-accent/5' : 'border-border hover:border-accent/60 bg-surface',
          ].join(' ')}
        >
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            multiple
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.length) uploadFiles(e.target.files)
              e.target.value = ''
            }}
          />
          {uploading.length > 0 ? (
            <div className="flex flex-col items-center gap-2 text-sm text-lead">
              <Loader2 size={20} className="animate-spin text-accent" />
              Indexing {uploading.join(', ')}…
              <span className="text-[11px] text-muted">Extracting text → chunking → embedding</span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <CloudUpload size={22} className="text-accent" />
              <p className="text-sm text-lead">Drop files here or click to upload</p>
              <p className="text-[11px] text-muted">PDF, Markdown or text · up to 20 MB</p>
            </div>
          )}
        </div>

        {/* Ask the library */}
        <div className="space-y-3">
          <div className="flex gap-2">
            <div className="flex-1 flex items-center gap-2 px-4 bg-surface border border-border rounded-xl focus-within:border-accent transition-colors">
              <Search size={14} className="text-muted flex-shrink-0" />
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleAsk() }}
                placeholder="Ask a question answered only from your library…"
                className="flex-1 py-3 bg-transparent text-sm text-ink placeholder:text-muted/50 focus:outline-none"
              />
            </div>
            <button
              onClick={handleAsk}
              disabled={!question.trim() || asking || docs.length === 0}
              className="px-4 rounded-xl bg-lead text-paper text-xs font-medium flex items-center gap-1.5 hover:bg-lead/90 transition-all disabled:opacity-40"
            >
              {asking ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              Ask
            </button>
          </div>
          {answer && (
            <ChatMessage
              role="assistant"
              content={answer.content}
              isStreaming={asking}
              sources={answer.sources}
            />
          )}
        </div>

        {/* Documents */}
        <DocumentSection
          title="Your uploads"
          empty="No documents yet. Upload lecture notes or a textbook chapter to ground your lessons."
          docs={uploads}
          onDelete={handleDelete}
        />
        <DocumentSection
          title="Lesson memory"
          empty="Lessons you complete are saved here automatically, so later answers can build on them."
          docs={lessons}
          onDelete={handleDelete}
        />
      </div>
    </div>
  )
}

function DocumentSection({
  title,
  empty,
  docs,
  onDelete,
}: {
  title: string
  empty: string
  docs: LibraryDocument[]
  onDelete: (doc: LibraryDocument) => void
}) {
  return (
    <div>
      <p className="text-xs font-mono text-muted mb-2">
        {title} · {docs.length}
      </p>
      {docs.length === 0 ? (
        <p className="text-xs text-muted/80 px-4 py-3 rounded-lg border border-border bg-surface">{empty}</p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
          {docs.map((doc) => (
            <li key={doc.id} className="flex items-center gap-3 px-4 py-3">
              {doc.source_type === 'lesson' ? (
                <GraduationCap size={15} className="text-accent-dim flex-shrink-0" />
              ) : (
                <FileText size={15} className="text-lead flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-lead truncate">{doc.filename}</p>
                {doc.status === 'failed' ? (
                  <p className="text-[11px] text-error">{doc.error}</p>
                ) : (
                  <p className="text-[11px] text-muted font-mono">
                    {[
                      doc.num_pages ? `${doc.num_pages} pages` : null,
                      `${doc.num_chunks} chunks`,
                      formatSize(doc.size_bytes),
                      doc.embedding_model ? 'semantic + keyword' : 'keyword only',
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                )}
              </div>
              <button
                onClick={() => onDelete(doc)}
                title="Remove from library"
                className="p-1.5 rounded-md text-muted hover:text-error hover:bg-error/5 transition-colors"
              >
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
