'use client'
import { CheckCircle2, Circle, Clock } from 'lucide-react'

interface Topic {
  id: string
  title: string
  index_order: number
  status: 'pending' | 'in_progress' | 'completed'
}

interface OutlinePanelProps {
  topics: Topic[]
  activeTopic: Topic | null
  onSelectTopic: (t: Topic) => void
  subjectName?: string
  subjectLevel?: string
  subjectPurpose?: string
  compact?: boolean
}

const statusIcon = (s: Topic['status']) => {
  if (s === 'completed') return <CheckCircle2 size={14} className="text-green-600" />
  if (s === 'in_progress') return <Clock size={14} className="text-amber-500" />
  return <Circle size={14} className="text-gray-300" />
}

export default function OutlinePanel({
  topics,
  activeTopic,
  onSelectTopic,
  subjectName,
  subjectLevel,
  subjectPurpose,
  compact,
}: OutlinePanelProps) {
  return (
    <div className="flex flex-col h-full">
      {!compact && (
        <div className="px-4 py-4 border-b border-border">
          <p className="font-display text-base text-lead truncate">{subjectName}</p>
          <p className="text-xs text-muted capitalize mt-0.5">
            {subjectPurpose} · {subjectLevel}
          </p>
        </div>
      )}
      <div className="flex-1 overflow-y-auto py-3">
        {topics.map((t) => (
          <button
            key={t.id}
            onClick={() => onSelectTopic(t)}
            className={`w-full flex items-start gap-2.5 px-4 py-3 text-left hover:bg-paper transition-colors ${
              activeTopic?.id === t.id ? 'bg-accent/6 border-r-2 border-accent' : ''
            }`}
          >
            <div className="mt-0.5 flex-shrink-0">{statusIcon(t.status)}</div>
            <span
              className={`text-xs leading-snug ${
                activeTopic?.id === t.id ? 'text-lead font-medium' : 'text-ink/70'
              }`}
            >
              {t.title}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
