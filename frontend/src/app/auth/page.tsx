'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { useStore } from '@/store/useStore'
import toast from 'react-hot-toast'

export default function AuthPage() {
  const router = useRouter()
  const setAuth = useStore((s) => s.setAuth)
  const setPreferences = useStore((s) => s.setPreferences)

  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [loading, setLoading] = useState(false)
  const [isChecking, setIsChecking] = useState(true)
  const [form, setForm] = useState({ email: '', password: '', full_name: '' })

  const token = useStore((s) => s.token)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  // Guard: check for existing token
  useEffect(() => {
    if (!mounted) return
    // Migrate old token key
    const oldToken = localStorage.getItem('one01_token')
    if (oldToken && !localStorage.getItem('token')) {
      localStorage.setItem('token', oldToken)
      localStorage.removeItem('one01_token')
    }
    const localToken = localStorage.getItem('token')
    if (token || localToken) {
      router.replace('/dashboard')
      // keep isChecking=true so spinner shows during redirect, form never flashes
    } else {
      setIsChecking(false)
    }
  }, [mounted, token, router])

  const handle = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const endpoint = mode === 'register' ? '/auth/register' : '/auth/login'
      const payload =
        mode === 'login'
          ? new URLSearchParams({ username: form.email, password: form.password })
          : form

      const res = await (mode === 'login'
        ? api.post(endpoint, payload, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
        : api.post(endpoint, payload))

      const data = res.data
      localStorage.setItem('token', data.access_token)

      const meRes = await api.get('/auth/me', { headers: { Authorization: `Bearer ${data.access_token}` } })
      const me = meRes.data

      setAuth(data.access_token, { id: me.id, email: me.email, full_name: me.full_name, onboarding_completed: me.onboarding_completed })

      if (me.onboarding_completed) {
        if (me.preferences) setPreferences(me.preferences)
        router.replace('/dashboard')
      } else {
        router.replace('/onboarding')
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Something went wrong'
      toast.error(msg, { duration: 5000 })
    } finally {
      setLoading(false)
    }
  }

  // Render spinner while token check runs — zero UI flicker
  if (isChecking) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <div className="text-sm text-muted">Loading…</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-paper flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-lead flex-col justify-between p-16">
        <div className="font-display text-2xl text-accent">One01</div>
        <div>
          <p className="font-display text-4xl text-paper leading-snug mb-6">
            Your personal<br />
            <em>council of AI teachers</em>
          </p>
          <p className="text-paper/50 text-sm leading-relaxed max-w-sm">
            Professor, Tutor, Examiner, and Scribe — four agents working in concert
            to ensure you never stop learning.
          </p>
        </div>
        <div className="flex gap-8">
          {['Professor', 'Tutor', 'Examiner', 'Scribe'].map((a) => (
            <div key={a} className="text-center">
              <div className="w-10 h-10 rounded-full bg-paper/10 flex items-center justify-center mx-auto mb-2">
                <span className="text-accent text-xs font-mono">{a[0]}</span>
              </div>
              <p className="text-paper/40 text-xs">{a}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Logo mobile */}
          <div className="lg:hidden font-display text-2xl text-lead mb-10">One01</div>

          <h1 className="font-display text-3xl text-lead mb-2">
            {mode === 'login' ? 'Welcome back' : 'Start learning'}
          </h1>
          <p className="text-muted text-sm mb-8">
            {mode === 'login'
              ? 'Sign in to continue your journey'
              : 'Create your account — it takes 30 seconds'}
          </p>

          <form onSubmit={handle} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-xs text-muted mb-1.5">Full name</label>
                <input
                  type="text"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  placeholder="Your name"
                  className="w-full px-4 py-3 bg-surface border border-border rounded-lg text-sm text-ink placeholder:text-muted/50 focus:outline-none focus:border-accent transition-colors"
                />
              </div>
            )}
            <div>
              <label className="block text-xs text-muted mb-1.5">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@example.com"
                required
                className="w-full px-4 py-3 bg-surface border border-border rounded-lg text-sm text-ink placeholder:text-muted/50 focus:outline-none focus:border-accent transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-muted mb-1.5">Password</label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="••••••••"
                required
                minLength={8}
                className="w-full px-4 py-3 bg-surface border border-border rounded-lg text-sm text-ink placeholder:text-muted/50 focus:outline-none focus:border-accent transition-colors"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-lead text-paper py-3 rounded-lg text-sm font-medium hover:bg-lead/90 transition-all duration-200 disabled:opacity-50 mt-2"
            >
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          <p className="text-center text-sm text-muted mt-6">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
              className="text-accent font-medium underline underline-offset-2 hover:text-accent/80 transition-colors"
            >
              {mode === 'login' ? 'Sign up free →' : '← Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}