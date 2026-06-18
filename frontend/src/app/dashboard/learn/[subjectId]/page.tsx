'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import { useStore } from '@/store/useStore'
import toast from 'react-hot-toast'
import { LayoutList, MessageCircle, ClipboardList } from 'lucide-react'
import ChatWindow from '@/components/chat/ChatWindow'
import OutlinePanel from '@/components/outline/OutlinePanel'
import QuizPanel from '@/components/quiz/QuizPanel'

interface Topic {
  id: string
  title: string
  index_order: number
  status: 'pending' | 'in_progress' | 'completed'
}

type TabType = 'chat' | 'outline' | 'quiz'

export default function LearnPage() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const { setActiveSubject } = useStore()
  const [subject, setSubject] = useState<{ name: string; level: string; purpose: string } | null>(null)
  const [topics, setTopics] = useState<Topic[]>([])
  const [activeTopic, setActiveTopic] = useState<Topic | null>(null)
  const [tab, setTab] = useState<TabType>('chat')

  useEffect(() => {
    if (!subjectId) return
    setActiveSubject(subjectId)
    api.get(`/subjects/${subjectId}`).then((res) => {
      setSubject({ name: res.data.name, level: res.data.level, purpose: res.data.purpose })
      const ts: Topic[] = res.data.topics
      setTopics(ts)
      const first = ts.find((t) => t.status !== 'completed') ?? ts[0]
      if (first) setActiveTopic(first)
    })
  }, [subjectId, setActiveSubject])

  const handleTopicExplained = () => {
    setTopics((prev) =>
      prev.map((t) => (t.id === activeTopic?.id ? { ...t, status: 'in_progress' as const } : t))
    )
  }

  const handleTopicAdvanced = (newTopicId: string, newTopicTitle: string, completedTopicId: string) => {
    // Update sidebar: mark completed + in_progress
    setTopics((prev) =>
      prev.map((t) => {
        if (t.id === completedTopicId) return { ...t, status: 'completed' as const }
        if (t.id === newTopicId) return { ...t, status: 'in_progress' as const }
        return t
      })
    )
    // Switch active topic
    setActiveTopic({ id: newTopicId, title: newTopicTitle, index_order: 0, status: 'in_progress' })
  }

  const handleMarkComplete = async () => {
    if (!activeTopic) return
    await api.patch(`/topics/${activeTopic.id}/complete`)
    const updated = topics.map((t) =>
      t.id === activeTopic.id ? { ...t, status: 'completed' as const } : t
    )
    setTopics(updated)
    toast.success('Topic completed! 🎉')
    const idx = topics.findIndex((t) => t.id === activeTopic.id)
    const next = updated[idx + 1]
    if (next) { setActiveTopic(next); setTab('chat') }
  }

  const TABS: { id: TabType; label: string; Icon: React.ComponentType<{ size: number }> }[] = [
    { id: 'chat', label: 'Chat', Icon: MessageCircle },
    { id: 'outline', label: 'Outline', Icon: LayoutList },
    { id: 'quiz', label: 'Quiz', Icon: ClipboardList },
  ]

  return (
    <div className="flex h-full">
      <aside className="hidden lg:flex flex-col w-64 border-r border-border flex-shrink-0 bg-surface overflow-hidden">
        <OutlinePanel
          topics={topics}
          activeTopic={activeTopic}
          onSelectTopic={(t) => { setActiveTopic(t); setTab('chat') }}
          subjectName={subject?.name}
          subjectLevel={subject?.level}
          subjectPurpose={subject?.purpose}
        />
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-auto">
        <div className="flex items-center border-b border-border px-4 bg-surface flex-shrink-0">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={[
                'flex items-center gap-1.5 px-4 py-3.5 text-xs border-b-2 transition-all',
                tab === id ? 'border-accent text-lead font-medium' : 'border-transparent text-muted hover:text-ink',
                id === 'outline' ? 'lg:hidden' : '',
              ].join(' ')}
            >
              <Icon size={13} />
              {label}
            </button>
          ))}
        </div>

        {tab === 'chat' && (
          <ChatWindow
            topic={activeTopic}
            subjectName={subject?.name ?? ''}
            onTopicExplained={handleTopicExplained}
            onMarkComplete={handleMarkComplete}
            onTopicAdvanced={handleTopicAdvanced}
          />
        )}

        {tab === 'outline' && (
          <div className="flex-1 overflow-hidden">
            <OutlinePanel
              topics={topics}
              activeTopic={activeTopic}
              onSelectTopic={(t) => { setActiveTopic(t); setTab('chat') }}
              subjectName={subject?.name}
              subjectLevel={subject?.level}
              subjectPurpose={subject?.purpose}
              compact
            />
          </div>
        )}

        {tab === 'quiz' && (
          activeTopic
            ? <QuizPanel />
            : <div className="flex-1 flex items-center justify-center text-muted text-sm">Select a topic first.</div>
        )}
      </div>
    </div>
  )
}