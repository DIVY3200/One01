'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import toast from 'react-hot-toast'
import { Loader2 } from 'lucide-react'
import NoteSidebar from '@/components/notes/NoteSidebar'
import NoteEditor from '@/components/notes/NoteEditor'
import NoteViewer from '@/components/notes/NoteViewer'

interface Note {
  id: string
  topic_id: string | null
  topic_title: string | null
  content: string
  is_user_edited: boolean
  updated_at: string | null
}

export default function NotesPage() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const [notes, setNotes] = useState<Note[]>([])
  const [activeNote, setActiveNote] = useState<Note | null>(null)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/notes/${subjectId}`)
      .then((res) => {
        setNotes(res.data)
        if (res.data.length > 0) {
          setActiveNote(res.data[0])
          setDraft(res.data[0].content)
        }
      })
      .finally(() => setLoading(false))
  }, [subjectId])

  const handleSelect = (note: Note) => {
    setActiveNote(note)
    setDraft(note.content)
  }

  const handleSave = async () => {
    if (!activeNote) return
    setSaving(true)
    try {
      await api.put(`/notes/${activeNote.id}`, { content: draft })
      const updated = { ...activeNote, content: draft, is_user_edited: true }
      setNotes((prev) => prev.map((n) => (n.id === activeNote.id ? updated : n)))
      setActiveNote(updated)
      toast.success('Notes saved')
    } catch {
      toast.error('Failed to save notes')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={20} className="animate-spin text-muted" />
      </div>
    )
  }

  return (
    <div className="flex h-full overflow-hidden">
      <NoteSidebar
        notes={notes}
        activeNoteId={activeNote?.id ?? null}
        onSelect={handleSelect}
      />
      <div className="flex-1 overflow-hidden flex flex-col">
        {activeNote ? (
          <NoteEditor
            content={draft}
            onChange={setDraft}
            onSave={handleSave}
            isSaving={saving}
            isUserEdited={activeNote.is_user_edited}
            updatedAt={activeNote.updated_at}
            topicTitle={activeNote.topic_title ?? undefined}
          />
        ) : (
          <NoteViewer content="" isEmpty />
        )}
      </div>
    </div>
  )
}