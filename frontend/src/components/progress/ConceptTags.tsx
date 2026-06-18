'use client'
import { AlertCircle, CheckCircle2, Info } from 'lucide-react'

interface ConceptTagsProps {
    weakConcepts: string[]
    strongConcepts: string[]
}

export default function ConceptTags({ weakConcepts, strongConcepts }: ConceptTagsProps) {
    const hasData = weakConcepts.length > 0 || strongConcepts.length > 0

    if (!hasData) {
        return (
            <div className="bg-surface border border-border rounded-xl p-5 flex items-start gap-3">
                <Info size={16} className="text-muted mt-0.5 flex-shrink-0" />
                <p className="text-sm text-muted">
                    Complete quizzes to identify your strong and weak areas. The Examiner Agent will tag concepts automatically.
                </p>
            </div>
        )
    }

    return (
        <div className="space-y-4">
            {strongConcepts.length > 0 && (
                <div className="bg-surface border border-border rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <CheckCircle2 size={15} className="text-success" />
                        <p className="text-sm font-medium text-ink">Strong Areas</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {strongConcepts.map((c) => (
                            <span
                                key={c}
                                className="px-3 py-1 bg-success/8 text-success text-xs rounded-full border border-success/20 font-medium"
                            >
                                {c}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {weakConcepts.length > 0 && (
                <div className="bg-surface border border-border rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <AlertCircle size={15} className="text-warn" />
                        <p className="text-sm font-medium text-ink">Areas to Improve</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {weakConcepts.map((c) => (
                            <span
                                key={c}
                                className="px-3 py-1 bg-warn/8 text-warn text-xs rounded-full border border-warn/20 font-medium"
                            >
                                {c}
                            </span>
                        ))}
                    </div>
                    <p className="text-xs text-muted mt-3 flex items-center gap-1.5">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent" />
                        Tutor Agent will prioritize these concepts in your next lessons.
                    </p>
                </div>
            )}
        </div>
    )
}