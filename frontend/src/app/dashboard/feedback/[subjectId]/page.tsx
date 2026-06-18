'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import { useStore } from '@/store/useStore'
import toast from 'react-hot-toast'
import { Send, Loader2 } from 'lucide-react'

interface FeedbackEntry {
  id: string
  content: string
  ai_response: string
  created_at: string
}

const CATEGORIES = [
  { id: 'tone',     label: 'Tone'     },
  { id: 'pace',     label: 'Pace'     },
  { id: 'clarity',  label: 'Clarity'  },
  { id: 'depth',    label: 'Depth'    },
  { id: 'examples', label: 'Examples' },
]

export default function FeedbackPage() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const { preferences } = useStore()
  const [feedbacks, setFeedbacks] = useState<FeedbackEntry[]>([])
  const [text, setText] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [aiReply, setAiReply] = useState('')

  useEffect(() => {
    api.get(`/feedback/${subjectId}`).then((res) => setFeedbacks(res.data))
  }, [subjectId])

  const toggleCategory = (id: string) =>
    setSelected((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])

  const handleSubmit = async () => {
    if (!text.trim()) return
    setSubmitting(true)
    setAiReply('')
    try {
      const res = await api.post(`/feedback/${subjectId}`, {
        content: text,
        categories: Object.fromEntries(selected.map((s) => [s, true])),
      })
      setAiReply(res.data.ai_response)
      setFeedbacks((prev) => [
        {
          id: Date.now().toString(),
          content: text,
          ai_response: res.data.ai_response,
          created_at: new Date().toISOString(),
        },
        ...prev,
      ])
      setText('')
      setSelected([])
      toast.success('Feedback submitted — teacher is adapting!')
    } catch {
      toast.error('Failed to submit feedback')
    } finally {
      setSubmitting(false)
    }
  }

  const teacherName = preferences?.ai_teacher_name ?? 'Lead'

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <div className="mb-8">
        <p className="text-xs font-mono text-muted uppercase tracking-wider mb-1">Feedback</p>
        <h1 className="font-display text-3xl text-lead">Help {teacherName} improve</h1>
        <p className="text-sm text-muted mt-1">
          Your feedback directly shapes how your AI teacher teaches you.
        </p>
      </div>

      <div className="bg-surface border border-border rounded-xl p-5 mb-7">
        <div className="mb-4">
          <label className="block text-xs text-muted mb-2">What area does this relate to?</label>
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((c) => (
              <button
                key={c.id}
                onClick={() => toggleCategory(c.id)}
                className={`px-3 py-1.5 rounded-full border text-xs transition-all ${
                  selected.includes(c.id)
                    ? 'border-accent bg-accent/10 text-lead font-medium'
                    : 'border-border text-muted hover:border-accent/40'
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={`Describe what ${teacherName} should improve…`}
          rows={4}
          className="w-full resize-none px-4 py-3 bg-paper border border-border rounded-lg text-sm text-ink placeholder:text-muted/40 focus:outline-none focus:border-accent transition-colors mb-4"
        />

        <button
          onClick={handleSubmit}
          disabled={!text.trim() || submitting}
          className="w-full py-3 bg-lead text-paper rounded-lg text-sm font-medium hover:bg-lead/90 transition-all disabled:opacity-40 flex items-center justify-center gap-2"
        >
          {submitting
            ? <><Loader2 size={14} className="animate-spin" /> Processing…</>
            : <><Send size={14} /> Submit Feedback</>}
        </button>

        {aiReply && (
          <div className="mt-4 p-4 bg-accent/6 border border-accent/20 rounded-lg">
            <p className="text-xs font-mono text-accent mb-1">{teacherName} responds</p>
            <p className="text-sm text-ink leading-relaxed">{aiReply}</p>
          </div>
        )}
      </div>

      {feedbacks.length > 0 && (
        <div>
          <p className="text-xs font-mono text-muted uppercase tracking-wider mb-4">Previous Feedback</p>
          <div className="space-y-4">
            {feedbacks.map((f) => (
              <div key={f.id} className="bg-surface border border-border rounded-xl p-4">
                <p className="text-sm text-ink mb-1">{f.content}</p>
                <p className="text-[11px] text-muted mb-3">
                  {new Date(f.created_at).toLocaleDateString()}
                </p>
                {f.ai_response && (
                  <div className="p-3 bg-paper rounded-lg border border-border">
                    <p className="text-[11px] text-muted font-mono mb-1">Teacher's response</p>
                    <p className="text-xs text-ink">{f.ai_response}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}