'use client'
import { FileText, Pencil } from 'lucide-react'

interface Note {
  id: string
  topic_id: string | null
  topic_title: string | null
  content: string
  is_user_edited: boolean
  updated_at: string | null
}

interface NoteSidebarProps {
  notes: Note[]
  activeNoteId: string | null
  onSelect: (note: Note) => void
}

export default function NoteSidebar({ notes, activeNoteId, onSelect }: NoteSidebarProps) {
  return (
    <aside className="w-52 border-r border-border bg-surface flex-shrink-0 flex flex-col">
      <div className="px-4 py-4 border-b border-border flex-shrink-0">
        <p className="text-xs font-mono text-muted uppercase tracking-wider">Notes</p>
        <p className="text-[11px] text-muted/60 mt-0.5">{notes.length} topics</p>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {notes.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
            <FileText size={24} className="text-muted/25 mb-3" />
            <p className="text-xs text-muted">No notes yet. Complete a lesson to generate notes.</p>
          </div>
        )}

        {notes.map((note) => {
          const isActive = note.id === activeNoteId
          return (
            <button
              key={note.id}
              onClick={() => onSelect(note)}
              className={[
                'w-full text-left px-4 py-3 border-b border-border/50 transition-colors',
                'hover:bg-paper border-r-2',
                isActive ? 'bg-accent/6 border-r-accent' : 'border-r-transparent',
              ].join(' ')}
            >
              <p
                className={[
                  'text-xs leading-snug line-clamp-2',
                  isActive ? 'text-lead font-medium' : 'text-ink/70',
                ].join(' ')}
              >
                {note.topic_title || 'General Notes'}
              </p>

              <div className="flex items-center gap-2 mt-1.5">
                {note.is_user_edited ? (
                  <span className="flex items-center gap-1 text-[10px] text-accent">
                    <Pencil size={9} />
                    Edited
                  </span>
                ) : (
                  <span className="text-[10px] text-muted">Scribe Agent</span>
                )}
                {note.updated_at && (
                  <span className="text-[10px] text-muted/50">
                    {new Date(note.updated_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                    })}
                  </span>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </aside>
  )
}