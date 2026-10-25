import axios from 'axios'
import toast from 'react-hot-toast'
import { useStore } from '@/store/useStore'

// Shown when the backend served sample content because Gemini was unavailable.
// A fixed toast id means repeated warnings replace each other instead of stacking.
export function warnAiFallback(message?: string) {
  toast(message || 'Gemini is unavailable right now, so you are seeing sample content.', {
    id: 'ai-fallback',
    icon: '⚠️',
    duration: 6000,
  })
}

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
  (res) => {
    if (res.headers['x-ai-fallback']) warnAiFallback()
    return res
  },
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

// ── Streaming helpers ───────────────────────────────────────────────
export type StreamEvent = Record<string, unknown>

// Server-Sent Events reader. Buffers partial lines, so an event split across
// two network reads (e.g. a large `sources` payload) is not dropped.
async function readEventStream(
  response: Response,
  onChunk: (chunk: string) => void,
  onDone?: (data?: StreamEvent) => void,
  onEvent?: (data: StreamEvent) => void
) {
  // Errors (rate limit, not found, ...) come back as JSON, not a stream: show them in the reply
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      detail = (await response.json()).detail || detail
    } catch {}
    onChunk(`⚠️ ${detail}`)
    onEvent?.({ type: 'error', status: response.status, message: detail })
    return
  }
  if (!response.body) return
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const handleLine = (line: string) => {
    if (!line.startsWith('data: ')) return
    try {
      const data = JSON.parse(line.slice(6))
      if (data.chunk) onChunk(data.chunk)
      if (data.type === 'done' && onDone) onDone()
      if (data.type === 'notes_ready' && onDone) onDone(data)
      if (data.type === 'ai_fallback') warnAiFallback(data.message)
      // Forward all events to onEvent handler for custom processing
      if (onEvent && data.type) onEvent(data)
    } catch {}
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    lines.forEach(handleLine)
  }
  buffer += decoder.decode()
  if (buffer) handleLine(buffer)
}

export async function streamFetch(
  url: string,
  onChunk: (chunk: string) => void,
  onDone?: (data?: StreamEvent) => void,
  onEvent?: (data: StreamEvent) => void
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
  await readEventStream(response, onChunk, onDone, onEvent)
}

export async function streamPost(
  url: string,
  body: Record<string, unknown>,
  onChunk: (chunk: string) => void,
  onDone?: (data?: StreamEvent) => void,
  onEvent?: (data: StreamEvent) => void
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
  await readEventStream(response, onChunk, onDone, onEvent)
}
