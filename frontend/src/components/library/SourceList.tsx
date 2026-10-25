'use client'
import { useState } from 'react'
import { BookMarked, ChevronDown, ChevronRight, FileText, GraduationCap } from 'lucide-react'

export interface Source {
  n: number
  chunk_id: string
  document_id: string
  title: string
  source_type: 'upload' | 'lesson'
  page?: number | null
  heading?: string | null
  snippet: string
  score: number
  dense_score?: number | null
  keyword_score?: number | null
}

export function sourceLabel(s: Source) {
  return [s.title, s.page ? `p. ${s.page}` : null, s.heading].filter(Boolean).join(' · ')
}

interface SourceListProps {
  sources: Source[]
  query?: string
}

export default function SourceList({ sources, query }: SourceListProps) {
  const [open, setOpen] = useState(false)
  if (!sources?.length) return null

  return (
    <div className="mt-3 pt-3 border-t border-border">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-[11px] font-mono text-muted hover:text-lead transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <BookMarked size={12} />
        {sources.length} source{sources.length > 1 ? 's' : ''} from your library
      </button>

      {!open && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {sources.map((s) => (
            <button
              key={s.chunk_id}
              onClick={() => setOpen(true)}
              title={s.snippet}
              className="flex items-center gap-1 max-w-[220px] px-2 py-0.5 rounded-md border border-border bg-paper text-[11px] text-lead hover:border-accent transition-colors"
            >
              <span className="font-mono text-accent-dim">[{s.n}]</span>
              <span className="truncate">{sourceLabel(s)}</span>
            </button>
          ))}
        </div>
      )}

      {open && (
        <div className="mt-2 space-y-2">
          {query && (
            <p className="text-[11px] text-muted">
              Searched for: <span className="italic">{query}</span>
            </p>
          )}
          {sources.map((s) => (
            <div key={s.chunk_id} className="rounded-lg border border-border bg-paper/60 px-3 py-2">
              <div className="flex items-center gap-2 text-xs text-lead min-w-0">
                <span className="w-5 h-5 rounded bg-lead text-paper text-[10px] font-mono flex items-center justify-center flex-shrink-0">
                  {s.n}
                </span>
                {s.source_type === 'lesson' ? (
                  <GraduationCap size={12} className="flex-shrink-0" />
                ) : (
                  <FileText size={12} className="flex-shrink-0" />
                )}
                <span className="font-medium truncate">{sourceLabel(s)}</span>
              </div>
              <p className="mt-1.5 text-xs text-muted leading-relaxed whitespace-pre-line">{s.snippet}</p>
              <div className="mt-1.5 flex flex-wrap gap-x-3 text-[10px] font-mono text-muted/80">
                <span>RRF {s.score.toFixed(4)}</span>
                {s.dense_score != null && <span>cosine {s.dense_score.toFixed(3)}</span>}
                {s.keyword_score != null && <span>BM25 {s.keyword_score.toFixed(2)}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
