'use client'

import { Toaster } from 'react-hot-toast'

export default function ClientToaster() {
  return (
    <Toaster 
      position="top-right"
      toastOptions={{
        duration: 7000, // 7 seconds so users can read error messages
        style: {
          background: '#1a1a2e',
          color: '#f5f4ef',
          fontSize: '0.875rem',
          fontFamily: 'DM Sans, sans-serif',
          border: '1px solid #2a2a2a',
          borderRadius: '6px',
          maxWidth: '420px',
        },
        success: {
          duration: 5000, // Success can be shorter
          iconTheme: { primary: '#c8a96e', secondary: '#1a1a2e' },
        },
        error: {
          duration: 7000, // Errors stay longer so user can read them
          iconTheme: { primary: '#ef4444', secondary: '#1a1a2e' },
          style: {
            border: '1px solid rgba(239, 68, 68, 0.3)',
          },
        },
      }}
    />
  )
}
