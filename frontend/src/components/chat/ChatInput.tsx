'use client'
import { useRef } from 'react'
import { Send, Loader2 } from 'lucide-react'

interface ChatInputProps {
  value: string
  onChange: (val: string) => void
  onSend: () => void
  disabled?: boolean
  streaming?: boolean
}

export default function ChatInput({ value, onChange, onSend, disabled, streaming }: ChatInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null)

  return (
    <div className="px-5 py-4 border-t border-border">
      <div className="flex gap-3 items-end">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              onSend()
            }
          }}
          placeholder="Ask a doubt, say 'next' to advance, or request a different explanation…"
          rows={1}
          className="flex-1 resize-none px-4 py-3 bg-surface border border-border rounded-xl text-sm text-ink placeholder:text-muted/40 focus:outline-none focus:border-accent transition-colors"
          style={{ minHeight: 44, maxHeight: 150 }}
        />
        <button
          onClick={onSend}
          disabled={!value.trim() || disabled || streaming}
          className="w-11 h-11 rounded-xl bg-lead flex items-center justify-center flex-shrink-0 hover:bg-lead/90 transition-all disabled:opacity-40"
        >
          {streaming ? (
            <Loader2 size={16} className="text-paper animate-spin" />
          ) : (
            <Send size={15} className="text-paper" />
          )}
        </button>
      </div>
      <p className="text-[11px] text-muted mt-2">Enter to send · Shift+Enter for new line · Say &quot;next&quot; to advance</p>
    </div>
  )
}
