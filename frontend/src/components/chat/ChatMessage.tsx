'use client'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import { useStore } from '@/store/useStore'
import QuickQuiz from './QuickQuiz'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  onSend?: (text: string) => void
}

export default function ChatMessage({ role, content, isStreaming, onSend }: ChatMessageProps) {
  const { preferences } = useStore()
  const aiName = preferences?.ai_teacher_name || 'Lead'

  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-2xl rounded-2xl px-5 py-4 bg-lead text-paper">
          <p className="text-sm leading-relaxed">{content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="w-7 h-7 rounded-full bg-lead flex items-center justify-center flex-shrink-0 mr-3 mt-1">
        <span className="text-accent text-xs font-mono">{aiName[0]}</span>
      </div>
      <div
        className={`max-w-2xl rounded-2xl px-5 py-4 bg-surface border border-border ${
          content === '' && isStreaming ? 'streaming-cursor' : ''
        }`}
      >
        <div className="prose-lead text-sm leading-relaxed">
          <ReactMarkdown
            remarkPlugins={[remarkMath, remarkGfm]}
            rehypePlugins={[rehypeKatex]}
            components={{
              code({ node, inline, className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || '')
                if (!inline && match && match[1] === 'quiz') {
                  const quizContent = String(children).replace(/\n$/, '')
                  return <QuickQuiz quizData={quizContent} onSelectOption={(msg) => onSend && onSend(msg)} />
                }
                return (
                  <code className={className} {...props}>
                    {children}
                  </code>
                )
              }
            }}
          >
            {content || ' '}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
