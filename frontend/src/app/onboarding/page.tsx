'use client'
import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { api } from '@/lib/api'
import { useStore } from '@/store/useStore'
import toast from 'react-hot-toast'

const TEACHING_STYLES = [
  { id: 'brother', label: 'Brother / Sister', desc: 'Casual, warm, relatable' },
  { id: 'friend', label: 'Best Friend', desc: 'Fun, conversational, humorous' },
  { id: 'philosopher', label: 'Philosopher', desc: 'Socratic, questioning, deep' },
  { id: 'scientist', label: 'Scientist', desc: 'Rigorous, precise, evidence-based' },
  { id: 'professor', label: 'Professor', desc: 'Formal, structured, academic' },
  { id: 'mentor', label: 'Mentor', desc: 'Balanced, growth-focused, wise' },
]

const GENDERS = [
  { id: 'male', label: 'He / Him' },
  { id: 'female', label: 'She / Her' },
  { id: 'neutral', label: 'They / Them' },
]

function OnboardingForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const isEdit = searchParams.get('edit') === 'true'
  
  const { user, preferences, setPreferences, setAuth, token } = useStore()
  
  // Guard
  useEffect(() => {
    if (!isEdit && user?.onboarding_completed) {
      router.replace('/dashboard')
    }
  }, [isEdit, user, router])

  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  
  // If editing, use existing preferences as initial state
  const [form, setForm] = useState({
    nickname: isEdit && preferences?.nickname ? preferences.nickname : '',
    ai_teacher_name: isEdit && preferences?.ai_teacher_name ? preferences.ai_teacher_name : '',
    ai_gender: isEdit && preferences?.ai_gender ? preferences.ai_gender : 'neutral',
    teaching_style: isEdit && preferences?.teaching_style ? preferences.teaching_style : 'mentor',
  })

  const steps = [
    {
      title: 'What should your AI teacher call you?',
      subtitle: 'Pick a nickname — bro, champ, genius, or anything you like.',
      content: (
        <div>
          <input
            type="text"
            value={form.nickname}
            onChange={(e) => setForm({ ...form, nickname: e.target.value })}
            placeholder="e.g. bro, buddy, champ, Alex…"
            maxLength={30}
            className="w-full px-4 py-3.5 bg-surface border border-border rounded-lg text-sm text-ink placeholder:text-muted/40 focus:outline-none focus:border-accent transition-colors"
          />
          <p className="text-xs text-muted mt-2">This is how your AI teacher will address you every session.</p>
        </div>
      ),
      valid: form.nickname.trim().length > 0,
    },
    {
      title: 'Name your AI teacher',
      subtitle: 'Give your teacher a name and choose their pronouns.',
      content: (
        <div className="space-y-4">
          <input
            type="text"
            value={form.ai_teacher_name}
            onChange={(e) => setForm({ ...form, ai_teacher_name: e.target.value })}
            placeholder="e.g. Nova, Atlas, Sage, Zara…"
            maxLength={30}
            className="w-full px-4 py-3.5 bg-surface border border-border rounded-lg text-sm text-ink placeholder:text-muted/40 focus:outline-none focus:border-accent transition-colors"
          />
          <div className="flex gap-3">
            {GENDERS.map((g) => (
              <button
                key={g.id}
                onClick={() => setForm({ ...form, ai_gender: g.id })}
                className={`flex-1 py-3 rounded-lg border text-sm transition-all ${
                  form.ai_gender === g.id
                    ? 'border-accent bg-accent/8 text-lead font-medium'
                    : 'border-border text-muted hover:border-accent/50'
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>
      ),
      valid: form.ai_teacher_name.trim().length > 0,
    },
    {
      title: 'How should your teacher teach?',
      subtitle: 'Choose the teaching persona that resonates with you.',
      content: (
        <div className="grid grid-cols-2 gap-3">
          {TEACHING_STYLES.map((s) => (
            <button
              key={s.id}
              onClick={() => setForm({ ...form, teaching_style: s.id })}
              className={`text-left p-4 rounded-lg border transition-all duration-200 ${
                form.teaching_style === s.id
                  ? 'border-accent bg-accent/8'
                  : 'border-border hover:border-accent/50'
              }`}
            >
              <p className={`text-sm font-medium mb-0.5 ${form.teaching_style === s.id ? 'text-lead' : 'text-ink'}`}>
                {s.label}
              </p>
              <p className="text-xs text-muted">{s.desc}</p>
            </button>
          ))}
        </div>
      ),
      valid: true,
    },
  ]

  const current = steps[step]

  const handleNext = async () => {
    if (step < steps.length - 1) {
      setStep(step + 1)
    } else {
      setLoading(true)
      try {
        await api.post('/auth/preferences', form)
        setPreferences(form)
        if (user && token) {
           setAuth(token, { ...user, onboarding_completed: true })
        }
        
        if (isEdit) {
          toast.success('Profile updated successfully!')
        } else {
          toast.success(`Welcome! ${form.ai_teacher_name} is ready to teach you.`)
        }
        router.push('/dashboard')
      } catch {
        toast.error('Could not save preferences')
      } finally {
        setLoading(false)
      }
    }
  }

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="font-display text-xl text-lead mb-12">
          {isEdit ? 'Edit Your AI Mentor' : 'One01'}
        </div>

        {/* Progress */}
        <div className="flex gap-2 mb-10">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`h-0.5 flex-1 rounded-full transition-all duration-300 ${
                i <= step ? 'bg-accent' : 'bg-border'
              }`}
            />
          ))}
        </div>

        {/* Step */}
        <div className="animate-fade-up">
          <p className="text-xs text-muted font-mono mb-3">Step {step + 1} of {steps.length}</p>
          <h2 className="font-display text-2xl text-lead mb-2">{current.title}</h2>
          <p className="text-muted text-sm mb-8">{current.subtitle}</p>
          {current.content}
        </div>

        {/* Navigation */}
        <div className="flex justify-between items-center mt-10">
          <button
            onClick={() => setStep(Math.max(0, step - 1))}
            disabled={step === 0}
            className="text-sm text-muted hover:text-ink transition-colors disabled:opacity-0"
          >
            ← Back
          </button>
          <button
            onClick={handleNext}
            disabled={!current.valid || loading}
            className="px-8 py-2.5 bg-lead text-paper rounded-lg text-sm font-medium hover:bg-lead/90 transition-all disabled:opacity-40"
          >
            {loading ? 'Saving…' : step < steps.length - 1 ? 'Continue →' : isEdit ? 'Save Changes' : 'Start Learning →'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-paper flex justify-center items-center text-muted">Loading...</div>}>
      <OnboardingForm />
    </Suspense>
  )
}