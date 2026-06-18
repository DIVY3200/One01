'use client'
import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { useStore } from '@/store/useStore'
import { api } from '@/lib/api'
import {
  BookOpen, BarChart2, FileText, HelpCircle, MessageSquare,
  Plus, ChevronRight, LogOut, Menu, X, Trash2, Settings
} from 'lucide-react'
import toast from 'react-hot-toast'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const token = useStore((s) => s.token)
  const user = useStore((s) => s.user)
  const preferences = useStore((s) => s.preferences)
  const subjects = useStore((s) => s.subjects)
  const setSubjects = useStore((s) => s.setSubjects)
  const removeSubject = useStore((s) => s.removeSubject)
  const activeSubjectId = useStore((s) => s.activeSubjectId)
  const setActiveSubject = useStore((s) => s.setActiveSubject)
  const logout = useStore((s) => s.logout)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isChecking, setIsChecking] = useState(true)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!mounted) return

    // ── Migrate old token key from previous code ──
    const oldToken = localStorage.getItem('one01_token')
    if (oldToken && !localStorage.getItem('token')) {
      localStorage.setItem('token', oldToken)
      localStorage.removeItem('one01_token')
    }

    const localToken = localStorage.getItem('token')
    // Read Zustand state imperatively — avoids reactive dependency loops
    const { token: storeToken, user: storeUser, preferences: storePrefs } = useStore.getState()

    // ── No token anywhere → go to auth ──
    if (!storeToken && !localToken) {
      router.replace('/auth')
      return
    }

    // ── Sync: Zustand has token but localStorage doesn't ──
    if (storeToken && !localToken) {
      localStorage.setItem('token', storeToken)
    }

    // ── User already in store → just check onboarding ──
    if (storeUser) {
      if (!storePrefs && !storeUser.onboarding_completed && !pathname.includes('onboarding')) {
        router.replace('/onboarding')
        return
      }
      setIsChecking(false)
      return
    }

    // ── Token exists but no user in store → fetch from API ──
    const effectiveToken = localToken || storeToken
    api.get('/auth/me')
      .then((res) => {
        const u = res.data
        useStore.getState().setAuth(effectiveToken!, {
          id: u.id,
          email: u.email,
          full_name: u.full_name,
          onboarding_completed: u.onboarding_completed
        })
        if (u.preferences) useStore.getState().setPreferences(u.preferences)
        if (!u.onboarding_completed && !pathname.includes('onboarding')) {
          router.replace('/onboarding')
        } else {
          setIsChecking(false)
        }
      })
      .catch((err) => {
        console.error('Auth check failed:', err)
        localStorage.removeItem('token')
        useStore.getState().logout()
        router.replace('/auth')
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, pathname, router])

  useEffect(() => {
    if (!isChecking) {
      api.get('/subjects/').then((res) => setSubjects(res.data)).catch(() => {})
    }
  }, [isChecking, setSubjects])

  const navItems = activeSubjectId
    ? [
        { href: `/dashboard/learn/${activeSubjectId}`, icon: BookOpen, label: 'Learn' },
        { href: `/dashboard/notes/${activeSubjectId}`, icon: FileText, label: 'Notes' },
        { href: `/dashboard/progress/${activeSubjectId}`, icon: BarChart2, label: 'Progress' },
        { href: `/dashboard/questions/${activeSubjectId}`, icon: HelpCircle, label: 'Question Bank' },
        { href: `/dashboard/feedback/${activeSubjectId}`, icon: MessageSquare, label: 'Feedback' },
      ]
    : []

  const handleLogout = () => {
    logout()
    localStorage.removeItem('token')
    router.replace('/auth')
  }

  const handleDeleteSubject = async (e: React.MouseEvent, id: string, name: string) => {
    e.stopPropagation()
    if (window.confirm(`Are you sure you want to delete "${name}"? This action cannot be undone.`)) {
      // Instant UI removal
      removeSubject(id)
      if (activeSubjectId === id) {
        setActiveSubject(null)
        router.push('/dashboard')
      }
      try {
        await api.delete(`/subjects/${id}`)
        toast.success(`"${name}" deleted successfully`)
      } catch {
        // Re-fetch to restore state if delete failed on server
        toast.error('Failed to delete subject on server. Refreshing...')
        api.get('/subjects/').then((res) => setSubjects(res.data)).catch(() => {})
      }
    }
  }

  const renderSidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <div className="font-display text-xl text-lead">One01</div>
        {preferences && (
          <p className="text-xs text-muted mt-0.5">
            Hello, {preferences.nickname} · {preferences.ai_teacher_name}
          </p>
        )}
      </div>

      {/* Subjects list */}
      <div className="px-3 py-4 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between px-2 mb-3">
          <p className="text-xs font-mono text-muted uppercase tracking-wider">Subjects</p>
          <button
            onClick={() => { router.push('/dashboard'); setSidebarOpen(false) }}
            className="w-6 h-6 rounded flex items-center justify-center hover:bg-border transition-colors z-10"
            title="Add subject"
          >
            <Plus size={14} className="text-muted" />
          </button>
        </div>

        {subjects.length === 0 && (
          <p className="text-xs text-muted px-2 py-3">No subjects yet. Add one to begin.</p>
        )}

        {subjects.map((s) => (
          <div key={s.id} className="relative group flex items-center mb-1 outline-none">
            <button
              onClick={() => {
                setActiveSubject(s.id)
                router.push(`/dashboard/learn/${s.id}`)
                setSidebarOpen(false)
              }}
              className={`sidebar-item flex-1 pr-8 ${activeSubjectId === s.id ? 'active' : 'text-ink/70'}`}
            >
              <BookOpen size={15} />
              <span className="flex-1 text-left truncate">{s.name}</span>
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                handleDeleteSubject(e, s.id, s.name);
              }}
              className="absolute right-2 p-1.5 text-muted hover:text-error hover:bg-error/10 rounded transition-all z-10 lg:opacity-0 lg:group-hover:opacity-100"
              title="Delete Subject"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}

        {/* Nav items for active subject */}
        {activeSubjectId && navItems.length > 0 && (
          <div className="mt-4 border-t border-border pt-4">
            <p className="text-xs font-mono text-muted uppercase tracking-wider px-2 mb-3">Section</p>
            {navItems.map((item) => {
              const isActive = pathname === item.href
              return (
                <Link key={item.href} href={item.href} onClick={() => setSidebarOpen(false)}>
                  <div className={`sidebar-item ${isActive ? 'active' : 'text-ink/70'}`}>
                    <item.icon size={15} />
                    <span>{item.label}</span>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>

      {/* Bottom */}
      <div className="px-3 py-4 border-t border-border">
        <Link 
          href="/onboarding?edit=true" 
          onClick={() => setSidebarOpen(false)}
          className="sidebar-item block w-full text-muted hover:text-ink mb-1 flex items-center"
        >
          <Settings size={15} className="mr-3" />
          <span>Edit Profile</span>
        </Link>
        <button
          onClick={handleLogout}
          className="sidebar-item w-full text-muted hover:text-error flex items-center z-10"
        >
          <LogOut size={15} className="mr-3" />
          <span>Sign out</span>
        </button>
      </div>
    </div>
  )

  // Show spinner until auth is confirmed — prevents content flash
  if (isChecking) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <div className="font-display text-xl text-lead mb-1">One01</div>
          <div className="text-sm text-muted">Loading your workspace…</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-paper overflow-hidden">
      {/* Sidebar desktop */}
      <aside className="hidden md:flex flex-col w-60 bg-surface border-r border-border flex-shrink-0">
        {renderSidebarContent()}
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="w-64 bg-surface border-r border-border flex flex-col">
            <div className="flex justify-end p-3">
              <button onClick={() => setSidebarOpen(false)}>
                <X size={20} className="text-muted" />
              </button>
            </div>
            {renderSidebarContent()}
          </div>
          <div className="flex-1 bg-black/30" onClick={() => setSidebarOpen(false)} />
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile topbar */}
        <div className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-border bg-surface">
          <button onClick={() => setSidebarOpen(true)}>
            <Menu size={20} className="text-muted" />
          </button>
          <div className="font-display text-lg text-lead">One01</div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </main>
    </div>
  )
}