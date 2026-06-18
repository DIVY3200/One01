'use client'
import { useState } from 'react'
import { Eye, Code2, Save, Loader2 } from 'lucide-react'
import NoteViewer from './NoteViewer'

interface NoteEditorProps {
  content: string
  onChange: (val: string) => void
  onSave: () => Promise<void>
  isSaving?: boolean
  isUserEdited?: boolean
  updatedAt?: string | null
  topicTitle?: string
}

export default function NoteEditor({
  content,
  onChange,
  onSave,
  isSaving = false,
  isUserEdited = false,
  updatedAt,
  topicTitle,
}: NoteEditorProps) {
  const [preview, setPreview] = useState(true)

  const handleSave = async () => {
    await onSave()
    setPreview(true)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface flex-shrink-0">
        <div>
          {topicTitle && (
            <p className="text-sm font-medium text-lead leading-tight">{topicTitle}</p>
          )}
          {updatedAt && (
            <p className="text-[11px] text-muted mt-0.5">
              {new Date(updatedAt).toLocaleDateString(undefined, {
                day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
              })}
              {isUserEdited ? ' · Edited by you' : ' · By Scribe Agent'}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Toggle preview / source */}
          <button
            onClick={() => setPreview(!preview)}
            className={[
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-all',
              !preview
                ? 'border-accent bg-accent/8 text-lead'
                : 'border-border text-muted hover:text-ink',
            ].join(' ')}
          >
            {preview ? <Code2 size={13} /> : <Eye size={13} />}
            {preview ? 'Edit' : 'Preview'}
          </button>

          {/* Save — only shown in edit mode */}
          {!preview && (
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-lead text-paper text-xs hover:bg-lead/90 transition-all disabled:opacity-50"
            >
              {isSaving ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Save size={12} />
              )}
              Save
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {preview ? (
          <NoteViewer content={content} />
        ) : (
          <textarea
            value={content}
            onChange={(e) => onChange(e.target.value)}
            placeholder={`# ${topicTitle || 'Notes'}\n\nStart writing in Markdown…\nFormulas: $E = mc^2$`}
            className="w-full h-full resize-none bg-transparent font-mono text-sm text-ink focus:outline-none leading-relaxed px-8 py-6"
            spellCheck={false}
          />
        )}
      </div>
    </div>
  )
}