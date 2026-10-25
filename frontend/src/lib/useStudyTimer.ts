'use client'
import { useEffect, useRef } from 'react'
import { api } from '@/lib/api'

const HEARTBEAT_MS = 60_000 // the backend adds one minute per heartbeat
const IDLE_MS = 5 * 60_000 // no input for 5 minutes = not studying
const ACTIVITY_EVENTS = ['mousemove', 'keydown', 'scroll', 'touchstart', 'click']

/** Counts study time: one heartbeat per minute while the page is visible and the student is active. */
export function useStudyTimer(subjectId?: string | null) {
  const lastActivity = useRef(Date.now())

  useEffect(() => {
    if (!subjectId) return
    const markActive = () => {
      lastActivity.current = Date.now()
    }
    // capture: scroll events don't bubble, and the chat scrolls inside its own panel
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, markActive, { capture: true, passive: true }))

    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return
      if (Date.now() - lastActivity.current > IDLE_MS) return
      api.post(`/progress/${subjectId}/heartbeat`).catch(() => {})
    }, HEARTBEAT_MS)

    return () => {
      window.clearInterval(timer)
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, markActive, { capture: true }))
    }
  }, [subjectId])
}
