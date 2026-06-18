'use client'
import { BarChart2, Clock, CheckCircle2, BookOpen } from 'lucide-react'

interface ProgressStatsProps {
  totalTopics: number
  completedTopics: number
  completionPercent: number
  avgQuizScore: number
  timeSpentMinutes: number
  lastActivity?: string | null
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ComponentType<{ size: number; className?: string }>
  label: string
  value: string
  sub?: string
  accent?: string
}) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <Icon size={15} className="text-muted" />
        <p className="text-xs text-muted">{label}</p>
      </div>
      <p className={`font-display text-3xl ${accent ?? 'text-lead'}`}>{value}</p>
      {sub && <p className="text-xs text-muted mt-1">{sub}</p>}
    </div>
  )
}

export default function ProgressStats({
  totalTopics,
  completedTopics,
  completionPercent,
  avgQuizScore,
  timeSpentMinutes,
  lastActivity,
}: ProgressStatsProps) {
  const scoreColor =
    avgQuizScore >= 75 ? 'text-success' :
    avgQuizScore >= 50 ? 'text-warn' :
    avgQuizScore > 0  ? 'text-error' : 'text-muted'

  const formattedTime =
    timeSpentMinutes < 60
      ? `${timeSpentMinutes}m`
      : `${Math.floor(timeSpentMinutes / 60)}h ${timeSpentMinutes % 60}m`

  return (
    <div className="space-y-5">
      {/* Completion bar */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <div className="flex justify-between items-end mb-3">
          <div>
            <p className="text-xs text-muted font-mono uppercase tracking-wide mb-1">
              Course Completion
            </p>
            <p className="text-sm text-ink">
              {completedTopics} of {totalTopics} topics done
            </p>
          </div>
          <p className="font-display text-3xl text-lead">{completionPercent}%</p>
        </div>
        <div className="h-2.5 bg-border rounded-full overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all duration-700 ease-out"
            style={{ width: `${completionPercent}%` }}
          />
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4">
        <StatCard
          icon={BarChart2}
          label="Avg Quiz Score"
          value={`${avgQuizScore > 0 ? avgQuizScore.toFixed(0) : '—'}%`}
          sub={avgQuizScore > 0 ? (avgQuizScore >= 70 ? 'On track 🎯' : 'Keep practicing') : 'No quizzes yet'}
          accent={scoreColor}
        />
        <StatCard
          icon={Clock}
          label="Time Spent"
          value={timeSpentMinutes > 0 ? formattedTime : '—'}
          sub={lastActivity ? `Last active ${new Date(lastActivity).toLocaleDateString()}` : undefined}
        />
        <StatCard
          icon={CheckCircle2}
          label="Completed"
          value={String(completedTopics)}
          sub="topics"
          accent="text-success"
        />
        <StatCard
          icon={BookOpen}
          label="Remaining"
          value={String(Math.max(0, totalTopics - completedTopics))}
          sub="topics left"
        />
      </div>
    </div>
  )
}