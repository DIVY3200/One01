import axios from 'axios'
import { useStore } from '@/store/useStore'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000, // 60 seconds for non-streaming requests (outline generation etc.)
})

// Attach auth token
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token')
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 — clear ALL auth state (localStorage + Zustand persist) to break redirect loops
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      // Only act if there was a stored token (avoids clearing during login failures)
      const hadToken = localStorage.getItem('token')
      if (hadToken) {
        localStorage.removeItem('token')
        localStorage.removeItem('one01_user')
        // Clear Zustand persisted state — this writes nulls to one01-store in localStorage
        useStore.getState().logout()
        if (window.location.pathname !== '/auth') {
          window.location.href = '/auth'
        }
      }
    }
    return Promise.reject(err)
  }
)

// ── Streaming helper ────────────────────────────────────────────────
export async function streamFetch(
  url: string,
  onChunk: (chunk: string) => void,
  onDone?: (data?: Record<string, unknown>) => void
) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : ''
  const response = await fetch(`${API_URL}/api${url}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'text/event-stream',
    },
    signal: AbortSignal.timeout(120000), // 2 minutes for streaming AI responses
  })

  if (!response.body) return

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const raw = decoder.decode(value)
    const lines = raw.split('\n')
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const data = JSON.parse(line.slice(6))
        if (data.chunk) onChunk(data.chunk)
        if (data.type === 'done' && onDone) onDone()
        if (data.type === 'notes_ready' && onDone) onDone(data)
      } catch {}
    }
  }
}

export async function streamPost(
  url: string,
  body: Record<string, unknown>,
  onChunk: (chunk: string) => void,
  onDone?: (data?: Record<string, unknown>) => void,
  onEvent?: (data: Record<string, unknown>) => void
) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : ''
  const response = await fetch(`${API_URL}/api${url}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(120000), // 2 minutes for streaming AI responses
  })

  if (!response.body) return
  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const raw = decoder.decode(value)
    const lines = raw.split('\n')
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const data = JSON.parse(line.slice(6))
        if (data.chunk) onChunk(data.chunk)
        if (data.type === 'done' && onDone) onDone()
        if (data.type === 'notes_ready' && onDone) onDone(data)
        // Forward all events to onEvent handler for custom processing
        if (onEvent && data.type) onEvent(data)
      } catch {}
    }
  }
}