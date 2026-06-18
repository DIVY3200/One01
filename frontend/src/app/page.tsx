'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useStore } from '@/store/useStore'

export default function Home() {
  const router = useRouter()
  const token = useStore((s) => s.token)
  const preferences = useStore((s) => s.preferences)
  const user = useStore((s) => s.user)
  const [mounted, setMounted] = useState(false)

  // Wait for Zustand to hydrate from localStorage before any redirect
  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!mounted) return
    if (!token) {
      router.replace('/auth')
    } else if (!preferences && !user?.onboarding_completed) {
      router.replace('/onboarding')
    } else {
      router.replace('/dashboard')
    }
  }, [mounted, token, preferences, user, router])

  // Always show a clean spinner — this page is purely a router gate
  return (
    <div className="min-h-screen bg-paper flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <div className="font-display text-xl text-lead mb-1">One01</div>
        <div className="text-sm text-muted">Loading…</div>
      </div>
    </div>
  )
}