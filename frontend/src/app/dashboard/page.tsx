'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useStore } from '@/store/useStore'
import { api } from '@/lib/api'
import toast from 'react-hot-toast'
import { BookOpen, Sparkles, Loader2 } from 'lucide-react'

const PURPOSES = [
  { id: 'academic', label: 'Academic / Exam', desc: 'Structured for exams and coursework' },
  { id: 'job', label: 'Job / Career', desc: 'Practical, industry-focused learning' },
  { id: 'research', label: 'Research', desc: 'Deep, critical, methodology-focused' },
]

const LEVELS = [
  { id: 'beginner', label: 'Beginner' },
  { id: 'intermediate', label: 'Intermediate' },
  { id: 'advanced', label: 'Advanced' },
]

export default function DashboardPage() {
  const router = useRouter()
  const { subjects, addSubject, setActiveSubject, preferences } = useStore()
  const [creating, setCreating] = useState(false)
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ name: '', purpose: 'academic', level: 'beginner' })

  const handleCreate = async () => {
    if (!form.name.trim()) return
    setLoading(true)
    try {
      const res = await api.post('/subjects/', form)
      addSubject({ id: res.data.id, ...form, current_topic_index: 0 })
      setActiveSubject(res.data.id)
      toast.success(`"${form.name}" is ready to study!`)
      router.push(`/dashboard/learn/${res.data.id}`)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Failed to create subject. Please check your API key and try again.'
      toast.error(detail)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      {/* Greeting */}
      <div className="mb-12">
        <h1 className="font-display text-4xl text-lead mb-2">
          {preferences ? `Welcome back, ${preferences.nickname}.` : 'Welcome back.'}
        </h1>
        <p className="text-muted text-sm">
          {subjects.length === 0
            ? 'Add your first subject to begin learning.'
            : `You're studying ${subjects.length} subject${subjects.length > 1 ? 's' : ''}. Keep going.`}
        </p>
      </div>

      {/* Existing subjects */}
      {subjects.length > 0 && (
        <div className="mb-10">
          <p className="text-xs font-mono text-muted uppercase tracking-wider mb-4">Continue Learning</p>
          <div className="grid gap-3">
            {subjects.map((s) => (
              <button
                key={s.id}
                onClick={() => { setActiveSubject(s.id); router.push(`/dashboard/learn/${s.id}`) }}
                className="flex items-center gap-4 p-4 bg-surface border border-border rounded-xl hover:border-accent transition-all duration-200 group text-left"
              >
                <div className="w-10 h-10 rounded-lg bg-lead/8 flex items-center justify-center flex-shrink-0">
                  <BookOpen size={18} className="text-lead/60" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-ink text-sm">{s.name}</p>
                  <p className="text-xs text-muted capitalize">{s.purpose} · {s.level}</p>
                </div>
                <div className="text-accent opacity-0 group-hover:opacity-100 transition-opacity text-xs">
                  Open →
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Create new subject */}
      {!creating ? (
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-3 w-full p-5 border-2 border-dashed border-border rounded-xl hover:border-accent hover:bg-accent/4 transition-all duration-200 group"
        >
          <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
            <Sparkles size={16} className="text-accent" />
          </div>
          <div className="text-left">
            <p className="text-sm font-medium text-ink group-hover:text-lead transition-colors">
              Add a new subject
            </p>
            <p className="text-xs text-muted">Professor Agent will build your curriculum</p>
          </div>
        </button>
      ) : (
        <div className="bg-surface border border-border rounded-xl p-6 animate-fade-up">
          <h3 className="font-display text-xl text-lead mb-5">New Subject</h3>

          <div className="space-y-5">
            <div>
              <label className="block text-xs text-muted mb-2">What do you want to learn?</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Quantum Physics, Machine Learning, History of Rome…"
                className="w-full px-4 py-3 bg-paper border border-border rounded-lg text-sm text-ink placeholder:text-muted/40 focus:outline-none focus:border-accent transition-colors"
                autoFocus
              />
            </div>

            <div>
              <label className="block text-xs text-muted mb-2">Learning purpose</label>
              <div className="grid grid-cols-3 gap-2">
                {PURPOSES.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setForm({ ...form, purpose: p.id })}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      form.purpose === p.id
                        ? 'border-accent bg-accent/8'
                        : 'border-border hover:border-accent/40'
                    }`}
                  >
                    <p className={`text-xs font-medium mb-0.5 ${form.purpose === p.id ? 'text-lead' : 'text-ink'}`}>
                      {p.label}
                    </p>
                    <p className="text-[11px] text-muted leading-tight">{p.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs text-muted mb-2">Your level</label>
              <div className="flex gap-2">
                {LEVELS.map((l) => (
                  <button
                    key={l.id}
                    onClick={() => setForm({ ...form, level: l.id })}
                    className={`flex-1 py-2.5 rounded-lg border text-sm transition-all ${
                      form.level === l.id
                        ? 'border-accent bg-accent/8 text-lead font-medium'
                        : 'border-border text-muted hover:border-accent/40'
                    }`}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => setCreating(false)}
                className="flex-1 py-2.5 border border-border rounded-lg text-sm text-muted hover:text-ink transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!form.name.trim() || loading}
                className="flex-1 py-2.5 bg-lead text-paper rounded-lg text-sm font-medium hover:bg-lead/90 transition-all disabled:opacity-40 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Building curriculum…
                  </>
                ) : (
                  'Generate Outline →'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}