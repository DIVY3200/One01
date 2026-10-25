'use client'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import { useStore } from '@/store/useStore'
import QuickQuiz from './QuickQuiz'
import SourceList, { Source, sourceLabel } from '@/components/library/SourceList'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  onSend?: (text: string) => void
  sources?: Source[]
  query?: string
  aiFallback?: boolean // sample content because Gemini was unavailable
}

// A run of inline citations: [2], [1][3] or [1, 2]. Not a[1], [x](url) or [ref]: defs.
const CITATION_RUN = /(?<![\w\]])((?:\[\d{1,2}(?:,\s*\d{1,2})*\])+)(?![(\[:])/g

// Turn inline citations into links the renderer shows as badges.
// Code fences are left untouched so array indexing such as x = [1] survives.
function linkCitations(markdown: string, count: number) {
  if (!count) return markdown
  return markdown
    .split(/(```[\s\S]*?```)/g)
    .map((part, i) =>
      i % 2
        ? part
        : part.replace(CITATION_RUN, (run) => {
            const nums = (run.match(/\d+/g) ?? []).map(Number)
            return nums.every((n) => n >= 1 && n <= count)
              ? nums.map((n) => `[${n}](#cite-${n})`).join('')
              : run
          })
    )
    .join('')
}

export default function ChatMessage({ role, content, isStreaming, onSend, sources, query, aiFallback }: ChatMessageProps) {
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
        {aiFallback && (
          <p className="mb-3 px-3 py-1.5 rounded-md bg-warn/10 border border-warn/30 text-[11px] text-warn">
            Sample content — Gemini was unavailable, so this isn&apos;t a real AI answer.
          </p>
        )}
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
              },
              a({ node, href, children, ...props }: any) {
                if (href?.startsWith('#cite-')) {
                  const source = sources?.find((s) => s.n === Number(href.slice(6)))
                  return (
                    <sup className="citation" title={source ? sourceLabel(source) : undefined}>
                      {children}
                    </sup>
                  )
                }
                return (
                  <a href={href} {...props}>
                    {children}
                  </a>
                )
              },
            }}
          >
            {linkCitations(content || ' ', sources?.length ?? 0)}
          </ReactMarkdown>
        </div>
        {sources && sources.length > 0 && <SourceList sources={sources} query={query} />}
      </div>
    </div>
  )
}
