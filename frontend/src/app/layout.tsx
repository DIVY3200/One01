import type { Metadata } from 'next'
import './globals.css'
import ClientToaster from '../components/ui/ClientToaster'

export const metadata: Metadata = {
  title: 'One01 — Learn Anything, Grow Anywhere',
  description: 'Learn anything with your personal AI council of teachers',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>
        {children}
        <ClientToaster />
      </body>
    </html>
  )
}