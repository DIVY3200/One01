import { useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle2, XCircle } from 'lucide-react'

interface QuickQuizProps {
  quizData: string
  onSelectOption?: (text: string) => void
}

export default function QuickQuiz({ quizData, onSelectOption }: QuickQuizProps) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [hasSubmitted, setHasSubmitted] = useState(false)

  let quiz: { question: string; options: string[]; correctIndex: number } | null = null
  try {
    quiz = JSON.parse(quizData)
  } catch (e) {
    // If it's streaming, the JSON will be incomplete. Show a loading state instead of an error.
    return (
      <div className="mt-4 p-5 bg-surface border border-border rounded-xl shadow-sm animate-pulse">
        <div className="h-4 bg-border rounded w-1/4 mb-4"></div>
        <div className="space-y-2">
          <div className="h-10 bg-border/50 rounded-lg w-full"></div>
          <div className="h-10 bg-border/50 rounded-lg w-full"></div>
        </div>
      </div>
    )
  }

  if (!quiz || !quiz.options) return null

  const handleSelect = (idx: number) => {
    if (hasSubmitted) return
    setSelectedIdx(idx)
    setHasSubmitted(true)
    if (onSelectOption) {
      const isCorrect = idx === quiz?.correctIndex
      const hashStr = (quiz as any)?.content_hash ? ` [Question Hash: ${(quiz as any).content_hash}]` : '';
      if (isCorrect) {
        onSelectOption(`I choose option ${idx + 1}: "${quiz?.options[idx]}". This is correct! Let's move to the next sub-concept.${hashStr}`)
      } else {
        onSelectOption(`I choose option ${idx + 1}: "${quiz?.options[idx]}". I think I misunderstood, let's try a different approach.${hashStr}`)
      }
    }
  }

  return (
    <div className="mt-4 p-5 bg-surface border border-border rounded-xl shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <span className="bg-accent/10 text-accent text-xs px-2 py-1 rounded font-semibold uppercase tracking-wider">
          Quick Quiz
        </span>
      </div>
      <h4 className="font-medium text-lead mb-4">{quiz.question}</h4>
      <div className="space-y-2">
        {quiz.options.map((opt, idx) => {
          const isSelected = selectedIdx === idx
          const isCorrect = hasSubmitted && idx === quiz!.correctIndex
          const isWrong = hasSubmitted && isSelected && !isCorrect

          let ringClass = 'border-border hover:border-indigo-500 bg-white text-slate-900'
          if (hasSubmitted) {
            if (isCorrect) ringClass = 'border-green-500 bg-green-50 text-green-800'
            else if (isWrong) ringClass = 'border-red-500 bg-red-50 text-red-800'
            else ringClass = 'border-border bg-white opacity-50 text-slate-900'
          } else if (isSelected) {
            ringClass = 'border-indigo-500 bg-indigo-50 text-indigo-700'
          }

          return (
            <button
              key={idx}
              onClick={() => handleSelect(idx)}
              disabled={hasSubmitted}
              className={`w-full text-left px-4 py-3 border rounded-lg transition-all flex items-center justify-between hover:scale-[1.01] active:scale-[0.98] ${ringClass}`}
            >
              <span className="text-sm font-medium">{opt}</span>
              {hasSubmitted && isCorrect && <CheckCircle2 className="text-green-500" size={18} />}
              {hasSubmitted && isWrong && <XCircle className="text-red-500" size={18} />}
            </button>
          )
        })}
      </div>
      {hasSubmitted && (
        <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="mt-4">
          {selectedIdx === quiz.correctIndex ? (
            <p className="text-green-600 text-sm font-medium">Correct! Moving you to the next topic...</p>
          ) : (
            <p className="text-red-600 text-sm font-medium">Not quite. The AI will explain this differently...</p>
          )}
        </motion.div>
      )}
    </div>
  )
}
