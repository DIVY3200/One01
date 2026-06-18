'use client'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import { FileText } from 'lucide-react'

interface NoteViewerProps {
  content: string
  isEmpty?: boolean
}

export default function NoteViewer({ content, isEmpty = false }: NoteViewerProps) {
  if (isEmpty || !content.trim()) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center py-16 px-6">
        <FileText size={36} className="text-muted/25 mb-4" />
        <p className="text-sm font-medium text-muted mb-1">No notes yet</p>
        <p className="text-xs text-muted/60 max-w-xs">
          The Scribe Agent generates notes automatically after each lesson.
        </p>
      </div>
    )
  }

  return (
    <div className="prose-lead max-w-none px-8 py-6">
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[rehypeKatex]}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}