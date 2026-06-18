'use client'
import { useEffect, useState, useRef, useCallback } from 'react'
import { api, streamFetch, streamPost } from '@/lib/api'
import { useStore } from '@/store/useStore'
import toast from 'react-hot-toast'
import { BookOpen, CheckCircle2 } from 'lucide-react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'

interface Topic {
  id: string
  title: string
  index_order: number
  status: 'pending' | 'in_progress' | 'completed'
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  agent_type?: string
}

interface ChatWindowProps {
  topic: Topic | null
  subjectName: string
  onTopicExplained?: () => void
  onMarkComplete?: () => void
  onTopicAdvanced?: (newTopicId: string, newTopicTitle: string, completedTopicId: string) => void
}

export default function ChatWindow({
  topic,
  subjectName,
  onTopicExplained,
  onMarkComplete,
  onTopicAdvanced,
}: ChatWindowProps) {
  const { preferences } = useStore()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [explaining, setExplaining] = useState(false)
  const [quizReady, setQuizReady] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Load chat history when topic changes
  useEffect(() => {
    if (!topic) return
    setMessages([])
    setQuizReady(false)
    api.get(`/chat/history/${topic.id}`).then((res) => {
      setMessages(res.data)
      if (res.data.some((m: Message) => m.role === 'assistant')) {
        setQuizReady(true)
      }
    })
  }, [topic?.id])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ── Start Lesson: stream explanation ────────────────────────────
  const handleExplain = useCallback(async () => {
    if (!topic || explaining) return
    setExplaining(true)
    setMessages([])

    const aiMsg: Message = { id: Date.now().toString(), role: 'assistant', content: '', agent_type: 'tutor' }
    setMessages([aiMsg])

    await streamFetch(
      `/chat/explain/${topic.id}`,
      (chunk) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === aiMsg.id ? { ...m, content: m.content + chunk } : m))
        )
      },
      (data) => {
        setQuizReady(true)
        if (data?.notes) toast.success('Notes generated!', { icon: '📝' })
      }
    )
    setExplaining(false)
    onTopicExplained?.()
  }, [topic, explaining, onTopicExplained])

  // ── Send doubt or navigation command ───────────────────────────
  const handleSend = async (overrideText?: string) => {
    const textToUse = typeof overrideText === 'string' ? overrideText : input;
    if (!textToUse.trim() || !topic || streaming) return
    const text = textToUse.trim()
    setInput('')

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text }
    const aiMsg: Message = { id: (Date.now() + 1).toString(), role: 'assistant', content: '', agent_type: 'tutor' }
    setMessages((prev) => [...prev, userMsg, aiMsg])
    setStreaming(true)

    let advancedToNewTopic = false

    await streamPost(
      '/chat/doubt',
      { topic_id: topic.id, message: text, message_type: 'doubt' },
      // onChunk
      (chunk) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === aiMsg.id ? { ...m, content: m.content + chunk } : m))
        )
      },
      // onDone
      () => {
        if (advancedToNewTopic) {
          setQuizReady(true)
        }
      },
      // onEvent — handle topic advancement, subject completion, etc.
      (event) => {
        if (event.type === 'topic_advanced') {
          advancedToNewTopic = true
          const newId = event.new_topic_id as string
          const newTitle = event.new_topic_title as string
          const completedId = event.completed_topic_id as string

          // Reset messages for the new topic and keep only streaming AI msg
          setMessages([{ ...aiMsg, content: '' }])

          toast.success(`Moving to: ${newTitle}`, { icon: '➡️' })

          // Notify parent page to update sidebar
          onTopicAdvanced?.(newId, newTitle, completedId)
        }

        if (event.type === 'subject_complete') {
          toast.success('🎓 All topics completed!', { duration: 5000 })
        }

        if (event.type === 'notes_ready') {
          toast.success('Notes generated!', { icon: '📝' })
        }
      }
    )
    setStreaming(false)
  }

  // ── No topic selected ──────────────────────────────────────────
  if (!topic) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted text-sm">
        Select a topic from the outline to begin.
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Topic header */}
      <div className="px-5 py-3 border-b border-border flex items-center justify-between flex-shrink-0">
        <div>
          <p className="text-xs text-muted font-mono">Current topic</p>
          <p className="text-sm font-medium text-lead">{topic.title}</p>
        </div>
        <div className="flex gap-2">
          {messages.length === 0 && !explaining && (
            <button
              onClick={handleExplain}
              className="px-4 py-2 bg-lead text-paper rounded-lg text-xs font-medium hover:bg-lead/90 transition-all flex items-center gap-2"
            >
              <BookOpen size={13} />
              Start Lesson
            </button>
          )}
          {quizReady && topic.status !== 'completed' && (
            <button
              onClick={onMarkComplete}
              className="px-4 py-2 bg-green-50 text-green-700 border border-green-200 rounded-lg text-xs font-medium hover:bg-green-100 transition-all flex items-center gap-2"
            >
              <CheckCircle2 size={13} />
              Complete
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-6 space-y-5">
        {messages.length === 0 && !explaining && (
          <div className="text-center py-16">
            <div className="font-display text-2xl text-lead mb-2">{topic.title}</div>
            <p className="text-muted text-sm mb-6">
              {preferences?.ai_teacher_name || 'Lead'} is ready to teach you this topic.
            </p>
            <button
              onClick={handleExplain}
              className="px-8 py-3 bg-lead text-paper rounded-lg text-sm font-medium hover:bg-lead/90 transition-all"
            >
              Begin Lesson →
            </button>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            role={msg.role}
            content={msg.content}
            isStreaming={(explaining || streaming) && msg.content === ''}
            onSend={(text) => handleSend(text)}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input — visible once lesson started */}
      {messages.length > 0 && (
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          streaming={streaming}
          disabled={explaining}
        />
      )}
    </div>
  )
}
