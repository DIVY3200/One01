'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { api } from '@/lib/api'
import toast from 'react-hot-toast'
import { Loader2, CheckCircle2, XCircle, HelpCircle, BookOpen } from 'lucide-react'

interface Question {
  question: string
  options?: string[]
  correct?: string
  explanation?: string
  expected_answer?: string
  key_points?: string[]
  solution_steps?: string[]
  final_answer?: string
  concept?: string
}

export default function QuizPanel() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const [topics, setTopics] = useState<Array<{ id: string; title: string }>>([])
  const [form, setForm] = useState({ topic_title: '', question_type: 'mcq', count: 5 })
  const [questions, setQuestions] = useState<Question[]>([])
  const [quizSetId, setQuizSetId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Interactive states
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [showInsight, setShowInsight] = useState<Record<number, boolean>>({})
  const [syncingNote, setSyncingNote] = useState<Record<number, boolean>>({})

  useEffect(() => {
    api.get(`/subjects/${subjectId}`).then((res) => {
      const ts = res.data.topics || []
      setTopics(ts)
      if (ts[0]) setForm((f) => ({ ...f, topic_title: ts[0].title }))
    })
  }, [subjectId])

  const handleGenerate = async () => {
    if (!form.topic_title) { toast.error('Select a topic'); return }
    setLoading(true)
    setQuestions([])
    setAnswers({})
    setShowInsight({})
    setSyncingNote({})
    setQuizSetId(null)
    try {
      const res = await api.post('/quiz/generate', {
        topic_id: null,
        subject_id: subjectId,
        topic_title: form.topic_title,
        question_type: form.question_type,
        count: form.count,
        quiz_types: [form.question_type],
      })
      if (res.data.quiz_sets?.[0]) {
        setQuestions(res.data.quiz_sets[0].questions)
        setQuizSetId(res.data.quiz_sets[0].id)
      }
      toast.success(`${form.count} questions generated!`)
    } catch {
      toast.error('Failed to generate questions')
    } finally {
      setLoading(false)
    }
  }

  // ── Adaptive Learning: sync insight to notes + flag weak points ──
  const syncInsightToNotes = async (q: Question, isCorrect: boolean) => {
    try {
      await api.post(`/notes/${subjectId}/sync-insight`, {
        concept: q.concept || form.topic_title,
        is_correct: isCorrect,
        explanation: q.explanation || q.expected_answer || 'Reviewed concept from quiz.',
      })
    } catch (err) {
      console.error('Failed to sync insight to notes', err)
    }
  }

  const handleOptionSelect = async (qIndex: number, optionText: string) => {
    if (answers[qIndex]) return // prevent changing answer
    setAnswers(prev => ({ ...prev, [qIndex]: optionText }))
    setShowInsight(prev => ({ ...prev, [qIndex]: true }))

    // Determine correctness
    const q = questions[qIndex]
    const correctLetter = (q.correct || '').replace(')', '').trim().toUpperCase()[0]
    const pickedIndex = q.options?.findIndex(o => o === optionText) ?? -1
    const pickedLetter = ['A', 'B', 'C', 'D', 'E'][pickedIndex] || ''
    const isCorrect = pickedLetter === correctLetter

    // Adaptive sync (fire-and-forget with UI indicator)
    setSyncingNote(prev => ({ ...prev, [qIndex]: true }))
    await syncInsightToNotes(q, isCorrect)
    setSyncingNote(prev => ({ ...prev, [qIndex]: false }))
  }

  const handleTextInput = (qIndex: number, text: string) => {
    setAnswers(prev => ({ ...prev, [qIndex]: text }))
  }

  const handleCheckReasoning = async (qIndex: number) => {
    if (!answers[qIndex]) return
    setShowInsight(prev => ({ ...prev, [qIndex]: true }))

    // For theory/numerical, sync as "reviewed" (not auto-graded)
    const q = questions[qIndex]
    setSyncingNote(prev => ({ ...prev, [qIndex]: true }))
    await syncInsightToNotes(q, false) // Flag for review
    setSyncingNote(prev => ({ ...prev, [qIndex]: false }))
  }

  const handleSubmitQuiz = async () => {
    if (!quizSetId) return
    const answeredCount = Object.keys(answers).length
    if (answeredCount < questions.length) {
      toast.error('Please answer all questions first!')
      return
    }

    setSubmitting(true)
    try {
      const orderedAnswers = questions.map((_, i) => answers[i] || '')
      await api.post('/quiz/submit', {
        quiz_set_id: quizSetId,
        answers: orderedAnswers,
      })
      toast.success('Quiz submitted! Notes & weak points synchronized.')
    } catch {
      toast.error('Failed to submit results')
    } finally {
      setSubmitting(false)
    }
  }

  const getOptionLetter = (idx: number) => ['A', 'B', 'C', 'D', 'E'][idx] || ''

  return (
    <div className="flex-1 overflow-y-auto max-h-[75vh]">
      <div className="max-w-2xl mx-auto px-6 py-10">
        <div className="mb-8">
          <p className="text-xs font-mono text-muted uppercase tracking-wider mb-1">Adaptive Learning</p>
          <h1 className="font-display text-3xl text-lead">Teacher's Quiz</h1>
          <p className="text-sm text-muted mt-1">Generate dynamic conceptual tests.</p>
        </div>

        {/* Generator form */}
        <div className="bg-surface border border-border rounded-xl p-5 mb-7">
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-muted mb-2">Topic Focus</label>
              <select
                value={form.topic_title}
                onChange={(e) => setForm({ ...form, topic_title: e.target.value })}
                className="w-full px-4 py-3 bg-paper border border-border rounded-lg text-sm text-slate-900 focus:outline-none focus:border-accent transition-colors"
              >
                {topics.map((t) => (
                  <option key={t.id} value={t.title}>{t.title}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-muted mb-2">Test Style</label>
                <select
                  value={form.question_type}
                  onChange={(e) => setForm({ ...form, question_type: e.target.value })}
                  className="w-full px-4 py-3 bg-paper border border-border rounded-lg text-sm text-slate-900 focus:outline-none focus:border-accent transition-colors"
                >
                  <option value="mcq">Conceptual MCQ</option>
                  <option value="theory">Deep Theory</option>
                  <option value="numerical">Advanced Numerical</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-muted mb-2">Length</label>
                <select
                  value={form.count}
                  onChange={(e) => setForm({ ...form, count: Number(e.target.value) })}
                  className="w-full px-4 py-3 bg-paper border border-border rounded-lg text-sm text-slate-900 focus:outline-none focus:border-accent transition-colors"
                >
                  {[3, 5, 8, 10, 15].map((n) => (
                    <option key={n} value={n}>{n} Questions</option>
                  ))}
                </select>
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={loading}
              className="w-full py-3 bg-lead text-paper rounded-lg text-sm font-medium hover:bg-lead/90 transition-all disabled:opacity-40 flex items-center justify-center gap-2 cursor-pointer"
            >
              {loading ? <><Loader2 size={14} className="animate-spin" />Building Test...</> : 'Generate Test →'}
            </button>
          </div>
        </div>

        {/* Loading Skeleton — removed from DOM when done so it can't block pointer events */}
        {loading && (
          <div className="space-y-5 animate-pulse">
            <div className="p-4 bg-muted/10 rounded-lg text-center text-sm text-muted">
              Professor agent is preparing your test...
            </div>
            {[1, 2, 3].map(i => (
              <div key={i} className="bg-surface border border-border rounded-xl p-5 h-40"></div>
            ))}
          </div>
        )}

        {/* Questions list — scrollable container with proper height */}
        {!loading && questions.length > 0 && (
          <div className="space-y-5 pb-8">
            <p className="text-xs font-mono text-muted uppercase tracking-wider">{questions.length} Questions</p>
            {questions.map((q, i) => {
              const answered = !!answers[i]
              const showInsightBox = showInsight[i]
              const correctLetter = (q.correct || '').replace(')', '').trim().toUpperCase()[0]

              let isCorrectUserAnswer = false
              if (q.options) {
                const pickedIndex = q.options.findIndex(o => answers[i] === o)
                if (pickedIndex >= 0) {
                  const pickedLetter = getOptionLetter(pickedIndex)
                  isCorrectUserAnswer = pickedLetter === correctLetter
                }
              }

              return (
                <div key={i} className="bg-white border border-border rounded-xl p-5 shadow-sm">
                  <p className="text-sm font-medium text-slate-900 mb-4">
                    <span className="font-mono text-muted mr-2">Q{i + 1}.</span>
                    {q.question}
                  </p>

                  {/* MCQ Options — explicit text-slate-900 + bg-white for visibility */}
                  {q.options && (
                    <div className="space-y-2 mb-4">
                      {q.options.map((opt, j) => {
                        const letter = getOptionLetter(j)
                        const isCorrectOpt = letter === correctLetter
                        const isSelected = answers[i] === opt

                        let btnClass = 'border-border hover:border-accent/70 text-slate-900 bg-white'
                        if (answered) {
                          if (isCorrectOpt) btnClass = 'border-green-500 bg-green-50 text-green-800'
                          else if (isSelected && !isCorrectOpt) btnClass = 'border-red-500 bg-red-50 text-red-800'
                          else btnClass = 'border-border opacity-50 text-slate-500 bg-white'
                        }

                        return (
                          <button
                            key={j}
                            disabled={answered}
                            onClick={() => handleOptionSelect(i, opt)}
                            className={`w-full text-left px-4 py-3 rounded-lg text-sm border transition-all flex items-center justify-between cursor-pointer disabled:cursor-default ${btnClass}`}
                          >
                            <span className="text-slate-900 font-medium">
                              <span className="font-mono text-xs mr-2 opacity-60">{letter})</span>
                              {opt.replace(/^[A-E]\)\s?/, '')}
                            </span>
                            {answered && isCorrectOpt && <CheckCircle2 className="text-green-500 flex-shrink-0" size={16} />}
                            {answered && isSelected && !isCorrectOpt && <XCircle className="text-red-500 flex-shrink-0" size={16} />}
                          </button>
                        )
                      })}
                    </div>
                  )}

                  {/* Theory/Numerical Free Text */}
                  {!q.options && (
                    <div className="mb-4">
                      <textarea
                        className="w-full p-3 bg-white border border-border rounded-lg text-sm text-slate-900 focus:border-accent outline-none resize-none"
                        rows={3}
                        placeholder="Type your reasoning or final numeric answer..."
                        disabled={showInsightBox}
                        value={answers[i] || ''}
                        onChange={(e) => handleTextInput(i, e.target.value)}
                      />
                      {!showInsightBox && (
                        <button
                          onClick={() => handleCheckReasoning(i)}
                          disabled={!answers[i]}
                          className="mt-2 text-xs bg-lead text-white px-4 py-2 rounded-lg disabled:opacity-50 cursor-pointer hover:bg-lead/90 transition-colors"
                        >
                          Check Reasoning
                        </button>
                      )}
                    </div>
                  )}

                  {/* Teacher's Insight Pop-up with adaptive sync indicator */}
                  {showInsightBox && (
                    <div className={`mt-4 p-4 rounded-lg border ${!q.options || isCorrectUserAnswer ? 'border-accent/30 bg-accent/5' : 'border-red-200 bg-red-50/50'}`}>
                      <div className="flex items-center gap-2 mb-2">
                        <HelpCircle size={14} className={!q.options || isCorrectUserAnswer ? 'text-accent' : 'text-red-500'} />
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-800 font-mono">
                          Teacher's Insight
                        </span>
                        {syncingNote[i] && (
                          <span className="ml-auto flex items-center gap-1 text-[10px] text-muted">
                            <Loader2 size={10} className="animate-spin" /> syncing to notes…
                          </span>
                        )}
                        {!syncingNote[i] && showInsight[i] && (
                          <span className="ml-auto flex items-center gap-1 text-[10px] text-green-600">
                            <BookOpen size={10} /> saved to notes
                          </span>
                        )}
                      </div>

                      {/* Correct/Wrong verdict for MCQs */}
                      {q.options && (
                        <div className={`text-sm font-semibold mb-2 ${isCorrectUserAnswer ? 'text-green-700' : 'text-red-600'}`}>
                          {isCorrectUserAnswer ? '✓ Correct!' : `✗ Incorrect — The correct answer is ${correctLetter})`}
                        </div>
                      )}

                      {q.explanation && <p className="text-sm text-slate-800 mb-2">{q.explanation}</p>}
                      {q.expected_answer && (
                        <div className="mb-2">
                          <span className="text-xs font-semibold text-muted">Expected Approach: </span>
                          <span className="text-sm text-slate-800">{q.expected_answer}</span>
                        </div>
                      )}
                      {q.solution_steps && (
                        <div className="mb-2">
                          <span className="text-xs font-semibold text-muted">Solution Steps: </span>
                          <ul className="list-decimal pl-4 mt-1">
                            {q.solution_steps.map((s, k) => <li key={k} className="text-sm text-slate-800 mb-1">{s}</li>)}
                          </ul>
                          {q.final_answer && <p className="text-sm font-medium text-lead mt-2">Target Answer: {q.final_answer}</p>}
                        </div>
                      )}
                      {q.key_points && (
                        <ul className="list-disc pl-4 mt-2">
                          {q.key_points.map((kp, k) => <li key={k} className="text-xs text-slate-700 opacity-80">{kp}</li>)}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              )
            })}

            {/* Submit button */}
            <div className="pt-4 pb-8 flex justify-end">
              <button
                onClick={handleSubmitQuiz}
                disabled={submitting || Object.keys(answers).length < questions.length}
                className="px-6 py-3 bg-accent text-white rounded-lg font-medium hover:bg-accent/90 disabled:opacity-50 flex items-center gap-2 cursor-pointer transition-all"
              >
                {submitting && <Loader2 size={16} className="animate-spin" />}
                Finish & Analyze Knowledge Gaps
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}