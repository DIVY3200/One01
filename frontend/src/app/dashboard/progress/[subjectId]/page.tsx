'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import { Loader2 } from 'lucide-react'
import ProgressStats from '@/components/progress/ProgressStats'
import ConceptTags from '@/components/progress/ConceptTags'

interface ProgressData {
  total_topics: number
  completed_topics: number
  completion_percent: number
  avg_quiz_score: number
  weak_concepts: string[]
  strong_concepts: string[]
  time_spent_minutes: number
  last_activity: string | null
}

export default function ProgressPage() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const [progress, setProgress] = useState<ProgressData | null>(null)
  const [subjectName, setSubjectName] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get(`/progress/${subjectId}`),
      api.get(`/subjects/${subjectId}`),
    ])
      .then(([pr, sr]) => {
        setProgress(pr.data)
        setSubjectName(sr.data.name)
      })
      .finally(() => setLoading(false))
  }, [subjectId])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={20} className="animate-spin text-muted" />
      </div>
    )
  }

  if (!progress) return null

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <div className="mb-8">
        <p className="text-xs font-mono text-muted uppercase tracking-wider mb-1">Progress Report</p>
        <h1 className="font-display text-3xl text-lead">{subjectName}</h1>
      </div>
      <div className="mb-6">
        <ProgressStats
          totalTopics={progress.total_topics}
          completedTopics={progress.completed_topics}
          completionPercent={progress.completion_percent}
          avgQuizScore={progress.avg_quiz_score}
          timeSpentMinutes={progress.time_spent_minutes}
          lastActivity={progress.last_activity}
        />
      </div>
      <ConceptTags
        weakConcepts={progress.weak_concepts}
        strongConcepts={progress.strong_concepts}
      />
    </div>
  )
}